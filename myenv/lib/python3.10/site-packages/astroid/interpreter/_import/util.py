# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import pathlib
import sys
from functools import lru_cache
from importlib._bootstrap_external import _NamespacePath
from importlib.util import _find_spec_from_path  # type: ignore[attr-defined]

from astroid.const import IS_PYPY


@lru_cache(maxsize=4096)
def is_namespace(modname: str) -> bool:
    from astroid.modutils import (  # pylint: disable=import-outside-toplevel
        EXT_LIB_DIRS,
        STD_LIB_DIRS,
    )

    STD_AND_EXT_LIB_DIRS = STD_LIB_DIRS.union(EXT_LIB_DIRS)

    if modname in sys.builtin_module_names:
        return False

    found_spec = None

    # find_spec() attempts to import parent packages when given dotted paths.
    # That's unacceptable here, so we fallback to _find_spec_from_path(), which does
    # not, but requires instead that each single parent ('astroid', 'nodes', etc.)
    # be specced from left to right.
    processed_components = []
    last_submodule_search_locations: _NamespacePath | None = None
    for component in modname.split("."):
        processed_components.append(component)
        working_modname = ".".join(processed_components)
        try:
            # Both the modname and the path are built iteratively, with the
            # path (e.g. ['a', 'a/b', 'a/b/c']) lagging the modname by one
            found_spec = _find_spec_from_path(
                working_modname, path=last_submodule_search_locations
            )
        except AttributeError:
            return False
        except ValueError:
            if modname == "__main__":
                return False
            try:
                # .pth files will be on sys.modules
                # __spec__ is set inconsistently on PyPy so we can't really on the heuristic here
                # See: https://foss.heptapod.net/pypy/pypy/-/issues/3736
                # Check first fragment of modname, e.g. "astroid", not "astroid.interpreter"
                # because of cffi's behavior
                # See: https://github.com/PyCQA/astroid/issues/1776
                mod = sys.modules[processed_components[0]]
                return (
                    mod.__spec__ is None
                    and getattr(mod, "__file__", None) is None
                    and hasattr(mod, "__path__")
                    and not IS_PYPY
                )
            except KeyError:
                return False
            except AttributeError:
                # Workaround for "py" module
                # https://github.com/pytest-dev/apipkg/issues/13
                return False
        except KeyError:
            # Intermediate steps might raise KeyErrors
            # https://github.com/python/cpython/issues/93334
            # TODO: update if fixed in importlib
            # For tree a > b > c.py
            # >>> from importlib.machinery import PathFinder
            # >>> PathFinder.find_spec('a.b', ['a'])
            # KeyError: 'a'

            # Repair last_submodule_search_locations
            if last_submodule_search_locations:
                # TODO: py38: remove except
                try:
                    # pylint: disable=unsubscriptable-object
                    last_item = last_submodule_search_locations[-1]
                except TypeError:
                    last_item = last_submodule_search_locations._recalculate()[-1]
                # e.g. for failure example above, add 'a/b' and keep going
                # so that find_spec('a.b.c', path=['a', 'a/b']) succeeds
                assumed_location = pathlib.Path(last_item) / component
                last_submodule_search_locations.append(str(assumed_location))
            continue

        # Update last_submodule_search_locations for next iteration
        if found_spec and found_spec.submodule_search_locations:
            # But immediately return False if we can detect we are in stdlib
            # or external lib (e.g site-packages)
            if any(
                any(location.startswith(lib_dir) for lib_dir in STD_AND_EXT_LIB_DIRS)
                for location in found_spec.submodule_search_locations
            ):
                return False
            last_submodule_search_locations = found_spec.submodule_search_locations

    return (
        found_spec is not None
        and found_spec.submodule_search_locations is not None
        and found_spec.origin is None
    )
