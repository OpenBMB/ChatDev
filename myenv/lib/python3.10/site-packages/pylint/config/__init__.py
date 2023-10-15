# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

__all__ = [
    "ConfigurationMixIn",  # Deprecated
    "find_default_config_files",
    "find_pylintrc",  # Deprecated
    "Option",  # Deprecated
    "OptionsManagerMixIn",  # Deprecated
    "OptionParser",  # Deprecated
    "OptionsProviderMixIn",  # Deprecated
    "UnsupportedAction",  # Deprecated
    "PYLINTRC",
    "USER_HOME",  # Compatibility with the old API
    "PYLINT_HOME",  # Compatibility with the old API
    "save_results",  # Compatibility with the old API # Deprecated
    "load_results",  # Compatibility with the old API # Deprecated
]

import warnings

from pylint.config.arguments_provider import UnsupportedAction
from pylint.config.configuration_mixin import ConfigurationMixIn
from pylint.config.environment_variable import PYLINTRC
from pylint.config.find_default_config_files import (
    find_default_config_files,
    find_pylintrc,
)
from pylint.config.option import Option
from pylint.config.option_manager_mixin import OptionsManagerMixIn
from pylint.config.option_parser import OptionParser  # type: ignore[attr-defined]
from pylint.config.options_provider_mixin import (  # type: ignore[attr-defined]
    OptionsProviderMixIn,
)
from pylint.constants import PYLINT_HOME, USER_HOME
from pylint.utils import LinterStats


def load_results(base: str) -> LinterStats | None:
    # TODO: 3.0: Remove deprecated function
    # pylint: disable=import-outside-toplevel
    from pylint.lint.caching import load_results as _real_load_results

    warnings.warn(
        "'pylint.config.load_results' is deprecated, please use "
        "'pylint.lint.load_results' instead. This will be removed in 3.0.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _real_load_results(base, PYLINT_HOME)


def save_results(results: LinterStats, base: str) -> None:
    # TODO: 3.0: Remove deprecated function
    # pylint: disable=import-outside-toplevel
    from pylint.lint.caching import save_results as _real_save_results

    warnings.warn(
        "'pylint.config.save_results' is deprecated, please use "
        "'pylint.lint.save_results' instead. This will be removed in 3.0.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _real_save_results(results, base, PYLINT_HOME)
