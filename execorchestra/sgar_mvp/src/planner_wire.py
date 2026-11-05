"""Portable strict wire contracts for Planner model responses.

The live v5 protocol asks the model only for semantic decisions.  Canonical task
identities, topology, edge compatibility, extensions, stages, and execution
projection are compiled deterministically.  Typed v4 and JSON-in-string v3 are
available only through explicit read-only replay entrypoints.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .formal_contracts import (
    ExecutionResourceRequirementV1,
    NodeSemanticContractV2,
    SemanticEdgeContractV2,
    SemanticInputReferenceV2,
    SemanticOutputDescriptorV2,
    SemanticRequirementDeclarationV1,
)
from .pipeline_control import canonical_sha256
from .text_format_contract import TextFormatContract
from .schema import (
    ArtifactType,
    PlannerExecutionMode,
    PlannerOutput,
    RegexFindallAcceptanceProbe,
    TaskStage,
)


PLANNER_WIRE_PROTOCOL = "sgar-planner-wire-v7"
PLANNER_WIRE_PROJECTOR_VERSION = "planner-wire-projector-v7.9-declared-tree-members"
LEGACY_LIVE_PLANNER_WIRE_PROTOCOL = "sgar-planner-wire-v5"
LEGACY_LIVE_PLANNER_WIRE_PROJECTOR_VERSION = "planner-wire-projector-v5.1"
LEGACY_TYPED_PLANNER_WIRE_PROTOCOL = "sgar-planner-wire-v4"
LEGACY_TYPED_PLANNER_WIRE_PROJECTOR_VERSION = "planner-wire-projector-v4"
LEGACY_PLANNER_WIRE_PROTOCOL = "sgar-planner-wire-v3"
LEGACY_PLANNER_WIRE_PROJECTOR_VERSION = "planner-wire-projector-v3"

PLANNER_WIRE_COMPLEXITY_POLICY = {
    "protocol": "sgar-planner-complexity-policy-v1",
    "max_subtasks": 24,
    "max_dependency_edges": 96,
    "max_schema_graphs": 48,
    "max_schema_nodes": 512,
    "max_produced_files": 96,
}
PLANNER_WIRE_COMPLEXITY_POLICY_SHA256 = canonical_sha256(
    PLANNER_WIRE_COMPLEXITY_POLICY
)

_EXECUTION_REQUIREMENT_ID_SAFE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]*$")
_EXECUTION_REQUIREMENT_ID_UNSAFE = re.compile(r"[^A-Za-z0-9_.:-]+")

# Only local, content-free validator identifiers may enter correction feedback.
_WIRE_CONSTRAINT_IDS = frozenset({
    "planner_required_members_require_tree_output",
    "text_format_requires_plaintext_value",
    "regex_acceptance_probes_require_python_regex",
    "python_regex_requires_plaintext_value",
    "planner_input_requirement_conflicts_with_inputs",
})


class PlannerWireContractError(ValueError):
    """The model wire value cannot be losslessly projected to PlannerOutput."""

    def __init__(
        self,
        failure_code: str,
        *,
        paths: Sequence[str] = (),
        invariant_ids: Sequence[str] = (),
    ) -> None:
        self.failure_code = str(failure_code)
        self.paths = tuple(dict.fromkeys(str(item) for item in paths if str(item)))
        self.invariant_ids = tuple(
            dict.fromkeys(str(item) for item in invariant_ids if str(item))
        )
        self.node_path: tuple[str | int, ...] = ()
        self.constraint_details: dict[str, Any] = {}
        self.structural_details: dict[str, Any] = {}
        super().__init__(self.failure_code)


def _pydantic_validation_paths(exc: Exception) -> tuple[str, ...]:
    errors = getattr(exc, "errors", None)
    if not callable(errors):
        return ()
    result: list[str] = []
    try:
        raw_values = errors(
            include_url=False,
            include_context=False,
            include_input=False,
        )
    except TypeError:
        raw_values = errors()
    if not isinstance(raw_values, Sequence) or isinstance(raw_values, (str, bytes)):
        return ()
    values = cast(Sequence[Any], raw_values)
    for raw_item in values:
        if not isinstance(raw_item, Mapping):
            continue
        item = cast(Mapping[str, Any], raw_item)
        location = item.get("loc")
        if isinstance(location, Sequence) and not isinstance(location, (str, bytes)):
            parts = cast(Sequence[Any], location)
            result.append(".".join(str(part) for part in parts))
    return tuple(result)


class _WireModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlannerProducedFileWireV1(_WireModel):
    path_hint: str = Field(min_length=1)
    artifact_type: str = "plaintext"
    required: bool = True
    schema_hint_json: str | None = None


class PlannerOutputContractWireV1(_WireModel):
    artifact_type: ArtifactType
    output_extension: str = ""
    required_content: list[str] = Field(default_factory=list)
    produced_files: list[PlannerProducedFileWireV1] = Field(default_factory=list)
    json_schema_json: str | None = None
    interface_contract_json: str = "{}"
    grounding_requirements: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    downstream_consumers: list[str] = Field(default_factory=list)


class PlannerSubtaskWireV1(_WireModel):
    id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    description: str = Field(min_length=1)
    expected_output: str = Field(min_length=1)
    depends_on: list[str] = Field(default_factory=list)
    artifact_type: ArtifactType
    output_extension: str = ""
    output_contract: PlannerOutputContractWireV1 | None = None
    task_stage: TaskStage | None = None
    planning_execution_mode: PlannerExecutionMode | None = None
    capability_evidence: list[str] = Field(default_factory=list)
    capability_gap: str | None = None


class PlannerOutputWireV1(_WireModel):
    subtasks: list[PlannerSubtaskWireV1]


class PlannerDependencyInputWireV1(_WireModel):
    protocol: Literal["sgar-dependency-input-contract-v1"] = (
        "sgar-dependency-input-contract-v1"
    )
    producer_id: str = Field(min_length=1)
    input_slot: str = Field(min_length=1)
    accepted_artifact_types: list[str] = Field(min_length=1)
    accepted_extensions: list[str]
    consumption_mode: Literal["context_content", "artifact_handle"]
    required_interface_contract_json: str
    required: Literal[True]


class PlannerSubtaskWireV2(_WireModel):
    id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    description: str = Field(min_length=1)
    expected_output: str = Field(min_length=1)
    depends_on: list[str]
    dependency_inputs: list[PlannerDependencyInputWireV1]
    artifact_type: ArtifactType
    output_extension: str
    output_contract: PlannerOutputContractWireV1 | None
    task_stage: TaskStage | None = None
    planning_execution_mode: PlannerExecutionMode | None = None
    capability_evidence: list[str] = Field(default_factory=list)
    capability_gap: str | None = None


class PlannerOutputWireV2(_WireModel):
    subtasks: list[PlannerSubtaskWireV2]


PlannerSchemaNodeKind = Literal[
    "object",
    "array",
    "map",
    "string",
    "integer",
    "number",
    "boolean",
    "null",
    "all_of",
    "any_of",
    "one_of",
]
PlannerStringFormat = Literal[
    "date",
    "date-time",
    "duration",
    "email",
    "hostname",
    "idn-email",
    "idn-hostname",
    "ipv4",
    "ipv6",
    "iri",
    "iri-reference",
    "json-pointer",
    "regex",
    "relative-json-pointer",
    "time",
    "uri",
    "uri-reference",
    "uuid",
]


class PlannerSchemaNodeWireV1(_WireModel):
    """One non-recursive semantic node in a Planner-owned schema graph."""

    node_id: str = Field(min_length=1)
    kind: PlannerSchemaNodeKind
    description: str = ""
    nullable: bool = False
    enum_strings: list[str] = Field(default_factory=list)
    enum_integers: list[int] = Field(default_factory=list)
    enum_numbers: list[float] = Field(default_factory=list)
    enum_booleans: list[bool] = Field(default_factory=list)
    minimum: float | None = None
    maximum: float | None = None
    exclusive_minimum: float | None = None
    exclusive_maximum: float | None = None
    multiple_of: float | None = None
    min_length: int | None = Field(default=None, ge=0)
    max_length: int | None = Field(default=None, ge=0)
    pattern: str | None = None
    format: PlannerStringFormat | None = None
    min_items: int | None = Field(default=None, ge=0)
    max_items: int | None = Field(default=None, ge=0)
    unique_items: bool = False
    min_properties: int | None = Field(default=None, ge=0)
    max_properties: int | None = Field(default=None, ge=0)


class PlannerObjectFieldWireV1(_WireModel):
    object_node_id: str = Field(min_length=1)
    field_name: str = Field(min_length=1)
    value_node_id: str = Field(min_length=1)
    required: bool


class PlannerArrayItemsWireV1(_WireModel):
    array_node_id: str = Field(min_length=1)
    value_node_id: str = Field(min_length=1)


class PlannerMapValueWireV1(_WireModel):
    map_node_id: str = Field(min_length=1)
    value_node_id: str = Field(min_length=1)


class PlannerCombinatorBranchWireV1(_WireModel):
    combinator_node_id: str = Field(min_length=1)
    value_node_id: str = Field(min_length=1)


class PlannerSchemaGraphWireV1(_WireModel):
    """Provider-portable graph compiled to canonical JSON Schema locally."""

    # ``schema_id`` is only a response-local foreign key. The projector uses it
    # to join ``primary_schema_id`` and produced-file references, then discards
    # the label after compiling the authoritative JSON Schemas. Requiring the
    # model to invent a framework-safe identifier spelling is therefore neither
    # a semantic decision nor a downstream safety boundary. Keep only bounded
    # key guards and enforce uniqueness/reference integrity below.
    schema_id: str = Field(min_length=1, max_length=256)
    root_node_id: str = Field(min_length=1)
    nodes: list[PlannerSchemaNodeWireV1] = Field(min_length=1)
    object_fields: list[PlannerObjectFieldWireV1] = Field(default_factory=list)
    array_items: list[PlannerArrayItemsWireV1] = Field(default_factory=list)
    map_values: list[PlannerMapValueWireV1] = Field(default_factory=list)
    combinator_branches: list[PlannerCombinatorBranchWireV1] = Field(
        default_factory=list
    )


class PlannerCsvColumnWireV1(_WireModel):
    name: str = Field(min_length=1)
    value_type: Literal["string", "integer", "number", "boolean"]
    required: bool
    description: str = ""


class PlannerProducedFileWireV4(_WireModel):
    path_hint: str = Field(min_length=1)
    artifact_type: ArtifactType
    required: bool
    schema_id: str | None = None
    csv_columns: list[PlannerCsvColumnWireV1] = Field(default_factory=list)


class PlannerInterfacePropertyWireV1(_WireModel):
    property_name: str = Field(min_length=1)
    value_type: Literal["string", "integer", "number", "boolean", "string_list"]
    string_value: str | None = None
    integer_value: int | None = None
    number_value: float | None = None
    boolean_value: bool | None = None
    string_list_value: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_selected_value(self) -> "PlannerInterfacePropertyWireV1":
        scalar_values = {
            "string": self.string_value,
            "integer": self.integer_value,
            "number": self.number_value,
            "boolean": self.boolean_value,
        }
        populated_scalars = [
            name for name, value in scalar_values.items() if value is not None
        ]
        if self.value_type == "string_list":
            valid = not populated_scalars
        else:
            valid = (
                populated_scalars == [self.value_type]
                and not self.string_list_value
            )
        if not valid:
            raise ValueError("planner_interface_property_value_mismatch")
        return self

    def python_value(self) -> Any:
        if self.value_type == "string":
            return self.string_value
        if self.value_type == "integer":
            return self.integer_value
        if self.value_type == "number":
            return self.number_value
        if self.value_type == "boolean":
            return self.boolean_value
        return list(self.string_list_value)


class PlannerInterfaceCapabilityWireV1(_WireModel):
    capability_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: str | None = None
    properties: list[PlannerInterfacePropertyWireV1] = Field(default_factory=list)


class PlannerOutputContractWireV4(_WireModel):
    contract_status: Literal["expressible", "not_expressible"]
    unexpressible_requirements: list[str] = Field(default_factory=list)
    artifact_type: ArtifactType
    output_extension: str
    required_content: list[str]
    schemas: list[PlannerSchemaGraphWireV1]
    primary_schema_id: str | None
    produced_files: list[PlannerProducedFileWireV4]
    interface_capabilities: list[PlannerInterfaceCapabilityWireV1]
    grounding_requirements: list[str]
    acceptance_criteria: list[str]
    downstream_consumers: list[str]


class PlannerDependencyInputWireV4(_WireModel):
    protocol: Literal["sgar-dependency-input-contract-v1"]
    producer_id: str = Field(min_length=1)
    input_slot: str = Field(min_length=1)
    accepted_artifact_types: list[str] = Field(min_length=1)
    accepted_extensions: list[str]
    consumption_mode: Literal["context_content", "artifact_handle"]
    required_interface_capabilities: list[PlannerInterfaceCapabilityWireV1]
    required: Literal[True]


class PlannerSubtaskWireV4(_WireModel):
    id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    description: str = Field(min_length=1)
    expected_output: str = Field(min_length=1)
    depends_on: list[str]
    dependency_inputs: list[PlannerDependencyInputWireV4]
    artifact_type: ArtifactType
    output_extension: str
    output_contract: PlannerOutputContractWireV4
    task_stage: TaskStage | None
    planning_execution_mode: PlannerExecutionMode | None
    capability_evidence: list[str]
    capability_gap: str | None
    semantic_requirements: list[SemanticRequirementDeclarationV1] = Field(
        min_length=1
    )


class PlannerOutputWireV4(_WireModel):
    protocol: Literal["sgar-planner-wire-v4"]
    subtasks: list[PlannerSubtaskWireV4] = Field(min_length=1)


class PlannerOutputContractWireV5(_WireModel):
    """The single model-owned semantic description of one node output."""

    contract_status: Literal["expressible", "not_expressible"]
    unexpressible_requirements: list[str] = Field(default_factory=list)
    artifact_type: ArtifactType
    required_content: list[str]
    schemas: list[PlannerSchemaGraphWireV1]
    primary_schema_id: str | None
    produced_files: list[PlannerProducedFileWireV4]
    interface_capabilities: list[PlannerInterfaceCapabilityWireV1]
    grounding_requirements: list[str]
    acceptance_criteria: list[str]


class PlannerDependencyUseWireV5(_WireModel):
    """Model-owned purpose for one authoritative dependency edge."""

    producer_key: str = Field(min_length=1)
    input_slot: str = Field(min_length=1)
    consumption_mode: Literal["context_content", "artifact_handle"]
    required_interface_capabilities: list[PlannerInterfaceCapabilityWireV1]


class PlannerSubtaskWireV5(_WireModel):
    """One semantic DAG node before framework identity/execution projection."""

    node_key: str = Field(min_length=1)
    role: str = Field(min_length=1)
    description: str = Field(min_length=1)
    expected_output: str = Field(min_length=1)
    depends_on: list[str]
    dependency_uses: list[PlannerDependencyUseWireV5]
    output: PlannerOutputContractWireV5
    capability_evidence: list[str]
    capability_gap: str | None
    semantic_requirements: list[SemanticRequirementDeclarationV1] = Field(
        min_length=1
    )


class PlannerOutputWireV5(_WireModel):
    protocol: Literal["sgar-planner-wire-v5"]
    subtasks: list[PlannerSubtaskWireV5] = Field(min_length=1, max_length=24)


class PlannerInputReferenceWireV6(_WireModel):
    source: Literal["public_input", "node_output", "completed_output"]
    ref: str = Field(min_length=1)
    purpose: str = Field(min_length=1)


from .evidence_requirements import EvidenceSourceDeclaration


class PlannerNodeOutputWireV6(_WireModel, EvidenceSourceDeclaration):
    logical_name: str = Field(min_length=1)
    artifact_type: Literal[
        "code", "json", "csv", "markdown", "plaintext", "file", "directory", "bundle"
    ]
    contract_scope: Literal["intermediate", "final_deliverable"]
    delivery_mode: Literal["value", "file"]
    semantic_description: str = Field(min_length=1)
    content_kind: Literal["value", "json_schema_document"] = "value"
    syntax_validator: Literal["python_regex", "python_regex_findall_string", "python_regex_findall_whole_match"] | None = None
    acceptance_probes: list[RegexFindallAcceptanceProbe] = Field(default_factory=list, max_length=4)
    text_format: TextFormatContract | None = None
    json_schema_json: str | None = None
    grounding_requirements: list[str] = Field(default_factory=list)
    required_members: list[str] = Field(default_factory=list, max_length=96)

    @model_validator(mode="after")
    def _syntax_validator(self):
        if self.required_members and self.artifact_type not in {"bundle", "directory"}:
            raise ValueError("planner_required_members_require_tree_output")
        if self.text_format is not None and (self.artifact_type != "plaintext" or self.content_kind != "value"):
            raise ValueError("text_format_requires_plaintext_value")
        if self.acceptance_probes and self.syntax_validator not in (
            "python_regex", "python_regex_findall_string", "python_regex_findall_whole_match"
        ):
            raise ValueError("regex_acceptance_probes_require_python_regex")
        if self.syntax_validator in ("python_regex", "python_regex_findall_string", "python_regex_findall_whole_match") and (
            self.artifact_type != "plaintext" or self.content_kind != "value"
        ):
            raise ValueError("python_regex_requires_plaintext_value")
        return self


class PlannerNodeWireV6(_WireModel):
    node_key: str = Field(min_length=1)
    role_intent: str = Field(min_length=1)
    task: str = Field(min_length=1)
    input_requirement: Literal["task_text_only", "requires_material"]
    required_effect: Literal["none", "task_workspace_mutation"] = "none"
    inputs: list[PlannerInputReferenceWireV6]
    output: PlannerNodeOutputWireV6
    acceptance_criteria: list[str] = Field(min_length=1)
    execution_requirements: list[ExecutionResourceRequirementV1] = Field(
        default_factory=list
    )


    @model_validator(mode="after")
    def _input_requirement(self):
        if self.output.external_acquisition_mode == "if_needed" and self.input_requirement != "requires_material":
            raise ValueError("conditional_acquisition_requires_material_inspection")
        if (self.input_requirement == "requires_material") != bool(self.inputs):
            raise ValueError("planner_input_requirement_conflicts_with_inputs")
        return self


class PlannerOutputWireV6(_WireModel):
    protocol: Literal["sgar-planner-wire-v7"]
    nodes: list[PlannerNodeWireV6] = Field(min_length=1, max_length=24)


def _normalize_planner_local_token(
    value: Any,
    *,
    path: str,
    actions: list[str],
) -> Any:
    if not isinstance(value, str):
        return value
    normalized = unicodedata.normalize("NFKC", value).strip()
    if normalized != value:
        actions.append(f"local_identifier_normalized:{path}")
    return normalized


def _normalize_execution_requirement_id(
    value: Any,
    *,
    node_key: str,
    index: int,
    used: set[str],
    path: str,
    actions: list[str],
) -> str:
    """Canonicalize a model-local requirement label without changing its meaning.

    Requirement IDs are internal join keys, not user content or resource
    identities.  Providers occasionally return whitespace, punctuation, or a
    leading digit even when the response schema advertises the pattern.  Make
    that representation error deterministic and preserve the actual typed
    requirement for downstream compilation.
    """

    original = value if isinstance(value, str) else ""
    normalized = unicodedata.normalize("NFKC", original).strip()
    normalized = _EXECUTION_REQUIREMENT_ID_UNSAFE.sub("_", normalized)
    normalized = normalized.strip("_.:-")
    if not normalized or not re.match(r"^[A-Za-z]", normalized):
        normalized = f"req_{normalized}" if normalized else f"req_{node_key}_{index + 1}"
    if not _EXECUTION_REQUIREMENT_ID_SAFE.fullmatch(normalized):
        normalized = f"req_{node_key}_{index + 1}"

    base = normalized
    suffix = 2
    while normalized in used:
        normalized = f"{base}_{suffix}"
        suffix += 1
    used.add(normalized)
    if normalized != original:
        actions.append(f"execution_requirement_id_canonicalized:{path}")
    return normalized


def normalize_planner_wire_ingress(
    value: Any,
) -> tuple[Any, tuple[str, ...]]:
    """Normalize model-local labels without changing Planner-owned semantics."""

    if not isinstance(value, Mapping):
        return value, ()
    payload = deepcopy(dict(value))
    actions: list[str] = []

    # Apply the shared schema-directed null/enum/extra-field normalization here
    # as well so direct projector callers observe the same live boundary.
    from .model_response_contracts import (
        normalize_portable_wire_instance,
        system_role_schema,
    )

    payload = normalize_portable_wire_instance(
        payload,
        system_role_schema("planner"),
        actions=actions,
    )
    local_scalar_fields = {
        "node_key",
        "ref",
        "producer_key",
        "input_slot",
        "schema_id",
        "primary_schema_id",
        "node_id",
        "root_node_id",
        "object_node_id",
        "array_node_id",
        "map_node_id",
        "combinator_node_id",
        "value_node_id",
        "capability_id",
    }

    def visit(item: Any, path: str) -> None:
        if isinstance(item, dict):
            for field_name, child in item.items():
                child_path = f"{path}.{field_name}"
                if field_name in local_scalar_fields:
                    item[field_name] = _normalize_planner_local_token(
                        child,
                        path=child_path,
                        actions=actions,
                    )
                elif field_name == "depends_on" and isinstance(child, list):
                    item[field_name] = [
                        _normalize_planner_local_token(
                            dependency,
                            path=f"{child_path}[{index}]",
                            actions=actions,
                        )
                        for index, dependency in enumerate(child)
                    ]
                elif field_name == "evidence_source_ids" and isinstance(child, list):
                    for index, evidence_id in enumerate(child):
                        if isinstance(evidence_id, str) and evidence_id.startswith(
                            "subtask_output:"
                        ):
                            prefix, local_key = evidence_id.split(":", 1)
                            normalized_key = _normalize_planner_local_token(
                                local_key,
                                path=f"{child_path}[{index}]",
                                actions=actions,
                            )
                            child[index] = f"{prefix}:{normalized_key}"
                else:
                    visit(child, child_path)
        elif isinstance(item, list):
            for index, child in enumerate(item):
                visit(child, f"{path}[{index}]")

    visit(payload, "$")

    # A recognized filename extension is a mechanical representation fact, not
    # a planning decision.  Normalize only the generic ``file`` label; conflicts
    # between two specific artifact types remain semantic errors for correction.
    extension_types = {
        ".json": "json",
        ".csv": "csv",
        ".md": "markdown",
        ".markdown": "markdown",
        ".txt": "plaintext",
        ".py": "code",
        ".js": "code",
        ".ts": "code",
    }
    nodes = payload.get("nodes")
    if isinstance(nodes, list):
        for index, node in enumerate(nodes):
            if not isinstance(node, dict):
                continue
            requirements = node.get("execution_requirements")
            if isinstance(requirements, list):
                used_requirement_ids: set[str] = set()
                node_key = str(node.get("node_key") or f"node_{index + 1}")
                normalized_requirements: list[Any] = []
                resource_prefix_by_type = {
                    "Model": "model.",
                    "Agent": "agent.",
                    "Tool": "tool.",
                    "Skill": "skill.",
                }
                for requirement_index, requirement in enumerate(requirements):
                    if not isinstance(requirement, dict):
                        normalized_requirements.append(requirement)
                        continue
                    requirement_path = (
                        f"$.nodes[{index}].execution_requirements[{requirement_index}]"
                    )
                    requirement["requirement_id"] = _normalize_execution_requirement_id(
                        requirement.get("requirement_id"),
                        node_key=node_key,
                        index=requirement_index,
                        used=used_requirement_ids,
                        path=f"{requirement_path}.requirement_id",
                        actions=actions,
                    )
                    resource_id = str(requirement.get("resource_id") or "").strip()
                    expected_prefix = resource_prefix_by_type.get(
                        str(requirement.get("resource_type") or "")
                    )
                    if (
                        resource_id
                        and expected_prefix is not None
                        and not resource_id.casefold().startswith(expected_prefix)
                    ):
                        if (
                            requirement.get("resource_type") == "Model"
                            and str(requirement.get("api_model_id") or "").strip()
                        ):
                            requirement["resource_id"] = None
                            actions.append(
                                f"non_catalog_resource_alias_removed:{requirement_path}.resource_id"
                            )
                        else:
                            actions.append(
                                f"runtime_implementation_constraint_removed:{requirement_path}"
                            )
                            continue
                    normalized_requirements.append(requirement)
                node["execution_requirements"] = normalized_requirements
            output = node.get("output")
            if not isinstance(output, dict):
                continue
            logical_name = output.get("logical_name")
            artifact_type = output.get("artifact_type")
            if not isinstance(logical_name, str) or artifact_type != "file":
                continue
            normalized_name = logical_name.strip().lower()
            inferred = next(
                (
                    value
                    for suffix, value in extension_types.items()
                    if normalized_name.endswith(suffix)
                ),
                None,
            )
            if inferred is not None:
                output["artifact_type"] = inferred
                actions.append(
                    f"artifact_type_normalized_from_extension:$.nodes[{index}].output.artifact_type"
                )

    return payload, tuple(dict.fromkeys(actions))


def _schema_ref(node_id: str) -> dict[str, str]:
    return {"$ref": f"#/$defs/{node_id}"}


def _constraint_kind_error(
    code: str, node: PlannerSchemaNodeWireV1,
    fields: Sequence[str], kinds: Sequence[str],
) -> PlannerWireContractError:
    """Attach facts at the existing rejection; never normalize a model constraint."""
    inactive = {
        field: [] if field.startswith("enum_") else False if field == "unique_items" else None
        for field in fields
    }
    active = {field: getattr(node, field) for field in fields
              if getattr(node, field) != inactive[field]}
    error = PlannerWireContractError(code)
    error.constraint_details = {
        "reason_code": code, "node_id": node.node_id, "kind": node.kind,
        "observed_fields": active, "allowed_kinds": list(kinds),
        "inactive_values": {field: inactive[field] for field in active},
    }
    return error


def _validate_schema_node_constraints(node: PlannerSchemaNodeWireV1) -> None:
    enum_groups = {
        "string": node.enum_strings,
        "integer": node.enum_integers,
        "number": node.enum_numbers,
        "boolean": node.enum_booleans,
    }
    populated_enum_groups = [name for name, values in enum_groups.items() if values]
    if populated_enum_groups and populated_enum_groups != [node.kind]:
        suffixes = {"string": "strings", "integer": "integers", "number": "numbers", "boolean": "booleans"}
        wrong_kinds = tuple(kind for kind in populated_enum_groups if kind != node.kind)
        raise _constraint_kind_error(
            "planner_schema_enum_kind_mismatch", node,
            tuple("enum_" + suffixes[kind] for kind in wrong_kinds), wrong_kinds,
        )
    numeric_values = (
        node.minimum,
        node.maximum,
        node.exclusive_minimum,
        node.exclusive_maximum,
        node.multiple_of,
    )
    if any(value is not None for value in numeric_values) and node.kind not in {
        "integer",
        "number",
    }:
        raise _constraint_kind_error(
            "planner_schema_numeric_constraint_kind_mismatch", node,
            ("minimum", "maximum", "exclusive_minimum", "exclusive_maximum", "multiple_of"), ("integer", "number"),
        )
    if node.multiple_of is not None and node.multiple_of <= 0:
        raise PlannerWireContractError("planner_schema_multiple_of_invalid")
    if node.minimum is not None and node.maximum is not None and node.minimum > node.maximum:
        raise PlannerWireContractError("planner_schema_numeric_bounds_invalid")
    if (
        node.exclusive_minimum is not None
        and node.exclusive_maximum is not None
        and node.exclusive_minimum >= node.exclusive_maximum
    ):
        raise PlannerWireContractError("planner_schema_exclusive_bounds_invalid")
    if node.kind == "integer":
        for value in numeric_values:
            if value is not None and not float(value).is_integer():
                raise PlannerWireContractError(
                    "planner_schema_integer_constraint_not_integer"
                )
    if any(
        value is not None
        for value in (node.min_length, node.max_length, node.pattern, node.format)
    ) and node.kind != "string":
        raise _constraint_kind_error(
            "planner_schema_string_constraint_kind_mismatch", node,
            ("min_length", "max_length", "pattern", "format"), ("string",),
        )
    if (
        node.min_length is not None
        and node.max_length is not None
        and node.min_length > node.max_length
    ):
        raise PlannerWireContractError("planner_schema_string_bounds_invalid")
    if any(value is not None for value in (node.min_items, node.max_items)) or node.unique_items:
        if node.kind != "array":
            raise _constraint_kind_error(
                "planner_schema_array_constraint_kind_mismatch", node,
                ("min_items", "max_items", "unique_items"), ("array",),
            )
    if (
        node.min_items is not None
        and node.max_items is not None
        and node.min_items > node.max_items
    ):
        raise PlannerWireContractError("planner_schema_array_bounds_invalid")
    if any(value is not None for value in (node.min_properties, node.max_properties)):
        if node.kind not in {"object", "map"}:
            raise _constraint_kind_error(
                "planner_schema_object_constraint_kind_mismatch", node,
                ("min_properties", "max_properties"), ("object", "map"),
            )
    if (
        node.min_properties is not None
        and node.max_properties is not None
        and node.min_properties > node.max_properties
    ):
        raise PlannerWireContractError("planner_schema_object_bounds_invalid")
    if node.nullable and node.kind == "null":
        raise PlannerWireContractError("planner_schema_null_node_nullable_redundant")


def compile_planner_schema_graph(graph: PlannerSchemaGraphWireV1) -> dict[str, Any]:
    """Compile one acyclic semantic graph to canonical enforceable JSON Schema."""

    nodes: dict[str, PlannerSchemaNodeWireV1] = {}
    for index, node in enumerate(graph.nodes):
        if node.node_id in nodes:
            raise PlannerWireContractError("planner_schema_node_id_duplicate")
        try:
            _validate_schema_node_constraints(node)
        except PlannerWireContractError as exc:
            if exc.constraint_details:
                exc.node_path = ("nodes", index)
            raise
        nodes[node.node_id] = node
    if graph.root_node_id not in nodes:
        raise PlannerWireContractError("planner_schema_root_node_missing")
    canonical_node_ids = {
        node.node_id: f"node_{index:04d}"
        for index, node in enumerate(graph.nodes, start=1)
    }

    object_fields: dict[str, list[PlannerObjectFieldWireV1]] = defaultdict(list)
    array_items: dict[str, list[PlannerArrayItemsWireV1]] = defaultdict(list)
    map_values: dict[str, list[PlannerMapValueWireV1]] = defaultdict(list)
    branches: dict[str, list[PlannerCombinatorBranchWireV1]] = defaultdict(list)
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in nodes}

    def structure_error(code: str, path: tuple[str | int, ...], **details: Any) -> PlannerWireContractError:
        error = PlannerWireContractError(code)
        error.node_path = path
        error.structural_details = details
        return error

    def require_relation(parent_id: str, value_id: str, expected_kinds: set[str], path: tuple[str | int, ...]) -> None:
        parent = nodes.get(parent_id)
        if parent is None or value_id not in nodes:
            raise structure_error("planner_schema_relation_node_missing", path,
                parent_node_id=parent_id, value_node_id=value_id,
                expected="Both relation endpoints must name declared nodes.")
        if parent.kind not in expected_kinds:
            raise structure_error("planner_schema_relation_parent_kind_invalid", path,
                parent_node_id=parent_id, observed_kind=parent.kind, expected_kinds=sorted(expected_kinds),
                expected="Use the relation family matching the parent node's kind; preserve intended child semantics.")
        adjacency[parent_id].add(value_id)

    for index, field in enumerate(graph.object_fields):
        require_relation(field.object_node_id, field.value_node_id, {"object"}, ("object_fields", index))
        object_fields[field.object_node_id].append(field)
    for index, relation in enumerate(graph.array_items):
        require_relation(relation.array_node_id, relation.value_node_id, {"array"}, ("array_items", index))
        array_items[relation.array_node_id].append(relation)
    for index, relation in enumerate(graph.map_values):
        require_relation(relation.map_node_id, relation.value_node_id, {"map"}, ("map_values", index))
        map_values[relation.map_node_id].append(relation)
    for index, relation in enumerate(graph.combinator_branches):
        require_relation(
            relation.combinator_node_id,
            relation.value_node_id,
            {"all_of", "any_of", "one_of"},
            ("combinator_branches", index),
        )
        branches[relation.combinator_node_id].append(relation)

    for index, (node_id, node) in enumerate(nodes.items()):
        if node.kind == "object":
            names = [item.field_name for item in object_fields[node_id]]
            if not names:
                raise PlannerWireContractError("planner_schema_object_fields_empty")
            if len(names) != len(set(names)):
                raise PlannerWireContractError("planner_schema_object_field_duplicate")
        elif object_fields[node_id]:
            raise PlannerWireContractError("planner_schema_object_field_parent_invalid")
        if node.kind == "array" and len(array_items[node_id]) != 1:
            raise structure_error("planner_schema_array_items_cardinality", ("nodes", index),
                node_id=node_id, observed_count=len(array_items[node_id]), expected_count=1,
                expected="Declare exactly one array_items relation for this array node; value_node_id identifies its item Schema node.")
        if node.kind != "array" and array_items[node_id]:
            raise PlannerWireContractError("planner_schema_array_items_parent_invalid")
        if node.kind == "map" and len(map_values[node_id]) != 1:
            raise structure_error("planner_schema_map_value_cardinality", ("nodes", index),
                node_id=node_id, observed_count=len(map_values[node_id]), expected_count=1,
                expected="Declare exactly one map_values relation for this map node.")
        if node.kind != "map" and map_values[node_id]:
            raise PlannerWireContractError("planner_schema_map_value_parent_invalid")
        if node.kind in {"all_of", "any_of", "one_of"} and len(branches[node_id]) < 2:
            raise structure_error("planner_schema_combinator_branch_cardinality", ("nodes", index),
                node_id=node_id, observed_count=len(branches[node_id]), minimum_count=2,
                expected="Declare at least two combinator_branches relations for this combinator node.")
        if node.kind not in {"all_of", "any_of", "one_of"} and branches[node_id]:
            raise PlannerWireContractError("planner_schema_combinator_parent_invalid")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise PlannerWireContractError("planner_schema_graph_cycle")
        if node_id in visited:
            return
        visiting.add(node_id)
        for child_id in sorted(adjacency[node_id]):
            visit(child_id)
        visiting.remove(node_id)
        visited.add(node_id)

    visit(graph.root_node_id)
    if visited != set(nodes):
        raise PlannerWireContractError("planner_schema_graph_unreachable_node")

    definitions: dict[str, dict[str, Any]] = {}
    for node_id in (node.node_id for node in graph.nodes):
        node = nodes[node_id]
        if node.kind == "object":
            fields = sorted(object_fields[node_id], key=lambda item: item.field_name)
            definition: dict[str, Any] = {
                "type": "object",
                "properties": {
                    item.field_name: _schema_ref(canonical_node_ids[item.value_node_id])
                    for item in fields
                },
                "required": sorted(item.field_name for item in fields if item.required),
                "additionalProperties": False,
            }
        elif node.kind == "array":
            definition = {
                "type": "array",
                "items": _schema_ref(
                    canonical_node_ids[array_items[node_id][0].value_node_id]
                ),
            }
        elif node.kind == "map":
            definition = {
                "type": "object",
                "additionalProperties": _schema_ref(
                    canonical_node_ids[map_values[node_id][0].value_node_id]
                ),
            }
        elif node.kind in {"all_of", "any_of", "one_of"}:
            keyword = {
                "all_of": "allOf",
                "any_of": "anyOf",
                "one_of": "oneOf",
            }[node.kind]
            definition = {
                keyword: [
                    _schema_ref(canonical_node_ids[item.value_node_id])
                    for item in sorted(
                        branches[node_id], key=lambda item: item.value_node_id
                    )
                ]
            }
        else:
            definition = {"type": node.kind}

        if node.description:
            definition["description"] = node.description
        enum_values: Sequence[Any] = {
            "string": node.enum_strings,
            "integer": node.enum_integers,
            "number": node.enum_numbers,
            "boolean": node.enum_booleans,
        }.get(node.kind, ())
        if enum_values:
            definition["enum"] = list(enum_values)
        for field_name, keyword in (
            ("minimum", "minimum"),
            ("maximum", "maximum"),
            ("exclusive_minimum", "exclusiveMinimum"),
            ("exclusive_maximum", "exclusiveMaximum"),
            ("multiple_of", "multipleOf"),
            ("min_length", "minLength"),
            ("max_length", "maxLength"),
            ("pattern", "pattern"),
            ("format", "format"),
            ("min_items", "minItems"),
            ("max_items", "maxItems"),
            ("min_properties", "minProperties"),
            ("max_properties", "maxProperties"),
        ):
            value = getattr(node, field_name)
            if value is not None:
                definition[keyword] = value
        if node.unique_items:
            definition["uniqueItems"] = True
        if node.nullable:
            definition = {"anyOf": [definition, {"type": "null"}]}
        definitions[canonical_node_ids[node_id]] = definition

    schema = {
        "$defs": definitions,
        "$ref": f"#/$defs/{canonical_node_ids[graph.root_node_id]}",
    }
    try:
        from .model_response_contracts import require_semantic_json_schema

        return require_semantic_json_schema(schema)
    except PlannerWireContractError:
        raise
    except Exception as exc:
        raise PlannerWireContractError(
            "planner_framework_schema_compile_failure",
            invariant_ids=("planner_deterministic_schema_compiler",),
        ) from exc


def _project_interface_capabilities(
    capabilities: Sequence[PlannerInterfaceCapabilityWireV1],
) -> dict[str, Any]:
    seen: set[str] = set()
    projected: list[dict[str, Any]] = []
    for capability in sorted(capabilities, key=lambda item: item.capability_id):
        if capability.capability_id in seen:
            raise PlannerWireContractError("planner_interface_capability_id_duplicate")
        seen.add(capability.capability_id)
        properties: dict[str, Any] = {}
        for item in sorted(capability.properties, key=lambda value: value.property_name):
            if item.property_name in properties:
                raise PlannerWireContractError(
                    "planner_interface_property_name_duplicate"
                )
            properties[item.property_name] = item.python_value()
        projected.append(
            {
                "capability_id": capability.capability_id,
                "kind": capability.kind,
                "name": capability.name,
                "version": capability.version,
                "properties": properties,
            }
        )
    return {"capabilities": projected} if projected else {}


def _compile_output_contract(
    contract: PlannerOutputContractWireV4 | PlannerOutputContractWireV5,
) -> dict[str, Any]:
    if contract.contract_status == "not_expressible":
        if not contract.unexpressible_requirements:
            raise PlannerWireContractError(
                "planner_contract_not_expressible_reason_missing"
            )
        raise PlannerWireContractError("planner_contract_not_expressible")
    if contract.unexpressible_requirements:
        raise PlannerWireContractError(
            "planner_contract_expressible_has_unexpressible_requirements"
        )

    compiled_schemas: dict[str, dict[str, Any]] = {}
    for graph in contract.schemas:
        if graph.schema_id in compiled_schemas:
            raise PlannerWireContractError("planner_schema_id_duplicate")
        compiled_schemas[graph.schema_id] = compile_planner_schema_graph(graph)

    artifact_type = contract.artifact_type.value
    if artifact_type == "json":
        if not contract.primary_schema_id:
            raise PlannerWireContractError("planner_primary_json_schema_missing")
        if contract.primary_schema_id not in compiled_schemas:
            raise PlannerWireContractError("planner_primary_json_schema_unknown")
        primary_schema = compiled_schemas[contract.primary_schema_id]
    else:
        if contract.primary_schema_id is not None:
            raise PlannerWireContractError(
                "planner_primary_schema_requires_json_artifact"
            )
        primary_schema = None

    produced_files: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for produced in contract.produced_files:
        if produced.path_hint in seen_paths:
            raise PlannerWireContractError("planner_produced_file_path_duplicate")
        seen_paths.add(produced.path_hint)
        produced_type = produced.artifact_type.value
        if produced_type == "json":
            if not produced.schema_id or produced.schema_id not in compiled_schemas:
                raise PlannerWireContractError(
                    "planner_produced_json_schema_reference_invalid"
                )
            if produced.csv_columns:
                raise PlannerWireContractError(
                    "planner_produced_json_has_csv_columns"
                )
            schema_hint: Any = compiled_schemas[produced.schema_id]
        elif produced_type == "csv":
            if produced.schema_id is not None or not produced.csv_columns:
                raise PlannerWireContractError(
                    "planner_produced_csv_structure_invalid"
                )
            names = [item.name for item in produced.csv_columns]
            if len(names) != len(set(names)):
                raise PlannerWireContractError(
                    "planner_produced_csv_column_duplicate"
                )
            schema_hint = [item.model_dump(mode="json") for item in produced.csv_columns]
        else:
            if produced.schema_id is not None or produced.csv_columns:
                raise PlannerWireContractError(
                    "planner_unstructured_file_has_structure"
                )
            schema_hint = None
        produced_files.append(
            {
                "path_hint": produced.path_hint,
                "artifact_type": produced_type,
                "required": produced.required,
                "schema_hint": schema_hint,
            }
        )

    return {
        "artifact_type": artifact_type,
        "output_extension": (
            contract.output_extension
            if isinstance(contract, PlannerOutputContractWireV4)
            else _default_extension(artifact_type)
        ),
        "required_content": list(contract.required_content),
        "produced_files": produced_files,
        "json_schema": primary_schema,
        "interface_contract": _project_interface_capabilities(
            contract.interface_capabilities
        ),
        "grounding_requirements": list(contract.grounding_requirements),
        "acceptance_criteria": list(contract.acceptance_criteria),
        "downstream_consumers": (
            list(contract.downstream_consumers)
            if isinstance(contract, PlannerOutputContractWireV4)
            else []
        ),
    }


def _default_extension(artifact_type: str | ArtifactType) -> str:
    from .planner_contracts import default_extension

    return default_extension(artifact_type)


def _explicit_member_produced_files(members: Sequence[str]) -> list[dict[str, Any]]:
    """Project explicit bundle members into exact workspace file obligations."""

    from .planner_contracts import _known_extension_artifact

    produced: list[dict[str, Any]] = []
    for member in members:
        normalized = str(member).replace("\\", "/").strip().lstrip("/")
        if normalized.startswith("app/"):
            normalized = normalized.removeprefix("app/")
        suffix = Path(normalized).suffix.lower()
        produced.append({
            "path_hint": f"/app/{normalized}",
            "artifact_type": _known_extension_artifact(suffix) or "file",
            "required": True,
            "schema_hint": None,
        })
    return produced


def _wire_output_extension(output: PlannerNodeOutputWireV6) -> str:
    """Derive a physical extension from the declared logical filename.

    V6 intentionally keeps ``artifact_type`` semantic (for example ``code``),
    while benchmark tasks may require a language-specific physical suffix such
    as ``.v`` or ``.sql``.  Dependency ports must carry that physical suffix;
    falling back to the generic ``code -> .py`` mapping makes otherwise valid
    cross-node contracts fail during projection.
    """

    # A bundle is a typed collection of member files.  Its logical name is a
    # label, not one physical member, so a suffix on that label cannot become
    # the bundle's output extension.  Exact member suffixes live in
    # produced_files and remain independently enforceable.
    if output.artifact_type == "bundle":
        return ""
    logical_name = str(output.logical_name or "").strip()
    suffix = Path(logical_name).suffix.lower()
    if suffix and suffix != ".":
        return suffix
    return _default_extension(output.artifact_type)


def _align_derived_v7_dependency_extensions(output: PlannerOutput) -> PlannerOutput:
    """Keep framework-created edge ports aligned with producer file contracts.

    V7 does not ask the model to specify accepted extensions.  The compatibility
    ports are derived here, so their physical suffix must follow the same rule
    used when the producer contract is canonicalized downstream.
    """

    from .planner_contracts import _known_extension, _produced_file_extensions

    producer_extensions: dict[str, str] = {}
    for producer in output.subtasks:
        contract = producer.output_contract
        if contract is None:
            continue
        extension = _known_extension(
            contract.output_extension or producer.output_extension
        )
        required_file_extensions = _produced_file_extensions(contract)
        if len(required_file_extensions) == 1:
            extension = required_file_extensions[0]
        producer_extensions[producer.id] = extension

    aligned = []
    for consumer in output.subtasks:
        inputs = [
            item.model_copy(
                update={"accepted_extensions": (producer_extensions[item.producer_id],)}
            )
            if item.producer_id in producer_extensions
            and item.accepted_extensions
            != (producer_extensions[item.producer_id],)
            else item
            for item in consumer.dependency_inputs
        ]
        aligned.append(consumer.model_copy(update={"dependency_inputs": inputs}))
    return output.model_copy(update={"subtasks": aligned})


_EXTERNAL_GROUNDING_MARKERS = (
    "external source",
    "external fact",
    "public source",
    "public web",
    "web search",
    "internet",
    "online",
    "browse",
    "search the web",
    "changelog",
    "release notes",
    "historical record",
    "according to the",
    "according to official",
    '\u6839\u636e\u516c\u5f00',
    '\u6839\u636e\u5b98\u7f51',
    '\u7f51\u9875\u641c\u7d22',
    '\u4e92\u8054\u7f51',
    '\u66f4\u65b0\u65e5\u5fd7',
)


def _generic_grounding_requirements(item: PlannerNodeWireV6) -> list[str]:
    """Preserve external-fact obligations without leaking answers or resources."""

    declared = [
        str(value).strip()
        for value in item.output.grounding_requirements
        if str(value).strip()
    ]
    from .capability_operations import requires_external_grounding

    text = " ".join(
        [
            item.task,
            item.output.semantic_description,
            *item.acceptance_criteria,
            *(reference.purpose for reference in getattr(item, "inputs", ())),
        ]
    )
    anchored_external_grounding = requires_external_grounding(
        text, evidence_source_scope=getattr(item.output, "evidence_source_scope", None)
    )
    if declared:
        # The Planner owns the semantic source requirement. An attachment can
        # supply identifiers or references without supplying the needed facts.
        # Preserve that declaration across paraphrases; keyword inference is
        # only a fallback for nodes that did not declare external evidence.
        return list(dict.fromkeys(declared))
    if anchored_external_grounding:
        return [
            "Acquire and verify the external factual evidence required by the task using an authorized public-source capability before synthesis.",
            "Preserve source provenance and distinguish retrieved evidence from model-generated content.",
        ]
    return []


def _derive_execution_mode(
    requirements: Sequence[SemanticRequirementDeclarationV1],
) -> PlannerExecutionMode:
    natures = {item.work_nature for item in requirements}
    if natures == {"deterministic"}:
        return PlannerExecutionMode.RESOURCE_GROUNDED
    if natures == {"generative"}:
        return PlannerExecutionMode.GENERATIVE
    return PlannerExecutionMode.HYBRID


def _validate_v5_complexity(wire: PlannerOutputWireV5) -> None:
    totals = {
        "dependency_edges": sum(len(item.depends_on) for item in wire.subtasks),
        "schema_graphs": sum(len(item.output.schemas) for item in wire.subtasks),
        "schema_nodes": sum(
            len(graph.nodes)
            for item in wire.subtasks
            for graph in item.output.schemas
        ),
        "produced_files": sum(
            len(item.output.produced_files) for item in wire.subtasks
        ),
    }
    limits = {
        "dependency_edges": int(PLANNER_WIRE_COMPLEXITY_POLICY["max_dependency_edges"]),
        "schema_graphs": int(PLANNER_WIRE_COMPLEXITY_POLICY["max_schema_graphs"]),
        "schema_nodes": int(PLANNER_WIRE_COMPLEXITY_POLICY["max_schema_nodes"]),
        "produced_files": int(PLANNER_WIRE_COMPLEXITY_POLICY["max_produced_files"]),
    }
    exceeded = [name for name, value in totals.items() if value > limits[name]]
    if exceeded:
        raise PlannerWireContractError(
            "planner_complexity_policy_exceeded",
            paths=tuple(exceeded),
            invariant_ids=("planner_complexity_policy_v1",),
        )


def _topological_v5_nodes(
    wire: PlannerOutputWireV5,
) -> tuple[list[PlannerSubtaskWireV5], dict[str, str], dict[str, list[str]]]:
    by_key: dict[str, PlannerSubtaskWireV5] = {}
    for item in wire.subtasks:
        if item.node_key in by_key:
            raise PlannerWireContractError(
                "planner_node_key_duplicate",
                paths=(f"subtasks[{item.node_key}].node_key",),
                invariant_ids=("planner_node_key_unique",),
            )
        by_key[item.node_key] = item
    consumers: dict[str, list[str]] = {key: [] for key in by_key}
    indegree: dict[str, int] = {}
    for item in wire.subtasks:
        dependencies = list(item.depends_on)
        if len(dependencies) != len(set(dependencies)):
            raise PlannerWireContractError(
                "planner_dependency_duplicate",
                paths=(f"subtasks[{item.node_key}].depends_on",),
                invariant_ids=("planner_authoritative_dependency_unique",),
            )
        unknown = sorted(set(dependencies) - set(by_key))
        if unknown or item.node_key in dependencies:
            raise PlannerWireContractError(
                "planner_dependency_invalid",
                paths=(f"subtasks[{item.node_key}].depends_on",),
                invariant_ids=("planner_dependency_known_and_not_self",),
            )
        indegree[item.node_key] = len(dependencies)
        for producer_key in dependencies:
            consumers[producer_key].append(item.node_key)
    ready = sorted(key for key, value in indegree.items() if value == 0)
    ordered: list[PlannerSubtaskWireV5] = []
    while ready:
        node_key = ready.pop(0)
        ordered.append(by_key[node_key])
        for consumer_key in sorted(consumers[node_key]):
            indegree[consumer_key] -= 1
            if indegree[consumer_key] == 0:
                ready.append(consumer_key)
                ready.sort()
    if len(ordered) != len(wire.subtasks):
        raise PlannerWireContractError(
            "planner_dag_cycle",
            paths=("subtasks.depends_on",),
            invariant_ids=("planner_authoritative_dag_acyclic",),
        )
    canonical_ids = {
        item.node_key: f"task_{index:03d}"
        for index, item in enumerate(ordered, start=1)
    }
    return ordered, canonical_ids, consumers


def _parse_json_object(value: str, *, error_prefix: str) -> dict[str, Any]:
    def reject_constant(token: str) -> None:
        raise ValueError(f"non_finite_json_constant:{token}")

    try:
        decoded = json.loads(str(value), parse_constant=reject_constant)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise PlannerWireContractError(f"{error_prefix}_invalid") from exc
    if not isinstance(decoded, dict):
        raise PlannerWireContractError(f"{error_prefix}_not_object")
    try:
        json.dumps(
            decoded,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise PlannerWireContractError(f"{error_prefix}_not_canonicalizable") from exc
    return cast(dict[str, Any], decoded)


def _parse_interface_contract(value: str) -> dict[str, Any]:
    return _parse_json_object(
        value,
        error_prefix="planner_interface_contract_json",
    )


def _parse_json_schema(value: str | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return _parse_json_object(value, error_prefix="planner_output_json_schema")


def _parse_json_value(value: str | None, *, error_prefix: str) -> Any:
    if value is None:
        return None

    def reject_constant(token: str) -> None:
        raise ValueError(f"non_finite_json_constant:{token}")

    try:
        decoded = json.loads(str(value), parse_constant=reject_constant)
        json.dumps(
            decoded,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise PlannerWireContractError(f"{error_prefix}_invalid") from exc
    return decoded


def project_legacy_planner_wire_payload_v3(value: Mapping[str, Any]) -> PlannerOutput:
    """Explicitly project one historical JSON-in-string v3 response."""

    try:
        wire = PlannerOutputWireV2.model_validate(value)
    except Exception as exc:
        raise PlannerWireContractError("planner_wire_payload_invalid") from exc

    subtasks: list[dict[str, Any]] = []
    for item in wire.subtasks:
        projected = item.model_dump(mode="json", exclude={"output_contract"})
        if item.output_contract is None:
            projected["output_contract"] = None
        else:
            output_contract = item.output_contract.model_dump(
                mode="json",
                exclude={
                    "interface_contract_json",
                    "json_schema_json",
                    "produced_files",
                },
            )
            output_contract["produced_files"] = [
                {
                    "path_hint": produced.path_hint,
                    "artifact_type": produced.artifact_type,
                    "required": produced.required,
                    "schema_hint": _parse_json_value(
                        produced.schema_hint_json,
                        error_prefix="planner_produced_file_schema_hint_json",
                    ),
                }
                for produced in item.output_contract.produced_files
            ]
            output_contract["json_schema"] = _parse_json_schema(
                item.output_contract.json_schema_json
            )
            output_contract["interface_contract"] = _parse_interface_contract(
                item.output_contract.interface_contract_json
            )
            projected["output_contract"] = output_contract
        subtasks.append(projected)
    try:
        return PlannerOutput.model_validate({"subtasks": subtasks})
    except Exception as exc:
        raise PlannerWireContractError("planner_wire_projection_invalid") from exc


def project_legacy_planner_wire_payload_v4(
    value: Mapping[str, Any],
) -> PlannerOutput:
    """Project one historical typed v4 response for read-only replay."""

    try:
        wire = PlannerOutputWireV4.model_validate(value)
    except Exception as exc:
        raise PlannerWireContractError(
            "planner_wire_v4_payload_invalid",
            paths=_pydantic_validation_paths(exc),
            invariant_ids=("planner_wire_v4_outer_schema",),
        ) from exc

    subtasks: list[dict[str, Any]] = []
    for item in wire.subtasks:
        projected = item.model_dump(
            mode="json",
            exclude={"output_contract", "dependency_inputs"},
        )
        try:
            projected["output_contract"] = _compile_output_contract(
                item.output_contract
            )
        except PlannerWireContractError as exc:
            raise PlannerWireContractError(
                exc.failure_code,
                paths=(
                    *(f"subtasks[{item.id}].{path}" for path in exc.paths),
                    f"subtasks[{item.id}].output_contract",
                ),
                invariant_ids=exc.invariant_ids
                or ("planner_typed_output_contract_valid",),
            ) from exc
        projected["dependency_inputs"] = [
            {
                "protocol": dependency.protocol,
                "producer_id": dependency.producer_id,
                "input_slot": dependency.input_slot,
                "accepted_artifact_types": list(
                    dependency.accepted_artifact_types
                ),
                "accepted_extensions": list(dependency.accepted_extensions),
                "consumption_mode": dependency.consumption_mode,
                "required_interface_contract_json": _project_interface_capabilities(
                    dependency.required_interface_capabilities
                ),
                "required": dependency.required,
            }
            for dependency in item.dependency_inputs
        ]
        subtasks.append(projected)
    try:
        return PlannerOutput.model_validate({"subtasks": subtasks})
    except Exception as exc:
        raise PlannerWireContractError("planner_wire_v4_projection_invalid") from exc


def project_planner_wire_v5_replay(value: Mapping[str, Any]) -> PlannerOutput:
    """Validate and project one frozen V5 payload for read-only replay."""

    try:
        wire = PlannerOutputWireV5.model_validate(value)
    except PlannerWireContractError:
        raise
    except Exception as exc:
        raise PlannerWireContractError(
            "planner_wire_v5_payload_invalid",
            paths=_pydantic_validation_paths(exc),
            invariant_ids=("planner_wire_v5_outer_schema",),
        ) from exc
    _validate_v5_complexity(wire)
    ordered, canonical_ids, consumers = _topological_v5_nodes(wire)
    compiled_outputs: dict[str, dict[str, Any]] = {}
    for item in ordered:
        try:
            compiled_outputs[item.node_key] = _compile_output_contract(item.output)
        except PlannerWireContractError as exc:
            raise PlannerWireContractError(
                exc.failure_code,
                paths=(
                    *(f"subtasks[{item.node_key}].{path}" for path in exc.paths),
                    f"subtasks[{item.node_key}].output",
                ),
                invariant_ids=exc.invariant_ids
                or ("planner_typed_output_contract_valid",),
            ) from exc

    subtasks: list[dict[str, Any]] = []
    for item in ordered:
        dependency_by_producer: dict[str, PlannerDependencyUseWireV5] = {}
        slots: set[str] = set()
        for dependency in item.dependency_uses:
            if dependency.producer_key in dependency_by_producer:
                raise PlannerWireContractError(
                    "planner_dependency_use_duplicate",
                    paths=(f"subtasks[{item.node_key}].dependency_uses",),
                    invariant_ids=("planner_dependency_use_exactly_once",),
                )
            if dependency.input_slot in slots:
                raise PlannerWireContractError(
                    "planner_dependency_input_slot_duplicate",
                    paths=(f"subtasks[{item.node_key}].dependency_uses",),
                    invariant_ids=("planner_dependency_input_slot_unique",),
                )
            dependency_by_producer[dependency.producer_key] = dependency
            slots.add(dependency.input_slot)
        if set(dependency_by_producer) != set(item.depends_on):
            raise PlannerWireContractError(
                "planner_dependency_use_mismatch",
                paths=(
                    f"subtasks[{item.node_key}].depends_on",
                    f"subtasks[{item.node_key}].dependency_uses",
                ),
                invariant_ids=("planner_dependency_use_matches_authoritative_edge",),
            )

        dependency_inputs: list[dict[str, Any]] = []
        for producer_key in item.depends_on:
            dependency = dependency_by_producer[producer_key]
            producer_output = compiled_outputs[producer_key]
            dependency_inputs.append(
                {
                    "protocol": "sgar-dependency-input-contract-v1",
                    "producer_id": canonical_ids[producer_key],
                    "input_slot": dependency.input_slot,
                    "accepted_artifact_types": [producer_output["artifact_type"]],
                    "accepted_extensions": [producer_output["output_extension"]],
                    "consumption_mode": dependency.consumption_mode,
                    "required_interface_contract_json": _project_interface_capabilities(
                        dependency.required_interface_capabilities
                    ),
                    "required": True,
                }
            )

        output_contract = dict(compiled_outputs[item.node_key])
        output_contract["downstream_consumers"] = [
            canonical_ids[key] for key in sorted(consumers[item.node_key])
        ]
        is_terminal = not consumers[item.node_key]
        projected_requirements: list[dict[str, Any]] = []
        for requirement in item.semantic_requirements:
            projected_evidence: list[str] = []
            for evidence_id in requirement.evidence_source_ids:
                if evidence_id.startswith("subtask_output:"):
                    producer_key = evidence_id.split(":", 1)[1]
                    if producer_key not in item.depends_on:
                        raise PlannerWireContractError(
                            "planner_semantic_dependency_evidence_invalid",
                            paths=(
                                f"subtasks[{item.node_key}].semantic_requirements"
                                f"[{requirement.requirement_id}].evidence_source_ids",
                            ),
                            invariant_ids=(
                                "planner_semantic_dependency_evidence_is_authoritative_edge",
                            ),
                        )
                    projected_evidence.append(
                        f"subtask_output:{canonical_ids[producer_key]}"
                    )
                else:
                    projected_evidence.append(evidence_id)
            projected_requirements.append(
                requirement.model_copy(
                    update={"evidence_source_ids": tuple(projected_evidence)}
                ).model_dump(mode="json")
            )
        subtasks.append(
            {
                "id": canonical_ids[item.node_key],
                "role": item.role,
                "description": item.description,
                "expected_output": item.expected_output,
                "depends_on": [canonical_ids[key] for key in item.depends_on],
                "dependency_inputs": dependency_inputs,
                "artifact_type": output_contract["artifact_type"],
                "output_extension": output_contract["output_extension"],
                "output_contract": output_contract,
                "task_stage": (
                    TaskStage.SYNTHESIZE_FINAL
                    if is_terminal
                    else TaskStage.PRODUCE_ARTIFACT
                ),
                "planning_execution_mode": _derive_execution_mode(
                    item.semantic_requirements
                ),
                "capability_evidence": list(item.capability_evidence),
                "capability_gap": item.capability_gap,
                "semantic_requirements": projected_requirements,
            }
        )
    try:
        return PlannerOutput.model_validate({"subtasks": subtasks})
    except Exception as exc:
        raise PlannerWireContractError(
            "planner_wire_v5_projection_invalid",
            paths=_pydantic_validation_paths(exc),
            invariant_ids=("planner_wire_v5_internal_projection",),
        ) from exc


def _topological_v6_nodes(
    wire: PlannerOutputWireV6,
) -> tuple[
    list[PlannerNodeWireV6],
    dict[str, str],
    dict[str, list[str]],
    dict[str, tuple[PlannerInputReferenceWireV6, ...]],
]:
    by_key: dict[str, PlannerNodeWireV6] = {}
    dependency_inputs: dict[str, tuple[PlannerInputReferenceWireV6, ...]] = {}
    for item in wire.nodes:
        if item.node_key in by_key:
            raise PlannerWireContractError(
                "planner_v6_node_key_duplicate",
                paths=(f"nodes[{item.node_key}].node_key",),
                invariant_ids=("planner_v6_node_key_unique",),
            )
        by_key[item.node_key] = item
        reference_keys = tuple((value.source, value.ref) for value in item.inputs)
        if len(reference_keys) != len(set(reference_keys)):
            raise PlannerWireContractError(
                "planner_v6_input_reference_duplicate",
                paths=(f"nodes[{item.node_key}].inputs",),
                invariant_ids=("planner_v6_input_reference_unique",),
            )
        dependency_inputs[item.node_key] = tuple(
            value for value in item.inputs if value.source == "node_output"
        )
    consumers: dict[str, list[str]] = {key: [] for key in by_key}
    indegree: dict[str, int] = {}
    for item in wire.nodes:
        dependencies = [value.ref for value in dependency_inputs[item.node_key]]
        unknown = sorted(set(dependencies) - set(by_key))
        if unknown:
            raise PlannerWireContractError(
                "planner_v6_node_output_reference_unknown",
                paths=(f"nodes[{item.node_key}].inputs",),
                invariant_ids=("planner_v6_node_output_reference_known",),
            )
        if item.node_key in dependencies:
            raise PlannerWireContractError(
                "planner_v6_self_dependency",
                paths=(f"nodes[{item.node_key}].inputs",),
                invariant_ids=("planner_v6_dependency_not_self",),
            )
        indegree[item.node_key] = len(dependencies)
        for producer in dependencies:
            consumers[producer].append(item.node_key)
    ready = sorted(key for key, count in indegree.items() if count == 0)
    ordered: list[PlannerNodeWireV6] = []
    while ready:
        key = ready.pop(0)
        ordered.append(by_key[key])
        for consumer in sorted(consumers[key]):
            indegree[consumer] -= 1
            if indegree[consumer] == 0:
                ready.append(consumer)
                ready.sort()
    if len(ordered) != len(wire.nodes):
        raise PlannerWireContractError(
            "planner_v6_dag_cycle",
            paths=("nodes.inputs",),
            invariant_ids=("planner_v6_dag_acyclic",),
        )
    canonical_ids = {
        item.node_key: f"task_{index:03d}"
        for index, item in enumerate(ordered, start=1)
    }
    return ordered, canonical_ids, consumers, dependency_inputs


def _validate_v6_terminal_shape(
    ordered: Sequence[PlannerNodeWireV6],
    consumers: Mapping[str, Sequence[str]],
) -> str:
    final_nodes = [
        item.node_key
        for item in ordered
        if item.output.contract_scope == "final_deliverable"
    ]
    if len(final_nodes) != 1:
        raise PlannerWireContractError(
            "planner_v6_final_deliverable_cardinality",
            paths=("nodes.output.contract_scope",),
            invariant_ids=("planner_v6_exactly_one_final_deliverable",),
        )
    final_key = final_nodes[0]
    if consumers[final_key]:
        raise PlannerWireContractError(
            "planner_v6_final_deliverable_is_not_terminal",
            paths=(f"nodes[{final_key}].output.contract_scope",),
            invariant_ids=("planner_v6_final_deliverable_terminal",),
        )
    orphaned = [
        item.node_key
        for item in ordered
        if item.node_key != final_key and not consumers[item.node_key]
    ]
    if orphaned:
        raise PlannerWireContractError(
            "planner_v6_intermediate_not_consumed",
            paths=tuple(f"nodes[{key}].output" for key in orphaned),
            invariant_ids=("planner_v6_all_intermediates_consumed",),
        )
    return final_key


_PLANNER_ACCEPTANCE_WIRE_FIELDS = frozenset({
    "protocol", "node_key", "role_intent", "input_requirement",
    "execution_requirements", "acceptance_criteria", "contract_scope",
    "delivery_mode", "json_schema_json", "grounding_requirements",
})
_PLANNER_ACCEPTANCE_FIELD_FRAGMENT = re.compile(
    r"^\s*['\"]?(?:protocol|node_key|role_intent|input_requirement|"
    r"execution_requirements|acceptance_criteria|contract_scope|delivery_mode|"
    r"json_schema_json|grounding_requirements)\s*['\"]\s*:"
)


def _reject_planner_wire_fragments_in_acceptance(wire: PlannerOutputWireV6) -> None:
    """Fail closed when model response fields leak into task acceptance text."""
    for node_index, node in enumerate(wire.nodes):
        for criterion_index, criterion in enumerate(node.acceptance_criteria):
            text = criterion.strip()
            if (
                not text
                or text in _PLANNER_ACCEPTANCE_WIRE_FIELDS
                or _PLANNER_ACCEPTANCE_FIELD_FRAGMENT.match(text)
                or re.search(r"[.!?]\]\s*,\s*$", text)
            ):
                raise PlannerWireContractError(
                    "planner_acceptance_wire_fragment",
                    paths=(f"nodes[{node_index}].acceptance_criteria[{criterion_index}]",),
                    invariant_ids=("planner_acceptance_wire_integrity",),
                )


def project_planner_wire_payload(
    value: Mapping[str, Any],
    *,
    allowed_public_input_refs: Sequence[str] | None = None,
    allowed_completed_output_refs: Sequence[str] | None = None,
    expected_final_deliverable: Mapping[str, Any] | None = None,
    allowed_source_clause_ids: Sequence[str] | None = None,
    require_json_schemas: bool = True,
) -> PlannerOutput:
    """Validate and deterministically project one live Planner V6 response."""

    from .planner_contracts import _known_extension_artifact

    try:
        normalized_value, _actions = normalize_planner_wire_ingress(value)
        wire = PlannerOutputWireV6.model_validate(normalized_value)
    except PlannerWireContractError:
        raise
    except Exception as exc:
        error = PlannerWireContractError(
            "planner_wire_v6_payload_invalid",
            paths=_pydantic_validation_paths(exc),
            invariant_ids=("planner_wire_v6_outer_schema",),
        )
        # Keep field/type and known constraint diagnostics; input/error context
        # can contain private task values and are not correction instructions.
        details = []
        if callable(getattr(exc, "errors", None)):
            for item in exc.errors(include_input=False, include_context=False, include_url=False):
                diagnostic = {"path": list(item.get("loc", ())),
                              "type": str(item.get("type", "validation_error"))}
                constraint = str(item.get("msg", "")).removeprefix("Value error, ")
                if constraint in _WIRE_CONSTRAINT_IDS:
                    diagnostic["constraint_id"] = constraint
                details.append(diagnostic)
        error.invariant_ids = tuple(dict.fromkeys((
            *error.invariant_ids,
            *(item["constraint_id"] for item in details if "constraint_id" in item),
        )))
        error.structural_details = {"validation_errors": details,
                                    "exception_type": type(exc).__name__}
        raise error from exc
    _reject_planner_wire_fragments_in_acceptance(wire)
    if len(wire.nodes) > int(PLANNER_WIRE_COMPLEXITY_POLICY["max_subtasks"]):
        raise PlannerWireContractError(
            "planner_complexity_policy_exceeded",
            paths=("nodes",),
            invariant_ids=("planner_complexity_policy_v1",),
        )
    ordered, canonical_ids, consumers, dependencies = _topological_v6_nodes(wire)
    final_key = _validate_v6_terminal_shape(ordered, consumers)
    explicit_final_members: tuple[str, ...] = ()
    explicit_final_runtime_path: str | None = None
    if expected_final_deliverable is not None:
        expected = dict(expected_final_deliverable)
        explicit_final_members = tuple(
            str(item).strip()
            for item in (expected.get("required_members") or ())
            if str(item).strip()
        )
        if str(expected.get("contract_authority") or "request_only") == "explicit":
            explicit_final_runtime_path = expected.get("runtime_path")
            actual_final = next(item for item in ordered if item.node_key == final_key)
            expected_name = str(expected.get("logical_name") or "").strip()
            expected_type = str(expected.get("artifact_type") or "").strip().lower()
            if actual_final.output.logical_name != expected_name:
                raise PlannerWireContractError(
                    "planner_v6_final_logical_name_mismatch",
                    paths=(f"nodes[{final_key}].output.logical_name",),
                    invariant_ids=("planner_v6_final_deliverable_matches_input",),
                )
            if actual_final.output.artifact_type != expected_type:
                raise PlannerWireContractError(
                    "planner_v6_final_artifact_type_mismatch",
                    paths=(f"nodes[{final_key}].output.artifact_type",),
                    invariant_ids=("planner_v6_final_deliverable_matches_input",),
                )
            expected_representation = str(expected.get("representation") or "").strip()
            if expected_representation:
                expected_mode = "value" if expected_representation == "inline_text" else "file"
                if actual_final.output.delivery_mode != expected_mode:
                    raise PlannerWireContractError(
                        "planner_v7_final_delivery_mode_mismatch",
                        paths=(f"nodes[{final_key}].output.delivery_mode",),
                        invariant_ids=("planner_v7_delivery_mode_matches_input",),
                    )
            expected_text_format = expected.get("text_format")
            if expected_text_format is not None:
                typed_text_format = TextFormatContract.model_validate(
                    expected_text_format
                )
                if actual_final.output.text_format != typed_text_format:
                    raise PlannerWireContractError(
                        "planner_v7_final_text_format_mismatch",
                        paths=(f"nodes[{final_key}].output.text_format",),
                        invariant_ids=(
                            "planner_v6_final_deliverable_matches_input",
                        ),
                    )
    allowed_public = (
        set(str(value) for value in allowed_public_input_refs)
        if allowed_public_input_refs is not None
        else None
    )
    allowed_completed = (
        set(str(value) for value in allowed_completed_output_refs)
        if allowed_completed_output_refs is not None
        else None
    )
    allowed_clauses = (
        set(str(value) for value in allowed_source_clause_ids)
        if allowed_source_clause_ids is not None
        else None
    )
    for item in ordered:
        if item.output.contract_scope == "intermediate" and item.output.delivery_mode != "file":
            raise PlannerWireContractError(
                "planner_v7_intermediate_requires_artifact",
                paths=(f"nodes[{item.node_key}].output.delivery_mode",),
                invariant_ids=("planner_v7_intermediate_artifact_handle",),
            )
        requirement_ids = [value.requirement_id for value in item.execution_requirements]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise PlannerWireContractError(
                "planner_v7_execution_requirement_id_duplicate",
                paths=(f"nodes[{item.node_key}].execution_requirements",),
                invariant_ids=("planner_execution_requirement_id_unique",),
            )
        if allowed_clauses is not None:
            for requirement in item.execution_requirements:
                if set(requirement.source_clause_ids) - allowed_clauses:
                    raise PlannerWireContractError(
                        "planner_v7_execution_requirement_clause_unknown",
                        paths=(f"nodes[{item.node_key}].execution_requirements",),
                        invariant_ids=("planner_execution_requirement_evidence_bound",),
                    )
        for reference in item.inputs:
            if (
                reference.source == "public_input"
                and allowed_public is not None
                and reference.ref not in allowed_public
            ):
                raise PlannerWireContractError(
                    "planner_v6_public_input_reference_unknown",
                    paths=(f"nodes[{item.node_key}].inputs",),
                    invariant_ids=("planner_v6_public_input_reference_authorized",),
                )
            if (
                reference.source == "completed_output"
                and allowed_completed is not None
                and reference.ref not in allowed_completed
            ):
                raise PlannerWireContractError(
                    "planner_v6_completed_output_reference_unknown",
                    paths=(f"nodes[{item.node_key}].inputs",),
                    invariant_ids=("planner_v6_completed_output_reference_authorized",),
                )

    outputs = {item.node_key: item.output for item in ordered}
    semantic_edges: list[SemanticEdgeContractV2] = []
    incoming_semantic: dict[str, list[SemanticEdgeContractV2]] = defaultdict(list)
    for consumer in ordered:
        for reference in dependencies[consumer.node_key]:
            producer_output = outputs[reference.ref]
            edge = SemanticEdgeContractV2(
                producer_id=canonical_ids[reference.ref],
                consumer_id=canonical_ids[consumer.node_key],
                producer_output_ref=reference.ref,
                purpose=reference.purpose,
                artifact_type=producer_output.artifact_type,
                content_kind=producer_output.content_kind,
            )
            semantic_edges.append(edge)
            incoming_semantic[consumer.node_key].append(edge)
    semantic_edges.sort(key=lambda edge: (edge.producer_id, edge.consumer_id, edge.edge_sha256))

    subtasks: list[dict[str, Any]] = []
    for item in ordered:
        task_id = canonical_ids[item.node_key]
        output_extension = _wire_output_extension(item.output)
        grounding_requirements = _generic_grounding_requirements(item)
        node_inputs = tuple(
            SemanticInputReferenceV2(
                source=reference.source,
                ref=(
                    canonical_ids[reference.ref]
                    if reference.source == "node_output"
                    else reference.ref
                ),
                purpose=reference.purpose,
            )
            for reference in item.inputs
        )
        semantic_contract = NodeSemanticContractV2(
            task_id=task_id,
            role_intent=item.role_intent,
            task=item.task,
            input_requirement=item.input_requirement,
            required_effect=item.required_effect,
            authorized_inputs=node_inputs,
            output=SemanticOutputDescriptorV2(
                logical_name=item.output.logical_name,
                artifact_type=item.output.artifact_type,
                contract_scope=item.output.contract_scope,
                semantic_description=item.output.semantic_description,
                content_kind=item.output.content_kind,
                syntax_validator=item.output.syntax_validator,
            ),
            acceptance_conditions=tuple(item.acceptance_criteria),
        )
        json_schema = None
        if item.output.artifact_type == "json":
            if item.output.json_schema_json is None:
                if require_json_schemas:
                    raise PlannerWireContractError(
                        "planner_v6_json_schema_missing",
                        paths=(f"nodes[{item.node_key}].output.json_schema_json",),
                        invariant_ids=("planner_v6_json_output_schema_present",),
                    )
            elif not isinstance(item.output.json_schema_json, str):
                raise PlannerWireContractError(
                    "planner_v6_json_schema_invalid",
                    paths=(f"nodes[{item.node_key}].output.json_schema_json",),
                    invariant_ids=("planner_v6_json_output_schema_enforceable",),
                )
            else:
                try:
                    parsed_schema = json.loads(item.output.json_schema_json)
                    from .model_response_contracts import require_semantic_json_schema

                    json_schema = require_semantic_json_schema(parsed_schema)
                except PlannerWireContractError:
                    raise
                except Exception as exc:
                    raise PlannerWireContractError(
                        "planner_v6_json_schema_invalid",
                        paths=(f"nodes[{item.node_key}].output.json_schema_json",),
                        invariant_ids=("planner_v6_json_output_schema_enforceable",),
                    ) from exc
        dependency_inputs = []
        for index, reference in enumerate(dependencies[item.node_key], start=1):
            producer_output = outputs[reference.ref]
            producer_extension = _wire_output_extension(producer_output)
            dependency_inputs.append(
                {
                    "protocol": "sgar-dependency-input-contract-v1",
                    "producer_id": canonical_ids[reference.ref],
                    "input_slot": f"semantic_input_{index:03d}",
                    "accepted_artifact_types": [producer_output.artifact_type],
                    "accepted_extensions": (
                        [producer_extension] if producer_extension else []
                    ),
                    "consumption_mode": "artifact_handle",
                    "required_interface_contract_json": "{}",
                    "required": True,
                }
            )
        subtasks.append(
            {
                "id": task_id,
                "role": item.role_intent,
                "description": item.task,
                "expected_output": item.output.semantic_description,
                "depends_on": [canonical_ids[value.ref] for value in dependencies[item.node_key]],
                "dependency_inputs": dependency_inputs,
                "artifact_type": item.output.artifact_type,
                "output_extension": output_extension,
                "output_contract": {
                    "content_kind": item.output.content_kind,
                    "syntax_validator": item.output.syntax_validator,
                    "acceptance_probes": [probe.model_dump(mode="json") for probe in item.output.acceptance_probes],
                    "artifact_type": item.output.artifact_type,
                    "output_extension": output_extension,
                    "required_content": [item.output.semantic_description],
                    "produced_files": (
                        _explicit_member_produced_files(explicit_final_members)
                        if item.node_key == final_key and explicit_final_members
                        else [{
                            "path_hint": member,
                            "artifact_type": (
                                _known_extension_artifact(Path(member).suffix.lower()) or "file"
                            ),
                            "required": True,
                            "schema_hint": None,
                        } for member in item.output.required_members]
                        if item.output.required_members
                        else [{
                            "path_hint": (
                                explicit_final_runtime_path
                                if item.node_key == final_key and explicit_final_runtime_path
                                else item.output.logical_name
                            ),
                            "artifact_type": item.output.artifact_type,
                            "required": True,
                            "schema_hint": None,
                        }] if item.output.delivery_mode == "file" else []
                    ),
                    "json_schema": json_schema,
                    "interface_contract": (
                        {"text_format": item.output.text_format.model_dump(mode="json")}
                        if item.output.text_format is not None else {}
                    ),
                    "grounding_requirements": grounding_requirements,
                    **({"evidence_source_scope": item.output.evidence_source_scope}
                       if item.output.evidence_source_scope is not None else {}),
                    **({"external_acquisition_mode": item.output.external_acquisition_mode}
                       if item.output.external_acquisition_mode is not None else {}),
                    **({"external_discovery_mode": item.output.external_discovery_mode}
                       if item.output.external_discovery_mode is not None else {}),
                    "acceptance_criteria": list(item.acceptance_criteria),
                    "downstream_consumers": [
                        canonical_ids[value] for value in sorted(consumers[item.node_key])
                    ],
                },
                "task_stage": (
                    TaskStage.SYNTHESIZE_FINAL
                    if item.node_key == final_key
                    else TaskStage.PRODUCE_ARTIFACT
                ),
                "planning_execution_mode": None,
                "capability_evidence": [],
                "capability_gap": None,
                "semantic_requirements": [],
                "execution_requirements": [
                    value.model_dump(mode="json")
                    for value in item.execution_requirements
                ],
                "semantic_contract_v2": semantic_contract.model_dump(mode="json"),
                "incoming_semantic_edges_v2": [
                    edge.model_dump(mode="json")
                    for edge in incoming_semantic[item.node_key]
                ],
            }
        )
    try:
        projected = PlannerOutput.model_validate(
            {
                "subtasks": subtasks,
                "semantic_edge_contracts_v2": [
                    edge.model_dump(mode="json") for edge in semantic_edges
                ],
            }
        )
        return _align_derived_v7_dependency_extensions(projected)
    except Exception as exc:
        raise PlannerWireContractError(
            "planner_wire_v6_projection_invalid",
            paths=_pydantic_validation_paths(exc),
            invariant_ids=("planner_wire_v6_internal_projection",),
        ) from exc


def planner_output_to_wire(output: PlannerOutput) -> PlannerOutputWireV2:
    """Create a historical v3 wire value for explicit read-only audits only."""

    subtasks: list[dict[str, Any]] = []
    for item in output.subtasks:
        projected = item.model_dump(
            mode="json",
            exclude={"output_contract", "incoming_edge_contracts"},
        )
        if item.output_contract is None:
            projected["output_contract"] = None
        else:
            output_contract = item.output_contract.model_dump(mode="json")
            interface_contract = output_contract.pop("interface_contract", {})
            json_schema = output_contract.pop("json_schema", None)
            produced_files = output_contract.pop("produced_files", [])
            output_contract["produced_files"] = [
                {
                    "path_hint": produced.get("path_hint"),
                    "artifact_type": produced.get("artifact_type", "plaintext"),
                    "required": produced.get("required", True),
                    "schema_hint_json": (
                        json.dumps(
                            produced.get("schema_hint"),
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                            allow_nan=False,
                        )
                        if produced.get("schema_hint") is not None
                        else None
                    ),
                }
                for produced in produced_files
            ]
            output_contract["json_schema_json"] = (
                json.dumps(
                    json_schema,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                )
                if json_schema is not None
                else None
            )
            output_contract["interface_contract_json"] = json.dumps(
                interface_contract,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            projected["output_contract"] = output_contract
        subtasks.append(projected)
    try:
        return PlannerOutputWireV2.model_validate({"subtasks": subtasks})
    except Exception as exc:
        raise PlannerWireContractError("planner_output_wire_projection_invalid") from exc


def planner_wire_projection_audit(
    *,
    wire_payload: Mapping[str, Any],
    output: PlannerOutput,
) -> dict[str, Any]:
    """Return content-free parity evidence for the wire/public boundary."""

    try:
        validated_wire = PlannerOutputWireV6.model_validate(wire_payload)
        reprojected = project_planner_wire_payload(
            validated_wire.model_dump(mode="python"),
            require_json_schemas=False,
        )
    except Exception as exc:
        raise PlannerWireContractError("planner_wire_v6_audit_invalid") from exc
    projection = {
        "protocol": PLANNER_WIRE_PROTOCOL,
        "projector_version": PLANNER_WIRE_PROJECTOR_VERSION,
        "complexity_policy_sha256": PLANNER_WIRE_COMPLEXITY_POLICY_SHA256,
        "wire_payload_sha256": canonical_sha256(dict(wire_payload)),
        "public_output_sha256": canonical_sha256(output.model_dump(mode="json")),
        "round_trip_wire_sha256": canonical_sha256(
            validated_wire.model_dump(mode="json")
        ),
        "semantic_round_trip": reprojected.model_dump(mode="json")
        == output.model_dump(mode="json"),
    }
    projection["audit_sha256"] = canonical_sha256(projection)
    return projection


def planner_probe_wire_payload_v4_replay() -> dict[str, Any]:
    """Return the frozen typed v4 probe only for read-only replay tests."""

    capability: dict[str, Any] = {
        "capability_id": "artifact.records.v1",
        "kind": "data_interface",
        "name": "records",
        "version": "1",
        "properties": [
            {
                "property_name": "encoding",
                "value_type": "string",
                "string_value": "utf-8",
                "integer_value": None,
                "number_value": None,
                "boolean_value": None,
                "string_list_value": [],
            }
        ],
    }
    payload: dict[str, Any] = {
        "protocol": LEGACY_TYPED_PLANNER_WIRE_PROTOCOL,
        "subtasks": [
            {
                "id": "probe_source",
                "role": "Synthetic Producer",
                "description": "Produce public synthetic nested records.",
                "expected_output": "A typed synthetic JSON artifact.",
                "depends_on": [],
                "dependency_inputs": [],
                "artifact_type": "json",
                "output_extension": ".json",
                "output_contract": {
                    "contract_status": "expressible",
                    "unexpressible_requirements": [],
                    "artifact_type": "json",
                    "output_extension": ".json",
                    "required_content": ["records"],
                    "schemas": [
                        {
                            "schema_id": "records_schema",
                            "root_node_id": "root",
                            "nodes": [
                                {"node_id": "root", "kind": "object"},
                                {"node_id": "records", "kind": "array"},
                                {"node_id": "record", "kind": "object"},
                                {"node_id": "label", "kind": "string", "min_length": 1},
                            ],
                            "object_fields": [
                                {
                                    "object_node_id": "root",
                                    "field_name": "records",
                                    "value_node_id": "records",
                                    "required": True,
                                },
                                {
                                    "object_node_id": "record",
                                    "field_name": "label",
                                    "value_node_id": "label",
                                    "required": True,
                                },
                            ],
                            "array_items": [
                                {
                                    "array_node_id": "records",
                                    "value_node_id": "record",
                                }
                            ],
                            "map_values": [],
                            "combinator_branches": [],
                        }
                    ],
                    "primary_schema_id": "records_schema",
                    "produced_files": [
                        {
                            "path_hint": "synthetic_records.json",
                            "artifact_type": "json",
                            "required": True,
                            "schema_id": "records_schema",
                            "csv_columns": [],
                        }
                    ],
                    "interface_capabilities": [capability],
                    "grounding_requirements": ["public synthetic probe input"],
                    "acceptance_criteria": ["nested records validate"],
                    "downstream_consumers": ["probe_consumer"],
                },
                "task_stage": "produce_artifact",
                "planning_execution_mode": "generative",
                "capability_evidence": [],
                "capability_gap": None,
                "semantic_requirements": [
                    {
                        "protocol": "sgar-semantic-requirement-v1",
                        "requirement_id": "probe_records",
                        "source_clause_ids": ["probe:producer:1"],
                        "status": "expressible",
                        "work_nature": "generative",
                        "material_coverage": "authorized_subset",
                        "verification": "required",
                        "side_effect_policy": "none",
                        "input_semantics": ["public synthetic probe input"],
                        "output_semantics": ["nested records json"],
                        "acceptance_conditions": ["nested records validate"],
                        "evidence_source_ids": [],
                        "unexpressible_reason": None,
                    }
                ],
            },
            {
                "id": "probe_consumer",
                "role": "Synthetic Consumer",
                "description": "Consume the public synthetic nested records.",
                "expected_output": "A grounded synthetic summary.",
                "depends_on": ["probe_source"],
                "dependency_inputs": [
                    {
                        "protocol": "sgar-dependency-input-contract-v1",
                        "producer_id": "probe_source",
                        "input_slot": "records_input",
                        "accepted_artifact_types": ["json"],
                        "accepted_extensions": [".json"],
                        "consumption_mode": "context_content",
                        "required_interface_capabilities": [capability],
                        "required": True,
                    }
                ],
                "artifact_type": "markdown",
                "output_extension": ".md",
                "output_contract": {
                    "contract_status": "expressible",
                    "unexpressible_requirements": [],
                    "artifact_type": "markdown",
                    "output_extension": ".md",
                    "required_content": ["synthetic summary"],
                    "schemas": [],
                    "primary_schema_id": None,
                    "produced_files": [
                        {
                            "path_hint": "synthetic_summary.md",
                            "artifact_type": "markdown",
                            "required": True,
                            "schema_id": None,
                            "csv_columns": [],
                        }
                    ],
                    "interface_capabilities": [],
                    "grounding_requirements": ["probe_source"],
                    "acceptance_criteria": ["uses the synthetic records"],
                    "downstream_consumers": [],
                },
                "task_stage": "synthesize_final",
                "planning_execution_mode": "generative",
                "capability_evidence": [],
                "capability_gap": None,
                "semantic_requirements": [
                    {
                        "protocol": "sgar-semantic-requirement-v1",
                        "requirement_id": "probe_summary",
                        "source_clause_ids": ["probe:consumer:1"],
                        "status": "expressible",
                        "work_nature": "generative",
                        "material_coverage": "complete",
                        "verification": "required",
                        "side_effect_policy": "none",
                        "input_semantics": ["nested records json"],
                        "output_semantics": ["grounded synthetic summary"],
                        "acceptance_conditions": ["uses the synthetic records"],
                        "evidence_source_ids": ["probe_source"],
                        "unexpressible_reason": None,
                    }
                ],
            },
        ],
    }
    wire = PlannerOutputWireV4.model_validate(payload)
    output = project_legacy_planner_wire_payload_v4(
        wire.model_dump(mode="python")
    )
    from .planner_contracts import project_planner_contract

    project_planner_contract(output)
    return wire.model_dump(mode="json")


def planner_probe_wire_payload() -> dict[str, Any]:
    """Return a non-vacuous synthetic live V6 payload for exact probes."""

    payload: dict[str, Any] = {
        "protocol": PLANNER_WIRE_PROTOCOL,
        "nodes": [
            {
                "node_key": "example_extract",
                "role_intent": "structured data analyst",
                "task": "Create a synthetic illustrative record from the task text; do not claim it is observed data.",
                "input_requirement": "task_text_only",
                "inputs": [],
                "output": {
                    "logical_name": "example_records.json",
                    "artifact_type": "json",
                    "contract_scope": "intermediate",
                    "delivery_mode": "file",
                    "semantic_description": "Structured synthetic records.",
                    "json_schema_json": json.dumps(
                        {
                            "type": "object",
                            "properties": {
                                "records": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "summary": {"type": "string"}
                                        },
                                        "required": ["summary"],
                                        "additionalProperties": False,
                                    },
                                }
                            },
                            "required": ["records"],
                            "additionalProperties": False,
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                },
                "acceptance_criteria": ["Every declared synthetic record is represented."],
            },
            {
                "node_key": "example_report",
                "role_intent": "evidence-grounded report author",
                "task": "Synthesize a concise report from the structured synthetic records.",
                "input_requirement": "requires_material",
                "inputs": [
                    {
                        "source": "node_output",
                        "ref": "example_extract",
                        "purpose": "Use the complete structured records as report evidence.",
                    }
                ],
                "output": {
                    "logical_name": "example_report.md",
                    "artifact_type": "markdown",
                    "contract_scope": "final_deliverable",
                    "delivery_mode": "file",
                    "semantic_description": "A concise evidence-grounded synthetic report.",
                },
                "acceptance_criteria": ["Every claim is grounded in the supplied records."],
            },
        ],
    }
    wire = PlannerOutputWireV6.model_validate(payload)
    output = project_planner_wire_payload(
        wire.model_dump(mode="python"),
    )
    from .planner_contracts import project_planner_contract_v2

    project_planner_contract_v2(output)
    return wire.model_dump(mode="json")


__all__ = [
    "LEGACY_LIVE_PLANNER_WIRE_PROJECTOR_VERSION",
    "LEGACY_LIVE_PLANNER_WIRE_PROTOCOL",
    "LEGACY_PLANNER_WIRE_PROJECTOR_VERSION",
    "LEGACY_PLANNER_WIRE_PROTOCOL",
    "LEGACY_TYPED_PLANNER_WIRE_PROJECTOR_VERSION",
    "LEGACY_TYPED_PLANNER_WIRE_PROTOCOL",
    "PLANNER_WIRE_PROJECTOR_VERSION",
    "PLANNER_WIRE_PROTOCOL",
    "PLANNER_WIRE_COMPLEXITY_POLICY",
    "PLANNER_WIRE_COMPLEXITY_POLICY_SHA256",
    "PlannerOutputContractWireV1",
    "PlannerOutputWireV1",
    "PlannerDependencyInputWireV1",
    "PlannerSubtaskWireV2",
    "PlannerOutputContractWireV5",
    "PlannerDependencyUseWireV5",
    "PlannerSubtaskWireV5",
    "PlannerOutputWireV5",
    "PlannerInputReferenceWireV6",
    "PlannerNodeOutputWireV6",
    "PlannerNodeWireV6",
    "PlannerOutputWireV6",
    "PlannerOutputWireV2",
    "PlannerOutputWireV4",
    "PlannerOutputContractWireV4",
    "PlannerSchemaGraphWireV1",
    "PlannerSchemaNodeWireV1",
    "PlannerInterfaceCapabilityWireV1",
    "PlannerProducedFileWireV1",
    "PlannerSubtaskWireV1",
    "PlannerWireContractError",
    "compile_planner_schema_graph",
    "normalize_planner_wire_ingress",
    "planner_output_to_wire",
    "planner_probe_wire_payload",
    "planner_wire_projection_audit",
    "project_legacy_planner_wire_payload_v3",
    "project_legacy_planner_wire_payload_v4",
    "project_planner_wire_payload",
    "project_planner_wire_v5_replay",
    "planner_probe_wire_payload_v4_replay",
]
