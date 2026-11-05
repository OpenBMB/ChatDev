"""Structured recovery evidence and checkpoint extraction.

This module reads only canonical Plan and execution facts.  It never classifies
failures from free-form error text and never reaches back into retrieval.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .executable_plan import ExecutablePlan, SealedPlanCompilationArtifact
from .executors import ExecutionResult
from .pipeline_control import canonical_json_bytes, canonical_sha256
from .recovery_control import (
    CompletedStepCheckpoint,
    RecoveryControlError,
    RecoveryLineage,
    SideEffectEvidence,
    SideEffectStatus,
    StructuredExecutionFailureEvidence,
    executable_step_call_signature,
    executable_step_semantic_sha256,
)


_WINDOWS_PATH = re.compile(r"(?i)(?:[a-z]:[\\/][^\s'\"]+|\\\\[^\s'\"]+)")
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(api[_-]?key|authorization|password|secret|token)\s*[:=]\s*[^\s,;<>\"'\\]+"
)


@dataclass(frozen=True)
class RecoveryExecutionSnapshot:
    failure_evidence: StructuredExecutionFailureEvidence
    checkpoints: tuple[CompletedStepCheckpoint, ...]
    checkpoint_results: Mapping[str, ExecutionResult]
    lineage: RecoveryLineage
    diagnostic_excerpt: str


def sanitize_recovery_diagnostic(value: Any, *, max_bytes: int = 8192) -> tuple[str, int]:
    """Redact bounded diagnostic material without using it for classification."""

    text = str(value or "")
    text, secret_count = _SECRET_ASSIGNMENT.subn(r"\1=<redacted>", text)
    text, path_count = _WINDOWS_PATH.subn("<runtime-path-redacted>", text)
    raw = text.encode("utf-8")[:max_bytes]
    while raw:
        try:
            text = raw.decode("utf-8")
            break
        except UnicodeDecodeError:
            raw = raw[:-1]
    return text if raw else "", secret_count + path_count


def _structured_failure(result: ExecutionResult) -> tuple[str, Mapping[str, Any]]:
    metrics = dict(result.cost_metric or {})
    failure = metrics.get("failure")
    structured = dict(failure) if isinstance(failure, Mapping) else {}
    responsibility = str(
        structured.get("responsibility") or metrics.get("failure_layer") or "framework"
    )
    if responsibility not in {
        "framework",
        "infrastructure",
        "research",
        "budget",
        "interrupted",
    }:
        responsibility = "framework"
    return responsibility, structured


def _call_reference(metrics: Mapping[str, Any]) -> Mapping[str, Any]:
    reference = metrics.get("resource_call_reference")
    return dict(reference) if isinstance(reference, Mapping) else {}


def _side_effect_from_metrics(
    metrics: Mapping[str, Any],
    *,
    dispatched: bool,
) -> SideEffectEvidence:
    reference = _call_reference(metrics)
    started = bool(reference.get("started_event_id"))
    terminal = bool(reference.get("terminal_event_id"))
    audit = metrics.get("execution_audit")
    audit = dict(audit) if isinstance(audit, Mapping) else {}
    network_required = bool(
        audit.get("network_required") or metrics.get("network_required")
    )
    scope_sha256 = metrics.get("sandbox_scope_hash") or audit.get("sandbox_scope_hash")
    # A Controller model is not a direct Resource call. Its fully observed Tool
    # calls still count as dispatched work when classifying the failed frontier.
    if (
        audit.get("controller_tool_observations_complete") is True
        and audit.get("controller_observed_tool_count", 0) > 0
    ):
        dispatched = True
    if started and not terminal:
        status = SideEffectStatus.UNMATCHED_CALL
        dispatched = True
    elif not dispatched and not started:
        status = SideEffectStatus.NOT_DISPATCHED
    elif network_required:
        status = (
            SideEffectStatus.MANIFEST_IDEMPOTENT
            if audit.get("manifest_idempotent") is True
            else SideEffectStatus.UNKNOWN_EXTERNAL
        )
    elif audit.get("writable_scope") or audit.get("sandbox_scope_hash") or scope_sha256:
        status = SideEffectStatus.ISOLATED_WORKSPACE_ONLY
    else:
        status = SideEffectStatus.NONE_OBSERVED
    return SideEffectEvidence(
        status=status,
        dispatched=bool(dispatched or started),
        network_required=network_required,
        writable_scope_sha256=(str(scope_sha256) if scope_sha256 else None),
    )


def _failed_trace_item(trace: Sequence[Any]) -> Mapping[str, Any] | None:
    for item in reversed(trace):
        if isinstance(item, Mapping) and item.get("status") == "failed":
            return item
    return None


def attribute_final_output_contract_failure(
    result: ExecutionResult, *, final_step_id: str, failure_code: str,
) -> bool:
    """Mark a completed final step whose delivered output failed its contract.

    The resource call remains successful in its immutable ledger and in the
    original execution metrics.  Only the application step postcondition fails,
    so recovery must not preserve that invalid output as a completed checkpoint.
    Missing or ambiguous trace identity leaves the trace unchanged.
    """

    return attribute_step_postcondition_failure(
        result, step_id=final_step_id, failure_code=failure_code,
        phase="output_contract",
    )


def attribute_step_postcondition_failure(
    result: ExecutionResult, *, step_id: str, failure_code: str, phase: str,
) -> bool:
    """Invalidate a completed step and its descendants for recovery planning."""

    if phase not in {"output_contract", "source_grounding"}:
        raise ValueError("recovery_postcondition_phase_invalid")
    trace = result.cost_metric.get("application_step_trace")
    if not isinstance(trace, list) or not step_id or not failure_code:
        return False
    matches = [
        index for index, item in enumerate(trace)
        if isinstance(item, Mapping) and item.get("step_id") == step_id
    ]
    if len(matches) != 1:
        return False
    index = matches[0]
    step = trace[index]
    if step.get("status") not in {"success", "reused"}:
        return False
    revised_trace = list(trace)
    revised_step = dict(step)
    revised_step["resource_call_status"] = revised_step["status"]
    revised_step["status"] = "failed"
    revised_step["failure_type"] = failure_code
    revised_step["failure_reason"] = f"{phase}_postcondition_failed"
    revised_step["postcondition_failure_phase"] = phase
    revised_trace[index] = revised_step
    result.cost_metric["application_step_trace"] = revised_trace
    return True


def _descendants(plan: ExecutablePlan, step_id: str) -> tuple[str, ...]:
    children: dict[str, list[str]] = {item.step_id: [] for item in plan.steps}
    for step in plan.steps:
        for parent in step.depends_on:
            children.setdefault(parent, []).append(step.step_id)
    seen: set[str] = set()
    pending = [step_id]
    while pending:
        current = pending.pop(0)
        if current in seen:
            continue
        seen.add(current)
        pending.extend(children.get(current, ()))
    return tuple(item.step_id for item in plan.steps if item.step_id in seen)


def build_recovery_execution_snapshot(
    *,
    artifact: SealedPlanCompilationArtifact,
    execution_result: ExecutionResult,
    diagnostic: Any = "",
    diagnostic_max_bytes: int = 8192,
) -> RecoveryExecutionSnapshot:
    if artifact.status != "success" or artifact.executable_plan is None:
        raise RecoveryControlError("recovery_snapshot_requires_sealed_plan")
    if execution_result.is_success:
        raise RecoveryControlError("recovery_snapshot_requires_failed_execution")
    plan = artifact.executable_plan
    metrics = dict(execution_result.cost_metric or {})
    trace_raw = metrics.get("application_step_trace")
    trace = tuple(trace_raw) if isinstance(trace_raw, list) else ()
    outputs_raw = metrics.get("application_step_outputs")
    outputs = dict(outputs_raw) if isinstance(outputs_raw, Mapping) else {}
    failed_item = _failed_trace_item(trace)
    failed_metrics = (
        dict(failed_item.get("execution_metrics") or {})
        if isinstance(failed_item, Mapping)
        and isinstance(failed_item.get("execution_metrics"), Mapping)
        else metrics
    )
    responsibility, structured = _structured_failure(execution_result)
    failed_step_id = str(failed_item.get("step_id") or "") if failed_item else ""
    failed_step = next(
        (item for item in plan.steps if item.step_id == failed_step_id),
        None,
    )
    call_reference = _call_reference(failed_metrics)
    dispatched = bool(call_reference.get("started_event_id"))
    side_effect = _side_effect_from_metrics(failed_metrics, dispatched=dispatched)
    diagnostic_excerpt, redaction_count = sanitize_recovery_diagnostic(
        diagnostic,
        max_bytes=diagnostic_max_bytes,
    )
    message_sha256 = str(structured.get("message_sha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", message_sha256):
        message_sha256 = canonical_sha256(
            {
                "failure_code": structured.get("failure_code")
                or metrics.get("failure_type")
                or "execution_failure",
                "exception_type": structured.get("exception_type") or "",
            }
        )
    failure_code = str(
        structured.get("failure_code")
        or metrics.get("failure_type")
        or "execution_failure_unstructured"
    )
    failure_stage = str(
        structured.get("failure_stage") or "resource_execution"
    )
    # Runtime-preparation hashes identify dependency environments and may use
    # a prefixed encoding. They are not the ResourceCallRequest identity.
    request_sha256 = call_reference.get("request_sha256")
    failure_evidence = StructuredExecutionFailureEvidence(
        responsibility=responsibility,
        failure_stage=failure_stage,
        failure_code=failure_code,
        exception_type=str(structured.get("exception_type") or ""),
        retryable=bool(structured.get("retryable", False)),
        response_received=bool(structured.get("response_received", False)),
        resource_id=(failed_step.resource_id if failed_step is not None else None),
        entrypoint_id=(failed_step.entrypoint_id if failed_step is not None else None),
        step_id=(failed_step.step_id if failed_step is not None else None),
        resource_call_id=(str(call_reference.get("call_id")) if call_reference.get("call_id") else None),
        request_sha256=(str(request_sha256) if request_sha256 else None),
        plan_sha256=plan.plan_sha256,
        candidate_pool_sha256=plan.candidate_pool_sha256,
        sandbox_scope_sha256=(
            str(failed_metrics.get("sandbox_scope_hash"))
            if failed_metrics.get("sandbox_scope_hash")
            else None
        ),
        message_sha256=message_sha256,
        diagnostic_sha256=canonical_sha256(diagnostic_excerpt),
        diagnostic_bytes=len(diagnostic_excerpt.encode("utf-8")),
        redaction_count=redaction_count,
        side_effect_evidence=side_effect,
    )

    trace_by_step = {
        str(item.get("step_id")): item
        for item in trace
        if isinstance(item, Mapping) and item.get("step_id")
    }
    checkpoints: list[CompletedStepCheckpoint] = []
    checkpoint_results: dict[str, ExecutionResult] = {}
    for step in plan.steps:
        item = trace_by_step.get(step.step_id)
        if not isinstance(item, Mapping) or item.get("status") not in {"success", "reused"}:
            continue
        output = outputs.get(step.output_key)
        execution_metrics = item.get("execution_metrics")
        execution_metrics = (
            dict(execution_metrics) if isinstance(execution_metrics, Mapping) else {}
        )
        reference = _call_reference(execution_metrics)
        if not reference and isinstance(item.get("resource_call_reference"), Mapping):
            reference = dict(item["resource_call_reference"])
        if output is None or not all(
            reference.get(name)
            for name in (
                "call_id",
                "result_sha256",
                "started_event_id",
                "terminal_event_id",
            )
        ):
            continue
        provenance = item.get("output_provenance")
        source_ids: tuple[str, ...] = ()
        if isinstance(provenance, Mapping) and provenance.get("source_id"):
            source_ids = (str(provenance["source_id"]),)
        reused_side_effect = item.get("side_effect_evidence")
        checkpoint = CompletedStepCheckpoint(
            step_id=step.step_id,
            step_semantic_sha256=executable_step_semantic_sha256(step),
            resource_id=step.resource_id,
            entrypoint_id=step.entrypoint_id,
            result_sha256=str(reference["result_sha256"]),
            resource_call_id=str(reference["call_id"]),
            provenance_source_ids=source_ids,
            started_event_id=str(reference["started_event_id"]),
            terminal_event_id=str(reference["terminal_event_id"]),
            side_effect_evidence=(
                SideEffectEvidence.model_validate(reused_side_effect)
                if isinstance(reused_side_effect, Mapping)
                else _side_effect_from_metrics(execution_metrics, dispatched=True)
            ),
        )
        checkpoints.append(checkpoint)
        checkpoint_output = (
            output
            if isinstance(output, str)
            else canonical_json_bytes(output).decode("utf-8")
        )
        checkpoint_results[step.step_id] = ExecutionResult(
            is_success=True,
            output_data=checkpoint_output,
            error_log=None,
            cost_metric={
                **execution_metrics,
                "resource_call_reference": dict(reference),
            },
        )

    # A checkpoint is reusable only when every dynamic predecessor is reusable
    # too. Step semantics contain input bindings by output key, not the prior
    # output bytes. Reusing a downstream side effect while an uncheckpointed
    # Model/Agent predecessor runs again can therefore replay stale material.
    # Keep the maximal dependency-closed subset; independent completed branches
    # remain reusable.
    dependency_closed_ids = {item.step_id for item in checkpoints}
    while True:
        invalid_ids = {
            step.step_id
            for step in plan.steps
            if step.step_id in dependency_closed_ids
            and any(parent not in dependency_closed_ids for parent in step.depends_on)
        }
        if not invalid_ids:
            break
        dependency_closed_ids.difference_update(invalid_ids)
    checkpoints = [
        item for item in checkpoints if item.step_id in dependency_closed_ids
    ]
    checkpoint_results = {
        step_id: result
        for step_id, result in checkpoint_results.items()
        if step_id in dependency_closed_ids
    }

    traced_step_ids = set(trace_by_step)
    never_started = tuple(
        item.step_id for item in plan.steps if item.step_id not in traced_step_ids
    )
    failed_frontier = _descendants(plan, failed_step_id) if failed_step_id else ()
    forbidden: tuple[str, ...] = ()
    if failed_step is not None and side_effect.status is SideEffectStatus.UNKNOWN_EXTERNAL:
        forbidden = (executable_step_call_signature(failed_step),)
    lineage = RecoveryLineage(
        previous_plan_artifact_sha256=artifact.artifact_sha256,
        previous_plan_sha256=plan.plan_sha256,
        failure_evidence_sha256=failure_evidence.evidence_sha256,
        preserved_checkpoint_ids=tuple(item.checkpoint_sha256 for item in checkpoints),
        failed_frontier_step_ids=failed_frontier,
        never_started_step_ids=never_started,
        rerun_forbidden_call_signatures=forbidden,
    )
    return RecoveryExecutionSnapshot(
        failure_evidence=failure_evidence,
        checkpoints=tuple(checkpoints),
        checkpoint_results=checkpoint_results,
        lineage=lineage,
        diagnostic_excerpt=diagnostic_excerpt,
    )


__all__ = [
    "RecoveryExecutionSnapshot",
    "attribute_final_output_contract_failure",
    "attribute_step_postcondition_failure",
    "build_recovery_execution_snapshot",
    "sanitize_recovery_diagnostic",
]
