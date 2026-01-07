"""Builder that assembles the runtime context for workflow execution."""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from runtime.node.agent import ToolManager
from utils.attachments import AttachmentStore
from utils.function_manager import EDGE_FUNCTION_DIR, EDGE_PROCESSOR_FUNCTION_DIR, get_function_manager
from utils.log_manager import LogManager
from utils.logger import WorkflowLogger
from utils.token_tracker import TokenTracker
from workflow.graph_context import GraphContext

from .runtime_context import RuntimeContext


@dataclass
class RuntimeBuilder:
    """Constructs RuntimeContext instances for GraphExecutor."""

    graph: GraphContext

    def build(self, logger: Optional[WorkflowLogger] = None, *, session_id: Optional[str] = None) -> RuntimeContext:
        tool_manager = ToolManager()
        function_manager = get_function_manager(EDGE_FUNCTION_DIR)
        processor_function_manager = get_function_manager(EDGE_PROCESSOR_FUNCTION_DIR)
        logger = logger or WorkflowLogger(self.graph.name, self.graph.log_level)
        log_manager = LogManager(logger)
        token_tracker = TokenTracker(workflow_id=self.graph.name)

        code_workspace = (self.graph.directory / "code_workspace").resolve()
        code_workspace.mkdir(parents=True, exist_ok=True)
        attachments_dir = code_workspace / "attachments"
        attachments_dir.mkdir(parents=True, exist_ok=True)
        attachment_store = AttachmentStore(attachments_dir)

        global_state: Dict[str, Any] = {
            "graph_directory": self.graph.directory,
            "vars": self.graph.config.vars,
            "python_workspace_root": code_workspace,
            "attachment_store": attachment_store,
        }

        context = RuntimeContext(
            tool_manager=tool_manager,
            function_manager=function_manager,
            edge_processor_function_manager=processor_function_manager,
            logger=logger,
            log_manager=log_manager,
            token_tracker=token_tracker,
            attachment_store=attachment_store,
            code_workspace=code_workspace,
            global_state=global_state,
        )
        context.session_id = session_id
        if session_id:
            context.global_state.setdefault("session_id", session_id)
        return context
