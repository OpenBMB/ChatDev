# Copyright 2017-2020 Palantir Technologies, Inc.
# Copyright 2021- Python Language Server Contributors.

from collections import defaultdict
import logging
from time import time

from jedi.api.classes import Completion

from pylsp import lsp


log = logging.getLogger(__name__)


# ---- Base class
# -----------------------------------------------------------------------------
class Resolver:

    def __init__(self, callback, resolve_on_error, time_to_live=60 * 30):
        self.callback = callback
        self.resolve_on_error = resolve_on_error
        self._cache = {}
        self._time_to_live = time_to_live
        self._cache_ttl = defaultdict(set)
        self._clear_every = 2
        # see https://github.com/davidhalter/jedi/blob/master/jedi/inference/helpers.py#L194-L202
        self._cached_modules = {'pandas', 'numpy', 'tensorflow', 'matplotlib'}

    @property
    def cached_modules(self):
        return self._cached_modules

    @cached_modules.setter
    def cached_modules(self, new_value):
        self._cached_modules = set(new_value)

    def clear_outdated(self):
        now = self.time_key()
        to_clear = [
            timestamp
            for timestamp in self._cache_ttl
            if timestamp < now
        ]
        for time_key in to_clear:
            for key in self._cache_ttl[time_key]:
                del self._cache[key]
            del self._cache_ttl[time_key]

    def time_key(self):
        return int(time() / self._time_to_live)

    def get_or_create(self, completion: Completion):
        if not completion.full_name:
            use_cache = False
        else:
            module_parts = completion.full_name.split('.')
            use_cache = module_parts and module_parts[0] in self._cached_modules

        if use_cache:
            key = self._create_completion_id(completion)
            if key not in self._cache:
                if self.time_key() % self._clear_every == 0:
                    self.clear_outdated()

                self._cache[key] = self.resolve(completion)
                self._cache_ttl[self.time_key()].add(key)
            return self._cache[key]

        return self.resolve(completion)

    def _create_completion_id(self, completion: Completion):
        return (
            completion.full_name, completion.module_path,
            completion.line, completion.column,
            self.time_key()
        )

    def resolve(self, completion):
        try:
            sig = completion.get_signatures()
            return self.callback(completion, sig)
        except Exception as e:  # pylint: disable=broad-except
            log.warning(f'Something went wrong when resolving label for {completion}: {e}')
            return self.resolve_on_error


# ---- Label resolver
# -----------------------------------------------------------------------------
def format_label(completion, sig):
    if sig and completion.type in ('function', 'method'):
        params = ', '.join(param.name for param in sig[0].params)
        label = '{}({})'.format(completion.name, params)
        return label
    return completion.name


LABEL_RESOLVER = Resolver(callback=format_label, resolve_on_error='')


# ---- Snippets resolver
# -----------------------------------------------------------------------------
def format_snippet(completion, sig):
    if not sig:
        return {}

    snippet_completion = {}

    positional_args = [param for param in sig[0].params
                       if '=' not in param.description and
                       param.name not in {'/', '*'}]

    if len(positional_args) > 1:
        # For completions with params, we can generate a snippet instead
        snippet_completion['insertTextFormat'] = lsp.InsertTextFormat.Snippet
        snippet = completion.name + '('
        for i, param in enumerate(positional_args):
            snippet += '${%s:%s}' % (i + 1, param.name)
            if i < len(positional_args) - 1:
                snippet += ', '
        snippet += ')$0'
        snippet_completion['insertText'] = snippet
    elif len(positional_args) == 1:
        snippet_completion['insertTextFormat'] = lsp.InsertTextFormat.Snippet
        snippet_completion['insertText'] = completion.name + '($0)'
    else:
        snippet_completion['insertText'] = completion.name + '()'

    return snippet_completion


SNIPPET_RESOLVER = Resolver(callback=format_snippet, resolve_on_error={})
