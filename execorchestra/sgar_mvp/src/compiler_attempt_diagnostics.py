"""Best-effort, value-safe diagnostics for Compiler V3 semantic attempts.

This module is deliberately outside the model-facing contract surface.  It
does not validate, normalize, project, retry, or otherwise influence Compiler
decisions.  Callers must treat every persistence failure as non-authoritative
diagnostic loss and preserve the original business outcome.
"""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

from pydantic import ValidationError

from .atomic_io import temporary_sibling_path
from .pipeline_control import canonical_sha256
from .secret_policy import sanitize_sensitive_text


COMPILER_ATTEMPT_DIAGNOSTIC_PROTOCOL = "sgar-compiler-attempt-diagnostic-v1"
COMPILER_CORRECTION_DIAGNOSTIC_PROTOCOL = "sgar-compiler-correction-diagnostic-v1"
COMPILER_FIELD_DELTA_PROTOCOL = "sgar-compiler-attempt-field-delta-v1"

_SENSITIVE_KEY = re.compile(
    r"(?i)(?:api[_-]?key|apikey|secret|password|credential|"
    r"^(?:(?:access|refresh|bearer|auth)[_-]?)?token$|authorization)"
)
_HIDDEN_REASONING_KEY = re.compile(
    r"(?i)(?:reasoning[_-]?content|chain[_-]?of[_-]?thought|hidden[_-]?reasoning)"
)
_MISSING = object()


class CompilerAttemptDiagnosticPersistenceError(RuntimeError):
    """Raised only inside the best-effort diagnostic boundary."""


def _pointer_token(value: Any) -> str:
    return str(value).replace("~", "~0").replace("/", "~1")


def _child_path(path: str, value: Any) -> str:
    token = _pointer_token(value)
    return f"{path}/{token}" if path else f"/{token}"


def _json_safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def sanitize_diagnostic_value(
    value: Any,
    *,
    secret_values: Sequence[str] = (),
    host_roots: Sequence[str] = (),
    hidden_values: Sequence[str] = (),
) -> tuple[Any, tuple[dict[str, Any], ...]]:
    """Return a JSON-safe structural copy with sensitive values redacted."""

    actions: list[dict[str, Any]] = []

    def record(path: str, category: str, count: int = 1) -> None:
        actions.append(
            {
                "path": path or "/",
                "category": category,
                "occurrence_count": int(count),
            }
        )

    def walk(item: Any, path: str) -> Any:
        if isinstance(item, Mapping):
            projected: dict[str, Any] = {}
            for raw_key, child in item.items():
                key = str(raw_key)
                child_path = _child_path(path, key)
                if _HIDDEN_REASONING_KEY.search(key):
                    projected[key] = "<redacted-hidden>"
                    record(child_path, "hidden")
                elif _SENSITIVE_KEY.search(key):
                    projected[key] = "<redacted-secret>"
                    record(child_path, "secret")
                else:
                    projected[key] = walk(child, child_path)
            return projected
        if isinstance(item, (list, tuple)):
            return [walk(child, _child_path(path, index)) for index, child in enumerate(item)]
        if isinstance(item, str):
            sanitized, counts = sanitize_sensitive_text(
                item,
                secret_values=secret_values,
                host_roots=host_roots,
                hidden_values=hidden_values,
            )
            for category, count in sorted(counts.items()):
                if count:
                    record(path, category, count)
            return sanitized
        return _json_safe_scalar(item)

    sanitized = walk(deepcopy(value), "")
    return sanitized, tuple(actions)


def validation_error_diagnostics(
    exc: ValidationError,
    *,
    secret_values: Sequence[str] = (),
    host_roots: Sequence[str] = (),
    hidden_values: Sequence[str] = (),
) -> tuple[dict[str, Any], ...]:
    """Project complete loc/type/msg/input fields without persisting secrets."""

    projected: list[dict[str, Any]] = []
    for item in exc.errors(include_input=True, include_url=False):
        location = [
            value if isinstance(value, int) else str(value)
            for value in tuple(item.get("loc") or ())
        ]
        raw_input = item.get("input")
        terminal_field = str(location[-1]) if location else ""
        if _HIDDEN_REASONING_KEY.search(terminal_field):
            safe_input = "<redacted-hidden>"
            redactions = (
                {
                    "path": "/input",
                    "category": "hidden",
                    "occurrence_count": 1,
                },
            )
        elif _SENSITIVE_KEY.search(terminal_field):
            safe_input = "<redacted-secret>"
            redactions = (
                {
                    "path": "/input",
                    "category": "secret",
                    "occurrence_count": 1,
                },
            )
        else:
            safe_input, redactions = sanitize_diagnostic_value(
                raw_input,
                secret_values=secret_values,
                host_roots=host_roots,
                hidden_values=hidden_values,
            )
        safe_message, _ = sanitize_sensitive_text(
            str(item.get("msg") or "Validation error"),
            secret_values=secret_values,
            host_roots=host_roots,
            hidden_values=hidden_values,
        )
        projected.append(
            {
                "loc": location,
                "type": str(item.get("type") or "validation_error"),
                "msg": safe_message,
                "input": safe_input,
                "input_storage": "redacted" if redactions else "verbatim_safe",
                "input_redactions": list(redactions),
            }
        )
    return tuple(projected)


def _response_format_identity(api_kwargs: Mapping[str, Any]) -> dict[str, Any]:
    response_format = api_kwargs.get("response_format")
    if not isinstance(response_format, Mapping):
        return {
            "response_format_type": None,
            "name": None,
            "strict": None,
            "schema_sha256": None,
        }
    format_type = str(response_format.get("type") or "") or None
    json_schema = response_format.get("json_schema")
    if format_type != "json_schema" or not isinstance(json_schema, Mapping):
        return {
            "response_format_type": format_type,
            "name": None,
            "strict": None,
            "schema_sha256": None,
        }
    schema = json_schema.get("schema")
    return {
        "response_format_type": format_type,
        "name": str(json_schema.get("name") or "") or None,
        "strict": bool(json_schema.get("strict")),
        "schema_sha256": (
            canonical_sha256(schema) if isinstance(schema, Mapping) else None
        ),
    }


def build_attempt_diagnostic(
    *,
    run_id: str,
    attempt_index: int,
    graph_revision: int,
    subtask_id: str,
    subtask_revision: int,
    plan_revision: int,
    plan_revision_sha256: str,
    model_id: str,
    model_resource_id: str,
    prompt_version: str,
    prompt_sha256: str,
    request_sha256: str,
    provider_constraint_contract: Mapping[str, Any],
    api_kwargs: Mapping[str, Any],
    local_schema_name: str,
    local_schema_version: str,
    local_schema_sha256: str,
    candidate_pool_sha256: str,
    response_sha256: str | None,
    structured_json: Any,
    validation_status: str,
    failure_class: str | None,
    structured_json_stage: str = "unspecified",
    validation_error: ValidationError | None = None,
    secret_values: Sequence[str] = (),
    host_roots: Sequence[str] = (),
    hidden_values: Sequence[str] = (),
) -> dict[str, Any]:
    safe_json, response_redactions = sanitize_diagnostic_value(
        structured_json,
        secret_values=secret_values,
        host_roots=host_roots,
        hidden_values=hidden_values,
    )
    errors = (
        validation_error_diagnostics(
            validation_error,
            secret_values=secret_values,
            host_roots=host_roots,
            hidden_values=hidden_values,
        )
        if validation_error is not None
        else ()
    )
    provider_contract = {
        "version": str(provider_constraint_contract.get("protocol") or "") or None,
        "contract_sha256": provider_constraint_contract.get("contract_sha256"),
        "wire_schema_sha256": provider_constraint_contract.get("wire_schema_sha256"),
        **_response_format_identity(api_kwargs),
    }
    projection: dict[str, Any] = {
        "protocol": COMPILER_ATTEMPT_DIAGNOSTIC_PROTOCOL,
        "attempt_index": int(attempt_index),
        "run_id": str(run_id),
        "task_identity": {
            "graph_revision": int(graph_revision),
            "subtask_id": str(subtask_id),
            "subtask_revision": int(subtask_revision),
            "plan_revision": int(plan_revision),
            "plan_revision_sha256": str(plan_revision_sha256),
        },
        "model": {
            "model_id": str(model_id),
            "model_resource_id": str(model_resource_id),
        },
        "prompt": {
            "version": str(prompt_version),
            "sha256": str(prompt_sha256),
        },
        "request_sha256": str(request_sha256),
        "provider_schema": provider_contract,
        "local_schema": {
            "name": str(local_schema_name),
            "version": str(local_schema_version),
            "sha256": str(local_schema_sha256),
        },
        "candidate_pool_sha256": str(candidate_pool_sha256),
        "response_sha256": response_sha256,
        "structured_json_storage": (
            "unavailable"
            if structured_json is None
            else ("redacted" if response_redactions else "verbatim_safe")
        ),
        "structured_json": safe_json,
        "structured_json_sha256": (
            canonical_sha256(safe_json) if structured_json is not None else None
        ),
        "structured_json_stage": str(structured_json_stage),
        "validation_scope": "local_response_schema",
        "validation_status": str(validation_status),
        "validation_errors": list(errors),
        "failure_class": failure_class,
        "response_redactions": list(response_redactions),
    }
    unhashed = dict(projection)
    projection["diagnostic_sha256"] = canonical_sha256(unhashed)
    return projection


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(
        dict(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    if path.exists():
        existing = path.read_text(encoding="utf-8").rstrip("\n")
        if existing == serialized:
            return
        raise CompilerAttemptDiagnosticPersistenceError(
            "compiler_attempt_diagnostic_overwrite_forbidden"
        )
    temp = temporary_sibling_path(path)
    try:
        with temp.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    except OSError as exc:
        try:
            if temp.exists():
                temp.unlink()
        except OSError:
            pass
        raise CompilerAttemptDiagnosticPersistenceError(
            "compiler_attempt_diagnostic_persist_failed"
        ) from exc


def attempt_root(artifact_path: Path) -> Path:
    return artifact_path.with_name(f"{artifact_path.stem}.attempts")


def attempt_directory(artifact_path: Path, attempt_index: int) -> Path:
    return attempt_root(artifact_path) / f"compiler_attempt_{int(attempt_index)}"


def persist_attempt_diagnostic(
    artifact_path: Path,
    *,
    attempt_index: int,
    diagnostic: Mapping[str, Any],
) -> Path:
    target = attempt_directory(artifact_path, attempt_index) / "attempt.json"
    _atomic_json(target, diagnostic)
    if int(attempt_index) == 2:
        persist_field_delta(artifact_path)
    return target


def persist_correction_diagnostic(
    artifact_path: Path,
    *,
    source_attempt_index: int,
    next_attempt_index: int,
    correction: Mapping[str, Any],
    next_request_sha256: str,
    secret_values: Sequence[str] = (),
    host_roots: Sequence[str] = (),
    hidden_values: Sequence[str] = (),
) -> Path:
    safe_correction, redactions = sanitize_diagnostic_value(
        correction,
        secret_values=secret_values,
        host_roots=host_roots,
        hidden_values=hidden_values,
    )
    projection: dict[str, Any] = {
        "protocol": COMPILER_CORRECTION_DIAGNOSTIC_PROTOCOL,
        "source_attempt_index": int(source_attempt_index),
        "next_attempt_index": int(next_attempt_index),
        "semantic_correction": safe_correction,
        "semantic_correction_sha256": canonical_sha256(safe_correction),
        "next_request_sha256": str(next_request_sha256),
        "redactions": list(redactions),
    }
    projection["diagnostic_sha256"] = canonical_sha256(projection)
    target = (
        attempt_directory(artifact_path, source_attempt_index)
        / "correction_request.json"
    )
    _atomic_json(target, projection)
    return target


def _field_delta(before: Any, after: Any, path: str = "") -> list[dict[str, Any]]:
    if isinstance(before, Mapping) and isinstance(after, Mapping):
        changes: list[dict[str, Any]] = []
        for key in sorted(set(before) | set(after), key=str):
            child_path = _child_path(path, key)
            left = before.get(key, _MISSING)
            right = after.get(key, _MISSING)
            if left is _MISSING:
                changes.append({"path": child_path, "operation": "add", "after": right})
            elif right is _MISSING:
                changes.append({"path": child_path, "operation": "remove", "before": left})
            else:
                changes.extend(_field_delta(left, right, child_path))
        return changes
    if isinstance(before, list) and isinstance(after, list):
        changes = []
        for index in range(max(len(before), len(after))):
            child_path = _child_path(path, index)
            left = before[index] if index < len(before) else _MISSING
            right = after[index] if index < len(after) else _MISSING
            if left is _MISSING:
                changes.append({"path": child_path, "operation": "add", "after": right})
            elif right is _MISSING:
                changes.append({"path": child_path, "operation": "remove", "before": left})
            else:
                changes.extend(_field_delta(left, right, child_path))
        return changes
    if before == after:
        return []
    return [{"path": path or "/", "operation": "replace", "before": before, "after": after}]


def persist_field_delta(artifact_path: Path) -> Path | None:
    first_path = attempt_directory(artifact_path, 1) / "attempt.json"
    second_path = attempt_directory(artifact_path, 2) / "attempt.json"
    if not first_path.exists() or not second_path.exists():
        return None
    first = json.loads(first_path.read_text(encoding="utf-8"))
    second = json.loads(second_path.read_text(encoding="utf-8"))
    before = first.get("structured_json")
    after = second.get("structured_json")
    changes = _field_delta(before, after)
    projection: dict[str, Any] = {
        "protocol": COMPILER_FIELD_DELTA_PROTOCOL,
        "from_attempt_index": 1,
        "to_attempt_index": 2,
        "from_response_sha256": first.get("response_sha256"),
        "to_response_sha256": second.get("response_sha256"),
        "changes": changes,
    }
    projection["diagnostic_sha256"] = canonical_sha256(projection)
    target = attempt_directory(artifact_path, 2) / "field_delta_from_attempt_1.json"
    _atomic_json(target, projection)
    return target


__all__ = [
    "COMPILER_ATTEMPT_DIAGNOSTIC_PROTOCOL",
    "COMPILER_CORRECTION_DIAGNOSTIC_PROTOCOL",
    "COMPILER_FIELD_DELTA_PROTOCOL",
    "CompilerAttemptDiagnosticPersistenceError",
    "attempt_directory",
    "build_attempt_diagnostic",
    "persist_attempt_diagnostic",
    "persist_correction_diagnostic",
    "persist_field_delta",
    "sanitize_diagnostic_value",
    "validation_error_diagnostics",
]
