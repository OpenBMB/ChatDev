"""Dynamic edge configuration for edge-level Map and Tree execution modes."""

from dataclasses import dataclass, field, replace
from typing import Any, Dict, Mapping

from entity.configs.base import (
    BaseConfig,
    ConfigError,
    ConfigFieldSpec,
    ChildKey,
    extend_path,
    require_mapping,
    require_str,
)
from entity.configs.dynamic_base import (
    SplitConfig,
    MapDynamicConfig,
    TreeDynamicConfig,
)
from entity.enum_options import enum_options_from_values
from utils.registry import Registry, RegistryError


# Local registry for edge-level dynamic types (reuses same type names)
dynamic_edge_type_registry = Registry("dynamic_edge_type")


def register_dynamic_edge_type(
    name: str,
    *,
    config_cls: type[BaseConfig],
    description: str | None = None,
) -> None:
    metadata = {"summary": description} if description else None
    dynamic_edge_type_registry.register(name, target=config_cls, metadata=metadata)


def get_dynamic_edge_type_config(name: str) -> type[BaseConfig]:
    entry = dynamic_edge_type_registry.get(name)
    config_cls = entry.load()
    if not isinstance(config_cls, type) or not issubclass(config_cls, BaseConfig):
        raise RegistryError(f"Entry '{name}' is not a BaseConfig subclass")
    return config_cls


def iter_dynamic_edge_type_registrations() -> Dict[str, type[BaseConfig]]:
    return {name: entry.load() for name, entry in dynamic_edge_type_registry.items()}


def iter_dynamic_edge_type_metadata() -> Dict[str, Dict[str, Any]]:
    return {name: dict(entry.metadata or {}) for name, entry in dynamic_edge_type_registry.items()}


@dataclass
class DynamicEdgeConfig(BaseConfig):
    """Dynamic configuration for edge-level Map and Tree execution modes.
    
    When configured on an edge, the target node will be dynamically expanded
    based on the split results. The split logic is applied to messages
    passing through this edge.
    
    Attributes:
        type: Dynamic mode type (map or tree)
        split: How to split the payload passing through this edge
        config: Mode-specific configuration (MapDynamicConfig or TreeDynamicConfig)
    """
    type: str
    split: SplitConfig = field(default_factory=lambda: SplitConfig())
    config: BaseConfig | None = None

    FIELD_SPECS = {
        "type": ConfigFieldSpec(
            name="type",
            display_name="Dynamic Type",
            type_hint="str",
            required=True,
            description="Dynamic execution mode (map or tree)",
        ),
        "split": ConfigFieldSpec(
            name="split",
            display_name="Split Strategy",
            type_hint="SplitConfig",
            required=False,
            description="How to split the edge payload into parallel execution units",
            child=SplitConfig,
        ),
        "config": ConfigFieldSpec(
            name="config",
            display_name="Dynamic Config",
            type_hint="object",
            required=False,
            description="Mode-specific configuration",
        ),
    }

    @classmethod
    def child_routes(cls) -> Dict[ChildKey, type[BaseConfig]]:
        return {
            ChildKey(field="config", value=name): config_cls
            for name, config_cls in iter_dynamic_edge_type_registrations().items()
        }

    @classmethod
    def field_specs(cls) -> Dict[str, ConfigFieldSpec]:
        specs = super().field_specs()
        type_spec = specs.get("type")
        if type_spec:
            registrations = iter_dynamic_edge_type_registrations()
            metadata = iter_dynamic_edge_type_metadata()
            type_names = list(registrations.keys())
            descriptions = {name: (metadata.get(name) or {}).get("summary") for name in type_names}
            specs["type"] = replace(
                type_spec,
                enum=type_names,
                enum_options=enum_options_from_values(type_names, descriptions),
            )
        return specs

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None, *, path: str) -> "DynamicEdgeConfig | None":
        if data is None:
            return None
        mapping = require_mapping(data, path)
        dynamic_type = require_str(mapping, "type", path)
        
        try:
            config_cls = get_dynamic_edge_type_config(dynamic_type)
        except RegistryError as exc:
            raise ConfigError(
                f"dynamic type must be one of {list(iter_dynamic_edge_type_registrations().keys())}",
                extend_path(path, "type"),
            ) from exc
        
        # Parse split at top level
        split_data = mapping.get("split")
        split = SplitConfig.from_dict(split_data, path=extend_path(path, "split"))
        
        # Parse mode-specific config
        config_data = mapping.get("config")
        config_path = extend_path(path, "config")
        
        config = config_cls.from_dict(config_data, path=config_path)
        
        return cls(type=dynamic_type, split=split, config=config, path=path)

    def is_map(self) -> bool:
        return self.type == "map"

    def is_tree(self) -> bool:
        return self.type == "tree"

    def as_map_config(self) -> MapDynamicConfig | None:
        return self.config if self.is_map() and isinstance(self.config, MapDynamicConfig) else None

    def as_tree_config(self) -> TreeDynamicConfig | None:
        return self.config if self.is_tree() and isinstance(self.config, TreeDynamicConfig) else None

    @property
    def max_parallel(self) -> int:
        """Get max_parallel from config."""
        if hasattr(self.config, "max_parallel"):
            return getattr(self.config, "max_parallel")
        return 10

    @property
    def group_size(self) -> int:
        """Get group_size (tree mode only, defaults to 3)."""
        if isinstance(self.config, TreeDynamicConfig):
            return self.config.group_size
        return 3


# Register dynamic edge types
register_dynamic_edge_type(
    "map",
    config_cls=MapDynamicConfig,
    description="Fan-out only: split into parallel units and collect results",
)
register_dynamic_edge_type(
    "tree",
    config_cls=TreeDynamicConfig,
    description="Fan-out and reduce: split into units, then iteratively reduce results",
)
