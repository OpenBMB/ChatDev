"""Shared, machine-readable invariants for Compiler proposal validation.

This module intentionally depends only on pipeline-control primitives.  It is
used by the prompt builder, response validator, correction diagnostics, and
structural validator without importing the executable-plan model graph.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any, Literal, Mapping, Sequence

from pydantic import Field, model_validator

from .pipeline_control import FrozenContract, canonical_json_bytes, canonical_sha256
from .path_policy import is_private_host_path_value


COMPILER_INVARIANT_CATALOG_PROTOCOL = "sgar-compiler-invariant-catalog-v2"
COMPILER_NORMALIZATION_AUDIT_PROTOCOL = "sgar-compiler-proposal-normalization-audit-v1"
COMPILER_VALIDATION_ISSUE_PROTOCOL = "sgar-compiler-proposal-validation-issue-v2"
COMPILER_CORRECTION_VIEW_PROTOCOL = "sgar-compiler-proposal-correction-view-v1"
COMPILER_CONSTRAINT_PROJECTION_PROTOCOL = "sgar-compiler-constraint-projection-v4"
COMPILER_SAFE_ISSUE_AUDIT_PROTOCOL = "sgar-compiler-safe-issue-audit-v2"
INITIAL_COMPILER_MODEL_INVARIANT_PROTOCOL = (
    "sgar-initial-compiler-model-invariant-catalog-v3"
)
ADAPTATION_MODEL_INVARIANT_PROTOCOL = (
    "sgar-adaptation-model-invariant-catalog-v3"
)

_CANONICAL_STEP_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
_BINDING_VALUE_FIELDS = (
    "literal_json",
    "source_id",
    "from_step",
    "output_key",
    "logical_path",
    "value_path",
)
_BINDING_EXPECTED_FIELDS: dict[str, frozenset[str]] = {
    "literal": frozenset({"literal_json"}),
    "artifact_handle": frozenset({"source_id"}),
    "resource": frozenset({"source_id"}),
    "step_output": frozenset({"from_step", "output_key"}),
    "logical_path": frozenset({"logical_path"}),
}


def _strict_json_loads(value: str) -> Any:
    def reject_constant(token: str) -> None:
        raise ValueError(f"non_finite_json_number:{token}")

    return json.loads(value, parse_constant=reject_constant)


class CompilerInvariantRuleV2(FrozenContract):
    invariant_id: str = Field(min_length=1)
    responsibility: Literal["model", "framework", "normalization"]
    applicable_paths: tuple[str, ...]
    condition: dict[str, Any]
    expected_state: dict[str, Any]
    failure_layer: Literal[
        "protocol",
        "selection",
        "connection",
        "executability",
        "framework",
        "normalization",
    ]
    failure_code: str = Field(min_length=1)
    safe_correction: str = Field(min_length=1)
    allow_lossless_normalization: bool = False


class CompilerInvariantCatalogV2(FrozenContract):
    protocol: Literal[COMPILER_INVARIANT_CATALOG_PROTOCOL] = (
        COMPILER_INVARIANT_CATALOG_PROTOCOL
    )
    candidate_resource_types: dict[str, str]
    allowed_operation_kinds: dict[str, tuple[str, ...]]
    tool_entrypoints: dict[str, tuple[dict[str, Any], ...]]
    agent_base_models: dict[str, tuple[str, ...]]
    application_profiles: dict[str, tuple[str, ...]]
    output_format_contracts: dict[str, Any]
    resource_output_contracts: dict[str, Any]
    resource_runtime_requirements: dict[str, Any]
    runtime_capabilities: dict[str, Any]
    final_artifact_contract: dict[str, Any]
    capability_operations: dict[str, tuple[dict[str, Any], ...]] = Field(
        default_factory=dict
    )
    execution_obligations: tuple[dict[str, Any], ...] = ()
    materials: tuple[dict[str, Any], ...] = ()
    rules: tuple[CompilerInvariantRuleV2, ...]
    invariant_ids: tuple[str, ...]
    catalog_sha256: str = ""

    @model_validator(mode="after")
    def _seal_catalog(self) -> "CompilerInvariantCatalogV2":
        rule_ids = tuple(rule.invariant_id for rule in self.rules)
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("compiler_invariant_rule_id_duplicate")
        if rule_ids != self.invariant_ids:
            raise ValueError("compiler_invariant_id_registry_mismatch")
        projected = self.model_dump(mode="python", exclude={"catalog_sha256"})
        expected = canonical_sha256(projected)
        if self.catalog_sha256 and self.catalog_sha256 != expected:
            raise ValueError("compiler_invariant_catalog_sha256_mismatch")
        object.__setattr__(self, "catalog_sha256", expected)
        return self


class InitialCompilerModelInvariantCatalogV3(FrozenContract):
    protocol: Literal[
        "sgar-initial-compiler-model-invariant-catalog-v3"
    ] = INITIAL_COMPILER_MODEL_INVARIANT_PROTOCOL
    local_validator_catalog_sha256: str
    rules: tuple[CompilerInvariantRuleV2, ...]
    invariant_ids: tuple[str, ...]
    catalog_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "InitialCompilerModelInvariantCatalogV3":
        rule_ids = tuple(item.invariant_id for item in self.rules)
        if rule_ids != self.invariant_ids or len(rule_ids) != len(set(rule_ids)):
            raise ValueError("initial_compiler_model_invariant_registry_mismatch")
        expected = canonical_sha256(
            self.model_dump(mode="python", exclude={"catalog_sha256"})
        )
        if self.catalog_sha256 and self.catalog_sha256 != expected:
            raise ValueError("initial_compiler_model_invariant_sha256_mismatch")
        object.__setattr__(self, "catalog_sha256", expected)
        return self


class AdaptationModelInvariantCatalogV3(FrozenContract):
    protocol: Literal[
        "sgar-adaptation-model-invariant-catalog-v3"
    ] = ADAPTATION_MODEL_INVARIANT_PROTOCOL
    local_validator_catalog_sha256: str
    rules: tuple[CompilerInvariantRuleV2, ...]
    invariant_ids: tuple[str, ...]
    catalog_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "AdaptationModelInvariantCatalogV3":
        rule_ids = tuple(item.invariant_id for item in self.rules)
        if rule_ids != self.invariant_ids or len(rule_ids) != len(set(rule_ids)):
            raise ValueError("adaptation_model_invariant_registry_mismatch")
        expected = canonical_sha256(
            self.model_dump(mode="python", exclude={"catalog_sha256"})
        )
        if self.catalog_sha256 and self.catalog_sha256 != expected:
            raise ValueError("adaptation_model_invariant_sha256_mismatch")
        object.__setattr__(self, "catalog_sha256", expected)
        return self


class CompilerProposalNormalizationActionV1(FrozenContract):
    path: tuple[str | int, ...]
    action: Literal[
        "blank_inactive_field_to_null",
        "deduplicate_dependency",
        "deduplicate_profile_ref",
        "merge_identical_binding",
    ]
    before_sha256: str
    after_sha256: str


class CompilerProposalNormalizationAuditV1(FrozenContract):
    protocol: Literal[COMPILER_NORMALIZATION_AUDIT_PROTOCOL] = (
        COMPILER_NORMALIZATION_AUDIT_PROTOCOL
    )
    input_sha256: str
    normalized_sha256: str
    actions: tuple[CompilerProposalNormalizationActionV1, ...] = ()
    semantic_equivalence: Literal[True] = True
    audit_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "CompilerProposalNormalizationAuditV1":
        expected = canonical_sha256(
            self.model_dump(mode="python", exclude={"audit_sha256"})
        )
        if self.audit_sha256 and self.audit_sha256 != expected:
            raise ValueError("compiler_normalization_audit_sha256_mismatch")
        object.__setattr__(self, "audit_sha256", expected)
        return self


class CompilerProposalValidationIssueV1(FrozenContract):
    protocol: Literal[COMPILER_VALIDATION_ISSUE_PROTOCOL] = (
        COMPILER_VALIDATION_ISSUE_PROTOCOL
    )
    invariant_id: str = Field(min_length=1)
    path: tuple[str | int, ...]
    expected_active_fields: tuple[str, ...] = ()
    observed_active_fields: tuple[str, ...] = ()
    failure_layer: Literal["protocol", "selection", "connection", "executability"]
    failure_code: str = Field(min_length=1)
    authority_source: str = ""
    observed_value: str | None = None
    responsibility_stage: str = ""
    internal_path: tuple[str | int, ...] = ()
    step_id: str | None = None
    output_reachability: dict[str, Any] | None = None
    input_binding: dict[str, Any] | None = None
    issue_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "CompilerProposalValidationIssueV1":
        expected = canonical_sha256(self.model_dump(mode="python", exclude={"issue_sha256"}))
        if self.issue_sha256 and self.issue_sha256 != expected:
            raise ValueError("compiler_validation_issue_sha256_mismatch")
        object.__setattr__(self, "issue_sha256", expected)
        return self


class CompilerProposalCorrectionViewV1(FrozenContract):
    protocol: Literal[COMPILER_CORRECTION_VIEW_PROTOCOL] = COMPILER_CORRECTION_VIEW_PROTOCOL
    proposal_sha256: str
    normalized_structure: dict[str, Any]
    view_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "CompilerProposalCorrectionViewV1":
        expected = canonical_sha256(self.model_dump(mode="python", exclude={"view_sha256"}))
        if self.view_sha256 and self.view_sha256 != expected:
            raise ValueError("compiler_correction_view_sha256_mismatch")
        object.__setattr__(self, "view_sha256", expected)
        return self


class CompilerProposalInvariantError(ValueError):
    def __init__(self, issues: Sequence[CompilerProposalValidationIssueV1]) -> None:
        if not issues:
            raise ValueError("compiler_invariant_error_requires_issue")
        super().__init__("plan_compiler_proposal_invariant_invalid")
        self.issues = tuple(issues)


def _rule(
    invariant_id: str,
    *,
    paths: tuple[str, ...],
    condition: str,
    expected: str,
    failure_layer: Literal["protocol", "selection", "connection", "executability"],
    failure_code: str,
    correction: str,
    normalization: bool = False,
) -> CompilerInvariantRuleV2:
    return CompilerInvariantRuleV2(
        invariant_id=invariant_id,
        responsibility="normalization" if normalization else "model",
        applicable_paths=paths,
        condition={"expression": condition},
        expected_state={"expression": expected},
        failure_layer=failure_layer,
        failure_code=failure_code,
        safe_correction=correction,
        allow_lossless_normalization=normalization,
    )


def compiler_invariant_rules() -> tuple[CompilerInvariantRuleV2, ...]:
    return (
        _rule(
            "proposal_sufficiency_shape",
            paths=("is_sufficient", "insufficiency_code", "steps", "final_output"),
            condition="is_sufficient selects exactly one sufficient or insufficient shape",
            expected="sufficient has steps and final_output; insufficient has only insufficiency_code",
            failure_layer="protocol",
            failure_code="compiler_proposal_sufficiency_shape_invalid",
            correction="Return exactly the fields required by the selected sufficiency state.",
        ),
        _rule(
            "adaptation_preserved_step_unique",
            paths=("preserved_completed_step_ids[*]",),
            condition="checkpointed completed steps identify each step once",
            expected="preserved_completed_step_ids contains no duplicate IDs",
            failure_layer="protocol",
            failure_code="adaptation_preserved_step_duplicate",
            correction="List each preserved completed step ID once.",
        ),
        _rule(
            "adaptation_transform_directive_consistent",
            paths=("adaptation_kind", "temporary_tool_transform"),
            condition="temporary transform metadata matches the selected adaptation kind",
            expected="temporary_tool_transform is present exactly for temporary_tool_transform",
            failure_layer="protocol",
            failure_code="temporary_tool_transform_directive_mismatch",
            correction="Set the directive only when adaptation_kind is temporary_tool_transform.",
        ),
        _rule(
            "step_id_unique",
            paths=("steps[*].step_id",),
            condition="step IDs identify one step each",
            expected="all step_id values are unique",
            failure_layer="protocol",
            failure_code="compiler_step_id_duplicate",
            correction="Rename the duplicate step without changing its resource or intent.",
        ),
        _rule(
            "step_identity_canonical",
            paths=("steps[*].step_id", "steps[*].output_key"),
            condition="step and output identities are portable map keys",
            expected="identities start alphanumeric and contain only alphanumeric, dot, underscore, colon, or hyphen",
            failure_layer="protocol",
            failure_code="compiler_step_identity_not_canonical",
            correction="Use a portable step_id and output_key without spaces or path separators.",
        ),
        _rule(
            "binding_source_fields_exact",
            paths=("steps[*].input_bindings[*]",),
            condition="source_kind selects its active source fields",
            expected="only the source_kind fields are non-null and active values are non-empty",
            failure_layer="protocol",
            failure_code="compiler_binding_source_fields_conflict",
            correction="Keep only the fields selected by source_kind and populate every active field.",
        ),
        _rule(
            "binding_literal_json_valid",
            paths=("steps[*].input_bindings[*].literal_json",),
            condition="literal bindings encode a JSON value",
            expected="literal_json parses as any JSON value, including false, zero, null, or empty values",
            failure_layer="protocol",
            failure_code="compiler_binding_literal_json_invalid",
            correction="Encode the intended literal as valid JSON text.",
        ),
        _rule(
            "binding_name_unique",
            paths=("steps[*].input_bindings[*].name",),
            condition="binding names are keys after projection",
            expected="each step has one binding per name",
            failure_layer="protocol",
            failure_code="compiler_binding_name_duplicate",
            correction="Remove or rename conflicting bindings; identical duplicates are normalized automatically.",
        ),
        _rule(
            "dependency_and_profile_exact_duplicate_normalization",
            paths=("steps[*].depends_on", "steps[*].advisory_profile_refs"),
            condition="exact repeated list entries have no additional semantics",
            expected="exact duplicates are removed in first-seen order",
            failure_layer="protocol",
            failure_code="compiler_exact_duplicate_not_normalized",
            correction="No correction is required for exact duplicates.",
            normalization=True,
        ),
        _rule(
            "output_contract_mode_fields",
            paths=("steps[*].output_contract",),
            condition="output contract mode selects authoritative or custom fields",
            expected="authoritative modes have null custom fields; custom has non-empty artifact_type",
            failure_layer="protocol",
            failure_code="compiler_output_contract_mode_fields_invalid",
            correction="Set custom fields to null for authoritative modes or provide custom artifact_type.",
        ),
        _rule(
            "output_contract_schema_hint_json_valid",
            paths=("steps[*].output_contract.schema_hint_json",),
            condition="a supplied schema hint is JSON text",
            expected="schema_hint_json is null or valid JSON",
            failure_layer="protocol",
            failure_code="compiler_schema_hint_json_invalid",
            correction="Encode the schema hint as valid JSON text or use null.",
        ),
        _rule(
            "candidate_resource_authorized",
            paths=("steps[*].resource_id",),
            condition="a step selects a frozen candidate",
            expected="resource_id exists in candidate_resource_types",
            failure_layer="selection",
            failure_code="plan_resource_outside_candidate_pool",
            correction="Select one resource ID from the supplied frozen candidate catalog.",
        ),
        _rule(
            "operation_kind_matches_resource_type",
            paths=("steps[*].operation_kind",),
            condition="the operation is supported by the selected resource type",
            expected="operation_kind is in allowed_operation_kinds for the resource type",
            failure_layer="selection",
            failure_code="plan_operation_kind_resource_type_mismatch",
            correction="Use an allowed operation for the selected resource type.",
        ),
        _rule(
            "tool_entrypoint_declared",
            paths=("steps[*].entrypoint_id",),
            condition="Tool dispatch resolves exactly one declared entrypoint",
            expected="multi-entrypoint Tools select an ID; omitted ID is allowed only for a single entrypoint",
            failure_layer="connection",
            failure_code="plan_unknown_entrypoint",
            correction="Select a declared entrypoint ID, or null only when the Tool has one entrypoint.",
        ),
        _rule(
            "tool_required_bindings_present",
            paths=("steps[*].input_bindings",),
            condition="Tool entrypoint required inputs are connected",
            expected="every required binding name is present; additional bindings remain allowed",
            failure_layer="connection",
            failure_code="plan_required_binding_missing",
            correction="Add the missing required binding without removing valid auxiliary bindings.",
        ),
        _rule(
            "agent_base_model_authorized",
            paths=("steps[*].agent_base_model_resource_id",),
            condition="Agent execution selects an authorized base Model",
            expected="Agent has one listed base Model; non-Agent has null",
            failure_layer="selection",
            failure_code="plan_agent_base_model_invalid",
            correction="Select a listed base Model for an Agent and null for other resource types.",
        ),
        _rule(
            "application_profile_declared",
            paths=("steps[*].advisory_profile_refs",),
            condition="profiles are optional advisory references",
            expected="every supplied profile is declared for the selected resource",
            failure_layer="selection",
            failure_code="plan_unknown_application_profile",
            correction="Remove unknown profile IDs; an empty profile list is valid.",
        ),
        _rule(
            "dag_acyclic_topological",
            paths=("steps[*].depends_on",),
            condition="dependencies form a static executable DAG",
            expected="no self, unknown, forward, or cyclic dependency",
            failure_layer="connection",
            failure_code="plan_steps_not_topologically_ordered",
            correction="Order producers before consumers and reference only declared producer steps.",
        ),
        _rule(
            "step_output_dependency_declared",
            paths=("steps[*].input_bindings[*]",),
            condition="step_output identifies its producer and edge",
            expected="from_step is in depends_on and output_key matches that producer",
            failure_layer="connection",
            failure_code="plan_data_dependency_not_declared",
            correction="Declare the producer dependency and use that producer's output_key.",
        ),
        _rule(
            "final_output_contract_exact",
            paths=("final_output", "steps[*].output_contract.mode"),
            condition="one final reference selects the canonical subtask contract",
            expected="the referenced step alone uses subtask_final and the step output_key matches",
            failure_layer="executability",
            failure_code="compiler_final_output_contract_mode_mismatch",
            correction="Use subtask_final only on the exactly referenced final step.",
        ),
        _rule(
            "final_output_reachable",
            paths=("steps", "final_output"),
            condition="every planned step contributes to the final output",
            expected="all steps are reachable through final-step dependencies",
            failure_layer="connection",
            failure_code="plan_contains_disconnected_steps",
            correction="Connect every intended step to the final dependency closure or omit it.",
        ),
        _rule(
            "structured_output_format_eligible",
            paths=(
                "steps[*].resource_id",
                "steps[*].agent_base_model_resource_id",
                "steps[*].output_contract",
            ),
            condition="every structured Model or Agent step has verified enforcement",
            expected="the selected Model producer is eligible for native strict or local-validator mode",
            failure_layer="executability",
            failure_code="plan_structured_producer_ineligible",
            correction="Use a non-structured declared output contract or select an eligible structured producer.",
        ),
        _rule(
            "runtime_and_network_compatible",
            paths=("steps[*].resource_id",),
            condition="selected runtime requirements fit the current runtime capabilities",
            expected="runtime kind is supported and required network is enabled",
            failure_layer="executability",
            failure_code="plan_runtime_requirement_unsupported",
            correction="Select a candidate whose declared runtime requirements are supported.",
        ),
        _rule(
            "host_path_and_hidden_value_forbidden",
            paths=("$",),
            condition="proposal is portable and contains no host locator",
            expected="no Windows absolute path, UNC path, or file URI",
            failure_layer="protocol",
            failure_code="compiler_proposal_host_path_forbidden",
            correction="Use logical paths or authorized handles instead of host paths.",
        ),
    )


def initial_compiler_model_invariant_rules() -> tuple[CompilerInvariantRuleV2, ...]:
    """Rules expressed only in fields writable by CompilerDecisionProposalV3."""

    return (
        _rule(
            "v3_sufficiency_shape",
            paths=(
                "is_sufficient",
                "insufficiency_code",
                "unsatisfied_obligation_ids",
                "capability_gaps",
                "steps",
                "final_step_id",
                "final_contract",
            ),
            condition="is_sufficient selects exactly one declared V3 decision shape",
            expected="a sufficient decision contains a nonempty DAG and one final_step_id; an insufficient decision contains only declared gaps",
            failure_layer="protocol",
            failure_code="compiler_v3_sufficiency_shape_invalid",
            correction="Return only fields valid for the selected sufficiency state.",
        ),
        _rule(
            "v3_step_id_unique",
            paths=("steps[*].step_id",),
            condition="each step_id identifies exactly one step",
            expected="step_id values are unique",
            failure_layer="protocol",
            failure_code="compiler_v3_step_id_duplicate",
            correction="Rename the duplicate step_id without changing its task intent.",
        ),
        _rule(
            "v3_step_identity_portable",
            paths=("steps[*].step_id",),
            condition="step_id is a portable reference",
            expected="step_id starts alphanumeric and uses only declared portable characters",
            failure_layer="protocol",
            failure_code="compiler_v3_step_id_not_portable",
            correction="Use a portable step_id without spaces or path separators.",
        ),
        _rule(
            "v3_source_fields_exact",
            paths=("steps[*].input_mappings[*]",),
            condition="source_kind selects its V3 source fields",
            expected="literal uses literal_value; artifact_handle and resource use source_id; step_output uses from_step",
            failure_layer="protocol",
            failure_code="compiler_v3_input_mapping_shape_invalid",
            correction="Keep only the fields selected by source_kind.",
        ),
        _rule(
            "v3_literal_value_exact",
            paths=("steps[*].input_mappings[*].literal_value",),
            condition="literal_value selects exactly one declared typed value",
            expected="value_type and its one corresponding value agree",
            failure_layer="protocol",
            failure_code="compiler_v3_literal_value_mismatch",
            correction="Populate exactly the value selected by value_type.",
        ),
        _rule(
            "v3_target_port_unique",
            paths=("steps[*].input_mappings[*].target_port",),
            condition="target_port identifies the selected semantic input port",
            expected=(
                "each non-context target_port has exactly one mapping; a Model or Agent "
                "port may additionally receive sealed artifact_handle context mappings"
            ),
            failure_layer="protocol",
            failure_code="compiler_v3_target_port_duplicate",
            correction=(
                "Keep at most one literal, resource, or step_output mapping per port. "
                "Additional mappings on a Model or Agent port must be artifact_handle context."
            ),
        ),
        _rule(
            "v3_dependency_exact_duplicate_normalization",
            paths=("steps[*].depends_on",),
            condition="exact repeated dependency IDs have no additional meaning",
            expected="each dependency appears once",
            failure_layer="protocol",
            failure_code="compiler_v3_dependency_duplicate",
            correction="List each dependency once.",
        ),
        _rule(
            "v3_result_contract_shape",
            paths=(
                "steps[*].output_role",
                "steps[*].intermediate_contract",
                "final_contract",
            ),
            condition="declared result roles select their V3 semantic contract fields",
            expected="intermediate has intermediate_contract; final contract appears only when requested",
            failure_layer="protocol",
            failure_code="compiler_v3_result_contract_shape_invalid",
            correction="Align output_role with intermediate_contract and the requested final_contract state.",
        ),
        _rule(
            "v3_schema_graph_valid",
            paths=(
                "steps[*].intermediate_contract.schema_graph",
                "final_contract.schema_graph",
            ),
            condition="a JSON semantic contract contains a valid declared schema graph",
            expected="JSON uses a non-broad graph; non-JSON does not use a graph",
            failure_layer="protocol",
            failure_code="compiler_v3_schema_graph_invalid",
            correction="Provide a valid semantic schema graph only for JSON artifacts.",
        ),
        _rule(
            "v3_candidate_resource_authorized",
            paths=("steps[*].resource_id",),
            condition="a step selects one frozen candidate",
            expected="resource_id is present in candidate_cards",
            failure_layer="selection",
            failure_code="compiler_v3_resource_not_candidate",
            correction="Select one supplied candidate resource_id.",
        ),
        _rule(
            "v3_capability_operation_authorized",
            paths=(
                "steps[*].resource_id",
                "steps[*].capability_operation_id",
            ),
            condition="the selected capability belongs to the selected resource",
            expected="capability_operation_id is declared on that resource and has executable framework metadata",
            failure_layer="selection",
            failure_code="compiler_v3_capability_operation_unknown",
            correction="Select one capability_operation_id declared for the selected resource_id.",
        ),
        _rule(
            "v3_required_ports_mapped",
            paths=(
                "steps[*].capability_operation_id",
                "steps[*].input_mappings[*].target_port",
            ),
            condition="the selected capability receives all required semantic ports",
            expected="every required target_port is mapped and no undeclared target_port is used",
            failure_layer="connection",
            failure_code="compiler_v3_required_input_port_missing",
            correction="Map every required target_port declared by the selected capability.",
        ),
        _rule(
            "v3_material_binding_authorized",
            paths=(
                "steps[*].resource_id",
                "steps[*].capability_operation_id",
                "steps[*].input_mappings[*].target_port",
                "steps[*].input_mappings[*].source_kind",
                "steps[*].input_mappings[*].source_id",
            ),
            condition="each artifact_handle mapping selects one framework-authorized source-operation-port binding",
            expected="artifact_handle source_id appears in authorized_artifact_bindings for the selected resource, capability operation, and target_port",
            failure_layer="connection",
            failure_code="compiler_v3_material_binding_unauthorized",
            correction="Select an authorized artifact binding or a valid step_output path.",
        ),
        _rule(
            "v3_agent_base_model_authorized",
            paths=(
                "steps[*].resource_id",
                "steps[*].agent_base_model_resource_id",
            ),
            condition="an Agent selects an authorized base Model",
            expected="Agent has one supplied base Model and other resource types use null",
            failure_layer="selection",
            failure_code="compiler_v3_agent_base_model_invalid",
            correction="Select a supplied Agent base Model or use null for non-Agent resources.",
        ),
        _rule(
            "v3_dag_acyclic_topological",
            paths=("steps[*].depends_on",),
            condition="dependencies form one static executable DAG",
            expected="no self, unknown, forward, or cyclic dependency",
            failure_layer="connection",
            failure_code="compiler_v3_dependency_not_prior_step",
            correction="Order producers before consumers and reference only prior declared steps.",
        ),
        _rule(
            "v3_step_dependency_mapping",
            paths=(
                "steps[*].depends_on",
                "steps[*].input_mappings[*].source_kind",
                "steps[*].input_mappings[*].from_step",
            ),
            condition="each dependency carries data or a proven fixed file side effect",
            expected="from_step names a declared dependency; an otherwise unmapped dependency must be a deterministic write_file whose literal destination equals a literal consumer file_path input",
            failure_layer="connection",
            failure_code="compiler_v3_dependency_input_mapping_mismatch",
            correction="Map the producer output, or use a fixed matching file path with a declared deterministic writer dependency.",
        ),
        _rule(
            "v3_terminal_step_exact",
            paths=(
                "final_step_id",
                "steps[*].step_id",
                "steps[*].output_role",
                "final_contract",
            ),
            condition="one terminal step owns the final semantic result",
            expected="final_step_id names the only step whose output_role is final",
            failure_layer="executability",
            failure_code="compiler_v3_terminal_role_mismatch",
            correction="Set final_step_id to the one step whose output_role is final.",
        ),
        _rule(
            "v3_terminal_reachable",
            paths=("steps", "final_step_id", "steps[*].depends_on"),
            condition="every planned step contributes to the terminal step",
            expected="all steps are reachable through final-step dependencies",
            failure_layer="connection",
            failure_code="compiler_v3_disconnected_step",
            correction="Connect every required step to final_step_id or omit it.",
        ),
        _rule(
            "v3_structured_producer_eligible",
            paths=(
                "steps[*].resource_id",
                "steps[*].capability_operation_id",
                "steps[*].output_role",
                "steps[*].intermediate_contract",
                "final_contract",
            ),
            condition="a structured producer has verified enforcement support",
            expected="the selected candidate capability can produce the declared structured artifact",
            failure_layer="executability",
            failure_code="compiler_v3_structured_producer_ineligible",
            correction="Select a declared structured-capable resource and capability.",
        ),
        _rule(
            "v3_runtime_compatible",
            paths=(
                "steps[*].resource_id",
                "steps[*].capability_operation_id",
            ),
            condition="the selected capability has supported sealed runtime metadata",
            expected="the framework can resolve a supported dispatch for the selected capability",
            failure_layer="executability",
            failure_code="compiler_v3_runtime_requirement_unsupported",
            correction="Select a candidate capability supported by the sealed runtime.",
        ),
        _rule(
            "v3_host_path_forbidden",
            paths=(
                "steps[*].input_mappings[*].source_id",
                "steps[*].intent",
                "concise_rationale",
            ),
            condition="model-owned text and source identities are portable",
            expected="no host path, file URI, runtime locator, or hidden value",
            failure_layer="protocol",
            failure_code="compiler_v3_host_path_forbidden",
            correction="Use only authorized source_id values and portable semantic text.",
        ),
    )


def build_initial_compiler_model_invariant_catalog(
    local_catalog: CompilerInvariantCatalogV2,
) -> InitialCompilerModelInvariantCatalogV3:
    rules = tuple(
        rule.model_copy(
            update={
                "expected_state": {
                    "expression": (
                        "JSON object, array, map, and combinator nodes explicitly declare "
                        "their required object_fields, array_items, map_values, or "
                        "combinator_branches relations, and every node is reachable from "
                        "root_node_id"
                    )
                },
                "safe_correction": (
                    "Declare at least one object_field for every object node; exactly one "
                    "array_items or map_values relation for every array or map node; and at "
                    "least two combinator_branches for every all_of, any_of, or one_of node. "
                    "Reference only declared nodes and keep every node reachable from "
                    "root_node_id. min_properties does not replace object_fields."
                ),
            }
        )
        if rule.invariant_id == "v3_schema_graph_valid"
        else rule
        for rule in initial_compiler_model_invariant_rules()
    )
    return InitialCompilerModelInvariantCatalogV3(
        local_validator_catalog_sha256=local_catalog.catalog_sha256,
        rules=rules,
        invariant_ids=tuple(item.invariant_id for item in rules),
    )


def build_adaptation_model_invariant_catalog(
    local_catalog: CompilerInvariantCatalogV2,
) -> AdaptationModelInvariantCatalogV3:
    plan_rules = tuple(
        rule.model_copy(
            update={
                "invariant_id": f"plan_decision.{rule.invariant_id}",
                "applicable_paths": tuple(
                    f"plan_decision.{path}" for path in rule.applicable_paths
                ),
            }
        )
        for rule in initial_compiler_model_invariant_rules()
    )
    adaptation_rules = (
        _rule(
            "adaptation_selection_valid",
            paths=("adaptation_kind",),
            condition="adaptation_kind selects one active V3 adaptation mode",
            expected="use binding correction or plan recomposition",
            failure_layer="protocol",
            failure_code="plan_adaptation_v3_kind_invalid",
            correction="Select one allowed adaptation_kind.",
        ),
        _rule(
            "adaptation_preserved_steps_unique",
            paths=("preserved_completed_step_ids[*]",),
            condition="completed checkpoint identities are immutable",
            expected="each preserved completed step appears once",
            failure_layer="protocol",
            failure_code="adaptation_preserved_step_duplicate",
            correction="List every preserved completed step exactly once.",
        ),
        _rule(
            "adaptation_failure_identity_exact",
            paths=("failure_evidence_sha256", "previous_plan_sha256"),
            condition="adaptation remains bound to its failure and prior plan",
            expected="both identities exactly match the supplied adaptation input",
            failure_layer="protocol",
            failure_code="plan_adaptation_v3_identity_mismatch",
            correction="Copy the supplied failure and previous-plan identities exactly.",
        ),
    )
    rules = (*adaptation_rules, *plan_rules)
    return AdaptationModelInvariantCatalogV3(
        local_validator_catalog_sha256=local_catalog.catalog_sha256,
        rules=rules,
        invariant_ids=tuple(item.invariant_id for item in rules),
    )


def initial_compiler_model_invariant_projection(
    local_catalog: CompilerInvariantCatalogV2,
) -> dict[str, Any]:
    return build_initial_compiler_model_invariant_catalog(local_catalog).model_dump(
        mode="json"
    )


def adaptation_model_invariant_projection(
    local_catalog: CompilerInvariantCatalogV2,
) -> dict[str, Any]:
    return build_adaptation_model_invariant_catalog(local_catalog).model_dump(
        mode="json"
    )


_INITIAL_CORRECTION_FIELD_MAP = {
    "input_bindings": "input_mappings",
    "name": "target_port",
    "literal_json": "literal_value",
    "operation_kind": "capability_operation_id",
    "entrypoint_id": "capability_operation_id",
    "output_contract": "intermediate_contract",
    "output_key": "step_id",
    "final_output": "final_step_id",
    "advisory_profile_refs": "capability_operation_id",
    "logical_path": "source_id",
}

_INITIAL_CORRECTION_INVARIANT_MAP = {
    "proposal_sufficiency_shape": "v3_sufficiency_shape",
    "step_id_unique": "v3_step_id_unique",
    "step_identity_canonical": "v3_step_identity_portable",
    "binding_source_fields_exact": "v3_source_fields_exact",
    "binding_literal_json_valid": "v3_literal_value_exact",
    "binding_name_unique": "v3_target_port_unique",
    "dependency_and_profile_exact_duplicate_normalization": (
        "v3_dependency_exact_duplicate_normalization"
    ),
    "output_contract_mode_fields": "v3_result_contract_shape",
    "output_contract_schema_hint_json_valid": "v3_schema_graph_valid",
    "candidate_resource_authorized": "v3_candidate_resource_authorized",
    "operation_kind_matches_resource_type": "v3_capability_operation_authorized",
    "tool_entrypoint_declared": "v3_capability_operation_authorized",
    "tool_required_bindings_present": "v3_required_ports_mapped",
    "agent_base_model_authorized": "v3_agent_base_model_authorized",
    "application_profile_declared": "v3_capability_operation_authorized",
    "dag_acyclic_topological": "v3_dag_acyclic_topological",
    "step_output_dependency_declared": "v3_step_dependency_mapping",
    "final_output_contract_exact": "v3_terminal_step_exact",
    "final_output_reachable": "v3_terminal_reachable",
    "structured_output_format_eligible": "v3_structured_producer_eligible",
    "runtime_and_network_compatible": "v3_runtime_compatible",
    "host_path_and_hidden_value_forbidden": "v3_host_path_forbidden",
}

_INITIAL_CORRECTION_FAILURE_MAP = {
    "compiler_proposal_sufficiency_shape_invalid": "compiler_v3_sufficiency_shape_invalid",
    "compiler_step_id_duplicate": "compiler_v3_step_id_duplicate",
    "compiler_step_identity_not_canonical": "compiler_v3_step_id_not_portable",
    "compiler_binding_source_fields_conflict": "compiler_v3_input_mapping_shape_invalid",
    "compiler_binding_literal_json_invalid": "compiler_v3_literal_value_mismatch",
    "compiler_binding_name_duplicate": "compiler_v3_target_port_duplicate",
    "compiler_output_contract_mode_fields_invalid": "compiler_v3_result_contract_shape_invalid",
    "compiler_schema_hint_json_invalid": "compiler_v3_schema_graph_invalid",
    "plan_resource_outside_candidate_pool": "compiler_v3_resource_not_candidate",
    "plan_operation_kind_resource_type_mismatch": "compiler_v3_capability_operation_unknown",
    "plan_unknown_entrypoint": "compiler_v3_capability_operation_unknown",
    "plan_required_binding_missing": "compiler_v3_required_input_port_missing",
    "plan_agent_base_model_invalid": "compiler_v3_agent_base_model_invalid",
    "plan_unknown_application_profile": "compiler_v3_capability_operation_unknown",
    "plan_steps_not_topologically_ordered": "compiler_v3_dependency_not_prior_step",
    "plan_data_dependency_not_declared": "compiler_v3_dependency_input_mapping_mismatch",
    "compiler_final_output_contract_mode_mismatch": "compiler_v3_terminal_role_mismatch",
    "compiler_v3_final_output_role_mismatch": "compiler_v3_terminal_role_mismatch",
    "plan_contains_disconnected_steps": "compiler_v3_disconnected_step",
    "plan_structured_producer_ineligible": "compiler_v3_structured_producer_ineligible",
    "plan_runtime_requirement_unsupported": "compiler_v3_runtime_requirement_unsupported",
    "compiler_proposal_host_path_forbidden": "compiler_v3_host_path_forbidden",
}


def _project_initial_compiler_field_name(value: str) -> str:
    projected = value
    for internal_name, v3_name in sorted(
        _INITIAL_CORRECTION_FIELD_MAP.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        projected = re.sub(
            rf"(?<![A-Za-z0-9_]){re.escape(internal_name)}(?![A-Za-z0-9_])",
            v3_name,
            projected,
        )
    return projected


def project_initial_compiler_correction_v3(
    correction: Mapping[str, Any],
) -> dict[str, Any]:
    """Translate existing internal diagnostics into the V3 model-owned surface."""

    projected = deepcopy(dict(correction))
    invariant_id = str(projected.get("invariant_id") or "")
    projected["invariant_id"] = _INITIAL_CORRECTION_INVARIANT_MAP.get(
        invariant_id, invariant_id
    )
    failure_code = str(projected.get("failure_code") or "")
    projected["failure_code"] = _INITIAL_CORRECTION_FAILURE_MAP.get(
        failure_code, failure_code
    )
    raw_path = projected.get("path")
    if isinstance(raw_path, (list, tuple)):
        projected["path"] = [
            _project_initial_compiler_field_name(str(item))
            if not isinstance(item, int)
            else item
            for item in raw_path
        ]
    for key in ("expected_active_fields", "observed_active_fields"):
        raw_fields = projected.get(key)
        if isinstance(raw_fields, (list, tuple)):
            mapped_fields = [
                _project_initial_compiler_field_name(str(item))
                for item in raw_fields
            ]
            projected[key] = list(dict.fromkeys(mapped_fields))
    additional_issues = projected.get("additional_issues")
    if isinstance(additional_issues, list):
        projected["additional_issues"] = [
            project_initial_compiler_correction_v3(item)
            if isinstance(item, Mapping)
            else item
            for item in additional_issues
        ]
    return projected


def compiler_invariant_request_projection(
    catalog: CompilerInvariantCatalogV2,
) -> dict[str, Any]:
    return {
        "protocol": catalog.protocol,
        "catalog_sha256": catalog.catalog_sha256,
        "rules": [rule.model_dump(mode="json") for rule in catalog.rules],
    }


def compiler_invariant_validator_projection(
    catalog: CompilerInvariantCatalogV2,
) -> dict[str, Any]:
    rules = tuple(
        CompilerInvariantRuleV2.model_validate(rule.model_dump(mode="python"))
        for rule in catalog.rules
    )
    return {
        "protocol": catalog.protocol,
        "catalog_sha256": catalog.catalog_sha256,
        "rules": [rule.model_dump(mode="json") for rule in rules],
    }


def _compact_output_format_contract(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    decision_fields = (
        "final_producer_eligible",
        "eligible",
        "allowed_enforcement_modes",
        "selected_enforcement_mode",
        "format_contract_sha256",
        "requirement_sha256",
        "schema_sha256",
        "wire_schema_sha256",
        "probe_outcome",
        "probe_reason_code",
    )
    return {
        field_name: deepcopy(value[field_name])
        for field_name in decision_fields
        if field_name in value
    }


def compiler_constraint_prompt_projection(
    catalog: CompilerInvariantCatalogV2,
    *,
    candidate_pool_sha256: str,
) -> dict[str, Any]:
    """Project only model decision constraints; authoritative contracts stay in cards."""

    resource_types = set(catalog.candidate_resource_types.values())
    dispatch_policies: dict[str, Any] = {}
    for resource_id in sorted(catalog.candidate_resource_types):
        resource_type = catalog.candidate_resource_types[resource_id]
        entrypoints = catalog.tool_entrypoints.get(resource_id, ())
        entrypoint_ids = [
            str(entrypoint.get("entrypoint_id") or "")
            for entrypoint in entrypoints
            if entrypoint.get("entrypoint_id")
        ]
        base_models = list(catalog.agent_base_models.get(resource_id, ()))
        dispatch_policies[resource_id] = {
            "resource_type": resource_type,
            "allowed_operation_kinds": list(
                catalog.allowed_operation_kinds.get(resource_type, ())
            ),
            "entrypoint_policy": (
                "declared_tool_entrypoint"
                if resource_type == "Tool"
                else "null_only"
            ),
            "allowed_entrypoint_ids": entrypoint_ids,
            "legacy_null_entrypoint_compatible": bool(
                resource_type == "Tool" and len(entrypoint_ids) == 1
            ),
            "agent_base_model_policy": (
                "declared_agent_base_model"
                if resource_type == "Agent"
                else "null_only"
            ),
            "allowed_agent_base_model_resource_ids": base_models,
            "allowed_profile_refs": list(
                catalog.application_profiles.get(resource_id, ())
            ),
            "capability_operations": list(
                catalog.capability_operations.get(resource_id, ())
            ),
        }

    projection: dict[str, Any] = {
        "protocol": COMPILER_CONSTRAINT_PROJECTION_PROTOCOL,
        "source_catalog_sha256": catalog.catalog_sha256,
        "candidate_pool_sha256": str(candidate_pool_sha256),
        "binding_source_policies": {
            source_kind: {
                "active_fields": sorted(expected_fields),
                "inactive_fields_must_be_null": sorted(
                    set(_BINDING_VALUE_FIELDS) - set(expected_fields)
                ),
            }
            for source_kind, expected_fields in sorted(
                _BINDING_EXPECTED_FIELDS.items()
            )
        },
        "candidate_resource_types": dict(catalog.candidate_resource_types),
        "allowed_operation_kinds": {
            resource_type: list(catalog.allowed_operation_kinds[resource_type])
            for resource_type in sorted(resource_types)
            if resource_type in catalog.allowed_operation_kinds
        },
        "tool_entrypoints": {
            resource_id: [
                {
                    "entrypoint_id": str(entrypoint.get("entrypoint_id") or ""),
                    "required_binding_names": list(
                        entrypoint.get("required_binding_names") or ()
                    ),
                }
                for entrypoint in entrypoints
            ]
            for resource_id, entrypoints in catalog.tool_entrypoints.items()
        },
        "agent_base_models": {
            resource_id: list(model_ids)
            for resource_id, model_ids in catalog.agent_base_models.items()
        },
        "application_profiles": {
            resource_id: list(profile_ids)
            for resource_id, profile_ids in catalog.application_profiles.items()
        },
        "dispatch_policies": dispatch_policies,
        "output_format_eligibility": {
            resource_id: _compact_output_format_contract(value)
            for resource_id, value in catalog.output_format_contracts.items()
        },
        "final_artifact_contract": deepcopy(catalog.final_artifact_contract),
        "execution_obligations": list(catalog.execution_obligations),
        "materials": list(catalog.materials),
        "runtime_capabilities_sha256": canonical_sha256(
            catalog.runtime_capabilities
        ),
        "rule_registry_sha256": canonical_sha256(
            [rule.model_dump(mode="json") for rule in catalog.rules]
        ),
    }
    projection["projection_sha256"] = canonical_sha256(projection)
    return projection


def _proposal_value_at_path(
    proposal: Mapping[str, Any],
    path: Sequence[str | int],
) -> tuple[bool, Any]:
    current: Any = proposal
    for component in path:
        if isinstance(component, int):
            if not isinstance(current, (list, tuple)) or not 0 <= component < len(current):
                return False, None
            current = current[component]
        else:
            if not isinstance(current, Mapping) or component not in current:
                return False, None
            current = current[component]
    return True, current


def _safe_json_type(present: bool, value: Any) -> str:
    if not present:
        return "missing"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, Mapping):
        return "object"
    if isinstance(value, (list, tuple)):
        return "array"
    return "unknown"


def build_compiler_safe_issue_audits(
    issues: Sequence[CompilerProposalValidationIssueV1],
    *,
    proposal: Mapping[str, Any],
    catalog: CompilerInvariantCatalogV2,
) -> list[dict[str, Any]]:
    """Build hash-only model-value diagnostics safe for persisted audit sidecars."""

    audits: list[dict[str, Any]] = []
    for issue in issues:
        authorized_resource_id: str | None = None
        untrusted_resource_id_sha256: str | None = None
        resource_path = issue.internal_path or issue.path
        if len(resource_path) >= 2 and resource_path[0] == "steps" and isinstance(
            resource_path[1], int
        ):
            step_index = resource_path[1]
            steps = proposal.get("steps")
            if isinstance(steps, (list, tuple)) and 0 <= step_index < len(steps):
                step = steps[step_index]
                resource_id = step.get("resource_id") if isinstance(step, Mapping) else None
                if (
                    isinstance(resource_id, str)
                    and resource_id in catalog.candidate_resource_types
                ):
                    authorized_resource_id = resource_id
                elif resource_id is not None:
                    untrusted_resource_id_sha256 = canonical_sha256(resource_id)

        present, observed_value = _proposal_value_at_path(proposal, issue.path)
        declared_values = tuple(sorted(set(issue.expected_active_fields)))
        observed_values = tuple(issue.observed_active_fields)
        observed_declared: bool | None = None
        if declared_values and observed_values:
            observed_declared = all(value in declared_values for value in observed_values)
        audit: dict[str, Any] = {
            "protocol": COMPILER_SAFE_ISSUE_AUDIT_PROTOCOL,
            "invariant_id": issue.invariant_id,
            "path": list(issue.path),
            "failure_layer": issue.failure_layer,
            "failure_code": issue.failure_code,
            "issue_sha256": issue.issue_sha256,
            "authorized_resource_id": authorized_resource_id,
            "untrusted_resource_id_sha256": untrusted_resource_id_sha256,
            "declared_value_count": len(declared_values),
            "declared_values_sha256": canonical_sha256(declared_values),
            "observed_value_type": ("unrecorded" if not present and issue.internal_path else _safe_json_type(present, observed_value)),
            "internal_path": list(issue.internal_path),
            "observed_value_sha256": canonical_sha256(
                observed_value if present else {"state": "missing"}
            ),
            "observed_values_sha256": canonical_sha256(observed_values),
            "observed_values_declared": observed_declared,
        }
        audit["audit_sha256"] = canonical_sha256(audit)
        audits.append(audit)
    return audits


def invariant_id_for_failure_code(code: str) -> str:
    for rule in compiler_invariant_rules():
        if rule.failure_code == code:
            return rule.invariant_id
    aliases = {
        "plan_multi_entrypoint_tool_requires_entrypoint": "tool_entrypoint_declared",
        "plan_non_tool_has_entrypoint": "tool_entrypoint_declared",
        "plan_agent_base_model_missing": "agent_base_model_authorized",
        "plan_agent_base_model_outside_closure": "agent_base_model_authorized",
        "plan_non_agent_has_base_model": "agent_base_model_authorized",
        "plan_step_output_binding_incomplete": "step_output_dependency_declared",
        "plan_step_output_producer_missing": "step_output_dependency_declared",
        "plan_step_output_key_mismatch": "step_output_dependency_declared",
        "plan_final_output_reference_invalid": "final_output_contract_exact",
        "plan_final_output_contract_mismatch": "final_output_contract_exact",
        "plan_network_requirement_unsupported": "runtime_and_network_compatible",
        "plan_runtime_kind_unsupported": "runtime_and_network_compatible",
        "plan_structured_producer_format_evidence_missing": "structured_output_format_eligible",
        "plan_structured_producer_has_no_enforcement_mode": "structured_output_format_eligible",
        "compiler_v3_material_binding_unauthorized": "v3_material_binding_authorized",
    }
    return aliases.get(code, code)


def _record_action(
    actions: list[CompilerProposalNormalizationActionV1],
    *,
    path: tuple[str | int, ...],
    action: Literal[
        "blank_inactive_field_to_null",
        "deduplicate_dependency",
        "deduplicate_profile_ref",
        "merge_identical_binding",
    ],
    before: Any,
    after: Any,
) -> None:
    actions.append(
        CompilerProposalNormalizationActionV1(
            path=path,
            action=action,
            before_sha256=canonical_sha256(before),
            after_sha256=canonical_sha256(after),
        )
    )


def _deduplicate_scalars(
    values: Any,
    *,
    path: tuple[str | int, ...],
    action: Literal["deduplicate_dependency", "deduplicate_profile_ref"],
    actions: list[CompilerProposalNormalizationActionV1],
) -> Any:
    if not isinstance(values, list):
        return values
    deduplicated: list[Any] = []
    seen: set[str] = set()
    for value in values:
        identity = canonical_sha256(value)
        if identity in seen:
            continue
        seen.add(identity)
        deduplicated.append(value)
    if deduplicated != values:
        _record_action(actions, path=path, action=action, before=values, after=deduplicated)
    return deduplicated


def normalize_compiler_proposal_payload(
    payload: Mapping[str, Any],
) -> tuple[dict[str, Any], CompilerProposalNormalizationAuditV1]:
    original = json.loads(canonical_json_bytes(payload).decode("utf-8"))
    normalized = deepcopy(original)
    actions: list[CompilerProposalNormalizationActionV1] = []
    steps = normalized.get("steps")
    if isinstance(steps, list):
        for step_index, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            step["depends_on"] = _deduplicate_scalars(
                step.get("depends_on"),
                path=("steps", step_index, "depends_on"),
                action="deduplicate_dependency",
                actions=actions,
            )
            step["advisory_profile_refs"] = _deduplicate_scalars(
                step.get("advisory_profile_refs"),
                path=("steps", step_index, "advisory_profile_refs"),
                action="deduplicate_profile_ref",
                actions=actions,
            )
            output_contract = step.get("output_contract")
            if isinstance(output_contract, dict) and output_contract.get("mode") in {
                "subtask_final",
                "selected_resource",
            }:
                for field_name in ("artifact_type", "description", "schema_hint_json"):
                    value = output_contract.get(field_name)
                    if isinstance(value, str) and not value.strip():
                        output_contract[field_name] = None
                        _record_action(
                            actions,
                            path=("steps", step_index, "output_contract", field_name),
                            action="blank_inactive_field_to_null",
                            before=value,
                            after=None,
                        )
            bindings = step.get("input_bindings")
            if not isinstance(bindings, list):
                continue
            deduplicated_bindings: list[Any] = []
            seen_bindings: dict[str, str] = {}
            for binding_index, binding in enumerate(bindings):
                if not isinstance(binding, dict):
                    deduplicated_bindings.append(binding)
                    continue
                source_kind = str(binding.get("source_kind") or "")
                expected = _BINDING_EXPECTED_FIELDS.get(source_kind, frozenset())
                for field_name in _BINDING_VALUE_FIELDS:
                    value = binding.get(field_name)
                    if (
                        field_name not in expected
                        and isinstance(value, str)
                        and not value.strip()
                    ):
                        before = value
                        binding[field_name] = None
                        _record_action(
                            actions,
                            path=("steps", step_index, "input_bindings", binding_index, field_name),
                            action="blank_inactive_field_to_null",
                            before=before,
                            after=None,
                        )
                name = binding.get("name")
                identity = canonical_sha256(binding)
                if isinstance(name, str) and name in seen_bindings and seen_bindings[name] == identity:
                    _record_action(
                        actions,
                        path=("steps", step_index, "input_bindings", binding_index),
                        action="merge_identical_binding",
                        before=binding,
                        after={"merged_with_first_index": True},
                    )
                    continue
                if isinstance(name, str) and name not in seen_bindings:
                    seen_bindings[name] = identity
                deduplicated_bindings.append(binding)
            step["input_bindings"] = deduplicated_bindings
    audit = CompilerProposalNormalizationAuditV1(
        input_sha256=canonical_sha256(original),
        normalized_sha256=canonical_sha256(normalized),
        actions=tuple(actions),
    )
    return normalized, audit


def _issue(
    catalog: CompilerInvariantCatalogV2,
    invariant_id: str,
    path: tuple[str | int, ...],
    *,
    expected: Sequence[str] = (),
    observed: Sequence[str] = (),
) -> CompilerProposalValidationIssueV1:
    rule = next(rule for rule in catalog.rules if rule.invariant_id == invariant_id)
    if rule.failure_layer in {"framework", "normalization"}:
        raise ValueError("compiler_model_issue_has_non_model_layer")
    return CompilerProposalValidationIssueV1(
        invariant_id=invariant_id,
        path=path,
        expected_active_fields=tuple(expected),
        observed_active_fields=tuple(observed),
        failure_layer=rule.failure_layer,
        failure_code=rule.failure_code,
    )


def _is_nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _json_valid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        _strict_json_loads(value)
    except (TypeError, ValueError):
        return False
    return True


def _host_path(value: Any, path: tuple[str | int, ...] = ()) -> tuple[str | int, ...] | None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            found = _host_path(item, (*path, str(key)))
            if found is not None:
                return found
        return None
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found = _host_path(item, (*path, index))
            if found is not None:
                return found
        return None
    if isinstance(value, str) and is_private_host_path_value(value):
        return path
    return None


def _format_contract_eligible(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    if not bool(value.get("final_producer_eligible")):
        return False
    modes = set(value.get("allowed_enforcement_modes") or ())
    return bool(modes & {"native_strict_schema", "json_object_local_validator"})


def _schema_bound_format_eligible(
    catalog: CompilerInvariantCatalogV2,
    *,
    producer: str,
) -> bool:
    """Accept exact evidence, or a sealed V6 capability pending exact binding.

    A Planner V6 JSON schema does not exist until the Compiler has produced it.
    The pre-projection invariant may therefore authorize selection from a
    hash-bound generic capability declaration.  Exact schema evidence is still
    mandatory after selection and is enforced by PlanStructuralValidator and
    lowering.
    """

    if _format_contract_eligible(catalog.output_format_contracts.get(producer)):
        return True
    if not bool(catalog.final_artifact_contract.get("schema_generation_required")):
        return False
    runtime = catalog.resource_runtime_requirements.get(producer)
    if not isinstance(runtime, Mapping):
        return False
    capability = runtime.get("sgar_structured_output_capability")
    if not isinstance(capability, Mapping):
        return False
    projection = dict(capability)
    supplied_hash = str(projection.pop("capability_sha256", ""))
    return (
        projection.get("protocol")
        == "sgar-candidate-structured-output-capability-v1"
        and projection.get("schema_phase") == "compiler_pending"
        and projection.get("compatibility_status") != "incompatible"
        and supplied_hash == canonical_sha256(projection)
    )


def _mapping_output_contract_structured(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    artifact_type = str(value.get("artifact_type") or "").strip().lower()
    if artifact_type == "json":
        return True
    for field_name in ("schema_hint", "json_schema", "schema"):
        if value.get(field_name) is not None:
            return True
    schema_hint_json = value.get("schema_hint_json")
    if schema_hint_json is None:
        return False
    try:
        return _strict_json_loads(str(schema_hint_json)) is not None
    except (TypeError, ValueError, json.JSONDecodeError):
        # The dedicated schema-hint invariant reports malformed JSON. Treat it
        # as structured here so an invalid value can never bypass eligibility.
        return True


def _proposal_step_output_structured(
    step: Mapping[str, Any],
    catalog: CompilerInvariantCatalogV2,
) -> bool:
    output_contract = step.get("output_contract")
    if not isinstance(output_contract, Mapping):
        return False
    mode = str(output_contract.get("mode") or "")
    if mode == "subtask_final":
        effective_contract = catalog.final_artifact_contract
    elif mode == "selected_resource":
        effective_contract = catalog.resource_output_contracts.get(
            str(step.get("resource_id") or "")
        )
    else:
        effective_contract = output_contract
    return _mapping_output_contract_structured(effective_contract)


def validate_compiler_proposal_invariants(
    proposal: Mapping[str, Any],
    catalog: CompilerInvariantCatalogV2,
) -> tuple[CompilerProposalValidationIssueV1, ...]:
    issues: list[CompilerProposalValidationIssueV1] = []
    sufficient = proposal.get("is_sufficient") is True
    steps = proposal.get("steps")
    final_output = proposal.get("final_output")
    insufficiency = proposal.get("insufficiency_code")
    if not isinstance(steps, list):
        steps = []
    shape_valid = (
        bool(steps) and isinstance(final_output, Mapping) and insufficiency is None
        if sufficient
        else not steps and final_output is None and insufficiency is not None
    )
    if not shape_valid:
        issues.append(
            _issue(
                catalog,
                "proposal_sufficiency_shape",
                ("is_sufficient",),
                expected=("steps", "final_output") if sufficient else ("insufficiency_code",),
                observed=tuple(
                    name
                    for name, value in (
                        ("steps", steps),
                        ("final_output", final_output),
                        ("insufficiency_code", insufficiency),
                    )
                    if value not in (None, [], ())
                ),
            )
        )
    forbidden_path = _host_path(proposal)
    if forbidden_path is not None:
        issues.append(
            _issue(catalog, "host_path_and_hidden_value_forbidden", forbidden_path)
        )
    if not sufficient:
        return tuple(issues)

    step_by_id: dict[str, Mapping[str, Any]] = {}
    prior_step_ids: set[str] = set()
    output_by_step: dict[str, str] = {}
    for step_index, raw_step in enumerate(steps):
        if not isinstance(raw_step, Mapping):
            continue
        step = raw_step
        step_id = str(step.get("step_id") or "")
        step_path = ("steps", step_index)
        output_key_value = str(step.get("output_key") or "")
        if not _CANONICAL_STEP_ID.fullmatch(step_id):
            issues.append(
                _issue(catalog, "step_identity_canonical", (*step_path, "step_id"))
            )
        if not _CANONICAL_STEP_ID.fullmatch(output_key_value):
            issues.append(
                _issue(catalog, "step_identity_canonical", (*step_path, "output_key"))
            )
        if step_id in step_by_id:
            issues.append(_issue(catalog, "step_id_unique", (*step_path, "step_id")))
        else:
            step_by_id[step_id] = step
        output_by_step[step_id] = str(step.get("output_key") or "")

        depends_on = step.get("depends_on")
        dependencies = list(depends_on) if isinstance(depends_on, list) else []
        bad_dependencies = [
            str(item)
            for item in dependencies
            if str(item) == step_id or str(item) not in prior_step_ids
        ]
        if bad_dependencies:
            issues.append(
                _issue(
                    catalog,
                    "dag_acyclic_topological",
                    (*step_path, "depends_on"),
                    expected=tuple(sorted(prior_step_ids)),
                    observed=tuple(bad_dependencies),
                )
            )

        bindings = step.get("input_bindings")
        bindings_list = list(bindings) if isinstance(bindings, list) else []
        binding_names: dict[str, int] = {}
        for binding_index, raw_binding in enumerate(bindings_list):
            if not isinstance(raw_binding, Mapping):
                continue
            binding = raw_binding
            path = (*step_path, "input_bindings", binding_index)
            name = str(binding.get("name") or "")
            if name in binding_names:
                issues.append(
                    _issue(
                        catalog,
                        "binding_name_unique",
                        (*path, "name"),
                        observed=(str(binding_names[name]), str(binding_index)),
                    )
                )
            else:
                binding_names[name] = binding_index
            source_kind = str(binding.get("source_kind") or "")
            expected_fields = _BINDING_EXPECTED_FIELDS.get(source_kind, frozenset())
            if source_kind == "step_output" and binding.get("value_path") is not None:
                expected_fields = expected_fields | {"value_path"}
            observed_fields = frozenset(
                field_name
                for field_name in _BINDING_VALUE_FIELDS
                if binding.get(field_name) is not None
            )
            active_nonempty = all(
                (
                    isinstance(binding.get(field_name), (list, tuple))
                    and bool(binding[field_name])
                    and all(isinstance(v, str) for v in binding[field_name])
                ) if field_name == "value_path" else (
                    field_name == "literal_json" or _is_nonempty(binding.get(field_name))
                )
                for field_name in expected_fields
            )
            if observed_fields != expected_fields or not active_nonempty:
                issues.append(
                    _issue(
                        catalog,
                        "binding_source_fields_exact",
                        path,
                        expected=tuple(sorted(expected_fields)),
                        observed=tuple(sorted(observed_fields)),
                    )
                )
            if source_kind == "literal" and not _json_valid(binding.get("literal_json")):
                issues.append(
                    _issue(catalog, "binding_literal_json_valid", (*path, "literal_json"))
                )
            if source_kind == "step_output":
                from_step = str(binding.get("from_step") or "")
                output_key = str(binding.get("output_key") or "")
                if (
                    from_step not in dependencies
                    or from_step not in prior_step_ids
                    or output_by_step.get(from_step) != output_key
                ):
                    issues.append(
                        _issue(
                            catalog,
                            "step_output_dependency_declared",
                            path,
                            expected=(from_step, output_by_step.get(from_step, "")),
                            observed=(from_step, output_key),
                        )
                    )

        output_contract = step.get("output_contract")
        if isinstance(output_contract, Mapping):
            mode = str(output_contract.get("mode") or "")
            custom_fields = {
                name: output_contract.get(name)
                for name in ("artifact_type", "description", "schema_hint_json")
            }
            mode_valid = (
                all(value is None for value in custom_fields.values())
                if mode in {"subtask_final", "selected_resource"}
                else mode == "custom" and _is_nonempty(custom_fields["artifact_type"])
            )
            if not mode_valid:
                issues.append(
                    _issue(
                        catalog,
                        "output_contract_mode_fields",
                        (*step_path, "output_contract"),
                        expected=("artifact_type",) if mode == "custom" else (),
                        observed=tuple(name for name, value in custom_fields.items() if value is not None),
                    )
                )
            schema_hint_json = custom_fields["schema_hint_json"]
            if schema_hint_json is not None and not _json_valid(schema_hint_json):
                issues.append(
                    _issue(
                        catalog,
                        "output_contract_schema_hint_json_valid",
                        (*step_path, "output_contract", "schema_hint_json"),
                    )
                )

        resource_id = str(step.get("resource_id") or "")
        resource_type = catalog.candidate_resource_types.get(resource_id)
        if resource_type is None:
            issues.append(
                _issue(catalog, "candidate_resource_authorized", (*step_path, "resource_id"))
            )
        else:
            operation = str(step.get("operation_kind") or "")
            if operation not in set(catalog.allowed_operation_kinds.get(resource_type, ())):
                issues.append(
                    _issue(
                        catalog,
                        "operation_kind_matches_resource_type",
                        (*step_path, "operation_kind"),
                        expected=catalog.allowed_operation_kinds.get(resource_type, ()),
                        observed=(operation,),
                    )
                )
            entrypoint_id = step.get("entrypoint_id")
            if resource_type == "Tool":
                entries = catalog.tool_entrypoints.get(resource_id, ())
                selected = None
                if entrypoint_id is None and len(entries) == 1:
                    selected = entries[0]
                else:
                    selected = next(
                        (
                            entry
                            for entry in entries
                            if entry.get("entrypoint_id") == entrypoint_id
                        ),
                        None,
                    )
                if selected is None:
                    issues.append(
                        _issue(
                            catalog,
                            "tool_entrypoint_declared",
                            (*step_path, "entrypoint_id"),
                            expected=tuple(
                                str(entry.get("entrypoint_id") or "") for entry in entries
                            ),
                            observed=(str(entrypoint_id or "null"),),
                        )
                    )
                else:
                    missing = tuple(
                        name
                        for name in selected.get("required_binding_names", ())
                        if name not in binding_names
                    )
                    if missing:
                        issues.append(
                            _issue(
                                catalog,
                                "tool_required_bindings_present",
                                (*step_path, "input_bindings"),
                                expected=missing,
                                observed=tuple(binding_names),
                            )
                        )
            elif entrypoint_id is not None:
                issues.append(
                    _issue(catalog, "tool_entrypoint_declared", (*step_path, "entrypoint_id"))
                )

            base_model = step.get("agent_base_model_resource_id")
            if resource_type == "Agent":
                allowed_models = catalog.agent_base_models.get(resource_id, ())
                if base_model not in allowed_models:
                    issues.append(
                        _issue(
                            catalog,
                            "agent_base_model_authorized",
                            (*step_path, "agent_base_model_resource_id"),
                            expected=allowed_models,
                            observed=(str(base_model or "null"),),
                        )
                    )
            elif base_model is not None:
                issues.append(
                    _issue(
                        catalog,
                        "agent_base_model_authorized",
                        (*step_path, "agent_base_model_resource_id"),
                        expected=(),
                        observed=(str(base_model),),
                    )
                )

            if resource_type in {"Model", "Agent"} and _proposal_step_output_structured(
                step,
                catalog,
            ):
                producer = (
                    resource_id if resource_type == "Model" else str(base_model or "")
                )
                if not _schema_bound_format_eligible(
                    catalog,
                    producer=producer,
                ):
                    issues.append(
                        _issue(
                            catalog,
                            "structured_output_format_eligible",
                            (*step_path, "output_contract"),
                            observed=(producer,),
                        )
                    )

            profiles = step.get("advisory_profile_refs")
            profile_values = list(profiles) if isinstance(profiles, list) else []
            unknown_profiles = tuple(
                str(item)
                for item in profile_values
                if item not in catalog.application_profiles.get(resource_id, ())
                and catalog.candidate_resource_types.get(str(item)) != "Skill"
            )
            if unknown_profiles:
                issues.append(
                    _issue(
                        catalog,
                        "application_profile_declared",
                        (*step_path, "advisory_profile_refs"),
                        expected=catalog.application_profiles.get(resource_id, ()),
                        observed=unknown_profiles,
                    )
                )

            requirements = catalog.resource_runtime_requirements.get(resource_id)
            if isinstance(requirements, Mapping):
                runtime_kind = requirements.get("runtime_kind") or requirements.get("runtime_type")
                supported = set(catalog.runtime_capabilities.get("supported_runtime_kinds") or ())
                network = requirements.get("network")
                network_required = bool(
                    requirements.get("network_required")
                    or (isinstance(network, Mapping) and network.get("required"))
                )
                if (
                    runtime_kind
                    and supported
                    and str(runtime_kind) not in supported
                ) or (
                    network_required
                    and catalog.runtime_capabilities.get("network_policy") == "disabled"
                ):
                    issues.append(
                        _issue(
                            catalog,
                            "runtime_and_network_compatible",
                            (*step_path, "resource_id"),
                        )
                    )

        prior_step_ids.add(step_id)

    if isinstance(final_output, Mapping):
        final_step_id = str(final_output.get("step_id") or "")
        final_key = str(final_output.get("output_key") or "")
        final_step = step_by_id.get(final_step_id)
        final_valid = final_step is not None and output_by_step.get(final_step_id) == final_key
        schema_generation_required = bool(
            catalog.final_artifact_contract.get("schema_generation_required")
        )
        for step_index, raw_step in enumerate(steps):
            if not isinstance(raw_step, Mapping):
                continue
            output = raw_step.get("output_contract")
            mode = output.get("mode") if isinstance(output, Mapping) else None
            is_final = (
                str(raw_step.get("step_id") or "") == final_step_id
                and str(raw_step.get("output_key") or "") == final_key
            )
            expected_final_mode = (
                "custom" if schema_generation_required else "subtask_final"
            )
            mode_matches_position = (
                mode == expected_final_mode
                if is_final
                else mode != "subtask_final"
            )
            if not mode_matches_position:
                issues.append(
                    _issue(
                        catalog,
                        "final_output_contract_exact",
                        ("steps", step_index, "output_contract", "mode"),
                        expected=(
                            expected_final_mode
                            if is_final
                            else "not_subtask_final",
                        ),
                        observed=(str(mode),),
                    )
                )
        if not final_valid:
            issues.append(
                _issue(catalog, "final_output_contract_exact", ("final_output",))
            )
        elif final_step is not None:
            reachable: set[str] = set()
            pending = [final_step_id]
            while pending:
                current = pending.pop()
                if current in reachable:
                    continue
                reachable.add(current)
                step = step_by_id.get(current)
                dependencies = step.get("depends_on") if isinstance(step, Mapping) else []
                if isinstance(dependencies, list):
                    pending.extend(str(item) for item in dependencies)
            disconnected = tuple(step_id for step_id in step_by_id if step_id not in reachable)
            if disconnected:
                issues.append(
                    _issue(
                        catalog,
                        "final_output_reachable",
                        ("final_output",),
                        observed=disconnected,
                    )
                )

    return tuple(issues)


def require_compiler_proposal_invariants(
    proposal: Mapping[str, Any],
    catalog: CompilerInvariantCatalogV2,
) -> None:
    issues = validate_compiler_proposal_invariants(proposal, catalog)
    if issues:
        raise CompilerProposalInvariantError(issues)


def validate_plan_adaptation_invariants(
    payload: Mapping[str, Any],
    catalog: CompilerInvariantCatalogV2,
) -> tuple[CompilerProposalValidationIssueV1, ...]:
    """Validate adaptation-only model rules from the shared catalog."""

    issues: list[CompilerProposalValidationIssueV1] = []
    preserved = payload.get("preserved_completed_step_ids")
    if isinstance(preserved, list):
        seen: set[str] = set()
        duplicate_indexes: list[str] = []
        for index, value in enumerate(preserved):
            identity = canonical_sha256(value)
            if identity in seen:
                duplicate_indexes.append(str(index))
            else:
                seen.add(identity)
        if duplicate_indexes:
            issues.append(
                _issue(
                    catalog,
                    "adaptation_preserved_step_unique",
                    ("preserved_completed_step_ids",),
                    observed=tuple(duplicate_indexes),
                )
            )

    adaptation_kind = str(payload.get("adaptation_kind") or "")
    directive_present = payload.get("temporary_tool_transform") is not None
    if (adaptation_kind == "temporary_tool_transform") != directive_present:
        issues.append(
            _issue(
                catalog,
                "adaptation_transform_directive_consistent",
                ("adaptation_kind", "temporary_tool_transform"),
                expected=("temporary_tool_transform" if adaptation_kind == "temporary_tool_transform" else "null",),
                observed=("present" if directive_present else "null",),
            )
        )
    return tuple(issues)


def require_plan_adaptation_invariants(
    payload: Mapping[str, Any],
    catalog: CompilerInvariantCatalogV2,
) -> None:
    issues = validate_plan_adaptation_invariants(payload, catalog)
    if issues:
        raise CompilerProposalInvariantError(issues)


def _json_descriptor(value: Any) -> dict[str, Any]:
    raw_hash = canonical_sha256(value)
    if not isinstance(value, str):
        return {"json_type": "missing", "sha256": raw_hash}
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {"json_type": "invalid", "sha256": raw_hash}
    if decoded is None:
        kind = "null"
    elif isinstance(decoded, bool):
        kind = "boolean"
    elif isinstance(decoded, (int, float)):
        kind = "number"
    elif isinstance(decoded, str):
        kind = "string"
    elif isinstance(decoded, list):
        kind = "array"
    else:
        kind = "object"
    return {"json_type": kind, "sha256": canonical_sha256(decoded)}


def build_compiler_proposal_correction_view(
    proposal: Mapping[str, Any],
) -> CompilerProposalCorrectionViewV1:
    view: dict[str, Any] = {
        "is_sufficient": proposal.get("is_sufficient"),
        "insufficiency_code": proposal.get("insufficiency_code"),
        "final_output": proposal.get("final_output"),
        "steps": [],
    }
    raw_steps = proposal.get("steps")
    for raw_step in raw_steps if isinstance(raw_steps, list) else ():
        if not isinstance(raw_step, Mapping):
            continue
        step_view: dict[str, Any] = {
            name: raw_step.get(name)
            for name in (
                "step_id",
                "resource_id",
                "operation_kind",
                "entrypoint_id",
                "depends_on",
                "consumed_context_source_ids",
                "output_key",
                "advisory_profile_refs",
                "agent_base_model_resource_id",
            )
        }
        bindings: list[dict[str, Any]] = []
        raw_bindings = raw_step.get("input_bindings")
        for raw_binding in raw_bindings if isinstance(raw_bindings, list) else ():
            if not isinstance(raw_binding, Mapping):
                continue
            binding_view = {
                name: raw_binding.get(name)
                for name in (
                    "name",
                    "source_kind",
                    "source_id",
                    "from_step",
                    "output_key",
                    "logical_path",
                )
            }
            if raw_binding.get("value_path") is not None:
                binding_view["value_path"] = raw_binding["value_path"]
            logical_path = binding_view.get("logical_path")
            if _host_path(logical_path) is not None:
                binding_view["logical_path"] = {
                    "redacted_sha256": canonical_sha256(logical_path)
                }
            binding_view["literal_json"] = _json_descriptor(raw_binding.get("literal_json"))
            bindings.append(binding_view)
        step_view["input_bindings"] = bindings
        raw_output = raw_step.get("output_contract")
        if isinstance(raw_output, Mapping):
            step_view["output_contract"] = {
                "mode": raw_output.get("mode"),
                "artifact_type": raw_output.get("artifact_type"),
                "description_sha256": canonical_sha256(raw_output.get("description")),
                "schema_hint_json": _json_descriptor(raw_output.get("schema_hint_json")),
            }
        view["steps"].append(step_view)
    return CompilerProposalCorrectionViewV1(
        proposal_sha256=canonical_sha256(proposal),
        normalized_structure=view,
    )


__all__ = [
    "COMPILER_CONSTRAINT_PROJECTION_PROTOCOL",
    "COMPILER_CORRECTION_VIEW_PROTOCOL",
    "COMPILER_INVARIANT_CATALOG_PROTOCOL",
    "COMPILER_NORMALIZATION_AUDIT_PROTOCOL",
    "COMPILER_SAFE_ISSUE_AUDIT_PROTOCOL",
    "COMPILER_VALIDATION_ISSUE_PROTOCOL",
    "ADAPTATION_MODEL_INVARIANT_PROTOCOL",
    "INITIAL_COMPILER_MODEL_INVARIANT_PROTOCOL",
    "AdaptationModelInvariantCatalogV3",
    "CompilerInvariantCatalogV2",
    "CompilerInvariantRuleV2",
    "InitialCompilerModelInvariantCatalogV3",
    "CompilerProposalCorrectionViewV1",
    "CompilerProposalInvariantError",
    "CompilerProposalNormalizationActionV1",
    "CompilerProposalNormalizationAuditV1",
    "CompilerProposalValidationIssueV1",
    "build_compiler_safe_issue_audits",
    "build_compiler_proposal_correction_view",
    "build_adaptation_model_invariant_catalog",
    "build_initial_compiler_model_invariant_catalog",
    "adaptation_model_invariant_projection",
    "compiler_constraint_prompt_projection",
    "compiler_invariant_request_projection",
    "compiler_invariant_rules",
    "compiler_invariant_validator_projection",
    "initial_compiler_model_invariant_projection",
    "initial_compiler_model_invariant_rules",
    "invariant_id_for_failure_code",
    "normalize_compiler_proposal_payload",
    "project_initial_compiler_correction_v3",
    "require_plan_adaptation_invariants",
    "require_compiler_proposal_invariants",
    "validate_plan_adaptation_invariants",
    "validate_compiler_proposal_invariants",
]
