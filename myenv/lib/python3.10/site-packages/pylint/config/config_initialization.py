# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import sys
from glob import glob
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING

from pylint import reporters
from pylint.config.config_file_parser import _ConfigurationFileParser
from pylint.config.exceptions import _UnrecognizedOptionError
from pylint.utils import utils

if TYPE_CHECKING:
    from pylint.lint import PyLinter


def _config_initialization(
    linter: PyLinter,
    args_list: list[str],
    reporter: reporters.BaseReporter | reporters.MultiReporter | None = None,
    config_file: None | str | Path = None,
    verbose_mode: bool = False,
) -> list[str]:
    """Parse all available options, read config files and command line arguments and
    set options accordingly.
    """
    config_file = Path(config_file) if config_file else None

    # Set the current module to the configuration file
    # to allow raising messages on the configuration file.
    linter.set_current_module(str(config_file) if config_file else "")

    # Read the configuration file
    config_file_parser = _ConfigurationFileParser(verbose_mode, linter)
    try:
        config_data, config_args = config_file_parser.parse_config_file(
            file_path=config_file
        )
    except OSError as ex:
        print(ex, file=sys.stderr)
        sys.exit(32)

    # Run init hook, if present, before loading plugins
    if "init-hook" in config_data:
        exec(utils._unquote(config_data["init-hook"]))  # pylint: disable=exec-used

    # Load plugins if specified in the config file
    if "load-plugins" in config_data:
        linter.load_plugin_modules(utils._splitstrip(config_data["load-plugins"]))

    unrecognized_options_message = None
    # First we parse any options from a configuration file
    try:
        linter._parse_configuration_file(config_args)
    except _UnrecognizedOptionError as exc:
        unrecognized_options_message = ", ".join(exc.options)

    # Then, if a custom reporter is provided as argument, it may be overridden
    # by file parameters, so we re-set it here. We do this before command line
    # parsing, so it's still overridable by command line options
    if reporter:
        linter.set_reporter(reporter)

    # Set the current module to the command line
    # to allow raising messages on it
    linter.set_current_module("Command line")

    # Now we parse any options from the command line, so they can override
    # the configuration file
    parsed_args_list = linter._parse_command_line_configuration(args_list)

    # Remove the positional arguments separator from the list of arguments if it exists
    try:
        parsed_args_list.remove("--")
    except ValueError:
        pass

    # Check if there are any options that we do not recognize
    unrecognized_options: list[str] = []
    for opt in parsed_args_list:
        if opt.startswith("--"):
            unrecognized_options.append(opt[2:])
        elif opt.startswith("-"):
            unrecognized_options.append(opt[1:])
    if unrecognized_options:
        msg = ", ".join(unrecognized_options)
        try:
            linter._arg_parser.error(f"Unrecognized option found: {msg}")
        except SystemExit:
            sys.exit(32)

    # Now that config file and command line options have been loaded
    # with all disables, it is safe to emit messages
    if unrecognized_options_message is not None:
        linter.set_current_module(str(config_file) if config_file else "")
        linter.add_message(
            "unrecognized-option", args=unrecognized_options_message, line=0
        )

    linter._emit_stashed_messages()

    # Set the current module to configuration as we don't know where
    # the --load-plugins key is coming from
    linter.set_current_module("Command line or configuration file")

    # We have loaded configuration from config file and command line. Now, we can
    # load plugin specific configuration.
    linter.load_plugin_configuration()

    # Now that plugins are loaded, get list of all fail_on messages, and
    # enable them
    linter.enable_fail_on_messages()

    linter._parse_error_mode()

    # Link the base Namespace object on the current directory
    linter._directory_namespaces[Path(".").resolve()] = (linter.config, {})

    # parsed_args_list should now only be a list of inputs to lint.
    # All other options have been removed from the list.
    return list(
        chain.from_iterable(
            # NOTE: 'or [arg]' is needed in the case the input file or directory does
            # not exist and 'glob(arg)' cannot find anything. Without this we would
            # not be able to output the fatal import error for this module later on,
            # as it would get silently ignored.
            glob(arg, recursive=True) or [arg]
            for arg in parsed_args_list
        )
    )
