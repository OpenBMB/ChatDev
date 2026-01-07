"""Passthrough node executor."""

from typing import List

from entity.configs import Node
from entity.configs.node.passthrough import PassthroughConfig
from entity.messages import Message, MessageRole
from runtime.node.executor.base import NodeExecutor


class PassthroughNodeExecutor(NodeExecutor):
    """Forward input messages without modifications."""

    def execute(self, node: Node, inputs: List[Message]) -> List[Message]:
        if node.node_type != "passthrough":
            raise ValueError(f"Node {node.id} is not a passthrough node")

        config = node.as_config(PassthroughConfig)
        if config is None:
            raise ValueError(f"Node {node.id} missing passthrough configuration")

        if not inputs:
            warning_msg = f"Passthrough node '{node.id}' triggered without inputs"
            self.log_manager.warning(warning_msg, node_id=node.id, details={"input_count": 0})
            return [Message(content="", role=MessageRole.USER)]

        if config.only_last_message:
            if len(inputs) > 1:
                self.log_manager.debug(
                    f"Passthrough node '{node.id}' received {len(inputs)} inputs; forwarding the latest entry",
                    node_id=node.id,
                    details={"input_count": len(inputs)},
                )
            return [inputs[-1].clone()]
        else:
            return [msg.clone() for msg in inputs]
