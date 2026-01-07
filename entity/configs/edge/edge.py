"""Edge configuration dataclasses."""

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping

from entity.configs.base import (
    BaseConfig,
    ConfigFieldSpec,
    require_mapping,
    require_str,
    optional_bool,
    extend_path,
)
from .edge_condition import EdgeConditionConfig
from .edge_processor import EdgeProcessorConfig
from .dynamic_edge_config import DynamicEdgeConfig


@dataclass
class EdgeConfig(BaseConfig):
    source: str
    target: str
    trigger: bool = True
    condition: EdgeConditionConfig | None = None
    carry_data: bool = True
    keep_message: bool = False
    clear_context: bool = False
    clear_kept_context: bool = False
    process: EdgeProcessorConfig | None = None
    dynamic: DynamicEdgeConfig | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "EdgeConfig":
        mapping = require_mapping(data, path)
        source = require_str(mapping, "from", path)
        target = require_str(mapping, "to", path)
        trigger_value = optional_bool(mapping, "trigger", path, default=True)
        carry_data_value = optional_bool(mapping, "carry_data", path, default=True)
        keep_message_value = optional_bool(mapping, "keep_message", path, default=False)
        clear_context_value = optional_bool(mapping, "clear_context", path, default=False)
        clear_kept_context_value = optional_bool(mapping, "clear_kept_context", path, default=False)
        condition_value = mapping.get("condition", "true")
        condition_cfg = EdgeConditionConfig.from_dict(condition_value, path=extend_path(path, "condition"))
        process_cfg = None
        if "process" in mapping and mapping["process"] is not None:
            process_cfg = EdgeProcessorConfig.from_dict(mapping["process"], path=extend_path(path, "process"))
        dynamic_cfg = None
        if "dynamic" in mapping and mapping["dynamic"] is not None:
            dynamic_cfg = DynamicEdgeConfig.from_dict(mapping["dynamic"], path=extend_path(path, "dynamic"))
        return cls(
            source=source,
            target=target,
            trigger=bool(trigger_value) if trigger_value is not None else True,
            condition=condition_cfg,
            carry_data=bool(carry_data_value) if carry_data_value is not None else True,
            keep_message=bool(keep_message_value) if keep_message_value is not None else False,
            clear_context=bool(clear_context_value) if clear_context_value is not None else False,
            clear_kept_context=bool(clear_kept_context_value) if clear_kept_context_value is not None else False,
            process=process_cfg,
            dynamic=dynamic_cfg,
            path=path,
        )

    FIELD_SPECS = {
        "from": ConfigFieldSpec(
            name="from",
            display_name="Source Node ID",
            type_hint="str",
            required=True,
            description="Source node ID of the edge",
        ),
        "to": ConfigFieldSpec(
            name="to",
            display_name="Target Node ID",
            type_hint="str",
            required=True,
            description="Target node ID of the edge",
        ),
        "trigger": ConfigFieldSpec(
            name="trigger",
            type_hint="bool",
            required=False,
            default=True,
            display_name="Can Trigger Successor",
            description="Whether this edge can trigger successor nodes",
            advance=True,
        ),
        "condition": ConfigFieldSpec(
            name="condition",
            type_hint="EdgeConditionConfig",
            required=False,
            display_name="Edge Condition",
            description="Edge condition configuration（type + config）",
            advance=True,
            child=EdgeConditionConfig,
        ),
        "carry_data": ConfigFieldSpec(
            name="carry_data",
            type_hint="bool",
            required=False,
            default=True,
            display_name="Pass Data to Target",
            description="Whether to pass data to the target node",
            advance=True,
        ),
        "keep_message": ConfigFieldSpec(
            name="keep_message",
            type_hint="bool",
            required=False,
            default=False,
            display_name="Keep Message Input",
            description="Whether to always keep this message input in the target node without being cleared",
            advance=True,
        ),
        "clear_context": ConfigFieldSpec(
            name="clear_context",
            type_hint="bool",
            required=False,
            default=False,
            display_name="Clear Context",
            description="Clear all incoming context messages without keep=True before passing new payload",
            advance=True,
        ),
        "clear_kept_context": ConfigFieldSpec(
            name="clear_kept_context",
            type_hint="bool",
            required=False,
            default=False,
            display_name="Clear Kept Context",
            description="Clear messages marked with keep=True before passing new payload",
            advance=True,
        ),
        "process": ConfigFieldSpec(
            name="process",
            type_hint="EdgeProcessorConfig",
            required=False,
            display_name="Payload Processor",
            description="Optional payload processor applied after the condition is met (regex extraction, custom functions, etc.)",
            advance=True,
            child=EdgeProcessorConfig,
        ),
        "dynamic": ConfigFieldSpec(
            name="dynamic",
            type_hint="DynamicEdgeConfig",
            required=False,
            display_name="Dynamic Expansion",
            description="Dynamic expansion configuration for edge-level Map (fan-out) or Tree (fan-out + reduce) modes. When set, the target node is dynamically expanded based on split results.",
            advance=True,
            child=DynamicEdgeConfig,
        ),
    }
