# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

from typing import TYPE_CHECKING

from astroid import nodes

from pylint.checkers import BaseChecker
from pylint.checkers.utils import (
    PYMETHODS,
    decorated_with_property,
    is_overload_stub,
    is_protocol_class,
    overrides_a_method,
)
from pylint.interfaces import INFERENCE

if TYPE_CHECKING:
    from pylint.lint.pylinter import PyLinter


class NoSelfUseChecker(BaseChecker):
    name = "no_self_use"
    msgs = {
        "R6301": (
            "Method could be a function",
            "no-self-use",
            "Used when a method doesn't use its bound instance, and so could "
            "be written as a function.",
            {"old_names": [("R0201", "old-no-self-use")]},
        ),
    }

    def __init__(self, linter: PyLinter) -> None:
        super().__init__(linter)
        self._first_attrs: list[str | None] = []
        self._meth_could_be_func: bool | None = None

    def visit_name(self, node: nodes.Name) -> None:
        """Check if the name handle an access to a class member
        if so, register it.
        """
        if self._first_attrs and (
            node.name == self._first_attrs[-1] or not self._first_attrs[-1]
        ):
            self._meth_could_be_func = False

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        if not node.is_method():
            return
        self._meth_could_be_func = True
        self._check_first_arg_for_type(node)

    visit_asyncfunctiondef = visit_functiondef

    def _check_first_arg_for_type(self, node: nodes.FunctionDef) -> None:
        """Check the name of first argument."""
        # pylint: disable=duplicate-code
        if node.args.posonlyargs:
            first_arg = node.args.posonlyargs[0].name
        elif node.args.args:
            first_arg = node.argnames()[0]
        else:
            first_arg = None
        self._first_attrs.append(first_arg)
        # static method
        if node.type == "staticmethod":
            self._first_attrs[-1] = None

    def leave_functiondef(self, node: nodes.FunctionDef) -> None:
        """On method node, check if this method couldn't be a function.

        ignore class, static and abstract methods, initializer,
        methods overridden from a parent class.
        """
        if node.is_method():
            first = self._first_attrs.pop()
            if first is None:
                return
            class_node = node.parent.frame(future=True)
            if (
                self._meth_could_be_func
                and node.type == "method"
                and node.name not in PYMETHODS
                and not (
                    node.is_abstract()
                    or overrides_a_method(class_node, node.name)
                    or decorated_with_property(node)
                    or _has_bare_super_call(node)
                    or is_protocol_class(class_node)
                    or is_overload_stub(node)
                )
            ):
                self.add_message("no-self-use", node=node, confidence=INFERENCE)

    leave_asyncfunctiondef = leave_functiondef


def _has_bare_super_call(fundef_node: nodes.FunctionDef) -> bool:
    for call in fundef_node.nodes_of_class(nodes.Call):
        func = call.func
        if isinstance(func, nodes.Name) and func.name == "super" and not call.args:
            return True
    return False


def register(linter: PyLinter) -> None:
    linter.register_checker(NoSelfUseChecker(linter))
