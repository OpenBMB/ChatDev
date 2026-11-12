"""Unit tests for edge payload processors and regex processor configuration validation."""

from unittest.mock import MagicMock

import pytest

from entity.configs.base import ConfigError
from entity.configs.edge.edge_processor import RegexEdgeProcessorConfig
from entity.messages import Message, MessageRole
from runtime.edge.processors.base import ProcessorFactoryContext
from runtime.edge.processors.regex_processor import RegexEdgePayloadProcessor


def test_regex_processor_config_valid():
    """Verify that valid regex patterns and capture groups pass validation."""
    cfg1 = RegexEdgeProcessorConfig.from_dict({"pattern": r"\d+"}, path="edge.process")
    assert cfg1.pattern == r"\d+"
    assert cfg1.group is None

    cfg2 = RegexEdgeProcessorConfig.from_dict(
        {"pattern": r"(\w+): (\d+)", "group": 2}, path="edge.process"
    )
    assert cfg2.group == 2

    cfg3 = RegexEdgeProcessorConfig.from_dict(
        {"pattern": r"(?P<val>[a-z]+)", "group": "val"}, path="edge.process"
    )
    assert cfg3.group == "val"


def test_regex_processor_config_invalid_pattern_raises_config_error():
    """Verify that syntactically invalid regular expressions raise ConfigError at validation time."""
    with pytest.raises(ConfigError) as exc_info:
        RegexEdgeProcessorConfig.from_dict(
            {"pattern": r"[unclosed"}, path="edge.process"
        )
    assert "Invalid regular expression pattern" in str(exc_info.value)
    assert exc_info.value.path == "edge.process.pattern"


def test_regex_processor_config_out_of_bounds_group_index_raises_config_error():
    """Verify that group indices exceeding the pattern's capture group count or negative indices raise ConfigError."""
    # Pattern has 1 capture group, requesting group 2 must fail
    with pytest.raises(ConfigError) as exc_info:
        RegexEdgeProcessorConfig.from_dict(
            {"pattern": r"(\w+)", "group": 2}, path="edge.process"
        )
    assert "out of bounds" in str(exc_info.value)
    assert "pattern has 1 capture groups" in str(exc_info.value)
    assert exc_info.value.path == "edge.process.group"

    # Pattern has 0 capture groups, requesting group 1 must fail
    with pytest.raises(ConfigError) as exc_info:
        RegexEdgeProcessorConfig.from_dict(
            {"pattern": r"\w+", "group": 1}, path="edge.process"
        )
    assert "out of bounds" in str(exc_info.value)
    assert "pattern has 0 capture groups" in str(exc_info.value)

    # Negative group index must fail
    with pytest.raises(ConfigError) as exc_info:
        RegexEdgeProcessorConfig.from_dict(
            {"pattern": r"(\w+)", "group": -1}, path="edge.process"
        )
    assert "out of bounds" in str(exc_info.value)


def test_regex_processor_config_missing_named_group_raises_config_error():
    """Verify that nonexistent named capture groups raise ConfigError."""
    with pytest.raises(ConfigError) as exc_info:
        RegexEdgeProcessorConfig.from_dict(
            {"pattern": r"(?P<id>\d+)", "group": "name"}, path="edge.process"
        )
    assert "Capture group name 'name' not found in pattern" in str(exc_info.value)
    assert exc_info.value.path == "edge.process.group"


def test_regex_processor_transform_single_and_multiple():
    """Verify regex payload transformation for single and multiple matches with template."""
    ctx = ProcessorFactoryContext(log_manager=MagicMock())
    config = RegexEdgeProcessorConfig.from_dict(
        {
            "pattern": r"Task #(\d+)",
            "group": 1,
            "multiple": True,
            "template": "ID:{match}",
        },
        path="edge.process",
    )
    processor = RegexEdgePayloadProcessor(config, ctx)

    payload = Message(
        role=MessageRole.ASSISTANT,
        content="Completed Task #101 and Task #202 in parallel.",
    )
    result = processor.transform(
        payload,
        source_result=payload,
        from_node=MagicMock(id="node_a"),
        edge_link=MagicMock(target=MagicMock(id="node_b")),
        log_manager=MagicMock(),
        context=MagicMock(),
    )
    assert result is not None
    assert result.content == "ID:101\nID:202"
    assert result.role == MessageRole.ASSISTANT


def test_regex_processor_named_group_extraction():
    """Verify extraction using a named capture group."""
    ctx = ProcessorFactoryContext(log_manager=MagicMock())
    config = RegexEdgeProcessorConfig.from_dict(
        {"pattern": r"score:\s*(?P<score>\d+\.\d+)", "group": "score"},
        path="edge.process",
    )
    processor = RegexEdgePayloadProcessor(config, ctx)

    payload = Message(
        role=MessageRole.USER,
        content="Evaluation finished with score: 0.95 and high accuracy.",
    )
    result = processor.transform(
        payload,
        source_result=payload,
        from_node=MagicMock(id="node_a"),
        edge_link=MagicMock(target=MagicMock(id="node_b")),
        log_manager=MagicMock(),
        context=MagicMock(),
    )
    assert result is not None
    assert result.content == "0.95"


def test_regex_processor_no_match_behaviors():
    """Verify pass, default, and drop behaviors when no match occurs."""
    ctx = ProcessorFactoryContext(log_manager=MagicMock())
    payload = Message(role=MessageRole.USER, content="No numbers here.")

    # on_no_match = 'pass' (default)
    cfg_pass = RegexEdgeProcessorConfig.from_dict(
        {"pattern": r"\d+", "on_no_match": "pass"}, path="edge.process"
    )
    proc_pass = RegexEdgePayloadProcessor(cfg_pass, ctx)
    res_pass = proc_pass.transform(
        payload,
        source_result=payload,
        from_node=MagicMock(id="a"),
        edge_link=MagicMock(target=MagicMock(id="b")),
        log_manager=MagicMock(),
        context=MagicMock(),
    )
    assert res_pass is not None
    assert res_pass.content == "No numbers here."

    # on_no_match = 'default'
    cfg_default = RegexEdgeProcessorConfig.from_dict(
        {"pattern": r"\d+", "on_no_match": "default", "default_value": "NONE"},
        path="edge.process",
    )
    proc_default = RegexEdgePayloadProcessor(cfg_default, ctx)
    res_default = proc_default.transform(
        payload,
        source_result=payload,
        from_node=MagicMock(id="a"),
        edge_link=MagicMock(target=MagicMock(id="b")),
        log_manager=MagicMock(),
        context=MagicMock(),
    )
    assert res_default is not None
    assert res_default.content == "NONE"

    # on_no_match = 'drop'
    cfg_drop = RegexEdgeProcessorConfig.from_dict(
        {"pattern": r"\d+", "on_no_match": "drop"}, path="edge.process"
    )
    proc_drop = RegexEdgePayloadProcessor(cfg_drop, ctx)
    res_drop = proc_drop.transform(
        payload,
        source_result=payload,
        from_node=MagicMock(id="a"),
        edge_link=MagicMock(target=MagicMock(id="b")),
        log_manager=MagicMock(),
        context=MagicMock(),
    )
    assert res_drop is None
