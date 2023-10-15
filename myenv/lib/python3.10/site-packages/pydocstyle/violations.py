"""Docstring violation definition."""

from collections import namedtuple
from functools import partial
from itertools import dropwhile
from typing import Any, Callable, Iterable, List, Optional

from .parser import Definition
from .utils import is_blank

__all__ = ('Error', 'ErrorRegistry', 'conventions')


ErrorParams = namedtuple('ErrorParams', ['code', 'short_desc', 'context'])


class Error:
    """Error in docstring style."""

    # Options that define how errors are printed:
    explain = False
    source = False

    def __init__(
        self,
        code: str,
        short_desc: str,
        context: str,
        *parameters: Iterable[str],
    ) -> None:
        """Initialize the object.

        `parameters` are specific to the created error.

        """
        self.code = code
        self.short_desc = short_desc
        self.context = context
        self.parameters = parameters
        self.definition = None  # type: Optional[Definition]
        self.explanation = None  # type: Optional[str]

    def set_context(self, definition: Definition, explanation: str) -> None:
        """Set the source code context for this error."""
        self.definition = definition
        self.explanation = explanation

    filename = property(lambda self: self.definition.module.name)
    line = property(lambda self: self.definition.error_lineno)

    @property
    def message(self) -> str:
        """Return the message to print to the user."""
        ret = f'{self.code}: {self.short_desc}'
        if self.context is not None:
            specific_error_msg = self.context.format(*self.parameters)
            ret += f' ({specific_error_msg})'
        return ret

    @property
    def lines(self) -> str:
        """Return the source code lines for this error."""
        if self.definition is None:
            return ''
        source = ''
        lines = self.definition.source.splitlines(keepends=True)
        offset = self.definition.start  # type: ignore
        lines_stripped = list(
            reversed(list(dropwhile(is_blank, reversed(lines))))
        )
        numbers_width = len(str(offset + len(lines_stripped)))
        line_format = f'{{:{numbers_width}}}:{{}}'
        for n, line in enumerate(lines_stripped):
            if line:
                line = ' ' + line
            source += line_format.format(n + offset, line)
            if n > 5:
                source += '        ...\n'
                break
        return source

    def __str__(self) -> str:
        if self.explanation:
            self.explanation = '\n'.join(
                l for l in self.explanation.split('\n') if not is_blank(l)
            )
        template = '{filename}:{line} {definition}:\n        {message}'
        if self.source and self.explain:
            template += '\n\n{explanation}\n\n{lines}\n'
        elif self.source and not self.explain:
            template += '\n\n{lines}\n'
        elif self.explain and not self.source:
            template += '\n\n{explanation}\n\n'
        return template.format(
            **{
                name: getattr(self, name)
                for name in [
                    'filename',
                    'line',
                    'definition',
                    'message',
                    'explanation',
                    'lines',
                ]
            }
        )

    def __repr__(self) -> str:
        return str(self)

    def __lt__(self, other: 'Error') -> bool:
        return (self.filename, self.line) < (other.filename, other.line)


class ErrorRegistry:
    """A registry of all error codes, divided to groups."""

    groups = []  # type: ignore

    class ErrorGroup:
        """A group of similarly themed errors."""

        def __init__(self, prefix: str, name: str) -> None:
            """Initialize the object.

            `Prefix` should be the common prefix for errors in this group,
            e.g., "D1".
            `name` is the name of the group (its subject).

            """
            self.prefix = prefix
            self.name = name
            self.errors = []  # type: List[ErrorParams]

        def create_error(
            self,
            error_code: str,
            error_desc: str,
            error_context: Optional[str] = None,
        ) -> Callable[[Iterable[str]], Error]:
            """Create an error, register it to this group and return it."""
            # TODO: check prefix

            error_params = ErrorParams(error_code, error_desc, error_context)
            factory = partial(Error, *error_params)
            self.errors.append(error_params)
            return factory

    @classmethod
    def create_group(cls, prefix: str, name: str) -> ErrorGroup:
        """Create a new error group and return it."""
        group = cls.ErrorGroup(prefix, name)
        cls.groups.append(group)
        return group

    @classmethod
    def get_error_codes(cls) -> Iterable[str]:
        """Yield all registered codes."""
        for group in cls.groups:
            for error in group.errors:
                yield error.code

    @classmethod
    def to_rst(cls) -> str:
        """Output the registry as reStructuredText, for documentation."""
        max_len = max(
            len(error.short_desc)
            for group in cls.groups
            for error in group.errors
        )
        sep_line = '+' + 6 * '-' + '+' + '-' * (max_len + 2) + '+\n'
        blank_line = '|' + (max_len + 9) * ' ' + '|\n'
        table = ''
        for group in cls.groups:
            table += sep_line
            table += blank_line
            table += '|' + f'**{group.name}**'.center(max_len + 9) + '|\n'
            table += blank_line
            for error in group.errors:
                table += sep_line
                table += (
                    '|'
                    + error.code.center(6)
                    + '| '
                    + error.short_desc.ljust(max_len + 1)
                    + '|\n'
                )
        table += sep_line
        return table


D1xx = ErrorRegistry.create_group('D1', 'Missing Docstrings')
D100 = D1xx.create_error(
    'D100',
    'Missing docstring in public module',
)
D101 = D1xx.create_error(
    'D101',
    'Missing docstring in public class',
)
D102 = D1xx.create_error(
    'D102',
    'Missing docstring in public method',
)
D103 = D1xx.create_error(
    'D103',
    'Missing docstring in public function',
)
D104 = D1xx.create_error(
    'D104',
    'Missing docstring in public package',
)
D105 = D1xx.create_error(
    'D105',
    'Missing docstring in magic method',
)
D106 = D1xx.create_error(
    'D106',
    'Missing docstring in public nested class',
)
D107 = D1xx.create_error(
    'D107',
    'Missing docstring in __init__',
)

D2xx = ErrorRegistry.create_group('D2', 'Whitespace Issues')
D200 = D2xx.create_error(
    'D200',
    'One-line docstring should fit on one line ' 'with quotes',
    'found {0}',
)
D201 = D2xx.create_error(
    'D201',
    'No blank lines allowed before function docstring',
    'found {0}',
)
D202 = D2xx.create_error(
    'D202',
    'No blank lines allowed after function docstring',
    'found {0}',
)
D203 = D2xx.create_error(
    'D203',
    '1 blank line required before class docstring',
    'found {0}',
)
D204 = D2xx.create_error(
    'D204',
    '1 blank line required after class docstring',
    'found {0}',
)
D205 = D2xx.create_error(
    'D205',
    '1 blank line required between summary line and description',
    'found {0}',
)
D206 = D2xx.create_error(
    'D206',
    'Docstring should be indented with spaces, not tabs',
)
D207 = D2xx.create_error(
    'D207',
    'Docstring is under-indented',
)
D208 = D2xx.create_error(
    'D208',
    'Docstring is over-indented',
)
D209 = D2xx.create_error(
    'D209',
    'Multi-line docstring closing quotes should be on a separate line',
)
D210 = D2xx.create_error(
    'D210',
    'No whitespaces allowed surrounding docstring text',
)
D211 = D2xx.create_error(
    'D211',
    'No blank lines allowed before class docstring',
    'found {0}',
)
D212 = D2xx.create_error(
    'D212',
    'Multi-line docstring summary should start at the first line',
)
D213 = D2xx.create_error(
    'D213',
    'Multi-line docstring summary should start at the second line',
)
D214 = D2xx.create_error(
    'D214',
    'Section is over-indented',
    '{0!r}',
)
D215 = D2xx.create_error(
    'D215',
    'Section underline is over-indented',
    'in section {0!r}',
)

D3xx = ErrorRegistry.create_group('D3', 'Quotes Issues')
D300 = D3xx.create_error(
    'D300',
    'Use """triple double quotes"""',
    'found {0}-quotes',
)
D301 = D3xx.create_error(
    'D301',
    'Use r""" if any backslashes in a docstring',
)
D302 = D3xx.create_error(
    'D302',
    'Deprecated: Use u""" for Unicode docstrings',
)

D4xx = ErrorRegistry.create_group('D4', 'Docstring Content Issues')
D400 = D4xx.create_error(
    'D400',
    'First line should end with a period',
    'not {0!r}',
)
D401 = D4xx.create_error(
    'D401',
    'First line should be in imperative mood',
    "perhaps '{0}', not '{1}'",
)
D401b = D4xx.create_error(
    'D401',
    'First line should be in imperative mood; try rephrasing',
    "found '{0}'",
)
D402 = D4xx.create_error(
    'D402',
    'First line should not be the function\'s "signature"',
)
D403 = D4xx.create_error(
    'D403',
    'First word of the first line should be properly capitalized',
    '{0!r}, not {1!r}',
)
D404 = D4xx.create_error(
    'D404',
    'First word of the docstring should not be `This`',
)
D405 = D4xx.create_error(
    'D405',
    'Section name should be properly capitalized',
    '{0!r}, not {1!r}',
)
D406 = D4xx.create_error(
    'D406',
    'Section name should end with a newline',
    '{0!r}, not {1!r}',
)
D407 = D4xx.create_error(
    'D407',
    'Missing dashed underline after section',
    '{0!r}',
)
D408 = D4xx.create_error(
    'D408',
    'Section underline should be in the line following the section\'s name',
    '{0!r}',
)
D409 = D4xx.create_error(
    'D409',
    'Section underline should match the length of its name',
    'Expected {0!r} dashes in section {1!r}, got {2!r}',
)
D410 = D4xx.create_error(
    'D410',
    'Missing blank line after section',
    '{0!r}',
)
D411 = D4xx.create_error(
    'D411',
    'Missing blank line before section',
    '{0!r}',
)
D412 = D4xx.create_error(
    'D412',
    'No blank lines allowed between a section header and its content',
    '{0!r}',
)
D413 = D4xx.create_error(
    'D413',
    'Missing blank line after last section',
    '{0!r}',
)
D414 = D4xx.create_error(
    'D414',
    'Section has no content',
    '{0!r}',
)
D415 = D4xx.create_error(
    'D415',
    (
        'First line should end with a period, question '
        'mark, or exclamation point'
    ),
    'not {0!r}',
)
D416 = D4xx.create_error(
    'D416',
    'Section name should end with a colon',
    '{0!r}, not {1!r}',
)
D417 = D4xx.create_error(
    'D417',
    'Missing argument descriptions in the docstring',
    'argument(s) {0} are missing descriptions in {1!r} docstring',
)

D418 = D4xx.create_error(
    'D418',
    'Function/ Method decorated with @overload shouldn\'t contain a docstring',
)
D419 = D4xx.create_error(
    'D419',
    'Docstring is empty',
)


class AttrDict(dict):
    def __getattr__(self, item: str) -> Any:
        return self[item]


all_errors = set(ErrorRegistry.get_error_codes())


conventions = AttrDict(
    {
        'pep257': all_errors
        - {
            'D203',
            'D212',
            'D213',
            'D214',
            'D215',
            'D404',
            'D405',
            'D406',
            'D407',
            'D408',
            'D409',
            'D410',
            'D411',
            'D413',
            'D415',
            'D416',
            'D417',
            'D418',
        },
        'numpy': all_errors
        - {
            'D107',
            'D203',
            'D212',
            'D213',
            'D402',
            'D413',
            'D415',
            'D416',
            'D417',
        },
        'google': all_errors
        - {
            'D203',
            'D204',
            'D213',
            'D215',
            'D400',
            'D401',
            'D404',
            'D406',
            'D407',
            'D408',
            'D409',
            'D413',
        },
    }
)
