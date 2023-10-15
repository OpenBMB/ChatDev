# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import collections
from collections import defaultdict

from pylint import checkers, exceptions
from pylint.reporters.ureports.nodes import Section, Table
from pylint.utils import LinterStats


def report_total_messages_stats(
    sect: Section,
    stats: LinterStats,
    previous_stats: LinterStats | None,
) -> None:
    """Make total errors / warnings report."""
    lines = ["type", "number", "previous", "difference"]
    lines += checkers.table_lines_from_stats(stats, previous_stats, "message_types")
    sect.append(Table(children=lines, cols=4, rheaders=1))


def report_messages_stats(
    sect: Section,
    stats: LinterStats,
    _: LinterStats | None,
) -> None:
    """Make messages type report."""
    by_msg_stats = stats.by_msg
    in_order = sorted(
        (value, msg_id)
        for msg_id, value in by_msg_stats.items()
        if not msg_id.startswith("I")
    )
    in_order.reverse()
    lines = ["message id", "occurrences"]
    for value, msg_id in in_order:
        lines += [msg_id, str(value)]
    sect.append(Table(children=lines, cols=2, rheaders=1))


def report_messages_by_module_stats(
    sect: Section,
    stats: LinterStats,
    _: LinterStats | None,
) -> None:
    """Make errors / warnings by modules report."""
    module_stats = stats.by_module
    if len(module_stats) == 1:
        # don't print this report when we are analysing a single module
        raise exceptions.EmptyReportError()
    by_mod: defaultdict[str, dict[str, int | float]] = collections.defaultdict(dict)
    for m_type in ("fatal", "error", "warning", "refactor", "convention"):
        total = stats.get_global_message_count(m_type)
        for module in module_stats.keys():
            mod_total = stats.get_module_message_count(module, m_type)
            percent = 0 if total == 0 else float(mod_total * 100) / total
            by_mod[module][m_type] = percent
    sorted_result = []
    for module, mod_info in by_mod.items():
        sorted_result.append(
            (
                mod_info["error"],
                mod_info["warning"],
                mod_info["refactor"],
                mod_info["convention"],
                module,
            )
        )
    sorted_result.sort()
    sorted_result.reverse()
    lines = ["module", "error", "warning", "refactor", "convention"]
    for line in sorted_result:
        # Don't report clean modules.
        if all(entry == 0 for entry in line[:-1]):
            continue
        lines.append(line[-1])
        for val in line[:-1]:
            lines.append(f"{val:.2f}")
    if len(lines) == 5:
        raise exceptions.EmptyReportError()
    sect.append(Table(children=lines, cols=5, rheaders=1))
