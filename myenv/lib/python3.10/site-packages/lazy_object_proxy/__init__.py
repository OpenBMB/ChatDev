try:
    import copy_reg as copyreg
except ImportError:
    import copyreg

from .utils import identity

copyreg.constructor(identity)

try:
    from .cext import Proxy
    from .cext import identity
except ImportError:
    from .simple import Proxy
else:
    copyreg.constructor(identity)

try:
    from ._version import version as __version__
except ImportError:
    __version__ = '1.9.0'

__all__ = ("Proxy",)
