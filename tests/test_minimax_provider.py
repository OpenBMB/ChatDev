"""Tests for the MiniMax agent provider."""

import os
import re
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from entity.configs.node.agent import AgentConfig
from entity.messages import (
    Message,
    MessageBlock,
    MessageBlockType,
    MessageRole,
    ToolCallPayload,
)
from entity.tool_spec import ToolSpec
from runtime.node.agent.providers.minimax_provider import (
    MiniMaxProvider,
    _MINIMAX_DEFAULT_BASE_URL,
    _MINIMAX_TEMP_MIN,
    _MINIMAX_TEMP_MAX,
    _THINK_TAG_RE,
)
from runtime.node.agent.providers.response import ModelResponse
from utils.token_tracker import TokenTracker, TokenUsage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(
    *,
    provider: str = "minimax",
    name: str = "MiniMax-M2.7",
    base_url: str = "",
    api_key: str = "",
    params: Optional[Dict[str, Any]] = None,
) -> AgentConfig:
    """Create a minimal AgentConfig for testing."""
    return AgentConfig(
        provider=provider,
        name=name,
        base_url=base_url,
        api_key=api_key,
        params=params or {},
        path="test",
    )


def _make_chat_response(content: str = "Hello", tool_calls=None):
    """Create a mock OpenAI Chat Completions response."""
    mock_message = MagicMock()
    mock_message.content = content
    mock_message.tool_calls = tool_calls or []
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = MagicMock(
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        input_tokens=None,
        output_tokens=None,
    )
    return mock_response


# ---------------------------------------------------------------------------
# Unit tests – initialization
# ---------------------------------------------------------------------------


class TestMiniMaxProviderInit:
    """Tests for MiniMaxProvider initialization and defaults."""

    def test_default_base_url_applied(self):
        config = _make_config(base_url="")
        provider = MiniMaxProvider(config)
        assert provider.base_url == _MINIMAX_DEFAULT_BASE_URL

    def test_custom_base_url_preserved(self):
        custom = "https://custom.minimax.io/v1"
        config = _make_config(base_url=custom)
        provider = MiniMaxProvider(config)
        assert provider.base_url == custom

    def test_api_key_from_env(self):
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key-123"}):
            config = _make_config(api_key="")
            provider = MiniMaxProvider(config)
            assert provider.config.api_key == "test-key-123"

    def test_explicit_api_key_preserved(self):
        config = _make_config(api_key="explicit-key")
        provider = MiniMaxProvider(config)
        assert provider.config.api_key == "explicit-key"

    def test_model_name_stored(self):
        config = _make_config(name="MiniMax-M2.7-highspeed")
        provider = MiniMaxProvider(config)
        assert provider.model_name == "MiniMax-M2.7-highspeed"


# ---------------------------------------------------------------------------
# Unit tests – chat completions mode
# ---------------------------------------------------------------------------


class TestChatCompletionsMode:
    """MiniMax always uses Chat Completions, never Responses API."""

    def test_always_chat_mode(self):
        config = _make_config()
        provider = MiniMaxProvider(config)
        # Even with a client that has a responses attribute
        mock_client = MagicMock()
        mock_client.responses = MagicMock()
        assert provider._is_chat_completions_mode(mock_client) is True

    def test_chat_mode_no_responses(self):
        config = _make_config()
        provider = MiniMaxProvider(config)
        mock_client = MagicMock(spec=[])
        assert provider._is_chat_completions_mode(mock_client) is True


# ---------------------------------------------------------------------------
# Unit tests – temperature clamping
# ---------------------------------------------------------------------------


class TestTemperatureClamping:
    """MiniMax requires temperature in (0.0, 1.0]."""

    def test_zero_temperature_clamped(self):
        config = _make_config()
        provider = MiniMaxProvider(config)
        conversation = [Message(role=MessageRole.USER, content="hi")]
        payload = provider._build_chat_payload(
            conversation, None, {"temperature": 0}
        )
        assert payload["temperature"] == _MINIMAX_TEMP_MIN

    def test_negative_temperature_clamped(self):
        config = _make_config()
        provider = MiniMaxProvider(config)
        conversation = [Message(role=MessageRole.USER, content="hi")]
        payload = provider._build_chat_payload(
            conversation, None, {"temperature": -0.5}
        )
        assert payload["temperature"] == _MINIMAX_TEMP_MIN

    def test_high_temperature_clamped(self):
        config = _make_config()
        provider = MiniMaxProvider(config)
        conversation = [Message(role=MessageRole.USER, content="hi")]
        payload = provider._build_chat_payload(
            conversation, None, {"temperature": 2.0}
        )
        assert payload["temperature"] == _MINIMAX_TEMP_MAX

    def test_valid_temperature_preserved(self):
        config = _make_config()
        provider = MiniMaxProvider(config)
        conversation = [Message(role=MessageRole.USER, content="hi")]
        payload = provider._build_chat_payload(
            conversation, None, {"temperature": 0.7}
        )
        assert payload["temperature"] == 0.7

    def test_boundary_temperature_one(self):
        config = _make_config()
        provider = MiniMaxProvider(config)
        conversation = [Message(role=MessageRole.USER, content="hi")]
        payload = provider._build_chat_payload(
            conversation, None, {"temperature": 1.0}
        )
        assert payload["temperature"] == 1.0

    def test_no_temperature_uses_default(self):
        config = _make_config()
        provider = MiniMaxProvider(config)
        conversation = [Message(role=MessageRole.USER, content="hi")]
        payload = provider._build_chat_payload(
            conversation, None, {}
        )
        # Default from parent is 0.7
        assert payload["temperature"] == 0.7


# ---------------------------------------------------------------------------
# Unit tests – think tag stripping
# ---------------------------------------------------------------------------


class TestThinkTagStripping:
    """<think> tags from reasoning models should be stripped."""

    def test_strip_think_from_string_content(self):
        config = _make_config()
        provider = MiniMaxProvider(config)
        msg = Message(
            role=MessageRole.ASSISTANT,
            content="<think>Internal reasoning here</think>The answer is 42.",
        )
        cleaned = provider._strip_think_tags(msg)
        assert cleaned.text_content() == "The answer is 42."

    def test_strip_think_from_block_content(self):
        config = _make_config()
        provider = MiniMaxProvider(config)
        blocks = [
            MessageBlock(MessageBlockType.TEXT, text="<think>reasoning</think>Result"),
        ]
        msg = Message(role=MessageRole.ASSISTANT, content=blocks)
        cleaned = provider._strip_think_tags(msg)
        assert cleaned.blocks()[0].text == "Result"

    def test_no_think_tags_unchanged(self):
        config = _make_config()
        provider = MiniMaxProvider(config)
        msg = Message(role=MessageRole.ASSISTANT, content="Normal response")
        cleaned = provider._strip_think_tags(msg)
        assert cleaned.text_content() == "Normal response"

    def test_multiline_think_tags(self):
        config = _make_config()
        provider = MiniMaxProvider(config)
        msg = Message(
            role=MessageRole.ASSISTANT,
            content="<think>\nStep 1\nStep 2\n</think>\nFinal answer",
        )
        cleaned = provider._strip_think_tags(msg)
        assert cleaned.text_content() == "Final answer"

    def test_user_message_not_stripped(self):
        config = _make_config()
        provider = MiniMaxProvider(config)
        msg = Message(
            role=MessageRole.USER,
            content="<think>user text</think>hello",
        )
        cleaned = provider._strip_think_tags(msg)
        assert "<think>" in cleaned.text_content()

    def test_tool_calls_preserved_after_stripping(self):
        config = _make_config()
        provider = MiniMaxProvider(config)
        tc = ToolCallPayload(id="tc1", function_name="get_weather", arguments='{"city":"SF"}')
        msg = Message(
            role=MessageRole.ASSISTANT,
            content="<think>reason</think>Let me check.",
            tool_calls=[tc],
        )
        cleaned = provider._strip_think_tags(msg)
        assert len(cleaned.tool_calls) == 1
        assert cleaned.tool_calls[0].function_name == "get_weather"


# ---------------------------------------------------------------------------
# Unit tests – response deserialization
# ---------------------------------------------------------------------------


class TestResponseDeserialization:
    """Test _deserialize_chat_response strips think tags automatically."""

    def test_deserialize_strips_think(self):
        config = _make_config()
        provider = MiniMaxProvider(config)
        response = _make_chat_response("<think>thinking</think>Answer")
        msg = provider._deserialize_chat_response(response)
        assert msg.text_content() == "Answer"

    def test_deserialize_normal_response(self):
        config = _make_config()
        provider = MiniMaxProvider(config)
        response = _make_chat_response("Hello world")
        msg = provider._deserialize_chat_response(response)
        assert msg.text_content() == "Hello world"


# ---------------------------------------------------------------------------
# Unit tests – token tracking
# ---------------------------------------------------------------------------


class TestTokenTracking:
    """Token usage should be reported with provider='minimax'."""

    def test_token_tracking_provider(self):
        config = _make_config()
        tracker = TokenTracker(workflow_id="test-wf")
        config.token_tracker = tracker
        config.node_id = "node-1"

        provider = MiniMaxProvider(config)
        response = _make_chat_response("hi")
        provider._track_token_usage(response)

        assert len(tracker.call_history) == 1
        assert tracker.call_history[0]["provider"] == "minimax"

    def test_no_tracker_no_error(self):
        config = _make_config()
        provider = MiniMaxProvider(config)
        response = _make_chat_response("hi")
        # Should not raise
        provider._track_token_usage(response)


# ---------------------------------------------------------------------------
# Unit tests – chat payload construction
# ---------------------------------------------------------------------------


class TestChatPayload:
    """Test payload construction for MiniMax."""

    def test_model_name_in_payload(self):
        config = _make_config(name="MiniMax-M2.7")
        provider = MiniMaxProvider(config)
        conversation = [Message(role=MessageRole.USER, content="hello")]
        payload = provider._build_chat_payload(conversation, None, {})
        assert payload["model"] == "MiniMax-M2.7"

    def test_tool_specs_in_payload(self):
        config = _make_config()
        provider = MiniMaxProvider(config)
        conversation = [Message(role=MessageRole.USER, content="What's the weather?")]
        spec = ToolSpec(
            name="get_weather",
            description="Get weather for a city",
            parameters={"type": "object", "properties": {"city": {"type": "string"}}},
        )
        payload = provider._build_chat_payload(conversation, [spec], {})
        assert "tools" in payload
        assert len(payload["tools"]) == 1
        assert payload["tools"][0]["function"]["name"] == "get_weather"

    def test_max_tokens_in_payload(self):
        config = _make_config()
        provider = MiniMaxProvider(config)
        conversation = [Message(role=MessageRole.USER, content="hi")]
        payload = provider._build_chat_payload(
            conversation, None, {"max_tokens": 1024}
        )
        assert payload["max_tokens"] == 1024


# ---------------------------------------------------------------------------
# Unit tests – provider registration
# ---------------------------------------------------------------------------


class TestProviderRegistration:
    """MiniMax should be registered as a built-in provider."""

    def test_minimax_registered(self):
        from runtime.node.agent.providers.base import ProviderRegistry
        import runtime.node.agent.providers.builtin_providers  # noqa: F401

        assert "minimax" in ProviderRegistry.list_providers()
        provider_cls = ProviderRegistry.get_provider("minimax")
        assert provider_cls is MiniMaxProvider

    def test_minimax_metadata(self):
        from runtime.node.agent.providers.base import ProviderRegistry
        import runtime.node.agent.providers.builtin_providers  # noqa: F401

        metadata = ProviderRegistry.iter_metadata()
        assert "minimax" in metadata
        assert metadata["minimax"]["label"] == "MiniMax"


# ---------------------------------------------------------------------------
# Unit tests – think tag regex
# ---------------------------------------------------------------------------


class TestThinkTagRegex:
    """Validate the regex pattern for think tag stripping."""

    def test_simple_think_tag(self):
        text = "<think>hello</think>world"
        assert _THINK_TAG_RE.sub("", text).strip() == "world"

    def test_multiline_think_tag(self):
        text = "<think>\nline1\nline2\n</think>\nresult"
        assert _THINK_TAG_RE.sub("", text).strip() == "result"

    def test_no_think_tag(self):
        text = "just normal text"
        assert _THINK_TAG_RE.sub("", text).strip() == "just normal text"

    def test_multiple_think_tags(self):
        text = "<think>a</think>first<think>b</think>second"
        assert _THINK_TAG_RE.sub("", text).strip() == "firstsecond"


# ---------------------------------------------------------------------------
# Unit tests – create_client
# ---------------------------------------------------------------------------


class TestCreateClient:
    """Test client creation."""

    @patch("runtime.node.agent.providers.openai_provider.OpenAI")
    def test_create_client_with_defaults(self, mock_openai_cls):
        config = _make_config(api_key="test-key")
        provider = MiniMaxProvider(config)
        client = provider.create_client()
        mock_openai_cls.assert_called_once_with(
            api_key="test-key",
            base_url=_MINIMAX_DEFAULT_BASE_URL,
        )

    @patch("runtime.node.agent.providers.openai_provider.OpenAI")
    def test_create_client_with_custom_url(self, mock_openai_cls):
        config = _make_config(api_key="key", base_url="https://custom.api/v1")
        provider = MiniMaxProvider(config)
        client = provider.create_client()
        mock_openai_cls.assert_called_once_with(
            api_key="key",
            base_url="https://custom.api/v1",
        )


# ---------------------------------------------------------------------------
# Integration tests (marked, require MINIMAX_API_KEY)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not os.environ.get("MINIMAX_API_KEY"),
    reason="MINIMAX_API_KEY not set",
)
class TestMiniMaxIntegration:
    """Integration tests that call the real MiniMax API."""

    def test_simple_completion(self):
        config = _make_config(
            api_key=os.environ["MINIMAX_API_KEY"],
            name="MiniMax-M2.7",
        )
        provider = MiniMaxProvider(config)
        client = provider.create_client()
        conversation = [Message(role=MessageRole.USER, content="Say 'hello' and nothing else.")]
        timeline = list(conversation)
        result = provider.call_model(client, conversation, timeline)
        assert isinstance(result, ModelResponse)
        text = result.message.text_content().lower()
        assert "hello" in text

    def test_highspeed_model(self):
        config = _make_config(
            api_key=os.environ["MINIMAX_API_KEY"],
            name="MiniMax-M2.7-highspeed",
        )
        provider = MiniMaxProvider(config)
        client = provider.create_client()
        conversation = [Message(role=MessageRole.USER, content="Reply with just the word 'ok'.")]
        timeline = list(conversation)
        result = provider.call_model(client, conversation, timeline)
        assert isinstance(result, ModelResponse)
        assert result.message.text_content().strip() != ""

    def test_token_usage_tracked(self):
        config = _make_config(
            api_key=os.environ["MINIMAX_API_KEY"],
            name="MiniMax-M2.7-highspeed",
        )
        tracker = TokenTracker(workflow_id="integ-test")
        config.token_tracker = tracker
        config.node_id = "test-node"

        provider = MiniMaxProvider(config)
        client = provider.create_client()
        conversation = [Message(role=MessageRole.USER, content="Say hi")]
        timeline = list(conversation)
        provider.call_model(client, conversation, timeline)

        usage = tracker.get_total_usage()
        assert usage.total_tokens > 0
