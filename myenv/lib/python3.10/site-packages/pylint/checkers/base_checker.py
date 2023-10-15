# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import abc
import functools
import warnings
from collections.abc import Iterable, Sequence
from inspect import cleandoc
from tokenize import TokenInfo
from typing import TYPE_CHECKING, Any

from astroid import nodes

from pylint.config.arguments_provider import _ArgumentsProvider
from pylint.constants import _MSG_ORDER, MAIN_CHECKER_NAME, WarningScope
from pylint.exceptions import InvalidMessageError
from pylint.interfaces import Confidence, IRawChecker, ITokenChecker, implements
from pylint.message.message_definition import MessageDefinition
from pylint.typing import (
    ExtraMessageOptions,
    MessageDefinitionTuple,
    OptionDict,
    Options,
    ReportsCallable,
)
from pylint.utils import get_rst_section, get_rst_title

if TYPE_CHECKING:
    from pylint.lint import PyLinter


@functools.total_ordering
class BaseChecker(_ArgumentsProvider):
    # checker name (you may reuse an existing one)
    name: str = ""
    # ordered list of options to control the checker behaviour
    options: Options = ()
    # messages issued by this checker
    msgs: dict[str, MessageDefinitionTuple] = {}
    # reports issued by this checker
    reports: tuple[tuple[str, str, ReportsCallable], ...] = ()
    # mark this checker as enabled or not.
    enabled: bool = True

    def __init__(self, linter: PyLinter) -> None:
        """Checker instances should have the linter as argument."""
        if getattr(self, "__implements__", None):
            warnings.warn(
                "Using the __implements__ inheritance pattern for BaseChecker is no "
                "longer supported. Child classes should only inherit BaseChecker or any "
                "of the other checker types from pylint.checkers.",
                DeprecationWarning,
                stacklevel=2,
            )
        if self.name is not None:
            self.name = self.name.lower()
        self.linter = linter

        _ArgumentsProvider.__init__(self, linter)

    def __gt__(self, other: Any) -> bool:
        """Sorting of checkers."""
        if not isinstance(other, BaseChecker):
            return False
        if self.name == MAIN_CHECKER_NAME:
            return False
        if other.name == MAIN_CHECKER_NAME:
            return True
        if type(self).__module__.startswith("pylint.checkers") and not type(
            other
        ).__module__.startswith("pylint.checkers"):
            return False
        return self.name > other.name

    def __eq__(self, other: Any) -> bool:
        """Permit to assert Checkers are equal."""
        if not isinstance(other, BaseChecker):
            return False
        return f"{self.name}{self.msgs}" == f"{other.name}{other.msgs}"

    def __hash__(self) -> int:
        """Make Checker hashable."""
        return hash(f"{self.name}{self.msgs}")

    def __repr__(self) -> str:
        status = "Checker" if self.enabled else "Disabled checker"
        msgs = "', '".join(self.msgs.keys())
        return f"{status} '{self.name}' (responsible for '{msgs}')"

    def __str__(self) -> str:
        """This might be incomplete because multiple classes inheriting BaseChecker
        can have the same name.

        See: MessageHandlerMixIn.get_full_documentation()
        """
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            return self.get_full_documentation(
                msgs=self.msgs, options=self.options_and_values(), reports=self.reports
            )

    def get_full_documentation(
        self,
        msgs: dict[str, MessageDefinitionTuple],
        options: Iterable[tuple[str, OptionDict, Any]],
        reports: Sequence[tuple[str, str, ReportsCallable]],
        doc: str | None = None,
        module: str | None = None,
        show_options: bool = True,
    ) -> str:
        result = ""
        checker_title = f"{self.name.replace('_', ' ').title()} checker"
        if module:
            # Provide anchor to link against
            result += f".. _{module}:\n\n"
        result += f"{get_rst_title(checker_title, '~')}\n"
        if module:
            result += f"This checker is provided by ``{module}``.\n"
        result += f"Verbatim name of the checker is ``{self.name}``.\n\n"
        if doc:
            # Provide anchor to link against
            result += get_rst_title(f"{checker_title} Documentation", "^")
            result += f"{cleandoc(doc)}\n\n"
        # options might be an empty generator and not be False when cast to boolean
        options_list = list(options)
        if options_list:
            if show_options:
                result += get_rst_title(f"{checker_title} Options", "^")
                result += f"{get_rst_section(None, options_list)}\n"
            else:
                result += f"See also :ref:`{self.name} checker's options' documentation <{self.name}-options>`\n\n"
        if msgs:
            result += get_rst_title(f"{checker_title} Messages", "^")
            for msgid, msg in sorted(
                msgs.items(), key=lambda kv: (_MSG_ORDER.index(kv[0][0]), kv[1])
            ):
                msg_def = self.create_message_definition_from_tuple(msgid, msg)
                result += f"{msg_def.format_help(checkerref=False)}\n"
            result += "\n"
        if reports:
            result += get_rst_title(f"{checker_title} Reports", "^")
            for report in reports:
                result += (
                    ":%s: %s\n" % report[:2]  # pylint: disable=consider-using-f-string
                )
            result += "\n"
        result += "\n"
        return result

    def add_message(
        self,
        msgid: str,
        line: int | None = None,
        node: nodes.NodeNG | None = None,
        args: Any = None,
        confidence: Confidence | None = None,
        col_offset: int | None = None,
        end_lineno: int | None = None,
        end_col_offset: int | None = None,
    ) -> None:
        self.linter.add_message(
            msgid, line, node, args, confidence, col_offset, end_lineno, end_col_offset
        )

    def check_consistency(self) -> None:
        """Check the consistency of msgid.

        msg ids for a checker should be a string of len 4, where the two first
        characters are the checker id and the two last the msg id in this
        checker.

        :raises InvalidMessageError: If the checker id in the messages are not
        always the same.
        """
        checker_id = None
        existing_ids = []
        for message in self.messages:
            # Id's for shared messages such as the 'deprecated-*' messages
            # can be inconsistent with their checker id.
            if message.shared:
                continue
            if checker_id is not None and checker_id != message.msgid[1:3]:
                error_msg = "Inconsistent checker part in message id "
                error_msg += f"'{message.msgid}' (expected 'x{checker_id}xx' "
                error_msg += f"because we already had {existing_ids})."
                raise InvalidMessageError(error_msg)
            checker_id = message.msgid[1:3]
            existing_ids.append(message.msgid)

    def create_message_definition_from_tuple(
        self, msgid: str, msg_tuple: MessageDefinitionTuple
    ) -> MessageDefinition:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            if isinstance(self, (BaseTokenChecker, BaseRawFileChecker)):
                default_scope = WarningScope.LINE
            # TODO: 3.0: Remove deprecated if-statement
            elif implements(self, (IRawChecker, ITokenChecker)):
                warnings.warn(  # pragma: no cover
                    "Checkers should subclass BaseTokenChecker or BaseRawFileChecker "
                    "instead of using the __implements__ mechanism. Use of __implements__ "
                    "will no longer be supported in pylint 3.0",
                    DeprecationWarning,
                )
                default_scope = WarningScope.LINE  # pragma: no cover
            else:
                default_scope = WarningScope.NODE
        options: ExtraMessageOptions = {}
        if len(msg_tuple) == 4:
            (msg, symbol, descr, options) = msg_tuple  # type: ignore[misc]
        elif len(msg_tuple) == 3:
            (msg, symbol, descr) = msg_tuple  # type: ignore[misc]
        else:
            error_msg = """Messages should have a msgid, a symbol and a description. Something like this :

"W1234": (
    "message",
    "message-symbol",
    "Message description with detail.",
    ...
),
"""
            raise InvalidMessageError(error_msg)
        options.setdefault("scope", default_scope)
        return MessageDefinition(self, msgid, msg, descr, symbol, **options)

    @property
    def messages(self) -> list[MessageDefinition]:
        return [
            self.create_message_definition_from_tuple(msgid, msg_tuple)
            for msgid, msg_tuple in sorted(self.msgs.items())
        ]

    def get_message_definition(self, msgid: str) -> MessageDefinition:
        # TODO: 3.0: Remove deprecated method
        warnings.warn(
            "'get_message_definition' is deprecated and will be removed in 3.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        for message_definition in self.messages:
            if message_definition.msgid == msgid:
                return message_definition
        error_msg = f"MessageDefinition for '{msgid}' does not exists. "
        error_msg += f"Choose from {[m.msgid for m in self.messages]}."
        raise InvalidMessageError(error_msg)

    def open(self) -> None:
        """Called before visiting project (i.e. set of modules)."""

    def close(self) -> None:
        """Called after visiting project (i.e set of modules)."""

    def get_map_data(self) -> Any:
        return None

    # pylint: disable-next=unused-argument
    def reduce_map_data(self, linter: PyLinter, data: list[Any]) -> None:
        return None


class BaseTokenChecker(BaseChecker):
    """Base class for checkers that want to have access to the token stream."""

    @abc.abstractmethod
    def process_tokens(self, tokens: list[TokenInfo]) -> None:
        """Should be overridden by subclasses."""
        raise NotImplementedError()


class BaseRawFileChecker(BaseChecker):
    """Base class for checkers which need to parse the raw file."""

    @abc.abstractmethod
    def process_module(self, node: nodes.Module) -> None:
        """Process a module.

        The module's content is accessible via ``astroid.stream``
        """
        raise NotImplementedError()
