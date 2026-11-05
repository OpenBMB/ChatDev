"""Formal sealed-plan execution boundary.

This module intentionally does not import ``ResourceApplicationPlan``.  It
projects an already validated/lowered executable plan into a small immutable
runtime view and dispatches that view without reopening planning semantics.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping, Sequence

from .executable_plan import ResourceApplicationV1, SealedPlanCompilationArtifact
from .executors import ExecutionResult
from .pipeline_control import canonical_sha256
from .plan_lowering import LoweredExecutionPlan
from .formal_contracts import PlanExecutionReadinessV1, PlanReadinessStepV1
from .recovery_control import CompletedStepCheckpoint, executable_step_semantic_sha256
from .resource_runtime import ResourceDefinition, ResourceExecutionContext
from .schema import OperationKind, ResourceOutputContract, TypedResourceRef
from .controller_session import (
    ControllerSessionSpec,
    ControllerSessionSpecV2,
    derive_controller_session_spec,
    load_controller_session_policy,
)
from .controller_tooling import (
    ControllerCallableToolSpecV1,
    ControllerToolingError,
    derive_controller_callable_tool_spec,
)
from .controller_tool_runtime import CONTROLLER_TOOL_RUNTIME_PROTOCOL


FORMAL_EXECUTION_PROTOCOL = "sgar-formal-execution-v3"


class FormalExecutionError(ValueError):
    """A sealed-plan failure with safe codes for the recovery boundary."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        primary, _, detail = message.partition(":")
        self.code = primary if re.fullmatch(r"[a-z][a-z0-9_]*", primary) else "formal_execution_error"
        self.failure_stage = "formal_execution"
        self.reason_codes = tuple(
            code for code in detail.split(",")
            if re.fullmatch(r"[a-z][a-z0-9_]*", code)
        )


@dataclass(frozen=True)
class FormalExecutableStep:
    step_id: str
    step_type: str
    resource_id: str
    capability_operation_id: str
    satisfied_obligation_ids: tuple[str, ...]
    resource_type: str
    operation_kind: OperationKind
    entrypoint_id: str | None
    intent: str
    depends_on: tuple[str, ...]
    input_bindings: Mapping[str, Any]
    consumed_context_source_ids: tuple[str, ...]
    runtime_context_handle_ids: tuple[str, ...]
    consumed_edge_contract_sha256s: tuple[str, ...]
    output_key: str
    expected_output_contract: ResourceOutputContract
    resource_application: ResourceApplicationV1 | None
    controller_session_spec: ControllerSessionSpec | None
    format_enforcement: Mapping[str, Any] | None
    advisory_profile_refs: tuple[str, ...]
    agent_base_model_resource_id: str | None
    execution_network_required: bool | None = None


@dataclass(frozen=True)
class FormalExecutablePlan:
    protocol: str
    selected_resource_ids: tuple[str, ...]
    resource_usage: tuple[Any, ...]
    steps: tuple[FormalExecutableStep, ...]
    final_output_from: str
    plan_sha256: str
    dag_edge_contract_sha256s: tuple[str, ...]

    def model_dump(self, *, mode: str = "python") -> dict[str, Any]:
        del mode
        return {
            "protocol": self.protocol,
            "selected_resource_ids": list(self.selected_resource_ids),
            "resource_usage": [
                item.model_dump(mode="json") if hasattr(item, "model_dump") else item
                for item in self.resource_usage
            ],
            "steps": [
                {
                    "step_id": step.step_id,
                    "step_type": step.step_type,
                    "resource_id": step.resource_id,
                    "capability_operation_id": step.capability_operation_id,
                    "satisfied_obligation_ids": list(step.satisfied_obligation_ids),
                    "resource_type": step.resource_type,
                    "operation_kind": step.operation_kind.value,
                    "entrypoint_id": step.entrypoint_id,
                    "intent": step.intent,
                    "depends_on": list(step.depends_on),
                    "input_bindings": copy.deepcopy(dict(step.input_bindings)),
                    "consumed_context_source_ids": list(
                        step.consumed_context_source_ids
                    ),
                    "runtime_context_handle_ids": list(step.runtime_context_handle_ids),
                    "consumed_edge_contract_sha256s": list(
                        step.consumed_edge_contract_sha256s
                    ),
                    "output_key": step.output_key,
                    "expected_output_contract": step.expected_output_contract.model_dump(
                        mode="json"
                    ),
                    "resource_application": (
                        step.resource_application.model_dump(mode="json")
                        if step.resource_application is not None
                        else None
                    ),
                    "controller_session_spec": (
                        step.controller_session_spec.model_dump(mode="json")
                        if step.controller_session_spec is not None
                        else None
                    ),
                    "format_enforcement": copy.deepcopy(step.format_enforcement),
                    "advisory_profile_refs": list(step.advisory_profile_refs),
                    "agent_base_model_resource_id": step.agent_base_model_resource_id,
                    **({"execution_network_required": step.execution_network_required}
                       if step.execution_network_required is not None else {}),
                }
                for step in self.steps
            ],
            "final_output_from": self.final_output_from,
            "plan_sha256": self.plan_sha256,
            "dag_edge_contract_sha256s": list(self.dag_edge_contract_sha256s),
        }


def _step_type(resource_type: str, operation_kind: OperationKind) -> str:
    if resource_type == "Tool":
        return operation_kind.value
    if resource_type == "Model":
        return (
            "synthesize_final"
            if operation_kind == OperationKind.SYNTHESIZE_FINAL
            else "call_model"
        )
    if resource_type == "Agent":
        return (
            "synthesize_final"
            if operation_kind == OperationKind.SYNTHESIZE_FINAL
            else "call_agent"
        )
    if resource_type == "Skill":
        return "apply_skill_hint"
    if resource_type == "Resource":
        return "read_resource"
    raise FormalExecutionError("formal_resource_type_unsupported")


def _formal_plan(
    artifact: SealedPlanCompilationArtifact,
    lowered: LoweredExecutionPlan,
) -> FormalExecutablePlan:
    plan = artifact.executable_plan
    if plan is None:
        raise FormalExecutionError("sealed_plan_artifact_not_executable")
    templates = {item.step_id: item for item in lowered.step_templates}
    steps: list[FormalExecutableStep] = []
    for step in plan.steps:
        template = templates[step.step_id]
        bindings = copy.deepcopy(dict(template.unresolved_typed_bindings))
        runtime_context_handle_ids = (
            template.runtime_context_handle_ids
            or template.consumed_context_source_ids
        )
        if template.agent_base_model_resource_id is not None:
            bindings["base_model"] = {
                "resource_id": template.agent_base_model_resource_id,
            }
        steps.append(
            FormalExecutableStep(
                step_id=step.step_id,
                step_type=_step_type(step.resource_type, step.operation_kind),
                resource_id=step.resource_id,
                capability_operation_id=template.capability_operation_id,
                satisfied_obligation_ids=template.satisfied_obligation_ids,
                resource_type=step.resource_type,
                operation_kind=step.operation_kind,
                entrypoint_id=template.entrypoint_id,
                intent=step.intent,
                depends_on=step.depends_on,
                input_bindings=bindings,
                consumed_context_source_ids=template.consumed_context_source_ids,
                runtime_context_handle_ids=runtime_context_handle_ids,
                consumed_edge_contract_sha256s=template.edge_contract_sha256s,
                output_key=step.output_key,
                expected_output_contract=ResourceOutputContract.model_validate(
                    template.expected_output_contract
                ),
                resource_application=template.resource_application,
                controller_session_spec=template.controller_session_spec,
                format_enforcement=copy.deepcopy(template.format_enforcement),
                advisory_profile_refs=template.advisory_profile_refs,
                agent_base_model_resource_id=template.agent_base_model_resource_id,
                execution_network_required=template.execution_network_required,
            )
        )
    return FormalExecutablePlan(
        protocol=FORMAL_EXECUTION_PROTOCOL,
        selected_resource_ids=plan.selected_resource_ids,
        resource_usage=plan.resource_usage,
        steps=tuple(steps),
        final_output_from=plan.final_output.output_key,
        plan_sha256=plan.plan_sha256,
        dag_edge_contract_sha256s=plan.dag_edge_contract_sha256s,
    )


FormalDagExecutor = Callable[
    [FormalExecutablePlan, ResourceExecutionContext, Mapping[str, CompletedStepCheckpoint], Mapping[str, ExecutionResult]],
    Awaitable[ExecutionResult],
]


def _applied_capability_verified(
    facts: Mapping[str, Any], capability: str
) -> bool:
    """Read measured or separately approved applied facts; declarations are insufficient."""

    if facts.get("capability_authority") != "applied_ready_state":
        return False
    manual = facts.get("operator_approved_capabilities")
    if isinstance(manual, Mapping):
        approval = manual.get(capability)
        if isinstance(approval, Mapping) and approval.get("status") == "operator_approved":
            digest = approval.get("approval_sha256")
            if isinstance(digest, str) and len(digest) == 64 and all(c in "0123456789abcdef" for c in digest):
                return True
    applied = facts.get("applied_capabilities")
    if isinstance(applied, Mapping):
        value = applied.get(capability)
        if value is True:
            return True
        return isinstance(value, Mapping) and value.get("status") == "live_verified"
    if isinstance(applied, (list, tuple)):
        return capability in applied
    return False


def build_plan_execution_readiness(
    *,
    run_id: str,
    lowered: LoweredExecutionPlan,
    resource_definitions: Mapping[str, ResourceDefinition],
    sandbox_scope_sha256: str,
    environment_facts: Mapping[str, Mapping[str, Any]],
) -> PlanExecutionReadinessV1:
    """Validate every sealed adapter identity before the first DAG call."""

    step_results: list[PlanReadinessStepV1] = []
    try:
        controller_policy = load_controller_session_policy()
    except ValueError as exc:
        raise FormalExecutionError("controller_session_policy_invalid") from exc
    for template in lowered.step_templates:
        failures: list[str] = []
        checks = [
            "manifest_identity",
            "capability_operation_identity",
            "entrypoint_identity",
            "port_contract",
            "environment_identity",
        ]
        definition = resource_definitions.get(template.resource_id)
        entrypoint_id = template.entrypoint_id or "invoke"
        if definition is None:
            failures.append("readiness_resource_definition_missing")
            manifest_sha256 = canonical_sha256({"missing": template.resource_id})
        else:
            manifest_sha256 = definition.manifest_sha256
            if definition.manifest_sha256 != template.resource_manifest_sha256:
                failures.append("readiness_manifest_identity_changed")
            if definition.resource_type != template.resource_type:
                failures.append("readiness_resource_type_changed")
            operations = (
                {
                    item.capability_operation_id: item
                    for item in definition.capability_card.capability_operations
                }
                if definition.capability_card is not None
                else {}
            )
            operation = operations.get(template.capability_operation_id)
            if operation is None:
                failures.append("readiness_capability_operation_missing")
            elif operation.evidence_status == "unknown":
                failures.append("readiness_capability_evidence_unknown")
            elif operation.entrypoint_id not in {None, entrypoint_id}:
                failures.append("readiness_capability_entrypoint_changed")
            try:
                entrypoint = definition.entrypoint(entrypoint_id)
            except Exception:
                failures.append("readiness_entrypoint_missing")
                entrypoint = None
            application = template.resource_application
            if application is None:
                if template.resource_type in {"Tool", "Resource"}:
                    failures.append("readiness_output_realization_missing")
            elif (
                application.resource_id != template.resource_id
                or application.capability_operation_id
                != template.capability_operation_id
                or application.entrypoint_id != entrypoint_id
                or application.resource_manifest_sha256
                != template.resource_manifest_sha256
            ):
                failures.append("readiness_resource_application_identity_changed")
            elif entrypoint is not None and (
                canonical_sha256(application.operation_input_contract)
                != canonical_sha256(entrypoint.input_contract)
                or canonical_sha256(application.resource_native_output_contract)
                != canonical_sha256(entrypoint.output_contract)
            ):
                failures.append("readiness_resource_application_contract_changed")
            if template.resource_type == "Agent" and not template.agent_base_model_resource_id:
                failures.append("readiness_agent_base_model_missing")
            elif template.resource_type == "Agent":
                base = resource_definitions.get(
                    str(template.agent_base_model_resource_id)
                )
                if base is None or base.resource_type != "Model":
                    failures.append("readiness_agent_base_model_unavailable")
            session_spec = template.controller_session_spec
            if session_spec is not None:
                checks.extend(
                    (
                        "controller_session_identity",
                        "controller_policy_identity",
                        "controller_input_bindings",
                        "controller_output_contract",
                        "controller_backing_model_identity",
                    )
                )
                expected_backing = (
                    template.resource_id
                    if template.resource_type == "Model"
                    else template.agent_base_model_resource_id
                )
                if (
                    template.resource_type not in {"Model", "Agent"}
                    or session_spec.controller_resource_id != template.resource_id
                    or session_spec.controller_resource_type != template.resource_type
                    or session_spec.controller_step_id != template.step_id
                    or session_spec.backing_model_resource_id != expected_backing
                    or session_spec.declared_input_bindings
                    != template.unresolved_typed_bindings
                    or session_spec.expected_output_contract
                    != template.expected_output_contract
                ):
                    failures.append("readiness_controller_session_identity_changed")
                if (
                    session_spec.controller_session_policy_sha256
                    != controller_policy.policy_sha256
                ):
                    failures.append("readiness_controller_policy_identity_changed")
                if isinstance(session_spec, ControllerSessionSpecV2):
                    checks.extend(
                        (
                            "controller_callable_tool_authorization",
                            "controller_callable_tool_manifest_identity",
                            "controller_callable_tool_operation_identity",
                            "controller_callable_tool_port_partition",
                            "controller_callable_tool_result_realization",
                            "controller_applied_tool_calling_capability",
                            "controller_applied_tool_result_continuation_capability",
                            "controller_tool_runtime_protocol",
                        )
                    )
                    recomputed_tools: list[ControllerCallableToolSpecV1] = []
                    for callable_tool in session_spec.callable_tools:
                        callable_definition = resource_definitions.get(
                            callable_tool.resource_id
                        )
                        if (
                            callable_definition is None
                            or callable_tool.resource_id
                            not in lowered.selected_resource_ids
                        ):
                            failures.append(
                                "readiness_controller_callable_tool_unauthorized"
                            )
                            continue
                        try:
                            recomputed = derive_controller_callable_tool_spec(
                                execution_network_required=callable_tool.execution_network_required,
                                definition=callable_definition,
                                capability_operation_id=(
                                    callable_tool.capability_operation_id
                                ),
                                fixed_input_bindings=(
                                    callable_tool.fixed_input_bindings
                                ),
                                dynamic_input_names=tuple(
                                    str(item["name"])
                                    for item in callable_tool.dynamic_input_ports
                                ),
                                capability_evidence_refs=(
                                    callable_tool.capability_evidence_refs
                                ),
                            )
                        except (ControllerToolingError, TypeError, ValueError):
                            failures.append(
                                "readiness_controller_callable_tool_identity_changed"
                            )
                            continue
                        if (
                            recomputed.callable_spec_sha256
                            != callable_tool.callable_spec_sha256
                            or recomputed.provider_tool_schema_sha256
                            != callable_tool.provider_tool_schema_sha256
                        ):
                            failures.append(
                                "readiness_controller_callable_tool_identity_changed"
                            )
                        recomputed_tools.append(recomputed)
                        callable_facts = dict(
                            environment_facts.get(callable_tool.resource_id) or {}
                        )
                        if callable_facts.get("ready") is not True:
                            failures.append(
                                "readiness_controller_callable_tool_unready"
                            )
                            failures.extend(
                                str(item)
                                for item in callable_facts.get("failure_codes") or ()
                            )
                    try:
                        expected_session = derive_controller_session_spec(
                            subtask_id=session_spec.subtask_id,
                            subtask_revision=session_spec.subtask_revision,
                            controller_step_id=template.step_id,
                            controller_resource_id=template.resource_id,
                            controller_resource_type=template.resource_type,
                            backing_model_resource_id=(
                                template.agent_base_model_resource_id
                            ),
                            task_instruction=session_spec.task_instruction,
                            declared_input_bindings=(
                                template.unresolved_typed_bindings
                            ),
                            expected_output_contract=(
                                template.expected_output_contract
                            ),
                            policy=controller_policy,
                            callable_tools=tuple(recomputed_tools),
                            context_bindings=session_spec.context_bindings,
                        )
                    except (TypeError, ValueError):
                        expected_session = None
                    if (
                        expected_session is None
                        or expected_session.spec_sha256 != session_spec.spec_sha256
                    ):
                        failures.append("readiness_controller_session_identity_changed")
                    backing_facts = dict(
                        environment_facts.get(
                            session_spec.backing_model_resource_id
                        )
                        or {}
                    )
                    if backing_facts.get("ready") is not True:
                        failures.append("readiness_controller_backing_model_unready")
                    if not _applied_capability_verified(
                        backing_facts, "tool_calling"
                    ):
                        failures.append(
                            "readiness_controller_tool_calling_capability_unverified"
                        )
                    if not _applied_capability_verified(
                        backing_facts, "tool_result_continuation"
                    ):
                        failures.append(
                            "readiness_controller_tool_result_continuation_capability_unverified"
                        )
                    if (
                        backing_facts.get("controller_tool_runtime_protocol")
                        != CONTROLLER_TOOL_RUNTIME_PROTOCOL
                    ):
                        failures.append(
                            "readiness_controller_tool_runtime_protocol_unverified"
                        )
            elif template.resource_type in {"Model", "Agent"}:
                checks.append("legacy_one_shot_compatibility")
        facts = dict(environment_facts.get(template.resource_id) or {})
        if facts.get("ready") is not True:
            failures.extend(str(item) for item in facts.get("failure_codes") or ())
            if not facts.get("failure_codes"):
                failures.append("readiness_environment_unverified")
        step_results.append(
            PlanReadinessStepV1(
                step_id=template.step_id,
                resource_id=template.resource_id,
                resource_type=template.resource_type,
                entrypoint_id=entrypoint_id,
                status="blocked" if failures else "ready",
                checks=tuple(checks),
                failure_codes=tuple(dict.fromkeys(failures)),
                manifest_sha256=manifest_sha256,
            )
        )
    execution_world_sha256 = canonical_sha256(
        {
            "sandbox_scope_sha256": sandbox_scope_sha256,
            "resource_manifests": {
                resource_id: definition.manifest_sha256
                for resource_id, definition in sorted(resource_definitions.items())
            },
            "environment_facts": {
                key: dict(value) for key, value in sorted(environment_facts.items())
            },
        }
    )
    status = "ready" if step_results and all(
        item.status == "ready" for item in step_results
    ) else "blocked"
    return PlanExecutionReadinessV1(
        run_id=run_id,
        plan_sha256=lowered.plan_sha256,
        candidate_pool_sha256=lowered.candidate_pool_sha256,
        sandbox_scope_sha256=sandbox_scope_sha256,
        execution_world_sha256=execution_world_sha256,
        steps=tuple(step_results),
        status=status,
    )


class SealedPlanExecutionEngine:
    """Validate a sealed artifact and execute its lowered DAG exactly once."""

    def __init__(self, *, run_id: str) -> None:
        self.run_id = run_id

    async def execute(
        self,
        *,
        artifact: SealedPlanCompilationArtifact,
        candidate_resources: Sequence[TypedResourceRef],
        resource_definitions: Mapping[str, ResourceDefinition],
        environment_facts: Mapping[str, Mapping[str, Any]],
        sandbox_scope_sha256: str,
        execute_dag: FormalDagExecutor,
        resume_checkpoints: Sequence[CompletedStepCheckpoint] = (),
        resume_results: Mapping[str, ExecutionResult] | None = None,
    ) -> dict[str, Any]:
        if artifact.run_id != self.run_id:
            raise FormalExecutionError("sealed_plan_run_identity_mismatch")
        if artifact.status != "success" or artifact.executable_plan is None:
            raise FormalExecutionError("sealed_plan_artifact_not_executable")
        if artifact.lowered_plan is None or artifact.lowering_audit is None:
            raise FormalExecutionError("sealed_plan_lowering_missing")
        lowered = LoweredExecutionPlan.model_validate(artifact.lowered_plan)
        plan = artifact.executable_plan
        if not (
            artifact.lowered_plan_semantic_sha256
            == lowered.plan_semantic_sha256
            == plan.plan_sha256
        ):
            raise FormalExecutionError("sealed_plan_semantic_hash_mismatch")
        if artifact.lowering_sha256 != lowered.lowering_sha256:
            raise FormalExecutionError("sealed_plan_lowering_hash_mismatch")

        readiness = build_plan_execution_readiness(
            run_id=artifact.run_id,
            lowered=lowered,
            resource_definitions=resource_definitions,
            sandbox_scope_sha256=sandbox_scope_sha256,
            environment_facts=environment_facts,
        )
        if readiness.status != "ready":
            blocked = sorted(
                {
                    code
                    for step in readiness.steps
                    for code in step.failure_codes
                }
            )
            raise FormalExecutionError(
                "plan_execution_readiness_blocked:" + ",".join(blocked)
            )

        for candidate in candidate_resources:
            definition = resource_definitions.get(candidate.resource_id)
            if definition is not None and definition.resource_type == "Model" and definition.selection_scope != "candidate":
                raise FormalExecutionError("execution_model_not_candidate")
        candidate_ids = tuple(item.resource_id for item in candidate_resources)
        lowered_candidate_ids = (
            lowered.step_templates[0].execution_context_template.candidate_resource_ids
            if lowered.step_templates
            else ()
        )
        if candidate_ids != lowered_candidate_ids:
            raise FormalExecutionError("sealed_plan_candidate_order_mismatch")
        if set(plan.selected_resource_ids) - set(candidate_ids):
            raise FormalExecutionError("sealed_plan_selected_resource_not_in_candidate_pool")
        if tuple(item.step_id for item in lowered.step_templates) != tuple(
            item.step_id for item in plan.steps
        ):
            raise FormalExecutionError("sealed_plan_lowered_step_order_mismatch")
        templates = {item.step_id: item for item in lowered.step_templates}
        for step in plan.steps:
            template = templates[step.step_id]
            if (
                template.resource_id != step.resource_id
                or template.resource_type != step.resource_type
                or template.capability_operation_id != step.capability_operation_id
                or template.satisfied_obligation_ids != step.satisfied_obligation_ids
                or template.entrypoint_id != step.entrypoint_id
                or canonical_sha256(template.unresolved_typed_bindings)
                != canonical_sha256(step.input_bindings)
                or template.consumed_context_source_ids
                != step.consumed_context_source_ids
                or (
                    bool(template.runtime_context_handle_ids)
                    and len(template.runtime_context_handle_ids)
                    != len(step.consumed_context_source_ids)
                )
                or template.edge_contract_sha256s
                != step.consumed_edge_contract_sha256s
                or template.dependency_step_ids != step.depends_on
                or canonical_sha256(template.expected_output_contract)
                != canonical_sha256(
                    step.expected_output_contract.model_dump(mode="json")
                )
                or canonical_sha256(template.resource_application)
                != canonical_sha256(step.resource_application)
                or canonical_sha256(template.controller_session_spec)
                != canonical_sha256(step.controller_session_spec)
                or template.advisory_profile_refs
                != step.advisory_profile_refs
                or template.agent_base_model_resource_id
                != step.agent_base_model_resource_id
                or template.execution_context_template.plan_sha256
                != plan.plan_sha256
                or template.execution_context_template.selected_resource_ids
                != plan.selected_resource_ids
            ):
                raise FormalExecutionError("sealed_plan_lowered_step_identity_mismatch")

        checkpoints = {item.step_id: item for item in resume_checkpoints}
        if len(checkpoints) != len(tuple(resume_checkpoints)):
            raise FormalExecutionError("sealed_plan_duplicate_resume_checkpoint")
        results = dict(resume_results or {})
        if set(results) != set(checkpoints):
            raise FormalExecutionError("sealed_plan_resume_result_set_mismatch")
        plan_steps = {item.step_id: item for item in plan.steps}
        for step_id, checkpoint in checkpoints.items():
            step = plan_steps.get(step_id)
            if step is None:
                raise FormalExecutionError("sealed_plan_resume_step_missing")
            if executable_step_semantic_sha256(step) != checkpoint.step_semantic_sha256:
                raise FormalExecutionError("sealed_plan_resume_step_hash_mismatch")
            result = results[step_id]
            reference = result.cost_metric.get("resource_call_reference")
            if not isinstance(reference, Mapping) or (
                reference.get("call_id") != checkpoint.resource_call_id
                or reference.get("result_sha256") != checkpoint.result_sha256
                or reference.get("started_event_id") != checkpoint.started_event_id
                or reference.get("terminal_event_id") != checkpoint.terminal_event_id
            ):
                raise FormalExecutionError("sealed_plan_resume_result_identity_mismatch")
            if not result.is_success:
                raise FormalExecutionError("sealed_plan_resume_result_not_success")

        formal_plan = _formal_plan(artifact, lowered)
        context = ResourceExecutionContext(
            run_id=artifact.run_id,
            graph_revision=artifact.plan_revision.subtask_revision.graph_revision,
            subtask_id=artifact.plan_revision.subtask_revision.subtask_id,
            subtask_revision=artifact.plan_revision.subtask_revision.subtask_revision,
            candidate_pool_sha256=artifact.candidate_pool_sha256,
            candidate_resource_ids=candidate_ids,
            selected_resource_ids=plan.selected_resource_ids,
            plan_sha256=plan.plan_sha256,
            step_id="plan",
            attempt=max(1, artifact.plan_revision.plan_revision + 1),
            sandbox_scope_sha256=sandbox_scope_sha256,
        )
        result = await execute_dag(formal_plan, context, checkpoints, results)
        result.cost_metric["formal_execution_protocol"] = FORMAL_EXECUTION_PROTOCOL
        return {
            "preflight": {
                "ok": True,
                "protocol": FORMAL_EXECUTION_PROTOCOL,
                "binding_protocol": "binding-protocol-v3",
                "plan_hash": plan.plan_sha256,
                "lowering_audit_sha256": lowered.preflight_audit.audit_sha256,
                "readiness": readiness.model_dump(mode="json"),
            },
            "result": result,
            "plan": plan,
            "plan_immutability": {
                "validated_plan_hash": plan.plan_sha256,
                "preflight_plan_hash": plan.plan_sha256,
                "executed_plan_hash": plan.plan_sha256,
                "passed": True,
            },
            "sealed_plan": {
                "artifact_sha256": artifact.artifact_sha256,
                "validated_plan_sha256": plan.plan_sha256,
                "lowered_plan_semantic_sha256": lowered.plan_semantic_sha256,
                "lowering_sha256": lowered.lowering_sha256,
                "executed_plan_sha256": plan.plan_sha256,
                "formal_execution_request_sha256": canonical_sha256(
                    {
                        "artifact_sha256": artifact.artifact_sha256,
                        "plan_sha256": plan.plan_sha256,
                        "candidate_pool_sha256": artifact.candidate_pool_sha256,
                        "sandbox_scope_sha256": sandbox_scope_sha256,
                    }
                ),
            },
        }


__all__ = [
    "FORMAL_EXECUTION_PROTOCOL",
    "FormalExecutablePlan",
    "FormalExecutableStep",
    "FormalExecutionError",
    "SealedPlanExecutionEngine",
    "build_plan_execution_readiness",
]
