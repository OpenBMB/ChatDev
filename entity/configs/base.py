"""Shared helpers and base classes for configuration dataclasses."""

from dataclasses import dataclass, field, replace
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Sequence, TypeVar, ClassVar, Optional


TConfig = TypeVar("TConfig", bound="BaseConfig")


class ConfigError(ValueError):
    """Raised when configuration parsing or validation fails."""

    def __init__(self, message: str, path: str | None = None):
        self.path = path
        full_message = f"{path}: {message}" if path else message
        super().__init__(full_message)


@dataclass(frozen=True)
class RuntimeConstraint:
    """Represents a conditional requirement for configuration fields."""

    when: Mapping[str, Any]
    require: Sequence[str]
    message: str

    def to_json(self) -> Dict[str, Any]:
        return {
            "when": dict(self.when),
            "require": list(self.require),
            "message": self.message,
        }


@dataclass(frozen=True)
class ChildKey:
    """Identifies a conditional navigation target for nested schemas."""

    field: str
    value: Any | None = None
    # variant: str | None = None

    def matches(self, field: str, value: Any | None) -> bool:
        if self.field != field:
            return False
        # if self.variant is not None and self.variant != str(value):
        #     return False
        if self.value is None:
            return True
        return self.value == value

    def to_json(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"field": self.field}
        if self.value is not None:
            payload["value"] = self.value
        # if self.variant is not None:
        #     payload["variant"] = self.variant
        return payload


@dataclass(frozen=True)
class EnumOption:
    """Rich metadata for enum values shown in UI."""

    value: Any
    label: str | None = None
    description: str | None = None

    def to_json(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"value": self.value}
        if self.label:
            payload["label"] = self.label
        if self.description:
            payload["description"] = self.description
        return payload


@dataclass(frozen=True)
class ConfigFieldSpec:
    """Describes a single configuration field for schema export."""

    name: str
    type_hint: str
    required: bool = False
    display_name: str | None = None
    default: Any | None = None
    enum: Sequence[Any] | None = None
    enum_options: Sequence[EnumOption] | None = None
    description: str | None = None
    child: type["BaseConfig"] | None = None
    advance: bool = False
    # ui: Mapping[str, Any] | None = None

    def with_name(self, name: str) -> "ConfigFieldSpec":
        if self.name == name:
            return self
        return replace(self, name=name)

    def to_json(self) -> Dict[str, Any]:
        display = self.display_name or self.name
        data: Dict[str, Any] = {
            "name": self.name,
            "displayName": display,
            "type": self.type_hint,
            "required": self.required,
            "advance": self.advance,
        }
        if self.default is not None:
            data["default"] = self.default
        if self.enum is not None:
            data["enum"] = list(self.enum)
        if self.enum_options:
            data["enumOptions"] = [option.to_json() for option in self.enum_options]
        if self.description:
            data["description"] = self.description
        if self.child is not None:
            data["childNode"] = self.child.__name__
        # if self.ui:
        #     data["ui"] = dict(self.ui)
        return data


@dataclass(frozen=True)
class SchemaNode:
    """Serializable representation of a configuration node."""

    node: str
    fields: Sequence[ConfigFieldSpec]
    constraints: Sequence[RuntimeConstraint] = field(default_factory=list)

    def to_json(self) -> Dict[str, Any]:
        return {
            "node": self.node,
            "fields": [spec.to_json() for spec in self.fields],
            "constraints": [constraint.to_json() for constraint in self.constraints],
        }


@dataclass
class BaseConfig:
    """Base dataclass providing validation and schema hooks."""

    path: str

    # Class-level hooks populated by concrete configs.
    FIELD_SPECS: ClassVar[Dict[str, ConfigFieldSpec]] = {}
    CONSTRAINTS: ClassVar[Sequence[RuntimeConstraint]] = ()
    CHILD_ROUTES: ClassVar[Dict[ChildKey, type["BaseConfig"]]] = {}

    def __post_init__(self) -> None:  # pragma: no cover - thin wrapper
        self.validate()

    def validate(self) -> None:
        """Hook for subclasses to implement structural validation."""
        # Default implementation intentionally empty.
        return None

    @classmethod
    def field_specs(cls) -> Dict[str, ConfigFieldSpec]:
        return {name: spec.with_name(name) for name, spec in getattr(cls, "FIELD_SPECS", {}).items()}

    @classmethod
    def constraints(cls) -> Sequence[RuntimeConstraint]:
        return tuple(getattr(cls, "CONSTRAINTS", ()) or ())

    @classmethod
    def child_routes(cls) -> Dict[ChildKey, type["BaseConfig"]]:
        return dict(getattr(cls, "CHILD_ROUTES", {}) or {})

    @classmethod
    def resolve_child(cls, field: str, value: Any | None = None) -> type["BaseConfig"] | None:
        for key, target in cls.child_routes().items():
            if key.matches(field, value):
                return target
        return None

    def as_config(self, expected_type: type[TConfig], *, attr: str = "config") -> TConfig | None:
        """Return the nested config stored under *attr* if it matches the expected type."""
        value = getattr(self, attr, None)
        if isinstance(value, expected_type):
            return value
        return None

    @classmethod
    def collect_schema(cls) -> SchemaNode:
        return SchemaNode(node=cls.__name__, fields=list(cls.field_specs().values()), constraints=list(cls.constraints()))

    @classmethod
    def example(cls) -> Dict[str, Any]:
        """Placeholder for future example export support."""
        return {}


T = TypeVar("T")


def ensure_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, (tuple, set)):
        return list(value)
    return [value]


def ensure_dict(value: Mapping[str, Any] | None) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, MutableMapping):
        return dict(value)
    if isinstance(value, Mapping):
        return dict(value)
    raise ConfigError("expected mapping", path=str(value))


def require_mapping(data: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(data, Mapping):
        raise ConfigError("expected mapping", path)
    return data


def require_str(data: Mapping[str, Any], key: str, path: str, *, allow_empty: bool = False) -> str:
    value = data.get(key)
    key_path = f"{path}.{key}" if path else key
    if not isinstance(value, str):
        raise ConfigError("expected string", key_path)
    if not allow_empty and not value.strip():
        raise ConfigError("expected non-empty string", key_path)
    return value


def optional_str(data: Mapping[str, Any], key: str, path: str) -> str | None:
    value = data.get(key)
    if value is None or value == "":
        return None
    key_path = f"{path}.{key}" if path else key
    if not isinstance(value, str):
        raise ConfigError("expected string", key_path)
    return value


def require_bool(data: Mapping[str, Any], key: str, path: str) -> bool:
    value = data.get(key)
    key_path = f"{path}.{key}" if path else key
    if not isinstance(value, bool):
        raise ConfigError("expected boolean", key_path)
    return value


def optional_bool(data: Mapping[str, Any], key: str, path: str, *, default: bool | None = None) -> bool | None:
    if key not in data:
        return default
    value = data[key]
    key_path = f"{path}.{key}" if path else key
    if not isinstance(value, bool):
        raise ConfigError("expected boolean", key_path)
    return value


def optional_dict(data: Mapping[str, Any], key: str, path: str) -> Dict[str, Any] | None:
    if key not in data or data[key] is None:
        return None
    value = data[key]
    key_path = f"{path}.{key}" if path else key
    if not isinstance(value, Mapping):
        raise ConfigError("expected mapping", key_path)
    return dict(value)


def extend_path(path: str, suffix: str) -> str:
    if not path:
        return suffix
    if suffix.startswith("["):
        return f"{path}{suffix}"
    return f"{path}.{suffix}"
