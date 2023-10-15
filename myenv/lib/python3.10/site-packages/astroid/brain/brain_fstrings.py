# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import collections.abc
from typing import TypeVar

from astroid import nodes
from astroid.manager import AstroidManager

_NodeT = TypeVar("_NodeT", bound=nodes.NodeNG)


def _clone_node_with_lineno(
    node: _NodeT, parent: nodes.NodeNG, lineno: int | None
) -> _NodeT:
    cls = node.__class__
    other_fields = node._other_fields
    _astroid_fields = node._astroid_fields
    init_params = {"lineno": lineno, "col_offset": node.col_offset, "parent": parent}
    postinit_params = {param: getattr(node, param) for param in _astroid_fields}
    if other_fields:
        init_params.update({param: getattr(node, param) for param in other_fields})
    new_node = cls(**init_params)
    if hasattr(node, "postinit") and _astroid_fields:
        for param, child in postinit_params.items():
            if child and not isinstance(child, collections.abc.Sequence):
                cloned_child = _clone_node_with_lineno(
                    node=child, lineno=new_node.lineno, parent=new_node
                )
                postinit_params[param] = cloned_child
        new_node.postinit(**postinit_params)
    return new_node


def _transform_formatted_value(  # pylint: disable=inconsistent-return-statements
    node: nodes.FormattedValue,
) -> nodes.FormattedValue | None:
    if node.value and node.value.lineno == 1:
        if node.lineno != node.value.lineno:
            new_node = nodes.FormattedValue(
                lineno=node.lineno, col_offset=node.col_offset, parent=node.parent
            )
            new_value = _clone_node_with_lineno(
                node=node.value, lineno=node.lineno, parent=new_node
            )
            new_node.postinit(
                value=new_value,
                conversion=node.conversion,
                format_spec=node.format_spec,
            )
            return new_node


# TODO: this fix tries to *patch* http://bugs.python.org/issue29051
# The problem is that FormattedValue.value, which is a Name node,
# has wrong line numbers, usually 1. This creates problems for pylint,
# which expects correct line numbers for things such as message control.
AstroidManager().register_transform(nodes.FormattedValue, _transform_formatted_value)
