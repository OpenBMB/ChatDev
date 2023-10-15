# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""This module contains exceptions used in the astroid library."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from astroid import util

if TYPE_CHECKING:
    from astroid import arguments, bases, nodes, objects
    from astroid.context import InferenceContext

__all__ = (
    "AstroidBuildingError",
    "AstroidBuildingException",
    "AstroidError",
    "AstroidImportError",
    "AstroidIndexError",
    "AstroidSyntaxError",
    "AstroidTypeError",
    "AstroidValueError",
    "AttributeInferenceError",
    "BinaryOperationError",
    "DuplicateBasesError",
    "InconsistentMroError",
    "InferenceError",
    "InferenceOverwriteError",
    "MroError",
    "NameInferenceError",
    "NoDefault",
    "NotFoundError",
    "OperationError",
    "ParentMissingError",
    "ResolveError",
    "StatementMissing",
    "SuperArgumentTypeError",
    "SuperError",
    "TooManyLevelsError",
    "UnaryOperationError",
    "UnresolvableName",
    "UseInferenceDefault",
)


class AstroidError(Exception):
    """Base exception class for all astroid related exceptions.

    AstroidError and its subclasses are structured, intended to hold
    objects representing state when the exception is thrown.  Field
    values are passed to the constructor as keyword-only arguments.
    Each subclass has its own set of standard fields, but use your
    best judgment to decide whether a specific exception instance
    needs more or fewer fields for debugging.  Field values may be
    used to lazily generate the error message: self.message.format()
    will be called with the field names and values supplied as keyword
    arguments.
    """

    def __init__(self, message: str = "", **kws: Any) -> None:
        super().__init__(message)
        self.message = message
        for key, value in kws.items():
            setattr(self, key, value)

    def __str__(self) -> str:
        return self.message.format(**vars(self))


class AstroidBuildingError(AstroidError):
    """Exception class when we are unable to build an astroid representation.

    Standard attributes:
        modname: Name of the module that AST construction failed for.
        error: Exception raised during construction.
    """

    def __init__(
        self,
        message: str = "Failed to import module {modname}.",
        modname: str | None = None,
        error: Exception | None = None,
        source: str | None = None,
        path: str | None = None,
        cls: type | None = None,
        class_repr: str | None = None,
        **kws: Any,
    ) -> None:
        self.modname = modname
        self.error = error
        self.source = source
        self.path = path
        self.cls = cls
        self.class_repr = class_repr
        super().__init__(message, **kws)


class AstroidImportError(AstroidBuildingError):
    """Exception class used when a module can't be imported by astroid."""


class TooManyLevelsError(AstroidImportError):
    """Exception class which is raised when a relative import was beyond the top-level.

    Standard attributes:
        level: The level which was attempted.
        name: the name of the module on which the relative import was attempted.
    """

    def __init__(
        self,
        message: str = "Relative import with too many levels "
        "({level}) for module {name!r}",
        level: int | None = None,
        name: str | None = None,
        **kws: Any,
    ) -> None:
        self.level = level
        self.name = name
        super().__init__(message, **kws)


class AstroidSyntaxError(AstroidBuildingError):
    """Exception class used when a module can't be parsed."""

    def __init__(
        self,
        message: str,
        modname: str | None,
        error: Exception,
        path: str | None,
        source: str | None = None,
    ) -> None:
        super().__init__(message, modname, error, source, path)


class NoDefault(AstroidError):
    """Raised by function's `default_value` method when an argument has
    no default value.

    Standard attributes:
        func: Function node.
        name: Name of argument without a default.
    """

    def __init__(
        self,
        message: str = "{func!r} has no default for {name!r}.",
        func: nodes.FunctionDef | None = None,
        name: str | None = None,
        **kws: Any,
    ) -> None:
        self.func = func
        self.name = name
        super().__init__(message, **kws)


class ResolveError(AstroidError):
    """Base class of astroid resolution/inference error.

    ResolveError is not intended to be raised.

    Standard attributes:
        context: InferenceContext object.
    """

    def __init__(
        self, message: str = "", context: InferenceContext | None = None, **kws: Any
    ) -> None:
        self.context = context
        super().__init__(message, **kws)


class MroError(ResolveError):
    """Error raised when there is a problem with method resolution of a class.

    Standard attributes:
        mros: A sequence of sequences containing ClassDef nodes.
        cls: ClassDef node whose MRO resolution failed.
        context: InferenceContext object.
    """

    def __init__(
        self,
        message: str,
        mros: list[nodes.ClassDef],
        cls: nodes.ClassDef,
        context: InferenceContext | None = None,
        **kws: Any,
    ) -> None:
        self.mros = mros
        self.cls = cls
        self.context = context
        super().__init__(message, **kws)

    def __str__(self) -> str:
        mro_names = ", ".join(f"({', '.join(b.name for b in m)})" for m in self.mros)
        return self.message.format(mros=mro_names, cls=self.cls)


class DuplicateBasesError(MroError):
    """Error raised when there are duplicate bases in the same class bases."""


class InconsistentMroError(MroError):
    """Error raised when a class's MRO is inconsistent."""


class SuperError(ResolveError):
    """Error raised when there is a problem with a *super* call.

    Standard attributes:
        *super_*: The Super instance that raised the exception.
        context: InferenceContext object.
    """

    def __init__(self, message: str, super_: objects.Super, **kws: Any) -> None:
        self.super_ = super_
        super().__init__(message, **kws)

    def __str__(self) -> str:
        return self.message.format(**vars(self.super_))


class InferenceError(ResolveError):  # pylint: disable=too-many-instance-attributes
    """Raised when we are unable to infer a node.

    Standard attributes:
        node: The node inference was called on.
        context: InferenceContext object.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        message: str = "Inference failed for {node!r}.",
        node: nodes.NodeNG | bases.Instance | None = None,
        context: InferenceContext | None = None,
        target: nodes.NodeNG | bases.Instance | None = None,
        targets: nodes.Tuple | None = None,
        attribute: str | None = None,
        unknown: nodes.NodeNG | bases.Instance | None = None,
        assign_path: list[int] | None = None,
        caller: nodes.Call | None = None,
        stmts: Sequence[nodes.NodeNG | bases.Instance] | None = None,
        frame: nodes.LocalsDictNodeNG | None = None,
        call_site: arguments.CallSite | None = None,
        func: nodes.FunctionDef | None = None,
        arg: str | None = None,
        positional_arguments: list | None = None,
        unpacked_args: list | None = None,
        keyword_arguments: dict | None = None,
        unpacked_kwargs: dict | None = None,
        **kws: Any,
    ) -> None:
        self.node = node
        self.context = context
        self.target = target
        self.targets = targets
        self.attribute = attribute
        self.unknown = unknown
        self.assign_path = assign_path
        self.caller = caller
        self.stmts = stmts
        self.frame = frame
        self.call_site = call_site
        self.func = func
        self.arg = arg
        self.positional_arguments = positional_arguments
        self.unpacked_args = unpacked_args
        self.keyword_arguments = keyword_arguments
        self.unpacked_kwargs = unpacked_kwargs
        super().__init__(message, **kws)


# Why does this inherit from InferenceError rather than ResolveError?
# Changing it causes some inference tests to fail.
class NameInferenceError(InferenceError):
    """Raised when a name lookup fails, corresponds to NameError.

    Standard attributes:
        name: The name for which lookup failed, as a string.
        scope: The node representing the scope in which the lookup occurred.
        context: InferenceContext object.
    """

    def __init__(
        self,
        message: str = "{name!r} not found in {scope!r}.",
        name: str | None = None,
        scope: nodes.LocalsDictNodeNG | None = None,
        context: InferenceContext | None = None,
        **kws: Any,
    ) -> None:
        self.name = name
        self.scope = scope
        self.context = context
        super().__init__(message, **kws)


class AttributeInferenceError(ResolveError):
    """Raised when an attribute lookup fails, corresponds to AttributeError.

    Standard attributes:
        target: The node for which lookup failed.
        attribute: The attribute for which lookup failed, as a string.
        context: InferenceContext object.
    """

    def __init__(
        self,
        message: str = "{attribute!r} not found on {target!r}.",
        attribute: str = "",
        target: nodes.NodeNG | bases.Instance | None = None,
        context: InferenceContext | None = None,
        mros: list[nodes.ClassDef] | None = None,
        super_: nodes.ClassDef | None = None,
        cls: nodes.ClassDef | None = None,
        **kws: Any,
    ) -> None:
        self.attribute = attribute
        self.target = target
        self.context = context
        self.mros = mros
        self.super_ = super_
        self.cls = cls
        super().__init__(message, **kws)


class UseInferenceDefault(Exception):
    """Exception to be raised in custom inference function to indicate that it
    should go back to the default behaviour.
    """


class _NonDeducibleTypeHierarchy(Exception):
    """Raised when is_subtype / is_supertype can't deduce the relation between two
    types.
    """


class AstroidIndexError(AstroidError):
    """Raised when an Indexable / Mapping does not have an index / key."""

    def __init__(
        self,
        message: str = "",
        node: nodes.NodeNG | bases.Instance | None = None,
        index: nodes.Subscript | None = None,
        context: InferenceContext | None = None,
        **kws: Any,
    ) -> None:
        self.node = node
        self.index = index
        self.context = context
        super().__init__(message, **kws)


class AstroidTypeError(AstroidError):
    """Raised when a TypeError would be expected in Python code."""

    def __init__(
        self,
        message: str = "",
        node: nodes.NodeNG | bases.Instance | None = None,
        index: nodes.Subscript | None = None,
        context: InferenceContext | None = None,
        **kws: Any,
    ) -> None:
        self.node = node
        self.index = index
        self.context = context
        super().__init__(message, **kws)


class AstroidValueError(AstroidError):
    """Raised when a ValueError would be expected in Python code."""


class InferenceOverwriteError(AstroidError):
    """Raised when an inference tip is overwritten.

    Currently only used for debugging.
    """


class ParentMissingError(AstroidError):
    """Raised when a node which is expected to have a parent attribute is missing one.

    Standard attributes:
        target: The node for which the parent lookup failed.
    """

    def __init__(self, target: nodes.NodeNG) -> None:
        self.target = target
        super().__init__(message=f"Parent not found on {target!r}.")


class StatementMissing(ParentMissingError):
    """Raised when a call to node.statement() does not return a node.

    This is because a node in the chain does not have a parent attribute
    and therefore does not return a node for statement().

    Standard attributes:
        target: The node for which the parent lookup failed.
    """

    def __init__(self, target: nodes.NodeNG) -> None:
        super(ParentMissingError, self).__init__(
            message=f"Statement not found on {target!r}"
        )


# Backwards-compatibility aliases
OperationError = util.BadOperationMessage
UnaryOperationError = util.BadUnaryOperationMessage
BinaryOperationError = util.BadBinaryOperationMessage

SuperArgumentTypeError = SuperError
UnresolvableName = NameInferenceError
NotFoundError = AttributeInferenceError
AstroidBuildingException = AstroidBuildingError
