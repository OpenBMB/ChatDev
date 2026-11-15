"""Unit tests for HumanPromptService, CliPromptChannel, and PromptResult."""

from unittest.mock import MagicMock

from entity.messages import MessageBlock, MessageBlockType
from utils.human_prompt import (
    CliPromptChannel,
    HumanPromptService,
    PromptResult,
    resolve_prompt_channel,
)


def test_prompt_result_defaults_and_message_content():
    # Default text is empty string, blocks is None
    res = PromptResult()
    assert res.text == ""
    assert res.blocks is None
    assert res.as_message_content() == ""

    # When blocks are set, as_message_content returns blocks
    block = MessageBlock.text_block("hello")
    res_with_blocks = PromptResult(text="hello", blocks=[block])
    assert res_with_blocks.as_message_content() == [block]

    # When blocks is None but text is set
    res_text_only = PromptResult(text="user message")
    assert res_text_only.as_message_content() == "user message"


def test_cli_prompt_channel_normal_response():
    channel = CliPromptChannel(input_func=lambda _: "approved")
    result = channel.request(node_id="human_1", task="Review document", inputs="Sample draft")
    assert result.text == "approved"
    assert result.blocks is not None
    assert len(result.blocks) == 1
    assert result.blocks[0].text == "approved"


def test_cli_prompt_channel_eof_handling():
    def raise_eof(_):
        raise EOFError("stdin closed")

    channel = CliPromptChannel(input_func=raise_eof)
    result = channel.request(node_id="human_1", task="Review document")
    assert result.text == ""
    assert result.blocks is not None
    assert len(result.blocks) == 1
    assert result.blocks[0].text == ""


def test_sanitize_response():
    # None should return empty string, never "None"
    assert HumanPromptService._sanitize_response(None) == ""

    # Normal strings
    assert HumanPromptService._sanitize_response("valid text") == "valid text"
    assert HumanPromptService._sanitize_response("") == ""

    # Non-string scalar types convert properly
    assert HumanPromptService._sanitize_response(123) == "123"
    assert HumanPromptService._sanitize_response(True) == "True"


def test_normalize_result_with_none_and_scalars():
    log_manager = MagicMock()
    channel = MagicMock()
    service = HumanPromptService(log_manager=log_manager, channel=channel)

    # None raw_result
    normalized_none = service._normalize_result(None)
    assert normalized_none.text == ""
    assert normalized_none.blocks is not None
    assert len(normalized_none.blocks) == 1
    assert normalized_none.blocks[0].text == ""

    # Plain string raw_result
    normalized_str = service._normalize_result("raw string response")
    assert normalized_str.text == "raw string response"
    assert normalized_str.blocks[0].text == "raw string response"

    # PromptResult raw_result pass-through
    pr = PromptResult(text="already prompt result")
    assert service._normalize_result(pr) is pr


def test_normalize_blocks_fallback_and_none_text():
    log_manager = MagicMock()
    channel = MagicMock()
    service = HumanPromptService(log_manager=log_manager, channel=channel)

    # Empty blocks list falls back to fallback_text
    empty_blocks = service._normalize_blocks([], fallback_text="fallback text")
    assert len(empty_blocks) == 1
    assert empty_blocks[0].text == "fallback text"

    # None fallback_text gracefully normalizes to ""
    none_fallback = service._normalize_blocks(None, fallback_text=None)
    assert len(none_fallback) == 1
    assert none_fallback[0].text == ""

    # Block with None text normalizes safely
    block_with_none = MessageBlock(type=MessageBlockType.TEXT, text=None)
    normalized = service._normalize_blocks([block_with_none], fallback_text="unused")
    assert len(normalized) == 1
    assert normalized[0].text == ""


def test_human_prompt_service_request_end_to_end():
    log_manager = MagicMock()
    channel = MagicMock()
    service = HumanPromptService(log_manager=log_manager, channel=channel, session_id="sess_123")

    channel.request.return_value = PromptResult(text="user feedback", metadata={"channel": "mock"})

    result = service.request(
        "node_review",
        "Please approve PR",
        inputs="diff content",
        metadata={"priority": "high"},
    )

    assert result.text == "user feedback"
    assert result.blocks[0].text == "user feedback"
    assert result.metadata["priority"] == "high"
    assert result.metadata["channel"] == "mock"
    assert result.metadata["session_id"] == "sess_123"

    log_manager.record_human_interaction.assert_called_once()
    args, _ = log_manager.record_human_interaction.call_args
    assert args[0] == "node_review"
    assert args[1] == "diff content"
    assert args[2] == "user feedback"


def test_human_prompt_service_request_with_none_channel_return():
    log_manager = MagicMock()
    channel = MagicMock()
    service = HumanPromptService(log_manager=log_manager, channel=channel)

    channel.request.return_value = None

    result = service.request("node_review", "Please approve PR")

    assert result.text == ""
    assert result.blocks[0].text == ""
    log_manager.record_human_interaction.assert_called_once()
    args, _ = log_manager.record_human_interaction.call_args
    assert args[2] == ""


def test_resolve_prompt_channel():
    assert resolve_prompt_channel(None) is None

    class HookWithGetter:
        def get_prompt_channel(self):
            return "channel_from_getter"

    class HookWithAttr:
        prompt_channel = "channel_from_attr"

    class EmptyHook:
        pass

    assert resolve_prompt_channel(HookWithGetter()) == "channel_from_getter"
    assert resolve_prompt_channel(HookWithAttr()) == "channel_from_attr"
    assert resolve_prompt_channel(EmptyHook()) is None
