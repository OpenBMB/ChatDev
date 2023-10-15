# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import re
from re import Pattern

from pylint import constants
from pylint.typing import OptionDict, Options


class NamingStyle:
    """Class to register all accepted forms of a single naming style.

    It may seem counter-intuitive that single naming style has multiple "accepted"
    forms of regular expressions, but we need to special-case stuff like dunder
    names in method names.
    """

    ANY: Pattern[str] = re.compile(".*")
    CLASS_NAME_RGX: Pattern[str] = ANY
    MOD_NAME_RGX: Pattern[str] = ANY
    CONST_NAME_RGX: Pattern[str] = ANY
    COMP_VAR_RGX: Pattern[str] = ANY
    DEFAULT_NAME_RGX: Pattern[str] = ANY
    CLASS_ATTRIBUTE_RGX: Pattern[str] = ANY

    @classmethod
    def get_regex(cls, name_type: str) -> Pattern[str]:
        return {
            "module": cls.MOD_NAME_RGX,
            "const": cls.CONST_NAME_RGX,
            "class": cls.CLASS_NAME_RGX,
            "function": cls.DEFAULT_NAME_RGX,
            "method": cls.DEFAULT_NAME_RGX,
            "attr": cls.DEFAULT_NAME_RGX,
            "argument": cls.DEFAULT_NAME_RGX,
            "variable": cls.DEFAULT_NAME_RGX,
            "class_attribute": cls.CLASS_ATTRIBUTE_RGX,
            "class_const": cls.CONST_NAME_RGX,
            "inlinevar": cls.COMP_VAR_RGX,
        }[name_type]


class SnakeCaseStyle(NamingStyle):
    """Regex rules for snake_case naming style."""

    CLASS_NAME_RGX = re.compile(r"[^\W\dA-Z][^\WA-Z]+$")
    MOD_NAME_RGX = re.compile(r"[^\W\dA-Z][^\WA-Z]*$")
    CONST_NAME_RGX = re.compile(r"([^\W\dA-Z][^\WA-Z]*|__.*__)$")
    COMP_VAR_RGX = CLASS_NAME_RGX
    DEFAULT_NAME_RGX = re.compile(
        r"([^\W\dA-Z][^\WA-Z]{2,}|_[^\WA-Z]*|__[^\WA-Z\d_][^\WA-Z]+__)$"
    )
    CLASS_ATTRIBUTE_RGX = re.compile(r"([^\W\dA-Z][^\WA-Z]{2,}|__.*__)$")


class CamelCaseStyle(NamingStyle):
    """Regex rules for camelCase naming style."""

    CLASS_NAME_RGX = re.compile(r"[^\W\dA-Z][^\W_]+$")
    MOD_NAME_RGX = re.compile(r"[^\W\dA-Z][^\W_]*$")
    CONST_NAME_RGX = re.compile(r"([^\W\dA-Z][^\W_]*|__.*__)$")
    COMP_VAR_RGX = MOD_NAME_RGX
    DEFAULT_NAME_RGX = re.compile(r"([^\W\dA-Z][^\W_]{2,}|__[^\W\dA-Z_]\w+__)$")
    CLASS_ATTRIBUTE_RGX = re.compile(r"([^\W\dA-Z][^\W_]{2,}|__.*__)$")


class PascalCaseStyle(NamingStyle):
    """Regex rules for PascalCase naming style."""

    CLASS_NAME_RGX = re.compile(r"[^\W\da-z][^\W_]+$")
    MOD_NAME_RGX = CLASS_NAME_RGX
    CONST_NAME_RGX = re.compile(r"([^\W\da-z][^\W_]*|__.*__)$")
    COMP_VAR_RGX = CLASS_NAME_RGX
    DEFAULT_NAME_RGX = re.compile(r"([^\W\da-z][^\W_]{2,}|__[^\W\dA-Z_]\w+__)$")
    CLASS_ATTRIBUTE_RGX = re.compile(r"[^\W\da-z][^\W_]{2,}$")


class UpperCaseStyle(NamingStyle):
    """Regex rules for UPPER_CASE naming style."""

    CLASS_NAME_RGX = re.compile(r"[^\W\da-z][^\Wa-z]+$")
    MOD_NAME_RGX = CLASS_NAME_RGX
    CONST_NAME_RGX = re.compile(r"([^\W\da-z][^\Wa-z]*|__.*__)$")
    COMP_VAR_RGX = CLASS_NAME_RGX
    DEFAULT_NAME_RGX = re.compile(r"([^\W\da-z][^\Wa-z]{2,}|__[^\W\dA-Z_]\w+__)$")
    CLASS_ATTRIBUTE_RGX = re.compile(r"[^\W\da-z][^\Wa-z]{2,}$")


class AnyStyle(NamingStyle):
    pass


NAMING_STYLES = {
    "snake_case": SnakeCaseStyle,
    "camelCase": CamelCaseStyle,
    "PascalCase": PascalCaseStyle,
    "UPPER_CASE": UpperCaseStyle,
    "any": AnyStyle,
}

# Name types that have a style option
KNOWN_NAME_TYPES_WITH_STYLE = {
    "module",
    "const",
    "class",
    "function",
    "method",
    "attr",
    "argument",
    "variable",
    "class_attribute",
    "class_const",
    "inlinevar",
}


DEFAULT_NAMING_STYLES = {
    "module": "snake_case",
    "const": "UPPER_CASE",
    "class": "PascalCase",
    "function": "snake_case",
    "method": "snake_case",
    "attr": "snake_case",
    "argument": "snake_case",
    "variable": "snake_case",
    "class_attribute": "any",
    "class_const": "UPPER_CASE",
    "inlinevar": "any",
}


# Name types that have a 'rgx' option
KNOWN_NAME_TYPES = {
    *KNOWN_NAME_TYPES_WITH_STYLE,
    "typevar",
    "typealias",
}


def _create_naming_options() -> Options:
    name_options: list[tuple[str, OptionDict]] = []
    for name_type in sorted(KNOWN_NAME_TYPES):
        human_readable_name = constants.HUMAN_READABLE_TYPES[name_type]
        name_type_hyphened = name_type.replace("_", "-")

        help_msg = f"Regular expression matching correct {human_readable_name} names. "
        if name_type in KNOWN_NAME_TYPES_WITH_STYLE:
            help_msg += f"Overrides {name_type_hyphened}-naming-style. "
        help_msg += (
            f"If left empty, {human_readable_name} names will be checked "
            "with the set naming style."
        )

        # Add style option for names that support it
        if name_type in KNOWN_NAME_TYPES_WITH_STYLE:
            default_style = DEFAULT_NAMING_STYLES[name_type]
            name_options.append(
                (
                    f"{name_type_hyphened}-naming-style",
                    {
                        "default": default_style,
                        "type": "choice",
                        "choices": list(NAMING_STYLES.keys()),
                        "metavar": "<style>",
                        "help": f"Naming style matching correct {human_readable_name} names.",
                    },
                )
            )

        name_options.append(
            (
                f"{name_type_hyphened}-rgx",
                {
                    "default": None,
                    "type": "regexp",
                    "metavar": "<regexp>",
                    "help": help_msg,
                },
            )
        )
    return tuple(name_options)
