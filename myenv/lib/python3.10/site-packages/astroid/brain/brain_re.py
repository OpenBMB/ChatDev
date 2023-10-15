# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

from astroid import context, inference_tip, nodes
from astroid.brain.helpers import register_module_extender
from astroid.builder import _extract_single_node, parse
from astroid.const import PY39_PLUS, PY311_PLUS
from astroid.manager import AstroidManager


def _re_transform() -> nodes.Module:
    # The RegexFlag enum exposes all its entries by updating globals()
    # In 3.6-3.10 all flags come from sre_compile
    # On 3.11+ all flags come from re._compiler
    if PY311_PLUS:
        import_compiler = "import re._compiler as _compiler"
    else:
        import_compiler = "import sre_compile as _compiler"
    return parse(
        f"""
    {import_compiler}
    NOFLAG = 0
    ASCII = _compiler.SRE_FLAG_ASCII
    IGNORECASE = _compiler.SRE_FLAG_IGNORECASE
    LOCALE = _compiler.SRE_FLAG_LOCALE
    UNICODE = _compiler.SRE_FLAG_UNICODE
    MULTILINE = _compiler.SRE_FLAG_MULTILINE
    DOTALL = _compiler.SRE_FLAG_DOTALL
    VERBOSE = _compiler.SRE_FLAG_VERBOSE
    TEMPLATE = _compiler.SRE_FLAG_TEMPLATE
    DEBUG = _compiler.SRE_FLAG_DEBUG
    A = ASCII
    I = IGNORECASE
    L = LOCALE
    U = UNICODE
    M = MULTILINE
    S = DOTALL
    X = VERBOSE
    T = TEMPLATE
    """
    )


register_module_extender(AstroidManager(), "re", _re_transform)


CLASS_GETITEM_TEMPLATE = """
@classmethod
def __class_getitem__(cls, item):
    return cls
"""


def _looks_like_pattern_or_match(node: nodes.Call) -> bool:
    """Check for re.Pattern or re.Match call in stdlib.

    Match these patterns from stdlib/re.py
    ```py
    Pattern = type(...)
    Match = type(...)
    ```
    """
    return (
        node.root().name == "re"
        and isinstance(node.func, nodes.Name)
        and node.func.name == "type"
        and isinstance(node.parent, nodes.Assign)
        and len(node.parent.targets) == 1
        and isinstance(node.parent.targets[0], nodes.AssignName)
        and node.parent.targets[0].name in {"Pattern", "Match"}
    )


def infer_pattern_match(node: nodes.Call, ctx: context.InferenceContext | None = None):
    """Infer re.Pattern and re.Match as classes.

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
