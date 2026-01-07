"""Subgraph node configuration and registry helpers."""

from dataclasses import dataclass, replace
from typing import Any, Dict, Mapping

from entity.enums import LogLevel
from entity.enum_options import enum_options_for, enum_options_from_values
from entity.configs.base import (
    BaseConfig,
    ConfigError,
    ConfigFieldSpec,
    ChildKey,
    require_mapping,
    require_str,
    extend_path,
)
from entity.configs.edge.edge import EdgeConfig
from entity.configs.node.memory import MemoryStoreConfig
from utils.registry import Registry, RegistryError


subgraph_source_registry = Registry("subgraph_source")


def register_subgraph_source(
    name: str,
    *,
    config_cls: type[BaseConfig],
    description: str | None = None,
) -> None:
    """Register a subgraph source configuration class."""

    metadata = {"summary": description} if description else None
    subgraph_source_registry.register(name, target=config_cls, metadata=metadata)


def get_subgraph_source_config(name: str) -> type[BaseConfig]:
    entry = subgraph_source_registry.get(name)
    config_cls = entry.load()
    if not isinstance(config_cls, type) or not issubclass(config_cls, BaseConfig):
        raise RegistryError(f"Entry '{name}' is not a BaseConfig subclass")
    return config_cls


def iter_subgraph_source_registrations() -> Dict[str, type[BaseConfig]]:
    return {name: entry.load() for name, entry in subgraph_source_registry.items()}


def iter_subgraph_source_metadata() -> Dict[str, Dict[str, Any]]:
    return {name: dict(entry.metadata or {}) for name, entry in subgraph_source_registry.items()}


@dataclass
class SubgraphFileConfig(BaseConfig):
    file_path: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "SubgraphFileConfig":
        mapping = require_mapping(data, path)
        file_path = require_str(mapping, "path", path)
        return cls(file_path=file_path, path=path)

    FIELD_SPECS = {
        "path": ConfigFieldSpec(
            name="path",
            display_name="Subgraph File Path",
            type_hint="str",
            required=True,
            description="Subgraph file path (relative to yaml_instance/ or absolute path)",
        ),
    }


@dataclass
class SubgraphInlineConfig(BaseConfig):
    graph: Dict[str, Any]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "SubgraphInlineConfig":
        mapping = require_mapping(data, path)
        return cls(graph=dict(mapping), path=path)

    def validate(self) -> None:
        if "nodes" not in self.graph:
            raise ConfigError("subgraph config must define nodes", extend_path(self.path, "nodes"))
        if "edges" not in self.graph:
            raise ConfigError("subgraph config must define edges", extend_path(self.path, "edges"))

    FIELD_SPECS = {
        "id": ConfigFieldSpec(
            name="id",
            display_name="Subgraph ID",
            type_hint="str",
            required=True,
            description="Subgraph identifier",
        ),
        "description": ConfigFieldSpec(
            name="description",
            display_name="Subgraph Description",
            type_hint="str",
            required=False,
            description="Describe the subgraph's responsibility, trigger conditions, and success criteria so reviewers know when to call it.",
        ),
        "log_level": ConfigFieldSpec(
            name="log_level",
            display_name="Log Level",
            type_hint="enum:LogLevel",
            required=False,
            default=LogLevel.INFO.value,
            enum=[lvl.value for lvl in LogLevel],
            description="Subgraph runtime log level",
            enum_options=enum_options_for(LogLevel),
        ),
        "is_majority_voting": ConfigFieldSpec(
            name="is_majority_voting",
            display_name="Majority Voting",
            type_hint="bool",
            required=False,
            default=False,
            description="Whether to perform majority voting on node results",
        ),
        "nodes": ConfigFieldSpec(
            name="nodes",
            display_name="Node List",
            type_hint="list[Node]",
            required=True,
            description="Subgraph node list, must contain at least one node",
        ),
        "edges": ConfigFieldSpec(
            name="edges",
            display_name="Edge List",
            type_hint="list[EdgeConfig]",
            required=True,
            description="Subgraph edge list",
            child=EdgeConfig,
        ),
        "memory": ConfigFieldSpec(
            name="memory",
            display_name="Memory Stores",
            type_hint="list[MemoryStoreConfig]",
            required=False,
            description="Provide a list of memory stores if this subgraph needs dedicated stores; leave empty to inherit parent graph stores.",
            child=MemoryStoreConfig,
        ),
        "vars": ConfigFieldSpec(
            name="vars",
            display_name="Variables",
            type_hint="dict[str, Any]",
            required=False,
            default={},
            description="Variables passed to subgraph nodes",
        ),
        "organization": ConfigFieldSpec(
            name="organization",
            display_name="Organization",
            type_hint="str",
            required=False,
            description="Subgraph organization/team identifier",
        ),
        "initial_instruction": ConfigFieldSpec(
            name="initial_instruction",
            display_name="Initial Instruction",
            type_hint="str",
            required=False,
            description="Subgraph level initial instruction",
        ),
        "start": ConfigFieldSpec(
            name="start",
            display_name="Start Node",
            type_hint="str | list[str]",
            required=False,
            description="Start node ID list (entry list executed at subgraph start; not recommended to edit manually)",
        ),
        "end": ConfigFieldSpec(
            name="end",
            display_name="End Node",
            type_hint="str | list[str]",
            required=False,
            description="End node ID list (used to collect final subgraph output, not part of execution logic). This is an ordered list: earlier nodes are checked first; the first with output becomes the subgraph output, otherwise continue down the list.",
        ),
    }

    @classmethod
    def field_specs(cls) -> Dict[str, ConfigFieldSpec]:
        specs = super().field_specs()
        nodes_spec = specs.get("nodes")
        if nodes_spec:
            from entity.configs.node.node import Node

            specs["nodes"] = replace(nodes_spec, child=Node)
        return specs


@dataclass
class SubgraphConfig(BaseConfig):
    type: str
    config: BaseConfig | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "SubgraphConfig":
        mapping = require_mapping(data, path)
        source_type = require_str(mapping, "type", path)
        if "vars" in mapping and mapping["vars"]:
            raise ConfigError("vars is only allowed at root level (DesignConfig.vars)", extend_path(path, "vars"))

        if "config" not in mapping or mapping["config"] is None:
            raise ConfigError("subgraph configuration requires 'config' block", extend_path(path, "config"))

        try:
            config_cls = get_subgraph_source_config(source_type)
        except RegistryError as exc:
            raise ConfigError(
                f"subgraph.type must be one of {list(iter_subgraph_source_registrations().keys())}",
                extend_path(path, "type"),
            ) from exc
        config_obj = config_cls.from_dict(mapping["config"], path=extend_path(path, "config"))

        return cls(type=source_type, config=config_obj, path=path)

    def validate(self) -> None:
        if not self.config:
            raise ConfigError("subgraph config missing", extend_path(self.path, "config"))
        if hasattr(self.config, "validate"):
            self.config.validate()

    FIELD_SPECS = {
        "type": ConfigFieldSpec(
            name="type",
            display_name="Subgraph Source Type",
            type_hint="str",
            required=True,
            description="Registered subgraph source such as 'config' or 'file' (see subgraph_source_registry).",
        ),
        "config": ConfigFieldSpec(
            name="config",
            display_name="Subgraph Configuration",
            type_hint="object",
            required=True,
            description="Payload interpreted by the chosen type—for example inline graph schema for 'config' or file path payload for 'file'.",
        ),
    }

    @classmethod
    def child_routes(cls) -> Dict[ChildKey, type[BaseConfig]]:
        return {
            ChildKey(field="config", value=name): config_cls
            for name, config_cls in iter_subgraph_source_registrations().items()
        }

    @classmethod
    def field_specs(cls) -> Dict[str, ConfigFieldSpec]:
        specs = super().field_specs()
        type_spec = specs.get("type")
        if type_spec:
            registrations = iter_subgraph_source_registrations()
            metadata = iter_subgraph_source_metadata()
            names = list(registrations.keys())
            descriptions = {
                name: (metadata.get(name) or {}).get("summary") for name in names
            }
            specs["type"] = replace(
                type_spec,
                enum=names,
                enum_options=enum_options_from_values(names, descriptions, preserve_label_case=True),
            )
        return specs
