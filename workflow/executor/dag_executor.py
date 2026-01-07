"""Executor for DAG (Directed Acyclic Graph) workflows."""

from typing import Dict, List, Callable

from entity.configs import Node
from utils.log_manager import LogManager
from workflow.executor.parallel_executor import ParallelExecutor


class DAGExecutor:
    """Execute DAG workflows.
    
    Features:
    - Execute layer by layer following the topology
    - Support parallel execution inside a layer
    - Serialize Human nodes automatically
    """
    
    def __init__(
        self,
        log_manager: LogManager,
        nodes: Dict[str, Node],
        layers: List[List[str]],
        execute_node_func: Callable[[Node], None]
    ):
        """Initialize the executor.
        
        Args:
            log_manager: Logger instance
            nodes: Mapping of node ids to ``Node`` objects
            layers: Topological layers
            execute_node_func: Callable used to execute a single node
        """
        self.log_manager = log_manager
        self.nodes = nodes
        self.layers = layers
        self.execute_node_func = execute_node_func
        self.parallel_executor = ParallelExecutor(log_manager, nodes)
    
    def execute(self) -> None:
        """Execute the DAG workflow."""
        for layer_idx, layer_nodes in enumerate(self.layers):
            self.log_manager.debug(f"Executing Layer {layer_idx} with nodes: {layer_nodes}")
            self._execute_layer(layer_nodes)
    
    def _execute_layer(self, layer_nodes: List[str]) -> None:
        """Execute a single topological layer."""
        def execute_if_triggered(node_id: str) -> None:
            node = self.nodes[node_id]
            if node.is_triggered():
                self.execute_node_func(node)
            else:
                self.log_manager.debug(f"Node {node_id} skipped - not triggered")
        
        self.parallel_executor.execute_nodes_parallel(layer_nodes, execute_if_triggered)
