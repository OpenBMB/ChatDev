# Copyright 2017-2020 Palantir Technologies, Inc.
# Copyright 2021- Python Language Server Contributors.

from pyflakes import api as pyflakes_api, messages
from pylsp import hookimpl, lsp

# Pyflakes messages that should be reported as Errors instead of Warns
PYFLAKES_ERROR_MESSAGES = (
    messages.UndefinedName,
    messages.UndefinedExport,
    messages.UndefinedLocal,
    messages.DuplicateArgument,
    messages.FutureFeatureNotDefined,
    messages.ReturnOutsideFunction,
    messages.YieldOutsideFunction,
    messages.ContinueOutsideLoop,
    messages.BreakOutsideLoop,
    messages.ContinueInFinally,
    messages.TwoStarredExpressions,
)


@hookimpl
def pylsp_lint(workspace, document):
    with workspace.report_progress("lint: pyflakes"):
        reporter = PyflakesDiagnosticReport(document.lines)
        pyflakes_api.check(document.source.encode('utf-8'), document.path, reporter=reporter)
        return reporter.diagnostics


class PyflakesDiagnosticReport:

    def __init__(self, lines):
        self.lines = lines
        self.diagnostics = []

    def unexpectedError(self, _filename, msg):  # pragma: no cover
        err_range = {
            'start': {'line': 0, 'character': 0},
            'end': {'line': 0, 'character': 0},
        }
        self.diagnostics.append({
            'source': 'pyflakes',
            'range': err_range,
            'message': msg,
            'severity': lsp.DiagnosticSeverity.Error,
        })

    def syntaxError(self, _filename, msg, lineno, offset, text):
        # We've seen that lineno and offset can sometimes be None
        lineno = lineno or 1
        offset = offset or 0

        err_range = {
            'start': {'line': lineno - 1, 'character': offset},
            'end': {'line': lineno - 1, 'character': offset + len(text)},
        }
        self.diagnostics.append({
            'source': 'pyflakes',
            'range': err_range,
            'message': msg,
            'severity': lsp.DiagnosticSeverity.Error,
        })

    def flake(self, message):
        """ Get message like <filename>:<lineno>: <msg> """
        err_range = {
            'start': {'line': message.lineno - 1, 'character': message.col},
            'end': {'line': message.lineno - 1, 'character': len(self.lines[message.lineno - 1])},
        }

        severity = lsp.DiagnosticSeverity.Warning
        for message_type in PYFLAKES_ERROR_MESSAGES:
            if isinstance(message, message_type):
                severity = lsp.DiagnosticSeverity.Error
                break

        self.diagnostics.append({
            'source': 'pyflakes',
            'range': err_range,
            'message': message.message % message.message_args,
            'severity': severity
        })
