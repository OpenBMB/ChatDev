# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""Astroid hooks for unittest module."""
from astroid.brain.helpers import register_module_extender
from astroid.builder import parse
from astroid.const import PY38_PLUS
from astroid.manager import AstroidManager


def IsolatedAsyncioTestCaseImport():
    """
    In the unittest package, the IsolatedAsyncioTestCase class is imported lazily.

    I.E. only when the ``__getattr__`` method of the unittest module is called with
    'IsolatedAsyncioTestCase' as argument. Thus the IsolatedAsyncioTestCase
    is not imported statically (during import time).
    This function mocks a classical static import of the IsolatedAsyncioTestCase.

    (see https://github.com/PyCQA/pylint/issues/4060)
    """
    return parse(
        """
    from .async_case import IsolatedAsyncioTestCase
    """
    )


if PY38_PLUS:
    register_module_extender(
        AstroidManager(), "unittest", IsolatedAsyncioTestCaseImport
    )
