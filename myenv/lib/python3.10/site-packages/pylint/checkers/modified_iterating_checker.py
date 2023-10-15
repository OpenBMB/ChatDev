# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

from typing import TYPE_CHECKING

from astroid import nodes

from pylint import checkers, interfaces
from pylint.checkers import utils

if TYPE_CHECKING:
    from pylint.lint import PyLinter


_LIST_MODIFIER_METHODS = {"append", "remove"}
_SET_MODIFIER_METHODS = {"add", "remove"}


class ModifiedIterationChecker(checkers.BaseChecker):
    """Checks for modified iterators in for loops iterations.

    Currently supports `for` loops for Sets, Dictionaries and Lists.
    """

    name = "modified_iteration"

    msgs = {
        "W4701": (
            "Iterated list '%s' is being modified inside for loop body, consider iterating through a copy of it "
            "instead.",
            "modified-iterating-list",
            "Emitted when items are added or removed to a list being iterated through. "
            "Doing so can result in unexpected behaviour, that is why it is preferred to use a copy of the list.",
        ),
        "E4702": (
            "Iterated dict '%s' is being modified inside for loop body, iterate through a copy of it instead.",
            "modified-iterating-dict",
            "Emitted when items are added or removed to a dict being iterated through. "
            "Doing so raises a RuntimeError.",
        ),
        "E4703": (
            "Iterated set '%s' is being modified inside for loop body, iterate through a copy of it instead.",
            "modified-iterating-set",
            "Emitted when items are added or removed to a set being iterated through. "
            "Doing so raises a RuntimeError.",
        ),
    }

    options = ()

    @utils.only_required_for_messages(
        "modified-iterating-list", "modified-iterating-dict", "modified-iterating-set"
    )
    def visit_for(self, node: nodes.For) -> None:
        iter_obj = node.iter
        for body_node in node.body:
            self._modified_iterating_check_on_node_and_children(body_node, iter_obj)

    def _modified_iterating_check_on_node_and_children(
        self, body_node: nodes.NodeNG, iter_obj: nodes.NodeNG
    ) -> None:
        """See if node or any of its children raises modified iterating messages."""
        self._modified_iterating_check(body_node, iter_obj)
        for child in body_node.get_children():
            self._modified_iterating_check_on_node_and_children(child, iter_obj)

    def _modified_iterating_check(
        self, node: nodes.NodeNG, iter_obj: nodes.NodeNG
    ) -> None:
        msg_id = None
        if isinstance(node, nodes.Delete) and any(
            self._deleted_iteration_target_cond(t, iter_obj) for t in node.targets
        ):
            inferred = utils.safe_infer(iter_obj)
            if isinstance(inferred, nodes.List):
                msg_id = "modified-iterating-list"
            elif isinstance(inferred, nodes.Dict):
                msg_id = "modified-iterating-dict"
            elif isinstance(inferred, nodes.Set):
                msg_id = "modified-iterating-set"
        elif not isinstance(iter_obj, (nodes.Name, nodes.Attribute)):
            pass
        elif self._modified_iterating_list_cond(node, iter_obj):
            msg_id = "modified-iterating-list"
        elif self._modified_iterating_dict_cond(node, iter_obj):
            msg_id = "modified-iterating-dict"
        elif self._modified_iterating_set_cond(node, iter_obj):
            msg_id = "modified-iterating-set"
        if msg_id:
            if isinstance(iter_obj, nodes.Attribute):
                obj_name = iter_obj.attrname
            else:
                obj_name = iter_obj.name
            self.add_message(
                msg_id,
                node=node,
                args=(obj_name,),
                confidence=interfaces.INFERENCE,
            )

    @staticmethod
    def _is_node_expr_that_calls_attribute_name(node: nodes.NodeNG) -> bool:
        return (
            isinstance(node, nodes.Expr)
            and isinstance(node.value, nodes.Call)
            and isinstance(node.value.func, nodes.Attribute)
            and isinstance(node.value.func.expr, nodes.Name)
        )

    @staticmethod
    def _common_cond_list_set(
        node: nodes.Expr,
        iter_obj: nodes.Name | nodes.Attribute,
        infer_val: nodes.List | nodes.Set,
    ) -> bool:
        iter_obj_name = (
            iter_obj.attrname
            if isinstance(iter_obj, nodes.Attribute)
            else iter_obj.name
        )
        return (infer_val == utils.safe_infer(iter_obj)) and (  # type: ignore[no-any-return]
            node.value.func.expr.name == iter_obj_name
        )

    @staticmethod
    def _is_node_assigns_subscript_name(node: nodes.NodeNG) -> bool:
        return isinstance(node, nodes.Assign) and (
            isinstance(node.targets[0], nodes.Subscript)
            and (isinstance(node.targets[0].value, nodes.Name))
        )

    def _modified_iterating_list_cond(
        self, node: nodes.NodeNG, iter_obj: nodes.Name | nodes.Attribute
    ) -> bool:
        if not self._is_node_expr_that_calls_attribute_name(node):
            return False
        infer_val = utils.safe_infer(node.value.func.expr)
        if not isinstance(infer_val, nodes.List):
            return False
        return (
            self._common_cond_list_set(node, iter_obj, infer_val)
            and node.value.func.attrname in _LIST_MODIFIER_METHODS
        )

    def _modified_iterating_dict_cond(
        self, node: nodes.NodeNG, iter_obj: nodes.Name | nodes.Attribute
    ) -> bool:
        if not self._is_node_assigns_subscript_name(node):
            return False
        # Do not emit when merely updating the same key being iterated
        if (
            isinstance(iter_obj, nodes.Name)
            and iter_obj.name == node.targets[0].value.name
            and isinstance(iter_obj.parent.target, nodes.AssignName)
            and isinstance(node.targets[0].slice, nodes.Name)
            and iter_obj.parent.target.name == node.targets[0].slice.name
        ):
            return False
        infer_val = utils.safe_infer(node.targets[0].value)
        if not isinstance(infer_val, nodes.Dict):
            return False
        if infer_val != utils.safe_infer(iter_obj):
            return False
        if isinstance(iter_obj, nodes.Attribute):
            iter_obj_name = iter_obj.attrname
        else:
            iter_obj_name = iter_obj.name
        return node.targets[0].value.name == iter_obj_name  # type: ignore[no-any-return]

    def _modified_iterating_set_cond(
        self, node: nodes.NodeNG, iter_obj: nodes.Name | nodes.Attribute
    ) -> bool:
        if not self._is_node_expr_that_calls_attribute_name(node):
            return False
        infer_val = utils.safe_infer(node.value.func.expr)
        if not isinstance(infer_val, nodes.Set):
            return False
        return (
            self._common_cond_list_set(node, iter_obj, infer_val)
            and node.value.func.attrname in _SET_MODIFIER_METHODS
        )

    def _deleted_iteration_target_cond(
        self, node: nodes.DelName, iter_obj: nodes.NodeNG
    ) -> bool:
        if not isinstance(node, nodes.DelName):
            return False
        if not isinstance(iter_obj.parent, nodes.For):
            return False
        if not isinstance(
            iter_obj.parent.target, (nodes.AssignName, nodes.BaseContainer)
        ):
            return False
        return any(
            t == node.name
            for t in utils.find_assigned_names_recursive(iter_obj.parent.target)
        )


def register(linter: PyLinter) -> None:
    linter.register_checker(ModifiedIterationChecker(linter))
