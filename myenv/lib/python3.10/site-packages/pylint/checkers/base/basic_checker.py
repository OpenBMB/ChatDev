# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Basic checker for Python code."""

from __future__ import annotations

import collections
import itertools
import sys
from collections.abc import Iterator
from typing import TYPE_CHECKING, cast

import astroid
from astroid import nodes, objects, util

from pylint import utils as lint_utils
from pylint.checkers import BaseChecker, utils
from pylint.interfaces import HIGH, INFERENCE, Confidence
from pylint.reporters.ureports import nodes as reporter_nodes
from pylint.utils import LinterStats

if TYPE_CHECKING:
    from pylint.lint.pylinter import PyLinter

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal


class _BasicChecker(BaseChecker):
    """Permits separating multiple checks with the same checker name into
    classes/file.
    """

    name = "basic"


REVERSED_PROTOCOL_METHOD = "__reversed__"
SEQUENCE_PROTOCOL_METHODS = ("__getitem__", "__len__")
REVERSED_METHODS = (SEQUENCE_PROTOCOL_METHODS, (REVERSED_PROTOCOL_METHOD,))
# A mapping from qname -> symbol, to be used when generating messages
# about dangerous default values as arguments
DEFAULT_ARGUMENT_SYMBOLS = dict(
    zip(
        [".".join(["builtins", x]) for x in ("set", "dict", "list")],
        ["set()", "{}", "[]"],
    ),
    **{
        x: f"{x}()"
        for x in (
            "collections.deque",
            "collections.ChainMap",
            "collections.Counter",
            "collections.OrderedDict",
            "collections.defaultdict",
            "collections.UserDict",
            "collections.UserList",
        )
    },
)


def report_by_type_stats(
    sect: reporter_nodes.Section,
    stats: LinterStats,
    old_stats: LinterStats | None,
) -> None:
    """Make a report of.

    * percentage of different types documented
    * percentage of different types with a bad name
    """
    # percentage of different types documented and/or with a bad name
    nice_stats: dict[str, dict[str, str]] = {}
    for node_type in ("module", "class", "method", "function"):
        node_type = cast(Literal["function", "class", "method", "module"], node_type)
        total = stats.get_node_count(node_type)
        nice_stats[node_type] = {}
        if total != 0:
            undocumented_node = stats.get_undocumented(node_type)
            documented = total - undocumented_node
            percent = (documented * 100.0) / total
            nice_stats[node_type]["percent_documented"] = f"{percent:.2f}"
            badname_node = stats.get_bad_names(node_type)
            percent = (badname_node * 100.0) / total
            nice_stats[node_type]["percent_badname"] = f"{percent:.2f}"
    lines = ["type", "number", "old number", "difference", "%documented", "%badname"]
    for node_type in ("module", "class", "method", "function"):
        node_type = cast(Literal["function", "class", "method", "module"], node_type)
        new = stats.get_node_count(node_type)
        old = old_stats.get_node_count(node_type) if old_stats else None
        diff_str = lint_utils.diff_string(old, new) if old else None
        lines += [
            node_type,
            str(new),
            str(old) if old else "NC",
            diff_str if diff_str else "NC",
            nice_stats[node_type].get("percent_documented", "0"),
            nice_stats[node_type].get("percent_badname", "0"),
        ]
    sect.append(reporter_nodes.Table(children=lines, cols=6, rheaders=1))


# pylint: disable-next = too-many-public-methods
class BasicChecker(_BasicChecker):
    """Basic checker.

    Checks for :
    * doc strings
    * number of arguments, local variables, branches, returns and statements in
    functions, methods
    * required module attributes
    * dangerous default values as arguments
    * redefinition of function / method / class
    * uses of the global statement
    """

    name = "basic"
    msgs = {
        "W0101": (
            "Unreachable code",
            "unreachable",
            'Used when there is some code behind a "return" or "raise" '
            "statement, which will never be accessed.",
        ),
        "W0102": (
            "Dangerous default value %s as argument",
            "dangerous-default-value",
            "Used when a mutable value as list or dictionary is detected in "
            "a default value for an argument.",
        ),
        "W0104": (
            "Statement seems to have no effect",
            "pointless-statement",
            "Used when a statement doesn't have (or at least seems to) any effect.",
        ),
        "W0105": (
            "String statement has no effect",
            "pointless-string-statement",
            "Used when a string is used as a statement (which of course "
            "has no effect). This is a particular case of W0104 with its "
            "own message so you can easily disable it if you're using "
            "those strings as documentation, instead of comments.",
        ),
        "W0106": (
            'Expression "%s" is assigned to nothing',
            "expression-not-assigned",
            "Used when an expression that is not a function call is assigned "
            "to nothing. Probably something else was intended.",
        ),
        "W0108": (
            "Lambda may not be necessary",
            "unnecessary-lambda",
            "Used when the body of a lambda expression is a function call "
            "on the same argument list as the lambda itself; such lambda "
            "expressions are in all but a few cases replaceable with the "
            "function being called in the body of the lambda.",
        ),
        "W0109": (
            "Duplicate key %r in dictionary",
            "duplicate-key",
            "Used when a dictionary expression binds the same key multiple times.",
        ),
        "W0122": (
            "Use of exec",
            "exec-used",
            "Raised when the 'exec' statement is used. It's dangerous to use this "
            "function for a user input, and it's also slower than actual code in "
            "general. This doesn't mean you should never use it, but you should "
            "consider alternatives first and restrict the functions available.",
        ),
        "W0123": (
            "Use of eval",
            "eval-used",
            'Used when you use the "eval" function, to discourage its '
            "usage. Consider using `ast.literal_eval` for safely evaluating "
            "strings containing Python expressions "
            "from untrusted sources.",
        ),
        "W0150": (
            "%s statement in finally block may swallow exception",
            "lost-exception",
            "Used when a break or a return statement is found inside the "
            "finally clause of a try...finally block: the exceptions raised "
            "in the try clause will be silently swallowed instead of being "
            "re-raised.",
        ),
        "W0199": (
            "Assert called on a populated tuple. Did you mean 'assert x,y'?",
            "assert-on-tuple",
            "A call of assert on a tuple will always evaluate to true if "
            "the tuple is not empty, and will always evaluate to false if "
            "it is.",
        ),
        "W0124": (
            'Following "as" with another context manager looks like a tuple.',
            "confusing-with-statement",
            "Emitted when a `with` statement component returns multiple values "
            "and uses name binding with `as` only for a part of those values, "
            "as in with ctx() as a, b. This can be misleading, since it's not "
            "clear if the context manager returns a tuple or if the node without "
            "a name binding is another context manager.",
        ),
        "W0125": (
            "Using a conditional statement with a constant value",
            "using-constant-test",
            "Emitted when a conditional statement (If or ternary if) "
            "uses a constant value for its test. This might not be what "
            "the user intended to do.",
        ),
        "W0126": (
            "Using a conditional statement with potentially wrong function or method call due to "
            "missing parentheses",
            "missing-parentheses-for-call-in-test",
            "Emitted when a conditional statement (If or ternary if) "
            "seems to wrongly call a function due to missing parentheses",
        ),
        "W0127": (
            "Assigning the same variable %r to itself",
            "self-assigning-variable",
            "Emitted when we detect that a variable is assigned to itself",
        ),
        "W0128": (
            "Redeclared variable %r in assignment",
            "redeclared-assigned-name",
            "Emitted when we detect that a variable was redeclared in the same assignment.",
        ),
        "E0111": (
            "The first reversed() argument is not a sequence",
            "bad-reversed-sequence",
            "Used when the first argument to reversed() builtin "
            "isn't a sequence (does not implement __reversed__, "
            "nor __getitem__ and __len__",
        ),
        "E0119": (
            "format function is not called on str",
            "misplaced-format-function",
            "Emitted when format function is not called on str object. "
            'e.g doing print("value: {}").format(123) instead of '
            'print("value: {}".format(123)). This might not be what the user '
            "intended to do.",
        ),
        "W0129": (
            "Assert statement has a string literal as its first argument. The assert will %s fail.",
            "assert-on-string-literal",
            "Used when an assert statement has a string literal as its first argument, which will "
            "cause the assert to always pass.",
        ),
        "W0130": (
            "Duplicate value %r in set",
            "duplicate-value",
            "This message is emitted when a set contains the same value two or more times.",
        ),
        "W0131": (
            "Named expression used without context",
            "named-expr-without-context",
            "Emitted if named expression is used to do a regular assignment "
            "outside a context like if, for, while, or a comprehension.",
        ),
        "W0133": (
            "Exception statement has no effect",
            "pointless-exception-statement",
            "Used when an exception is created without being assigned, raised or returned "
            "for subsequent use elsewhere.",
        ),
    }

    reports = (("RP0101", "Statistics by type", report_by_type_stats),)

    def __init__(self, linter: PyLinter) -> None:
        super().__init__(linter)
        self._tryfinallys: list[nodes.TryFinally] | None = None

    def open(self) -> None:
        """Initialize visit variables and statistics."""
        py_version = self.linter.config.py_version
        self._py38_plus = py_version >= (3, 8)
        self._tryfinallys = []
        self.linter.stats.reset_node_count()

    @utils.only_required_for_messages(
        "using-constant-test", "missing-parentheses-for-call-in-test"
    )
    def visit_if(self, node: nodes.If) -> None:
        self._check_using_constant_test(node, node.test)

    @utils.only_required_for_messages(
        "using-constant-test", "missing-parentheses-for-call-in-test"
    )
    def visit_ifexp(self, node: nodes.IfExp) -> None:
        self._check_using_constant_test(node, node.test)

    @utils.only_required_for_messages(
        "using-constant-test", "missing-parentheses-for-call-in-test"
    )
    def visit_comprehension(self, node: nodes.Comprehension) -> None:
        if node.ifs:
            for if_test in node.ifs:
                self._check_using_constant_test(node, if_test)

    def _check_using_constant_test(
        self,
        node: nodes.If | nodes.IfExp | nodes.Comprehension,
        test: nodes.NodeNG | None,
    ) -> None:
        const_nodes = (
            nodes.Module,
            nodes.GeneratorExp,
            nodes.Lambda,
            nodes.FunctionDef,
            nodes.ClassDef,
            astroid.bases.Generator,
            astroid.UnboundMethod,
            astroid.BoundMethod,
            nodes.Module,
        )
        structs = (nodes.Dict, nodes.Tuple, nodes.Set, nodes.List)

        # These nodes are excepted, since they are not constant
        # values, requiring a computation to happen.
        except_nodes = (
            nodes.Call,
            nodes.BinOp,
            nodes.BoolOp,
            nodes.UnaryOp,
            nodes.Subscript,
        )
        inferred = None
        emit = isinstance(test, (nodes.Const,) + structs + const_nodes)
        maybe_generator_call = None
        if not isinstance(test, except_nodes):
            inferred = utils.safe_infer(test)
            if isinstance(inferred, util.UninferableBase) and isinstance(
                test, nodes.Name
            ):
                emit, maybe_generator_call = BasicChecker._name_holds_generator(test)

        # Emit if calling a function that only returns GeneratorExp (always tests True)
        elif isinstance(test, nodes.Call):
            maybe_generator_call = test
        if maybe_generator_call:
            inferred_call = utils.safe_infer(maybe_generator_call.func)
            if isinstance(inferred_call, nodes.FunctionDef):
                # Can't use all(x) or not any(not x) for this condition, because it
                # will return True for empty generators, which is not what we want.
                all_returns_were_generator = None
                for return_node in inferred_call._get_return_nodes_skip_functions():
                    if not isinstance(return_node.value, nodes.GeneratorExp):
                        all_returns_were_generator = False
                        break
                    all_returns_were_generator = True
                if all_returns_were_generator:
                    self.add_message(
                        "using-constant-test", node=node, confidence=INFERENCE
                    )
                    return

        if emit:
            self.add_message("using-constant-test", node=test, confidence=INFERENCE)
        elif isinstance(inferred, const_nodes):
            # If the constant node is a FunctionDef or Lambda then
            # it may be an illicit function call due to missing parentheses
            call_inferred = None
            try:
                # Just forcing the generator to infer all elements.
                # astroid.exceptions.InferenceError are false positives
                # see https://github.com/PyCQA/pylint/pull/8185
                if isinstance(inferred, nodes.FunctionDef):
                    call_inferred = list(inferred.infer_call_result())
                elif isinstance(inferred, nodes.Lambda):
                    call_inferred = list(inferred.infer_call_result(node))
            except astroid.InferenceError:
                call_inferred = None
            if call_inferred:
                self.add_message(
                    "missing-parentheses-for-call-in-test",
                    node=test,
                    confidence=INFERENCE,
                )
            self.add_message("using-constant-test", node=test, confidence=INFERENCE)

    @staticmethod
    def _name_holds_generator(test: nodes.Name) -> tuple[bool, nodes.Call | None]:
        """Return whether `test` tests a name certain to hold a generator, or optionally
        a call that should be then tested to see if *it* returns only generators.
        """
        assert isinstance(test, nodes.Name)
        emit = False
        maybe_generator_call = None
        lookup_result = test.frame(future=True).lookup(test.name)
        if not lookup_result:
            return emit, maybe_generator_call
        maybe_generator_assigned = (
            isinstance(assign_name.parent.value, nodes.GeneratorExp)
            for assign_name in lookup_result[1]
            if isinstance(assign_name.parent, nodes.Assign)
        )
        first_item = next(maybe_generator_assigned, None)
        if first_item is not None:
            # Emit if this variable is certain to hold a generator
            if all(itertools.chain((first_item,), maybe_generator_assigned)):
                emit = True
            # If this variable holds the result of a call, save it for next test
            elif (
                len(lookup_result[1]) == 1
                and isinstance(lookup_result[1][0].parent, nodes.Assign)
                and isinstance(lookup_result[1][0].parent.value, nodes.Call)
            ):
                maybe_generator_call = lookup_result[1][0].parent.value
        return emit, maybe_generator_call

    def visit_module(self, _: nodes.Module) -> None:
        """Check module name, docstring and required arguments."""
        self.linter.stats.node_count["module"] += 1

    def visit_classdef(self, _: nodes.ClassDef) -> None:
        """Check module name, docstring and redefinition
        increment branch counter.
        """
        self.linter.stats.node_count["klass"] += 1

    @utils.only_required_for_messages(
        "pointless-statement",
        "pointless-exception-statement",
        "pointless-string-statement",
        "expression-not-assigned",
        "named-expr-without-context",
    )
    def visit_expr(self, node: nodes.Expr) -> None:
        """Check for various kind of statements without effect."""
        expr = node.value
        if isinstance(expr, nodes.Const) and isinstance(expr.value, str):
            # treat string statement in a separated message
            # Handle PEP-257 attribute docstrings.
            # An attribute docstring is defined as being a string right after
            # an assignment at the module level, class level or __init__ level.
            scope = expr.scope()
            if isinstance(scope, (nodes.ClassDef, nodes.Module, nodes.FunctionDef)):
                if isinstance(scope, nodes.FunctionDef) and scope.name != "__init__":
                    pass
                else:
                    sibling = expr.previous_sibling()
                    if (
                        sibling is not None
                        and sibling.scope() is scope
                        and isinstance(sibling, (nodes.Assign, nodes.AnnAssign))
                    ):
                        return
            self.add_message("pointless-string-statement", node=node)
            return

        # Warn W0133 for exceptions that are used as statements
        if isinstance(expr, nodes.Call):
            name = ""
            if isinstance(expr.func, nodes.Name):
                name = expr.func.name
            elif isinstance(expr.func, nodes.Attribute):
                name = expr.func.attrname

            # Heuristic: only run inference for names that begin with an uppercase char
            # This reduces W0133's coverage, but retains acceptable runtime performance
            # For more details, see: https://github.com/PyCQA/pylint/issues/8073
            inferred = utils.safe_infer(expr) if name[:1].isupper() else None
            if isinstance(inferred, objects.ExceptionInstance):
                self.add_message(
                    "pointless-exception-statement", node=node, confidence=INFERENCE
                )
            return

        # Ignore if this is :
        # * the unique child of a try/except body
        # * a yield statement
        # * an ellipsis (which can be used on Python 3 instead of pass)
        # warn W0106 if we have any underlying function call (we can't predict
        # side effects), else pointless-statement
        if (
            isinstance(expr, (nodes.Yield, nodes.Await))
            or (isinstance(node.parent, nodes.TryExcept) and node.parent.body == [node])
            or (isinstance(expr, nodes.Const) and expr.value is Ellipsis)
        ):
            return
        if isinstance(expr, nodes.NamedExpr):
            self.add_message("named-expr-without-context", node=node, confidence=HIGH)
        elif any(expr.nodes_of_class(nodes.Call)):
            self.add_message(
                "expression-not-assigned", node=node, args=expr.as_string()
            )
        else:
            self.add_message("pointless-statement", node=node)

    @staticmethod
    def _filter_vararg(
        node: nodes.Lambda, call_args: list[nodes.NodeNG]
    ) -> Iterator[nodes.NodeNG]:
        # Return the arguments for the given call which are
        # not passed as vararg.
        for arg in call_args:
            if isinstance(arg, nodes.Starred):
                if (
                    isinstance(arg.value, nodes.Name)
                    and arg.value.name != node.args.vararg
                ):
                    yield arg
            else:
                yield arg

    @staticmethod
    def _has_variadic_argument(
        args: list[nodes.Starred | nodes.Keyword], variadic_name: str
    ) -> bool:
        return not args or any(
            isinstance(a.value, nodes.Name)
            and a.value.name != variadic_name
            or not isinstance(a.value, nodes.Name)
            for a in args
        )

    @utils.only_required_for_messages("unnecessary-lambda")
    def visit_lambda(self, node: nodes.Lambda) -> None:
        """Check whether the lambda is suspicious."""
        # if the body of the lambda is a call expression with the same
        # argument list as the lambda itself, then the lambda is
        # possibly unnecessary and at least suspicious.
        if node.args.defaults:
            # If the arguments of the lambda include defaults, then a
            # judgment cannot be made because there is no way to check
            # that the defaults defined by the lambda are the same as
            # the defaults defined by the function called in the body
            # of the lambda.
            return
        call = node.body
        if not isinstance(call, nodes.Call):
            # The body of the lambda must be a function call expression
            # for the lambda to be unnecessary.
            return
        if isinstance(node.body.func, nodes.Attribute) and isinstance(
            node.body.func.expr, nodes.Call
        ):
            # Chained call, the intermediate call might
            # return something else (but we don't check that, yet).
            return

        call_site = astroid.arguments.CallSite.from_call(call)
        ordinary_args = list(node.args.args)
        new_call_args = list(self._filter_vararg(node, call.args))
        if node.args.kwarg:
            if self._has_variadic_argument(call.kwargs, node.args.kwarg):
                return

        if node.args.vararg:
            if self._has_variadic_argument(call.starargs, node.args.vararg):
                return
        elif call.starargs:
            return

        if call.keywords:
            # Look for additional keyword arguments that are not part
            # of the lambda's signature
            lambda_kwargs = {keyword.name for keyword in node.args.defaults}
            if len(lambda_kwargs) != len(call_site.keyword_arguments):
                # Different lengths, so probably not identical
                return
            if set(call_site.keyword_arguments).difference(lambda_kwargs):
                return

        # The "ordinary" arguments must be in a correspondence such that:
        # ordinary_args[i].name == call.args[i].name.
        if len(ordinary_args) != len(new_call_args):
            return
        for arg, passed_arg in zip(ordinary_args, new_call_args):
            if not isinstance(passed_arg, nodes.Name):
                return
            if arg.name != passed_arg.name:
                return

        self.add_message("unnecessary-lambda", line=node.fromlineno, node=node)

    @utils.only_required_for_messages("dangerous-default-value")
    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Check function name, docstring, arguments, redefinition,
        variable names, max locals.
        """
        if node.is_method():
            self.linter.stats.node_count["method"] += 1
        else:
            self.linter.stats.node_count["function"] += 1
        self._check_dangerous_default(node)

    visit_asyncfunctiondef = visit_functiondef

    def _check_dangerous_default(self, node: nodes.FunctionDef) -> None:
        """Check for dangerous default values as arguments."""

        def is_iterable(internal_node: nodes.NodeNG) -> bool:
            return isinstance(internal_node, (nodes.List, nodes.Set, nodes.Dict))

        defaults = (node.args.defaults or []) + (node.args.kw_defaults or [])
        for default in defaults:
            if not default:
                continue
            try:
                value = next(default.infer())
            except astroid.InferenceError:
                continue

            if (
                isinstance(value, astroid.Instance)
                and value.qname() in DEFAULT_ARGUMENT_SYMBOLS
            ):
                if value is default:
                    msg = DEFAULT_ARGUMENT_SYMBOLS[value.qname()]
                elif isinstance(value, astroid.Instance) or is_iterable(value):
                    # We are here in the following situation(s):
                    #   * a dict/set/list/tuple call which wasn't inferred
                    #     to a syntax node ({}, () etc.). This can happen
                    #     when the arguments are invalid or unknown to
                    #     the inference.
                    #   * a variable from somewhere else, which turns out to be a list
                    #     or a dict.
                    if is_iterable(default):
                        msg = value.pytype()
                    elif isinstance(default, nodes.Call):
                        msg = f"{value.name}() ({value.qname()})"
                    else:
                        msg = f"{default.as_string()} ({value.qname()})"
                else:
                    # this argument is a name
                    msg = f"{default.as_string()} ({DEFAULT_ARGUMENT_SYMBOLS[value.qname()]})"
                self.add_message("dangerous-default-value", node=node, args=(msg,))

    @utils.only_required_for_messages("unreachable", "lost-exception")
    def visit_return(self, node: nodes.Return) -> None:
        """Return node visitor.

        1 - check if the node has a right sibling (if so, that's some
        unreachable code)
        2 - check if the node is inside the 'finally' clause of a 'try...finally'
        block
        """
        self._check_unreachable(node)
        # Is it inside final body of a try...finally block ?
        self._check_not_in_finally(node, "return", (nodes.FunctionDef,))

    @utils.only_required_for_messages("unreachable")
    def visit_continue(self, node: nodes.Continue) -> None:
        """Check is the node has a right sibling (if so, that's some unreachable
        code).
        """
        self._check_unreachable(node)

    @utils.only_required_for_messages("unreachable", "lost-exception")
    def visit_break(self, node: nodes.Break) -> None:
        """Break node visitor.

        1 - check if the node has a right sibling (if so, that's some
        unreachable code)
        2 - check if the node is inside the 'finally' clause of a 'try...finally'
        block
        """
        # 1 - Is it right sibling ?
        self._check_unreachable(node)
        # 2 - Is it inside final body of a try...finally block ?
        self._check_not_in_finally(node, "break", (nodes.For, nodes.While))

    @utils.only_required_for_messages("unreachable")
    def visit_raise(self, node: nodes.Raise) -> None:
        """Check if the node has a right sibling (if so, that's some unreachable
        code).
        """
        self._check_unreachable(node)

    def _check_misplaced_format_function(self, call_node: nodes.Call) -> None:
        if not isinstance(call_node.func, nodes.Attribute):
            return
        if call_node.func.attrname != "format":
            return

        expr = utils.safe_infer(call_node.func.expr)
        if isinstance(expr, util.UninferableBase):
            return
        if not expr:
            # we are doubtful on inferred type of node, so here just check if format
            # was called on print()
            call_expr = call_node.func.expr
            if not isinstance(call_expr, nodes.Call):
                return
            if (
                isinstance(call_expr.func, nodes.Name)
                and call_expr.func.name == "print"
            ):
                self.add_message("misplaced-format-function", node=call_node)

    @utils.only_required_for_messages(
        "eval-used",
        "exec-used",
        "bad-reversed-sequence",
        "misplaced-format-function",
        "unreachable",
    )
    def visit_call(self, node: nodes.Call) -> None:
        """Visit a Call node."""
        if utils.is_terminating_func(node):
            self._check_unreachable(node, confidence=INFERENCE)
        self._check_misplaced_format_function(node)
        if isinstance(node.func, nodes.Name):
            name = node.func.name
            # ignore the name if it's not a builtin (i.e. not defined in the
            # locals nor globals scope)
            if not (name in node.frame(future=True) or name in node.root()):
                if name == "exec":
                    self.add_message("exec-used", node=node)
                elif name == "reversed":
                    self._check_reversed(node)
                elif name == "eval":
                    self.add_message("eval-used", node=node)

    @utils.only_required_for_messages("assert-on-tuple", "assert-on-string-literal")
    def visit_assert(self, node: nodes.Assert) -> None:
        """Check whether assert is used on a tuple or string literal."""
        if isinstance(node.test, nodes.Tuple) and len(node.test.elts) > 0:
            self.add_message("assert-on-tuple", node=node, confidence=HIGH)

        if isinstance(node.test, nodes.Const) and isinstance(node.test.value, str):
            if node.test.value:
                when = "never"
            else:
                when = "always"
            self.add_message("assert-on-string-literal", node=node, args=(when,))

    @utils.only_required_for_messages("duplicate-key")
    def visit_dict(self, node: nodes.Dict) -> None:
        """Check duplicate key in dictionary."""
        keys = set()
        for k, _ in node.items:
            if isinstance(k, nodes.Const):
                key = k.value
            elif isinstance(k, nodes.Attribute):
                key = k.as_string()
            else:
                continue
            if key in keys:
                self.add_message("duplicate-key", node=node, args=key)
            keys.add(key)

    @utils.only_required_for_messages("duplicate-value")
    def visit_set(self, node: nodes.Set) -> None:
        """Check duplicate value in set."""
        values = set()
        for v in node.elts:
            if isinstance(v, nodes.Const):
                value = v.value
            else:
                continue
            if value in values:
                self.add_message(
                    "duplicate-value", node=node, args=value, confidence=HIGH
                )
            values.add(value)

    def visit_tryfinally(self, node: nodes.TryFinally) -> None:
        """Update try...finally flag."""
        assert self._tryfinallys is not None
        self._tryfinallys.append(node)

    def leave_tryfinally(self, _: nodes.TryFinally) -> None:
        """Update try...finally flag."""
        assert self._tryfinallys is not None
        self._tryfinallys.pop()

    def _check_unreachable(
        self,
        node: nodes.Return | nodes.Continue | nodes.Break | nodes.Raise | nodes.Call,
        confidence: Confidence = HIGH,
    ) -> None:
        """Check unreachable code."""
        unreachable_statement = node.next_sibling()
        if unreachable_statement is not None:
            if (
                isinstance(node, nodes.Return)
                and isinstance(unreachable_statement, nodes.Expr)
                and isinstance(unreachable_statement.value, nodes.Yield)
            ):
                # Don't add 'unreachable' for empty generators.
                # Only add warning if 'yield' is followed by another node.
                unreachable_statement = unreachable_statement.next_sibling()
                if unreachable_statement is None:
                    return
            self.add_message(
                "unreachable", node=unreachable_statement, confidence=confidence
            )

    def _check_not_in_finally(
        self,
        node: nodes.Break | nodes.Return,
        node_name: str,
        breaker_classes: tuple[nodes.NodeNG, ...] = (),
    ) -> None:
        """Check that a node is not inside a 'finally' clause of a
        'try...finally' statement.

        If we find a parent which type is in breaker_classes before
        a 'try...finally' block we skip the whole check.
        """
        # if self._tryfinallys is empty, we're not an in try...finally block
        if not self._tryfinallys:
            return
        # the node could be a grand-grand...-child of the 'try...finally'
        _parent = node.parent
        _node = node
        while _parent and not isinstance(_parent, breaker_classes):
            if hasattr(_parent, "finalbody") and _node in _parent.finalbody:
                self.add_message("lost-exception", node=node, args=node_name)
                return
            _node = _parent
            _parent = _node.parent

    def _check_reversed(self, node: nodes.Call) -> None:
        """Check that the argument to `reversed` is a sequence."""
        try:
            argument = utils.safe_infer(utils.get_argument_from_call(node, position=0))
        except utils.NoSuchArgumentError:
            pass
        else:
            if isinstance(argument, util.UninferableBase):
                return
            if argument is None:
                # Nothing was inferred.
                # Try to see if we have iter().
                if isinstance(node.args[0], nodes.Call):
                    try:
                        func = next(node.args[0].func.infer())
                    except astroid.InferenceError:
                        return
                    if getattr(
                        func, "name", None
                    ) == "iter" and utils.is_builtin_object(func):
                        self.add_message("bad-reversed-sequence", node=node)
                return

            if isinstance(argument, (nodes.List, nodes.Tuple)):
                return

            # dicts are reversible, but only from Python 3.8 onward. Prior to
            # that, any class based on dict must explicitly provide a
            # __reversed__ method
            if not self._py38_plus and isinstance(argument, astroid.Instance):
                if any(
                    ancestor.name == "dict" and utils.is_builtin_object(ancestor)
                    for ancestor in itertools.chain(
                        (argument._proxied,), argument._proxied.ancestors()
                    )
                ):
                    try:
                        argument.locals[REVERSED_PROTOCOL_METHOD]
                    except KeyError:
                        self.add_message("bad-reversed-sequence", node=node)
                    return

            if hasattr(argument, "getattr"):
                # everything else is not a proper sequence for reversed()
                for methods in REVERSED_METHODS:
                    for meth in methods:
                        try:
                            argument.getattr(meth)
                        except astroid.NotFoundError:
                            break
                    else:
                        break
                else:
                    self.add_message("bad-reversed-sequence", node=node)
            else:
                self.add_message("bad-reversed-sequence", node=node)

    @utils.only_required_for_messages("confusing-with-statement")
    def visit_with(self, node: nodes.With) -> None:
        # a "with" statement with multiple managers corresponds
        # to one AST "With" node with multiple items
        pairs = node.items
        if pairs:
            for prev_pair, pair in zip(pairs, pairs[1:]):
                if isinstance(prev_pair[1], nodes.AssignName) and (
                    pair[1] is None and not isinstance(pair[0], nodes.Call)
                ):
                    # Don't emit a message if the second is a function call
                    # there's no way that can be mistaken for a name assignment.
                    # If the line number doesn't match
                    # we assume it's a nested "with".
                    self.add_message("confusing-with-statement", node=node)

    def _check_self_assigning_variable(self, node: nodes.Assign) -> None:
        # Detect assigning to the same variable.

        scope = node.scope()
        scope_locals = scope.locals

        rhs_names = []
        targets = node.targets
        if isinstance(targets[0], nodes.Tuple):
            if len(targets) != 1:
                # A complex assignment, so bail out early.
                return
            targets = targets[0].elts
            if len(targets) == 1:
                # Unpacking a variable into the same name.
                return

        if isinstance(node.value, nodes.Name):
            if len(targets) != 1:
                return
            rhs_names = [node.value]
        elif isinstance(node.value, nodes.Tuple):
            rhs_count = len(node.value.elts)
            if len(targets) != rhs_count or rhs_count == 1:
                return
            rhs_names = node.value.elts

        for target, lhs_name in zip(targets, rhs_names):
            if not isinstance(lhs_name, nodes.Name):
                continue
            if not isinstance(target, nodes.AssignName):
                continue
            # Check that the scope is different from a class level, which is usually
            # a pattern to expose module level attributes as class level ones.
            if isinstance(scope, nodes.ClassDef) and target.name in scope_locals:
                continue
            if target.name == lhs_name.name:
                self.add_message(
                    "self-assigning-variable", args=(target.name,), node=target
                )

    def _check_redeclared_assign_name(self, targets: list[nodes.NodeNG | None]) -> None:
        dummy_variables_rgx = self.linter.config.dummy_variables_rgx

        for target in targets:
            if not isinstance(target, nodes.Tuple):
                continue

            found_names = []
            for element in target.elts:
                if isinstance(element, nodes.Tuple):
                    self._check_redeclared_assign_name([element])
                elif isinstance(element, nodes.AssignName) and element.name != "_":
                    if dummy_variables_rgx and dummy_variables_rgx.match(element.name):
                        return
                    found_names.append(element.name)

            names = collections.Counter(found_names)
            for name, count in names.most_common():
                if count > 1:
                    self.add_message(
                        "redeclared-assigned-name", args=(name,), node=target
                    )

    @utils.only_required_for_messages(
        "self-assigning-variable", "redeclared-assigned-name"
    )
    def visit_assign(self, node: nodes.Assign) -> None:
        self._check_self_assigning_variable(node)
        self._check_redeclared_assign_name(node.targets)

    @utils.only_required_for_messages("redeclared-assigned-name")
    def visit_for(self, node: nodes.For) -> None:
        self._check_redeclared_assign_name([node.target])
