"""File-backed memory stores accept relative and absolute persistence paths."""

from pathlib import Path

import pytest

from runtime.node.agent.memory.builtin_stores import MemoryFactory
from runtime.node.agent.memory.memory_base import MemoryItem
from entity.configs.node.memory import MemoryStoreConfig


@pytest.mark.parametrize("store_type", ["simple", "file", "blackboard"])
@pytest.mark.parametrize("path_kind", ["bare", "dot", "nested", "absolute"])
def test_memory_save_load_paths(tmp_path, monkeypatch, store_type, path_kind):
    monkeypatch.chdir(tmp_path)
    sources = tmp_path / "sources"
    sources.mkdir()
    filename = f"{store_type}.json"
    paths = {
        "bare": filename,
        "dot": f"./{filename}",
        "nested": f"missing/nested/{filename}",
        "absolute": str(tmp_path / "absolute" / filename),
    }
    path = paths[path_kind]
    config = {"memory_path": path}
    if store_type == "file":
        config = {"index_path": path, "file_sources": [{"path": str(sources)}]}
    store = MemoryStoreConfig.from_dict(
        {"name": "persist", "type": store_type, "config": config}, path="memory"
    )
    memory = MemoryFactory.create_memory(store)
    item = MemoryItem(
        id="saved", content_summary="A saved memory", metadata={"role": "writer"}
    )
    memory.contents = [item]
    memory.save()
    assert Path(path).is_file()

    restored = MemoryFactory.create_memory(store)
    restored.load()
    assert [entry.to_dict() for entry in restored.contents] == [item.to_dict()]


@pytest.mark.parametrize("store_type", ["simple", "file", "blackboard"])
def test_memory_without_persistence_path(tmp_path, monkeypatch, store_type):
    monkeypatch.chdir(tmp_path)
    config = {}
    if store_type == "file":
        config = {"file_sources": [{"path": str(tmp_path)}]}
    store = MemoryStoreConfig.from_dict(
        {"name": "ephemeral", "type": store_type, "config": config}, path="memory"
    )
    memory = MemoryFactory.create_memory(store)
    memory.save()
    assert list(tmp_path.iterdir()) == []
