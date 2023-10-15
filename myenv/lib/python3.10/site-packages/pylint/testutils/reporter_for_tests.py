# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

from io import StringIO
from os import getcwd, sep
from typing import TYPE_CHECKING

from pylint.message import Message
from pylint.reporters import BaseReporter

if TYPE_CHECKING:
    from pylint.reporters.ureports.nodes import Section


class GenericTestReporter(BaseReporter):
    """Reporter storing plain text messages."""

    out: StringIO

    def __init__(  # pylint: disable=super-init-not-called # See https://github.com/PyCQA/pylint/issues/4941
        self,
    ) -> None:
        self.path_strip_prefix: str = getcwd() + sep
        self.reset()

    def reset(self) -> None:
        self.out = StringIO()
        self.messages: list[Message] = []

    def handle_message(self, msg: Message) -> None:
        """Append messages to the list of messages of the reporter."""
        self.messages.append(msg)

    def finalize(self) -> str:
        """Format and print messages in the context of the path."""
        messages: list[str] = []
        for msg in self.messages:
            obj = ""
            if msg.obj:
                obj = f":{msg.obj}"
            messages.append(f"{msg.msg_id[0]}:{msg.line:>3}{obj}: {msg.msg}")

        messages.sort()
        for message in messages:
            print(message, file=self.out)

        result = self.out.getvalue()
        self.reset()
        return result

    def on_set_current_module(self, module: str, filepath: str | None) -> None:
        pass

    # pylint: enable=unused-argument

    def display_reports(self, layout: Section) -> None:
        """Ignore layouts."""

    def _display(self, layout: Section) -> None:
        pass


class MinimalTestReporter(BaseReporter):
    def on_set_current_module(self, module: str, filepath: str | None) -> None:
        self.messages = []

    def _display(self, layout: Section) -> None:
        pass


class FunctionalTestReporter(BaseReporter):
    def display_reports(self, layout: Section) -> None:
        """Ignore layouts and don't call self._display()."""

    def _display(self, layout: Section) -> None:
        pass
