"""Agent node executor.

Responsible for running agent nodes, including
- memory retrieval
- thinking workflows
- agent invocation
- tool calling
"""

import asyncio
import base64
import json
import traceback
from typing import Any, Callable, Dict, List, Optional, Sequence

from entity.configs import Node
from entity.configs.node.agent import AgentConfig, AgentRetryConfig
from entity.enums import CallStage, AgentExecFlowStage, AgentInputMode
from entity.messages import (
    AttachmentRef,
    FunctionCallOutputEvent,
    Message,
    MessageBlock,
    MessageRole,
    ToolCallPayload,
)
from entity.tool_spec import ToolSpec
from runtime.node.executor.base import NodeExecutor
from runtime.node.agent.memory.memory_base import (
    MemoryContentSnapshot,
    MemoryRetrievalResult,
    MemoryWritePayload,
)
from runtime.node.agent import ThinkingPayload
from runtime.node.agent import ModelProvider, ProviderRegistry, ModelResponse
from runtime.node.agent.skills import AgentSkillManager
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_random_exponential

CONTEXT_COMPRESSION_MAX_MESSAGES = 8
CONTEXT_COMPRESSION_MAX_CHARS = 6000
CONTEXT_COMPRESSION_KEEP_RECENT = 4
CONTEXT_COMPRESSION_PREVIEW_CHARS = 220


class AgentNodeExecutor(NodeExecutor):
    """Executor that runs agent nodes."""
    
    def execute(self, node: Node, inputs: List[Message]) -> List[Message]:
        """Execute an agent node.
        
        Args:
            node: Agent node definition
            inputs: Input messages collected from upstream nodes
        
        Returns:
            Agent output messages
        """
        self._ensure_not_cancelled()
        if node.node_type != "agent":
            raise ValueError(f"Node {node.id} is not an agent node")
        
        agent_config = node.as_config(AgentConfig)
        if not agent_config:
            raise ValueError(f"Node {node.id} missing agent config")
        
        try:
            self._current_node_id = node.id
            provider_class = ProviderRegistry.get_provider(agent_config.provider)
            if not provider_class:
                raise ValueError(f"Provider '{agent_config.provider}' not found")

            agent_config.token_tracker = self.context.get_token_tracker()
            agent_config.node_id = node.id

            conversation_inputs = self._compress_inputs_for_context(node, inputs)
            input_data = self._inputs_to_text(conversation_inputs)
            input_payload = self._build_thinking_payload_from_inputs(inputs, input_data)
            memory_query_snapshot = self._build_memory_query_snapshot(inputs, input_data)
            input_mode = agent_config.input_mode or AgentInputMode.PROMPT
            external_tool_specs = self.tool_manager.get_tool_specs(agent_config.tooling)
            skill_manager = self._build_skill_manager(node, agent_config, external_tool_specs)

            provider = provider_class(agent_config)
            client = provider.create_client()

            if input_mode is AgentInputMode.PROMPT:
                conversation = self._prepare_prompt_messages(node, input_data, skill_manager)
            else:
                conversation = self._prepare_message_conversation(node, conversation_inputs, skill_manager)
            call_options = self._prepare_call_options(node)
            tool_specs = self._merge_skill_tool_specs(external_tool_specs, skill_manager)

            agent_invoker = self._build_agent_invoker(
                provider,
                client,
                call_options,
                tool_specs,
                node,
            )

            if agent_config.thinking:
                self._apply_pre_generation_thinking(
                    node,
                    conversation,
                    input_payload,
                    memory_query_snapshot,
                    AgentExecFlowStage.PRE_GEN_THINKING_STAGE,
                    agent_invoker,
                    input_mode,
                )

            self._apply_memory_retrieval(
                node,
                conversation,
                memory_query_snapshot,
                AgentExecFlowStage.GEN_STAGE,
                input_mode,
            )

            timeline = self._build_initial_timeline(conversation)
            response_obj = self._invoke_provider(
                provider,
                client,
                conversation,
                timeline,
                call_options,
                tool_specs,
                node,
            )

            if response_obj.has_tool_calls():
                response_message = self._handle_tool_calls(
                    node,
                    provider,
                    client,
                    conversation,
                    timeline,
                    call_options,
                    response_obj,
                    tool_specs,
                    skill_manager,
                )
            else:
                response_message = response_obj.message

            self._persist_message_attachments(response_message, node.id)

            final_message: Message | str = response_message

            if agent_config.thinking:
                gen_payload = self._build_thinking_payload_from_message(final_message, source="model_output")
                final_message = self._apply_post_generation_thinking(
                    node,
                    conversation,
                    memory_query_snapshot,
                    input_payload,
                    gen_payload,
                    AgentExecFlowStage.POST_GEN_THINKING_STAGE,
                    agent_invoker,
                    input_mode,
                )

            self._update_memory(node, input_data, inputs, final_message)

            if isinstance(final_message, Message):
                return [self._clone_with_source(final_message, node.id)]
            return [self._build_message(
                role=MessageRole.ASSISTANT,
                content=final_message,
                source=node.id,
            )]
            
        except Exception as e:
            traceback.print_exc()
            error_msg = f"[Node: {node.id}] Error calling model: {str(e)}"
            self.log_manager.error(error_msg)
            return [self._build_message(
                role=MessageRole.ASSISTANT,
                content=f"Error calling model {node.model_name}: {str(e)}\n\nOriginal input: {input_data[:200]}...",
                source=node.id,
            )]
        finally:
            self._current_node_id = None
    
    def _prepare_prompt_messages(
        self,
        node: Node,
        input_data: str,
        skill_manager: AgentSkillManager | None,
    ) -> List[Message]:
        """Prepare the prompt-style message sequence."""
        messages: List[Message] = []

        system_prompt = self._build_system_prompt(node, skill_manager)
        if system_prompt:
            messages.append(Message(role=MessageRole.SYSTEM, content=system_prompt))

        try:
            if isinstance(input_data, str):
                clean_input = input_data.encode("utf-8", errors="ignore").decode("utf-8")
            else:
                clean_input = str(input_data)
        except Exception as encoding_error:
            self.log_manager.error(f"[Node: {node.id}] Encoding error: {encoding_error}")
            clean_input = str(input_data)

        messages.append(Message(role=MessageRole.USER, content=clean_input))
        return messages

    def _prepare_message_conversation(
        self,
        node: Node,
        inputs: List[Message],
        skill_manager: AgentSkillManager | None,
    ) -> List[Message]:
        messages: List[Message] = []

        system_prompt = self._build_system_prompt(node, skill_manager)
        if system_prompt:
            messages.append(Message(role=MessageRole.SYSTEM, content=system_prompt))

        normalized_inputs = self._coerce_inputs_to_messages(inputs)
        if normalized_inputs:
            messages.extend(normalized_inputs)
        else:
            messages.append(Message(role=MessageRole.USER, content=""))

        return messages
    
    def _prepare_call_options(self, node: Node) -> Dict[str, Any]:
        """Prepare model call options (excluding conversation messages)."""
        call_options: Dict[str, Any] = {}

        model = node.as_config(AgentConfig)
        if not model:
            raise ValueError(f"Node {node.id} missing model config")

        if model.params:
            call_options.update(model.params)

        # call_options.setdefault("temperature", 0.7)
        # call_options.setdefault("max_tokens", 4096)
        return call_options

    def _build_skill_manager(
        self,
        node: Node,
        agent_config: AgentConfig,
        external_tool_specs: List[ToolSpec],
    ) -> AgentSkillManager | None:
        skills_config = agent_config.skills
        if not skills_config or not skills_config.enabled:
            return None

        manager = AgentSkillManager(
            allow=skills_config.allow,
            available_tool_names=[spec.name for spec in external_tool_specs],
            warning_reporter=lambda message: self.log_manager.warning(message, node_id=node.id),
        )
        return manager

    def _build_system_prompt(self, node: Node, skill_manager: AgentSkillManager | None) -> str | None:
        parts: List[str] = []
        if node.role:
            parts.append(node.role)

        replay_context = self.context.global_state.get("replay_context") or {}
        replay_context_text = str(replay_context.get("text") or "").strip()
        retained_tasks = replay_context.get("retained_tasks") or []
        if replay_context_text and retained_tasks:
            parts.append(
                "\n".join(
                    [
                        "Replay context is active for this run.",
                        "Treat the retained task outputs below as previously approved context unless new evidence clearly invalidates them.",
                        replay_context_text,
                    ]
                )
            )

        if skill_manager is not None:
            skills_xml = skill_manager.build_available_skills_xml()
            if skills_xml:
                parts.append(
                    "\n".join(
                        [
                            "You have access to Agent Skills.",
                            "Use `activate_skill` to load the full SKILL.md instructions for a relevant skill before following it.",
                            "Use `read_skill_file` to read supporting files from that skill directory when the instructions reference them.",
                            "Do not assume a skill's contents until you load it.",
                            skills_xml,
                        ]
                    )
                )
            else:
                warning_lines = skill_manager.discovery_warnings()
                warning_text = "\n".join(f"- {warning}" for warning in warning_lines[:5])
                parts.append(
                    "\n".join(
                        [
                            "Agent Skills are enabled for this node, but no compatible skills are currently available.",
                            "Do not claim to use or load any skill unless it appears in <available_skills>.",
                            warning_text,
                        ]
                    ).strip()
                )

        if not parts:
            return None
        return "\n\n".join(part for part in parts if part)

    def _merge_skill_tool_specs(
        self,
        tool_specs: List[ToolSpec],
        skill_manager: AgentSkillManager | None,
    ) -> List[ToolSpec]:
        if skill_manager is None:
            return tool_specs

        merged = list(tool_specs)
        existing_names = {spec.name for spec in merged}
        for spec in skill_manager.build_tool_specs():
            if spec.name in existing_names:
                raise ValueError(f"Tool name '{spec.name}' conflicts with a built-in skill tool")
            existing_names.add(spec.name)
            merged.append(spec)
        return merged

    def _build_agent_invoker(
        self,
        provider: ModelProvider,
        client: Any,
        base_call_options: Dict[str, Any],
        default_tool_specs: List[ToolSpec],
        node: Node,
    ) -> Callable[[List[Message]], Message]:
        """Create a callable that other components can use to invoke the model."""

        def invoke(
            conversation: List[Message],
            *,
            tools: Optional[List[ToolSpec]] = None,
            **overrides: Any,
        ) -> Message:
            call_options = dict(base_call_options)
            call_options.update(overrides)
            timeline = self._build_initial_timeline(conversation)
            response = self._invoke_provider(
                provider,
                client,
                conversation,
                timeline,
                call_options,
                tools if tools is not None else default_tool_specs,
                node,
            )
            return response.message

        return invoke

    def _invoke_provider(
        self,
        provider: ModelProvider,
        client: Any,
        conversation: List[Message],
        timeline: List[Any],
        call_options: Dict[str, Any],
        tool_specs: List[ToolSpec] | None,
        node: Node,
    ) -> ModelResponse:
        """Invoke provider with logging + token tracking."""
        self._ensure_not_cancelled()
        if self.context.token_tracker:
            self.context.token_tracker.current_node_id = node.id

        agent_config = node.as_config(AgentConfig)
        retry_policy = self._resolve_retry_policy(node, agent_config)

        def _call_provider() -> ModelResponse:
            return provider.call_model(
                client,
                conversation=conversation,
                timeline=timeline,
                tool_specs=tool_specs or None,
                **call_options,
            )

        last_input = ''.join(msg.text_content() for msg in conversation) if conversation else ""
        self._record_model_call(node, last_input, None, CallStage.BEFORE)
        response = self._execute_with_retry(node, retry_policy, _call_provider)
        self.log_manager.debug(response.str_raw_response())
        self._record_model_call(node, last_input, response, CallStage.AFTER)
        return response

    def _record_model_call(
        self,
        node: Node,
        input_payload: str,
        response: ModelResponse | None,
        stage: CallStage = CallStage.AFTER,
    ) -> None:
        """Record model invocation to the log manager."""
        response_text = response.message.text_content() if response else None
        call_details = {"has_tool_calls": response.has_tool_calls()} if response else {}
        self.log_manager.record_model_call(
            node.id,
            node.model_name,
            input_payload,
            response_text,
            call_details,
            stage,
        )

    def _execute_with_retry(
        self,
        node: Node,
        retry_config: AgentRetryConfig | None,
        func: Callable[[], ModelResponse],
    ) -> ModelResponse:
        if not retry_config or not retry_config.is_active:
            return func()

        wait = wait_random_exponential(
            min=retry_config.min_wait_seconds,
            max=retry_config.max_wait_seconds,
        )
        retry_condition = retry_if_exception(lambda exc: retry_config.should_retry(exc))

        def _before_sleep(retry_state) -> None:
            exc = retry_state.outcome.exception()
            if exc is None:
                return
            attempt = retry_state.attempt_number
            details = {
                "attempt": attempt,
                "max_attempts": retry_config.max_attempts,
                "exception": exc.__class__.__name__,
            }
            self.log_manager.warning(
                f"[Node: {node.id}] Model call attempt {attempt} failed: {exc}",
                node_id=node.id,
                details=details,
            )

        retrier = Retrying(
            stop=stop_after_attempt(retry_config.max_attempts),
            wait=wait,
            retry=retry_condition,
            before_sleep=_before_sleep,
            reraise=True,
        )
        return retrier(func)

    def _resolve_retry_policy(
        self,
        node: Node,
        agent_config: AgentConfig | None,
    ) -> AgentRetryConfig | None:
        """Ensure every agent node has a retry policy even if config omits it."""
        if not agent_config:
            return None
        if agent_config.retry is not None:
            return agent_config.retry

        base_path = getattr(agent_config, "path", None) or getattr(node, "path", None) or "<runtime>"
        retry_path = f"{base_path}.retry" if base_path else "retry"
        default_retry = AgentRetryConfig(path=retry_path)
        agent_config.retry = default_retry
        return default_retry
    
    def _apply_pre_generation_thinking(
        self,
        node: Node,
        conversation: List[Message],
        input_payload: ThinkingPayload,
        query_snapshot: MemoryContentSnapshot,
        stage: AgentExecFlowStage,
        agent_invoker: Callable[[List[Message]], Message],
        input_mode: AgentInputMode,
    ) -> None:
        """Apply pre-generation thinking."""
        self._ensure_not_cancelled()
        thinking_manager = self.context.get_thinking_manager(node.id)
        if not thinking_manager or not conversation:
            return

        model = node.as_config(AgentConfig)

        with self.log_manager.thinking_timer(node.id, stage.value):
            retrieved_memory = self._retrieve_memory(node, query_snapshot, stage)
            memory_payload = self._memory_result_to_thinking_payload(retrieved_memory)
            thinking_result = thinking_manager.think(
                agent_invoker=agent_invoker,
                input_payload=input_payload,
                agent_role=node.role or "",
                memory=memory_payload,
                gen_payload=None,
            )

        mode_value = model.thinking.type if model and model.thinking else "unknown"
        self.log_manager.record_thinking_process(
            node.id,
            mode_value,
            thinking_result if isinstance(thinking_result, str) else "[message]",
            stage.value,
            {"has_memory": bool(retrieved_memory and retrieved_memory.items)},
        )

        if input_mode is AgentInputMode.MESSAGES:
            if isinstance(thinking_result, Message):
                self._persist_message_attachments(thinking_result, node.id)
                conversation.append(self._clone_with_source(thinking_result, node.id))
            else:
                self._append_user_message(conversation, thinking_result, node_id=node.id)
        else:
            content = thinking_result if isinstance(thinking_result, str) else thinking_result.text_content()
            conversation[-1] = conversation[-1].with_content(content)
    
    def _apply_memory_retrieval(
        self,
        node: Node,
        conversation: List[Message],
        query_snapshot: MemoryContentSnapshot,
        stage: AgentExecFlowStage,
        input_mode: AgentInputMode,
    ) -> None:
        """Apply memory retrieval side effects."""
        self._ensure_not_cancelled()
        if not conversation:
            return

        retrieved_memory = self._retrieve_memory(node, query_snapshot, stage)

        if retrieved_memory and retrieved_memory.formatted_text:
            if input_mode is AgentInputMode.MESSAGES:
                self._insert_memory_message(conversation, retrieved_memory.formatted_text, node_id=node.id)
            else:
                last_message = conversation[-1]
                merged_content = f"{retrieved_memory.formatted_text}\n\n{last_message.text_content()}"
                conversation[-1] = last_message.with_content(merged_content)
    
    def _retrieve_memory(
        self,
        node: Node,
        query_snapshot: MemoryContentSnapshot,
        stage: AgentExecFlowStage
    ) -> MemoryRetrievalResult | None:
        """Retrieve memory for the node."""
        memory_manager = self.context.get_memory_manager(node.id)
        if not memory_manager:
            return None

        with self.log_manager.memory_timer(node.id, "RETRIEVE", stage.value):
            retrieved_memory = memory_manager.retrieve(
                agent_role=node.role if node.role else "",
                query=query_snapshot,
                current_stage=stage,
            )

        preview_text = retrieved_memory.formatted_text if retrieved_memory else ""
        details = {
            "stage": stage.value,
            "item_count": len(retrieved_memory.items) if retrieved_memory else 0,
            "attachment_count": len(retrieved_memory.attachment_overview()) if retrieved_memory else 0,
        }

        self.log_manager.record_memory_operation(
            node.id,
            "RETRIEVE",
            stage.value,
            preview_text,
            details,
        )

        return retrieved_memory
    
    
    def _handle_tool_calls(
        self,
        node: Node,
        provider: ModelProvider,
        client: Any,
        conversation: List[Message],
        timeline: List[Any],
        call_options: Dict[str, Any],
        initial_response: ModelResponse,
        tool_specs: List[ToolSpec],
        skill_manager: AgentSkillManager | None,
    ) -> Message:
        """Handle tool calls until completion or until the loop limit is reached."""
        assistant_message = initial_response.message
        trace_messages: List[Message] = []
        loop_limit = self._get_tool_loop_limit(node)
        iteration = 0

        while True:
            self._ensure_not_cancelled()
            cloned_assistant = self._clone_with_source(assistant_message, node.id)
            conversation.append(cloned_assistant)
            trace_messages.append(cloned_assistant)

            if not assistant_message.tool_calls:
                return self._finalize_tool_trace(assistant_message, trace_messages, True, node.id)

            if iteration >= loop_limit:
                self.log_manager.warning(
                    f"[Node: {node.id}] Tool call limit {loop_limit} reached, returning last assistant response"
                )
                return self._finalize_tool_trace(assistant_message, trace_messages, False, node.id)

            iteration += 1

            tool_call_messages, tool_events = self._execute_tool_batch(
                node,
                assistant_message.tool_calls,
                tool_specs,
                skill_manager,
            )
            conversation.extend(tool_call_messages)
            timeline.extend(tool_events)
            trace_messages.extend(self._clone_with_source(msg, node.id) for msg in tool_call_messages)

            follow_up_response = self._invoke_provider(
                provider,
                client,
                conversation,
                timeline,
                call_options,
                tool_specs,
                node,
            )
            assistant_message = follow_up_response.message

    def _execute_tool_batch(
        self,
        node: Node,
        tool_calls: List[ToolCallPayload],
        tool_specs: List[ToolSpec],
        skill_manager: AgentSkillManager | None,
    ) -> tuple[List[Message], List[Any]]:
        """Execute a batch of tool calls and return conversation + timeline events."""
        messages: List[Message] = []
        events: List[Any] = []
        model = node.as_config(AgentConfig)
        
        # Build map for fast lookup
        spec_map = {spec.name: spec for spec in tool_specs}
        configs = model.tooling if model else []

        context_state = self.context.global_state
        previous_node_id = context_state.get("node_id") if context_state is not None else None
        if context_state is not None:
            context_state["node_id"] = node.id

        try:
            for tool_call in tool_calls:
                self._ensure_not_cancelled()
                tool_name = tool_call.function_name
                arguments = self._parse_tool_call_arguments(tool_call.arguments)
                
                # Resolve tool config
                spec = spec_map.get(tool_name)
                tool_config = None
                execution_name = tool_name
                
                if spec:
                    idx = spec.metadata.get("_config_index")
                    if idx is not None and 0 <= idx < len(configs):
                        tool_config = configs[idx]
                    # Use original name if prefixed
                    execution_name = spec.metadata.get("original_name", tool_name)

                if spec and spec.metadata.get("source") == "agent_skill_internal":
                    try:
                        self.log_manager.record_tool_call(
                            node.id,
                            tool_name,
                            None,
                            None,
                            {"arguments": arguments},
                            CallStage.BEFORE,
                        )
                        with self.log_manager.tool_timer(node.id, tool_name):
                            result = self._execute_skill_tool(tool_name, arguments, skill_manager)

                        tool_message = self._build_tool_message(
                            result,
                            tool_call,
                            node_id=node.id,
                            tool_name=tool_name,
                        )
                        events.append(self._build_function_call_output_event(tool_call, result))
                        system_message = self._build_skill_followup_message(tool_name, result, node.id)
                        if system_message is not None:
                            messages.append(system_message)
                            events.append(system_message)
                        self.log_manager.record_tool_call(
                            node.id,
                            tool_name,
                            True,
                            self._serialize_tool_result(result),
                            {"arguments": arguments},
                            CallStage.AFTER,
                        )
                    except Exception as exc:
                        self.log_manager.record_tool_call(
                            node.id,
                            tool_name,
                            False,
                            None,
                            {"error": str(exc), "arguments": arguments},
                            CallStage.AFTER,
                        )
                        tool_message = Message(
                            role=MessageRole.TOOL,
                            content=f"Tool {tool_name} error: {exc}",
                            tool_call_id=tool_call.id,
                            metadata={"tool_name": tool_name, "source": node.id},
                        )
                        events.append(
                            FunctionCallOutputEvent(
                                call_id=tool_call.id or tool_call.function_name or "tool_call",
                                function_name=tool_call.function_name,
                                output_text=f"error: {exc}",
                            )
                        )

                    messages.append(tool_message)
                    continue

                active_skill = skill_manager.active_skill() if skill_manager is not None else None
                if (
                    active_skill is not None
                    and active_skill.allowed_tools
                    and execution_name not in active_skill.allowed_tools
                ):
                    error_msg = (
                        f"Tool '{tool_name}' is not allowed by active skill "
                        f"'{active_skill.name}'. Allowed tools: {list(active_skill.allowed_tools)}"
                    )
                    self.log_manager.record_tool_call(
                        node.id,
                        tool_name,
                        False,
                        None,
                        {"error": error_msg, "arguments": arguments},
                        CallStage.AFTER,
                    )
                    tool_message = Message(
                        role=MessageRole.TOOL,
                        content=f"Error: {error_msg}",
                        tool_call_id=tool_call.id,
                        metadata={"tool_name": tool_name, "source": node.id},
                    )
                    events.append(
                        FunctionCallOutputEvent(
                            call_id=tool_call.id or tool_call.function_name or "tool_call",
                            function_name=tool_call.function_name,
                            output_text=f"error: {error_msg}",
                        )
                    )
                    messages.append(tool_message)
                    continue
                
                if not tool_config:
                     # Fallback check: if we have 1 config, maybe it's that one? 
                     # But strict routing is safer. If spec not found, it's a hallucination or error.
                     # We proceed and let tool_manager raise error or handle it.
                     # But execute_tool requires tool_config. 
                     
                     # Construct a helpful error message
                     error_msg = f"Tool '{tool_name}' configuration not found."
                     self.log_manager.record_tool_call(
                        node.id,
                        tool_name,
                        False,
                        None,
                        {"error": error_msg, "arguments": arguments},
                        CallStage.AFTER,
                    )
                     tool_message = Message(
                        role=MessageRole.TOOL,
                        content=f"Error: {error_msg}",
                        tool_call_id=tool_call.id,
                        metadata={"tool_name": tool_name, "source": node.id},
                    )
                     events.append(
                        FunctionCallOutputEvent(
                            call_id=tool_call.id or tool_call.function_name or "tool_call",
                            function_name=tool_call.function_name,
                            output_text=f"error: {error_msg}",
                        )
                    )
                     messages.append(tool_message)
                     continue

                try:
                    self.log_manager.record_tool_call(
                        node.id,
                        tool_name,
                        None,
                        None,
                        {"arguments": arguments},
                        CallStage.BEFORE,
                    )
                    with self.log_manager.tool_timer(node.id, tool_name):
                        result = asyncio.run(
                            self.tool_manager.execute_tool(
                                execution_name,
                                arguments,
                                tool_config,
                                tool_context=self.context.global_state,
                            )
                        )

                    tool_message = self._build_tool_message(
                        result,
                        tool_call,
                        node_id=node.id,
                        tool_name=tool_name,
                    )
                    events.append(
                        self._build_function_call_output_event(
                            tool_call,
                            result,
                        )
                    )

                    self.log_manager.record_tool_call(
                        node.id,
                        tool_name,
                        True,
                        self._serialize_tool_result(result),
                        {"arguments": arguments},
                        CallStage.AFTER,
                    )
                except Exception as exc:
                    self.log_manager.record_tool_call(
                        node.id,
                        tool_name,
                        False,
                        None,
                        {"error": str(exc), "arguments": arguments},
                        CallStage.AFTER,
                    )
                    tool_message = Message(
                        role=MessageRole.TOOL,
                        content=f"Tool {tool_name} error: {exc}",
                        tool_call_id=tool_call.id,
                        metadata={"tool_name": tool_name, "source": node.id},
                    )
                    events.append(
                        FunctionCallOutputEvent(
                            call_id=tool_call.id or tool_call.function_name or "tool_call",
                            function_name=tool_call.function_name,
                            output_text=f"error: {exc}",
                        )
                    )

                messages.append(tool_message)
        finally:
            if context_state is not None:
                if previous_node_id is None:
                    context_state.pop("node_id", None)
                else:
                    context_state["node_id"] = previous_node_id

        return messages, events

    def _build_skill_followup_message(
        self,
        tool_name: str,
        result: Any,
        node_id: str,
    ) -> Message | None:
        if tool_name != "activate_skill" or not isinstance(result, dict):
            return None

        instructions = result.get("instructions")
        skill_name = result.get("skill_name", "unknown-skill")
        allowed_tools = result.get("allowed_tools")
        if not isinstance(instructions, str) or not instructions.strip():
            return None

        tool_constraint = ""
        if isinstance(allowed_tools, list) and allowed_tools:
            tool_constraint = f"\n\nOnly use these external tools while this skill is active: {allowed_tools}"

        return Message(
            role=MessageRole.SYSTEM,
            content=(
                f"Activated Agent Skill `{skill_name}`. "
                "Follow its instructions for the current task until they are completed or no longer relevant.\n\n"
                f"{instructions}{tool_constraint}"
            ),
            metadata={"source": node_id, "skill_name": skill_name, "skill_activation": True},
        )

    def _execute_skill_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        skill_manager: AgentSkillManager | None,
    ) -> Dict[str, Any]:
        if skill_manager is None:
            raise ValueError("Agent Skills are not enabled for this node")

        if tool_name == "activate_skill":
            skill_name = str(arguments.get("skill_name", "")).strip()
            if not skill_name:
                raise ValueError("skill_name is required")
            return skill_manager.activate_skill(skill_name)

        if tool_name == "read_skill_file":
            skill_name = str(arguments.get("skill_name", "")).strip()
            relative_path = str(arguments.get("relative_path", "")).strip()
            if not skill_name:
                raise ValueError("skill_name is required")
            if not relative_path:
                raise ValueError("relative_path is required")
            return skill_manager.read_skill_file(skill_name, relative_path)

        raise ValueError(f"Unsupported skill tool '{tool_name}'")

    def _build_function_call_output_event(
        self,
        tool_call: ToolCallPayload,
        result: Any,
    ) -> FunctionCallOutputEvent:
        call_id = tool_call.id or tool_call.function_name or "tool_call"
        blocks = self._coerce_tool_result_to_blocks(result)
        if blocks:
            return FunctionCallOutputEvent(
                call_id=call_id,
                function_name=tool_call.function_name,
                output_blocks=blocks,
            )
        return FunctionCallOutputEvent(
            call_id=call_id,
            function_name=tool_call.function_name,
            output_text=self._stringify_tool_result(result),
        )

    def _stringify_tool_result(self, result: Any) -> str:
        if isinstance(result, Message):
            return result.text_content()
        if isinstance(result, list) and all(isinstance(item, MessageBlock) for item in result):
            parts = [block.describe() for block in result if block.describe()]
            return "\n".join(parts)
        if isinstance(result, (dict, list)):
            try:
                return json.dumps(result, ensure_ascii=False)
            except Exception:
                return str(result)
        return str(result)

    def _serialize_tool_result(self, result: Any) -> Any:
        """Convert tool outputs into JSON-serializable structures for logging."""
        from utils.attachments import AttachmentRecord  # local import to avoid cycles

        if result is None:
            return None
        if isinstance(result, Message):
            return result.to_dict(include_data=False)
        if isinstance(result, MessageBlock):
            return result.to_dict(include_data=False)
        if isinstance(result, AttachmentRecord):
            return result.to_dict()
        if isinstance(result, list):
            return [self._serialize_tool_result(item) for item in result]
        if isinstance(result, dict):
            return {
                str(key): self._serialize_tool_result(value)
                for key, value in result.items()
            }
        if hasattr(result, "to_dict"):
            try:
                return self._serialize_tool_result(result.to_dict())
            except Exception:
                return str(result)
        return result if isinstance(result, (str, int, float, bool)) else str(result)

    def _build_tool_message(
        self,
        result: Any,
        tool_call: ToolCallPayload,
        *,
        node_id: str,
        tool_name: str,
    ) -> Message:
        base_metadata = {"tool_name": tool_name, "source": node_id}
        if isinstance(result, Message):
            msg = result.clone()
            msg = msg.with_role(MessageRole.TOOL)
            msg.tool_call_id = tool_call.id
            metadata = dict(base_metadata)
            metadata.update(msg.metadata)
            msg.metadata = metadata
            return msg

        from utils.attachments import AttachmentRecord  # local import

        if isinstance(result, AttachmentRecord):
            content = [result.as_message_block()]
        elif isinstance(result, list) and all(isinstance(item, MessageBlock) for item in result):
            content = [block.copy() for block in result]
        else:
            content = result
            if isinstance(result, dict):
                content = json.dumps(self._serialize_tool_result(content), ensure_ascii=False, indent=2)
            elif not isinstance(result, str):
                content = str(result)

        return Message(
            role=MessageRole.TOOL,
            content=content,
            tool_call_id=tool_call.id,
            metadata=base_metadata,
        )

    def _build_initial_timeline(self, conversation: List[Message]) -> List[Any]:
        return [msg.clone() for msg in conversation]

    def _finalize_tool_trace(
        self,
        message: Message,
        trace_messages: List[Message],
        complete: bool,
        node_id: str,
    ) -> Message:
        final_message = self._clone_with_source(message, node_id)
        if trace_messages:
            metadata = dict(final_message.metadata)
            metadata["context_trace"] = [item.to_dict() for item in trace_messages]
            metadata["context_trace_complete"] = complete
            final_message.metadata = metadata
        return final_message

    def _clone_with_source(self, message: Message, node_id: str) -> Message:
        cloned = message.clone()
        metadata = dict(cloned.metadata)
        metadata.setdefault("source", node_id)
        cloned.metadata = metadata
        return cloned

    def _coerce_tool_result_to_blocks(self, result: Any) -> List[MessageBlock]:
        """Convert supported tool outputs into MessageBlock sequences."""
        if result is None:
            return []
        if isinstance(result, Message):
            return [block.copy() for block in result.blocks()]
        if isinstance(result, MessageBlock):
            return [result.copy()]

        from utils.attachments import AttachmentRecord  # local import to avoid cycles

        if isinstance(result, AttachmentRecord):
            return [result.as_message_block()]

        if isinstance(result, Sequence) and not isinstance(result, (str, bytes, bytearray)):
            blocks: List[MessageBlock] = []
            for item in result:
                blocks.extend(self._coerce_tool_result_to_blocks(item))
            return blocks

        return []

    def _parse_tool_call_arguments(self, raw_arguments: Any) -> Dict[str, Any]:
        if isinstance(raw_arguments, dict):
            return raw_arguments
        if not raw_arguments:
            return {}
        if isinstance(raw_arguments, str):
            try:
                parsed = json.loads(raw_arguments)
            except json.JSONDecodeError:
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return {}

    def _get_tool_loop_limit(self, node: Node) -> int:
        default_limit = 50
        model = node.as_config(AgentConfig)
        if not model or not model.params:
            return default_limit
        custom_limit = model.params.get("tool_loop_limit")
        if isinstance(custom_limit, int) and custom_limit > 0:
            return custom_limit
        return default_limit

    def _persist_message_attachments(self, message: Message, node_id: str) -> None:
        """Register attachments produced by model outputs to the attachment store."""
        store = self.context.global_state.get("attachment_store")
        if store is None:
            return
        for block in message.blocks():
            attachment = block.attachment
            if not attachment:
                continue
            try:
                self._persist_single_attachment(store, block, node_id)
            except Exception as exc:
                raise RuntimeError(f"Failed to persist attachment '{attachment.name or attachment.attachment_id}': {exc}") from exc

    def _persist_single_attachment(self, store: Any, block: MessageBlock, node_id: str) -> None:
        attachment = block.attachment
        if attachment is None:
            return
        if attachment.remote_file_id and not attachment.data_uri and not attachment.local_path:
            record = store.register_remote_file(
                remote_file_id=attachment.remote_file_id,
                name=attachment.name or attachment.attachment_id or "remote_file",
                mime_type=attachment.mime_type,
                size=attachment.size,
                kind=block.type,
                attachment_id=attachment.attachment_id,
            )
            block.attachment = record.ref
            return

        workspace_root = self.context.global_state.get("python_workspace_root")
        if workspace_root is None or not node_id:
            raise RuntimeError("Workspace or node context missing for attachment persistence")

        target_dir = workspace_root / "generated" / node_id
        target_dir.mkdir(parents=True, exist_ok=True)

        inferred_mime = attachment.mime_type or self._guess_mime_from_data_uri(attachment.data_uri)
        attachment.mime_type = inferred_mime

        data_bytes = self._decode_data_uri(attachment.data_uri) if attachment.data_uri else None
        target_path = None

        if data_bytes is None and attachment.local_path:
            target_path = target_dir / (attachment.name or self._make_generated_filename(attachment))
            import shutil
            shutil.copy2(attachment.local_path, target_path)
        elif data_bytes is not None:
            target_path = target_dir / (attachment.name or self._make_generated_filename(attachment))
            with open(target_path, "wb") as handle:
                handle.write(data_bytes)
        else:
            raise ValueError("Attachment missing data for persistence")

        record = store.register_file(
            target_path,
            kind=block.type,
            display_name=attachment.name or target_path.name,
            mime_type=attachment.mime_type,
            attachment_id=attachment.attachment_id,
            copy_file=False,
            persist=True,
        )
        block.attachment = record.ref

    def _decode_data_uri(self, data_uri: Optional[str]) -> Optional[bytes]:
        if not data_uri:
            return None
        if not data_uri.startswith("data:"):
            return None
        header, _, payload = data_uri.partition(",")
        if not _:
            return None
        if ";base64" in header:
            return base64.b64decode(payload)
        return payload.encode("utf-8")

    def _make_generated_filename(self, attachment: AttachmentRef) -> str:
        """Generate a filename based on mime type or attachment id."""
        name = attachment.name
        if name:
            return name
        mime = attachment.mime_type or ""
        ext = ""
        if "/" in mime:
            subtype = mime.split("/", 1)[1]
            if subtype:
                ext = f".{subtype.split('+')[0]}"
        if not ext:
            ext = ".bin"
        return f"{attachment.attachment_id or 'generated'}{ext}"
    
    def _guess_mime_from_data_uri(self, data_uri: Optional[str]) -> Optional[str]:
        if not data_uri or not data_uri.startswith("data:"):
            return None
        header = data_uri.split(",", 1)[0]
        if ":" in header:
            header = header.split(":", 1)[1]
        return header.split(";")[0] if ";" in header else header


    def _apply_post_generation_thinking(
        self,
        node: Node,
        conversation: List[Message],
        query_snapshot: MemoryContentSnapshot,
        input_payload: ThinkingPayload,
        gen_payload: ThinkingPayload,
        stage: AgentExecFlowStage,
        agent_invoker: Callable[[List[Message]], Message],
        input_mode: AgentInputMode,
    ) -> Message | str:
        """Apply post-generation thinking."""
        self._ensure_not_cancelled()
        thinking_manager = self.context.get_thinking_manager(node.id)
        if not thinking_manager:
            return gen_payload.raw if gen_payload.raw is not None else gen_payload.text

        model = node.as_config(AgentConfig)

        with self.log_manager.thinking_timer(node.id, stage.value):
            retrieved_memory = self._retrieve_memory(node, query_snapshot, stage)
            memory_payload = self._memory_result_to_thinking_payload(retrieved_memory)
            result = thinking_manager.think(
                agent_invoker=agent_invoker,
                input_payload=input_payload,
                agent_role=node.role or "",
                memory=memory_payload,
                gen_payload=gen_payload,
            )

        mode_value = model.thinking.type if model and model.thinking else "unknown"
        self.log_manager.record_thinking_process(
            node.id,
            mode_value,
            result if isinstance(result, str) else "[message]",
            stage.value,
            {"has_memory": bool(retrieved_memory and retrieved_memory.items)},
        )

        if input_mode is AgentInputMode.MESSAGES:
            if isinstance(result, Message):
                self._persist_message_attachments(result, node.id)
                self._reset_conversation_with_user_result(conversation, result, node_id=node.id)
            else:
                self._reset_conversation_with_user_result(conversation, result, node_id=node.id)

        return result

    def _coerce_inputs_to_messages(self, inputs: List[Message]) -> List[Message]:
        return [message.clone() for message in inputs if isinstance(message, Message)]

    def _compress_inputs_for_context(self, node: Node, inputs: List[Message]) -> List[Message]:
        normalized = self._coerce_inputs_to_messages(inputs)
        if not normalized:
            return normalized

        config = self._context_compression_config()
        total_chars = sum(len(message.text_content()) for message in normalized)
        should_compress = (
            len(normalized) > config["max_messages"]
            or total_chars > config["max_chars"]
        )
        if not should_compress:
            return normalized

        pinned: List[Message] = []
        ordinary: List[Message] = []
        for message in normalized:
            if message.keep or message.preserve_role or message.role is MessageRole.SYSTEM:
                pinned.append(message.clone())
            else:
                ordinary.append(message.clone())

        keep_recent = max(1, min(config["keep_recent"], len(ordinary))) if ordinary else 0
        preserved_recent = ordinary[-keep_recent:] if keep_recent else []
        summarized = ordinary[:-keep_recent] if keep_recent else ordinary

        if not summarized:
            return normalized

        summary_message = self._build_compressed_context_message(node, summarized, total_chars)
        compressed_messages = pinned + [summary_message] + preserved_recent
        compressed_chars = sum(len(message.text_content()) for message in compressed_messages)
        self.log_manager.info(
            f"[Node: {node.id}] Compressed context from {len(normalized)} to {len(compressed_messages)} messages",
            node_id=node.id,
            details={
                "original_message_count": len(normalized),
                "compressed_message_count": len(compressed_messages),
                "original_char_count": total_chars,
                "compressed_char_count": compressed_chars,
            },
        )
        return compressed_messages

    def _context_compression_config(self) -> Dict[str, int]:
        global_state = self.context.global_state or {}
        config = global_state.get("context_compression")
        if not isinstance(config, dict):
            config = {}

        def _int_value(key: str, default: int) -> int:
            try:
                return max(1, int(config.get(key, default)))
            except (TypeError, ValueError):
                return default

        return {
            "max_messages": _int_value("max_messages", CONTEXT_COMPRESSION_MAX_MESSAGES),
            "max_chars": _int_value("max_chars", CONTEXT_COMPRESSION_MAX_CHARS),
            "keep_recent": _int_value("keep_recent", CONTEXT_COMPRESSION_KEEP_RECENT),
            "preview_chars": _int_value("preview_chars", CONTEXT_COMPRESSION_PREVIEW_CHARS),
        }

    def _build_compressed_context_message(
        self,
        node: Node,
        messages: List[Message],
        original_char_count: int,
    ) -> Message:
        preview_chars = self._context_compression_config()["preview_chars"]
        lines = [
            "[Compressed Earlier Context]",
            f"Older context was compressed for this node to reduce token usage. Original chars: {original_char_count}.",
            "Summaries:",
        ]
        for index, message in enumerate(messages, start=1):
            source = str(message.metadata.get("source") or "unknown").strip()
            preview = " ".join(message.text_content().split())
            if len(preview) > preview_chars:
                preview = f"{preview[: preview_chars - 1].rstrip()}..."
            lines.append(f"{index}. ({message.role.value}) {source}: {preview}")

        return Message(
            role=MessageRole.SYSTEM,
            content="\n".join(lines),
            metadata={
                "source": "CONTEXT_SUMMARY",
                "compressed": True,
                "compressed_message_count": len(messages),
                "node_id": node.id,
            },
            preserve_role=True,
            keep=True,
        )

    def _append_user_message(self, conversation: List[Message], content: str, *, node_id: str) -> None:
        conversation.append(
            Message(role=MessageRole.USER, content=content, metadata={"source": node_id})
        )

    def _insert_memory_message(self, conversation: List[Message], content: str, *, node_id: str) -> None:
        last_user_idx = self._find_last_user_index(conversation)
        insert_idx = last_user_idx if last_user_idx is not None else len(conversation)
        conversation.insert(
            insert_idx,
            Message(role=MessageRole.USER, content=content, metadata={"source": node_id}),
        )

    def _find_last_user_index(self, conversation: List[Message]) -> Optional[int]:
        for idx in range(len(conversation) - 1, -1, -1):
            if conversation[idx].role is MessageRole.USER:
                return idx
        return None

    def _reset_conversation_with_user_result(self, conversation: List[Message], content: Message | str, *, node_id: str) -> None:
        system_messages = [msg.clone() for msg in conversation if msg.role is MessageRole.SYSTEM]
        conversation.clear()
        conversation.extend(system_messages)
        if isinstance(content, Message):
            conversation.append(self._clone_with_source(content.with_role(MessageRole.USER), node_id))
        else:
            conversation.append(
                Message(role=MessageRole.USER, content=content, metadata={"source": node_id})
            )
    
    def _update_memory(self, node: Node, input_data: str, inputs: List[Message], result: Message | str) -> None:
        """Update the memory store with the latest conversation."""
        memory_manager = self.context.get_memory_manager(node.id)
        if not memory_manager:
            return
        
        stage = AgentExecFlowStage.FINISHED_STAGE
        
        input_snapshot = MemoryContentSnapshot.from_messages(inputs)
        output_snapshot = MemoryContentSnapshot.from_message(result)
        payload = MemoryWritePayload(
            agent_role=node.role if node.role else "",
            inputs_text=input_data,
            input_snapshot=input_snapshot,
            output_snapshot=output_snapshot,
        )

        with self.log_manager.memory_timer(node.id, "UPDATE", stage.value):
            memory_manager.update(payload)
        
        # Record the memory update
        normalized_result = result.text_content() if isinstance(result, Message) else str(result)
        self.log_manager.record_memory_operation(
            node.id,
            "UPDATE",
            stage.value,
            normalized_result,
            {
                "stage": stage.value,
                "input_size": len(str(input_data)),
                "output_size": len(normalized_result),
                "attachment_count": len(output_snapshot.attachment_overview()) if output_snapshot else 0,
            }
        )

    def _build_thinking_payload_from_inputs(self, inputs: List[Message], input_text: str) -> ThinkingPayload:
        blocks: List[MessageBlock] = []
        for message in inputs:
            blocks.extend(message.blocks())
        return ThinkingPayload(
            text=input_text,
            blocks=blocks,
            metadata={"source": "inputs"},
            raw=input_text,
        )

    def _build_memory_query_snapshot(
        self,
        inputs: List[Message],
        input_text: str,
    ) -> MemoryContentSnapshot:
        base_snapshot = MemoryContentSnapshot.from_messages(inputs)
        blocks = list(base_snapshot.blocks) if base_snapshot else []
        return MemoryContentSnapshot(text=input_text, blocks=blocks)

    def _build_thinking_payload_from_message(self, message: Message | str | None, *, source: str) -> ThinkingPayload:
        if isinstance(message, Message):
            return ThinkingPayload(
                text=message.text_content(),
                blocks=message.blocks(),
                metadata={"source": source},
                raw=message,
            )
        text = "" if message is None else str(message)
        return ThinkingPayload(text=text, blocks=[], metadata={"source": source}, raw=text)

    def _memory_result_to_thinking_payload(
        self,
        result: MemoryRetrievalResult | None,
    ) -> ThinkingPayload | None:
        if not result:
            return None
        blocks: List[MessageBlock] = []
        for item in result.items:
            if item.output_snapshot:
                blocks.extend(item.output_snapshot.to_message_blocks())
            if item.input_snapshot:
                blocks.extend(item.input_snapshot.to_message_blocks())
        metadata = {
            "source": "memory",
            "has_multimodal": result.has_multimodal(),
            "attachment_count": len(result.attachment_overview()),
        }
        return ThinkingPayload(text=result.formatted_text, blocks=blocks, metadata=metadata)
