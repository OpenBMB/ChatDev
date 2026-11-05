"""Production recovery state machine over sealed Plans and a frozen pool."""

from __future__ import annotations

import asyncio
import json
import re
import threading
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal, Mapping, Protocol, Sequence, cast

from pydantic import ValidationError

from .executable_plan import SealedPlanCompilationArtifact
from .executors import ExecutionResult
from .model_request_budget import (
    ModelTimeBudgetError,
    current_attempt_timeout,
    model_recovery_routes_remaining,
)
from .pipeline_control import canonical_sha256, subtask_revision_identity_sha256
from .recovery_control import (
    CompletedStepCheckpoint,
    RecoveryControlError,
    RecoveryEventLedger,
    RecoveryOperationRef,
    RecoveryPersistenceError,
    RecoveryPolicy,
    StructuredExecutionFailureEvidence,
)
from .recovery_runtime import RecoveryExecutionSnapshot, build_recovery_execution_snapshot
from .resource_runtime import (
    ProcessFailureDiagnostic,
    ResourceCallResult,
    ResourceCallStatus,
    resource_result_to_execution_result,
)
from .terminal_failure import (
    TerminalFailureEnvelope,
    terminal_failure_from_execution_result,
)


RECOVERY_CONTROLLER_PROTOCOL = "sgar-recovery-runtime-v1"
_STRUCTURED_FAILURE_CODE = re.compile(r"^[a-z][a-z0-9_]{2,127}$")


class RecoveryControllerError(RecoveryControlError):
    pass


class PlanCompilationPort(Protocol):
    async def compile_initial(self) -> SealedPlanCompilationArtifact: ...

    async def adapt(
        self,
        *,
        previous_artifact: SealedPlanCompilationArtifact,
        snapshot: RecoveryExecutionSnapshot,
        plan_revision: int,
    ) -> SealedPlanCompilationArtifact: ...


class PlanExecutionPort(Protocol):
    async def execute(
        self,
        *,
        artifact: SealedPlanCompilationArtifact,
        checkpoints: Sequence[CompletedStepCheckpoint] = (),
        checkpoint_results: Mapping[str, ExecutionResult] | None = None,
    ) -> ExecutionResult: ...


class FullGenerationPort(Protocol):
    async def generate(
        self,
        *,
        compiler_failure_hashes: Sequence[str],
        execution_failures: Sequence[StructuredExecutionFailureEvidence],
        diagnostic_excerpts: Sequence[str],
        checkpoints: Sequence[CompletedStepCheckpoint],
    ) -> ResourceCallResult: ...


@dataclass(frozen=True)
class PreparedTemporaryToolExecution:
    checkpoint: CompletedStepCheckpoint
    checkpoint_result: ExecutionResult
    artifact_sha256: str


class TemporaryToolPort(Protocol):
    async def prepare(
        self,
        *,
        artifact: SealedPlanCompilationArtifact,
        snapshot: RecoveryExecutionSnapshot,
    ) -> PreparedTemporaryToolExecution | ExecutionResult | None: ...


@dataclass(frozen=True)
class RecoveryTerminalResult:
    protocol: str
    status: Literal[
        "evaluating",
        "framework_failure",
        "infrastructure_failure",
        "research_failure",
        "budget_failure",
        "interrupted",
    ]
    execution_result: ExecutionResult
    final_plan_artifact: SealedPlanCompilationArtifact | None
    operation_ref: RecoveryOperationRef | None
    plan_artifact_sha256s: tuple[str, ...]
    failure_evidence_sha256s: tuple[str, ...]
    adaptation_attempts: int
    full_generation_attempts: int
    checkpoint_reused_count: int
    temporary_tool_artifact_sha256s: tuple[str, ...]
    model_response_success: bool = False
    artifact_ready_for_evaluation: bool = False
    evaluation_eligible: bool = False
    terminal_failure: TerminalFailureEnvelope | None = None
    primary_failure: TerminalFailureEnvelope | None = None
    recovery_outcome: str | None = None
    causal_chain: tuple[str, ...] = ()


def _failure_execution_result(
    *,
    responsibility: str,
    failure_stage: str,
    failure_code: str,
    message_sha256: str | None = None,
    exception_type: str = "",
) -> ExecutionResult:
    normalized = (
        responsibility
        if responsibility in {"framework", "infrastructure", "research", "budget", "interrupted"}
        else "framework"
    )
    message_hash = message_sha256 or canonical_sha256(
        {"failure_stage": failure_stage, "failure_code": failure_code}
    )
    return ExecutionResult(
        is_success=False,
        output_data="",
        error_log=failure_code,
        cost_metric={
            "failure_type": failure_code,
            "failure_layer": normalized,
            "failure": {
                "responsibility": normalized,
                "failure_stage": failure_stage,
                "failure_code": failure_code,
                "exception_type": exception_type,
                "retryable": False,
                "response_received": False,
                "message_sha256": message_hash,
            },
        },
    )


def _exception_message_sha256(exc: Exception) -> str:
    """Fingerprint an exception without persisting its potentially sensitive text."""

    try:
        message = str(exc)
    except Exception:
        message = ""
    return canonical_sha256(
        {"exception_type": type(exc).__name__, "message": message}
    )


def _validation_issue_locations(exc: Exception) -> tuple[str, ...]:
    """Keep only Pydantic field locations, never rejected input or messages."""

    if not isinstance(exc, ValidationError):
        return ()
    locations = []
    for issue in exc.errors(include_input=False, include_context=False, include_url=False):
        location = ".".join(str(part) for part in issue.get("loc", ()))
        if location and len(location) <= 160:
            locations.append(location)
    return tuple(sorted(set(locations))[:8])


def _exception_failure_code(exc: Exception) -> str:
    """Return only an explicitly structured, path-free framework error code."""

    candidate = getattr(exc, "code", None) or getattr(exc, "error_code", None)
    if isinstance(candidate, str):
        # Some shared safety validators append a private locator after a colon
        # (for example ``recovery_projection_unsafe:$.input``).  Keep only the
        # stable protocol code; the complete exception remains represented by
        # the separately stored message hash.
        stable_candidate = candidate.split(":", 1)[0]
        if _STRUCTURED_FAILURE_CODE.fullmatch(stable_candidate):
            return stable_candidate
    return "recovery_controller_internal_error"


def _compiler_failure_status(
    artifact: SealedPlanCompilationArtifact,
) -> tuple[str, str, str, str]:
    failure = artifact.failure
    if failure is None:
        return (
            "framework",
            "plan_compilation",
            "plan_compilation_terminal_without_failure",
            canonical_sha256("plan_compilation_terminal_without_failure"),
        )
    return (
        failure.responsibility,
        failure.failure_stage,
        failure.failure_code,
        failure.message_sha256,
    )


def _execution_responsibility(result: ExecutionResult) -> str:
    metrics = dict(result.cost_metric or {})
    structured = metrics.get("failure")
    responsibility = (
        structured.get("responsibility")
        if isinstance(structured, Mapping)
        else metrics.get("failure_layer")
    )
    normalized = str(responsibility or "framework")
    if normalized not in {
        "framework",
        "infrastructure",
        "research",
        "budget",
        "interrupted",
    }:
        return "framework"
    return normalized


_RECOMPOSABLE_PROVIDER_FAILURES = frozenset({
    "provider_timeout",
    "provider_connection_error",
    "provider_rate_limit",
    "provider_server_error",
    "provider_model_unavailable",
})


def _controller_process_failure_allows_plan_adaptation(
    result: ExecutionResult,
    evidence: StructuredExecutionFailureEvidence,
    summary: Mapping[str, Any],
) -> bool:
    """Admit one sealed re-plan for a fully observed generated-process failure.

    The local Controller loop cannot repair an upstream generated payload when
    its writer inputs were sealed from a previous step.  A response-backed,
    bounded process diagnostic is enough to recompile that failed frontier.
    Unknown effects, missing terminal evidence, and all framework or transport
    failures remain terminal.  The recovery state machine still stops a second
    attempt at the same callable failure boundary.
    """

    terminal = summary.get("terminal_failure")
    if not isinstance(terminal, Mapping):
        return False
    original = terminal.get("original_resource_failure")
    if not isinstance(original, Mapping):
        return False
    if not (
        evidence.responsibility == "research"
        and evidence.failure_stage == "resource_execution"
        and evidence.failure_code == "resource_process_failed"
        and bool(evidence.response_received)
        and terminal.get("responsibility") == "research"
        and terminal.get("failure_stage") == "resource_execution"
        and terminal.get("failure_code") == "resource_process_failed"
        and terminal.get("resource_dispatched") is True
        and terminal.get("resource_outcome") == "result_received"
        and terminal.get("evidence_incomplete") is False
        and original.get("responsibility") == "research"
        and original.get("failure_stage") == "resource_execution"
        and original.get("failure_code") == "resource_process_failed"
        and original.get("response_received") is True
    ):
        return False
    try:
        diagnostic_envelope = json.loads(str(result.error_log or ""))
        if diagnostic_envelope.get("failure_code") != "resource_process_failed":
            return False
        ProcessFailureDiagnostic.model_validate(
            diagnostic_envelope.get("process_diagnostic")
        )
    except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
        return False
    return True


def _execution_failure_allows_plan_adaptation(
    result: ExecutionResult,
    snapshot: RecoveryExecutionSnapshot,
) -> bool:
    """Recompose unfinished work before hidden effects or after fully observed local work."""

    evidence = snapshot.failure_evidence
    summary = (result.cost_metric or {}).get("controller_session_summary")
    if isinstance(summary, Mapping):
        try:
            controller_tool_call_count = int(summary.get("tool_call_count") or 0)
        except (TypeError, ValueError):
            return False
    else:
        controller_tool_call_count = 0
    audit = (result.cost_metric or {}).get("execution_audit")
    observed_local_work = bool(
        controller_tool_call_count > 0
        and isinstance(summary, Mapping)
        and summary.get("evidence_incomplete") is False
        and isinstance(audit, Mapping)
        and audit.get("controller_tool_observations_complete") is True
        and audit.get("controller_observed_tool_count") == controller_tool_call_count
        and evidence.side_effect_evidence.status.value in {
            "none_observed", "isolated_workspace_only", "manifest_idempotent",
        }
    )
    if evidence.responsibility == "research":
        # Local correction belongs to the Controller first. Once it terminates,
        # fully observed local results may inform a changed unfinished route;
        # the existing checkpoint and repeat-boundary rules still apply.
        return controller_tool_call_count == 0 or (
            _controller_process_failure_allows_plan_adaptation(
                result, evidence, summary,
            )
        ) or (
            observed_local_work and evidence.failure_code in {
                "controller_finalization_evidence_unsatisfied",
                "controller_no_progress",
                "controller_tool_call_repeat_limit",
                "controller_required_operation_unsatisfied",
                "controller_provider_truncation",
            }
        )
    if evidence.responsibility != "infrastructure":
        return False
    if evidence.failure_code not in _RECOMPOSABLE_PROVIDER_FAILURES:
        return False
    # ``retryable`` describes whether the same transport request may be sent
    # again.  By the time recovery sees this failure, the bounded per-resource
    # transport attempts are already exhausted.  A known Provider failure may
    # still be recomposed onto a different frozen Model/Agent route, provided
    # the failed frontier was never dispatched and no controller Tool ran.
    if observed_local_work:
        return True
    if evidence.side_effect_evidence.status.value != "not_dispatched":
        return False
    if controller_tool_call_count > 0:
        return False
    return True


def _declared_failure_reason_identity(
    evidence: StructuredExecutionFailureEvidence, diagnostic_excerpt: str,
) -> dict[str, str]:
    """Use only stable reason codes from the sealed native failure diagnostic.

    The Resource Runtime already validates the native payload before forwarding
    it. Bind this projection to the recovery snapshot; varying URLs, timestamps,
    messages, or plan wording must not buy another adaptation of the same error.
    """
    if not diagnostic_excerpt or canonical_sha256(diagnostic_excerpt) != getattr(
        evidence, "diagnostic_sha256", None
    ):
        return {}
    try:
        diagnostic = json.loads(diagnostic_excerpt)
    except (TypeError, ValueError):
        return {}
    if not isinstance(diagnostic, Mapping) or diagnostic.get(
        "failure_code"
    ) != "declared_result_status_failure":
        return {}
    native = diagnostic.get("native_result")
    if not isinstance(native, Mapping):
        return {}
    for field in ("reason_code", "error_code"):
        code = native.get(field)
        if isinstance(code, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_.:-]{1,127}", code):
            return {"native_failure_reason_field": field, "native_failure_reason_code": code}
    return {}


def _execution_failure_boundary_signature(
    evidence: StructuredExecutionFailureEvidence,
    *,
    cost_metric: Mapping[str, Any] | None = None,
    diagnostic_excerpt: str = "",
) -> str:
    """Identify the failed capability boundary independently of plan wording.

    A changed plan or step identifier is not evidence of a new execution route.
    Resource and entrypoint identity remain part of the signature so recovery
    may still switch to a genuinely different selected capability.

    For a controller session, the outer failed step is the selected Model or
    Agent.  Its V2 summary names the actual callable frontier that failed.  Use
    that callable identity when present so swapping the controller model does
    not disguise another attempt through the same failed Tool operation.  A
    fully observed generated-process failure also includes its diagnostic hash:
    the same traceback is terminal, while a materially new failure may use the
    policy's remaining bounded adaptation.
    """

    metrics = cost_metric if isinstance(cost_metric, Mapping) else {}
    summary = metrics.get("controller_session_summary")
    terminal = (
        summary.get("terminal_failure")
        if isinstance(summary, Mapping)
        else None
    )
    if isinstance(terminal, Mapping) and terminal.get("callable_id"):
        original = terminal.get("original_resource_failure")
        original_failure = original if isinstance(original, Mapping) else {}
        failure_code = str(
            original_failure.get("failure_code")
            or terminal.get("failure_code")
            or evidence.failure_code
        )
        boundary = {
            "responsibility": (
                original_failure.get("responsibility")
                or terminal.get("responsibility")
                or evidence.responsibility
            ),
            "failure_stage": (
                original_failure.get("failure_stage")
                or terminal.get("failure_stage")
                or evidence.failure_stage
            ),
            "failure_code": failure_code,
            "controller_callable_id": str(terminal["callable_id"]),
        }
        if failure_code == "declared_result_status_failure":
            boundary.update(_declared_failure_reason_identity(evidence, diagnostic_excerpt))
        if failure_code.lower() == "resource_process_failed":
            diagnostic_sha256 = str(
                getattr(evidence, "diagnostic_sha256", "") or ""
            )
            if diagnostic_sha256:
                boundary["process_diagnostic_sha256"] = diagnostic_sha256
        return canonical_sha256(boundary)

    boundary = {
        "responsibility": evidence.responsibility,
        "failure_stage": evidence.failure_stage,
        "failure_code": evidence.failure_code,
        "resource_id": evidence.resource_id,
        "entrypoint_id": evidence.entrypoint_id,
    }
    if evidence.failure_code == "declared_result_status_failure":
        boundary.update(_declared_failure_reason_identity(evidence, diagnostic_excerpt))
    if str(evidence.failure_code).lower() == "resource_process_failed":
        diagnostic_sha256 = str(
            getattr(evidence, "diagnostic_sha256", "") or ""
        )
        if diagnostic_sha256:
            boundary["process_diagnostic_sha256"] = diagnostic_sha256
    return canonical_sha256(boundary)


def _artifact_adaptation_kind(artifact: SealedPlanCompilationArtifact) -> str | None:
    validation = artifact.validation_audit
    if not isinstance(validation, Mapping):
        return None
    adaptation = validation.get("adaptation")
    if not isinstance(adaptation, Mapping):
        return None
    kind = adaptation.get("adaptation_kind")
    return str(kind) if kind else None


def _causal_failure_codes(
    primary_failure: TerminalFailureEnvelope | None,
    recovery_outcome: str | None,
    terminal_failure: TerminalFailureEnvelope | None,
) -> tuple[str, ...]:
    chain: list[str] = []
    for item in (
        primary_failure.failure_code if primary_failure is not None else None,
        recovery_outcome if recovery_outcome not in {None, "none"} else None,
        terminal_failure.failure_code if terminal_failure is not None else None,
    ):
        if item and item not in chain:
            chain.append(item)
    return tuple(chain)


class RecoveryController:
    """Run sealed compilation and bounded same-pool adaptations.

    Production uses ``strict_plan_only`` and can never enter temporary-Tool or
    Full Generation recovery. ``legacy_extended`` remains an explicit audit
    compatibility mode for historical records and tests.
    """

    def __init__(
        self,
        *,
        run_id: str,
        policy: RecoveryPolicy,
        ledger: RecoveryEventLedger,
        compilation_port: PlanCompilationPort,
        execution_port: PlanExecutionPort,
        full_generation_port: FullGenerationPort | None,
        temporary_tool_port: TemporaryToolPort | None = None,
    ) -> None:
        self.run_id = str(run_id).strip()
        if not self.run_id:
            raise RecoveryControllerError("recovery_run_id_missing")
        if ledger.run_id != self.run_id:
            raise RecoveryControllerError("recovery_ledger_run_identity_mismatch")
        self.policy = policy
        self.ledger = ledger
        self.compilation_port = compilation_port
        self.execution_port = execution_port
        self.full_generation_port = full_generation_port
        self.temporary_tool_port = temporary_tool_port
        if (
            self.policy.sealed_runtime_mode == "legacy_extended"
            and self.full_generation_port is None
        ):
            raise RecoveryControllerError("legacy_full_generation_port_missing")
        self._condition = threading.Condition(threading.RLock())
        self._cache: dict[str, RecoveryTerminalResult] = {}
        self._inflight: set[str] = set()

    async def execute_subtask(
        self,
        *,
        subtask: Any,
        routing_session: Any,
        frozen_candidate_pool: Any,
        compiler_context: Any,
        resource_definitions: Mapping[str, Any],
        runtime_capabilities: Any,
        pricing_catalog: Any,
        execution_port: PlanExecutionPort | None = None,
    ) -> RecoveryTerminalResult:
        del compiler_context, resource_definitions, runtime_capabilities, pricing_catalog
        active_execution_port = execution_port or self.execution_port
        snapshot = frozen_candidate_pool.candidate_pool_snapshot
        revision = snapshot.revision
        candidate_hash = snapshot.candidate_pool_sha256
        session_snapshot = getattr(routing_session, "candidate_pool_snapshot", None)
        if session_snapshot is not None and (
            session_snapshot.candidate_pool_sha256 != candidate_hash
            or session_snapshot.revision != revision
        ):
            raise RecoveryControllerError("recovery_candidate_session_mismatch")
        subtask_id = str(getattr(subtask, "id", "") or "")
        if subtask_id != revision.subtask_id:
            raise RecoveryControllerError("recovery_subtask_revision_mismatch")
        identity_key = canonical_sha256(
            {
                "run_id": self.run_id,
                "revision_sha256": subtask_revision_identity_sha256(revision),
                "candidate_pool_sha256": candidate_hash,
                "recovery_policy_sha256": self.policy.policy_sha256,
            }
        )
        claimed, cached = await asyncio.to_thread(
            self._claim_identity,
            identity_key,
        )
        if not claimed:
            if cached is None:
                raise RecoveryControllerError("recovery_identity_cache_missing")
            return cached
        try:
            result = await self._execute_once(
                subtask=subtask,
                revision=revision,
                candidate_pool_sha256=candidate_hash,
                execution_port=active_execution_port,
            )
            with self._condition:
                self._cache[identity_key] = result
            return result
        finally:
            with self._condition:
                self._inflight.discard(identity_key)
                self._condition.notify_all()

    def _claim_identity(
        self,
        key: str,
    ) -> tuple[bool, RecoveryTerminalResult | None]:
        with self._condition:
            while key in self._inflight:
                self._condition.wait()
            cached = self._cache.get(key)
            if cached is not None:
                return False, cached
            self._inflight.add(key)
            return True, None

    def _event(self, event_type: str, payload: Mapping[str, Any]) -> None:
        self.ledger.append_event(event_type, payload)

    def _operation_ref(
        self,
        *,
        revision: Any,
        candidate_pool_sha256: str,
        initial_artifact_sha256: str,
        current_plan_revision: int,
        adaptation_count: int,
        full_generation_count: int,
    ) -> RecoveryOperationRef:
        return RecoveryOperationRef(
            run_id=self.run_id,
            revision=revision,
            candidate_pool_sha256=candidate_pool_sha256,
            initial_plan_artifact_sha256=initial_artifact_sha256,
            current_plan_revision=current_plan_revision,
            adaptation_count=adaptation_count,
            full_generation_count=full_generation_count,
            recovery_policy_sha256=self.policy.policy_sha256,
        )

    async def _execute_once(
        self,
        *,
        subtask: Any,
        revision: Any,
        candidate_pool_sha256: str,
        execution_port: PlanExecutionPort,
    ) -> RecoveryTerminalResult:
        plan_artifacts: list[str] = []
        evidence_hashes: list[str] = []
        compiler_failure_hashes: list[str] = []
        diagnostic_excerpts: list[str] = []
        checkpoints: tuple[CompletedStepCheckpoint, ...] = ()
        checkpoint_results: dict[str, ExecutionResult] = {}
        temporary_artifacts: list[str] = []
        adaptation_count = 0
        full_generation_count = 0
        progress = {"adaptation_count": 0, "full_generation_count": 0}
        operation_ref: RecoveryOperationRef | None = None
        primary_failure: TerminalFailureEnvelope | None = None
        current: SealedPlanCompilationArtifact | None = None
        try:
            self._event(
                "recovery_started",
                {
                    "revision": revision.model_dump(mode="json"),
                    "recovery_identity_sha256": subtask_revision_identity_sha256(
                        revision
                    ),
                    "candidate_pool_sha256": candidate_pool_sha256,
                    "recovery_policy_sha256": self.policy.policy_sha256,
                },
            )
            # Each active phase uses the live request window. The timing policy
            # already reserves time for the next model-capable phase; possible
            # later adaptations must not reserve that same time a second time.
            with model_recovery_routes_remaining(1):
                initial = await self.compilation_port.compile_initial()
            plan_artifacts.append(initial.artifact_sha256)
            self._event(
                "initial_plan_compilation_finished",
                {
                    "status": initial.status,
                    "plan_artifact_sha256": initial.artifact_sha256,
                    "candidate_pool_sha256": initial.candidate_pool_sha256,
                    "accounting_operation_id": initial.accounting_operation_id,
                },
            )
            if initial.candidate_pool_sha256 != candidate_pool_sha256:
                raise RecoveryControllerError("recovery_initial_candidate_hash_mismatch")
            operation_ref = self._operation_ref(
                revision=revision,
                candidate_pool_sha256=candidate_pool_sha256,
                initial_artifact_sha256=initial.artifact_sha256,
                current_plan_revision=0,
                adaptation_count=0,
                full_generation_count=0,
            )
            if initial.status != "success" or initial.executable_plan is None:
                responsibility, stage, code, message_hash = _compiler_failure_status(initial)
                initial_failure_result = _failure_execution_result(
                    responsibility=responsibility,
                    failure_stage=stage,
                    failure_code=code,
                    message_sha256=message_hash,
                )
                primary_failure = terminal_failure_from_execution_result(
                    initial_failure_result,
                    run_id=self.run_id,
                    graph_revision=revision.graph_revision,
                    subtask_id=revision.subtask_id,
                    subtask_revision=revision.subtask_revision,
                    plan_revision=initial.plan_revision.plan_revision,
                )
                compiler_failure_hashes.append(message_hash)
                self._event(
                    "recovery_decision",
                    {
                        "decision": (
                            "full_generation"
                            if responsibility == "research"
                            and code != "required_input_missing"
                            and self.policy.sealed_runtime_mode == "legacy_extended"
                            else "terminal"
                        ),
                        "responsibility": responsibility,
                        "failure_stage": stage,
                        "failure_code": code,
                        "plan_artifact_sha256": initial.artifact_sha256,
                    },
                )
                if (
                    responsibility == "research"
                    and code != "required_input_missing"
                    and self.policy.sealed_runtime_mode == "legacy_extended"
                ):
                    return await self._full_generate(
                        operation_ref=operation_ref,
                        initial_artifact=initial,
                        plan_artifacts=plan_artifacts,
                        evidence_hashes=evidence_hashes,
                        compiler_failure_hashes=compiler_failure_hashes,
                        execution_failures=(),
                        diagnostic_excerpts=(),
                        checkpoints=checkpoints,
                        adaptation_count=adaptation_count,
                        temporary_artifacts=temporary_artifacts,
                        progress=progress,
                        primary_failure=primary_failure,
                    )
                return self._terminal(
                    status=(responsibility if responsibility != "research" else "research") + "_failure",
                    execution_result=initial_failure_result,
                    artifact=initial,
                    operation_ref=operation_ref,
                    plan_artifacts=plan_artifacts,
                    evidence_hashes=evidence_hashes,
                    adaptation_count=0,
                    full_generation_count=0,
                    checkpoints=checkpoints,
                    temporary_artifacts=temporary_artifacts,
                    primary_failure=primary_failure,
                )

            current = initial
            execution_failures: list[StructuredExecutionFailureEvidence] = []
            execution_failure_boundaries: list[str] = []
            with model_recovery_routes_remaining(1):
                execution_result = await execution_port.execute(artifact=current)
            if execution_result.is_success:
                return self._terminal(
                    status="evaluating",
                    execution_result=execution_result,
                    artifact=current,
                    operation_ref=operation_ref,
                    plan_artifacts=plan_artifacts,
                    evidence_hashes=evidence_hashes,
                    adaptation_count=0,
                    full_generation_count=0,
                    checkpoints=checkpoints,
                    temporary_artifacts=temporary_artifacts,
                )

            primary_failure = terminal_failure_from_execution_result(
                execution_result,
                run_id=self.run_id,
                graph_revision=revision.graph_revision,
                subtask_id=revision.subtask_id,
                subtask_revision=revision.subtask_revision,
                plan_revision=current.plan_revision.plan_revision,
            )

            for plan_revision in range(1, self.policy.max_plan_adaptations + 1):
                responsibility = _execution_responsibility(execution_result)
                if responsibility not in {"research", "infrastructure"}:
                    return self._terminal(
                        status=("interrupted" if responsibility == "interrupted" else responsibility + "_failure"),
                        execution_result=execution_result,
                        artifact=current,
                        operation_ref=operation_ref,
                        plan_artifacts=plan_artifacts,
                        evidence_hashes=evidence_hashes,
                        adaptation_count=adaptation_count,
                        full_generation_count=0,
                        checkpoints=checkpoints,
                        temporary_artifacts=temporary_artifacts,
                        primary_failure=primary_failure,
                    )
                recovery_snapshot = build_recovery_execution_snapshot(
                    artifact=current,
                    execution_result=execution_result,
                    diagnostic=execution_result.error_log or "",
                    diagnostic_max_bytes=self.policy.diagnostic_payload_max_bytes,
                )
                if not _execution_failure_allows_plan_adaptation(
                    execution_result, recovery_snapshot,
                ):
                    return self._terminal(
                        status=responsibility + "_failure",
                        execution_result=execution_result,
                        artifact=current,
                        operation_ref=operation_ref,
                        plan_artifacts=plan_artifacts,
                        evidence_hashes=evidence_hashes,
                        adaptation_count=adaptation_count,
                        full_generation_count=0,
                        checkpoints=checkpoints,
                        temporary_artifacts=temporary_artifacts,
                        primary_failure=primary_failure,
                    )
                if recovery_snapshot.failure_evidence.side_effect_evidence.status.value == "unmatched_call":
                    return self._terminal(
                        status="interrupted",
                        execution_result=_failure_execution_result(
                            responsibility="interrupted",
                            failure_stage="resource_execution",
                            failure_code="recovery_unmatched_started_call",
                        ),
                        artifact=current,
                        operation_ref=operation_ref,
                        plan_artifacts=plan_artifacts,
                        evidence_hashes=evidence_hashes,
                        adaptation_count=adaptation_count,
                        full_generation_count=0,
                        checkpoints=checkpoints,
                        temporary_artifacts=temporary_artifacts,
                        primary_failure=primary_failure,
                    )
                checkpoints = recovery_snapshot.checkpoints
                checkpoint_results = dict(recovery_snapshot.checkpoint_results)
                for checkpoint in checkpoints:
                    self._event(
                        "checkpoint_registered",
                        {
                            "plan_revision": current.plan_revision.plan_revision,
                            "step_id": checkpoint.step_id,
                            "checkpoint_sha256": checkpoint.checkpoint_sha256,
                            "resource_call_id": checkpoint.resource_call_id,
                            "result_sha256": checkpoint.result_sha256,
                        },
                    )
                evidence_hashes.append(recovery_snapshot.failure_evidence.evidence_sha256)
                failure_boundary = _execution_failure_boundary_signature(
                    recovery_snapshot.failure_evidence,
                    cost_metric=execution_result.cost_metric,
                    diagnostic_excerpt=recovery_snapshot.diagnostic_excerpt,
                )
                repeated_failure_boundary = (
                    failure_boundary in execution_failure_boundaries
                )
                execution_failures.append(recovery_snapshot.failure_evidence)
                execution_failure_boundaries.append(failure_boundary)
                if recovery_snapshot.diagnostic_excerpt:
                    diagnostic_excerpts.append(recovery_snapshot.diagnostic_excerpt)
                if (
                    recovery_snapshot.failure_evidence.responsibility == "research"
                    and repeated_failure_boundary
                ):
                    self._event(
                        "recovery_decision",
                        {
                            "decision": "terminal_repeated_failure_boundary",
                            "responsibility": recovery_snapshot.failure_evidence.responsibility,
                            "failure_stage": recovery_snapshot.failure_evidence.failure_stage,
                            "failure_code": recovery_snapshot.failure_evidence.failure_code,
                            "resource_id": recovery_snapshot.failure_evidence.resource_id,
                            "entrypoint_id": recovery_snapshot.failure_evidence.entrypoint_id,
                            "plan_artifact_sha256": current.artifact_sha256,
                        },
                    )
                    return self._terminal(
                        status="research_failure",
                        execution_result=execution_result,
                        artifact=current,
                        operation_ref=operation_ref,
                        plan_artifacts=plan_artifacts,
                        evidence_hashes=evidence_hashes,
                        adaptation_count=adaptation_count,
                        full_generation_count=0,
                        checkpoints=checkpoints,
                        temporary_artifacts=temporary_artifacts,
                        primary_failure=primary_failure,
                        recovery_outcome="repeated_failure_boundary",
                    )
                # Admission happens before an attempt is recorded.  A recovery
                # compilation that cannot receive the minimum provider window is
                # a budget terminal, not a started adaptation or framework bug.
                with model_recovery_routes_remaining(1):
                    current_attempt_timeout("plan_adaptation")
                self._event(
                    "plan_adaptation_started",
                    {
                        "plan_revision": plan_revision,
                        "previous_plan_artifact_sha256": current.artifact_sha256,
                        "failure_evidence_sha256": recovery_snapshot.failure_evidence.evidence_sha256,
                        "candidate_pool_sha256": candidate_pool_sha256,
                    },
                )
                progress["adaptation_count"] = plan_revision
                with model_recovery_routes_remaining(1):
                    adapted = await self.compilation_port.adapt(
                        previous_artifact=current,
                        snapshot=recovery_snapshot,
                        plan_revision=plan_revision,
                    )
                adaptation_count = plan_revision
                plan_artifacts.append(adapted.artifact_sha256)
                operation_ref = self._operation_ref(
                    revision=revision,
                    candidate_pool_sha256=candidate_pool_sha256,
                    initial_artifact_sha256=initial.artifact_sha256,
                    current_plan_revision=plan_revision,
                    adaptation_count=adaptation_count,
                    full_generation_count=0,
                )
                if adapted.candidate_pool_sha256 != candidate_pool_sha256:
                    raise RecoveryControllerError("recovery_adaptation_candidate_hash_mismatch")
                if adapted.status != "success" or adapted.executable_plan is None:
                    responsibility, stage, code, message_hash = _compiler_failure_status(adapted)
                    compiler_failure_hashes.append(message_hash)
                    self._event(
                        "plan_adaptation_failed",
                        {
                            "plan_revision": plan_revision,
                            "responsibility": responsibility,
                            "failure_stage": stage,
                            "failure_code": code,
                            "plan_artifact_sha256": adapted.artifact_sha256,
                            "accounting_operation_id": adapted.accounting_operation_id,
                        },
                    )
                    # If the original execution already produced a concrete
                    # research/semantic failure, an adaptation-side framework
                    # error must not replace it as the public outcome.  Keep
                    # the original result/plan as the causal primary failure
                    # and record the adaptation failure in recovery metadata.
                    # This preserves normal successful recovery behavior while
                    # preventing representation bugs from masquerading as the
                    # task's actual failure.
                    if responsibility == "framework" and primary_failure is not None:
                        return self._terminal(
                            status=(
                                "interrupted"
                                if _execution_responsibility(execution_result) == "interrupted"
                                else _execution_responsibility(execution_result) + "_failure"
                            ),
                            execution_result=execution_result,
                            artifact=current,
                            operation_ref=operation_ref,
                            plan_artifacts=plan_artifacts,
                            evidence_hashes=evidence_hashes,
                            adaptation_count=adaptation_count,
                            full_generation_count=0,
                            checkpoints=checkpoints,
                            temporary_artifacts=temporary_artifacts,
                            primary_failure=primary_failure,
                            recovery_outcome="adaptation_failed",
                        )
                    if responsibility == "research" and code != "plan_adaptation_insufficient":
                        if plan_revision < self.policy.max_plan_adaptations:
                            continue
                        break
                    return self._terminal(
                        status=responsibility + "_failure",
                        execution_result=_failure_execution_result(
                            responsibility=responsibility,
                            failure_stage=stage,
                            failure_code=code,
                            message_sha256=message_hash,
                        ),
                        artifact=adapted,
                        operation_ref=operation_ref,
                        plan_artifacts=plan_artifacts,
                        evidence_hashes=evidence_hashes,
                        adaptation_count=adaptation_count,
                        full_generation_count=0,
                        checkpoints=checkpoints,
                        temporary_artifacts=temporary_artifacts,
                        primary_failure=primary_failure,
                    )
                if _artifact_adaptation_kind(adapted) == "temporary_tool_transform":
                    if self.policy.sealed_runtime_mode == "strict_plan_only":
                        forbidden = _failure_execution_result(
                            responsibility="framework",
                            failure_stage="plan_adaptation_projection",
                            failure_code="formal_temporary_tool_transform_forbidden",
                        )
                        return self._terminal(
                            status="framework_failure",
                            execution_result=forbidden,
                            artifact=adapted,
                            operation_ref=operation_ref,
                            plan_artifacts=plan_artifacts,
                            evidence_hashes=evidence_hashes,
                            adaptation_count=adaptation_count,
                            full_generation_count=0,
                            checkpoints=checkpoints,
                            temporary_artifacts=temporary_artifacts,
                            primary_failure=primary_failure,
                        )
                    if self.temporary_tool_port is None:
                        execution_result = _failure_execution_result(
                            responsibility="research",
                            failure_stage="temporary_tool_eligibility",
                            failure_code="temporary_tool_port_unavailable",
                        )
                        current = adapted
                        if plan_revision < self.policy.max_plan_adaptations:
                            continue
                        break
                    prepared = await self.temporary_tool_port.prepare(
                        artifact=adapted,
                        snapshot=recovery_snapshot,
                    )
                    if prepared is None:
                        execution_result = _failure_execution_result(
                            responsibility="research",
                            failure_stage="temporary_tool_eligibility",
                            failure_code="temporary_tool_path_unavailable",
                        )
                        current = adapted
                        if plan_revision < self.policy.max_plan_adaptations:
                            continue
                        break
                    if isinstance(prepared, ExecutionResult):
                        execution_result = prepared
                        current = adapted
                        responsibility = _execution_responsibility(prepared)
                        if responsibility == "research":
                            if plan_revision < self.policy.max_plan_adaptations:
                                continue
                            break
                        return self._terminal(
                            status=(
                                "interrupted"
                                if responsibility == "interrupted"
                                else responsibility + "_failure"
                            ),
                            execution_result=prepared,
                            artifact=adapted,
                            operation_ref=operation_ref,
                            plan_artifacts=plan_artifacts,
                            evidence_hashes=evidence_hashes,
                            adaptation_count=adaptation_count,
                            full_generation_count=0,
                            checkpoints=checkpoints,
                            temporary_artifacts=temporary_artifacts,
                            primary_failure=primary_failure,
                        )
                    checkpoints = (*checkpoints, prepared.checkpoint)
                    checkpoint_results[prepared.checkpoint.step_id] = prepared.checkpoint_result
                    temporary_artifacts.append(prepared.artifact_sha256)
                    self._event(
                        "temporary_tool_generated",
                        {
                            "plan_revision": plan_revision,
                            "artifact_sha256": prepared.artifact_sha256,
                            "checkpoint_sha256": prepared.checkpoint.checkpoint_sha256,
                        },
                    )
                self._event(
                    "plan_adaptation_finished",
                    {
                        "plan_revision": plan_revision,
                        "plan_artifact_sha256": adapted.artifact_sha256,
                        "checkpoint_count": len(checkpoints),
                        "accounting_operation_id": adapted.accounting_operation_id,
                    },
                )
                for checkpoint in checkpoints:
                    self._event(
                        "checkpoint_reused",
                        {
                            "plan_revision": plan_revision,
                            "step_id": checkpoint.step_id,
                            "checkpoint_sha256": checkpoint.checkpoint_sha256,
                            "resource_call_id": checkpoint.resource_call_id,
                        },
                    )
                with model_recovery_routes_remaining(1):
                    execution_result = await execution_port.execute(
                        artifact=adapted,
                        checkpoints=checkpoints,
                        checkpoint_results=checkpoint_results,
                    )
                current = adapted
                if execution_result.is_success:
                    return self._terminal(
                        status="evaluating",
                        execution_result=execution_result,
                        artifact=current,
                        operation_ref=operation_ref,
                        plan_artifacts=plan_artifacts,
                        evidence_hashes=evidence_hashes,
                        adaptation_count=adaptation_count,
                        full_generation_count=0,
                        checkpoints=checkpoints,
                        temporary_artifacts=temporary_artifacts,
                        primary_failure=primary_failure,
                        recovery_outcome="plan_adaptation_succeeded",
                    )

            if self.policy.sealed_runtime_mode == "strict_plan_only":
                responsibility = _execution_responsibility(execution_result)
                return self._terminal(
                    status=(
                        "interrupted"
                        if responsibility == "interrupted"
                        else responsibility + "_failure"
                    ),
                    execution_result=execution_result,
                    artifact=current,
                    operation_ref=operation_ref,
                    plan_artifacts=plan_artifacts,
                    evidence_hashes=evidence_hashes,
                    adaptation_count=adaptation_count,
                    full_generation_count=0,
                    checkpoints=checkpoints,
                    temporary_artifacts=temporary_artifacts,
                    primary_failure=primary_failure,
                )
            return await self._full_generate(
                operation_ref=operation_ref,
                initial_artifact=initial,
                plan_artifacts=plan_artifacts,
                evidence_hashes=evidence_hashes,
                compiler_failure_hashes=compiler_failure_hashes,
                execution_failures=execution_failures,
                diagnostic_excerpts=diagnostic_excerpts,
                checkpoints=checkpoints,
                adaptation_count=adaptation_count,
                temporary_artifacts=temporary_artifacts,
                progress=progress,
                primary_failure=primary_failure,
            )
        except RecoveryPersistenceError:
            adaptation_count = progress["adaptation_count"]
            full_generation_count = progress["full_generation_count"]
            persistence_result = _failure_execution_result(
                responsibility="framework",
                failure_stage="recovery_persistence",
                failure_code="recovery_persistence_failed",
            )
            persistence_failure = terminal_failure_from_execution_result(
                persistence_result,
                run_id=self.run_id,
                graph_revision=revision.graph_revision,
                subtask_id=revision.subtask_id,
                subtask_revision=revision.subtask_revision,
            )
            resolved_primary = primary_failure or persistence_failure
            return RecoveryTerminalResult(
                protocol=RECOVERY_CONTROLLER_PROTOCOL,
                status="framework_failure",
                execution_result=persistence_result,
                final_plan_artifact=None,
                operation_ref=operation_ref,
                plan_artifact_sha256s=tuple(plan_artifacts),
                failure_evidence_sha256s=tuple(evidence_hashes),
                adaptation_attempts=adaptation_count,
                full_generation_attempts=full_generation_count,
                checkpoint_reused_count=len(checkpoints),
                temporary_tool_artifact_sha256s=tuple(temporary_artifacts),
                terminal_failure=persistence_failure,
                primary_failure=resolved_primary,
                recovery_outcome="none",
                causal_chain=_causal_failure_codes(
                    resolved_primary,
                    "none",
                    persistence_failure,
                ),
            )
        except ModelTimeBudgetError:
            return self._terminal(
                status="budget_failure",
                execution_result=_failure_execution_result(
                    responsibility="budget",
                    failure_stage="recovery_model_admission",
                    failure_code="model_time_budget_exhausted",
                ),
                artifact=current,
                operation_ref=operation_ref,
                plan_artifacts=plan_artifacts,
                evidence_hashes=evidence_hashes,
                adaptation_count=progress["adaptation_count"],
                full_generation_count=progress["full_generation_count"],
                checkpoints=checkpoints,
                temporary_artifacts=temporary_artifacts,
                revision=revision,
                candidate_pool_sha256=candidate_pool_sha256,
                primary_failure=primary_failure,
            )
        except asyncio.CancelledError:
            try:
                self._event(
                    "recovery_interrupted",
                    {
                        "recovery_identity_sha256": (
                            subtask_revision_identity_sha256(revision)
                        ),
                        "candidate_pool_sha256": candidate_pool_sha256,
                        "plan_artifact_sha256s": plan_artifacts,
                    },
                )
                self._terminal(
                    status="interrupted",
                    execution_result=_failure_execution_result(
                        responsibility="interrupted",
                        failure_stage="recovery_controller",
                        failure_code="recovery_cancelled",
                    ),
                    artifact=None,
                    operation_ref=operation_ref,
                    plan_artifacts=plan_artifacts,
                    evidence_hashes=evidence_hashes,
                    adaptation_count=progress["adaptation_count"],
                    full_generation_count=progress["full_generation_count"],
                    checkpoints=checkpoints,
                    temporary_artifacts=temporary_artifacts,
                    revision=revision,
                    candidate_pool_sha256=candidate_pool_sha256,
                    primary_failure=primary_failure,
                )
            finally:
                raise
        except Exception as exc:
            adaptation_count = progress["adaptation_count"]
            full_generation_count = progress["full_generation_count"]
            failure_code = _exception_failure_code(exc)
            declared_stage = getattr(exc, "failure_stage", None)
            failure_stage = (
                declared_stage if isinstance(declared_stage, str)
                and _STRUCTURED_FAILURE_CODE.fullmatch(declared_stage)
                else "recovery_controller"
            )
            declared_reasons = getattr(exc, "reason_codes", ())
            reason_codes = tuple(
                code for code in declared_reasons
                if isinstance(code, str) and _STRUCTURED_FAILURE_CODE.fullmatch(code)
            ) if isinstance(declared_reasons, (tuple, list)) else ()
            message_sha256 = _exception_message_sha256(exc)
            try:
                self._event(
                    "recovery_internal_failure",
                    {
                        "candidate_pool_sha256": candidate_pool_sha256,
                        "plan_artifact_sha256s": list(plan_artifacts),
                        "failure_code": failure_code,
                        "failure_stage": failure_stage,
                        "reason_codes": list(reason_codes),
                        "exception_type": type(exc).__name__,
                        "validation_issue_locations": list(_validation_issue_locations(exc)),
                        "message_sha256": message_sha256,
                    },
                )
                return self._terminal(
                    status="framework_failure",
                    execution_result=_failure_execution_result(
                        responsibility="framework",
                        failure_stage=failure_stage,
                        failure_code=failure_code,
                        message_sha256=message_sha256,
                        exception_type=type(exc).__name__,
                    ),
                    artifact=None,
                    operation_ref=operation_ref,
                    plan_artifacts=plan_artifacts,
                    evidence_hashes=evidence_hashes,
                    adaptation_count=adaptation_count,
                    full_generation_count=full_generation_count,
                    checkpoints=checkpoints,
                    temporary_artifacts=temporary_artifacts,
                    revision=revision,
                    candidate_pool_sha256=candidate_pool_sha256,
                    primary_failure=primary_failure,
                )
            except RecoveryPersistenceError:
                persistence_result = _failure_execution_result(
                    responsibility="framework",
                    failure_stage="recovery_persistence",
                    failure_code="recovery_persistence_failed",
                    message_sha256=message_sha256,
                    exception_type=type(exc).__name__,
                )
                persistence_failure = terminal_failure_from_execution_result(
                    persistence_result,
                    run_id=self.run_id,
                    graph_revision=revision.graph_revision,
                    subtask_id=revision.subtask_id,
                    subtask_revision=revision.subtask_revision,
                )
                resolved_primary = primary_failure or persistence_failure
                return RecoveryTerminalResult(
                    protocol=RECOVERY_CONTROLLER_PROTOCOL,
                    status="framework_failure",
                    execution_result=persistence_result,
                    final_plan_artifact=None,
                    operation_ref=operation_ref,
                    plan_artifact_sha256s=tuple(plan_artifacts),
                    failure_evidence_sha256s=tuple(evidence_hashes),
                    adaptation_attempts=adaptation_count,
                    full_generation_attempts=full_generation_count,
                    checkpoint_reused_count=len(checkpoints),
                    temporary_tool_artifact_sha256s=tuple(temporary_artifacts),
                    terminal_failure=persistence_failure,
                    primary_failure=resolved_primary,
                    recovery_outcome="none",
                    causal_chain=_causal_failure_codes(
                        resolved_primary,
                        "none",
                        persistence_failure,
                    ),
                )

    async def _full_generate(
        self,
        *,
        operation_ref: RecoveryOperationRef | None,
        initial_artifact: SealedPlanCompilationArtifact,
        plan_artifacts: Sequence[str],
        evidence_hashes: Sequence[str],
        compiler_failure_hashes: Sequence[str],
        execution_failures: Sequence[StructuredExecutionFailureEvidence],
        diagnostic_excerpts: Sequence[str],
        checkpoints: Sequence[CompletedStepCheckpoint],
        adaptation_count: int,
        temporary_artifacts: Sequence[str],
        progress: dict[str, int],
        primary_failure: TerminalFailureEnvelope | None,
    ) -> RecoveryTerminalResult:
        if self.policy.sealed_runtime_mode != "legacy_extended":
            raise RecoveryControllerError("formal_full_generation_forbidden")
        if self.full_generation_port is None:
            raise RecoveryControllerError("legacy_full_generation_port_missing")
        recovery_identity_sha256 = subtask_revision_identity_sha256(
            operation_ref.revision
            if operation_ref is not None
            else initial_artifact.plan_revision.subtask_revision
        )
        self._event(
            "full_generation_started",
            {
                "attempt": 1,
                "recovery_identity_sha256": recovery_identity_sha256,
                "candidate_pool_sha256": initial_artifact.candidate_pool_sha256,
                "failure_evidence_sha256s": list(evidence_hashes),
                "compiler_failure_hashes": list(compiler_failure_hashes),
            },
        )
        progress["full_generation_count"] = 1
        finished = False
        try:
            result = await self.full_generation_port.generate(
                compiler_failure_hashes=compiler_failure_hashes,
                execution_failures=execution_failures,
                diagnostic_excerpts=diagnostic_excerpts,
                checkpoints=checkpoints,
            )
            projected_result = result.model_copy(
                update={
                    "execution_audit": {
                        **dict(result.execution_audit),
                        "legacy_metric_projection": {
                            "full_generation": True,
                            "system_fallback_resource_id": result.resource_id,
                        },
                    }
                }
            )
            execution_result = resource_result_to_execution_result(projected_result)
            model_response_success = result.status is ResourceCallStatus.SUCCESS
            if model_response_success:
                execution_result = ExecutionResult(
                    is_success=False,
                    output_data=execution_result.output_data,
                    error_log="recovery_diagnostic_not_formal_artifact",
                    cost_metric={
                        **dict(execution_result.cost_metric or {}),
                        "failure_type": "recovery_diagnostic_not_formal_artifact",
                        "failure_layer": "research",
                        "failure": {
                            "responsibility": "research",
                            "failure_stage": "recovery",
                            "failure_code": "recovery_diagnostic_not_formal_artifact",
                            "exception_type": "",
                            "retryable": False,
                            "response_received": True,
                            "message_sha256": canonical_sha256(
                                "recovery_diagnostic_not_formal_artifact"
                            ),
                        },
                        "model_response_success": True,
                        "artifact_ready_for_evaluation": False,
                        "evaluation_eligible": False,
                    },
                )
                status = "research_failure"
            else:
                status = (
                    "interrupted"
                    if result.status is ResourceCallStatus.INTERRUPTED
                    else result.status.value
                )
            updated_ref = None
            if operation_ref is not None:
                updated_ref = self._operation_ref(
                    revision=operation_ref.revision,
                    candidate_pool_sha256=operation_ref.candidate_pool_sha256,
                    initial_artifact_sha256=operation_ref.initial_plan_artifact_sha256,
                    current_plan_revision=operation_ref.current_plan_revision,
                    adaptation_count=operation_ref.adaptation_count,
                    full_generation_count=1,
                )
            self._event(
                "full_generation_finished",
                {
                    "attempt": 1,
                    "recovery_identity_sha256": recovery_identity_sha256,
                    "status": result.status.value,
                    "resource_id": result.resource_id,
                    "usage_reference": result.usage_reference,
                    "candidate_pool_sha256": initial_artifact.candidate_pool_sha256,
                    "model_response_success": model_response_success,
                    "artifact_ready_for_evaluation": False,
                    "evaluation_eligible": False,
                },
            )
            finished = True
            return self._terminal(
                status=status,
                execution_result=execution_result,
                artifact=None,
                operation_ref=updated_ref,
                plan_artifacts=plan_artifacts,
                evidence_hashes=evidence_hashes,
                adaptation_count=adaptation_count,
                full_generation_count=1,
                checkpoints=checkpoints,
                temporary_artifacts=temporary_artifacts,
                model_response_success=model_response_success,
                artifact_ready_for_evaluation=False,
                evaluation_eligible=False,
                primary_failure=primary_failure,
            )
        except asyncio.CancelledError:
            if not finished:
                self._event(
                    "full_generation_finished",
                    {
                        "attempt": 1,
                        "recovery_identity_sha256": recovery_identity_sha256,
                        "status": "interrupted",
                        "failure_stage": "full_generation",
                        "failure_code": "recovery_cancelled",
                        "candidate_pool_sha256": initial_artifact.candidate_pool_sha256,
                    },
                )
            raise
        except Exception as exc:
            if not finished:
                self._event(
                    "full_generation_finished",
                    {
                        "attempt": 1,
                        "recovery_identity_sha256": recovery_identity_sha256,
                        "status": "framework_failure",
                        "failure_stage": "full_generation",
                        "failure_code": _exception_failure_code(exc),
                        "exception_type": type(exc).__name__,
                        "message_sha256": _exception_message_sha256(exc),
                        "candidate_pool_sha256": initial_artifact.candidate_pool_sha256,
                    },
                )
            raise

    def _terminal(
        self,
        *,
        status: str,
        execution_result: ExecutionResult,
        artifact: SealedPlanCompilationArtifact | None,
        operation_ref: RecoveryOperationRef | None,
        plan_artifacts: Sequence[str],
        evidence_hashes: Sequence[str],
        adaptation_count: int,
        full_generation_count: int,
        checkpoints: Sequence[CompletedStepCheckpoint],
        temporary_artifacts: Sequence[str],
        revision: Any | None = None,
        candidate_pool_sha256: str | None = None,
        model_response_success: bool | None = None,
        artifact_ready_for_evaluation: bool | None = None,
        evaluation_eligible: bool | None = None,
        primary_failure: TerminalFailureEnvelope | None = None,
        recovery_outcome: str | None = None,
    ) -> RecoveryTerminalResult:
        normalized = status
        if normalized not in {
            "evaluating",
            "framework_failure",
            "infrastructure_failure",
            "research_failure",
            "budget_failure",
            "interrupted",
        }:
            normalized = "framework_failure"
        terminal_revision = (
            operation_ref.revision if operation_ref is not None else revision
        )
        terminal_candidate_pool_sha256 = (
            operation_ref.candidate_pool_sha256
            if operation_ref is not None
            else candidate_pool_sha256
        )
        formal_artifact_ready = bool(
            artifact is not None
            and artifact.status == "success"
            and artifact.executable_plan is not None
            and execution_result.is_success
        )
        resolved_model_response_success = (
            bool(execution_result.is_success)
            if model_response_success is None
            else bool(model_response_success)
        )
        resolved_artifact_ready = (
            formal_artifact_ready
            if artifact_ready_for_evaluation is None
            else bool(artifact_ready_for_evaluation)
        )
        resolved_evaluation_eligible = (
            formal_artifact_ready
            if evaluation_eligible is None
            else bool(evaluation_eligible)
        )
        if normalized == "evaluating" and not (
            formal_artifact_ready
            and resolved_artifact_ready
            and resolved_evaluation_eligible
        ):
            normalized = "framework_failure"
            resolved_artifact_ready = False
            resolved_evaluation_eligible = False
            execution_result = _failure_execution_result(
                responsibility="framework",
                failure_stage="recovery_evaluation_gate",
                failure_code="evaluation_requires_formal_executed_artifact",
            )
        self._event(
            "recovery_terminal",
            {
                "recovery_identity_sha256": (
                    subtask_revision_identity_sha256(terminal_revision)
                    if terminal_revision is not None
                    else None
                ),
                "recovery_operation_sha256": (
                    operation_ref.operation_sha256
                    if operation_ref is not None
                    else None
                ),
                "candidate_pool_sha256": (
                    terminal_candidate_pool_sha256
                ),
                "status": normalized,
                "final_plan_artifact_sha256": artifact.artifact_sha256 if artifact else None,
                "plan_artifact_sha256s": list(plan_artifacts),
                "failure_evidence_sha256s": list(evidence_hashes),
                "adaptation_attempts": adaptation_count,
                "full_generation_attempts": full_generation_count,
                "checkpoint_reused_count": len(checkpoints),
                "temporary_tool_artifact_sha256s": list(temporary_artifacts),
                "model_response_success": resolved_model_response_success,
                "artifact_ready_for_evaluation": resolved_artifact_ready,
                "evaluation_eligible": resolved_evaluation_eligible,
            },
        )
        terminal_failure = (
            None
            if normalized == "evaluating"
            else terminal_failure_from_execution_result(
                execution_result,
                run_id=self.run_id,
                graph_revision=(
                    terminal_revision.graph_revision
                    if terminal_revision is not None
                    else None
                ),
                subtask_id=(
                    terminal_revision.subtask_id
                    if terminal_revision is not None
                    else ""
                ),
                subtask_revision=(
                    terminal_revision.subtask_revision
                    if terminal_revision is not None
                    else None
                ),
                plan_revision=(
                    artifact.plan_revision.plan_revision
                    if artifact is not None
                    else None
                ),
            )
        )
        resolved_primary = primary_failure or terminal_failure
        resolved_outcome = recovery_outcome
        if resolved_outcome is None and terminal_failure is not None:
            resolved_outcome = (
                "recovery_diagnostic_not_formal_artifact"
                if terminal_failure.failure_code == "recovery_diagnostic_not_formal_artifact"
                else "none"
            )
        return RecoveryTerminalResult(
            protocol=RECOVERY_CONTROLLER_PROTOCOL,
            status=cast(
                Literal[
                    "evaluating",
                    "framework_failure",
                    "infrastructure_failure",
                    "research_failure",
                    "budget_failure",
                    "interrupted",
                ],
                normalized,
            ),
            execution_result=execution_result,
            final_plan_artifact=artifact,
            operation_ref=operation_ref,
            plan_artifact_sha256s=tuple(plan_artifacts),
            failure_evidence_sha256s=tuple(evidence_hashes),
            adaptation_attempts=adaptation_count,
            full_generation_attempts=full_generation_count,
            checkpoint_reused_count=len(checkpoints),
            temporary_tool_artifact_sha256s=tuple(temporary_artifacts),
            model_response_success=resolved_model_response_success,
            artifact_ready_for_evaluation=resolved_artifact_ready,
            evaluation_eligible=resolved_evaluation_eligible,
            terminal_failure=terminal_failure,
            primary_failure=resolved_primary,
            recovery_outcome=resolved_outcome,
            causal_chain=_causal_failure_codes(
                resolved_primary,
                resolved_outcome,
                terminal_failure,
            ),
        )


__all__ = [
    "FullGenerationPort",
    "PlanCompilationPort",
    "PlanExecutionPort",
    "PreparedTemporaryToolExecution",
    "RECOVERY_CONTROLLER_PROTOCOL",
    "RecoveryController",
    "RecoveryControllerError",
    "RecoveryTerminalResult",
    "TemporaryToolPort",
]
