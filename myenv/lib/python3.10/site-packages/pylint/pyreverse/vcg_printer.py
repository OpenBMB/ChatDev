# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Functions to generate files readable with George Sander's vcg
(Visualization of Compiler Graphs).

You can download vcg at https://rw4.cs.uni-sb.de/~sander/html/gshome.html
Note that vcg exists as a debian package.
See vcg's documentation for explanation about the different values that
maybe used for the functions parameters.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pylint.pyreverse.printer import EdgeType, Layout, NodeProperties, NodeType, Printer

ATTRS_VAL = {
    "algos": (
        "dfs",
        "tree",
        "minbackward",
        "left_to_right",
        "right_to_left",
        "top_to_bottom",
        "bottom_to_top",
        "maxdepth",
        "maxdepthslow",
        "mindepth",
        "mindepthslow",
        "mindegree",
        "minindegree",
        "minoutdegree",
        "maxdegree",
        "maxindegree",
        "maxoutdegree",
    ),
    "booleans": ("yes", "no"),
    "colors": (
        "black",
        "white",
        "blue",
        "red",
        "green",
        "yellow",
        "magenta",
        "lightgrey",
        "cyan",
        "darkgrey",
        "darkblue",
        "darkred",
        "darkgreen",
        "darkyellow",
        "darkmagenta",
        "darkcyan",
        "gold",
        "lightblue",
        "lightred",
        "lightgreen",
        "lightyellow",
        "lightmagenta",
        "lightcyan",
        "lilac",
        "turquoise",
        "aquamarine",
        "khaki",
        "purple",
        "yellowgreen",
        "pink",
        "orange",
        "orchid",
    ),
    "shapes": ("box", "ellipse", "rhomb", "triangle"),
    "textmodes": ("center", "left_justify", "right_justify"),
    "arrowstyles": ("solid", "line", "none"),
    "linestyles": ("continuous", "dashed", "dotted", "invisible"),
}

# meaning of possible values:
#   O    -> string
#   1    -> int
#   list -> value in list
GRAPH_ATTRS = {
    "title": 0,
    "label": 0,
    "color": ATTRS_VAL["colors"],
    "textcolor": ATTRS_VAL["colors"],
    "bordercolor": ATTRS_VAL["colors"],
    "width": 1,
    "height": 1,
    "borderwidth": 1,
    "textmode": ATTRS_VAL["textmodes"],
    "shape": ATTRS_VAL["shapes"],
    "shrink": 1,
    "stretch": 1,
    "orientation": ATTRS_VAL["algos"],
    "vertical_order": 1,
    "horizontal_order": 1,
    "xspace": 1,
    "yspace": 1,
    "layoutalgorithm": ATTRS_VAL["algos"],
    "late_edge_labels": ATTRS_VAL["booleans"],
    "display_edge_labels": ATTRS_VAL["booleans"],
    "dirty_edge_labels": ATTRS_VAL["booleans"],
    "finetuning": ATTRS_VAL["booleans"],
    "manhattan_edges": ATTRS_VAL["booleans"],
    "smanhattan_edges": ATTRS_VAL["booleans"],
    "port_sharing": ATTRS_VAL["booleans"],
    "edges": ATTRS_VAL["booleans"],
    "nodes": ATTRS_VAL["booleans"],
    "splines": ATTRS_VAL["booleans"],
}
NODE_ATTRS = {
    "title": 0,
    "label": 0,
    "color": ATTRS_VAL["colors"],
    "textcolor": ATTRS_VAL["colors"],
    "bordercolor": ATTRS_VAL["colors"],
    "width": 1,
    "height": 1,
    "borderwidth": 1,
    "textmode": ATTRS_VAL["textmodes"],
    "shape": ATTRS_VAL["shapes"],
    "shrink": 1,
    "stretch": 1,
    "vertical_order": 1,
    "horizontal_order": 1,
}
EDGE_ATTRS = {
    "sourcename": 0,
    "targetname": 0,
    "label": 0,
    "linestyle": ATTRS_VAL["linestyles"],
    "class": 1,
    "thickness": 0,
    "color": ATTRS_VAL["colors"],
    "textcolor": ATTRS_VAL["colors"],
    "arrowcolor": ATTRS_VAL["colors"],
    "backarrowcolor": ATTRS_VAL["colors"],
    "arrowsize": 1,
    "backarrowsize": 1,
    "arrowstyle": ATTRS_VAL["arrowstyles"],
    "backarrowstyle": ATTRS_VAL["arrowstyles"],
    "textmode": ATTRS_VAL["textmodes"],
    "priority": 1,
    "anchor": 1,
    "horizontal_order": 1,
}
SHAPES: dict[NodeType, str] = {
    NodeType.PACKAGE: "box",
    NodeType.CLASS: "box",
    NodeType.INTERFACE: "ellipse",
}
# pylint: disable-next=consider-using-namedtuple-or-dataclass
ARROWS: dict[EdgeType, dict[str, str | int]] = {
    EdgeType.USES: {
        "arrowstyle": "solid",
        "backarrowstyle": "none",
        "backarrowsize": 0,
    },
    EdgeType.INHERITS: {
        "arrowstyle": "solid",
        "backarrowstyle": "none",
        "backarrowsize": 10,
    },
    EdgeType.IMPLEMENTS: {
        "arrowstyle": "solid",
        "backarrowstyle": "none",
        "linestyle": "dotted",
        "backarrowsize": 10,
    },
    EdgeType.ASSOCIATION: {
        "arrowstyle": "solid",
        "backarrowstyle": "none",
        "textcolor": "green",
    },
    EdgeType.AGGREGATION: {
        "arrowstyle": "solid",
        "backarrowstyle": "none",
        "textcolor": "green",
    },
}
ORIENTATION: dict[Layout, str] = {
    Layout.LEFT_TO_RIGHT: "left_to_right",
    Layout.RIGHT_TO_LEFT: "right_to_left",
    Layout.TOP_TO_BOTTOM: "top_to_bottom",
    Layout.BOTTOM_TO_TOP: "bottom_to_top",
}

# Misc utilities ###############################################################


class VCGPrinter(Printer):
    def _open_graph(self) -> None:
        """Emit the header lines."""
        self.emit("graph:{\n")
        self._inc_indent()
        self._write_attributes(
            GRAPH_ATTRS,
            title=self.title,
            layoutalgorithm="dfs",
            late_edge_labels="yes",
            port_sharing="no",
            manhattan_edges="yes",
        )
        if self.layout:
            self._write_attributes(GRAPH_ATTRS, orientation=ORIENTATION[self.layout])

    def _close_graph(self) -> None:
        """Emit the lines needed to properly close the graph."""
        self._dec_indent()
        self.emit("}")

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
        elif properties.label is None:
            properties.label = name
        self.emit(f'node: {{title:"{name}"', force_newline=False)
        self._write_attributes(
            NODE_ATTRS,
            label=self._build_label_for_node(properties),
            shape=SHAPES[type_],
        )
        self.emit("}")

    @staticmethod
    def _build_label_for_node(properties: NodeProperties) -> str:
        fontcolor = "\f09" if properties.fontcolor == "red" else ""
        label = rf"\fb{fontcolor}{properties.label}\fn"
        if properties.attrs is None and properties.methods is None:
            # return a compact form which only displays the classname in a box
            return label
        attrs = properties.attrs or []
        methods = properties.methods or []
        method_names = [func.name for func in methods]
        # box width for UML like diagram
        maxlen = max(len(name) for name in [properties.label] + method_names + attrs)
        line = "_" * (maxlen + 2)
        label = rf"{label}\n\f{line}"
        for attr in attrs:
            label = rf"{label}\n\f08{attr}"
        if attrs:
            label = rf"{label}\n\f{line}"
        for func in method_names:
            label = rf"{label}\n\f10{func}()"
        return label

    def emit_edge(
        self,
        from_node: str,
        to_node: str,
        type_: EdgeType,
        label: str | None = None,
    ) -> None:
        """Create an edge from one node to another to display relationships."""
        self.emit(
            f'edge: {{sourcename:"{from_node}" targetname:"{to_node}"',
            force_newline=False,
        )
        attributes = ARROWS[type_]
        if label:
            attributes["label"] = label
        self._write_attributes(
            EDGE_ATTRS,
            **attributes,
        )
        self.emit("}")

    def _write_attributes(
        self, attributes_dict: Mapping[str, Any], **args: Any
    ) -> None:
        """Write graph, node or edge attributes."""
        for key, value in args.items():
            try:
                _type = attributes_dict[key]
            except KeyError as e:
                raise AttributeError(
                    f"no such attribute {key}\npossible attributes are {attributes_dict.keys()}"
                ) from e

            if not _type:
                self.emit(f'{key}:"{value}"\n')
            elif _type == 1:
                self.emit(f"{key}:{int(value)}\n")
            elif value in _type:
                self.emit(f"{key}:{value}\n")
            else:
                raise ValueError(
                    f"value {value} isn't correct for attribute {key} correct values are {type}"
                )
