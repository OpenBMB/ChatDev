"""Lightweight append-only Blackboard memory implementation."""

import json
import os
import time
import uuid
from typing import List

from entity.configs import MemoryStoreConfig
from entity.configs.node.memory import BlackboardMemoryConfig
from runtime.node.agent.memory.memory_base import (
    MemoryBase,
    MemoryContentSnapshot,
    MemoryItem,
    MemoryWritePayload,
)


class BlackboardMemory(MemoryBase):
    """Simple append-only memory: save raw outputs, retrieve by recency."""

    def __init__(self, store: MemoryStoreConfig):
        config = store.as_config(BlackboardMemoryConfig)
        if not config:
            raise ValueError("BlackboardMemory requires a blackboard memory store configuration")
        super().__init__(store)
        self.config = config
        self.memory_path = config.memory_path
        self.max_items = config.max_items

    # -------- Persistence --------
    def load(self) -> None:
        if not self.memory_path or not os.path.exists(self.memory_path):
            self.contents = []
            return

        try:
            with open(self.memory_path, "r", encoding="utf-8") as file:
                data = json.load(file)
            contents: List[MemoryItem] = []
            for raw in data:
                try:
                    contents.append(MemoryItem.from_dict(raw))
                except Exception:
                    continue
            self.contents = contents
        except Exception:
            # Corrupted file -> reset to empty to avoid blocking execution
            self.contents = []

    def save(self) -> None:
        if not self.memory_path:
            return

        os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)
        payload = [item.to_dict() for item in self.contents[-self.max_items :]]
        with open(self.memory_path, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)

    # -------- Memory operations --------
    def retrieve(
        self,
        agent_role: str,
        query: MemoryContentSnapshot,
        top_k: int,
        similarity_threshold: float,
    ) -> List[MemoryItem]:
        if not self.contents:
            return []

        if top_k <= 0 or top_k >= len(self.contents):
            return list(self.contents)

        return list(self.contents[-top_k:])

    def update(self, payload: MemoryWritePayload) -> None:
        snapshot = payload.output_snapshot or payload.input_snapshot
        content = (snapshot.text if snapshot else payload.inputs_text or "").strip()
        if not content:
            return

        metadata = {
            "agent_role": payload.agent_role,
            "input_preview": (payload.inputs_text or "")[:200],
            "attachments": snapshot.attachment_overview() if snapshot else [],
        }

        memory_item = MemoryItem(
            id=f"bb_{uuid.uuid4().hex}",
            content_summary=content,
            metadata=metadata,
            timestamp=time.time(),
            input_snapshot=payload.input_snapshot,
            output_snapshot=payload.output_snapshot,
        )

        self.contents.append(memory_item)
        if len(self.contents) > self.max_items:
            self.contents = self.contents[-self.max_items :]
