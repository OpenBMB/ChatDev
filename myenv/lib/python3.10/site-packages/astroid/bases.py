# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""This module contains base classes and functions for the nodes and some
inference utils.
"""
from __future__ import annotations

import collections
import collections.abc
import sys
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, ClassVar

from astroid import decorators, nodes
from astroid.const import PY310_PLUS
from astroid.context import (
    CallContext,
    InferenceContext,
    bind_context_to_node,
    copy_context,
)
from astroid.exceptions import (
    AstroidTypeError,
    AttributeInferenceError,
    InferenceError,
    NameInferenceError,
)
from astroid.typing import InferBinaryOp, InferenceErrorInfo, InferenceResult
from astroid.util import Uninferable, UninferableBase, lazy_descriptor, lazy_import

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal

if TYPE_CHECKING:
    from astroid.constraint import Constraint

objectmodel = lazy_import("interpreter.objectmodel")
helpers = lazy_import("helpers")
manager = lazy_import("manager")


# TODO: check if needs special treatment
BOOL_SPECIAL_METHOD = "__bool__"
BUILTINS = "builtins"  # TODO Remove in 2.8

PROPERTIES = {"builtins.property", "abc.abstractproperty"}
if PY310_PLUS:
    PROPERTIES.add("enum.property")

# List of possible property names. We use this list in order
# to see if a method is a property or not. This should be
# pretty reliable and fast, the alternative being to check each
# decorator to see if its a real property-like descriptor, which
# can be too complicated.
# Also, these aren't qualified, because each project can
# define them, we shouldn't expect to know every possible
# property-like decorator!
POSSIBLE_PROPERTIES = {
    "cached_property",
    "cachedproperty",
    "lazyproperty",
    "lazy_property",
    "reify",
    "lazyattribute",
    "lazy_attribute",
    "LazyProperty",
    "lazy",
    "cache_readonly",
    "DynamicClassAttribute",
}


def _is_property(meth, context: InferenceContext | None = None) -> bool:
    decoratornames = meth.decoratornames(context=context)
    if PROPERTIES.intersection(decoratornames):
        return True
    stripped = {
        name.split(".")[-1]
        for name in decoratornames
        if not isinstance(name, UninferableBase)
    }
    if any(name in stripped for name in POSSIBLE_PROPERTIES):
        return True

    # Lookup for subclasses of *property*
    if not meth.decorators:
        return False
    for decorator in meth.decorators.nodes or ():
        inferred = helpers.safe_infer(decorator, context=context)
        if inferred is None or isinstance(inferred, UninferableBase):
            continue
        if inferred.__class__.__name__ == "ClassDef":
            for base_class in inferred.bases:
                if base_class.__class__.__name__ != "Name":
                    continue
                module, _ = base_class.lookup(base_class.name)
                if module.name == "builtins" and base_class.name == "property":
                    return True

    return False


class Proxy:
    """A simple proxy object.

    Note:

    Subclasses of this object will need a custom __getattr__
    if new instance attributes are created. See the Const class
    """

    _proxied: nodes.ClassDef | nodes.Lambda | Proxy | None = (
        None  # proxied object may be set by class or by instance
    )

    def __init__(
        self, proxied: nodes.ClassDef | nodes.Lambda | Proxy | None = None
    ) -> None:
        if proxied is None:
            # This is a hack to allow calling this __init__ during bootstrapping of
            # builtin classes and their docstrings.
            # For Const, Generator, and UnionType nodes the _proxied attribute
            # is set during bootstrapping
            # as we first need to build the ClassDef that they can proxy.
            # Thus, if proxied is None self should be a Const or Generator
            # as that is the only way _proxied will be correctly set as a ClassDef.
            assert isinstance(self, (nodes.Const, Generator, UnionType))
        else:
            self._proxied = proxied

    def __getattr__(self, name):
        if name == "_proxied":
            return self.__class__._proxied
        if name in self.__dict__:
            return self.__dict__[name]
        return getattr(self._proxied, name)

    def infer(  # type: ignore[return]
        self, context: InferenceContext | None = None, **kwargs: Any
    ) -> collections.abc.Generator[InferenceResult, None, InferenceErrorInfo | None]:
        yield self


def _infer_stmts(
    stmts: Sequence[nodes.NodeNG | UninferableBase | Instance],
    context: InferenceContext | None,
    frame: nodes.NodeNG | Instance | None = None,
) -> collections.abc.Generator[InferenceResult, None, None]:
    """Return an iterator on statements inferred by each statement in *stmts*."""
    inferred = False
    constraint_failed = False
    if context is not None:
        name = context.lookupname
        context = context.clone()
        constraints = context.constraints.get(name, {})
    else:
        name = None
        constraints = {}
        context = InferenceContext()

    for stmt in stmts:
        if isinstance(stmt, UninferableBase):
            yield stmt
            inferred = True
            continue
        # 'context' is always InferenceContext and Instances get '_infer_name' from ClassDef
        context.lookupname = stmt._infer_name(frame, name)  # type: ignore[union-attr]
        try:
            stmt_constraints: set[Constraint] = set()
            for constraint_stmt, potential_constraints in constraints.items():
                if not constraint_stmt.parent_of(stmt):
                    stmt_constraints.update(potential_constraints)
            for inf in stmt.infer(context=context):
                if all(constraint.satisfied_by(inf) for constraint in stmt_constraints):
                    yield inf
                    inferred = True
                else:
                    constraint_failed = True
        except NameInferenceError:
            continue
        except InferenceError:
            yield Uninferable
            inferred = True

    if not inferred and constraint_failed:
        yield Uninferable
    elif not inferred:
        raise InferenceError(
            "Inference failed for all members of {stmts!r}.",
            stmts=stmts,
            frame=frame,
            context=context,
        )


def _infer_method_result_truth(instance, method_name, context):
    # Get the method from the instance and try to infer
    # its return's truth value.
    meth = next(instance.igetattr(method_name, context=context), None)
    if meth and hasattr(meth, "infer_call_result"):
        if not meth.callable():
            return Uninferable
        try:
            context.callcontext = CallContext(args=[], callee=meth)
            for value in meth.infer_call_result(instance, context=context):
                if isinstance(value, UninferableBase):
                    return value
                try:
                    inferred = next(value.infer(context=context))
                except StopIteration as e:
                    raise InferenceError(context=context) from e
                return inferred.bool_value()
        except InferenceError:
            pass
    return Uninferable


class BaseInstance(Proxy):
    """An instance base class, which provides lookup methods for potential
    instances.
    """

    special_attributes = None

    def display_type(self) -> str:
        return "Instance of"

    def getattr(self, name, context: InferenceContext | None = None, lookupclass=True):
        try:
            values = self._proxied.instance_attr(name, context)
        except AttributeInferenceError as exc:
            if self.special_attributes and name in self.special_attributes:
                return [self.special_attributes.lookup(name)]

            if lookupclass:
                # Class attributes not available through the instance
                # unless they are explicitly defined.
                return self._proxied.getattr(name, context, class_context=False)

            raise AttributeInferenceError(
                target=self, attribute=name, context=context
            ) from exc
        # since we've no context information, return matching class members as
        # well
        if lookupclass:
            try:
                return values + self._proxied.getattr(
                    name, context, class_context=False
                )
            except AttributeInferenceError:
                pass
        return values

    def igetattr(self, name, context: InferenceContext | None = None):
        """Inferred getattr."""
        if not context:
            context = InferenceContext()
        try:
            context.lookupname = name
            # avoid recursively inferring the same attr on the same class
            if context.push(self._proxied):
                raise InferenceError(
                    message="Cannot infer the same attribute again",
                    node=self,
                    context=context,
                )

            # XXX frame should be self._proxied, or not ?
            get_attr = self.getattr(name, context, lookupclass=False)
            yield from _infer_stmts(
                self._wrap_attr(get_attr, context), context, frame=self
            )
        except AttributeInferenceError:
            try:
                # fallback to class.igetattr since it has some logic to handle
                # descriptors
                # But only if the _proxied is the Class.
                if self._proxied.__class__.__name__ != "ClassDef":
                    raise
                attrs = self._proxied.igetattr(name, context, class_context=False)
                yield from self._wrap_attr(attrs, context)
            except AttributeInferenceError as error:
                raise InferenceError(**vars(error)) from error

    def _wrap_attr(self, attrs, context: InferenceContext | None = None):
        """Wrap bound methods of attrs in a InstanceMethod proxies."""
        for attr in attrs:
            if isinstance(attr, UnboundMethod):
                if _is_property(attr):
                    yield from attr.infer_call_result(self, context)
                else:
                    yield BoundMethod(attr, self)
            elif hasattr(attr, "name") and attr.name == "<lambda>":
                if attr.args.arguments and attr.args.arguments[0].name == "self":
                    yield BoundMethod(attr, self)
                    continue
                yield attr
            else:
                yield attr

    def infer_call_result(
        self, caller: nodes.Call | Proxy, context: InferenceContext | None = None
    ):
        """Infer what a class instance is returning when called."""
        context = bind_context_to_node(context, self)
        inferred = False

        # If the call is an attribute on the instance, we infer the attribute itself
        if isinstance(caller, nodes.Call) and isinstance(caller.func, nodes.Attribute):
            for res in self.igetattr(caller.func.attrname, context):
                inferred = True
                yield res

        # Otherwise we infer the call to the __call__ dunder normally
        for node in self._proxied.igetattr("__call__", context):
            if isinstance(node, UninferableBase) or not node.callable():
                continue
            for res in node.infer_call_result(caller, context):
                inferred = True
                yield res
        if not inferred:
            raise InferenceError(node=self, caller=caller, context=context)


class Instance(BaseInstance):
    """A special node representing a class instance."""

    _proxied: nodes.ClassDef

    # pylint: disable=unnecessary-lambda
    special_attributes = lazy_descriptor(lambda: objectmodel.InstanceModel())

    def __init__(self, proxied: nodes.ClassDef | None) -> None:
        super().__init__(proxied)

    infer_binary_op: ClassVar[InferBinaryOp[Instance]]

    def __repr__(self) -> str:
        return "<Instance of {}.{} at 0x{}>".format(
            self._proxied.root().name, self._proxied.name, id(self)
        )

    def __str__(self) -> str:
        return f"Instance of {self._proxied.root().name}.{self._proxied.name}"

    def callable(self) -> bool:
        try:
            self._proxied.getattr("__call__", class_context=False)
            return True
        except AttributeInferenceError:
            return False

    def pytype(self) -> str:
        return self._proxied.qname()

    def display_type(self) -> str:
        return "Instance of"

    def bool_value(self, context: InferenceContext | None = None):
        """Infer the truth value for an Instance.

        The truth value of an instance is determined by these conditions:

           * if it implements __bool__ on Python 3 or __nonzero__
             on Python 2, then its bool value will be determined by
             calling this special method and checking its result.
           * when this method is not defined, __len__() is called, if it
             is defined, and the object is considered true if its result is
             nonzero. If a class defines neither __len__() nor __bool__(),
             all its instances are considered true.
        """
        context = context or InferenceContext()
        context.boundnode = self

        try:
            result = _infer_method_result_truth(self, BOOL_SPECIAL_METHOD, context)
        except (InferenceError, AttributeInferenceError):
            # Fallback to __len__.
            try:
                result = _infer_method_result_truth(self, "__len__", context)
            except (AttributeInferenceError, InferenceError):
                return True
        return result

    def getitem(self, index, context: InferenceContext | None = None):
        new_context = bind_context_to_node(context, self)
        if not context:
            context = new_context
        method = next(self.igetattr("__getitem__", context=context), None)
        # Create a new CallContext for providing index as an argument.
        new_context.callcontext = CallContext(args=[index], callee=method)
        if not isinstance(method, BoundMethod):
            raise InferenceError(
                "Could not find __getitem__ for {node!r}.", node=self, context=context
            )
        if len(method.args.arguments) != 2:  # (self, index)
            raise AstroidTypeError(
                "__getitem__ for {node!r} does not have correct signature",
                node=self,
                context=context,
            )
        return next(method.infer_call_result(self, new_context), None)


class UnboundMethod(Proxy):
    """A special node representing a method not bound to an instance."""

    # pylint: disable=unnecessary-lambda
    special_attributes = lazy_descriptor(lambda: objectmodel.UnboundMethodModel())

    def __repr__(self) -> str:
        frame = self._proxied.parent.frame(future=True)
        return "<{} {} of {} at 0x{}".format(
            self.__class__.__name__, self._proxied.name, frame.qname(), id(self)
        )

    def implicit_parameters(self) -> Literal[0]:
        return 0

    def is_bound(self) -> Literal[False]:
        return False

    def getattr(self, name, context: InferenceContext | None = None):
        if name in self.special_attributes:
            return [self.special_attributes.lookup(name)]
        return self._proxied.getattr(name, context)

    def igetattr(self, name, context: InferenceContext | None = None):
        if name in self.special_attributes:
            return iter((self.special_attributes.lookup(name),))
        return self._proxied.igetattr(name, context)

    def infer_call_result(self, caller, context):
        """
        The boundnode of the regular context with a function called
        on ``object.__new__`` will be of type ``object``,
        which is incorrect for the argument in general.
        If no context is given the ``object.__new__`` call argument will
        be correctly inferred except when inside a call that requires
        the additional context (such as a classmethod) of the boundnode
        to determine which class the method was called from
        """

        # If we're unbound method __new__ of a builtin, the result is an
        # instance of the class given as first argument.
        if self._proxied.name == "__new__":
            qname = self._proxied.parent.frame(future=True).qname()
            # Avoid checking builtins.type: _infer_type_new_call() does more validation
            if qname.startswith("builtins.") and qname != "builtins.type":
                return self._infer_builtin_new(caller, context)
        return self._proxied.infer_call_result(caller, context)

    def _infer_builtin_new(
        self,
        caller: nodes.Call,
        context: InferenceContext,
    ) -> collections.abc.Generator[
        nodes.Const | Instance | UninferableBase, None, None
    ]:
        if not caller.args:
            return
        # Attempt to create a constant
        if len(caller.args) > 1:
            value = None
            if isinstance(caller.args[1], nodes.Const):
                value = caller.args[1].value
            else:
                inferred_arg = next(caller.args[1].infer(), None)
                if isinstance(inferred_arg, nodes.Const):
                    value = inferred_arg.value
            if value is not None:
                yield nodes.const_factory(value)
                return

        node_context = context.extra_context.get(caller.args[0])
        for inferred in caller.args[0].infer(context=node_context):
            if isinstance(inferred, UninferableBase):
                yield inferred
            if isinstance(inferred, nodes.ClassDef):
                yield Instance(inferred)
            raise InferenceError

    def bool_value(self, context: InferenceContext | None = None) -> Literal[True]:
        return True


class BoundMethod(UnboundMethod):
    """A special node representing a method bound to an instance."""

    # pylint: disable=unnecessary-lambda
    special_attributes = lazy_descriptor(lambda: objectmodel.BoundMethodModel())

    def __init__(self, proxy, bound):
        super().__init__(proxy)
        self.bound = bound

    def implicit_parameters(self) -> Literal[0, 1]:
        if self.name == "__new__":
            # __new__ acts as a classmethod but the class argument is not implicit.
            return 0
        return 1

    def is_bound(self) -> Literal[True]:
        return True

    def _infer_type_new_call(self, caller, context):  # noqa: C901
        """Try to infer what type.__new__(mcs, name, bases, attrs) returns.

        In order for such call to be valid, the metaclass needs to be
        a subtype of ``type``, the name needs to be a string, the bases
        needs to be a tuple of classes
        """
        # pylint: disable=import-outside-toplevel; circular import
        from astroid.nodes import Pass

        # Verify the metaclass
        try:
            mcs = next(caller.args[0].infer(context=context))
        except StopIteration as e:
            raise InferenceError(context=context) from e
        if mcs.__class__.__name__ != "ClassDef":
            # Not a valid first argument.
            return None
        if not mcs.is_subtype_of("builtins.type"):
            # Not a valid metaclass.
            return None

        # Verify the name
        try:
            name = next(caller.args[1].infer(context=context))
        except StopIteration as e:
            raise InferenceError(context=context) from e
        if name.__class__.__name__ != "Const":
            # Not a valid name, needs to be a const.
            return None
        if not isinstance(name.value, str):
            # Needs to be a string.
            return None

        # Verify the bases
        try:
            bases = next(caller.args[2].infer(context=context))
        except StopIteration as e:
            raise InferenceError(context=context) from e
        if bases.__class__.__name__ != "Tuple":
            # Needs to be a tuple.
            return None
        try:
            inferred_bases = [next(elt.infer(context=context)) for elt in bases.elts]
        except StopIteration as e:
            raise InferenceError(context=context) from e
        if any(base.__class__.__name__ != "ClassDef" for base in inferred_bases):
            # All the bases needs to be Classes
            return None

        # Verify the attributes.
        try:
            attrs = next(caller.args[3].infer(context=context))
        except StopIteration as e:
            raise InferenceError(context=context) from e
        if attrs.__class__.__name__ != "Dict":
            # Needs to be a dictionary.
            return None
        cls_locals = collections.defaultdict(list)
        for key, value in attrs.items:
            try:
                key = next(key.infer(context=context))
            except StopIteration as e:
                raise InferenceError(context=context) from e
            try:
                value = next(value.infer(context=context))
            except StopIteration as e:
                raise InferenceError(context=context) from e
            # Ignore non string keys
            if key.__class__.__name__ == "Const" and isinstance(key.value, str):
                cls_locals[key.value].append(value)

        # Build the class from now.
        cls = mcs.__class__(
            name=name.value,
            lineno=caller.lineno,
            col_offset=caller.col_offset,
            parent=caller,
        )
        empty = Pass()
        cls.postinit(
            bases=bases.elts,
            body=[empty],
            decorators=[],
            newstyle=True,
            metaclass=mcs,
            keywords=[],
        )
        cls.locals = cls_locals
        return cls

    def infer_call_result(self, caller, context: InferenceContext | None = None):
        context = bind_context_to_node(context, self.bound)
        if (
            self.bound.__class__.__name__ == "ClassDef"
            and self.bound.name == "type"
            and self.name == "__new__"
            and len(caller.args) == 4
        ):
            # Check if we have a ``type.__new__(mcs, name, bases, attrs)`` call.
            new_cls = self._infer_type_new_call(caller, context)
            if new_cls:
                return iter((new_cls,))

        return super().infer_call_result(caller, context)

    def bool_value(self, context: InferenceContext | None = None) -> Literal[True]:
        return True


class Generator(BaseInstance):
    """A special node representing a generator.

    Proxied class is set once for all in raw_building.
    """

    _proxied: nodes.ClassDef

    special_attributes = lazy_descriptor(objectmodel.GeneratorModel)

    def __init__(
        self, parent=None, generator_initial_context: InferenceContext | None = None
    ):
        super().__init__()
        self.parent = parent
        self._call_context = copy_context(generator_initial_context)

    @decorators.cached
    def infer_yield_types(self):
        yield from self.parent.infer_yield_result(self._call_context)

    def callable(self) -> Literal[False]:
        return False

    def pytype(self) -> Literal["builtins.generator"]:
        return "builtins.generator"

    def display_type(self) -> str:
        return "Generator"

    def bool_value(self, context: InferenceContext | None = None) -> Literal[True]:
        return True

    def __repr__(self) -> str:
        return f"<Generator({self._proxied.name}) l.{self.lineno} at 0x{id(self)}>"

    def __str__(self) -> str:
        return f"Generator({self._proxied.name})"


class AsyncGenerator(Generator):
    """Special node representing an async generator."""

    def pytype(self) -> Literal["builtins.async_generator"]:
        return "builtins.async_generator"

    def display_type(self) -> str:
        return "AsyncGenerator"

    def __repr__(self) -> str:
        return f"<AsyncGenerator({self._proxied.name}) l.{self.lineno} at 0x{id(self)}>"

    def __str__(self) -> str:
        return f"AsyncGenerator({self._proxied.name})"


class UnionType(BaseInstance):
    """Special node representing new style typing unions.

    Proxied class is set once for all in raw_building.
    """

    _proxied: nodes.ClassDef

    def __init__(
        self,
        left: UnionType | nodes.ClassDef | nodes.Const,
        right: UnionType | nodes.ClassDef | nodes.Const,
        parent: nodes.NodeNG | None = None,
    ) -> None:
        super().__init__()
        self.parent = parent
        self.left = left
        self.right = right

    def callable(self) -> Literal[False]:
        return False

    def bool_value(self, context: InferenceContext | None = None) -> Literal[True]:
        return True

    def pytype(self) -> Literal["types.UnionType"]:
        return "types.UnionType"

    def display_type(self) -> str:
        return "UnionType"

    def __repr__(self) -> str:
        return f"<UnionType({self._proxied.name}) l.{self.lineno} at 0x{id(self)}>"

    def __str__(self) -> str:
        return f"UnionType({self._proxied.name})"
