# Copyright 2017-2020 Palantir Technologies, Inc.
# Copyright 2021- Python Language Server Contributors.

import logging
import os

from yapf.yapflib import file_resources, style
from yapf.yapflib.yapf_api import FormatCode

import whatthepatch

from pylsp import hookimpl
from pylsp._utils import get_eol_chars

log = logging.getLogger(__name__)


@hookimpl
def pylsp_format_document(workspace, document, options):
    log.info("Formatting document %s with yapf", document)
    with workspace.report_progress("format: yapf"):
        return _format(document, options=options)


@hookimpl
def pylsp_format_range(workspace, document, range, options):  # pylint: disable=redefined-builtin
    log.info("Formatting document %s in range %s with yapf", document, range)
    with workspace.report_progress("format_range: yapf"):
        # First we 'round' the range up/down to full lines only
        range['start']['character'] = 0
        range['end']['line'] += 1
        range['end']['character'] = 0

        # From Yapf docs:
        # lines: (list of tuples of integers) A list of tuples of lines, [start, end],
        #   that we want to format. The lines are 1-based indexed. It can be used by
        #   third-party code (e.g., IDEs) when reformatting a snippet of code rather
        #   than a whole file.

        # Add 1 for 1-indexing vs LSP's 0-indexing
        lines = [(range['start']['line'] + 1, range['end']['line'] + 1)]
        return _format(document, lines=lines, options=options)


def get_style_config(document_path, options=None):
    # Exclude file if it follows the patterns for that
    exclude_patterns_from_ignore_file = file_resources.GetExcludePatternsForDir(os.getcwd())
    if file_resources.IsIgnored(document_path, exclude_patterns_from_ignore_file):
        return []

    # Get the default styles as a string
    # for a preset configuration, i.e. "pep8"
    style_config = file_resources.GetDefaultStyleForDir(
        os.path.dirname(document_path)
    )
    if options is None:
        return style_config

    # We have options passed from LSP format request
    # let's pass them to the formatter.
    # First we want to get a dictionary of the preset style
    # to pass instead of a string so that we can modify it
    style_config = style.CreateStyleFromConfig(style_config)

    use_tabs = style_config['USE_TABS']
    indent_width = style_config['INDENT_WIDTH']

    if options.get('tabSize') is not None:
        indent_width = max(int(options.get('tabSize')), 1)

    if options.get('insertSpaces') is not None:
        # TODO is it guaranteed to be a boolean, or can it be a string?
        use_tabs = not options.get('insertSpaces')

        if use_tabs:
            # Indent width doesn't make sense when using tabs
            # the specifications state: "Size of a tab in spaces"
            indent_width = 1

    style_config['USE_TABS'] = use_tabs
    style_config['INDENT_WIDTH'] = indent_width
    style_config['CONTINUATION_INDENT_WIDTH'] = indent_width

    for style_option, value in options.items():
        # Apply arbitrary options passed as formatter options
        if style_option not in style_config:
            # ignore if it's not a known yapf config
            continue

        style_config[style_option] = value

    return style_config


def diff_to_text_edits(diff, eol_chars):
    # To keep things simple our text edits will be line based.
    # We will also return the edits uncompacted, meaning a
    # line replacement will come in as a line remove followed
    # by a line add instead of a line replace.
    text_edits = []
    # keep track of line number since additions
    # don't include the line number it's being added
    # to in diffs. lsp is 0-indexed so we'll start with -1
    prev_line_no = -1

    for change in diff.changes:
        if change.old and change.new:
            # old and new are the same line, no change
            # diffs are 1-indexed
            prev_line_no = change.old - 1
        elif change.new:
            # addition
            text_edits.append({
                'range': {
                    'start': {
                        'line': prev_line_no + 1,
                        'character': 0
                    },
                    'end': {
                        'line': prev_line_no + 1,
                        'character': 0
                    }
                },
                'newText': change.line + eol_chars
            })
        elif change.old:
            # remove
            lsp_line_no = change.old - 1
            text_edits.append({
                'range': {
                    'start': {
                        'line': lsp_line_no,
                        'character': 0
                    },
                    'end': {
                        # From LSP spec:
                        # If you want to specify a range that contains a line
                        # including the line ending character(s) then use an
                        # end position denoting the start of the next line.
                        'line': lsp_line_no + 1,
                        'character': 0
                    }
                },
                'newText': ''
            })
            prev_line_no = lsp_line_no

    return text_edits


def ensure_eof_new_line(document, eol_chars, text_edits):
    # diffs don't include EOF newline https://github.com/google/yapf/issues/1008
    # we'll add it ourselves if our document doesn't already have it and the diff
    # does not change the last line.
    if document.source.endswith(eol_chars):
        return

    lines = document.lines
    last_line_number = len(lines) - 1

    if text_edits and text_edits[-1]['range']['start']['line'] >= last_line_number:
        return

    text_edits.append({
        'range': {
            'start': {
                'line': last_line_number,
                'character': 0
            },
            'end': {
                'line': last_line_number + 1,
                'character': 0
            }
        },
        'newText': lines[-1] + eol_chars
    })


def _format(document, lines=None, options=None):
    source = document.source
    # Yapf doesn't work with CRLF/CR line endings, so we replace them by '\n'
    # and restore them below when adding new lines
    eol_chars = get_eol_chars(source)
    if eol_chars in ['\r', '\r\n']:
        source = source.replace(eol_chars, '\n')
    else:
        eol_chars = '\n'

    style_config = get_style_config(document_path=document.path, options=options)

    diff_txt, changed = FormatCode(
        source,
        lines=lines,
        filename=document.filename,
        print_diff=True,
        style_config=style_config
    )

    if not changed:
        return []

    patch_generator = whatthepatch.parse_patch(diff_txt)
    diff = next(patch_generator)
    patch_generator.close()

    text_edits = diff_to_text_edits(diff=diff, eol_chars=eol_chars)

    ensure_eof_new_line(document=document, eol_chars=eol_chars, text_edits=text_edits)

    return text_edits
