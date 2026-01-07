"""Registry for thinking managers."""

from dataclasses import dataclass
from importlib import import_module
from typing import Any, Dict, Type

from schema_registry import register_thinking_schema
from utils.registry import Registry, RegistryEntry, RegistryError
from runtime.node.agent.thinking.thinking_manager import ThinkingManagerBase

thinking_registry = Registry("thinking_mode")
_BUILTINS_LOADED = False

@dataclass(slots=True)
class ThinkingRegistration:
    name: str
    config_cls: Type[Any]
    manager_cls: Type["ThinkingManagerBase"]
    summary: str | None = None


def _ensure_builtins_loaded() -> None:
    global _BUILTINS_LOADED
    if not _BUILTINS_LOADED:
        import_module("runtime.node.agent.thinking.builtin_thinking")
        _BUILTINS_LOADED = True


def register_thinking_mode(
    name: str,
    *,
    config_cls: Type[Any],
    manager_cls: Type["ThinkingManagerBase"],
    summary: str | None = None,
) -> None:
    if name in thinking_registry.names():
        raise RegistryError(f"Thinking mode '{name}' already registered")
    entry = ThinkingRegistration(name=name, config_cls=config_cls, manager_cls=manager_cls, summary=summary)
    thinking_registry.register(name, target=entry)
    register_thinking_schema(name, config_cls=config_cls, summary=summary)


def get_thinking_registration(name: str) -> ThinkingRegistration:
    _ensure_builtins_loaded()
    entry: RegistryEntry = thinking_registry.get(name)
    registration = entry.load()
    if not isinstance(registration, ThinkingRegistration):
        raise RegistryError(f"Entry '{name}' is not a ThinkingRegistration")
    return registration


def iter_thinking_registrations() -> Dict[str, ThinkingRegistration]:
    _ensure_builtins_loaded()
    return {name: entry.load() for name, entry in thinking_registry.items()}


__all__ = [
    "thinking_registry",
    "ThinkingRegistration",
    "register_thinking_mode",
    "get_thinking_registration",
    "iter_thinking_registrations",
]
