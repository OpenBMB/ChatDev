# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""
Astroid hooks for ctypes module.

Inside the ctypes module, the value class is defined inside
the C coded module _ctypes.
Thus astroid doesn't know that the value member is a builtin type
among float, int, bytes or str.
"""
import sys

from astroid.brain.helpers import register_module_extender
from astroid.builder import parse
from astroid.manager import AstroidManager


def enrich_ctypes_redefined_types():
    """
    For each ctypes redefined types, overload 'value' and '_type_' members
    definition.

    Overloading 'value' is mandatory otherwise astroid cannot infer the correct type for it.
    Overloading '_type_' is necessary because the class definition made here replaces the original
    one, in which '_type_' member is defined. Luckily those original class definitions are very short
    and contain only the '_type_' member definition.
    """
    c_class_to_type = (
        ("c_byte", "int", "b"),
        ("c_char", "bytes", "c"),
        ("c_double", "float", "d"),
        ("c_float", "float", "f"),
        ("c_int", "int", "i"),
        ("c_int16", "int", "h"),
        ("c_int32", "int", "i"),
        ("c_int64", "int", "l"),
        ("c_int8", "int", "b"),
        ("c_long", "int", "l"),
        ("c_longdouble", "float", "g"),
        ("c_longlong", "int", "l"),
        ("c_short", "int", "h"),
        ("c_size_t", "int", "L"),
        ("c_ssize_t", "int", "l"),
        ("c_ubyte", "int", "B"),
        ("c_uint", "int", "I"),
        ("c_uint16", "int", "H"),
        ("c_uint32", "int", "I"),
        ("c_uint64", "int", "L"),
        ("c_uint8", "int", "B"),
        ("c_ulong", "int", "L"),
        ("c_ulonglong", "int", "L"),
        ("c_ushort", "int", "H"),
        ("c_wchar", "str", "u"),
    )

    src = [
        """
from _ctypes import _SimpleCData

class c_bool(_SimpleCData):
    def __init__(self, value):
        self.value = True
        self._type_ = '?'
    """
    ]

    for c_type, builtin_type, type_code in c_class_to_type:
        src.append(
            f"""
class {c_type}(_SimpleCData):
    def __init__(self, value):
        self.value = {builtin_type}(value)
        self._type_ = '{type_code}'
        """
        )

    return parse("\n".join(src))


if not hasattr(sys, "pypy_version_info"):
    # No need of this module in pypy where everything is written in python
    register_module_extender(AstroidManager(), "ctypes", enrich_ctypes_redefined_types)
