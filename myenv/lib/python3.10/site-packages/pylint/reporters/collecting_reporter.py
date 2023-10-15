# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

from typing import TYPE_CHECKING

from pylint.reporters.base_reporter import BaseReporter

if TYPE_CHECKING:
    from pylint.reporters.ureports.nodes import Section


class CollectingReporter(BaseReporter):
    """Collects messages."""

    name = "collector"

    def __init__(self) -> None:
        super().__init__()
        self.messages = []

    def reset(self) -> None:
        self.messages = []

    def _display(self, layout: Section) -> None:
        pass
