# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt


# pylint: disable=duplicate-code

from __future__ import annotations

import collections
import configparser
import contextlib
import copy
import optparse  # pylint: disable=deprecated-module
import os
import sys
import warnings
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any, TextIO

from pylint import utils
from pylint.config.option import Option
from pylint.config.option_parser import OptionParser  # type: ignore[attr-defined]
from pylint.typing import OptionDict

if TYPE_CHECKING:
    from pylint.config.options_provider_mixin import (  # type: ignore[attr-defined]
        OptionsProviderMixin,
    )

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def _expand_default(self: optparse.HelpFormatter, option: Option) -> str:
    """Patch OptionParser.expand_default with custom behaviour.

    This will handle defaults to avoid overriding values in the
    configuration file.
    """
    if self.parser is None or not self.default_tag:
        return str(option.help)
    optname = option._long_opts[0][2:]
    try:
        provider = self.parser.options_manager._all_options[optname]  # type: ignore[attr-defined]
    except KeyError:
        value = None
    else:
        optdict = provider.get_option_def(optname)
        optname = provider.option_attrname(optname, optdict)
        value = getattr(provider.config, optname, optdict)
        value = utils._format_option_value(optdict, value)
    if value is optparse.NO_DEFAULT or not value:
        value = self.NO_DEFAULT_VALUE
    return option.help.replace(self.default_tag, str(value))  # type: ignore[union-attr]


@contextlib.contextmanager
def _patch_optparse() -> Iterator[None]:
    # pylint: disable = redefined-variable-type
    orig_default = optparse.HelpFormatter
    try:
        optparse.HelpFormatter.expand_default = _expand_default  # type: ignore[assignment]
        yield
    finally:
        optparse.HelpFormatter.expand_default = orig_default  # type: ignore[assignment]


class OptionsManagerMixIn:
    """Handle configuration from both a configuration file and command line options."""

    def __init__(self, usage: str) -> None:
        # TODO: 3.0: Remove deprecated class
        warnings.warn(
            "OptionsManagerMixIn has been deprecated and will be removed in pylint 3.0",
            DeprecationWarning,
            stacklevel=2,
        )
        self.reset_parsers(usage)
        # list of registered options providers
        self.options_providers: list[OptionsProviderMixin] = []
        # dictionary associating option name to checker
        self._all_options: collections.OrderedDict[Any, Any] = collections.OrderedDict()
        self._short_options: dict[Any, Any] = {}
        self._nocallback_options: dict[Any, Any] = {}
        self._mygroups: dict[Any, Any] = {}
        # verbosity
        self._maxlevel = 0

    def reset_parsers(self, usage: str = "") -> None:
        # configuration file parser
        self.cfgfile_parser = configparser.ConfigParser(
            inline_comment_prefixes=("#", ";")
        )
        # command line parser
        self.cmdline_parser = OptionParser(Option, usage=usage)
        self.cmdline_parser.options_manager = self
        self._optik_option_attrs = set(self.cmdline_parser.option_class.ATTRS)

    def register_options_provider(
        self, provider: OptionsProviderMixin, own_group: bool = True
    ) -> None:
        """Register an options provider."""
        self.options_providers.append(provider)
        non_group_spec_options = [
            option for option in provider.options if "group" not in option[1]
        ]
        groups = getattr(provider, "option_groups", ())
        if own_group and non_group_spec_options:
            self.add_option_group(
                provider.name.upper(),
                provider.__doc__,
                non_group_spec_options,
                provider,
            )
        else:
            for opt, optdict in non_group_spec_options:
                self.add_optik_option(provider, self.cmdline_parser, opt, optdict)
        for gname, gdoc in groups:
            gname = gname.upper()
            goptions = [
                option
                for option in provider.options
                if option[1].get("group", "").upper() == gname
            ]
            self.add_option_group(gname, gdoc, goptions, provider)

    def add_option_group(
        self, group_name: str, _: Any, options: Any, provider: OptionsProviderMixin
    ) -> None:
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
            self.add_optik_option(provider, group, opt, optdict)

    def add_optik_option(
        self,
        provider: OptionsProviderMixin,
        optikcontainer: Any,
        opt: str,
        optdict: OptionDict,
    ) -> None:
        args, optdict = self.optik_option(provider, opt, optdict)
        option = optikcontainer.add_option(*args, **optdict)
        self._all_options[opt] = provider
        self._maxlevel = max(self._maxlevel, option.level or 0)

    def optik_option(
        self, provider: OptionsProviderMixin, opt: str, optdict: OptionDict
    ) -> tuple[list[str], OptionDict]:
        """Get our personal option definition and return a suitable form for
        use with optik/optparse.
        """
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
            self._short_options[optdict["short"]] = opt
            args.append("-" + optdict["short"])  # type: ignore[operator]
            del optdict["short"]
        # cleanup option definition dict before giving it to optik
        for key in list(optdict.keys()):
            if key not in self._optik_option_attrs:
                optdict.pop(key)
        return args, optdict

    def cb_set_provider_option(
        self, option: Option, opt: str, value: Any, parser: Any
    ) -> None:
        """Optik callback for option setting."""
        if opt.startswith("--"):
            # remove -- on long option
            opt = opt[2:]
        else:
            # short option, get its long equivalent
            opt = self._short_options[opt[1:]]
        # trick since we can't set action='store_true' on options
        if value is None:
            value = 1
        self.global_set_option(opt, value)

    def global_set_option(self, opt: str, value: Any) -> None:
        """Set option on the correct option provider."""
        self._all_options[opt].set_option(opt, value)

    def generate_config(
        self, stream: TextIO | None = None, skipsections: tuple[str, ...] = ()
    ) -> None:
        """Write a configuration file according to the current configuration
        into the given stream or stdout.
        """
        options_by_section: dict[str, list[tuple[str, OptionDict, Any]]] = {}
        sections = []
        for provider in self.options_providers:
            for section, options in provider.options_by_section():
                if section is None:
                    section = provider.name
                if section in skipsections:
                    continue
                options = [
                    (n, d, v)
                    for (n, d, v) in options
                    if d.get("type") is not None and not d.get("deprecated")
                ]
                if not options:
                    continue
                if section not in sections:
                    sections.append(section)
                all_options = options_by_section.setdefault(section, [])
                all_options += options
        stream = stream or sys.stdout
        printed = False
        for section in sections:
            if printed:
                print("\n", file=stream)
            utils.format_section(
                stream, section.upper(), sorted(options_by_section[section])
            )
            printed = True

    def load_provider_defaults(self) -> None:
        """Initialize configuration using default values."""
        for provider in self.options_providers:
            provider.load_defaults()

    def read_config_file(
        self, config_file: Path | None = None, verbose: bool = False
    ) -> None:
        """Read the configuration file but do not load it (i.e. dispatching
        values to each option's provider).
        """
        if config_file:
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

        if not verbose:
            return
        if config_file and config_file.exists():
            msg = f"Using config file '{config_file}'"
        else:
            msg = "No config file found, using default configuration"
        print(msg, file=sys.stderr)

    def _parse_toml(self, config_file: Path, parser: configparser.ConfigParser) -> None:
        """Parse and handle errors of a toml configuration file."""
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
                # This class is a mixin: add_message comes from the `PyLinter` class
                self.add_message(  # type: ignore[attr-defined]
                    "bad-configuration-section", line=0, args=(section, values)
                )
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

    def load_config_file(self) -> None:
        """Dispatch values previously read from a configuration file to each
        option's provider.
        """
        parser = self.cfgfile_parser
        for section in parser.sections():
            for option, value in parser.items(section):
                try:
                    self.global_set_option(option, value)
                except (KeyError, optparse.OptionError):
                    continue

    def load_configuration(self, **kwargs: Any) -> None:
        """Override configuration according to given parameters."""
        return self.load_configuration_from_config(kwargs)

    def load_configuration_from_config(self, config: dict[str, Any]) -> None:
        for opt, opt_value in config.items():
            opt = opt.replace("_", "-")
            provider = self._all_options[opt]
            provider.set_option(opt, opt_value)

    def load_command_line_configuration(
        self, args: list[str] | None = None
    ) -> list[str]:
        """Override configuration according to command line parameters.

        return additional arguments
        """
        with _patch_optparse():
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

    def help(self, level: int = 0) -> str:
        """Return the usage string for available options."""
        self.cmdline_parser.formatter.output_level = level
        with _patch_optparse():
            return str(self.cmdline_parser.format_help())
