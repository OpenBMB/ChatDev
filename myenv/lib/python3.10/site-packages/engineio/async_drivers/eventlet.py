from __future__ import absolute_import

from eventlet.green.threading import Thread, Event
from eventlet import queue
from eventlet import sleep
from eventlet.websocket import WebSocketWSGI as _WebSocketWSGI


class WebSocketWSGI(_WebSocketWSGI):
    def __init__(self, handler, server):
        try:
            super().__init__(
                handler, max_frame_length=int(server.max_http_buffer_size))
        except TypeError:  # pragma: no cover
            # older versions of eventlet do not support a max frame size
            super().__init__(handler)
        self._sock = None

    def __call__(self, environ, start_response):
        if 'eventlet.input' not in environ:
            raise RuntimeError('You need to use the eventlet server. '
                               'See the Deployment section of the '
                               'documentation for more information.')
        self._sock = environ['eventlet.input'].get_socket()
        return super().__call__(environ, start_response)


_async = {
    'thread': Thread,
    'queue': queue.Queue,
    'queue_empty': queue.Empty,
    'event': Event,
    'websocket': WebSocketWSGI,
    'sleep': sleep,
}
