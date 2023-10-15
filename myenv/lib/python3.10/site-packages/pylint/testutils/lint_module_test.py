# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import csv
import operator
import platform
import sys
from collections import Counter
from io import StringIO
from pathlib import Path
from typing import Counter as CounterType
from typing import TextIO, Tuple

import pytest
from _pytest.config import Config

from pylint import checkers
from pylint.config.config_initialization import _config_initialization
from pylint.constants import IS_PYPY
from pylint.lint import PyLinter
from pylint.message.message import Message
from pylint.testutils.constants import _EXPECTED_RE, _OPERATORS, UPDATE_OPTION

# need to import from functional.test_file to avoid cyclic import
from pylint.testutils.functional.test_file import (
    FunctionalTestFile,
    NoFileError,
    parse_python_version,
)
from pylint.testutils.output_line import OutputLine
from pylint.testutils.reporter_for_tests import FunctionalTestReporter

MessageCounter = CounterType[Tuple[int, str]]

PYLINTRC = Path(__file__).parent / "testing_pylintrc"


class LintModuleTest:
    maxDiff = None

    def __init__(
        self, test_file: FunctionalTestFile, config: Config | None = None
    ) -> None:
        _test_reporter = FunctionalTestReporter()
        self._linter = PyLinter()
        self._linter.config.persistent = 0
        checkers.initialize(self._linter)

        # See if test has its own .rc file, if so we use that one
        rc_file: Path | str = PYLINTRC
        try:
            rc_file = test_file.option_file
            self._linter.disable("suppressed-message")
            self._linter.disable("locally-disabled")
            self._linter.disable("useless-suppression")
        except NoFileError:
            pass

        self._test_file = test_file
        try:
            args = [test_file.source]
        except NoFileError:
            # If we're still raising NoFileError the actual source file doesn't exist
            args = [""]
        if config and config.getoption("minimal_messages_config"):
            with self._open_source_file() as f:
                messages_to_enable = {msg[1] for msg in self.get_expected_messages(f)}
                # Always enable fatal errors
                messages_to_enable.add("astroid-error")
                messages_to_enable.add("fatal")
                messages_to_enable.add("syntax-error")
            args.extend(["--disable=all", f"--enable={','.join(messages_to_enable)}"])

        # Add testoptions
        self._linter._arg_parser.add_argument(
            "--min_pyver", type=parse_python_version, default=(2, 5)
        )
        self._linter._arg_parser.add_argument(
            "--max_pyver", type=parse_python_version, default=(4, 0)
        )
        self._linter._arg_parser.add_argument(
            "--min_pyver_end_position", type=parse_python_version, default=(3, 8)
        )
        self._linter._arg_parser.add_argument(
            "--requires", type=lambda s: [i.strip() for i in s.split(",")], default=[]
        )
        self._linter._arg_parser.add_argument(
            "--except_implementations",
            type=lambda s: [i.strip() for i in s.split(",")],
            default=[],
        )
        self._linter._arg_parser.add_argument(
            "--exclude_platforms",
            type=lambda s: [i.strip() for i in s.split(",")],
            default=[],
        )
        self._linter._arg_parser.add_argument(
            "--exclude_from_minimal_messages_config", default=False
        )

        _config_initialization(
            self._linter, args_list=args, config_file=rc_file, reporter=_test_reporter
        )

        self._check_end_position = (
            sys.version_info >= self._linter.config.min_pyver_end_position
        )
        # TODO: PY3.9: PyPy supports end_lineno from 3.9 and above
        if self._check_end_position and IS_PYPY:
            self._check_end_position = sys.version_info >= (3, 9)  # pragma: no cover

        self._config = config

    def setUp(self) -> None:
        if self._should_be_skipped_due_to_version():
            pytest.skip(
                f"Test cannot run with Python {sys.version.split(' ', maxsplit=1)[0]}."
            )
        missing = []
        for requirement in self._linter.config.requires:
            try:
                __import__(requirement)
            except ImportError:
                missing.append(requirement)
        if missing:
            pytest.skip(f"Requires {','.join(missing)} to be present.")
        except_implementations = self._linter.config.except_implementations
        if except_implementations:
            if platform.python_implementation() in except_implementations:
                msg = "Test cannot run with Python implementation %r"
                pytest.skip(msg % platform.python_implementation())
        excluded_platforms = self._linter.config.exclude_platforms
        if excluded_platforms:
            if sys.platform.lower() in excluded_platforms:
                pytest.skip(f"Test cannot run on platform {sys.platform!r}")
        if (
            self._config
            and self._config.getoption("minimal_messages_config")
            and self._linter.config.exclude_from_minimal_messages_config
        ):
            pytest.skip("Test excluded from --minimal-messages-config")

    def runTest(self) -> None:
        self._runTest()

    def _should_be_skipped_due_to_version(self) -> bool:
        return (  # type: ignore[no-any-return]
            sys.version_info < self._linter.config.min_pyver
            or sys.version_info > self._linter.config.max_pyver
        )

    def __str__(self) -> str:
        return f"{self._test_file.base} ({self.__class__.__module__}.{self.__class__.__name__})"

    @staticmethod
    def get_expected_messages(stream: TextIO) -> MessageCounter:
        """Parses a file and get expected messages.

        :param stream: File-like input stream.
        :type stream: enumerable
        :returns: A dict mapping line,msg-symbol tuples to the count on this line.
        :rtype: dict
        """
        messages: MessageCounter = Counter()
        for i, line in enumerate(stream):
            match = _EXPECTED_RE.search(line)
            if match is None:
                continue
            line = match.group("line")
            if line is None:
                lineno = i + 1
            elif line.startswith("+") or line.startswith("-"):
                lineno = i + 1 + int(line)
            else:
                lineno = int(line)

            version = match.group("version")
            op = match.group("op")
            if version:
                required = parse_python_version(version)
                if not _OPERATORS[op](sys.version_info, required):
                    continue

            for msg_id in match.group("msgs").split(","):
                messages[lineno, msg_id.strip()] += 1
        return messages

    @staticmethod
    def multiset_difference(
        expected_entries: MessageCounter,
        actual_entries: MessageCounter,
    ) -> tuple[MessageCounter, dict[tuple[int, str], int]]:
        """Takes two multisets and compares them.

        A multiset is a dict with the cardinality of the key as the value.
        """
        missing = expected_entries.copy()
        missing.subtract(actual_entries)
        unexpected = {}
        for key, value in list(missing.items()):
            if value <= 0:
                missing.pop(key)
                if value < 0:
                    unexpected[key] = -value
        return missing, unexpected

    def _open_expected_file(self) -> TextIO:
        try:
            return open(self._test_file.expected_output, encoding="utf-8")
        except FileNotFoundError:
            return StringIO("")

    def _open_source_file(self) -> TextIO:
        if self._test_file.base == "invalid_encoded_data":
            return open(self._test_file.source, encoding="utf-8")
        if "latin1" in self._test_file.base:
            return open(self._test_file.source, encoding="latin1")
        return open(self._test_file.source, encoding="utf8")

    def _get_expected(self) -> tuple[MessageCounter, list[OutputLine]]:
        with self._open_source_file() as f:
            expected_msgs = self.get_expected_messages(f)
        if not expected_msgs:
            expected_msgs = Counter()
        with self._open_expected_file() as f:
            expected_output_lines = [
                OutputLine.from_csv(row, self._check_end_position)
                for row in csv.reader(f, "test")
            ]
        return expected_msgs, expected_output_lines

    def _get_actual(self) -> tuple[MessageCounter, list[OutputLine]]:
        messages: list[Message] = self._linter.reporter.messages
        messages.sort(key=lambda m: (m.line, m.symbol, m.msg))
        received_msgs: MessageCounter = Counter()
        received_output_lines = []
        for msg in messages:
            assert (
                msg.symbol != "fatal"
            ), f"Pylint analysis failed because of '{msg.msg}'"
            received_msgs[msg.line, msg.symbol] += 1
            received_output_lines.append(
                OutputLine.from_msg(msg, self._check_end_position)
            )
        return received_msgs, received_output_lines

    def _runTest(self) -> None:
        __tracebackhide__ = True  # pylint: disable=unused-variable
        modules_to_check = [self._test_file.source]
        self._linter.check(modules_to_check)
        expected_messages, expected_output = self._get_expected()
        actual_messages, actual_output = self._get_actual()
        assert (
            expected_messages == actual_messages
        ), self.error_msg_for_unequal_messages(
            actual_messages, expected_messages, actual_output
        )
        self._check_output_text(expected_messages, expected_output, actual_output)

    def error_msg_for_unequal_messages(
        self,
        actual_messages: MessageCounter,
        expected_messages: MessageCounter,
        actual_output: list[OutputLine],
    ) -> str:
        msg = [f'Wrong results for file "{self._test_file.base}":']
        missing, unexpected = self.multiset_difference(
            expected_messages, actual_messages
        )
        if missing:
            msg.append("\nExpected in testdata:")
            msg.extend(f" {msg[0]:3}: {msg[1]}" for msg in sorted(missing))
        if unexpected:
            msg.append("\nUnexpected in testdata:")
            msg.extend(f" {msg[0]:3}: {msg[1]}" for msg in sorted(unexpected))
        error_msg = "\n".join(msg)
        if self._config and self._config.getoption("verbose") > 0:
            error_msg += "\n\nActual pylint output for this file:\n"
            error_msg += "\n".join(str(o) for o in actual_output)
        return error_msg

    def error_msg_for_unequal_output(
        self,
        expected_lines: list[OutputLine],
        received_lines: list[OutputLine],
    ) -> str:
        missing = set(expected_lines) - set(received_lines)
        unexpected = set(received_lines) - set(expected_lines)
        error_msg = f"Wrong output for '{self._test_file.base}.txt':"
        sort_by_line_number = operator.attrgetter("lineno")
        if missing:
            error_msg += "\n- Missing lines:\n"
            for line in sorted(missing, key=sort_by_line_number):
                error_msg += f"{line}\n"
        if unexpected:
            error_msg += "\n- Unexpected lines:\n"
            for line in sorted(unexpected, key=sort_by_line_number):
                error_msg += f"{line}\n"
            error_msg += (
                "\nYou can update the expected output automatically with:\n'"
                f"python tests/test_functional.py {UPDATE_OPTION} -k "
                f'"test_functional[{self._test_file.base}]"\'\n\n'
                "Here's the update text in case you can't:\n"
            )
            expected_csv = StringIO()
            writer = csv.writer(expected_csv, dialect="test")
            for line in sorted(received_lines, key=sort_by_line_number):
                writer.writerow(line.to_csv())
            error_msg += expected_csv.getvalue()
        return error_msg

    def _check_output_text(
        self,
        _: MessageCounter,
        expected_output: list[OutputLine],
        actual_output: list[OutputLine],
    ) -> None:
        """This is a function because we want to be able to update the text in
        LintModuleOutputUpdate.
        """
        assert expected_output == actual_output, self.error_msg_for_unequal_output(
            expected_output, actual_output
        )
