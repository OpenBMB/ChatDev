"""Loop counter guard node executor."""

from typing import List, Dict, Any

from entity.configs import Node
from entity.configs.node.loop_counter import LoopCounterConfig
from entity.messages import Message, MessageRole
from runtime.node.executor.base import NodeExecutor


class LoopCounterNodeExecutor(NodeExecutor):
    """Track loop iterations and emit output only after hitting the limit."""

    STATE_KEY = "loop_counter"

    def execute(self, node: Node, inputs: List[Message]) -> List[Message]:
        config = node.as_config(LoopCounterConfig)
        if config is None:
            raise ValueError(f"Node {node.id} missing loop_counter configuration")

        state = self._get_state()
        counter = state.setdefault(node.id, {"count": 0})
        counter["count"] += 1
        count = counter["count"]

        if count < config.max_iterations:
            self.log_manager.debug(
                f"LoopCounter {node.id}: iteration {count}/{config.max_iterations} (suppress downstream)"
            )
            return []

        if config.reset_on_emit:
            counter["count"] = 0

        content = config.message or f"Loop limit reached ({config.max_iterations})"
        metadata = {
            "loop_counter": {
                "count": count,
                "max": config.max_iterations,
                "reset_on_emit": config.reset_on_emit,
            }
        }

        self.log_manager.debug(
            f"LoopCounter {node.id}: iteration {count}/{config.max_iterations} reached limit, releasing output"
        )

        return [Message(
            role=MessageRole.ASSISTANT,
            content=content,
            metadata=metadata,
        )]

    def _get_state(self) -> Dict[str, Dict[str, Any]]:
        return self.context.global_state.setdefault(self.STATE_KEY, {})
