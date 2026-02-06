"""Graph orchestration adapted to ChatDev design_0.4.0 workflows."""

import threading
from typing import Any, Callable, Dict, List, Optional

from runtime.node.agent.memory import MemoryBase, MemoryFactory, MemoryManager
from runtime.node.agent.thinking import ThinkingManagerBase, ThinkingManagerFactory
from entity.configs import Node, EdgeLink, AgentConfig, ConfigError
from entity.configs.edge import EdgeConditionConfig
from entity.configs.node.memory import SimpleMemoryConfig
from entity.messages import Message, MessageRole
from runtime.node.executor.base import ExecutionContext
from runtime.node.executor.factory import NodeExecutorFactory
from utils.logger import WorkflowLogger
from utils.exceptions import ValidationError, WorkflowExecutionError, WorkflowCancelledError
from utils.structured_logger import get_server_logger
from utils.human_prompt import (
    CliPromptChannel,
    HumanPromptService,
    resolve_prompt_channel,
)
from workflow.cycle_manager import CycleManager
from workflow.graph_context import GraphContext
from workflow.graph_manager import GraphManager
from workflow.executor.resource_manager import ResourceManager
from workflow.runtime import (
    RuntimeBuilder,
    ResultArchiver,
    DagExecutionStrategy,
    CycleExecutionStrategy,
    MajorityVoteStrategy,
)
from workflow.runtime.runtime_context import RuntimeContext
from runtime.edge.conditions import (
    ConditionFactoryContext,
    build_edge_condition_manager,
)
from runtime.edge.processors import (
    ProcessorFactoryContext as PayloadProcessorFactoryContext,
    build_edge_processor as build_edge_payload_processor,
)
from workflow.executor.dynamic_edge_executor import DynamicEdgeExecutor


# ------------------------------------------------------------------
#  Executor class (includes all Memory and Thinking logic)
# ------------------------------------------------------------------

class ExecutionError(RuntimeError):
    """Raised when the workflow graph cannot be executed."""


class GraphExecutor:
    """Executes ChatDev_new graph workflows with integrated memory and thinking management."""

    def __init__(
        self,
        graph: GraphContext,
        *,
        session_id: Optional[str] = None,
        workspace_hook_factory: Optional[Callable[[RuntimeContext], Any]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> None:
        """Initialize executor with graph context instance."""
        self.majority_result = None
        self.graph: GraphContext = graph
        self.outputs = {}
        self.logger = self._create_logger()
        self._cancel_event = cancel_event or threading.Event()
        self._cancel_reason: Optional[str] = None
        runtime = RuntimeBuilder(graph).build(logger=self.logger, session_id=session_id)
        if workspace_hook_factory:
            runtime.workspace_hook = workspace_hook_factory(runtime)
        self.runtime_context = runtime
        self.tool_manager = runtime.tool_manager
        self.function_manager = runtime.function_manager
        self.edge_processor_function_manager = runtime.edge_processor_function_manager
        self.log_manager = runtime.log_manager
        self.resource_manager = ResourceManager(self.log_manager)

        # Memory and Thinking management (moved from Graph)
        self.thinking_managers: Dict[str, ThinkingManagerBase] = {}
        self.global_memories: Dict[str, MemoryBase] = {}
        self.agent_memory_managers: Dict[str, MemoryManager] = {}

        # Token tracking
        self.token_tracker = runtime.token_tracker

        # Workspace roots
        self.code_workspace = runtime.code_workspace
        self.attachment_store = runtime.attachment_store
        
        # Cycle management
        self.cycle_manager: Optional[CycleManager] = None
        
        # Node executors (new strategy pattern implementation)
        self.__execution_context: Optional[ExecutionContext] = None
        self.node_executors: Dict[str, Any] = {}
        self._human_prompt_service: Optional[HumanPromptService] = None

        # for majority voting mode
        self.initial_task_messages: List[Message] = []

    def request_cancel(self, reason: Optional[str] = None) -> None:
        """Signal the executor to stop as soon as possible."""
        if reason:
            self._cancel_reason = reason
        elif not self._cancel_reason:
            self._cancel_reason = "Workflow execution cancelled"
        self._cancel_event.set()
        self.logger.info(f"Cancellation requested for workflow {self.graph.name}")

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def _raise_if_cancelled(self) -> None:
        if self.is_cancelled():
            message = self._cancel_reason or "Workflow execution cancelled"
            raise WorkflowCancelledError(message, workflow_id=self.graph.name)

    def _create_logger(self) -> WorkflowLogger:
        """Create and return a logger instance."""
        return WorkflowLogger(self.graph.name, self.graph.log_level)

    @classmethod
    def execute_graph(
        cls,
        graph: GraphContext,
        task_prompt: Any,
        *,
        cancel_event: Optional[threading.Event] = None,
    ) -> "GraphExecutor":
        """Convenience method to execute a graph with a task prompt."""
        executor = cls(graph, cancel_event=cancel_event)
        executor._execute(task_prompt)
        return executor

    def _execute(self, task_prompt: Any):
        self._raise_if_cancelled()
        results = self.run(task_prompt)
        self.graph.record(results)

    def _build_memories_and_thinking(self) -> None:
        """Initialize all memory and thinking managers before execution."""
        self._build_global_memories()
        self._build_thinking_managers()
        self._build_agent_memories()
        self._build_node_executors()

    def _build_global_memories(self) -> None:
        """Build global memories from config."""
        memory_config = self.graph.config.get_memory_config()
        if not memory_config:
            return

        for store in memory_config:
            if store.name in self.global_memories:
                error_msg = f"Duplicated memory name detected: {store.name}"
                self.log_manager.error(error_msg)
                raise ValidationError(error_msg, details={"memory_name": store.name})

            simple_cfg = store.as_config(SimpleMemoryConfig)
            if simple_cfg and (not simple_cfg.memory_path or simple_cfg.memory_path == "auto"):
                path = self.graph.directory / f"memory_{store.name}.json"
                simple_cfg.memory_path = str(path)

            try:
                memory_instance = MemoryFactory.create_memory(store)
                self.global_memories[store.name] = memory_instance
                memory_instance.load()
                self.log_manager.info(
                    f"Global memory '{store.name}' built successfully",
                    details={"memory_name": store.name},
                )
            except Exception as e:
                error_msg = f"Failed to create memory '{store.name}': {str(e)}"
                self.log_manager.error(error_msg, details={"memory_name": store.name})
                logger = get_server_logger()
                logger.log_exception(e, error_msg, memory_name=store.name)
                raise WorkflowExecutionError(error_msg, details={"memory_name": store.name})

    def _build_thinking_managers(self) -> None:
        """Build thinking managers for nodes that require them."""
        for node_id, node in self.graph.nodes.items():
            agent_config = node.as_config(AgentConfig)
            if agent_config and agent_config.thinking:
                self.thinking_managers[node_id] = ThinkingManagerFactory.get_thinking_manager(
                    agent_config.thinking
                )

    def _build_agent_memories(self) -> None:
        """Build memory managers for agent nodes referencing global stores."""
        for node_id, node in self.graph.nodes.items():
            agent_config = node.as_config(AgentConfig)
            if not (agent_config and agent_config.memories):
                continue
            try:
                self.agent_memory_managers[node_id] = MemoryManager(agent_config.memories, self.global_memories)
                self.log_manager.info(
                    f"Memory manager built for node {node_id}",
                    node_id=node_id,
                    details={"memory_refs": [mem.name for mem in agent_config.memories]},
                )
            except Exception as e:
                error_msg = f"Failed to create memory manager for node {node_id}: {str(e)}"
                self.log_manager.error(error_msg, node_id=node_id)
                logger = get_server_logger()
                logger.log_exception(e, error_msg, node_id=node_id)
                raise WorkflowExecutionError(error_msg, node_id=node_id)

    def _get_execution_context(self) -> ExecutionContext:
        if self.__execution_context is None:
            global_state = dict(self.runtime_context.global_state)
            global_state.setdefault("attachment_store", self.attachment_store)
            prompt_service = self._ensure_human_prompt_service()
            global_state.setdefault("human_prompt", prompt_service)
            self.__execution_context = ExecutionContext(
                tool_manager=self.tool_manager,
                function_manager=self.function_manager,
                log_manager=self.log_manager,
                memory_managers=self.agent_memory_managers,
                thinking_managers=self.thinking_managers,
                token_tracker=self.token_tracker,
                global_state=global_state,
                workspace_hook=self.runtime_context.workspace_hook,
                human_prompt_service=prompt_service,
                cancel_event=self._cancel_event,
            )
        return self.__execution_context
    
    def _build_node_executors(self) -> None:
        """Build node executors using strategy pattern."""

        # Create node executors
        self.node_executors = NodeExecutorFactory.create_executors(
            self._get_execution_context(),
            self.graph.subgraphs
        )

    def _ensure_human_prompt_service(self) -> HumanPromptService:
        if self._human_prompt_service:
            return self._human_prompt_service

        channel = resolve_prompt_channel(self.runtime_context.workspace_hook)
        if channel is None:
            channel = CliPromptChannel()

        self._human_prompt_service = HumanPromptService(
            log_manager=self.log_manager,
            channel=channel,
            session_id=self.runtime_context.session_id,
        )
        return self._human_prompt_service

    def _save_memories(self) -> None:
        """Save all memories after execution."""
        for memory in self.global_memories.values():
            memory.save()

    def run(self, task_prompt: Any) -> Dict[str, Any]:
        """Execute the graph based on topological layers structure or cycle-aware execution."""
        self._raise_if_cancelled()
        graph_manager = GraphManager(self.graph)
        try:
            graph_manager.build_graph()
        except ConfigError as err:
            error_msg = f"Graph configuration error: {str(err)}"
            self.log_manager.logger.error(error_msg)
            raise err

        self._prepare_edge_conditions()

        if not self.graph.layers:
            raise ExecutionError("Graph not built. Call GraphManager.build_graph() first.")

        # Record workflow start
        self.log_manager.record_workflow_start(self.graph.metadata)

        # Initialize memory and thinking before execution
        self._build_memories_and_thinking()

        # Initialize cycle manager if graph has cycles
        if self.graph.has_cycles:
            self.cycle_manager = graph_manager.get_cycle_manager()

        self.initial_task_messages = [msg.clone() for msg in self._normalize_task_input(task_prompt)]

        start_node_ids = set(self.graph.start_nodes)

        # Reset all trigger states and initialize configured start nodes
        for node_id, node in self.graph.nodes.items():
            self._raise_if_cancelled()
            node.reset_triggers()
            if node_id in start_node_ids:
                node.start_triggered = True
                node.clear_input()
                for message in self.initial_task_messages:
                    node.append_input(message.clone())

        # Execute based on graph type (using strategy objects)
        if self.graph.is_majority_voting:
            strategy = MajorityVoteStrategy(
                log_manager=self.log_manager,
                nodes=self.graph.nodes,
                initial_messages=self.initial_task_messages,
                execute_node_func=self._execute_node,
                payload_to_text_func=self._payload_to_text,
            )
            self.majority_result = strategy.run()
        elif self.graph.has_cycles:
            strategy = CycleExecutionStrategy(
                log_manager=self.log_manager,
                nodes=self.graph.nodes,
                cycle_execution_order=self.graph.cycle_execution_order,
                cycle_manager=self.cycle_manager,
                execute_node_func=self._execute_node,
            )
            strategy.run()
        else:
            strategy = DagExecutionStrategy(
                log_manager=self.log_manager,
                nodes=self.graph.nodes,
                layers=self.graph.layers,
                execute_node_func=self._execute_node,
            )
            strategy.run()

        self._raise_if_cancelled()

        # Collect final outputs and save memories
        self._collect_all_outputs()
        
        # Get the final result according to the new logic
        final_result = self.get_final_output()
        
        self._save_memories()

        # Export runtime artifacts
        archiver = ResultArchiver(self.graph, self.log_manager, self.token_tracker)
        archiver.export(final_result)

        return self.outputs
    
    def _prepare_edge_conditions(self) -> None:
        """Compile registered edge condition types into callable evaluators."""
        context = ConditionFactoryContext(function_manager=self.function_manager, log_manager=self.log_manager)
        processor_context = PayloadProcessorFactoryContext(
            function_manager=self.edge_processor_function_manager,
            log_manager=self.log_manager,
        )
        for node in self.graph.nodes.values():
            for edge_link in node.iter_outgoing_edges():
                condition_config = edge_link.condition_config
                if not isinstance(condition_config, EdgeConditionConfig):
                    raw_value = edge_link.config.get("condition", "true")
                    condition_config = EdgeConditionConfig.from_dict(raw_value, path=f"{node.path}.edges")
                    edge_link.condition_config = condition_config
                try:
                    manager = build_edge_condition_manager(condition_config, context, self._get_execution_context())
                except Exception as exc:  # pragma: no cover - defensive logging
                    error_msg = f"Failed to prepare condition '{condition_config.display_label()}': {exc}"
                    self.log_manager.error(error_msg)
                    logger = get_server_logger()
                    logger.log_exception(exc, error_msg, condition_type=condition_config.type)
                    raise WorkflowExecutionError(error_msg) from exc
                edge_link.condition_manager = manager
                label = getattr(manager, "label", None) or condition_config.display_label()
                metadata = getattr(manager, "metadata", {}) or {}
                edge_link.condition = label
                edge_link.condition_metadata = metadata
                edge_link.condition_type = condition_config.type

                process_config = edge_link.process_config
                if process_config:
                    try:
                        processor = build_edge_payload_processor(process_config, processor_context)
                    except Exception as exc:  # pragma: no cover
                        error_msg = (
                            f"Failed to prepare processor '{process_config.display_label()}': {exc}"
                        )
                        self.log_manager.error(error_msg)
                        logger = get_server_logger()
                        logger.log_exception(exc, error_msg, processor_type=process_config.type)
                        raise WorkflowExecutionError(error_msg) from exc
                    edge_link.payload_processor = processor
                    edge_link.process_type = process_config.type
                    edge_link.process_metadata = getattr(processor, "metadata", {}) or {}
                    processor_label = getattr(processor, "label", None)
                    if processor_label:
                        edge_link.config["process_label"] = processor_label
                else:
                    edge_link.payload_processor = None
                    edge_link.process_metadata = {}
                    edge_link.process_type = None

    def _process_edge_output(
            self,
            edge_link: EdgeLink,
            source_result: Message,
            from_node: Node
    ) -> None:
        """Perform edge instantiation behavior.
        
        Edges with dynamic configuration still pass messages normally to the target
        node's input queue. Dynamic execution happens when the target node executes.
        """
        # All edges (including dynamic ones) use standard processing to pass messages
        # Dynamic execution will happen in _execute_node when the target node runs
        
        # Standard edge processing (no dynamic config)
        manager = edge_link.condition_manager
        if manager is None:
            raise WorkflowExecutionError(
                f"Edge {from_node.id}->{edge_link.target.id} is missing a condition manager"
            )
        try:
            manager.process(
                edge_link,
                source_result,
                from_node,
                self.log_manager,
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            error_msg = (
                f"Edge manager failed for {from_node.id} -> {edge_link.target.id}: {exc}"
            )
            self.log_manager.error(
                error_msg,
                details={
                    "condition_type": edge_link.condition_type,
                    "condition_metadata": edge_link.condition_metadata,
                },
            )
            logger = get_server_logger()
            logger.log_exception(
                exc,
                error_msg,
                condition_type=edge_link.condition_type,
                condition_metadata=edge_link.condition_metadata,
            )
            raise WorkflowExecutionError(error_msg) from exc


    def _get_dynamic_config_for_node(self, node: Node):
        """Get the dynamic configuration for a node from its incoming edges.
        
        If multiple incoming edges have dynamic config, they must be identical
        (same type and parameters). Otherwise raises an error.
        
        Returns the dynamic config if found, or None.
        """
        from entity.configs.edge.dynamic_edge_config import DynamicEdgeConfig
        
        found_configs = []  # List of (source_node_id, dynamic_config)
        
        for predecessor in node.predecessors:
            for edge_link in predecessor.iter_outgoing_edges():
                if edge_link.target is node and edge_link.dynamic_config is not None:
                    found_configs.append((predecessor.id, edge_link.dynamic_config))
        
        if not found_configs:
            return None
        
        if len(found_configs) == 1:
            return found_configs[0][1]
        
        # Multiple dynamic configs found - verify they are consistent
        first_source, first_config = found_configs[0]
        for source_id, config in found_configs[1:]:
            # Check type consistency
            if config.type != first_config.type:
                raise WorkflowExecutionError(
                    f"Node '{node.id}' has inconsistent dynamic configurations on incoming edges: "
                    f"edge from '{first_source}' has type '{first_config.type}', "
                    f"but edge from '{source_id}' has type '{config.type}'. "
                    f"All dynamic edges to the same node must use the same configuration."
                )
            # Check split config consistency
            if (config.split.type != first_config.split.type or
                config.split.pattern != first_config.split.pattern or
                config.split.json_path != first_config.split.json_path):
                raise WorkflowExecutionError(
                    f"Node '{node.id}' has inconsistent split configurations on incoming edges: "
                    f"edges from '{first_source}' and '{source_id}' have different split settings. "
                    f"All dynamic edges to the same node must use the same configuration."
                )
            # Check mode-specific config consistency
            if config.max_parallel != first_config.max_parallel:
                raise WorkflowExecutionError(
                    f"Node '{node.id}' has inconsistent max_parallel on incoming edges: "
                    f"edge from '{first_source}' has max_parallel={first_config.max_parallel}, "
                    f"but edge from '{source_id}' has max_parallel={config.max_parallel}."
                )
            if config.type == "tree" and config.group_size != first_config.group_size:
                raise WorkflowExecutionError(
                    f"Node '{node.id}' has inconsistent group_size on incoming edges: "
                    f"edge from '{first_source}' has group_size={first_config.group_size}, "
                    f"but edge from '{source_id}' has group_size={config.group_size}."
                )
        
        return first_config

    def _execute_with_dynamic_config(
        self,
        node: Node,
        inputs: List[Message],
        dynamic_config,
    ) -> List[Message]:
        """Execute a node with dynamic configuration from incoming edges.
        
        Args:
            node: Target node to execute
            inputs: All input messages collected for this node
            dynamic_config: Dynamic configuration from the incoming edge
            
        Returns:
            Output messages from dynamic execution
        """
        # Separate inputs: dynamic edge inputs vs static (non-dynamic) edge inputs
        # Dynamic edge inputs will be split, static inputs will be replicated to all units
        dynamic_inputs: List[Message] = []
        static_inputs: List[Message] = []
        
        for msg in inputs:
            if msg.metadata.get("_from_dynamic_edge"):
                dynamic_inputs.append(msg)
            else:
                static_inputs.append(msg)
        
        self.log_manager.info(
            f"Executing node {node.id} with edge dynamic config ({dynamic_config.type} mode): "
            f"{len(dynamic_inputs)} dynamic inputs, {len(static_inputs)} static inputs"
        )
        
        # Create node executor function
        def node_executor_func(n: Node, inp: List[Message]) -> List[Message]:
            return self._process_result(n, inp)
        
        # Execute with dynamic edge executor
        dynamic_executor = DynamicEdgeExecutor(self.log_manager, node_executor_func)
        
        # Pass dynamic inputs for splitting, static inputs for replication
        return dynamic_executor.execute_from_inputs(
            node, dynamic_inputs, dynamic_config, static_inputs=static_inputs
        )

    def _execute_node(self, node: Node) -> None:
        """Execute a single node."""
        self._raise_if_cancelled()
        with self.resource_manager.guard_node(node):
            input_results = node.input

            # Clear incoming triggers so future iterations wait for fresh signals
            node.reset_triggers()

            serialized_inputs = [message.to_dict(include_data=False) for message in input_results]

            # Record node start
            self.log_manager.record_node_start(node.id, serialized_inputs, node.node_type, {
                "input_count": len(input_results),
                "predecessors": [p.id for p in node.predecessors],
                "successors": [s.id for s in node.successors]
            })

            self.log_manager.debug(f"Processing {len(input_results)} inputs together for node {node.id}")

            # Check if any incoming edge has dynamic configuration
            dynamic_config = self._get_dynamic_config_for_node(node)
            
            # Process all inputs together in a single executor call
            with self.log_manager.node_timer(node.id):
                if dynamic_config is not None:
                    raw_outputs = self._execute_with_dynamic_config(node, input_results, dynamic_config)
                else:
                    raw_outputs = self._process_result(node, input_results)

            # Process all output messages
            output_messages: List[Message] = []
            for raw_output in raw_outputs:
                msg = self._ensure_source_output(raw_output, node.id)
                node.append_output(msg)
                output_messages.append(msg)

            # Use first output for context trace handling (backward compat)
            unified_output = output_messages[0] if output_messages else None

            context_trace_payload = None
            context_restored = False
            if unified_output is not None and isinstance(unified_output.metadata, dict):
                context_trace_payload = unified_output.metadata.get("context_trace")
            if node.context_window != 0 and context_trace_payload:
                context_restored = self._restore_context_trace(node, context_trace_payload)

            if node.context_window != -1:
                preserved_inputs = node.clear_input(preserve_kept=True, context_window=node.context_window)
                if preserved_inputs:
                    self.log_manager.debug(
                        f"Node {node.id} cleaned up its input context after execution (preserved {preserved_inputs} keep-marked inputs)"
                    )
                else:
                    self.log_manager.debug(
                        f"Node {node.id} cleaned up its input context after execution"
                    )

            if output_messages:
                self.log_manager.debug(
                    f"Node {node.id} processed {len(input_results)} inputs into {len(output_messages)} output(s)"
                )
            else:
                self.log_manager.debug(
                    f"Node {node.id} produced no output; downstream edges suppressed"
                )

            # Record node end
            output_text = ""
            if output_messages:
                if len(output_messages) == 1:
                    output_text = unified_output.text_content()
                else:
                    for idx, msg in enumerate(output_messages):
                        output_text += f"===== OUTPUT {idx} =====\n\n" + msg.text_content() + "\n\n"
                output_role = unified_output.role.value
                output_source = unified_output.metadata.get("source")
            else:
                output_text = ""
                output_role = "none"
                output_source = None

            self.log_manager.record_node_end(node.id, output_text if node.log_output else "", {
                "output_size": len(output_text),
                "output_count": len(output_messages),
                "output_role": output_role,
                "output_source": output_source
            })

            # Pass results to successor nodes via edges
            # For each output message, process all edges
            for output_msg in output_messages:
                for edge_link in node.iter_outgoing_edges():
                    self._process_edge_output(edge_link, output_msg, node)
            
            if output_messages and node.context_window != 0 and not context_restored:
                # Use first output for pseudo edge
                pseudo_condition = EdgeConditionConfig.from_dict("true", path=f"{node.path}.pseudo_edge")
                pseudo_link = EdgeLink(target=node, trigger=False)
                pseudo_link.condition_config = pseudo_condition
                pseudo_context = ConditionFactoryContext(
                    function_manager=self.function_manager,
                    log_manager=self.log_manager,
                )
                pseudo_link.condition_manager = build_edge_condition_manager(pseudo_condition, pseudo_context, self._get_execution_context())
                pseudo_link.condition = pseudo_condition.display_label()
                pseudo_link.condition_type = pseudo_condition.type
                for output_msg in output_messages:
                    self._process_edge_output(pseudo_link, output_msg, node)

    def _process_result(self, node: Node, input_payload: List[Message]) -> List[Message]:
        """Process a single input result using strategy pattern executors.

        This method delegates to specific node executors based on node type.
        Returns a list of messages (maybe empty if node suppresses output).
        """
        if not self.node_executors:
            raise RuntimeError("Node executors not initialized. Call _build_memories_and_thinking() first.")
        
        if node.type not in self.node_executors:
            raise ValueError(f"Unsupported node type: {node.type}")
        
        executor = self.node_executors[node.type]
        hook = self.runtime_context.workspace_hook
        workspace = self.runtime_context.code_workspace
        if hook:
            try:
                hook.before_node(node, workspace)
            except Exception:
                self.log_manager.warning("workspace hook before_node failed for %s", node.id)
        success = False
        try:
            result = executor.execute(node, input_payload)
            success = True
            return result
        finally:
            if hook:
                try:
                    hook.after_node(node, workspace, success=success)
                except Exception:
                    self.log_manager.warning("workspace hook after_node failed for %s", node.id)


    def _collect_all_outputs(self) -> None:
        """Collect final outputs from all nodes, especially sink nodes."""
        all_outputs = {}

        # For majority voting, we might want to collect differently
        if self.graph.is_majority_voting:
            # In majority voting mode, collect all outputs and the final majority result
            for node_id, node in self.graph.nodes.items():
                if node.output:
                    node_output = {
                        "node_id": node_id,
                        "node_type": node.node_type,
                        "predecessors_num": len(node.predecessors),
                        "successors_num": len(node.successors),
                        "results": [self._serialize_output_payload(item) for item in node.output]
                    }
                    all_outputs[f"node_{node_id}"] = node_output
            
            # Add the majority result
            if hasattr(self, 'majority_result'):
                all_outputs["majority_result"] = self.majority_result
        else:
            # Collect outputs from all nodes normally
            for node_id, node in self.graph.nodes.items():
                if node.output:
                    node_output = {
                        "node_id": node_id,
                        "node_type": node.node_type,
                        "predecessors_num": len(node.predecessors),
                        "successors_num": len(node.successors),
                        "results": [self._serialize_output_payload(item) for item in node.output]
                    }
                    all_outputs[f"node_{node_id}"] = node_output

        # Add graph summary
        all_outputs["graph_summary"] = {
            "total_nodes": len(self.graph.nodes),
            "total_edges": len(self.graph.edges),
            "total_transmissions": len([k for k in self.outputs.keys() if "->" in k]),
            "layers": len(self.graph.layers),
            "execution_completed": True,
            "is_majority_voting": self.graph.is_majority_voting
        }

        self.outputs.update(all_outputs)

    def get_final_output(self) -> str:
        final_message = self.get_final_output_message()
        return final_message.text_content() if final_message else ""

    def get_final_output_message(self) -> Message | None:
        if self.graph.is_majority_voting:
            if self.majority_result is None:
                return None
            if isinstance(self.majority_result, Message):
                return self.majority_result.clone()
            return self._create_message(MessageRole.ASSISTANT, str(self.majority_result), "MAJORITY_VOTE")

        final_node = self._get_final_node()
        if not final_node:
            return None
        if final_node.output:
            value = final_node.output[-1]
            if isinstance(value, Message):
                return value.clone()
            return self._create_message(MessageRole.ASSISTANT, str(value), final_node.id)
        return None

    def get_final_output_messages(self) -> List[Message]:
        """Return all messages from the final node."""
        if self.graph.is_majority_voting:
            msg = self.get_final_output_message()
            return [msg] if msg else []

        final_node = self._get_final_node()
        if not final_node:
            return []
        
        results = []
        for value in final_node.output:
            if isinstance(value, Message):
                results.append(value.clone())
            else:
                results.append(self._create_message(MessageRole.ASSISTANT, str(value), final_node.id))
        return results

    def _get_final_node(self) -> Node:
        """Return the explicitly configured end node, or sink node as fallback."""
        end_node_ids = self.graph.config.definition.end_nodes

        if end_node_ids:
            for end_node_id in end_node_ids:
                if end_node_id in self.graph.nodes:
                    node = self.graph.nodes[end_node_id]
                    # Check if node has output
                    if node.output:
                        return node

        # Fallback to default behavior - return sink node
        sink_node = [node for node in self.graph.nodes.values() if not node.successors]
        return sink_node[0] if sink_node else None

    def _restore_context_trace(self, node: Node, trace_payload: Any) -> bool:
        if not isinstance(trace_payload, list):
            return False

        restored = 0
        for entry in trace_payload:
            if not isinstance(entry, dict):
                continue
            try:
                message = Message.from_dict(entry)
                if message.role not in [MessageRole.USER, MessageRole.ASSISTANT]:
                    continue
            except Exception as exc:
                self.log_manager.warning(
                    f"Failed to deserialize context trace for node {node.id}: {exc}"
                )
                continue
            node.append_input(self._ensure_source(message, node.id))
            restored += 1

        if restored:
            self.log_manager.debug(
                f"Node {node.id} preserved {restored} messages from its tool execution trace"
            )
        return restored > 0

    def _payload_to_text(self, payload: Any) -> str:
        if isinstance(payload, Message):
            return payload.text_content()
        if payload is None:
            return ""
        return str(payload)

    def _serialize_output_payload(self, payload: Any) -> Any:
        if isinstance(payload, Message):
            return {"type": "message", "payload": payload.to_dict(include_data=False)}
        return {"type": "text", "payload": str(payload)}

    def _normalize_task_input(self, raw_input: Any) -> List[Message]:
        if isinstance(raw_input, list):
            messages: List[Message] = []
            for item in raw_input:
                if isinstance(item, Message):
                    messages.append(self._ensure_source(item, "TASK"))
                elif isinstance(item, str):
                    messages.append(self._create_message(MessageRole.USER, item, "TASK"))
            return messages or [self._create_message(MessageRole.USER, "", "TASK")]
        if isinstance(raw_input, Message):
            return [self._ensure_source(raw_input, "TASK")]
        return [self._create_message(MessageRole.USER, str(raw_input), "TASK")]

    def _ensure_source(self, message: Message, default_source: str) -> Message:
        cloned = message.clone()
        metadata = dict(cloned.metadata)
        metadata.setdefault("source", default_source)
        cloned.metadata = metadata
        return cloned

    def _create_message(self, role: MessageRole, content: str, source: str) -> Message:
        return Message(role=role, content=content, metadata={"source": source})

    def _ensure_source_output(self, message: Any, node_id: str) -> Message:
        if not isinstance(message, Message):
            return self._create_message(MessageRole.ASSISTANT, str(message), node_id)
        cloned = message.clone()
        metadata = dict(message.metadata)
        metadata.setdefault("source", node_id)
        cloned.metadata = metadata
        return cloned
