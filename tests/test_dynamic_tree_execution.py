"""Tree edges must execute their target even for a single split message."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from entity.configs import Node
from entity.configs.edge.dynamic_edge_config import DynamicEdgeConfig
from entity.messages import Message, MessageRole
from runtime import sdk
from utils.log_manager import LogManager
from utils.logger import WorkflowLogger
from workflow.executor.dynamic_edge_executor import DynamicEdgeExecutor


def _node() -> Node:
    return Node.from_dict(
        {"id": "target", "type": "literal", "config": {"content": "processed result"}},
        path="node",
    )


def _message(text: str) -> Message:
    return Message(role=MessageRole.USER, content=text)


def _config(mode: str = "tree") -> DynamicEdgeConfig:
    config = DynamicEdgeConfig.from_dict(
        {"type": mode, "config": {"group_size": 2, "max_parallel": 2}},
        path="edge.dynamic",
    )
    assert config is not None
    return config


def _executor(
    execute: Callable[[Node, list[Message]], list[Message]],
) -> DynamicEdgeExecutor:
    logger = WorkflowLogger(use_structured_logging=False, log_to_console=False)
    return DynamicEdgeExecutor(LogManager(logger), execute)


@pytest.mark.parametrize(
    ("content", "split"),
    [
        ("raw document", {"type": "message"}),
        ("raw document", {"type": "regex", "config": {"pattern": ".+"}}),
        (
            '{"items": ["raw document"]}',
            {"type": "json_path", "config": {"json_path": "items"}},
        ),
    ],
    ids=["message", "regex", "json_path"],
)
def test_singleton_tree_executes_literal_target_through_sdk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    content: str,
    split: dict[str, Any],
) -> None:
    monkeypatch.chdir(tmp_path)
    workflow = tmp_path / "singleton_tree.yaml"
    workflow.write_text(
        yaml.safe_dump(
            {
                "graph": {
                    "id": "singleton_tree",
                    "nodes": [
                        {
                            "id": "source",
                            "type": "literal",
                            "config": {"content": content},
                        },
                        {
                            "id": "target",
                            "type": "literal",
                            "config": {"content": "processed result"},
                        },
                    ],
                    "edges": [
                        {
                            "from": "source",
                            "to": "target",
                            "dynamic": {"type": "tree", "split": split},
                        }
                    ],
                    "start": ["source"],
                    "end": ["target"],
                }
            }
        ),
        encoding="utf-8",
    )

    result = sdk.run_workflow(workflow, task_prompt="test")

    assert result.final_message is not None
    assert result.final_message.text_content() == "processed result"
    assert result.final_message.metadata["source"] == "target"


@pytest.mark.parametrize("entrypoint", ["execute", "execute_from_inputs"])
def test_singleton_tree_includes_static_inputs_and_tags_first_layer(
    entrypoint: str,
) -> None:
    dynamic_input = _message("document")
    static_input = _message("instructions")
    calls: list[list[Message]] = []

    def execute(node: Node, inputs: list[Message]) -> list[Message]:
        calls.append(inputs)
        return [_message("processed result")]

    executor = _executor(execute)
    node = _node()
    if entrypoint == "execute":
        outputs = executor.execute(node, dynamic_input, _config(), [static_input])
    else:
        outputs = executor.execute_from_inputs(
            node, [dynamic_input], _config(), [static_input]
        )

    assert len(calls) == 1
    assert [msg.text_content() for msg in calls[0]] == ["instructions", "document"]
    assert all(msg.metadata["dynamic_edge_tree_layer"] == 1 for msg in calls[0])
    assert all(msg.metadata["dynamic_edge_tree_group"] == 0 for msg in calls[0])
    assert outputs[0].text_content() == "processed result"
    assert outputs[0].metadata["dynamic_edge_instance_id"] == "target#1-0"
    assert dynamic_input.metadata == static_input.metadata == {}


@pytest.mark.parametrize("mode", ["tree", "map"])
def test_empty_inputs_do_not_execute_target(mode: str) -> None:
    def execute(node: Node, inputs: list[Message]) -> list[Message]:
        raise AssertionError("An empty split must not execute the target")

    assert _executor(execute).execute_from_inputs(_node(), [], _config(mode)) == []


def test_singleton_tree_can_suppress_output() -> None:
    calls: list[list[Message]] = []

    def execute(node: Node, inputs: list[Message]) -> list[Message]:
        calls.append(inputs)
        return []

    outputs = _executor(execute).execute_from_inputs(
        _node(),
        [_message("document")],
        _config(),
    )

    assert outputs == []
    assert len(calls) == 1


def test_multilayer_tree_stops_after_reduction_and_only_replicates_static_inputs_once() -> (
    None
):
    calls: list[list[Message]] = []

    def execute(node: Node, inputs: list[Message]) -> list[Message]:
        calls.append(inputs)
        return [_message("|".join(msg.text_content() for msg in inputs))]

    outputs = _executor(execute).execute_from_inputs(
        _node(),
        [_message(str(index)) for index in range(5)],
        _config(),
        [_message("instructions")],
    )

    assert len(calls) == 6  # Three groups, then two, then one final reduction.
    for inputs in calls:
        layer = inputs[0].metadata["dynamic_edge_tree_layer"]
        assert (inputs[0].text_content() == "instructions") == (layer == 1)
    assert [msg.text_content() for msg in outputs] == [
        "instructions|0|1|instructions|2|3|instructions|4"
    ]
    assert outputs[0].metadata["dynamic_edge_tree_layer"] == 3
