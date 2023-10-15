# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Checker for use of Python logging."""

from __future__ import annotations

import string
import sys
from typing import TYPE_CHECKING

import astroid
from astroid import bases, nodes
from astroid.typing import InferenceResult

from pylint import checkers
from pylint.checkers import utils
from pylint.checkers.utils import infer_all
from pylint.typing import MessageDefinitionTuple

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal

if TYPE_CHECKING:
    from pylint.lint import PyLinter

MSGS: dict[
    str, MessageDefinitionTuple
] = {  # pylint: disable=consider-using-namedtuple-or-dataclass
    "W1201": (
        "Use %s formatting in logging functions",
        "logging-not-lazy",
        "Used when a logging statement has a call form of "
        '"logging.<logging method>(format_string % (format_args...))". '
        "Use another type of string formatting instead. "
        "You can use % formatting but leave interpolation to "
        "the logging function by passing the parameters as arguments. "
        "If logging-fstring-interpolation is disabled then "
        "you can use fstring formatting. "
        "If logging-format-interpolation is disabled then "
        "you can use str.format.",
    ),
    "W1202": (
        "Use %s formatting in logging functions",
        "logging-format-interpolation",
        "Used when a logging statement has a call form of "
        '"logging.<logging method>(format_string.format(format_args...))". '
        "Use another type of string formatting instead. "
        "You can use % formatting but leave interpolation to "
        "the logging function by passing the parameters as arguments. "
        "If logging-fstring-interpolation is disabled then "
        "you can use fstring formatting. "
        "If logging-not-lazy is disabled then "
        "you can use % formatting as normal.",
    ),
    "W1203": (
        "Use %s formatting in logging functions",
        "logging-fstring-interpolation",
        "Used when a logging statement has a call form of "
        '"logging.<logging method>(f"...")".'
        "Use another type of string formatting instead. "
        "You can use % formatting but leave interpolation to "
        "the logging function by passing the parameters as arguments. "
        "If logging-format-interpolation is disabled then "
        "you can use str.format. "
        "If logging-not-lazy is disabled then "
        "you can use % formatting as normal.",
    ),
    "E1200": (
        "Unsupported logging format character %r (%#02x) at index %d",
        "logging-unsupported-format",
        "Used when an unsupported format character is used in a logging "
        "statement format string.",
    ),
    "E1201": (
        "Logging format string ends in middle of conversion specifier",
        "logging-format-truncated",
        "Used when a logging statement format string terminates before "
        "the end of a conversion specifier.",
    ),
    "E1205": (
        "Too many arguments for logging format string",
        "logging-too-many-args",
        "Used when a logging format string is given too many arguments.",
    ),
    "E1206": (
        "Not enough arguments for logging format string",
        "logging-too-few-args",
        "Used when a logging format string is given too few arguments.",
    ),
}


CHECKED_CONVENIENCE_FUNCTIONS = {
    "critical",
    "debug",
    "error",
    "exception",
    "fatal",
    "info",
    "warn",
    "warning",
}

MOST_COMMON_FORMATTING = frozenset(["%s", "%d", "%f", "%r"])


def is_method_call(
    func: bases.BoundMethod, types: tuple[str, ...] = (), methods: tuple[str, ...] = ()
) -> bool:
    """Determines if a BoundMethod node represents a method call.

    Args:
      func: The BoundMethod AST node to check.
      types: Optional sequence of caller type names to restrict check.
      methods: Optional sequence of method names to restrict check.

    Returns:
      true if the node represents a method call for the given type and
      method names, False otherwise.
    """
    return (
        isinstance(func, astroid.BoundMethod)
        and isinstance(func.bound, astroid.Instance)
        and (func.bound.name in types if types else True)
        and (func.name in methods if methods else True)
    )


class LoggingChecker(checkers.BaseChecker):
    """Checks use of the logging module."""

    name = "logging"
    msgs = MSGS

    options = (
        (
            "logging-modules",
            {
                "default": ("logging",),
                "type": "csv",
                "metavar": "<comma separated list>",
                "help": "Logging modules to check that the string format "
                "arguments are in logging function parameter format.",
            },
        ),
        (
            "logging-format-style",
            {
                "default": "old",
                "type": "choice",
                "metavar": "<old (%) or new ({)>",
                "choices": ["old", "new"],
                "help": "The type of string formatting that logging methods do. "
                "`old` means using % formatting, `new` is for `{}` formatting.",
            },
        ),
    )

    def visit_module(self, _: nodes.Module) -> None:
        """Clears any state left in this checker from last module checked."""
        # The code being checked can just as easily "import logging as foo",
        # so it is necessary to process the imports and store in this field
        # what name the logging module is actually given.
        self._logging_names: set[str] = set()
        logging_mods = self.linter.config.logging_modules

        self._format_style = self.linter.config.logging_format_style

        self._logging_modules = set(logging_mods)
        self._from_imports = {}
        for logging_mod in logging_mods:
            parts = logging_mod.rsplit(".", 1)
            if len(parts) > 1:
                self._from_imports[parts[0]] = parts[1]

    def visit_importfrom(self, node: nodes.ImportFrom) -> None:
        """Checks to see if a module uses a non-Python logging module."""
        try:
            logging_name = self._from_imports[node.modname]
            for module, as_name in node.names:
                if module == logging_name:
                    self._logging_names.add(as_name or module)
        except KeyError:
            pass

    def visit_import(self, node: nodes.Import) -> None:
        """Checks to see if this module uses Python's built-in logging."""
        for module, as_name in node.names:
            if module in self._logging_modules:
                self._logging_names.add(as_name or module)

    def visit_call(self, node: nodes.Call) -> None:
        """Checks calls to logging methods."""

        def is_logging_name() -> bool:
            return (
                isinstance(node.func, nodes.Attribute)
                and isinstance(node.func.expr, nodes.Name)
                and node.func.expr.name in self._logging_names
            )

        def is_logger_class() -> tuple[bool, str | None]:
            for inferred in infer_all(node.func):
                if isinstance(inferred, astroid.BoundMethod):
                    parent = inferred._proxied.parent
                    if isinstance(parent, nodes.ClassDef) and (
                        parent.qname() == "logging.Logger"
                        or any(
                            ancestor.qname() == "logging.Logger"
                            for ancestor in parent.ancestors()
                        )
                    ):
                        return True, inferred._proxied.name
            return False, None

        if is_logging_name():
            name = node.func.attrname
        else:
            result, name = is_logger_class()
            if not result:
                return
        self._check_log_method(node, name)

    def _check_log_method(self, node: nodes.Call, name: str) -> None:
        """Checks calls to logging.log(level, format, *format_args)."""
        if name == "log":
            if node.starargs or node.kwargs or len(node.args) < 2:
                # Either a malformed call, star args, or double-star args. Beyond
                # the scope of this checker.
                return
            format_pos: Literal[0, 1] = 1
        elif name in CHECKED_CONVENIENCE_FUNCTIONS:
            if node.starargs or node.kwargs or not node.args:
                # Either no args, star args, or double-star args. Beyond the
                # scope of this checker.
                return
            format_pos = 0
        else:
            return

        format_arg = node.args[format_pos]
        if isinstance(format_arg, nodes.BinOp):
            binop = format_arg
            emit = binop.op == "%"
            if binop.op == "+":
                total_number_of_strings = sum(
                    1
                    for operand in (binop.left, binop.right)
                    if self._is_operand_literal_str(utils.safe_infer(operand))
                )
                emit = total_number_of_strings > 0
            if emit:
                self.add_message(
                    "logging-not-lazy",
                    node=node,
                    args=(self._helper_string(node),),
                )
        elif isinstance(format_arg, nodes.Call):
            self._check_call_func(format_arg)
        elif isinstance(format_arg, nodes.Const):
            self._check_format_string(node, format_pos)
        elif isinstance(format_arg, nodes.JoinedStr):
            if str_formatting_in_f_string(format_arg):
                return
            self.add_message(
                "logging-fstring-interpolation",
                node=node,
                args=(self._helper_string(node),),
            )

    def _helper_string(self, node: nodes.Call) -> str:
        """Create a string that lists the valid types of formatting for this node."""
        valid_types = ["lazy %"]

        if not self.linter.is_message_enabled(
            "logging-fstring-formatting", node.fromlineno
        ):
            valid_types.append("fstring")
        if not self.linter.is_message_enabled(
            "logging-format-interpolation", node.fromlineno
        ):
            valid_types.append(".format()")
        if not self.linter.is_message_enabled("logging-not-lazy", node.fromlineno):
            valid_types.append("%")

        return " or ".join(valid_types)

    @staticmethod
    def _is_operand_literal_str(operand: InferenceResult | None) -> bool:
        """Return True if the operand in argument is a literal string."""
        return isinstance(operand, nodes.Const) and operand.name == "str"

    def _check_call_func(self, node: nodes.Call) -> None:
        """Checks that function call is not format_string.format()."""
        func = utils.safe_infer(node.func)
        types = ("str", "unicode")
        methods = ("format",)
        if (
            isinstance(func, astroid.BoundMethod)
            and is_method_call(func, types, methods)
            and not is_complex_format_str(func.bound)
        ):
            self.add_message(
                "logging-format-interpolation",
                node=node,
                args=(self._helper_string(node),),
            )

    def _check_format_string(self, node: nodes.Call, format_arg: Literal[0, 1]) -> None:
        """Checks that format string tokens match the supplied arguments.

        Args:
          node: AST node to be checked.
          format_arg: Index of the format string in the node arguments.
        """
        num_args = _count_supplied_tokens(node.args[format_arg + 1 :])
        if not num_args:
            # If no args were supplied the string is not interpolated and can contain
            # formatting characters - it's used verbatim. Don't check any further.
            return

        format_string = node.args[format_arg].value
        required_num_args = 0
        if isinstance(format_string, bytes):
            format_string = format_string.decode()
        if isinstance(format_string, str):
            try:
                if self._format_style == "old":
                    keyword_args, required_num_args, _, _ = utils.parse_format_string(
                        format_string
                    )
                    if keyword_args:
                        # Keyword checking on logging strings is complicated by
                        # special keywords - out of scope.
                        return
                elif self._format_style == "new":
                    (
                        keyword_arguments,
                        implicit_pos_args,
                        explicit_pos_args,
                    ) = utils.parse_format_method_string(format_string)

                    keyword_args_cnt = len(
                        {k for k, _ in keyword_arguments if not isinstance(k, int)}
                    )
                    required_num_args = (
                        keyword_args_cnt + implicit_pos_args + explicit_pos_args
                    )
            except utils.UnsupportedFormatCharacter as ex:
                char = format_string[ex.index]
                self.add_message(
                    "logging-unsupported-format",
                    node=node,
                    args=(char, ord(char), ex.index),
                )
                return
            except utils.IncompleteFormatString:
                self.add_message("logging-format-truncated", node=node)
                return
        if num_args > required_num_args:
            self.add_message("logging-too-many-args", node=node)
        elif num_args < required_num_args:
            self.add_message("logging-too-few-args", node=node)


def is_complex_format_str(node: nodes.NodeNG) -> bool:
    """Return whether the node represents a string with complex formatting specs."""
    inferred = utils.safe_infer(node)
    if inferred is None or not (
        isinstance(inferred, nodes.Const) and isinstance(inferred.value, str)
    ):
        return True
    try:
        parsed = list(string.Formatter().parse(inferred.value))
    except ValueError:
        # This format string is invalid
        return False
    return any(format_spec for (_, _, format_spec, _) in parsed)


def _count_supplied_tokens(args: list[nodes.NodeNG]) -> int:
    """Counts the number of tokens in an args list.

    The Python log functions allow for special keyword arguments: func,
    exc_info and extra. To handle these cases correctly, we only count
    arguments that aren't keywords.

    Args:
      args: AST nodes that are arguments for a log format string.

    Returns:
      Number of AST nodes that aren't keywords.
    """
    return sum(1 for arg in args if not isinstance(arg, nodes.Keyword))


def str_formatting_in_f_string(node: nodes.JoinedStr) -> bool:
    """Determine whether the node represents an f-string with string formatting.

    For example: `f'Hello %s'`
    """
    # Check "%" presence first for performance.
    return any(
        "%" in val.value and any(x in val.value for x in MOST_COMMON_FORMATTING)
        for val in node.values
        if isinstance(val, nodes.Const)
    )


def register(linter: PyLinter) -> None:
    linter.register_checker(LoggingChecker(linter))
