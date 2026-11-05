"""A narrow, deterministic postcondition for literal answers from fetched sources.

This check is deliberately limited to declared exact-name/identifier extraction.
It does not judge inferred, calculated, translated, or free-form answers.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from html import unescape
import json
import re
from typing import Any, Mapping


_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]{2,127}\Z")
_EXTRACTION = re.compile(r"\b(name|identifier|symbol|command)\b", re.I)
_EXACT = re.compile(r"\b(only|exact|literal|verbatim)\b", re.I)
_HTML_TAG = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class SourceLiteralSupportFailure:
    failure_code: str
    failed_step_id: str
    source_step_id: str
    source_body_sha256: str


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _operation_name(step: Any) -> str:
    return str(_field(step, "capability_operation_id", "") or "").rsplit("::", 1)[-1]


def _kind(step: Any) -> str:
    value = _field(step, "operation_kind", "")
    return str(getattr(value, "value", value) or "")


def _source_body(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        payload = json.loads(value)
    except ValueError:
        return None
    if not isinstance(payload, Mapping) or payload.get("status") != "success":
        return None
    body = payload.get("body")
    return body if isinstance(body, str) and body.strip() else None


def check_source_literal_support(
    *,
    plan: Any,
    output_contract: Any,
    artifact_type: str,
    final_answer: str,
    step_outputs: Mapping[str, Any],
) -> SourceLiteralSupportFailure | None:
    """Reject an unsupported exact identifier while preserving inferred answers.

    The first upstream generative URL selector is the failed frontier so recovery
    may replace its source choice and all dependent fetch/extraction steps.
    """

    if artifact_type != "plaintext" or not _field(output_contract, "grounding_requirements", ()):
        return None
    contract_text = " ".join(
        str(item)
        for name in ("required_content", "acceptance_criteria")
        for item in (_field(output_contract, name, ()) or ())
    )
    if not (_EXTRACTION.search(contract_text) and _EXACT.search(contract_text)):
        return None
    answer = final_answer.strip()
    if not _IDENTIFIER.fullmatch(answer):
        return None
    # Skip ordinary words and yes/no responses; this postcondition is for
    # source identifiers whose exact spelling is an output requirement.
    if not (any(char.isupper() for char in answer[1:]) or "_" in answer or any(char.isdigit() for char in answer)):
        return None
    steps = tuple(_field(plan, "steps", ()) or ())
    by_id = {str(_field(step, "step_id", "")): step for step in steps}
    final = _field(plan, "final_output", None)
    final_step = by_id.get(str(_field(final, "step_id", "")))
    if final_step is None or _kind(final_step) not in {"call_model", "call_agent", "synthesize_final"}:
        return None
    ancestors: set[str] = set()
    pending = list(_field(final_step, "depends_on", ()) or ())
    while pending:
        step_id = str(pending.pop())
        if step_id in ancestors:
            continue
        ancestors.add(step_id)
        ancestor = by_id.get(step_id)
        if ancestor is not None:
            pending.extend(_field(ancestor, "depends_on", ()) or ())
    missing: list[SourceLiteralSupportFailure] = []
    for step in steps:
        if _operation_name(step) != "fetch_web_resource" or str(_field(step, "step_id", "")) not in ancestors:
            continue
        source_step_id = str(_field(step, "step_id", ""))
        output_key = str(_field(step, "output_key", ""))
        body = _source_body(step_outputs.get(output_key) or step_outputs.get(source_step_id))
        if body is None:
            continue
        pattern = r"(?<![A-Za-z0-9_])" + re.escape(answer) + r"(?![A-Za-z0-9_])"
        visible = unescape(_HTML_TAG.sub(" ", body))
        joined_inline = unescape(_HTML_TAG.sub("", body))
        if re.search(pattern, visible, re.I) or re.search(pattern, joined_inline, re.I):
            return None
        bindings = _field(step, "input_bindings", {}) or {}
        url_binding = bindings.get("url") if isinstance(bindings, Mapping) else None
        selector_id = str(_field(url_binding, "from_step", "") or "")
        selector = by_id.get(selector_id)
        selector_kind = _kind(selector) if selector is not None else ""
        failed_step_id = (
            selector_id
            if selector_kind in {"call_model", "call_agent", "synthesize_final"}
            else source_step_id
        )
        missing.append(SourceLiteralSupportFailure(
            failure_code="source_literal_support_missing",
            failed_step_id=failed_step_id,
            source_step_id=source_step_id,
            source_body_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
        ))
    return missing[0] if missing else None
