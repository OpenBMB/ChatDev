"""Preserve user node identifiers when scheduling graphs with cycles."""

import pytest

from entity.graph_config import GraphConfig
from runtime.bootstrap.schema import ensure_schema_registry_populated
from workflow.graph import GraphExecutor
from workflow.graph_context import GraphContext
from workflow.graph_manager import GraphManager
from workflow.topology_builder import GraphTopologyBuilder


def _graph(tmp_path, start_id, end_id, *, with_cycle=True):
    ensure_schema_registry_populated()
    edges = [{"from": start_id, "to": "loop"}, {"from": "loop", "to": end_id}]
    if with_cycle:
        edges.append(
            {
                "from": "loop",
                "to": "loop",
                "condition": {"type": "keyword", "config": {"any": ["repeat"]}},
            }
        )
    config = GraphConfig.from_dict(
        {
            "id": "topology_test",
            "start": [start_id],
            "end": [end_id],
            "nodes": [
                {"id": node_id, "type": "literal", "config": {"content": node_id}}
                for node_id in (start_id, "loop", end_id)
            ],
            "edges": edges,
        },
        name="topology_test",
        output_root=tmp_path,
    )
    return GraphContext(config)


@pytest.mark.parametrize(
    ("start_id", "end_id"),
    [
        ("node_start", "node_end"),
        ("start_node_input", "end_node_output"),
        ("node_node_start", "node_node_end"),
        ("node_", "end"),
        ("start", "end"),
        ("super_cycle_0", "super_cycle_1"),
    ],
)
def test_cycle_execution_order_preserves_node_ids(tmp_path, start_id, end_id):
    graph = _graph(tmp_path, start_id, end_id)
    GraphManager(graph).build_graph_structure()

    assert graph.has_cycles
    first, cycle, last = graph.cycle_execution_order
    assert first == [{"type": "node", "node_id": start_id}]
    assert cycle[0]["type"] == "cycle"
    assert cycle[0]["nodes"] == ["loop"]
    assert last == [{"type": "node", "node_id": end_id}]


def test_dag_execution_order_preserves_node_ids(tmp_path):
    graph = _graph(tmp_path, "node_start", "node_end", with_cycle=False)
    GraphManager(graph).build_graph_structure()

    assert not graph.has_cycles
    assert GraphTopologyBuilder.build_execution_order(graph.nodes, graph.edges) == [
        [{"type": "node", "node_id": "node_start"}],
        [{"type": "node", "node_id": "loop"}],
        [{"type": "node", "node_id": "node_end"}],
    ]


def test_cyclic_workflow_executes_nodes_with_node_prefix(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    graph = _graph(tmp_path, "node_start", "node_end")

    executor = GraphExecutor.execute_graph(graph, "Run the literal workflow")

    for node_id in ("node_start", "loop", "node_end"):
        assert [message.content for message in graph.nodes[node_id].output] == [node_id]
    final_message = executor.get_final_output_message()
    assert final_message is not None
    assert final_message.content == "node_end"
