# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Utilities for creating VCG and Dot diagrams."""

from __future__ import annotations

import argparse
import itertools
import os
from collections.abc import Iterable

from astroid import modutils, nodes

from pylint.pyreverse.diagrams import (
    ClassDiagram,
    ClassEntity,
    DiagramEntity,
    PackageDiagram,
    PackageEntity,
)
from pylint.pyreverse.printer import EdgeType, NodeProperties, NodeType, Printer
from pylint.pyreverse.printer_factory import get_printer_for_filetype
from pylint.pyreverse.utils import is_exception


class DiagramWriter:
    """Base class for writing project diagrams."""

    def __init__(self, config: argparse.Namespace) -> None:
        self.config = config
        self.printer_class = get_printer_for_filetype(self.config.output_format)
        self.printer: Printer  # defined in set_printer
        self.file_name = ""  # defined in set_printer
        self.depth = self.config.max_color_depth
        # default colors are an adaption of the seaborn colorblind palette
        self.available_colors = itertools.cycle(self.config.color_palette)
        self.used_colors: dict[str, str] = {}

    def write(self, diadefs: Iterable[ClassDiagram | PackageDiagram]) -> None:
        """Write files for <project> according to <diadefs>."""
        for diagram in diadefs:
            basename = diagram.title.strip().replace(" ", "_")
            file_name = f"{basename}.{self.config.output_format}"
            if os.path.exists(self.config.output_directory):
                file_name = os.path.join(self.config.output_directory, file_name)
            self.set_printer(file_name, basename)
            if isinstance(diagram, PackageDiagram):
                self.write_packages(diagram)
            else:
                self.write_classes(diagram)
            self.save()

    def write_packages(self, diagram: PackageDiagram) -> None:
        """Write a package diagram."""
        # sorted to get predictable (hence testable) results
        for module in sorted(diagram.modules(), key=lambda x: x.title):
            module.fig_id = module.node.qname()
            self.printer.emit_node(
                module.fig_id,
                type_=NodeType.PACKAGE,
                properties=self.get_package_properties(module),
            )
        # package dependencies
        for rel in diagram.get_relationships("depends"):
            self.printer.emit_edge(
                rel.from_object.fig_id,
                rel.to_object.fig_id,
                type_=EdgeType.USES,
            )

    def write_classes(self, diagram: ClassDiagram) -> None:
        """Write a class diagram."""
        # sorted to get predictable (hence testable) results
        for obj in sorted(diagram.objects, key=lambda x: x.title):  # type: ignore[no-any-return]
            obj.fig_id = obj.node.qname()
            type_ = NodeType.INTERFACE if obj.shape == "interface" else NodeType.CLASS
            self.printer.emit_node(
                obj.fig_id, type_=type_, properties=self.get_class_properties(obj)
            )
        # inheritance links
        for rel in diagram.get_relationships("specialization"):
            self.printer.emit_edge(
                rel.from_object.fig_id,
                rel.to_object.fig_id,
                type_=EdgeType.INHERITS,
            )
        # implementation links
        for rel in diagram.get_relationships("implements"):
            self.printer.emit_edge(
                rel.from_object.fig_id,
                rel.to_object.fig_id,
                type_=EdgeType.IMPLEMENTS,
            )
        # generate associations
        for rel in diagram.get_relationships("association"):
            self.printer.emit_edge(
                rel.from_object.fig_id,
                rel.to_object.fig_id,
                label=rel.name,
                type_=EdgeType.ASSOCIATION,
            )
        # generate aggregations
        for rel in diagram.get_relationships("aggregation"):
            self.printer.emit_edge(
                rel.from_object.fig_id,
                rel.to_object.fig_id,
                label=rel.name,
                type_=EdgeType.AGGREGATION,
            )

    def set_printer(self, file_name: str, basename: str) -> None:
        """Set printer."""
        self.printer = self.printer_class(basename)
        self.file_name = file_name

    def get_package_properties(self, obj: PackageEntity) -> NodeProperties:
        """Get label and shape for packages."""
        return NodeProperties(
            label=obj.title,
            color=self.get_shape_color(obj) if self.config.colorized else "black",
        )

    def get_class_properties(self, obj: ClassEntity) -> NodeProperties:
        """Get label and shape for classes."""
        properties = NodeProperties(
            label=obj.title,
            attrs=obj.attrs if not self.config.only_classnames else None,
            methods=obj.methods if not self.config.only_classnames else None,
            fontcolor="red" if is_exception(obj.node) else "black",
            color=self.get_shape_color(obj) if self.config.colorized else "black",
        )
        return properties

    def get_shape_color(self, obj: DiagramEntity) -> str:
        """Get shape color."""
        qualified_name = obj.node.qname()
        if modutils.is_stdlib_module(qualified_name.split(".", maxsplit=1)[0]):
            return "grey"
        if isinstance(obj.node, nodes.ClassDef):
            package = qualified_name.rsplit(".", maxsplit=2)[0]
        elif obj.node.package:
            package = qualified_name
        else:
            package = qualified_name.rsplit(".", maxsplit=1)[0]
        base_name = ".".join(package.split(".", self.depth)[: self.depth])
        if base_name not in self.used_colors:
            self.used_colors[base_name] = next(self.available_colors)
        return self.used_colors[base_name]

    def save(self) -> None:
        """Write to disk."""
        self.printer.generate(self.file_name)
