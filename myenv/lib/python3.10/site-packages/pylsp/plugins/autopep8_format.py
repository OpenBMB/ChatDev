# Copyright 2017-2020 Palantir Technologies, Inc.
# Copyright 2021- Python Language Server Contributors.

import logging

import pycodestyle
from autopep8 import fix_code, continued_indentation as autopep8_c_i

from pylsp import hookimpl
from pylsp._utils import get_eol_chars

log = logging.getLogger(__name__)


@hookimpl(tryfirst=True)  # Prefer autopep8 over YAPF
def pylsp_format_document(config, workspace, document, options):  # pylint: disable=unused-argument
    with workspace.report_progress("format: autopep8"):
        log.info("Formatting document %s with autopep8", document)
        return _format(config, document)


@hookimpl(tryfirst=True)  # Prefer autopep8 over YAPF
def pylsp_format_range(
    config, workspace, document, range, options
):  # pylint: disable=redefined-builtin,unused-argument
    with workspace.report_progress("format_range: autopep8"):
        log.info("Formatting document %s in range %s with autopep8", document, range)

        # First we 'round' the range up/down to full lines only
        range['start']['character'] = 0
        range['end']['line'] += 1
        range['end']['character'] = 0

        # Add 1 for 1-indexing vs LSP's 0-indexing
        line_range = (range['start']['line'] + 1, range['end']['line'] + 1)
        return _format(config, document, line_range=line_range)


def _format(config, document, line_range=None):
    options = _autopep8_config(config, document)
    if line_range:
        options['line_range'] = list(line_range)

    # Temporarily re-monkey-patch the continued_indentation checker - #771
    del pycodestyle._checks['logical_line'][pycodestyle.continued_indentation]
    pycodestyle.register_check(autopep8_c_i)

    # Autopep8 doesn't work with CR line endings, so we replace them by '\n'
    # and restore them below.
    replace_cr = False
    source = document.source
    eol_chars = get_eol_chars(source)
    if eol_chars == '\r':
        replace_cr = True
        source = source.replace('\r', '\n')

    new_source = fix_code(source, options=options)

    # Switch it back
    del pycodestyle._checks['logical_line'][autopep8_c_i]
    pycodestyle.register_check(pycodestyle.continued_indentation)

    if new_source == source:
        return []

    if replace_cr:
        new_source = new_source.replace('\n', '\r')

    # I'm too lazy at the moment to parse diffs into TextEdit items
    # So let's just return the entire file...
    return [{
        'range': {
            'start': {'line': 0, 'character': 0},
            # End char 0 of the line after our document
            'end': {'line': len(document.lines), 'character': 0}
        },
        'newText': new_source
    }]


def _autopep8_config(config, document=None):
    # We user pycodestyle settings to avoid redefining things
    path = document.path if document is not None else None
    settings = config.plugin_settings('pycodestyle', document_path=path)
    options = {
        'exclude': settings.get('exclude'),
        'hang_closing': settings.get('hangClosing'),
        'ignore': settings.get('ignore'),
        'max_line_length': settings.get('maxLineLength'),
        'select': settings.get('select'),
        'aggressive': settings.get('aggressive'),
    }

    # Filter out null options
    return {k: v for k, v in options.items() if v}
