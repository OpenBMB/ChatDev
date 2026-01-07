"""Shared dynamic configuration classes for both node and edge level execution.

This module contains the base classes used by both node-level and edge-level
dynamic execution configurations to avoid circular imports.
"""

from dataclasses import dataclass, fields, replace
from typing import Any, ClassVar, Dict, Mapping, Optional, Type, TypeVar

from entity.configs.base import (
    BaseConfig,
    ChildKey,
    ConfigError,
    ConfigFieldSpec,
    extend_path,
    optional_bool,
    optional_str,
    require_mapping,
    require_str,
)
from entity.enum_options import enum_options_from_values


def _serialize_config(config: BaseConfig) -> Dict[str, Any]:
    """Serialize a config to dict, excluding the path field."""
    payload: Dict[str, Any] = {}
    for field_obj in fields(config):
        if field_obj.name == "path":
            continue
        payload[field_obj.name] = getattr(config, field_obj.name)
    return payload


class SplitTypeConfig(BaseConfig):
    """Base helper class for split type configs."""

    def display_label(self) -> str:
        return self.__class__.__name__

    def to_external_value(self) -> Any:
        return _serialize_config(self)


@dataclass
class MessageSplitConfig(SplitTypeConfig):
    """Configuration for message-based splitting.
    
    Each input message becomes one execution unit. No additional configuration needed.
    """

    FIELD_SPECS: ClassVar[Dict[str, ConfigFieldSpec]] = {}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None, *, path: str) -> "MessageSplitConfig":
        # No config needed for message split
        return cls(path=path)

    def display_label(self) -> str:
        return "message"


_NO_MATCH_DESCRIPTIONS = {
    "pass": "Leave the content unchanged when no match is found.",
    "empty": "Return empty content when no match is found.",
}


@dataclass
class RegexSplitConfig(SplitTypeConfig):
    """Configuration for regex-based splitting.
    
    Split content by regex pattern matches. Each match becomes one execution unit.
    
    Attributes:
        pattern: Python regular expression used to split content.
        group: Capture group name or index. Defaults to the entire match (group 0).
        case_sensitive: Whether the regex should be case sensitive.
        multiline: Enable multiline mode (re.MULTILINE).
        dotall: Enable dotall mode (re.DOTALL).
        on_no_match: Behavior when no match is found.
    """

    pattern: str = ""
    group: str | int | None = None
    case_sensitive: bool = True
    multiline: bool = False
    dotall: bool = False
    on_no_match: str = "pass"

    FIELD_SPECS = {
        "pattern": ConfigFieldSpec(
            name="pattern",
            display_name="Regex Pattern",
            type_hint="str",
            required=True,
            description="Python regular expression used to split content.",
        ),
        "group": ConfigFieldSpec(
            name="group",
            display_name="Capture Group",
            type_hint="str",
            required=False,
            description="Capture group name or index. Defaults to the entire match (group 0).",
        ),
        "case_sensitive": ConfigFieldSpec(
            name="case_sensitive",
            display_name="Case Sensitive",
            type_hint="bool",
            required=False,
            default=True,
            description="Whether the regex should be case sensitive.",
        ),
        "multiline": ConfigFieldSpec(
            name="multiline",
            display_name="Multiline Flag",
            type_hint="bool",
            required=False,
            default=False,
            description="Enable multiline mode (re.MULTILINE).",
            advance=True,
        ),
        "dotall": ConfigFieldSpec(
            name="dotall",
            display_name="Dotall Flag",
            type_hint="bool",
            required=False,
            default=False,
            description="Enable dotall mode (re.DOTALL).",
            advance=True,
        ),
        "on_no_match": ConfigFieldSpec(
            name="on_no_match",
            display_name="No Match Behavior",
            type_hint="enum",
            required=False,
            default="pass",
            enum=["pass", "empty"],
            description="Behavior when no match is found.",
            enum_options=enum_options_from_values(
                list(_NO_MATCH_DESCRIPTIONS.keys()),
                _NO_MATCH_DESCRIPTIONS,
                preserve_label_case=True,
            ),
            advance=True,
        ),
    }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "RegexSplitConfig":
        mapping = require_mapping(data, path)
        pattern = require_str(mapping, "pattern", path, allow_empty=False)
        
        group_value = mapping.get("group")
        group_normalized: str | int | None = None
        if group_value is not None:
            if isinstance(group_value, int):
                group_normalized = group_value
            elif isinstance(group_value, str):
                if group_value.isdigit():
                    group_normalized = int(group_value)
                else:
                    group_normalized = group_value
            else:
                raise ConfigError("group must be str or int", extend_path(path, "group"))
        
        case_sensitive = optional_bool(mapping, "case_sensitive", path, default=True)
        multiline = optional_bool(mapping, "multiline", path, default=False)
        dotall = optional_bool(mapping, "dotall", path, default=False)
        on_no_match = optional_str(mapping, "on_no_match", path) or "pass"
        
        if on_no_match not in {"pass", "empty"}:
            raise ConfigError("on_no_match must be 'pass' or 'empty'", extend_path(path, "on_no_match"))

        return cls(
            pattern=pattern,
            group=group_normalized,
            case_sensitive=True if case_sensitive is None else bool(case_sensitive),
            multiline=bool(multiline) if multiline is not None else False,
            dotall=bool(dotall) if dotall is not None else False,
            on_no_match=on_no_match,
            path=path,
        )

    def display_label(self) -> str:
        return f"regex({self.pattern})"


@dataclass
class JsonPathSplitConfig(SplitTypeConfig):
    """Configuration for JSON path-based splitting.
    
    Split content by extracting array items from JSON using a path expression.
    Each array item becomes one execution unit.
    
    Attributes:
        json_path: Simple dot-notation path to array (e.g., 'items', 'data.results').
    """

    json_path: str = ""

    FIELD_SPECS = {
        "json_path": ConfigFieldSpec(
            name="json_path",
            display_name="JSON Path",
            type_hint="str",
            required=True,
            description="Simple dot-notation path to array (e.g., 'items', 'data.results').",
        ),
    }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str) -> "JsonPathSplitConfig":
        mapping = require_mapping(data, path)
        json_path_value = require_str(mapping, "json_path", path, allow_empty=True)
        return cls(json_path=json_path_value, path=path)

    def display_label(self) -> str:
        return f"json_path({self.json_path})"


# Registry for split types
_SPLIT_TYPE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "message": {
        "config_cls": MessageSplitConfig,
        "summary": "Each input message becomes one unit",
    },
    "regex": {
        "config_cls": RegexSplitConfig,
        "summary": "Split by regex pattern matches",
    },
    "json_path": {
        "config_cls": JsonPathSplitConfig,
        "summary": "Split by JSON array path",
    },
}


def get_split_type_config(name: str) -> Type[SplitTypeConfig]:
    """Get the config class for a split type."""
    entry = _SPLIT_TYPE_REGISTRY.get(name)
    if not entry:
        raise ConfigError(f"Unknown split type: {name}", None)
    return entry["config_cls"]


def iter_split_type_registrations() -> Dict[str, Type[SplitTypeConfig]]:
    """Iterate over all registered split types."""
    return {name: entry["config_cls"] for name, entry in _SPLIT_TYPE_REGISTRY.items()}


def iter_split_type_metadata() -> Dict[str, Dict[str, Any]]:
    """Iterate over split type metadata."""
    return {name: {"summary": entry.get("summary")} for name, entry in _SPLIT_TYPE_REGISTRY.items()}


TSplitConfig = TypeVar("TSplitConfig", bound=SplitTypeConfig)


@dataclass
class SplitConfig(BaseConfig):
    """Configuration for how to split inputs into execution units.
    
    Attributes:
        type: Split strategy type (message, regex, json_path)
        config: Type-specific configuration
    """
    type: str = "message"
    config: SplitTypeConfig | None = None

    FIELD_SPECS = {
        "type": ConfigFieldSpec(
            name="type",
            display_name="Split Type",
            type_hint="str",
            required=True,
            default="message",
            description="Strategy for splitting inputs into parallel execution units",
        ),
        "config": ConfigFieldSpec(
            name="config",
            display_name="Split Config",
            type_hint="object",
            required=False,
            description="Type-specific split configuration",
        ),
    }

    @classmethod
    def child_routes(cls) -> Dict[ChildKey, Type[BaseConfig]]:
        return {
            ChildKey(field="config", value=name): config_cls
            for name, config_cls in iter_split_type_registrations().items()
        }

    @classmethod
    def field_specs(cls) -> Dict[str, ConfigFieldSpec]:
        specs = super().field_specs()
        type_spec = specs.get("type")
        if type_spec:
            registrations = iter_split_type_registrations()
            metadata = iter_split_type_metadata()
            type_names = list(registrations.keys())
            descriptions = {name: (metadata.get(name) or {}).get("summary") for name in type_names}
            specs["type"] = replace(
                type_spec,
                enum=type_names,
                enum_options=enum_options_from_values(type_names, descriptions),
            )
        return specs

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None, *, path: str) -> "SplitConfig":
        if data is None:
            # Default to message split
            return cls(type="message", config=MessageSplitConfig(path=extend_path(path, "config")), path=path)
        
        mapping = require_mapping(data, path)
        split_type = optional_str(mapping, "type", path) or "message"
        
        if split_type not in _SPLIT_TYPE_REGISTRY:
            raise ConfigError(
                f"split type must be one of {list(_SPLIT_TYPE_REGISTRY.keys())}, got '{split_type}'",
                extend_path(path, "type"),
            )
        
        config_cls = get_split_type_config(split_type)
        config_data = mapping.get("config")
        config_path = extend_path(path, "config")
        
        # For message type, config is optional
        if split_type == "message":
            config = config_cls.from_dict(config_data, path=config_path)
        else:
            if config_data is None:
                raise ConfigError(f"{split_type} split requires 'config' field", path)
            config = config_cls.from_dict(config_data, path=config_path)

        return cls(type=split_type, config=config, path=path)

    def display_label(self) -> str:
        if self.config:
            return self.config.display_label()
        return self.type

    def to_external_value(self) -> Any:
        return {
            "type": self.type,
            "config": self.config.to_external_value() if self.config else {},
        }

    def as_split_config(self, expected_type: Type[TSplitConfig]) -> TSplitConfig | None:
        """Return the nested config if it matches the expected type."""
        if isinstance(self.config, expected_type):
            return self.config
        return None

    # Convenience properties for backward compatibility and easy access
    @property
    def pattern(self) -> Optional[str]:
        """Get regex pattern if this is a regex split."""
        if isinstance(self.config, RegexSplitConfig):
            return self.config.pattern
        return None

    @property
    def json_path(self) -> Optional[str]:
        """Get json_path if this is a json_path split."""
        if isinstance(self.config, JsonPathSplitConfig):
            return self.config.json_path
        return None


@dataclass
class MapDynamicConfig(BaseConfig):
    """Configuration for Map dynamic mode (fan-out only).
    
    Map mode is similar to passthrough - minimal config required.
    
    Attributes:
        max_parallel: Maximum concurrent executions
    """
    max_parallel: int = 10

    FIELD_SPECS = {
        "max_parallel": ConfigFieldSpec(
            name="max_parallel",
            display_name="Max Parallel",
            type_hint="int",
            required=False,
            default=10,
            description="Maximum number of parallel executions",
        ),
    }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None, *, path: str) -> "MapDynamicConfig":
        if data is None:
            return cls(path=path)
        mapping = require_mapping(data, path)
        max_parallel = int(mapping.get("max_parallel", 10))
        return cls(max_parallel=max_parallel, path=path)


@dataclass
class TreeDynamicConfig(BaseConfig):
    """Configuration for Tree dynamic mode (fan-out and reduce).
    
    Attributes:
        group_size: Number of items per group in reduction
        max_parallel: Maximum concurrent executions per layer
    """
    group_size: int = 3
    max_parallel: int = 10

    FIELD_SPECS = {
        "group_size": ConfigFieldSpec(
            name="group_size",
            display_name="Group Size",
            type_hint="int",
            required=False,
            default=3,
            description="Number of items per group during reduction",
        ),
        "max_parallel": ConfigFieldSpec(
            name="max_parallel",
            display_name="Max Parallel",
            type_hint="int",
            required=False,
            default=10,
            description="Maximum concurrent executions per layer",
        ),
    }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None, *, path: str) -> "TreeDynamicConfig":
        if data is None:
            return cls(path=path)
        mapping = require_mapping(data, path)
        group_size = int(mapping.get("group_size", 3))
        if group_size < 2:
            raise ConfigError("group_size must be at least 2", extend_path(path, "group_size"))
        max_parallel = int(mapping.get("max_parallel", 10))
        return cls(group_size=group_size, max_parallel=max_parallel, path=path)
