"""Utilities to distribute artifact events to internal consumers."""

import logging
from typing import Sequence

from server.services.artifact_events import ArtifactEvent
from server.services.session_store import WorkflowSessionStore
from workflow.hooks.workspace_artifact import WorkspaceArtifact


class ArtifactDispatcher:
    """Persists artifact events and optionally mirrors them to WebSocket clients."""

    def __init__(
        self,
        session_id: str,
        session_store: WorkflowSessionStore,
        websocket_manager=None,
    ) -> None:
        self.session_id = session_id
        self.session_store = session_store
        self.websocket_manager = websocket_manager
        self.logger = logging.getLogger(__name__)

    def emit_workspace_artifacts(self, artifacts: Sequence[WorkspaceArtifact]) -> None:
        if not artifacts:
            return
        events = [self._workspace_to_event(artifact) for artifact in artifacts]
        self.emit(events)

    def emit(self, events: Sequence[ArtifactEvent]) -> None:
        if not events:
            return
        queue = self.session_store.get_artifact_queue(self.session_id)
        if not queue:
            self.logger.debug("Artifact queue missing for session %s", self.session_id)
            return
        queue.append_many(events)
        if self.websocket_manager:
            payload = {
                "type": "artifact_created",
                "data": {
                    "session_id": self.session_id,
                    "events": [event.to_dict() for event in events],
                },
            }
            try:
                self.websocket_manager.send_message_sync(self.session_id, payload)
            except Exception as exc:
                self.logger.warning("Failed to broadcast artifact events: %s", exc)

    def _workspace_to_event(self, artifact: WorkspaceArtifact) -> ArtifactEvent:
        return ArtifactEvent(
            node_id=artifact.node_id,
            attachment_id=artifact.attachment_id,
            file_name=artifact.file_name,
            relative_path=artifact.relative_path,
            workspace_path=artifact.absolute_path,
            mime_type=artifact.mime_type,
            size=artifact.size,
            sha256=artifact.sha256,
            data_uri=artifact.data_uri,
            created_at=artifact.created_at,
            change_type=artifact.change_type,
            extra=artifact.extra,
        )
