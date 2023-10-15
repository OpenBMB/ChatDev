# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Arguments manager class used to handle command-line arguments and options."""

from __future__ import annotations

import argparse
import configparser
import copy
import optparse  # pylint: disable=deprecated-module
import os
import re
import sys
import textwrap
import warnings
from collections import OrderedDict
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, TextIO, Union

import tomlkit

from pylint import utils
from pylint.config.argument import (
    _Argument,
    _CallableArgument,
    _ExtendArgument,
    _StoreArgument,
    _StoreNewNamesArgument,
    _StoreOldNamesArgument,
    _StoreTrueArgument,
)
from pylint.config.exceptions import (
    UnrecognizedArgumentAction,
    _UnrecognizedOptionError,
)
from pylint.config.help_formatter import _HelpFormatter
from pylint.config.option import Option
from pylint.config.option_parser import OptionParser  # type: ignore[attr-defined]
from pylint.config.options_provider_mixin import (  # type: ignore[attr-defined]
    OptionsProviderMixIn,
)
from pylint.config.utils import _convert_option_to_argument, _parse_rich_type_value
from pylint.constants import MAIN_CHECKER_NAME
from pylint.typing import DirectoryNamespaceDict, OptionDict

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


if TYPE_CHECKING:
    from pylint.config.arguments_provider import _ArgumentsProvider

ConfigProvider = Union["_ArgumentsProvider", OptionsProviderMixIn]


# pylint: disable-next=too-many-instance-attributes
class _ArgumentsManager:
    """Arguments manager class used to handle command-line arguments and options."""

    def __init__(
        self, prog: str, usage: str | None = None, description: str | None = None
    ) -> None:
        self._config = argparse.Namespace()
        """Namespace for all options."""

        self._base_config = self._config
        """Fall back Namespace object created during initialization.

        This is necessary for the per-directory configuration support. Whenever we
        fail to match a file with a directory we fall back to the Namespace object
        created during initialization.
        """

        self._arg_parser = argparse.ArgumentParser(
            prog=prog,
            usage=usage or "%(prog)s [options]",
            description=description,
            formatter_class=_HelpFormatter,
            # Needed to let 'pylint-config' overwrite the -h command
            conflict_handler="resolve",
        )
        """The command line argument parser."""

        self._argument_groups_dict: dict[str, argparse._ArgumentGroup] = {}
        """Dictionary of all the argument groups."""

        self._option_dicts: dict[str, OptionDict] = {}
        """All option dictionaries that have been registered."""

        self._directory_namespaces: DirectoryNamespaceDict = {}
        """Mapping of directories and their respective namespace objects."""

        # TODO: 3.0: Remove deprecated attributes introduced to keep API
        # parity with optparse. Until '_maxlevel'
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            self.reset_parsers(usage or "")
        # list of registered options providers
        self._options_providers: list[ConfigProvider] = []
        # dictionary associating option name to checker
        self._all_options: OrderedDict[str, ConfigProvider] = OrderedDict()
        self._short_options: dict[str, str] = {}
        self._nocallback_options: dict[ConfigProvider, str] = {}
        self._mygroups: dict[str, optparse.OptionGroup] = {}
        # verbosity
        self._maxlevel: int = 0

    @property
    def config(self) -> argparse.Namespace:
        """Namespace for all options."""
        return self._config

    @config.setter
    def config(self, value: argparse.Namespace) -> None:
        self._config = value

    @property
    def options_providers(self) -> list[ConfigProvider]:
        # TODO: 3.0: Remove deprecated attribute.
        warnings.warn(
            "options_providers has been deprecated. It will be removed in pylint 3.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._options_providers

    @options_providers.setter
    def options_providers(self, value: list[ConfigProvider]) -> None:
        warnings.warn(
            "Setting options_providers has been deprecated. It will be removed in pylint 3.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._options_providers = value

    def _register_options_provider(self, provider: _ArgumentsProvider) -> None:
        """Register an options provider and load its defaults."""
        for opt, optdict in provider.options:
            self._option_dicts[opt] = optdict
            argument = _convert_option_to_argument(opt, optdict)
            section = argument.section or provider.name.capitalize()

            section_desc = provider.option_groups_descs.get(section, None)

            # We exclude main since its docstring comes from PyLinter
            if provider.name != MAIN_CHECKER_NAME and provider.__doc__:
                section_desc = provider.__doc__.split("\n\n")[0]

            self._add_arguments_to_parser(section, section_desc, argument)

        self._load_default_argument_values()

    def _add_arguments_to_parser(
        self, section: str, section_desc: str | None, argument: _Argument
    ) -> None:
        """Add an argument to the correct argument section/group."""
        try:
            section_group = self._argument_groups_dict[section]
        except KeyError:
            if section_desc:
                section_group = self._arg_parser.add_argument_group(
                    section, section_desc
                )
            else:
                section_group = self._arg_parser.add_argument_group(title=section)
            self._argument_groups_dict[section] = section_group
        self._add_parser_option(section_group, argument)

    @staticmethod
    def _add_parser_option(
        section_group: argparse._ArgumentGroup, argument: _Argument
    ) -> None:
        """Add an argument."""
        if isinstance(argument, _StoreArgument):
            section_group.add_argument(
                *argument.flags,
                action=argument.action,
                default=argument.default,
                type=argument.type,  # type: ignore[arg-type] # incorrect typing in typeshed
                help=argument.help,
                metavar=argument.metavar,
                choices=argument.choices,
            )
        elif isinstance(argument, _StoreOldNamesArgument):
            section_group.add_argument(
                *argument.flags,
                **argument.kwargs,
                action=argument.action,
                default=argument.default,
                type=argument.type,  # type: ignore[arg-type] # incorrect typing in typeshed
                help=argument.help,
                metavar=argument.metavar,
                choices=argument.choices,
            )
            # We add the old name as hidden option to make it's default value gets loaded when
            # argparse initializes all options from the checker
            assert argument.kwargs["old_names"]
            for old_name in argument.kwargs["old_names"]:
                section_group.add_argument(
                    f"--{old_name}",
                    action="store",
                    default=argument.default,
                    type=argument.type,  # type: ignore[arg-type] # incorrect typing in typeshed
                    help=argparse.SUPPRESS,
                    metavar=argument.metavar,
                    choices=argument.choices,
                )
        elif isinstance(argument, _StoreNewNamesArgument):
            section_group.add_argument(
                *argument.flags,
                **argument.kwargs,
                action=argument.action,
                default=argument.default,
                type=argument.type,  # type: ignore[arg-type] # incorrect typing in typeshed
                help=argument.help,
                metavar=argument.metavar,
                choices=argument.choices,
            )
        elif isinstance(argument, _StoreTrueArgument):
            section_group.add_argument(
                *argument.flags,
                action=argument.action,
                default=argument.default,
                help=argument.help,
            )
        elif isinstance(argument, _CallableArgument):
            section_group.add_argument(
                *argument.flags,
                **argument.kwargs,
                action=argument.action,
                help=argument.help,
                metavar=argument.metavar,
            )
        elif isinstance(argument, _ExtendArgument):
            section_group.add_argument(
                *argument.flags,
                action=argument.action,
                default=argument.default,
                type=argument.type,  # type: ignore[arg-type] # incorrect typing in typeshed
                help=argument.help,
                metavar=argument.metavar,
                choices=argument.choices,
                dest=argument.dest,
            )
        else:
            raise UnrecognizedArgumentAction

    def _load_default_argument_values(self) -> None:
        """Loads the default values of all registered options."""
        self.config = self._arg_parser.parse_args([], self.config)

    def _parse_configuration_file(self, arguments: list[str]) -> None:
        """Parse the arguments found in a configuration file into the namespace."""
        try:
            self.config, parsed_args = self._arg_parser.parse_known_args(
                arguments, self.config
            )
        except SystemExit:
            sys.exit(32)
        unrecognized_options: list[str] = []
        for opt in parsed_args:
            if opt.startswith("--"):
                unrecognized_options.append(opt[2:])
        if unrecognized_options:
            raise _UnrecognizedOptionError(options=unrecognized_options)

    def _parse_command_line_configuration(
        self, arguments: Sequence[str] | None = None
    ) -> list[str]:
        """Parse the arguments found on the command line into the namespace."""
        arguments = sys.argv[1:] if arguments is None else arguments

        self.config, parsed_args = self._arg_parser.parse_known_args(
            arguments, self.config
        )

        return parsed_args

    def reset_parsers(self, usage: str = "") -> None:  # pragma: no cover
        """DEPRECATED."""
        warnings.warn(
            "reset_parsers has been deprecated. Parsers should be instantiated "
            "once during initialization and do not need to be reset.",
            DeprecationWarning,
            stacklevel=2,
        )
        # configuration file parser
        self.cfgfile_parser = configparser.ConfigParser(
            inline_comment_prefixes=("#", ";")
        )
        # command line parser
        self.cmdline_parser = OptionParser(Option, usage=usage)
        self.cmdline_parser.options_manager = self
        self._optik_option_attrs = set(self.cmdline_parser.option_class.ATTRS)

    def register_options_provider(
        self, provider: ConfigProvider, own_group: bool = True
    ) -> None:  # pragma: no cover
        """DEPRECATED: Register an options provider."""
        warnings.warn(
            "register_options_provider has been deprecated. Options providers and "
            "arguments providers should be registered by initializing ArgumentsProvider. "
            "This automatically registers the provider on the ArgumentsManager.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.options_providers.append(provider)
        non_group_spec_options = [
            option for option in provider.options if "group" not in option[1]
        ]
        groups = getattr(provider, "option_groups", ())
        if own_group and non_group_spec_options:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=DeprecationWarning)
                self.add_option_group(
                    provider.name.upper(),
                    provider.__doc__,
                    non_group_spec_options,
                    provider,
                )
        else:
            for opt, optdict in non_group_spec_options:
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=DeprecationWarning)
                    self.add_optik_option(provider, self.cmdline_parser, opt, optdict)
        for gname, gdoc in groups:
            gname = gname.upper()
            goptions = [
                option
                for option in provider.options
                if option[1].get("group", "").upper() == gname  # type: ignore[union-attr]
            ]
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=DeprecationWarning)
                self.add_option_group(gname, gdoc, goptions, provider)

    def add_option_group(
        self,
        group_name: str,
        _: str | None,
        options: list[tuple[str, OptionDict]],
        provider: ConfigProvider,
    ) -> None:  # pragma: no cover
        """DEPRECATED."""
        warnings.warn(
            "add_option_group has been deprecated. Option groups should be "
            "registered by initializing ArgumentsProvider. "
            "This automatically registers the group on the ArgumentsManager.",
            DeprecationWarning,
            stacklevel=2,
        )
        # add option group to the command line parser
        if group_name in self._mygroups:
            group = self._mygroups[group_name]
        else:
            group = optparse.OptionGroup(
                self.cmdline_parser, title=group_name.capitalize()
            )
            self.cmdline_parser.add_option_group(group)
            self._mygroups[group_name] = group
            # add section to the config file
            if (
                group_name != "DEFAULT"
                and group_name not in self.cfgfile_parser._sections  # type: ignore[attr-defined]
            ):
                self.cfgfile_parser.add_section(group_name)
        # add provider's specific options
        for opt, optdict in options:
            if not isinstance(optdict.get("action", "store"), str):
                optdict["action"] = "callback"
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=DeprecationWarning)
                self.add_optik_option(provider, group, opt, optdict)

    def add_optik_option(
        self,
        provider: ConfigProvider,
        optikcontainer: optparse.OptionParser | optparse.OptionGroup,
        opt: str,
        optdict: OptionDict,
    ) -> None:  # pragma: no cover
        """DEPRECATED."""
        warnings.warn(
            "add_optik_option has been deprecated. Options should be automatically "
            "added by initializing an ArgumentsProvider.",
            DeprecationWarning,
            stacklevel=2,
        )
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            args, optdict = self.optik_option(provider, opt, optdict)
        option = optikcontainer.add_option(*args, **optdict)
        self._all_options[opt] = provider
        self._maxlevel = max(self._maxlevel, option.level or 0)

    def optik_option(
        self, provider: ConfigProvider, opt: str, optdict: OptionDict
    ) -> tuple[list[str], OptionDict]:  # pragma: no cover
        """DEPRECATED: Get our personal option definition and return a suitable form for
        use with optik/optparse.
        """
        warnings.warn(
            "optik_option has been deprecated. Parsing of option dictionaries should be done "
            "automatically by initializing an ArgumentsProvider.",
            DeprecationWarning,
            stacklevel=2,
        )
        optdict = copy.copy(optdict)
        if "action" in optdict:
            self._nocallback_options[provider] = opt
        else:
            optdict["action"] = "callback"
            optdict["callback"] = self.cb_set_provider_option
        # default is handled here and *must not* be given to optik if you
        # want the whole machinery to work
        if "default" in optdict:
            if (
                "help" in optdict
                and optdict.get("default") is not None
                and optdict["action"] not in ("store_true", "store_false")
            ):
                optdict["help"] += " [current: %default]"  # type: ignore[operator]
            del optdict["default"]
        args = ["--" + str(opt)]
        if "short" in optdict:
            self._short_options[optdict["short"]] = opt  # type: ignore[index]
            args.append("-" + optdict["short"])  # type: ignore[operator]
            del optdict["short"]
        # cleanup option definition dict before giving it to optik
        for key in list(optdict.keys()):
            if key not in self._optik_option_attrs:
                optdict.pop(key)
        return args, optdict

    def generate_config(
        self, stream: TextIO | None = None, skipsections: tuple[str, ...] = ()
    ) -> None:  # pragma: no cover
        """DEPRECATED: Write a configuration file according to the current configuration
        into the given stream or stdout.
        """
        warnings.warn(
            "generate_config has been deprecated. It will be removed in pylint 3.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        options_by_section = {}
        sections = []
        for group in sorted(
            self._arg_parser._action_groups,
            key=lambda x: (x.title != "Main", x.title),
        ):
            group_name = group.title
            assert group_name
            if group_name in skipsections:
                continue

            options = []
            option_actions = [
                i
                for i in group._group_actions
                if not isinstance(i, argparse._SubParsersAction)
            ]
            for opt in sorted(option_actions, key=lambda x: x.option_strings[0][2:]):
                if "--help" in opt.option_strings:
                    continue

                optname = opt.option_strings[0][2:]

                try:
                    optdict = self._option_dicts[optname]
                except KeyError:
                    continue

                options.append(
                    (
                        optname,
                        optdict,
                        getattr(self.config, optname.replace("-", "_")),
                    )
                )

                options = [
                    (n, d, v) for (n, d, v) in options if not d.get("deprecated")
                ]

            if options:
                sections.append(group_name)
                options_by_section[group_name] = options
        stream = stream or sys.stdout
        printed = False
        for section in sections:
            if printed:
                print("\n", file=stream)
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=DeprecationWarning)
                utils.format_section(
                    stream, section.upper(), sorted(options_by_section[section])
                )
            printed = True

    def load_provider_defaults(self) -> None:  # pragma: no cover
        """DEPRECATED: Initialize configuration using default values."""
        warnings.warn(
            "load_provider_defaults has been deprecated. Parsing of option defaults should be done "
            "automatically by initializing an ArgumentsProvider.",
            DeprecationWarning,
            stacklevel=2,
        )
        for provider in self.options_providers:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=DeprecationWarning)
                provider.load_defaults()

    def read_config_file(
        self, config_file: Path | None = None, verbose: bool = False
    ) -> None:  # pragma: no cover
        """DEPRECATED: Read the configuration file but do not load it (i.e. dispatching
        values to each option's provider).

        :raises OSError: When the specified config file doesn't exist
        """
        warnings.warn(
            "read_config_file has been deprecated. It will be removed in pylint 3.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        if not config_file:
            if verbose:
                print(
                    "No config file found, using default configuration", file=sys.stderr
                )
            return
        config_file = Path(os.path.expandvars(config_file)).expanduser()
        if not config_file.exists():
            raise OSError(f"The config file {str(config_file)} doesn't exist!")
        parser = self.cfgfile_parser
        if config_file.suffix == ".toml":
            try:
                self._parse_toml(config_file, parser)
            except tomllib.TOMLDecodeError:
                pass
        else:
            # Use this encoding in order to strip the BOM marker, if any.
            with open(config_file, encoding="utf_8_sig") as fp:
                parser.read_file(fp)
            # normalize each section's title
            for sect, values in list(parser._sections.items()):  # type: ignore[attr-defined]
                if sect.startswith("pylint."):
                    sect = sect[len("pylint.") :]
                if not sect.isupper() and values:
                    parser._sections[sect.upper()] = values  # type: ignore[attr-defined]

        if verbose:
            print(f"Using config file '{config_file}'", file=sys.stderr)

    @staticmethod
    def _parse_toml(
        config_file: Path, parser: configparser.ConfigParser
    ) -> None:  # pragma: no cover
        """DEPRECATED: Parse and handle errors of a toml configuration file.

        TODO: 3.0: Remove deprecated method.
        """
        with open(config_file, mode="rb") as fp:
            content = tomllib.load(fp)
        try:
            sections_values = content["tool"]["pylint"]
        except KeyError:
            return
        for section, values in sections_values.items():
            section_name = section.upper()
            # TOML has rich types, convert values to
            # strings as ConfigParser expects.
            if not isinstance(values, dict):
                continue
            for option, value in values.items():
                if isinstance(value, bool):
                    values[option] = "yes" if value else "no"
                elif isinstance(value, list):
                    values[option] = ",".join(value)
                else:
                    values[option] = str(value)
            for option, value in values.items():
                try:
                    parser.set(section_name, option, value=value)
                except configparser.NoSectionError:
                    parser.add_section(section_name)
                    parser.set(section_name, option, value=value)

    def load_config_file(self) -> None:  # pragma: no cover
        """DEPRECATED: Dispatch values previously read from a configuration file to each
        option's provider.
        """
        warnings.warn(
            "load_config_file has been deprecated. It will be removed in pylint 3.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        parser = self.cfgfile_parser
        for section in parser.sections():
            for option, value in parser.items(section):
                try:
                    self.global_set_option(option, value)
                except (KeyError, optparse.OptionError):
                    continue

    def load_configuration(self, **kwargs: Any) -> None:  # pragma: no cover
        """DEPRECATED: Override configuration according to given parameters."""
        warnings.warn(
            "load_configuration has been deprecated. It will be removed in pylint 3.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            return self.load_configuration_from_config(kwargs)

    def load_configuration_from_config(
        self, config: dict[str, Any]
    ) -> None:  # pragma: no cover
        warnings.warn(
            "DEPRECATED: load_configuration_from_config has been deprecated. It will be removed in pylint 3.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        for opt, opt_value in config.items():
            opt = opt.replace("_", "-")
            provider = self._all_options[opt]
            provider.set_option(opt, opt_value)

    def load_command_line_configuration(
        self, args: list[str] | None = None
    ) -> list[str]:  # pragma: no cover
        """DEPRECATED: Override configuration according to command line parameters.

        return additional arguments
        """
        warnings.warn(
            "load_command_line_configuration has been deprecated. It will be removed in pylint 3.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        args = sys.argv[1:] if args is None else list(args)
        (options, args) = self.cmdline_parser.parse_args(args=args)
        for provider in self._nocallback_options:
            config = provider.config
            for attr in config.__dict__.keys():
                value = getattr(options, attr, None)
                if value is None:
                    continue
                setattr(config, attr, value)
        return args  # type: ignore[return-value]

    def help(self, level: int | None = None) -> str:
        """Return the usage string based on the available options."""
        if level is not None:
            warnings.warn(
                "Supplying a 'level' argument to help() has been deprecated."
                "You can call help() without any arguments.",
                DeprecationWarning,
                stacklevel=2,
            )
        return self._arg_parser.format_help()

    def cb_set_provider_option(  # pragma: no cover
        self, option: Any, opt: Any, value: Any, parser: Any
    ) -> None:
        """DEPRECATED: Optik callback for option setting."""
        # TODO: 3.0: Remove deprecated method.
        warnings.warn(
            "cb_set_provider_option has been deprecated. It will be removed in pylint 3.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        if opt.startswith("--"):
            # remove -- on long option
            opt = opt[2:]
        else:
            # short option, get its long equivalent
            opt = self._short_options[opt[1:]]
        # trick since we can't set action='store_true' on options
        if value is None:
            value = 1
        self.set_option(opt, value)

    def global_set_option(self, opt: str, value: Any) -> None:  # pragma: no cover
        """DEPRECATED: Set option on the correct option provider."""
        # TODO: 3.0: Remove deprecated method.
        warnings.warn(
            "global_set_option has been deprecated. You can use _arguments_manager.set_option "
            "or linter.set_option to set options on the global configuration object.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.set_option(opt, value)

    def _generate_config_file(self, *, minimal: bool = False) -> str:
        """Write a configuration file according to the current configuration into
        stdout.
        """
        toml_doc = tomlkit.document()
        pylint_tool_table = tomlkit.table(is_super_table=True)
        toml_doc.add(tomlkit.key(["tool", "pylint"]), pylint_tool_table)

        for group in sorted(
            self._arg_parser._action_groups,
            key=lambda x: (x.title != "Main", x.title),
        ):
            # Skip the options section with the --help option
            if group.title in {"options", "optional arguments", "Commands"}:
                continue

            # Skip sections without options such as "positional arguments"
            if not group._group_actions:
                continue

            group_table = tomlkit.table()
            option_actions = [
                i
                for i in group._group_actions
                if not isinstance(i, argparse._SubParsersAction)
            ]
            for action in sorted(option_actions, key=lambda x: x.option_strings[0][2:]):
                optname = action.option_strings[0][2:]

                # We skip old name options that don't have their own optdict
                try:
                    optdict = self._option_dicts[optname]
                except KeyError:
                    continue

                if optdict.get("hide_from_config_file"):
                    continue

                # Add help comment
                if not minimal:
                    help_msg = optdict.get("help", "")
                    assert isinstance(help_msg, str)
                    help_text = textwrap.wrap(help_msg, width=79)
                    for line in help_text:
                        group_table.add(tomlkit.comment(line))

                # Get current value of option
                value = getattr(self.config, optname.replace("-", "_"))

                # Create a comment if the option has no value
                if not value:
                    if not minimal:
                        group_table.add(tomlkit.comment(f"{optname} ="))
                        group_table.add(tomlkit.nl())
                    continue

                # Skip deprecated options
                if "kwargs" in optdict:
                    assert isinstance(optdict["kwargs"], dict)
                    if "new_names" in optdict["kwargs"]:
                        continue

                # Tomlkit doesn't support regular expressions
                if isinstance(value, re.Pattern):
                    value = value.pattern
                elif isinstance(value, (list, tuple)) and isinstance(
                    value[0], re.Pattern
                ):
                    value = [i.pattern for i in value]

                # Handle tuples that should be strings
                if optdict.get("type") == "py_version":
                    value = ".".join(str(i) for i in value)

                # Check if it is default value if we are in minimal mode
                if minimal and value == optdict.get("default"):
                    continue

                # Add to table
                group_table.add(optname, value)
                group_table.add(tomlkit.nl())

            assert group.title
            if group_table:
                pylint_tool_table.add(group.title.lower(), group_table)

        toml_string = tomlkit.dumps(toml_doc)

        # Make sure the string we produce is valid toml and can be parsed
        tomllib.loads(toml_string)

        return str(toml_string)

    def set_option(
        self,
        optname: str,
        value: Any,
        action: str | None = "default_value",
        optdict: None | str | OptionDict = "default_value",
    ) -> None:
        """Set an option on the namespace object."""
        # TODO: 3.0: Remove deprecated arguments.
        if action != "default_value":
            warnings.warn(
                "The 'action' argument has been deprecated. You can use set_option "
                "without the 'action' or 'optdict' arguments.",
                DeprecationWarning,
                stacklevel=2,
            )
        if optdict != "default_value":
            warnings.warn(
                "The 'optdict' argument has been deprecated. You can use set_option "
                "without the 'action' or 'optdict' arguments.",
                DeprecationWarning,
                stacklevel=2,
            )

        self.config = self._arg_parser.parse_known_args(
            [f"--{optname.replace('_', '-')}", _parse_rich_type_value(value)],
            self.config,
        )[0]
