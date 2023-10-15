# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import pprint
import sys
import warnings
from collections.abc import Generator, Iterator
from functools import singledispatch as _singledispatch
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)

from astroid import decorators, util
from astroid.context import InferenceContext
from astroid.exceptions import (
    AstroidError,
    InferenceError,
    ParentMissingError,
    StatementMissing,
    UseInferenceDefault,
)
from astroid.manager import AstroidManager
from astroid.nodes.as_string import AsStringVisitor
from astroid.nodes.const import OP_PRECEDENCE
from astroid.nodes.utils import Position
from astroid.typing import InferenceErrorInfo, InferenceResult, InferFn

if TYPE_CHECKING:
    from astroid import nodes

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal

if sys.version_info >= (3, 8):
    from functools import cached_property
else:
    from astroid.decorators import cachedproperty as cached_property

# Types for 'NodeNG.nodes_of_class()'
_NodesT = TypeVar("_NodesT", bound="NodeNG")
_NodesT2 = TypeVar("_NodesT2", bound="NodeNG")
_NodesT3 = TypeVar("_NodesT3", bound="NodeNG")
SkipKlassT = Union[None, Type["NodeNG"], Tuple[Type["NodeNG"], ...]]


class NodeNG:
    """A node of the new Abstract Syntax Tree (AST).

    This is the base class for all Astroid node classes.
    """

    is_statement: ClassVar[bool] = False
    """Whether this node indicates a statement."""
    optional_assign: ClassVar[
        bool
    ] = False  # True for For (and for Comprehension if py <3.0)
    """Whether this node optionally assigns a variable.

    This is for loop assignments because loop won't necessarily perform an
    assignment if the loop has no iterations.
    This is also the case from comprehensions in Python 2.
    """
    is_function: ClassVar[bool] = False  # True for FunctionDef nodes
    """Whether this node indicates a function."""
    is_lambda: ClassVar[bool] = False

    # Attributes below are set by the builder module or by raw factories
    _astroid_fields: ClassVar[tuple[str, ...]] = ()
    """Node attributes that contain child nodes.

    This is redefined in most concrete classes.
    """
    _other_fields: ClassVar[tuple[str, ...]] = ()
    """Node attributes that do not contain child nodes."""
    _other_other_fields: ClassVar[tuple[str, ...]] = ()
    """Attributes that contain AST-dependent fields."""
    # instance specific inference function infer(node, context)
    _explicit_inference: InferFn | None = None

    def __init__(
        self,
        lineno: int | None = None,
        col_offset: int | None = None,
        parent: NodeNG | None = None,
        *,
        end_lineno: int | None = None,
        end_col_offset: int | None = None,
    ) -> None:
        """
        :param lineno: The line that this node appears on in the source code.

        :param col_offset: The column that this node appears on in the
            source code.

        :param parent: The parent node in the syntax tree.

        :param end_lineno: The last line this node appears on in the source code.

        :param end_col_offset: The end column this node appears on in the
            source code. Note: This is after the last symbol.
        """
        self.lineno: int | None = lineno
        """The line that this node appears on in the source code."""

        self.col_offset: int | None = col_offset
        """The column that this node appears on in the source code."""

        self.parent: NodeNG | None = parent
        """The parent node in the syntax tree."""

        self.end_lineno: int | None = end_lineno
        """The last line this node appears on in the source code."""

        self.end_col_offset: int | None = end_col_offset
        """The end column this node appears on in the source code.

        Note: This is after the last symbol.
        """

        self.position: Position | None = None
        """Position of keyword(s) and name.

        Used as fallback for block nodes which might not provide good
        enough positional information. E.g. ClassDef, FunctionDef.
        """

    def infer(
        self, context: InferenceContext | None = None, **kwargs: Any
    ) -> Generator[InferenceResult, None, None]:
        """Get a generator of the inferred values.

        This is the main entry point to the inference system.

        .. seealso:: :ref:`inference`

        If the instance has some explicit inference function set, it will be
        called instead of the default interface.

        :returns: The inferred values.
        :rtype: iterable
        """
        if context is not None:
            context = context.extra_context.get(self, context)
        if self._explicit_inference is not None:
            # explicit_inference is not bound, give it self explicitly
            try:
                # pylint: disable=not-callable
                results = list(self._explicit_inference(self, context, **kwargs))
                if context is not None:
                    context.nodes_inferred += len(results)
                yield from results
                return
            except UseInferenceDefault:
                pass

        if not context:
            # nodes_inferred?
            yield from self._infer(context=context, **kwargs)
            return

        key = (self, context.lookupname, context.callcontext, context.boundnode)
        if key in context.inferred:
            yield from context.inferred[key]
            return

        results = []

        # Limit inference amount to help with performance issues with
        # exponentially exploding possible results.
        limit = AstroidManager.max_inferable_values
        for i, result in enumerate(self._infer(context=context, **kwargs)):
            if i >= limit or (context.nodes_inferred > context.max_inferred):
                results.append(util.Uninferable)
                yield util.Uninferable
                break
            results.append(result)
            yield result
            context.nodes_inferred += 1

        # Cache generated results for subsequent inferences of the
        # same node using the same context
        context.inferred[key] = tuple(results)
        return

    def _repr_name(self) -> str:
        """Get a name for nice representation.

        This is either :attr:`name`, :attr:`attrname`, or the empty string.

        :returns: The nice name.
        :rtype: str
        """
        if all(name not in self._astroid_fields for name in ("name", "attrname")):
            return getattr(self, "name", "") or getattr(self, "attrname", "")
        return ""

    def __str__(self) -> str:
        rname = self._repr_name()
        cname = type(self).__name__
        if rname:
            string = "%(cname)s.%(rname)s(%(fields)s)"
            alignment = len(cname) + len(rname) + 2
        else:
            string = "%(cname)s(%(fields)s)"
            alignment = len(cname) + 1
        result = []
        for field in self._other_fields + self._astroid_fields:
            value = getattr(self, field)
            width = 80 - len(field) - alignment
            lines = pprint.pformat(value, indent=2, width=width).splitlines(True)

            inner = [lines[0]]
            for line in lines[1:]:
                inner.append(" " * alignment + line)
            result.append(f"{field}={''.join(inner)}")

        return string % {
            "cname": cname,
            "rname": rname,
            "fields": (",\n" + " " * alignment).join(result),
        }

    def __repr__(self) -> str:
        rname = self._repr_name()
        if rname:
            string = "<%(cname)s.%(rname)s l.%(lineno)s at 0x%(id)x>"
        else:
            string = "<%(cname)s l.%(lineno)s at 0x%(id)x>"
        return string % {
            "cname": type(self).__name__,
            "rname": rname,
            "lineno": self.fromlineno,
            "id": id(self),
        }

    def accept(self, visitor):
        """Visit this node using the given visitor."""
        func = getattr(visitor, "visit_" + self.__class__.__name__.lower())
        return func(self)

    def get_children(self) -> Iterator[NodeNG]:
        """Get the child nodes below this node."""
        for field in self._astroid_fields:
            attr = getattr(self, field)
            if attr is None:
                continue
            if isinstance(attr, (list, tuple)):
                yield from attr
            else:
                yield attr
        yield from ()

    def last_child(self) -> NodeNG | None:
        """An optimized version of list(get_children())[-1]."""
        for field in self._astroid_fields[::-1]:
            attr = getattr(self, field)
            if not attr:  # None or empty list / tuple
                continue
            if isinstance(attr, (list, tuple)):
                return attr[-1]
            return attr
        return None

    def node_ancestors(self) -> Iterator[NodeNG]:
        """Yield parent, grandparent, etc until there are no more."""
        parent = self.parent
        while parent is not None:
            yield parent
            parent = parent.parent

    def parent_of(self, node) -> bool:
        """Check if this node is the parent of the given node.

        :param node: The node to check if it is the child.
        :type node: NodeNG

        :returns: Whether this node is the parent of the given node.
        """
        return any(self is parent for parent in node.node_ancestors())

    @overload
    def statement(self, *, future: None = ...) -> nodes.Statement | nodes.Module:
        ...

    @overload
    def statement(self, *, future: Literal[True]) -> nodes.Statement:
        ...

    def statement(
        self, *, future: Literal[None, True] = None
    ) -> nodes.Statement | nodes.Module:
        """The first parent node, including self, marked as statement node.

        TODO: Deprecate the future parameter and only raise StatementMissing and return
        nodes.Statement

        :raises AttributeError: If self has no parent attribute
        :raises StatementMissing: If self has no parent attribute and future is True
        """
        if self.is_statement:
            return cast("nodes.Statement", self)
        if not self.parent:
            if future:
                raise StatementMissing(target=self)
            warnings.warn(
                "In astroid 3.0.0 NodeNG.statement() will return either a nodes.Statement "
                "or raise a StatementMissing exception. AttributeError will no longer be raised. "
                "This behaviour can already be triggered "
                "by passing 'future=True' to a statement() call.",
                DeprecationWarning,
                stacklevel=2,
            )
            raise AttributeError(f"{self} object has no attribute 'parent'")
        return self.parent.statement(future=future)

    def frame(
        self, *, future: Literal[None, True] = None
    ) -> nodes.FunctionDef | nodes.Module | nodes.ClassDef | nodes.Lambda:
        """The first parent frame node.

        A frame node is a :class:`Module`, :class:`FunctionDef`,
        :class:`ClassDef` or :class:`Lambda`.

        :returns: The first parent frame node.
        """
        if self.parent is None:
            if future:
                raise ParentMissingError(target=self)
            warnings.warn(
                "In astroid 3.0.0 NodeNG.frame() will return either a Frame node, "
                "or raise ParentMissingError. AttributeError will no longer be raised. "
                "This behaviour can already be triggered "
                "by passing 'future=True' to a frame() call.",
                DeprecationWarning,
                stacklevel=2,
            )
            raise AttributeError(f"{self} object has no attribute 'parent'")

        return self.parent.frame(future=future)

    def scope(self) -> nodes.LocalsDictNodeNG:
        """The first parent node defining a new scope.

        These can be Module, FunctionDef, ClassDef, Lambda, or GeneratorExp nodes.

        :returns: The first parent scope node.
        """
        if not self.parent:
            raise ParentMissingError(target=self)
        return self.parent.scope()

    def root(self) -> nodes.Module:
        """Return the root node of the syntax tree.

        :returns: The root node.
        """
        if self.parent:
            return self.parent.root()
        return self  # type: ignore[return-value] # Only 'Module' does not have a parent node.

    def child_sequence(self, child):
        """Search for the sequence that contains this child.

        :param child: The child node to search sequences for.
        :type child: NodeNG

        :returns: The sequence containing the given child node.
        :rtype: iterable(NodeNG)

        :raises AstroidError: If no sequence could be found that contains
            the given child.
        """
        for field in self._astroid_fields:
            node_or_sequence = getattr(self, field)
            if node_or_sequence is child:
                return [node_or_sequence]
            # /!\ compiler.ast Nodes have an __iter__ walking over child nodes
            if (
                isinstance(node_or_sequence, (tuple, list))
                and child in node_or_sequence
            ):
                return node_or_sequence

        msg = "Could not find %s in %s's children"
        raise AstroidError(msg % (repr(child), repr(self)))

    def locate_child(self, child):
        """Find the field of this node that contains the given child.

        :param child: The child node to search fields for.
        :type child: NodeNG

        :returns: A tuple of the name of the field that contains the child,
            and the sequence or node that contains the child node.
        :rtype: tuple(str, iterable(NodeNG) or NodeNG)

        :raises AstroidError: If no field could be found that contains
            the given child.
        """
        for field in self._astroid_fields:
            node_or_sequence = getattr(self, field)
            # /!\ compiler.ast Nodes have an __iter__ walking over child nodes
            if child is node_or_sequence:
                return field, child
            if (
                isinstance(node_or_sequence, (tuple, list))
                and child in node_or_sequence
            ):
                return field, node_or_sequence
        msg = "Could not find %s in %s's children"
        raise AstroidError(msg % (repr(child), repr(self)))

    # FIXME : should we merge child_sequence and locate_child ? locate_child
    # is only used in are_exclusive, child_sequence one time in pylint.

    def next_sibling(self):
        """The next sibling statement node.

        :returns: The next sibling statement node.
        :rtype: NodeNG or None
        """
        return self.parent.next_sibling()

    def previous_sibling(self):
        """The previous sibling statement.

        :returns: The previous sibling statement node.
        :rtype: NodeNG or None
        """
        return self.parent.previous_sibling()

    # these are lazy because they're relatively expensive to compute for every
    # single node, and they rarely get looked at

    @cached_property
    def fromlineno(self) -> int | None:
        """The first line that this node appears on in the source code."""
        if self.lineno is None:
            return self._fixed_source_line()
        return self.lineno

    @cached_property
    def tolineno(self) -> int | None:
        """The last line that this node appears on in the source code."""
        if self.end_lineno is not None:
            return self.end_lineno
        if not self._astroid_fields:
            # can't have children
            last_child = None
        else:
            last_child = self.last_child()
        if last_child is None:
            return self.fromlineno
        return last_child.tolineno

    def _fixed_source_line(self) -> int | None:
        """Attempt to find the line that this node appears on.

        We need this method since not all nodes have :attr:`lineno` set.
        """
        line = self.lineno
        _node = self
        try:
            while line is None:
                _node = next(_node.get_children())
                line = _node.lineno
        except StopIteration:
            parent = self.parent
            while parent and line is None:
                line = parent.lineno
                parent = parent.parent
        return line

    def block_range(self, lineno):
        """Get a range from the given line number to where this node ends.

        :param lineno: The line number to start the range at.
        :type lineno: int

        :returns: The range of line numbers that this node belongs to,
            starting at the given line number.
        :rtype: tuple(int, int or None)
        """
        return lineno, self.tolineno

    def set_local(self, name: str, stmt: NodeNG) -> None:
        """Define that the given name is declared in the given statement node.

        This definition is stored on the parent scope node.

        .. seealso:: :meth:`scope`

        :param name: The name that is being defined.

        :param stmt: The statement that defines the given name.
        """
        assert self.parent
        self.parent.set_local(name, stmt)

    @overload
    def nodes_of_class(
        self,
        klass: type[_NodesT],
        skip_klass: SkipKlassT = ...,
    ) -> Iterator[_NodesT]:
        ...

    @overload
    def nodes_of_class(
        self,
        klass: tuple[type[_NodesT], type[_NodesT2]],
        skip_klass: SkipKlassT = ...,
    ) -> Iterator[_NodesT] | Iterator[_NodesT2]:
        ...

    @overload
    def nodes_of_class(
        self,
        klass: tuple[type[_NodesT], type[_NodesT2], type[_NodesT3]],
        skip_klass: SkipKlassT = ...,
    ) -> Iterator[_NodesT] | Iterator[_NodesT2] | Iterator[_NodesT3]:
        ...

    @overload
    def nodes_of_class(
        self,
        klass: tuple[type[_NodesT], ...],
        skip_klass: SkipKlassT = ...,
    ) -> Iterator[_NodesT]:
        ...

    def nodes_of_class(  # type: ignore[misc] # mypy doesn't correctly recognize the overloads
        self,
        klass: (
            type[_NodesT]
            | tuple[type[_NodesT], type[_NodesT2]]
            | tuple[type[_NodesT], type[_NodesT2], type[_NodesT3]]
            | tuple[type[_NodesT], ...]
        ),
        skip_klass: SkipKlassT = None,
    ) -> Iterator[_NodesT] | Iterator[_NodesT2] | Iterator[_NodesT3]:
        """Get the nodes (including this one or below) of the given types.

        :param klass: The types of node to search for.

        :param skip_klass: The types of node to ignore. This is useful to ignore
            subclasses of :attr:`klass`.

        :returns: The node of the given types.
        """
        if isinstance(self, klass):
            yield self

        if skip_klass is None:
            for child_node in self.get_children():
                yield from child_node.nodes_of_class(klass, skip_klass)

            return

        for child_node in self.get_children():
            if isinstance(child_node, skip_klass):
                continue
            yield from child_node.nodes_of_class(klass, skip_klass)

    @decorators.cached
    def _get_assign_nodes(self):
        return []

    def _get_name_nodes(self):
        for child_node in self.get_children():
            yield from child_node._get_name_nodes()

    def _get_return_nodes_skip_functions(self):
        yield from ()

    def _get_yield_nodes_skip_lambdas(self):
        yield from ()

    def _infer_name(self, frame, name):
        # overridden for ImportFrom, Import, Global, TryExcept and Arguments
        pass

    def _infer(
        self, context: InferenceContext | None = None, **kwargs: Any
    ) -> Generator[InferenceResult, None, InferenceErrorInfo | None]:
        """We don't know how to resolve a statement by default."""
        # this method is overridden by most concrete classes
        raise InferenceError(
            "No inference function for {node!r}.", node=self, context=context
        )

    def inferred(self):
        """Get a list of the inferred values.

        .. seealso:: :ref:`inference`

        :returns: The inferred values.
        :rtype: list
        """
        return list(self.infer())

    def instantiate_class(self):
        """Instantiate an instance of the defined class.

        .. note::

            On anything other than a :class:`ClassDef` this will return self.

        :returns: An instance of the defined class.
        :rtype: object
        """
        return self

    def has_base(self, node) -> bool:
        """Check if this node inherits from the given type.

        :param node: The node defining the base to look for.
            Usually this is a :class:`Name` node.
        :type node: NodeNG
        """
        return False

    def callable(self) -> bool:
        """Whether this node defines something that is callable.

        :returns: Whether this defines something that is callable.
        """
        return False

    def eq(self, value) -> bool:
        return False

    def as_string(self) -> str:
        """Get the source code that this node represents."""
        return AsStringVisitor()(self)

    def repr_tree(
        self,
        ids=False,
        include_linenos=False,
        ast_state=False,
        indent="   ",
        max_depth=0,
        max_width=80,
    ) -> str:
        """Get a string representation of the AST from this node.

        :param ids: If true, includes the ids with the node type names.
        :type ids: bool

        :param include_linenos: If true, includes the line numbers and
            column offsets.
        :type include_linenos: bool

        :param ast_state: If true, includes information derived from
            the whole AST like local and global variables.
        :type ast_state: bool

        :param indent: A string to use to indent the output string.
        :type indent: str

        :param max_depth: If set to a positive integer, won't return
            nodes deeper than max_depth in the string.
        :type max_depth: int

        :param max_width: Attempt to format the output string to stay
            within this number of characters, but can exceed it under some
            circumstances. Only positive integer values are valid, the default is 80.
        :type max_width: int

        :returns: The string representation of the AST.
        :rtype: str
        """

        @_singledispatch
        def _repr_tree(node, result, done, cur_indent="", depth=1):
            """Outputs a representation of a non-tuple/list, non-node that's
            contained within an AST, including strings.
            """
            lines = pprint.pformat(
                node, width=max(max_width - len(cur_indent), 1)
            ).splitlines(True)
            result.append(lines[0])
            result.extend([cur_indent + line for line in lines[1:]])
            return len(lines) != 1

        # pylint: disable=unused-variable,useless-suppression; doesn't understand singledispatch
        @_repr_tree.register(tuple)
        @_repr_tree.register(list)
        def _repr_seq(node, result, done, cur_indent="", depth=1):
            """Outputs a representation of a sequence that's contained within an
            AST.
            """
            cur_indent += indent
            result.append("[")
            if not node:
                broken = False
            elif len(node) == 1:
                broken = _repr_tree(node[0], result, done, cur_indent, depth)
            elif len(node) == 2:
                broken = _repr_tree(node[0], result, done, cur_indent, depth)
                if not broken:
                    result.append(", ")
                else:
                    result.append(",\n")
                    result.append(cur_indent)
                broken = _repr_tree(node[1], result, done, cur_indent, depth) or broken
            else:
                result.append("\n")
                result.append(cur_indent)
                for child in node[:-1]:
                    _repr_tree(child, result, done, cur_indent, depth)
                    result.append(",\n")
                    result.append(cur_indent)
                _repr_tree(node[-1], result, done, cur_indent, depth)
                broken = True
            result.append("]")
            return broken

        # pylint: disable=unused-variable,useless-suppression; doesn't understand singledispatch
        @_repr_tree.register(NodeNG)
        def _repr_node(node, result, done, cur_indent="", depth=1):
            """Outputs a strings representation of an astroid node."""
            if node in done:
                result.append(
                    indent + f"<Recursion on {type(node).__name__} with id={id(node)}"
                )
                return False
            done.add(node)

            if max_depth and depth > max_depth:
                result.append("...")
                return False
            depth += 1
            cur_indent += indent
            if ids:
                result.append(f"{type(node).__name__}<0x{id(node):x}>(\n")
            else:
                result.append(f"{type(node).__name__}(")
            fields = []
            if include_linenos:
                fields.extend(("lineno", "col_offset"))
            fields.extend(node._other_fields)
            fields.extend(node._astroid_fields)
            if ast_state:
                fields.extend(node._other_other_fields)
            if not fields:
                broken = False
            elif len(fields) == 1:
                result.append(f"{fields[0]}=")
                broken = _repr_tree(
                    getattr(node, fields[0]), result, done, cur_indent, depth
                )
            else:
                result.append("\n")
                result.append(cur_indent)
                for field in fields[:-1]:
                    # TODO: Remove this after removal of the 'doc' attribute
                    if field == "doc":
                        continue
                    result.append(f"{field}=")
                    _repr_tree(getattr(node, field), result, done, cur_indent, depth)
                    result.append(",\n")
                    result.append(cur_indent)
                result.append(f"{fields[-1]}=")
                _repr_tree(getattr(node, fields[-1]), result, done, cur_indent, depth)
                broken = True
            result.append(")")
            return broken

        result: list[str] = []
        _repr_tree(self, result, set())
        return "".join(result)

    def bool_value(self, context: InferenceContext | None = None):
        """Determine the boolean value of this node.

        The boolean value of a node can have three
        possible values:

            * False: For instance, empty data structures,
              False, empty strings, instances which return
              explicitly False from the __nonzero__ / __bool__
              method.
            * True: Most of constructs are True by default:
              classes, functions, modules etc
            * Uninferable: The inference engine is uncertain of the
              node's value.

        :returns: The boolean value of this node.
        :rtype: bool or Uninferable
        """
        return util.Uninferable

    def op_precedence(self):
        # Look up by class name or default to highest precedence
        return OP_PRECEDENCE.get(self.__class__.__name__, len(OP_PRECEDENCE))

    def op_left_associative(self) -> Literal[True]:
        # Everything is left associative except `**` and IfExp
        return True
