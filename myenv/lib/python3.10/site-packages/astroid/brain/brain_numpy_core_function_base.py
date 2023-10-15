# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""Astroid hooks for numpy.core.function_base module."""

import functools

from astroid.brain.brain_numpy_utils import infer_numpy_member, looks_like_numpy_member
from astroid.inference_tip import inference_tip
from astroid.manager import AstroidManager
from astroid.nodes.node_classes import Attribute

METHODS_TO_BE_INFERRED = {
    "linspace": """def linspace(start, stop, num=50, endpoint=True, retstep=False, dtype=None, axis=0):
            return numpy.ndarray([0, 0])""",
    "logspace": """def logspace(start, stop, num=50, endpoint=True, base=10.0, dtype=None, axis=0):
            return numpy.ndarray([0, 0])""",
    "geomspace": """def geomspace(start, stop, num=50, endpoint=True, dtype=None, axis=0):
            return numpy.ndarray([0, 0])""",
}

for func_name, func_src in METHODS_TO_BE_INFERRED.items():
    inference_function = functools.partial(infer_numpy_member, func_src)
    AstroidManager().register_transform(
        Attribute,
        inference_tip(inference_function),
        functools.partial(looks_like_numpy_member, func_name),
    )
