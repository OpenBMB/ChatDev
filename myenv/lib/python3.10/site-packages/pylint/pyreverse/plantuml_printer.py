# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Class to generate files in dot format and image formats supported by Graphviz."""

from __future__ import annotations

from pylint.pyreverse.printer import EdgeType, Layout, NodeProperties, NodeType, Printer
from pylint.pyreverse.utils import get_annotation_label


class PlantUmlPrinter(Printer):
    """Printer for PlantUML diagrams."""

    DEFAULT_COLOR = "black"

    NODES: dict[NodeType, str] = {
        NodeType.CLASS: "class",
        NodeType.INTERFACE: "class",
        NodeType.PACKAGE: "package",
    }
    ARROWS: dict[EdgeType, str] = {
        EdgeType.INHERITS: "--|>",
        EdgeType.IMPLEMENTS: "..|>",
        EdgeType.ASSOCIATION: "--*",
        EdgeType.AGGREGATION: "--o",
        EdgeType.USES: "-->",
    }

    def _open_graph(self) -> None:
        """Emit the header lines."""
        self.emit("@startuml " + self.title)
        if not self.use_automatic_namespace:
            self.emit("set namespaceSeparator none")
        if self.layout:
            if self.layout is Layout.LEFT_TO_RIGHT:
                self.emit("left to right direction")
            elif self.layout is Layout.TOP_TO_BOTTOM:
                self.emit("top to bottom direction")
            else:
                raise ValueError(
                    f"Unsupported layout {self.layout}. PlantUmlPrinter only "
                    "supports left to right and top to bottom layout."
                )

    def emit_node(
        self,
        name: str,
        type_: NodeType,
        properties: NodeProperties | None = None,
    ) -> None:
        """Create a new node.

        Nodes can be classes, packages, participants etc.
        """
        if properties is None:
            properties = NodeProperties(label=name)
        stereotype = " << interface >>" if type_ is NodeType.INTERFACE else ""
        nodetype = self.NODES[type_]
        if properties.color and properties.color != self.DEFAULT_COLOR:
            color = f" #{properties.color}"
        else:
            color = ""
        body = []
        if properties.attrs:
            body.extend(properties.attrs)
        if properties.methods:
            for func in properties.methods:
                args = self._get_method_arguments(func)
                line = "{abstract}" if func.is_abstract() else ""
                line += f"{func.name}({', '.join(args)})"
                if func.returns:
                    line += " -> " + get_annotation_label(func.returns)
                body.append(line)
        label = properties.label if properties.label is not None else name
        if properties.fontcolor and properties.fontcolor != self.DEFAULT_COLOR:
            label = f"<color:{properties.fontcolor}>{label}</color>"
        self.emit(f'{nodetype} "{label}" as {name}{stereotype}{color} {{')
        self._inc_indent()
        for line in body:
            self.emit(line)
        self._dec_indent()
        self.emit("}")

    def emit_edge(
        self,
        from_node: str,
        to_node: str,
        type_: EdgeType,
        label: str | None = None,
    ) -> None:
        """Create an edge from one node to another to display relationships."""
        edge = f"{from_node} {self.ARROWS[type_]} {to_node}"
        if label:
            edge += f" : {label}"
        self.emit(edge)

    def _close_graph(self) -> None:
        """Emit the lines needed to properly close the graph."""
        self.emit("@enduml")
