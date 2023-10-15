import asyncio
import sys
from urllib.parse import urlsplit

from aiohttp.web import Response, WebSocketResponse


def create_route(app, engineio_server, engineio_endpoint):
    """This function sets up the engine.io endpoint as a route for the
    application.

    Note that both GET and POST requests must be hooked up on the engine.io
    endpoint.
    """
    app.router.add_get(engineio_endpoint, engineio_server.handle_request)
    app.router.add_post(engineio_endpoint, engineio_server.handle_request)
    app.router.add_route('OPTIONS', engineio_endpoint,
                         engineio_server.handle_request)


def translate_request(request):
    """This function takes the arguments passed to the request handler and
    uses them to generate a WSGI compatible environ dictionary.
    """
    message = request._message
    payload = request._payload

    uri_parts = urlsplit(message.path)
    environ = {
        'wsgi.input': payload,
        'wsgi.errors': sys.stderr,
        'wsgi.version': (1, 0),
        'wsgi.async': True,
        'wsgi.multithread': False,
        'wsgi.multiprocess': False,
        'wsgi.run_once': False,
        'SERVER_SOFTWARE': 'aiohttp',
        'REQUEST_METHOD': message.method,
        'QUERY_STRING': uri_parts.query or '',
        'RAW_URI': message.path,
        'SERVER_PROTOCOL': 'HTTP/%s.%s' % message.version,
        'REMOTE_ADDR': '127.0.0.1',
        'REMOTE_PORT': '0',
        'SERVER_NAME': 'aiohttp',
        'SERVER_PORT': '0',
        'aiohttp.request': request
    }

    for hdr_name, hdr_value in message.headers.items():
        hdr_name = hdr_name.upper()
        if hdr_name == 'CONTENT-TYPE':
            environ['CONTENT_TYPE'] = hdr_value
            continue
        elif hdr_name == 'CONTENT-LENGTH':
            environ['CONTENT_LENGTH'] = hdr_value
            continue

        key = 'HTTP_%s' % hdr_name.replace('-', '_')
        if key in environ:
            hdr_value = '%s,%s' % (environ[key], hdr_value)

        environ[key] = hdr_value

    environ['wsgi.url_scheme'] = environ.get('HTTP_X_FORWARDED_PROTO', 'http')

    path_info = uri_parts.path

    environ['PATH_INFO'] = path_info
    environ['SCRIPT_NAME'] = ''

    return environ


def make_response(status, headers, payload, environ):
    """This function generates an appropriate response object for this async
    mode.
    """
    return Response(body=payload, status=int(status.split()[0]),
                    headers=headers)


class WebSocket(object):  # pragma: no cover
    """
    This wrapper class provides a aiohttp WebSocket interface that is
    somewhat compatible with eventlet's implementation.
    """
    def __init__(self, handler, server):
        self.handler = handler
        self._sock = None

    async def __call__(self, environ):
        request = environ['aiohttp.request']
        self._sock = WebSocketResponse(max_msg_size=0)
        await self._sock.prepare(request)

        self.environ = environ
        await self.handler(self)
        return self._sock

    async def close(self):
        await self._sock.close()

    async def send(self, message):
        if isinstance(message, bytes):
            f = self._sock.send_bytes
        else:
            f = self._sock.send_str
        if asyncio.iscoroutinefunction(f):
            await f(message)
        else:
            f(message)

    async def wait(self):
        msg = await self._sock.receive()
        if not isinstance(msg.data, bytes) and \
                not isinstance(msg.data, str):
            raise IOError()
        return msg.data


_async = {
    'asyncio': True,
    'create_route': create_route,
    'translate_request': translate_request,
    'make_response': make_response,
    'websocket': WebSocket,
}
