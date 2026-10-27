"""Offline regression tests for repeated loop timer releases."""

from unittest.mock import Mock

import pytest

from entity.configs import Node
from entity.messages import Message, MessageRole
from runtime.node.agent.tool.tool_manager import ToolManager
from runtime.node.executor import loop_timer_executor
from runtime.node.executor.base import ExecutionContext
from runtime.node.executor.loop_timer_executor import LoopTimerNodeExecutor
from utils.function_manager import FunctionManager
from utils.log_manager import LogManager


@pytest.fixture
def timer(monkeypatch, tmp_path):
    context = ExecutionContext(
        tool_manager=ToolManager(),
        function_manager=FunctionManager(tmp_path),
        log_manager=Mock(spec=LogManager),
    )
    clock = [1000.0]
    monkeypatch.setattr(loop_timer_executor.time, "time", lambda: clock[0])
    return LoopTimerNodeExecutor(context), clock


def make_node(node_id="timer", **config):
    return Node.from_dict(
        {
            "id": node_id,
            "type": "loop_timer",
            "config": {"max_duration": 2, **config},
        },
        path=f"graph.nodes.{node_id}",
    )


@pytest.mark.parametrize(
    ("unit", "multiplier"), [("seconds", 1), ("minutes", 60), ("hours", 3600)]
)
def test_standard_timer_resets_after_every_release(timer, unit, multiplier):
    executor, clock = timer
    node = make_node(duration_unit=unit, message="next cycle")
    inputs = [Message(role=MessageRole.USER, content="keep working")]
    duration = 2 * multiplier

    assert executor.execute(node, inputs) == []
    for cycle in range(1, 4):
        clock[0] = 1000 + cycle * duration - 0.5
        assert executor.execute(node, inputs) == []

        clock[0] += 0.5
        output = executor.execute(node, inputs)
        assert len(output) == 1
        assert output[0].role == MessageRole.ASSISTANT
        assert output[0].text_content() == "next cycle"
        assert output[0].metadata["loop_timer"]["elapsed_time"] == duration

        # A new interval must begin after the second release as well as the first.
        assert executor.execute(node, inputs) == []


def test_standard_timer_without_reset_keeps_releasing(timer):
    executor, clock = timer
    node = make_node(reset_on_emit=False)

    assert executor.execute(node, []) == []
    for elapsed in (2, 2.5, 4, 6):
        clock[0] = 1000 + elapsed
        output = executor.execute(node, [])
        assert len(output) == 1
        assert output[0].text_content() == "Time limit reached (2.0 seconds)"
        assert output[0].metadata["loop_timer"]["elapsed_time"] == elapsed


@pytest.mark.parametrize("reset_on_emit", [True, False])
def test_passthrough_timer_emits_only_once(timer, reset_on_emit):
    executor, clock = timer
    node = make_node(passthrough=True, reset_on_emit=reset_on_emit, message="done")
    inputs = [Message(role=MessageRole.USER, content="work")]

    assert executor.execute(node, inputs) is inputs
    clock[0] += 1
    assert executor.execute(node, inputs) is inputs
    clock[0] += 1
    output = executor.execute(node, inputs)
    assert len(output) == 1
    assert output[0].text_content() == "done"
    assert output[0].metadata["loop_timer"]["passthrough"] is True

    for elapsed in (2, 3, 4, 6, 8):
        clock[0] = 1000 + elapsed
        assert executor.execute(node, inputs) is inputs


def test_repeated_releases_do_not_reset_other_nodes(timer):
    executor, clock = timer
    first = make_node("first")
    second = make_node("second")

    assert executor.execute(first, []) == []
    clock[0] += 1
    assert executor.execute(second, []) == []

    for elapsed in range(2, 8):
        clock[0] = 1000 + elapsed
        assert len(executor.execute(first, [])) == (elapsed % 2 == 0)
        assert len(executor.execute(second, [])) == (elapsed % 2 == 1)


def test_timer_state_survives_executor_recreation(timer):
    executor, clock = timer
    node = make_node()

    assert executor.execute(node, []) == []
    for elapsed in (2, 4, 6):
        clock[0] = 1000 + elapsed
        executor = LoopTimerNodeExecutor(executor.context)
        assert len(executor.execute(node, [])) == 1
        assert executor.execute(node, []) == []
