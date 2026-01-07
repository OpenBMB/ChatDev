"""Global state shared across server modules."""

from typing import Optional

from server.services.websocket_manager import WebSocketManager
from utils.exceptions import ValidationError

websocket_manager: Optional[WebSocketManager] = None


def init_state() -> None:
    """Ensure global singletons are ready for incoming requests."""

    get_websocket_manager()


def get_websocket_manager() -> WebSocketManager:
    global websocket_manager
    if websocket_manager is None:
        websocket_manager = WebSocketManager()
    return websocket_manager


def ensure_known_session(session_id: str, *, require_connection: bool = False) -> WebSocketManager:
    """Return the WebSocket manager if the session is connected or known."""

    manager = get_websocket_manager()
    if not session_id:
        raise ValidationError("Session not connected", details={"session_id": session_id})

    if session_id in manager.active_connections:
        return manager

    if not require_connection and manager.session_store.has_session(session_id):
        return manager

    raise ValidationError("Session not connected", details={"session_id": session_id})
