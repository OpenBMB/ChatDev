"""Revision-bound runtime contracts for formal SGAR candidate retrieval.

The module is intentionally independent from Planner, Plan Compiler, Gold, and
experiment schemas.  It freezes the effective retrieval state before any paid
work and guarantees that one subtask revision can produce at most one semantic
HyDE ideal-resource profile.  Candidate construction is added on top of these
contracts in the second retrieval commit.
"""

from __future__ import annotations

from . import terminal_progress

import argparse
import asyncio
import hashlib
import importlib
import json
import math
import os
import posixpath
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Sequence, cast

from pydantic import Field, field_validator, model_validator, model_serializer

from .atomic_io import temporary_sibling_path
from .capability_operations import manifest_capability_operations, requires_external_grounding
from .capability_operations import (
    normalize_task_capability_operations,
    normalize_task_general_operation_kinds,
    requests_external_content,
    tool_allowed_operation_kinds,
)
from .model_accounting import BudgetControlError, ModelAccountingError, RunCostLedger
from .model_identity import (
    ModelIdentityError,
    ResolvedModelIdentity,
    resolve_model_identity,
)
from .model_liveness import (
    ModelLivenessEvidence,
    ModelLivenessProbeError,
    ModelLivenessProbeService,
)
from .model_response_contracts import (
    CapabilityProbeEvidence,
    ExactCapabilityProbeService,
    ModelResponseContractError,
    OutputFormatRequirement,
    StructuredResponseMode,
    StructuredResponseModeInput,
    classify_output_schema_phase,
    normalize_structured_response_mode,
    system_role_requirement,
)
from .model_transport import (
    ModelTransportError,
    SyncModelTransportPort,
    require_sync_model_transport,
)
from .pipeline_control import (
    CandidateOrigin,
    CandidatePoolSnapshot,
    CandidateResourceRef,
    FailureResponsibility,
    FrozenContract,
    PerTypeConfidenceStatistics,
    RetrievalConfidenceEvidence,
    RetrievalAttemptOutcome,
    RetrievalAttemptRecord,
    SubtaskRevisionRef,
    canonical_json_bytes,
    canonical_sha256,
)
from .planner_contracts import PlannerContractConflict, validate_planner_subtask_contract
from .formal_contracts import (
    ExecutionResourceRequirementV1,
    NodeSemanticContractV2,
    SemanticEdgeContractV2,
    SemanticRequirementDeclarationV1,
)
from .profiler_protocol import (
    ProfilerInputEnvelopeV1,
    ProfilerMaterialDescriptorV1,
    ProfilerSubtaskContractV1,
)
from .internal_language import INTERNAL_LANGUAGE_POLICY
from .retrieval_policy import RetrievalPolicy, load_retrieval_policy
from .runtime_policy_context import bind_retrieval_policy_path
from .release_source_seal import load_and_verify_source_seal
from .resource_runtime import (
    ResourceDefinition,
    ResourceManifestError,
    runtime_adapter_supported,
)
from .schema import (
    Manifest,
    ManifestType,
    QueryRetrievalProfile,
    Subtask,
    TypedResourceRef,
    Vector,
)


RETRIEVAL_RUNTIME_PROTOCOL = "sgar-retrieval-runtime-v1"
MODEL_READY_STATE_PROTOCOL = "sgar-model-ready-state-v1"
FORMAL_TYPE_ORDER = ("Model", "Tool", "Skill", "Agent", "Resource", "Device")
FORMAL_TYPED_QUOTAS: Mapping[str, int] = {
    "Model": 5,
    "Tool": 10,
    "Skill": 4,
    "Agent": 3,
    "Resource": 0,
    "Device": 0,
}
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class RetrievalRuntimeError(ValueError):
    """Fail-closed retrieval configuration or runtime invariant."""

    def __init__(
        self,
        error_code: str,
        *,
        responsibility: str = "framework",
        retryable: bool = False,
    ) -> None:
        super().__init__(error_code)
        self.error_code = str(error_code)
        self.failure_responsibility = str(responsibility)
        self.retryable = bool(retryable)
        self.response_received = False


class LocalRetrievalInfrastructureError(RetrievalRuntimeError):
    """A structured local embedding/index outage eligible for fixed retry."""

    def __init__(self, error_code: str) -> None:
        super().__init__(
            error_code,
            responsibility=FailureResponsibility.INFRASTRUCTURE.value,
            retryable=True,
        )


class RetrievalPreparationError(RetrievalRuntimeError):
    """Cached terminal failure for one revision's ideal-profile preparation."""

    def __init__(
        self,
        error_code: str,
        *,
        responsibility: str,
        attempts: Sequence[RetrievalAttemptRecord] = (),
        response_received: bool = False,
        exception_type: str = "",
        message_sha256: str | None = None,
    ) -> None:
        super().__init__(error_code, responsibility=responsibility, retryable=False)
        self.attempts = tuple(attempts)
        self.response_received = bool(response_received)
        self.exception_type = str(exception_type)
        self.message_sha256 = str(
            message_sha256
            or canonical_sha256(
                {
                    "exception_type": self.exception_type,
                    "failure_code": self.error_code,
                    "responsibility": self.failure_responsibility,
                }
            )
        )

    def clone(self) -> "RetrievalPreparationError":
        return RetrievalPreparationError(
            self.error_code,
            responsibility=self.failure_responsibility,
            attempts=self.attempts,
            response_received=self.response_received,
            exception_type=self.exception_type,
            message_sha256=self.message_sha256,
        )


def _sha256_file(path: Path) -> str:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()
    except OSError as exc:
        raise RetrievalRuntimeError("retrieval_identity_file_unreadable") from exc


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RetrievalRuntimeError("retrieval_identity_json_invalid") from exc


def _resource_id(raw: Mapping[str, Any]) -> str:
    return str(raw.get("resource_id") or raw.get("id") or "").strip()


def _resource_type(raw: Mapping[str, Any]) -> str:
    nested = raw.get("type")
    nested_type = nested.get("resource_type") if isinstance(nested, Mapping) else None
    return str(raw.get("resource_type") or nested_type or "").strip()


def _model_api_id(raw: Mapping[str, Any]) -> str:
    specific = raw.get("type_specific")
    model = specific.get("model") if isinstance(specific, Mapping) else None
    execution = raw.get("execution")
    execution = execution if isinstance(execution, Mapping) else {}
    return str(
        (model.get("model_id") if isinstance(model, Mapping) else None)
        or execution.get("model_id")
        or execution.get("default_base_model")
        or ""
    ).strip()


def _canonical_json_value(value: Any) -> Any:
    return json.loads(canonical_json_bytes(value).decode("utf-8"))


class NamedSha256(FrozenContract):
    name: str = Field(min_length=1)
    sha256: str

    @field_validator("sha256")
    @classmethod
    def _valid_hash(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
            raise ValueError("named_sha256_invalid")
        return normalized


class TypedQuota(FrozenContract):
    resource_type: str = Field(min_length=1)
    quota: int = Field(ge=0)


class AvailabilityRecord(FrozenContract):
    resource_id: str = Field(min_length=1)
    resource_type: str = Field(min_length=1)
    in_effective_pool: bool
    status: Literal["available", "unavailable", "unknown"]
    reason_code: str | None = None
    provider_compatibility: Literal["compatible", "incompatible", "unknown"] = "unknown"


class RetrievalRuntimeIdentity(FrozenContract):
    protocol: Literal[RETRIEVAL_RUNTIME_PROTOCOL] = RETRIEVAL_RUNTIME_PROTOCOL
    pool_sha256: str
    index_sha256: str
    index_components: tuple[NamedSha256, ...]
    policy_sha256: str
    availability_sha256: str
    availability_records: tuple[AvailabilityRecord, ...]
    active_strategy: str = Field(min_length=1)
    typed_quotas: tuple[TypedQuota, ...]
    profile_version: str = Field(min_length=1)
    embedding_model: str = Field(min_length=1)
    bge_prefix: str
    embedding_configuration_sha256: str = ""
    hyde_resource_id: str = Field(min_length=1)
    hyde_api_model_id: str = Field(min_length=1)
    hyde_prompt_version: str = Field(min_length=1)
    hyde_temperature: float | None
    hyde_max_tokens: int = Field(gt=0)
    hyde_reasoning_effort: str = "max"
    profiler_schema_sha256: str = ""
    internal_language_policy_sha256: str = ""
    identity_sha256: str = ""

    @field_validator("pool_sha256", "index_sha256", "policy_sha256", "availability_sha256")
    @classmethod
    def _valid_hash(cls, value: str, info: Any) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
            raise ValueError(f"{info.field_name}_invalid")
        return normalized

    @model_validator(mode="after")
    def _seal_identity(self) -> "RetrievalRuntimeIdentity":
        if self.active_strategy not in {
            "capability_only",
            "capability_constraint_weighted",
        }:
            raise ValueError("formal_retrieval_strategy_not_supported")
        component_names = [item.name for item in self.index_components]
        if component_names != ["capability", "constraint", "metadata"]:
            raise ValueError("retrieval_index_components_invalid")
        expected_index = canonical_sha256(
            {item.name: item.sha256 for item in self.index_components}
        )
        if self.index_sha256 != expected_index:
            raise ValueError("retrieval_combined_index_sha256_mismatch")

        quota_types = [item.resource_type for item in self.typed_quotas]
        if quota_types != list(FORMAL_TYPE_ORDER):
            raise ValueError("retrieval_typed_quota_order_invalid")
        if {item.resource_type: item.quota for item in self.typed_quotas} != dict(
            FORMAL_TYPED_QUOTAS
        ):
            raise ValueError("retrieval_typed_quotas_not_formal")


        identities = [item.resource_id for item in self.availability_records]
        if identities != sorted(identities) or len(identities) != len(set(identities)):
            raise ValueError("retrieval_availability_records_not_unique_sorted")
        expected_availability = canonical_sha256(self.availability_records)
        if self.availability_sha256 != expected_availability:
            raise ValueError("retrieval_availability_sha256_mismatch")

        projection = self.model_dump(mode="python", exclude={"identity_sha256"})
        expected = canonical_sha256(projection)
        if self.identity_sha256:
            supplied = self.identity_sha256.strip().lower()
            if supplied != expected:
                raise ValueError("retrieval_runtime_identity_sha256_mismatch")
        object.__setattr__(self, "identity_sha256", expected)
        return self

    @property
    def quota_map(self) -> dict[str, int]:
        return {item.resource_type: item.quota for item in self.typed_quotas}

    @property
    def eligible_resource_ids(self) -> frozenset[str]:
        return frozenset(
            item.resource_id
            for item in self.availability_records
            if item.in_effective_pool
            and (
                item.status == "available"
                if item.resource_type == "Model"
                else item.status != "unavailable"
            )
            and item.provider_compatibility != "incompatible"
        )


def _normalize_provider_compatibility(value: Any) -> str:
    if value is True:
        return "compatible"
    if value is False:
        return "incompatible"
    normalized = str(value or "unknown").strip().lower()
    if normalized not in {"compatible", "incompatible", "unknown"}:
        raise RetrievalRuntimeError("provider_compatibility_value_invalid")
    return normalized


def resolve_model_health_state_path(project_root: str | Path) -> Path:
    """Return the last explicitly applied ready-state, or the legacy baseline."""

    root = Path(project_root).resolve()
    applied = root / "sgar_mvp" / "runtime_state" / "model_ready_state.json"
    if applied.is_file():
        return applied
    return root / "sgar_mvp" / "config" / "model_health.json"


class AppliedReadyModel(FrozenContract):
    """One endpoint-bound model admitted by the last explicit health apply."""

    resource_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    structured_output_modes_live_verified: tuple[str, ...] = ()
    capabilities_live_verified: tuple[str, ...] = ()
    capability_evidence_sha256: str
    operator_approved_capabilities: tuple[str, ...] = ()
    operator_approval_sha256: str | None = None


class AppliedModelReadyState(FrozenContract):
    """Validated, operator-applied model readiness used by Git-authority runs."""

    protocol: Literal[MODEL_READY_STATE_PROTOCOL] = MODEL_READY_STATE_PROTOCOL
    endpoint_identity_sha256: str
    health_sha256: str
    generated_at_epoch: float = Field(ge=0)
    models: tuple[AppliedReadyModel, ...]

    @model_validator(mode="after")
    def _validate_identity(self) -> "AppliedModelReadyState":
        for field_name in ("endpoint_identity_sha256", "health_sha256"):
            value = str(getattr(self, field_name)).strip().lower()
            if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
                raise ValueError(f"{field_name}_invalid")
            object.__setattr__(self, field_name, value)
        resource_ids = tuple(item.resource_id for item in self.models)
        model_ids = tuple(item.model_id for item in self.models)
        if resource_ids != tuple(sorted(resource_ids)) or len(set(resource_ids)) != len(resource_ids):
            raise ValueError("applied_ready_state_resource_ids_invalid")
        if len(set(model_ids)) != len(model_ids):
            raise ValueError("applied_ready_state_model_ids_invalid")
        return self

    @property
    def by_resource_id(self) -> dict[str, AppliedReadyModel]:
        return {item.resource_id: item for item in self.models}


def load_applied_model_ready_state(
    project_root: str | Path,
    *,
    expected_endpoint_identity_sha256: str,
) -> AppliedModelReadyState:
    """Load only the explicitly applied ready-state and verify its own identity."""

    root = Path(project_root).resolve()
    path = root / "sgar_mvp" / "runtime_state" / "model_ready_state.json"
    if not path.is_file():
        raise RetrievalRuntimeError("applied_model_ready_state_missing")
    payload = _read_json(path)
    if not isinstance(payload, Mapping):
        raise RetrievalRuntimeError("model_ready_state_schema_invalid")
    if int(payload.get("schema_version") or 0) < 6:
        raise RetrievalRuntimeError("model_ready_state_schema_version_invalid")
    if payload.get("ready_state_protocol") != MODEL_READY_STATE_PROTOCOL:
        raise RetrievalRuntimeError("model_ready_state_protocol_invalid")
    claimed = str(payload.get("health_sha256") or "").strip().lower()
    unsigned = dict(payload)
    unsigned.pop("health_sha256", None)
    if claimed != canonical_sha256(unsigned):
        raise RetrievalRuntimeError("model_ready_state_sha256_mismatch")
    endpoint = str(payload.get("endpoint_identity_sha256") or "").strip().lower()
    if endpoint != str(expected_endpoint_identity_sha256).strip().lower():
        raise RetrievalRuntimeError("model_ready_state_endpoint_identity_mismatch")
    from .model_admission import operator_admission
    models: list[AppliedReadyModel] = []
    observed_model_ids: set[str] = set()
    for raw in payload.get("models") or ():
        if not isinstance(raw, Mapping):
            raise RetrievalRuntimeError("model_ready_state_record_invalid")
        ready = raw.get("ready_state")
        if not isinstance(ready, Mapping):
            raise RetrievalRuntimeError("model_ready_state_record_missing")
        if ready.get("protocol") != MODEL_READY_STATE_PROTOCOL:
            raise RetrievalRuntimeError("model_ready_state_record_invalid")
        admission = operator_admission(raw, endpoint)
        if ready.get("status") != "ready" and admission is None:
            continue
        resource_id = str(raw.get("resource_id") or "").strip()
        model_id = str(raw.get("model_id") or "").strip()
        if not resource_id or not model_id or model_id in observed_model_ids:
            raise RetrievalRuntimeError("model_ready_state_identity_invalid")
        observed_model_ids.add(model_id)
        modes = tuple(
            sorted(
                {
                    str(item).strip()
                    for item in ready.get("structured_output_modes_live_verified") or ()
                    if str(item).strip()
                }
            )
        )
        capability_statuses = ready.get("capability_statuses")
        if not isinstance(capability_statuses, Mapping):
            capability_statuses = {}
        capabilities = tuple(
            sorted(
                str(name)
                for name, status in capability_statuses.items()
                if str(status) == "live_verified"
            )
        )
        models.append(
            AppliedReadyModel(
                resource_id=resource_id,
                model_id=model_id,
                structured_output_modes_live_verified=modes,
                capabilities_live_verified=capabilities,
                operator_approved_capabilities=tuple(admission["capabilities"]) if admission else (),
                operator_approval_sha256=admission["approval_sha256"] if admission else None,
                capability_evidence_sha256=canonical_sha256(
                    raw.get("capability_evidence") or {}
                ),
            )
        )
    if not models:
        raise RetrievalRuntimeError("applied_model_ready_state_empty")
    return AppliedModelReadyState(
        endpoint_identity_sha256=endpoint,
        health_sha256=claimed,
        generated_at_epoch=float(payload.get("generated_at_epoch") or 0.0),
        models=tuple(sorted(models, key=lambda item: item.resource_id)),
    )


class AppliedReadyStateCapabilityService:
    """Reuse explicit health-apply capability evidence without sending probes."""

    def __init__(
        self,
        ready_state: AppliedModelReadyState,
        *,
        enforcement_policy: str,
    ) -> None:
        self.ready_state = ready_state
        self.enforcement_policy = str(enforcement_policy)

    def probe(
        self,
        *,
        resource_id: str,
        model_id: str,
        requirement: OutputFormatRequirement,
        cost_ledger: RunCostLedger | None = None,
        subtask_id: str | None = None,
        subtask_revision: int | None = None,
        request_fields: Mapping[str, Any] | None = None,
        request_policy_sha256: str | None = None,
    ) -> CapabilityProbeEvidence:
        del cost_ledger, subtask_id, subtask_revision
        model = self.ready_state.by_resource_id.get(str(resource_id))
        if model is None or model.model_id != str(model_id):
            raise ModelResponseContractError("applied_ready_state_model_identity_mismatch")
        manual = model.operator_approval_sha256 is not None
        modes = set(model.structured_output_modes_live_verified)
        if manual:
            modes.update(set(model.operator_approved_capabilities) & {"generic_strict_schema", "json_mode"})
        wire = requirement.portable_wire_schema
        if wire is not None and wire.native_eligible and "generic_strict_schema" in modes:
            selected_mode: Literal[
                "native_strict_schema", "json_object_local_validator"
            ] = "native_strict_schema"
            reason = "applied_ready_state_generic_strict_schema"
        elif "json_mode" in modes:
            selected_mode = "json_object_local_validator"
            reason = "applied_ready_state_json_mode"
        else:
            raise ModelResponseContractError(
                "applied_ready_state_structured_output_unverified"
            )
        checked_at = self.ready_state.generated_at_epoch
        return CapabilityProbeEvidence(
            resource_id=model.resource_id,
            model_id=model.model_id,
            endpoint_identity_sha256=self.ready_state.endpoint_identity_sha256,
            requirement_sha256=requirement.requirement_sha256,
            schema_sha256=str(requirement.schema_sha256),
            wire_schema_protocol=(wire.protocol if wire is not None else None),
            wire_schema_sha256=(wire.wire_schema_sha256 if wire is not None else None),
            input_modality=requirement.input_modality,
            authority_source="operator_approval" if manual else "applied_ready_state",
            outcome="operator_approved" if manual else "live_verified",
            reason_code=reason.replace("applied_ready_state", "operator_approved") if manual else reason,
            checked_at_epoch=checked_at,
            # An applied state is configuration, not a TTL cache. It remains in
            # force until an operator explicitly replaces the file.
            expires_at_epoch=253402300799.0,
            response_sha256=None if manual else model.capability_evidence_sha256,
            message_sha256=model.operator_approval_sha256 if manual else None,
            request_policy_sha256=request_policy_sha256,
            reasoning_effort=(
                str((request_fields or {}).get("reasoning_effort"))
                if (request_fields or {}).get("reasoning_effort") is not None
                else None
            ),
            attempted_enforcement_modes=() if manual else (selected_mode,),
            selected_enforcement_mode=selected_mode,
        )


def _availability_records(
    catalog: Sequence[Mapping[str, Any]],
    effective: Sequence[Mapping[str, Any]],
    health_payload: Mapping[str, Any],
    provider_compatibility: Mapping[str, Any] | None,
    *,
    explicitly_applied_ready_state: bool,
    provider_endpoint_identity_sha256: str | None,
    now_epoch: float,
) -> tuple[AvailabilityRecord, ...]:
    from .model_admission import operator_admission
    effective_ids = {_resource_id(item) for item in effective}
    if "models" not in health_payload or not isinstance(health_payload.get("models"), list):
        raise RetrievalRuntimeError("model_health_schema_invalid")
    try:
        schema_version = int(health_payload.get("schema_version") or 0)
    except (TypeError, ValueError) as exc:
        raise RetrievalRuntimeError("model_health_schema_version_invalid") from exc
    if schema_version >= 6:
        if health_payload.get("ready_state_protocol") != MODEL_READY_STATE_PROTOCOL:
            raise RetrievalRuntimeError("model_ready_state_protocol_invalid")
        claimed_health_sha256 = str(health_payload.get("health_sha256") or "")
        unsigned_health = dict(health_payload)
        unsigned_health.pop("health_sha256", None)
        if claimed_health_sha256 != canonical_sha256(unsigned_health):
            raise RetrievalRuntimeError("model_ready_state_sha256_mismatch")
    health_endpoint = str(
        health_payload.get("endpoint_identity_sha256") or ""
    ).strip().lower()
    expected_endpoint = str(provider_endpoint_identity_sha256 or "").strip().lower()
    expires_at_epoch = health_payload.get("expires_at_epoch")
    # A v6 state in runtime_state is an operator-applied configuration: it
    # remains authoritative until the next explicit apply.  Legacy snapshots
    # retain their time-bounded evidence semantics.
    health_state_authoritative = bool(
        schema_version >= 5
        and expected_endpoint
        and health_endpoint == expected_endpoint
        and isinstance(expires_at_epoch, (int, float))
        and (
            (explicitly_applied_ready_state and schema_version >= 6)
            or float(expires_at_epoch) > float(now_epoch)
        )
    )
    raw_unavailable = (
        health_payload.get("unavailable_model_ids", [])
        if health_state_authoritative
        else []
    )
    if not isinstance(raw_unavailable, list):
        raise RetrievalRuntimeError("model_health_unavailable_ids_invalid")
    unavailable_ids = {
        str(item).strip() for item in raw_unavailable if str(item).strip()
    }
    by_resource: dict[str, Mapping[str, Any]] = {}
    by_model: dict[str, Mapping[str, Any]] = {}
    for item in health_payload.get("models", []) if health_state_authoritative else []:
        if not isinstance(item, Mapping):
            raise RetrievalRuntimeError("model_health_record_invalid")
        resource_id = str(item.get("resource_id") or "").strip()
        model_id = str(item.get("model_id") or "").strip()
        if resource_id:
            if resource_id in by_resource:
                raise RetrievalRuntimeError("model_health_resource_id_duplicate")
            by_resource[resource_id] = item
        if model_id:
            if model_id in by_model:
                raise RetrievalRuntimeError("model_health_model_id_duplicate")
            by_model[model_id] = item

    compatibility = dict(provider_compatibility or {})
    records: list[AvailabilityRecord] = []
    observed_ids: set[str] = set()
    for raw in sorted(catalog, key=_resource_id):
        resource_id = _resource_id(raw)
        resource_type = _resource_type(raw)
        if not resource_id or resource_id in observed_ids:
            raise RetrievalRuntimeError("resource_catalog_identity_invalid")
        if resource_type not in set(FORMAL_TYPE_ORDER):
            raise RetrievalRuntimeError("resource_catalog_type_invalid")
        observed_ids.add(resource_id)
        in_effective = resource_id in effective_ids
        catalog_status = str(raw.get("status") or "active").strip().lower()
        provider_state = _normalize_provider_compatibility(
            compatibility.get(
                resource_id,
                compatibility.get(_model_api_id(raw), "unknown"),
            )
        )
        status: str
        reason: str | None
        if catalog_status not in {"", "active", "available", "ok", "ready"}:
            status, reason = "unavailable", "catalog_inactive"
        elif not in_effective:
            status, reason = "unavailable", "not_in_effective_pool"
        elif resource_type != "Model":
            status, reason = "available", "effective_pool_ready"
        else:
            api_model_id = _model_api_id(raw)
            health = by_resource.get(resource_id) or by_model.get(api_model_id)
            explicit_admission = (operator_admission(health, health_endpoint)
                                  if health is not None and schema_version >= 6 else None)
            if (resource_id in unavailable_ids or api_model_id in unavailable_ids) and explicit_admission is None:
                status, reason = "unavailable", "model_health_unavailable"
            elif health is None:
                status, reason = (
                    "unknown",
                    (
                        "model_health_unprobed"
                        if health_state_authoritative
                        else "model_health_snapshot_stale_or_unbound"
                    ),
                )
            else:
                ready_state = health.get("ready_state")
                if schema_version >= 6:
                    if not isinstance(ready_state, Mapping):
                        raise RetrievalRuntimeError("model_ready_state_record_missing")
                    ready_protocol = str(ready_state.get("protocol") or "")
                    ready_status = str(ready_state.get("status") or "")
                    if ready_protocol != MODEL_READY_STATE_PROTOCOL or ready_status not in {
                        "ready",
                        "blocked",
                        "unavailable",
                        "transient_failure",
                    }:
                        raise RetrievalRuntimeError("model_ready_state_record_invalid")
                    admission = operator_admission(health, health_endpoint)
                    if admission is not None:
                        status, reason = "available", "operator_approved_model_admission"
                    elif ready_status == "ready":
                        status, reason = "available", "model_ready_state_ready"
                    else:
                        status = "unavailable"
                        reason = f"model_ready_state_{ready_status}"
                    records.append(
                        AvailabilityRecord(
                            resource_id=resource_id,
                            resource_type=resource_type,
                            in_effective_pool=in_effective,
                            status=status,
                            reason_code=reason,
                            provider_compatibility=provider_state,
                        )
                    )
                    continue
                health_status = str(health.get("status") or "unknown").strip().lower()
                if health_status == "unavailable":
                    status = "unavailable"
                    reason = str(health.get("error_code") or "model_health_unavailable")
                elif health_status in {"ok", "available", "ready"} and health.get(
                    "text_ok"
                ) is not False:
                    status, reason = "available", "model_health_ok"
                else:
                    status, reason = "unknown", str(
                        health.get("error_code") or "model_health_unknown"
                    )
        records.append(
            AvailabilityRecord(
                resource_id=resource_id,
                resource_type=resource_type,
                in_effective_pool=in_effective,
                status=status,
                reason_code=reason,
                provider_compatibility=provider_state,
            )
        )
    if effective_ids - observed_ids:
        raise RetrievalRuntimeError("effective_pool_contains_unknown_resource")
    return tuple(records)


def build_retrieval_runtime_identity(
    *,
    project_root: str | Path = PROJECT_ROOT,
    provider_compatibility: Mapping[str, Any] | None = None,
    provider_endpoint_identity_sha256: str | None = None,
    now_epoch: float | None = None,
    require_release_sealed: bool = False,
    honor_release_environment: bool = True,
    policy_path: str | Path | None = None,
) -> RetrievalRuntimeIdentity:
    """Validate and freeze all formal retrieval inputs without network access."""

    root = Path(project_root).resolve()
    sealed_local_validation = bool(
        honor_release_environment
        and os.environ.get("SGAR_SEALED_LOCAL_VALIDATION") == "1"
    )
    configured_policy_path = (
        os.environ.get("SGAR_RETRIEVAL_POLICY_PATH")
        if honor_release_environment
        else None
    )
    configured_index_dir = (
        os.environ.get("SGAR_INDEX_DIR") if honor_release_environment else None
    )
    if (configured_policy_path or configured_index_dir) and not sealed_local_validation:
        raise RetrievalRuntimeError(
            "formal_index_environment_override"
            if configured_index_dir
            else "formal_policy_environment_override"
        )
    source_seal = None
    if sealed_local_validation:
        raw_source_seal = os.environ.get("SGAR_SOURCE_SEAL_PATH")
        if not raw_source_seal:
            raise RetrievalRuntimeError("sealed_local_validation_source_seal_missing")
        try:
            source_seal = load_and_verify_source_seal(
                Path(raw_source_seal),
                project_root=root,
                allowed_stages=("release", "activated"),
            )
        except Exception as exc:
            raise RetrievalRuntimeError("sealed_local_validation_source_seal_invalid") from exc
    selected_policy_path = (
        Path(policy_path).resolve()
        if policy_path is not None
        else Path(configured_policy_path).resolve()
        if configured_policy_path
        else root / "sgar_mvp" / "config" / "retrieval_policy.json"
    )
    effective_path = root / "Pool" / "resources" / "json" / "effective_combine.json"
    catalog_path = root / "Pool" / "resources" / "json" / "combine.json"
    health_path = resolve_model_health_state_path(root)
    selected_index_dir = (
        Path(configured_index_dir).resolve()
        if configured_index_dir
        else root / "Pool" / "index_meta"
    )
    index_paths = {
        "capability": selected_index_dir / "faiss_cap.index",
        "constraint": selected_index_dir / "faiss_con.index",
        "metadata": selected_index_dir / "resource_meta.pkl",
    }
    build_manifest_path = selected_index_dir / "index_build_manifest.json"
    required_paths = [selected_policy_path, effective_path, catalog_path, health_path, *index_paths.values()]
    if any(not path.is_file() for path in required_paths):
        raise RetrievalRuntimeError("retrieval_identity_required_file_missing")

    try:
        policy: RetrievalPolicy = load_retrieval_policy(selected_policy_path)
    except Exception as exc:
        raise RetrievalRuntimeError("retrieval_policy_schema_invalid") from exc
    if policy.active_strategy not in {
        "capability_only",
        "capability_constraint_weighted",
    }:
        raise RetrievalRuntimeError("formal_retrieval_strategy_not_supported")
    if require_release_sealed and not policy.release_sealed:
        raise RetrievalRuntimeError("retrieval_configuration_promotion_pending")
    if policy.index_bound:
        if not build_manifest_path.is_file():
            raise RetrievalRuntimeError("retrieval_index_build_manifest_missing")
        manifest = _read_json(build_manifest_path)
        if (
            not isinstance(manifest, Mapping)
            or manifest.get("protocol") != "sgar-retrieval-index-build-v1"
        ):
            raise RetrievalRuntimeError("retrieval_index_build_manifest_invalid")
        claimed_manifest_sha256 = str(manifest.get("manifest_sha256") or "")
        unsigned_manifest = dict(manifest)
        unsigned_manifest.pop("manifest_sha256", None)
        if canonical_sha256(unsigned_manifest) != claimed_manifest_sha256:
            raise RetrievalRuntimeError(
                "retrieval_index_build_manifest_sha256_mismatch"
            )
        if claimed_manifest_sha256 != policy.index_build_manifest_sha256:
            raise RetrievalRuntimeError(
                "retrieval_index_build_manifest_policy_mismatch"
            )
        manifest_source_seal = str(
            (manifest.get("release_source_seal") or {}).get("seal_sha256") or ""
        )
        if policy.local_pool_update:
            if (
                manifest.get("generation_kind") not in {
                    "local_model_pool_update", "local_model_pool_full_rebuild",
                    "local_resource_metadata_update", "local_resource_profile_reembedding",
                    "local_readiness_rebind",
                }
                or manifest.get("release_source_seal") is not None
                or manifest.get("catalog_sha256") != _sha256_file(catalog_path)
                or manifest.get("effective_pool_sha256") != _sha256_file(effective_path)
            ):
                raise RetrievalRuntimeError("local_model_pool_generation_mismatch")
            if source_seal is not None:
                raise RetrievalRuntimeError("local_model_pool_not_a_sealed_release")
        if policy.release_sealed and manifest_source_seal != policy.release_source_seal_sha256:
            raise RetrievalRuntimeError(
                "retrieval_index_release_source_seal_policy_mismatch"
            )
        if source_seal is not None:
            expected_release_seal = (
                source_seal["seal_sha256"]
                if source_seal["stage"] == "release"
                else source_seal.get("parent_release_source_seal_sha256")
            )
            if expected_release_seal != policy.release_source_seal_sha256:
                raise RetrievalRuntimeError(
                    "retrieval_policy_source_seal_runtime_mismatch"
                )
    configured_hyde_model = str(os.environ.get("SGAR_HYDE_MODEL") or "").strip()
    if configured_hyde_model and configured_hyde_model != policy.hyde.api_model_id:
        raise RetrievalRuntimeError("formal_hyde_model_environment_override")
    actual_pool_hash = _sha256_file(effective_path)
    if actual_pool_hash != policy.effective_pool_sha256:
        raise RetrievalRuntimeError("retrieval_effective_pool_sha256_mismatch")
    components = tuple(
        NamedSha256(name=name, sha256=_sha256_file(path))
        for name, path in index_paths.items()
    )
    for item in components:
        if policy.index_sha256.get(item.name) != item.sha256:
            raise RetrievalRuntimeError(f"retrieval_{item.name}_index_sha256_mismatch")
    if policy.index_bound:
        manifest_files = dict(manifest.get("files_sha256") or {})
        expected_manifest_files = {
            "faiss_cap.index": policy.index_sha256["capability"],
            "faiss_con.index": policy.index_sha256["constraint"],
            "resource_meta.pkl": policy.index_sha256["metadata"],
        }
        if any(
            manifest_files.get(name) != sha256
            for name, sha256 in expected_manifest_files.items()
        ):
            raise RetrievalRuntimeError(
                "retrieval_index_build_manifest_file_mismatch"
            )

    policy_quotas = {**policy.initial_quotas(), "Device": 0}
    if policy_quotas != dict(FORMAL_TYPED_QUOTAS):
        raise RetrievalRuntimeError("retrieval_policy_typed_quotas_not_formal")
    catalog = _read_json(catalog_path)
    effective = _read_json(effective_path)
    health = _read_json(health_path)
    if not isinstance(catalog, list) or not all(isinstance(item, Mapping) for item in catalog):
        raise RetrievalRuntimeError("resource_catalog_schema_invalid")
    if not isinstance(effective, list) or not all(isinstance(item, Mapping) for item in effective):
        raise RetrievalRuntimeError("effective_pool_schema_invalid")
    if not isinstance(health, Mapping):
        raise RetrievalRuntimeError("model_health_schema_invalid")
    from .model_selection import require_registered_models
    require_registered_models(catalog, root=root, complete=True)
    require_registered_models(effective, root=root)
    catalog_by_id = {_resource_id(item): item for item in catalog}
    effective_ids = [_resource_id(item) for item in effective]
    if (
        any(not resource_id for resource_id in effective_ids)
        or len(effective_ids) != len(set(effective_ids))
    ):
        raise RetrievalRuntimeError("effective_pool_identity_invalid")
    for item in effective:
        resource_id = _resource_id(item)
        catalog_item = catalog_by_id.get(resource_id)
        if catalog_item is None:
            raise RetrievalRuntimeError("effective_pool_contains_unknown_resource")
        if canonical_sha256(item) != canonical_sha256(catalog_item):
            raise RetrievalRuntimeError("effective_pool_catalog_content_mismatch")
    validate_required_dependency_graph(effective)
    availability = _availability_records(
        catalog,
        effective,
        health,
        provider_compatibility,
        explicitly_applied_ready_state=(
            health_path
            == root / "sgar_mvp" / "runtime_state" / "model_ready_state.json"
        ),
        provider_endpoint_identity_sha256=provider_endpoint_identity_sha256,
        now_epoch=(time.time() if now_epoch is None else float(now_epoch)),
    )
    index_hash = canonical_sha256({item.name: item.sha256 for item in components})
    try:
        import pickle

        with index_paths["metadata"].open("rb") as handle:
            index_metadata = pickle.load(handle)
        embedding_configuration_sha256 = str(
            (index_metadata.get("embedding_runtime_config") or {}).get(
                "configuration_sha256"
            )
            or ""
        )
        embedding_config = dict(index_metadata.get("embedding_runtime_config") or {})
        embedding_identity_v2 = dict(
            index_metadata.get("embedding_runtime_identity_v2") or {}
        )
        index_meta_v2 = dict(index_metadata.get("index_meta_v2") or {})
        if policy.index_bound:
            if embedding_config.get("candidate_id") != policy.embedding_candidate_id:
                raise RetrievalRuntimeError("retrieval_embedding_candidate_mismatch")
            if embedding_config.get("model_id") != policy.embedding_model:
                raise RetrievalRuntimeError("retrieval_embedding_model_mismatch")
            if (
                embedding_config.get("capability_query_instruction")
                != policy.bge_prefix
            ):
                raise RetrievalRuntimeError("retrieval_embedding_instruction_mismatch")
            if (
                embedding_identity_v2.get("identity_sha256")
                != policy.embedding_runtime_identity_sha256
            ):
                raise RetrievalRuntimeError(
                    "retrieval_embedding_runtime_identity_mismatch"
                )
            if index_meta_v2.get("index_meta_sha256") != policy.index_meta_sha256:
                raise RetrievalRuntimeError("retrieval_index_meta_identity_mismatch")
            if (
                (index_meta_v2.get("embedding_runtime_identity") or {}).get(
                    "identity_sha256"
                )
                != policy.embedding_runtime_identity_sha256
            ):
                raise RetrievalRuntimeError(
                    "retrieval_index_embedding_identity_mismatch"
                )
    except Exception as exc:
        if isinstance(exc, RetrievalRuntimeError):
            raise
        raise RetrievalRuntimeError("retrieval_metadata_identity_invalid") from exc
    profiler_requirement = system_role_requirement("hyde")
    return RetrievalRuntimeIdentity(
        pool_sha256=actual_pool_hash,
        index_sha256=index_hash,
        index_components=components,
        policy_sha256=policy.sha256(),
        availability_sha256=canonical_sha256(availability),
        availability_records=availability,
        active_strategy=policy.active_strategy,
        typed_quotas=tuple(
            TypedQuota(resource_type=resource_type, quota=FORMAL_TYPED_QUOTAS[resource_type])
            for resource_type in FORMAL_TYPE_ORDER
        ),
        profile_version=policy.profile_version,
        embedding_model=policy.embedding_model,
        bge_prefix=policy.bge_prefix,
        embedding_configuration_sha256=embedding_configuration_sha256,
        hyde_resource_id=policy.hyde.resource_id,
        hyde_api_model_id=policy.hyde.api_model_id,
        hyde_prompt_version=policy.hyde.prompt_version,
        hyde_temperature=policy.hyde.temperature,
        hyde_max_tokens=policy.hyde.max_tokens,
        hyde_reasoning_effort=policy.hyde.reasoning_effort,
        profiler_schema_sha256=profiler_requirement.wire_schema_sha256,
        internal_language_policy_sha256=INTERNAL_LANGUAGE_POLICY.policy_sha256,
    )


def validate_loaded_retrieval_backend(
    identity: RetrievalRuntimeIdentity,
    *,
    resource_index: Mapping[str, Mapping[str, Any]] | None = None,
    project_root: str | Path = PROJECT_ROOT,
    backend: Any | None = None,
    policy_path: str | Path | None = None,
) -> None:
    """Bind the lazy retrieval backend to the frozen runtime identity.

    ``retrieve.py`` is imported lazily because loading FAISS and BGE is
    expensive.  This closes that initialization boundary: a policy,
    environment override, index, or pool change between identity construction
    and backend loading cannot silently enter a formal run.
    """

    root = Path(project_root).resolve()
    if policy_path is not None:
        bind_retrieval_policy_path(policy_path)
    loaded = backend if backend is not None else importlib.import_module("retrieve")
    backend_file = getattr(loaded, "__file__", None)
    try:
        loaded_backend_path = Path(str(backend_file)).resolve()
    except (OSError, TypeError) as exc:
        raise RetrievalRuntimeError("loaded_backend_module_mismatch") from exc
    if backend_file is None or loaded_backend_path != (root / "retrieve.py").resolve():
        raise RetrievalRuntimeError("loaded_backend_module_mismatch")
    policy = getattr(loaded, "RETRIEVAL_POLICY", None)
    if not isinstance(policy, RetrievalPolicy):
        raise RetrievalRuntimeError("loaded_policy_type_identity_mismatch")
    if policy.sha256() != identity.policy_sha256:
        raise RetrievalRuntimeError("loaded_policy_content_mismatch")

    accounting_types = {
        "RunCostLedger": RunCostLedger,
        "BudgetControlError": BudgetControlError,
        "ModelAccountingError": ModelAccountingError,
    }
    if any(getattr(loaded, name, None) is not expected for name, expected in accounting_types.items()):
        raise RetrievalRuntimeError("loaded_accounting_type_identity_mismatch")
    if getattr(loaded, "ModelTransportError", None) is not ModelTransportError:
        raise RetrievalRuntimeError("loaded_transport_type_identity_mismatch")

    expected_scalars = {
        "EMBED_MODEL": identity.embedding_model,
        "BGE_PREFIX": identity.bge_prefix,
        "HYDE_MODEL": identity.hyde_api_model_id,
        "HYDE_PROFILE_VERSION": identity.hyde_prompt_version,
    }
    if any(
        getattr(loaded, name, None) != expected
        for name, expected in expected_scalars.items()
    ):
        raise RetrievalRuntimeError("loaded_retrieval_backend_configuration_mismatch")

    configured_index_dir = os.environ.get("SGAR_INDEX_DIR")
    sealed_local_validation = os.environ.get("SGAR_SEALED_LOCAL_VALIDATION") == "1"
    if configured_index_dir and not sealed_local_validation:
        raise RetrievalRuntimeError("formal_index_environment_override")
    selected_index_dir = (
        Path(configured_index_dir).resolve()
        if configured_index_dir
        else root / "Pool" / "index_meta"
    )
    index_paths = {
        "capability": selected_index_dir / "faiss_cap.index",
        "constraint": selected_index_dir / "faiss_con.index",
        "metadata": selected_index_dir / "resource_meta.pkl",
    }
    backend_paths = {
        "capability": getattr(loaded, "CAP_INDEX_FILE", None),
        "constraint": getattr(loaded, "CON_INDEX_FILE", None),
        "metadata": getattr(loaded, "METADATA_FILE", None),
    }
    component_hashes = {item.name: item.sha256 for item in identity.index_components}
    for name, expected_path in index_paths.items():
        try:
            loaded_path = Path(backend_paths[name]).resolve()
        except (OSError, TypeError) as exc:
            raise RetrievalRuntimeError("loaded_retrieval_index_path_invalid") from exc
        if loaded_path != expected_path.resolve():
            raise RetrievalRuntimeError("loaded_retrieval_index_path_mismatch")
        if _sha256_file(loaded_path) != component_hashes[name]:
            raise RetrievalRuntimeError("loaded_retrieval_index_content_mismatch")

    metadata_reader = getattr(loaded, "get_index_metadata", None)
    if not callable(metadata_reader):
        raise RetrievalRuntimeError("loaded_retrieval_metadata_reader_missing")
    metadata = metadata_reader()
    if (
        not isinstance(metadata, Mapping)
        or metadata.get("profile_version") != identity.profile_version
    ):
        raise RetrievalRuntimeError("loaded_retrieval_profile_version_mismatch")

    effective_path = root / "Pool" / "resources" / "json" / "effective_combine.json"
    if _sha256_file(effective_path) != identity.pool_sha256:
        raise RetrievalRuntimeError("loaded_effective_pool_identity_mismatch")
    if resource_index is None:
        return
    effective = _read_json(effective_path)
    if not isinstance(effective, list) or not all(
        isinstance(item, Mapping) for item in effective
    ):
        raise RetrievalRuntimeError("effective_pool_schema_invalid")
    effective_by_id = {_resource_id(item): item for item in effective}
    for resource_id, raw in resource_index.items():
        expected = effective_by_id.get(resource_id)
        if expected is None or canonical_sha256(raw) != canonical_sha256(expected):
            raise RetrievalRuntimeError("loaded_resource_content_identity_mismatch")


class PublicContextDescriptor(FrozenContract):
    logical_name: str = Field(min_length=1)
    source_name: str | None = None
    artifact_type: str = Field(min_length=1)
    sha256: str
    coverage_status: Literal["complete", "partial", "handle_only"] = "handle_only"
    original_bytes: int | None = Field(default=None, ge=0)
    included_bytes: int | None = Field(default=None, ge=0)
    included_content_sha256: str | None = None
    handle_available: bool = True
    content_acquisition_required: bool = True
    container_inventory: dict[str, Any] = Field(default_factory=dict)

    @model_serializer(mode="wrap")
    def _serialize_observations(self, handler):
        result = handler(self)
        if not self.container_inventory:
            result.pop("container_inventory", None)
        return result

    @field_validator("logical_name")
    @classmethod
    def _logical_name_is_host_free(cls, value: str) -> str:
        normalized = value.strip()
        if (
            not normalized
            or normalized.startswith(("/", "\\", "file:"))
            or re.match(r"^[a-zA-Z]:[\\/]", normalized)
        ):
            raise ValueError("public_context_logical_name_not_portable")
        return normalized

    @field_validator("sha256", "included_content_sha256")
    @classmethod
    def _valid_hash(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
            raise ValueError("public_context_sha256_invalid")
        return normalized


class ProducedFileProjection(FrozenContract):
    path_hint: str
    artifact_type: str
    required: bool
    schema_hint: Any = None

    @field_validator("schema_hint", mode="before")
    @classmethod
    def _canonical_schema(cls, value: Any) -> Any:
        return _canonical_json_value(value)


from .evidence_requirements import EvidenceSourceDeclaration


class RetrievalContractProjection(FrozenContract, EvidenceSourceDeclaration):
    protocol: Literal[RETRIEVAL_RUNTIME_PROTOCOL] = RETRIEVAL_RUNTIME_PROTOCOL
    revision: SubtaskRevisionRef
    description: str
    expected_output: str
    artifact_type: str
    output_extension: str
    required_content: tuple[str, ...] = ()
    produced_files: tuple[ProducedFileProjection, ...] = ()
    json_schema: dict[str, Any] | None = None
    interface_contract: dict[str, Any] = Field(default_factory=dict)
    grounding_requirements: tuple[str, ...] = ()
    required_operation_kinds: tuple[str, ...] = ()
    evidence_acquisition_operations: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()
    downstream_consumers: tuple[str, ...] = ()
    dag_edge_contract_sha256s: tuple[str, ...] = ()
    dependency_inputs: tuple[dict[str, Any], ...] = ()
    public_context_descriptors: tuple[PublicContextDescriptor, ...] = ()
    role_intent: str = ""
    semantic_contract_v2: NodeSemanticContractV2 | None = None
    semantic_edges_v2: tuple[SemanticEdgeContractV2, ...] = ()
    planning_execution_mode: str | None = None
    planner_capability_evidence: tuple[str, ...] = ()
    planner_capability_gap: str | None = None
    semantic_requirements: tuple[SemanticRequirementDeclarationV1, ...] = ()
    execution_requirements: tuple[ExecutionResourceRequirementV1, ...] = ()
    contract_sha256: str = ""

    @field_validator("interface_contract", mode="before")
    @classmethod
    def _canonical_interface(cls, value: Any) -> dict[str, Any]:
        canonical = _canonical_json_value(value or {})
        if not isinstance(canonical, dict):
            raise ValueError("retrieval_interface_contract_must_be_object")
        return cast(dict[str, Any], canonical)

    @model_serializer(mode="wrap")
    def _serialize_operation_origins(self, handler: Any) -> dict[str, Any]:
        value = handler(self)
        if self.evidence_source_scope is None:
            value.pop("evidence_source_scope", None)
        if self.external_acquisition_mode is None:
            value.pop("external_acquisition_mode", None)
        if self.external_discovery_mode is None:
            value.pop("external_discovery_mode", None)
        if not self.evidence_acquisition_operations:
            value.pop("evidence_acquisition_operations", None)
        return value

    @field_validator("json_schema", mode="before")
    @classmethod
    def _canonical_json_schema(cls, value: Any) -> dict[str, Any] | None:
        if value is None:
            return None
        canonical = _canonical_json_value(value)
        if not isinstance(canonical, dict):
            raise ValueError("retrieval_json_schema_must_be_object")
        return canonical

    @model_validator(mode="after")
    def _seal_contract(self) -> "RetrievalContractProjection":
        descriptors = list(self.public_context_descriptors)
        descriptor_keys = [(item.logical_name, item.artifact_type, item.sha256) for item in descriptors]
        if descriptor_keys != sorted(descriptor_keys) or len(descriptor_keys) != len(
            set(descriptor_keys)
        ):
            raise ValueError("public_context_descriptors_not_unique_sorted")
        if self.dag_edge_contract_sha256s != tuple(
            sorted(set(self.dag_edge_contract_sha256s))
        ):
            raise ValueError("retrieval_edge_contract_hashes_not_unique_sorted")
        projection = self.model_dump(mode="python", exclude={"contract_sha256"})
        expected = canonical_sha256(projection)
        if self.contract_sha256 and self.contract_sha256.strip().lower() != expected:
            raise ValueError("retrieval_contract_sha256_mismatch")
        object.__setattr__(self, "contract_sha256", expected)
        return self


def project_retrieval_contract(
    revision: SubtaskRevisionRef,
    subtask: Subtask,
    *,
    public_context: Sequence[Mapping[str, Any] | PublicContextDescriptor] | None = None,
) -> RetrievalContractProjection:
    if subtask.id != revision.subtask_id:
        raise RetrievalRuntimeError("retrieval_revision_subtask_mismatch")
    try:
        validate_planner_subtask_contract(subtask)
    except PlannerContractConflict as exc:
        raise RetrievalRuntimeError("planner_contract_conflict") from exc
    except Exception as exc:
        raise RetrievalRuntimeError("planner_contract_projection_failure") from exc
    descriptors: list[PublicContextDescriptor] = []
    for item in public_context or ():
        if isinstance(item, PublicContextDescriptor):
            descriptor = item
        elif isinstance(item, Mapping):
            prohibited = {
                "path",
                "host_path",
                "tool_path",
                "absolute_path",
                "content",
                "secret",
            }
            if prohibited & {str(key) for key in item}:
                raise RetrievalRuntimeError("public_context_descriptor_contains_private_field")
            descriptor = PublicContextDescriptor(
                logical_name=str(item.get("logical_name") or item.get("name") or ""),
                source_name=(
                    str(item.get("source_name") or "").strip() or None
                ),
                artifact_type=str(item.get("artifact_type") or item.get("kind") or "unknown"),
                sha256=str(item.get("sha256") or ""),
                coverage_status=str(item.get("coverage_status") or "handle_only"),
                original_bytes=item.get("original_bytes"),
                included_bytes=item.get("included_bytes"),
                included_content_sha256=item.get("included_content_sha256"),
                handle_available=bool(item.get("handle_available", True)),
                content_acquisition_required=item.get(
                    "content_acquisition_required", True
                ),
                container_inventory=dict(item.get("container_inventory") or {}),
            )
        else:
            raise RetrievalRuntimeError("public_context_descriptor_invalid")
        descriptors.append(descriptor)
    descriptors.sort(key=lambda item: (item.logical_name, item.artifact_type, item.sha256))

    contract = subtask.output_contract
    semantic_v2 = subtask.semantic_contract_v2
    semantic_dependency_inputs = (
        tuple(
            item.model_dump(mode="json")
            for item in semantic_v2.authorized_inputs
            if item.source == "node_output"
        )
        if semantic_v2 is not None
        else ()
    )
    text_parts = [str(subtask.description), str(subtask.expected_output)]
    if contract is not None:
        text_parts.extend(str(item) for item in contract.required_content)
        text_parts.extend(str(item) for item in contract.acceptance_criteria)
        text_parts.extend(str(item) for item in contract.grounding_requirements)
    # Lexical action matches reserve useful candidates in _required_tool_operations.
    # They do not authorize a mandatory execution primitive: a composed script,
    # model or Controller may satisfy the same task semantics. Preserve actual
    # material/evidence requirements below and explicit execution_requirements.
    required_operations: set[str] = set()
    # A declared text-like input whose bytes are available only by handle
    # needs an executable content-acquisition route.  Describing the handle
    # to Planner does not put the file contents into a downstream Model call.
    # Reserve one read capability before the pool is frozen, independent of
    # vector top-k and without requiring the Planner to use a magic phrase.
    if any(
        item.handle_available
        and item.content_acquisition_required
        and item.coverage_status != "complete"
        and item.artifact_type in {"plaintext", "markdown", "json", "csv", "code"}
        and (item.original_bytes is None or item.original_bytes <= 256 * 1024)
        for item in descriptors
    ):
        required_operations.add("read_text_file")
    if any(
        item.handle_available
        and item.coverage_status != "complete"
        and item.artifact_type in {"xlsx", "spreadsheet"}
        for item in descriptors
    ):
        required_operations.add("load_xlsx_read_only")
    if any(
        item.required
        and item.relation == "direct_executor"
        and item.resource_type == "Tool"
        and item.operation_id is None
        for item in subtask.execution_requirements
    ):
        required_operations.update(
            normalize_task_capability_operations("\n".join(text_parts))
        )
    grounding = tuple(contract.grounding_requirements if contract is not None else ())
    has_authorized_materials = bool(
        descriptors or semantic_dependency_inputs or subtask.dependency_inputs
    )
    grounding_text = "\n".join(
        [str(subtask.description), str(subtask.expected_output), *text_parts[2:], *grounding]
    )
    acquisition_operations: set[str] = set()
    if requires_external_grounding(
        grounding_text,
        has_authorized_materials=has_authorized_materials,
        declared_grounding=bool(grounding),
        evidence_source_scope=getattr(contract, "evidence_source_scope", None),
    ):
        # Search snippets identify candidate sources but do not establish the
        # contents of a source. Require the plan to acquire source content
        # before a grounded answer is presented as verified.
        # This is an evidence duty, not a user-bound choice of an API family.
        # Retrieval still reserves specialist tools; a compatible executable
        # composition may acquire the same evidence. Explicit resource/method
        # requirements remain in required_operations and execution_requirements.
        acquisition_operations.add("fetch_web_resource")
        if not (has_authorized_materials and requests_external_content(grounding_text)):
            acquisition_operations.add("search_web")
    return RetrievalContractProjection(
        revision=revision,
        description=(semantic_v2.task if semantic_v2 is not None else str(subtask.description)),
        expected_output=(
            semantic_v2.output.semantic_description
            if semantic_v2 is not None
            else str(subtask.expected_output)
        ),
        artifact_type=(
            semantic_v2.output.artifact_type
            if semantic_v2 is not None
            else contract.artifact_type.value if contract is not None else subtask.artifact_type.value
        ),
        output_extension=str(subtask.output_extension or ""),
        required_content=tuple(contract.required_content if contract is not None else ()),
        produced_files=tuple(
            ProducedFileProjection(
                path_hint=item.path_hint,
                artifact_type=item.artifact_type,
                required=item.required,
                schema_hint=item.schema_hint,
            )
            for item in (contract.produced_files if contract is not None else ())
        ),
        json_schema=(
            dict(contract.json_schema)
            if contract is not None and contract.json_schema is not None
            else None
        ),
        interface_contract=dict(contract.interface_contract if contract is not None else {}),
        grounding_requirements=grounding,
        evidence_source_scope=getattr(contract, "evidence_source_scope", None),
        external_acquisition_mode=getattr(contract, "external_acquisition_mode", None),
        external_discovery_mode=getattr(contract, "external_discovery_mode", None),
        required_operation_kinds=tuple(sorted(required_operations)),
        evidence_acquisition_operations=tuple(sorted(acquisition_operations)),
        acceptance_criteria=(
            tuple(semantic_v2.acceptance_conditions)
            if semantic_v2 is not None
            else tuple(contract.acceptance_criteria if contract is not None else ())
        ),
        downstream_consumers=tuple(
            contract.downstream_consumers if contract is not None else ()
        ),
        dag_edge_contract_sha256s=tuple(
            sorted(
                edge.edge_contract_sha256
                for edge in subtask.incoming_edge_contracts
            )
        ),
        dependency_inputs=(
            tuple(_canonical_json_value(item) for item in semantic_dependency_inputs)
            if semantic_v2 is not None
            else tuple(
                _canonical_json_value(item.model_dump(mode="json"))
                for item in subtask.dependency_inputs
            )
        ),
        public_context_descriptors=tuple(descriptors),
        role_intent=(semantic_v2.role_intent if semantic_v2 is not None else subtask.role),
        semantic_contract_v2=semantic_v2,
        semantic_edges_v2=tuple(subtask.incoming_semantic_edges_v2),
        planning_execution_mode=(
            subtask.planning_execution_mode.value
            if subtask.planning_execution_mode is not None
            else None
        ),
        planner_capability_evidence=tuple(
            dict.fromkeys(str(item) for item in subtask.capability_evidence)
        ),
        planner_capability_gap=(
            str(subtask.capability_gap).strip()
            if str(subtask.capability_gap or "").strip()
            else None
        ),
        semantic_requirements=(
            () if semantic_v2 is not None else tuple(subtask.semantic_requirements)
        ),
        execution_requirements=tuple(subtask.execution_requirements),
    )


def explicit_hard_requirements(
    projection: RetrievalContractProjection,
) -> dict[str, Any]:
    """Extract hard gates only from explicit structured contract fields."""

    interface = projection.interface_contract
    allowed = (
        "required_model_features",
        "input_modalities",
        "output_modalities",
        "min_context_tokens",
        "required_runtime",
        "input_kinds",
        "prohibited_licenses",
        "minimum_trust",
    )
    result = {key: interface[key] for key in allowed if key in interface}
    if projection.public_context_descriptors:
        result["public_input_artifact_types"] = sorted(
            {item.artifact_type for item in projection.public_context_descriptors}
        )
    return _canonical_json_value(result)


def ideal_profile_input_envelope(
    projection: RetrievalContractProjection,
) -> ProfilerInputEnvelopeV1:
    """Build the pool-blind typed Profiler input from Planner contracts."""

    return ProfilerInputEnvelopeV1(
        revision=projection.revision.model_dump(mode="json"),
        subtask=ProfilerSubtaskContractV1(
            role_intent=projection.role_intent,
            description=projection.description,
            expected_output=projection.expected_output,
            execution_mode=projection.planning_execution_mode,
        ),
        semantic_requirements=tuple(
            item.model_dump(mode="json") for item in projection.semantic_requirements
        ),
        execution_requirements=tuple(
            item.model_dump(mode="json") for item in projection.execution_requirements
        ),
        materials=tuple(
            ProfilerMaterialDescriptorV1(
                logical_name=item.logical_name,
                source_name=item.source_name,
                artifact_type=item.artifact_type,
                content_sha256=item.sha256,
                coverage_status=item.coverage_status,
                original_bytes=item.original_bytes,
                included_bytes=item.included_bytes,
                included_content_sha256=item.included_content_sha256,
                handle_available=item.handle_available,
                container_inventory=item.container_inventory,
            )
            for item in projection.public_context_descriptors
        ),
        dag_inputs=projection.dependency_inputs,
        output_contract={
            "artifact_type": projection.artifact_type,
            "required_effect": (
                projection.semantic_contract_v2.required_effect
                if projection.semantic_contract_v2 is not None else "none"
            ),
            "output_extension": projection.output_extension,
            "required_content": list(projection.required_content),
            "produced_files": [
                item.model_dump(mode="json") for item in projection.produced_files
            ],
            "json_schema": None,
            "interface_contract": projection.interface_contract,
            "grounding_requirements": list(projection.grounding_requirements),
            **({"evidence_source_scope": projection.evidence_source_scope}
               if projection.evidence_source_scope is not None else {}),
            **({"external_acquisition_mode": projection.external_acquisition_mode}
               if projection.external_acquisition_mode is not None else {}),
            **({"external_discovery_mode": projection.external_discovery_mode}
               if projection.external_discovery_mode is not None else {}),
            "acceptance_criteria": list(projection.acceptance_criteria),
            "downstream_consumers": list(projection.downstream_consumers),
        },
        contract_sha256=projection.contract_sha256,
    )


def ideal_profile_query_text(projection: RetrievalContractProjection) -> str:
    """Canonical typed user data for one Profiler call."""

    envelope = ideal_profile_input_envelope(projection)
    return canonical_json_bytes(envelope.model_dump(mode="json")).decode("utf-8")


class IdealResourceProfileArtifact(FrozenContract):
    protocol: Literal[RETRIEVAL_RUNTIME_PROTOCOL] = RETRIEVAL_RUNTIME_PROTOCOL
    revision: SubtaskRevisionRef
    contract_sha256: str
    raw_query_text: str
    capability_text: str = Field(min_length=1)
    constraint_text: str = Field(min_length=1)
    think: str = Field(min_length=1)
    explicit_hard_requirements: dict[str, Any] = Field(default_factory=dict)
    prompt_version: str = Field(min_length=1)
    prompt_sha256: str
    profile_sha256: str = ""
    model_accounting_reference: dict[str, Any] | None = None

    @field_validator("explicit_hard_requirements", mode="before")
    @classmethod
    def _canonical_requirements(cls, value: Any) -> dict[str, Any]:
        canonical = _canonical_json_value(value or {})
        if not isinstance(canonical, dict):
            raise ValueError("explicit_hard_requirements_must_be_object")
        return canonical

    @field_validator("contract_sha256", "prompt_sha256")
    @classmethod
    def _valid_hash(cls, value: str, info: Any) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
            raise ValueError(f"{info.field_name}_invalid")
        return normalized

    @model_validator(mode="after")
    def _seal_profile(self) -> "IdealResourceProfileArtifact":
        projection = self.model_dump(
            mode="python",
            exclude={"profile_sha256", "model_accounting_reference"},
        )
        expected = canonical_sha256(projection)
        if self.profile_sha256 and self.profile_sha256.strip().lower() != expected:
            raise ValueError("ideal_resource_profile_sha256_mismatch")
        object.__setattr__(self, "profile_sha256", expected)
        return self


class EncodedIdealResourceProfile(FrozenContract):
    artifact: IdealResourceProfileArtifact
    capability_vector: tuple[float, ...]
    constraint_vector: tuple[float, ...] | None = None
    raw_query_vector: tuple[float, ...] | None = None
    dimension: int = Field(gt=0)
    retrieval_attempts: tuple[RetrievalAttemptRecord, ...]

    @field_validator("capability_vector")
    @classmethod
    def _finite_vector(cls, value: tuple[float, ...]) -> tuple[float, ...]:
        if not value or any(not math.isfinite(float(item)) for item in value):
            raise ValueError("retrieval_profile_vector_invalid")
        return tuple(float(item) for item in value)

    @field_validator("constraint_vector", "raw_query_vector")
    @classmethod
    def _finite_optional_vector(
        cls, value: tuple[float, ...] | None
    ) -> tuple[float, ...] | None:
        if value is None:
            return None
        return cls._finite_vector(value)

    @model_validator(mode="after")
    def _validate_dimensions(self) -> "EncodedIdealResourceProfile":
        if any(
            len(vector) != self.dimension
            for vector in (
                self.capability_vector,
                self.constraint_vector,
                self.raw_query_vector,
            )
            if vector is not None
        ):
            raise ValueError("retrieval_profile_vector_dimension_mismatch")
        if not self.retrieval_attempts or self.retrieval_attempts[-1].outcome is not RetrievalAttemptOutcome.SUCCESS:
            raise ValueError("encoded_profile_requires_successful_retrieval_attempt")
        return self

    def as_query_profile(self) -> QueryRetrievalProfile:
        metadata: dict[str, Any] = {
            "status": "generated",
            "prompt_version": self.artifact.prompt_version,
            "profile_sha256": self.artifact.profile_sha256,
            "think_sha256": hashlib.sha256(
                self.artifact.think.encode("utf-8")
            ).hexdigest(),
        }
        if self.artifact.model_accounting_reference is not None:
            metadata["model_accounting_reference"] = _canonical_json_value(
                self.artifact.model_accounting_reference
            )
        return QueryRetrievalProfile(
            capability=Vector(embedding=list(self.capability_vector), dim=self.dimension),
            constraint=(
                Vector(embedding=list(self.constraint_vector), dim=self.dimension)
                if self.constraint_vector is not None
                else None
            ),
            raw_query=(
                Vector(embedding=list(self.raw_query_vector), dim=self.dimension)
                if self.raw_query_vector is not None
                else None
            ),
            capability_text=self.artifact.capability_text,
            constraint_text=self.artifact.constraint_text,
            raw_query_text=self.artifact.raw_query_text,
            hard_requirements=dict(self.artifact.explicit_hard_requirements),
            profile_version=self.artifact.prompt_version,
            generation_metadata=metadata,
        )


class CandidateCompatibilityDecision(FrozenContract):
    resource_id: str = Field(min_length=1)
    resource_type: str = Field(min_length=1)
    verdict: Literal["compatible", "conditional", "unknown", "incompatible"]
    reason_codes: tuple[str, ...] = ()


class CandidateScoreEvidence(FrozenContract):
    resource_id: str = Field(min_length=1)
    resource_type: str = Field(min_length=1)
    query_role: Literal["base", "dependency_slot", "agent_base_model"]
    rank: int = Field(ge=1)
    score: float
    capability_score: float
    constraint_score: float | None = None
    parent_resource_id: str | None = None
    dependency_slot: str | None = None

    @field_validator("score", "capability_score", "constraint_score")
    @classmethod
    def _finite_score(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if not math.isfinite(float(value)):
            raise ValueError("candidate_score_must_be_finite")
        return float(value)

class CandidateDependencyEdge(FrozenContract):
    parent_resource_id: str = Field(min_length=1)
    child_resource_id: str = Field(min_length=1)
    requirement_kind: Literal["explicit_id", "dependency_slot", "agent_base_model"]
    required: Literal[True] = True
    dependency_slot: str | None = None
    child_resource_type: str = Field(min_length=1)
    rank: int = Field(ge=1)

    @model_validator(mode="after")
    def _validate_slot(self) -> "CandidateDependencyEdge":
        if self.requirement_kind == "dependency_slot" and not self.dependency_slot:
            raise ValueError("dependency_slot_edge_requires_slot")
        return self


class OptionalDependencyHint(FrozenContract):
    parent_resource_id: str = Field(min_length=1)
    hint_kind: Literal[
        "optional_resource_id",
        "recommended_dependency_id",
        "allowed_dependency_id",
        "optional_dependency_slot",
    ]
    resource_id: str | None = None
    dependency_slot: str | None = None
    description: str | None = None
    allowed_types: tuple[str, ...] = ()


class DependencyRejection(FrozenContract):
    parent_resource_id: str = Field(min_length=1)
    parent_resource_type: str = Field(min_length=1)
    reason_code: str = Field(min_length=1)
    required_resource_id: str | None = None
    dependency_slot: str | None = None


class TypeQuotaEvidence(FrozenContract):
    resource_type: str = Field(min_length=1)
    quota: int = Field(ge=0)
    eligible_count: int = Field(ge=0)
    base_count: int = Field(ge=0)
    final_count: int = Field(ge=0)
    shortfall: int = Field(ge=0)
    quota_coverage: bool

    @model_validator(mode="after")
    def _validate_counts(self) -> "TypeQuotaEvidence":
        if self.base_count > self.final_count:
            raise ValueError("base_candidate_count_exceeds_final_count")
        expected = self.base_count >= min(self.quota, self.eligible_count)
        if self.quota_coverage != expected:
            raise ValueError("quota_coverage_value_mismatch")
        if self.shortfall != max(self.quota - self.base_count, 0):
            raise ValueError("quota_shortfall_value_mismatch")
        return self


class LocalEncodingAttempt(FrozenContract):
    operation: Literal["dependency_slot", "agent_base_model"]
    operation_key: str = Field(min_length=1)
    attempt: int = Field(ge=1, le=3)
    outcome: Literal["success", "infrastructure_failure", "terminal_failure"]
    failure_responsibility: str | None = None
    failure_code: str | None = None

    @model_validator(mode="after")
    def _validate_failure(self) -> "LocalEncodingAttempt":
        if self.outcome == "success":
            if self.failure_responsibility is not None or self.failure_code is not None:
                raise ValueError("successful_local_encoding_has_failure")
        elif not self.failure_responsibility or not self.failure_code:
            raise ValueError("failed_local_encoding_requires_structured_failure")
        return self


class FrozenCandidatePoolResult(FrozenContract):
    protocol: Literal[RETRIEVAL_RUNTIME_PROTOCOL] = RETRIEVAL_RUNTIME_PROTOCOL
    runtime_identity: RetrievalRuntimeIdentity
    contract_projection: RetrievalContractProjection
    ideal_resource_profile: IdealResourceProfileArtifact
    retrieval_attempts: tuple[RetrievalAttemptRecord, ...]
    candidate_pool_snapshot: CandidatePoolSnapshot
    base_candidate_ids_by_type: dict[str, tuple[str, ...]]
    compiler_priority_candidate_ids: tuple[str, ...] = ()
    type_quota_evidence: tuple[TypeQuotaEvidence, ...]
    candidate_score_evidence: tuple[CandidateScoreEvidence, ...]
    dependency_edges: tuple[CandidateDependencyEdge, ...]
    compatibility_decisions: tuple[CandidateCompatibilityDecision, ...]
    capability_probe_evidence: tuple[CapabilityProbeEvidence, ...] = ()
    resolved_model_identities: tuple[ResolvedModelIdentity, ...] = ()
    model_liveness_evidence: tuple[ModelLivenessEvidence, ...] = ()
    model_readiness_authority: Literal["live_probe", "applied_ready_state"] = (
        "live_probe"
    )
    optional_dependency_hints: tuple[OptionalDependencyHint, ...]
    dependency_rejections: tuple[DependencyRejection, ...]
    local_encoding_attempts: tuple[LocalEncodingAttempt, ...]
    confidence_evidence: RetrievalConfidenceEvidence
    retrieval_evidence_sha256: str = ""

    @model_validator(mode="after")
    def _seal_result(self) -> "FrozenCandidatePoolResult":
        revision = self.contract_projection.revision
        if self.ideal_resource_profile.revision != revision:
            raise ValueError("candidate_profile_revision_mismatch")
        if self.candidate_pool_snapshot.revision != revision:
            raise ValueError("candidate_snapshot_revision_mismatch")
        if self.confidence_evidence.revision != revision:
            raise ValueError("candidate_confidence_revision_mismatch")
        if (
            self.confidence_evidence.candidate_pool_sha256
            != self.candidate_pool_snapshot.candidate_pool_sha256
        ):
            raise ValueError("candidate_confidence_pool_hash_mismatch")
        if (
            self.runtime_identity.pool_sha256 != self.candidate_pool_snapshot.pool_sha256
            or self.runtime_identity.index_sha256
            != self.candidate_pool_snapshot.index_sha256
            or self.runtime_identity.policy_sha256
            != self.candidate_pool_snapshot.policy_sha256
            or self.runtime_identity.availability_sha256
            != self.candidate_pool_snapshot.availability_sha256
        ):
            raise ValueError("candidate_snapshot_runtime_identity_mismatch")
        candidate_ids = tuple(
            item.resource_id for item in self.candidate_pool_snapshot.candidates
        )
        candidate_id_set = set(candidate_ids)
        priority_ids = tuple(self.compiler_priority_candidate_ids)
        if (
            len(priority_ids) != len(set(priority_ids))
            or any(item not in candidate_id_set for item in priority_ids)
            or priority_ids
            != tuple(item for item in candidate_ids if item in set(priority_ids))
        ):
            raise ValueError("compiler_priority_candidate_ids_invalid")
        candidate_model_ids = {
            item.resource_id
            for item in self.candidate_pool_snapshot.candidates
            if item.resource_type == ManifestType.MODEL.value
        }
        resolved_ids = {item.resource_id for item in self.resolved_model_identities}
        if self.resolved_model_identities and resolved_ids != candidate_model_ids:
            raise ValueError("candidate_model_identity_set_mismatch")
        liveness_by_id = {
            item.resource_id: item for item in self.model_liveness_evidence
        }
        if len(liveness_by_id) != len(self.model_liveness_evidence):
            raise ValueError("candidate_model_liveness_duplicate")
        if (
            self.model_readiness_authority == "live_probe"
            and self.resolved_model_identities
            and not candidate_model_ids <= set(liveness_by_id)
        ):
            raise ValueError("candidate_model_liveness_missing")
        identity_by_id = {item.resource_id: item for item in self.resolved_model_identities}
        for resource_id in candidate_model_ids:
            identity = identity_by_id.get(resource_id)
            evidence = liveness_by_id.get(resource_id)
            if identity is not None and evidence is not None and (
                identity.api_model_id != evidence.api_model_id
                or identity.manifest_sha256 != evidence.manifest_sha256
            ):
                raise ValueError("candidate_model_liveness_identity_mismatch")
        projection = self.model_dump(
            mode="python",
            exclude={"retrieval_evidence_sha256"},
        )
        expected = canonical_sha256(projection)
        if self.retrieval_evidence_sha256:
            supplied = self.retrieval_evidence_sha256.strip().lower()
            pre_priority_projection = self.model_dump(
                mode="python",
                exclude={
                    "retrieval_evidence_sha256",
                    "compiler_priority_candidate_ids",
                },
            )
            pre_priority_expected = canonical_sha256(pre_priority_projection)
            legacy_projection = self.model_dump(
                mode="python",
                exclude={
                    "retrieval_evidence_sha256",
                    "capability_probe_evidence",
                    "resolved_model_identities",
                    "model_liveness_evidence",
                    "model_readiness_authority",
                    "compiler_priority_candidate_ids",
                },
            )
            legacy_expected = canonical_sha256(legacy_projection)
            if supplied not in {expected, pre_priority_expected, legacy_expected}:
                raise ValueError("retrieval_evidence_sha256_mismatch")
            object.__setattr__(self, "retrieval_evidence_sha256", supplied)
        else:
            object.__setattr__(self, "retrieval_evidence_sha256", expected)
        return self

    @property
    def revision(self) -> SubtaskRevisionRef:
        return self.contract_projection.revision


def typed_refs_from_frozen_pool(
    result: FrozenCandidatePoolResult,
    library: Sequence[Manifest],
) -> list[TypedResourceRef]:
    """Materialize the exact frozen snapshot as legacy Router references."""

    manifest_by_id = {item.id: item for item in library}
    score_by_id: dict[str, float] = {}
    for item in result.candidate_score_evidence:
        score_by_id.setdefault(item.resource_id, item.score)
    refs: list[TypedResourceRef] = []
    model_identity_by_id = {
        item.resource_id: item for item in result.resolved_model_identities
    }
    for candidate in result.candidate_pool_snapshot.candidates:
        manifest = manifest_by_id.get(candidate.resource_id)
        if manifest is None or manifest.type.value != candidate.resource_type:
            raise RetrievalRuntimeError("frozen_candidate_missing_from_library")
        model_identity = model_identity_by_id.get(candidate.resource_id)
        if manifest.type == ManifestType.MODEL and result.resolved_model_identities:
            if model_identity is None:
                raise RetrievalRuntimeError("frozen_candidate_model_identity_missing")
        refs.append(
            TypedResourceRef(
                resource_id=candidate.resource_id,
                resource_type=manifest.type,
                base_model=(
                    model_identity.api_model_id
                    if manifest.type == ManifestType.MODEL and model_identity is not None
                    else (
                        candidate.resource_id
                        if manifest.type == ManifestType.MODEL
                        else None
                    )
                ),
                similarity=score_by_id.get(candidate.resource_id),
                candidate_origin=candidate.origin.value,
                injected_reason=(
                    f"required_by:{candidate.required_by_resource_id}"
                    if candidate.required_by_resource_id
                    else None
                ),
            )
        )
    return refs


@dataclass(frozen=True)
class _DependencySlotSpec:
    slot_id: str
    description: str
    allowed_types: tuple[str, ...]
    top_k_per_type: int


@dataclass
class _CandidateEntry:
    resource_id: str
    resource_type: str
    origin: CandidateOrigin
    required_by_resource_id: str | None
    dependency_slot: str | None
    score: float
    rank: int


@dataclass
class _Resolution:
    entries: dict[str, _CandidateEntry] = field(default_factory=dict)
    edges: list[CandidateDependencyEdge] = field(default_factory=list)
    optional_hints: list[OptionalDependencyHint] = field(default_factory=list)


def required_candidate_dependency_edges(
    edges: Sequence[CandidateDependencyEdge],
) -> tuple[CandidateDependencyEdge, ...]:
    """Keep one backing-model witness per Agent; other models are alternatives."""
    anchors: dict[str, CandidateDependencyEdge] = {}
    for edge in edges:
        if edge.requirement_kind == "agent_base_model":
            current = anchors.get(edge.parent_resource_id)
            if current is None or (edge.rank, edge.child_resource_id) < (current.rank, current.child_resource_id):
                anchors[edge.parent_resource_id] = edge
    return tuple(edge for edge in edges if edge.requirement_kind != "agent_base_model"
                 or edge == anchors[edge.parent_resource_id])


def _expand_admitted_agent_model_choices(
    resolution: _Resolution,
    *,
    score_evidence: Sequence[CandidateScoreEvidence],
    compatibility: Mapping[str, CandidateCompatibilityDecision],
    explicit_model_binding: bool,
) -> None:
    """Expose compatible, already-admitted alternatives without new probes/recall."""
    if explicit_model_binding:
        return
    agents = {edge.parent_resource_id for edge in resolution.edges
              if edge.requirement_kind == "agent_base_model"}
    known = {(edge.parent_resource_id, edge.child_resource_id)
             for edge in resolution.edges if edge.requirement_kind == "agent_base_model"}
    for evidence in score_evidence:
        parent = evidence.parent_resource_id
        model = resolution.entries.get(evidence.resource_id)
        decision = compatibility.get(evidence.resource_id)
        if (evidence.query_role != "agent_base_model" or parent not in agents
                or model is None or model.resource_type != "Model"
                or decision is None or decision.verdict != "compatible"
                or (parent, model.resource_id) in known):
            continue
        resolution.edges.append(CandidateDependencyEdge(
            parent_resource_id=parent, child_resource_id=model.resource_id,
            requirement_kind="agent_base_model", child_resource_type="Model", rank=evidence.rank,
        ))
        known.add((parent, model.resource_id))


class _ResolutionFailure(RuntimeError):
    def __init__(
        self,
        reason_code: str,
        *,
        required_resource_id: str | None = None,
        dependency_slot: str | None = None,
    ) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.required_resource_id = required_resource_id
        self.dependency_slot = dependency_slot


_ORIGIN_PRIORITY = {
    CandidateOrigin.RETRIEVAL: 0,
    CandidateOrigin.CONTRACT_DELIVERY: 1,
    CandidateOrigin.REQUIRED_OPERATION: 2,
    CandidateOrigin.USER_EXECUTION_REQUIREMENT: 3,
    CandidateOrigin.PLANNER_CAPABILITY_EVIDENCE: 4,
    CandidateOrigin.EXPLICIT_DEPENDENCY: 5,
    CandidateOrigin.AGENT_BASE_MODEL: 6,
    CandidateOrigin.DEPENDENCY_SLOT: 7,
}


def _normalized_resource_type(value: Any) -> str | None:
    text = str(getattr(value, "value", value) or "").strip()
    aliases = {"MAS": "Agent", "MultiAgentSystem": "Agent"}
    text = aliases.get(text, text)
    return text if text in FORMAL_TYPE_ORDER else None


def _normalized_delivery_artifact_type(value: Any) -> str:
    normalized = str(value or "").strip().casefold().replace("-", "_")
    return {
        "text": "plaintext",
        "text/plain": "plaintext",
        "plain_text": "plaintext",
    }.get(normalized, normalized)


def _required_file_delivery_specs(
    contract: RetrievalContractProjection,
) -> tuple[tuple[str, str], ...]:
    """Return explicit required file locators and their declared value types."""

    return tuple(
        (
            posixpath.normpath(str(item.path_hint).strip()),
            _normalized_delivery_artifact_type(item.artifact_type),
        )
        for item in contract.produced_files
        if item.required
        and str(item.path_hint or "").strip()
        and _normalized_delivery_artifact_type(item.artifact_type)
    )


def _manifest_input_contracts(raw: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    contracts = raw.get("input_contract")
    if not isinstance(contracts, list):
        io = raw.get("io")
        contracts = io.get("input_contract") if isinstance(io, Mapping) else []
    return tuple(item for item in contracts if isinstance(item, Mapping))


def _manifest_explicitly_reads_material(
    raw: Mapping[str, Any],
    descriptor: PublicContextDescriptor,
) -> bool:
    """Prove that a read-only Tool explicitly accepts this material type.

    Generic file-path ports do not establish that a binary representation can
    be decoded.  The manifest must name the artifact type or its extension and
    expose a read/parse/extract style operation.  This keeps material access
    independent of vector top-k without claiming that every path-taking Tool is
    a reader.
    """

    if _resource_type(raw) != "Tool":
        return False
    capability = raw.get("capability")
    capability = capability if isinstance(capability, Mapping) else {}
    semantics = capability.get("execution_semantics")
    semantics = semantics if isinstance(semantics, Mapping) else {}
    if str(semantics.get("side_effects") or "").strip().casefold() != "none":
        return False
    operations = " ".join(
        sorted(manifest_capability_operations(dict(raw)))
    ).casefold()
    if not any(
        marker in operations
        for marker in ("read", "load", "open", "parse", "extract", "inspect", "convert")
    ):
        return False
    artifact_type = _normalized_delivery_artifact_type(descriptor.artifact_type)
    source_name = str(descriptor.source_name or descriptor.logical_name or "").strip()
    extension = posixpath.splitext(source_name.replace("\\", "/"))[1].casefold()
    for port in _manifest_input_contracts(raw):
        declared_types = port.get("artifact_types")
        declared_types = (
            declared_types
            if isinstance(declared_types, (list, tuple, set))
            else (declared_types,)
        )
        normalized_types = {
            _normalized_delivery_artifact_type(item)
            for item in declared_types
            if item not in (None, "")
        }
        declared_extensions = port.get("extensions")
        declared_extensions = (
            declared_extensions
            if isinstance(declared_extensions, (list, tuple, set))
            else (declared_extensions,)
        )
        normalized_extensions = {
            str(item).strip().casefold()
            for item in declared_extensions
            if str(item or "").strip()
        }
        if artifact_type in normalized_types or (
            extension and extension in normalized_extensions
        ):
            return True
    return False


def _contract_material_access_candidate_ids(
    contract: RetrievalContractProjection,
    rankings: Sequence[tuple[Manifest, float, float, float | None, int]],
    raw_by_id: Mapping[str, Mapping[str, Any]],
) -> tuple[str, ...]:
    """Reserve the smallest native-or-generated route for handle-only inputs.

    An exact, read-only native processor wins.  If no ranked Tool explicitly
    accepts a material representation, reserve one general generated-code
    runner; the existing composition closure then admits one compatible writer.
    These are candidates only.  Compiler still chooses the cheapest feasible
    route and may use a directly bound Model when its declared contract covers
    the material.
    """

    selected: list[str] = []
    fallback_needed = False
    descriptors = tuple(
        item
        for item in contract.public_context_descriptors
        if item.handle_available and item.coverage_status != "complete"
    )
    for descriptor in descriptors:
        match = next(
            (
                manifest.id
                for manifest, _score, _cap, _con, _rank in rankings
                if _manifest_explicitly_reads_material(
                    raw_by_id[manifest.id], descriptor
                )
            ),
            None,
        )
        if match is None:
            fallback_needed = True
        elif match not in selected:
            selected.append(match)
    if fallback_needed:
        fallback = next(
            (
                manifest.id
                for manifest, _score, _cap, _con, _rank in rankings
                if manifest_capability_operations(dict(raw_by_id[manifest.id]))
                & {"python_execution", "generated_code_execution"}
                and any(
                    bool(port.get("accepts_artifact_handle_item"))
                    for port in _manifest_input_contracts(raw_by_id[manifest.id])
                )
            ),
            None,
        )
        if fallback is not None and fallback not in selected:
            selected.append(fallback)
    return tuple(selected)


def _cost_diverse_model_rankings(
    rankings: Sequence[tuple[Manifest, float, float, float | None, int]],
    raw_by_id: Mapping[str, Mapping[str, Any]],
    *,
    quota: int,
) -> tuple[tuple[Manifest, float, float, float | None, int], ...]:
    """Reserve one semantically credible low-price Model inside the same quota.

    Semantic retrieval establishes eligibility.  This projection changes only
    which eligible Models occupy a bounded top-k portfolio; it does not make a
    Model executable, preferred by the Compiler, or exempt from compatibility
    and readiness checks.
    """

    ordered = tuple(rankings)
    if quota < 2 or len(ordered) <= quota:
        return ordered
    best_score = float(ordered[0][1])
    semantic_floor = best_score - 0.10

    def price_key(
        item: tuple[Manifest, float, float, float | None, int],
    ) -> tuple[float, float, float, int, str]:
        raw = raw_by_id.get(item[0].id, {})
        type_specific = raw.get("type_specific")
        model = (
            type_specific.get("model")
            if isinstance(type_specific, Mapping)
            else None
        )
        pricing = model.get("pricing") if isinstance(model, Mapping) else None
        try:
            input_price = float(pricing["input_per_m"])
            output_price = float(pricing["output_per_m"])
        except (KeyError, TypeError, ValueError):
            return (math.inf, math.inf, math.inf, item[4], item[0].id)
        if (
            not math.isfinite(input_price)
            or not math.isfinite(output_price)
            or input_price < 0
            or output_price < 0
        ):
            return (math.inf, math.inf, math.inf, item[4], item[0].id)
        return (
            input_price + output_price,
            output_price,
            input_price,
            item[4],
            item[0].id,
        )

    credible = tuple(item for item in ordered if float(item[1]) >= semantic_floor)
    priced = tuple(item for item in credible if math.isfinite(price_key(item)[0]))
    if not priced:
        return ordered
    cost_representative = min(priced, key=price_key)
    if cost_representative in ordered[:quota]:
        return ordered

    selected = [ordered[0]]
    for item in ordered[1:]:
        if item == cost_representative:
            continue
        if len(selected) >= quota - 1:
            break
        selected.append(item)
    selected.append(cost_representative)
    selected_ids = {item[0].id for item in selected}
    return tuple((*selected, *(item for item in ordered if item[0].id not in selected_ids)))


def _contract_input_parser_candidate_ids(
    contract: RetrievalContractProjection,
    rankings: Sequence[tuple[Manifest, float, float, float | None, int]],
    raw_by_id: Mapping[str, Mapping[str, Any]],
    *,
    candidate_ids: Sequence[str] = (),
    required_formats: Sequence[str] = (),
    source_acquisition: bool = False,
) -> tuple[str, ...]:
    """Keep a format reader available for unread authorized material.

    Selection is a candidate, not an execution route. Prefer explicit complete
    extraction over bounded previews; keep semantic order within each class.
    No resource IDs or business task text participate in this coverage rule.
    """
    formats: set[str] = {str(value).lower().lstrip(".") for value in required_formats}
    if source_acquisition:
        # External acquisition can discover a typed document only after freeze.
        # Reserve the highest-ranked native reader's format family in advance,
        # then select its complete reader below. This is one semantic coverage
        # slot, not all catalog readers or an inferred task/file-format rule.
        # Existing ranked candidates, availability checks, and frozen recovery
        # remain unchanged; the Compiler decides whether to use this option.
        for manifest, *_score in rankings:
            raw = raw_by_id.get(manifest.id, {})
            capability = raw.get("capability") or {}
            semantics = capability.get("execution_semantics") or {}
            if semantics.get("side_effects") not in (None, "none"):
                continue
            evidence = " ".join(str(v) for v in capability.get("core_primitives", ()))
            evidence += " " + str(capability.get("summary") or "")
            if not re.search(r"extract|parse|read|load", evidence, re.I):
                continue
            declared = {str(value).lower().lstrip(".")
                        for port in _manifest_input_contracts(raw)
                        if port.get("kind") == "file_path"
                        for value in (*port.get("artifact_types", ()), *port.get("extensions", ()))}
            declared.difference_update({"file", "directory", "bundle", "unknown", "code", "plaintext"})
            if declared:
                formats.update(declared)
                break
    for descriptor in contract.public_context_descriptors:
        if not descriptor.content_acquisition_required or descriptor.coverage_status == "complete":
            continue
        formats.add(descriptor.artifact_type.lower())
        inventory = descriptor.container_inventory
        if inventory.get("status") == "observed":
            # Reading contained formats also requires access to the container.
            # Keep its declared extractor available; never treat its members
            # as already materialized files.
            container_format = str(inventory.get("format") or "").lower()
            if container_format:
                formats.add(container_format)
            formats.update(str(value).lower() for value in inventory.get("artifact_types", ()))
            formats.update(str(value).lower() for value in inventory.get("formats", ()))
    # A discovered external document has no input descriptor yet. If semantic
    # retrieval already admitted a bounded file reader, preserve an eligible
    # complete reader for that same declared representation before freezing.
    # This adds no format inferred from task text and chooses no execution route.
    ranked_ids = {manifest.id for manifest, *_score in rankings}
    for resource_id in candidate_ids:
        if resource_id not in ranked_ids:
            continue
        raw = raw_by_id.get(resource_id, {})
        capability = raw.get("capability") or {}
        evidence = " ".join(str(value) for value in capability.get("core_primitives", ()))
        evidence += " " + str(capability.get("summary") or "")
        if not re.search(r"extract|convert|parse|read|load", evidence, re.I):
            continue
        if not re.search(r"preview|truncate|first\s+\d+|at.most\s+\d+\s+character", evidence, re.I):
            continue
        for port in _manifest_input_contracts(raw):
            if port.get("kind") != "file_path":
                continue
            formats.update(str(value).lower().lstrip(".") for value in (
                *port.get("artifact_types", ()), *port.get("extensions", ())))
    formats.difference_update({"file", "directory", "bundle", "unknown", "code", "plaintext"})
    selected: list[str] = []
    for format_id in sorted(formats):
        choices = []
        for order, (manifest, *_score) in enumerate(rankings):
            raw = raw_by_id.get(manifest.id, {})
            capability = raw.get("capability") or {}
            constraint = raw.get("constraint") or {}
            primitives = " ".join(str(value) for value in capability.get("core_primitives", ()))
            summary = str(capability.get("summary") or "")
            if not re.search(r"extract|convert|parse|read|load", primitives + " " + summary, re.I):
                continue
            ports = _manifest_input_contracts(raw)
            declared_types = {str(value).lower().lstrip(".") for port in ports
                              for value in (*port.get("artifact_types", ()), *port.get("extensions", ()))}
            accepted = " ".join(str(value) for value in constraint.get("accepted_inputs", ()))
            if (format_id not in declared_types
                    and not re.search(r"(?<![\w])" + re.escape(format_id) + r"(?![\w])", accepted, re.I)):
                continue
            limited = bool(re.search(r"preview|truncate|first\s+\d+|at.most\s+\d+\s+character",
                                     primitives + " " + summary, re.I))
            complete = bool(re.search(r"complete|\ball\b|\bevery\b|iterate_all", primitives + " " + summary, re.I))
            choices.append((2 if limited else 0 if complete else 1, order, manifest.id))
        if choices:
            selected.append(min(choices)[2])
    return tuple(dict.fromkeys(selected))


def _manifest_delivery_types(raw: Mapping[str, Any]) -> frozenset[str]:
    constraint = raw.get("constraint")
    constraint = constraint if isinstance(constraint, Mapping) else {}
    declared = constraint.get("materialized_artifact_types")
    values = declared if isinstance(declared, (list, tuple, set)) else (declared,)
    candidates = [item for item in values if item not in (None, "")]
    return frozenset(
        _normalized_delivery_artifact_type(item)
        for item in candidates
        if _normalized_delivery_artifact_type(item)
    )


def _path_is_within_declared_root(path: str, root: str) -> bool:
    normalized_root = posixpath.normpath(str(root or "").strip())
    raw_path = str(path or "").strip()
    if not raw_path or not normalized_root.startswith("/"):
        return False
    # Planner contracts intentionally use logical, workspace-relative file
    # names.  Materializer manifests declare the container root (normally
    # /app).  Lower the logical name into that root for the proof, while
    # rejecting traversal and host-style path spellings before normalization.
    if "\\" in raw_path or any(part == ".." for part in raw_path.split("/")):
        return False
    try:
        normalized_path = lower_container_path(raw_path, workspace_root=normalized_root)
    except ValueError:
        return False
    return bool(
        normalized_path.startswith("/")
        and (
            normalized_path == normalized_root
            or normalized_path.startswith(normalized_root.rstrip("/") + "/")
        )
    )


def lower_container_path(path: str, *, workspace_root: str = "/app") -> str:
    """Lower one logical artifact name into the declared container namespace."""

    raw = str(path or "").strip()
    root = posixpath.normpath(str(workspace_root or "/app").strip())
    if not raw or not root.startswith("/"):
        raise ValueError("container_workspace_root_invalid")
    if "\\" in raw or any(part == ".." for part in raw.split("/")):
        raise ValueError("container_path_traversal")
    candidate = posixpath.normpath(
        raw if raw.startswith("/") else posixpath.join(root, raw)
    )
    if candidate != root and not candidate.startswith(root.rstrip("/") + "/"):
        raise ValueError("container_path_outside_workspace")
    return candidate


def _manifest_covers_file_delivery(
    raw: Mapping[str, Any],
    *,
    path: str,
    artifact_type: str,
) -> bool:
    """Prove a deterministic value-to-file operation from declared manifest facts."""

    if _resource_type(raw) != "Tool":
        return False
    if not manifest_capability_operations(dict(raw)) & {
        "write_complete_text_file",
        "create_text_artifact",
        "overwrite_file_contents",
        "write_file",
    }:
        return False
    capability = raw.get("capability")
    capability = capability if isinstance(capability, Mapping) else {}
    semantics = capability.get("execution_semantics")
    semantics = semantics if isinstance(semantics, Mapping) else {}
    if (
        str(semantics.get("determinism") or "").strip().casefold()
        != "deterministic"
        or str(semantics.get("side_effects") or "").strip().casefold()
        != "declared"
    ):
        return False
    contracts = _manifest_input_contracts(raw)
    port_names = {str(item.get("name") or "").strip().casefold() for item in contracts}
    path_ports = {"path", "file_path", "destination", "destination_path", "target_path"}
    payload_ports = {"content", "text", "payload", "data"}
    if not (port_names & path_ports and port_names & payload_ports):
        return False
    if artifact_type not in _manifest_delivery_types(raw):
        return False
    requirements = raw.get("runtime_requirements")
    requirements = requirements if isinstance(requirements, Mapping) else {}
    mcp = requirements.get("mcp")
    roots = mcp.get("allowed_roots") if isinstance(mcp, Mapping) else None
    if not isinstance(roots, list) or not any(
        _path_is_within_declared_root(path, str(root)) for root in roots
    ):
        return False
    return True


def _contract_delivery_candidate_ids(
    contract: RetrievalContractProjection,
    rankings: Sequence[tuple[Manifest, float, float, float | None, int]],
    raw_by_id: Mapping[str, Mapping[str, Any]],
) -> tuple[str, ...]:
    """Choose the highest semantic-ranked compatible materializer per file contract."""

    selected: list[str] = []
    for path, artifact_type in _required_file_delivery_specs(contract):
        match = next(
            (
                manifest.id
                for manifest, _score, _cap, _con, _rank in rankings
                if _manifest_covers_file_delivery(
                    raw_by_id[manifest.id],
                    path=path,
                    artifact_type=artifact_type,
                )
            ),
            None,
        )
        if match is not None and match not in selected:
            selected.append(match)
    return tuple(selected)


def _contract_workspace_effect_candidate_ids(
    contract: RetrievalContractProjection,
    rankings: Sequence[tuple[Manifest, float, float, float | None, int]],
    raw_by_id: Mapping[str, Mapping[str, Any]],
) -> tuple[str, ...]:
    """Keep a declared mutator and a flexible executor available for state work.

    This reserves candidates, not plan steps. The Compiler may still choose a
    cheaper deterministic mutator when it can satisfy the exact task.
    """

    semantic = contract.semantic_contract_v2
    if semantic is None or semantic.required_effect != "task_workspace_mutation":
        return ()
    eligible: list[tuple[str, frozenset[str]]] = []
    for manifest, _score, _cap, _con, _rank in rankings:
        raw = raw_by_id[manifest.id]
        capability = raw.get("capability")
        if not isinstance(capability, Mapping):
            continue
        semantics = capability.get("execution_semantics")
        if not isinstance(semantics, Mapping):
            continue
        if semantics.get("side_effects") != "declared" or "task_workspace" not in (semantics.get("effect_targets") or ()):
            continue
        eligible.append((manifest.id, manifest_capability_operations(dict(raw))))
    if not eligible:
        return ()
    selected = [eligible[0][0]]
    flexible = next(
        (resource_id for resource_id, operations in eligible
         if operations & {"python_execution", "generated_code_execution", "execute_shell_commands"}),
        None,
    )
    if flexible is not None and flexible not in selected:
        selected.append(flexible)
    return tuple(selected)


def _generated_program_materializer_ids(
    selected_ids: Sequence[str],
    rankings: Sequence[tuple[Manifest, float, float, float | None, int]],
    raw_by_id: Mapping[str, Mapping[str, Any]],
) -> tuple[str, ...]:
    """Keep a file-based code executor composable with at most one writer.

    This is capability closure, not a required execution route. A direct-text
    shell does not need it. The Compiler may reuse an authorized script or
    choose another route, and every admitted writer still passes normal
    runtime/dependency validation. The probe path only establishes public
    workspace coverage; it is never prescribed as a plan output path.
    """
    needs_file = any(
        manifest_capability_operations(dict(raw_by_id[resource_id]))
        & {"python_execution", "generated_code_execution"}
        and "file_path" in _manifest_input_kinds(raw_by_id[resource_id])
        for resource_id in selected_ids if resource_id in raw_by_id
    )
    if not needs_file:
        return ()

    def covers(raw: Mapping[str, Any]) -> bool:
        return _manifest_covers_file_delivery(
            raw, path="/app/.sgar/program.py", artifact_type="code",
        )

    if any(covers(raw_by_id[rid]) for rid in selected_ids if rid in raw_by_id):
        return ()
    match = next((manifest.id for manifest, *_ in rankings
                  if covers(raw_by_id[manifest.id])), None)
    return (match,) if match is not None else ()


def _manifest_input_kinds(raw: Mapping[str, Any]) -> frozenset[str]:
    contracts: Any = raw.get("input_contract")
    if not isinstance(contracts, list):
        io = raw.get("io")
        contracts = io.get("input_contract") if isinstance(io, Mapping) else []
    kinds: set[str] = set()
    for item in contracts or ():
        if not isinstance(item, Mapping):
            continue
        value = str(item.get("kind") or "").strip().lower().replace("-", "_")
        if value in {"file_path", "filepath"}:
            kinds.add("file_path")
        elif value in {"directory_path", "dir_path", "folder_path", "directory"}:
            kinds.add("directory_path")
        elif value:
            kinds.add(value)
    constraint = raw.get("constraint")
    artifact_input = constraint.get("artifact_input") if isinstance(constraint, Mapping) else None
    for value in artifact_input if isinstance(artifact_input, list) else ():
        normalized = str(value).strip().lower().replace("-", "_")
        if normalized in {"repo_path", "proj_dir", "directory", "directory_path"}:
            kinds.add("directory_path")
        elif normalized in {"file", "file_path", "python_script"}:
            kinds.add("file_path")
        elif normalized:
            kinds.add(normalized)
    return frozenset(kinds)


def _parse_context_tokens(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value if value >= 0 else None
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*([km]?)",
        str(value or "").lower().replace(",", ""),
    )
    if not match:
        return None
    amount = float(match.group(1))
    if match.group(2) == "k":
        amount *= 1_000
    elif match.group(2) == "m":
        amount *= 1_000_000
    return int(amount)


def _required_dependency_declarations(
    raw: Mapping[str, Any],
) -> tuple[tuple[str, ...], tuple[_DependencySlotSpec, ...], tuple[OptionalDependencyHint, ...]]:
    resource_id = _resource_id(raw)
    type_specific = raw.get("type_specific")
    type_specific = type_specific if isinstance(type_specific, Mapping) else {}
    skill = type_specific.get("skill")
    skill = skill if isinstance(skill, Mapping) else {}
    agent = type_specific.get("agent")
    agent = agent if isinstance(agent, Mapping) else {}

    required_ids: list[str] = []
    for source in (
        skill.get("required_resource_ids", ()),
        agent.get("required_dependency_ids", ()),
    ):
        if isinstance(source, list):
            required_ids.extend(str(item).strip() for item in source if str(item).strip())

    slots: list[_DependencySlotSpec] = []
    hints: list[OptionalDependencyHint] = []
    routing = raw.get("routing")
    routing = routing if isinstance(routing, Mapping) else {}
    sources = (
        raw.get("dependency_slots"),
        raw.get("dependencies"),
        routing.get("dependency_slots"),
    )
    slot_index = 0
    for source in sources:
        values = source if isinstance(source, list) else ([source] if isinstance(source, Mapping) else [])
        for item in values:
            if not isinstance(item, Mapping):
                continue
            required = bool(item.get("required", False))
            dependency_id = str(item.get("resource_id") or item.get("id") or "").strip()
            if dependency_id:
                if required:
                    required_ids.append(dependency_id)
                else:
                    hints.append(
                        OptionalDependencyHint(
                            parent_resource_id=resource_id,
                            hint_kind="optional_resource_id",
                            resource_id=dependency_id,
                        )
                    )
                continue
            description = str(
                item.get("description") or item.get("query") or item.get("name") or ""
            ).strip()
            if not description:
                continue
            slot_id = str(
                item.get("slot_id") or item.get("name") or f"{resource_id}_dep_{slot_index}"
            ).strip()
            slot_index += 1
            raw_allowed = item.get("allowed_types") or item.get("resource_types") or ()
            allowed = tuple(
                resource_type
                for resource_type in (
                    _normalized_resource_type(value) for value in raw_allowed
                )
                if resource_type is not None
            )
            if not allowed:
                allowed = ("Tool", "Skill", "Resource", "Agent")
            if required:
                slots.append(
                    _DependencySlotSpec(
                        slot_id=slot_id,
                        description=description,
                        allowed_types=tuple(dict.fromkeys(allowed)),
                        top_k_per_type=max(1, int(item.get("top_k_per_type") or 3)),
                    )
                )
            else:
                hints.append(
                    OptionalDependencyHint(
                        parent_resource_id=resource_id,
                        hint_kind="optional_dependency_slot",
                        dependency_slot=slot_id,
                        description=description,
                        allowed_types=tuple(dict.fromkeys(allowed)),
                    )
                )

    optional_sources = (
        ("optional_resource_id", skill.get("optional_resource_ids", ())),
        ("recommended_dependency_id", agent.get("recommended_dependency_ids", ())),
        ("allowed_dependency_id", agent.get("allowed_dependency_ids", ())),
    )
    for hint_kind, source in optional_sources:
        if not isinstance(source, list):
            continue
        for dependency_id in source:
            normalized = str(dependency_id or "").strip()
            if normalized:
                hints.append(
                    OptionalDependencyHint(
                        parent_resource_id=resource_id,
                        hint_kind=hint_kind,
                        resource_id=normalized,
                    )
                )
    return (
        tuple(dict.fromkeys(required_ids)),
        tuple(sorted(slots, key=lambda item: item.slot_id)),
        tuple(
            sorted(
                hints,
                key=lambda item: (
                    item.hint_kind,
                    item.resource_id or "",
                    item.dependency_slot or "",
                ),
            )
        ),
    )


def validate_required_dependency_graph(
    resources: Sequence[Mapping[str, Any]],
) -> None:
    """Reject explicit required-ID cycles before any paid model operation."""

    by_id = {_resource_id(item): item for item in resources}
    graph: dict[str, tuple[str, ...]] = {}
    for resource_id, raw in by_id.items():
        required_ids, _slots, _hints = _required_dependency_declarations(raw)
        graph[resource_id] = tuple(item for item in required_ids if item in by_id)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(resource_id: str) -> None:
        if resource_id in visiting:
            raise RetrievalRuntimeError("required_dependency_cycle")
        if resource_id in visited:
            return
        visiting.add(resource_id)
        for dependency_id in graph.get(resource_id, ()):
            visit(dependency_id)
        visiting.remove(resource_id)
        visited.add(resource_id)

    for resource_id in sorted(graph):
        visit(resource_id)


def _compatibility_decision(
    raw: Mapping[str, Any],
    manifest: Manifest,
    availability: AvailabilityRecord,
    requirements: Mapping[str, Any],
) -> CandidateCompatibilityDecision:
    hard_reasons: list[str] = []
    conditional_reasons: list[str] = []
    unknown = False
    raw_type = _resource_type(raw)
    if raw_type != manifest.type.value:
        return CandidateCompatibilityDecision(
            resource_id=manifest.id,
            resource_type=manifest.type.value,
            verdict="incompatible",
            reason_codes=("manifest_type_mismatch",),
        )
    if availability.status == "unavailable" or not availability.in_effective_pool:
        return CandidateCompatibilityDecision(
            resource_id=manifest.id,
            resource_type=manifest.type.value,
            verdict="incompatible",
            reason_codes=(availability.reason_code or "resource_unavailable",),
        )
    if availability.provider_compatibility == "incompatible":
        return CandidateCompatibilityDecision(
            resource_id=manifest.id,
            resource_type=manifest.type.value,
            verdict="incompatible",
            reason_codes=("provider_incompatible",),
        )
    if availability.status == "unknown" or (
        manifest.type == ManifestType.MODEL
        and availability.provider_compatibility == "unknown"
    ):
        unknown = True

    status = str(raw.get("status") or "active").strip().lower()
    execution = raw.get("execution")
    execution = execution if isinstance(execution, Mapping) else {}
    execution_status = str(execution.get("execution_status") or "active").strip().lower()
    if status not in {"", "active", "available", "ok", "ready"}:
        hard_reasons.append("manifest_inactive")
    if execution_status not in {"", "active", "available", "ok", "ready"}:
        hard_reasons.append("execution_inactive")
    actual_runtime = str(execution.get("runtime") or "").strip()
    if not actual_runtime:
        hard_reasons.append("runtime_kind_missing")
    elif not runtime_adapter_supported(manifest.type.value, actual_runtime):
        hard_reasons.append("runtime_adapter_unsupported")
    try:
        definition = ResourceDefinition.from_manifest(raw)
    except (ResourceManifestError, TypeError, ValueError):
        hard_reasons.append("resource_execution_contract_invalid")
    else:
        operations = (
            definition.capability_card.capability_operations
            if definition.capability_card is not None
            else ()
        )
        operation_entrypoints = {
            operation.entrypoint_id
            for operation in operations
            if operation.entrypoint_id is not None
        }
        declared_entrypoints = {item.entrypoint_id for item in definition.entrypoints}
        if not operation_entrypoints or not operation_entrypoints.issubset(
            declared_entrypoints
        ):
            hard_reasons.append("operation_entrypoint_unexecutable")
        if manifest.type == ManifestType.TOOL and any(
            str(entrypoint.output_contract.get("artifact_type") or "").strip().casefold() == "json"
            and not any(
                isinstance(entrypoint.output_contract.get(key), Mapping)
                for key in ("schema_hint", "json_schema", "schema", "semantic_output", "result_status")
            )
            for entrypoint in definition.entrypoints
        ):
            # The same native JSON gate is enforced by the Compiler and
            # ResourceRuntime. Exclude unusable Tools before retrieval freezes
            # the pool instead of paying for a doomed Compiler proposal.
            hard_reasons.append("tool_native_json_contract_missing")
    provenance = raw.get("provenance")
    provenance = provenance if isinstance(provenance, Mapping) else {}
    trust = str(provenance.get("trust_level") or "").strip().lower()
    if trust in {"blocked", "untrusted", "unsafe", "denied"}:
        hard_reasons.append("trust_blocked")
    safety = raw.get("safety")
    safety = safety if isinstance(safety, Mapping) else {}
    if str(safety.get("status") or "").strip().lower() in {"blocked", "unsafe", "denied"}:
        hard_reasons.append("safety_blocked")
    prohibited_licenses = {
        str(item).strip().lower()
        for item in requirements.get("prohibited_licenses", ())
        if str(item).strip()
    }
    license_name = str(provenance.get("license") or "").strip().lower()
    if prohibited_licenses:
        if license_name and license_name in prohibited_licenses:
            hard_reasons.append("license_prohibited")
        elif not license_name:
            unknown = True
    minimum_trust = str(requirements.get("minimum_trust") or "").strip().lower()
    trust_order = {"community": 1, "maintained": 2, "official": 3}
    if minimum_trust in trust_order:
        if trust in trust_order and trust_order[trust] < trust_order[minimum_trust]:
            hard_reasons.append("trust_below_minimum")
        elif trust not in trust_order:
            unknown = True

    required_runtime = str(requirements.get("required_runtime") or "").strip().lower()
    actual_runtime = str(execution.get("runtime") or "").strip().lower()
    if required_runtime:
        if actual_runtime and actual_runtime != required_runtime:
            hard_reasons.append("runtime_contract_conflict")
        elif not actual_runtime:
            unknown = True

    if manifest.type == ManifestType.MODEL:
        type_specific = raw.get("type_specific")
        model = type_specific.get("model") if isinstance(type_specific, Mapping) else None
        model = model if isinstance(model, Mapping) else {}
        supports = model.get("supports")
        supports = supports if isinstance(supports, Mapping) else {}
        for feature in requirements.get("required_model_features", ()):
            value = supports.get(str(feature))
            if value is False:
                if str(feature) in {
                    "json_mode",
                    "json_schema",
                    "structured_outputs",
                    "structured_outputs_ok",
                }:
                    conditional_reasons.append(
                        f"native_format_feature_explicitly_unsupported:{feature}"
                    )
                else:
                    hard_reasons.append(f"model_feature_explicitly_unsupported:{feature}")
            elif value is not True:
                unknown = True
        from retrieval_profiles import model_modality_support, model_context_tokens
        for direction in ("input", "output"):
            for modality in requirements.get(f"{direction}_modalities", ()):
                normalized = str(modality).strip().lower()
                value = model_modality_support(model, normalized, direction)
                if value is False:
                    hard_reasons.append(f"model_{direction}_modality_explicitly_unsupported:{normalized}")
                elif value is not True:
                    unknown = True
                if normalized in {"audio", "video"} and model.get("gateway_verification_status") != "live_verified":
                    unknown = True
        minimum = requirements.get("min_context_tokens")
        if isinstance(minimum, int) and not isinstance(minimum, bool) and minimum > 0:
            available = model_context_tokens(model)
            if available is not None and available < minimum:
                hard_reasons.append("model_context_window_insufficient")
            elif available is None:
                unknown = True

    # A task-level input kind does not constrain every Tool in a multi-step
    # workflow. A file writer, for example, consumes a Model's text output
    # even when the original task input is a file. Pool-level coverage checks
    # explicit input kinds; Compiler bindings validate each selected port.

    if hard_reasons:
        verdict = "incompatible"
        reasons = hard_reasons
    elif conditional_reasons:
        verdict = "conditional"
        reasons = conditional_reasons
    elif unknown:
        verdict = "unknown"
        reasons = ["metadata_incomplete"]
    else:
        verdict = "compatible"
        reasons = []
    return CandidateCompatibilityDecision(
        resource_id=manifest.id,
        resource_type=manifest.type.value,
        verdict=verdict,
        reason_codes=tuple(sorted(set(reasons))),
    )


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        raise RetrievalRuntimeError("retrieval_vector_dimension_mismatch")
    numerator = sum(float(a) * float(b) for a, b in zip(left, right))
    left_norm = math.sqrt(sum(float(item) ** 2 for item in left))
    right_norm = math.sqrt(sum(float(item) ** 2 for item in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return numerator / (left_norm * right_norm)


class _CandidatePoolBuilder:
    def __init__(
        self,
        *,
        identity: RetrievalRuntimeIdentity,
        contract: RetrievalContractProjection,
        profile: EncodedIdealResourceProfile,
        library: Sequence[Manifest],
        resource_index: Mapping[str, Mapping[str, Any]],
        local_text_encoder: Callable[[str], Sequence[float]],
        capability_probe_service: Any,
        model_liveness_probe_service: ModelLivenessProbeService,
        cost_ledger: RunCostLedger | None,
        model_readiness_authority: Literal["live_probe", "applied_ready_state"],
        runtime_incompatibility: Callable[[Mapping[str, Any]], str | None] | None = None,
    ) -> None:
        self.identity = identity
        self.contract = contract
        self.profile = profile
        self.library = tuple(library)
        self.manifest_by_id = {item.id: item for item in self.library}
        self.raw_by_id = {str(key): value for key, value in resource_index.items()}
        self.local_text_encoder = local_text_encoder
        self.capability_probe_service = capability_probe_service
        self.model_liveness_probe_service = model_liveness_probe_service
        self.cost_ledger = cost_ledger
        self.model_readiness_authority = model_readiness_authority
        self.runtime_incompatibility = runtime_incompatibility
        self.requirements = profile.artifact.explicit_hard_requirements
        self.output_schema_phase = classify_output_schema_phase(contract)
        if self.output_schema_phase == "invalid_missing":
            # Preserve the strict V4/V5 behavior and its precise failure code.
            self.output_format_requirement: OutputFormatRequirement | None = (
                OutputFormatRequirement.from_contract_projection(contract)
            )
        elif self.output_schema_phase == "compiler_pending":
            # Planner V6 owns semantic output shape only.  Exact schema probing
            # is deferred until the Compiler has generated a concrete schema
            # and selected the producer resource.
            self.output_format_requirement = None
        else:
            self.output_format_requirement = (
                OutputFormatRequirement.from_contract_projection(contract)
            )
        self.availability_by_id = {
            item.resource_id: item for item in identity.availability_records
        }
        self.compatibility: dict[str, CandidateCompatibilityDecision] = {}
        self.capability_probe_evidence: dict[
            tuple[str, str], CapabilityProbeEvidence
        ] = {}
        self.resolved_model_identities: dict[str, ResolvedModelIdentity] = {}
        self.model_liveness_evidence: dict[str, ModelLivenessEvidence] = {}
        self.model_liveness_transient_failures: set[str] = set()
        self.model_liveness_permanent_failures: set[str] = set()
        self.format_probe_attempted: set[str] = set()
        self.temporary_tool_probe_attempted: set[str] = set()
        self.score_evidence: list[CandidateScoreEvidence] = []
        self.local_attempts: list[LocalEncodingAttempt] = []
        self.dependency_rejections: list[DependencyRejection] = []
        self._slot_vectors: dict[tuple[str, str], tuple[float, ...]] = {}
        self._agent_vectors: dict[str, tuple[float, ...]] = {}
        self._validate_library_identity()
        self._prepare_compatibility()

    def _required_resource_id(self, requirement: ExecutionResourceRequirementV1) -> str | None:
        if requirement.resource_id is not None:
            requested = str(requirement.resource_id).strip()
            manifest = self.manifest_by_id.get(requested)
            if manifest is not None and manifest.type.value == requirement.resource_type:
                return requested

            # Planner requirements may carry a provider/tool alias (for
            # example ``coqc``) instead of the catalog's sealed resource ID.
            # Resolve only a unique declaration-backed match; never guess when
            # multiple resources expose the same alias.
            requested_token = requested.casefold().replace("-", "_")
            matches: list[str] = []
            for resource_id, candidate in self.manifest_by_id.items():
                if candidate.type.value != requirement.resource_type:
                    continue
                raw = self.raw_by_id.get(resource_id)
                if not isinstance(raw, Mapping):
                    continue
                aliases: set[str] = {resource_id.casefold()}
                if "." in resource_id:
                    aliases.add(resource_id.split(".", 2)[1].casefold())
                capability = raw.get("capability")
                if isinstance(capability, Mapping):
                    for key in ("operation_kinds", "core_primitives", "operations"):
                        values = capability.get(key) or ()
                        if isinstance(values, (list, tuple, set)):
                            aliases.update(str(item).casefold() for item in values)
                operation_ids = getattr(candidate, "capability_operations", ()) or ()
                aliases.update(
                    str(getattr(item, "operation_id", "") or "").casefold()
                    for item in operation_ids
                )
                if any(
                    requested_token == alias.replace("-", "_")
                    or requested_token in alias.replace("-", "_").split(".")
                    or requested_token in alias.replace("-", "_")
                    for alias in aliases
                    if alias
                ):
                    matches.append(resource_id)
            if len(matches) != 1:
                raise RetrievalRuntimeError("execution_requirement_resource_unavailable")
            return matches[0]
        if requirement.api_model_id is None:
            return None
        matches = [
            resource_id
            for resource_id, raw in self.raw_by_id.items()
            if self.manifest_by_id[resource_id].type == ManifestType.MODEL
            and _model_api_id(raw) == requirement.api_model_id
        ]
        if len(matches) != 1:
            raise RetrievalRuntimeError("execution_requirement_api_identity_unresolved")
        return matches[0]

    def _validate_library_identity(self) -> None:
        if len(self.manifest_by_id) != len(self.library):
            raise RetrievalRuntimeError("retrieval_library_contains_duplicate_id")
        library_ids = set(self.manifest_by_id)
        raw_ids = set(self.raw_by_id)
        expected_ids = set(self.identity.eligible_resource_ids)
        if library_ids != raw_ids or library_ids != expected_ids:
            raise RetrievalRuntimeError("retrieval_library_identity_mismatch")
        for resource_id, manifest in self.manifest_by_id.items():
            raw = self.raw_by_id.get(resource_id)
            if not isinstance(raw, Mapping) or _resource_type(raw) != manifest.type.value:
                raise RetrievalRuntimeError("retrieval_manifest_type_mismatch")

    def _prepare_compatibility(self) -> None:
        for manifest in sorted(self.library, key=lambda item: item.id):
            availability = self.availability_by_id.get(manifest.id)
            raw = self.raw_by_id.get(manifest.id)
            if availability is None or not isinstance(raw, Mapping):
                raise RetrievalRuntimeError("retrieval_resource_identity_missing")
            decision = _compatibility_decision(
                raw,
                manifest,
                availability,
                self.requirements,
            )
            if self.runtime_incompatibility is not None and manifest.type == ManifestType.TOOL:
                failure = self.runtime_incompatibility(raw)
                if failure:
                    decision = decision.model_copy(update={
                        "verdict": "incompatible",
                        "reason_codes": tuple(sorted(set(decision.reason_codes) | {failure})),
                    })
            if manifest.type == ManifestType.MODEL:
                reasons = set(decision.reason_codes)
                type_specific = raw.get("type_specific")
                model_block = (
                    type_specific.get("model")
                    if isinstance(type_specific, Mapping)
                    else None
                )
                supports = (
                    model_block.get("supports")
                    if isinstance(model_block, Mapping)
                    else None
                )
                if isinstance(supports, Mapping):
                    if supports.get("json_mode") is True:
                        reasons.add("manifest_json_mode_supported")
                    elif supports.get("json_mode") is False:
                        reasons.add("manifest_json_mode_unsupported")
                    if any(
                        supports.get(name) is True
                        for name in ("json_schema", "structured_outputs", "structured_outputs_ok")
                    ):
                        reasons.add("manifest_native_structured_output_supported")
                decision = decision.model_copy(
                    update={"reason_codes": tuple(sorted(reasons))}
                )
            self.compatibility[manifest.id] = decision

    def _refresh_live_model_compatibility(self, resource_id: str) -> None:
        """Re-evaluate one Model using endpoint-bound liveness evidence."""

        manifest = self.manifest_by_id[resource_id]
        raw = self.raw_by_id[resource_id]
        availability = self.availability_by_id[resource_id].model_copy(
            update={
                "status": "available",
                "reason_code": "model_liveness_live_verified",
                "provider_compatibility": "compatible",
            }
        )
        decision = _compatibility_decision(
            raw,
            manifest,
            availability,
            self.requirements,
        )
        reasons = set(decision.reason_codes)
        reasons.add("provider_model_live_verified")
        self.compatibility[resource_id] = decision.model_copy(
            update={"reason_codes": tuple(sorted(reasons))}
        )

    def _refresh_applied_model_compatibility(self, resource_id: str) -> None:
        """Re-evaluate one Model using the explicit applied ready-state."""

        manifest = self.manifest_by_id[resource_id]
        raw = self.raw_by_id[resource_id]
        availability = self.availability_by_id[resource_id].model_copy(
            update={"provider_compatibility": "compatible"}
        )
        decision = _compatibility_decision(
            raw,
            manifest,
            availability,
            self.requirements,
        )
        reasons = set(decision.reason_codes)
        reasons.add("applied_model_ready_state")
        self.compatibility[resource_id] = decision.model_copy(
            update={"reason_codes": tuple(sorted(reasons))}
        )

    def _ensure_model_format_evidence(self, resource_id: str) -> None:
        requirement = self.output_format_requirement
        if requirement is None or not requirement.structured:
            return
        if resource_id in self.format_probe_attempted:
            return
        self.format_probe_attempted.add(resource_id)
        manifest = self.manifest_by_id[resource_id]
        if manifest.type != ManifestType.MODEL:
            return
        raw = self.raw_by_id[resource_id]
        model_id = _model_api_id(raw)
        if not model_id:
            current = self.compatibility[resource_id]
            self.compatibility[resource_id] = CandidateCompatibilityDecision(
                resource_id=current.resource_id,
                resource_type=current.resource_type,
                verdict="incompatible",
                reason_codes=tuple(
                    sorted({*current.reason_codes, "model_api_identity_missing"})
                ),
            )
            return
        evidence = self.capability_probe_service.probe(
            resource_id=resource_id,
            model_id=model_id,
            requirement=requirement,
            cost_ledger=self.cost_ledger,
            subtask_id=self.contract.revision.subtask_id,
            subtask_revision=self.contract.revision.subtask_revision,
        )
        if evidence.outcome != "not_checked":
            self.capability_probe_evidence[
                (resource_id, evidence.requirement_sha256)
            ] = evidence
        current = self.compatibility[resource_id]
        if current.verdict == "incompatible":
            return
        reasons = set(current.reason_codes)
        reasons.add(evidence.reason_code)
        type_specific = raw.get("type_specific")
        model_block = (
            type_specific.get("model") if isinstance(type_specific, Mapping) else None
        )
        supports = model_block.get("supports") if isinstance(model_block, Mapping) else None
        if isinstance(supports, Mapping):
            if supports.get("json_mode") is True:
                reasons.add("manifest_json_mode_supported")
            elif supports.get("json_mode") is False:
                reasons.add("manifest_json_mode_unsupported")
        if evidence.outcome == "unsupported":
            verdict = "incompatible"
        elif evidence.is_admissible:
            # Exact format evidence may discharge the only currently modelled
            # conditional requirement.  It must not erase an unrelated
            # metadata/readiness gap that remains unproven.
            verdict = (
                "compatible"
                if current.verdict in {"compatible", "conditional"}
                else current.verdict
            )
        elif current.verdict == "conditional":
            verdict = "conditional"
        else:
            verdict = "unknown"
        self.compatibility[resource_id] = CandidateCompatibilityDecision(
            resource_id=current.resource_id,
            resource_type=current.resource_type,
            verdict=verdict,
            reason_codes=tuple(sorted(reasons)),
        )

    def _ensure_model_liveness(self, resource_id: str) -> None:
        manifest = self.manifest_by_id[resource_id]
        if manifest.type != ManifestType.MODEL:
            return
        if (
            resource_id in self.model_liveness_evidence
            or resource_id in self.resolved_model_identities
        ):
            return
        raw = self.raw_by_id[resource_id]
        try:
            identity = resolve_model_identity(resource_id, raw)
            if self.model_readiness_authority == "applied_ready_state":
                availability = self.availability_by_id[resource_id]
                if (
                    availability.status != "available"
                    or availability.reason_code != "model_ready_state_ready"
                ):
                    raise _ResolutionFailure(
                        "model_not_in_applied_ready_state",
                        required_resource_id=resource_id,
                    )
                self.resolved_model_identities[resource_id] = identity
                self._refresh_applied_model_compatibility(resource_id)
                return
            evidence = self.model_liveness_probe_service.probe(
                identity=identity,
                cost_ledger=self.cost_ledger,
                subtask_id=self.contract.revision.subtask_id,
                subtask_revision=self.contract.revision.subtask_revision,
            )
        except (ModelIdentityError, ModelLivenessProbeError):
            raise
        self.resolved_model_identities[resource_id] = identity
        self.model_liveness_evidence[resource_id] = evidence
        if evidence.outcome == "permanent_unavailable":
            self.model_liveness_permanent_failures.add(resource_id)
            raise _ResolutionFailure(
                "model_liveness_permanent_unavailable",
                required_resource_id=resource_id,
            )
        if evidence.outcome == "transient_failure":
            self.model_liveness_transient_failures.add(resource_id)
            raise _ResolutionFailure(
                "model_liveness_transient_failure",
                required_resource_id=resource_id,
            )
        if evidence.outcome == "live_verified":
            self._refresh_live_model_compatibility(resource_id)

    def _ensure_temporary_tool_format_evidence(self, resource_id: str) -> None:
        if resource_id in self.temporary_tool_probe_attempted:
            return
        self.temporary_tool_probe_attempted.add(resource_id)
        manifest = self.manifest_by_id[resource_id]
        if manifest.type != ManifestType.MODEL:
            return
        raw = self.raw_by_id[resource_id]
        model_id = _model_api_id(raw)
        if not model_id:
            return
        requirement = system_role_requirement("temporary_tool")
        evidence = self.capability_probe_service.probe(
            resource_id=resource_id,
            model_id=model_id,
            requirement=requirement,
            cost_ledger=self.cost_ledger,
            subtask_id=self.contract.revision.subtask_id,
            subtask_revision=self.contract.revision.subtask_revision,
        )
        if evidence.outcome != "not_checked":
            self.capability_probe_evidence[
                (resource_id, evidence.requirement_sha256)
            ] = evidence

    def _rank(
        self,
        query_vector: Sequence[float],
        resource_type: str,
        *,
        query_role: Literal["base", "dependency_slot", "agent_base_model"],
        parent_resource_id: str | None = None,
        dependency_slot: str | None = None,
    ) -> list[tuple[Manifest, float, float, float | None, int]]:
        candidates: list[tuple[Manifest, float, float, float | None]] = []
        for manifest in self.library:
            if manifest.type.value != resource_type:
                continue
            from .model_selection import is_candidate_resource
            if not is_candidate_resource(self.raw_by_id[manifest.id]):
                continue
            if self.compatibility[manifest.id].verdict == "incompatible":
                continue
            capability_score = _cosine(query_vector, manifest.v_cap.embedding)
            constraint_score = (
                _cosine(self.profile.constraint_vector, manifest.v_con.embedding)
                if self.profile.constraint_vector is not None
                else None
            )
            if self.identity.active_strategy == "capability_only":
                score = capability_score
            else:
                if constraint_score is None:
                    raise RetrievalRuntimeError("retrieval_constraint_vector_missing")
                type_weights = {
                    "Model": (0.65, 0.35),
                    "Agent": (0.75, 0.25),
                    "Skill": (0.85, 0.15),
                    "Tool": (0.60, 0.40),
                    "Resource": (0.70, 0.30),
                    "Device": (0.70, 0.30),
                }
                capability_weight, constraint_weight = type_weights.get(
                    resource_type,
                    (0.70, 0.30),
                )
                score = (
                    capability_weight * capability_score
                    + constraint_weight * constraint_score
                )
            candidates.append((manifest, score, capability_score, constraint_score))
        candidates.sort(key=lambda item: (-item[1], item[0].id))
        ranked: list[tuple[Manifest, float, float, float | None, int]] = []
        for rank, (manifest, score, capability_score, constraint_score) in enumerate(
            candidates,
            start=1,
        ):
            self.score_evidence.append(
                CandidateScoreEvidence(
                    resource_id=manifest.id,
                    resource_type=manifest.type.value,
                    query_role=query_role,
                    rank=rank,
                    score=score,
                    capability_score=capability_score,
                    constraint_score=constraint_score,
                    parent_resource_id=parent_resource_id,
                    dependency_slot=dependency_slot,
                )
            )
            ranked.append((manifest, score, capability_score, constraint_score, rank))
        return ranked

    def _encode_local(
        self,
        text: str,
        *,
        operation: Literal["dependency_slot", "agent_base_model"],
        operation_key: str,
    ) -> tuple[float, ...]:
        for attempt in range(1, 4):
            try:
                vector = tuple(float(item) for item in self.local_text_encoder(text))
                if len(vector) != self.profile.dimension or any(
                    not math.isfinite(item) for item in vector
                ):
                    raise RetrievalRuntimeError("local_retrieval_vector_invalid")
                self.local_attempts.append(
                    LocalEncodingAttempt(
                        operation=operation,
                        operation_key=operation_key,
                        attempt=attempt,
                        outcome="success",
                    )
                )
                return vector
            except BaseException as exc:
                responsibility = str(
                    getattr(exc, "failure_responsibility", None)
                    or getattr(exc, "responsibility", None)
                    or FailureResponsibility.FRAMEWORK.value
                )
                retryable = bool(getattr(exc, "retryable", False))
                code = str(
                    getattr(exc, "error_code", None)
                    or getattr(exc, "failure_code", None)
                    or type(exc).__name__
                )
                infrastructure = (
                    responsibility == FailureResponsibility.INFRASTRUCTURE.value
                )
                self.local_attempts.append(
                    LocalEncodingAttempt(
                        operation=operation,
                        operation_key=operation_key,
                        attempt=attempt,
                        outcome=(
                            "infrastructure_failure"
                            if infrastructure
                            else "terminal_failure"
                        ),
                        failure_responsibility=responsibility,
                        failure_code=code,
                    )
                )
                if infrastructure and retryable and attempt < 3:
                    continue
                raise RetrievalPreparationError(
                    code,
                    responsibility=responsibility,
                    attempts=self.profile.retrieval_attempts,
                    response_received=False,
                ) from exc
        raise AssertionError("unreachable_local_encoding_retry_state")

    @staticmethod
    def _merge_resolution(target: _Resolution, source: _Resolution) -> None:
        for resource_id, entry in source.entries.items():
            current = target.entries.get(resource_id)
            if current is None or _ORIGIN_PRIORITY[entry.origin] < _ORIGIN_PRIORITY[current.origin]:
                target.entries[resource_id] = entry
        existing_edges = {
            (
                item.parent_resource_id,
                item.child_resource_id,
                item.requirement_kind,
                item.dependency_slot,
            )
            for item in target.edges
        }
        for edge in source.edges:
            identity = (
                edge.parent_resource_id,
                edge.child_resource_id,
                edge.requirement_kind,
                edge.dependency_slot,
            )
            if identity not in existing_edges:
                target.edges.append(edge)
                existing_edges.add(identity)
        existing_hints = {
            canonical_sha256(item) for item in target.optional_hints
        }
        for hint in source.optional_hints:
            identity = canonical_sha256(hint)
            if identity not in existing_hints:
                target.optional_hints.append(hint)
                existing_hints.add(identity)

    def _entry_score(self, manifest: Manifest) -> float:
        return _cosine(self.profile.capability_vector, manifest.v_cap.embedding)

    def _resolve_resource(
        self,
        resource_id: str,
        *,
        origin: CandidateOrigin,
        parent_resource_id: str | None,
        dependency_slot: str | None,
        score: float,
        rank: int,
        ancestors: tuple[str, ...],
    ) -> _Resolution:
        if resource_id in ancestors:
            raise _ResolutionFailure(
                "required_dependency_cycle",
                required_resource_id=resource_id,
            )
        manifest = self.manifest_by_id.get(resource_id)
        raw = self.raw_by_id.get(resource_id)
        if manifest is None or not isinstance(raw, Mapping):
            raise _ResolutionFailure(
                "required_dependency_missing",
                required_resource_id=resource_id,
            )
        from .model_selection import is_candidate_resource
        if not is_candidate_resource(raw):
            raise _ResolutionFailure("model_not_candidate", required_resource_id=resource_id)
        if self.compatibility[resource_id].verdict == "incompatible":
            raise _ResolutionFailure(
                "required_dependency_incompatible",
                required_resource_id=resource_id,
            )
        self._ensure_model_liveness(resource_id)
        self._ensure_model_format_evidence(resource_id)
        self._ensure_temporary_tool_format_evidence(resource_id)
        if self.compatibility[resource_id].verdict != "compatible":
            raise _ResolutionFailure(
                "required_dependency_compatibility_unproven",
                required_resource_id=resource_id,
            )
        resolution = _Resolution()
        resolution.entries[resource_id] = _CandidateEntry(
            resource_id=resource_id,
            resource_type=manifest.type.value,
            origin=origin,
            required_by_resource_id=parent_resource_id,
            dependency_slot=dependency_slot,
            score=float(score),
            rank=max(1, int(rank)),
        )
        required_ids, slots, hints = _required_dependency_declarations(raw)
        resolution.optional_hints.extend(hints)
        next_ancestors = (*ancestors, resource_id)

        for dependency_id in required_ids:
            dependency = self.manifest_by_id.get(dependency_id)
            if dependency is None:
                raise _ResolutionFailure(
                    "required_dependency_missing",
                    required_resource_id=dependency_id,
                )
            child = self._resolve_resource(
                dependency_id,
                origin=CandidateOrigin.EXPLICIT_DEPENDENCY,
                parent_resource_id=resource_id,
                dependency_slot=None,
                score=self._entry_score(dependency),
                rank=1,
                ancestors=next_ancestors,
            )
            self._merge_resolution(resolution, child)
            resolution.edges.append(
                CandidateDependencyEdge(
                    parent_resource_id=resource_id,
                    child_resource_id=dependency_id,
                    requirement_kind="explicit_id",
                    child_resource_type=dependency.type.value,
                    rank=1,
                )
            )

        for slot in slots:
            vector_key = (resource_id, slot.slot_id)
            query_vector = self._slot_vectors.get(vector_key)
            if query_vector is None:
                query_text = (
                    self.profile.artifact.capability_text
                    + "\nREQUIRED DEPENDENCY SLOT\n"
                    + slot.description
                )
                query_vector = self._encode_local(
                    query_text,
                    operation="dependency_slot",
                    operation_key=f"{resource_id}:{slot.slot_id}",
                )
                self._slot_vectors[vector_key] = query_vector
            resolved_any = False
            slot_resolution = _Resolution()
            for allowed_type in slot.allowed_types:
                # Dependency completion has its own declared per-slot bound.
                # Base retrieval quotas must not truncate required closure.
                limit = slot.top_k_per_type
                if limit <= 0:
                    continue
                ranked = self._rank(
                    query_vector,
                    allowed_type,
                    query_role="dependency_slot",
                    parent_resource_id=resource_id,
                    dependency_slot=slot.slot_id,
                )
                accepted = 0
                for candidate, candidate_score, _cap, _con, candidate_rank in ranked:
                    if candidate.id in next_ancestors:
                        continue
                    try:
                        child = self._resolve_resource(
                            candidate.id,
                            origin=CandidateOrigin.DEPENDENCY_SLOT,
                            parent_resource_id=resource_id,
                            dependency_slot=slot.slot_id,
                            score=candidate_score,
                            rank=candidate_rank,
                            ancestors=next_ancestors,
                        )
                    except _ResolutionFailure:
                        continue
                    self._merge_resolution(slot_resolution, child)
                    slot_resolution.edges.append(
                        CandidateDependencyEdge(
                            parent_resource_id=resource_id,
                            child_resource_id=candidate.id,
                            requirement_kind="dependency_slot",
                            dependency_slot=slot.slot_id,
                            child_resource_type=candidate.type.value,
                            rank=candidate_rank,
                        )
                    )
                    accepted += 1
                    resolved_any = True
                    if accepted >= limit:
                        break
            if not resolved_any:
                raise _ResolutionFailure(
                    "required_dependency_slot_unfilled",
                    dependency_slot=slot.slot_id,
                )
            self._merge_resolution(resolution, slot_resolution)

        if manifest.type == ManifestType.AGENT:
            query_vector = self._agent_vectors.get(resource_id)
            if query_vector is None:
                capability = raw.get("capability")
                capability = capability if isinstance(capability, Mapping) else {}
                public_agent_contract = {
                    "problem_space": capability.get("problem_space", ""),
                    "core_primitives": capability.get("core_primitives", []),
                    "domain_tags": capability.get("domain_tags", []),
                }
                query_text = (
                    self.profile.artifact.capability_text
                    + "\nAGENT PUBLIC CAPABILITY\n"
                    + canonical_json_bytes(public_agent_contract).decode("utf-8")
                )
                query_vector = self._encode_local(
                    query_text,
                    operation="agent_base_model",
                    operation_key=resource_id,
                )
                self._agent_vectors[resource_id] = query_vector
            model_ranked = self._rank(
                query_vector,
                "Model",
                query_role="agent_base_model",
                parent_resource_id=resource_id,
            )
            required_base_ids = tuple(
                dict.fromkeys(
                    resource_id
                    for requirement in self.contract.execution_requirements
                    if requirement.relation == "agent_base_model"
                    for resource_id in (self._required_resource_id(requirement),)
                    if resource_id is not None
                )
            )
            if len(required_base_ids) > 1:
                raise _ResolutionFailure("multiple_required_agent_base_models")
            if required_base_ids:
                required_base_id = required_base_ids[0]
                model_ranked = sorted(
                    model_ranked,
                    key=lambda item: (item[0].id != required_base_id, item[4]),
                )
            selected_model: tuple[Manifest, float, int, _Resolution] | None = None
            for model_manifest, model_score, _cap, _con, model_rank in model_ranked:
                if required_base_ids and model_manifest.id != required_base_ids[0]:
                    continue
                try:
                    child = self._resolve_resource(
                        model_manifest.id,
                        origin=CandidateOrigin.AGENT_BASE_MODEL,
                        parent_resource_id=resource_id,
                        dependency_slot=None,
                        score=model_score,
                        rank=model_rank,
                        ancestors=next_ancestors,
                    )
                except _ResolutionFailure:
                    continue
                selected_model = (model_manifest, model_score, model_rank, child)
                break
            if selected_model is None:
                raise _ResolutionFailure("agent_base_model_unavailable")
            model_manifest, _model_score, model_rank, child = selected_model
            self._merge_resolution(resolution, child)
            resolution.edges.append(
                CandidateDependencyEdge(
                    parent_resource_id=resource_id,
                    child_resource_id=model_manifest.id,
                    requirement_kind="agent_base_model",
                    child_resource_type="Model",
                    rank=model_rank,
                )
            )
        return resolution

    def _contract_coverage(self, entries: Mapping[str, _CandidateEntry]) -> bool:
        if not self.requirements:
            return True
        selected = [self.manifest_by_id[item] for item in entries]
        selected_models = [item for item in selected if item.type == ManifestType.MODEL]
        selected_tools = [item for item in selected if item.type == ManifestType.TOOL]
        for feature in self.requirements.get("required_model_features", ()):
            satisfied = False
            for manifest in selected_models:
                raw = self.raw_by_id[manifest.id]
                specific = raw.get("type_specific")
                model = specific.get("model") if isinstance(specific, Mapping) else {}
                supports = model.get("supports") if isinstance(model, Mapping) else {}
                if isinstance(supports, Mapping) and supports.get(str(feature)) is True:
                    satisfied = True
                    break
            if not satisfied:
                return False
        from retrieval_profiles import model_context_tokens, model_modality_support
        selected_model_facts = [
            ((self.raw_by_id[item.id].get("type_specific") or {}).get("model") or {})
            for item in selected_models
        ]
        for direction in ("input", "output"):
            for modality in self.requirements.get(f"{direction}_modalities", ()):
                if not any(model_modality_support(facts, str(modality), direction) is True
                           for facts in selected_model_facts):
                    return False
        minimum = self.requirements.get("min_context_tokens")
        if isinstance(minimum, int) and not isinstance(minimum, bool) and minimum > 0:
            if not any((model_context_tokens(facts) or 0) >= minimum for facts in selected_model_facts):
                return False
        required_runtime = str(self.requirements.get("required_runtime") or "").strip().lower()
        if required_runtime and not any(
            str((self.raw_by_id[item.id].get("execution") or {}).get("runtime") or "")
            .strip()
            .lower()
            == required_runtime
            for item in selected_tools
        ):
            return False
        required_input_kinds = {
            str(item).strip().lower().replace("-", "_")
            for item in self.requirements.get("input_kinds", ())
            if str(item).strip()
        }
        if required_input_kinds and not all(
            any(kind in _manifest_input_kinds(self.raw_by_id[item.id]) for item in selected_tools)
            for kind in required_input_kinds
        ):
            return False
        return True

    def _required_tool_operations(self) -> frozenset[str]:
        """Return operation families explicitly required by the node contract.

        This is a deterministic projection over the Planner contract. It is
        intentionally benchmark agnostic and only reserves a Tool when the
        contract names an operation or an external-evidence acquisition need.
        """
        large_text_handle = any(
            item.handle_available
            and item.content_acquisition_required
            and item.coverage_status != "complete"
            and item.artifact_type in {"plaintext", "markdown", "json", "csv", "code", "file"}
            and item.original_bytes is not None
            and item.original_bytes > 256 * 1024
            for item in getattr(self.contract, "public_context_descriptors", ())
        )
        acquisition = getattr(self.contract, "evidence_acquisition_operations", ())
        if self.contract.required_operation_kinds or acquisition:
            operations = set(self.contract.required_operation_kinds) | set(acquisition)
            content_text = "\n".join([
                getattr(self.contract, "description", ""), getattr(self.contract, "expected_output", ""),
                *getattr(self.contract, "required_content", ()), *getattr(self.contract, "acceptance_criteria", ()),
                *getattr(self.contract, "grounding_requirements", ()),
            ])
            has_materials = bool(
                getattr(self.contract, "public_context_descriptors", ())
                or getattr(self.contract, "dependency_inputs", ())
            )
            if requires_external_grounding(
                content_text, has_authorized_materials=has_materials,
                declared_grounding=bool(self.contract.grounding_requirements),
                evidence_source_scope=getattr(self.contract, "evidence_source_scope", None),
            ):
                operations.add("fetch_web_resource")
                if not requests_external_content(content_text):
                    operations.add("search_web")
            if "search_web" in operations and self.contract.grounding_requirements:
                # Reserve source access alongside discovery. The Compiler may
                # still decide that a search record itself is sufficient; the
                # fetch operation is available when source text must be checked.
                operations.add("fetch_web_resource")
            if large_text_handle:
                operations.add("python_execution")
            return frozenset(operations)
        text_parts = [self.contract.description, self.contract.expected_output]
        text_parts.extend(self.contract.required_content)
        text_parts.extend(self.contract.grounding_requirements)
        text_parts.extend(self.contract.acceptance_criteria)
        operations = set(normalize_task_general_operation_kinds("\n".join(text_parts)))
        if getattr(self.contract, "evidence_source_scope", None) == "supplied_materials":
            # Candidate hints do not turn local source inspection into web acquisition.
            operations.difference_update({"search_web", "fetch_web_resource"})
        has_authorized_materials = bool(
            self.contract.public_context_descriptors or self.contract.dependency_inputs
        )
        if requires_external_grounding(
            "\n".join(text_parts),
            has_authorized_materials=has_authorized_materials,
            declared_grounding=bool(self.contract.grounding_requirements),
            evidence_source_scope=getattr(self.contract, "evidence_source_scope", None),
        ):
            operations.add("search_web")
            if self.contract.grounding_requirements:
                operations.add("fetch_web_resource")
        if large_text_handle:
            # Keep bounded local processing available for large inputs.  It is
            # an optional candidate, not a forced step in the Compiler plan.
            operations.add("python_execution")
        return frozenset(operations)

    def _required_operation_candidate_ids(
        self,
        rankings: Sequence[tuple[Manifest, float, float, float | None, int]],
    ) -> tuple[str, ...]:
        required = self._required_tool_operations()
        if not required:
            return ()
        selected: list[str] = []
        for operation in sorted(required):
            match = next(
                (
                    manifest.id
                    for manifest, _score, _cap, _con, _rank in rankings
                    if operation
                    in set(tool_allowed_operation_kinds(self.raw_by_id[manifest.id]))
                    | set(manifest_capability_operations(self.raw_by_id[manifest.id]))
                ),
                None,
            )
            if match is not None and match not in selected:
                selected.append(match)
        return tuple(selected)

    def build(self) -> FrozenCandidatePoolResult:
        base_rankings = {
            resource_type: self._rank(
                self.profile.capability_vector,
                resource_type,
                query_role="base",
            )
            for resource_type in FORMAL_TYPE_ORDER
            if self.identity.quota_map.get(resource_type, 0) > 0
        }
        if "Model" in base_rankings:
            base_rankings["Model"] = _cost_diverse_model_rankings(
                base_rankings["Model"],
                self.raw_by_id,
                quota=self.identity.quota_map.get("Model", 0),
            )
        global_resolution = _Resolution()
        base_ids: dict[str, list[str]] = {item: [] for item in FORMAL_TYPE_ORDER}
        eligible_counts = {
            resource_type: len(base_rankings.get(resource_type, ()))
            for resource_type in FORMAL_TYPE_ORDER
        }
        for resource_type in FORMAL_TYPE_ORDER:
            quota = self.identity.quota_map.get(resource_type, 0)
            if quota <= 0:
                continue
            for manifest, score, _cap, _con, rank in base_rankings.get(resource_type, ()):
                if len(base_ids[resource_type]) >= quota:
                    break
                try:
                    resolution = self._resolve_resource(
                        manifest.id,
                        origin=CandidateOrigin.RETRIEVAL,
                        parent_resource_id=None,
                        dependency_slot=None,
                        score=score,
                        rank=rank,
                        ancestors=(),
                    )
                except _ResolutionFailure as exc:
                    self.dependency_rejections.append(
                        DependencyRejection(
                            parent_resource_id=manifest.id,
                            parent_resource_type=manifest.type.value,
                            reason_code=exc.reason_code,
                            required_resource_id=exc.required_resource_id,
                            dependency_slot=exc.dependency_slot,
                        )
                    )
                    continue
                resolution.entries[manifest.id] = _CandidateEntry(
                    resource_id=manifest.id,
                    resource_type=manifest.type.value,
                    origin=CandidateOrigin.RETRIEVAL,
                    required_by_resource_id=None,
                    dependency_slot=None,
                    score=score,
                    rank=rank,
                )
                self._merge_resolution(global_resolution, resolution)
                base_ids[resource_type].append(manifest.id)

        # File delivery and in-place workspace effects are contract obligations.
        # Admit one manifest-proven materializer for each distinct
        # required file delivery after the ordinary typed quota so the contract
        # cannot be silently truncated by an unrelated top-k ranking.  The
        # selected resource still passes the same availability, compatibility,
        # dependency, and runtime closure checks as every retrieval candidate.
        tool_rankings = base_rankings.get("Tool", ())
        tool_rank_by_id = {
            manifest.id: (score, rank)
            for manifest, score, _cap, _con, rank in tool_rankings
        }
        delivery_ids = tuple(dict.fromkeys((
            *_contract_delivery_candidate_ids(self.contract, tool_rankings, self.raw_by_id),
            *_contract_workspace_effect_candidate_ids(self.contract, tool_rankings, self.raw_by_id),
        )))
        for resource_id in delivery_ids:
            if resource_id in global_resolution.entries:
                continue
            score, rank = tool_rank_by_id[resource_id]
            try:
                resolution = self._resolve_resource(
                    resource_id,
                    origin=CandidateOrigin.CONTRACT_DELIVERY,
                    parent_resource_id=None,
                    dependency_slot=None,
                    score=score,
                    rank=rank,
                    ancestors=(),
                )
            except _ResolutionFailure as exc:
                self.dependency_rejections.append(
                    DependencyRejection(
                        parent_resource_id=resource_id,
                        parent_resource_type="Tool",
                        reason_code=exc.reason_code,
                        required_resource_id=exc.required_resource_id,
                        dependency_slot=exc.dependency_slot,
                    )
                )
                continue
            resolution.entries[resource_id] = _CandidateEntry(
                resource_id=resource_id,
                resource_type="Tool",
                origin=CandidateOrigin.CONTRACT_DELIVERY,
                required_by_resource_id=None,
                dependency_slot=None,
                score=score,
                rank=rank,
            )
            self._merge_resolution(global_resolution, resolution)

        # Preserve at least one semantically compatible Tool for each operation
        # that the contract explicitly requires. This is additive to the typed
        # quota and keeps vector ranking responsible for choosing among tools;
        # it only prevents a required operation from being cut off by top-k.
        required_operation_ids = tuple(dict.fromkeys((
            *self._required_operation_candidate_ids(tool_rankings),
            *_contract_material_access_candidate_ids(
                self.contract, tool_rankings, self.raw_by_id,
            ),
            *_contract_input_parser_candidate_ids(
                self.contract, tool_rankings, self.raw_by_id,
                candidate_ids=tuple(global_resolution.entries),
                # Source acquisition needs an optional body-reading route as
                # well as a download receipt. Reserve one eligible static-web
                # reader before any concrete downloaded input exists. Format
                # readers for attachments/previews remain additive; Compiler
                # chooses which reader matches the actual acquired material.
                required_formats=("html",) if (
                    self.contract.grounding_requirements
                    and "fetch_web_resource" in self._required_tool_operations()
                ) else (),
                source_acquisition=bool(
                    self.contract.grounding_requirements
                    and "fetch_web_resource" in self._required_tool_operations()
                ),
            ),
        )))
        for resource_id in required_operation_ids:
            if resource_id in global_resolution.entries:
                continue
            score, rank = tool_rank_by_id[resource_id]
            try:
                resolution = self._resolve_resource(
                    resource_id,
                    origin=CandidateOrigin.REQUIRED_OPERATION,
                    parent_resource_id=None,
                    dependency_slot=None,
                    score=score,
                    rank=rank,
                    ancestors=(),
                )
            except _ResolutionFailure as exc:
                self.dependency_rejections.append(
                    DependencyRejection(
                        parent_resource_id=resource_id,
                        parent_resource_type="Tool",
                        reason_code=exc.reason_code,
                        required_resource_id=exc.required_resource_id,
                        dependency_slot=exc.dependency_slot,
                    )
                )
                continue
            resolution.entries[resource_id] = _CandidateEntry(
                resource_id=resource_id,
                resource_type="Tool",
                origin=CandidateOrigin.REQUIRED_OPERATION,
                required_by_resource_id=None,
                dependency_slot=None,
                score=score,
                rank=rank,
            )
            self._merge_resolution(global_resolution, resolution)

        # Resource-Aware Planner evidence is admitted only before freeze and
        # only after the same availability, compatibility and dependency
        # closure checks as semantic retrieval.  It is additive, so it never
        # displaces a typed base-quota candidate.
        evidence_ids = tuple(dict.fromkeys(self.contract.planner_capability_evidence))
        evidence_types = {
            self.manifest_by_id[resource_id].type.value
            for resource_id in evidence_ids
            if resource_id in self.manifest_by_id
        }
        for resource_type in sorted(evidence_types):
            if resource_type not in base_rankings:
                base_rankings[resource_type] = self._rank(
                    self.profile.capability_vector,
                    resource_type,
                    query_role="base",
                )
        rank_by_id = {
            manifest.id: (score, rank)
            for rankings in base_rankings.values()
            for manifest, score, _cap, _con, rank in rankings
        }
        for resource_id in evidence_ids:
            if resource_id in global_resolution.entries:
                continue
            manifest = self.manifest_by_id.get(resource_id)
            ranked = rank_by_id.get(resource_id)
            if (
                manifest is None
                or ranked is None
                or self.compatibility[resource_id].verdict == "incompatible"
            ):
                continue
            score, rank = ranked
            try:
                resolution = self._resolve_resource(
                    resource_id,
                    origin=CandidateOrigin.PLANNER_CAPABILITY_EVIDENCE,
                    parent_resource_id=None,
                    dependency_slot=None,
                    score=score,
                    rank=rank,
                    ancestors=(),
                )
            except _ResolutionFailure:
                continue
            resolution.entries[resource_id] = _CandidateEntry(
                resource_id=resource_id,
                resource_type=manifest.type.value,
                origin=CandidateOrigin.PLANNER_CAPABILITY_EVIDENCE,
                required_by_resource_id=None,
                dependency_slot=None,
                score=score,
                rank=rank,
            )
            self._merge_resolution(global_resolution, resolution)

        required_ids = tuple(
            dict.fromkeys(
                resource_id
                for requirement in self.contract.execution_requirements
                for resource_id in (self._required_resource_id(requirement),)
                if resource_id is not None
            )
        )
        for resource_id in required_ids:
            if resource_id in global_resolution.entries:
                continue
            manifest = self.manifest_by_id[resource_id]
            if manifest.type.value not in base_rankings:
                base_rankings[manifest.type.value] = self._rank(
                    self.profile.capability_vector,
                    manifest.type.value,
                    query_role="base",
                )
                rank_by_id.update(
                    {
                        item.id: (score, rank)
                        for item, score, _cap, _con, rank in base_rankings[manifest.type.value]
                    }
                )
            ranked = rank_by_id.get(resource_id)
            if ranked is None:
                raise RetrievalRuntimeError("execution_requirement_resource_not_eligible")
            score, rank = ranked
            try:
                resolution = self._resolve_resource(
                    resource_id,
                    origin=CandidateOrigin.USER_EXECUTION_REQUIREMENT,
                    parent_resource_id=None,
                    dependency_slot=None,
                    score=score,
                    rank=rank,
                    ancestors=(),
                )
            except _ResolutionFailure as exc:
                raise RetrievalRuntimeError(
                    f"execution_requirement_resource_rejected:{exc.reason_code}"
                ) from exc
            resolution.entries[resource_id] = _CandidateEntry(
                resource_id=resource_id,
                resource_type=manifest.type.value,
                origin=CandidateOrigin.USER_EXECUTION_REQUIREMENT,
                required_by_resource_id=None,
                dependency_slot=None,
                score=score,
                rank=rank,
            )
            self._merge_resolution(global_resolution, resolution)

        # Apply composition closure after every candidate admission route,
        # including Planner evidence and explicit execution requirements.
        composition_rankings = base_rankings.get("Tool", ())
        composition_ranks = {
            manifest.id: (score, rank)
            for manifest, score, _cap, _con, rank in composition_rankings
        }
        for resource_id in _generated_program_materializer_ids(
            tuple(global_resolution.entries), composition_rankings, self.raw_by_id,
        ):
            score, rank = composition_ranks[resource_id]
            try:
                resolution = self._resolve_resource(
                    resource_id, origin=CandidateOrigin.CONTRACT_DELIVERY,
                    parent_resource_id=None, dependency_slot=None,
                    score=score, rank=rank, ancestors=(),
                )
            except _ResolutionFailure as exc:
                self.dependency_rejections.append(DependencyRejection(
                    parent_resource_id=resource_id, parent_resource_type="Tool",
                    reason_code=exc.reason_code, required_resource_id=exc.required_resource_id,
                    dependency_slot=exc.dependency_slot,
                ))
                continue
            self._merge_resolution(global_resolution, resolution)

        # The first resolved model proves the Agent is runnable; it is not the
        # Compiler's final binding. Reuse admitted models and their existing
        # Agent-specific ranking evidence as alternatives, without extra calls.
        _expand_admitted_agent_model_choices(
            global_resolution, score_evidence=self.score_evidence,
            compatibility=self.compatibility,
            explicit_model_binding=any(
                item.relation == "agent_base_model" for item in self.contract.execution_requirements
            ),
        )

        ordered_entries: list[_CandidateEntry] = []
        seen: set[str] = set()
        for resource_type in FORMAL_TYPE_ORDER:
            for resource_id in base_ids[resource_type]:
                if resource_id not in seen:
                    ordered_entries.append(global_resolution.entries[resource_id])
                    seen.add(resource_id)
            additions = [
                item
                for item in global_resolution.entries.values()
                if item.resource_type == resource_type and item.resource_id not in seen
            ]
            additions.sort(
                key=lambda item: (
                    _ORIGIN_PRIORITY[item.origin],
                    item.required_by_resource_id or "",
                    item.dependency_slot or "",
                    item.rank,
                    item.resource_id,
                )
            )
            for item in additions:
                ordered_entries.append(item)
                seen.add(item.resource_id)

        snapshot = CandidatePoolSnapshot(
            revision=self.contract.revision,
            candidates=tuple(
                CandidateResourceRef(
                    resource_id=item.resource_id,
                    resource_type=item.resource_type,
                    origin=item.origin,
                    required_by_resource_id=item.required_by_resource_id,
                    dependency_slot=item.dependency_slot,
                )
                for item in ordered_entries
            ),
            pool_sha256=self.identity.pool_sha256,
            index_sha256=self.identity.index_sha256,
            policy_sha256=self.identity.policy_sha256,
            availability_sha256=self.identity.availability_sha256,
        )
        compiler_priority_roots = set(
            (*delivery_ids, *required_operation_ids, *evidence_ids, *required_ids)
        )
        compiler_priority_ids = set(compiler_priority_roots)
        changed = True
        while changed:
            changed = False
            for edge in required_candidate_dependency_edges(global_resolution.edges):
                if (
                    edge.parent_resource_id in compiler_priority_ids
                    and edge.child_resource_id not in compiler_priority_ids
                ):
                    compiler_priority_ids.add(edge.child_resource_id)
                    changed = True
        compiler_priority_candidate_ids = tuple(
            item.resource_id
            for item in ordered_entries
            if item.resource_id in compiler_priority_ids
        )
        final_counts = {
            resource_type: sum(
                1 for item in ordered_entries if item.resource_type == resource_type
            )
            for resource_type in FORMAL_TYPE_ORDER
        }
        quota_evidence = tuple(
            TypeQuotaEvidence(
                resource_type=resource_type,
                quota=self.identity.quota_map[resource_type],
                eligible_count=eligible_counts[resource_type],
                base_count=len(base_ids[resource_type]),
                final_count=final_counts[resource_type],
                shortfall=max(
                    self.identity.quota_map[resource_type] - len(base_ids[resource_type]),
                    0,
                ),
                quota_coverage=(
                    len(base_ids[resource_type])
                    >= min(self.identity.quota_map[resource_type], eligible_counts[resource_type])
                ),
            )
            for resource_type in FORMAL_TYPE_ORDER
        )
        model_quota = self.identity.quota_map.get("Model", 0)
        # Typed quotas cap base retrieval candidates; they are not minimum
        # bundle sizes. Preserve strict compatibility and dependency admission,
        # but allow a smaller pool when at least one Model can be resolved.
        # If none of the potentially eligible Models resolves, retain the
        # existing failure; all-hard-incompatible pools keep audited shortfalls.
        minimum_model_count = min(1, model_quota, eligible_counts.get("Model", 0))
        if len(base_ids.get("Model", ())) < minimum_model_count:
            transient = bool(self.model_liveness_transient_failures)
            raise RetrievalPreparationError(
                (
                    "model_liveness_quota_unavailable"
                    if transient
                    else "model_resource_quota_unavailable"
                ),
                responsibility=(
                    FailureResponsibility.INFRASTRUCTURE.value
                    if transient
                    else FailureResponsibility.RESEARCH.value
                ),
                attempts=self.profile.retrieval_attempts,
                response_received=False,
            )
        per_type: list[PerTypeConfidenceStatistics] = []
        for resource_type in FORMAL_TYPE_ORDER:
            entries = [item for item in ordered_entries if item.resource_type == resource_type]
            scores = [item.score for item in entries]
            per_type.append(
                PerTypeConfidenceStatistics(
                    resource_type=resource_type,
                    candidate_count=len(entries),
                    quota=self.identity.quota_map[resource_type],
                    contract_compatible_count=len(entries),
                    dependency_covered_count=len(entries),
                    score_min=min(scores) if scores else None,
                    score_mean=(sum(scores) / len(scores)) if scores else None,
                    score_max=max(scores) if scores else None,
                )
            )
        raw_capability_cosine = (
            _cosine(self.profile.raw_query_vector, self.profile.capability_vector)
            if self.profile.raw_query_vector is not None
            else None
        )
        confidence = RetrievalConfidenceEvidence(
            revision=self.contract.revision,
            candidate_pool_sha256=snapshot.candidate_pool_sha256,
            per_type=tuple(per_type),
            quota_coverage=all(
                item.quota_coverage for item in quota_evidence if item.quota > 0
            ),
            contract_coverage=self._contract_coverage(global_resolution.entries),
            dependency_coverage=True,
            original_query_hyde_consistency=(
                max(0.0, min(1.0, (raw_capability_cosine + 1.0) / 2.0))
                if raw_capability_cosine is not None
                else None
            ),
        )
        return FrozenCandidatePoolResult(
            runtime_identity=self.identity,
            contract_projection=self.contract,
            ideal_resource_profile=self.profile.artifact,
            retrieval_attempts=self.profile.retrieval_attempts,
            candidate_pool_snapshot=snapshot,
            base_candidate_ids_by_type={
                resource_type: tuple(base_ids[resource_type])
                for resource_type in FORMAL_TYPE_ORDER
            },
            compiler_priority_candidate_ids=compiler_priority_candidate_ids,
            type_quota_evidence=quota_evidence,
            candidate_score_evidence=tuple(self.score_evidence),
            dependency_edges=tuple(
                sorted(
                    global_resolution.edges,
                    key=lambda item: (
                        item.parent_resource_id,
                        item.dependency_slot or "",
                        item.rank,
                        item.child_resource_id,
                    ),
                )
            ),
            compatibility_decisions=tuple(
                self.compatibility[item]
                for item in sorted(self.compatibility)
            ),
            capability_probe_evidence=tuple(
                self.capability_probe_evidence[item]
                for item in sorted(self.capability_probe_evidence)
            ),
            resolved_model_identities=tuple(
                self.resolved_model_identities[item.resource_id]
                for item in ordered_entries
                if item.resource_type == ManifestType.MODEL.value
            ),
            model_liveness_evidence=tuple(
                self.model_liveness_evidence[item]
                for item in sorted(self.model_liveness_evidence)
            ),
            model_readiness_authority=self.model_readiness_authority,
            optional_dependency_hints=tuple(
                sorted(
                    global_resolution.optional_hints,
                    key=lambda item: (
                        item.parent_resource_id,
                        item.hint_kind,
                        item.resource_id or "",
                        item.dependency_slot or "",
                    ),
                )
            ),
            dependency_rejections=tuple(self.dependency_rejections),
            local_encoding_attempts=tuple(self.local_attempts),
            confidence_evidence=confidence,
        )


ProfileGenerator = Callable[..., Mapping[str, Any]]
ProfileEncoder = Callable[[IdealResourceProfileArtifact], QueryRetrievalProfile]


def _default_profile_generator(
    query_text: str,
    *,
    cost_ledger: RunCostLedger | None,
    revision: SubtaskRevisionRef,
    transport: SyncModelTransportPort,
    response_mode: StructuredResponseModeInput,
    model_id: str | None = None,
    reasoning_effort: str | None = None,
    max_output_tokens: int | None = None,
    source_seal_path: Path | None = None,
    defer_embeddability_validation: bool = False,
) -> Mapping[str, Any]:
    import retrieve
    from .profiler_protocol import ProfilerInputEnvelopeV1, ProfilerOutputV2

    ProfilerInputEnvelopeV1.model_validate_json(query_text)
    generated = retrieve.generate_hyde_profile_text(
        query_text,
        cost_ledger=cost_ledger,
        subtask_id=revision.subtask_id,
        subtask_revision=revision.subtask_revision,
        transport=transport,
        response_mode=response_mode,
        model_id=model_id,
        reasoning_effort=reasoning_effort,
        require_typed_input=True,
        max_output_tokens=max_output_tokens,
        source_seal_path=source_seal_path,
    )
    generation_history: list[dict[str, Any]] = [
        {
            "attempt": 1,
            "response_sha256": (generated.get("metadata") or {}).get(
                "response_sha256"
            ),
        }
    ]
    output = ProfilerOutputV2.model_validate(
        {
            "capability_text": generated.get("capability_text"),
            "constraint_text": generated.get("constraint_text"),
            "think": generated.get("think"),
        }
    )
    if defer_embeddability_validation:
        metadata = dict(generated.get("metadata") or {})
        metadata.update(
            {
                "deterministic_validation": {
                    "schema_valid": True,
                    "english_valid": True,
                    "think_valid": True,
                    "embeddable": False,
                },
                "embeddability_status": "deferred_to_embedding_candidate_evaluation",
                "semantic_generation_attempt_count": 1,
                "semantic_generation_attempt_limit": 2,
                "generation_history": generation_history,
            }
        )
        return {
            "capability_text": output.capability_text,
            "constraint_text": output.constraint_text,
            "think": output.think,
            "metadata": metadata,
        }
    if retrieve.profiler_output_is_embeddable(output):
        metadata = dict(generated.get("metadata") or {})
        metadata.update(
            {
                "deterministic_validation": {
                    "schema_valid": True,
                    "english_valid": True,
                    "think_valid": True,
                    "embeddable": True,
                },
                "semantic_generation_attempt_count": 1,
                "semantic_generation_attempt_limit": 2,
                "generation_history": generation_history,
            }
        )
        return {
            "capability_text": output.capability_text,
            "constraint_text": output.constraint_text,
            "think": output.think,
            "metadata": metadata,
        }
    revision_diagnostics = {
        "failure_code": "profiler_profile_not_embeddable",
        "instruction": (
            "Shorten both fields without dropping any declared requirement, "
            "literal identifier, interface, or acceptance constraint."
        ),
    }
    initial_model_attempts = int(
        (generated.get("metadata") or {}).get("model_attempt_count") or 1
    )
    if initial_model_attempts >= 2:
        raise RetrievalRuntimeError(
            "profiler_profile_not_embeddable",
            responsibility="research",
        )
    revised = retrieve.generate_hyde_profile_text(
        query_text,
        cost_ledger=cost_ledger,
        subtask_id=revision.subtask_id,
        subtask_revision=revision.subtask_revision,
        transport=transport,
        response_mode=response_mode,
        model_id=model_id,
        reasoning_effort=reasoning_effort,
        require_typed_input=True,
        max_output_tokens=max_output_tokens,
        correction_diagnostics=revision_diagnostics,
        model_attempt_limit=1,
        source_seal_path=source_seal_path,
    )
    revised_output = ProfilerOutputV2.model_validate(
        {
            "capability_text": revised.get("capability_text"),
            "constraint_text": revised.get("constraint_text"),
            "think": revised.get("think"),
        }
    )
    if not retrieve.profiler_output_is_embeddable(revised_output):
        raise RetrievalRuntimeError(
            "profiler_profile_not_embeddable",
            responsibility="research",
        )
    generation_history.append(
        {
            "attempt": 2,
            "response_sha256": (revised.get("metadata") or {}).get(
                "response_sha256"
            ),
        }
    )
    metadata = dict(revised.get("metadata") or {})
    metadata.update(
        {
            "deterministic_validation": {
                "schema_valid": True,
                "english_valid": True,
                "think_valid": True,
                "embeddable": True,
            },
            "semantic_generation_attempt_count": 2,
            "semantic_generation_attempt_limit": 2,
            "generation_history": generation_history,
        }
    )
    return {
        "capability_text": revised_output.capability_text,
        "constraint_text": revised_output.constraint_text,
        "think": revised_output.think,
        "metadata": metadata,
    }


def _default_profile_encoder(
    artifact: IdealResourceProfileArtifact,
) -> QueryRetrievalProfile:
    import retrieve

    capability_vector = retrieve.encode_query(
        artifact.capability_text,
        role="capability",
    )
    constraint_vector = retrieve.encode_query(
        artifact.constraint_text,
        role="constraint",
    )
    dim = len(capability_vector)
    if len(constraint_vector) != dim:
        raise RetrievalRuntimeError("retrieval_profile_vector_dimension_mismatch")
    return QueryRetrievalProfile(
        capability=Vector(embedding=capability_vector, dim=dim),
        constraint=Vector(embedding=constraint_vector, dim=dim),
        raw_query=None,
        capability_text=artifact.capability_text,
        constraint_text=artifact.constraint_text,
        raw_query_text=artifact.raw_query_text,
        hard_requirements=dict(artifact.explicit_hard_requirements),
        profile_version=artifact.prompt_version,
        generation_metadata={
            "status": "generated",
            "embedding_strategy": "capability_and_constraint",
            "model_accounting_reference": artifact.model_accounting_reference,
        },
    )


def _default_local_text_encoder(text: str) -> Sequence[float]:
    import retrieve

    return retrieve.encode_query(text)


class _ProfileCacheEntry:
    def __init__(self, contract_sha256: str) -> None:
        self.contract_sha256 = contract_sha256
        self.in_flight = True
        self.result: EncodedIdealResourceProfile | None = None
        self.failure: RetrievalPreparationError | None = None


class _CandidatePoolCacheEntry:
    def __init__(self, contract_sha256: str, input_sha256: str) -> None:
        self.contract_sha256 = contract_sha256
        self.input_sha256 = input_sha256
        self.in_flight = True
        self.result: FrozenCandidatePoolResult | None = None
        self.failure: RetrievalPreparationError | None = None


class RetrievalCoordinator:
    """Single-flight, terminally cached retrieval coordinator for one run."""

    def __init__(
        self,
        runtime_identity: RetrievalRuntimeIdentity,
        *,
        profile_generator: ProfileGenerator | None = None,
        profile_encoder: ProfileEncoder | None = None,
        local_text_encoder: Callable[[str], Sequence[float]] | None = None,
        prompt_text: str | None = None,
        prompt_version: str | None = None,
        sync_model_transport: SyncModelTransportPort | None = None,
        capability_probe_service: ExactCapabilityProbeService | None = None,
        model_liveness_probe_service: ModelLivenessProbeService | None = None,
        hyde_response_mode: StructuredResponseModeInput = "native_strict_schema",
        model_readiness_authority: Literal[
            "live_probe", "applied_ready_state"
        ] = "live_probe",
        runtime_incompatibility: Callable[[Mapping[str, Any]], str | None] | None = None,
    ) -> None:
        self.runtime_identity = runtime_identity
        self._runtime_incompatibility = runtime_incompatibility
        self._model_readiness_authority = model_readiness_authority
        self._hyde_response_mode: StructuredResponseMode = normalize_structured_response_mode(
            hyde_response_mode
        )
        if profile_generator is None:
            if sync_model_transport is not None:
                sync_model_transport = require_sync_model_transport(sync_model_transport)

                def bound_profile_generator(
                    query_text: str,
                    *,
                    cost_ledger: RunCostLedger | None,
                    revision: SubtaskRevisionRef,
                ) -> Mapping[str, Any]:
                    return _default_profile_generator(
                        query_text,
                        cost_ledger=cost_ledger,
                        revision=revision,
                        transport=sync_model_transport,
                        response_mode=self._hyde_response_mode,
                    )
            else:
                # Explicit compatibility construction for offline/legacy APIs.
                # Formal main always injects the shared transport bundle.
                def bound_profile_generator(
                    query_text: str,
                    *,
                    cost_ledger: RunCostLedger | None,
                    revision: SubtaskRevisionRef,
                ) -> Mapping[str, Any]:
                    import retrieve

                    return retrieve.generate_hyde_profile_text(
                        query_text,
                        cost_ledger=cost_ledger,
                        subtask_id=revision.subtask_id,
                        subtask_revision=revision.subtask_revision,
                        response_mode=self._hyde_response_mode,
                        require_typed_input=True,
                    )

            self._profile_generator = bound_profile_generator
        else:
            self._profile_generator = profile_generator
        self._profile_encoder = profile_encoder or _default_profile_encoder
        self._local_text_encoder = local_text_encoder or _default_local_text_encoder
        self._capability_probe_service = (
            capability_probe_service
            if capability_probe_service is not None
            else ExactCapabilityProbeService(sync_model_transport)
        )
        self._model_liveness_probe_service = (
            model_liveness_probe_service
            if model_liveness_probe_service is not None
            else ModelLivenessProbeService(sync_model_transport)
        )
        if prompt_text is None:
            import retrieve

            prompt_text = retrieve.HYDE_PROMPT
        self._prompt_text = str(prompt_text)
        self._prompt_version = str(
            prompt_version or self.runtime_identity.hyde_prompt_version
        )
        self._lock = threading.Condition(threading.RLock())
        self._profiles: dict[tuple[int, str, int], _ProfileCacheEntry] = {}
        self._candidate_pools: dict[
            tuple[int, str, int], _CandidatePoolCacheEntry
        ] = {}

    def set_hyde_response_mode(
        self,
        response_mode: StructuredResponseModeInput,
    ) -> None:
        normalized_mode = normalize_structured_response_mode(response_mode)
        with self._lock:
            if self._profiles or self._candidate_pools:
                raise RetrievalRuntimeError("hyde_response_mode_change_after_use")
            self._hyde_response_mode = normalized_mode

    @staticmethod
    def _revision_key(revision: SubtaskRevisionRef) -> tuple[int, str, int]:
        return (revision.graph_revision, revision.subtask_id, revision.subtask_revision)

    def _failure_record(
        self,
        *,
        revision: SubtaskRevisionRef,
        attempt: int,
        query_sha256: str,
        profile_sha256: str,
        responsibility: str,
        failure_code: str,
        infrastructure: bool,
    ) -> RetrievalAttemptRecord:
        return RetrievalAttemptRecord(
            revision=revision,
            attempt=attempt,
            query_sha256=query_sha256,
            profile_sha256=profile_sha256,
            policy_sha256=self.runtime_identity.policy_sha256,
            index_sha256=self.runtime_identity.index_sha256,
            pool_sha256=self.runtime_identity.pool_sha256,
            outcome=(
                RetrievalAttemptOutcome.INFRASTRUCTURE_FAILURE
                if infrastructure
                else RetrievalAttemptOutcome.TERMINAL_FAILURE
            ),
            failure_responsibility=FailureResponsibility(responsibility),
            failure_code=failure_code,
        )

    @staticmethod
    def _classify_failure(
        exc: BaseException,
        *,
        unknown_failure_code: str,
    ) -> tuple[str, str, bool, bool]:
        responsibility = str(
            getattr(exc, "failure_responsibility", None)
            or getattr(exc, "responsibility", None)
            or ""
        )
        code = str(
            getattr(exc, "failure_code", None)
            or getattr(exc, "error_code", None)
            or unknown_failure_code
        )
        retryable = bool(getattr(exc, "retryable", False))
        response_received = bool(getattr(exc, "response_received", False))
        if isinstance(exc, BudgetControlError):
            return FailureResponsibility.BUDGET.value, code, False, False
        if isinstance(exc, (ModelAccountingError, ModelTransportError)):
            return FailureResponsibility.FRAMEWORK.value, code, False, response_received
        if responsibility in {item.value for item in FailureResponsibility}:
            return responsibility, code, retryable, response_received
        return FailureResponsibility.FRAMEWORK.value, code, False, response_received

    def prepare_ideal_profile(
        self,
        revision: SubtaskRevisionRef,
        subtask: Subtask,
        *,
        runtime_identity: RetrievalRuntimeIdentity | None = None,
        cost_ledger: RunCostLedger | None = None,
        public_context: Sequence[Mapping[str, Any] | PublicContextDescriptor] | None = None,
    ) -> EncodedIdealResourceProfile:
        """Prepare one semantic profile and locally encode it with fixed retry."""

        supplied_identity = runtime_identity or self.runtime_identity
        if supplied_identity.identity_sha256 != self.runtime_identity.identity_sha256:
            raise RetrievalRuntimeError("retrieval_runtime_identity_changed")
        projection = project_retrieval_contract(
            revision,
            subtask,
            public_context=public_context,
        )
        key = self._revision_key(revision)
        while True:
            with self._lock:
                entry = self._profiles.get(key)
                if entry is None:
                    entry = _ProfileCacheEntry(projection.contract_sha256)
                    self._profiles[key] = entry
                    break
                if entry.contract_sha256 != projection.contract_sha256:
                    raise RetrievalRuntimeError("retrieval_revision_contract_conflict")
                while entry.in_flight:
                    self._lock.wait()
                if entry.result is not None:
                    return entry.result
                if entry.failure is not None:
                    raise entry.failure.clone()

        try:
            result = self._prepare_profile_uncached(
                revision,
                projection,
                cost_ledger=cost_ledger,
            )
        except RetrievalPreparationError as exc:
            with self._lock:
                entry.failure = exc
                entry.in_flight = False
                self._lock.notify_all()
            raise exc.clone()
        except (asyncio.CancelledError, KeyboardInterrupt):
            with self._lock:
                entry.in_flight = False
                if self._profiles.get(key) is entry:
                    self._profiles.pop(key, None)
                self._lock.notify_all()
            raise
        except Exception as exc:
            failure = RetrievalPreparationError(
                "retrieval_profile_generator_contract_failure",
                responsibility=FailureResponsibility.FRAMEWORK.value,
                response_received=False,
                exception_type=type(exc).__name__,
                message_sha256=canonical_sha256(str(exc)),
            )
            with self._lock:
                entry.failure = failure
                entry.in_flight = False
                self._lock.notify_all()
            raise failure.clone() from exc
        with self._lock:
            entry.result = result
            entry.in_flight = False
            self._lock.notify_all()
        return result

    @staticmethod
    def _candidate_input_sha256(
        library: Sequence[Manifest],
        resource_index: Mapping[str, Mapping[str, Any]],
    ) -> str:
        manifests = [
            {
                "resource_id": item.id,
                "resource_type": item.type.value,
                "v_cap": list(item.v_cap.embedding),
                "v_con": list(item.v_con.embedding),
            }
            for item in sorted(library, key=lambda value: value.id)
        ]
        raw_identity = [
            {
                "resource_id": str(resource_id),
                "resource_type": _resource_type(raw),
                "manifest_sha256": canonical_sha256(raw),
            }
            for resource_id, raw in sorted(resource_index.items())
        ]
        return canonical_sha256({"manifests": manifests, "resource_index": raw_identity})

    def prepare_candidate_pool(
        self,
        revision: SubtaskRevisionRef,
        subtask: Subtask,
        runtime_identity: RetrievalRuntimeIdentity,
        library: Sequence[Manifest],
        resource_index: Mapping[str, Mapping[str, Any]],
        cost_ledger: RunCostLedger | None,
        public_context: Sequence[Mapping[str, Any] | PublicContextDescriptor] | None = None,
    ) -> FrozenCandidatePoolResult:
        """Build and atomically freeze the only formal pool for one revision."""

        if runtime_identity.identity_sha256 != self.runtime_identity.identity_sha256:
            raise RetrievalRuntimeError("retrieval_runtime_identity_changed")
        projection = project_retrieval_contract(
            revision,
            subtask,
            public_context=public_context,
        )
        input_sha256 = self._candidate_input_sha256(library, resource_index)
        key = self._revision_key(revision)
        while True:
            with self._lock:
                entry = self._candidate_pools.get(key)
                if entry is None:
                    entry = _CandidatePoolCacheEntry(
                        projection.contract_sha256,
                        input_sha256,
                    )
                    self._candidate_pools[key] = entry
                    break
                if entry.contract_sha256 != projection.contract_sha256:
                    raise RetrievalRuntimeError("retrieval_revision_contract_conflict")
                if entry.input_sha256 != input_sha256:
                    raise RetrievalRuntimeError("retrieval_frozen_pool_input_changed")
                while entry.in_flight:
                    self._lock.wait()
                if entry.result is not None:
                    return entry.result
                if entry.failure is not None:
                    raise entry.failure.clone()

        try:
            profile = self.prepare_ideal_profile(
                revision,
                subtask,
                runtime_identity=runtime_identity,
                cost_ledger=cost_ledger,
                public_context=public_context,
            )
            result = _CandidatePoolBuilder(
                identity=runtime_identity,
                contract=projection,
                profile=profile,
                library=library,
                resource_index=resource_index,
                local_text_encoder=self._local_text_encoder,
                capability_probe_service=self._capability_probe_service,
                model_liveness_probe_service=self._model_liveness_probe_service,
                cost_ledger=cost_ledger,
                model_readiness_authority=self._model_readiness_authority,
                runtime_incompatibility=self._runtime_incompatibility,
            ).build()
        except RetrievalPreparationError as exc:
            with self._lock:
                entry.failure = exc
                entry.in_flight = False
                self._lock.notify_all()
            raise exc.clone()
        except (asyncio.CancelledError, KeyboardInterrupt):
            with self._lock:
                entry.in_flight = False
                if self._candidate_pools.get(key) is entry:
                    self._candidate_pools.pop(key, None)
                self._lock.notify_all()
            raise
        except BudgetControlError as exc:
            failure = RetrievalPreparationError(
                str(getattr(exc, "error_code", "model_cost_limit_reached")),
                responsibility=FailureResponsibility.BUDGET.value,
                response_received=False,
                exception_type=type(exc).__name__,
            )
            with self._lock:
                entry.failure = failure
                entry.in_flight = False
                self._lock.notify_all()
            raise failure.clone() from exc
        except (ModelIdentityError, ModelLivenessProbeError) as exc:
            failure = RetrievalPreparationError(
                str(getattr(exc, "error_code", "model_liveness_contract_failure")),
                responsibility=str(
                    getattr(
                        exc,
                        "failure_responsibility",
                        FailureResponsibility.FRAMEWORK.value,
                    )
                ),
                response_received=False,
                exception_type=type(exc).__name__,
            )
            with self._lock:
                entry.failure = failure
                entry.in_flight = False
                self._lock.notify_all()
            raise failure.clone() from exc
        except RetrievalRuntimeError as exc:
            failure = RetrievalPreparationError(
                exc.error_code,
                responsibility=exc.failure_responsibility,
                response_received=False,
                exception_type=type(exc).__name__,
                message_sha256=canonical_sha256(str(exc)),
            )
            with self._lock:
                entry.failure = failure
                entry.in_flight = False
                self._lock.notify_all()
            raise failure.clone() from exc
        except ModelResponseContractError as exc:
            failure = RetrievalPreparationError(
                str(exc),
                responsibility=FailureResponsibility.FRAMEWORK.value,
                response_received=False,
                exception_type=type(exc).__name__,
                message_sha256=canonical_sha256(str(exc)),
            )
            with self._lock:
                entry.failure = failure
                entry.in_flight = False
                self._lock.notify_all()
            raise failure.clone() from exc
        except Exception as exc:
            failure = RetrievalPreparationError(
                "retrieval_candidate_build_framework_failure",
                responsibility=FailureResponsibility.FRAMEWORK.value,
                response_received=False,
                exception_type=type(exc).__name__,
                message_sha256=canonical_sha256(str(exc)),
            )
            with self._lock:
                entry.failure = failure
                entry.in_flight = False
                self._lock.notify_all()
            raise failure.clone() from exc
        with self._lock:
            entry.result = result
            entry.in_flight = False
            self._lock.notify_all()
        return result

    def has_frozen_candidate_pool(self, revision: SubtaskRevisionRef) -> bool:
        with self._lock:
            entry = self._candidate_pools.get(self._revision_key(revision))
            return bool(entry is not None and not entry.in_flight and entry.result is not None)

    def revalidate_frozen_model_liveness(
        self,
        frozen_result: FrozenCandidatePoolResult,
        *,
        cost_ledger: RunCostLedger | None = None,
    ) -> tuple[ModelLivenessEvidence, ...]:
        """Refresh only expired selected models without changing the frozen pool."""

        if frozen_result.model_readiness_authority == "applied_ready_state":
            return ()

        if not frozen_result.resolved_model_identities:
            raise RetrievalPreparationError(
                "frozen_model_identity_evidence_missing",
                responsibility=FailureResponsibility.FRAMEWORK.value,
                response_received=False,
            )
        frozen_evidence = {
            item.resource_id: item for item in frozen_result.model_liveness_evidence
        }
        now = self._model_liveness_probe_service.clock()
        verified: list[ModelLivenessEvidence] = []
        for identity in frozen_result.resolved_model_identities:
            evidence = frozen_evidence.get(identity.resource_id)
            if evidence is None:
                raise RetrievalPreparationError(
                    "frozen_model_liveness_evidence_missing",
                    responsibility=FailureResponsibility.FRAMEWORK.value,
                    response_received=False,
                )
            if evidence.outcome == "live_verified" and evidence.is_fresh(now):
                verified.append(evidence)
                continue
            refreshed = self._model_liveness_probe_service.probe(
                identity=identity,
                cost_ledger=cost_ledger,
                subtask_id=frozen_result.revision.subtask_id,
                subtask_revision=frozen_result.revision.subtask_revision,
                force_refresh=True,
            )
            if refreshed.outcome != "live_verified":
                transient = refreshed.outcome == "transient_failure"
                raise RetrievalPreparationError(
                    "frozen_model_liveness_revalidation_failed",
                    responsibility=(
                        FailureResponsibility.INFRASTRUCTURE.value
                        if transient
                        else FailureResponsibility.RESEARCH.value
                    ),
                    response_received=False,
                )
            verified.append(refreshed)
        return tuple(verified)

    def _prepare_profile_uncached(
        self,
        revision: SubtaskRevisionRef,
        projection: RetrievalContractProjection,
        *,
        cost_ledger: RunCostLedger | None,
    ) -> EncodedIdealResourceProfile:
        query_text = ideal_profile_query_text(projection)
        terminal_progress.detail("Profiler", "Starting; complete input", query_text, revision.subtask_id)
        query_hash = canonical_sha256(query_text)
        intended_profile_hash = canonical_sha256(
            {
                "revision": revision,
                "contract_sha256": projection.contract_sha256,
                "raw_query_text": query_text,
                "prompt_version": self._prompt_version,
                "prompt_sha256": hashlib.sha256(self._prompt_text.encode("utf-8")).hexdigest(),
            }
        )
        try:
            generated = self._profile_generator(
                query_text,
                cost_ledger=cost_ledger,
                revision=revision,
            )
            terminal_progress.detail("Profiler", "Returned profile (before validation)", generated, revision.subtask_id)
            if not isinstance(generated, Mapping):
                raise RetrievalRuntimeError(
                    "hyde_response_schema_invalid",
                    responsibility=FailureResponsibility.RESEARCH.value,
                )
            capability = str(generated.get("capability_text") or "").strip()
            constraint = str(generated.get("constraint_text") or "").strip()
            think = str(generated.get("think") or "").strip()
            if not capability or not constraint or not think:
                raise RetrievalRuntimeError(
                    "hyde_response_fields_empty",
                    responsibility=FailureResponsibility.RESEARCH.value,
                )
            metadata = generated.get("metadata")
            metadata = metadata if isinstance(metadata, Mapping) else {}
            accounting_reference = metadata.get("model_accounting_reference")
            if accounting_reference is not None and not isinstance(accounting_reference, Mapping):
                raise RetrievalRuntimeError("hyde_accounting_reference_invalid")
            artifact = IdealResourceProfileArtifact(
                revision=revision,
                contract_sha256=projection.contract_sha256,
                raw_query_text=query_text,
                capability_text=capability,
                constraint_text=constraint,
                think=think,
                explicit_hard_requirements=explicit_hard_requirements(projection),
                prompt_version=str(metadata.get("prompt_version") or self._prompt_version),
                prompt_sha256=hashlib.sha256(self._prompt_text.encode("utf-8")).hexdigest(),
                model_accounting_reference=(
                    _canonical_json_value(accounting_reference)
                    if isinstance(accounting_reference, Mapping)
                    else None
                ),
            )
        except (asyncio.CancelledError, KeyboardInterrupt):
            raise
        except Exception as exc:
            responsibility, code, _retryable, response_received = self._classify_failure(
                exc,
                unknown_failure_code="retrieval_profile_generator_contract_failure",
            )
            record = self._failure_record(
                revision=revision,
                attempt=1,
                query_sha256=query_hash,
                profile_sha256=intended_profile_hash,
                responsibility=responsibility,
                failure_code=code,
                infrastructure=responsibility == FailureResponsibility.INFRASTRUCTURE.value,
            )
            raise RetrievalPreparationError(
                code,
                responsibility=responsibility,
                attempts=(record,),
                response_received=response_received,
                exception_type=type(exc).__name__,
                message_sha256=canonical_sha256(str(exc)),
            ) from exc

        terminal_progress.detail("Profiler", "Validated retrieval profile", artifact, revision.subtask_id)
        attempts: list[RetrievalAttemptRecord] = []
        for attempt_number in range(1, 4):
            try:
                profile = self._profile_encoder(artifact)
                vectors = (
                    tuple(float(item) for item in profile.capability.embedding),
                    (
                        tuple(float(item) for item in profile.constraint.embedding)
                        if profile.constraint is not None
                        else None
                    ),
                    (
                        tuple(float(item) for item in profile.raw_query.embedding)
                        if profile.raw_query is not None
                        else None
                    ),
                )
                dimension = profile.capability.dim
                success = RetrievalAttemptRecord(
                    revision=revision,
                    attempt=attempt_number,
                    query_sha256=query_hash,
                    profile_sha256=artifact.profile_sha256,
                    policy_sha256=self.runtime_identity.policy_sha256,
                    index_sha256=self.runtime_identity.index_sha256,
                    pool_sha256=self.runtime_identity.pool_sha256,
                    outcome=RetrievalAttemptOutcome.SUCCESS,
                )
                attempts.append(success)
                return EncodedIdealResourceProfile(
                    artifact=artifact,
                    capability_vector=vectors[0],
                    constraint_vector=vectors[1],
                    raw_query_vector=vectors[2],
                    dimension=dimension,
                    retrieval_attempts=tuple(attempts),
                )
            except (asyncio.CancelledError, KeyboardInterrupt):
                raise
            except Exception as exc:
                responsibility, code, retryable, response_received = self._classify_failure(
                    exc,
                    unknown_failure_code="retrieval_profile_encoding_framework_failure",
                )
                infrastructure = responsibility == FailureResponsibility.INFRASTRUCTURE.value
                attempts.append(
                    self._failure_record(
                        revision=revision,
                        attempt=attempt_number,
                        query_sha256=query_hash,
                        profile_sha256=artifact.profile_sha256,
                        responsibility=responsibility,
                        failure_code=code,
                        infrastructure=infrastructure,
                    )
                )
                if infrastructure and retryable and attempt_number < 3:
                    continue
                raise RetrievalPreparationError(
                    code,
                    responsibility=responsibility,
                    attempts=tuple(attempts),
                    response_received=response_received,
                    exception_type=type(exc).__name__,
                    message_sha256=canonical_sha256(str(exc)),
                ) from exc
        raise AssertionError("unreachable_retrieval_profile_retry_state")


def check_retrieval_runtime(
    *,
    project_root: str | Path = PROJECT_ROOT,
    provider_compatibility: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """No-network CLI/API preflight for the formal retrieval identity."""

    try:
        identity = build_retrieval_runtime_identity(
            project_root=project_root,
            provider_compatibility=provider_compatibility,
            require_release_sealed=True,
        )
    except RetrievalRuntimeError as exc:
        return {
            "protocol": RETRIEVAL_RUNTIME_PROTOCOL,
            "valid": False,
            "error_code": exc.error_code,
            "responsibility": exc.failure_responsibility,
        }
    eligible_counts = {
        resource_type: sum(
            1
            for item in identity.availability_records
            if item.resource_type == resource_type
            and item.resource_id in identity.eligible_resource_ids
        )
        for resource_type in FORMAL_TYPE_ORDER
    }
    return {
        "protocol": RETRIEVAL_RUNTIME_PROTOCOL,
        "valid": True,
        "identity": identity.model_dump(mode="json"),
        "eligible_counts": eligible_counts,
        "quota_satisfiable": {
            resource_type: eligible_counts[resource_type] >= quota
            for resource_type, quota in identity.quota_map.items()
            if quota > 0
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate frozen SGAR retrieval inputs.")
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    parser.add_argument("--output")
    args = parser.parse_args()
    report = check_retrieval_runtime(project_root=args.project_root)
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = temporary_sibling_path(output)
        temporary.write_text(serialized + "\n", encoding="utf-8")
        os.replace(temporary, output)
    print(serialized)
    raise SystemExit(0 if report.get("valid") is True else 2)


if __name__ == "__main__":
    main()


__all__ = [
    "AppliedModelReadyState",
    "AppliedReadyModel",
    "AppliedReadyStateCapabilityService",
    "AvailabilityRecord",
    "CandidateCompatibilityDecision",
    "CandidateDependencyEdge",
    "CandidateScoreEvidence",
    "EncodedIdealResourceProfile",
    "FORMAL_TYPED_QUOTAS",
    "FrozenCandidatePoolResult",
    "IdealResourceProfileArtifact",
    "LocalRetrievalInfrastructureError",
    "OptionalDependencyHint",
    "PublicContextDescriptor",
    "RETRIEVAL_RUNTIME_PROTOCOL",
    "RetrievalContractProjection",
    "RetrievalCoordinator",
    "RetrievalPreparationError",
    "RetrievalRuntimeError",
    "RetrievalRuntimeIdentity",
    "TypeQuotaEvidence",
    "build_retrieval_runtime_identity",
    "check_retrieval_runtime",
    "explicit_hard_requirements",
    "ideal_profile_query_text",
    "load_applied_model_ready_state",
    "project_retrieval_contract",
    "typed_refs_from_frozen_pool",
    "validate_loaded_retrieval_backend",
    "validate_required_dependency_graph",
]
