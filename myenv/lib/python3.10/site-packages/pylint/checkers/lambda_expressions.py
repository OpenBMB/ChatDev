# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

from itertools import zip_longest
from typing import TYPE_CHECKING

from astroid import nodes

from pylint.checkers import BaseChecker
from pylint.interfaces import HIGH

if TYPE_CHECKING:
    from pylint.lint import PyLinter


class LambdaExpressionChecker(BaseChecker):
    """Check for unnecessary usage of lambda expressions."""

    name = "lambda-expressions"
    msgs = {
        "C3001": (
            "Lambda expression assigned to a variable. "
            'Define a function using the "def" keyword instead.',
            "unnecessary-lambda-assignment",
            "Used when a lambda expression is assigned to variable "
            'rather than defining a standard function with the "def" keyword.',
        ),
        "C3002": (
            "Lambda expression called directly. Execute the expression inline instead.",
            "unnecessary-direct-lambda-call",
            "Used when a lambda expression is directly called "
            "rather than executing its contents inline.",
        ),
    }
    options = ()

    def visit_assign(self, node: nodes.Assign) -> None:
        """Check if lambda expression is assigned to a variable."""
        if isinstance(node.targets[0], nodes.AssignName) and isinstance(
            node.value, nodes.Lambda
        ):
            self.add_message(
                "unnecessary-lambda-assignment",
                node=node.value,
                confidence=HIGH,
            )
        elif isinstance(node.targets[0], nodes.Tuple) and isinstance(
            node.value, (nodes.Tuple, nodes.List)
        ):
            # Iterate over tuple unpacking assignment elements and
            # see if any lambdas are assigned to a variable.
            # N.B. We may encounter W0632 (unbalanced-tuple-unpacking)
            # and still need to flag the lambdas that are being assigned.
            for lhs_elem, rhs_elem in zip_longest(
                node.targets[0].elts, node.value.elts
            ):
                if lhs_elem is None or rhs_elem is None:
                    # unbalanced tuple unpacking. stop checking.
                    break
                if isinstance(lhs_elem, nodes.AssignName) and isinstance(
                    rhs_elem, nodes.Lambda
                ):
                    self.add_message(
                        "unnecessary-lambda-assignment",
                        node=rhs_elem,
                        confidence=HIGH,
                    )

    def visit_namedexpr(self, node: nodes.NamedExpr) -> None:
        if isinstance(node.target, nodes.AssignName) and isinstance(
            node.value, nodes.Lambda
        ):
            self.add_message(
                "unnecessary-lambda-assignment",
                node=node.value,
                confidence=HIGH,
            )

    def visit_call(self, node: nodes.Call) -> None:
        """Check if lambda expression is called directly."""
        if isinstance(node.func, nodes.Lambda):
            self.add_message(
                "unnecessary-direct-lambda-call",
                node=node,
                confidence=HIGH,
            )


def register(linter: PyLinter) -> None:
    linter.register_checker(LambdaExpressionChecker(linter))
