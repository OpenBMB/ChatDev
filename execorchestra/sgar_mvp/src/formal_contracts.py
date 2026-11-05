"""Typed contracts for the deterministic Planner-to-Runtime boundary.

The models in this module deliberately separate the only model-owned semantic
declaration from framework-owned execution obligations and material identity.
No helper in this module parses task prose, filenames, resource IDs, or path
extensions to infer execution policy.
"""

from __future__ import annotations

from typing import Any, Literal, Mapping, Sequence

from pydantic import Field, field_validator, model_validator

from .pipeline_control import FrozenContract, canonical_sha256


SEMANTIC_REQUIREMENT_PROTOCOL = "sgar-semantic-requirement-v1"
EXECUTION_RESOURCE_REQUIREMENT_PROTOCOL = "sgar-execution-resource-requirement-v1"
EXECUTION_OBLIGATION_PROTOCOL = "sgar-execution-obligation-v1"
NODE_SEMANTIC_CONTRACT_PROTOCOL = "sgar-node-semantic-contract-v3"
SEMANTIC_EDGE_CONTRACT_PROTOCOL = "sgar-semantic-edge-contract-v2"
EXECUTION_OBLIGATION_V2_PROTOCOL = "sgar-execution-obligation-v3"
EXECUTABLE_EDGE_CONTRACT_PROTOCOL = "sgar-executable-edge-contract-v2"
MATERIAL_DESCRIPTOR_PROTOCOL = "sgar-material-descriptor-v1"
PLAN_EXECUTION_READINESS_PROTOCOL = "sgar-plan-execution-readiness-v1"


class FormalContractError(ValueError):
    """Stable failure raised when deterministic projection is impossible."""


class SemanticInputReferenceV2(FrozenContract):
    """One Planner-owned semantic input reference, without runtime bindings."""

    source: Literal["public_input", "node_output", "completed_output"]
    ref: str = Field(min_length=1)
    purpose: str = Field(min_length=1)


class SemanticOutputDescriptorV2(FrozenContract):
    """The semantic artifact promised by one Planner node."""

    logical_name: str = Field(min_length=1)
    artifact_type: Literal[
        "code", "json", "csv", "markdown", "plaintext", "file", "directory", "bundle"
    ]
    contract_scope: Literal["intermediate", "final_deliverable"]
    semantic_description: str = Field(min_length=1)
    content_kind: Literal["value", "json_schema_document"] = "value"
    syntax_validator: Literal["python_regex", "python_regex_findall_string", "python_regex_findall_whole_match"] | None = None

    @model_validator(mode="after")
    def _content_kind(self):
        if self.content_kind == "json_schema_document" and self.artifact_type != "json":
            raise ValueError("schema_document_requires_json_artifact")
        if self.syntax_validator in ("python_regex", "python_regex_findall_string", "python_regex_findall_whole_match") and (
            self.artifact_type != "plaintext" or self.content_kind != "value"
        ):
            raise ValueError("python_regex_requires_plaintext_value")
        return self


class NodeSemanticContractV2(FrozenContract):
    """Role-oriented Planner semantics before any resource decision exists."""

    protocol: Literal[NODE_SEMANTIC_CONTRACT_PROTOCOL] = NODE_SEMANTIC_CONTRACT_PROTOCOL
    task_id: str = Field(min_length=1)
    role_intent: str = Field(min_length=1)
    task: str = Field(min_length=1)
    input_requirement: Literal["task_text_only", "requires_material"]
    required_effect: Literal["none", "task_workspace_mutation"] = "none"
    authorized_inputs: tuple[SemanticInputReferenceV2, ...]
    output: SemanticOutputDescriptorV2
    acceptance_conditions: tuple[str, ...] = Field(min_length=1)
    contract_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "NodeSemanticContractV2":
        if (self.input_requirement == "requires_material") != bool(self.authorized_inputs):
            raise ValueError("node_input_requirement_conflicts_with_inputs")
        keys = tuple((item.source, item.ref) for item in self.authorized_inputs)
        if len(keys) != len(set(keys)):
            raise ValueError("node_semantic_input_reference_duplicate")
        expected = canonical_sha256(self.model_dump(mode="python", exclude={"contract_sha256"}))
        if self.contract_sha256 and self.contract_sha256 != expected:
            raise ValueError("node_semantic_contract_sha256_mismatch")
        object.__setattr__(self, "contract_sha256", expected)
        return self


class SemanticEdgeContractV2(FrozenContract):
    """Framework-derived semantic producer/consumer relation."""

    protocol: Literal[SEMANTIC_EDGE_CONTRACT_PROTOCOL] = SEMANTIC_EDGE_CONTRACT_PROTOCOL
    producer_id: str = Field(min_length=1)
    consumer_id: str = Field(min_length=1)
    producer_output_ref: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    artifact_type: str = Field(min_length=1)
    content_kind: Literal["value", "json_schema_document"] = "value"
    edge_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "SemanticEdgeContractV2":
        if self.producer_id == self.consumer_id:
            raise ValueError("semantic_edge_self_dependency")
        expected = canonical_sha256(self.model_dump(mode="python", exclude={"edge_sha256"}))
        if self.edge_sha256 and self.edge_sha256 != expected:
            raise ValueError("semantic_edge_sha256_mismatch")
        object.__setattr__(self, "edge_sha256", expected)
        return self


class ExecutionObligationV2(FrozenContract):
    """Compiler input derived only from one V2 semantic node contract."""

    protocol: Literal[EXECUTION_OBLIGATION_V2_PROTOCOL] = EXECUTION_OBLIGATION_V2_PROTOCOL
    obligation_id: str = Field(min_length=1)
    source_contract_sha256: str
    role_intent: str = Field(min_length=1)
    task_semantics: str = Field(min_length=1)
    input_requirement: Literal["task_text_only", "requires_material"]
    required_effect: Literal["none", "task_workspace_mutation"] = "none"
    authorized_inputs: tuple[SemanticInputReferenceV2, ...]
    required_output_semantics: tuple[str, ...] = Field(min_length=1)
    acceptance_conditions: tuple[str, ...] = Field(min_length=1)
    output_contract_sha256: str
    obligation_sha256: str = ""

    @field_validator("source_contract_sha256", "output_contract_sha256")
    @classmethod
    def _hashes(cls, value: str, info: Any) -> str:
        normalized = str(value).strip().lower()
        if len(normalized) != 64 or any(character not in "0123456789abcdef" for character in normalized):
            raise ValueError(f"{info.field_name}_invalid")
        return normalized

    @model_validator(mode="after")
    def _seal(self) -> "ExecutionObligationV2":
        if (self.input_requirement == "requires_material") != bool(self.authorized_inputs):
            raise ValueError("execution_obligation_input_requirement_conflict")
        expected = canonical_sha256(self.model_dump(mode="python", exclude={"obligation_sha256"}))
        if self.obligation_sha256 and self.obligation_sha256 != expected:
            raise ValueError("execution_obligation_v2_sha256_mismatch")
        object.__setattr__(self, "obligation_sha256", expected)
        return self


class ExecutableEdgeContractV2(FrozenContract):
    """Compiler/lowering-owned binding for one semantic DAG edge."""

    protocol: Literal[EXECUTABLE_EDGE_CONTRACT_PROTOCOL] = EXECUTABLE_EDGE_CONTRACT_PROTOCOL
    semantic_edge_sha256: str
    producer_id: str = Field(min_length=1)
    consumer_id: str = Field(min_length=1)
    source_output_key: str = Field(min_length=1)
    target_step_id: str = Field(min_length=1)
    target_input_port: str = Field(min_length=1)
    transport: Literal["artifact_handle", "context_content"]
    executable_edge_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "ExecutableEdgeContractV2":
        expected = canonical_sha256(
            self.model_dump(mode="python", exclude={"executable_edge_sha256"})
        )
        if self.executable_edge_sha256 and self.executable_edge_sha256 != expected:
            raise ValueError("executable_edge_contract_sha256_mismatch")
        object.__setattr__(self, "executable_edge_sha256", expected)
        return self


def compile_execution_obligation_v2(
    contract: NodeSemanticContractV2 | Mapping[str, Any],
    *,
    output_contract_sha256: str,
) -> ExecutionObligationV2:
    """Compile one V2 node contract without inferring execution character."""

    semantic = (
        contract
        if isinstance(contract, NodeSemanticContractV2)
        else NodeSemanticContractV2.model_validate(contract)
    )
    return ExecutionObligationV2(
        obligation_id=f"obligation:{semantic.task_id}",
        source_contract_sha256=semantic.contract_sha256,
        role_intent=semantic.role_intent,
        task_semantics=semantic.task,
        input_requirement=semantic.input_requirement,
        required_effect=semantic.required_effect,
        authorized_inputs=semantic.authorized_inputs,
        required_output_semantics=(semantic.output.semantic_description,),
        acceptance_conditions=semantic.acceptance_conditions,
        output_contract_sha256=output_contract_sha256,
    )


class SemanticRequirementDeclarationV1(FrozenContract):
    """The minimal, evidence-bound semantic decision emitted by Planner."""

    protocol: Literal[SEMANTIC_REQUIREMENT_PROTOCOL] = SEMANTIC_REQUIREMENT_PROTOCOL
    requirement_id: str = Field(min_length=1, pattern=r"^[A-Za-z][A-Za-z0-9_.:-]*$")
    source_clause_ids: tuple[str, ...] = Field(min_length=1)
    status: Literal["expressible", "not_expressible"]
    work_nature: Literal["deterministic", "generative", "hybrid"]
    material_coverage: Literal["complete", "authorized_subset"]
    verification: Literal["required", "not_required"]
    side_effect_policy: Literal["none", "declared_only"]
    input_semantics: tuple[str, ...] = ()
    output_semantics: tuple[str, ...] = Field(min_length=1)
    acceptance_conditions: tuple[str, ...] = Field(min_length=1)
    evidence_source_ids: tuple[str, ...] = ()
    unexpressible_reason: str | None = None

    @field_validator(
        "source_clause_ids",
        "input_semantics",
        "output_semantics",
        "acceptance_conditions",
        "evidence_source_ids",
    )
    @classmethod
    def _unique_nonempty(cls, value: tuple[str, ...], info: Any) -> tuple[str, ...]:
        normalized = tuple(str(item).strip() for item in value)
        if any(not item for item in normalized):
            raise ValueError(f"semantic_requirement_{info.field_name}_empty")
        if len(normalized) != len(set(normalized)):
            raise ValueError(f"semantic_requirement_{info.field_name}_duplicate")
        return normalized

    @model_validator(mode="after")
    def _status_shape(self) -> "SemanticRequirementDeclarationV1":
        reason = str(self.unexpressible_reason or "").strip() or None
        if self.status == "expressible" and reason is not None:
            raise ValueError("expressible_requirement_has_unexpressible_reason")
        if self.status == "not_expressible" and reason is None:
            raise ValueError("unexpressible_requirement_reason_missing")
        object.__setattr__(self, "unexpressible_reason", reason)
        return self


class ExecutionResourceRequirementV1(FrozenContract):
    """One user-declared, evidence-bound resource or collaboration constraint."""

    protocol: Literal[EXECUTION_RESOURCE_REQUIREMENT_PROTOCOL] = (
        EXECUTION_RESOURCE_REQUIREMENT_PROTOCOL
    )
    requirement_id: str = Field(min_length=1, pattern=r"^[A-Za-z][A-Za-z0-9_.:-]*$")
    source_clause_ids: tuple[str, ...] = Field(min_length=1)
    relation: Literal[
        "direct_executor",
        "agent_base_model",
        "controller_callable_tool",
        "advisory_skill",
    ]
    resource_type: Literal["Model", "Agent", "Tool", "Skill"]
    resource_id: str | None = None
    api_model_id: str | None = None
    operation_id: str | None = None
    required: Literal[True] = True

    @field_validator("source_clause_ids")
    @classmethod
    def _source_clauses(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(str(item).strip() for item in value)
        if any(not item for item in normalized) or len(normalized) != len(set(normalized)):
            raise ValueError("execution_requirement_source_clause_ids_invalid")
        return normalized

    @field_validator("resource_id", "api_model_id", "operation_id")
    @classmethod
    def _optional_identity(cls, value: str | None) -> str | None:
        normalized = str(value or "").strip()
        return normalized or None

    @model_validator(mode="after")
    def _relation_shape(self) -> "ExecutionResourceRequirementV1":
        expected_type = {
            "agent_base_model": "Model",
            "controller_callable_tool": "Tool",
            "advisory_skill": "Skill",
        }.get(self.relation)
        if expected_type is not None and self.resource_type != expected_type:
            raise ValueError("execution_requirement_relation_type_mismatch")
        if self.api_model_id is not None and self.resource_type != "Model":
            raise ValueError("execution_requirement_api_identity_requires_model")
        if self.relation == "advisory_skill" and self.operation_id is not None:
            raise ValueError("execution_requirement_skill_operation_unsupported")
        return self


class ExecutionObligationV1(FrozenContract):
    """Framework-owned operational consequence of one semantic declaration."""

    protocol: Literal[EXECUTION_OBLIGATION_PROTOCOL] = EXECUTION_OBLIGATION_PROTOCOL
    obligation_id: str = Field(min_length=1)
    source_requirement_id: str = Field(min_length=1)
    source_clause_ids: tuple[str, ...]
    work_nature: Literal["deterministic", "generative", "hybrid"]
    material_coverage: Literal["complete", "authorized_subset"]
    verification: Literal["required", "not_required"]
    side_effect_policy: Literal["none", "declared_only"]
    required_input_semantics: tuple[str, ...]
    required_output_semantics: tuple[str, ...]
    acceptance_conditions: tuple[str, ...]
    required_evidence_source_ids: tuple[str, ...]
    output_contract_sha256: str
    obligation_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "ExecutionObligationV1":
        projected = self.model_dump(mode="python", exclude={"obligation_sha256"})
        expected = canonical_sha256(projected)
        if self.obligation_sha256 and self.obligation_sha256 != expected:
            raise ValueError("execution_obligation_sha256_mismatch")
        object.__setattr__(self, "obligation_sha256", expected)
        return self


def compile_execution_obligations(
    requirements: Sequence[SemanticRequirementDeclarationV1 | Mapping[str, Any]],
    *,
    output_contract_sha256: str,
) -> tuple[ExecutionObligationV1, ...]:
    """Compile typed declarations without inspecting free-form task language."""

    declarations = tuple(
        item
        if isinstance(item, SemanticRequirementDeclarationV1)
        else SemanticRequirementDeclarationV1.model_validate(item)
        for item in requirements
    )
    if not declarations:
        raise FormalContractError("planner_semantic_requirements_missing")
    ids = tuple(item.requirement_id for item in declarations)
    if len(ids) != len(set(ids)):
        raise FormalContractError("planner_semantic_requirement_id_duplicate")
    blocked = tuple(item for item in declarations if item.status == "not_expressible")
    if blocked:
        raise FormalContractError("planner_contract_not_expressible")
    return tuple(
        ExecutionObligationV1(
            obligation_id=f"obligation:{item.requirement_id}",
            source_requirement_id=item.requirement_id,
            source_clause_ids=tuple(item.source_clause_ids),
            work_nature=item.work_nature,
            material_coverage=item.material_coverage,
            verification=item.verification,
            side_effect_policy=item.side_effect_policy,
            required_input_semantics=tuple(item.input_semantics),
            required_output_semantics=tuple(item.output_semantics),
            acceptance_conditions=tuple(item.acceptance_conditions),
            required_evidence_source_ids=tuple(item.evidence_source_ids),
            output_contract_sha256=output_contract_sha256,
        )
        for item in declarations
    )


class MaterialDescriptorV1(FrozenContract):
    """Content identity plus explicit projection coverage for one material."""

    protocol: Literal[MATERIAL_DESCRIPTOR_PROTOCOL] = MATERIAL_DESCRIPTOR_PROTOCOL
    source_id: str = Field(min_length=1)
    logical_name: str = Field(min_length=1)
    artifact_type: str = Field(min_length=1)
    mime_type: str | None = None
    schema_id: str | None = None
    content_sha256: str
    original_bytes: int = Field(ge=0)
    included_bytes: int = Field(ge=0)
    included_sha256: str | None = None
    coverage_status: Literal["complete", "partial", "handle_only"]
    handle_id: str | None = None
    runtime_path: str | None = None
    utf8_decodable: bool | None = None
    descriptor_sha256: str = ""

    @field_validator("content_sha256", "included_sha256")
    @classmethod
    def _hashes(cls, value: str | None, info: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value).lower()
        if len(normalized) != 64 or any(c not in "0123456789abcdef" for c in normalized):
            raise ValueError(f"material_{info.field_name}_invalid")
        return normalized

    @model_validator(mode="after")
    def _shape_and_seal(self) -> "MaterialDescriptorV1":
        if self.coverage_status == "complete":
            if self.included_bytes != self.original_bytes:
                raise ValueError("complete_material_byte_count_mismatch")
            if self.included_sha256 != self.content_sha256:
                raise ValueError("complete_material_hash_mismatch")
        elif self.coverage_status == "partial":
            if not 0 < self.included_bytes < self.original_bytes:
                raise ValueError("partial_material_byte_count_invalid")
            if self.included_sha256 is None:
                raise ValueError("partial_material_hash_missing")
        else:
            if self.included_bytes != 0 or self.included_sha256 is not None:
                raise ValueError("handle_only_material_has_inline_bytes")
            if self.handle_id is None:
                raise ValueError("handle_only_material_handle_missing")
        projected = self.model_dump(mode="python", exclude={"descriptor_sha256"})
        expected = canonical_sha256(projected)
        if self.descriptor_sha256 and self.descriptor_sha256 != expected:
            raise ValueError("material_descriptor_sha256_mismatch")
        object.__setattr__(self, "descriptor_sha256", expected)
        return self


class PlanReadinessStepV1(FrozenContract):
    step_id: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    resource_type: str = Field(min_length=1)
    entrypoint_id: str = Field(min_length=1)
    status: Literal["ready", "blocked"]
    checks: tuple[str, ...]
    failure_codes: tuple[str, ...] = ()
    manifest_sha256: str


class PlanExecutionReadinessV1(FrozenContract):
    """Immutable pre-execution admission bound to Plan and environment identity."""

    protocol: Literal[PLAN_EXECUTION_READINESS_PROTOCOL] = PLAN_EXECUTION_READINESS_PROTOCOL
    run_id: str = Field(min_length=1)
    plan_sha256: str
    candidate_pool_sha256: str
    sandbox_scope_sha256: str
    execution_world_sha256: str
    steps: tuple[PlanReadinessStepV1, ...]
    status: Literal["ready", "blocked"]
    readiness_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "PlanExecutionReadinessV1":
        expected_status = "ready" if self.steps and all(
            item.status == "ready" for item in self.steps
        ) else "blocked"
        if self.status != expected_status:
            raise ValueError("plan_readiness_status_mismatch")
        projected = self.model_dump(mode="python", exclude={"readiness_sha256"})
        expected = canonical_sha256(projected)
        if self.readiness_sha256 and self.readiness_sha256 != expected:
            raise ValueError("plan_readiness_sha256_mismatch")
        object.__setattr__(self, "readiness_sha256", expected)
        return self


__all__ = [
    "EXECUTABLE_EDGE_CONTRACT_PROTOCOL",
    "EXECUTION_OBLIGATION_PROTOCOL",
    "EXECUTION_OBLIGATION_V2_PROTOCOL",
    "MATERIAL_DESCRIPTOR_PROTOCOL",
    "NODE_SEMANTIC_CONTRACT_PROTOCOL",
    "PLAN_EXECUTION_READINESS_PROTOCOL",
    "SEMANTIC_EDGE_CONTRACT_PROTOCOL",
    "SEMANTIC_REQUIREMENT_PROTOCOL",
    "ExecutableEdgeContractV2",
    "ExecutionObligationV1",
    "ExecutionObligationV2",
    "FormalContractError",
    "MaterialDescriptorV1",
    "NodeSemanticContractV2",
    "PlanExecutionReadinessV1",
    "PlanReadinessStepV1",
    "SemanticEdgeContractV2",
    "SemanticInputReferenceV2",
    "SemanticOutputDescriptorV2",
    "SemanticRequirementDeclarationV1",
    "compile_execution_obligation_v2",
    "compile_execution_obligations",
]
