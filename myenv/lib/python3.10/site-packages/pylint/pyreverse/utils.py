# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/pylint/blob/main/CONTRIBUTORS.txt

"""Generic classes/functions for pyreverse core/extensions."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from typing import TYPE_CHECKING, Any, Callable, Optional, Tuple, Union

import astroid
from astroid import nodes
from astroid.typing import InferenceResult

if TYPE_CHECKING:
    from pylint.pyreverse.diagrams import ClassDiagram, PackageDiagram

    _CallbackT = Callable[
        [nodes.NodeNG],
        Union[Tuple[ClassDiagram], Tuple[PackageDiagram, ClassDiagram], None],
    ]
    _CallbackTupleT = Tuple[Optional[_CallbackT], Optional[_CallbackT]]


RCFILE = ".pyreverserc"


def get_default_options() -> list[str]:
    """Read config file and return list of options."""
    options = []
    home = os.environ.get("HOME", "")
    if home:
        rcfile = os.path.join(home, RCFILE)
        try:
            with open(rcfile, encoding="utf-8") as file_handle:
                options = file_handle.read().split()
        except OSError:
            pass  # ignore if no config file found
    return options


def insert_default_options() -> None:
    """Insert default options to sys.argv."""
    options = get_default_options()
    options.reverse()
    for arg in options:
        sys.argv.insert(1, arg)


# astroid utilities ###########################################################
SPECIAL = re.compile(r"^__([^\W_]_*)+__$")
PRIVATE = re.compile(r"^__(_*[^\W_])+_?$")
PROTECTED = re.compile(r"^_\w*$")


def get_visibility(name: str) -> str:
    """Return the visibility from a name: public, protected, private or special."""
    if SPECIAL.match(name):
        visibility = "special"
    elif PRIVATE.match(name):
        visibility = "private"
    elif PROTECTED.match(name):
        visibility = "protected"

    else:
        visibility = "public"
    return visibility


def is_interface(node: nodes.ClassDef) -> bool:
    # bw compatibility
    return node.type == "interface"  # type: ignore[no-any-return]


def is_exception(node: nodes.ClassDef) -> bool:
    # bw compatibility
    return node.type == "exception"  # type: ignore[no-any-return]


# Helpers #####################################################################

_SPECIAL = 2
_PROTECTED = 4
_PRIVATE = 8
MODES = {
    "ALL": 0,
    "PUB_ONLY": _SPECIAL + _PROTECTED + _PRIVATE,
    "SPECIAL": _SPECIAL,
    "OTHER": _PROTECTED + _PRIVATE,
}
VIS_MOD = {
    "special": _SPECIAL,
    "protected": _PROTECTED,
    "private": _PRIVATE,
    "public": 0,
}


class FilterMixIn:
    """Filter nodes according to a mode and nodes' visibility."""

    def __init__(self, mode: str) -> None:
        """Init filter modes."""
        __mode = 0
        for nummod in mode.split("+"):
            try:
                __mode += MODES[nummod]
            except KeyError as ex:
                print(f"Unknown filter mode {ex}", file=sys.stderr)
        self.__mode = __mode

    def show_attr(self, node: nodes.NodeNG | str) -> bool:
        """Return true if the node should be treated."""
        visibility = get_visibility(getattr(node, "name", node))
        return not self.__mode & VIS_MOD[visibility]


class LocalsVisitor:
    """Visit a project by traversing the locals dictionary.

    * visit_<class name> on entering a node, where class name is the class of
    the node in lower case

    * leave_<class name> on leaving a node, where class name is the class of
    the node in lower case
    """

    def __init__(self) -> None:
        self._cache: dict[type[nodes.NodeNG], _CallbackTupleT] = {}
        self._visited: set[nodes.NodeNG] = set()

    def get_callbacks(self, node: nodes.NodeNG) -> _CallbackTupleT:
        """Get callbacks from handler for the visited node."""
        klass = node.__class__
        methods = self._cache.get(klass)
        if methods is None:
            kid = klass.__name__.lower()
            e_method = getattr(
                self, f"visit_{kid}", getattr(self, "visit_default", None)
            )
            l_method = getattr(
                self, f"leave_{kid}", getattr(self, "leave_default", None)
            )
            self._cache[klass] = (e_method, l_method)
        else:
            e_method, l_method = methods
        return e_method, l_method

    def visit(self, node: nodes.NodeNG) -> Any:
        """Launch the visit starting from the given node."""
        if node in self._visited:
            return None

        self._visited.add(node)
        methods = self.get_callbacks(node)
        if methods[0] is not None:
            methods[0](node)
        if hasattr(node, "locals"):  # skip Instance and other proxy
            for local_node in node.values():
                self.visit(local_node)
        if methods[1] is not None:
            return methods[1](node)
        return None


def get_annotation_label(ann: nodes.Name | nodes.NodeNG) -> str:
    if isinstance(ann, nodes.Name) and ann.name is not None:
        return ann.name  # type: ignore[no-any-return]
    if isinstance(ann, nodes.NodeNG):
        return ann.as_string()  # type: ignore[no-any-return]
    return ""


def get_annotation(
    node: nodes.AssignAttr | nodes.AssignName,
) -> nodes.Name | nodes.Subscript | None:
    """Return the annotation for `node`."""
    ann = None
    if isinstance(node.parent, nodes.AnnAssign):
        ann = node.parent.annotation
    elif isinstance(node, nodes.AssignAttr):
        init_method = node.parent.parent
        try:
            annotations = dict(zip(init_method.locals, init_method.args.annotations))
            ann = annotations.get(node.parent.value.name)
        except AttributeError:
            pass
    else:
        return ann

    try:
        default, *_ = node.infer()
    except astroid.InferenceError:
        default = ""

    label = get_annotation_label(ann)
    if ann:
        label = (
            rf"Optional[{label}]"
            if getattr(default, "value", "value") is None
            and not label.startswith("Optional")
            else label
        )
    if label:
        ann.name = label
    return ann


def infer_node(node: nodes.AssignAttr | nodes.AssignName) -> set[InferenceResult]:
    """Return a set containing the node annotation if it exists
    otherwise return a set of the inferred types using the NodeNG.infer method.
    """

    ann = get_annotation(node)
    try:
        if ann:
            if isinstance(ann, nodes.Subscript) or (
                isinstance(ann, nodes.BinOp) and ann.op == "|"
            ):
                return {ann}
            return set(ann.infer())
        return set(node.infer())
    except astroid.InferenceError:
        return {ann} if ann else set()


def check_graphviz_availability() -> None:
    """Check if the ``dot`` command is available on the machine.

    This is needed if image output is desired and ``dot`` is used to convert
    from *.dot or *.gv into the final output format.
    """
    if shutil.which("dot") is None:
        print("'Graphviz' needs to be installed for your chosen output format.")
        sys.exit(32)


def check_if_graphviz_supports_format(output_format: str) -> None:
    """Check if the ``dot`` command supports the requested output format.

    This is needed if image output is desired and ``dot`` is used to convert
    from *.gv into the final output format.
    """
    dot_output = subprocess.run(
        ["dot", "-T?"], capture_output=True, check=False, encoding="utf-8"
    )
    match = re.match(
        pattern=r".*Use one of: (?P<formats>(\S*\s?)+)",
        string=dot_output.stderr.strip(),
    )
    if not match:
        print(
            "Unable to determine Graphviz supported output formats. "
            "Pyreverse will continue, but subsequent error messages "
            "regarding the output format may come from Graphviz directly."
        )
        return
    supported_formats = match.group("formats")
    if output_format not in supported_formats.split():
        print(
            f"Format {output_format} is not supported by Graphviz. It supports: {supported_formats}"
        )
        sys.exit(32)
