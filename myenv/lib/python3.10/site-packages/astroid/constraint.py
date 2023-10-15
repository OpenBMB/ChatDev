# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""Classes representing different types of constraints on inference values."""
from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Union

from astroid import bases, nodes, util
from astroid.typing import InferenceResult

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

_NameNodes = Union[nodes.AssignAttr, nodes.Attribute, nodes.AssignName, nodes.Name]


class Constraint(ABC):
    """Represents a single constraint on a variable."""

    def __init__(self, node: nodes.NodeNG, negate: bool) -> None:
        self.node = node
        """The node that this constraint applies to."""
        self.negate = negate
        """True if this constraint is negated. E.g., "is not" instead of "is"."""

    @classmethod
    @abstractmethod
    def match(
        cls: type[Self], node: _NameNodes, expr: nodes.NodeNG, negate: bool = False
    ) -> Self | None:
        """Return a new constraint for node matched from expr, if expr matches
        the constraint pattern.

        If negate is True, negate the constraint.
        """

    @abstractmethod
    def satisfied_by(self, inferred: InferenceResult) -> bool:
        """Return True if this constraint is satisfied by the given inferred value."""


class NoneConstraint(Constraint):
    """Represents an "is None" or "is not None" constraint."""

    CONST_NONE: nodes.Const = nodes.Const(None)

    @classmethod
    def match(
        cls: type[Self], node: _NameNodes, expr: nodes.NodeNG, negate: bool = False
    ) -> Self | None:
        """Return a new constraint for node matched from expr, if expr matches
        the constraint pattern.

        Negate the constraint based on the value of negate.
        """
        if isinstance(expr, nodes.Compare) and len(expr.ops) == 1:
            left = expr.left
            op, right = expr.ops[0]
            if op in {"is", "is not"} and (
                _matches(left, node) and _matches(right, cls.CONST_NONE)
            ):
                negate = (op == "is" and negate) or (op == "is not" and not negate)
                return cls(node=node, negate=negate)

        return None

    def satisfied_by(self, inferred: InferenceResult) -> bool:
        """Return True if this constraint is satisfied by the given inferred value."""
        # Assume true if uninferable
        if isinstance(inferred, util.UninferableBase):
            return True

        # Return the XOR of self.negate and matches(inferred, self.CONST_NONE)
        return self.negate ^ _matches(inferred, self.CONST_NONE)


def get_constraints(
    expr: _NameNodes, frame: nodes.LocalsDictNodeNG
) -> dict[nodes.If, set[Constraint]]:
    """Returns the constraints for the given expression.

    The returned dictionary maps the node where the constraint was generated to the
    corresponding constraint(s).

    Constraints are computed statically by analysing the code surrounding expr.
    Currently this only supports constraints generated from if conditions.
    """
    current_node: nodes.NodeNG | None = expr
    constraints_mapping: dict[nodes.If, set[Constraint]] = {}
    while current_node is not None and current_node is not frame:
        parent = current_node.parent
        if isinstance(parent, nodes.If):
            branch, _ = parent.locate_child(current_node)
            constraints: set[Constraint] | None = None
            if branch == "body":
                constraints = set(_match_constraint(expr, parent.test))
            elif branch == "orelse":
                constraints = set(_match_constraint(expr, parent.test, invert=True))

            if constraints:
                constraints_mapping[parent] = constraints
        current_node = parent

    return constraints_mapping


ALL_CONSTRAINT_CLASSES = frozenset((NoneConstraint,))
"""All supported constraint types."""


def _matches(node1: nodes.NodeNG | bases.Proxy, node2: nodes.NodeNG) -> bool:
    """Returns True if the two nodes match."""
    if isinstance(node1, nodes.Name) and isinstance(node2, nodes.Name):
        return node1.name == node2.name
    if isinstance(node1, nodes.Attribute) and isinstance(node2, nodes.Attribute):
        return node1.attrname == node2.attrname and _matches(node1.expr, node2.expr)
    if isinstance(node1, nodes.Const) and isinstance(node2, nodes.Const):
        return node1.value == node2.value

    return False


def _match_constraint(
    node: _NameNodes, expr: nodes.NodeNG, invert: bool = False
) -> Iterator[Constraint]:
    """Yields all constraint patterns for node that match."""
    for constraint_cls in ALL_CONSTRAINT_CLASSES:
        constraint = constraint_cls.match(node, expr, invert)
        if constraint:
            yield constraint
