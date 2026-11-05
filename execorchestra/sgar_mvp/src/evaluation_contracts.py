"""Immutable contracts for contract-first evaluation and artifact publication.

This module owns identities and verdict invariants only.  It deliberately does
not import Planner, Router, E1 cases, Gold data, Validators, or concrete
execution adapters.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal, Mapping, cast

from pydantic import Field, field_validator, model_validator

from .pipeline_control import FrozenContract, SubtaskRevisionRef, canonical_sha256
from .path_policy import is_private_host_path_value


EVALUATOR_POLICY_PROTOCOL = "sgar-evaluator-policy-v2"
EVALUATOR_POLICY_EXPERIMENT_PROTOCOL = "sgar-evaluator-policy-v3"
EVALUATION_REFERENCE_PROTOCOL = "sgar-evaluation-reference-v1"
EVALUATION_INPUT_PROTOCOL = "sgar-evaluation-input-v1"
EVALUATION_DECISION_PROTOCOL = "sgar-evaluation-decision-v1"
EVALUATION_REVIEW_PROTOCOL = "sgar-evaluation-review-v1"
ARTIFACT_CANDIDATE_PROTOCOL = "sgar-artifact-candidate-v1"
ARTIFACT_LIFECYCLE_PROTOCOL = "sgar-artifact-lifecycle-v1"
ARTIFACT_MANIFEST_PROTOCOL = "sgar-artifact-manifest-v1"
ARTIFACT_COMMIT_PROTOCOL = "sgar-artifact-commit-v1"
CONTEXT_COMMIT_PROTOCOL = "sgar-context-commit-v1"
COMMITTED_CONTEXT_PROTOCOL = "sgar-committed-context-v1"
EVALUATION_EVENT_PROTOCOL = "sgar-evaluation-events-v1"
ARTIFACT_EVENT_PROTOCOL = "sgar-artifact-events-v1"
ARTIFACT_PROTOCOL_V2 = "sgar-artifact-v2"
ARTIFACT_EVIDENCE_PROTOCOL_V2 = "sgar-artifact-evidence-v2"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CANONICAL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
_SECRET_KEY = re.compile(
    r"(?i)^(?:api[_-]?key|authorization|password|secret|access[_-]?token|"
    r"refresh[_-]?token|bearer[_-]?token)$"
)
_AUTHORIZED_CONTENT_FIELDS = frozenset(
    {"public_content", "authorized_content", "original_public_objective"}
)


class EvaluationContractError(ValueError):
    pass


def require_sha256(value: str, *, field_name: str) -> str:
    normalized = str(value or "").strip().lower()
    if not _SHA256.fullmatch(normalized):
        raise ValueError(f"{field_name}_must_be_sha256_hex")
    return normalized


def _unsafe_locator(value: Any, locator: str = "$") -> str | None:
    if isinstance(value, Mapping):
        for key, item in cast(Mapping[Any, Any], value).items():
            if _SECRET_KEY.fullmatch(str(key)):
                return f"{locator}.{key}"
            # These fields are already authorized public/model-visible bytes.
            # Treating path-like text inside their contents as a private host
            # locator rejects legitimate artifacts and user inputs.
            if str(key) in _AUTHORIZED_CONTENT_FIELDS:
                continue
            found = _unsafe_locator(item, f"{locator}.{key}")
            if found:
                return found
        return None
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found = _unsafe_locator(item, f"{locator}[{index}]")
            if found:
                return found
        return None
    if isinstance(value, str) and (
        is_private_host_path_value(value)
    ):
        return locator
    return None


def assert_evaluation_projection_safe(value: Any) -> None:
    locator = _unsafe_locator(value)
    if locator:
        raise EvaluationContractError(f"evaluation_projection_unsafe:{locator}")


class CriterionSource(str, Enum):
    MACHINE_CONTRACT = "machine_contract"
    REQUIRED_CONTENT = "required_content"
    GROUNDING_REQUIREMENT = "grounding_requirement"
    ACCEPTANCE_CRITERION = "acceptance_criterion"
    EXPECTED_OUTPUT = "expected_output"
    DOWNSTREAM_CONTRACT = "downstream_contract"
    UNIVERSAL_CONSISTENCY = "universal_consistency"


class CriterionStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class EvaluationVerdict(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"


class ArtifactLifecycleState(str, Enum):
    PREPARED = "prepared"
    STAGED = "staged"
    EVALUATING = "evaluating"
    REVIEWING = "reviewing"
    VERIFIED = "verified"
    COMMITTED = "committed"
    QUARANTINED = "quarantined"
    TERMINAL = "terminal"


class ArtifactRepresentation(str, Enum):
    INLINE_TEXT = "inline_text"
    FILE = "file"
    DIRECTORY = "directory"
    BUNDLE = "bundle"


class ArtifactMemberDescriptorV2(FrozenContract):
    """One host-free member of a directory or multi-file artifact."""

    logical_locator: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    representation: Literal["file", "directory"]
    format_id: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    extension: str = ""
    content_sha256: str | None = None
    tree_sha256: str | None = None
    byte_size: int = Field(ge=0)
    required: bool = True
    member_sha256: str = ""

    @field_validator("content_sha256", "tree_sha256")
    @classmethod
    def _member_hashes(cls, value: str | None, info: Any) -> str | None:
        return None if value is None else require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _seal_member(self) -> "ArtifactMemberDescriptorV2":
        normalized = self.relative_path.replace("\\", "/")
        if (
            normalized.startswith("/")
            or normalized in {"", ".", ".."}
            or any(part in {"", ".", ".."} for part in normalized.split("/"))
            or re.match(r"^[A-Za-z]:", normalized)
        ):
            raise ValueError("artifact_member_relative_path_invalid")
        if self.representation == "file" and not self.content_sha256:
            raise ValueError("artifact_file_member_content_sha256_missing")
        if self.representation == "directory" and not self.tree_sha256:
            raise ValueError("artifact_directory_member_tree_sha256_missing")
        assert_evaluation_projection_safe(self.model_dump(mode="python"))
        expected = canonical_sha256(
            self.model_dump(mode="python", exclude={"member_sha256"})
        )
        if self.member_sha256 and require_sha256(
            self.member_sha256, field_name="member_sha256"
        ) != expected:
            raise ValueError("artifact_member_sha256_mismatch")
        object.__setattr__(self, "relative_path", normalized)
        object.__setattr__(self, "member_sha256", expected)
        return self


class ArtifactDescriptorV2(FrozenContract):
    """Open, representation-oriented artifact identity.

    The descriptor never contains a source host path.  Physical paths stay in
    the lifecycle store's private call frame and are replaced by logical
    locators plus content identities before persistence.
    """

    protocol: Literal[ARTIFACT_PROTOCOL_V2] = ARTIFACT_PROTOCOL_V2
    representation: ArtifactRepresentation
    format_id: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    extension: str = ""
    content_sha256: str | None = None
    tree_sha256: str | None = None
    bundle_sha256: str | None = None
    byte_size: int = Field(ge=0)
    logical_locator: str = Field(min_length=1)
    primary_member: str | None = None
    members: tuple[ArtifactMemberDescriptorV2, ...] = ()
    provenance_source_ids: tuple[str, ...]
    contract_status: Literal["pass", "fail", "unknown"]
    machine_check_ids: tuple[str, ...]
    semantic_evidence_status: Literal["available", "bounded", "unavailable"]
    descriptor_sha256: str = ""

    @field_validator("content_sha256", "tree_sha256", "bundle_sha256")
    @classmethod
    def _descriptor_hashes(cls, value: str | None, info: Any) -> str | None:
        return None if value is None else require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _seal_descriptor(self) -> "ArtifactDescriptorV2":
        if self.representation in {
            ArtifactRepresentation.INLINE_TEXT,
            ArtifactRepresentation.FILE,
        } and not self.content_sha256:
            raise ValueError("artifact_v2_content_sha256_missing")
        if self.representation is ArtifactRepresentation.DIRECTORY and not self.tree_sha256:
            raise ValueError("artifact_v2_tree_sha256_missing")
        if self.representation is ArtifactRepresentation.BUNDLE and not self.bundle_sha256:
            raise ValueError("artifact_v2_bundle_sha256_missing")
        member_paths = [item.relative_path for item in self.members]
        if len(member_paths) != len(set(member_paths)):
            raise ValueError("artifact_v2_duplicate_member_path")
        if self.primary_member and self.primary_member not in set(member_paths):
            raise ValueError("artifact_v2_primary_member_missing")
        if self.representation is ArtifactRepresentation.BUNDLE and not self.members:
            raise ValueError("artifact_v2_bundle_members_missing")
        assert_evaluation_projection_safe(self.model_dump(mode="python"))
        expected = canonical_sha256(
            self.model_dump(mode="python", exclude={"descriptor_sha256"})
        )
        if self.descriptor_sha256 and require_sha256(
            self.descriptor_sha256, field_name="descriptor_sha256"
        ) != expected:
            raise ValueError("artifact_v2_descriptor_sha256_mismatch")
        object.__setattr__(self, "descriptor_sha256", expected)
        return self


class FinalArtifactCandidateV2(FrozenContract):
    protocol: Literal[ARTIFACT_PROTOCOL_V2] = ARTIFACT_PROTOCOL_V2
    artifact_revision: "ArtifactRevisionRef"
    execution_result_sha256: str
    descriptor: ArtifactDescriptorV2
    output_contract_sha256: str
    candidate_pool_sha256: str
    plan_sha256: str | None = None
    recovery_operation_sha256: str | None = None
    execution_event_ids: tuple[str, ...] = ()
    source_handle_ids: tuple[str, ...] = ()
    candidate_sha256: str = ""

    @field_validator(
        "execution_result_sha256",
        "output_contract_sha256",
        "candidate_pool_sha256",
        "plan_sha256",
        "recovery_operation_sha256",
    )
    @classmethod
    def _candidate_hashes(cls, value: str | None, info: Any) -> str | None:
        return None if value is None else require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _seal_candidate(self) -> "FinalArtifactCandidateV2":
        if self.descriptor.contract_status != "pass":
            raise ValueError("artifact_v2_candidate_machine_contract_failed")
        assert_evaluation_projection_safe(self.model_dump(mode="python"))
        expected = canonical_sha256(
            self.model_dump(mode="python", exclude={"candidate_sha256"})
        )
        if self.candidate_sha256 and require_sha256(
            self.candidate_sha256, field_name="candidate_sha256"
        ) != expected:
            raise ValueError("artifact_v2_candidate_sha256_mismatch")
        object.__setattr__(self, "candidate_sha256", expected)
        return self


class EvaluatorPolicy(FrozenContract):
    protocol: Literal[
        EVALUATOR_POLICY_PROTOCOL,
        EVALUATOR_POLICY_EXPERIMENT_PROTOCOL,
    ] = EVALUATOR_POLICY_PROTOCOL
    model_resource_id: str = "model.gpt_5_6_sol.v1"
    max_initial_semantic_calls: Literal[1] = 1
    max_review_semantic_calls: Literal[1] = 1
    transport_retry_limit: Literal[2] = 2
    reasoning_effort: Literal["low", "medium", "high", "xhigh", "max"] | None = "high"
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    strict_schema: Literal[True] = True
    initial_evidence_max_bytes: Literal[262144] = 262144
    review_evidence_max_bytes: Literal[262144] = 262144
    max_output_tokens: Literal[8192] = 8192
    max_global_context_bytes: Literal[65536] = 65536
    max_critical_issues: Literal[3] = 3
    allow_model_failover: Literal[False] = False
    allow_soft_pass: Literal[False] = False
    hidden_validator_feedback: Literal[False] = False
    unknown_model: Literal["reject"] = "reject"
    policy_sha256: str = ""

    @field_validator("model_resource_id")
    @classmethod
    def _canonical_model_resource_id(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not re.fullmatch(r"model\.[A-Za-z0-9][A-Za-z0-9_.:-]*", normalized):
            raise ValueError("evaluator_model_resource_id_invalid")
        return normalized

    @model_validator(mode="after")
    def _seal(self) -> "EvaluatorPolicy":
        if self.reasoning_effort is not None and self.temperature is not None:
            raise ValueError("evaluator_reasoning_and_temperature_conflict")
        if self.protocol == EVALUATOR_POLICY_PROTOCOL and (
            self.model_resource_id != "model.gpt_5_6_sol.v1"
            or self.reasoning_effort != "high"
            or self.temperature is not None
        ):
            raise ValueError("evaluator_policy_v2_identity_invalid")
        expected = canonical_sha256(self.model_dump(mode="python", exclude={"policy_sha256"}))
        if self.policy_sha256 and require_sha256(
            self.policy_sha256, field_name="policy_sha256"
        ) != expected:
            raise ValueError("evaluator_policy_sha256_mismatch")
        object.__setattr__(self, "policy_sha256", expected)
        return self


class ArtifactRevisionRef(FrozenContract):
    protocol: Literal[ARTIFACT_LIFECYCLE_PROTOCOL] = ARTIFACT_LIFECYCLE_PROTOCOL
    run_id: str = Field(min_length=1)
    subtask_revision: SubtaskRevisionRef
    artifact_revision: int = Field(default=0, ge=0)
    revision_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "ArtifactRevisionRef":
        expected = canonical_sha256(self.model_dump(mode="python", exclude={"revision_sha256"}))
        if self.revision_sha256 and require_sha256(
            self.revision_sha256, field_name="revision_sha256"
        ) != expected:
            raise ValueError("artifact_revision_sha256_mismatch")
        object.__setattr__(self, "revision_sha256", expected)
        return self


class EvaluationCriterion(FrozenContract):
    criterion_id: str = Field(min_length=1)
    source: CriterionSource
    description: str = Field(min_length=1)
    required: bool = True
    source_locator: str = Field(min_length=1)
    criterion_sha256: str = ""

    @field_validator("criterion_id")
    @classmethod
    def _canonical_id(cls, value: str) -> str:
        normalized = str(value).strip()
        if not _CANONICAL_ID.fullmatch(normalized):
            raise ValueError("criterion_id_not_canonical")
        return normalized

    @model_validator(mode="after")
    def _seal(self) -> "EvaluationCriterion":
        assert_evaluation_projection_safe(self.model_dump(mode="python"))
        expected = canonical_sha256(self.model_dump(mode="python", exclude={"criterion_sha256"}))
        if self.criterion_sha256 and require_sha256(
            self.criterion_sha256, field_name="criterion_sha256"
        ) != expected:
            raise ValueError("criterion_sha256_mismatch")
        object.__setattr__(self, "criterion_sha256", expected)
        return self


class EvaluationReferenceStandard(FrozenContract):
    protocol: Literal[EVALUATION_REFERENCE_PROTOCOL] = EVALUATION_REFERENCE_PROTOCOL
    artifact_revision: ArtifactRevisionRef
    output_contract_sha256: str
    criteria: tuple[EvaluationCriterion, ...]
    reference_standard_sha256: str = ""

    @field_validator("output_contract_sha256")
    @classmethod
    def _hash(cls, value: str) -> str:
        return require_sha256(value, field_name="output_contract_sha256")

    @model_validator(mode="after")
    def _seal(self) -> "EvaluationReferenceStandard":
        ids = [item.criterion_id for item in self.criteria]
        if not ids:
            raise ValueError("evaluation_reference_requires_criteria")
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate_evaluation_criterion_id")
        expected = canonical_sha256(
            self.model_dump(mode="python", exclude={"reference_standard_sha256"})
        )
        if self.reference_standard_sha256 and require_sha256(
            self.reference_standard_sha256, field_name="reference_standard_sha256"
        ) != expected:
            raise ValueError("evaluation_reference_sha256_mismatch")
        object.__setattr__(self, "reference_standard_sha256", expected)
        return self


class MachineContractEvidence(FrozenContract):
    status: Literal["pass", "fail"]
    check_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    evidence_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "MachineContractEvidence":
        if not self.check_ids:
            raise ValueError("machine_contract_checks_required")
        expected = canonical_sha256(self.model_dump(mode="python", exclude={"evidence_sha256"}))
        if self.evidence_sha256 and require_sha256(
            self.evidence_sha256, field_name="evidence_sha256"
        ) != expected:
            raise ValueError("machine_contract_evidence_sha256_mismatch")
        object.__setattr__(self, "evidence_sha256", expected)
        return self


class FinalArtifactCandidate(FrozenContract):
    protocol: Literal[ARTIFACT_CANDIDATE_PROTOCOL] = ARTIFACT_CANDIDATE_PROTOCOL
    artifact_revision: ArtifactRevisionRef
    execution_result_sha256: str
    content_sha256: str
    byte_size: int = Field(ge=0)
    artifact_type: Literal["code", "json", "csv", "markdown", "plaintext"]
    extension: str
    mime_type: str = Field(min_length=1)
    logical_locator: str = Field(min_length=1)
    output_contract_sha256: str
    candidate_pool_sha256: str
    plan_sha256: str | None = None
    recovery_operation_sha256: str | None = None
    execution_event_ids: tuple[str, ...] = ()
    source_handle_ids: tuple[str, ...] = ()
    provenance_source_ids: tuple[str, ...]
    machine_contract_status: MachineContractEvidence
    candidate_sha256: str = ""

    @field_validator(
        "execution_result_sha256",
        "content_sha256",
        "output_contract_sha256",
        "candidate_pool_sha256",
        "plan_sha256",
        "recovery_operation_sha256",
    )
    @classmethod
    def _hashes(cls, value: str | None, info: Any) -> str | None:
        return None if value is None else require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _seal(self) -> "FinalArtifactCandidate":
        if self.machine_contract_status.status != "pass":
            raise ValueError("final_artifact_candidate_machine_contract_failed")
        assert_evaluation_projection_safe(self.model_dump(mode="python"))
        expected = canonical_sha256(self.model_dump(mode="python", exclude={"candidate_sha256"}))
        if self.candidate_sha256 and require_sha256(
            self.candidate_sha256, field_name="candidate_sha256"
        ) != expected:
            raise ValueError("artifact_candidate_sha256_mismatch")
        object.__setattr__(self, "candidate_sha256", expected)
        return self


class ArtifactTreeEntry(FrozenContract):
    relative_path: str = Field(min_length=1)
    content_sha256: str
    byte_size: int = Field(ge=0)

    @field_validator("content_sha256")
    @classmethod
    def _hash(cls, value: str) -> str:
        return require_sha256(value, field_name="content_sha256")


class StagedArtifactManifest(FrozenContract):
    protocol: Literal[ARTIFACT_MANIFEST_PROTOCOL] = ARTIFACT_MANIFEST_PROTOCOL
    artifact_revision: ArtifactRevisionRef
    candidate_sha256: str
    artifact_type: str = Field(min_length=1)
    content_sha256: str
    tree_sha256: str | None = None
    tree_entries: tuple[ArtifactTreeEntry, ...] = ()
    byte_size: int = Field(ge=0)
    mime_type: str = Field(min_length=1)
    extension: str
    logical_locator: str = Field(min_length=1)
    blob_locator: str = Field(min_length=1)
    output_contract_sha256: str
    execution_result_sha256: str
    candidate_pool_sha256: str
    plan_sha256: str | None = None
    recovery_operation_sha256: str | None = None
    source_handle_ids: tuple[str, ...] = ()
    provenance_source_ids: tuple[str, ...]
    execution_event_ids: tuple[str, ...] = ()
    accounting_operation_ids: tuple[str, ...] = ()
    machine_evidence_sha256: str
    artifact_v2: ArtifactDescriptorV2 | None = None
    visibility: Literal["staged"] = "staged"
    manifest_sha256: str = ""

    @field_validator(
        "candidate_sha256",
        "content_sha256",
        "tree_sha256",
        "output_contract_sha256",
        "execution_result_sha256",
        "candidate_pool_sha256",
        "plan_sha256",
        "recovery_operation_sha256",
        "machine_evidence_sha256",
    )
    @classmethod
    def _hashes(cls, value: str | None, info: Any) -> str | None:
        return None if value is None else require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _seal(self) -> "StagedArtifactManifest":
        if self.tree_entries and not self.tree_sha256:
            raise ValueError("directory_manifest_tree_sha256_missing")
        assert_evaluation_projection_safe(self.model_dump(mode="python"))
        expected = canonical_sha256(self.model_dump(mode="python", exclude={"manifest_sha256"}))
        if self.manifest_sha256 and require_sha256(
            self.manifest_sha256, field_name="manifest_sha256"
        ) != expected:
            raise ValueError("staged_manifest_sha256_mismatch")
        object.__setattr__(self, "manifest_sha256", expected)
        return self


class EvidenceReference(FrozenContract):
    evidence_id: str = Field(min_length=1)
    kind: Literal["full", "segment", "schema", "structure", "machine", "context"]
    content_sha256: str
    start_offset: int | None = Field(default=None, ge=0)
    end_offset: int | None = Field(default=None, ge=0)
    locator: str = Field(min_length=1)

    @field_validator("content_sha256")
    @classmethod
    def _hash(cls, value: str) -> str:
        return require_sha256(value, field_name="content_sha256")

    @model_validator(mode="after")
    def _offsets(self) -> "EvidenceReference":
        if (self.start_offset is None) != (self.end_offset is None):
            raise ValueError("evidence_offsets_must_be_paired")
        if self.start_offset is not None and self.end_offset < self.start_offset:
            raise ValueError("evidence_offset_order_invalid")
        return self


class ArtifactEvidenceBundle(FrozenContract):
    protocol: Literal[EVALUATION_INPUT_PROTOCOL] = EVALUATION_INPUT_PROTOCOL
    artifact_manifest_sha256: str
    reference_standard_sha256: str
    review_index: Literal[0, 1]
    coverage_status: Literal["complete", "bounded"]
    total_byte_size: int = Field(ge=0)
    included_byte_size: int = Field(ge=0)
    evidence: tuple[EvidenceReference, ...]
    criterion_evidence: dict[str, tuple[str, ...]]
    public_content: str
    evidence_content: dict[str, str] = Field(default_factory=dict)
    evidence_bundle_sha256: str = ""

    @field_validator("artifact_manifest_sha256", "reference_standard_sha256")
    @classmethod
    def _hashes(cls, value: str, info: Any) -> str:
        return require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _seal(self) -> "ArtifactEvidenceBundle":
        if self.included_byte_size > self.total_byte_size:
            raise ValueError("evidence_included_bytes_exceed_total")
        if self.coverage_status == "complete" and self.included_byte_size != self.total_byte_size:
            raise ValueError("complete_evidence_size_mismatch")
        evidence_ids = {item.evidence_id for item in self.evidence}
        if len(evidence_ids) != len(self.evidence):
            raise ValueError("duplicate_evidence_id")
        for refs in self.criterion_evidence.values():
            if any(item not in evidence_ids for item in refs):
                raise ValueError("criterion_evidence_unknown_reference")
        if any(item not in evidence_ids for item in self.evidence_content):
            raise ValueError("evidence_content_unknown_reference")
        evidence_by_id = {item.evidence_id: item for item in self.evidence}
        for evidence_id, content in self.evidence_content.items():
            if canonical_sha256(content) == evidence_by_id[evidence_id].content_sha256:
                continue
            import hashlib

            if hashlib.sha256(content.encode("utf-8")).hexdigest() != (
                evidence_by_id[evidence_id].content_sha256
            ):
                raise ValueError("evidence_content_sha256_mismatch")
        assert_evaluation_projection_safe(self.model_dump(mode="python"))
        expected = canonical_sha256(
            self.model_dump(mode="python", exclude={"evidence_bundle_sha256"})
        )
        if self.evidence_bundle_sha256 and require_sha256(
            self.evidence_bundle_sha256, field_name="evidence_bundle_sha256"
        ) != expected:
            raise ValueError("evidence_bundle_sha256_mismatch")
        object.__setattr__(self, "evidence_bundle_sha256", expected)
        return self


class CriterionResult(FrozenContract):
    criterion_id: str
    status: CriterionStatus
    evidence_ids: tuple[str, ...] = ()
    concise_reason: str = ""


class EvaluationDimensionScores(FrozenContract):
    factual_consistency: float | None = Field(default=None, ge=0.0, le=1.0)
    internal_consistency: float | None = Field(default=None, ge=0.0, le=1.0)
    requirement_completeness: float | None = Field(default=None, ge=0.0, le=1.0)
    dependency_grounding: float | None = Field(default=None, ge=0.0, le=1.0)
    downstream_consumability: float | None = Field(default=None, ge=0.0, le=1.0)


class EvaluationDecision(FrozenContract):
    protocol: Literal[EVALUATION_DECISION_PROTOCOL] = EVALUATION_DECISION_PROTOCOL
    verdict: EvaluationVerdict
    failure_code: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    criterion_results: tuple[CriterionResult, ...]
    dimension_scores: EvaluationDimensionScores = Field(default_factory=EvaluationDimensionScores)
    critical_issues: tuple[str, ...] = ()
    training_label: Literal[
        "good_case", "repairable_case", "hard_case", "evaluator_noise"
    ]
    reference_standard_sha256: str
    evidence_bundle_sha256: str
    artifact_manifest_sha256: str
    context_snapshot_sha256: str
    evaluator_model_resource_id: str
    evaluator_api_model_id: str
    accounting_operation_id: str | None = None
    request_sha256: str
    response_sha256: str
    review_index: Literal[0, 1] = 0
    decision_sha256: str = ""

    @field_validator(
        "reference_standard_sha256",
        "evidence_bundle_sha256",
        "artifact_manifest_sha256",
        "context_snapshot_sha256",
        "request_sha256",
        "response_sha256",
    )
    @classmethod
    def _hashes(cls, value: str, info: Any) -> str:
        return require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _seal(self) -> "EvaluationDecision":
        ids = [item.criterion_id for item in self.criterion_results]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate_criterion_result")
        failed = [item for item in self.criterion_results if item.status is CriterionStatus.FAIL]
        if self.verdict is EvaluationVerdict.FAIL:
            if not failed or any(not item.evidence_ids for item in failed):
                raise ValueError("evaluation_fail_requires_evidence_backed_failure")
        if self.verdict is not EvaluationVerdict.FAIL and self.failure_code == "artifact_quality_failure":
            raise ValueError("artifact_quality_failure_requires_fail_verdict")
        assert_evaluation_projection_safe(self.model_dump(mode="python"))
        expected = canonical_sha256(self.model_dump(mode="python", exclude={"decision_sha256"}))
        if self.decision_sha256 and require_sha256(
            self.decision_sha256, field_name="decision_sha256"
        ) != expected:
            raise ValueError("evaluation_decision_sha256_mismatch")
        object.__setattr__(self, "decision_sha256", expected)
        return self


def validate_evaluation_decision(
    *,
    decision: EvaluationDecision,
    standard: EvaluationReferenceStandard,
    bundle: ArtifactEvidenceBundle,
) -> EvaluationDecision:
    if decision.reference_standard_sha256 != standard.reference_standard_sha256:
        raise EvaluationContractError("evaluation_reference_identity_mismatch")
    if decision.evidence_bundle_sha256 != bundle.evidence_bundle_sha256:
        raise EvaluationContractError("evaluation_evidence_identity_mismatch")
    required = {item.criterion_id for item in standard.criteria if item.required}
    result_by_id = {item.criterion_id: item for item in decision.criterion_results}
    if set(result_by_id) != {item.criterion_id for item in standard.criteria}:
        raise EvaluationContractError("evaluation_criterion_result_set_mismatch")
    evidence_ids = {item.evidence_id for item in bundle.evidence}
    for result in decision.criterion_results:
        if any(item not in evidence_ids for item in result.evidence_ids):
            raise EvaluationContractError("evaluation_decision_unknown_evidence")
        allowed_evidence = set(bundle.criterion_evidence.get(result.criterion_id, ()))
        if any(item not in allowed_evidence for item in result.evidence_ids):
            raise EvaluationContractError("evaluation_decision_cross_criterion_evidence")
    for criterion in standard.criteria:
        if criterion.source is CriterionSource.MACHINE_CONTRACT:
            machine_result = result_by_id[criterion.criterion_id]
            if machine_result.status is not CriterionStatus.PASS or not machine_result.evidence_ids:
                raise EvaluationContractError("evaluation_machine_contract_contradiction")
    required_results = [result_by_id[item] for item in required]
    has_failure = any(item.status is CriterionStatus.FAIL for item in required_results)
    has_unknown = any(
        item.status in {CriterionStatus.UNKNOWN, CriterionStatus.NOT_APPLICABLE}
        for item in required_results
    )
    if decision.verdict is EvaluationVerdict.PASS and (
        has_failure or has_unknown or bundle.coverage_status != "complete"
    ):
        raise EvaluationContractError("evaluation_pass_not_fully_supported")
    if decision.verdict is EvaluationVerdict.FAIL and not any(
        item.status is CriterionStatus.FAIL and item.evidence_ids for item in required_results
    ):
        raise EvaluationContractError("evaluation_fail_without_required_evidence")
    if decision.verdict is EvaluationVerdict.INCONCLUSIVE and not (
        has_unknown or bundle.coverage_status == "bounded"
    ):
        raise EvaluationContractError("evaluation_inconclusive_without_uncertainty")
    return decision


class EvaluationReviewRef(FrozenContract):
    protocol: Literal[EVALUATION_REVIEW_PROTOCOL] = EVALUATION_REVIEW_PROTOCOL
    initial_decision_sha256: str
    artifact_manifest_sha256: str
    reference_standard_sha256: str
    context_snapshot_sha256: str
    review_index: Literal[1] = 1
    review_sha256: str = ""

    @field_validator(
        "initial_decision_sha256",
        "artifact_manifest_sha256",
        "reference_standard_sha256",
        "context_snapshot_sha256",
    )
    @classmethod
    def _hashes(cls, value: str, info: Any) -> str:
        return require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _seal(self) -> "EvaluationReviewRef":
        expected = canonical_sha256(self.model_dump(mode="python", exclude={"review_sha256"}))
        if self.review_sha256 and require_sha256(
            self.review_sha256, field_name="review_sha256"
        ) != expected:
            raise ValueError("evaluation_review_sha256_mismatch")
        object.__setattr__(self, "review_sha256", expected)
        return self


class VerifiedArtifactManifest(FrozenContract):
    protocol: Literal[ARTIFACT_MANIFEST_PROTOCOL] = ARTIFACT_MANIFEST_PROTOCOL
    artifact_revision: ArtifactRevisionRef
    staged_manifest_sha256: str
    evaluation_decision_sha256: str
    machine_evidence_sha256: str
    verified_content_sha256: str
    visibility_scope: Literal["run_committed_context"] = "run_committed_context"
    verification_event_id: str
    verified_manifest_sha256: str = ""

    @field_validator(
        "staged_manifest_sha256",
        "evaluation_decision_sha256",
        "machine_evidence_sha256",
        "verified_content_sha256",
    )
    @classmethod
    def _hashes(cls, value: str, info: Any) -> str:
        return require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _seal(self) -> "VerifiedArtifactManifest":
        expected = canonical_sha256(
            self.model_dump(mode="python", exclude={"verified_manifest_sha256"})
        )
        if self.verified_manifest_sha256 and require_sha256(
            self.verified_manifest_sha256, field_name="verified_manifest_sha256"
        ) != expected:
            raise ValueError("verified_manifest_sha256_mismatch")
        object.__setattr__(self, "verified_manifest_sha256", expected)
        return self


class QuarantinedArtifactManifest(FrozenContract):
    protocol: Literal[ARTIFACT_MANIFEST_PROTOCOL] = ARTIFACT_MANIFEST_PROTOCOL
    artifact_revision: ArtifactRevisionRef
    staged_manifest_sha256: str
    final_decision_sha256: str | None = None
    reason_code: Literal[
        "artifact_quality_failure",
        "evaluation_inconclusive",
        "evaluation_protocol_inconclusive",
        "evaluation_infrastructure_failure",
        "evaluation_framework_failure",
        "evaluation_budget_failure",
        "evaluation_interrupted",
    ]
    visibility: Literal["quarantined"] = "quarantined"
    quarantine_sha256: str = ""

    @field_validator("staged_manifest_sha256", "final_decision_sha256")
    @classmethod
    def _hashes(cls, value: str | None, info: Any) -> str | None:
        return None if value is None else require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _seal(self) -> "QuarantinedArtifactManifest":
        expected = canonical_sha256(self.model_dump(mode="python", exclude={"quarantine_sha256"}))
        if self.quarantine_sha256 and require_sha256(
            self.quarantine_sha256, field_name="quarantine_sha256"
        ) != expected:
            raise ValueError("quarantine_sha256_mismatch")
        object.__setattr__(self, "quarantine_sha256", expected)
        return self


class CommittedArtifactManifest(FrozenContract):
    protocol: Literal[ARTIFACT_COMMIT_PROTOCOL] = ARTIFACT_COMMIT_PROTOCOL
    artifact_revision: ArtifactRevisionRef
    staged_manifest_sha256: str
    verified_manifest_sha256: str
    evaluation_decision_sha256: str
    content_sha256: str
    blob_locator: str
    logical_locator: str
    artifact_type: str
    extension: str
    mime_type: str
    byte_size: int = Field(ge=0)
    output_contract_sha256: str
    candidate_pool_sha256: str
    plan_sha256: str | None = None
    recovery_operation_sha256: str | None = None
    source_handle_ids: tuple[str, ...] = ()
    provenance_source_ids: tuple[str, ...]
    execution_event_ids: tuple[str, ...] = ()
    accounting_operation_ids: tuple[str, ...] = ()
    artifact_v2: ArtifactDescriptorV2 | None = None
    visibility: Literal["committed"] = "committed"
    commit_event_id: str
    committed_manifest_sha256: str = ""

    @field_validator(
        "staged_manifest_sha256",
        "verified_manifest_sha256",
        "evaluation_decision_sha256",
        "content_sha256",
        "output_contract_sha256",
        "candidate_pool_sha256",
        "plan_sha256",
        "recovery_operation_sha256",
    )
    @classmethod
    def _hashes(cls, value: str | None, info: Any) -> str | None:
        return None if value is None else require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _seal(self) -> "CommittedArtifactManifest":
        assert_evaluation_projection_safe(self.model_dump(mode="python"))
        expected = canonical_sha256(
            self.model_dump(mode="python", exclude={"committed_manifest_sha256"})
        )
        if self.committed_manifest_sha256 and require_sha256(
            self.committed_manifest_sha256, field_name="committed_manifest_sha256"
        ) != expected:
            raise ValueError("committed_manifest_sha256_mismatch")
        object.__setattr__(self, "committed_manifest_sha256", expected)
        return self


class EvaluationContextSnapshot(FrozenContract):
    protocol: Literal[COMMITTED_CONTEXT_PROTOCOL] = COMMITTED_CONTEXT_PROTOCOL
    current_revision: SubtaskRevisionRef
    original_public_objective: str
    original_public_objective_sha256: str
    current_contract: dict[str, Any]
    macro_delivery_standard: dict[str, Any] = Field(default_factory=dict)
    document_validation: dict[str, Any] = Field(default_factory=dict)
    dag_contract_descriptors: tuple[dict[str, Any], ...]
    downstream_consumer_descriptors: tuple[dict[str, Any], ...]
    dependency_committed_manifest_sha256s: tuple[str, ...]
    dependency_artifact_descriptors: tuple[dict[str, Any], ...] = ()
    source_evidence: tuple["EvaluationSourceEvidence", ...] = ()
    staged_artifact_manifest_sha256: str
    plan_sha256: str | None = None
    recovery_operation_sha256: str | None = None
    provenance_source_ids: tuple[str, ...]
    context_snapshot_sha256: str = ""

    @field_validator(
        "original_public_objective_sha256",
        "staged_artifact_manifest_sha256",
        "plan_sha256",
        "recovery_operation_sha256",
    )
    @classmethod
    def _hashes(cls, value: str | None, info: Any) -> str | None:
        return None if value is None else require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _seal(self) -> "EvaluationContextSnapshot":
        if canonical_sha256(self.original_public_objective) != self.original_public_objective_sha256:
            raise ValueError("evaluation_public_objective_sha256_mismatch")
        for item in self.dependency_committed_manifest_sha256s:
            require_sha256(item, field_name="dependency_committed_manifest_sha256")
        source_ids = [item.source_id for item in self.source_evidence]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("evaluation_source_evidence_duplicate")
        assert_evaluation_projection_safe(self.model_dump(mode="python"))
        expected = canonical_sha256(
            self.model_dump(mode="python", exclude={"context_snapshot_sha256"})
        )
        if self.context_snapshot_sha256 and require_sha256(
            self.context_snapshot_sha256, field_name="context_snapshot_sha256"
        ) != expected:
            raise ValueError("evaluation_context_sha256_mismatch")
        object.__setattr__(self, "context_snapshot_sha256", expected)
        return self


class EvaluationSourceEvidence(FrozenContract):
    """Bounded exact evidence from an authorized Public Input or dependency."""

    source_id: str = Field(min_length=1)
    origin: Literal["public_input", "committed_dependency", "checkpoint"]
    logical_name: str = Field(min_length=1)
    logical_locator: str = Field(min_length=1)
    representation: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    content_sha256: str | None = None
    descriptor_sha256: str
    coverage_status: Literal["complete", "bounded", "machine_only"]
    byte_size: int = Field(ge=0)
    public_content: str = ""
    public_content_sha256: str = ""
    structure_evidence: dict[str, Any] = Field(default_factory=dict)
    source_evidence_sha256: str = ""

    @field_validator("content_sha256", "descriptor_sha256")
    @classmethod
    def _source_hashes(cls, value: str | None, info: Any) -> str | None:
        return None if value is None else require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _seal_source(self) -> "EvaluationSourceEvidence":
        import hashlib

        observed = hashlib.sha256(self.public_content.encode("utf-8")).hexdigest()
        if self.public_content_sha256 and self.public_content_sha256 != observed:
            raise ValueError("evaluation_source_content_sha256_mismatch")
        object.__setattr__(self, "public_content_sha256", observed)
        projection = self.model_dump(
            mode="python", exclude={"source_evidence_sha256"}
        )
        expected = canonical_sha256(projection)
        if self.source_evidence_sha256 and self.source_evidence_sha256 != expected:
            raise ValueError("evaluation_source_evidence_sha256_mismatch")
        object.__setattr__(self, "source_evidence_sha256", expected)
        return self


EvaluationContextSnapshot.model_rebuild()


class CommittedContextSnapshot(FrozenContract):
    protocol: Literal[COMMITTED_CONTEXT_PROTOCOL] = COMMITTED_CONTEXT_PROTOCOL
    consumer_revision: SubtaskRevisionRef
    declared_dependency_refs: tuple[str, ...]
    committed_artifacts: tuple[CommittedArtifactManifest, ...]
    exact_content_available: Literal[True] = True
    derived_summary_available: bool = False
    snapshot_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "CommittedContextSnapshot":
        allowed = set(self.declared_dependency_refs)
        actual = {
            item.artifact_revision.subtask_revision.subtask_id
            for item in self.committed_artifacts
        }
        if not actual.issubset(allowed):
            raise ValueError("committed_context_contains_undeclared_dependency")
        run_ids = {item.artifact_revision.run_id for item in self.committed_artifacts}
        if len(run_ids) > 1:
            raise ValueError("committed_context_cross_run")
        expected = canonical_sha256(self.model_dump(mode="python", exclude={"snapshot_sha256"}))
        if self.snapshot_sha256 and require_sha256(
            self.snapshot_sha256, field_name="snapshot_sha256"
        ) != expected:
            raise ValueError("committed_context_sha256_mismatch")
        object.__setattr__(self, "snapshot_sha256", expected)
        return self


__all__ = [
    "ARTIFACT_EVIDENCE_PROTOCOL_V2",
    "ARTIFACT_PROTOCOL_V2",
    "ARTIFACT_CANDIDATE_PROTOCOL",
    "ARTIFACT_COMMIT_PROTOCOL",
    "ARTIFACT_EVENT_PROTOCOL",
    "ARTIFACT_LIFECYCLE_PROTOCOL",
    "ARTIFACT_MANIFEST_PROTOCOL",
    "COMMITTED_CONTEXT_PROTOCOL",
    "CONTEXT_COMMIT_PROTOCOL",
    "EVALUATION_DECISION_PROTOCOL",
    "EVALUATION_EVENT_PROTOCOL",
    "EVALUATION_INPUT_PROTOCOL",
    "EVALUATION_REFERENCE_PROTOCOL",
    "EVALUATION_REVIEW_PROTOCOL",
    "EVALUATOR_POLICY_EXPERIMENT_PROTOCOL",
    "EVALUATOR_POLICY_PROTOCOL",
    "ArtifactEvidenceBundle",
    "ArtifactDescriptorV2",
    "ArtifactLifecycleState",
    "ArtifactMemberDescriptorV2",
    "ArtifactRepresentation",
    "ArtifactRevisionRef",
    "ArtifactTreeEntry",
    "CommittedArtifactManifest",
    "CommittedContextSnapshot",
    "CriterionResult",
    "CriterionSource",
    "CriterionStatus",
    "EvaluationContextSnapshot",
    "EvaluationSourceEvidence",
    "EvaluationContractError",
    "EvaluationCriterion",
    "EvaluationDecision",
    "EvaluationDimensionScores",
    "EvaluationReferenceStandard",
    "EvaluationReviewRef",
    "EvaluationVerdict",
    "EvaluatorPolicy",
    "EvidenceReference",
    "FinalArtifactCandidate",
    "FinalArtifactCandidateV2",
    "MachineContractEvidence",
    "QuarantinedArtifactManifest",
    "StagedArtifactManifest",
    "VerifiedArtifactManifest",
    "assert_evaluation_projection_safe",
    "require_sha256",
    "validate_evaluation_decision",
]
