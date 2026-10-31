"""Regression tests for OpenAI provider internal protocol routing."""

from entity.configs.node.agent import AgentConfig
from entity.messages import Message, MessageRole
from runtime.node.agent.providers.openai_provider import OpenAIProvider


def _provider() -> OpenAIProvider:
    return OpenAIProvider(
        AgentConfig(
            path="test.model",
            provider="openai",
            base_url="",
            name="gpt-test",
            api_key="test-key",
            params={},
        )
    )


def test_responses_payload_does_not_forward_protocol_param():
    payload = _provider()._build_request_payload(
        [Message(role=MessageRole.USER, content="hello")],
        tool_specs=None,
        raw_params={"protocol": "responses", "temperature": 0.2},
    )

    assert payload["temperature"] == 0.2
    assert "protocol" not in payload


def test_chat_payload_does_not_forward_protocol_param():
    payload = _provider()._build_chat_payload(
        [Message(role=MessageRole.USER, content="hello")],
        tool_specs=None,
        raw_params={"protocol": "chat", "temperature": 0.2},
    )

    assert payload["temperature"] == 0.2
    assert "protocol" not in payload
