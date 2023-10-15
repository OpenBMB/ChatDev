# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Looks for try/except statements with too much code in the try clause."""

from __future__ import annotations

from typing import TYPE_CHECKING

from astroid import nodes

from pylint import checkers

if TYPE_CHECKING:
    from pylint.lint import PyLinter


class BroadTryClauseChecker(checkers.BaseChecker):
    """Checks for try clauses with too many lines.

    According to PEP 8, ``try`` clauses shall contain the absolute minimum
    amount of code. This checker enforces a maximum number of statements within
    ``try`` clauses.
    """

    # configuration section name
    name = "broad_try_clause"
    msgs = {
        "W0717": (
            "%s",
            "too-many-try-statements",
            "Try clause contains too many statements.",
        )
    }

    options = (
        (
            "max-try-statements",
            {
                "default": 1,
                "type": "int",
                "metavar": "<int>",
                "help": "Maximum number of statements allowed in a try clause",
            },
        ),
    )

    def _count_statements(self, try_node: nodes.TryExcept | nodes.TryFinally) -> int:
        statement_count = len(try_node.body)

        for body_node in try_node.body:
            if isinstance(body_node, (nodes.For, nodes.If, nodes.While, nodes.With)):
                statement_count += self._count_statements(body_node)

        return statement_count

    def visit_tryexcept(self, node: nodes.TryExcept | nodes.TryFinally) -> None:
        try_clause_statements = self._count_statements(node)
        if try_clause_statements > self.linter.config.max_try_statements:
            msg = (
                f"try clause contains {try_clause_statements} statements, expected at"
                f" most {self.linter.config.max_try_statements}"
            )
            self.add_message(
                "too-many-try-statements", node.lineno, node=node, args=msg
            )

    visit_tryfinally = visit_tryexcept


def register(linter: PyLinter) -> None:
    linter.register_checker(BroadTryClauseChecker(linter))
