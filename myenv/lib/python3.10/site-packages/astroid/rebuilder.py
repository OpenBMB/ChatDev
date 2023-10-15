# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""This module contains utilities for rebuilding an _ast tree in
order to get a single Astroid representation.
"""

from __future__ import annotations

import ast
import sys
import token
from collections.abc import Callable, Generator
from io import StringIO
from tokenize import TokenInfo, generate_tokens
from typing import TYPE_CHECKING, TypeVar, Union, cast, overload

from astroid import nodes
from astroid._ast import ParserModule, get_parser_module, parse_function_type_comment
from astroid.const import IS_PYPY, PY38, PY38_PLUS, PY39_PLUS, Context
from astroid.manager import AstroidManager
from astroid.nodes import NodeNG
from astroid.nodes.utils import Position
from astroid.typing import SuccessfulInferenceResult

if sys.version_info >= (3, 8):
    from typing import Final
else:
    from typing_extensions import Final


REDIRECT: Final[dict[str, str]] = {
    "arguments": "Arguments",
    "comprehension": "Comprehension",
    "ListCompFor": "Comprehension",
    "GenExprFor": "Comprehension",
    "excepthandler": "ExceptHandler",
    "keyword": "Keyword",
    "match_case": "MatchCase",
}


T_Doc = TypeVar(
    "T_Doc",
    "ast.Module",
    "ast.ClassDef",
    Union["ast.FunctionDef", "ast.AsyncFunctionDef"],
)
_FunctionT = TypeVar("_FunctionT", nodes.FunctionDef, nodes.AsyncFunctionDef)
_ForT = TypeVar("_ForT", nodes.For, nodes.AsyncFor)
_WithT = TypeVar("_WithT", nodes.With, nodes.AsyncWith)
NodesWithDocsType = Union[nodes.Module, nodes.ClassDef, nodes.FunctionDef]


# noinspection PyMethodMayBeStatic
class TreeRebuilder:
    """Rebuilds the _ast tree to become an Astroid tree."""

    def __init__(
        self,
        manager: AstroidManager,
        parser_module: ParserModule | None = None,
        data: str | None = None,
    ) -> None:
        self._manager = manager
        self._data = data.split("\n") if data else None
        self._global_names: list[dict[str, list[nodes.Global]]] = []
        self._import_from_nodes: list[nodes.ImportFrom] = []
        self._delayed_assattr: list[nodes.AssignAttr] = []
        self._visit_meths: dict[type[ast.AST], Callable[[ast.AST, NodeNG], NodeNG]] = {}

        if parser_module is None:
            self._parser_module = get_parser_module()
        else:
            self._parser_module = parser_module
        self._module = self._parser_module.module

    def _get_doc(self, node: T_Doc) -> tuple[T_Doc, ast.Constant | ast.Str | None]:
        """Return the doc ast node."""
        try:
            if node.body and isinstance(node.body[0], self._module.Expr):
                first_value = node.body[0].value
                if isinstance(first_value, self._module.Str) or (
                    PY38_PLUS
                    and isinstance(first_value, self._module.Constant)
                    and isinstance(first_value.value, str)
                ):
                    doc_ast_node = first_value
                    node.body = node.body[1:]
                    # The ast parser of python < 3.8 sets col_offset of multi-line strings to -1
                    # as it is unable to determine the value correctly. We reset this to None.
                    if doc_ast_node.col_offset == -1:
                        doc_ast_node.col_offset = None
                    return node, doc_ast_node
        except IndexError:
            pass  # ast built from scratch
        return node, None

    def _get_context(
        self,
        node: (
            ast.Attribute
            | ast.List
            | ast.Name
            | ast.Subscript
            | ast.Starred
            | ast.Tuple
        ),
    ) -> Context:
        return self._parser_module.context_classes.get(type(node.ctx), Context.Load)

    def _get_position_info(
        self,
        node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
        parent: nodes.ClassDef | nodes.FunctionDef | nodes.AsyncFunctionDef,
    ) -> Position | None:
        """Return position information for ClassDef and FunctionDef nodes.

        In contrast to AST positions, these only include the actual keyword(s)
        and the class / function name.

        >>> @decorator
        >>> async def some_func(var: int) -> None:
        >>> ^^^^^^^^^^^^^^^^^^^
        """
        if not self._data:
            return None
        end_lineno: int | None = getattr(node, "end_lineno", None)
        if node.body:
            end_lineno = node.body[0].lineno
        # pylint: disable-next=unsubscriptable-object
        data = "\n".join(self._data[node.lineno - 1 : end_lineno])

        start_token: TokenInfo | None = None
        keyword_tokens: tuple[int, ...] = (token.NAME,)
        if isinstance(parent, nodes.AsyncFunctionDef):
            search_token = "async"
        elif isinstance(parent, nodes.FunctionDef):
            search_token = "def"
        else:
            search_token = "class"

        for t in generate_tokens(StringIO(data).readline):
            if (
                start_token is not None
                and t.type == token.NAME
                and t.string == node.name
            ):
                break
            if t.type in keyword_tokens:
                if t.string == search_token:
                    start_token = t
                    continue
                if t.string in {"def"}:
                    continue
            start_token = None
        else:
            return None

        return Position(
            lineno=node.lineno + start_token.start[0] - 1,
            col_offset=start_token.start[1],
            end_lineno=node.lineno + t.end[0] - 1,
            end_col_offset=t.end[1],
        )

    def _fix_doc_node_position(self, node: NodesWithDocsType) -> None:
        """Fix start and end position of doc nodes for Python < 3.8."""
        if not self._data or not node.doc_node or node.lineno is None:
            return
        if PY38_PLUS:
            return

        lineno = node.lineno or 1  # lineno of modules is 0
        end_range: int | None = node.doc_node.lineno
        if IS_PYPY and not PY39_PLUS:
            end_range = None
        # pylint: disable-next=unsubscriptable-object
        data = "\n".join(self._data[lineno - 1 : end_range])

        found_start, found_end = False, False
        open_brackets = 0
        skip_token: set[int] = {token.NEWLINE, token.INDENT, token.NL, token.COMMENT}

        if isinstance(node, nodes.Module):
            found_end = True

        for t in generate_tokens(StringIO(data).readline):
            if found_end is False:
                if (
                    found_start is False
                    and t.type == token.NAME
                    and t.string in {"def", "class"}
                ):
                    found_start = True
                elif found_start is True and t.type == token.OP:
                    if t.exact_type == token.COLON and open_brackets == 0:
                        found_end = True
                    elif t.exact_type == token.LPAR:
                        open_brackets += 1
                    elif t.exact_type == token.RPAR:
                        open_brackets -= 1
                continue
            if t.type in skip_token:
                continue
            if t.type == token.STRING:
                break
            return
        else:
            return

        node.doc_node.lineno = lineno + t.start[0] - 1
        node.doc_node.col_offset = t.start[1]
        node.doc_node.end_lineno = lineno + t.end[0] - 1
        node.doc_node.end_col_offset = t.end[1]

    def _reset_end_lineno(self, newnode: nodes.NodeNG) -> None:
        """Reset end_lineno and end_col_offset attributes for PyPy 3.8.

        For some nodes, these are either set to -1 or only partially assigned.
        To keep consistency across astroid and pylint, reset all.

        This has been fixed in PyPy 3.9.
        For reference, an (incomplete) list of nodes with issues:
            - ClassDef          - For
            - FunctionDef       - While
            - Call              - If
            - Decorators        - TryExcept
            - With              - TryFinally
            - Assign
        """
        newnode.end_lineno = None
        newnode.end_col_offset = None
        for child_node in newnode.get_children():
            self._reset_end_lineno(child_node)

    def visit_module(
        self, node: ast.Module, modname: str, modpath: str, package: bool
    ) -> nodes.Module:
        """Visit a Module node by returning a fresh instance of it.

        Note: Method not called by 'visit'
        """
        node, doc_ast_node = self._get_doc(node)
        newnode = nodes.Module(
            name=modname,
            file=modpath,
            path=[modpath],
            package=package,
            parent=None,
        )
        newnode.postinit(
            [self.visit(child, newnode) for child in node.body],
            doc_node=self.visit(doc_ast_node, newnode),
        )
        self._fix_doc_node_position(newnode)
        if IS_PYPY and PY38:
            self._reset_end_lineno(newnode)
        return newnode

    if TYPE_CHECKING:  # noqa: C901

        @overload
        def visit(self, node: ast.arg, parent: NodeNG) -> nodes.AssignName:
            ...

        @overload
        def visit(self, node: ast.arguments, parent: NodeNG) -> nodes.Arguments:
            ...

        @overload
        def visit(self, node: ast.Assert, parent: NodeNG) -> nodes.Assert:
            ...

        @overload
        def visit(
            self, node: ast.AsyncFunctionDef, parent: NodeNG
        ) -> nodes.AsyncFunctionDef:
            ...

        @overload
        def visit(self, node: ast.AsyncFor, parent: NodeNG) -> nodes.AsyncFor:
            ...

        @overload
        def visit(self, node: ast.Await, parent: NodeNG) -> nodes.Await:
            ...

        @overload
        def visit(self, node: ast.AsyncWith, parent: NodeNG) -> nodes.AsyncWith:
            ...

        @overload
        def visit(self, node: ast.Assign, parent: NodeNG) -> nodes.Assign:
            ...

        @overload
        def visit(self, node: ast.AnnAssign, parent: NodeNG) -> nodes.AnnAssign:
            ...

        @overload
        def visit(self, node: ast.AugAssign, parent: NodeNG) -> nodes.AugAssign:
            ...

        @overload
        def visit(self, node: ast.BinOp, parent: NodeNG) -> nodes.BinOp:
            ...

        @overload
        def visit(self, node: ast.BoolOp, parent: NodeNG) -> nodes.BoolOp:
            ...

        @overload
        def visit(self, node: ast.Break, parent: NodeNG) -> nodes.Break:
            ...

        @overload
        def visit(self, node: ast.Call, parent: NodeNG) -> nodes.Call:
            ...

        @overload
        def visit(self, node: ast.ClassDef, parent: NodeNG) -> nodes.ClassDef:
            ...

        @overload
        def visit(self, node: ast.Continue, parent: NodeNG) -> nodes.Continue:
            ...

        @overload
        def visit(self, node: ast.Compare, parent: NodeNG) -> nodes.Compare:
            ...

        @overload
        def visit(self, node: ast.comprehension, parent: NodeNG) -> nodes.Comprehension:
            ...

        @overload
        def visit(self, node: ast.Delete, parent: NodeNG) -> nodes.Delete:
            ...

        @overload
        def visit(self, node: ast.Dict, parent: NodeNG) -> nodes.Dict:
            ...

        @overload
        def visit(self, node: ast.DictComp, parent: NodeNG) -> nodes.DictComp:
            ...

        @overload
        def visit(self, node: ast.Expr, parent: NodeNG) -> nodes.Expr:
            ...

        @overload
        def visit(self, node: ast.ExceptHandler, parent: NodeNG) -> nodes.ExceptHandler:
            ...

        @overload
        def visit(self, node: ast.For, parent: NodeNG) -> nodes.For:
            ...

        @overload
        def visit(self, node: ast.ImportFrom, parent: NodeNG) -> nodes.ImportFrom:
            ...

        @overload
        def visit(self, node: ast.FunctionDef, parent: NodeNG) -> nodes.FunctionDef:
            ...

        @overload
        def visit(self, node: ast.GeneratorExp, parent: NodeNG) -> nodes.GeneratorExp:
            ...

        @overload
        def visit(self, node: ast.Attribute, parent: NodeNG) -> nodes.Attribute:
            ...

        @overload
        def visit(self, node: ast.Global, parent: NodeNG) -> nodes.Global:
            ...

        @overload
        def visit(self, node: ast.If, parent: NodeNG) -> nodes.If:
            ...

        @overload
        def visit(self, node: ast.IfExp, parent: NodeNG) -> nodes.IfExp:
            ...

        @overload
        def visit(self, node: ast.Import, parent: NodeNG) -> nodes.Import:
            ...

        @overload
        def visit(self, node: ast.JoinedStr, parent: NodeNG) -> nodes.JoinedStr:
            ...

        @overload
        def visit(
            self, node: ast.FormattedValue, parent: NodeNG
        ) -> nodes.FormattedValue:
            ...

        if sys.version_info >= (3, 8):

            @overload
            def visit(self, node: ast.NamedExpr, parent: NodeNG) -> nodes.NamedExpr:
                ...

        if sys.version_info < (3, 9):
            # Not used in Python 3.9+
            @overload
            def visit(self, node: ast.ExtSlice, parent: nodes.Subscript) -> nodes.Tuple:
                ...

            @overload
            def visit(self, node: ast.Index, parent: nodes.Subscript) -> NodeNG:
                ...

        @overload
        def visit(self, node: ast.keyword, parent: NodeNG) -> nodes.Keyword:
            ...

        @overload
        def visit(self, node: ast.Lambda, parent: NodeNG) -> nodes.Lambda:
            ...

        @overload
        def visit(self, node: ast.List, parent: NodeNG) -> nodes.List:
            ...

        @overload
        def visit(self, node: ast.ListComp, parent: NodeNG) -> nodes.ListComp:
            ...

        @overload
        def visit(
            self, node: ast.Name, parent: NodeNG
        ) -> nodes.Name | nodes.Const | nodes.AssignName | nodes.DelName:
            ...

        @overload
        def visit(self, node: ast.Nonlocal, parent: NodeNG) -> nodes.Nonlocal:
            ...

        if sys.version_info < (3, 8):
            # Not used in Python 3.8+
            @overload
            def visit(self, node: ast.Ellipsis, parent: NodeNG) -> nodes.Const:
                ...

            @overload
            def visit(self, node: ast.NameConstant, parent: NodeNG) -> nodes.Const:
                ...

            @overload
            def visit(self, node: ast.Str, parent: NodeNG) -> nodes.Const:
                ...

            @overload
            def visit(self, node: ast.Bytes, parent: NodeNG) -> nodes.Const:
                ...

            @overload
            def visit(self, node: ast.Num, parent: NodeNG) -> nodes.Const:
                ...

        @overload
        def visit(self, node: ast.Constant, parent: NodeNG) -> nodes.Const:
            ...

        @overload
        def visit(self, node: ast.Pass, parent: NodeNG) -> nodes.Pass:
            ...

        @overload
        def visit(self, node: ast.Raise, parent: NodeNG) -> nodes.Raise:
            ...

        @overload
        def visit(self, node: ast.Return, parent: NodeNG) -> nodes.Return:
            ...

        @overload
        def visit(self, node: ast.Set, parent: NodeNG) -> nodes.Set:
            ...

        @overload
        def visit(self, node: ast.SetComp, parent: NodeNG) -> nodes.SetComp:
            ...

        @overload
        def visit(self, node: ast.Slice, parent: nodes.Subscript) -> nodes.Slice:
            ...

        @overload
        def visit(self, node: ast.Subscript, parent: NodeNG) -> nodes.Subscript:
            ...

        @overload
        def visit(self, node: ast.Starred, parent: NodeNG) -> nodes.Starred:
            ...

        @overload
        def visit(
            self, node: ast.Try, parent: NodeNG
        ) -> nodes.TryExcept | nodes.TryFinally:
            ...

        @overload
        def visit(self, node: ast.Tuple, parent: NodeNG) -> nodes.Tuple:
            ...

        @overload
        def visit(self, node: ast.UnaryOp, parent: NodeNG) -> nodes.UnaryOp:
            ...

        @overload
        def visit(self, node: ast.While, parent: NodeNG) -> nodes.While:
            ...

        @overload
        def visit(self, node: ast.With, parent: NodeNG) -> nodes.With:
            ...

        @overload
        def visit(self, node: ast.Yield, parent: NodeNG) -> nodes.Yield:
            ...

        @overload
        def visit(self, node: ast.YieldFrom, parent: NodeNG) -> nodes.YieldFrom:
            ...

        if sys.version_info >= (3, 10):

            @overload
            def visit(self, node: ast.Match, parent: NodeNG) -> nodes.Match:
                ...

            @overload
            def visit(self, node: ast.match_case, parent: NodeNG) -> nodes.MatchCase:
                ...

            @overload
            def visit(self, node: ast.MatchValue, parent: NodeNG) -> nodes.MatchValue:
                ...

            @overload
            def visit(
                self, node: ast.MatchSingleton, parent: NodeNG
            ) -> nodes.MatchSingleton:
                ...

            @overload
            def visit(
                self, node: ast.MatchSequence, parent: NodeNG
            ) -> nodes.MatchSequence:
                ...

            @overload
            def visit(
                self, node: ast.MatchMapping, parent: NodeNG
            ) -> nodes.MatchMapping:
                ...

            @overload
            def visit(self, node: ast.MatchClass, parent: NodeNG) -> nodes.MatchClass:
                ...

            @overload
            def visit(self, node: ast.MatchStar, parent: NodeNG) -> nodes.MatchStar:
                ...

            @overload
            def visit(self, node: ast.MatchAs, parent: NodeNG) -> nodes.MatchAs:
                ...

            @overload
            def visit(self, node: ast.MatchOr, parent: NodeNG) -> nodes.MatchOr:
                ...

            @overload
            def visit(self, node: ast.pattern, parent: NodeNG) -> nodes.Pattern:
                ...

        @overload
        def visit(self, node: ast.AST, parent: NodeNG) -> NodeNG:
            ...

        @overload
        def visit(self, node: None, parent: NodeNG) -> None:
            ...

    def visit(self, node: ast.AST | None, parent: NodeNG) -> NodeNG | None:
        if node is None:
            return None
        cls = node.__class__
        if cls in self._visit_meths:
            visit_method = self._visit_meths[cls]
        else:
            cls_name = cls.__name__
            visit_name = "visit_" + REDIRECT.get(cls_name, cls_name).lower()
            visit_method = getattr(self, visit_name)
            self._visit_meths[cls] = visit_method
        return visit_method(node, parent)

    def _save_assignment(self, node: nodes.AssignName | nodes.DelName) -> None:
        """Save assignment situation since node.parent is not available yet."""
        if self._global_names and node.name in self._global_names[-1]:
            node.root().set_local(node.name, node)
        else:
            assert node.parent
            assert node.name
            node.parent.set_local(node.name, node)

    def visit_arg(self, node: ast.arg, parent: NodeNG) -> nodes.AssignName:
        """Visit an arg node by returning a fresh AssName instance."""
        return self.visit_assignname(node, parent, node.arg)

    def visit_arguments(self, node: ast.arguments, parent: NodeNG) -> nodes.Arguments:
        """Visit an Arguments node by returning a fresh instance of it."""
        vararg: str | None = None
        kwarg: str | None = None
        newnode = nodes.Arguments(
            node.vararg.arg if node.vararg else None,
            node.kwarg.arg if node.kwarg else None,
            parent,
        )
        args = [self.visit(child, newnode) for child in node.args]
        defaults = [self.visit(child, newnode) for child in node.defaults]
        varargannotation: NodeNG | None = None
        kwargannotation: NodeNG | None = None
        posonlyargs: list[nodes.AssignName] = []
        if node.vararg:
            vararg = node.vararg.arg
            varargannotation = self.visit(node.vararg.annotation, newnode)
        if node.kwarg:
            kwarg = node.kwarg.arg
            kwargannotation = self.visit(node.kwarg.annotation, newnode)

        if PY38:
            # In Python 3.8 'end_lineno' and 'end_col_offset'
            # for 'kwonlyargs' don't include the annotation.
            for arg in node.kwonlyargs:
                if arg.annotation is not None:
                    arg.end_lineno = arg.annotation.end_lineno
                    arg.end_col_offset = arg.annotation.end_col_offset

        kwonlyargs = [self.visit(child, newnode) for child in node.kwonlyargs]
        kw_defaults = [self.visit(child, newnode) for child in node.kw_defaults]
        annotations = [self.visit(arg.annotation, newnode) for arg in node.args]
        kwonlyargs_annotations = [
            self.visit(arg.annotation, newnode) for arg in node.kwonlyargs
        ]

        posonlyargs_annotations: list[NodeNG | None] = []
        if PY38_PLUS:
            posonlyargs = [self.visit(child, newnode) for child in node.posonlyargs]
            posonlyargs_annotations = [
                self.visit(arg.annotation, newnode) for arg in node.posonlyargs
            ]
        type_comment_args = [
            self.check_type_comment(child, parent=newnode) for child in node.args
        ]
        type_comment_kwonlyargs = [
            self.check_type_comment(child, parent=newnode) for child in node.kwonlyargs
        ]
        type_comment_posonlyargs: list[NodeNG | None] = []
        if PY38_PLUS:
            type_comment_posonlyargs = [
                self.check_type_comment(child, parent=newnode)
                for child in node.posonlyargs
            ]

        newnode.postinit(
            args=args,
            defaults=defaults,
            kwonlyargs=kwonlyargs,
            posonlyargs=posonlyargs,
            kw_defaults=kw_defaults,
            annotations=annotations,
            kwonlyargs_annotations=kwonlyargs_annotations,
            posonlyargs_annotations=posonlyargs_annotations,
            varargannotation=varargannotation,
            kwargannotation=kwargannotation,
            type_comment_args=type_comment_args,
            type_comment_kwonlyargs=type_comment_kwonlyargs,
            type_comment_posonlyargs=type_comment_posonlyargs,
        )
        # save argument names in locals:
        assert newnode.parent
        if vararg:
            newnode.parent.set_local(vararg, newnode)
        if kwarg:
            newnode.parent.set_local(kwarg, newnode)
        return newnode

    def visit_assert(self, node: ast.Assert, parent: NodeNG) -> nodes.Assert:
        """Visit a Assert node by returning a fresh instance of it."""
        newnode = nodes.Assert(
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        msg: NodeNG | None = None
        if node.msg:
            msg = self.visit(node.msg, newnode)
        newnode.postinit(self.visit(node.test, newnode), msg)
        return newnode

    def check_type_comment(
        self,
        node: (
            ast.Assign | ast.arg | ast.For | ast.AsyncFor | ast.With | ast.AsyncWith
        ),
        parent: (
            nodes.Assign
            | nodes.Arguments
            | nodes.For
            | nodes.AsyncFor
            | nodes.With
            | nodes.AsyncWith
        ),
    ) -> NodeNG | None:
        type_comment = getattr(node, "type_comment", None)  # Added in Python 3.8
        if not type_comment:
            return None

        try:
            type_comment_ast = self._parser_module.parse(type_comment)
        except SyntaxError:
            # Invalid type comment, just skip it.
            return None

        # For '# type: # any comment' ast.parse returns a Module node,
        # without any nodes in the body.
        if not type_comment_ast.body:
            return None

        type_object = self.visit(type_comment_ast.body[0], parent=parent)
        if not isinstance(type_object, nodes.Expr):
            return None

        return type_object.value

    def check_function_type_comment(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, parent: NodeNG
    ) -> tuple[NodeNG | None, list[NodeNG]] | None:
        type_comment = getattr(node, "type_comment", None)  # Added in Python 3.8
        if not type_comment:
            return None

        try:
            type_comment_ast = parse_function_type_comment(type_comment)
        except SyntaxError:
            # Invalid type comment, just skip it.
            return None

        if not type_comment_ast:
            return None

        returns: NodeNG | None = None
        argtypes: list[NodeNG] = [
            self.visit(elem, parent) for elem in (type_comment_ast.argtypes or [])
        ]
        if type_comment_ast.returns:
            returns = self.visit(type_comment_ast.returns, parent)

        return returns, argtypes

    def visit_asyncfunctiondef(
        self, node: ast.AsyncFunctionDef, parent: NodeNG
    ) -> nodes.AsyncFunctionDef:
        return self._visit_functiondef(nodes.AsyncFunctionDef, node, parent)

    def visit_asyncfor(self, node: ast.AsyncFor, parent: NodeNG) -> nodes.AsyncFor:
        return self._visit_for(nodes.AsyncFor, node, parent)

    def visit_await(self, node: ast.Await, parent: NodeNG) -> nodes.Await:
        newnode = nodes.Await(
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        newnode.postinit(value=self.visit(node.value, newnode))
        return newnode

    def visit_asyncwith(self, node: ast.AsyncWith, parent: NodeNG) -> nodes.AsyncWith:
        return self._visit_with(nodes.AsyncWith, node, parent)

    def visit_assign(self, node: ast.Assign, parent: NodeNG) -> nodes.Assign:
        """Visit a Assign node by returning a fresh instance of it."""
        newnode = nodes.Assign(
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        type_annotation = self.check_type_comment(node, parent=newnode)
        newnode.postinit(
            targets=[self.visit(child, newnode) for child in node.targets],
            value=self.visit(node.value, newnode),
            type_annotation=type_annotation,
        )
        return newnode

    def visit_annassign(self, node: ast.AnnAssign, parent: NodeNG) -> nodes.AnnAssign:
        """Visit an AnnAssign node by returning a fresh instance of it."""
        newnode = nodes.AnnAssign(
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        newnode.postinit(
            target=self.visit(node.target, newnode),
            annotation=self.visit(node.annotation, newnode),
            simple=node.simple,
            value=self.visit(node.value, newnode),
        )
        return newnode

    @overload
    def visit_assignname(
        self, node: ast.AST, parent: NodeNG, node_name: str
    ) -> nodes.AssignName:
        ...

    @overload
    def visit_assignname(self, node: ast.AST, parent: NodeNG, node_name: None) -> None:
        ...

    def visit_assignname(
        self, node: ast.AST, parent: NodeNG, node_name: str | None
    ) -> nodes.AssignName | None:
        """Visit a node and return a AssignName node.

        Note: Method not called by 'visit'
        """
        if node_name is None:
            return None
        newnode = nodes.AssignName(
            name=node_name,
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        self._save_assignment(newnode)
        return newnode

    def visit_augassign(self, node: ast.AugAssign, parent: NodeNG) -> nodes.AugAssign:
        """Visit a AugAssign node by returning a fresh instance of it."""
        newnode = nodes.AugAssign(
            op=self._parser_module.bin_op_classes[type(node.op)] + "=",
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        newnode.postinit(
            self.visit(node.target, newnode), self.visit(node.value, newnode)
        )
        return newnode

    def visit_binop(self, node: ast.BinOp, parent: NodeNG) -> nodes.BinOp:
        """Visit a BinOp node by returning a fresh instance of it."""
        newnode = nodes.BinOp(
            op=self._parser_module.bin_op_classes[type(node.op)],
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        newnode.postinit(
            self.visit(node.left, newnode), self.visit(node.right, newnode)
        )
        return newnode

    def visit_boolop(self, node: ast.BoolOp, parent: NodeNG) -> nodes.BoolOp:
        """Visit a BoolOp node by returning a fresh instance of it."""
        newnode = nodes.BoolOp(
            op=self._parser_module.bool_op_classes[type(node.op)],
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        newnode.postinit([self.visit(child, newnode) for child in node.values])
        return newnode

    def visit_break(self, node: ast.Break, parent: NodeNG) -> nodes.Break:
        """Visit a Break node by returning a fresh instance of it."""
        return nodes.Break(
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )

    def visit_call(self, node: ast.Call, parent: NodeNG) -> nodes.Call:
        """Visit a CallFunc node by returning a fresh instance of it."""
        newnode = nodes.Call(
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        newnode.postinit(
            func=self.visit(node.func, newnode),
            args=[self.visit(child, newnode) for child in node.args],
            keywords=[self.visit(child, newnode) for child in node.keywords],
        )
        return newnode

    def visit_classdef(
        self, node: ast.ClassDef, parent: NodeNG, newstyle: bool = True
    ) -> nodes.ClassDef:
        """Visit a ClassDef node to become astroid."""
        node, doc_ast_node = self._get_doc(node)
        newnode = nodes.ClassDef(
            name=node.name,
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        metaclass = None
        for keyword in node.keywords:
            if keyword.arg == "metaclass":
                metaclass = self.visit(keyword, newnode).value
                break
        decorators = self.visit_decorators(node, newnode)
        newnode.postinit(
            [self.visit(child, newnode) for child in node.bases],
            [self.visit(child, newnode) for child in node.body],
            decorators,
            newstyle,
            metaclass,
            [
                self.visit(kwd, newnode)
                for kwd in node.keywords
                if kwd.arg != "metaclass"
            ],
            position=self._get_position_info(node, newnode),
            doc_node=self.visit(doc_ast_node, newnode),
        )
        self._fix_doc_node_position(newnode)
        return newnode

    def visit_continue(self, node: ast.Continue, parent: NodeNG) -> nodes.Continue:
        """Visit a Continue node by returning a fresh instance of it."""
        return nodes.Continue(
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )

    def visit_compare(self, node: ast.Compare, parent: NodeNG) -> nodes.Compare:
        """Visit a Compare node by returning a fresh instance of it."""
        newnode = nodes.Compare(
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        newnode.postinit(
            self.visit(node.left, newnode),
            [
                (
                    self._parser_module.cmp_op_classes[op.__class__],
                    self.visit(expr, newnode),
                )
                for (op, expr) in zip(node.ops, node.comparators)
            ],
        )
        return newnode

    def visit_comprehension(
        self, node: ast.comprehension, parent: NodeNG
    ) -> nodes.Comprehension:
        """Visit a Comprehension node by returning a fresh instance of it."""
        newnode = nodes.Comprehension(parent)
        newnode.postinit(
            self.visit(node.target, newnode),
            self.visit(node.iter, newnode),
            [self.visit(child, newnode) for child in node.ifs],
            bool(node.is_async),
        )
        return newnode

    def visit_decorators(
        self,
        node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
        parent: NodeNG,
    ) -> nodes.Decorators | None:
        """Visit a Decorators node by returning a fresh instance of it.

        Note: Method not called by 'visit'
        """
        if not node.decorator_list:
            return None
        # /!\ node is actually an _ast.FunctionDef node while
        # parent is an astroid.nodes.FunctionDef node
        if sys.version_info >= (3, 8):
            # Set the line number of the first decorator for Python 3.8+.
            lineno = node.decorator_list[0].lineno
            end_lineno = node.decorator_list[-1].end_lineno
            end_col_offset = node.decorator_list[-1].end_col_offset
        else:
            lineno = node.lineno
            end_lineno = None
            end_col_offset = None
        newnode = nodes.Decorators(
            lineno=lineno,
            col_offset=node.col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
            parent=parent,
        )
        newnode.postinit([self.visit(child, newnode) for child in node.decorator_list])
        return newnode

    def visit_delete(self, node: ast.Delete, parent: NodeNG) -> nodes.Delete:
        """Visit a Delete node by returning a fresh instance of it."""
        newnode = nodes.Delete(
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        newnode.postinit([self.visit(child, newnode) for child in node.targets])
        return newnode

    def _visit_dict_items(
        self, node: ast.Dict, parent: NodeNG, newnode: nodes.Dict
    ) -> Generator[tuple[NodeNG, NodeNG], None, None]:
        for key, value in zip(node.keys, node.values):
            rebuilt_key: NodeNG
            rebuilt_value = self.visit(value, newnode)
            if not key:
                # Extended unpacking
                rebuilt_key = nodes.DictUnpack(
                    lineno=rebuilt_value.lineno,
                    col_offset=rebuilt_value.col_offset,
                    # end_lineno and end_col_offset added in 3.8
                    end_lineno=getattr(rebuilt_value, "end_lineno", None),
                    end_col_offset=getattr(rebuilt_value, "end_col_offset", None),
                    parent=parent,
                )
            else:
                rebuilt_key = self.visit(key, newnode)
            yield rebuilt_key, rebuilt_value

    def visit_dict(self, node: ast.Dict, parent: NodeNG) -> nodes.Dict:
        """Visit a Dict node by returning a fresh instance of it."""
        newnode = nodes.Dict(
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        items: list[tuple[SuccessfulInferenceResult, SuccessfulInferenceResult]] = list(
            self._visit_dict_items(node, parent, newnode)
        )
        newnode.postinit(items)
        return newnode

    def visit_dictcomp(self, node: ast.DictComp, parent: NodeNG) -> nodes.DictComp:
        """Visit a DictComp node by returning a fresh instance of it."""
        newnode = nodes.DictComp(
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        newnode.postinit(
            self.visit(node.key, newnode),
            self.visit(node.value, newnode),
            [self.visit(child, newnode) for child in node.generators],
        )
        return newnode

    def visit_expr(self, node: ast.Expr, parent: NodeNG) -> nodes.Expr:
        """Visit a Expr node by returning a fresh instance of it."""
        newnode = nodes.Expr(
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        newnode.postinit(self.visit(node.value, newnode))
        return newnode

    def visit_excepthandler(
        self, node: ast.ExceptHandler, parent: NodeNG
    ) -> nodes.ExceptHandler:
        """Visit an ExceptHandler node by returning a fresh instance of it."""
        newnode = nodes.ExceptHandler(
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        newnode.postinit(
            self.visit(node.type, newnode),
            self.visit_assignname(node, newnode, node.name),
            [self.visit(child, newnode) for child in node.body],
        )
        return newnode

    @overload
    def _visit_for(
        self, cls: type[nodes.For], node: ast.For, parent: NodeNG
    ) -> nodes.For:
        ...

    @overload
    def _visit_for(
        self, cls: type[nodes.AsyncFor], node: ast.AsyncFor, parent: NodeNG
    ) -> nodes.AsyncFor:
        ...

    def _visit_for(
        self, cls: type[_ForT], node: ast.For | ast.AsyncFor, parent: NodeNG
    ) -> _ForT:
        """Visit a For node by returning a fresh instance of it."""
        col_offset = node.col_offset
        if IS_PYPY and not PY39_PLUS and isinstance(node, ast.AsyncFor) and self._data:
            # pylint: disable-next=unsubscriptable-object
            col_offset = self._data[node.lineno - 1].index("async")

        newnode = cls(
            lineno=node.lineno,
            col_offset=col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        type_annotation = self.check_type_comment(node, parent=newnode)
        newnode.postinit(
            target=self.visit(node.target, newnode),
            iter=self.visit(node.iter, newnode),
            body=[self.visit(child, newnode) for child in node.body],
            orelse=[self.visit(child, newnode) for child in node.orelse],
            type_annotation=type_annotation,
        )
        return newnode

    def visit_for(self, node: ast.For, parent: NodeNG) -> nodes.For:
        return self._visit_for(nodes.For, node, parent)

    def visit_importfrom(
        self, node: ast.ImportFrom, parent: NodeNG
    ) -> nodes.ImportFrom:
        """Visit an ImportFrom node by returning a fresh instance of it."""
        names = [(alias.name, alias.asname) for alias in node.names]
        newnode = nodes.ImportFrom(
            fromname=node.module or "",
            names=names,
            level=node.level or None,
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        # store From names to add them to locals after building
        self._import_from_nodes.append(newnode)
        return newnode

    @overload
    def _visit_functiondef(
        self, cls: type[nodes.FunctionDef], node: ast.FunctionDef, parent: NodeNG
    ) -> nodes.FunctionDef:
        ...

    @overload
    def _visit_functiondef(
        self,
        cls: type[nodes.AsyncFunctionDef],
        node: ast.AsyncFunctionDef,
        parent: NodeNG,
    ) -> nodes.AsyncFunctionDef:
        ...

    def _visit_functiondef(
        self,
        cls: type[_FunctionT],
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        parent: NodeNG,
    ) -> _FunctionT:
        """Visit an FunctionDef node to become astroid."""
        self._global_names.append({})
        node, doc_ast_node = self._get_doc(node)

        lineno = node.lineno
        if PY38_PLUS and node.decorator_list:
            # Python 3.8 sets the line number of a decorated function
            # to be the actual line number of the function, but the
            # previous versions expected the decorator's line number instead.
            # We reset the function's line number to that of the
            # first decorator to maintain backward compatibility.
            # It's not ideal but this discrepancy was baked into
            # the framework for *years*.
            lineno = node.decorator_list[0].lineno

        newnode = cls(
            name=node.name,
            lineno=lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        decorators = self.visit_decorators(node, newnode)
        returns: NodeNG | None
        if node.returns:
            returns = self.visit(node.returns, newnode)
        else:
            returns = None

        type_comment_args = type_comment_returns = None
        type_comment_annotation = self.check_function_type_comment(node, newnode)
        if type_comment_annotation:
            type_comment_returns, type_comment_args = type_comment_annotation
        newnode.postinit(
            args=self.visit(node.args, newnode),
            body=[self.visit(child, newnode) for child in node.body],
            decorators=decorators,
            returns=returns,
            type_comment_returns=type_comment_returns,
            type_comment_args=type_comment_args,
            position=self._get_position_info(node, newnode),
            doc_node=self.visit(doc_ast_node, newnode),
        )
        self._fix_doc_node_position(newnode)
        self._global_names.pop()
        return newnode

    def visit_functiondef(
        self, node: ast.FunctionDef, parent: NodeNG
    ) -> nodes.FunctionDef:
        return self._visit_functiondef(nodes.FunctionDef, node, parent)

    def visit_generatorexp(
        self, node: ast.GeneratorExp, parent: NodeNG
    ) -> nodes.GeneratorExp:
        """Visit a GeneratorExp node by returning a fresh instance of it."""
        newnode = nodes.GeneratorExp(
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        newnode.postinit(
            self.visit(node.elt, newnode),
            [self.visit(child, newnode) for child in node.generators],
        )
        return newnode

    def visit_attribute(
        self, node: ast.Attribute, parent: NodeNG
    ) -> nodes.Attribute | nodes.AssignAttr | nodes.DelAttr:
        """Visit an Attribute node by returning a fresh instance of it."""
        context = self._get_context(node)
        newnode: nodes.Attribute | nodes.AssignAttr | nodes.DelAttr
        if context == Context.Del:
            # FIXME : maybe we should reintroduce and visit_delattr ?
            # for instance, deactivating assign_ctx
            newnode = nodes.DelAttr(
                attrname=node.attr,
                lineno=node.lineno,
                col_offset=node.col_offset,
                # end_lineno and end_col_offset added in 3.8
                end_lineno=getattr(node, "end_lineno", None),
                end_col_offset=getattr(node, "end_col_offset", None),
                parent=parent,
            )
        elif context == Context.Store:
            newnode = nodes.AssignAttr(
                attrname=node.attr,
                lineno=node.lineno,
                col_offset=node.col_offset,
                # end_lineno and end_col_offset added in 3.8
                end_lineno=getattr(node, "end_lineno", None),
                end_col_offset=getattr(node, "end_col_offset", None),
                parent=parent,
            )
            # Prohibit a local save if we are in an ExceptHandler.
            if not isinstance(parent, nodes.ExceptHandler):
                # mypy doesn't recognize that newnode has to be AssignAttr because it
                # doesn't support ParamSpec
                # See https://github.com/python/mypy/issues/8645
                self._delayed_assattr.append(newnode)  # type: ignore[arg-type]
        else:
            newnode = nodes.Attribute(
                attrname=node.attr,
                lineno=node.lineno,
                col_offset=node.col_offset,
                # end_lineno and end_col_offset added in 3.8
                end_lineno=getattr(node, "end_lineno", None),
                end_col_offset=getattr(node, "end_col_offset", None),
                parent=parent,
            )
        newnode.postinit(self.visit(node.value, newnode))
        return newnode

    def visit_global(self, node: ast.Global, parent: NodeNG) -> nodes.Global:
        """Visit a Global node to become astroid."""
        newnode = nodes.Global(
            names=node.names,
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        if self._global_names:  # global at the module level, no effect
            for name in node.names:
                self._global_names[-1].setdefault(name, []).append(newnode)
        return newnode

    def visit_if(self, node: ast.If, parent: NodeNG) -> nodes.If:
        """Visit an If node by returning a fresh instance of it."""
        newnode = nodes.If(
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        newnode.postinit(
            self.visit(node.test, newnode),
            [self.visit(child, newnode) for child in node.body],
            [self.visit(child, newnode) for child in node.orelse],
        )
        return newnode

    def visit_ifexp(self, node: ast.IfExp, parent: NodeNG) -> nodes.IfExp:
        """Visit a IfExp node by returning a fresh instance of it."""
        newnode = nodes.IfExp(
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        newnode.postinit(
            self.visit(node.test, newnode),
            self.visit(node.body, newnode),
            self.visit(node.orelse, newnode),
        )
        return newnode

    def visit_import(self, node: ast.Import, parent: NodeNG) -> nodes.Import:
        """Visit a Import node by returning a fresh instance of it."""
        names = [(alias.name, alias.asname) for alias in node.names]
        newnode = nodes.Import(
            names=names,
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        # save import names in parent's locals:
        for name, asname in newnode.names:
            name = asname or name
            parent.set_local(name.split(".")[0], newnode)
        return newnode

    def visit_joinedstr(self, node: ast.JoinedStr, parent: NodeNG) -> nodes.JoinedStr:
        newnode = nodes.JoinedStr(
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        newnode.postinit([self.visit(child, newnode) for child in node.values])
        return newnode

    def visit_formattedvalue(
        self, node: ast.FormattedValue, parent: NodeNG
    ) -> nodes.FormattedValue:
        newnode = nodes.FormattedValue(
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        newnode.postinit(
            value=self.visit(node.value, newnode),
            conversion=node.conversion,
            format_spec=self.visit(node.format_spec, newnode),
        )
        return newnode

    if sys.version_info >= (3, 8):

        def visit_namedexpr(
            self, node: ast.NamedExpr, parent: NodeNG
        ) -> nodes.NamedExpr:
            newnode = nodes.NamedExpr(
                lineno=node.lineno,
                col_offset=node.col_offset,
                # end_lineno and end_col_offset added in 3.8
                end_lineno=getattr(node, "end_lineno", None),
                end_col_offset=getattr(node, "end_col_offset", None),
                parent=parent,
            )
            newnode.postinit(
                self.visit(node.target, newnode), self.visit(node.value, newnode)
            )
            return newnode

    if sys.version_info < (3, 9):
        # Not used in Python 3.9+.
        def visit_extslice(
            self, node: ast.ExtSlice, parent: nodes.Subscript
        ) -> nodes.Tuple:
            """Visit an ExtSlice node by returning a fresh instance of Tuple."""
            # ExtSlice doesn't have lineno or col_offset information
            newnode = nodes.Tuple(ctx=Context.Load, parent=parent)
            newnode.postinit([self.visit(dim, newnode) for dim in node.dims])
            return newnode

        def visit_index(self, node: ast.Index, parent: nodes.Subscript) -> NodeNG:
            """Visit a Index node by returning a fresh instance of NodeNG."""
            return self.visit(node.value, parent)

    def visit_keyword(self, node: ast.keyword, parent: NodeNG) -> nodes.Keyword:
        """Visit a Keyword node by returning a fresh instance of it."""
        newnode = nodes.Keyword(
            arg=node.arg,
            # position attributes added in 3.9
            lineno=getattr(node, "lineno", None),
            col_offset=getattr(node, "col_offset", None),
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        newnode.postinit(self.visit(node.value, newnode))
        return newnode

    def visit_lambda(self, node: ast.Lambda, parent: NodeNG) -> nodes.Lambda:
        """Visit a Lambda node by returning a fresh instance of it."""
        newnode = nodes.Lambda(
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        newnode.postinit(self.visit(node.args, newnode), self.visit(node.body, newnode))
        return newnode

    def visit_list(self, node: ast.List, parent: NodeNG) -> nodes.List:
        """Visit a List node by returning a fresh instance of it."""
        context = self._get_context(node)
        newnode = nodes.List(
            ctx=context,
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        newnode.postinit([self.visit(child, newnode) for child in node.elts])
        return newnode

    def visit_listcomp(self, node: ast.ListComp, parent: NodeNG) -> nodes.ListComp:
        """Visit a ListComp node by returning a fresh instance of it."""
        newnode = nodes.ListComp(
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        newnode.postinit(
            self.visit(node.elt, newnode),
            [self.visit(child, newnode) for child in node.generators],
        )
        return newnode

    def visit_name(
        self, node: ast.Name, parent: NodeNG
    ) -> nodes.Name | nodes.AssignName | nodes.DelName:
        """Visit a Name node by returning a fresh instance of it."""
        context = self._get_context(node)
        newnode: nodes.Name | nodes.AssignName | nodes.DelName
        if context == Context.Del:
            newnode = nodes.DelName(
                name=node.id,
                lineno=node.lineno,
                col_offset=node.col_offset,
                # end_lineno and end_col_offset added in 3.8
                end_lineno=getattr(node, "end_lineno", None),
                end_col_offset=getattr(node, "end_col_offset", None),
                parent=parent,
            )
        elif context == Context.Store:
            newnode = nodes.AssignName(
                name=node.id,
                lineno=node.lineno,
                col_offset=node.col_offset,
                # end_lineno and end_col_offset added in 3.8
                end_lineno=getattr(node, "end_lineno", None),
                end_col_offset=getattr(node, "end_col_offset", None),
                parent=parent,
            )
        else:
            newnode = nodes.Name(
                name=node.id,
                lineno=node.lineno,
                col_offset=node.col_offset,
                # end_lineno and end_col_offset added in 3.8
                end_lineno=getattr(node, "end_lineno", None),
                end_col_offset=getattr(node, "end_col_offset", None),
                parent=parent,
            )
        # XXX REMOVE me :
        if context in (Context.Del, Context.Store):  # 'Aug' ??
            newnode = cast(Union[nodes.AssignName, nodes.DelName], newnode)
            self._save_assignment(newnode)
        return newnode

    def visit_nonlocal(self, node: ast.Nonlocal, parent: NodeNG) -> nodes.Nonlocal:
        """Visit a Nonlocal node and return a new instance of it."""
        return nodes.Nonlocal(
            names=node.names,
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )

    def visit_constant(self, node: ast.Constant, parent: NodeNG) -> nodes.Const:
        """Visit a Constant node by returning a fresh instance of Const."""
        return nodes.Const(
            value=node.value,
            kind=node.kind,
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )

    if sys.version_info < (3, 8):
        # Not used in Python 3.8+.
        def visit_ellipsis(self, node: ast.Ellipsis, parent: NodeNG) -> nodes.Const:
            """Visit an Ellipsis node by returning a fresh instance of Const."""
            return nodes.Const(
                value=Ellipsis,
                lineno=node.lineno,
                col_offset=node.col_offset,
                parent=parent,
            )

        def visit_nameconstant(
            self, node: ast.NameConstant, parent: NodeNG
        ) -> nodes.Const:
            # For singleton values True / False / None
            return nodes.Const(
                node.value,
                node.lineno,
                node.col_offset,
                parent,
            )

        def visit_str(self, node: ast.Str | ast.Bytes, parent: NodeNG) -> nodes.Const:
            """Visit a String/Bytes node by returning a fresh instance of Const."""
            return nodes.Const(
                node.s,
                node.lineno,
                node.col_offset,
                parent,
            )

        visit_bytes = visit_str

        def visit_num(self, node: ast.Num, parent: NodeNG) -> nodes.Const:
            """Visit a Num node by returning a fresh instance of Const."""
            return nodes.Const(
                node.n,
                node.lineno,
                node.col_offset,
                parent,
            )

    def visit_pass(self, node: ast.Pass, parent: NodeNG) -> nodes.Pass:
        """Visit a Pass node by returning a fresh instance of it."""
        return nodes.Pass(
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )

    def visit_raise(self, node: ast.Raise, parent: NodeNG) -> nodes.Raise:
        """Visit a Raise node by returning a fresh instance of it."""
        newnode = nodes.Raise(
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        # no traceback; anyway it is not used in Pylint
        newnode.postinit(
            exc=self.visit(node.exc, newnode),
            cause=self.visit(node.cause, newnode),
        )
        return newnode

    def visit_return(self, node: ast.Return, parent: NodeNG) -> nodes.Return:
        """Visit a Return node by returning a fresh instance of it."""
        newnode = nodes.Return(
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        if node.value is not None:
            newnode.postinit(self.visit(node.value, newnode))
        return newnode

    def visit_set(self, node: ast.Set, parent: NodeNG) -> nodes.Set:
        """Visit a Set node by returning a fresh instance of it."""
        newnode = nodes.Set(
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        newnode.postinit([self.visit(child, newnode) for child in node.elts])
        return newnode

    def visit_setcomp(self, node: ast.SetComp, parent: NodeNG) -> nodes.SetComp:
        """Visit a SetComp node by returning a fresh instance of it."""
        newnode = nodes.SetComp(
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        newnode.postinit(
            self.visit(node.elt, newnode),
            [self.visit(child, newnode) for child in node.generators],
        )
        return newnode

    def visit_slice(self, node: ast.Slice, parent: nodes.Subscript) -> nodes.Slice:
        """Visit a Slice node by returning a fresh instance of it."""
        newnode = nodes.Slice(
            # position attributes added in 3.9
            lineno=getattr(node, "lineno", None),
            col_offset=getattr(node, "col_offset", None),
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        newnode.postinit(
            lower=self.visit(node.lower, newnode),
            upper=self.visit(node.upper, newnode),
            step=self.visit(node.step, newnode),
        )
        return newnode

    def visit_subscript(self, node: ast.Subscript, parent: NodeNG) -> nodes.Subscript:
        """Visit a Subscript node by returning a fresh instance of it."""
        context = self._get_context(node)
        newnode = nodes.Subscript(
            ctx=context,
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        newnode.postinit(
            self.visit(node.value, newnode), self.visit(node.slice, newnode)
        )
        return newnode

    def visit_starred(self, node: ast.Starred, parent: NodeNG) -> nodes.Starred:
        """Visit a Starred node and return a new instance of it."""
        context = self._get_context(node)
        newnode = nodes.Starred(
            ctx=context,
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        newnode.postinit(self.visit(node.value, newnode))
        return newnode

    def visit_tryexcept(self, node: ast.Try, parent: NodeNG) -> nodes.TryExcept:
        """Visit a TryExcept node by returning a fresh instance of it."""
        if sys.version_info >= (3, 8):
            # TryExcept excludes the 'finally' but that will be included in the
            # end_lineno from 'node'. Therefore, we check all non 'finally'
            # children to find the correct end_lineno and column.
            end_lineno = node.end_lineno
            end_col_offset = node.end_col_offset
            all_children: list[ast.AST] = [*node.body, *node.handlers, *node.orelse]
            for child in reversed(all_children):
                end_lineno = child.end_lineno
                end_col_offset = child.end_col_offset
                break
            newnode = nodes.TryExcept(
                lineno=node.lineno,
                col_offset=node.col_offset,
                end_lineno=end_lineno,
                end_col_offset=end_col_offset,
                parent=parent,
            )
        else:
            newnode = nodes.TryExcept(node.lineno, node.col_offset, parent)
        newnode.postinit(
            [self.visit(child, newnode) for child in node.body],
            [self.visit(child, newnode) for child in node.handlers],
            [self.visit(child, newnode) for child in node.orelse],
        )
        return newnode

    def visit_try(
        self, node: ast.Try, parent: NodeNG
    ) -> nodes.TryExcept | nodes.TryFinally | None:
        # python 3.3 introduce a new Try node replacing
        # TryFinally/TryExcept nodes
        if node.finalbody:
            newnode = nodes.TryFinally(
                lineno=node.lineno,
                col_offset=node.col_offset,
                # end_lineno and end_col_offset added in 3.8
                end_lineno=getattr(node, "end_lineno", None),
                end_col_offset=getattr(node, "end_col_offset", None),
                parent=parent,
            )
            body: list[NodeNG | nodes.TryExcept]
            if node.handlers:
                body = [self.visit_tryexcept(node, newnode)]
            else:
                body = [self.visit(child, newnode) for child in node.body]
            newnode.postinit(body, [self.visit(n, newnode) for n in node.finalbody])
            return newnode
        if node.handlers:
            return self.visit_tryexcept(node, parent)
        return None

    def visit_trystar(self, node: ast.TryStar, parent: NodeNG) -> nodes.TryStar:
        newnode = nodes.TryStar(
            lineno=node.lineno,
            col_offset=node.col_offset,
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        newnode.postinit(
            body=[self.visit(n, newnode) for n in node.body],
            handlers=[self.visit(n, newnode) for n in node.handlers],
            orelse=[self.visit(n, newnode) for n in node.orelse],
            finalbody=[self.visit(n, newnode) for n in node.finalbody],
        )
        return newnode

    def visit_tuple(self, node: ast.Tuple, parent: NodeNG) -> nodes.Tuple:
        """Visit a Tuple node by returning a fresh instance of it."""
        context = self._get_context(node)
        newnode = nodes.Tuple(
            ctx=context,
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        newnode.postinit([self.visit(child, newnode) for child in node.elts])
        return newnode

    def visit_unaryop(self, node: ast.UnaryOp, parent: NodeNG) -> nodes.UnaryOp:
        """Visit a UnaryOp node by returning a fresh instance of it."""
        newnode = nodes.UnaryOp(
            op=self._parser_module.unary_op_classes[node.op.__class__],
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        newnode.postinit(self.visit(node.operand, newnode))
        return newnode

    def visit_while(self, node: ast.While, parent: NodeNG) -> nodes.While:
        """Visit a While node by returning a fresh instance of it."""
        newnode = nodes.While(
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        newnode.postinit(
            self.visit(node.test, newnode),
            [self.visit(child, newnode) for child in node.body],
            [self.visit(child, newnode) for child in node.orelse],
        )
        return newnode

    @overload
    def _visit_with(
        self, cls: type[nodes.With], node: ast.With, parent: NodeNG
    ) -> nodes.With:
        ...

    @overload
    def _visit_with(
        self, cls: type[nodes.AsyncWith], node: ast.AsyncWith, parent: NodeNG
    ) -> nodes.AsyncWith:
        ...

    def _visit_with(
        self,
        cls: type[_WithT],
        node: ast.With | ast.AsyncWith,
        parent: NodeNG,
    ) -> _WithT:
        col_offset = node.col_offset
        if IS_PYPY and not PY39_PLUS and isinstance(node, ast.AsyncWith) and self._data:
            # pylint: disable-next=unsubscriptable-object
            col_offset = self._data[node.lineno - 1].index("async")

        newnode = cls(
            lineno=node.lineno,
            col_offset=col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )

        def visit_child(child: ast.withitem) -> tuple[NodeNG, NodeNG | None]:
            expr = self.visit(child.context_expr, newnode)
            var = self.visit(child.optional_vars, newnode)
            return expr, var

        type_annotation = self.check_type_comment(node, parent=newnode)
        newnode.postinit(
            items=[visit_child(child) for child in node.items],
            body=[self.visit(child, newnode) for child in node.body],
            type_annotation=type_annotation,
        )
        return newnode

    def visit_with(self, node: ast.With, parent: NodeNG) -> NodeNG:
        return self._visit_with(nodes.With, node, parent)

    def visit_yield(self, node: ast.Yield, parent: NodeNG) -> NodeNG:
        """Visit a Yield node by returning a fresh instance of it."""
        newnode = nodes.Yield(
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        if node.value is not None:
            newnode.postinit(self.visit(node.value, newnode))
        return newnode

    def visit_yieldfrom(self, node: ast.YieldFrom, parent: NodeNG) -> NodeNG:
        newnode = nodes.YieldFrom(
            lineno=node.lineno,
            col_offset=node.col_offset,
            # end_lineno and end_col_offset added in 3.8
            end_lineno=getattr(node, "end_lineno", None),
            end_col_offset=getattr(node, "end_col_offset", None),
            parent=parent,
        )
        if node.value is not None:
            newnode.postinit(self.visit(node.value, newnode))
        return newnode

    if sys.version_info >= (3, 10):

        def visit_match(self, node: ast.Match, parent: NodeNG) -> nodes.Match:
            newnode = nodes.Match(
                lineno=node.lineno,
                col_offset=node.col_offset,
                end_lineno=node.end_lineno,
                end_col_offset=node.end_col_offset,
                parent=parent,
            )
            newnode.postinit(
                subject=self.visit(node.subject, newnode),
                cases=[self.visit(case, newnode) for case in node.cases],
            )
            return newnode

        def visit_matchcase(
            self, node: ast.match_case, parent: NodeNG
        ) -> nodes.MatchCase:
            newnode = nodes.MatchCase(parent=parent)
            newnode.postinit(
                pattern=self.visit(node.pattern, newnode),
                guard=self.visit(node.guard, newnode),
                body=[self.visit(child, newnode) for child in node.body],
            )
            return newnode

        def visit_matchvalue(
            self, node: ast.MatchValue, parent: NodeNG
        ) -> nodes.MatchValue:
            newnode = nodes.MatchValue(
                lineno=node.lineno,
                col_offset=node.col_offset,
                end_lineno=node.end_lineno,
                end_col_offset=node.end_col_offset,
                parent=parent,
            )
            newnode.postinit(value=self.visit(node.value, newnode))
            return newnode

        def visit_matchsingleton(
            self, node: ast.MatchSingleton, parent: NodeNG
        ) -> nodes.MatchSingleton:
            return nodes.MatchSingleton(
                value=node.value,
                lineno=node.lineno,
                col_offset=node.col_offset,
                end_lineno=node.end_lineno,
                end_col_offset=node.end_col_offset,
                parent=parent,
            )

        def visit_matchsequence(
            self, node: ast.MatchSequence, parent: NodeNG
        ) -> nodes.MatchSequence:
            newnode = nodes.MatchSequence(
                lineno=node.lineno,
                col_offset=node.col_offset,
                end_lineno=node.end_lineno,
                end_col_offset=node.end_col_offset,
                parent=parent,
            )
            newnode.postinit(
                patterns=[self.visit(pattern, newnode) for pattern in node.patterns]
            )
            return newnode

        def visit_matchmapping(
            self, node: ast.MatchMapping, parent: NodeNG
        ) -> nodes.MatchMapping:
            newnode = nodes.MatchMapping(
                lineno=node.lineno,
                col_offset=node.col_offset,
                end_lineno=node.end_lineno,
                end_col_offset=node.end_col_offset,
                parent=parent,
            )
            # Add AssignName node for 'node.name'
            # https://bugs.python.org/issue43994
            newnode.postinit(
                keys=[self.visit(child, newnode) for child in node.keys],
                patterns=[self.visit(pattern, newnode) for pattern in node.patterns],
                rest=self.visit_assignname(node, newnode, node.rest),
            )
            return newnode

        def visit_matchclass(
            self, node: ast.MatchClass, parent: NodeNG
        ) -> nodes.MatchClass:
            newnode = nodes.MatchClass(
                lineno=node.lineno,
                col_offset=node.col_offset,
                end_lineno=node.end_lineno,
                end_col_offset=node.end_col_offset,
                parent=parent,
            )
            newnode.postinit(
                cls=self.visit(node.cls, newnode),
                patterns=[self.visit(pattern, newnode) for pattern in node.patterns],
                kwd_attrs=node.kwd_attrs,
                kwd_patterns=[
                    self.visit(pattern, newnode) for pattern in node.kwd_patterns
                ],
            )
            return newnode

        def visit_matchstar(
            self, node: ast.MatchStar, parent: NodeNG
        ) -> nodes.MatchStar:
            newnode = nodes.MatchStar(
                lineno=node.lineno,
                col_offset=node.col_offset,
                end_lineno=node.end_lineno,
                end_col_offset=node.end_col_offset,
                parent=parent,
            )
            # Add AssignName node for 'node.name'
            # https://bugs.python.org/issue43994
            newnode.postinit(name=self.visit_assignname(node, newnode, node.name))
            return newnode

        def visit_matchas(self, node: ast.MatchAs, parent: NodeNG) -> nodes.MatchAs:
            newnode = nodes.MatchAs(
                lineno=node.lineno,
                col_offset=node.col_offset,
                end_lineno=node.end_lineno,
                end_col_offset=node.end_col_offset,
                parent=parent,
            )
            # Add AssignName node for 'node.name'
            # https://bugs.python.org/issue43994
            newnode.postinit(
                pattern=self.visit(node.pattern, newnode),
                name=self.visit_assignname(node, newnode, node.name),
            )
            return newnode

        def visit_matchor(self, node: ast.MatchOr, parent: NodeNG) -> nodes.MatchOr:
            newnode = nodes.MatchOr(
                lineno=node.lineno,
                col_offset=node.col_offset,
                end_lineno=node.end_lineno,
                end_col_offset=node.end_col_offset,
                parent=parent,
            )
            newnode.postinit(
                patterns=[self.visit(pattern, newnode) for pattern in node.patterns]
            )
            return newnode
