# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Various helper functions to create the docs of a linter object."""

from __future__ import annotations

import sys
import warnings
from typing import TYPE_CHECKING, Any, TextIO

from pylint.constants import MAIN_CHECKER_NAME
from pylint.utils.utils import get_rst_section, get_rst_title

if TYPE_CHECKING:
    from pylint.lint.pylinter import PyLinter


def _get_checkers_infos(linter: PyLinter) -> dict[str, dict[str, Any]]:
    """Get info from a checker and handle KeyError."""
    by_checker: dict[str, dict[str, Any]] = {}
    for checker in linter.get_checkers():
        name = checker.name
        if name != MAIN_CHECKER_NAME:
            try:
                by_checker[name]["checker"] = checker
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=DeprecationWarning)
                    by_checker[name]["options"] += checker.options_and_values()
                by_checker[name]["msgs"].update(checker.msgs)
                by_checker[name]["reports"] += checker.reports
            except KeyError:
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=DeprecationWarning)
                    by_checker[name] = {
                        "checker": checker,
                        "options": list(checker.options_and_values()),
                        "msgs": dict(checker.msgs),
                        "reports": list(checker.reports),
                    }
    return by_checker


def _get_global_options_documentation(linter: PyLinter) -> str:
    """Get documentation for the main checker."""
    result = get_rst_title("Pylint global options and switches", "-")
    result += """
Pylint provides global options and switches.

"""
    for checker in linter.get_checkers():
        if checker.name == MAIN_CHECKER_NAME and checker.options:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=DeprecationWarning)
                for section, options in checker.options_by_section():
                    if section is None:
                        title = "General options"
                    else:
                        title = f"{section.capitalize()} options"
                    result += get_rst_title(title, "~")
                    assert isinstance(options, list)
                    result += f"{get_rst_section(None, options)}\n"
    return result


def _get_checkers_documentation(linter: PyLinter, show_options: bool = True) -> str:
    """Get documentation for individual checkers."""
    if show_options:
        result = _get_global_options_documentation(linter)
    else:
        result = ""

    result += get_rst_title("Pylint checkers' options and switches", "-")
    result += """\

Pylint checkers can provide three set of features:

* options that control their execution,
* messages that they can raise,
* reports that they can generate.

Below is a list of all checkers and their features.

"""
    by_checker = _get_checkers_infos(linter)
    for checker_name in sorted(by_checker):
        information = by_checker[checker_name]
        checker = information["checker"]
        del information["checker"]
        result += checker.get_full_documentation(
            **information, show_options=show_options
        )
    return result


def print_full_documentation(
    linter: PyLinter, stream: TextIO = sys.stdout, show_options: bool = True
) -> None:
    """Output a full documentation in ReST format."""
    print(
        _get_checkers_documentation(linter, show_options=show_options)[:-3], file=stream
    )
