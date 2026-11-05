"""Explicit input admission and constraint attribution; no inference from task prose."""
from __future__ import annotations
from typing import Literal
from pydantic import Field, model_validator
from .pipeline_control import FrozenContract


class MissingInputInformation(FrozenContract):
    requirement_ref: str = Field(min_length=1)
    missing_information: str = Field(min_length=1)


class CompilerInputAssessment(FrozenContract):
    sufficient: bool
    missing_information: tuple[MissingInputInformation, ...]

    @model_validator(mode="after")
    def _shape(self):
        if self.sufficient == bool(self.missing_information):
            raise ValueError("compiler_input_assessment_missing_information_conflict")
        return self


class ConstraintBasis(FrozenContract):
    step_id: str = Field(min_length=1)
    scope: Literal["execution_contract", "artifact_content"]
    # Response-relative path for execution contracts, JSON pointer for document content.
    constraint_path: tuple[str, ...] = Field(min_length=1)
    category: Literal["task_requirement", "material_fact", "implementation_choice"]
    requirement_refs: tuple[str, ...]
    source_ids: tuple[str, ...]
    explanation: str = Field(min_length=1)

    @model_validator(mode="after")
    def _basis_shape(self):
        if self.category == "task_requirement":
            valid = bool(self.requirement_refs) and not self.source_ids
        elif self.category == "material_fact":
            valid = bool(self.source_ids) and not self.requirement_refs
        else:
            valid = not self.source_ids and not self.requirement_refs
        if not valid:
            raise ValueError("compiler_constraint_basis_category_conflict")
        return self


def requirement_catalog(envelope):
    """Stable local references to existing requirements; no new acceptance conditions."""
    result = {}
    for o in envelope.execution_obligations:
        task = getattr(o, "task_semantics", None)
        if task:
            result[o.obligation_id + ":task"] = task
        for i, text in enumerate(o.acceptance_conditions):
            result[f"{o.obligation_id}:acceptance:{i}"] = text
        for i, text in enumerate(getattr(o, "required_output_semantics", ())):
            result[f"{o.obligation_id}:output:{i}"] = text
    return result


def _reject(code, path, expected, actual, *, stage="plan_compiler_projection", framework=False):
    from .executable_plan import CompilerSchemaProjectionError
    from .compiler_invariants import CompilerProposalValidationIssueV1
    issue = CompilerProposalValidationIssueV1(
        invariant_id=code, failure_code=code, failure_layer="selection",
        path=tuple(str(x) for x in path), expected_active_fields=(expected,),
        observed_active_fields=(actual,), authority_source="Planner.input_requirement / authorized inputs / requirement_catalog",
        responsibility_stage=stage,
    )
    raise CompilerSchemaProjectionError(code, origin=issue.authority_source,
        responsibility="framework" if framework else "research", contract_path=".".join(issue.path),
        actual_type="invariant_violation", issues=(issue,))


def validate_authoritative_input_requirements(envelope):
    semantic = envelope.contract_projection.semantic_contract_v2
    if semantic is None:  # Explicit legacy requirement contracts remain a separate path.
        return
    requirement = getattr(semantic, "input_requirement", None)
    if requirement not in {"requires_material", "task_text_only"}:
        _reject("compiler_authoritative_input_requirement_missing", ("execution_obligations",),
                "Planner must supply input_requirement; start a new run for old state", "missing", framework=True)
    if (requirement == "requires_material") != bool(semantic.authorized_inputs):
        _reject("planner_input_requirement_conflicts_with_inputs", ("execution_obligations",),
                "requires_material needs declared inputs; task_text_only has no materials", requirement, framework=True)
    obligations = envelope.execution_obligations
    if len(obligations) != 1 or getattr(obligations[0], "input_requirement", None) != requirement or obligations[0].authorized_inputs != semantic.authorized_inputs:
        _reject("compiler_authoritative_input_projection_mismatch", ("execution_obligations",),
                "carry the Planner input declaration unchanged", "inconsistent projection", framework=True)
    if getattr(obligations[0], "required_effect", "none") != getattr(semantic, "required_effect", "none"):
        _reject("compiler_authoritative_effect_projection_mismatch", ("execution_obligations",),
                "carry the Planner required state effect unchanged", "inconsistent effect projection", framework=True)


def consumed_materials(decision, step_id):
    """Dataflow closure, not mere scheduling ancestors."""
    steps = {s.step_id:s for s in decision.steps}
    seen, result = set(), set()
    def visit(sid):
        if sid in seen or sid not in steps:
            return
        seen.add(sid)
        for mapping in steps[sid].input_mappings:
            if mapping.source_kind == "artifact_handle":
                result.add(mapping.source_id)
            elif mapping.source_kind == "step_output":
                visit(mapping.from_step)
    visit(step_id)
    return result


def validate_input_alignment(decision, envelope):
    validate_authoritative_input_requirements(envelope)
    requirements = requirement_catalog(envelope)
    for i, gap in enumerate(decision.input_assessment.missing_information):
        if gap.requirement_ref not in requirements:
            _reject("compiler_input_gap_requirement_unknown", ("input_assessment", "missing_information", i, "requirement_ref"),
                    "reference an entry in requirement_catalog", gap.requirement_ref)
    if not decision.input_assessment.sufficient:
        _reject("required_input_missing", ("input_assessment", "missing_information"),
                "the Planner must authorize the material needed by these requirements before a new run", 
                "; ".join(g.requirement_ref + ": " + g.missing_information for g in decision.input_assessment.missing_information), stage="planner_input_declaration")


def alignment_evidence(decision, envelope):
    return {"protocol":"sgar-input-alignment-v1",
            "input_requirement":getattr(envelope.contract_projection.semantic_contract_v2, "input_requirement", None),
            "input_assessment":decision.input_assessment.model_dump(mode="json"),
            "constraint_basis":[],
            "requirement_catalog":requirement_catalog(envelope),
            "evidence_status":"input_admission_checked_basis_unused_not_factual_truth"}
