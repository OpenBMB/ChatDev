"""Registry for memory store implementations."""

from dataclasses import dataclass
from importlib import import_module
from typing import Any, Callable, Dict, Type

from schema_registry import register_memory_store_schema
from utils.registry import Registry, RegistryEntry, RegistryError
from entity.configs import MemoryStoreConfig
from runtime.node.agent.memory.memory_base import MemoryBase

memory_store_registry = Registry("memory_store")
_BUILTINS_LOADED = False

@dataclass(slots=True)
class MemoryStoreRegistration:
    name: str
    config_cls: Type[Any]
    factory: Callable[["MemoryStoreConfig"], "MemoryBase"]
    summary: str | None = None


def _ensure_builtins_loaded() -> None:
    global _BUILTINS_LOADED
    if not _BUILTINS_LOADED:
        import_module("runtime.node.agent.memory.builtin_stores")
        _BUILTINS_LOADED = True


def register_memory_store(
    name: str,
    *,
    config_cls: Type[Any],
    factory: Callable[["MemoryStoreConfig"], "MemoryBase"],
    summary: str | None = None,
) -> None:
    if name in memory_store_registry.names():
        raise RegistryError(f"Memory store '{name}' already registered")
    entry = MemoryStoreRegistration(name=name, config_cls=config_cls, factory=factory, summary=summary)
    memory_store_registry.register(name, target=entry)
    register_memory_store_schema(name, config_cls=config_cls, summary=summary)


def get_memory_store_registration(name: str) -> MemoryStoreRegistration:
    _ensure_builtins_loaded()
    entry: RegistryEntry = memory_store_registry.get(name)
    registration = entry.load()
    if not isinstance(registration, MemoryStoreRegistration):
        raise RegistryError(f"Entry '{name}' is not a MemoryStoreRegistration")
    return registration


def iter_memory_store_registrations() -> Dict[str, MemoryStoreRegistration]:
    _ensure_builtins_loaded()
    return {name: entry.load() for name, entry in memory_store_registry.items()}


__all__ = [
    "memory_store_registry",
    "MemoryStoreRegistration",
    "register_memory_store",
    "get_memory_store_registration",
    "iter_memory_store_registrations",
]
