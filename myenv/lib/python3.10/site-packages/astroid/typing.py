# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, Callable, Generator, TypeVar, Union

if TYPE_CHECKING:
    from astroid import bases, exceptions, nodes, transforms, util
    from astroid.context import InferenceContext
    from astroid.interpreter._import import spec

if sys.version_info >= (3, 8):
    from typing import TypedDict
else:
    from typing_extensions import TypedDict

_NodesT = TypeVar("_NodesT", bound="nodes.NodeNG")


class InferenceErrorInfo(TypedDict):
    """Store additional Inference error information
    raised with StopIteration exception.
    """

    node: nodes.NodeNG
    context: InferenceContext | None


InferFn = Callable[..., Any]


class AstroidManagerBrain(TypedDict):
    """Dictionary to store relevant information for a AstroidManager class."""

    astroid_cache: dict[str, nodes.Module]
    _mod_file_cache: dict[
        tuple[str, str | None], spec.ModuleSpec | exceptions.AstroidImportError
    ]
    _failed_import_hooks: list[Callable[[str], nodes.Module]]
    always_load_extensions: bool
    optimize_ast: bool
    extension_package_whitelist: set[str]
    _transform: transforms.TransformVisitor


InferenceResult = Union["nodes.NodeNG", "util.UninferableBase", "bases.Proxy"]
SuccessfulInferenceResult = Union["nodes.NodeNG", "bases.Proxy"]

ConstFactoryResult = Union[
    "nodes.List",
    "nodes.Set",
    "nodes.Tuple",
    "nodes.Dict",
    "nodes.Const",
    "nodes.EmptyNode",
]

InferBinaryOp = Callable[
    [
        Union[_NodesT, "bases.Instance"],
        Union["nodes.AugAssign", "nodes.BinOp"],
        str,
        InferenceResult,
        "InferenceContext",
        SuccessfulInferenceResult,
    ],
    Generator[InferenceResult, None, None],
]
