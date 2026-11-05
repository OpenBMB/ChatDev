"""Versioned, immutable control contracts for the S-GAR pipeline.

This module deliberately contains no runtime orchestration.  It freezes the
identity, retrieval, candidate-pool, recovery, and artifact-commit contracts
that later Router/Planner/Compiler work can share without changing today's
execution behaviour.
"""

from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal
from enum import Enum
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


PIPELINE_CONTROL_PROTOCOL = "sgar-pipeline-control-v1"
SHA256_HEX_LENGTH = 64


class PipelineControlError(ValueError):
    """Raised when a versioned pipeline-control invariant is violated."""


class FrozenContract(BaseModel):
    """Base class for immutable, strict protocol values."""

    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=False)


def _canonical_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _canonical_value(value.model_dump(mode="python", exclude_none=False))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise PipelineControlError("canonical_decimal_must_be_finite")
        return format(value.normalize(), "f")
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise PipelineControlError("canonical_float_must_be_finite")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise PipelineControlError(f"unsupported_canonical_type:{type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    """Return the protocol's stable UTF-8 JSON representation."""

    return json.dumps(
        _canonical_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    """Hash a protocol value without timestamps or dictionary-order effects."""

    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _require_sha256(value: str, *, field_name: str) -> str:
    normalized = str(value).strip().lower()
    if len(normalized) != SHA256_HEX_LENGTH or any(
        char not in "0123456789abcdef" for char in normalized
    ):
        raise ValueError(f"{field_name}_must_be_sha256_hex")
    return normalized


class SubtaskRevisionRef(FrozenContract):
    protocol: Literal[PIPELINE_CONTROL_PROTOCOL] = PIPELINE_CONTROL_PROTOCOL
    graph_revision: int = Field(ge=0)
    subtask_id: str = Field(min_length=1)
    subtask_revision: int = Field(ge=0)

    @field_validator("subtask_id")
    @classmethod
    def _strip_subtask_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("subtask_id_empty")
        return normalized


def subtask_revision_identity_sha256(revision: SubtaskRevisionRef) -> str:
    """Return the canonical identity for a graph subtask revision."""

    if not isinstance(revision, SubtaskRevisionRef):
        raise TypeError("subtask_revision_identity_requires_subtask_revision_ref")
    return canonical_sha256(revision.model_dump(mode="json"))


class FailureResponsibility(str, Enum):
    FRAMEWORK = "framework"
    INFRASTRUCTURE = "infrastructure"
    RESEARCH = "research"
    BUDGET = "budget"


class RetrievalAttemptOutcome(str, Enum):
    SUCCESS = "success"
    INFRASTRUCTURE_FAILURE = "infrastructure_failure"
    TERMINAL_FAILURE = "terminal_failure"


class RetrievalAttemptRecord(FrozenContract):
    protocol: Literal[PIPELINE_CONTROL_PROTOCOL] = PIPELINE_CONTROL_PROTOCOL
    revision: SubtaskRevisionRef
    attempt: int = Field(ge=1, le=3)
    query_sha256: str
    profile_sha256: str
    policy_sha256: str
    index_sha256: str
    pool_sha256: str
    outcome: RetrievalAttemptOutcome
    failure_responsibility: FailureResponsibility | None = None
    failure_code: str | None = None

    @field_validator(
        "query_sha256",
        "profile_sha256",
        "policy_sha256",
        "index_sha256",
        "pool_sha256",
    )
    @classmethod
    def _validate_hashes(cls, value: str, info: Any) -> str:
        return _require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _validate_outcome(self) -> "RetrievalAttemptRecord":
        if self.outcome is RetrievalAttemptOutcome.SUCCESS:
            if self.failure_responsibility is not None or self.failure_code is not None:
                raise ValueError("successful_retrieval_cannot_have_failure")
        else:
            if self.failure_responsibility is None or not self.failure_code:
                raise ValueError("failed_retrieval_requires_structured_failure")
            if (
                self.outcome is RetrievalAttemptOutcome.INFRASTRUCTURE_FAILURE
                and self.failure_responsibility is not FailureResponsibility.INFRASTRUCTURE
            ):
                raise ValueError("infrastructure_outcome_requires_infrastructure_responsibility")
        return self


class CandidateOrigin(str, Enum):
    RETRIEVAL = "retrieval"
    CONTRACT_DELIVERY = "contract_delivery"
    REQUIRED_OPERATION = "required_operation"
    USER_EXECUTION_REQUIREMENT = "user_execution_requirement"
    PLANNER_CAPABILITY_EVIDENCE = "planner_capability_evidence"
    EXPLICIT_DEPENDENCY = "explicit_dependency"
    DEPENDENCY_SLOT = "dependency_slot"
    AGENT_BASE_MODEL = "agent_base_model"


class CandidateResourceRef(FrozenContract):
    resource_id: str = Field(min_length=1)
    resource_type: str = Field(min_length=1)
    origin: CandidateOrigin
    required_by_resource_id: str | None = None
    dependency_slot: str | None = None

    @field_validator("resource_id", "resource_type")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("candidate_identity_empty")
        return normalized

    @model_validator(mode="after")
    def _validate_origin_evidence(self) -> "CandidateResourceRef":
        if self.origin in {
            CandidateOrigin.RETRIEVAL,
            CandidateOrigin.CONTRACT_DELIVERY,
            CandidateOrigin.REQUIRED_OPERATION,
            CandidateOrigin.PLANNER_CAPABILITY_EVIDENCE,
            CandidateOrigin.USER_EXECUTION_REQUIREMENT,
        }:
            if self.required_by_resource_id is not None or self.dependency_slot is not None:
                raise ValueError("independent_candidate_cannot_claim_dependency_origin")
        elif not self.required_by_resource_id:
            raise ValueError("dependency_candidate_requires_parent_resource")
        if self.origin is CandidateOrigin.DEPENDENCY_SLOT and not self.dependency_slot:
            raise ValueError("dependency_slot_origin_requires_slot")
        return self


class CandidatePoolSnapshot(FrozenContract):
    protocol: Literal[PIPELINE_CONTROL_PROTOCOL] = PIPELINE_CONTROL_PROTOCOL
    revision: SubtaskRevisionRef
    candidates: tuple[CandidateResourceRef, ...]
    pool_sha256: str
    index_sha256: str
    policy_sha256: str
    availability_sha256: str
    frozen: Literal[True] = True
    candidate_pool_sha256: str = ""

    @field_validator("pool_sha256", "index_sha256", "policy_sha256", "availability_sha256")
    @classmethod
    def _validate_hashes(cls, value: str, info: Any) -> str:
        return _require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _seal_snapshot(self) -> "CandidatePoolSnapshot":
        identities = [(item.resource_type, item.resource_id) for item in self.candidates]
        if len(identities) != len(set(identities)):
            raise ValueError("candidate_pool_contains_duplicate_typed_reference")
        projection = self.model_dump(mode="python", exclude={"candidate_pool_sha256"})
        expected = canonical_sha256(projection)
        if self.candidate_pool_sha256:
            supplied = _require_sha256(
                self.candidate_pool_sha256,
                field_name="candidate_pool_sha256",
            )
            if supplied != expected:
                raise ValueError("candidate_pool_sha256_mismatch")
        object.__setattr__(self, "candidate_pool_sha256", expected)
        return self


class PerTypeConfidenceStatistics(FrozenContract):
    resource_type: str = Field(min_length=1)
    candidate_count: int = Field(ge=0)
    quota: int = Field(ge=0)
    contract_compatible_count: int = Field(ge=0)
    dependency_covered_count: int = Field(ge=0)
    score_min: float | None = None
    score_mean: float | None = None
    score_max: float | None = None

    @field_validator("score_min", "score_mean", "score_max")
    @classmethod
    def _finite_scores(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("confidence_score_must_be_finite")
        return value

    @model_validator(mode="after")
    def _validate_counts_and_scores(self) -> "PerTypeConfidenceStatistics":
        for value in (self.contract_compatible_count, self.dependency_covered_count):
            if value > self.candidate_count:
                raise ValueError("confidence_coverage_count_exceeds_candidates")
        scores = (self.score_min, self.score_mean, self.score_max)
        if self.candidate_count == 0 and any(score is not None for score in scores):
            raise ValueError("empty_candidate_type_cannot_have_scores")
        if self.candidate_count > 0 and not all(score is not None for score in scores):
            raise ValueError("nonempty_candidate_type_requires_score_statistics")
        if all(score is not None for score in scores) and not (
            self.score_min <= self.score_mean <= self.score_max  # type: ignore[operator]
        ):
            raise ValueError("confidence_score_order_invalid")
        return self


class RetrievalConfidenceEvidence(FrozenContract):
    protocol: Literal[PIPELINE_CONTROL_PROTOCOL] = PIPELINE_CONTROL_PROTOCOL
    revision: SubtaskRevisionRef
    candidate_pool_sha256: str
    per_type: tuple[PerTypeConfidenceStatistics, ...]
    quota_coverage: bool
    contract_coverage: bool
    dependency_coverage: bool
    original_query_hyde_consistency: float | None = None
    calibration_status: Literal["unconfigured"] = "unconfigured"
    evidence_sha256: str = ""

    @field_validator("candidate_pool_sha256")
    @classmethod
    def _validate_pool_hash(cls, value: str) -> str:
        return _require_sha256(value, field_name="candidate_pool_sha256")

    @field_validator("original_query_hyde_consistency")
    @classmethod
    def _validate_consistency(cls, value: float | None) -> float | None:
        if value is not None and (not math.isfinite(value) or not 0.0 <= value <= 1.0):
            raise ValueError("query_hyde_consistency_out_of_range")
        return value

    @model_validator(mode="after")
    def _seal_evidence(self) -> "RetrievalConfidenceEvidence":
        resource_types = [item.resource_type for item in self.per_type]
        if len(resource_types) != len(set(resource_types)):
            raise ValueError("duplicate_confidence_resource_type")
        projection = self.model_dump(mode="python", exclude={"evidence_sha256"})
        expected = canonical_sha256(projection)
        if self.evidence_sha256:
            supplied = _require_sha256(self.evidence_sha256, field_name="evidence_sha256")
            if supplied != expected:
                raise ValueError("retrieval_confidence_evidence_sha256_mismatch")
        object.__setattr__(self, "evidence_sha256", expected)
        return self


class PlannerReplanRequest(FrozenContract):
    protocol: Literal[PIPELINE_CONTROL_PROTOCOL] = PIPELINE_CONTROL_PROTOCOL
    revision: SubtaskRevisionRef
    trigger: Literal["retrieval_confidence"] = "retrieval_confidence"
    current_node_id: str = Field(min_length=1)
    affected_downstream_node_ids: tuple[str, ...] = ()
    preserved_completed_node_ids: tuple[str, ...] = ()
    evidence_sha256: str
    replan_attempt: int = Field(ge=1, le=2)

    @field_validator("evidence_sha256")
    @classmethod
    def _validate_evidence_hash(cls, value: str) -> str:
        return _require_sha256(value, field_name="evidence_sha256")

    @model_validator(mode="after")
    def _validate_node_sets(self) -> "PlannerReplanRequest":
        affected = {self.current_node_id, *self.affected_downstream_node_ids}
        preserved = set(self.preserved_completed_node_ids)
        if affected & preserved:
            raise ValueError("replan_affected_and_preserved_nodes_overlap")
        if len(self.affected_downstream_node_ids) != len(set(self.affected_downstream_node_ids)):
            raise ValueError("duplicate_affected_downstream_node")
        if len(self.preserved_completed_node_ids) != len(set(self.preserved_completed_node_ids)):
            raise ValueError("duplicate_preserved_completed_node")
        return self


class RecoveryState(str, Enum):
    SUBTASK_READY = "SUBTASK_READY"
    RETRIEVING = "RETRIEVING"
    RETRIEVAL_RETRY = "RETRIEVAL_RETRY"
    REPLAN_REQUESTED = "REPLAN_REQUESTED"
    CANDIDATE_POOL_FROZEN = "CANDIDATE_POOL_FROZEN"
    PLAN_COMPILING = "PLAN_COMPILING"
    EXECUTING = "EXECUTING"
    PLAN_ADAPTING = "PLAN_ADAPTING"
    FULL_GENERATION = "FULL_GENERATION"
    EVALUATING = "EVALUATING"
    ARTIFACT_STAGED = "ARTIFACT_STAGED"
    ARTIFACT_COMMITTED = "ARTIFACT_COMMITTED"
    TERMINAL_FAILURE = "TERMINAL_FAILURE"


_ALLOWED_TRANSITIONS: Mapping[RecoveryState, frozenset[RecoveryState]] = {
    RecoveryState.SUBTASK_READY: frozenset(
        {RecoveryState.RETRIEVING, RecoveryState.TERMINAL_FAILURE}
    ),
    RecoveryState.RETRIEVING: frozenset(
        {
            RecoveryState.RETRIEVAL_RETRY,
            RecoveryState.REPLAN_REQUESTED,
            RecoveryState.CANDIDATE_POOL_FROZEN,
            RecoveryState.TERMINAL_FAILURE,
        }
    ),
    RecoveryState.RETRIEVAL_RETRY: frozenset(
        {RecoveryState.RETRIEVING, RecoveryState.TERMINAL_FAILURE}
    ),
    RecoveryState.REPLAN_REQUESTED: frozenset(
        {RecoveryState.RETRIEVING, RecoveryState.TERMINAL_FAILURE}
    ),
    RecoveryState.CANDIDATE_POOL_FROZEN: frozenset(
        {RecoveryState.PLAN_COMPILING, RecoveryState.TERMINAL_FAILURE}
    ),
    RecoveryState.PLAN_COMPILING: frozenset(
        {
            RecoveryState.EXECUTING,
            RecoveryState.PLAN_ADAPTING,
            RecoveryState.FULL_GENERATION,
            RecoveryState.TERMINAL_FAILURE,
        }
    ),
    RecoveryState.EXECUTING: frozenset(
        {
            RecoveryState.PLAN_ADAPTING,
            RecoveryState.FULL_GENERATION,
            RecoveryState.EVALUATING,
            RecoveryState.TERMINAL_FAILURE,
        }
    ),
    RecoveryState.PLAN_ADAPTING: frozenset(
        {
            RecoveryState.EXECUTING,
            RecoveryState.FULL_GENERATION,
            RecoveryState.TERMINAL_FAILURE,
        }
    ),
    RecoveryState.FULL_GENERATION: frozenset(
        {RecoveryState.EVALUATING, RecoveryState.TERMINAL_FAILURE}
    ),
    RecoveryState.EVALUATING: frozenset(
        {
            RecoveryState.EVALUATING,
            RecoveryState.ARTIFACT_STAGED,
            RecoveryState.TERMINAL_FAILURE,
        }
    ),
    RecoveryState.ARTIFACT_STAGED: frozenset(
        {RecoveryState.ARTIFACT_COMMITTED, RecoveryState.TERMINAL_FAILURE}
    ),
    RecoveryState.ARTIFACT_COMMITTED: frozenset(),
    RecoveryState.TERMINAL_FAILURE: frozenset(),
}


class RecoveryControlSnapshot(FrozenContract):
    protocol: Literal[PIPELINE_CONTROL_PROTOCOL] = PIPELINE_CONTROL_PROTOCOL
    revision: SubtaskRevisionRef
    state: RecoveryState = RecoveryState.SUBTASK_READY
    retrieval_attempts: int = Field(default=0, ge=0, le=3)
    replan_count: int = Field(default=0, ge=0, le=2)
    adaptation_count: int = Field(default=0, ge=0, le=2)
    full_generation_count: int = Field(default=0, ge=0, le=1)
    evaluator_retry_count: int = Field(default=0, ge=0, le=1)
    candidate_pool_sha256: str | None = None
    artifact_verified: bool = False

    @field_validator("candidate_pool_sha256")
    @classmethod
    def _validate_optional_pool_hash(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_sha256(value, field_name="candidate_pool_sha256")

    @model_validator(mode="after")
    def _validate_snapshot(self) -> "RecoveryControlSnapshot":
        post_freeze = {
            RecoveryState.CANDIDATE_POOL_FROZEN,
            RecoveryState.PLAN_COMPILING,
            RecoveryState.EXECUTING,
            RecoveryState.PLAN_ADAPTING,
            RecoveryState.FULL_GENERATION,
            RecoveryState.EVALUATING,
            RecoveryState.ARTIFACT_STAGED,
            RecoveryState.ARTIFACT_COMMITTED,
        }
        if self.state in post_freeze and self.candidate_pool_sha256 is None:
            raise ValueError("post_freeze_state_requires_candidate_pool_sha256")
        if self.state is RecoveryState.ARTIFACT_COMMITTED and not self.artifact_verified:
            raise ValueError("committed_artifact_must_be_verified")
        return self


def initial_recovery_snapshot(revision: SubtaskRevisionRef) -> RecoveryControlSnapshot:
    return RecoveryControlSnapshot(revision=revision)


def validate_recovery_transition(
    previous: RecoveryControlSnapshot,
    target_state: RecoveryState,
    *,
    revision: SubtaskRevisionRef | None = None,
    candidate_pool_sha256: str | None = None,
    artifact_verified: bool | None = None,
) -> RecoveryControlSnapshot:
    """Validate one state-machine edge and return the immutable next snapshot."""

    if target_state not in _ALLOWED_TRANSITIONS[previous.state]:
        raise PipelineControlError(
            f"invalid_recovery_transition:{previous.state.value}->{target_state.value}"
        )

    next_revision = revision or previous.revision
    leaving_replan = (
        previous.state is RecoveryState.REPLAN_REQUESTED
        and target_state is RecoveryState.RETRIEVING
    )
    if leaving_replan:
        if revision is None:
            raise PipelineControlError("replan_transition_requires_new_revision")
        if next_revision.subtask_id != previous.revision.subtask_id:
            raise PipelineControlError("replan_cannot_change_subtask_identity")
        if next_revision.graph_revision <= previous.revision.graph_revision:
            raise PipelineControlError("replan_must_increment_graph_revision")
        if next_revision.subtask_revision <= previous.revision.subtask_revision:
            raise PipelineControlError("replan_must_increment_subtask_revision")
    elif next_revision != previous.revision:
        raise PipelineControlError("revision_change_only_allowed_after_replan")

    retrieval_attempts = previous.retrieval_attempts
    replan_count = previous.replan_count
    adaptation_count = previous.adaptation_count
    full_generation_count = previous.full_generation_count
    evaluator_retry_count = previous.evaluator_retry_count

    if target_state is RecoveryState.RETRIEVING:
        retrieval_attempts = 1 if leaving_replan else retrieval_attempts + 1
        if retrieval_attempts > 3:
            raise PipelineControlError("retrieval_attempt_limit_exceeded")
    if target_state is RecoveryState.REPLAN_REQUESTED:
        replan_count += 1
        if replan_count > 2:
            raise PipelineControlError("planner_replan_limit_exceeded")
    if target_state is RecoveryState.PLAN_ADAPTING:
        adaptation_count += 1
        if adaptation_count > 2:
            raise PipelineControlError("plan_adaptation_limit_exceeded")
    if target_state is RecoveryState.FULL_GENERATION:
        full_generation_count += 1
        if full_generation_count > 1:
            raise PipelineControlError("full_generation_limit_exceeded")
    if previous.state is RecoveryState.EVALUATING and target_state is RecoveryState.EVALUATING:
        evaluator_retry_count += 1
        if evaluator_retry_count > 1:
            raise PipelineControlError("evaluator_retry_limit_exceeded")

    next_pool_sha = previous.candidate_pool_sha256
    if target_state is RecoveryState.CANDIDATE_POOL_FROZEN:
        if candidate_pool_sha256 is None:
            raise PipelineControlError("candidate_pool_freeze_requires_sha256")
        next_pool_sha = _require_sha256(
            candidate_pool_sha256,
            field_name="candidate_pool_sha256",
        )
    elif previous.candidate_pool_sha256 is not None:
        if candidate_pool_sha256 is not None and (
            _require_sha256(candidate_pool_sha256, field_name="candidate_pool_sha256")
            != previous.candidate_pool_sha256
        ):
            raise PipelineControlError("frozen_candidate_pool_cannot_change")
        next_pool_sha = previous.candidate_pool_sha256
    elif candidate_pool_sha256 is not None:
        raise PipelineControlError("candidate_pool_sha_only_allowed_at_freeze")

    verified = previous.artifact_verified if artifact_verified is None else artifact_verified
    if target_state is RecoveryState.ARTIFACT_COMMITTED and not verified:
        raise PipelineControlError("only_verified_artifact_can_be_committed")

    return RecoveryControlSnapshot(
        revision=next_revision,
        state=target_state,
        retrieval_attempts=retrieval_attempts,
        replan_count=replan_count,
        adaptation_count=adaptation_count,
        full_generation_count=full_generation_count,
        evaluator_retry_count=evaluator_retry_count,
        candidate_pool_sha256=next_pool_sha,
        artifact_verified=verified,
    )


def validate_snapshot_sequence(sequence: Sequence[RecoveryControlSnapshot]) -> None:
    """Reject snapshots spliced across unrelated subtasks or revisions."""

    if not sequence:
        raise PipelineControlError("recovery_snapshot_sequence_empty")
    subtask_id = sequence[0].revision.subtask_id
    for previous, current in zip(sequence, sequence[1:]):
        if current.revision.subtask_id != subtask_id:
            raise PipelineControlError("recovery_sequence_mixes_subtasks")
        expected = validate_recovery_transition(
            previous,
            current.state,
            revision=(current.revision if current.revision != previous.revision else None),
            candidate_pool_sha256=(
                current.candidate_pool_sha256
                if current.state is RecoveryState.CANDIDATE_POOL_FROZEN
                else None
            ),
            artifact_verified=current.artifact_verified,
        )
        if current != expected:
            raise PipelineControlError("recovery_sequence_snapshot_mismatch")


__all__ = [
    "PIPELINE_CONTROL_PROTOCOL",
    "CandidateOrigin",
    "CandidatePoolSnapshot",
    "CandidateResourceRef",
    "FailureResponsibility",
    "PerTypeConfidenceStatistics",
    "PipelineControlError",
    "PlannerReplanRequest",
    "RecoveryControlSnapshot",
    "RecoveryState",
    "RetrievalAttemptOutcome",
    "RetrievalAttemptRecord",
    "RetrievalConfidenceEvidence",
    "SubtaskRevisionRef",
    "canonical_json_bytes",
    "canonical_sha256",
    "initial_recovery_snapshot",
    "subtask_revision_identity_sha256",
    "validate_recovery_transition",
    "validate_snapshot_sequence",
]
