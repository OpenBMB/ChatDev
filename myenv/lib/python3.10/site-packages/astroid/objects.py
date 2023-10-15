# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""
Inference objects are a way to represent composite AST nodes,
which are used only as inference results, so they can't be found in the
original AST tree. For instance, inferring the following frozenset use,
leads to an inferred FrozenSet:

    Call(func=Name('frozenset'), args=Tuple(...))
"""

from __future__ import annotations

import sys
from collections.abc import Generator
from typing import Any, TypeVar

from astroid import bases, decorators, util
from astroid.context import InferenceContext
from astroid.exceptions import (
    AttributeInferenceError,
    InferenceError,
    MroError,
    SuperError,
)
from astroid.manager import AstroidManager
from astroid.nodes import node_classes, scoped_nodes

objectmodel = util.lazy_import("interpreter.objectmodel")

if sys.version_info >= (3, 8):
    from functools import cached_property
    from typing import Literal
else:
    from typing_extensions import Literal

    from astroid.decorators import cachedproperty as cached_property

_T = TypeVar("_T")


class FrozenSet(node_classes.BaseContainer):
    """Class representing a FrozenSet composite node."""

    def pytype(self) -> Literal["builtins.frozenset"]:
        return "builtins.frozenset"

    def _infer(self, context: InferenceContext | None = None, **kwargs: Any):
        yield self

    @cached_property
    def _proxied(self):  # pylint: disable=method-hidden
        ast_builtins = AstroidManager().builtins_module
        return ast_builtins.getattr("frozenset")[0]


class Super(node_classes.NodeNG):
    """Proxy class over a super call.

    This class offers almost the same behaviour as Python's super,
    which is MRO lookups for retrieving attributes from the parents.

    The *mro_pointer* is the place in the MRO from where we should
    start looking, not counting it. *mro_type* is the object which
    provides the MRO, it can be both a type or an instance.
    *self_class* is the class where the super call is, while
    *scope* is the function where the super call is.
    """

    # pylint: disable=unnecessary-lambda
    special_attributes = util.lazy_descriptor(lambda: objectmodel.SuperModel())

    def __init__(self, mro_pointer, mro_type, self_class, scope):
        self.type = mro_type
        self.mro_pointer = mro_pointer
        self._class_based = False
        self._self_class = self_class
        self._scope = scope
        super().__init__()

    def _infer(self, context: InferenceContext | None = None, **kwargs: Any):
        yield self

    def super_mro(self):
        """Get the MRO which will be used to lookup attributes in this super."""
        if not isinstance(self.mro_pointer, scoped_nodes.ClassDef):
            raise SuperError(
                "The first argument to super must be a subtype of "
                "type, not {mro_pointer}.",
                super_=self,
            )

        if isinstance(self.type, scoped_nodes.ClassDef):
            # `super(type, type)`, most likely in a class method.
            self._class_based = True
            mro_type = self.type
        else:
            mro_type = getattr(self.type, "_proxied", None)
            if not isinstance(mro_type, (bases.Instance, scoped_nodes.ClassDef)):
                raise SuperError(
                    "The second argument to super must be an "
                    "instance or subtype of type, not {type}.",
                    super_=self,
                )

        if not mro_type.newstyle:
            raise SuperError("Unable to call super on old-style classes.", super_=self)

        mro = mro_type.mro()
        if self.mro_pointer not in mro:
            raise SuperError(
                "The second argument to super must be an "
                "instance or subtype of type, not {type}.",
                super_=self,
            )

        index = mro.index(self.mro_pointer)
        return mro[index + 1 :]

    @cached_property
    def _proxied(self):
        ast_builtins = AstroidManager().builtins_module
        return ast_builtins.getattr("super")[0]

    def pytype(self) -> Literal["builtins.super"]:
        return "builtins.super"

    def display_type(self) -> str:
        return "Super of"

    @property
    def name(self):
        """Get the name of the MRO pointer."""
        return self.mro_pointer.name

    def qname(self) -> Literal["super"]:
        return "super"

    def igetattr(  # noqa: C901
        self, name: str, context: InferenceContext | None = None
    ):
        """Retrieve the inferred values of the given attribute name."""
        # '__class__' is a special attribute that should be taken directly
        # from the special attributes dict
        if name == "__class__":
            yield self.special_attributes.lookup(name)
            return

        try:
            mro = self.super_mro()
        # Don't let invalid MROs or invalid super calls
        # leak out as is from this function.
        except SuperError as exc:
            raise AttributeInferenceError(
                (
                    "Lookup for {name} on {target!r} because super call {super!r} "
                    "is invalid."
                ),
                target=self,
                attribute=name,
                context=context,
                super_=exc.super_,
            ) from exc
        except MroError as exc:
            raise AttributeInferenceError(
                (
                    "Lookup for {name} on {target!r} failed because {cls!r} has an "
                    "invalid MRO."
                ),
                target=self,
                attribute=name,
                context=context,
                mros=exc.mros,
                cls=exc.cls,
            ) from exc
        found = False
        for cls in mro:
            if name not in cls.locals:
                continue

            found = True
            for inferred in bases._infer_stmts([cls[name]], context, frame=self):
                if not isinstance(inferred, scoped_nodes.FunctionDef):
                    yield inferred
                    continue

                # We can obtain different descriptors from a super depending
                # on what we are accessing and where the super call is.
                if inferred.type == "classmethod":
                    yield bases.BoundMethod(inferred, cls)
                elif self._scope.type == "classmethod" and inferred.type == "method":
                    yield inferred
                elif self._class_based or inferred.type == "staticmethod":
                    yield inferred
                elif isinstance(inferred, Property):
                    function = inferred.function
                    try:
                        yield from function.infer_call_result(
                            caller=self, context=context
                        )
                    except InferenceError:
                        yield util.Uninferable
                elif bases._is_property(inferred):
                    # TODO: support other descriptors as well.
                    try:
                        yield from inferred.infer_call_result(self, context)
                    except InferenceError:
                        yield util.Uninferable
                else:
                    yield bases.BoundMethod(inferred, cls)

        # Only if we haven't found any explicit overwrites for the
        # attribute we look it up in the special attributes
        if not found and name in self.special_attributes:
            yield self.special_attributes.lookup(name)
            return

        if not found:
            raise AttributeInferenceError(target=self, attribute=name, context=context)

    def getattr(self, name, context: InferenceContext | None = None):
        return list(self.igetattr(name, context=context))


class ExceptionInstance(bases.Instance):
    """Class for instances of exceptions.

    It has special treatment for some of the exceptions's attributes,
    which are transformed at runtime into certain concrete objects, such as
    the case of .args.
    """

    @cached_property
    def special_attributes(self):
        qname = self.qname()
        instance = objectmodel.BUILTIN_EXCEPTIONS.get(
            qname, objectmodel.ExceptionInstanceModel
        )
        return instance()(self)


class DictInstance(bases.Instance):
    """Special kind of instances for dictionaries.

    This instance knows the underlying object model of the dictionaries, which means
    that methods such as .values or .items can be properly inferred.
    """

    # pylint: disable=unnecessary-lambda
    special_attributes = util.lazy_descriptor(lambda: objectmodel.DictModel())


# Custom objects tailored for dictionaries, which are used to
# disambiguate between the types of Python 2 dict's method returns
# and Python 3 (where they return set like objects).
class DictItems(bases.Proxy):
    __str__ = node_classes.NodeNG.__str__
    __repr__ = node_classes.NodeNG.__repr__


class DictKeys(bases.Proxy):
    __str__ = node_classes.NodeNG.__str__
    __repr__ = node_classes.NodeNG.__repr__


class DictValues(bases.Proxy):
    __str__ = node_classes.NodeNG.__str__
    __repr__ = node_classes.NodeNG.__repr__


class PartialFunction(scoped_nodes.FunctionDef):
    """A class representing partial function obtained via functools.partial."""

    @decorators.deprecate_arguments(doc="Use the postinit arg 'doc_node' instead")
    def __init__(
        self, call, name=None, doc=None, lineno=None, col_offset=None, parent=None
    ):
        # TODO: Pass end_lineno and end_col_offset as well
        super().__init__(name, lineno=lineno, col_offset=col_offset, parent=None)
        # Assigned directly to prevent triggering the DeprecationWarning.
        self._doc = doc
        # A typical FunctionDef automatically adds its name to the parent scope,
        # but a partial should not, so defer setting parent until after init
        self.parent = parent
        self.filled_args = call.positional_arguments[1:]
        self.filled_keywords = call.keyword_arguments

        wrapped_function = call.positional_arguments[0]
        inferred_wrapped_function = next(wrapped_function.infer())
        if isinstance(inferred_wrapped_function, PartialFunction):
            self.filled_args = inferred_wrapped_function.filled_args + self.filled_args
            self.filled_keywords = {
                **inferred_wrapped_function.filled_keywords,
                **self.filled_keywords,
            }

        self.filled_positionals = len(self.filled_args)

    def infer_call_result(self, caller=None, context: InferenceContext | None = None):
        if context:
            current_passed_keywords = {
                keyword for (keyword, _) in context.callcontext.keywords
            }
            for keyword, value in self.filled_keywords.items():
                if keyword not in current_passed_keywords:
                    context.callcontext.keywords.append((keyword, value))

            call_context_args = context.callcontext.args or []
            context.callcontext.args = self.filled_args + call_context_args

        return super().infer_call_result(caller=caller, context=context)

    def qname(self) -> str:
        return self.__class__.__name__


# TODO: Hack to solve the circular import problem between node_classes and objects
# This is not needed in 2.0, which has a cleaner design overall
node_classes.Dict.__bases__ = (node_classes.NodeNG, DictInstance)


class Property(scoped_nodes.FunctionDef):
    """Class representing a Python property."""

    @decorators.deprecate_arguments(doc="Use the postinit arg 'doc_node' instead")
    def __init__(
        self, function, name=None, doc=None, lineno=None, col_offset=None, parent=None
    ):
        self.function = function
        super().__init__(name, lineno=lineno, col_offset=col_offset, parent=parent)
        # Assigned directly to prevent triggering the DeprecationWarning.
        self._doc = doc

    # pylint: disable=unnecessary-lambda
    special_attributes = util.lazy_descriptor(lambda: objectmodel.PropertyModel())
    type = "property"

    def pytype(self) -> Literal["builtins.property"]:
        return "builtins.property"

    def infer_call_result(self, caller=None, context: InferenceContext | None = None):
        raise InferenceError("Properties are not callable")

    def _infer(
        self: _T, context: InferenceContext | None = None, **kwargs: Any
    ) -> Generator[_T, None, None]:
        yield self
