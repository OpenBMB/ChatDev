# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import os
import pathlib
import platform
import sys
from datetime import datetime

import astroid
import platformdirs

from pylint.__pkginfo__ import __version__
from pylint.typing import MessageTypesFullName

PY38_PLUS = sys.version_info[:2] >= (3, 8)
PY39_PLUS = sys.version_info[:2] >= (3, 9)
PY310_PLUS = sys.version_info[:2] >= (3, 10)

IS_PYPY = platform.python_implementation() == "PyPy"

PY_EXTS = (".py", ".pyc", ".pyo", ".pyw", ".so", ".dll")

MSG_STATE_CONFIDENCE = 2
_MSG_ORDER = "EWRCIF"
MSG_STATE_SCOPE_CONFIG = 0
MSG_STATE_SCOPE_MODULE = 1

# The line/node distinction does not apply to fatal errors and reports.
_SCOPE_EXEMPT = "FR"

MSG_TYPES: dict[str, MessageTypesFullName] = {
    "I": "info",
    "C": "convention",
    "R": "refactor",
    "W": "warning",
    "E": "error",
    "F": "fatal",
}
MSG_TYPES_LONG: dict[str, str] = {v: k for k, v in MSG_TYPES.items()}

MSG_TYPES_STATUS = {"I": 0, "C": 16, "R": 8, "W": 4, "E": 2, "F": 1}

# You probably don't want to change the MAIN_CHECKER_NAME
# This would affect rcfile generation and retro-compatibility
# on all project using [MAIN] in their rcfile.
MAIN_CHECKER_NAME = "main"

USER_HOME = os.path.expanduser("~")
# TODO: 3.0: Remove in 3.0 with all the surrounding code
OLD_DEFAULT_PYLINT_HOME = ".pylint.d"
DEFAULT_PYLINT_HOME = platformdirs.user_cache_dir("pylint")

DEFAULT_IGNORE_LIST = ("CVS",)


class WarningScope:
    LINE = "line-based-msg"
    NODE = "node-based-msg"


full_version = f"""pylint {__version__}
astroid {astroid.__version__}
Python {sys.version}"""

HUMAN_READABLE_TYPES = {
    "file": "file",
    "module": "module",
    "const": "constant",
    "class": "class",
    "function": "function",
    "method": "method",
    "attr": "attribute",
    "argument": "argument",
    "variable": "variable",
    "class_attribute": "class attribute",
    "class_const": "class constant",
    "inlinevar": "inline iteration",
    "typevar": "type variable",
    "typealias": "type alias",
}

# ignore some messages when emitting useless-suppression:
# - cyclic-import: can show false positives due to incomplete context
# - deprecated-{module, argument, class, method, decorator}:
#   can cause false positives for multi-interpreter projects
#   when linting with an interpreter on a lower python version
INCOMPATIBLE_WITH_USELESS_SUPPRESSION = frozenset(
    [
        "R0401",  # cyclic-import
        "W0402",  # deprecated-module
        "W1505",  # deprecated-method
        "W1511",  # deprecated-argument
        "W1512",  # deprecated-class
        "W1513",  # deprecated-decorator
        "R0801",  # duplicate-code
    ]
)


def _warn_about_old_home(pylint_home: pathlib.Path) -> None:
    """Warn users about the old pylint home being deprecated.

    The spam prevention mechanism is due to pylint being used in parallel by
    pre-commit, and the message being spammy in this context
    Also if you work with an old version of pylint that recreates the
    old pylint home, you can get the old message for a long time.
    """
    prefix_spam_prevention = "pylint_warned_about_old_cache_already"
    spam_prevention_file = pathlib.Path(pylint_home) / datetime.now().strftime(
        prefix_spam_prevention + "_%Y-%m-%d.temp"
    )
    old_home = pathlib.Path(USER_HOME) / OLD_DEFAULT_PYLINT_HOME

    if old_home.exists() and not spam_prevention_file.exists():
        print(
            f"PYLINTHOME is now '{pylint_home}' but obsolescent '{old_home}' is found; "
            "you can safely remove the latter",
            file=sys.stderr,
        )

        # Remove old spam prevention file
        if pylint_home.exists():
            for filename in pylint_home.iterdir():
                if prefix_spam_prevention in str(filename):
                    try:
                        os.remove(pylint_home / filename)
                    except OSError:  # pragma: no cover
                        pass

        # Create spam prevention file for today
        try:
            pylint_home.mkdir(parents=True, exist_ok=True)
            with open(spam_prevention_file, "w", encoding="utf8") as f:
                f.write("")
        except Exception as exc:  # pragma: no cover  # pylint: disable=broad-except
            print(
                "Can't write the file that was supposed to "
                f"prevent 'pylint.d' deprecation spam in {pylint_home} because of {exc}."
            )


def _get_pylint_home() -> str:
    """Return the pylint home."""
    if "PYLINTHOME" in os.environ:
        return os.environ["PYLINTHOME"]

    _warn_about_old_home(pathlib.Path(DEFAULT_PYLINT_HOME))

    return DEFAULT_PYLINT_HOME


PYLINT_HOME = _get_pylint_home()

TYPING_NORETURN = frozenset(
    (
        "typing.NoReturn",
        "typing_extensions.NoReturn",
    )
)
TYPING_NEVER = frozenset(
    (
        "typing.Never",
        "typing_extensions.Never",
    )
)

DUNDER_METHODS: dict[tuple[int, int], dict[str, str]] = {
    (0, 0): {
        "__init__": "Instantiate class directly",
        "__del__": "Use del keyword",
        "__repr__": "Use repr built-in function",
        "__str__": "Use str built-in function",
        "__bytes__": "Use bytes built-in function",
        "__format__": "Use format built-in function, format string method, or f-string",
        "__lt__": "Use < operator",
        "__le__": "Use <= operator",
        "__eq__": "Use == operator",
        "__ne__": "Use != operator",
        "__gt__": "Use > operator",
        "__ge__": "Use >= operator",
        "__hash__": "Use hash built-in function",
        "__bool__": "Use bool built-in function",
        "__getattr__": "Access attribute directly or use getattr built-in function",
        "__getattribute__": "Access attribute directly or use getattr built-in function",
        "__setattr__": "Set attribute directly or use setattr built-in function",
        "__delattr__": "Use del keyword",
        "__dir__": "Use dir built-in function",
        "__get__": "Use get method",
        "__set__": "Use set method",
        "__delete__": "Use del keyword",
        "__instancecheck__": "Use isinstance built-in function",
        "__subclasscheck__": "Use issubclass built-in function",
        "__call__": "Invoke instance directly",
        "__len__": "Use len built-in function",
        "__length_hint__": "Use length_hint method",
        "__getitem__": "Access item via subscript",
        "__setitem__": "Set item via subscript",
        "__delitem__": "Use del keyword",
        "__iter__": "Use iter built-in function",
        "__next__": "Use next built-in function",
        "__reversed__": "Use reversed built-in function",
        "__contains__": "Use in keyword",
        "__add__": "Use + operator",
        "__sub__": "Use - operator",
        "__mul__": "Use * operator",
        "__matmul__": "Use @ operator",
        "__truediv__": "Use / operator",
        "__floordiv__": "Use // operator",
        "__mod__": "Use % operator",
        "__divmod__": "Use divmod built-in function",
        "__pow__": "Use ** operator or pow built-in function",
        "__lshift__": "Use << operator",
        "__rshift__": "Use >> operator",
        "__and__": "Use & operator",
        "__xor__": "Use ^ operator",
        "__or__": "Use | operator",
        "__radd__": "Use + operator",
        "__rsub__": "Use - operator",
        "__rmul__": "Use * operator",
        "__rmatmul__": "Use @ operator",
        "__rtruediv__": "Use / operator",
        "__rfloordiv__": "Use // operator",
        "__rmod__": "Use % operator",
        "__rdivmod__": "Use divmod built-in function",
        "__rpow__": "Use ** operator or pow built-in function",
        "__rlshift__": "Use << operator",
        "__rrshift__": "Use >> operator",
        "__rand__": "Use & operator",
        "__rxor__": "Use ^ operator",
        "__ror__": "Use | operator",
        "__iadd__": "Use += operator",
        "__isub__": "Use -= operator",
        "__imul__": "Use *= operator",
        "__imatmul__": "Use @= operator",
        "__itruediv__": "Use /= operator",
        "__ifloordiv__": "Use //= operator",
        "__imod__": "Use %= operator",
        "__ipow__": "Use **= operator",
        "__ilshift__": "Use <<= operator",
        "__irshift__": "Use >>= operator",
        "__iand__": "Use &= operator",
        "__ixor__": "Use ^= operator",
        "__ior__": "Use |= operator",
        "__neg__": "Multiply by -1 instead",
        "__pos__": "Multiply by +1 instead",
        "__abs__": "Use abs built-in function",
        "__invert__": "Use ~ operator",
        "__complex__": "Use complex built-in function",
        "__int__": "Use int built-in function",
        "__float__": "Use float built-in function",
        "__round__": "Use round built-in function",
        "__trunc__": "Use math.trunc function",
        "__floor__": "Use math.floor function",
        "__ceil__": "Use math.ceil function",
        "__enter__": "Invoke context manager directly",
        "__aenter__": "Invoke context manager directly",
        "__copy__": "Use copy.copy function",
        "__deepcopy__": "Use copy.deepcopy function",
        "__fspath__": "Use os.fspath function instead",
    },
    (3, 10): {
        "__aiter__": "Use aiter built-in function",
        "__anext__": "Use anext built-in function",
    },
}

EXTRA_DUNDER_METHODS = [
    "__new__",
    "__subclasses__",
    "__init_subclass__",
    "__set_name__",
    "__class_getitem__",
    "__missing__",
    "__exit__",
    "__await__",
    "__aexit__",
    "__getnewargs_ex__",
    "__getnewargs__",
    "__getstate__",
    "__setstate__",
    "__reduce__",
    "__reduce_ex__",
    "__post_init__",  # part of `dataclasses` module
]

DUNDER_PROPERTIES = [
    "__class__",
    "__dict__",
    "__doc__",
    "__format__",
    "__module__",
    "__sizeof__",
    "__subclasshook__",
    "__weakref__",
]
