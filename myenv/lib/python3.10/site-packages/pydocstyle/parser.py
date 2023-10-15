"""Python code parser."""

import sys
import textwrap
import tokenize as tk
from io import StringIO
from itertools import chain, dropwhile
from pathlib import Path
from re import compile as re
from typing import Tuple

from .utils import log

__all__ = (
    'Parser',
    'Definition',
    'Module',
    'Package',
    'Function',
    'NestedFunction',
    'Method',
    'Class',
    'NestedClass',
    'AllError',
    'StringIO',
    'ParseError',
)


class ParseError(Exception):
    """An error parsing contents of a Python file."""

    def __str__(self):
        return "Cannot parse file."


class UnexpectedTokenError(ParseError):
    def __init__(self, token, expected_kind):
        self.token = token
        self.expected_kind = expected_kind

    def __str__(self):
        return "Unexpected token {}, expected {}".format(
            self.token, self.expected_kind
        )


def humanize(string):
    return re(r'(.)([A-Z]+)').sub(r'\1 \2', string).lower()


class Value:
    """A generic object with a list of preset fields."""

    def __init__(self, *args):
        if len(self._fields) != len(args):
            raise ValueError(
                'got {} arguments for {} fields for {}: {}'.format(
                    len(args),
                    len(self._fields),
                    self.__class__.__name__,
                    self._fields,
                )
            )
        vars(self).update(zip(self._fields, args))

    def __hash__(self):
        return hash(repr(self))

    def __eq__(self, other):
        return other and vars(self) == vars(other)

    def __repr__(self):
        kwargs = ', '.join(
            '{}={!r}'.format(field, getattr(self, field))
            for field in self._fields
        )
        return f'{self.__class__.__name__}({kwargs})'


class Definition(Value):
    """A Python source code definition (could be class, function, etc)."""

    _fields = (
        'name',
        '_source',
        'start',
        'end',
        'decorators',
        'docstring',
        'children',
        'parent',
        'skipped_error_codes',
    )  # type: Tuple[str, ...]

    _human = property(lambda self: humanize(type(self).__name__))
    kind = property(lambda self: self._human.split()[-1])
    module = property(lambda self: self.parent.module)
    dunder_all = property(lambda self: self.module.dunder_all)
    _slice = property(lambda self: slice(self.start - 1, self.end))
    is_class = False

    def __iter__(self):
        return chain([self], *self.children)

    @property
    def error_lineno(self):
        """Get the line number with which to report violations."""
        if isinstance(self.docstring, Docstring):
            return self.docstring.start
        return self.start

    @property
    def _publicity(self):
        return {True: 'public', False: 'private'}[self.is_public]

    @property
    def source(self):
        """Return the source code for the definition."""
        full_src = self._source[self._slice]

        def is_empty_or_comment(line):
            return line.strip() == '' or line.strip().startswith('#')

        filtered_src = dropwhile(is_empty_or_comment, reversed(full_src))
        return ''.join(reversed(list(filtered_src)))

    def __str__(self):
        out = f'in {self._publicity} {self._human} `{self.name}`'
        if self.skipped_error_codes:
            out += f' (skipping {self.skipped_error_codes})'
        return out


class Module(Definition):
    """A Python source code module."""

    _fields = (
        'name',
        '_source',
        'start',
        'end',
        'decorators',
        'docstring',
        'children',
        'parent',
        '_dunder_all',
        'dunder_all_error',
        'future_imports',
        'skipped_error_codes',
    )
    _nest = staticmethod(lambda s: {'def': Function, 'class': Class}[s])
    module = property(lambda self: self)
    dunder_all = property(lambda self: self._dunder_all)

    @property
    def is_public(self):
        """Return True iff the module is considered public.

        This helps determine if it requires a docstring.
        """
        module_name = Path(self.name).stem
        return not self._is_inside_private_package() and self._is_public_name(
            module_name
        )

    def _is_inside_private_package(self):
        """Return True if the module is inside a private package."""
        path = Path(self.name).parent  # Ignore the actual module's name.
        syspath = [Path(p) for p in sys.path]  # Convert to pathlib.Path.

        # Bail if we are at the root directory or in `PYTHONPATH`.
        while path != path.parent and path not in syspath:
            if self._is_private_name(path.name):
                return True
            path = path.parent

        return False

    def _is_public_name(self, module_name):
        """Determine whether a "module name" (i.e. module or package name) is public."""
        return not module_name.startswith('_') or (
            module_name.startswith('__') and module_name.endswith('__')
        )

    def _is_private_name(self, module_name):
        """Determine whether a "module name" (i.e. module or package name) is private."""
        return not self._is_public_name(module_name)

    def __str__(self):
        return 'at module level'


class Package(Module):
    """A package is a __init__.py module."""


class Function(Definition):
    """A Python source code function."""

    _nest = staticmethod(
        lambda s: {'def': NestedFunction, 'class': NestedClass}[s]
    )

    @property
    def is_public(self):
        """Return True iff this function should be considered public."""
        if self.dunder_all is not None:
            return self.name in self.dunder_all
        else:
            return not self.name.startswith('_')

    @property
    def is_overload(self):
        """Return True iff the method decorated with overload."""
        return any(
            decorator.name == "overload" for decorator in self.decorators
        )

    def is_property(self, property_decorator_names):
        """Return True if the method is decorated with any property decorator."""
        return any(
            decorator.name in property_decorator_names
            for decorator in self.decorators
        )

    @property
    def is_test(self):
        """Return True if this function is a test function/method.

        We exclude tests from the imperative mood check, because to phrase
        their docstring in the imperative mood, they would have to start with
        a highly redundant "Test that ...".

        """
        return self.name.startswith('test') or self.name == 'runTest'


class NestedFunction(Function):
    """A Python source code nested function."""

    is_public = False


class Method(Function):
    """A Python source code method."""

    @property
    def is_magic(self):
        """Return True iff this method is a magic method (e.g., `__str__`)."""
        return (
            self.name.startswith('__')
            and self.name.endswith('__')
            and self.name not in VARIADIC_MAGIC_METHODS
        )

    @property
    def is_init(self):
        """Return True iff this method is `__init__`."""
        return self.name == '__init__'

    @property
    def is_public(self):
        """Return True iff this method should be considered public."""
        # Check if we are a setter/deleter method, and mark as private if so.
        for decorator in self.decorators:
            # Given 'foo', match 'foo.bar' but not 'foobar' or 'sfoo'
            if re(fr"^{self.name}\.").match(decorator.name):
                return False
        name_is_public = (
            not self.name.startswith('_')
            or self.name in VARIADIC_MAGIC_METHODS
            or self.is_magic
        )
        return self.parent.is_public and name_is_public

    @property
    def is_static(self):
        """Return True iff the method is static."""
        for decorator in self.decorators:
            if decorator.name == "staticmethod":
                return True
        return False


class Class(Definition):
    """A Python source code class."""

    _nest = staticmethod(lambda s: {'def': Method, 'class': NestedClass}[s])
    is_public = Function.is_public
    is_class = True


class NestedClass(Class):
    """A Python source code nested class."""

    @property
    def is_public(self):
        """Return True iff this class should be considered public."""
        return (
            not self.name.startswith('_')
            and self.parent.is_class
            and self.parent.is_public
        )


class Decorator(Value):
    """A decorator for function, method or class."""

    _fields = 'name arguments'.split()


class Docstring(str):
    """Represent a docstring.

    This is a string, but has additional start/end attributes representing
    the start and end of the token.

    """

    def __new__(cls, v, start, end):
        return str.__new__(cls, v)

    def __init__(self, v, start, end):
        self.start = start
        self.end = end


VARIADIC_MAGIC_METHODS = ('__init__', '__call__', '__new__')


class AllError(Exception):
    """Raised when there is a problem with __all__ when parsing."""

    def __init__(self, message):
        """Initialize the error with a more specific message."""
        Exception.__init__(
            self,
            message
            + textwrap.dedent(
                """
                That means pydocstyle cannot decide which definitions are
                public. Variable __all__ should be present at most once in
                each file, in form
                `__all__ = ('a_public_function', 'APublicClass', ...)`.
                More info on __all__: http://stackoverflow.com/q/44834/. ')
                """
            ),
        )


class TokenStream:
    # A logical newline is where a new expression or statement begins. When
    # there is a physical new line, but not a logical one, for example:
    # (x +
    #  y)
    # The token will be tk.NL, not tk.NEWLINE.
    LOGICAL_NEWLINES = {tk.NEWLINE, tk.INDENT, tk.DEDENT}

    def __init__(self, filelike):
        self._generator = tk.generate_tokens(filelike.readline)
        self.current = Token(*next(self._generator, None))
        self.line = self.current.start[0]
        self.log = log
        self.got_logical_newline = True

    def move(self):
        previous = self.current
        current = self._next_from_generator()
        self.current = None if current is None else Token(*current)
        self.line = self.current.start[0] if self.current else self.line
        is_logical_blank = previous.kind in (tk.NL, tk.COMMENT)
        self.got_logical_newline = (
            previous.kind in self.LOGICAL_NEWLINES
            # Retain logical_newline status if last line was logically blank
            or (self.got_logical_newline and is_logical_blank)
        )
        return previous

    def _next_from_generator(self):
        try:
            return next(self._generator, None)
        except (SyntaxError, tk.TokenError):
            self.log.warning('error generating tokens', exc_info=True)
            return None

    def __iter__(self):
        while True:
            if self.current is not None:
                yield self.current
            else:
                return
            self.move()


class TokenKind(int):
    def __repr__(self):
        return "tk.{}".format(tk.tok_name[self])


class Token(Value):
    _fields = 'kind value start end source'.split()

    def __init__(self, *args):
        super().__init__(*args)
        self.kind = TokenKind(self.kind)

    def __str__(self):
        return f"{self.kind!r} ({self.value})"


class Parser:
    """A Python source code parser."""

    def parse(self, filelike, filename):
        """Parse the given file-like object and return its Module object."""
        self.log = log
        self.source = filelike.readlines()
        src = ''.join(self.source)
        try:
            compile(src, filename, 'exec')
        except SyntaxError as error:
            raise ParseError() from error
        self.stream = TokenStream(StringIO(src))
        self.filename = filename
        self.dunder_all = None
        self.dunder_all_error = None
        self.future_imports = set()
        self._accumulated_decorators = []
        return self.parse_module()

    # TODO: remove
    def __call__(self, *args, **kwargs):
        """Call the parse method."""
        return self.parse(*args, **kwargs)

    current = property(lambda self: self.stream.current)
    line = property(lambda self: self.stream.line)

    def consume(self, kind):
        """Consume one token and verify it is of the expected kind."""
        next_token = self.stream.move()
        if next_token.kind != kind:
            raise UnexpectedTokenError(token=next_token, expected_kind=kind)

    def leapfrog(self, kind, value=None):
        """Skip tokens in the stream until a certain token kind is reached.

        If `value` is specified, tokens whose values are different will also
        be skipped.
        """
        while self.current is not None:
            if self.current.kind == kind and (
                value is None or self.current.value == value
            ):
                self.consume(kind)
                return
            self.stream.move()

    def parse_docstring(self):
        """Parse a single docstring and return its value."""
        self.log.debug("parsing docstring, token is %s", self.current)
        while self.current.kind in (tk.COMMENT, tk.NEWLINE, tk.NL):
            self.stream.move()
            self.log.debug(
                "parsing docstring, token is %r (%s)",
                self.current.kind,
                self.current.value,
            )
        if self.current.kind == tk.STRING:
            docstring = Docstring(
                self.current.value, self.current.start[0], self.current.end[0]
            )
            self.stream.move()
            return docstring
        return None

    def parse_decorators(self):
        """Parse decorators into self._accumulated_decorators.

        Called after first @ is found.
        Continue to do so until encountering the 'def' or 'class' start token.
        """
        name = []
        arguments = []
        at_arguments = False

        while self.current is not None:
            self.log.debug(
                "parsing decorators, current token is %r (%s)",
                self.current.kind,
                self.current.value,
            )
            if self.current.kind == tk.NAME and self.current.value in [
                'async',
                'def',
                'class',
            ]:
                # Done with decorators - found function or class proper
                break
            elif self.current.kind == tk.OP and self.current.value == '@':
                # New decorator found. Store the decorator accumulated so far:
                self._accumulated_decorators.append(
                    Decorator(''.join(name), ''.join(arguments))
                )
                # Now reset to begin accumulating the new decorator:
                name = []
                arguments = []
                at_arguments = False
            elif self.current.kind == tk.OP and self.current.value == '(':
                at_arguments = True
            elif self.current.kind == tk.OP and self.current.value == ')':
                # Ignore close parenthesis
                pass
            elif self.current.kind == tk.NEWLINE or self.current.kind == tk.NL:
                # Ignore newlines
                pass
            else:
                # Keep accumulating current decorator's name or argument.
                if not at_arguments:
                    name.append(self.current.value)
                else:
                    arguments.append(self.current.value)
            self.stream.move()

        # Add decorator accumulated so far
        self._accumulated_decorators.append(
            Decorator(''.join(name), ''.join(arguments))
        )

    def parse_definitions(self, class_, dunder_all=False):
        """Parse multiple definitions and yield them."""
        while self.current is not None:
            self.log.debug(
                "parsing definition list, current token is %r (%s)",
                self.current.kind,
                self.current.value,
            )
            self.log.debug('got_newline: %s', self.stream.got_logical_newline)
            if dunder_all and self.current.value == '__all__':
                self.parse_dunder_all()
            elif (
                self.current.kind == tk.OP
                and self.current.value == '@'
                and self.stream.got_logical_newline
            ):
                self.consume(tk.OP)
                self.parse_decorators()
            elif self.current.value in ['def', 'class']:
                yield self.parse_definition(class_._nest(self.current.value))
            elif self.current.kind == tk.INDENT:
                self.consume(tk.INDENT)
                yield from self.parse_definitions(class_)
            elif self.current.kind == tk.DEDENT:
                self.consume(tk.DEDENT)
                return
            elif self.current.value == 'from':
                self.parse_from_import_statement()
            else:
                self.stream.move()

    def parse_dunder_all(self):
        """Parse the __all__ definition in a module."""
        assert self.current.value == '__all__'
        self.consume(tk.NAME)
        # More than one __all__ definition means we ignore all __all__.
        if self.dunder_all is not None or self.dunder_all_error is not None:
            self.dunder_all = None
            self.dunder_all_error = 'Could not evaluate contents of __all__. '
            return
        if self.current.value != '=':
            self.dunder_all_error = 'Could not evaluate contents of __all__. '
            return
        self.consume(tk.OP)

        is_surrounded = False
        if self.current.value in '([':
            is_surrounded = True
            self.consume(tk.OP)

        dunder_all_content = "("
        while True:
            if is_surrounded and self.current.value in ")]":
                break
            if self.current.kind in (tk.NEWLINE, tk.ENDMARKER):
                break
            if self.current.kind in (tk.NL, tk.COMMENT):
                pass
            elif self.current.kind == tk.STRING or self.current.value == ',':
                dunder_all_content += self.current.value
            else:
                self.dunder_all_error = (
                    'Could not evaluate contents of __all__.'
                )
                return
            self.stream.move()
        if is_surrounded:
            self.consume(tk.OP)
        if not is_surrounded and ',' not in dunder_all_content:
            self.dunder_all_error = (
                'Unexpected token kind in __all__: {!r}. '.format(
                    self.current.kind
                )
            )
            return
        dunder_all_content += ")"

        try:
            self.dunder_all = eval(dunder_all_content, {})
        except BaseException as e:
            self.dunder_all_error = (
                'Could not evaluate contents of __all__.'
                '\bThe value was {}. The exception was:\n{}'.format(
                    dunder_all_content, e
                )
            )

        while (
            self.current.kind not in self.stream.LOGICAL_NEWLINES
            and self.current.kind != tk.ENDMARKER
        ):
            if self.current.kind != tk.COMMENT:
                self.dunder_all = None
                self.dunder_all_error = (
                    'Could not evaluate contents of __all__. '
                )
                return
            self.stream.move()

    def parse_module(self):
        """Parse a module (and its children) and return a Module object."""
        self.log.debug("parsing module.")
        start = self.line
        skipped_error_codes = self.parse_skip_comment()
        docstring = self.parse_docstring()
        children = list(self.parse_definitions(Module, dunder_all=True))
        assert self.current is None, self.current
        end = self.line
        cls = Module
        if self.filename.endswith('__init__.py'):
            cls = Package
        module = cls(
            self.filename,
            self.source,
            start,
            end,
            [],
            docstring,
            children,
            None,
            self.dunder_all,
            self.dunder_all_error,
            None,
            skipped_error_codes,
        )
        for child in module.children:
            child.parent = module
        module.future_imports = self.future_imports
        self.log.debug("finished parsing module.")
        return module

    def parse_definition(self, class_):
        """Parse a definition and return its value in a `class_` object."""
        start = self.line
        self.consume(tk.NAME)
        name = self.current.value
        self.log.debug("parsing %s '%s'", class_.__name__, name)
        self.stream.move()
        if self.current.kind == tk.OP and self.current.value == '(':
            parenthesis_level = 0
            while True:
                if self.current.kind == tk.OP:
                    if self.current.value == '(':
                        parenthesis_level += 1
                    elif self.current.value == ')':
                        parenthesis_level -= 1
                        if parenthesis_level == 0:
                            break
                self.stream.move()
        if self.current.kind != tk.OP or self.current.value != ':':
            self.leapfrog(tk.OP, value=":")
        else:
            self.consume(tk.OP)
        if self.current.kind in (tk.NEWLINE, tk.COMMENT):
            skipped_error_codes = self.parse_skip_comment()
            self.leapfrog(tk.INDENT)
            assert self.current.kind != tk.INDENT
            docstring = self.parse_docstring()
            decorators = self._accumulated_decorators
            self.log.debug("current accumulated decorators: %s", decorators)
            self._accumulated_decorators = []
            self.log.debug("parsing nested definitions.")
            children = list(self.parse_definitions(class_))
            self.log.debug(
                "finished parsing nested definitions for '%s'", name
            )
            end = self.line - 1
        else:  # one-liner definition
            skipped_error_codes = ''
            docstring = self.parse_docstring()
            decorators = self._accumulated_decorators
            self.log.debug("current accumulated decorators: %s", decorators)
            self._accumulated_decorators = []
            children = []
            end = self.line
            self.leapfrog(tk.NEWLINE)
        definition = class_(
            name,
            self.source,
            start,
            end,
            decorators,
            docstring,
            children,
            None,
            skipped_error_codes,
        )
        for child in definition.children:
            child.parent = definition
        self.log.debug(
            "finished parsing %s '%s'. Next token is %r",
            class_.__name__,
            name,
            self.current,
        )
        return definition

    def parse_skip_comment(self):
        """Parse a definition comment for noqa skips."""
        skipped_error_codes = ''
        while self.current.kind in (tk.COMMENT, tk.NEWLINE, tk.NL):
            if self.current.kind == tk.COMMENT:
                if 'noqa: ' in self.current.value:
                    skipped_error_codes = ''.join(
                        self.current.value.split('noqa: ')[1:]
                    )
                elif self.current.value.startswith('# noqa'):
                    skipped_error_codes = 'all'
            self.stream.move()
            self.log.debug(
                "parsing comments before docstring, token is %r (%s)",
                self.current.kind,
                self.current.value,
            )

            if skipped_error_codes:
                break

        return skipped_error_codes

    def check_current(self, kind=None, value=None):
        """Verify the current token is of type `kind` and equals `value`."""
        msg = textwrap.dedent(
            """
        Unexpected token at line {self.line}:

        In file: {self.filename}

        Got kind {self.current.kind!r}
        Got value {self.current.value}
        """.format(
                self=self
            )
        )
        kind_valid = self.current.kind == kind if kind else True
        value_valid = self.current.value == value if value else True
        assert kind_valid and value_valid, msg

    def parse_from_import_statement(self):
        """Parse a 'from x import y' statement.

        The purpose is to find __future__ statements.

        """
        self.log.debug('parsing from/import statement.')
        is_future_import = self._parse_from_import_source()
        self._parse_from_import_names(is_future_import)

    def _parse_from_import_source(self):
        """Parse the 'from x import' part in a 'from x import y' statement.

        Return true iff `x` is __future__.
        """
        assert self.current.value == 'from', self.current.value
        self.stream.move()
        is_future_import = self.current.value == '__future__'
        self.stream.move()
        while (
            self.current is not None
            and self.current.kind in (tk.DOT, tk.NAME, tk.OP)
            and self.current.value != 'import'
        ):
            self.stream.move()
        if self.current is None or self.current.value != 'import':
            return False
        self.check_current(value='import')
        assert self.current.value == 'import', self.current.value
        self.stream.move()
        return is_future_import

    def _parse_from_import_names(self, is_future_import):
        """Parse the 'y' part in a 'from x import y' statement."""
        if self.current.value == '(':
            self.consume(tk.OP)
            expected_end_kinds = (tk.OP,)
        else:
            expected_end_kinds = (tk.NEWLINE, tk.ENDMARKER)
        while self.current.kind not in expected_end_kinds and not (
            self.current.kind == tk.OP and self.current.value == ';'
        ):
            if self.current.kind != tk.NAME:
                self.stream.move()
                continue
            self.log.debug(
                "parsing import, token is %r (%s)",
                self.current.kind,
                self.current.value,
            )
            if is_future_import:
                self.log.debug('found future import: %s', self.current.value)
                self.future_imports.add(self.current.value)
            self.consume(tk.NAME)
            self.log.debug(
                "parsing import, token is %r (%s)",
                self.current.kind,
                self.current.value,
            )
            if self.current.kind == tk.NAME and self.current.value == 'as':
                self.consume(tk.NAME)  # as
                if self.current.kind == tk.NAME:
                    self.consume(tk.NAME)  # new name, irrelevant
            if self.current.value == ',':
                self.consume(tk.OP)
            self.log.debug(
                "parsing import, token is %r (%s)",
                self.current.kind,
                self.current.value,
            )
