# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Diagram objects."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import astroid
from astroid import nodes, util

from pylint.checkers.utils import decorated_with_property
from pylint.pyreverse.utils import FilterMixIn, is_interface


class Figure:
    """Base class for counter handling."""

    def __init__(self) -> None:
        self.fig_id: str = ""


class Relationship(Figure):
    """A relationship from an object in the diagram to another."""

    def __init__(
        self,
        from_object: DiagramEntity,
        to_object: DiagramEntity,
        relation_type: str,
        name: str | None = None,
    ):
        super().__init__()
        self.from_object = from_object
        self.to_object = to_object
        self.type = relation_type
        self.name = name


class DiagramEntity(Figure):
    """A diagram object, i.e. a label associated to an astroid node."""

    default_shape = ""

    def __init__(
        self, title: str = "No name", node: nodes.NodeNG | None = None
    ) -> None:
        super().__init__()
        self.title = title
        self.node: nodes.NodeNG = node if node else nodes.NodeNG()
        self.shape = self.default_shape


class PackageEntity(DiagramEntity):
    """A diagram object representing a package."""

    default_shape = "package"


class ClassEntity(DiagramEntity):
    """A diagram object representing a class."""

    default_shape = "class"

    def __init__(self, title: str, node: nodes.ClassDef) -> None:
        super().__init__(title=title, node=node)
        self.attrs: list[str] = []
        self.methods: list[nodes.FunctionDef] = []


class ClassDiagram(Figure, FilterMixIn):
    """Main class diagram handling."""

    TYPE = "class"

    def __init__(self, title: str, mode: str) -> None:
        FilterMixIn.__init__(self, mode)
        Figure.__init__(self)
        self.title = title
        # TODO: Specify 'Any' after refactor of `DiagramEntity`
        self.objects: list[Any] = []
        self.relationships: dict[str, list[Relationship]] = {}
        self._nodes: dict[nodes.NodeNG, DiagramEntity] = {}

    def get_relationships(self, role: str) -> Iterable[Relationship]:
        # sorted to get predictable (hence testable) results
        return sorted(
            self.relationships.get(role, ()),
            key=lambda x: (x.from_object.fig_id, x.to_object.fig_id),
        )

    def add_relationship(
        self,
        from_object: DiagramEntity,
        to_object: DiagramEntity,
        relation_type: str,
        name: str | None = None,
    ) -> None:
        """Create a relationship."""
        rel = Relationship(from_object, to_object, relation_type, name)
        self.relationships.setdefault(relation_type, []).append(rel)

    def get_relationship(
        self, from_object: DiagramEntity, relation_type: str
    ) -> Relationship:
        """Return a relationship or None."""
        for rel in self.relationships.get(relation_type, ()):
            if rel.from_object is from_object:
                return rel
        raise KeyError(relation_type)

    def get_attrs(self, node: nodes.ClassDef) -> list[str]:
        """Return visible attributes, possibly with class name."""
        attrs = []
        properties = [
            (n, m)
            for n, m in node.items()
            if isinstance(m, nodes.FunctionDef) and decorated_with_property(m)
        ]
        for node_name, associated_nodes in (
            list(node.instance_attrs_type.items())
            + list(node.locals_type.items())
            + properties
        ):
            if not self.show_attr(node_name):
                continue
            names = self.class_names(associated_nodes)
            if names:
                node_name = f"{node_name} : {', '.join(names)}"
            attrs.append(node_name)
        return sorted(attrs)

    def get_methods(self, node: nodes.ClassDef) -> list[nodes.FunctionDef]:
        """Return visible methods."""
        methods = [
            m
            for m in node.values()
            if isinstance(m, nodes.FunctionDef)
            and not isinstance(m, astroid.objects.Property)
            and not decorated_with_property(m)
            and self.show_attr(m.name)
        ]
        return sorted(methods, key=lambda n: n.name)  # type: ignore[no-any-return]

    def add_object(self, title: str, node: nodes.ClassDef) -> None:
        """Create a diagram object."""
        assert node not in self._nodes
        ent = ClassEntity(title, node)
        self._nodes[node] = ent
        self.objects.append(ent)

    def class_names(self, nodes_lst: Iterable[nodes.NodeNG]) -> list[str]:
        """Return class names if needed in diagram."""
        names = []
        for node in nodes_lst:
            if isinstance(node, astroid.Instance):
                node = node._proxied
            if (
                isinstance(
                    node, (nodes.ClassDef, nodes.Name, nodes.Subscript, nodes.BinOp)
                )
                and hasattr(node, "name")
                and not self.has_node(node)
            ):
                if node.name not in names:
                    node_name = node.name
                    names.append(node_name)
        return names

    def has_node(self, node: nodes.NodeNG) -> bool:
        """Return true if the given node is included in the diagram."""
        return node in self._nodes

    def object_from_node(self, node: nodes.NodeNG) -> DiagramEntity:
        """Return the diagram object mapped to node."""
        return self._nodes[node]

    def classes(self) -> list[ClassEntity]:
        """Return all class nodes in the diagram."""
        return [o for o in self.objects if isinstance(o, ClassEntity)]

    def classe(self, name: str) -> ClassEntity:
        """Return a class by its name, raise KeyError if not found."""
        for klass in self.classes():
            if klass.node.name == name:
                return klass
        raise KeyError(name)

    def extract_relationships(self) -> None:
        """Extract relationships between nodes in the diagram."""
        for obj in self.classes():
            node = obj.node
            obj.attrs = self.get_attrs(node)
            obj.methods = self.get_methods(node)
            # shape
            if is_interface(node):
                obj.shape = "interface"
            else:
                obj.shape = "class"
            # inheritance link
            for par_node in node.ancestors(recurs=False):
                try:
                    par_obj = self.object_from_node(par_node)
                    self.add_relationship(obj, par_obj, "specialization")
                except KeyError:
                    continue
            # implements link
            for impl_node in node.implements:
                try:
                    impl_obj = self.object_from_node(impl_node)
                    self.add_relationship(obj, impl_obj, "implements")
                except KeyError:
                    continue

            # associations & aggregations links
            for name, values in list(node.aggregations_type.items()):
                for value in values:
                    self.assign_association_relationship(
                        value, obj, name, "aggregation"
                    )

            for name, values in list(node.associations_type.items()) + list(
                node.locals_type.items()
            ):
                for value in values:
                    self.assign_association_relationship(
                        value, obj, name, "association"
                    )

    def assign_association_relationship(
        self, value: astroid.NodeNG, obj: ClassEntity, name: str, type_relationship: str
    ) -> None:
        if isinstance(value, util.UninferableBase):
            return
        if isinstance(value, astroid.Instance):
            value = value._proxied
        try:
            associated_obj = self.object_from_node(value)
            self.add_relationship(associated_obj, obj, type_relationship, name)
        except KeyError:
            return


class PackageDiagram(ClassDiagram):
    """Package diagram handling."""

    TYPE = "package"

    def modules(self) -> list[PackageEntity]:
        """Return all module nodes in the diagram."""
        return [o for o in self.objects if isinstance(o, PackageEntity)]

    def module(self, name: str) -> PackageEntity:
        """Return a module by its name, raise KeyError if not found."""
        for mod in self.modules():
            if mod.node.name == name:
                return mod
        raise KeyError(name)

    def add_object(self, title: str, node: nodes.Module) -> None:
        """Create a diagram object."""
        assert node not in self._nodes
        ent = PackageEntity(title, node)
        self._nodes[node] = ent
        self.objects.append(ent)

    def get_module(self, name: str, node: nodes.Module) -> PackageEntity:
        """Return a module by its name, looking also for relative imports;
        raise KeyError if not found.
        """
        for mod in self.modules():
            mod_name = mod.node.name
            if mod_name == name:
                return mod
            # search for fullname of relative import modules
            package = node.root().name
            if mod_name == f"{package}.{name}":
                return mod
            if mod_name == f"{package.rsplit('.', 1)[0]}.{name}":
                return mod
        raise KeyError(name)

    def add_from_depend(self, node: nodes.ImportFrom, from_module: str) -> None:
        """Add dependencies created by from-imports."""
        mod_name = node.root().name
        obj = self.module(mod_name)
        if from_module not in obj.node.depends:
            obj.node.depends.append(from_module)

    def extract_relationships(self) -> None:
        """Extract relationships between nodes in the diagram."""
        super().extract_relationships()
        for class_obj in self.classes():
            # ownership
            try:
                mod = self.object_from_node(class_obj.node.root())
                self.add_relationship(class_obj, mod, "ownership")
            except KeyError:
                continue
        for package_obj in self.modules():
            package_obj.shape = "package"
            # dependencies
            for dep_name in package_obj.node.depends:
                try:
                    dep = self.get_module(dep_name, package_obj.node)
                except KeyError:
                    continue
                self.add_relationship(package_obj, dep, "depends")
