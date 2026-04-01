"""Mem0 managed memory store implementation."""

import logging
import time
import uuid
from typing import Any, Dict, List

from entity.configs import MemoryStoreConfig
from entity.configs.node.memory import Mem0MemoryConfig
from runtime.node.agent.memory.memory_base import (
    MemoryBase,
    MemoryContentSnapshot,
    MemoryItem,
    MemoryWritePayload,
)

logger = logging.getLogger(__name__)


def _get_mem0_client(config: Mem0MemoryConfig):
    """Lazy-import mem0ai and create a MemoryClient."""
    try:
        from mem0 import MemoryClient
    except ImportError:
        raise ImportError(
            "mem0ai is required for Mem0Memory. Install it with: pip install mem0ai"
        )

    client_kwargs: Dict[str, Any] = {}
    if config.api_key:
        client_kwargs["api_key"] = config.api_key
    if config.org_id:
        client_kwargs["org_id"] = config.org_id
    if config.project_id:
        client_kwargs["project_id"] = config.project_id

    return MemoryClient(**client_kwargs)


class Mem0Memory(MemoryBase):
    """Memory store backed by Mem0's managed cloud service.

    Mem0 handles embeddings, storage, and semantic search server-side.
    No local persistence or embedding computation is needed.

    Important API constraints:
    - Agent memories use role="assistant" + agent_id
    - user_id and agent_id are stored as separate records in Mem0;
      if both are configured, an OR filter is used to search across both scopes.
    - search() uses filters dict; add() uses top-level kwargs.
    - SDK returns {"memories": [...]} from search.
    """

    def __init__(self, store: MemoryStoreConfig):
        config = store.as_config(Mem0MemoryConfig)
        if not config:
            raise ValueError("Mem0Memory requires a Mem0 memory store configuration")
        super().__init__(store)
        self.config = config
        self.client = _get_mem0_client(config)
        self.user_id = config.user_id
        self.agent_id = config.agent_id

    # -------- Persistence (no-ops for cloud-managed store) --------

    def load(self) -> None:
        """No-op: Mem0 manages persistence server-side."""
        pass

    def save(self) -> None:
        """No-op: Mem0 manages persistence server-side."""
        pass

    # -------- Retrieval --------

    def _build_search_filters(self, agent_role: str) -> Dict[str, Any]:
        """Build the filters dict for Mem0 search.

        Mem0 search requires a filters dict for entity scoping.
        user_id and agent_id are stored as separate records, so
        when both are configured we use an OR filter to match either.
        """
        if self.user_id and self.agent_id:
            return {
                "OR": [
                    {"user_id": self.user_id},
                    {"agent_id": self.agent_id},
                ]
            }
        elif self.user_id:
            return {"user_id": self.user_id}
        elif self.agent_id:
            return {"agent_id": self.agent_id}
        else:
            # Fallback: use agent_role as agent_id
            return {"agent_id": agent_role}

    def retrieve(
        self,
        agent_role: str,
        query: MemoryContentSnapshot,
        top_k: int,
        similarity_threshold: float,
    ) -> List[MemoryItem]:
        """Search Mem0 for relevant memories.

        Uses the filters dict to scope by user_id, agent_id, or both
        (via OR filter). The SDK returns {"memories": [...]}.
        """
        if not query.text.strip():
            return []

        try:
            filters = self._build_search_filters(agent_role)
            search_kwargs: Dict[str, Any] = {
                "query": query.text,
                "top_k": top_k,
                "filters": filters,
            }
            if similarity_threshold >= 0:
                search_kwargs["threshold"] = similarity_threshold

            response = self.client.search(**search_kwargs)

            # SDK returns {"memories": [...]} — extract the list
            if isinstance(response, dict):
                raw_results = response.get("memories", response.get("results", []))
            else:
                raw_results = response
        except Exception as e:
            logger.error("Mem0 search failed: %s", e)
            return []

        items: List[MemoryItem] = []
        for entry in raw_results:
            item = MemoryItem(
                id=entry.get("id", f"mem0_{uuid.uuid4().hex}"),
                content_summary=entry.get("memory", ""),
                metadata={
                    "agent_role": agent_role,
                    "score": entry.get("score"),
                    "categories": entry.get("categories", []),
                    "source": "mem0",
                },
                timestamp=time.time(),
            )
            items.append(item)

        return items

    # -------- Update --------

    def update(self, payload: MemoryWritePayload) -> None:
        """Store a memory in Mem0.

        Uses role="assistant" + agent_id for agent-generated memories,
        and role="user" + user_id for user-scoped memories.
        """
        snapshot = payload.output_snapshot or payload.input_snapshot
        if not snapshot or not snapshot.text.strip():
            return

        messages = self._build_messages(payload)
        if not messages:
            return

        add_kwargs: Dict[str, Any] = {"messages": messages}

        # Determine scoping: agent_id takes precedence for agent-generated content
        if self.agent_id:
            add_kwargs["agent_id"] = self.agent_id
        elif self.user_id:
            add_kwargs["user_id"] = self.user_id
        else:
            # Default: use agent_role as agent_id
            add_kwargs["agent_id"] = payload.agent_role

        try:
            self.client.add(**add_kwargs)
        except Exception as e:
            logger.error("Mem0 add failed: %s", e)

    def _build_messages(self, payload: MemoryWritePayload) -> List[Dict[str, str]]:
        """Build Mem0-compatible message list from write payload.

        Agent-generated content uses role="assistant".
        User input uses role="user".
        """
        messages: List[Dict[str, str]] = []

        if payload.inputs_text and payload.inputs_text.strip():
            messages.append({
                "role": "user",
                "content": payload.inputs_text.strip(),
            })

        if payload.output_snapshot and payload.output_snapshot.text.strip():
            messages.append({
                "role": "assistant",
                "content": payload.output_snapshot.text.strip(),
            })

        return messages
