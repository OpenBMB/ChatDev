import json

import pytest

from entity.messages import Message, MessageRole
from runtime.node.splitter import JsonPathSplitter


@pytest.mark.parametrize("item", [True, False, None, 0, 1.25, {"text": "你好"}, [1, False]])
def test_non_string_items_remain_valid_json(item):
    message = Message(role=MessageRole.USER, content=json.dumps({"items": [item]}))
    units = JsonPathSplitter("items").split([message])
    assert len(units) == 1
    assert json.loads(units[0][0].text_content()) == item
    assert units[0][0].metadata["split_source"] == "json_path"


@pytest.mark.parametrize("text", ["hello", "你好", ""])
def test_string_items_stay_plain_text(text):
    message = Message(role=MessageRole.USER, content=json.dumps({"items": [text]}))
    assert JsonPathSplitter("items").split([message])[0][0].text_content() == text


def test_invalid_json_is_still_passed_through():
    message = Message(role=MessageRole.USER, content="not JSON")
    assert JsonPathSplitter("items").split([message]) == [[message]]
