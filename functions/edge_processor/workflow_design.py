"""Edge processor for ``yaml_instance/workflow_designer.yaml``: emit only the workflow YAML, flagged if it fails validation."""

import re
from typing import Any, Dict

from functions.function_calling.workflow_design import validate_workflow_yaml

# Greedy: prompts inside the generated workflow may contain their own ``` fences.
_FENCED_YAML = re.compile(r"```(?:yaml|yml)?\s*\n(.*)```", re.DOTALL)


def extract_validated_workflow(data: str, _context: Dict[str, Any]) -> str:
    """Strip the designer's reply down to its YAML block and re-validate it.

    A valid workflow passes through unchanged. An invalid one keeps its YAML but gains the
    validation errors as leading ``#`` comments, so the result is still a YAML document the
    user can fix, while saving it is rejected by the same check.
    """
    match = _FENCED_YAML.search(data or "")
    yaml_text = (match.group(1) if match else data or "").strip() + "\n"
    verdict = validate_workflow_yaml(yaml_text)
    if verdict == "OK":
        return yaml_text
    comments = "\n".join(f"# {line}" for line in verdict.splitlines())
    return f"# VALIDATION FAILED - fix these before saving:\n{comments}\n{yaml_text}"
