# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Pylint [options] modules_or_packages.

  Check that module(s) satisfy a coding standard (and more !).

    pylint --help

  Display this help message and exit.

    pylint --help-msg <msg-id>[,<msg-id>]

  Display help messages about given message identifiers and exit.
"""
import sys

from pylint.config.exceptions import ArgumentPreprocessingError
from pylint.lint.caching import load_results, save_results
from pylint.lint.expand_modules import discover_package_path
from pylint.lint.parallel import check_parallel
from pylint.lint.pylinter import PyLinter
from pylint.lint.report_functions import (
    report_messages_by_module_stats,
    report_messages_stats,
    report_total_messages_stats,
)
from pylint.lint.run import Run
from pylint.lint.utils import (
    _augment_sys_path,
    _patch_sys_path,
    augmented_sys_path,
    fix_import_path,
)

__all__ = [
    "check_parallel",
    "PyLinter",
    "report_messages_by_module_stats",
    "report_messages_stats",
    "report_total_messages_stats",
    "Run",
    "ArgumentPreprocessingError",
    "_patch_sys_path",
    "fix_import_path",
    "_augment_sys_path",
    "augmented_sys_path",
    "discover_package_path",
    "save_results",
    "load_results",
]

if __name__ == "__main__":
    Run(sys.argv[1:])
