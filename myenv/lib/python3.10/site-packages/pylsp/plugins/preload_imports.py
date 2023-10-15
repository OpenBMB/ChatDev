# Copyright 2017-2020 Palantir Technologies, Inc.
# Copyright 2021- Python Language Server Contributors.

import logging
from pylsp import hookimpl

log = logging.getLogger(__name__)

MODULES = [
    "OpenGL", "PIL",
    "array", "audioop", "binascii", "cPickle", "cStringIO", "cmath", "collections",
    "datetime", "errno", "exceptions", "gc", "imageop", "imp", "itertools",
    "marshal", "math", "matplotlib", "mmap", "mpmath", "msvcrt", "networkx", "nose", "nt",
    "numpy", "operator", "os", "os.path", "pandas", "parser", "rgbimg", "scipy", "signal",
    "skimage", "sklearn", "statsmodels", "strop", "sympy", "sys", "thread", "time",
    "wx", "xxsubtype", "zipimport", "zlib"
]


@hookimpl
def pylsp_settings():
    # Setup default modules to preload, and rope extension modules
    return {
        'plugins': {'preload': {'modules': MODULES}},
        'rope': {'extensionModules': MODULES}
    }


@hookimpl
def pylsp_initialize(config):
    for mod_name in config.plugin_settings('preload').get('modules', []):
        try:
            __import__(mod_name)
            log.debug("Preloaded module %s", mod_name)
        except Exception:  # pylint: disable=broad-except
            # Catch any exception since not only ImportError can be raised here
            # For example, old versions of NumPy can cause a ValueError.
            # See spyder-ide/spyder#13985
            pass
