"""Registry helpers for pluggable edge condition managers."""

from dataclasses import dataclass
from importlib import import_module
from typing import Any, Dict, Type

from schema_registry import register_edge_condition_schema
from utils.registry import Registry, RegistryEntry, RegistryError
from entity.configs.edge.edge_condition import EdgeConditionConfig, EdgeConditionTypeConfig
from .base import EdgeConditionManager, ConditionFactoryContext
from ...node.executor import ExecutionContext


@dataclass(slots=True)
class EdgeConditionRegistration:
    """Registry entry describing a pluggable condition type."""

    name: str
    config_cls: Type["EdgeConditionTypeConfig"]
    manager_cls: Type["EdgeConditionManager[Any]"]
    summary: str | None = None


edge_condition_registry = Registry("edge_condition_type")
_BUILTINS_LOADED = False


def _ensure_builtins_loaded() -> None:
    global _BUILTINS_LOADED
    if not _BUILTINS_LOADED:
        import_module("runtime.edge.conditions.builtin_types")
        _BUILTINS_LOADED = True


def register_edge_condition(
    name: str,
    *,
    config_cls: Type["EdgeConditionTypeConfig"],
    manager_cls: Type["EdgeConditionManager[Any]"],
    summary: str | None = None,
) -> None:
    """Register a manager class that encapsulates edge processing logic."""
    if name in edge_condition_registry.names():
        raise RegistryError(f"Edge condition type '{name}' already registered")
    entry = EdgeConditionRegistration(
        name=name,
        config_cls=config_cls,
        manager_cls=manager_cls,
        summary=summary,
    )
    edge_condition_registry.register(name, target=entry)
    register_edge_condition_schema(name, config_cls=config_cls, summary=summary)


def get_edge_condition_registration(name: str) -> EdgeConditionRegistration:
    """Retrieve a registered condition type."""
    _ensure_builtins_loaded()
    entry: RegistryEntry = edge_condition_registry.get(name)
    registration = entry.load()
    if not isinstance(registration, EdgeConditionRegistration):
        raise RegistryError(f"Entry '{name}' is not an EdgeConditionRegistration")
    return registration


def iter_edge_condition_registrations() -> Dict[str, EdgeConditionRegistration]:
    """Iterate over registered condition types."""
    _ensure_builtins_loaded()
    return {name: entry.load() for name, entry in edge_condition_registry.items()}


def build_edge_condition_manager(
    condition: "EdgeConditionConfig",
    context: ConditionFactoryContext,
    execution_context: ExecutionContext
) -> "EdgeConditionManager[Any]":
    """Instantiate the manager responsible for a specific edge."""
    registration = get_edge_condition_registration(condition.type)
    manager_cls = registration.manager_cls
    if not manager_cls:
        raise RegistryError(
            f"Edge condition type '{condition.type}' does not provide a manager implementation"
        )
    return manager_cls(condition.config, context, execution_context)


__all__ = [
    "EdgeConditionRegistration",
    "register_edge_condition",
    "get_edge_condition_registration",
    "iter_edge_condition_registrations",
    "build_edge_condition_manager",
]
