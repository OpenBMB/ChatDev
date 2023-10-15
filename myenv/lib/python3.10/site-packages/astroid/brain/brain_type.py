# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""
Astroid hooks for type support.

Starting from python3.9, type object behaves as it had __class_getitem__ method.
However it was not possible to simply add this method inside type's body, otherwise
all types would also have this method. In this case it would have been possible
to write str[int].
Guido Van Rossum proposed a hack to handle this in the interpreter:
https://github.com/python/cpython/blob/67e394562d67cbcd0ac8114e5439494e7645b8f5/Objects/abstract.c#L181-L184

This brain follows the same logic. It is no wise to add permanently the __class_getitem__ method
to the type object. Instead we choose to add it only in the case of a subscript node
which inside name node is type.
Doing this type[int] is allowed whereas str[int] is not.

Thanks to Lukasz Langa for fruitful discussion.
"""

from __future__ import annotations

from astroid import extract_node, inference_tip, nodes
from astroid.const import PY39_PLUS
from astroid.context import InferenceContext
from astroid.exceptions import UseInferenceDefault
from astroid.manager import AstroidManager


def _looks_like_type_subscript(node) -> bool:
    """
    Try to figure out if a Name node is used inside a type related subscript.

    :param node: node to check
    :type node: astroid.nodes.node_classes.NodeNG
    :return: whether the node is a Name node inside a type related subscript
    """
    if isinstance(node, nodes.Name) and isinstance(node.parent, nodes.Subscript):
        return node.name == "type"
    return False


def infer_type_sub(node, context: InferenceContext | None = None):
    """
    Infer a type[...] subscript.

    :param node: node to infer
    :type node: astroid.nodes.node_classes.NodeNG
    :return: the inferred node
    :rtype: nodes.NodeNG
    """
    node_scope, _ = node.scope().lookup("type")
    if not isinstance(node_scope, nodes.Module) or node_scope.qname() != "builtins":
        raise UseInferenceDefault()
    class_src = """
    class type:
        def __class_getitem__(cls, key):
            return cls
     """
    node = extract_node(class_src)
    return node.infer(context=context)


if PY39_PLUS:
    AstroidManager().register_transform(
        nodes.Name, inference_tip(infer_type_sub), _looks_like_type_subscript
    )
