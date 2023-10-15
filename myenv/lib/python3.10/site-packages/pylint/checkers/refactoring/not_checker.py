# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

import astroid
from astroid import nodes

from pylint import checkers
from pylint.checkers import utils


class NotChecker(checkers.BaseChecker):
    """Checks for too many not in comparison expressions.

    - "not not" should trigger a warning
    - "not" followed by a comparison should trigger a warning
    """

    msgs = {
        "C0113": (
            'Consider changing "%s" to "%s"',
            "unneeded-not",
            "Used when a boolean expression contains an unneeded negation.",
        )
    }
    name = "refactoring"
    reverse_op = {
        "<": ">=",
        "<=": ">",
        ">": "<=",
        ">=": "<",
        "==": "!=",
        "!=": "==",
        "in": "not in",
        "is": "is not",
    }
    # sets are not ordered, so for example "not set(LEFT_VALS) <= set(RIGHT_VALS)" is
    # not equivalent to "set(LEFT_VALS) > set(RIGHT_VALS)"
    skipped_nodes = (nodes.Set,)
    # 'builtins' py3, '__builtin__' py2
    skipped_classnames = [f"builtins.{qname}" for qname in ("set", "frozenset")]

    @utils.only_required_for_messages("unneeded-not")
    def visit_unaryop(self, node: nodes.UnaryOp) -> None:
        if node.op != "not":
            return
        operand = node.operand

        if isinstance(operand, nodes.UnaryOp) and operand.op == "not":
            self.add_message(
                "unneeded-not",
                node=node,
                args=(node.as_string(), operand.operand.as_string()),
            )
        elif isinstance(operand, nodes.Compare):
            left = operand.left
            # ignore multiple comparisons
            if len(operand.ops) > 1:
                return
            operator, right = operand.ops[0]
            if operator not in self.reverse_op:
                return
            # Ignore __ne__ as function of __eq__
            frame = node.frame(future=True)
            if frame.name == "__ne__" and operator == "==":
                return
            for _type in (utils.node_type(left), utils.node_type(right)):
                if not _type:
                    return
                if isinstance(_type, self.skipped_nodes):
                    return
                if (
                    isinstance(_type, astroid.Instance)
                    and _type.qname() in self.skipped_classnames
                ):
                    return
            suggestion = (
                f"{left.as_string()} {self.reverse_op[operator]} {right.as_string()}"
            )
            self.add_message(
                "unneeded-not", node=node, args=(node.as_string(), suggestion)
            )
