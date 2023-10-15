import sys

from .client import Client
from .middleware import WSGIApp, Middleware
from .server import Server
if sys.version_info >= (3, 5):  # pragma: no cover
    from .asyncio_server import AsyncServer
    from .asyncio_client import AsyncClient
    from .async_drivers.asgi import ASGIApp
    try:
        from .async_drivers.tornado import get_tornado_handler
    except ImportError:
        get_tornado_handler = None
else:  # pragma: no cover
    AsyncServer = None
    AsyncClient = None
    get_tornado_handler = None
    ASGIApp = None

__all__ = ['Server', 'WSGIApp', 'Middleware', 'Client']
if AsyncServer is not None:  # pragma: no cover
    __all__ += ['AsyncServer', 'ASGIApp', 'get_tornado_handler',
                'AsyncClient']
