# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Everything related to the 'pylint-config generate' command."""


from __future__ import annotations

import warnings
from io import StringIO
from typing import TYPE_CHECKING

from pylint.config._pylint_config import utils
from pylint.config._pylint_config.help_message import get_subparser_help

if TYPE_CHECKING:
    from pylint.lint.pylinter import PyLinter


def generate_interactive_config(linter: PyLinter) -> None:
    print("Starting interactive pylint configuration generation")

    format_type = utils.get_and_validate_format()
    minimal = format_type == "toml" and utils.get_minimal_setting()
    to_file, output_file_name = utils.get_and_validate_output_file()

    if format_type == "toml":
        config_string = linter._generate_config_file(minimal=minimal)
    else:
        output_stream = StringIO()
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            linter.generate_config(stream=output_stream, skipsections=("Commands",))
            config_string = output_stream.getvalue()

    if to_file:
        with open(output_file_name, "w", encoding="utf-8") as f:
            print(config_string, file=f)
        print(f"Wrote configuration file to {output_file_name.resolve()}")
    else:
        print(config_string)


def handle_generate_command(linter: PyLinter) -> int:
    """Handle 'pylint-config generate'."""
    # Interactively generate a pylint configuration
    if linter.config.interactive:
        generate_interactive_config(linter)
        return 0
    print(get_subparser_help(linter, "generate"))
    return 32
