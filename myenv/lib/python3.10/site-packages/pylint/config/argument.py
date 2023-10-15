# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Definition of an Argument class and transformers for various argument types.

An Argument instance represents a pylint option to be handled by an argparse.ArgumentParser
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import sys
from collections.abc import Callable
from glob import glob
from typing import Any, Pattern, Sequence, Tuple, Union

from pylint import interfaces
from pylint import utils as pylint_utils
from pylint.config.callback_actions import _CallbackAction, _ExtendAction
from pylint.config.deprecation_actions import _NewNamesAction, _OldNamesAction
from pylint.constants import PY38_PLUS

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal


_ArgumentTypes = Union[
    str,
    int,
    float,
    bool,
    Pattern[str],
    Sequence[str],
    Sequence[Pattern[str]],
    Tuple[int, ...],
]
"""List of possible argument types."""


def _confidence_transformer(value: str) -> Sequence[str]:
    """Transforms a comma separated string of confidence values."""
    if not value:
        return interfaces.CONFIDENCE_LEVEL_NAMES
    values = pylint_utils._check_csv(value)
    for confidence in values:
        if confidence not in interfaces.CONFIDENCE_LEVEL_NAMES:
            raise argparse.ArgumentTypeError(
                f"{value} should be in {*interfaces.CONFIDENCE_LEVEL_NAMES,}"
            )
    return values


def _csv_transformer(value: str) -> Sequence[str]:
    """Transforms a comma separated string."""
    return pylint_utils._check_csv(value)


YES_VALUES = {"y", "yes", "true"}
NO_VALUES = {"n", "no", "false"}


def _yn_transformer(value: str) -> bool:
    """Transforms a yes/no or stringified bool into a bool."""
    value = value.lower()
    if value in YES_VALUES:
        return True
    if value in NO_VALUES:
        return False
    raise argparse.ArgumentTypeError(
        None, f"Invalid yn value '{value}', should be in {*YES_VALUES, *NO_VALUES}"
    )


def _non_empty_string_transformer(value: str) -> str:
    """Check that a string is not empty and remove quotes."""
    if not value:
        raise argparse.ArgumentTypeError("Option cannot be an empty string.")
    return pylint_utils._unquote(value)


def _path_transformer(value: str) -> str:
    """Expand user and variables in a path."""
    return os.path.expandvars(os.path.expanduser(value))


def _glob_paths_csv_transformer(value: str) -> Sequence[str]:
    """Transforms a comma separated list of paths while expanding user and
    variables and glob patterns.
    """
    paths: list[str] = []
    for path in _csv_transformer(value):
        paths.extend(glob(_path_transformer(path), recursive=True))
    return paths


def _py_version_transformer(value: str) -> tuple[int, ...]:
    """Transforms a version string into a version tuple."""
    try:
        version = tuple(int(val) for val in value.replace(",", ".").split("."))
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"{value} has an invalid format, should be a version string. E.g., '3.8'"
        ) from None
    return version


def _regex_transformer(value: str) -> Pattern[str]:
    """Return `re.compile(value)`."""
    try:
        return re.compile(value)
    except re.error as e:
        msg = f"Error in provided regular expression: {value} beginning at index {e.pos}: {e.msg}"
        raise argparse.ArgumentTypeError(msg) from e


def _regexp_csv_transfomer(value: str) -> Sequence[Pattern[str]]:
    """Transforms a comma separated list of regular expressions."""
    patterns: list[Pattern[str]] = []
    for pattern in _csv_transformer(value):
        patterns.append(_regex_transformer(pattern))
    return patterns


def _regexp_paths_csv_transfomer(value: str) -> Sequence[Pattern[str]]:
    """Transforms a comma separated list of regular expressions paths."""
    patterns: list[Pattern[str]] = []
    for pattern in _csv_transformer(value):
        patterns.append(
            re.compile(
                str(pathlib.PureWindowsPath(pattern)).replace("\\", "\\\\")
                + "|"
                + pathlib.PureWindowsPath(pattern).as_posix()
            )
        )
    return patterns


_TYPE_TRANSFORMERS: dict[str, Callable[[str], _ArgumentTypes]] = {
    "choice": str,
    "csv": _csv_transformer,
    "float": float,
    "int": int,
    "confidence": _confidence_transformer,
    "non_empty_string": _non_empty_string_transformer,
    "path": _path_transformer,
    "glob_paths_csv": _glob_paths_csv_transformer,
    "py_version": _py_version_transformer,
    "regexp": _regex_transformer,
    "regexp_csv": _regexp_csv_transfomer,
    "regexp_paths_csv": _regexp_paths_csv_transfomer,
    "string": pylint_utils._unquote,
    "yn": _yn_transformer,
}
"""Type transformers for all argument types.

A transformer should accept a string and return one of the supported
Argument types. It will only be called when parsing 1) command-line,
2) configuration files and 3) a string default value.
Non-string default values are assumed to be of the correct type.
"""


class _Argument:
    """Class representing an argument to be parsed by an argparse.ArgumentsParser.

    This is based on the parameters passed to argparse.ArgumentsParser.add_message.
    See:
    https://docs.python.org/3/library/argparse.html#argparse.ArgumentParser.add_argument
    """

    def __init__(
        self,
        *,
        flags: list[str],
        arg_help: str,
        hide_help: bool,
        section: str | None,
    ) -> None:
        self.flags = flags
        """The name of the argument."""

        self.hide_help = hide_help
        """Whether to hide this argument in the help message."""

        # argparse uses % formatting on help strings, so a % needs to be escaped
        self.help = arg_help.replace("%", "%%")
        """The description of the argument."""

        if hide_help:
            self.help = argparse.SUPPRESS

        self.section = section
        """The section to add this argument to."""


class _BaseStoreArgument(_Argument):
    """Base class for store arguments to be parsed by an argparse.ArgumentsParser.

    This is based on the parameters passed to argparse.ArgumentsParser.add_message.
    See:
    https://docs.python.org/3/library/argparse.html#argparse.ArgumentParser.add_argument
    """

    def __init__(
        self,
        *,
        flags: list[str],
        action: str,
        default: _ArgumentTypes,
        arg_help: str,
        hide_help: bool,
        section: str | None,
    ) -> None:
        super().__init__(
            flags=flags, arg_help=arg_help, hide_help=hide_help, section=section
        )

        self.action = action
        """The action to perform with the argument."""

        self.default = default
        """The default value of the argument."""


class _StoreArgument(_BaseStoreArgument):
    """Class representing a store argument to be parsed by an argparse.ArgumentsParser.

    This is based on the parameters passed to argparse.ArgumentsParser.add_message.
    See:
    https://docs.python.org/3/library/argparse.html#argparse.ArgumentParser.add_argument
    """

    def __init__(
        self,
        *,
        flags: list[str],
        action: str,
        default: _ArgumentTypes,
        arg_type: str,
        choices: list[str] | None,
        arg_help: str,
        metavar: str,
        hide_help: bool,
        section: str | None,
    ) -> None:
        super().__init__(
            flags=flags,
            action=action,
            default=default,
            arg_help=arg_help,
            hide_help=hide_help,
            section=section,
        )

        self.type = _TYPE_TRANSFORMERS[arg_type]
        """A transformer function that returns a transformed type of the argument."""

        self.choices = choices
        """A list of possible choices for the argument.

        None if there are no restrictions.
        """

        self.metavar = metavar
        """The metavar of the argument.

        See:
        https://docs.python.org/3/library/argparse.html#metavar
        """


class _StoreTrueArgument(_BaseStoreArgument):
    """Class representing a 'store_true' argument to be parsed by an
    argparse.ArgumentsParser.

    This is based on the parameters passed to argparse.ArgumentsParser.add_message.
    See:
    https://docs.python.org/3/library/argparse.html#argparse.ArgumentParser.add_argument
    """

    # pylint: disable-next=useless-parent-delegation # We narrow down the type of action
    def __init__(
        self,
        *,
        flags: list[str],
        action: Literal["store_true"],
        default: _ArgumentTypes,
        arg_help: str,
        hide_help: bool,
        section: str | None,
    ) -> None:
        super().__init__(
            flags=flags,
            action=action,
            default=default,
            arg_help=arg_help,
            hide_help=hide_help,
            section=section,
        )


class _DeprecationArgument(_Argument):
    """Store arguments while also handling deprecation warnings for old and new names.

    This is based on the parameters passed to argparse.ArgumentsParser.add_message.
    See:
    https://docs.python.org/3/library/argparse.html#argparse.ArgumentParser.add_argument
    """

    def __init__(
        self,
        *,
        flags: list[str],
        action: type[argparse.Action],
        default: _ArgumentTypes,
        arg_type: str,
        choices: list[str] | None,
        arg_help: str,
        metavar: str,
        hide_help: bool,
        section: str | None,
    ) -> None:
        super().__init__(
            flags=flags, arg_help=arg_help, hide_help=hide_help, section=section
        )

        self.action = action
        """The action to perform with the argument."""

        self.default = default
        """The default value of the argument."""

        self.type = _TYPE_TRANSFORMERS[arg_type]
        """A transformer function that returns a transformed type of the argument."""

        self.choices = choices
        """A list of possible choices for the argument.

        None if there are no restrictions.
        """

        self.metavar = metavar
        """The metavar of the argument.

        See:
        https://docs.python.org/3/library/argparse.html#metavar
        """


class _ExtendArgument(_DeprecationArgument):
    """Class for extend arguments to be parsed by an argparse.ArgumentsParser.

    This is based on the parameters passed to argparse.ArgumentsParser.add_message.
    See:
    https://docs.python.org/3/library/argparse.html#argparse.ArgumentParser.add_argument
    """

    def __init__(
        self,
        *,
        flags: list[str],
        action: Literal["extend"],
        default: _ArgumentTypes,
        arg_type: str,
        metavar: str,
        arg_help: str,
        hide_help: bool,
        section: str | None,
        choices: list[str] | None,
        dest: str | None,
    ) -> None:
        # The extend action is included in the stdlib from 3.8+
        if PY38_PLUS:
            action_class = argparse._ExtendAction
        else:
            action_class = _ExtendAction  # type: ignore[assignment]

        self.dest = dest
        """The destination of the argument."""

        super().__init__(
            flags=flags,
            action=action_class,
            default=default,
            arg_type=arg_type,
            choices=choices,
            arg_help=arg_help,
            metavar=metavar,
            hide_help=hide_help,
            section=section,
        )


class _StoreOldNamesArgument(_DeprecationArgument):
    """Store arguments while also handling old names.

    This is based on the parameters passed to argparse.ArgumentsParser.add_message.
    See:
    https://docs.python.org/3/library/argparse.html#argparse.ArgumentParser.add_argument
    """

    def __init__(
        self,
        *,
        flags: list[str],
        default: _ArgumentTypes,
        arg_type: str,
        choices: list[str] | None,
        arg_help: str,
        metavar: str,
        hide_help: bool,
        kwargs: dict[str, Any],
        section: str | None,
    ) -> None:
        super().__init__(
            flags=flags,
            action=_OldNamesAction,
            default=default,
            arg_type=arg_type,
            choices=choices,
            arg_help=arg_help,
            metavar=metavar,
            hide_help=hide_help,
            section=section,
        )

        self.kwargs = kwargs
        """Any additional arguments passed to the action."""


class _StoreNewNamesArgument(_DeprecationArgument):
    """Store arguments while also emitting deprecation warnings.

    This is based on the parameters passed to argparse.ArgumentsParser.add_message.
    See:
    https://docs.python.org/3/library/argparse.html#argparse.ArgumentParser.add_argument
    """

    def __init__(
        self,
        *,
        flags: list[str],
        default: _ArgumentTypes,
        arg_type: str,
        choices: list[str] | None,
        arg_help: str,
        metavar: str,
        hide_help: bool,
        kwargs: dict[str, Any],
        section: str | None,
    ) -> None:
        super().__init__(
            flags=flags,
            action=_NewNamesAction,
            default=default,
            arg_type=arg_type,
            choices=choices,
            arg_help=arg_help,
            metavar=metavar,
            hide_help=hide_help,
            section=section,
        )

        self.kwargs = kwargs
        """Any additional arguments passed to the action."""


class _CallableArgument(_Argument):
    """Class representing an callable argument to be parsed by an
    argparse.ArgumentsParser.

    This is based on the parameters passed to argparse.ArgumentsParser.add_message.
    See:
    https://docs.python.org/3/library/argparse.html#argparse.ArgumentParser.add_argument
    """

    def __init__(
        self,
        *,
        flags: list[str],
        action: type[_CallbackAction],
        arg_help: str,
        kwargs: dict[str, Any],
        hide_help: bool,
        section: str | None,
        metavar: str,
    ) -> None:
        super().__init__(
            flags=flags, arg_help=arg_help, hide_help=hide_help, section=section
        )

        self.action = action
        """The action to perform with the argument."""

        self.kwargs = kwargs
        """Any additional arguments passed to the action."""

        self.metavar = metavar
        """The metavar of the argument.

        See:
        https://docs.python.org/3/library/argparse.html#metavar
        """
