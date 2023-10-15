# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Base class defining the interface for a printer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import NamedTuple

from astroid import nodes

from pylint.pyreverse.utils import get_annotation_label


class NodeType(Enum):
    CLASS = "class"
    INTERFACE = "interface"
    PACKAGE = "package"


class EdgeType(Enum):
    INHERITS = "inherits"
    IMPLEMENTS = "implements"
    ASSOCIATION = "association"
    AGGREGATION = "aggregation"
    USES = "uses"


class Layout(Enum):
    LEFT_TO_RIGHT = "LR"
    RIGHT_TO_LEFT = "RL"
    TOP_TO_BOTTOM = "TB"
    BOTTOM_TO_TOP = "BT"


class NodeProperties(NamedTuple):
    label: str
    attrs: list[str] | None = None
    methods: list[nodes.FunctionDef] | None = None
    color: str | None = None
    fontcolor: str | None = None


class Printer(ABC):
    """Base class defining the interface for a printer."""

    def __init__(
        self,
        title: str,
        layout: Layout | None = None,
        use_automatic_namespace: bool | None = None,
    ) -> None:
        self.title: str = title
        self.layout = layout
        self.use_automatic_namespace = use_automatic_namespace
        self.lines: list[str] = []
        self._indent = ""
        self._open_graph()

    def _inc_indent(self) -> None:
        """Increment indentation."""
        self._indent += "  "

    def _dec_indent(self) -> None:
        """Decrement indentation."""
        self._indent = self._indent[:-2]

    @abstractmethod
    def _open_graph(self) -> None:
        """Emit the header lines, i.e. all boilerplate code that defines things like
        layout etc.
        """

    def emit(self, line: str, force_newline: bool | None = True) -> None:
        if force_newline and not line.endswith("\n"):
            line += "\n"
        self.lines.append(self._indent + line)

    @abstractmethod
    def emit_node(
        self,
        name: str,
        type_: NodeType,
        properties: NodeProperties | None = None,
    ) -> None:
        """Create a new node.

        Nodes can be classes, packages, participants etc.
        """

    @abstractmethod
    def emit_edge(
        self,
        from_node: str,
        to_node: str,
        type_: EdgeType,
        label: str | None = None,
    ) -> None:
        """Create an edge from one node to another to display relationships."""

    @staticmethod
    def _get_method_arguments(method: nodes.FunctionDef) -> list[str]:
        if method.args.args is None:
            return []

        first_arg = 0 if method.type in {"function", "staticmethod"} else 1
        arguments: list[nodes.AssignName] = method.args.args[first_arg:]

        annotations = dict(zip(arguments, method.args.annotations[first_arg:]))
        for arg in arguments:
            annotation_label = ""
            ann = annotations.get(arg)
            if ann:
                annotation_label = get_annotation_label(ann)
            annotations[arg] = annotation_label

        return [
            f"{arg.name}: {ann}" if ann else f"{arg.name}"
            for arg, ann in annotations.items()
        ]

    def generate(self, outputfile: str) -> None:
        """Generate and save the final outputfile."""
        self._close_graph()
        with open(outputfile, "w", encoding="utf-8") as outfile:
            outfile.writelines(self.lines)

    @abstractmethod
    def _close_graph(self) -> None:
        """Emit the lines needed to properly close the graph."""
