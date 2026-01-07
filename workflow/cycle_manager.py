"""Cycle detection and management for workflow graphs."""

from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field
from entity.configs import Node


@dataclass
class CycleInfo:
    """Information about a detected cycle in the workflow graph."""
    cycle_id: str
    nodes: Set[str]  # Node IDs in the cycle
    entry_nodes: Set[str]  # Nodes that can enter the cycle (kept for compatibility)
    exit_edges: List[Dict[str, Any]]  # Edges that can exit the cycle
    iteration_count: int = 0
    max_iterations: Optional[int] = None  # Safety limit
    is_active: bool = False
    execution_state: Dict[str, Any] = field(default_factory=dict)

    # New fields for refactored cycle execution
    initial_node: Optional[str] = None  # The unique initial node when first entering the cycle
    configured_entry_node: Optional[str] = None  # User-configured entry node (if any)
    max_iterations_default: int = 100  # Default maximum iterations if max_iterations is None
    
    def add_node(self, node_id: str) -> None:
        """Add a node to the cycle."""
        self.nodes.add(node_id)
    
    def add_entry_node(self, node_id: str) -> None:
        """Add an entry node to the cycle."""
        self.entry_nodes.add(node_id)
    
    def add_exit_edge(self, edge_config: Dict[str, Any]) -> None:
        """Add an exit edge configuration."""
        self.exit_edges.append(edge_config)
    
    def increment_iteration(self) -> None:
        """Increment the iteration counter."""
        self.iteration_count += 1
    
    def is_within_iteration_limit(self) -> bool:
        """Check if the cycle should continue executing."""
        max_iter = self.max_iterations if self.max_iterations is not None else self.max_iterations_default
        return self.iteration_count < max_iter

    def get_max_iterations(self) -> int:
        """Get the effective maximum iterations."""
        return self.max_iterations if self.max_iterations is not None else self.max_iterations_default

    def reset_iteration_count(self) -> None:
        """Reset the iteration counter."""
        self.iteration_count = 0
    
    def is_node_in_cycle(self, node_id: str) -> bool:
        """Check if a node is part of this cycle."""
        return node_id in self.nodes
    
    def is_entry_node(self, node_id: str) -> bool:
        """Check if a node is an entry node for this cycle."""
        return node_id in self.entry_nodes


class CycleDetector:
    """Detects cycles in workflow graphs using Tarjan's algorithm."""
    
    def __init__(self):
        self.index_counter = 0
        self.index: Dict[str, int] = {}
        self.low_link: Dict[str, int] = {}
        self.stack: List[str] = []
        self.on_stack: Set[str] = set()
        self.cycles: List[Set[str]] = []
    
    def detect_cycles(self, nodes: Dict[str, Node]) -> List[Set[str]]:
        """Detect all cycles in the graph using Tarjan's strongly connected components' algorithm."""
        self.cycles.clear()
        self.index_counter = 0
        self.index.clear()
        self.low_link.clear()
        self.stack.clear()
        self.on_stack.clear()
        
        for node_id in nodes:
            if node_id not in self.index:
                self._strong_connect(node_id, nodes)
        
        # return [cycle for cycle in self.cycles if len(cycle) > 1 or self._has_self_loop(next(iter(cycle)), nodes)]
        return self.cycles

    def _has_self_loop(self, node_id: str, nodes: Dict[str, Node]) -> bool:
        """Check if a node has a self-loop."""
        node = nodes.get(node_id)
        if not node:
            return False
        return any(edge_link.target.id == node_id for edge_link in node.iter_outgoing_edges())

    def _strong_connect(self, node_id: str, nodes: Dict[str, Node]) -> None:
        """Recursive part of Tarjan's algorithm."""
        self.index[node_id] = self.index_counter
        self.low_link[node_id] = self.index_counter
        self.index_counter += 1
        self.stack.append(node_id)
        self.on_stack.add(node_id)
        
        node = nodes.get(node_id)
        if not node:
            return
        
        # Consider successors of node
        for edge_link in node.iter_outgoing_edges():
            successor_id = edge_link.target.id
            
            if successor_id not in self.index:
                self._strong_connect(successor_id, nodes)
                self.low_link[node_id] = min(self.low_link[node_id], self.low_link[successor_id])
            elif successor_id in self.on_stack:
                self.low_link[node_id] = min(self.low_link[node_id], self.index[successor_id])
        
        # If node is a root node, pop the stack and generate an SCC
        if self.low_link[node_id] == self.index[node_id]:
            cycle = set()
            while True:
                w = self.stack.pop()
                self.on_stack.remove(w)
                cycle.add(w)
                if w == node_id:
                    break
            
            if len(cycle) > 1 or self._has_self_loop(node_id, nodes):
                self.cycles.append(cycle)


class CycleManager:
    """Manages execution of cycles in the workflow graph."""
    
    def __init__(self):
        self.cycles: Dict[str, CycleInfo] = {}
        self.node_to_cycle: Dict[str, str] = {}  # Maps node ID to cycle ID
        self.active_cycles: Set[str] = set()
    
    def initialize_cycles(self, cycles: List[Set[str]], nodes: Dict[str, Node]) -> None:
        """Initialize cycle information from detected cycles."""
        self.cycles.clear()
        self.node_to_cycle.clear()
        
        for i, cycle_nodes in enumerate(cycles):
            cycle_id = f"cycle_{i}_{cycle_nodes}"
            cycle_info = CycleInfo(
                cycle_id=cycle_id,
                nodes=set(cycle_nodes),
                entry_nodes=set(),
                exit_edges=[]
            )
            
            # Find entry nodes and exit edges
            self._analyze_cycle_structure(cycle_info, nodes)
            
            self.cycles[cycle_id] = cycle_info
            
            # Map nodes to their cycle
            for node_id in cycle_nodes:
                self.node_to_cycle[node_id] = cycle_id

    def _analyze_cycle_structure(self, cycle: CycleInfo, nodes: Dict[str, Node]) -> None:
        """Analyze cycle structure to find entry nodes and exit edges."""
        cycle_nodes = cycle.nodes
        
        # Find entry nodes (nodes with predecessors outside the cycle)
        def judge_entry_predecessor(_predecessor: Node, _predecessor_id: str) -> bool:
            if _predecessor_id in cycle_nodes:
                return False
            for _edge_link in _predecessor.iter_outgoing_edges():
                if _edge_link.target.id == node_id:
                    if _edge_link.trigger:
                        return True
                    else:
                        return False
            return False

        for node_id in cycle_nodes:
            node = nodes.get(node_id)
            if not node:
                continue
                
            for predecessor in node.predecessors:
                if judge_entry_predecessor(predecessor, predecessor.id):
                    cycle.add_entry_node(node_id)
                    break
        
        # Find exit edges (edges from cycle nodes to nodes outside the cycle)
        for node_id in cycle_nodes:
            node = nodes.get(node_id)
            if not node:
                continue
                
            for edge_link in node.iter_outgoing_edges():
                if edge_link.target.id not in cycle_nodes and edge_link.trigger:
                    exit_edge = {
                        "from": node_id,
                        "to": edge_link.target.id,
                        "condition": edge_link.condition,
                        "trigger": edge_link.trigger,
                        "config": edge_link.config
                    }
                    cycle.add_exit_edge(exit_edge)
    
    def activate_cycle(self, cycle_id: str) -> None:
        """Activate a cycle for execution."""
        if cycle_id in self.cycles:
            self.cycles[cycle_id].is_active = True
            self.active_cycles.add(cycle_id)
    
    def deactivate_cycle(self, cycle_id: str) -> None:
        """Deactivate a cycle."""
        if cycle_id in self.cycles:
            self.cycles[cycle_id].is_active = False
            self.cycles[cycle_id].iteration_count = 0
            self.active_cycles.discard(cycle_id)
