import logging
from typing import Any, Dict

from utils.exceptions import ValidationError

from server.services.session_execution import SessionExecutionController
from server.services.session_store import WorkflowSessionStore


class MessageHandler:
    """Routes WebSocket messages to the appropriate handlers."""

    def __init__(
        self,
        session_store: WorkflowSessionStore,
        session_controller: SessionExecutionController,
        workflow_run_service=None,
    ) -> None:
        self.session_store = session_store
        self.session_controller = session_controller
        self.workflow_run_service = workflow_run_service
        self.logger = logging.getLogger(__name__)

    async def handle_message(self, session_id: str, data: Dict[str, Any], websocket_manager):
        message_type = data.get("type")
        if message_type == "human_input":
            await self._handle_human_input(session_id, data, websocket_manager)
        elif message_type == "ping":
            await self._handle_ping(session_id, websocket_manager)
        elif message_type == "get_status":
            await self._handle_get_status(session_id, websocket_manager)
        else:
            await websocket_manager.send_message(
                session_id,
                {"type": "error", "data": {"message": f"Unknown message type: {message_type}"}},
            )

    async def _handle_human_input(self, session_id: str, data: Dict[str, Any], websocket_manager):
        try:
            payload = data.get("data", {}) or {}
            user_input = payload.get("input", "")
            attachments = payload.get("attachments") or []

            if not user_input and not attachments:
                await websocket_manager.send_message(
                    session_id,
                    {"type": "error", "data": {"message": "Empty input"}},
                )
                return

            self.session_controller.provide_human_input(
                session_id,
                {"text": user_input, "attachments": attachments},
            )

            await websocket_manager.send_message(
                session_id,
                {"type": "input_received", "data": {"message": "Input received"}},
            )

        except ValidationError as exc:
            await websocket_manager.send_message(
                session_id,
                {"type": "error", "data": {"message": str(exc)}},
            )
        except Exception as exc:
            self.logger.error("Error handling human input for session %s: %s", session_id, exc)
            await websocket_manager.send_message(
                session_id,
                {"type": "error", "data": {"message": str(exc)}},
            )

    async def _handle_ping(self, session_id: str, websocket_manager):
        await websocket_manager.handle_heartbeat(session_id)

    async def _handle_get_status(self, session_id: str, websocket_manager):
        session_info = self.session_store.get_session_info(session_id)
        await websocket_manager.send_message(
            session_id,
            {"type": "status", "data": session_info or {"message": "Session not found"}},
        )
