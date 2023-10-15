# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Classes and functions used to mimic normal pylint runs.

This module is considered private and can change at any time.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pylint.lint import Run as LintRun
from pylint.lint.run import UNUSED_PARAM_SENTINEL
from pylint.reporters.base_reporter import BaseReporter
from pylint.testutils.lint_module_test import PYLINTRC


def _add_rcfile_default_pylintrc(args: list[str]) -> list[str]:
    """Add a default pylintrc with the rcfile option in a list of pylint args."""
    if not any("--rcfile" in arg for arg in args):
        args.insert(0, f"--rcfile={PYLINTRC}")
    return args


class _Run(LintRun):

    """Like Run, but we're using an explicitly set empty pylintrc.

    We don't want to use the project's pylintrc during tests, because
    it means that a change in our config could break tests.
    But we want to see if the changes to the default break tests.
    """

    def __init__(
        self,
        args: Sequence[str],
        reporter: BaseReporter | None = None,
        exit: bool = True,  # pylint: disable=redefined-builtin
        do_exit: Any = UNUSED_PARAM_SENTINEL,
    ) -> None:
        args = _add_rcfile_default_pylintrc(list(args))
        super().__init__(args, reporter, exit, do_exit)
