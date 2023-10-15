# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

from dataclasses import asdict, dataclass
from warnings import warn

from pylint.constants import MSG_TYPES
from pylint.interfaces import UNDEFINED, Confidence
from pylint.typing import MessageLocationTuple


@dataclass(unsafe_hash=True)
class Message:  # pylint: disable=too-many-instance-attributes
    """This class represent a message to be issued by the reporters."""

    msg_id: str
    symbol: str
    msg: str
    C: str
    category: str
    confidence: Confidence
    abspath: str
    path: str
    module: str
    obj: str
    line: int
    column: int
    end_line: int | None
    end_column: int | None

    def __init__(
        self,
        msg_id: str,
        symbol: str,
        location: tuple[str, str, str, str, int, int] | MessageLocationTuple,
        msg: str,
        confidence: Confidence | None,
    ) -> None:
        if not isinstance(location, MessageLocationTuple):
            warn(
                "In pylint 3.0, Messages will only accept a MessageLocationTuple as location parameter",
                DeprecationWarning,
                stacklevel=2,
            )
            location = MessageLocationTuple(
                location[0],
                location[1],
                location[2],
                location[3],
                location[4],
                location[5],
                None,
                None,
            )

        self.msg_id = msg_id
        self.symbol = symbol
        self.msg = msg
        self.C = msg_id[0]
        self.category = MSG_TYPES[msg_id[0]]
        self.confidence = confidence or UNDEFINED
        self.abspath = location.abspath
        self.path = location.path
        self.module = location.module
        self.obj = location.obj
        self.line = location.line
        self.column = location.column
        self.end_line = location.end_line
        self.end_column = location.end_column

    def format(self, template: str) -> str:
        """Format the message according to the given template.

        The template format is the one of the format method :
        cf. https://docs.python.org/2/library/string.html#formatstrings
        """
        return template.format(**asdict(self))

    @property
    def location(self) -> MessageLocationTuple:
        return MessageLocationTuple(
            self.abspath,
            self.path,
            self.module,
            self.obj,
            self.line,
            self.column,
            self.end_line,
            self.end_column,
        )
