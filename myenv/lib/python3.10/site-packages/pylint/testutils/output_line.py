# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import warnings
from collections.abc import Sequence
from typing import Any, NamedTuple, TypeVar

from astroid import nodes

from pylint.constants import PY38_PLUS
from pylint.interfaces import UNDEFINED, Confidence
from pylint.message.message import Message
from pylint.testutils.constants import UPDATE_OPTION

_T = TypeVar("_T")


class MessageTest(NamedTuple):
    msg_id: str
    line: int | None = None
    node: nodes.NodeNG | None = None
    args: Any | None = None
    confidence: Confidence | None = UNDEFINED
    col_offset: int | None = None
    end_line: int | None = None
    end_col_offset: int | None = None
    """Used to test messages produced by pylint.

    Class name cannot start with Test as pytest doesn't allow constructors in test classes.
    """


class OutputLine(NamedTuple):
    symbol: str
    lineno: int
    column: int
    end_lineno: int | None
    end_column: int | None
    object: str
    msg: str
    confidence: str

    @classmethod
    def from_msg(cls, msg: Message, check_endline: bool = True) -> OutputLine:
        """Create an OutputLine from a Pylint Message."""
        column = cls._get_column(msg.column)
        end_line = cls._get_py38_none_value(msg.end_line, check_endline)
        end_column = cls._get_py38_none_value(msg.end_column, check_endline)
        return cls(
            msg.symbol,
            msg.line,
            column,
            end_line,
            end_column,
            msg.obj or "",
            msg.msg.replace("\r\n", "\n"),
            msg.confidence.name,
        )

    @staticmethod
    def _get_column(column: str | int) -> int:
        """Handle column numbers except for python < 3.8.

        The ast parser in those versions doesn't return them.
        """
        if not PY38_PLUS:
            # We check the column only for the new better ast parser introduced in python 3.8
            return 0  # pragma: no cover
        return int(column)

    @staticmethod
    def _get_py38_none_value(value: _T, check_endline: bool) -> _T | None:
        """Used to make end_line and end_column None as indicated by our version
        compared to `min_pyver_end_position`.
        """
        if not check_endline:
            return None  # pragma: no cover
        return value

    @classmethod
    def from_csv(
        cls, row: Sequence[str] | str, check_endline: bool = True
    ) -> OutputLine:
        """Create an OutputLine from a comma separated list (the functional tests
        expected output .txt files).
        """
        if isinstance(row, str):
            row = row.split(",")
        # noinspection PyBroadException
        # pylint: disable = too-many-try-statements
        try:
            column = cls._get_column(row[2])
            if len(row) == 5:
                warnings.warn(
                    "In pylint 3.0 functional tests expected output should always include the "
                    "expected confidence level, expected end_line and expected end_column. "
                    "An OutputLine should thus have a length of 8.",
                    DeprecationWarning,
                    stacklevel=2,
                )
                return cls(
                    row[0],
                    int(row[1]),
                    column,
                    None,
                    None,
                    row[3],
                    row[4],
                    UNDEFINED.name,
                )
            if len(row) == 6:
                warnings.warn(
                    "In pylint 3.0 functional tests expected output should always include the "
                    "expected end_line and expected end_column. An OutputLine should thus have "
                    "a length of 8.",
                    DeprecationWarning,
                    stacklevel=2,
                )
                return cls(
                    row[0], int(row[1]), column, None, None, row[3], row[4], row[5]
                )
            if len(row) == 8:
                end_line = cls._get_py38_none_value(row[3], check_endline)
                end_column = cls._get_py38_none_value(row[4], check_endline)
                return cls(
                    row[0],
                    int(row[1]),
                    column,
                    cls._value_to_optional_int(end_line),
                    cls._value_to_optional_int(end_column),
                    row[5],
                    row[6],
                    row[7],
                )
            raise IndexError
        except Exception:  # pylint: disable=broad-except
            warnings.warn(
                "Expected 'msg-symbolic-name:42:27:MyClass.my_function:The message:"
                f"CONFIDENCE' but we got '{':'.join(row)}'. Try updating the expected"
                f" output with:\npython tests/test_functional.py {UPDATE_OPTION}",
                UserWarning,
            )
            return cls("", 0, 0, None, None, "", "", "")

    def to_csv(self) -> tuple[str, str, str, str, str, str, str, str]:
        """Convert an OutputLine to a tuple of string to be written by a
        csv-writer.
        """
        return (
            str(self.symbol),
            str(self.lineno),
            str(self.column),
            str(self.end_lineno),
            str(self.end_column),
            str(self.object),
            str(self.msg),
            str(self.confidence),
        )

    @staticmethod
    def _value_to_optional_int(value: str | None) -> int | None:
        """Checks if a (stringified) value should be None or a Python integer."""
        if value == "None" or not value:
            return None
        return int(value)
