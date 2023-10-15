# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

from typing import TYPE_CHECKING

from pylint.checkers.classes.class_checker import ClassChecker
from pylint.checkers.classes.special_methods_checker import SpecialMethodsChecker

if TYPE_CHECKING:
    from pylint.lint import PyLinter


def register(linter: PyLinter) -> None:
    linter.register_checker(ClassChecker(linter))
    linter.register_checker(SpecialMethodsChecker(linter))
