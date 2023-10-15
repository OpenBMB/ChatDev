# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import os
from pathlib import Path

from pylint.testutils.functional.test_file import FunctionalTestFile

REASONABLY_DISPLAYABLE_VERTICALLY = 48
"""'Wet finger' number of files that are reasonable to display by an IDE."""
SHOULD_BE_IN_THE_SAME_DIRECTORY = 5
"""'Wet finger' as in 'in my settings there are precisely this many'."""

IGNORED_PARENT_DIRS = {
    "deprecated_relative_import",
    "ext",
    "regression",
    "regression_02",
}
"""Direct parent directories that should be ignored."""

IGNORED_PARENT_PARENT_DIRS = {
    "docparams",
    "deprecated_relative_import",
    "ext",
}
"""Parents of direct parent directories that should be ignored."""


def get_functional_test_files_from_directory(
    input_dir: Path | str,
) -> list[FunctionalTestFile]:
    """Get all functional tests in the input_dir."""
    suite = []

    _check_functional_tests_structure(Path(input_dir))

    for dirpath, dirnames, filenames in os.walk(input_dir):
        if dirpath.endswith("__pycache__"):
            continue
        dirnames.sort()
        filenames.sort()
        for filename in filenames:
            if filename != "__init__.py" and filename.endswith(".py"):
                suite.append(FunctionalTestFile(dirpath, filename))
    return suite


def _check_functional_tests_structure(directory: Path) -> None:
    """Check if test directories follow correct file/folder structure."""
    # Ignore underscored directories
    if Path(directory).stem.startswith("_"):
        return

    files: set[Path] = set()
    dirs: set[Path] = set()

    # Collect all sub-directories and files in directory
    for file_or_dir in directory.iterdir():
        if file_or_dir.is_file():
            if file_or_dir.suffix == ".py" and not file_or_dir.stem.startswith("_"):
                files.add(file_or_dir)
        elif file_or_dir.is_dir():
            dirs.add(file_or_dir)
            _check_functional_tests_structure(file_or_dir)

    assert len(files) <= REASONABLY_DISPLAYABLE_VERTICALLY, (
        f"{directory} contains too many functional tests files "
        + f"({len(files)} > {REASONABLY_DISPLAYABLE_VERTICALLY})."
    )

    for file in files:
        possible_dir = file.parent / file.stem.split("_")[0]
        assert not possible_dir.exists(), f"{file} should go in {possible_dir}."

        # Exclude some directories as they follow a different structure
        if (
            not len(file.parent.stem) == 1  # First letter sub-directories
            and file.parent.stem not in IGNORED_PARENT_DIRS
            and file.parent.parent.stem not in IGNORED_PARENT_PARENT_DIRS
        ):
            assert file.stem.startswith(
                file.parent.stem
            ), f"{file} should not go in {file.parent}"
