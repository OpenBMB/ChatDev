# Copyright 2017-2020 Palantir Technologies, Inc.
# Copyright 2021- Python Language Server Contributors.

import logging
from pathlib import Path

from pylsp import hookimpl
from pylsp.lsp import SymbolKind

log = logging.getLogger(__name__)


@hookimpl
def pylsp_document_symbols(config, document):
    # pylint: disable=broad-except
    # pylint: disable=too-many-nested-blocks
    # pylint: disable=too-many-locals
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-statements

    symbols_settings = config.plugin_settings('jedi_symbols')
    all_scopes = symbols_settings.get('all_scopes', True)
    add_import_symbols = symbols_settings.get('include_import_symbols', True)
    definitions = document.jedi_names(all_scopes=all_scopes)
    symbols = []
    exclude = set({})
    redefinitions = {}

    while definitions != []:
        d = definitions.pop(0)

        # Skip symbols imported from other modules.
        if not add_import_symbols:
            # Skip if there's an import in the code the symbol is defined.
            code = d.get_line_code()
            if ' import ' in code or 'import ' in code:
                continue

            # Skip imported symbols comparing module names.
            sym_full_name = d.full_name
            if sym_full_name is not None:
                document_dot_path = document.dot_path

                # We assume a symbol is imported from another module to start
                # with.
                imported_symbol = True

                # The last element of sym_full_name is the symbol itself, so
                # we need to discard it to do module comparisons below.
                if '.' in sym_full_name:
                    sym_module_name = sym_full_name.rpartition('.')[0]
                else:
                    sym_module_name = sym_full_name

                # This is necessary to display symbols in init files (the checks
                # below fail without it).
                if document_dot_path.endswith('__init__'):
                    document_dot_path = document_dot_path.rpartition('.')[0]

                # document_dot_path is the module where the symbol is imported,
                # whereas sym_module_name is the one where it was declared.
                if document_dot_path in sym_module_name:
                    # If document_dot_path is in sym_module_name, we can safely assume
                    # that the symbol was declared in the document.
                    imported_symbol = False
                elif sym_module_name.split('.')[0] in document_dot_path.split('.'):
                    # If the first module in sym_module_name is one of the modules in
                    # document_dot_path, we need to check if sym_module_name starts
                    # with the modules in document_dot_path.
                    document_mods = document_dot_path.split('.')
                    for i in range(1, len(document_mods) + 1):
                        submod = '.'.join(document_mods[-i:])
                        if sym_module_name.startswith(submod):
                            imported_symbol = False
                            break

                # When there's no __init__.py next to a file or in one of its
                # parents, the checks above fail. However, Jedi has a nice way
                # to tell if the symbol was declared in the same file: if
                # sym_module_name starts by __main__.
                if imported_symbol:
                    if not sym_module_name.startswith('__main__'):
                        continue
            else:
                # We need to skip symbols if their definition doesn't have `full_name` info, they
                # are detected as a definition, but their description (e.g. `class Foo`) doesn't
                # match the code where they're detected by Jedi. This happens for relative imports.
                if _include_def(d):
                    if d.description not in d.get_line_code():
                        continue
                else:
                    continue

        if _include_def(d) and Path(document.path) == Path(d.module_path):
            tuple_range = _tuple_range(d)
            if tuple_range in exclude:
                continue

            kind = redefinitions.get(tuple_range, None)
            if kind is not None:
                exclude |= {tuple_range}

            if d.type == 'statement':
                if d.description.startswith('self'):
                    kind = 'field'

            symbol = {
                'name': d.name,
                'containerName': _container(d),
                'location': {
                    'uri': document.uri,
                    'range': _range(d),
                },
                'kind': _kind(d) if kind is None else _SYMBOL_KIND_MAP[kind],
            }
            symbols.append(symbol)

            if d.type == 'class':
                try:
                    defined_names = list(d.defined_names())
                    for method in defined_names:
                        if method.type == 'function':
                            redefinitions[_tuple_range(method)] = 'method'
                        elif method.type == 'statement':
                            redefinitions[_tuple_range(method)] = 'field'
                        else:
                            redefinitions[_tuple_range(method)] = method.type
                    definitions = list(defined_names) + definitions
                except Exception:
                    pass
    return symbols


def _include_def(definition):
    return (
        # Don't tend to include parameters as symbols
        definition.type != 'param' and
        # Unused vars should also be skipped
        definition.name != '_' and
        _kind(definition) is not None
    )


def _container(definition):
    try:
        # Jedi sometimes fails here.
        parent = definition.parent()
        # Here we check that a grand-parent exists to avoid declaring symbols
        # as children of the module.
        if parent.parent():
            return parent.name
    except:  # pylint: disable=bare-except
        return None

    return None


def _range(definition):
    # This gets us more accurate end position
    definition = definition._name.tree_name.get_definition()
    (start_line, start_column) = definition.start_pos
    (end_line, end_column) = definition.end_pos
    return {
        'start': {'line': start_line - 1, 'character': start_column},
        'end': {'line': end_line - 1, 'character': end_column}
    }


def _tuple_range(definition):
    definition = definition._name.tree_name.get_definition()
    return (definition.start_pos, definition.end_pos)


_SYMBOL_KIND_MAP = {
    'none': SymbolKind.Variable,
    'type': SymbolKind.Class,
    'tuple': SymbolKind.Class,
    'dict': SymbolKind.Class,
    'dictionary': SymbolKind.Class,
    'function': SymbolKind.Function,
    'lambda': SymbolKind.Function,
    'generator': SymbolKind.Function,
    'class': SymbolKind.Class,
    'instance': SymbolKind.Class,
    'method': SymbolKind.Method,
    'builtin': SymbolKind.Class,
    'builtinfunction': SymbolKind.Function,
    'module': SymbolKind.Module,
    'file': SymbolKind.File,
    'xrange': SymbolKind.Array,
    'slice': SymbolKind.Class,
    'traceback': SymbolKind.Class,
    'frame': SymbolKind.Class,
    'buffer': SymbolKind.Array,
    'dictproxy': SymbolKind.Class,
    'funcdef': SymbolKind.Function,
    'property': SymbolKind.Property,
    'import': SymbolKind.Module,
    'keyword': SymbolKind.Variable,
    'constant': SymbolKind.Constant,
    'variable': SymbolKind.Variable,
    'value': SymbolKind.Variable,
    'param': SymbolKind.Variable,
    'statement': SymbolKind.Variable,
    'boolean': SymbolKind.Boolean,
    'int': SymbolKind.Number,
    'longlean': SymbolKind.Number,
    'float': SymbolKind.Number,
    'complex': SymbolKind.Number,
    'string': SymbolKind.String,
    'unicode': SymbolKind.String,
    'list': SymbolKind.Array,
    'field': SymbolKind.Field
}


def _kind(d):
    """ Return the VSCode Symbol Type """
    return _SYMBOL_KIND_MAP.get(d.type)
