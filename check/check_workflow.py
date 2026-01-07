import argparse
from typing import Any, Dict, List, Optional, Tuple

import yaml

from check import check_yaml
from utils.io_utils import read_yaml


def _node_ids(graph: Dict[str, Any]) -> List[str]:
    nodes = graph.get("nodes", []) or []
    ids: List[str] = []
    for n in nodes:
        nid = n.get("id")
        if isinstance(nid, str):
            ids.append(nid)
    return ids


def _edge_list(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    edges = graph.get("edges", []) or []
    return [e for e in edges if isinstance(e, dict) and "from" in e and "to" in e]


def _analyze_graph(graph: Dict[str, Any], base_path: str, errors: List[str]) -> None:
    # Majority voting graphs are skipped for start/end structure checks
    is_mv = graph.get("is_majority_voting", False)
    if is_mv:
        return

    nodes = _node_ids(graph)
    node_set = set(nodes)

    # Validate provided start/end (if any) reference existing nodes
    # start = graph.get("start")
    end = graph.get("end")
    # if start is not None and start not in node_set:
        # errors.append(f"{base_path}.start references unknown node id '{start}'")

    # Normalize to list
    if end is not None:
        if isinstance(end, str):
            end_list = [end]
        elif isinstance(end, list):
            end_list = end
        else:
            errors.append(f"{base_path}.end must be a string or list of strings")
            return

        # Check each node ID in the end list
        for end_node_id in end_list:
            if not isinstance(end_node_id, str):
                errors.append(
                    f"{base_path}.end contains non-string element: {end_node_id}"
                )
            elif end_node_id not in node_set:
                errors.append(
                    f"{base_path}.end references unknown node id '{end_node_id}'"
                )

    # Compute in/out degrees within this graph scope
    indeg = {nid: 0 for nid in nodes}
    outdeg = {nid: 0 for nid in nodes}
    for e in _edge_list(graph):
        frm = e.get("from")
        to = e.get("to")
        if frm in outdeg:
            outdeg[frm] += 1
        if to in indeg:
            indeg[to] += 1

    # sources = [nid for nid in nodes if indeg.get(nid, 0) == 0]
    sinks = [nid for nid in nodes if outdeg.get(nid, 0) == 0]

    # # Rule:
    # # - A non-cyclic (sub)graph should have exactly one natural source AND exactly one natural sink.
    # # - Otherwise (e.g., multiple sources/sinks or cycles -> none), require explicit start or end.
    # has_unique_source = len(sources) == 1
    # has_unique_sink = len(sinks) == 1
    # if not (has_unique_source and has_unique_sink):
    #     if start is None and end is None:
    #         errors.append(
    #             f"{base_path}: graph lacks a unique natural start and end; specify 'start' or 'end' explicitly"
    #         )
    if not (len(sinks) == 1):
        if end is None:
            errors.append(
                f"{base_path}: graph lacks a unique natural end; specify 'end' explicitly"
            )

    # Recurse into subgraphs
    for i, n in enumerate(graph.get("nodes", []) or []):
        if isinstance(n, dict) and n.get("type") == "subgraph":
            sub = n.get("config") or {}
            if not isinstance(sub, dict):
                errors.append(f"{base_path}.nodes[{i}].config must be object for subgraph nodes")
                continue
            sg_type = sub.get("type")
            if sg_type == "config":
                config_block = sub.get("config")
                if not isinstance(config_block, dict):
                    errors.append(
                        f"{base_path}.nodes[{i}].config.config must be object when type=config"
                    )
                    continue
                _analyze_graph(config_block, f"{base_path}.nodes[{i}].config.config", errors)
            elif sg_type == "file":
                file_block = sub.get("config")
                if not (isinstance(file_block, dict) and isinstance(file_block.get("path"), str)):
                    errors.append(
                        f"{base_path}.nodes[{i}].config.config.path must be string when type=file"
                    )
            else:
                errors.append(
                    f"{base_path}.nodes[{i}].config.type must be 'config' or 'file'"
                )


def check_workflow_structure(data: Any) -> List[str]:
    errors: List[str] = []
    if not isinstance(data, dict) or "graph" not in data:
        return ["<root>.graph is required"]
    graph = data["graph"]
    if not isinstance(graph, dict):
        return ["<root>.graph must be object"]

    _analyze_graph(graph, "graph", errors)
    return errors


def main():
    parser = argparse.ArgumentParser(
        description="Check workflow structure: unique natural start/end or explicit start/end per (sub)graph")
    parser.add_argument("path", nargs="?", default="design_0.4.0.yaml", help="Path to YAML file")
    parser.add_argument("--no-schema", action="store_true", help="Skip schema validation (0.4.0)")
    parser.add_argument("--fn-module", dest="fn_module", default=None,
                        help="Module name or .py path where edge functions are defined (for schema validation)")
    args = parser.parse_args()

    data = read_yaml(args.path)

    if not args.no_schema:
        schema_errors = check_yaml.validate_design(data, set_defaults=True, fn_module_ref=args.fn_module)
        if schema_errors:
            print("Invalid schema:")
            for e in schema_errors:
                print(f"- {e}")
            raise SystemExit(1)

    logic_errors = check_workflow_structure(data)
    if logic_errors:
        print("Workflow issues:")
        for e in logic_errors:
            print(f"- {e}")
        raise SystemExit(2)
    else:
        print("Workflow OK.")


if __name__ == "__main__":
    main()
