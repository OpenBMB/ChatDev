"""Explicit user admission kept separate from measured provider health.

Approval belongs to one immutable health record and endpoint. A new health apply
removes it unless the operator explicitly approves the new record. No model name
or task-specific rule participates in the decision.
"""
from __future__ import annotations
from typing import Any, Mapping
from .pipeline_control import canonical_sha256

PROTOCOL = "sgar-operator-model-admission-v1"

def admission_capabilities(record: Mapping[str, Any]) -> tuple[str, ...]:
    supports = record.get("supports") or {}
    caps = {"generic_strict_schema"}
    for name in ("json_mode", "tool_calling", "vision"):
        if supports.get(name) is True:
            caps.add(name)
    if "tool_calling" in caps:
        caps.add("tool_result_continuation")
    return tuple(sorted(caps))

def operator_admission(record: Mapping[str, Any], endpoint_sha256: str) -> dict[str, Any] | None:
    value = record.get("operator_admission")
    if value is None:
        return None
    fields = {"protocol", "resource_id", "model_id", "endpoint_identity_sha256",
              "observed_record_sha256", "approved_at", "approved_by", "reason",
              "capabilities", "approval_sha256"}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("operator_model_admission_invalid")
    unsigned = {k: v for k, v in value.items() if k != "approval_sha256"}
    observed = {k: v for k, v in record.items() if k != "operator_admission"}
    if (value["protocol"] != PROTOCOL or value["approved_by"] != "user"
        or value["resource_id"] != record.get("resource_id")
        or value["model_id"] != record.get("model_id")
        or value["endpoint_identity_sha256"] != endpoint_sha256
        or value["observed_record_sha256"] != canonical_sha256(observed)
        or value["approval_sha256"] != canonical_sha256(unsigned)
        or value["capabilities"] != list(admission_capabilities(record))
        or not isinstance(value["approved_at"], str) or not value["approved_at"].strip()
        or not isinstance(value["reason"], str) or not value["reason"].strip()):
        raise ValueError("operator_model_admission_binding_invalid")
    return dict(value)

def approve_record(record: Mapping[str, Any], *, endpoint_sha256: str,
                   approved_at: str, reason: str) -> dict[str, Any]:
    result = {k: v for k, v in record.items() if k != "operator_admission"}
    approval = {"protocol": PROTOCOL, "resource_id": result["resource_id"],
                "model_id": result["model_id"], "endpoint_identity_sha256": endpoint_sha256,
                "observed_record_sha256": canonical_sha256(result),
                "approved_at": approved_at, "approved_by": "user", "reason": reason,
                "capabilities": list(admission_capabilities(result))}
    approval["approval_sha256"] = canonical_sha256(approval)
    result["operator_admission"] = approval
    operator_admission(result, endpoint_sha256)
    return result
