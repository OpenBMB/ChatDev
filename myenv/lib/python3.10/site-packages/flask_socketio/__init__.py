from functools import wraps
import os
import sys

# make sure gevent-socketio is not installed, as it conflicts with
# python-socketio
gevent_socketio_found = True
try:
    from socketio import socketio_manage  # noqa: F401
except ImportError:
    gevent_socketio_found = False
if gevent_socketio_found:
    print('The gevent-socketio package is incompatible with this version of '
          'the Flask-SocketIO extension. Please uninstall it, and then '
          'install the latest version of python-socketio in its place.')
    sys.exit(1)

import flask
from flask import has_request_context, json as flask_json
from flask.sessions import SessionMixin
import socketio
from socketio.exceptions import ConnectionRefusedError  # noqa: F401
from werkzeug.debug import DebuggedApplication
from werkzeug._reloader import run_with_reloader

from .namespace import Namespace
from .test_client import SocketIOTestClient


class _SocketIOMiddleware(socketio.WSGIApp):
    """This WSGI middleware simply exposes the Flask application in the WSGI
    environment before executing the request.
    """
    def __init__(self, socketio_app, flask_app, socketio_path='socket.io'):
        self.flask_app = flask_app
        super(_SocketIOMiddleware, self).__init__(socketio_app,
                                                  flask_app.wsgi_app,
                                                  socketio_path=socketio_path)

    def __call__(self, environ, start_response):
        environ = environ.copy()
        environ['flask.app'] = self.flask_app
        return super(_SocketIOMiddleware, self).__call__(environ,
                                                         start_response)


class _ManagedSession(dict, SessionMixin):
    """This class is used for user sessions that are managed by
    Flask-SocketIO. It is simple dict, expanded with the Flask session
    attributes."""
    pass


class SocketIO(object):
    """Create a Flask-SocketIO server.

    :param app: The flask application instance. If the application instance
                isn't known at the time this class is instantiated, then call
                ``socketio.init_app(app)`` once the application instance is
                available.
    :param manage_session: If set to ``True``, this extension manages the user
                           session for Socket.IO events. If set to ``False``,
                           Flask's own session management is used. When using
                           Flask's cookie based sessions it is recommended that
                           you leave this set to the default of ``True``. When
                           using server-side sessions, a ``False`` setting
                           enables sharing the user session between HTTP routes
                           and Socket.IO events.
    :param message_queue: A connection URL for a message queue service the
                          server can use for multi-process communication. A
                          message queue is not required when using a single
                          server process.
    :param channel: The channel name, when using a message queue. If a channel
                    isn't specified, a default channel will be used. If
                    multiple clusters of SocketIO processes need to use the
                    same message queue without interfering with each other,
                    then each cluster should use a different channel.
    :param path: The path where the Socket.IO server is exposed. Defaults to
                 ``'socket.io'``. Leave this as is unless you know what you are
                 doing.
    :param resource: Alias to ``path``.
    :param kwargs: Socket.IO and Engine.IO server options.

    The Socket.IO server options are detailed below:

    :param client_manager: The client manager instance that will manage the
                           client list. When this is omitted, the client list
                           is stored in an in-memory structure, so the use of
                           multiple connected servers is not possible. In most
                           cases, this argument does not need to be set
                           explicitly.
    :param logger: To enable logging set to ``True`` or pass a logger object to
                   use. To disable logging set to ``False``. The default is
                   ``False``. Note that fatal errors will be logged even when
                   ``logger`` is ``False``.
    :param json: An alternative json module to use for encoding and decoding
                 packets. Custom json modules must have ``dumps`` and ``loads``
                 functions that are compatible with the standard library
                 versions. To use the same json encoder and decoder as a Flask
                 application, use ``flask.json``.
    :param async_handlers: If set to ``True``, event handlers for a client are
                           executed in separate threads. To run handlers for a
                           client synchronously, set to ``False``. The default
                           is ``True``.
    :param always_connect: When set to ``False``, new connections are
                           provisory until the connect handler returns
                           something other than ``False``, at which point they
                           are accepted. When set to ``True``, connections are
                           immediately accepted, and then if the connect
                           handler returns ``False`` a disconnect is issued.
                           Set to ``True`` if you need to emit events from the
                           connect handler and your client is confused when it
                           receives events before the connection acceptance.
                           In any other case use the default of ``False``.

    The Engine.IO server configuration supports the following settings:

    :param async_mode: The asynchronous model to use. See the Deployment
                       section in the documentation for a description of the
                       available options. Valid async modes are ``threading``,
                       ``eventlet``, ``gevent`` and ``gevent_uwsgi``. If this
                       argument is not given, ``eventlet`` is tried first, then
                       ``gevent_uwsgi``, then ``gevent``, and finally
                       ``threading``. The first async mode that has all its
                       dependencies installed is then one that is chosen.
    :param ping_interval: The interval in seconds at which the server pings
                          the client. The default is 25 seconds. For advanced
                          control, a two element tuple can be given, where
                          the first number is the ping interval and the second
                          is a grace period added by the server.
    :param ping_timeout: The time in seconds that the client waits for the
                         server to respond before disconnecting. The default
                         is 5 seconds.
    :param max_http_buffer_size: The maximum size of a message when using the
                                 polling transport. The default is 1,000,000
                                 bytes.
    :param allow_upgrades: Whether to allow transport upgrades or not. The
                           default is ``True``.
    :param http_compression: Whether to compress packages when using the
                             polling transport. The default is ``True``.
    :param compression_threshold: Only compress messages when their byte size
                                  is greater than this value. The default is
                                  1024 bytes.
    :param cookie: If set to a string, it is the name of the HTTP cookie the
                   server sends back to the client containing the client
                   session id. If set to a dictionary, the ``'name'`` key
                   contains the cookie name and other keys define cookie
                   attributes, where the value of each attribute can be a
                   string, a callable with no arguments, or a boolean. If set
                   to ``None`` (the default), a cookie is not sent to the
                   client.
    :param cors_allowed_origins: Origin or list of origins that are allowed to
                                 connect to this server. Only the same origin
                                 is allowed by default. Set this argument to
                                 ``'*'`` to allow all origins, or to ``[]`` to
                                 disable CORS handling.
    :param cors_credentials: Whether credentials (cookies, authentication) are
                             allowed in requests to this server. The default is
                             ``True``.
    :param monitor_clients: If set to ``True``, a background task will ensure
                            inactive clients are closed. Set to ``False`` to
                            disable the monitoring task (not recommended). The
                            default is ``True``.
    :param engineio_logger: To enable Engine.IO logging set to ``True`` or pass
                            a logger object to use. To disable logging set to
                            ``False``. The default is ``False``. Note that
                            fatal errors are logged even when
                            ``engineio_logger`` is ``False``.
    """

    def __init__(self, app=None, **kwargs):
        self.server = None
        self.server_options = {}
        self.wsgi_server = None
        self.handlers = []
        self.namespace_handlers = []
        self.exception_handlers = {}
        self.default_exception_handler = None
        self.manage_session = True
        # We can call init_app when:
        # - we were given the Flask app instance (standard initialization)
        # - we were not given the app, but we were given a message_queue
        #   (standard initialization for auxiliary process)
        # In all other cases we collect the arguments and assume the client
        # will call init_app from an app factory function.
        if app is not None or 'message_queue' in kwargs:
            self.init_app(app, **kwargs)
        else:
            self.server_options.update(kwargs)

    def init_app(self, app, **kwargs):
        if app is not None:
            if not hasattr(app, 'extensions'):
                app.extensions = {}  # pragma: no cover
            app.extensions['socketio'] = self
        self.server_options.update(kwargs)
        self.manage_session = self.server_options.pop('manage_session',
                                                      self.manage_session)

        if 'client_manager' not in kwargs:
            url = self.server_options.get('message_queue', None)
            channel = self.server_options.pop('channel', 'flask-socketio')
            write_only = app is None
            if url:
                if url.startswith(('redis://', "rediss://")):
                    queue_class = socketio.RedisManager
                elif url.startswith(('kafka://')):
                    queue_class = socketio.KafkaManager
                elif url.startswith('zmq'):
                    queue_class = socketio.ZmqManager
                else:
                    queue_class = socketio.KombuManager
                queue = queue_class(url, channel=channel,
                                    write_only=write_only)
                self.server_options['client_manager'] = queue

        if 'json' in self.server_options and \
                self.server_options['json'] == flask_json:
            # flask's json module is tricky to use because its output
            # changes when it is invoked inside or outside the app context
            # so here to prevent any ambiguities we replace it with wrappers
            # that ensure that the app context is always present
            class FlaskSafeJSON(object):
                @staticmethod
                def dumps(*args, **kwargs):
                    with app.app_context():
                        return flask_json.dumps(*args, **kwargs)

                @staticmethod
                def loads(*args, **kwargs):
                    with app.app_context():
                        return flask_json.loads(*args, **kwargs)

            self.server_options['json'] = FlaskSafeJSON

        resource = self.server_options.pop('path', None) or \
            self.server_options.pop('resource', None) or 'socket.io'
        if resource.startswith('/'):
            resource = resource[1:]
        if os.environ.get('FLASK_RUN_FROM_CLI'):
            if self.server_options.get('async_mode') is None:
                self.server_options['async_mode'] = 'threading'
        self.server = socketio.Server(**self.server_options)
        self.async_mode = self.server.async_mode
        for handler in self.handlers:
            self.server.on(handler[0], handler[1], namespace=handler[2])
        for namespace_handler in self.namespace_handlers:
            self.server.register_namespace(namespace_handler)

        if app is not None:
            # here we attach the SocketIO middleware to the SocketIO object so
            # it can be referenced later if debug middleware needs to be
            # inserted
            self.sockio_mw = _SocketIOMiddleware(self.server, app,
                                                 socketio_path=resource)
            app.wsgi_app = self.sockio_mw

    def on(self, message, namespace=None):
        """Decorator to register a SocketIO event handler.

        This decorator must be applied to SocketIO event handlers. Example::

            @socketio.on('my event', namespace='/chat')
            def handle_my_custom_event(json):
                print('received json: ' + str(json))

        :param message: The name of the event. This is normally a user defined
                        string, but a few event names are already defined. Use
                        ``'message'`` to define a handler that takes a string
                        payload, ``'json'`` to define a handler that takes a
                        JSON blob payload, ``'connect'`` or ``'disconnect'``
                        to create handlers for connection and disconnection
                        events.
        :param namespace: The namespace on which the handler is to be
                          registered. Defaults to the global namespace.
        """
        namespace = namespace or '/'

        def decorator(handler):
            @wraps(handler)
            def _handler(sid, *args):
                return self._handle_event(handler, message, namespace, sid,
                                          *args)

            if self.server:
                self.server.on(message, _handler, namespace=namespace)
            else:
                self.handlers.append((message, _handler, namespace))
            return handler
        return decorator

    def on_error(self, namespace=None):
        """Decorator to define a custom error handler for SocketIO events.

        This decorator can be applied to a function that acts as an error
        handler for a namespace. This handler will be invoked when a SocketIO
        event handler raises an exception. The handler function must accept one
        argument, which is the exception raised. Example::

            @socketio.on_error(namespace='/chat')
            def chat_error_handler(e):
                print('An error has occurred: ' + str(e))

        :param namespace: The namespace for which to register the error
                          handler. Defaults to the global namespace.
        """
        namespace = namespace or '/'

        def decorator(exception_handler):
            if not callable(exception_handler):
                raise ValueError('exception_handler must be callable')
            self.exception_handlers[namespace] = exception_handler
            return exception_handler
        return decorator

    def on_error_default(self, exception_handler):
        """Decorator to define a default error handler for SocketIO events.

        This decorator can be applied to a function that acts as a default
        error handler for any namespaces that do not have a specific handler.
        Example::

            @socketio.on_error_default
            def error_handler(e):
                print('An error has occurred: ' + str(e))
        """
        if not callable(exception_handler):
            raise ValueError('exception_handler must be callable')
        self.default_exception_handler = exception_handler
        return exception_handler

    def on_event(self, message, handler, namespace=None):
        """Register a SocketIO event handler.

        ``on_event`` is the non-decorator version of ``'on'``.

        Example::

            def on_foo_event(json):
                print('received json: ' + str(json))

            socketio.on_event('my event', on_foo_event, namespace='/chat')

        :param message: The name of the event. This is normally a user defined
                        string, but a few event names are already defined. Use
                        ``'message'`` to define a handler that takes a string
                        payload, ``'json'`` to define a handler that takes a
                        JSON blob payload, ``'connect'`` or ``'disconnect'``
                        to create handlers for connection and disconnection
                        events.
        :param handler: The function that handles the event.
        :param namespace: The namespace on which the handler is to be
                          registered. Defaults to the global namespace.
        """
        self.on(message, namespace=namespace)(handler)

    def event(self, *args, **kwargs):
        """Decorator to register an event handler.

        This is a simplified version of the ``on()`` method that takes the
        event name from the decorated function.

        Example usage::

            @socketio.event
            def my_event(data):
                print('Received data: ', data)

        The above example is equivalent to::

            @socketio.on('my_event')
            def my_event(data):
                print('Received data: ', data)

        A custom namespace can be given as an argument to the decorator::

            @socketio.event(namespace='/test')
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

    def on_namespace(self, namespace_handler):
        if not isinstance(namespace_handler, Namespace):
            raise ValueError('Not a namespace instance.')
        namespace_handler._set_socketio(self)
        if self.server:
            self.server.register_namespace(namespace_handler)
        else:
            self.namespace_handlers.append(namespace_handler)

    def emit(self, event, *args, **kwargs):
        """Emit a server generated SocketIO event.

        This function emits a SocketIO event to one or more connected clients.
        A JSON blob can be attached to the event as payload. This function can
        be used outside of a SocketIO event context, so it is appropriate to
        use when the server is the originator of an event, outside of any
        client context, such as in a regular HTTP request handler or a
        background task. Example::

            @app.route('/ping')
            def ping():
                socketio.emit('ping event', {'data': 42}, namespace='/chat')

        :param event: The name of the user event to emit.
        :param args: A dictionary with the JSON data to send as payload.
        :param namespace: The namespace under which the message is to be sent.
                          Defaults to the global namespace.
        :param to: Send the message to all the users in the given room, or to
                   the user with the given session ID. If this parameter is not
                   included, the event is sent to all connected users.
        :param include_self: ``True`` to include the sender when broadcasting
                             or addressing a room, or ``False`` to send to
                             everyone but the sender.
        :param skip_sid: The session id of a client to ignore when broadcasting
                         or addressing a room. This is typically set to the
                         originator of the message, so that everyone except
                         that client receive the message. To skip multiple sids
                         pass a list.
        :param callback: If given, this function will be called to acknowledge
                         that the client has received the message. The
                         arguments that will be passed to the function are
                         those provided by the client. Callback functions can
                         only be used when addressing an individual client.
        """
        namespace = kwargs.pop('namespace', '/')
        to = kwargs.pop('to', None) or kwargs.pop('room', None)
        include_self = kwargs.pop('include_self', True)
        skip_sid = kwargs.pop('skip_sid', None)
        if not include_self and not skip_sid:
            skip_sid = flask.request.sid
        callback = kwargs.pop('callback', None)
        if callback:
            # wrap the callback so that it sets app app and request contexts
            sid = None
            original_callback = callback
            original_namespace = namespace
            if has_request_context():
                sid = getattr(flask.request, 'sid', None)
                original_namespace = getattr(flask.request, 'namespace', None)

            def _callback_wrapper(*args):
                return self._handle_event(original_callback, None,
                                          original_namespace, sid, *args)

            if sid:
                # the callback wrapper above will install a request context
                # before invoking the original callback
                # we only use it if the emit was issued from a Socket.IO
                # populated request context (i.e. request.sid is defined)
                callback = _callback_wrapper
        self.server.emit(event, *args, namespace=namespace, to=to,
                         skip_sid=skip_sid, callback=callback, **kwargs)

    def call(self, event, *args, **kwargs):  # pragma: no cover
        """Emit a SocketIO event and wait for the response.

        This method issues an emit with a callback and waits for the callback
        to be invoked by the client before returning. If the callback isn’t
        invoked before the timeout, then a TimeoutError exception is raised. If
        the Socket.IO connection drops during the wait, this method still waits
        until the specified timeout. Example::

            def get_status(client, data):
                status = call('status', {'data': data}, to=client)

        :param event: The name of the user event to emit.
        :param args: A dictionary with the JSON data to send as payload.
        :param namespace: The namespace under which the message is to be sent.
                          Defaults to the global namespace.
        :param to: The session ID of the recipient client.
        :param timeout: The waiting timeout. If the timeout is reached before
                        the client acknowledges the event, then a
                        ``TimeoutError`` exception is raised. The default is 60
                        seconds.
        :param ignore_queue: Only used when a message queue is configured. If
                             set to ``True``, the event is emitted to the
                             client directly, without going through the queue.
                             This is more efficient, but only works when a
                             single server process is used, or when there is a
                             single addressee. It is recommended to always
                             leave this parameter with its default value of
                             ``False``.
        """
        namespace = kwargs.pop('namespace', '/')
        to = kwargs.pop('to', None) or kwargs.pop('room', None)
        return self.server.call(event, *args, namespace=namespace, to=to,
                                **kwargs)

    def send(self, data, json=False, namespace=None, to=None,
             callback=None, include_self=True, skip_sid=None, **kwargs):
        """Send a server-generated SocketIO message.

        This function sends a simple SocketIO message to one or more connected
        clients. The message can be a string or a JSON blob. This is a simpler
        version of ``emit()``, which should be preferred. This function can be
        used outside of a SocketIO event context, so it is appropriate to use
        when the server is the originator of an event.

        :param data: The message to send, either a string or a JSON blob.
        :param json: ``True`` if ``message`` is a JSON blob, ``False``
                     otherwise.
        :param namespace: The namespace under which the message is to be sent.
                          Defaults to the global namespace.
        :param to: Send the message to all the users in the given room, or to
                   the user with the given session ID. If this parameter is not
                   included, the event is sent to all connected users.
        :param include_self: ``True`` to include the sender when broadcasting
                             or addressing a room, or ``False`` to send to
                             everyone but the sender.
        :param skip_sid: The session id of a client to ignore when broadcasting
                         or addressing a room. This is typically set to the
                         originator of the message, so that everyone except
                         that client receive the message. To skip multiple sids
                         pass a list.
        :param callback: If given, this function will be called to acknowledge
                         that the client has received the message. The
                         arguments that will be passed to the function are
                         those provided by the client. Callback functions can
                         only be used when addressing an individual client.
        """
        skip_sid = flask.request.sid if not include_self else skip_sid
        if json:
            self.emit('json', data, namespace=namespace, to=to,
                      skip_sid=skip_sid, callback=callback, **kwargs)
        else:
            self.emit('message', data, namespace=namespace, to=to,
                      skip_sid=skip_sid, callback=callback, **kwargs)

    def close_room(self, room, namespace=None):
        """Close a room.

        This function removes any users that are in the given room and then
        deletes the room from the server. This function can be used outside
        of a SocketIO event context.

        :param room: The name of the room to close.
        :param namespace: The namespace under which the room exists. Defaults
                          to the global namespace.
        """
        self.server.close_room(room, namespace)

    def run(self, app, host=None, port=None, **kwargs):  # pragma: no cover
        """Run the SocketIO web server.

        :param app: The Flask application instance.
        :param host: The hostname or IP address for the server to listen on.
                     Defaults to 127.0.0.1.
        :param port: The port number for the server to listen on. Defaults to
                     5000.
        :param debug: ``True`` to start the server in debug mode, ``False`` to
                      start in normal mode.
        :param use_reloader: ``True`` to enable the Flask reloader, ``False``
                             to disable it.
        :param reloader_options: A dictionary with options that are passed to
                                 the Flask reloader, such as ``extra_files``,
                                 ``reloader_type``, etc.
        :param extra_files: A list of additional files that the Flask
                            reloader should watch. Defaults to ``None``.
                            Deprecated, use ``reloader_options`` instead.
        :param log_output: If ``True``, the server logs all incoming
                           connections. If ``False`` logging is disabled.
                           Defaults to ``True`` in debug mode, ``False``
                           in normal mode. Unused when the threading async
                           mode is used.
        :param allow_unsafe_werkzeug: Set to ``True`` to allow the use of the
                                      Werkzeug web server in a production
                                      setting. Default is ``False``. Set to
                                      ``True`` at your own risk.
        :param kwargs: Additional web server options. The web server options
                       are specific to the server used in each of the supported
                       async modes. Note that options provided here will
                       not be seen when using an external web server such
                       as gunicorn, since this method is not called in that
                       case.
        """
        if host is None:
            host = '127.0.0.1'
        if port is None:
            server_name = app.config['SERVER_NAME']
            if server_name and ':' in server_name:
                port = int(server_name.rsplit(':', 1)[1])
            else:
                port = 5000

        debug = kwargs.pop('debug', app.debug)
        log_output = kwargs.pop('log_output', debug)
        use_reloader = kwargs.pop('use_reloader', debug)
        extra_files = kwargs.pop('extra_files', None)
        reloader_options = kwargs.pop('reloader_options', {})
        if extra_files:
            reloader_options['extra_files'] = extra_files

        app.debug = debug
        if app.debug and self.server.eio.async_mode != 'threading':
            # put the debug middleware between the SocketIO middleware
            # and the Flask application instance
            #
            #    mw1   mw2   mw3   Flask app
            #     o ---- o ---- o ---- o
            #    /
            #   o Flask-SocketIO
            #    \  middleware
            #     o
            #  Flask-SocketIO WebSocket handler
            #
            # BECOMES
            #
            #  dbg-mw   mw1   mw2   mw3   Flask app
            #     o ---- o ---- o ---- o ---- o
            #    /
            #   o Flask-SocketIO
            #    \  middleware
            #     o
            #  Flask-SocketIO WebSocket handler
            #
            self.sockio_mw.wsgi_app = DebuggedApplication(
                self.sockio_mw.wsgi_app, evalex=True)

        if self.server.eio.async_mode == 'threading':
            try:
                import simple_websocket  # noqa: F401
            except ImportError:
                from werkzeug._internal import _log
                _log('warning', 'WebSocket transport not available. Install '
                                'simple-websocket for improved performance.')
            allow_unsafe_werkzeug = kwargs.pop('allow_unsafe_werkzeug',
                                               False)
            if not sys.stdin or not sys.stdin.isatty():  # pragma: no cover
                if not allow_unsafe_werkzeug:
                    raise RuntimeError('The Werkzeug web server is not '
                                       'designed to run in production. Pass '
                                       'allow_unsafe_werkzeug=True to the '
                                       'run() method to disable this error.')
                else:
                    from werkzeug._internal import _log
                    _log('warning', ('Werkzeug appears to be used in a '
                                     'production deployment. Consider '
                                     'switching to a production web server '
                                     'instead.'))
            app.run(host=host, port=port, threaded=True,
                    use_reloader=use_reloader, **reloader_options, **kwargs)
        elif self.server.eio.async_mode == 'eventlet':
            def run_server():
                import eventlet
                import eventlet.wsgi
                import eventlet.green
                addresses = eventlet.green.socket.getaddrinfo(host, port)
                if not addresses:
                    raise RuntimeError(
                        'Could not resolve host to a valid address')
                eventlet_socket = eventlet.listen(addresses[0][4],
                                                  addresses[0][0])

                # If provided an SSL argument, use an SSL socket
                ssl_args = ['keyfile', 'certfile', 'server_side', 'cert_reqs',
                            'ssl_version', 'ca_certs',
                            'do_handshake_on_connect', 'suppress_ragged_eofs',
                            'ciphers']
                ssl_params = {k: kwargs[k] for k in kwargs
                              if k in ssl_args and kwargs[k] is not None}
                for k in ssl_args:
                    kwargs.pop(k, None)
                if len(ssl_params) > 0:
                    ssl_params['server_side'] = True  # Listening requires true
                    eventlet_socket = eventlet.wrap_ssl(eventlet_socket,
                                                        **ssl_params)

                eventlet.wsgi.server(eventlet_socket, app,
                                     log_output=log_output, **kwargs)

            if use_reloader:
                run_with_reloader(run_server, **reloader_options)
            else:
                run_server()
        elif self.server.eio.async_mode == 'gevent':
            from gevent import pywsgi
            try:
                from geventwebsocket.handler import WebSocketHandler
                websocket = True
            except ImportError:
                app.logger.warning(
                    'WebSocket transport not available. Install '
                    'gevent-websocket for improved performance.')
                websocket = False

            log = 'default'
            if not log_output:
                log = None
            if websocket:
                self.wsgi_server = pywsgi.WSGIServer(
                    (host, port), app, handler_class=WebSocketHandler,
                    log=log, **kwargs)
            else:
                self.wsgi_server = pywsgi.WSGIServer((host, port), app,
                                                     log=log, **kwargs)

            if use_reloader:
                # monkey patching is required by the reloader
                from gevent import monkey
                monkey.patch_thread()
                monkey.patch_time()

                def run_server():
                    self.wsgi_server.serve_forever()

                run_with_reloader(run_server, **reloader_options)
            else:
                self.wsgi_server.serve_forever()

    def stop(self):
        """Stop a running SocketIO web server.

        This method must be called from a HTTP or SocketIO handler function.
        """
        if self.server.eio.async_mode == 'threading':
            func = flask.request.environ.get('werkzeug.server.shutdown')
            if func:
                func()
            else:
                raise RuntimeError('Cannot stop unknown web server')
        elif self.server.eio.async_mode == 'eventlet':
            raise SystemExit
        elif self.server.eio.async_mode == 'gevent':
            self.wsgi_server.stop()

    def start_background_task(self, target, *args, **kwargs):
        """Start a background task using the appropriate async model.

        This is a utility function that applications can use to start a
        background task using the method that is compatible with the
        selected async mode.

        :param target: the target function to execute.
        :param args: arguments to pass to the function.
        :param kwargs: keyword arguments to pass to the function.

        This function returns an object that represents the background task,
        on which the ``join()`` method can be invoked to wait for the task to
        complete.
        """
        return self.server.start_background_task(target, *args, **kwargs)

    def sleep(self, seconds=0):
        """Sleep for the requested amount of time using the appropriate async
        model.

        This is a utility function that applications can use to put a task to
        sleep without having to worry about using the correct call for the
        selected async mode.
        """
        return self.server.sleep(seconds)

    def test_client(self, app, namespace=None, query_string=None,
                    headers=None, auth=None, flask_test_client=None):
        """The Socket.IO test client is useful for testing a Flask-SocketIO
        server. It works in a similar way to the Flask Test Client, but
        adapted to the Socket.IO server.

        :param app: The Flask application instance.
        :param namespace: The namespace for the client. If not provided, the
                          client connects to the server on the global
                          namespace.
        :param query_string: A string with custom query string arguments.
        :param headers: A dictionary with custom HTTP headers.
        :param auth: Optional authentication data, given as a dictionary.
        :param flask_test_client: The instance of the Flask test client
                                  currently in use. Passing the Flask test
                                  client is optional, but is necessary if you
                                  want the Flask user session and any other
                                  cookies set in HTTP routes accessible from
                                  Socket.IO events.
        """
        return SocketIOTestClient(app, self, namespace=namespace,
                                  query_string=query_string, headers=headers,
                                  auth=auth,
                                  flask_test_client=flask_test_client)

    def _handle_event(self, handler, message, namespace, sid, *args):
        environ = self.server.get_environ(sid, namespace=namespace)
        if not environ:
            # we don't have record of this client, ignore this event
            return '', 400
        app = environ['flask.app']
        with app.request_context(environ):
            if self.manage_session:
                # manage a separate session for this client's Socket.IO events
                # created as a copy of the regular user session
                if 'saved_session' not in environ:
                    environ['saved_session'] = _ManagedSession(flask.session)
                session_obj = environ['saved_session']
                if hasattr(flask, 'globals') and \
                        hasattr(flask.globals, 'request_ctx'):
                    # update session for Flask >= 2.2
                    ctx = flask.globals.request_ctx._get_current_object()
                else:  # pragma: no cover
                    # update session for Flask < 2.2
                    ctx = flask._request_ctx_stack.top
                ctx.session = session_obj
            else:
                # let Flask handle the user session
                # for cookie based sessions, this effectively freezes the
                # session to its state at connection time
                # for server-side sessions, this allows HTTP and Socket.IO to
                # share the session, with both having read/write access to it
                session_obj = flask.session._get_current_object()
            flask.request.sid = sid
            flask.request.namespace = namespace
            flask.request.event = {'message': message, 'args': args}
            try:
                if message == 'connect':
                    auth = args[1] if len(args) > 1 else None
                    try:
                        ret = handler(auth)
                    except TypeError:
                        ret = handler()
                else:
                    ret = handler(*args)
            except ConnectionRefusedError:
                raise  # let this error bubble up to python-socketio
            except:
                err_handler = self.exception_handlers.get(
                    namespace, self.default_exception_handler)
                if err_handler is None:
                    raise
                type, value, traceback = sys.exc_info()
                return err_handler(value)
            if not self.manage_session:
                # when Flask is managing the user session, it needs to save it
                if not hasattr(session_obj, 'modified') or \
                        session_obj.modified:
                    resp = app.response_class()
                    app.session_interface.save_session(app, session_obj, resp)
            return ret


def emit(event, *args, **kwargs):
    """Emit a SocketIO event.

    This function emits a SocketIO event to one or more connected clients. A
    JSON blob can be attached to the event as payload. This is a function that
    can only be called from a SocketIO event handler, as in obtains some
    information from the current client context. Example::

        @socketio.on('my event')
        def handle_my_custom_event(json):
            emit('my response', {'data': 42})

    :param event: The name of the user event to emit.
    :param args: A dictionary with the JSON data to send as payload.
    :param namespace: The namespace under which the message is to be sent.
                      Defaults to the namespace used by the originating event.
                      A ``'/'`` can be used to explicitly specify the global
                      namespace.
    :param callback: Callback function to invoke with the client's
                     acknowledgement.
    :param broadcast: ``True`` to send the message to all clients, or ``False``
                      to only reply to the sender of the originating event.
    :param to: Send the message to all the users in the given room, or to the
               user with the given session ID. If this argument is not set and
               ``broadcast`` is ``False``, then the message is sent only to the
               originating user.
    :param include_self: ``True`` to include the sender when broadcasting or
                         addressing a room, or ``False`` to send to everyone
                         but the sender.
    :param skip_sid: The session id of a client to ignore when broadcasting
                     or addressing a room. This is typically set to the
                     originator of the message, so that everyone except
                     that client receive the message. To skip multiple sids
                     pass a list.
    :param ignore_queue: Only used when a message queue is configured. If
                         set to ``True``, the event is emitted to the
                         clients directly, without going through the queue.
                         This is more efficient, but only works when a
                         single server process is used, or when there is a
                         single addressee. It is recommended to always leave
                         this parameter with its default value of ``False``.
    """
    if 'namespace' in kwargs:
        namespace = kwargs['namespace']
    else:
        namespace = flask.request.namespace
    callback = kwargs.get('callback')
    broadcast = kwargs.get('broadcast')
    to = kwargs.pop('to', None) or kwargs.pop('room', None)
    if to is None and not broadcast:
        to = flask.request.sid
    include_self = kwargs.get('include_self', True)
    skip_sid = kwargs.get('skip_sid')
    ignore_queue = kwargs.get('ignore_queue', False)

    socketio = flask.current_app.extensions['socketio']
    return socketio.emit(event, *args, namespace=namespace, to=to,
                         include_self=include_self, skip_sid=skip_sid,
                         callback=callback, ignore_queue=ignore_queue)


def call(event, *args, **kwargs):  # pragma: no cover
    """Emit a SocketIO event and wait for the response.

    This function issues an emit with a callback and waits for the callback to
    be invoked by the client before returning. If the callback isn’t invoked
    before the timeout, then a TimeoutError exception is raised. If the
    Socket.IO connection drops during the wait, this method still waits until
    the specified timeout. Example::

        def get_status(client, data):
            status = call('status', {'data': data}, to=client)

    :param event: The name of the user event to emit.
    :param args: A dictionary with the JSON data to send as payload.
    :param namespace: The namespace under which the message is to be sent.
                      Defaults to the namespace used by the originating event.
                      A ``'/'`` can be used to explicitly specify the global
                      namespace.
    :param to: The session ID of the recipient client. If this argument is not
               given, the event is sent to the originating client.
    :param timeout: The waiting timeout. If the timeout is reached before the
                    client acknowledges the event, then a ``TimeoutError``
                    exception is raised. The default is 60 seconds.
    :param ignore_queue: Only used when a message queue is configured. If
                         set to ``True``, the event is emitted to the
                         client directly, without going through the queue.
                         This is more efficient, but only works when a
                         single server process is used, or when there is a
                         single addressee. It is recommended to always leave
                         this parameter with its default value of ``False``.
    """
    if 'namespace' in kwargs:
        namespace = kwargs['namespace']
    else:
        namespace = flask.request.namespace
    to = kwargs.pop('to', None) or kwargs.pop('room', None)
    if to is None:
        to = flask.request.sid
    timeout = kwargs.get('timeout', 60)
    ignore_queue = kwargs.get('ignore_queue', False)

    socketio = flask.current_app.extensions['socketio']
    return socketio.call(event, *args, namespace=namespace, to=to,
                         ignore_queue=ignore_queue, timeout=timeout)


def send(message, **kwargs):
    """Send a SocketIO message.

    This function sends a simple SocketIO message to one or more connected
    clients. The message can be a string or a JSON blob. This is a simpler
    version of ``emit()``, which should be preferred. This is a function that
    can only be called from a SocketIO event handler.

    :param message: The message to send, either a string or a JSON blob.
    :param json: ``True`` if ``message`` is a JSON blob, ``False``
                     otherwise.
    :param namespace: The namespace under which the message is to be sent.
                      Defaults to the namespace used by the originating event.
                      An empty string can be used to use the global namespace.
    :param callback: Callback function to invoke with the client's
                     acknowledgement.
    :param broadcast: ``True`` to send the message to all connected clients, or
                      ``False`` to only reply to the sender of the originating
                      event.
    :param to: Send the message to all the users in the given room, or to the
               user with the given session ID. If this argument is not set and
               ``broadcast`` is ``False``, then the message is sent only to the
               originating user.
    :param include_self: ``True`` to include the sender when broadcasting or
                         addressing a room, or ``False`` to send to everyone
                         but the sender.
    :param skip_sid: The session id of a client to ignore when broadcasting
                     or addressing a room. This is typically set to the
                     originator of the message, so that everyone except
                     that client receive the message. To skip multiple sids
                     pass a list.
    :param ignore_queue: Only used when a message queue is configured. If
                         set to ``True``, the event is emitted to the
                         clients directly, without going through the queue.
                         This is more efficient, but only works when a
                         single server process is used, or when there is a
                         single addressee. It is recommended to always leave
                         this parameter with its default value of ``False``.
    """
    json = kwargs.get('json', False)
    if 'namespace' in kwargs:
        namespace = kwargs['namespace']
    else:
        namespace = flask.request.namespace
    callback = kwargs.get('callback')
    broadcast = kwargs.get('broadcast')
    to = kwargs.pop('to', None) or kwargs.pop('room', None)
    if to is None and not broadcast:
        to = flask.request.sid
    include_self = kwargs.get('include_self', True)
    skip_sid = kwargs.get('skip_sid')
    ignore_queue = kwargs.get('ignore_queue', False)

    socketio = flask.current_app.extensions['socketio']
    return socketio.send(message, json=json, namespace=namespace, to=to,
                         include_self=include_self, skip_sid=skip_sid,
                         callback=callback, ignore_queue=ignore_queue)


def join_room(room, sid=None, namespace=None):
    """Join a room.

    This function puts the user in a room, under the current namespace. The
    user and the namespace are obtained from the event context. This is a
    function that can only be called from a SocketIO event handler. Example::

        @socketio.on('join')
        def on_join(data):
            username = session['username']
            room = data['room']
            join_room(room)
            send(username + ' has entered the room.', to=room)

    :param room: The name of the room to join.
    :param sid: The session id of the client. If not provided, the client is
                obtained from the request context.
    :param namespace: The namespace for the room. If not provided, the
                      namespace is obtained from the request context.
    """
    socketio = flask.current_app.extensions['socketio']
    sid = sid or flask.request.sid
    namespace = namespace or flask.request.namespace
    socketio.server.enter_room(sid, room, namespace=namespace)


def leave_room(room, sid=None, namespace=None):
    """Leave a room.

    This function removes the user from a room, under the current namespace.
    The user and the namespace are obtained from the event context. Example::

        @socketio.on('leave')
        def on_leave(data):
            username = session['username']
            room = data['room']
            leave_room(room)
            send(username + ' has left the room.', to=room)

    :param room: The name of the room to leave.
    :param sid: The session id of the client. If not provided, the client is
                obtained from the request context.
    :param namespace: The namespace for the room. If not provided, the
                      namespace is obtained from the request context.
    """
    socketio = flask.current_app.extensions['socketio']
    sid = sid or flask.request.sid
    namespace = namespace or flask.request.namespace
    socketio.server.leave_room(sid, room, namespace=namespace)


def close_room(room, namespace=None):
    """Close a room.

    This function removes any users that are in the given room and then deletes
    the room from the server.

    :param room: The name of the room to close.
    :param namespace: The namespace for the room. If not provided, the
                      namespace is obtained from the request context.
    """
    socketio = flask.current_app.extensions['socketio']
    namespace = namespace or flask.request.namespace
    socketio.server.close_room(room, namespace=namespace)


def rooms(sid=None, namespace=None):
    """Return a list of the rooms the client is in.

    This function returns all the rooms the client has entered, including its
    own room, assigned by the Socket.IO server.

    :param sid: The session id of the client. If not provided, the client is
                obtained from the request context.
    :param namespace: The namespace for the room. If not provided, the
                      namespace is obtained from the request context.
    """
    socketio = flask.current_app.extensions['socketio']
    sid = sid or flask.request.sid
    namespace = namespace or flask.request.namespace
    return socketio.server.rooms(sid, namespace=namespace)


def disconnect(sid=None, namespace=None, silent=False):
    """Disconnect the client.

    This function terminates the connection with the client. As a result of
    this call the client will receive a disconnect event. Example::

        @socketio.on('message')
        def receive_message(msg):
            if is_banned(session['username']):
                disconnect()
            else:
                # ...

    :param sid: The session id of the client. If not provided, the client is
                obtained from the request context.
    :param namespace: The namespace for the room. If not provided, the
                      namespace is obtained from the request context.
    :param silent: this option is deprecated.
    """
    socketio = flask.current_app.extensions['socketio']
    sid = sid or flask.request.sid
    namespace = namespace or flask.request.namespace
    return socketio.server.disconnect(sid, namespace=namespace)
