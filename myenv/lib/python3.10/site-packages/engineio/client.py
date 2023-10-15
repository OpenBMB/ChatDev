from base64 import b64encode
from engineio.json import JSONDecodeError
import logging
import queue
import signal
import ssl
import threading
import time
import urllib

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None
try:
    import websocket
except ImportError:  # pragma: no cover
    websocket = None
from . import exceptions
from . import packet
from . import payload

default_logger = logging.getLogger('engineio.client')
connected_clients = []


def signal_handler(sig, frame):
    """SIGINT handler.

    Disconnect all active clients and then invoke the original signal handler.
    """
    for client in connected_clients[:]:
        if not client.is_asyncio_based():
            client.disconnect()
    if callable(original_signal_handler):
        return original_signal_handler(sig, frame)
    else:  # pragma: no cover
        # Handle case where no original SIGINT handler was present.
        return signal.default_int_handler(sig, frame)


original_signal_handler = None


class Client(object):
    """An Engine.IO client.

    This class implements a fully compliant Engine.IO web client with support
    for websocket and long-polling transports.

    :param logger: To enable logging set to ``True`` or pass a logger object to
                   use. To disable logging set to ``False``. The default is
                   ``False``. Note that fatal errors are logged even when
                   ``logger`` is ``False``.
    :param json: An alternative json module to use for encoding and decoding
                 packets. Custom json modules must have ``dumps`` and ``loads``
                 functions that are compatible with the standard library
                 versions.
    :param request_timeout: A timeout in seconds for requests. The default is
                            5 seconds.
    :param http_session: an initialized ``requests.Session`` object to be used
                         when sending requests to the server. Use it if you
                         need to add special client options such as proxy
                         servers, SSL certificates, custom CA bundle, etc.
    :param ssl_verify: ``True`` to verify SSL certificates, or ``False`` to
                       skip SSL certificate verification, allowing
                       connections to servers with self signed certificates.
                       The default is ``True``.
    :param handle_sigint: Set to ``True`` to automatically handle disconnection
                          when the process is interrupted, or to ``False`` to
                          leave interrupt handling to the calling application.
                          Interrupt handling can only be enabled when the
                          client instance is created in the main thread.
    :param websocket_extra_options: Dictionary containing additional keyword
                                    arguments passed to
                                    ``websocket.create_connection()``.
    """
    event_names = ['connect', 'disconnect', 'message']

    def __init__(self, logger=False, json=None, request_timeout=5,
                 http_session=None, ssl_verify=True, handle_sigint=True,
                 websocket_extra_options=None):
        global original_signal_handler
        if handle_sigint and original_signal_handler is None and \
                threading.current_thread() == threading.main_thread():
            original_signal_handler = signal.signal(signal.SIGINT,
                                                    signal_handler)
        self.handlers = {}
        self.base_url = None
        self.transports = None
        self.current_transport = None
        self.sid = None
        self.upgrades = None
        self.ping_interval = None
        self.ping_timeout = None
        self.http = http_session
        self.external_http = http_session is not None
        self.handle_sigint = handle_sigint
        self.ws = None
        self.read_loop_task = None
        self.write_loop_task = None
        self.queue = None
        self.state = 'disconnected'
        self.ssl_verify = ssl_verify
        self.websocket_extra_options = websocket_extra_options or {}

        if json is not None:
            packet.Packet.json = json
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

        self.request_timeout = request_timeout

    def is_asyncio_based(self):
        return False

    def on(self, event, handler=None):
        """Register an event handler.

        :param event: The event name. Can be ``'connect'``, ``'message'`` or
                      ``'disconnect'``.
        :param handler: The function that should be invoked to handle the
                        event. When this parameter is not given, the method
                        acts as a decorator for the handler function.

        Example usage::

            # as a decorator:
            @eio.on('connect')
            def connect_handler():
                print('Connection request')

            # as a method:
            def message_handler(msg):
                print('Received message: ', msg)
                eio.send('response')
            eio.on('message', message_handler)
        """
        if event not in self.event_names:
            raise ValueError('Invalid event')

        def set_handler(handler):
            self.handlers[event] = handler
            return handler

        if handler is None:
            return set_handler
        set_handler(handler)

    def connect(self, url, headers=None, transports=None,
                engineio_path='engine.io'):
        """Connect to an Engine.IO server.

        :param url: The URL of the Engine.IO server. It can include custom
                    query string parameters if required by the server.
        :param headers: A dictionary with custom headers to send with the
                        connection request.
        :param transports: The list of allowed transports. Valid transports
                           are ``'polling'`` and ``'websocket'``. If not
                           given, the polling transport is connected first,
                           then an upgrade to websocket is attempted.
        :param engineio_path: The endpoint where the Engine.IO server is
                              installed. The default value is appropriate for
                              most cases.

        Example usage::

            eio = engineio.Client()
            eio.connect('http://localhost:5000')
        """
        if self.state != 'disconnected':
            raise ValueError('Client is not in a disconnected state')
        valid_transports = ['polling', 'websocket']
        if transports is not None:
            if isinstance(transports, str):
                transports = [transports]
            transports = [transport for transport in transports
                          if transport in valid_transports]
            if not transports:
                raise ValueError('No valid transports provided')
        self.transports = transports or valid_transports
        self.queue = self.create_queue()
        return getattr(self, '_connect_' + self.transports[0])(
            url, headers or {}, engineio_path)

    def wait(self):
        """Wait until the connection with the server ends.

        Client applications can use this function to block the main thread
        during the life of the connection.
        """
        if self.read_loop_task:
            self.read_loop_task.join()

    def send(self, data):
        """Send a message to the server.

        :param data: The data to send to the server. Data can be of type
                     ``str``, ``bytes``, ``list`` or ``dict``. If a ``list``
                     or ``dict``, the data will be serialized as JSON.
        """
        self._send_packet(packet.Packet(packet.MESSAGE, data=data))

    def disconnect(self, abort=False):
        """Disconnect from the server.

        :param abort: If set to ``True``, do not wait for background tasks
                      associated with the connection to end.
        """
        if self.state == 'connected':
            self._send_packet(packet.Packet(packet.CLOSE))
            self.queue.put(None)
            self.state = 'disconnecting'
            self._trigger_event('disconnect', run_async=False)
            if self.current_transport == 'websocket':
                self.ws.close()
            if not abort:
                self.read_loop_task.join()
            self.state = 'disconnected'
            try:
                connected_clients.remove(self)
            except ValueError:  # pragma: no cover
                pass
        self._reset()

    def transport(self):
        """Return the name of the transport currently in use.

        The possible values returned by this function are ``'polling'`` and
        ``'websocket'``.
        """
        return self.current_transport

    def start_background_task(self, target, *args, **kwargs):
        """Start a background task.

        This is a utility function that applications can use to start a
        background task.

        :param target: the target function to execute.
        :param args: arguments to pass to the function.
        :param kwargs: keyword arguments to pass to the function.

        This function returns an object that represents the background task,
        on which the ``join()`` method can be invoked to wait for the task to
        complete.
        """
        th = threading.Thread(target=target, args=args, kwargs=kwargs)
        th.start()
        return th

    def sleep(self, seconds=0):
        """Sleep for the requested amount of time."""
        return time.sleep(seconds)

    def create_queue(self, *args, **kwargs):
        """Create a queue object."""
        q = queue.Queue(*args, **kwargs)
        q.Empty = queue.Empty
        return q

    def create_event(self, *args, **kwargs):
        """Create an event object."""
        return threading.Event(*args, **kwargs)

    def _reset(self):
        self.state = 'disconnected'
        self.sid = None

    def _connect_polling(self, url, headers, engineio_path):
        """Establish a long-polling connection to the Engine.IO server."""
        if requests is None:  # pragma: no cover
            # not installed
            self.logger.error('requests package is not installed -- cannot '
                              'send HTTP requests!')
            return
        self.base_url = self._get_engineio_url(url, engineio_path, 'polling')
        self.logger.info('Attempting polling connection to ' + self.base_url)
        r = self._send_request(
            'GET', self.base_url + self._get_url_timestamp(), headers=headers,
            timeout=self.request_timeout)
        if r is None or isinstance(r, str):
            self._reset()
            raise exceptions.ConnectionError(
                r or 'Connection refused by the server')
        if r.status_code < 200 or r.status_code >= 300:
            self._reset()
            try:
                arg = r.json()
            except JSONDecodeError:
                arg = None
            raise exceptions.ConnectionError(
                'Unexpected status code {} in server response'.format(
                    r.status_code), arg)
        try:
            p = payload.Payload(encoded_payload=r.content.decode('utf-8'))
        except ValueError:
            raise exceptions.ConnectionError(
                'Unexpected response from server') from None
        open_packet = p.packets[0]
        if open_packet.packet_type != packet.OPEN:
            raise exceptions.ConnectionError(
                'OPEN packet not returned by server')
        self.logger.info(
            'Polling connection accepted with ' + str(open_packet.data))
        self.sid = open_packet.data['sid']
        self.upgrades = open_packet.data['upgrades']
        self.ping_interval = int(open_packet.data['pingInterval']) / 1000.0
        self.ping_timeout = int(open_packet.data['pingTimeout']) / 1000.0
        self.current_transport = 'polling'
        self.base_url += '&sid=' + self.sid

        self.state = 'connected'
        connected_clients.append(self)
        self._trigger_event('connect', run_async=False)

        for pkt in p.packets[1:]:
            self._receive_packet(pkt)

        if 'websocket' in self.upgrades and 'websocket' in self.transports:
            # attempt to upgrade to websocket
            if self._connect_websocket(url, headers, engineio_path):
                # upgrade to websocket succeeded, we're done here
                return

        # start background tasks associated with this client
        self.write_loop_task = self.start_background_task(self._write_loop)
        self.read_loop_task = self.start_background_task(
            self._read_loop_polling)

    def _connect_websocket(self, url, headers, engineio_path):
        """Establish or upgrade to a WebSocket connection with the server."""
        if websocket is None:  # pragma: no cover
            # not installed
            self.logger.error('websocket-client package not installed, only '
                              'polling transport is available')
            return False
        websocket_url = self._get_engineio_url(url, engineio_path, 'websocket')
        if self.sid:
            self.logger.info(
                'Attempting WebSocket upgrade to ' + websocket_url)
            upgrade = True
            websocket_url += '&sid=' + self.sid
        else:
            upgrade = False
            self.base_url = websocket_url
            self.logger.info(
                'Attempting WebSocket connection to ' + websocket_url)

        # get cookies and other settings from the long-polling connection
        # so that they are preserved when connecting to the WebSocket route
        cookies = None
        extra_options = {}
        if self.http:
            # cookies
            cookies = '; '.join(["{}={}".format(cookie.name, cookie.value)
                                 for cookie in self.http.cookies])
            for header, value in headers.items():
                if header.lower() == 'cookie':
                    if cookies:
                        cookies += '; '
                    cookies += value
                    del headers[header]
                    break

            # auth
            if 'Authorization' not in headers and self.http.auth is not None:
                if not isinstance(self.http.auth, tuple):  # pragma: no cover
                    raise ValueError('Only basic authentication is supported')
                basic_auth = '{}:{}'.format(
                    self.http.auth[0], self.http.auth[1]).encode('utf-8')
                basic_auth = b64encode(basic_auth).decode('utf-8')
                headers['Authorization'] = 'Basic ' + basic_auth

            # cert
            # this can be given as ('certfile', 'keyfile') or just 'certfile'
            if isinstance(self.http.cert, tuple):
                extra_options['sslopt'] = {
                    'certfile': self.http.cert[0],
                    'keyfile': self.http.cert[1]}
            elif self.http.cert:
                extra_options['sslopt'] = {'certfile': self.http.cert}

            # proxies
            if self.http.proxies:
                proxy_url = None
                if websocket_url.startswith('ws://'):
                    proxy_url = self.http.proxies.get(
                        'ws', self.http.proxies.get('http'))
                else:  # wss://
                    proxy_url = self.http.proxies.get(
                        'wss', self.http.proxies.get('https'))
                if proxy_url:
                    parsed_url = urllib.parse.urlparse(
                        proxy_url if '://' in proxy_url
                        else 'scheme://' + proxy_url)
                    extra_options['http_proxy_host'] = parsed_url.hostname
                    extra_options['http_proxy_port'] = parsed_url.port
                    extra_options['http_proxy_auth'] = (
                        (parsed_url.username, parsed_url.password)
                        if parsed_url.username or parsed_url.password
                        else None)

            # verify
            if isinstance(self.http.verify, str):
                if 'sslopt' in extra_options:
                    extra_options['sslopt']['ca_certs'] = self.http.verify
                else:
                    extra_options['sslopt'] = {'ca_certs': self.http.verify}
            elif not self.http.verify:
                self.ssl_verify = False

        if not self.ssl_verify:
            extra_options['sslopt'] = {"cert_reqs": ssl.CERT_NONE}

        # combine internally generated options with the ones supplied by the
        # caller. The caller's options take precedence.
        headers.update(self.websocket_extra_options.pop('header', {}))
        extra_options['header'] = headers
        extra_options['cookie'] = cookies
        extra_options['enable_multithread'] = True
        extra_options['timeout'] = self.request_timeout
        extra_options.update(self.websocket_extra_options)
        try:
            ws = websocket.create_connection(
                websocket_url + self._get_url_timestamp(), **extra_options)
        except (ConnectionError, IOError, websocket.WebSocketException):
            if upgrade:
                self.logger.warning(
                    'WebSocket upgrade failed: connection error')
                return False
            else:
                raise exceptions.ConnectionError('Connection error')
        if upgrade:
            p = packet.Packet(packet.PING, data='probe').encode()
            try:
                ws.send(p)
            except Exception as e:  # pragma: no cover
                self.logger.warning(
                    'WebSocket upgrade failed: unexpected send exception: %s',
                    str(e))
                return False
            try:
                p = ws.recv()
            except Exception as e:  # pragma: no cover
                self.logger.warning(
                    'WebSocket upgrade failed: unexpected recv exception: %s',
                    str(e))
                return False
            pkt = packet.Packet(encoded_packet=p)
            if pkt.packet_type != packet.PONG or pkt.data != 'probe':
                self.logger.warning(
                    'WebSocket upgrade failed: no PONG packet')
                return False
            p = packet.Packet(packet.UPGRADE).encode()
            try:
                ws.send(p)
            except Exception as e:  # pragma: no cover
                self.logger.warning(
                    'WebSocket upgrade failed: unexpected send exception: %s',
                    str(e))
                return False
            self.current_transport = 'websocket'
            self.logger.info('WebSocket upgrade was successful')
        else:
            try:
                p = ws.recv()
            except Exception as e:  # pragma: no cover
                raise exceptions.ConnectionError(
                    'Unexpected recv exception: ' + str(e))
            open_packet = packet.Packet(encoded_packet=p)
            if open_packet.packet_type != packet.OPEN:
                raise exceptions.ConnectionError('no OPEN packet')
            self.logger.info(
                'WebSocket connection accepted with ' + str(open_packet.data))
            self.sid = open_packet.data['sid']
            self.upgrades = open_packet.data['upgrades']
            self.ping_interval = int(open_packet.data['pingInterval']) / 1000.0
            self.ping_timeout = int(open_packet.data['pingTimeout']) / 1000.0
            self.current_transport = 'websocket'

            self.state = 'connected'
            connected_clients.append(self)
            self._trigger_event('connect', run_async=False)
        self.ws = ws
        self.ws.settimeout(self.ping_interval + self.ping_timeout)

        # start background tasks associated with this client
        self.write_loop_task = self.start_background_task(self._write_loop)
        self.read_loop_task = self.start_background_task(
            self._read_loop_websocket)
        return True

    def _receive_packet(self, pkt):
        """Handle incoming packets from the server."""
        packet_name = packet.packet_names[pkt.packet_type] \
            if pkt.packet_type < len(packet.packet_names) else 'UNKNOWN'
        self.logger.info(
            'Received packet %s data %s', packet_name,
            pkt.data if not isinstance(pkt.data, bytes) else '<binary>')
        if pkt.packet_type == packet.MESSAGE:
            self._trigger_event('message', pkt.data, run_async=True)
        elif pkt.packet_type == packet.PING:
            self._send_packet(packet.Packet(packet.PONG, pkt.data))
        elif pkt.packet_type == packet.CLOSE:
            self.disconnect(abort=True)
        elif pkt.packet_type == packet.NOOP:
            pass
        else:
            self.logger.error('Received unexpected packet of type %s',
                              pkt.packet_type)

    def _send_packet(self, pkt):
        """Queue a packet to be sent to the server."""
        if self.state != 'connected':
            return
        self.queue.put(pkt)
        self.logger.info(
            'Sending packet %s data %s',
            packet.packet_names[pkt.packet_type],
            pkt.data if not isinstance(pkt.data, bytes) else '<binary>')

    def _send_request(
            self, method, url, headers=None, body=None,
            timeout=None):  # pragma: no cover
        if self.http is None:
            self.http = requests.Session()
        if not self.ssl_verify:
            self.http.verify = False
        try:
            return self.http.request(method, url, headers=headers, data=body,
                                     timeout=timeout)
        except requests.exceptions.RequestException as exc:
            self.logger.info('HTTP %s request to %s failed with error %s.',
                             method, url, exc)
            return str(exc)

    def _trigger_event(self, event, *args, **kwargs):
        """Invoke an event handler."""
        run_async = kwargs.pop('run_async', False)
        if event in self.handlers:
            if run_async:
                return self.start_background_task(self.handlers[event], *args)
            else:
                try:
                    return self.handlers[event](*args)
                except:
                    self.logger.exception(event + ' handler error')

    def _get_engineio_url(self, url, engineio_path, transport):
        """Generate the Engine.IO connection URL."""
        engineio_path = engineio_path.strip('/')
        parsed_url = urllib.parse.urlparse(url)

        if transport == 'polling':
            scheme = 'http'
        elif transport == 'websocket':
            scheme = 'ws'
        else:  # pragma: no cover
            raise ValueError('invalid transport')
        if parsed_url.scheme in ['https', 'wss']:
            scheme += 's'

        return ('{scheme}://{netloc}/{path}/?{query}'
                '{sep}transport={transport}&EIO=4').format(
                    scheme=scheme, netloc=parsed_url.netloc,
                    path=engineio_path, query=parsed_url.query,
                    sep='&' if parsed_url.query else '',
                    transport=transport)

    def _get_url_timestamp(self):
        """Generate the Engine.IO query string timestamp."""
        return '&t=' + str(time.time())

    def _read_loop_polling(self):
        """Read packets by polling the Engine.IO server."""
        while self.state == 'connected':
            self.logger.info(
                'Sending polling GET request to ' + self.base_url)
            r = self._send_request(
                'GET', self.base_url + self._get_url_timestamp(),
                timeout=max(self.ping_interval, self.ping_timeout) + 5)
            if r is None or isinstance(r, str):
                self.logger.warning(
                    r or 'Connection refused by the server, aborting')
                self.queue.put(None)
                break
            if r.status_code < 200 or r.status_code >= 300:
                self.logger.warning('Unexpected status code %s in server '
                                    'response, aborting', r.status_code)
                self.queue.put(None)
                break
            try:
                p = payload.Payload(encoded_payload=r.content.decode('utf-8'))
            except ValueError:
                self.logger.warning(
                    'Unexpected packet from server, aborting')
                self.queue.put(None)
                break
            for pkt in p.packets:
                self._receive_packet(pkt)

        self.logger.info('Waiting for write loop task to end')
        self.write_loop_task.join()
        if self.state == 'connected':
            self._trigger_event('disconnect', run_async=False)
            try:
                connected_clients.remove(self)
            except ValueError:  # pragma: no cover
                pass
            self._reset()
        self.logger.info('Exiting read loop task')

    def _read_loop_websocket(self):
        """Read packets from the Engine.IO WebSocket connection."""
        while self.state == 'connected':
            p = None
            try:
                p = self.ws.recv()
            except websocket.WebSocketTimeoutException:
                self.logger.warning(
                    'Server has stopped communicating, aborting')
                self.queue.put(None)
                break
            except websocket.WebSocketConnectionClosedException:
                self.logger.warning(
                    'WebSocket connection was closed, aborting')
                self.queue.put(None)
                break
            except Exception as e:
                self.logger.info(
                    'Unexpected error receiving packet: "%s", aborting',
                    str(e))
                self.queue.put(None)
                break
            try:
                pkt = packet.Packet(encoded_packet=p)
            except Exception as e:  # pragma: no cover
                self.logger.info(
                    'Unexpected error decoding packet: "%s", aborting', str(e))
                self.queue.put(None)
                break
            self._receive_packet(pkt)

        self.logger.info('Waiting for write loop task to end')
        self.write_loop_task.join()
        if self.state == 'connected':
            self._trigger_event('disconnect', run_async=False)
            try:
                connected_clients.remove(self)
            except ValueError:  # pragma: no cover
                pass
            self._reset()
        self.logger.info('Exiting read loop task')

    def _write_loop(self):
        """This background task sends packages to the server as they are
        pushed to the send queue.
        """
        while self.state == 'connected':
            # to simplify the timeout handling, use the maximum of the
            # ping interval and ping timeout as timeout, with an extra 5
            # seconds grace period
            timeout = max(self.ping_interval, self.ping_timeout) + 5
            packets = None
            try:
                packets = [self.queue.get(timeout=timeout)]
            except self.queue.Empty:
                self.logger.error('packet queue is empty, aborting')
                break
            if packets == [None]:
                self.queue.task_done()
                packets = []
            else:
                while True:
                    try:
                        packets.append(self.queue.get(block=False))
                    except self.queue.Empty:
                        break
                    if packets[-1] is None:
                        packets = packets[:-1]
                        self.queue.task_done()
                        break
            if not packets:
                # empty packet list returned -> connection closed
                break
            if self.current_transport == 'polling':
                p = payload.Payload(packets=packets)
                r = self._send_request(
                    'POST', self.base_url, body=p.encode(),
                    headers={'Content-Type': 'text/plain'},
                    timeout=self.request_timeout)
                for pkt in packets:
                    self.queue.task_done()
                if r is None or isinstance(r, str):
                    self.logger.warning(
                        r or 'Connection refused by the server, aborting')
                    break
                if r.status_code < 200 or r.status_code >= 300:
                    self.logger.warning('Unexpected status code %s in server '
                                        'response, aborting', r.status_code)
                    self._reset()
                    break
            else:
                # websocket
                try:
                    for pkt in packets:
                        encoded_packet = pkt.encode()
                        if pkt.binary:
                            self.ws.send_binary(encoded_packet)
                        else:
                            self.ws.send(encoded_packet)
                        self.queue.task_done()
                except (websocket.WebSocketConnectionClosedException,
                        BrokenPipeError, OSError):
                    self.logger.warning(
                        'WebSocket connection was closed, aborting')
                    break
        self.logger.info('Exiting write loop task')
