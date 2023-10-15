# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""
Astroid hooks for numpy.core.einsumfunc module:
https://github.com/numpy/numpy/blob/main/numpy/core/einsumfunc.py.
"""

from astroid import nodes
from astroid.brain.helpers import register_module_extender
from astroid.builder import parse
from astroid.manager import AstroidManager


def numpy_core_einsumfunc_transform() -> nodes.Module:
    return parse(
        """
    def einsum(*operands, out=None, optimize=False, **kwargs):
        return numpy.ndarray([0, 0])
    """
    )


register_module_extender(
    AstroidManager(), "numpy.core.einsumfunc", numpy_core_einsumfunc_transform
)
