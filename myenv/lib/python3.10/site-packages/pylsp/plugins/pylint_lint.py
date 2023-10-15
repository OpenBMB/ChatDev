# Copyright 2018 Google LLC.
# Copyright 2017-2020 Palantir Technologies, Inc.
# Copyright 2021- Python Language Server Contributors.

"""Linter plugin for pylint."""
import collections
import logging
import sys
import re
from subprocess import Popen, PIPE
import os
import shlex

from pylsp import hookimpl, lsp

try:
    import ujson as json
except Exception:  # pylint: disable=broad-except
    import json

log = logging.getLogger(__name__)

# Pylint fails to suppress STDOUT when importing whitelisted C
# extensions, mangling their output into the expected JSON which breaks the
# parser. The most prominent example (and maybe the only one out there) is
# pygame - we work around that by asking pygame to NOT display the message upon
# import via an (otherwise harmless) environment variable. This is an ad-hoc
# fix for a very specific upstream issue.
# Related: https://github.com/PyCQA/pylint/issues/3518
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = 'hide'
DEPRECATION_CODES = {
    'W0402',  # Uses of a deprecated module %r
    'W1505',  # Using deprecated method %s()
    'W1511',  # Using deprecated argument %s of method %s()
    'W1512',  # Using deprecated class %s of module %s
    'W1513',  # Using deprecated decorator %s()
}
UNNECESSITY_CODES = {
    'W0611',  # Unused import %s
    'W0612',  # Unused variable %r
    'W0613',  # Unused argument %r
    'W0614',  # Unused import %s from wildcard import
    'W1304',  # Unused-format-string-argument
}


class PylintLinter:
    last_diags = collections.defaultdict(list)

    @classmethod
    def lint(cls, document, is_saved, flags=''):
        """Plugin interface to pylsp linter.

        Args:
            document: The document to be linted.
            is_saved: Whether or not the file has been saved to disk.
            flags: Additional flags to pass to pylint. Not exposed to
                pylsp_lint, but used for testing.

        Returns:
            A list of dicts with the following format:

                {
                    'source': 'pylint',
                    'range': {
                        'start': {
                            'line': start_line,
                            'character': start_column,
                        },
                        'end': {
                            'line': end_line,
                            'character': end_column,
                        },
                    }
                    'message': msg,
                    'severity': lsp.DiagnosticSeverity.*,
                }
        """
        if not is_saved:
            # Pylint can only be run on files that have been saved to disk.
            # Rather than return nothing, return the previous list of
            # diagnostics. If we return an empty list, any diagnostics we'd
            # previously shown will be cleared until the next save. Instead,
            # continue showing (possibly stale) diagnostics until the next
            # save.
            return cls.last_diags[document.path]

        cmd = [
            sys.executable,
            '-c',
            'import sys; from pylint.lint import Run; Run(sys.argv[1:])',
            '-f',
            'json',
            document.path
        ] + (shlex.split(str(flags)) if flags else [])
        log.debug("Calling pylint with '%s'", ' '.join(cmd))

        with Popen(cmd, stdout=PIPE, stderr=PIPE,
                   cwd=document._workspace.root_path, universal_newlines=True) as process:
            process.wait()
            json_out = process.stdout.read()
            err = process.stderr.read()

        if err != '':
            log.error("Error calling pylint: '%s'", err)

        # pylint prints nothing rather than [] when there are no diagnostics.
        # json.loads will not parse an empty string, so just return.
        if not json_out.strip():
            cls.last_diags[document.path] = []
            return []

        # Pylint's JSON output is a list of objects with the following format.
        #
        #     {
        #         "obj": "main",
        #         "path": "foo.py",
        #         "message": "Missing function docstring",
        #         "message-id": "C0111",
        #         "symbol": "missing-docstring",
        #         "column": 0,
        #         "type": "convention",
        #         "line": 5,
        #         "module": "foo"
        #     }
        #
        # The type can be any of:
        #
        #  * convention
        #  * information
        #  * error
        #  * fatal
        #  * refactor
        #  * warning
        diagnostics = []
        for diag in json.loads(json_out):
            # pylint lines index from 1, pylsp lines index from 0
            line = diag['line'] - 1

            err_range = {
                'start': {
                    'line': line,
                    # Index columns start from 0
                    'character': diag['column'],
                },
                'end': {
                    'line': line,
                    # It's possible that we're linting an empty file. Even an empty
                    # file might fail linting if it isn't named properly.
                    'character': len(document.lines[line]) if document.lines else 0,
                },
            }

            if diag['type'] == 'convention':
                severity = lsp.DiagnosticSeverity.Information
            elif diag['type'] == 'information':
                severity = lsp.DiagnosticSeverity.Information
            elif diag['type'] == 'error':
                severity = lsp.DiagnosticSeverity.Error
            elif diag['type'] == 'fatal':
                severity = lsp.DiagnosticSeverity.Error
            elif diag['type'] == 'refactor':
                severity = lsp.DiagnosticSeverity.Hint
            elif diag['type'] == 'warning':
                severity = lsp.DiagnosticSeverity.Warning

            code = diag['message-id']

            diagnostic = {
                'source': 'pylint',
                'range': err_range,
                'message': '[{}] {}'.format(diag['symbol'], diag['message']),
                'severity': severity,
                'code': code
            }

            if code in UNNECESSITY_CODES:
                diagnostic['tags'] = [lsp.DiagnosticTag.Unnecessary]
            if code in DEPRECATION_CODES:
                diagnostic['tags'] = [lsp.DiagnosticTag.Deprecated]

            diagnostics.append(diagnostic)
        cls.last_diags[document.path] = diagnostics
        return diagnostics


def _build_pylint_flags(settings):
    """Build arguments for calling pylint."""
    pylint_args = settings.get('args')
    if pylint_args is None:
        return ''
    return ' '.join(pylint_args)


@hookimpl
def pylsp_settings():
    # Default pylint to disabled because it requires a config
    # file to be useful.
    return {'plugins': {'pylint': {
        'enabled': False,
        'args': [],
        # disabled by default as it can slow down the workflow
        'executable': None,
    }}}


@hookimpl
def pylsp_lint(config, workspace, document, is_saved):
    """Run pylint linter."""
    with workspace.report_progress("lint: pylint"):
        settings = config.plugin_settings('pylint')
        log.debug("Got pylint settings: %s", settings)
        # pylint >= 2.5.0 is required for working through stdin and only
        # available with python3
        if settings.get('executable') and sys.version_info[0] >= 3:
            flags = build_args_stdio(settings)
            pylint_executable = settings.get('executable', 'pylint')
            return pylint_lint_stdin(pylint_executable, document, flags)
        flags = _build_pylint_flags(settings)
        return PylintLinter.lint(document, is_saved, flags=flags)


def build_args_stdio(settings):
    """Build arguments for calling pylint.

    :param settings: client settings
    :type settings: dict

    :return: arguments to path to pylint
    :rtype: list
    """
    pylint_args = settings.get('args')
    if pylint_args is None:
        return []
    return pylint_args


def pylint_lint_stdin(pylint_executable, document, flags):
    """Run pylint linter from stdin.

    This runs pylint in a subprocess with popen.
    This allows passing the file from stdin and as a result
    run pylint on unsaved files. Can slowdown the workflow.

    :param pylint_executable: path to pylint executable
    :type pylint_executable: string
    :param document: document to run pylint on
    :type document: pylsp.workspace.Document
    :param flags: arguments to path to pylint
    :type flags: list

    :return: linting diagnostics
    :rtype: list
    """
    pylint_result = _run_pylint_stdio(pylint_executable, document, flags)
    return _parse_pylint_stdio_result(document, pylint_result)


def _run_pylint_stdio(pylint_executable, document, flags):
    """Run pylint in popen.

    :param pylint_executable: path to pylint executable
    :type pylint_executable: string
    :param document: document to run pylint on
    :type document: pylsp.workspace.Document
    :param flags: arguments to path to pylint
    :type flags: list

    :return: result of calling pylint
    :rtype: string
    """
    log.debug("Calling %s with args: '%s'", pylint_executable, flags)
    try:
        cmd = [pylint_executable]
        cmd.extend(flags)
        cmd.extend(['--from-stdin', document.path])
        p = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    except IOError:
        log.debug("Can't execute %s. Trying with 'python -m pylint'", pylint_executable)
        cmd = ['python', '-m', 'pylint']
        cmd.extend(flags)
        cmd.extend(['--from-stdin', document.path])
        p = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)  # pylint: disable=consider-using-with
    (stdout, stderr) = p.communicate(document.source.encode())
    if stderr:
        log.error("Error while running pylint '%s'", stderr.decode())
    return stdout.decode()


def _parse_pylint_stdio_result(document, stdout):
    """Parse pylint results.

    :param document: document to run pylint on
    :type document: pylsp.workspace.Document
    :param stdout: pylint results to parse
    :type stdout: string

    :return: linting diagnostics
    :rtype: list
    """
    diagnostics = []
    lines = stdout.splitlines()
    for raw_line in lines:
        parsed_line = re.match(r'(.*):(\d*):(\d*): (\w*): (.*)', raw_line)
        if not parsed_line:
            log.debug("Pylint output parser can't parse line '%s'", raw_line)
            continue

        parsed_line = parsed_line.groups()
        if len(parsed_line) != 5:
            log.debug("Pylint output parser can't parse line '%s'", raw_line)
            continue

        _, line, character, code, msg = parsed_line
        line = int(line) - 1
        character = int(character)
        severity_map = {
            'C': lsp.DiagnosticSeverity.Information,
            'E': lsp.DiagnosticSeverity.Error,
            'F': lsp.DiagnosticSeverity.Error,
            'I': lsp.DiagnosticSeverity.Information,
            'R': lsp.DiagnosticSeverity.Hint,
            'W': lsp.DiagnosticSeverity.Warning,
        }
        severity = severity_map[code[0]]
        diagnostic = {
            'source': 'pylint',
            'code': code,
            'range': {
                'start': {
                    'line': line,
                    'character': character
                },
                'end': {
                    'line': line,
                    # no way to determine the column
                    'character': len(document.lines[line]) - 1
                }
            },
            'message': msg,
            'severity': severity,
        }
        if code in UNNECESSITY_CODES:
            diagnostic['tags'] = [lsp.DiagnosticTag.Unnecessary]
        if code in DEPRECATION_CODES:
            diagnostic['tags'] = [lsp.DiagnosticTag.Deprecated]
        diagnostics.append(diagnostic)

    return diagnostics
