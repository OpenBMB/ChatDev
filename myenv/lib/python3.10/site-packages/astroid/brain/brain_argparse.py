# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

from astroid import arguments, inference_tip, nodes
from astroid.context import InferenceContext
from astroid.exceptions import UseInferenceDefault
from astroid.manager import AstroidManager


def infer_namespace(node, context: InferenceContext | None = None):
    callsite = arguments.CallSite.from_call(node, context=context)
    if not callsite.keyword_arguments:
        # Cannot make sense of it.
        raise UseInferenceDefault()

    class_node = nodes.ClassDef("Namespace")
    # Set parent manually until ClassDef constructor fixed:
    # https://github.com/PyCQA/astroid/issues/1490
    class_node.parent = node.parent
    for attr in set(callsite.keyword_arguments):
        fake_node = nodes.EmptyNode()
        fake_node.parent = class_node
        fake_node.attrname = attr
        class_node.instance_attrs[attr] = [fake_node]
    return iter((class_node.instantiate_class(),))


def _looks_like_namespace(node) -> bool:
    func = node.func
    if isinstance(func, nodes.Attribute):
        return (
            func.attrname == "Namespace"
            and isinstance(func.expr, nodes.Name)
            and func.expr.name == "argparse"
        )
    return False


AstroidManager().register_transform(
    nodes.Call, inference_tip(infer_namespace), _looks_like_namespace
)
