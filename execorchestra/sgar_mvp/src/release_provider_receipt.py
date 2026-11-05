"""Verification of the five paid control-role probes used by a sealed release."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from .pipeline_control import canonical_sha256
from .release_source_seal import load_and_verify_source_seal
from .control_role_policy import ControlRolePolicyV1, load_control_role_policy
from .model_response_contracts import (
    build_exact_schema_probe_request,
    system_role_requirement,
)
from .model_transport import model_request_sha256
from .planner import DEFAULT_PLANNER_MAX_OUTPUT_TOKENS


RELEASE_PROVIDER_PROBE_PROTOCOL = "sgar-release-control-provider-probes-v2"
RELEASE_PROVIDER_PROBE_ROLES = (
    "profiler",
    "planner",
    "plan_compiler",
    "plan_adaptation",
    "evaluator",
)
RELEASE_PROVIDER_PROBE_EFFORTS = {
    "profiler": "xhigh",
    "planner": "xhigh",
    "plan_compiler": "xhigh",
    "plan_adaptation": "xhigh",
    "evaluator": "high",
}
_RELEASE_PROVIDER_SCHEMA_ROLES = {
    "profiler": "hyde",
    "planner": "planner",
    "plan_compiler": "plan_compiler",
    "plan_adaptation": "plan_adaptation",
    "evaluator": "evaluator",
}
_RELEASE_PROVIDER_OUTPUT_CAPS = {
    "profiler": 16384,
    "planner": DEFAULT_PLANNER_MAX_OUTPUT_TOKENS,
    "plan_compiler": None,
    "plan_adaptation": None,
    "evaluator": 8192,
}


def _expected_probe_identity(
    role: str,
    *,
    control_role_policy: ControlRolePolicyV1 | None = None,
) -> dict[str, str]:
    control = control_role_policy or load_control_role_policy()
    role_policy = control.for_role(role)  # type: ignore[arg-type]
    requirement = system_role_requirement(_RELEASE_PROVIDER_SCHEMA_ROLES[role])
    request = build_exact_schema_probe_request(
        model_id=role_policy.api_model_id,
        requirement=requirement,
        request_fields=role_policy.request_fields(),
    )
    output_cap = _RELEASE_PROVIDER_OUTPUT_CAPS[role]
    if output_cap is not None:
        request["max_tokens"] = output_cap
    return {
        "request_sha256": model_request_sha256(request),
        "request_policy_sha256": role_policy.role_policy_sha256,
        "prompt_sha256": canonical_sha256(request["messages"]),
        "schema_sha256": str(requirement.schema_sha256),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_sha(value: Any, *, code: str) -> str:
    normalized = str(value or "").strip().lower()
    if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
        raise RuntimeError(code)
    return normalized


def load_and_verify_release_provider_probe_receipt(
    path: Path,
    *,
    expected_endpoint_identity_sha256: str | None = None,
    expected_source_seal_sha256: str | None = None,
    control_role_policy: ControlRolePolicyV1 | None = None,
) -> dict[str, Any]:
    control = control_role_policy or load_control_role_policy()
    source = path.resolve()
    payload = json.loads(source.read_text(encoding="utf-8-sig"))
    claimed = _require_sha(payload.get("result_sha256"), code="release_probe_result_hash_missing")
    unsigned = dict(payload)
    unsigned.pop("result_sha256", None)
    if claimed != canonical_sha256(unsigned):
        raise RuntimeError("release_probe_result_hash_mismatch")
    local_refresh = payload.get("protocol") == "sgar-local-control-probe-refresh-v1"
    if local_refresh:
        if expected_source_seal_sha256 is not None:
            raise RuntimeError("local_probe_refresh_not_release_evidence")
        parent = payload.get("parent_receipt")
        if not isinstance(parent, dict):
            raise RuntimeError("local_probe_refresh_parent_missing")
        parent_unsigned = dict(parent)
        parent_hash = parent_unsigned.pop("result_sha256", None)
        if parent_hash != canonical_sha256(parent_unsigned):
            raise RuntimeError("local_probe_refresh_parent_hash_mismatch")
        if parent.get("status") != "passed" or parent.get("endpoint_identity_sha256") != payload.get("endpoint_identity_sha256"):
            raise RuntimeError("local_probe_refresh_parent_identity_mismatch")
        fresh = payload.get("refreshed_roles")
        if not isinstance(fresh, list) or len(set(fresh)) != len(fresh) or not set(fresh) <= set(RELEASE_PROVIDER_PROBE_ROLES):
            raise RuntimeError("local_probe_refresh_roles_invalid")
        if int(payload.get("provider_request_count") or 0) != len(fresh):
            raise RuntimeError("local_probe_refresh_count_invalid")
        inherited = {item["role"]: item for item in parent.get("records", [])}
        for item in payload.get("records", []):
            if item.get("role") not in fresh and item != inherited.get(item.get("role")):
                raise RuntimeError("local_probe_refresh_inherited_record_mismatch")
    if (
        (not local_refresh and payload.get("protocol") != RELEASE_PROVIDER_PROBE_PROTOCOL)
        or payload.get("status") != "passed"
        or (not local_refresh and int(payload.get("provider_request_count") or 0) != 5)
        or payload.get("provider_reasoning_plaintext_persisted") is not False
    ):
        raise RuntimeError("release_probe_result_contract_invalid")
    if expected_source_seal_sha256 is not None:
        actual_source = (payload.get("release_source_seal") or {}).get("seal_sha256")
        if actual_source != expected_source_seal_sha256:
            raise RuntimeError("release_probe_source_seal_mismatch")
    endpoint = _require_sha(
        payload.get("endpoint_identity_sha256"),
        code="release_probe_endpoint_identity_invalid",
    )
    if expected_endpoint_identity_sha256 is not None and endpoint != expected_endpoint_identity_sha256:
        raise RuntimeError("release_probe_endpoint_identity_mismatch")
    records = payload.get("records")
    if not isinstance(records, list) or tuple(
        str(item.get("role") or "") for item in records if isinstance(item, Mapping)
    ) != RELEASE_PROVIDER_PROBE_ROLES:
        raise RuntimeError("release_probe_roles_invalid")
    for item in records:
        if not isinstance(item, Mapping):
            raise RuntimeError("release_probe_record_invalid")
        role = str(item.get("role") or "")
        role_policy = control.for_role(role)  # type: ignore[arg-type]
        if (
            item.get("model_resource_id") != role_policy.resource_id
            or item.get("api_model_id") != role_policy.api_model_id
            or item.get("reasoning_effort") != role_policy.reasoning_effort
            or item.get("temperature") != role_policy.temperature
            or item.get("finish_reason") != "stop"
            or item.get("endpoint_identity_sha256") != endpoint
        ):
            raise RuntimeError(f"release_probe_record_policy_invalid:{role}")
        expected = _expected_probe_identity(
            role,
            control_role_policy=control,
        )
        for field_name in (
            "request_sha256",
            "request_policy_sha256",
            "prompt_sha256",
            "response_sha256",
            "schema_sha256",
        ):
            actual = _require_sha(
                item.get(field_name),
                code=f"release_probe_{field_name}_invalid:{role}",
            )
            if field_name in expected and actual != expected[field_name]:
                raise RuntimeError(
                    f"release_probe_{field_name}_mismatch:{role}"
                )
        if not isinstance(item.get("usage"), Mapping):
            raise RuntimeError(f"release_probe_usage_invalid:{role}")
        reasoning = item.get("provider_reasoning_observation")
        if not isinstance(reasoning, Mapping) or "storage_handle" in reasoning:
            raise RuntimeError(f"release_probe_reasoning_observation_invalid:{role}")
    return payload


def resolve_activated_release_provider_probe_receipt(
    project_root: str | Path,
    *,
    expected_endpoint_identity_sha256: str,
) -> tuple[Path, dict[str, Any]]:
    root = Path(project_root).resolve()
    explicit = str(os.environ.get("SGAR_RELEASE_PROVIDER_PROBE_RECEIPT_PATH") or "").strip()
    if explicit:
        path = Path(explicit).resolve()
        return path, load_and_verify_release_provider_probe_receipt(
            path,
            expected_endpoint_identity_sha256=expected_endpoint_identity_sha256,
        )
    activated_raw = str(os.environ.get("SGAR_ACTIVATED_SYSTEM_SEAL_PATH") or "").strip()
    if not activated_raw:
        raise RuntimeError("activated_release_probe_receipt_unavailable")
    activated = load_and_verify_source_seal(
        Path(activated_raw),
        project_root=root,
        allowed_stages=("activated",),
    )
    promotion_path = Path(str(activated.get("promotion_receipt_path") or "")).resolve()
    if not promotion_path.is_file():
        raise RuntimeError("activated_promotion_receipt_missing")
    if _sha256_file(promotion_path) != activated.get("promotion_receipt_file_sha256"):
        raise RuntimeError("activated_promotion_receipt_file_hash_mismatch")
    promotion = json.loads(promotion_path.read_text(encoding="utf-8-sig"))
    claimed = _require_sha(
        promotion.get("receipt_sha256"),
        code="activated_promotion_receipt_hash_missing",
    )
    unsigned = dict(promotion)
    unsigned.pop("receipt_sha256", None)
    if claimed != canonical_sha256(unsigned):
        raise RuntimeError("activated_promotion_receipt_hash_mismatch")
    probe_path = Path(str(promotion.get("provider_probe_results_path") or "")).resolve()
    if not probe_path.is_file():
        raise RuntimeError("activated_provider_probe_results_missing")
    if _sha256_file(probe_path) != promotion.get("provider_probe_results_file_sha256"):
        raise RuntimeError("activated_provider_probe_results_file_hash_mismatch")
    return probe_path, load_and_verify_release_provider_probe_receipt(
        probe_path,
        expected_endpoint_identity_sha256=expected_endpoint_identity_sha256,
        expected_source_seal_sha256=str(
            activated.get("parent_release_source_seal_sha256") or ""
        ),
    )


__all__ = [
    "RELEASE_PROVIDER_PROBE_EFFORTS",
    "RELEASE_PROVIDER_PROBE_PROTOCOL",
    "RELEASE_PROVIDER_PROBE_ROLES",
    "load_and_verify_release_provider_probe_receipt",
    "resolve_activated_release_provider_probe_receipt",
]
