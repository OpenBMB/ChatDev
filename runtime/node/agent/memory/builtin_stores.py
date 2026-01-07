"""Register built-in memory stores."""

from entity.configs.node.memory import (
    BlackboardMemoryConfig,
    FileMemoryConfig,
    SimpleMemoryConfig,
    MemoryStoreConfig,
)
from runtime.node.agent.memory.blackboard_memory import BlackboardMemory
from runtime.node.agent.memory.file_memory import FileMemory
from runtime.node.agent.memory.memory_base import MemoryBase
from runtime.node.agent.memory.simple_memory import SimpleMemory
from runtime.node.agent.memory.registry import register_memory_store, get_memory_store_registration

register_memory_store(
    "simple",
    config_cls=SimpleMemoryConfig,
    factory=lambda store: SimpleMemory(store),
    summary="In-memory store that resets between runs; best for testing",
)

register_memory_store(
    "file",
    config_cls=FileMemoryConfig,
    factory=lambda store: FileMemory(store),
    summary="Persists documents on disk and supports embedding search",
)

register_memory_store(
    "blackboard",
    config_cls=BlackboardMemoryConfig,
    factory=lambda store: BlackboardMemory(store),
    summary="Shared blackboard memory allowing multiple nodes to read/write",
)


class MemoryFactory:
    @staticmethod
    def create_memory(store: MemoryStoreConfig) -> MemoryBase:
        registration = get_memory_store_registration(store.type)
        return registration.factory(store)
