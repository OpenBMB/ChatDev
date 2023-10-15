# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

import operator
import re
import sys
from pathlib import Path

SYS_VERS_STR = (
    "%d%d%d" % sys.version_info[:3]  # pylint: disable=consider-using-f-string
)
TITLE_UNDERLINES = ["", "=", "-", "."]
UPDATE_OPTION = "--update-functional-output"
UPDATE_FILE = Path("pylint-functional-test-update")
# Common sub-expressions.
_MESSAGE = {"msg": r"[a-z][a-z\-]+"}
# Matches a #,
#  - followed by a comparison operator and a Python version (optional),
#  - followed by a line number with a +/- (optional),
#  - followed by a list of bracketed message symbols.
# Used to extract expected messages from testdata files.
_EXPECTED_RE = re.compile(
    r"\s*#\s*(?:(?P<line>[+-]?[0-9]+):)?"  # pylint: disable=consider-using-f-string
    r"(?:(?P<op>[><=]+) *(?P<version>[0-9.]+):)?"
    r"\s*\[(?P<msgs>%(msg)s(?:,\s*%(msg)s)*)]" % _MESSAGE
)

_OPERATORS = {">": operator.gt, "<": operator.lt, ">=": operator.ge, "<=": operator.le}
