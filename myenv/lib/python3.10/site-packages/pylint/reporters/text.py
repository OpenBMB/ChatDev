# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Plain text reporters:.

:text: the default one grouping messages by module
:colorized: an ANSI colorized text reporter
"""

from __future__ import annotations

import os
import re
import sys
import warnings
from dataclasses import asdict, fields
from typing import TYPE_CHECKING, Dict, NamedTuple, Optional, TextIO, cast, overload

from pylint.message import Message
from pylint.reporters import BaseReporter
from pylint.reporters.ureports.text_writer import TextWriter
from pylint.utils import _splitstrip

if TYPE_CHECKING:
    from pylint.lint import PyLinter
    from pylint.reporters.ureports.nodes import Section


class MessageStyle(NamedTuple):
    """Styling of a message."""

    color: str | None
    """The color name (see `ANSI_COLORS` for available values)
    or the color number when 256 colors are available.
    """
    style: tuple[str, ...] = ()
    """Tuple of style strings (see `ANSI_COLORS` for available values)."""


ColorMappingDict = Dict[str, MessageStyle]

TITLE_UNDERLINES = ["", "=", "-", "."]

ANSI_PREFIX = "\033["
ANSI_END = "m"
ANSI_RESET = "\033[0m"
ANSI_STYLES = {
    "reset": "0",
    "bold": "1",
    "italic": "3",
    "underline": "4",
    "blink": "5",
    "inverse": "7",
    "strike": "9",
}
ANSI_COLORS = {
    "reset": "0",
    "black": "30",
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "magenta": "35",
    "cyan": "36",
    "white": "37",
}

MESSAGE_FIELDS = {i.name for i in fields(Message)}
"""All fields of the Message class."""


def _get_ansi_code(msg_style: MessageStyle) -> str:
    """Return ANSI escape code corresponding to color and style.

    :param msg_style: the message style

    :raise KeyError: if a nonexistent color or style identifier is given

    :return: the built escape code
    """
    ansi_code = [ANSI_STYLES[effect] for effect in msg_style.style]
    if msg_style.color:
        if msg_style.color.isdigit():
            ansi_code.extend(["38", "5"])
            ansi_code.append(msg_style.color)
        else:
            ansi_code.append(ANSI_COLORS[msg_style.color])
    if ansi_code:
        return ANSI_PREFIX + ";".join(ansi_code) + ANSI_END
    return ""


@overload
def colorize_ansi(
    msg: str,
    msg_style: MessageStyle | None = ...,
) -> str:
    ...


@overload
def colorize_ansi(
    msg: str,
    msg_style: str | None = ...,
    style: str = ...,
    *,
    color: str | None = ...,
) -> str:
    # Remove for pylint 3.0
    ...


def colorize_ansi(
    msg: str,
    msg_style: MessageStyle | str | None = None,
    style: str = "",
    **kwargs: str | None,
) -> str:
    r"""colorize message by wrapping it with ANSI escape codes

    :param msg: the message string to colorize

    :param msg_style: the message style
        or color (for backwards compatibility): the color of the message style

    :param style: the message's style elements, this will be deprecated

    :param \**kwargs: used to accept `color` parameter while it is being deprecated

    :return: the ANSI escaped string
    """
    # TODO: 3.0: Remove deprecated typing and only accept MessageStyle as parameter
    if not isinstance(msg_style, MessageStyle):
        warnings.warn(
            "In pylint 3.0, the colorize_ansi function of Text reporters will only accept a "
            "MessageStyle parameter",
            DeprecationWarning,
            stacklevel=2,
        )
        color = kwargs.get("color")
        style_attrs = tuple(_splitstrip(style))
        msg_style = MessageStyle(color or msg_style, style_attrs)
    # If both color and style are not defined, then leave the text as is
    if msg_style.color is None and len(msg_style.style) == 0:
        return msg
    escape_code = _get_ansi_code(msg_style)
    # If invalid (or unknown) color, don't wrap msg with ANSI codes
    if escape_code:
        return f"{escape_code}{msg}{ANSI_RESET}"
    return msg


def make_header(msg: Message) -> str:
    return f"************* Module {msg.module}"


class TextReporter(BaseReporter):
    """Reports messages and layouts in plain text."""

    name = "text"
    extension = "txt"
    line_format = "{path}:{line}:{column}: {msg_id}: {msg} ({symbol})"

    def __init__(self, output: TextIO | None = None) -> None:
        super().__init__(output)
        self._modules: set[str] = set()
        self._template = self.line_format
        self._fixed_template = self.line_format
        """The output format template with any unrecognized arguments removed."""

    def on_set_current_module(self, module: str, filepath: str | None) -> None:
        """Set the format template to be used and check for unrecognized arguments."""
        template = str(self.linter.config.msg_template or self._template)

        # Return early if the template is the same as the previous one
        if template == self._template:
            return

        # Set template to the currently selected template
        self._template = template

        # Check to see if all parameters in the template are attributes of the Message
        arguments = re.findall(r"\{(\w+?)(:.*)?\}", template)
        for argument in arguments:
            if argument[0] not in MESSAGE_FIELDS:
                warnings.warn(
                    f"Don't recognize the argument '{argument[0]}' in the --msg-template. "
                    "Are you sure it is supported on the current version of pylint?"
                )
                template = re.sub(r"\{" + argument[0] + r"(:.*?)?\}", "", template)
        self._fixed_template = template

    def write_message(self, msg: Message) -> None:
        """Convenience method to write a formatted message with class default
        template.
        """
        self_dict = asdict(msg)
        for key in ("end_line", "end_column"):
            self_dict[key] = self_dict[key] or ""

        self.writeln(self._fixed_template.format(**self_dict))

    def handle_message(self, msg: Message) -> None:
        """Manage message of different type and in the context of path."""
        if msg.module not in self._modules:
            self.writeln(make_header(msg))
            self._modules.add(msg.module)
        self.write_message(msg)

    def _display(self, layout: Section) -> None:
        """Launch layouts display."""
        print(file=self.out)
        TextWriter().format(layout, self.out)


class NoHeaderReporter(TextReporter):
    """Reports messages and layouts in plain text without a module header."""

    name = "no-header"

    def handle_message(self, msg: Message) -> None:
        """Write message(s) without module header."""
        if msg.module not in self._modules:
            self._modules.add(msg.module)
        self.write_message(msg)


class ParseableTextReporter(TextReporter):
    """A reporter very similar to TextReporter, but display messages in a form
    recognized by most text editors :

    <filename>:<linenum>:<msg>
    """

    name = "parseable"
    line_format = "{path}:{line}: [{msg_id}({symbol}), {obj}] {msg}"

    def __init__(self, output: TextIO | None = None) -> None:
        warnings.warn(
            f"{self.name} output format is deprecated. This is equivalent to --msg-template={self.line_format}",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(output)


class VSTextReporter(ParseableTextReporter):
    """Visual studio text reporter."""

    name = "msvs"
    line_format = "{path}({line}): [{msg_id}({symbol}){obj}] {msg}"


class ColorizedTextReporter(TextReporter):
    """Simple TextReporter that colorizes text output."""

    name = "colorized"
    COLOR_MAPPING: ColorMappingDict = {
        "I": MessageStyle("green"),
        "C": MessageStyle(None, ("bold",)),
        "R": MessageStyle("magenta", ("bold", "italic")),
        "W": MessageStyle("magenta"),
        "E": MessageStyle("red", ("bold",)),
        "F": MessageStyle("red", ("bold", "underline")),
        "S": MessageStyle("yellow", ("inverse",)),  # S stands for module Separator
    }

    def __init__(
        self,
        output: TextIO | None = None,
        color_mapping: (
            ColorMappingDict | dict[str, tuple[str | None, str]] | None
        ) = None,
    ) -> None:
        super().__init__(output)
        # TODO: 3.0: Remove deprecated typing and only accept ColorMappingDict as
        #  color_mapping parameter
        if color_mapping and not isinstance(
            list(color_mapping.values())[0], MessageStyle
        ):
            warnings.warn(
                "In pylint 3.0, the ColorizedTextReporter will only accept ColorMappingDict as "
                "color_mapping parameter",
                DeprecationWarning,
                stacklevel=2,
            )
            temp_color_mapping: ColorMappingDict = {}
            for key, value in color_mapping.items():
                color = value[0]
                style_attrs = tuple(_splitstrip(value[1]))  # type: ignore[arg-type]
                temp_color_mapping[key] = MessageStyle(color, style_attrs)
            color_mapping = temp_color_mapping
        else:
            color_mapping = cast(Optional[ColorMappingDict], color_mapping)
        self.color_mapping = color_mapping or ColorizedTextReporter.COLOR_MAPPING
        ansi_terms = ["xterm-16color", "xterm-256color"]
        if os.environ.get("TERM") not in ansi_terms:
            if sys.platform == "win32":
                # pylint: disable=import-outside-toplevel
                import colorama

                self.out = colorama.AnsiToWin32(self.out)

    def _get_decoration(self, msg_id: str) -> MessageStyle:
        """Returns the message style as defined in self.color_mapping."""
        return self.color_mapping.get(msg_id[0]) or MessageStyle(None)

    def handle_message(self, msg: Message) -> None:
        """Manage message of different types, and colorize output
        using ANSI escape codes.
        """
        if msg.module not in self._modules:
            msg_style = self._get_decoration("S")
            modsep = colorize_ansi(make_header(msg), msg_style)
            self.writeln(modsep)
            self._modules.add(msg.module)
        msg_style = self._get_decoration(msg.C)

        msg.msg = colorize_ansi(msg.msg, msg_style)
        msg.symbol = colorize_ansi(msg.symbol, msg_style)
        msg.category = colorize_ansi(msg.category, msg_style)
        msg.C = colorize_ansi(msg.C, msg_style)
        self.write_message(msg)


def register(linter: PyLinter) -> None:
    linter.register_reporter(TextReporter)
    linter.register_reporter(NoHeaderReporter)
    linter.register_reporter(ParseableTextReporter)
    linter.register_reporter(VSTextReporter)
    linter.register_reporter(ColorizedTextReporter)
