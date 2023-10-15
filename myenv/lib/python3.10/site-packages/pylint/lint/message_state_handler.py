# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import sys
import tokenize
from collections import defaultdict
from typing import TYPE_CHECKING

from pylint import exceptions, interfaces
from pylint.constants import (
    MSG_STATE_CONFIDENCE,
    MSG_STATE_SCOPE_CONFIG,
    MSG_STATE_SCOPE_MODULE,
    MSG_TYPES,
    MSG_TYPES_LONG,
)
from pylint.interfaces import HIGH
from pylint.message import MessageDefinition
from pylint.typing import ManagedMessage
from pylint.utils.pragma_parser import (
    OPTION_PO,
    InvalidPragmaError,
    UnRecognizedOptionError,
    parse_pragma,
)

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal


if TYPE_CHECKING:
    from pylint.lint.pylinter import PyLinter


class _MessageStateHandler:
    """Class that handles message disabling & enabling and processing of inline
    pragma's.
    """

    def __init__(self, linter: PyLinter) -> None:
        self.linter = linter
        self._msgs_state: dict[str, bool] = {}
        self._options_methods = {
            "enable": self.enable,
            "disable": self.disable,
            "disable-next": self.disable_next,
        }
        self._bw_options_methods = {
            "disable-msg": self._options_methods["disable"],
            "enable-msg": self._options_methods["enable"],
        }
        self._pragma_lineno: dict[str, int] = {}
        # TODO: 3.0: Update key type to str when current_name is always str
        self._stashed_messages: defaultdict[
            tuple[str | None, str], list[tuple[str | None, str]]
        ] = defaultdict(list)
        """Some messages in the options (for --enable and --disable) are encountered
        too early to warn about them.

        i.e. before all option providers have been fully parsed. Thus, this dict stores
        option_value and msg_id needed to (later) emit the messages keyed on module names.
        """

    def _set_one_msg_status(
        self, scope: str, msg: MessageDefinition, line: int | None, enable: bool
    ) -> None:
        """Set the status of an individual message."""
        if scope in {"module", "line"}:
            assert isinstance(line, int)  # should always be int inside module scope

            self.linter.file_state.set_msg_status(msg, line, enable, scope)
            if not enable and msg.symbol != "locally-disabled":
                self.linter.add_message(
                    "locally-disabled", line=line, args=(msg.symbol, msg.msgid)
                )
        else:
            msgs = self._msgs_state
            msgs[msg.msgid] = enable

    def _get_messages_to_set(
        self, msgid: str, enable: bool, ignore_unknown: bool = False
    ) -> list[MessageDefinition]:
        """Do some tests and find the actual messages of which the status should be set."""
        message_definitions: list[MessageDefinition] = []
        if msgid == "all":
            for _msgid in MSG_TYPES:
                message_definitions.extend(
                    self._get_messages_to_set(_msgid, enable, ignore_unknown)
                )
            return message_definitions

        # msgid is a category?
        category_id = msgid.upper()
        if category_id not in MSG_TYPES:
            category_id_formatted = MSG_TYPES_LONG.get(category_id)
        else:
            category_id_formatted = category_id
        if category_id_formatted is not None:
            for _msgid in self.linter.msgs_store._msgs_by_category[
                category_id_formatted
            ]:
                message_definitions.extend(
                    self._get_messages_to_set(_msgid, enable, ignore_unknown)
                )
            return message_definitions

        # msgid is a checker name?
        if msgid.lower() in self.linter._checkers:
            for checker in self.linter._checkers[msgid.lower()]:
                for _msgid in checker.msgs:
                    message_definitions.extend(
                        self._get_messages_to_set(_msgid, enable, ignore_unknown)
                    )
            return message_definitions

        # msgid is report id?
        if msgid.lower().startswith("rp"):
            if enable:
                self.linter.enable_report(msgid)
            else:
                self.linter.disable_report(msgid)
            return message_definitions

        try:
            # msgid is a symbolic or numeric msgid.
            message_definitions = self.linter.msgs_store.get_message_definitions(msgid)
        except exceptions.UnknownMessageError:
            if not ignore_unknown:
                raise
        return message_definitions

    def _set_msg_status(
        self,
        msgid: str,
        enable: bool,
        scope: str = "package",
        line: int | None = None,
        ignore_unknown: bool = False,
    ) -> None:
        """Do some tests and then iterate over message definitions to set state."""
        assert scope in {"package", "module", "line"}

        message_definitions = self._get_messages_to_set(msgid, enable, ignore_unknown)

        for message_definition in message_definitions:
            self._set_one_msg_status(scope, message_definition, line, enable)

        # sync configuration object
        self.linter.config.enable = []
        self.linter.config.disable = []
        for msgid_or_symbol, is_enabled in self._msgs_state.items():
            symbols = [
                m.symbol
                for m in self.linter.msgs_store.get_message_definitions(msgid_or_symbol)
            ]
            if is_enabled:
                self.linter.config.enable += symbols
            else:
                self.linter.config.disable += symbols

    def _register_by_id_managed_msg(
        self, msgid_or_symbol: str, line: int | None, is_disabled: bool = True
    ) -> None:
        """If the msgid is a numeric one, then register it to inform the user
        it could furnish instead a symbolic msgid.
        """
        if msgid_or_symbol[1:].isdigit():
            try:
                symbol = self.linter.msgs_store.message_id_store.get_symbol(
                    msgid=msgid_or_symbol
                )
            except exceptions.UnknownMessageError:
                return
            managed = ManagedMessage(
                self.linter.current_name, msgid_or_symbol, symbol, line, is_disabled
            )
            self.linter._by_id_managed_msgs.append(managed)

    def disable(
        self,
        msgid: str,
        scope: str = "package",
        line: int | None = None,
        ignore_unknown: bool = False,
    ) -> None:
        """Disable a message for a scope."""
        self._set_msg_status(
            msgid, enable=False, scope=scope, line=line, ignore_unknown=ignore_unknown
        )
        self._register_by_id_managed_msg(msgid, line)

    def disable_next(
        self,
        msgid: str,
        _: str = "package",
        line: int | None = None,
        ignore_unknown: bool = False,
    ) -> None:
        """Disable a message for the next line."""
        if not line:
            raise exceptions.NoLineSuppliedError
        self._set_msg_status(
            msgid,
            enable=False,
            scope="line",
            line=line + 1,
            ignore_unknown=ignore_unknown,
        )
        self._register_by_id_managed_msg(msgid, line + 1)

    def enable(
        self,
        msgid: str,
        scope: str = "package",
        line: int | None = None,
        ignore_unknown: bool = False,
    ) -> None:
        """Enable a message for a scope."""
        self._set_msg_status(
            msgid, enable=True, scope=scope, line=line, ignore_unknown=ignore_unknown
        )
        self._register_by_id_managed_msg(msgid, line, is_disabled=False)

    def disable_noerror_messages(self) -> None:
        """Disable message categories other than `error` and `fatal`."""
        for msgcat in self.linter.msgs_store._msgs_by_category:
            if msgcat in {"E", "F"}:
                continue
            self.disable(msgcat)

    def list_messages_enabled(self) -> None:
        emittable, non_emittable = self.linter.msgs_store.find_emittable_messages()
        enabled: list[str] = []
        disabled: list[str] = []
        for message in emittable:
            if self.is_message_enabled(message.msgid):
                enabled.append(f"  {message.symbol} ({message.msgid})")
            else:
                disabled.append(f"  {message.symbol} ({message.msgid})")
        print("Enabled messages:")
        for msg in enabled:
            print(msg)
        print("\nDisabled messages:")
        for msg in disabled:
            print(msg)
        print("\nNon-emittable messages with current interpreter:")
        for msg_def in non_emittable:
            print(f"  {msg_def.symbol} ({msg_def.msgid})")
        print("")

    def _get_message_state_scope(
        self,
        msgid: str,
        line: int | None = None,
        confidence: interfaces.Confidence | None = None,
    ) -> Literal[0, 1, 2] | None:
        """Returns the scope at which a message was enabled/disabled."""
        if confidence is None:
            confidence = interfaces.UNDEFINED
        if confidence.name not in self.linter.config.confidence:
            return MSG_STATE_CONFIDENCE  # type: ignore[return-value] # mypy does not infer Literal correctly
        try:
            if line in self.linter.file_state._module_msgs_state[msgid]:
                return MSG_STATE_SCOPE_MODULE  # type: ignore[return-value]
        except (KeyError, TypeError):
            return MSG_STATE_SCOPE_CONFIG  # type: ignore[return-value]
        return None

    def _is_one_message_enabled(self, msgid: str, line: int | None) -> bool:
        """Checks state of a single message for the current file.

        This function can't be cached as it depends on self.file_state which can
        change.
        """
        if line is None:
            return self._msgs_state.get(msgid, True)
        try:
            return self.linter.file_state._module_msgs_state[msgid][line]
        except KeyError:
            # Check if the message's line is after the maximum line existing in ast tree.
            # This line won't appear in the ast tree and won't be referred in
            # self.file_state._module_msgs_state
            # This happens for example with a commented line at the end of a module.
            max_line_number = self.linter.file_state.get_effective_max_line_number()
            if max_line_number and line > max_line_number:
                fallback = True
                lines = self.linter.file_state._raw_module_msgs_state.get(msgid, {})

                # Doesn't consider scopes, as a 'disable' can be in a
                # different scope than that of the current line.
                closest_lines = reversed(
                    [
                        (message_line, enable)
                        for message_line, enable in lines.items()
                        if message_line <= line
                    ]
                )
                _, fallback_iter = next(closest_lines, (None, None))
                if fallback_iter is not None:
                    fallback = fallback_iter

                return self._msgs_state.get(msgid, fallback)
            return self._msgs_state.get(msgid, True)

    def is_message_enabled(
        self,
        msg_descr: str,
        line: int | None = None,
        confidence: interfaces.Confidence | None = None,
    ) -> bool:
        """Return whether this message is enabled for the current file, line and
        confidence level.

        This function can't be cached right now as the line is the line of
        the currently analysed file (self.file_state), if it changes, then the
        result for the same msg_descr/line might need to change.

        :param msg_descr: Either the msgid or the symbol for a MessageDefinition
        :param line: The line of the currently analysed file
        :param confidence: The confidence of the message
        """
        if confidence and confidence.name not in self.linter.config.confidence:
            return False
        try:
            msgids = self.linter.msgs_store.message_id_store.get_active_msgids(
                msg_descr
            )
        except exceptions.UnknownMessageError:
            # The linter checks for messages that are not registered
            # due to version mismatch, just treat them as message IDs
            # for now.
            msgids = [msg_descr]
        return any(self._is_one_message_enabled(msgid, line) for msgid in msgids)

    def process_tokens(self, tokens: list[tokenize.TokenInfo]) -> None:
        """Process tokens from the current module to search for module/block level
        options.

        See func_block_disable_msg.py test case for expected behaviour.
        """
        control_pragmas = {"disable", "disable-next", "enable"}
        prev_line = None
        saw_newline = True
        seen_newline = True
        for tok_type, content, start, _, _ in tokens:
            if prev_line and prev_line != start[0]:
                saw_newline = seen_newline
                seen_newline = False

            prev_line = start[0]
            if tok_type in (tokenize.NL, tokenize.NEWLINE):
                seen_newline = True

            if tok_type != tokenize.COMMENT:
                continue
            match = OPTION_PO.search(content)
            if match is None:
                continue
            try:  # pylint: disable = too-many-try-statements
                for pragma_repr in parse_pragma(match.group(2)):
                    if pragma_repr.action in {"disable-all", "skip-file"}:
                        if pragma_repr.action == "disable-all":
                            self.linter.add_message(
                                "deprecated-pragma",
                                line=start[0],
                                args=("disable-all", "skip-file"),
                            )
                        self.linter.add_message("file-ignored", line=start[0])
                        self._ignore_file = True
                        return
                    try:
                        meth = self._options_methods[pragma_repr.action]
                    except KeyError:
                        meth = self._bw_options_methods[pragma_repr.action]
                        # found a "(dis|en)able-msg" pragma deprecated suppression
                        self.linter.add_message(
                            "deprecated-pragma",
                            line=start[0],
                            args=(
                                pragma_repr.action,
                                pragma_repr.action.replace("-msg", ""),
                            ),
                        )
                    for msgid in pragma_repr.messages:
                        # Add the line where a control pragma was encountered.
                        if pragma_repr.action in control_pragmas:
                            self._pragma_lineno[msgid] = start[0]

                        if (pragma_repr.action, msgid) == ("disable", "all"):
                            self.linter.add_message(
                                "deprecated-pragma",
                                line=start[0],
                                args=("disable=all", "skip-file"),
                            )
                            self.linter.add_message("file-ignored", line=start[0])
                            self._ignore_file = True
                            return
                            # If we did not see a newline between the previous line and now,
                            # we saw a backslash so treat the two lines as one.
                        l_start = start[0]
                        if not saw_newline:
                            l_start -= 1
                        try:
                            meth(msgid, "module", l_start)
                        except (
                            exceptions.DeletedMessageError,
                            exceptions.MessageBecameExtensionError,
                        ) as e:
                            self.linter.add_message(
                                "useless-option-value",
                                args=(pragma_repr.action, e),
                                line=start[0],
                                confidence=HIGH,
                            )
                        except exceptions.UnknownMessageError:
                            self.linter.add_message(
                                "unknown-option-value",
                                args=(pragma_repr.action, msgid),
                                line=start[0],
                                confidence=HIGH,
                            )

            except UnRecognizedOptionError as err:
                self.linter.add_message(
                    "unrecognized-inline-option", args=err.token, line=start[0]
                )
                continue
            except InvalidPragmaError as err:
                self.linter.add_message(
                    "bad-inline-option", args=err.token, line=start[0]
                )
                continue
