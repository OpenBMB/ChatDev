# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Basic Error checker from the basic checker."""

from __future__ import annotations

import itertools
from collections.abc import Iterator
from typing import Any

import astroid
from astroid import nodes
from astroid.typing import InferenceResult

from pylint.checkers import utils
from pylint.checkers.base.basic_checker import _BasicChecker
from pylint.checkers.utils import infer_all
from pylint.interfaces import HIGH

ABC_METACLASSES = {"_py_abc.ABCMeta", "abc.ABCMeta"}  # Python 3.7+,
# List of methods which can be redefined
REDEFINABLE_METHODS = frozenset(("__module__",))
TYPING_FORWARD_REF_QNAME = "typing.ForwardRef"


def _get_break_loop_node(break_node: nodes.Break) -> nodes.For | nodes.While | None:
    """Returns the loop node that holds the break node in arguments.

    Args:
        break_node (astroid.Break): the break node of interest.

    Returns:
        astroid.For or astroid.While: the loop node holding the break node.
    """
    loop_nodes = (nodes.For, nodes.While)
    parent = break_node.parent
    while not isinstance(parent, loop_nodes) or break_node in getattr(
        parent, "orelse", []
    ):
        break_node = parent
        parent = parent.parent
        if parent is None:
            break
    return parent


def _loop_exits_early(loop: nodes.For | nodes.While) -> bool:
    """Returns true if a loop may end with a break statement.

    Args:
        loop (astroid.For, astroid.While): the loop node inspected.

    Returns:
        bool: True if the loop may end with a break statement, False otherwise.
    """
    loop_nodes = (nodes.For, nodes.While)
    definition_nodes = (nodes.FunctionDef, nodes.ClassDef)
    inner_loop_nodes: list[nodes.For | nodes.While] = [
        _node
        for _node in loop.nodes_of_class(loop_nodes, skip_klass=definition_nodes)
        if _node != loop
    ]
    return any(
        _node
        for _node in loop.nodes_of_class(nodes.Break, skip_klass=definition_nodes)
        if _get_break_loop_node(_node) not in inner_loop_nodes
    )


def _has_abstract_methods(node: nodes.ClassDef) -> bool:
    """Determine if the given `node` has abstract methods.

    The methods should be made abstract by decorating them
    with `abc` decorators.
    """
    return len(utils.unimplemented_abstract_methods(node)) > 0


def redefined_by_decorator(node: nodes.FunctionDef) -> bool:
    """Return True if the object is a method redefined via decorator.

    For example:
        @property
        def x(self): return self._x
        @x.setter
        def x(self, value): self._x = value
    """
    if node.decorators:
        for decorator in node.decorators.nodes:
            if (
                isinstance(decorator, nodes.Attribute)
                and getattr(decorator.expr, "name", None) == node.name
            ):
                return True
    return False


class BasicErrorChecker(_BasicChecker):
    msgs = {
        "E0100": (
            "__init__ method is a generator",
            "init-is-generator",
            "Used when the special class method __init__ is turned into a "
            "generator by a yield in its body.",
        ),
        "E0101": (
            "Explicit return in __init__",
            "return-in-init",
            "Used when the special class method __init__ has an explicit "
            "return value.",
        ),
        "E0102": (
            "%s already defined line %s",
            "function-redefined",
            "Used when a function / class / method is redefined.",
        ),
        "E0103": (
            "%r not properly in loop",
            "not-in-loop",
            "Used when break or continue keywords are used outside a loop.",
        ),
        "E0104": (
            "Return outside function",
            "return-outside-function",
            'Used when a "return" statement is found outside a function or method.',
        ),
        "E0105": (
            "Yield outside function",
            "yield-outside-function",
            'Used when a "yield" statement is found outside a function or method.',
        ),
        "E0106": (
            "Return with argument inside generator",
            "return-arg-in-generator",
            'Used when a "return" statement with an argument is found '
            "outside in a generator function or method (e.g. with some "
            '"yield" statements).',
            {"maxversion": (3, 3)},
        ),
        "E0107": (
            "Use of the non-existent %s operator",
            "nonexistent-operator",
            "Used when you attempt to use the C-style pre-increment or "
            "pre-decrement operator -- and ++, which doesn't exist in Python.",
        ),
        "E0108": (
            "Duplicate argument name %s in function definition",
            "duplicate-argument-name",
            "Duplicate argument names in function definitions are syntax errors.",
        ),
        "E0110": (
            "Abstract class %r with abstract methods instantiated",
            "abstract-class-instantiated",
            "Used when an abstract class with `abc.ABCMeta` as metaclass "
            "has abstract methods and is instantiated.",
        ),
        "W0120": (
            "Else clause on loop without a break statement, remove the else and"
            " de-indent all the code inside it",
            "useless-else-on-loop",
            "Loops should only have an else clause if they can exit early "
            "with a break statement, otherwise the statements under else "
            "should be on the same scope as the loop itself.",
        ),
        "E0112": (
            "More than one starred expression in assignment",
            "too-many-star-expressions",
            "Emitted when there are more than one starred "
            "expressions (`*x`) in an assignment. This is a SyntaxError.",
        ),
        "E0113": (
            "Starred assignment target must be in a list or tuple",
            "invalid-star-assignment-target",
            "Emitted when a star expression is used as a starred assignment target.",
        ),
        "E0114": (
            "Can use starred expression only in assignment target",
            "star-needs-assignment-target",
            "Emitted when a star expression is not used in an assignment target.",
        ),
        "E0115": (
            "Name %r is nonlocal and global",
            "nonlocal-and-global",
            "Emitted when a name is both nonlocal and global.",
        ),
        "E0116": (
            "'continue' not supported inside 'finally' clause",
            "continue-in-finally",
            "Emitted when the `continue` keyword is found "
            "inside a finally clause, which is a SyntaxError.",
        ),
        "E0117": (
            "nonlocal name %s found without binding",
            "nonlocal-without-binding",
            "Emitted when a nonlocal variable does not have an attached "
            "name somewhere in the parent scopes",
        ),
        "E0118": (
            "Name %r is used prior to global declaration",
            "used-prior-global-declaration",
            "Emitted when a name is used prior a global declaration, "
            "which results in an error since Python 3.6.",
            {"minversion": (3, 6)},
        ),
    }

    def open(self) -> None:
        py_version = self.linter.config.py_version
        self._py38_plus = py_version >= (3, 8)

    @utils.only_required_for_messages("function-redefined")
    def visit_classdef(self, node: nodes.ClassDef) -> None:
        self._check_redefinition("class", node)

    def _too_many_starred_for_tuple(self, assign_tuple: nodes.Tuple) -> bool:
        starred_count = 0
        for elem in assign_tuple.itered():
            if isinstance(elem, nodes.Tuple):
                return self._too_many_starred_for_tuple(elem)
            if isinstance(elem, nodes.Starred):
                starred_count += 1
        return starred_count > 1

    @utils.only_required_for_messages(
        "too-many-star-expressions", "invalid-star-assignment-target"
    )
    def visit_assign(self, node: nodes.Assign) -> None:
        # Check *a, *b = ...
        assign_target = node.targets[0]
        # Check *a = b
        if isinstance(node.targets[0], nodes.Starred):
            self.add_message("invalid-star-assignment-target", node=node)

        if not isinstance(assign_target, nodes.Tuple):
            return
        if self._too_many_starred_for_tuple(assign_target):
            self.add_message("too-many-star-expressions", node=node)

    @utils.only_required_for_messages("star-needs-assignment-target")
    def visit_starred(self, node: nodes.Starred) -> None:
        """Check that a Starred expression is used in an assignment target."""
        if isinstance(node.parent, nodes.Call):
            # f(*args) is converted to Call(args=[Starred]), so ignore
            # them for this check.
            return
        if isinstance(node.parent, (nodes.List, nodes.Tuple, nodes.Set, nodes.Dict)):
            # PEP 448 unpacking.
            return

        stmt = node.statement(future=True)
        if not isinstance(stmt, nodes.Assign):
            return

        if stmt.value is node or stmt.value.parent_of(node):
            self.add_message("star-needs-assignment-target", node=node)

    @utils.only_required_for_messages(
        "init-is-generator",
        "return-in-init",
        "function-redefined",
        "return-arg-in-generator",
        "duplicate-argument-name",
        "nonlocal-and-global",
        "used-prior-global-declaration",
    )
    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        self._check_nonlocal_and_global(node)
        self._check_name_used_prior_global(node)
        if not redefined_by_decorator(
            node
        ) and not utils.is_registered_in_singledispatch_function(node):
            self._check_redefinition(node.is_method() and "method" or "function", node)
        # checks for max returns, branch, return in __init__
        returns = node.nodes_of_class(
            nodes.Return, skip_klass=(nodes.FunctionDef, nodes.ClassDef)
        )
        if node.is_method() and node.name == "__init__":
            if node.is_generator():
                self.add_message("init-is-generator", node=node)
            else:
                values = [r.value for r in returns]
                # Are we returning anything but None from constructors
                if any(v for v in values if not utils.is_none(v)):
                    self.add_message("return-in-init", node=node)
        # Check for duplicate names by clustering args with same name for detailed report
        arg_clusters = {}
        arguments: Iterator[Any] = filter(None, [node.args.args, node.args.kwonlyargs])
        for arg in itertools.chain.from_iterable(arguments):
            if arg.name in arg_clusters:
                self.add_message(
                    "duplicate-argument-name",
                    node=arg,
                    args=(arg.name,),
                    confidence=HIGH,
                )
            else:
                arg_clusters[arg.name] = arg

    visit_asyncfunctiondef = visit_functiondef

    def _check_name_used_prior_global(self, node: nodes.FunctionDef) -> None:
        scope_globals = {
            name: child
            for child in node.nodes_of_class(nodes.Global)
            for name in child.names
            if child.scope() is node
        }

        if not scope_globals:
            return

        for node_name in node.nodes_of_class(nodes.Name):
            if node_name.scope() is not node:
                continue

            name = node_name.name
            corresponding_global = scope_globals.get(name)
            if not corresponding_global:
                continue

            global_lineno = corresponding_global.fromlineno
            if global_lineno and global_lineno > node_name.fromlineno:
                self.add_message(
                    "used-prior-global-declaration", node=node_name, args=(name,)
                )

    def _check_nonlocal_and_global(self, node: nodes.FunctionDef) -> None:
        """Check that a name is both nonlocal and global."""

        def same_scope(current: nodes.Global | nodes.Nonlocal) -> bool:
            return current.scope() is node

        from_iter = itertools.chain.from_iterable
        nonlocals = set(
            from_iter(
                child.names
                for child in node.nodes_of_class(nodes.Nonlocal)
                if same_scope(child)
            )
        )

        if not nonlocals:
            return

        global_vars = set(
            from_iter(
                child.names
                for child in node.nodes_of_class(nodes.Global)
                if same_scope(child)
            )
        )
        for name in nonlocals.intersection(global_vars):
            self.add_message("nonlocal-and-global", args=(name,), node=node)

    @utils.only_required_for_messages("return-outside-function")
    def visit_return(self, node: nodes.Return) -> None:
        if not isinstance(node.frame(future=True), nodes.FunctionDef):
            self.add_message("return-outside-function", node=node)

    @utils.only_required_for_messages("yield-outside-function")
    def visit_yield(self, node: nodes.Yield) -> None:
        self._check_yield_outside_func(node)

    @utils.only_required_for_messages("yield-outside-function")
    def visit_yieldfrom(self, node: nodes.YieldFrom) -> None:
        self._check_yield_outside_func(node)

    @utils.only_required_for_messages("not-in-loop", "continue-in-finally")
    def visit_continue(self, node: nodes.Continue) -> None:
        self._check_in_loop(node, "continue")

    @utils.only_required_for_messages("not-in-loop")
    def visit_break(self, node: nodes.Break) -> None:
        self._check_in_loop(node, "break")

    @utils.only_required_for_messages("useless-else-on-loop")
    def visit_for(self, node: nodes.For) -> None:
        self._check_else_on_loop(node)

    @utils.only_required_for_messages("useless-else-on-loop")
    def visit_while(self, node: nodes.While) -> None:
        self._check_else_on_loop(node)

    @utils.only_required_for_messages("nonexistent-operator")
    def visit_unaryop(self, node: nodes.UnaryOp) -> None:
        """Check use of the non-existent ++ and -- operators."""
        if (
            (node.op in "+-")
            and isinstance(node.operand, nodes.UnaryOp)
            and (node.operand.op == node.op)
            and (node.col_offset + 1 == node.operand.col_offset)
        ):
            self.add_message("nonexistent-operator", node=node, args=node.op * 2)

    def _check_nonlocal_without_binding(self, node: nodes.Nonlocal, name: str) -> None:
        current_scope = node.scope()
        while current_scope.parent is not None:
            if not isinstance(current_scope, (nodes.ClassDef, nodes.FunctionDef)):
                self.add_message("nonlocal-without-binding", args=(name,), node=node)
                return

            # Search for `name` in the parent scope if:
            #  `current_scope` is the same scope in which the `nonlocal` name is declared
            #  or `name` is not in `current_scope.locals`.
            if current_scope is node.scope() or name not in current_scope.locals:
                current_scope = current_scope.parent.scope()
                continue

            # Okay, found it.
            return

        if not isinstance(current_scope, nodes.FunctionDef):
            self.add_message(
                "nonlocal-without-binding", args=(name,), node=node, confidence=HIGH
            )

    @utils.only_required_for_messages("nonlocal-without-binding")
    def visit_nonlocal(self, node: nodes.Nonlocal) -> None:
        for name in node.names:
            self._check_nonlocal_without_binding(node, name)

    @utils.only_required_for_messages("abstract-class-instantiated")
    def visit_call(self, node: nodes.Call) -> None:
        """Check instantiating abstract class with
        abc.ABCMeta as metaclass.
        """
        for inferred in infer_all(node.func):
            self._check_inferred_class_is_abstract(inferred, node)

    def _check_inferred_class_is_abstract(
        self, inferred: InferenceResult, node: nodes.Call
    ) -> None:
        if not isinstance(inferred, nodes.ClassDef):
            return

        klass = utils.node_frame_class(node)
        if klass is inferred:
            # Don't emit the warning if the class is instantiated
            # in its own body or if the call is not an instance
            # creation. If the class is instantiated into its own
            # body, we're expecting that it knows what it is doing.
            return

        # __init__ was called
        abstract_methods = _has_abstract_methods(inferred)

        if not abstract_methods:
            return

        metaclass = inferred.metaclass()

        if metaclass is None:
            # Python 3.4 has `abc.ABC`, which won't be detected
            # by ClassNode.metaclass()
            for ancestor in inferred.ancestors():
                if ancestor.qname() == "abc.ABC":
                    self.add_message(
                        "abstract-class-instantiated", args=(inferred.name,), node=node
                    )
                    break

            return

        if metaclass.qname() in ABC_METACLASSES:
            self.add_message(
                "abstract-class-instantiated", args=(inferred.name,), node=node
            )

    def _check_yield_outside_func(self, node: nodes.Yield) -> None:
        if not isinstance(node.frame(future=True), (nodes.FunctionDef, nodes.Lambda)):
            self.add_message("yield-outside-function", node=node)

    def _check_else_on_loop(self, node: nodes.For | nodes.While) -> None:
        """Check that any loop with an else clause has a break statement."""
        if node.orelse and not _loop_exits_early(node):
            self.add_message(
                "useless-else-on-loop",
                node=node,
                # This is not optimal, but the line previous
                # to the first statement in the else clause
                # will usually be the one that contains the else:.
                line=node.orelse[0].lineno - 1,
            )

    def _check_in_loop(
        self, node: nodes.Continue | nodes.Break, node_name: str
    ) -> None:
        """Check that a node is inside a for or while loop."""
        for parent in node.node_ancestors():
            if isinstance(parent, (nodes.For, nodes.While)):
                if node not in parent.orelse:
                    return

            if isinstance(parent, (nodes.ClassDef, nodes.FunctionDef)):
                break
            if (
                isinstance(parent, nodes.TryFinally)
                and node in parent.finalbody
                and isinstance(node, nodes.Continue)
                and not self._py38_plus
            ):
                self.add_message("continue-in-finally", node=node)

        self.add_message("not-in-loop", node=node, args=node_name)

    def _check_redefinition(
        self, redeftype: str, node: nodes.Call | nodes.FunctionDef
    ) -> None:
        """Check for redefinition of a function / method / class name."""
        parent_frame = node.parent.frame(future=True)

        # Ignore function stubs created for type information
        redefinitions = [
            i
            for i in parent_frame.locals[node.name]
            if not (isinstance(i.parent, nodes.AnnAssign) and i.parent.simple)
        ]
        defined_self = next(
            (local for local in redefinitions if not utils.is_overload_stub(local)),
            node,
        )
        if defined_self is not node and not astroid.are_exclusive(node, defined_self):
            # Additional checks for methods which are not considered
            # redefined, since they are already part of the base API.
            if (
                isinstance(parent_frame, nodes.ClassDef)
                and node.name in REDEFINABLE_METHODS
            ):
                return

            # Skip typing.overload() functions.
            if utils.is_overload_stub(node):
                return

            # Exempt functions redefined on a condition.
            if isinstance(node.parent, nodes.If):
                # Exempt "if not <func>" cases
                if (
                    isinstance(node.parent.test, nodes.UnaryOp)
                    and node.parent.test.op == "not"
                    and isinstance(node.parent.test.operand, nodes.Name)
                    and node.parent.test.operand.name == node.name
                ):
                    return

                # Exempt "if <func> is not None" cases
                # pylint: disable=too-many-boolean-expressions
                if (
                    isinstance(node.parent.test, nodes.Compare)
                    and isinstance(node.parent.test.left, nodes.Name)
                    and node.parent.test.left.name == node.name
                    and node.parent.test.ops[0][0] == "is"
                    and isinstance(node.parent.test.ops[0][1], nodes.Const)
                    and node.parent.test.ops[0][1].value is None
                ):
                    return

            # Check if we have forward references for this node.
            try:
                redefinition_index = redefinitions.index(node)
            except ValueError:
                pass
            else:
                for redefinition in redefinitions[:redefinition_index]:
                    inferred = utils.safe_infer(redefinition)
                    if (
                        inferred
                        and isinstance(inferred, astroid.Instance)
                        and inferred.qname() == TYPING_FORWARD_REF_QNAME
                    ):
                        return

            dummy_variables_rgx = self.linter.config.dummy_variables_rgx
            if dummy_variables_rgx and dummy_variables_rgx.match(node.name):
                return
            self.add_message(
                "function-redefined",
                node=node,
                args=(redeftype, defined_self.fromlineno),
            )
