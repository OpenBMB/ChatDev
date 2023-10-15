# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

from typing import TYPE_CHECKING

from astroid import nodes

from pylint.checkers import BaseChecker
from pylint.checkers.utils import only_required_for_messages, safe_infer

if TYPE_CHECKING:
    from pylint.lint import PyLinter


class ThreadingChecker(BaseChecker):
    """Checks for threading module.

    - useless with lock - locking used in wrong way that has no effect (with threading.Lock():)
    """

    name = "threading"

    LOCKS = frozenset(
        (
            "threading.Lock",
            "threading.RLock",
            "threading.Condition",
            "threading.Semaphore",
            "threading.BoundedSemaphore",
        )
    )

    msgs = {
        "W2101": (
            "'%s()' directly created in 'with' has no effect",
            "useless-with-lock",
            "Used when a new lock instance is created by using with statement "
            "which has no effect. Instead, an existing instance should be used to acquire lock.",
        ),
    }

    @only_required_for_messages("useless-with-lock")
    def visit_with(self, node: nodes.With) -> None:
        context_managers = (c for c, _ in node.items if isinstance(c, nodes.Call))
        for context_manager in context_managers:
            if isinstance(context_manager, nodes.Call):
                infered_function = safe_infer(context_manager.func)
                if infered_function is None:
                    continue
                qname = infered_function.qname()
                if qname in self.LOCKS:
                    self.add_message("useless-with-lock", node=node, args=qname)


def register(linter: PyLinter) -> None:
    linter.register_checker(ThreadingChecker(linter))
