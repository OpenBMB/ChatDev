# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import collections
from typing import TYPE_CHECKING

from astroid.context import _invalidate_cache

if TYPE_CHECKING:
    from astroid import NodeNG


class TransformVisitor:
    """A visitor for handling transforms.

    The standard approach of using it is to call
    :meth:`~visit` with an *astroid* module and the class
    will take care of the rest, walking the tree and running the
    transforms for each encountered node.

    Based on its usage in AstroidManager.brain, it should not be reinstantiated.
    """

    def __init__(self):
        self.transforms = collections.defaultdict(list)

    def _transform(self, node: NodeNG) -> NodeNG:
        """Call matching transforms for the given node if any and return the
        transformed node.
        """
        cls = node.__class__

        transforms = self.transforms[cls]
        for transform_func, predicate in transforms:
            if predicate is None or predicate(node):
                ret = transform_func(node)
                # if the transformation function returns something, it's
                # expected to be a replacement for the node
                if ret is not None:
                    _invalidate_cache()
                    node = ret
                if ret.__class__ != cls:
                    # Can no longer apply the rest of the transforms.
                    break
        return node

    def _visit(self, node):
        if hasattr(node, "_astroid_fields"):
            for name in node._astroid_fields:
                value = getattr(node, name)
                visited = self._visit_generic(value)
                if visited != value:
                    setattr(node, name, visited)
        return self._transform(node)

    def _visit_generic(self, node):
        if isinstance(node, list):
            return [self._visit_generic(child) for child in node]
        if isinstance(node, tuple):
            return tuple(self._visit_generic(child) for child in node)
        if not node or isinstance(node, str):
            return node

        return self._visit(node)

    def register_transform(self, node_class, transform, predicate=None) -> None:
        """Register `transform(node)` function to be applied on the given
        astroid's `node_class` if `predicate` is None or returns true
        when called with the node as argument.

        The transform function may return a value which is then used to
        substitute the original node in the tree.
        """
        self.transforms[node_class].append((transform, predicate))

    def unregister_transform(self, node_class, transform, predicate=None) -> None:
        """Unregister the given transform."""
        self.transforms[node_class].remove((transform, predicate))

    def visit(self, module):
        """Walk the given astroid *tree* and transform each encountered node.

        Only the nodes which have transforms registered will actually
        be replaced or changed.
        """
        return self._visit(module)
