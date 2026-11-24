"""Tests for TokenUsage and TokenTracker."""

import json
from datetime import datetime

import pytest

from utils.token_tracker import TokenTracker, TokenUsage


def test_token_usage_defaults():
    usage = TokenUsage()
    assert usage.input_tokens == 0
    assert usage.output_tokens == 0
    assert usage.total_tokens == 0
    assert usage.metadata == {}
    assert usage.node_id is None
    assert usage.model_name is None
    assert usage.provider is None


def test_token_usage_auto_calculates_total():
    usage = TokenUsage(input_tokens=15, output_tokens=25)
    assert usage.input_tokens == 15
    assert usage.output_tokens == 25
    assert usage.total_tokens == 40


def test_token_usage_type_coercion_and_clamping():
    usage = TokenUsage(input_tokens="100", output_tokens=50.5, total_tokens=None)
    assert usage.input_tokens == 100
    assert usage.output_tokens == 50
    assert usage.total_tokens == 150

    # Negative tokens clamped to 0
    neg_usage = TokenUsage(input_tokens=-10, output_tokens=-5, total_tokens=-1)
    assert neg_usage.input_tokens == 0
    assert neg_usage.output_tokens == 0
    assert neg_usage.total_tokens == 0


def test_token_usage_to_dict():
    dt = datetime(2026, 11, 25, 12, 0, 0)
    usage = TokenUsage(
        input_tokens=10,
        output_tokens=20,
        total_tokens=30,
        metadata={"cost": 0.002},
        timestamp=dt,
        node_id="node_a",
        model_name="gpt-4o",
        workflow_id="wf_1",
        provider="openai",
    )
    d = usage.to_dict()
    assert d == {
        "input_tokens": 10,
        "output_tokens": 20,
        "total_tokens": 30,
        "metadata": {"cost": 0.002},
        "timestamp": dt.isoformat(),
        "node_id": "node_a",
        "model_name": "gpt-4o",
        "workflow_id": "wf_1",
        "provider": "openai",
    }


def test_tracker_record_usage_accumulates():
    tracker = TokenTracker(workflow_id="wf_test")
    u1 = TokenUsage(input_tokens=100, output_tokens=50)
    u2 = TokenUsage(input_tokens=200, output_tokens=100)

    tracker.record_usage("agent_node", "gpt-4o", u1, provider="openai")
    tracker.record_usage("agent_node", "gpt-4o", u2, provider="openai")

    total = tracker.get_total_usage()
    assert total.input_tokens == 300
    assert total.output_tokens == 150
    assert total.total_tokens == 450

    node = tracker.get_node_usage("agent_node")
    assert node.input_tokens == 300
    assert node.output_tokens == 150
    assert node.total_tokens == 450
    assert node.provider == "openai"

    assert tracker.get_node_execution_count("agent_node") == 2
    assert tracker.get_node_execution_count("non_existent") == 0


def test_tracker_record_usage_dict_input():
    tracker = TokenTracker(workflow_id="wf_test")
    tracker.record_usage(
        "node_1",
        "gemini-1.5-pro",
        {"input_tokens": 50, "output_tokens": 25},
        provider="google",
    )
    total = tracker.get_total_usage()
    assert total.input_tokens == 50
    assert total.output_tokens == 25
    assert total.total_tokens == 75


def test_tracker_record_usage_rejects_invalid_type():
    tracker = TokenTracker(workflow_id="wf_test")
    with pytest.raises(TypeError, match="Expected TokenUsage or dict"):
        tracker.record_usage("node_1", "model_1", 12345)


def test_tracker_record_usage_ignores_none():
    tracker = TokenTracker(workflow_id="wf_test")
    tracker.record_usage("node_1", "model_1", None)
    assert tracker.get_total_usage().total_tokens == 0
    assert len(tracker.call_history) == 0


def test_tracker_lookups_do_not_mutate_state():
    tracker = TokenTracker(workflow_id="wf_test")
    # Looking up a node that was never recorded should return empty TokenUsage without adding to node_usages
    node = tracker.get_node_usage("ghost_node")
    assert node.total_tokens == 0
    assert "ghost_node" not in tracker.get_token_usage()["node_usages"]

    model = tracker.get_model_usage("ghost_model")
    assert model.total_tokens == 0
    assert "ghost_model" not in tracker.get_token_usage()["model_usages"]


def test_tracker_reset():
    tracker = TokenTracker(workflow_id="wf_test")
    tracker.record_usage(
        "node_1", "model_1", TokenUsage(input_tokens=10, output_tokens=10)
    )
    assert tracker.get_total_usage().total_tokens == 20

    tracker.reset()
    assert tracker.get_total_usage().total_tokens == 0
    assert tracker.get_node_execution_count("node_1") == 0
    assert len(tracker.call_history) == 0
    assert tracker.get_token_usage()["node_usages"] == {}


def test_tracker_export_to_file(tmp_path):
    tracker = TokenTracker(workflow_id="wf_test")
    tracker.record_usage(
        "node_1",
        "model_1",
        TokenUsage(
            input_tokens=40,
            output_tokens=60,
            metadata={"time": datetime(2026, 11, 25, 10, 0, 0)},
        ),
    )
    target_path = tmp_path / "subdir" / "tokens.json"
    tracker.export_to_file(str(target_path))

    assert target_path.exists()
    data = json.loads(target_path.read_text(encoding="utf-8"))
    assert data["workflow_id"] == "wf_test"
    assert data["total_usage"]["total_tokens"] == 100
    assert len(data["call_history"]) == 1
