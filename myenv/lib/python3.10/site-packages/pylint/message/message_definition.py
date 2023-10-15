# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import sys
import warnings
from typing import TYPE_CHECKING, Any

from astroid import nodes

from pylint.constants import _SCOPE_EXEMPT, MSG_TYPES, WarningScope
from pylint.exceptions import InvalidMessageError
from pylint.utils import normalize_text

if TYPE_CHECKING:
    from pylint.checkers import BaseChecker


class MessageDefinition:
    # pylint: disable-next=too-many-arguments
    def __init__(
        self,
        checker: BaseChecker,
        msgid: str,
        msg: str,
        description: str,
        symbol: str,
        scope: str,
        minversion: tuple[int, int] | None = None,
        maxversion: tuple[int, int] | None = None,
        old_names: list[tuple[str, str]] | None = None,
        shared: bool = False,
        default_enabled: bool = True,
    ) -> None:
        self.checker_name = checker.name
        self.check_msgid(msgid)
        self.msgid = msgid
        self.symbol = symbol
        self.msg = msg
        self.description = description
        self.scope = scope
        self.minversion = minversion
        self.maxversion = maxversion
        self.shared = shared
        self.default_enabled = default_enabled
        self.old_names: list[tuple[str, str]] = []
        if old_names:
            for old_msgid, old_symbol in old_names:
                self.check_msgid(old_msgid)
                self.old_names.append(
                    (old_msgid, old_symbol),
                )

    @staticmethod
    def check_msgid(msgid: str) -> None:
        if len(msgid) != 5:
            raise InvalidMessageError(f"Invalid message id {msgid!r}")
        if msgid[0] not in MSG_TYPES:
            raise InvalidMessageError(f"Bad message type {msgid[0]} in {msgid!r}")

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, MessageDefinition)
            and self.msgid == other.msgid
            and self.symbol == other.symbol
        )

    def __repr__(self) -> str:
        return f"MessageDefinition:{self.symbol} ({self.msgid})"

    def __str__(self) -> str:
        return f"{repr(self)}:\n{self.msg} {self.description}"

    def may_be_emitted(
        self,
        py_version: tuple[int, ...] | sys._version_info | None = None,
    ) -> bool:
        """Return True if message may be emitted using the configured py_version."""
        if py_version is None:
            py_version = sys.version_info
            warnings.warn(
                "'py_version' will be a required parameter of "
                "'MessageDefinition.may_be_emitted' in pylint 3.0. The most likely "
                "solution is to use 'linter.config.py_version' if you need to keep "
                "using this function, or to use 'MessageDefinition.is_message_enabled'"
                " instead.",
                DeprecationWarning,
            )
        if self.minversion is not None and self.minversion > py_version:
            return False
        if self.maxversion is not None and self.maxversion <= py_version:
            return False
        return True

    def format_help(self, checkerref: bool = False) -> str:
        """Return the help string for the given message id."""
        desc = self.description
        if checkerref:
            desc += f" This message belongs to the {self.checker_name} checker."
        title = self.msg
        if self.minversion or self.maxversion:
            restr = []
            if self.minversion:
                restr.append(f"< {'.'.join(str(n) for n in self.minversion)}")
            if self.maxversion:
                restr.append(f">= {'.'.join(str(n) for n in self.maxversion)}")
            restriction = " or ".join(restr)
            if checkerref:
                desc += f" It can't be emitted when using Python {restriction}."
            else:
                desc += (
                    f" This message can't be emitted when using Python {restriction}."
                )
        msg_help = normalize_text(" ".join(desc.split()), indent="  ")
        message_id = f"{self.symbol} ({self.msgid})"
        if title != "%s":
            title = title.splitlines()[0]
            return f":{message_id}: *{title.rstrip(' ')}*\n{msg_help}"
        return f":{message_id}:\n{msg_help}"

    def check_message_definition(
        self, line: int | None, node: nodes.NodeNG | None
    ) -> None:
        """Check MessageDefinition for possible errors."""
        if self.msgid[0] not in _SCOPE_EXEMPT:
            # Fatal messages and reports are special, the node/scope distinction
            # does not apply to them.
            if self.scope == WarningScope.LINE:
                if line is None:
                    raise InvalidMessageError(
                        f"Message {self.msgid} must provide line, got None"
                    )
                if node is not None:
                    raise InvalidMessageError(
                        f"Message {self.msgid} must only provide line, "
                        f"got line={line}, node={node}"
                    )
            elif self.scope == WarningScope.NODE:
                # Node-based warnings may provide an override line.
                if node is None:
                    raise InvalidMessageError(
                        f"Message {self.msgid} must provide Node, got None"
                    )
