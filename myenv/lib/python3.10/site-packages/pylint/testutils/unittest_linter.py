# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

# pylint: disable=duplicate-code

from __future__ import annotations

import sys
from typing import Any

from astroid import nodes

from pylint.interfaces import UNDEFINED, Confidence
from pylint.lint import PyLinter
from pylint.testutils.output_line import MessageTest

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal


class UnittestLinter(PyLinter):
    """A fake linter class to capture checker messages."""

    def __init__(self) -> None:
        self._messages: list[MessageTest] = []
        super().__init__()

    def release_messages(self) -> list[MessageTest]:
        try:
            return self._messages
        finally:
            self._messages = []

    def add_message(
        self,
        msgid: str,
        line: int | None = None,
        # TODO: Make node non optional
        node: nodes.NodeNG | None = None,
        args: Any = None,
        confidence: Confidence | None = None,
        col_offset: int | None = None,
        end_lineno: int | None = None,
        end_col_offset: int | None = None,
    ) -> None:
        """Add a MessageTest to the _messages attribute of the linter class."""
        # If confidence is None we set it to UNDEFINED as well in PyLinter
        if confidence is None:
            confidence = UNDEFINED

        # Look up "location" data of node if not yet supplied
        if node:
            if node.position:
                if not line:
                    line = node.position.lineno
                if not col_offset:
                    col_offset = node.position.col_offset
                if not end_lineno:
                    end_lineno = node.position.end_lineno
                if not end_col_offset:
                    end_col_offset = node.position.end_col_offset
            else:
                if not line:
                    line = node.fromlineno
                if not col_offset:
                    col_offset = node.col_offset
                if not end_lineno:
                    end_lineno = node.end_lineno
                if not end_col_offset:
                    end_col_offset = node.end_col_offset

        self._messages.append(
            MessageTest(
                msgid,
                line,
                node,
                args,
                confidence,
                col_offset,
                end_lineno,
                end_col_offset,
            )
        )

    @staticmethod
    def is_message_enabled(*unused_args: Any, **unused_kwargs: Any) -> Literal[True]:
        return True
