# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Classes checker for Python code."""

from __future__ import annotations

import collections
import sys
from collections import defaultdict
from collections.abc import Callable, Sequence
from itertools import chain, zip_longest
from re import Pattern
from typing import TYPE_CHECKING, Any, Union

import astroid
from astroid import bases, nodes, util
from astroid.nodes import LocalsDictNodeNG
from astroid.typing import SuccessfulInferenceResult

from pylint.checkers import BaseChecker, utils
from pylint.checkers.utils import (
    PYMETHODS,
    class_is_abstract,
    decorated_with,
    decorated_with_property,
    get_outer_class,
    has_known_bases,
    is_attr_private,
    is_attr_protected,
    is_builtin_object,
    is_comprehension,
    is_iterable,
    is_property_setter,
    is_property_setter_or_deleter,
    node_frame_class,
    only_required_for_messages,
    safe_infer,
    unimplemented_abstract_methods,
    uninferable_final_decorators,
)
from pylint.interfaces import HIGH, INFERENCE
from pylint.typing import MessageDefinitionTuple

if TYPE_CHECKING:
    from pylint.lint.pylinter import PyLinter


if sys.version_info >= (3, 8):
    from functools import cached_property
else:
    from astroid.decorators import cachedproperty as cached_property

_AccessNodes = Union[nodes.Attribute, nodes.AssignAttr]

INVALID_BASE_CLASSES = {"bool", "range", "slice", "memoryview"}
BUILTIN_DECORATORS = {"builtins.property", "builtins.classmethod"}
ASTROID_TYPE_COMPARATORS = {
    nodes.Const: lambda a, b: a.value == b.value,
    nodes.ClassDef: lambda a, b: a.qname == b.qname,
    nodes.Tuple: lambda a, b: a.elts == b.elts,
    nodes.List: lambda a, b: a.elts == b.elts,
    nodes.Dict: lambda a, b: a.items == b.items,
    nodes.Name: lambda a, b: set(a.infer()) == set(b.infer()),
}

# Dealing with useless override detection, with regard
# to parameters vs arguments

_CallSignature = collections.namedtuple(
    "_CallSignature", "args kws starred_args starred_kws"
)
_ParameterSignature = collections.namedtuple(
    "_ParameterSignature", "args kwonlyargs varargs kwargs"
)


def _signature_from_call(call: nodes.Call) -> _CallSignature:
    kws = {}
    args = []
    starred_kws = []
    starred_args = []
    for keyword in call.keywords or []:
        arg, value = keyword.arg, keyword.value
        if arg is None and isinstance(value, nodes.Name):
            # Starred node, and we are interested only in names,
            # otherwise some transformation might occur for the parameter.
            starred_kws.append(value.name)
        elif isinstance(value, nodes.Name):
            kws[arg] = value.name
        else:
            kws[arg] = None

    for arg in call.args:
        if isinstance(arg, nodes.Starred) and isinstance(arg.value, nodes.Name):
            # Positional variadic and a name, otherwise some transformation
            # might have occurred.
            starred_args.append(arg.value.name)
        elif isinstance(arg, nodes.Name):
            args.append(arg.name)
        else:
            args.append(None)

    return _CallSignature(args, kws, starred_args, starred_kws)


def _signature_from_arguments(arguments: nodes.Arguments) -> _ParameterSignature:
    kwarg = arguments.kwarg
    vararg = arguments.vararg
    args = [
        arg.name
        for arg in chain(arguments.posonlyargs, arguments.args)
        if arg.name != "self"
    ]
    kwonlyargs = [arg.name for arg in arguments.kwonlyargs]
    return _ParameterSignature(args, kwonlyargs, vararg, kwarg)


def _definition_equivalent_to_call(
    definition: _ParameterSignature, call: _CallSignature
) -> bool:
    """Check if a definition signature is equivalent to a call."""
    if definition.kwargs:
        if definition.kwargs not in call.starred_kws:
            return False
    elif call.starred_kws:
        return False
    if definition.varargs:
        if definition.varargs not in call.starred_args:
            return False
    elif call.starred_args:
        return False
    if any(kw not in call.kws for kw in definition.kwonlyargs):
        return False
    if definition.args != call.args:
        return False

    # No extra kwargs in call.
    return all(kw in call.args or kw in definition.kwonlyargs for kw in call.kws)


def _is_trivial_super_delegation(function: nodes.FunctionDef) -> bool:
    """Check whether a function definition is a method consisting only of a
    call to the same function on the superclass.
    """
    if (
        not function.is_method()
        # Adding decorators to a function changes behavior and
        # constitutes a non-trivial change.
        or function.decorators
    ):
        return False

    body = function.body
    if len(body) != 1:
        # Multiple statements, which means this overridden method
        # could do multiple things we are not aware of.
        return False

    statement = body[0]
    if not isinstance(statement, (nodes.Expr, nodes.Return)):
        # Doing something else than what we are interested in.
        return False

    call = statement.value
    if (
        not isinstance(call, nodes.Call)
        # Not a super() attribute access.
        or not isinstance(call.func, nodes.Attribute)
    ):
        return False

    # Anything other than a super call is non-trivial.
    super_call = safe_infer(call.func.expr)
    if not isinstance(super_call, astroid.objects.Super):
        return False

    # The name should be the same.
    if call.func.attrname != function.name:
        return False

    # Should be a super call with the MRO pointer being the
    # current class and the type being the current instance.
    current_scope = function.parent.scope()
    if (
        super_call.mro_pointer != current_scope
        or not isinstance(super_call.type, astroid.Instance)
        or super_call.type.name != current_scope.name
    ):
        return False

    return True


# Deal with parameters overriding in two methods.


def _positional_parameters(method: nodes.FunctionDef) -> list[nodes.AssignName]:
    positional = method.args.args
    if method.is_bound() and method.type in {"classmethod", "method"}:
        positional = positional[1:]
    return positional  # type: ignore[no-any-return]


class _DefaultMissing:
    """Sentinel value for missing arg default, use _DEFAULT_MISSING."""


_DEFAULT_MISSING = _DefaultMissing()


def _has_different_parameters_default_value(
    original: nodes.Arguments, overridden: nodes.Arguments
) -> bool:
    """Check if original and overridden methods arguments have different default values.

    Return True if one of the overridden arguments has a default
    value different from the default value of the original argument
    If one of the method doesn't have argument (.args is None)
    return False
    """
    if original.args is None or overridden.args is None:
        return False

    for param in chain(original.args, original.kwonlyargs):
        try:
            original_default = original.default_value(param.name)
        except astroid.exceptions.NoDefault:
            original_default = _DEFAULT_MISSING
        try:
            overridden_default = overridden.default_value(param.name)
            if original_default is _DEFAULT_MISSING:
                # Only the original has a default.
                return True
        except astroid.exceptions.NoDefault:
            if original_default is _DEFAULT_MISSING:
                # Both have a default, no difference
                continue
            # Only the override has a default.
            return True

        original_type = type(original_default)
        if not isinstance(overridden_default, original_type):
            # Two args with same name but different types
            return True
        is_same_fn: Callable[[Any, Any], bool] | None = ASTROID_TYPE_COMPARATORS.get(
            original_type
        )
        if is_same_fn is None:
            # If the default value comparison is unhandled, assume the value is different
            return True
        if not is_same_fn(original_default, overridden_default):
            # Two args with same type but different values
            return True
    return False


def _has_different_parameters(
    original: list[nodes.AssignName],
    overridden: list[nodes.AssignName],
    dummy_parameter_regex: Pattern[str],
) -> list[str]:
    result: list[str] = []
    zipped = zip_longest(original, overridden)
    for original_param, overridden_param in zipped:
        if not overridden_param:
            return ["Number of parameters "]

        if not original_param:
            try:
                overridden_param.parent.default_value(overridden_param.name)
                continue
            except astroid.NoDefault:
                return ["Number of parameters "]

        # check for the arguments' name
        names = [param.name for param in (original_param, overridden_param)]
        if any(dummy_parameter_regex.match(name) for name in names):
            continue
        if original_param.name != overridden_param.name:
            result.append(
                f"Parameter '{original_param.name}' has been renamed "
                f"to '{overridden_param.name}' in"
            )

    return result


def _has_different_keyword_only_parameters(
    original: list[nodes.AssignName],
    overridden: list[nodes.AssignName],
) -> list[str]:
    """Determine if the two methods have different keyword only parameters."""
    original_names = [i.name for i in original]
    overridden_names = [i.name for i in overridden]

    if any(name not in overridden_names for name in original_names):
        return ["Number of parameters "]

    for name in overridden_names:
        if name in original_names:
            continue

        try:
            overridden[0].parent.default_value(name)
        except astroid.NoDefault:
            return ["Number of parameters "]

    return []


def _different_parameters(
    original: nodes.FunctionDef,
    overridden: nodes.FunctionDef,
    dummy_parameter_regex: Pattern[str],
) -> list[str]:
    """Determine if the two methods have different parameters.

    They are considered to have different parameters if:

       * they have different positional parameters, including different names

       * one of the methods is having variadics, while the other is not

       * they have different keyword only parameters.
    """
    output_messages = []
    original_parameters = _positional_parameters(original)
    overridden_parameters = _positional_parameters(overridden)

    # Copy kwonlyargs list so that we don't affect later function linting
    original_kwonlyargs = original.args.kwonlyargs

    # Allow positional/keyword variadic in overridden to match against any
    # positional/keyword argument in original.
    # Keep any arguments that are found separately in overridden to satisfy
    # later tests
    if overridden.args.vararg:
        overridden_names = [v.name for v in overridden_parameters]
        original_parameters = [
            v for v in original_parameters if v.name in overridden_names
        ]

    if overridden.args.kwarg:
        overridden_names = [v.name for v in overridden.args.kwonlyargs]
        original_kwonlyargs = [
            v for v in original.args.kwonlyargs if v.name in overridden_names
        ]

    different_positional = _has_different_parameters(
        original_parameters, overridden_parameters, dummy_parameter_regex
    )
    different_kwonly = _has_different_keyword_only_parameters(
        original_kwonlyargs, overridden.args.kwonlyargs
    )
    if different_kwonly and different_positional:
        if "Number " in different_positional[0] and "Number " in different_kwonly[0]:
            output_messages.append("Number of parameters ")
            output_messages += different_positional[1:]
            output_messages += different_kwonly[1:]
        else:
            output_messages += different_positional
            output_messages += different_kwonly
    else:
        if different_positional:
            output_messages += different_positional
        if different_kwonly:
            output_messages += different_kwonly

    if original.name in PYMETHODS:
        # Ignore the difference for special methods. If the parameter
        # numbers are different, then that is going to be caught by
        # unexpected-special-method-signature.
        # If the names are different, it doesn't matter, since they can't
        # be used as keyword arguments anyway.
        output_messages.clear()

    # Arguments will only violate LSP if there are variadics in the original
    # that are then removed from the overridden
    kwarg_lost = original.args.kwarg and not overridden.args.kwarg
    vararg_lost = original.args.vararg and not overridden.args.vararg

    if kwarg_lost or vararg_lost:
        output_messages += ["Variadics removed in"]

    return output_messages


def _is_invalid_base_class(cls: nodes.ClassDef) -> bool:
    return cls.name in INVALID_BASE_CLASSES and is_builtin_object(cls)


def _has_data_descriptor(cls: nodes.ClassDef, attr: str) -> bool:
    attributes = cls.getattr(attr)
    for attribute in attributes:
        try:
            for inferred in attribute.infer():
                if isinstance(inferred, astroid.Instance):
                    try:
                        inferred.getattr("__get__")
                        inferred.getattr("__set__")
                    except astroid.NotFoundError:
                        continue
                    else:
                        return True
        except astroid.InferenceError:
            # Can't infer, avoid emitting a false positive in this case.
            return True
    return False


def _called_in_methods(
    func: LocalsDictNodeNG,
    klass: nodes.ClassDef,
    methods: Sequence[str],
) -> bool:
    """Check if the func was called in any of the given methods,
    belonging to the *klass*.

    Returns True if so, False otherwise.
    """
    if not isinstance(func, nodes.FunctionDef):
        return False
    for method in methods:
        try:
            inferred = klass.getattr(method)
        except astroid.NotFoundError:
            continue
        for infer_method in inferred:
            for call in infer_method.nodes_of_class(nodes.Call):
                try:
                    bound = next(call.func.infer())
                except (astroid.InferenceError, StopIteration):
                    continue
                if not isinstance(bound, astroid.BoundMethod):
                    continue
                func_obj = bound._proxied
                if isinstance(func_obj, astroid.UnboundMethod):
                    func_obj = func_obj._proxied
                if func_obj.name == func.name:
                    return True
    return False


def _is_attribute_property(name: str, klass: nodes.ClassDef) -> bool:
    """Check if the given attribute *name* is a property in the given *klass*.

    It will look for `property` calls or for functions
    with the given name, decorated by `property` or `property`
    subclasses.
    Returns ``True`` if the name is a property in the given klass,
    ``False`` otherwise.
    """

    try:
        attributes = klass.getattr(name)
    except astroid.NotFoundError:
        return False
    property_name = "builtins.property"
    for attr in attributes:
        if isinstance(attr, util.UninferableBase):
            continue
        try:
            inferred = next(attr.infer())
        except astroid.InferenceError:
            continue
        if isinstance(inferred, nodes.FunctionDef) and decorated_with_property(
            inferred
        ):
            return True
        if inferred.pytype() != property_name:
            continue

        cls = node_frame_class(inferred)
        if cls == klass.declared_metaclass():
            continue
        return True
    return False


def _has_same_layout_slots(
    slots: list[nodes.Const | None], assigned_value: nodes.Name
) -> bool:
    inferred = next(assigned_value.infer())
    if isinstance(inferred, nodes.ClassDef):
        other_slots = inferred.slots()
        if all(
            first_slot and second_slot and first_slot.value == second_slot.value
            for (first_slot, second_slot) in zip_longest(slots, other_slots)
        ):
            return True
    return False


MSGS: dict[str, MessageDefinitionTuple] = {
    "F0202": (
        "Unable to check methods signature (%s / %s)",
        "method-check-failed",
        "Used when Pylint has been unable to check methods signature "
        "compatibility for an unexpected reason. Please report this kind "
        "if you don't make sense of it.",
    ),
    "E0202": (
        "An attribute defined in %s line %s hides this method",
        "method-hidden",
        "Used when a class defines a method which is hidden by an "
        "instance attribute from an ancestor class or set by some "
        "client code.",
    ),
    "E0203": (
        "Access to member %r before its definition line %s",
        "access-member-before-definition",
        "Used when an instance member is accessed before it's actually assigned.",
    ),
    "W0201": (
        "Attribute %r defined outside __init__",
        "attribute-defined-outside-init",
        "Used when an instance attribute is defined outside the __init__ method.",
    ),
    "W0212": (
        "Access to a protected member %s of a client class",  # E0214
        "protected-access",
        "Used when a protected member (i.e. class member with a name "
        "beginning with an underscore) is access outside the class or a "
        "descendant of the class where it's defined.",
    ),
    "W0213": (
        "Flag member %(overlap)s shares bit positions with %(sources)s",
        "implicit-flag-alias",
        "Used when multiple integer values declared within an enum.IntFlag "
        "class share a common bit position.",
    ),
    "E0211": (
        "Method %r has no argument",
        "no-method-argument",
        "Used when a method which should have the bound instance as "
        "first argument has no argument defined.",
    ),
    "E0213": (
        'Method %r should have "self" as first argument',
        "no-self-argument",
        'Used when a method has an attribute different the "self" as '
        "first argument. This is considered as an error since this is "
        "a so common convention that you shouldn't break it!",
    ),
    "C0202": (
        "Class method %s should have %s as first argument",
        "bad-classmethod-argument",
        "Used when a class method has a first argument named differently "
        "than the value specified in valid-classmethod-first-arg option "
        '(default to "cls"), recommended to easily differentiate them '
        "from regular instance methods.",
    ),
    "C0203": (
        "Metaclass method %s should have %s as first argument",
        "bad-mcs-method-argument",
        "Used when a metaclass method has a first argument named "
        "differently than the value specified in valid-classmethod-first"
        '-arg option (default to "cls"), recommended to easily '
        "differentiate them from regular instance methods.",
    ),
    "C0204": (
        "Metaclass class method %s should have %s as first argument",
        "bad-mcs-classmethod-argument",
        "Used when a metaclass class method has a first argument named "
        "differently than the value specified in valid-metaclass-"
        'classmethod-first-arg option (default to "mcs"), recommended to '
        "easily differentiate them from regular instance methods.",
    ),
    "W0211": (
        "Static method with %r as first argument",
        "bad-staticmethod-argument",
        'Used when a static method has "self" or a value specified in '
        "valid-classmethod-first-arg option or "
        "valid-metaclass-classmethod-first-arg option as first argument.",
    ),
    "W0221": (
        "%s %s %r method",
        "arguments-differ",
        "Used when a method has a different number of arguments than in "
        "the implemented interface or in an overridden method. Extra arguments "
        "with default values are ignored.",
    ),
    "W0222": (
        "Signature differs from %s %r method",
        "signature-differs",
        "Used when a method signature is different than in the "
        "implemented interface or in an overridden method.",
    ),
    "W0223": (
        "Method %r is abstract in class %r but is not overridden in child class %r",
        "abstract-method",
        "Used when an abstract method (i.e. raise NotImplementedError) is "
        "not overridden in concrete class.",
    ),
    "W0231": (
        "__init__ method from base class %r is not called",
        "super-init-not-called",
        "Used when an ancestor class method has an __init__ method "
        "which is not called by a derived class.",
    ),
    "W0233": (
        "__init__ method from a non direct base class %r is called",
        "non-parent-init-called",
        "Used when an __init__ method is called on a class which is not "
        "in the direct ancestors for the analysed class.",
    ),
    "W0246": (
        "Useless parent or super() delegation in method %r",
        "useless-parent-delegation",
        "Used whenever we can detect that an overridden method is useless, "
        "relying on parent or super() delegation to do the same thing as another method "
        "from the MRO.",
        {"old_names": [("W0235", "useless-super-delegation")]},
    ),
    "W0236": (
        "Method %r was expected to be %r, found it instead as %r",
        "invalid-overridden-method",
        "Used when we detect that a method was overridden in a way "
        "that does not match its base class "
        "which could result in potential bugs at runtime.",
    ),
    "W0237": (
        "%s %s %r method",
        "arguments-renamed",
        "Used when a method parameter has a different name than in "
        "the implemented interface or in an overridden method.",
    ),
    "W0238": (
        "Unused private member `%s.%s`",
        "unused-private-member",
        "Emitted when a private member of a class is defined but not used.",
    ),
    "W0239": (
        "Method %r overrides a method decorated with typing.final which is defined in class %r",
        "overridden-final-method",
        "Used when a method decorated with typing.final has been overridden.",
    ),
    "W0240": (
        "Class %r is a subclass of a class decorated with typing.final: %r",
        "subclassed-final-class",
        "Used when a class decorated with typing.final has been subclassed.",
    ),
    "W0244": (
        "Redefined slots %r in subclass",
        "redefined-slots-in-subclass",
        "Used when a slot is re-defined in a subclass.",
    ),
    "W0245": (
        "Super call without brackets",
        "super-without-brackets",
        "Used when a call to super does not have brackets and thus is not an actual "
        "call and does not work as expected.",
    ),
    "E0236": (
        "Invalid object %r in __slots__, must contain only non empty strings",
        "invalid-slots-object",
        "Used when an invalid (non-string) object occurs in __slots__.",
    ),
    "E0237": (
        "Assigning to attribute %r not defined in class slots",
        "assigning-non-slot",
        "Used when assigning to an attribute not defined in the class slots.",
    ),
    "E0238": (
        "Invalid __slots__ object",
        "invalid-slots",
        "Used when an invalid __slots__ is found in class. "
        "Only a string, an iterable or a sequence is permitted.",
    ),
    "E0239": (
        "Inheriting %r, which is not a class.",
        "inherit-non-class",
        "Used when a class inherits from something which is not a class.",
    ),
    "E0240": (
        "Inconsistent method resolution order for class %r",
        "inconsistent-mro",
        "Used when a class has an inconsistent method resolution order.",
    ),
    "E0241": (
        "Duplicate bases for class %r",
        "duplicate-bases",
        "Duplicate use of base classes in derived classes raise TypeErrors.",
    ),
    "E0242": (
        "Value %r in slots conflicts with class variable",
        "class-variable-slots-conflict",
        "Used when a value in __slots__ conflicts with a class variable, property or method.",
    ),
    "E0243": (
        "Invalid assignment to '__class__'. Should be a class definition but got a '%s'",
        "invalid-class-object",
        "Used when an invalid object is assigned to a __class__ property. "
        "Only a class is permitted.",
    ),
    "E0244": (
        'Extending inherited Enum class "%s"',
        "invalid-enum-extension",
        "Used when a class tries to extend an inherited Enum class. "
        "Doing so will raise a TypeError at runtime.",
    ),
    "R0202": (
        "Consider using a decorator instead of calling classmethod",
        "no-classmethod-decorator",
        "Used when a class method is defined without using the decorator syntax.",
    ),
    "R0203": (
        "Consider using a decorator instead of calling staticmethod",
        "no-staticmethod-decorator",
        "Used when a static method is defined without using the decorator syntax.",
    ),
    "C0205": (
        "Class __slots__ should be a non-string iterable",
        "single-string-used-for-slots",
        "Used when a class __slots__ is a simple string, rather than an iterable.",
    ),
    "R0205": (
        "Class %r inherits from object, can be safely removed from bases in python3",
        "useless-object-inheritance",
        "Used when a class inherit from object, which under python3 is implicit, "
        "hence can be safely removed from bases.",
    ),
    "R0206": (
        "Cannot have defined parameters for properties",
        "property-with-parameters",
        "Used when we detect that a property also has parameters, which are useless, "
        "given that properties cannot be called with additional arguments.",
    ),
}


def _scope_default() -> defaultdict[str, list[_AccessNodes]]:
    # It's impossible to nest defaultdicts so we must use a function
    return defaultdict(list)


class ScopeAccessMap:
    """Store the accessed variables per scope."""

    def __init__(self) -> None:
        self._scopes: defaultdict[
            nodes.ClassDef, defaultdict[str, list[_AccessNodes]]
        ] = defaultdict(_scope_default)

    def set_accessed(self, node: _AccessNodes) -> None:
        """Set the given node as accessed."""

        frame = node_frame_class(node)
        if frame is None:
            # The node does not live in a class.
            return
        self._scopes[frame][node.attrname].append(node)

    def accessed(self, scope: nodes.ClassDef) -> dict[str, list[_AccessNodes]]:
        """Get the accessed variables for the given scope."""
        return self._scopes.get(scope, {})


class ClassChecker(BaseChecker):
    """Checker for class nodes.

    Checks for :
    * methods without self as first argument
    * overridden methods signature
    * access only to existent members via self
    * attributes not defined in the __init__ method
    * unreachable code
    """

    # configuration section name
    name = "classes"
    # messages
    msgs = MSGS
    # configuration options
    options = (
        (
            "defining-attr-methods",
            {
                "default": ("__init__", "__new__", "setUp", "__post_init__"),
                "type": "csv",
                "metavar": "<method names>",
                "help": "List of method names used to declare (i.e. assign) \
instance attributes.",
            },
        ),
        (
            "valid-classmethod-first-arg",
            {
                "default": ("cls",),
                "type": "csv",
                "metavar": "<argument names>",
                "help": "List of valid names for the first argument in \
a class method.",
            },
        ),
        (
            "valid-metaclass-classmethod-first-arg",
            {
                "default": ("mcs",),
                "type": "csv",
                "metavar": "<argument names>",
                "help": "List of valid names for the first argument in \
a metaclass class method.",
            },
        ),
        (
            "exclude-protected",
            {
                "default": (
                    # namedtuple public API.
                    "_asdict",
                    "_fields",
                    "_replace",
                    "_source",
                    "_make",
                    "os._exit",
                ),
                "type": "csv",
                "metavar": "<protected access exclusions>",
                "help": (
                    "List of member names, which should be excluded "
                    "from the protected access warning."
                ),
            },
        ),
        (
            "check-protected-access-in-special-methods",
            {
                "default": False,
                "type": "yn",
                "metavar": "<y or n>",
                "help": "Warn about protected attribute access inside special methods",
            },
        ),
    )

    def __init__(self, linter: PyLinter) -> None:
        super().__init__(linter)
        self._accessed = ScopeAccessMap()
        self._first_attrs: list[str | None] = []

    def open(self) -> None:
        self._mixin_class_rgx = self.linter.config.mixin_class_rgx
        py_version = self.linter.config.py_version
        self._py38_plus = py_version >= (3, 8)

    @cached_property
    def _dummy_rgx(self) -> Pattern[str]:
        return self.linter.config.dummy_variables_rgx  # type: ignore[no-any-return]

    @only_required_for_messages(
        "abstract-method",
        "invalid-slots",
        "single-string-used-for-slots",
        "invalid-slots-object",
        "class-variable-slots-conflict",
        "inherit-non-class",
        "useless-object-inheritance",
        "inconsistent-mro",
        "duplicate-bases",
        "redefined-slots-in-subclass",
        "invalid-enum-extension",
        "subclassed-final-class",
        "implicit-flag-alias",
    )
    def visit_classdef(self, node: nodes.ClassDef) -> None:
        """Init visit variable _accessed."""
        self._check_bases_classes(node)
        self._check_slots(node)
        self._check_proper_bases(node)
        self._check_typing_final(node)
        self._check_consistent_mro(node)

    def _check_consistent_mro(self, node: nodes.ClassDef) -> None:
        """Detect that a class has a consistent mro or duplicate bases."""
        try:
            node.mro()
        except astroid.InconsistentMroError:
            self.add_message("inconsistent-mro", args=node.name, node=node)
        except astroid.DuplicateBasesError:
            self.add_message("duplicate-bases", args=node.name, node=node)

    def _check_enum_base(self, node: nodes.ClassDef, ancestor: nodes.ClassDef) -> None:
        members = ancestor.getattr("__members__")
        if members and isinstance(members[0], nodes.Dict) and members[0].items:
            self.add_message(
                "invalid-enum-extension",
                args=ancestor.name,
                node=node,
                confidence=INFERENCE,
            )

        if ancestor.is_subtype_of("enum.IntFlag"):
            # Collect integer flag assignments present on the class
            assignments = defaultdict(list)
            for assign_name in node.nodes_of_class(nodes.AssignName):
                if isinstance(assign_name.parent, nodes.Assign):
                    value = getattr(assign_name.parent.value, "value", None)
                    if isinstance(value, int):
                        assignments[value].append(assign_name)

            # For each bit position, collect all the flags that set the bit
            bit_flags = defaultdict(set)
            for flag in assignments:
                flag_bits = (i for i, c in enumerate(reversed(bin(flag))) if c == "1")
                for bit in flag_bits:
                    bit_flags[bit].add(flag)

            # Collect the minimum, unique values that each flag overlaps with
            overlaps = defaultdict(list)
            for flags in bit_flags.values():
                source, *conflicts = sorted(flags)
                for conflict in conflicts:
                    overlaps[conflict].append(source)

            # Report the overlapping values
            for overlap in overlaps:
                for assignment_node in assignments[overlap]:
                    self.add_message(
                        "implicit-flag-alias",
                        node=assignment_node,
                        args={
                            "overlap": f"<{node.name}.{assignment_node.name}: {overlap}>",
                            "sources": ", ".join(
                                f"<{node.name}.{assignments[source][0].name}: {source}> "
                                f"({overlap} & {source} = {overlap & source})"
                                for source in overlaps[overlap]
                            ),
                        },
                        confidence=INFERENCE,
                    )

    def _check_proper_bases(self, node: nodes.ClassDef) -> None:
        """Detect that a class inherits something which is not
        a class or a type.
        """
        for base in node.bases:
            ancestor = safe_infer(base)
            if not ancestor:
                continue
            if isinstance(ancestor, astroid.Instance) and ancestor.is_subtype_of(
                "builtins.type"
            ):
                continue

            if not isinstance(ancestor, nodes.ClassDef) or _is_invalid_base_class(
                ancestor
            ):
                self.add_message("inherit-non-class", args=base.as_string(), node=node)

            if isinstance(ancestor, nodes.ClassDef) and ancestor.is_subtype_of(
                "enum.Enum"
            ):
                self._check_enum_base(node, ancestor)

            if ancestor.name == object.__name__:
                self.add_message(
                    "useless-object-inheritance", args=node.name, node=node
                )

    def _check_typing_final(self, node: nodes.ClassDef) -> None:
        """Detect that a class does not subclass a class decorated with
        `typing.final`.
        """
        if not self._py38_plus:
            return
        for base in node.bases:
            ancestor = safe_infer(base)
            if not ancestor:
                continue

            if isinstance(ancestor, nodes.ClassDef) and (
                decorated_with(ancestor, ["typing.final"])
                or uninferable_final_decorators(ancestor.decorators)
            ):
                self.add_message(
                    "subclassed-final-class",
                    args=(node.name, ancestor.name),
                    node=node,
                )

    @only_required_for_messages(
        "unused-private-member",
        "attribute-defined-outside-init",
        "access-member-before-definition",
    )
    def leave_classdef(self, node: nodes.ClassDef) -> None:
        """Checker for Class nodes.

        check that instance attributes are defined in __init__ and check
        access to existent members
        """
        self._check_unused_private_functions(node)
        self._check_unused_private_variables(node)
        self._check_unused_private_attributes(node)
        self._check_attribute_defined_outside_init(node)

    def _check_unused_private_functions(self, node: nodes.ClassDef) -> None:
        for function_def in node.nodes_of_class(nodes.FunctionDef):
            if not is_attr_private(function_def.name):
                continue
            parent_scope = function_def.parent.scope()
            if isinstance(parent_scope, nodes.FunctionDef):
                # Handle nested functions
                if function_def.name in (
                    n.name for n in parent_scope.nodes_of_class(nodes.Name)
                ):
                    continue
            for child in node.nodes_of_class((nodes.Name, nodes.Attribute)):
                # Check for cases where the functions are used as a variable instead of as a
                # method call
                if isinstance(child, nodes.Name) and child.name == function_def.name:
                    break
                if isinstance(child, nodes.Attribute):
                    # Ignore recursive calls
                    if (
                        child.attrname != function_def.name
                        or child.scope() == function_def
                    ):
                        continue

                    # Check self.__attrname, cls.__attrname, node_name.__attrname
                    if isinstance(child.expr, nodes.Name) and child.expr.name in {
                        "self",
                        "cls",
                        node.name,
                    }:
                        break

                    # Check type(self).__attrname
                    if isinstance(child.expr, nodes.Call):
                        inferred = safe_infer(child.expr)
                        if (
                            isinstance(inferred, nodes.ClassDef)
                            and inferred.name == node.name
                        ):
                            break
            else:
                name_stack = []
                curr = parent_scope
                # Generate proper names for nested functions
                while curr != node:
                    name_stack.append(curr.name)
                    curr = curr.parent.scope()

                outer_level_names = f"{'.'.join(reversed(name_stack))}"
                function_repr = f"{outer_level_names}.{function_def.name}({function_def.args.as_string()})"
                self.add_message(
                    "unused-private-member",
                    node=function_def,
                    args=(node.name, function_repr.lstrip(".")),
                )

    def _check_unused_private_variables(self, node: nodes.ClassDef) -> None:
        """Check if private variables are never used within a class."""
        for assign_name in node.nodes_of_class(nodes.AssignName):
            if isinstance(assign_name.parent, nodes.Arguments):
                continue  # Ignore function arguments
            if not is_attr_private(assign_name.name):
                continue
            for child in node.nodes_of_class((nodes.Name, nodes.Attribute)):
                if isinstance(child, nodes.Name) and child.name == assign_name.name:
                    break
                if isinstance(child, nodes.Attribute):
                    if not isinstance(child.expr, nodes.Name):
                        break
                    if child.attrname == assign_name.name and child.expr.name in (
                        "self",
                        "cls",
                        node.name,
                    ):
                        break
            else:
                args = (node.name, assign_name.name)
                self.add_message("unused-private-member", node=assign_name, args=args)

    def _check_unused_private_attributes(self, node: nodes.ClassDef) -> None:
        for assign_attr in node.nodes_of_class(nodes.AssignAttr):
            if not is_attr_private(assign_attr.attrname) or not isinstance(
                assign_attr.expr, nodes.Name
            ):
                continue

            # Logic for checking false positive when using __new__,
            # Get the returned object names of the __new__ magic function
            # Then check if the attribute was consumed in other instance methods
            acceptable_obj_names: list[str] = ["self"]
            scope = assign_attr.scope()
            if isinstance(scope, nodes.FunctionDef) and scope.name == "__new__":
                acceptable_obj_names.extend(
                    [
                        return_node.value.name
                        for return_node in scope.nodes_of_class(nodes.Return)
                        if isinstance(return_node.value, nodes.Name)
                    ]
                )

            for attribute in node.nodes_of_class(nodes.Attribute):
                if attribute.attrname != assign_attr.attrname:
                    continue

                if not isinstance(attribute.expr, nodes.Name):
                    continue

                if assign_attr.expr.name in {
                    "cls",
                    node.name,
                } and attribute.expr.name in {"cls", "self", node.name}:
                    # If assigned to cls or class name, can be accessed by cls/self/class name
                    break

                if (
                    assign_attr.expr.name in acceptable_obj_names
                    and attribute.expr.name == "self"
                ):
                    # If assigned to self.attrib, can only be accessed by self
                    # Or if __new__ was used, the returned object names are acceptable
                    break

                if assign_attr.expr.name == attribute.expr.name == node.name:
                    # Recognise attributes which are accessed via the class name
                    break

            else:
                args = (node.name, assign_attr.attrname)
                self.add_message("unused-private-member", node=assign_attr, args=args)

    def _check_attribute_defined_outside_init(self, cnode: nodes.ClassDef) -> None:
        # check access to existent members on non metaclass classes
        if (
            "attribute-defined-outside-init"
            in self.linter.config.ignored_checks_for_mixins
            and self._mixin_class_rgx.match(cnode.name)
        ):
            # We are in a mixin class. No need to try to figure out if
            # something is missing, since it is most likely that it will
            # miss.
            return

        accessed = self._accessed.accessed(cnode)
        if cnode.type != "metaclass":
            self._check_accessed_members(cnode, accessed)
        # checks attributes are defined in an allowed method such as __init__
        if not self.linter.is_message_enabled("attribute-defined-outside-init"):
            return
        defining_methods = self.linter.config.defining_attr_methods
        current_module = cnode.root()
        for attr, nodes_lst in cnode.instance_attrs.items():
            # Exclude `__dict__` as it is already defined.
            if attr == "__dict__":
                continue

            # Skip nodes which are not in the current module and it may screw up
            # the output, while it's not worth it
            nodes_lst = [
                n
                for n in nodes_lst
                if not isinstance(
                    n.statement(future=True), (nodes.Delete, nodes.AugAssign)
                )
                and n.root() is current_module
            ]
            if not nodes_lst:
                continue  # error detected by typechecking

            # Check if any method attr is defined in is a defining method
            # or if we have the attribute defined in a setter.
            frames = (node.frame(future=True) for node in nodes_lst)
            if any(
                frame.name in defining_methods or is_property_setter(frame)
                for frame in frames
            ):
                continue

            # check attribute is defined in a parent's __init__
            for parent in cnode.instance_attr_ancestors(attr):
                attr_defined = False
                # check if any parent method attr is defined in is a defining method
                for node in parent.instance_attrs[attr]:
                    if node.frame(future=True).name in defining_methods:
                        attr_defined = True
                if attr_defined:
                    # we're done :)
                    break
            else:
                # check attribute is defined as a class attribute
                try:
                    cnode.local_attr(attr)
                except astroid.NotFoundError:
                    for node in nodes_lst:
                        if node.frame(future=True).name not in defining_methods:
                            # If the attribute was set by a call in any
                            # of the defining methods, then don't emit
                            # the warning.
                            if _called_in_methods(
                                node.frame(future=True), cnode, defining_methods
                            ):
                                continue
                            self.add_message(
                                "attribute-defined-outside-init", args=attr, node=node
                            )

    # pylint: disable = too-many-branches
    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Check method arguments, overriding."""
        # ignore actual functions
        if not node.is_method():
            return

        self._check_useless_super_delegation(node)
        self._check_property_with_parameters(node)

        # 'is_method()' is called and makes sure that this is a 'nodes.ClassDef'
        klass: nodes.ClassDef = node.parent.frame(future=True)
        # check first argument is self if this is actually a method
        self._check_first_arg_for_type(node, klass.type == "metaclass")
        if node.name == "__init__":
            self._check_init(node, klass)
            return
        # check signature if the method overloads inherited method
        for overridden in klass.local_attr_ancestors(node.name):
            # get astroid for the searched method
            try:
                parent_function = overridden[node.name]
            except KeyError:
                # we have found the method but it's not in the local
                # dictionary.
                # This may happen with astroid build from living objects
                continue
            if not isinstance(parent_function, nodes.FunctionDef):
                continue
            self._check_signature(node, parent_function, klass)
            self._check_invalid_overridden_method(node, parent_function)
            break

        if node.decorators:
            for decorator in node.decorators.nodes:
                if isinstance(decorator, nodes.Attribute) and decorator.attrname in {
                    "getter",
                    "setter",
                    "deleter",
                }:
                    # attribute affectation will call this method, not hiding it
                    return
                if isinstance(decorator, nodes.Name):
                    if decorator.name == "property":
                        # attribute affectation will either call a setter or raise
                        # an attribute error, anyway not hiding the function
                        return

                # Infer the decorator and see if it returns something useful
                inferred = safe_infer(decorator)
                if not inferred:
                    return
                if isinstance(inferred, nodes.FunctionDef):
                    # Okay, it's a decorator, let's see what it can infer.
                    try:
                        inferred = next(inferred.infer_call_result(inferred))
                    except astroid.InferenceError:
                        return
                try:
                    if (
                        isinstance(inferred, (astroid.Instance, nodes.ClassDef))
                        and inferred.getattr("__get__")
                        and inferred.getattr("__set__")
                    ):
                        return
                except astroid.AttributeInferenceError:
                    pass

        # check if the method is hidden by an attribute
        # pylint: disable = too-many-try-statements
        try:
            overridden = klass.instance_attr(node.name)[0]
            overridden_frame = overridden.frame(future=True)
            if (
                isinstance(overridden_frame, nodes.FunctionDef)
                and overridden_frame.type == "method"
            ):
                overridden_frame = overridden_frame.parent.frame(future=True)
            if not (
                isinstance(overridden_frame, nodes.ClassDef)
                and klass.is_subtype_of(overridden_frame.qname())
            ):
                return

            # If a subclass defined the method then it's not our fault.
            for ancestor in klass.ancestors():
                if node.name in ancestor.instance_attrs and is_attr_private(node.name):
                    return
                for obj in ancestor.lookup(node.name)[1]:
                    if isinstance(obj, nodes.FunctionDef):
                        return
            args = (overridden.root().name, overridden.fromlineno)
            self.add_message("method-hidden", args=args, node=node)
        except astroid.NotFoundError:
            pass

    visit_asyncfunctiondef = visit_functiondef

    def _check_useless_super_delegation(self, function: nodes.FunctionDef) -> None:
        """Check if the given function node is an useless method override.

        We consider it *useless* if it uses the super() builtin, but having
        nothing additional whatsoever than not implementing the method at all.
        If the method uses super() to delegate an operation to the rest of the MRO,
        and if the method called is the same as the current one, the arguments
        passed to super() are the same as the parameters that were passed to
        this method, then the method could be removed altogether, by letting
        other implementation to take precedence.
        """
        if not _is_trivial_super_delegation(function):
            return

        call: nodes.Call = function.body[0].value

        # Classes that override __eq__ should also override
        # __hash__, even a trivial override is meaningful
        if function.name == "__hash__":
            for other_method in function.parent.mymethods():
                if other_method.name == "__eq__":
                    return

        # Check values of default args
        klass = function.parent.frame(future=True)
        meth_node = None
        for overridden in klass.local_attr_ancestors(function.name):
            # get astroid for the searched method
            try:
                meth_node = overridden[function.name]
            except KeyError:
                # we have found the method but it's not in the local
                # dictionary.
                # This may happen with astroid build from living objects
                continue
            if (
                not isinstance(meth_node, nodes.FunctionDef)
                # If the method have an ancestor which is not a
                # function then it is legitimate to redefine it
                or _has_different_parameters_default_value(
                    meth_node.args, function.args
                )
                # arguments to builtins such as Exception.__init__() cannot be inspected
                or (meth_node.args.args is None and function.argnames() != ["self"])
            ):
                return
            break

        # Detect if the parameters are the same as the call's arguments.
        params = _signature_from_arguments(function.args)
        args = _signature_from_call(call)

        if meth_node is not None:
            # Detect if the super method uses varargs and the function doesn't or makes some of those explicit
            if meth_node.args.vararg and (
                not function.args.vararg
                or len(function.args.args) > len(meth_node.args.args)
            ):
                return

            def form_annotations(arguments: nodes.Arguments) -> list[str]:
                annotations = chain(
                    (arguments.posonlyargs_annotations or []), arguments.annotations
                )
                return [ann.as_string() for ann in annotations if ann is not None]

            called_annotations = form_annotations(function.args)
            overridden_annotations = form_annotations(meth_node.args)
            if called_annotations and overridden_annotations:
                if called_annotations != overridden_annotations:
                    return

            if (
                function.returns is not None
                and meth_node.returns is not None
                and meth_node.returns.as_string() != function.returns.as_string()
            ):
                # Override adds typing information to the return type
                return

        if _definition_equivalent_to_call(params, args):
            self.add_message(
                "useless-parent-delegation",
                node=function,
                args=(function.name,),
                confidence=INFERENCE,
            )

    def _check_property_with_parameters(self, node: nodes.FunctionDef) -> None:
        if (
            node.args.args
            and len(node.args.args) > 1
            and decorated_with_property(node)
            and not is_property_setter(node)
        ):
            self.add_message("property-with-parameters", node=node)

    def _check_invalid_overridden_method(
        self,
        function_node: nodes.FunctionDef,
        parent_function_node: nodes.FunctionDef,
    ) -> None:
        parent_is_property = decorated_with_property(
            parent_function_node
        ) or is_property_setter_or_deleter(parent_function_node)
        current_is_property = decorated_with_property(
            function_node
        ) or is_property_setter_or_deleter(function_node)
        if parent_is_property and not current_is_property:
            self.add_message(
                "invalid-overridden-method",
                args=(function_node.name, "property", function_node.type),
                node=function_node,
            )
        elif not parent_is_property and current_is_property:
            self.add_message(
                "invalid-overridden-method",
                args=(function_node.name, "method", "property"),
                node=function_node,
            )

        parent_is_async = isinstance(parent_function_node, nodes.AsyncFunctionDef)
        current_is_async = isinstance(function_node, nodes.AsyncFunctionDef)

        if parent_is_async and not current_is_async:
            self.add_message(
                "invalid-overridden-method",
                args=(function_node.name, "async", "non-async"),
                node=function_node,
            )

        elif not parent_is_async and current_is_async:
            self.add_message(
                "invalid-overridden-method",
                args=(function_node.name, "non-async", "async"),
                node=function_node,
            )
        if (
            decorated_with(parent_function_node, ["typing.final"])
            or uninferable_final_decorators(parent_function_node.decorators)
        ) and self._py38_plus:
            self.add_message(
                "overridden-final-method",
                args=(function_node.name, parent_function_node.parent.frame().name),
                node=function_node,
            )

    def _check_slots(self, node: nodes.ClassDef) -> None:
        if "__slots__" not in node.locals:
            return

        for slots in node.ilookup("__slots__"):
            # check if __slots__ is a valid type
            if isinstance(slots, util.UninferableBase):
                continue
            if not is_iterable(slots) and not is_comprehension(slots):
                self.add_message("invalid-slots", node=node)
                continue

            if isinstance(slots, nodes.Const):
                # a string, ignore the following checks
                self.add_message("single-string-used-for-slots", node=node)
                continue
            if not hasattr(slots, "itered"):
                # we can't obtain the values, maybe a .deque?
                continue

            if isinstance(slots, nodes.Dict):
                values = [item[0] for item in slots.items]
            else:
                values = slots.itered()
            if isinstance(values, util.UninferableBase):
                continue
            for elt in values:
                try:
                    self._check_slots_elt(elt, node)
                except astroid.InferenceError:
                    continue
            self._check_redefined_slots(node, slots, values)

    def _check_redefined_slots(
        self,
        node: nodes.ClassDef,
        slots_node: nodes.NodeNG,
        slots_list: list[nodes.NodeNG],
    ) -> None:
        """Check if `node` redefines a slot which is defined in an ancestor class."""
        slots_names: list[str] = []
        for slot in slots_list:
            if isinstance(slot, nodes.Const):
                slots_names.append(slot.value)
            else:
                inferred_slot = safe_infer(slot)
                inferred_slot_value = getattr(inferred_slot, "value", None)
                if isinstance(inferred_slot_value, str):
                    slots_names.append(inferred_slot_value)

        # Slots of all parent classes
        ancestors_slots_names = {
            slot.value
            for ancestor in node.local_attr_ancestors("__slots__")
            for slot in ancestor.slots() or []
        }

        # Slots which are common to `node` and its parent classes
        redefined_slots = ancestors_slots_names.intersection(slots_names)

        if redefined_slots:
            self.add_message(
                "redefined-slots-in-subclass",
                args=([name for name in slots_names if name in redefined_slots],),
                node=slots_node,
            )

    def _check_slots_elt(
        self, elt: SuccessfulInferenceResult, node: nodes.ClassDef
    ) -> None:
        for inferred in elt.infer():
            if isinstance(inferred, util.UninferableBase):
                continue
            if not isinstance(inferred, nodes.Const) or not isinstance(
                inferred.value, str
            ):
                self.add_message(
                    "invalid-slots-object",
                    args=elt.as_string(),
                    node=elt,
                    confidence=INFERENCE,
                )
                continue
            if not inferred.value:
                self.add_message(
                    "invalid-slots-object",
                    args=elt.as_string(),
                    node=elt,
                    confidence=INFERENCE,
                )

            # Check if we have a conflict with a class variable.
            class_variable = node.locals.get(inferred.value)
            if class_variable:
                # Skip annotated assignments which don't conflict at all with slots.
                if len(class_variable) == 1:
                    parent = class_variable[0].parent
                    if isinstance(parent, nodes.AnnAssign) and parent.value is None:
                        return
                self.add_message(
                    "class-variable-slots-conflict", args=(inferred.value,), node=elt
                )

    def leave_functiondef(self, node: nodes.FunctionDef) -> None:
        """On method node, check if this method couldn't be a function.

        ignore class, static and abstract methods, initializer,
        methods overridden from a parent class.
        """
        if node.is_method():
            if node.args.args is not None:
                self._first_attrs.pop()

    leave_asyncfunctiondef = leave_functiondef

    def visit_attribute(self, node: nodes.Attribute) -> None:
        """Check if the getattr is an access to a class member
        if so, register it.

        Also check for access to protected
        class member from outside its class (but ignore __special__
        methods)
        """
        self._check_super_without_brackets(node)

        # Check self
        if self._uses_mandatory_method_param(node):
            self._accessed.set_accessed(node)
            return
        if not self.linter.is_message_enabled("protected-access"):
            return

        self._check_protected_attribute_access(node)

    def _check_super_without_brackets(self, node: nodes.Attribute) -> None:
        """Check if there is a function call on a super call without brackets."""
        # Check if attribute call is in frame definition in class definition
        frame = node.frame()
        if not isinstance(frame, nodes.FunctionDef):
            return
        if not isinstance(frame.parent.frame(), nodes.ClassDef):
            return
        if not isinstance(node.parent, nodes.Call):
            return
        if not isinstance(node.expr, nodes.Name):
            return
        if node.expr.name == "super":
            self.add_message("super-without-brackets", node=node.expr, confidence=HIGH)

    @only_required_for_messages(
        "assigning-non-slot", "invalid-class-object", "access-member-before-definition"
    )
    def visit_assignattr(self, node: nodes.AssignAttr) -> None:
        if isinstance(
            node.assign_type(), nodes.AugAssign
        ) and self._uses_mandatory_method_param(node):
            self._accessed.set_accessed(node)
        self._check_in_slots(node)
        self._check_invalid_class_object(node)

    def _check_invalid_class_object(self, node: nodes.AssignAttr) -> None:
        if not node.attrname == "__class__":
            return
        if isinstance(node.parent, nodes.Tuple):
            class_index = -1
            for i, elt in enumerate(node.parent.elts):
                if hasattr(elt, "attrname") and elt.attrname == "__class__":
                    class_index = i
            if class_index == -1:
                # This should not happen because we checked that the node name
                # is '__class__' earlier, but let's not be too confident here
                return  # pragma: no cover
            inferred = safe_infer(node.parent.parent.value.elts[class_index])
        else:
            inferred = safe_infer(node.parent.value)
        if (
            isinstance(inferred, (nodes.ClassDef, util.UninferableBase))
            or inferred is None
        ):
            # If is uninferable, we allow it to prevent false positives
            return
        self.add_message(
            "invalid-class-object",
            node=node,
            args=inferred.__class__.__name__,
            confidence=INFERENCE,
        )

    def _check_in_slots(self, node: nodes.AssignAttr) -> None:
        """Check that the given AssignAttr node
        is defined in the class slots.
        """
        inferred = safe_infer(node.expr)
        if not isinstance(inferred, astroid.Instance):
            return

        klass = inferred._proxied
        if not has_known_bases(klass):
            return
        if "__slots__" not in klass.locals or not klass.newstyle:
            return
        # If `__setattr__` is defined on the class, then we can't reason about
        # what will happen when assigning to an attribute.
        if any(
            base.locals.get("__setattr__")
            for base in klass.mro()
            if base.qname() != "builtins.object"
        ):
            return

        # If 'typing.Generic' is a base of bases of klass, the cached version
        # of 'slots()' might have been evaluated incorrectly, thus deleted cache entry.
        if any(base.qname() == "typing.Generic" for base in klass.mro()):
            cache = getattr(klass, "__cache", None)
            if cache and cache.get(klass.slots) is not None:
                del cache[klass.slots]

        slots = klass.slots()
        if slots is None:
            return
        # If any ancestor doesn't use slots, the slots
        # defined for this class are superfluous.
        if any(
            "__slots__" not in ancestor.locals and ancestor.name != "object"
            for ancestor in klass.ancestors()
        ):
            return

        if not any(slot.value == node.attrname for slot in slots):
            # If we have a '__dict__' in slots, then
            # assigning any name is valid.
            if not any(slot.value == "__dict__" for slot in slots):
                if _is_attribute_property(node.attrname, klass):
                    # Properties circumvent the slots mechanism,
                    # so we should not emit a warning for them.
                    return
                if node.attrname != "__class__" and utils.is_class_attr(
                    node.attrname, klass
                ):
                    return
                if node.attrname in klass.locals:
                    for local_name in klass.locals.get(node.attrname):
                        statement = local_name.statement(future=True)
                        if (
                            isinstance(statement, nodes.AnnAssign)
                            and not statement.value
                        ):
                            return
                    if _has_data_descriptor(klass, node.attrname):
                        # Descriptors circumvent the slots mechanism as well.
                        return
                if node.attrname == "__class__" and _has_same_layout_slots(
                    slots, node.parent.value
                ):
                    return
                self.add_message(
                    "assigning-non-slot",
                    args=(node.attrname,),
                    node=node,
                    confidence=INFERENCE,
                )

    @only_required_for_messages(
        "protected-access", "no-classmethod-decorator", "no-staticmethod-decorator"
    )
    def visit_assign(self, assign_node: nodes.Assign) -> None:
        self._check_classmethod_declaration(assign_node)
        node = assign_node.targets[0]
        if not isinstance(node, nodes.AssignAttr):
            return

        if self._uses_mandatory_method_param(node):
            return
        self._check_protected_attribute_access(node)

    def _check_classmethod_declaration(self, node: nodes.Assign) -> None:
        """Checks for uses of classmethod() or staticmethod().

        When a @classmethod or @staticmethod decorator should be used instead.
        A message will be emitted only if the assignment is at a class scope
        and only if the classmethod's argument belongs to the class where it
        is defined.
        `node` is an assign node.
        """
        if not isinstance(node.value, nodes.Call):
            return

        # check the function called is "classmethod" or "staticmethod"
        func = node.value.func
        if not isinstance(func, nodes.Name) or func.name not in (
            "classmethod",
            "staticmethod",
        ):
            return

        msg = (
            "no-classmethod-decorator"
            if func.name == "classmethod"
            else "no-staticmethod-decorator"
        )
        # assignment must be at a class scope
        parent_class = node.scope()
        if not isinstance(parent_class, nodes.ClassDef):
            return

        # Check if the arg passed to classmethod is a class member
        classmeth_arg = node.value.args[0]
        if not isinstance(classmeth_arg, nodes.Name):
            return

        method_name = classmeth_arg.name
        if any(method_name == member.name for member in parent_class.mymethods()):
            self.add_message(msg, node=node.targets[0])

    def _check_protected_attribute_access(
        self, node: nodes.Attribute | nodes.AssignAttr
    ) -> None:
        """Given an attribute access node (set or get), check if attribute
        access is legitimate.

        Call _check_first_attr with node before calling
        this method. Valid cases are:
        * self._attr in a method or cls._attr in a classmethod. Checked by
        _check_first_attr.
        * Klass._attr inside "Klass" class.
        * Klass2._attr inside "Klass" class when Klass2 is a base class of
            Klass.
        """
        attrname = node.attrname

        if (
            not is_attr_protected(attrname)
            or attrname in self.linter.config.exclude_protected
        ):
            return

        # Typing annotations in function definitions can include protected members
        if utils.is_node_in_type_annotation_context(node):
            return

        # Return if `attrname` is defined at the module-level or as a class attribute
        # and is listed in `exclude-protected`.
        inferred = safe_infer(node.expr)
        if (
            inferred
            and isinstance(inferred, (nodes.ClassDef, nodes.Module))
            and f"{inferred.name}.{attrname}" in self.linter.config.exclude_protected
        ):
            return

        klass = node_frame_class(node)
        if klass is None:
            # We are not in a class, no remaining valid case
            self.add_message("protected-access", node=node, args=attrname)
            return

        # In classes, check we are not getting a parent method
        # through the class object or through super

        # If the expression begins with a call to super, that's ok.
        if (
            isinstance(node.expr, nodes.Call)
            and isinstance(node.expr.func, nodes.Name)
            and node.expr.func.name == "super"
        ):
            return

        # If the expression begins with a call to type(self), that's ok.
        if self._is_type_self_call(node.expr):
            return

        # Check if we are inside the scope of a class or nested inner class
        inside_klass = True
        outer_klass = klass
        callee = node.expr.as_string()
        parents_callee = callee.split(".")
        parents_callee.reverse()
        for callee in parents_callee:
            if not outer_klass or callee != outer_klass.name:
                inside_klass = False
                break

            # Move up one level within the nested classes
            outer_klass = get_outer_class(outer_klass)

        # We are in a class, one remaining valid cases, Klass._attr inside
        # Klass
        if not (inside_klass or callee in klass.basenames):
            # Detect property assignments in the body of the class.
            # This is acceptable:
            #
            # class A:
            #     b = property(lambda: self._b)

            stmt = node.parent.statement(future=True)
            if (
                isinstance(stmt, nodes.Assign)
                and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], nodes.AssignName)
            ):
                name = stmt.targets[0].name
                if _is_attribute_property(name, klass):
                    return

            if (
                self._is_classmethod(node.frame(future=True))
                and self._is_inferred_instance(node.expr, klass)
                and self._is_class_or_instance_attribute(attrname, klass)
            ):
                return

            licit_protected_member = not attrname.startswith("__")
            if (
                not self.linter.config.check_protected_access_in_special_methods
                and licit_protected_member
                and self._is_called_inside_special_method(node)
            ):
                return

            self.add_message("protected-access", node=node, args=attrname)

    @staticmethod
    def _is_called_inside_special_method(node: nodes.NodeNG) -> bool:
        """Returns true if the node is located inside a special (aka dunder) method."""
        frame_name = node.frame(future=True).name
        return frame_name and frame_name in PYMETHODS

    def _is_type_self_call(self, expr: nodes.NodeNG) -> bool:
        return (
            isinstance(expr, nodes.Call)
            and isinstance(expr.func, nodes.Name)
            and expr.func.name == "type"
            and len(expr.args) == 1
            and self._is_mandatory_method_param(expr.args[0])
        )

    @staticmethod
    def _is_classmethod(func: LocalsDictNodeNG) -> bool:
        """Check if the given *func* node is a class method."""
        return isinstance(func, nodes.FunctionDef) and (
            func.type == "classmethod" or func.name == "__class_getitem__"
        )

    @staticmethod
    def _is_inferred_instance(expr: nodes.NodeNG, klass: nodes.ClassDef) -> bool:
        """Check if the inferred value of the given *expr* is an instance of
        *klass*.
        """
        inferred = safe_infer(expr)
        if not isinstance(inferred, astroid.Instance):
            return False
        return inferred._proxied is klass

    @staticmethod
    def _is_class_or_instance_attribute(name: str, klass: nodes.ClassDef) -> bool:
        """Check if the given attribute *name* is a class or instance member of the
        given *klass*.

        Returns ``True`` if the name is a property in the given klass,
        ``False`` otherwise.
        """

        if utils.is_class_attr(name, klass):
            return True

        try:
            klass.instance_attr(name)
            return True
        except astroid.NotFoundError:
            return False

    def _check_accessed_members(
        self, node: nodes.ClassDef, accessed: dict[str, list[_AccessNodes]]
    ) -> None:
        """Check that accessed members are defined."""
        excs = ("AttributeError", "Exception", "BaseException")
        for attr, nodes_lst in accessed.items():
            try:
                # is it a class attribute ?
                node.local_attr(attr)
                # yes, stop here
                continue
            except astroid.NotFoundError:
                pass
            # is it an instance attribute of a parent class ?
            try:
                next(node.instance_attr_ancestors(attr))
                # yes, stop here
                continue
            except StopIteration:
                pass
            # is it an instance attribute ?
            try:
                defstmts = node.instance_attr(attr)
            except astroid.NotFoundError:
                pass
            else:
                # filter out augment assignment nodes
                defstmts = [stmt for stmt in defstmts if stmt not in nodes_lst]
                if not defstmts:
                    # only augment assignment for this node, no-member should be
                    # triggered by the typecheck checker
                    continue
                # filter defstmts to only pick the first one when there are
                # several assignments in the same scope
                scope = defstmts[0].scope()
                defstmts = [
                    stmt
                    for i, stmt in enumerate(defstmts)
                    if i == 0 or stmt.scope() is not scope
                ]
                # if there are still more than one, don't attempt to be smarter
                # than we can be
                if len(defstmts) == 1:
                    defstmt = defstmts[0]
                    # check that if the node is accessed in the same method as
                    # it's defined, it's accessed after the initial assignment
                    frame = defstmt.frame(future=True)
                    lno = defstmt.fromlineno
                    for _node in nodes_lst:
                        if (
                            _node.frame(future=True) is frame
                            and _node.fromlineno < lno
                            and not astroid.are_exclusive(
                                _node.statement(future=True), defstmt, excs
                            )
                        ):
                            self.add_message(
                                "access-member-before-definition",
                                node=_node,
                                args=(attr, lno),
                            )

    def _check_first_arg_for_type(
        self, node: nodes.FunctionDef, metaclass: bool
    ) -> None:
        """Check the name of first argument, expect:.

        * 'self' for a regular method
        * 'cls' for a class method or a metaclass regular method (actually
          valid-classmethod-first-arg value)
        * 'mcs' for a metaclass class method (actually
          valid-metaclass-classmethod-first-arg)
        * not one of the above for a static method
        """
        # don't care about functions with unknown argument (builtins)
        if node.args.args is None:
            return
        if node.args.posonlyargs:
            first_arg = node.args.posonlyargs[0].name
        elif node.args.args:
            first_arg = node.argnames()[0]
        else:
            first_arg = None
        self._first_attrs.append(first_arg)
        first = self._first_attrs[-1]
        # static method
        if node.type == "staticmethod":
            if (
                first_arg == "self"
                or first_arg in self.linter.config.valid_classmethod_first_arg
                or first_arg in self.linter.config.valid_metaclass_classmethod_first_arg
            ):
                self.add_message("bad-staticmethod-argument", args=first, node=node)
                return
            self._first_attrs[-1] = None
        elif "builtins.staticmethod" in node.decoratornames():
            # Check if there is a decorator which is not named `staticmethod`
            # but is assigned to one.
            return
        # class / regular method with no args
        elif not (
            node.args.args
            or node.args.posonlyargs
            or node.args.vararg
            or node.args.kwarg
        ):
            self.add_message("no-method-argument", node=node, args=node.name)
        # metaclass
        elif metaclass:
            # metaclass __new__ or classmethod
            if node.type == "classmethod":
                self._check_first_arg_config(
                    first,
                    self.linter.config.valid_metaclass_classmethod_first_arg,
                    node,
                    "bad-mcs-classmethod-argument",
                    node.name,
                )
            # metaclass regular method
            else:
                self._check_first_arg_config(
                    first,
                    self.linter.config.valid_classmethod_first_arg,
                    node,
                    "bad-mcs-method-argument",
                    node.name,
                )
        # regular class with class method
        elif node.type == "classmethod" or node.name == "__class_getitem__":
            self._check_first_arg_config(
                first,
                self.linter.config.valid_classmethod_first_arg,
                node,
                "bad-classmethod-argument",
                node.name,
            )
        # regular class with regular method without self as argument
        elif first != "self":
            self.add_message("no-self-argument", node=node, args=node.name)

    def _check_first_arg_config(
        self,
        first: str | None,
        config: Sequence[str],
        node: nodes.FunctionDef,
        message: str,
        method_name: str,
    ) -> None:
        if first not in config:
            if len(config) == 1:
                valid = repr(config[0])
            else:
                valid = ", ".join(repr(v) for v in config[:-1])
                valid = f"{valid} or {config[-1]!r}"
            self.add_message(message, args=(method_name, valid), node=node)

    def _check_bases_classes(self, node: nodes.ClassDef) -> None:
        """Check that the given class node implements abstract methods from
        base classes.
        """

        def is_abstract(method: nodes.FunctionDef) -> bool:
            return method.is_abstract(pass_is_abstract=False)  # type: ignore[no-any-return]

        # check if this class abstract
        if class_is_abstract(node):
            return

        methods = sorted(
            unimplemented_abstract_methods(node, is_abstract).items(),
            key=lambda item: item[0],
        )
        for name, method in methods:
            owner = method.parent.frame(future=True)
            if owner is node:
                continue
            # owner is not this class, it must be a parent class
            # check that the ancestor's method is not abstract
            if name in node.locals:
                # it is redefined as an attribute or with a descriptor
                continue

            self.add_message(
                "abstract-method",
                node=node,
                args=(name, owner.name, node.name),
                confidence=INFERENCE,
            )

    def _check_init(self, node: nodes.FunctionDef, klass_node: nodes.ClassDef) -> None:
        """Check that the __init__ method call super or ancestors'__init__
        method (unless it is used for type hinting with `typing.overload`).
        """
        if not self.linter.is_message_enabled(
            "super-init-not-called"
        ) and not self.linter.is_message_enabled("non-parent-init-called"):
            return
        to_call = _ancestors_to_call(klass_node)
        not_called_yet = dict(to_call)
        parents_with_called_inits: set[bases.UnboundMethod] = set()
        for stmt in node.nodes_of_class(nodes.Call):
            expr = stmt.func
            if not isinstance(expr, nodes.Attribute) or expr.attrname != "__init__":
                continue
            # skip the test if using super
            if (
                isinstance(expr.expr, nodes.Call)
                and isinstance(expr.expr.func, nodes.Name)
                and expr.expr.func.name == "super"
            ):
                return
            # pylint: disable = too-many-try-statements
            try:
                for klass in expr.expr.infer():
                    if isinstance(klass, util.UninferableBase):
                        continue
                    # The inferred klass can be super(), which was
                    # assigned to a variable and the `__init__`
                    # was called later.
                    #
                    # base = super()
                    # base.__init__(...)

                    if (
                        isinstance(klass, astroid.Instance)
                        and isinstance(klass._proxied, nodes.ClassDef)
                        and is_builtin_object(klass._proxied)
                        and klass._proxied.name == "super"
                    ):
                        return
                    if isinstance(klass, astroid.objects.Super):
                        return
                    try:
                        method = not_called_yet.pop(klass)
                        # Record that the class' init has been called
                        parents_with_called_inits.add(node_frame_class(method))
                    except KeyError:
                        if klass not in klass_node.ancestors(recurs=False):
                            self.add_message(
                                "non-parent-init-called", node=expr, args=klass.name
                            )
            except astroid.InferenceError:
                continue
        for klass, method in not_called_yet.items():
            # Check if the init of the class that defines this init has already
            # been called.
            if node_frame_class(method) in parents_with_called_inits:
                return

            if utils.is_protocol_class(klass):
                return

            if decorated_with(node, ["typing.overload"]):
                continue
            self.add_message(
                "super-init-not-called",
                args=klass.name,
                node=node,
                confidence=INFERENCE,
            )

    def _check_signature(
        self,
        method1: nodes.FunctionDef,
        refmethod: nodes.FunctionDef,
        cls: nodes.ClassDef,
    ) -> None:
        """Check that the signature of the two given methods match."""
        if not (
            isinstance(method1, nodes.FunctionDef)
            and isinstance(refmethod, nodes.FunctionDef)
        ):
            self.add_message(
                "method-check-failed", args=(method1, refmethod), node=method1
            )
            return

        instance = cls.instantiate_class()
        method1 = astroid.scoped_nodes.function_to_method(method1, instance)
        refmethod = astroid.scoped_nodes.function_to_method(refmethod, instance)

        # Don't care about functions with unknown argument (builtins).
        if method1.args.args is None or refmethod.args.args is None:
            return

        # Ignore private to class methods.
        if is_attr_private(method1.name):
            return
        # Ignore setters, they have an implicit extra argument,
        # which shouldn't be taken in consideration.
        if is_property_setter(method1):
            return

        arg_differ_output = _different_parameters(
            refmethod, method1, dummy_parameter_regex=self._dummy_rgx
        )

        class_type = "overriding"

        if len(arg_differ_output) > 0:
            for msg in arg_differ_output:
                if "Number" in msg:
                    total_args_method1 = len(method1.args.args)
                    if method1.args.vararg:
                        total_args_method1 += 1
                    if method1.args.kwarg:
                        total_args_method1 += 1
                    if method1.args.kwonlyargs:
                        total_args_method1 += len(method1.args.kwonlyargs)
                    total_args_refmethod = len(refmethod.args.args)
                    if refmethod.args.vararg:
                        total_args_refmethod += 1
                    if refmethod.args.kwarg:
                        total_args_refmethod += 1
                    if refmethod.args.kwonlyargs:
                        total_args_refmethod += len(refmethod.args.kwonlyargs)
                    error_type = "arguments-differ"
                    msg_args = (
                        msg
                        + f"was {total_args_refmethod} in '{refmethod.parent.frame().name}.{refmethod.name}' and "
                        f"is now {total_args_method1} in",
                        class_type,
                        f"{method1.parent.frame().name}.{method1.name}",
                    )
                elif "renamed" in msg:
                    error_type = "arguments-renamed"
                    msg_args = (
                        msg,
                        class_type,
                        f"{method1.parent.frame().name}.{method1.name}",
                    )
                else:
                    error_type = "arguments-differ"
                    msg_args = (
                        msg,
                        class_type,
                        f"{method1.parent.frame().name}.{method1.name}",
                    )
                self.add_message(error_type, args=msg_args, node=method1)
        elif (
            len(method1.args.defaults) < len(refmethod.args.defaults)
            and not method1.args.vararg
        ):
            class_type = "overridden"
            self.add_message(
                "signature-differs", args=(class_type, method1.name), node=method1
            )

    def _uses_mandatory_method_param(
        self, node: nodes.Attribute | nodes.Assign | nodes.AssignAttr
    ) -> bool:
        """Check that attribute lookup name use first attribute variable name.

        Name is `self` for method, `cls` for classmethod and `mcs` for metaclass.
        """
        return self._is_mandatory_method_param(node.expr)

    def _is_mandatory_method_param(self, node: nodes.NodeNG) -> bool:
        """Check if nodes.Name corresponds to first attribute variable name.

        Name is `self` for method, `cls` for classmethod and `mcs` for metaclass.
        Static methods return False.
        """
        if self._first_attrs:
            first_attr = self._first_attrs[-1]
        else:
            # It's possible the function was already unregistered.
            closest_func = utils.get_node_first_ancestor_of_type(
                node, nodes.FunctionDef
            )
            if closest_func is None:
                return False
            if not closest_func.is_bound():
                return False
            if not closest_func.args.args:
                return False
            first_attr = closest_func.args.args[0].name
        return isinstance(node, nodes.Name) and node.name == first_attr


def _ancestors_to_call(
    klass_node: nodes.ClassDef, method_name: str = "__init__"
) -> dict[nodes.ClassDef, bases.UnboundMethod]:
    """Return a dictionary where keys are the list of base classes providing
    the queried method, and so that should/may be called from the method node.
    """
    to_call: dict[nodes.ClassDef, bases.UnboundMethod] = {}
    for base_node in klass_node.ancestors(recurs=False):
        try:
            init_node = next(base_node.igetattr(method_name))
            if not isinstance(init_node, astroid.UnboundMethod):
                continue
            if init_node.is_abstract():
                continue
            to_call[base_node] = init_node
        except astroid.InferenceError:
            continue
    return to_call
