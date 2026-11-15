"""Unit tests for keyword edge condition configuration validation and evaluation."""

from unittest.mock import MagicMock
import pytest

from entity.configs.base import ConfigError
from entity.configs.edge.edge_condition import (
    EdgeConditionConfig,
    KeywordEdgeConditionConfig,
)
from runtime.edge.conditions.base import ConditionFactoryContext
from runtime.edge.conditions.keyword_manager import KeywordEdgeConditionManager


def test_keyword_edge_condition_config_valid():
    """Verify that valid keyword condition configs initialize with expected values."""
    config = KeywordEdgeConditionConfig.from_dict(
        {
            "any": ["SUCCESS", "OK"],
            "none": ["ERROR", "FAIL"],
            "regex": [r"\d+\.\d+", r"[a-z]+_\d+"],
            "case_sensitive": False,
            "default": True,
        },
        path="edge.condition.config",
    )
    assert config.any_keywords == ["SUCCESS", "OK"]
    assert config.none_keywords == ["ERROR", "FAIL"]
    assert config.regex_patterns == [r"\d+\.\d+", r"[a-z]+_\d+"]
    assert config.case_sensitive is False
    assert config.default is True


def test_keyword_edge_condition_config_invalid_regex_raises_config_error():
    """Verify that an invalid regular expression in regex_patterns raises ConfigError."""
    with pytest.raises(ConfigError) as exc_info:
        KeywordEdgeConditionConfig.from_dict(
            {"regex": [r"[unclosed"]},
            path="edge.condition.config",
        )
    assert "Invalid regular expression pattern '[unclosed'" in str(exc_info.value)
    assert exc_info.value.path == "edge.condition.config.regex"


def test_keyword_edge_condition_manager_any_and_none():
    """Verify any/none keyword logic, priority of none keywords, and case sensitivity."""
    ctx = ConditionFactoryContext(log_manager=MagicMock())
    exec_ctx = MagicMock()

    # Case-insensitive
    cfg_ci = KeywordEdgeConditionConfig.from_dict(
        {"any": ["success"], "none": ["fatal"], "case_sensitive": False},
        path="edge.condition.config",
    )
    mgr_ci = KeywordEdgeConditionManager(cfg_ci, ctx, exec_ctx)
    assert mgr_ci._evaluate("Status: SUCCESS!") is True
    assert mgr_ci._evaluate("Status: FATAL error") is False
    assert (
        mgr_ci._evaluate("Status: SUCCESS but FATAL error") is False
    )  # none has priority
    assert mgr_ci._evaluate("Status: pending") is False

    # Case-sensitive
    cfg_cs = KeywordEdgeConditionConfig.from_dict(
        {"any": ["Ready"], "case_sensitive": True},
        path="edge.condition.config",
    )
    mgr_cs = KeywordEdgeConditionManager(cfg_cs, ctx, exec_ctx)
    assert mgr_cs._evaluate("System is Ready") is True
    assert mgr_cs._evaluate("System is ready") is False


def test_keyword_edge_condition_manager_regex_matching():
    """Verify regular expression evaluation in keyword edge condition manager."""
    ctx = ConditionFactoryContext(log_manager=MagicMock())
    exec_ctx = MagicMock()

    config = KeywordEdgeConditionConfig.from_dict(
        {"regex": [r"item_\d{3}"], "case_sensitive": False},
        path="edge.condition.config",
    )
    manager = KeywordEdgeConditionManager(config, ctx, exec_ctx)
    assert manager._evaluate("Processing ITEM_042 now") is True
    assert manager._evaluate("Processing item_none now") is False


def test_keyword_edge_condition_manager_default_fallback():
    """Verify default value fallback when any/regex do not match."""
    ctx = ConditionFactoryContext(log_manager=MagicMock())
    exec_ctx = MagicMock()

    cfg_default_true = KeywordEdgeConditionConfig.from_dict(
        {"any": ["confirmed"], "default": True},
        path="edge.condition.config",
    )
    mgr_default_true = KeywordEdgeConditionManager(cfg_default_true, ctx, exec_ctx)
    assert mgr_default_true._evaluate("unrelated text") is True
    assert mgr_default_true._evaluate("confirmed action") is True

    cfg_default_false = KeywordEdgeConditionConfig.from_dict(
        {"any": ["confirmed"], "default": False},
        path="edge.condition.config",
    )
    mgr_default_false = KeywordEdgeConditionManager(cfg_default_false, ctx, exec_ctx)
    assert mgr_default_false._evaluate("unrelated text") is False


def test_keyword_edge_condition_manager_none_data():
    """Verify that passing None as payload text does not raise AttributeError."""
    ctx = ConditionFactoryContext(log_manager=MagicMock())
    exec_ctx = MagicMock()

    config = KeywordEdgeConditionConfig.from_dict(
        {"any": ["trigger"], "default": False},
        path="edge.condition.config",
    )
    manager = KeywordEdgeConditionManager(config, ctx, exec_ctx)
    assert manager._evaluate(None) is False


def test_edge_condition_config_integration_with_keyword_type():
    """Verify integration through EdgeConditionConfig wrapper."""
    edge_cond = EdgeConditionConfig.from_dict(
        {"type": "keyword", "config": {"any": ["done"]}},
        path="edge.condition",
    )
    assert edge_cond.type == "keyword"
    assert isinstance(edge_cond.config, KeywordEdgeConditionConfig)
    assert edge_cond.config.any_keywords == ["done"]

    with pytest.raises(ConfigError) as exc_info:
        EdgeConditionConfig.from_dict(
            {"type": "keyword", "config": {"regex": [r"(?P<unclosed"]}},
            path="edge.condition",
        )
    assert "Invalid regular expression pattern" in str(exc_info.value)
    assert exc_info.value.path == "edge.condition.config.regex"
