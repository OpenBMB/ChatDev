# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import ast
import sys
import types
from collections.abc import Callable
from functools import partial
from typing import NamedTuple

from astroid.const import PY38_PLUS, Context

if sys.version_info >= (3, 8):
    # On Python 3.8, typed_ast was merged back into `ast`
    _ast_py3: types.ModuleType | None = ast
else:
    try:
        import typed_ast.ast3 as _ast_py3
    except ImportError:
        _ast_py3 = None


class FunctionType(NamedTuple):
    argtypes: list[ast.expr]
    returns: ast.expr


class ParserModule(NamedTuple):
    module: types.ModuleType
    unary_op_classes: dict[type[ast.unaryop], str]
    cmp_op_classes: dict[type[ast.cmpop], str]
    bool_op_classes: dict[type[ast.boolop], str]
    bin_op_classes: dict[type[ast.operator], str]
    context_classes: dict[type[ast.expr_context], Context]

    def parse(self, string: str, type_comments: bool = True) -> ast.Module:
        parse_func: Callable[[str], ast.Module]
        if self.module is _ast_py3:
            if PY38_PLUS:
                parse_func = partial(self.module.parse, type_comments=type_comments)
            else:
                parse_func = partial(
                    self.module.parse, feature_version=sys.version_info.minor
                )
        else:
            parse_func = self.module.parse
        return parse_func(string)


def parse_function_type_comment(type_comment: str) -> FunctionType | None:
    """Given a correct type comment, obtain a FunctionType object."""
    if _ast_py3 is None:
        return None

    func_type = _ast_py3.parse(type_comment, "<type_comment>", "func_type")  # type: ignore[attr-defined]
    return FunctionType(argtypes=func_type.argtypes, returns=func_type.returns)


def get_parser_module(type_comments: bool = True) -> ParserModule:
    parser_module = ast
    if type_comments and _ast_py3:
        parser_module = _ast_py3

    unary_op_classes = _unary_operators_from_module(parser_module)
    cmp_op_classes = _compare_operators_from_module(parser_module)
    bool_op_classes = _bool_operators_from_module(parser_module)
    bin_op_classes = _binary_operators_from_module(parser_module)
    context_classes = _contexts_from_module(parser_module)

    return ParserModule(
        parser_module,
        unary_op_classes,
        cmp_op_classes,
        bool_op_classes,
        bin_op_classes,
        context_classes,
    )


def _unary_operators_from_module(
    module: types.ModuleType,
) -> dict[type[ast.unaryop], str]:
    return {module.UAdd: "+", module.USub: "-", module.Not: "not", module.Invert: "~"}


def _binary_operators_from_module(
    module: types.ModuleType,
) -> dict[type[ast.operator], str]:
    binary_operators = {
        module.Add: "+",
        module.BitAnd: "&",
        module.BitOr: "|",
        module.BitXor: "^",
        module.Div: "/",
        module.FloorDiv: "//",
        module.MatMult: "@",
        module.Mod: "%",
        module.Mult: "*",
        module.Pow: "**",
        module.Sub: "-",
        module.LShift: "<<",
        module.RShift: ">>",
    }
    return binary_operators


def _bool_operators_from_module(
    module: types.ModuleType,
) -> dict[type[ast.boolop], str]:
    return {module.And: "and", module.Or: "or"}


def _compare_operators_from_module(
    module: types.ModuleType,
) -> dict[type[ast.cmpop], str]:
    return {
        module.Eq: "==",
        module.Gt: ">",
        module.GtE: ">=",
        module.In: "in",
        module.Is: "is",
        module.IsNot: "is not",
        module.Lt: "<",
        module.LtE: "<=",
        module.NotEq: "!=",
        module.NotIn: "not in",
    }


def _contexts_from_module(
    module: types.ModuleType,
) -> dict[type[ast.expr_context], Context]:
    return {
        module.Load: Context.Load,
        module.Store: Context.Store,
        module.Del: Context.Del,
        module.Param: Context.Store,
    }
