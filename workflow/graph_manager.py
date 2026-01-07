"""Graph management and construction utilities for workflow graphs."""

from typing import Dict, List, Set, Any
import copy

from entity.configs import ConfigError, SubgraphConfig
from entity.configs.edge.edge_condition import EdgeConditionConfig
from entity.configs.base import extend_path
from entity.configs.node.subgraph import SubgraphFileConfig, SubgraphInlineConfig
from workflow.cycle_manager import CycleManager
from workflow.subgraph_loader import load_subgraph_config
from workflow.topology_builder import GraphTopologyBuilder
from utils.env_loader import build_env_var_map
from utils.vars_resolver import resolve_mapping_with_vars
from workflow.graph_context import GraphContext


class GraphManager:
    """Manages graph construction, cycle detection, and execution order determination."""
    
    def __init__(self, graph: "GraphContext") -> None:
        """Initialize GraphManager with a GraphContext instance."""
        self.graph = graph
        self.cycle_manager = CycleManager()
    
    def build_graph_structure(self) -> None:
        """Build the complete graph structure including nodes, edges, and layers."""
        self._instantiate_nodes()
        self._initiate_edges()
        self._determine_start_nodes()
        self._warn_on_untriggerable_nodes()
        self._build_topology_and_metadata()
    
    def _instantiate_nodes(self) -> None:
        """Instantiate all nodes from configuration."""
        self.graph.nodes.clear()
        for node_def in self.graph.config.get_node_definitions():
            node_id = node_def.id
            if node_id in self.graph.nodes:
                print(f"Duplicated node id detected: {node_id}")
                continue
            node_instance = copy.deepcopy(node_def)
            node_instance.predecessors = []
            node_instance.successors = []
            node_instance._outgoing_edges = []
            node_instance.vars = dict(self.graph.vars)
            self.graph.nodes[node_id] = node_instance

            if node_instance.node_type == "subgraph":
                self._build_subgraph(node_id)
    
    def _build_subgraph(self, node_id: str) -> None:
        """Build a subgraph for the given node ID."""
        from entity.graph_config import GraphConfig
        from workflow.graph_context import GraphContext
        
        subgraph_config_data = self.graph.nodes[node_id].as_config(SubgraphConfig)
        if not subgraph_config_data:
            return

        parent_source = self.graph.config.get_source_path()
        subgraph_vars: Dict[str, Any] = {}

        if subgraph_config_data.type == "config":
            inline_cfg = subgraph_config_data.as_config(SubgraphInlineConfig)
            if not inline_cfg:
                raise ConfigError(
                    f"Inline subgraph configuration missing for node '{node_id}'",
                    subgraph_config_data.path,
                )
            config_payload = copy.deepcopy(inline_cfg.graph)
            source_path = parent_source
        elif subgraph_config_data.type == "file":
            file_cfg = subgraph_config_data.as_config(SubgraphFileConfig)
            if not file_cfg:
                raise ConfigError(
                    f"File subgraph configuration missing for node '{node_id}'",
                    subgraph_config_data.path,
                )
            config_payload, subgraph_vars, source_path = load_subgraph_config(
                file_cfg.file_path,
                parent_source=parent_source,
            )
        else:
            raise ConfigError(
                f"Unsupported subgraph configuration on node '{node_id}'",
                subgraph_config_data.path,
            )

        combined_vars = dict(self.graph.config.vars)
        combined_vars.update(subgraph_vars)

        resolve_mapping_with_vars(
            config_payload,
            env_lookup=build_env_var_map(),
            vars_map=combined_vars,
            path=f"subgraph[{node_id}]",
        )

        if config_payload.get("log_level", None) is None:
            config_payload["log_level"] = self.graph.log_level.value

        subgraph_config = GraphConfig.from_dict(
            config=config_payload,
            name=f"{self.graph.name}_{node_id}_subgraph",
            output_root=self.graph.config.output_root,
            source_path=source_path,
            vars=combined_vars,
        )

        subgraph = GraphContext(config=subgraph_config)

        subgraph_manager = GraphManager(subgraph)
        subgraph_manager.build_graph_structure()

        self.graph.subgraphs[node_id] = subgraph
    
    def _initiate_edges(self) -> None:
        """Initialize edges and determine layers or cycle execution order."""
        # For majority voting mode, there are no edges by design
        if self.graph.is_majority_voting:
            print("Majority voting mode detected - skipping edge initialization")
            self.graph.edges = []
            
            # For majority voting, all nodes are independent and can be executed in parallel
            # Create a single layer with all nodes
            all_node_ids = list(self.graph.nodes.keys())
            self.graph.layers = [all_node_ids]
            return
        
        self.graph.edges = []
        for edge_config in self.graph.config.get_edge_definitions():
            src = edge_config.source
            dst = edge_config.target
            if src not in self.graph.nodes or dst not in self.graph.nodes:
                print(f"Edge references unknown node: {src}->{dst}")
                continue
                
            condition_config = edge_config.condition
            if condition_config is None:
                condition_config = EdgeConditionConfig.from_dict("true", path=extend_path(edge_config.path, "condition"))
            condition_value = condition_config.to_external_value()
            process_config = edge_config.process
            process_value = process_config.to_external_value() if process_config else None
            dynamic_config = edge_config.dynamic
            payload = {
                "trigger": edge_config.trigger,
                "condition": condition_value,
                "condition_config": condition_config,
                "condition_label": condition_config.display_label(),
                "condition_type": condition_config.type,
                "carry_data": edge_config.carry_data,
                "keep_message": edge_config.keep_message,
                "clear_context": edge_config.clear_context,
                "clear_kept_context": edge_config.clear_kept_context,
                "process_config": process_config,
                "process": process_value,
                "process_type": process_config.type if process_config else None,
                "dynamic_config": dynamic_config,
            }
            self.graph.nodes[src].add_successor(self.graph.nodes[dst], payload)
            self.graph.nodes[dst].add_predecessor(self.graph.nodes[src])
            self.graph.edges.append({
                "from": src,
                "to": dst,
                "trigger": edge_config.trigger,
                "condition": condition_value,
                "condition_type": condition_config.type,
                "carry_data": edge_config.carry_data,
                "keep_message": edge_config.keep_message,
                "clear_context": edge_config.clear_context,
                "clear_kept_context": edge_config.clear_kept_context,
                "process": process_value,
                "process_type": process_config.type if process_config else None,
                "dynamic": dynamic_config is not None,
            })
        
        # Check for cycles and build appropriate execution structure
        cycles = self._detect_cycles()
        self.graph.has_cycles = len(cycles) > 0

        if self.graph.has_cycles:
            print(f"Detected {len(cycles)} cycle(s) in the workflow graph.")
            self.graph.layers = self._build_cycle_execution_order(cycles)
        else:
            self.graph.layers = self._build_dag_layers()
    
    def _detect_cycles(self) -> List[Set[str]]:
        """Detect cycles in the graph using GraphTopologyBuilder."""
        return GraphTopologyBuilder.detect_cycles(self.graph.nodes)
    
    def _build_dag_layers(self) -> List[List[str]]:
        """Build layers for DAG (Directed Acyclic Graph) using GraphTopologyBuilder."""
        layers_with_items = GraphTopologyBuilder.build_dag_layers(self.graph.nodes)

        # Convert format to be compatible with existing code
        layers = [
            [item["node_id"] for item in layer]
            for layer in layers_with_items
        ]

        print(f"layers: {layers}")

        if len(set(node_id for layer in layers for node_id in layer)) != len(self.graph.nodes):
            print("Detected a cycle in the workflow graph; a DAG is required.")

        return layers
    
    def _build_cycle_execution_order(self, cycles: List[Set[str]]) -> List[List[str]]:
        """Build execution order for graphs with cycles using super-node abstraction and GraphTopologyBuilder."""
        # Initialize cycle manager
        self.cycle_manager.initialize_cycles(cycles, self.graph.nodes)

        # Use GraphTopologyBuilder to create super-node graph
        super_node_graph = GraphTopologyBuilder.create_super_node_graph(
            self.graph.nodes,
            self.graph.edges,
            cycles
        )

        # Use GraphTopologyBuilder for topological sorting
        execution_order = GraphTopologyBuilder.topological_sort_super_nodes(
            super_node_graph,
            cycles
        )

        # Enrich execution_order with entry_nodes and exit_edges from cycle_manager
        for layer in execution_order:
            for item in layer:
                if item["type"] == "cycle":
                    cycle_id = item["cycle_id"]
                    cycle_info = self.cycle_manager.cycles[cycle_id]
                    item["entry_nodes"] = list(cycle_info.entry_nodes)
                    item["exit_edges"] = cycle_info.exit_edges

        self.graph.cycle_execution_order = execution_order

        # Return a simplified layer structure for compatibility
        return [["__CYCLE_AWARE__"]]  # Special marker for cycle-aware execution

    def _build_topology_and_metadata(self) -> None:
        """Build topology and metadata for the graph."""
        self.graph.topology = [node_id for layer in self.graph.layers for node_id in layer]
        self.graph.depth = len(self.graph.layers) - 1 if self.graph.layers else 0
        self.graph.metadata = self._build_metadata()
    
    def _build_metadata(self) -> Dict[str, Any]:
        """Build metadata for the graph."""
        graph_def = self.graph.config.definition
        catalog: Dict[str, Any] = {}
        for node_id, node in self.graph.nodes.items():
            catalog[node_id] = {
                "type": node.node_type,
                "description": node.description,
                "model_name": node.model_name,
                "role": node.role,
                "tools": node.tools,
                "memories": node.memories,
                "params": node.params,
            }

        return {
            "design_id": graph_def.id,
            "node_count": len(self.graph.nodes),
            "edge_count": len(self.graph.edges),
            "start": list(self.graph.start_nodes),
            "end": graph_def.end_nodes,
            "catalog": catalog,
            "topology": self.graph.topology,
            "layers": self.graph.layers,
        }

    def _determine_start_nodes(self) -> None:
        """Determine the effective set of start nodes (explicit only)."""
        definition = self.graph.config.definition
        explicit_ordered = list(definition.start_nodes)
        explicit_set = set(explicit_ordered)

        # if explicit_ordered and not self.graph.has_cycles:
        #     raise ConfigError(
        #         "start nodes can only be specified for graphs that contain cycles",
        #         extend_path(definition.path, "start"),
        #     )

        if explicit_set:
            cycle_path = extend_path(definition.path, "start")
            for node_id in explicit_ordered:
                if node_id not in self.graph.nodes:
                    raise ConfigError(
                        f"start node '{node_id}' not defined in nodes",
                        cycle_path,
                    )

                cycle_id = self.cycle_manager.node_to_cycle.get(node_id)
                if cycle_id is None:
                    continue
                cycle_info = self.cycle_manager.cycles.get(cycle_id)
                if cycle_info is None:
                    raise ConfigError(
                        f"cycle data missing for start node '{node_id}'",
                        cycle_path,
                    )

                if cycle_info.configured_entry_node and cycle_info.configured_entry_node != node_id:
                    raise ConfigError(
                        f"cycle '{cycle_id}' already has start node '{cycle_info.configured_entry_node}'",
                        cycle_path,
                    )

                cycle_info.configured_entry_node = node_id

        if not explicit_ordered:
            raise ConfigError(
                "Unable to determine a start node for this graph. Configure at least one Start Node via Configure Graph > Advanced Settings > Start Node > input node ID.",
                extend_path(definition.path, "start"),
            )

        self.graph.start_nodes = explicit_ordered
        self.graph.explicit_start_nodes = explicit_ordered

    def _warn_on_untriggerable_nodes(self) -> None:
        """Emit warnings for nodes that cannot be triggered by any predecessor."""
        start_nodes = set(self.graph.start_nodes or [])
        for node_id, node in self.graph.nodes.items():
            if not node.predecessors:
                continue
            if node_id in start_nodes:
                continue

            has_triggerable_edge = False
            for predecessor in node.predecessors:
                for edge_link in predecessor.iter_outgoing_edges():
                    if edge_link.target is node and edge_link.trigger:
                        has_triggerable_edge = True
                        break
                if has_triggerable_edge:
                    break

            if not has_triggerable_edge:
                print(
                    f"Warning: node '{node_id}' has no triggerable incoming edges and will never execute."
                )
    
    def get_cycle_manager(self) -> CycleManager:
        """Get the cycle manager instance."""
        return self.cycle_manager
    
    def build_graph(self) -> None:
        """Build graph structure only (no memory/thinking initialization)."""
        self.build_graph_structure()
