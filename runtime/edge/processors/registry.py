"""Registry helpers for edge payload processors."""

from dataclasses import dataclass
from importlib import import_module
from typing import Any, Dict, Type

from schema_registry import register_edge_processor_schema
from utils.registry import Registry, RegistryEntry, RegistryError
from entity.configs.edge.edge_processor import EdgeProcessorConfig, EdgeProcessorTypeConfig
from .base import EdgePayloadProcessor, ProcessorFactoryContext


@dataclass(slots=True)
class EdgeProcessorRegistration:
    name: str
    config_cls: Type["EdgeProcessorTypeConfig"]
    processor_cls: Type["EdgePayloadProcessor[Any]"]
    summary: str | None = None


edge_processor_registry = Registry("edge_processor_type")
_BUILTINS_LOADED = False


def _ensure_builtins_loaded() -> None:
    global _BUILTINS_LOADED
    if not _BUILTINS_LOADED:
        import_module("runtime.edge.processors.builtin_types")
        _BUILTINS_LOADED = True


def register_edge_processor(
    name: str,
    *,
    config_cls: Type["EdgeProcessorTypeConfig"],
    processor_cls: Type["EdgePayloadProcessor[Any]"],
    summary: str | None = None,
) -> None:
    if name in edge_processor_registry.names():
        raise RegistryError(f"Edge processor type '{name}' already registered")
    entry = EdgeProcessorRegistration(
        name=name,
        config_cls=config_cls,
        processor_cls=processor_cls,
        summary=summary,
    )
    edge_processor_registry.register(name, target=entry)
    register_edge_processor_schema(name, config_cls=config_cls, summary=summary)


def get_edge_processor_registration(name: str) -> EdgeProcessorRegistration:
    _ensure_builtins_loaded()
    entry: RegistryEntry = edge_processor_registry.get(name)
    registration = entry.load()
    if not isinstance(registration, EdgeProcessorRegistration):
        raise RegistryError(f"Entry '{name}' is not an EdgeProcessorRegistration")
    return registration


def iter_edge_processor_registrations() -> Dict[str, EdgeProcessorRegistration]:
    _ensure_builtins_loaded()
    return {name: entry.load() for name, entry in edge_processor_registry.items()}


def build_edge_processor(
    processor_config: "EdgeProcessorConfig",
    context: ProcessorFactoryContext,
) -> "EdgePayloadProcessor[Any]":
    registration = get_edge_processor_registration(processor_config.type)
    processor_cls = registration.processor_cls
    if not processor_cls:
        raise RegistryError(f"Edge processor type '{processor_config.type}' does not provide an implementation")
    return processor_cls(processor_config.config, context)


__all__ = [
    "register_edge_processor",
    "get_edge_processor_registration",
    "iter_edge_processor_registrations",
    "build_edge_processor",
]
