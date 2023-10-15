# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Everything related to the 'pylint-config -h' command and subcommands."""


from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pylint.lint.pylinter import PyLinter


def get_subparser_help(linter: PyLinter, command: str) -> str:
    """Get the help message for one of the subcommands."""
    # Make sure subparsers are initialized properly
    assert linter._arg_parser._subparsers
    subparser_action = linter._arg_parser._subparsers._group_actions[0]
    assert isinstance(subparser_action, argparse._SubParsersAction)

    for name, subparser in subparser_action.choices.items():
        assert isinstance(subparser, argparse.ArgumentParser)
        if name == command:
            # Remove last character which is an extra new line
            return subparser.format_help()[:-1]
    return ""  # pragma: no cover


def get_help(parser: argparse.ArgumentParser) -> str:
    """Get the help message for the main 'pylint-config' command.

    Taken from argparse.ArgumentParser.format_help.
    """
    formatter = parser._get_formatter()

    # usage
    formatter.add_usage(
        parser.usage, parser._actions, parser._mutually_exclusive_groups
    )

    # description
    formatter.add_text(parser.description)

    # positionals, optionals and user-defined groups
    for action_group in parser._action_groups:
        if action_group.title == "Subcommands":
            formatter.start_section(action_group.title)
            formatter.add_text(action_group.description)
            formatter.add_arguments(action_group._group_actions)
            formatter.end_section()

    # epilog
    formatter.add_text(parser.epilog)

    # determine help from format above
    return formatter.format_help()
