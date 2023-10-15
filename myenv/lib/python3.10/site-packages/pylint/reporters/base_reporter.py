# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import os
import sys
import warnings
from typing import TYPE_CHECKING, TextIO
from warnings import warn

from pylint.message import Message
from pylint.reporters.ureports.nodes import Text
from pylint.utils import LinterStats

if TYPE_CHECKING:
    from pylint.lint.pylinter import PyLinter
    from pylint.reporters.ureports.nodes import Section


class BaseReporter:
    """Base class for reporters.

    symbols: show short symbolic names for messages.
    """

    extension = ""

    name = "base"
    """Name of the reporter."""

    def __init__(self, output: TextIO | None = None) -> None:
        if getattr(self, "__implements__", None):
            warnings.warn(
                "Using the __implements__ inheritance pattern for BaseReporter is no "
                "longer supported. Child classes should only inherit BaseReporter",
                DeprecationWarning,
                stacklevel=2,
            )
        self.linter: PyLinter
        self.section = 0
        self.out: TextIO = output or sys.stdout
        self.messages: list[Message] = []
        # Build the path prefix to strip to get relative paths
        self.path_strip_prefix = os.getcwd() + os.sep

    def handle_message(self, msg: Message) -> None:
        """Handle a new message triggered on the current file."""
        self.messages.append(msg)

    def set_output(self, output: TextIO | None = None) -> None:
        """Set output stream."""
        # TODO: 3.0: Remove deprecated method
        warn(
            "'set_output' will be removed in 3.0, please use 'reporter.out = stream' instead",
            DeprecationWarning,
            stacklevel=2,
        )
        self.out = output or sys.stdout

    def writeln(self, string: str = "") -> None:
        """Write a line in the output buffer."""
        print(string, file=self.out)

    def display_reports(self, layout: Section) -> None:
        """Display results encapsulated in the layout tree."""
        self.section = 0
        if layout.report_id:
            if isinstance(layout.children[0].children[0], Text):
                layout.children[0].children[0].data += f" ({layout.report_id})"
            else:
                raise ValueError(f"Incorrect child for {layout.children[0].children}")
        self._display(layout)

    def _display(self, layout: Section) -> None:
        """Display the layout."""
        raise NotImplementedError()

    def display_messages(self, layout: Section | None) -> None:
        """Hook for displaying the messages of the reporter.

        This will be called whenever the underlying messages
        needs to be displayed. For some reporters, it probably
        doesn't make sense to display messages as soon as they
        are available, so some mechanism of storing them could be used.
        This method can be implemented to display them after they've
        been aggregated.
        """

    # Event callbacks

    def on_set_current_module(self, module: str, filepath: str | None) -> None:
        """Hook called when a module starts to be analysed."""

    def on_close(
        self,
        stats: LinterStats,
        previous_stats: LinterStats | None,
    ) -> None:
        """Hook called when a module finished analyzing."""
