# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import tokenize
from io import StringIO
from tokenize import TokenInfo


def _tokenize_str(code: str) -> list[TokenInfo]:
    return list(tokenize.generate_tokens(StringIO(code).readline))
