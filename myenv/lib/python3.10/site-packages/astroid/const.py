# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

import enum
import sys
from pathlib import Path

PY38 = sys.version_info[:2] == (3, 8)
PY38_PLUS = sys.version_info >= (3, 8)
PY39_PLUS = sys.version_info >= (3, 9)
PY310_PLUS = sys.version_info >= (3, 10)
PY311_PLUS = sys.version_info >= (3, 11)
BUILTINS = "builtins"  # TODO Remove in 2.8

WIN32 = sys.platform == "win32"

IS_PYPY = sys.implementation.name == "pypy"
IS_JYTHON = sys.implementation.name == "jython"

# pylint: disable-next=no-member
PYPY_7_3_11_PLUS = IS_PYPY and sys.pypy_version_info >= (7, 3, 11)  # type: ignore[attr-defined]


class Context(enum.Enum):
    Load = 1
    Store = 2
    Del = 3


# TODO Remove in 3.0 in favor of Context
Load = Context.Load
Store = Context.Store
Del = Context.Del


ASTROID_INSTALL_DIRECTORY = Path(__file__).parent
BRAIN_MODULES_DIRECTORY = ASTROID_INSTALL_DIRECTORY / "brain"


_EMPTY_OBJECT_MARKER = object()
