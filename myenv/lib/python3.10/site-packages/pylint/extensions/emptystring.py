# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Looks for  comparisons to empty string."""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING

from astroid import nodes

from pylint import checkers
from pylint.checkers import utils
from pylint.interfaces import HIGH

if TYPE_CHECKING:
    from pylint.lint import PyLinter


class CompareToEmptyStringChecker(checkers.BaseChecker):
    name = "compare-to-empty-string"
    msgs = {
        "C1901": (
            '"%s" can be simplified to "%s" as an empty string is falsey',
            "compare-to-empty-string",
            "Used when Pylint detects comparison to an empty string constant.",
        )
    }

    options = ()

    @utils.only_required_for_messages("compare-to-empty-string")
    def visit_compare(self, node: nodes.Compare) -> None:
        """Checks for comparisons to empty string.

        Most of the time you should use the fact that empty strings are false.
        An exception to this rule is when an empty string value is allowed in the program
        and has a different meaning than None!
        """
        _operators = {"!=", "==", "is not", "is"}
        # note: astroid.Compare has the left most operand in node.left while the rest
        # are a list of tuples in node.ops the format of the tuple is
        # ('compare operator sign', node) here we squash everything into `ops`
        # to make it easier for processing later
        ops: list[tuple[str, nodes.NodeNG | None]] = [("", node.left)]
        ops.extend(node.ops)
        iter_ops = iter(ops)
        ops = list(itertools.chain(*iter_ops))  # type: ignore[arg-type]
        for ops_idx in range(len(ops) - 2):
            op_1: nodes.NodeNG | None = ops[ops_idx]
            op_2: str = ops[ops_idx + 1]  # type: ignore[assignment]
            op_3: nodes.NodeNG | None = ops[ops_idx + 2]
            error_detected = False
            if op_1 is None or op_3 is None or op_2 not in _operators:
                continue
            node_name = ""
            # x ?? ""
            if utils.is_empty_str_literal(op_1):
                error_detected = True
                node_name = op_3.as_string()
            # '' ?? X
            elif utils.is_empty_str_literal(op_3):
                error_detected = True
                node_name = op_1.as_string()
            if error_detected:
                suggestion = f"not {node_name}" if op_2 in {"==", "is"} else node_name
                self.add_message(
                    "compare-to-empty-string",
                    args=(node.as_string(), suggestion),
                    node=node,
                    confidence=HIGH,
                )


def register(linter: PyLinter) -> None:
    linter.register_checker(CompareToEmptyStringChecker(linter))
