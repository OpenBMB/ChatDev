import asyncio
import pickle

from socketio.asyncio_pubsub_manager import AsyncPubSubManager

try:
    import aio_pika
except ImportError:
    aio_pika = None


class AsyncAioPikaManager(AsyncPubSubManager):  # pragma: no cover
    """Client manager that uses aio_pika for inter-process messaging under
    asyncio.

    This class implements a client manager backend for event sharing across
    multiple processes, using RabbitMQ

    To use a aio_pika backend, initialize the :class:`Server` instance as
    follows::

        url = 'amqp://user:password@hostname:port//'
        server = socketio.Server(client_manager=socketio.AsyncAioPikaManager(
            url))

    :param url: The connection URL for the backend messaging queue. Example
                connection URLs are ``'amqp://guest:guest@localhost:5672//'``
                for RabbitMQ.
    :param channel: The channel name on which the server sends and receives
                    notifications. Must be the same in all the servers.
                    With this manager, the channel name is the exchange name
                    in rabbitmq
    :param write_only: If set to ``True``, only initialize to emit events. The
                       default of ``False`` initializes the class for emitting
                       and receiving.
    """

    name = 'asyncaiopika'

    def __init__(self, url='amqp://guest:guest@localhost:5672//',
                 channel='socketio', write_only=False, logger=None):
        if aio_pika is None:
            raise RuntimeError('aio_pika package is not installed '
                               '(Run "pip install aio_pika" in your '
                               'virtualenv).')
        self.url = url
        self._lock = asyncio.Lock()
        self.publisher_connection = None
        self.publisher_channel = None
        self.publisher_exchange = None
        super().__init__(channel=channel, write_only=write_only, logger=logger)

    async def _connection(self):
        return await aio_pika.connect_robust(self.url)

    async def _channel(self, connection):
        return await connection.channel()

    async def _exchange(self, channel):
        return await channel.declare_exchange(self.channel,
                                              aio_pika.ExchangeType.FANOUT)

    async def _queue(self, channel, exchange):
        queue = await channel.declare_queue(durable=False,
                                            arguments={'x-expires': 300000})
        await queue.bind(exchange)
        return queue

    async def _publish(self, data):
        if self.publisher_connection is None:
            async with self._lock:
                if self.publisher_connection is None:
                    self.publisher_connection = await self._connection()
                    self.publisher_channel = await self._channel(
                        self.publisher_connection
                    )
                    self.publisher_exchange = await self._exchange(
                        self.publisher_channel
                    )
        retry = True
        while True:
            try:
                await self.publisher_exchange.publish(
                    aio_pika.Message(
                        body=pickle.dumps(data),
                        delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                    ), routing_key='*',
                )
                break
            except aio_pika.AMQPException:
                if retry:
                    self._get_logger().error('Cannot publish to rabbitmq... '
                                             'retrying')
                    retry = False
                else:
                    self._get_logger().error(
                        'Cannot publish to rabbitmq... giving up')
                    break
            except aio_pika.exceptions.ChannelInvalidStateError:
                # aio_pika raises this exception when the task is cancelled
                raise asyncio.CancelledError()

    async def _listen(self):
        async with (await self._connection()) as connection:
            channel = await self._channel(connection)
            await channel.set_qos(prefetch_count=1)
            exchange = await self._exchange(channel)
            queue = await self._queue(channel, exchange)

            retry_sleep = 1
            while True:
                try:
                    async with queue.iterator() as queue_iter:
                        async for message in queue_iter:
                            async with message.process():
                                yield pickle.loads(message.body)
                                retry_sleep = 1
                except aio_pika.AMQPException:
                    self._get_logger().error(
                        'Cannot receive from rabbitmq... '
                        'retrying in {} secs'.format(retry_sleep))
                    await asyncio.sleep(retry_sleep)
                    retry_sleep = min(retry_sleep * 2, 60)
                except aio_pika.exceptions.ChannelInvalidStateError:
                    # aio_pika raises this exception when the task is cancelled
                    raise asyncio.CancelledError()
