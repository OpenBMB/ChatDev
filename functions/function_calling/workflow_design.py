"""Tools for ``yaml_instance/workflow_designer.yaml``: read DevAll's authoring docs and examples, validate generated YAML."""

import re
from pathlib import Path
from typing import Annotated

import yaml

from utils.function_catalog import ParamMeta

_REPO = Path(__file__).resolve().parents[2]
_EXAMPLES_DIR = _REPO / "yaml_instance"
_NODE_DOCS_DIR = _REPO / "docs" / "user_guide" / "en" / "nodes"
_YAML_FENCE = re.compile(r"^\s*```(?:yaml|yml)?\s*\n(.*?)\n?```\s*$", re.DOTALL)
_SECRET = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}")
# Generated workflows must stay portable and must never embed the server's real credentials.
_AGENT_PLACEHOLDERS = {"base_url": "${BASE_URL}", "api_key": "${API_KEY}", "name": "${MODEL_NAME}"}


def _agent_nodes(data: object) -> list[dict]:
    """Every ``type: agent`` node mapping, including those in inline subgraphs."""
    if isinstance(data, list):
        return [node for item in data for node in _agent_nodes(item)]
    if not isinstance(data, dict):
        return []
    found = [data] if data.get("type") == "agent" else []
    return found + [node for value in data.values() for node in _agent_nodes(value)]


def get_workflow_authoring_guide() -> str:
    """Return the DevAll workflow authoring guide plus the annotated design template (yaml_template/design.yaml)."""
    guide = (_REPO / "docs" / "user_guide" / "en" / "workflow_authoring.md").read_text(encoding="utf-8")
    template = (_REPO / "yaml_template" / "design.yaml").read_text(encoding="utf-8")
    return f"{guide}\n\n# Annotated design template\n```yaml\n{template}\n```"


def read_node_doc(
    node_type: Annotated[str, ParamMeta(description="Node type, e.g. agent, human, loop_counter")],
) -> str:
    """Return the detailed documentation for one node type, or the list of documented node types."""
    docs = {path.stem: path for path in _NODE_DOCS_DIR.glob("*.md")}
    if node_type not in docs:
        return "Unknown node type. Documented node types: " + ", ".join(sorted(docs))
    return docs[node_type].read_text(encoding="utf-8")


def read_example_workflow(
    name: Annotated[str, ParamMeta(description="Example path relative to yaml_instance/, e.g. demo_loop_counter.yaml")] = "",
) -> str:
    """Return a bundled example workflow YAML, or the list of available examples when ``name`` is empty or unknown."""
    # Only names from this listing are readable, so no path outside yaml_instance/ can be requested.
    examples = {path.relative_to(_EXAMPLES_DIR).as_posix(): path for path in _EXAMPLES_DIR.rglob("*.yaml")}
    if name not in examples:
        return "Available examples:\n" + "\n".join(sorted(examples))
    return examples[name].read_text(encoding="utf-8")


def validate_workflow_yaml(
    yaml_text: Annotated[str, ParamMeta(description="The complete workflow YAML document")],
) -> str:
    """Validate a workflow YAML with the same check the save route uses. Returns ``OK`` or the list of errors to fix."""
    from check.check import check_config  # deferred: function modules load while the server is importing

    fenced = _YAML_FENCE.match(yaml_text)
    if fenced:
        yaml_text = fenced.group(1)
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        return f"YAML syntax error: {exc}"
    errors = check_config(data)
    if errors:
        return errors
    problems = []
    if _SECRET.search(yaml_text):
        problems.append("- the YAML contains what looks like an API key; remove it")
    for node in _agent_nodes(data):
        config = node.get("config") if isinstance(node.get("config"), dict) else {}
        for field, placeholder in _AGENT_PLACEHOLDERS.items():
            if config.get(field) != placeholder:
                problems.append(f"- agent node '{node.get('id')}': config.{field} must be exactly {placeholder}")
    return "\n".join(problems) or "OK"
