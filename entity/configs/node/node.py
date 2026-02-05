"""Node configuration dataclasses."""

from dataclasses import dataclass, field, replace
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from entity.messages import Message, MessageRole
from schema_registry import (
    SchemaLookupError,
    get_node_schema,
    iter_node_schemas,
)

from entity.configs.base import (
    BaseConfig,
    ConfigError,
    ConfigFieldSpec,
    EnumOption,
    ChildKey,
    ensure_list,
    optional_str,
    require_mapping,
    require_str,
    extend_path,
)
from entity.configs.edge.edge_condition import EdgeConditionConfig
from entity.configs.edge.edge_processor import EdgeProcessorConfig
from entity.configs.edge.dynamic_edge_config import DynamicEdgeConfig
from entity.configs.node.agent import AgentConfig
from entity.configs.node.human import HumanConfig
from entity.configs.node.tooling import FunctionToolConfig

NodePayload = Message




@dataclass
class EdgeLink:
    target: "Node"
    config: Dict[str, Any] = field(default_factory=dict)
    trigger: bool = True
    condition: str = "true"
    condition_config: EdgeConditionConfig | None = None
    condition_type: str | None = None
    condition_metadata: Dict[str, Any] = field(default_factory=dict)
    triggered: bool = False
    carry_data: bool = True
    keep_message: bool = False
    clear_context: bool = False
    clear_kept_context: bool = False
    condition_manager: Any = None
    process_config: EdgeProcessorConfig | None = None
    process_type: str | None = None
    process_metadata: Dict[str, Any] = field(default_factory=dict)
    payload_processor: Any = None
    dynamic_config: DynamicEdgeConfig | None = None

    def __post_init__(self) -> None:
        self.config = dict(self.config or {})


@dataclass
class Node(BaseConfig):
    id: str
    type: str
    description: str | None = None
    # keep_context: bool = False
    log_output: bool = True
    context_window: int = 0
    vars: Dict[str, Any] = field(default_factory=dict)
    config: BaseConfig | None = None
    # dynamic configuration has been moved to edges (DynamicEdgeConfig)

    input: List[Message] = field(default_factory=list)
    output: List[NodePayload] = field(default_factory=list)
    # Runtime flag for explicit graph start nodes
    start_triggered: bool = False
    predecessors: List["Node"] = field(default_factory=list, repr=False)
    successors: List["Node"] = field(default_factory=list, repr=False)
    _outgoing_edges: List[EdgeLink] = field(default_factory=list, repr=False)

    FIELD_SPECS = {
        "id": ConfigFieldSpec(
            name="id",
            display_name="Node ID",
            type_hint="str",
            required=True,
            description="Unique node identifier",
        ),
        "type": ConfigFieldSpec(
            name="type",
            display_name="Node Type",
            type_hint="str",
            required=True,
            description="Select a node type registered in node.registry (agent, human, python_runner, etc.); it determines the config schema.",
        ),
        "description": ConfigFieldSpec(
            name="description",
            display_name="Node Description",
            type_hint="str",
            required=False,
            advance=True,
            description="Short summary shown in consoles/logs to explain this node's role or prompt context.",
        ),
        # "keep_context": ConfigFieldSpec(
        #     name="keep_context",
        #     display_name="Preserve Context",
        #     type_hint="bool",
        #     required=False,
        #     default=False,
        #     description="Nodes clear their context by default; set to True to keep context data after execution.",
        # ),
        "context_window": ConfigFieldSpec(
            name="context_window",
            display_name="Context Window Size",
            type_hint="int",
            required=False,
            default=0,
            description="Number of context messages accessible during node execution. 0 means clear all context except messages with keep_message=True, -1 means unlimited, other values represent the number of context messages to keep besides those with keep_message=True.",
            # advance=True,
        ),
        "log_output": ConfigFieldSpec(
            name="log_output",
            display_name="Log Output",
            type_hint="bool",
            required=False,
            default=True,
            advance=True,
            description="Whether to log this node's output content. Set to false to avoid logging outputs.",
        ),
        "config": ConfigFieldSpec(
            name="config",
            display_name="Node Configuration",
            type_hint="object",
            required=True,
            description="Configuration object required by the chosen node type (see Schema API for the supported fields).",
        ),
        # Dynamic execution configuration has been moved to edges (DynamicEdgeConfig)
    }

    @classmethod
    def child_routes(cls) -> Dict[ChildKey, type[BaseConfig]]:
        routes: Dict[ChildKey, type[BaseConfig]] = {}
        for name, schema in iter_node_schemas().items():
            routes[ChildKey(field="config", value=name)] = schema.config_cls
        return routes

    @classmethod
    def field_specs(cls) -> Dict[str, ConfigFieldSpec]:
        specs = super().field_specs()
        type_spec = specs.get("type")
        if type_spec:
            registrations = iter_node_schemas()
            specs["type"] = replace(
                type_spec,
                enum=list(registrations.keys()),
                enum_options=[
                    EnumOption(
                        value=name,
                        label=name,
                        description=schema.summary or "No description provided for this node type",
                    )
                    for name, schema in registrations.items()
                ],
            )
        return specs

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "Node":
        mapping = require_mapping(data, path)
        node_id = require_str(mapping, "id", path)
        node_type = require_str(mapping, "type", path)
        try:
            schema = get_node_schema(node_type)
        except SchemaLookupError as exc:
            raise ConfigError(
                f"unsupported node type '{node_type}'",
                extend_path(path, "type"),
            ) from exc

        description = optional_str(mapping, "description", path)
        # keep_context = bool(mapping.get("keep_context", False))
        log_output = bool(mapping.get("log_output", True))
        context_window = int(mapping.get("context_window", 0))
        input_value = ensure_list(mapping.get("input"))
        output_value = ensure_list(mapping.get("output"))

        input_messages: List[Message] = []
        for value in input_value:
            if isinstance(value, dict) and "role" in value:
                input_messages.append(Message.from_dict(value))
            elif isinstance(value, Message):
                input_messages.append(value)
            else:
                input_messages.append(Message(role=MessageRole.USER, content=str(value)))

        if "config" not in mapping or mapping["config"] is None:
            raise ConfigError("node config block required", extend_path(path, "config"))
        config_obj = schema.config_cls.from_dict(
            mapping["config"], path=extend_path(path, "config")
        )

        formatted_output: List[NodePayload] = []
        for value in output_value:
            if isinstance(value, dict) and "role" in value:
                formatted_output.append(Message.from_dict(value))
            elif isinstance(value, Message):
                formatted_output.append(value)
            else:
                formatted_output.append(
                    Message(role=MessageRole.ASSISTANT, content=str(value))
                )

        # Dynamic configuration parsing removed - dynamic is now on edges

        node = cls(
            id=node_id,
            type=node_type,
            description=description,
            log_output=log_output,
            input=input_messages,
            output=formatted_output,
            # keep_context=keep_context,
            context_window=context_window,
            vars={},
            config=config_obj,
            path=path,
        )
        node.validate()
        return node

    def append_input(self, message: Message) -> None:
        self.input.append(message)

    def append_output(self, payload: NodePayload) -> None:
        self.output.append(payload)

    def clear_input(self, *, preserve_kept: bool = False, context_window: int = 0) -> int:
        """Clear queued inputs according to the node's context window semantics."""
        if not preserve_kept:
            self.input = []
            return len(self.input)

        if context_window < 0:
            return len(self.input)

        if context_window == 0:
            self.input = [message for message in self.input if getattr(message, "keep", False)]
            return len(self.input)

        # context_window > 0 => retain the newest messages up to the specified
        # capacity, but never drop messages flagged with keep=True. Those kept
        # messages still count toward the window, effectively consuming slots that
        # would otherwise be available for non-kept inputs.
        keep_count = sum(1 for message in self.input if getattr(message, "keep", False))
        allowed_non_keep = max(0, context_window - keep_count)
        non_keep_total = sum(1 for message in self.input if not getattr(message, "keep", False))
        non_keep_to_drop = max(0, non_keep_total - allowed_non_keep)

        trimmed_inputs: List[Message] = []
        for message in self.input:
            if getattr(message, "keep", False):
                trimmed_inputs.append(message)
                continue
            if non_keep_to_drop > 0:
                non_keep_to_drop -= 1
                continue
            trimmed_inputs.append(message)

        self.input = trimmed_inputs
        return len(self.input)

    def clear_inputs_by_flag(self, *, drop_non_keep: bool, drop_keep: bool) -> Tuple[int, int]:
        """Clear queued inputs according to keep markers."""
        if not drop_non_keep and not drop_keep:
            return 0, 0

        remaining: List[Message] = []
        removed_non_keep = 0
        removed_keep = 0

        for message in self.input:
            is_keep = message.keep
            if is_keep and drop_keep:
                removed_keep += 1
                continue
            if not is_keep and drop_non_keep:
                removed_non_keep += 1
                continue
            remaining.append(message)

        if removed_non_keep or removed_keep:
            self.input = remaining
        return removed_non_keep, removed_keep

    def validate(self) -> None:
        if not self.config:
            raise ConfigError("node configuration missing", extend_path(self.path, "config"))
        if hasattr(self.config, "validate"):
            self.config.validate()

    @property
    def node_type(self) -> str:
        return self.type

    @property
    def model_name(self) -> Optional[str]:
        agent = self.as_config(AgentConfig)
        if not agent:
            return None
        return agent.name

    @property
    def role(self) -> Optional[str]:
        agent = self.as_config(AgentConfig)
        if agent:
            return agent.role
        human = self.as_config(HumanConfig)
        if human:
            return human.description
        return None

    @property
    def tools(self) -> List[Any]:
        agent = self.as_config(AgentConfig)
        if agent and agent.tooling:
            all_tools: List[Any] = []
            for tool_config in agent.tooling:
                func_cfg = tool_config.as_config(FunctionToolConfig)
                if func_cfg:
                    all_tools.extend(func_cfg.tools)
            return all_tools
        return []

    @property
    def memories(self) -> List[Any]:
        agent = self.as_config(AgentConfig)
        if agent:
            return list(agent.memories)
        return []

    @property
    def params(self) -> Dict[str, Any]:
        agent = self.as_config(AgentConfig)
        if agent:
            return dict(agent.params)
        return {}

    @property
    def base_url(self) -> Optional[str]:
        agent = self.as_config(AgentConfig)
        if agent:
            return agent.base_url
        return None

    def add_successor(self, node: "Node", edge_config: Optional[Dict[str, Any]] = None) -> None:
        if node not in self.successors:
            self.successors.append(node)
        payload = dict(edge_config or {})
        existing = next((link for link in self._outgoing_edges if link.target is node), None)
        trigger = bool(payload.get("trigger", True)) if payload else True
        carry_data = bool(payload.get("carry_data", True)) if payload else True
        keep_message = bool(payload.get("keep_message", False)) if payload else False
        clear_context = bool(payload.get("clear_context", False)) if payload else False
        clear_kept_context = bool(payload.get("clear_kept_context", False)) if payload else False
        condition_config = payload.pop("condition_config", None)
        if not isinstance(condition_config, EdgeConditionConfig):
            raw_value = payload.get("condition", "true")
            condition_config = EdgeConditionConfig.from_dict(
                raw_value,
                path=extend_path(self.path, f"edge[{self.id}->{node.id}].condition"),
            )
        condition_label = condition_config.display_label()
        condition_type = condition_config.type
        condition_serializable = condition_config.to_external_value()

        process_config = payload.pop("process_config", None)
        if process_config is None and payload.get("process") is not None:
            process_config = EdgeProcessorConfig.from_dict(
                payload.get("process"),
                path=extend_path(self.path, f"edge[{self.id}->{node.id}].process"),
            )
        process_serializable = process_config.to_external_value() if isinstance(process_config, EdgeProcessorConfig) else None
        process_type = process_config.type if isinstance(process_config, EdgeProcessorConfig) else None
        process_label = process_config.display_label() if isinstance(process_config, EdgeProcessorConfig) else None

        # Handle dynamic_config
        dynamic_config = payload.pop("dynamic_config", None)
        if dynamic_config is None and payload.get("dynamic") is not None:
            dynamic_config = DynamicEdgeConfig.from_dict(
                payload.get("dynamic"),
                path=extend_path(self.path, f"edge[{self.id}->{node.id}].dynamic"),
            )

        payload["condition"] = condition_serializable
        payload["condition_label"] = condition_label
        payload["condition_type"] = condition_type
        if process_serializable is not None:
            payload["process"] = process_serializable
            payload["process_label"] = process_label
            payload["process_type"] = process_type

        if existing:
            existing.config.update(payload)
            existing.trigger = trigger
            existing.condition = condition_label
            existing.condition_config = condition_config
            existing.condition_type = condition_type
            existing.carry_data = carry_data
            existing.keep_message = keep_message
            existing.clear_context = clear_context
            existing.clear_kept_context = clear_kept_context
            if isinstance(process_config, EdgeProcessorConfig):
                existing.process_config = process_config
                existing.process_type = process_type
            else:
                existing.process_config = None
                existing.process_type = None
            existing.dynamic_config = dynamic_config
        else:
            self._outgoing_edges.append(
                EdgeLink(
                    target=node,
                    config=payload,
                    trigger=trigger,
                    condition=condition_label,
                    condition_config=condition_config,
                    condition_type=condition_type,
                    carry_data=carry_data,
                    keep_message=keep_message,
                    clear_context=clear_context,
                    clear_kept_context=clear_kept_context,
                    process_config=process_config if isinstance(process_config, EdgeProcessorConfig) else None,
                    process_type=process_type,
                    dynamic_config=dynamic_config,
                )
            )

    def add_predecessor(self, node: "Node") -> None:
        if node not in self.predecessors:
            self.predecessors.append(node)

    def iter_outgoing_edges(self) -> Iterable[EdgeLink]:
        return tuple(self._outgoing_edges)

    def find_outgoing_edge(self, node_id: str) -> EdgeLink | None:
        for link in self._outgoing_edges:
            if link.target.id == node_id:
                return link
        return None

    def is_triggered(self) -> bool:
        if self.start_triggered:
            return True
        for predecessor in self.predecessors:
            for edge_link in predecessor.iter_outgoing_edges():
                if edge_link.target is self and edge_link.trigger and edge_link.triggered:
                    return True
        return False

    def reset_triggers(self) -> None:
        self.start_triggered = False
        for predecessor in self.predecessors:
            for edge_link in predecessor.iter_outgoing_edges():
                if edge_link.target is self:
                    edge_link.triggered = False

    def merge_vars(self, parent_vars: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        merged = dict(parent_vars or {})
        merged.update(self.vars)
        return merged
