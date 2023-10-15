import sys

from .client import Client
from .base_manager import BaseManager
from .pubsub_manager import PubSubManager
from .kombu_manager import KombuManager
from .redis_manager import RedisManager
from .kafka_manager import KafkaManager
from .zmq_manager import ZmqManager
from .server import Server
from .namespace import Namespace, ClientNamespace
from .middleware import WSGIApp, Middleware
from .tornado import get_tornado_handler
if sys.version_info >= (3, 5):  # pragma: no cover
    from .asyncio_client import AsyncClient
    from .asyncio_server import AsyncServer
    from .asyncio_manager import AsyncManager
    from .asyncio_namespace import AsyncNamespace, AsyncClientNamespace
    from .asyncio_redis_manager import AsyncRedisManager
    from .asyncio_aiopika_manager import AsyncAioPikaManager
    from .asgi import ASGIApp
else:  # pragma: no cover
    AsyncClient = None
    AsyncServer = None
    AsyncManager = None
    AsyncNamespace = None
    AsyncRedisManager = None
    AsyncAioPikaManager = None

__all__ = ['Client', 'Server', 'BaseManager', 'PubSubManager',
           'KombuManager', 'RedisManager', 'ZmqManager', 'KafkaManager',
           'Namespace', 'ClientNamespace', 'WSGIApp', 'Middleware']
if AsyncServer is not None:  # pragma: no cover
    __all__ += ['AsyncClient', 'AsyncServer', 'AsyncNamespace',
                'AsyncClientNamespace', 'AsyncManager', 'AsyncRedisManager',
                'ASGIApp', 'get_tornado_handler', 'AsyncAioPikaManager']
