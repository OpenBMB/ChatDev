# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import abc
import warnings
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pylint.lint import PyLinter


class MapReduceMixin(metaclass=abc.ABCMeta):
    """A mixin design to allow multi-process/threaded runs of a Checker."""

    def __init__(self) -> None:
        warnings.warn(
            "MapReduceMixin has been deprecated and will be removed in pylint 3.0. "
            "To make a checker reduce map data simply implement get_map_data and reduce_map_data.",
            DeprecationWarning,
            stacklevel=2,
        )

    @abc.abstractmethod
    def get_map_data(self) -> Any:
        """Returns merge-able/reducible data that will be examined."""

    @abc.abstractmethod
    def reduce_map_data(self, linter: PyLinter, data: list[Any]) -> None:
        """For a given Checker, receives data for all mapped runs."""
