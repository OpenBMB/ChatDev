# Copyright 2017-2020 Palantir Technologies, Inc.
# Copyright 2021- Python Language Server Contributors.

import logging

import pycodestyle

from pylsp import hookimpl, lsp
from pylsp._utils import get_eol_chars

try:
    from autopep8 import continued_indentation as autopep8_c_i
except ImportError:
    pass
else:
    # Check if autopep8's continued_indentation implementation
    # is overriding pycodestyle's and if so, re-register
    # the check using pycodestyle's implementation as expected
    if autopep8_c_i in pycodestyle._checks['logical_line']:
        del pycodestyle._checks['logical_line'][autopep8_c_i]
        pycodestyle.register_check(pycodestyle.continued_indentation)

log = logging.getLogger(__name__)


@hookimpl
def pylsp_lint(workspace, document):
    with workspace.report_progress("lint: pycodestyle"):
        config = workspace._config
        settings = config.plugin_settings('pycodestyle', document_path=document.path)
        log.debug("Got pycodestyle settings: %s", settings)

        opts = {
            'exclude': settings.get('exclude'),
            'filename': settings.get('filename'),
            'hang_closing': settings.get('hangClosing'),
            'ignore': settings.get('ignore'),
            'max_line_length': settings.get('maxLineLength'),
            'indent_size': settings.get('indentSize'),
            'select': settings.get('select'),
        }
        kwargs = {k: v for k, v in opts.items() if v}
        styleguide = pycodestyle.StyleGuide(kwargs)

        # Use LF to lint file because other line endings can give false positives.
        # See spyder-ide/spyder#19565 for context.
        source = document.source
        eol_chars = get_eol_chars(source)
        if eol_chars in ['\r', '\r\n']:
            source = source.replace(eol_chars, '\n')
            lines = source.splitlines(keepends=True)
        else:
            lines = document.lines

        c = pycodestyle.Checker(
            filename=document.path, lines=lines, options=styleguide.options,
            report=PyCodeStyleDiagnosticReport(styleguide.options)
        )
        c.check_all()
        diagnostics = c.report.diagnostics

        return diagnostics


class PyCodeStyleDiagnosticReport(pycodestyle.BaseReport):

    def __init__(self, options):
        self.diagnostics = []
        super().__init__(options=options)

    def error(self, line_number, offset, text, check):
        code = text[:4]
        if self._ignore_code(code):
            return

        # Don't care about expected errors or warnings
        if code in self.expected:
            return

        # PyCodeStyle will sometimes give you an error the line after the end of the file
        #   e.g. no newline at end of file
        # In that case, the end offset should just be some number ~100
        # (because why not? There's nothing to underline anyways)
        err_range = {
            'start': {'line': line_number - 1, 'character': offset},
            'end': {
                # FIXME: It's a little naiive to mark until the end of the line, can we not easily do better?
                'line': line_number - 1,
                'character': 100 if line_number > len(self.lines) else len(self.lines[line_number - 1])
            },
        }
        diagnostic = {
            'source': 'pycodestyle',
            'range': err_range,
            'message': text,
            'code': code,
            # Are style errors really ever errors?
            'severity': _get_severity(code)
        }
        if code.startswith('W6'):
            diagnostic['tags'] = [lsp.DiagnosticTag.Deprecated]
        self.diagnostics.append(diagnostic)


def _get_severity(code):
    # Are style errors ever really errors?
    if code[0] == 'E' or code[0] == 'W':
        return lsp.DiagnosticSeverity.Warning
    # If no severity is specified, why wouldn't this be informational only?
    return lsp.DiagnosticSeverity.Information
