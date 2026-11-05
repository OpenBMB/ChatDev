"""Structural validation and deterministic lowering for executable Plans."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any, Iterable, Literal, Mapping, Sequence, cast

from pydantic import Field, field_validator, model_validator

from .execution_requirements import ExecutionNetworkDeclaration, requires_execution_network
from .binding_protocol import (
    BindingProtocolError,
    artifact_handle_matches_input_contract,
    normalize_contract_kind,
    parse_binding_source,
    selected_value_schema,
    selected_schema_types,
)
from .compiler_invariants import invariant_id_for_failure_code
from .executable_plan import (
    PLAN_LOWERING_PROTOCOL,
    PLAN_VALIDATION_PROTOCOL,
    CompilerPlanDraft,
    CompilerInvariantCatalog,
    ExecutablePlan,
    ExecutablePlanStep,
    ModelCostEvidence,
    PlanCompilerInputEnvelope,
    PlanObjectiveEvidence,
    PlanRevisionRef,
    ResourceApplicationV1,
    ResourceUsageRecord,
    StepOutputRef,
    StepOutputContract,
    build_compiler_invariant_catalog,
    resolve_final_step_eligibility,
    workspace_effect_mutator_eligible,
    workspace_file_delivery_required,
    _ensure_host_free,
    _selected_schema_identity_valid,
)
from .model_response_contracts import (
    ModelResponseContractError,
    OutputFormatRequirement,
    classify_output_schema_phase,
    require_semantic_json_schema,
)
from .output_realization import (
    OutputRealizationContractV1,
    OutputReachabilityProof,
    prove_output_reachability,
)
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
from .formal_contracts import ExecutableEdgeContractV2
from .pipeline_control import FrozenContract, canonical_sha256
from .resource_runtime import ResourceDefinition, runtime_adapter_supported
from .schema import OperationKind


class PlanValidationError(ValueError):
    def __init__(
        self,
        code: str,
        *,
        failure_layer: Literal["protocol", "selection", "connection", "executability"],
        path: tuple[str | int, ...] = (),
        invariant_id: str | None = None,
        output_reachability: dict[str, Any] | None = None,
        step_id: str | None = None,
        input_binding: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.failure_layer = failure_layer
        self.responsibility = "research"
        self.path = path
        self.invariant_id = invariant_id or invariant_id_for_failure_code(code)
        self.output_reachability = output_reachability
        self.step_id = step_id
        self.input_binding = input_binding


class PlanFrameworkValidationError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code
        self.failure_layer = "framework"
        self.responsibility = "framework"


class PlanValidationAudit(FrozenContract):
    protocol: Literal[PLAN_VALIDATION_PROTOCOL] = PLAN_VALIDATION_PROTOCOL
    status: Literal["passed"] = "passed"
    candidate_pool_sha256: str
    compiler_input_sha256: str
    draft_sha256: str
    validated_plan_sha256: str
    checks: tuple[str, ...]
    audit_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "PlanValidationAudit":
        projected = self.model_dump(mode="python", exclude={"audit_sha256"})
        expected = canonical_sha256(projected)
        if self.audit_sha256 and self.audit_sha256 != expected:
            raise ValueError("plan_validation_audit_sha256_mismatch")
        object.__setattr__(self, "audit_sha256", expected)
        return self


class ResourceExecutionContextTemplate(FrozenContract):
    """Host-free execution identity completed with scope data at dispatch."""

    protocol: Literal[PLAN_LOWERING_PROTOCOL] = PLAN_LOWERING_PROTOCOL
    run_id: str = Field(min_length=1)
    plan_revision: PlanRevisionRef
    candidate_pool_sha256: str
    candidate_resource_ids: tuple[str, ...]
    selected_resource_ids: tuple[str, ...]
    plan_sha256: str
    step_id: str = Field(min_length=1)
    attempt: int = Field(default=1, ge=1)
    parent_operation_id: str | None = None

    @field_validator("candidate_pool_sha256", "plan_sha256")
    @classmethod
    def _hashes(cls, value: str) -> str:
        normalized = str(value).strip().lower()
        if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
            raise ValueError("execution_context_template_hash_invalid")
        return normalized

    @model_validator(mode="after")
    def _authorization(self) -> "ResourceExecutionContextTemplate":
        if not set(self.selected_resource_ids).issubset(self.candidate_resource_ids):
            raise ValueError("lowered_selected_resources_not_in_candidate_pool")
        _ensure_host_free(
            self.model_dump(mode="python"),
            field_name="resource_execution_context_template",
        )
        return self


class ResourceCallRequestTemplate(ExecutionNetworkDeclaration):
    """One deterministic, side-effect-free ResourceRuntime dispatch template."""

    protocol: Literal[PLAN_LOWERING_PROTOCOL] = PLAN_LOWERING_PROTOCOL
    step_id: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    capability_operation_id: str = Field(min_length=1)
    satisfied_obligation_ids: tuple[str, ...] = ()
    resource_type: str = Field(min_length=1)
    resource_manifest_sha256: str
    entrypoint_id: str | None = None
    entrypoint_dispatch_sha256: str | None = None
    unresolved_typed_bindings: dict[str, Any] = Field(default_factory=dict)
    # Canonical provenance identities retained for sealed-plan validation.
    consumed_context_source_ids: tuple[str, ...] = ()
    # Framework-private handles resolved from the canonical identities.  This
    # field is absent in historical templates, whose consumed IDs were already
    # runtime-resolvable.
    runtime_context_handle_ids: tuple[str, ...] = ()
    edge_contract_sha256s: tuple[str, ...] = ()
    dependency_step_ids: tuple[str, ...] = ()
    expected_output_contract: dict[str, Any]
    resource_application: ResourceApplicationV1 | None = None
    controller_session_spec: ControllerSessionSpec | None = None
    format_enforcement: dict[str, Any] | None = None
    advisory_profile_refs: tuple[str, ...] = ()
    agent_base_model_resource_id: str | None = None
    direct_argv_required: Literal[True] = True
    execution_context_template: ResourceExecutionContextTemplate
    template_sha256: str = ""

    @field_validator("resource_manifest_sha256", "entrypoint_dispatch_sha256")
    @classmethod
    def _optional_hashes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip().lower()
        if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
            raise ValueError("resource_call_template_hash_invalid")
        return normalized

    @model_validator(mode="after")
    def _seal(self) -> "ResourceCallRequestTemplate":
        if self.resource_type == "Tool":
            if not self.entrypoint_id or not self.entrypoint_dispatch_sha256:
                raise ValueError("tool_call_template_entrypoint_missing")
        elif self.entrypoint_id is not None or self.entrypoint_dispatch_sha256 is not None:
            raise ValueError("non_tool_call_template_has_entrypoint")
        if self.format_enforcement is not None:
            supplied = str(
                self.format_enforcement.get("format_contract_sha256") or ""
            )
            projection = dict(self.format_enforcement)
            projection.pop("format_contract_sha256", None)
            if supplied != canonical_sha256(projection):
                raise ValueError("format_enforcement_contract_sha256_mismatch")
        if self.resource_application is not None:
            application = self.resource_application
            if (
                application.resource_id != self.resource_id
                or application.resource_type != self.resource_type
                or application.capability_operation_id
                != self.capability_operation_id
                or application.resource_manifest_sha256
                != self.resource_manifest_sha256
                or application.input_bindings != self.unresolved_typed_bindings
                or application.target_step_output_contract.model_dump(mode="json")
                != self.expected_output_contract
            ):
                raise ValueError("resource_call_template_application_mismatch")
        if self.controller_session_spec is not None:
            spec = self.controller_session_spec
            expected_backing = (
                self.resource_id
                if self.resource_type == "Model"
                else self.agent_base_model_resource_id
            )
            if (
                self.resource_type not in {"Model", "Agent"}
                or spec.controller_step_id != self.step_id
                or spec.controller_resource_id != self.resource_id
                or spec.controller_resource_type != self.resource_type
                or spec.backing_model_resource_id != expected_backing
                or spec.declared_input_bindings != self.unresolved_typed_bindings
                or spec.expected_output_contract != self.expected_output_contract
            ):
                raise ValueError("resource_call_template_controller_session_mismatch")
        projected = self.model_dump(mode="python", exclude={"template_sha256"})
        _ensure_host_free(projected, field_name="resource_call_request_template")
        expected = canonical_sha256(projected)
        if self.template_sha256:
            stage_b_legacy_projection = dict(projected)
            stage_b_legacy_projection.pop("controller_session_spec", None)
            stage_b_legacy_expected = canonical_sha256(stage_b_legacy_projection)
            legacy_projection = dict(projected)
            legacy_projection.pop("format_enforcement", None)
            legacy_projection.pop("resource_application", None)
            legacy_projection.pop("controller_session_spec", None)
            legacy_expected = canonical_sha256(legacy_projection)
            if self.template_sha256 not in {
                expected,
                stage_b_legacy_expected,
                legacy_expected,
            }:
                raise ValueError("resource_call_template_sha256_mismatch")
            object.__setattr__(self, "template_sha256", self.template_sha256)
        else:
            object.__setattr__(self, "template_sha256", expected)
        return self


class PlanLoweringAudit(FrozenContract):
    protocol: Literal[PLAN_LOWERING_PROTOCOL] = PLAN_LOWERING_PROTOCOL
    status: Literal["passed"] = "passed"
    plan_sha256: str
    candidate_pool_sha256: str
    step_count: int = Field(ge=1)
    direct_argv: Literal[True] = True
    shell_commands: tuple[str, ...] = ()
    semantic_mutation: Literal[False] = False
    checks: tuple[str, ...]
    audit_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "PlanLoweringAudit":
        if self.shell_commands:
            raise ValueError("lowering_shell_command_forbidden")
        projected = self.model_dump(mode="python", exclude={"audit_sha256"})
        expected = canonical_sha256(projected)
        if self.audit_sha256 and self.audit_sha256 != expected:
            raise ValueError("plan_lowering_audit_sha256_mismatch")
        object.__setattr__(self, "audit_sha256", expected)
        return self


class LoweredExecutionPlan(FrozenContract):
    protocol: Literal[PLAN_LOWERING_PROTOCOL] = PLAN_LOWERING_PROTOCOL
    plan_revision: PlanRevisionRef
    plan_sha256: str
    plan_semantic_sha256: str
    candidate_pool_sha256: str
    dag_edge_contract_sha256s: tuple[str, ...] = ()
    selected_resource_ids: tuple[str, ...]
    step_templates: tuple[ResourceCallRequestTemplate, ...]
    final_output: StepOutputRef
    preflight_audit: PlanLoweringAudit
    lowering_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "LoweredExecutionPlan":
        if self.plan_sha256 != self.plan_semantic_sha256:
            raise ValueError("lowered_plan_semantic_hash_mismatch")
        if self.preflight_audit.plan_sha256 != self.plan_sha256:
            raise ValueError("lowered_plan_audit_hash_mismatch")
        if tuple(item.step_id for item in self.step_templates) != tuple(
            item.execution_context_template.step_id for item in self.step_templates
        ):
            raise ValueError("lowered_plan_step_context_mismatch")
        projected = self.model_dump(mode="python", exclude={"lowering_sha256"})
        _ensure_host_free(projected, field_name="lowered_execution_plan")
        expected = canonical_sha256(projected)
        if self.lowering_sha256:
            legacy_projection = self.model_dump(
                mode="python", exclude={"lowering_sha256"}
            )
            for template in legacy_projection.get("step_templates", ()):
                if isinstance(template, dict):
                    template.pop("format_enforcement", None)
                    template.pop("resource_application", None)
                    template.pop("controller_session_spec", None)
            legacy_expected = canonical_sha256(legacy_projection)
            stage_b_legacy_projection = self.model_dump(
                mode="python", exclude={"lowering_sha256"}
            )
            for template in stage_b_legacy_projection.get("step_templates", ()):
                if isinstance(template, dict):
                    template.pop("controller_session_spec", None)
            stage_b_legacy_expected = canonical_sha256(stage_b_legacy_projection)
            if self.lowering_sha256 not in {
                expected,
                stage_b_legacy_expected,
                legacy_expected,
            }:
                raise ValueError("lowered_execution_plan_sha256_mismatch")
            object.__setattr__(self, "lowering_sha256", self.lowering_sha256)
        else:
            object.__setattr__(self, "lowering_sha256", expected)
        return self


def _binding_sources(value: Any) -> Iterable[tuple[str, str | None, str | None]]:
    """Yield explicit sources without interpreting opaque structured literals."""

    if isinstance(value, (list, tuple)):
        for item in value:
            yield from _binding_sources(item)
        return
    parsed = parse_binding_source(value)
    yield parsed.variant, parsed.from_step, parsed.output_key


def _declared_primary_file(projection: Any) -> bool:
    """A task-declared locator for the public output, rather than a side file."""
    kind = str(projection.artifact_type or "")
    return any(
        bool(item.required) and bool(str(item.path_hint or "").strip())
        and str(getattr(item.artifact_type, "value", item.artifact_type) or kind) in {kind, "file"}
        for item in projection.produced_files
    )


def _complete_resource_application(
    *,
    step: CompilerStepDraft | ExecutablePlanStep,
    definition: ResourceDefinition,
    materialized_output: bool = False,
) -> ResourceApplicationV1:
    """Project the selected Resource/operation into a complete sealed application."""

    entrypoint_id = str(step.entrypoint_id or "invoke")
    entrypoint = definition.entrypoint(entrypoint_id)
    native_output_contract = dict(entrypoint.output_contract)
    semantic = native_output_contract.get("semantic_output")
    semantic_contract = dict(semantic) if isinstance(semantic, Mapping) else None
    target_contract = step.expected_output_contract.model_dump(mode="json")
    operation = next(
        (
            item
            for item in definition.capability_card.capability_operations
            if item.capability_operation_id == str(step.capability_operation_id or "")
        ),
        None,
    )
    materializer = bool(
        operation is not None
        and operation.execution_operation_kind == "write_file"
        and operation.determinism == "deterministic"
        and operation.side_effects == "declared"
        and str(target_contract.get("artifact_type") or "").strip().lower()
        in {str(item).strip().lower() for item in operation.materialized_artifact_types}
    )
    materializer = materializer or bool(
        materialized_output and operation is not None
        and definition.resource_type == "Tool"
        and operation.side_effects == "declared"
        and "task_workspace" in operation.effect_targets
        and str(target_contract.get("artifact_type") or "")
        in set(operation.produced_artifact_types) | set(operation.materialized_artifact_types)
    )
    if materializer:
        source_hash = canonical_sha256(native_output_contract)
        target_hash = canonical_sha256(target_contract)
        realization = OutputRealizationContractV1(
            realization_kind="materialized_file_side_effect",
            source_view="native",
            source_artifact_type=str(native_output_contract.get("artifact_type") or "json"),
            target_artifact_type=str(target_contract.get("artifact_type") or "file"),
            source_contract_sha256=source_hash,
            target_contract_sha256=target_hash,
        )
        proof = OutputReachabilityProof(
            resource_id=step.resource_id,
            capability_operation_id=str(step.capability_operation_id or ""),
            entrypoint_id=entrypoint_id,
            source_view="native",
            source_contract_sha256=source_hash,
            target_contract_sha256=target_hash,
            compatibility="deterministically_convertible",
            realization_kind=realization.realization_kind,
            output_realization_contract_sha256=realization.contract_sha256,
            reason_code="declared_materialized_file_side_effect",
        )
    else:
        proof, realization = prove_output_reachability(
            resource_id=step.resource_id,
            capability_operation_id=str(step.capability_operation_id or ""),
            entrypoint_id=entrypoint_id,
            resource_native_output_contract=native_output_contract,
            target_output_contract=target_contract,
        )
    dependency_bindings: dict[str, Any] = {}
    for name, binding in step.input_bindings.items():
        if any(variant == "step_output" for variant, _, _ in _binding_sources(binding)):
            dependency_bindings[name] = binding
    return ResourceApplicationV1(
        resource_id=step.resource_id,
        resource_type=definition.resource_type,
        capability_operation_id=str(step.capability_operation_id or ""),
        entrypoint_id=entrypoint_id,
        resource_manifest_sha256=definition.manifest_sha256,
        operation_input_contract=entrypoint.input_contract,
        resource_native_output_contract=native_output_contract,
        available_semantic_output_contract=semantic_contract,
        input_bindings=step.input_bindings,
        dependency_bindings=dependency_bindings,
        target_step_output_contract=step.expected_output_contract,
        output_reachability_proof=proof,
        output_realization_contract=realization,
    )


def _artifact_handle_ids(value: Any) -> Iterable[str]:
    """Yield artifact handles without interpreting opaque structured literals."""

    if isinstance(value, (list, tuple)):
        for item in value:
            yield from _artifact_handle_ids(item)
        return
    parsed = parse_binding_source(value)
    if parsed.variant == "artifact_handle":
        yield str(parsed.value or "").removeprefix("artifact:")


def _runtime_requirement(definition: ResourceDefinition, *keys: str) -> Any:
    requirements: Any = definition.runtime_requirements
    for key in keys:
        if not isinstance(requirements, Mapping) or key not in requirements:
            return None
        requirements = requirements[key]
    return requirements


def _structured_output_contract(contract: Any) -> bool:
    artifact_type = str(getattr(contract, "artifact_type", "") or "").strip().lower()
    return artifact_type == "json" or getattr(contract, "schema_hint", None) is not None


def _validated_step_json_schema(
    contract: Any, *, native_output_contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    schema = getattr(contract, "schema_hint", None)
    if not isinstance(schema, Mapping):
        raise ModelResponseContractError("typed_json_output_schema_missing")
    if native_output_contract is not None:
        from .native_output_contracts import (
            native_json_value_only, require_native_json_schema,
        )
        # Only the exact manifest-authorized representation can use this path.
        # It says nothing about semantic fields or a final delivery contract.
        native_identity = {**native_output_contract, "schema_hint": dict(schema)}
        if (
            str(native_output_contract.get("artifact_type") or "").lower() == "json"
            and native_json_value_only(native_output_contract)
            and native_json_value_only(native_identity)
        ):
            return require_native_json_schema(native_identity, schema)
    return require_semantic_json_schema(cast(Mapping[str, Any], schema))


def _literal_matches_contract_kind(value: Any, kind: str) -> bool:
    if kind == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "bool":
        return isinstance(value, bool)
    if kind == "list":
        return isinstance(value, (list, tuple))
    if kind in {"object", "json"}:
        return isinstance(value, Mapping)
    if kind in {"path", "file_path", "directory_path", "text"}:
        return isinstance(value, str)
    return True


def _binding_matches_input_contract(
    *,
    binding: Any,
    contract: Mapping[str, Any],
    context_descriptors_by_handle: Mapping[str, Any],
    prior_steps: Mapping[str, Any],
    candidate_types: Mapping[str, str],
) -> bool:
    parsed = parse_binding_source(binding)
    kind = normalize_contract_kind(contract)
    if parsed.variant == "literal":
        return _literal_matches_contract_kind(parsed.value, kind)
    if parsed.variant == "path":
        return kind in {"path", "file_path", "directory_path"}
    if parsed.variant == "resource":
        return (
            str(parsed.value or "") in candidate_types
            and kind in {"resource", "resource_ref", "text"}
        )
    if parsed.variant == "artifact_handle":
        handle_id = str(parsed.value or "").removeprefix("artifact:")
        descriptor = context_descriptors_by_handle.get(handle_id)
        if descriptor is None:
            return False
        return artifact_handle_matches_input_contract(descriptor, contract)
    if parsed.variant == "step_output":
        producer = prior_steps.get(str(parsed.from_step or ""))
        if producer is None:
            return False
        artifact_type = str(
            producer.expected_output_contract.artifact_type or ""
        ).lower()
        if parsed.value_path is not None:
            if artifact_type != "json":
                return False
            schema = selected_value_schema(producer.expected_output_contract.schema_hint or {}, parsed.value_path)
            types = selected_schema_types(schema)
            allowed = {"text": {"string"}, "path": {"string"}, "file_path": {"string"},
                       "directory_path": {"string"}, "list": {"array"}, "object": {"object"},
                       "json": {"object", "array"}, "int": {"integer"}, "float": {"integer", "number"}, "bool": {"boolean"}}
            return bool(types) and types <= allowed.get(kind, types)
        if kind == "json":
            return artifact_type == "json"
        if kind in {"file_path", "directory_path", "path"}:
            compatible_path_artifact_types = {
                "file", "directory", "bundle", "code", "csv", kind,
            }
            if kind == "path":
                compatible_path_artifact_types.update(
                    {"file_path", "directory_path"}
                )
            return artifact_type in compatible_path_artifact_types
        return True
    return False


def _input_binding_facts(binding: Any, contract: Mapping[str, Any], descriptors: Mapping[str, Any]) -> dict[str, Any]:
    """Describe rejected types without copying payloads or private paths."""
    parsed = parse_binding_source(binding)
    facts: dict[str, Any] = {
        "target_port": str(contract.get("name") or ""),
        "target_kind": normalize_contract_kind(contract),
        "accepts_artifact_handle_item": contract.get("accepts_artifact_handle_item") is True,
        "source_kind": parsed.variant,
    }
    if parsed.variant == "artifact_handle":
        descriptor = descriptors.get(str(parsed.value or "").removeprefix("artifact:"))
        facts["source_registered"] = descriptor is not None
        if descriptor is not None:
            facts["source_artifact_type"] = descriptor.artifact_type
    elif parsed.variant == "literal":
        facts["literal_type"] = type(parsed.value).__name__
    return facts


def _candidate_format_contract(card: Any) -> Mapping[str, Any] | None:
    value = card.runtime_requirements.get("sgar_format_contract")
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise PlanFrameworkValidationError("candidate_format_contract_invalid")
    projection = dict(value)
    supplied = str(projection.pop("format_contract_sha256", ""))
    if supplied != canonical_sha256(projection):
        raise PlanFrameworkValidationError("candidate_format_contract_hash_mismatch")
    return value


def _unique_capability_operation_id(
    *,
    definition: ResourceDefinition,
    operation_kind: OperationKind,
    entrypoint_id: str | None,
) -> str:
    """Resolve only an exact, unique manifest-backed operation identity."""

    card = definition.capability_card
    if card is None:
        raise PlanValidationError(
            "plan_capability_card_missing",
            failure_layer="executability",
        )
    matches = [
        item.capability_operation_id
        for item in card.capability_operations
        if item.declared_operation == operation_kind.value
        and (
            definition.resource_type != "Tool"
            or item.entrypoint_id == entrypoint_id
        )
    ]
    if not matches:
        matches = [
            item.capability_operation_id
            for item in card.capability_operations
            if item.execution_operation_kind == operation_kind.value
            and (
                definition.resource_type != "Tool"
                or item.entrypoint_id == entrypoint_id
            )
        ]
    if len(matches) != 1:
        raise PlanValidationError(
            "plan_capability_operation_not_unique",
            failure_layer="executability",
        )
    return matches[0]


def _selected_format_contract(
    *,
    step: Any,
    cards: Mapping[str, Any],
    resource_type: str | None = None,
    selected_format_contracts: Mapping[str, Mapping[str, Any]] | None = None,
    schema_phase: str | None = None,
) -> Mapping[str, Any] | None:
    card = cards[step.resource_id]
    model = card if card.resource_type == "Model" else cards.get(str(step.agent_base_model_resource_id))
    capability = model.runtime_requirements.get("sgar_structured_output_capability") if model is not None else None
    pending = schema_phase == "compiler_pending" or (isinstance(capability, Mapping) and capability.get("schema_phase") == "compiler_pending")
    if selected_format_contracts is not None and step.step_id in selected_format_contracts:
        value = selected_format_contracts[step.step_id]
        if not isinstance(value, Mapping):
            raise PlanFrameworkValidationError("selected_format_contract_invalid")
        projection = dict(value)
        supplied = str(projection.pop("format_contract_sha256", ""))
        if supplied != canonical_sha256(projection):
            raise PlanFrameworkValidationError(
                "selected_format_contract_hash_mismatch"
            )
        if not _selected_schema_identity_valid(
            card=card, cards=cards, selected_backing_model_id=step.agent_base_model_resource_id,
            contract=value, expected_schema_sha256=canonical_sha256(_validated_step_json_schema(step.expected_output_contract)),
            identity_required=pending,
        ):
            raise PlanFrameworkValidationError("selected_format_contract_identity_mismatch")
        return value
    if pending:
        return None
    selected_type = str(resource_type or getattr(step, "resource_type", ""))
    if selected_type == "Model":
        return _candidate_format_contract(cards[step.resource_id])
    if selected_type == "Agent" and step.agent_base_model_resource_id:
        return _candidate_format_contract(cards[step.agent_base_model_resource_id])
    return None


def _execution_strategy(steps: Sequence[ExecutablePlanStep]) -> str:
    types = {item.resource_type for item in steps}
    if any(item.operation_kind is OperationKind.EXECUTE_SCRIPT for item in steps):
        return "generated_code"
    if "Agent" in types and "Model" in types:
        return "mixed"
    if "Agent" in types:
        return "agent_assisted"
    if "Model" in types:
        return "model_assisted"
    return "tool_only"


def _execution_character(
    steps: Sequence[ExecutablePlanStep],
    cards: Mapping[str, Any],
) -> Literal["deterministic", "generative", "hybrid"]:
    """Derive execution character from selected manifest-backed operations.

    Planner V6 never makes this execution decision. Unknown metadata is kept
    conservative: validation requires a verifier before lowering and the
    resulting plan remains hybrid rather than pretending to be deterministic.
    """

    determinations: set[str] = set()
    for step in steps:
        card = cards[step.resource_id]
        operation = next(
            (
                item
                for item in card.capability_operations
                if item.capability_operation_id == step.capability_operation_id
            ),
            None,
        )
        if operation is None:
            raise PlanFrameworkValidationError(
                "plan_selected_capability_operation_metadata_missing"
            )
        determinations.add(str(operation.determinism))
    if determinations == {"deterministic"}:
        return "deterministic"
    if determinations == {"nondeterministic"}:
        return "generative"
    return "hybrid"


def _controller_callable_representation_issue(
    *,
    controller_step: Any,
    callable_choices: Sequence[Any],
    cards: Mapping[str, Any],
    context_descriptors_by_source: Mapping[str, Any],
) -> int | None:
    """Return a text-only callable that cannot read any required inventory file.

    Workspace inventory adapters may declare aggregate representation facts
    without claiming file content.  When every listed file is known non-text,
    a dynamically addressed UTF-8 file callable has zero usable coverage and
    must not be exposed to a controller as a speculative first route.
    """

    all_known_non_text = False
    for source_id in getattr(controller_step, "consumed_context_source_ids", ()):
        descriptor = context_descriptors_by_source.get(source_id)
        contract = getattr(descriptor, "execution_contract", None)
        if not isinstance(contract, Mapping):
            continue
        if contract.get("contract_kind") != "workspace_file_inventory":
            continue
        try:
            file_count = int(contract.get("file_count", 0))
            known_non_text = int(contract.get("known_non_text_file_count", 0))
            unknown = int(contract.get("unknown_media_type_count", 0))
        except (TypeError, ValueError):
            continue
        if file_count > 0 and known_non_text == file_count and unknown == 0:
            all_known_non_text = True
            break
    if not all_known_non_text:
        return None

    for choice_index, choice in enumerate(callable_choices):
        card = cards.get(getattr(choice, "resource_id", ""))
        if card is None:
            continue
        operation = next(
            (
                item
                for item in getattr(card, "capability_operations", ())
                if item.capability_operation_id
                == getattr(choice, "capability_operation_id", None)
            ),
            None,
        )
        if operation is None:
            continue
        dynamic_ports = set(getattr(choice, "dynamic_input_ports", ()))
        if any(
            port.name in dynamic_ports
            and str(port.kind).strip().lower().replace("-", "_")
            in {"file_path", "filepath"}
            and port.content_encoding == "utf-8"
            for port in getattr(operation, "input_ports", ())
        ):
            return choice_index
    return None


def _static_workspace_effect_delivery_on_final_path(
    *,
    final_step: Any,
    prior_steps: Mapping[str, Any],
    cards: Mapping[str, Any],
    runtime_capabilities: Any,
) -> bool:
    """Return whether the final dependency closure contains a valid mutator.

    A final Model or Agent may return a compact completion receipt for a file,
    directory, or bundle only when a preceding static Tool step on its actual
    dataflow path has declared and can perform the required workspace effect.
    """

    closure: set[str] = set()
    pending = list(getattr(final_step, "depends_on", ()) or ())
    while pending:
        step_id = str(pending.pop())
        if step_id in closure:
            continue
        closure.add(step_id)
        step = prior_steps.get(step_id)
        if step is None:
            continue
        card = cards.get(str(step.resource_id))
        if card is not None:
            operation = next(
                (
                    item
                    for item in card.capability_operations
                    if item.capability_operation_id
                    == step.capability_operation_id
                ),
                None,
            )
            if operation is not None and workspace_effect_mutator_eligible(
                card,
                operation,
                runtime_capabilities,
            ):
                return True
        pending.extend(getattr(step, "depends_on", ()) or ())
    return False


class PlanStructuralValidator:
    """Validate a provider Draft and derive the immutable executable Plan."""

    def validate(
        self,
        *,
        envelope: PlanCompilerInputEnvelope,
        draft: CompilerPlanDraft,
        resource_definitions: Mapping[str, ResourceDefinition],
        compiler_input_sha256: str | None = None,
        invariant_catalog: CompilerInvariantCatalog | None = None,
        selected_format_contracts: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> tuple[ExecutablePlan, PlanValidationAudit]:
        effective_compiler_input_sha256 = (
            str(compiler_input_sha256)
            if compiler_input_sha256 is not None
            else envelope.input_sha256
        )
        if not re.fullmatch(r"[0-9a-f]{64}", effective_compiler_input_sha256):
            raise PlanFrameworkValidationError("plan_compiler_input_hash_invalid")
        active_catalog = invariant_catalog or build_compiler_invariant_catalog(envelope)
        expected_catalog = build_compiler_invariant_catalog(envelope)
        if active_catalog.catalog_sha256 != expected_catalog.catalog_sha256:
            raise PlanFrameworkValidationError("plan_invariant_catalog_mismatch")
        if not draft.is_sufficient:
            raise PlanValidationError(
                draft.insufficiency_code.value if draft.insufficiency_code else "plan_insufficient",
                failure_layer="selection",
            )

        snapshot = envelope.candidate_pool_snapshot
        candidate_ids = [item.resource_id for item in snapshot.candidates]
        candidate_types = {
            item.resource_id: item.resource_type for item in snapshot.candidates
        }
        cards = {item.resource_id: item for item in envelope.candidate_cards}
        context_descriptors_by_source = {
            item.provenance_source_id: item
            for item in envelope.public_context.descriptors
        }
        context_descriptors_by_handle = {
            item.handle_id: item
            for item in envelope.public_context.descriptors
            if item.handle_id
        }
        if set(resource_definitions) != set(candidate_ids):
            raise PlanFrameworkValidationError("plan_resource_definition_set_mismatch")
        if set(cards) != set(candidate_ids):
            raise PlanFrameworkValidationError("plan_candidate_card_set_mismatch")
        controller_candidates = tuple(
            item.step_id for item in draft.steps
            if candidate_types.get(item.resource_id) in {"Model", "Agent"}
        )
        controller_step_id = draft.controller_step_id
        if draft.controller_callable_tools:
            if controller_step_id is None and len(controller_candidates) == 1:
                controller_step_id = controller_candidates[0]
            if controller_step_id not in controller_candidates:
                raise PlanValidationError(
                    "controller_callable_tool_controller_step_invalid",
                    failure_layer="executability",
                )
        elif controller_step_id is not None:
            raise PlanValidationError(
                "controller_step_without_callable_tools",
                failure_layer="executability",
            )
        try:
            controller_policy = load_controller_session_policy()
        except ValueError as exc:
            raise PlanFrameworkValidationError(
                "controller_session_policy_invalid"
            ) from exc

        step_ids: set[str] = set()
        output_by_step: dict[str, str] = {}
        step_by_id: dict[str, Any] = {}
        normalized_steps: list[ExecutablePlanStep] = []
        callable_specs: list[ControllerCallableToolSpecV1] = []
        callable_fixed_resource_ids: set[str] = set()

        for step_index, draft_step in enumerate(draft.steps):
            if draft_step.step_id in step_ids:
                raise PlanValidationError(
                    "plan_step_id_duplicate",
                    failure_layer="protocol",
                )
            if draft_step.resource_id not in candidate_types:
                raise PlanValidationError(
                    "plan_resource_outside_candidate_pool",
                    failure_layer="selection",
                )
            definition = resource_definitions[draft_step.resource_id]
            resource_type = candidate_types[draft_step.resource_id]
            if resource_type not in {"Model", "Tool", "Agent", "Skill", "Resource"}:
                raise PlanValidationError(
                    "plan_resource_type_not_formally_executable",
                    failure_layer="executability",
                )
            if any(
                source_id not in context_descriptors_by_source
                for source_id in draft_step.consumed_context_source_ids
            ):
                raise PlanValidationError(
                    "plan_context_source_undeclared",
                    failure_layer="connection",
                )
            if draft_step.consumed_context_source_ids and resource_type not in {
                "Model",
                "Agent",
            }:
                raise PlanValidationError(
                    "plan_context_content_resource_type_mismatch",
                    failure_layer="connection",
                )
            for binding in draft_step.context_bindings:
                materials = [item for item in envelope.materials if item.source_id == binding.source_id]
                if (resource_type not in {"Model", "Agent"}
                    or binding.source_id not in draft_step.consumed_context_source_ids
                    or len(materials) != 1
                    or materials[0].handle_id != binding.handle_id
                    or materials[0].content_sha256 != binding.content_sha256):
                    raise PlanValidationError("plan_context_binding_material_identity_mismatch",
                                              failure_layer="connection")
            consumed_edge_hashes: set[str] = {
                edge_hash
                for source_id in draft_step.consumed_context_source_ids
                for edge_hash in context_descriptors_by_source[
                    source_id
                ].edge_contract_sha256s
            }
            for binding in draft_step.input_bindings.values():
                parsed_binding = parse_binding_source(binding)
                if parsed_binding.variant != "artifact_handle":
                    continue
                handle_id = str(parsed_binding.value or "")
                descriptor = context_descriptors_by_handle.get(
                    handle_id.removeprefix("artifact:")
                )
                if descriptor is not None:
                    consumed_edge_hashes.update(
                        descriptor.edge_contract_sha256s
                    )
            if definition.resource_id != draft_step.resource_id:
                raise PlanFrameworkValidationError("plan_resource_definition_id_mismatch")
            if definition.resource_type != resource_type:
                raise PlanFrameworkValidationError("plan_resource_definition_type_mismatch")
            allowed = set(active_catalog.allowed_operation_kinds.get(resource_type, ()))
            if draft_step.operation_kind.value not in allowed:
                raise PlanValidationError(
                    "plan_operation_kind_resource_type_mismatch",
                    failure_layer="selection",
                )

            entrypoint_id: str | None = draft_step.entrypoint_id
            if resource_type == "Tool":
                if entrypoint_id is None:
                    if len(definition.entrypoints) != 1:
                        raise PlanValidationError(
                            "plan_multi_entrypoint_tool_requires_entrypoint",
                            failure_layer="connection",
                        )
                    entrypoint_id = definition.entrypoints[0].entrypoint_id
                try:
                    entrypoint = definition.entrypoint(entrypoint_id)
                except Exception as exc:
                    raise PlanValidationError(
                        "plan_unknown_entrypoint",
                        failure_layer="connection",
                    ) from exc
                required_names: list[str] = []
                declared_names: list[str] = []
                for item in entrypoint.input_contract:
                    name = str(item.get("name") or "").strip()
                    if not name:
                        raise PlanFrameworkValidationError(
                            "plan_entrypoint_input_contract_name_missing"
                        )
                    if name in declared_names:
                        raise PlanFrameworkValidationError(
                            "plan_entrypoint_input_contract_name_duplicate"
                        )
                    declared_names.append(name)
                    if bool(item.get("required", True)):
                        required_names.append(name)
                unexpected = sorted(
                    set(draft_step.input_bindings) - set(declared_names)
                )
                if unexpected:
                    raise PlanValidationError(
                        "plan_undeclared_binding_name",
                        failure_layer="connection",
                    )
                missing = [
                    name for name in required_names if name not in draft_step.input_bindings
                ]
                if missing:
                    raise PlanValidationError(
                        "plan_required_binding_missing",
                        failure_layer="connection",
                    )
                input_contract_by_name = {
                    str(item.get("name") or "").strip(): item
                    for item in entrypoint.input_contract
                }
                for name, binding in draft_step.input_bindings.items():
                    try:
                        compatible = _binding_matches_input_contract(
                            binding=binding,
                            contract=input_contract_by_name[name],
                            context_descriptors_by_handle=context_descriptors_by_handle,
                            prior_steps=step_by_id,
                            candidate_types=candidate_types,
                        )
                    except BindingProtocolError as exc:
                        raise PlanValidationError(
                            exc.code,
                            failure_layer="connection",
                        ) from exc
                    if not compatible:
                        raise PlanValidationError(
                            "plan_binding_input_contract_mismatch",
                            failure_layer="connection",
                            path=("steps", step_index, "input_bindings", name),
                            step_id=draft_step.step_id,
                            input_binding=_input_binding_facts(binding, input_contract_by_name[name], context_descriptors_by_handle),
                        )
            elif entrypoint_id is not None:
                raise PlanValidationError(
                    "plan_non_tool_has_entrypoint",
                    failure_layer="protocol",
                )

            capability_operation_id = (
                draft_step.capability_operation_id
                or _unique_capability_operation_id(
                    definition=definition,
                    operation_kind=draft_step.operation_kind,
                    entrypoint_id=entrypoint_id,
                )
            )
            selected_operation = next(
                (
                    item
                    for item in cards[draft_step.resource_id].capability_operations
                    if item.capability_operation_id == capability_operation_id
                ),
                None,
            )
            if selected_operation is None:
                raise PlanValidationError(
                    "plan_capability_operation_unknown",
                    failure_layer="selection",
                )

            known_profiles = {item.profile_id for item in definition.application_profiles}
            if any(
                profile_id not in known_profiles
                and candidate_types.get(profile_id) != "Skill"
                for profile_id in draft_step.advisory_profile_refs
            ):
                raise PlanValidationError(
                    "plan_unknown_application_profile",
                    failure_layer="selection",
                )

            if resource_type == "Agent":
                base_model = draft_step.agent_base_model_resource_id
                if not base_model:
                    raise PlanValidationError(
                        "plan_agent_base_model_missing",
                        failure_layer="selection",
                    )
                if candidate_types.get(base_model) != "Model":
                    raise PlanValidationError(
                        "plan_agent_base_model_invalid",
                        failure_layer="selection",
                    )
                allowed_models = set(cards[draft_step.resource_id].agent_base_model_candidates)
                if base_model not in allowed_models:
                    raise PlanValidationError(
                        "plan_agent_base_model_outside_closure",
                        failure_layer="selection",
                    )
            elif draft_step.agent_base_model_resource_id is not None:
                raise PlanValidationError(
                    "plan_non_agent_has_base_model",
                    failure_layer="protocol",
                )

            is_final_step = bool(
                draft.final_output is not None
                and draft.final_output.step_id == draft_step.step_id
                and draft.final_output.output_key == draft_step.output_key
            )
            step_artifact_type = str(
                draft_step.expected_output_contract.artifact_type or ""
            ).strip().lower()
            if step_artifact_type == "json":
                try:
                    _validated_step_json_schema(
                        draft_step.expected_output_contract,
                        native_output_contract=(
                            entrypoint.output_contract
                            if resource_type == "Tool" and not is_final_step
                            else None
                        ),
                    )
                except ModelResponseContractError as exc:
                    raise PlanValidationError(
                        "plan_json_output_schema_invalid",
                        failure_layer="executability",
                    ) from exc

            format_contract = None
            if _structured_output_contract(draft_step.expected_output_contract) and resource_type in {
                "Model",
                "Agent",
            }:
                format_contract = _selected_format_contract(
                    step=draft_step,
                    cards=cards,
                    resource_type=resource_type,
                    selected_format_contracts=selected_format_contracts,
                    schema_phase=classify_output_schema_phase(envelope.contract_projection),
                )
                if format_contract is None:
                    raise PlanValidationError(
                        "plan_structured_producer_format_evidence_missing",
                        failure_layer="executability",
                    )
                try:
                    step_requirement = OutputFormatRequirement.from_json_schema(
                        artifact_type=step_artifact_type,
                        json_schema=_validated_step_json_schema(
                            draft_step.expected_output_contract
                        ),
                        schema_source="compiler_step_contract",
                    )
                except ModelResponseContractError as exc:
                    raise PlanValidationError(
                        "plan_structured_producer_schema_binding_invalid",
                        failure_layer="executability",
                    ) from exc
                if (
                    str(format_contract.get("schema_sha256") or "")
                    != str(step_requirement.schema_sha256 or "")
                ):
                    raise PlanValidationError(
                        "plan_structured_producer_schema_binding_mismatch",
                        failure_layer="executability",
                    )
                if not bool(format_contract.get("final_producer_eligible")):
                    raise PlanValidationError(
                        "plan_structured_producer_ineligible",
                        failure_layer="executability",
                    )
                modes = set(format_contract.get("allowed_enforcement_modes") or ())
                if not modes & {
                    "native_strict_schema",
                    "json_object_local_validator",
                }:
                    raise PlanValidationError(
                        "plan_structured_producer_has_no_enforcement_mode",
                        failure_layer="executability",
                    )

            if is_final_step:
                schema_phase = classify_output_schema_phase(envelope.contract_projection)
                static_workspace_effect_delivery = bool(
                    resource_type in {"Model", "Agent"}
                    and _static_workspace_effect_delivery_on_final_path(
                        final_step=draft_step,
                        prior_steps=step_by_id,
                        cards=cards,
                        runtime_capabilities=envelope.runtime_capabilities,
                    )
                )
                workspace_effect_delivery = bool(
                    workspace_file_delivery_required(envelope.contract_projection)
                    and (
                        static_workspace_effect_delivery
                        or (
                            draft_step.step_id == controller_step_id
                            and any(
                                choice.resource_id in cards
                                and any(
                                    operation.capability_operation_id
                                    == choice.capability_operation_id
                                    and workspace_effect_mutator_eligible(
                                        cards[choice.resource_id],
                                        operation,
                                        envelope.runtime_capabilities,
                                    )
                                    for operation in cards[
                                        choice.resource_id
                                    ].capability_operations
                                )
                                for choice in draft.controller_callable_tools
                            )
                        )
                    )
                )
                if not resolve_final_step_eligibility(
                    cards[draft_step.resource_id], selected_operation, step_artifact_type,
                    schema_phase == "compiler_pending", envelope.runtime_capabilities,
                    phase="postcompile", schema_phase=schema_phase, candidate_cards=cards,
                    selected_backing_model_id=draft_step.agent_base_model_resource_id,
                    expected_schema_sha256=(
                        canonical_sha256(_validated_step_json_schema(draft_step.expected_output_contract))
                        if step_artifact_type == "json" else None
                    ),
                    selected_exact_contract=format_contract,
                    workspace_effect_delivery=workspace_effect_delivery,
                ):
                    raise PlanValidationError("plan_final_step_operation_ineligible", failure_layer="executability")

            if any(dependency not in step_ids for dependency in draft_step.depends_on):
                raise PlanValidationError(
                    "plan_steps_not_topologically_ordered",
                    failure_layer="connection",
                )

            try:
                for binding in draft_step.input_bindings.values():
                    for variant, from_step, output_key in _binding_sources(binding):
                        if variant != "step_output":
                            continue
                        if not from_step or not output_key:
                            raise PlanValidationError(
                                "plan_step_output_binding_incomplete",
                                failure_layer="connection",
                            )
                        if from_step not in step_ids:
                            raise PlanValidationError(
                                "plan_step_output_producer_missing",
                                failure_layer="connection",
                            )
                        if output_by_step.get(from_step) != output_key:
                            raise PlanValidationError(
                                "plan_step_output_key_mismatch",
                                failure_layer="connection",
                            )
                        if from_step not in draft_step.depends_on:
                            raise PlanValidationError(
                                "plan_data_dependency_not_declared",
                                failure_layer="connection",
                            )
            except BindingProtocolError as exc:
                raise PlanValidationError(
                    exc.code,
                    failure_layer="connection",
                ) from exc

            runtime_kind = (
                _runtime_requirement(definition, "runtime_kind")
                or _runtime_requirement(definition, "runtime_type")
            )
            supported_runtime_kinds = set(
                envelope.runtime_capabilities.supported_runtime_kinds
            )
            if (
                runtime_kind
                and supported_runtime_kinds
                and str(runtime_kind) not in supported_runtime_kinds
            ):
                raise PlanValidationError(
                    "plan_runtime_kind_unsupported",
                    failure_layer="executability",
                )
            if not runtime_kind or not runtime_adapter_supported(
                definition.resource_type, str(runtime_kind)
            ):
                raise PlanValidationError(
                    "plan_runtime_adapter_unsupported",
                    failure_layer="executability",
                )
            network_required = requires_execution_network(definition.runtime_requirements, draft_step)
            if (
                network_required
                and envelope.runtime_capabilities.network_policy == "disabled"
            ):
                raise PlanValidationError(
                    "plan_network_requirement_unsupported",
                    failure_layer="executability",
                )

            normalized = ExecutablePlanStep(
                step_id=draft_step.step_id,
                resource_id=draft_step.resource_id,
                capability_operation_id=(
                    capability_operation_id
                ),
                satisfied_obligation_ids=draft_step.satisfied_obligation_ids,
                resource_type=resource_type,
                operation_kind=draft_step.operation_kind,
                entrypoint_id=entrypoint_id,
                intent=draft_step.intent,
                execution_network_required=draft_step.execution_network_required,
                depends_on=draft_step.depends_on,
                input_bindings=draft_step.input_bindings,
                consumed_context_source_ids=draft_step.consumed_context_source_ids,
                context_bindings=draft_step.context_bindings,
                consumed_edge_contract_sha256s=tuple(
                    sorted(consumed_edge_hashes)
                ),
                output_key=draft_step.output_key,
                expected_output_contract=draft_step.expected_output_contract,
                advisory_profile_refs=tuple(sorted(draft_step.advisory_profile_refs)),
                agent_base_model_resource_id=draft_step.agent_base_model_resource_id,
            )
            if resource_type in {"Model", "Agent"}:
                controller_spec = derive_controller_session_spec(
                    subtask_id=(
                        envelope.plan_revision.subtask_revision.subtask_id
                    ),
                    subtask_revision=(
                        envelope.plan_revision.subtask_revision.subtask_revision
                    ),
                    controller_step_id=normalized.step_id,
                    controller_resource_id=normalized.resource_id,
                    controller_resource_type=resource_type,
                    backing_model_resource_id=(
                        normalized.agent_base_model_resource_id
                    ),
                    task_instruction=normalized.intent,
                    declared_input_bindings=normalized.input_bindings,
                    context_bindings=normalized.context_bindings,
                    expected_output_contract=(
                        normalized.expected_output_contract.model_dump(mode="json")
                    ),
                    policy=controller_policy,
                )
                normalized = normalized.model_copy(
                    update={"controller_session_spec": controller_spec}
                )
            if definition.resource_type in {"Tool", "Resource"}:
                resource_application = _complete_resource_application(
                    step=normalized,
                    definition=definition,
                    materialized_output=is_final_step and _declared_primary_file(envelope.contract_projection),
                )
                if resource_application.output_reachability_proof.compatibility not in {
                    "exact",
                    "deterministically_convertible",
                }:
                    from .compiler_output_facts import explain_output_rejection
                    details = explain_output_rejection(
                        resource_application.resource_native_output_contract,
                        normalized.expected_output_contract.model_dump(mode="json"),
                        resource_application.output_reachability_proof,
                    )
                    if details["proof_reason"] in {
                        "representation_contract_artifact_type_missing",
                        "manifest_semantic_payload_path_missing",
                    } or details["source"]["native"]["machine_schema_status"] in {"invalid", "conflicting"}:
                        error = PlanFrameworkValidationError("plan_output_authority_invalid")
                        error.output_diagnostic = {
                            "protocol": "sgar-compiler-output-diagnostic-v2",
                            "authority_source": "resource_runtime.output_contract",
                            "responsibility_stage": "plan_compiler_validation",
                            "step_id": normalized.step_id,
                            "output_reachability": details,
                            "response_path": [],
                        }
                        raise error
                    raise PlanValidationError(
                        "plan_output_reachability_not_deterministic",
                        output_reachability=details,
                        step_id=normalized.step_id,
                        failure_layer="executability",
                        path=(
                            "steps",
                            len(normalized_steps),
                            "expected_output_contract",
                        ),
                    )
                normalized = normalized.model_copy(
                    update={"resource_application": resource_application}
                )
            normalized_steps.append(normalized)
            step_ids.add(draft_step.step_id)
            output_by_step[draft_step.step_id] = draft_step.output_key
            step_by_id[draft_step.step_id] = normalized

        if draft.controller_callable_tools:
            controller_indexes = tuple(
                index
                for index, step in enumerate(normalized_steps)
                if step.step_id == controller_step_id
            )
            if len(controller_indexes) != 1:
                raise PlanValidationError(
                    "controller_callable_tool_controller_step_invalid",
                    failure_layer="executability",
                )
            controller_index = controller_indexes[0]
            controller_step = normalized_steps[controller_index]
            representation_issue = _controller_callable_representation_issue(
                controller_step=controller_step,
                callable_choices=draft.controller_callable_tools,
                cards=cards,
                context_descriptors_by_source=context_descriptors_by_source,
            )
            if representation_issue is not None:
                raise PlanValidationError(
                    "controller_callable_representation_coverage_incompatible",
                    failure_layer="connection",
                    path=("controller_callable_tools", representation_issue),
                    step_id=controller_step.step_id,
                )
            controller_closure: set[str] = set()
            pending_controller_dependencies = list(controller_step.depends_on)
            while pending_controller_dependencies:
                dependency_id = pending_controller_dependencies.pop()
                if dependency_id in controller_closure:
                    continue
                dependency = step_by_id.get(dependency_id)
                if dependency is None:
                    raise PlanValidationError(
                        "callable_tool_fixed_source_unavailable",
                        failure_layer="connection",
                    )
                controller_closure.add(dependency_id)
                pending_controller_dependencies.extend(dependency.depends_on)

            materials_by_id = {item.source_id: item for item in envelope.materials}
            context_by_source: dict[str, list[Any]] = defaultdict(list)
            for descriptor in envelope.public_context.descriptors:
                context_by_source[descriptor.provenance_source_id].append(descriptor)

            for choice_index, choice in enumerate(draft.controller_callable_tools):
                # A Tool may perform an initial deterministic read and then
                # remain callable by the Controller for later observations.
                # Each use retains its own bindings and execution identity.
                definition = resource_definitions.get(choice.resource_id)
                card = cards.get(choice.resource_id)
                if definition is None or card is None:
                    raise PlanValidationError(
                        "compiler_v3_callable_resource_not_candidate",
                        failure_layer="selection",
                    )
                if definition.resource_type != "Tool" or card.resource_type != "Tool":
                    raise PlanValidationError(
                        "controller_callable_resource_not_tool",
                        failure_layer="selection",
                    )
                if definition.manifest_sha256 != card.manifest_sha256:
                    raise PlanFrameworkValidationError(
                        "controller_callable_manifest_identity_mismatch"
                    )
                if (
                    str(card.availability_status or "").strip().casefold()
                    not in {"active", "available", "ok", "ready"}
                    or card.compatibility_status == "incompatible"
                ):
                    raise PlanValidationError(
                        "controller_callable_tool_unavailable",
                        failure_layer="executability",
                    )
                operation = next(
                    (
                        item
                        for item in card.capability_operations
                        if item.capability_operation_id
                        == choice.capability_operation_id
                    ),
                    None,
                )
                if operation is None or not operation.entrypoint_id:
                    raise PlanValidationError(
                        "controller_callable_operation_unknown",
                        failure_layer="selection",
                    )
                runtime_kind = (
                    _runtime_requirement(definition, "runtime_kind")
                    or _runtime_requirement(definition, "runtime_type")
                )
                if (
                    not runtime_kind
                    or not runtime_adapter_supported("Tool", str(runtime_kind))
                    or (
                        envelope.runtime_capabilities.supported_runtime_kinds
                        and str(runtime_kind)
                        not in set(
                            envelope.runtime_capabilities.supported_runtime_kinds
                        )
                    )
                ):
                    raise PlanValidationError(
                        "controller_callable_runtime_unsupported",
                        failure_layer="executability",
                    )
                if requires_execution_network(definition.runtime_requirements, choice) and (
                    envelope.runtime_capabilities.network_policy == "disabled"
                ):
                    raise PlanValidationError(
                        "controller_callable_network_requirement_unsupported",
                        failure_layer="executability",
                    )
                entrypoint = definition.entrypoint(str(operation.entrypoint_id))
                contract_by_name = {
                    str(item.get("name") or ""): item
                    for item in entrypoint.input_contract
                }
                fixed_bindings: dict[str, Any] = {}
                for mapping_index, mapping in enumerate(choice.fixed_input_mappings):
                    if mapping.target_port not in contract_by_name:
                        raise PlanValidationError(
                            "callable_tool_fixed_port_undeclared",
                            failure_layer="connection",
                        )
                    if mapping.source_kind == "literal":
                        assert mapping.literal_value is not None
                        binding: Any = {
                            "literal": mapping.literal_value.python_value()
                        }
                    elif mapping.source_kind == "artifact_handle":
                        from .executable_plan import (
                            resolve_material_delivery as resolve_callable_material_delivery,
                            select_material_delivery_mode as select_callable_delivery_mode,
                        )

                        source_id = str(mapping.source_id or "")
                        descriptors = context_by_source.get(source_id, [])
                        material = materials_by_id.get(source_id)
                        if len(descriptors) != 1 or material is None:
                            raise PlanValidationError(
                                "compiler_v3_context_source_unauthorized",
                                failure_layer="connection",
                            )
                        descriptor = descriptors[0]
                        handle_id = str(descriptor.handle_id or "").strip()
                        if not handle_id:
                            raise PlanValidationError(
                                "compiler_v3_artifact_runtime_handle_missing",
                                failure_layer="connection",
                            )
                        delivery = resolve_callable_material_delivery(
                            material=material,
                            candidate_card=card,
                            operation=operation,
                            target_port=mapping.target_port,
                            runtime_capabilities=envelope.runtime_capabilities,
                        )
                        select_callable_delivery_mode(
                            resolution=delivery,
                            candidate_card=card,
                            runtime_capabilities=envelope.runtime_capabilities,
                        )
                        binding = {"artifact_handle": handle_id}
                    elif mapping.source_kind == "resource":
                        source_id = str(mapping.source_id or "")
                        if source_id not in candidate_types:
                            raise PlanValidationError(
                                "compiler_v3_resource_source_unauthorized",
                                failure_layer="connection",
                            )
                        callable_fixed_resource_ids.add(source_id)
                        binding = {"resource_id": source_id}
                    else:
                        from_step = str(mapping.from_step or "")
                        if from_step not in controller_closure:
                            raise PlanValidationError(
                                "callable_tool_fixed_source_unavailable",
                                failure_layer="connection",
                            )
                        binding = {
                            "from_step": from_step,
                            "output_key": output_by_step[from_step],
                            **({"value_path": list(mapping.value_path)} if mapping.value_path is not None else {}),
                        }
                    try:
                        compatible = _binding_matches_input_contract(
                            binding=binding,
                            contract=contract_by_name[mapping.target_port],
                            context_descriptors_by_handle=context_descriptors_by_handle,
                            prior_steps=step_by_id,
                            candidate_types=candidate_types,
                        )
                    except BindingProtocolError as exc:
                        raise PlanValidationError(
                            exc.code, failure_layer="connection"
                        ) from exc
                    if not compatible:
                        raise PlanValidationError(
                            "plan_binding_input_contract_mismatch",
                            failure_layer="connection",
                            path=("controller_callable_tools", choice_index, "fixed_input_mappings", mapping_index),
                            step_id=draft.controller_step_id,
                            input_binding=_input_binding_facts(binding, contract_by_name[mapping.target_port], context_descriptors_by_handle),
                        )
                    fixed_bindings[mapping.target_port] = binding
                try:
                    callable_specs.append(
                        derive_controller_callable_tool_spec(
                            definition=definition,
                            capability_operation_id=choice.capability_operation_id,
                            fixed_input_bindings=fixed_bindings,
                            dynamic_input_names=choice.dynamic_input_ports,
                            capability_evidence_refs=choice.capability_evidence_refs,
                            execution_network_required=choice.execution_network_required,
                        )
                    )
                except ControllerToolingError as exc:
                    raise PlanValidationError(
                        exc.code, failure_layer="executability"
                    ) from exc

            controller_spec = derive_controller_session_spec(
                subtask_id=envelope.plan_revision.subtask_revision.subtask_id,
                subtask_revision=(
                    envelope.plan_revision.subtask_revision.subtask_revision
                ),
                controller_step_id=controller_step.step_id,
                controller_resource_id=controller_step.resource_id,
                controller_resource_type=controller_step.resource_type,
                backing_model_resource_id=controller_step.agent_base_model_resource_id,
                task_instruction=controller_step.intent,
                declared_input_bindings=controller_step.input_bindings,
                context_bindings=controller_step.context_bindings,
                expected_output_contract=(
                    controller_step.expected_output_contract.model_dump(mode="json")
                ),
                policy=controller_policy,
                callable_tools=callable_specs,
            )
            if not isinstance(controller_spec, ControllerSessionSpecV2):
                raise PlanFrameworkValidationError(
                    "controller_session_v2_projection_failed"
                )
            controller_step = controller_step.model_copy(
                update={"controller_session_spec": controller_spec}
            )
            normalized_steps[controller_index] = controller_step
            step_by_id[controller_step.step_id] = controller_step

        if draft.final_output is None:
            raise PlanValidationError(
                "plan_final_output_missing",
                failure_layer="protocol",
            )
        if output_by_step.get(draft.final_output.step_id) != draft.final_output.output_key:
            raise PlanValidationError(
                "plan_final_output_reference_invalid",
                failure_layer="connection",
            )
        final_step = step_by_id[draft.final_output.step_id]
        final_artifact_type = str(
            final_step.expected_output_contract.artifact_type or ""
        )
        required_artifact_type = str(envelope.contract_projection.artifact_type or "")
        if not final_artifact_type or final_artifact_type != required_artifact_type:
            raise PlanValidationError(
                "plan_final_output_contract_mismatch",
                failure_layer="executability",
            )
        expected_kind = getattr(getattr(envelope.contract_projection.semantic_contract_v2, "output", None), "content_kind", "value")
        if final_step.expected_output_contract.content_kind != expected_kind:
            raise PlanValidationError("plan_final_content_kind_mismatch", failure_layer="executability")
        if envelope.contract_projection.semantic_contract_v2 is not None:
            authoritative_final_contract = final_step.expected_output_contract
            if not str(authoritative_final_contract.description or "").strip():
                raise PlanValidationError(
                    "plan_final_output_semantic_description_missing",
                    failure_layer="executability",
                )
            if required_artifact_type == "json":
                try:
                    _validated_step_json_schema(authoritative_final_contract)
                except ModelResponseContractError as exc:
                    raise PlanValidationError(
                        "plan_final_output_json_schema_missing_or_broad",
                        failure_layer="executability",
                    ) from exc
        else:
            try:
                final_requirement = OutputFormatRequirement.from_contract_projection(
                    envelope.contract_projection
                )
            except ModelResponseContractError as exc:
                raise PlanFrameworkValidationError(
                    "plan_final_output_format_contract_invalid"
                ) from exc
            authoritative_final_contract = StepOutputContract(
                artifact_type=envelope.contract_projection.artifact_type,
                schema_hint=final_requirement.json_schema,
                description=envelope.contract_projection.expected_output,
                serialization_format=(final_step.expected_output_contract.serialization_format),
            )
        if envelope.contract_projection.semantic_contract_v2 is None and (
            final_step.expected_output_contract.model_dump(mode="json")
            != authoritative_final_contract.model_dump(mode="json")
        ):
            raise PlanValidationError(
                "plan_final_output_semantic_contract_mismatch",
                failure_layer="executability",
            )

        reachable: set[str] = set()
        pending = [draft.final_output.step_id]
        while pending:
            current = pending.pop()
            if current in reachable:
                continue
            reachable.add(current)
            pending.extend(step_by_id[current].depends_on)
        disconnected = tuple(
            item.step_id for item in normalized_steps if item.step_id not in reachable
        )
        if disconnected:
            raise PlanValidationError(
                "plan_contains_disconnected_steps",
                failure_layer="connection",
            )
        v6_semantic_edge_authority = bool(
            envelope.contract_projection.semantic_contract_v2 is not None
            and envelope.public_context.incoming_semantic_edges_v2
        )
        for edge in envelope.public_context.incoming_edge_contracts:
            consumers = [
                step
                for step in normalized_steps
                if step.step_id in reachable
                and edge.edge_contract_sha256
                in step.consumed_edge_contract_sha256s
            ]
            if not consumers:
                raise PlanValidationError(
                    "plan_required_edge_not_consumed",
                    failure_layer="connection",
                )
            # Planner V6 declares only the semantic producer-consumer edge.  The
            # Compiler selects the concrete resource and therefore owns whether
            # the registered handle is delivered to a Model/Agent as bounded
            # context or to another runtime as a handle.  Keep the legacy mode
            # checks for V4/V5 replay, while V6 is validated below against the
            # exact selected step, input port, handle, and semantic edge hash.
            if (
                not v6_semantic_edge_authority
                and edge.consumption_mode == "context_content"
                and not any(
                    step.resource_type in {"Model", "Agent"}
                    and bool(step.consumed_context_source_ids)
                    for step in consumers
                )
            ):
                raise PlanValidationError(
                    "plan_edge_context_consumption_mode_mismatch",
                    failure_layer="connection",
                )
            if (
                not v6_semantic_edge_authority
                and edge.consumption_mode == "artifact_handle"
                and not any(
                    step.resource_type not in {"Model", "Agent"}
                    for step in consumers
                )
            ):
                raise PlanValidationError(
                    "plan_edge_handle_consumption_mode_mismatch",
                    failure_layer="connection",
                )

        executable_edges_v2: list[ExecutableEdgeContractV2] = []
        for edge in envelope.public_context.incoming_semantic_edges_v2:
            if edge.consumer_id != envelope.plan_revision.subtask_revision.subtask_id:
                raise PlanValidationError(
                    "plan_semantic_edge_consumer_mismatch",
                    failure_layer="connection",
                )
            producer_descriptors = [
                descriptor
                for descriptor in envelope.public_context.descriptors
                if descriptor.producer_task == edge.producer_id
            ]
            if len(producer_descriptors) != 1:
                raise PlanValidationError(
                    "plan_semantic_edge_source_not_unique",
                    failure_layer="connection",
                )
            producer_handle = producer_descriptors[0].handle_id
            consumers: list[tuple[str, str, str]] = []
            try:
                for step in normalized_steps:
                    if step.step_id not in reachable:
                        continue
                    for port_name, binding in step.input_bindings.items():
                        if producer_handle in set(_artifact_handle_ids(binding)):
                            consumers.append(
                                (step.step_id, port_name, "artifact_handle")
                            )
                    if (
                        producer_descriptors[0].provenance_source_id
                        in set(step.consumed_context_source_ids)
                    ):
                        # Model and Agent adapters consume authorized material
                        # through their bounded context projection instead of a
                        # named Tool input port.  That is still an exact runtime
                        # binding of the same upstream task-final handle.
                        consumers.append(
                            (step.step_id, "context", "context_content")
                        )
            except BindingProtocolError as exc:
                raise PlanValidationError(
                    exc.code,
                    failure_layer="connection",
                ) from exc
            if not consumers:
                raise PlanValidationError(
                    "plan_semantic_edge_not_consumed",
                    failure_layer="connection",
                )
            for step_id, port_name, transport in sorted(set(consumers)):
                executable_edges_v2.append(
                    ExecutableEdgeContractV2(
                        semantic_edge_sha256=edge.edge_sha256,
                        producer_id=edge.producer_id,
                        consumer_id=edge.consumer_id,
                        source_output_key=edge.producer_output_ref,
                        target_step_id=step_id,
                        target_input_port=port_name,
                        transport=transport,
                    )
                )

        edges_by_parent: dict[str, tuple[str, ...]] = defaultdict(tuple)
        selected_agent_models = {
            (step.resource_id, step.agent_base_model_resource_id)
            for step in normalized_steps if step.agent_base_model_resource_id
        }
        for edge in envelope.dependency_edges:
            if (edge.requirement_kind == "agent_base_model"
                    and (edge.parent_resource_id, edge.child_resource_id) not in selected_agent_models):
                continue
            edges_by_parent[edge.parent_resource_id] = (
                *edges_by_parent[edge.parent_resource_id],
                edge.child_resource_id,
            )

        selected_seed = {item.resource_id for item in normalized_steps}
        agent_attachment: dict[str, set[str]] = defaultdict(set)
        for step in normalized_steps:
            if step.agent_base_model_resource_id:
                selected_seed.add(step.agent_base_model_resource_id)
                agent_attachment[step.agent_base_model_resource_id].add(step.step_id)
        callable_attachment: dict[str, set[str]] = defaultdict(set)
        if callable_specs:
            controller_step_id = next(
                item.step_id
                for item in normalized_steps
                if isinstance(item.controller_session_spec, ControllerSessionSpecV2)
            )
            for spec in callable_specs:
                selected_seed.add(spec.resource_id)
                callable_attachment[spec.resource_id].add(controller_step_id)
            for resource_id in callable_fixed_resource_ids:
                selected_seed.add(resource_id)
                callable_attachment[resource_id].add(controller_step_id)

        selected = set(selected_seed)
        pending_resources = list(selected_seed)
        while pending_resources:
            parent = pending_resources.pop()
            for child in edges_by_parent.get(parent, ()):
                if child not in candidate_types:
                    raise PlanValidationError(
                        "plan_required_dependency_outside_candidate_pool",
                        failure_layer="selection",
                    )
                if child not in selected:
                    selected.add(child)
                    pending_resources.append(child)

        selected_ids = tuple(item for item in candidate_ids if item in selected)
        step_attachment: dict[str, set[str]] = defaultdict(set)
        for step in normalized_steps:
            step_attachment[step.resource_id].add(step.step_id)

        dependency_attachment: dict[str, set[str]] = defaultdict(set)
        for step in normalized_steps:
            frontier = [step.resource_id]
            visited: set[str] = set()
            while frontier:
                parent = frontier.pop()
                if parent in visited:
                    continue
                visited.add(parent)
                for child in edges_by_parent.get(parent, ()):
                    dependency_attachment[child].add(step.step_id)
                    frontier.append(child)
        for resource_id, attached_steps in callable_attachment.items():
            frontier = [resource_id]
            visited: set[str] = set()
            while frontier:
                parent = frontier.pop()
                if parent in visited:
                    continue
                visited.add(parent)
                dependency_attachment[parent].update(attached_steps)
                for child in edges_by_parent.get(parent, ()):
                    dependency_attachment[child].update(attached_steps)
                    frontier.append(child)

        usage_records: list[ResourceUsageRecord] = []
        for resource_id in selected_ids:
            if resource_id in step_attachment:
                use_as = "executable_step"
                attached = step_attachment[resource_id]
            elif resource_id in agent_attachment:
                use_as = "agent_base_model"
                attached = agent_attachment[resource_id]
            elif resource_id in callable_attachment:
                use_as = "runtime_dependency"
                attached = callable_attachment[resource_id]
            else:
                use_as = "runtime_dependency"
                attached = dependency_attachment[resource_id]
            usage_records.append(
                ResourceUsageRecord(
                    resource_id=resource_id,
                    use_as=use_as,
                    attached_to_steps=tuple(sorted(attached)),
                )
            )

        model_call_counts: Counter[str] = Counter()
        for step in normalized_steps:
            if step.resource_type == "Model":
                model_call_counts[step.resource_id] += 1
            if step.resource_type == "Agent" and step.agent_base_model_resource_id:
                model_call_counts[step.agent_base_model_resource_id] += 1
        model_cost_evidence: list[ModelCostEvidence] = []
        for resource_id in selected_ids:
            call_count = model_call_counts.get(resource_id, 0)
            if not call_count:
                continue
            pricing = cards[resource_id].model_pricing
            if pricing is None:
                raise PlanFrameworkValidationError("plan_selected_model_pricing_missing")
            model_cost_evidence.append(
                ModelCostEvidence(
                    pricing_catalog_sha256=pricing.pricing_catalog_sha256,
                    model_resource_id=pricing.resource_id,
                    api_model_id=pricing.api_model_id,
                    input_per_m=pricing.input_per_m,
                    cache_per_m=pricing.cache_per_m,
                    output_per_m=pricing.output_per_m,
                    expected_call_count=call_count,
                    usage_estimate_status="unknown",
                )
            )

        if not model_cost_evidence:
            cost_comparison_status = "comparable"
            objective_status = "valid"
        elif len(model_cost_evidence) == 1:
            cost_comparison_status = "incomparable"
            objective_status = "valid_cost_incomparable"
        else:
            cost_comparison_status = "partially_comparable"
            objective_status = "valid_cost_incomparable"
        objective = PlanObjectiveEvidence(
            contract_satisfied=True,
            dependency_complete=True,
            runtime_compatible=True,
            final_output_reachable=True,
            selected_resource_count=len(selected_ids),
            executable_step_count=len(normalized_steps),
            unused_selected_resources=(),
            disconnected_steps=(),
            model_cost_evidence=tuple(model_cost_evidence),
            cost_comparison_status=cost_comparison_status,
            objective_status=objective_status,
        )
        plan = ExecutablePlan(
            plan_revision=envelope.plan_revision,
            contract_sha256=envelope.contract_projection.contract_sha256,
            candidate_pool_sha256=snapshot.candidate_pool_sha256,
            retrieval_evidence_sha256=envelope.retrieval_evidence_sha256,
            compiler_input_sha256=effective_compiler_input_sha256,
            dag_edge_contract_sha256s=tuple(
                sorted(
                    edge.edge_contract_sha256
                    for edge in envelope.public_context.incoming_edge_contracts
                )
            ),
            executable_edge_contracts_v2=tuple(
                sorted(
                    executable_edges_v2,
                    key=lambda item: (
                        item.producer_id,
                        item.consumer_id,
                        item.source_output_key,
                        item.target_step_id,
                        item.target_input_port,
                    ),
                )
            ),
            selected_resource_ids=selected_ids,
            resource_usage=tuple(usage_records),
            steps=tuple(normalized_steps),
            final_output=StepOutputRef(
                step_id=draft.final_output.step_id,
                output_key=draft.final_output.output_key,
            ),
            execution_strategy=_execution_strategy(normalized_steps),
            execution_character=_execution_character(normalized_steps, cards),
            objective_evidence=objective,
        )
        audit = PlanValidationAudit(
            candidate_pool_sha256=snapshot.candidate_pool_sha256,
            compiler_input_sha256=effective_compiler_input_sha256,
            draft_sha256=draft.draft_sha256,
            validated_plan_sha256=plan.plan_sha256,
            checks=(
                "identity",
                "candidate_authorization",
                "resource_definition",
                "entrypoint",
                "agent_base_model",
                "dag",
                "binding_sources",
                "binding_contracts",
                "output_schema_authority",
                "runtime_requirements",
                "final_output_contract",
                "dependency_closure",
                "objective_evidence",
            ),
        )
        return plan, audit


class ExecutionPlanLowerer:
    """Lower one validated Plan into immutable ResourceRuntime templates.

    Lowering is intentionally side-effect free.  It validates the declared
    technical entrypoint and preserves typed bindings verbatim; live step
    outputs, runtime paths, scope hashes, argv and environment are completed by
    ResourceRuntime immediately before dispatch.
    """

    def lower(
        self,
        *,
        run_id: str,
        plan: ExecutablePlan,
        envelope: PlanCompilerInputEnvelope,
        resource_definitions: Mapping[str, ResourceDefinition],
        selected_format_contracts: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> tuple[LoweredExecutionPlan, PlanLoweringAudit]:
        if plan.plan_revision != envelope.plan_revision:
            raise PlanFrameworkValidationError("lowering_plan_revision_mismatch")
        if plan.candidate_pool_sha256 != envelope.candidate_pool_snapshot.candidate_pool_sha256:
            raise PlanFrameworkValidationError("lowering_candidate_pool_mismatch")
        candidate_ids = tuple(
            item.resource_id for item in envelope.candidate_pool_snapshot.candidates
        )
        if set(resource_definitions) != set(candidate_ids):
            raise PlanFrameworkValidationError("lowering_resource_definition_set_mismatch")

        context_descriptors_by_source: dict[str, list[Any]] = {}
        for descriptor in envelope.public_context.descriptors:
            context_descriptors_by_source.setdefault(
                descriptor.provenance_source_id, []
            ).append(descriptor)

        templates: list[ResourceCallRequestTemplate] = []
        controller_policy = load_controller_session_policy()
        for step in plan.steps:
            definition = resource_definitions.get(step.resource_id)
            if definition is None:
                raise PlanFrameworkValidationError("lowering_resource_definition_missing")
            if definition.manifest_sha256 != next(
                card.manifest_sha256
                for card in envelope.candidate_cards
                if card.resource_id == step.resource_id
            ):
                raise PlanFrameworkValidationError("lowering_resource_manifest_hash_mismatch")

            resource_application = step.resource_application
            if definition.resource_type in {"Tool", "Resource"}:
                expected_resource_application = _complete_resource_application(
                    step=step,
                    definition=definition,
                    materialized_output=(step.step_id == plan.final_output.step_id
                                         and _declared_primary_file(envelope.contract_projection)),
                )
                if resource_application is None:
                    resource_application = expected_resource_application
                elif (
                    resource_application.application_sha256
                    != expected_resource_application.application_sha256
                ):
                    raise PlanFrameworkValidationError(
                        "lowering_resource_application_identity_changed"
                    )
            if definition.resource_type in {"Tool", "Resource"} and (
                resource_application.output_reachability_proof.compatibility
                not in {"exact", "deterministically_convertible"}
                or resource_application.output_realization_contract is None
            ):
                raise PlanFrameworkValidationError(
                    "lowering_stage_a_output_reachability_not_deterministic"
                )

            controller_session_spec = step.controller_session_spec
            if definition.resource_type in {"Model", "Agent"} and (
                controller_session_spec is not None
            ):
                expected_callable_tools: tuple[ControllerCallableToolSpecV1, ...] = ()
                if isinstance(controller_session_spec, ControllerSessionSpecV2):
                    recomputed: list[ControllerCallableToolSpecV1] = []
                    try:
                        for callable_tool in controller_session_spec.callable_tools:
                            callable_definition = resource_definitions.get(
                                callable_tool.resource_id
                            )
                            if (
                                callable_definition is None
                                or callable_tool.resource_id
                                not in plan.selected_resource_ids
                            ):
                                raise ControllerToolingError(
                                    "controller_callable_resource_not_selected"
                                )
                            expected_tool = derive_controller_callable_tool_spec(
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
                            if (
                                expected_tool.callable_spec_sha256
                                != callable_tool.callable_spec_sha256
                                or expected_tool.provider_tool_schema_sha256
                                != callable_tool.provider_tool_schema_sha256
                            ):
                                raise ControllerToolingError(
                                    "controller_callable_identity_changed"
                                )
                            recomputed.append(expected_tool)
                    except (ControllerToolingError, TypeError, ValueError) as exc:
                        raise PlanFrameworkValidationError(
                            "lowering_controller_callable_tool_identity_changed"
                        ) from exc
                    expected_callable_tools = tuple(recomputed)
                expected_controller_spec = derive_controller_session_spec(
                    subtask_id=plan.plan_revision.subtask_revision.subtask_id,
                    subtask_revision=(
                        plan.plan_revision.subtask_revision.subtask_revision
                    ),
                    controller_step_id=step.step_id,
                    controller_resource_id=step.resource_id,
                    controller_resource_type=step.resource_type,
                    backing_model_resource_id=step.agent_base_model_resource_id,
                    task_instruction=step.intent,
                    declared_input_bindings=step.input_bindings,
                    context_bindings=step.context_bindings,
                    expected_output_contract=(
                        step.expected_output_contract.model_dump(mode="json")
                    ),
                    policy=controller_policy,
                    callable_tools=expected_callable_tools,
                )
                if (
                    controller_session_spec.spec_sha256
                    != expected_controller_spec.spec_sha256
                ):
                    raise PlanFrameworkValidationError(
                        "lowering_controller_session_identity_changed"
                    )
            elif controller_session_spec is not None:
                raise PlanFrameworkValidationError(
                    "lowering_controller_session_identity_changed"
                )

            entrypoint_id: str | None = None
            dispatch_hash: str | None = None
            if definition.resource_type == "Tool":
                if step.entrypoint_id is None:
                    raise PlanFrameworkValidationError("validated_tool_entrypoint_missing")
                try:
                    entrypoint = definition.entrypoint(step.entrypoint_id)
                except Exception as exc:
                    raise PlanFrameworkValidationError(
                        "validated_tool_entrypoint_unresolvable"
                    ) from exc
                entrypoint_id = entrypoint.entrypoint_id
                # Dispatch is framework-private.  The persisted template binds
                # it by hash without exposing a host path or implementation URI.
                dispatch_hash = canonical_sha256(
                    {
                        "resource_id": definition.resource_id,
                        "entrypoint_id": entrypoint.entrypoint_id,
                        "dispatch": entrypoint.dispatch,
                    }
                )

            context = ResourceExecutionContextTemplate(
                run_id=run_id,
                plan_revision=plan.plan_revision,
                candidate_pool_sha256=plan.candidate_pool_sha256,
                candidate_resource_ids=candidate_ids,
                selected_resource_ids=plan.selected_resource_ids,
                plan_sha256=plan.plan_sha256,
                step_id=step.step_id,
            )
            format_enforcement: dict[str, Any] | None = None
            if _structured_output_contract(step.expected_output_contract) and step.resource_type in {
                "Model",
                "Agent",
            }:
                cards = {item.resource_id: item for item in envelope.candidate_cards}
                format_contract = _selected_format_contract(
                    step=step,
                    cards=cards,
                    selected_format_contracts=selected_format_contracts,
                    schema_phase=classify_output_schema_phase(envelope.contract_projection),
                )
                if format_contract is None:
                    raise PlanFrameworkValidationError(
                        "validated_format_contract_missing_during_lowering"
                    )
                modes = tuple(format_contract.get("allowed_enforcement_modes") or ())
                selected_mode = str(
                    format_contract.get("selected_enforcement_mode") or ""
                )
                if not selected_mode:
                    selected_mode = (
                        "native_strict_schema"
                        if "native_strict_schema" in modes
                        else "json_object_local_validator"
                    )
                if selected_mode not in modes or selected_mode not in {
                    "native_strict_schema",
                    "json_object_local_validator",
                }:
                    raise PlanFrameworkValidationError(
                        "validated_format_contract_mode_invalid"
                    )
                format_enforcement = dict(format_contract)
                format_enforcement["selected_enforcement_mode"] = selected_mode
                format_enforcement.pop("format_contract_sha256", None)
                format_enforcement["format_contract_sha256"] = canonical_sha256(
                    format_enforcement
                )
            runtime_context_source_ids: list[str] = []
            for canonical_source_id in step.consumed_context_source_ids:
                matches = context_descriptors_by_source.get(canonical_source_id, [])
                if len(matches) != 1:
                    raise PlanFrameworkValidationError(
                        "lowering_context_source_not_unique"
                    )
                handle_id = str(matches[0].handle_id or "").strip()
                if not handle_id:
                    raise PlanFrameworkValidationError(
                        "lowering_context_runtime_handle_missing"
                    )
                runtime_context_source_ids.append(
                    (
                        handle_id
                        if handle_id.startswith("artifact:")
                        else f"artifact:{handle_id}"
                    )
                )
            templates.append(
                ResourceCallRequestTemplate(
                    step_id=step.step_id,
                    resource_id=step.resource_id,
                    capability_operation_id=step.capability_operation_id,
                    satisfied_obligation_ids=step.satisfied_obligation_ids,
                    resource_type=step.resource_type,
                    resource_manifest_sha256=definition.manifest_sha256,
                    entrypoint_id=entrypoint_id,
                    entrypoint_dispatch_sha256=dispatch_hash,
                    unresolved_typed_bindings=step.input_bindings,
                    consumed_context_source_ids=step.consumed_context_source_ids,
                    runtime_context_handle_ids=tuple(runtime_context_source_ids),
                    edge_contract_sha256s=step.consumed_edge_contract_sha256s,
                    dependency_step_ids=step.depends_on,
                    expected_output_contract=step.expected_output_contract.model_dump(
                        mode="json"
                    ),
                    resource_application=resource_application,
                    controller_session_spec=controller_session_spec,
                    format_enforcement=format_enforcement,
                    advisory_profile_refs=step.advisory_profile_refs,
                    agent_base_model_resource_id=step.agent_base_model_resource_id,
                    execution_network_required=step.execution_network_required,
                    execution_context_template=context,
                )
            )

        audit = PlanLoweringAudit(
            plan_sha256=plan.plan_sha256,
            candidate_pool_sha256=plan.candidate_pool_sha256,
            step_count=len(templates),
            checks=(
                "sealed_plan_identity",
                "candidate_authorization",
                "resource_manifest_identity",
                "entrypoint_dispatch_identity",
                "typed_binding_preservation",
                "resource_native_output_contract_identity",
                "output_reachability_proof_identity",
                "output_realization_contract_identity",
                "controller_session_spec_identity",
                "controller_session_policy_identity",
                "controller_callable_tool_identity",
                "controller_provider_tool_schema_identity",
                "direct_argv_required",
                "shell_forbidden",
                "semantic_hash_preserved",
            ),
        )
        lowered = LoweredExecutionPlan(
            plan_revision=plan.plan_revision,
            plan_sha256=plan.plan_sha256,
            plan_semantic_sha256=plan.plan_sha256,
            candidate_pool_sha256=plan.candidate_pool_sha256,
            dag_edge_contract_sha256s=plan.dag_edge_contract_sha256s,
            selected_resource_ids=plan.selected_resource_ids,
            step_templates=tuple(templates),
            final_output=plan.final_output,
            preflight_audit=audit,
        )
        return lowered, audit


__all__ = [
    "ExecutionPlanLowerer",
    "LoweredExecutionPlan",
    "PlanLoweringAudit",
    "PlanFrameworkValidationError",
    "PlanStructuralValidator",
    "PlanValidationAudit",
    "PlanValidationError",
    "ResourceCallRequestTemplate",
    "ResourceExecutionContextTemplate",
]
