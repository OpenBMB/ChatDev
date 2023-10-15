import itertools
import logging
import random
import signal
import threading

import engineio

from . import exceptions
from . import namespace
from . import packet

default_logger = logging.getLogger('socketio.client')
reconnecting_clients = []


def signal_handler(sig, frame):  # pragma: no cover
    """SIGINT handler.

    Notify any clients that are in a reconnect loop to abort. Other
    disconnection tasks are handled at the engine.io level.
    """
    for client in reconnecting_clients[:]:
        client._reconnect_abort.set()
    if callable(original_signal_handler):
        return original_signal_handler(sig, frame)
    else:  # pragma: no cover
        # Handle case where no original SIGINT handler was present.
        return signal.default_int_handler(sig, frame)


original_signal_handler = None


class Client(object):
    """A Socket.IO client.

    This class implements a fully compliant Socket.IO web client with support
    for websocket and long-polling transports.

    :param reconnection: ``True`` if the client should automatically attempt to
                         reconnect to the server after an interruption, or
                         ``False`` to not reconnect. The default is ``True``.
    :param reconnection_attempts: How many reconnection attempts to issue
                                  before giving up, or 0 for infinite attempts.
                                  The default is 0.
    :param reconnection_delay: How long to wait in seconds before the first
                               reconnection attempt. Each successive attempt
                               doubles this delay.
    :param reconnection_delay_max: The maximum delay between reconnection
                                   attempts.
    :param randomization_factor: Randomization amount for each delay between
                                 reconnection attempts. The default is 0.5,
                                 which means that each delay is randomly
                                 adjusted by +/- 50%.
    :param logger: To enable logging set to ``True`` or pass a logger object to
                   use. To disable logging set to ``False``. The default is
                   ``False``. Note that fatal errors are logged even when
                   ``logger`` is ``False``.
    :param serializer: The serialization method to use when transmitting
                       packets. Valid values are ``'default'``, ``'pickle'``,
                       ``'msgpack'`` and ``'cbor'``. Alternatively, a subclass
                       of the :class:`Packet` class with custom implementations
                       of the ``encode()`` and ``decode()`` methods can be
                       provided. Client and server must use compatible
                       serializers.
    :param json: An alternative json module to use for encoding and decoding
                 packets. Custom json modules must have ``dumps`` and ``loads``
                 functions that are compatible with the standard library
                 versions.
    :param handle_sigint: Set to ``True`` to automatically handle disconnection
                          when the process is interrupted, or to ``False`` to
                          leave interrupt handling to the calling application.
                          Interrupt handling can only be enabled when the
                          client instance is created in the main thread.

    The Engine.IO configuration supports the following settings:

    :param request_timeout: A timeout in seconds for requests. The default is
                            5 seconds.
    :param http_session: an initialized ``requests.Session`` object to be used
                         when sending requests to the server. Use it if you
                         need to add special client options such as proxy
                         servers, SSL certificates, etc.
    :param ssl_verify: ``True`` to verify SSL certificates, or ``False`` to
                       skip SSL certificate verification, allowing
                       connections to servers with self signed certificates.
                       The default is ``True``.
    :param engineio_logger: To enable Engine.IO logging set to ``True`` or pass
                            a logger object to use. To disable logging set to
                            ``False``. The default is ``False``. Note that
                            fatal errors are logged even when
                            ``engineio_logger`` is ``False``.
    """
    reserved_events = ['connect', 'connect_error', 'disconnect']

    def __init__(self, reconnection=True, reconnection_attempts=0,
                 reconnection_delay=1, reconnection_delay_max=5,
                 randomization_factor=0.5, logger=False, serializer='default',
                 json=None, handle_sigint=True, **kwargs):
        global original_signal_handler
        if handle_sigint and original_signal_handler is None and \
                threading.current_thread() == threading.main_thread():
            original_signal_handler = signal.signal(signal.SIGINT,
                                                    signal_handler)
        self.reconnection = reconnection
        self.reconnection_attempts = reconnection_attempts
        self.reconnection_delay = reconnection_delay
        self.reconnection_delay_max = reconnection_delay_max
        self.randomization_factor = randomization_factor
        self.handle_sigint = handle_sigint

        engineio_options = kwargs
        engineio_options['handle_sigint'] = handle_sigint
        engineio_logger = engineio_options.pop('engineio_logger', None)
        if engineio_logger is not None:
            engineio_options['logger'] = engineio_logger
        if serializer == 'default':
            self.packet_class = packet.Packet
        elif serializer == 'msgpack':
            from . import msgpack_packet
            self.packet_class = msgpack_packet.MsgPackPacket
        else:
            self.packet_class = serializer
        if json is not None:
            self.packet_class.json = json
            engineio_options['json'] = json

        self.eio = self._engineio_client_class()(**engineio_options)
        self.eio.on('connect', self._handle_eio_connect)
        self.eio.on('message', self._handle_eio_message)
        self.eio.on('disconnect', self._handle_eio_disconnect)

        if not isinstance(logger, bool):
            self.logger = logger
        else:
            self.logger = default_logger
            if self.logger.level == logging.NOTSET:
                if logger:
                    self.logger.setLevel(logging.INFO)
                else:
                    self.logger.setLevel(logging.ERROR)
                self.logger.addHandler(logging.StreamHandler())

        self.connection_url = None
        self.connection_headers = None
        self.connection_auth = None
        self.connection_transports = None
        self.connection_namespaces = []
        self.socketio_path = None
        self.sid = None

        self.connected = False  #: Indicates if the client is connected or not.
        self.namespaces = {}  #: set of connected namespaces.
        self.handlers = {}
        self.namespace_handlers = {}
        self.callbacks = {}
        self._binary_packet = None
        self._connect_event = None
        self._reconnect_task = None
        self._reconnect_abort = None

    def is_asyncio_based(self):
        return False

    def on(self, event, handler=None, namespace=None):
        """Register an event handler.

        :param event: The event name. It can be any string. The event names
                      ``'connect'``, ``'message'`` and ``'disconnect'`` are
                      reserved and should not be used.
        :param handler: The function that should be invoked to handle the
                        event. When this parameter is not given, the method
                        acts as a decorator for the handler function.
        :param namespace: The Socket.IO namespace for the event. If this
                          argument is omitted the handler is associated with
                          the default namespace.

        Example usage::

            # as a decorator:
            @sio.on('connect')
            def connect_handler():
                print('Connected!')

            # as a method:
            def message_handler(msg):
                print('Received message: ', msg)
                sio.send( 'response')
            sio.on('message', message_handler)

        The ``'connect'`` event handler receives no arguments. The
        ``'message'`` handler and handlers for custom event names receive the
        message payload as only argument. Any values returned from a message
        handler will be passed to the client's acknowledgement callback
        function if it exists. The ``'disconnect'`` handler does not take
        arguments.
        """
        namespace = namespace or '/'

        def set_handler(handler):
            if namespace not in self.handlers:
                self.handlers[namespace] = {}
            self.handlers[namespace][event] = handler
            return handler

        if handler is None:
            return set_handler
        set_handler(handler)

    def event(self, *args, **kwargs):
        """Decorator to register an event handler.

        This is a simplified version of the ``on()`` method that takes the
        event name from the decorated function.

        Example usage::

            @sio.event
            def my_event(data):
                print('Received data: ', data)

        The above example is equivalent to::

            @sio.on('my_event')
            def my_event(data):
                print('Received data: ', data)

        A custom namespace can be given as an argument to the decorator::

            @sio.event(namespace='/test')
            def my_event(data):
                print('Received data: ', data)
        """
        if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
            # the decorator was invoked without arguments
            # args[0] is the decorated function
            return self.on(args[0].__name__)(args[0])
        else:
            # the decorator was invoked with arguments
            def set_handler(handler):
                return self.on(handler.__name__, *args, **kwargs)(handler)

            return set_handler

    def register_namespace(self, namespace_handler):
        """Register a namespace handler object.

        :param namespace_handler: An instance of a :class:`Namespace`
                                  subclass that handles all the event traffic
                                  for a namespace.
        """
        if not isinstance(namespace_handler, namespace.ClientNamespace):
            raise ValueError('Not a namespace instance')
        if self.is_asyncio_based() != namespace_handler.is_asyncio_based():
            raise ValueError('Not a valid namespace class for this client')
        namespace_handler._set_client(self)
        self.namespace_handlers[namespace_handler.namespace] = \
            namespace_handler

    def connect(self, url, headers={}, auth=None, transports=None,
                namespaces=None, socketio_path='socket.io', wait=True,
                wait_timeout=1):
        """Connect to a Socket.IO server.

        :param url: The URL of the Socket.IO server. It can include custom
                    query string parameters if required by the server. If a
                    function is provided, the client will invoke it to obtain
                    the URL each time a connection or reconnection is
                    attempted.
        :param headers: A dictionary with custom headers to send with the
                        connection request. If a function is provided, the
                        client will invoke it to obtain the headers dictionary
                        each time a connection or reconnection is attempted.
        :param auth: Authentication data passed to the server with the
                     connection request, normally a dictionary with one or
                     more string key/value pairs. If a function is provided,
                     the client will invoke it to obtain the authentication
                     data each time a connection or reconnection is attempted.
        :param transports: The list of allowed transports. Valid transports
                           are ``'polling'`` and ``'websocket'``. If not
                           given, the polling transport is connected first,
                           then an upgrade to websocket is attempted.
        :param namespaces: The namespaces to connect as a string or list of
                           strings. If not given, the namespaces that have
                           registered event handlers are connected.
        :param socketio_path: The endpoint where the Socket.IO server is
                              installed. The default value is appropriate for
                              most cases.
        :param wait: if set to ``True`` (the default) the call only returns
                     when all the namespaces are connected. If set to
                     ``False``, the call returns as soon as the Engine.IO
                     transport is connected, and the namespaces will connect
                     in the background.
        :param wait_timeout: How long the client should wait for the
                             connection. The default is 1 second. This
                             argument is only considered when ``wait`` is set
                             to ``True``.

        Example usage::

            sio = socketio.Client()
            sio.connect('http://localhost:5000')
        """
        if self.connected:
            raise exceptions.ConnectionError('Already connected')

        self.connection_url = url
        self.connection_headers = headers
        self.connection_auth = auth
        self.connection_transports = transports
        self.connection_namespaces = namespaces
        self.socketio_path = socketio_path

        if namespaces is None:
            namespaces = list(set(self.handlers.keys()).union(
                set(self.namespace_handlers.keys())))
            if len(namespaces) == 0:
                namespaces = ['/']
        elif isinstance(namespaces, str):
            namespaces = [namespaces]
        self.connection_namespaces = namespaces
        self.namespaces = {}
        if self._connect_event is None:
            self._connect_event = self.eio.create_event()
        else:
            self._connect_event.clear()
        real_url = self._get_real_value(self.connection_url)
        real_headers = self._get_real_value(self.connection_headers)
        try:
            self.eio.connect(real_url, headers=real_headers,
                             transports=transports,
                             engineio_path=socketio_path)
        except engineio.exceptions.ConnectionError as exc:
            self._trigger_event(
                'connect_error', '/',
                exc.args[1] if len(exc.args) > 1 else exc.args[0])
            raise exceptions.ConnectionError(exc.args[0]) from None

        if wait:
            while self._connect_event.wait(timeout=wait_timeout):
                self._connect_event.clear()
                if set(self.namespaces) == set(self.connection_namespaces):
                    break
            if set(self.namespaces) != set(self.connection_namespaces):
                self.disconnect()
                raise exceptions.ConnectionError(
                    'One or more namespaces failed to connect')

        self.connected = True

    def wait(self):
        """Wait until the connection with the server ends.

        Client applications can use this function to block the main thread
        during the life of the connection.
        """
        while True:
            self.eio.wait()
            self.sleep(1)  # give the reconnect task time to start up
            if not self._reconnect_task:
                break
            self._reconnect_task.join()
            if self.eio.state != 'connected':
                break

    def emit(self, event, data=None, namespace=None, callback=None):
        """Emit a custom event to one or more connected clients.

        :param event: The event name. It can be any string. The event names
                      ``'connect'``, ``'message'`` and ``'disconnect'`` are
                      reserved and should not be used.
        :param data: The data to send to the server. Data can be of
                     type ``str``, ``bytes``, ``list`` or ``dict``. To send
                     multiple arguments, use a tuple where each element is of
                     one of the types indicated above.
        :param namespace: The Socket.IO namespace for the event. If this
                          argument is omitted the event is emitted to the
                          default namespace.
        :param callback: If given, this function will be called to acknowledge
                         the server has received the message. The arguments
                         that will be passed to the function are those provided
                         by the server.

        Note: this method is not thread safe. If multiple threads are emitting
        at the same time on the same client connection, messages composed of
        multiple packets may end up being sent in an incorrect sequence. Use
        standard concurrency solutions (such as a Lock object) to prevent this
        situation.
        """
        namespace = namespace or '/'
        if namespace not in self.namespaces:
            raise exceptions.BadNamespaceError(
                namespace + ' is not a connected namespace.')
        self.logger.info('Emitting event "%s" [%s]', event, namespace)
        if callback is not None:
            id = self._generate_ack_id(namespace, callback)
        else:
            id = None
        # tuples are expanded to multiple arguments, everything else is sent
        # as a single argument
        if isinstance(data, tuple):
            data = list(data)
        elif data is not None:
            data = [data]
        else:
            data = []
        self._send_packet(self.packet_class(packet.EVENT, namespace=namespace,
                                            data=[event] + data, id=id))

    def send(self, data, namespace=None, callback=None):
        """Send a message to one or more connected clients.

        This function emits an event with the name ``'message'``. Use
        :func:`emit` to issue custom event names.

        :param data: The data to send to the server. Data can be of
                     type ``str``, ``bytes``, ``list`` or ``dict``. To send
                     multiple arguments, use a tuple where each element is of
                     one of the types indicated above.
        :param namespace: The Socket.IO namespace for the event. If this
                          argument is omitted the event is emitted to the
                          default namespace.
        :param callback: If given, this function will be called to acknowledge
                         the server has received the message. The arguments
                         that will be passed to the function are those provided
                         by the server.
        """
        self.emit('message', data=data, namespace=namespace,
                  callback=callback)

    def call(self, event, data=None, namespace=None, timeout=60):
        """Emit a custom event to a client and wait for the response.

        This method issues an emit with a callback and waits for the callback
        to be invoked before returning. If the callback isn't invoked before
        the timeout, then a ``TimeoutError`` exception is raised. If the
        Socket.IO connection drops during the wait, this method still waits
        until the specified timeout.

        :param event: The event name. It can be any string. The event names
                      ``'connect'``, ``'message'`` and ``'disconnect'`` are
                      reserved and should not be used.
        :param data: The data to send to the server. Data can be of
                     type ``str``, ``bytes``, ``list`` or ``dict``. To send
                     multiple arguments, use a tuple where each element is of
                     one of the types indicated above.
        :param namespace: The Socket.IO namespace for the event. If this
                          argument is omitted the event is emitted to the
                          default namespace.
        :param timeout: The waiting timeout. If the timeout is reached before
                        the client acknowledges the event, then a
                        ``TimeoutError`` exception is raised.

        Note: this method is not thread safe. If multiple threads are emitting
        at the same time on the same client connection, messages composed of
        multiple packets may end up being sent in an incorrect sequence. Use
        standard concurrency solutions (such as a Lock object) to prevent this
        situation.
        """
        callback_event = self.eio.create_event()
        callback_args = []

        def event_callback(*args):
            callback_args.append(args)
            callback_event.set()

        self.emit(event, data=data, namespace=namespace,
                  callback=event_callback)
        if not callback_event.wait(timeout=timeout):
            raise exceptions.TimeoutError()
        return callback_args[0] if len(callback_args[0]) > 1 \
            else callback_args[0][0] if len(callback_args[0]) == 1 \
            else None

    def disconnect(self):
        """Disconnect from the server."""
        # here we just request the disconnection
        # later in _handle_eio_disconnect we invoke the disconnect handler
        for n in self.namespaces:
            self._send_packet(self.packet_class(
                packet.DISCONNECT, namespace=n))
        self.eio.disconnect(abort=True)

    def get_sid(self, namespace=None):
        """Return the ``sid`` associated with a connection.

        :param namespace: The Socket.IO namespace. If this argument is omitted
                          the handler is associated with the default
                          namespace. Note that unlike previous versions, the
                          current version of the Socket.IO protocol uses
                          different ``sid`` values per namespace.

        This method returns the ``sid`` for the requested namespace as a
        string.
        """
        return self.namespaces.get(namespace or '/')

    def transport(self):
        """Return the name of the transport used by the client.

        The two possible values returned by this function are ``'polling'``
        and ``'websocket'``.
        """
        return self.eio.transport()

    def start_background_task(self, target, *args, **kwargs):
        """Start a background task using the appropriate async model.

        This is a utility function that applications can use to start a
        background task using the method that is compatible with the
        selected async mode.

        :param target: the target function to execute.
        :param args: arguments to pass to the function.
        :param kwargs: keyword arguments to pass to the function.

        This function returns an object that represents the background task,
        on which the ``join()`` methond can be invoked to wait for the task to
        complete.
        """
        return self.eio.start_background_task(target, *args, **kwargs)

    def sleep(self, seconds=0):
        """Sleep for the requested amount of time using the appropriate async
        model.

        This is a utility function that applications can use to put a task to
        sleep without having to worry about using the correct call for the
        selected async mode.
        """
        return self.eio.sleep(seconds)

    def _get_real_value(self, value):
        """Return the actual value, for parameters that can also be given as
        callables."""
        if not callable(value):
            return value
        return value()

    def _send_packet(self, pkt):
        """Send a Socket.IO packet to the server."""
        encoded_packet = pkt.encode()
        if isinstance(encoded_packet, list):
            for ep in encoded_packet:
                self.eio.send(ep)
        else:
            self.eio.send(encoded_packet)

    def _generate_ack_id(self, namespace, callback):
        """Generate a unique identifier for an ACK packet."""
        namespace = namespace or '/'
        if namespace not in self.callbacks:
            self.callbacks[namespace] = {0: itertools.count(1)}
        id = next(self.callbacks[namespace][0])
        self.callbacks[namespace][id] = callback
        return id

    def _handle_connect(self, namespace, data):
        namespace = namespace or '/'
        if namespace not in self.namespaces:
            self.logger.info('Namespace {} is connected'.format(namespace))
            self.namespaces[namespace] = (data or {}).get('sid', self.sid)
            self._trigger_event('connect', namespace=namespace)
            self._connect_event.set()

    def _handle_disconnect(self, namespace):
        if not self.connected:
            return
        namespace = namespace or '/'
        self._trigger_event('disconnect', namespace=namespace)
        if namespace in self.namespaces:
            del self.namespaces[namespace]
        if not self.namespaces:
            self.connected = False
            self.eio.disconnect(abort=True)

    def _handle_event(self, namespace, id, data):
        namespace = namespace or '/'
        self.logger.info('Received event "%s" [%s]', data[0], namespace)
        r = self._trigger_event(data[0], namespace, *data[1:])
        if id is not None:
            # send ACK packet with the response returned by the handler
            # tuples are expanded as multiple arguments
            if r is None:
                data = []
            elif isinstance(r, tuple):
                data = list(r)
            else:
                data = [r]
            self._send_packet(self.packet_class(
                packet.ACK, namespace=namespace, id=id, data=data))

    def _handle_ack(self, namespace, id, data):
        namespace = namespace or '/'
        self.logger.info('Received ack [%s]', namespace)
        callback = None
        try:
            callback = self.callbacks[namespace][id]
        except KeyError:
            # if we get an unknown callback we just ignore it
            self.logger.warning('Unknown callback received, ignoring.')
        else:
            del self.callbacks[namespace][id]
        if callback is not None:
            callback(*data)

    def _handle_error(self, namespace, data):
        namespace = namespace or '/'
        self.logger.info('Connection to namespace {} was rejected'.format(
            namespace))
        if data is None:
            data = tuple()
        elif not isinstance(data, (tuple, list)):
            data = (data,)
        self._trigger_event('connect_error', namespace, *data)
        self._connect_event.set()
        if namespace in self.namespaces:
            del self.namespaces[namespace]
        if namespace == '/':
            self.namespaces = {}
            self.connected = False

    def _trigger_event(self, event, namespace, *args):
        """Invoke an application event handler."""
        # first see if we have an explicit handler for the event
        if namespace in self.handlers:
            if event in self.handlers[namespace]:
                return self.handlers[namespace][event](*args)
            elif event not in self.reserved_events and \
                    '*' in self.handlers[namespace]:
                return self.handlers[namespace]['*'](event, *args)

        # or else, forward the event to a namespace handler if one exists
        elif namespace in self.namespace_handlers:
            return self.namespace_handlers[namespace].trigger_event(
                event, *args)

    def _handle_reconnect(self):
        if self._reconnect_abort is None:  # pragma: no cover
            self._reconnect_abort = self.eio.create_event()
        self._reconnect_abort.clear()
        reconnecting_clients.append(self)
        attempt_count = 0
        current_delay = self.reconnection_delay
        while True:
            delay = current_delay
            current_delay *= 2
            if delay > self.reconnection_delay_max:
                delay = self.reconnection_delay_max
            delay += self.randomization_factor * (2 * random.random() - 1)
            self.logger.info(
                'Connection failed, new attempt in {:.02f} seconds'.format(
                    delay))
            if self._reconnect_abort.wait(delay):
                self.logger.info('Reconnect task aborted')
                break
            attempt_count += 1
            try:
                self.connect(self.connection_url,
                             headers=self.connection_headers,
                             auth=self.connection_auth,
                             transports=self.connection_transports,
                             namespaces=self.connection_namespaces,
                             socketio_path=self.socketio_path)
            except (exceptions.ConnectionError, ValueError):
                pass
            else:
                self.logger.info('Reconnection successful')
                self._reconnect_task = None
                break
            if self.reconnection_attempts and \
                    attempt_count >= self.reconnection_attempts:
                self.logger.info(
                    'Maximum reconnection attempts reached, giving up')
                break
        reconnecting_clients.remove(self)

    def _handle_eio_connect(self):
        """Handle the Engine.IO connection event."""
        self.logger.info('Engine.IO connection established')
        self.sid = self.eio.sid
        real_auth = self._get_real_value(self.connection_auth) or {}
        for n in self.connection_namespaces:
            self._send_packet(self.packet_class(
                packet.CONNECT, data=real_auth, namespace=n))

    def _handle_eio_message(self, data):
        """Dispatch Engine.IO messages."""
        if self._binary_packet:
            pkt = self._binary_packet
            if pkt.add_attachment(data):
                self._binary_packet = None
                if pkt.packet_type == packet.BINARY_EVENT:
                    self._handle_event(pkt.namespace, pkt.id, pkt.data)
                else:
                    self._handle_ack(pkt.namespace, pkt.id, pkt.data)
        else:
            pkt = self.packet_class(encoded_packet=data)
            if pkt.packet_type == packet.CONNECT:
                self._handle_connect(pkt.namespace, pkt.data)
            elif pkt.packet_type == packet.DISCONNECT:
                self._handle_disconnect(pkt.namespace)
            elif pkt.packet_type == packet.EVENT:
                self._handle_event(pkt.namespace, pkt.id, pkt.data)
            elif pkt.packet_type == packet.ACK:
                self._handle_ack(pkt.namespace, pkt.id, pkt.data)
            elif pkt.packet_type == packet.BINARY_EVENT or \
                    pkt.packet_type == packet.BINARY_ACK:
                self._binary_packet = pkt
            elif pkt.packet_type == packet.CONNECT_ERROR:
                self._handle_error(pkt.namespace, pkt.data)
            else:
                raise ValueError('Unknown packet type.')

    def _handle_eio_disconnect(self):
        """Handle the Engine.IO disconnection event."""
        self.logger.info('Engine.IO connection dropped')
        if self.connected:
            for n in self.namespaces:
                self._trigger_event('disconnect', namespace=n)
            self.namespaces = {}
            self.connected = False
        self.callbacks = {}
        self._binary_packet = None
        self.sid = None
        if self.eio.state == 'connected' and self.reconnection:
            self._reconnect_task = self.start_background_task(
                self._handle_reconnect)

    def _engineio_client_class(self):
        return engineio.Client
