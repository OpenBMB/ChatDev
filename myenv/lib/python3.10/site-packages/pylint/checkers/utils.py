# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Some functions that may be useful for various checkers."""

from __future__ import annotations

import builtins
import fnmatch
import itertools
import numbers
import re
import string
import warnings
from collections import deque
from collections.abc import Iterable, Iterator
from functools import lru_cache, partial
from re import Match
from typing import TYPE_CHECKING, Callable, TypeVar

import _string
import astroid.objects
from astroid import TooManyLevelsError, nodes, util
from astroid.context import InferenceContext
from astroid.exceptions import AstroidError
from astroid.nodes._base_nodes import ImportNode
from astroid.typing import InferenceResult, SuccessfulInferenceResult

if TYPE_CHECKING:
    from pylint.checkers import BaseChecker

_NodeT = TypeVar("_NodeT", bound=nodes.NodeNG)
_CheckerT = TypeVar("_CheckerT", bound="BaseChecker")
AstCallbackMethod = Callable[[_CheckerT, _NodeT], None]

COMP_NODE_TYPES = (
    nodes.ListComp,
    nodes.SetComp,
    nodes.DictComp,
    nodes.GeneratorExp,
)
EXCEPTIONS_MODULE = "builtins"
ABC_MODULES = {"abc", "_py_abc"}
ABC_METHODS = {
    "abc.abstractproperty",
    "abc.abstractmethod",
    "abc.abstractclassmethod",
    "abc.abstractstaticmethod",
}
TYPING_PROTOCOLS = frozenset(
    {"typing.Protocol", "typing_extensions.Protocol", ".Protocol"}
)
COMMUTATIVE_OPERATORS = frozenset({"*", "+", "^", "&", "|"})
ITER_METHOD = "__iter__"
AITER_METHOD = "__aiter__"
NEXT_METHOD = "__next__"
GETITEM_METHOD = "__getitem__"
CLASS_GETITEM_METHOD = "__class_getitem__"
SETITEM_METHOD = "__setitem__"
DELITEM_METHOD = "__delitem__"
CONTAINS_METHOD = "__contains__"
KEYS_METHOD = "keys"

# Dictionary which maps the number of expected parameters a
# special method can have to a set of special methods.
# The following keys are used to denote the parameters restrictions:
#
# * None: variable number of parameters
# * number: exactly that number of parameters
# * tuple: these are the odd ones. Basically it means that the function
#          can work with any number of arguments from that tuple,
#          although it's best to implement it in order to accept
#          all of them.
_SPECIAL_METHODS_PARAMS = {
    None: ("__new__", "__init__", "__call__", "__init_subclass__"),
    0: (
        "__del__",
        "__repr__",
        "__str__",
        "__bytes__",
        "__hash__",
        "__bool__",
        "__dir__",
        "__len__",
        "__length_hint__",
        "__iter__",
        "__reversed__",
        "__neg__",
        "__pos__",
        "__abs__",
        "__invert__",
        "__complex__",
        "__int__",
        "__float__",
        "__index__",
        "__trunc__",
        "__floor__",
        "__ceil__",
        "__enter__",
        "__aenter__",
        "__getnewargs_ex__",
        "__getnewargs__",
        "__getstate__",
        "__reduce__",
        "__copy__",
        "__unicode__",
        "__nonzero__",
        "__await__",
        "__aiter__",
        "__anext__",
        "__fspath__",
        "__subclasses__",
    ),
    1: (
        "__format__",
        "__lt__",
        "__le__",
        "__eq__",
        "__ne__",
        "__gt__",
        "__ge__",
        "__getattr__",
        "__getattribute__",
        "__delattr__",
        "__delete__",
        "__instancecheck__",
        "__subclasscheck__",
        "__getitem__",
        "__missing__",
        "__delitem__",
        "__contains__",
        "__add__",
        "__sub__",
        "__mul__",
        "__truediv__",
        "__floordiv__",
        "__rfloordiv__",
        "__mod__",
        "__divmod__",
        "__lshift__",
        "__rshift__",
        "__and__",
        "__xor__",
        "__or__",
        "__radd__",
        "__rsub__",
        "__rmul__",
        "__rtruediv__",
        "__rmod__",
        "__rdivmod__",
        "__rpow__",
        "__rlshift__",
        "__rrshift__",
        "__rand__",
        "__rxor__",
        "__ror__",
        "__iadd__",
        "__isub__",
        "__imul__",
        "__itruediv__",
        "__ifloordiv__",
        "__imod__",
        "__ilshift__",
        "__irshift__",
        "__iand__",
        "__ixor__",
        "__ior__",
        "__ipow__",
        "__setstate__",
        "__reduce_ex__",
        "__deepcopy__",
        "__cmp__",
        "__matmul__",
        "__rmatmul__",
        "__imatmul__",
        "__div__",
    ),
    2: ("__setattr__", "__get__", "__set__", "__setitem__", "__set_name__"),
    3: ("__exit__", "__aexit__"),
    (0, 1): ("__round__",),
    (1, 2): ("__pow__",),
}

SPECIAL_METHODS_PARAMS = {
    name: params
    for params, methods in _SPECIAL_METHODS_PARAMS.items()
    for name in methods
}
PYMETHODS = set(SPECIAL_METHODS_PARAMS)

SUBSCRIPTABLE_CLASSES_PEP585 = frozenset(
    (
        "builtins.tuple",
        "builtins.list",
        "builtins.dict",
        "builtins.set",
        "builtins.frozenset",
        "builtins.type",
        "collections.deque",
        "collections.defaultdict",
        "collections.OrderedDict",
        "collections.Counter",
        "collections.ChainMap",
        "_collections_abc.Awaitable",
        "_collections_abc.Coroutine",
        "_collections_abc.AsyncIterable",
        "_collections_abc.AsyncIterator",
        "_collections_abc.AsyncGenerator",
        "_collections_abc.Iterable",
        "_collections_abc.Iterator",
        "_collections_abc.Generator",
        "_collections_abc.Reversible",
        "_collections_abc.Container",
        "_collections_abc.Collection",
        "_collections_abc.Callable",
        "_collections_abc.Set",
        "_collections_abc.MutableSet",
        "_collections_abc.Mapping",
        "_collections_abc.MutableMapping",
        "_collections_abc.Sequence",
        "_collections_abc.MutableSequence",
        "_collections_abc.ByteString",
        "_collections_abc.MappingView",
        "_collections_abc.KeysView",
        "_collections_abc.ItemsView",
        "_collections_abc.ValuesView",
        "contextlib.AbstractContextManager",
        "contextlib.AbstractAsyncContextManager",
        "re.Pattern",
        "re.Match",
    )
)

SINGLETON_VALUES = {True, False, None}

TERMINATING_FUNCS_QNAMES = frozenset(
    {"_sitebuiltins.Quitter", "sys.exit", "posix._exit", "nt._exit"}
)


class NoSuchArgumentError(Exception):
    pass


class InferredTypeError(Exception):
    pass


def is_inside_lambda(node: nodes.NodeNG) -> bool:
    """Return whether the given node is inside a lambda."""
    warnings.warn(
        "utils.is_inside_lambda will be removed in favour of calling "
        "utils.get_node_first_ancestor_of_type(x, nodes.Lambda) in pylint 3.0",
        DeprecationWarning,
        stacklevel=2,
    )
    return any(isinstance(parent, nodes.Lambda) for parent in node.node_ancestors())


def get_all_elements(
    node: nodes.NodeNG,
) -> Iterable[nodes.NodeNG]:
    """Recursively returns all atoms in nested lists and tuples."""
    if isinstance(node, (nodes.Tuple, nodes.List)):
        for child in node.elts:
            yield from get_all_elements(child)
    else:
        yield node


def is_super(node: nodes.NodeNG) -> bool:
    """Return True if the node is referencing the "super" builtin function."""
    if getattr(node, "name", None) == "super" and node.root().name == "builtins":
        return True
    return False


def is_error(node: nodes.FunctionDef) -> bool:
    """Return true if the given function node only raises an exception."""
    return len(node.body) == 1 and isinstance(node.body[0], nodes.Raise)


builtins = builtins.__dict__.copy()  # type: ignore[assignment]
SPECIAL_BUILTINS = ("__builtins__",)  # '__path__', '__file__')


def is_builtin_object(node: nodes.NodeNG) -> bool:
    """Returns True if the given node is an object from the __builtin__ module."""
    return node and node.root().name == "builtins"  # type: ignore[no-any-return]


def is_builtin(name: str) -> bool:
    """Return true if <name> could be considered as a builtin defined by python."""
    return name in builtins or name in SPECIAL_BUILTINS  # type: ignore[operator]


def is_defined_in_scope(
    var_node: nodes.NodeNG,
    varname: str,
    scope: nodes.NodeNG,
) -> bool:
    return defnode_in_scope(var_node, varname, scope) is not None


# pylint: disable = too-many-branches
def defnode_in_scope(
    var_node: nodes.NodeNG,
    varname: str,
    scope: nodes.NodeNG,
) -> nodes.NodeNG | None:
    if isinstance(scope, nodes.If):
        for node in scope.body:
            if isinstance(node, nodes.Nonlocal) and varname in node.names:
                return node
            if isinstance(node, nodes.Assign):
                for target in node.targets:
                    if isinstance(target, nodes.AssignName) and target.name == varname:
                        return target
    elif isinstance(scope, (COMP_NODE_TYPES, nodes.For)):
        for ass_node in scope.nodes_of_class(nodes.AssignName):
            if ass_node.name == varname:
                return ass_node
    elif isinstance(scope, nodes.With):
        for expr, ids in scope.items:
            if expr.parent_of(var_node):
                break
            if ids and isinstance(ids, nodes.AssignName) and ids.name == varname:
                return ids
    elif isinstance(scope, (nodes.Lambda, nodes.FunctionDef)):
        if scope.args.is_argument(varname):
            # If the name is found inside a default value
            # of a function, then let the search continue
            # in the parent's tree.
            if scope.args.parent_of(var_node):
                try:
                    scope.args.default_value(varname)
                    scope = scope.parent
                    defnode = defnode_in_scope(var_node, varname, scope)
                except astroid.NoDefault:
                    pass
                else:
                    return defnode
            return scope
        if getattr(scope, "name", None) == varname:
            return scope
    elif isinstance(scope, nodes.ExceptHandler):
        if isinstance(scope.name, nodes.AssignName):
            ass_node = scope.name
            if ass_node.name == varname:
                return ass_node
    return None


def is_defined_before(var_node: nodes.Name) -> bool:
    """Check if the given variable node is defined before.

    Verify that the variable node is defined by a parent node
    (e.g. if or with) earlier than `var_node`, or is defined by a
    (list, set, dict, or generator comprehension, lambda)
    or in a previous sibling node on the same line
    (statement_defining ; statement_using).
    """
    varname = var_node.name
    for parent in var_node.node_ancestors():
        defnode = defnode_in_scope(var_node, varname, parent)
        if defnode is None:
            continue
        defnode_scope = defnode.scope()
        if isinstance(defnode_scope, COMP_NODE_TYPES + (nodes.Lambda,)):
            # Avoid the case where var_node_scope is a nested function
            # FunctionDef is a Lambda until https://github.com/PyCQA/astroid/issues/291
            if isinstance(defnode_scope, nodes.FunctionDef):
                var_node_scope = var_node.scope()
                if var_node_scope is not defnode_scope and isinstance(
                    var_node_scope, nodes.FunctionDef
                ):
                    return False
            return True
        if defnode.lineno < var_node.lineno:
            return True
        # `defnode` and `var_node` on the same line
        for defnode_anc in defnode.node_ancestors():
            if defnode_anc.lineno != var_node.lineno:
                continue
            if isinstance(
                defnode_anc,
                (
                    nodes.For,
                    nodes.While,
                    nodes.With,
                    nodes.TryExcept,
                    nodes.TryFinally,
                    nodes.ExceptHandler,
                ),
            ):
                return True
    # possibly multiple statements on the same line using semicolon separator
    stmt = var_node.statement(future=True)
    _node = stmt.previous_sibling()
    lineno = stmt.fromlineno
    while _node and _node.fromlineno == lineno:
        for assign_node in _node.nodes_of_class(nodes.AssignName):
            if assign_node.name == varname:
                return True
        for imp_node in _node.nodes_of_class((nodes.ImportFrom, nodes.Import)):
            if varname in [name[1] or name[0] for name in imp_node.names]:
                return True
        _node = _node.previous_sibling()
    return False


def is_default_argument(node: nodes.NodeNG, scope: nodes.NodeNG | None = None) -> bool:
    """Return true if the given Name node is used in function or lambda
    default argument's value.
    """
    if not scope:
        scope = node.scope()
    if isinstance(scope, (nodes.FunctionDef, nodes.Lambda)):
        all_defaults = itertools.chain(
            scope.args.defaults, (d for d in scope.args.kw_defaults if d is not None)
        )
        return any(
            default_name_node is node
            for default_node in all_defaults
            for default_name_node in default_node.nodes_of_class(nodes.Name)
        )

    return False


def is_func_decorator(node: nodes.NodeNG) -> bool:
    """Return true if the name is used in function decorator."""
    for parent in node.node_ancestors():
        if isinstance(parent, nodes.Decorators):
            return True
        if parent.is_statement or isinstance(
            parent,
            (
                nodes.Lambda,
                nodes.ComprehensionScope,
                nodes.ListComp,
            ),
        ):
            break
    return False


def is_ancestor_name(frame: nodes.ClassDef, node: nodes.NodeNG) -> bool:
    """Return whether `frame` is an astroid.Class node with `node` in the
    subtree of its bases attribute.
    """
    if not isinstance(frame, nodes.ClassDef):
        return False
    return any(node in base.nodes_of_class(nodes.Name) for base in frame.bases)


def is_being_called(node: nodes.NodeNG) -> bool:
    """Return True if node is the function being called in a Call node."""
    return isinstance(node.parent, nodes.Call) and node.parent.func is node


def assign_parent(node: nodes.NodeNG) -> nodes.NodeNG:
    """Return the higher parent which is not an AssignName, Tuple or List node."""
    while node and isinstance(node, (nodes.AssignName, nodes.Tuple, nodes.List)):
        node = node.parent
    return node


def overrides_a_method(class_node: nodes.ClassDef, name: str) -> bool:
    """Return True if <name> is a method overridden from an ancestor
    which is not the base object class.
    """
    for ancestor in class_node.ancestors():
        if ancestor.name == "object":
            continue
        if name in ancestor and isinstance(ancestor[name], nodes.FunctionDef):
            return True
    return False


def only_required_for_messages(
    *messages: str,
) -> Callable[
    [AstCallbackMethod[_CheckerT, _NodeT]], AstCallbackMethod[_CheckerT, _NodeT]
]:
    """Decorator to store messages that are handled by a checker method as an
    attribute of the function object.

    This information is used by ``ASTWalker`` to decide whether to call the decorated
    method or not. If none of the messages is enabled, the method will be skipped.
    Therefore, the list of messages must be well maintained at all times!
    This decorator only has an effect on ``visit_*`` and ``leave_*`` methods
    of a class inheriting from ``BaseChecker``.
    """

    def store_messages(
        func: AstCallbackMethod[_CheckerT, _NodeT]
    ) -> AstCallbackMethod[_CheckerT, _NodeT]:
        func.checks_msgs = messages  # type: ignore[attr-defined]
        return func

    return store_messages


def check_messages(
    *messages: str,
) -> Callable[
    [AstCallbackMethod[_CheckerT, _NodeT]], AstCallbackMethod[_CheckerT, _NodeT]
]:
    """Kept for backwards compatibility, deprecated.

    Use only_required_for_messages instead, which conveys the intent of the decorator much clearer.
    """
    warnings.warn(
        "utils.check_messages will be removed in favour of calling "
        "utils.only_required_for_messages in pylint 3.0",
        DeprecationWarning,
        stacklevel=2,
    )

    return only_required_for_messages(*messages)


class IncompleteFormatString(Exception):
    """A format string ended in the middle of a format specifier."""


class UnsupportedFormatCharacter(Exception):
    """A format character in a format string is not one of the supported
    format characters.
    """

    def __init__(self, index: int) -> None:
        super().__init__(index)
        self.index = index


def parse_format_string(
    format_string: str,
) -> tuple[set[str], int, dict[str, str], list[str]]:
    """Parses a format string, returning a tuple (keys, num_args).

    Where 'keys' is the set of mapping keys in the format string, and 'num_args' is the number
    of arguments required by the format string. Raises IncompleteFormatString or
    UnsupportedFormatCharacter if a parse error occurs.
    """
    keys = set()
    key_types = {}
    pos_types = []
    num_args = 0

    def next_char(i: int) -> tuple[int, str]:
        i += 1
        if i == len(format_string):
            raise IncompleteFormatString
        return (i, format_string[i])

    i = 0
    while i < len(format_string):
        char = format_string[i]
        if char == "%":
            i, char = next_char(i)
            # Parse the mapping key (optional).
            key = None
            if char == "(":
                depth = 1
                i, char = next_char(i)
                key_start = i
                while depth != 0:
                    if char == "(":
                        depth += 1
                    elif char == ")":
                        depth -= 1
                    i, char = next_char(i)
                key_end = i - 1
                key = format_string[key_start:key_end]

            # Parse the conversion flags (optional).
            while char in "#0- +":
                i, char = next_char(i)
            # Parse the minimum field width (optional).
            if char == "*":
                num_args += 1
                i, char = next_char(i)
            else:
                while char in string.digits:
                    i, char = next_char(i)
            # Parse the precision (optional).
            if char == ".":
                i, char = next_char(i)
                if char == "*":
                    num_args += 1
                    i, char = next_char(i)
                else:
                    while char in string.digits:
                        i, char = next_char(i)
            # Parse the length modifier (optional).
            if char in "hlL":
                i, char = next_char(i)
            # Parse the conversion type (mandatory).
            flags = "diouxXeEfFgGcrs%a"
            if char not in flags:
                raise UnsupportedFormatCharacter(i)
            if key:
                keys.add(key)
                key_types[key] = char
            elif char != "%":
                num_args += 1
                pos_types.append(char)
        i += 1
    return keys, num_args, key_types, pos_types


def split_format_field_names(
    format_string: str,
) -> tuple[str, Iterable[tuple[bool, str]]]:
    try:
        return _string.formatter_field_name_split(format_string)  # type: ignore[no-any-return]
    except ValueError as e:
        raise IncompleteFormatString() from e


def collect_string_fields(format_string: str) -> Iterable[str | None]:
    """Given a format string, return an iterator
    of all the valid format fields.

    It handles nested fields as well.
    """
    formatter = string.Formatter()
    # pylint: disable = too-many-try-statements
    try:
        parseiterator = formatter.parse(format_string)
        for result in parseiterator:
            if all(item is None for item in result[1:]):
                # not a replacement format
                continue
            name = result[1]
            nested = result[2]
            yield name
            if nested:
                yield from collect_string_fields(nested)
    except ValueError as exc:
        # Probably the format string is invalid.
        if exc.args[0].startswith("cannot switch from manual"):
            # On Jython, parsing a string with both manual
            # and automatic positions will fail with a ValueError,
            # while on CPython it will simply return the fields,
            # the validation being done in the interpreter (?).
            # We're just returning two mixed fields in order
            # to trigger the format-combined-specification check.
            yield ""
            yield "1"
            return
        raise IncompleteFormatString(format_string) from exc


def parse_format_method_string(
    format_string: str,
) -> tuple[list[tuple[str, list[tuple[bool, str]]]], int, int]:
    """Parses a PEP 3101 format string, returning a tuple of
    (keyword_arguments, implicit_pos_args_cnt, explicit_pos_args).

    keyword_arguments is the set of mapping keys in the format string, implicit_pos_args_cnt
    is the number of arguments required by the format string and
    explicit_pos_args is the number of arguments passed with the position.
    """
    keyword_arguments = []
    implicit_pos_args_cnt = 0
    explicit_pos_args = set()
    for name in collect_string_fields(format_string):
        if name and str(name).isdigit():
            explicit_pos_args.add(str(name))
        elif name:
            keyname, fielditerator = split_format_field_names(name)
            if isinstance(keyname, numbers.Number):
                explicit_pos_args.add(str(keyname))
            try:
                keyword_arguments.append((keyname, list(fielditerator)))
            except ValueError as e:
                raise IncompleteFormatString() from e
        else:
            implicit_pos_args_cnt += 1
    return keyword_arguments, implicit_pos_args_cnt, len(explicit_pos_args)


def is_attr_protected(attrname: str) -> bool:
    """Return True if attribute name is protected (start with _ and some other
    details), False otherwise.
    """
    return (
        attrname[0] == "_"
        and attrname != "_"
        and not (attrname.startswith("__") and attrname.endswith("__"))
    )


def node_frame_class(node: nodes.NodeNG) -> nodes.ClassDef | None:
    """Return the class that is wrapping the given node.

    The function returns a class for a method node (or a staticmethod or a
    classmethod), otherwise it returns `None`.
    """
    klass = node.frame(future=True)
    nodes_to_check = (
        nodes.NodeNG,
        astroid.UnboundMethod,
        astroid.BaseInstance,
    )
    while (
        klass
        and isinstance(klass, nodes_to_check)
        and not isinstance(klass, nodes.ClassDef)
    ):
        if klass.parent is None:
            return None

        klass = klass.parent.frame(future=True)

    return klass


def get_outer_class(class_node: astroid.ClassDef) -> astroid.ClassDef | None:
    """Return the class that is the outer class of given (nested) class_node."""
    parent_klass = class_node.parent.frame(future=True)

    return parent_klass if isinstance(parent_klass, astroid.ClassDef) else None


def is_attr_private(attrname: str) -> Match[str] | None:
    """Check that attribute name is private (at least two leading underscores,
    at most one trailing underscore).
    """
    regex = re.compile("^_{2,10}.*[^_]+_?$")
    return regex.match(attrname)


def get_argument_from_call(
    call_node: nodes.Call, position: int | None = None, keyword: str | None = None
) -> nodes.Name:
    """Returns the specified argument from a function call.

    :param nodes.Call call_node: Node representing a function call to check.
    :param int position: position of the argument.
    :param str keyword: the keyword of the argument.

    :returns: The node representing the argument, None if the argument is not found.
    :rtype: nodes.Name
    :raises ValueError: if both position and keyword are None.
    :raises NoSuchArgumentError: if no argument at the provided position or with
    the provided keyword.
    """
    if position is None and keyword is None:
        raise ValueError("Must specify at least one of: position or keyword.")
    if position is not None:
        try:
            return call_node.args[position]
        except IndexError:
            pass
    if keyword and call_node.keywords:
        for arg in call_node.keywords:
            if arg.arg == keyword:
                return arg.value

    raise NoSuchArgumentError


def inherit_from_std_ex(node: nodes.NodeNG | astroid.Instance) -> bool:
    """Return whether the given class node is subclass of
    exceptions.Exception.
    """
    ancestors = node.ancestors() if hasattr(node, "ancestors") else []
    return any(
        ancestor.name in {"Exception", "BaseException"}
        and ancestor.root().name == EXCEPTIONS_MODULE
        for ancestor in itertools.chain([node], ancestors)
    )


def error_of_type(
    handler: nodes.ExceptHandler,
    error_type: str | type[Exception] | tuple[str | type[Exception], ...],
) -> bool:
    """Check if the given exception handler catches
    the given error_type.

    The *handler* parameter is a node, representing an ExceptHandler node.
    The *error_type* can be an exception, such as AttributeError,
    the name of an exception, or it can be a tuple of errors.
    The function will return True if the handler catches any of the
    given errors.
    """

    def stringify_error(error: str | type[Exception]) -> str:
        if not isinstance(error, str):
            return error.__name__
        return error

    if not isinstance(error_type, tuple):
        error_type = (error_type,)
    expected_errors = {stringify_error(error) for error in error_type}
    if not handler.type:
        return False
    return handler.catch(expected_errors)  # type: ignore[no-any-return]


def decorated_with_property(node: nodes.FunctionDef) -> bool:
    """Detect if the given function node is decorated with a property."""
    if not node.decorators:
        return False
    for decorator in node.decorators.nodes:
        try:
            if _is_property_decorator(decorator):
                return True
        except astroid.InferenceError:
            pass
    return False


def _is_property_kind(node: nodes.NodeNG, *kinds: str) -> bool:
    if not isinstance(node, (astroid.UnboundMethod, nodes.FunctionDef)):
        return False
    if node.decorators:
        for decorator in node.decorators.nodes:
            if isinstance(decorator, nodes.Attribute) and decorator.attrname in kinds:
                return True
    return False


def is_property_setter(node: nodes.NodeNG) -> bool:
    """Check if the given node is a property setter."""
    return _is_property_kind(node, "setter")


def is_property_deleter(node: nodes.NodeNG) -> bool:
    """Check if the given node is a property deleter."""
    return _is_property_kind(node, "deleter")


def is_property_setter_or_deleter(node: nodes.NodeNG) -> bool:
    """Check if the given node is either a property setter or a deleter."""
    return _is_property_kind(node, "setter", "deleter")


def _is_property_decorator(decorator: nodes.Name) -> bool:
    for inferred in decorator.infer():
        if isinstance(inferred, nodes.ClassDef):
            if inferred.qname() in {"builtins.property", "functools.cached_property"}:
                return True
            for ancestor in inferred.ancestors():
                if ancestor.name == "property" and ancestor.root().name == "builtins":
                    return True
        elif isinstance(inferred, nodes.FunctionDef):
            # If decorator is function, check if it has exactly one return
            # and the return is itself a function decorated with property
            returns: list[nodes.Return] = list(
                inferred._get_return_nodes_skip_functions()
            )
            if len(returns) == 1 and isinstance(
                returns[0].value, (nodes.Name, nodes.Attribute)
            ):
                inferred = safe_infer(returns[0].value)
                if (
                    inferred
                    and isinstance(inferred, astroid.objects.Property)
                    and isinstance(inferred.function, nodes.FunctionDef)
                ):
                    return decorated_with_property(inferred.function)
    return False


def decorated_with(
    func: (
        nodes.ClassDef | nodes.FunctionDef | astroid.BoundMethod | astroid.UnboundMethod
    ),
    qnames: Iterable[str],
) -> bool:
    """Determine if the `func` node has a decorator with the qualified name `qname`."""
    decorators = func.decorators.nodes if func.decorators else []
    for decorator_node in decorators:
        if isinstance(decorator_node, nodes.Call):
            # We only want to infer the function name
            decorator_node = decorator_node.func
        try:
            if any(
                i.name in qnames or i.qname() in qnames
                for i in decorator_node.infer()
                if i is not None and not isinstance(i, util.UninferableBase)
            ):
                return True
        except astroid.InferenceError:
            continue
    return False


def uninferable_final_decorators(
    node: nodes.Decorators,
) -> list[nodes.Attribute | nodes.Name | None]:
    """Return a list of uninferable `typing.final` decorators in `node`.

    This function is used to determine if the `typing.final` decorator is used
    with an unsupported Python version; the decorator cannot be inferred when
    using a Python version lower than 3.8.
    """
    decorators = []
    for decorator in getattr(node, "nodes", []):
        import_nodes: tuple[nodes.Import | nodes.ImportFrom] | None = None

        # Get the `Import` node. The decorator is of the form: @module.name
        if isinstance(decorator, nodes.Attribute):
            inferred = safe_infer(decorator.expr)
            if isinstance(inferred, nodes.Module) and inferred.qname() == "typing":
                _, import_nodes = decorator.expr.lookup(decorator.expr.name)

        # Get the `ImportFrom` node. The decorator is of the form: @name
        elif isinstance(decorator, nodes.Name):
            _, import_nodes = decorator.lookup(decorator.name)

        # The `final` decorator is expected to be found in the
        # import_nodes. Continue if we don't find any `Import` or `ImportFrom`
        # nodes for this decorator.
        if not import_nodes:
            continue
        import_node = import_nodes[0]

        if not isinstance(import_node, (astroid.Import, astroid.ImportFrom)):
            continue

        import_names = dict(import_node.names)

        # Check if the import is of the form: `from typing import final`
        is_from_import = ("final" in import_names) and import_node.modname == "typing"

        # Check if the import is of the form: `import typing`
        is_import = ("typing" in import_names) and getattr(
            decorator, "attrname", None
        ) == "final"

        if is_from_import or is_import:
            inferred = safe_infer(decorator)
            if inferred is None or isinstance(inferred, util.UninferableBase):
                decorators.append(decorator)
    return decorators


@lru_cache(maxsize=1024)
def unimplemented_abstract_methods(
    node: nodes.ClassDef, is_abstract_cb: nodes.FunctionDef = None
) -> dict[str, nodes.FunctionDef]:
    """Get the unimplemented abstract methods for the given *node*.

    A method can be considered abstract if the callback *is_abstract_cb*
    returns a ``True`` value. The check defaults to verifying that
    a method is decorated with abstract methods.
    It will return a dictionary of abstract method
    names and their inferred objects.
    """
    if is_abstract_cb is None:
        is_abstract_cb = partial(decorated_with, qnames=ABC_METHODS)
    visited: dict[str, nodes.FunctionDef] = {}
    try:
        mro = reversed(node.mro())
    except astroid.ResolveError:
        # Probably inconsistent hierarchy, don't try to figure this out here.
        return {}
    for ancestor in mro:
        for obj in ancestor.values():
            inferred = obj
            if isinstance(obj, nodes.AssignName):
                inferred = safe_infer(obj)
                if not inferred:
                    # Might be an abstract function,
                    # but since we don't have enough information
                    # in order to take this decision, we're taking
                    # the *safe* decision instead.
                    if obj.name in visited:
                        del visited[obj.name]
                    continue
                if not isinstance(inferred, nodes.FunctionDef):
                    if obj.name in visited:
                        del visited[obj.name]
            if isinstance(inferred, nodes.FunctionDef):
                # It's critical to use the original name,
                # since after inferring, an object can be something
                # else than expected, as in the case of the
                # following assignment.
                #
                # class A:
                #     def keys(self): pass
                #     __iter__ = keys
                abstract = is_abstract_cb(inferred)
                if abstract:
                    visited[obj.name] = inferred
                elif not abstract and obj.name in visited:
                    del visited[obj.name]
    return visited


def find_try_except_wrapper_node(
    node: nodes.NodeNG,
) -> nodes.ExceptHandler | nodes.TryExcept | None:
    """Return the ExceptHandler or the TryExcept node in which the node is."""
    current = node
    ignores = (nodes.ExceptHandler, nodes.TryExcept)
    while current and not isinstance(current.parent, ignores):
        current = current.parent

    if current and isinstance(current.parent, ignores):
        return current.parent
    return None


def find_except_wrapper_node_in_scope(
    node: nodes.NodeNG,
) -> nodes.ExceptHandler | nodes.TryExcept | None:
    """Return the ExceptHandler in which the node is, without going out of scope."""
    for current in node.node_ancestors():
        if isinstance(current, astroid.scoped_nodes.LocalsDictNodeNG):
            # If we're inside a function/class definition, we don't want to keep checking
            # higher ancestors for `except` clauses, because if these exist, it means our
            # function/class was defined in an `except` clause, rather than the current code
            # actually running in an `except` clause.
            return None
        if isinstance(current, nodes.ExceptHandler):
            return current
    return None


def is_from_fallback_block(node: nodes.NodeNG) -> bool:
    """Check if the given node is from a fallback import block."""
    context = find_try_except_wrapper_node(node)
    if not context:
        return False

    if isinstance(context, nodes.ExceptHandler):
        other_body = context.parent.body
        handlers = context.parent.handlers
    else:
        other_body = itertools.chain.from_iterable(
            handler.body for handler in context.handlers
        )
        handlers = context.handlers

    has_fallback_imports = any(
        isinstance(import_node, (nodes.ImportFrom, nodes.Import))
        for import_node in other_body
    )
    ignores_import_error = _except_handlers_ignores_exceptions(
        handlers, (ImportError, ModuleNotFoundError)
    )
    return ignores_import_error or has_fallback_imports


def _except_handlers_ignores_exceptions(
    handlers: nodes.ExceptHandler,
    exceptions: tuple[type[ImportError], type[ModuleNotFoundError]],
) -> bool:
    func = partial(error_of_type, error_type=exceptions)
    return any(func(handler) for handler in handlers)


def get_exception_handlers(
    node: nodes.NodeNG, exception: type[Exception] | str = Exception
) -> list[nodes.ExceptHandler] | None:
    """Return the collections of handlers handling the exception in arguments.

    Args:
        node (nodes.NodeNG): A node that is potentially wrapped in a try except.
        exception (builtin.Exception or str): exception or name of the exception.

    Returns:
        list: the collection of handlers that are handling the exception or None.
    """
    context = find_try_except_wrapper_node(node)
    if isinstance(context, nodes.TryExcept):
        return [
            handler for handler in context.handlers if error_of_type(handler, exception)
        ]
    return []


def get_contextlib_with_statements(node: nodes.NodeNG) -> Iterator[nodes.With]:
    """Get all contextlib.with statements in the ancestors of the given node."""
    for with_node in node.node_ancestors():
        if isinstance(with_node, nodes.With):
            yield with_node


def _suppresses_exception(
    call: nodes.Call, exception: type[Exception] | str = Exception
) -> bool:
    """Check if the given node suppresses the given exception."""
    if not isinstance(exception, str):
        exception = exception.__name__
    for arg in call.args:
        inferred = safe_infer(arg)
        if isinstance(inferred, nodes.ClassDef):
            if inferred.name == exception:
                return True
        elif isinstance(inferred, nodes.Tuple):
            for elt in inferred.elts:
                inferred_elt = safe_infer(elt)
                if (
                    isinstance(inferred_elt, nodes.ClassDef)
                    and inferred_elt.name == exception
                ):
                    return True
    return False


def get_contextlib_suppressors(
    node: nodes.NodeNG, exception: type[Exception] | str = Exception
) -> Iterator[nodes.With]:
    """Return the contextlib suppressors handling the exception.

    Args:
        node (nodes.NodeNG): A node that is potentially wrapped in a contextlib.suppress.
        exception (builtin.Exception): exception or name of the exception.

    Yields:
        nodes.With: A with node that is suppressing the exception.
    """
    for with_node in get_contextlib_with_statements(node):
        for item, _ in with_node.items:
            if isinstance(item, nodes.Call):
                inferred = safe_infer(item.func)
                if (
                    isinstance(inferred, nodes.ClassDef)
                    and inferred.qname() == "contextlib.suppress"
                ):
                    if _suppresses_exception(item, exception):
                        yield with_node


def is_node_inside_try_except(node: nodes.Raise) -> bool:
    """Check if the node is directly under a Try/Except statement
    (but not under an ExceptHandler!).

    Args:
        node (nodes.Raise): the node raising the exception.

    Returns:
        bool: True if the node is inside a try/except statement, False otherwise.
    """
    context = find_try_except_wrapper_node(node)
    return isinstance(context, nodes.TryExcept)


def node_ignores_exception(
    node: nodes.NodeNG, exception: type[Exception] | str = Exception
) -> bool:
    """Check if the node is in a TryExcept which handles the given exception.

    If the exception is not given, the function is going to look for bare
    excepts.
    """
    managing_handlers = get_exception_handlers(node, exception)
    if managing_handlers:
        return True
    return any(get_contextlib_suppressors(node, exception))


def class_is_abstract(node: nodes.ClassDef) -> bool:
    """Return true if the given class node should be considered as an abstract
    class.
    """
    # Protocol classes are considered "abstract"
    if is_protocol_class(node):
        return True

    # Only check for explicit metaclass=ABCMeta on this specific class
    meta = node.declared_metaclass()
    if meta is not None:
        if meta.name == "ABCMeta" and meta.root().name in ABC_MODULES:
            return True

    for ancestor in node.ancestors():
        if ancestor.name == "ABC" and ancestor.root().name in ABC_MODULES:
            # abc.ABC inheritance
            return True

    for method in node.methods():
        if method.parent.frame(future=True) is node:
            if method.is_abstract(pass_is_abstract=False):
                return True
    return False


def _supports_protocol_method(value: nodes.NodeNG, attr: str) -> bool:
    try:
        attributes = value.getattr(attr)
    except astroid.NotFoundError:
        return False

    first = attributes[0]

    # Return False if a constant is assigned
    if isinstance(first, nodes.AssignName):
        this_assign_parent = get_node_first_ancestor_of_type(
            first, (nodes.Assign, nodes.NamedExpr)
        )
        if this_assign_parent is None:  # pragma: no cover
            # Cannot imagine this being None, but return True to avoid false positives
            return True
        if isinstance(this_assign_parent.value, nodes.BaseContainer):
            if all(isinstance(n, nodes.Const) for n in this_assign_parent.value.elts):
                return False
        if isinstance(this_assign_parent.value, nodes.Const):
            return False
    return True


def is_comprehension(node: nodes.NodeNG) -> bool:
    comprehensions = (
        nodes.ListComp,
        nodes.SetComp,
        nodes.DictComp,
        nodes.GeneratorExp,
    )
    return isinstance(node, comprehensions)


def _supports_mapping_protocol(value: nodes.NodeNG) -> bool:
    return _supports_protocol_method(
        value, GETITEM_METHOD
    ) and _supports_protocol_method(value, KEYS_METHOD)


def _supports_membership_test_protocol(value: nodes.NodeNG) -> bool:
    return _supports_protocol_method(value, CONTAINS_METHOD)


def _supports_iteration_protocol(value: nodes.NodeNG) -> bool:
    return _supports_protocol_method(value, ITER_METHOD) or _supports_protocol_method(
        value, GETITEM_METHOD
    )


def _supports_async_iteration_protocol(value: nodes.NodeNG) -> bool:
    return _supports_protocol_method(value, AITER_METHOD)


def _supports_getitem_protocol(value: nodes.NodeNG) -> bool:
    return _supports_protocol_method(value, GETITEM_METHOD)


def _supports_setitem_protocol(value: nodes.NodeNG) -> bool:
    return _supports_protocol_method(value, SETITEM_METHOD)


def _supports_delitem_protocol(value: nodes.NodeNG) -> bool:
    return _supports_protocol_method(value, DELITEM_METHOD)


def _is_abstract_class_name(name: str) -> bool:
    lname = name.lower()
    is_mixin = lname.endswith("mixin")
    is_abstract = lname.startswith("abstract")
    is_base = lname.startswith("base") or lname.endswith("base")
    return is_mixin or is_abstract or is_base


def is_inside_abstract_class(node: nodes.NodeNG) -> bool:
    while node is not None:
        if isinstance(node, nodes.ClassDef):
            if class_is_abstract(node):
                return True
            name = getattr(node, "name", None)
            if name is not None and _is_abstract_class_name(name):
                return True
        node = node.parent
    return False


def _supports_protocol(
    value: nodes.NodeNG, protocol_callback: Callable[[nodes.NodeNG], bool]
) -> bool:
    if isinstance(value, nodes.ClassDef):
        if not has_known_bases(value):
            return True
        # classobj can only be iterable if it has an iterable metaclass
        meta = value.metaclass()
        if meta is not None:
            if protocol_callback(meta):
                return True
    if isinstance(value, astroid.BaseInstance):
        if not has_known_bases(value):
            return True
        if value.has_dynamic_getattr():
            return True
        if protocol_callback(value):
            return True

    if isinstance(value, nodes.ComprehensionScope):
        return True

    if (
        isinstance(value, astroid.bases.Proxy)
        and isinstance(value._proxied, astroid.BaseInstance)
        and has_known_bases(value._proxied)
    ):
        value = value._proxied
        return protocol_callback(value)

    return False


def is_iterable(value: nodes.NodeNG, check_async: bool = False) -> bool:
    if check_async:
        protocol_check = _supports_async_iteration_protocol
    else:
        protocol_check = _supports_iteration_protocol
    return _supports_protocol(value, protocol_check)


def is_mapping(value: nodes.NodeNG) -> bool:
    return _supports_protocol(value, _supports_mapping_protocol)


def supports_membership_test(value: nodes.NodeNG) -> bool:
    supported = _supports_protocol(value, _supports_membership_test_protocol)
    return supported or is_iterable(value)


def supports_getitem(value: nodes.NodeNG, node: nodes.NodeNG) -> bool:
    if isinstance(value, nodes.ClassDef):
        if _supports_protocol_method(value, CLASS_GETITEM_METHOD):
            return True
        if is_postponed_evaluation_enabled(node) and is_node_in_type_annotation_context(
            node
        ):
            return True
    return _supports_protocol(value, _supports_getitem_protocol)


def supports_setitem(value: nodes.NodeNG, _: nodes.NodeNG) -> bool:
    return _supports_protocol(value, _supports_setitem_protocol)


def supports_delitem(value: nodes.NodeNG, _: nodes.NodeNG) -> bool:
    return _supports_protocol(value, _supports_delitem_protocol)


def _get_python_type_of_node(node: nodes.NodeNG) -> str | None:
    pytype: Callable[[], str] | None = getattr(node, "pytype", None)
    if callable(pytype):
        return pytype()
    return None


@lru_cache(maxsize=1024)
def safe_infer(
    node: nodes.NodeNG,
    context: InferenceContext | None = None,
    *,
    compare_constants: bool = False,
) -> InferenceResult | None:
    """Return the inferred value for the given node.

    Return None if inference failed or if there is some ambiguity (more than
    one node has been inferred of different types).

    If compare_constants is True and if multiple constants are inferred,
    unequal inferred values are also considered ambiguous and return None.
    """
    inferred_types: set[str | None] = set()
    try:
        infer_gen = node.infer(context=context)
        value = next(infer_gen)
    except astroid.InferenceError:
        return None
    except Exception as e:  # pragma: no cover
        raise AstroidError from e

    if not isinstance(value, util.UninferableBase):
        inferred_types.add(_get_python_type_of_node(value))

    # pylint: disable = too-many-try-statements
    try:
        for inferred in infer_gen:
            inferred_type = _get_python_type_of_node(inferred)
            if inferred_type not in inferred_types:
                return None  # If there is ambiguity on the inferred node.
            if (
                compare_constants
                and isinstance(inferred, nodes.Const)
                and isinstance(value, nodes.Const)
                and inferred.value != value.value
            ):
                return None
            if (
                isinstance(inferred, nodes.FunctionDef)
                and inferred.args.args is not None
                and isinstance(value, nodes.FunctionDef)
                and value.args.args is not None
                and len(inferred.args.args) != len(value.args.args)
            ):
                return None  # Different number of arguments indicates ambiguity
    except astroid.InferenceError:
        return None  # There is some kind of ambiguity
    except StopIteration:
        return value
    except Exception as e:  # pragma: no cover
        raise AstroidError from e
    return value if len(inferred_types) <= 1 else None


@lru_cache(maxsize=512)
def infer_all(
    node: nodes.NodeNG, context: InferenceContext | None = None
) -> list[InferenceResult]:
    try:
        return list(node.infer(context=context))
    except astroid.InferenceError:
        return []
    except Exception as e:  # pragma: no cover
        raise AstroidError from e


def has_known_bases(
    klass: nodes.ClassDef, context: InferenceContext | None = None
) -> bool:
    """Return true if all base classes of a class could be inferred."""
    try:
        return klass._all_bases_known  # type: ignore[no-any-return]
    except AttributeError:
        pass
    for base in klass.bases:
        result = safe_infer(base, context=context)
        if (
            not isinstance(result, nodes.ClassDef)
            or result is klass
            or not has_known_bases(result, context=context)
        ):
            klass._all_bases_known = False
            return False
    klass._all_bases_known = True
    return True


def is_none(node: nodes.NodeNG) -> bool:
    return (
        node is None
        or (isinstance(node, nodes.Const) and node.value is None)
        or (isinstance(node, nodes.Name) and node.name == "None")
    )


def node_type(node: nodes.NodeNG) -> SuccessfulInferenceResult | None:
    """Return the inferred type for `node`.

    If there is more than one possible type, or if inferred type is Uninferable or None,
    return None
    """
    # check there is only one possible type for the assign node. Else we
    # don't handle it for now
    types: set[SuccessfulInferenceResult] = set()
    try:
        for var_type in node.infer():
            if isinstance(var_type, util.UninferableBase) or is_none(var_type):
                continue
            types.add(var_type)
            if len(types) > 1:
                return None
    except astroid.InferenceError:
        return None
    return types.pop() if types else None


def is_registered_in_singledispatch_function(node: nodes.FunctionDef) -> bool:
    """Check if the given function node is a singledispatch function."""

    singledispatch_qnames = (
        "functools.singledispatch",
        "singledispatch.singledispatch",
    )

    if not isinstance(node, nodes.FunctionDef):
        return False

    decorators = node.decorators.nodes if node.decorators else []
    for decorator in decorators:
        # func.register are function calls or register attributes
        # when the function is annotated with types
        if isinstance(decorator, nodes.Call):
            func = decorator.func
        elif isinstance(decorator, nodes.Attribute):
            func = decorator
        else:
            continue

        if not isinstance(func, nodes.Attribute) or func.attrname != "register":
            continue

        try:
            func_def = next(func.expr.infer())
        except astroid.InferenceError:
            continue

        if isinstance(func_def, nodes.FunctionDef):
            return decorated_with(func_def, singledispatch_qnames)

    return False


def find_inferred_fn_from_register(node: nodes.NodeNG) -> nodes.FunctionDef | None:
    # func.register are function calls or register attributes
    # when the function is annotated with types
    if isinstance(node, nodes.Call):
        func = node.func
    elif isinstance(node, nodes.Attribute):
        func = node
    else:
        return None

    if not isinstance(func, nodes.Attribute) or func.attrname != "register":
        return None

    func_def = safe_infer(func.expr)
    if not isinstance(func_def, nodes.FunctionDef):
        return None

    return func_def


def is_registered_in_singledispatchmethod_function(node: nodes.FunctionDef) -> bool:
    """Check if the given function node is a singledispatchmethod function."""

    singledispatchmethod_qnames = (
        "functools.singledispatchmethod",
        "singledispatch.singledispatchmethod",
    )

    decorators = node.decorators.nodes if node.decorators else []
    for decorator in decorators:
        func_def = find_inferred_fn_from_register(decorator)
        if func_def:
            return decorated_with(func_def, singledispatchmethod_qnames)

    return False


def get_node_last_lineno(node: nodes.NodeNG) -> int:
    """Get the last lineno of the given node.

    For a simple statement this will just be node.lineno,
    but for a node that has child statements (e.g. a method) this will be the lineno of the last
    child statement recursively.
    """
    # 'finalbody' is always the last clause in a try statement, if present
    if getattr(node, "finalbody", False):
        return get_node_last_lineno(node.finalbody[-1])
    # For if, while, and for statements 'orelse' is always the last clause.
    # For try statements 'orelse' is the last in the absence of a 'finalbody'
    if getattr(node, "orelse", False):
        return get_node_last_lineno(node.orelse[-1])
    # try statements have the 'handlers' last if there is no 'orelse' or 'finalbody'
    if getattr(node, "handlers", False):
        return get_node_last_lineno(node.handlers[-1])
    # All compound statements have a 'body'
    if getattr(node, "body", False):
        return get_node_last_lineno(node.body[-1])
    # Not a compound statement
    return node.lineno  # type: ignore[no-any-return]


def is_postponed_evaluation_enabled(node: nodes.NodeNG) -> bool:
    """Check if the postponed evaluation of annotations is enabled."""
    module = node.root()
    return "annotations" in module.future_imports


def is_class_subscriptable_pep585_with_postponed_evaluation_enabled(
    value: nodes.ClassDef, node: nodes.NodeNG
) -> bool:
    """Check if class is subscriptable with PEP 585 and
    postponed evaluation enabled.
    """
    warnings.warn(
        "'is_class_subscriptable_pep585_with_postponed_evaluation_enabled' has been "
        "deprecated and will be removed in pylint 3.0. "
        "Use 'is_postponed_evaluation_enabled(node) and "
        "is_node_in_type_annotation_context(node)' instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return (
        is_postponed_evaluation_enabled(node)
        and value.qname() in SUBSCRIPTABLE_CLASSES_PEP585
        and is_node_in_type_annotation_context(node)
    )


def is_node_in_type_annotation_context(node: nodes.NodeNG) -> bool:
    """Check if node is in type annotation context.

    Check for 'AnnAssign', function 'Arguments',
    or part of function return type annotation.
    """
    # pylint: disable=too-many-boolean-expressions
    current_node, parent_node = node, node.parent
    while True:
        if (
            isinstance(parent_node, nodes.AnnAssign)
            and parent_node.annotation == current_node
            or isinstance(parent_node, nodes.Arguments)
            and current_node
            in (
                *parent_node.annotations,
                *parent_node.posonlyargs_annotations,
                *parent_node.kwonlyargs_annotations,
                parent_node.varargannotation,
                parent_node.kwargannotation,
            )
            or isinstance(parent_node, nodes.FunctionDef)
            and parent_node.returns == current_node
        ):
            return True
        current_node, parent_node = parent_node, parent_node.parent
        if isinstance(parent_node, nodes.Module):
            return False


def is_subclass_of(child: nodes.ClassDef, parent: nodes.ClassDef) -> bool:
    """Check if first node is a subclass of second node.

    :param child: Node to check for subclass.
    :param parent: Node to check for superclass.
    :returns: True if child is derived from parent. False otherwise.
    """
    if not all(isinstance(node, nodes.ClassDef) for node in (child, parent)):
        return False

    for ancestor in child.ancestors():
        try:
            if astroid.helpers.is_subtype(ancestor, parent):
                return True
        except astroid.exceptions._NonDeducibleTypeHierarchy:
            continue
    return False


@lru_cache(maxsize=1024)
def is_overload_stub(node: nodes.NodeNG) -> bool:
    """Check if a node is a function stub decorated with typing.overload.

    :param node: Node to check.
    :returns: True if node is an overload function stub. False otherwise.
    """
    decorators = getattr(node, "decorators", None)
    return bool(decorators and decorated_with(node, ["typing.overload", "overload"]))


def is_protocol_class(cls: nodes.NodeNG) -> bool:
    """Check if the given node represents a protocol class.

    :param cls: The node to check
    :returns: True if the node is or inherits from typing.Protocol directly, false otherwise.
    """
    if not isinstance(cls, nodes.ClassDef):
        return False

    # Return if klass is protocol
    if cls.qname() in TYPING_PROTOCOLS:
        return True

    for base in cls.bases:
        try:
            for inf_base in base.infer():
                if inf_base.qname() in TYPING_PROTOCOLS:
                    return True
        except astroid.InferenceError:
            continue
    return False


def is_call_of_name(node: nodes.NodeNG, name: str) -> bool:
    """Checks if node is a function call with the given name."""
    return (
        isinstance(node, nodes.Call)
        and isinstance(node.func, nodes.Name)
        and node.func.name == name
    )


def is_test_condition(
    node: nodes.NodeNG,
    parent: nodes.NodeNG | None = None,
) -> bool:
    """Returns true if the given node is being tested for truthiness."""
    parent = parent or node.parent
    if isinstance(parent, (nodes.While, nodes.If, nodes.IfExp, nodes.Assert)):
        return node is parent.test or parent.test.parent_of(node)
    if isinstance(parent, nodes.Comprehension):
        return node in parent.ifs
    return is_call_of_name(parent, "bool") and parent.parent_of(node)


def is_classdef_type(node: nodes.ClassDef) -> bool:
    """Test if ClassDef node is Type."""
    if node.name == "type":
        return True
    return any(isinstance(b, nodes.Name) and b.name == "type" for b in node.bases)


def is_attribute_typed_annotation(
    node: nodes.ClassDef | astroid.Instance, attr_name: str
) -> bool:
    """Test if attribute is typed annotation in current node
    or any base nodes.
    """
    attribute = node.locals.get(attr_name, [None])[0]
    if (
        attribute
        and isinstance(attribute, nodes.AssignName)
        and isinstance(attribute.parent, nodes.AnnAssign)
    ):
        return True
    for base in node.bases:
        inferred = safe_infer(base)
        if (
            inferred
            and isinstance(inferred, nodes.ClassDef)
            and is_attribute_typed_annotation(inferred, attr_name)
        ):
            return True
    return False


def is_enum(node: nodes.ClassDef) -> bool:
    return node.name == "Enum" and node.root().name == "enum"  # type: ignore[no-any-return]


def is_assign_name_annotated_with(node: nodes.AssignName, typing_name: str) -> bool:
    """Test if AssignName node has `typing_name` annotation.

    Especially useful to check for `typing._SpecialForm` instances
    like: `Union`, `Optional`, `Literal`, `ClassVar`, `Final`.
    """
    if not isinstance(node.parent, nodes.AnnAssign):
        return False
    annotation = node.parent.annotation
    if isinstance(annotation, nodes.Subscript):
        annotation = annotation.value
    if (
        isinstance(annotation, nodes.Name)
        and annotation.name == typing_name
        or isinstance(annotation, nodes.Attribute)
        and annotation.attrname == typing_name
    ):
        return True
    return False


def get_iterating_dictionary_name(node: nodes.For | nodes.Comprehension) -> str | None:
    """Get the name of the dictionary which keys are being iterated over on
    a ``nodes.For`` or ``nodes.Comprehension`` node.

    If the iterating object is not either the keys method of a dictionary
    or a dictionary itself, this returns None.
    """
    # Is it a proper keys call?
    if (
        isinstance(node.iter, nodes.Call)
        and isinstance(node.iter.func, nodes.Attribute)
        and node.iter.func.attrname == "keys"
    ):
        inferred = safe_infer(node.iter.func)
        if not isinstance(inferred, astroid.BoundMethod):
            return None
        return node.iter.as_string().rpartition(".keys")[0]  # type: ignore[no-any-return]

    # Is it a dictionary?
    if isinstance(node.iter, (nodes.Name, nodes.Attribute)):
        inferred = safe_infer(node.iter)
        if not isinstance(inferred, nodes.Dict):
            return None
        return node.iter.as_string()  # type: ignore[no-any-return]

    return None


def get_subscript_const_value(node: nodes.Subscript) -> nodes.Const:
    """Returns the value 'subscript.slice' of a Subscript node.

    :param node: Subscript Node to extract value from
    :returns: Const Node containing subscript value
    :raises InferredTypeError: if the subscript node cannot be inferred as a Const
    """
    inferred = safe_infer(node.slice)
    if not isinstance(inferred, nodes.Const):
        raise InferredTypeError("Subscript.slice cannot be inferred as a nodes.Const")

    return inferred


def get_import_name(importnode: ImportNode, modname: str | None) -> str | None:
    """Get a prepared module name from the given import node.

    In the case of relative imports, this will return the
    absolute qualified module name, which might be useful
    for debugging. Otherwise, the initial module name
    is returned unchanged.

    :param importnode: node representing import statement.
    :param modname: module name from import statement.
    :returns: absolute qualified module name of the module
        used in import.
    """
    if isinstance(importnode, nodes.ImportFrom) and importnode.level:
        root = importnode.root()
        if isinstance(root, nodes.Module):
            try:
                return root.relative_to_absolute_name(  # type: ignore[no-any-return]
                    modname, level=importnode.level
                )
            except TooManyLevelsError:
                return modname
    return modname


def is_sys_guard(node: nodes.If) -> bool:
    """Return True if IF stmt is a sys.version_info guard.

    >>> import sys
    >>> if sys.version_info > (3, 8):
    >>>     from typing import Literal
    >>> else:
    >>>     from typing_extensions import Literal
    """
    if isinstance(node.test, nodes.Compare):
        value = node.test.left
        if isinstance(value, nodes.Subscript):
            value = value.value
        if (
            isinstance(value, nodes.Attribute)
            and value.as_string() == "sys.version_info"
        ):
            return True

    return False


def is_typing_guard(node: nodes.If) -> bool:
    """Return True if IF stmt is a typing guard.

    >>> from typing import TYPE_CHECKING
    >>> if TYPE_CHECKING:
    >>>     from xyz import a
    """
    return isinstance(
        node.test, (nodes.Name, nodes.Attribute)
    ) and node.test.as_string().endswith("TYPE_CHECKING")


def is_node_in_typing_guarded_import_block(node: nodes.NodeNG) -> bool:
    """Return True if node is part for guarded `typing.TYPE_CHECKING` if block."""
    return isinstance(node.parent, nodes.If) and is_typing_guard(node.parent)


def is_node_in_guarded_import_block(node: nodes.NodeNG) -> bool:
    """Return True if node is part for guarded if block.

    I.e. `sys.version_info` or `typing.TYPE_CHECKING`
    """
    return isinstance(node.parent, nodes.If) and (
        is_sys_guard(node.parent) or is_typing_guard(node.parent)
    )


def is_reassigned_after_current(node: nodes.NodeNG, varname: str) -> bool:
    """Check if the given variable name is reassigned in the same scope after the
    current node.
    """
    return any(
        a.name == varname and a.lineno > node.lineno
        for a in node.scope().nodes_of_class(
            (nodes.AssignName, nodes.ClassDef, nodes.FunctionDef)
        )
    )


def is_deleted_after_current(node: nodes.NodeNG, varname: str) -> bool:
    """Check if the given variable name is deleted in the same scope after the current
    node.
    """
    return any(
        getattr(target, "name", None) == varname and target.lineno > node.lineno
        for del_node in node.scope().nodes_of_class(nodes.Delete)
        for target in del_node.targets
    )


def is_function_body_ellipsis(node: nodes.FunctionDef) -> bool:
    """Checks whether a function body only consists of a single Ellipsis."""
    return (
        len(node.body) == 1
        and isinstance(node.body[0], nodes.Expr)
        and isinstance(node.body[0].value, nodes.Const)
        and node.body[0].value.value == Ellipsis
    )


def is_base_container(node: nodes.NodeNG | None) -> bool:
    return isinstance(node, nodes.BaseContainer) and not node.elts


def is_empty_dict_literal(node: nodes.NodeNG | None) -> bool:
    return isinstance(node, nodes.Dict) and not node.items


def is_empty_str_literal(node: nodes.NodeNG | None) -> bool:
    return (
        isinstance(node, nodes.Const) and isinstance(node.value, str) and not node.value
    )


def returns_bool(node: nodes.NodeNG) -> bool:
    """Returns true if a node is a nodes.Return that returns a constant boolean."""
    return (
        isinstance(node, nodes.Return)
        and isinstance(node.value, nodes.Const)
        and isinstance(node.value.value, bool)
    )


def assigned_bool(node: nodes.NodeNG) -> bool:
    """Returns true if a node is a nodes.Assign that returns a constant boolean."""
    return (
        isinstance(node, nodes.Assign)
        and isinstance(node.value, nodes.Const)
        and isinstance(node.value.value, bool)
    )


def get_node_first_ancestor_of_type(
    node: nodes.NodeNG, ancestor_type: type[_NodeT] | tuple[type[_NodeT], ...]
) -> _NodeT | None:
    """Return the first parent node that is any of the provided types (or None)."""
    for ancestor in node.node_ancestors():
        if isinstance(ancestor, ancestor_type):
            return ancestor  # type: ignore[no-any-return]
    return None


def get_node_first_ancestor_of_type_and_its_child(
    node: nodes.NodeNG, ancestor_type: type[_NodeT] | tuple[type[_NodeT], ...]
) -> tuple[None, None] | tuple[_NodeT, nodes.NodeNG]:
    """Modified version of get_node_first_ancestor_of_type to also return the
    descendant visited directly before reaching the sought ancestor.

    Useful for extracting whether a statement is guarded by a try, except, or finally
    when searching for a TryFinally ancestor.
    """
    child = node
    for ancestor in node.node_ancestors():
        if isinstance(ancestor, ancestor_type):
            return (ancestor, child)
        child = ancestor
    return None, None


def in_type_checking_block(node: nodes.NodeNG) -> bool:
    """Check if a node is guarded by a TYPE_CHECKING guard."""
    for ancestor in node.node_ancestors():
        if not isinstance(ancestor, nodes.If):
            continue
        if isinstance(ancestor.test, nodes.Name):
            if ancestor.test.name != "TYPE_CHECKING":
                continue
            maybe_import_from = ancestor.test.lookup(ancestor.test.name)[1][0]
            if (
                isinstance(maybe_import_from, nodes.ImportFrom)
                and maybe_import_from.modname == "typing"
            ):
                return True
            inferred = safe_infer(ancestor.test)
            if isinstance(inferred, nodes.Const) and inferred.value is False:
                return True
        elif isinstance(ancestor.test, nodes.Attribute):
            if ancestor.test.attrname != "TYPE_CHECKING":
                continue
            inferred_module = safe_infer(ancestor.test.expr)
            if (
                isinstance(inferred_module, nodes.Module)
                and inferred_module.name == "typing"
            ):
                return True

    return False


def is_typing_member(node: nodes.NodeNG, names_to_check: tuple[str, ...]) -> bool:
    """Check if `node` is a member of the `typing` module and has one of the names from
    `names_to_check`.
    """
    if isinstance(node, nodes.Name):
        try:
            import_from = node.lookup(node.name)[1][0]
        except IndexError:
            return False

        if isinstance(import_from, nodes.ImportFrom):
            return (
                import_from.modname == "typing"
                and import_from.real_name(node.name) in names_to_check
            )
    elif isinstance(node, nodes.Attribute):
        inferred_module = safe_infer(node.expr)
        return (
            isinstance(inferred_module, nodes.Module)
            and inferred_module.name == "typing"
            and node.attrname in names_to_check
        )
    return False


@lru_cache()
def in_for_else_branch(parent: nodes.NodeNG, stmt: nodes.Statement) -> bool:
    """Returns True if stmt is inside the else branch for a parent For stmt."""
    return isinstance(parent, nodes.For) and any(
        else_stmt.parent_of(stmt) or else_stmt == stmt for else_stmt in parent.orelse
    )


def find_assigned_names_recursive(
    target: nodes.AssignName | nodes.BaseContainer,
) -> Iterator[str]:
    """Yield the names of assignment targets, accounting for nested ones."""
    if isinstance(target, nodes.AssignName):
        if target.name is not None:
            yield target.name
    elif isinstance(target, nodes.BaseContainer):
        for elt in target.elts:
            yield from find_assigned_names_recursive(elt)


def has_starred_node_recursive(
    node: nodes.For | nodes.Comprehension | nodes.Set,
) -> Iterator[bool]:
    """Yield ``True`` if a Starred node is found recursively."""
    if isinstance(node, nodes.Starred):
        yield True
    elif isinstance(node, nodes.Set):
        for elt in node.elts:
            yield from has_starred_node_recursive(elt)
    elif isinstance(node, (nodes.For, nodes.Comprehension)):
        for elt in node.iter.elts:
            yield from has_starred_node_recursive(elt)


def is_hashable(node: nodes.NodeNG) -> bool:
    """Return whether any inferred value of `node` is hashable.

    When finding ambiguity, return True.
    """
    # pylint: disable = too-many-try-statements
    try:
        for inferred in node.infer():
            if isinstance(inferred, (nodes.ClassDef, util.UninferableBase)):
                return True
            if not hasattr(inferred, "igetattr"):
                return True
            hash_fn = next(inferred.igetattr("__hash__"))
            if hash_fn.parent is inferred:
                return True
            if getattr(hash_fn, "value", True) is not None:
                return True
        return False
    except astroid.InferenceError:
        return True


def _is_target_name_in_binop_side(
    target: nodes.AssignName | nodes.AssignAttr, side: nodes.NodeNG | None
) -> bool:
    """Determine whether the target name-like node is referenced in the side node."""
    if isinstance(side, nodes.Name):
        if isinstance(target, nodes.AssignName):
            return target.name == side.name  # type: ignore[no-any-return]
        return False
    if isinstance(side, nodes.Attribute) and isinstance(target, nodes.AssignAttr):
        return target.as_string() == side.as_string()  # type: ignore[no-any-return]
    return False


def is_augmented_assign(node: nodes.Assign) -> tuple[bool, str]:
    """Determine if the node is assigning itself (with modifications) to itself.

    For example: x = 1 + x
    """
    if not isinstance(node.value, nodes.BinOp):
        return False, ""

    binop = node.value
    target = node.targets[0]

    if not isinstance(target, (nodes.AssignName, nodes.AssignAttr)):
        return False, ""

    # We don't want to catch x = "1" + x or x = "%s" % x
    if isinstance(binop.left, nodes.Const) and isinstance(
        binop.left.value, (str, bytes)
    ):
        return False, ""

    # This could probably be improved but for now we disregard all assignments from calls
    if isinstance(binop.left, nodes.Call) or isinstance(binop.right, nodes.Call):
        return False, ""

    if _is_target_name_in_binop_side(target, binop.left):
        return True, binop.op
    if (
        # Unless an operator is commutative, we should not raise (i.e. x = 3/x)
        binop.op in COMMUTATIVE_OPERATORS
        and _is_target_name_in_binop_side(target, binop.right)
    ):
        inferred_left = safe_infer(binop.left)
        if isinstance(inferred_left, nodes.Const) and isinstance(
            inferred_left.value, int
        ):
            return True, binop.op
        return False, ""
    return False, ""


def is_module_ignored(
    module: nodes.Module,
    ignored_modules: Iterable[str],
) -> bool:
    ignored_modules = set(ignored_modules)
    module_name = module.name
    module_qname = module.qname()

    for ignore in ignored_modules:
        # Try to match the module name / fully qualified name directly
        if module_qname in ignored_modules or module_name in ignored_modules:
            return True

        # Try to see if the ignores pattern match against the module name.
        if fnmatch.fnmatch(module_qname, ignore):
            return True

        # Otherwise, we might have a root module name being ignored,
        # and the qualified owner has more levels of depth.
        parts = deque(module_name.split("."))
        current_module = ""

        while parts:
            part = parts.popleft()
            if not current_module:
                current_module = part
            else:
                current_module += f".{part}"
            if current_module in ignored_modules:
                return True

    return False


def is_singleton_const(node: nodes.NodeNG) -> bool:
    return isinstance(node, nodes.Const) and any(
        node.value is value for value in SINGLETON_VALUES
    )


def is_terminating_func(node: nodes.Call) -> bool:
    """Detect call to exit(), quit(), os._exit(), or sys.exit()."""
    if (
        not isinstance(node.func, nodes.Attribute)
        and not (isinstance(node.func, nodes.Name))
        or isinstance(node.parent, nodes.Lambda)
    ):
        return False

    try:
        for inferred in node.func.infer():
            if (
                hasattr(inferred, "qname")
                and inferred.qname() in TERMINATING_FUNCS_QNAMES
            ):
                return True
    except (StopIteration, astroid.InferenceError):
        pass

    return False


def is_class_attr(name: str, klass: nodes.ClassDef) -> bool:
    try:
        klass.getattr(name)
        return True
    except astroid.NotFoundError:
        return False


def is_defined(name: str, node: nodes.NodeNG) -> bool:
    """Searches for a tree node that defines the given variable name."""
    is_defined_so_far = False

    if isinstance(node, nodes.NamedExpr):
        is_defined_so_far = node.target.name == name

    if isinstance(node, (nodes.Import, nodes.ImportFrom)):
        is_defined_so_far = any(node_name[0] == name for node_name in node.names)

    if isinstance(node, nodes.With):
        is_defined_so_far = any(
            isinstance(item[1], nodes.AssignName) and item[1].name == name
            for item in node.items
        )

    if isinstance(node, (nodes.ClassDef, nodes.FunctionDef)):
        is_defined_so_far = node.name == name

    if isinstance(node, nodes.AnnAssign):
        is_defined_so_far = (
            node.value
            and isinstance(node.target, nodes.AssignName)
            and node.target.name == name
        )

    if isinstance(node, nodes.Assign):
        is_defined_so_far = any(
            any(
                (
                    (
                        isinstance(elt, nodes.Starred)
                        and isinstance(elt.value, nodes.AssignName)
                        and elt.value.name == name
                    )
                    or (isinstance(elt, nodes.AssignName) and elt.name == name)
                )
                for elt in get_all_elements(target)
            )
            for target in node.targets
        )

    return is_defined_so_far or any(
        is_defined(name, child) for child in node.get_children()
    )


def get_inverse_comparator(op: str) -> str:
    """Returns the inverse comparator given a comparator.

    E.g. when given "==", returns "!="

    :param str op: the comparator to look up.

    :returns: The inverse of the comparator in string format
    :raises KeyError: if input is not recognized as a comparator
    """
    return {
        "==": "!=",
        "!=": "==",
        "<": ">=",
        ">": "<=",
        "<=": ">",
        ">=": "<",
        "in": "not in",
        "not in": "in",
        "is": "is not",
        "is not": "is",
    }[op]


def not_condition_as_string(
    test_node: nodes.Compare | nodes.Name | nodes.UnaryOp | nodes.BoolOp | nodes.BinOp,
) -> str:
    msg = f"not {test_node.as_string()}"
    if isinstance(test_node, nodes.UnaryOp):
        msg = test_node.operand.as_string()
    elif isinstance(test_node, nodes.BoolOp):
        msg = f"not ({test_node.as_string()})"
    elif isinstance(test_node, nodes.Compare):
        lhs = test_node.left
        ops, rhs = test_node.ops[0]
        lower_priority_expressions = (
            nodes.Lambda,
            nodes.UnaryOp,
            nodes.BoolOp,
            nodes.IfExp,
            nodes.NamedExpr,
        )
        lhs = (
            f"({lhs.as_string()})"
            if isinstance(lhs, lower_priority_expressions)
            else lhs.as_string()
        )
        rhs = (
            f"({rhs.as_string()})"
            if isinstance(rhs, lower_priority_expressions)
            else rhs.as_string()
        )
        msg = f"{lhs} {get_inverse_comparator(ops)} {rhs}"
    return msg
