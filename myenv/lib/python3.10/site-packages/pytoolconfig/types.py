"""PyToolConfig internal definitions and functions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from enum import Enum, auto
from typing import Any, Callable, Dict, List, TypeVar, Union

DataclassT = TypeVar("DataclassT", bound="Dataclass")


class Dataclass:
    __initialised__: bool
    __post_init_original__: Callable[..., None] | None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def __call__(self: DataclassT, *args: Any, **kwargs: Any) -> DataclassT:
        pass


_BaseType = Union[str, int, float, datetime, date, time, bool]
_BaseTypeWithList = Union[_BaseType, List[_BaseType]]
Key = Union[Dict[str, _BaseTypeWithList], _BaseTypeWithList]


# We have a circular dependency preventing us from generating universal keys from
# universal_config. Universal Config requires field, which requires Universal Key.
class UniversalKey(Enum):
    """See universal config documentation."""

    formatter = auto()
    max_line_length = auto()
    min_py_version = auto()
    max_py_version = auto()
    dependencies = auto()
    optional_dependencies = auto()
    version = auto()


@dataclass
class ConfigField:
    """Dataclass store and validate fields in a configuration model."""

    description: str | None = None
    universal_config: UniversalKey | None = None
    command_line: tuple[str] | None = None
    _type: Any = None
    _default: Any = None
