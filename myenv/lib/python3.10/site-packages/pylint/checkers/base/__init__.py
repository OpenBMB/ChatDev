# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

# pylint: disable=duplicate-code # This is similar to the __init__ of .name_checker

from __future__ import annotations

__all__ = [
    "NameChecker",
    "NamingStyle",
    "KNOWN_NAME_TYPES_WITH_STYLE",
    "SnakeCaseStyle",
    "CamelCaseStyle",
    "UpperCaseStyle",
    "PascalCaseStyle",
    "AnyStyle",
]

from typing import TYPE_CHECKING

from pylint.checkers.base.basic_checker import BasicChecker
from pylint.checkers.base.basic_error_checker import BasicErrorChecker
from pylint.checkers.base.comparison_checker import ComparisonChecker
from pylint.checkers.base.docstring_checker import DocStringChecker
from pylint.checkers.base.name_checker import (
    KNOWN_NAME_TYPES_WITH_STYLE,
    AnyStyle,
    CamelCaseStyle,
    NamingStyle,
    PascalCaseStyle,
    SnakeCaseStyle,
    UpperCaseStyle,
)
from pylint.checkers.base.name_checker.checker import NameChecker
from pylint.checkers.base.pass_checker import PassChecker

if TYPE_CHECKING:
    from pylint.lint import PyLinter


def register(linter: PyLinter) -> None:
    linter.register_checker(BasicErrorChecker(linter))
    linter.register_checker(BasicChecker(linter))
    linter.register_checker(NameChecker(linter))
    linter.register_checker(DocStringChecker(linter))
    linter.register_checker(PassChecker(linter))
    linter.register_checker(ComparisonChecker(linter))
