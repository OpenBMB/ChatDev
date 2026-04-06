"""Tests for Mem0 memory store implementation."""

from unittest.mock import MagicMock, patch
import pytest

from entity.configs.node.memory import Mem0MemoryConfig
from runtime.node.agent.memory.memory_base import (
    MemoryContentSnapshot,
    MemoryItem,
    MemoryWritePayload,
)


def _make_store(user_id=None, agent_id=None, api_key="test-key"):
    """Build a minimal MemoryStoreConfig mock for Mem0Memory."""
    mem0_cfg = MagicMock(spec=Mem0MemoryConfig)
    mem0_cfg.api_key = api_key
    mem0_cfg.org_id = None
    mem0_cfg.project_id = None
    mem0_cfg.user_id = user_id
    mem0_cfg.agent_id = agent_id

    store = MagicMock()
    store.name = "test_mem0"

    # Return correct config type based on the requested class
    def _as_config_side_effect(expected_type, **kwargs):
        if expected_type is Mem0MemoryConfig:
            return mem0_cfg
        return None

    store.as_config.side_effect = _as_config_side_effect
    return store


def _make_mem0_memory(user_id=None, agent_id=None):
    """Create a Mem0Memory with a mocked client."""
    with patch("runtime.node.agent.memory.mem0_memory._get_mem0_client") as mock_get:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        from runtime.node.agent.memory.mem0_memory import Mem0Memory
        store = _make_store(user_id=user_id, agent_id=agent_id)
        memory = Mem0Memory(store)
        return memory, mock_client


class TestMem0MemoryRetrieve:

    def test_retrieve_with_agent_id(self):
        """Retrieve passes agent_id in filters dict to SDK search."""
        memory, client = _make_mem0_memory(agent_id="agent-1")
        client.search.return_value = {
            "memories": [
                {"id": "m1", "memory": "test fact", "score": 0.95},
            ]
        }

        query = MemoryContentSnapshot(text="what do you know?")
        results = memory.retrieve("writer", query, top_k=5, similarity_threshold=-1.0)

        client.search.assert_called_once()
        call_kwargs = client.search.call_args[1]
        assert call_kwargs["filters"] == {"agent_id": "agent-1"}
        assert len(results) == 1
        assert results[0].content_summary == "test fact"
        assert results[0].metadata["source"] == "mem0"

    def test_retrieve_with_user_id(self):
        """Retrieve passes user_id in filters dict to SDK search."""
        memory, client = _make_mem0_memory(user_id="user-1")
        client.search.return_value = {
            "memories": [
                {"id": "m1", "memory": "user pref", "score": 0.9},
            ]
        }

        query = MemoryContentSnapshot(text="preferences")
        results = memory.retrieve("assistant", query, top_k=3, similarity_threshold=-1.0)

        call_kwargs = client.search.call_args[1]
        assert call_kwargs["filters"] == {"user_id": "user-1"}
        assert len(results) == 1

    def test_retrieve_with_both_ids_uses_or_filter(self):
        """When both user_id and agent_id are set, an OR filter is used."""
        memory, client = _make_mem0_memory(user_id="user-1", agent_id="agent-1")
        client.search.return_value = {
            "memories": [
                {"id": "u1", "memory": "user fact", "score": 0.8},
                {"id": "a1", "memory": "agent fact", "score": 0.9},
            ]
        }

        query = MemoryContentSnapshot(text="test")
        results = memory.retrieve("writer", query, top_k=5, similarity_threshold=-1.0)

        client.search.assert_called_once()
        call_kwargs = client.search.call_args[1]
        assert call_kwargs["filters"] == {
            "OR": [
                {"user_id": "user-1"},
                {"agent_id": "agent-1"},
            ]
        }
        assert len(results) == 2

    def test_retrieve_fallback_uses_agent_role(self):
        """When no IDs configured, fall back to agent_role as agent_id in filters."""
        memory, client = _make_mem0_memory()
        client.search.return_value = {"memories": []}

        query = MemoryContentSnapshot(text="test")
        memory.retrieve("coder", query, top_k=3, similarity_threshold=-1.0)

        call_kwargs = client.search.call_args[1]
        assert call_kwargs["filters"] == {"agent_id": "coder"}

    def test_retrieve_empty_query_returns_empty(self):
        """Empty query text returns empty without calling API."""
        memory, client = _make_mem0_memory(agent_id="a1")

        query = MemoryContentSnapshot(text="   ")
        results = memory.retrieve("writer", query, top_k=3, similarity_threshold=-1.0)

        assert results == []
        client.search.assert_not_called()

    def test_retrieve_api_error_returns_empty(self):
        """API errors are caught and return empty list."""
        memory, client = _make_mem0_memory(agent_id="a1")
        client.search.side_effect = Exception("API down")

        query = MemoryContentSnapshot(text="test")
        results = memory.retrieve("writer", query, top_k=3, similarity_threshold=-1.0)

        assert results == []

    def test_retrieve_respects_top_k(self):
        """top_k is passed to Mem0 search."""
        memory, client = _make_mem0_memory(agent_id="a1")
        client.search.return_value = {"memories": []}

        query = MemoryContentSnapshot(text="test")
        memory.retrieve("writer", query, top_k=7, similarity_threshold=-1.0)

        call_kwargs = client.search.call_args[1]
        assert call_kwargs["top_k"] == 7

    def test_retrieve_passes_threshold_when_non_negative(self):
        """Non-negative similarity_threshold is forwarded to Mem0."""
        memory, client = _make_mem0_memory(agent_id="a1")
        client.search.return_value = {"memories": []}

        query = MemoryContentSnapshot(text="test")
        memory.retrieve("writer", query, top_k=3, similarity_threshold=0.5)

        call_kwargs = client.search.call_args[1]
        assert call_kwargs["threshold"] == 0.5

    def test_retrieve_passes_zero_threshold(self):
        """A threshold of 0.0 is a valid value and should be sent."""
        memory, client = _make_mem0_memory(agent_id="a1")
        client.search.return_value = {"memories": []}

        query = MemoryContentSnapshot(text="test")
        memory.retrieve("writer", query, top_k=3, similarity_threshold=0.0)

        call_kwargs = client.search.call_args[1]
        assert call_kwargs["threshold"] == 0.0

    def test_retrieve_skips_threshold_when_negative(self):
        """Negative similarity_threshold is not sent to Mem0."""
        memory, client = _make_mem0_memory(agent_id="a1")
        client.search.return_value = {"memories": []}

        query = MemoryContentSnapshot(text="test")
        memory.retrieve("writer", query, top_k=3, similarity_threshold=-1.0)

        call_kwargs = client.search.call_args[1]
        assert "threshold" not in call_kwargs

    def test_retrieve_handles_legacy_results_key(self):
        """Handles SDK response with 'results' key (older SDK versions)."""
        memory, client = _make_mem0_memory(agent_id="a1")
        client.search.return_value = {
            "results": [
                {"id": "m1", "memory": "legacy format", "score": 0.8},
            ]
        }

        query = MemoryContentSnapshot(text="test")
        results = memory.retrieve("writer", query, top_k=3, similarity_threshold=-1.0)

        assert len(results) == 1
        assert results[0].content_summary == "legacy format"


class TestMem0MemoryUpdate:

    def test_update_sends_only_user_input(self):
        """Update sends only user input, not assistant output, to prevent noise."""
        memory, client = _make_mem0_memory(agent_id="agent-1")
        client.add.return_value = [{"id": "new", "event": "ADD"}]

        payload = MemoryWritePayload(
            agent_role="writer",
            inputs_text="Write about AI",
            input_snapshot=MemoryContentSnapshot(text="Write about AI"),
            output_snapshot=MemoryContentSnapshot(text="AI is transformative..."),
        )
        memory.update(payload)

        client.add.assert_called_once()
        call_kwargs = client.add.call_args[1]
        assert call_kwargs["agent_id"] == "agent-1"
        assert "user_id" not in call_kwargs
        messages = call_kwargs["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Write about AI"

    def test_update_does_not_send_async_mode(self):
        """Update does not send deprecated async_mode parameter."""
        memory, client = _make_mem0_memory(agent_id="agent-1")
        client.add.return_value = []

        payload = MemoryWritePayload(
            agent_role="writer",
            inputs_text="test",
            input_snapshot=None,
            output_snapshot=MemoryContentSnapshot(text="output"),
        )
        memory.update(payload)

        call_kwargs = client.add.call_args[1]
        assert "async_mode" not in call_kwargs
        assert call_kwargs["infer"] is True

    def test_update_with_user_id(self):
        """User-scoped update uses user_id, not agent_id."""
        memory, client = _make_mem0_memory(user_id="user-1")
        client.add.return_value = []

        payload = MemoryWritePayload(
            agent_role="writer",
            inputs_text="I prefer Python",
            input_snapshot=None,
            output_snapshot=None,
        )
        memory.update(payload)

        call_kwargs = client.add.call_args[1]
        assert call_kwargs["user_id"] == "user-1"
        assert "agent_id" not in call_kwargs

    def test_update_fallback_uses_agent_role(self):
        """When no IDs configured, uses agent_role as agent_id."""
        memory, client = _make_mem0_memory()
        client.add.return_value = []

        payload = MemoryWritePayload(
            agent_role="coder",
            inputs_text="test input",
            input_snapshot=None,
            output_snapshot=None,
        )
        memory.update(payload)

        call_kwargs = client.add.call_args[1]
        assert call_kwargs["agent_id"] == "coder"

    def test_update_with_both_ids_includes_both(self):
        """When both user_id and agent_id configured, both are included in add() call."""
        memory, client = _make_mem0_memory(user_id="user-1", agent_id="agent-1")
        client.add.return_value = []

        payload = MemoryWritePayload(
            agent_role="writer",
            inputs_text="input",
            input_snapshot=None,
            output_snapshot=None,
        )
        memory.update(payload)

        call_kwargs = client.add.call_args[1]
        assert call_kwargs["agent_id"] == "agent-1"
        assert call_kwargs["user_id"] == "user-1"

    def test_update_empty_input_is_noop(self):
        """Empty inputs_text skips API call."""
        memory, client = _make_mem0_memory(agent_id="a1")

        payload = MemoryWritePayload(
            agent_role="writer",
            inputs_text="   ",
            input_snapshot=None,
            output_snapshot=MemoryContentSnapshot(text="some output"),
        )
        memory.update(payload)

        client.add.assert_not_called()

    def test_update_no_input_is_noop(self):
        """No inputs_text skips API call."""
        memory, client = _make_mem0_memory(agent_id="a1")

        payload = MemoryWritePayload(
            agent_role="writer",
            inputs_text="",
            input_snapshot=None,
            output_snapshot=MemoryContentSnapshot(text="output"),
        )
        memory.update(payload)

        client.add.assert_not_called()

    def test_update_api_error_does_not_raise(self):
        """API errors are logged but do not propagate."""
        memory, client = _make_mem0_memory(agent_id="a1")
        client.add.side_effect = Exception("API error")

        payload = MemoryWritePayload(
            agent_role="writer",
            inputs_text="test user input",
            input_snapshot=None,
            output_snapshot=None,
        )
        # Should not raise
        memory.update(payload)


class TestMem0MemoryPipelineTextCleaning:

    def test_strips_input_from_task_header(self):
        """Pipeline headers like '=== INPUT FROM TASK (user) ===' are stripped."""
        memory, client = _make_mem0_memory(agent_id="a1")
        client.add.return_value = []

        payload = MemoryWritePayload(
            agent_role="writer",
            inputs_text="=== INPUT FROM TASK (user) ===\n\nMy name is Alex, I love Python",
            input_snapshot=None,
            output_snapshot=MemoryContentSnapshot(text="Nice to meet you Alex!"),
        )
        memory.update(payload)

        call_kwargs = client.add.call_args[1]
        messages = call_kwargs["messages"]
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "My name is Alex, I love Python"
        assert "INPUT FROM" not in messages[0]["content"]

    def test_strips_multiple_input_headers(self):
        """Multiple pipeline headers from different sources are all stripped."""
        memory, client = _make_mem0_memory(agent_id="a1")
        client.add.return_value = []

        payload = MemoryWritePayload(
            agent_role="writer",
            inputs_text=(
                "=== INPUT FROM TASK (user) ===\n\nHello\n\n"
                "=== INPUT FROM reviewer (assistant) ===\n\nWorld"
            ),
            input_snapshot=None,
            output_snapshot=MemoryContentSnapshot(text="Hi!"),
        )
        memory.update(payload)

        call_kwargs = client.add.call_args[1]
        user_content = call_kwargs["messages"][0]["content"]
        assert "INPUT FROM" not in user_content
        assert "Hello" in user_content
        assert "World" in user_content

    def test_clean_text_without_headers_unchanged(self):
        """Text without pipeline headers passes through unchanged."""
        from runtime.node.agent.memory.mem0_memory import Mem0Memory
        assert Mem0Memory._clean_pipeline_text("Just normal text") == "Just normal text"


class TestMem0MemoryLoadSave:

    def test_load_is_noop(self):
        """load() does nothing for cloud-managed store."""
        memory, _ = _make_mem0_memory(agent_id="a1")
        memory.load()  # Should not raise

    def test_save_is_noop(self):
        """save() does nothing for cloud-managed store."""
        memory, _ = _make_mem0_memory(agent_id="a1")
        memory.save()  # Should not raise


class TestMem0MemoryConfig:

    def test_config_from_dict(self):
        """Config parses from dict correctly."""
        data = {
            "api_key": "test-key",
            "user_id": "u1",
            "org_id": "org-1",
        }
        config = Mem0MemoryConfig.from_dict(data, path="test")
        assert config.api_key == "test-key"
        assert config.user_id == "u1"
        assert config.org_id == "org-1"
        assert config.agent_id is None
        assert config.project_id is None

    def test_config_field_specs_exist(self):
        """FIELD_SPECS are defined for UI generation."""
        specs = Mem0MemoryConfig.field_specs()
        assert "api_key" in specs
        assert "user_id" in specs
        assert "agent_id" in specs
        assert specs["api_key"].required is True

    def test_config_requires_api_key(self):
        """Config raises ConfigError when api_key is missing."""
        from entity.configs.base import ConfigError

        data = {"agent_id": "a1"}
        with pytest.raises(ConfigError):
            Mem0MemoryConfig.from_dict(data, path="test")


class TestMem0MemoryConstructor:

    def test_raises_on_wrong_config_type(self):
        """Mem0Memory raises ValueError when store has wrong config type."""
        from runtime.node.agent.memory.mem0_memory import Mem0Memory

        store = MagicMock()
        store.name = "bad_store"
        store.as_config.return_value = None  # Wrong config type

        with pytest.raises(ValueError, match="Mem0 memory store configuration"):
            Mem0Memory(store)

    def test_import_error_when_mem0ai_missing(self):
        """Helpful ImportError when mem0ai is not installed."""
        from runtime.node.agent.memory.mem0_memory import _get_mem0_client

        mem0_cfg = MagicMock(spec=Mem0MemoryConfig)
        mem0_cfg.api_key = "test"
        mem0_cfg.org_id = None
        mem0_cfg.project_id = None

        with patch.dict("sys.modules", {"mem0": None}):
            with pytest.raises(ImportError, match="pip install mem0ai"):
                _get_mem0_client(mem0_cfg)
