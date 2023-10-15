# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pylint.testutils._primer import PackageToLint
from pylint.testutils._primer.primer_command import PrimerCommand
from pylint.testutils._primer.primer_compare_command import CompareCommand
from pylint.testutils._primer.primer_prepare_command import PrepareCommand
from pylint.testutils._primer.primer_run_command import RunCommand


class Primer:
    """Main class to handle priming of packages."""

    def __init__(self, primer_directory: Path, json_path: Path) -> None:
        # Preparing arguments
        self.primer_directory = primer_directory
        self._argument_parser = argparse.ArgumentParser(prog="Pylint Primer")
        self._subparsers = self._argument_parser.add_subparsers(
            dest="command", required=True
        )

        # All arguments for the prepare parser
        prepare_parser = self._subparsers.add_parser("prepare")
        prepare_parser.add_argument(
            "--clone", help="Clone all packages.", action="store_true", default=False
        )
        prepare_parser.add_argument(
            "--check",
            help="Check consistencies and commits of all packages.",
            action="store_true",
            default=False,
        )
        prepare_parser.add_argument(
            "--make-commit-string",
            help="Get latest commit string.",
            action="store_true",
            default=False,
        )
        prepare_parser.add_argument(
            "--read-commit-string",
            help="Print latest commit string.",
            action="store_true",
            default=False,
        )

        # All arguments for the run parser
        run_parser = self._subparsers.add_parser("run")
        run_parser.add_argument(
            "--type", choices=["main", "pr"], required=True, help="Type of primer run."
        )

        # All arguments for the compare parser
        compare_parser = self._subparsers.add_parser("compare")
        compare_parser.add_argument(
            "--base-file",
            required=True,
            help="Location of output file of the base run.",
        )
        compare_parser.add_argument(
            "--new-file",
            required=True,
            help="Location of output file of the new run.",
        )
        compare_parser.add_argument(
            "--commit",
            required=True,
            help="Commit hash of the PR commit being checked.",
        )

        # Storing arguments
        self.config = self._argument_parser.parse_args()

        self.packages = self._get_packages_to_lint_from_json(json_path)
        """All packages to prime."""

        if self.config.command == "prepare":
            command_class: type[PrimerCommand] = PrepareCommand
        elif self.config.command == "run":
            command_class = RunCommand
        elif self.config.command == "compare":
            command_class = CompareCommand
        self.command = command_class(self.primer_directory, self.packages, self.config)

    def run(self) -> None:
        self.command.run()

    @staticmethod
    def _minimum_python_supported(package_data: dict[str, str]) -> bool:
        min_python_str = package_data.get("minimum_python", None)
        if not min_python_str:
            return True
        min_python_tuple = tuple(int(n) for n in min_python_str.split("."))
        return min_python_tuple <= sys.version_info[:2]

    @staticmethod
    def _get_packages_to_lint_from_json(json_path: Path) -> dict[str, PackageToLint]:
        with open(json_path, encoding="utf8") as f:
            return {
                name: PackageToLint(**package_data)
                for name, package_data in json.load(f).items()
                if Primer._minimum_python_supported(package_data)
            }
