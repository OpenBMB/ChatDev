# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Check for use of while loops."""

from __future__ import annotations

from typing import TYPE_CHECKING

from astroid import nodes

from pylint.checkers import BaseChecker
from pylint.checkers.utils import only_required_for_messages

if TYPE_CHECKING:
    from pylint.lint import PyLinter


class WhileChecker(BaseChecker):
    name = "while_used"
    msgs = {
        "W0149": (
            "Used `while` loop",
            "while-used",
            "Unbounded `while` loops can often be rewritten as bounded `for` loops. "
            "Exceptions can be made for cases such as event loops, listeners, etc.",
        )
    }

    @only_required_for_messages("while-used")
    def visit_while(self, node: nodes.While) -> None:
        self.add_message("while-used", node=node)


def register(linter: PyLinter) -> None:
    linter.register_checker(WhileChecker(linter))
