# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

import astroid.bases
from astroid import nodes

from pylint.checkers import BaseChecker
from pylint.checkers.utils import (
    in_type_checking_block,
    is_node_in_type_annotation_context,
    is_postponed_evaluation_enabled,
    only_required_for_messages,
    safe_infer,
)
from pylint.constants import TYPING_NORETURN
from pylint.interfaces import HIGH, INFERENCE

if TYPE_CHECKING:
    from pylint.lint import PyLinter


class TypingAlias(NamedTuple):
    name: str
    name_collision: bool


DEPRECATED_TYPING_ALIASES: dict[str, TypingAlias] = {
    "typing.Tuple": TypingAlias("tuple", False),
    "typing.List": TypingAlias("list", False),
    "typing.Dict": TypingAlias("dict", False),
    "typing.Set": TypingAlias("set", False),
    "typing.FrozenSet": TypingAlias("frozenset", False),
    "typing.Type": TypingAlias("type", False),
    "typing.Deque": TypingAlias("collections.deque", True),
    "typing.DefaultDict": TypingAlias("collections.defaultdict", True),
    "typing.OrderedDict": TypingAlias("collections.OrderedDict", True),
    "typing.Counter": TypingAlias("collections.Counter", True),
    "typing.ChainMap": TypingAlias("collections.ChainMap", True),
    "typing.Awaitable": TypingAlias("collections.abc.Awaitable", True),
    "typing.Coroutine": TypingAlias("collections.abc.Coroutine", True),
    "typing.AsyncIterable": TypingAlias("collections.abc.AsyncIterable", True),
    "typing.AsyncIterator": TypingAlias("collections.abc.AsyncIterator", True),
    "typing.AsyncGenerator": TypingAlias("collections.abc.AsyncGenerator", True),
    "typing.Iterable": TypingAlias("collections.abc.Iterable", True),
    "typing.Iterator": TypingAlias("collections.abc.Iterator", True),
    "typing.Generator": TypingAlias("collections.abc.Generator", True),
    "typing.Reversible": TypingAlias("collections.abc.Reversible", True),
    "typing.Container": TypingAlias("collections.abc.Container", True),
    "typing.Collection": TypingAlias("collections.abc.Collection", True),
    "typing.Callable": TypingAlias("collections.abc.Callable", True),
    "typing.AbstractSet": TypingAlias("collections.abc.Set", False),
    "typing.MutableSet": TypingAlias("collections.abc.MutableSet", True),
    "typing.Mapping": TypingAlias("collections.abc.Mapping", True),
    "typing.MutableMapping": TypingAlias("collections.abc.MutableMapping", True),
    "typing.Sequence": TypingAlias("collections.abc.Sequence", True),
    "typing.MutableSequence": TypingAlias("collections.abc.MutableSequence", True),
    "typing.ByteString": TypingAlias("collections.abc.ByteString", True),
    "typing.MappingView": TypingAlias("collections.abc.MappingView", True),
    "typing.KeysView": TypingAlias("collections.abc.KeysView", True),
    "typing.ItemsView": TypingAlias("collections.abc.ItemsView", True),
    "typing.ValuesView": TypingAlias("collections.abc.ValuesView", True),
    "typing.ContextManager": TypingAlias("contextlib.AbstractContextManager", False),
    "typing.AsyncContextManager": TypingAlias(
        "contextlib.AbstractAsyncContextManager", False
    ),
    "typing.Pattern": TypingAlias("re.Pattern", True),
    "typing.Match": TypingAlias("re.Match", True),
    "typing.Hashable": TypingAlias("collections.abc.Hashable", True),
    "typing.Sized": TypingAlias("collections.abc.Sized", True),
}

ALIAS_NAMES = frozenset(key.split(".")[1] for key in DEPRECATED_TYPING_ALIASES)
UNION_NAMES = ("Optional", "Union")


class DeprecatedTypingAliasMsg(NamedTuple):
    node: nodes.Name | nodes.Attribute
    qname: str
    alias: str
    parent_subscript: bool = False


class TypingChecker(BaseChecker):
    """Find issue specifically related to type annotations."""

    name = "typing"
    msgs = {
        "W6001": (
            "'%s' is deprecated, use '%s' instead",
            "deprecated-typing-alias",
            "Emitted when a deprecated typing alias is used.",
        ),
        "R6002": (
            "'%s' will be deprecated with PY39, consider using '%s' instead%s",
            "consider-using-alias",
            "Only emitted if 'runtime-typing=no' and a deprecated "
            "typing alias is used in a type annotation context in "
            "Python 3.7 or 3.8.",
        ),
        "R6003": (
            "Consider using alternative Union syntax instead of '%s'%s",
            "consider-alternative-union-syntax",
            "Emitted when 'typing.Union' or 'typing.Optional' is used "
            "instead of the alternative Union syntax 'int | None'.",
        ),
        "E6004": (
            "'NoReturn' inside compound types is broken in 3.7.0 / 3.7.1",
            "broken-noreturn",
            "``typing.NoReturn`` inside compound types is broken in "
            "Python 3.7.0 and 3.7.1. If not dependent on runtime introspection, "
            "use string annotation instead. E.g. "
            "``Callable[..., 'NoReturn']``. https://bugs.python.org/issue34921",
        ),
        "E6005": (
            "'collections.abc.Callable' inside Optional and Union is broken in "
            "3.9.0 / 3.9.1 (use 'typing.Callable' instead)",
            "broken-collections-callable",
            "``collections.abc.Callable`` inside Optional and Union is broken in "
            "Python 3.9.0 and 3.9.1. Use ``typing.Callable`` for these cases instead. "
            "https://bugs.python.org/issue42965",
        ),
        "R6006": (
            "Type `%s` is used more than once in union type annotation. Remove redundant typehints.",
            "redundant-typehint-argument",
            "Duplicated type arguments will be skipped by `mypy` tool, therefore should be "
            "removed to avoid confusion.",
        ),
    }
    options = (
        (
            "runtime-typing",
            {
                "default": True,
                "type": "yn",
                "metavar": "<y or n>",
                "help": (
                    "Set to ``no`` if the app / library does **NOT** need to "
                    "support runtime introspection of type annotations. "
                    "If you use type annotations **exclusively** for type checking "
                    "of an application, you're probably fine. For libraries, "
                    "evaluate if some users want to access the type hints "
                    "at runtime first, e.g., through ``typing.get_type_hints``. "
                    "Applies to Python versions 3.7 - 3.9"
                ),
            },
        ),
    )

    _should_check_typing_alias: bool
    """The use of type aliases (PEP 585) requires Python 3.9
    or Python 3.7+ with postponed evaluation.
    """

    _should_check_alternative_union_syntax: bool
    """The use of alternative union syntax (PEP 604) requires Python 3.10
    or Python 3.7+ with postponed evaluation.
    """

    def __init__(self, linter: PyLinter) -> None:
        """Initialize checker instance."""
        super().__init__(linter=linter)
        self._found_broken_callable_location: bool = False
        self._alias_name_collisions: set[str] = set()
        self._deprecated_typing_alias_msgs: list[DeprecatedTypingAliasMsg] = []
        self._consider_using_alias_msgs: list[DeprecatedTypingAliasMsg] = []

    def open(self) -> None:
        py_version = self.linter.config.py_version
        self._py37_plus = py_version >= (3, 7)
        self._py39_plus = py_version >= (3, 9)
        self._py310_plus = py_version >= (3, 10)

        self._should_check_typing_alias = self._py39_plus or (
            self._py37_plus and self.linter.config.runtime_typing is False
        )
        self._should_check_alternative_union_syntax = self._py310_plus or (
            self._py37_plus and self.linter.config.runtime_typing is False
        )

        self._should_check_noreturn = py_version < (3, 7, 2)
        self._should_check_callable = py_version < (3, 9, 2)

    def _msg_postponed_eval_hint(self, node: nodes.NodeNG) -> str:
        """Message hint if postponed evaluation isn't enabled."""
        if self._py310_plus or "annotations" in node.root().future_imports:
            return ""
        return ". Add 'from __future__ import annotations' as well"

    @only_required_for_messages(
        "deprecated-typing-alias",
        "consider-using-alias",
        "consider-alternative-union-syntax",
        "broken-noreturn",
        "broken-collections-callable",
    )
    def visit_name(self, node: nodes.Name) -> None:
        if self._should_check_typing_alias and node.name in ALIAS_NAMES:
            self._check_for_typing_alias(node)
        if self._should_check_alternative_union_syntax and node.name in UNION_NAMES:
            self._check_for_alternative_union_syntax(node, node.name)
        if self._should_check_noreturn and node.name == "NoReturn":
            self._check_broken_noreturn(node)
        if self._should_check_callable and node.name == "Callable":
            self._check_broken_callable(node)

    @only_required_for_messages(
        "deprecated-typing-alias",
        "consider-using-alias",
        "consider-alternative-union-syntax",
        "broken-noreturn",
        "broken-collections-callable",
    )
    def visit_attribute(self, node: nodes.Attribute) -> None:
        if self._should_check_typing_alias and node.attrname in ALIAS_NAMES:
            self._check_for_typing_alias(node)
        if self._should_check_alternative_union_syntax and node.attrname in UNION_NAMES:
            self._check_for_alternative_union_syntax(node, node.attrname)
        if self._should_check_noreturn and node.attrname == "NoReturn":
            self._check_broken_noreturn(node)
        if self._should_check_callable and node.attrname == "Callable":
            self._check_broken_callable(node)

    @only_required_for_messages("redundant-typehint-argument")
    def visit_annassign(self, node: nodes.AnnAssign) -> None:
        annotation = node.annotation
        if self._is_deprecated_union_annotation(annotation, "Optional"):
            if self._is_optional_none_annotation(annotation):
                self.add_message(
                    "redundant-typehint-argument",
                    node=annotation,
                    args="None",
                    confidence=HIGH,
                )
            return
        if self._is_deprecated_union_annotation(annotation, "Union") and isinstance(
            annotation.slice, nodes.Tuple
        ):
            types = annotation.slice.elts
        elif self._is_binop_union_annotation(annotation):
            types = self._parse_binops_typehints(annotation)
        else:
            return

        self._check_union_types(types, node)

    @staticmethod
    def _is_deprecated_union_annotation(
        annotation: nodes.NodeNG, union_name: str
    ) -> bool:
        return (
            isinstance(annotation, nodes.Subscript)
            and isinstance(annotation.value, nodes.Name)
            and annotation.value.name == union_name
        )

    def _is_binop_union_annotation(self, annotation: nodes.NodeNG) -> bool:
        return self._should_check_alternative_union_syntax and isinstance(
            annotation, nodes.BinOp
        )

    @staticmethod
    def _is_optional_none_annotation(annotation: nodes.Subscript) -> bool:
        return (
            isinstance(annotation.slice, nodes.Const) and annotation.slice.value is None
        )

    def _parse_binops_typehints(
        self, binop_node: nodes.BinOp, typehints_list: list[nodes.NodeNG] | None = None
    ) -> list[nodes.NodeNG]:
        typehints_list = typehints_list or []
        if isinstance(binop_node.left, nodes.BinOp):
            typehints_list.extend(
                self._parse_binops_typehints(binop_node.left, typehints_list)
            )
        else:
            typehints_list.append(binop_node.left)
        typehints_list.append(binop_node.right)
        return typehints_list

    def _check_union_types(
        self, types: list[nodes.NodeNG], annotation: nodes.NodeNG
    ) -> None:
        types_set = set()
        for typehint in types:
            typehint_str = typehint.as_string()
            if typehint_str in types_set:
                self.add_message(
                    "redundant-typehint-argument",
                    node=annotation,
                    args=(typehint_str),
                    confidence=HIGH,
                )
            else:
                types_set.add(typehint_str)

    def _check_for_alternative_union_syntax(
        self,
        node: nodes.Name | nodes.Attribute,
        name: str,
    ) -> None:
        """Check if alternative union syntax could be used.

        Requires
        - Python 3.10
        - OR: Python 3.7+ with postponed evaluation in
              a type annotation context
        """
        inferred = safe_infer(node)
        if not (
            isinstance(inferred, nodes.FunctionDef)
            and inferred.qname() in {"typing.Optional", "typing.Union"}
            or isinstance(inferred, astroid.bases.Instance)
            and inferred.qname() == "typing._SpecialForm"
        ):
            return
        if not (self._py310_plus or is_node_in_type_annotation_context(node)):
            return
        self.add_message(
            "consider-alternative-union-syntax",
            node=node,
            args=(name, self._msg_postponed_eval_hint(node)),
            confidence=INFERENCE,
        )

    def _check_for_typing_alias(
        self,
        node: nodes.Name | nodes.Attribute,
    ) -> None:
        """Check if typing alias is deprecated or could be replaced.

        Requires
        - Python 3.9
        - OR: Python 3.7+ with postponed evaluation in
              a type annotation context

        For Python 3.7+: Only emit message if change doesn't create
            any name collisions, only ever used in a type annotation
            context, and can safely be replaced.
        """
        inferred = safe_infer(node)
        if not isinstance(inferred, nodes.ClassDef):
            return
        alias = DEPRECATED_TYPING_ALIASES.get(inferred.qname(), None)
        if alias is None:
            return

        if self._py39_plus:
            if inferred.qname() == "typing.Callable" and self._broken_callable_location(
                node
            ):
                self._found_broken_callable_location = True
            self._deprecated_typing_alias_msgs.append(
                DeprecatedTypingAliasMsg(
                    node,
                    inferred.qname(),
                    alias.name,
                )
            )
            return

        # For PY37+, check for type annotation context first
        if not is_node_in_type_annotation_context(node) and isinstance(
            node.parent, nodes.Subscript
        ):
            if alias.name_collision is True:
                self._alias_name_collisions.add(inferred.qname())
            return
        self._consider_using_alias_msgs.append(
            DeprecatedTypingAliasMsg(
                node,
                inferred.qname(),
                alias.name,
                isinstance(node.parent, nodes.Subscript),
            )
        )

    @only_required_for_messages("consider-using-alias", "deprecated-typing-alias")
    def leave_module(self, node: nodes.Module) -> None:
        """After parsing of module is complete, add messages for
        'consider-using-alias' check.

        Make sure results are safe to recommend / collision free.
        """
        if self._py39_plus:
            for msg in self._deprecated_typing_alias_msgs:
                if (
                    self._found_broken_callable_location
                    and msg.qname == "typing.Callable"
                ):
                    continue
                self.add_message(
                    "deprecated-typing-alias",
                    node=msg.node,
                    args=(msg.qname, msg.alias),
                    confidence=INFERENCE,
                )

        elif self._py37_plus:
            msg_future_import = self._msg_postponed_eval_hint(node)
            for msg in self._consider_using_alias_msgs:
                if msg.qname in self._alias_name_collisions:
                    continue
                self.add_message(
                    "consider-using-alias",
                    node=msg.node,
                    args=(
                        msg.qname,
                        msg.alias,
                        msg_future_import if msg.parent_subscript else "",
                    ),
                    confidence=INFERENCE,
                )

        # Clear all module cache variables
        self._found_broken_callable_location = False
        self._deprecated_typing_alias_msgs.clear()
        self._alias_name_collisions.clear()
        self._consider_using_alias_msgs.clear()

    def _check_broken_noreturn(self, node: nodes.Name | nodes.Attribute) -> None:
        """Check for 'NoReturn' inside compound types."""
        if not isinstance(node.parent, nodes.BaseContainer):
            # NoReturn not part of a Union or Callable type
            return

        if (
            in_type_checking_block(node)
            or is_postponed_evaluation_enabled(node)
            and is_node_in_type_annotation_context(node)
        ):
            return

        for inferred in node.infer():
            # To deal with typing_extensions, don't use safe_infer
            if (
                isinstance(inferred, (nodes.FunctionDef, nodes.ClassDef))
                and inferred.qname() in TYPING_NORETURN
                # In Python 3.7 - 3.8, NoReturn is alias of '_SpecialForm'
                or isinstance(inferred, astroid.bases.BaseInstance)
                and isinstance(inferred._proxied, nodes.ClassDef)
                and inferred._proxied.qname() == "typing._SpecialForm"
            ):
                self.add_message("broken-noreturn", node=node, confidence=INFERENCE)
                break

    def _check_broken_callable(self, node: nodes.Name | nodes.Attribute) -> None:
        """Check for 'collections.abc.Callable' inside Optional and Union."""
        inferred = safe_infer(node)
        if not (
            isinstance(inferred, nodes.ClassDef)
            and inferred.qname() == "_collections_abc.Callable"
            and self._broken_callable_location(node)
        ):
            return

        self.add_message("broken-collections-callable", node=node, confidence=INFERENCE)

    def _broken_callable_location(self, node: nodes.Name | nodes.Attribute) -> bool:
        """Check if node would be a broken location for collections.abc.Callable."""
        if (
            in_type_checking_block(node)
            or is_postponed_evaluation_enabled(node)
            and is_node_in_type_annotation_context(node)
        ):
            return False

        # Check first Callable arg is a list of arguments -> Callable[[int], None]
        if not (
            isinstance(node.parent, nodes.Subscript)
            and isinstance(node.parent.slice, nodes.Tuple)
            and len(node.parent.slice.elts) == 2
            and isinstance(node.parent.slice.elts[0], nodes.List)
        ):
            return False

        # Check nested inside Optional or Union
        parent_subscript = node.parent.parent
        if isinstance(parent_subscript, nodes.BaseContainer):
            parent_subscript = parent_subscript.parent
        if not (
            isinstance(parent_subscript, nodes.Subscript)
            and isinstance(parent_subscript.value, (nodes.Name, nodes.Attribute))
        ):
            return False

        inferred_parent = safe_infer(parent_subscript.value)
        if not (
            isinstance(inferred_parent, nodes.FunctionDef)
            and inferred_parent.qname() in {"typing.Optional", "typing.Union"}
            or isinstance(inferred_parent, astroid.bases.Instance)
            and inferred_parent.qname() == "typing._SpecialForm"
        ):
            return False

        return True


def register(linter: PyLinter) -> None:
    linter.register_checker(TypingChecker(linter))
