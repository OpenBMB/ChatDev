# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""This module renders Astroid nodes as string"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from astroid.nodes import Const
    from astroid.nodes.node_classes import (
        Match,
        MatchAs,
        MatchCase,
        MatchClass,
        MatchMapping,
        MatchOr,
        MatchSequence,
        MatchSingleton,
        MatchStar,
        MatchValue,
        Unknown,
    )

# pylint: disable=unused-argument

DOC_NEWLINE = "\0"


# Visitor pattern require argument all the time and is not better with staticmethod
# noinspection PyUnusedLocal,PyMethodMayBeStatic
class AsStringVisitor:
    """Visitor to render an Astroid node as a valid python code string"""

    def __init__(self, indent: str = "    "):
        self.indent: str = indent

    def __call__(self, node) -> str:
        """Makes this visitor behave as a simple function"""
        return node.accept(self).replace(DOC_NEWLINE, "\n")

    def _docs_dedent(self, doc_node: Const | None) -> str:
        """Stop newlines in docs being indented by self._stmt_list"""
        if not doc_node:
            return ""

        return '\n{}"""{}"""'.format(
            self.indent, doc_node.value.replace("\n", DOC_NEWLINE)
        )

    def _stmt_list(self, stmts: list, indent: bool = True) -> str:
        """return a list of nodes to string"""
        stmts_str: str = "\n".join(
            nstr for nstr in [n.accept(self) for n in stmts] if nstr
        )
        if not indent:
            return stmts_str

        return self.indent + stmts_str.replace("\n", "\n" + self.indent)

    def _precedence_parens(self, node, child, is_left: bool = True) -> str:
        """Wrap child in parens only if required to keep same semantics"""
        if self._should_wrap(node, child, is_left):
            return f"({child.accept(self)})"

        return child.accept(self)

    def _should_wrap(self, node, child, is_left: bool) -> bool:
        """Wrap child if:
        - it has lower precedence
        - same precedence with position opposite to associativity direction
        """
        node_precedence = node.op_precedence()
        child_precedence = child.op_precedence()

        if node_precedence > child_precedence:
            # 3 * (4 + 5)
            return True

        if (
            node_precedence == child_precedence
            and is_left != node.op_left_associative()
        ):
            # 3 - (4 - 5)
            # (2**3)**4
            return True

        return False

    # visit_<node> methods ###########################################

    def visit_await(self, node) -> str:
        return f"await {node.value.accept(self)}"

    def visit_asyncwith(self, node) -> str:
        return f"async {self.visit_with(node)}"

    def visit_asyncfor(self, node) -> str:
        return f"async {self.visit_for(node)}"

    def visit_arguments(self, node) -> str:
        """return an astroid.Function node as string"""
        return node.format_args()

    def visit_assignattr(self, node) -> str:
        """return an astroid.AssAttr node as string"""
        return self.visit_attribute(node)

    def visit_assert(self, node) -> str:
        """return an astroid.Assert node as string"""
        if node.fail:
            return f"assert {node.test.accept(self)}, {node.fail.accept(self)}"
        return f"assert {node.test.accept(self)}"

    def visit_assignname(self, node) -> str:
        """return an astroid.AssName node as string"""
        return node.name

    def visit_assign(self, node) -> str:
        """return an astroid.Assign node as string"""
        lhs = " = ".join(n.accept(self) for n in node.targets)
        return f"{lhs} = {node.value.accept(self)}"

    def visit_augassign(self, node) -> str:
        """return an astroid.AugAssign node as string"""
        return f"{node.target.accept(self)} {node.op} {node.value.accept(self)}"

    def visit_annassign(self, node) -> str:
        """Return an astroid.AugAssign node as string"""

        target = node.target.accept(self)
        annotation = node.annotation.accept(self)
        if node.value is None:
            return f"{target}: {annotation}"
        return f"{target}: {annotation} = {node.value.accept(self)}"

    def visit_binop(self, node) -> str:
        """return an astroid.BinOp node as string"""
        left = self._precedence_parens(node, node.left)
        right = self._precedence_parens(node, node.right, is_left=False)
        if node.op == "**":
            return f"{left}{node.op}{right}"

        return f"{left} {node.op} {right}"

    def visit_boolop(self, node) -> str:
        """return an astroid.BoolOp node as string"""
        values = [f"{self._precedence_parens(node, n)}" for n in node.values]
        return (f" {node.op} ").join(values)

    def visit_break(self, node) -> str:
        """return an astroid.Break node as string"""
        return "break"

    def visit_call(self, node) -> str:
        """return an astroid.Call node as string"""
        expr_str = self._precedence_parens(node, node.func)
        args = [arg.accept(self) for arg in node.args]
        if node.keywords:
            keywords = [kwarg.accept(self) for kwarg in node.keywords]
        else:
            keywords = []

        args.extend(keywords)
        return f"{expr_str}({', '.join(args)})"

    def visit_classdef(self, node) -> str:
        """return an astroid.ClassDef node as string"""
        decorate = node.decorators.accept(self) if node.decorators else ""
        args = [n.accept(self) for n in node.bases]
        if node._metaclass and not node.has_metaclass_hack():
            args.append("metaclass=" + node._metaclass.accept(self))
        args += [n.accept(self) for n in node.keywords]
        args_str = f"({', '.join(args)})" if args else ""
        docs = self._docs_dedent(node.doc_node)
        return "\n\n{}class {}{}:{}\n{}\n".format(
            decorate, node.name, args_str, docs, self._stmt_list(node.body)
        )

    def visit_compare(self, node) -> str:
        """return an astroid.Compare node as string"""
        rhs_str = " ".join(
            f"{op} {self._precedence_parens(node, expr, is_left=False)}"
            for op, expr in node.ops
        )
        return f"{self._precedence_parens(node, node.left)} {rhs_str}"

    def visit_comprehension(self, node) -> str:
        """return an astroid.Comprehension node as string"""
        ifs = "".join(f" if {n.accept(self)}" for n in node.ifs)
        generated = f"for {node.target.accept(self)} in {node.iter.accept(self)}{ifs}"
        return f"{'async ' if node.is_async else ''}{generated}"

    def visit_const(self, node) -> str:
        """return an astroid.Const node as string"""
        if node.value is Ellipsis:
            return "..."
        return repr(node.value)

    def visit_continue(self, node) -> str:
        """return an astroid.Continue node as string"""
        return "continue"

    def visit_delete(self, node) -> str:  # XXX check if correct
        """return an astroid.Delete node as string"""
        return f"del {', '.join(child.accept(self) for child in node.targets)}"

    def visit_delattr(self, node) -> str:
        """return an astroid.DelAttr node as string"""
        return self.visit_attribute(node)

    def visit_delname(self, node) -> str:
        """return an astroid.DelName node as string"""
        return node.name

    def visit_decorators(self, node) -> str:
        """return an astroid.Decorators node as string"""
        return "@%s\n" % "\n@".join(item.accept(self) for item in node.nodes)

    def visit_dict(self, node) -> str:
        """return an astroid.Dict node as string"""
        return "{%s}" % ", ".join(self._visit_dict(node))

    def _visit_dict(self, node) -> Iterator[str]:
        for key, value in node.items:
            key = key.accept(self)
            value = value.accept(self)
            if key == "**":
                # It can only be a DictUnpack node.
                yield key + value
            else:
                yield f"{key}: {value}"

    def visit_dictunpack(self, node) -> str:
        return "**"

    def visit_dictcomp(self, node) -> str:
        """return an astroid.DictComp node as string"""
        return "{{{}: {} {}}}".format(
            node.key.accept(self),
            node.value.accept(self),
            " ".join(n.accept(self) for n in node.generators),
        )

    def visit_expr(self, node) -> str:
        """return an astroid.Discard node as string"""
        return node.value.accept(self)

    def visit_emptynode(self, node) -> str:
        """dummy method for visiting an Empty node"""
        return ""

    def visit_excepthandler(self, node) -> str:
        if node.type:
            if node.name:
                excs = f"except {node.type.accept(self)} as {node.name.accept(self)}"
            else:
                excs = f"except {node.type.accept(self)}"
        else:
            excs = "except"
        return f"{excs}:\n{self._stmt_list(node.body)}"

    def visit_empty(self, node) -> str:
        """return an Empty node as string"""
        return ""

    def visit_for(self, node) -> str:
        """return an astroid.For node as string"""
        fors = "for {} in {}:\n{}".format(
            node.target.accept(self), node.iter.accept(self), self._stmt_list(node.body)
        )
        if node.orelse:
            fors = f"{fors}\nelse:\n{self._stmt_list(node.orelse)}"
        return fors

    def visit_importfrom(self, node) -> str:
        """return an astroid.ImportFrom node as string"""
        return "from {} import {}".format(
            "." * (node.level or 0) + node.modname, _import_string(node.names)
        )

    def visit_joinedstr(self, node) -> str:
        string = "".join(
            # Use repr on the string literal parts
            # to get proper escapes, e.g. \n, \\, \"
            # But strip the quotes off the ends
            # (they will always be one character: ' or ")
            repr(value.value)[1:-1]
            # Literal braces must be doubled to escape them
            .replace("{", "{{").replace("}", "}}")
            # Each value in values is either a string literal (Const)
            # or a FormattedValue
            if type(value).__name__ == "Const" else value.accept(self)
            for value in node.values
        )

        # Try to find surrounding quotes that don't appear at all in the string.
        # Because the formatted values inside {} can't contain backslash (\)
        # using a triple quote is sometimes necessary
        for quote in ("'", '"', '"""', "'''"):
            if quote not in string:
                break

        return "f" + quote + string + quote

    def visit_formattedvalue(self, node) -> str:
        result = node.value.accept(self)
        if node.conversion and node.conversion >= 0:
            # e.g. if node.conversion == 114: result += "!r"
            result += "!" + chr(node.conversion)
        if node.format_spec:
            # The format spec is itself a JoinedString, i.e. an f-string
            # We strip the f and quotes of the ends
            result += ":" + node.format_spec.accept(self)[2:-1]
        return "{%s}" % result

    def handle_functiondef(self, node, keyword) -> str:
        """return a (possibly async) function definition node as string"""
        decorate = node.decorators.accept(self) if node.decorators else ""
        docs = self._docs_dedent(node.doc_node)
        trailer = ":"
        if node.returns:
            return_annotation = " -> " + node.returns.as_string()
            trailer = return_annotation + ":"
        def_format = "\n%s%s %s(%s)%s%s\n%s"
        return def_format % (
            decorate,
            keyword,
            node.name,
            node.args.accept(self),
            trailer,
            docs,
            self._stmt_list(node.body),
        )

    def visit_functiondef(self, node) -> str:
        """return an astroid.FunctionDef node as string"""
        return self.handle_functiondef(node, "def")

    def visit_asyncfunctiondef(self, node) -> str:
        """return an astroid.AsyncFunction node as string"""
        return self.handle_functiondef(node, "async def")

    def visit_generatorexp(self, node) -> str:
        """return an astroid.GeneratorExp node as string"""
        return "({} {})".format(
            node.elt.accept(self), " ".join(n.accept(self) for n in node.generators)
        )

    def visit_attribute(self, node) -> str:
        """return an astroid.Getattr node as string"""
        left = self._precedence_parens(node, node.expr)
        if left.isdigit():
            left = f"({left})"
        return f"{left}.{node.attrname}"

    def visit_global(self, node) -> str:
        """return an astroid.Global node as string"""
        return f"global {', '.join(node.names)}"

    def visit_if(self, node) -> str:
        """return an astroid.If node as string"""
        ifs = [f"if {node.test.accept(self)}:\n{self._stmt_list(node.body)}"]
        if node.has_elif_block():
            ifs.append(f"el{self._stmt_list(node.orelse, indent=False)}")
        elif node.orelse:
            ifs.append(f"else:\n{self._stmt_list(node.orelse)}")
        return "\n".join(ifs)

    def visit_ifexp(self, node) -> str:
        """return an astroid.IfExp node as string"""
        return "{} if {} else {}".format(
            self._precedence_parens(node, node.body, is_left=True),
            self._precedence_parens(node, node.test, is_left=True),
            self._precedence_parens(node, node.orelse, is_left=False),
        )

    def visit_import(self, node) -> str:
        """return an astroid.Import node as string"""
        return f"import {_import_string(node.names)}"

    def visit_keyword(self, node) -> str:
        """return an astroid.Keyword node as string"""
        if node.arg is None:
            return f"**{node.value.accept(self)}"
        return f"{node.arg}={node.value.accept(self)}"

    def visit_lambda(self, node) -> str:
        """return an astroid.Lambda node as string"""
        args = node.args.accept(self)
        body = node.body.accept(self)
        if args:
            return f"lambda {args}: {body}"

        return f"lambda: {body}"

    def visit_list(self, node) -> str:
        """return an astroid.List node as string"""
        return f"[{', '.join(child.accept(self) for child in node.elts)}]"

    def visit_listcomp(self, node) -> str:
        """return an astroid.ListComp node as string"""
        return "[{} {}]".format(
            node.elt.accept(self), " ".join(n.accept(self) for n in node.generators)
        )

    def visit_module(self, node) -> str:
        """return an astroid.Module node as string"""
        docs = f'"""{node.doc_node.value}"""\n\n' if node.doc_node else ""
        return docs + "\n".join(n.accept(self) for n in node.body) + "\n\n"

    def visit_name(self, node) -> str:
        """return an astroid.Name node as string"""
        return node.name

    def visit_namedexpr(self, node) -> str:
        """Return an assignment expression node as string"""
        target = node.target.accept(self)
        value = node.value.accept(self)
        return f"{target} := {value}"

    def visit_nonlocal(self, node) -> str:
        """return an astroid.Nonlocal node as string"""
        return f"nonlocal {', '.join(node.names)}"

    def visit_pass(self, node) -> str:
        """return an astroid.Pass node as string"""
        return "pass"

    def visit_raise(self, node) -> str:
        """return an astroid.Raise node as string"""
        if node.exc:
            if node.cause:
                return f"raise {node.exc.accept(self)} from {node.cause.accept(self)}"
            return f"raise {node.exc.accept(self)}"
        return "raise"

    def visit_return(self, node) -> str:
        """return an astroid.Return node as string"""
        if node.is_tuple_return() and len(node.value.elts) > 1:
            elts = [child.accept(self) for child in node.value.elts]
            return f"return {', '.join(elts)}"

        if node.value:
            return f"return {node.value.accept(self)}"

        return "return"

    def visit_set(self, node) -> str:
        """return an astroid.Set node as string"""
        return "{%s}" % ", ".join(child.accept(self) for child in node.elts)

    def visit_setcomp(self, node) -> str:
        """return an astroid.SetComp node as string"""
        return "{{{} {}}}".format(
            node.elt.accept(self), " ".join(n.accept(self) for n in node.generators)
        )

    def visit_slice(self, node) -> str:
        """return an astroid.Slice node as string"""
        lower = node.lower.accept(self) if node.lower else ""
        upper = node.upper.accept(self) if node.upper else ""
        step = node.step.accept(self) if node.step else ""
        if step:
            return f"{lower}:{upper}:{step}"
        return f"{lower}:{upper}"

    def visit_subscript(self, node) -> str:
        """return an astroid.Subscript node as string"""
        idx = node.slice
        if idx.__class__.__name__.lower() == "index":
            idx = idx.value
        idxstr = idx.accept(self)
        if idx.__class__.__name__.lower() == "tuple" and idx.elts:
            # Remove parenthesis in tuple and extended slice.
            # a[(::1, 1:)] is not valid syntax.
            idxstr = idxstr[1:-1]
        return f"{self._precedence_parens(node, node.value)}[{idxstr}]"

    def visit_tryexcept(self, node) -> str:
        """return an astroid.TryExcept node as string"""
        trys = [f"try:\n{self._stmt_list(node.body)}"]
        for handler in node.handlers:
            trys.append(handler.accept(self))
        if node.orelse:
            trys.append(f"else:\n{self._stmt_list(node.orelse)}")
        return "\n".join(trys)

    def visit_tryfinally(self, node) -> str:
        """return an astroid.TryFinally node as string"""
        return "try:\n{}\nfinally:\n{}".format(
            self._stmt_list(node.body), self._stmt_list(node.finalbody)
        )

    def visit_tuple(self, node) -> str:
        """return an astroid.Tuple node as string"""
        if len(node.elts) == 1:
            return f"({node.elts[0].accept(self)}, )"
        return f"({', '.join(child.accept(self) for child in node.elts)})"

    def visit_unaryop(self, node) -> str:
        """return an astroid.UnaryOp node as string"""
        if node.op == "not":
            operator = "not "
        else:
            operator = node.op
        return f"{operator}{self._precedence_parens(node, node.operand)}"

    def visit_while(self, node) -> str:
        """return an astroid.While node as string"""
        whiles = f"while {node.test.accept(self)}:\n{self._stmt_list(node.body)}"
        if node.orelse:
            whiles = f"{whiles}\nelse:\n{self._stmt_list(node.orelse)}"
        return whiles

    def visit_with(self, node) -> str:  # 'with' without 'as' is possible
        """return an astroid.With node as string"""
        items = ", ".join(
            f"{expr.accept(self)}" + (v and f" as {v.accept(self)}" or "")
            for expr, v in node.items
        )
        return f"with {items}:\n{self._stmt_list(node.body)}"

    def visit_yield(self, node) -> str:
        """yield an ast.Yield node as string"""
        yi_val = (" " + node.value.accept(self)) if node.value else ""
        expr = "yield" + yi_val
        if node.parent.is_statement:
            return expr

        return f"({expr})"

    def visit_yieldfrom(self, node) -> str:
        """Return an astroid.YieldFrom node as string."""
        yi_val = (" " + node.value.accept(self)) if node.value else ""
        expr = "yield from" + yi_val
        if node.parent.is_statement:
            return expr

        return f"({expr})"

    def visit_starred(self, node) -> str:
        """return Starred node as string"""
        return "*" + node.value.accept(self)

    def visit_match(self, node: Match) -> str:
        """Return an astroid.Match node as string."""
        return f"match {node.subject.accept(self)}:\n{self._stmt_list(node.cases)}"

    def visit_matchcase(self, node: MatchCase) -> str:
        """Return an astroid.MatchCase node as string."""
        guard_str = f" if {node.guard.accept(self)}" if node.guard else ""
        return (
            f"case {node.pattern.accept(self)}{guard_str}:\n"
            f"{self._stmt_list(node.body)}"
        )

    def visit_matchvalue(self, node: MatchValue) -> str:
        """Return an astroid.MatchValue node as string."""
        return node.value.accept(self)

    @staticmethod
    def visit_matchsingleton(node: MatchSingleton) -> str:
        """Return an astroid.MatchSingleton node as string."""
        return str(node.value)

    def visit_matchsequence(self, node: MatchSequence) -> str:
        """Return an astroid.MatchSequence node as string."""
        if node.patterns is None:
            return "[]"
        return f"[{', '.join(p.accept(self) for p in node.patterns)}]"

    def visit_matchmapping(self, node: MatchMapping) -> str:
        """Return an astroid.MatchMapping node as string."""
        mapping_strings: list[str] = []
        if node.keys and node.patterns:
            mapping_strings.extend(
                f"{key.accept(self)}: {p.accept(self)}"
                for key, p in zip(node.keys, node.patterns)
            )
        if node.rest:
            mapping_strings.append(f"**{node.rest.accept(self)}")
        return f"{'{'}{', '.join(mapping_strings)}{'}'}"

    def visit_matchclass(self, node: MatchClass) -> str:
        """Return an astroid.MatchClass node as string."""
        if node.cls is None:
            raise AssertionError(f"{node} does not have a 'cls' node")
        class_strings: list[str] = []
        if node.patterns:
            class_strings.extend(p.accept(self) for p in node.patterns)
        if node.kwd_attrs and node.kwd_patterns:
            for attr, pattern in zip(node.kwd_attrs, node.kwd_patterns):
                class_strings.append(f"{attr}={pattern.accept(self)}")
        return f"{node.cls.accept(self)}({', '.join(class_strings)})"

    def visit_matchstar(self, node: MatchStar) -> str:
        """Return an astroid.MatchStar node as string."""
        return f"*{node.name.accept(self) if node.name else '_'}"

    def visit_matchas(self, node: MatchAs) -> str:
        """Return an astroid.MatchAs node as string."""
        # pylint: disable=import-outside-toplevel
        # Prevent circular dependency
        from astroid.nodes.node_classes import MatchClass, MatchMapping, MatchSequence

        if isinstance(node.parent, (MatchSequence, MatchMapping, MatchClass)):
            return node.name.accept(self) if node.name else "_"
        return (
            f"{node.pattern.accept(self) if node.pattern else '_'}"
            f"{f' as {node.name.accept(self)}' if node.name else ''}"
        )

    def visit_matchor(self, node: MatchOr) -> str:
        """Return an astroid.MatchOr node as string."""
        if node.patterns is None:
            raise AssertionError(f"{node} does not have pattern nodes")
        return " | ".join(p.accept(self) for p in node.patterns)

    # These aren't for real AST nodes, but for inference objects.

    def visit_frozenset(self, node):
        return node.parent.accept(self)

    def visit_super(self, node):
        return node.parent.accept(self)

    def visit_uninferable(self, node):
        return str(node)

    def visit_property(self, node):
        return node.function.accept(self)

    def visit_evaluatedobject(self, node):
        return node.original.accept(self)

    def visit_unknown(self, node: Unknown) -> str:
        return str(node)


def _import_string(names) -> str:
    """return a list of (name, asname) formatted as a string"""
    _names = []
    for name, asname in names:
        if asname is not None:
            _names.append(f"{name} as {asname}")
        else:
            _names.append(name)
    return ", ".join(_names)


# This sets the default indent to 4 spaces.
to_code = AsStringVisitor("    ")
