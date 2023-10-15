# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

from astroid.brain.helpers import register_module_extender
from astroid.builder import parse
from astroid.manager import AstroidManager


def _thread_transform():
    return parse(
        """
    class lock(object):
        def acquire(self, blocking=True, timeout=-1):
            return False
        def release(self):
            pass
        def __enter__(self):
            return True
        def __exit__(self, *args):
            pass
        def locked(self):
            return False

    def Lock(*args, **kwargs):
        return lock()
    """
    )


register_module_extender(AstroidManager(), "threading", _thread_transform)
