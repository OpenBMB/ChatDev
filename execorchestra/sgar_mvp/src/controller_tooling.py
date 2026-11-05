"""Sealed callable Tool contracts for future Controller continuation runtime.

Stage C1 owns only deterministic authority projection.  It does not dispatch a
Tool, send a provider Tool schema, or continue a Controller after a Tool result.
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any, Literal, Mapping, Sequence

from pydantic import Field, field_validator, model_validator

from .binding_protocol import normalize_contract_kind
from .output_realization import (
    OutputReachabilityProof,
    OutputRealizationContractV1,
    prove_output_reachability,
)
from .execution_requirements import ExecutionNetworkDeclaration
from .pipeline_control import FrozenContract, canonical_json_bytes, canonical_sha256
from .resource_runtime import ResourceDefinition
from .path_policy import is_private_host_path_value


CONTROLLER_CALLABLE_TOOL_V1_PROTOCOL = "sgar-controller-callable-tool-v1"
CONTROLLER_CALLABLE_TOOL_V2_PROTOCOL = "sgar-controller-callable-tool-v2"
CONTROLLER_CALLABLE_TOOL_PROTOCOL = CONTROLLER_CALLABLE_TOOL_V2_PROTOCOL
_CONTROLLER_CALLABLE_AUTHORITY_PROTOCOL = CONTROLLER_CALLABLE_TOOL_V1_PROTOCOL

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_DYNAMIC_KINDS = frozenset({
    "text", "int", "float", "bool", "list", "object", "json",
    "path", "file_path", "directory_path",
})
_JSON_TYPES = {
    "text": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "list": "array",
    "object": "object",
    "json": None,
    "path": "string",
    "file_path": "string",
    "directory_path": "string",
}


class ControllerToolingError(ValueError):
    """A callable Tool selection cannot be deterministically sealed."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _require_sha256(value: str, *, field_name: str) -> str:
    normalized = str(value or "").strip().lower()
    if not _SHA256.fullmatch(normalized):
        raise ValueError(f"{field_name}_must_be_sha256_hex")
    return normalized


def _host_path_locator(value: Any, locator: str = "$") -> str | None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            found = _host_path_locator(item, f"{locator}.{key}")
            if found:
                return found
        return None
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found = _host_path_locator(item, f"{locator}[{index}]")
            if found:
                return found
        return None
    if isinstance(value, str) and is_private_host_path_value(value):
        return locator
    return None


def _canonical_host_free(value: Any, *, field_name: str) -> Any:
    projected = json.loads(canonical_json_bytes(value).decode("utf-8"))
    locator = _host_path_locator(projected)
    if locator:
        raise ValueError(f"{field_name}_contains_host_path:{locator}")
    return projected


def _dynamic_port_schema(port: Mapping[str, Any]) -> dict[str, Any]:
    kind = normalize_contract_kind(port)
    if kind not in _SAFE_DYNAMIC_KINDS:
        raise ControllerToolingError("callable_tool_dynamic_port_kind_unsafe")
    json_type = _JSON_TYPES[kind]
    schema: dict[str, Any] = {}
    if json_type is not None:
        schema["type"] = json_type
    description = str(port.get("description") or "").strip()
    if description:
        if _host_path_locator(description):
            raise ControllerToolingError("callable_tool_dynamic_port_description_not_portable")
        schema["description"] = description
    return schema


def _provider_parameters(
    dynamic_input_ports: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    properties = {
        str(port["name"]): _dynamic_port_schema(port)
        for port in dynamic_input_ports
    }
    required = [
        str(port["name"])
        for port in dynamic_input_ports
        if bool(port.get("required", True))
    ]
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def validate_callable_port_partition(
    *,
    operation_input_contract: Sequence[Mapping[str, Any]],
    operation_output_contract: Mapping[str, Any] | None = None,
    fixed_input_names: Sequence[str],
    dynamic_input_names: Sequence[str],
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    """Prove the required fixed/dynamic partition from one entrypoint contract."""

    ports = tuple(dict(item) for item in operation_input_contract)
    names = tuple(str(item.get("name") or "").strip() for item in ports)
    if not all(names) or len(names) != len(set(names)):
        raise ControllerToolingError("callable_tool_input_contract_invalid")
    fixed = tuple(str(item).strip() for item in fixed_input_names)
    dynamic = tuple(str(item).strip() for item in dynamic_input_names)
    if (
        not all(fixed)
        or not all(dynamic)
        or len(fixed) != len(set(fixed))
        or len(dynamic) != len(set(dynamic))
    ):
        raise ControllerToolingError("callable_tool_input_port_duplicate")
    declared = set(names)
    if set(fixed) - declared:
        raise ControllerToolingError("callable_tool_fixed_port_undeclared")
    if set(dynamic) - declared:
        raise ControllerToolingError("callable_tool_dynamic_port_undeclared")
    if set(fixed) & set(dynamic):
        raise ControllerToolingError("callable_tool_fixed_dynamic_port_overlap")
    required = {
        str(item["name"])
        for item in ports
        if bool(item.get("required", True))
    }
    missing = required - set(fixed) - set(dynamic)
    if missing:
        by_name = {str(item["name"]): item for item in ports}
        if any(normalize_contract_kind(by_name[name]) not in _SAFE_DYNAMIC_KINDS for name in missing):
            raise ControllerToolingError("callable_tool_required_fixed_port_missing")
        raise ControllerToolingError("callable_tool_required_port_unassigned")
    # A first read may omit its cursor. Later reads still need the Composer
    # to authorize that input, or explicitly bind it to a fixed value.
    for port in ports:
        if "continuation_from" not in port:
            continue
        source = port["continuation_from"]
        output = operation_output_contract or {}
        schema = next((output[key] for key in ("json_schema", "schema_hint", "schema")
                       if isinstance(output.get(key), Mapping)), {})
        properties = schema.get("properties")
        field = properties.get(source) if isinstance(properties, Mapping) and isinstance(source, str) else None
        types = field.get("type") if isinstance(field, Mapping) else None
        types = types if isinstance(types, list) else [types]
        kind = {"text": "string", "int": "integer"}.get(normalize_contract_kind(port))
        if not kind or kind not in types or any(t not in (kind, "null") for t in types):
            raise ControllerToolingError("callable_tool_continuation_source_invalid")
        if port["name"] not in fixed and port["name"] not in dynamic:
            raise ControllerToolingError("callable_tool_continuation_port_unassigned")
    dynamic_ports = tuple(item for item in ports if str(item["name"]) in set(dynamic))
    for port in dynamic_ports:
        _dynamic_port_schema(port)
    fixed_ports = tuple(item for item in ports if str(item["name"]) in set(fixed))
    return fixed_ports, dynamic_ports


class ControllerCallableToolSpecV1(ExecutionNetworkDeclaration):
    """Version-aware framework identity for one Controller-callable Tool."""

    protocol: Literal[
        CONTROLLER_CALLABLE_TOOL_V1_PROTOCOL,
        CONTROLLER_CALLABLE_TOOL_V2_PROTOCOL,
    ] = (
        CONTROLLER_CALLABLE_TOOL_PROTOCOL
    )
    callable_id: str
    provider_tool_name: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9_]+$",
    )
    resource_id: str = Field(min_length=1)
    resource_type: Literal["Tool"] = "Tool"
    capability_operation_id: str = Field(min_length=1)
    capability_evidence_refs: tuple[str, ...] = Field(min_length=1)
    side_effects: Literal["none", "declared", "unknown"] = "unknown"
    effect_targets: tuple[str, ...] = ()
    entrypoint_id: str = Field(min_length=1)
    resource_manifest_sha256: str
    operation_input_contract: tuple[dict[str, Any], ...]
    fixed_input_bindings: dict[str, Any] = Field(default_factory=dict)
    dynamic_input_ports: tuple[dict[str, Any], ...]
    dynamic_input_schema_sha256: str
    resource_native_output_contract: dict[str, Any]
    available_semantic_output_contract: dict[str, Any] | None = None
    controller_result_source_view: Literal["native", "semantic"]
    controller_result_target_contract: dict[str, Any]
    output_reachability_proof: OutputReachabilityProof
    output_realization_contract: OutputRealizationContractV1
    provider_description: str = Field(min_length=1)
    provider_tool_schema_sha256: str
    callable_spec_sha256: str = ""

    @field_validator(
        "callable_id",
        "resource_manifest_sha256",
        "dynamic_input_schema_sha256",
        "provider_tool_schema_sha256",
    )
    @classmethod
    def _hashes(cls, value: str, info: Any) -> str:
        return _require_sha256(value, field_name=info.field_name)

    @model_validator(mode="before")
    @classmethod
    def _canonicalize(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        return _canonical_host_free(value, field_name="controller_callable_tool_spec")

    @model_validator(mode="after")
    def _seal(self) -> "ControllerCallableToolSpecV1":
        if self.effect_targets and self.side_effects != "declared":
            raise ValueError("controller_callable_effect_targets_without_declared_side_effect")
        fixed_ports, dynamic_ports = validate_callable_port_partition(
            operation_input_contract=self.operation_input_contract,
            operation_output_contract=self.resource_native_output_contract,
            fixed_input_names=tuple(self.fixed_input_bindings),
            dynamic_input_names=tuple(str(item.get("name") or "") for item in self.dynamic_input_ports),
        )
        if tuple(fixed_ports) != tuple(
            item
            for item in self.operation_input_contract
            if str(item["name"]) in self.fixed_input_bindings
        ) or tuple(dynamic_ports) != self.dynamic_input_ports:
            raise ValueError("callable_tool_port_contract_identity_mismatch")
        parameters = _provider_parameters(self.dynamic_input_ports)
        if canonical_sha256(parameters) != self.dynamic_input_schema_sha256:
            raise ValueError("callable_tool_dynamic_schema_identity_mismatch")
        proof = self.output_reachability_proof
        realization = self.output_realization_contract
        if (
            proof.resource_id != self.resource_id
            or proof.capability_operation_id != self.capability_operation_id
            or proof.entrypoint_id != self.entrypoint_id
            or proof.source_view != self.controller_result_source_view
            or proof.output_realization_contract_sha256 != realization.contract_sha256
            or realization.source_view != self.controller_result_source_view
            or canonical_sha256(self.controller_result_target_contract)
            != proof.target_contract_sha256
        ):
            raise ValueError("callable_tool_result_realization_identity_mismatch")
        source_contract = (
            self.available_semantic_output_contract
            if self.controller_result_source_view == "semantic"
            else self.resource_native_output_contract
        )
        if source_contract is None or canonical_sha256(source_contract) != proof.source_contract_sha256:
            raise ValueError("callable_tool_result_source_identity_mismatch")
        authority = _callable_authority_projection(
            resource_id=self.resource_id,
            capability_operation_id=self.capability_operation_id,
            entrypoint_id=self.entrypoint_id,
            resource_manifest_sha256=self.resource_manifest_sha256,
            operation_input_contract=self.operation_input_contract,
            fixed_input_bindings=self.fixed_input_bindings,
            dynamic_input_ports=self.dynamic_input_ports,
            resource_native_output_contract=self.resource_native_output_contract,
            controller_result_target_contract=self.controller_result_target_contract,
            output_reachability_proof=proof,
            output_realization_contract=realization,
            execution_network_required=self.execution_network_required,
        )
        if canonical_sha256(authority) != self.callable_id:
            raise ValueError("controller_callable_id_mismatch")
        expected_provider_name = derive_provider_tool_name(
            capability_operation_id=self.capability_operation_id,
            callable_id=self.callable_id,
            protocol=self.protocol,
        )
        if self.provider_tool_name != expected_provider_name:
            raise ValueError("controller_provider_tool_name_mismatch")
        wire = _provider_tool_schema(
            provider_tool_name=self.provider_tool_name,
            provider_description=self.provider_description,
            parameters=parameters,
        )
        if canonical_sha256(wire) != self.provider_tool_schema_sha256:
            raise ValueError("controller_provider_tool_schema_identity_mismatch")
        projection = self.model_dump(mode="python", exclude={"callable_spec_sha256"})
        expected = canonical_sha256(projection)
        if self.callable_spec_sha256:
            supplied = _require_sha256(
                self.callable_spec_sha256, field_name="callable_spec_sha256"
            )
            if supplied != expected:
                raise ValueError("controller_callable_tool_spec_sha256_mismatch")
        object.__setattr__(self, "callable_spec_sha256", expected)
        return self


def _callable_authority_projection(
    *,
    resource_id: str,
    capability_operation_id: str,
    entrypoint_id: str,
    resource_manifest_sha256: str,
    operation_input_contract: Sequence[Mapping[str, Any]],
    fixed_input_bindings: Mapping[str, Any],
    dynamic_input_ports: Sequence[Mapping[str, Any]],
    resource_native_output_contract: Mapping[str, Any],
    controller_result_target_contract: Mapping[str, Any],
    output_reachability_proof: OutputReachabilityProof,
    output_realization_contract: OutputRealizationContractV1,
    execution_network_required: bool | None = None,
) -> dict[str, Any]:
    result = {
        "protocol": _CONTROLLER_CALLABLE_AUTHORITY_PROTOCOL,
        "resource_id": resource_id,
        "capability_operation_id": capability_operation_id,
        "entrypoint_id": entrypoint_id,
        "resource_manifest_sha256": resource_manifest_sha256,
        "operation_input_contract": [dict(item) for item in operation_input_contract],
        "fixed_input_bindings": dict(fixed_input_bindings),
        "dynamic_input_ports": [dict(item) for item in dynamic_input_ports],
        "resource_native_output_contract": dict(resource_native_output_contract),
        "controller_result_target_contract": dict(controller_result_target_contract),
        "output_reachability_proof_sha256": output_reachability_proof.proof_sha256,
        "output_realization_contract_sha256": output_realization_contract.contract_sha256,
    }
    if execution_network_required is not None:
        result["execution_network_required"] = execution_network_required
    return result


def _provider_tool_schema(
    *,
    provider_tool_name: str,
    provider_description: str,
    parameters: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": provider_tool_name,
            "description": provider_description,
            "parameters": copy.deepcopy(dict(parameters)),
        },
    }


def _provider_operation_slug(capability_operation_id: str) -> str:
    operation_name = str(capability_operation_id or "").rsplit("::", 1)[-1]
    normalized = re.sub(r"[^a-z0-9]+", "_", operation_name.casefold()).strip("_")
    normalized = re.sub(r"_+", "_", normalized)
    return (normalized or "tool")[:32].rstrip("_") or "tool"


def derive_provider_tool_name(
    *,
    capability_operation_id: str,
    callable_id: str,
    protocol: str = CONTROLLER_CALLABLE_TOOL_PROTOCOL,
) -> str:
    """Project one provider-safe name from sealed framework authority only."""

    identity = _require_sha256(callable_id, field_name="callable_id")
    if protocol == CONTROLLER_CALLABLE_TOOL_V1_PROTOCOL:
        return f"sgar_call_{identity[:24]}"
    if protocol == CONTROLLER_CALLABLE_TOOL_V2_PROTOCOL:
        slug = _provider_operation_slug(capability_operation_id)
        return f"sgar_{slug}_{identity[:24]}"
    raise ControllerToolingError("controller_callable_tool_protocol_unsupported")


def derive_controller_callable_tool_spec(
    *,
    definition: ResourceDefinition,
    capability_operation_id: str,
    fixed_input_bindings: Mapping[str, Any],
    dynamic_input_names: Sequence[str],
    capability_evidence_refs: Sequence[str],
    execution_network_required: bool | None = None,
) -> ControllerCallableToolSpecV1:
    """Re-prove and seal one candidate-authorized callable Tool application."""

    if definition.resource_type != "Tool":
        raise ControllerToolingError("controller_callable_resource_not_tool")
    card = definition.capability_card
    if card is None:
        raise ControllerToolingError("controller_callable_capability_card_missing")
    operation = next(
        (
            item
            for item in card.capability_operations
            if item.capability_operation_id == capability_operation_id
        ),
        None,
    )
    if operation is None:
        raise ControllerToolingError("controller_callable_operation_unknown")
    if operation.evidence_status == "unknown":
        raise ControllerToolingError("controller_callable_operation_evidence_unknown")
    evidence_refs = tuple(str(item) for item in capability_evidence_refs)
    if not (
        capability_operation_id in evidence_refs
        or operation.operation_sha256 in evidence_refs
    ):
        raise ControllerToolingError("controller_callable_operation_evidence_missing")
    entrypoint_id = str(operation.entrypoint_id or "").strip()
    if not entrypoint_id:
        raise ControllerToolingError("controller_callable_entrypoint_unresolved")
    try:
        entrypoint = definition.entrypoint(entrypoint_id)
    except Exception as exc:
        raise ControllerToolingError("controller_callable_entrypoint_unresolved") from exc
    fixed = _canonical_host_free(
        dict(fixed_input_bindings), field_name="controller_callable_fixed_bindings"
    )
    _, dynamic_ports = validate_callable_port_partition(
        operation_input_contract=entrypoint.input_contract,
        operation_output_contract=entrypoint.output_contract,
        fixed_input_names=tuple(fixed),
        dynamic_input_names=tuple(dynamic_input_names),
    )
    native_contract = _canonical_host_free(
        entrypoint.output_contract, field_name="controller_callable_native_output"
    )
    semantic_raw = native_contract.get("semantic_output")
    semantic_contract = (
        dict(semantic_raw)
        if isinstance(semantic_raw, Mapping)
        and str(semantic_raw.get("payload_path") or "").strip()
        else None
    )
    target_contract = semantic_contract or native_contract
    proof, realization = prove_output_reachability(
        resource_id=definition.resource_id,
        capability_operation_id=capability_operation_id,
        entrypoint_id=entrypoint_id,
        resource_native_output_contract=native_contract,
        target_output_contract=target_contract,
    )
    if proof.compatibility not in {"exact", "deterministically_convertible"} or realization is None:
        raise ControllerToolingError("controller_callable_result_not_deterministically_reachable")
    parameters = _provider_parameters(dynamic_ports)
    authority = _callable_authority_projection(
        resource_id=definition.resource_id,
        capability_operation_id=capability_operation_id,
        entrypoint_id=entrypoint_id,
        resource_manifest_sha256=definition.manifest_sha256,
        operation_input_contract=entrypoint.input_contract,
        fixed_input_bindings=fixed,
        dynamic_input_ports=dynamic_ports,
        resource_native_output_contract=native_contract,
        controller_result_target_contract=target_contract,
        output_reachability_proof=proof,
        output_realization_contract=realization,
        execution_network_required=execution_network_required,
    )
    callable_id = canonical_sha256(authority)
    provider_tool_name = derive_provider_tool_name(
        capability_operation_id=capability_operation_id,
        callable_id=callable_id,
    )
    provider_description = (
        f"Invoke sealed capability operation {operation.declared_operation}. "
        "Use this function name exactly as supplied."
    )
    output_description = native_contract.get("description")
    if isinstance(output_description, str) and 0 < len(output_description) <= 400:
        provider_description += " Returns: " + output_description
    if _host_path_locator(provider_description):
        raise ControllerToolingError("controller_callable_description_not_portable")
    wire = _provider_tool_schema(
        provider_tool_name=provider_tool_name,
        provider_description=provider_description,
        parameters=parameters,
    )
    return ControllerCallableToolSpecV1(
        execution_network_required=execution_network_required,
        callable_id=callable_id,
        provider_tool_name=provider_tool_name,
        resource_id=definition.resource_id,
        capability_operation_id=capability_operation_id,
        capability_evidence_refs=evidence_refs,
        side_effects=operation.side_effects,
        effect_targets=operation.effect_targets,
        entrypoint_id=entrypoint_id,
        resource_manifest_sha256=definition.manifest_sha256,
        operation_input_contract=entrypoint.input_contract,
        fixed_input_bindings=fixed,
        dynamic_input_ports=dynamic_ports,
        dynamic_input_schema_sha256=canonical_sha256(parameters),
        resource_native_output_contract=native_contract,
        available_semantic_output_contract=semantic_contract,
        controller_result_source_view=proof.source_view,
        controller_result_target_contract=target_contract,
        output_reachability_proof=proof,
        output_realization_contract=realization,
        provider_description=provider_description,
        provider_tool_schema_sha256=canonical_sha256(wire),
    )


def project_provider_tool_schema(spec: ControllerCallableToolSpecV1) -> dict[str, Any]:
    """Project the provider wire schema without exposing any sealed fixed input."""

    parameters = _provider_parameters(spec.dynamic_input_ports)
    wire = _provider_tool_schema(
        provider_tool_name=spec.provider_tool_name,
        provider_description=spec.provider_description,
        parameters=parameters,
    )
    if canonical_sha256(parameters) != spec.dynamic_input_schema_sha256:
        raise ControllerToolingError("controller_dynamic_schema_identity_changed")
    if canonical_sha256(wire) != spec.provider_tool_schema_sha256:
        raise ControllerToolingError("controller_provider_tool_schema_identity_changed")
    return wire


def require_unique_provider_tool_names(
    specs: Sequence[ControllerCallableToolSpecV1],
) -> None:
    names = tuple(item.provider_tool_name for item in specs)
    if len(names) != len(set(names)):
        raise ControllerToolingError("controller_provider_tool_name_collision")


__all__ = [
    "CONTROLLER_CALLABLE_TOOL_PROTOCOL",
    "CONTROLLER_CALLABLE_TOOL_V1_PROTOCOL",
    "CONTROLLER_CALLABLE_TOOL_V2_PROTOCOL",
    "ControllerCallableToolSpecV1",
    "ControllerToolingError",
    "derive_controller_callable_tool_spec",
    "derive_provider_tool_name",
    "project_provider_tool_schema",
    "require_unique_provider_tool_names",
    "validate_callable_port_partition",
]
