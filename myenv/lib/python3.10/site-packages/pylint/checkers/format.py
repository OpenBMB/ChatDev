# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Python code format's checker.

By default, try to follow Guido's style guide :

https://www.python.org/doc/essays/styleguide/

Some parts of the process_token method is based from The Tab Nanny std module.
"""

from __future__ import annotations

import sys
import tokenize
from functools import reduce
from re import Match
from typing import TYPE_CHECKING

from astroid import nodes

from pylint.checkers import BaseRawFileChecker, BaseTokenChecker
from pylint.checkers.utils import only_required_for_messages
from pylint.constants import WarningScope
from pylint.interfaces import HIGH
from pylint.typing import MessageDefinitionTuple
from pylint.utils.pragma_parser import OPTION_PO, PragmaParserError, parse_pragma

if TYPE_CHECKING:
    from pylint.lint import PyLinter

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal

_KEYWORD_TOKENS = {
    "assert",
    "del",
    "elif",
    "except",
    "for",
    "if",
    "in",
    "not",
    "raise",
    "return",
    "while",
    "yield",
    "with",
    "=",
    ":=",
}
_JUNK_TOKENS = {tokenize.COMMENT, tokenize.NL}


MSGS: dict[str, MessageDefinitionTuple] = {
    "C0301": (
        "Line too long (%s/%s)",
        "line-too-long",
        "Used when a line is longer than a given number of characters.",
    ),
    "C0302": (
        "Too many lines in module (%s/%s)",  # was W0302
        "too-many-lines",
        "Used when a module has too many lines, reducing its readability.",
    ),
    "C0303": (
        "Trailing whitespace",
        "trailing-whitespace",
        "Used when there is whitespace between the end of a line and the newline.",
    ),
    "C0304": (
        "Final newline missing",
        "missing-final-newline",
        "Used when the last line in a file is missing a newline.",
    ),
    "C0305": (
        "Trailing newlines",
        "trailing-newlines",
        "Used when there are trailing blank lines in a file.",
    ),
    "W0311": (
        "Bad indentation. Found %s %s, expected %s",
        "bad-indentation",
        "Used when an unexpected number of indentation's tabulations or "
        "spaces has been found.",
    ),
    "W0301": (
        "Unnecessary semicolon",  # was W0106
        "unnecessary-semicolon",
        'Used when a statement is ended by a semi-colon (";"), which '
        "isn't necessary (that's python, not C ;).",
    ),
    "C0321": (
        "More than one statement on a single line",
        "multiple-statements",
        "Used when more than on statement are found on the same line.",
        {"scope": WarningScope.NODE},
    ),
    "C0325": (
        "Unnecessary parens after %r keyword",
        "superfluous-parens",
        "Used when a single item in parentheses follows an if, for, or "
        "other keyword.",
    ),
    "C0327": (
        "Mixed line endings LF and CRLF",
        "mixed-line-endings",
        "Used when there are mixed (LF and CRLF) newline signs in a file.",
    ),
    "C0328": (
        "Unexpected line ending format. There is '%s' while it should be '%s'.",
        "unexpected-line-ending-format",
        "Used when there is different newline than expected.",
    ),
}


def _last_token_on_line_is(tokens: TokenWrapper, line_end: int, token: str) -> bool:
    return (
        line_end > 0
        and tokens.token(line_end - 1) == token
        or line_end > 1
        and tokens.token(line_end - 2) == token
        and tokens.type(line_end - 1) == tokenize.COMMENT
    )


class TokenWrapper:
    """A wrapper for readable access to token information."""

    def __init__(self, tokens: list[tokenize.TokenInfo]) -> None:
        self._tokens = tokens

    def token(self, idx: int) -> str:
        return self._tokens[idx][1]

    def type(self, idx: int) -> int:
        return self._tokens[idx][0]

    def start_line(self, idx: int) -> int:
        return self._tokens[idx][2][0]

    def start_col(self, idx: int) -> int:
        return self._tokens[idx][2][1]

    def line(self, idx: int) -> str:
        return self._tokens[idx][4]


class FormatChecker(BaseTokenChecker, BaseRawFileChecker):
    """Formatting checker.

    Checks for :
    * unauthorized constructions
    * strict indentation
    * line length
    """

    # configuration section name
    name = "format"
    # messages
    msgs = MSGS
    # configuration options
    # for available dict keys/values see the optik parser 'add_option' method
    options = (
        (
            "max-line-length",
            {
                "default": 100,
                "type": "int",
                "metavar": "<int>",
                "help": "Maximum number of characters on a single line.",
            },
        ),
        (
            "ignore-long-lines",
            {
                "type": "regexp",
                "metavar": "<regexp>",
                "default": r"^\s*(# )?<?https?://\S+>?$",
                "help": (
                    "Regexp for a line that is allowed to be longer than the limit."
                ),
            },
        ),
        (
            "single-line-if-stmt",
            {
                "default": False,
                "type": "yn",
                "metavar": "<y or n>",
                "help": (
                    "Allow the body of an if to be on the same "
                    "line as the test if there is no else."
                ),
            },
        ),
        (
            "single-line-class-stmt",
            {
                "default": False,
                "type": "yn",
                "metavar": "<y or n>",
                "help": (
                    "Allow the body of a class to be on the same "
                    "line as the declaration if body contains "
                    "single statement."
                ),
            },
        ),
        (
            "max-module-lines",
            {
                "default": 1000,
                "type": "int",
                "metavar": "<int>",
                "help": "Maximum number of lines in a module.",
            },
        ),
        (
            "indent-string",
            {
                "default": "    ",
                "type": "non_empty_string",
                "metavar": "<string>",
                "help": "String used as indentation unit. This is usually "
                '"    " (4 spaces) or "\\t" (1 tab).',
            },
        ),
        (
            "indent-after-paren",
            {
                "type": "int",
                "metavar": "<int>",
                "default": 4,
                "help": "Number of spaces of indent required inside a hanging "
                "or continued line.",
            },
        ),
        (
            "expected-line-ending-format",
            {
                "type": "choice",
                "metavar": "<empty or LF or CRLF>",
                "default": "",
                "choices": ["", "LF", "CRLF"],
                "help": (
                    "Expected format of line ending, "
                    "e.g. empty (any line ending), LF or CRLF."
                ),
            },
        ),
    )

    def __init__(self, linter: PyLinter) -> None:
        super().__init__(linter)
        self._lines: dict[int, str] = {}
        self._visited_lines: dict[int, Literal[1, 2]] = {}

    def new_line(self, tokens: TokenWrapper, line_end: int, line_start: int) -> None:
        """A new line has been encountered, process it if necessary."""
        if _last_token_on_line_is(tokens, line_end, ";"):
            self.add_message("unnecessary-semicolon", line=tokens.start_line(line_end))

        line_num = tokens.start_line(line_start)
        line = tokens.line(line_start)
        if tokens.type(line_start) not in _JUNK_TOKENS:
            self._lines[line_num] = line.split("\n")[0]
        self.check_lines(tokens, line_start, line, line_num)

    def process_module(self, node: nodes.Module) -> None:
        pass

    # pylint: disable-next = too-many-return-statements, too-many-branches
    def _check_keyword_parentheses(
        self, tokens: list[tokenize.TokenInfo], start: int
    ) -> None:
        """Check that there are not unnecessary parentheses after a keyword.

        Parens are unnecessary if there is exactly one balanced outer pair on a
        line and contains no commas (i.e. is not a tuple).

        Args:
        tokens: The entire list of Tokens.
        start: The position of the keyword in the token list.
        """
        # If the next token is not a paren, we're fine.
        if tokens[start + 1].string != "(":
            return
        if (
            tokens[start].string == "not"
            and start > 0
            and tokens[start - 1].string == "is"
        ):
            # If this is part of an `is not` expression, we have a binary operator
            # so the parentheses are not necessarily redundant.
            return
        found_and_or = False
        contains_walrus_operator = False
        walrus_operator_depth = 0
        contains_double_parens = 0
        depth = 0
        keyword_token = str(tokens[start].string)
        line_num = tokens[start].start[0]
        for i in range(start, len(tokens) - 1):
            token = tokens[i]

            # If we hit a newline, then assume any parens were for continuation.
            if token.type == tokenize.NL:
                return
            # Since the walrus operator doesn't exist below python3.8, the tokenizer
            # generates independent tokens
            if (
                token.string == ":="  # <-- python3.8+ path
                or token.string + tokens[i + 1].string == ":="
            ):
                contains_walrus_operator = True
                walrus_operator_depth = depth
            if token.string == "(":
                depth += 1
                if tokens[i + 1].string == "(":
                    contains_double_parens = 1
            elif token.string == ")":
                depth -= 1
                if depth:
                    if contains_double_parens and tokens[i + 1].string == ")":
                        # For walrus operators in `if (not)` conditions and comprehensions
                        if keyword_token in {"in", "if", "not"}:
                            continue
                        return
                    contains_double_parens -= 1
                    continue
                # ')' can't happen after if (foo), since it would be a syntax error.
                if tokens[i + 1].string in {":", ")", "]", "}", "in"} or tokens[
                    i + 1
                ].type in {tokenize.NEWLINE, tokenize.ENDMARKER, tokenize.COMMENT}:
                    if contains_walrus_operator and walrus_operator_depth - 1 == depth:
                        return
                    # The empty tuple () is always accepted.
                    if i == start + 2:
                        return
                    if found_and_or:
                        return
                    if keyword_token == "in":
                        # This special case was added in https://github.com/PyCQA/pylint/pull/4948
                        # but it could be removed in the future. Avoid churn for now.
                        return
                    self.add_message(
                        "superfluous-parens", line=line_num, args=keyword_token
                    )
                return
            elif depth == 1:
                # This is a tuple, which is always acceptable.
                if token[1] == ",":
                    return
                # 'and' and 'or' are the only boolean operators with lower precedence
                # than 'not', so parens are only required when they are found.
                if token[1] in {"and", "or"}:
                    found_and_or = True
                # A yield inside an expression must always be in parentheses,
                # quit early without error.
                elif token[1] == "yield":
                    return
                # A generator expression always has a 'for' token in it, and
                # the 'for' token is only legal inside parens when it is in a
                # generator expression.  The parens are necessary here, so bail
                # without an error.
                elif token[1] == "for":
                    return
                # A generator expression can have an 'else' token in it.
                # We check the rest of the tokens to see if any problems occur after
                # the 'else'.
                elif token[1] == "else":
                    if "(" in (i.string for i in tokens[i:]):
                        self._check_keyword_parentheses(tokens[i:], 0)
                    return

    def process_tokens(self, tokens: list[tokenize.TokenInfo]) -> None:
        """Process tokens and search for:

        - too long lines (i.e. longer than <max_chars>)
        - optionally bad construct (if given, bad_construct must be a compiled
          regular expression).
        """
        indents = [0]
        check_equal = False
        line_num = 0
        self._lines = {}
        self._visited_lines = {}
        self._last_line_ending: str | None = None
        last_blank_line_num = 0
        for idx, (tok_type, string, start, _, line) in enumerate(tokens):
            if start[0] != line_num:
                line_num = start[0]
                # A tokenizer oddity: if an indented line contains a multi-line
                # docstring, the line member of the INDENT token does not contain
                # the full line; therefore we check the next token on the line.
                if tok_type == tokenize.INDENT:
                    self.new_line(TokenWrapper(tokens), idx - 1, idx + 1)
                else:
                    self.new_line(TokenWrapper(tokens), idx - 1, idx)

            if tok_type == tokenize.NEWLINE:
                # a program statement, or ENDMARKER, will eventually follow,
                # after some (possibly empty) run of tokens of the form
                #     (NL | COMMENT)* (INDENT | DEDENT+)?
                # If an INDENT appears, setting check_equal is wrong, and will
                # be undone when we see the INDENT.
                check_equal = True
                self._check_line_ending(string, line_num)
            elif tok_type == tokenize.INDENT:
                check_equal = False
                self.check_indent_level(string, indents[-1] + 1, line_num)
                indents.append(indents[-1] + 1)
            elif tok_type == tokenize.DEDENT:
                # there's nothing we need to check here!  what's important is
                # that when the run of DEDENTs ends, the indentation of the
                # program statement (or ENDMARKER) that triggered the run is
                # equal to what's left at the top of the indents stack
                check_equal = True
                if len(indents) > 1:
                    del indents[-1]
            elif tok_type == tokenize.NL:
                if not line.strip("\r\n"):
                    last_blank_line_num = line_num
            elif tok_type not in (tokenize.COMMENT, tokenize.ENCODING):
                # This is the first concrete token following a NEWLINE, so it
                # must be the first token of the next program statement, or an
                # ENDMARKER; the "line" argument exposes the leading white-space
                # for this statement; in the case of ENDMARKER, line is an empty
                # string, so will properly match the empty string with which the
                # "indents" stack was seeded
                if check_equal:
                    check_equal = False
                    self.check_indent_level(line, indents[-1], line_num)

            if tok_type == tokenize.NUMBER and string.endswith("l"):
                self.add_message("lowercase-l-suffix", line=line_num)

            if string in _KEYWORD_TOKENS:
                self._check_keyword_parentheses(tokens, idx)

        line_num -= 1  # to be ok with "wc -l"
        if line_num > self.linter.config.max_module_lines:
            # Get the line where the too-many-lines (or its message id)
            # was disabled or default to 1.
            message_definition = self.linter.msgs_store.get_message_definitions(
                "too-many-lines"
            )[0]
            names = (message_definition.msgid, "too-many-lines")
            lineno = next(
                filter(None, (self.linter._pragma_lineno.get(name) for name in names)),
                1,
            )
            self.add_message(
                "too-many-lines",
                args=(line_num, self.linter.config.max_module_lines),
                line=lineno,
            )

        # See if there are any trailing lines.  Do not complain about empty
        # files like __init__.py markers.
        if line_num == last_blank_line_num and line_num > 0:
            self.add_message("trailing-newlines", line=line_num)

    def _check_line_ending(self, line_ending: str, line_num: int) -> None:
        # check if line endings are mixed
        if self._last_line_ending is not None:
            # line_ending == "" indicates a synthetic newline added at
            # the end of a file that does not, in fact, end with a
            # newline.
            if line_ending and line_ending != self._last_line_ending:
                self.add_message("mixed-line-endings", line=line_num)

        self._last_line_ending = line_ending

        # check if line ending is as expected
        expected = self.linter.config.expected_line_ending_format
        if expected:
            # reduce multiple \n\n\n\n to one \n
            line_ending = reduce(lambda x, y: x + y if x != y else x, line_ending, "")
            line_ending = "LF" if line_ending == "\n" else "CRLF"
            if line_ending != expected:
                self.add_message(
                    "unexpected-line-ending-format",
                    args=(line_ending, expected),
                    line=line_num,
                )

    @only_required_for_messages("multiple-statements")
    def visit_default(self, node: nodes.NodeNG) -> None:
        """Check the node line number and check it if not yet done."""
        if not node.is_statement:
            return
        if not node.root().pure_python:
            return
        prev_sibl = node.previous_sibling()
        if prev_sibl is not None:
            prev_line = prev_sibl.fromlineno
        # The line on which a 'finally': occurs in a 'try/finally'
        # is not directly represented in the AST. We infer it
        # by taking the last line of the body and adding 1, which
        # should be the line of finally:
        elif (
            isinstance(node.parent, nodes.TryFinally) and node in node.parent.finalbody
        ):
            prev_line = node.parent.body[0].tolineno + 1
        elif isinstance(node.parent, nodes.Module):
            prev_line = 0
        else:
            prev_line = node.parent.statement(future=True).fromlineno
        line = node.fromlineno
        assert line, node
        if prev_line == line and self._visited_lines.get(line) != 2:
            self._check_multi_statement_line(node, line)
            return
        if line in self._visited_lines:
            return
        try:
            tolineno = node.blockstart_tolineno
        except AttributeError:
            tolineno = node.tolineno
        assert tolineno, node
        lines: list[str] = []
        for line in range(line, tolineno + 1):  # noqa: B020
            self._visited_lines[line] = 1
            try:
                lines.append(self._lines[line].rstrip())
            except KeyError:
                lines.append("")

    def _check_multi_statement_line(self, node: nodes.NodeNG, line: int) -> None:
        """Check for lines containing multiple statements."""
        # Do not warn about multiple nested context managers
        # in with statements.
        if isinstance(node, nodes.With):
            return
        # For try... except... finally..., the two nodes
        # appear to be on the same line due to how the AST is built.
        if isinstance(node, nodes.TryExcept) and isinstance(
            node.parent, nodes.TryFinally
        ):
            return
        if (
            isinstance(node.parent, nodes.If)
            and not node.parent.orelse
            and self.linter.config.single_line_if_stmt
        ):
            return
        if (
            isinstance(node.parent, nodes.ClassDef)
            and len(node.parent.body) == 1
            and self.linter.config.single_line_class_stmt
        ):
            return

        # Functions stubs with ``Ellipsis`` as body are exempted.
        if (
            isinstance(node.parent, nodes.FunctionDef)
            and isinstance(node, nodes.Expr)
            and isinstance(node.value, nodes.Const)
            and node.value.value is Ellipsis
        ):
            return

        self.add_message("multiple-statements", node=node)
        self._visited_lines[line] = 2

    def check_trailing_whitespace_ending(self, line: str, i: int) -> None:
        """Check that there is no trailing white-space."""
        # exclude \f (formfeed) from the rstrip
        stripped_line = line.rstrip("\t\n\r\v ")
        if line[len(stripped_line) :] not in ("\n", "\r\n"):
            self.add_message(
                "trailing-whitespace",
                line=i,
                col_offset=len(stripped_line),
                confidence=HIGH,
            )

    def check_line_length(self, line: str, i: int, checker_off: bool) -> None:
        """Check that the line length is less than the authorized value."""
        max_chars = self.linter.config.max_line_length
        ignore_long_line = self.linter.config.ignore_long_lines
        line = line.rstrip()
        if len(line) > max_chars and not ignore_long_line.search(line):
            if checker_off:
                self.linter.add_ignored_message("line-too-long", i)
            else:
                self.add_message("line-too-long", line=i, args=(len(line), max_chars))

    @staticmethod
    def remove_pylint_option_from_lines(options_pattern_obj: Match[str]) -> str:
        """Remove the `# pylint ...` pattern from lines."""
        lines = options_pattern_obj.string
        purged_lines = (
            lines[: options_pattern_obj.start(1)].rstrip()
            + lines[options_pattern_obj.end(1) :]
        )
        return purged_lines

    @staticmethod
    def is_line_length_check_activated(pylint_pattern_match_object: Match[str]) -> bool:
        """Return True if the line length check is activated."""
        try:
            for pragma in parse_pragma(pylint_pattern_match_object.group(2)):
                if pragma.action == "disable" and "line-too-long" in pragma.messages:
                    return False
        except PragmaParserError:
            # Printing useful information dealing with this error is done in the lint package
            pass
        return True

    @staticmethod
    def specific_splitlines(lines: str) -> list[str]:
        """Split lines according to universal newlines except those in a specific
        sets.
        """
        unsplit_ends = {
            "\x0b",  # synonym of \v
            "\x0c",  # synonym of \f
            "\x1c",
            "\x1d",
            "\x1e",
            "\x85",
            "\u2028",
            "\u2029",
        }
        res: list[str] = []
        buffer = ""
        for atomic_line in lines.splitlines(True):
            if atomic_line[-1] not in unsplit_ends:
                res.append(buffer + atomic_line)
                buffer = ""
            else:
                buffer += atomic_line
        return res

    def check_lines(
        self, tokens: TokenWrapper, line_start: int, lines: str, lineno: int
    ) -> None:
        """Check given lines for potential messages.

        Check if lines have:
        - a final newline
        - no trailing white-space
        - less than a maximum number of characters
        """
        # we're first going to do a rough check whether any lines in this set
        # go over the line limit. If none of them do, then we don't need to
        # parse out the pylint options later on and can just assume that these
        # lines are clean

        # we'll also handle the line ending check here to avoid double-iteration
        # unless the line lengths are suspect

        max_chars = self.linter.config.max_line_length

        split_lines = self.specific_splitlines(lines)

        for offset, line in enumerate(split_lines):
            if not line.endswith("\n"):
                self.add_message("missing-final-newline", line=lineno + offset)
                continue
            # We don't test for trailing whitespaces in strings
            # See https://github.com/PyCQA/pylint/issues/6936
            # and https://github.com/PyCQA/pylint/issues/3822
            if tokens.type(line_start) != tokenize.STRING:
                self.check_trailing_whitespace_ending(line, lineno + offset)

        # This check is purposefully simple and doesn't rstrip since this is running
        # on every line you're checking it's advantageous to avoid doing a lot of work
        potential_line_length_warning = any(
            len(line) > max_chars for line in split_lines
        )

        # if there were no lines passing the max_chars config, we don't bother
        # running the full line check (as we've met an even more strict condition)
        if not potential_line_length_warning:
            return

        # Line length check may be deactivated through `pylint: disable` comment
        mobj = OPTION_PO.search(lines)
        checker_off = False
        if mobj:
            if not self.is_line_length_check_activated(mobj):
                checker_off = True
            # The 'pylint: disable whatever' should not be taken into account for line length count
            lines = self.remove_pylint_option_from_lines(mobj)

        # here we re-run specific_splitlines since we have filtered out pylint options above
        for offset, line in enumerate(self.specific_splitlines(lines)):
            self.check_line_length(line, lineno + offset, checker_off)

    def check_indent_level(self, string: str, expected: int, line_num: int) -> None:
        """Return the indent level of the string."""
        indent = self.linter.config.indent_string
        if indent == "\\t":  # \t is not interpreted in the configuration file
            indent = "\t"
        level = 0
        unit_size = len(indent)
        while string[:unit_size] == indent:
            string = string[unit_size:]
            level += 1
        suppl = ""
        while string and string[0] in " \t":
            suppl += string[0]
            string = string[1:]
        if level != expected or suppl:
            i_type = "spaces"
            if indent[0] == "\t":
                i_type = "tabs"
            self.add_message(
                "bad-indentation",
                line=line_num,
                args=(level * unit_size + len(suppl), i_type, expected * unit_size),
            )


def register(linter: PyLinter) -> None:
    linter.register_checker(FormatChecker(linter))
