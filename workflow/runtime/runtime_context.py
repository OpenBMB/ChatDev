"""Shared runtime context for workflow execution."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from runtime.node.agent import ToolManager
from utils.function_manager import FunctionManager
from utils.logger import WorkflowLogger
from utils.log_manager import LogManager
from utils.token_tracker import TokenTracker
from utils.attachments import AttachmentStore


@dataclass
class RuntimeContext:
    """Container for runtime-wide dependencies required by GraphExecutor."""

    tool_manager: ToolManager
    function_manager: FunctionManager
    edge_processor_function_manager: FunctionManager
    logger: WorkflowLogger
    log_manager: LogManager
    token_tracker: TokenTracker
    attachment_store: AttachmentStore
    code_workspace: Path
    global_state: Dict[str, Any] = field(default_factory=dict)
    cycle_manager: Optional[Any] = None  # Late-bound by GraphManager
    session_id: Optional[str] = None
    workspace_hook: Optional[Any] = None
