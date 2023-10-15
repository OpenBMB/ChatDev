# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Checks for magic values instead of literals."""

from __future__ import annotations

from re import match as regex_match
from typing import TYPE_CHECKING

from astroid import nodes

from pylint.checkers import BaseChecker, utils
from pylint.interfaces import HIGH

if TYPE_CHECKING:
    from pylint.lint import PyLinter


class MagicValueChecker(BaseChecker):
    """Checks for constants in comparisons."""

    name = "magic-value"
    msgs = {
        "R2004": (
            "Consider using a named constant or an enum instead of '%s'.",
            "magic-value-comparison",
            "Using named constants instead of magic values helps improve readability and maintainability of your"
            " code, try to avoid them in comparisons.",
        )
    }

    options = (
        (
            "valid-magic-values",
            {
                "default": (0, -1, 1, "", "__main__"),
                "type": "csv",
                "metavar": "<argument names>",
                "help": "List of valid magic values that `magic-value-compare` will not detect. "
                "Supports integers, floats, negative numbers, for empty string enter ``''``,"
                " for backslash values just use one backslash e.g \\n.",
            },
        ),
    )

    def __init__(self, linter: PyLinter) -> None:
        """Initialize checker instance."""
        super().__init__(linter=linter)
        self.valid_magic_vals: tuple[float | str, ...] = ()

    def open(self) -> None:
        # Extra manipulation is needed in case of using external configuration like an rcfile
        if self._magic_vals_ext_configured():
            self.valid_magic_vals = tuple(
                self._parse_rcfile_magic_numbers(value)
                for value in self.linter.config.valid_magic_values
            )
        else:
            self.valid_magic_vals = self.linter.config.valid_magic_values

    def _magic_vals_ext_configured(self) -> bool:
        return not isinstance(self.linter.config.valid_magic_values, tuple)

    def _check_constants_comparison(self, node: nodes.Compare) -> None:
        """
        Magic values in any side of the comparison should be avoided,
        Detects comparisons that `comparison-of-constants` core checker cannot detect.
        """
        const_operands = []
        LEFT_OPERAND = 0
        RIGHT_OPERAND = 1

        left_operand = node.left
        const_operands.append(isinstance(left_operand, nodes.Const))

        right_operand = node.ops[0][1]
        const_operands.append(isinstance(right_operand, nodes.Const))

        if all(const_operands):
            # `comparison-of-constants` avoided
            return

        operand_value = None
        if const_operands[LEFT_OPERAND] and self._is_magic_value(left_operand):
            operand_value = left_operand.value
        elif const_operands[RIGHT_OPERAND] and self._is_magic_value(right_operand):
            operand_value = right_operand.value
        if operand_value is not None:
            self.add_message(
                "magic-value-comparison",
                node=node,
                args=(operand_value),
                confidence=HIGH,
            )

    def _is_magic_value(self, node: nodes.Const) -> bool:
        return (not utils.is_singleton_const(node)) and (
            node.value not in (self.valid_magic_vals)
        )

    @staticmethod
    def _parse_rcfile_magic_numbers(parsed_val: str) -> float | str:
        parsed_val = parsed_val.encode().decode("unicode_escape")

        if parsed_val.startswith("'") and parsed_val.endswith("'"):
            return parsed_val[1:-1]

        is_number = regex_match(r"[-+]?\d+(\.0*)?$", parsed_val)
        return float(parsed_val) if is_number else parsed_val

    @utils.only_required_for_messages("magic-comparison")
    def visit_compare(self, node: nodes.Compare) -> None:
        self._check_constants_comparison(node)


def register(linter: PyLinter) -> None:
    linter.register_checker(MagicValueChecker(linter))
