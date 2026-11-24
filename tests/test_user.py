"""Unit tests for call_user function calling tool."""

from unittest.mock import Mock

import pytest

from functions.function_calling.user import call_user
from utils.human_prompt import PromptResult


def test_call_user_with_mock_prompt_result():
    mock_prompt = Mock()
    mock_prompt.request.return_value = PromptResult(text="Operator approved")

    context = {
        "human_prompt": mock_prompt,
        "node_id": "test_node",
        "task_description": "Confirm deployment parameters",
        "metadata": {"session_id": "sess-123"},
    }

    response = call_user("Please confirm proceed with deployment", _context=context)

    assert response == "Operator approved"
    mock_prompt.request.assert_called_once_with(
        node_id="test_node",
        task_description="Confirm deployment parameters",
        inputs="Please confirm proceed with deployment",
        metadata={"session_id": "sess-123", "source": "function_tool"},
    )


def test_call_user_default_node_id_and_task_description():
    mock_prompt = Mock()
    mock_prompt.request.return_value = PromptResult(text="Yes")

    context = {"human_prompt": mock_prompt}

    response = call_user("Do you want to continue?", _context=context)

    assert response == "Yes"
    mock_prompt.request.assert_called_once_with(
        node_id="model_function_calling",
        task_description="Please respond to the model instruction.",
        inputs="Do you want to continue?",
        metadata={"source": "function_tool"},
    )


def test_call_user_without_context():
    response = call_user("Need assistance")
    assert (
        response
        == "Human prompt unavailable, default response for instruction: Need assistance"
    )


def test_call_user_with_none_prompt():
    response = call_user("Need assistance", _context={"human_prompt": None})
    assert (
        response
        == "Human prompt unavailable, default response for instruction: Need assistance"
    )


def test_call_user_with_invalid_prompt_object():
    class DummyInvalidPrompt:
        pass

    response = call_user(
        "Need assistance", _context={"human_prompt": DummyInvalidPrompt()}
    )
    assert (
        response
        == "Human prompt unavailable, default response for instruction: Need assistance"
    )


def test_call_user_with_non_dict_context():
    response = call_user("Need assistance", _context="invalid_context_type")  # type: ignore[arg-type]
    assert (
        response
        == "Human prompt unavailable, default response for instruction: Need assistance"
    )


@pytest.mark.parametrize(
    "invalid_instruction", [None, 123, 45.6, ["do this"], {"instr": "foo"}, True]
)
def test_call_user_rejects_non_string_instruction(invalid_instruction):
    with pytest.raises(TypeError, match="instruction must be a string"):
        call_user(invalid_instruction)  # type: ignore[arg-type]


@pytest.mark.parametrize("empty_instruction", ["", "   ", "\t\n  "])
def test_call_user_rejects_empty_instruction(empty_instruction):
    with pytest.raises(ValueError, match="instruction cannot be empty"):
        call_user(empty_instruction)


def test_call_user_handles_plain_string_result():
    mock_prompt = Mock()
    mock_prompt.request.return_value = "plain string response"

    context = {"human_prompt": mock_prompt}
    response = call_user("Query user", _context=context)

    assert response == "plain string response"


def test_call_user_handles_none_text_in_result():
    mock_prompt = Mock()
    mock_prompt.request.return_value = Mock(text=None)

    context = {"human_prompt": mock_prompt}
    response = call_user("Query user", _context=context)

    assert response == ""
