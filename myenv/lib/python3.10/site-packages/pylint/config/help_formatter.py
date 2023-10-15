# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import argparse

from pylint.config.callback_actions import _CallbackAction
from pylint.constants import DEFAULT_PYLINT_HOME, OLD_DEFAULT_PYLINT_HOME


class _HelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Formatter for the help message emitted by argparse."""

    def _get_help_string(self, action: argparse.Action) -> str | None:
        """Copied from argparse.ArgumentDefaultsHelpFormatter."""
        assert action.help
        help_string = action.help

        # CallbackActions don't have a default
        if isinstance(action, _CallbackAction):
            return help_string

        if "%(default)" not in help_string:
            if action.default is not argparse.SUPPRESS:
                defaulting_nargs = [argparse.OPTIONAL, argparse.ZERO_OR_MORE]
                if action.option_strings or action.nargs in defaulting_nargs:
                    help_string += " (default: %(default)s)"
        return help_string

    @staticmethod
    def get_long_description() -> str:
        return f"""
Environment variables:
    The following environment variables are used:
        * PYLINTHOME    Path to the directory where persistent data for the run will
                        be stored. If not found, it defaults to '{DEFAULT_PYLINT_HOME}'
                        or '{OLD_DEFAULT_PYLINT_HOME}' (in the current working directory).
        * PYLINTRC      Path to the configuration file. See the documentation for the method used
                        to search for configuration file.

Output:
    Using the default text output, the message format is :

        MESSAGE_TYPE: LINE_NUM:[OBJECT:] MESSAGE

    There are 5 kind of message types :
        * (I) info,         for informational messages
        * (C) convention,   for programming standard violation
        * (R) refactor,     for bad code smell
        * (W) warning,      for python specific problems
        * (E) error,        for probable bugs in the code
        * (F) fatal,        if an error occurred which prevented pylint from doing further processing.

Output status code:
    Pylint should leave with following bitwise status codes:
        * 0 if everything went fine
        * 1 if a fatal message was issued
        * 2 if an error message was issued
        * 4 if a warning message was issued
        * 8 if a refactor message was issued
        * 16 if a convention message was issued
        * 32 on usage error
"""
