"""Abstract base classes for node executors.

Defines the interfaces that every node executor must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List

from entity.configs import Node
from entity.messages import Message, MessageContent, MessageRole, serialize_messages
from runtime.node.agent import MemoryManager
from runtime.node.agent import ThinkingManagerBase
from runtime.node.agent import ToolManager
from utils.function_manager import FunctionManager
from utils.human_prompt import HumanPromptService
from utils.log_manager import LogManager
from utils.token_tracker import TokenTracker
from utils.exceptions import WorkflowCancelledError


@dataclass
class ExecutionContext:
    """Node execution context that bundles every service and state the executor needs.
    
    Attributes:
        tool_manager: Tool manager shared by executors
        function_manager: Function manager registry
        log_manager: Structured log manager
        memory_managers: Mapping of node_id to ``MemoryManager`` instances
        thinking_managers: Mapping of node_id to ``ThinkingManagerBase`` instances
        token_tracker: Token tracker used for accounting
        global_state: Shared global state dictionary
    """
    tool_manager: ToolManager
    function_manager: FunctionManager
    log_manager: LogManager
    memory_managers: Dict[str, MemoryManager] = field(default_factory=dict)
    thinking_managers: Dict[str, ThinkingManagerBase] = field(default_factory=dict)
    token_tracker: Optional[TokenTracker] = None
    global_state: Dict[str, Any] = field(default_factory=dict)
    workspace_hook: Optional[Any] = None
    human_prompt_service: Optional[HumanPromptService] = None
    cancel_event: Optional[Any] = None
    
    def get_memory_manager(self, node_id: str) -> Optional[MemoryManager]:
        """Return the memory manager for a given node."""
        return self.memory_managers.get(node_id)
    
    def get_thinking_manager(self, node_id: str) -> Optional[ThinkingManagerBase]:
        """Return the thinking manager for a given node."""
        return self.thinking_managers.get(node_id)
    
    def get_token_tracker(self) -> Optional[TokenTracker]:
        """Return the configured token tracker."""
        return self.token_tracker

    def get_human_prompt_service(self) -> Optional[HumanPromptService]:
        """Return the interactive human prompt service."""
        return self.human_prompt_service


class NodeExecutor(ABC):
    """Abstract base class for node executors.
    
    Every concrete executor must inherit from this class and implement ``execute``.
    """
    
    def __init__(self, context: ExecutionContext):
        """Initialize the executor with the shared execution context.
        
        Args:
            context: Execution context
        """
        self.context = context
    
    @abstractmethod
    def execute(self, node: Node, inputs: List[Message]) -> List[Message]:
        """Execute the node logic.
        
        Args:
            node: Node definition to execute
            inputs: Input queue for the node
        
        Returns:
            List of payload messages produced by the node. Empty list when the
            node intentionally suppresses downstream propagation. Standard nodes
            return a single-element list.
            
        Raises:
            Exception: Raised when execution fails
        """
        pass
    
    @property
    def tool_manager(self) -> ToolManager:
        """Return the shared tool manager."""
        return self.context.tool_manager
    
    @property
    def function_manager(self) -> FunctionManager:
        """Return the shared function manager."""
        return self.context.function_manager
    
    @property
    def log_manager(self) -> LogManager:
        """Return the structured log manager."""
        return self.context.log_manager

    def _inputs_to_text(self, inputs: List[Message]) -> str:
        if not inputs:
            return ""
        parts: list[str] = []
        for message in inputs:
            source = message.metadata.get("source", "UNKNOWN")
            parts.append(
                f"=== INPUT FROM {source} ({message.role.value}) ===\n\n{message.text_content()}"
            )
        return "\n\n".join(parts)

    def _inputs_to_message_json(self, inputs: List[Message]) -> str | None:
        if not inputs:
            return None
        return serialize_messages(inputs)

    def _build_message(
        self,
        role: MessageRole,
        content: MessageContent,
        *,
        source: str | None = None,
        metadata: Dict[str, Any] | None = None,
        preserve_role: bool = False,
    ) -> Message:
        meta = dict(metadata or {})
        if source:
            meta.setdefault("source", source)
        return Message(role=role, content=content, metadata=meta, preserve_role=preserve_role)

    def _clone_messages(self, messages: List[Message]) -> List[Message]:
        return [message.clone() for message in messages]

    def _ensure_not_cancelled(self) -> None:
        event = getattr(self.context, "cancel_event", None)
        if event is not None and event.is_set():
            raise WorkflowCancelledError("Workflow execution cancelled")
