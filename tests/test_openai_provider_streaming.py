"""Tests for OpenAIProvider streaming chat completions (issue #653).

Anthropic-backed OpenAI-compatible endpoints reject non-streaming requests
that run longer than 10 minutes. With ``params.stream: true`` on the model
node, the provider must issue a streaming request and reassemble the chunks
into the classic chat.completion shape the rest of the pipeline expects.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import openai
import pytest

from entity.configs import AgentConfig
from entity.messages import Message, MessageRole
from runtime.node.agent.providers.openai_provider import OpenAIProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_provider(params=None) -> OpenAIProvider:
    config = MagicMock(spec=AgentConfig)
    config.base_url = None
    config.api_key = "test-key"
    config.name = "test-model"
    config.provider = "openai"
    config.params = params or {}
    config.token_tracker = None
    return OpenAIProvider(config)


def _chunk(content=None, role=None, tool_calls=None, finish_reason=None, usage=None):
    delta = SimpleNamespace(role=role, content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(index=0, delta=delta, finish_reason=finish_reason)
    return SimpleNamespace(
        id="chatcmpl-123",
        model="test-model",
        created=1,
        choices=[choice] if (content or role or tool_calls or finish_reason) else [],
        usage=usage,
    )


def _tool_call_delta(index, call_id=None, name=None, arguments=None):
    return SimpleNamespace(
        index=index,
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def _make_client(chunks):
    client = MagicMock()
    client.chat.completions.create.return_value = iter(chunks)
    return client


# ---------------------------------------------------------------------------
# Non-streaming default is preserved
# ---------------------------------------------------------------------------

def test_default_call_is_non_streaming():
    provider = _make_provider()
    client = MagicMock()
    provider._create_chat_completion(client, {"model": "test-model", "messages": []})

    kwargs = client.chat.completions.create.call_args.kwargs
    assert "stream" not in kwargs
    assert "stream_options" not in kwargs


# ---------------------------------------------------------------------------
# Streaming opt-in
# ---------------------------------------------------------------------------

def test_stream_param_enables_streaming_request():
    provider = _make_provider(params={"stream": True})
    client = _make_client([_chunk(content="hi", finish_reason="stop")])
    provider._create_chat_completion(client, {"model": "test-model", "messages": []})

    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["stream"] is True
    assert kwargs["stream_options"] == {"include_usage": True}


def test_stream_chunks_reassembled_into_classic_shape():
    provider = _make_provider(params={"stream": True})
    usage = SimpleNamespace(
        prompt_tokens=10, completion_tokens=5, total_tokens=15
    )
    client = _make_client([
        _chunk(role="assistant", content="Hello"),
        _chunk(content=", "),
        _chunk(content="world"),
        _chunk(finish_reason="stop"),
        _chunk(usage=usage),
    ])

    response = provider._create_chat_completion(
        client, {"model": "test-model", "messages": []}
    )

    assert response.choices[0].message.content == "Hello, world"
    assert response.choices[0].finish_reason == "stop"
    assert response.choices[0].message.tool_calls is None
    assert response.usage.total_tokens == 15

    # The reassembled response must satisfy the existing deserializer.
    message = provider._deserialize_chat_response(response)
    assert message.role is MessageRole.ASSISTANT
    assert message.text_content() == "Hello, world"

    # And token tracking must read the streamed usage payload.
    token_usage = provider.extract_token_usage(response)
    assert token_usage.input_tokens == 10
    assert token_usage.output_tokens == 5


def test_streamed_tool_calls_are_accumulated():
    provider = _make_provider(params={"stream": True})
    client = _make_client([
        _chunk(tool_calls=[_tool_call_delta(0, call_id="call_1", name="search")]),
        _chunk(tool_calls=[_tool_call_delta(0, arguments='{"query": ')]),
        _chunk(tool_calls=[_tool_call_delta(0, arguments='"chatdev"}')]),
        _chunk(finish_reason="tool_calls"),
    ])

    response = provider._create_chat_completion(
        client, {"model": "test-model", "messages": []}
    )

    calls = response.choices[0].message.tool_calls
    assert len(calls) == 1
    assert calls[0].id == "call_1"
    assert calls[0].function.name == "search"
    assert calls[0].function.arguments == '{"query": "chatdev"}'

    message = provider._deserialize_chat_response(response)
    assert message.tool_calls[0].function_name == "search"
    assert message.tool_calls[0].arguments == '{"query": "chatdev"}'


def test_stream_true_in_payload_params_also_streams():
    """`stream` passed through node params ends up in the payload; it must not
    reach the SDK as a bare kwarg on the reassembly path."""
    provider = _make_provider()
    client = _make_client([_chunk(content="ok", finish_reason="stop")])
    response = provider._create_chat_completion(
        client, {"model": "test-model", "messages": [], "stream": True}
    )
    assert response.choices[0].message.content == "ok"


def test_stream_options_rejection_falls_back_without_usage():
    provider = _make_provider(params={"stream": True})
    client = MagicMock()
    bad_request = openai.BadRequestError(
        message="stream_options not supported",
        response=MagicMock(status_code=400, headers={}),
        body=None,
    )
    client.chat.completions.create.side_effect = [
        bad_request,
        iter([_chunk(content="ok", finish_reason="stop")]),
    ]

    response = provider._create_chat_completion(
        client, {"model": "test-model", "messages": []}
    )

    assert response.choices[0].message.content == "ok"
    retry_kwargs = client.chat.completions.create.call_args.kwargs
    assert retry_kwargs["stream"] is True
    assert "stream_options" not in retry_kwargs


def test_call_model_streams_end_to_end():
    provider = _make_provider(params={"stream": True, "protocol": "chat"})
    client = _make_client([
        _chunk(role="assistant", content="done"),
        _chunk(finish_reason="stop"),
    ])

    timeline = []
    result = provider.call_model(
        client,
        conversation=[Message(role=MessageRole.USER, content="go")],
        timeline=timeline,
    )

    assert result.message.text_content() == "done"
    assert timeline[-1]["content"] == "done"
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["stream"] is True
