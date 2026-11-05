"""Audit execution evidence for an explicitly required task-workspace mutation.

This establishes a successful declared mutator invocation, not the business
correctness of the resulting state. An external verifier or task-specific
acceptance contract remains authoritative for that judgment.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def is_declared_workspace_mutator(resource_id: str, resource_index: Mapping[str, Any]) -> bool:
    manifest = resource_index.get(resource_id)
    if not isinstance(manifest, Mapping) or manifest.get("resource_type") != "Tool":
        return False
    capability = manifest.get("capability")
    semantics = capability.get("execution_semantics") if isinstance(capability, Mapping) else None
    targets = semantics.get("effect_targets") if isinstance(semantics, Mapping) else None
    return (
        isinstance(semantics, Mapping)
        and semantics.get("side_effects") == "declared"
        and isinstance(targets, (list, tuple))
        and "task_workspace" in targets
    )


def _final_dependency_steps(plan: Any) -> tuple[Any, ...] | None:
    steps = {step.step_id: step for step in plan.steps}
    if len(steps) != len(plan.steps):
        return None
    # The sealed compiler plan uses a StepOutputRef; its formal runtime view
    # retains the unique output key. Both must identify the same final producer.
    final_output = getattr(plan, "final_output", None)
    if final_output is not None:
        final_step_id = final_output.step_id
    else:
        final_key = getattr(plan, "final_output_from", None)
        matches = [step.step_id for step in plan.steps if step.output_key == final_key]
        if final_key is None or len(matches) != 1:
            return None
        final_step_id = matches[0]
    closure: set[str] = set()
    pending = [final_step_id]
    while pending:
        step_id = pending.pop()
        if step_id in closure:
            continue
        step = steps.get(step_id)
        if step is None:
            return None
        closure.add(step_id)
        pending.extend(step.depends_on)
    return tuple(step for step in plan.steps if step.step_id in closure)


def audit_workspace_effect_invocation(
    *,
    plan: Any,
    step_trace: Sequence[Mapping[str, Any]],
    resource_index: Mapping[str, Any],
) -> dict[str, Any]:
    """Require one successful selected mutator in the final dependency closure."""

    final_steps = _final_dependency_steps(plan)
    if final_steps is None:
        return {"status": "invalid_plan", "selected_operation_ids": [], "observed_operation_ids": [],
                "semantic_state_verified": False}
    closure = {step.step_id for step in final_steps}
    selected: set[str] = set()
    for step in final_steps:
        if step.resource_type == "Tool" and is_declared_workspace_mutator(step.resource_id, resource_index):
            selected.add(step.capability_operation_id)
        spec = getattr(step, "controller_session_spec", None)
        for callable_tool in getattr(spec, "callable_tools", ()) if spec is not None else ():
            if is_declared_workspace_mutator(callable_tool.resource_id, resource_index):
                selected.add(callable_tool.capability_operation_id)
    observed: set[str] = set()
    for trace in step_trace:
        if trace.get("step_id") not in closure or trace.get("status") not in {"success", "reused"}:
            continue
        if trace.get("status") == "reused":
            reference = trace.get("resource_call_reference")
            if not isinstance(reference, Mapping) or not all(
                reference.get(key)
                for key in ("call_id", "result_sha256", "started_event_id", "terminal_event_id")
            ):
                continue
        if trace.get("resource_type") == "Tool":
            operation_id = str(trace.get("capability_operation_id") or "")
            if operation_id in selected:
                observed.add(operation_id)
        for operation_id in trace.get("successful_tool_operation_ids") or ():
            if operation_id in selected:
                observed.add(operation_id)
    return {
        "status": "invoked_successfully" if observed else "not_observed",
        "selected_operation_ids": sorted(selected),
        "observed_operation_ids": sorted(observed),
        "semantic_state_verified": False,
    }


def required_controller_workspace_operation(
    *,
    plan: Any,
    controller_step: Any,
    step_trace: Sequence[Mapping[str, Any]],
    resource_index: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Bind the effect to its Controller when no static mutator owns the work."""

    final_steps = _final_dependency_steps(plan)
    if final_steps is None or controller_step.step_id not in {
        step.step_id for step in final_steps
    }:
        return None
    # A static mutator may be before or after the Controller. Do not add a
    # redundant mutation call when the Compiler already assigned that work.
    if any(
        step.resource_type == "Tool"
        and is_declared_workspace_mutator(step.resource_id, resource_index)
        for step in final_steps
    ):
        return None

    if audit_workspace_effect_invocation(
        plan=plan, step_trace=step_trace, resource_index=resource_index,
    )["status"] == "invoked_successfully":
        return None
    spec = getattr(controller_step, "controller_session_spec", None)
    callables = tuple(
        item for item in getattr(spec, "callable_tools", ())
        if is_declared_workspace_mutator(item.resource_id, resource_index)
    )
    if not callables:
        return None
    return {
        "operation_kind": "task_workspace_mutation",
        "capability_operation_ids": [item.capability_operation_id for item in callables],
        "function_names": [item.provider_tool_name for item in callables],
    }
