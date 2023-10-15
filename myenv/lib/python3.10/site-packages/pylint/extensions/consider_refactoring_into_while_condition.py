# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Looks for try/except statements with too much code in the try clause."""

from __future__ import annotations

from typing import TYPE_CHECKING

from astroid import nodes

from pylint import checkers
from pylint.checkers import utils
from pylint.interfaces import HIGH

if TYPE_CHECKING:
    from pylint.lint import PyLinter


class ConsiderRefactorIntoWhileConditionChecker(checkers.BaseChecker):
    """Checks for instances where while loops are implemented with a constant condition
    which.

    always evaluates to truthy and the first statement(s) is/are if statements which, when
    evaluated.

    to True, breaks out of the loop.

    The if statement(s) can be refactored into the while loop.
    """

    name = "consider_refactoring_into_while"
    msgs = {
        "R3501": (
            "Consider using 'while %s' instead of 'while %s:' an 'if', and a 'break'",
            "consider-refactoring-into-while-condition",
            "Emitted when `while True:` loop is used and the first statement is a break condition. "
            "The ``if / break`` construct can be removed if the check is inverted and moved to "
            "the ``while`` statement.",
        ),
    }

    @utils.only_required_for_messages("consider-refactoring-into-while-condition")
    def visit_while(self, node: nodes.While) -> None:
        self._check_breaking_after_while_true(node)

    def _check_breaking_after_while_true(self, node: nodes.While) -> None:
        """Check that any loop with an ``if`` clause has a break statement."""
        if not isinstance(node.test, nodes.Const) or not node.test.bool_value():
            return
        pri_candidates: list[nodes.If] = []
        for n in node.body:
            if not isinstance(n, nodes.If):
                break
            pri_candidates.append(n)
        candidates = []
        tainted = False
        for c in pri_candidates:
            if tainted or not isinstance(c.body[0], nodes.Break):
                break
            candidates.append(c)
            orelse = c.orelse
            while orelse:
                orelse_node = orelse[0]
                if not isinstance(orelse_node, nodes.If):
                    tainted = True
                else:
                    candidates.append(orelse_node)
                if not isinstance(orelse_node, nodes.If):
                    break
                orelse = orelse_node.orelse

        candidates = [n for n in candidates if isinstance(n.body[0], nodes.Break)]
        msg = " and ".join(
            [f"({utils.not_condition_as_string(c.test)})" for c in candidates]
        )
        if len(candidates) == 1:
            msg = utils.not_condition_as_string(candidates[0].test)
        if not msg:
            return

        self.add_message(
            "consider-refactoring-into-while-condition",
            node=node,
            line=node.lineno,
            args=(msg, node.test.as_string()),
            confidence=HIGH,
        )


def register(linter: PyLinter) -> None:
    linter.register_checker(ConsiderRefactorIntoWhileConditionChecker(linter))
