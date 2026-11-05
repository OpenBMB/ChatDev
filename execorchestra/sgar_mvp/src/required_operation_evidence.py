"""Check whether a completed capability operation supplied usable evidence."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from .capability_operations import normalize_capability_operation


def required_operation_evidence_failure(
    capability_operation_id: str,
    required_operation_kinds: Sequence[str],
    output: Any,
) -> str | None:
    """Reject explicit empty discovery results when that operation is required.

    A successful transport with zero search records cannot establish a source
    for a task that requires web discovery. Other operation outputs retain their
    declared contracts; absence of this explicit count is not inferred as empty.
    """
    kind = normalize_capability_operation(
        str(capability_operation_id).rsplit("::", 1)[-1]
    )
    required = {
        normalize_capability_operation(item)
        for item in required_operation_kinds if str(item).strip()
    }
    if kind not in required or kind != "search_web":
        return None
    if isinstance(output, str):
        try:
            output = json.loads(output)
        except (ValueError, TypeError):
            return None
    if (
        isinstance(output, Mapping)
        and type(output.get("result_count")) is int
        and output["result_count"] == 0
        and output.get("records") == []
    ):
        return "required_operation_no_records"
    return None
