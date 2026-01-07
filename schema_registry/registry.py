"""Schema registries for entity-layer configuration classes."""

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, MutableMapping, Type
from entity.configs.base import BaseConfig


class SchemaLookupError(RuntimeError):
    """Raised when a requested schema spec is not registered."""


class SchemaRegistrationError(RuntimeError):
    """Raised when schema registration is inconsistent."""


@dataclass
class NodeSchemaSpec:
    name: str
    config_cls: Type["BaseConfig"]
    summary: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EdgeConditionSchemaSpec:
    name: str
    config_cls: Type["BaseConfig"]
    summary: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EdgeProcessorSchemaSpec:
    name: str
    config_cls: Type["BaseConfig"]
    summary: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryStoreSchemaSpec:
    name: str
    config_cls: Type["BaseConfig"]
    summary: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ThinkingSchemaSpec:
    name: str
    config_cls: Type["BaseConfig"]
    summary: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelProviderSchemaSpec:
    name: str
    label: str | None = None
    summary: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)


_node_schemas: Dict[str, NodeSchemaSpec] = {}
_edge_condition_schemas: Dict[str, EdgeConditionSchemaSpec] = {}
_edge_processor_schemas: Dict[str, EdgeProcessorSchemaSpec] = {}
_edge_processor_builtins_loaded = False
_memory_store_schemas: Dict[str, MemoryStoreSchemaSpec] = {}
_thinking_schemas: Dict[str, ThinkingSchemaSpec] = {}
_model_provider_schemas: Dict[str, ModelProviderSchemaSpec] = {}


def _update_metadata(target: MutableMapping[str, Any], new_items: Mapping[str, Any] | None) -> None:
    if not new_items:
        return
    target.update({key: value for key, value in new_items.items() if value is not None})


def register_node_schema(
    name: str,
    *,
    config_cls: Type["BaseConfig"],
    summary: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> NodeSchemaSpec:
    spec = _node_schemas.get(name)
    if spec:
        if spec.config_cls is not config_cls:
            raise SchemaRegistrationError(
                f"Node schema '{name}' already registered with a different config class"
            )
        if summary:
            spec.summary = summary
        _update_metadata(spec.metadata, metadata)
        return spec
    spec = NodeSchemaSpec(name=name, config_cls=config_cls, summary=summary)
    _update_metadata(spec.metadata, metadata)
    _node_schemas[name] = spec
    return spec


def iter_node_schemas() -> Dict[str, NodeSchemaSpec]:
    return dict(_node_schemas)


def get_node_schema(name: str) -> NodeSchemaSpec:
    try:
        return _node_schemas[name]
    except KeyError as exc:  # pragma: no cover - defensive guard
        raise SchemaLookupError(f"Node schema '{name}' is not registered") from exc


def register_edge_condition_schema(
    name: str,
    *,
    config_cls: Type["BaseConfig"],
    summary: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> EdgeConditionSchemaSpec:
    spec = _edge_condition_schemas.get(name)
    if spec:
        if spec.config_cls is not config_cls:
            raise SchemaRegistrationError(
                f"Edge condition schema '{name}' already registered with a different config class"
            )
        if summary:
            spec.summary = summary
        _update_metadata(spec.metadata, metadata)
        return spec
    spec = EdgeConditionSchemaSpec(name=name, config_cls=config_cls, summary=summary)
    _update_metadata(spec.metadata, metadata)
    _edge_condition_schemas[name] = spec
    return spec


def iter_edge_condition_schemas() -> Dict[str, EdgeConditionSchemaSpec]:
    return dict(_edge_condition_schemas)


def get_edge_condition_schema(name: str) -> EdgeConditionSchemaSpec:
    try:
        return _edge_condition_schemas[name]
    except KeyError as exc:  # pragma: no cover
        raise SchemaLookupError(f"Edge condition schema '{name}' is not registered") from exc


def register_edge_processor_schema(
    name: str,
    *,
    config_cls: Type["BaseConfig"],
    summary: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> EdgeProcessorSchemaSpec:
    spec = _edge_processor_schemas.get(name)
    if spec:
        if spec.config_cls is not config_cls:
            raise SchemaRegistrationError(
                f"Edge processor schema '{name}' already registered with a different config class"
            )
        if summary:
            spec.summary = summary
        _update_metadata(spec.metadata, metadata)
        return spec
    spec = EdgeProcessorSchemaSpec(name=name, config_cls=config_cls, summary=summary)
    _update_metadata(spec.metadata, metadata)
    _edge_processor_schemas[name] = spec
    return spec


def iter_edge_processor_schemas() -> Dict[str, EdgeProcessorSchemaSpec]:
    _ensure_edge_processor_builtins_loaded()
    return dict(_edge_processor_schemas)


def get_edge_processor_schema(name: str) -> EdgeProcessorSchemaSpec:
    _ensure_edge_processor_builtins_loaded()
    try:
        return _edge_processor_schemas[name]
    except KeyError as exc:  # pragma: no cover
        raise SchemaLookupError(f"Edge processor schema '{name}' is not registered") from exc


def register_memory_store_schema(
    name: str,
    *,
    config_cls: Type["BaseConfig"],
    summary: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> MemoryStoreSchemaSpec:
    spec = _memory_store_schemas.get(name)
    if spec:
        if spec.config_cls is not config_cls:
            raise SchemaRegistrationError(
                f"Memory store schema '{name}' already registered with a different config class"
            )
        if summary:
            spec.summary = summary
        _update_metadata(spec.metadata, metadata)
        return spec
    spec = MemoryStoreSchemaSpec(name=name, config_cls=config_cls, summary=summary)
    _update_metadata(spec.metadata, metadata)
    _memory_store_schemas[name] = spec
    return spec


def iter_memory_store_schemas() -> Dict[str, MemoryStoreSchemaSpec]:
    return dict(_memory_store_schemas)


def get_memory_store_schema(name: str) -> MemoryStoreSchemaSpec:
    try:
        return _memory_store_schemas[name]
    except KeyError as exc:  # pragma: no cover
        raise SchemaLookupError(f"Memory store schema '{name}' is not registered") from exc


def register_thinking_schema(
    name: str,
    *,
    config_cls: Type["BaseConfig"],
    summary: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> ThinkingSchemaSpec:
    spec = _thinking_schemas.get(name)
    if spec:
        if spec.config_cls is not config_cls:
            raise SchemaRegistrationError(
                f"Thinking schema '{name}' already registered with a different config class"
            )
        if summary:
            spec.summary = summary
        _update_metadata(spec.metadata, metadata)
        return spec
    spec = ThinkingSchemaSpec(name=name, config_cls=config_cls, summary=summary)
    _update_metadata(spec.metadata, metadata)
    _thinking_schemas[name] = spec
    return spec


def iter_thinking_schemas() -> Dict[str, ThinkingSchemaSpec]:
    return dict(_thinking_schemas)


def get_thinking_schema(name: str) -> ThinkingSchemaSpec:
    try:
        return _thinking_schemas[name]
    except KeyError as exc:  # pragma: no cover
        raise SchemaLookupError(f"Thinking schema '{name}' is not registered") from exc


def register_model_provider_schema(
    name: str,
    *,
    label: str | None = None,
    summary: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> ModelProviderSchemaSpec:
    spec = _model_provider_schemas.get(name)
    if spec:
        if label:
            spec.label = label
        if summary:
            spec.summary = summary
        _update_metadata(spec.metadata, metadata)
        return spec
    spec = ModelProviderSchemaSpec(name=name, label=label, summary=summary)
    _update_metadata(spec.metadata, metadata)
    _model_provider_schemas[name] = spec
    return spec


def iter_model_provider_schemas() -> Dict[str, ModelProviderSchemaSpec]:
    return dict(_model_provider_schemas)


def get_model_provider_schema(name: str) -> ModelProviderSchemaSpec:
    try:
        return _model_provider_schemas[name]
    except KeyError as exc:  # pragma: no cover
        raise SchemaLookupError(f"Model provider schema '{name}' is not registered") from exc

def _ensure_edge_processor_builtins_loaded() -> None:
    global _edge_processor_builtins_loaded
    if _edge_processor_builtins_loaded:
        return
    try:
        import runtime.edge.processors.builtin_types  # noqa: F401
    except Exception:
        pass
    _edge_processor_builtins_loaded = True
