# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

from typing import TYPE_CHECKING

from astroid import nodes

from pylint.checkers import BaseChecker
from pylint.checkers.utils import only_required_for_messages

if TYPE_CHECKING:
    from pylint.lint import PyLinter


class SetMembershipChecker(BaseChecker):
    name = "set_membership"
    msgs = {
        "R6201": (
            "Consider using set for membership test",
            "use-set-for-membership",
            "Membership tests are more efficient when performed on "
            "a lookup optimized datatype like ``sets``.",
        ),
    }

    def __init__(self, linter: PyLinter) -> None:
        """Initialize checker instance."""
        super().__init__(linter=linter)

    @only_required_for_messages("use-set-for-membership")
    def visit_compare(self, node: nodes.Compare) -> None:
        for op, comparator in node.ops:
            if op == "in":
                self._check_in_comparison(comparator)

    def _check_in_comparison(self, comparator: nodes.NodeNG) -> None:
        """Checks for membership comparisons with in-place container objects."""
        if not isinstance(comparator, nodes.BaseContainer) or isinstance(
            comparator, nodes.Set
        ):
            return

        # Heuristic - We need to be sure all items in set are hashable
        if all(isinstance(item, nodes.Const) for item in comparator.elts):
            self.add_message("use-set-for-membership", node=comparator)


def register(linter: PyLinter) -> None:
    linter.register_checker(SetMembershipChecker(linter))
