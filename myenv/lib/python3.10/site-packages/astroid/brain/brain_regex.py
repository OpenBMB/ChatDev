# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

from astroid import context, inference_tip, nodes
from astroid.brain.helpers import register_module_extender
from astroid.builder import _extract_single_node, parse
from astroid.const import PY39_PLUS
from astroid.manager import AstroidManager


def _regex_transform() -> nodes.Module:
    """The RegexFlag enum exposes all its entries by updating globals().

    We hard-code the flags for now.
    # pylint: disable-next=line-too-long
    See https://github.com/mrabarnett/mrab-regex/blob/2022.10.31/regex_3/regex.py#L200
    """
    return parse(
        """
    A = ASCII = 0x80          # Assume ASCII locale.
    B = BESTMATCH = 0x1000    # Best fuzzy match.
    D = DEBUG = 0x200         # Print parsed pattern.
    E = ENHANCEMATCH = 0x8000 # Attempt to improve the fit after finding the first
                              # fuzzy match.
    F = FULLCASE = 0x4000     # Unicode full case-folding.
    I = IGNORECASE = 0x2      # Ignore case.
    L = LOCALE = 0x4          # Assume current 8-bit locale.
    M = MULTILINE = 0x8       # Make anchors look for newline.
    P = POSIX = 0x10000       # POSIX-style matching (leftmost longest).
    R = REVERSE = 0x400       # Search backwards.
    S = DOTALL = 0x10         # Make dot match newline.
    U = UNICODE = 0x20        # Assume Unicode locale.
    V0 = VERSION0 = 0x2000    # Old legacy behaviour.
    DEFAULT_VERSION = V0
    V1 = VERSION1 = 0x100     # New enhanced behaviour.
    W = WORD = 0x800          # Default Unicode word breaks.
    X = VERBOSE = 0x40        # Ignore whitespace and comments.
    T = TEMPLATE = 0x1        # Template (present because re module has it).
    """
    )


register_module_extender(AstroidManager(), "regex", _regex_transform)


CLASS_GETITEM_TEMPLATE = """
@classmethod
def __class_getitem__(cls, item):
    return cls
"""


def _looks_like_pattern_or_match(node: nodes.Call) -> bool:
    """Check for regex.Pattern or regex.Match call in stdlib.

    Match these patterns from stdlib/re.py
    ```py
    Pattern = type(...)
    Match = type(...)
    ```
    """
    return (
        node.root().name == "regex.regex"
        and isinstance(node.func, nodes.Name)
        and node.func.name == "type"
        and isinstance(node.parent, nodes.Assign)
        and len(node.parent.targets) == 1
        and isinstance(node.parent.targets[0], nodes.AssignName)
        and node.parent.targets[0].name in {"Pattern", "Match"}
    )


def infer_pattern_match(node: nodes.Call, ctx: context.InferenceContext | None = None):
    """Infer regex.Pattern and regex.Match as classes.

    For PY39+ add `__class_getitem__`.
    """
    class_def = nodes.ClassDef(
        name=node.parent.targets[0].name,
        lineno=node.lineno,
        col_offset=node.col_offset,
        parent=node.parent,
    )
    if PY39_PLUS:
        func_to_add = _extract_single_node(CLASS_GETITEM_TEMPLATE)
        class_def.locals["__class_getitem__"] = [func_to_add]
    return iter([class_def])


AstroidManager().register_transform(
    nodes.Call, inference_tip(infer_pattern_match), _looks_like_pattern_or_match
)
