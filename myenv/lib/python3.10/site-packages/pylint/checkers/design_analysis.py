# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Check for signs of poor design."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterator
from typing import TYPE_CHECKING

import astroid
from astroid import nodes

from pylint.checkers import BaseChecker
from pylint.checkers.utils import is_enum, only_required_for_messages
from pylint.typing import MessageDefinitionTuple

if TYPE_CHECKING:
    from pylint.lint import PyLinter

MSGS: dict[
    str, MessageDefinitionTuple
] = {  # pylint: disable=consider-using-namedtuple-or-dataclass
    "R0901": (
        "Too many ancestors (%s/%s)",
        "too-many-ancestors",
        "Used when class has too many parent classes, try to reduce "
        "this to get a simpler (and so easier to use) class.",
    ),
    "R0902": (
        "Too many instance attributes (%s/%s)",
        "too-many-instance-attributes",
        "Used when class has too many instance attributes, try to reduce "
        "this to get a simpler (and so easier to use) class.",
    ),
    "R0903": (
        "Too few public methods (%s/%s)",
        "too-few-public-methods",
        "Used when class has too few public methods, so be sure it's "
        "really worth it.",
    ),
    "R0904": (
        "Too many public methods (%s/%s)",
        "too-many-public-methods",
        "Used when class has too many public methods, try to reduce "
        "this to get a simpler (and so easier to use) class.",
    ),
    "R0911": (
        "Too many return statements (%s/%s)",
        "too-many-return-statements",
        "Used when a function or method has too many return statement, "
        "making it hard to follow.",
    ),
    "R0912": (
        "Too many branches (%s/%s)",
        "too-many-branches",
        "Used when a function or method has too many branches, "
        "making it hard to follow.",
    ),
    "R0913": (
        "Too many arguments (%s/%s)",
        "too-many-arguments",
        "Used when a function or method takes too many arguments.",
    ),
    "R0914": (
        "Too many local variables (%s/%s)",
        "too-many-locals",
        "Used when a function or method has too many local variables.",
    ),
    "R0915": (
        "Too many statements (%s/%s)",
        "too-many-statements",
        "Used when a function or method has too many statements. You "
        "should then split it in smaller functions / methods.",
    ),
    "R0916": (
        "Too many boolean expressions in if statement (%s/%s)",
        "too-many-boolean-expressions",
        "Used when an if statement contains too many boolean expressions.",
    ),
}
SPECIAL_OBJ = re.compile("^_{2}[a-z]+_{2}$")
DATACLASSES_DECORATORS = frozenset({"dataclass", "attrs"})
DATACLASS_IMPORT = "dataclasses"
TYPING_NAMEDTUPLE = "typing.NamedTuple"
TYPING_TYPEDDICT = "typing.TypedDict"

# Set of stdlib classes to ignore when calculating number of ancestors
STDLIB_CLASSES_IGNORE_ANCESTOR = frozenset(
    (
        "builtins.object",
        "builtins.tuple",
        "builtins.dict",
        "builtins.list",
        "builtins.set",
        "bulitins.frozenset",
        "collections.ChainMap",
        "collections.Counter",
        "collections.OrderedDict",
        "collections.UserDict",
        "collections.UserList",
        "collections.UserString",
        "collections.defaultdict",
        "collections.deque",
        "collections.namedtuple",
        "_collections_abc.Awaitable",
        "_collections_abc.Coroutine",
        "_collections_abc.AsyncIterable",
        "_collections_abc.AsyncIterator",
        "_collections_abc.AsyncGenerator",
        "_collections_abc.Hashable",
        "_collections_abc.Iterable",
        "_collections_abc.Iterator",
        "_collections_abc.Generator",
        "_collections_abc.Reversible",
        "_collections_abc.Sized",
        "_collections_abc.Container",
        "_collections_abc.Collection",
        "_collections_abc.Set",
        "_collections_abc.MutableSet",
        "_collections_abc.Mapping",
        "_collections_abc.MutableMapping",
        "_collections_abc.MappingView",
        "_collections_abc.KeysView",
        "_collections_abc.ItemsView",
        "_collections_abc.ValuesView",
        "_collections_abc.Sequence",
        "_collections_abc.MutableSequence",
        "_collections_abc.ByteString",
        "typing.Tuple",
        "typing.List",
        "typing.Dict",
        "typing.Set",
        "typing.FrozenSet",
        "typing.Deque",
        "typing.DefaultDict",
        "typing.OrderedDict",
        "typing.Counter",
        "typing.ChainMap",
        "typing.Awaitable",
        "typing.Coroutine",
        "typing.AsyncIterable",
        "typing.AsyncIterator",
        "typing.AsyncGenerator",
        "typing.Iterable",
        "typing.Iterator",
        "typing.Generator",
        "typing.Reversible",
        "typing.Container",
        "typing.Collection",
        "typing.AbstractSet",
        "typing.MutableSet",
        "typing.Mapping",
        "typing.MutableMapping",
        "typing.Sequence",
        "typing.MutableSequence",
        "typing.ByteString",
        "typing.MappingView",
        "typing.KeysView",
        "typing.ItemsView",
        "typing.ValuesView",
        "typing.ContextManager",
        "typing.AsyncContextManager",
        "typing.Hashable",
        "typing.Sized",
    )
)


def _is_exempt_from_public_methods(node: astroid.ClassDef) -> bool:
    """Check if a class is exempt from too-few-public-methods."""

    # If it's a typing.Namedtuple, typing.TypedDict or an Enum
    for ancestor in node.ancestors():
        if is_enum(ancestor):
            return True
        if ancestor.qname() in (TYPING_NAMEDTUPLE, TYPING_TYPEDDICT):
            return True

    # Or if it's a dataclass
    if not node.decorators:
        return False

    root_locals = set(node.root().locals)
    for decorator in node.decorators.nodes:
        if isinstance(decorator, astroid.Call):
            decorator = decorator.func
        if not isinstance(decorator, (astroid.Name, astroid.Attribute)):
            continue
        if isinstance(decorator, astroid.Name):
            name = decorator.name
        else:
            name = decorator.attrname
        if name in DATACLASSES_DECORATORS and (
            root_locals.intersection(DATACLASSES_DECORATORS)
            or DATACLASS_IMPORT in root_locals
        ):
            return True
    return False


def _count_boolean_expressions(bool_op: nodes.BoolOp) -> int:
    """Counts the number of boolean expressions in BoolOp `bool_op` (recursive).

    example: a and (b or c or (d and e)) ==> 5 boolean expressions
    """
    nb_bool_expr = 0
    for bool_expr in bool_op.get_children():
        if isinstance(bool_expr, astroid.BoolOp):
            nb_bool_expr += _count_boolean_expressions(bool_expr)
        else:
            nb_bool_expr += 1
    return nb_bool_expr


def _count_methods_in_class(node: nodes.ClassDef) -> int:
    all_methods = sum(1 for method in node.methods() if not method.name.startswith("_"))
    # Special methods count towards the number of public methods,
    # but don't count towards there being too many methods.
    for method in node.mymethods():
        if SPECIAL_OBJ.search(method.name) and method.name != "__init__":
            all_methods += 1
    return all_methods


def _get_parents_iter(
    node: nodes.ClassDef, ignored_parents: frozenset[str]
) -> Iterator[nodes.ClassDef]:
    r"""Get parents of ``node``, excluding ancestors of ``ignored_parents``.

    If we have the following inheritance diagram:

             F
            /
        D  E
         \/
          B  C
           \/
            A      # class A(B, C): ...

    And ``ignored_parents`` is ``{"E"}``, then this function will return
    ``{A, B, C, D}`` -- both ``E`` and its ancestors are excluded.
    """
    parents: set[nodes.ClassDef] = set()
    to_explore = list(node.ancestors(recurs=False))
    while to_explore:
        parent = to_explore.pop()
        if parent.qname() in ignored_parents:
            continue
        if parent not in parents:
            # This guard might appear to be performing the same function as
            # adding the resolved parents to a set to eliminate duplicates
            # (legitimate due to diamond inheritance patterns), but its
            # additional purpose is to prevent cycles (not normally possible,
            # but potential due to inference) and thus guarantee termination
            # of the while-loop
            yield parent
            parents.add(parent)
            to_explore.extend(parent.ancestors(recurs=False))


def _get_parents(
    node: nodes.ClassDef, ignored_parents: frozenset[str]
) -> set[nodes.ClassDef]:
    return set(_get_parents_iter(node, ignored_parents))


class MisdesignChecker(BaseChecker):
    """Checker of potential misdesigns.

    Checks for sign of poor/misdesign:
    * number of methods, attributes, local variables...
    * size, complexity of functions, methods
    """

    # configuration section name
    name = "design"
    # messages
    msgs = MSGS
    # configuration options
    options = (
        (
            "max-args",
            {
                "default": 5,
                "type": "int",
                "metavar": "<int>",
                "help": "Maximum number of arguments for function / method.",
            },
        ),
        (
            "max-locals",
            {
                "default": 15,
                "type": "int",
                "metavar": "<int>",
                "help": "Maximum number of locals for function / method body.",
            },
        ),
        (
            "max-returns",
            {
                "default": 6,
                "type": "int",
                "metavar": "<int>",
                "help": "Maximum number of return / yield for function / "
                "method body.",
            },
        ),
        (
            "max-branches",
            {
                "default": 12,
                "type": "int",
                "metavar": "<int>",
                "help": "Maximum number of branch for function / method body.",
            },
        ),
        (
            "max-statements",
            {
                "default": 50,
                "type": "int",
                "metavar": "<int>",
                "help": "Maximum number of statements in function / method body.",
            },
        ),
        (
            "max-parents",
            {
                "default": 7,
                "type": "int",
                "metavar": "<num>",
                "help": "Maximum number of parents for a class (see R0901).",
            },
        ),
        (
            "ignored-parents",
            {
                "default": (),
                "type": "csv",
                "metavar": "<comma separated list of class names>",
                "help": "List of qualified class names to ignore when counting class parents (see R0901)",
            },
        ),
        (
            "max-attributes",
            {
                "default": 7,
                "type": "int",
                "metavar": "<num>",
                "help": "Maximum number of attributes for a class \
(see R0902).",
            },
        ),
        (
            "min-public-methods",
            {
                "default": 2,
                "type": "int",
                "metavar": "<num>",
                "help": "Minimum number of public methods for a class \
(see R0903).",
            },
        ),
        (
            "max-public-methods",
            {
                "default": 20,
                "type": "int",
                "metavar": "<num>",
                "help": "Maximum number of public methods for a class \
(see R0904).",
            },
        ),
        (
            "max-bool-expr",
            {
                "default": 5,
                "type": "int",
                "metavar": "<num>",
                "help": "Maximum number of boolean expressions in an if "
                "statement (see R0916).",
            },
        ),
        (
            "exclude-too-few-public-methods",
            {
                "default": [],
                "type": "regexp_csv",
                "metavar": "<pattern>[,<pattern>...]",
                "help": "List of regular expressions of class ancestor names "
                "to ignore when counting public methods (see R0903)",
            },
        ),
    )

    def __init__(self, linter: PyLinter) -> None:
        super().__init__(linter)
        self._returns: list[int]
        self._branches: defaultdict[nodes.LocalsDictNodeNG, int]
        self._stmts: list[int]

    def open(self) -> None:
        """Initialize visit variables."""
        self.linter.stats.reset_node_count()
        self._returns = []
        self._branches = defaultdict(int)
        self._stmts = []
        self._exclude_too_few_public_methods = (
            self.linter.config.exclude_too_few_public_methods
        )

    def _inc_all_stmts(self, amount: int) -> None:
        for i, _ in enumerate(self._stmts):
            self._stmts[i] += amount

    @only_required_for_messages(
        "too-many-ancestors",
        "too-many-instance-attributes",
        "too-few-public-methods",
        "too-many-public-methods",
    )
    def visit_classdef(self, node: nodes.ClassDef) -> None:
        """Check size of inheritance hierarchy and number of instance attributes."""
        parents = _get_parents(
            node,
            STDLIB_CLASSES_IGNORE_ANCESTOR.union(self.linter.config.ignored_parents),
        )
        nb_parents = len(parents)
        if nb_parents > self.linter.config.max_parents:
            self.add_message(
                "too-many-ancestors",
                node=node,
                args=(nb_parents, self.linter.config.max_parents),
            )

        if len(node.instance_attrs) > self.linter.config.max_attributes:
            self.add_message(
                "too-many-instance-attributes",
                node=node,
                args=(len(node.instance_attrs), self.linter.config.max_attributes),
            )

    @only_required_for_messages("too-few-public-methods", "too-many-public-methods")
    def leave_classdef(self, node: nodes.ClassDef) -> None:
        """Check number of public methods."""
        my_methods = sum(
            1 for method in node.mymethods() if not method.name.startswith("_")
        )

        # Does the class contain less than n public methods ?
        # This checks only the methods defined in the current class,
        # since the user might not have control over the classes
        # from the ancestors. It avoids some false positives
        # for classes such as unittest.TestCase, which provides
        # a lot of assert methods. It doesn't make sense to warn
        # when the user subclasses TestCase to add his own tests.
        if my_methods > self.linter.config.max_public_methods:
            self.add_message(
                "too-many-public-methods",
                node=node,
                args=(my_methods, self.linter.config.max_public_methods),
            )

        # Stop here if the class is excluded via configuration.
        if node.type == "class" and self._exclude_too_few_public_methods:
            for ancestor in node.ancestors():
                if any(
                    pattern.match(ancestor.qname())
                    for pattern in self._exclude_too_few_public_methods
                ):
                    return

        # Stop here for exception, metaclass, interface classes and other
        # classes for which we don't need to count the methods.
        if node.type != "class" or _is_exempt_from_public_methods(node):
            return

        # Does the class contain more than n public methods ?
        # This checks all the methods defined by ancestors and
        # by the current class.
        all_methods = _count_methods_in_class(node)
        if all_methods < self.linter.config.min_public_methods:
            self.add_message(
                "too-few-public-methods",
                node=node,
                args=(all_methods, self.linter.config.min_public_methods),
            )

    @only_required_for_messages(
        "too-many-return-statements",
        "too-many-branches",
        "too-many-arguments",
        "too-many-locals",
        "too-many-statements",
        "keyword-arg-before-vararg",
    )
    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Check function name, docstring, arguments, redefinition,
        variable names, max locals.
        """
        # init branch and returns counters
        self._returns.append(0)
        # check number of arguments
        args = node.args.args
        ignored_argument_names = self.linter.config.ignored_argument_names
        if args is not None:
            ignored_args_num = 0
            if ignored_argument_names:
                ignored_args_num = sum(
                    1 for arg in args if ignored_argument_names.match(arg.name)
                )

            argnum = len(args) - ignored_args_num
            if argnum > self.linter.config.max_args:
                self.add_message(
                    "too-many-arguments",
                    node=node,
                    args=(len(args), self.linter.config.max_args),
                )
        else:
            ignored_args_num = 0
        # check number of local variables
        locnum = len(node.locals) - ignored_args_num

        # decrement number of local variables if '_' is one of them
        if "_" in node.locals:
            locnum -= 1

        if locnum > self.linter.config.max_locals:
            self.add_message(
                "too-many-locals",
                node=node,
                args=(locnum, self.linter.config.max_locals),
            )
        # init new statements counter
        self._stmts.append(1)

    visit_asyncfunctiondef = visit_functiondef

    @only_required_for_messages(
        "too-many-return-statements",
        "too-many-branches",
        "too-many-arguments",
        "too-many-locals",
        "too-many-statements",
    )
    def leave_functiondef(self, node: nodes.FunctionDef) -> None:
        """Most of the work is done here on close:
        checks for max returns, branch, return in __init__.
        """
        returns = self._returns.pop()
        if returns > self.linter.config.max_returns:
            self.add_message(
                "too-many-return-statements",
                node=node,
                args=(returns, self.linter.config.max_returns),
            )
        branches = self._branches[node]
        if branches > self.linter.config.max_branches:
            self.add_message(
                "too-many-branches",
                node=node,
                args=(branches, self.linter.config.max_branches),
            )
        # check number of statements
        stmts = self._stmts.pop()
        if stmts > self.linter.config.max_statements:
            self.add_message(
                "too-many-statements",
                node=node,
                args=(stmts, self.linter.config.max_statements),
            )

    leave_asyncfunctiondef = leave_functiondef

    def visit_return(self, _: nodes.Return) -> None:
        """Count number of returns."""
        if not self._returns:
            return  # return outside function, reported by the base checker
        self._returns[-1] += 1

    def visit_default(self, node: nodes.NodeNG) -> None:
        """Default visit method -> increments the statements counter if
        necessary.
        """
        if node.is_statement:
            self._inc_all_stmts(1)

    def visit_tryexcept(self, node: nodes.TryExcept) -> None:
        """Increments the branches counter."""
        branches = len(node.handlers)
        if node.orelse:
            branches += 1
        self._inc_branch(node, branches)
        self._inc_all_stmts(branches)

    def visit_tryfinally(self, node: nodes.TryFinally) -> None:
        """Increments the branches counter."""
        self._inc_branch(node, 2)
        self._inc_all_stmts(2)

    @only_required_for_messages("too-many-boolean-expressions", "too-many-branches")
    def visit_if(self, node: nodes.If) -> None:
        """Increments the branches counter and checks boolean expressions."""
        self._check_boolean_expressions(node)
        branches = 1
        # don't double count If nodes coming from some 'elif'
        if node.orelse and (
            len(node.orelse) > 1 or not isinstance(node.orelse[0], astroid.If)
        ):
            branches += 1
        self._inc_branch(node, branches)
        self._inc_all_stmts(branches)

    def _check_boolean_expressions(self, node: nodes.If) -> None:
        """Go through "if" node `node` and count its boolean expressions
        if the 'if' node test is a BoolOp node.
        """
        condition = node.test
        if not isinstance(condition, astroid.BoolOp):
            return
        nb_bool_expr = _count_boolean_expressions(condition)
        if nb_bool_expr > self.linter.config.max_bool_expr:
            self.add_message(
                "too-many-boolean-expressions",
                node=condition,
                args=(nb_bool_expr, self.linter.config.max_bool_expr),
            )

    def visit_while(self, node: nodes.While) -> None:
        """Increments the branches counter."""
        branches = 1
        if node.orelse:
            branches += 1
        self._inc_branch(node, branches)

    visit_for = visit_while

    def _inc_branch(self, node: nodes.NodeNG, branchesnum: int = 1) -> None:
        """Increments the branches counter."""
        self._branches[node.scope()] += branchesnum


def register(linter: PyLinter) -> None:
    linter.register_checker(MisdesignChecker(linter))
