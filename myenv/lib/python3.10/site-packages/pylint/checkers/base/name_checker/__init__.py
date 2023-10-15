# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

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

from pylint.checkers.base.name_checker.checker import NameChecker
from pylint.checkers.base.name_checker.naming_style import (
    KNOWN_NAME_TYPES_WITH_STYLE,
    AnyStyle,
    CamelCaseStyle,
    NamingStyle,
    PascalCaseStyle,
    SnakeCaseStyle,
    UpperCaseStyle,
)
