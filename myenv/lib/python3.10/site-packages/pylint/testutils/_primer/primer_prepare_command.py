# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt
from __future__ import annotations

import sys

from git.cmd import Git
from git.repo import Repo

from pylint.testutils._primer.primer_command import PrimerCommand


class PrepareCommand(PrimerCommand):
    def run(self) -> None:
        commit_string = ""
        version_string = ".".join(str(x) for x in sys.version_info[:2])
        if self.config.clone:
            for package, data in self.packages.items():
                local_commit = data.lazy_clone()
                print(f"Cloned '{package}' at commit '{local_commit}'.")
                commit_string += local_commit + "_"
        elif self.config.check:
            for package, data in self.packages.items():
                local_commit = Repo(data.clone_directory).head.object.hexsha
                print(f"Found '{package}' at commit '{local_commit}'.")
                commit_string += local_commit + "_"
        elif self.config.make_commit_string:
            for package, data in self.packages.items():
                remote_sha1_commit = (
                    Git().ls_remote(data.url, data.branch).split("\t")[0]
                )
                print(f"'{package}' remote is at commit '{remote_sha1_commit}'.")
                commit_string += remote_sha1_commit + "_"
        elif self.config.read_commit_string:
            with open(
                self.primer_directory / f"commit_string_{version_string}.txt",
                encoding="utf-8",
            ) as f:
                print(f.read())
        if commit_string:
            with open(
                self.primer_directory / f"commit_string_{version_string}.txt",
                "w",
                encoding="utf-8",
            ) as f:
                f.write(commit_string)
