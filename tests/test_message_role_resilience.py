"""Unit tests for Message role coercion and string-role resilience across executors and providers."""


from entity.messages import Message, MessageRole, deserialize_messages, serialize_messages
from runtime.edge.conditions.base import EdgeConditionManager
from runtime.node.agent.memory.memory_base import MemoryContentSnapshot
from runtime.node.agent.providers.openai_provider import OpenAIProvider
from runtime.node.agent.providers.response import ModelResponse
from runtime.node.executor.base import NodeExecutor


class TestMessageRoleNormalization:
    def test_standard_string_role_normalized_to_enum(self):
        msg_user = Message(role="user", content="hello")
        assert isinstance(msg_user.role, MessageRole)
        assert msg_user.role == MessageRole.USER

        msg_assistant = Message(role="assistant", content="world")
        assert isinstance(msg_assistant.role, MessageRole)
        assert msg_assistant.role == MessageRole.ASSISTANT

        msg_system = Message(role="system", content="prompt")
        assert isinstance(msg_system.role, MessageRole)
        assert msg_system.role == MessageRole.SYSTEM

        msg_tool = Message(role="tool", content="data")
        assert isinstance(msg_tool.role, MessageRole)
        assert msg_tool.role == MessageRole.TOOL

    def test_case_insensitive_string_role_normalized(self):
        msg = Message(role="USER", content="query")
        assert isinstance(msg.role, MessageRole)
        assert msg.role == MessageRole.USER

        msg_mixed = Message(role="Assistant", content="reply")
        assert isinstance(msg_mixed.role, MessageRole)
        assert msg_mixed.role == MessageRole.ASSISTANT

    def test_custom_string_role_preserved(self):
        msg = Message(role="evaluator", content="review")
        assert isinstance(msg.role, str)
        assert msg.role == "evaluator"

    def test_with_role_normalizes(self):
        msg = Message(role=MessageRole.USER, content="test")
        msg_new = msg.with_role("assistant")
        assert isinstance(msg_new.role, MessageRole)
        assert msg_new.role == MessageRole.ASSISTANT


class TestMessageToDictResilience:
    def test_to_dict_with_message_role_enum(self):
        msg = Message(role=MessageRole.USER, content="test")
        payload = msg.to_dict()
        assert payload["role"] == "user"
        assert payload["content"] == "test"
        restored = Message.from_dict(payload)
        assert restored.role == MessageRole.USER
        assert restored.content == "test"

    def test_to_dict_and_from_dict_with_string_role(self):
        msg = Message(role="custom_agent", content="action")
        payload = msg.to_dict()
        assert payload["role"] == "custom_agent"
        assert payload["content"] == "action"

        # Symmetry: from_dict and serialize/deserialize preserve custom roles
        restored = Message.from_dict(payload)
        assert restored.role == "custom_agent"
        assert restored.content == "action"

        serialized = serialize_messages([msg])
        deserialized = deserialize_messages(serialized)
        assert len(deserialized) == 1
        assert deserialized[0].role == "custom_agent"
        assert deserialized[0].content == "action"


class TestModelResponseToDictResilience:
    def test_model_response_to_dict_with_enum_role(self):
        msg = Message(role=MessageRole.ASSISTANT, content="done")
        resp = ModelResponse(message=msg)
        payload = resp.to_dict()
        assert payload["role"] == "assistant"
        assert payload["content"] == "done"

    def test_model_response_to_dict_with_custom_role(self):
        msg = Message(role="supervisor", content="approved")
        resp = ModelResponse(message=msg)
        payload = resp.to_dict()
        assert payload["role"] == "supervisor"
        assert payload["content"] == "approved"


class TestExecutorAndEdgeResilience:
    def test_inputs_to_text_with_enum_and_string_roles(self):
        msg1 = Message(role=MessageRole.USER, content="input text", metadata={"source": "node_a"})
        msg2 = Message(role="judge", content="verdict", metadata={"source": "node_b"})

        text = NodeExecutor._inputs_to_text(None, [msg1, msg2])
        assert "=== INPUT FROM node_a (user) ===\n\ninput text" in text
        assert "=== INPUT FROM node_b (judge) ===\n\nverdict" in text

    def test_describe_payload_with_enum_and_string_roles(self):
        msg1 = Message(role=MessageRole.USER, content="hi")
        msg2 = Message(role="moderator", content="warn")

        assert EdgeConditionManager._describe_payload(None, msg1) == "message:user"
        assert EdgeConditionManager._describe_payload(None, msg2) == "message:moderator"


class TestOpenAIProviderSerializationResilience:
    def test_serialize_message_for_chat(self):
        provider = OpenAIProvider.__new__(OpenAIProvider)
        provider._transform_blocks_for_chat = lambda blocks: blocks[0]["text"] if len(blocks) == 1 else blocks
        provider._serialize_blocks = lambda blocks, role: [{"type": "text", "text": b.text} for b in blocks]

        msg_enum = Message(role=MessageRole.USER, content="hello")
        chat_payload_enum = provider._serialize_message_for_chat(msg_enum)
        assert chat_payload_enum["role"] == "user"
        assert chat_payload_enum["content"] == "hello"

        # Custom roles map to user with role name preserved in name field
        msg_custom = Message(role="critic", content="check")
        chat_payload_custom = provider._serialize_message_for_chat(msg_custom)
        assert chat_payload_custom["role"] == "user"
        assert chat_payload_custom["name"] == "critic"
        assert chat_payload_custom["content"] == "check"

    def test_serialize_message_for_responses(self):
        provider = OpenAIProvider.__new__(OpenAIProvider)
        provider._serialize_content_blocks = lambda msg: [{"type": "text", "text": msg.text_content()}]

        msg_enum = Message(role=MessageRole.USER, content="hello")
        resp_payload_enum = provider._serialize_message_for_responses(msg_enum)
        assert resp_payload_enum["role"] == "user"

        # Custom roles map to user with role name preserved in name field
        msg_custom = Message(role="critic", content="check")
        resp_payload_custom = provider._serialize_message_for_responses(msg_custom)
        assert resp_payload_custom["role"] == "user"
        assert resp_payload_custom["name"] == "critic"


class TestMemorySnapshotResilience:
    def test_from_message_with_string_role(self):
        msg = Message(role="evaluator", content="evaluation text")
        snapshot = MemoryContentSnapshot.from_message(msg)
        assert snapshot is not None
        assert snapshot.text == "evaluation text"

    def test_from_messages_with_string_role(self):
        msg1 = Message(role=MessageRole.USER, content="user prompt")
        msg2 = Message(role="reviewer", content="review text")
        snapshot = MemoryContentSnapshot.from_messages([msg1, msg2])
        assert snapshot is not None
        assert "(user) user prompt" in snapshot.text
        assert "(reviewer) review text" in snapshot.text
