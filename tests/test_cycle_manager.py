"""Unit tests for cycle detection and cycle manager entry/exit structure analysis."""

from unittest.mock import MagicMock

from entity.configs.node.node import EdgeLink, Node
from workflow.cycle_manager import CycleDetector, CycleManager


def _create_node(node_id: str) -> Node:
    """Create a minimal valid Node for graph structure analysis."""
    return Node(id=node_id, type="literal", path="node", config=MagicMock())


def test_entry_node_detected_when_predecessor_has_non_trigger_edge_before_trigger_edge():
    """Verify that a non-trigger edge does not mask a subsequent triggering edge from the same predecessor."""
    pred = _create_node("pred")
    node_a = _create_node("node_a")
    node_b = _create_node("node_b")

    # Predecessor has two outgoing edges to node_a:
    # 1. Non-trigger edge (e.g. data passing or conditional branch)
    # 2. Triggering edge
    edge_non_trigger = EdgeLink(target=node_a, trigger=False)
    edge_trigger = EdgeLink(target=node_a, trigger=True)
    pred._outgoing_edges = [edge_non_trigger, edge_trigger]

    # Cycle: node_a <-> node_b
    node_a.predecessors = [pred, node_b]
    node_b.predecessors = [node_a]
    node_a._outgoing_edges = [EdgeLink(target=node_b, trigger=True)]
    node_b._outgoing_edges = [EdgeLink(target=node_a, trigger=True)]

    nodes = {"pred": pred, "node_a": node_a, "node_b": node_b}
    cycles = [{"node_a", "node_b"}]

    manager = CycleManager()
    manager.initialize_cycles(cycles, nodes)

    cycle_info = next(iter(manager.cycles.values()))
    assert "node_a" in cycle_info.entry_nodes
    assert cycle_info.is_entry_node("node_a")
    assert not cycle_info.is_entry_node("node_b")


def test_entry_node_not_added_when_all_edges_from_predecessor_are_non_trigger():
    """Verify that a predecessor with only non-triggering edges does not make a node an entry node."""
    pred = _create_node("pred")
    node_a = _create_node("node_a")
    node_b = _create_node("node_b")

    edge_non_trigger = EdgeLink(target=node_a, trigger=False)
    pred._outgoing_edges = [edge_non_trigger]

    node_a.predecessors = [pred, node_b]
    node_b.predecessors = [node_a]
    node_a._outgoing_edges = [EdgeLink(target=node_b, trigger=True)]
    node_b._outgoing_edges = [EdgeLink(target=node_a, trigger=True)]

    nodes = {"pred": pred, "node_a": node_a, "node_b": node_b}
    cycles = [{"node_a", "node_b"}]

    manager = CycleManager()
    manager.initialize_cycles(cycles, nodes)

    cycle_info = next(iter(manager.cycles.values()))
    assert "node_a" not in cycle_info.entry_nodes
    assert len(cycle_info.entry_nodes) == 0


def test_exit_edges_and_lifecycle():
    """Verify exit edge detection and activate/deactivate lifecycle."""
    pred = _create_node("pred")
    node_a = _create_node("node_a")
    node_b = _create_node("node_b")
    outside = _create_node("outside")

    pred._outgoing_edges = [EdgeLink(target=node_a, trigger=True)]
    node_a.predecessors = [pred, node_b]
    node_b.predecessors = [node_a]
    outside.predecessors = [node_b]

    # node_b has cycle edge back to node_a, plus an exit edge to outside
    node_a._outgoing_edges = [EdgeLink(target=node_b, trigger=True)]
    node_b._outgoing_edges = [
        EdgeLink(target=node_a, trigger=True),
        EdgeLink(target=outside, trigger=True, condition="done"),
    ]

    nodes = {"pred": pred, "node_a": node_a, "node_b": node_b, "outside": outside}
    cycles = [{"node_a", "node_b"}]

    manager = CycleManager()
    manager.initialize_cycles(cycles, nodes)

    cycle_id = next(iter(manager.cycles.keys()))
    cycle_info = manager.cycles[cycle_id]

    assert cycle_info.entry_nodes == {"node_a"}
    assert len(cycle_info.exit_edges) == 1
    assert cycle_info.exit_edges[0]["from"] == "node_b"
    assert cycle_info.exit_edges[0]["to"] == "outside"
    assert cycle_info.exit_edges[0]["condition"] == "done"

    # Lifecycle checks
    assert not cycle_info.is_active
    manager.activate_cycle(cycle_id)
    assert cycle_info.is_active
    assert cycle_id in manager.active_cycles

    cycle_info.increment_iteration()
    assert cycle_info.iteration_count == 1
    assert cycle_info.is_within_iteration_limit()

    manager.deactivate_cycle(cycle_id)
    assert not cycle_info.is_active
    assert cycle_info.iteration_count == 0
    assert cycle_id not in manager.active_cycles


def test_cycle_detector_tarjan():
    """Verify CycleDetector finds cycle using Tarjan's algorithm."""
    pred = _create_node("pred")
    node_a = _create_node("node_a")
    node_b = _create_node("node_b")

    pred._outgoing_edges = [EdgeLink(target=node_a, trigger=True)]
    node_a._outgoing_edges = [EdgeLink(target=node_b, trigger=True)]
    node_b._outgoing_edges = [EdgeLink(target=node_a, trigger=True)]

    nodes = {"pred": pred, "node_a": node_a, "node_b": node_b}

    detector = CycleDetector()
    detected = detector.detect_cycles(nodes)

    assert len(detected) == 1
    assert detected[0] == {"node_a", "node_b"}
