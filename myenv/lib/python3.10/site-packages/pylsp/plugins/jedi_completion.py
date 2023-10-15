# Copyright 2017-2020 Palantir Technologies, Inc.
# Copyright 2021- Python Language Server Contributors.

import logging
import os

import parso

from pylsp import _utils, hookimpl, lsp
from pylsp.plugins._resolvers import LABEL_RESOLVER, SNIPPET_RESOLVER

log = logging.getLogger(__name__)

# Map to the LSP type
# > Valid values for type are ``module``, `` class ``, ``instance``, ``function``,
# > ``param``, ``path``, ``keyword``, ``property`` and ``statement``.
# see: https://jedi.readthedocs.io/en/latest/docs/api-classes.html#jedi.api.classes.BaseName.type
_TYPE_MAP = {
    'module': lsp.CompletionItemKind.Module,
    'namespace': lsp.CompletionItemKind.Module,    # to be added in Jedi 0.18+
    'class': lsp.CompletionItemKind.Class,
    'instance': lsp.CompletionItemKind.Reference,
    'function': lsp.CompletionItemKind.Function,
    'param': lsp.CompletionItemKind.Variable,
    'path': lsp.CompletionItemKind.File,
    'keyword': lsp.CompletionItemKind.Keyword,
    'property': lsp.CompletionItemKind.Property,    # added in Jedi 0.18
    'statement': lsp.CompletionItemKind.Variable
}

# Types of parso nodes for which snippet is not included in the completion
_IMPORTS = ('import_name', 'import_from')

# Types of parso node for errors
_ERRORS = ('error_node', )


@hookimpl
def pylsp_completions(config, document, position):
    """Get formatted completions for current code position"""
    # pylint: disable=too-many-locals
    settings = config.plugin_settings('jedi_completion', document_path=document.path)
    resolve_eagerly = settings.get('eager', False)
    code_position = _utils.position_to_jedi_linecolumn(document, position)

    code_position['fuzzy'] = settings.get('fuzzy', False)
    completions = document.jedi_script(use_document_path=True).complete(**code_position)

    if not completions:
        return None

    completion_capabilities = config.capabilities.get('textDocument', {}).get('completion', {})
    item_capabilities = completion_capabilities.get('completionItem', {})
    snippet_support = item_capabilities.get('snippetSupport')
    supported_markup_kinds = item_capabilities.get('documentationFormat', ['markdown'])
    preferred_markup_kind = _utils.choose_markup_kind(supported_markup_kinds)

    should_include_params = settings.get('include_params')
    should_include_class_objects = settings.get('include_class_objects', False)
    should_include_function_objects = settings.get('include_function_objects', False)

    max_to_resolve = settings.get('resolve_at_most', 25)
    modules_to_cache_for = settings.get('cache_for', None)
    if modules_to_cache_for is not None:
        LABEL_RESOLVER.cached_modules = modules_to_cache_for
        SNIPPET_RESOLVER.cached_modules = modules_to_cache_for

    include_params = snippet_support and should_include_params and use_snippets(document, position)
    include_class_objects = snippet_support and should_include_class_objects and use_snippets(document, position)
    include_function_objects = snippet_support and should_include_function_objects and use_snippets(document, position)

    ready_completions = [
        _format_completion(
            c,
            markup_kind=preferred_markup_kind,
            include_params=include_params if c.type in ["class", "function"] else False,
            resolve=resolve_eagerly,
            resolve_label_or_snippet=(i < max_to_resolve)
        )
        for i, c in enumerate(completions)
    ]

    # TODO split up once other improvements are merged
    if include_class_objects:
        for i, c in enumerate(completions):
            if c.type == 'class':
                completion_dict = _format_completion(
                    c,
                    markup_kind=preferred_markup_kind,
                    include_params=False,
                    resolve=resolve_eagerly,
                    resolve_label_or_snippet=(i < max_to_resolve)
                )
                completion_dict['kind'] = lsp.CompletionItemKind.TypeParameter
                completion_dict['label'] += ' object'
                ready_completions.append(completion_dict)

    if include_function_objects:
        for i, c in enumerate(completions):
            if c.type == 'function':
                completion_dict = _format_completion(
                    c,
                    markup_kind=preferred_markup_kind,
                    include_params=False,
                    resolve=resolve_eagerly,
                    resolve_label_or_snippet=(i < max_to_resolve)
                )
                completion_dict['kind'] = lsp.CompletionItemKind.TypeParameter
                completion_dict['label'] += ' object'
                ready_completions.append(completion_dict)

    for completion_dict in ready_completions:
        completion_dict['data'] = {
            'doc_uri': document.uri
        }

    # most recently retrieved completion items, used for resolution
    document.shared_data['LAST_JEDI_COMPLETIONS'] = {
        # label is the only required property; here it is assumed to be unique
        completion['label']: (completion, data)
        for completion, data in zip(ready_completions, completions)
    }

    return ready_completions or None


@hookimpl
def pylsp_completion_item_resolve(config, completion_item, document):
    """Resolve formatted completion for given non-resolved completion"""
    shared_data = document.shared_data['LAST_JEDI_COMPLETIONS'].get(completion_item['label'])

    completion_capabilities = config.capabilities.get('textDocument', {}).get('completion', {})
    item_capabilities = completion_capabilities.get('completionItem', {})
    supported_markup_kinds = item_capabilities.get('documentationFormat', ['markdown'])
    preferred_markup_kind = _utils.choose_markup_kind(supported_markup_kinds)

    if shared_data:
        completion, data = shared_data
        return _resolve_completion(completion, data, markup_kind=preferred_markup_kind)
    return completion_item


def is_exception_class(name):
    """
    Determine if a class name is an instance of an Exception.

    This returns `False` if the name given corresponds with a instance of
    the 'Exception' class, `True` otherwise
    """
    try:
        return name in [cls.__name__ for cls in Exception.__subclasses__()]
    except AttributeError:
        # Needed in case a class don't uses new-style
        # class definition in Python 2
        return False


def use_snippets(document, position):
    """
    Determine if it's necessary to return snippets in code completions.

    This returns `False` if a completion is being requested on an import
    statement, `True` otherwise.
    """
    line = position['line']
    lines = document.source.split('\n', line)
    act_lines = [lines[line][:position['character']]]
    line -= 1
    last_character = ''
    while line > -1:
        act_line = lines[line]
        if (act_line.rstrip().endswith('\\') or
                act_line.rstrip().endswith('(') or
                act_line.rstrip().endswith(',')):
            act_lines.insert(0, act_line)
            line -= 1
            if act_line.rstrip().endswith('('):
                # Needs to be added to the end of the code before parsing
                # to make it valid, otherwise the node type could end
                # being an 'error_node' for multi-line imports that use '('
                last_character = ')'
        else:
            break
    if '(' in act_lines[-1].strip():
        last_character = ')'
    code = '\n'.join(act_lines).rsplit(';', maxsplit=1)[-1].strip() + last_character
    tokens = parso.parse(code)
    expr_type = tokens.children[0].type
    return (expr_type not in _IMPORTS and
            not (expr_type in _ERRORS and 'import' in code))


def _resolve_completion(completion, d, markup_kind: str):
    # pylint: disable=broad-except
    completion['detail'] = _detail(d)
    try:
        docs = _utils.format_docstring(
            d.docstring(raw=True),
            signatures=[
                signature.to_string()
                for signature in d.get_signatures()
            ],
            markup_kind=markup_kind
        )
    except Exception:
        docs = ''
    completion['documentation'] = docs
    return completion


def _format_completion(d, markup_kind: str, include_params=True, resolve=False, resolve_label_or_snippet=False):
    completion = {
        'label': _label(d, resolve_label_or_snippet),
        'kind': _TYPE_MAP.get(d.type),
        'sortText': _sort_text(d),
        'insertText': d.name
    }

    if resolve:
        completion = _resolve_completion(completion, d, markup_kind)

    # Adjustments for file completions
    if d.type == 'path':
        path = os.path.normpath(d.name)
        path = path.replace('\\', '\\\\')
        path = path.replace('/', '\\/')

        # If the completion ends with os.sep, it means it's a directory. So we add an escaped os.sep
        # at the end to ease additional file completions.
        if d.name.endswith(os.sep):
            if os.name == 'nt':
                path = path + '\\\\'
            else:
                path = path + '\\/'

        completion['insertText'] = path

    if include_params and not is_exception_class(d.name):
        snippet = _snippet(d, resolve_label_or_snippet)
        completion.update(snippet)

    return completion


def _label(definition, resolve=False):
    if not resolve:
        return definition.name
    sig = LABEL_RESOLVER.get_or_create(definition)
    if sig:
        return sig
    return definition.name


def _snippet(definition, resolve=False):
    if not resolve:
        return {}
    snippet = SNIPPET_RESOLVER.get_or_create(definition)
    return snippet


def _detail(definition):
    try:
        return definition.parent().full_name or ''
    except AttributeError:
        return definition.full_name or ''


def _sort_text(definition):
    """ Ensure builtins appear at the bottom.
    Description is of format <type>: <module>.<item>
    """

    # If its 'hidden', put it next last
    prefix = 'z{}' if definition.name.startswith('_') else 'a{}'
    return prefix.format(definition.name)
