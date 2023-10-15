# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Utility functions for configuration testing."""

from __future__ import annotations

import copy
import json
import logging
import re
import unittest
from pathlib import Path
from typing import Any, Dict
from unittest.mock import Mock

from pylint.constants import PY38_PLUS
from pylint.lint import Run

# We use Any in this typing because the configuration contains real objects and constants
# that could be a lot of things.
ConfigurationValue = Any
PylintConfiguration = Dict[str, ConfigurationValue]


if not PY38_PLUS:
    # We need to deepcopy a compiled regex pattern
    # In python 3.6 and 3.7 this requires a hack
    # See https://stackoverflow.com/a/56935186
    copy._deepcopy_dispatch[type(re.compile(""))] = lambda r, _: r  # type: ignore[attr-defined]


def get_expected_or_default(
    tested_configuration_file: str | Path,
    suffix: str,
    default: str,
) -> str:
    """Return the expected value from the file if it exists, or the given default."""
    expected = default
    path = Path(tested_configuration_file)
    expected_result_path = path.parent / f"{path.stem}.{suffix}"
    if expected_result_path.exists():
        with open(expected_result_path, encoding="utf8") as f:
            expected = f.read()
        # logging is helpful to realize your file is not taken into
        # account after a misspelling of the file name. The output of the
        # program is checked during the test so printing messes with the result.
        logging.info("%s exists.", expected_result_path)
    else:
        logging.info("%s not found, using '%s'.", expected_result_path, default)
    return expected


EXPECTED_CONF_APPEND_KEY = "functional_append"
EXPECTED_CONF_REMOVE_KEY = "functional_remove"


def get_expected_configuration(
    configuration_path: str, default_configuration: PylintConfiguration
) -> PylintConfiguration:
    """Get the expected parsed configuration of a configuration functional test."""
    result = copy.deepcopy(default_configuration)
    config_as_json = get_expected_or_default(
        configuration_path, suffix="result.json", default="{}"
    )
    to_override = json.loads(config_as_json)
    for key, value in to_override.items():
        if key == EXPECTED_CONF_APPEND_KEY:
            for fkey, fvalue in value.items():
                result[fkey] += fvalue
        elif key == EXPECTED_CONF_REMOVE_KEY:
            for fkey, fvalue in value.items():
                new_value = []
                for old_value in result[fkey]:
                    if old_value not in fvalue:
                        new_value.append(old_value)
                result[fkey] = new_value
        else:
            result[key] = value
    return result


def get_related_files(
    tested_configuration_file: str | Path, suffix_filter: str
) -> list[Path]:
    """Return all the file related to a test conf file ending with a suffix."""
    conf_path = Path(tested_configuration_file)
    return [
        p
        for p in conf_path.parent.iterdir()
        if str(p.stem).startswith(conf_path.stem) and str(p).endswith(suffix_filter)
    ]


def get_expected_output(
    configuration_path: str | Path, user_specific_path: Path
) -> tuple[int, str]:
    """Get the expected output of a functional test."""
    exit_code = 0
    msg = (
        "we expect a single file of the form 'filename.32.out' where 'filename' represents "
        "the name of the configuration file, and '32' the expected error code."
    )
    possible_out_files = get_related_files(configuration_path, suffix_filter="out")
    if len(possible_out_files) > 1:
        logging.error(
            "Too much .out files for %s %s.",
            configuration_path,
            msg,
        )
        return -1, "out file is broken"
    if not possible_out_files:
        # logging is helpful to see what the expected exit code is and why.
        # The output of the program is checked during the test so printing
        # messes with the result.
        logging.info(".out file does not exists, so the expected exit code is 0")
        return 0, ""
    path = possible_out_files[0]
    try:
        exit_code = int(str(path.stem).rsplit(".", maxsplit=1)[-1])
    except Exception as e:  # pylint: disable=broad-except
        logging.error(
            "Wrong format for .out file name for %s %s: %s",
            configuration_path,
            msg,
            e,
        )
        return -1, "out file is broken"

    output = get_expected_or_default(
        configuration_path, suffix=f"{exit_code}.out", default=""
    )
    logging.info(
        "Output exists for %s so the expected exit code is %s",
        configuration_path,
        exit_code,
    )
    return exit_code, output.format(
        abspath=configuration_path,
        relpath=Path(configuration_path).relative_to(user_specific_path),
    )


def run_using_a_configuration_file(
    configuration_path: Path | str, file_to_lint: str = __file__
) -> tuple[Mock, Mock, Run]:
    """Simulate a run with a configuration without really launching the checks."""
    configuration_path = str(configuration_path)
    args = ["--rcfile", configuration_path, file_to_lint]
    # We do not capture the `SystemExit` as then the `runner` variable
    # would not be accessible outside the `with` block.
    with unittest.mock.patch("sys.exit") as mocked_exit:
        # Do not actually run checks, that could be slow. We don't mock
        # `PyLinter.check`: it calls `PyLinter.initialize` which is
        # needed to properly set up messages inclusion/exclusion
        # in `_msg_states`, used by `is_message_enabled`.
        check = "pylint.lint.pylinter.check_parallel"
        with unittest.mock.patch(check) as mocked_check_parallel:
            runner = Run(args)
    return mocked_exit, mocked_check_parallel, runner
