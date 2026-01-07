"""Thinking configuration models."""

from dataclasses import dataclass, replace
from typing import Any, Dict, Mapping

from entity.enum_options import enum_options_from_values
from schema_registry import (
    SchemaLookupError,
    get_thinking_schema,
    iter_thinking_schemas,
)

from entity.configs.base import BaseConfig, ConfigError, ConfigFieldSpec, ChildKey, extend_path, require_mapping, require_str


@dataclass
class ReflectionThinkingConfig(BaseConfig):
    reflection_prompt: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "ReflectionThinkingConfig":
        mapping = require_mapping(data, path)
        prompt = require_str(mapping, "reflection_prompt", path)
        return cls(reflection_prompt=prompt, path=path)

    FIELD_SPECS = {
        "reflection_prompt": ConfigFieldSpec(
            name="reflection_prompt",
            display_name="Reflection Prompt",
            type_hint="str",
            required=True,
            description="Prompt used for reflection in reflection mode",
        )
    }


@dataclass
class ThinkingConfig(BaseConfig):
    type: str
    config: BaseConfig | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "ThinkingConfig":
        mapping = require_mapping(data, path)
        thinking_type = require_str(mapping, "type", path)
        try:
            schema = get_thinking_schema(thinking_type)
        except SchemaLookupError as exc:
            raise ConfigError(f"unsupported thinking type '{thinking_type}'", extend_path(path, "type")) from exc

        if "config" not in mapping or mapping["config"] is None:
            raise ConfigError("thinking config requires config block", extend_path(path, "config"))

        config_obj = schema.config_cls.from_dict(mapping["config"], path=extend_path(path, "config"))
        return cls(type=thinking_type, config=config_obj, path=path)

    FIELD_SPECS = {
        "type": ConfigFieldSpec(
            name="type",
            display_name="Thinking Mode",
            type_hint="str",
            required=True,
            description="Thinking mode type",
        ),
        "config": ConfigFieldSpec(
            name="config",
            display_name="Thinking Configuration",
            type_hint="object",
            required=True,
            description="Thinking mode configuration body",
        ),
    }

    @classmethod
    def child_routes(cls) -> dict[ChildKey, type[BaseConfig]]:
        return {
            ChildKey(field="config", value=name): schema.config_cls
            for name, schema in iter_thinking_schemas().items()
        }

    @classmethod
    def field_specs(cls) -> Dict[str, ConfigFieldSpec]:
        specs = super().field_specs()
        type_spec = specs.get("type")
        if type_spec:
            registrations = iter_thinking_schemas()
            names = list(registrations.keys())
            descriptions = {name: schema.summary for name, schema in registrations.items()}
            specs["type"] = replace(
                type_spec,
                enum=names,
                enum_options=enum_options_from_values(names, descriptions, preserve_label_case=True),
            )
        return specs
