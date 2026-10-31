"""End-node references must be validated for file-backed subgraphs too."""

from pathlib import Path
from typing import Any

import pytest
import yaml

from entity.configs import ConfigError, GraphDefinition
from runtime import sdk


def _graph(end: Any = None) -> dict[str, Any]:
    return {
        "id": "child",
        "nodes": [
            {"id": "first", "type": "literal", "config": {"content": "first result"}},
            {"id": "second", "type": "literal", "config": {"content": "second result"}},
        ],
        "edges": [],
        "start": ["first", "second"],
        "end": end,
    }


def _file_parent(path: Path) -> dict[str, Any]:
    return {
        "id": "parent",
        "nodes": [
            {
                "id": "child",
                "type": "subgraph",
                "config": {"type": "file", "config": {"path": str(path)}},
            }
        ],
        "edges": [],
        "start": ["child"],
        "end": ["child"],
    }


@pytest.mark.parametrize("end", ["missing", ["missing"], ["second", "missing"]])
def test_graph_definition_rejects_unknown_end_reference(end: Any) -> None:
    with pytest.raises(ConfigError, match="end node 'missing' not defined") as error:
        GraphDefinition.from_dict(_graph(end), path="root.graph")
    assert error.value.path == "root.graph.end"


@pytest.mark.parametrize("end", ["missing", ["second", "missing"]])
def test_majority_voting_keeps_ignoring_end_references(end: Any) -> None:
    graph = _graph(end)
    graph["is_majority_voting"] = True
    definition = GraphDefinition.from_dict(graph, path="root.graph")
    assert definition.is_majority_voting
    assert definition.end_nodes == ([end] if isinstance(end, str) else end)


@pytest.mark.parametrize("wrapped", [False, True])
@pytest.mark.parametrize("depth", [1, 2])
@pytest.mark.parametrize("end", ["missing", ["second", "missing"]])
def test_sdk_rejects_unknown_file_subgraph_end_before_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    wrapped: bool,
    depth: int,
    end: Any,
) -> None:
    monkeypatch.chdir(tmp_path)
    child = tmp_path / "child.yaml"
    graph = _graph(end)
    child.write_text(yaml.safe_dump({"graph": graph} if wrapped else graph))
    for level in range(depth):
        parent = tmp_path / f"parent_{level}.yaml"
        parent.write_text(yaml.safe_dump({"graph": _file_parent(child)}))
        child = parent

    with pytest.raises(ConfigError, match="end node 'missing' not defined"):
        sdk.run_workflow(child, task_prompt="test")
    assert not list(tmp_path.rglob("execution_logs.json"))


@pytest.mark.parametrize(
    ("end", "expected"),
    [
        ("second", "second result"),
        (["second", "first"], "second result"),
        (["first", "second"], "first result"),
        (["second", "second"], "second result"),
        (None, "first result"),
        ([], "first result"),
    ],
)
def test_file_subgraph_preserves_end_priority_and_implicit_sink_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    end: Any,
    expected: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    child = tmp_path / "child.yaml"
    child.write_text(yaml.safe_dump({"graph": _graph(end)}))
    parent = tmp_path / "parent.yaml"
    parent.write_text(yaml.safe_dump({"graph": _file_parent(child)}))
    result = sdk.run_workflow(parent, task_prompt="test")
    assert result.final_message is not None
    assert result.final_message.text_content() == expected
