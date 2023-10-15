# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""Utility functions for test code that uses astroid ASTs as input."""

from __future__ import annotations

import contextlib
import functools
import sys
import warnings
from collections.abc import Callable

import pytest

from astroid import manager, nodes, transforms


def require_version(minver: str = "0.0.0", maxver: str = "4.0.0") -> Callable:
    """Compare version of python interpreter to the given one and skips the test if older."""

    def parse(python_version: str) -> tuple[int, ...]:
        try:
            return tuple(int(v) for v in python_version.split("."))
        except ValueError as e:
            msg = f"{python_version} is not a correct version : should be X.Y[.Z]."
            raise ValueError(msg) from e

    min_version = parse(minver)
    max_version = parse(maxver)

    def check_require_version(f):
        current: tuple[int, int, int] = sys.version_info[:3]
        if min_version < current <= max_version:
            return f

        version: str = ".".join(str(v) for v in sys.version_info)

        @functools.wraps(f)
        def new_f(*args, **kwargs):
            if current <= min_version:
                pytest.skip(f"Needs Python > {minver}. Current version is {version}.")
            elif current > max_version:
                pytest.skip(f"Needs Python <= {maxver}. Current version is {version}.")

        return new_f

    return check_require_version


def get_name_node(start_from, name, index=0):
    return [n for n in start_from.nodes_of_class(nodes.Name) if n.name == name][index]


@contextlib.contextmanager
def enable_warning(warning):
    warnings.simplefilter("always", warning)
    try:
        yield
    finally:
        # Reset it to default value, so it will take
        # into account the values from the -W flag.
        warnings.simplefilter("default", warning)


def brainless_manager():
    m = manager.AstroidManager()
    # avoid caching into the AstroidManager borg since we get problems
    # with other tests :
    m.__dict__ = {}
    m._failed_import_hooks = []
    m.astroid_cache = {}
    m._mod_file_cache = {}
    m._transform = transforms.TransformVisitor()
    m.extension_package_whitelist = set()
    return m
