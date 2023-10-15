# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""This module contains a set of functions to handle inference on astroid trees."""

from __future__ import annotations

import ast
import functools
import itertools
import operator
import typing
from collections.abc import Callable, Generator, Iterable, Iterator
from typing import TYPE_CHECKING, Any, Optional, TypeVar, Union

from astroid import bases, constraint, decorators, helpers, nodes, protocols, util
from astroid.const import PY310_PLUS
from astroid.context import (
    CallContext,
    InferenceContext,
    bind_context_to_node,
    copy_context,
)
from astroid.exceptions import (
    AstroidBuildingError,
    AstroidError,
    AstroidIndexError,
    AstroidTypeError,
    AstroidValueError,
    AttributeInferenceError,
    InferenceError,
    NameInferenceError,
    _NonDeducibleTypeHierarchy,
)
from astroid.interpreter import dunder_lookup
from astroid.manager import AstroidManager
from astroid.typing import (
    InferenceErrorInfo,
    InferenceResult,
    SuccessfulInferenceResult,
)

if TYPE_CHECKING:
    from astroid.objects import Property

# Prevents circular imports
objects = util.lazy_import("objects")

_T = TypeVar("_T")
_BaseContainerT = TypeVar("_BaseContainerT", bound=nodes.BaseContainer)
_FunctionDefT = TypeVar("_FunctionDefT", bound=nodes.FunctionDef)

GetFlowFactory = typing.Callable[
    [
        InferenceResult,
        Optional[InferenceResult],
        Union[nodes.AugAssign, nodes.BinOp],
        InferenceResult,
        Optional[InferenceResult],
        InferenceContext,
        InferenceContext,
    ],
    "list[functools.partial[Generator[InferenceResult, None, None]]]",
]

# .infer method ###############################################################


def infer_end(
    self: _T, context: InferenceContext | None = None, **kwargs: Any
) -> Iterator[_T]:
    """Inference's end for nodes that yield themselves on inference.

    These are objects for which inference does not have any semantic,
    such as Module or Consts.
    """
    yield self


# We add ignores to all assignments to methods
# See https://github.com/python/mypy/issues/2427
nodes.Module._infer = infer_end
nodes.ClassDef._infer = infer_end
nodes.Lambda._infer = infer_end  # type: ignore[assignment]
nodes.Const._infer = infer_end  # type: ignore[assignment]
nodes.Slice._infer = infer_end  # type: ignore[assignment]


def _infer_sequence_helper(
    node: _BaseContainerT, context: InferenceContext | None = None
) -> list[SuccessfulInferenceResult]:
    """Infer all values based on _BaseContainer.elts."""
    values = []

    for elt in node.elts:
        if isinstance(elt, nodes.Starred):
            starred = helpers.safe_infer(elt.value, context)
            if not starred:
                raise InferenceError(node=node, context=context)
            if not hasattr(starred, "elts"):
                raise InferenceError(node=node, context=context)
            values.extend(_infer_sequence_helper(starred))
        elif isinstance(elt, nodes.NamedExpr):
            value = helpers.safe_infer(elt.value, context)
            if not value:
                raise InferenceError(node=node, context=context)
            values.append(value)
        else:
            values.append(elt)
    return values


@decorators.raise_if_nothing_inferred
def infer_sequence(
    self: _BaseContainerT,
    context: InferenceContext | None = None,
    **kwargs: Any,
) -> Iterator[_BaseContainerT]:
    has_starred_named_expr = any(
        isinstance(e, (nodes.Starred, nodes.NamedExpr)) for e in self.elts
    )
    if has_starred_named_expr:
        values = _infer_sequence_helper(self, context)
        new_seq = type(self)(
            lineno=self.lineno, col_offset=self.col_offset, parent=self.parent
        )
        new_seq.postinit(values)

        yield new_seq
    else:
        yield self


nodes.List._infer = infer_sequence  # type: ignore[assignment]
nodes.Tuple._infer = infer_sequence  # type: ignore[assignment]
nodes.Set._infer = infer_sequence  # type: ignore[assignment]


def infer_map(
    self: nodes.Dict, context: InferenceContext | None = None
) -> Iterator[nodes.Dict]:
    if not any(isinstance(k, nodes.DictUnpack) for k, _ in self.items):
        yield self
    else:
        items = _infer_map(self, context)
        new_seq = type(self)(self.lineno, self.col_offset, self.parent)
        new_seq.postinit(list(items.items()))
        yield new_seq


def _update_with_replacement(
    lhs_dict: dict[SuccessfulInferenceResult, SuccessfulInferenceResult],
    rhs_dict: dict[SuccessfulInferenceResult, SuccessfulInferenceResult],
) -> dict[SuccessfulInferenceResult, SuccessfulInferenceResult]:
    """Delete nodes that equate to duplicate keys.

    Since an astroid node doesn't 'equal' another node with the same value,
    this function uses the as_string method to make sure duplicate keys
    don't get through

    Note that both the key and the value are astroid nodes

    Fixes issue with DictUnpack causing duplicate keys
    in inferred Dict items

    :param lhs_dict: Dictionary to 'merge' nodes into
    :param rhs_dict: Dictionary with nodes to pull from
    :return : merged dictionary of nodes
    """
    combined_dict = itertools.chain(lhs_dict.items(), rhs_dict.items())
    # Overwrite keys which have the same string values
    string_map = {key.as_string(): (key, value) for key, value in combined_dict}
    # Return to dictionary
    return dict(string_map.values())


def _infer_map(
    node: nodes.Dict, context: InferenceContext | None
) -> dict[SuccessfulInferenceResult, SuccessfulInferenceResult]:
    """Infer all values based on Dict.items."""
    values: dict[SuccessfulInferenceResult, SuccessfulInferenceResult] = {}
    for name, value in node.items:
        if isinstance(name, nodes.DictUnpack):
            double_starred = helpers.safe_infer(value, context)
            if not double_starred:
                raise InferenceError
            if not isinstance(double_starred, nodes.Dict):
                raise InferenceError(node=node, context=context)
            unpack_items = _infer_map(double_starred, context)
            values = _update_with_replacement(values, unpack_items)
        else:
            key = helpers.safe_infer(name, context=context)
            safe_value = helpers.safe_infer(value, context=context)
            if any(not elem for elem in (key, safe_value)):
                raise InferenceError(node=node, context=context)
            # safe_value is SuccessfulInferenceResult as bool(Uninferable) == False
            values = _update_with_replacement(values, {key: safe_value})
    return values


nodes.Dict._infer = infer_map  # type: ignore[assignment]


def _higher_function_scope(node: nodes.NodeNG) -> nodes.FunctionDef | None:
    """Search for the first function which encloses the given
    scope. This can be used for looking up in that function's
    scope, in case looking up in a lower scope for a particular
    name fails.

    :param node: A scope node.
    :returns:
        ``None``, if no parent function scope was found,
        otherwise an instance of :class:`astroid.nodes.scoped_nodes.Function`,
        which encloses the given node.
    """
    current = node
    while current.parent and not isinstance(current.parent, nodes.FunctionDef):
        current = current.parent
    if current and current.parent:
        return current.parent  # type: ignore[no-any-return]
    return None


def infer_name(
    self: nodes.Name | nodes.AssignName,
    context: InferenceContext | None = None,
    **kwargs: Any,
) -> Generator[InferenceResult, None, None]:
    """Infer a Name: use name lookup rules."""
    frame, stmts = self.lookup(self.name)
    if not stmts:
        # Try to see if the name is enclosed in a nested function
        # and use the higher (first function) scope for searching.
        parent_function = _higher_function_scope(self.scope())
        if parent_function:
            _, stmts = parent_function.lookup(self.name)

        if not stmts:
            raise NameInferenceError(
                name=self.name, scope=self.scope(), context=context
            )
    context = copy_context(context)
    context.lookupname = self.name
    context.constraints[self.name] = constraint.get_constraints(self, frame)

    return bases._infer_stmts(stmts, context, frame)


# pylint: disable=no-value-for-parameter
# The order of the decorators here is important
# See https://github.com/PyCQA/astroid/commit/0a8a75db30da060a24922e05048bc270230f5
nodes.Name._infer = decorators.raise_if_nothing_inferred(
    decorators.path_wrapper(infer_name)
)
nodes.AssignName.infer_lhs = infer_name  # won't work with a path wrapper


@decorators.raise_if_nothing_inferred
@decorators.path_wrapper
def infer_call(
    self: nodes.Call, context: InferenceContext | None = None, **kwargs: Any
) -> Generator[InferenceResult, None, InferenceErrorInfo]:
    """Infer a Call node by trying to guess what the function returns."""
    callcontext = copy_context(context)
    callcontext.boundnode = None
    if context is not None:
        callcontext.extra_context = _populate_context_lookup(self, context.clone())

    for callee in self.func.infer(context):
        if isinstance(callee, util.UninferableBase):
            yield callee
            continue
        try:
            if hasattr(callee, "infer_call_result"):
                callcontext.callcontext = CallContext(
                    args=self.args, keywords=self.keywords, callee=callee
                )
                yield from callee.infer_call_result(caller=self, context=callcontext)
        except InferenceError:
            continue
    return InferenceErrorInfo(node=self, context=context)


nodes.Call._infer = infer_call  # type: ignore[assignment]


@decorators.raise_if_nothing_inferred
@decorators.path_wrapper
def infer_import(
    self: nodes.Import,
    context: InferenceContext | None = None,
    asname: bool = True,
    **kwargs: Any,
) -> Generator[nodes.Module, None, None]:
    """Infer an Import node: return the imported module/object."""
    context = context or InferenceContext()
    name = context.lookupname
    if name is None:
        raise InferenceError(node=self, context=context)

    try:
        if asname:
            yield self.do_import_module(self.real_name(name))
        else:
            yield self.do_import_module(name)
    except AstroidBuildingError as exc:
        raise InferenceError(node=self, context=context) from exc


nodes.Import._infer = infer_import


@decorators.raise_if_nothing_inferred
@decorators.path_wrapper
def infer_import_from(
    self: nodes.ImportFrom,
    context: InferenceContext | None = None,
    asname: bool = True,
    **kwargs: Any,
) -> Generator[InferenceResult, None, None]:
    """Infer a ImportFrom node: return the imported module/object."""
    context = context or InferenceContext()
    name = context.lookupname
    if name is None:
        raise InferenceError(node=self, context=context)
    if asname:
        try:
            name = self.real_name(name)
        except AttributeInferenceError as exc:
            # See https://github.com/PyCQA/pylint/issues/4692
            raise InferenceError(node=self, context=context) from exc
    try:
        module = self.do_import_module()
    except AstroidBuildingError as exc:
        raise InferenceError(node=self, context=context) from exc

    try:
        context = copy_context(context)
        context.lookupname = name
        stmts = module.getattr(name, ignore_locals=module is self.root())
        return bases._infer_stmts(stmts, context)
    except AttributeInferenceError as error:
        raise InferenceError(
            str(error), target=self, attribute=name, context=context
        ) from error


nodes.ImportFrom._infer = infer_import_from  # type: ignore[assignment]


def infer_attribute(
    self: nodes.Attribute | nodes.AssignAttr,
    context: InferenceContext | None = None,
    **kwargs: Any,
) -> Generator[InferenceResult, None, InferenceErrorInfo]:
    """Infer an Attribute node by using getattr on the associated object."""
    for owner in self.expr.infer(context):
        if isinstance(owner, util.UninferableBase):
            yield owner
            continue

        context = copy_context(context)
        old_boundnode = context.boundnode
        try:
            context.boundnode = owner
            if isinstance(owner, (nodes.ClassDef, bases.Instance)):
                frame = owner if isinstance(owner, nodes.ClassDef) else owner._proxied
                context.constraints[self.attrname] = constraint.get_constraints(
                    self, frame=frame
                )
            yield from owner.igetattr(self.attrname, context)
        except (
            AttributeInferenceError,
            InferenceError,
            AttributeError,
        ):
            pass
        finally:
            context.boundnode = old_boundnode
    return InferenceErrorInfo(node=self, context=context)


# The order of the decorators here is important
# See https://github.com/PyCQA/astroid/commit/0a8a75db30da060a24922e05048bc270230f5
nodes.Attribute._infer = decorators.raise_if_nothing_inferred(
    decorators.path_wrapper(infer_attribute)
)
# won't work with a path wrapper
nodes.AssignAttr.infer_lhs = decorators.raise_if_nothing_inferred(infer_attribute)


@decorators.raise_if_nothing_inferred
@decorators.path_wrapper
def infer_global(
    self: nodes.Global, context: InferenceContext | None = None, **kwargs: Any
) -> Generator[InferenceResult, None, None]:
    if context is None or context.lookupname is None:
        raise InferenceError(node=self, context=context)
    try:
        return bases._infer_stmts(self.root().getattr(context.lookupname), context)
    except AttributeInferenceError as error:
        raise InferenceError(
            str(error), target=self, attribute=context.lookupname, context=context
        ) from error


nodes.Global._infer = infer_global  # type: ignore[assignment]


_SUBSCRIPT_SENTINEL = object()


def infer_subscript(
    self: nodes.Subscript, context: InferenceContext | None = None, **kwargs: Any
) -> Generator[InferenceResult, None, InferenceErrorInfo | None]:
    """Inference for subscripts.

    We're understanding if the index is a Const
    or a slice, passing the result of inference
    to the value's `getitem` method, which should
    handle each supported index type accordingly.
    """

    found_one = False
    for value in self.value.infer(context):
        if isinstance(value, util.UninferableBase):
            yield util.Uninferable
            return None
        for index in self.slice.infer(context):
            if isinstance(index, util.UninferableBase):
                yield util.Uninferable
                return None

            # Try to deduce the index value.
            index_value = _SUBSCRIPT_SENTINEL
            if value.__class__ == bases.Instance:
                index_value = index
            elif index.__class__ == bases.Instance:
                instance_as_index = helpers.class_instance_as_index(index)
                if instance_as_index:
                    index_value = instance_as_index
            else:
                index_value = index

            if index_value is _SUBSCRIPT_SENTINEL:
                raise InferenceError(node=self, context=context)

            try:
                assigned = value.getitem(index_value, context)
            except (
                AstroidTypeError,
                AstroidIndexError,
                AstroidValueError,
                AttributeInferenceError,
                AttributeError,
            ) as exc:
                raise InferenceError(node=self, context=context) from exc

            # Prevent inferring if the inferred subscript
            # is the same as the original subscripted object.
            if self is assigned or isinstance(assigned, util.UninferableBase):
                yield util.Uninferable
                return None
            yield from assigned.infer(context)
            found_one = True

    if found_one:
        return InferenceErrorInfo(node=self, context=context)
    return None


# The order of the decorators here is important
# See https://github.com/PyCQA/astroid/commit/0a8a75db30da060a24922e05048bc270230f5
nodes.Subscript._infer = decorators.raise_if_nothing_inferred(  # type: ignore[assignment]
    decorators.path_wrapper(infer_subscript)
)
nodes.Subscript.infer_lhs = decorators.raise_if_nothing_inferred(infer_subscript)


@decorators.raise_if_nothing_inferred
@decorators.path_wrapper
def _infer_boolop(
    self: nodes.BoolOp, context: InferenceContext | None = None, **kwargs: Any
) -> Generator[InferenceResult, None, InferenceErrorInfo | None]:
    """Infer a boolean operation (and / or / not).

    The function will calculate the boolean operation
    for all pairs generated through inference for each component
    node.
    """
    values = self.values
    if self.op == "or":
        predicate = operator.truth
    else:
        predicate = operator.not_

    try:
        inferred_values = [value.infer(context=context) for value in values]
    except InferenceError:
        yield util.Uninferable
        return None

    for pair in itertools.product(*inferred_values):
        if any(isinstance(item, util.UninferableBase) for item in pair):
            # Can't infer the final result, just yield Uninferable.
            yield util.Uninferable
            continue

        bool_values = [item.bool_value() for item in pair]
        if any(isinstance(item, util.UninferableBase) for item in bool_values):
            # Can't infer the final result, just yield Uninferable.
            yield util.Uninferable
            continue

        # Since the boolean operations are short circuited operations,
        # this code yields the first value for which the predicate is True
        # and if no value respected the predicate, then the last value will
        # be returned (or Uninferable if there was no last value).
        # This is conforming to the semantics of `and` and `or`:
        #   1 and 0 -> 1
        #   0 and 1 -> 0
        #   1 or 0 -> 1
        #   0 or 1 -> 1
        value = util.Uninferable
        for value, bool_value in zip(pair, bool_values):
            if predicate(bool_value):
                yield value
                break
        else:
            yield value

    return InferenceErrorInfo(node=self, context=context)


nodes.BoolOp._infer = _infer_boolop


# UnaryOp, BinOp and AugAssign inferences


def _filter_operation_errors(
    self: _T,
    infer_callable: Callable[
        [_T, InferenceContext | None],
        Generator[InferenceResult | util.BadOperationMessage, None, None],
    ],
    context: InferenceContext | None,
    error: type[util.BadOperationMessage],
) -> Generator[InferenceResult, None, None]:
    for result in infer_callable(self, context):
        if isinstance(result, error):
            # For the sake of .infer(), we don't care about operation
            # errors, which is the job of pylint. So return something
            # which shows that we can't infer the result.
            yield util.Uninferable
        else:
            yield result


def _infer_unaryop(
    self: nodes.UnaryOp, context: InferenceContext | None = None
) -> Generator[InferenceResult | util.BadUnaryOperationMessage, None, None]:
    """Infer what an UnaryOp should return when evaluated."""
    for operand in self.operand.infer(context):
        try:
            yield operand.infer_unary_op(self.op)
        except TypeError as exc:
            # The operand doesn't support this operation.
            yield util.BadUnaryOperationMessage(operand, self.op, exc)
        except AttributeError as exc:
            meth = protocols.UNARY_OP_METHOD[self.op]
            if meth is None:
                # `not node`. Determine node's boolean
                # value and negate its result, unless it is
                # Uninferable, which will be returned as is.
                bool_value = operand.bool_value()
                if not isinstance(bool_value, util.UninferableBase):
                    yield nodes.const_factory(not bool_value)
                else:
                    yield util.Uninferable
            else:
                if not isinstance(operand, (bases.Instance, nodes.ClassDef)):
                    # The operation was used on something which
                    # doesn't support it.
                    yield util.BadUnaryOperationMessage(operand, self.op, exc)
                    continue

                try:
                    try:
                        methods = dunder_lookup.lookup(operand, meth)
                    except AttributeInferenceError:
                        yield util.BadUnaryOperationMessage(operand, self.op, exc)
                        continue

                    meth = methods[0]
                    inferred = next(meth.infer(context=context), None)
                    if (
                        isinstance(inferred, util.UninferableBase)
                        or not inferred.callable()
                    ):
                        continue

                    context = copy_context(context)
                    context.boundnode = operand
                    context.callcontext = CallContext(args=[], callee=inferred)

                    call_results = inferred.infer_call_result(self, context=context)
                    result = next(call_results, None)
                    if result is None:
                        # Failed to infer, return the same type.
                        yield operand
                    else:
                        yield result
                except AttributeInferenceError as inner_exc:
                    # The unary operation special method was not found.
                    yield util.BadUnaryOperationMessage(operand, self.op, inner_exc)
                except InferenceError:
                    yield util.Uninferable


@decorators.raise_if_nothing_inferred
@decorators.path_wrapper
def infer_unaryop(
    self: nodes.UnaryOp, context: InferenceContext | None = None, **kwargs: Any
) -> Generator[InferenceResult, None, InferenceErrorInfo]:
    """Infer what an UnaryOp should return when evaluated."""
    yield from _filter_operation_errors(
        self, _infer_unaryop, context, util.BadUnaryOperationMessage
    )
    return InferenceErrorInfo(node=self, context=context)


nodes.UnaryOp._infer_unaryop = _infer_unaryop
nodes.UnaryOp._infer = infer_unaryop


def _is_not_implemented(const) -> bool:
    """Check if the given const node is NotImplemented."""
    return isinstance(const, nodes.Const) and const.value is NotImplemented


def _infer_old_style_string_formatting(
    instance: nodes.Const, other: nodes.NodeNG, context: InferenceContext
) -> tuple[util.UninferableBase | nodes.Const]:
    """Infer the result of '"string" % ...'.

    TODO: Instead of returning Uninferable we should rely
    on the call to '%' to see if the result is actually uninferable.
    """
    if isinstance(other, nodes.Tuple):
        if util.Uninferable in other.elts:
            return (util.Uninferable,)
        inferred_positional = [helpers.safe_infer(i, context) for i in other.elts]
        if all(isinstance(i, nodes.Const) for i in inferred_positional):
            values = tuple(i.value for i in inferred_positional)
        else:
            values = None
    elif isinstance(other, nodes.Dict):
        values: dict[Any, Any] = {}
        for pair in other.items:
            key = helpers.safe_infer(pair[0], context)
            if not isinstance(key, nodes.Const):
                return (util.Uninferable,)
            value = helpers.safe_infer(pair[1], context)
            if not isinstance(value, nodes.Const):
                return (util.Uninferable,)
            values[key.value] = value.value
    elif isinstance(other, nodes.Const):
        values = other.value
    else:
        return (util.Uninferable,)

    try:
        return (nodes.const_factory(instance.value % values),)
    except (TypeError, KeyError, ValueError):
        return (util.Uninferable,)


def _invoke_binop_inference(
    instance: InferenceResult,
    opnode: nodes.AugAssign | nodes.BinOp,
    op: str,
    other: InferenceResult,
    context: InferenceContext,
    method_name: str,
) -> Generator[InferenceResult, None, None]:
    """Invoke binary operation inference on the given instance."""
    methods = dunder_lookup.lookup(instance, method_name)
    context = bind_context_to_node(context, instance)
    method = methods[0]
    context.callcontext.callee = method

    if (
        isinstance(instance, nodes.Const)
        and isinstance(instance.value, str)
        and op == "%"
    ):
        return iter(_infer_old_style_string_formatting(instance, other, context))

    try:
        inferred = next(method.infer(context=context))
    except StopIteration as e:
        raise InferenceError(node=method, context=context) from e
    if isinstance(inferred, util.UninferableBase):
        raise InferenceError
    if not isinstance(
        instance, (nodes.Const, nodes.Tuple, nodes.List, nodes.ClassDef, bases.Instance)
    ):
        raise InferenceError  # pragma: no cover # Used as a failsafe
    return instance.infer_binary_op(opnode, op, other, context, inferred)


def _aug_op(
    instance: InferenceResult,
    opnode: nodes.AugAssign,
    op: str,
    other: InferenceResult,
    context: InferenceContext,
    reverse: bool = False,
) -> functools.partial[Generator[InferenceResult, None, None]]:
    """Get an inference callable for an augmented binary operation."""
    method_name = protocols.AUGMENTED_OP_METHOD[op]
    return functools.partial(
        _invoke_binop_inference,
        instance=instance,
        op=op,
        opnode=opnode,
        other=other,
        context=context,
        method_name=method_name,
    )


def _bin_op(
    instance: InferenceResult,
    opnode: nodes.AugAssign | nodes.BinOp,
    op: str,
    other: InferenceResult,
    context: InferenceContext,
    reverse: bool = False,
) -> functools.partial[Generator[InferenceResult, None, None]]:
    """Get an inference callable for a normal binary operation.

    If *reverse* is True, then the reflected method will be used instead.
    """
    if reverse:
        method_name = protocols.REFLECTED_BIN_OP_METHOD[op]
    else:
        method_name = protocols.BIN_OP_METHOD[op]
    return functools.partial(
        _invoke_binop_inference,
        instance=instance,
        op=op,
        opnode=opnode,
        other=other,
        context=context,
        method_name=method_name,
    )


def _bin_op_or_union_type(
    left: bases.UnionType | nodes.ClassDef | nodes.Const,
    right: bases.UnionType | nodes.ClassDef | nodes.Const,
) -> Generator[InferenceResult, None, None]:
    """Create a new UnionType instance for binary or, e.g. int | str."""
    yield bases.UnionType(left, right)


def _get_binop_contexts(context, left, right):
    """Get contexts for binary operations.

    This will return two inference contexts, the first one
    for x.__op__(y), the other one for y.__rop__(x), where
    only the arguments are inversed.
    """
    # The order is important, since the first one should be
    # left.__op__(right).
    for arg in (right, left):
        new_context = context.clone()
        new_context.callcontext = CallContext(args=[arg])
        new_context.boundnode = None
        yield new_context


def _same_type(type1, type2) -> bool:
    """Check if type1 is the same as type2."""
    return type1.qname() == type2.qname()


def _get_binop_flow(
    left: InferenceResult,
    left_type: InferenceResult | None,
    binary_opnode: nodes.AugAssign | nodes.BinOp,
    right: InferenceResult,
    right_type: InferenceResult | None,
    context: InferenceContext,
    reverse_context: InferenceContext,
) -> list[functools.partial[Generator[InferenceResult, None, None]]]:
    """Get the flow for binary operations.

    The rules are a bit messy:

        * if left and right have the same type, then only one
          method will be called, left.__op__(right)
        * if left and right are unrelated typewise, then first
          left.__op__(right) is tried and if this does not exist
          or returns NotImplemented, then right.__rop__(left) is tried.
        * if left is a subtype of right, then only left.__op__(right)
          is tried.
        * if left is a supertype of right, then right.__rop__(left)
          is first tried and then left.__op__(right)
    """
    op = binary_opnode.op
    if _same_type(left_type, right_type):
        methods = [_bin_op(left, binary_opnode, op, right, context)]
    elif helpers.is_subtype(left_type, right_type):
        methods = [_bin_op(left, binary_opnode, op, right, context)]
    elif helpers.is_supertype(left_type, right_type):
        methods = [
            _bin_op(right, binary_opnode, op, left, reverse_context, reverse=True),
            _bin_op(left, binary_opnode, op, right, context),
        ]
    else:
        methods = [
            _bin_op(left, binary_opnode, op, right, context),
            _bin_op(right, binary_opnode, op, left, reverse_context, reverse=True),
        ]

    if (
        PY310_PLUS
        and op == "|"
        and (
            isinstance(left, (bases.UnionType, nodes.ClassDef))
            or isinstance(left, nodes.Const)
            and left.value is None
        )
        and (
            isinstance(right, (bases.UnionType, nodes.ClassDef))
            or isinstance(right, nodes.Const)
            and right.value is None
        )
    ):
        methods.extend([functools.partial(_bin_op_or_union_type, left, right)])
    return methods


def _get_aug_flow(
    left: InferenceResult,
    left_type: InferenceResult | None,
    aug_opnode: nodes.AugAssign,
    right: InferenceResult,
    right_type: InferenceResult | None,
    context: InferenceContext,
    reverse_context: InferenceContext,
) -> list[functools.partial[Generator[InferenceResult, None, None]]]:
    """Get the flow for augmented binary operations.

    The rules are a bit messy:

        * if left and right have the same type, then left.__augop__(right)
          is first tried and then left.__op__(right).
        * if left and right are unrelated typewise, then
          left.__augop__(right) is tried, then left.__op__(right)
          is tried and then right.__rop__(left) is tried.
        * if left is a subtype of right, then left.__augop__(right)
          is tried and then left.__op__(right).
        * if left is a supertype of right, then left.__augop__(right)
          is tried, then right.__rop__(left) and then
          left.__op__(right)
    """
    bin_op = aug_opnode.op.strip("=")
    aug_op = aug_opnode.op
    if _same_type(left_type, right_type):
        methods = [
            _aug_op(left, aug_opnode, aug_op, right, context),
            _bin_op(left, aug_opnode, bin_op, right, context),
        ]
    elif helpers.is_subtype(left_type, right_type):
        methods = [
            _aug_op(left, aug_opnode, aug_op, right, context),
            _bin_op(left, aug_opnode, bin_op, right, context),
        ]
    elif helpers.is_supertype(left_type, right_type):
        methods = [
            _aug_op(left, aug_opnode, aug_op, right, context),
            _bin_op(right, aug_opnode, bin_op, left, reverse_context, reverse=True),
            _bin_op(left, aug_opnode, bin_op, right, context),
        ]
    else:
        methods = [
            _aug_op(left, aug_opnode, aug_op, right, context),
            _bin_op(left, aug_opnode, bin_op, right, context),
            _bin_op(right, aug_opnode, bin_op, left, reverse_context, reverse=True),
        ]
    return methods


def _infer_binary_operation(
    left: InferenceResult,
    right: InferenceResult,
    binary_opnode: nodes.AugAssign | nodes.BinOp,
    context: InferenceContext,
    flow_factory: GetFlowFactory,
) -> Generator[InferenceResult | util.BadBinaryOperationMessage, None, None]:
    """Infer a binary operation between a left operand and a right operand.

    This is used by both normal binary operations and augmented binary
    operations, the only difference is the flow factory used.
    """

    context, reverse_context = _get_binop_contexts(context, left, right)
    left_type = helpers.object_type(left)
    right_type = helpers.object_type(right)
    methods = flow_factory(
        left, left_type, binary_opnode, right, right_type, context, reverse_context
    )
    for method in methods:
        try:
            results = list(method())
        except AttributeError:
            continue
        except AttributeInferenceError:
            continue
        except InferenceError:
            yield util.Uninferable
            return
        else:
            if any(isinstance(result, util.UninferableBase) for result in results):
                yield util.Uninferable
                return

            if all(map(_is_not_implemented, results)):
                continue
            not_implemented = sum(
                1 for result in results if _is_not_implemented(result)
            )
            if not_implemented and not_implemented != len(results):
                # Can't infer yet what this is.
                yield util.Uninferable
                return

            yield from results
            return
    # The operation doesn't seem to be supported so let the caller know about it
    yield util.BadBinaryOperationMessage(left_type, binary_opnode.op, right_type)


def _infer_binop(
    self: nodes.BinOp, context: InferenceContext | None = None
) -> Generator[InferenceResult | util.BadBinaryOperationMessage, None, None]:
    """Binary operation inference logic."""
    left = self.left
    right = self.right

    # we use two separate contexts for evaluating lhs and rhs because
    # 1. evaluating lhs may leave some undesired entries in context.path
    #    which may not let us infer right value of rhs
    context = context or InferenceContext()
    lhs_context = copy_context(context)
    rhs_context = copy_context(context)
    lhs_iter = left.infer(context=lhs_context)
    rhs_iter = right.infer(context=rhs_context)
    for lhs, rhs in itertools.product(lhs_iter, rhs_iter):
        if any(isinstance(value, util.UninferableBase) for value in (rhs, lhs)):
            # Don't know how to process this.
            yield util.Uninferable
            return

        try:
            yield from _infer_binary_operation(lhs, rhs, self, context, _get_binop_flow)
        except _NonDeducibleTypeHierarchy:
            yield util.Uninferable


@decorators.yes_if_nothing_inferred
@decorators.path_wrapper
def infer_binop(
    self: nodes.BinOp, context: InferenceContext | None = None, **kwargs: Any
) -> Generator[InferenceResult, None, None]:
    return _filter_operation_errors(
        self, _infer_binop, context, util.BadBinaryOperationMessage
    )


nodes.BinOp._infer_binop = _infer_binop
nodes.BinOp._infer = infer_binop

COMPARE_OPS: dict[str, Callable[[Any, Any], bool]] = {
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "in": lambda a, b: a in b,
    "not in": lambda a, b: a not in b,
}
UNINFERABLE_OPS = {
    "is",
    "is not",
}


def _to_literal(node: nodes.NodeNG) -> Any:
    # Can raise SyntaxError or ValueError from ast.literal_eval
    # Can raise AttributeError from node.as_string() as not all nodes have a visitor
    # Is this the stupidest idea or the simplest idea?
    return ast.literal_eval(node.as_string())


def _do_compare(
    left_iter: Iterable[nodes.NodeNG], op: str, right_iter: Iterable[nodes.NodeNG]
) -> bool | util.UninferableBase:
    """
    If all possible combinations are either True or False, return that:
    >>> _do_compare([1, 2], '<=', [3, 4])
    True
    >>> _do_compare([1, 2], '==', [3, 4])
    False

    If any item is uninferable, or if some combinations are True and some
    are False, return Uninferable:
    >>> _do_compare([1, 3], '<=', [2, 4])
    util.Uninferable
    """
    retval: bool | None = None
    if op in UNINFERABLE_OPS:
        return util.Uninferable
    op_func = COMPARE_OPS[op]

    for left, right in itertools.product(left_iter, right_iter):
        if isinstance(left, util.UninferableBase) or isinstance(
            right, util.UninferableBase
        ):
            return util.Uninferable

        try:
            left, right = _to_literal(left), _to_literal(right)
        except (SyntaxError, ValueError, AttributeError):
            return util.Uninferable

        try:
            expr = op_func(left, right)
        except TypeError as exc:
            raise AstroidTypeError from exc

        if retval is None:
            retval = expr
        elif retval != expr:
            return util.Uninferable
            # (or both, but "True | False" is basically the same)

    assert retval is not None
    return retval  # it was all the same value


def _infer_compare(
    self: nodes.Compare, context: InferenceContext | None = None, **kwargs: Any
) -> Generator[nodes.Const | util.UninferableBase, None, None]:
    """Chained comparison inference logic."""
    retval: bool | util.UninferableBase = True

    ops = self.ops
    left_node = self.left
    lhs = list(left_node.infer(context=context))
    # should we break early if first element is uninferable?
    for op, right_node in ops:
        # eagerly evaluate rhs so that values can be re-used as lhs
        rhs = list(right_node.infer(context=context))
        try:
            retval = _do_compare(lhs, op, rhs)
        except AstroidTypeError:
            retval = util.Uninferable
            break
        if retval is not True:
            break  # short-circuit
        lhs = rhs  # continue
    if retval is util.Uninferable:
        yield retval  # type: ignore[misc]
    else:
        yield nodes.Const(retval)


nodes.Compare._infer = _infer_compare  # type: ignore[assignment]


def _infer_augassign(
    self: nodes.AugAssign, context: InferenceContext | None = None
) -> Generator[InferenceResult | util.BadBinaryOperationMessage, None, None]:
    """Inference logic for augmented binary operations."""
    context = context or InferenceContext()

    rhs_context = context.clone()

    lhs_iter = self.target.infer_lhs(context=context)
    rhs_iter = self.value.infer(context=rhs_context)
    for lhs, rhs in itertools.product(lhs_iter, rhs_iter):
        if any(isinstance(value, util.UninferableBase) for value in (rhs, lhs)):
            # Don't know how to process this.
            yield util.Uninferable
            return

        try:
            yield from _infer_binary_operation(
                left=lhs,
                right=rhs,
                binary_opnode=self,
                context=context,
                flow_factory=_get_aug_flow,
            )
        except _NonDeducibleTypeHierarchy:
            yield util.Uninferable


@decorators.raise_if_nothing_inferred
@decorators.path_wrapper
def infer_augassign(
    self: nodes.AugAssign, context: InferenceContext | None = None, **kwargs: Any
) -> Generator[InferenceResult, None, None]:
    return _filter_operation_errors(
        self, _infer_augassign, context, util.BadBinaryOperationMessage
    )


nodes.AugAssign._infer_augassign = _infer_augassign
nodes.AugAssign._infer = infer_augassign

# End of binary operation inference.


@decorators.raise_if_nothing_inferred
def infer_arguments(
    self: nodes.Arguments, context: InferenceContext | None = None, **kwargs: Any
) -> Generator[InferenceResult, None, None]:
    if context is None or context.lookupname is None:
        raise InferenceError(node=self, context=context)
    return protocols._arguments_infer_argname(self, context.lookupname, context)


nodes.Arguments._infer = infer_arguments  # type: ignore[assignment]


@decorators.raise_if_nothing_inferred
@decorators.path_wrapper
def infer_assign(
    self: nodes.AssignName | nodes.AssignAttr,
    context: InferenceContext | None = None,
    **kwargs: Any,
) -> Generator[InferenceResult, None, None]:
    """Infer a AssignName/AssignAttr: need to inspect the RHS part of the
    assign node.
    """
    if isinstance(self.parent, nodes.AugAssign):
        return self.parent.infer(context)

    stmts = list(self.assigned_stmts(context=context))
    return bases._infer_stmts(stmts, context)


nodes.AssignName._infer = infer_assign
nodes.AssignAttr._infer = infer_assign


@decorators.raise_if_nothing_inferred
@decorators.path_wrapper
def infer_empty_node(
    self: nodes.EmptyNode, context: InferenceContext | None = None, **kwargs: Any
) -> Generator[InferenceResult, None, None]:
    if not self.has_underlying_object():
        yield util.Uninferable
    else:
        try:
            yield from AstroidManager().infer_ast_from_something(
                self.object, context=context
            )
        except AstroidError:
            yield util.Uninferable


nodes.EmptyNode._infer = infer_empty_node  # type: ignore[assignment]


def _populate_context_lookup(call: nodes.Call, context: InferenceContext | None):
    # Allows context to be saved for later
    # for inference inside a function
    context_lookup: dict[InferenceResult, InferenceContext] = {}
    if context is None:
        return context_lookup
    for arg in call.args:
        if isinstance(arg, nodes.Starred):
            context_lookup[arg.value] = context
        else:
            context_lookup[arg] = context
    keywords = call.keywords if call.keywords is not None else []
    for keyword in keywords:
        context_lookup[keyword.value] = context
    return context_lookup


@decorators.raise_if_nothing_inferred
def infer_ifexp(
    self: nodes.IfExp, context: InferenceContext | None = None, **kwargs: Any
) -> Generator[InferenceResult, None, None]:
    """Support IfExp inference.

    If we can't infer the truthiness of the condition, we default
    to inferring both branches. Otherwise, we infer either branch
    depending on the condition.
    """
    both_branches = False
    # We use two separate contexts for evaluating lhs and rhs because
    # evaluating lhs may leave some undesired entries in context.path
    # which may not let us infer right value of rhs.

    context = context or InferenceContext()
    lhs_context = copy_context(context)
    rhs_context = copy_context(context)
    try:
        test = next(self.test.infer(context=context.clone()))
    except (InferenceError, StopIteration):
        both_branches = True
    else:
        if not isinstance(test, util.UninferableBase):
            if test.bool_value():
                yield from self.body.infer(context=lhs_context)
            else:
                yield from self.orelse.infer(context=rhs_context)
        else:
            both_branches = True
    if both_branches:
        yield from self.body.infer(context=lhs_context)
        yield from self.orelse.infer(context=rhs_context)


nodes.IfExp._infer = infer_ifexp  # type: ignore[assignment]


def infer_functiondef(
    self: _FunctionDefT, context: InferenceContext | None = None, **kwargs: Any
) -> Generator[Property | _FunctionDefT, None, InferenceErrorInfo]:
    if not self.decorators or not bases._is_property(self):
        yield self
        return InferenceErrorInfo(node=self, context=context)

    # When inferring a property, we instantiate a new `objects.Property` object,
    # which in turn, because it inherits from `FunctionDef`, sets itself in the locals
    # of the wrapping frame. This means that every time we infer a property, the locals
    # are mutated with a new instance of the property. To avoid this, we detect this
    # scenario and avoid passing the `parent` argument to the constructor.
    parent_frame = self.parent.frame(future=True)
    property_already_in_parent_locals = self.name in parent_frame.locals and any(
        isinstance(val, objects.Property) for val in parent_frame.locals[self.name]
    )
    # We also don't want to pass parent if the definition is within a Try node
    if isinstance(self.parent, (nodes.TryExcept, nodes.TryFinally, nodes.If)):
        property_already_in_parent_locals = True

    prop_func = objects.Property(
        function=self,
        name=self.name,
        lineno=self.lineno,
        parent=self.parent if not property_already_in_parent_locals else None,
        col_offset=self.col_offset,
    )
    if property_already_in_parent_locals:
        prop_func.parent = self.parent
    prop_func.postinit(body=[], args=self.args, doc_node=self.doc_node)
    yield prop_func
    return InferenceErrorInfo(node=self, context=context)


nodes.FunctionDef._infer = infer_functiondef
