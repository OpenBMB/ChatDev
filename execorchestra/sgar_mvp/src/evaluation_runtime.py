"""Evidence-bound evaluator with one optional review and append-only events."""

from __future__ import annotations

from . import terminal_progress

import asyncio
import hashlib
import json
import os
import threading
import uuid
from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Sequence

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from .atomic_io import bounded_path_component, temporary_sibling_path
from .evaluation_contracts import (
    EVALUATION_EVENT_PROTOCOL,
    ArtifactEvidenceBundle,
    CriterionResult,
    CriterionSource,
    CriterionStatus,
    EvaluationContextSnapshot,
    EvaluationDecision,
    EvaluationDimensionScores,
    EvaluationReferenceStandard,
    EvaluationReviewRef,
    EvaluationVerdict,
    EvaluatorPolicy,
    EvidenceReference,
    StagedArtifactManifest,
    assert_evaluation_projection_safe,
    validate_evaluation_decision,
)
from .artifact_v2 import build_evidence_v2
from .model_accounting import (
    BudgetControlError,
    ModelCallContext,
    ModelPricingCatalog,
    RunCostLedger,
)
from .model_transport import (
    AsyncModelTransportPort,
    classify_transport_exception,
    model_request_sha256,
    require_async_model_transport,
)
from .model_response_contracts import (
    StructuredResponseModeInput,
    build_structured_role_contract,
    normalize_structured_response_mode,
    structured_role_prompt_projection,
    system_role_requirement,
    system_role_response_format,
    validate_structured_response_content,
)
from .pipeline_control import canonical_json_bytes, canonical_sha256
from .internal_language import prompt_file_text
from .terminal_failure import TerminalFailureEnvelope


EVALUATOR_PROMPT_VERSION = "task-first-evaluator-en-v12-result-semantics"
EVALUATOR_MAX_TRANSPORT_ATTEMPTS = 3
EvaluationMode = Literal["off", "silent", "active"]


def normalize_evaluation_mode(value: Any = None) -> EvaluationMode:
    mode = str(value or "off").strip().lower()
    if mode not in {"off", "silent", "active"}:
        raise EvaluationRuntimeError("evaluation_mode_invalid")
    return mode  # type: ignore[return-value]

# Shared with the file prompt by a regression assertion; not an acceptance postprocessor.
BOUND_SCHEMA_EVALUATION_INSTRUCTIONS = "BOUND SCHEMA CHECKS: framework_publication_facts.bound_schema_checks reports deterministic validation of the exact current output against documents explicitly bound to the selected final step. A pass proves conformance to that specific schema within the stated local coverage; use this fact rather than reinterpreting the same schema as a conflicting structural requirement. It does not prove business correctness, that the schema itself meets the original task, or compliance with another document. Unknown is not pass or invalidity. JSON Schema at a schema position uses true to allow any value and false to reject every value; these are not const constraints. An actual constant is expressed using const or enum inside a schema object. A Schema document's own output contract describes the document, not the business instance. Continue checking every assigned content, factual and task requirement; do not turn a structural pass into an overall pass."

STAGED_DELIVERY_EVALUATION_INSTRUCTIONS = (
    "framework_publication_facts is read-only context for staged, pre-export node evaluation. "
    "Keep every required criterion, including mixed content, encoding and naming requirements. "
    "Evaluate actual content and listed byte checks, plus the final target binding against the "
    "original requirements. Only the framework's deterministic top-level copy/naming occurs after "
    "acceptance and commit; do not require that future export to have already happened. A pass "
    "means candidate content conforms, the applicable target binding is correct, and formal "
    "export remains pending; it never means physical delivery is complete. This does not defer "
    "names inside content, required directory members, code references, current-node side effects "
    "or remote writes. Conflicting bindings or incorrect content can fail; missing necessary "
    "binding or encoding evidence remains unknown. For a declared intermediate node, "
    "final_target=null is expected: judge the current node and downstream input interface "
    "using the staged descriptor, including its declared extension. Do not require a final "
    "export target for that node. Its own explicit content, member and naming obligations "
    "still apply. Never infer encoding from a suffix, media "
    "type or displayed text, or interpret tree checks as member encoding checks. Machine checks "
    "do not establish business correctness. Preserve intermediate/final scope: evaluate only "
    "assigned work, without shifting current obligations to downstream nodes. Do not delete or "
    "split criteria by keywords, mark a required criterion not_applicable, or convert unknown to pass."
)


class EvaluationRuntimeError(RuntimeError):
    pass


class EvaluationPersistenceError(EvaluationRuntimeError):
    pass


def load_evaluator_policy(path: str | Path) -> EvaluatorPolicy:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvaluationRuntimeError("evaluator_policy_unreadable") from exc
    if not isinstance(payload, Mapping):
        raise EvaluationRuntimeError("evaluator_policy_root_not_mapping")
    try:
        return EvaluatorPolicy.model_validate(payload)
    except Exception as exc:
        raise EvaluationRuntimeError("evaluator_policy_invalid") from exc


class ResolvedEvaluatorModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    resource_id: str
    api_model_id: str
    manifest_sha256: str
    pricing_catalog_sha256: str
    response_mode: StructuredResponseModeInput
    policy_sha256: str
    identity_sha256: str

def resolve_evaluator_model(
    *,
    policy: EvaluatorPolicy,
    pricing_catalog: ModelPricingCatalog,
    manifest: Mapping[str, Any],
    availability_status: str,
    response_mode: StructuredResponseModeInput,
) -> ResolvedEvaluatorModel:
    if str(manifest.get("resource_id") or "") != policy.model_resource_id:
        raise EvaluationRuntimeError("evaluator_manifest_identity_mismatch")
    if str(manifest.get("resource_type") or "") != "Model":
        raise EvaluationRuntimeError("evaluator_resource_not_model")
    if str(availability_status or "unknown").strip().lower() == "unavailable":
        raise EvaluationRuntimeError("evaluator_model_unavailable")
    execution = manifest.get("execution")
    if not isinstance(execution, Mapping):
        raise EvaluationRuntimeError("evaluator_execution_missing")
    api_model_id = str(execution.get("model_id") or "").strip()
    if not api_model_id:
        raise EvaluationRuntimeError("evaluator_api_model_id_missing")
    price = pricing_catalog.resolve(
        resource_id=policy.model_resource_id,
        api_model_id=api_model_id,
    )
    if price.resource_id != policy.model_resource_id or price.api_model_id != api_model_id:
        raise EvaluationRuntimeError("evaluator_pricing_identity_mismatch")
    projection = {
        "resource_id": policy.model_resource_id,
        "api_model_id": api_model_id,
        "manifest_sha256": canonical_sha256(dict(manifest)),
        "pricing_catalog_sha256": pricing_catalog.pricing_catalog_sha256,
        "response_mode": normalize_structured_response_mode(response_mode),
        "policy_sha256": policy.policy_sha256,
    }
    return ResolvedEvaluatorModel(**projection, identity_sha256=canonical_sha256(projection))


class EvaluationEventLedger:
    """Thread-safe ledger. A failed started event prevents model dispatch."""

    def __init__(self, *, output_dir: str | Path, run_id: str) -> None:
        self.output_dir = Path(output_dir).resolve()
        self.run_id = str(run_id).strip()
        if not self.run_id:
            raise EvaluationPersistenceError("evaluation_run_id_empty")
        self.evaluation_dir = self.output_dir / "evaluation"
        self.events_path = self.evaluation_dir / "evaluation_events.jsonl"
        self.summary_path = self.evaluation_dir / "evaluation_summary.json"
        self._events: list[dict[str, Any]] = []
        self._lock = threading.RLock()
        self._closed = False
        try:
            self.evaluation_dir.mkdir(parents=True, exist_ok=True)
            if self.events_path.exists() and self.events_path.stat().st_size:
                raise EvaluationPersistenceError("evaluation_ledger_already_exists")
            self.write_summary()
        except EvaluationPersistenceError:
            raise
        except OSError as exc:
            raise EvaluationPersistenceError("evaluation_ledger_initialization_failed") from exc

    def append_event(self, event_type: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        event = {
            "schema_version": EVALUATION_EVENT_PROTOCOL,
            "event_type": str(event_type),
            "event_id": uuid.uuid4().hex,
            "run_id": self.run_id,
            **dict(payload),
        }
        assert_evaluation_projection_safe(event)
        serialized = canonical_json_bytes(event).decode("utf-8")
        with self._lock:
            if self._closed:
                raise EvaluationPersistenceError("evaluation_ledger_closed")
            try:
                with self.events_path.open("a", encoding="utf-8", newline="\n") as handle:
                    handle.write(serialized + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
            except OSError as exc:
                raise EvaluationPersistenceError("evaluation_event_write_failed") from exc
            self._events.append(event)
            self.write_summary()
        terminal_progress.observe_evaluation(event)
        return dict(event)

    def write_artifact(self, name: str, payload: Mapping[str, Any]) -> Path:
        path = self.evaluation_dir / name
        serialized = canonical_json_bytes(payload)
        with self._lock:
            if path.exists():
                existing = path.read_bytes()
                if existing == serialized:
                    return path
                raise EvaluationPersistenceError("evaluation_artifact_hash_conflict")
            temporary = temporary_sibling_path(path)
            try:
                with temporary.open("xb") as handle:
                    handle.write(serialized)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, path)
            except OSError as exc:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
                raise EvaluationPersistenceError("evaluation_artifact_write_failed") from exc
        return path

    def summary(self) -> dict[str, Any]:
        with self._lock:
            counts: dict[str, int] = {}
            started: set[str] = set()
            terminal: set[str] = set()
            for event in self._events:
                event_type = str(event.get("event_type") or "")
                counts[event_type] = counts.get(event_type, 0) + 1
                operation_id = str(event.get("evaluation_operation_id") or "")
                if event_type in {"evaluation_started", "evaluation_review_started"} and operation_id:
                    started.add(operation_id)
                if event_type in {
                    "evaluation_finished",
                    "evaluation_review_finished",
                    "evaluation_interrupted",
                } and operation_id:
                    terminal.add(operation_id)
            return {
                "schema_version": EVALUATION_EVENT_PROTOCOL,
                "run_id": self.run_id,
                "event_count": len(self._events),
                "event_counts": counts,
                "unmatched_operations": sorted(started - terminal),
                "complete": not (started - terminal),
                "ledger_sha256": canonical_sha256(self._events),
            }

    def write_summary(self) -> dict[str, Any]:
        payload = self.summary()
        temporary = temporary_sibling_path(self.summary_path)
        try:
            with temporary.open("wb") as handle:
                handle.write(canonical_json_bytes(payload))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.summary_path)
        except OSError as exc:
            raise EvaluationPersistenceError("evaluation_summary_write_failed") from exc
        return payload

    def close(self) -> dict[str, Any]:
        with self._lock:
            pending: dict[str, dict[str, Any]] = {}
            terminal: set[str] = set()
            for event in self._events:
                operation_id = str(event.get("evaluation_operation_id") or "")
                if not operation_id:
                    continue
                if event.get("event_type") in {
                    "evaluation_started",
                    "evaluation_review_started",
                }:
                    pending[operation_id] = event
                elif event.get("event_type") in {
                    "evaluation_finished",
                    "evaluation_review_finished",
                    "evaluation_interrupted",
                }:
                    terminal.add(operation_id)
            for operation_id in sorted(set(pending) - terminal):
                event = pending[operation_id]
                self.append_event(
                    "evaluation_interrupted",
                    {
                        "evaluation_operation_id": operation_id,
                        "review_index": int(event.get("review_index") or 0),
                        "request_sha256": event.get("request_sha256"),
                        "failure_code": "evaluation_normal_shutdown_interrupted",
                    },
                )
            summary = self.write_summary()
            self._closed = True
            return summary


def _decode_public_text(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EvaluationRuntimeError("artifact_evidence_not_utf8") from exc


def _attach_fact_evidence(
    *, bundle: ArtifactEvidenceBundle, standard: EvaluationReferenceStandard,
    evidence_id: str, kind: Literal["structure", "context"],
    facts: Mapping[str, Any], locator: str,
) -> ArtifactEvidenceBundle:
    """Add one referencable fact snapshot without changing body coverage or criteria."""
    text = canonical_json_bytes(dict(facts)).decode("utf-8")
    reference = EvidenceReference(
        evidence_id=evidence_id, kind=kind,
        content_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(), locator=locator,
    )
    references = {item.evidence_id: item for item in bundle.evidence}
    if evidence_id in references:
        if references[evidence_id] != reference or bundle.evidence_content.get(evidence_id) != text:
            raise EvaluationRuntimeError("evaluation_fact_evidence_conflict")
        return bundle
    criterion_evidence = dict(bundle.criterion_evidence)
    for criterion in standard.criteria:
        if criterion.source is not CriterionSource.MACHINE_CONTRACT:
            criterion_evidence[criterion.criterion_id] = tuple(dict.fromkeys(
                (*criterion_evidence.get(criterion.criterion_id, ()), evidence_id)
            ))
    return ArtifactEvidenceBundle(
        artifact_manifest_sha256=bundle.artifact_manifest_sha256,
        reference_standard_sha256=bundle.reference_standard_sha256,
        review_index=bundle.review_index, coverage_status=bundle.coverage_status,
        total_byte_size=bundle.total_byte_size, included_byte_size=bundle.included_byte_size,
        evidence=(*bundle.evidence, reference), criterion_evidence=criterion_evidence,
        public_content=bundle.public_content,
        evidence_content={**bundle.evidence_content, evidence_id: text},
    )


def build_artifact_evidence(
    *,
    content: bytes,
    manifest: StagedArtifactManifest,
    standard: EvaluationReferenceStandard,
    max_bytes: int,
    review_index: Literal[0, 1],
) -> ArtifactEvidenceBundle:
    """Build stable evidence without query or case-specific selection."""

    if manifest.artifact_v2 is not None:
        descriptor = manifest.artifact_v2
        evidence_v2 = build_evidence_v2(
            descriptor=descriptor,
            content=(content if descriptor.representation.value in {"inline_text", "file"} else None),
            max_bytes=max_bytes,
        )
        references: list[EvidenceReference] = []
        for index, evidence_id in enumerate(evidence_v2.machine_evidence_ids):
            references.append(
                EvidenceReference(
                    evidence_id=evidence_id,
                    kind="machine",
                    content_sha256=descriptor.descriptor_sha256,
                    locator=f"artifact://{manifest.artifact_revision.revision_sha256}#machine/{index}",
                )
            )
        public_evidence_id = None
        public_bytes = evidence_v2.public_content.encode("utf-8")
        if public_bytes:
            public_evidence_id = "artifact:v2:public"
            references.append(
                EvidenceReference(
                    evidence_id=public_evidence_id,
                    kind="structure" if descriptor.representation.value in {"directory", "bundle"} else "full",
                    content_sha256=hashlib.sha256(public_bytes).hexdigest(),
                    start_offset=0,
                    end_offset=len(public_bytes),
                    locator=f"artifact://{manifest.artifact_revision.revision_sha256}#evidence",
                )
            )
        machine_ids = tuple(evidence_v2.machine_evidence_ids)
        criterion_evidence: dict[str, tuple[str, ...]] = {}
        for criterion in standard.criteria:
            if criterion.source is CriterionSource.MACHINE_CONTRACT:
                criterion_evidence[criterion.criterion_id] = machine_ids
            elif public_evidence_id:
                criterion_evidence[criterion.criterion_id] = (public_evidence_id,)
            else:
                criterion_evidence[criterion.criterion_id] = ()
        bundle = ArtifactEvidenceBundle(
            artifact_manifest_sha256=manifest.manifest_sha256,
            reference_standard_sha256=standard.reference_standard_sha256,
            review_index=review_index,
            coverage_status=(
                "complete" if evidence_v2.evidence_status == "complete" else "bounded"
            ),
            total_byte_size=descriptor.byte_size,
            included_byte_size=(
                descriptor.byte_size
                if evidence_v2.evidence_status == "complete"
                else min(len(public_bytes), descriptor.byte_size)
            ),
            evidence=tuple(references),
            criterion_evidence=criterion_evidence,
            public_content=evidence_v2.public_content,
            evidence_content=(
                {public_evidence_id: evidence_v2.public_content}
                if public_evidence_id is not None
                else {}
            ),
        )

        # Read the descriptor from this staged manifest, never from an input or a newer file.
        facts = {
            "artifact_revision": manifest.artifact_revision.model_dump(mode="json"),
            "artifact_manifest_sha256": manifest.manifest_sha256,
            "descriptor": descriptor.model_dump(mode="json", include={
                "representation", "format_id", "extension", "media_type", "byte_size", "contract_status",
                "machine_check_ids", "logical_locator", "descriptor_sha256", "content_sha256",
                "tree_sha256", "bundle_sha256", "primary_member",
            }),
            "scope": "Checks describe this staged artifact only; logical_locator is a binding, not export completion. Only listed checks were performed; tree checks do not establish member encodings.",
        }
        return _attach_fact_evidence(
            bundle=bundle, standard=standard, evidence_id="artifact:v2:current_facts",
            kind="structure", facts=facts,
            locator=f"artifact://{manifest.artifact_revision.revision_sha256}#current-facts",
        )

    if hashlib.sha256(content).hexdigest() != manifest.content_sha256:
        raise EvaluationRuntimeError("artifact_evidence_content_hash_mismatch")
    text = _decode_public_text(content)
    total = len(content)
    if total <= max_bytes:
        refs = (
            EvidenceReference(
                evidence_id="artifact:full",
                kind="full",
                content_sha256=manifest.content_sha256,
                start_offset=0,
                end_offset=total,
                locator=f"artifact://{manifest.artifact_revision.revision_sha256}",
            ),
        )
        return ArtifactEvidenceBundle(
            artifact_manifest_sha256=manifest.manifest_sha256,
            reference_standard_sha256=standard.reference_standard_sha256,
            review_index=review_index,
            coverage_status="complete",
            total_byte_size=total,
            included_byte_size=total,
            evidence=refs,
            criterion_evidence={item.criterion_id: ("artifact:full",) for item in standard.criteria},
            public_content=text,
            evidence_content={"artifact:full": text},
        )

    # Stable offsets are derived from criterion identity, never query keywords.
    segment_budget = max(1024, max_bytes // max(1, min(len(standard.criteria), 16)))
    max_start = max(0, total - segment_budget)
    starts = {0, max_start}
    for criterion in standard.criteria:
        starts.add(int(criterion.criterion_sha256[:12], 16) % (max_start + 1))
    selected: list[tuple[int, int]] = []
    consumed = 0
    for start in sorted(starts):
        if consumed >= max_bytes:
            break
        end = min(total, start + min(segment_budget, max_bytes - consumed))
        if end <= start:
            continue
        selected.append((start, end))
        consumed += end - start
    references: list[EvidenceReference] = []
    chunks: list[str] = []
    evidence_content: dict[str, str] = {}
    for index, (start, end) in enumerate(selected):
        while start < end and content[start] & 0xC0 == 0x80:
            start += 1
        chunk = content[start:end]
        while chunk:
            try:
                decoded = chunk.decode("utf-8", errors="strict")
                break
            except UnicodeDecodeError as exc:
                if exc.end != len(chunk):
                    raise EvaluationRuntimeError(
                        "artifact_evidence_utf8_alignment_invalid"
                    ) from exc
                chunk = chunk[: exc.start]
        else:
            continue
        chunk_bytes = decoded.encode("utf-8")
        evidence_id = f"artifact:segment:{index}"
        references.append(
            EvidenceReference(
                evidence_id=evidence_id,
                kind="segment",
                content_sha256=hashlib.sha256(chunk_bytes).hexdigest(),
                start_offset=start,
                end_offset=start + len(chunk_bytes),
                locator=f"artifact://{manifest.artifact_revision.revision_sha256}#{start}",
            )
        )
        evidence_content[evidence_id] = decoded
        chunks.append(f"[{evidence_id} offset={start}]\n{decoded}")
    evidence_ids = tuple(item.evidence_id for item in references)
    return ArtifactEvidenceBundle(
        artifact_manifest_sha256=manifest.manifest_sha256,
        reference_standard_sha256=standard.reference_standard_sha256,
        review_index=review_index,
        coverage_status="bounded",
        total_byte_size=total,
        included_byte_size=sum((item.end_offset or 0) - (item.start_offset or 0) for item in references),
        evidence=tuple(references),
        criterion_evidence={item.criterion_id: evidence_ids for item in standard.criteria},
        public_content="\n\n".join(chunks),
        evidence_content=evidence_content,
    )


def attach_context_source_evidence(
    *,
    bundle: ArtifactEvidenceBundle,
    standard: EvaluationReferenceStandard,
    context: EvaluationContextSnapshot,
) -> ArtifactEvidenceBundle:
    """Join authorized Public Input/dependency evidence to semantic criteria."""

    publication = context.macro_delivery_standard.get("framework_publication_facts")
    if publication is not None:
        bundle = _attach_fact_evidence(
            bundle=bundle, standard=standard, evidence_id="context:publication_facts",
            kind="context", facts=publication,
            locator=f"context://{context.context_snapshot_sha256}#publication-facts",
        )
    if not context.source_evidence:
        return bundle
    references = list(bundle.evidence)
    evidence_content = dict(bundle.evidence_content)
    source_ids: list[str] = []
    for index, source in enumerate(context.source_evidence, 1):
        evidence_id = f"context:source:{index}"
        content = source.public_content
        if not content:
            content = json.dumps(
                {
                    "source_id": source.source_id,
                    "origin": source.origin,
                    "logical_name": source.logical_name,
                    "representation": source.representation,
                    "media_type": source.media_type,
                    "coverage_status": source.coverage_status,
                    "byte_size": source.byte_size,
                    "content_sha256": source.content_sha256,
                    "descriptor_sha256": source.descriptor_sha256,
                    "structure_evidence": source.structure_evidence,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        content_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        references.append(
            EvidenceReference(
                evidence_id=evidence_id,
                kind="context",
                content_sha256=content_sha256,
                locator=f"context://{source.source_evidence_sha256}",
            )
        )
        evidence_content[evidence_id] = content
        source_ids.append(evidence_id)
    criterion_evidence = dict(bundle.criterion_evidence)
    semantic_criteria = {
        item.criterion_id
        for item in standard.criteria
        if item.source is not CriterionSource.MACHINE_CONTRACT
    }
    for criterion_id in semantic_criteria:
        criterion_evidence[criterion_id] = tuple(
            dict.fromkeys(
                (*criterion_evidence.get(criterion_id, ()), *source_ids)
            )
        )
    return ArtifactEvidenceBundle(
        artifact_manifest_sha256=bundle.artifact_manifest_sha256,
        reference_standard_sha256=bundle.reference_standard_sha256,
        review_index=bundle.review_index,
        coverage_status=bundle.coverage_status,
        total_byte_size=bundle.total_byte_size,
        included_byte_size=bundle.included_byte_size,
        evidence=tuple(references),
        criterion_evidence=criterion_evidence,
        public_content=bundle.public_content,
        evidence_content=evidence_content,
    )


class EvaluationCriterionAssessmentV2(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    criterion_slot: str = Field(min_length=1, max_length=32)
    status: Literal["pass", "fail", "unknown", "not_applicable"]
    evidence_slots: list[str] = Field(max_length=8)
    concise_reason: str = Field(min_length=1)
    repairability: Literal["repairable", "hard"] | None

    @model_validator(mode="after")
    def _validate_status(self) -> "EvaluationCriterionAssessmentV2":
        if any(not item.strip() or len(item) > 32 for item in self.evidence_slots):
            raise ValueError("evaluation_evidence_slot_length_invalid")
        if self.status == "fail" and self.repairability is None:
            raise ValueError("evaluation_fail_requires_repairability")
        if self.status != "fail" and self.repairability is not None:
            raise ValueError("evaluation_repairability_status_contradiction")
        if self.status in {"pass", "fail"} and not self.evidence_slots:
            raise ValueError("evaluation_decisive_status_requires_evidence")
        return self


class _DimensionScoresDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    factual_consistency: float | None = Field(default=None, ge=0.0, le=1.0)
    internal_consistency: float | None = Field(default=None, ge=0.0, le=1.0)
    requirement_completeness: float | None = Field(default=None, ge=0.0, le=1.0)
    dependency_grounding: float | None = Field(default=None, ge=0.0, le=1.0)
    downstream_consumability: float | None = Field(default=None, ge=0.0, le=1.0)


class EvaluationAssessmentProposalV2(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    confidence: float = Field(ge=0.0, le=1.0)
    criterion_assessments: list[EvaluationCriterionAssessmentV2] = Field(max_length=32)
    dimension_scores: _DimensionScoresDraft
    critical_issues: list[str]

    @field_validator("critical_issues")
    @classmethod
    def _validate_critical_issues(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("evaluation_critical_issue_empty")
        return value


@dataclass(frozen=True)
class _EvaluationSlotBinding:
    criterion_slot: str
    criterion_id: str
    source: CriterionSource
    required: bool
    evidence_slot_to_id: Mapping[str, str]


@dataclass(frozen=True)
class EvaluationCallContractV2:
    protocol: Literal["sgar-evaluation-call-contract-v2"]
    criterion_rows: tuple[dict[str, Any], ...]
    evidence_catalog: tuple[dict[str, Any], ...]
    machine_results: tuple[CriterionResult, ...]
    bindings: tuple[_EvaluationSlotBinding, ...]
    contract_sha256: str


def build_evaluation_call_contract(
    *,
    standard: EvaluationReferenceStandard,
    bundle: ArtifactEvidenceBundle,
) -> EvaluationCallContractV2:
    evidence_by_id = {item.evidence_id: item for item in bundle.evidence}
    globally_used_ids = tuple(
        dict.fromkeys(
            evidence_id
            for criterion in standard.criteria
            if criterion.source is not CriterionSource.MACHINE_CONTRACT
            for evidence_id in bundle.criterion_evidence.get(criterion.criterion_id, ())
        )
    )
    global_slot_by_id = {
        evidence_id: f"e{index}" for index, evidence_id in enumerate(globally_used_ids, 1)
    }
    for evidence_id in globally_used_ids:
        if evidence_id in {"artifact:v2:current_facts", "context:publication_facts"} and not bundle.evidence_content.get(evidence_id):
            raise EvaluationRuntimeError("evaluation_fact_evidence_content_missing")
    evidence_catalog = tuple(
        {
            "evidence_slot": global_slot_by_id[evidence_id],
            "kind": evidence_by_id[evidence_id].kind,
            "public_content": bundle.evidence_content.get(
                evidence_id,
                bundle.public_content,
            ),
        }
        for evidence_id in globally_used_ids
    )
    criterion_rows: list[dict[str, Any]] = []
    machine_results: list[CriterionResult] = []
    bindings: list[_EvaluationSlotBinding] = []
    model_index = 0
    for criterion in standard.criteria:
        allowed_ids = tuple(bundle.criterion_evidence.get(criterion.criterion_id, ()))
        if criterion.source is CriterionSource.MACHINE_CONTRACT:
            machine_results.append(
                CriterionResult(
                    criterion_id=criterion.criterion_id,
                    status=CriterionStatus.PASS,
                    evidence_ids=allowed_ids,
                    concise_reason="Machine contract checks passed before semantic evaluation.",
                )
            )
            continue
        model_index += 1
        criterion_slot = f"c{model_index}"
        slot_to_id = {
            global_slot_by_id[evidence_id]: evidence_id for evidence_id in allowed_ids
        }
        criterion_rows.append(
            {
                "criterion_slot": criterion_slot,
                "source": criterion.source.value,
                "description": criterion.description,
                "required": criterion.required,
                "evidence_slots": list(slot_to_id),
            }
        )
        bindings.append(
            _EvaluationSlotBinding(
                criterion_slot=criterion_slot,
                criterion_id=criterion.criterion_id,
                source=criterion.source,
                required=criterion.required,
                evidence_slot_to_id=slot_to_id,
            )
        )
    public_projection = {
        "protocol": "sgar-evaluation-call-contract-v2",
        "criteria": criterion_rows,
        "evidence_catalog": evidence_catalog,
        "machine_criterion_count": len(machine_results),
        "coverage_status": bundle.coverage_status,
    }
    return EvaluationCallContractV2(
        protocol="sgar-evaluation-call-contract-v2",
        criterion_rows=tuple(criterion_rows),
        evidence_catalog=evidence_catalog,
        machine_results=tuple(machine_results),
        bindings=tuple(bindings),
        contract_sha256=canonical_sha256(public_projection),
    )


def project_evaluation_assessment(
    *,
    proposal: EvaluationAssessmentProposalV2,
    call_contract: EvaluationCallContractV2,
    standard: EvaluationReferenceStandard,
    bundle: ArtifactEvidenceBundle,
    manifest: StagedArtifactManifest,
    context: EvaluationContextSnapshot,
    evaluator_resource_id: str,
    evaluator_api_model_id: str,
    accounting_operation_id: str | None,
    request_sha256: str,
    response_sha256: str,
    review_index: Literal[0, 1],
) -> EvaluationDecision:
    bindings = {item.criterion_slot: item for item in call_contract.bindings}
    assessment_by_slot = {
        item.criterion_slot: item for item in proposal.criterion_assessments
    }
    if len(assessment_by_slot) != len(proposal.criterion_assessments):
        raise EvaluationRuntimeError("evaluation_criterion_slot_duplicate")
    if set(assessment_by_slot) != set(bindings):
        raise EvaluationRuntimeError("evaluation_criterion_slot_set_mismatch")
    results = list(call_contract.machine_results)
    hard_failure = False
    repairable_failure = False
    for slot in (item.criterion_slot for item in call_contract.bindings):
        binding = bindings[slot]
        assessment = assessment_by_slot[slot]
        if any(item not in binding.evidence_slot_to_id for item in assessment.evidence_slots):
            raise EvaluationRuntimeError("evaluation_evidence_slot_invalid")
        evidence_ids = tuple(
            binding.evidence_slot_to_id[item] for item in assessment.evidence_slots
        )
        if assessment.status == "fail":
            hard_failure |= assessment.repairability == "hard"
            repairable_failure |= assessment.repairability == "repairable"
        results.append(
            CriterionResult(
                criterion_id=binding.criterion_id,
                status=CriterionStatus(assessment.status),
                evidence_ids=evidence_ids,
                concise_reason=assessment.concise_reason,
            )
        )
    order = {item.criterion_id: index for index, item in enumerate(standard.criteria)}
    results.sort(key=lambda item: order[item.criterion_id])
    required = {
        item.criterion_id for item in standard.criteria if item.required
    }
    required_results = [item for item in results if item.criterion_id in required]
    has_fail = any(
        item.status is CriterionStatus.FAIL and bool(item.evidence_ids)
        for item in required_results
    )
    has_unknown = any(
        item.status in {CriterionStatus.UNKNOWN, CriterionStatus.NOT_APPLICABLE}
        for item in required_results
    )
    if has_fail:
        verdict = EvaluationVerdict.FAIL
        failure_code = "artifact_quality_failure"
        training_label = "hard_case" if hard_failure else "repairable_case"
    elif has_unknown or bundle.coverage_status == "bounded":
        verdict = EvaluationVerdict.INCONCLUSIVE
        failure_code = "evaluation_inconclusive"
        training_label = "evaluator_noise"
    else:
        verdict = EvaluationVerdict.PASS
        failure_code = None
        training_label = "good_case"
    return EvaluationDecision(
        verdict=verdict,
        failure_code=failure_code,
        confidence=proposal.confidence,
        criterion_results=tuple(results),
        dimension_scores=EvaluationDimensionScores.model_validate(
            proposal.dimension_scores.model_dump(mode="python")
        ),
        critical_issues=tuple(proposal.critical_issues),
        training_label=training_label,
        reference_standard_sha256=standard.reference_standard_sha256,
        evidence_bundle_sha256=bundle.evidence_bundle_sha256,
        artifact_manifest_sha256=manifest.manifest_sha256,
        context_snapshot_sha256=context.context_snapshot_sha256,
        evaluator_model_resource_id=evaluator_resource_id,
        evaluator_api_model_id=evaluator_api_model_id,
        accounting_operation_id=accounting_operation_id,
        request_sha256=request_sha256,
        response_sha256=response_sha256,
        review_index=review_index,
    )


def _evaluation_failure_category(exc: BaseException) -> str:
    text = str(exc)
    if isinstance(exc, (json.JSONDecodeError,)) or "json_invalid" in text:
        return "evaluation_json_invalid"
    for code in (
        "evaluation_criterion_slot_set_mismatch",
        "evaluation_criterion_slot_duplicate",
        "evaluation_evidence_slot_invalid",
        "evaluation_decisive_status_requires_evidence",
        "evaluation_fail_requires_repairability",
        "evaluation_repairability_status_contradiction",
    ):
        if code in text:
            return code
    if isinstance(exc, ValidationError) or "schema_invalid" in text:
        return "evaluation_model_output_schema_invalid"
    if isinstance(exc, EvaluationRuntimeError):
        return "evaluation_dynamic_invariant_mismatch"
    return "evaluation_framework_projection_failure"


def _evaluation_boundary_diagnostic(exc: Exception, boundary: str) -> dict[str, Any]:
    """Record only protocol locations and stable codes, never rejected values."""
    category = {
        "structured_ingress": "evaluation_structured_ingress_invalid",
        "proposal_schema": "evaluation_proposal_schema_invalid",
        "assessment_projection": "evaluation_assessment_projection_invalid",
        "decision_validation": "evaluation_decision_validation_invalid",
    }[boundary]
    diagnostic: dict[str, Any] = {
        "boundary": boundary, "failure_code": category,
        "failure_category": category, "exception_type": type(exc).__name__,
        "invariant_code": _evaluation_failure_category(exc),
        "message_sha256": canonical_sha256(str(exc)),
    }
    if isinstance(exc, ValidationError):
        # Non-field dictionary keys may be source values: do not persist them.
        allowed = set(EvaluationAssessmentProposalV2.model_fields)
        allowed.update(EvaluationCriterionAssessmentV2.model_fields)
        allowed.update(_DimensionScoresDraft.model_fields)
        diagnostic["errors"] = [
            {"loc": [part if isinstance(part, int) or part in allowed else "<dynamic-key>"
                     for part in error["loc"]], "type": error["type"]}
            for error in exc.errors(include_url=False, include_context=False, include_input=False)
        ]
    return diagnostic


def _prompt_payload(
    *,
    standard: EvaluationReferenceStandard,
    bundle: ArtifactEvidenceBundle,
    context: EvaluationContextSnapshot,
    review_ref: EvaluationReviewRef | None,
    call_contract: EvaluationCallContractV2,
    structured_role_contract: Mapping[str, Any],
    review_diagnostic: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        "protocol": "sgar-evaluation-input-v6",
        "instruction": (
            "Judge only the listed criterion slots. Cite evidence slots scoped to the current "
            "criterion for every pass or fail. Evidence kind=context contains bounded, "
            "identity-checked Public Input, committed dependency material, or explicitly labeled "
            "framework publication facts; compare it with "
            "the artifact evidence for grounding and factual claims. "
            "The original public task owns explicit requirements. macro_delivery_standard "
            "declares this subtask's responsibility; current_contract is the Compiler's concrete "
            "execution contract, not a replacement for the task. Structural checks have passed; "
            "judge meaning, completeness, grounding and factual correctness. For a document "
            "describing a result, evaluate whether its rules match the requested target and "
            "transformation; source agreement alone is insufficient. This is the document's "
            "own responsibility, not the later consumer's execution or delivery. Preservation "
            "requirements do not undo a requested transformation. A Compiler choice "
            "cannot excuse a violation of explicit task requirements. Cite the conflict and "
            "its stage in the reason. Accept differing structures if the task permits them. "
            "Do not invent an alternative required structure. document_validation reports local "
            "syntax coverage only; partial coverage is neither invalidity nor full verification. "
            "Use unknown when evidence is insufficient. Do not add requirements, style "
            "preferences, best practices, or downstream work. Return one strict JSON object "
            "and no chain-of-thought. " + STAGED_DELIVERY_EVALUATION_INSTRUCTIONS + "\n\n" + BOUND_SCHEMA_EVALUATION_INSTRUCTIONS
        ),
        "evaluation_call_contract": {
            "protocol": call_contract.protocol,
            "criteria": list(call_contract.criterion_rows),
            "evidence_catalog": list(call_contract.evidence_catalog),
            "contract_sha256": call_contract.contract_sha256,
            "coverage_status": bundle.coverage_status,
        },
        "public_context": {
            "original_public_objective": context.original_public_objective,
            "current_contract": context.current_contract,
            "macro_delivery_standard": context.macro_delivery_standard,
            "document_validation": context.document_validation,
            "source_evidence_descriptors": [
                {
                    "source_id": item.source_id,
                    "origin": item.origin,
                    "logical_name": item.logical_name,
                    "coverage_status": item.coverage_status,
                    "content_sha256": item.content_sha256,
                    "descriptor_sha256": item.descriptor_sha256,
                    "source_evidence_sha256": item.source_evidence_sha256,
                }
                for item in context.source_evidence
            ],
            "downstream_consumer_descriptors": context.downstream_consumer_descriptors,
        },
        "structured_role_contract": dict(structured_role_contract),
        "review": (
            {
                "previous_hash": review_ref.initial_decision_sha256,
                "diagnostic": dict(review_diagnostic or {}),
            }
            if review_ref
            else None
        ),
    }


def _response_text(response: Any) -> str:
    choices = getattr(response, "choices", None)
    if not choices:
        return ""
    message = getattr(choices[0], "message", None)
    return str(getattr(message, "content", "") or "")


def _response_finish_reason(response: Any) -> str:
    choices = getattr(response, "choices", None)
    if not choices:
        return ""
    return str(getattr(choices[0], "finish_reason", "") or "").strip().lower()


@dataclass(frozen=True)
class EvaluationOutcome:
    status: Literal[
        "pass",
        "fail",
        "inconclusive",
        "protocol_inconclusive",
        "infrastructure_failure",
        "framework_failure",
        "budget_failure",
        "interrupted",
    ]
    final_decision: EvaluationDecision | None
    initial_decision: EvaluationDecision | None
    review_decision: EvaluationDecision | None
    review_triggered: bool
    failure_code: str | None
    accounting_operation_ids: tuple[str, ...]
    terminal_failure: TerminalFailureEnvelope | None = None


def _attach_terminal_failure(
    outcome: EvaluationOutcome,
    *,
    manifest: StagedArtifactManifest,
) -> EvaluationOutcome:
    if outcome.status == "pass" or outcome.terminal_failure is not None:
        return outcome
    if outcome.status == "infrastructure_failure":
        responsibility, stage = "infrastructure", "evaluation_transport"
    elif outcome.status == "framework_failure":
        responsibility, stage = "framework", "evaluation"
    elif outcome.status == "budget_failure":
        responsibility, stage = "budget", "evaluation_transport"
    elif outcome.status == "interrupted":
        responsibility, stage = "interrupted", "evaluation"
    elif outcome.status == "fail":
        responsibility, stage = "research", "artifact_quality"
    elif outcome.status == "inconclusive":
        responsibility, stage = "research", "evaluator_inconclusive"
    else:
        responsibility, stage = "research", "evaluation_protocol"
    revision = manifest.artifact_revision.subtask_revision
    return replace(
        outcome,
        terminal_failure=TerminalFailureEnvelope.create(
            responsibility=responsibility,
            failure_stage=stage,
            failure_code=outcome.failure_code or f"evaluation_{outcome.status}",
            response_received=outcome.status
            in {"fail", "inconclusive", "protocol_inconclusive"},
            run_id=manifest.artifact_revision.run_id,
            graph_revision=revision.graph_revision,
            subtask_id=revision.subtask_id,
            subtask_revision=revision.subtask_revision,
            model_operation_id=(
                outcome.accounting_operation_ids[-1]
                if outcome.accounting_operation_ids
                else None
            ),
            evaluation_operation_id=(
                outcome.accounting_operation_ids[-1]
                if outcome.accounting_operation_ids
                else None
            ),
        ),
    )


@dataclass(frozen=True)
class _AttemptOutcome:
    status: Literal[
        "decision",
        "invalid_response",
        "infrastructure_failure",
        "framework_failure",
        "budget_failure",
        "interrupted",
    ]
    decision: EvaluationDecision | None
    failure_code: str | None
    accounting_operation_id: str | None
    response_received: bool
    terminal_failure: TerminalFailureEnvelope | None = None
    diagnostic: Mapping[str, Any] | None = None
    proposal_sha256: str | None = None


class EvaluationCoordinator:
    def __init__(
        self,
        *,
        transport: AsyncModelTransportPort,
        resolved_model: ResolvedEvaluatorModel,
        policy: EvaluatorPolicy,
        cost_ledger: RunCostLedger | None,
        event_ledger: EvaluationEventLedger,
    ) -> None:
        normalize_structured_response_mode(resolved_model.response_mode)
        # Provider output tokens bound generation; prose length is not an acceptance rule.
        self.transport = require_async_model_transport(transport)
        self.resolved_model = resolved_model
        self.policy = policy
        self.cost_ledger = cost_ledger
        self.event_ledger = event_ledger
        self._locks: dict[str, asyncio.Lock] = {}
        self._cache: dict[str, EvaluationOutcome] = {}

    async def evaluate(
        self,
        *,
        manifest: StagedArtifactManifest,
        content: bytes,
        standard: EvaluationReferenceStandard,
        context: EvaluationContextSnapshot,
        payload_guard_factory: Callable[[int], Callable[[Mapping[str, Any]], None] | None],
    ) -> EvaluationOutcome:
        identity = canonical_sha256(
            {
                "artifact_manifest_sha256": manifest.manifest_sha256,
                "reference_standard_sha256": standard.reference_standard_sha256,
                "context_snapshot_sha256": context.context_snapshot_sha256,
                "evaluator_policy_sha256": self.policy.policy_sha256,
                "evaluator_model_sha256": self.resolved_model.identity_sha256,
            }
        )
        lock = self._locks.setdefault(identity, asyncio.Lock())
        async with lock:
            if identity in self._cache:
                return self._cache[identity]
            initial_bundle = build_artifact_evidence(
                content=content,
                manifest=manifest,
                standard=standard,
                max_bytes=self.policy.initial_evidence_max_bytes,
                review_index=0,
            )
            initial_bundle = attach_context_source_evidence(
                bundle=initial_bundle,
                standard=standard,
                context=context,
            )
            initial = await self._attempt(
                identity=identity,
                review_index=0,
                manifest=manifest,
                standard=standard,
                bundle=initial_bundle,
                context=context,
                review_ref=None,
                payload_guard_factory=payload_guard_factory,
            )
            operation_ids = tuple(
                item for item in (initial.accounting_operation_id,) if item
            )
            if initial.status in {
                "infrastructure_failure",
                "framework_failure",
                "budget_failure",
                "interrupted",
            }:
                outcome = EvaluationOutcome(
                    status=initial.status,
                    final_decision=None,
                    initial_decision=None,
                    review_decision=None,
                    review_triggered=False,
                    failure_code=initial.failure_code,
                    accounting_operation_ids=operation_ids,
                    terminal_failure=initial.terminal_failure,
                )
                outcome = _attach_terminal_failure(outcome, manifest=manifest)
                self._cache[identity] = outcome
                return outcome

            if initial.status == "decision" and initial.decision is not None:
                if initial.decision.verdict is EvaluationVerdict.PASS:
                    outcome = EvaluationOutcome(
                        status="pass",
                        final_decision=initial.decision,
                        initial_decision=initial.decision,
                        review_decision=None,
                        review_triggered=False,
                        failure_code=None,
                        accounting_operation_ids=operation_ids,
                    )
                    self._cache[identity] = outcome
                    return outcome
                if initial.decision.verdict is EvaluationVerdict.FAIL:
                    outcome = EvaluationOutcome(
                        status="fail",
                        final_decision=initial.decision,
                        initial_decision=initial.decision,
                        review_decision=None,
                        review_triggered=False,
                        failure_code="artifact_quality_failure",
                        accounting_operation_ids=operation_ids,
                    )
                    outcome = _attach_terminal_failure(outcome, manifest=manifest)
                    self._cache[identity] = outcome
                    return outcome

            # Invalid/schema-inconsistent/inconclusive responses receive exactly one review.
            initial_hash = (
                initial.decision.decision_sha256
                if initial.decision is not None
                else canonical_sha256(
                    {
                        "identity": identity,
                        "status": initial.status,
                        "failure_code": initial.failure_code,
                    }
                )
            )
            review_ref = EvaluationReviewRef(
                initial_decision_sha256=initial_hash,
                artifact_manifest_sha256=manifest.manifest_sha256,
                reference_standard_sha256=standard.reference_standard_sha256,
                context_snapshot_sha256=context.context_snapshot_sha256,
            )
            # Review is a correction over the exact same canonical evidence
            # snapshot.  Only the bounded structured diagnostic is additional.
            review_bundle = initial_bundle
            review = await self._attempt(
                identity=identity,
                review_index=1,
                manifest=manifest,
                standard=standard,
                bundle=review_bundle,
                context=context,
                review_ref=review_ref,
                review_diagnostic={
                    "previous_failure_category": initial.failure_code,
                    "previous_proposal_sha256": initial.proposal_sha256,
                    "normalized_status": (
                        initial.decision.verdict.value
                        if initial.decision is not None
                        else initial.status
                    ),
                    **dict(initial.diagnostic or {}),
                },
                payload_guard_factory=payload_guard_factory,
            )
            operation_ids = tuple(
                item
                for item in (initial.accounting_operation_id, review.accounting_operation_id)
                if item
            )
            if review.status == "decision" and review.decision is not None:
                if review.decision.verdict is EvaluationVerdict.PASS:
                    final_status, failure_code = "pass", None
                elif review.decision.verdict is EvaluationVerdict.FAIL:
                    final_status, failure_code = "fail", "artifact_quality_failure"
                else:
                    final_status, failure_code = "inconclusive", "evaluation_inconclusive"
                outcome = EvaluationOutcome(
                    status=final_status,
                    final_decision=review.decision,
                    initial_decision=initial.decision,
                    review_decision=review.decision,
                    review_triggered=True,
                    failure_code=failure_code,
                    accounting_operation_ids=operation_ids,
                )
            elif review.status == "invalid_response":
                outcome = EvaluationOutcome(
                    status="protocol_inconclusive",
                    final_decision=None,
                    initial_decision=initial.decision,
                    review_decision=None,
                    review_triggered=True,
                    failure_code="evaluation_protocol_inconclusive",
                    accounting_operation_ids=operation_ids,
                )
            else:
                outcome = EvaluationOutcome(
                    status=review.status,
                    final_decision=None,
                    initial_decision=initial.decision,
                    review_decision=None,
                    review_triggered=True,
                    failure_code=review.failure_code,
                    accounting_operation_ids=operation_ids,
                    terminal_failure=review.terminal_failure,
                )
            outcome = _attach_terminal_failure(outcome, manifest=manifest)
            self._cache[identity] = outcome
            return outcome

    def _framework_attempt_failure(
        self,
        *,
        event_prefix: str,
        operation_id: str,
        review_index: int,
        request_hash: str,
        manifest: StagedArtifactManifest,
        failure_code: str,
        exception: BaseException,
        accounting_operation_id: str | None = None,
        response_received: bool = False,
        response_sha256: str | None = None,
        diagnostic: Mapping[str, Any] | None = None,
    ) -> _AttemptOutcome:
        revision = manifest.artifact_revision.subtask_revision
        terminal_failure = TerminalFailureEnvelope.create(
            responsibility="framework",
            failure_stage="evaluation",
            failure_code=failure_code,
            exception=exception,
            response_received=response_received,
            run_id=manifest.artifact_revision.run_id,
            graph_revision=revision.graph_revision,
            subtask_id=revision.subtask_id,
            subtask_revision=revision.subtask_revision,
            model_operation_id=accounting_operation_id,
            evaluation_operation_id=operation_id,
        )
        try:
            self.event_ledger.append_event(
                event_prefix + "_finished",
                {
                    "evaluation_operation_id": operation_id,
                    "review_index": review_index,
                    "status": "framework_failure",
                    "failure_code": failure_code,
                    "request_sha256": request_hash,
                    "accounting_operation_id": accounting_operation_id,
                    "response_received": response_received,
                    "response_sha256": response_sha256,
                    "diagnostic": diagnostic,
                    "exception_type": terminal_failure.exception_type,
                    "message_sha256": terminal_failure.message_sha256,
                },
            )
        except EvaluationPersistenceError as persistence_error:
            terminal_failure = TerminalFailureEnvelope.create(
                responsibility="framework",
                failure_stage="evaluation_persistence",
                failure_code="evaluation_terminal_persistence_failed",
                exception=persistence_error,
                run_id=manifest.artifact_revision.run_id,
                graph_revision=revision.graph_revision,
                subtask_id=revision.subtask_id,
                subtask_revision=revision.subtask_revision,
                model_operation_id=accounting_operation_id,
                evaluation_operation_id=operation_id,
                primary_failure_sha256=terminal_failure.failure_sha256,
                response_received=response_received,
            )
        return _AttemptOutcome(
            status="framework_failure",
            decision=None,
            failure_code=terminal_failure.failure_code,
            accounting_operation_id=accounting_operation_id,
            response_received=response_received,
            terminal_failure=terminal_failure,
            diagnostic=diagnostic,
            proposal_sha256=response_sha256,
        )

    async def _attempt(
        self,
        *,
        identity: str,
        review_index: Literal[0, 1],
        manifest: StagedArtifactManifest,
        standard: EvaluationReferenceStandard,
        bundle: ArtifactEvidenceBundle,
        context: EvaluationContextSnapshot,
        review_ref: EvaluationReviewRef | None,
        review_diagnostic: Mapping[str, Any] | None = None,
        payload_guard_factory: Callable[
            [int], Callable[[Mapping[str, Any]], None] | None
        ],
    ) -> _AttemptOutcome:
        event_prefix = "evaluation" if review_index == 0 else "evaluation_review"
        operation_id = f"{identity}:{review_index}"
        call_contract = build_evaluation_call_contract(standard=standard, bundle=bundle)
        role_contract = build_structured_role_contract(
            "evaluator",
            mode=self.resolved_model.response_mode,
            projector_version="evaluation-slot-projector-v2",
        )
        prompt_payload = _prompt_payload(
            standard=standard,
            bundle=bundle,
            context=context,
            review_ref=review_ref,
            call_contract=call_contract,
            structured_role_contract=structured_role_prompt_projection(
                role_contract,
                selected_mode=self.resolved_model.response_mode,
            ),
            review_diagnostic=review_diagnostic,
        )
        prompt = json.dumps(prompt_payload, ensure_ascii=False, separators=(",", ":"))
        api_kwargs: dict[str, Any] = {
            "model": self.resolved_model.api_model_id,
            "messages": [
                {
                    "role": "system",
                    "content": prompt_file_text("evaluator_system.txt"),
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self.policy.max_output_tokens,
        }
        if self.policy.reasoning_effort is not None:
            api_kwargs["reasoning_effort"] = self.policy.reasoning_effort
        if self.policy.temperature is not None:
            api_kwargs["temperature"] = self.policy.temperature
        api_kwargs["response_format"] = system_role_response_format(
            "evaluator",
            mode=normalize_structured_response_mode(
                self.resolved_model.response_mode
            ),
        )
        frozen_kwargs = deepcopy(api_kwargs)
        request_hash = model_request_sha256(frozen_kwargs)
        try:
            self.event_ledger.append_event(
                event_prefix + "_started",
                {
                    "evaluation_operation_id": operation_id,
                    "review_index": review_index,
                    "artifact_manifest_sha256": manifest.manifest_sha256,
                    "reference_standard_sha256": standard.reference_standard_sha256,
                    "evidence_bundle_sha256": bundle.evidence_bundle_sha256,
                    "context_snapshot_sha256": context.context_snapshot_sha256,
                    "request_sha256": request_hash,
                },
            )
        except EvaluationPersistenceError as exc:
            revision = manifest.artifact_revision.subtask_revision
            return _AttemptOutcome(
                status="framework_failure",
                decision=None,
                failure_code="evaluation_started_persistence_failed",
                accounting_operation_id=None,
                response_received=False,
                terminal_failure=TerminalFailureEnvelope.create(
                    responsibility="framework",
                    failure_stage="evaluation_persistence",
                    failure_code="evaluation_started_persistence_failed",
                    exception=exc,
                    run_id=manifest.artifact_revision.run_id,
                    graph_revision=revision.graph_revision,
                    subtask_id=revision.subtask_id,
                    subtask_revision=revision.subtask_revision,
                    evaluation_operation_id=operation_id,
                ),
            )

        accounting_context: ModelCallContext | None = None
        accounting_operation_id: str | None = None
        try:
            if self.cost_ledger is not None:
                accounting_context = self.cost_ledger.new_operation(
                    stage="evaluator_review" if review_index else "evaluator",
                    subtask_id=context.current_revision.subtask_id,
                    subtask_revision=context.current_revision.subtask_revision,
                )
                accounting_operation_id = accounting_context.operation_id
            payload_guard = payload_guard_factory(review_index)
        except asyncio.CancelledError:
            self.event_ledger.append_event(
                "evaluation_interrupted",
                {
                    "evaluation_operation_id": operation_id,
                    "review_index": review_index,
                    "request_sha256": request_hash,
                },
            )
            raise
        except Exception as exc:
            return self._framework_attempt_failure(
                event_prefix=event_prefix,
                operation_id=operation_id,
                review_index=review_index,
                request_hash=request_hash,
                manifest=manifest,
                failure_code="evaluation_request_context_failed",
                exception=exc,
                accounting_operation_id=accounting_operation_id,
            )

        response_text: str | None = None
        finish_reason = ""
        transport_attempt_limit = self.policy.transport_retry_limit + 1
        for attempt in range(1, transport_attempt_limit + 1):
            if payload_guard is not None:
                try:
                    payload_guard(deepcopy(frozen_kwargs))
                except asyncio.CancelledError:
                    self.event_ledger.append_event(
                        "evaluation_interrupted",
                        {
                            "evaluation_operation_id": operation_id,
                            "review_index": review_index,
                            "request_sha256": request_hash,
                        },
                    )
                    raise
                except Exception as exc:
                    return self._framework_attempt_failure(
                        event_prefix=event_prefix,
                        operation_id=operation_id,
                        review_index=review_index,
                        request_hash=request_hash,
                        manifest=manifest,
                        failure_code="evaluation_payload_guard_failed",
                        exception=exc,
                        accounting_operation_id=accounting_operation_id,
                    )
            try:
                response = await self.transport.send(
                    ledger=self.cost_ledger,
                    context=accounting_context,
                    **deepcopy(frozen_kwargs),
                )
                response_text = _response_text(response)
                finish_reason = _response_finish_reason(response)
                self.event_ledger.append_event(
                    "evaluation_response_received",
                    {
                        "evaluation_operation_id": operation_id,
                        "review_index": review_index,
                        "transport_attempt": attempt,
                        "request_sha256": request_hash,
                        "response_sha256": canonical_sha256(response_text),
                        "finish_reason": finish_reason,
                        "accounting_operation_id": accounting_operation_id,
                    },
                )
                break
            except asyncio.CancelledError:
                self.event_ledger.append_event(
                    "evaluation_interrupted",
                    {
                        "evaluation_operation_id": operation_id,
                        "review_index": review_index,
                        "request_sha256": request_hash,
                    },
                )
                raise
            except BudgetControlError:
                self.event_ledger.append_event(
                    event_prefix + "_finished",
                    {
                        "evaluation_operation_id": operation_id,
                        "review_index": review_index,
                        "status": "budget_failure",
                        "failure_code": "evaluation_budget_blocked",
                        "request_sha256": request_hash,
                    },
                )
                return _AttemptOutcome(
                    status="budget_failure",
                    decision=None,
                    failure_code="evaluation_budget_blocked",
                    accounting_operation_id=accounting_operation_id,
                    response_received=False,
                )
            except Exception as exc:
                retryable, failure_code = classify_transport_exception(exc)
                if retryable and attempt < transport_attempt_limit:
                    continue
                if not retryable:
                    return self._framework_attempt_failure(
                        event_prefix=event_prefix,
                        operation_id=operation_id,
                        review_index=review_index,
                        request_hash=request_hash,
                        manifest=manifest,
                        failure_code=failure_code,
                        exception=exc,
                        accounting_operation_id=accounting_operation_id,
                    )
                status = "infrastructure_failure" if retryable else "framework_failure"
                self.event_ledger.append_event(
                    event_prefix + "_finished",
                    {
                        "evaluation_operation_id": operation_id,
                        "review_index": review_index,
                        "status": status,
                        "failure_code": failure_code,
                        "transport_attempt": attempt,
                        "request_sha256": request_hash,
                    },
                )
                return _AttemptOutcome(
                    status=status,
                    decision=None,
                    failure_code=failure_code,
                    accounting_operation_id=accounting_operation_id,
                    response_received=False,
                )

        if response_text is None:
            raise EvaluationRuntimeError("evaluation_transport_terminal_state_missing")
        response_hash = canonical_sha256(response_text)
        if finish_reason in {"length", "max_tokens", "max_output_tokens"}:
            self.event_ledger.append_event(
                event_prefix + "_finished",
                {
                    "evaluation_operation_id": operation_id,
                    "review_index": review_index,
                    "status": "invalid_response",
                    "failure_code": "evaluator_output_truncated",
                    "request_sha256": request_hash,
                    "response_sha256": response_hash,
                },
            )
            return _AttemptOutcome(
                status="invalid_response",
                decision=None,
                failure_code="evaluator_output_truncated",
                accounting_operation_id=accounting_operation_id,
                response_received=True,
                proposal_sha256=response_hash,
                diagnostic={"failure_path": "$.finish_reason"},
            )
        boundary = "structured_ingress"
        try:
            # Deliberately no code-fence extraction, substring extraction,
            # aliases, coercion, defaults, regex salvage, or case correction.
            decoded = validate_structured_response_content(
                response_text,
                requirement=system_role_requirement("evaluator"),
                mode=self.resolved_model.response_mode,
            )
            boundary = "proposal_schema"
            proposal = EvaluationAssessmentProposalV2.model_validate_json(
                json.dumps(decoded, ensure_ascii=False),
                strict=True,
            )
            boundary = "assessment_projection"
            decision = project_evaluation_assessment(
                proposal=proposal,
                call_contract=call_contract,
                standard=standard,
                bundle=bundle,
                manifest=manifest,
                context=context,
                evaluator_resource_id=self.resolved_model.resource_id,
                evaluator_api_model_id=self.resolved_model.api_model_id,
                accounting_operation_id=accounting_operation_id,
                request_sha256=request_hash,
                response_sha256=response_hash,
                review_index=review_index,
            )
            boundary = "decision_validation"
            validate_evaluation_decision(decision=decision, standard=standard, bundle=bundle)
        except Exception as exc:
            diagnostic = _evaluation_boundary_diagnostic(exc, boundary)
            model_correctable_projection = (
                type(exc) is EvaluationRuntimeError
                and str(exc) in {
                    "evaluation_criterion_slot_duplicate",
                    "evaluation_criterion_slot_set_mismatch",
                    "evaluation_evidence_slot_invalid",
                }
            )
            if boundary == "decision_validation" or (
                boundary == "assessment_projection" and not model_correctable_projection
            ):
                return self._framework_attempt_failure(
                    event_prefix=event_prefix, operation_id=operation_id,
                    review_index=review_index, request_hash=request_hash, manifest=manifest,
                    failure_code=diagnostic["failure_code"], exception=exc,
                    accounting_operation_id=accounting_operation_id,
                    response_received=True, response_sha256=response_hash, diagnostic=diagnostic,
                )
            self.event_ledger.append_event(
                event_prefix + "_finished",
                {
                    "evaluation_operation_id": operation_id,
                    "review_index": review_index,
                    "status": "invalid_response",
                    "failure_code": diagnostic["failure_code"],
                    "diagnostic": diagnostic,
                    "request_sha256": request_hash,
                    "response_sha256": response_hash,
                    "accounting_operation_id": accounting_operation_id,
                },
            )
            return _AttemptOutcome(
                status="invalid_response",
                decision=None,
                failure_code=diagnostic["failure_code"],
                accounting_operation_id=accounting_operation_id,
                response_received=True,
                diagnostic=diagnostic,
                proposal_sha256=(
                    canonical_sha256(decoded) if "decoded" in locals() else None
                ),
            )

        subtask_component = bounded_path_component(
            manifest.artifact_revision.subtask_revision.subtask_id,
            fallback="subtask",
        )
        artifact_name = (
            f"{manifest.artifact_revision.subtask_revision.graph_revision}_"
            f"{subtask_component}_"
            f"{manifest.artifact_revision.subtask_revision.subtask_revision}_"
            f"{'review' if review_index else 'initial'}.json"
        )
        try:
            self.event_ledger.write_artifact(
                artifact_name,
                {
                    "schema_version": "sgar-evaluation-decision-v1",
                    "decision": decision.model_dump(mode="json"),
                    "request_sha256": request_hash,
                    "response_sha256": response_hash,
                },
            )
            self.event_ledger.append_event(
                event_prefix + "_finished",
                {
                    "evaluation_operation_id": operation_id,
                    "review_index": review_index,
                    "status": decision.verdict.value,
                    "decision_sha256": decision.decision_sha256,
                    "request_sha256": request_hash,
                    "response_sha256": response_hash,
                    "accounting_operation_id": accounting_operation_id,
                },
            )
        except EvaluationPersistenceError:
            return _AttemptOutcome(
                status="framework_failure",
                decision=decision,
                failure_code="evaluation_terminal_persistence_failed",
                accounting_operation_id=accounting_operation_id,
                response_received=True,
            )
        terminal_progress.evaluation_reasons(decision, context)
        return _AttemptOutcome(
            status="decision",
            decision=decision,
            failure_code=None,
            accounting_operation_id=accounting_operation_id,
            response_received=True,
        )


class StaticEvaluationCoordinator:
    """Accept statically valid artifacts without dispatching an evaluator model."""

    def __init__(
        self,
        *,
        mode: EvaluationMode,
        event_ledger: EvaluationEventLedger,
        evidence_max_bytes: int = 262144,
    ) -> None:
        self.mode = normalize_evaluation_mode(mode)
        if self.mode == "active":
            raise EvaluationRuntimeError("static_evaluator_active_mode_invalid")
        self.event_ledger = event_ledger
        self.evidence_max_bytes = max(1, int(evidence_max_bytes))

    async def evaluate(
        self,
        *,
        manifest: StagedArtifactManifest,
        content: bytes,
        standard: EvaluationReferenceStandard,
        context: EvaluationContextSnapshot,
        payload_guard_factory: Callable[[int], Callable[[Mapping[str, Any]], None] | None],
    ) -> EvaluationOutcome:
        del payload_guard_factory
        bundle = build_artifact_evidence(
            content=content,
            manifest=manifest,
            standard=standard,
            max_bytes=self.evidence_max_bytes,
            review_index=0,
        )
        bundle = attach_context_source_evidence(
            bundle=bundle,
            standard=standard,
            context=context,
        )
        criterion_results = tuple(
            CriterionResult(
                criterion_id=criterion.criterion_id,
                status=(
                    CriterionStatus.PASS
                    if criterion.source is CriterionSource.MACHINE_CONTRACT
                    else CriterionStatus.NOT_APPLICABLE
                ),
                evidence_ids=(
                    tuple(bundle.criterion_evidence.get(criterion.criterion_id, ()))
                    if criterion.source is CriterionSource.MACHINE_CONTRACT
                    else ()
                ),
                concise_reason=(
                    "Deterministic artifact checks passed."
                    if criterion.source is CriterionSource.MACHINE_CONTRACT
                    else "Semantic evaluation is disabled; external verification owns correctness."
                ),
            )
            for criterion in standard.criteria
        )
        identity = canonical_sha256(
            {
                "mode": self.mode,
                "artifact_manifest_sha256": manifest.manifest_sha256,
                "reference_standard_sha256": standard.reference_standard_sha256,
                "evidence_bundle_sha256": bundle.evidence_bundle_sha256,
                "context_snapshot_sha256": context.context_snapshot_sha256,
            }
        )
        request_sha256 = canonical_sha256(
            {"protocol": "sgar-static-evaluation-v1", "identity": identity}
        )
        response_sha256 = canonical_sha256(
            {
                "status": "static_acceptance",
                "mode": self.mode,
                "semantic_evaluation_performed": False,
            }
        )
        decision = EvaluationDecision(
            verdict=EvaluationVerdict.PASS,
            failure_code=None,
            confidence=1.0,
            criterion_results=criterion_results,
            dimension_scores=EvaluationDimensionScores(),
            critical_issues=(),
            training_label="evaluator_noise",
            reference_standard_sha256=standard.reference_standard_sha256,
            evidence_bundle_sha256=bundle.evidence_bundle_sha256,
            artifact_manifest_sha256=manifest.manifest_sha256,
            context_snapshot_sha256=context.context_snapshot_sha256,
            evaluator_model_resource_id="framework.static_acceptance",
            evaluator_api_model_id="disabled",
            accounting_operation_id=None,
            request_sha256=request_sha256,
            response_sha256=response_sha256,
            review_index=0,
        )
        if self.mode == "silent":
            operation_id = f"{identity}:static"
            self.event_ledger.append_event(
                "evaluation_static_started",
                {
                    "evaluation_operation_id": operation_id,
                    "review_index": 0,
                    "artifact_manifest_sha256": manifest.manifest_sha256,
                    "reference_standard_sha256": standard.reference_standard_sha256,
                    "evidence_bundle_sha256": bundle.evidence_bundle_sha256,
                    "context_snapshot_sha256": context.context_snapshot_sha256,
                    "request_sha256": request_sha256,
                },
            )
            subtask_component = bounded_path_component(
                manifest.artifact_revision.subtask_revision.subtask_id,
                fallback="subtask",
            )
            artifact_name = (
                f"{manifest.artifact_revision.subtask_revision.graph_revision}_"
                f"{subtask_component}_"
                f"{manifest.artifact_revision.subtask_revision.subtask_revision}_static.json"
            )
            self.event_ledger.write_artifact(
                artifact_name,
                {
                    "schema_version": "sgar-static-evaluation-v1",
                    "mode": self.mode,
                    "semantic_evaluation_performed": False,
                    "decision": decision.model_dump(mode="json"),
                    "request_sha256": request_sha256,
                    "response_sha256": response_sha256,
                },
            )
            self.event_ledger.append_event(
                "evaluation_static_finished",
                {
                    "evaluation_operation_id": operation_id,
                    "review_index": 0,
                    "status": "pass",
                    "decision_sha256": decision.decision_sha256,
                    "request_sha256": request_sha256,
                    "response_sha256": response_sha256,
                    "accounting_operation_id": None,
                },
            )
        return EvaluationOutcome(
            status="pass",
            final_decision=decision,
            initial_decision=decision,
            review_decision=None,
            review_triggered=False,
            failure_code=None,
            accounting_operation_ids=(),
        )


__all__ = [
    "EVALUATOR_MAX_TRANSPORT_ATTEMPTS",
    "EVALUATOR_PROMPT_VERSION",
    "EvaluationCoordinator",
    "EvaluationMode",
    "EvaluationEventLedger",
    "EvaluationOutcome",
    "EvaluationPersistenceError",
    "EvaluationRuntimeError",
    "ResolvedEvaluatorModel",
    "StaticEvaluationCoordinator",
    "build_artifact_evidence",
    "attach_context_source_evidence",
    "load_evaluator_policy",
    "normalize_evaluation_mode",
    "resolve_evaluator_model",
]
