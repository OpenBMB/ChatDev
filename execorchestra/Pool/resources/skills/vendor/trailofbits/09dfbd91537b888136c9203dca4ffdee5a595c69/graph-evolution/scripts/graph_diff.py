# /// script
# requires-python = ">=3.12"
# ///
"""Compute structural diff between two Trailmark graph JSON exports.

Compares nodes, edges, complexity, subgraph membership, and
pre-analysis results to surface security-relevant structural changes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_graph(path: str) -> dict[str, Any]:
    """Load and validate a Trailmark JSON export."""
    data = json.loads(Path(path).read_text())
    for key in ("nodes", "edges"):
        if key not in data:
            print(f"ERROR: Missing '{key}' in {path}", file=sys.stderr)
            sys.exit(1)
    return data


def diff_nodes(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    """Compute added, removed, and modified nodes."""
    before_ids = set(before.keys())
    after_ids = set(after.keys())

    added = _summarize_nodes(after, after_ids - before_ids)
    removed = _summarize_nodes(before, before_ids - after_ids)
    modified = _find_modified(before, after, before_ids & after_ids)

    return {"added": added, "removed": removed, "modified": modified}


def _summarize_nodes(
    nodes: dict[str, Any],
    ids: set[str],
) -> list[dict[str, Any]]:
    """Extract summary dicts for a set of node IDs."""
    result = []
    for nid in sorted(ids):
        node = nodes[nid]
        result.append(
            {
                "id": nid,
                "name": node.get("name", ""),
                "kind": node.get("kind", ""),
                "file": _node_file(node),
                "cyclomatic_complexity": node.get("cyclomatic_complexity"),
            }
        )
    return result


def _node_file(node: dict[str, Any]) -> str:
    """Extract file path from a node's location."""
    loc = node.get("location", {})
    if isinstance(loc, dict):
        return loc.get("file_path", "")
    return ""


def _find_modified(
    before: dict[str, Any],
    after: dict[str, Any],
    shared_ids: set[str],
) -> list[dict[str, Any]]:
    """Find nodes present in both with changed properties."""
    modified = []
    for nid in sorted(shared_ids):
        b, a = before[nid], after[nid]
        changes = _compare_node_properties(b, a)
        if changes:
            modified.append({"id": nid, "changes": changes})
    return modified


def _compare_node_properties(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    """Compare security-relevant properties of two node versions."""
    changes: dict[str, Any] = {}
    cc_b = before.get("cyclomatic_complexity")
    cc_a = after.get("cyclomatic_complexity")
    if cc_b != cc_a:
        changes["cyclomatic_complexity"] = {
            "before": cc_b,
            "after": cc_a,
        }

    params_b = _param_signature(before)
    params_a = _param_signature(after)
    if params_b != params_a:
        changes["parameters"] = {
            "before": params_b,
            "after": params_a,
        }

    ret_b = _return_type_str(before)
    ret_a = _return_type_str(after)
    if ret_b != ret_a:
        changes["return_type"] = {"before": ret_b, "after": ret_a}

    span_b = _line_span(before)
    span_a = _line_span(after)
    if span_b != span_a:
        changes["line_span"] = {"before": span_b, "after": span_a}

    return changes


def _param_signature(node: dict[str, Any]) -> list[str]:
    """Extract parameter names from a node."""
    params = node.get("parameters", ())
    if isinstance(params, (list, tuple)):
        return [p.get("name", "") if isinstance(p, dict) else str(p) for p in params]
    return []


def _return_type_str(node: dict[str, Any]) -> str | None:
    """Extract return type string from a node."""
    rt = node.get("return_type")
    if isinstance(rt, dict):
        return rt.get("name")
    return rt


def _line_span(node: dict[str, Any]) -> int:
    """Compute line count from a node's location."""
    loc = node.get("location", {})
    if isinstance(loc, dict):
        start = loc.get("start_line", 0)
        end = loc.get("end_line", 0)
        return max(0, end - start + 1)
    return 0


def diff_edges(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute added and removed edges."""
    before_set = {_edge_key(e) for e in before}
    after_set = {_edge_key(e) for e in after}

    added = sorted(after_set - before_set)
    removed = sorted(before_set - after_set)

    return {
        "added": [_parse_edge_key(k) for k in added],
        "removed": [_parse_edge_key(k) for k in removed],
    }


def _edge_key(edge: dict[str, Any]) -> str:
    """Create a hashable key for an edge."""
    src = edge.get("source", edge.get("source_id", ""))
    tgt = edge.get("target", edge.get("target_id", ""))
    kind = edge.get("kind", "")
    return f"{src}|{tgt}|{kind}"


def _parse_edge_key(key: str) -> dict[str, str]:
    """Convert an edge key back to a dict."""
    source, target, kind = key.split("|", 2)
    return {"source": source, "target": target, "kind": kind}


def diff_subgraphs(
    before: dict[str, list[str]],
    after: dict[str, list[str]],
) -> dict[str, Any]:
    """Compute per-subgraph membership changes."""
    all_names = sorted(set(before.keys()) | set(after.keys()))
    changes: dict[str, Any] = {}

    for name in all_names:
        b_ids = set(before.get(name, []))
        a_ids = set(after.get(name, []))
        added = sorted(a_ids - b_ids)
        removed = sorted(b_ids - a_ids)
        if added or removed:
            changes[name] = {"added": added, "removed": removed}

    return changes


def compute_summary_delta(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    """Compute deltas for summary statistics."""
    b_sum = before.get("summary", {})
    a_sum = after.get("summary", {})
    delta: dict[str, Any] = {}

    for key in ("total_nodes", "functions", "classes", "call_edges", "entrypoints"):
        b_val = b_sum.get(key, 0)
        a_val = a_sum.get(key, 0)
        if b_val != a_val:
            delta[key] = {
                "before": b_val,
                "after": a_val,
                "delta": a_val - b_val,
            }
    return delta


def compute_diff(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    """Compute the full structural diff between two graphs."""
    return {
        "summary_delta": compute_summary_delta(before, after),
        "nodes": diff_nodes(
            before.get("nodes", {}),
            after.get("nodes", {}),
        ),
        "edges": diff_edges(
            before.get("edges", []),
            after.get("edges", []),
        ),
        "subgraphs": diff_subgraphs(
            before.get("subgraphs", {}),
            after.get("subgraphs", {}),
        ),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Structural diff between Trailmark graphs",
    )
    parser.add_argument(
        "--before",
        required=True,
        help="Path to the 'before' graph JSON export",
    )
    parser.add_argument(
        "--after",
        required=True,
        help="Path to the 'after' graph JSON export",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON output indentation (default: 2)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Entry point: load graphs, compute diff, print JSON."""
    args = parse_args(argv)
    before = load_graph(args.before)
    after = load_graph(args.after)
    diff = compute_diff(before, after)
    print(json.dumps(diff, indent=args.indent))


if __name__ == "__main__":
    main()
