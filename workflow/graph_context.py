"""Runtime context for workflow graphs.

This module stores execution-time state and business logic for graphs.
"""

from datetime import datetime
from typing import Any, Dict, List

import yaml

from entity.configs import Node
from entity.graph_config import GraphConfig


class GraphContext:
    """Runtime context for a workflow graph (state + business logic).
    
    Differences from ``GraphConfig``:
    - ``GraphConfig`` is immutable configuration data.
    - ``GraphContext`` is mutable runtime state with dynamic execution data.
    
    Attributes:
        config: Graph configuration
        nodes: Mapping of ``node_id`` to ``Node``
        edges: List of edges
        layers: Topological layer layout
        outputs: Node outputs captured during execution
        topology: Topological ordering list
        subgraphs: Mapping of ``node_id`` to nested ``GraphContext``
        has_cycles: Whether the graph contains cycles
        cycle_execution_order: Execution order for cycles
        directory: Output directory for artifacts
        depth: Graph depth
    """
    
    def __init__(self, config: GraphConfig) -> None:
        """Initialize the graph context.
        
        Args:
            config: Graph configuration
        """
        self.config = config
        self.vars: Dict[str, Any] = dict(config.vars)
        
        # Graph structure
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Dict[str, Any]] = []
        self.layers: List[List[str]] = []
        self.topology: List[str] = []
        self.depth: int = 0
        self.start_nodes: List[str] = []
        self.explicit_start_nodes: List[str] = []
        
        # Runtime state
        self.outputs: Dict[str, str] = {}
        self.subgraphs: Dict[str, "GraphContext"] = {}
        
        # Cycle support
        self.has_cycles: bool = False
        self.cycle_execution_order: List[Dict[str, Any]] = []
        
        # Output directory
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        fixed_output_dir = bool(config.metadata.get("fixed_output_dir"))
        if fixed_output_dir or "session_" in config.name:
            self.directory = config.output_root / config.name
        else:
            self.directory = config.output_root / f"{config.name}_{timestamp}"
        self.directory.mkdir(parents=True, exist_ok=True)
        # Voting mode flag
        self.is_majority_voting: bool = config.is_majority_voting
    
    @property
    def name(self) -> str:
        """Return the project name."""
        return self.config.name
    
    @property
    def log_level(self):
        """Return the configured log level."""
        return self.config.log_level
    
    @property
    def metadata(self) -> Dict[str, Any]:
        """Return graph metadata."""
        return self.config.metadata
    
    @metadata.setter
    def metadata(self, value: Dict[str, Any]) -> None:
        """Set graph metadata."""
        self.config.metadata = value
    
    def record(self, outputs: Dict[str, Any]) -> None:
        """Persist execution results to disk.
        
        Args:
            outputs: Mapping of node outputs
        """
        self.outputs = outputs
        # self.directory.mkdir(parents=True, exist_ok=True)
        
        # Persist node outputs
        outputs_path = self.directory / "node_outputs.yaml"
        if self.outputs:
            with outputs_path.open("w", encoding="utf-8") as handle:
                yaml.dump(self.outputs, handle, allow_unicode=True, sort_keys=False)
        
        # Persist workflow summary
        summary = {
            "project": self.config.name,
            "organization": self.config.get_organization(),
            "design_path": self.config.get_source_path(),
            "metadata": self.config.metadata,
        }
        summary_path = self.directory / "workflow_summary.yaml"
        with summary_path.open("w", encoding="utf-8") as handle:
            yaml.dump(summary, handle, allow_unicode=True, sort_keys=False)
    
    def final_message(self) -> str:
        """Build the final completion string.
        
        Returns:
            Completion message text
        """
        if not self.outputs:
            return "Workflow finished with no outputs."
        
        sink_nodes = [node_id for node_id, node in self.nodes.items() if not node.successors]
        return (
            f"Workflow finished with {len(self.outputs)} node outputs"
            f" ({len(sink_nodes)} terminal nodes)."
        )
    
    def get_sink_nodes(self) -> List[Node]:
        """Return all leaf nodes (nodes without successors)."""
        return [node for node in self.nodes.values() if not node.successors]
    
    def get_source_nodes(self) -> List[Node]:
        """Return all source nodes (nodes without predecessors)."""
        return [node for node in self.nodes.values() if not node.predecessors]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the graph context to a dictionary."""
        return {
            "config": self.config.to_dict(),
            "nodes": {node_id: node.to_dict() for node_id, node in self.nodes.items()},
            "edges": list(self.edges),
            "layers": list(self.layers),
            "topology": list(self.topology),
            "depth": self.depth,
            "has_cycles": self.has_cycles,
            "start_nodes": list(self.start_nodes),
            "explicit_start_nodes": list(self.explicit_start_nodes),
            "outputs": dict(self.outputs),
        }
