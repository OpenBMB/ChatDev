# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Looks for overlapping exceptions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import astroid
from astroid import nodes, util

from pylint import checkers
from pylint.checkers import utils
from pylint.checkers.exceptions import _annotated_unpack_infer

if TYPE_CHECKING:
    from pylint.lint import PyLinter


class OverlappingExceptionsChecker(checkers.BaseChecker):
    """Checks for two or more exceptions in the same exception handler
    clause that are identical or parts of the same inheritance hierarchy.

    (i.e. overlapping).
    """

    name = "overlap-except"
    msgs = {
        "W0714": (
            "Overlapping exceptions (%s)",
            "overlapping-except",
            "Used when exceptions in handler overlap or are identical",
        )
    }
    options = ()

    @utils.only_required_for_messages("overlapping-except")
    def visit_tryexcept(self, node: nodes.TryExcept) -> None:
        """Check for empty except."""
        for handler in node.handlers:
            if handler.type is None:
                continue
            if isinstance(handler.type, astroid.BoolOp):
                continue
            try:
                excs = list(_annotated_unpack_infer(handler.type))
            except astroid.InferenceError:
                continue

            handled_in_clause: list[tuple[Any, Any]] = []
            for part, exc in excs:
                if isinstance(exc, util.UninferableBase):
                    continue
                if isinstance(exc, astroid.Instance) and utils.inherit_from_std_ex(exc):
                    exc = exc._proxied

                if not isinstance(exc, astroid.ClassDef):
                    continue

                exc_ancestors = [
                    anc for anc in exc.ancestors() if isinstance(anc, astroid.ClassDef)
                ]

                for prev_part, prev_exc in handled_in_clause:
                    prev_exc_ancestors = [
                        anc
                        for anc in prev_exc.ancestors()
                        if isinstance(anc, astroid.ClassDef)
                    ]
                    if exc == prev_exc:
                        self.add_message(
                            "overlapping-except",
                            node=handler.type,
                            args=f"{prev_part.as_string()} and {part.as_string()} are the same",
                        )
                    elif prev_exc in exc_ancestors or exc in prev_exc_ancestors:
                        ancestor = part if exc in prev_exc_ancestors else prev_part
                        descendant = part if prev_exc in exc_ancestors else prev_part
                        self.add_message(
                            "overlapping-except",
                            node=handler.type,
                            args=f"{ancestor.as_string()} is an ancestor class of {descendant.as_string()}",
                        )
                handled_in_clause += [(part, exc)]


def register(linter: PyLinter) -> None:
    linter.register_checker(OverlappingExceptionsChecker(linter))
