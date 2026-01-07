"""Registry helpers for pluggable workflow node types."""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Type

from schema_registry import register_node_schema
from utils.registry import Registry, RegistryEntry, RegistryError


node_registry = Registry("node_type")
_BUILTINS_LOADED = False


def _ensure_builtins_loaded() -> None:
    global _BUILTINS_LOADED
    if not _BUILTINS_LOADED:
        from importlib import import_module

        import_module("runtime.node.builtin_nodes")
        _BUILTINS_LOADED = True


@dataclass(slots=True)
class NodeCapabilities:
    default_role_field: str | None = None
    exposes_tools: bool = False
    resource_key: str | None = None
    resource_limit: int | None = None


@dataclass(slots=True)
class NodeRegistration:
    name: str
    config_cls: Type[Any]
    executor_cls: Type[Any]
    capabilities: NodeCapabilities = field(default_factory=NodeCapabilities)
    executor_factory: Callable[..., Any] | None = None
    summary: str | None = None

    def build_executor(self, context: Any, *, subgraphs: Dict[str, Any] | None = None) -> Any:
        if self.executor_factory:
            return self.executor_factory(context, subgraphs=subgraphs)
        return self.executor_cls(context)


def register_node_type(
    name: str,
    *,
    config_cls: Type[Any],
    executor_cls: Type[Any],
    capabilities: NodeCapabilities | None = None,
    executor_factory: Callable[..., Any] | None = None,
    summary: str | None = None,
) -> None:
    if name in node_registry.names():
        raise RegistryError(f"Node type '{name}' already registered")

    entry = NodeRegistration(
        name=name,
        config_cls=config_cls,
        executor_cls=executor_cls,
        capabilities=capabilities or NodeCapabilities(),
        executor_factory=executor_factory,
        summary=summary,
    )
    node_registry.register(name, target=entry)
    register_node_schema(name, config_cls=config_cls, summary=summary)


def get_node_registration(name: str) -> NodeRegistration:
    _ensure_builtins_loaded()
    entry: RegistryEntry = node_registry.get(name)
    registration = entry.load()
    if not isinstance(registration, NodeRegistration):
        raise RegistryError(f"Registry entry '{name}' is not a NodeRegistration")
    return registration


def iter_node_registrations() -> Dict[str, NodeRegistration]:
    _ensure_builtins_loaded()
    return {name: entry.load() for name, entry in node_registry.items()}
