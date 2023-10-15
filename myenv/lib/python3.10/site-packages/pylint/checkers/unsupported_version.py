# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Checker for features used that are not supported by all python versions
indicated by the py-version setting.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from astroid import nodes

from pylint.checkers import BaseChecker
from pylint.checkers.utils import (
    only_required_for_messages,
    safe_infer,
    uninferable_final_decorators,
)

if TYPE_CHECKING:
    from pylint.lint import PyLinter


class UnsupportedVersionChecker(BaseChecker):
    """Checker for features that are not supported by all python versions
    indicated by the py-version setting.
    """

    name = "unsupported_version"
    msgs = {
        "W2601": (
            "F-strings are not supported by all versions included in the py-version setting",
            "using-f-string-in-unsupported-version",
            "Used when the py-version set by the user is lower than 3.6 and pylint encounters "
            "a f-string.",
        ),
        "W2602": (
            "typing.final is not supported by all versions included in the py-version setting",
            "using-final-decorator-in-unsupported-version",
            "Used when the py-version set by the user is lower than 3.8 and pylint encounters "
            "a ``typing.final`` decorator.",
        ),
    }

    def open(self) -> None:
        """Initialize visit variables and statistics."""
        py_version = self.linter.config.py_version
        self._py36_plus = py_version >= (3, 6)
        self._py38_plus = py_version >= (3, 8)

    @only_required_for_messages("using-f-string-in-unsupported-version")
    def visit_joinedstr(self, node: nodes.JoinedStr) -> None:
        """Check f-strings."""
        if not self._py36_plus:
            self.add_message("using-f-string-in-unsupported-version", node=node)

    @only_required_for_messages("using-final-decorator-in-unsupported-version")
    def visit_decorators(self, node: nodes.Decorators) -> None:
        """Check decorators."""
        self._check_typing_final(node)

    def _check_typing_final(self, node: nodes.Decorators) -> None:
        """Add a message when the `typing.final` decorator is used and the
        py-version is lower than 3.8.
        """
        if self._py38_plus:
            return

        decorators = []
        for decorator in node.get_children():
            inferred = safe_infer(decorator)
            if inferred and inferred.qname() == "typing.final":
                decorators.append(decorator)

        for decorator in decorators or uninferable_final_decorators(node):
            self.add_message(
                "using-final-decorator-in-unsupported-version", node=decorator
            )


def register(linter: PyLinter) -> None:
    linter.register_checker(UnsupportedVersionChecker(linter))
