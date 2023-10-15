from socketio import Namespace as _Namespace


class Namespace(_Namespace):
    def __init__(self, namespace=None):
        super(Namespace, self).__init__(namespace)
        self.socketio = None

    def _set_socketio(self, socketio):
        self.socketio = socketio

    def trigger_event(self, event, *args):
        """Dispatch an event to the proper handler method.

        In the most common usage, this method is not overloaded by subclasses,
        as it performs the routing of events to methods. However, this
        method can be overridden if special dispatching rules are needed, or if
        having a single method that catches all events is desired.
        """
        handler_name = 'on_' + event
        if not hasattr(self, handler_name):
            # there is no handler for this event, so we ignore it
            return
        handler = getattr(self, handler_name)
        return self.socketio._handle_event(handler, event, self.namespace,
                                           *args)

    def emit(self, event, data=None, room=None, include_self=True,
             namespace=None, callback=None):
        """Emit a custom event to one or more connected clients."""
        return self.socketio.emit(event, data, room=room,
                                  include_self=include_self,
                                  namespace=namespace or self.namespace,
                                  callback=callback)

    def send(self, data, room=None, include_self=True, namespace=None,
             callback=None):
        """Send a message to one or more connected clients."""
        return self.socketio.send(data, room=room, include_self=include_self,
                                  namespace=namespace or self.namespace,
                                  callback=callback)

    def close_room(self, room, namespace=None):
        """Close a room."""
        return self.socketio.close_room(room=room,
                                        namespace=namespace or self.namespace)
