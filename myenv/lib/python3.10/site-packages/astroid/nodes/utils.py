# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

from typing import NamedTuple


class Position(NamedTuple):
    """Position with line and column information."""

    lineno: int
    col_offset: int
    end_lineno: int
    end_col_offset: int
