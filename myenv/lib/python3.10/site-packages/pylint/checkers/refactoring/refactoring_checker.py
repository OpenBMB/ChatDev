# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import collections
import copy
import itertools
import sys
import tokenize
from collections.abc import Iterator
from functools import reduce
from re import Pattern
from typing import TYPE_CHECKING, Any, NamedTuple, Union, cast

import astroid
from astroid import bases, nodes
from astroid.util import UninferableBase

from pylint import checkers
from pylint.checkers import utils
from pylint.checkers.base.basic_error_checker import _loop_exits_early
from pylint.checkers.utils import node_frame_class
from pylint.interfaces import HIGH, INFERENCE, Confidence

if TYPE_CHECKING:
    from pylint.lint import PyLinter

if sys.version_info >= (3, 8):
    from functools import cached_property
else:
    from astroid.decorators import cachedproperty as cached_property

NodesWithNestedBlocks = Union[
    nodes.TryExcept, nodes.TryFinally, nodes.While, nodes.For, nodes.If
]

KNOWN_INFINITE_ITERATORS = {"itertools.count", "itertools.cycle"}
BUILTIN_EXIT_FUNCS = frozenset(("quit", "exit"))
CALLS_THAT_COULD_BE_REPLACED_BY_WITH = frozenset(
    (
        "threading.lock.acquire",
        "threading._RLock.acquire",
        "threading.Semaphore.acquire",
        "multiprocessing.managers.BaseManager.start",
        "multiprocessing.managers.SyncManager.start",
    )
)
CALLS_RETURNING_CONTEXT_MANAGERS = frozenset(
    (
        "_io.open",  # regular 'open()' call
        "pathlib.Path.open",
        "codecs.open",
        "urllib.request.urlopen",
        "tempfile.NamedTemporaryFile",
        "tempfile.SpooledTemporaryFile",
        "tempfile.TemporaryDirectory",
        "tempfile.TemporaryFile",
        "zipfile.ZipFile",
        "zipfile.PyZipFile",
        "zipfile.ZipFile.open",
        "zipfile.PyZipFile.open",
        "tarfile.TarFile",
        "tarfile.TarFile.open",
        "multiprocessing.context.BaseContext.Pool",
        "subprocess.Popen",
    )
)


def _if_statement_is_always_returning(
    if_node: nodes.If, returning_node_class: nodes.NodeNG
) -> bool:
    return any(isinstance(node, returning_node_class) for node in if_node.body)


def _except_statement_is_always_returning(
    node: nodes.TryExcept, returning_node_class: nodes.NodeNG
) -> bool:
    """Detect if all except statements return."""
    return all(
        any(isinstance(child, returning_node_class) for child in handler.body)
        for handler in node.handlers
    )


def _is_trailing_comma(tokens: list[tokenize.TokenInfo], index: int) -> bool:
    """Check if the given token is a trailing comma.

    :param tokens: Sequence of modules tokens
    :type tokens: list[tokenize.TokenInfo]
    :param int index: Index of token under check in tokens
    :returns: True if the token is a comma which trails an expression
    :rtype: bool
    """
    token = tokens[index]
    if token.exact_type != tokenize.COMMA:
        return False
    # Must have remaining tokens on the same line such as NEWLINE
    left_tokens = list(itertools.islice(tokens, index + 1, None))

    more_tokens_on_line = False
    for remaining_token in left_tokens:
        if remaining_token.start[0] == token.start[0]:
            more_tokens_on_line = True
            # If one of the remaining same line tokens is not NEWLINE or COMMENT
            # the comma is not trailing.
            if remaining_token.type not in (tokenize.NEWLINE, tokenize.COMMENT):
                return False

    if not more_tokens_on_line:
        return False

    def get_curline_index_start() -> int:
        """Get the index denoting the start of the current line."""
        for subindex, token in enumerate(reversed(tokens[:index])):
            # See Lib/tokenize.py and Lib/token.py in cpython for more info
            if token.type == tokenize.NEWLINE:
                return index - subindex
        return 0

    curline_start = get_curline_index_start()
    expected_tokens = {"return", "yield"}
    return any(
        "=" in prevtoken.string or prevtoken.string in expected_tokens
        for prevtoken in tokens[curline_start:index]
    )


def _is_inside_context_manager(node: nodes.Call) -> bool:
    frame = node.frame(future=True)
    if not isinstance(
        frame, (nodes.FunctionDef, astroid.BoundMethod, astroid.UnboundMethod)
    ):
        return False
    return frame.name == "__enter__" or utils.decorated_with(
        frame, "contextlib.contextmanager"
    )


def _is_a_return_statement(node: nodes.Call) -> bool:
    frame = node.frame(future=True)
    for parent in node.node_ancestors():
        if parent is frame:
            break
        if isinstance(parent, nodes.Return):
            return True
    return False


def _is_part_of_with_items(node: nodes.Call) -> bool:
    """Checks if one of the node's parents is a ``nodes.With`` node and that the node
    itself is located somewhere under its ``items``.
    """
    frame = node.frame(future=True)
    current = node
    while current != frame:
        if isinstance(current, nodes.With):
            items_start = current.items[0][0].lineno
            items_end = current.items[-1][0].tolineno
            return items_start <= node.lineno <= items_end  # type: ignore[no-any-return]
        current = current.parent
    return False


def _will_be_released_automatically(node: nodes.Call) -> bool:
    """Checks if a call that could be used in a ``with`` statement is used in an
    alternative construct which would ensure that its __exit__ method is called.
    """
    callables_taking_care_of_exit = frozenset(
        (
            "contextlib._BaseExitStack.enter_context",
            "contextlib.ExitStack.enter_context",  # necessary for Python 3.6 compatibility
        )
    )
    if not isinstance(node.parent, nodes.Call):
        return False
    func = utils.safe_infer(node.parent.func)
    if not func:
        return False
    return func.qname() in callables_taking_care_of_exit


def _is_part_of_assignment_target(node: nodes.NodeNG) -> bool:
    """Check whether use of a variable is happening as part of the left-hand
    side of an assignment.

    This requires recursive checking, because destructuring assignment can have
    arbitrarily nested tuples and lists to unpack.
    """
    if isinstance(node.parent, nodes.Assign):
        return node in node.parent.targets

    if isinstance(node.parent, nodes.AugAssign):
        return node == node.parent.target  # type: ignore[no-any-return]

    if isinstance(node.parent, (nodes.Tuple, nodes.List)):
        return _is_part_of_assignment_target(node.parent)

    return False


class ConsiderUsingWithStack(NamedTuple):
    """Stack for objects that may potentially trigger a R1732 message
    if they are not used in a ``with`` block later on.
    """

    module_scope: dict[str, nodes.NodeNG] = {}
    class_scope: dict[str, nodes.NodeNG] = {}
    function_scope: dict[str, nodes.NodeNG] = {}

    def __iter__(self) -> Iterator[dict[str, nodes.NodeNG]]:
        yield from (self.function_scope, self.class_scope, self.module_scope)

    def get_stack_for_frame(
        self, frame: nodes.FunctionDef | nodes.ClassDef | nodes.Module
    ) -> dict[str, nodes.NodeNG]:
        """Get the stack corresponding to the scope of the given frame."""
        if isinstance(frame, nodes.FunctionDef):
            return self.function_scope
        if isinstance(frame, nodes.ClassDef):
            return self.class_scope
        return self.module_scope

    def clear_all(self) -> None:
        """Convenience method to clear all stacks."""
        for stack in self:
            stack.clear()


class RefactoringChecker(checkers.BaseTokenChecker):
    """Looks for code which can be refactored.

    This checker also mixes the astroid and the token approaches
    in order to create knowledge about whether an "else if" node
    is a true "else if" node, or an "elif" node.
    """

    name = "refactoring"

    msgs = {
        "R1701": (
            "Consider merging these isinstance calls to isinstance(%s, (%s))",
            "consider-merging-isinstance",
            "Used when multiple consecutive isinstance calls can be merged into one.",
        ),
        "R1706": (
            "Consider using ternary (%s)",
            "consider-using-ternary",
            "Used when one of known pre-python 2.5 ternary syntax is used.",
        ),
        "R1709": (
            "Boolean expression may be simplified to %s",
            "simplify-boolean-expression",
            "Emitted when redundant pre-python 2.5 ternary syntax is used.",
        ),
        "R1726": (
            "Boolean condition '%s' may be simplified to '%s'",
            "simplifiable-condition",
            "Emitted when a boolean condition is able to be simplified.",
        ),
        "R1727": (
            "Boolean condition '%s' will always evaluate to '%s'",
            "condition-evals-to-constant",
            "Emitted when a boolean condition can be simplified to a constant value.",
        ),
        "R1702": (
            "Too many nested blocks (%s/%s)",
            "too-many-nested-blocks",
            "Used when a function or a method has too many nested "
            "blocks. This makes the code less understandable and "
            "maintainable.",
            {"old_names": [("R0101", "old-too-many-nested-blocks")]},
        ),
        "R1703": (
            "The if statement can be replaced with %s",
            "simplifiable-if-statement",
            "Used when an if statement can be replaced with 'bool(test)'.",
            {"old_names": [("R0102", "old-simplifiable-if-statement")]},
        ),
        "R1704": (
            "Redefining argument with the local name %r",
            "redefined-argument-from-local",
            "Used when a local name is redefining an argument, which might "
            "suggest a potential error. This is taken in account only for "
            "a handful of name binding operations, such as for iteration, "
            "with statement assignment and exception handler assignment.",
        ),
        "R1705": (
            'Unnecessary "%s" after "return", %s',
            "no-else-return",
            "Used in order to highlight an unnecessary block of "
            "code following an if containing a return statement. "
            "As such, it will warn when it encounters an else "
            "following a chain of ifs, all of them containing a "
            "return statement.",
        ),
        "R1707": (
            "Disallow trailing comma tuple",
            "trailing-comma-tuple",
            "In Python, a tuple is actually created by the comma symbol, "
            "not by the parentheses. Unfortunately, one can actually create a "
            "tuple by misplacing a trailing comma, which can lead to potential "
            "weird bugs in your code. You should always use parentheses "
            "explicitly for creating a tuple.",
        ),
        "R1708": (
            "Do not raise StopIteration in generator, use return statement instead",
            "stop-iteration-return",
            "According to PEP479, the raise of StopIteration to end the loop of "
            "a generator may lead to hard to find bugs. This PEP specify that "
            "raise StopIteration has to be replaced by a simple return statement",
        ),
        "R1710": (
            "Either all return statements in a function should return an expression, "
            "or none of them should.",
            "inconsistent-return-statements",
            "According to PEP8, if any return statement returns an expression, "
            "any return statements where no value is returned should explicitly "
            "state this as return None, and an explicit return statement "
            "should be present at the end of the function (if reachable)",
        ),
        "R1711": (
            "Useless return at end of function or method",
            "useless-return",
            'Emitted when a single "return" or "return None" statement is found '
            "at the end of function or method definition. This statement can safely be "
            "removed because Python will implicitly return None",
        ),
        "R1712": (
            "Consider using tuple unpacking for swapping variables",
            "consider-swap-variables",
            "You do not have to use a temporary variable in order to "
            'swap variables. Using "tuple unpacking" to directly swap '
            "variables makes the intention more clear.",
        ),
        "R1713": (
            "Consider using str.join(sequence) for concatenating "
            "strings from an iterable",
            "consider-using-join",
            "Using str.join(sequence) is faster, uses less memory "
            "and increases readability compared to for-loop iteration.",
        ),
        "R1714": (
            "Consider merging these comparisons with 'in' by using '%s %sin (%s)'."
            " Use a set instead if elements are hashable.",
            "consider-using-in",
            "To check if a variable is equal to one of many values, "
            'combine the values into a set or tuple and check if the variable is contained "in" it '
            "instead of checking for equality against each of the values. "
            "This is faster and less verbose.",
        ),
        "R1715": (
            "Consider using dict.get for getting values from a dict "
            "if a key is present or a default if not",
            "consider-using-get",
            "Using the builtin dict.get for getting a value from a dictionary "
            "if a key is present or a default if not, is simpler and considered "
            "more idiomatic, although sometimes a bit slower",
        ),
        "R1716": (
            "Simplify chained comparison between the operands",
            "chained-comparison",
            "This message is emitted when pylint encounters boolean operation like "
            '"a < b and b < c", suggesting instead to refactor it to "a < b < c"',
        ),
        "R1717": (
            "Consider using a dictionary comprehension",
            "consider-using-dict-comprehension",
            "Emitted when we detect the creation of a dictionary "
            "using the dict() callable and a transient list. "
            "Although there is nothing syntactically wrong with this code, "
            "it is hard to read and can be simplified to a dict comprehension. "
            "Also it is faster since you don't need to create another "
            "transient list",
        ),
        "R1718": (
            "Consider using a set comprehension",
            "consider-using-set-comprehension",
            "Although there is nothing syntactically wrong with this code, "
            "it is hard to read and can be simplified to a set comprehension. "
            "Also it is faster since you don't need to create another "
            "transient list",
        ),
        "R1719": (
            "The if expression can be replaced with %s",
            "simplifiable-if-expression",
            "Used when an if expression can be replaced with 'bool(test)' "
            "or simply 'test' if the boolean cast is implicit.",
        ),
        "R1720": (
            'Unnecessary "%s" after "raise", %s',
            "no-else-raise",
            "Used in order to highlight an unnecessary block of "
            "code following an if containing a raise statement. "
            "As such, it will warn when it encounters an else "
            "following a chain of ifs, all of them containing a "
            "raise statement.",
        ),
        "R1721": (
            "Unnecessary use of a comprehension, use %s instead.",
            "unnecessary-comprehension",
            "Instead of using an identity comprehension, "
            "consider using the list, dict or set constructor. "
            "It is faster and simpler.",
        ),
        "R1722": (
            "Consider using 'sys.exit' instead",
            "consider-using-sys-exit",
            "Contrary to 'exit()' or 'quit()', 'sys.exit' does not rely on the "
            "site module being available (as the 'sys' module is always available).",
        ),
        "R1723": (
            'Unnecessary "%s" after "break", %s',
            "no-else-break",
            "Used in order to highlight an unnecessary block of "
            "code following an if containing a break statement. "
            "As such, it will warn when it encounters an else "
            "following a chain of ifs, all of them containing a "
            "break statement.",
        ),
        "R1724": (
            'Unnecessary "%s" after "continue", %s',
            "no-else-continue",
            "Used in order to highlight an unnecessary block of "
            "code following an if containing a continue statement. "
            "As such, it will warn when it encounters an else "
            "following a chain of ifs, all of them containing a "
            "continue statement.",
        ),
        "R1725": (
            "Consider using Python 3 style super() without arguments",
            "super-with-arguments",
            "Emitted when calling the super() builtin with the current class "
            "and instance. On Python 3 these arguments are the default and they can be omitted.",
        ),
        "R1728": (
            "Consider using a generator instead '%s(%s)'",
            "consider-using-generator",
            "If your container can be large using "
            "a generator will bring better performance.",
        ),
        "R1729": (
            "Use a generator instead '%s(%s)'",
            "use-a-generator",
            "Comprehension inside of 'any', 'all', 'max', 'min' or 'sum' is unnecessary. "
            "A generator would be sufficient and faster.",
        ),
        "R1730": (
            "Consider using '%s' instead of unnecessary if block",
            "consider-using-min-builtin",
            "Using the min builtin instead of a conditional improves readability and conciseness.",
        ),
        "R1731": (
            "Consider using '%s' instead of unnecessary if block",
            "consider-using-max-builtin",
            "Using the max builtin instead of a conditional improves readability and conciseness.",
        ),
        "R1732": (
            "Consider using 'with' for resource-allocating operations",
            "consider-using-with",
            "Emitted if a resource-allocating assignment or call may be replaced by a 'with' block. "
            "By using 'with' the release of the allocated resources is ensured even in the case "
            "of an exception.",
        ),
        "R1733": (
            "Unnecessary dictionary index lookup, use '%s' instead",
            "unnecessary-dict-index-lookup",
            "Emitted when iterating over the dictionary items (key-item pairs) and accessing the "
            "value by index lookup. "
            "The value can be accessed directly instead.",
        ),
        "R1734": (
            "Consider using [] instead of list()",
            "use-list-literal",
            "Emitted when using list() to create an empty list instead of the literal []. "
            "The literal is faster as it avoids an additional function call.",
        ),
        "R1735": (
            "Consider using '%s' instead of a call to 'dict'.",
            "use-dict-literal",
            "Emitted when using dict() to create a dictionary instead of a literal '{ ... }'. "
            "The literal is faster as it avoids an additional function call.",
        ),
        "R1736": (
            "Unnecessary list index lookup, use '%s' instead",
            "unnecessary-list-index-lookup",
            "Emitted when iterating over an enumeration and accessing the "
            "value by index lookup. "
            "The value can be accessed directly instead.",
        ),
    }
    options = (
        (
            "max-nested-blocks",
            {
                "default": 5,
                "type": "int",
                "metavar": "<int>",
                "help": "Maximum number of nested blocks for function / method body",
            },
        ),
        (
            "never-returning-functions",
            {
                "default": ("sys.exit", "argparse.parse_error"),
                "type": "csv",
                "metavar": "<members names>",
                "help": "Complete name of functions that never returns. When checking "
                "for inconsistent-return-statements if a never returning function is "
                "called then it will be considered as an explicit return statement "
                "and no message will be printed.",
            },
        ),
    )

    def __init__(self, linter: PyLinter) -> None:
        super().__init__(linter)
        self._return_nodes: dict[str, list[nodes.Return]] = {}
        self._consider_using_with_stack = ConsiderUsingWithStack()
        self._init()
        self._never_returning_functions: set[str] = set()

    def _init(self) -> None:
        self._nested_blocks: list[NodesWithNestedBlocks] = []
        self._elifs: list[tuple[int, int]] = []
        self._reported_swap_nodes: set[nodes.NodeNG] = set()
        self._can_simplify_bool_op: bool = False
        self._consider_using_with_stack.clear_all()

    def open(self) -> None:
        # do this in open since config not fully initialized in __init__
        self._never_returning_functions = set(
            self.linter.config.never_returning_functions
        )

    @cached_property
    def _dummy_rgx(self) -> Pattern[str]:
        return self.linter.config.dummy_variables_rgx  # type: ignore[no-any-return]

    @staticmethod
    def _is_bool_const(node: nodes.Return | nodes.Assign) -> bool:
        return isinstance(node.value, nodes.Const) and isinstance(
            node.value.value, bool
        )

    def _is_actual_elif(self, node: nodes.If | nodes.TryExcept) -> bool:
        """Check if the given node is an actual elif.

        This is a problem we're having with the builtin ast module,
        which splits `elif` branches into a separate if statement.
        Unfortunately we need to know the exact type in certain
        cases.
        """
        if isinstance(node.parent, nodes.If):
            orelse = node.parent.orelse
            # current if node must directly follow an "else"
            if orelse and orelse == [node]:
                if (node.lineno, node.col_offset) in self._elifs:
                    return True
        return False

    def _check_simplifiable_if(self, node: nodes.If) -> None:
        """Check if the given if node can be simplified.

        The if statement can be reduced to a boolean expression
        in some cases. For instance, if there are two branches
        and both of them return a boolean value that depends on
        the result of the statement's test, then this can be reduced
        to `bool(test)` without losing any functionality.
        """

        if self._is_actual_elif(node):
            # Not interested in if statements with multiple branches.
            return
        if len(node.orelse) != 1 or len(node.body) != 1:
            return

        # Check if both branches can be reduced.
        first_branch = node.body[0]
        else_branch = node.orelse[0]
        if isinstance(first_branch, nodes.Return):
            if not isinstance(else_branch, nodes.Return):
                return
            first_branch_is_bool = self._is_bool_const(first_branch)
            else_branch_is_bool = self._is_bool_const(else_branch)
            reduced_to = "'return bool(test)'"
        elif isinstance(first_branch, nodes.Assign):
            if not isinstance(else_branch, nodes.Assign):
                return

            # Check if we assign to the same value
            first_branch_targets = [
                target.name
                for target in first_branch.targets
                if isinstance(target, nodes.AssignName)
            ]
            else_branch_targets = [
                target.name
                for target in else_branch.targets
                if isinstance(target, nodes.AssignName)
            ]
            if not first_branch_targets or not else_branch_targets:
                return
            if sorted(first_branch_targets) != sorted(else_branch_targets):
                return

            first_branch_is_bool = self._is_bool_const(first_branch)
            else_branch_is_bool = self._is_bool_const(else_branch)
            reduced_to = "'var = bool(test)'"
        else:
            return

        if not first_branch_is_bool or not else_branch_is_bool:
            return
        if not first_branch.value.value:
            # This is a case that can't be easily simplified and
            # if it can be simplified, it will usually result in a
            # code that's harder to understand and comprehend.
            # Let's take for instance `arg and arg <= 3`. This could theoretically be
            # reduced to `not arg or arg > 3`, but the net result is that now the
            # condition is harder to understand, because it requires understanding of
            # an extra clause:
            #   * first, there is the negation of truthness with `not arg`
            #   * the second clause is `arg > 3`, which occurs when arg has a
            #     a truth value, but it implies that `arg > 3` is equivalent
            #     with `arg and arg > 3`, which means that the user must
            #     think about this assumption when evaluating `arg > 3`.
            #     The original form is easier to grasp.
            return

        self.add_message("simplifiable-if-statement", node=node, args=(reduced_to,))

    def process_tokens(self, tokens: list[tokenize.TokenInfo]) -> None:
        # Process tokens and look for 'if' or 'elif'
        for index, token in enumerate(tokens):
            token_string = token[1]
            if token_string == "elif":
                # AST exists by the time process_tokens is called, so
                # it's safe to assume tokens[index+1] exists.
                # tokens[index+1][2] is the elif's position as
                # reported by CPython and PyPy,
                # token[2] is the actual position and also is
                # reported by IronPython.
                self._elifs.extend([token[2], tokens[index + 1][2]])
            elif _is_trailing_comma(tokens, index):
                if self.linter.is_message_enabled("trailing-comma-tuple"):
                    self.add_message("trailing-comma-tuple", line=token.start[0])

    @utils.only_required_for_messages("consider-using-with")
    def leave_module(self, _: nodes.Module) -> None:
        # check for context managers that have been created but not used
        self._emit_consider_using_with_if_needed(
            self._consider_using_with_stack.module_scope
        )
        self._init()

    @utils.only_required_for_messages("too-many-nested-blocks", "no-else-return")
    def visit_tryexcept(self, node: nodes.TryExcept | nodes.TryFinally) -> None:
        self._check_nested_blocks(node)

        if isinstance(node, nodes.TryExcept):
            self._check_superfluous_else_return(node)
            self._check_superfluous_else_raise(node)

    visit_tryfinally = visit_tryexcept
    visit_while = visit_tryexcept

    def _check_redefined_argument_from_local(self, name_node: nodes.AssignName) -> None:
        if self._dummy_rgx and self._dummy_rgx.match(name_node.name):
            return
        if not name_node.lineno:
            # Unknown position, maybe it is a manually built AST?
            return

        scope = name_node.scope()
        if not isinstance(scope, nodes.FunctionDef):
            return

        for defined_argument in scope.args.nodes_of_class(
            nodes.AssignName, skip_klass=(nodes.Lambda,)
        ):
            if defined_argument.name == name_node.name:
                self.add_message(
                    "redefined-argument-from-local",
                    node=name_node,
                    args=(name_node.name,),
                )

    @utils.only_required_for_messages(
        "redefined-argument-from-local",
        "too-many-nested-blocks",
        "unnecessary-dict-index-lookup",
        "unnecessary-list-index-lookup",
    )
    def visit_for(self, node: nodes.For) -> None:
        self._check_nested_blocks(node)
        self._check_unnecessary_dict_index_lookup(node)
        self._check_unnecessary_list_index_lookup(node)

        for name in node.target.nodes_of_class(nodes.AssignName):
            self._check_redefined_argument_from_local(name)

    @utils.only_required_for_messages("redefined-argument-from-local")
    def visit_excepthandler(self, node: nodes.ExceptHandler) -> None:
        if node.name and isinstance(node.name, nodes.AssignName):
            self._check_redefined_argument_from_local(node.name)

    @utils.only_required_for_messages(
        "redefined-argument-from-local", "consider-using-with"
    )
    def visit_with(self, node: nodes.With) -> None:
        for var, names in node.items:
            if isinstance(var, nodes.Name):
                for stack in self._consider_using_with_stack:
                    # We don't need to restrict the stacks we search to the current scope and
                    # outer scopes, as e.g. the function_scope stack will be empty when we
                    # check a ``with`` on the class level.
                    if var.name in stack:
                        del stack[var.name]
                        break
            if not names:
                continue
            for name in names.nodes_of_class(nodes.AssignName):
                self._check_redefined_argument_from_local(name)

    def _check_superfluous_else(
        self,
        node: nodes.If | nodes.TryExcept,
        msg_id: str,
        returning_node_class: nodes.NodeNG,
    ) -> None:
        if isinstance(node, nodes.TryExcept) and isinstance(
            node.parent, nodes.TryFinally
        ):
            # Not interested in try/except/else/finally statements.
            return

        if not node.orelse:
            # Not interested in if/try statements without else.
            return

        if self._is_actual_elif(node):
            # Not interested in elif nodes; only if
            return

        if (
            isinstance(node, nodes.If)
            and _if_statement_is_always_returning(node, returning_node_class)
        ) or (
            isinstance(node, nodes.TryExcept)
            and _except_statement_is_always_returning(node, returning_node_class)
        ):
            orelse = node.orelse[0]
            if (orelse.lineno, orelse.col_offset) in self._elifs:
                args = ("elif", 'remove the leading "el" from "elif"')
            else:
                args = ("else", 'remove the "else" and de-indent the code inside it')
            self.add_message(msg_id, node=node, args=args, confidence=HIGH)

    def _check_superfluous_else_return(self, node: nodes.If) -> None:
        return self._check_superfluous_else(
            node, msg_id="no-else-return", returning_node_class=nodes.Return
        )

    def _check_superfluous_else_raise(self, node: nodes.If) -> None:
        return self._check_superfluous_else(
            node, msg_id="no-else-raise", returning_node_class=nodes.Raise
        )

    def _check_superfluous_else_break(self, node: nodes.If) -> None:
        return self._check_superfluous_else(
            node, msg_id="no-else-break", returning_node_class=nodes.Break
        )

    def _check_superfluous_else_continue(self, node: nodes.If) -> None:
        return self._check_superfluous_else(
            node, msg_id="no-else-continue", returning_node_class=nodes.Continue
        )

    @staticmethod
    def _type_and_name_are_equal(node_a: Any, node_b: Any) -> bool:
        if isinstance(node_a, nodes.Name) and isinstance(node_b, nodes.Name):
            return node_a.name == node_b.name  # type: ignore[no-any-return]
        if isinstance(node_a, nodes.AssignName) and isinstance(
            node_b, nodes.AssignName
        ):
            return node_a.name == node_b.name  # type: ignore[no-any-return]
        if isinstance(node_a, nodes.Const) and isinstance(node_b, nodes.Const):
            return node_a.value == node_b.value  # type: ignore[no-any-return]
        return False

    def _is_dict_get_block(self, node: nodes.If) -> bool:
        # "if <compare node>"
        if not isinstance(node.test, nodes.Compare):
            return False

        # Does not have a single statement in the guard's body
        if len(node.body) != 1:
            return False

        # Look for a single variable assignment on the LHS and a subscript on RHS
        stmt = node.body[0]
        if not (
            isinstance(stmt, nodes.Assign)
            and len(node.body[0].targets) == 1
            and isinstance(node.body[0].targets[0], nodes.AssignName)
            and isinstance(stmt.value, nodes.Subscript)
        ):
            return False

        # The subscript's slice needs to be the same as the test variable.
        slice_value = stmt.value.slice
        if not (
            self._type_and_name_are_equal(stmt.value.value, node.test.ops[0][1])
            and self._type_and_name_are_equal(slice_value, node.test.left)
        ):
            return False

        # The object needs to be a dictionary instance
        return isinstance(utils.safe_infer(node.test.ops[0][1]), nodes.Dict)

    def _check_consider_get(self, node: nodes.If) -> None:
        if_block_ok = self._is_dict_get_block(node)
        if if_block_ok and not node.orelse:
            self.add_message("consider-using-get", node=node)
        elif (
            if_block_ok
            and len(node.orelse) == 1
            and isinstance(node.orelse[0], nodes.Assign)
            and self._type_and_name_are_equal(
                node.orelse[0].targets[0], node.body[0].targets[0]
            )
            and len(node.orelse[0].targets) == 1
        ):
            self.add_message("consider-using-get", node=node)

    @utils.only_required_for_messages(
        "too-many-nested-blocks",
        "simplifiable-if-statement",
        "no-else-return",
        "no-else-raise",
        "no-else-break",
        "no-else-continue",
        "consider-using-get",
        "consider-using-min-builtin",
        "consider-using-max-builtin",
    )
    def visit_if(self, node: nodes.If) -> None:
        self._check_simplifiable_if(node)
        self._check_nested_blocks(node)
        self._check_superfluous_else_return(node)
        self._check_superfluous_else_raise(node)
        self._check_superfluous_else_break(node)
        self._check_superfluous_else_continue(node)
        self._check_consider_get(node)
        self._check_consider_using_min_max_builtin(node)

    # pylint: disable = too-many-branches
    def _check_consider_using_min_max_builtin(self, node: nodes.If) -> None:
        """Check if the given if node can be refactored as a min/max python builtin."""
        if self._is_actual_elif(node) or node.orelse:
            # Not interested in if statements with multiple branches.
            return

        if len(node.body) != 1:
            return

        body = node.body[0]
        # Check if condition can be reduced.
        if not hasattr(body, "targets") or len(body.targets) != 1:
            return

        target = body.targets[0]
        if not (
            isinstance(node.test, nodes.Compare)
            and not isinstance(target, nodes.Subscript)
            and not isinstance(node.test.left, nodes.Subscript)
            and isinstance(body, nodes.Assign)
        ):
            return

        # Check that the assignation is on the same variable.
        if hasattr(node.test.left, "name"):
            left_operand = node.test.left.name
        elif hasattr(node.test.left, "attrname"):
            left_operand = node.test.left.attrname
        else:
            return

        if hasattr(target, "name"):
            target_assignation = target.name
        elif hasattr(target, "attrname"):
            target_assignation = target.attrname
        else:
            return

        if not (left_operand == target_assignation):
            return

        if len(node.test.ops) > 1:
            return

        if not isinstance(body.value, (nodes.Name, nodes.Const)):
            return

        operator, right_statement = node.test.ops[0]
        if isinstance(body.value, nodes.Name):
            body_value = body.value.name
        else:
            body_value = body.value.value

        if isinstance(right_statement, nodes.Name):
            right_statement_value = right_statement.name
        elif isinstance(right_statement, nodes.Const):
            right_statement_value = right_statement.value
        else:
            return

        # Verify the right part of the statement is the same.
        if right_statement_value != body_value:
            return

        if operator in {"<", "<="}:
            reduced_to = "{target} = max({target}, {item})".format(
                target=target_assignation, item=body_value
            )
            self.add_message(
                "consider-using-max-builtin", node=node, args=(reduced_to,)
            )
        elif operator in {">", ">="}:
            reduced_to = "{target} = min({target}, {item})".format(
                target=target_assignation, item=body_value
            )
            self.add_message(
                "consider-using-min-builtin", node=node, args=(reduced_to,)
            )

    @utils.only_required_for_messages("simplifiable-if-expression")
    def visit_ifexp(self, node: nodes.IfExp) -> None:
        self._check_simplifiable_ifexp(node)

    def _check_simplifiable_ifexp(self, node: nodes.IfExp) -> None:
        if not isinstance(node.body, nodes.Const) or not isinstance(
            node.orelse, nodes.Const
        ):
            return

        if not isinstance(node.body.value, bool) or not isinstance(
            node.orelse.value, bool
        ):
            return

        if isinstance(node.test, nodes.Compare):
            test_reduced_to = "test"
        else:
            test_reduced_to = "bool(test)"

        if (node.body.value, node.orelse.value) == (True, False):
            reduced_to = f"'{test_reduced_to}'"
        elif (node.body.value, node.orelse.value) == (False, True):
            reduced_to = "'not test'"
        else:
            return

        self.add_message("simplifiable-if-expression", node=node, args=(reduced_to,))

    @utils.only_required_for_messages(
        "too-many-nested-blocks",
        "inconsistent-return-statements",
        "useless-return",
        "consider-using-with",
    )
    def leave_functiondef(self, node: nodes.FunctionDef) -> None:
        # check left-over nested blocks stack
        self._emit_nested_blocks_message_if_needed(self._nested_blocks)
        # new scope = reinitialize the stack of nested blocks
        self._nested_blocks = []
        # check consistent return statements
        self._check_consistent_returns(node)
        # check for single return or return None at the end
        self._check_return_at_the_end(node)
        self._return_nodes[node.name] = []
        # check for context managers that have been created but not used
        self._emit_consider_using_with_if_needed(
            self._consider_using_with_stack.function_scope
        )
        self._consider_using_with_stack.function_scope.clear()

    @utils.only_required_for_messages("consider-using-with")
    def leave_classdef(self, _: nodes.ClassDef) -> None:
        # check for context managers that have been created but not used
        self._emit_consider_using_with_if_needed(
            self._consider_using_with_stack.class_scope
        )
        self._consider_using_with_stack.class_scope.clear()

    @utils.only_required_for_messages("stop-iteration-return")
    def visit_raise(self, node: nodes.Raise) -> None:
        self._check_stop_iteration_inside_generator(node)

    def _check_stop_iteration_inside_generator(self, node: nodes.Raise) -> None:
        """Check if an exception of type StopIteration is raised inside a generator."""
        frame = node.frame(future=True)
        if not isinstance(frame, nodes.FunctionDef) or not frame.is_generator():
            return
        if utils.node_ignores_exception(node, StopIteration):
            return
        if not node.exc:
            return
        exc = utils.safe_infer(node.exc)
        if not exc or not isinstance(exc, (bases.Instance, nodes.ClassDef)):
            return
        if self._check_exception_inherit_from_stopiteration(exc):
            self.add_message("stop-iteration-return", node=node, confidence=INFERENCE)

    @staticmethod
    def _check_exception_inherit_from_stopiteration(
        exc: nodes.ClassDef | bases.Instance,
    ) -> bool:
        """Return True if the exception node in argument inherit from StopIteration."""
        stopiteration_qname = f"{utils.EXCEPTIONS_MODULE}.StopIteration"
        return any(_class.qname() == stopiteration_qname for _class in exc.mro())

    def _check_consider_using_comprehension_constructor(self, node: nodes.Call) -> None:
        if (
            isinstance(node.func, nodes.Name)
            and node.args
            and isinstance(node.args[0], nodes.ListComp)
        ):
            if node.func.name == "dict":
                element = node.args[0].elt
                if isinstance(element, nodes.Call):
                    return

                # If we have an `IfExp` here where both the key AND value
                # are different, then don't raise the issue. See #5588
                if (
                    isinstance(element, nodes.IfExp)
                    and isinstance(element.body, (nodes.Tuple, nodes.List))
                    and len(element.body.elts) == 2
                    and isinstance(element.orelse, (nodes.Tuple, nodes.List))
                    and len(element.orelse.elts) == 2
                ):
                    key1, value1 = element.body.elts
                    key2, value2 = element.orelse.elts
                    if (
                        key1.as_string() != key2.as_string()
                        and value1.as_string() != value2.as_string()
                    ):
                        return

                message_name = "consider-using-dict-comprehension"
                self.add_message(message_name, node=node)
            elif node.func.name == "set":
                message_name = "consider-using-set-comprehension"
                self.add_message(message_name, node=node)

    def _check_consider_using_generator(self, node: nodes.Call) -> None:
        # 'any', 'all', definitely should use generator, while 'list', 'tuple',
        # 'sum', 'max', and 'min' need to be considered first
        # See https://github.com/PyCQA/pylint/pull/3309#discussion_r576683109
        # https://github.com/PyCQA/pylint/pull/6595#issuecomment-1125704244
        # and https://peps.python.org/pep-0289/
        checked_call = ["any", "all", "sum", "max", "min", "list", "tuple"]
        if (
            isinstance(node, nodes.Call)
            and node.func
            and isinstance(node.func, nodes.Name)
            and node.func.name in checked_call
        ):
            # functions in checked_calls take exactly one argument
            # check whether the argument is list comprehension
            if len(node.args) == 1 and isinstance(node.args[0], nodes.ListComp):
                # remove square brackets '[]'
                inside_comp = node.args[0].as_string()[1:-1]
                call_name = node.func.name
                if call_name in {"any", "all"}:
                    self.add_message(
                        "use-a-generator",
                        node=node,
                        args=(call_name, inside_comp),
                    )
                else:
                    self.add_message(
                        "consider-using-generator",
                        node=node,
                        args=(call_name, inside_comp),
                    )

    @utils.only_required_for_messages(
        "stop-iteration-return",
        "consider-using-dict-comprehension",
        "consider-using-set-comprehension",
        "consider-using-sys-exit",
        "super-with-arguments",
        "consider-using-generator",
        "consider-using-with",
        "use-list-literal",
        "use-dict-literal",
        "use-a-generator",
    )
    def visit_call(self, node: nodes.Call) -> None:
        self._check_raising_stopiteration_in_generator_next_call(node)
        self._check_consider_using_comprehension_constructor(node)
        self._check_quit_exit_call(node)
        self._check_super_with_arguments(node)
        self._check_consider_using_generator(node)
        self._check_consider_using_with(node)
        self._check_use_list_literal(node)
        self._check_use_dict_literal(node)

    @staticmethod
    def _has_exit_in_scope(scope: nodes.LocalsDictNodeNG) -> bool:
        exit_func = scope.locals.get("exit")
        return bool(
            exit_func and isinstance(exit_func[0], (nodes.ImportFrom, nodes.Import))
        )

    def _check_quit_exit_call(self, node: nodes.Call) -> None:
        if isinstance(node.func, nodes.Name) and node.func.name in BUILTIN_EXIT_FUNCS:
            # If we have `exit` imported from `sys` in the current or global scope,
            # exempt this instance.
            local_scope = node.scope()
            if self._has_exit_in_scope(local_scope) or self._has_exit_in_scope(
                node.root()
            ):
                return
            self.add_message("consider-using-sys-exit", node=node, confidence=HIGH)

    def _check_super_with_arguments(self, node: nodes.Call) -> None:
        if not isinstance(node.func, nodes.Name) or node.func.name != "super":
            return

        # pylint: disable=too-many-boolean-expressions
        if (
            len(node.args) != 2
            or not isinstance(node.args[1], nodes.Name)
            or node.args[1].name != "self"
            or not isinstance(node.args[0], nodes.Name)
            or not isinstance(node.args[1], nodes.Name)
            or node_frame_class(node) is None
            # TODO: PY38: Use walrus operator, this will also fix the mypy issue
            or node.args[0].name != node_frame_class(node).name  # type: ignore[union-attr]
        ):
            return

        self.add_message("super-with-arguments", node=node)

    def _check_raising_stopiteration_in_generator_next_call(
        self, node: nodes.Call
    ) -> None:
        """Check if a StopIteration exception is raised by the call to next function.

        If the next value has a default value, then do not add message.

        :param node: Check to see if this Call node is a next function
        :type node: :class:`nodes.Call`
        """

        def _looks_like_infinite_iterator(param: nodes.NodeNG) -> bool:
            inferred = utils.safe_infer(param)
            if isinstance(inferred, bases.Instance):
                return inferred.qname() in KNOWN_INFINITE_ITERATORS
            return False

        if isinstance(node.func, nodes.Attribute):
            # A next() method, which is now what we want.
            return

        if len(node.args) == 0:
            # handle case when builtin.next is called without args.
            # see https://github.com/PyCQA/pylint/issues/7828
            return

        inferred = utils.safe_infer(node.func)

        if (
            isinstance(inferred, nodes.FunctionDef)
            and inferred.qname() == "builtins.next"
        ):
            frame = node.frame(future=True)
            # The next builtin can only have up to two
            # positional arguments and no keyword arguments
            has_sentinel_value = len(node.args) > 1
            if (
                isinstance(frame, nodes.FunctionDef)
                and frame.is_generator()
                and not has_sentinel_value
                and not utils.node_ignores_exception(node, StopIteration)
                and not _looks_like_infinite_iterator(node.args[0])
            ):
                self.add_message(
                    "stop-iteration-return", node=node, confidence=INFERENCE
                )

    def _check_nested_blocks(
        self,
        node: NodesWithNestedBlocks,
    ) -> None:
        """Update and check the number of nested blocks."""
        # only check block levels inside functions or methods
        if not isinstance(node.scope(), nodes.FunctionDef):
            return
        # messages are triggered on leaving the nested block. Here we save the
        # stack in case the current node isn't nested in the previous one
        nested_blocks = self._nested_blocks[:]
        if node.parent == node.scope():
            self._nested_blocks = [node]
        else:
            # go through ancestors from the most nested to the less
            for ancestor_node in reversed(self._nested_blocks):
                if ancestor_node == node.parent:
                    break
                self._nested_blocks.pop()
            # if the node is an elif, this should not be another nesting level
            if isinstance(node, nodes.If) and self._is_actual_elif(node):
                if self._nested_blocks:
                    self._nested_blocks.pop()
            self._nested_blocks.append(node)

        # send message only once per group of nested blocks
        if len(nested_blocks) > len(self._nested_blocks):
            self._emit_nested_blocks_message_if_needed(nested_blocks)

    def _emit_nested_blocks_message_if_needed(
        self, nested_blocks: list[NodesWithNestedBlocks]
    ) -> None:
        if len(nested_blocks) > self.linter.config.max_nested_blocks:
            self.add_message(
                "too-many-nested-blocks",
                node=nested_blocks[0],
                args=(len(nested_blocks), self.linter.config.max_nested_blocks),
            )

    def _emit_consider_using_with_if_needed(
        self, stack: dict[str, nodes.NodeNG]
    ) -> None:
        for node in stack.values():
            self.add_message("consider-using-with", node=node)

    @staticmethod
    def _duplicated_isinstance_types(node: nodes.BoolOp) -> dict[str, set[str]]:
        """Get the duplicated types from the underlying isinstance calls.

        :param nodes.BoolOp node: Node which should contain a bunch of isinstance calls.
        :returns: Dictionary of the comparison objects from the isinstance calls,
                  to duplicate values from consecutive calls.
        :rtype: dict
        """
        duplicated_objects: set[str] = set()
        all_types: collections.defaultdict[str, set[str]] = collections.defaultdict(set)

        for call in node.values:
            if not isinstance(call, nodes.Call) or len(call.args) != 2:
                continue

            inferred = utils.safe_infer(call.func)
            if not inferred or not utils.is_builtin_object(inferred):
                continue

            if inferred.name != "isinstance":
                continue

            isinstance_object = call.args[0].as_string()
            isinstance_types = call.args[1]

            if isinstance_object in all_types:
                duplicated_objects.add(isinstance_object)

            if isinstance(isinstance_types, nodes.Tuple):
                elems = [
                    class_type.as_string() for class_type in isinstance_types.itered()
                ]
            else:
                elems = [isinstance_types.as_string()]
            all_types[isinstance_object].update(elems)

        # Remove all keys which not duplicated
        return {
            key: value for key, value in all_types.items() if key in duplicated_objects
        }

    def _check_consider_merging_isinstance(self, node: nodes.BoolOp) -> None:
        """Check isinstance calls which can be merged together."""
        if node.op != "or":
            return

        first_args = self._duplicated_isinstance_types(node)
        for duplicated_name, class_names in first_args.items():
            names = sorted(name for name in class_names)
            self.add_message(
                "consider-merging-isinstance",
                node=node,
                args=(duplicated_name, ", ".join(names)),
            )

    def _check_consider_using_in(self, node: nodes.BoolOp) -> None:
        allowed_ops = {"or": "==", "and": "!="}

        if node.op not in allowed_ops or len(node.values) < 2:
            return

        for value in node.values:
            if (
                not isinstance(value, nodes.Compare)
                or len(value.ops) != 1
                or value.ops[0][0] not in allowed_ops[node.op]
            ):
                return
            for comparable in value.left, value.ops[0][1]:
                if isinstance(comparable, nodes.Call):
                    return

        # Gather variables and values from comparisons
        variables, values = [], []
        for value in node.values:
            variable_set = set()
            for comparable in value.left, value.ops[0][1]:
                if isinstance(comparable, (nodes.Name, nodes.Attribute)):
                    variable_set.add(comparable.as_string())
                values.append(comparable.as_string())
            variables.append(variable_set)

        # Look for (common-)variables that occur in all comparisons
        common_variables = reduce(lambda a, b: a.intersection(b), variables)

        if not common_variables:
            return

        # Gather information for the suggestion
        common_variable = sorted(list(common_variables))[0]
        values = list(collections.OrderedDict.fromkeys(values))
        values.remove(common_variable)
        values_string = ", ".join(values) if len(values) != 1 else values[0] + ","
        maybe_not = "" if node.op == "or" else "not "
        self.add_message(
            "consider-using-in",
            node=node,
            args=(common_variable, maybe_not, values_string),
            confidence=HIGH,
        )

    def _check_chained_comparison(self, node: nodes.BoolOp) -> None:
        """Check if there is any chained comparison in the expression.

        Add a refactoring message if a boolOp contains comparison like a < b and b < c,
        which can be chained as a < b < c.

        Care is taken to avoid simplifying a < b < c and b < d.
        """
        if node.op != "and" or len(node.values) < 2:
            return

        def _find_lower_upper_bounds(
            comparison_node: nodes.Compare,
            uses: collections.defaultdict[str, dict[str, set[nodes.Compare]]],
        ) -> None:
            left_operand = comparison_node.left
            for operator, right_operand in comparison_node.ops:
                for operand in (left_operand, right_operand):
                    value = None
                    if isinstance(operand, nodes.Name):
                        value = operand.name
                    elif isinstance(operand, nodes.Const):
                        value = operand.value

                    if value is None:
                        continue

                    if operator in {"<", "<="}:
                        if operand is left_operand:
                            uses[value]["lower_bound"].add(comparison_node)
                        elif operand is right_operand:
                            uses[value]["upper_bound"].add(comparison_node)
                    elif operator in {">", ">="}:
                        if operand is left_operand:
                            uses[value]["upper_bound"].add(comparison_node)
                        elif operand is right_operand:
                            uses[value]["lower_bound"].add(comparison_node)
                left_operand = right_operand

        uses: collections.defaultdict[
            str, dict[str, set[nodes.Compare]]
        ] = collections.defaultdict(
            lambda: {"lower_bound": set(), "upper_bound": set()}
        )
        for comparison_node in node.values:
            if isinstance(comparison_node, nodes.Compare):
                _find_lower_upper_bounds(comparison_node, uses)

        for bounds in uses.values():
            num_shared = len(bounds["lower_bound"].intersection(bounds["upper_bound"]))
            num_lower_bounds = len(bounds["lower_bound"])
            num_upper_bounds = len(bounds["upper_bound"])
            if num_shared < num_lower_bounds and num_shared < num_upper_bounds:
                self.add_message("chained-comparison", node=node)
                break

    @staticmethod
    def _apply_boolean_simplification_rules(
        operator: str, values: list[nodes.NodeNG]
    ) -> list[nodes.NodeNG]:
        """Removes irrelevant values or returns short-circuiting values.

        This function applies the following two rules:
        1) an OR expression with True in it will always be true, and the
           reverse for AND

        2) False values in OR expressions are only relevant if all values are
           false, and the reverse for AND
        """
        simplified_values: list[nodes.NodeNG] = []

        for subnode in values:
            inferred_bool = None
            if not next(subnode.nodes_of_class(nodes.Name), False):
                inferred = utils.safe_infer(subnode)
                if inferred:
                    inferred_bool = inferred.bool_value()

            if not isinstance(inferred_bool, bool):
                simplified_values.append(subnode)
            elif (operator == "or") == inferred_bool:
                return [subnode]

        return simplified_values or [nodes.Const(operator == "and")]

    def _simplify_boolean_operation(self, bool_op: nodes.BoolOp) -> nodes.BoolOp:
        """Attempts to simplify a boolean operation.

        Recursively applies simplification on the operator terms,
        and keeps track of whether reductions have been made.
        """
        children = list(bool_op.get_children())
        intermediate = [
            self._simplify_boolean_operation(child)
            if isinstance(child, nodes.BoolOp)
            else child
            for child in children
        ]
        result = self._apply_boolean_simplification_rules(bool_op.op, intermediate)
        if len(result) < len(children):
            self._can_simplify_bool_op = True
        if len(result) == 1:
            return result[0]
        simplified_bool_op = copy.copy(bool_op)
        simplified_bool_op.postinit(result)
        return simplified_bool_op

    def _check_simplifiable_condition(self, node: nodes.BoolOp) -> None:
        """Check if a boolean condition can be simplified.

        Variables will not be simplified, even if the value can be inferred,
        and expressions like '3 + 4' will remain expanded.
        """
        if not utils.is_test_condition(node):
            return

        self._can_simplify_bool_op = False
        simplified_expr = self._simplify_boolean_operation(node)

        if not self._can_simplify_bool_op:
            return

        if not next(simplified_expr.nodes_of_class(nodes.Name), False):
            self.add_message(
                "condition-evals-to-constant",
                node=node,
                args=(node.as_string(), simplified_expr.as_string()),
            )
        else:
            self.add_message(
                "simplifiable-condition",
                node=node,
                args=(node.as_string(), simplified_expr.as_string()),
            )

    @utils.only_required_for_messages(
        "consider-merging-isinstance",
        "consider-using-in",
        "chained-comparison",
        "simplifiable-condition",
        "condition-evals-to-constant",
    )
    def visit_boolop(self, node: nodes.BoolOp) -> None:
        self._check_consider_merging_isinstance(node)
        self._check_consider_using_in(node)
        self._check_chained_comparison(node)
        self._check_simplifiable_condition(node)

    @staticmethod
    def _is_simple_assignment(node: nodes.NodeNG | None) -> bool:
        return (
            isinstance(node, nodes.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], nodes.AssignName)
            and isinstance(node.value, nodes.Name)
        )

    def _check_swap_variables(self, node: nodes.Return | nodes.Assign) -> None:
        if not node.next_sibling() or not node.next_sibling().next_sibling():
            return
        assignments = [node, node.next_sibling(), node.next_sibling().next_sibling()]
        if not all(self._is_simple_assignment(node) for node in assignments):
            return
        if any(node in self._reported_swap_nodes for node in assignments):
            return
        left = [node.targets[0].name for node in assignments]
        right = [node.value.name for node in assignments]
        if left[0] == right[-1] and left[1:] == right[:-1]:
            self._reported_swap_nodes.update(assignments)
            message = "consider-swap-variables"
            self.add_message(message, node=node)

    @utils.only_required_for_messages(
        "simplify-boolean-expression",
        "consider-using-ternary",
        "consider-swap-variables",
        "consider-using-with",
    )
    def visit_assign(self, node: nodes.Assign) -> None:
        self._append_context_managers_to_stack(node)
        self.visit_return(node)  # remaining checks are identical as for return nodes

    @utils.only_required_for_messages(
        "simplify-boolean-expression",
        "consider-using-ternary",
        "consider-swap-variables",
    )
    def visit_return(self, node: nodes.Return | nodes.Assign) -> None:
        self._check_swap_variables(node)
        if self._is_and_or_ternary(node.value):
            cond, truth_value, false_value = self._and_or_ternary_arguments(node.value)
        else:
            return

        if all(
            isinstance(value, nodes.Compare) for value in (truth_value, false_value)
        ):
            return

        inferred_truth_value = utils.safe_infer(truth_value, compare_constants=True)
        if inferred_truth_value is None or isinstance(
            inferred_truth_value, UninferableBase
        ):
            return
        truth_boolean_value = inferred_truth_value.bool_value()

        if truth_boolean_value is False:
            message = "simplify-boolean-expression"
            suggestion = false_value.as_string()
        else:
            message = "consider-using-ternary"
            suggestion = f"{truth_value.as_string()} if {cond.as_string()} else {false_value.as_string()}"
        self.add_message(message, node=node, args=(suggestion,), confidence=INFERENCE)

    def _append_context_managers_to_stack(self, node: nodes.Assign) -> None:
        if _is_inside_context_manager(node):
            # if we are inside a context manager itself, we assume that it will handle
            # the resource management itself.
            return
        if isinstance(node.targets[0], (nodes.Tuple, nodes.List, nodes.Set)):
            assignees = node.targets[0].elts
            value = utils.safe_infer(node.value)
            if value is None or not hasattr(value, "elts"):
                # We cannot deduce what values are assigned, so we have to skip this
                return
            values = value.elts
        else:
            assignees = [node.targets[0]]
            values = [node.value]
        if any(isinstance(n, UninferableBase) for n in (assignees, values)):
            return
        for assignee, value in zip(assignees, values):
            if not isinstance(value, nodes.Call):
                continue
            inferred = utils.safe_infer(value.func)
            if (
                not inferred
                or inferred.qname() not in CALLS_RETURNING_CONTEXT_MANAGERS
                or not isinstance(assignee, (nodes.AssignName, nodes.AssignAttr))
            ):
                continue
            stack = self._consider_using_with_stack.get_stack_for_frame(
                node.frame(future=True)
            )
            varname = (
                assignee.name
                if isinstance(assignee, nodes.AssignName)
                else assignee.attrname
            )
            if varname in stack:
                existing_node = stack[varname]
                if astroid.are_exclusive(node, existing_node):
                    # only one of the two assignments can be executed at runtime, thus it is fine
                    stack[varname] = value
                    continue
                # variable was redefined before it was used in a ``with`` block
                self.add_message(
                    "consider-using-with",
                    node=existing_node,
                )
            stack[varname] = value

    def _check_consider_using_with(self, node: nodes.Call) -> None:
        if _is_inside_context_manager(node) or _is_a_return_statement(node):
            # If we are inside a context manager itself, we assume that it will handle the
            # resource management itself.
            # If the node is a child of a return, we assume that the caller knows he is getting
            # a context manager he should use properly (i.e. in a ``with``).
            return
        if (
            node
            in self._consider_using_with_stack.get_stack_for_frame(
                node.frame(future=True)
            ).values()
        ):
            # the result of this call was already assigned to a variable and will be
            # checked when leaving the scope.
            return
        inferred = utils.safe_infer(node.func)
        if not inferred or not isinstance(
            inferred, (nodes.FunctionDef, nodes.ClassDef, bases.UnboundMethod)
        ):
            return
        could_be_used_in_with = (
            # things like ``lock.acquire()``
            inferred.qname() in CALLS_THAT_COULD_BE_REPLACED_BY_WITH
            or (
                # things like ``open("foo")`` which are not already inside a ``with`` statement
                inferred.qname() in CALLS_RETURNING_CONTEXT_MANAGERS
                and not _is_part_of_with_items(node)
            )
        )
        if could_be_used_in_with and not _will_be_released_automatically(node):
            self.add_message("consider-using-with", node=node)

    def _check_use_list_literal(self, node: nodes.Call) -> None:
        """Check if empty list is created by using the literal []."""
        if node.as_string() == "list()":
            inferred = utils.safe_infer(node.func)
            if isinstance(inferred, nodes.ClassDef) and not node.args:
                if inferred.qname() == "builtins.list":
                    self.add_message("use-list-literal", node=node)

    def _check_use_dict_literal(self, node: nodes.Call) -> None:
        """Check if dict is created by using the literal {}."""
        if not isinstance(node.func, astroid.Name) or node.func.name != "dict":
            return
        inferred = utils.safe_infer(node.func)
        if (
            isinstance(inferred, nodes.ClassDef)
            and inferred.qname() == "builtins.dict"
            and not node.args
        ):
            self.add_message(
                "use-dict-literal",
                args=(self._dict_literal_suggestion(node),),
                node=node,
                confidence=INFERENCE,
            )

    @staticmethod
    def _dict_literal_suggestion(node: nodes.Call) -> str:
        """Return a suggestion of reasonable length."""
        elements: list[str] = []
        for keyword in node.keywords:
            if len(", ".join(elements)) >= 64:
                break
            if keyword not in node.kwargs:
                elements.append(f'"{keyword.arg}": {keyword.value.as_string()}')
        for keyword in node.kwargs:
            if len(", ".join(elements)) >= 64:
                break
            elements.append(f"**{keyword.value.as_string()}")
        suggestion = ", ".join(elements)
        return f"{{{suggestion}{', ... '  if len(suggestion) > 64 else ''}}}"

    @staticmethod
    def _name_to_concatenate(node: nodes.NodeNG) -> str | None:
        """Try to extract the name used in a concatenation loop."""
        if isinstance(node, nodes.Name):
            return cast("str | None", node.name)
        if not isinstance(node, nodes.JoinedStr):
            return None

        values = [
            value for value in node.values if isinstance(value, nodes.FormattedValue)
        ]
        if len(values) != 1 or not isinstance(values[0].value, nodes.Name):
            return None
        return cast("str | None", values[0].value.name)

    def _check_consider_using_join(self, aug_assign: nodes.AugAssign) -> None:
        """We start with the augmented assignment and work our way upwards.

        Names of variables for nodes if match successful:
        result = ''  # assign
        for number in ['1', '2', '3']  # for_loop
            result += number  # aug_assign
        """
        for_loop = aug_assign.parent
        if not isinstance(for_loop, nodes.For) or len(for_loop.body) > 1:
            return
        assign = for_loop.previous_sibling()
        if not isinstance(assign, nodes.Assign):
            return
        result_assign_names = {
            target.name
            for target in assign.targets
            if isinstance(target, nodes.AssignName)
        }

        is_concat_loop = (
            aug_assign.op == "+="
            and isinstance(aug_assign.target, nodes.AssignName)
            and len(for_loop.body) == 1
            and aug_assign.target.name in result_assign_names
            and isinstance(assign.value, nodes.Const)
            and isinstance(assign.value.value, str)
            and self._name_to_concatenate(aug_assign.value) == for_loop.target.name
        )
        if is_concat_loop:
            self.add_message("consider-using-join", node=aug_assign)

    @utils.only_required_for_messages("consider-using-join")
    def visit_augassign(self, node: nodes.AugAssign) -> None:
        self._check_consider_using_join(node)

    @utils.only_required_for_messages(
        "unnecessary-comprehension",
        "unnecessary-dict-index-lookup",
        "unnecessary-list-index-lookup",
    )
    def visit_comprehension(self, node: nodes.Comprehension) -> None:
        self._check_unnecessary_comprehension(node)
        self._check_unnecessary_dict_index_lookup(node)
        self._check_unnecessary_list_index_lookup(node)

    def _check_unnecessary_comprehension(self, node: nodes.Comprehension) -> None:
        if (
            isinstance(node.parent, nodes.GeneratorExp)
            or len(node.ifs) != 0
            or len(node.parent.generators) != 1
            or node.is_async
        ):
            return

        if (
            isinstance(node.parent, nodes.DictComp)
            and isinstance(node.parent.key, nodes.Name)
            and isinstance(node.parent.value, nodes.Name)
            and isinstance(node.target, nodes.Tuple)
            and all(isinstance(elt, nodes.AssignName) for elt in node.target.elts)
        ):
            expr_list = [node.parent.key.name, node.parent.value.name]
            target_list = [elt.name for elt in node.target.elts]

        elif isinstance(node.parent, (nodes.ListComp, nodes.SetComp)):
            expr = node.parent.elt
            if isinstance(expr, nodes.Name):
                expr_list = expr.name
            elif isinstance(expr, nodes.Tuple):
                if any(not isinstance(elt, nodes.Name) for elt in expr.elts):
                    return
                expr_list = [elt.name for elt in expr.elts]
            else:
                expr_list = []
            target = node.parent.generators[0].target
            target_list = (
                target.name
                if isinstance(target, nodes.AssignName)
                else (
                    [
                        elt.name
                        for elt in target.elts
                        if isinstance(elt, nodes.AssignName)
                    ]
                    if isinstance(target, nodes.Tuple)
                    else []
                )
            )
        else:
            return
        if expr_list == target_list and expr_list:
            args: tuple[str] | None = None
            inferred = utils.safe_infer(node.iter)
            if isinstance(node.parent, nodes.DictComp) and isinstance(
                inferred, astroid.objects.DictItems
            ):
                args = (f"{node.iter.func.expr.as_string()}",)
            elif (
                isinstance(node.parent, nodes.ListComp)
                and isinstance(inferred, nodes.List)
            ) or (
                isinstance(node.parent, nodes.SetComp)
                and isinstance(inferred, nodes.Set)
            ):
                args = (f"{node.iter.as_string()}",)
            if args:
                self.add_message(
                    "unnecessary-comprehension", node=node.parent, args=args
                )
                return

            if isinstance(node.parent, nodes.DictComp):
                func = "dict"
            elif isinstance(node.parent, nodes.ListComp):
                func = "list"
            elif isinstance(node.parent, nodes.SetComp):
                func = "set"
            else:
                return

            self.add_message(
                "unnecessary-comprehension",
                node=node.parent,
                args=(f"{func}({node.iter.as_string()})",),
            )

    @staticmethod
    def _is_and_or_ternary(node: nodes.NodeNG | None) -> bool:
        """Returns true if node is 'condition and true_value or false_value' form.

        All of: condition, true_value and false_value should not be a complex boolean expression
        """
        return (
            isinstance(node, nodes.BoolOp)
            and node.op == "or"
            and len(node.values) == 2
            and isinstance(node.values[0], nodes.BoolOp)
            and not isinstance(node.values[1], nodes.BoolOp)
            and node.values[0].op == "and"
            and not isinstance(node.values[0].values[1], nodes.BoolOp)
            and len(node.values[0].values) == 2
        )

    @staticmethod
    def _and_or_ternary_arguments(
        node: nodes.BoolOp,
    ) -> tuple[nodes.NodeNG, nodes.NodeNG, nodes.NodeNG]:
        false_value = node.values[1]
        condition, true_value = node.values[0].values
        return condition, true_value, false_value

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        self._return_nodes[node.name] = list(
            node.nodes_of_class(nodes.Return, skip_klass=nodes.FunctionDef)
        )

    def _check_consistent_returns(self, node: nodes.FunctionDef) -> None:
        """Check that all return statements inside a function are consistent.

        Return statements are consistent if:
            - all returns are explicit and if there is no implicit return;
            - all returns are empty and if there is, possibly, an implicit return.

        Args:
            node (nodes.FunctionDef): the function holding the return statements.
        """
        # explicit return statements are those with a not None value
        explicit_returns = [
            _node for _node in self._return_nodes[node.name] if _node.value is not None
        ]
        if not explicit_returns:
            return
        if len(explicit_returns) == len(
            self._return_nodes[node.name]
        ) and self._is_node_return_ended(node):
            return
        self.add_message("inconsistent-return-statements", node=node)

    def _is_if_node_return_ended(self, node: nodes.If) -> bool:
        """Check if the If node ends with an explicit return statement.

        Args:
            node (nodes.If): If node to be checked.

        Returns:
            bool: True if the node ends with an explicit statement, False otherwise.
        """
        # Do not check if inner function definition are return ended.
        is_if_returning = any(
            self._is_node_return_ended(_ifn)
            for _ifn in node.body
            if not isinstance(_ifn, nodes.FunctionDef)
        )
        if not node.orelse:
            # If there is not orelse part then the if statement is returning if :
            # - there is at least one return statement in its siblings;
            # - the if body is itself returning.
            if not self._has_return_in_siblings(node):
                return False
            return is_if_returning
        # If there is an orelse part then both if body and orelse part should return.
        is_orelse_returning = any(
            self._is_node_return_ended(_ore)
            for _ore in node.orelse
            if not isinstance(_ore, nodes.FunctionDef)
        )
        return is_if_returning and is_orelse_returning

    def _is_raise_node_return_ended(self, node: nodes.Raise) -> bool:
        """Check if the Raise node ends with an explicit return statement.

        Args:
            node (nodes.Raise): Raise node to be checked.

        Returns:
            bool: True if the node ends with an explicit statement, False otherwise.
        """
        # a Raise statement doesn't need to end with a return statement
        # but if the exception raised is handled, then the handler has to
        # ends with a return statement
        if not node.exc:
            # Ignore bare raises
            return True
        if not utils.is_node_inside_try_except(node):
            # If the raise statement is not inside a try/except statement
            # then the exception is raised and cannot be caught. No need
            # to infer it.
            return True
        exc = utils.safe_infer(node.exc)
        if (
            exc is None
            or isinstance(exc, UninferableBase)
            or not hasattr(exc, "pytype")
        ):
            return False
        exc_name = exc.pytype().split(".")[-1]
        handlers = utils.get_exception_handlers(node, exc_name)
        handlers = list(handlers) if handlers is not None else []
        if handlers:
            # among all the handlers handling the exception at least one
            # must end with a return statement
            return any(self._is_node_return_ended(_handler) for _handler in handlers)
        # if no handlers handle the exception then it's ok
        return True

    def _is_node_return_ended(self, node: nodes.NodeNG) -> bool:
        """Check if the node ends with an explicit return statement.

        Args:
            node (nodes.NodeNG): node to be checked.

        Returns:
            bool: True if the node ends with an explicit statement, False otherwise.
        """
        # Recursion base case
        if isinstance(node, nodes.Return):
            return True
        if isinstance(node, nodes.Call):
            try:
                funcdef_node = node.func.inferred()[0]
                if self._is_function_def_never_returning(funcdef_node):
                    return True
            except astroid.InferenceError:
                pass
        if isinstance(node, nodes.While):
            # A while-loop is considered return-ended if it has a
            # truthy test and no break statements
            return (node.test.bool_value() and not _loop_exits_early(node)) or any(
                self._is_node_return_ended(child) for child in node.orelse
            )
        if isinstance(node, nodes.Raise):
            return self._is_raise_node_return_ended(node)
        if isinstance(node, nodes.If):
            return self._is_if_node_return_ended(node)
        if isinstance(node, nodes.TryExcept):
            handlers = {
                _child
                for _child in node.get_children()
                if isinstance(_child, nodes.ExceptHandler)
            }
            all_but_handler = set(node.get_children()) - handlers
            return any(
                self._is_node_return_ended(_child) for _child in all_but_handler
            ) and all(self._is_node_return_ended(_child) for _child in handlers)
        if (
            isinstance(node, nodes.Assert)
            and isinstance(node.test, nodes.Const)
            and not node.test.value
        ):
            # consider assert False as a return node
            return True
        # recurses on the children of the node
        return any(self._is_node_return_ended(_child) for _child in node.get_children())

    @staticmethod
    def _has_return_in_siblings(node: nodes.NodeNG) -> bool:
        """Returns True if there is at least one return in the node's siblings."""
        next_sibling = node.next_sibling()
        while next_sibling:
            if isinstance(next_sibling, nodes.Return):
                return True
            next_sibling = next_sibling.next_sibling()
        return False

    def _is_function_def_never_returning(self, node: nodes.FunctionDef) -> bool:
        """Return True if the function never returns, False otherwise.

        Args:
            node (nodes.FunctionDef): function definition node to be analyzed.

        Returns:
            bool: True if the function never returns, False otherwise.
        """
        if isinstance(node, nodes.FunctionDef) and node.returns:
            return (
                isinstance(node.returns, nodes.Attribute)
                and node.returns.attrname == "NoReturn"
                or isinstance(node.returns, nodes.Name)
                and node.returns.name == "NoReturn"
            )
        try:
            return node.qname() in self._never_returning_functions
        except (TypeError, AttributeError):
            return False

    def _check_return_at_the_end(self, node: nodes.FunctionDef) -> None:
        """Check for presence of a *single* return statement at the end of a
        function.

        "return" or "return None" are useless because None is the
        default return type if they are missing.

        NOTE: produces a message only if there is a single return statement
        in the function body. Otherwise _check_consistent_returns() is called!
        Per its implementation and PEP8 we can have a "return None" at the end
        of the function body if there are other return statements before that!
        """
        if len(self._return_nodes[node.name]) > 1:
            return
        if len(node.body) <= 1:
            return

        last = node.body[-1]
        if isinstance(last, nodes.Return):
            # e.g. "return"
            if last.value is None:
                self.add_message("useless-return", node=node)
            # return None"
            elif isinstance(last.value, nodes.Const) and (last.value.value is None):
                self.add_message("useless-return", node=node)

    def _check_unnecessary_dict_index_lookup(
        self, node: nodes.For | nodes.Comprehension
    ) -> None:
        """Add message when accessing dict values by index lookup."""
        # Verify that we have an .items() call and
        # that the object which is iterated is used as a subscript in the
        # body of the for.
        # Is it a proper items call?
        if (
            isinstance(node.iter, nodes.Call)
            and isinstance(node.iter.func, nodes.Attribute)
            and node.iter.func.attrname == "items"
        ):
            inferred = utils.safe_infer(node.iter.func)
            if not isinstance(inferred, astroid.BoundMethod):
                return
            iterating_object_name = node.iter.func.expr.as_string()

            # Store potential violations. These will only be reported if we don't
            # discover any writes to the collection during the loop.
            messages = []

            # Verify that the body of the for loop uses a subscript
            # with the object that was iterated. This uses some heuristics
            # in order to make sure that the same object is used in the
            # for body.

            children = (
                node.body
                if isinstance(node, nodes.For)
                else list(node.parent.get_children())
            )

            # Check if there are any for / while loops within the loop in question;
            # If so, we will be more conservative about reporting errors as we
            # can't yet do proper control flow analysis to be sure when
            # reassignment will affect us
            nested_loops = itertools.chain.from_iterable(
                child.nodes_of_class((nodes.For, nodes.While)) for child in children
            )
            has_nested_loops = next(nested_loops, None) is not None

            for child in children:
                for subscript in child.nodes_of_class(nodes.Subscript):
                    if not isinstance(subscript.value, (nodes.Name, nodes.Attribute)):
                        continue

                    value = subscript.slice

                    if isinstance(node, nodes.For) and _is_part_of_assignment_target(
                        subscript
                    ):
                        # Ignore this subscript if it is the target of an assignment
                        # Early termination; after reassignment dict index lookup will be necessary
                        return

                    if isinstance(subscript.parent, nodes.Delete):
                        # Ignore this subscript if it's used with the delete keyword
                        return

                    # Case where .items is assigned to k,v (i.e., for k, v in d.items())
                    if isinstance(value, nodes.Name):
                        if (
                            not isinstance(node.target, nodes.Tuple)
                            # Ignore 1-tuples: for k, in d.items()
                            or len(node.target.elts) < 2
                            or value.name != node.target.elts[0].name
                            or iterating_object_name != subscript.value.as_string()
                        ):
                            continue

                        if (
                            isinstance(node, nodes.For)
                            and value.lookup(value.name)[1][-1].lineno > node.lineno
                        ):
                            # Ignore this subscript if it has been redefined after
                            # the for loop. This checks for the line number using .lookup()
                            # to get the line number where the iterating object was last
                            # defined and compare that to the for loop's line number
                            continue

                        if has_nested_loops:
                            messages.append(
                                {
                                    "node": subscript,
                                    "variable": node.target.elts[1].as_string(),
                                }
                            )
                        else:
                            self.add_message(
                                "unnecessary-dict-index-lookup",
                                node=subscript,
                                args=(node.target.elts[1].as_string(),),
                            )

                    # Case where .items is assigned to single var (i.e., for item in d.items())
                    elif isinstance(value, nodes.Subscript):
                        if (
                            not isinstance(node.target, nodes.AssignName)
                            or not isinstance(value.value, nodes.Name)
                            or node.target.name != value.value.name
                            or iterating_object_name != subscript.value.as_string()
                        ):
                            continue

                        if (
                            isinstance(node, nodes.For)
                            and value.value.lookup(value.value.name)[1][-1].lineno
                            > node.lineno
                        ):
                            # Ignore this subscript if it has been redefined after
                            # the for loop. This checks for the line number using .lookup()
                            # to get the line number where the iterating object was last
                            # defined and compare that to the for loop's line number
                            continue

                        # check if subscripted by 0 (key)
                        inferred = utils.safe_infer(value.slice)
                        if not isinstance(inferred, nodes.Const) or inferred.value != 0:
                            continue

                        if has_nested_loops:
                            messages.append(
                                {
                                    "node": subscript,
                                    "variable": "1".join(
                                        value.as_string().rsplit("0", maxsplit=1)
                                    ),
                                }
                            )
                        else:
                            self.add_message(
                                "unnecessary-dict-index-lookup",
                                node=subscript,
                                args=(
                                    "1".join(value.as_string().rsplit("0", maxsplit=1)),
                                ),
                            )

            for message in messages:
                self.add_message(
                    "unnecessary-dict-index-lookup",
                    node=message["node"],
                    args=(message["variable"],),
                )

    def _check_unnecessary_list_index_lookup(
        self, node: nodes.For | nodes.Comprehension
    ) -> None:
        if (
            not isinstance(node.iter, nodes.Call)
            or not isinstance(node.iter.func, nodes.Name)
            or not node.iter.func.name == "enumerate"
        ):
            return

        try:
            iterable_arg = utils.get_argument_from_call(
                node.iter, position=0, keyword="iterable"
            )
        except utils.NoSuchArgumentError:
            return

        if not isinstance(iterable_arg, nodes.Name):
            return

        if not isinstance(node.target, nodes.Tuple) or len(node.target.elts) < 2:
            # enumerate() result is being assigned without destructuring
            return

        if not isinstance(node.target.elts[1], nodes.AssignName):
            # The value is not being assigned to a single variable, e.g. being
            # destructured, so we can't necessarily use it.
            return

        has_start_arg, confidence = self._enumerate_with_start(node)
        if has_start_arg:
            # enumerate is being called with start arg/kwarg so resulting index lookup
            # is not redundant, hence we should not report an error.
            return

        iterating_object_name = iterable_arg.name
        value_variable = node.target.elts[1]

        # Store potential violations. These will only be reported if we don't
        # discover any writes to the collection during the loop.
        bad_nodes = []

        children = (
            node.body
            if isinstance(node, nodes.For)
            else list(node.parent.get_children())
        )

        # Check if there are any for / while loops within the loop in question;
        # If so, we will be more conservative about reporting errors as we
        # can't yet do proper control flow analysis to be sure when
        # reassignment will affect us
        nested_loops = itertools.chain.from_iterable(
            child.nodes_of_class((nodes.For, nodes.While)) for child in children
        )
        has_nested_loops = next(nested_loops, None) is not None

        # Check if there are any if statements within the loop in question;
        # If so, we will be more conservative about reporting errors as we
        # can't yet do proper control flow analysis to be sure when
        # reassignment will affect us
        if_statements = itertools.chain.from_iterable(
            child.nodes_of_class(nodes.If) for child in children
        )
        has_if_statements = next(if_statements, None) is not None

        for child in children:
            for subscript in child.nodes_of_class(nodes.Subscript):
                if isinstance(node, nodes.For) and _is_part_of_assignment_target(
                    subscript
                ):
                    # Ignore this subscript if it is the target of an assignment
                    # Early termination; after reassignment index lookup will be necessary
                    return

                if isinstance(subscript.parent, nodes.Delete):
                    # Ignore this subscript if it's used with the delete keyword
                    return

                index = subscript.slice
                if isinstance(index, nodes.Name):
                    if (
                        index.name != node.target.elts[0].name
                        or iterating_object_name != subscript.value.as_string()
                    ):
                        continue

                    if (
                        isinstance(node, nodes.For)
                        and index.lookup(index.name)[1][-1].lineno > node.lineno
                    ):
                        # Ignore this subscript if it has been redefined after
                        # the for loop.
                        continue

                    if (
                        isinstance(node, nodes.For)
                        and index.lookup(value_variable.name)[1][-1].lineno
                        > node.lineno
                    ):
                        # The variable holding the value from iteration has been
                        # reassigned on a later line, so it can't be used.
                        continue

                    if has_nested_loops:
                        # Have found a likely issue, but since there are nested
                        # loops we don't want to report this unless we get to the
                        # end of the loop without updating the collection
                        bad_nodes.append(subscript)
                    elif has_if_statements:
                        continue
                    else:
                        self.add_message(
                            "unnecessary-list-index-lookup",
                            node=subscript,
                            args=(node.target.elts[1].name,),
                            confidence=confidence,
                        )

        for subscript in bad_nodes:
            self.add_message(
                "unnecessary-list-index-lookup",
                node=subscript,
                args=(node.target.elts[1].name,),
                confidence=confidence,
            )

    def _enumerate_with_start(
        self, node: nodes.For | nodes.Comprehension
    ) -> tuple[bool, Confidence]:
        """Check presence of `start` kwarg or second argument to enumerate.

        For example:

        `enumerate([1,2,3], start=1)`
        `enumerate([1,2,3], 1)`

        If `start` is assigned to `0`, the default value, this is equivalent to
        not calling `enumerate` with start.
        """
        confidence = HIGH

        if len(node.iter.args) > 1:
            # We assume the second argument to `enumerate` is the `start` int arg.
            # It's a reasonable assumption for now as it's the only possible argument:
            # https://docs.python.org/3/library/functions.html#enumerate
            start_arg = node.iter.args[1]
            start_val, confidence = self._get_start_value(start_arg)
            if start_val is None:
                return False, confidence
            return not start_val == 0, confidence

        for keyword in node.iter.keywords:
            if keyword.arg == "start":
                start_val, confidence = self._get_start_value(keyword.value)
                if start_val is None:
                    return False, confidence
                return not start_val == 0, confidence

        return False, confidence

    def _get_start_value(self, node: nodes.NodeNG) -> tuple[int | None, Confidence]:
        if (
            isinstance(node, (nodes.Name, nodes.Call, nodes.Attribute))
            or isinstance(node, nodes.UnaryOp)
            and isinstance(node.operand, nodes.Attribute)
        ):
            inferred = utils.safe_infer(node)
            start_val = inferred.value if inferred else None
            return start_val, INFERENCE
        if isinstance(node, nodes.UnaryOp):
            return node.operand.value, HIGH
        if isinstance(node, nodes.Const):
            return node.value, HIGH
        return None, HIGH
