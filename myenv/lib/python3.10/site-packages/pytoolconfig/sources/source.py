"""Base class for defining custom sources."""
from __future__ import annotations

from abc import ABC, abstractmethod

from pytoolconfig.types import Key


class Source(ABC):
    """Base class for defining custom sources."""

    name: str  # The name of the tool for documentation
    description: str | None  # The description, written as markdown.

    @abstractmethod
    def _read(self) -> bool:
        """Read the file.

        If file does not exist or the tool does not exist in the file,
        return False. Can be called multiple times and overwrite the
        existing cached configuration.
        """

    @abstractmethod
    def parse(self) -> dict[str, Key] | None:
        """Parse the file for each property as a nested dict.

        Return None if tool is not configured in file. Otherwise,
        returns configuration pertaining to the tool.
        """
