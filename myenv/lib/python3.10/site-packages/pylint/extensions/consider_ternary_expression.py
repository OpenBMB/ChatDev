# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Check for if / assign blocks that can be rewritten with if-expressions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from astroid import nodes

from pylint.checkers import BaseChecker

if TYPE_CHECKING:
    from pylint.lint import PyLinter


class ConsiderTernaryExpressionChecker(BaseChecker):
    name = "consider_ternary_expression"
    msgs = {
        "W0160": (
            "Consider rewriting as a ternary expression",
            "consider-ternary-expression",
            "Multiple assign statements spread across if/else blocks can be "
            "rewritten with a single assignment and ternary expression",
        )
    }

    def visit_if(self, node: nodes.If) -> None:
        if isinstance(node.parent, nodes.If):
            return

        if len(node.body) != 1 or len(node.orelse) != 1:
            return

        bst = node.body[0]
        ost = node.orelse[0]

        if not isinstance(bst, nodes.Assign) or not isinstance(ost, nodes.Assign):
            return

        for bname, oname in zip(bst.targets, ost.targets):
            if not isinstance(bname, nodes.AssignName) or not isinstance(
                oname, nodes.AssignName
            ):
                return

            if bname.name != oname.name:
                return

        self.add_message("consider-ternary-expression", node=node)


def register(linter: PyLinter) -> None:
    linter.register_checker(ConsiderTernaryExpressionChecker(linter))
