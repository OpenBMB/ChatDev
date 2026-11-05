"""Explicit model membership, independent of capability ranking and health.

The registered catalog includes fixed control models for accounting and role
execution. Only candidate-scoped models may enter task resource selection.
Reserve files are never a runtime fallback. Missing policy fails closed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[2]

def resource_type(raw: Mapping[str, Any]) -> str:
    nested = raw.get("type")
    return str(raw.get("resource_type") or (nested.get("resource_type") if isinstance(nested, Mapping) else "") or "")

def is_candidate_resource(raw: Mapping[str, Any]) -> bool:
    return resource_type(raw) != "Model" or raw.get("selection_scope", "candidate") == "candidate"

def load_model_selection(root: str | Path = ROOT) -> dict[str, Any]:
    path = Path(root) / "sgar_mvp/config/model_selection.json"
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("model_selection_policy_unreadable") from exc
    if not isinstance(policy, dict) or policy.get("schema_version") != "model-selection-v1":
        raise ValueError("model_selection_policy_invalid")
    if set(policy) != {"schema_version", "candidates", "control_only"}:
        raise ValueError("model_selection_policy_fields_invalid")
    seen = {key: set() for key in ("source_id", "resource_id", "api_model_id")}
    for group in ("candidates", "control_only"):
        rows = policy.get(group)
        if not isinstance(rows, list) or (group == "candidates" and not rows):
            raise ValueError("model_selection_entries_invalid")
        for row in rows:
            if not isinstance(row, dict) or set(row) != set(seen):
                raise ValueError("model_selection_entry_invalid")
            for key, values in seen.items():
                value = row[key]
                if not isinstance(value, str) or not value or value != value.strip() or value in values:
                    raise ValueError("model_selection_identity_invalid")
                values.add(value)
    return policy

def registered_models(policy: Mapping[str, Any]) -> dict[str, tuple[str, Mapping[str, str]]]:
    return {row["resource_id"]: (scope, row)
            for group, scope in (("candidates", "candidate"), ("control_only", "control_only"))
            for row in policy[group]}

def require_registered_models(resources: Iterable[Mapping[str, Any]], *,
                              root: str | Path = ROOT, complete: bool = False) -> None:
    expected = registered_models(load_model_selection(root))
    seen: set[str] = set()
    for raw in resources:
        if resource_type(raw) != "Model":
            continue
        rid = str(raw.get("resource_id") or "")
        if rid not in expected:
            raise ValueError(f"model_not_registered:{rid}")
        if rid in seen:
            raise ValueError(f"model_selection_duplicate:{rid}")
        seen.add(rid)
        scope, entry = expected[rid]
        wire = raw.get("execution", {}).get("model_id")
        typed_wire = raw.get("type_specific", {}).get("model", {}).get("model_id")
        if wire != entry["api_model_id"] or typed_wire != wire:
            raise ValueError(f"model_selection_wire_identity_mismatch:{rid}")
        if raw.get("selection_scope") != scope:
            raise ValueError(f"model_selection_scope_mismatch:{rid}")
    if complete and seen != set(expected):
        raise ValueError("model_selection_catalog_incomplete")

def control_model_index(resources: Iterable[Mapping[str, Any]], *,
                        root: str | Path = ROOT) -> dict[str, dict[str, Any]]:
    """Resolve all registered Model definitions for explicit control-role lookup.

    Candidate eligibility and control-role assignment are independent properties.
    Callers still select only explicitly configured role resource IDs and must
    verify the exact control-role Provider evidence before making a request.
    """
    rows = list(resources)
    require_registered_models(rows, root=root, complete=True)
    return {str(raw["resource_id"]): dict(raw) for raw in rows
            if resource_type(raw) == "Model"}


def apply_model_selection(raw: dict[str, Any], policy: Mapping[str, Any]) -> dict[str, Any]:
    """Project a reviewed source into its explicit catalog scope, without changing it."""
    rid = raw["resource_id"]
    expected = registered_models(policy)
    if rid not in expected:
        raise ValueError(f"model_not_registered:{rid}")
    scope, entry = expected[rid]
    if raw["execution"]["model_id"] != entry["api_model_id"]:
        raise ValueError(f"model_selection_wire_identity_mismatch:{rid}")
    raw = {**raw, "selection_scope": scope}
    provenance = dict(raw.get("provenance", {}))
    if str(provenance.get("integration_status", "")).startswith("source_registered_pending"):
        provenance["integration_status"] = "canonical_registered_gateway_verification_pending"
        raw["provenance"] = provenance
        if raw["status"] == "inactive":
            raw["status"] = "active"
            raw["execution"] = {**raw["execution"], "execution_status": "active"}
    return raw


def candidate_health_manifests(resources: Iterable[Mapping[str, Any]], *,
                               root: str | Path = ROOT) -> list[Mapping[str, Any]]:
    """Select the complete configured candidate population before any paid probe."""
    rows = list(resources)
    require_registered_models(rows, root=root)
    selected = [row for row in rows
                if resource_type(row) == "Model" and is_candidate_resource(row)]
    expected = {row["resource_id"] for row in load_model_selection(root)["candidates"]}
    if {row["resource_id"] for row in selected} != expected:
        raise ValueError("candidate_health_catalog_incomplete")
    return selected


def validated_candidate_ready_ids(health: Mapping[str, Any], *,
                                  root: str | Path = ROOT) -> set[str]:
    """Require endpoint-bound, hash-verified evidence for the current candidate set."""
    from .pipeline_control import canonical_sha256

    if health.get("schema_version") != 6 or health.get("ready_state_protocol") != "sgar-model-ready-state-v1":
        raise ValueError("candidate_health_protocol_invalid")
    unsigned = dict(health)
    claimed = unsigned.pop("health_sha256", None)
    if claimed != canonical_sha256(unsigned):
        raise ValueError("candidate_health_hash_mismatch")
    endpoint = str(health.get("endpoint_identity_sha256") or "")
    if len(endpoint) != 64 or any(c not in "0123456789abcdef" for c in endpoint):
        raise ValueError("candidate_health_endpoint_missing")
    expected = {row["resource_id"]: row["api_model_id"]
                for row in load_model_selection(root)["candidates"]}
    rows = health.get("models")
    if not isinstance(rows, list) or any(not isinstance(row, Mapping) for row in rows):
        raise ValueError("candidate_health_records_invalid")
    if len(rows) != len(expected) or {row.get("resource_id") for row in rows} != set(expected):
        raise ValueError("candidate_health_population_mismatch")
    ready_ids = set()
    for row in rows:
        rid = row["resource_id"]
        if row.get("model_id") != expected[rid]:
            raise ValueError("candidate_health_wire_identity_mismatch")
        ready = row.get("ready_state") or {}
        if ready.get("protocol") != "sgar-model-ready-state-v1":
            raise ValueError("candidate_health_record_protocol_invalid")
        if ready.get("status") == "ready":
            evidence = row.get("capability_evidence") or {}
            if row.get("text_ok") is not True or (evidence.get("generic_strict_schema") or {}).get("status") != "live_verified":
                raise ValueError("candidate_health_ready_evidence_inconsistent")
            ready_ids.add(rid)
    return ready_ids


def require_healthy_candidate_models(resources: Iterable[Mapping[str, Any]],
                                    health: Mapping[str, Any], *,
                                    root: str | Path = ROOT) -> None:
    rows = list(resources)
    require_registered_models(rows, root=root)
    ready_ids = validated_candidate_ready_ids(health, root=root)
    for row in rows:
        if resource_type(row) != "Model":
            continue
        if not is_candidate_resource(row):
            raise ValueError("control_model_in_candidate_pool")
        if row["resource_id"] not in ready_ids:
            raise ValueError("unhealthy_model_in_candidate_pool:" + row["resource_id"])


def validated_candidate_admitted_ids(health: Mapping[str, Any], *,
                                      root: str | Path = ROOT) -> set[str]:
    """Admit measured-ready models plus explicit endpoint-bound user approvals."""
    from .model_admission import operator_admission
    admitted = validated_candidate_ready_ids(health, root=root)
    for row in health["models"]:
        if operator_admission(row, health["endpoint_identity_sha256"]) is not None:
            admitted.add(row["resource_id"])
    return admitted


def require_admitted_candidate_models(resources: Iterable[Mapping[str, Any]],
                                     health: Mapping[str, Any], *,
                                     root: str | Path = ROOT) -> None:
    rows = list(resources)
    require_registered_models(rows, root=root)
    admitted = validated_candidate_admitted_ids(health, root=root)
    for row in rows:
        if resource_type(row) != "Model":
            continue
        if not is_candidate_resource(row):
            raise ValueError("control_model_in_candidate_pool")
        if row["resource_id"] not in admitted:
            raise ValueError("unhealthy_model_in_candidate_pool:" + row["resource_id"])
