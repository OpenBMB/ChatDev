import asyncio
from functools import partial
import uuid

from engineio import json
import pickle

from .asyncio_manager import AsyncManager


class AsyncPubSubManager(AsyncManager):
    """Manage a client list attached to a pub/sub backend under asyncio.

    This is a base class that enables multiple servers to share the list of
    clients, with the servers communicating events through a pub/sub backend.
    The use of a pub/sub backend also allows any client connected to the
    backend to emit events addressed to Socket.IO clients.

    The actual backends must be implemented by subclasses, this class only
    provides a pub/sub generic framework for asyncio applications.

    :param channel: The channel name on which the server sends and receives
                    notifications.
    """
    name = 'asyncpubsub'

    def __init__(self, channel='socketio', write_only=False, logger=None):
        super().__init__()
        self.channel = channel
        self.write_only = write_only
        self.host_id = uuid.uuid4().hex
        self.logger = logger

    def initialize(self):
        super().initialize()
        if not self.write_only:
            self.thread = self.server.start_background_task(self._thread)
        self._get_logger().info(self.name + ' backend initialized.')

    async def emit(self, event, data, namespace=None, room=None, skip_sid=None,
                   callback=None, **kwargs):
        """Emit a message to a single client, a room, or all the clients
        connected to the namespace.

        This method takes care or propagating the message to all the servers
        that are connected through the message queue.

        The parameters are the same as in :meth:`.Server.emit`.

        Note: this method is a coroutine.
        """
        if kwargs.get('ignore_queue'):
            return await super().emit(
                event, data, namespace=namespace, room=room, skip_sid=skip_sid,
                callback=callback)
        namespace = namespace or '/'
        if callback is not None:
            if self.server is None:
                raise RuntimeError('Callbacks can only be issued from the '
                                   'context of a server.')
            if room is None:
                raise ValueError('Cannot use callback without a room set.')
            id = self._generate_ack_id(room, callback)
            callback = (room, namespace, id)
        else:
            callback = None
        await self._publish({'method': 'emit', 'event': event, 'data': data,
                             'namespace': namespace, 'room': room,
                             'skip_sid': skip_sid, 'callback': callback,
                             'host_id': self.host_id})

    async def can_disconnect(self, sid, namespace):
        if self.is_connected(sid, namespace):
            # client is in this server, so we can disconnect directly
            return await super().can_disconnect(sid, namespace)
        else:
            # client is in another server, so we post request to the queue
            await self._publish({'method': 'disconnect', 'sid': sid,
                                 'namespace': namespace or '/'})

    async def disconnect(self, sid, namespace, **kwargs):
        if kwargs.get('ignore_queue'):
            return await super(AsyncPubSubManager, self).disconnect(
                sid, namespace=namespace)
        await self._publish({'method': 'disconnect', 'sid': sid,
                             'namespace': namespace or '/'})

    async def close_room(self, room, namespace=None):
        await self._publish({'method': 'close_room', 'room': room,
                             'namespace': namespace or '/'})

    async def _publish(self, data):
        """Publish a message on the Socket.IO channel.

        This method needs to be implemented by the different subclasses that
        support pub/sub backends.
        """
        raise NotImplementedError('This method must be implemented in a '
                                  'subclass.')  # pragma: no cover

    async def _listen(self):
        """Return the next message published on the Socket.IO channel,
        blocking until a message is available.

        This method needs to be implemented by the different subclasses that
        support pub/sub backends.
        """
        raise NotImplementedError('This method must be implemented in a '
                                  'subclass.')  # pragma: no cover

    async def _handle_emit(self, message):
        # Events with callbacks are very tricky to handle across hosts
        # Here in the receiving end we set up a local callback that preserves
        # the callback host and id from the sender
        remote_callback = message.get('callback')
        remote_host_id = message.get('host_id')
        if remote_callback is not None and len(remote_callback) == 3:
            callback = partial(self._return_callback, remote_host_id,
                               *remote_callback)
        else:
            callback = None
        await super().emit(message['event'], message['data'],
                           namespace=message.get('namespace'),
                           room=message.get('room'),
                           skip_sid=message.get('skip_sid'),
                           callback=callback)

    async def _handle_callback(self, message):
        if self.host_id == message.get('host_id'):
            try:
                sid = message['sid']
                id = message['id']
                args = message['args']
            except KeyError:
                return
            await self.trigger_callback(sid, id, args)

    async def _return_callback(self, host_id, sid, namespace, callback_id,
                               *args):
        # When an event callback is received, the callback is returned back
        # the sender, which is identified by the host_id
        await self._publish({'method': 'callback', 'host_id': host_id,
                             'sid': sid, 'namespace': namespace,
                             'id': callback_id, 'args': args})

    async def _handle_disconnect(self, message):
        await self.server.disconnect(sid=message.get('sid'),
                                     namespace=message.get('namespace'),
                                     ignore_queue=True)

    async def _handle_close_room(self, message):
        await super().close_room(
            room=message.get('room'), namespace=message.get('namespace'))

    async def _thread(self):
        while True:
            try:
                async for message in self._listen():  # pragma: no branch
                    data = None
                    if isinstance(message, dict):
                        data = message
                    else:
                        if isinstance(message, bytes):  # pragma: no cover
                            try:
                                data = pickle.loads(message)
                            except:
                                pass
                        if data is None:
                            try:
                                data = json.loads(message)
                            except:
                                pass
                    if data and 'method' in data:
                        self._get_logger().info('pubsub message: {}'.format(
                            data['method']))
                        try:
                            if data['method'] == 'emit':
                                await self._handle_emit(data)
                            elif data['method'] == 'callback':
                                await self._handle_callback(data)
                            elif data['method'] == 'disconnect':
                                await self._handle_disconnect(data)
                            elif data['method'] == 'close_room':
                                await self._handle_close_room(data)
                        except asyncio.CancelledError:
                            raise  # let the outer try/except handle it
                        except:
                            self.server.logger.exception(
                                'Unknown error in pubsub listening task')
            except asyncio.CancelledError:  # pragma: no cover
                break
            except:  # pragma: no cover
                import traceback
                traceback.print_exc()
