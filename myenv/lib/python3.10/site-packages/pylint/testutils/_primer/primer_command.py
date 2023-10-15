# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import abc
import argparse
import sys
from pathlib import Path
from typing import Dict

from pylint.reporters.json_reporter import OldJsonExport
from pylint.testutils._primer import PackageToLint

if sys.version_info >= (3, 8):
    from typing import TypedDict
else:
    from typing_extensions import TypedDict


class PackageData(TypedDict):
    commit: str
    messages: list[OldJsonExport]


PackageMessages = Dict[str, PackageData]


class PrimerCommand:
    """Generic primer action with required arguments."""

    def __init__(
        self,
        primer_directory: Path,
        packages: dict[str, PackageToLint],
        config: argparse.Namespace,
    ) -> None:
        self.primer_directory = primer_directory
        self.packages = packages
        self.config = config

    @abc.abstractmethod
    def run(self) -> None:
        pass
