# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""Astroid hooks for numpy.core.multiarray module."""

import functools

from astroid.brain.brain_numpy_utils import infer_numpy_member, looks_like_numpy_member
from astroid.brain.helpers import register_module_extender
from astroid.builder import parse
from astroid.inference_tip import inference_tip
from astroid.manager import AstroidManager
from astroid.nodes.node_classes import Attribute, Name


def numpy_core_multiarray_transform():
    return parse(
        """
    # different functions defined in multiarray.py
    def inner(a, b):
        return numpy.ndarray([0, 0])

    def vdot(a, b):
        return numpy.ndarray([0, 0])
        """
    )


register_module_extender(
    AstroidManager(), "numpy.core.multiarray", numpy_core_multiarray_transform
)


METHODS_TO_BE_INFERRED = {
    "array": """def array(object, dtype=None, copy=True, order='K', subok=False, ndmin=0):
            return numpy.ndarray([0, 0])""",
    "dot": """def dot(a, b, out=None):
            return numpy.ndarray([0, 0])""",
    "empty_like": """def empty_like(a, dtype=None, order='K', subok=True):
            return numpy.ndarray((0, 0))""",
    "concatenate": """def concatenate(arrays, axis=None, out=None):
            return numpy.ndarray((0, 0))""",
    "where": """def where(condition, x=None, y=None):
            return numpy.ndarray([0, 0])""",
    "empty": """def empty(shape, dtype=float, order='C'):
            return numpy.ndarray([0, 0])""",
    "bincount": """def bincount(x, weights=None, minlength=0):
            return numpy.ndarray([0, 0])""",
    "busday_count": """def busday_count(
        begindates, enddates, weekmask='1111100', holidays=[], busdaycal=None, out=None
    ):
        return numpy.ndarray([0, 0])""",
    "busday_offset": """def busday_offset(
        dates, offsets, roll='raise', weekmask='1111100', holidays=None,
        busdaycal=None, out=None
    ):
        return numpy.ndarray([0, 0])""",
    "can_cast": """def can_cast(from_, to, casting='safe'):
            return True""",
    "copyto": """def copyto(dst, src, casting='same_kind', where=True):
            return None""",
    "datetime_as_string": """def datetime_as_string(arr, unit=None, timezone='naive', casting='same_kind'):
            return numpy.ndarray([0, 0])""",
    "is_busday": """def is_busday(dates, weekmask='1111100', holidays=None, busdaycal=None, out=None):
            return numpy.ndarray([0, 0])""",
    "lexsort": """def lexsort(keys, axis=-1):
            return numpy.ndarray([0, 0])""",
    "may_share_memory": """def may_share_memory(a, b, max_work=None):
            return True""",
    # Not yet available because dtype is not yet present in those brains
    #     "min_scalar_type": """def min_scalar_type(a):
    #             return numpy.dtype('int16')""",
    "packbits": """def packbits(a, axis=None, bitorder='big'):
            return numpy.ndarray([0, 0])""",
    # Not yet available because dtype is not yet present in those brains
    #     "result_type": """def result_type(*arrays_and_dtypes):
    #             return numpy.dtype('int16')""",
    "shares_memory": """def shares_memory(a, b, max_work=None):
            return True""",
    "unpackbits": """def unpackbits(a, axis=None, count=None, bitorder='big'):
            return numpy.ndarray([0, 0])""",
    "unravel_index": """def unravel_index(indices, shape, order='C'):
            return (numpy.ndarray([0, 0]),)""",
    "zeros": """def zeros(shape, dtype=float, order='C'):
            return numpy.ndarray([0, 0])""",
}

for method_name, function_src in METHODS_TO_BE_INFERRED.items():
    inference_function = functools.partial(infer_numpy_member, function_src)
    AstroidManager().register_transform(
        Attribute,
        inference_tip(inference_function),
        functools.partial(looks_like_numpy_member, method_name),
    )
    AstroidManager().register_transform(
        Name,
        inference_tip(inference_function),
        functools.partial(looks_like_numpy_member, method_name),
    )
