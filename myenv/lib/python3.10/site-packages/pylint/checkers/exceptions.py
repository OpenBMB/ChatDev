# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Checks for various exception related errors."""

from __future__ import annotations

import builtins
import inspect
import warnings
from collections.abc import Generator
from typing import TYPE_CHECKING, Any

import astroid
from astroid import nodes, objects, util
from astroid.context import InferenceContext
from astroid.typing import InferenceResult, SuccessfulInferenceResult

from pylint import checkers
from pylint.checkers import utils
from pylint.interfaces import HIGH, INFERENCE
from pylint.typing import MessageDefinitionTuple

if TYPE_CHECKING:
    from pylint.lint import PyLinter


def _builtin_exceptions() -> set[str]:
    def predicate(obj: Any) -> bool:
        return isinstance(obj, type) and issubclass(obj, BaseException)

    members = inspect.getmembers(builtins, predicate)
    return {exc.__name__ for (_, exc) in members}


def _annotated_unpack_infer(
    stmt: nodes.NodeNG, context: InferenceContext | None = None
) -> Generator[tuple[nodes.NodeNG, SuccessfulInferenceResult], None, None]:
    """Recursively generate nodes inferred by the given statement.

    If the inferred value is a list or a tuple, recurse on the elements.
    Returns an iterator which yields tuples in the format
    ('original node', 'inferred node').
    """
    if isinstance(stmt, (nodes.List, nodes.Tuple)):
        for elt in stmt.elts:
            inferred = utils.safe_infer(elt)
            if inferred and not isinstance(inferred, util.UninferableBase):
                yield elt, inferred
        return
    for inferred in stmt.infer(context):
        if isinstance(inferred, util.UninferableBase):
            continue
        yield stmt, inferred


def _is_raising(body: list[nodes.NodeNG]) -> bool:
    """Return whether the given statement node raises an exception."""
    return any(isinstance(node, nodes.Raise) for node in body)


MSGS: dict[str, MessageDefinitionTuple] = {
    "E0701": (
        "Bad except clauses order (%s)",
        "bad-except-order",
        "Used when except clauses are not in the correct order (from the "
        "more specific to the more generic). If you don't fix the order, "
        "some exceptions may not be caught by the most specific handler.",
    ),
    "E0702": (
        "Raising %s while only classes or instances are allowed",
        "raising-bad-type",
        "Used when something which is neither a class nor an instance "
        "is raised (i.e. a `TypeError` will be raised).",
    ),
    "E0704": (
        "The raise statement is not inside an except clause",
        "misplaced-bare-raise",
        "Used when a bare raise is not used inside an except clause. "
        "This generates an error, since there are no active exceptions "
        "to be reraised. An exception to this rule is represented by "
        "a bare raise inside a finally clause, which might work, as long "
        "as an exception is raised inside the try block, but it is "
        "nevertheless a code smell that must not be relied upon.",
    ),
    "E0705": (
        "Exception cause set to something which is not an exception, nor None",
        "bad-exception-cause",
        'Used when using the syntax "raise ... from ...", '
        "where the exception cause is not an exception, "
        "nor None.",
        {"old_names": [("E0703", "bad-exception-context")]},
    ),
    "E0710": (
        "Raising a new style class which doesn't inherit from BaseException",
        "raising-non-exception",
        "Used when a new style class which doesn't inherit from "
        "BaseException is raised.",
    ),
    "E0711": (
        "NotImplemented raised - should raise NotImplementedError",
        "notimplemented-raised",
        "Used when NotImplemented is raised instead of NotImplementedError",
    ),
    "E0712": (
        "Catching an exception which doesn't inherit from Exception: %s",
        "catching-non-exception",
        "Used when a class which doesn't inherit from "
        "Exception is used as an exception in an except clause.",
    ),
    "W0702": (
        "No exception type(s) specified",
        "bare-except",
        "A bare ``except:`` clause will catch ``SystemExit`` and "
        "``KeyboardInterrupt`` exceptions, making it harder to interrupt a program "
        "with ``Control-C``, and can disguise other problems. If you want to catch "
        "all exceptions that signal program errors, use ``except Exception:`` (bare "
        "except is equivalent to ``except BaseException:``).",
    ),
    "W0718": (
        "Catching too general exception %s",
        "broad-exception-caught",
        "If you use a naked ``except Exception:`` clause, you might end up catching "
        "exceptions other than the ones you expect to catch. This can hide bugs or "
        "make it harder to debug programs when unrelated errors are hidden.",
        {"old_names": [("W0703", "broad-except")]},
    ),
    "W0705": (
        "Catching previously caught exception type %s",
        "duplicate-except",
        "Used when an except catches a type that was already caught by "
        "a previous handler.",
    ),
    "W0706": (
        "The except handler raises immediately",
        "try-except-raise",
        "Used when an except handler uses raise as its first or only "
        "operator. This is useless because it raises back the exception "
        "immediately. Remove the raise operator or the entire "
        "try-except-raise block!",
    ),
    "W0707": (
        "Consider explicitly re-raising using %s'%s from %s'",
        "raise-missing-from",
        "Python's exception chaining shows the traceback of the current exception, "
        "but also of the original exception. When you raise a new exception after "
        "another exception was caught it's likely that the second exception is a "
        "friendly re-wrapping of the first exception. In such cases `raise from` "
        "provides a better link between the two tracebacks in the final error.",
    ),
    "W0711": (
        'Exception to catch is the result of a binary "%s" operation',
        "binary-op-exception",
        "Used when the exception to catch is of the form "
        '"except A or B:".  If intending to catch multiple, '
        'rewrite as "except (A, B):"',
    ),
    "W0715": (
        "Exception arguments suggest string formatting might be intended",
        "raising-format-tuple",
        "Used when passing multiple arguments to an exception "
        "constructor, the first of them a string literal containing what "
        "appears to be placeholders intended for formatting",
    ),
    "W0716": (
        "Invalid exception operation. %s",
        "wrong-exception-operation",
        "Used when an operation is done against an exception, but the operation "
        "is not valid for the exception in question. Usually emitted when having "
        "binary operations between exceptions in except handlers.",
    ),
    "W0719": (
        "Raising too general exception: %s",
        "broad-exception-raised",
        "Raising exceptions that are too generic force you to catch exceptions "
        "generically too. It will force you to use a naked ``except Exception:`` "
        "clause. You might then end up catching exceptions other than the ones "
        "you expect to catch. This can hide bugs or make it harder to debug programs "
        "when unrelated errors are hidden.",
    ),
}


class BaseVisitor:
    """Base class for visitors defined in this module."""

    def __init__(self, checker: ExceptionsChecker, node: nodes.Raise) -> None:
        self._checker = checker
        self._node = node

    def visit(self, node: SuccessfulInferenceResult) -> None:
        name = node.__class__.__name__.lower()
        dispatch_meth = getattr(self, "visit_" + name, None)
        if dispatch_meth:
            dispatch_meth(node)
        else:
            self.visit_default(node)

    def visit_default(self, _: nodes.NodeNG) -> None:
        """Default implementation for all the nodes."""


class ExceptionRaiseRefVisitor(BaseVisitor):
    """Visit references (anything that is not an AST leaf)."""

    def visit_name(self, node: nodes.Name) -> None:
        if node.name == "NotImplemented":
            self._checker.add_message(
                "notimplemented-raised", node=self._node, confidence=HIGH
            )
            return

        try:
            exceptions = list(_annotated_unpack_infer(node))
        except astroid.InferenceError:
            return

        for _, exception in exceptions:
            if isinstance(
                exception, nodes.ClassDef
            ) and self._checker._is_overgeneral_exception(exception):
                self._checker.add_message(
                    "broad-exception-raised",
                    args=exception.name,
                    node=self._node,
                    confidence=INFERENCE,
                )

    def visit_call(self, node: nodes.Call) -> None:
        if isinstance(node.func, nodes.Name):
            self.visit_name(node.func)
        if (
            len(node.args) > 1
            and isinstance(node.args[0], nodes.Const)
            and isinstance(node.args[0].value, str)
        ):
            msg = node.args[0].value
            if "%" in msg or ("{" in msg and "}" in msg):
                self._checker.add_message(
                    "raising-format-tuple", node=self._node, confidence=HIGH
                )


class ExceptionRaiseLeafVisitor(BaseVisitor):
    """Visitor for handling leaf kinds of a raise value."""

    def visit_const(self, node: nodes.Const) -> None:
        self._checker.add_message(
            "raising-bad-type",
            node=self._node,
            args=node.value.__class__.__name__,
            confidence=INFERENCE,
        )

    def visit_instance(self, instance: objects.ExceptionInstance) -> None:
        cls = instance._proxied
        self.visit_classdef(cls)

    # Exception instances have a particular class type
    visit_exceptioninstance = visit_instance

    def visit_classdef(self, node: nodes.ClassDef) -> None:
        if not utils.inherit_from_std_ex(node) and utils.has_known_bases(node):
            if node.newstyle:
                self._checker.add_message(
                    "raising-non-exception",
                    node=self._node,
                    confidence=INFERENCE,
                )

    def visit_tuple(self, _: nodes.Tuple) -> None:
        self._checker.add_message(
            "raising-bad-type",
            node=self._node,
            args="tuple",
            confidence=INFERENCE,
        )

    def visit_default(self, node: nodes.NodeNG) -> None:
        name = getattr(node, "name", node.__class__.__name__)
        self._checker.add_message(
            "raising-bad-type",
            node=self._node,
            args=name,
            confidence=INFERENCE,
        )


class ExceptionsChecker(checkers.BaseChecker):
    """Exception related checks."""

    name = "exceptions"
    msgs = MSGS
    options = (
        (
            "overgeneral-exceptions",
            {
                "default": ("builtins.BaseException", "builtins.Exception"),
                "type": "csv",
                "metavar": "<comma-separated class names>",
                "help": "Exceptions that will emit a warning when caught.",
            },
        ),
    )

    def open(self) -> None:
        self._builtin_exceptions = _builtin_exceptions()
        for exc_name in self.linter.config.overgeneral_exceptions:
            if "." not in exc_name:
                warnings.warn_explicit(
                    "Specifying exception names in the overgeneral-exceptions option"
                    " without module name is deprecated and support for it"
                    " will be removed in pylint 3.0."
                    f" Use fully qualified name (maybe 'builtins.{exc_name}' ?) instead.",
                    category=UserWarning,
                    filename="pylint: Command line or configuration file",
                    lineno=1,
                    module="pylint",
                )
        super().open()

    @utils.only_required_for_messages(
        "misplaced-bare-raise",
        "raising-bad-type",
        "raising-non-exception",
        "notimplemented-raised",
        "bad-exception-cause",
        "raising-format-tuple",
        "raise-missing-from",
        "broad-exception-raised",
    )
    def visit_raise(self, node: nodes.Raise) -> None:
        if node.exc is None:
            self._check_misplaced_bare_raise(node)
            return

        if node.cause is None:
            self._check_raise_missing_from(node)
        else:
            self._check_bad_exception_cause(node)

        expr = node.exc
        ExceptionRaiseRefVisitor(self, node).visit(expr)

        inferred = utils.safe_infer(expr)
        if inferred is None or isinstance(inferred, util.UninferableBase):
            return
        ExceptionRaiseLeafVisitor(self, node).visit(inferred)

    def _check_misplaced_bare_raise(self, node: nodes.Raise) -> None:
        # Filter out if it's present in __exit__.
        scope = node.scope()
        if (
            isinstance(scope, nodes.FunctionDef)
            and scope.is_method()
            and scope.name == "__exit__"
        ):
            return

        current = node
        # Stop when a new scope is generated or when the raise
        # statement is found inside a TryFinally.
        ignores = (nodes.ExceptHandler, nodes.FunctionDef)
        while current and not isinstance(current.parent, ignores):
            current = current.parent

        expected = (nodes.ExceptHandler,)
        if not current or not isinstance(current.parent, expected):
            self.add_message("misplaced-bare-raise", node=node, confidence=HIGH)

    def _check_bad_exception_cause(self, node: nodes.Raise) -> None:
        """Verify that the exception cause is properly set.

        An exception cause can be only `None` or an exception.
        """
        cause = utils.safe_infer(node.cause)
        if cause is None or isinstance(cause, util.UninferableBase):
            return

        if isinstance(cause, nodes.Const):
            if cause.value is not None:
                self.add_message("bad-exception-cause", node=node, confidence=INFERENCE)
        elif not isinstance(cause, nodes.ClassDef) and not utils.inherit_from_std_ex(
            cause
        ):
            self.add_message("bad-exception-cause", node=node, confidence=INFERENCE)

    def _check_raise_missing_from(self, node: nodes.Raise) -> None:
        if node.exc is None:
            # This is a plain `raise`, raising the previously-caught exception. No need for a
            # cause.
            return
        # We'd like to check whether we're inside an `except` clause:
        containing_except_node = utils.find_except_wrapper_node_in_scope(node)
        if not containing_except_node:
            return
        # We found a surrounding `except`! We're almost done proving there's a
        # `raise-missing-from` here. The only thing we need to protect against is that maybe
        # the `raise` is raising the exception that was caught, possibly with some shenanigans
        # like `exc.with_traceback(whatever)`. We won't analyze these, we'll just assume
        # there's a violation on two simple cases: `raise SomeException(whatever)` and `raise
        # SomeException`.
        if containing_except_node.name is None:
            # The `except` doesn't have an `as exception:` part, meaning there's no way that
            # the `raise` is raising the same exception.
            class_of_old_error = "Exception"
            if isinstance(containing_except_node.type, (nodes.Name, nodes.Tuple)):
                # 'except ZeroDivisionError' or 'except (ZeroDivisionError, ValueError)'
                class_of_old_error = containing_except_node.type.as_string()
            self.add_message(
                "raise-missing-from",
                node=node,
                args=(
                    f"'except {class_of_old_error} as exc' and ",
                    node.as_string(),
                    "exc",
                ),
                confidence=HIGH,
            )
        elif (
            isinstance(node.exc, nodes.Call)
            and isinstance(node.exc.func, nodes.Name)
            or isinstance(node.exc, nodes.Name)
            and node.exc.name != containing_except_node.name.name
        ):
            # We have a `raise SomeException(whatever)` or a `raise SomeException`
            self.add_message(
                "raise-missing-from",
                node=node,
                args=("", node.as_string(), containing_except_node.name.name),
                confidence=HIGH,
            )

    def _check_catching_non_exception(
        self,
        handler: nodes.ExceptHandler,
        exc: SuccessfulInferenceResult,
        part: nodes.NodeNG,
    ) -> None:
        if isinstance(exc, nodes.Tuple):
            # Check if it is a tuple of exceptions.
            inferred = [utils.safe_infer(elt) for elt in exc.elts]
            if any(isinstance(node, util.UninferableBase) for node in inferred):
                # Don't emit if we don't know every component.
                return
            if all(
                node
                and (utils.inherit_from_std_ex(node) or not utils.has_known_bases(node))
                for node in inferred
            ):
                return

        if not isinstance(exc, nodes.ClassDef):
            # Don't emit the warning if the inferred stmt
            # is None, but the exception handler is something else,
            # maybe it was redefined.
            if isinstance(exc, nodes.Const) and exc.value is None:
                if (
                    isinstance(handler.type, nodes.Const) and handler.type.value is None
                ) or handler.type.parent_of(exc):
                    # If the exception handler catches None or
                    # the exception component, which is None, is
                    # defined by the entire exception handler, then
                    # emit a warning.
                    self.add_message(
                        "catching-non-exception",
                        node=handler.type,
                        args=(part.as_string(),),
                    )
            else:
                self.add_message(
                    "catching-non-exception",
                    node=handler.type,
                    args=(part.as_string(),),
                )
            return

        if (
            not utils.inherit_from_std_ex(exc)
            and exc.name not in self._builtin_exceptions
        ):
            if utils.has_known_bases(exc):
                self.add_message(
                    "catching-non-exception", node=handler.type, args=(exc.name,)
                )

    def _check_try_except_raise(self, node: nodes.TryExcept) -> None:
        def gather_exceptions_from_handler(
            handler: nodes.ExceptHandler,
        ) -> list[InferenceResult] | None:
            exceptions: list[InferenceResult] = []
            if handler.type:
                exceptions_in_handler = utils.safe_infer(handler.type)
                if isinstance(exceptions_in_handler, nodes.Tuple):
                    exceptions = list(
                        {
                            exception
                            for exception in exceptions_in_handler.elts
                            if isinstance(exception, (nodes.Name, nodes.Attribute))
                        }
                    )
                elif exceptions_in_handler:
                    exceptions = [exceptions_in_handler]
                else:
                    # Break when we cannot infer anything reliably.
                    return None
            return exceptions

        bare_raise = False
        handler_having_bare_raise = None
        exceptions_in_bare_handler: list[InferenceResult] | None = []
        for handler in node.handlers:
            if bare_raise:
                # check that subsequent handler is not parent of handler which had bare raise.
                # since utils.safe_infer can fail for bare except, check it before.
                # also break early if bare except is followed by bare except.

                excs_in_current_handler = gather_exceptions_from_handler(handler)
                if not excs_in_current_handler:
                    break
                if exceptions_in_bare_handler is None:
                    # It can be `None` when the inference failed
                    break
                for exc_in_current_handler in excs_in_current_handler:
                    inferred_current = utils.safe_infer(exc_in_current_handler)
                    if any(
                        utils.is_subclass_of(utils.safe_infer(e), inferred_current)
                        for e in exceptions_in_bare_handler
                    ):
                        bare_raise = False
                        break

            # `raise` as the first operator inside the except handler
            if _is_raising([handler.body[0]]):
                # flags when there is a bare raise
                if handler.body[0].exc is None:
                    bare_raise = True
                    handler_having_bare_raise = handler
                    exceptions_in_bare_handler = gather_exceptions_from_handler(handler)
        else:
            if bare_raise:
                self.add_message("try-except-raise", node=handler_having_bare_raise)

    @utils.only_required_for_messages("wrong-exception-operation")
    def visit_binop(self, node: nodes.BinOp) -> None:
        if isinstance(node.parent, nodes.ExceptHandler):
            # except (V | A)
            suggestion = f"Did you mean '({node.left.as_string()}, {node.right.as_string()})' instead?"
            self.add_message("wrong-exception-operation", node=node, args=(suggestion,))

    @utils.only_required_for_messages("wrong-exception-operation")
    def visit_compare(self, node: nodes.Compare) -> None:
        if isinstance(node.parent, nodes.ExceptHandler):
            # except (V < A)
            suggestion = (
                f"Did you mean '({node.left.as_string()}, "
                f"{', '.join(o.as_string() for _, o in node.ops)})' instead?"
            )
            self.add_message("wrong-exception-operation", node=node, args=(suggestion,))

    @utils.only_required_for_messages(
        "bare-except",
        "broad-exception-caught",
        "try-except-raise",
        "binary-op-exception",
        "bad-except-order",
        "catching-non-exception",
        "duplicate-except",
    )
    def visit_tryexcept(self, node: nodes.TryExcept) -> None:
        """Check for empty except."""
        self._check_try_except_raise(node)
        exceptions_classes: list[Any] = []
        nb_handlers = len(node.handlers)
        for index, handler in enumerate(node.handlers):
            if handler.type is None:
                if not _is_raising(handler.body):
                    self.add_message("bare-except", node=handler, confidence=HIGH)

                # check if an "except:" is followed by some other
                # except
                if index < (nb_handlers - 1):
                    msg = "empty except clause should always appear last"
                    self.add_message(
                        "bad-except-order", node=node, args=msg, confidence=HIGH
                    )

            elif isinstance(handler.type, nodes.BoolOp):
                self.add_message(
                    "binary-op-exception",
                    node=handler,
                    args=handler.type.op,
                    confidence=HIGH,
                )
            else:
                try:
                    exceptions = list(_annotated_unpack_infer(handler.type))
                except astroid.InferenceError:
                    continue

                for part, exception in exceptions:
                    if isinstance(
                        exception, astroid.Instance
                    ) and utils.inherit_from_std_ex(exception):
                        exception = exception._proxied

                    self._check_catching_non_exception(handler, exception, part)

                    if not isinstance(exception, nodes.ClassDef):
                        continue

                    exc_ancestors = [
                        anc
                        for anc in exception.ancestors()
                        if isinstance(anc, nodes.ClassDef)
                    ]

                    for previous_exc in exceptions_classes:
                        if previous_exc in exc_ancestors:
                            msg = f"{previous_exc.name} is an ancestor class of {exception.name}"
                            self.add_message(
                                "bad-except-order",
                                node=handler.type,
                                args=msg,
                                confidence=INFERENCE,
                            )
                    if self._is_overgeneral_exception(exception) and not _is_raising(
                        handler.body
                    ):
                        self.add_message(
                            "broad-exception-caught",
                            args=exception.name,
                            node=handler.type,
                            confidence=INFERENCE,
                        )

                    if exception in exceptions_classes:
                        self.add_message(
                            "duplicate-except",
                            args=exception.name,
                            node=handler.type,
                            confidence=INFERENCE,
                        )

                exceptions_classes += [exc for _, exc in exceptions]

    def _is_overgeneral_exception(self, exception: nodes.ClassDef) -> bool:
        return (
            exception.qname() in self.linter.config.overgeneral_exceptions
            # TODO: 3.0: not a qualified name, deprecated
            or "." not in exception.name
            and exception.name in self.linter.config.overgeneral_exceptions
            and exception.root().name == utils.EXCEPTIONS_MODULE
        )


def register(linter: PyLinter) -> None:
    linter.register_checker(ExceptionsChecker(linter))
