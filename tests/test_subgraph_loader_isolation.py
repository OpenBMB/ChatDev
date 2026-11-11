"""Tests for subgraph configuration caching and variable isolation."""

import yaml

from workflow.subgraph_loader import load_subgraph_config


def test_subgraph_loader_isolates_nested_vars_from_caller_mutation(tmp_path):
    """Mutating returned vars must not pollute _SUBGRAPH_CACHE or subsequent loads."""
    subgraph_content = {
        "graph": {
            "id": "child",
            "nodes": [
                {"id": "n1", "type": "literal", "config": {"content": "hello"}},
            ],
            "start": "n1",
            "end": "n1",
        },
        "vars": {
            "model_config": {
                "name": "gpt-4o",
                "temperature": 0.7,
                "tags": ["prod", "v1"],
            },
            "scalar_var": 42,
        },
    }

    subgraph_file = tmp_path / "child_subgraph.yaml"
    subgraph_file.write_text(yaml.safe_dump(subgraph_content), encoding="utf-8")

    # First load
    _graph1, vars1, _path1 = load_subgraph_config(str(subgraph_file))
    assert vars1["model_config"]["name"] == "gpt-4o"
    assert vars1["model_config"]["tags"] == ["prod", "v1"]
    assert vars1["scalar_var"] == 42

    # Mutate the returned vars dict deeply
    vars1["model_config"]["name"] = "mutated-model"
    vars1["model_config"]["tags"].append("mutated-tag")
    vars1["model_config"]["new_field"] = "injected"
    vars1["scalar_var"] = 999

    # Second load from the same file (served from _SUBGRAPH_CACHE)
    _graph2, vars2, _path2 = load_subgraph_config(str(subgraph_file))
    assert vars2["model_config"]["name"] == "gpt-4o"
    assert vars2["model_config"]["tags"] == ["prod", "v1"]
    assert "new_field" not in vars2["model_config"]
    assert vars2["scalar_var"] == 42

    # Verify objects are distinct instances
    assert vars1 is not vars2
    assert vars1["model_config"] is not vars2["model_config"]
    assert vars1["model_config"]["tags"] is not vars2["model_config"]["tags"]


def test_subgraph_loader_isolates_nested_graph_from_caller_mutation(tmp_path):
    """Mutating returned graph_dict must not pollute _SUBGRAPH_CACHE."""
    subgraph_content = {
        "graph": {
            "id": "child",
            "nodes": [
                {"id": "n1", "type": "literal", "config": {"content": "hello"}},
            ],
            "start": "n1",
            "end": "n1",
        },
        "vars": {"test": "val"},
    }

    subgraph_file = tmp_path / "child_subgraph_2.yaml"
    subgraph_file.write_text(yaml.safe_dump(subgraph_content), encoding="utf-8")

    graph1, _vars1, _ = load_subgraph_config(str(subgraph_file))
    graph1["nodes"][0]["config"]["content"] = "mutated-content"
    graph1["nodes"].append({"id": "injected", "type": "literal"})

    graph2, _vars2, _ = load_subgraph_config(str(subgraph_file))
    assert len(graph2["nodes"]) == 1
    assert graph2["nodes"][0]["config"]["content"] == "hello"
    assert graph1 is not graph2
    assert graph1["nodes"] is not graph2["nodes"]
