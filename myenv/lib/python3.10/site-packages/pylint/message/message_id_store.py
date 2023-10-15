# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

from typing import NoReturn

from pylint.exceptions import (
    DeletedMessageError,
    InvalidMessageError,
    MessageBecameExtensionError,
    UnknownMessageError,
)
from pylint.message._deleted_message_ids import (
    is_deleted_msgid,
    is_deleted_symbol,
    is_moved_msgid,
    is_moved_symbol,
)


class MessageIdStore:

    """The MessageIdStore store MessageId and make sure that there is a 1-1 relation
    between msgid and symbol.
    """

    def __init__(self) -> None:
        self.__msgid_to_symbol: dict[str, str] = {}
        self.__symbol_to_msgid: dict[str, str] = {}
        self.__old_names: dict[str, list[str]] = {}
        self.__active_msgids: dict[str, list[str]] = {}

    def __len__(self) -> int:
        return len(self.__msgid_to_symbol)

    def __repr__(self) -> str:
        result = "MessageIdStore: [\n"
        for msgid, symbol in self.__msgid_to_symbol.items():
            result += f"  - {msgid} ({symbol})\n"
        result += "]"
        return result

    def get_symbol(self, msgid: str) -> str:
        try:
            return self.__msgid_to_symbol[msgid.upper()]
        except KeyError as e:
            msg = f"'{msgid}' is not stored in the message store."
            raise UnknownMessageError(msg) from e

    def get_msgid(self, symbol: str) -> str:
        try:
            return self.__symbol_to_msgid[symbol]
        except KeyError as e:
            msg = f"'{symbol}' is not stored in the message store."
            raise UnknownMessageError(msg) from e

    def register_message_definition(
        self, msgid: str, symbol: str, old_names: list[tuple[str, str]]
    ) -> None:
        self.check_msgid_and_symbol(msgid, symbol)
        self.add_msgid_and_symbol(msgid, symbol)
        for old_msgid, old_symbol in old_names:
            self.check_msgid_and_symbol(old_msgid, old_symbol)
            self.add_legacy_msgid_and_symbol(old_msgid, old_symbol, msgid)

    def add_msgid_and_symbol(self, msgid: str, symbol: str) -> None:
        """Add valid message id.

        There is a little duplication with add_legacy_msgid_and_symbol to avoid a function call,
        this is called a lot at initialization.
        """
        self.__msgid_to_symbol[msgid] = symbol
        self.__symbol_to_msgid[symbol] = msgid

    def add_legacy_msgid_and_symbol(
        self, msgid: str, symbol: str, new_msgid: str
    ) -> None:
        """Add valid legacy message id.

        There is a little duplication with add_msgid_and_symbol to avoid a function call,
        this is called a lot at initialization.
        """
        self.__msgid_to_symbol[msgid] = symbol
        self.__symbol_to_msgid[symbol] = msgid
        existing_old_names = self.__old_names.get(msgid, [])
        existing_old_names.append(new_msgid)
        self.__old_names[msgid] = existing_old_names

    def check_msgid_and_symbol(self, msgid: str, symbol: str) -> None:
        existing_msgid: str | None = self.__symbol_to_msgid.get(symbol)
        existing_symbol: str | None = self.__msgid_to_symbol.get(msgid)
        if existing_symbol is None and existing_msgid is None:
            return  # both symbol and msgid are usable
        if existing_msgid is not None:
            if existing_msgid != msgid:
                self._raise_duplicate_msgid(symbol, msgid, existing_msgid)
        if existing_symbol and existing_symbol != symbol:
            # See https://github.com/python/mypy/issues/10559
            self._raise_duplicate_symbol(msgid, symbol, existing_symbol)

    @staticmethod
    def _raise_duplicate_symbol(msgid: str, symbol: str, other_symbol: str) -> NoReturn:
        """Raise an error when a symbol is duplicated."""
        symbols = [symbol, other_symbol]
        symbols.sort()
        error_message = f"Message id '{msgid}' cannot have both "
        error_message += f"'{symbols[0]}' and '{symbols[1]}' as symbolic name."
        raise InvalidMessageError(error_message)

    @staticmethod
    def _raise_duplicate_msgid(symbol: str, msgid: str, other_msgid: str) -> NoReturn:
        """Raise an error when a msgid is duplicated."""
        msgids = [msgid, other_msgid]
        msgids.sort()
        error_message = (
            f"Message symbol '{symbol}' cannot be used for "
            f"'{msgids[0]}' and '{msgids[1]}' at the same time."
            f" If you're creating an 'old_names' use 'old-{symbol}' as the old symbol."
        )
        raise InvalidMessageError(error_message)

    def get_active_msgids(self, msgid_or_symbol: str) -> list[str]:
        """Return msgids but the input can be a symbol.

        self.__active_msgids is used to implement a primitive cache for this function.
        """
        try:
            return self.__active_msgids[msgid_or_symbol]
        except KeyError:
            pass

        # If we don't have a cached value yet we compute it
        msgid: str | None
        deletion_reason = None
        moved_reason = None
        if msgid_or_symbol[1:].isdigit():
            # Only msgid can have a digit as second letter
            msgid = msgid_or_symbol.upper()
            symbol = self.__msgid_to_symbol.get(msgid)
            if not symbol:
                deletion_reason = is_deleted_msgid(msgid)
                if deletion_reason is None:
                    moved_reason = is_moved_msgid(msgid)
        else:
            symbol = msgid_or_symbol
            msgid = self.__symbol_to_msgid.get(msgid_or_symbol)
            if not msgid:
                deletion_reason = is_deleted_symbol(symbol)
                if deletion_reason is None:
                    moved_reason = is_moved_symbol(symbol)
        if not msgid or not symbol:
            if deletion_reason is not None:
                raise DeletedMessageError(msgid_or_symbol, deletion_reason)
            if moved_reason is not None:
                raise MessageBecameExtensionError(msgid_or_symbol, moved_reason)
            error_msg = f"No such message id or symbol '{msgid_or_symbol}'."
            raise UnknownMessageError(error_msg)
        ids = self.__old_names.get(msgid, [msgid])
        # Add to cache
        self.__active_msgids[msgid_or_symbol] = ids
        return ids
