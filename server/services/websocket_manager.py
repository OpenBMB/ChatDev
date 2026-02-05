"""WebSocket connection manager used by FastAPI app."""

import asyncio
import json
import logging
import time
import traceback
import uuid
from typing import Any, Dict, Optional

from fastapi import WebSocket

from server.services.message_handler import MessageHandler
from server.services.attachment_service import AttachmentService
from server.services.session_execution import SessionExecutionController
from server.services.session_store import WorkflowSessionStore, SessionStatus
from server.services.workflow_run_service import WorkflowRunService


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
        self.send_locks: Dict[str, asyncio.Lock] = {}
        self.loop: asyncio.AbstractEventLoop | None = None
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
        await websocket.accept()
        if self.loop is None:
            try:
                self.loop = asyncio.get_running_loop()
            except RuntimeError:
                self.loop = None
        if not session_id:
            session_id = str(uuid.uuid4())
        self.active_connections[session_id] = websocket
        self.connection_timestamps[session_id] = time.time()
        self.send_locks[session_id] = asyncio.Lock()
        logging.info("WebSocket connected: %s", session_id)
        await self.send_message(
            session_id,
            {
                "type": "connection",
                "data": {"session_id": session_id, "status": "connected"},
            },
        )
        return session_id

    def disconnect(self, session_id: str) -> None:
        session = self.session_store.get_session(session_id)
        if session and session.status in {SessionStatus.RUNNING, SessionStatus.WAITING_FOR_INPUT}:
            self.workflow_run_service.request_cancel(
                session_id,
                reason="WebSocket disconnected",
            )
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        if session_id in self.connection_timestamps:
            del self.connection_timestamps[session_id]
        if session_id in self.send_locks:
            del self.send_locks[session_id]
        self.session_controller.cleanup_session(session_id)
        remaining_session = self.session_store.get_session(session_id)
        if remaining_session and remaining_session.executor is None:
            self.session_store.pop_session(session_id)
        self.attachment_service.cleanup_session(session_id)
        logging.info("WebSocket disconnected: %s", session_id)

    async def send_message(self, session_id: str, message: Dict[str, Any]) -> None:
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            try:
                lock = self.send_locks.get(session_id)
                if lock is None:
                    await websocket.send_text(_encode_ws_message(message))
                else:
                    async with lock:
                        await websocket.send_text(_encode_ws_message(message))
            except Exception as exc:
                traceback.print_exc()
                logging.error("Failed to send message to %s: %s", session_id, exc)
                # self.disconnect(session_id)

    def send_message_sync(self, session_id: str, message: Dict[str, Any]) -> None:
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                asyncio.create_task(self.send_message(session_id, message))
            else:
                asyncio.run(self.send_message(session_id, message))
        except RuntimeError:
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.send_message(session_id, message),
                    self.loop,
                )
            else:
                asyncio.run(self.send_message(session_id, message))

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
