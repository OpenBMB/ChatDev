# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

from functools import lru_cache
from typing import NamedTuple


class DeletedMessage(NamedTuple):
    msgid: str
    symbol: str
    old_names: list[tuple[str, str]] = []


DELETED_MSGID_PREFIXES: list[int] = []

DELETED_MESSAGES_IDS = {
    # Everything until the next comment is from the PY3K+ checker
    "https://github.com/PyCQA/pylint/pull/4942": [
        DeletedMessage("W1601", "apply-builtin"),
        DeletedMessage("E1601", "print-statement"),
        DeletedMessage("E1602", "parameter-unpacking"),
        DeletedMessage(
            "E1603", "unpacking-in-except", [("W0712", "old-unpacking-in-except")]
        ),
        DeletedMessage(
            "E1604", "old-raise-syntax", [("W0121", "old-old-raise-syntax")]
        ),
        DeletedMessage("E1605", "backtick", [("W0333", "old-backtick")]),
        DeletedMessage("E1609", "import-star-module-level"),
        DeletedMessage("W1601", "apply-builtin"),
        DeletedMessage("W1602", "basestring-builtin"),
        DeletedMessage("W1603", "buffer-builtin"),
        DeletedMessage("W1604", "cmp-builtin"),
        DeletedMessage("W1605", "coerce-builtin"),
        DeletedMessage("W1606", "execfile-builtin"),
        DeletedMessage("W1607", "file-builtin"),
        DeletedMessage("W1608", "long-builtin"),
        DeletedMessage("W1609", "raw_input-builtin"),
        DeletedMessage("W1610", "reduce-builtin"),
        DeletedMessage("W1611", "standarderror-builtin"),
        DeletedMessage("W1612", "unicode-builtin"),
        DeletedMessage("W1613", "xrange-builtin"),
        DeletedMessage("W1614", "coerce-method"),
        DeletedMessage("W1615", "delslice-method"),
        DeletedMessage("W1616", "getslice-method"),
        DeletedMessage("W1617", "setslice-method"),
        DeletedMessage("W1618", "no-absolute-import"),
        DeletedMessage("W1619", "old-division"),
        DeletedMessage("W1620", "dict-iter-method"),
        DeletedMessage("W1621", "dict-view-method"),
        DeletedMessage("W1622", "next-method-called"),
        DeletedMessage("W1623", "metaclass-assignment"),
        DeletedMessage(
            "W1624", "indexing-exception", [("W0713", "old-indexing-exception")]
        ),
        DeletedMessage("W1625", "raising-string", [("W0701", "old-raising-string")]),
        DeletedMessage("W1626", "reload-builtin"),
        DeletedMessage("W1627", "oct-method"),
        DeletedMessage("W1628", "hex-method"),
        DeletedMessage("W1629", "nonzero-method"),
        DeletedMessage("W1630", "cmp-method"),
        DeletedMessage("W1632", "input-builtin"),
        DeletedMessage("W1633", "round-builtin"),
        DeletedMessage("W1634", "intern-builtin"),
        DeletedMessage("W1635", "unichr-builtin"),
        DeletedMessage(
            "W1636", "map-builtin-not-iterating", [("W1631", "implicit-map-evaluation")]
        ),
        DeletedMessage("W1637", "zip-builtin-not-iterating"),
        DeletedMessage("W1638", "range-builtin-not-iterating"),
        DeletedMessage("W1639", "filter-builtin-not-iterating"),
        DeletedMessage("W1640", "using-cmp-argument"),
        DeletedMessage("W1642", "div-method"),
        DeletedMessage("W1643", "idiv-method"),
        DeletedMessage("W1644", "rdiv-method"),
        DeletedMessage("W1645", "exception-message-attribute"),
        DeletedMessage("W1646", "invalid-str-codec"),
        DeletedMessage("W1647", "sys-max-int"),
        DeletedMessage("W1648", "bad-python3-import"),
        DeletedMessage("W1649", "deprecated-string-function"),
        DeletedMessage("W1650", "deprecated-str-translate-call"),
        DeletedMessage("W1651", "deprecated-itertools-function"),
        DeletedMessage("W1652", "deprecated-types-field"),
        DeletedMessage("W1653", "next-method-defined"),
        DeletedMessage("W1654", "dict-items-not-iterating"),
        DeletedMessage("W1655", "dict-keys-not-iterating"),
        DeletedMessage("W1656", "dict-values-not-iterating"),
        DeletedMessage("W1657", "deprecated-operator-function"),
        DeletedMessage("W1658", "deprecated-urllib-function"),
        DeletedMessage("W1659", "xreadlines-attribute"),
        DeletedMessage("W1660", "deprecated-sys-function"),
        DeletedMessage("W1661", "exception-escape"),
        DeletedMessage("W1662", "comprehension-escape"),
    ],
    "https://github.com/PyCQA/pylint/pull/3578": [
        DeletedMessage("W0312", "mixed-indentation"),
    ],
    "https://github.com/PyCQA/pylint/pull/3577": [
        DeletedMessage(
            "C0326",
            "bad-whitespace",
            [
                ("C0323", "no-space-after-operator"),
                ("C0324", "no-space-after-comma"),
                ("C0322", "no-space-before-operator"),
            ],
        ),
    ],
    "https://github.com/PyCQA/pylint/pull/3571": [
        DeletedMessage("C0330", "bad-continuation")
    ],
    "https://pylint.readthedocs.io/en/latest/whatsnew/1/1.4.html#what-s-new-in-pylint-1-4-3": [
        DeletedMessage("R0921", "abstract-class-not-used"),
        DeletedMessage("R0922", "abstract-class-little-used"),
        DeletedMessage("W0142", "star-args"),
    ],
    "https://github.com/PyCQA/pylint/issues/2409": [
        DeletedMessage("W0232", "no-init"),
    ],
    "https://github.com/PyCQA/pylint/pull/6421": [
        DeletedMessage("W0111", "assign-to-new-keyword"),
    ],
}
MOVED_TO_EXTENSIONS = {
    "https://pylint.readthedocs.io/en/latest/whatsnew/2/2.14/summary.html#removed-checkers": [
        DeletedMessage("R0201", "no-self-use")
    ],
}


@lru_cache(maxsize=None)
def is_deleted_symbol(symbol: str) -> str | None:
    """Return the explanation for removal if the message was removed."""
    for explanation, deleted_messages in DELETED_MESSAGES_IDS.items():
        for deleted_message in deleted_messages:
            if symbol == deleted_message.symbol or any(
                symbol == m[1] for m in deleted_message.old_names
            ):
                return explanation
    return None


@lru_cache(maxsize=None)
def is_deleted_msgid(msgid: str) -> str | None:
    """Return the explanation for removal if the message was removed."""
    for explanation, deleted_messages in DELETED_MESSAGES_IDS.items():
        for deleted_message in deleted_messages:
            if msgid == deleted_message.msgid or any(
                msgid == m[0] for m in deleted_message.old_names
            ):
                return explanation
    return None


@lru_cache(maxsize=None)
def is_moved_symbol(symbol: str) -> str | None:
    """Return the explanation for moving if the message was moved to extensions."""
    for explanation, moved_messages in MOVED_TO_EXTENSIONS.items():
        for moved_message in moved_messages:
            if symbol == moved_message.symbol or any(
                symbol == m[1] for m in moved_message.old_names
            ):
                return explanation
    return None


@lru_cache(maxsize=None)
def is_moved_msgid(msgid: str) -> str | None:
    """Return the explanation for moving if the message was moved to extensions."""
    for explanation, moved_messages in MOVED_TO_EXTENSIONS.items():
        for moved_message in moved_messages:
            if msgid == moved_message.msgid or any(
                msgid == m[0] for m in moved_message.old_names
            ):
                return explanation
    return None
