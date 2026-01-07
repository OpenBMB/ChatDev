"""Factory helpers for node executors.

Create and manage executors for different node types.
"""

from typing import Dict

from runtime.node.executor.base import NodeExecutor, ExecutionContext
from runtime.node.registry import iter_node_registrations


class NodeExecutorFactory:
    """Factory class that instantiates executors for every node type."""
    
    @staticmethod
    def create_executors(context: ExecutionContext, subgraphs: dict = None) -> Dict[str, NodeExecutor]:
        """Create executors for every registered node type.
        
        Args:
            context: Shared execution context
            subgraphs: Mapping of subgraph nodes (used by Subgraph executors)
            
        Returns:
            Mapping from node type to executor instance
        """
        subgraphs = subgraphs or {}
        
        executors: Dict[str, NodeExecutor] = {}
        for name, registration in iter_node_registrations().items():
            executors[name] = registration.build_executor(context, subgraphs=subgraphs)
        return executors
    
    @staticmethod
    def create_executor(
        node_type: str,
        context: ExecutionContext,
        subgraphs: dict = None
    ) -> NodeExecutor:
        """Create an executor for the requested node type.
        
        Args:
            node_type: Registered node type name
            context: Shared execution context
            subgraphs: Mapping of subgraph nodes (used by Subgraph executors)
            
        Returns:
            Executor instance for the requested type
            
        Raises:
            ValueError: If the node type is not supported
        """
        subgraphs = subgraphs or {}
        
        registrations = iter_node_registrations()
        if node_type not in registrations:
            raise ValueError(f"Unsupported node type: {node_type}")
        return registrations[node_type].build_executor(context, subgraphs=subgraphs)
