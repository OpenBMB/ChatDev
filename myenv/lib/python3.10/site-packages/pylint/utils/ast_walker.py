# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import sys
import traceback
from collections import defaultdict
from collections.abc import Sequence
from typing import TYPE_CHECKING, Callable

from astroid import nodes

if TYPE_CHECKING:
    from pylint.checkers.base_checker import BaseChecker
    from pylint.lint import PyLinter

# Callable parameter type NodeNG not completely correct.
# Due to contravariance of Callable parameter types,
# it should be a Union of all NodeNG subclasses.
# However, since the methods are only retrieved with
# getattr(checker, member) and thus are inferred as Any,
# NodeNG will work too.
AstCallback = Callable[[nodes.NodeNG], None]


class ASTWalker:
    def __init__(self, linter: PyLinter) -> None:
        # callbacks per node types
        self.nbstatements = 0
        self.visit_events: defaultdict[str, list[AstCallback]] = defaultdict(list)
        self.leave_events: defaultdict[str, list[AstCallback]] = defaultdict(list)
        self.linter = linter
        self.exception_msg = False

    def _is_method_enabled(self, method: AstCallback) -> bool:
        if not hasattr(method, "checks_msgs"):
            return True
        return any(self.linter.is_message_enabled(m) for m in method.checks_msgs)

    def add_checker(self, checker: BaseChecker) -> None:
        """Walk to the checker's dir and collect visit and leave methods."""
        vcids: set[str] = set()
        lcids: set[str] = set()
        visits = self.visit_events
        leaves = self.leave_events
        for member in dir(checker):
            cid = member[6:]
            if cid == "default":
                continue
            if member.startswith("visit_"):
                v_meth = getattr(checker, member)
                # don't use visit_methods with no activated message:
                if self._is_method_enabled(v_meth):
                    visits[cid].append(v_meth)
                    vcids.add(cid)
            elif member.startswith("leave_"):
                l_meth = getattr(checker, member)
                # don't use leave_methods with no activated message:
                if self._is_method_enabled(l_meth):
                    leaves[cid].append(l_meth)
                    lcids.add(cid)
        visit_default = getattr(checker, "visit_default", None)
        if visit_default:
            for cls in nodes.ALL_NODE_CLASSES:
                cid = cls.__name__.lower()
                if cid not in vcids:
                    visits[cid].append(visit_default)
        # For now, we have no "leave_default" method in Pylint

    def walk(self, astroid: nodes.NodeNG) -> None:
        """Call visit events of astroid checkers for the given node, recurse on
        its children, then leave events.
        """
        cid = astroid.__class__.__name__.lower()

        # Detect if the node is a new name for a deprecated alias.
        # In this case, favour the methods for the deprecated
        # alias if any,  in order to maintain backwards
        # compatibility.
        visit_events: Sequence[AstCallback] = self.visit_events.get(cid, ())
        leave_events: Sequence[AstCallback] = self.leave_events.get(cid, ())

        # pylint: disable = too-many-try-statements
        try:
            if astroid.is_statement:
                self.nbstatements += 1
            # generate events for this node on each checker
            for callback in visit_events:
                callback(astroid)
            # recurse on children
            for child in astroid.get_children():
                self.walk(child)
            for callback in leave_events:
                callback(astroid)
        except Exception:
            if self.exception_msg is False:
                file = getattr(astroid.root(), "file", None)
                print(
                    f"Exception on node {repr(astroid)} in file '{file}'",
                    file=sys.stderr,
                )
                traceback.print_exc()
                self.exception_msg = True
            raise
