"""Immutable, fail-closed contracts for production recovery.

The module owns recovery identity and persistence only.  It deliberately does
not import Planner, Router, E1 cases, validators, or concrete Tool adapters.
"""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from collections import Counter
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from pydantic import Field, field_validator, model_validator

from .authorized_material import AuthorizedModelMaterialView
from .atomic_io import temporary_sibling_path
from .executable_plan import (
    CompilerDecisionProposalV3,
    CompilerPlanProposalV2,
    CompilerPublicContext,
    CompilerPlanDraft,
    ExecutablePlan,
    ExecutablePlanStep,
    PlanCompilerInputEnvelope,
)
from .model_accounting import ModelPricingCatalog
from .model_response_contracts import (
    StructuredResponseModeInput,
    normalize_structured_response_mode,
)
from .pipeline_control import FrozenContract, SubtaskRevisionRef, canonical_json_bytes, canonical_sha256
from .path_policy import is_private_host_path_value


RECOVERY_POLICY_PROTOCOL = "sgar-recovery-policy-v1"
RECOVERY_RUNTIME_PROTOCOL = "sgar-recovery-runtime-v1"
RECOVERY_EVIDENCE_PROTOCOL = "sgar-recovery-evidence-v1"
RECOVERY_LINEAGE_PROTOCOL = "sgar-recovery-lineage-v1"
PLAN_ADAPTATION_INPUT_PROTOCOL = "sgar-plan-adaptation-input-v2"
FAILED_GENERATION_ROUTE_PROTOCOL = "sgar-failed-generation-route-v1"
TEMPORARY_TOOL_PROTOCOL = "sgar-temporary-tool-v1"
FULL_GENERATION_PROTOCOL = "sgar-full-generation-v2"
RECOVERY_EVENT_PROTOCOL = "sgar-recovery-events-v1"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SECRET_FIELD = re.compile(
    r"(?i)^(?:api[_-]?key|authorization|password|secret|access[_-]?token|"
    r"refresh[_-]?token|bearer[_-]?token)$"
)


class RecoveryControlError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = str(code)
        super().__init__(self.code)


class RecoveryPersistenceError(RecoveryControlError):
    pass


def _require_sha256(value: str, *, field_name: str) -> str:
    normalized = str(value or "").strip().lower()
    if not _SHA256.fullmatch(normalized):
        raise ValueError(f"{field_name}_must_be_sha256_hex")
    return normalized


def _host_or_secret_locator(value: Any, locator: str = "$") -> str | None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if _SECRET_FIELD.search(str(key)):
                return f"{locator}.{key}"
            found = _host_or_secret_locator(item, f"{locator}.{key}")
            if found:
                return found
        return None
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found = _host_or_secret_locator(item, f"{locator}[{index}]")
            if found:
                return found
        return None
    if isinstance(value, str) and is_private_host_path_value(value):
        return locator
    return None


def assert_recovery_projection_safe(value: Any) -> None:
    locator = _host_or_secret_locator(value)
    if locator:
        raise RecoveryControlError(f"recovery_projection_unsafe:{locator}")


class RecoveryPolicy(FrozenContract):
    protocol: Literal[RECOVERY_POLICY_PROTOCOL] = RECOVERY_POLICY_PROTOCOL
    sealed_runtime_mode: Literal["strict_plan_only", "legacy_extended"] = (
        "legacy_extended"
    )
    max_plan_adaptations: Literal[2] = 2
    max_full_generation_calls: int = Field(default=1, ge=0, le=1)
    full_generation_model_resource_id: str = Field(min_length=1)
    temporary_tool_source_max_bytes: int = Field(default=65536, ge=1, le=65536)
    temporary_tool_bundle_max_bytes: int = Field(default=262144, ge=1, le=262144)
    temporary_tool_bundle_max_files: int = Field(default=32, ge=1, le=32)
    diagnostic_payload_max_bytes: int = Field(default=8192, ge=1, le=8192)
    allow_network_expansion: Literal[False] = False
    allow_dependency_install: Literal[False] = False
    policy_sha256: str = ""

    @model_validator(mode="after")
    def _seal_policy(self) -> "RecoveryPolicy":
        if self.temporary_tool_bundle_max_bytes < self.temporary_tool_source_max_bytes:
            raise ValueError("temporary_tool_bundle_limit_below_source_limit")
        projection = self.model_dump(mode="python", exclude={"policy_sha256"})
        expected = canonical_sha256(projection)
        if self.policy_sha256:
            if _require_sha256(self.policy_sha256, field_name="policy_sha256") != expected:
                raise ValueError("recovery_policy_sha256_mismatch")
        object.__setattr__(self, "policy_sha256", expected)
        return self


def load_recovery_policy(path: str | Path) -> RecoveryPolicy:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RecoveryControlError("recovery_policy_unreadable") from exc
    if not isinstance(payload, Mapping):
        raise RecoveryControlError("recovery_policy_root_not_mapping")
    try:
        return RecoveryPolicy.model_validate(payload)
    except Exception as exc:
        raise RecoveryControlError("recovery_policy_invalid") from exc


class SystemFullGenerationPolicy(FrozenContract):
    protocol: Literal[FULL_GENERATION_PROTOCOL] = FULL_GENERATION_PROTOCOL
    resource_id: str = Field(min_length=1)
    api_model_id: str = Field(min_length=1)
    manifest_sha256: str
    pricing_catalog_sha256: str
    response_mode: StructuredResponseModeInput
    temperature: float = Field(ge=0.0, le=2.0)
    max_tokens: int = Field(ge=1)
    allow_streaming: bool
    prompt_version: str = Field(min_length=1)
    prompt_sha256: str
    recovery_policy_sha256: str
    policy_sha256: str = ""

    @field_validator(
        "manifest_sha256",
        "pricing_catalog_sha256",
        "prompt_sha256",
        "recovery_policy_sha256",
    )
    @classmethod
    def _hash_fields(cls, value: str, info: Any) -> str:
        return _require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _seal_system_policy(self) -> "SystemFullGenerationPolicy":
        projection = self.model_dump(mode="python", exclude={"policy_sha256"})
        expected = canonical_sha256(projection)
        if self.policy_sha256:
            if _require_sha256(self.policy_sha256, field_name="policy_sha256") != expected:
                raise ValueError("full_generation_policy_sha256_mismatch")
        object.__setattr__(self, "policy_sha256", expected)
        return self


def resolve_system_full_generation_policy(
    *,
    recovery_policy: RecoveryPolicy,
    pricing_catalog: ModelPricingCatalog,
    manifest: Mapping[str, Any],
    response_mode: StructuredResponseModeInput,
    temperature: float,
    max_tokens: int,
    allow_streaming: bool,
    prompt_version: str,
    prompt_sha256: str,
    availability_status: str = "unknown",
) -> SystemFullGenerationPolicy:
    normalize_structured_response_mode(response_mode)
    resource_id = recovery_policy.full_generation_model_resource_id
    if str(manifest.get("resource_id") or "") != resource_id:
        raise RecoveryControlError("full_generation_manifest_identity_mismatch")
    if str(manifest.get("resource_type") or "") != "Model":
        raise RecoveryControlError("full_generation_resource_not_model")
    if str(availability_status).strip().lower() == "unavailable":
        raise RecoveryControlError("full_generation_model_unavailable")
    execution = manifest.get("execution")
    if not isinstance(execution, Mapping):
        raise RecoveryControlError("full_generation_execution_missing")
    api_model_id = str(execution.get("model_id") or "").strip()
    if not api_model_id:
        raise RecoveryControlError("full_generation_api_model_id_missing")
    price = pricing_catalog.resolve(resource_id=resource_id, api_model_id=api_model_id)
    if price.resource_id != resource_id or price.api_model_id != api_model_id:
        raise RecoveryControlError("full_generation_pricing_identity_mismatch")
    manifest_sha256 = canonical_sha256(dict(manifest))
    return SystemFullGenerationPolicy(
        resource_id=resource_id,
        api_model_id=api_model_id,
        manifest_sha256=manifest_sha256,
        pricing_catalog_sha256=pricing_catalog.pricing_catalog_sha256,
        response_mode=response_mode,
        temperature=temperature,
        max_tokens=max_tokens,
        allow_streaming=allow_streaming,
        prompt_version=prompt_version,
        prompt_sha256=prompt_sha256,
        recovery_policy_sha256=recovery_policy.policy_sha256,
    )


class SideEffectStatus(str, Enum):
    NOT_DISPATCHED = "not_dispatched"
    NONE_OBSERVED = "none_observed"
    ISOLATED_WORKSPACE_ONLY = "isolated_workspace_only"
    MANIFEST_IDEMPOTENT = "manifest_idempotent"
    UNKNOWN_EXTERNAL = "unknown_external"
    UNMATCHED_CALL = "unmatched_call"


class AdaptationKind(str, Enum):
    BINDING_OR_ENTRYPOINT_CORRECTION = "binding_or_entrypoint_correction"
    PLAN_RECOMPOSITION = "plan_recomposition"
    TEMPORARY_TOOL_TRANSFORM = "temporary_tool_transform"


class SideEffectEvidence(FrozenContract):
    protocol: Literal[RECOVERY_EVIDENCE_PROTOCOL] = RECOVERY_EVIDENCE_PROTOCOL
    status: SideEffectStatus
    dispatched: bool
    network_required: bool = False
    writable_scope_sha256: str | None = None
    artifact_hashes: tuple[str, ...] = ()
    evidence_sha256: str = ""

    @field_validator("writable_scope_sha256")
    @classmethod
    def _optional_scope_hash(cls, value: str | None) -> str | None:
        return None if value is None else _require_sha256(value, field_name="writable_scope_sha256")

    @field_validator("artifact_hashes")
    @classmethod
    def _artifact_hashes(cls, value: Sequence[str]) -> tuple[str, ...]:
        return tuple(_require_sha256(item, field_name="artifact_hash") for item in value)

    @model_validator(mode="after")
    def _seal_evidence(self) -> "SideEffectEvidence":
        if self.status is SideEffectStatus.NOT_DISPATCHED and self.dispatched:
            raise ValueError("not_dispatched_side_effect_marked_dispatched")
        if self.status is SideEffectStatus.UNMATCHED_CALL and not self.dispatched:
            raise ValueError("unmatched_call_must_be_dispatched")
        expected = canonical_sha256(self.model_dump(mode="python", exclude={"evidence_sha256"}))
        if self.evidence_sha256:
            if _require_sha256(self.evidence_sha256, field_name="evidence_sha256") != expected:
                raise ValueError("side_effect_evidence_sha256_mismatch")
        object.__setattr__(self, "evidence_sha256", expected)
        return self


class StructuredExecutionFailureEvidence(FrozenContract):
    protocol: Literal[RECOVERY_EVIDENCE_PROTOCOL] = RECOVERY_EVIDENCE_PROTOCOL
    responsibility: Literal["framework", "infrastructure", "research", "budget", "interrupted"]
    failure_stage: str = Field(min_length=1)
    failure_code: str = Field(min_length=1)
    exception_type: str = ""
    retryable: bool = False
    response_received: bool = False
    resource_id: str | None = None
    entrypoint_id: str | None = None
    step_id: str | None = None
    resource_call_id: str | None = None
    request_sha256: str | None = None
    plan_sha256: str
    candidate_pool_sha256: str
    sandbox_scope_sha256: str | None = None
    message_sha256: str
    diagnostic_sha256: str
    diagnostic_bytes: int = Field(default=0, ge=0, le=8192)
    redaction_count: int = Field(default=0, ge=0)
    side_effect_evidence: SideEffectEvidence
    evidence_sha256: str = ""

    @field_validator(
        "plan_sha256",
        "candidate_pool_sha256",
        "message_sha256",
        "diagnostic_sha256",
    )
    @classmethod
    def _required_hashes(cls, value: str, info: Any) -> str:
        return _require_sha256(value, field_name=info.field_name)

    @field_validator("request_sha256", "sandbox_scope_sha256")
    @classmethod
    def _optional_hashes(cls, value: str | None, info: Any) -> str | None:
        return None if value is None else _require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _seal_failure(self) -> "StructuredExecutionFailureEvidence":
        if self.responsibility != "infrastructure" and self.retryable:
            raise ValueError("non_infrastructure_failure_cannot_be_transport_retryable")
        if self.responsibility == "infrastructure" and self.response_received:
            raise ValueError("infrastructure_failure_cannot_have_response")
        projection = self.model_dump(mode="python", exclude={"evidence_sha256"})
        assert_recovery_projection_safe(projection)
        expected = canonical_sha256(projection)
        if self.evidence_sha256:
            if _require_sha256(self.evidence_sha256, field_name="evidence_sha256") != expected:
                raise ValueError("failure_evidence_sha256_mismatch")
        object.__setattr__(self, "evidence_sha256", expected)
        return self


class RecoveryOperationRef(FrozenContract):
    protocol: Literal[RECOVERY_RUNTIME_PROTOCOL] = RECOVERY_RUNTIME_PROTOCOL
    run_id: str = Field(min_length=1)
    revision: SubtaskRevisionRef
    candidate_pool_sha256: str
    initial_plan_artifact_sha256: str
    current_plan_revision: int = Field(ge=0, le=2)
    adaptation_count: int = Field(ge=0, le=2)
    full_generation_count: int = Field(ge=0, le=1)
    recovery_policy_sha256: str
    operation_sha256: str = ""

    @field_validator(
        "candidate_pool_sha256",
        "initial_plan_artifact_sha256",
        "recovery_policy_sha256",
    )
    @classmethod
    def _identity_hashes(cls, value: str, info: Any) -> str:
        return _require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _seal_operation(self) -> "RecoveryOperationRef":
        if self.current_plan_revision != self.adaptation_count:
            raise ValueError("recovery_plan_revision_adaptation_count_mismatch")
        projection = self.model_dump(mode="python", exclude={"operation_sha256"})
        expected = canonical_sha256(projection)
        if self.operation_sha256:
            if _require_sha256(self.operation_sha256, field_name="operation_sha256") != expected:
                raise ValueError("recovery_operation_sha256_mismatch")
        object.__setattr__(self, "operation_sha256", expected)
        return self


class CompletedStepCheckpoint(FrozenContract):
    protocol: Literal[RECOVERY_LINEAGE_PROTOCOL] = RECOVERY_LINEAGE_PROTOCOL
    step_id: str = Field(min_length=1)
    step_semantic_sha256: str
    resource_id: str = Field(min_length=1)
    entrypoint_id: str | None = None
    result_sha256: str
    resource_call_id: str = Field(min_length=1)
    artifact_handle_ids: tuple[str, ...] = ()
    artifact_hashes: tuple[str, ...] = ()
    provenance_source_ids: tuple[str, ...] = ()
    started_event_id: str = Field(min_length=1)
    terminal_event_id: str = Field(min_length=1)
    side_effect_evidence: SideEffectEvidence
    checkpoint_sha256: str = ""

    @field_validator("step_semantic_sha256", "result_sha256")
    @classmethod
    def _checkpoint_hashes(cls, value: str, info: Any) -> str:
        return _require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _seal_checkpoint(self) -> "CompletedStepCheckpoint":
        if len(self.artifact_handle_ids) != len(set(self.artifact_handle_ids)):
            raise ValueError("duplicate_checkpoint_artifact_handle")
        projection = self.model_dump(mode="python", exclude={"checkpoint_sha256"})
        assert_recovery_projection_safe(projection)
        expected = canonical_sha256(projection)
        if self.checkpoint_sha256:
            if _require_sha256(self.checkpoint_sha256, field_name="checkpoint_sha256") != expected:
                raise ValueError("checkpoint_sha256_mismatch")
        object.__setattr__(self, "checkpoint_sha256", expected)
        return self


class RecoveryLineage(FrozenContract):
    protocol: Literal[RECOVERY_LINEAGE_PROTOCOL] = RECOVERY_LINEAGE_PROTOCOL
    previous_plan_artifact_sha256: str
    previous_plan_sha256: str
    failure_evidence_sha256: str
    preserved_checkpoint_ids: tuple[str, ...] = ()
    failed_frontier_step_ids: tuple[str, ...] = ()
    never_started_step_ids: tuple[str, ...] = ()
    rerun_forbidden_call_signatures: tuple[str, ...] = ()
    adapted_plan_artifact_sha256: str | None = None
    lineage_sha256: str = ""

    @field_validator(
        "previous_plan_artifact_sha256",
        "previous_plan_sha256",
        "failure_evidence_sha256",
        "adapted_plan_artifact_sha256",
    )
    @classmethod
    def _lineage_hashes(cls, value: str | None, info: Any) -> str | None:
        return None if value is None else _require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _seal_lineage(self) -> "RecoveryLineage":
        for name in (
            "preserved_checkpoint_ids",
            "failed_frontier_step_ids",
            "never_started_step_ids",
            "rerun_forbidden_call_signatures",
        ):
            values = getattr(self, name)
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate_{name}")
        projection = self.model_dump(mode="python", exclude={"lineage_sha256"})
        expected = canonical_sha256(projection)
        if self.lineage_sha256:
            if _require_sha256(self.lineage_sha256, field_name="lineage_sha256") != expected:
                raise ValueError("recovery_lineage_sha256_mismatch")
        object.__setattr__(self, "lineage_sha256", expected)
        return self


def executable_step_semantic_sha256(step: ExecutablePlanStep) -> str:
    """Hash only the immutable executable semantics of one Plan step."""

    return canonical_sha256(step.model_dump(mode="json"))


def executable_step_call_signature(step: ExecutablePlanStep) -> str:
    """Stable pre-dispatch signature used to prohibit unsafe replay."""

    return canonical_sha256(
        {
            "resource_id": step.resource_id,
            "entrypoint_id": step.entrypoint_id,
            "operation_kind": step.operation_kind.value,
            "input_bindings": step.input_bindings,
            "expected_output_contract": step.expected_output_contract,
        }
    )


def _controller_callable_topology(plan: ExecutablePlan) -> str:
    """Hash callable processing capabilities rather than operation aliases.

    Two labels over the same Resource entrypoint, typed ports, output modality,
    and fixed authority do not create a new recovery route.  A different
    Resource, entrypoint, contract, or fixed material binding does.
    """

    callables: list[tuple[str, str, str, str, str, str]] = []
    for step in plan.steps:
        spec = getattr(step, "controller_session_spec", None)
        for item in getattr(spec, "callable_tools", ()) or ():
            callables.append((
                str(item.resource_id),
                str(getattr(item, "entrypoint_id", "") or ""),
                canonical_sha256(
                    tuple(getattr(item, "operation_input_contract", ()) or ())
                ),
                canonical_sha256(
                    dict(getattr(item, "resource_native_output_contract", {}) or {})
                ),
                canonical_sha256(
                    dict(getattr(item, "controller_result_target_contract", {}) or {})
                ),
                canonical_sha256(dict(item.fixed_input_bindings)),
            ))
    return canonical_sha256(sorted(callables))


def _generation_route_topology(plan: ExecutablePlan) -> str:
    """Describe resource wiring without treating rewritten prompts as a new route."""

    by_id = {step.step_id: step for step in plan.steps}
    return canonical_sha256({
        "steps": sorted(
            (
                step.resource_type,
                step.resource_id,
                step.entrypoint_id or "",
                step.agent_base_model_resource_id or "",
                tuple(sorted(by_id[parent].resource_id for parent in step.depends_on)),
            )
            for step in plan.steps
        ),
        "controller_callable_topology_sha256": _controller_callable_topology(plan),
    })


def _step_callable_topology(step: ExecutablePlanStep) -> str:
    """Hash callable Tool authority for one controller without prompt prose."""

    callables: list[tuple[str, str, str, str, str, str]] = []
    spec = getattr(step, "controller_session_spec", None)
    for item in getattr(spec, "callable_tools", ()) or ():
        callables.append((
            str(item.resource_id),
            str(getattr(item, "entrypoint_id", "") or ""),
            canonical_sha256(
                tuple(getattr(item, "operation_input_contract", ()) or ())
            ),
            canonical_sha256(
                dict(getattr(item, "resource_native_output_contract", {}) or {})
            ),
            canonical_sha256(
                dict(getattr(item, "controller_result_target_contract", {}) or {})
            ),
            canonical_sha256(dict(item.fixed_input_bindings)),
        ))
    return canonical_sha256(sorted(callables))


def _step_input_route_topology(plan: ExecutablePlan, step_id: str) -> str:
    """Hash the executable producer route into one step, excluding prompt rewrites.

    Step names and output-key labels are deliberately excluded.  A renamed graph or
    rewritten intent over the same Resources and bound inputs is the same route.
    Literal changes, typed processing, different Resources/operations, and changed
    controller Tool authority remain distinguishable.
    """

    by_id = {step.step_id: step for step in plan.steps}
    memo: dict[str, str] = {}

    def visit(current_id: str, stack: tuple[str, ...] = ()) -> str:
        if current_id in memo:
            return memo[current_id]
        if current_id in stack:
            raise RecoveryControlError("adaptation_input_route_cycle")
        step = by_id.get(current_id)
        if step is None:
            raise RecoveryControlError("adaptation_input_route_source_missing")

        def project_binding(value: Any) -> Any:
            if isinstance(value, Mapping):
                source_id = str(value.get("from_step") or "")
                if source_id:
                    return {
                        "source_step_route_sha256": visit(
                            source_id,
                            (*stack, current_id),
                        )
                    }
                return {
                    str(key): project_binding(item)
                    for key, item in sorted(
                        value.items(),
                        key=lambda pair: str(pair[0]),
                    )
                    if str(key) != "output_key"
                }
            if isinstance(value, (list, tuple)):
                return [project_binding(item) for item in value]
            return value

        output_contract = getattr(step, "expected_output_contract", None)
        output_shape = {
            "artifact_type": str(getattr(output_contract, "artifact_type", "") or ""),
            "content_kind": str(getattr(output_contract, "content_kind", "") or ""),
            "schema_hint": getattr(output_contract, "schema_hint", None),
        }
        dependency_hashes = sorted(
            visit(parent, (*stack, current_id))
            for parent in getattr(step, "depends_on", ()) or ()
        )
        projection = {
            "resource_type": str(step.resource_type),
            "resource_id": str(step.resource_id),
            "entrypoint_id": str(getattr(step, "entrypoint_id", "") or ""),
            "capability_operation_id": str(
                getattr(step, "capability_operation_id", "") or ""
            ),
            "agent_base_model_resource_id": str(
                getattr(step, "agent_base_model_resource_id", "") or ""
            ),
            "input_bindings": project_binding(
                dict(getattr(step, "input_bindings", {}) or {})
            ),
            "dependency_route_sha256s": dependency_hashes,
            "output_shape": output_shape,
            "controller_callable_topology_sha256": _step_callable_topology(step),
        }
        memo[current_id] = canonical_sha256(projection)
        return memo[current_id]

    return visit(step_id)


_TOOL_CAPABILITY_RECOMPOSITION_FAILURES = frozenset({
    "RESOURCE_TEXT_ENCODING_UNSUPPORTED",
    "controller_tool_dynamic_path_out_of_scope",
    "tool_missing_required_input",
    "interface_contract_mismatch",
    "tool_semantic_misuse",
    "operation_misuse",
})

_PROVIDER_GENERATION_ROUTE_FAILURES = frozenset({
    "provider_timeout",
    "provider_connection_error",
    "provider_rate_limit",
    "provider_server_error",
    "provider_model_unavailable",
})


def _is_generation_route_failure(
    failure_evidence: StructuredExecutionFailureEvidence,
) -> bool:
    return (
        failure_evidence.responsibility == "research"
        or (
            failure_evidence.responsibility == "infrastructure"
            and failure_evidence.failure_code
            in _PROVIDER_GENERATION_ROUTE_FAILURES
        )
    )


class FailedGenerationRouteRecordV1(FrozenContract):
    """Sealed evidence that one generation topology is exhausted in this run."""

    protocol: Literal[FAILED_GENERATION_ROUTE_PROTOCOL] = (
        FAILED_GENERATION_ROUTE_PROTOCOL
    )
    resource_id: str = Field(min_length=1)
    resource_type: Literal["Model", "Agent"]
    agent_base_model_resource_id: str | None = None
    failed_plan_sha256: str
    candidate_pool_sha256: str
    failure_evidence_sha256: str
    responsibility: Literal[
        "framework", "infrastructure", "research", "budget", "interrupted"
    ]
    failure_stage: str = Field(min_length=1)
    failure_code: str = Field(min_length=1)
    generation_route_topology_sha256: str
    controller_callable_topology_sha256: str
    record_sha256: str = ""

    @field_validator(
        "failed_plan_sha256",
        "candidate_pool_sha256",
        "failure_evidence_sha256",
        "generation_route_topology_sha256",
        "controller_callable_topology_sha256",
    )
    @classmethod
    def _route_hashes(cls, value: str, info: Any) -> str:
        return _require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _seal_record(self) -> "FailedGenerationRouteRecordV1":
        projection = self.model_dump(mode="python", exclude={"record_sha256"})
        expected = canonical_sha256(projection)
        if self.record_sha256:
            if _require_sha256(
                self.record_sha256,
                field_name="record_sha256",
            ) != expected:
                raise ValueError("failed_generation_route_record_sha256_mismatch")
        object.__setattr__(self, "record_sha256", expected)
        return self


def failed_generation_route_record(
    *,
    previous_plan: ExecutablePlan,
    failure_evidence: StructuredExecutionFailureEvidence,
) -> FailedGenerationRouteRecordV1 | None:
    """Project an execution failure into bounded same-run route history."""

    if not _is_generation_route_failure(failure_evidence) or not failure_evidence.step_id:
        return None
    failed_step = next(
        (
            step
            for step in previous_plan.steps
            if step.step_id == failure_evidence.step_id
        ),
        None,
    )
    if failed_step is None or failed_step.resource_type not in {"Model", "Agent"}:
        return None
    return FailedGenerationRouteRecordV1(
        resource_id=failed_step.resource_id,
        resource_type=failed_step.resource_type,
        agent_base_model_resource_id=failed_step.agent_base_model_resource_id,
        failed_plan_sha256=previous_plan.plan_sha256,
        candidate_pool_sha256=failure_evidence.candidate_pool_sha256,
        failure_evidence_sha256=failure_evidence.evidence_sha256,
        responsibility=failure_evidence.responsibility,
        failure_stage=failure_evidence.failure_stage,
        failure_code=failure_evidence.failure_code,
        generation_route_topology_sha256=_generation_route_topology(previous_plan),
        controller_callable_topology_sha256=_controller_callable_topology(
            previous_plan
        ),
    )


def reject_prior_failed_generation_routes(
    *,
    adapted_plan: ExecutablePlan,
    prior_failed_generation_routes: Sequence[FailedGenerationRouteRecordV1],
) -> None:
    """Reject a route exhausted earlier in the same bounded recovery chain."""

    topology_sha256 = _generation_route_topology(adapted_plan)
    if any(
        item.generation_route_topology_sha256 == topology_sha256
        for item in prior_failed_generation_routes
    ):
        raise RecoveryControlError(
            "adaptation_prior_failed_generation_route_repeated"
        )


def reject_repeated_failed_generation_route(
    *, previous_plan: ExecutablePlan,
    adapted_plan: ExecutablePlan,
    failure_evidence: StructuredExecutionFailureEvidence,
) -> None:
    """A research failure needs a changed generator or actual processing route."""

    if not _is_generation_route_failure(failure_evidence) or not failure_evidence.step_id:
        return
    failed_step = next(
        (step for step in previous_plan.steps if step.step_id == failure_evidence.step_id),
        None,
    )
    if failed_step is None or failed_step.resource_type not in {"Model", "Agent"}:
        return
    if (
        failure_evidence.responsibility == "research"
        and failure_evidence.failure_code in _TOOL_CAPABILITY_RECOMPOSITION_FAILURES
        and _controller_callable_topology(previous_plan)
        == _controller_callable_topology(adapted_plan)
    ):
        raise RecoveryControlError(
            "adaptation_failed_callable_tool_topology_repeated"
        )
    if not any(
        step.resource_type == failed_step.resource_type
        and step.resource_id == failed_step.resource_id
        and step.agent_base_model_resource_id == failed_step.agent_base_model_resource_id
        for step in adapted_plan.steps
    ):
        return
    if _generation_route_topology(previous_plan) == _generation_route_topology(adapted_plan):
        raise RecoveryControlError("adaptation_failed_generation_route_repeated")


def reject_repeated_failed_tool_input_route(
    *,
    previous_plan: ExecutablePlan,
    adapted_plan: ExecutablePlan,
    failure_evidence: StructuredExecutionFailureEvidence,
) -> None:
    """Reject a prompt-only replay of the executable input route into a failed Tool."""

    if (
        failure_evidence.responsibility != "research"
        or not failure_evidence.step_id
    ):
        return
    failed_step = next(
        (
            step
            for step in previous_plan.steps
            if step.step_id == failure_evidence.step_id
        ),
        None,
    )
    if failed_step is None or failed_step.resource_type != "Tool":
        return
    failed_route = _step_input_route_topology(
        previous_plan,
        failed_step.step_id,
    )
    for step in adapted_plan.steps:
        if (
            step.resource_type == "Tool"
            and step.resource_id == failed_step.resource_id
            and step.entrypoint_id == failed_step.entrypoint_id
            and _step_input_route_topology(adapted_plan, step.step_id)
            == failed_route
        ):
            raise RecoveryControlError(
                "adaptation_failed_tool_input_route_repeated"
            )


class PlanAdaptationInputEnvelope(FrozenContract):
    protocol: Literal[PLAN_ADAPTATION_INPUT_PROTOCOL] = PLAN_ADAPTATION_INPUT_PROTOCOL
    base_envelope: PlanCompilerInputEnvelope
    previous_plan_artifact_sha256: str
    previous_plan: ExecutablePlan
    failure_evidence: StructuredExecutionFailureEvidence
    checkpoints: tuple[CompletedStepCheckpoint, ...] = ()
    recovery_lineage: RecoveryLineage
    temporary_tool_source: "TemporaryToolSourceBundle | None" = None
    prior_adaptation_failure_sha256s: tuple[str, ...] = ()
    prior_failed_generation_routes: tuple[FailedGenerationRouteRecordV1, ...] = ()
    diagnostic_excerpt: str = Field(default="", max_length=8192)
    input_sha256: str = ""

    @field_validator("previous_plan_artifact_sha256")
    @classmethod
    def _previous_artifact_hash(cls, value: str) -> str:
        return _require_sha256(value, field_name="previous_plan_artifact_sha256")

    @field_validator("prior_adaptation_failure_sha256s")
    @classmethod
    def _prior_adaptation_hashes(cls, value: Sequence[str]) -> tuple[str, ...]:
        normalized = tuple(
            _require_sha256(item, field_name="prior_adaptation_failure_sha256")
            for item in value
        )
        if len(normalized) != len(set(normalized)):
            raise ValueError("prior_adaptation_failure_hash_duplicate")
        return normalized

    @field_validator("prior_failed_generation_routes")
    @classmethod
    def _prior_failed_routes(
        cls,
        value: Sequence[FailedGenerationRouteRecordV1],
    ) -> tuple[FailedGenerationRouteRecordV1, ...]:
        normalized = tuple(value)
        if len(normalized) > 2:
            raise ValueError("prior_failed_generation_route_limit_exceeded")
        hashes = tuple(item.record_sha256 for item in normalized)
        if len(hashes) != len(set(hashes)):
            raise ValueError("prior_failed_generation_route_duplicate")
        return normalized

    @model_validator(mode="after")
    def _seal_adaptation_input(self) -> "PlanAdaptationInputEnvelope":
        revision = self.base_envelope.plan_revision
        if revision.compile_purpose.value != "execution_adaptation":
            raise ValueError("adaptation_input_requires_adaptation_revision")
        if revision.plan_revision not in {1, 2}:
            raise ValueError("adaptation_plan_revision_out_of_range")
        if revision.subtask_revision != self.previous_plan.plan_revision.subtask_revision:
            raise ValueError("adaptation_subtask_revision_mismatch")
        revision_gap = revision.plan_revision - self.previous_plan.plan_revision.plan_revision
        if revision_gap != 1:
            if not (
                revision.plan_revision == 2
                and self.previous_plan.plan_revision.plan_revision == 0
                and len(self.prior_adaptation_failure_sha256s) == 1
            ):
                raise ValueError("adaptation_revision_not_successor")
        elif self.prior_adaptation_failure_sha256s:
            raise ValueError("prior_adaptation_failure_hash_unexpected")
        if (
            self.base_envelope.candidate_pool_snapshot.candidate_pool_sha256
            != self.previous_plan.candidate_pool_sha256
            or self.failure_evidence.candidate_pool_sha256
            != self.previous_plan.candidate_pool_sha256
        ):
            raise ValueError("adaptation_candidate_pool_mismatch")
        if self.failure_evidence.plan_sha256 != self.previous_plan.plan_sha256:
            raise ValueError("adaptation_failure_plan_mismatch")
        for route in self.prior_failed_generation_routes:
            if route.candidate_pool_sha256 != self.previous_plan.candidate_pool_sha256:
                raise ValueError("prior_failed_generation_route_candidate_mismatch")
            if route.failure_evidence_sha256 == self.failure_evidence.evidence_sha256:
                raise ValueError("current_failure_repeated_in_prior_route_history")
        if self.recovery_lineage.previous_plan_artifact_sha256 != self.previous_plan_artifact_sha256:
            raise ValueError("adaptation_lineage_artifact_mismatch")
        if self.recovery_lineage.previous_plan_sha256 != self.previous_plan.plan_sha256:
            raise ValueError("adaptation_lineage_plan_mismatch")
        if self.recovery_lineage.failure_evidence_sha256 != self.failure_evidence.evidence_sha256:
            raise ValueError("adaptation_lineage_failure_mismatch")
        if self.temporary_tool_source is not None:
            if (
                self.temporary_tool_source.candidate_pool_sha256
                != self.previous_plan.candidate_pool_sha256
            ):
                raise ValueError("adaptation_temporary_source_candidate_mismatch")
            if (
                self.failure_evidence.resource_id is None
                or self.temporary_tool_source.original_resource_id
                != self.failure_evidence.resource_id
            ):
                raise ValueError("adaptation_temporary_source_failure_mismatch")
        checkpoint_ids = tuple(item.checkpoint_sha256 for item in self.checkpoints)
        if checkpoint_ids != self.recovery_lineage.preserved_checkpoint_ids:
            raise ValueError("adaptation_checkpoint_lineage_mismatch")
        previous_steps = {item.step_id: item for item in self.previous_plan.steps}
        for checkpoint in self.checkpoints:
            step = previous_steps.get(checkpoint.step_id)
            if step is None:
                raise ValueError("adaptation_checkpoint_step_missing")
            if executable_step_semantic_sha256(step) != checkpoint.step_semantic_sha256:
                raise ValueError("adaptation_checkpoint_step_hash_mismatch")
            if step.resource_id != checkpoint.resource_id:
                raise ValueError("adaptation_checkpoint_resource_mismatch")
            if step.entrypoint_id != checkpoint.entrypoint_id:
                raise ValueError("adaptation_checkpoint_entrypoint_mismatch")
        if len(self.diagnostic_excerpt.encode("utf-8")) > 8192:
            raise ValueError("adaptation_diagnostic_too_large")
        if self.diagnostic_excerpt and (
            canonical_sha256(self.diagnostic_excerpt) != self.failure_evidence.diagnostic_sha256
            or len(self.diagnostic_excerpt.encode("utf-8")) != self.failure_evidence.diagnostic_bytes
        ):
            raise ValueError("adaptation_diagnostic_evidence_mismatch")
        projection = self.model_dump(mode="python", exclude={"input_sha256"})
        assert_recovery_projection_safe(projection)
        expected = canonical_sha256(projection)
        if self.input_sha256:
            if _require_sha256(self.input_sha256, field_name="input_sha256") != expected:
                raise ValueError("adaptation_input_sha256_mismatch")
        object.__setattr__(self, "input_sha256", expected)
        return self


class TemporaryToolTransformDirective(FrozenContract):
    protocol: Literal[TEMPORARY_TOOL_PROTOCOL] = TEMPORARY_TOOL_PROTOCOL
    original_resource_id: str = Field(min_length=1)
    generator_step_id: str = Field(min_length=1)
    runner_step_id: str = Field(min_length=1)
    directive_sha256: str = ""

    @model_validator(mode="after")
    def _seal_directive(self) -> "TemporaryToolTransformDirective":
        if self.generator_step_id == self.runner_step_id:
            raise ValueError("temporary_tool_generator_and_runner_step_must_differ")
        projection = self.model_dump(mode="python", exclude={"directive_sha256"})
        expected = canonical_sha256(projection)
        if self.directive_sha256:
            if _require_sha256(
                self.directive_sha256,
                field_name="directive_sha256",
            ) != expected:
                raise ValueError("temporary_tool_directive_sha256_mismatch")
        object.__setattr__(self, "directive_sha256", expected)
        return self


class PlanAdaptationDraft(FrozenContract):
    protocol: Literal[PLAN_ADAPTATION_INPUT_PROTOCOL] = PLAN_ADAPTATION_INPUT_PROTOCOL
    adaptation_kind: AdaptationKind
    preserved_completed_step_ids: tuple[str, ...] = ()
    failure_evidence_sha256: str
    previous_plan_sha256: str
    concise_adaptation_rationale: str = Field(default="")
    temporary_tool_transform: TemporaryToolTransformDirective | None = None
    plan: CompilerPlanDraft
    draft_sha256: str = ""

    @field_validator("failure_evidence_sha256", "previous_plan_sha256")
    @classmethod
    def _adaptation_hashes(cls, value: str, info: Any) -> str:
        return _require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _seal_adaptation_draft(self) -> "PlanAdaptationDraft":
        if len(self.preserved_completed_step_ids) != len(
            set(self.preserved_completed_step_ids)
        ):
            raise ValueError("adaptation_preserved_step_duplicate")
        if (
            self.adaptation_kind is AdaptationKind.TEMPORARY_TOOL_TRANSFORM
        ) != (self.temporary_tool_transform is not None):
            raise ValueError("temporary_tool_transform_directive_mismatch")
        projection = self.model_dump(mode="python", exclude={"draft_sha256"})
        assert_recovery_projection_safe(projection)
        expected = canonical_sha256(projection)
        if self.draft_sha256:
            if _require_sha256(self.draft_sha256, field_name="draft_sha256") != expected:
                raise ValueError("adaptation_draft_sha256_mismatch")
        object.__setattr__(self, "draft_sha256", expected)
        return self


class PlanAdaptationProposalV2(FrozenContract):
    adaptation_kind: AdaptationKind
    preserved_completed_step_ids: tuple[str, ...] = ()
    failure_evidence_sha256: str
    previous_plan_sha256: str
    concise_adaptation_rationale: str = Field(default="")
    temporary_tool_transform: TemporaryToolTransformDirective | None = None
    plan: CompilerPlanProposalV2

    @field_validator("failure_evidence_sha256", "previous_plan_sha256")
    @classmethod
    def _adaptation_hashes(cls, value: str, info: Any) -> str:
        return _require_sha256(value, field_name=info.field_name)


class PlanAdaptationDecisionV3(FrozenContract):
    """V4 adaptation wire; V3 Python name retained for internal import compatibility."""

    protocol: Literal["sgar-plan-adaptation-decision-v5"] = (
        "sgar-plan-adaptation-decision-v5"
    )
    adaptation_kind: Literal[
        AdaptationKind.BINDING_OR_ENTRYPOINT_CORRECTION,
        AdaptationKind.PLAN_RECOMPOSITION,
    ]
    preserved_completed_step_ids: tuple[str, ...] = ()
    failure_evidence_sha256: str
    previous_plan_sha256: str
    concise_adaptation_rationale: str = Field(default="")
    plan_decision: CompilerDecisionProposalV3

    @field_validator("failure_evidence_sha256", "previous_plan_sha256")
    @classmethod
    def _decision_hashes(cls, value: str, info: Any) -> str:
        return _require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _live_adaptation_shape(self) -> "PlanAdaptationDecisionV3":
        if len(self.preserved_completed_step_ids) != len(
            set(self.preserved_completed_step_ids)
        ):
            raise ValueError("adaptation_preserved_step_duplicate")
        assert_recovery_projection_safe(self.model_dump(mode="python"))
        return self

class TemporarySourceDescriptor(FrozenContract):
    protocol: Literal[TEMPORARY_TOOL_PROTOCOL] = TEMPORARY_TOOL_PROTOCOL
    logical_runtime_locator: str = Field(min_length=1)
    source_sha256: str
    size_bytes: int = Field(ge=0)
    relationship: Literal["primary", "supporting"]

    @field_validator("source_sha256")
    @classmethod
    def _source_hash(cls, value: str) -> str:
        return _require_sha256(value, field_name="source_sha256")


class TemporaryToolSourceBundle(FrozenContract):
    protocol: Literal[TEMPORARY_TOOL_PROTOCOL] = TEMPORARY_TOOL_PROTOCOL
    original_resource_id: str = Field(min_length=1)
    original_source_sha256: str
    sources: tuple[TemporarySourceDescriptor, ...]
    primary_runtime_locator: str = Field(min_length=1)
    candidate_pool_sha256: str
    source_bundle_sha256: str = ""

    @field_validator("original_source_sha256", "candidate_pool_sha256")
    @classmethod
    def _bundle_hashes(cls, value: str, info: Any) -> str:
        return _require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _seal_source_bundle(self) -> "TemporaryToolSourceBundle":
        if not self.sources or self.sources[0].relationship != "primary":
            raise ValueError("temporary_tool_primary_source_missing")
        if sum(item.relationship == "primary" for item in self.sources) != 1:
            raise ValueError("temporary_tool_primary_source_not_unique")
        if self.sources[0].source_sha256 != self.original_source_sha256:
            raise ValueError("temporary_tool_primary_source_hash_mismatch")
        locators = tuple(item.logical_runtime_locator for item in self.sources)
        if len(locators) != len(set(locators)):
            raise ValueError("temporary_tool_source_locator_duplicate")
        if self.primary_runtime_locator != self.sources[0].logical_runtime_locator:
            raise ValueError("temporary_tool_primary_locator_mismatch")
        projection = self.model_dump(mode="python", exclude={"source_bundle_sha256"})
        assert_recovery_projection_safe(projection)
        expected = canonical_sha256(projection)
        if self.source_bundle_sha256:
            if _require_sha256(
                self.source_bundle_sha256,
                field_name="source_bundle_sha256",
            ) != expected:
                raise ValueError("temporary_tool_bundle_sha256_mismatch")
        object.__setattr__(self, "source_bundle_sha256", expected)
        return self


PlanAdaptationInputEnvelope.model_rebuild()


class TemporaryToolArtifact(FrozenContract):
    protocol: Literal[TEMPORARY_TOOL_PROTOCOL] = TEMPORARY_TOOL_PROTOCOL
    ephemeral: Literal[True] = True
    original_resource_id: str = Field(min_length=1)
    original_source_sha256: str
    support_bundle_sha256: str
    generated_source_sha256: str
    generator_resource_id: str = Field(min_length=1)
    generator_accounting_operation_id: str = Field(min_length=1)
    runner_resource_id: str = Field(min_length=1)
    runtime_locator: str = Field(min_length=1)
    candidate_pool_sha256: str
    plan_revision: int = Field(ge=1, le=2)
    provenance_sha256: str
    artifact_sha256: str = ""

    @field_validator(
        "original_source_sha256",
        "support_bundle_sha256",
        "generated_source_sha256",
        "candidate_pool_sha256",
        "provenance_sha256",
    )
    @classmethod
    def _temporary_artifact_hashes(cls, value: str, info: Any) -> str:
        return _require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _seal_temporary_artifact(self) -> "TemporaryToolArtifact":
        projection = self.model_dump(mode="python", exclude={"artifact_sha256"})
        assert_recovery_projection_safe(projection)
        expected = canonical_sha256(projection)
        if self.artifact_sha256:
            if _require_sha256(self.artifact_sha256, field_name="artifact_sha256") != expected:
                raise ValueError("temporary_tool_artifact_sha256_mismatch")
        object.__setattr__(self, "artifact_sha256", expected)
        return self


class FullGenerationInputEnvelope(FrozenContract):
    protocol: Literal[FULL_GENERATION_PROTOCOL] = FULL_GENERATION_PROTOCOL
    revision: SubtaskRevisionRef
    contract_projection: dict[str, Any]
    public_context: CompilerPublicContext
    authorized_materials: AuthorizedModelMaterialView
    checkpoints: tuple[CompletedStepCheckpoint, ...] = ()
    failure_evidence_sha256: tuple[str, ...] = ()
    candidate_pool_sha256: str
    system_policy: SystemFullGenerationPolicy
    diagnostic_excerpt: str = Field(default="", max_length=8192)
    input_sha256: str = ""

    @field_validator("candidate_pool_sha256")
    @classmethod
    def _full_generation_candidate_hash(cls, value: str) -> str:
        return _require_sha256(value, field_name="candidate_pool_sha256")

    @field_validator("failure_evidence_sha256")
    @classmethod
    def _full_generation_failure_hashes(cls, value: Sequence[str]) -> tuple[str, ...]:
        return tuple(
            _require_sha256(item, field_name="failure_evidence_sha256")
            for item in value
        )

    @model_validator(mode="after")
    def _seal_full_generation_input(self) -> "FullGenerationInputEnvelope":
        if len(self.failure_evidence_sha256) != len(set(self.failure_evidence_sha256)):
            raise ValueError("full_generation_failure_evidence_duplicate")
        if len(self.diagnostic_excerpt.encode("utf-8")) > 8192:
            raise ValueError("full_generation_diagnostic_too_large")
        if self.authorized_materials.revision != self.revision:
            raise ValueError("full_generation_material_revision_mismatch")
        projection = self.model_dump(mode="python", exclude={"input_sha256"})
        assert_recovery_projection_safe(projection)
        expected = canonical_sha256(projection)
        if self.input_sha256:
            if _require_sha256(self.input_sha256, field_name="input_sha256") != expected:
                raise ValueError("full_generation_input_sha256_mismatch")
        object.__setattr__(self, "input_sha256", expected)
        return self


class FullGenerationDraft(FrozenContract):
    protocol: Literal[FULL_GENERATION_PROTOCOL] = FULL_GENERATION_PROTOCOL
    artifact_type: str = Field(min_length=1)
    content: str
    concise_rationale: str = Field(default="")


def validate_adaptation_decision_identity(*, adaptation_input: PlanAdaptationInputEnvelope,
                                          decision: PlanAdaptationDraft | PlanAdaptationDecisionV3) -> None:
    """Shared identity checks for both no-plan and successful adaptation decisions."""
    expected_step_ids = tuple(item.step_id for item in adaptation_input.checkpoints)
    if decision.preserved_completed_step_ids != expected_step_ids:
        raise RecoveryControlError("adaptation_draft_checkpoint_set_mismatch")
    if decision.failure_evidence_sha256 != adaptation_input.failure_evidence.evidence_sha256:
        raise RecoveryControlError("adaptation_draft_failure_hash_mismatch")
    if decision.previous_plan_sha256 != adaptation_input.previous_plan.plan_sha256:
        raise RecoveryControlError("adaptation_draft_previous_plan_hash_mismatch")


def validate_adapted_plan_lineage(
    *,
    adapted_plan: ExecutablePlan,
    adaptation_input: PlanAdaptationInputEnvelope,
    adaptation_draft: PlanAdaptationDraft,
) -> None:
    validate_adaptation_decision_identity(adaptation_input=adaptation_input, decision=adaptation_draft)
    reject_repeated_failed_generation_route(
        previous_plan=adaptation_input.previous_plan,
        adapted_plan=adapted_plan,
        failure_evidence=adaptation_input.failure_evidence,
    )
    reject_repeated_failed_tool_input_route(
        previous_plan=adaptation_input.previous_plan,
        adapted_plan=adapted_plan,
        failure_evidence=adaptation_input.failure_evidence,
    )
    reject_prior_failed_generation_routes(
        adapted_plan=adapted_plan,
        prior_failed_generation_routes=(
            adaptation_input.prior_failed_generation_routes
        ),
    )
    expected_step_ids = tuple(item.step_id for item in adaptation_input.checkpoints)
    adapted_steps = {item.step_id: item for item in adapted_plan.steps}
    for checkpoint in adaptation_input.checkpoints:
        step = adapted_steps.get(checkpoint.step_id)
        if step is None:
            raise RecoveryControlError("adaptation_checkpoint_removed")
        if executable_step_semantic_sha256(step) != checkpoint.step_semantic_sha256:
            raise RecoveryControlError("adaptation_checkpoint_modified")
    forbidden = set(adaptation_input.recovery_lineage.rerun_forbidden_call_signatures)
    for step in adapted_plan.steps:
        if step.step_id in expected_step_ids:
            continue
        if executable_step_call_signature(step) in forbidden:
            raise RecoveryControlError("adaptation_forbidden_call_repeated")
    directive = adaptation_draft.temporary_tool_transform
    if directive is not None:
        if adaptation_input.temporary_tool_source is None:
            raise RecoveryControlError("temporary_tool_source_not_eligible")
        if (
            directive.original_resource_id
            != adaptation_input.temporary_tool_source.original_resource_id
        ):
            raise RecoveryControlError("temporary_tool_source_directive_mismatch")
        by_id = {item.step_id: item for item in adapted_plan.steps}
        generator = by_id.get(directive.generator_step_id)
        runner = by_id.get(directive.runner_step_id)
        if generator is None or runner is None:
            raise RecoveryControlError("temporary_tool_directive_step_missing")
        if generator.resource_type not in {"Model", "Agent"}:
            raise RecoveryControlError("temporary_tool_directive_generator_type_invalid")
        generator_model_id = (
            generator.agent_base_model_resource_id
            if generator.resource_type == "Agent"
            else generator.resource_id
        )
        cards = {
            item.resource_id: item
            for item in adaptation_input.base_envelope.candidate_cards
        }
        generator_model_card = cards.get(str(generator_model_id or ""))
        role_contracts = (
            generator_model_card.runtime_requirements.get(
                "sgar_system_role_contracts"
            )
            if generator_model_card is not None
            else None
        )
        temporary_contract = (
            role_contracts.get("temporary_tool")
            if isinstance(role_contracts, Mapping)
            else None
        )
        if not isinstance(temporary_contract, Mapping):
            raise RecoveryControlError("temporary_tool_generator_format_evidence_missing")
        projected_contract = dict(temporary_contract)
        supplied_contract_hash = str(
            projected_contract.pop("format_contract_sha256", "")
        )
        if supplied_contract_hash != canonical_sha256(projected_contract):
            raise RecoveryControlError("temporary_tool_generator_format_evidence_invalid")
        allowed_modes = set(
            temporary_contract.get("allowed_enforcement_modes") or ()
        )
        selected_mode = str(
            temporary_contract.get("selected_enforcement_mode") or ""
        )
        if (
            not bool(temporary_contract.get("eligible"))
            or selected_mode
            not in {"native_strict_schema", "json_object_local_validator"}
            or selected_mode not in allowed_modes
        ):
            raise RecoveryControlError("temporary_tool_generator_format_incompatible")
        if runner.resource_type != "Tool":
            raise RecoveryControlError("temporary_tool_directive_runner_type_invalid")
        if generator.step_id not in runner.depends_on:
            raise RecoveryControlError("temporary_tool_runner_dependency_missing")
        if directive.original_resource_id not in adaptation_input.previous_plan.selected_resource_ids:
            raise RecoveryControlError("temporary_tool_original_resource_not_previously_selected")
        if (
            adaptation_input.failure_evidence.resource_id is not None
            and directive.original_resource_id
            != adaptation_input.failure_evidence.resource_id
        ):
            raise RecoveryControlError("temporary_tool_original_resource_not_failed_tool")

        def references_generator(value: Any) -> bool:
            if isinstance(value, Mapping):
                if (
                    str(value.get("from_step") or "") == generator.step_id
                    and str(value.get("output_key") or "") == generator.output_key
                ):
                    return True
                return any(references_generator(item) for item in value.values())
            if isinstance(value, (list, tuple)):
                return any(references_generator(item) for item in value)
            return False

        if not references_generator(runner.input_bindings):
            raise RecoveryControlError("temporary_tool_runner_source_binding_missing")


class RecoveryEventLedger:
    """Thread-safe append-only recovery ledger with immutable artifacts."""

    def __init__(self, *, output_dir: str | Path, run_id: str) -> None:
        self.output_dir = Path(output_dir).resolve()
        self.run_id = str(run_id).strip()
        if not self.run_id:
            raise RecoveryPersistenceError("recovery_run_id_empty")
        self.recovery_dir = self.output_dir / "recovery"
        self.events_path = self.recovery_dir / "recovery_events.jsonl"
        self.summary_path = self.recovery_dir / "recovery_summary.json"
        self.temporary_tools_dir = self.recovery_dir / "temporary_tools"
        self._lock = threading.RLock()
        self._events: list[dict[str, Any]] = []
        self._model_cost_projection: dict[str, Any] | None = None
        self._closed = False
        try:
            self.recovery_dir.mkdir(parents=True, exist_ok=True)
            self.temporary_tools_dir.mkdir(parents=True, exist_ok=True)
            if self.events_path.exists() and self.events_path.stat().st_size:
                raise RecoveryPersistenceError("recovery_ledger_already_exists")
            self.write_summary()
        except RecoveryPersistenceError:
            raise
        except OSError as exc:
            raise RecoveryPersistenceError("recovery_ledger_initialization_failed") from exc

    def append_event(self, event_type: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        event = {
            "schema_version": RECOVERY_EVENT_PROTOCOL,
            "event_type": str(event_type),
            "event_id": uuid.uuid4().hex,
            "run_id": self.run_id,
            **dict(payload),
        }
        assert_recovery_projection_safe(event)
        serialized = canonical_json_bytes(event).decode("utf-8")
        with self._lock:
            if self._closed:
                raise RecoveryPersistenceError("recovery_ledger_closed")
            try:
                with self.events_path.open("a", encoding="utf-8", newline="\n") as handle:
                    handle.write(serialized)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
            except OSError as exc:
                raise RecoveryPersistenceError("recovery_event_append_failed") from exc
            self._events.append(event)
        return dict(event)

    def persist_artifact(self, name: str, payload: Mapping[str, Any]) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+\.json", str(name)):
            raise RecoveryPersistenceError("recovery_artifact_name_invalid")
        projection = dict(payload)
        assert_recovery_projection_safe(projection)
        target = self.recovery_dir / name
        serialized = canonical_json_bytes(projection) + b"\n"
        with self._lock:
            if target.exists():
                try:
                    if target.read_bytes() == serialized:
                        return target
                except OSError as exc:
                    raise RecoveryPersistenceError("recovery_artifact_read_failed") from exc
                raise RecoveryPersistenceError("recovery_artifact_overwrite_forbidden")
            temp = temporary_sibling_path(target)
            try:
                with temp.open("xb") as handle:
                    handle.write(serialized)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp, target)
            except OSError as exc:
                try:
                    if temp.exists():
                        temp.unlink()
                except OSError:
                    pass
                raise RecoveryPersistenceError("recovery_artifact_persist_failed") from exc
        return target

    def summary(self) -> dict[str, Any]:
        with self._lock:
            counts = Counter(str(item.get("event_type")) for item in self._events)
            terminal = [
                item for item in self._events
                if item.get("event_type") in {"recovery_terminal", "recovery_interrupted"}
            ]
            started_identities = {
                str(item.get("recovery_identity_sha256"))
                for item in self._events
                if item.get("event_type") == "recovery_started"
                and item.get("recovery_identity_sha256")
            }
            terminal_identities = {
                str(item.get("recovery_identity_sha256"))
                for item in terminal
                if item.get("recovery_identity_sha256")
            }
            started_candidates = {
                str(item.get("recovery_identity_sha256")): str(
                    item.get("candidate_pool_sha256")
                )
                for item in self._events
                if item.get("event_type") == "recovery_started"
                and item.get("recovery_identity_sha256")
                and item.get("candidate_pool_sha256")
            }
            terminal_candidates = {
                str(item.get("recovery_identity_sha256")): str(
                    item.get("candidate_pool_sha256")
                )
                for item in terminal
                if item.get("recovery_identity_sha256")
                and item.get("candidate_pool_sha256")
            }
            candidate_consistent = all(
                terminal_candidates.get(identity) == candidate_hash
                for identity, candidate_hash in started_candidates.items()
                if identity in terminal_candidates
            )
            incomplete = sorted(started_identities - terminal_identities)
            unbound_started_count = sum(
                1
                for item in self._events
                if item.get("event_type") == "recovery_started"
                and not item.get("recovery_identity_sha256")
            )
            unbound_terminal_count = sum(
                1
                for item in terminal
                if not item.get("recovery_identity_sha256")
            )
            full_generation_started = Counter(
                str(item.get("recovery_identity_sha256") or "")
                for item in self._events
                if item.get("event_type") == "full_generation_started"
            )
            full_generation_finished = Counter(
                str(item.get("recovery_identity_sha256") or "")
                for item in self._events
                if item.get("event_type") == "full_generation_finished"
            )
            incomplete_full_generation_calls = sum(
                max(0, count - full_generation_finished.get(identity, 0))
                for identity, count in full_generation_started.items()
            )
            candidate_hashes = sorted(
                {
                    str(item.get("candidate_pool_sha256"))
                    for item in self._events
                    if item.get("candidate_pool_sha256")
                }
            )
            by_responsibility: Counter[str] = Counter()
            by_failure_stage: Counter[str] = Counter()
            accounting_references: set[str] = set()
            plan_lineage: list[dict[str, Any]] = []
            for item in self._events:
                responsibility = item.get("responsibility")
                failure_stage = item.get("failure_stage")
                if responsibility:
                    by_responsibility[str(responsibility)] += 1
                if failure_stage:
                    by_failure_stage[str(failure_stage)] += 1
                for name in (
                    "accounting_operation_id",
                    "generator_accounting_operation_id",
                    "usage_reference",
                ):
                    if item.get(name):
                        accounting_references.add(str(item[name]))
                if item.get("event_type") == "recovery_terminal":
                    plan_lineage.append(
                        {
                            "recovery_identity_sha256": item.get(
                                "recovery_identity_sha256"
                            ),
                            "recovery_operation_sha256": item.get(
                                "recovery_operation_sha256"
                            ),
                            "plan_artifact_sha256s": list(
                                item.get("plan_artifact_sha256s") or ()
                            ),
                            "failure_evidence_sha256s": list(
                                item.get("failure_evidence_sha256s") or ()
                            ),
                            "status": item.get("status"),
                        }
                    )
            payload = {
                "schema_version": RECOVERY_EVENT_PROTOCOL,
                "run_id": self.run_id,
                "event_count": len(self._events),
                "event_counts": dict(sorted(counts.items())),
                "terminal_count": len(terminal),
                "started_recovery_count": (
                    len(started_identities) + unbound_started_count
                ),
                "incomplete_recovery_identity_sha256s": incomplete,
                "incomplete_calls": (
                    len(incomplete) + incomplete_full_generation_calls
                ),
                "incomplete_full_generation_calls": incomplete_full_generation_calls,
                "complete": (
                    bool(started_identities or unbound_started_count)
                    and not incomplete
                    and unbound_terminal_count >= unbound_started_count
                    and incomplete_full_generation_calls == 0
                ),
                "adaptation_attempts": counts.get("plan_adaptation_started", 0),
                "adaptation_successes": counts.get("plan_adaptation_finished", 0),
                "full_generation_attempts": counts.get("full_generation_started", 0),
                "full_generation_terminal_count": counts.get(
                    "full_generation_finished", 0
                ),
                "full_generation_successes": sum(
                    1
                    for item in self._events
                    if item.get("event_type") == "full_generation_finished"
                    and item.get("status") == "success"
                ),
                "checkpoint_reused_count": counts.get("checkpoint_reused", 0),
                "duplicate_execution_prevented_count": counts.get(
                    "checkpoint_reused", 0
                ),
                "temporary_tool_attempts": counts.get(
                    "temporary_tool_source_registered", 0
                ),
                "temporary_tool_successes": counts.get(
                    "temporary_tool_generated", 0
                ),
                "by_responsibility": dict(sorted(by_responsibility.items())),
                "by_failure_stage": dict(sorted(by_failure_stage.items())),
                "candidate_pool_sha256s": candidate_hashes,
                "candidate_hash_consistent_per_recovery": candidate_consistent,
                "plan_lineage": plan_lineage,
                "model_accounting_references": sorted(accounting_references),
                "recovery_model_cost": (
                    dict(self._model_cost_projection)
                    if self._model_cost_projection is not None
                    else {
                        "status": "pending_final_join",
                        "operation_ids": sorted(accounting_references),
                    }
                ),
                "recovery_ledger_sha256": canonical_sha256(self._events),
                "host_path_occurrences": [],
                "hidden_value_occurrences": [],
                "safety_audit": {
                    "host_free": True,
                    "hidden_values_recorded": False,
                    "raw_diagnostics_recorded": False,
                    "raw_model_payloads_recorded": False,
                },
            }
            return payload

    def write_summary(self) -> dict[str, Any]:
        payload = self.summary()
        data = canonical_json_bytes(payload) + b"\n"
        temp = temporary_sibling_path(self.summary_path)
        try:
            with temp.open("wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, self.summary_path)
        except OSError as exc:
            raise RecoveryPersistenceError("recovery_summary_write_failed") from exc
        return payload

    def close(
        self,
        *,
        model_cost_projection: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if model_cost_projection is not None:
                projection = dict(model_cost_projection)
                assert_recovery_projection_safe(projection)
                self._model_cost_projection = projection
            summary = self.write_summary()
            self._closed = True
            return summary


__all__ = [
    "FAILED_GENERATION_ROUTE_PROTOCOL",
    "FULL_GENERATION_PROTOCOL",
    "PLAN_ADAPTATION_INPUT_PROTOCOL",
    "RECOVERY_EVENT_PROTOCOL",
    "RECOVERY_EVIDENCE_PROTOCOL",
    "RECOVERY_LINEAGE_PROTOCOL",
    "RECOVERY_POLICY_PROTOCOL",
    "RECOVERY_RUNTIME_PROTOCOL",
    "TEMPORARY_TOOL_PROTOCOL",
    "AdaptationKind",
    "CompletedStepCheckpoint",
    "FullGenerationDraft",
    "FullGenerationInputEnvelope",
    "FailedGenerationRouteRecordV1",
    "PlanAdaptationDraft",
    "PlanAdaptationInputEnvelope",
    "RecoveryControlError",
    "RecoveryEventLedger",
    "RecoveryLineage",
    "RecoveryOperationRef",
    "RecoveryPersistenceError",
    "RecoveryPolicy",
    "SideEffectEvidence",
    "SideEffectStatus",
    "StructuredExecutionFailureEvidence",
    "SystemFullGenerationPolicy",
    "TemporarySourceDescriptor",
    "TemporaryToolTransformDirective",
    "TemporaryToolArtifact",
    "TemporaryToolSourceBundle",
    "assert_recovery_projection_safe",
    "executable_step_call_signature",
    "executable_step_semantic_sha256",
    "failed_generation_route_record",
    "load_recovery_policy",
    "resolve_system_full_generation_policy",
    "reject_prior_failed_generation_routes",
    "reject_repeated_failed_tool_input_route",
    "validate_adapted_plan_lineage",
]
