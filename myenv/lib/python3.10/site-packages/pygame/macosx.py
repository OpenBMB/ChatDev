import platform
import os
import sys

__all__ = ["Video_AutoInit"]


def Video_AutoInit():
    """Called from the base.c just before display module is initialized."""
    if "Darwin" in platform.platform():
        if (os.getcwd() == "/") and len(sys.argv) > 1:
            os.chdir(os.path.dirname(sys.argv[0]))
    return True
