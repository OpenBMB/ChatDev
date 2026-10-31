"""Cancellation must cross subgraph execution boundaries."""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
import yaml

from entity.config_loader import load_design_from_mapping
from entity.graph_config import GraphConfig
from runtime.bootstrap.schema import ensure_schema_registry_populated
from runtime.node.executor.literal_executor import LiteralNodeExecutor
from utils.exceptions import WorkflowCancelledError
from workflow.graph import GraphExecutor
from workflow.graph_context import GraphContext


def _executor(tmp_path, source, depth, cancel_event):
    ensure_schema_registry_populated()
    graph = {
        "id": "inner",
        "nodes": [
            {"id": name, "type": "literal", "config": {"content": name}}
            for name in ("first", "second")
        ],
        "edges": [{"from": "first", "to": "second"}],
        "start": "first",
        "end": "second",
    }
    for level in range(depth):
        if source == "file":
            path = tmp_path / f"child-{level}.yaml"
            path.write_text(yaml.safe_dump({"graph": graph}), encoding="utf-8")
            config = {"type": "file", "config": {"path": str(path)}}
        else:
            config = {"type": "config", "config": graph}
        graph = {
            "id": f"outer-{level}",
            "nodes": [{"id": f"child-{level}", "type": "subgraph", "config": config}],
            "edges": [],
            "start": f"child-{level}",
            "end": f"child-{level}",
        }
    design = load_design_from_mapping({"graph": graph})
    config = GraphConfig.from_definition(design.graph, name="cancel-test", output_root=tmp_path)
    return GraphExecutor(GraphContext(config=config), cancel_event=cancel_event)


@pytest.mark.parametrize("source", ["config", "file"])
@pytest.mark.parametrize("depth", [1, 2])
def test_parent_cancellation_stops_next_subgraph_node(tmp_path, monkeypatch, source, depth):
    cancel_event = threading.Event()
    first_finished = threading.Event()
    release_first = threading.Event()
    executed = []
    original_execute = LiteralNodeExecutor.execute

    def observed_execute(self, node, inputs):
        result = original_execute(self, node, inputs)
        executed.append(node.id)
        if node.id == "first":
            first_finished.set()
            assert release_first.wait(10), "test did not release the first node"
        return result

    monkeypatch.setattr(LiteralNodeExecutor, "execute", observed_execute)
    executor = _executor(tmp_path, source, depth, cancel_event)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(executor.run, "task")
        try:
            assert first_finished.wait(10), "first subgraph node did not execute"
            executor.request_cancel()
        finally:
            release_first.set()
        with pytest.raises(WorkflowCancelledError):
            future.result(timeout=10)
    assert executed == ["first"]


@pytest.mark.parametrize("source", ["config", "file"])
@pytest.mark.parametrize("depth", [1, 2])
def test_uncancelled_subgraph_retains_output(tmp_path, source, depth):
    executor = _executor(tmp_path, source, depth, threading.Event())
    executor.run("task")
    assert executor.get_final_output_message().content == "second"
