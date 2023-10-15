"""Utility functions and classes."""
from __future__ import annotations

import sys
from dataclasses import Field, fields, is_dataclass, replace
from pathlib import Path
from typing import Any, Callable, Generator, Mapping, TypeVar

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet

from .types import Dataclass, Key


def find_config_file(
    working_directory: Path, filename: str, bases: list[str] | None = None
) -> Path | None:
    if bases is None:
        bases = [".git", ".hg"]
    """Recursively find the configuration file."""
    target = working_directory / filename
    if target.exists():
        return target
    for base in bases:
        if (working_directory / base).exists():
            return None
    if working_directory == working_directory.parent:
        return None
    return find_config_file(working_directory.parent, filename, bases)


def min_py_version(specifier: str) -> tuple[int, int]:
    """Return the minimum python 3 version.

    Between 3.4 and interpreter version.
    """
    parsed = SpecifierSet(specifier)
    for i in range(4, sys.version_info.minor):
        if parsed.contains(f"3.{i}"):
            return (3, i)
    return (3, sys.version_info.minor)


def max_py_version(specifier: str) -> tuple[int, int]:
    """Return the maximum python 3 version.

    Between 3.4 and interpreter version.
    """
    parsed = SpecifierSet(specifier)
    for i in range(sys.version_info.minor, 4, -1):
        if parsed.contains(f"3.{i}"):
            return (3, i)
    return (3, 4)  # Please don't cap your project at python3.4


def parse_dependencies(dependencies: list[str]) -> Generator[Requirement, None, None]:
    """Parse the dependencies from TOML using packaging."""
    for dependency in dependencies:
        yield Requirement(dependency)


T = TypeVar("T", bound="Dataclass")


def _subtables(dataclass_fields: dict[str, Field[Any]]) -> dict[str, type[Any]]:
    return {
        name: field.type
        for name, field in dataclass_fields.items()
        if is_dataclass(field.type)
    }


def _fields(dataclass) -> dict[str, Field[Any]]:
    return {field.name: field for field in fields(dataclass) if field.init}


def _dict_to_dataclass(dataclass: Callable[..., T], dictionary: Mapping[str, Key]) -> T:
    filtered_arg_dict: dict[str, Any] = {}
    dataclass_fields = _fields(dataclass)
    sub_tables = _subtables(dataclass_fields)
    for key_name, value in dictionary.items():
        if key_name in sub_tables:
            sub_table = sub_tables[key_name]
            assert isinstance(value, Mapping)
            filtered_arg_dict[key_name] = _dict_to_dataclass(sub_table, value)
        elif key_name in dataclass_fields:
            filtered_arg_dict[key_name] = value
    return dataclass(**filtered_arg_dict)


def _recursive_merge(dataclass: T, dictionary: Mapping[str, Key]) -> T:
    """Overwrite every value specified in dictionary on the dataclass."""
    filtered_arg_dict: dict[str, Any] = {}
    dataclass_fields = _fields(dataclass)
    sub_tables = _subtables(dataclass_fields)
    for key_name, value in dictionary.items():
        if key_name in sub_tables:
            sub_table = getattr(dataclass, key_name)
            assert isinstance(value, Mapping)
            filtered_arg_dict[key_name] = _recursive_merge(sub_table, value)
        elif key_name in dataclass_fields:
            filtered_arg_dict[key_name] = value
    return replace(dataclass, **filtered_arg_dict)
