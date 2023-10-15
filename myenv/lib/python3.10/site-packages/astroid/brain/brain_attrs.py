# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""
Astroid hook for the attrs library

Without this hook pylint reports unsupported-assignment-operation
for attrs classes
"""
from astroid.manager import AstroidManager
from astroid.nodes.node_classes import AnnAssign, Assign, AssignName, Call, Unknown
from astroid.nodes.scoped_nodes import ClassDef

ATTRIB_NAMES = frozenset(
    ("attr.ib", "attrib", "attr.attrib", "attr.field", "attrs.field", "field")
)
ATTRS_NAMES = frozenset(
    (
        "attr.s",
        "attrs",
        "attr.attrs",
        "attr.attributes",
        "attr.define",
        "attr.mutable",
        "attr.frozen",
        "attrs.define",
        "attrs.mutable",
        "attrs.frozen",
    )
)


def is_decorated_with_attrs(node, decorator_names=ATTRS_NAMES) -> bool:
    """Return whether a decorated node has an attr decorator applied."""
    if not node.decorators:
        return False
    for decorator_attribute in node.decorators.nodes:
        if isinstance(decorator_attribute, Call):  # decorator with arguments
            decorator_attribute = decorator_attribute.func
        if decorator_attribute.as_string() in decorator_names:
            return True
    return False


def attr_attributes_transform(node: ClassDef) -> None:
    """Given that the ClassNode has an attr decorator,
    rewrite class attributes as instance attributes
    """
    # Astroid can't infer this attribute properly
    # Prevents https://github.com/PyCQA/pylint/issues/1884
    node.locals["__attrs_attrs__"] = [Unknown(parent=node)]

    for cdef_body_node in node.body:
        if not isinstance(cdef_body_node, (Assign, AnnAssign)):
            continue
        if isinstance(cdef_body_node.value, Call):
            if cdef_body_node.value.func.as_string() not in ATTRIB_NAMES:
                continue
        else:
            continue
        targets = (
            cdef_body_node.targets
            if hasattr(cdef_body_node, "targets")
            else [cdef_body_node.target]
        )
        for target in targets:
            rhs_node = Unknown(
                lineno=cdef_body_node.lineno,
                col_offset=cdef_body_node.col_offset,
                parent=cdef_body_node,
            )
            if isinstance(target, AssignName):
                # Could be a subscript if the code analysed is
                # i = Optional[str] = ""
                # See https://github.com/PyCQA/pylint/issues/4439
                node.locals[target.name] = [rhs_node]
                node.instance_attrs[target.name] = [rhs_node]


AstroidManager().register_transform(
    ClassDef, attr_attributes_transform, is_decorated_with_attrs
)
