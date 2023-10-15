# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import argparse
import configparser
import shlex
import sys
from pathlib import Path
from typing import NamedTuple

from pylint.pyreverse.main import DEFAULT_COLOR_PALETTE

if sys.version_info >= (3, 8):
    from typing import TypedDict
else:
    from typing_extensions import TypedDict


# This class could and should be replaced with a simple dataclass when support for Python < 3.7 is dropped.
# A NamedTuple is not possible as some tests need to modify attributes during the test.
class PyreverseConfig(
    argparse.Namespace
):  # pylint: disable=too-many-instance-attributes, too-many-arguments
    """Holds the configuration options for Pyreverse.

    The default values correspond to the defaults of the options' parser.
    """

    def __init__(
        self,
        mode: str = "PUB_ONLY",
        classes: list[str] | None = None,
        show_ancestors: int | None = None,
        all_ancestors: bool | None = None,
        show_associated: int | None = None,
        all_associated: bool | None = None,
        show_builtin: bool = False,
        module_names: bool | None = None,
        only_classnames: bool = False,
        output_format: str = "dot",
        colorized: bool = False,
        max_color_depth: int = 2,
        color_palette: tuple[str, ...] = DEFAULT_COLOR_PALETTE,
        ignore_list: tuple[str, ...] = tuple(),
        project: str = "",
        output_directory: str = "",
    ) -> None:
        super().__init__()
        self.mode = mode
        if classes:
            self.classes = classes
        else:
            self.classes = []
        self.show_ancestors = show_ancestors
        self.all_ancestors = all_ancestors
        self.show_associated = show_associated
        self.all_associated = all_associated
        self.show_builtin = show_builtin
        self.module_names = module_names
        self.only_classnames = only_classnames
        self.output_format = output_format
        self.colorized = colorized
        self.max_color_depth = max_color_depth
        self.color_palette = color_palette
        self.ignore_list = ignore_list
        self.project = project
        self.output_directory = output_directory


class TestFileOptions(TypedDict):
    source_roots: list[str]
    output_formats: list[str]
    command_line_args: list[str]


class FunctionalPyreverseTestfile(NamedTuple):
    """Named tuple containing the test file and the expected output."""

    source: Path
    options: TestFileOptions


def get_functional_test_files(
    root_directory: Path,
) -> list[FunctionalPyreverseTestfile]:
    """Get all functional test files from the given directory."""
    test_files = []
    for path in root_directory.rglob("*.py"):
        if path.stem.startswith("_"):
            continue
        config_file = path.with_suffix(".rc")
        if config_file.exists():
            test_files.append(
                FunctionalPyreverseTestfile(
                    source=path, options=_read_config(config_file)
                )
            )
        else:
            test_files.append(
                FunctionalPyreverseTestfile(
                    source=path,
                    options={
                        "source_roots": [],
                        "output_formats": ["mmd"],
                        "command_line_args": [],
                    },
                )
            )
    return test_files


def _read_config(config_file: Path) -> TestFileOptions:
    config = configparser.ConfigParser()
    config.read(str(config_file))
    source_roots = config.get("testoptions", "source_roots", fallback=None)
    return {
        "source_roots": source_roots.split(",") if source_roots else [],
        "output_formats": config.get(
            "testoptions", "output_formats", fallback="mmd"
        ).split(","),
        "command_line_args": shlex.split(
            config.get("testoptions", "command_line_args", fallback="")
        ),
    }
