from types import MappingProxyType, SimpleNamespace

from entity.messages import AttachmentRef, Message, MessageBlock, MessageBlockType, MessageRole, ToolCallPayload
from runtime.node.executor.agent_executor import AgentNodeExecutor


def test_clone_isolates_nested_message_metadata():
    original = Message(
        MessageRole.USER, "prompt", metadata={"trace": {"tags": ["original"]}},
        keep=True, preserve_role=True,
    )
    cloned = original.clone()
    assert cloned.to_dict() == original.to_dict()
    cloned.metadata["trace"]["tags"].append("clone")
    assert original.metadata["trace"]["tags"] == ["original"]


def test_clone_isolates_multimodal_payloads_and_attachment_metadata():
    original = Message(MessageRole.USER, [MessageBlock(
        MessageBlockType.IMAGE,
        attachment=AttachmentRef("image", metadata={"labels": ["original"]}),
        data={"options": {"detail": ["low"]}},
    )])
    cloned = original.clone()
    sibling = original.clone()
    cloned.content[0].data["options"]["detail"].append("high")
    cloned.content[0].attachment.metadata["labels"].append("clone")
    for untouched in (original, sibling):
        assert untouched.content[0].data == {"options": {"detail": ["low"]}}
        assert untouched.content[0].attachment.metadata == {"labels": ["original"]}


def test_clone_isolates_tool_call_objects_and_their_metadata():
    original = Message(MessageRole.ASSISTANT, "", tool_calls=[ToolCallPayload(
        "call-1", "search", '{"query": "original"}', metadata={"tags": ["original"]},
    )])
    cloned = original.clone()
    cloned.tool_calls[0].arguments = '{"query": "clone"}'
    cloned.tool_calls[0].metadata["tags"].append("clone")
    assert original.tool_calls[0].arguments == '{"query": "original"}'
    assert original.tool_calls[0].metadata == {"tags": ["original"]}


def test_timeline_clones_read_only_tool_metadata():
    signature = {"parts": ["original"]}
    metadata = {"provider": [MappingProxyType(signature)]}
    source = Message(
        MessageRole.ASSISTANT, "", tool_calls=[ToolCallPayload("call", "tool", "{}", metadata=metadata)],
    )
    executor = AgentNodeExecutor(SimpleNamespace())
    cloned = executor._build_initial_timeline([source])[0]
    provider = cloned.tool_calls[0].metadata["provider"][0]
    assert isinstance(provider, MappingProxyType)
    provider["parts"].append("clone")
    assert signature["parts"] == ["original"]
