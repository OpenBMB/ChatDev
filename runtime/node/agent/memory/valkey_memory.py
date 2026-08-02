"""Valkey Search persistent vector memory store implementation."""

import logging
import struct
import time
import uuid
from typing import List

from entity.configs import MemoryStoreConfig
from entity.configs.node.memory import ValkeyMemoryConfig
from runtime.node.agent.memory.embedding import EmbeddingBase, EmbeddingFactory
from runtime.node.agent.memory.memory_base import (
    MemoryBase,
    MemoryContentSnapshot,
    MemoryItem,
    MemoryWritePayload,
)

logger = logging.getLogger(__name__)


def _get_glide_sync():
    try:
        import glide_sync
        return glide_sync
    except ImportError:
        raise ImportError(
            "valkey-glide-sync is required for ValkeyMemory. "
            "Install it with: pip install 'chatdev[valkey]' "
            "(https://pypi.org/project/valkey-glide-sync/)"
        )


def _make_client(host: str, port: int, username: str | None = None, password: str | None = None, db: int = 0, use_tls: bool = False):
    glide_sync = _get_glide_sync()
    credentials = None
    if password:
        credentials = glide_sync.ServerCredentials(username=username or "default", password=password)
    config = glide_sync.GlideClientConfiguration(
        addresses=[glide_sync.NodeAddress(host, port)],
        use_tls=use_tls,
        credentials=credentials,
        client_name="chatdev_memory_client",
        database_id=db if db != 0 else None,
    )
    return glide_sync.GlideClient.create(config)


class ValkeyMemory(MemoryBase):
    """Memory store backed by Valkey Search with persistent HNSW vector index.

    Each memory item is stored as a Valkey Hash at `memory:{uuid}` with fields:
    content_summary, embedding (float32 bytes), agent_role, and timestamp.
    A FT index with HNSW COSINE metric enables KNN retrieval.
    """

    def __init__(self, store: MemoryStoreConfig):
        config = store.as_config(ValkeyMemoryConfig)
        if not config:
            raise ValueError("ValkeyMemory requires a ValkeyMemoryConfig")
        # Skip MemoryBase.__init__ embedding logic — we handle it via config.embedding directly
        self.store = store
        self.name = store.name
        self.contents: list = []  # satisfy MemoryBase contract (unused; state lives in Valkey)
        self.config = config

        if config.embedding:
            self.embedding: EmbeddingBase | None = EmbeddingFactory.create_embedding(config.embedding)
        else:
            self.embedding = None

        self._glide = _get_glide_sync()
        self._client = _make_client(config.host, config.port, config.username, config.password, config.db, config.use_tls)
        self._ensure_index()

    # -------- Index lifecycle --------

    def _ensure_index(self) -> None:
        """Create the HNSW FT index if absent, probing dimension from a test embedding."""
        if self.embedding is None:
            raise ValueError(
                "ValkeyMemory requires an embedding configuration to determine vector dimension"
            )

        glide_sync = self._glide

        test_vec = self.embedding.get_embedding("test")
        dim = len(test_vec)

        schema = [
            glide_sync.TextField("content_summary"),
            glide_sync.TagField("agent_role"),
            glide_sync.NumericField("timestamp"),
            glide_sync.VectorField(
                "embedding",
                glide_sync.VectorAlgorithm.HNSW,
                glide_sync.VectorFieldAttributesHnsw(
                    dimensions=dim,
                    distance_metric=glide_sync.DistanceMetricType.COSINE,
                    type=glide_sync.VectorType.FLOAT32,
                ),
            ),
        ]
        options = glide_sync.FtCreateOptions(prefixes=[self.config.key_prefix])

        try:
            glide_sync.ft.create(self._client, self.config.index_name, schema, options)
            logger.info("Created Valkey FT index '%s' (dim=%d)", self.config.index_name, dim)
        except Exception as exc:
            msg = str(exc).lower()
            if "index already exists" in msg or "already exists" in msg:
                logger.debug("Valkey FT index '%s' already exists", self.config.index_name)
            elif "unknown command" in msg or "module" in msg:
                raise RuntimeError(
                    f"Valkey server at {self.config.host}:{self.config.port} does not have the "
                    "Search module loaded. Install valkey-search or use the valkey/valkey-bundle "
                    "Docker image that includes it."
                ) from exc
            else:
                raise

    @staticmethod
    def _sanitize_tag(value: str) -> str:
        """Sanitize a string for use as a Valkey TAG field value."""
        if not value:
            return ""
        # TAG syntax breaks on commas, braces, spaces, pipes
        for ch in ",{}|<> \t\n\r":
            value = value.replace(ch, "_")
        return value

    # -------- Persistence (no-ops — server-side) --------

    def load(self) -> None:
        pass

    def save(self) -> None:
        pass

    # -------- Update --------

    def update(self, payload: MemoryWritePayload) -> None:
        text = (payload.inputs_text or "").strip()
        if not text:
            return
        if self.embedding is None:
            logger.warning("ValkeyMemory: no embedding configured, skipping update")
            return

        embedding_vec = self.embedding.get_embedding(text)
        embedding_bytes = struct.pack(f"{len(embedding_vec)}f", *embedding_vec)

        key = f"{self.config.key_prefix}{uuid.uuid4().hex}"
        ts = time.time()

        try:
            self._client.hset(key, {
                "content_summary": text,
                "embedding": embedding_bytes,
                "agent_role": self._sanitize_tag(payload.agent_role or ""),
                "timestamp": str(ts),
            })

            if self.config.ttl_seconds is not None:
                self._client.expire(key, self.config.ttl_seconds)
        except Exception as exc:
            logger.error("ValkeyMemory update failed: %s", exc)
            return

        logger.debug("Stored memory at %s (agent_role=%s)", key, payload.agent_role)

    # -------- Retrieval --------

    def retrieve(
        self,
        agent_role: str,
        query: MemoryContentSnapshot,
        top_k: int,
        similarity_threshold: float,
    ) -> List[MemoryItem]:
        text = query.text.strip()
        if not text:
            return []
        if self.embedding is None:
            return []

        glide_sync = self._glide

        query_vec = self.embedding.get_embedding(text)
        query_bytes = struct.pack(f"{len(query_vec)}f", *query_vec)

        top_k = max(1, int(top_k))

        # Filter by agent_role when available
        safe_role = self._sanitize_tag(agent_role)
        if safe_role:
            ft_query = f"(@agent_role:{{{safe_role}}})=>[KNN {top_k} @embedding $vec]"
        else:
            ft_query = f"*=>[KNN {top_k} @embedding $vec]"
        options = glide_sync.FtSearchOptions(
            params={"vec": query_bytes},
            dialect=2,
        )

        try:
            results = glide_sync.ft.search(self._client, self.config.index_name, ft_query, options)
        except Exception as exc:
            logger.error("ValkeyMemory search failed: %s", exc)
            return []

        # results is [total_count, {key: {field: value, ...}}, ...]
        # Skip the first element (count), then iterate doc dicts
        items: List[MemoryItem] = []
        doc_entries = results[1:] if results else []
        for entry in doc_entries:
            if not isinstance(entry, dict):
                continue
            for key, fields in entry.items():
                score_raw = fields.get(b"__embedding_score") or fields.get("__embedding_score") or b"1.0"
                try:
                    distance = float(score_raw)
                except (ValueError, TypeError):
                    distance = 1.0
                similarity = 1.0 - distance

                if similarity_threshold >= 0 and similarity < similarity_threshold:
                    continue

                content = fields.get(b"content_summary") or fields.get("content_summary", b"")
                role = fields.get(b"agent_role") or fields.get("agent_role", b"")
                ts_raw = fields.get(b"timestamp") or fields.get("timestamp", b"0")

                items.append(MemoryItem(
                    id=key.decode() if isinstance(key, bytes) else key,
                    content_summary=content.decode() if isinstance(content, bytes) else content,
                    metadata={
                        "agent_role": role.decode() if isinstance(role, bytes) else role,
                        "score": similarity,
                        "source": "valkey",
                    },
                    timestamp=float(ts_raw) if ts_raw else time.time(),
                ))

        items.sort(key=lambda item: item.metadata.get("score", 0.0), reverse=True)
        return items

    # -------- Count --------

    def count_memories(self) -> int:
        try:
            info = self._glide.ft.info(self._client, self.config.index_name)
            num_docs = info.get(b"num_docs") or info.get("num_docs", 0)
            return int(num_docs)
        except Exception as exc:
            logger.error("ValkeyMemory count_memories failed: %s", exc)
            return 0
