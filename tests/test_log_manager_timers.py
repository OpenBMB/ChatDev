import pytest

from utils.log_manager import LogManager
from utils.logger import WorkflowLogger


@pytest.fixture
def manager():
    return LogManager(WorkflowLogger(use_structured_logging=False, log_to_console=False))


@pytest.mark.parametrize(
    ("method", "args", "key"),
    [
        ("operation_timer", ("load",), "load"),
        ("node_timer", ("node",), "node"),
        ("model_timer", ("node",), "model_node"),
        ("agent_timer", ("node",), "agent_node"),
        ("human_timer", ("node",), "human_node"),
        ("tool_timer", ("node", "search"), "tool_node_search"),
        ("thinking_timer", ("node", "before"), "thinking_node_before"),
        ("memory_timer", ("node", "recall", "before"), "memory_node_recall_before"),
    ],
)
def test_timer_can_be_the_first_operation(manager, method, args, key):
    with getattr(manager, method)(*args):
        pass
    assert manager.logger.get_timer(key) >= 0


def test_operation_timer_preserves_the_original_exception(manager):
    failure = RuntimeError("the operation failed")
    with pytest.raises(RuntimeError) as caught:
        with manager.operation_timer("failed-operation"):
            raise failure
    assert caught.value is failure
    assert manager.logger.get_timer("failed-operation") >= 0
