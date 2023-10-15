"""Universal Configuration base model."""
from __future__ import annotations

from packaging.requirements import Requirement

from .fields import field
from .types import dataclass


@dataclass
class UniversalConfig:
    """Universal Configuration base model."""

    formatter: str | None = field(None, "Formatter used to format this File")
    max_line_length: int | None = field(None, description="Maximum line length")

    min_py_version: tuple[int, int] | None = field(
        None,
        """Minimum target python version. Requires PEP 621.
        Taken from project.requires-python""",
    )
    max_py_version: tuple[int, int] | None = field(
        None,
        """Maximum target python version. Requires PEP 621.
        Taken from project.requires-python""",
    )
    dependencies: list[Requirement] | None = field(
        None,
        """Dependencies of project. Requires PEP 621.
        Taken from project.dependencies. """,
    )
    optional_dependencies: dict[str, list[Requirement]] | None = field(
        None,
        """Optional dependencies of project. Requires PEP 621.
    Taken from project.optional_dependencies.""",
    )
    version: str | None = field(
        None, "Version of the project. Requires PEP 621. Taken from project.version."
    )
