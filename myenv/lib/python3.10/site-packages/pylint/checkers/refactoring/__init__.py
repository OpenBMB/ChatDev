# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Looks for code which can be refactored."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylint.checkers.refactoring.implicit_booleaness_checker import (
    ImplicitBooleanessChecker,
)
from pylint.checkers.refactoring.not_checker import NotChecker
from pylint.checkers.refactoring.recommendation_checker import RecommendationChecker
from pylint.checkers.refactoring.refactoring_checker import RefactoringChecker

if TYPE_CHECKING:
    from pylint.lint import PyLinter

__all__ = [
    "ImplicitBooleanessChecker",
    "NotChecker",
    "RecommendationChecker",
    "RefactoringChecker",
]


def register(linter: PyLinter) -> None:
    linter.register_checker(RefactoringChecker(linter))
    linter.register_checker(NotChecker(linter))
    linter.register_checker(RecommendationChecker(linter))
    linter.register_checker(ImplicitBooleanessChecker(linter))
