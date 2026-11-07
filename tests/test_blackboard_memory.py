"""Tests for Blackboard memory store implementation."""

from unittest.mock import MagicMock

from entity.configs.node.memory import BlackboardMemoryConfig
from runtime.node.agent.memory.blackboard_memory import BlackboardMemory
from runtime.node.agent.memory.memory_base import (
    MemoryContentSnapshot,
    MemoryItem,
    MemoryWritePayload,
)


def _make_store(memory_path=None, max_items=1000):
    """Build a minimal MemoryStoreConfig mock for BlackboardMemory."""
    cfg = MagicMock(spec=BlackboardMemoryConfig)
    cfg.memory_path = memory_path
    cfg.max_items = max_items

    store = MagicMock()
    store.name = "test_blackboard"

    def _as_config_side_effect(expected_type, **kwargs):
        if expected_type is BlackboardMemoryConfig:
            return cfg
        return None

    store.as_config.side_effect = _as_config_side_effect
    return store


def _make_item(item_id: str, text: str) -> MemoryItem:
    return MemoryItem(
        id=item_id,
        content_summary=text,
        metadata={"role": "assistant"},
    )


class TestBlackboardMemoryRetrieve:
    def test_retrieve_empty_contents_returns_empty(self):
        store = _make_store()
        memory = BlackboardMemory(store)
        query = MemoryContentSnapshot(text="hello")

        assert (
            memory.retrieve("writer", query, top_k=3, similarity_threshold=-1.0) == []
        )

    def test_retrieve_non_positive_top_k_returns_empty(self):
        store = _make_store()
        memory = BlackboardMemory(store)
        memory.contents = [
            _make_item("1", "first note"),
            _make_item("2", "second note"),
            _make_item("3", "third note"),
        ]
        query = MemoryContentSnapshot(text="note")

        # Non-positive top_k must return empty list, not all contents
        assert (
            memory.retrieve("writer", query, top_k=0, similarity_threshold=-1.0) == []
        )
        assert (
            memory.retrieve("writer", query, top_k=-1, similarity_threshold=-1.0) == []
        )
        assert (
            memory.retrieve("writer", query, top_k=-10, similarity_threshold=-1.0) == []
        )

    def test_retrieve_top_k_exceeding_or_matching_length_returns_all(self):
        store = _make_store()
        memory = BlackboardMemory(store)
        items = [
            _make_item("1", "first note"),
            _make_item("2", "second note"),
        ]
        memory.contents = list(items)
        query = MemoryContentSnapshot(text="note")

        assert (
            memory.retrieve("writer", query, top_k=2, similarity_threshold=-1.0)
            == items
        )
        assert (
            memory.retrieve("writer", query, top_k=10, similarity_threshold=-1.0)
            == items
        )

    def test_retrieve_subsets_most_recent_items(self):
        store = _make_store()
        memory = BlackboardMemory(store)
        items = [
            _make_item("1", "first note"),
            _make_item("2", "second note"),
            _make_item("3", "third note"),
            _make_item("4", "fourth note"),
        ]
        memory.contents = list(items)
        query = MemoryContentSnapshot(text="note")

        result = memory.retrieve("writer", query, top_k=2, similarity_threshold=-1.0)
        assert len(result) == 2
        assert [r.id for r in result] == ["3", "4"]


class TestBlackboardMemoryUpdateAndLimits:
    def test_update_appends_item_and_caps_at_max_items(self):
        store = _make_store(max_items=3)
        memory = BlackboardMemory(store)

        for i in range(5):
            payload = MemoryWritePayload(
                agent_role="coder",
                inputs_text=f"input_{i}",
                input_snapshot=MemoryContentSnapshot(text=f"input_{i}"),
                output_snapshot=MemoryContentSnapshot(text=f"output_{i}"),
            )
            memory.update(payload)

        assert len(memory.contents) == 3
        assert [item.output_snapshot.text for item in memory.contents] == [
            "output_2",
            "output_3",
            "output_4",
        ]

    def test_update_ignores_empty_content(self):
        store = _make_store()
        memory = BlackboardMemory(store)

        payload = MemoryWritePayload(
            agent_role="coder",
            inputs_text="   ",
            input_snapshot=None,
            output_snapshot=None,
        )
        memory.update(payload)
        assert len(memory.contents) == 0


class TestBlackboardMemoryLoad:
    def test_load_nonexistent_path_resets_contents(self, tmp_path):
        nonexistent = str(tmp_path / "missing.json")
        store = _make_store(memory_path=nonexistent)
        memory = BlackboardMemory(store)
        memory.contents = [_make_item("1", "existing")]

        memory.load()
        assert memory.contents == []

    def test_load_corrupted_json_resets_contents(self, tmp_path):
        corrupted = tmp_path / "corrupted.json"
        corrupted.write_text("invalid json content", encoding="utf-8")
        store = _make_store(memory_path=str(corrupted))
        memory = BlackboardMemory(store)
        memory.contents = [_make_item("1", "existing")]

        memory.load()
        assert memory.contents == []
