# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Check for new / old style related problems."""

from __future__ import annotations

from typing import TYPE_CHECKING

import astroid
from astroid import nodes

from pylint.checkers import BaseChecker
from pylint.checkers.utils import (
    has_known_bases,
    node_frame_class,
    only_required_for_messages,
)
from pylint.typing import MessageDefinitionTuple

if TYPE_CHECKING:
    from pylint.lint import PyLinter

MSGS: dict[str, MessageDefinitionTuple] = {
    "E1003": (
        "Bad first argument %r given to super()",
        "bad-super-call",
        "Used when another argument than the current class is given as "
        "first argument of the super builtin.",
    )
}


class NewStyleConflictChecker(BaseChecker):
    """Checks for usage of new style capabilities on old style classes and
    other new/old styles conflicts problems.

    * use of property, __slots__, super
    * "super" usage
    """

    # configuration section name
    name = "newstyle"
    # messages
    msgs = MSGS
    # configuration options
    options = ()

    @only_required_for_messages("bad-super-call")
    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Check use of super."""
        # ignore actual functions or method within a new style class
        if not node.is_method():
            return
        klass = node.parent.frame(future=True)
        for stmt in node.nodes_of_class(nodes.Call):
            if node_frame_class(stmt) != node_frame_class(node):
                # Don't look down in other scopes.
                continue

            expr = stmt.func
            if not isinstance(expr, nodes.Attribute):
                continue

            call = expr.expr
            # skip the test if using super
            if not (
                isinstance(call, nodes.Call)
                and isinstance(call.func, nodes.Name)
                and call.func.name == "super"
            ):
                continue

            # super should not be used on an old style class
            if klass.newstyle or not has_known_bases(klass):
                # super first arg should not be the class
                if not call.args:
                    continue

                # calling super(type(self), self) can lead to recursion loop
                # in derived classes
                arg0 = call.args[0]
                if (
                    isinstance(arg0, nodes.Call)
                    and isinstance(arg0.func, nodes.Name)
                    and arg0.func.name == "type"
                ):
                    self.add_message("bad-super-call", node=call, args=("type",))
                    continue

                # calling super(self.__class__, self) can lead to recursion loop
                # in derived classes
                if (
                    len(call.args) >= 2
                    and isinstance(call.args[1], nodes.Name)
                    and call.args[1].name == "self"
                    and isinstance(arg0, nodes.Attribute)
                    and arg0.attrname == "__class__"
                ):
                    self.add_message(
                        "bad-super-call", node=call, args=("self.__class__",)
                    )
                    continue

                try:
                    supcls = call.args and next(call.args[0].infer(), None)
                except astroid.InferenceError:
                    continue

                # If the supcls is in the ancestors of klass super can be used to skip
                # a step in the mro() and get a method from a higher parent
                if klass is not supcls and all(i != supcls for i in klass.ancestors()):
                    name = None
                    # if supcls is not Uninferable, then supcls was inferred
                    # and use its name. Otherwise, try to look
                    # for call.args[0].name
                    if supcls:
                        name = supcls.name
                    elif call.args and hasattr(call.args[0], "name"):
                        name = call.args[0].name
                    if name:
                        self.add_message("bad-super-call", node=call, args=(name,))

    visit_asyncfunctiondef = visit_functiondef


def register(linter: PyLinter) -> None:
    linter.register_checker(NewStyleConflictChecker(linter))
