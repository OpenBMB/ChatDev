# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from astroid import nodes

from pylint.checkers import utils
from pylint.checkers.base.basic_checker import _BasicChecker


class PassChecker(_BasicChecker):
    """Check if the pass statement is really necessary."""

    msgs = {
        "W0107": (
            "Unnecessary pass statement",
            "unnecessary-pass",
            'Used when a "pass" statement that can be avoided is encountered.',
        )
    }

    @utils.only_required_for_messages("unnecessary-pass")
    def visit_pass(self, node: nodes.Pass) -> None:
        if len(node.parent.child_sequence(node)) > 1 or (
            isinstance(node.parent, (nodes.ClassDef, nodes.FunctionDef))
            and node.parent.doc_node
        ):
            self.add_message("unnecessary-pass", node=node)
