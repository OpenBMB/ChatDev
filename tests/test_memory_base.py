"""Unit tests for memory_base abstractions (MemoryContentSnapshot, MemoryItem, MemoryManager)."""

import time

from entity.enums import AgentExecFlowStage
from entity.messages import Message, MessageRole
from runtime.node.agent.memory.memory_base import (
    MemoryContentSnapshot,
    MemoryItem,
    MemoryManager,
    MemoryRetrievalResult,
)


class TestMemoryContentSnapshot:
    def test_from_message_with_message_role_enum(self):
        msg = Message(role=MessageRole.USER, content="Hello")
        snapshot = MemoryContentSnapshot.from_message(msg)
        assert snapshot is not None
        assert snapshot.text == "Hello"
        assert len(snapshot.blocks) == 1
        assert snapshot.blocks[0]["role"] == "user"

    def test_from_message_with_string_role(self):
        # When role is initialized as a plain string, message.role does not have a .value attribute
        msg = Message(role="assistant", content="Response text")
        snapshot = MemoryContentSnapshot.from_message(msg)
        assert snapshot is not None
        assert snapshot.text == "Response text"
        assert len(snapshot.blocks) == 1
        assert snapshot.blocks[0]["role"] == "assistant"

    def test_from_message_with_none(self):
        assert MemoryContentSnapshot.from_message(None) is None

    def test_from_message_with_plain_string(self):
        snapshot = MemoryContentSnapshot.from_message("raw text query")
        assert snapshot is not None
        assert snapshot.text == "raw text query"
        assert snapshot.blocks == []

    def test_from_messages_mixed_roles_and_strings(self):
        msgs = [
            Message(role=MessageRole.SYSTEM, content="System prompt"),
            Message(role="user", content="User question"),
            "raw string message",
        ]
        snapshot = MemoryContentSnapshot.from_messages(msgs)
        assert snapshot is not None
        assert "(system) System prompt" in snapshot.text
        assert "(user) User question" in snapshot.text
        assert "raw string message" in snapshot.text
        assert len(snapshot.blocks) == 2
        assert snapshot.blocks[0]["role"] == "system"
        assert snapshot.blocks[1]["role"] == "user"

    def test_from_messages_empty(self):
        assert MemoryContentSnapshot.from_messages([]) is None

    def test_from_dict_valid_dict(self):
        payload = {"text": "saved text", "blocks": [{"role": "user", "block": {"type": "text", "text": "saved"}}]}
        snapshot = MemoryContentSnapshot.from_dict(payload)
        assert snapshot is not None
        assert snapshot.text == "saved text"
        assert len(snapshot.blocks) == 1

    def test_from_dict_legacy_string(self):
        # Backwards compatibility when an older memory record stored a plain string snapshot
        snapshot = MemoryContentSnapshot.from_dict("plain text snapshot")
        assert snapshot is not None
        assert snapshot.text == "plain text snapshot"
        assert snapshot.blocks == []

    def test_from_dict_none_and_invalid(self):
        assert MemoryContentSnapshot.from_dict(None) is None
        assert MemoryContentSnapshot.from_dict({}) is None
        assert MemoryContentSnapshot.from_dict(12345) is None

    def test_attachment_overview_non_dict_attachment(self):
        snapshot = MemoryContentSnapshot(
            text="overview text",
            blocks=[
                {"role": "user", "block": {"attachment": "invalid_string_not_dict"}},
                {"role": "user", "block": "not_a_dict"},
                {
                    "role": "user",
                    "block": {
                        "attachment": {
                            "attachment_id": "att_1",
                            "mime_type": "image/png",
                            "name": "photo.png",
                            "size": 1024,
                        }
                    },
                },
            ],
        )
        overview = snapshot.attachment_overview()
        assert len(overview) == 1
        assert overview[0]["attachment_id"] == "att_1"
        assert overview[0]["mime_type"] == "image/png"


class TestMemoryItem:
    def test_from_dict_preserves_id(self):
        payload = {
            "id": "item_123",
            "content_summary": "Summary",
            "metadata": {"source": "test"},
        }
        item = MemoryItem.from_dict(payload)
        assert item.id == "item_123"
        assert item.content_summary == "Summary"

    def test_from_dict_generates_id_if_missing(self):
        payload = {
            "content_summary": "Summary without id",
        }
        item = MemoryItem.from_dict(payload)
        assert item.id.startswith("mem_")

    def test_from_dict_with_legacy_string_snapshot(self):
        payload = {
            "id": "item_legacy",
            "content_summary": "Legacy item",
            "input_snapshot": "legacy input text",
            "output_snapshot": None,
        }
        item = MemoryItem.from_dict(payload)
        assert item.input_snapshot is not None
        assert item.input_snapshot.text == "legacy input text"
        assert item.input_snapshot.blocks == []


class DummyMemory:
    def __init__(self, items):
        self.items = items

    def retrieve(self, agent_role, query, top_k, similarity_threshold):
        return self.items[:top_k]


class DummyAttachmentConfig:
    def __init__(self, name="default", top_k=5, similarity_threshold=0.0, read=True, retrieve_stage=None):
        self.name = name
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold
        self.read = read
        self.retrieve_stage = retrieve_stage


class TestMemoryManager:
    def test_retrieve_with_none_query(self):
        item = MemoryItem(id="m1", content_summary="Item 1", metadata={})
        dummy_store = DummyMemory([item])
        attachment = DummyAttachmentConfig(name="main_store")
        manager = MemoryManager(attachments=[attachment], stores={"main_store": dummy_store})

        # Calling retrieve with query=None should safely score and format without raising AttributeError
        result = manager.retrieve(
            agent_role="assistant",
            query=None,
            current_stage=AgentExecFlowStage.GEN_STAGE,
        )
        assert result is not None
        assert isinstance(result, MemoryRetrievalResult)
        assert len(result.items) == 1
        assert "Item 1" in result.formatted_text

    def test_score_memory_with_future_timestamp(self):
        manager = MemoryManager(attachments=[], stores={})
        future_time = time.time() + 3600  # 1 hour in future
        item = MemoryItem(id="future", content_summary="Future memory with enough words", metadata={}, timestamp=future_time)
        score = manager._score_memory(item, query="memory words")
        assert 0.0 <= score <= 1.0

    def test_score_memory_with_none_summary_and_none_query(self):
        manager = MemoryManager(attachments=[], stores={})
        item = MemoryItem(id="m_empty", content_summary=None, metadata={})
        score = manager._score_memory(item, query=None)
        assert isinstance(score, float)
        assert score >= 0.0
