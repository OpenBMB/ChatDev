# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Looks for comparisons to zero."""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING

import astroid
from astroid import nodes

from pylint import checkers
from pylint.checkers import utils
from pylint.interfaces import HIGH

if TYPE_CHECKING:
    from pylint.lint import PyLinter


def _is_constant_zero(node: str | nodes.NodeNG) -> bool:
    # We have to check that node.value is not False because node.value == 0 is True
    # when node.value is False
    return (
        isinstance(node, astroid.Const) and node.value == 0 and node.value is not False
    )


class CompareToZeroChecker(checkers.BaseChecker):
    """Checks for comparisons to zero.

    Most of the time you should use the fact that integers with a value of 0 are false.
    An exception to this rule is when 0 is allowed in the program and has a
    different meaning than None!
    """

    # configuration section name
    name = "compare-to-zero"
    msgs = {
        "C2001": (
            '"%s" can be simplified to "%s" as 0 is falsey',
            "compare-to-zero",
            "Used when Pylint detects comparison to a 0 constant.",
        )
    }

    options = ()

    @utils.only_required_for_messages("compare-to-zero")
    def visit_compare(self, node: nodes.Compare) -> None:
        # pylint: disable=duplicate-code
        _operators = ["!=", "==", "is not", "is"]
        # note: astroid.Compare has the left most operand in node.left
        # while the rest are a list of tuples in node.ops
        # the format of the tuple is ('compare operator sign', node)
        # here we squash everything into `ops` to make it easier for processing later
        ops: list[tuple[str, nodes.NodeNG]] = [("", node.left)]
        ops.extend(node.ops)
        iter_ops = iter(ops)
        all_ops = list(itertools.chain(*iter_ops))

        for ops_idx in range(len(all_ops) - 2):
            op_1 = all_ops[ops_idx]
            op_2 = all_ops[ops_idx + 1]
            op_3 = all_ops[ops_idx + 2]
            error_detected = False

            # 0 ?? X
            if _is_constant_zero(op_1) and op_2 in _operators:
                error_detected = True
                op = op_3
            # X ?? 0
            elif op_2 in _operators and _is_constant_zero(op_3):
                error_detected = True
                op = op_1

            if error_detected:
                original = f"{op_1.as_string()} {op_2} {op_3.as_string()}"
                suggestion = (
                    op.as_string()
                    if op_2 in {"!=", "is not"}
                    else f"not {op.as_string()}"
                )
                self.add_message(
                    "compare-to-zero",
                    args=(original, suggestion),
                    node=node,
                    confidence=HIGH,
                )


def register(linter: PyLinter) -> None:
    linter.register_checker(CompareToZeroChecker(linter))
