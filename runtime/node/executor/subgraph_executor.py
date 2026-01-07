"""Executor for subgraph nodes.

Runs nested graph nodes inside the parent workflow.
"""

from typing import List
import copy

from entity.configs import Node
from entity.configs.node.subgraph import SubgraphConfig
from runtime.node.executor.base import NodeExecutor
from entity.messages import Message, MessageRole


class SubgraphNodeExecutor(NodeExecutor):
    """Subgraph node executor.
    
    Note: this executor needs access to ``GraphContext.subgraphs``.
    """
    
    def __init__(self, context, subgraphs: dict):
        """Initialize the executor.
        
        Args:
            context: Execution context
            subgraphs: Mapping from node_id to ``GraphContext``
        """
        super().__init__(context)
        self.subgraphs = subgraphs
    
    def execute(self, node: Node, inputs: List[Message]) -> List[Message]:
        """Execute a subgraph node.
        
        Args:
            node: Subgraph node definition
            inputs: Input messages list
            
        Returns:
            Result produced by the subgraph
        """
        if node.node_type != "subgraph":
            raise ValueError(f"Node {node.id} is not a subgraph node")
        
        subgraph_config = node.as_config(SubgraphConfig)
        if not subgraph_config:
            raise ValueError(f"Node {node.id} has no subgraph configuration")
        
        task_payload: List[Message] = self._clone_messages(inputs)
        if not task_payload:
            task_payload = [self._build_message(MessageRole.USER, "", source="SUBGRAPH")]

        input_data = self._inputs_to_text(task_payload)

        self.log_manager.debug(
            f"Subgraph processing for node {node.id}",
            node_id=node.id,
            details={
                "input_size": len(str(input_data)),
                "input_result": input_data
            }
        )
        
        # Retrieve the subgraph context
        if node.id not in self.subgraphs:
            raise ValueError(f"Subgraph for node {node.id} not found")
        
        subgraph = self.subgraphs[node.id]
        
        # Deep copy the subgraph to ensure isolation during parallel execution
        # process. Nodes in the subgraph (e.g. Start) hold state (inputs/outputs)
        # that must not be shared across threads.
        subgraph = copy.deepcopy(subgraph)
        
        # Execute the subgraph (requires importing ``GraphExecutor``)
        from workflow.graph import GraphExecutor
        
        executor = GraphExecutor.execute_graph(subgraph, task_prompt=task_payload)
        result_messages = executor.get_final_output_messages()
        
        final_results = []
        if not result_messages:
            # Fallback for no output
            fallback = self._build_message(
                MessageRole.ASSISTANT,
                "",
                source=node.id,
            )
            final_results.append(fallback)
        else:
            for msg in result_messages:
                result_message = msg.clone()
                meta = dict(result_message.metadata)
                meta.setdefault("source", node.id)
                result_message.metadata = meta
                final_results.append(result_message)
        
        self.log_manager.debug(
            f"Subgraph processing completed for node {node.id}",
            node_id=node.id,
            details=executor.log_manager.logs_to_dict()
        )
        
        return final_results
