"""Tests for the loop_timer node's ``reset_on_emit`` behaviour.

The user guide documents both modes explicitly:

* ``reset_on_emit: true``  -> the timer restarts after every release, so the node
  emits once per ``max_duration`` window.
* ``reset_on_emit: false`` -> the timer keeps running, so every later trigger
  emits as well.

Only the second mode used to work: the ``emitted`` flag was consulted before
restarting the countdown, so after the *second* release the window was never
restarted again and the node emitted on every single call.
"""

from entity.configs.node.loop_timer import LoopTimerConfig
from entity.configs.node.node import Node
from entity.enums import LogLevel
from entity.messages import Message, MessageRole
from runtime.node.executor import loop_timer_executor as loop_timer_module
from runtime.node.executor.base import ExecutionContext
from runtime.node.executor.loop_timer_executor import LoopTimerNodeExecutor
from utils.log_manager import LogManager
from utils.logger import WorkflowLogger


class _FakeClock:
    """Controllable replacement for ``time.time``."""

    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def _build_executor(config_data, monkeypatch):
    clock = _FakeClock()
    monkeypatch.setattr(loop_timer_module.time, "time", clock)

    config = LoopTimerConfig.from_dict(config_data, path="graph.nodes[0].config")
    node = Node(
        id="Time Guard",
        type="loop_timer",
        config=config,
        path="graph.nodes[0]",
    )
    workflow_logger = WorkflowLogger(
        "loop-timer-test",
        LogLevel.INFO,
        use_structured_logging=False,
        log_to_console=False,
    )
    context = ExecutionContext(
        tool_manager=None,
        function_manager=None,
        log_manager=LogManager(workflow_logger),
    )
    return LoopTimerNodeExecutor(context), node, clock


def _emission_times(executor, node, clock, timestamps):
    message = Message(role=MessageRole.USER, content="keep looping")
    emitted = []
    for timestamp in timestamps:
        clock.now = timestamp
        if executor.execute(node, [message]):
            emitted.append(timestamp)
    return emitted


class TestLoopTimerResetOnEmit:
    def test_reset_on_emit_releases_once_per_window(self, monkeypatch):
        executor, node, clock = _build_executor(
            {"max_duration": 10, "duration_unit": "seconds", "reset_on_emit": True},
            monkeypatch,
        )

        emitted = _emission_times(
            executor,
            node,
            clock,
            [0.0, 9.9, 10.0, 15.0, 19.9, 20.0, 21.0, 25.0, 30.0],
        )

        assert emitted == [10.0, 20.0, 30.0]

    def test_reset_on_emit_disabled_keeps_releasing(self, monkeypatch):
        executor, node, clock = _build_executor(
            {"max_duration": 10, "duration_unit": "seconds", "reset_on_emit": False},
            monkeypatch,
        )

        emitted = _emission_times(
            executor,
            node,
            clock,
            [0.0, 5.0, 10.0, 15.0, 20.0],
        )

        assert emitted == [10.0, 15.0, 20.0]

    def test_reset_on_emit_emits_configured_message(self, monkeypatch):
        executor, node, clock = _build_executor(
            {
                "max_duration": 2,
                "duration_unit": "seconds",
                "reset_on_emit": True,
                "message": "time is up",
            },
            monkeypatch,
        )

        clock.now = 0.0
        assert executor.execute(node, [Message(role=MessageRole.USER, content="go")]) == []

        clock.now = 2.0
        messages = executor.execute(node, [Message(role=MessageRole.USER, content="go")])

        assert len(messages) == 1
        assert messages[0].text_content() == "time is up"
        assert messages[0].metadata["loop_timer"]["elapsed_time"] == 2.0
