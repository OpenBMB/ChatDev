# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import csv
import os

from _pytest.config import Config

from pylint.constants import PY38_PLUS
from pylint.testutils.functional.test_file import FunctionalTestFile
from pylint.testutils.lint_module_test import LintModuleTest, MessageCounter
from pylint.testutils.output_line import OutputLine


class LintModuleOutputUpdate(LintModuleTest):
    """Class to be used if expected output files should be updated instead of
    checked.
    """

    class TestDialect(csv.excel):
        """Dialect used by the csv writer."""

        delimiter = ":"
        lineterminator = "\n"

    csv.register_dialect("test", TestDialect)

    def __init__(
        self, test_file: FunctionalTestFile, config: Config | None = None
    ) -> None:
        if not PY38_PLUS:
            raise RuntimeError(
                "You need at least python 3.8 for the functional test updater to work. "
                "This is because python 3.8 includes a new AST parser, which amongst others "
                "returns the end line and end column of most nodes."
            )
        super().__init__(test_file, config)

    def _check_output_text(
        self,
        _: MessageCounter,
        expected_output: list[OutputLine],
        actual_output: list[OutputLine],
    ) -> None:
        """Overwrite or remove the expected output file based on actual output."""
        # Remove the file if no output is actually expected and a file exists
        if not expected_output and not actual_output:
            if os.path.exists(self._test_file.expected_output):
                os.remove(self._test_file.expected_output)
            return
        # Write file with expected output
        with open(self._test_file.expected_output, "w", encoding="utf-8") as f:
            writer = csv.writer(f, dialect="test")
            for line in actual_output:
                writer.writerow(line.to_csv())
