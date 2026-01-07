"""Base memory abstractions with multimodal snapshots."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import time

from entity.configs import MemoryAttachmentConfig, MemoryStoreConfig
from entity.configs.node.memory import FileMemoryConfig, SimpleMemoryConfig
from entity.enums import AgentExecFlowStage
from entity.messages import Message, MessageBlock
from runtime.node.agent.memory.embedding import EmbeddingBase, EmbeddingFactory


@dataclass
class MemoryContentSnapshot:
    """Lightweight serialization of a multimodal payload."""

    text: str
    blocks: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"text": self.text, "blocks": self.blocks}

    @classmethod
    def from_dict(cls, payload: Dict[str, Any] | None) -> "MemoryContentSnapshot | None":
        if not payload:
            return None
        text = payload.get("text", "")
        blocks = payload.get("blocks") or []
        return cls(text=text, blocks=list(blocks))

    @classmethod
    def from_message(cls, message: Message | str | None) -> "MemoryContentSnapshot | None":
        if message is None:
            return None
        if isinstance(message, Message):
            return cls(
                text=message.text_content(),
                blocks=[
                    {
                        "role": message.role.value,
                        "block": block.to_dict(include_data=True),
                    }
                    for block in message.blocks()
                ],
            )
        if isinstance(message, str):
            return cls(text=message, blocks=[])
        return cls(text=str(message), blocks=[])

    @classmethod
    def from_messages(cls, messages: List[Message]) -> "MemoryContentSnapshot | None":
        if not messages:
            return None
        parts: List[str] = []
        blocks: List[Dict[str, Any]] = []
        for message in messages:
            parts.append(f"({message.role.value}) {message.text_content()}")
            for block in message.blocks():
                blocks.append(
                    {
                        "role": message.role.value,
                        "block": block.to_dict(include_data=True),
                    }
                )
        return cls(text="\n\n".join(parts), blocks=blocks)

    def to_message_blocks(self) -> List[MessageBlock]:
        blocks: List[MessageBlock] = []
        for payload in self.blocks:
            block_data = payload.get("block") if isinstance(payload, dict) else None
            if not isinstance(block_data, dict):
                continue
            try:
                blocks.append(MessageBlock.from_dict(block_data))
            except Exception:
                continue
        return blocks

    def attachment_overview(self) -> List[Dict[str, Any]]:
        attachments: List[Dict[str, Any]] = []
        for payload in self.blocks:
            block_data = payload.get("block") if isinstance(payload, dict) else None
            if not isinstance(block_data, dict):
                continue
            attachment = block_data.get("attachment")
            if attachment:
                attachments.append(
                    {
                        "role": payload.get("role"),
                        "attachment_id": attachment.get("attachment_id"),
                        "mime_type": attachment.get("mime_type"),
                        "name": attachment.get("name"),
                        "size": attachment.get("size"),
                    }
                )
        return attachments

    @classmethod
    def from_blocks(
        cls,
        *,
        text: str,
        blocks: List[MessageBlock],
        role: str = "input",
    ) -> "MemoryContentSnapshot":
        serialized = [
            {
                "role": role,
                "block": block.to_dict(include_data=True),
            }
            for block in blocks
        ]
        return cls(text=text, blocks=serialized)


@dataclass
class MemoryItem:
    id: str
    content_summary: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None
    timestamp: float | None = None
    input_snapshot: MemoryContentSnapshot | None = None
    output_snapshot: MemoryContentSnapshot | None = None

    def __post_init__(self) -> None:
        if self.timestamp is None:
            self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "id": self.id,
            "content_summary": self.content_summary,
            "metadata": self.metadata,
            "embedding": self.embedding,
            "timestamp": self.timestamp,
        }
        if self.input_snapshot:
            payload["input_snapshot"] = self.input_snapshot.to_dict()
        if self.output_snapshot:
            payload["output_snapshot"] = self.output_snapshot.to_dict()
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "MemoryItem":
        return cls(
            id=payload["id"],
            content_summary=payload.get("content_summary", ""),
            metadata=payload.get("metadata") or {},
            embedding=payload.get("embedding"),
            timestamp=payload.get("timestamp"),
            input_snapshot=MemoryContentSnapshot.from_dict(payload.get("input_snapshot")),
            output_snapshot=MemoryContentSnapshot.from_dict(payload.get("output_snapshot")),
        )

    def attachments(self) -> List[Dict[str, Any]]:
        attachments: List[Dict[str, Any]] = []
        if self.input_snapshot:
            attachments.extend(self.input_snapshot.attachment_overview())
        if self.output_snapshot:
            attachments.extend(self.output_snapshot.attachment_overview())
        return attachments


@dataclass
class MemoryWritePayload:
    agent_role: str
    inputs_text: str
    input_snapshot: MemoryContentSnapshot | None
    output_snapshot: MemoryContentSnapshot | None


@dataclass
class MemoryRetrievalResult:
    formatted_text: str
    items: List[MemoryItem]

    def has_multimodal(self) -> bool:
        return any(
            (item.input_snapshot and item.input_snapshot.blocks)
            or (item.output_snapshot and item.output_snapshot.blocks)
            for item in self.items
        )

    def attachment_overview(self) -> List[Dict[str, Any]]:
        attachments: List[Dict[str, Any]] = []
        for item in self.items:
            attachments.extend(item.attachments())
        return attachments


class MemoryBase:
    def __init__(self, store: MemoryStoreConfig):
        self.store = store
        self.name = store.name
        self.contents: List[MemoryItem] = []

        embedding_cfg = None
        simple_cfg = store.as_config(SimpleMemoryConfig)
        file_cfg = store.as_config(FileMemoryConfig)
        if simple_cfg and simple_cfg.embedding:
            embedding_cfg = simple_cfg.embedding
        elif file_cfg and file_cfg.embedding:
            embedding_cfg = file_cfg.embedding

        self.embedding: EmbeddingBase | None = (
            EmbeddingFactory.create_embedding(embedding_cfg) if embedding_cfg else None
        )

    def count_memories(self) -> int:
        return len(self.contents)

    def load(self) -> None:  # pragma: no cover - implemented by subclasses
        raise NotImplementedError

    def save(self) -> None:  # pragma: no cover - implemented by subclasses
        raise NotImplementedError

    def retrieve(
        self,
        agent_role: str,
        query: MemoryContentSnapshot,
        top_k: int,
        similarity_threshold: float,
    ) -> List[MemoryItem]:
        raise NotImplementedError

    def update(self, payload: MemoryWritePayload) -> None:
        raise NotImplementedError


class MemoryManager:
    def __init__(self, attachments: List[MemoryAttachmentConfig], stores: Dict[str, MemoryBase]):
        self.attachments = attachments
        self.memories: Dict[str, MemoryBase] = {}
        for attachment in attachments:
            memory = stores.get(attachment.name)
            if not memory:
                raise ValueError(f"memory store {attachment.name} not found")
            self.memories[attachment.name] = memory

    def retrieve(
        self,
        agent_role: str,
        query: MemoryContentSnapshot,
        current_stage: AgentExecFlowStage,
    ) -> MemoryRetrievalResult | None:
        results: List[tuple[str, MemoryItem, float]] = []
        for attachment in self.attachments:
            if attachment.retrieve_stage and current_stage not in attachment.retrieve_stage:
                continue
            if not attachment.read:
                continue
            memory = self.memories.get(attachment.name)
            if not memory:
                continue
            items = memory.retrieve(agent_role, query, attachment.top_k, attachment.similarity_threshold)
            for item in items:
                combined_score = self._score_memory(item, query.text)
                results.append((attachment.name, item, combined_score))

        if not results:
            return None

        results.sort(key=lambda entry: entry[2], reverse=True)
        formatted = ["===== Related Memories ====="]
        grouped: Dict[str, List[MemoryItem]] = {}
        for name, item, _ in results:
            grouped.setdefault(name, []).append(item)
        for name, items in grouped.items():
            formatted.append(f"\n--- {name} ---")
            for idx, item in enumerate(items, 1):
                formatted.append(f"{idx}. {item.content_summary}")
        formatted.append("\n===== End of Memory =====")

        ordered_items = [item for _, item, _ in results]
        return MemoryRetrievalResult(formatted_text="\n".join(formatted), items=ordered_items)

    def update(self, payload: MemoryWritePayload) -> None:
        for attachment in self.attachments:
            if not attachment.write:
                continue
            memory = self.memories.get(attachment.name)
            if not memory:
                continue
            memory.update(payload)
            memory.save()

    def _score_memory(self, memory_item: MemoryItem, query: str) -> float:
        current_time = time.time()
        age_hours = (current_time - (memory_item.timestamp or current_time)) / 3600
        time_decay = max(0.1, 1.0 - age_hours / (24 * 30))
        length = len(memory_item.content_summary)
        if length < 20:
            length_factor = 0.5
        elif length > 200:
            length_factor = 0.8
        else:
            length_factor = 1.0
        query_words = set(query.lower().split())
        content_words = set(memory_item.content_summary.lower().split())
        relevance = len(query_words & content_words) / len(query_words) if query_words else 0.0
        return 0.7 * time_decay * length_factor + 0.3 * relevance
