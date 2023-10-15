# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""Astroid hooks for the Python 2 GObject introspection bindings.

Helps with understanding everything imported from 'gi.repository'
"""

# pylint:disable=import-error,import-outside-toplevel

import inspect
import itertools
import re
import sys
import warnings

from astroid import nodes
from astroid.builder import AstroidBuilder
from astroid.exceptions import AstroidBuildingError
from astroid.manager import AstroidManager

_inspected_modules = {}

_identifier_re = r"^[A-Za-z_]\w*$"

_special_methods = frozenset(
    {
        "__lt__",
        "__le__",
        "__eq__",
        "__ne__",
        "__ge__",
        "__gt__",
        "__iter__",
        "__getitem__",
        "__setitem__",
        "__delitem__",
        "__len__",
        "__bool__",
        "__nonzero__",
        "__next__",
        "__str__",
        "__contains__",
        "__enter__",
        "__exit__",
        "__repr__",
        "__getattr__",
        "__setattr__",
        "__delattr__",
        "__del__",
        "__hash__",
    }
)


def _gi_build_stub(parent):  # noqa: C901
    """
    Inspect the passed module recursively and build stubs for functions,
    classes, etc.
    """
    classes = {}
    functions = {}
    constants = {}
    methods = {}
    for name in dir(parent):
        if name.startswith("__") and name not in _special_methods:
            continue

        # Check if this is a valid name in python
        if not re.match(_identifier_re, name):
            continue

        try:
            obj = getattr(parent, name)
        except Exception:  # pylint: disable=broad-except
            # gi.module.IntrospectionModule.__getattr__() can raise all kinds of things
            # like ValueError, TypeError, NotImplementedError, RepositoryError, etc
            continue

        if inspect.isclass(obj):
            classes[name] = obj
        elif inspect.isfunction(obj) or inspect.isbuiltin(obj):
            functions[name] = obj
        elif inspect.ismethod(obj) or inspect.ismethoddescriptor(obj):
            methods[name] = obj
        elif (
            str(obj).startswith("<flags")
            or str(obj).startswith("<enum ")
            or str(obj).startswith("<GType ")
            or inspect.isdatadescriptor(obj)
        ):
            constants[name] = 0
        elif isinstance(obj, (int, str)):
            constants[name] = obj
        elif callable(obj):
            # Fall back to a function for anything callable
            functions[name] = obj
        else:
            # Assume everything else is some manner of constant
            constants[name] = 0

    ret = ""

    if constants:
        ret += f"# {parent.__name__} constants\n\n"
    for name in sorted(constants):
        if name[0].isdigit():
            # GDK has some busted constant names like
            # Gdk.EventType.2BUTTON_PRESS
            continue

        val = constants[name]

        strval = str(val)
        if isinstance(val, str):
            strval = '"%s"' % str(val).replace("\\", "\\\\")
        ret += f"{name} = {strval}\n"

    if ret:
        ret += "\n\n"
    if functions:
        ret += f"# {parent.__name__} functions\n\n"
    for name in sorted(functions):
        ret += f"def {name}(*args, **kwargs):\n"
        ret += "    pass\n"

    if ret:
        ret += "\n\n"
    if methods:
        ret += f"# {parent.__name__} methods\n\n"
    for name in sorted(methods):
        ret += f"def {name}(self, *args, **kwargs):\n"
        ret += "    pass\n"

    if ret:
        ret += "\n\n"
    if classes:
        ret += f"# {parent.__name__} classes\n\n"
    for name, obj in sorted(classes.items()):
        base = "object"
        if issubclass(obj, Exception):
            base = "Exception"
        ret += f"class {name}({base}):\n"

        classret = _gi_build_stub(obj)
        if not classret:
            classret = "pass\n"

        for line in classret.splitlines():
            ret += "    " + line + "\n"
        ret += "\n"

    return ret


def _import_gi_module(modname):
    # we only consider gi.repository submodules
    if not modname.startswith("gi.repository."):
        raise AstroidBuildingError(modname=modname)
    # build astroid representation unless we already tried so
    if modname not in _inspected_modules:
        modnames = [modname]
        optional_modnames = []

        # GLib and GObject may have some special case handling
        # in pygobject that we need to cope with. However at
        # least as of pygobject3-3.13.91 the _glib module doesn't
        # exist anymore, so if treat these modules as optional.
        if modname == "gi.repository.GLib":
            optional_modnames.append("gi._glib")
        elif modname == "gi.repository.GObject":
            optional_modnames.append("gi._gobject")

        try:
            modcode = ""
            for m in itertools.chain(modnames, optional_modnames):
                try:
                    with warnings.catch_warnings():
                        # Just inspecting the code can raise gi deprecation
                        # warnings, so ignore them.
                        try:
                            from gi import (  # pylint:disable=import-error
                                PyGIDeprecationWarning,
                                PyGIWarning,
                            )

                            warnings.simplefilter("ignore", PyGIDeprecationWarning)
                            warnings.simplefilter("ignore", PyGIWarning)
                        except Exception:  # pylint:disable=broad-except
                            pass

                        __import__(m)
                        modcode += _gi_build_stub(sys.modules[m])
                except ImportError:
                    if m not in optional_modnames:
                        raise
        except ImportError:
            astng = _inspected_modules[modname] = None
        else:
            astng = AstroidBuilder(AstroidManager()).string_build(modcode, modname)
            _inspected_modules[modname] = astng
    else:
        astng = _inspected_modules[modname]
    if astng is None:
        raise AstroidBuildingError(modname=modname)
    return astng


def _looks_like_require_version(node) -> bool:
    # Return whether this looks like a call to gi.require_version(<name>, <version>)
    # Only accept function calls with two constant arguments
    if len(node.args) != 2:
        return False

    if not all(isinstance(arg, nodes.Const) for arg in node.args):
        return False

    func = node.func
    if isinstance(func, nodes.Attribute):
        if func.attrname != "require_version":
            return False
        if isinstance(func.expr, nodes.Name) and func.expr.name == "gi":
            return True

        return False

    if isinstance(func, nodes.Name):
        return func.name == "require_version"

    return False


def _register_require_version(node):
    # Load the gi.require_version locally
    try:
        import gi

        gi.require_version(node.args[0].value, node.args[1].value)
    except Exception:  # pylint:disable=broad-except
        pass

    return node


AstroidManager().register_failed_import_hook(_import_gi_module)
AstroidManager().register_transform(
    nodes.Call, _register_require_version, _looks_like_require_version
)
