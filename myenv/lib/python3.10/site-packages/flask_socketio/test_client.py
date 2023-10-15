import uuid

from socketio import packet
from socketio.pubsub_manager import PubSubManager
from werkzeug.test import EnvironBuilder


class SocketIOTestClient(object):
    """
    This class is useful for testing a Flask-SocketIO server. It works in a
    similar way to the Flask Test Client, but adapted to the Socket.IO server.

    :param app: The Flask application instance.
    :param socketio: The application's ``SocketIO`` instance.
    :param namespace: The namespace for the client. If not provided, the client
                      connects to the server on the global namespace.
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
    clients = {}

    def __init__(self, app, socketio, namespace=None, query_string=None,
                 headers=None, auth=None, flask_test_client=None):
        def _mock_send_packet(eio_sid, pkt):
            # make sure the packet can be encoded and decoded
            epkt = pkt.encode()
            if not isinstance(epkt, list):
                pkt = packet.Packet(encoded_packet=epkt)
            else:
                pkt = packet.Packet(encoded_packet=epkt[0])
                for att in epkt[1:]:
                    pkt.add_attachment(att)
            client = self.clients.get(eio_sid)
            if not client:
                return
            if pkt.packet_type == packet.EVENT or \
                    pkt.packet_type == packet.BINARY_EVENT:
                if pkt.data[0] == 'message' or pkt.data[0] == 'json':
                    client.queue.append({
                        'name': pkt.data[0],
                        'args': pkt.data[1],
                        'namespace': pkt.namespace or '/'})
                else:
                    client.queue.append({
                        'name': pkt.data[0],
                        'args': pkt.data[1:],
                        'namespace': pkt.namespace or '/'})
            elif pkt.packet_type == packet.ACK or \
                    pkt.packet_type == packet.BINARY_ACK:
                client.acks = {'args': pkt.data,
                               'namespace': pkt.namespace or '/'}
            elif pkt.packet_type in [packet.DISCONNECT, packet.CONNECT_ERROR]:
                client.connected[pkt.namespace or '/'] = False

        self.app = app
        self.flask_test_client = flask_test_client
        self.eio_sid = uuid.uuid4().hex
        self.clients[self.eio_sid] = self
        self.callback_counter = 0
        self.socketio = socketio
        self.connected = {}
        self.queue = []
        self.acks = None
        socketio.server._send_packet = _mock_send_packet
        socketio.server.environ[self.eio_sid] = {}
        socketio.server.async_handlers = False      # easier to test when
        socketio.server.eio.async_handlers = False  # events are sync
        if isinstance(socketio.server.manager, PubSubManager):
            raise RuntimeError('Test client cannot be used with a message '
                               'queue. Disable the queue on your test '
                               'configuration.')
        socketio.server.manager.initialize()
        self.connect(namespace=namespace, query_string=query_string,
                     headers=headers, auth=auth)

    def is_connected(self, namespace=None):
        """Check if a namespace is connected.

        :param namespace: The namespace to check. The global namespace is
                         assumed if this argument is not provided.
        """
        return self.connected.get(namespace or '/', False)

    def connect(self, namespace=None, query_string=None, headers=None,
                auth=None):
        """Connect the client.

        :param namespace: The namespace for the client. If not provided, the
                          client connects to the server on the global
                          namespace.
        :param query_string: A string with custom query string arguments.
        :param headers: A dictionary with custom HTTP headers.
        :param auth: Optional authentication data, given as a dictionary.

        Note that it is usually not necessary to explicitly call this method,
        since a connection is automatically established when an instance of
        this class is created. An example where it this method would be useful
        is when the application accepts multiple namespace connections.
        """
        url = '/socket.io'
        namespace = namespace or '/'
        if query_string:
            if query_string[0] != '?':
                query_string = '?' + query_string
            url += query_string
        environ = EnvironBuilder(url, headers=headers).get_environ()
        environ['flask.app'] = self.app
        if self.flask_test_client:
            # inject cookies from Flask
            if hasattr(self.flask_test_client, '_add_cookies_to_wsgi'):
                # flask >= 2.3
                self.flask_test_client._add_cookies_to_wsgi(environ)
            else:  # pragma: no cover
                # flask < 2.3
                self.flask_test_client.cookie_jar.inject_wsgi(environ)
        self.socketio.server._handle_eio_connect(self.eio_sid, environ)
        pkt = packet.Packet(packet.CONNECT, auth, namespace=namespace)
        self.socketio.server._handle_eio_message(self.eio_sid, pkt.encode())
        sid = self.socketio.server.manager.sid_from_eio_sid(self.eio_sid,
                                                            namespace)
        if sid:
            self.connected[namespace] = True

    def disconnect(self, namespace=None):
        """Disconnect the client.

        :param namespace: The namespace to disconnect. The global namespace is
                         assumed if this argument is not provided.
        """
        if not self.is_connected(namespace):
            raise RuntimeError('not connected')
        pkt = packet.Packet(packet.DISCONNECT, namespace=namespace)
        self.socketio.server._handle_eio_message(self.eio_sid, pkt.encode())
        del self.connected[namespace or '/']

    def emit(self, event, *args, **kwargs):
        """Emit an event to the server.

        :param event: The event name.
        :param *args: The event arguments.
        :param callback: ``True`` if the client requests a callback, ``False``
                         if not. Note that client-side callbacks are not
                         implemented, a callback request will just tell the
                         server to provide the arguments to invoke the
                         callback, but no callback is invoked. Instead, the
                         arguments that the server provided for the callback
                         are returned by this function.
        :param namespace: The namespace of the event. The global namespace is
                          assumed if this argument is not provided.
        """
        namespace = kwargs.pop('namespace', None)
        if not self.is_connected(namespace):
            raise RuntimeError('not connected')
        callback = kwargs.pop('callback', False)
        id = None
        if callback:
            self.callback_counter += 1
            id = self.callback_counter
        pkt = packet.Packet(packet.EVENT, data=[event] + list(args),
                            namespace=namespace, id=id)
        encoded_pkt = pkt.encode()
        if isinstance(encoded_pkt, list):
            for epkt in encoded_pkt:
                self.socketio.server._handle_eio_message(self.eio_sid, epkt)
        else:
            self.socketio.server._handle_eio_message(self.eio_sid, encoded_pkt)
        if self.acks is not None:
            ack = self.acks
            self.acks = None
            return ack['args'][0] if len(ack['args']) == 1 \
                else ack['args']

    def send(self, data, json=False, callback=False, namespace=None):
        """Send a text or JSON message to the server.

        :param data: A string, dictionary or list to send to the server.
        :param json: ``True`` to send a JSON message, ``False`` to send a text
                     message.
        :param callback: ``True`` if the client requests a callback, ``False``
                         if not. Note that client-side callbacks are not
                         implemented, a callback request will just tell the
                         server to provide the arguments to invoke the
                         callback, but no callback is invoked. Instead, the
                         arguments that the server provided for the callback
                         are returned by this function.
        :param namespace: The namespace of the event. The global namespace is
                          assumed if this argument is not provided.
        """
        if json:
            msg = 'json'
        else:
            msg = 'message'
        return self.emit(msg, data, callback=callback, namespace=namespace)

    def get_received(self, namespace=None):
        """Return the list of messages received from the server.

        Since this is not a real client, any time the server emits an event,
        the event is simply stored. The test code can invoke this method to
        obtain the list of events that were received since the last call.

        :param namespace: The namespace to get events from. The global
                          namespace is assumed if this argument is not
                          provided.
        """
        if not self.is_connected(namespace):
            raise RuntimeError('not connected')
        namespace = namespace or '/'
        r = [pkt for pkt in self.queue if pkt['namespace'] == namespace]
        self.queue = [pkt for pkt in self.queue if pkt not in r]
        return r
