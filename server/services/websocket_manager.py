"""WebSocket connection manager used by FastAPI app."""

import asyncio
import json
import logging
import time
import traceback
import uuid
from typing import Any, Dict, Optional

from fastapi import WebSocket, WebSocketException

from server.services.message_handler import MessageHandler
from server.services.attachment_service import AttachmentService
from server.services.session_execution import SessionExecutionController
from server.services.session_store import WorkflowSessionStore, SessionStatus
from server.services.workflow_run_service import WorkflowRunService
from utils.exceptions import ValidationError
from utils.workspace_paths import validate_path_component


def _json_default(value):
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return to_dict()
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        try:
            return vars(value)
        except Exception:
            pass
    return str(value)


def _encode_ws_message(message: Any) -> str:
    if isinstance(message, str):
        return message
    return json.dumps(message, default=_json_default)


class WebSocketManager:
    SESSION_TTL_SECONDS = 24 * 60 * 60  # 24 hours

    def __init__(
        self,
        *,
        session_store: WorkflowSessionStore | None = None,
        session_controller: SessionExecutionController | None = None,
        attachment_service: AttachmentService | None = None,
        workflow_run_service: WorkflowRunService | None = None,
    ):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_timestamps: Dict[str, float] = {}
        self._owner_loop: Optional[asyncio.AbstractEventLoop] = None
        self._gc_task: Optional[asyncio.Task] = None
        self.session_store = session_store or WorkflowSessionStore()
        self.session_controller = session_controller or SessionExecutionController(self.session_store)
        self.attachment_service = attachment_service or AttachmentService()
        self.workflow_run_service = workflow_run_service or WorkflowRunService(
            self.session_store,
            self.session_controller,
            self.attachment_service,
        )
        self.message_handler = MessageHandler(
            self.session_store,
            self.session_controller,
            self.workflow_run_service,
        )

    async def connect(self, websocket: WebSocket, session_id: Optional[str] = None) -> str:
        if session_id:
            try:
                validate_path_component(session_id, field="session_id")
            except ValidationError as exc:
                raise WebSocketException(code=1008, reason=str(exc)) from exc
        await websocket.accept()
        # Capture the event loop that owns the WebSocket connections so that
        # worker threads can safely schedule sends via run_coroutine_threadsafe.
        if self._owner_loop is None:
            self._owner_loop = asyncio.get_running_loop()

        # --- Reconnect to existing session ---
        if session_id and self.session_store.has_session(session_id):
            # If an old WebSocket is still tied to this session, close it first
            if session_id in self.active_connections:
                old_ws = self.active_connections[session_id]
                try:
                    await old_ws.close(code=1000, reason="Replaced by new connection")
                except Exception:
                    pass

            self.active_connections[session_id] = websocket
            self.connection_timestamps[session_id] = time.time()
            logging.info("WebSocket reconnected to existing session: %s", session_id)

            # Always start the GC loop (idempotent)
            self._start_gc()

            # Send connection confirmation
            await self._send_raw(
                session_id,
                {"type": "connection", "data": {"session_id": session_id, "status": "connected"}},
            )

            # Replay all buffered messages (snapshot to avoid including messages
            # that arrive during replay)
            session = self.session_store.get_session(session_id)
            if session:
                messages_to_replay = list(session.message_buffer)
                for msg in messages_to_replay:
                    await self._send_raw(session_id, msg)

            # Send session state snapshot
            snapshot = self.session_store.get_session_snapshot(session_id)
            if snapshot:
                await self._send_raw(session_id, {"type": "session_resumed", "data": snapshot})

            return session_id

        # --- New connection ---
        if not session_id:
            session_id = str(uuid.uuid4())
        self.active_connections[session_id] = websocket
        self.connection_timestamps[session_id] = time.time()
        logging.info("WebSocket connected: %s", session_id)

        # Always start the GC loop (idempotent)
        self._start_gc()

        await self.send_message(
            session_id,
            {
                "type": "connection",
                "data": {"session_id": session_id, "status": "connected"},
            },
        )
        return session_id

    def disconnect(self, session_id: str) -> None:
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        if session_id in self.connection_timestamps:
            del self.connection_timestamps[session_id]
        logging.info("WebSocket disconnected (session preserved): %s", session_id)

    async def send_message(self, session_id: str, message: Dict[str, Any]) -> None:
        # Buffer business messages for reconnection replay (exclude transport messages)
        if message.get("type") not in ("connection", "pong"):
            session = self.session_store.get_session(session_id)
            if session:
                session.append_message(message)

        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            try:
                await websocket.send_text(_encode_ws_message(message))
            except Exception as exc:
                traceback.print_exc()
                logging.error("Failed to send message to %s: %s", session_id, exc)

    async def _send_raw(self, session_id: str, message: Dict[str, Any]) -> None:
        """Send a message without buffering. Used for replay and connection management."""
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            try:
                await websocket.send_text(_encode_ws_message(message))
            except Exception as exc:
                traceback.print_exc()
                logging.error("Failed to send raw message to %s: %s", session_id, exc)

    def send_message_sync(self, session_id: str, message: Dict[str, Any]) -> None:
        """Send a WebSocket message from any thread (including worker threads).

        WebSocket objects are bound to the event loop that created them (the main
        uvicorn loop).  Previous code called ``asyncio.run()`` from worker threads
        which spins up a *new* event loop, causing ``RuntimeError: … attached to a
        different loop`` or silent delivery failures.

        The fix: always schedule the coroutine on the loop that owns the sockets
        via ``asyncio.run_coroutine_threadsafe`` and wait for the result with a
        short timeout so the caller knows if delivery failed.
        """
        loop = self._owner_loop
        if loop is None or loop.is_closed():
            logging.warning(
                "Cannot send sync message to %s: owner event loop unavailable",
                session_id,
            )
            return

        future = asyncio.run_coroutine_threadsafe(
            self.send_message(session_id, message), loop
        )
        try:
            future.result(timeout=10)
        except TimeoutError:
            logging.warning(
                "Timed out sending sync WS message to %s", session_id
            )
        except Exception as exc:
            logging.error(
                "Error sending sync WS message to %s: %s", session_id, exc
            )

    async def broadcast(self, message: Dict[str, Any]) -> None:
        for session_id in list(self.active_connections.keys()):
            await self.send_message(session_id, message)

    async def handle_heartbeat(self, session_id: str) -> None:
        if session_id in self.active_connections:
            await self.send_message(
                session_id,
                {"type": "pong", "data": {"timestamp": time.time()}},
            )
        else:
            logging.warning("Heartbeat request from disconnected session: %s", session_id)

    async def handle_message(self, session_id: str, message: str) -> None:
        try:
            data = json.loads(message)
            await self.message_handler.handle_message(session_id, data, self)
        except json.JSONDecodeError:
            await self.send_message(
                session_id,
                {"type": "error", "data": {"message": "Invalid JSON format"}},
            )
        except Exception as exc:
            logging.error("Error handling message from %s: %s", session_id, exc)
            await self.send_message(
                session_id,
                {"type": "error", "data": {"message": str(exc)}},
            )

    def _start_gc(self) -> None:
        """Start the background GC task if not already running."""
        if self._gc_task is not None and not self._gc_task.done():
            return
        loop = asyncio.get_running_loop()
        self._gc_task = loop.create_task(self._gc_loop())

    async def _gc_loop(self) -> None:
        """Periodically clean up terminal sessions older than TTL."""
        TERMINAL = {SessionStatus.COMPLETED, SessionStatus.ERROR, SessionStatus.CANCELLED}
        while True:
            await asyncio.sleep(3600)  # run every hour
            now = time.time()
            to_remove = []
            for sid, session in self.session_store._sessions.items():
                if session.status in TERMINAL:
                    if now - session.updated_at > self.SESSION_TTL_SECONDS:
                        to_remove.append(sid)
            for sid in to_remove:
                self.session_store.pop_session(sid)
                self.attachment_service.cleanup_session(sid)
                logging.info("GC: removed expired session %s", sid)
