"""Executor for Human nodes.

Runs the human-in-the-loop interaction nodes.
"""

from typing import List

from entity.configs import Node
from entity.configs.node.human import HumanConfig
from entity.messages import Message, MessageRole
from runtime.node.executor.base import NodeExecutor


class HumanNodeExecutor(NodeExecutor):
    """Executor used for human interaction nodes."""
    
    def execute(self, node: Node, inputs: List[Message]) -> List[Message]:
        """Execute a human node.
        
        Args:
            node: Human node definition
            inputs: Input messages
            
        Returns:
            Result supplied by the human reviewer
        """
        self._ensure_not_cancelled()
        if node.node_type != "human":
            raise ValueError(f"Node {node.id} is not a human node")
        
        human_config = node.as_config(HumanConfig)
        if not human_config:
            raise ValueError(f"Node {node.id} has no human configuration")
        
        human_task_description = human_config.description
        # Use prompt-style preview so humans see the same flattened text format
        # instead of raw message JSON.
        input_data = self._inputs_to_text(inputs)

        prompt_service = self.context.get_human_prompt_service()
        if prompt_service is None:
            raise RuntimeError("HumanPromptService is not configured; cannot execute human node")

        prompt_result = prompt_service.request(
            node.id,
            human_task_description or "",
            inputs=input_data,
            metadata={"node_type": "human"},
        )

        return [self._build_message(
            MessageRole.USER,
            prompt_result.as_message_content(),
            source=node.id,
        )]

