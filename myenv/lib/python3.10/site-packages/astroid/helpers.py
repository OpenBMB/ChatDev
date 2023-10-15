# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""Various helper utilities."""

from __future__ import annotations

from collections.abc import Generator

from astroid import bases, manager, nodes, raw_building, util
from astroid.context import CallContext, InferenceContext
from astroid.exceptions import (
    AstroidTypeError,
    AttributeInferenceError,
    InferenceError,
    MroError,
    _NonDeducibleTypeHierarchy,
)
from astroid.nodes import scoped_nodes
from astroid.typing import InferenceResult, SuccessfulInferenceResult


def _build_proxy_class(cls_name: str, builtins: nodes.Module) -> nodes.ClassDef:
    proxy = raw_building.build_class(cls_name)
    proxy.parent = builtins
    return proxy


def _function_type(
    function: nodes.Lambda | bases.UnboundMethod, builtins: nodes.Module
) -> nodes.ClassDef:
    if isinstance(function, scoped_nodes.Lambda):
        if function.root().name == "builtins":
            cls_name = "builtin_function_or_method"
        else:
            cls_name = "function"
    elif isinstance(function, bases.BoundMethod):
        cls_name = "method"
    else:
        cls_name = "function"
    return _build_proxy_class(cls_name, builtins)


def _object_type(
    node: SuccessfulInferenceResult, context: InferenceContext | None = None
) -> Generator[InferenceResult | None, None, None]:
    astroid_manager = manager.AstroidManager()
    builtins = astroid_manager.builtins_module
    context = context or InferenceContext()

    for inferred in node.infer(context=context):
        if isinstance(inferred, scoped_nodes.ClassDef):
            if inferred.newstyle:
                metaclass = inferred.metaclass(context=context)
                if metaclass:
                    yield metaclass
                    continue
            yield builtins.getattr("type")[0]
        elif isinstance(inferred, (scoped_nodes.Lambda, bases.UnboundMethod)):
            yield _function_type(inferred, builtins)
        elif isinstance(inferred, scoped_nodes.Module):
            yield _build_proxy_class("module", builtins)
        elif isinstance(inferred, nodes.Unknown):
            raise InferenceError
        elif isinstance(inferred, util.UninferableBase):
            yield inferred
        elif isinstance(inferred, (bases.Proxy, nodes.Slice)):
            yield inferred._proxied
        else:  # pragma: no cover
            raise AssertionError(f"We don't handle {type(inferred)} currently")


def object_type(
    node: SuccessfulInferenceResult, context: InferenceContext | None = None
) -> InferenceResult | None:
    """Obtain the type of the given node.

    This is used to implement the ``type`` builtin, which means that it's
    used for inferring type calls, as well as used in a couple of other places
    in the inference.
    The node will be inferred first, so this function can support all
    sorts of objects, as long as they support inference.
    """

    try:
        types = set(_object_type(node, context))
    except InferenceError:
        return util.Uninferable
    if len(types) > 1 or not types:
        return util.Uninferable
    return list(types)[0]


def _object_type_is_subclass(
    obj_type, class_or_seq, context: InferenceContext | None = None
):
    if not isinstance(class_or_seq, (tuple, list)):
        class_seq = (class_or_seq,)
    else:
        class_seq = class_or_seq

    if isinstance(obj_type, util.UninferableBase):
        return util.Uninferable

    # Instances are not types
    class_seq = [
        item if not isinstance(item, bases.Instance) else util.Uninferable
        for item in class_seq
    ]
    # strict compatibility with issubclass
    # issubclass(type, (object, 1)) evaluates to true
    # issubclass(object, (1, type)) raises TypeError
    for klass in class_seq:
        if isinstance(klass, util.UninferableBase):
            raise AstroidTypeError("arg 2 must be a type or tuple of types")

        for obj_subclass in obj_type.mro():
            if obj_subclass == klass:
                return True
    return False


def object_isinstance(node, class_or_seq, context: InferenceContext | None = None):
    """Check if a node 'isinstance' any node in class_or_seq.

    :param node: A given node
    :param class_or_seq: Union[nodes.NodeNG, Sequence[nodes.NodeNG]]
    :rtype: bool

    :raises AstroidTypeError: if the given ``classes_or_seq`` are not types
    """
    obj_type = object_type(node, context)
    if isinstance(obj_type, util.UninferableBase):
        return util.Uninferable
    return _object_type_is_subclass(obj_type, class_or_seq, context=context)


def object_issubclass(node, class_or_seq, context: InferenceContext | None = None):
    """Check if a type is a subclass of any node in class_or_seq.

    :param node: A given node
    :param class_or_seq: Union[Nodes.NodeNG, Sequence[nodes.NodeNG]]
    :rtype: bool

    :raises AstroidTypeError: if the given ``classes_or_seq`` are not types
    :raises AstroidError: if the type of the given node cannot be inferred
        or its type's mro doesn't work
    """
    if not isinstance(node, nodes.ClassDef):
        raise TypeError(f"{node} needs to be a ClassDef node")
    return _object_type_is_subclass(node, class_or_seq, context=context)


def safe_infer(
    node: nodes.NodeNG | bases.Proxy, context: InferenceContext | None = None
) -> InferenceResult | None:
    """Return the inferred value for the given node.

    Return None if inference failed or if there is some ambiguity (more than
    one node has been inferred).
    """
    try:
        inferit = node.infer(context=context)
        value = next(inferit)
    except (InferenceError, StopIteration):
        return None
    try:
        next(inferit)
        return None  # None if there is ambiguity on the inferred node
    except InferenceError:
        return None  # there is some kind of ambiguity
    except StopIteration:
        return value


def has_known_bases(klass, context: InferenceContext | None = None) -> bool:
    """Return whether all base classes of a class could be inferred."""
    try:
        return klass._all_bases_known
    except AttributeError:
        pass
    for base in klass.bases:
        result = safe_infer(base, context=context)
        # TODO: check for A->B->A->B pattern in class structure too?
        if (
            not isinstance(result, scoped_nodes.ClassDef)
            or result is klass
            or not has_known_bases(result, context=context)
        ):
            klass._all_bases_known = False
            return False
    klass._all_bases_known = True
    return True


def _type_check(type1, type2) -> bool:
    if not all(map(has_known_bases, (type1, type2))):
        raise _NonDeducibleTypeHierarchy

    if not all([type1.newstyle, type2.newstyle]):
        return False
    try:
        return type1 in type2.mro()[:-1]
    except MroError as e:
        # The MRO is invalid.
        raise _NonDeducibleTypeHierarchy from e


def is_subtype(type1, type2) -> bool:
    """Check if *type1* is a subtype of *type2*."""
    return _type_check(type1=type2, type2=type1)


def is_supertype(type1, type2) -> bool:
    """Check if *type2* is a supertype of *type1*."""
    return _type_check(type1, type2)


def class_instance_as_index(node: SuccessfulInferenceResult) -> nodes.Const | None:
    """Get the value as an index for the given instance.

    If an instance provides an __index__ method, then it can
    be used in some scenarios where an integer is expected,
    for instance when multiplying or subscripting a list.
    """
    context = InferenceContext()
    try:
        for inferred in node.igetattr("__index__", context=context):
            if not isinstance(inferred, bases.BoundMethod):
                continue

            context.boundnode = node
            context.callcontext = CallContext(args=[], callee=inferred)
            for result in inferred.infer_call_result(node, context=context):
                if isinstance(result, nodes.Const) and isinstance(result.value, int):
                    return result
    except InferenceError:
        pass
    return None


def object_len(node, context: InferenceContext | None = None):
    """Infer length of given node object.

    :param Union[nodes.ClassDef, nodes.Instance] node:
    :param node: Node to infer length of

    :raises AstroidTypeError: If an invalid node is returned
        from __len__ method or no __len__ method exists
    :raises InferenceError: If the given node cannot be inferred
        or if multiple nodes are inferred or if the code executed in python
        would result in a infinite recursive check for length
    :rtype int: Integer length of node
    """
    # pylint: disable=import-outside-toplevel; circular import
    from astroid.objects import FrozenSet

    inferred_node = safe_infer(node, context=context)

    # prevent self referential length calls from causing a recursion error
    # see https://github.com/PyCQA/astroid/issues/777
    node_frame = node.frame(future=True)
    if (
        isinstance(node_frame, scoped_nodes.FunctionDef)
        and node_frame.name == "__len__"
        and hasattr(inferred_node, "_proxied")
        and inferred_node._proxied == node_frame.parent
    ):
        message = (
            "Self referential __len__ function will "
            "cause a RecursionError on line {} of {}".format(
                node.lineno, node.root().file
            )
        )
        raise InferenceError(message)

    if inferred_node is None or isinstance(inferred_node, util.UninferableBase):
        raise InferenceError(node=node)
    if isinstance(inferred_node, nodes.Const) and isinstance(
        inferred_node.value, (bytes, str)
    ):
        return len(inferred_node.value)
    if isinstance(inferred_node, (nodes.List, nodes.Set, nodes.Tuple, FrozenSet)):
        return len(inferred_node.elts)
    if isinstance(inferred_node, nodes.Dict):
        return len(inferred_node.items)

    node_type = object_type(inferred_node, context=context)
    if not node_type:
        raise InferenceError(node=node)

    try:
        len_call = next(node_type.igetattr("__len__", context=context))
    except StopIteration as e:
        raise AstroidTypeError(str(e)) from e
    except AttributeInferenceError as e:
        raise AstroidTypeError(
            f"object of type '{node_type.pytype()}' has no len()"
        ) from e

    inferred = len_call.infer_call_result(node, context)
    if isinstance(inferred, util.UninferableBase):
        raise InferenceError(node=node, context=context)
    result_of_len = next(inferred, None)
    if (
        isinstance(result_of_len, nodes.Const)
        and result_of_len.pytype() == "builtins.int"
    ):
        return result_of_len.value
    if (
        result_of_len is None
        or isinstance(result_of_len, bases.Instance)
        and result_of_len.is_subtype_of("builtins.int")
    ):
        # Fake a result as we don't know the arguments of the instance call.
        return 0
    raise AstroidTypeError(
        f"'{result_of_len}' object cannot be interpreted as an integer"
    )
