"""Dynamic edge executor for edge-level Map and Tree execution.

Handles dynamic node expansion based on edge-level dynamic configuration.
When a message passes through an edge with dynamic config, the target node
is virtually expanded into multiple instances based on split results.
"""

import concurrent.futures
from typing import Callable, Dict, List, Optional

from entity.configs import Node
from entity.configs.edge.dynamic_edge_config import DynamicEdgeConfig
from entity.messages import Message, MessageRole
from runtime.node.splitter import create_splitter_from_config, group_messages
from utils.log_manager import LogManager


class DynamicEdgeExecutor:
    """Execute edge-level dynamic expansion.
    
    When an edge has dynamic configuration, this executor:
    1. Splits the payload passing through the edge
    2. Executes the target node for each split unit
    3. Collects and returns results (flat for Map, reduced for Tree)
    """
    
    def __init__(
        self,
        log_manager: LogManager,
        node_executor_func: Callable[[Node, List[Message]], List[Message]],
    ):
        """Initialize the dynamic edge executor.
        
        Args:
            log_manager: Logger instance
            node_executor_func: Function to execute a node with inputs
        """
        self.log_manager = log_manager
        self.node_executor_func = node_executor_func
    
    def execute(
        self,
        target_node: Node,
        payload: Message,
        dynamic_config: DynamicEdgeConfig,
        static_inputs: Optional[List[Message]] = None,
    ) -> List[Message]:
        """Execute dynamic expansion for an edge.
        
        Args:
            target_node: The node to execute (will be used as template)
            payload: The message passing through the edge
            dynamic_config: Edge dynamic configuration
            static_inputs: Optional static inputs from non-dynamic edges
            
        Returns:
            List of output messages from all executions
        """
        split_config = dynamic_config.split
        
        # Create splitter based on config
        splitter = create_splitter_from_config(split_config)
        
        # Split the payload into execution units
        execution_units = splitter.split([payload])
        
        if not execution_units:
            self.log_manager.debug(
                f"Dynamic edge -> {target_node.id}: no execution units after split"
            )
            return []
        
        self.log_manager.info(
            f"Dynamic edge -> {target_node.id}: splitting into {len(execution_units)} parallel units"
        )
        
        if dynamic_config.is_map():
            return self._execute_map(
                target_node, execution_units, dynamic_config, static_inputs
            )
        elif dynamic_config.is_tree():
            return self._execute_tree(
                target_node, execution_units, dynamic_config, static_inputs
            )
        else:
            raise ValueError(f"Unknown dynamic type: {dynamic_config.type}")

    def execute_from_inputs(
        self,
        target_node: Node,
        inputs: List[Message],
        dynamic_config: DynamicEdgeConfig,
        static_inputs: Optional[List[Message]] = None,
    ) -> List[Message]:
        """Execute dynamic expansion using all collected inputs.
        
        This method is called from _execute_node when a node has incoming edges
        with dynamic configuration. All inputs are already collected and passed here.
        
        Args:
            target_node: The node to execute
            inputs: Dynamic edge inputs to be split
            dynamic_config: Edge dynamic configuration
            static_inputs: Non-dynamic edge inputs to be replicated to all units
            
        Returns:
            List of output messages from all executions
        """
        split_config = dynamic_config.split
        static_inputs = static_inputs or []
        
        # Create splitter based on config
        splitter = create_splitter_from_config(split_config)
        
        # Split only dynamic inputs into execution units
        execution_units = splitter.split(inputs)
        
        if not execution_units:
            self.log_manager.debug(
                f"Dynamic node {target_node.id}: no execution units after split"
            )
            # If no dynamic inputs but have static inputs, execute once with static inputs
            if static_inputs:
                return self.node_executor_func(target_node, static_inputs)
            return []
        
        self.log_manager.info(
            f"Dynamic node {target_node.id}: splitting {len(inputs)} dynamic inputs into "
            f"{len(execution_units)} parallel units ({dynamic_config.type} mode)"
            + (f", with {len(static_inputs)} static inputs replicated to each" if static_inputs else "")
        )
        
        if dynamic_config.is_map():
            return self._execute_map(
                target_node, execution_units, dynamic_config, static_inputs
            )
        elif dynamic_config.is_tree():
            return self._execute_tree(
                target_node, execution_units, dynamic_config, static_inputs
            )
        else:
            raise ValueError(f"Unknown dynamic type: {dynamic_config.type}")
    
    def _execute_map(
        self,
        target_node: Node,
        execution_units: List[List[Message]],
        dynamic_config: DynamicEdgeConfig,
        static_inputs: Optional[List[Message]] = None,
    ) -> List[Message]:
        """Execute in Map mode (fan-out only).
        
        Args:
            target_node: Target node template
            execution_units: Split message units
            dynamic_config: Dynamic configuration
            static_inputs: Static inputs to copy to all units
            
        Returns:
            Flat list of all output messages
        """
        map_config = dynamic_config.as_map_config()
        max_parallel = map_config.max_parallel
        all_outputs: List[Message] = []
        static_inputs = static_inputs or []
        
        if len(execution_units) == 1:
            # Single unit - execute directly
            unit_inputs = list(static_inputs) + execution_units[0]
            outputs = self._execute_unit(target_node, unit_inputs, 0)
            all_outputs.extend(outputs)
        else:
            # Multiple units - parallel execution
            effective_workers = min(len(execution_units), max_parallel)
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=effective_workers) as executor:
                futures: Dict[concurrent.futures.Future, int] = {}
                
                for idx, unit in enumerate(execution_units):
                    unit_inputs = list(static_inputs) + unit
                    future = executor.submit(
                        self._execute_unit, target_node, unit_inputs, idx
                    )
                    futures[future] = idx
                
                results_by_idx: Dict[int, List[Message]] = {}
                for future in concurrent.futures.as_completed(futures):
                    idx = futures[future]
                    try:
                        result = future.result()
                        results_by_idx[idx] = result
                        self.log_manager.debug(
                            f"Dynamic edge -> {target_node.id}#{idx}: "
                            f"completed with {len(result)} outputs"
                        )
                    except Exception as e:
                        self.log_manager.error(
                            f"Dynamic edge -> {target_node.id}#{idx}: "
                            f"failed with error: {e}"
                        )
                        raise
                
                # Combine results in original order
                for idx in range(len(execution_units)):
                    if idx in results_by_idx:
                        all_outputs.extend(results_by_idx[idx])
        
        self.log_manager.info(
            f"Dynamic edge -> {target_node.id}: "
            f"Map completed with {len(all_outputs)} total outputs"
        )
        
        return all_outputs
    
    def _execute_tree(
        self,
        target_node: Node,
        execution_units: List[List[Message]],
        dynamic_config: DynamicEdgeConfig,
        static_inputs: Optional[List[Message]] = None,
    ) -> List[Message]:
        """Execute in Tree mode (fan-out + reduce).
        
        Args:
            target_node: Target node template
            execution_units: Split message units
            dynamic_config: Dynamic configuration
            static_inputs: Static inputs (used in first layer only)
            
        Returns:
            Single-element list with the final reduced result
        """
        tree_config = dynamic_config.as_tree_config()
        if tree_config is None:
            raise ValueError(f"Invalid tree configuration for edge -> {target_node.id}")
        
        group_size = tree_config.group_size
        max_parallel = tree_config.max_parallel
        static_inputs = static_inputs or []
        
        # Flatten execution units to individual messages
        current_messages: List[Message] = []
        for unit in execution_units:
            current_messages.extend(unit)
        
        if not current_messages:
            return []
        
        self.log_manager.info(
            f"Dynamic edge -> {target_node.id}: "
            f"Tree starting with {len(current_messages)} inputs, group_size={group_size}"
        )
        
        layer = 0
        is_first_layer = True
        
        # Reduction loop
        while len(current_messages) > 1:
            layer += 1
            
            # Group messages
            groups = group_messages(current_messages, group_size)
            
            self.log_manager.debug(
                f"Dynamic edge -> {target_node.id} layer {layer}: "
                f"processing {len(groups)} groups"
            )
            
            layer_outputs: List[Message] = []
            
            if len(groups) == 1:
                # Single group - execute directly
                group_inputs = groups[0]
                if is_first_layer:
                    group_inputs = list(static_inputs) + group_inputs
                outputs = self._execute_group(target_node, group_inputs, layer, 0)
                layer_outputs.extend(outputs)
            else:
                # Multiple groups - parallel execution
                effective_workers = min(len(groups), max_parallel)
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=effective_workers) as executor:
                    futures: Dict[concurrent.futures.Future, int] = {}
                    
                    for idx, group in enumerate(groups):
                        group_inputs = group
                        if is_first_layer:
                            group_inputs = list(static_inputs) + group_inputs
                        future = executor.submit(
                            self._execute_group, target_node, group_inputs, layer, idx
                        )
                        futures[future] = idx
                    
                    results_by_idx: Dict[int, List[Message]] = {}
                    for future in concurrent.futures.as_completed(futures):
                        idx = futures[future]
                        try:
                            result = future.result()
                            results_by_idx[idx] = result
                        except Exception as e:
                            self.log_manager.error(
                                f"Dynamic edge -> {target_node.id}#{layer}-{idx}: "
                                f"failed with error: {e}"
                            )
                            raise
                    
                    for idx in range(len(groups)):
                        if idx in results_by_idx:
                            layer_outputs.extend(results_by_idx[idx])
            
            self.log_manager.debug(
                f"Dynamic edge -> {target_node.id} layer {layer}: "
                f"produced {len(layer_outputs)} outputs"
            )
            
            current_messages = layer_outputs
            is_first_layer = False
            
            # Safety check
            if layer > 100:
                self.log_manager.error(
                    f"Dynamic edge -> {target_node.id}: exceeded maximum layers"
                )
                break
        
        self.log_manager.info(
            f"Dynamic edge -> {target_node.id}: "
            f"Tree completed after {layer} layers with {len(current_messages)} output(s)"
        )
        
        return current_messages
    
    def _execute_unit(
        self,
        node: Node,
        unit_inputs: List[Message],
        unit_index: int,
    ) -> List[Message]:
        """Execute a single map unit."""
        self.log_manager.debug(
            f"Dynamic edge -> {node.id}#{unit_index}: "
            f"executing with {len(unit_inputs)} inputs"
        )
        
        # Tag inputs with unit index
        # Clone messages first to avoid mutating shared inputs in parallel threads
        unit_inputs = [msg.clone() for msg in unit_inputs]
        for msg in unit_inputs:
            metadata = dict(msg.metadata)
            metadata["dynamic_edge_unit_index"] = unit_index
            msg.metadata = metadata
        
        # Execute using node executor
        outputs = self.node_executor_func(node, unit_inputs)
        
        # Tag outputs with unit index
        for msg in outputs:
            metadata = dict(msg.metadata)
            metadata["dynamic_edge_unit_index"] = unit_index
            msg.metadata = metadata
        
        return outputs
    
    def _execute_group(
        self,
        node: Node,
        group_inputs: List[Message],
        layer: int,
        group_index: int,
    ) -> List[Message]:
        """Execute a single tree group."""
        instance_id = f"{node.id}#{layer}-{group_index}"
        
        self.log_manager.debug(
            f"Dynamic edge -> {instance_id}: executing with {len(group_inputs)} inputs"
        )
        
        # Tag inputs
        # Clone messages first to avoid mutating shared inputs in parallel threads
        group_inputs = [msg.clone() for msg in group_inputs]
        for msg in group_inputs:
            metadata = dict(msg.metadata)
            metadata["dynamic_edge_tree_layer"] = layer
            metadata["dynamic_edge_tree_group"] = group_index
            msg.metadata = metadata
        
        # Execute
        outputs = self.node_executor_func(node, group_inputs)
        
        # Tag outputs
        for msg in outputs:
            metadata = dict(msg.metadata)
            metadata["dynamic_edge_tree_layer"] = layer
            metadata["dynamic_edge_tree_group"] = group_index
            metadata["dynamic_edge_instance_id"] = instance_id
            msg.metadata = metadata
            msg.role = MessageRole.USER  # Mark as user-generated
        
        return outputs
