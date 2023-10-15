# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

try:
    import isort.api
    import isort.settings

    HAS_ISORT_5 = True
except ImportError:  # isort < 5
    import isort

    HAS_ISORT_5 = False

import argparse
import codecs
import os
import re
import sys
import textwrap
import tokenize
import warnings
from collections.abc import Sequence
from io import BufferedReader, BytesIO
from typing import (
    TYPE_CHECKING,
    Any,
    List,
    Pattern,
    TextIO,
    Tuple,
    TypeVar,
    Union,
    overload,
)

from astroid import Module, modutils, nodes

from pylint.constants import PY_EXTS
from pylint.typing import OptionDict

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal

if TYPE_CHECKING:
    from pylint.checkers.base_checker import BaseChecker
    from pylint.lint import PyLinter

DEFAULT_LINE_LENGTH = 79

# These are types used to overload get_global_option() and refer to the options type
GLOBAL_OPTION_BOOL = Literal[
    "suggestion-mode",
    "analyse-fallback-blocks",
    "allow-global-unused-variables",
]
GLOBAL_OPTION_INT = Literal["max-line-length", "docstring-min-length"]
GLOBAL_OPTION_LIST = Literal["ignored-modules"]
GLOBAL_OPTION_PATTERN = Literal[
    "no-docstring-rgx",
    "dummy-variables-rgx",
    "ignored-argument-names",
    "mixin-class-rgx",
]
GLOBAL_OPTION_PATTERN_LIST = Literal["exclude-too-few-public-methods", "ignore-paths"]
GLOBAL_OPTION_TUPLE_INT = Literal["py-version"]
GLOBAL_OPTION_NAMES = Union[
    GLOBAL_OPTION_BOOL,
    GLOBAL_OPTION_INT,
    GLOBAL_OPTION_LIST,
    GLOBAL_OPTION_PATTERN,
    GLOBAL_OPTION_PATTERN_LIST,
    GLOBAL_OPTION_TUPLE_INT,
]
T_GlobalOptionReturnTypes = TypeVar(
    "T_GlobalOptionReturnTypes",
    bool,
    int,
    List[str],
    Pattern[str],
    List[Pattern[str]],
    Tuple[int, ...],
)


def normalize_text(
    text: str, line_len: int = DEFAULT_LINE_LENGTH, indent: str = ""
) -> str:
    """Wrap the text on the given line length."""
    return "\n".join(
        textwrap.wrap(
            text, width=line_len, initial_indent=indent, subsequent_indent=indent
        )
    )


CMPS = ["=", "-", "+"]


# py3k has no more cmp builtin
def cmp(a: int | float, b: int | float) -> int:
    return (a > b) - (a < b)


def diff_string(old: int | float, new: int | float) -> str:
    """Given an old and new int value, return a string representing the
    difference.
    """
    diff = abs(old - new)
    diff_str = f"{CMPS[cmp(old, new)]}{diff and f'{diff:.2f}' or ''}"
    return diff_str


def get_module_and_frameid(node: nodes.NodeNG) -> tuple[str, str]:
    """Return the module name and the frame id in the module."""
    frame = node.frame(future=True)
    module, obj = "", []
    while frame:
        if isinstance(frame, Module):
            module = frame.name
        else:
            obj.append(getattr(frame, "name", "<lambda>"))
        try:
            frame = frame.parent.frame(future=True)
        except AttributeError:
            break
    obj.reverse()
    return module, ".".join(obj)


def get_rst_title(title: str, character: str) -> str:
    """Permit to get a title formatted as ReStructuredText test (underlined with a
    chosen character).
    """
    return f"{title}\n{character * len(title)}\n"


def get_rst_section(
    section: str | None,
    options: list[tuple[str, OptionDict, Any]],
    doc: str | None = None,
) -> str:
    """Format an option's section using as a ReStructuredText formatted output."""
    result = ""
    if section:
        result += get_rst_title(section, "'")
    if doc:
        formatted_doc = normalize_text(doc)
        result += f"{formatted_doc}\n\n"
    for optname, optdict, value in options:
        help_opt = optdict.get("help")
        result += f":{optname}:\n"
        if help_opt:
            assert isinstance(help_opt, str)
            formatted_help = normalize_text(help_opt, indent="  ")
            result += f"{formatted_help}\n"
        if value and optname != "py-version":
            value = str(_format_option_value(optdict, value))
            result += f"\n  Default: ``{value.replace('`` ', '```` ``')}``\n"
    return result


def decoding_stream(
    stream: BufferedReader | BytesIO,
    encoding: str,
    errors: Literal["strict"] = "strict",
) -> codecs.StreamReader:
    try:
        reader_cls = codecs.getreader(encoding or sys.getdefaultencoding())
    except LookupError:
        reader_cls = codecs.getreader(sys.getdefaultencoding())
    return reader_cls(stream, errors)


def tokenize_module(node: nodes.Module) -> list[tokenize.TokenInfo]:
    with node.stream() as stream:
        readline = stream.readline
        return list(tokenize.tokenize(readline))


def register_plugins(linter: PyLinter, directory: str) -> None:
    """Load all module and package in the given directory, looking for a
    'register' function in each one, used to register pylint checkers.
    """
    imported = {}
    for filename in os.listdir(directory):
        base, extension = os.path.splitext(filename)
        if base in imported or base == "__pycache__":
            continue
        if (
            extension in PY_EXTS
            and base != "__init__"
            or (
                not extension
                and os.path.isdir(os.path.join(directory, base))
                and not filename.startswith(".")
            )
        ):
            try:
                module = modutils.load_module_from_file(
                    os.path.join(directory, filename)
                )
            except ValueError:
                # empty module name (usually Emacs auto-save files)
                continue
            except ImportError as exc:
                print(f"Problem importing module {filename}: {exc}", file=sys.stderr)
            else:
                if hasattr(module, "register"):
                    module.register(linter)
                    imported[base] = 1


@overload
def get_global_option(
    checker: BaseChecker, option: GLOBAL_OPTION_BOOL, default: bool | None = ...
) -> bool:
    ...


@overload
def get_global_option(
    checker: BaseChecker, option: GLOBAL_OPTION_INT, default: int | None = ...
) -> int:
    ...


@overload
def get_global_option(
    checker: BaseChecker,
    option: GLOBAL_OPTION_LIST,
    default: list[str] | None = ...,
) -> list[str]:
    ...


@overload
def get_global_option(
    checker: BaseChecker,
    option: GLOBAL_OPTION_PATTERN,
    default: Pattern[str] | None = ...,
) -> Pattern[str]:
    ...


@overload
def get_global_option(
    checker: BaseChecker,
    option: GLOBAL_OPTION_PATTERN_LIST,
    default: list[Pattern[str]] | None = ...,
) -> list[Pattern[str]]:
    ...


@overload
def get_global_option(
    checker: BaseChecker,
    option: GLOBAL_OPTION_TUPLE_INT,
    default: tuple[int, ...] | None = ...,
) -> tuple[int, ...]:
    ...


def get_global_option(
    checker: BaseChecker,
    option: GLOBAL_OPTION_NAMES,
    default: T_GlobalOptionReturnTypes | None = None,  # pylint: disable=unused-argument
) -> T_GlobalOptionReturnTypes | None | Any:
    """DEPRECATED: Retrieve an option defined by the given *checker* or
    by all known option providers.

    It will look in the list of all options providers
    until the given *option* will be found.
    If the option wasn't found, the *default* value will be returned.
    """
    warnings.warn(
        "get_global_option has been deprecated. You can use "
        "checker.linter.config to get all global options instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return getattr(checker.linter.config, option.replace("-", "_"))


def _splitstrip(string: str, sep: str = ",") -> list[str]:
    """Return a list of stripped string by splitting the string given as
    argument on `sep` (',' by default), empty strings are discarded.

    >>> _splitstrip('a, b, c   ,  4,,')
    ['a', 'b', 'c', '4']
    >>> _splitstrip('a')
    ['a']
    >>> _splitstrip('a,\nb,\nc,')
    ['a', 'b', 'c']

    :type string: str or unicode
    :param string: a csv line

    :type sep: str or unicode
    :param sep: field separator, default to the comma (',')

    :rtype: str or unicode
    :return: the unquoted string (or the input string if it wasn't quoted)
    """
    return [word.strip() for word in string.split(sep) if word.strip()]


def _unquote(string: str) -> str:
    """Remove optional quotes (simple or double) from the string.

    :param string: an optionally quoted string
    :return: the unquoted string (or the input string if it wasn't quoted)
    """
    if not string:
        return string
    if string[0] in "\"'":
        string = string[1:]
    if string[-1] in "\"'":
        string = string[:-1]
    return string


def _check_csv(value: list[str] | tuple[str] | str) -> Sequence[str]:
    if isinstance(value, (list, tuple)):
        return value
    return _splitstrip(value)


def _comment(string: str) -> str:
    """Return string as a comment."""
    lines = [line.strip() for line in string.splitlines()]
    sep = "\n"
    return "# " + f"{sep}# ".join(lines)


def _format_option_value(optdict: OptionDict, value: Any) -> str:
    """Return the user input's value from a 'compiled' value.

    TODO: 3.0: Remove deprecated function
    """
    if optdict.get("type", None) == "py_version":
        value = ".".join(str(item) for item in value)
    elif isinstance(value, (list, tuple)):
        value = ",".join(_format_option_value(optdict, item) for item in value)
    elif isinstance(value, dict):
        value = ",".join(f"{k}:{v}" for k, v in value.items())
    elif hasattr(value, "match"):  # optdict.get('type') == 'regexp'
        # compiled regexp
        value = value.pattern
    elif optdict.get("type") == "yn":
        value = "yes" if value else "no"
    elif isinstance(value, str) and value.isspace():
        value = f"'{value}'"
    return str(value)


def format_section(
    stream: TextIO,
    section: str,
    options: list[tuple[str, OptionDict, Any]],
    doc: str | None = None,
) -> None:
    """Format an option's section using the INI format."""
    warnings.warn(
        "format_section has been deprecated. It will be removed in pylint 3.0.",
        DeprecationWarning,
        stacklevel=2,
    )
    if doc:
        print(_comment(doc), file=stream)
    print(f"[{section}]", file=stream)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        _ini_format(stream, options)


def _ini_format(stream: TextIO, options: list[tuple[str, OptionDict, Any]]) -> None:
    """Format options using the INI format."""
    warnings.warn(
        "_ini_format has been deprecated. It will be removed in pylint 3.0.",
        DeprecationWarning,
        stacklevel=2,
    )
    for optname, optdict, value in options:
        # Skip deprecated option
        if "kwargs" in optdict:
            assert isinstance(optdict["kwargs"], dict)
            if "new_names" in optdict["kwargs"]:
                continue
        value = _format_option_value(optdict, value)
        help_opt = optdict.get("help")
        if help_opt:
            assert isinstance(help_opt, str)
            help_opt = normalize_text(help_opt, indent="# ")
            print(file=stream)
            print(help_opt, file=stream)
        else:
            print(file=stream)
        if value in {"None", "False"}:
            print(f"#{optname}=", file=stream)
        else:
            value = str(value).strip()
            if re.match(r"^([\w-]+,)+[\w-]+$", str(value)):
                separator = "\n " + " " * len(optname)
                value = separator.join(x + "," for x in str(value).split(","))
                # remove trailing ',' from last element of the list
                value = value[:-1]
            print(f"{optname}={value}", file=stream)


class IsortDriver:
    """A wrapper around isort API that changed between versions 4 and 5."""

    def __init__(self, config: argparse.Namespace) -> None:
        if HAS_ISORT_5:
            self.isort5_config = isort.settings.Config(
                # There is no typo here. EXTRA_standard_library is
                # what most users want. The option has been named
                # KNOWN_standard_library for ages in pylint, and we
                # don't want to break compatibility.
                extra_standard_library=config.known_standard_library,
                known_third_party=config.known_third_party,
            )
        else:
            # pylint: disable-next=no-member
            self.isort4_obj = isort.SortImports(  # type: ignore[attr-defined]
                file_contents="",
                known_standard_library=config.known_standard_library,
                known_third_party=config.known_third_party,
            )

    def place_module(self, package: str) -> str:
        if HAS_ISORT_5:
            return isort.api.place_module(package, self.isort5_config)
        return self.isort4_obj.place_module(package)  # type: ignore[no-any-return]
