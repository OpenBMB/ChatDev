# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import re
from collections.abc import Generator
from typing import NamedTuple

# Allow stopping after the first semicolon/hash encountered,
# so that an option can be continued with the reasons
# why it is active or disabled.
OPTION_RGX = r"""
    (?:^\s*\#.*|\s*|               # Comment line, or whitespaces,
       \s*\#.*(?=\#.*?\bpylint:))  # or a beginning of an inline comment
                                   # followed by "pylint:" pragma
    (\#                            # Beginning of comment
    .*?                            # Anything (as little as possible)
    \bpylint:                      # pylint word and column
    \s*                            # Any number of whitespaces
    ([^;#\n]+))                    # Anything except semicolon or hash or
                                   # newline (it is the second matched group)
                                   # and end of the first matched group
    [;#]{0,1}                      # From 0 to 1 repetition of semicolon or hash
"""
OPTION_PO = re.compile(OPTION_RGX, re.VERBOSE)


class PragmaRepresenter(NamedTuple):
    action: str
    messages: list[str]


ATOMIC_KEYWORDS = frozenset(("disable-all", "skip-file"))
MESSAGE_KEYWORDS = frozenset(
    ("disable-next", "disable-msg", "enable-msg", "disable", "enable")
)
# sorted is necessary because sets are unordered collections and ALL_KEYWORDS
# string should not vary between executions
# reverse is necessary in order to have the longest keywords first, so that, for example,
# 'disable' string should not be matched instead of 'disable-all'
ALL_KEYWORDS = "|".join(
    sorted(ATOMIC_KEYWORDS | MESSAGE_KEYWORDS, key=len, reverse=True)
)


TOKEN_SPECIFICATION = [
    ("KEYWORD", rf"\b({ALL_KEYWORDS:s})\b"),
    ("MESSAGE_STRING", r"[0-9A-Za-z\-\_]{2,}"),  # Identifiers
    ("ASSIGN", r"="),  # Assignment operator
    ("MESSAGE_NUMBER", r"[CREIWF]{1}\d*"),
]

TOK_REGEX = "|".join(
    f"(?P<{token_name:s}>{token_rgx:s})"
    for token_name, token_rgx in TOKEN_SPECIFICATION
)


def emit_pragma_representer(action: str, messages: list[str]) -> PragmaRepresenter:
    if not messages and action in MESSAGE_KEYWORDS:
        raise InvalidPragmaError(
            "The keyword is not followed by message identifier", action
        )
    return PragmaRepresenter(action, messages)


class PragmaParserError(Exception):
    """A class for exceptions thrown by pragma_parser module."""

    def __init__(self, message: str, token: str) -> None:
        """:args message: explain the reason why the exception has been thrown
        :args token: token concerned by the exception.
        """
        self.message = message
        self.token = token
        super().__init__(self.message)


class UnRecognizedOptionError(PragmaParserError):
    """Thrown in case the of a valid but unrecognized option."""


class InvalidPragmaError(PragmaParserError):
    """Thrown in case the pragma is invalid."""


def parse_pragma(pylint_pragma: str) -> Generator[PragmaRepresenter, None, None]:
    action: str | None = None
    messages: list[str] = []
    assignment_required = False
    previous_token = ""

    for mo in re.finditer(TOK_REGEX, pylint_pragma):
        kind = mo.lastgroup
        value = mo.group()

        if kind == "ASSIGN":
            if not assignment_required:
                if action:
                    # A keyword has been found previously but doesn't support assignment
                    raise UnRecognizedOptionError(
                        "The keyword doesn't support assignment", action
                    )
                if previous_token:
                    # Something found previously but not a known keyword
                    raise UnRecognizedOptionError(
                        "The keyword is unknown", previous_token
                    )
                # Nothing at all detected before this assignment
                raise InvalidPragmaError("Missing keyword before assignment", "")
            assignment_required = False
        elif assignment_required:
            raise InvalidPragmaError(
                "The = sign is missing after the keyword", action or ""
            )
        elif kind == "KEYWORD":
            if action:
                yield emit_pragma_representer(action, messages)
            action = value
            messages = []
            assignment_required = action in MESSAGE_KEYWORDS
        elif kind in {"MESSAGE_STRING", "MESSAGE_NUMBER"}:
            messages.append(value)
            assignment_required = False
        else:
            raise RuntimeError("Token not recognized")

        previous_token = value

    if action:
        yield emit_pragma_representer(action, messages)
    else:
        raise UnRecognizedOptionError("The keyword is unknown", previous_token)
