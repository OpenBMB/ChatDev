# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""This module contains some base nodes that can be inherited for the different nodes.

Previously these were called Mixin nodes.
"""

from __future__ import annotations

import itertools
import sys
from collections.abc import Iterator
from typing import TYPE_CHECKING, ClassVar

from astroid import decorators
from astroid.exceptions import AttributeInferenceError
from astroid.nodes.node_ng import NodeNG

if TYPE_CHECKING:
    from astroid import nodes

if sys.version_info >= (3, 8):
    from functools import cached_property
else:
    from astroid.decorators import cachedproperty as cached_property


class Statement(NodeNG):
    """Statement node adding a few attributes.

    NOTE: This class is part of the public API of 'astroid.nodes'.
    """

    is_statement = True
    """Whether this node indicates a statement."""

    def next_sibling(self):
        """The next sibling statement node.

        :returns: The next sibling statement node.
        :rtype: NodeNG or None
        """
        stmts = self.parent.child_sequence(self)
        index = stmts.index(self)
        try:
            return stmts[index + 1]
        except IndexError:
            return None

    def previous_sibling(self):
        """The previous sibling statement.

        :returns: The previous sibling statement node.
        :rtype: NodeNG or None
        """
        stmts = self.parent.child_sequence(self)
        index = stmts.index(self)
        if index >= 1:
            return stmts[index - 1]
        return None


class NoChildrenNode(NodeNG):
    """Base nodes for nodes with no children, e.g. Pass."""

    def get_children(self) -> Iterator[NodeNG]:
        yield from ()


class FilterStmtsBaseNode(NodeNG):
    """Base node for statement filtering and assignment type."""

    def _get_filtered_stmts(self, _, node, _stmts, mystmt: Statement | None):
        """Method used in _filter_stmts to get statements and trigger break."""
        if self.statement(future=True) is mystmt:
            # original node's statement is the assignment, only keep
            # current node (gen exp, list comp)
            return [node], True
        return _stmts, False

    def assign_type(self):
        return self


class AssignTypeNode(NodeNG):
    """Base node for nodes that can 'assign' such as AnnAssign."""

    def assign_type(self):
        return self

    def _get_filtered_stmts(self, lookup_node, node, _stmts, mystmt: Statement | None):
        """Method used in filter_stmts."""
        if self is mystmt:
            return _stmts, True
        if self.statement(future=True) is mystmt:
            # original node's statement is the assignment, only keep
            # current node (gen exp, list comp)
            return [node], True
        return _stmts, False


class ParentAssignNode(AssignTypeNode):
    """Base node for nodes whose assign_type is determined by the parent node."""

    def assign_type(self):
        return self.parent.assign_type()


class ImportNode(FilterStmtsBaseNode, NoChildrenNode, Statement):
    """Base node for From and Import Nodes."""

    modname: str | None
    """The module that is being imported from.

    This is ``None`` for relative imports.
    """

    names: list[tuple[str, str | None]]
    """What is being imported from the module.

    Each entry is a :class:`tuple` of the name being imported,
    and the alias that the name is assigned to (if any).
    """

    def _infer_name(self, frame, name):
        return name

    def do_import_module(self, modname: str | None = None) -> nodes.Module:
        """Return the ast for a module whose name is <modname> imported by <self>."""
        mymodule = self.root()
        level: int | None = getattr(self, "level", None)  # Import has no level
        if modname is None:
            modname = self.modname
        # If the module ImportNode is importing is a module with the same name
        # as the file that contains the ImportNode we don't want to use the cache
        # to make sure we use the import system to get the correct module.
        # pylint: disable-next=no-member # pylint doesn't recognize type of mymodule
        if mymodule.relative_to_absolute_name(modname, level) == mymodule.name:
            use_cache = False
        else:
            use_cache = True

        # pylint: disable-next=no-member # pylint doesn't recognize type of mymodule
        return mymodule.import_module(
            modname,
            level=level,
            relative_only=bool(level and level >= 1),
            use_cache=use_cache,
        )

    def real_name(self, asname: str) -> str:
        """Get name from 'as' name."""
        for name, _asname in self.names:
            if name == "*":
                return asname
            if not _asname:
                name = name.split(".", 1)[0]
                _asname = name
            if asname == _asname:
                return name
        raise AttributeInferenceError(
            "Could not find original name for {attribute} in {target!r}",
            target=self,
            attribute=asname,
        )


class MultiLineBlockNode(NodeNG):
    """Base node for multi-line blocks, e.g. For and FunctionDef.

    Note that this does not apply to every node with a `body` field.
    For instance, an If node has a multi-line body, but the body of an
    IfExpr is not multi-line, and hence cannot contain Return nodes,
    Assign nodes, etc.
    """

    _multi_line_block_fields: ClassVar[tuple[str, ...]] = ()

    @cached_property
    def _multi_line_blocks(self):
        return tuple(getattr(self, field) for field in self._multi_line_block_fields)

    def _get_return_nodes_skip_functions(self):
        for block in self._multi_line_blocks:
            for child_node in block:
                if child_node.is_function:
                    continue
                yield from child_node._get_return_nodes_skip_functions()

    def _get_yield_nodes_skip_lambdas(self):
        for block in self._multi_line_blocks:
            for child_node in block:
                if child_node.is_lambda:
                    continue
                yield from child_node._get_yield_nodes_skip_lambdas()

    @decorators.cached
    def _get_assign_nodes(self):
        children_assign_nodes = (
            child_node._get_assign_nodes()
            for block in self._multi_line_blocks
            for child_node in block
        )
        return list(itertools.chain.from_iterable(children_assign_nodes))


class MultiLineWithElseBlockNode(MultiLineBlockNode):
    """Base node for multi-line blocks that can have else statements."""

    @cached_property
    def blockstart_tolineno(self):
        return self.lineno

    def _elsed_block_range(self, lineno, orelse, last=None):
        """Handle block line numbers range for try/finally, for, if and while
        statements.
        """
        if lineno == self.fromlineno:
            return lineno, lineno
        if orelse:
            if lineno >= orelse[0].fromlineno:
                return lineno, orelse[-1].tolineno
            return lineno, orelse[0].fromlineno - 1
        return lineno, last or self.tolineno
