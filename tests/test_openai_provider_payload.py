"""Regression tests for OpenAI provider transport parameters (issue #674)."""

from types import SimpleNamespace

from runtime.node.agent.providers.openai_provider import OpenAIProvider


def _provider(**params):
    config = SimpleNamespace(
        base_url="http://127.0.0.1:1234/v1",
        api_key="test-key",
        name="test-model",
        provider="openai",
        params=params,
        token_tracker=None,
        node_id="test-node",
    )
    return OpenAIProvider(config)


def test_chat_payload_strips_protocol_and_forwards_timeout():
    provider = _provider(protocol="chat", timeout=42)

    payload = provider._build_chat_payload(
        conversation=[],
        tool_specs=None,
        raw_params={"protocol": "chat", "timeout": 42},
    )

    assert "protocol" not in payload
    assert payload["timeout"] == 42


def test_chat_payload_uses_default_timeout():
    provider = _provider(protocol="chat")

    payload = provider._build_chat_payload(
        conversation=[],
        tool_specs=None,
        raw_params={"protocol": "chat"},
    )

    assert "protocol" not in payload
    assert payload["timeout"] == 300


def test_responses_payload_strips_protocol():
    provider = _provider(protocol="responses", timeout=42)

    payload = provider._build_request_payload(
        timeline=[],
        tool_specs=None,
        raw_params={"protocol": "responses", "timeout": 42},
    )

    assert "protocol" not in payload
    assert payload["timeout"] == 42


def test_protocol_still_selects_the_api_mode():
    without_responses = SimpleNamespace()
    with_responses = SimpleNamespace(responses=object())

    assert _provider(protocol="chat")._is_chat_completions_mode(without_responses) is True
    assert _provider(protocol="responses")._is_chat_completions_mode(with_responses) is False
    assert _provider()._is_chat_completions_mode(without_responses) is True
    assert _provider()._is_chat_completions_mode(with_responses) is False


def test_graph_module_has_no_utf8_bom():
    from pathlib import Path

    source = Path(__file__).resolve().parents[1] / "workflow" / "graph.py"
    assert not source.read_bytes().startswith(b"\xef\xbb\xbf")
