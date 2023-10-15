# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Utility methods for docstring checking."""

from __future__ import annotations

import re

import astroid
from astroid import nodes
from astroid.util import UninferableBase

from pylint.checkers import utils


def space_indentation(s: str) -> int:
    """The number of leading spaces in a string.

    :param str s: input string

    :rtype: int
    :return: number of leading spaces
    """
    return len(s) - len(s.lstrip(" "))


def get_setters_property_name(node: nodes.FunctionDef) -> str | None:
    """Get the name of the property that the given node is a setter for.

    :param node: The node to get the property name for.
    :type node: str

    :rtype: str or None
    :returns: The name of the property that the node is a setter for,
        or None if one could not be found.
    """
    decorators = node.decorators.nodes if node.decorators else []
    for decorator in decorators:
        if (
            isinstance(decorator, nodes.Attribute)
            and decorator.attrname == "setter"
            and isinstance(decorator.expr, nodes.Name)
        ):
            return decorator.expr.name  # type: ignore[no-any-return]
    return None


def get_setters_property(node: nodes.FunctionDef) -> nodes.FunctionDef | None:
    """Get the property node for the given setter node.

    :param node: The node to get the property for.
    :type node: nodes.FunctionDef

    :rtype: nodes.FunctionDef or None
    :returns: The node relating to the property of the given setter node,
        or None if one could not be found.
    """
    property_ = None

    property_name = get_setters_property_name(node)
    class_node = utils.node_frame_class(node)
    if property_name and class_node:
        class_attrs: list[nodes.FunctionDef] = class_node.getattr(node.name)
        for attr in class_attrs:
            if utils.decorated_with_property(attr):
                property_ = attr
                break

    return property_


def returns_something(return_node: nodes.Return) -> bool:
    """Check if a return node returns a value other than None.

    :param return_node: The return node to check.
    :type return_node: astroid.Return

    :rtype: bool
    :return: True if the return node returns a value other than None,
        False otherwise.
    """
    returns = return_node.value

    if returns is None:
        return False

    return not (isinstance(returns, nodes.Const) and returns.value is None)


def _get_raise_target(node: nodes.NodeNG) -> nodes.NodeNG | UninferableBase | None:
    if isinstance(node.exc, nodes.Call):
        func = node.exc.func
        if isinstance(func, (nodes.Name, nodes.Attribute)):
            return utils.safe_infer(func)
    return None


def _split_multiple_exc_types(target: str) -> list[str]:
    delimiters = r"(\s*,(?:\s*or\s)?\s*|\s+or\s+)"
    return re.split(delimiters, target)


def possible_exc_types(node: nodes.NodeNG) -> set[nodes.ClassDef]:
    """Gets all the possible raised exception types for the given raise node.

    .. note::

        Caught exception types are ignored.

    :param node: The raise node to find exception types for.

    :returns: A list of exception types possibly raised by :param:`node`.
    """
    exceptions = []
    if isinstance(node.exc, nodes.Name):
        inferred = utils.safe_infer(node.exc)
        if inferred:
            exceptions = [inferred]
    elif node.exc is None:
        handler = node.parent
        while handler and not isinstance(handler, nodes.ExceptHandler):
            handler = handler.parent

        if handler and handler.type:
            try:
                for exception in astroid.unpack_infer(handler.type):
                    if not isinstance(exception, UninferableBase):
                        exceptions.append(exception)
            except astroid.InferenceError:
                pass
    else:
        target = _get_raise_target(node)
        if isinstance(target, nodes.ClassDef):
            exceptions = [target]
        elif isinstance(target, nodes.FunctionDef):
            for ret in target.nodes_of_class(nodes.Return):
                if ret.value is None:
                    continue
                if ret.frame(future=True) != target:
                    # return from inner function - ignore it
                    continue

                val = utils.safe_infer(ret.value)
                if val and utils.inherit_from_std_ex(val):
                    if isinstance(val, nodes.ClassDef):
                        exceptions.append(val)
                    elif isinstance(val, astroid.Instance):
                        exceptions.append(val.getattr("__class__")[0])

    try:
        return {
            exc
            for exc in exceptions
            if not utils.node_ignores_exception(node, exc.name)
        }
    except astroid.InferenceError:
        return set()


def docstringify(
    docstring: nodes.Const | None, default_type: str = "default"
) -> Docstring:
    best_match = (0, DOCSTRING_TYPES.get(default_type, Docstring)(docstring))
    for docstring_type in (
        SphinxDocstring,
        EpytextDocstring,
        GoogleDocstring,
        NumpyDocstring,
    ):
        instance = docstring_type(docstring)
        matching_sections = instance.matching_sections()
        if matching_sections > best_match[0]:
            best_match = (matching_sections, instance)

    return best_match[1]


class Docstring:
    re_for_parameters_see = re.compile(
        r"""
        For\s+the\s+(other)?\s*parameters\s*,\s+see
        """,
        re.X | re.S,
    )

    supports_yields: bool = False
    """True if the docstring supports a "yield" section.

    False if the docstring uses the returns section to document generators.
    """

    # These methods are designed to be overridden
    def __init__(self, doc: nodes.Const | None) -> None:
        docstring: str = doc.value if doc else ""
        self.doc = docstring.expandtabs()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}:'''{self.doc}'''>"

    def matching_sections(self) -> int:
        """Returns the number of matching docstring sections."""
        return 0

    def exceptions(self) -> set[str]:
        return set()

    def has_params(self) -> bool:
        return False

    def has_returns(self) -> bool:
        return False

    def has_rtype(self) -> bool:
        return False

    def has_property_returns(self) -> bool:
        return False

    def has_property_type(self) -> bool:
        return False

    def has_yields(self) -> bool:
        return False

    def has_yields_type(self) -> bool:
        return False

    def match_param_docs(self) -> tuple[set[str], set[str]]:
        return set(), set()

    def params_documented_elsewhere(self) -> bool:
        return self.re_for_parameters_see.search(self.doc) is not None


class SphinxDocstring(Docstring):
    re_type = r"""
        [~!.]?               # Optional link style prefix
        \w(?:\w|\.[^\.])*    # Valid python name
        """

    re_simple_container_type = rf"""
        {re_type}                     # a container type
        [\(\[] [^\n\s]+ [\)\]]        # with the contents of the container
    """

    re_multiple_simple_type = r"""
        (?:{container_type}|{type})
        (?:(?:\s+(?:of|or)\s+|\s*,\s*|\s+\|\s+)(?:{container_type}|{type}))*
    """.format(
        type=re_type, container_type=re_simple_container_type
    )

    re_xref = rf"""
        (?::\w+:)?                    # optional tag
        `{re_type}`                   # what to reference
        """

    re_param_raw = rf"""
        :                       # initial colon
        (?:                     # Sphinx keywords
        param|parameter|
        arg|argument|
        key|keyword
        )
        \s+                     # whitespace

        (?:                     # optional type declaration
        ({re_type}|{re_simple_container_type})
        \s+
        )?

        ((\\\*{{0,2}}\w+)|(\w+))  # Parameter name with potential asterisks
        \s*                       # whitespace
        :                         # final colon
        """
    re_param_in_docstring = re.compile(re_param_raw, re.X | re.S)

    re_type_raw = rf"""
        :type                           # Sphinx keyword
        \s+                             # whitespace
        ({re_multiple_simple_type})     # Parameter name
        \s*                             # whitespace
        :                               # final colon
        """
    re_type_in_docstring = re.compile(re_type_raw, re.X | re.S)

    re_property_type_raw = rf"""
        :type:                      # Sphinx keyword
        \s+                         # whitespace
        {re_multiple_simple_type}   # type declaration
        """
    re_property_type_in_docstring = re.compile(re_property_type_raw, re.X | re.S)

    re_raise_raw = rf"""
        :                               # initial colon
        (?:                             # Sphinx keyword
        raises?|
        except|exception
        )
        \s+                             # whitespace
        ({re_multiple_simple_type})     # exception type
        \s*                             # whitespace
        :                               # final colon
        """
    re_raise_in_docstring = re.compile(re_raise_raw, re.X | re.S)

    re_rtype_in_docstring = re.compile(r":rtype:")

    re_returns_in_docstring = re.compile(r":returns?:")

    supports_yields = False

    def matching_sections(self) -> int:
        """Returns the number of matching docstring sections."""
        return sum(
            bool(i)
            for i in (
                self.re_param_in_docstring.search(self.doc),
                self.re_raise_in_docstring.search(self.doc),
                self.re_rtype_in_docstring.search(self.doc),
                self.re_returns_in_docstring.search(self.doc),
                self.re_property_type_in_docstring.search(self.doc),
            )
        )

    def exceptions(self) -> set[str]:
        types: set[str] = set()

        for match in re.finditer(self.re_raise_in_docstring, self.doc):
            raise_type = match.group(1)
            types.update(_split_multiple_exc_types(raise_type))

        return types

    def has_params(self) -> bool:
        if not self.doc:
            return False

        return self.re_param_in_docstring.search(self.doc) is not None

    def has_returns(self) -> bool:
        if not self.doc:
            return False

        return bool(self.re_returns_in_docstring.search(self.doc))

    def has_rtype(self) -> bool:
        if not self.doc:
            return False

        return bool(self.re_rtype_in_docstring.search(self.doc))

    def has_property_returns(self) -> bool:
        if not self.doc:
            return False

        # The summary line is the return doc,
        # so the first line must not be a known directive.
        return not self.doc.lstrip().startswith(":")

    def has_property_type(self) -> bool:
        if not self.doc:
            return False

        return bool(self.re_property_type_in_docstring.search(self.doc))

    def match_param_docs(self) -> tuple[set[str], set[str]]:
        params_with_doc = set()
        params_with_type = set()

        for match in re.finditer(self.re_param_in_docstring, self.doc):
            name = match.group(2)
            # Remove escape characters necessary for asterisks
            name = name.replace("\\", "")
            params_with_doc.add(name)
            param_type = match.group(1)
            if param_type is not None:
                params_with_type.add(name)

        params_with_type.update(re.findall(self.re_type_in_docstring, self.doc))
        return params_with_doc, params_with_type


class EpytextDocstring(SphinxDocstring):
    """Epytext is similar to Sphinx.

    See the docs:
        http://epydoc.sourceforge.net/epytext.html
        http://epydoc.sourceforge.net/fields.html#fields

    It's used in PyCharm:
        https://www.jetbrains.com/help/pycharm/2016.1/creating-documentation-comments.html#d848203e314
        https://www.jetbrains.com/help/pycharm/2016.1/using-docstrings-to-specify-types.html
    """

    re_param_in_docstring = re.compile(
        SphinxDocstring.re_param_raw.replace(":", "@", 1), re.X | re.S
    )

    re_type_in_docstring = re.compile(
        SphinxDocstring.re_type_raw.replace(":", "@", 1), re.X | re.S
    )

    re_property_type_in_docstring = re.compile(
        SphinxDocstring.re_property_type_raw.replace(":", "@", 1), re.X | re.S
    )

    re_raise_in_docstring = re.compile(
        SphinxDocstring.re_raise_raw.replace(":", "@", 1), re.X | re.S
    )

    re_rtype_in_docstring = re.compile(
        r"""
        @                       # initial "at" symbol
        (?:                     # Epytext keyword
        rtype|returntype
        )
        :                       # final colon
        """,
        re.X | re.S,
    )

    re_returns_in_docstring = re.compile(r"@returns?:")

    def has_property_returns(self) -> bool:
        if not self.doc:
            return False

        # If this is a property docstring, the summary is the return doc.
        if self.has_property_type():
            # The summary line is the return doc,
            # so the first line must not be a known directive.
            return not self.doc.lstrip().startswith("@")

        return False


class GoogleDocstring(Docstring):
    re_type = SphinxDocstring.re_type

    re_xref = SphinxDocstring.re_xref

    re_container_type = rf"""
        (?:{re_type}|{re_xref})       # a container type
        [\(\[] [^\n]+ [\)\]]          # with the contents of the container
    """

    re_multiple_type = r"""
        (?:{container_type}|{type}|{xref})
        (?:(?:\s+(?:of|or)\s+|\s*,\s*|\s+\|\s+)(?:{container_type}|{type}|{xref}))*
    """.format(
        type=re_type, xref=re_xref, container_type=re_container_type
    )

    _re_section_template = r"""
        ^([ ]*)   {0} \s*:   \s*$     # Google parameter header
        (  .* )                       # section
        """

    re_param_section = re.compile(
        _re_section_template.format(r"(?:Args|Arguments|Parameters)"),
        re.X | re.S | re.M,
    )

    re_keyword_param_section = re.compile(
        _re_section_template.format(r"Keyword\s(?:Args|Arguments|Parameters)"),
        re.X | re.S | re.M,
    )

    re_param_line = re.compile(
        rf"""
        \s*  ((?:\\?\*{{0,2}})?[\w\\]+) # identifier potentially with asterisks or escaped `\`
        \s*  ( [(]
            {re_multiple_type}
            (?:,\s+optional)?
            [)] )? \s* :                # optional type declaration
        \s*  (.*)                       # beginning of optional description
    """,
        re.X | re.S | re.M,
    )

    re_raise_section = re.compile(
        _re_section_template.format(r"Raises"), re.X | re.S | re.M
    )

    re_raise_line = re.compile(
        rf"""
        \s*  ({re_multiple_type}) \s* :  # identifier
        \s*  (.*)                        # beginning of optional description
    """,
        re.X | re.S | re.M,
    )

    re_returns_section = re.compile(
        _re_section_template.format(r"Returns?"), re.X | re.S | re.M
    )

    re_returns_line = re.compile(
        rf"""
        \s* ({re_multiple_type}:)?        # identifier
        \s* (.*)                          # beginning of description
    """,
        re.X | re.S | re.M,
    )

    re_property_returns_line = re.compile(
        rf"""
        ^{re_multiple_type}:           # identifier
        \s* (.*)                       # Summary line / description
    """,
        re.X | re.S | re.M,
    )

    re_yields_section = re.compile(
        _re_section_template.format(r"Yields?"), re.X | re.S | re.M
    )

    re_yields_line = re_returns_line

    supports_yields = True

    def matching_sections(self) -> int:
        """Returns the number of matching docstring sections."""
        return sum(
            bool(i)
            for i in (
                self.re_param_section.search(self.doc),
                self.re_raise_section.search(self.doc),
                self.re_returns_section.search(self.doc),
                self.re_yields_section.search(self.doc),
                self.re_property_returns_line.search(self._first_line()),
            )
        )

    def has_params(self) -> bool:
        if not self.doc:
            return False

        return self.re_param_section.search(self.doc) is not None

    def has_returns(self) -> bool:
        if not self.doc:
            return False

        entries = self._parse_section(self.re_returns_section)
        for entry in entries:
            match = self.re_returns_line.match(entry)
            if not match:
                continue

            return_desc = match.group(2)
            if return_desc:
                return True

        return False

    def has_rtype(self) -> bool:
        if not self.doc:
            return False

        entries = self._parse_section(self.re_returns_section)
        for entry in entries:
            match = self.re_returns_line.match(entry)
            if not match:
                continue

            return_type = match.group(1)
            if return_type:
                return True

        return False

    def has_property_returns(self) -> bool:
        # The summary line is the return doc,
        # so the first line must not be a known directive.
        first_line = self._first_line()
        return not bool(
            self.re_param_section.search(first_line)
            or self.re_raise_section.search(first_line)
            or self.re_returns_section.search(first_line)
            or self.re_yields_section.search(first_line)
        )

    def has_property_type(self) -> bool:
        if not self.doc:
            return False

        return bool(self.re_property_returns_line.match(self._first_line()))

    def has_yields(self) -> bool:
        if not self.doc:
            return False

        entries = self._parse_section(self.re_yields_section)
        for entry in entries:
            match = self.re_yields_line.match(entry)
            if not match:
                continue

            yield_desc = match.group(2)
            if yield_desc:
                return True

        return False

    def has_yields_type(self) -> bool:
        if not self.doc:
            return False

        entries = self._parse_section(self.re_yields_section)
        for entry in entries:
            match = self.re_yields_line.match(entry)
            if not match:
                continue

            yield_type = match.group(1)
            if yield_type:
                return True

        return False

    def exceptions(self) -> set[str]:
        types: set[str] = set()

        entries = self._parse_section(self.re_raise_section)
        for entry in entries:
            match = self.re_raise_line.match(entry)
            if not match:
                continue

            exc_type = match.group(1)
            exc_desc = match.group(2)
            if exc_desc:
                types.update(_split_multiple_exc_types(exc_type))

        return types

    def match_param_docs(self) -> tuple[set[str], set[str]]:
        params_with_doc: set[str] = set()
        params_with_type: set[str] = set()

        entries = self._parse_section(self.re_param_section)
        entries.extend(self._parse_section(self.re_keyword_param_section))
        for entry in entries:
            match = self.re_param_line.match(entry)
            if not match:
                continue

            param_name = match.group(1)
            # Remove escape characters necessary for asterisks
            param_name = param_name.replace("\\", "")

            param_type = match.group(2)
            param_desc = match.group(3)

            if param_type:
                params_with_type.add(param_name)

            if param_desc:
                params_with_doc.add(param_name)

        return params_with_doc, params_with_type

    def _first_line(self) -> str:
        return self.doc.lstrip().split("\n", 1)[0]

    @staticmethod
    def min_section_indent(section_match: re.Match[str]) -> int:
        return len(section_match.group(1)) + 1

    @staticmethod
    def _is_section_header(_: str) -> bool:
        # Google parsing does not need to detect section headers,
        # because it works off of indentation level only
        return False

    def _parse_section(self, section_re: re.Pattern[str]) -> list[str]:
        section_match = section_re.search(self.doc)
        if section_match is None:
            return []

        min_indentation = self.min_section_indent(section_match)

        entries: list[str] = []
        entry: list[str] = []
        is_first = True
        for line in section_match.group(2).splitlines():
            if not line.strip():
                continue
            indentation = space_indentation(line)
            if indentation < min_indentation:
                break

            # The first line after the header defines the minimum
            # indentation.
            if is_first:
                min_indentation = indentation
                is_first = False

            if indentation == min_indentation:
                if self._is_section_header(line):
                    break
                # Lines with minimum indentation must contain the beginning
                # of a new parameter documentation.
                if entry:
                    entries.append("\n".join(entry))
                    entry = []

            entry.append(line)

        if entry:
            entries.append("\n".join(entry))

        return entries


class NumpyDocstring(GoogleDocstring):
    _re_section_template = r"""
        ^([ ]*)   {0}   \s*?$          # Numpy parameters header
        \s*     [-=]+   \s*?$          # underline
        (  .* )                        # section
    """

    re_param_section = re.compile(
        _re_section_template.format(r"(?:Args|Arguments|Parameters)"),
        re.X | re.S | re.M,
    )

    re_default_value = r"""((['"]\w+\s*['"])|(\d+)|(True)|(False)|(None))"""

    re_param_line = re.compile(
        rf"""
        \s*  (?P<param_name>\*{{0,2}}\w+)(\s?(:|\n)) # identifier with potential asterisks
        \s*
        (?P<param_type>
         (
          ({GoogleDocstring.re_multiple_type})      # default type declaration
          (,\s+optional)?                           # optional 'optional' indication
         )?
         (
          {{({re_default_value},?\s*)+}}            # set of default values
         )?
         (?:$|\n)
        )?
        (
         \s* (?P<param_desc>.*)                     # optional description
        )?
    """,
        re.X | re.S,
    )

    re_raise_section = re.compile(
        _re_section_template.format(r"Raises"), re.X | re.S | re.M
    )

    re_raise_line = re.compile(
        rf"""
        \s* ({GoogleDocstring.re_type})$   # type declaration
        \s* (.*)                           # optional description
    """,
        re.X | re.S | re.M,
    )

    re_returns_section = re.compile(
        _re_section_template.format(r"Returns?"), re.X | re.S | re.M
    )

    re_returns_line = re.compile(
        rf"""
        \s* (?:\w+\s+:\s+)? # optional name
        ({GoogleDocstring.re_multiple_type})$   # type declaration
        \s* (.*)                                # optional description
    """,
        re.X | re.S | re.M,
    )

    re_yields_section = re.compile(
        _re_section_template.format(r"Yields?"), re.X | re.S | re.M
    )

    re_yields_line = re_returns_line

    supports_yields = True

    def match_param_docs(self) -> tuple[set[str], set[str]]:
        """Matches parameter documentation section to parameter documentation rules."""
        params_with_doc = set()
        params_with_type = set()

        entries = self._parse_section(self.re_param_section)
        entries.extend(self._parse_section(self.re_keyword_param_section))
        for entry in entries:
            match = self.re_param_line.match(entry)
            if not match:
                continue

            # check if parameter has description only
            re_only_desc = re.match(r"\s*(\*{0,2}\w+)\s*:?\n\s*\w*$", entry)
            if re_only_desc:
                param_name = match.group("param_name")
                param_desc = match.group("param_type")
                param_type = None
            else:
                param_name = match.group("param_name")
                param_type = match.group("param_type")
                param_desc = match.group("param_desc")
                # The re_param_line pattern needs to match multi-line which removes the ability
                # to match a single line description like 'arg : a number type.'
                # We are not trying to determine whether 'a number type' is correct typing
                # but we do accept it as typing as it is in the place where typing
                # should be
                if param_type is None and re.match(r"\s*(\*{0,2}\w+)\s*:.+$", entry):
                    param_type = param_desc
                # If the description is "" but we have a type description
                # we consider the description to be the type
                if not param_desc and param_type:
                    param_desc = param_type

            if param_type:
                params_with_type.add(param_name)

            if param_desc:
                params_with_doc.add(param_name)

        return params_with_doc, params_with_type

    @staticmethod
    def min_section_indent(section_match: re.Match[str]) -> int:
        return len(section_match.group(1))

    @staticmethod
    def _is_section_header(line: str) -> bool:
        return bool(re.match(r"\s*-+$", line))


DOCSTRING_TYPES = {
    "sphinx": SphinxDocstring,
    "epytext": EpytextDocstring,
    "google": GoogleDocstring,
    "numpy": NumpyDocstring,
    "default": Docstring,
}
"""A map of the name of the docstring type to its class.

:type: dict(str, type)
"""
