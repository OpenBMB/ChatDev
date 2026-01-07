"""Graph topology builder utility for cycle detection and topological sorting.

This module provides stateless utilities for building execution order of graphs,
supporting both global graphs and scoped subgraphs (e.g., within cycles).
"""

from typing import Dict, List, Set, Any
from entity.configs import Node
from workflow.cycle_manager import CycleDetector


class GraphTopologyBuilder:
    """
    Graph topology structure builder.

    Responsibilities:
    1. Detect cycles (based on CycleDetector)
    2. Build super-node graphs
    3. Perform topological sorting

    Features:
    - Stateless (pure static methods)
    - Can be used for both global graphs and local subgraphs
    - Does not depend on specific GraphContext instances
    """

    @staticmethod
    def detect_cycles(nodes: Dict[str, Node]) -> List[Set[str]]:
        """
        Detect cycles in the given node set.

        Args:
            nodes: Dictionary of nodes to analyze

        Returns:
            List of cycles, where each cycle is a set of node IDs
        """
        detector = CycleDetector()
        return detector.detect_cycles(nodes)

    @staticmethod
    def create_super_node_graph(
        nodes: Dict[str, Node],
        edges: List[Dict[str, Any]],
        cycles: List[Set[str]]
    ) -> Dict[str, Set[str]]:
        """
        Create a super-node graph where each cycle is treated as a single node.

        Args:
            nodes: Node dictionary
            edges: Edge configuration list (only edges to consider)
            cycles: List of detected cycles

        Returns:
            Super-node dependency graph: {super_node_id: set(predecessor_super_node_ids)}
        """
        super_nodes = {}
        node_to_super = {}

        # Create super-nodes for cycles
        for i, cycle_nodes in enumerate(cycles):
            super_node_id = f"super_cycle_{i}"
            super_nodes[super_node_id] = set()
            for node_id in cycle_nodes:
                node_to_super[node_id] = super_node_id

        # Create super-nodes for non-cycle nodes (each non-cycle node is its own super-node)
        for node_id in nodes.keys():
            if node_id not in node_to_super:
                super_node_id = f"node_{node_id}"
                super_nodes[super_node_id] = set()
                node_to_super[node_id] = super_node_id

        # Build dependencies between super-nodes
        for edge_config in edges:
            from_node = edge_config["from"]
            to_node = edge_config["to"]

            # Skip edges not in the node set
            if from_node not in nodes or to_node not in nodes:
                continue

            from_super = node_to_super[from_node]
            to_super = node_to_super[to_node]

            # Only add dependency if between different super-nodes
            if from_super != to_super:
                super_nodes[to_super].add(from_super)

        return super_nodes

    @staticmethod
    def topological_sort_super_nodes(
        super_node_graph: Dict[str, Set[str]],
        cycles: List[Set[str]]
    ) -> List[List[Dict[str, Any]]]:
        """
        Perform topological sort on super-node graph to determine execution order.

        Args:
            super_node_graph: Super-node dependency graph
            cycles: List of cycles for mapping super-nodes to cycle info

        Returns:
            Execution layers, where each layer contains items that can be executed in parallel.
            Format: [
                [{"type": "node", "node_id": "A"}, {"type": "cycle", "cycle_id": "...", "nodes": [...]}],
                [...]
            ]
        """
        # Calculate in-degrees
        in_degree = {
            super_node: len(predecessors)
            for super_node, predecessors in super_node_graph.items()
        }

        # Find super-nodes with no dependencies
        ready = [node for node, degree in in_degree.items() if degree == 0]
        execution_layers = []

        # Create cycle lookup
        cycle_lookup = {}
        for i, cycle_nodes in enumerate(cycles):
            cycle_id = f"cycle_{i}_{cycle_nodes}"
            cycle_lookup[f"super_cycle_{i}"] = {
                "cycle_id": cycle_id,
                "nodes": cycle_nodes
            }

        while ready:
            current_layer = ready[:]
            ready.clear()

            # Convert to execution items
            layer_items = []
            for super_node in current_layer:
                if super_node.startswith("super_cycle_"):
                    # Cycle super-node
                    cycle_data = cycle_lookup[super_node]
                    layer_items.append({
                        "type": "cycle",
                        "cycle_id": cycle_data["cycle_id"],
                        "nodes": list(cycle_data["nodes"])
                    })
                elif super_node.startswith("node_"):
                    # Regular node
                    node_id = super_node.replace("node_", "")
                    layer_items.append({
                        "type": "node",
                        "node_id": node_id
                    })

                # Update dependencies
                for dependent in super_node_graph:
                    if super_node in super_node_graph[dependent]:
                        super_node_graph[dependent].remove(super_node)
                        in_degree[dependent] -= 1
                        if in_degree[dependent] == 0:
                            ready.append(dependent)

            if layer_items:
                execution_layers.append(layer_items)

        return execution_layers

    @staticmethod
    def build_execution_order(
        nodes: Dict[str, Node],
        edges: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """
        One-stop method to build execution order.

        Combines cycle detection, super-node construction, and topological sorting.

        Args:
            nodes: Node dictionary
            edges: Edge configuration list

        Returns:
            Execution layers
        """
        cycles = GraphTopologyBuilder.detect_cycles(nodes)

        if not cycles:
            # No cycles, return DAG layers directly
            return GraphTopologyBuilder.build_dag_layers(nodes)

        super_graph = GraphTopologyBuilder.create_super_node_graph(
            nodes, edges, cycles
        )

        return GraphTopologyBuilder.topological_sort_super_nodes(
            super_graph, cycles
        )

    @staticmethod
    def build_dag_layers(nodes: Dict[str, Node]) -> List[List[Dict[str, Any]]]:
        """
        Build topological layers for DAG (Directed Acyclic Graph).

        Args:
            nodes: Node dictionary

        Returns:
            Layers in execution item format
        """
        in_degree = {
            node_id: len(node.predecessors)
            for node_id, node in nodes.items()
        }

        frontier = [
            node_id for node_id, deg in in_degree.items() if deg == 0
        ]
        layers = []

        while frontier:
            # Convert to execution item format
            layer_items = [
                {"type": "node", "node_id": node_id}
                for node_id in frontier
            ]
            layers.append(layer_items)

            next_frontier = []
            for node_id in frontier:
                for successor in nodes[node_id].successors:
                    in_degree[successor.id] -= 1
                    if in_degree[successor.id] == 0:
                        next_frontier.append(successor.id)
            frontier = next_frontier

        return layers
