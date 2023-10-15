"""
This file contain the global astroid MANAGER.

It prevents a circular import that happened
when the only possibility to import it was from astroid.__init__.py.

This AstroidManager is a singleton/borg so it's possible to instantiate an
AstroidManager() directly.
"""

# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

from astroid.manager import AstroidManager

MANAGER = AstroidManager()
