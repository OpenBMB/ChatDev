# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

from typing import TYPE_CHECKING

from pylint.utils import register_plugins

if TYPE_CHECKING:
    from pylint.lint import PyLinter


def initialize(linter: PyLinter) -> None:
    """Initialize linter with checkers in the extensions' directory."""
    register_plugins(linter, __path__[0])


__all__ = ["initialize"]
