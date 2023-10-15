# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Utils for arguments/options parsing and handling."""

from __future__ import annotations

import re
import warnings
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pylint import extensions, utils
from pylint.config.argument import (
    _CallableArgument,
    _ExtendArgument,
    _StoreArgument,
    _StoreNewNamesArgument,
    _StoreOldNamesArgument,
    _StoreTrueArgument,
)
from pylint.config.callback_actions import _CallbackAction
from pylint.config.exceptions import ArgumentPreprocessingError

if TYPE_CHECKING:
    from pylint.lint.run import Run


def _convert_option_to_argument(
    opt: str, optdict: dict[str, Any]
) -> (
    _StoreArgument
    | _StoreTrueArgument
    | _CallableArgument
    | _StoreOldNamesArgument
    | _StoreNewNamesArgument
    | _ExtendArgument
):
    """Convert an optdict to an Argument class instance."""
    if "level" in optdict and "hide" not in optdict:
        warnings.warn(
            "The 'level' key in optdicts has been deprecated. "
            "Use 'hide' with a boolean to hide an option from the help message. "
            f"optdict={optdict}",
            DeprecationWarning,
        )

    # Get the long and short flags
    flags = [f"--{opt}"]
    if "short" in optdict:
        flags += [f"-{optdict['short']}"]

    # Get the action type
    action = optdict.get("action", "store")

    if action == "store_true":
        return _StoreTrueArgument(
            flags=flags,
            action=action,
            default=optdict.get("default", True),
            arg_help=optdict.get("help", ""),
            hide_help=optdict.get("hide", False),
            section=optdict.get("group", None),
        )
    if not isinstance(action, str) and issubclass(action, _CallbackAction):
        return _CallableArgument(
            flags=flags,
            action=action,
            arg_help=optdict.get("help", ""),
            kwargs=optdict.get("kwargs", {}),
            hide_help=optdict.get("hide", False),
            section=optdict.get("group", None),
            metavar=optdict.get("metavar", None),
        )
    try:
        default = optdict["default"]
    except KeyError:
        warnings.warn(
            "An option dictionary should have a 'default' key to specify "
            "the option's default value. This key will be required in pylint "
            "3.0. It is not required for 'store_true' and callable actions. "
            f"optdict={optdict}",
            DeprecationWarning,
        )
        default = None
    if action == "extend":
        return _ExtendArgument(
            flags=flags,
            action=action,
            default=[] if default is None else default,
            arg_type=optdict["type"],
            choices=optdict.get("choices", None),
            arg_help=optdict.get("help", ""),
            metavar=optdict.get("metavar", ""),
            hide_help=optdict.get("hide", False),
            section=optdict.get("group", None),
            dest=optdict.get("dest", None),
        )
    if "kwargs" in optdict:
        if "old_names" in optdict["kwargs"]:
            return _StoreOldNamesArgument(
                flags=flags,
                default=default,
                arg_type=optdict["type"],
                choices=optdict.get("choices", None),
                arg_help=optdict.get("help", ""),
                metavar=optdict.get("metavar", ""),
                hide_help=optdict.get("hide", False),
                kwargs=optdict.get("kwargs", {}),
                section=optdict.get("group", None),
            )
        if "new_names" in optdict["kwargs"]:
            return _StoreNewNamesArgument(
                flags=flags,
                default=default,
                arg_type=optdict["type"],
                choices=optdict.get("choices", None),
                arg_help=optdict.get("help", ""),
                metavar=optdict.get("metavar", ""),
                hide_help=optdict.get("hide", False),
                kwargs=optdict.get("kwargs", {}),
                section=optdict.get("group", None),
            )
    if "dest" in optdict:
        return _StoreOldNamesArgument(
            flags=flags,
            default=default,
            arg_type=optdict["type"],
            choices=optdict.get("choices", None),
            arg_help=optdict.get("help", ""),
            metavar=optdict.get("metavar", ""),
            hide_help=optdict.get("hide", False),
            kwargs={"old_names": [optdict["dest"]]},
            section=optdict.get("group", None),
        )
    return _StoreArgument(
        flags=flags,
        action=action,
        default=default,
        arg_type=optdict["type"],
        choices=optdict.get("choices", None),
        arg_help=optdict.get("help", ""),
        metavar=optdict.get("metavar", ""),
        hide_help=optdict.get("hide", False),
        section=optdict.get("group", None),
    )


def _parse_rich_type_value(value: Any) -> str:
    """Parse rich (toml) types into strings."""
    if isinstance(value, (list, tuple)):
        return ",".join(_parse_rich_type_value(i) for i in value)
    if isinstance(value, re.Pattern):
        return str(value.pattern)
    if isinstance(value, dict):
        return ",".join(f"{k}:{v}" for k, v in value.items())
    return str(value)


# pylint: disable-next=unused-argument
def _init_hook(run: Run, value: str | None) -> None:
    """Execute arbitrary code from the init_hook.

    This can be used to set the 'sys.path' for example.
    """
    assert value is not None
    exec(value)  # pylint: disable=exec-used


def _set_rcfile(run: Run, value: str | None) -> None:
    """Set the rcfile."""
    assert value is not None
    run._rcfile = value


def _set_output(run: Run, value: str | None) -> None:
    """Set the output."""
    assert value is not None
    run._output = value


def _add_plugins(run: Run, value: str | None) -> None:
    """Add plugins to the list of loadable plugins."""
    assert value is not None
    run._plugins.extend(utils._splitstrip(value))


def _set_verbose_mode(run: Run, value: str | None) -> None:
    assert value is None
    run.verbose = True


def _enable_all_extensions(run: Run, value: str | None) -> None:
    """Enable all extensions."""
    assert value is None
    for filename in Path(extensions.__file__).parent.iterdir():
        if filename.suffix == ".py" and not filename.stem.startswith("_"):
            extension_name = f"pylint.extensions.{filename.stem}"
            if extension_name not in run._plugins:
                run._plugins.append(extension_name)


PREPROCESSABLE_OPTIONS: dict[
    str, tuple[bool, Callable[[Run, str | None], None], int]
] = {  # pylint: disable=consider-using-namedtuple-or-dataclass
    # pylint: disable=useless-suppression, wrong-spelling-in-comment
    # Argparse by default allows abbreviations. It behaves differently
    # if you turn this off, so we also turn it on. We mimic this
    # by allowing some abbreviations or incorrect spelling here.
    # The integer at the end of the tuple indicates how many letters
    # should match, include the '-'. 0 indicates a full match.
    #
    # Clashes with --init-(import)
    "--init-hook": (True, _init_hook, 8),
    # Clashes with --r(ecursive)
    "--rcfile": (True, _set_rcfile, 4),
    # Clashes with --output(-format)
    "--output": (True, _set_output, 0),
    # Clashes with --lo(ng-help)
    "--load-plugins": (True, _add_plugins, 5),
    # Clashes with --v(ariable-rgx)
    "--verbose": (False, _set_verbose_mode, 4),
    "-v": (False, _set_verbose_mode, 2),
    # Clashes with --enable
    "--enable-all-extensions": (False, _enable_all_extensions, 9),
}
# pylint: enable=wrong-spelling-in-comment


def _preprocess_options(run: Run, args: Sequence[str]) -> list[str]:
    """Pre-process options before full config parsing has started."""
    processed_args: list[str] = []

    i = 0
    while i < len(args):
        argument = args[i]
        if not argument.startswith("-"):
            processed_args.append(argument)
            i += 1
            continue

        try:
            option, value = argument.split("=", 1)
        except ValueError:
            option, value = argument, None

        matched_option = None
        for option_name, data in PREPROCESSABLE_OPTIONS.items():
            to_match = data[2]
            if to_match == 0:
                if option == option_name:
                    matched_option = option_name
            elif option.startswith(option_name[:to_match]):
                matched_option = option_name

        if matched_option is None:
            processed_args.append(argument)
            i += 1
            continue

        takearg, cb, _ = PREPROCESSABLE_OPTIONS[matched_option]

        if takearg and value is None:
            i += 1
            if i >= len(args) or args[i].startswith("-"):
                raise ArgumentPreprocessingError(f"Option {option} expects a value")
            value = args[i]
        elif not takearg and value is not None:
            raise ArgumentPreprocessingError(f"Option {option} doesn't expect a value")

        cb(run, value)
        i += 1

    return processed_args
