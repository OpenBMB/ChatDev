# Copyright 2017-2020 Palantir Technologies, Inc.
# Copyright 2021- Python Language Server Contributors.

import os
import pluggy
from . import _version
from ._version import __version__


def convert_version_info(version: str) -> (int, ..., str):
    version_info = version.split(".")
    for i, v in enumerate(version_info):
        try:
            version_info[i] = int(v)
        except ValueError:
            version_info[i] = v.split("+")[0]
            version_info = version_info[: i + 1]
            break

    return tuple(version_info)


_version.VERSION_INFO = convert_version_info(__version__)

PYLSP = 'pylsp'
IS_WIN = os.name == 'nt'

hookspec = pluggy.HookspecMarker(PYLSP)
hookimpl = pluggy.HookimplMarker(PYLSP)

__all__ = ("__version__",)
