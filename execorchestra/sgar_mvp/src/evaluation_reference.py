"""Deterministic construction of the contract-first evaluation standard."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .evaluation_contracts import (
    ArtifactRevisionRef,
    CriterionSource,
    EvaluationCriterion,
    EvaluationReferenceStandard,
)
from .pipeline_control import canonical_sha256
from .schema import DagEdgeContractV1, Subtask, SubtaskOutputContract


def _criterion_id(source: CriterionSource, index: int, description: str) -> str:
    digest = canonical_sha256(
        {"source": source.value, "index": index, "description": description}
    )[:12]
    return f"{source.value}:{index}:{digest}"


def _append(
    target: list[EvaluationCriterion],
    *,
    source: CriterionSource,
    description: str,
    source_locator: str,
    required: bool = True,
) -> None:
    normalized = str(description or "").strip()
    if not normalized:
        return
    index = sum(1 for item in target if item.source is source)
    target.append(
        EvaluationCriterion(
            criterion_id=_criterion_id(source, index, normalized),
            source=source,
            description=normalized,
            required=required,
            source_locator=source_locator,
        )
    )


def _original_public_consistency_description(subtask: Subtask) -> str:
    """Use only the Planner's declared scope; legacy nodes retain their standard."""
    semantic = subtask.semantic_contract_v2
    if semantic is not None and semantic.output.contract_scope == "intermediate":
        return (
            "Use the original public task as non-contradiction and grounding context, "
            "not as a final-deliverable completeness checklist for this intermediate artifact. "
            "Within this node's declared responsibility, check applicable public-task facts "
            "and explicit constraints, and ground any factual claims in authorized evidence. "
            "When this artifact describes or constrains another result, check that its rules "
            "describe the requested target after the specified transformation, not merely "
            "authentic source values. This is the current document's own semantic duty, not "
            "a demand to produce the later result or perform its delivery. "
            "Compiler implementation choices cannot override Planner requirements or source facts. "
            "Do not require the final deliverable filename, representation or format, complete "
            "field set, later aggregation or composition, sibling work, or downstream consumer "
            "output unless explicitly required by this node's own Planner contract or a formal "
            "downstream edge input contract. Reject supported local conflicts, omissions, and "
            "fabricated facts; identify the conflicting requirement and its responsible stage."
        )
    return ("Within this subtask's declared responsibility, the artifact must satisfy "
            "the original public task's explicit requirements as well as the Planner standard. "
            "Compiler implementation choices cannot override those requirements. Reject a "
            "supported conflict or omission even when the artifact fits its execution schema. "
            "Accept alternative representations when the task leaves them open. Do not require "
            "sibling or downstream work. Identify the conflicting requirement and whether it "
            "comes from planning, the compiled contract, or the produced content.")


def build_evaluation_reference_standard(
    *,
    artifact_revision: ArtifactRevisionRef,
    subtask: Subtask,
    downstream_edge_contracts: Sequence[
        DagEdgeContractV1 | Mapping[str, Any]
    ] = (),
    evaluation_contract: SubtaskOutputContract | Mapping[str, Any] | None = None,
) -> EvaluationReferenceStandard:
    """Project only declared, public requirements into evaluator criteria.

    Universal criteria interpret declared requirements; they never introduce
    style, performance, safety, or feature preferences that the contract did
    not request.
    """

    if evaluation_contract is not None:
        contract = (
            evaluation_contract.model_dump(mode="json")
            if isinstance(evaluation_contract, SubtaskOutputContract)
            else SubtaskOutputContract.model_validate(
                dict(evaluation_contract)
            ).model_dump(mode="json")
        )
    else:
        contract = subtask.output_contract.model_dump(mode="json") if subtask.output_contract else {
            "artifact_type": subtask.artifact_type.value,
            "output_extension": subtask.output_extension,
            "required_content": [],
            "produced_files": [],
            "interface_contract": {},
            "grounding_requirements": [],
            "acceptance_criteria": [],
            "downstream_consumers": list(subtask.depends_on),
        }
    output_contract_sha256 = canonical_sha256(contract)
    # Structural identity belongs to the execution contract; semantic criteria
    # remain owned by the Planner and the original public task.
    macro = subtask.output_contract.model_dump(mode="json") if subtask.output_contract else contract
    criteria: list[EvaluationCriterion] = []

    _append(
        criteria,
        source=CriterionSource.MACHINE_CONTRACT,
        description=(
            "The authoritative machine output contract has already been deterministically "
            "validated and defines the artifact's structural shape. The staged artifact "
            "must retain that contract, content hash, registered handles, and provenance "
            "identity. Structural conformance does not prove satisfaction of the original task."
        ),
        source_locator="output_contract",
    )
    for index, item in enumerate(macro.get("required_content") or ()):
        _append(
            criteria,
            source=CriterionSource.REQUIRED_CONTENT,
            description=str(item),
            source_locator=f"output_contract.required_content[{index}]",
        )
    for index, item in enumerate(macro.get("grounding_requirements") or ()):
        _append(
            criteria,
            source=CriterionSource.GROUNDING_REQUIREMENT,
            description=str(item),
            source_locator=f"output_contract.grounding_requirements[{index}]",
        )
    for index, item in enumerate(macro.get("acceptance_criteria") or ()):
        _append(
            criteria,
            source=CriterionSource.ACCEPTANCE_CRITERION,
            description=str(item),
            source_locator=f"output_contract.acceptance_criteria[{index}]",
        )
    _append(
        criteria,
        source=CriterionSource.EXPECTED_OUTPUT,
        description=subtask.expected_output,
        source_locator="subtask.expected_output",
    )
    _append(
        criteria, source=CriterionSource.UNIVERSAL_CONSISTENCY,
        description=_original_public_consistency_description(subtask),
        source_locator="original_public_objective",
    )
    for index, item in enumerate(downstream_edge_contracts):
        edge = (
            item
            if isinstance(item, DagEdgeContractV1)
            else DagEdgeContractV1.model_validate(item)
        )
        if edge.producer_id != subtask.id:
            continue
        _append(
            criteria,
            source=CriterionSource.DOWNSTREAM_CONTRACT,
            description=(
                "The current artifact must satisfy the declared DAG edge input "
                f"contract for consumer={edge.consumer_id}, input_slot={edge.input_slot}, "
                f"accepted_artifact_types={list(edge.accepted_artifact_types)}, "
                f"accepted_extensions={list(edge.accepted_extensions)}, "
                f"consumption_mode={edge.consumption_mode}, "
                f"required_interface_contract_json={edge.required_interface_contract_json}. This contract "
                "does not constrain the consumer's own output format."
            ),
            source_locator=f"downstream_edge_contracts[{index}]",
        )
    _append(
        criteria,
        source=CriterionSource.UNIVERSAL_CONSISTENCY,
        description=(
            "The artifact must not internally contradict itself or the public "
            "evidence needed to satisfy the criteria above. Check the relationship between "
            "the requested transformation, properties required to remain, and the artifact's "
            "claims or rules. Source authenticity and valid document structure do not establish "
            "that a constraint describes the intended result. Accept task-permitted alternatives "
            "and generality; do not introduce instance-specific limits or downstream duties."
        ),
        source_locator="universal_consistency",
    )
    return EvaluationReferenceStandard(
        artifact_revision=artifact_revision,
        output_contract_sha256=output_contract_sha256,
        criteria=tuple(criteria),
    )


__all__ = ["build_evaluation_reference_standard"]
