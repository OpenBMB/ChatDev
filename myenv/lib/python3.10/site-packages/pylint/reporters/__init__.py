# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Utilities methods and classes for reporters."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylint import utils
from pylint.reporters.base_reporter import BaseReporter
from pylint.reporters.collecting_reporter import CollectingReporter
from pylint.reporters.json_reporter import JSONReporter
from pylint.reporters.multi_reporter import MultiReporter
from pylint.reporters.reports_handler_mix_in import ReportsHandlerMixIn

if TYPE_CHECKING:
    from pylint.lint.pylinter import PyLinter


def initialize(linter: PyLinter) -> None:
    """Initialize linter with reporters in this package."""
    utils.register_plugins(linter, __path__[0])


__all__ = [
    "BaseReporter",
    "ReportsHandlerMixIn",
    "JSONReporter",
    "CollectingReporter",
    "MultiReporter",
]
