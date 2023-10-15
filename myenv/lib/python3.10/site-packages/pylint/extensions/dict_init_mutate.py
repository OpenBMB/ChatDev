# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Check for use of dictionary mutation after initialization."""
from __future__ import annotations

from typing import TYPE_CHECKING

from astroid import nodes

from pylint.checkers import BaseChecker
from pylint.checkers.utils import only_required_for_messages
from pylint.interfaces import HIGH

if TYPE_CHECKING:
    from pylint.lint.pylinter import PyLinter


class DictInitMutateChecker(BaseChecker):
    name = "dict-init-mutate"
    msgs = {
        "C3401": (
            "Declare all known key/values when initializing the dictionary.",
            "dict-init-mutate",
            "Dictionaries can be initialized with a single statement "
            "using dictionary literal syntax.",
        )
    }

    @only_required_for_messages("dict-init-mutate")
    def visit_assign(self, node: nodes.Assign) -> None:
        """
        Detect dictionary mutation immediately after initialization.

        At this time, detecting nested mutation is not supported.
        """
        if not isinstance(node.value, nodes.Dict):
            return

        dict_name = node.targets[0]
        if len(node.targets) != 1 or not isinstance(dict_name, nodes.AssignName):
            return

        first_sibling = node.next_sibling()
        if (
            not first_sibling
            or not isinstance(first_sibling, nodes.Assign)
            or len(first_sibling.targets) != 1
        ):
            return

        sibling_target = first_sibling.targets[0]
        if not isinstance(sibling_target, nodes.Subscript):
            return

        sibling_name = sibling_target.value
        if not isinstance(sibling_name, nodes.Name):
            return

        if sibling_name.name == dict_name.name:
            self.add_message("dict-init-mutate", node=node, confidence=HIGH)


def register(linter: PyLinter) -> None:
    linter.register_checker(DictInitMutateChecker(linter))
