"""Regression tests for reusable variable mappings."""

from copy import deepcopy

import pytest

from entity.configs.base import ConfigError
from utils.vars_resolver import resolve_mapping_with_vars


@pytest.mark.parametrize("template", [{"message": "${VALUE}"}, ["${VALUE}"]])
def test_nested_vars_can_be_reused_with_different_environments(template):
    variables = {"shared": template}
    original = deepcopy(variables)

    for value in ("first", "second"):
        data = {"output": "${shared}"}
        result = resolve_mapping_with_vars(
            data, env_lookup={"VALUE": value}, vars_map=variables
        )
        expected = {"message": value} if isinstance(template, dict) else [value]
        assert result is data
        assert data["output"] == expected
        assert variables == original


def test_resolved_output_does_not_alias_input_vars():
    variables = {"shared": {"items": ["original"]}}
    data = {"output": "${shared}"}
    resolve_mapping_with_vars(data, env_lookup={}, vars_map=variables)

    data["output"]["items"].append("changed")
    assert variables == {"shared": {"items": ["original"]}}


def test_failed_resolution_does_not_partially_mutate_vars():
    variables = {"shared": ["${KNOWN}", "${MISSING}"]}
    original = deepcopy(variables)

    with pytest.raises(ConfigError, match="Unresolved placeholder"):
        resolve_mapping_with_vars(
            {"output": "${shared}"}, env_lookup={"KNOWN": "value"}, vars_map=variables
        )

    assert variables == original


def test_scalar_references_and_root_precedence_are_preserved():
    variables = {"value": 42, "alias": "${value}"}
    data = {"number": "${alias}", "text": "answer=${value}"}
    resolve_mapping_with_vars(
        data, env_lookup={"value": "environment"}, vars_map=variables
    )
    assert data == {"number": 42, "text": "answer=42"}
    assert variables == {"value": 42, "alias": "${value}"}


def test_cyclic_variables_still_raise_config_error():
    with pytest.raises(ConfigError, match="placeholder cycle"):
        resolve_mapping_with_vars(
            {"output": "${first}"},
            env_lookup={},
            vars_map={"first": "${second}", "second": "${first}"},
        )


def test_resolving_subgraph_vars_does_not_pollute_cached_yaml(tmp_path):
    from workflow.subgraph_loader import load_subgraph_config

    path = tmp_path / "child.yaml"
    path.write_text(
        "graph:\n  payload: ${shared}\nvars:\n  shared:\n    message: ${VALUE}\n",
        encoding="utf-8",
    )

    for value in ("first", "second"):
        graph, variables, _ = load_subgraph_config(str(path))
        resolve_mapping_with_vars(
            graph, env_lookup={"VALUE": value}, vars_map=variables
        )
        assert graph["payload"] == {"message": value}

    _, cached_variables, _ = load_subgraph_config(str(path))
    assert cached_variables == {"shared": {"message": "${VALUE}"}}


def test_nested_aliases_resolve_without_mutating_vars():
    shared = {"items": ["${VALUE}"]}
    variables = {"first": shared, "second": shared, "alias": "${first}"}
    data = {"one": "${alias}", "two": "${second}"}
    resolve_mapping_with_vars(
        data, env_lookup={"VALUE": "resolved"}, vars_map=variables
    )
    assert data == {"one": {"items": ["resolved"]}, "two": {"items": ["resolved"]}}
    assert data["one"] is data["two"]
    assert shared == {"items": ["${VALUE}"]}


def test_design_resolution_remains_in_place():
    from utils.vars_resolver import resolve_design_placeholders

    data = {"vars": {"shared": {"message": "${VALUE}"}}, "output": "${shared}"}
    returned_vars = resolve_design_placeholders(data, env_lookup={"VALUE": "resolved"})
    assert data == {
        "vars": {"shared": {"message": "resolved"}},
        "output": {"message": "resolved"},
    }
    assert returned_vars == data["vars"]
