# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import json
import sys
import warnings
from io import StringIO

from git.repo import Repo

from pylint.lint import Run
from pylint.message import Message
from pylint.reporters import JSONReporter
from pylint.reporters.json_reporter import OldJsonExport
from pylint.testutils._primer.package_to_lint import PackageToLint
from pylint.testutils._primer.primer_command import (
    PackageData,
    PackageMessages,
    PrimerCommand,
)

GITHUB_CRASH_TEMPLATE_LOCATION = "/home/runner/.cache"
CRASH_TEMPLATE_INTRO = "There is a pre-filled template"


class RunCommand(PrimerCommand):
    def run(self) -> None:
        packages: PackageMessages = {}
        fatal_msgs: list[Message] = []
        for package, data in self.packages.items():
            messages, p_fatal_msgs = self._lint_package(package, data)
            fatal_msgs += p_fatal_msgs
            local_commit = Repo(data.clone_directory).head.object.hexsha
            packages[package] = PackageData(commit=local_commit, messages=messages)
        path = (
            self.primer_directory
            / f"output_{'.'.join(str(i) for i in sys.version_info[:3])}_{self.config.type}.txt"
        )
        print(f"Writing result in {path}")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(packages, f)
        # Assert that a PR run does not introduce new fatal errors
        if self.config.type == "pr":
            plural = "s" if len(fatal_msgs) > 1 else ""
            assert (
                not fatal_msgs
            ), f"We encountered {len(fatal_msgs)} fatal error message{plural} (see log)."

    @staticmethod
    def _filter_fatal_errors(
        messages: list[OldJsonExport],
    ) -> list[Message]:
        """Separate fatal errors so we can report them independently."""
        fatal_msgs: list[Message] = []
        for raw_message in messages:
            message = JSONReporter.deserialize(raw_message)
            if message.category == "fatal":
                if GITHUB_CRASH_TEMPLATE_LOCATION in message.msg:
                    # Remove the crash template location if we're running on GitHub.
                    # We were falsely getting "new" errors when the timestamp changed.
                    message.msg = message.msg.rsplit(CRASH_TEMPLATE_INTRO)[0]
                fatal_msgs.append(message)
        return fatal_msgs

    @staticmethod
    def _print_msgs(msgs: list[Message]) -> str:
        return "\n".join(f"- {JSONReporter.serialize(m)}" for m in msgs)

    def _lint_package(
        self, package_name: str, data: PackageToLint
    ) -> tuple[list[OldJsonExport], list[Message]]:
        # We want to test all the code we can
        enables = ["--enable-all-extensions", "--enable=all"]
        # Duplicate code takes too long and is relatively safe
        # TODO: Find a way to allow cyclic-import and compare output correctly
        disables = ["--disable=duplicate-code,cyclic-import"]
        arguments = data.pylint_args + enables + disables
        output = StringIO()
        reporter = JSONReporter(output)
        print(f"Running 'pylint {', '.join(arguments)}'")
        pylint_exit_code = -1
        try:
            Run(arguments, reporter=reporter)
        except SystemExit as e:
            pylint_exit_code = int(e.code)  # type: ignore[arg-type]
        readable_messages: str = output.getvalue()
        messages: list[OldJsonExport] = json.loads(readable_messages)
        fatal_msgs: list[Message] = []
        if pylint_exit_code % 2 == 0:
            print(f"Successfully primed {package_name}.")
        else:
            fatal_msgs = self._filter_fatal_errors(messages)
            if fatal_msgs:
                warnings.warn(
                    f"Encountered fatal errors while priming {package_name} !\n"
                    f"{self._print_msgs(fatal_msgs)}\n\n"
                )
        return messages, fatal_msgs
