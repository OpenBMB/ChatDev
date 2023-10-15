# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Micro reports objects.

A micro report is a tree of layout and content objects.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any, Callable, TypeVar

from pylint.reporters.ureports.base_writer import BaseWriter

_T = TypeVar("_T")
_VNodeT = TypeVar("_VNodeT", bound="VNode")
VisitLeaveFunction = Callable[[_T, Any, Any], None]


class VNode:
    def __init__(self) -> None:
        self.parent: BaseLayout | None = None
        self.children: list[VNode] = []
        self.visitor_name: str = self.__class__.__name__.lower()

    def __iter__(self) -> Iterator[VNode]:
        return iter(self.children)

    def accept(self: _VNodeT, visitor: BaseWriter, *args: Any, **kwargs: Any) -> None:
        func: VisitLeaveFunction[_VNodeT] = getattr(
            visitor, f"visit_{self.visitor_name}"
        )
        return func(self, *args, **kwargs)

    def leave(self: _VNodeT, visitor: BaseWriter, *args: Any, **kwargs: Any) -> None:
        func: VisitLeaveFunction[_VNodeT] = getattr(
            visitor, f"leave_{self.visitor_name}"
        )
        return func(self, *args, **kwargs)


class BaseLayout(VNode):
    """Base container node.

    attributes
    * children : components in this table (i.e. the table's cells)
    """

    def __init__(self, children: Iterable[Text | str] = ()) -> None:
        super().__init__()
        for child in children:
            if isinstance(child, VNode):
                self.append(child)
            else:
                self.add_text(child)

    def append(self, child: VNode) -> None:
        """Add a node to children."""
        assert child not in self.parents()
        self.children.append(child)
        child.parent = self

    def insert(self, index: int, child: VNode) -> None:
        """Insert a child node."""
        self.children.insert(index, child)
        child.parent = self

    def parents(self) -> list[BaseLayout]:
        """Return the ancestor nodes."""
        assert self.parent is not self
        if self.parent is None:
            return []
        return [self.parent] + self.parent.parents()

    def add_text(self, text: str) -> None:
        """Shortcut to add text data."""
        self.children.append(Text(text))


# non container nodes #########################################################


class Text(VNode):
    """A text portion.

    attributes :
    * data : the text value as an encoded or unicode string
    """

    def __init__(self, data: str, escaped: bool = True) -> None:
        super().__init__()
        self.escaped = escaped
        self.data = data


class VerbatimText(Text):
    """A verbatim text, display the raw data.

    attributes :
    * data : the text value as an encoded or unicode string
    """


# container nodes #############################################################


class Section(BaseLayout):
    """A section.

    attributes :
    * BaseLayout attributes

    a title may also be given to the constructor, it'll be added
    as a first element
    a description may also be given to the constructor, it'll be added
    as a first paragraph
    """

    def __init__(
        self,
        title: str | None = None,
        description: str | None = None,
        children: Iterable[Text | str] = (),
    ) -> None:
        super().__init__(children=children)
        if description:
            self.insert(0, Paragraph([Text(description)]))
        if title:
            self.insert(0, Title(children=(title,)))
        self.report_id: str = ""  # Used in ReportHandlerMixin.make_reports


class EvaluationSection(Section):
    def __init__(self, message: str, children: Iterable[Text | str] = ()) -> None:
        super().__init__(children=children)
        title = Paragraph()
        title.append(Text("-" * len(message)))
        self.append(title)
        message_body = Paragraph()
        message_body.append(Text(message))
        self.append(message_body)


class Title(BaseLayout):
    """A title.

    attributes :
    * BaseLayout attributes

    A title must not contain a section nor a paragraph!
    """


class Paragraph(BaseLayout):
    """A simple text paragraph.

    attributes :
    * BaseLayout attributes

    A paragraph must not contains a section !
    """


class Table(BaseLayout):
    """Some tabular data.

    attributes :
    * BaseLayout attributes
    * cols : the number of columns of the table (REQUIRED)
    * rheaders : the first row's elements are table's header
    * cheaders : the first col's elements are table's header
    * title : the table's optional title
    """

    def __init__(
        self,
        cols: int,
        title: str | None = None,
        rheaders: int = 0,
        cheaders: int = 0,
        children: Iterable[Text | str] = (),
    ) -> None:
        super().__init__(children=children)
        assert isinstance(cols, int)
        self.cols = cols
        self.title = title
        self.rheaders = rheaders
        self.cheaders = cheaders
