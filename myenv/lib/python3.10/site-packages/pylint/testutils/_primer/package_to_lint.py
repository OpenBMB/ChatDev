# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import logging
import sys
from pathlib import Path

from git import GitCommandError
from git.cmd import Git
from git.repo import Repo

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal

PRIMER_DIRECTORY_PATH = Path("tests") / ".pylint_primer_tests"


class PackageToLint:
    """Represents data about a package to be tested during primer tests."""

    url: str
    """URL of the repository to clone."""

    branch: str
    """Branch of the repository to clone."""

    directories: list[str]
    """Directories within the repository to run pylint over."""

    commit: str | None
    """Commit hash to pin the repository on."""

    pylint_additional_args: list[str]
    """Arguments to give to pylint."""

    pylintrc_relpath: str | None
    """Path relative to project's main directory to the pylintrc if it exists."""

    minimum_python: str | None
    """Minimum python version supported by the package."""

    def __init__(
        self,
        url: str,
        branch: str,
        directories: list[str],
        commit: str | None = None,
        pylint_additional_args: list[str] | None = None,
        pylintrc_relpath: str | None = None,
        minimum_python: str | None = None,
    ) -> None:
        self.url = url
        self.branch = branch
        self.directories = directories
        self.commit = commit
        self.pylint_additional_args = pylint_additional_args or []
        self.pylintrc_relpath = pylintrc_relpath
        self.minimum_python = minimum_python

    @property
    def pylintrc(self) -> Path | Literal[""]:
        if self.pylintrc_relpath is None:
            # Fall back to "" to ensure pylint's own pylintrc is not discovered
            return ""
        return self.clone_directory / self.pylintrc_relpath

    @property
    def clone_directory(self) -> Path:
        """Directory to clone repository into."""
        clone_name = "/".join(self.url.split("/")[-2:]).replace(".git", "")
        return PRIMER_DIRECTORY_PATH / clone_name

    @property
    def paths_to_lint(self) -> list[str]:
        """The paths we need to lint."""
        return [str(self.clone_directory / path) for path in self.directories]

    @property
    def pylint_args(self) -> list[str]:
        options: list[str] = []
        # There is an error if rcfile is given but does not exist
        options += [f"--rcfile={self.pylintrc}"]
        return self.paths_to_lint + options + self.pylint_additional_args

    def lazy_clone(self) -> str:  # pragma: no cover
        """Concatenates the target directory and clones the file.

        Not expected to be tested as the primer won't work if it doesn't.
        It's tested in the continuous integration primers, only the coverage
        is not calculated on everything. If lazy clone breaks for local use
        we'll probably notice because we'll have a fatal when launching the
        primer locally.
        """
        logging.info("Lazy cloning %s", self.url)
        if not self.clone_directory.exists():
            return self._clone_repository()
        return self._pull_repository()

    def _clone_repository(self) -> str:
        options: dict[str, str | int] = {
            "url": self.url,
            "to_path": str(self.clone_directory),
            "branch": self.branch,
            "depth": 1,
        }
        logging.info("Directory does not exists, cloning: %s", options)
        repo = Repo.clone_from(
            url=self.url, to_path=self.clone_directory, branch=self.branch, depth=1
        )
        return str(repo.head.object.hexsha)

    def _pull_repository(self) -> str:
        remote_sha1_commit = Git().ls_remote(self.url, self.branch).split("\t")[0]
        local_sha1_commit = Repo(self.clone_directory).head.object.hexsha
        if remote_sha1_commit != local_sha1_commit:
            logging.info(
                "Remote sha is '%s' while local sha is '%s': pulling new commits",
                remote_sha1_commit,
                local_sha1_commit,
            )
            try:
                repo = Repo(self.clone_directory)
                origin = repo.remotes.origin
                origin.pull()
            except GitCommandError as e:
                raise SystemError(
                    f"Failed to clone repository for {self.clone_directory}"
                ) from e
        else:
            logging.info("Repository already up to date.")
        return str(remote_sha1_commit)
