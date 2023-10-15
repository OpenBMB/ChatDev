# Copyright 2017-2020 Palantir Technologies, Inc.
# Copyright 2021- Python Language Server Contributors.

import functools
import inspect
import logging
import os
import pathlib
import re
import threading
from typing import List, Optional

import docstring_to_markdown
import jedi

JEDI_VERSION = jedi.__version__

# Eol chars accepted by the LSP protocol
# the ordering affects performance
EOL_CHARS = ['\r\n', '\r', '\n']
EOL_REGEX = re.compile(f'({"|".join(EOL_CHARS)})')

log = logging.getLogger(__name__)


def debounce(interval_s, keyed_by=None):
    """Debounce calls to this function until interval_s seconds have passed."""
    def wrapper(func):
        timers = {}
        lock = threading.Lock()

        @functools.wraps(func)
        def debounced(*args, **kwargs):
            sig = inspect.signature(func)
            call_args = sig.bind(*args, **kwargs)
            key = call_args.arguments[keyed_by] if keyed_by else None

            def run():
                with lock:
                    del timers[key]
                return func(*args, **kwargs)

            with lock:
                old_timer = timers.get(key)
                if old_timer:
                    old_timer.cancel()

                timer = threading.Timer(interval_s, run)
                timers[key] = timer
                timer.start()
        return debounced
    return wrapper


def find_parents(root, path, names):
    """Find files matching the given names relative to the given path.

    Args:
        path (str): The file path to start searching up from.
        names (List[str]): The file/directory names to look for.
        root (str): The directory at which to stop recursing upwards.

    Note:
        The path MUST be within the root.
    """
    if not root:
        return []

    if not os.path.commonprefix((root, path)):
        log.warning("Path %s not in %s", path, root)
        return []

    # Split the relative by directory, generate all the parent directories, then check each of them.
    # This avoids running a loop that has different base-cases for unix/windows
    # e.g. /a/b and /a/b/c/d/e.py -> ['/a/b', 'c', 'd']
    dirs = [root] + os.path.relpath(os.path.dirname(path), root).split(os.path.sep)

    # Search each of /a/b/c, /a/b, /a
    while dirs:
        search_dir = os.path.join(*dirs)
        existing = list(filter(os.path.exists, [os.path.join(search_dir, n) for n in names]))
        if existing:
            return existing
        dirs.pop()

    # Otherwise nothing
    return []


def path_to_dot_name(path):
    """Given a path to a module, derive its dot-separated full name."""
    directory = os.path.dirname(path)
    module_name, _ = os.path.splitext(os.path.basename(path))
    full_name = [module_name]
    while os.path.exists(os.path.join(directory, '__init__.py')):
        this_directory = os.path.basename(directory)
        directory = os.path.dirname(directory)
        full_name = [this_directory] + full_name
    return '.'.join(full_name)


def match_uri_to_workspace(uri, workspaces):
    if uri is None:
        return None
    max_len, chosen_workspace = -1, None
    path = pathlib.Path(uri).parts
    for workspace in workspaces:
        workspace_parts = pathlib.Path(workspace).parts
        if len(workspace_parts) > len(path):
            continue
        match_len = 0
        for workspace_part, path_part in zip(workspace_parts, path):
            if workspace_part == path_part:
                match_len += 1
        if match_len > 0:
            if match_len > max_len:
                max_len = match_len
                chosen_workspace = workspace
    return chosen_workspace


def list_to_string(value):
    return ",".join(value) if isinstance(value, list) else value


def merge_dicts(dict_a, dict_b):
    """Recursively merge dictionary b into dictionary a.

    If override_nones is True, then
    """
    def _merge_dicts_(a, b):
        for key in set(a.keys()).union(b.keys()):
            if key in a and key in b:
                if isinstance(a[key], dict) and isinstance(b[key], dict):
                    yield (key, dict(_merge_dicts_(a[key], b[key])))
                elif isinstance(a[key], list) and isinstance(b[key], list):
                    yield (key, list(set(a[key] + b[key])))
                elif b[key] is not None:
                    yield (key, b[key])
                else:
                    yield (key, a[key])
            elif key in a:
                yield (key, a[key])
            elif b[key] is not None:
                yield (key, b[key])
    return dict(_merge_dicts_(dict_a, dict_b))


def escape_plain_text(contents: str) -> str:
    """
    Format plain text to display nicely in environments which do not respect whitespaces.
    """
    contents = contents.replace('\t', '\u00A0' * 4)
    contents = contents.replace('  ', '\u00A0' * 2)
    return contents


def escape_markdown(contents: str) -> str:
    """
    Format plain text to display nicely in Markdown environment.
    """
    # escape markdown syntax
    contents = re.sub(r'([\\*_#[\]])', r'\\\1', contents)
    # preserve white space characters
    contents = escape_plain_text(contents)
    return contents


def wrap_signature(signature):
    return '```python\n' + signature + '\n```\n'


SERVER_SUPPORTED_MARKUP_KINDS = {'markdown', 'plaintext'}


def choose_markup_kind(client_supported_markup_kinds: List[str]):
    """Choose a markup kind supported by both client and the server.

    This gives priority to the markup kinds provided earlier on the client preference list.
    """
    for kind in client_supported_markup_kinds:
        if kind in SERVER_SUPPORTED_MARKUP_KINDS:
            return kind
    return 'markdown'


def format_docstring(contents: str, markup_kind: str, signatures: Optional[List[str]] = None):
    """Transform the provided docstring into a MarkupContent object.

    If `markup_kind` is 'markdown' the docstring will get converted to
    markdown representation using `docstring-to-markdown`; if it is
    `plaintext`, it will be returned as plain text.
    Call signatures of functions (or equivalent code summaries)
    provided in optional `signatures` argument will be prepended
    to the provided contents of the docstring if given.
    """
    if not isinstance(contents, str):
        contents = ''

    if markup_kind == 'markdown':
        try:
            value = docstring_to_markdown.convert(contents)
            return {
                'kind': 'markdown',
                'value': value
            }
        except docstring_to_markdown.UnknownFormatError:
            # try to escape the Markdown syntax instead:
            value = escape_markdown(contents)

        if signatures:
            value = wrap_signature('\n'.join(signatures)) + '\n\n' + value

        return {
            'kind': 'markdown',
            'value': value
        }
    value = contents
    if signatures:
        value = '\n'.join(signatures) + '\n\n' + value
    return {
        'kind': 'plaintext',
        'value': escape_plain_text(value)
    }


def clip_column(column, lines, line_number):
    """
    Normalise the position as per the LSP that accepts character positions > line length

    https://microsoft.github.io/language-server-protocol/specification#position
    """
    max_column = len(lines[line_number].rstrip('\r\n')) if len(lines) > line_number else 0
    return min(column, max_column)


def position_to_jedi_linecolumn(document, position):
    """
    Convert the LSP format 'line', 'character' to Jedi's 'line', 'column'

    https://microsoft.github.io/language-server-protocol/specification#position
    """
    code_position = {}
    if position:
        code_position = {'line': position['line'] + 1,
                         'column': clip_column(position['character'],
                                               document.lines,
                                               position['line'])}
    return code_position


if os.name == 'nt':
    import ctypes

    kernel32 = ctypes.windll.kernel32
    PROCESS_QUERY_INFROMATION = 0x1000

    def is_process_alive(pid):
        """Check whether the process with the given pid is still alive.

        Running `os.kill()` on Windows always exits the process, so it can't be used to check for an alive process.
        see: https://docs.python.org/3/library/os.html?highlight=os%20kill#os.kill

        Hence ctypes is used to check for the process directly via windows API avoiding any other 3rd-party dependency.

        Args:
            pid (int): process ID

        Returns:
            bool: False if the process is not alive or don't have permission to check, True otherwise.
        """
        process = kernel32.OpenProcess(PROCESS_QUERY_INFROMATION, 0, pid)
        if process != 0:
            kernel32.CloseHandle(process)
            return True
        return False

else:
    import errno

    def is_process_alive(pid):
        """Check whether the process with the given pid is still alive.

        Args:
            pid (int): process ID

        Returns:
            bool: False if the process is not alive or don't have permission to check, True otherwise.
        """
        if pid < 0:
            return False
        try:
            os.kill(pid, 0)
        except OSError as e:
            return e.errno == errno.EPERM
        else:
            return True


def get_eol_chars(text):
    """Get EOL chars used in text."""
    match = EOL_REGEX.search(text)
    if match:
        return match.group(0)
    return None
