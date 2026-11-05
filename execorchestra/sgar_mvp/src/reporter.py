"""
S-GAR Entry Layer - Reporter
============================
Generates Markdown reports from planner, router, and execution trace data.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from loguru import logger

from .schema import ExecutionMode, PlannerOutput, RoutingDecision


_MODEL_COST_START = "<!-- SGAR_MODEL_COST_START -->"
_MODEL_COST_END = "<!-- SGAR_MODEL_COST_END -->"
_EXECUTION_START = "<!-- SGAR_RESOURCE_EXECUTION_START -->"
_EXECUTION_END = "<!-- SGAR_RESOURCE_EXECUTION_END -->"
_RECOVERY_START = "<!-- SGAR_RECOVERY_START -->"
_RECOVERY_END = "<!-- SGAR_RECOVERY_END -->"
_EVALUATION_ARTIFACT_START = "<!-- SGAR_EVALUATION_ARTIFACT_START -->"
_EVALUATION_ARTIFACT_END = "<!-- SGAR_EVALUATION_ARTIFACT_END -->"


def _model_cost_markdown(summary: Dict[str, Any]) -> str:
    tokens = summary.get("token_usage") or {}
    budget = summary.get("budget_status") or {}
    lines = [
        _MODEL_COST_START,
        "## Model Cost",
        "",
        f"- Observed model cost (USD): `${summary.get('observed_total_model_cost_usd', 'unknown')}`",
        f"- Provider-reported cost complete: `{bool(summary.get('provider_reported_cost_complete', False))}`",
        f"- Pricing catalog: `{summary.get('pricing_catalog_sha256', 'unknown')}`",
        (
            "- Tokens: "
            f"input=`{tokens.get('input_tokens', 0)}`, "
            f"cache=`{tokens.get('cached_input_tokens', 0)}`, "
            f"output=`{tokens.get('output_tokens', 0)}`"
        ),
        (
            "- Budget: "
            f"mode=`{budget.get('mode', 'unknown')}`, "
            f"warning=`{budget.get('warning_emitted', False)}`, "
            f"limit_reached=`{budget.get('limit_reached', False)}`, "
            f"overshoot_usd=`{budget.get('overshoot_usd', '0.000000000000')}`"
        ),
        (
            "- Incomplete accounting: "
            f"missing_usage=`{summary.get('response_usage_missing_count', 0)}`, "
            f"invalid_usage=`{summary.get('response_usage_invalid_count', 0)}`, "
            f"no_response=`{summary.get('no_response_attempt_count', 0)}`, "
            f"pending=`{summary.get('pending_call_count', 0)}`"
        ),
        "",
        "| Stage | Attempts | Input | Cache | Output | Observed USD |",
        "| ----- | -------- | ----- | ----- | ------ | ------------ |",
    ]
    for stage, values in sorted((summary.get("by_stage") or {}).items()):
        lines.append(
            f"| `{stage}` | {values.get('attempt_count', 0)} | "
            f"{values.get('input_tokens', 0)} | "
            f"{values.get('cached_input_tokens', 0)} | "
            f"{values.get('output_tokens', 0)} | "
            f"{values.get('observed_model_cost_usd', '0.000000000000')} |"
        )
    lines.extend(["", _MODEL_COST_END, ""])
    return "\n".join(lines)


def upsert_model_cost_section(output_path: str, summary: Dict[str, Any]) -> None:
    """Atomically append or replace the non-secret final model-cost section."""

    path = os.path.abspath(output_path)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            existing = handle.read()
    else:
        existing = "# S-GAR Pipeline Execution Report\n\n"
    section = _model_cost_markdown(summary)
    start = existing.find(_MODEL_COST_START)
    end = existing.find(_MODEL_COST_END)
    if start >= 0 and end >= start:
        end += len(_MODEL_COST_END)
        updated = existing[:start].rstrip() + "\n\n" + section + existing[end:].lstrip("\r\n")
    else:
        updated = existing.rstrip() + "\n\n" + section
    temporary = path + ".model-cost.tmp"
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(updated)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _execution_markdown(summary: Dict[str, Any]) -> str:
    lines = [
        _EXECUTION_START,
        "## Resource Execution",
        "",
        f"- Protocol: `{summary.get('schema_version', 'unknown')}`",
        f"- Calls: started=`{summary.get('started_count', 0)}`, terminal=`{summary.get('terminal_count', 0)}`",
        f"- Complete: `{bool(summary.get('complete', False))}`",
        f"- Artifacts registered: `{summary.get('artifact_count', 0)}`",
        f"- Ledger SHA-256: `{summary.get('execution_ledger_sha256', 'unknown')}`",
        f"- Unmatched calls: `{len(summary.get('unmatched_call_ids') or [])}`",
        "",
        "| Status | Count |",
        "| ------ | ----- |",
    ]
    for status, count in sorted((summary.get("by_status") or {}).items()):
        lines.append(f"| `{status}` | {count} |")
    lines.extend(["", _EXECUTION_END, ""])
    return "\n".join(lines)


def upsert_execution_section(output_path: str, summary: Dict[str, Any]) -> None:
    """Atomically append or replace the host-free Resource Runtime summary."""

    path = os.path.abspath(output_path)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            existing = handle.read()
    else:
        existing = "# S-GAR Pipeline Execution Report\n\n"
    section = _execution_markdown(summary)
    start = existing.find(_EXECUTION_START)
    end = existing.find(_EXECUTION_END)
    if start >= 0 and end >= start:
        end += len(_EXECUTION_END)
        updated = (
            existing[:start].rstrip()
            + "\n\n"
            + section
            + existing[end:].lstrip("\r\n")
        )
    else:
        updated = existing.rstrip() + "\n\n" + section
    temporary = path + ".resource-execution.tmp"
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(updated)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _recovery_markdown(summary: Dict[str, Any]) -> str:
    counts = summary.get("event_counts") or {}
    recovery_cost = summary.get("recovery_model_cost") or {}
    lines = [
        _RECOVERY_START,
        "## Recovery",
        "",
        f"- Protocol: `{summary.get('schema_version', 'unknown')}`",
        f"- Complete: `{bool(summary.get('complete', False))}`",
        f"- Terminal operations: `{summary.get('terminal_count', 0)}`",
        f"- Adaptation starts: `{counts.get('plan_adaptation_started', 0)}`",
        f"- Full Generation starts: `{counts.get('full_generation_started', 0)}`",
        f"- Checkpoint reuse events: `{counts.get('checkpoint_reused', 0)}`",
        f"- Temporary Tool generations: `{counts.get('temporary_tool_generated', 0)}`",
        (
            "- Observed Recovery model cost (USD): "
            f"`${recovery_cost.get('observed_model_cost_usd', 'unknown')}`"
        ),
        (
            "- Recovery cost complete: "
            f"`{bool(recovery_cost.get('provider_reported_cost_complete', False))}`"
        ),
        f"- Ledger SHA-256: `{summary.get('recovery_ledger_sha256', 'unknown')}`",
        f"- Host path occurrences: `{len(summary.get('host_path_occurrences') or [])}`",
        f"- Hidden value occurrences: `{len(summary.get('hidden_value_occurrences') or [])}`",
        "",
        _RECOVERY_END,
        "",
    ]
    return "\n".join(lines)


def upsert_recovery_section(output_path: str, summary: Dict[str, Any]) -> None:
    """Atomically append or replace the hash-only recovery summary."""

    path = os.path.abspath(output_path)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            existing = handle.read()
    else:
        existing = "# S-GAR Pipeline Execution Report\n\n"
    section = _recovery_markdown(summary)
    start = existing.find(_RECOVERY_START)
    end = existing.find(_RECOVERY_END)
    if start >= 0 and end >= start:
        end += len(_RECOVERY_END)
        updated = (
            existing[:start].rstrip()
            + "\n\n"
            + section
            + existing[end:].lstrip("\r\n")
        )
    else:
        updated = existing.rstrip() + "\n\n" + section
    temporary = path + ".recovery.tmp"
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(updated)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def upsert_evaluation_artifact_section(
    output_path: str,
    *,
    evaluation_summary: Dict[str, Any],
    artifact_summary: Dict[str, Any],
    context_summary: Dict[str, Any],
) -> None:
    """Atomically report evaluation, lifecycle and Context visibility facts."""

    path = os.path.abspath(output_path)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            existing = handle.read()
    else:
        existing = "# S-GAR Pipeline Execution Report\n\n"
    evaluation_counts = evaluation_summary.get("event_counts") or {}
    artifact_counts = artifact_summary.get("event_counts") or {}
    lines = [
        _EVALUATION_ARTIFACT_START,
        "## Evaluation and Artifact Publication",
        "",
        f"- Evaluation protocol: `{evaluation_summary.get('schema_version', 'unknown')}`",
        f"- Initial evaluations: `{evaluation_counts.get('evaluation_started', 0)}`",
        f"- Evidence reviews: `{evaluation_counts.get('evaluation_review_started', 0)}`",
        f"- Evaluation operations complete: `{bool(evaluation_summary.get('complete', False))}`",
        f"- Artifacts staged: `{artifact_counts.get('artifact_staged', 0)}`",
        f"- Artifacts verified: `{artifact_counts.get('artifact_verified', 0)}`",
        f"- Artifacts committed: `{artifact_counts.get('artifact_committed', 0)}`",
        f"- Artifacts quarantined: `{artifact_counts.get('artifact_quarantined', 0)}`",
        f"- Unmatched evaluation operations: `{len(evaluation_summary.get('unmatched_operations') or [])}`",
        f"- Unmatched artifact operations: `{len(artifact_summary.get('unmatched_artifact_operations') or [])}`",
        f"- Unmatched Context commits: `{len(context_summary.get('unmatched_context_commits') or [])}`",
        f"- Evaluation ledger SHA-256: `{evaluation_summary.get('ledger_sha256', 'unknown')}`",
        f"- Artifact ledger SHA-256: `{artifact_summary.get('ledger_sha256', 'unknown')}`",
        f"- Context ledger SHA-256: `{context_summary.get('ledger_sha256', 'unknown')}`",
        "",
        _EVALUATION_ARTIFACT_END,
        "",
    ]
    section = "\n".join(lines)
    start = existing.find(_EVALUATION_ARTIFACT_START)
    end = existing.find(_EVALUATION_ARTIFACT_END)
    if start >= 0 and end >= start:
        end += len(_EVALUATION_ARTIFACT_END)
        updated = existing[:start].rstrip() + "\n\n" + section + existing[end:].lstrip("\r\n")
    else:
        updated = existing.rstrip() + "\n\n" + section
    temporary = path + ".evaluation-artifact.tmp"
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(updated)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _short(text: str, limit: int = 80) -> str:
    clean = " ".join(str(text).split())
    return clean if len(clean) <= limit else clean[: limit - 3] + "..."


def _context_packet_lines(context_packet: Dict[str, Any]) -> List[str]:
    if not isinstance(context_packet, dict) or not context_packet:
        return []
    contract = context_packet.get("current_output_contract") or {}
    upstream = context_packet.get("upstream_context_availability") or {}
    files = context_packet.get("resolved_local_files") or []
    downstream = context_packet.get("downstream_consumption") or []
    artifact = contract.get("artifact_type") or context_packet.get("current_subtask", {}).get("artifact_type")
    task_stage = context_packet.get("current_subtask", {}).get("task_stage") or "auto"
    ext = contract.get("output_extension") or ""
    produced = contract.get("produced_files") or []
    artifact_handles = context_packet.get("artifact_handles") or []
    validation_handles = context_packet.get("validation_handles") or []
    produced_hints = [
        item.get("path_hint")
        for item in produced
        if isinstance(item, dict) and item.get("path_hint")
    ]
    lines = [
        "    - Context packet: "
        f"stage=`{task_stage}` artifact=`{artifact}` ext=`{ext or 'N/A'}` "
        f"upstream=`{', '.join(upstream.keys()) or 'none'}` "
        f"files=`{len(files)}` handles=`{len(artifact_handles)}` "
        f"validation_handles=`{len(validation_handles)}` downstream=`{len(downstream)}`"
    ]
    if produced_hints:
        lines.append(f"    - Contract produced files: `{', '.join(produced_hints[:8])}`")
    if files:
        visible = []
        for item in files[:5]:
            if isinstance(item, dict):
                marker = "context" if item.get("content_available_as_context") else "path"
                role = item.get("role") or "input"
                origin = item.get("origin") or "unknown"
                visible.append(f"{os.path.basename(str(item.get('path', '')))}:{role}/{origin}/{marker}")
        if visible:
            lines.append(f"    - Resolved local files: `{', '.join(visible)}`")
    return lines


def _session_trace(routing: Dict[str, Any]) -> str:
    session = routing.get("routing_session") if isinstance(routing, dict) else None
    if session is None:
        return "No RoutingSession recorded."

    lines: List[str] = []
    lines.append(f"- Policy expected mode: `{session.policy_expected_mode.value if getattr(session, 'policy_expected_mode', None) else 'N/A'}`")
    lines.append(f"- Actual runtime mode: `{session.actual_runtime_mode.value if getattr(session, 'actual_runtime_mode', None) else (session.final_mode.value if session.final_mode else 'N/A')}`")
    lines.append(f"- Fallback used: `{getattr(session, 'fallback_used', False)}`")
    if getattr(session, "execution_outcome", None):
        outcome = session.execution_outcome
        failure_category = (
            outcome.failure_category.value
            if getattr(outcome, "failure_category", None)
            else "none"
        )
        lines.append(
            f"- Execution outcome: status=`{outcome.status.value}` | "
            f"strictness=`{outcome.strictness.value}` | "
            f"category=`{failure_category}` | "
            f"type=`{outcome.failure_type or 'none'}` | "
            f"graph_replan_allowed=`{outcome.graph_replan_allowed}`"
        )
        if getattr(outcome, "warnings", None):
            warning_text = "; ".join(
                f"{item.get('warning_type', 'warning')}:{_short(item.get('reason', ''), 90)}"
                for item in outcome.warnings[:6]
                if isinstance(item, dict)
            )
            if warning_text:
                lines.append(f"- Balanced warnings: `{warning_text}`")
    if getattr(session, "final_training_label", None):
        lines.append(f"- Final training label: `{session.final_training_label.value}`")
    if session.final_selected_resources:
        selected = ", ".join(
            f"{ref.resource_id}({ref.resource_type.value}; {getattr(ref, 'candidate_origin', 'retrieval')})"
            for ref in session.final_selected_resources
        )
        lines.append(f"- Final selected resources: `{selected}`")
    lines.append("- Attempts:")
    for attempt in session.attempts:
        anchors = ", ".join(ref.resource_id for ref in attempt.anchor_resources) or "N/A"
        candidates = ", ".join(ref.resource_id for ref in attempt.candidate_resources) or "N/A"
        supplemental = [
            ref.resource_id for ref in attempt.candidate_resources
            if getattr(ref, "candidate_origin", "") == "capability_completion"
        ]
        failure = attempt.failure_type or "none"
        reason = _short(attempt.failure_reason or "", 120)
        lines.append(
            f"  - Attempt {attempt.attempt_index}: anchors=`{anchors}` | "
            f"candidates=`{candidates}` | failure=`{failure}` | reason={reason}"
        )
        if getattr(attempt, "typed_candidate_counts", None):
            lines.append(f"    - Typed counts: `{attempt.typed_candidate_counts}`")
        lines.extend(_context_packet_lines(getattr(attempt, "context_packet", {})))
        if getattr(attempt, "candidate_resource_cards", None):
            compact = ", ".join(
                f"{card.get('resource_id')}[{card.get('resource_type')}]"
                for card in attempt.candidate_resource_cards[:10]
                if isinstance(card, dict)
            )
            if compact:
                card_label = (
                    "Candidate cards"
                    if getattr(session, "candidate_pool_snapshot", None) is not None
                    else "Compact cards"
                )
                lines.append(f"    - {card_label}: `{compact}`")
        if supplemental:
            lines.append(
                f"    - Supplemental candidates: `{', '.join(supplemental)}` "
                "(origin=`capability_completion`)"
            )
        decision = attempt.bundle_decision
        if decision and decision.application_plan:
            plan = decision.application_plan
            lines.append(
                f"    - ApplicationPlan: sufficient=`{plan.is_sufficient}` | "
                f"final_output_from=`{plan.final_output_from}` | mode=`{plan.expected_execution_mode.value}`"
            )
            if getattr(plan, "resource_usage", None):
                usage = ", ".join(
                    f"{u.resource_id}:{u.decision}/{u.use_as}"
                    for u in plan.resource_usage[:12]
                )
                lines.append(f"    - Resource usage: `{usage}`")
            for step in plan.steps:
                operation_kind = getattr(step, "operation_kind", None)
                operation_value = getattr(operation_kind, "value", operation_kind) or "auto"
                lines.append(
                    f"    - Step `{step.step_id}`: resource=`{step.resource_id}` | "
                    f"type=`{step.step_type or 'legacy'}` | operation=`{operation_value}` | "
                    f"output=`{step.output_key}` | "
                    f"intent={_short(step.intent, 100)}"
                )
        if attempt.advantage_metrics:
            metrics = attempt.advantage_metrics
            lines.append(
                f"    - Advantage: score=`{metrics.bundle_advantage_score:.4f}` | "
                f"threshold=`{metrics.threshold:.4f}` | "
                f"input_binding=`{metrics.input_binding_coverage:.2f}` | "
                f"output_contract=`{metrics.output_contract_compatibility:.2f}`"
            )
        if getattr(attempt, "execution_step_trace", None):
            validation_targets = []
            execution_steps = []
            source_overlays = []
            for step_trace in attempt.execution_step_trace:
                if not isinstance(step_trace, dict):
                    continue
                resource_id = str(step_trace.get("resource_id") or "")
                step_type = str(step_trace.get("step_type") or "")
                execution_steps.append(
                    f"{step_trace.get('step_id')}:{step_trace.get('operation_kind', step_type)}/"
                    f"{step_trace.get('status', 'unknown')}"
                )
                for overlay in step_trace.get("source_overlays") or []:
                    if isinstance(overlay, dict):
                        source_overlays.append(
                            f"{step_trace.get('step_id')}->{overlay.get('tool_path') or overlay.get('original_workspace_path')}"
                        )
                if step_type != "validate_artifact" and "artifact_validator" not in resource_id:
                    continue
                bindings = step_trace.get("resolved_bindings") or {}
                if not isinstance(bindings, dict):
                    bindings = {}
                validation_targets.append(
                    f"{step_trace.get('step_id')}:{bindings.get('_target_role', 'unknown')}/"
                    f"{bindings.get('_target_sources', 'unknown')}"
                )
            if execution_steps:
                lines.append(f"    - Execution steps: `{', '.join(execution_steps[:10])}`")
            if source_overlays:
                lines.append(f"    - Source overlays: `{', '.join(source_overlays[:8])}`")
            if validation_targets:
                lines.append(f"    - Validation targets: `{', '.join(validation_targets[:8])}`")
            selected_handles = []
            for step_trace in attempt.execution_step_trace:
                if not isinstance(step_trace, dict):
                    continue
                bindings = step_trace.get("resolved_bindings") or {}
                if not isinstance(bindings, dict):
                    continue
                handle_id = bindings.get("_selected_handle_id")
                if handle_id:
                    selected_handles.append(
                        f"{step_trace.get('step_id')}:{bindings.get('_selected_handle_kind', 'handle')}/{handle_id}"
                    )
            if selected_handles:
                lines.append(f"    - Selected handles: `{', '.join(selected_handles[:8])}`")
        if getattr(attempt, "evaluation_result", None):
            eval_result = attempt.evaluation_result
            issues = "; ".join(eval_result.critical_issues) or "none"
            lines.append(
                f"    - Evaluation: verdict=`{eval_result.verdict.value}` | "
                f"failure=`{eval_result.failure_type.value}` | "
                f"confidence=`{eval_result.confidence:.2f}` | "
                f"label=`{eval_result.training_label.value}` | "
                f"profile=`{eval_result.profile_used}` | issues={_short(issues, 160)}"
            )
        if getattr(attempt, "produced_file_status", None):
            compact_status = []
            for item in attempt.produced_file_status[:8]:
                if not isinstance(item, dict):
                    continue
                compact_status.append(
                    f"{item.get('path_hint')}:{item.get('status')}/{item.get('source') or 'none'}"
                )
            if compact_status:
                lines.append(f"    - Required produced files: `{', '.join(compact_status)}`")
        if getattr(attempt, "lineage_warnings", None):
            compact_warnings = []
            for item in attempt.lineage_warnings[:5]:
                if not isinstance(item, dict):
                    continue
                compact_warnings.append(
                    f"{item.get('failure_type', 'lineage_warning')}:{_short(item.get('reason', ''), 90)}"
                )
            if compact_warnings:
                lines.append(f"    - Lineage warnings: `{'; '.join(compact_warnings)}`")
        if getattr(attempt, "repair_attempted", False):
            initial_label = (
                attempt.evaluation_result.training_label.value
                if getattr(attempt, "evaluation_result", None)
                else "N/A"
            )
            final_label = initial_label
            if getattr(attempt, "repair_success", False) and getattr(attempt, "repair_evaluation_result", None):
                final_label = attempt.repair_evaluation_result.training_label.value
            lines.append(
                f"    - Repair: success=`{attempt.repair_success}` | "
                f"failure=`{attempt.repair_failure_type or 'none'}` | "
                f"initial_label=`{initial_label}` | final_label=`{final_label}` | "
                f"reason={_short(attempt.repair_reason or '', 120)}"
            )
            if getattr(attempt, "repair_evaluation_result", None):
                repair_eval = attempt.repair_evaluation_result
                issues = "; ".join(repair_eval.critical_issues) or "none"
                lines.append(
                    f"    - Repair Evaluation: verdict=`{repair_eval.verdict.value}` | "
                    f"failure=`{repair_eval.failure_type.value}` | "
                    f"confidence=`{repair_eval.confidence:.2f}` | "
                    f"label=`{repair_eval.training_label.value}` | issues={_short(issues, 160)}"
                )
        if getattr(attempt, "blocked_resources", None) or getattr(attempt, "blocked_base_models", None):
            lines.append(
                f"    - Infra blocks: resources=`{', '.join(attempt.blocked_resources) or 'none'}` | "
                f"base_models=`{', '.join(attempt.blocked_base_models) or 'none'}`"
            )
    if getattr(session, "blocked_resources", None) or getattr(session, "blocked_base_models", None):
        lines.append(
            f"- Session infra blocks: resources=`{', '.join(session.blocked_resources) or 'none'}` | "
            f"base_models=`{', '.join(session.blocked_base_models) or 'none'}`"
        )
    return "\n".join(lines)


def _retrieval_pool_trace(routing: Dict[str, Any]) -> str:
    """Render the public, hash-bound candidate-pool evidence for one node."""

    if not isinstance(routing, dict):
        return "- No candidate-pool evidence recorded."
    terminal = routing.get("retrieval_terminal_failure")
    if isinstance(terminal, dict):
        return (
            "- Terminal retrieval failure: "
            f"code=`{terminal.get('failure_code', 'unknown')}` | "
            f"responsibility=`{terminal.get('failure_responsibility', 'unknown')}` | "
            f"response_received=`{bool(terminal.get('response_received', False))}`"
        )
    frozen = routing.get("frozen_candidate_pool")
    if frozen is None:
        return "- No candidate-pool evidence recorded."
    payload = (
        frozen.model_dump(mode="json")
        if hasattr(frozen, "model_dump")
        else frozen
    )
    if not isinstance(payload, dict):
        return "- Candidate-pool evidence is unavailable."
    snapshot = payload.get("candidate_pool_snapshot") or {}
    contract = payload.get("contract_projection") or {}
    profile = payload.get("ideal_resource_profile") or {}
    nested_artifact = profile.get("artifact") if isinstance(profile, dict) else None
    artifact = nested_artifact if isinstance(nested_artifact, dict) else profile
    if not isinstance(artifact, dict):
        artifact = {}
    confidence = payload.get("confidence_evidence") or {}
    revision = contract.get("revision") or {}
    lines = [
        "- Revision: "
        f"graph=`{revision.get('graph_revision', 'N/A')}` | "
        f"subtask=`{revision.get('subtask_id', 'N/A')}` | "
        f"subtask_revision=`{revision.get('subtask_revision', 'N/A')}`",
        f"- Candidate pool hash: `{snapshot.get('candidate_pool_sha256', 'N/A')}`",
        f"- Retrieval evidence hash: `{payload.get('retrieval_evidence_sha256', 'N/A')}`",
        f"- HyDE profile hash: `{artifact.get('profile_sha256', 'N/A')}`",
        "- Confidence: "
        f"calibration=`{confidence.get('calibration_status', 'unconfigured')}` | "
        f"quota_coverage=`{confidence.get('quota_coverage', False)}` | "
        f"contract_coverage=`{confidence.get('contract_coverage', False)}` | "
        f"dependency_coverage=`{confidence.get('dependency_coverage', False)}`",
        f"- HyDE accounting reference: `{_short(artifact.get('model_accounting_reference') or 'none', 180)}`",
        f"- Candidate-pool artifact: `{routing.get('candidate_pool_artifact', 'N/A')}`",
        "- Type quotas (base retrieval is not reduced by dependency closure):",
    ]
    for item in payload.get("type_quota_evidence") or []:
        if not isinstance(item, dict):
            continue
        lines.append(
            "  - "
            f"{item.get('resource_type')}: quota=`{item.get('quota')}` | "
            f"eligible=`{item.get('eligible_count')}` | "
            f"base=`{item.get('base_count')}` | final=`{item.get('final_count')}` | "
            f"shortfall=`{item.get('shortfall')}`"
        )
    lines.append(
        "- Dependency closure: "
        f"edges=`{len(payload.get('dependency_edges') or [])}` | "
        f"rejections=`{len(payload.get('dependency_rejections') or [])}` | "
        f"optional_hints=`{len(payload.get('optional_dependency_hints') or [])}`"
    )
    lines.append(
        "- Interpretation: these are frozen **candidates**, not resources selected by the Plan Compiler."
    )
    return "\n".join(lines)


def _plan_compilation_trace(routing: Dict[str, Any]) -> str:
    payload = routing.get("plan_compilation") if isinstance(routing, dict) else None
    if not isinstance(payload, dict):
        return "- Plan compilation has not completed."
    execution_accounting_operations = ", ".join(
        payload.get("execution_accounting_operation_ids") or ()
    )
    lines = [
        f"- Status: `{payload.get('status', 'unknown')}`",
        f"- Artifact hash: `{payload.get('artifact_sha256', 'N/A')}`",
        f"- Candidate pool hash: `{payload.get('candidate_pool_sha256', 'N/A')}`",
        f"- Compiler input hash: `{payload.get('compiler_input_sha256', 'N/A')}`",
        f"- Accounting operation: `{payload.get('accounting_operation_id') or 'none'}`",
        "- Execution accounting operations: "
        f"`{execution_accounting_operations or 'none'}`",
        f"- Transport attempts: `{payload.get('transport_attempts', 0)}`",
        f"- Checked Compiler payloads: `{len(payload.get('payload_checks') or [])}`",
    ]
    failure = payload.get("failure")
    if isinstance(failure, dict):
        lines.append(
            "- Failure: "
            f"responsibility=`{failure.get('responsibility')}` "
            f"layer=`{failure.get('failure_layer')}` "
            f"code=`{failure.get('failure_code')}`"
        )
        diagnostic = failure.get("output_diagnostic")
        if isinstance(diagnostic, dict):
            facts = diagnostic.get("output_reachability") or {}
            lines.append("- Output executability: " + ", ".join(str(x) for x in facts.get("reason_codes", [])))
            lines.append("- Compiler response field: `" + ".".join(str(x) for x in diagnostic.get("response_path", diagnostic.get("path", []))) + "`")
    return "\n".join(lines)


def _recovery_trace(routing: Dict[str, Any]) -> str:
    payload = routing.get("recovery") if isinstance(routing, dict) else None
    if not isinstance(payload, dict):
        return "- Recovery has not completed."
    plan_hashes = ", ".join(payload.get("plan_artifact_sha256s") or ())
    failure_hashes = ", ".join(payload.get("failure_evidence_sha256s") or ())
    temporary_hashes = ", ".join(
        payload.get("temporary_tool_artifact_sha256s") or ()
    )
    return "\n".join(
        [
            f"- Status: `{payload.get('status', 'unknown')}`",
            f"- Plan adaptations: `{payload.get('adaptation_attempts', 0)}`",
            f"- Full Generation attempts: `{payload.get('full_generation_attempts', 0)}`",
            f"- Reused checkpoints: `{payload.get('checkpoint_reused_count', 0)}`",
            f"- Plan artifact hashes: `{plan_hashes or 'none'}`",
            f"- Failure evidence hashes: `{failure_hashes or 'none'}`",
            f"- Temporary Tool artifact hashes: `{temporary_hashes or 'none'}`",
            "- Evaluator handoff is one-way; evaluator feedback is not returned to recovery.",
        ]
    )


def generate_report(
    query: str,
    planner_output: PlannerOutput,
    decisions: List[RoutingDecision],
    output_path: str = "experiment_report.md",
    routing_bundles: Optional[Dict[str, Dict[str, Any]]] = None,
) -> None:
    """Generate a Markdown report with planner, graph, and routing-session traces."""
    routing_bundles = routing_bundles or {}
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# S-GAR Pipeline Execution Report\n\n")
        f.write(f"**Query**: `{query}`\n\n")
        query_diagnostics = routing_bundles.get("_query_diagnostics", {})
        if isinstance(query_diagnostics, dict) and query_diagnostics.get("query_encoding_warning"):
            f.write("**Query encoding warning**: ")
            f.write(
                f"`{query_diagnostics.get('reason', 'likely mojibake')}` "
                f"repair_applied=`{query_diagnostics.get('repair_applied', False)}`\n\n"
            )
        environment_profile = routing_bundles.get("_environment_profile", {})
        if isinstance(environment_profile, dict) and environment_profile:
            f.write("**Environment profile**: ")
            f.write(
                f"docker_cli=`{environment_profile.get('docker_cli_available', environment_profile.get('commands', {}).get('docker', False))}` "
                f"docker_daemon=`{environment_profile.get('docker_daemon_available', environment_profile.get('docker_available', False))}` "
                f"docker_ready=`{environment_profile.get('docker_available', False)}`"
            )
            docker_error = environment_profile.get("docker_error")
            if docker_error:
                f.write(f" reason=`{_short(str(docker_error), 140)}`")
            f.write("\n\n")
        control_model_chain = routing_bundles.get("_control_model_chain", {})
        if isinstance(control_model_chain, dict) and control_model_chain:
            configured = control_model_chain.get("configured_system_model_chain") or []
            available = control_model_chain.get("health_filtered_system_model_chain") or []
            skipped = control_model_chain.get("skipped_control_models") or []
            f.write("**Control model chain**: ")
            f.write(
                f"configured=`{', '.join(str(item) for item in configured)}` "
                f"available=`{', '.join(str(item) for item in available)}`"
            )
            if skipped:
                skipped_text = "; ".join(
                    f"{item.get('model_id')}:{item.get('reason')}"
                    for item in skipped[:6]
                    if isinstance(item, dict)
                )
                f.write(f" skipped=`{_short(skipped_text, 180)}`")
            f.write("\n\n")
        planner_parse_metadata = routing_bundles.get("_planner_parse_metadata", {})
        if isinstance(planner_parse_metadata, dict) and planner_parse_metadata:
            warnings = planner_parse_metadata.get("planner_schema_warnings") or []
            warning_text = ", ".join(str(item) for item in warnings[:6]) if isinstance(warnings, list) else str(warnings)
            f.write("**Planner parse**: ")
            f.write(
                f"mode=`{planner_parse_metadata.get('parse_mode', 'unknown')}` "
                f"requested=`{planner_parse_metadata.get('requested_response_format', 'unknown')}` "
                f"attempt=`{planner_parse_metadata.get('attempt', 'N/A')}`"
            )
            selected_control_model = planner_parse_metadata.get("selected_control_model")
            if selected_control_model:
                f.write(f" control_model=`{selected_control_model}`")
            if warning_text:
                f.write(f" warnings=`{_short(warning_text, 180)}`")
            f.write("\n\n")
        replan_history = routing_bundles.get("_replan_history", [])
        if isinstance(replan_history, list) and replan_history:
            f.write("## Replan History\n\n")
            for item in replan_history:
                if not isinstance(item, dict):
                    continue
                subtasks = item.get("subtasks") or []
                summary = ", ".join(
                    f"{st.get('id')}:{st.get('artifact_type')}{st.get('output_extension') or ''}"
                    for st in subtasks[:12]
                    if isinstance(st, dict)
                )
                f.write(
                    f"- replan_count=`{item.get('replan_count')}` "
                    f"protected=`{', '.join(item.get('protected_contracts') or []) or 'none'}` "
                    f"subtasks=`{summary}`\n"
                )
            f.write("\n")

        f.write("## 1. Task Decomposition (Planner)\n\n")
        f.write("| ID | Role | Description | Artifact | Dependencies |\n")
        f.write("| -- | ---- | ----------- | -------- | ------------ |\n")
        for st in planner_output.subtasks:
            deps = ", ".join(st.depends_on) if st.depends_on else "none"
            f.write(
                f"| `{st.id}` | **{st.role}** | "
                f"{_short(st.description, 70)} | `{st.artifact_type.value}` | {deps} |\n"
            )

        f.write("\n## 2. Orchestration Graph\n\n")
        f.write("```mermaid\ngraph TD\n")
        f.write(f'    Q["{_short(query, 30)}"] --> P[SGAR Planner]\n')
        for i, st in enumerate(planner_output.subtasks):
            dec = decisions[i] if i < len(decisions) else None
            f.write(f'    P --> ST{i}["[{st.role}]<br>{st.id}"]\n')
            if dec is None:
                f.write(f'    ST{i} --> R{i}(("unrouted"))\n')
                continue
            sim = dec.metrics.similarity
            ap = dec.metrics.advantage
            res_id = dec.resource.id
            frozen_candidate = bool(
                isinstance(routing_bundles.get(st.id), dict)
                and routing_bundles.get(st.id, {}).get("frozen_candidate_pool") is not None
            )
            label = (
                "Candidate (not selected)"
                if frozen_candidate
                else ("Bypass" if dec.mode == ExecutionMode.BYPASS else "Routed")
            )
            f.write(f'    ST{i} --> D{i}{{"Sim:{sim:.2f}<br>Ap:{ap:.1f}"}}\n')
            f.write(f'    D{i} -- "{label}" --> R{i}(("{res_id}"))\n')
        for i, st in enumerate(planner_output.subtasks):
            for dep in st.depends_on:
                dep_idx = next(
                    (j for j, s in enumerate(planner_output.subtasks) if s.id == dep),
                    None,
                )
                if dep_idx is not None:
                    f.write(f"    R{dep_idx} -.-> ST{i}\n")
        f.write("```\n\n")

        f.write("## 3. Retrieval & Candidate Pool\n\n")
        for st in planner_output.subtasks:
            f.write(f"### {st.id}\n\n")
            f.write(_retrieval_pool_trace(routing_bundles.get(st.id, {})))
            f.write("\n\n")

        f.write("## 4. Sealed Executable Plan Compilation\n\n")
        for st in planner_output.subtasks:
            f.write(f"### {st.id}\n\n")
            f.write(_plan_compilation_trace(routing_bundles.get(st.id, {})))
            f.write("\n\n")

        f.write("## 5. Compatibility Candidate Projection\n\n")
        f.write(
            "This compatibility view reports one retrieved candidate for older visualizations; "
            "it is not the Plan Compiler's selected resource.\n\n"
        )
        for i, st in enumerate(planner_output.subtasks):
            if i >= len(decisions):
                f.write(f"- **{st.id}** -> `unrouted`\n")
                continue
            dec = decisions[i]
            f.write(
                f"- **{st.id}** -> candidate_mode=`{dec.mode.value}` -> "
                f"candidate=`{dec.resource.id}`\n"
            )

        f.write("\n## 6. Runtime RoutingSession Trace\n\n")
        carried_over = routing_bundles.get("_carried_over_artifacts", {})
        if carried_over:
            f.write("### Carried-over Artifacts\n\n")
            for task_id, contract in carried_over.items():
                f.write(f"- `{task_id}`: {_short(contract, 160)}\n")
            f.write("\n")
        for st in planner_output.subtasks:
            f.write(f"### {st.id}\n\n")
            f.write(_session_trace(routing_bundles.get(st.id, {})))
            f.write("\n\n")
            f.write("#### Recovery\n\n")
            f.write(_recovery_trace(routing_bundles.get(st.id, {})))
            f.write("\n\n")
            evaluation = routing_bundles.get(st.id, {}).get("evaluation") or {}
            f.write("#### Evaluation and Artifact Lifecycle\n\n")
            if evaluation:
                f.write(
                    f"- status=`{evaluation.get('status', 'unknown')}` "
                    f"review=`{evaluation.get('review_triggered', False)}` "
                    f"failure=`{evaluation.get('failure_code') or 'none'}`\n"
                )
                f.write(
                    f"- staged=`{evaluation.get('staged_manifest_sha256') or 'none'}` "
                    f"verified=`{evaluation.get('verified_manifest_sha256') or 'none'}` "
                    f"committed=`{evaluation.get('committed_manifest_sha256') or 'none'}` "
                    f"quarantined=`{evaluation.get('quarantine_sha256') or 'none'}`\n"
                )
            else:
                f.write("- not_run\n")
            f.write("\n")

    logger.info("[Reporter] Report saved -> {}", os.path.basename(output_path))
    cost_summary = routing_bundles.get("_model_cost_summary")
    if isinstance(cost_summary, dict):
        upsert_model_cost_section(output_path, cost_summary)
    execution_summary = routing_bundles.get("_execution_summary")
    if isinstance(execution_summary, dict):
        upsert_execution_section(output_path, execution_summary)
    recovery_summary = routing_bundles.get("_recovery_summary")
    if isinstance(recovery_summary, dict):
        upsert_recovery_section(output_path, recovery_summary)
    evaluation_summary = routing_bundles.get("_evaluation_summary")
    artifact_summary = routing_bundles.get("_artifact_summary")
    context_summary = routing_bundles.get("_context_summary")
    if all(
        isinstance(item, dict)
        for item in (evaluation_summary, artifact_summary, context_summary)
    ):
        upsert_evaluation_artifact_section(
            output_path,
            evaluation_summary=evaluation_summary,
            artifact_summary=artifact_summary,
            context_summary=context_summary,
        )
