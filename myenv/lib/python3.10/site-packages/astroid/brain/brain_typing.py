# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""Astroid hooks for typing.py support."""

from __future__ import annotations

import sys
import typing
from collections.abc import Iterator
from functools import partial

from astroid import context, extract_node, inference_tip
from astroid.builder import _extract_single_node
from astroid.const import PY38_PLUS, PY39_PLUS
from astroid.exceptions import (
    AttributeInferenceError,
    InferenceError,
    UseInferenceDefault,
)
from astroid.manager import AstroidManager
from astroid.nodes.node_classes import (
    Assign,
    AssignName,
    Attribute,
    Call,
    Const,
    JoinedStr,
    Name,
    NodeNG,
    Subscript,
    Tuple,
)
from astroid.nodes.scoped_nodes import ClassDef, FunctionDef

if sys.version_info >= (3, 8):
    from typing import Final
else:
    from typing_extensions import Final

TYPING_TYPEVARS = {"TypeVar", "NewType"}
TYPING_TYPEVARS_QUALIFIED: Final = {
    "typing.TypeVar",
    "typing.NewType",
    "typing_extensions.TypeVar",
}
TYPING_TYPEDDICT_QUALIFIED: Final = {"typing.TypedDict", "typing_extensions.TypedDict"}
TYPING_TYPE_TEMPLATE = """
class Meta(type):
    def __getitem__(self, item):
        return self

    @property
    def __args__(self):
        return ()

class {0}(metaclass=Meta):
    pass
"""
TYPING_MEMBERS = set(getattr(typing, "__all__", []))

TYPING_ALIAS = frozenset(
    (
        "typing.Hashable",
        "typing.Awaitable",
        "typing.Coroutine",
        "typing.AsyncIterable",
        "typing.AsyncIterator",
        "typing.Iterable",
        "typing.Iterator",
        "typing.Reversible",
        "typing.Sized",
        "typing.Container",
        "typing.Collection",
        "typing.Callable",
        "typing.AbstractSet",
        "typing.MutableSet",
        "typing.Mapping",
        "typing.MutableMapping",
        "typing.Sequence",
        "typing.MutableSequence",
        "typing.ByteString",
        "typing.Tuple",
        "typing.List",
        "typing.Deque",
        "typing.Set",
        "typing.FrozenSet",
        "typing.MappingView",
        "typing.KeysView",
        "typing.ItemsView",
        "typing.ValuesView",
        "typing.ContextManager",
        "typing.AsyncContextManager",
        "typing.Dict",
        "typing.DefaultDict",
        "typing.OrderedDict",
        "typing.Counter",
        "typing.ChainMap",
        "typing.Generator",
        "typing.AsyncGenerator",
        "typing.Type",
        "typing.Pattern",
        "typing.Match",
    )
)

CLASS_GETITEM_TEMPLATE = """
@classmethod
def __class_getitem__(cls, item):
    return cls
"""


def looks_like_typing_typevar_or_newtype(node) -> bool:
    func = node.func
    if isinstance(func, Attribute):
        return func.attrname in TYPING_TYPEVARS
    if isinstance(func, Name):
        return func.name in TYPING_TYPEVARS
    return False


def infer_typing_typevar_or_newtype(node, context_itton=None):
    """Infer a typing.TypeVar(...) or typing.NewType(...) call."""
    try:
        func = next(node.func.infer(context=context_itton))
    except (InferenceError, StopIteration) as exc:
        raise UseInferenceDefault from exc

    if func.qname() not in TYPING_TYPEVARS_QUALIFIED:
        raise UseInferenceDefault
    if not node.args:
        raise UseInferenceDefault
    # Cannot infer from a dynamic class name (f-string)
    if isinstance(node.args[0], JoinedStr):
        raise UseInferenceDefault

    typename = node.args[0].as_string().strip("'")
    node = extract_node(TYPING_TYPE_TEMPLATE.format(typename))
    return node.infer(context=context_itton)


def _looks_like_typing_subscript(node) -> bool:
    """Try to figure out if a Subscript node *might* be a typing-related subscript."""
    if isinstance(node, Name):
        return node.name in TYPING_MEMBERS
    if isinstance(node, Attribute):
        return node.attrname in TYPING_MEMBERS
    if isinstance(node, Subscript):
        return _looks_like_typing_subscript(node.value)
    return False


def infer_typing_attr(
    node: Subscript, ctx: context.InferenceContext | None = None
) -> Iterator[ClassDef]:
    """Infer a typing.X[...] subscript."""
    try:
        value = next(node.value.infer())  # type: ignore[union-attr] # value shouldn't be None for Subscript.
    except (InferenceError, StopIteration) as exc:
        raise UseInferenceDefault from exc

    if not value.qname().startswith("typing.") or value.qname() in TYPING_ALIAS:
        # If typing subscript belongs to an alias handle it separately.
        raise UseInferenceDefault

    if isinstance(value, ClassDef) and value.qname() in {
        "typing.Generic",
        "typing.Annotated",
        "typing_extensions.Annotated",
    }:
        # typing.Generic and typing.Annotated (PY39) are subscriptable
        # through __class_getitem__. Since astroid can't easily
        # infer the native methods, replace them for an easy inference tip
        func_to_add = _extract_single_node(CLASS_GETITEM_TEMPLATE)
        value.locals["__class_getitem__"] = [func_to_add]
        if (
            isinstance(node.parent, ClassDef)
            and node in node.parent.bases
            and getattr(node.parent, "__cache", None)
        ):
            # node.parent.slots is evaluated and cached before the inference tip
            # is first applied. Remove the last result to allow a recalculation of slots
            cache = node.parent.__cache  # type: ignore[attr-defined] # Unrecognized getattr
            if cache.get(node.parent.slots) is not None:
                del cache[node.parent.slots]
        return iter([value])

    node = extract_node(TYPING_TYPE_TEMPLATE.format(value.qname().split(".")[-1]))
    return node.infer(context=ctx)


def _looks_like_typedDict(  # pylint: disable=invalid-name
    node: FunctionDef | ClassDef,
) -> bool:
    """Check if node is TypedDict FunctionDef."""
    return node.qname() in TYPING_TYPEDDICT_QUALIFIED


def infer_old_typedDict(  # pylint: disable=invalid-name
    node: ClassDef, ctx: context.InferenceContext | None = None
) -> Iterator[ClassDef]:
    func_to_add = _extract_single_node("dict")
    node.locals["__call__"] = [func_to_add]
    return iter([node])


def infer_typedDict(  # pylint: disable=invalid-name
    node: FunctionDef, ctx: context.InferenceContext | None = None
) -> Iterator[ClassDef]:
    """Replace TypedDict FunctionDef with ClassDef."""
    class_def = ClassDef(
        name="TypedDict",
        lineno=node.lineno,
        col_offset=node.col_offset,
        parent=node.parent,
    )
    class_def.postinit(bases=[extract_node("dict")], body=[], decorators=None)
    func_to_add = _extract_single_node("dict")
    class_def.locals["__call__"] = [func_to_add]
    return iter([class_def])


def _looks_like_typing_alias(node: Call) -> bool:
    """
    Returns True if the node corresponds to a call to _alias function.

    For example :

    MutableSet = _alias(collections.abc.MutableSet, T)

    :param node: call node
    """
    return (
        isinstance(node.func, Name)
        and node.func.name == "_alias"
        and (
            # _alias function works also for builtins object such as list and dict
            isinstance(node.args[0], (Attribute, Name))
        )
    )


def _forbid_class_getitem_access(node: ClassDef) -> None:
    """Disable the access to __class_getitem__ method for the node in parameters."""

    def full_raiser(origin_func, attr, *args, **kwargs):
        """
        Raises an AttributeInferenceError in case of access to __class_getitem__ method.
        Otherwise, just call origin_func.
        """
        if attr == "__class_getitem__":
            raise AttributeInferenceError("__class_getitem__ access is not allowed")
        return origin_func(attr, *args, **kwargs)

    try:
        node.getattr("__class_getitem__")
        # If we are here, then we are sure to modify an object that does have
        # __class_getitem__ method (which origin is the protocol defined in
        # collections module) whereas the typing module considers it should not.
        # We do not want __class_getitem__ to be found in the classdef
        partial_raiser = partial(full_raiser, node.getattr)
        node.getattr = partial_raiser
    except AttributeInferenceError:
        pass


def infer_typing_alias(
    node: Call, ctx: context.InferenceContext | None = None
) -> Iterator[ClassDef]:
    """
    Infers the call to _alias function
    Insert ClassDef, with same name as aliased class,
    in mro to simulate _GenericAlias.

    :param node: call node
    :param context: inference context
    """
    if (
        not isinstance(node.parent, Assign)
        or not len(node.parent.targets) == 1
        or not isinstance(node.parent.targets[0], AssignName)
    ):
        raise UseInferenceDefault
    try:
        res = next(node.args[0].infer(context=ctx))
    except StopIteration as e:
        raise InferenceError(node=node.args[0], context=ctx) from e

    assign_name = node.parent.targets[0]

    class_def = ClassDef(
        name=assign_name.name,
        lineno=assign_name.lineno,
        col_offset=assign_name.col_offset,
        parent=node.parent,
    )
    if isinstance(res, ClassDef):
        # Only add `res` as base if it's a `ClassDef`
        # This isn't the case for `typing.Pattern` and `typing.Match`
        class_def.postinit(bases=[res], body=[], decorators=None)

    maybe_type_var = node.args[1]
    if (
        not PY39_PLUS
        and not (isinstance(maybe_type_var, Tuple) and not maybe_type_var.elts)
        or PY39_PLUS
        and isinstance(maybe_type_var, Const)
        and maybe_type_var.value > 0
    ):
        # If typing alias is subscriptable, add `__class_getitem__` to ClassDef
        func_to_add = _extract_single_node(CLASS_GETITEM_TEMPLATE)
        class_def.locals["__class_getitem__"] = [func_to_add]
    else:
        # If not, make sure that `__class_getitem__` access is forbidden.
        # This is an issue in cases where the aliased class implements it,
        # but the typing alias isn't subscriptable. E.g., `typing.ByteString` for PY39+
        _forbid_class_getitem_access(class_def)
    return iter([class_def])


def _looks_like_special_alias(node: Call) -> bool:
    """Return True if call is for Tuple or Callable alias.

    In PY37 and PY38 the call is to '_VariadicGenericAlias' with 'tuple' as
    first argument. In PY39+ it is replaced by a call to '_TupleType'.

    PY37: Tuple = _VariadicGenericAlias(tuple, (), inst=False, special=True)
    PY39: Tuple = _TupleType(tuple, -1, inst=False, name='Tuple')

    PY37: Callable = _VariadicGenericAlias(collections.abc.Callable, (), special=True)
    PY39: Callable = _CallableType(collections.abc.Callable, 2)
    """
    return isinstance(node.func, Name) and (
        not PY39_PLUS
        and node.func.name == "_VariadicGenericAlias"
        and (
            isinstance(node.args[0], Name)
            and node.args[0].name == "tuple"
            or isinstance(node.args[0], Attribute)
            and node.args[0].as_string() == "collections.abc.Callable"
        )
        or PY39_PLUS
        and (
            node.func.name == "_TupleType"
            and isinstance(node.args[0], Name)
            and node.args[0].name == "tuple"
            or node.func.name == "_CallableType"
            and isinstance(node.args[0], Attribute)
            and node.args[0].as_string() == "collections.abc.Callable"
        )
    )


def infer_special_alias(
    node: Call, ctx: context.InferenceContext | None = None
) -> Iterator[ClassDef]:
    """Infer call to tuple alias as new subscriptable class typing.Tuple."""
    if not (
        isinstance(node.parent, Assign)
        and len(node.parent.targets) == 1
        and isinstance(node.parent.targets[0], AssignName)
    ):
        raise UseInferenceDefault
    try:
        res = next(node.args[0].infer(context=ctx))
    except StopIteration as e:
        raise InferenceError(node=node.args[0], context=ctx) from e

    assign_name = node.parent.targets[0]
    class_def = ClassDef(
        name=assign_name.name,
        parent=node.parent,
    )
    class_def.postinit(bases=[res], body=[], decorators=None)
    func_to_add = _extract_single_node(CLASS_GETITEM_TEMPLATE)
    class_def.locals["__class_getitem__"] = [func_to_add]
    return iter([class_def])


def _looks_like_typing_cast(node: Call) -> bool:
    return isinstance(node, Call) and (
        isinstance(node.func, Name)
        and node.func.name == "cast"
        or isinstance(node.func, Attribute)
        and node.func.attrname == "cast"
    )


def infer_typing_cast(
    node: Call, ctx: context.InferenceContext | None = None
) -> Iterator[NodeNG]:
    """Infer call to cast() returning same type as casted-from var."""
    if not isinstance(node.func, (Name, Attribute)):
        raise UseInferenceDefault

    try:
        func = next(node.func.infer(context=ctx))
    except (InferenceError, StopIteration) as exc:
        raise UseInferenceDefault from exc
    if (
        not isinstance(func, FunctionDef)
        or func.qname() != "typing.cast"
        or len(node.args) != 2
    ):
        raise UseInferenceDefault

    return node.args[1].infer(context=ctx)


AstroidManager().register_transform(
    Call,
    inference_tip(infer_typing_typevar_or_newtype),
    looks_like_typing_typevar_or_newtype,
)
AstroidManager().register_transform(
    Subscript, inference_tip(infer_typing_attr), _looks_like_typing_subscript
)
AstroidManager().register_transform(
    Call, inference_tip(infer_typing_cast), _looks_like_typing_cast
)

if PY39_PLUS:
    AstroidManager().register_transform(
        FunctionDef, inference_tip(infer_typedDict), _looks_like_typedDict
    )
elif PY38_PLUS:
    AstroidManager().register_transform(
        ClassDef, inference_tip(infer_old_typedDict), _looks_like_typedDict
    )

AstroidManager().register_transform(
    Call, inference_tip(infer_typing_alias), _looks_like_typing_alias
)
AstroidManager().register_transform(
    Call, inference_tip(infer_special_alias), _looks_like_special_alias
)
