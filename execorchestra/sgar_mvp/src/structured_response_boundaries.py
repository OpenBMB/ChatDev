"""Executable call-contract registry for structured-response model boundaries."""

from __future__ import annotations

import importlib
import inspect
import json
from dataclasses import dataclass
from typing import Any, cast

from .model_response_contracts import (
    StructuredResponseMode,
    system_role_requirement,
    system_role_response_format,
    validate_structured_response_content,
)
from .model_transport import (
    SyncModelTransportPort,
    model_request_sha256,
    require_sync_model_transport,
)
from .pipeline_control import canonical_sha256


STRUCTURED_RESPONSE_BOUNDARY_PROTOCOL = "sgar-structured-response-boundaries-v1"


@dataclass(frozen=True)
class StructuredResponseBoundary:
    role: str
    module: str
    qualname: str
    positional_parameter_count: int
    keyword_parameters: tuple[str, ...]
    mode_source: str
    response_model: str
    prompt_builder: str
    invariant_registry: str
    post_validator: str
    projector: str
    responsibility_contract: tuple[str, ...]
    registered_model_validators: tuple[str, ...] = ()

    @property
    def target(self) -> str:
        return f"{self.module}:{self.qualname}"


STRUCTURED_RESPONSE_BOUNDARIES = (
    StructuredResponseBoundary(
        role="planner",
        module="sgar_mvp.src.planner",
        qualname="SGARPlanner.__init__",
        positional_parameter_count=2,
        keyword_parameters=("transport", "response_mode"),
        mode_source="response_mode",
        response_model="PlannerOutput",
        prompt_builder="SGARPlanner",
        invariant_registry="planner_contract_invariants",
        post_validator="PlannerContractGate",
        projector="PlannerContractProjectionV1",
        responsibility_contract=("model", "framework", "normalization"),
    ),
    StructuredResponseBoundary(
        role="hyde",
        module="sgar_mvp.src.retrieval_runtime",
        qualname="_default_profile_generator",
        positional_parameter_count=1,
        keyword_parameters=("cost_ledger", "revision", "transport", "response_mode"),
        mode_source="response_mode",
        response_model="hyde_profile_schema",
        prompt_builder="generate_hyde_profile_text",
        invariant_registry="hyde_profile_contract",
        post_validator="validate_structured_response_content",
        projector="none",
        responsibility_contract=("model", "framework"),
    ),
    StructuredResponseBoundary(
        role="router_policy",
        module="sgar_mvp.src.router",
        qualname="build_plan_compiler_call_kwargs",
        positional_parameter_count=1,
        keyword_parameters=("model_id", "response_mode", "portable_schema"),
        mode_source="response_mode",
        response_model="BundleAdequacyDecision",
        prompt_builder="build_plan_compiler_call_kwargs",
        invariant_registry="router_policy_contract",
        post_validator="BundleAdequacyDecision",
        projector="none",
        responsibility_contract=("model", "framework"),
    ),
    StructuredResponseBoundary(
        role="plan_compiler",
        module="sgar_mvp.src.plan_compiler",
        qualname="build_plan_compiler_call_kwargs",
        positional_parameter_count=1,
        keyword_parameters=("response_mode",),
        mode_source="response_mode",
        response_model="CompilerDecisionProposalV3",
        prompt_builder="build_plan_compiler_call_kwargs",
        invariant_registry="CompilerInvariantCatalogV2",
        post_validator=(
            "CompilerDecisionProposalV3._shape+require_compiler_proposal_invariants"
        ),
        projector="project_compiler_decision_v3+project_compiler_plan_proposal",
        responsibility_contract=("model", "framework", "normalization"),
        registered_model_validators=("_shape",),
    ),
    StructuredResponseBoundary(
        role="plan_adaptation",
        module="sgar_mvp.src.plan_compiler",
        qualname="build_plan_adaptation_call_kwargs",
        positional_parameter_count=1,
        keyword_parameters=("response_mode",),
        mode_source="adaptation_response_mode",
        response_model="PlanAdaptationDecisionV3",
        prompt_builder="build_plan_adaptation_call_kwargs",
        invariant_registry="CompilerInvariantCatalogV2+adaptation_lineage",
        post_validator="PlanAdaptationDecisionV3._live_adaptation_shape+validate_adaptation_decision_identity+require_compiler_proposal_invariants+validate_adapted_plan_lineage",
        projector="project_compiler_decision_v3+project_compiler_plan_proposal",
        responsibility_contract=("model", "framework", "normalization"),
        registered_model_validators=("_live_adaptation_shape",),
    ),
    StructuredResponseBoundary(
        role="evaluator",
        module="sgar_mvp.src.evaluation_runtime",
        qualname="resolve_evaluator_model",
        positional_parameter_count=0,
        keyword_parameters=(
            "policy",
            "pricing_catalog",
            "manifest",
            "availability_status",
            "response_mode",
        ),
        mode_source="response_mode",
        response_model="EvaluationAssessmentProposalV2",
        prompt_builder="build_evaluation_call_contract",
        invariant_registry="evaluation_slot_invariant_catalog_v2",
        post_validator="project_evaluation_assessment",
        projector="project_evaluation_assessment",
        responsibility_contract=("model", "framework"),
    ),
    StructuredResponseBoundary(
        role="full_generation",
        module="sgar_mvp.src.full_generation",
        qualname="build_full_generation_call_kwargs",
        positional_parameter_count=1,
        keyword_parameters=(),
        mode_source="envelope.system_policy.response_mode",
        response_model="FullGenerationDraft",
        prompt_builder="build_full_generation_call_kwargs",
        invariant_registry="full_generation_contract",
        post_validator="validate_structured_response_content",
        projector="none",
        responsibility_contract=("model", "framework"),
    ),
    StructuredResponseBoundary(
        role="temporary_tool",
        module="sgar_mvp.src.temporary_tool",
        qualname="TemporaryToolGenerator.__init__",
        positional_parameter_count=1,
        keyword_parameters=(
            "transport",
            "cost_ledger",
            "pricing_catalog",
            "response_mode",
        ),
        mode_source="response_mode",
        response_model="TemporaryToolGenerationDraft",
        prompt_builder="TemporaryToolGenerator",
        invariant_registry="temporary_tool_contract",
        post_validator="validate_structured_response_content",
        projector="TemporaryToolArtifact",
        responsibility_contract=("model", "framework"),
    ),
)


def _resolve_target(boundary: StructuredResponseBoundary) -> Any:
    target: Any = importlib.import_module(boundary.module)
    for component in boundary.qualname.split("."):
        target = getattr(target, component)
    return target


def _resolve_response_model(boundary: StructuredResponseBoundary) -> Any | None:
    model_targets = {
        "PlannerOutput": ("sgar_mvp.src.schema", "PlannerOutput"),
        "BundleAdequacyDecision": ("sgar_mvp.src.schema", "BundleAdequacyDecision"),
        "CompilerPlanProposalV2": (
            "sgar_mvp.src.executable_plan",
            "CompilerPlanProposalV2",
        ),
        "CompilerDecisionProposalV3": (
            "sgar_mvp.src.executable_plan",
            "CompilerDecisionProposalV3",
        ),
        "PlanAdaptationDecisionV3": (
            "sgar_mvp.src.recovery_control",
            "PlanAdaptationDecisionV3",
        ),
        "PlanAdaptationProposalV2": (
            "sgar_mvp.src.recovery_control",
            "PlanAdaptationProposalV2",
        ),
        "EvaluationAssessmentProposalV2": (
            "sgar_mvp.src.evaluation_runtime",
            "EvaluationAssessmentProposalV2",
        ),
        "FullGenerationDraft": ("sgar_mvp.src.recovery_control", "FullGenerationDraft"),
        "TemporaryToolGenerationDraft": (
            "sgar_mvp.src.temporary_tool",
            "TemporaryToolGenerationDraft",
        ),
    }
    target = model_targets.get(boundary.response_model)
    if target is None:
        return None
    return getattr(importlib.import_module(target[0]), target[1])


def validate_structured_response_boundaries() -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for boundary in STRUCTURED_RESPONSE_BOUNDARIES:
        try:
            target = _resolve_target(boundary)
            signature = inspect.signature(target)
            positional = [object() for _ in range(boundary.positional_parameter_count)]
            keywords = {name: object() for name in boundary.keyword_parameters}
            signature.bind(*positional, **keywords)
            response_model = _resolve_response_model(boundary)
            actual_validators = (
                tuple(response_model.__pydantic_decorators__.model_validators)
                if response_model is not None
                else ()
            )
            if actual_validators != boundary.registered_model_validators:
                raise ValueError("structured_response_hidden_model_validator")
            record = {
                "role": boundary.role,
                "target": boundary.target,
                "mode_source": boundary.mode_source,
                "formal_keyword_parameters": list(boundary.keyword_parameters),
                "signature_sha256": canonical_sha256(str(signature)),
                "response_model": boundary.response_model,
                "prompt_builder": boundary.prompt_builder,
                "invariant_registry": boundary.invariant_registry,
                "post_validator": boundary.post_validator,
                "projector": boundary.projector,
                "responsibility_contract": list(boundary.responsibility_contract),
                "registered_model_validators": list(
                    boundary.registered_model_validators
                ),
                "valid": True,
            }
        except Exception as exc:
            record = {
                "role": boundary.role,
                "target": boundary.target,
                "mode_source": boundary.mode_source,
                "formal_keyword_parameters": list(boundary.keyword_parameters),
                "exception_type": type(exc).__name__,
                "message_sha256": canonical_sha256(str(exc)),
                "valid": False,
            }
        records.append(record)
    projection = {
        "protocol": STRUCTURED_RESPONSE_BOUNDARY_PROTOCOL,
        "records": records,
    }
    return {
        **projection,
        "valid": all(record["valid"] for record in records),
        "boundary_count": len(records),
        "audit_sha256": canonical_sha256(projection),
    }


def probe_structured_response_boundary_transport(
    transport: SyncModelTransportPort,
) -> dict[str, Any]:
    typed_transport = require_sync_model_transport(transport)
    binding = validate_structured_response_boundaries()
    if not binding["valid"]:
        return {
            "protocol": STRUCTURED_RESPONSE_BOUNDARY_PROTOCOL,
            "valid": False,
            "binding": binding,
            "records": [],
            "fake_transport_call_count": 0,
        }
    records: list[dict[str, Any]] = []
    fake_transport_call_count = 0
    for boundary in STRUCTURED_RESPONSE_BOUNDARIES:
        requirement = system_role_requirement(boundary.role)
        for mode in cast(
            tuple[StructuredResponseMode, StructuredResponseMode],
            (
            "native_strict_schema",
            "json_object_local_validator",
            ),
        ):
            selected_mode = mode
            projection = requirement.portable_wire_schema
            if (
                selected_mode == "native_strict_schema"
                and (projection is None or not projection.native_eligible)
            ):
                records.append(
                    {
                        "role": boundary.role,
                        "mode": selected_mode,
                        "request_sha256": None,
                        "wire_schema_sha256": requirement.wire_schema_sha256,
                        "response_format_type": "",
                        "outcome": "preflight_not_native_eligible",
                        "valid": True,
                    }
                )
                continue
            response_format = system_role_response_format(
                boundary.role,
                mode=selected_mode,
            )
            request: dict[str, Any] = {
                "model": "structured-boundary-model",
                "messages": [
                    {
                        "role": "user",
                        "content": json.dumps(
                            {"role": boundary.role, "mode": selected_mode},
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    }
                ],
                "response_format": response_format,
                "stream": False,
            }
            request_sha256 = model_request_sha256(request)
            response = typed_transport.send(**request)
            fake_transport_call_count += 1
            content = str(response.choices[0].message.content or "")
            validate_structured_response_content(
                content,
                requirement=requirement,
                mode=selected_mode,
            )
            records.append(
                {
                    "role": boundary.role,
                    "mode": selected_mode,
                    "request_sha256": request_sha256,
                    "wire_schema_sha256": requirement.wire_schema_sha256,
                    "response_format_type": response_format["type"],
                    "outcome": "validated",
                    "valid": True,
                }
            )
    projection = {
        "protocol": STRUCTURED_RESPONSE_BOUNDARY_PROTOCOL,
        "binding_audit_sha256": binding["audit_sha256"],
        "records": records,
    }
    return {
        **projection,
        "valid": len(records) == len(STRUCTURED_RESPONSE_BOUNDARIES) * 2,
        "binding": binding,
        "fake_transport_call_count": fake_transport_call_count,
        "audit_sha256": canonical_sha256(projection),
    }


def main() -> int:
    report = validate_structured_response_boundaries()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "STRUCTURED_RESPONSE_BOUNDARIES",
    "STRUCTURED_RESPONSE_BOUNDARY_PROTOCOL",
    "StructuredResponseBoundary",
    "probe_structured_response_boundary_transport",
    "validate_structured_response_boundaries",
]
