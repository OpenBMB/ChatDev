# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""This module exists for compatibility reasons.

It's updated via tbump, do not modify.
"""

from __future__ import annotations

__version__ = "2.17.0"


def get_numversion_from_version(v: str) -> tuple[int, int, int]:
    """Kept for compatibility reason.

    See https://github.com/PyCQA/pylint/issues/4399
    https://github.com/PyCQA/pylint/issues/4420,
    """
    version = v.replace("pylint-", "")
    result_version = []
    for number in version.split(".")[0:3]:
        try:
            result_version.append(int(number))
        except ValueError:
            current_number = ""
            for char in number:
                if char.isdigit():
                    current_number += char
                else:
                    break
            try:
                result_version.append(int(current_number))
            except ValueError:
                result_version.append(0)
    while len(result_version) != 3:
        result_version.append(0)

    return tuple(result_version)  # type: ignore[return-value] # mypy can't infer the length


numversion = get_numversion_from_version(__version__)
