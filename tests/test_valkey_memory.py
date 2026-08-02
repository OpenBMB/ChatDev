"""Tests for Valkey memory store: config validation, registry, and runtime behavior."""

import struct
from unittest.mock import MagicMock, patch
import pytest

from entity.configs.base import ConfigError
from entity.configs.node.memory import ValkeyMemoryConfig, EmbeddingConfig
from runtime.node.agent.memory.memory_base import (
    MemoryContentSnapshot,
    MemoryWritePayload,
)


# =============================================================================
# Unit Tests: ValkeyMemoryConfig
# =============================================================================


class TestValkeyMemoryConfigFromDict:
    """Test ValkeyMemoryConfig.from_dict parsing and validation."""

    def test_minimal_config(self):
        """Parses with all defaults when only empty dict provided."""
        cfg = ValkeyMemoryConfig.from_dict({}, path="test")
        assert cfg.host == "localhost"
        assert cfg.port == 6379
        assert cfg.username is None
        assert cfg.password is None
        assert cfg.db == 0
        assert cfg.use_tls is False
        assert cfg.index_name == "memory_index"
        assert cfg.key_prefix == "memory:"
        assert cfg.ttl_seconds is None
        assert cfg.embedding is None

    def test_full_config(self):
        """Parses all fields correctly."""
        data = {
            "host": "valkey.internal",
            "port": 6380,
            "username": "admin",
            "password": "secret",
            "db": 2,
            "use_tls": True,
            "index_name": "chatdev_memory",
            "key_prefix": "agent:",
            "ttl_seconds": 86400,
            "embedding": {
                "provider": "openai",
                "model": "text-embedding-3-small",
            },
        }
        cfg = ValkeyMemoryConfig.from_dict(data, path="test")
        assert cfg.host == "valkey.internal"
        assert cfg.port == 6380
        assert cfg.username == "admin"
        assert cfg.password == "secret"
        assert cfg.db == 2
        assert cfg.use_tls is True
        assert cfg.index_name == "chatdev_memory"
        assert cfg.key_prefix == "agent:"
        assert cfg.ttl_seconds == 86400
        assert cfg.embedding is not None
        assert cfg.embedding.provider == "openai"
        assert cfg.embedding.model == "text-embedding-3-small"

    def test_invalid_port_zero(self):
        """Port must be at least 1."""
        with pytest.raises(ConfigError, match="port"):
            ValkeyMemoryConfig.from_dict({"port": 0}, path="test")

    def test_invalid_port_negative(self):
        """Negative port rejected."""
        with pytest.raises(ConfigError, match="port"):
            ValkeyMemoryConfig.from_dict({"port": -1}, path="test")

    def test_invalid_port_string(self):
        """Non-integer port rejected."""
        with pytest.raises(ConfigError, match="port"):
            ValkeyMemoryConfig.from_dict({"port": "6379"}, path="test")

    def test_invalid_port_too_high(self):
        """Port above 65535 rejected."""
        with pytest.raises(ConfigError, match="port"):
            ValkeyMemoryConfig.from_dict({"port": 65536}, path="test")

    def test_invalid_db_negative(self):
        """Negative db index rejected."""
        with pytest.raises(ConfigError, match="db"):
            ValkeyMemoryConfig.from_dict({"db": -1}, path="test")

    def test_invalid_db_too_high(self):
        """Database index above 15 rejected."""
        with pytest.raises(ConfigError, match="db"):
            ValkeyMemoryConfig.from_dict({"db": 16}, path="test")

    def test_invalid_ttl_zero(self):
        """TTL must be positive if specified."""
        with pytest.raises(ConfigError, match="ttl_seconds"):
            ValkeyMemoryConfig.from_dict({"ttl_seconds": 0}, path="test")

    def test_invalid_ttl_negative(self):
        """Negative TTL rejected."""
        with pytest.raises(ConfigError, match="ttl_seconds"):
            ValkeyMemoryConfig.from_dict({"ttl_seconds": -100}, path="test")

    def test_invalid_ttl_string(self):
        """Non-integer TTL rejected."""
        with pytest.raises(ConfigError, match="ttl_seconds"):
            ValkeyMemoryConfig.from_dict({"ttl_seconds": "3600"}, path="test")

    def test_optional_fields_none_when_omitted(self):
        """TTL and embedding are None when not specified."""
        cfg = ValkeyMemoryConfig.from_dict({"host": "localhost"}, path="test")
        assert cfg.ttl_seconds is None
        assert cfg.embedding is None

    def test_embedding_none_when_explicitly_none(self):
        """Embedding config is None when explicitly set to None."""
        cfg = ValkeyMemoryConfig.from_dict({"embedding": None}, path="test")
        assert cfg.embedding is None


class TestValkeyMemoryConfigFieldSpecs:
    """Test FIELD_SPECS metadata for UI generation."""

    def test_field_specs_defined(self):
        """All expected fields have specs."""
        specs = ValkeyMemoryConfig.field_specs()
        expected_fields = {"host", "port", "username", "password", "db", "use_tls", "index_name", "key_prefix", "ttl_seconds", "embedding"}
        assert expected_fields.issubset(set(specs.keys()))

    def test_host_not_required(self):
        """Host has a default so it's not required."""
        specs = ValkeyMemoryConfig.field_specs()
        assert specs["host"].required is False

    def test_index_name_not_required(self):
        """index_name has a default."""
        specs = ValkeyMemoryConfig.field_specs()
        assert specs["index_name"].required is False
        assert specs["index_name"].default == "memory_index"

    def test_ttl_not_required(self):
        """ttl_seconds is optional."""
        specs = ValkeyMemoryConfig.field_specs()
        assert specs["ttl_seconds"].required is False

    def test_embedding_has_child(self):
        """Embedding spec references EmbeddingConfig as child."""
        specs = ValkeyMemoryConfig.field_specs()
        assert specs["embedding"].child is EmbeddingConfig


# =============================================================================
# Unit Tests: Registry
# =============================================================================


class TestValkeyRegistration:
    """Test that 'valkey' is properly registered as a memory store type."""

    def test_valkey_in_registry(self):
        """'valkey' appears in memory store registrations."""
        from runtime.node.agent.memory.registry import iter_memory_store_registrations

        stores = iter_memory_store_registrations()
        assert "valkey" in stores

    def test_valkey_config_cls(self):
        """Registry entry points to ValkeyMemoryConfig."""
        from runtime.node.agent.memory.registry import get_memory_store_registration

        reg = get_memory_store_registration("valkey")
        assert reg.config_cls is ValkeyMemoryConfig

    def test_valkey_has_summary(self):
        """Registry entry has a non-empty summary."""
        from runtime.node.agent.memory.registry import get_memory_store_registration

        reg = get_memory_store_registration("valkey")
        assert reg.summary and len(reg.summary) > 0

    def test_schema_registry_has_valkey(self):
        """schema_registry also knows about 'valkey' for config parsing."""
        from schema_registry import get_memory_store_schema

        schema = get_memory_store_schema("valkey")
        assert schema.config_cls is ValkeyMemoryConfig


# =============================================================================
# Unit Tests: MemoryStoreConfig can parse type=valkey
# =============================================================================


class TestMemoryStoreConfigValkey:
    """Test that MemoryStoreConfig.from_dict handles type='valkey'."""

    def test_parses_valkey_store(self):
        """Full memory store config with type=valkey parses successfully."""
        from entity.configs.node.memory import MemoryStoreConfig

        data = {
            "name": "chatdev_memory",
            "type": "valkey",
            "config": {
                "host": "localhost",
                "port": 6379,
                "index_name": "chatdev_memory",
                "ttl_seconds": 86400,
            },
        }
        store = MemoryStoreConfig.from_dict(data, path="test")
        assert store.name == "chatdev_memory"
        assert store.type == "valkey"
        assert isinstance(store.config, ValkeyMemoryConfig)
        assert store.config.index_name == "chatdev_memory"
        assert store.config.ttl_seconds == 86400

    def test_rejects_missing_config_block(self):
        """Config block is required."""
        from entity.configs.node.memory import MemoryStoreConfig

        data = {
            "name": "bad",
            "type": "valkey",
            "config": None,
        }
        with pytest.raises(ConfigError):
            MemoryStoreConfig.from_dict(data, path="test")


# =============================================================================
# Unit Tests: ValkeyMemory Runtime Behavior
# =============================================================================


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store(
    host="localhost",
    port=6379,
    index_name="chatdev_memory",
    ttl_seconds=None,
    username=None,
    password=None,
    use_tls=False,
):
    """Build a minimal MemoryStoreConfig mock for ValkeyMemory."""
    valkey_cfg = MagicMock(spec=ValkeyMemoryConfig)
    valkey_cfg.host = host
    valkey_cfg.port = port
    valkey_cfg.index_name = index_name
    valkey_cfg.ttl_seconds = ttl_seconds
    valkey_cfg.key_prefix = "memory:"
    valkey_cfg.username = username
    valkey_cfg.password = password
    valkey_cfg.db = 0
    valkey_cfg.use_tls = use_tls
    valkey_cfg.embedding = MagicMock()  # non-None so embedding branch is taken

    store = MagicMock()
    store.name = "test_valkey"

    def _as_config_side_effect(expected_type, **kwargs):
        if expected_type is ValkeyMemoryConfig:
            return valkey_cfg
        return None

    store.as_config.side_effect = _as_config_side_effect
    return store, valkey_cfg


def _make_valkey_memory(host="localhost", port=6379, ttl_seconds=None, username=None, password=None, use_tls=False):
    """Create a ValkeyMemory with mocked glide_sync client and embedding."""
    store, valkey_cfg = _make_store(host=host, port=port, ttl_seconds=ttl_seconds, username=username, password=password, use_tls=use_tls)

    mock_client = MagicMock()
    mock_embedding = MagicMock()
    mock_embedding.get_embedding.return_value = [0.1, 0.2, 0.3]  # dim=3

    mock_glide_module = MagicMock()
    mock_glide_module.ft.create.return_value = "OK"
    mock_glide_module.ft.search.return_value = []

    with patch("runtime.node.agent.memory.valkey_memory._get_glide_sync") as mock_get_glide, \
         patch("runtime.node.agent.memory.valkey_memory._make_client") as mock_make_client, \
         patch("runtime.node.agent.memory.valkey_memory.EmbeddingFactory") as mock_factory:
        mock_get_glide.return_value = mock_glide_module
        mock_make_client.return_value = mock_client
        mock_factory.create_embedding.return_value = mock_embedding

        from runtime.node.agent.memory.valkey_memory import ValkeyMemory
        memory = ValkeyMemory(store)
        # Attach the glide module mock so tests can inspect ft.create / ft.search calls
        memory._glide = mock_glide_module
        return memory, mock_client, mock_embedding


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------

class TestValkeyMemoryInstantiation:

    def test_instantiation_creates_ft_index(self):
        """ValkeyMemory creates FT index at __init__ time."""
        memory, client, _ = _make_valkey_memory()
        memory._glide.ft.create.assert_called_once()
        args = memory._glide.ft.create.call_args[0]
        assert args[1] == "chatdev_memory"  # index_name is second positional arg

    def test_instantiation_idempotent_when_index_exists(self):
        """ValkeyMemory silently ignores 'index already exists' error."""
        store, _ = _make_store()
        mock_client = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.get_embedding.return_value = [0.1, 0.2, 0.3]
        mock_glide_module = MagicMock()
        mock_glide_module.ft.create.side_effect = Exception("Index already exists")

        with patch("runtime.node.agent.memory.valkey_memory._get_glide_sync") as mock_get_glide, \
             patch("runtime.node.agent.memory.valkey_memory._make_client") as mock_make_client, \
             patch("runtime.node.agent.memory.valkey_memory.EmbeddingFactory") as mock_factory:
            mock_get_glide.return_value = mock_glide_module
            mock_make_client.return_value = mock_client
            mock_factory.create_embedding.return_value = mock_embedding

            from runtime.node.agent.memory.valkey_memory import ValkeyMemory
            ValkeyMemory(store)  # Should not raise

    def test_instantiation_raises_on_missing_search_module(self):
        """ValkeyMemory raises RuntimeError when Search module is absent."""
        store, _ = _make_store()
        mock_client = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.get_embedding.return_value = [0.1, 0.2, 0.3]
        mock_glide_module = MagicMock()
        mock_glide_module.ft.create.side_effect = Exception("unknown command ft.create")

        with patch("runtime.node.agent.memory.valkey_memory._get_glide_sync") as mock_get_glide, \
             patch("runtime.node.agent.memory.valkey_memory._make_client") as mock_make_client, \
             patch("runtime.node.agent.memory.valkey_memory.EmbeddingFactory") as mock_factory:
            mock_get_glide.return_value = mock_glide_module
            mock_make_client.return_value = mock_client
            mock_factory.create_embedding.return_value = mock_embedding

            from runtime.node.agent.memory.valkey_memory import ValkeyMemory
            with pytest.raises(RuntimeError, match="Search module"):
                ValkeyMemory(store)

    def test_raises_on_wrong_config_type(self):
        """ValkeyMemory raises ValueError when store has wrong config type."""
        from runtime.node.agent.memory.valkey_memory import ValkeyMemory

        store = MagicMock()
        store.name = "bad"
        store.as_config.return_value = None

        with patch("runtime.node.agent.memory.valkey_memory._get_glide_sync"), \
             patch("runtime.node.agent.memory.valkey_memory._make_client"):
            with pytest.raises(ValueError, match="ValkeyMemoryConfig"):
                ValkeyMemory(store)


# ---------------------------------------------------------------------------
# Connection options (TLS, username)
# ---------------------------------------------------------------------------

class TestValkeyMemoryConnectionOptions:

    def test_use_tls_passed_to_make_client(self):
        """use_tls=True is forwarded to _make_client."""
        store, _ = _make_store(use_tls=True, password="secret", username="admin")
        mock_client = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.get_embedding.return_value = [0.1, 0.2, 0.3]
        mock_glide_module = MagicMock()
        mock_glide_module.ft.create.return_value = "OK"

        with patch("runtime.node.agent.memory.valkey_memory._get_glide_sync") as mock_get_glide, \
             patch("runtime.node.agent.memory.valkey_memory._make_client") as mock_make_client, \
             patch("runtime.node.agent.memory.valkey_memory.EmbeddingFactory") as mock_factory:
            mock_get_glide.return_value = mock_glide_module
            mock_make_client.return_value = mock_client
            mock_factory.create_embedding.return_value = mock_embedding

            from runtime.node.agent.memory.valkey_memory import ValkeyMemory
            ValkeyMemory(store)

            mock_make_client.assert_called_once_with(
                "localhost", 6379, "admin", "secret", 0, True
            )

    def test_username_passed_to_make_client(self):
        """username is forwarded to _make_client when provided."""
        store, _ = _make_store(username="myuser", password="mypass")
        mock_client = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.get_embedding.return_value = [0.1, 0.2, 0.3]
        mock_glide_module = MagicMock()
        mock_glide_module.ft.create.return_value = "OK"

        with patch("runtime.node.agent.memory.valkey_memory._get_glide_sync") as mock_get_glide, \
             patch("runtime.node.agent.memory.valkey_memory._make_client") as mock_make_client, \
             patch("runtime.node.agent.memory.valkey_memory.EmbeddingFactory") as mock_factory:
            mock_get_glide.return_value = mock_glide_module
            mock_make_client.return_value = mock_client
            mock_factory.create_embedding.return_value = mock_embedding

            from runtime.node.agent.memory.valkey_memory import ValkeyMemory
            ValkeyMemory(store)

            call_args = mock_make_client.call_args[0]
            assert call_args[2] == "myuser"  # username
            assert call_args[3] == "mypass"  # password

    def test_client_name_set_in_configuration(self):
        """_make_client sets client_name='chatdev_memory_client' for server-side identification."""
        from runtime.node.agent.memory.valkey_memory import _make_client

        mock_glide_module = MagicMock()

        with patch("runtime.node.agent.memory.valkey_memory._get_glide_sync") as mock_get_glide:
            mock_get_glide.return_value = mock_glide_module
            _make_client("localhost", 6379)

            # Verify GlideClientConfiguration was called with client_name
            config_call = mock_glide_module.GlideClientConfiguration.call_args
            assert config_call[1]["client_name"] == "chatdev_memory_client"


# ---------------------------------------------------------------------------
# Tag sanitization
# ---------------------------------------------------------------------------

class TestValkeyMemorySanitizeTag:

    def test_sanitize_tag_removes_commas(self):
        """Commas in agent_role are replaced with underscores."""
        from runtime.node.agent.memory.valkey_memory import ValkeyMemory
        assert ValkeyMemory._sanitize_tag("role,with,commas") == "role_with_commas"

    def test_sanitize_tag_removes_braces(self):
        """Braces are replaced."""
        from runtime.node.agent.memory.valkey_memory import ValkeyMemory
        assert ValkeyMemory._sanitize_tag("{admin}") == "_admin_"

    def test_sanitize_tag_removes_spaces(self):
        """Spaces are replaced."""
        from runtime.node.agent.memory.valkey_memory import ValkeyMemory
        assert ValkeyMemory._sanitize_tag("my role") == "my_role"

    def test_sanitize_tag_removes_pipes(self):
        """Pipes are replaced."""
        from runtime.node.agent.memory.valkey_memory import ValkeyMemory
        assert ValkeyMemory._sanitize_tag("a|b") == "a_b"

    def test_sanitize_tag_empty_string(self):
        """Empty string returns empty."""
        from runtime.node.agent.memory.valkey_memory import ValkeyMemory
        assert ValkeyMemory._sanitize_tag("") == ""

    def test_sanitize_tag_clean_input_unchanged(self):
        """Clean input passes through unchanged."""
        from runtime.node.agent.memory.valkey_memory import ValkeyMemory
        assert ValkeyMemory._sanitize_tag("coder") == "coder"


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

class TestValkeyMemoryUpdate:

    def test_update_stores_hash(self):
        """update() calls hset with expected fields."""
        memory, client, embedding = _make_valkey_memory()
        embedding.get_embedding.return_value = [0.5, 0.6, 0.7]

        payload = MemoryWritePayload(
            agent_role="coder",
            inputs_text="I prefer Python",
            input_snapshot=None,
            output_snapshot=None,
        )
        memory.update(payload)

        client.hset.assert_called_once()
        args = client.hset.call_args
        key = args[0][0]
        fields = args[0][1]
        assert key.startswith("memory:")
        assert fields["content_summary"] == "I prefer Python"
        assert fields["agent_role"] == "coder"
        assert "embedding" in fields
        assert "timestamp" in fields

    def test_update_embedding_bytes_are_float32(self):
        """update() encodes embedding as packed float32 bytes."""
        memory, client, embedding = _make_valkey_memory()
        vec = [0.1, 0.2, 0.3]
        embedding.get_embedding.return_value = vec

        payload = MemoryWritePayload(
            agent_role="writer",
            inputs_text="test",
            input_snapshot=None,
            output_snapshot=None,
        )
        memory.update(payload)

        fields = client.hset.call_args[0][1]
        expected_bytes = struct.pack("3f", *vec)
        assert fields["embedding"] == expected_bytes

    def test_update_with_ttl_calls_expire(self):
        """update() calls expire on the key when ttl_seconds is configured."""
        memory, client, _ = _make_valkey_memory(ttl_seconds=3600)

        payload = MemoryWritePayload(
            agent_role="writer",
            inputs_text="test input",
            input_snapshot=None,
            output_snapshot=None,
        )
        memory.update(payload)

        client.expire.assert_called_once()
        expire_args = client.expire.call_args[0]
        assert expire_args[1] == 3600

    def test_update_without_ttl_does_not_call_expire(self):
        """update() does not call expire when ttl_seconds is None."""
        memory, client, _ = _make_valkey_memory(ttl_seconds=None)

        payload = MemoryWritePayload(
            agent_role="writer",
            inputs_text="test input",
            input_snapshot=None,
            output_snapshot=None,
        )
        memory.update(payload)

        client.expire.assert_not_called()

    def test_update_empty_input_is_noop(self):
        """update() with empty inputs_text skips hset."""
        memory, client, _ = _make_valkey_memory()

        payload = MemoryWritePayload(
            agent_role="writer",
            inputs_text="   ",
            input_snapshot=None,
            output_snapshot=None,
        )
        memory.update(payload)

        client.hset.assert_not_called()


# ---------------------------------------------------------------------------
# Retrieve
# ---------------------------------------------------------------------------

class TestValkeyMemoryRetrieve:

    def _ft_result(self, docs):
        """Build a ft.search return value: [count, {key: {fields}}, ...]
        docs: list of (key, content, agent_role, distance) tuples.
        """
        result = [len(docs)]
        for key, content, role, distance in docs:
            result.append({
                key.encode(): {
                    b"content_summary": content.encode(),
                    b"agent_role": role.encode(),
                    b"timestamp": b"1700000000.0",
                    b"__embedding_score": str(distance).encode(),
                }
            })
        return result

    def test_retrieve_returns_memory_items(self):
        """retrieve() returns MemoryItem list from ft.search results."""
        memory, client, embedding = _make_valkey_memory()
        embedding.get_embedding.return_value = [0.1, 0.2, 0.3]
        memory._glide.ft.search.return_value = self._ft_result([
            ("memory:abc", "Python is great", "coder", 0.05),
        ])

        query = MemoryContentSnapshot(text="Python")
        results = memory.retrieve("coder", query, top_k=3, similarity_threshold=-1.0)

        assert len(results) == 1
        assert results[0].content_summary == "Python is great"
        assert results[0].metadata["source"] == "valkey"

    def test_retrieve_filters_by_agent_role(self):
        """retrieve() filters KNN search by agent_role when provided (spec: AEA-500)."""
        memory, client, embedding = _make_valkey_memory()
        embedding.get_embedding.return_value = [0.1, 0.2, 0.3]
        memory._glide.ft.search.return_value = []

        query = MemoryContentSnapshot(text="test")
        memory.retrieve("designer", query, top_k=5, similarity_threshold=-1.0)

        ft_query_arg = memory._glide.ft.search.call_args[0][2]
        assert "(@agent_role:{designer})=>[KNN" in ft_query_arg

    def test_retrieve_threshold_filtering(self):
        """retrieve() excludes results below similarity_threshold."""
        memory, client, embedding = _make_valkey_memory()
        embedding.get_embedding.return_value = [0.1, 0.2, 0.3]
        # distance=0.8 -> similarity=0.2, below threshold of 0.5
        memory._glide.ft.search.return_value = self._ft_result([
            ("memory:a", "low relevance", "coder", 0.8),
        ])

        query = MemoryContentSnapshot(text="test")
        results = memory.retrieve("coder", query, top_k=5, similarity_threshold=0.5)

        assert results == []

    def test_retrieve_threshold_passes_high_similarity(self):
        """retrieve() includes results at or above similarity_threshold."""
        memory, client, embedding = _make_valkey_memory()
        embedding.get_embedding.return_value = [0.1, 0.2, 0.3]
        # distance=0.1 -> similarity=0.9
        memory._glide.ft.search.return_value = self._ft_result([
            ("memory:a", "high relevance", "coder", 0.1),
        ])

        query = MemoryContentSnapshot(text="test")
        results = memory.retrieve("coder", query, top_k=5, similarity_threshold=0.5)

        assert len(results) == 1

    def test_retrieve_ordered_by_similarity_descending(self):
        """retrieve() returns results ordered by descending cosine similarity."""
        memory, client, embedding = _make_valkey_memory()
        embedding.get_embedding.return_value = [0.1, 0.2, 0.3]
        memory._glide.ft.search.return_value = self._ft_result([
            ("memory:a", "less relevant", "coder", 0.4),   # similarity=0.6
            ("memory:b", "most relevant", "coder", 0.1),   # similarity=0.9
            ("memory:c", "middle", "coder", 0.2),          # similarity=0.8
        ])

        query = MemoryContentSnapshot(text="test")
        results = memory.retrieve("coder", query, top_k=5, similarity_threshold=-1.0)

        assert results[0].content_summary == "most relevant"
        assert results[1].content_summary == "middle"
        assert results[2].content_summary == "less relevant"

    def test_retrieve_empty_query_returns_empty(self):
        """retrieve() returns empty list for blank query without calling ft.search."""
        memory, client, _ = _make_valkey_memory()

        query = MemoryContentSnapshot(text="   ")
        results = memory.retrieve("coder", query, top_k=3, similarity_threshold=-1.0)

        assert results == []
        memory._glide.ft.search.assert_not_called()

    def test_retrieve_search_error_returns_empty(self):
        """retrieve() returns empty list when ft.search raises."""
        memory, client, embedding = _make_valkey_memory()
        embedding.get_embedding.return_value = [0.1, 0.2, 0.3]
        memory._glide.ft.search.side_effect = Exception("connection error")

        query = MemoryContentSnapshot(text="test")
        results = memory.retrieve("coder", query, top_k=3, similarity_threshold=-1.0)

        assert results == []

    def test_retrieve_no_threshold_passes_all(self):
        """retrieve() with threshold=-1.0 returns all results regardless of similarity."""
        memory, client, embedding = _make_valkey_memory()
        embedding.get_embedding.return_value = [0.1, 0.2, 0.3]
        memory._glide.ft.search.return_value = self._ft_result([
            ("memory:a", "very low", "coder", 0.99),  # similarity=0.01
        ])

        query = MemoryContentSnapshot(text="test")
        results = memory.retrieve("coder", query, top_k=5, similarity_threshold=-1.0)

        assert len(results) == 1


# ---------------------------------------------------------------------------
# Count memories
# ---------------------------------------------------------------------------

class TestValkeyMemoryCount:

    def test_count_memories_returns_num_docs(self):
        """count_memories() returns num_docs from ft.info."""
        memory, client, _ = _make_valkey_memory()
        memory._glide.ft.info.return_value = {b"num_docs": 3}

        assert memory.count_memories() == 3

    def test_count_memories_empty(self):
        """count_memories() returns 0 when index has no docs."""
        memory, client, _ = _make_valkey_memory()
        memory._glide.ft.info.return_value = {b"num_docs": 0}

        assert memory.count_memories() == 0

    def test_count_memories_error_returns_zero(self):
        """count_memories() returns 0 on error."""
        memory, client, _ = _make_valkey_memory()
        memory._glide.ft.info.side_effect = Exception("connection error")

        assert memory.count_memories() == 0


# ---------------------------------------------------------------------------
# Load / Save no-ops
# ---------------------------------------------------------------------------

class TestValkeyMemoryLoadSave:

    def test_load_is_noop(self):
        """load() does nothing for server-managed store."""
        memory, _, _ = _make_valkey_memory()
        memory.load()  # Should not raise

    def test_save_is_noop(self):
        """save() does nothing for server-managed store."""
        memory, _, _ = _make_valkey_memory()
        memory.save()  # Should not raise


# ---------------------------------------------------------------------------
# Lazy import error
# ---------------------------------------------------------------------------

class TestValkeyMemoryLazyImport:

    def test_import_error_when_valkey_glide_missing(self):
        """Helpful ImportError when valkey-glide is not installed."""
        from runtime.node.agent.memory.valkey_memory import _get_glide_sync

        with patch.dict("sys.modules", {"glide_sync": None}):
            with pytest.raises(ImportError, match="valkey-glide-sync is required"):
                _get_glide_sync()
