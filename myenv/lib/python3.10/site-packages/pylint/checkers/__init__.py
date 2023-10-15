# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Utilities methods and classes for checkers.

Base id of standard checkers (used in msg and report ids):
01: base
02: classes
03: format
04: import
05: misc
06: variables
07: exceptions
08: similar
09: design_analysis
10: newstyle
11: typecheck
12: logging
13: string_format
14: string_constant
15: stdlib
16: python3 (This one was deleted but needs to be reserved for consistency with old messages)
17: refactoring
.
.
.
24: non-ascii-names
25: unicode
26: unsupported_version
27: private-import
28-50: not yet used: reserved for future internal checkers.
This file is not updated. Use
   script/get_unused_message_id_category.py
to get the next free checker id.

51-99: perhaps used: reserved for external checkers

The raw_metrics checker has no number associated since it doesn't emit any
messages nor reports. XXX not true, emit a 07 report !
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from pylint.checkers.base_checker import (
    BaseChecker,
    BaseRawFileChecker,
    BaseTokenChecker,
)
from pylint.checkers.deprecated import DeprecatedMixin
from pylint.checkers.mapreduce_checker import MapReduceMixin
from pylint.utils import LinterStats, diff_string, register_plugins

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal

if TYPE_CHECKING:
    from pylint.lint import PyLinter


def table_lines_from_stats(
    stats: LinterStats,
    old_stats: LinterStats | None,
    stat_type: Literal["duplicated_lines", "message_types"],
) -> list[str]:
    """Get values listed in <columns> from <stats> and <old_stats>,
    and return a formatted list of values.

    The return value is designed to be given to a ureport.Table object
    """
    lines: list[str] = []
    if stat_type == "duplicated_lines":
        new: list[tuple[str, int | float]] = [
            ("nb_duplicated_lines", stats.duplicated_lines["nb_duplicated_lines"]),
            (
                "percent_duplicated_lines",
                stats.duplicated_lines["percent_duplicated_lines"],
            ),
        ]
        if old_stats:
            old: list[tuple[str, str | int | float]] = [
                (
                    "nb_duplicated_lines",
                    old_stats.duplicated_lines["nb_duplicated_lines"],
                ),
                (
                    "percent_duplicated_lines",
                    old_stats.duplicated_lines["percent_duplicated_lines"],
                ),
            ]
        else:
            old = [("nb_duplicated_lines", "NC"), ("percent_duplicated_lines", "NC")]
    elif stat_type == "message_types":
        new = [
            ("convention", stats.convention),
            ("refactor", stats.refactor),
            ("warning", stats.warning),
            ("error", stats.error),
        ]
        if old_stats:
            old = [
                ("convention", old_stats.convention),
                ("refactor", old_stats.refactor),
                ("warning", old_stats.warning),
                ("error", old_stats.error),
            ]
        else:
            old = [
                ("convention", "NC"),
                ("refactor", "NC"),
                ("warning", "NC"),
                ("error", "NC"),
            ]

    for index, value in enumerate(new):
        new_value = value[1]
        old_value = old[index][1]
        diff_str = (
            diff_string(old_value, new_value)
            if isinstance(old_value, float)
            else old_value
        )
        new_str = f"{new_value:.3f}" if isinstance(new_value, float) else str(new_value)
        old_str = f"{old_value:.3f}" if isinstance(old_value, float) else str(old_value)
        lines.extend((value[0].replace("_", " "), new_str, old_str, diff_str))  # type: ignore[arg-type]
    return lines


def initialize(linter: PyLinter) -> None:
    """Initialize linter with checkers in this package."""
    register_plugins(linter, __path__[0])


__all__ = [
    "BaseChecker",
    "BaseTokenChecker",
    "BaseRawFileChecker",
    "initialize",
    "MapReduceMixin",
    "DeprecatedMixin",
    "register_plugins",
]
