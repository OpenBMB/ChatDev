"""GraphExecutor variant that reports results over WebSocket."""

import asyncio
from typing import List

from utils.logger import WorkflowLogger
from workflow.graph import GraphExecutor
from workflow.graph_context import GraphContext

from server.services.attachment_service import AttachmentService
from server.services.artifact_dispatcher import ArtifactDispatcher
from server.services.prompt_channel import WebPromptChannel
from server.services.session_store import WorkflowSessionStore
from server.services.session_execution import SessionExecutionController
from workflow.hooks.workspace_artifact import WorkspaceArtifact, WorkspaceArtifactHook


class WebSocketGraphExecutor(GraphExecutor):
    """GraphExecutor subclass that emits events via WebSocket."""

    def __init__(
        self,
        graph: GraphContext,
        session_id: str,
        session_controller: SessionExecutionController,
        attachment_service: AttachmentService,
        websocket_manager,
        session_store: WorkflowSessionStore,
        cancel_event=None,
    ):
        self.session_id = session_id
        self.session_controller = session_controller
        self.attachment_service = attachment_service
        self.websocket_manager = websocket_manager
        self.session_store = session_store
        self.results = {}
        self.artifact_dispatcher = ArtifactDispatcher(session_id, session_store, websocket_manager)

        def hook_factory(runtime_context):
            prompt_channel = WebPromptChannel(
                session_id=session_id,
                session_controller=session_controller,
                websocket_manager=websocket_manager,
                attachment_service=attachment_service,
                attachment_store=runtime_context.attachment_store,
            )
            return WorkspaceArtifactHook(
                attachment_store=runtime_context.attachment_store,
                emit_callback=self._handle_workspace_artifacts,
                prompt_channel=prompt_channel,
            )

        super().__init__(
            graph,
            session_id=session_id,
            workspace_hook_factory=hook_factory,
            cancel_event=cancel_event,
        )

    def _create_logger(self) -> WorkflowLogger:
        from server.services.websocket_logger import WebSocketLogger

        return WebSocketLogger(self.websocket_manager, self.session_id, self.graph.name, self.graph.log_level)

    async def execute_graph_async(self, task_prompt):
        await asyncio.get_event_loop().run_in_executor(None, self._execute, task_prompt)

    def get_results(self):
        return self.outputs

    def _handle_workspace_artifacts(self, artifacts: List[WorkspaceArtifact]) -> None:
        self.artifact_dispatcher.emit_workspace_artifacts(artifacts)
