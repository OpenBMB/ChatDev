"""Generic, versioned execution contracts for S-GAR resources.

The runtime exposes a minimal executable surface.  A manifest without explicit
``execution.entrypoints`` receives one generic ``invoke`` entrypoint.  Optional
application profiles remain advisory and never restrict or dispatch calls.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import re
import time
import uuid
from enum import Enum
from typing import Any, Awaitable, Callable, Literal, Mapping, Sequence, cast

from pydantic import Field, field_validator, model_validator, model_serializer

from .binding_protocol import normalize_contract_kind
from .capability_cards import CapabilityCard, build_capability_card
from .execution_events import (
    ExecutionCallHandle,
    ExecutionPersistenceError,
    RunExecutionLedger,
)
from .formal_contracts import MaterialDescriptorV1
from .pipeline_control import FrozenContract, canonical_json_bytes, canonical_sha256
from .output_realization import (
    contract_schema,
    normalized_artifact_type,
    representation_bytes,
    representation_sha256,
)
from .schema import ArtifactHandle
from .path_policy import is_private_host_path_value
from .tool_output_protocol import normalize_tool_process_result


RESOURCE_RUNTIME_PROTOCOL = "sgar-resource-runtime-v1"
RESOURCE_CALL_PROTOCOL = "sgar-resource-invocation-envelope-v2"
CANONICAL_RESULT_PROTOCOL = "sgar-resource-call-result-v2"
EXECUTION_WORLD_PROTOCOL = "sgar-execution-world-v1"
_ENTRYPOINT_ID = re.compile(r"^[a-z][a-z0-9_.-]*$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


# The runtime adapters implemented by the formal orchestration path. This is
# framework evidence, not a union of runtime names found in resource manifests.
RESOURCE_RUNTIME_ADAPTER_MATRIX: dict[str, frozenset[str]] = {
    "Agent": frozenset({"prompt_agent"}),
    "Model": frozenset({"llm_chat_completion"}),
    "Skill": frozenset({"prompt_skill"}),
    "Tool": frozenset(
        {"mcp_server", "python_library", "python_script", "shell_script", "rest_api"}
    ),
}


def runtime_adapter_supported(resource_type: str, runtime_kind: str) -> bool:
    """Return whether Runtime implements this exact resource/dispatch pair."""

    normalized_type = str(resource_type or "").strip()
    normalized_runtime = str(runtime_kind or "").strip()
    return normalized_runtime in RESOURCE_RUNTIME_ADAPTER_MATRIX.get(
        normalized_type, frozenset()
    )


def supported_runtime_kinds(
    resource_types: Sequence[str] | None = None,
) -> tuple[str, ...]:
    """Project implemented runtime kinds for the requested resource types."""

    selected = (
        set(RESOURCE_RUNTIME_ADAPTER_MATRIX)
        if resource_types is None
        else {str(item or "").strip() for item in resource_types}
    )
    return tuple(
        sorted(
            {
                runtime_kind
                for resource_type in selected
                for runtime_kind in RESOURCE_RUNTIME_ADAPTER_MATRIX.get(
                    resource_type, frozenset()
                )
            }
        )
    )


class ResourceRuntimeError(RuntimeError):
    """Base exception for Resource Runtime invariants."""


class ResourceManifestError(ResourceRuntimeError):
    """Raised when a resource manifest cannot define an executable surface."""


class ResourceCallStatus(str, Enum):
    SUCCESS = "success"
    RESEARCH_FAILURE = "research_failure"
    INFRASTRUCTURE_FAILURE = "infrastructure_failure"
    FRAMEWORK_FAILURE = "framework_failure"
    BUDGET_FAILURE = "budget_failure"
    INTERRUPTED = "interrupted"


def _normalized_nonempty(value: Any, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ResourceManifestError(f"{field_name}_empty")
    return text


def _resource_type(manifest: Mapping[str, Any]) -> str:
    nested = manifest.get("type")
    if isinstance(nested, Mapping):
        value = nested.get("resource_type")
    else:
        value = None
    return _normalized_nonempty(
        manifest.get("resource_type") or value,
        field_name="resource_type",
    )


def _sha256(value: str, *, field_name: str) -> str:
    normalized = str(value or "").strip().lower()
    if not _SHA256.fullmatch(normalized):
        raise ValueError(f"{field_name}_must_be_sha256_hex")
    return normalized


def _host_path_locator(value: Any, *, locator: str = "value") -> str | None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            found = _host_path_locator(item, locator=f"{locator}.{key}")
            if found:
                return found
        return None
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found = _host_path_locator(item, locator=f"{locator}[{index}]")
            if found:
                return found
        return None
    if isinstance(value, str) and is_private_host_path_value(value):
        return locator
    return None


class ResourceEntrypoint(FrozenContract):
    protocol: Literal[RESOURCE_RUNTIME_PROTOCOL] = RESOURCE_RUNTIME_PROTOCOL
    entrypoint_id: str
    dispatch: str = Field(min_length=1)
    input_contract: tuple[dict[str, Any], ...] = ()
    output_contract: dict[str, Any] = Field(default_factory=dict)

    @field_validator("entrypoint_id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not _ENTRYPOINT_ID.fullmatch(normalized):
            raise ValueError("entrypoint_id_not_canonical")
        return normalized


class ApplicationProfile(FrozenContract):
    protocol: Literal[RESOURCE_RUNTIME_PROTOCOL] = RESOURCE_RUNTIME_PROTOCOL
    profile_id: str = Field(min_length=1)
    description: str = ""
    structured_preconditions: dict[str, Any] = Field(default_factory=dict)
    binding_hints: dict[str, Any] = Field(default_factory=dict)
    output_hints: dict[str, Any] = Field(default_factory=dict)

    @field_validator("profile_id")
    @classmethod
    def _validate_profile_id(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not _ENTRYPOINT_ID.fullmatch(normalized):
            raise ValueError("application_profile_id_not_canonical")
        return normalized


class ResourceCostProfileV1(FrozenContract):
    """Manifest-backed facts that let the Compiler compare non-Model cost.

    Dollar pricing remains authoritative in ``ModelPricingEvidence``.  This
    profile only exposes execution lower bounds and declared context/utility
    estimates; an unknown value is never converted to zero.
    """

    protocol: Literal["sgar-resource-cost-profile-v1"] = (
        "sgar-resource-cost-profile-v1"
    )
    cost_kind: Literal[
        "model_generation",
        "agent_backing_model_generation",
        "skill_context_injection",
        "deterministic_execution",
        "unknown_non_model",
    ]
    minimum_generation_calls: int | None = Field(default=None, ge=0)
    estimated_context_tokens: int | None = Field(default=None, ge=0)
    manifest_token_cost_factor: float | None = Field(default=None, ge=0)
    declared_latency_ms: float | None = Field(default=None, ge=0)
    evidence_source: Literal["framework_contract", "manifest_declared"]


class ResourceDefinition(FrozenContract):
    protocol: Literal[RESOURCE_RUNTIME_PROTOCOL] = RESOURCE_RUNTIME_PROTOCOL
    resource_id: str = Field(min_length=1)
    resource_type: str = Field(min_length=1)
    manifest_sha256: str = Field(min_length=64, max_length=64)
    status: str = "unknown"
    selection_scope: Literal["candidate", "control_only"] = "candidate"
    entrypoints: tuple[ResourceEntrypoint, ...]
    application_profiles: tuple[ApplicationProfile, ...] = ()
    runtime_requirements: dict[str, Any] = Field(default_factory=dict)
    base_input_contract: tuple[dict[str, Any], ...] = ()
    base_output_contract: dict[str, Any] = Field(default_factory=dict)
    capability_card: CapabilityCard | None = None
    semantic_family_id: str | None = None
    cost_profile: ResourceCostProfileV1 | None = None
    # Advisory resource-level prose; never an executable contract or entrypoint guarantee.
    output_description: str | None = None

    @model_serializer(mode="wrap")
    def _serialize_definition(self, handler):
        payload = handler(self)
        if self.output_description is None:
            payload.pop("output_description", None)
        if self.semantic_family_id is None:
            payload.pop("semantic_family_id", None)
        if self.cost_profile is None:
            payload.pop("cost_profile", None)
        return payload

    @model_validator(mode="after")
    def _validate_unique_ids(self) -> "ResourceDefinition":
        entrypoint_ids = [item.entrypoint_id for item in self.entrypoints]
        if not entrypoint_ids:
            raise ValueError("resource_entrypoints_empty")
        if len(entrypoint_ids) != len(set(entrypoint_ids)):
            raise ValueError("duplicate_entrypoint_id")
        profile_ids = [item.profile_id for item in self.application_profiles]
        if len(profile_ids) != len(set(profile_ids)):
            raise ValueError("duplicate_application_profile_id")
        for label, contract in (
            ("base", self.base_input_contract),
            *(
                (f"entrypoint:{item.entrypoint_id}", item.input_contract)
                for item in self.entrypoints
            ),
        ):
            names: list[str] = []
            for item in contract:
                name = str(item.get("name") or "").strip()
                if not name:
                    raise ValueError(f"resource_input_contract_name_missing:{label}")
                if name in names:
                    raise ValueError(f"resource_input_contract_name_duplicate:{label}")
                names.append(name)
                if not normalize_contract_kind(item):
                    raise ValueError(f"resource_input_contract_kind_missing:{label}")
        return self

    def entrypoint(self, entrypoint_id: str) -> ResourceEntrypoint:
        for entrypoint in self.entrypoints:
            if entrypoint.entrypoint_id == entrypoint_id:
                return entrypoint
        raise ResourceCallValidationError("unknown_resource_entrypoint")

    @classmethod
    def from_manifest(cls, manifest: Mapping[str, Any]) -> "ResourceDefinition":
        if not isinstance(manifest, Mapping):
            raise ResourceManifestError("resource_manifest_not_mapping")
        resource_id = _normalized_nonempty(
            manifest.get("resource_id"),
            field_name="resource_id",
        )
        execution = manifest.get("execution")
        if not isinstance(execution, Mapping):
            raise ResourceManifestError("resource_execution_missing")
        io = manifest.get("io")
        io = io if isinstance(io, Mapping) else {}
        # Capability cards treat nested io contracts as authoritative. Runtime
        # entrypoint cards must project the same ports and output contract.
        base_inputs_raw = (
            io["input_contract"]
            if io.get("input_contract") is not None
            else manifest.get("input_contract") or []
        )
        if not isinstance(base_inputs_raw, (list, tuple)) or not all(
            isinstance(item, Mapping) for item in base_inputs_raw
        ):
            raise ResourceManifestError("resource_input_contract_invalid")
        base_inputs = tuple(dict(item) for item in base_inputs_raw)
        base_output_raw = (
            io["output_contract"]
            if io.get("output_contract") is not None
            else manifest.get("output_contract") or {}
        )
        if not isinstance(base_output_raw, Mapping):
            raise ResourceManifestError("resource_output_contract_invalid")
        base_output = dict(base_output_raw)

        explicit_entrypoints = execution.get("entrypoints")
        entrypoints: list[ResourceEntrypoint] = []
        if explicit_entrypoints is None:
            dispatch = _normalized_nonempty(
                execution.get("uri"),
                field_name="resource_execution_uri",
            )
            entrypoints.append(
                ResourceEntrypoint(
                    entrypoint_id="invoke",
                    dispatch=dispatch,
                    input_contract=base_inputs,
                    output_contract=base_output,
                )
            )
        else:
            if not isinstance(explicit_entrypoints, (list, tuple)) or not explicit_entrypoints:
                raise ResourceManifestError("explicit_entrypoints_invalid")
            for raw in explicit_entrypoints:
                if not isinstance(raw, Mapping):
                    raise ResourceManifestError("explicit_entrypoint_not_mapping")
                if "input_contract" not in raw or "output_contract" not in raw:
                    raise ResourceManifestError("explicit_entrypoint_contract_missing")
                raw_inputs = raw.get("input_contract")
                raw_output = raw.get("output_contract")
                if not isinstance(raw_inputs, (list, tuple)) or not all(
                    isinstance(item, Mapping) for item in raw_inputs
                ):
                    raise ResourceManifestError("explicit_entrypoint_input_contract_invalid")
                if not isinstance(raw_output, Mapping):
                    raise ResourceManifestError("explicit_entrypoint_output_contract_invalid")
                entrypoints.append(
                    ResourceEntrypoint(
                        entrypoint_id=_normalized_nonempty(
                            raw.get("entrypoint_id"), field_name="entrypoint_id"
                        ),
                        dispatch=_normalized_nonempty(
                            raw.get("dispatch"), field_name="entrypoint_dispatch"
                        ),
                        input_contract=tuple(dict(item) for item in raw_inputs),
                        output_contract=dict(raw_output),
                    )
                )

        capability = manifest.get("capability")
        profiles_raw = (
            capability.get("application_profiles")
            if isinstance(capability, Mapping)
            else None
        ) or []
        if not isinstance(profiles_raw, (list, tuple)):
            raise ResourceManifestError("application_profiles_invalid")
        profiles: list[ApplicationProfile] = []
        for raw in profiles_raw:
            if not isinstance(raw, Mapping):
                raise ResourceManifestError("application_profile_not_mapping")
            for field_name in (
                "structured_preconditions",
                "binding_hints",
                "output_hints",
            ):
                field_value = raw.get(field_name) or {}
                if not isinstance(field_value, Mapping):
                    raise ResourceManifestError(
                        f"application_profile_{field_name}_invalid"
                    )
            profiles.append(
                ApplicationProfile(
                    profile_id=_normalized_nonempty(
                        raw.get("profile_id"), field_name="application_profile_id"
                    ),
                    description=str(raw.get("description") or ""),
                    structured_preconditions=dict(raw.get("structured_preconditions") or {}),
                    binding_hints=dict(raw.get("binding_hints") or {}),
                    output_hints=dict(raw.get("output_hints") or {}),
                )
            )
        status = str(
            manifest.get("status")
            or execution.get("execution_status")
            or "unknown"
        )
        runtime_requirements = manifest.get("runtime_requirements") or {}
        if not isinstance(runtime_requirements, Mapping):
            raise ResourceManifestError("runtime_requirements_invalid")
        runtime_requirements = dict(runtime_requirements)
        declared_runtime_kind = str(execution.get("runtime") or "").strip()
        existing_runtime_kind = str(
            runtime_requirements.get("runtime_kind") or ""
        ).strip()
        if (
            declared_runtime_kind
            and existing_runtime_kind
            and declared_runtime_kind != existing_runtime_kind
        ):
            raise ResourceManifestError("resource_runtime_kind_conflict")
        if declared_runtime_kind:
            runtime_requirements["runtime_kind"] = declared_runtime_kind
        resource_type = _resource_type(manifest)
        if resource_type == "Model":
            provenance = manifest.get("provenance")
            provenance = provenance if isinstance(provenance, Mapping) else {}
            reliability = provenance.get("runtime_reliability_evidence")
            if (
                isinstance(reliability, Mapping)
                and str(reliability.get("protocol") or "").strip()
                == "sgar-model-runtime-reliability-v1"
            ):
                short_bounded = reliability.get("short_bounded_response")
                short_bounded = (
                    short_bounded if isinstance(short_bounded, Mapping) else {}
                )
                long_form = reliability.get("long_form_artifact_generation")
                long_form = long_form if isinstance(long_form, Mapping) else {}
                runtime_requirements["sgar_generation_reliability"] = {
                    "protocol": "sgar-model-runtime-reliability-v1",
                    "endpoint_scope": str(
                        reliability.get("endpoint_scope") or ""
                    ).strip(),
                    "evidence_sha256": canonical_sha256(reliability),
                    "short_bounded_response_status": str(
                        short_bounded.get("status") or "unknown"
                    ).strip().casefold(),
                    "long_form_artifact_generation_status": str(
                        long_form.get("status") or "unknown"
                    ).strip().casefold(),
                }
        routing = manifest.get("routing")
        routing = routing if isinstance(routing, Mapping) else {}
        type_specific = manifest.get("type_specific")
        type_specific = type_specific if isinstance(type_specific, Mapping) else {}
        skill_specific = type_specific.get("skill")
        skill_specific = skill_specific if isinstance(skill_specific, Mapping) else {}
        if resource_type == "Skill":
            runtime_requirements["skill_portability"] = str(
                skill_specific.get("portability", "pure_prompt")
            )
        semantic_family_id = str(
            (
                skill_specific.get("canonical_name")
                if resource_type == "Skill"
                else None
            )
            or routing.get("family_id")
            or routing.get("family")
            or ""
        ).strip() or None

        utility = manifest.get("utility")
        utility = utility if isinstance(utility, Mapping) else {}
        capability_mapping = manifest.get("capability")
        capability_mapping = (
            capability_mapping if isinstance(capability_mapping, Mapping) else {}
        )
        execution_semantics = capability_mapping.get("execution_semantics")
        execution_semantics = (
            execution_semantics
            if isinstance(execution_semantics, Mapping)
            else {}
        )
        tool_specific = type_specific.get("tool")
        tool_specific = tool_specific if isinstance(tool_specific, Mapping) else {}
        deterministic_tool = resource_type == "Tool" and bool(
            tool_specific.get("deterministic") is True
            or str(execution_semantics.get("determinism") or "").casefold()
            == "deterministic"
        )
        estimated_context_tokens = (
            skill_specific.get("estimated_context_tokens")
            if resource_type == "Skill"
            else None
        )
        token_cost_factor = utility.get("token_cost_factor")
        latency_ms = utility.get("latency_ms")
        if resource_type == "Model":
            cost_profile = ResourceCostProfileV1(
                cost_kind="model_generation",
                minimum_generation_calls=1,
                evidence_source="framework_contract",
            )
        elif resource_type == "Agent":
            cost_profile = ResourceCostProfileV1(
                cost_kind="agent_backing_model_generation",
                minimum_generation_calls=1,
                manifest_token_cost_factor=token_cost_factor,
                declared_latency_ms=latency_ms,
                evidence_source="framework_contract",
            )
        elif resource_type == "Skill":
            cost_profile = ResourceCostProfileV1(
                cost_kind="skill_context_injection",
                minimum_generation_calls=0,
                estimated_context_tokens=estimated_context_tokens,
                manifest_token_cost_factor=token_cost_factor,
                declared_latency_ms=latency_ms,
                evidence_source="manifest_declared",
            )
        elif deterministic_tool:
            cost_profile = ResourceCostProfileV1(
                cost_kind="deterministic_execution",
                minimum_generation_calls=0,
                manifest_token_cost_factor=token_cost_factor,
                declared_latency_ms=latency_ms,
                evidence_source="manifest_declared",
            )
        else:
            cost_profile = ResourceCostProfileV1(
                cost_kind="unknown_non_model",
                minimum_generation_calls=None,
                manifest_token_cost_factor=token_cost_factor,
                declared_latency_ms=latency_ms,
                evidence_source="manifest_declared",
            )
        return cls(
            resource_id=resource_id,
            resource_type=resource_type,
            manifest_sha256=canonical_sha256(manifest),
            status=status,
            selection_scope=manifest.get("selection_scope", "candidate"),
            entrypoints=tuple(entrypoints),
            application_profiles=tuple(profiles),
            runtime_requirements=runtime_requirements,
            base_input_contract=base_inputs,
            base_output_contract=base_output,
            capability_card=build_capability_card(manifest),
            semantic_family_id=semantic_family_id,
            cost_profile=cost_profile,
            output_description=(
                manifest["constraint"]["output_shape"]
                if isinstance(manifest.get("constraint"), Mapping)
                and isinstance(manifest["constraint"].get("output_shape"), str)
                and manifest["constraint"]["output_shape"].strip()
                else None
            ),
        )


class ResourceExecutionContext(FrozenContract):
    protocol: Literal[RESOURCE_CALL_PROTOCOL] = RESOURCE_CALL_PROTOCOL
    identity_status: Literal["formal", "legacy_unbound"] = "formal"
    run_id: str = Field(min_length=1)
    graph_revision: int = Field(ge=0)
    subtask_id: str = Field(min_length=1)
    subtask_revision: int = Field(ge=0)
    candidate_pool_sha256: str = Field(min_length=64, max_length=64)
    candidate_resource_ids: tuple[str, ...]
    selected_resource_ids: tuple[str, ...]
    plan_sha256: str = Field(min_length=64, max_length=64)
    step_id: str = Field(min_length=1)
    attempt: int = Field(default=1, ge=1)
    parent_operation_id: str | None = None
    sandbox_scope_sha256: str = Field(min_length=64, max_length=64)

    @field_validator(
        "candidate_pool_sha256",
        "plan_sha256",
        "sandbox_scope_sha256",
    )
    @classmethod
    def _validate_hashes(cls, value: str, info: Any) -> str:
        return _sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _validate_authorization(self) -> "ResourceExecutionContext":
        if len(self.candidate_resource_ids) != len(set(self.candidate_resource_ids)):
            raise ValueError("candidate_resource_ids_not_unique")
        if len(self.selected_resource_ids) != len(set(self.selected_resource_ids)):
            raise ValueError("selected_resource_ids_not_unique")
        if not set(self.selected_resource_ids).issubset(self.candidate_resource_ids):
            raise ValueError("selected_resources_not_in_candidate_pool")
        if self.identity_status == "formal" and not self.candidate_resource_ids:
            raise ValueError("formal_candidate_pool_empty")
        return self

    @classmethod
    def legacy(
        cls,
        *,
        run_id: str,
        subtask_id: str,
        step_id: str,
        selected_resource_ids: Sequence[str],
        plan_sha256: str,
        sandbox_scope_sha256: str,
    ) -> "ResourceExecutionContext":
        selected = tuple(dict.fromkeys(str(item) for item in selected_resource_ids))
        return cls(
            identity_status="legacy_unbound",
            run_id=run_id,
            graph_revision=0,
            subtask_id=subtask_id,
            subtask_revision=0,
            candidate_pool_sha256=canonical_sha256({"legacy_selected": selected}),
            candidate_resource_ids=selected,
            selected_resource_ids=selected,
            plan_sha256=plan_sha256,
            step_id=step_id,
            sandbox_scope_sha256=sandbox_scope_sha256,
        )


class ExecutionWorldDescriptor(FrozenContract):
    protocol: Literal[EXECUTION_WORLD_PROTOCOL] = EXECUTION_WORLD_PROTOCOL
    runtime_image_id: str = ""
    runtime_kind: str = "unknown"
    runtime_roots: tuple[dict[str, Any], ...] = ()
    writable_root_runtime_path: str = ""
    working_directory: str = ""
    public_input_descriptors: tuple[dict[str, Any], ...] = ()
    environment_sha256: str = Field(min_length=64, max_length=64)
    dependency_lock_sha256: str = Field(min_length=64, max_length=64)
    runtime_request_sha256: str = Field(min_length=64, max_length=64)
    sandbox_scope_sha256: str = Field(min_length=64, max_length=64)
    network_required: bool = False
    direct_argv: bool = True

    @field_validator(
        "environment_sha256",
        "dependency_lock_sha256",
        "runtime_request_sha256",
        "sandbox_scope_sha256",
    )
    @classmethod
    def _validate_hashes(cls, value: str, info: Any) -> str:
        return _sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _validate_public_projection(self) -> "ExecutionWorldDescriptor":
        locator = _host_path_locator(self.model_dump(mode="python"))
        if locator:
            raise ValueError(f"execution_world_contains_host_path:{locator}")
        if not self.direct_argv:
            raise ValueError("resource_runtime_requires_direct_argv")
        return self

    @property
    def execution_world_sha256(self) -> str:
        return canonical_sha256(self)


class ResourceCallValidationError(ResourceRuntimeError):
    """Raised when a Plan requests a call outside the declared surface."""


class ResourceCallRequest(FrozenContract):
    protocol: Literal[RESOURCE_CALL_PROTOCOL] = RESOURCE_CALL_PROTOCOL
    call_id: str = Field(default_factory=lambda: uuid.uuid4().hex, min_length=1)
    resource_definition: ResourceDefinition
    entrypoint_id: str = "invoke"
    execution_context: ResourceExecutionContext
    resolved_bindings: dict[str, Any] = Field(default_factory=dict)
    capability_operation_id: str = Field(min_length=1)
    semantic_task_contract: dict[str, Any]
    authorized_materials: tuple[MaterialDescriptorV1, ...] = ()
    authorized_material_content: dict[str, str] = Field(default_factory=dict)
    upstream_artifact_handles: tuple[ArtifactHandle, ...] = ()
    advisory_materials: tuple[dict[str, Any], ...] = ()
    acceptance_requirements: tuple[str, ...]
    execution_world: ExecutionWorldDescriptor
    resource_native_output_contract: dict[str, Any] = Field(default_factory=dict)
    target_output_contract: dict[str, Any] = Field(default_factory=dict)
    provenance_source_ids: tuple[str, ...] = ()
    dag_edge_contract_sha256s: tuple[str, ...] = ()
    advisory_profile_refs: tuple[str, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def _upgrade_output_contract_alias(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        projected = dict(value)
        legacy = projected.pop("output_contract", None)
        if "resource_native_output_contract" not in projected and legacy is not None:
            definition = projected.get("resource_definition")
            entrypoint_id = str(projected.get("entrypoint_id") or "invoke")
            if isinstance(definition, ResourceDefinition):
                projected["resource_native_output_contract"] = dict(
                    definition.entrypoint(entrypoint_id).output_contract
                )
            elif isinstance(definition, Mapping):
                parsed_definition = ResourceDefinition.model_validate(definition)
                projected["resource_native_output_contract"] = dict(
                    parsed_definition.entrypoint(entrypoint_id).output_contract
                )
            else:
                projected["resource_native_output_contract"] = legacy
        if "target_output_contract" not in projected and legacy is not None:
            projected["target_output_contract"] = legacy
        return projected

    @model_validator(mode="after")
    def _validate_request(self) -> "ResourceCallRequest":
        if self.resource_definition.resource_id not in self.execution_context.selected_resource_ids:
            raise ValueError("resource_not_selected")
        entrypoint = self.resource_definition.entrypoint(self.entrypoint_id)
        if (
            self.execution_context.sandbox_scope_sha256
            != self.execution_world.sandbox_scope_sha256
        ):
            raise ValueError("execution_context_scope_mismatch")
        if self.execution_context.identity_status == "formal" and not self.resource_native_output_contract:
            raise ValueError("formal_resource_output_contract_missing")
        if self.execution_context.identity_status == "formal" and canonical_sha256(
            self.resource_native_output_contract
        ) != canonical_sha256(entrypoint.output_contract):
            raise ValueError("formal_resource_native_output_contract_mismatch")
        if self.execution_context.identity_status == "formal":
            if not self.semantic_task_contract:
                raise ValueError("formal_resource_semantic_task_contract_missing")
            if not self.acceptance_requirements:
                raise ValueError("formal_resource_acceptance_requirements_missing")
            card = self.resource_definition.capability_card
            operations = {
                item.capability_operation_id: item
                for item in (card.capability_operations if card is not None else ())
            }
            operation = operations.get(self.capability_operation_id)
            if operation is None:
                raise ValueError("formal_resource_capability_operation_missing")
            if operation.entrypoint_id not in {None, self.entrypoint_id}:
                raise ValueError("formal_resource_capability_entrypoint_mismatch")
        if self.resource_definition.resource_type == "Tool":
            declared = {
                str(item.get("name") or "").strip(): item
                for item in entrypoint.input_contract
            }
            missing = sorted(
                name
                for name, item in declared.items()
                if bool(item.get("required", True))
                and name not in self.resolved_bindings
            )
            if missing:
                raise ValueError("resource_required_binding_missing")
            if set(self.resolved_bindings) - set(declared):
                raise ValueError("resource_undeclared_binding_name")
            for name, value in self.resolved_bindings.items():
                kind = normalize_contract_kind(declared[name])
                compatible = True
                if kind == "list":
                    compatible = isinstance(value, (list, tuple))
                elif kind == "int":
                    compatible = isinstance(value, int) and not isinstance(value, bool)
                elif kind == "float":
                    compatible = isinstance(value, (int, float)) and not isinstance(
                        value, bool
                    )
                elif kind == "bool":
                    compatible = isinstance(value, bool)
                elif kind in {"object", "json"}:
                    compatible = isinstance(value, Mapping)
                elif kind in {"path", "file_path", "directory_path", "text"}:
                    compatible = isinstance(value, str)
                if not compatible:
                    raise ValueError("resource_binding_contract_mismatch")
        if len(self.provenance_source_ids) != len(set(self.provenance_source_ids)):
            raise ValueError("resource_provenance_source_duplicate")
        material_source_ids = tuple(item.source_id for item in self.authorized_materials)
        if len(material_source_ids) != len(set(material_source_ids)):
            raise ValueError("resource_authorized_material_source_duplicate")
        if set(material_source_ids) - set(self.provenance_source_ids):
            raise ValueError("resource_authorized_material_not_in_provenance")
        content_source_ids = set(self.authorized_material_content)
        if content_source_ids - set(material_source_ids):
            raise ValueError("resource_authorized_material_content_undeclared")
        for item in self.authorized_materials:
            content = self.authorized_material_content.get(item.source_id)
            if content is None:
                if item.coverage_status != "handle_only":
                    raise ValueError("resource_authorized_material_content_missing")
                continue
            content_bytes = content.encode("utf-8")
            if item.coverage_status != "complete":
                raise ValueError("resource_authorized_material_content_not_complete")
            if len(content_bytes) != item.original_bytes:
                raise ValueError("resource_authorized_material_content_size_mismatch")
            if hashlib.sha256(content_bytes).hexdigest() != item.content_sha256:
                raise ValueError("resource_authorized_material_content_hash_mismatch")
        upstream_handle_ids = {item.handle_id for item in self.upstream_artifact_handles}
        material_handle_ids = {
            str(item.handle_id)
            for item in self.authorized_materials
            if item.handle_id is not None
        }
        if upstream_handle_ids != material_handle_ids:
            raise ValueError("resource_authorized_material_handle_mismatch")
        if len(self.dag_edge_contract_sha256s) != len(
            set(self.dag_edge_contract_sha256s)
        ):
            raise ValueError("resource_dag_edge_contract_duplicate")
        for value in self.dag_edge_contract_sha256s:
            _sha256(value, field_name="dag_edge_contract_sha256")
        provider_projection = {
            "semantic_task_contract": self.semantic_task_contract,
            "typed_inputs": self.resolved_bindings,
            "authorized_materials": [
                item.model_dump(mode="json") for item in self.authorized_materials
            ],
            "authorized_material_content": self.authorized_material_content,
            "advisory_materials": self.advisory_materials,
            "resource_native_output_contract": self.resource_native_output_contract,
            "target_output_contract": self.target_output_contract,
            "acceptance_requirements": self.acceptance_requirements,
        }
        locator = _host_path_locator(provider_projection)
        if locator:
            raise ValueError(f"resource_provider_projection_contains_host_path:{locator}")
        return self

    def model_visible_payload(self) -> dict[str, Any]:
        """The sole provider-visible projection; no host/runtime closure data."""

        return {
            "protocol": self.protocol,
            "identity": {
                "run_id": self.execution_context.run_id,
                "plan_sha256": self.execution_context.plan_sha256,
                "step_id": self.execution_context.step_id,
                "request_sha256": self.request_sha256,
            },
            "semantic_task_contract": self.semantic_task_contract,
            "selected_operation": {
                "resource_id": self.resource_definition.resource_id,
                "capability_operation_id": self.capability_operation_id,
                "entrypoint_id": self.entrypoint_id,
            },
            "typed_inputs": self.resolved_bindings,
            "authorized_materials": [
                item.model_dump(mode="json") for item in self.authorized_materials
            ],
            "authorized_material_content": self.authorized_material_content,
            "upstream_artifact_handles": [
                item.model_dump(mode="json", exclude={"host_path"})
                for item in self.upstream_artifact_handles
            ],
            "advisory_materials": self.advisory_materials,
            "resource_native_output_contract": self.resource_native_output_contract,
            "target_output_contract": self.target_output_contract,
            "acceptance_requirements": self.acceptance_requirements,
            "provenance_source_ids": self.provenance_source_ids,
        }

    @property
    def request_sha256(self) -> str:
        return canonical_sha256(self)

    @property
    def output_contract(self) -> dict[str, Any]:
        """Compatibility accessor for providers; always the Resource-native contract."""

        return self.resource_native_output_contract


class ResourceFailure(FrozenContract):
    protocol: Literal[CANONICAL_RESULT_PROTOCOL] = CANONICAL_RESULT_PROTOCOL
    responsibility: Literal["framework", "infrastructure", "research", "budget"]
    failure_stage: str = Field(min_length=1)
    failure_code: str = Field(min_length=1)
    exception_type: str = ""
    retryable: bool = False
    response_received: bool = False
    message_sha256: str = Field(min_length=64, max_length=64)

    @classmethod
    def create(
        cls,
        *,
        responsibility: str,
        failure_stage: str,
        failure_code: str,
        error: BaseException | None = None,
        retryable: bool = False,
        response_received: bool = False,
    ) -> "ResourceFailure":
        return cls(
            responsibility=responsibility,
            failure_stage=failure_stage,
            failure_code=failure_code,
            exception_type=type(error).__name__ if error is not None else "",
            retryable=retryable,
            response_received=response_received,
            message_sha256=canonical_sha256(
                {
                    "failure_code": failure_code,
                    "exception_type": type(error).__name__ if error is not None else "",
                }
            ),
        )


class ProcessFailureDiagnostic(FrozenContract):
    """Bounded observed process diagnostics, never a success view."""

    protocol: Literal["sgar-process-failure-diagnostic-v1"] = "sgar-process-failure-diagnostic-v1"
    return_code: int
    stderr: str = ""
    stdout: str | None = None
    diagnostic_sha256: str = ""

    @model_serializer(mode="wrap")
    def _serialize_streams(self, handler: Any) -> dict[str, Any]:
        result = handler(self)
        if self.stdout is None:
            result.pop("stdout", None)
        return result

    @model_validator(mode="after")
    def _seal(self) -> "ProcessFailureDiagnostic":
        if (self.return_code == 0 or not (self.stderr or self.stdout)
                or any(len(value.encode("utf-8")) > 8192 for value in (self.stderr, self.stdout or ""))):
            raise ValueError("process_failure_diagnostic_invalid")
        projection = {"return_code": self.return_code, "stderr": self.stderr}
        if self.stdout is not None:
            projection["stdout"] = self.stdout
        expected = canonical_sha256(projection)
        if self.diagnostic_sha256 and self.diagnostic_sha256 != expected:
            raise ValueError("process_failure_diagnostic_identity_mismatch")
        object.__setattr__(self, "diagnostic_sha256", expected)
        return self


class ResourceCallResult(FrozenContract):
    protocol: Literal[CANONICAL_RESULT_PROTOCOL] = CANONICAL_RESULT_PROTOCOL
    call_id: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    entrypoint_id: str = Field(min_length=1)
    status: ResourceCallStatus
    native_value: Any = None
    native_content: str = ""
    native_output_sha256: str = ""
    native_output_bytes: int = Field(default=0, ge=0)
    semantic_view_available: bool = False
    semantic_value: Any = None
    semantic_content: str = ""
    semantic_output_sha256: str | None = None
    semantic_output_bytes: int = Field(default=0, ge=0)
    canonical_value: Any = None
    presentation: str = ""
    artifacts: tuple[ArtifactHandle, ...] = ()
    failure: ResourceFailure | None = None
    process_diagnostic: ProcessFailureDiagnostic | None = None
    usage_reference: str | None = None
    execution_audit: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    output_contract_status: str = "not_checked"
    started_event_id: str | None = None
    terminal_event_id: str | None = None
    request_sha256: str = ""
    canonical_content_sha256: str = ""
    result_type: str = "unknown"

    @model_validator(mode="after")
    def _validate_failure_status(self) -> "ResourceCallResult":
        if self.status == ResourceCallStatus.SUCCESS and self.failure is not None:
            raise ValueError("successful_resource_result_has_failure")
        if self.status != ResourceCallStatus.SUCCESS and self.failure is None and self.status != ResourceCallStatus.INTERRUPTED:
            raise ValueError("failed_resource_result_missing_failure")
        for field_name in (
            "request_sha256",
            "canonical_content_sha256",
            "native_output_sha256",
            "semantic_output_sha256",
        ):
            value = getattr(self, field_name)
            if value:
                _sha256(value, field_name=field_name)
        if self.semantic_view_available != (self.semantic_output_sha256 is not None):
            raise ValueError("semantic_resource_result_identity_incomplete")
        return self

    def public_projection(self) -> dict[str, Any]:
        artifacts = []
        for handle in self.artifacts:
            artifacts.append(
                {
                    "handle_id": handle.handle_id,
                    "kind": handle.kind,
                    "producer_task": handle.producer_task,
                    "producer_step": handle.producer_step,
                    "logical_path": handle.logical_path,
                    "tool_path": handle.tool_path,
                    "artifact_type": handle.artifact_type,
                    "validation_status": handle.validation_status,
                    "current_run": handle.current_run,
                }
            )
        payload = self.model_dump(
            mode="json",
            exclude={
                "artifacts",
                "canonical_value",
                "presentation",
                "native_value",
                "native_content",
                "semantic_value",
                "semantic_content",
            },
        )
        payload["canonical_value_sha256"] = canonical_sha256(self.canonical_value)
        payload["presentation_sha256"] = canonical_sha256(self.presentation)
        payload["artifacts"] = artifacts
        locator = _host_path_locator(payload)
        if locator:
            raise ResourceRuntimeError(f"resource_result_projection_contains_host_path:{locator}")
        return payload

    @property
    def result_sha256(self) -> str:
        projection = self.public_projection()
        projection.pop("started_event_id", None)
        projection.pop("terminal_event_id", None)
        return canonical_sha256(projection)


def _presentation_for_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return canonical_json_bytes(value).decode("utf-8")


def validated_declared_failure_payload(
    result: ResourceCallResult, native_output_contract: Mapping[str, Any],
) -> Any | None:
    """Read a declared business failure without turning it into successful output.

    Both static recovery and Controller continuation use this boundary. A raw
    exception, invalid schema, or changed native content cannot become model
    diagnostic material merely because it has an error-looking field.
    """
    failure = result.failure
    declaration = native_output_contract.get("result_status")
    if not (
        result.status == ResourceCallStatus.RESEARCH_FAILURE
        and result.output_contract_status == "failed"
        and failure is not None
        and failure.responsibility == "research"
        and failure.failure_stage == "resource_native_output_contract"
        and failure.failure_code == "declared_result_status_failure"
        and failure.response_received
        and isinstance(declaration, Mapping)
        and declaration.get("payload_path")
        and declaration.get("failure_values")
        and normalized_artifact_type(native_output_contract.get("artifact_type")) == "json"
    ):
        return None
    from .model_response_contracts import validate_json_schema_instance

    try:
        payload = json.loads(result.native_content)
        schema = contract_schema(native_output_contract)
        if not schema or not validate_json_schema_instance(payload, schema)[0]:
            return None
        if representation_sha256(result.native_content, "json") != result.native_output_sha256:
            return None
        normalized = normalize_tool_process_result(
            0, result.native_content, "", {"output_contract": dict(native_output_contract)}
        )
        if normalized.wrapper_reason != "declared_result_status_failure":
            return None
    except (TypeError, ValueError):
        return None
    return payload


def validated_process_failure_diagnostic(result: ResourceCallResult) -> dict[str, Any] | None:
    """Revalidate process evidence at the model boundary, including copied data."""
    failure = result.failure
    diagnostic = result.process_diagnostic
    if not (
        result.status == ResourceCallStatus.RESEARCH_FAILURE
        and failure is not None and failure.responsibility == "research"
        and failure.failure_stage == "resource_execution"
        and failure.failure_code == "resource_process_failed"
        and diagnostic is not None
    ):
        return None
    try:
        checked = ProcessFailureDiagnostic.model_validate(diagnostic.model_dump(mode="python"))
    except (TypeError, ValueError):
        return None
    return checked.model_dump(mode="json")


def resource_result_to_execution_result(
    result: ResourceCallResult,
    *,
    realization_result: Any = None,
    native_output_contract: Mapping[str, Any] | None = None,
) -> Any:
    """Project a canonical result onto the legacy executor boundary."""

    from .executors import ExecutionResult

    failure = result.failure
    audit = dict(result.execution_audit)
    legacy_projection = audit.pop("legacy_metric_projection", {})
    metrics = {
        "resource_id": result.resource_id,
        "entrypoint_id": result.entrypoint_id,
        "resource_call_reference": {
            "protocol": result.protocol,
            "call_id": result.call_id,
            "result_sha256": result.result_sha256,
            "request_sha256": result.request_sha256 or None,
            "started_event_id": result.started_event_id,
            "terminal_event_id": result.terminal_event_id,
        },
        "execution_audit": audit,
        "provenance": dict(result.provenance),
    }
    if isinstance(legacy_projection, Mapping):
        metrics.update(dict(legacy_projection))
    if result.usage_reference:
        # Keep one canonical accounting join at the compatibility boundary.
        # This is a reference only: the Resource Runtime never bills the model.
        metrics["usage_reference"] = result.usage_reference
    if failure is not None:
        metrics.update(
            {
                "failure_type": failure.failure_code,
                "failure_layer": failure.responsibility,
                "failure": failure.model_dump(mode="json"),
            }
        )
    if realization_result is not None:
        metrics["output_realization_reference"] = {
            "protocol": realization_result.protocol,
            "realization_id": realization_result.realization_id,
            "result_sha256": realization_result.result_sha256,
            "contract_sha256": (
                realization_result.provenance.output_realization_contract_sha256
                if realization_result.provenance is not None
                else None
            ),
        }
        metrics["output_realization_metrics"] = (
            realization_result.metrics.model_dump(mode="json")
        )
        if realization_result.provenance is not None:
            metrics["provenance"] = realization_result.provenance.model_dump(
                mode="json"
            )
        if realization_result.status != "success":
            metrics.update(
                {
                    "failure_type": realization_result.failure_code,
                    "failure_layer": "research",
                    "failure": {
                        "responsibility": "research",
                        "failure_stage": "output_realization",
                        "failure_code": realization_result.failure_code,
                        "retryable": False,
                        "response_received": True,
                    },
                }
            )
            return ExecutionResult(
                is_success=False,
                output_data="",
                error_log=realization_result.failure_code,
                cost_metric=metrics,
            )
    error_log = failure.failure_code if failure is not None else None
    process_diagnostic = validated_process_failure_diagnostic(result)
    if process_diagnostic is not None:
        error_log = canonical_json_bytes({
            "failure_code": failure.failure_code,
            "process_diagnostic": process_diagnostic,
        }).decode("utf-8")
    if failure is not None and native_output_contract is not None:
        diagnostic = validated_declared_failure_payload(result, native_output_contract)
        if diagnostic is not None:
            # Ephemeral diagnostic data is bounded/redacted when the recovery
            # snapshot is built. The ledger still records hashes and failure
            # identity, and failed data is never checkpointed as successful.
            error_log = canonical_json_bytes({
                "failure_code": failure.failure_code,
                "native_result": diagnostic,
            }).decode("utf-8")
    return ExecutionResult(
        is_success=result.status == ResourceCallStatus.SUCCESS,
        output_data=(
            realization_result.presentation
            if realization_result is not None
            else result.presentation
            if result.presentation
            else ""
            if result.canonical_value is None
            else _presentation_for_value(result.canonical_value)
        ),
        error_log=error_log,
        cost_metric=metrics,
    )


def execution_result_to_resource_result(
    result: Any,
    *,
    call_id: str,
    resource_id: str,
    entrypoint_id: str = "invoke",
    output_contract: Mapping[str, Any] | None = None,
    provider_result_source: str = "legacy_adapter",
    require_structured_failure: bool = False,
) -> ResourceCallResult:
    """Adapt an existing executor result without rerunning or reinterpreting it."""

    metrics = dict(getattr(result, "cost_metric", {}) or {})
    structured = metrics.get("failure")
    failure = None
    status = ResourceCallStatus.SUCCESS
    if not bool(getattr(result, "is_success", False)):
        if require_structured_failure and not isinstance(structured, Mapping):
            status = ResourceCallStatus.FRAMEWORK_FAILURE
            failure = ResourceFailure.create(
                responsibility="framework",
                failure_stage="provider_contract",
                failure_code="provider_failure_contract_missing",
                response_received=False,
            )
        else:
            responsibility = (
                structured.get("responsibility")
                if isinstance(structured, Mapping)
                else metrics.get("failure_layer")
            )
            responsibility = str(responsibility or "research")
            if responsibility not in {"framework", "infrastructure", "research", "budget"}:
                responsibility = "research"
            status = ResourceCallStatus(f"{responsibility}_failure")
            failure = ResourceFailure.create(
                responsibility=responsibility,
                failure_stage=str(
                    (
                        structured.get("failure_stage")
                        if isinstance(structured, Mapping)
                        else None
                    )
                    or "execution"
                ),
                failure_code=str(
                    (
                        structured.get("failure_code")
                        if isinstance(structured, Mapping)
                        else None
                    )
                    or metrics.get("failure_type")
                    or "legacy_execution_failed"
                ),
                retryable=bool(structured.get("retryable", False)) if isinstance(structured, Mapping) else False,
                response_received=bool(structured.get("response_received", False)) if isinstance(structured, Mapping) else False,
            )
    output = str(getattr(result, "output_data", "") or "")
    safe_metric_names = {
        "agent_id",
        "attempt_count",
        "base_model",
        "cost_usd",
        "entrypoint_id",
        "execution_world_sha256",
        "latency_ms",
        "model",
        "model_accounting_reference",
        "model_media_projection",
        "network_required",
        "prompt_only_json",
        "resource_runtime_protocol",
        "runtime_environment_hash",
        "runtime_image_id",
        "runtime_kind",
        "runtime_lock_hash",
        "runtime_request_hash",
        "sandbox_scope_hash",
        "semantic_normalization_applied",
        "temperature_control",
        "temperature_requested",
        "token_usage",
        "tool_execution_provider_protocol",
        "transport_audit",
    }
    legacy_projection = {
        key: metrics[key]
        for key in safe_metric_names
        if key in metrics
    }
    execution_audit = {
        "provider_result_source": provider_result_source,
        **(
            dict(metrics.get("execution_audit"))
            if isinstance(metrics.get("execution_audit"), Mapping)
            else {}
        ),
    }
    if failure is not None:
        execution_audit.setdefault("failure_origin", failure.failure_stage)
        execution_audit.setdefault(
            "stack_fingerprint_sha256",
            canonical_sha256(
                {
                    "failure_origin": failure.failure_stage,
                    "failure_code": failure.failure_code,
                    "exception_type": failure.exception_type,
                }
            ),
        )
    if legacy_projection:
        execution_audit["legacy_metric_projection"] = legacy_projection
    accounting_reference = metrics.get("model_accounting_reference")
    usage_reference = (
        str(accounting_reference.get("operation_id"))
        if isinstance(accounting_reference, Mapping)
        and accounting_reference.get("operation_id")
        else None
    )
    process_diagnostic = None
    return_code = metrics.get("return_code")
    if (
        failure is not None and failure.responsibility == "research"
        and failure.failure_stage == "resource_execution"
        and failure.failure_code == "resource_process_failed"
        and type(return_code) is int and return_code != 0
    ):
        # Classification comes only from structured provider/exit evidence.
        # Diagnostics are sanitized data; no exception text becomes authority.
        from .recovery_runtime import sanitize_recovery_diagnostic
        from .secret_policy import sanitize_sensitive_text

        diagnostic_text, _ = sanitize_sensitive_text(str(getattr(result, "error_log", "") or ""))
        diagnostic_text, _ = sanitize_recovery_diagnostic(diagnostic_text)
        diagnostic_stdout, _ = sanitize_sensitive_text(output)
        diagnostic_stdout, _ = sanitize_recovery_diagnostic(diagnostic_stdout)
        if diagnostic_text or diagnostic_stdout:
            process_diagnostic = ProcessFailureDiagnostic(
                return_code=return_code, stderr=diagnostic_text,
                stdout=diagnostic_stdout or None,
            )
        # Failure streams belong to the diagnostic, never the native success view.
        output = ""
    return ResourceCallResult(
        call_id=call_id,
        resource_id=resource_id,
        entrypoint_id=entrypoint_id,
        status=status,
        canonical_value=output,
        presentation=output,
        failure=failure,
        process_diagnostic=process_diagnostic,
        usage_reference=usage_reference,
        execution_audit=execution_audit,
        provenance=dict(metrics.get("provenance")) if isinstance(metrics.get("provenance"), Mapping) else {},
        output_contract_status="provider_reported" if output_contract else "not_checked",
    )


ProviderCallable = Callable[[ResourceCallRequest], Awaitable[Any] | Any]


class ResourceRuntime:
    """Validate, dispatch, normalize, and account for one generic resource call."""

    def __init__(
        self,
        *,
        ledger: RunExecutionLedger,
        provider: ProviderCallable | None = None,
    ) -> None:
        self.ledger = ledger
        self.provider = provider
        self.halted = False

    @staticmethod
    def _secondary_audit_failure(
        *,
        failure_origin: str,
        failure_code: str,
        error: BaseException,
    ) -> dict[str, Any]:
        return {
            "responsibility": "framework",
            "failure_origin": str(failure_origin),
            "failure_code": str(failure_code),
            "stack_fingerprint_sha256": canonical_sha256(
                {
                    "failure_origin": str(failure_origin),
                    "failure_code": str(failure_code),
                    "exception_type": type(error).__name__,
                }
            ),
        }

    @classmethod
    def _append_secondary_audit_failure(
        cls,
        result: ResourceCallResult,
        *,
        failure_origin: str,
        failure_code: str,
        error: BaseException,
    ) -> ResourceCallResult:
        audit = dict(result.execution_audit)
        failures = list(audit.get("secondary_audit_failures") or [])
        failures.append(
            cls._secondary_audit_failure(
                failure_origin=failure_origin,
                failure_code=failure_code,
                error=error,
            )
        )
        audit["secondary_audit_failures"] = failures
        return result.model_copy(update={"execution_audit": audit})

    @staticmethod
    def _runtime_kind(request: ResourceCallRequest) -> str:
        return str(request.execution_world.runtime_kind or "unknown")

    @staticmethod
    def _canonicalize_success(
        result: ResourceCallResult,
        output_contract: Mapping[str, Any],
    ) -> ResourceCallResult:
        if result.status != ResourceCallStatus.SUCCESS:
            return result
        native_type = normalized_artifact_type(output_contract.get("artifact_type"))
        native_value = result.canonical_value
        native_content = result.presentation
        if native_value is None and native_content:
            native_value = native_content
        if not native_content and native_value is not None:
            native_content = _presentation_for_value(native_value)

        def failed(
            *,
            responsibility: Literal["framework", "research"],
            failure_code: str,
            error: BaseException | None = None,
            reason: str | None = None,
        ) -> ResourceCallResult:
            audit = dict(result.execution_audit)
            if reason:
                audit["output_schema_failure_sha256"] = canonical_sha256(reason)
            return result.model_copy(
                update={
                    "status": ResourceCallStatus(f"{responsibility}_failure"),
                    "failure": ResourceFailure.create(
                        responsibility=responsibility,
                        failure_stage="resource_native_output_contract",
                        failure_code=failure_code,
                        error=error,
                        response_received=True,
                    ),
                    "native_content": native_content,
                    "native_output_sha256": representation_sha256(
                        native_content, native_type or "plaintext"
                    ),
                    "native_output_bytes": len(native_content.encode("utf-8")),
                    "execution_audit": audit,
                    "output_contract_status": "failed",
                }
            )

        from .json_serialization import json_serialization_format, parse_json_content
        jsonl_native = native_type == "json" and json_serialization_format(output_contract) == "jsonl"
        if jsonl_native:
            from .artifact_semantics import validate_output_contract_content, OutputContractViolation
            try:
                validate_output_contract_content(native_content.encode("utf-8"), output_contract)
                native_value = parse_json_content(native_content, serialization_format="jsonl",
                                                 schema=contract_schema(output_contract))
            except (OutputContractViolation, ValueError) as exc:
                return failed(responsibility="research", failure_code="resource_output_jsonl_invalid", error=exc)
        elif native_type == "json" and isinstance(native_value, str):
            try:
                native_value = json.loads(native_content or native_value)
            except json.JSONDecodeError as exc:
                return failed(
                    responsibility="research",
                    failure_code="tool_output_json_invalid",
                    error=exc,
                )

        native_schema = contract_schema(output_contract)
        semantic_declared = isinstance(output_contract.get("semantic_output"), Mapping)
        status_declared = isinstance(output_contract.get("result_status"), Mapping)
        if native_type == "json" and native_schema is None and not (
            semantic_declared or status_declared
        ):
            return failed(
                responsibility="framework",
                failure_code="resource_output_json_schema_missing",
            )
        if native_type == "json" and native_schema is not None and not jsonl_native:
            try:
                from .model_response_contracts import (
                    require_semantic_json_schema,
                    validate_json_schema_instance,
                )

                from .native_output_contracts import require_native_json_schema
                canonical_schema = require_native_json_schema(output_contract, native_schema)
                valid, reason = validate_json_schema_instance(
                    native_value,
                    canonical_schema,
                )
            except Exception as exc:
                return failed(
                    responsibility="framework",
                    failure_code="resource_output_json_schema_invalid",
                    error=exc,
                )
            if not valid:
                return failed(
                    responsibility="research",
                    failure_code="resource_output_json_schema_mismatch",
                    reason=reason,
                )

        normalized = None
        if semantic_declared or status_declared:
            normalized = normalize_tool_process_result(
                0,
                native_content,
                "",
                {"output_contract": dict(output_contract)},
            )
            if not normalized.is_success:
                return failed(
                    responsibility="research",
                    failure_code=(
                        normalized.wrapper_reason
                        or "declared_result_status_failed"
                    ),
                )
            if normalized.warning:
                return failed(
                    responsibility="research",
                    failure_code=normalized.warning,
                )

        semantic_available = bool(semantic_declared and normalized is not None)
        semantic_value: Any = None
        semantic_content = ""
        semantic_sha: str | None = None
        semantic_bytes = 0
        if semantic_available and normalized is not None:
            semantic_content = normalized.semantic_content
            semantic_value = semantic_content
            semantic_type = normalized_artifact_type(
                normalized.semantic_artifact_type
            )
            if semantic_type == "json":
                try:
                    semantic_value = json.loads(semantic_content)
                except json.JSONDecodeError as exc:
                    return failed(
                        responsibility="research",
                        failure_code="semantic_output_json_invalid",
                        error=exc,
                    )
                semantic_contract = cast(
                    Mapping[str, Any], output_contract["semantic_output"]
                )
                semantic_schema = contract_schema(semantic_contract)
                if semantic_schema is not None:
                    try:
                        from .model_response_contracts import (
                            require_semantic_json_schema,
                            validate_json_schema_instance,
                        )

                        canonical_semantic_schema = require_semantic_json_schema(
                            semantic_schema
                        )
                        valid, reason = validate_json_schema_instance(
                            semantic_value,
                            canonical_semantic_schema,
                        )
                    except Exception as exc:
                        return failed(
                            responsibility="framework",
                            failure_code="semantic_output_json_schema_invalid",
                            error=exc,
                        )
                    if not valid:
                        return failed(
                            responsibility="research",
                            failure_code="semantic_output_json_schema_mismatch",
                            reason=reason,
                        )
            semantic_sha = representation_sha256(semantic_content, semantic_type)
            semantic_bytes = len(semantic_content.encode("utf-8"))

        native_sha = representation_sha256(native_content, native_type or "plaintext")
        native_bytes = len(native_content.encode("utf-8"))
        canonical_value = semantic_value if semantic_available else native_value
        presentation = semantic_content if semantic_available else native_content
        return result.model_copy(
            update={
                "native_value": native_value,
                "native_content": native_content,
                "native_output_sha256": native_sha,
                "native_output_bytes": native_bytes,
                "semantic_view_available": semantic_available,
                "semantic_value": semantic_value,
                "semantic_content": semantic_content,
                "semantic_output_sha256": semantic_sha,
                "semantic_output_bytes": semantic_bytes,
                "canonical_value": canonical_value,
                "presentation": presentation or _presentation_for_value(canonical_value),
                "output_contract_status": "checked",
            }
        )

    async def execute(
        self,
        request: ResourceCallRequest,
        *,
        provider: ProviderCallable | None = None,
    ) -> ResourceCallResult:
        started_ns = time.perf_counter_ns()
        if self.halted:
            raise ResourceRuntimeError("resource_runtime_halted")
        active_provider = provider or self.provider
        if active_provider is None:
            raise ResourceRuntimeError("resource_execution_provider_missing")
        request_sha256 = request.request_sha256
        input_bytes = len(
            canonical_json_bytes(
                {
                    "resolved_bindings": request.resolved_bindings,
                    "authorized_material_content": request.authorized_material_content,
                }
            )
        )
        context = request.execution_context
        handle: ExecutionCallHandle | None = None
        try:
            handle = self.ledger.start_call(
                call_id=request.call_id,
                resource_id=request.resource_definition.resource_id,
                resource_type=request.resource_definition.resource_type,
                entrypoint_id=request.entrypoint_id,
                runtime_kind=self._runtime_kind(request),
                graph_revision=context.graph_revision,
                subtask_id=context.subtask_id,
                subtask_revision=context.subtask_revision,
                step_id=context.step_id,
                attempt=context.attempt,
                request_sha256=request_sha256,
                candidate_pool_sha256=context.candidate_pool_sha256,
                plan_sha256=context.plan_sha256,
                sandbox_scope_sha256=context.sandbox_scope_sha256,
            )
            self.ledger.record_world_prepared(
                handle,
                execution_world_sha256=request.execution_world.execution_world_sha256,
                runtime_image_id=request.execution_world.runtime_image_id,
                direct_argv=request.execution_world.direct_argv,
                network_required=request.execution_world.network_required,
            )
        except ExecutionPersistenceError:
            raise

        canonical: ResourceCallResult | None = None
        try:
            provider_result = active_provider(request)
            if inspect.isawaitable(provider_result):
                provider_result = await provider_result
            if isinstance(provider_result, ResourceCallResult):
                canonical = provider_result
            else:
                canonical = execution_result_to_resource_result(
                    provider_result,
                    call_id=request.call_id,
                    resource_id=request.resource_definition.resource_id,
                    entrypoint_id=request.entrypoint_id,
                    output_contract=request.resource_native_output_contract,
                )
            if (
                canonical.call_id != request.call_id
                or canonical.resource_id != request.resource_definition.resource_id
                or canonical.entrypoint_id != request.entrypoint_id
            ):
                raise ResourceRuntimeError("provider_result_identity_mismatch")
            canonical = self._canonicalize_success(
                canonical, request.resource_native_output_contract
            )
            if (
                canonical.status == ResourceCallStatus.SUCCESS
                and canonical.canonical_value is None
                and not canonical.artifacts
                and not (
                    normalized_artifact_type(request.resource_native_output_contract.get("artifact_type")) == "json"
                    and canonical.output_contract_status == "checked"
                    and canonical.native_content.strip() == "null"
                )
            ):
                raise ResourceRuntimeError("successful_resource_result_payload_missing")
            canonical = canonical.model_copy(
                update={
                    "request_sha256": request_sha256,
                    "canonical_content_sha256": canonical_sha256(
                        canonical.canonical_value
                        if canonical.canonical_value is not None
                        else [item.model_dump(mode="json") for item in canonical.artifacts]
                    ),
                    "result_type": str(
                        request.resource_native_output_contract.get("artifact_type")
                        or request.resource_native_output_contract.get(
                            "semantic_output_kind"
                        )
                        or "canonical_value"
                    ),
                    "provenance": {
                        **dict(canonical.provenance),
                        "source_ids": list(request.provenance_source_ids),
                        "resource_invocation_sha256": request_sha256,
                        "resource_call_id": request.call_id,
                        "resource_id": request.resource_definition.resource_id,
                        "operation_id": request.capability_operation_id,
                        "resource_native_output_contract_sha256": canonical_sha256(
                            request.resource_native_output_contract
                        ),
                        "native_output_sha256": canonical.native_output_sha256,
                        "semantic_output_sha256": canonical.semantic_output_sha256,
                    },
                }
            )
        except Exception as exc:
            if canonical is not None and canonical.status != ResourceCallStatus.SUCCESS:
                canonical = self._append_secondary_audit_failure(
                    canonical,
                    failure_origin="formal_adapter",
                    failure_code="resource_result_postprocessing_failed",
                    error=exc,
                )
            else:
                failure = ResourceFailure.create(
                    responsibility="framework",
                    failure_stage="provider_boundary",
                    failure_code="resource_provider_unstructured_exception",
                    error=exc,
                )
                canonical = ResourceCallResult(
                    call_id=request.call_id,
                    resource_id=request.resource_definition.resource_id,
                    entrypoint_id=request.entrypoint_id,
                    status=ResourceCallStatus.FRAMEWORK_FAILURE,
                    failure=failure,
                    execution_audit={
                        "failure_origin": "provider_boundary",
                        "stack_fingerprint_sha256": canonical_sha256(
                            {
                                "failure_origin": "provider_boundary",
                                "failure_code": failure.failure_code,
                                "exception_type": type(exc).__name__,
                            }
                        ),
                    },
                    output_contract_status="not_checked",
                )

        runtime_ms = 0.0
        legacy_metrics = canonical.execution_audit.get("legacy_metric_projection")
        if isinstance(legacy_metrics, Mapping):
            raw_runtime_ms = legacy_metrics.get("latency_ms")
            if isinstance(raw_runtime_ms, (int, float)) and not isinstance(
                raw_runtime_ms, bool
            ):
                runtime_ms = max(0.0, float(raw_runtime_ms))
        resource_metrics = {
            "resource_call_count": 1,
            "status": canonical.status.value,
            "wall_time_ms": (time.perf_counter_ns() - started_ns) / 1_000_000,
            "runtime_ms": runtime_ms,
            "input_bytes": input_bytes,
            "native_output_bytes": canonical.native_output_bytes,
            "semantic_output_bytes": canonical.semantic_output_bytes,
        }
        canonical = canonical.model_copy(
            update={
                "started_event_id": handle.started_event_id if handle else None,
                "execution_audit": {
                    **dict(canonical.execution_audit),
                    "resource_execution_metrics": resource_metrics,
                },
            }
        )
        try:
            for artifact in canonical.artifacts:
                self.ledger.register_artifact(
                    handle,
                    artifact_handle_id=artifact.handle_id,
                    artifact_type=artifact.artifact_type,
                    logical_path=artifact.logical_path or artifact.tool_path,
                    artifact_sha256=canonical_sha256(
                        {
                            "handle_id": artifact.handle_id,
                            "kind": artifact.kind,
                            "logical_path": artifact.logical_path,
                            "tool_path": artifact.tool_path,
                            "artifact_type": artifact.artifact_type,
                        }
                    ),
                )
            terminal = self.ledger.finish_call(
                handle,
                status=canonical.status.value,
                result_sha256=canonical.result_sha256,
                output_contract_status=canonical.output_contract_status,
                responsibility=(canonical.failure.responsibility if canonical.failure else None),
                failure_stage=(canonical.failure.failure_stage if canonical.failure else None),
                failure_code=(canonical.failure.failure_code if canonical.failure else None),
                usage_reference=canonical.usage_reference,
                execution_audit_sha256=canonical_sha256(canonical.execution_audit),
                wall_time_ms=resource_metrics["wall_time_ms"],
                runtime_ms=resource_metrics["runtime_ms"],
                input_bytes=resource_metrics["input_bytes"],
                native_output_bytes=resource_metrics["native_output_bytes"],
                semantic_output_bytes=resource_metrics["semantic_output_bytes"],
            )
            committed = canonical.model_copy(update={"terminal_event_id": terminal["event_id"]})
            if committed.status == ResourceCallStatus.SUCCESS and (
                not committed.request_sha256
                or not committed.canonical_content_sha256
                or committed.output_contract_status != "checked"
                or not committed.terminal_event_id
            ):
                raise ResourceRuntimeError("successful_resource_result_v2_incomplete")
            return committed
        except ExecutionPersistenceError as exc:
            self.halted = True
            with_secondary = self._append_secondary_audit_failure(
                canonical,
                failure_origin="execution_accounting",
                failure_code="execution_terminal_event_persistence_failed",
                error=exc,
            )
            if canonical.status != ResourceCallStatus.SUCCESS and canonical.failure is not None:
                return with_secondary
            return with_secondary.model_copy(
                update={
                    "status": ResourceCallStatus.FRAMEWORK_FAILURE,
                    "failure": ResourceFailure.create(
                        responsibility="framework",
                        failure_stage="execution_accounting",
                        failure_code="execution_terminal_event_persistence_failed",
                        error=exc,
                    ),
                }
            )


__all__ = [
    "CANONICAL_RESULT_PROTOCOL",
    "EXECUTION_WORLD_PROTOCOL",
    "RESOURCE_RUNTIME_ADAPTER_MATRIX",
    "RESOURCE_CALL_PROTOCOL",
    "RESOURCE_RUNTIME_PROTOCOL",
    "ApplicationProfile",
    "ExecutionWorldDescriptor",
    "ResourceCallRequest",
    "ResourceCallResult",
    "ResourceCallStatus",
    "ResourceCallValidationError",
    "ResourceDefinition",
    "ResourceEntrypoint",
    "ResourceExecutionContext",
    "ResourceFailure",
    "ResourceManifestError",
    "ResourceRuntime",
    "ResourceRuntimeError",
    "execution_result_to_resource_result",
    "resource_result_to_execution_result",
    "validated_declared_failure_payload",
    "validated_process_failure_diagnostic",
    "runtime_adapter_supported",
    "supported_runtime_kinds",
]
