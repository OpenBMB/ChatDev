"""Cycle executor that runs workflow graphs containing loops."""

import copy
import threading
from typing import Dict, List, Callable, Any, Set, Optional

from entity.configs import Node, EdgeLink
from utils.log_manager import LogManager
from workflow.cycle_manager import CycleManager
from workflow.executor.parallel_executor import ParallelExecutor
from workflow.topology_builder import GraphTopologyBuilder


class CycleExecutor:
    """Execute workflow graphs that contain cycles.
    
    Features:
    - Scheduling is based on "super nodes"
    - Parallel execution inside cycles
    - Automatic detection of exit conditions
    """
    
    def __init__(
        self,
        log_manager: LogManager,
        nodes: Dict[str, Node],
        cycle_execution_order: List[Dict[str, Any]],
        cycle_manager: CycleManager,
        execute_node_func: Callable[[Node], None],
    ):
        """Initialize the cycle executor.
        
        Args:
            log_manager: Logger instance
            nodes: Mapping of node ids to nodes
            cycle_execution_order: Super-node execution order with cycles
            cycle_manager: Cycle manager coordinating iterations
            execute_node_func: Callable that executes a single node
        """
        self.log_manager = log_manager
        self.nodes = nodes
        self.cycle_execution_order = cycle_execution_order
        self.cycle_manager = cycle_manager
        self.execute_node_func = execute_node_func
        self.parallel_executor = ParallelExecutor(log_manager, nodes)
    
    def execute(self) -> None:
        """Run the workflow that contains cycles."""
        self.log_manager.debug("Executing graph with cycles using super-node scheduler")
        
        for layer_idx, layer_items in enumerate(self.cycle_execution_order):
            self.log_manager.debug(f"Executing super-node layer {layer_idx} with {len(layer_items)} items")
            self._execute_super_layer(layer_items)
    
    def _execute_super_layer(self, layer_items: List[Dict[str, Any]]) -> None:
        """Execute a single super-node layer."""
        self._execute_super_layer_parallel(layer_items)
    
    def _execute_super_layer_parallel(self, layer_items: List[Dict[str, Any]]) -> None:
        """Execute a super-node layer in parallel."""
        def item_desc_func(item: Dict[str, Any]) -> str:
            if item["type"] == "cycle":
                return f"cycle {item['cycle_id']}"
            elif item["type"] == "node":
                # New format
                return f"node {item['node_id']}"
            else:
                # Old format: "layer"
                return f"node {item['nodes'][0]}"

        self.parallel_executor.execute_items_parallel(
            layer_items,
            self._execute_super_item,
            item_desc_func
        )
    
    def _execute_super_item(self, item: Dict[str, Any]) -> None:
        """Execute a single super-node item (node or cycle)."""
        if item["type"] == "layer":
            # Old format: {"type": "layer", "nodes": [node_id]}
            self._execute_single_node(item["nodes"][0])
        elif item["type"] == "node":
            # New format from GraphTopologyBuilder: {"type": "node", "node_id": "..."}
            self._execute_single_node(item["node_id"])
        elif item["type"] == "cycle":
            self._execute_cycle(item)
    
    def _execute_single_node(self, node_id: str) -> None:
        """Execute a non-cycle node."""
        self.log_manager.debug(f"Executing non-cycle node: {node_id}")
        
        node = self.nodes[node_id]
        if node.is_triggered():
            self.execute_node_func(node)
        else:
            self.log_manager.warning(f"Node {node_id} is not triggered, skipping execution")
    
    def _execute_cycle(self, cycle_info: Dict[str, Any]) -> None:
        """Execute a cycle using the multi-iteration logic."""
        cycle_id = cycle_info["cycle_id"]
        nodes = cycle_info["nodes"]

        self.log_manager.debug(f"Executing cycle {cycle_id} with nodes: {nodes}")

        # Step 2: Validate cycle entry uniqueness
        try:
            initial_node_id = self._validate_cycle_entry(cycle_id, nodes)
        except ValueError as e:
            self.log_manager.error(str(e))
            raise

        if initial_node_id is None:
            self.log_manager.debug(
                f"Cycle {cycle_id} has no triggered entry node in this pass; skipping execution"
            )
            return

        # Store initial node in cycle_manager
        self.cycle_manager.cycles[cycle_id].initial_node = initial_node_id
        self.log_manager.debug(f"Cycle {cycle_id} initial node: {initial_node_id}")

        # Activate cycle
        self.cycle_manager.activate_cycle(cycle_id)

        # Step 4: Execute cycle with iterations
        self._execute_cycle_with_iterations(
            cycle_id,
            nodes,
            initial_node_id,
            max_iterations=self.cycle_manager.cycles[cycle_id].get_max_iterations()
        )

        # Cleanup
        self.cycle_manager.deactivate_cycle(cycle_id)
        self.log_manager.debug(f"Cycle {cycle_id} completed")
    
    # ==================== New Methods for Refactored Cycle Execution ====================

    def _validate_cycle_entry(self, cycle_id: str, nodes: List[str]) -> str | None:
        """
        Validate that exactly one node in the cycle is triggered by external edges.

        Args:
            cycle_id: The cycle ID
            nodes: List of node IDs in the cycle

        Returns:
            The ID of the unique initial node

        Raises:
            ValueError: If no node or multiple nodes are triggered
        """
        triggered_nodes: List[str] = []

        for node_id in nodes:
            node = self.nodes[node_id]
            # Check if any external predecessor (node outside the cycle) triggers this node
            for predecessor in node.predecessors:
                if predecessor.id not in nodes:  # External node
                    edge = predecessor.find_outgoing_edge(node_id)
                    if edge and edge.trigger and edge.triggered:
                        triggered_nodes.append(node_id)
                        break

        cycle_info = self.cycle_manager.cycles.get(cycle_id)
        configured_entry = cycle_info.configured_entry_node if cycle_info else None

        if len(triggered_nodes) == 0:
            if configured_entry:
                return configured_entry
            return None
        elif len(triggered_nodes) > 1:
            raise ValueError(
                f"Cycle {cycle_id} has multiple triggered entry nodes: {triggered_nodes}. "
                "Only one entry node must be triggered when entering a cycle."
            )
        entry_node = triggered_nodes[0]
        if configured_entry and entry_node != configured_entry:
            raise ValueError(
                f"Cycle {cycle_id} entry mismatch: configured '{configured_entry}' "
                f"but triggered '{entry_node}'",
            )

        return entry_node

    def _execute_cycle_with_iterations(
        self,
        cycle_id: str,
        cycle_nodes: List[str],
        initial_node_id: str,
        max_iterations: int,
    ) -> Set[str]:
        """
        Execute a cycle with multiple iterations.

        Args:
            cycle_id: Cycle ID
            cycle_nodes: List of all nodes in the cycle
            initial_node_id: Initial node ID
            max_iterations: Maximum number of iterations

        Returns:
            A tuple of two sets:
                - exit_nodes: nodes triggered outside the *current* cycle scope
                - external_nodes: subset of exit_nodes that are also outside the
                  provided parent_cycle_nodes scope
        """
        iteration = 0

        while iteration < max_iterations:
            self.log_manager.debug(
                f"Cycle {cycle_id} iteration {iteration + 1}/{max_iterations}"
            )

            # Step 1: Detect nested cycles in the scoped subgraph
            inner_cycles = self._detect_cycles_in_scope(cycle_nodes, initial_node_id)

            # Build topological layers (whether there are nested cycles or not)
            execution_layers = self._build_topological_layers_in_scope(
                cycle_nodes, initial_node_id, inner_cycles,
                is_first_iteration=(iteration == 0)
            )

            # Execute the topological layers
            external_nodes = self._execute_scope_layers(
                execution_layers,
                cycle_id,
                cycle_nodes,
                initial_node_id=initial_node_id,
                is_first_iteration=(iteration == 0)
            )

            if external_nodes:
                self.log_manager.debug(
                    f"Cycle {cycle_id} exited - external nodes triggered: {sorted(external_nodes)}"
                )
                return external_nodes

            # Step 4: Check if initial node is retriggered
            if not self._is_initial_node_retriggered(initial_node_id, cycle_nodes):
                self.log_manager.debug(
                    f"Cycle {cycle_id} completed - initial node not retriggered"
                )
                break

            iteration += 1

        if iteration >= max_iterations:
            self.log_manager.warning(
                f"Cycle {cycle_id} reached max iterations ({max_iterations})"
            )
        return set()
    def _detect_cycles_in_scope(
        self,
        scope_nodes: List[str],
        initial_node_id: str
    ) -> List[Set[str]]:
        """
        Detect nested cycles within the scoped subgraph.

        Constructs a subgraph containing only:
        1. Nodes in scope_nodes
        2. Edges where both source and target are in scope_nodes
        3. Initial node's incoming edges are REMOVED (to break the outer cycle)

        Args:
            scope_nodes: List of node IDs in the current scope
            initial_node_id: Initial node ID (whose incoming edges are removed)

        Returns:
            List of detected nested cycles (excluding the current cycle itself)
        """
        # Build scoped nodes with initial node's incoming edges removed
        scoped_nodes = self._build_scoped_nodes(scope_nodes, clear_entry_node=initial_node_id)

        # Use GraphTopologyBuilder to detect cycles
        all_cycles = GraphTopologyBuilder.detect_cycles(scoped_nodes)

        # Filter out single-node "cycles" (unless they have self-loops)
        nested_cycles = [
            cycle for cycle in all_cycles
            if len(cycle) > 1
        ]

        return nested_cycles

    def _build_scoped_nodes(
        self,
        scope_nodes: List[str],
        clear_entry_node: Optional[str] = None
    ) -> Dict[str, Node]:
        """
        Build a scoped subgraph containing only nodes and edges within the scope.

        Args:
            scope_nodes: List of node IDs in the scope
            clear_entry_node: If specified, this node's incoming edges will be removed
                            (used to break the outer cycle when detecting nested cycles)

        Returns:
            Dictionary of scoped nodes
        """
        scoped_nodes = {}
        scope_nodes_set = set(scope_nodes)

        for node_id in scope_nodes:
            original_node = self.nodes[node_id]
            # Shallow copy the node
            scoped_node = copy.copy(original_node)

            # Filter outgoing edges: only keep edges where target is in scope AND trigger=true
            # Special case: if target is clear_entry_node, remove this edge
            scoped_edges = [
                edge_link for edge_link in original_node.iter_outgoing_edges()
                if edge_link.target.id in scope_nodes_set
                and edge_link.trigger
                and edge_link.target.id != clear_entry_node  # Remove edges to entry node
            ]
            scoped_node._outgoing_edges = scoped_edges

            # Filter predecessors: only keep predecessors in scope AND with trigger=true edge
            # Special case: if this node is clear_entry_node, clear all predecessors
            if node_id == clear_entry_node:
                scoped_node.predecessors = []
            else:
                scoped_predecessors = []
                for pred in original_node.predecessors:
                    if pred.id in scope_nodes_set:
                        # Check if the edge from pred to node has trigger=true
                        edge = pred.find_outgoing_edge(node_id)
                        if edge and edge.trigger:
                            scoped_predecessors.append(pred)
                scoped_node.predecessors = scoped_predecessors

            # Filter successors: only keep successors in scope AND with trigger=true edge
            # Special case: remove clear_entry_node from successors
            scoped_successors = [
                succ for succ in original_node.successors
                if succ.id in scope_nodes_set
                and succ.id != clear_entry_node  # Remove entry node from successors
                and any(
                    edge_link.target.id == succ.id and edge_link.trigger
                    for edge_link in original_node.iter_outgoing_edges()
                )
            ]
            scoped_node.successors = scoped_successors

            scoped_nodes[node_id] = scoped_node

        return scoped_nodes

    def _build_topological_layers_in_scope(
        self,
        scope_nodes: List[str],
        initial_node_id: str,
        inner_cycles: List[Set[str]],
        is_first_iteration: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Build topological execution order for the scoped subgraph.

        Args:
            scope_nodes: List of node IDs in the scope
            initial_node_id: Initial node ID
            inner_cycles: List of nested cycles detected in the scope
            is_first_iteration: Whether this is the first iteration (affects initial node handling)

        Returns:
            List of execution layers, each containing execution items
        """
        # Build scoped nodes WITHOUT clearing entry node
        # We want to keep all edges intact for execution
        scoped_nodes = self._build_scoped_nodes(scope_nodes, clear_entry_node=None)

        # Handle entry points based on iteration:
        # - First iteration: manually clear initial node's predecessors (for in_degree calculation only)
        # - Subsequent iterations: clear predecessors for all triggered nodes
        if is_first_iteration:
            # Clear initial node's predecessors to make it an entry point
            if initial_node_id in scoped_nodes:
                scoped_nodes[initial_node_id].predecessors = []
        else:
            # Subsequent iterations: clear predecessors for all triggered nodes
            for node_id in scope_nodes:
                if self.nodes[node_id].is_triggered():
                    scoped_nodes[node_id].predecessors = []

        # Extract scoped edges from scoped_nodes (not original nodes)
        # This ensures consistency with the filtered graph structure
        scoped_edges = []

        # Collect nodes whose incoming edges should be excluded
        # (to break cycles in topological sorting)
        exclude_targets = set()
        if is_first_iteration:
            # First iteration: exclude edges to initial_node
            exclude_targets.add(initial_node_id)
        else:
            # Subsequent iterations: exclude edges to all triggered nodes
            for node_id in scope_nodes:
                if self.nodes[node_id].is_triggered():
                    exclude_targets.add(node_id)

        for node_id in scope_nodes:
            # Use scoped_node to get filtered edges
            scoped_node = scoped_nodes.get(node_id)
            if scoped_node:
                for edge_link in scoped_node.iter_outgoing_edges():
                    # Exclude edges pointing to nodes in exclude_targets
                    if edge_link.target.id in exclude_targets:
                        continue
                    scoped_edges.append({
                        "from": node_id,
                        "to": edge_link.target.id,
                        "trigger": edge_link.trigger,
                        "condition": edge_link.condition
                    })

        # Use GraphTopologyBuilder to build execution order
        if not inner_cycles:
            # No nested cycles, use DAG layers
            layers = GraphTopologyBuilder.build_dag_layers(scoped_nodes)
            return layers
        else:
            # Has nested cycles, use super-node approach
            super_graph = GraphTopologyBuilder.create_super_node_graph(
                scoped_nodes, scoped_edges, inner_cycles
            )
            layers = GraphTopologyBuilder.topological_sort_super_nodes(
                super_graph, inner_cycles
            )
            return layers

    def _execute_scope_layers(
        self,
        execution_layers: List[List[Dict[str, Any]]],
        parent_cycle_id: str,
        parent_cycle_nodes: List[str],
        initial_node_id: Optional[str] = None,
        is_first_iteration: bool = False
    ) -> Set[str]:
        """
        Execute scoped layers with parallelism, supporting nested cycles.

        Args:
            execution_layers: List of execution layers
            parent_cycle_id: Parent cycle ID
            parent_cycle_nodes: List of nodes in the parent cycle
            initial_node_id: Initial node ID (for first iteration special handling)
            is_first_iteration: Whether this is the first iteration

        Returns:
            external_nodes: subset of exit_nodes outside parent_cycle_nodes_set
        """
        scope_node_set = set(parent_cycle_nodes)
        external_nodes: Set[str] = set()
        stop_event = threading.Event()
        result_lock = threading.Lock()

        def record_external(nodes: Set[str]) -> None:
            nonlocal external_nodes
            if not nodes:
                return
            with result_lock:
                if nodes:
                    external_nodes.update(nodes)
                    stop_event.set()

        def item_desc(item: Dict[str, Any]) -> str:
            if item["type"] == "node":
                return f"node {item['node_id']}"
            if item["type"] == "cycle":
                return f"cycle {item['cycle_id']}"
            return "layer_item"

        for layer in execution_layers:
            if stop_event.is_set():
                break

            def executor_func(item: Dict[str, Any]) -> None:
                if stop_event.is_set():
                    return

                if item["type"] == "node":
                    _node_id = item["node_id"]
                    force_execute = is_first_iteration and (_node_id == initial_node_id)
                    targets = self._execute_single_cycle_node_in_scope(
                        _node_id,
                        scope_node_set,
                        force_execute=force_execute
                    )
                    if targets:
                        record_external(targets)

                elif item["type"] == "cycle":
                    inner_cycle_nodes = item["nodes"]
                    inner_cycle_id = item["cycle_id"]

                    self.log_manager.debug(
                        f"Executing nested cycle {inner_cycle_id} within cycle {parent_cycle_id}"
                    )

                    try:
                        inner_initial_node = self._validate_cycle_entry(
                            inner_cycle_id, inner_cycle_nodes
                        )
                    except ValueError as e:
                        self.log_manager.error(str(e))
                        raise

                    if inner_initial_node is None:
                        self.log_manager.debug(
                            f"Nested cycle {inner_cycle_id} has no triggered entry; skipping"
                        )
                        return

                    inner_external_nodes = self._execute_cycle_with_iterations(
                        inner_cycle_id,
                        inner_cycle_nodes,
                        inner_initial_node,
                        max_iterations=100,
                    )

                    if inner_external_nodes:
                        filtered = {
                            node
                            for node in inner_external_nodes
                            if node not in scope_node_set
                        }
                        if filtered:
                            record_external(filtered)

            self.parallel_executor.execute_items_parallel(
                layer,
                executor_func,
                item_desc
            )

            if stop_event.is_set():
                break

        if external_nodes:
            for node_id in scope_node_set:
                self.nodes[node_id].reset_triggers()

        return external_nodes

    def _execute_single_cycle_node_in_scope(
        self,
        node_id: str,
        scope_node_set: Set[str],
        force_execute: bool = False
    ) -> Set[str]:
        """
        Execute a single node within a cycle scope.

        Args:
            node_id: Node ID to execute
            scope_node_set: Nodes that belong to the current scoped cycle
            force_execute: If True, execute even if not triggered (for initial node in first iteration)

        Returns:
            Set of node IDs triggered outside the current scoped cycle
        """
        node = self.nodes[node_id]

        # Check if node is triggered (unless force_execute is True)
        if not force_execute:
            if not node.is_triggered():
                return set()

        # Reset edge triggers
        for edge_link in node.iter_outgoing_edges():
            edge_link.triggered = False

        # Execute the node
        self.execute_node_func(node)

        # Check if any external node was triggered
        external_targets: Set[str] = set()
        for edge_link in node.iter_outgoing_edges():
            if edge_link.target.id not in scope_node_set and edge_link.triggered:
                self.log_manager.debug(
                    f"Node {node_id} triggered external node {edge_link.target.id}"
                )
                external_targets.add(edge_link.target.id)

        return external_targets

    def _is_initial_node_retriggered(
        self,
        initial_node_id: str,
        cycle_nodes: List[str]
    ) -> bool:
        """
        Check if the initial node is retriggered by any internal edge (from within the cycle).

        Args:
            initial_node_id: Initial node ID
            cycle_nodes: List of nodes in the cycle

        Returns:
            True if the initial node is retriggered by an internal edge
        """
        initial_node = self.nodes[initial_node_id]

        for predecessor in initial_node.predecessors:
            # Only check predecessors within the cycle
            if predecessor.id in cycle_nodes:
                edge = predecessor.find_outgoing_edge(initial_node_id)
                if edge and edge.trigger and edge.triggered:
                    return True

        return False
