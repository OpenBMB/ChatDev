"""Definitions of types for the Autoimport program."""
import pathlib
from enum import Enum
from typing import NamedTuple, Optional


class Source(Enum):
    """Describes the source of the package, for sorting purposes."""

    PROJECT = 0  # Obviously any project packages come first
    MANUAL = 1  # Placeholder since Autoimport classifies manually added modules
    BUILTIN = 2
    STANDARD = 3  # We want to favor standard library items
    SITE_PACKAGE = 4
    UNKNOWN = 5

    # modified_time


class ModuleInfo(NamedTuple):
    """Descriptor of information to get names from a module."""

    filepath: Optional[pathlib.Path]
    modname: str
    underlined: bool
    process_imports: bool


class ModuleFile(ModuleInfo):
    """Descriptor of information to get names from a file using ast."""

    filepath: pathlib.Path
    modname: str
    underlined: bool
    process_imports: bool


class ModuleCompiled(ModuleInfo):
    """Descriptor of information to get names using imports."""

    filepath = None
    modname: str
    underlined: bool
    process_imports: bool


class PackageType(Enum):
    """Describes the type of package, to determine how to get the names from it."""

    BUILTIN = 0  # No file exists, compiled into python. IE: Sys
    STANDARD = 1  # Just a folder
    COMPILED = 2  # .so module
    SINGLE_FILE = 3  # a .py file


class NameType(Enum):
    """Describes the type of Name for lsp completions. Taken from python lsp server."""

    Text = 1
    Method = 2
    Function = 3
    Constructor = 4
    Field = 5
    Variable = 6
    Class = 7
    Interface = 8
    Module = 9
    Property = 10
    Unit = 11
    Value = 12
    Enum = 13
    Keyword = 14
    Snippet = 15
    Color = 16
    File = 17
    Reference = 18
    Folder = 19
    EnumMember = 20
    Constant = 21
    Struct = 22
    Event = 23
    Operator = 24
    TypeParameter = 25


class Package(NamedTuple):
    """Attributes of a package."""

    name: str
    source: Source
    path: Optional[pathlib.Path]
    type: PackageType


class Name(NamedTuple):
    """A Name to be added to the database."""

    name: str
    modname: str
    package: str
    source: Source
    name_type: NameType


class PartialName(NamedTuple):
    """Partial information of a Name."""

    name: str
    name_type: NameType


class SearchResult(NamedTuple):
    """Search Result."""

    import_statement: str
    name: str
    source: int
    itemkind: int
