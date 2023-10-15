# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Everything related to the setup of the 'pylint-config' command."""


from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import Any

from pylint.config._pylint_config.help_message import get_help
from pylint.config.callback_actions import _AccessParserAction


class _HelpAction(_AccessParserAction):
    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = "--help",
    ) -> None:
        get_help(self.parser)


def _register_generate_config_options(parser: argparse.ArgumentParser) -> None:
    """Registers the necessary arguments on the parser."""
    parser.prog = "pylint-config"
    # Overwrite the help command
    parser.add_argument(
        "-h",
        "--help",
        action=_HelpAction,
        default=argparse.SUPPRESS,
        help="show this help message and exit",
        parser=parser,
    )

    # We use subparsers to create various subcommands under 'pylint-config'
    subparsers = parser.add_subparsers(dest="config_subcommand", title="Subcommands")

    # Add the generate command
    generate_parser = subparsers.add_parser(
        "generate", help="Generate a pylint configuration"
    )
    generate_parser.add_argument("--interactive", action="store_true")
