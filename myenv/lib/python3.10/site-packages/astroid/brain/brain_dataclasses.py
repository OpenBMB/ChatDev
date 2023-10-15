# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""
Astroid hook for the dataclasses library.

Support built-in dataclasses, pydantic.dataclasses, and marshmallow_dataclass-annotated
dataclasses. References:
- https://docs.python.org/3/library/dataclasses.html
- https://pydantic-docs.helpmanual.io/usage/dataclasses/
- https://lovasoa.github.io/marshmallow_dataclass/
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from typing import Tuple, Union

from astroid import bases, context, helpers, nodes
from astroid.builder import parse
from astroid.const import PY39_PLUS, PY310_PLUS
from astroid.exceptions import AstroidSyntaxError, InferenceError, UseInferenceDefault
from astroid.inference_tip import inference_tip
from astroid.manager import AstroidManager
from astroid.typing import InferenceResult
from astroid.util import Uninferable, UninferableBase

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal

_FieldDefaultReturn = Union[
    None,
    Tuple[Literal["default"], nodes.NodeNG],
    Tuple[Literal["default_factory"], nodes.Call],
]

DATACLASSES_DECORATORS = frozenset(("dataclass",))
FIELD_NAME = "field"
DATACLASS_MODULES = frozenset(
    ("dataclasses", "marshmallow_dataclass", "pydantic.dataclasses")
)
DEFAULT_FACTORY = "_HAS_DEFAULT_FACTORY"  # based on typing.py


def is_decorated_with_dataclass(
    node: nodes.ClassDef, decorator_names: frozenset[str] = DATACLASSES_DECORATORS
) -> bool:
    """Return True if a decorated node has a `dataclass` decorator applied."""
    if not isinstance(node, nodes.ClassDef) or not node.decorators:
        return False

    return any(
        _looks_like_dataclass_decorator(decorator_attribute, decorator_names)
        for decorator_attribute in node.decorators.nodes
    )


def dataclass_transform(node: nodes.ClassDef) -> None:
    """Rewrite a dataclass to be easily understood by pylint."""
    node.is_dataclass = True

    for assign_node in _get_dataclass_attributes(node):
        name = assign_node.target.name

        rhs_node = nodes.Unknown(
            lineno=assign_node.lineno,
            col_offset=assign_node.col_offset,
            parent=assign_node,
        )
        rhs_node = AstroidManager().visit_transforms(rhs_node)
        node.instance_attrs[name] = [rhs_node]

    if not _check_generate_dataclass_init(node):
        return

    kw_only_decorated = False
    if PY310_PLUS and node.decorators.nodes:
        for decorator in node.decorators.nodes:
            if not isinstance(decorator, nodes.Call):
                kw_only_decorated = False
                break
            for keyword in decorator.keywords:
                if keyword.arg == "kw_only":
                    kw_only_decorated = keyword.value.bool_value()

    init_str = _generate_dataclass_init(
        node,
        list(_get_dataclass_attributes(node, init=True)),
        kw_only_decorated,
    )

    try:
        init_node = parse(init_str)["__init__"]
    except AstroidSyntaxError:
        pass
    else:
        init_node.parent = node
        init_node.lineno, init_node.col_offset = None, None
        node.locals["__init__"] = [init_node]

        root = node.root()
        if DEFAULT_FACTORY not in root.locals:
            new_assign = parse(f"{DEFAULT_FACTORY} = object()").body[0]
            new_assign.parent = root
            root.locals[DEFAULT_FACTORY] = [new_assign.targets[0]]


def _get_dataclass_attributes(
    node: nodes.ClassDef, init: bool = False
) -> Iterator[nodes.AnnAssign]:
    """Yield the AnnAssign nodes of dataclass attributes for the node.

    If init is True, also include InitVars.
    """
    for assign_node in node.body:
        if not isinstance(assign_node, nodes.AnnAssign) or not isinstance(
            assign_node.target, nodes.AssignName
        ):
            continue

        # Annotation is never None
        if _is_class_var(assign_node.annotation):  # type: ignore[arg-type]
            continue

        if _is_keyword_only_sentinel(assign_node.annotation):
            continue

        # Annotation is never None
        if not init and _is_init_var(assign_node.annotation):  # type: ignore[arg-type]
            continue

        yield assign_node


def _check_generate_dataclass_init(node: nodes.ClassDef) -> bool:
    """Return True if we should generate an __init__ method for node.

    This is True when:
        - node doesn't define its own __init__ method
        - the dataclass decorator was called *without* the keyword argument init=False
    """
    if "__init__" in node.locals:
        return False

    found = None

    for decorator_attribute in node.decorators.nodes:
        if not isinstance(decorator_attribute, nodes.Call):
            continue

        if _looks_like_dataclass_decorator(decorator_attribute):
            found = decorator_attribute

    if found is None:
        return True

    # Check for keyword arguments of the form init=False
    return not any(
        keyword.arg == "init"
        and not keyword.value.bool_value()  # type: ignore[union-attr] # value is never None
        for keyword in found.keywords
    )


def _find_arguments_from_base_classes(
    node: nodes.ClassDef,
) -> tuple[
    dict[str, tuple[str | None, str | None]], dict[str, tuple[str | None, str | None]]
]:
    """Iterate through all bases and get their typing and defaults."""
    pos_only_store: dict[str, tuple[str | None, str | None]] = {}
    kw_only_store: dict[str, tuple[str | None, str | None]] = {}
    # See TODO down below
    # all_have_defaults = True

    for base in reversed(node.mro()):
        if not base.is_dataclass:
            continue
        try:
            base_init: nodes.FunctionDef = base.locals["__init__"][0]
        except KeyError:
            continue

        pos_only, kw_only = base_init.args._get_arguments_data()
        for posarg, data in pos_only.items():
            # if data[1] is None:
            #     if all_have_defaults and pos_only_store:
            #         # TODO: This should return an Uninferable as this would raise
            #         # a TypeError at runtime. However, transforms can't return
            #         # Uninferables currently.
            #         pass
            #     all_have_defaults = False
            pos_only_store[posarg] = data

        for kwarg, data in kw_only.items():
            kw_only_store[kwarg] = data
    return pos_only_store, kw_only_store


def _parse_arguments_into_strings(
    pos_only_store: dict[str, tuple[str | None, str | None]],
    kw_only_store: dict[str, tuple[str | None, str | None]],
) -> tuple[str, str]:
    """Parse positional and keyword arguments into strings for an __init__ method."""
    pos_only, kw_only = "", ""
    for pos_arg, data in pos_only_store.items():
        pos_only += pos_arg
        if data[0]:
            pos_only += ": " + data[0]
        if data[1]:
            pos_only += " = " + data[1]
        pos_only += ", "
    for kw_arg, data in kw_only_store.items():
        kw_only += kw_arg
        if data[0]:
            kw_only += ": " + data[0]
        if data[1]:
            kw_only += " = " + data[1]
        kw_only += ", "

    return pos_only, kw_only


def _get_previous_field_default(node: nodes.ClassDef, name: str) -> nodes.NodeNG | None:
    """Get the default value of a previously defined field."""
    for base in reversed(node.mro()):
        if not base.is_dataclass:
            continue
        if name in base.locals:
            for assign in base.locals[name]:
                if (
                    isinstance(assign.parent, nodes.AnnAssign)
                    and assign.parent.value
                    and isinstance(assign.parent.value, nodes.Call)
                    and _looks_like_dataclass_field_call(assign.parent.value)
                ):
                    default = _get_field_default(assign.parent.value)
                    if default:
                        return default[1]
    return None


def _generate_dataclass_init(  # pylint: disable=too-many-locals
    node: nodes.ClassDef, assigns: list[nodes.AnnAssign], kw_only_decorated: bool
) -> str:
    """Return an init method for a dataclass given the targets."""
    params: list[str] = []
    kw_only_params: list[str] = []
    assignments: list[str] = []

    prev_pos_only_store, prev_kw_only_store = _find_arguments_from_base_classes(node)

    for assign in assigns:
        name, annotation, value = assign.target.name, assign.annotation, assign.value

        # Check whether this assign is overriden by a property assignment
        property_node: nodes.FunctionDef | None = None
        for additional_assign in node.locals[name]:
            if not isinstance(additional_assign, nodes.FunctionDef):
                continue
            if not additional_assign.decorators:
                continue
            if "builtins.property" in additional_assign.decoratornames():
                property_node = additional_assign
                break

        is_field = isinstance(value, nodes.Call) and _looks_like_dataclass_field_call(
            value, check_scope=False
        )

        if is_field:
            # Skip any fields that have `init=False`
            if any(
                keyword.arg == "init" and not keyword.value.bool_value()
                for keyword in value.keywords  # type: ignore[union-attr] # value is never None
            ):
                # Also remove the name from the previous arguments to be inserted later
                prev_pos_only_store.pop(name, None)
                prev_kw_only_store.pop(name, None)
                continue

        if _is_init_var(annotation):  # type: ignore[arg-type] # annotation is never None
            init_var = True
            if isinstance(annotation, nodes.Subscript):
                annotation = annotation.slice
            else:
                # Cannot determine type annotation for parameter from InitVar
                annotation = None
            assignment_str = ""
        else:
            init_var = False
            assignment_str = f"self.{name} = {name}"

        ann_str, default_str = None, None
        if annotation is not None:
            ann_str = annotation.as_string()

        if value:
            if is_field:
                result = _get_field_default(value)  # type: ignore[arg-type]
                if result:
                    default_type, default_node = result
                    if default_type == "default":
                        default_str = default_node.as_string()
                    elif default_type == "default_factory":
                        default_str = DEFAULT_FACTORY
                        assignment_str = (
                            f"self.{name} = {default_node.as_string()} "
                            f"if {name} is {DEFAULT_FACTORY} else {name}"
                        )
            else:
                default_str = value.as_string()
        elif property_node:
            # We set the result of the property call as default
            # This hides the fact that this would normally be a 'property object'
            # But we can't represent those as string
            try:
                # Call str to make sure also Uninferable gets stringified
                default_str = str(next(property_node.infer_call_result()).as_string())
            except (InferenceError, StopIteration):
                pass
        else:
            # Even with `init=False` the default value still can be propogated to
            # later assignments. Creating weird signatures like:
            # (self, a: str = 1) -> None
            previous_default = _get_previous_field_default(node, name)
            if previous_default:
                default_str = previous_default.as_string()

        # Construct the param string to add to the init if necessary
        param_str = name
        if ann_str is not None:
            param_str += f": {ann_str}"
        if default_str is not None:
            param_str += f" = {default_str}"

        # If the field is a kw_only field, we need to add it to the kw_only_params
        # This overwrites whether or not the class is kw_only decorated
        if is_field:
            kw_only = [k for k in value.keywords if k.arg == "kw_only"]  # type: ignore[union-attr]
            if kw_only:
                if kw_only[0].value.bool_value():
                    kw_only_params.append(param_str)
                else:
                    params.append(param_str)
                continue
        # If kw_only decorated, we need to add all parameters to the kw_only_params
        if kw_only_decorated:
            if name in prev_kw_only_store:
                prev_kw_only_store[name] = (ann_str, default_str)
            else:
                kw_only_params.append(param_str)
        else:
            # If the name was previously seen, overwrite that data
            # pylint: disable-next=else-if-used
            if name in prev_pos_only_store:
                prev_pos_only_store[name] = (ann_str, default_str)
            elif name in prev_kw_only_store:
                params = [name] + params
                prev_kw_only_store.pop(name)
            else:
                params.append(param_str)

        if not init_var:
            assignments.append(assignment_str)

    prev_pos_only, prev_kw_only = _parse_arguments_into_strings(
        prev_pos_only_store, prev_kw_only_store
    )

    # Construct the new init method paramter string
    # First we do the positional only parameters, making sure to add the
    # the self parameter and the comma to allow adding keyword only parameters
    params_string = "" if "self" in prev_pos_only else "self, "
    params_string += prev_pos_only + ", ".join(params)
    if not params_string.endswith(", "):
        params_string += ", "

    # Then we add the keyword only parameters
    if prev_kw_only or kw_only_params:
        params_string += "*, "
    params_string += f"{prev_kw_only}{', '.join(kw_only_params)}"

    assignments_string = "\n    ".join(assignments) if assignments else "pass"
    return f"def __init__({params_string}) -> None:\n    {assignments_string}"


def infer_dataclass_attribute(
    node: nodes.Unknown, ctx: context.InferenceContext | None = None
) -> Iterator[InferenceResult]:
    """Inference tip for an Unknown node that was dynamically generated to
    represent a dataclass attribute.

    In the case that a default value is provided, that is inferred first.
    Then, an Instance of the annotated class is yielded.
    """
    assign = node.parent
    if not isinstance(assign, nodes.AnnAssign):
        yield Uninferable
        return

    annotation, value = assign.annotation, assign.value
    if value is not None:
        yield from value.infer(context=ctx)
    if annotation is not None:
        yield from _infer_instance_from_annotation(annotation, ctx=ctx)
    else:
        yield Uninferable


def infer_dataclass_field_call(
    node: nodes.Call, ctx: context.InferenceContext | None = None
) -> Iterator[InferenceResult]:
    """Inference tip for dataclass field calls."""
    if not isinstance(node.parent, (nodes.AnnAssign, nodes.Assign)):
        raise UseInferenceDefault
    result = _get_field_default(node)
    if not result:
        yield Uninferable
    else:
        default_type, default = result
        if default_type == "default":
            yield from default.infer(context=ctx)
        else:
            new_call = parse(default.as_string()).body[0].value
            new_call.parent = node.parent
            yield from new_call.infer(context=ctx)


def _looks_like_dataclass_decorator(
    node: nodes.NodeNG, decorator_names: frozenset[str] = DATACLASSES_DECORATORS
) -> bool:
    """Return True if node looks like a dataclass decorator.

    Uses inference to lookup the value of the node, and if that fails,
    matches against specific names.
    """
    if isinstance(node, nodes.Call):  # decorator with arguments
        node = node.func
    try:
        inferred = next(node.infer())
    except (InferenceError, StopIteration):
        inferred = Uninferable

    if isinstance(inferred, UninferableBase):
        if isinstance(node, nodes.Name):
            return node.name in decorator_names
        if isinstance(node, nodes.Attribute):
            return node.attrname in decorator_names

        return False

    return (
        isinstance(inferred, nodes.FunctionDef)
        and inferred.name in decorator_names
        and inferred.root().name in DATACLASS_MODULES
    )


def _looks_like_dataclass_attribute(node: nodes.Unknown) -> bool:
    """Return True if node was dynamically generated as the child of an AnnAssign
    statement.
    """
    parent = node.parent
    if not parent:
        return False

    scope = parent.scope()
    return (
        isinstance(parent, nodes.AnnAssign)
        and isinstance(scope, nodes.ClassDef)
        and is_decorated_with_dataclass(scope)
    )


def _looks_like_dataclass_field_call(
    node: nodes.Call, check_scope: bool = True
) -> bool:
    """Return True if node is calling dataclasses field or Field
    from an AnnAssign statement directly in the body of a ClassDef.

    If check_scope is False, skips checking the statement and body.
    """
    if check_scope:
        stmt = node.statement(future=True)
        scope = stmt.scope()
        if not (
            isinstance(stmt, nodes.AnnAssign)
            and stmt.value is not None
            and isinstance(scope, nodes.ClassDef)
            and is_decorated_with_dataclass(scope)
        ):
            return False

    try:
        inferred = next(node.func.infer())
    except (InferenceError, StopIteration):
        return False

    if not isinstance(inferred, nodes.FunctionDef):
        return False

    return inferred.name == FIELD_NAME and inferred.root().name in DATACLASS_MODULES


def _get_field_default(field_call: nodes.Call) -> _FieldDefaultReturn:
    """Return a the default value of a field call, and the corresponding keyword
    argument name.

    field(default=...) results in the ... node
    field(default_factory=...) results in a Call node with func ... and no arguments

    If neither or both arguments are present, return ("", None) instead,
    indicating that there is not a valid default value.
    """
    default, default_factory = None, None
    for keyword in field_call.keywords:
        if keyword.arg == "default":
            default = keyword.value
        elif keyword.arg == "default_factory":
            default_factory = keyword.value

    if default is not None and default_factory is None:
        return "default", default

    if default is None and default_factory is not None:
        new_call = nodes.Call(
            lineno=field_call.lineno,
            col_offset=field_call.col_offset,
            parent=field_call.parent,
        )
        new_call.postinit(func=default_factory)
        return "default_factory", new_call

    return None


def _is_class_var(node: nodes.NodeNG) -> bool:
    """Return True if node is a ClassVar, with or without subscripting."""
    if PY39_PLUS:
        try:
            inferred = next(node.infer())
        except (InferenceError, StopIteration):
            return False

        return getattr(inferred, "name", "") == "ClassVar"

    # Before Python 3.9, inference returns typing._SpecialForm instead of ClassVar.
    # Our backup is to inspect the node's structure.
    return isinstance(node, nodes.Subscript) and (
        isinstance(node.value, nodes.Name)
        and node.value.name == "ClassVar"
        or isinstance(node.value, nodes.Attribute)
        and node.value.attrname == "ClassVar"
    )


def _is_keyword_only_sentinel(node: nodes.NodeNG) -> bool:
    """Return True if node is the KW_ONLY sentinel."""
    if not PY310_PLUS:
        return False
    inferred = helpers.safe_infer(node)
    return (
        isinstance(inferred, bases.Instance)
        and inferred.qname() == "dataclasses._KW_ONLY_TYPE"
    )


def _is_init_var(node: nodes.NodeNG) -> bool:
    """Return True if node is an InitVar, with or without subscripting."""
    try:
        inferred = next(node.infer())
    except (InferenceError, StopIteration):
        return False

    return getattr(inferred, "name", "") == "InitVar"


# Allowed typing classes for which we support inferring instances
_INFERABLE_TYPING_TYPES = frozenset(
    (
        "Dict",
        "FrozenSet",
        "List",
        "Set",
        "Tuple",
    )
)


def _infer_instance_from_annotation(
    node: nodes.NodeNG, ctx: context.InferenceContext | None = None
) -> Iterator[UninferableBase | bases.Instance]:
    """Infer an instance corresponding to the type annotation represented by node.

    Currently has limited support for the typing module.
    """
    klass = None
    try:
        klass = next(node.infer(context=ctx))
    except (InferenceError, StopIteration):
        yield Uninferable
    if not isinstance(klass, nodes.ClassDef):
        yield Uninferable
    elif klass.root().name in {
        "typing",
        "_collections_abc",
        "",
    }:  # "" because of synthetic nodes in brain_typing.py
        if klass.name in _INFERABLE_TYPING_TYPES:
            yield klass.instantiate_class()
        else:
            yield Uninferable
    else:
        yield klass.instantiate_class()


AstroidManager().register_transform(
    nodes.ClassDef, dataclass_transform, is_decorated_with_dataclass
)

AstroidManager().register_transform(
    nodes.Call,
    inference_tip(infer_dataclass_field_call, raise_on_overwrite=True),
    _looks_like_dataclass_field_call,
)

AstroidManager().register_transform(
    nodes.Unknown,
    inference_tip(infer_dataclass_attribute, raise_on_overwrite=True),
    _looks_like_dataclass_attribute,
)
