"""Normalize Tool wire responses into their declared semantic artifacts.

Tools often use a JSON status envelope for transport while delivering the useful
artifact in one field of that envelope.  The orchestration layer must retain
both representations without registering the envelope as the downstream file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass(frozen=True)
class NormalizedToolOutput:
    content: str
    artifact_type: str
    transport_artifact_type: str
    payload: Optional[Any] = None
    warning: str = ""


@dataclass(frozen=True)
class NormalizedToolResult:
    """One immutable view of a completed Tool subprocess result."""

    return_code: int
    process_success: bool
    is_success: bool
    stdout: str
    stderr: str
    transport_content: str
    transport_artifact_type: str
    semantic_content: str
    semantic_artifact_type: str
    transport_payload: Optional[Any] = None
    wrapper_status: str = ""
    wrapper_semantic_ok: Optional[bool] = None
    wrapper_reason: str = ""
    wrapper_message: str = ""
    failure_source: str = ""
    primary_error: Optional[str] = None
    diagnostics: tuple[str, ...] = ()
    warning: str = ""


def _output_contract(manifest: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    manifest = manifest or {}
    contract = manifest.get("output_contract")
    if isinstance(contract, dict):
        return contract
    contract = manifest.get("io", {}).get("output_contract")
    return contract if isinstance(contract, dict) else {}


_MISSING = object()


def _payload_at_path(payload: Any, path: str) -> Any:
    value = payload
    for segment in str(path or "").split("."):
        if not segment:
            continue
        if not isinstance(value, dict) or segment not in value:
            return _MISSING
        value = value[segment]
    return value


def _serialize_payload(value: Any, artifact_type: str) -> str:
    if isinstance(value, str):
        return value
    if artifact_type == "json":
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


def normalize_tool_output(
    output_data: str,
    manifest: Optional[Dict[str, Any]] = None,
) -> NormalizedToolOutput:
    """Return the manifest-declared semantic output or the original wire body.

    ``semantic_output`` is intentionally manifest-driven.  The runtime never
    guesses that arbitrary fields named ``text`` or ``data`` are a file-like
    artifact, avoiding cross-tool semantic leakage.
    """
    contract = _output_contract(manifest)
    transport_type = str(contract.get("artifact_type") or "plaintext").lower()
    semantic = contract.get("semantic_output")
    if not isinstance(semantic, dict):
        return NormalizedToolOutput(
            content=str(output_data or ""),
            artifact_type=transport_type,
            transport_artifact_type=transport_type,
        )

    semantic_type = str(semantic.get("artifact_type") or transport_type).lower()
    path = str(semantic.get("payload_path") or "").strip()
    if not path:
        return NormalizedToolOutput(
            content=str(output_data or ""),
            artifact_type=transport_type,
            transport_artifact_type=transport_type,
            warning="semantic_output_payload_path_missing",
        )
    try:
        envelope = json.loads(str(output_data or ""))
    except (TypeError, json.JSONDecodeError):
        return NormalizedToolOutput(
            content=str(output_data or ""),
            artifact_type=transport_type,
            transport_artifact_type=transport_type,
            warning="semantic_output_transport_not_json",
        )
    value = _payload_at_path(envelope, path)
    if value is _MISSING:
        return NormalizedToolOutput(
            content=str(output_data or ""),
            artifact_type=transport_type,
            transport_artifact_type=transport_type,
            payload=envelope,
            warning="semantic_output_payload_missing",
        )
    return NormalizedToolOutput(
        content=_serialize_payload(value, semantic_type),
        artifact_type=semantic_type,
        transport_artifact_type=transport_type,
        payload=envelope,
    )


def _wrapper_message(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("message", "reason", "error"):
        value = payload.get(key)
        if isinstance(value, dict):
            nested = value.get("message") or value.get("reason")
            if nested:
                return str(nested).strip()
        elif value not in (None, ""):
            return str(value).strip()
    return ""


def _meaningful_stderr(stderr: str) -> str:
    """Exclude common package-manager notices from primary diagnostics."""
    meaningful = []
    for line in str(stderr or "").splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if not stripped:
            continue
        if "running pip as the 'root' user" in lowered:
            continue
        if lowered.startswith("[notice]") or "new release of pip" in lowered:
            continue
        meaningful.append(stripped)
    return "\n".join(meaningful)


def normalize_tool_process_result(
    return_code: int,
    stdout: str,
    stderr: str,
    manifest: Optional[Dict[str, Any]] = None,
) -> NormalizedToolResult:
    """Normalize process channels, wrapper metadata, and semantic output once."""
    stdout_text = str(stdout or "")
    stderr_text = str(stderr or "")
    contract = _output_contract(manifest)
    transport_type = str(contract.get("artifact_type") or "plaintext").lower()
    try:
        payload = json.loads(stdout_text)
    except (TypeError, json.JSONDecodeError):
        payload = None

    # A JSON field named ``status`` is ordinary business data unless the
    # manifest explicitly declares a result-status contract.  This prevents
    # one Tool's wrapper convention from becoming a global execution rule.
    status_contract = contract.get("result_status")
    wrapper_status = ""
    wrapper_semantic_ok: Optional[bool] = None
    wrapper_reason = ""
    if isinstance(status_contract, dict):
        status_path = str(status_contract.get("payload_path") or "").strip()
        success_values = {
            str(item) for item in (status_contract.get("success_values") or [])
        }
        failure_values = {
            str(item) for item in (status_contract.get("failure_values") or [])
        }
        raw_status = _payload_at_path(payload, status_path) if status_path else _MISSING
        if raw_status is _MISSING:
            wrapper_semantic_ok = False
            wrapper_reason = "declared_result_status_missing"
        else:
            wrapper_status = str(raw_status)
            if wrapper_status in success_values:
                wrapper_semantic_ok = True
            elif wrapper_status in failure_values:
                wrapper_semantic_ok = False
                wrapper_reason = "declared_result_status_failure"
            else:
                wrapper_semantic_ok = False
                wrapper_reason = "declared_result_status_unrecognized"
    wrapper_message = _wrapper_message(payload)
    process_success = int(return_code) == 0
    combined_success = process_success and wrapper_semantic_ok is not False

    if not process_success and wrapper_semantic_ok is False:
        failure_source = "process_exit_and_wrapper_status"
    elif not process_success:
        failure_source = "process_exit"
    elif wrapper_semantic_ok is False:
        failure_source = "wrapper_status"
    else:
        failure_source = ""

    if combined_success:
        semantic = normalize_tool_output(stdout_text, manifest)
    else:
        semantic = NormalizedToolOutput(
            content=stdout_text,
            artifact_type=transport_type,
            transport_artifact_type=transport_type,
            payload=payload,
        )

    primary_error = None
    if not combined_success:
        if wrapper_semantic_ok is False:
            primary_error = wrapper_reason
        else:
            primary_error = (
                _meaningful_stderr(stderr_text)
                or f"Tool process exited with code {return_code}."
            )

    return NormalizedToolResult(
        return_code=int(return_code),
        process_success=process_success,
        is_success=combined_success,
        stdout=stdout_text,
        stderr=stderr_text,
        transport_content=stdout_text,
        transport_artifact_type=transport_type,
        semantic_content=semantic.content,
        semantic_artifact_type=semantic.artifact_type,
        transport_payload=payload,
        wrapper_status=wrapper_status,
        wrapper_semantic_ok=wrapper_semantic_ok,
        wrapper_reason=wrapper_reason,
        wrapper_message=wrapper_message,
        failure_source=failure_source,
        primary_error=primary_error,
        diagnostics=(stderr_text,) if stderr_text else (),
        warning=semantic.warning,
    )
