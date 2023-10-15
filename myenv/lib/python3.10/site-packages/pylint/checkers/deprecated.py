# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Checker mixin for deprecated functionality."""

from __future__ import annotations

from collections.abc import Container, Iterable
from itertools import chain

import astroid
from astroid import nodes

from pylint.checkers import utils
from pylint.checkers.base_checker import BaseChecker
from pylint.checkers.utils import get_import_name, infer_all, safe_infer
from pylint.typing import MessageDefinitionTuple

ACCEPTABLE_NODES = (
    astroid.BoundMethod,
    astroid.UnboundMethod,
    nodes.FunctionDef,
    nodes.ClassDef,
)


class DeprecatedMixin(BaseChecker):
    """A mixin implementing logic for checking deprecated symbols.

    A class implementing mixin must define "deprecated-method" Message.
    """

    DEPRECATED_MODULE_MESSAGE: dict[str, MessageDefinitionTuple] = {
        "W4901": (
            "Deprecated module %r",
            "deprecated-module",
            "A module marked as deprecated is imported.",
            {"old_names": [("W0402", "old-deprecated-module")], "shared": True},
        ),
    }

    DEPRECATED_METHOD_MESSAGE: dict[str, MessageDefinitionTuple] = {
        "W4902": (
            "Using deprecated method %s()",
            "deprecated-method",
            "The method is marked as deprecated and will be removed in the future.",
            {"old_names": [("W1505", "old-deprecated-method")], "shared": True},
        ),
    }

    DEPRECATED_ARGUMENT_MESSAGE: dict[str, MessageDefinitionTuple] = {
        "W4903": (
            "Using deprecated argument %s of method %s()",
            "deprecated-argument",
            "The argument is marked as deprecated and will be removed in the future.",
            {"old_names": [("W1511", "old-deprecated-argument")], "shared": True},
        ),
    }

    DEPRECATED_CLASS_MESSAGE: dict[str, MessageDefinitionTuple] = {
        "W4904": (
            "Using deprecated class %s of module %s",
            "deprecated-class",
            "The class is marked as deprecated and will be removed in the future.",
            {"old_names": [("W1512", "old-deprecated-class")], "shared": True},
        ),
    }

    DEPRECATED_DECORATOR_MESSAGE: dict[str, MessageDefinitionTuple] = {
        "W4905": (
            "Using deprecated decorator %s()",
            "deprecated-decorator",
            "The decorator is marked as deprecated and will be removed in the future.",
            {"old_names": [("W1513", "old-deprecated-decorator")], "shared": True},
        ),
    }

    @utils.only_required_for_messages(
        "deprecated-method",
        "deprecated-argument",
        "deprecated-class",
    )
    def visit_call(self, node: nodes.Call) -> None:
        """Called when a :class:`nodes.Call` node is visited."""
        self.check_deprecated_class_in_call(node)
        for inferred in infer_all(node.func):
            # Calling entry point for deprecation check logic.
            self.check_deprecated_method(node, inferred)

    @utils.only_required_for_messages(
        "deprecated-module",
        "deprecated-class",
    )
    def visit_import(self, node: nodes.Import) -> None:
        """Triggered when an import statement is seen."""
        for name in (name for name, _ in node.names):
            self.check_deprecated_module(node, name)
            if "." in name:
                # Checking deprecation for import module with class
                mod_name, class_name = name.split(".", 1)
                self.check_deprecated_class(node, mod_name, (class_name,))

    def deprecated_decorators(self) -> Iterable[str]:
        """Callback returning the deprecated decorators.

        Returns:
            collections.abc.Container of deprecated decorator names.
        """
        return ()

    @utils.only_required_for_messages("deprecated-decorator")
    def visit_decorators(self, node: nodes.Decorators) -> None:
        """Triggered when a decorator statement is seen."""
        children = list(node.get_children())
        if not children:
            return
        if isinstance(children[0], nodes.Call):
            inf = safe_infer(children[0].func)
        else:
            inf = safe_infer(children[0])
        qname = inf.qname() if inf else None
        if qname in self.deprecated_decorators():
            self.add_message("deprecated-decorator", node=node, args=qname)

    @utils.only_required_for_messages(
        "deprecated-module",
        "deprecated-class",
    )
    def visit_importfrom(self, node: nodes.ImportFrom) -> None:
        """Triggered when a from statement is seen."""
        basename = node.modname
        basename = get_import_name(node, basename)
        self.check_deprecated_module(node, basename)
        class_names = (name for name, _ in node.names)
        self.check_deprecated_class(node, basename, class_names)

    def deprecated_methods(self) -> Container[str]:
        """Callback returning the deprecated methods/functions.

        Returns:
            collections.abc.Container of deprecated function/method names.
        """
        return ()

    def deprecated_arguments(self, method: str) -> Iterable[tuple[int | None, str]]:
        """Callback returning the deprecated arguments of method/function.

        Args:
            method (str): name of function/method checked for deprecated arguments

        Returns:
            collections.abc.Iterable in form:
                ((POSITION1, PARAM1), (POSITION2: PARAM2) ...)
            where
                * POSITIONX - position of deprecated argument PARAMX in function definition.
                  If argument is keyword-only, POSITIONX should be None.
                * PARAMX - name of the deprecated argument.
            E.g. suppose function:

            .. code-block:: python
                def bar(arg1, arg2, arg3, arg4, arg5='spam')

            with deprecated arguments `arg2` and `arg4`. `deprecated_arguments` should return:

            .. code-block:: python
                ((1, 'arg2'), (3, 'arg4'))
        """
        # pylint: disable=unused-argument
        return ()

    def deprecated_modules(self) -> Iterable[str]:
        """Callback returning the deprecated modules.

        Returns:
            collections.abc.Container of deprecated module names.
        """
        return ()

    def deprecated_classes(self, module: str) -> Iterable[str]:
        """Callback returning the deprecated classes of module.

        Args:
            module (str): name of module checked for deprecated classes

        Returns:
            collections.abc.Container of deprecated class names.
        """
        # pylint: disable=unused-argument
        return ()

    def check_deprecated_module(self, node: nodes.Import, mod_path: str | None) -> None:
        """Checks if the module is deprecated."""
        for mod_name in self.deprecated_modules():
            if mod_path == mod_name or mod_path and mod_path.startswith(mod_name + "."):
                self.add_message("deprecated-module", node=node, args=mod_path)

    def check_deprecated_method(self, node: nodes.Call, inferred: nodes.NodeNG) -> None:
        """Executes the checker for the given node.

        This method should be called from the checker implementing this mixin.
        """

        # Reject nodes which aren't of interest to us.
        if not isinstance(inferred, ACCEPTABLE_NODES):
            return

        if isinstance(node.func, nodes.Attribute):
            func_name = node.func.attrname
        elif isinstance(node.func, nodes.Name):
            func_name = node.func.name
        else:
            # Not interested in other nodes.
            return

        qnames = {inferred.qname(), func_name}
        if any(name in self.deprecated_methods() for name in qnames):
            self.add_message("deprecated-method", node=node, args=(func_name,))
            return
        num_of_args = len(node.args)
        kwargs = {kw.arg for kw in node.keywords} if node.keywords else {}
        deprecated_arguments = (self.deprecated_arguments(qn) for qn in qnames)
        for position, arg_name in chain(*deprecated_arguments):
            if arg_name in kwargs:
                # function was called with deprecated argument as keyword argument
                self.add_message(
                    "deprecated-argument", node=node, args=(arg_name, func_name)
                )
            elif position is not None and position < num_of_args:
                # function was called with deprecated argument as positional argument
                self.add_message(
                    "deprecated-argument", node=node, args=(arg_name, func_name)
                )

    def check_deprecated_class(
        self, node: nodes.NodeNG, mod_name: str, class_names: Iterable[str]
    ) -> None:
        """Checks if the class is deprecated."""

        for class_name in class_names:
            if class_name in self.deprecated_classes(mod_name):
                self.add_message(
                    "deprecated-class", node=node, args=(class_name, mod_name)
                )

    def check_deprecated_class_in_call(self, node: nodes.Call) -> None:
        """Checks if call the deprecated class."""

        if isinstance(node.func, nodes.Attribute) and isinstance(
            node.func.expr, nodes.Name
        ):
            mod_name = node.func.expr.name
            class_name = node.func.attrname
            self.check_deprecated_class(node, mod_name, (class_name,))
