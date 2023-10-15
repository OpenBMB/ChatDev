# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Utils for the 'pylint-config' command."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal

if sys.version_info >= (3, 10):
    from typing import ParamSpec
else:
    from typing_extensions import ParamSpec

_P = ParamSpec("_P")
_ReturnValueT = TypeVar("_ReturnValueT", bool, str)

SUPPORTED_FORMATS = {"t", "toml", "i", "ini"}
YES_NO_ANSWERS = {"y", "yes", "n", "no"}


class InvalidUserInput(Exception):
    """Raised whenever a user input is invalid."""

    def __init__(self, valid_input: str, input_value: str, *args: object) -> None:
        self.valid = valid_input
        self.input = input_value
        super().__init__(*args)


def should_retry_after_invalid_input(
    func: Callable[_P, _ReturnValueT]
) -> Callable[_P, _ReturnValueT]:
    """Decorator that handles InvalidUserInput exceptions and retries."""

    def inner_function(*args: _P.args, **kwargs: _P.kwargs) -> _ReturnValueT:
        called_once = False
        while True:
            try:
                return func(*args, **kwargs)
            except InvalidUserInput as exc:
                if called_once and exc.input == "exit()":
                    print("Stopping 'pylint-config'.")
                    sys.exit()
                print(f"Answer should be one of {exc.valid}.")
                print("Type 'exit()' if you want to exit the program.")
                called_once = True

    return inner_function


@should_retry_after_invalid_input
def get_and_validate_format() -> Literal["toml", "ini"]:
    """Make sure that the output format is either .toml or .ini."""
    # pylint: disable-next=bad-builtin
    format_type = input(
        "Please choose the format of configuration, (T)oml or (I)ni (.cfg): "
    ).lower()

    if format_type not in SUPPORTED_FORMATS:
        raise InvalidUserInput(", ".join(sorted(SUPPORTED_FORMATS)), format_type)

    if format_type.startswith("t"):
        return "toml"
    return "ini"


@should_retry_after_invalid_input
def validate_yes_no(question: str, default: Literal["yes", "no"] | None) -> bool:
    """Validate that a yes or no answer is correct."""
    question = f"{question} (y)es or (n)o "
    if default:
        question += f" (default={default}) "
    # pylint: disable-next=bad-builtin
    answer = input(question).lower()

    if not answer and default:
        answer = default

    if answer not in YES_NO_ANSWERS:
        raise InvalidUserInput(", ".join(sorted(YES_NO_ANSWERS)), answer)

    return answer.startswith("y")


def get_minimal_setting() -> bool:
    """Ask the user if they want to use the minimal setting."""
    return validate_yes_no(
        "Do you want a minimal configuration without comments or default values?", "no"
    )


def get_and_validate_output_file() -> tuple[bool, Path]:
    """Make sure that the output file is correct."""
    to_file = validate_yes_no("Do you want to write the output to a file?", "no")

    if not to_file:
        return False, Path()

    # pylint: disable-next=bad-builtin
    file_name = Path(input("What should the file be called: "))
    if file_name.exists():
        overwrite = validate_yes_no(
            f"{file_name} already exists. Are you sure you want to overwrite?", "no"
        )

        if not overwrite:
            return False, file_name
        return True, file_name

    return True, file_name
