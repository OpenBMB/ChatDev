"""Tools and edge processor behind yaml_instance/workflow_designer.yaml (no model calls)."""

from pathlib import Path

import runtime.sdk  # noqa: F401  # loads runtime before check.check (import order the server uses)
from check.check import load_config
from functions.edge_processor.workflow_design import extract_validated_workflow
from functions.function_calling.workflow_design import (
    read_example_workflow,
    read_node_doc,
    validate_workflow_yaml,
)

DESIGNER = Path(__file__).resolve().parents[1] / "yaml_instance" / "workflow_designer.yaml"


def test_designer_workflow_loads_and_passes_its_own_validator() -> None:
    load_config(DESIGNER, vars_override={"BASE_URL": "http://x", "API_KEY": "x"})
    assert validate_workflow_yaml(DESIGNER.read_text()) == "OK"


def test_validator_rejects_embedded_credentials() -> None:
    leaked = (
        DESIGNER.read_text()
        .replace("${API_KEY}", "sk-" + "a" * 24)
        .replace("${BASE_URL}", "https://api.openai.com/v1")
    )
    verdict = validate_workflow_yaml(leaked)
    assert "looks like an API key" in verdict
    assert "config.base_url must be exactly ${BASE_URL}" in verdict
    assert "sk-" not in verdict  # the secret is never echoed back to the model


def test_validator_reports_schema_and_syntax_errors() -> None:
    assert validate_workflow_yaml("graph: {nodes: 3}") != "OK"
    assert validate_workflow_yaml("a: [").startswith("YAML syntax error")


def test_readers_only_serve_listed_files() -> None:
    assert read_example_workflow("../pyproject.toml").startswith("Available examples:")
    assert "demo_loop_counter.yaml" in read_example_workflow("")
    assert read_node_doc("../../README").startswith("Unknown node type")
    assert read_node_doc("agent").startswith("#")


def test_processor_passes_valid_yaml_and_flags_invalid() -> None:
    good = DESIGNER.read_text()  # its role prompt contains ``` fences of its own
    assert extract_validated_workflow(f"Here it is:\n```yaml\n{good}```\nDone.", {}) == good
    flagged = extract_validated_workflow("```yaml\ngraph: {nodes: 3}\n```", {})
    assert flagged.startswith("# VALIDATION FAILED")
    assert flagged.rstrip().endswith("graph: {nodes: 3}")
