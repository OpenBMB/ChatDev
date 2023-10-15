# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Checks for yoda comparisons (variable before constant)
See https://en.wikipedia.org/wiki/Yoda_conditions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from astroid import nodes

from pylint.checkers import BaseChecker, utils

if TYPE_CHECKING:
    from pylint.lint import PyLinter

REVERSED_COMPS = {"<": ">", "<=": ">=", ">": "<", ">=": "<="}
COMPARISON_OPERATORS = frozenset(("==", "!=", "<", ">", "<=", ">="))


class MisplacedComparisonConstantChecker(BaseChecker):
    """Checks the placement of constants in comparisons."""

    # configuration section name
    name = "comparison-placement"
    msgs = {
        "C2201": (
            "Comparison should be %s",
            "misplaced-comparison-constant",
            "Used when the constant is placed on the left side "
            "of a comparison. It is usually clearer in intent to "
            "place it in the right hand side of the comparison.",
            {"old_names": [("C0122", "old-misplaced-comparison-constant")]},
        )
    }

    options = ()

    def _check_misplaced_constant(
        self,
        node: nodes.Compare,
        left: nodes.NodeNG,
        right: nodes.NodeNG,
        operator: str,
    ) -> None:
        if isinstance(right, nodes.Const):
            return
        operator = REVERSED_COMPS.get(operator, operator)
        suggestion = f"{right.as_string()} {operator} {left.value!r}"
        self.add_message("misplaced-comparison-constant", node=node, args=(suggestion,))

    @utils.only_required_for_messages("misplaced-comparison-constant")
    def visit_compare(self, node: nodes.Compare) -> None:
        # NOTE: this checker only works with binary comparisons like 'x == 42'
        # but not 'x == y == 42'
        if len(node.ops) != 1:
            return

        left = node.left
        operator, right = node.ops[0]
        if operator in COMPARISON_OPERATORS and isinstance(left, nodes.Const):
            self._check_misplaced_constant(node, left, right, operator)


def register(linter: PyLinter) -> None:
    linter.register_checker(MisplacedComparisonConstantChecker(linter))
