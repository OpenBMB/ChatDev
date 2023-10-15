# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Interfaces for Pylint objects."""

from __future__ import annotations

import warnings
from tokenize import TokenInfo
from typing import TYPE_CHECKING, NamedTuple

from astroid import nodes

if TYPE_CHECKING:
    from pylint.checkers import BaseChecker
    from pylint.message import Message
    from pylint.reporters.ureports.nodes import Section

__all__ = (
    "IRawChecker",
    "IAstroidChecker",
    "ITokenChecker",
    "IReporter",
    "IChecker",
    "HIGH",
    "CONTROL_FLOW",
    "INFERENCE",
    "INFERENCE_FAILURE",
    "UNDEFINED",
    "CONFIDENCE_LEVELS",
    "CONFIDENCE_LEVEL_NAMES",
)


class Confidence(NamedTuple):
    name: str
    description: str


# Warning Certainties
HIGH = Confidence("HIGH", "Warning that is not based on inference result.")
CONTROL_FLOW = Confidence(
    "CONTROL_FLOW", "Warning based on assumptions about control flow."
)
INFERENCE = Confidence("INFERENCE", "Warning based on inference result.")
INFERENCE_FAILURE = Confidence(
    "INFERENCE_FAILURE", "Warning based on inference with failures."
)
UNDEFINED = Confidence("UNDEFINED", "Warning without any associated confidence level.")

CONFIDENCE_LEVELS = [HIGH, CONTROL_FLOW, INFERENCE, INFERENCE_FAILURE, UNDEFINED]
CONFIDENCE_LEVEL_NAMES = [i.name for i in CONFIDENCE_LEVELS]


class Interface:
    """Base class for interfaces."""

    def __init__(self) -> None:
        warnings.warn(
            "Interface and all of its subclasses have been deprecated "
            "and will be removed in pylint 3.0.",
            DeprecationWarning,
            stacklevel=2,
        )

    @classmethod
    def is_implemented_by(
        cls: type[Interface] | tuple[type[Interface], ...], instance: BaseChecker
    ) -> bool:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            return implements(instance, cls)


def implements(
    obj: BaseChecker,
    interface: type[Interface] | tuple[type[Interface], ...],
) -> bool:
    """Does the given object (maybe an instance or class) implement the interface."""
    # TODO: 3.0: Remove deprecated function
    warnings.warn(
        "implements has been deprecated in favour of using basic "
        "inheritance patterns without using __implements__.",
        DeprecationWarning,
        stacklevel=2,
    )
    implements_ = getattr(obj, "__implements__", ())
    if not isinstance(implements_, (list, tuple)):
        implements_ = (implements_,)
    return any(issubclass(i, interface) for i in implements_)


class IChecker(Interface):
    """Base interface, to be used only for sub interfaces definition."""

    def open(self) -> None:
        """Called before visiting project (i.e. set of modules)."""

    def close(self) -> None:
        """Called after visiting project (i.e. set of modules)."""


class IRawChecker(IChecker):
    """Interface for checker which need to parse the raw file."""

    def process_module(self, node: nodes.Module) -> None:
        """Process a module.

        The module's content is accessible via ``astroid.stream``
        """


class ITokenChecker(IChecker):
    """Interface for checkers that need access to the token list."""

    def process_tokens(self, tokens: list[TokenInfo]) -> None:
        """Process a module.

        Tokens is a list of all source code tokens in the file.
        """


class IAstroidChecker(IChecker):
    """Interface for checker which prefers receive events according to
    statement type.
    """


class IReporter(Interface):
    """Reporter collect messages and display results encapsulated in a layout."""

    def handle_message(self, msg: Message) -> None:
        """Handle the given message object."""

    def display_reports(self, layout: Section) -> None:
        """Display results encapsulated in the layout tree."""
