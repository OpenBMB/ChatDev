# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

from collections.abc import Iterator

from astroid import bases, context, inference_tip, nodes
from astroid.builder import _extract_single_node
from astroid.exceptions import InferenceError, UseInferenceDefault
from astroid.manager import AstroidManager

PATH_TEMPLATE = """
from pathlib import Path
Path
"""


def _looks_like_parents_subscript(node: nodes.Subscript) -> bool:
    if not (
        isinstance(node.value, nodes.Attribute) and node.value.attrname == "parents"
    ):
        return False

    try:
        value = next(node.value.infer())
    except (InferenceError, StopIteration):
        return False
    return (
        isinstance(value, bases.Instance)
        and isinstance(value._proxied, nodes.ClassDef)
        and value.qname() == "pathlib._PathParents"
    )


def infer_parents_subscript(
    subscript_node: nodes.Subscript, ctx: context.InferenceContext | None = None
) -> Iterator[bases.Instance]:
    if isinstance(subscript_node.slice, nodes.Const):
        path_cls = next(_extract_single_node(PATH_TEMPLATE).infer())
        return iter([path_cls.instantiate_class()])

    raise UseInferenceDefault


AstroidManager().register_transform(
    nodes.Subscript,
    inference_tip(infer_parents_subscript),
    _looks_like_parents_subscript,
)
