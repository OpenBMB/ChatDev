# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""JSON reporter."""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING, Optional

from pylint.interfaces import UNDEFINED
from pylint.message import Message
from pylint.reporters.base_reporter import BaseReporter
from pylint.typing import MessageLocationTuple

if sys.version_info >= (3, 8):
    from typing import TypedDict
else:
    from typing_extensions import TypedDict

if TYPE_CHECKING:
    from pylint.lint.pylinter import PyLinter
    from pylint.reporters.ureports.nodes import Section

# Since message-id is an invalid name we need to use the alternative syntax
OldJsonExport = TypedDict(
    "OldJsonExport",
    {
        "type": str,
        "module": str,
        "obj": str,
        "line": int,
        "column": int,
        "endLine": Optional[int],
        "endColumn": Optional[int],
        "path": str,
        "symbol": str,
        "message": str,
        "message-id": str,
    },
)


class BaseJSONReporter(BaseReporter):
    """Report messages and layouts in JSON."""

    name = "json"
    extension = "json"

    def display_messages(self, layout: Section | None) -> None:
        """Launch layouts display."""
        json_dumpable = [self.serialize(message) for message in self.messages]
        print(json.dumps(json_dumpable, indent=4), file=self.out)

    def display_reports(self, layout: Section) -> None:
        """Don't do anything in this reporter."""

    def _display(self, layout: Section) -> None:
        """Do nothing."""

    @staticmethod
    def serialize(message: Message) -> OldJsonExport:
        raise NotImplementedError

    @staticmethod
    def deserialize(message_as_json: OldJsonExport) -> Message:
        raise NotImplementedError


class JSONReporter(BaseJSONReporter):

    """
    TODO: 3.0: Remove this JSONReporter in favor of the new one handling abs-path
    and confidence.

    TODO: 2.16: Add a new JSONReporter handling abs-path, confidence and scores.
    (Ultimately all other breaking change related to json for 3.0).
    """

    @staticmethod
    def serialize(message: Message) -> OldJsonExport:
        return {
            "type": message.category,
            "module": message.module,
            "obj": message.obj,
            "line": message.line,
            "column": message.column,
            "endLine": message.end_line,
            "endColumn": message.end_column,
            "path": message.path,
            "symbol": message.symbol,
            "message": message.msg or "",
            "message-id": message.msg_id,
        }

    @staticmethod
    def deserialize(message_as_json: OldJsonExport) -> Message:
        return Message(
            msg_id=message_as_json["message-id"],
            symbol=message_as_json["symbol"],
            msg=message_as_json["message"],
            location=MessageLocationTuple(
                # TODO: 3.0: Add abs-path and confidence in a new JSONReporter
                abspath=message_as_json["path"],
                path=message_as_json["path"],
                module=message_as_json["module"],
                obj=message_as_json["obj"],
                line=message_as_json["line"],
                column=message_as_json["column"],
                end_line=message_as_json["endLine"],
                end_column=message_as_json["endColumn"],
            ),
            # TODO: 3.0: Make confidence available in a new JSONReporter
            confidence=UNDEFINED,
        )


def register(linter: PyLinter) -> None:
    linter.register_reporter(JSONReporter)
