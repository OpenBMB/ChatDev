# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""
Astroid hook for the Hypothesis library.

Without this hook pylint reports no-value-for-parameter for use of strategies
defined using the `@hypothesis.strategies.composite` decorator.  For example:

    from hypothesis import strategies as st

    @st.composite
    def a_strategy(draw):
        return draw(st.integers())

    a_strategy()
"""
from astroid.manager import AstroidManager
from astroid.nodes.scoped_nodes import FunctionDef

COMPOSITE_NAMES = (
    "composite",
    "st.composite",
    "strategies.composite",
    "hypothesis.strategies.composite",
)


def is_decorated_with_st_composite(node) -> bool:
    """Return whether a decorated node has @st.composite applied."""
    if node.decorators and node.args.args and node.args.args[0].name == "draw":
        for decorator_attribute in node.decorators.nodes:
            if decorator_attribute.as_string() in COMPOSITE_NAMES:
                return True
    return False


def remove_draw_parameter_from_composite_strategy(node):
    """Given that the FunctionDef is decorated with @st.composite, remove the
    first argument (`draw`) - it's always supplied by Hypothesis so we don't
    need to emit the no-value-for-parameter lint.
    """
    del node.args.args[0]
    del node.args.annotations[0]
    del node.args.type_comment_args[0]
    return node


AstroidManager().register_transform(
    node_class=FunctionDef,
    transform=remove_draw_parameter_from_composite_strategy,
    predicate=is_decorated_with_st_composite,
)
