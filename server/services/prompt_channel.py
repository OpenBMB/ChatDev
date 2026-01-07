"""PromptChannel implementation backed by WebSocket sessions."""

import asyncio
from typing import Any, Dict, List, Optional

from entity.messages import MessageBlock
from server.services.attachment_service import AttachmentService
from server.services.session_execution import SessionExecutionController
from utils.attachments import AttachmentStore
from utils.exceptions import TimeoutError
from utils.human_prompt import PromptChannel, PromptResult
from utils.structured_logger import get_server_logger


class WebPromptChannel(PromptChannel):
    """Prompt channel that mediates through the WebSocket session controller."""

    def __init__(
        self,
        *,
        session_id: str,
        session_controller: SessionExecutionController,
        websocket_manager: Any,
        attachment_service: AttachmentService,
        attachment_store: AttachmentStore,
    ) -> None:
        self.session_id = session_id
        self.session_controller = session_controller
        self.websocket_manager = websocket_manager
        self.attachment_service = attachment_service
        self.attachment_store = attachment_store
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

    def request(
        self,
        *,
        node_id: str,
        task: str,
        inputs: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PromptResult:
        preview = inputs or ""
        payload = {
            "input": preview,
            "task_description": task,
            **(metadata or {}),
        }

        self.session_controller.set_waiting_for_input(
            self.session_id,
            node_id,
            payload,
        )

        self._notify_human_prompt(node_id, preview, task)

        try:
            human_response = self.session_controller.wait_for_human_input(self.session_id)
        except TimeoutError:
            raise
        except Exception as exc:  # pragma: no cover - propagated upstream
            logger = get_server_logger()
            logger.log_exception(exc, "Error waiting for human input", node_id=node_id, session_id=self.session_id)
            raise

        response_text, attachment_ids = self._extract_response(human_response)
        blocks = self._build_blocks(response_text, attachment_ids)
        metadata_out = {
            "attachment_count": len(attachment_ids),
            "input_size": len(preview),
        }
        return PromptResult(text=response_text, blocks=blocks, metadata=metadata_out)

    def _extract_response(self, payload: Any) -> tuple[str, List[str]]:
        if isinstance(payload, dict):
            response_text = payload.get("text") or ""
            attachments = payload.get("attachments") or []
            return response_text, attachments
        if payload is None:
            return "", []
        return str(payload), []

    def _build_blocks(self, text: str, attachment_ids: List[str]) -> List[MessageBlock]:
        blocks: List[MessageBlock] = []
        if text:
            blocks.append(MessageBlock.text_block(text))
        if attachment_ids:
            blocks.extend(
                self.attachment_service.build_attachment_blocks(
                    self.session_id,
                    attachment_ids,
                    target_store=self.attachment_store,
                )
            )
        if not blocks:
            blocks.append(MessageBlock.text_block(""))
        return blocks

    def _notify_human_prompt(self, node_id: str, preview: str, task: str) -> None:
        message = {
            "type": "human_input_required",
            "data": {
                "node_id": node_id,
                "input": preview,
                "task_description": task,
            },
        }
        if self._loop and self._loop.is_running():
            future = asyncio.run_coroutine_threadsafe(
                self.websocket_manager.send_message(self.session_id, message),
                self._loop,
            )
            try:
                future.result()
            except Exception:
                # fallback to sync send to surface errors/logging
                self.websocket_manager.send_message_sync(self.session_id, message)
        else:
            self.websocket_manager.send_message_sync(self.session_id, message)
