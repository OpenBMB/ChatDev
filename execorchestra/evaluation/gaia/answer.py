"""GAIA answer boundary: expose only the final answer to the scorer."""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any


@dataclass(frozen=True)
class GaiaAnswer:
    model_answer: str | int | float | list[Any] | None
    status: str = "ok"
    extraction: str = "final_output_text"


def extract_model_answer(final_output: Any) -> GaiaAnswer:
    """Extract a stable answer value without seeing evaluator-only data.

    The adapter accepts a plain final artifact, a JSON scalar/list, or a small
    ``final_answer:`` marker. It never receives or consults a gold answer.
    """
    if final_output is None:
        return GaiaAnswer(None, status="no_answer", extraction="missing")
    text = str(final_output).strip()
    if not text:
        return GaiaAnswer(None, status="no_answer", extraction="empty")
    marker = re.search(r"(?im)^\s*(?:final answer|answer)\s*:\s*(.+?)\s*$", text)
    candidate = marker.group(1).strip() if marker else text
    try:
        value = json.loads(candidate)
        if isinstance(value, (str, int, float, list)) or value is None:
            return GaiaAnswer(value, extraction="json_value")
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    return GaiaAnswer(candidate, extraction="text")
