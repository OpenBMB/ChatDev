"""Controller Tool runtime dispatch and typed continuation contracts.

This module consumes Stage-C1 callable authority.  It never selects a Tool,
operation, entrypoint, input partition, result view, or realization strategy.
Resource execution remains owned by :class:`ResourceRuntime`, while Stage-A's
``OutputRealizer`` remains the sole result-representation authority.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import posixpath
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal, Mapping, Sequence

from pydantic import Field, PrivateAttr, field_validator, model_validator

from .binding_protocol import BindingProtocolError, normalize_contract_kind, parse_binding_source
from .controller_tooling import (
    ControllerCallableToolSpecV1,
    project_provider_tool_schema,
)
from .formal_contracts import MaterialDescriptorV1
from .model_response_contracts import validate_json_schema_instance
from .output_realization import OutputRealizer, normalized_artifact_type
from .pipeline_control import FrozenContract, canonical_json_bytes, canonical_sha256
from .resource_runtime import (
    ExecutionWorldDescriptor,
    ProviderCallable,
    ResourceCallRequest,
    ResourceCallResult,
    ResourceCallStatus,
    ResourceDefinition,
    ResourceExecutionContext,
    ResourceFailure,
    ResourceRuntime,
    validated_declared_failure_payload,
    validated_process_failure_diagnostic,
)
from .schema import ArtifactHandle
from .path_policy import is_path_field_name, is_private_host_path_value


CONTROLLER_TOOL_RUNTIME_PROTOCOL = "sgar-controller-tool-runtime-v1"
CONTROLLER_TOOL_CALL_INTENT_PROTOCOL = "sgar-controller-tool-call-intent-v1"
CONTROLLER_TOOL_OBSERVATION_PROTOCOL = "sgar-controller-tool-observation-v1"
CONTROLLER_TOOL_PROVENANCE_PROTOCOL = "sgar-controller-tool-provenance-v1"
CONTROLLER_TOOL_METRICS_PROTOCOL = "sgar-controller-tool-runtime-metrics-v1"
CONTROLLER_TOOL_INVOCATION_RESULT_PROTOCOL = (
    "sgar-controller-tool-invocation-result-v1"
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
# /app is the public task-container namespace, not a private host locator.
# Native Tool receipts and ordinary task content can legitimately contain it.
# Dynamic path ports still pass the independent task-scope validation below.
_RUNTIME_ABSOLUTE = re.compile(
    r"(?:^|[\s'\"=(])/(?:workspace|tmp|var/tmp|home)(?:/|$)"
)


class ControllerToolRuntimeError(ValueError):
    """A Tool action violated sealed authority or failed terminally."""

    def __init__(
        self,
        code: str,
        *,
        responsibility: str = "framework",
        invocation_result: Any = None,
        failure_stage: str = "controller_tool_runtime",
        terminal_context: ControllerToolTerminalContext | None = None,
    ) -> None:
        super().__init__(str(code))
        self.code = str(code)
        self.responsibility = str(responsibility)
        self.invocation_result = invocation_result
        self.failure_stage = failure_stage
        self.terminal_context = terminal_context


class ControllerToolTerminalContext(FrozenContract):
    """Internal references, including calls without a valid observation."""

    failure_stage: str
    failure_code: str
    responsibility: Literal["framework", "infrastructure", "research", "budget"]
    session_id: str | None = None
    turn_id: str | None = None
    provider_tool_call_id: str | None = None
    callable_id: str | None = None
    resource_call_id: str | None = None
    resource_dispatched: bool = False
    resource_outcome: Literal["not_dispatched", "unknown", "result_received"] = "not_dispatched"
    resource_terminal_event_id: str | None = None
    resource_result_sha256: str | None = None
    original_resource_failure: ResourceFailure | None = None
    usage_reference: str | None = None
    realization_id: str | None = None
    realized_output_sha256: str | None = None
    observation_sha256: str | None = None
    provenance_sha256: str | None = None
    started_persisted: bool = False
    finished_persisted: bool = False
    evidence_incomplete: bool = False
    secondary_audit_failures: tuple[str, ...] = ()


class _ControllerToolAuditReferences(FrozenContract):
    """Neutral per-invocation facts, kept outside public contracts and hashes."""

    session_id: str
    turn_id: str
    provider_tool_call_id: str
    callable_id: str
    resource_call_id: str | None
    resource_dispatched: bool
    resource_outcome: Literal["not_dispatched", "unknown", "result_received"]
    resource_terminal_event_id: str | None
    resource_result_sha256: str | None
    original_resource_failure: ResourceFailure | None
    usage_reference: str | None
    realization_id: str | None
    realized_output_sha256: str | None
    observation_sha256: str | None
    provenance_sha256: str | None
    started_persisted: bool
    finished_persisted: bool
    evidence_incomplete: bool
    secondary_audit_failures: tuple[str, ...]

    def terminal_context(self, error: ControllerToolRuntimeError) -> ControllerToolTerminalContext:
        return ControllerToolTerminalContext(
            **self.model_dump(mode="python"),
            failure_code=error.code, failure_stage=error.failure_stage,
            responsibility=error.responsibility,
        )


@dataclass
class _ToolAttempt:
    request: ResourceCallRequest | None = None
    result: ResourceCallResult | None = None
    realization: Any = None
    invocation: Any = None
    failure: ControllerToolRuntimeError | None = None
    dispatched: bool = False
    started_persisted: bool = False
    finished_persisted: bool = False
    secondary_audit_failures: tuple[str, ...] = ()


def tool_failure_allows_continuation(
    result: ResourceCallResult, spec: ControllerCallableToolSpecV1
) -> bool:
    """Expose safe research failures as observations inside the bounded loop.

    A declared business failure is already native-contract evidence.  Other
    research failures may continue for capability operations explicitly
    declared effect-free, after a response was received.  A process that
    returned a sealed exit diagnostic may also continue: the bounded
    controller needs that observed failure to repair and rerun its authorized
    workspace action.  Infrastructure, framework, budget, and unobserved
    mutating failures remain terminal.
    """
    failure = result.failure
    declaration = spec.resource_native_output_contract.get("result_status")
    declared_business_failure = bool(
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
    )
    effect_free_research_failure = bool(
        result.status == ResourceCallStatus.RESEARCH_FAILURE
        and failure is not None
        and failure.responsibility == "research"
        and failure.response_received
        and getattr(spec, "side_effects", "unknown") == "none"
    )
    observed_process_failure = bool(
        result.status == ResourceCallStatus.RESEARCH_FAILURE
        and failure is not None
        and failure.responsibility == "research"
        and failure.failure_stage == "resource_execution"
        and failure.failure_code == "resource_process_failed"
        and failure.response_received
        and validated_process_failure_diagnostic(result) is not None
    )
    observed_effect_free_timeout = bool(
        result.status == ResourceCallStatus.RESEARCH_FAILURE
        and failure is not None and failure.responsibility == "research"
        and failure.failure_stage == "resource_execution"
        and failure.failure_code in {"tool_runtime_timeout", "resource_process_timeout"}
        and getattr(spec, "side_effects", "unknown") == "none"
        and not getattr(spec, "effect_targets", ())
        and result.started_event_id and result.terminal_event_id
    )
    return (
        declared_business_failure
        or effect_free_research_failure
        or observed_process_failure
        or observed_effect_free_timeout
    )


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
    if isinstance(value, str) and (
        is_private_host_path_value(value) or _RUNTIME_ABSOLUTE.search(value)
    ):
        return locator
    return None


def _require_host_free(value: Any, *, code: str) -> None:
    if _host_path_locator(value):
        raise ControllerToolRuntimeError(code)


def _require_public_result_paths(value: Any) -> None:
    """Inspect result locator fields, not code, diagnostics or document prose.

    Resource data is not framework dispatch metadata. POSIX paths in a Tool
    result refer to its execution environment, including system and temporary
    directories. Host aliases are resolved at dispatch; directory spelling
    alone cannot establish a private control-host identity.
    """
    if isinstance(value, Mapping):
        for key, item in value.items():
            if is_path_field_name(key):
                def check_path(path: Any) -> None:
                    if isinstance(path, str) and is_private_host_path_value(path):
                        raise ControllerToolRuntimeError("controller_tool_observation_contains_host_path")
                    if isinstance(path, (list, tuple)):
                        for nested in path:
                            check_path(nested)
                    elif isinstance(path, Mapping):
                        for nested in path.values():
                            check_path(nested)
                check_path(item)
            else:
                _require_public_result_paths(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _require_public_result_paths(item)


def _declared_failure_diagnostic(
    result: ResourceCallResult, spec: ControllerCallableToolSpecV1
) -> Any | None:
    """Expose native business failure or sealed process stderr, never a raw exception.

    Check the sealed native contract and recorded content identity again at
    the model boundary. This does not realize a failed result as success or
    create a semantic view that the resource did not produce.
    """
    payload = validated_declared_failure_payload(result, spec.resource_native_output_contract)
    if payload is None:
        diagnostic = validated_process_failure_diagnostic(result)
        if diagnostic is not None:
            payload = {"process_diagnostic": diagnostic}
    if payload is not None:
        try:
            _require_public_result_paths(payload)
        except (TypeError, ValueError):
            return None
    return payload


def _canonical_value(value: Any) -> Any:
    return json.loads(canonical_json_bytes(value).decode("utf-8"))


class ControllerToolCallIntentV1(FrozenContract):
    protocol: Literal[CONTROLLER_TOOL_CALL_INTENT_PROTOCOL] = (
        CONTROLLER_TOOL_CALL_INTENT_PROTOCOL
    )
    runtime_protocol: Literal[CONTROLLER_TOOL_RUNTIME_PROTOCOL] = (
        CONTROLLER_TOOL_RUNTIME_PROTOCOL
    )
    session_id: str = Field(min_length=1)
    turn_id: str = Field(min_length=1)
    provider_tool_call_id: str = Field(min_length=1)
    provider_tool_name: str = Field(min_length=1)
    callable_id: str
    normalized_dynamic_arguments: dict[str, Any]
    dynamic_arguments_sha256: str
    call_fingerprint_sha256: str
    intent_sha256: str = ""

    @field_validator(
        "callable_id",
        "dynamic_arguments_sha256",
        "call_fingerprint_sha256",
    )
    @classmethod
    def _hashes(cls, value: str, info: Any) -> str:
        return _require_sha256(value, field_name=info.field_name)

    @model_validator(mode="before")
    @classmethod
    def _canonicalize(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        projected = dict(value)
        if isinstance(projected.get("normalized_dynamic_arguments"), Mapping):
            projected["normalized_dynamic_arguments"] = _canonical_value(
                projected["normalized_dynamic_arguments"]
            )
        return projected

    @model_validator(mode="after")
    def _seal(self) -> "ControllerToolCallIntentV1":
        # Argument meaning belongs to the sealed callable's input ports.
        # Normalization, prevalidation and dispatch all validate those ports;
        # this identity envelope must not reinterpret arbitrary text as paths.
        _require_host_free(
            {"session_id": self.session_id, "turn_id": self.turn_id,
             "provider_tool_call_id": self.provider_tool_call_id,
             "provider_tool_name": self.provider_tool_name},
            code="controller_tool_intent_metadata_contains_host_path",
        )
        expected_arguments = canonical_sha256(self.normalized_dynamic_arguments)
        if self.dynamic_arguments_sha256 != expected_arguments:
            raise ValueError("controller_tool_dynamic_arguments_identity_mismatch")
        expected_fingerprint = canonical_sha256(
            {
                "callable_id": self.callable_id,
                "dynamic_arguments": self.normalized_dynamic_arguments,
            }
        )
        if self.call_fingerprint_sha256 != expected_fingerprint:
            raise ValueError("controller_tool_call_fingerprint_mismatch")
        projection = self.model_dump(mode="python", exclude={"intent_sha256"})
        expected = canonical_sha256(projection)
        if self.intent_sha256 and self.intent_sha256 != expected:
            raise ValueError("controller_tool_call_intent_sha256_mismatch")
        object.__setattr__(self, "intent_sha256", expected)
        return self


def _raw_tool_call(value: Any) -> tuple[str, str, Any]:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="python")
    if not isinstance(value, Mapping):
        raise ControllerToolRuntimeError("controller_tool_call_shape_invalid")
    function = value.get("function")
    if hasattr(function, "model_dump"):
        function = function.model_dump(mode="python")
    provider_call_id = str(
        value.get("id") or value.get("tool_call_id") or ""
    ).strip()
    if isinstance(function, Mapping):
        name = str(function.get("name") or "").strip()
        arguments = function.get("arguments")
    else:
        name = str(value.get("name") or "").strip()
        arguments = value.get("arguments")
    if not provider_call_id:
        raise ControllerToolRuntimeError("controller_provider_tool_call_id_missing")
    if not name:
        raise ControllerToolRuntimeError("controller_provider_tool_name_missing")
    return provider_call_id, name, arguments


def _provider_tool_aliases(spec: Any) -> tuple[str, ...]:
    """Return deterministic semantic aliases for providers that rewrite names.

    Some OpenAI-compatible gateways/models emit the operation slug instead of
    the framework's hash-suffixed provider name.  These aliases are derived
    solely from the sealed operation identity and are accepted only when they
    are unambiguous within the current callable scope.  The intent is always
    canonicalized back to ``spec.provider_tool_name`` before prevalidation or
    dispatch, so aliases cannot widen authority.
    """

    operation = str(getattr(spec, "capability_operation_id", "") or "").strip()
    slug = re.sub(r"[^a-z0-9]+", "_", operation.rsplit("::", 1)[-1].casefold()).strip("_")
    slug = re.sub(r"_+", "_", slug)
    resource = str(getattr(spec, "resource_id", "") or "").strip()
    resource_slug = re.sub(r"[^a-z0-9]+", "_", resource.casefold()).strip("_")
    if not slug and not operation and not resource_slug:
        return ()
    aliases = {
        value
        for value in (
            operation,
            operation.replace("::", "_"),
            slug,
            f"sgar_{slug}" if slug else "",
            resource,
            resource_slug,
        )
        if value
    }
    return tuple(sorted(aliases))


def _dynamic_arguments(
    value: Any, spec: ControllerCallableToolSpecV1
) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ControllerToolRuntimeError(
                "controller_tool_arguments_json_invalid"
            ) from exc
    if not isinstance(value, Mapping):
        raise ControllerToolRuntimeError("controller_tool_arguments_not_object")
    try:
        canonical = _canonical_value(dict(value))
    except (TypeError, ValueError) as exc:
        raise ControllerToolRuntimeError(
            "controller_tool_arguments_json_invalid"
        ) from exc
    # Providers sometimes echo a fixed literal alongside the dynamic fields.
    # Removing an exactly identical echo changes no dispatched value and avoids
    # spending a model turn to omit it. References remain runtime-owned, and any
    # differing value still reaches the existing fixed-override rejection.
    for name in set(canonical) & set(spec.fixed_input_bindings):
        try:
            fixed = parse_binding_source(spec.fixed_input_bindings[name])
        except BindingProtocolError:
            continue
        if fixed.variant == "literal" and canonical_json_bytes(canonical[name]) == canonical_json_bytes(fixed.value):
            del canonical[name]
    return canonical


def _canonical_dynamic_task_paths(arguments: Mapping[str, Any], spec: ControllerCallableToolSpecV1) -> dict[str, Any]:
    """Use the dispatch layer's public namespace after validating raw paths.

    Never normalize traversal away before scope validation. Non-path values,
    including source code and text that mentions a path, remain byte-identical.
    """
    canonical = dict(arguments)
    for port in spec.dynamic_input_ports:
        name = str(port.get("name") or "")
        if name not in canonical or normalize_contract_kind(port) not in {
            "path", "file_path", "directory_path",
        }:
            continue
        path = canonical[name]
        if isinstance(path, str):
            canonical[name] = posixpath.normpath(path if path.startswith("/") else "/app/" + path)
    return canonical


def _validate_dynamic_arguments(
    arguments: Mapping[str, Any], spec: ControllerCallableToolSpecV1
) -> None:
    wire = project_provider_tool_schema(spec)
    if canonical_sha256(wire) != spec.provider_tool_schema_sha256:
        raise ControllerToolRuntimeError(
            "controller_provider_tool_schema_identity_changed"
        )
    parameters = wire.get("function", {}).get("parameters")
    if not isinstance(parameters, Mapping):
        raise ControllerToolRuntimeError(
            "controller_provider_tool_schema_identity_changed"
        )
    dynamic_names = {
        str(item.get("name") or "") for item in spec.dynamic_input_ports
    }
    fixed_names = set(spec.fixed_input_bindings)
    supplied = set(arguments)
    if supplied & fixed_names:
        raise ControllerToolRuntimeError("controller_tool_fixed_argument_override")
    if supplied - dynamic_names:
        raise ControllerToolRuntimeError(
            "controller_tool_dynamic_argument_undeclared"
        )
    required = {
        str(item.get("name") or "")
        for item in spec.dynamic_input_ports
        if bool(item.get("required", True))
    }
    if required - supplied:
        raise ControllerToolRuntimeError(
            "controller_tool_dynamic_argument_required_missing"
        )
    valid, _ = validate_json_schema_instance(arguments, parameters)
    if not valid:
        raise ControllerToolRuntimeError(
            "controller_tool_dynamic_argument_contract_mismatch"
        )
    for port in spec.dynamic_input_ports:
        name = str(port.get("name") or "")
        if name not in arguments or normalize_contract_kind(port) not in {
            "path", "file_path", "directory_path",
        }:
            continue
        path = arguments[name]
        if (
            not isinstance(path, str)
            or not path.strip()
            or path.startswith("//")
            or "\\" in path
            or "\x00" in path
            or "\n" in path
            or "\r" in path
            or ".." in path.split("/")
            or is_private_host_path_value(path)
        ):
            raise ControllerToolRuntimeError(
                "controller_tool_dynamic_path_out_of_scope"
            )


def normalize_provider_tool_calls(
    *,
    session_id: str,
    turn_id: str,
    raw_tool_calls: Sequence[Any],
    callable_tools: Sequence[ControllerCallableToolSpecV1],
    argument_projector: Callable[[ControllerCallableToolSpecV1, Mapping[str, Any]], Mapping[str, Any]] | None = None,
) -> tuple[ControllerToolCallIntentV1, ...]:
    """Resolve and normalize a complete provider action turn without dispatch."""

    by_name = {item.provider_tool_name: item for item in callable_tools}
    if len(by_name) != len(tuple(callable_tools)):
        raise ControllerToolRuntimeError("controller_provider_tool_name_collision")
    alias_map: dict[str, Any | None] = {}
    for spec in callable_tools:
        for alias in _provider_tool_aliases(spec):
            if alias not in alias_map:
                alias_map[alias] = spec
            elif alias_map[alias] is not None:
                previous = alias_map[alias]
                if previous.callable_id != spec.callable_id:
                    # Keep an explicit ambiguity marker; a later spec must
                    # not accidentally make a collided alias usable again.
                    alias_map[alias] = None
    intents: list[ControllerToolCallIntentV1] = []
    provider_ids: set[str] = set()
    for raw in raw_tool_calls:
        provider_call_id, name, raw_arguments = _raw_tool_call(raw)
        if provider_call_id in provider_ids:
            raise ControllerToolRuntimeError(
                "controller_provider_tool_call_id_duplicate"
            )
        provider_ids.add(provider_call_id)
        spec = by_name.get(name)
        if spec is None:
            spec = alias_map.get(name)
        if spec is None:
            raise ControllerToolRuntimeError("controller_tool_call_not_authorized")
        arguments = _dynamic_arguments(raw_arguments, spec)
        _validate_dynamic_arguments(arguments, spec)
        arguments = (
            dict(argument_projector(spec, arguments)) if argument_projector is not None
            else _canonical_dynamic_task_paths(arguments, spec)
        )
        _validate_dynamic_arguments(arguments, spec)
        arguments_sha = canonical_sha256(arguments)
        fingerprint = canonical_sha256(
            {"callable_id": spec.callable_id, "dynamic_arguments": arguments}
        )
        intents.append(
            ControllerToolCallIntentV1(
                session_id=session_id,
                turn_id=turn_id,
                provider_tool_call_id=provider_call_id,
                # Canonicalize semantic aliases back to the sealed provider
                # name.  Downstream identity checks therefore remain strict.
                provider_tool_name=spec.provider_tool_name,
                callable_id=spec.callable_id,
                normalized_dynamic_arguments=arguments,
                dynamic_arguments_sha256=arguments_sha,
                call_fingerprint_sha256=fingerprint,
            )
        )
    return tuple(intents)


def prevalidate_tool_call_intents(
    *,
    intents: Sequence[ControllerToolCallIntentV1 | Mapping[str, Any]],
    callable_tools: Sequence[ControllerCallableToolSpecV1],
    session_id: str,
    turn_id: str,
    current_tool_call_count: int,
    prior_fingerprint_counts: Mapping[str, int],
    max_tool_calls: int,
    max_same_call_repeats: int,
    repeat_fingerprints: Mapping[str, str] | None = None,
) -> tuple[ControllerToolCallIntentV1, ...]:
    """Validate an entire action turn before its first Resource dispatch."""

    parsed = tuple(
        item
        if isinstance(item, ControllerToolCallIntentV1)
        else ControllerToolCallIntentV1.model_validate(item)
        for item in intents
    )
    if current_tool_call_count + len(parsed) > max_tool_calls:
        raise ControllerToolRuntimeError("controller_tool_call_limit", responsibility="budget")
    by_id = {item.callable_id: item for item in callable_tools}
    if len(by_id) != len(tuple(callable_tools)):
        raise ControllerToolRuntimeError("controller_callable_tool_identity_duplicate")
    provider_ids: set[str] = set()
    projected_counts = dict(prior_fingerprint_counts)
    for intent in parsed:
        if intent.session_id != session_id or intent.turn_id != turn_id:
            raise ControllerToolRuntimeError("controller_tool_call_identity_mismatch")
        spec = by_id.get(intent.callable_id)
        if spec is None or spec.provider_tool_name != intent.provider_tool_name:
            raise ControllerToolRuntimeError("controller_tool_call_not_authorized")
        if intent.provider_tool_call_id in provider_ids:
            raise ControllerToolRuntimeError(
                "controller_provider_tool_call_id_duplicate"
            )
        provider_ids.add(intent.provider_tool_call_id)
        _validate_dynamic_arguments(intent.normalized_dynamic_arguments, spec)
        repeat_key = (repeat_fingerprints or {}).get(
            intent.provider_tool_call_id, intent.call_fingerprint_sha256
        )
        count = projected_counts.get(repeat_key, 0) + 1
        if count > max_same_call_repeats:
            raise ControllerToolRuntimeError(
                "controller_tool_call_repeat_limit", responsibility="research"
            )
        projected_counts[repeat_key] = count
    return parsed


class ControllerToolRuntimeProvenanceV1(FrozenContract):
    protocol: Literal[CONTROLLER_TOOL_PROVENANCE_PROTOCOL] = (
        CONTROLLER_TOOL_PROVENANCE_PROTOCOL
    )
    runtime_protocol: Literal[CONTROLLER_TOOL_RUNTIME_PROTOCOL] = (
        CONTROLLER_TOOL_RUNTIME_PROTOCOL
    )
    session_id: str = Field(min_length=1)
    turn_id: str = Field(min_length=1)
    provider_tool_call_id: str = Field(min_length=1)
    callable_id: str
    callable_spec_sha256: str
    provider_tool_schema_sha256: str
    dynamic_arguments_sha256: str
    resource_call_id: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    entrypoint_id: str = Field(min_length=1)
    native_output_sha256: str | None = None
    semantic_output_sha256: str | None = None
    source_view: Literal["native", "semantic"]
    output_realization_contract_sha256: str
    target_contract_sha256: str
    realized_output_sha256: str | None = None
    observation_sha256: str
    provenance_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "ControllerToolRuntimeProvenanceV1":
        for field_name in (
            "callable_id",
            "callable_spec_sha256",
            "provider_tool_schema_sha256",
            "dynamic_arguments_sha256",
            "native_output_sha256",
            "semantic_output_sha256",
            "output_realization_contract_sha256",
            "target_contract_sha256",
            "realized_output_sha256",
            "observation_sha256",
        ):
            value = getattr(self, field_name)
            if value is not None:
                _require_sha256(value, field_name=field_name)
        projection = self.model_dump(mode="python", exclude={"provenance_sha256"})
        _require_host_free(
            projection, code="controller_tool_provenance_contains_host_path"
        )
        expected = canonical_sha256(projection)
        if self.provenance_sha256 and self.provenance_sha256 != expected:
            raise ValueError("controller_tool_provenance_sha256_mismatch")
        object.__setattr__(self, "provenance_sha256", expected)
        return self


class ControllerToolObservationV1(FrozenContract):
    protocol: Literal[CONTROLLER_TOOL_OBSERVATION_PROTOCOL] = (
        CONTROLLER_TOOL_OBSERVATION_PROTOCOL
    )
    runtime_protocol: Literal[CONTROLLER_TOOL_RUNTIME_PROTOCOL] = (
        CONTROLLER_TOOL_RUNTIME_PROTOCOL
    )
    session_id: str = Field(min_length=1)
    turn_id: str = Field(min_length=1)
    provider_tool_call_id: str = Field(min_length=1)
    callable_id: str
    resource_id: str = Field(min_length=1)
    capability_operation_id: str = Field(min_length=1)
    entrypoint_id: str = Field(min_length=1)
    status: Literal["success", "failure"]
    resource_call_id: str = Field(min_length=1)
    source_view: Literal["native", "semantic"]
    native_output_sha256: str | None = None
    semantic_output_sha256: str | None = None
    output_realization_contract_sha256: str
    target_contract_sha256: str
    realized_output_sha256: str | None = None
    artifact_type: str = Field(min_length=1)
    public_result: Any
    result_bytes: int = Field(ge=0)
    failure_code: str | None = None
    failure_responsibility: str | None = None
    observation_sha256: str = ""
    provenance_sha256: str

    @model_validator(mode="before")
    @classmethod
    def _canonicalize(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        projected = dict(value)
        if "public_result" in projected:
            projected["public_result"] = _canonical_value(projected["public_result"])
        return projected

    @model_validator(mode="after")
    def _seal(self) -> "ControllerToolObservationV1":
        for field_name in (
            "callable_id",
            "native_output_sha256",
            "semantic_output_sha256",
            "output_realization_contract_sha256",
            "target_contract_sha256",
            "realized_output_sha256",
            "provenance_sha256",
        ):
            value = getattr(self, field_name)
            if value is not None:
                _require_sha256(value, field_name=field_name)
        if self.status == "success":
            if self.failure_code or self.failure_responsibility:
                raise ValueError("successful_controller_tool_observation_has_failure")
            if self.realized_output_sha256 is None:
                raise ValueError("successful_controller_tool_observation_unrealized")
        elif not self.failure_code or not self.failure_responsibility:
            raise ValueError("failed_controller_tool_observation_missing_failure")
        if len(canonical_json_bytes(self.public_result)) != self.result_bytes:
            raise ValueError("controller_tool_observation_result_bytes_mismatch")
        projection = self.model_dump(
            mode="python", exclude={"observation_sha256", "provenance_sha256"}
        )
        _require_host_free(
            {key: value for key, value in projection.items() if key != "public_result"},
            code="controller_tool_observation_contains_host_path",
        )
        _require_public_result_paths(self.public_result)
        expected = canonical_sha256(projection)
        if self.observation_sha256 and self.observation_sha256 != expected:
            raise ValueError("controller_tool_observation_sha256_mismatch")
        object.__setattr__(self, "observation_sha256", expected)
        return self

    def public_projection(self) -> dict[str, Any]:
        projection = self.model_dump(mode="json")
        _require_host_free(
            {key: value for key, value in projection.items() if key != "public_result"},
            code="controller_tool_observation_contains_host_path",
        )
        _require_public_result_paths(self.public_result)
        return projection


def _observation_failure_facts(observation: ControllerToolObservationV1) -> dict[str, Any]:
    """Persist safe diagnostic categories from an already validated observation."""
    if observation.status != "failure":
        return {}
    facts: dict[str, Any] = {"failure_code": observation.failure_code}
    native = observation.public_result.get("native_result")
    if not isinstance(native, Mapping):
        return facts
    reason = native.get("reason_code")
    # Free-form native strings/bodies remain in their original observation,
    # never in the fact ledger. Unknown reason vocabularies retain identity.
    known_reasons = {
        "network_connect_timeout", "network_read_timeout", "network_write_timeout",
        "network_pool_timeout", "network_connect_error", "network_read_error",
        "network_remote_protocol_error", "network_proxy_error", "network_request_failed",
        "redirect_limit_exceeded", "url_protocol_unsupported", "response_too_large",
        "http_status_error", "network_timeout", "network_dns_error",
        "invalid_url", "url_policy_invalid", "url_syntax_invalid", "url_destination_disallowed",
        "destination_outside_workspace", "local_file_io_failed", "acquisition_failed", "redirect_limit",
    }
    if isinstance(reason, str) and reason:
        facts["native_reason_sha256"] = canonical_sha256(reason)
        if reason in known_reasons:
            facts["native_reason_code"] = reason
    status = native.get("http_status")
    if type(status) is int and 100 <= status <= 599:
        facts["http_status"] = status
    return facts


class ControllerToolRuntimeMetricsV1(FrozenContract):
    protocol: Literal[CONTROLLER_TOOL_METRICS_PROTOCOL] = (
        CONTROLLER_TOOL_METRICS_PROTOCOL
    )
    status: Literal["success", "failure"]
    tool_call_count: Literal[1] = 1
    observation_bytes: int = Field(ge=0)
    resource_metrics_authority: Literal["resource_runtime"] = "resource_runtime"
    realization_metrics_authority: Literal["output_realizer"] = "output_realizer"
    model_provider_monetary_cost: Literal[0] = 0


class ControllerToolInvocationResultV1(FrozenContract):
    protocol: Literal[CONTROLLER_TOOL_INVOCATION_RESULT_PROTOCOL] = (
        CONTROLLER_TOOL_INVOCATION_RESULT_PROTOCOL
    )
    observation: ControllerToolObservationV1
    metrics: ControllerToolRuntimeMetricsV1
    result_sha256: str = ""
    _audit_references: _ControllerToolAuditReferences | None = PrivateAttr(default=None)

    def audit_references_for(self, intent: ControllerToolCallIntentV1) -> _ControllerToolAuditReferences:
        """Read only after matching the handoff to the current call."""
        audit = self._audit_references
        if not isinstance(audit, _ControllerToolAuditReferences):
            raise ControllerToolRuntimeError(
                "controller_tool_audit_references_missing",
                failure_stage="controller_tool_observation_consumption",
            )
        if any(getattr(audit, name) != getattr(intent, name) for name in (
            "session_id", "turn_id", "provider_tool_call_id", "callable_id",
        )):
            raise ControllerToolRuntimeError(
                "controller_tool_audit_identity_mismatch",
                failure_stage="controller_tool_observation_consumption",
            )
        return audit

    @model_validator(mode="after")
    def _seal(self) -> "ControllerToolInvocationResultV1":
        expected = canonical_sha256(
            self.model_dump(mode="python", exclude={"result_sha256"})
        )
        if self.result_sha256 and self.result_sha256 != expected:
            raise ValueError("controller_tool_invocation_result_sha256_mismatch")
        object.__setattr__(self, "result_sha256", expected)
        return self


@dataclass(frozen=True)
class ResolvedControllerToolInputs:
    """Private fixed-input resolution; never serialized into observations."""

    values: Mapping[str, Any]
    provenance_source_ids: tuple[str, ...] = ()
    authorized_materials: tuple[MaterialDescriptorV1, ...] = ()
    authorized_material_content: Mapping[str, str] = field(default_factory=dict)
    upstream_artifact_handles: tuple[ArtifactHandle, ...] = ()


@dataclass(frozen=True)
class ControllerToolDispatchContext:
    """Private Orchestrator-owned dispatch material for one sealed call."""

    resource_definition: ResourceDefinition
    execution_context: ResourceExecutionContext
    execution_world: ExecutionWorldDescriptor
    provider: ProviderCallable
    resolved_bindings: Mapping[str, Any]
    semantic_task_contract: Mapping[str, Any]
    acceptance_requirements: tuple[str, ...]
    authorized_materials: tuple[MaterialDescriptorV1, ...] = ()
    authorized_material_content: Mapping[str, str] = field(default_factory=dict)
    upstream_artifact_handles: tuple[ArtifactHandle, ...] = ()
    provenance_source_ids: tuple[str, ...] = ()
    dag_edge_contract_sha256s: tuple[str, ...] = ()


FixedBindingResolver = Callable[
    [ControllerCallableToolSpecV1, ControllerToolCallIntentV1],
    ResolvedControllerToolInputs | Awaitable[ResolvedControllerToolInputs],
]
DispatchContextFactory = Callable[
    [
        ControllerCallableToolSpecV1,
        ControllerToolCallIntentV1,
        Mapping[str, Any],
        ResolvedControllerToolInputs,
    ],
    ControllerToolDispatchContext | Awaitable[ControllerToolDispatchContext],
]


async def _await_if_needed(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


def _input_kind_compatible(value: Any, port: Mapping[str, Any]) -> bool:
    kind = normalize_contract_kind(port)
    if kind == "list":
        return isinstance(value, (list, tuple))
    if kind == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "bool":
        return isinstance(value, bool)
    if kind in {"object", "json"}:
        return isinstance(value, Mapping)
    if kind in {"path", "file_path", "directory_path", "text"}:
        return isinstance(value, str)
    return False


def _validate_complete_inputs(
    values: Mapping[str, Any], spec: ControllerCallableToolSpecV1
) -> None:
    ports = {
        str(item.get("name") or ""): item for item in spec.operation_input_contract
    }
    if set(values) - set(ports):
        raise ControllerToolRuntimeError("controller_tool_complete_input_undeclared")
    missing = {
        name
        for name, port in ports.items()
        if bool(port.get("required", True)) and name not in values
    }
    if missing:
        raise ControllerToolRuntimeError("controller_tool_complete_input_missing")
    if any(not _input_kind_compatible(value, ports[name]) for name, value in values.items()):
        raise ControllerToolRuntimeError("controller_tool_complete_input_contract_mismatch")


class ControllerToolInvocationGateway:
    """Dispatch sealed Controller actions through Resource Runtime and Stage A."""

    def __init__(
        self,
        *,
        callable_tools: Sequence[ControllerCallableToolSpecV1],
        resource_runtime: ResourceRuntime,
        output_realizer: OutputRealizer,
        fixed_binding_resolver: FixedBindingResolver,
        dispatch_context_factory: DispatchContextFactory,
        execution_ledger: Any = None,
        successful_result_observer: Callable[[ResourceCallResult], None] | None = None,
    ) -> None:
        self.callable_tools = tuple(callable_tools)
        self.by_callable_id = {item.callable_id: item for item in self.callable_tools}
        if len(self.by_callable_id) != len(self.callable_tools):
            raise ControllerToolRuntimeError(
                "controller_callable_tool_identity_duplicate"
            )
        self.resource_runtime = resource_runtime
        self.output_realizer = output_realizer
        self.fixed_binding_resolver = fixed_binding_resolver
        self.dispatch_context_factory = dispatch_context_factory
        self.execution_ledger = execution_ledger
        self.successful_result_observer = successful_result_observer

    def _event(self, method: str, **fields: Any) -> bool:
        ledger = self.execution_ledger
        recorder = getattr(ledger, method, None) if ledger is not None else None
        if recorder is not None:
            try:
                recorder(**fields)
            except Exception as exc:
                raise ControllerToolRuntimeError(
                    "controller_tool_event_persistence_failed",
                    failure_stage="controller_tool_accounting",
                ) from exc
            return True
        return False

    @staticmethod
    def _observation_identity(
        *,
        spec: ControllerCallableToolSpecV1,
        intent: ControllerToolCallIntentV1,
        result: ResourceCallResult,
        status: Literal["success", "failure"],
        public_result: Any,
        realized_output_sha256: str | None,
        failure_code: str | None = None,
        failure_responsibility: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        target_sha = canonical_sha256(spec.controller_result_target_contract)
        fields = {
            "session_id": intent.session_id,
            "turn_id": intent.turn_id,
            "provider_tool_call_id": intent.provider_tool_call_id,
            "callable_id": spec.callable_id,
            "resource_id": spec.resource_id,
            "capability_operation_id": spec.capability_operation_id,
            "entrypoint_id": spec.entrypoint_id,
            "status": status,
            "resource_call_id": result.call_id,
            "source_view": spec.controller_result_source_view,
            "native_output_sha256": result.native_output_sha256 or None,
            "semantic_output_sha256": result.semantic_output_sha256,
            "output_realization_contract_sha256": (
                spec.output_realization_contract.contract_sha256
            ),
            "target_contract_sha256": target_sha,
            "realized_output_sha256": realized_output_sha256,
            "artifact_type": normalized_artifact_type(
                spec.controller_result_target_contract.get("artifact_type")
            ),
            "public_result": _canonical_value(public_result),
            "result_bytes": len(canonical_json_bytes(public_result)),
            "failure_code": failure_code,
            "failure_responsibility": failure_responsibility,
        }
        projection = {
            "protocol": CONTROLLER_TOOL_OBSERVATION_PROTOCOL,
            "runtime_protocol": CONTROLLER_TOOL_RUNTIME_PROTOCOL,
            **fields,
        }
        return canonical_sha256(projection), fields

    @staticmethod
    def _provenance(
        *,
        spec: ControllerCallableToolSpecV1,
        intent: ControllerToolCallIntentV1,
        result: ResourceCallResult,
        observation_sha256: str,
        realized_output_sha256: str | None,
    ) -> ControllerToolRuntimeProvenanceV1:
        return ControllerToolRuntimeProvenanceV1(
            session_id=intent.session_id,
            turn_id=intent.turn_id,
            provider_tool_call_id=intent.provider_tool_call_id,
            callable_id=spec.callable_id,
            callable_spec_sha256=spec.callable_spec_sha256,
            provider_tool_schema_sha256=spec.provider_tool_schema_sha256,
            dynamic_arguments_sha256=intent.dynamic_arguments_sha256,
            resource_call_id=result.call_id,
            resource_id=spec.resource_id,
            operation_id=spec.capability_operation_id,
            entrypoint_id=spec.entrypoint_id,
            native_output_sha256=result.native_output_sha256 or None,
            semantic_output_sha256=result.semantic_output_sha256,
            source_view=spec.controller_result_source_view,
            output_realization_contract_sha256=(
                spec.output_realization_contract.contract_sha256
            ),
            target_contract_sha256=canonical_sha256(
                spec.controller_result_target_contract
            ),
            realized_output_sha256=realized_output_sha256,
            observation_sha256=observation_sha256,
        )

    def _build_observation(
        self,
        *,
        spec: ControllerCallableToolSpecV1,
        intent: ControllerToolCallIntentV1,
        result: ResourceCallResult,
        status: Literal["success", "failure"],
        public_result: Any,
        realized_output_sha256: str | None,
        failure_code: str | None = None,
        failure_responsibility: str | None = None,
    ) -> ControllerToolObservationV1:
        observation_sha, fields = self._observation_identity(
            spec=spec,
            intent=intent,
            result=result,
            status=status,
            public_result=public_result,
            realized_output_sha256=realized_output_sha256,
            failure_code=failure_code,
            failure_responsibility=failure_responsibility,
        )
        provenance = self._provenance(
            spec=spec,
            intent=intent,
            result=result,
            observation_sha256=observation_sha,
            realized_output_sha256=realized_output_sha256,
        )
        return ControllerToolObservationV1(
            **fields,
            observation_sha256=observation_sha,
            provenance_sha256=provenance.provenance_sha256,
        )

    def _finish_attempt(
        self, intent: ControllerToolCallIntentV1, state: _ToolAttempt,
        error: ControllerToolRuntimeError | None,
    ) -> ControllerToolTerminalContext:
        """One terminal write attempt; persistence failure never retries it."""
        result = state.result
        observation = state.invocation.observation if state.invocation else None
        realization = state.realization
        failure = error or state.failure
        fields = dict(
            session_id=intent.session_id, turn_id=intent.turn_id,
            provider_tool_call_id=intent.provider_tool_call_id,
            callable_id=intent.callable_id,
            resource_call_id=state.request.call_id if state.request else None,
            resource_dispatched=state.dispatched,
            resource_outcome=("result_received" if result else "unknown" if state.dispatched else "not_dispatched"),
            resource_terminal_event_id=result.terminal_event_id if result else None,
            resource_result_sha256=result.result_sha256 if result else None,
            original_resource_failure=result.failure if result else None,
            usage_reference=result.usage_reference if result else None,
            realization_id=realization.realization_id if realization else None,
            realized_output_sha256=(realization.provenance.realized_output_sha256
                                   if realization and realization.provenance else None),
            observation_sha256=observation.observation_sha256 if observation else None,
            provenance_sha256=observation.provenance_sha256 if observation else None,
            started_persisted=state.started_persisted,
        )
        if state.started_persisted:
            try:
                event_fields = dict(fields)
                event_fields["original_resource_failure"] = (
                    result.failure.model_dump(mode="json") if result and result.failure else None
                )
                state.finished_persisted = self._event(
                    "record_controller_tool_call_finished", **event_fields,
                    status="failure" if error else observation.status if observation else "failure",
                    failure_code=failure.code if failure else None,
                    failure_stage=failure.failure_stage if failure else None,
                    responsibility=failure.responsibility if failure else None,
                    runtime_protocol=CONTROLLER_TOOL_RUNTIME_PROTOCOL,
                )
            except Exception:
                state.secondary_audit_failures += ("controller_tool_terminal_persistence_failed",)
        return ControllerToolTerminalContext(
            **fields,
            failure_code=failure.code if failure else "controller_tool_terminal_persistence_failed",
            failure_stage=failure.failure_stage if failure else "controller_tool_accounting",
            responsibility=failure.responsibility if failure else "framework",
            finished_persisted=state.finished_persisted,
            evidence_incomplete=(
                not state.started_persisted or not state.finished_persisted
                or bool(state.secondary_audit_failures)
                or (state.dispatched and (result is None or not result.terminal_event_id))
            ),
            secondary_audit_failures=state.secondary_audit_failures,
        )

    async def execute_tool_call(
        self, *, intent: ControllerToolCallIntentV1, max_inline_result_bytes: int,
    ) -> ControllerToolInvocationResultV1:
        state = _ToolAttempt()
        error = None
        cancelled = None
        try:
            await self._execute_tool_call(
                intent=intent, max_inline_result_bytes=max_inline_result_bytes, state=state,
            )
        except (asyncio.CancelledError, KeyboardInterrupt, SystemExit) as exc:
            cancelled = exc
            error = ControllerToolRuntimeError("controller_tool_cancelled")
        except BindingProtocolError as exc:
            error = ControllerToolRuntimeError(
                exc.code,
                failure_stage="controller_tool_input_binding",
            )
        except Exception as exc:
            error = state.failure or (
                exc if isinstance(exc, ControllerToolRuntimeError)
                else ControllerToolRuntimeError("controller_tool_boundary_failed")
            )
            if state.failure is not None and exc is not state.failure:
                state.secondary_audit_failures += ("controller_tool_postprocessing_failed",)
            if isinstance(exc, ControllerToolRuntimeError) and exc.failure_stage == "controller_tool_accounting":
                state.secondary_audit_failures += ("controller_tool_event_persistence_failed",)
        context = self._finish_attempt(intent, state, error)
        if cancelled is not None:
            cancelled.terminal_context = context
            raise cancelled
        if error is None and state.secondary_audit_failures:
            error = state.failure or ControllerToolRuntimeError(
                context.failure_code, failure_stage=context.failure_stage,
                responsibility=context.responsibility,
            )
        if error is not None:
            error.terminal_context = context
            error.invocation_result = state.invocation
            raise error
        assert state.invocation is not None
        # Select only audit facts: the success context's failure is a placeholder.
        state.invocation._audit_references = _ControllerToolAuditReferences(**{
            name: getattr(context, name) for name in _ControllerToolAuditReferences.model_fields
        })
        return state.invocation

    async def _execute_tool_call(
        self,
        *,
        intent: ControllerToolCallIntentV1,
        max_inline_result_bytes: int,
        state: _ToolAttempt,
    ) -> ControllerToolInvocationResultV1:
        spec = self.by_callable_id.get(intent.callable_id)
        if spec is None or spec.provider_tool_name != intent.provider_tool_name:
            raise ControllerToolRuntimeError("controller_tool_call_not_authorized")
        _validate_dynamic_arguments(intent.normalized_dynamic_arguments, spec)
        fixed = await _await_if_needed(self.fixed_binding_resolver(spec, intent))
        if not isinstance(fixed, ResolvedControllerToolInputs):
            raise ControllerToolRuntimeError(
                "controller_tool_fixed_binding_resolution_invalid"
            )
        if set(fixed.values) != set(spec.fixed_input_bindings):
            raise ControllerToolRuntimeError(
                "controller_tool_fixed_binding_resolution_mismatch"
            )
        if set(fixed.values) & set(intent.normalized_dynamic_arguments):
            raise ControllerToolRuntimeError("controller_tool_fixed_argument_override")
        complete = {
            **dict(fixed.values),
            **dict(intent.normalized_dynamic_arguments),
        }
        _validate_complete_inputs(complete, spec)
        dispatch = await _await_if_needed(
            self.dispatch_context_factory(spec, intent, complete, fixed)
        )
        if not isinstance(dispatch, ControllerToolDispatchContext):
            raise ControllerToolRuntimeError(
                "controller_tool_dispatch_context_invalid"
            )
        definition = dispatch.resource_definition
        if (
            definition.resource_id != spec.resource_id
            or definition.resource_type != "Tool"
            or definition.manifest_sha256 != spec.resource_manifest_sha256
        ):
            raise ControllerToolRuntimeError(
                "controller_tool_resource_identity_changed"
            )
        entrypoint = definition.entrypoint(spec.entrypoint_id)
        if (
            canonical_sha256(entrypoint.input_contract)
            != canonical_sha256(spec.operation_input_contract)
            or canonical_sha256(entrypoint.output_contract)
            != canonical_sha256(spec.resource_native_output_contract)
        ):
            raise ControllerToolRuntimeError(
                "controller_tool_resource_contract_changed"
            )
        if set(dispatch.resolved_bindings) != set(complete):
            raise ControllerToolRuntimeError(
                "controller_tool_dispatch_binding_names_changed"
            )
        for name in intent.normalized_dynamic_arguments:
            if dispatch.resolved_bindings[name] != intent.normalized_dynamic_arguments[name]:
                raise ControllerToolRuntimeError(
                    "controller_tool_dynamic_argument_changed"
                )
        _validate_complete_inputs(dispatch.resolved_bindings, spec)
        try:
            request = ResourceCallRequest(
                resource_definition=definition,
                entrypoint_id=spec.entrypoint_id,
                execution_context=dispatch.execution_context,
                resolved_bindings=dict(dispatch.resolved_bindings),
                capability_operation_id=spec.capability_operation_id,
                semantic_task_contract=dict(dispatch.semantic_task_contract),
                authorized_materials=dispatch.authorized_materials,
                authorized_material_content=dict(
                    dispatch.authorized_material_content
                ),
                upstream_artifact_handles=dispatch.upstream_artifact_handles,
                acceptance_requirements=dispatch.acceptance_requirements,
                execution_world=dispatch.execution_world,
                resource_native_output_contract=dict(
                    spec.resource_native_output_contract
                ),
                target_output_contract=dict(spec.controller_result_target_contract),
                provenance_source_ids=dispatch.provenance_source_ids,
                dag_edge_contract_sha256s=dispatch.dag_edge_contract_sha256s,
            )
        except (TypeError, ValueError) as exc:
            raise ControllerToolRuntimeError(
                "controller_tool_resource_call_request_invalid"
            ) from exc

        state.request = request
        state.started_persisted = self._event(
            "record_controller_tool_call_started",
            session_id=intent.session_id,
            turn_id=intent.turn_id,
            provider_tool_call_id=intent.provider_tool_call_id,
            callable_id=spec.callable_id,
            callable_spec_sha256=spec.callable_spec_sha256,
            resource_call_id=request.call_id,
            resource_id=spec.resource_id,
            operation_id=spec.capability_operation_id,
            entrypoint_id=spec.entrypoint_id,
            runtime_protocol=CONTROLLER_TOOL_RUNTIME_PROTOCOL,
        )
        state.dispatched = True
        result = await self.resource_runtime.execute(request, provider=dispatch.provider)
        if not isinstance(result, ResourceCallResult):
            raise ControllerToolRuntimeError("controller_tool_resource_result_invalid")
        state.result = result
        if result.failure is not None:
            state.failure = ControllerToolRuntimeError(
                result.failure.failure_code,
                responsibility=result.failure.responsibility,
                failure_stage=result.failure.failure_stage,
            )
        if (
            result.call_id != request.call_id
            or result.resource_id != spec.resource_id
            or result.entrypoint_id != spec.entrypoint_id
            or result.request_sha256 != request.request_sha256
        ):
            raise ControllerToolRuntimeError("controller_tool_result_identity_mismatch")
        if result.execution_audit.get("secondary_audit_failures"):
            state.secondary_audit_failures += ("resource_audit_evidence_incomplete",)
            raise state.failure or ControllerToolRuntimeError("controller_tool_resource_audit_failed")

        terminal_failure: tuple[str, str] | None = None
        if result.status == ResourceCallStatus.SUCCESS:
            source_contract = (
                spec.available_semantic_output_contract
                if spec.controller_result_source_view == "semantic"
                else spec.resource_native_output_contract
            )
            if not isinstance(source_contract, Mapping):
                raise ControllerToolRuntimeError(
                    "controller_tool_result_source_contract_missing"
                )
            realization = self.output_realizer.realize(
                resource_call_id=result.call_id,
                resource_id=spec.resource_id,
                operation_id=spec.capability_operation_id,
                native_value=result.native_value,
                native_content=result.native_content,
                native_output_sha256=result.native_output_sha256,
                semantic_view_available=result.semantic_view_available,
                semantic_value=result.semantic_value,
                semantic_content=result.semantic_content,
                semantic_output_sha256=result.semantic_output_sha256,
                source_contract=source_contract,
                target_contract=spec.controller_result_target_contract,
                contract=spec.output_realization_contract,
            )
            state.realization = realization
            if realization.status != "success" or realization.provenance is None:
                state.failure = ControllerToolRuntimeError(
                    realization.failure_code or "controller_tool_output_realization_failed",
                    failure_stage="controller_tool_output_realization",
                )
            ledger = self.execution_ledger
            if ledger is not None:
                self._event(
                    "record_output_realization",
                    resource_call_id=result.call_id,
                    realization_id=realization.realization_id,
                    realization_kind=realization.metrics.realization_kind,
                    status=realization.status,
                    source_bytes=realization.metrics.source_bytes,
                    target_bytes=realization.metrics.target_bytes,
                    latency_ms=realization.metrics.latency_ms,
                    output_realization_contract_sha256=(
                        spec.output_realization_contract.contract_sha256
                    ),
                    realized_output_sha256=(
                        realization.provenance.realized_output_sha256
                        if realization.provenance is not None
                        else None
                    ),
                    failure_code=realization.failure_code,
                )
            if realization.status != "success" or realization.provenance is None:
                assert state.failure is not None
                raise state.failure
            observation = self._build_observation(
                spec=spec,
                intent=intent,
                result=result,
                status="success",
                public_result=realization.realized_value,
                realized_output_sha256=(
                    realization.provenance.realized_output_sha256
                ),
            )
        else:
            failure = result.failure
            failure_code = (
                failure.failure_code
                if failure is not None
                else "controller_tool_resource_runtime_failed"
            )
            failure_responsibility = (
                failure.responsibility if failure is not None else "framework"
            )
            public_failure = {
                "failure_code": failure_code,
                "reason_sha256": (
                    failure.message_sha256
                    if failure is not None
                    else canonical_sha256(failure_code)
                ),
            }
            diagnostic = _declared_failure_diagnostic(result, spec)
            if diagnostic is not None:
                public_failure["native_result"] = diagnostic
            observation = self._build_observation(
                spec=spec,
                intent=intent,
                result=result,
                status="failure",
                public_result=public_failure,
                realized_output_sha256=None,
                failure_code=failure_code,
                failure_responsibility=failure_responsibility,
            )
            if not tool_failure_allows_continuation(result, spec):
                terminal_failure = (failure_code, failure_responsibility)

        serialized = canonical_json_bytes(observation.public_projection())
        # Size limits apply to the model-visible continuation, never to the
        # successful Tool result or its provenance record.
        provenance = self._provenance(
            spec=spec,
            intent=intent,
            result=result,
            observation_sha256=observation.observation_sha256,
            realized_output_sha256=observation.realized_output_sha256,
        )
        metrics = ControllerToolRuntimeMetricsV1(
            status=observation.status,
            observation_bytes=len(serialized),
        )
        invocation = ControllerToolInvocationResultV1(
            observation=observation,
            metrics=metrics,
        )
        state.invocation = invocation
        if terminal_failure is not None:
            state.failure = state.failure or ControllerToolRuntimeError(
                terminal_failure[0], responsibility=terminal_failure[1]
            )
        self._event(
            "record_controller_tool_observation_created",
            session_id=intent.session_id,
            turn_id=intent.turn_id,
            provider_tool_call_id=intent.provider_tool_call_id,
            callable_id=spec.callable_id,
            resource_call_id=result.call_id,
            observation_sha256=observation.observation_sha256,
            provenance_sha256=provenance.provenance_sha256,
            status=observation.status,
            observation_bytes=len(serialized),
            runtime_protocol=CONTROLLER_TOOL_RUNTIME_PROTOCOL,
            **_observation_failure_facts(observation),
        )
        if terminal_failure is not None:
            assert state.failure is not None
            raise state.failure
        if result.status == ResourceCallStatus.SUCCESS and self.successful_result_observer is not None:
            self.successful_result_observer(result)
        return invocation


__all__ = [
    "CONTROLLER_TOOL_CALL_INTENT_PROTOCOL",
    "CONTROLLER_TOOL_INVOCATION_RESULT_PROTOCOL",
    "CONTROLLER_TOOL_METRICS_PROTOCOL",
    "CONTROLLER_TOOL_OBSERVATION_PROTOCOL",
    "CONTROLLER_TOOL_PROVENANCE_PROTOCOL",
    "CONTROLLER_TOOL_RUNTIME_PROTOCOL",
    "ControllerToolCallIntentV1",
    "ControllerToolDispatchContext",
    "ControllerToolInvocationGateway",
    "ControllerToolInvocationResultV1",
    "ControllerToolObservationV1",
    "ControllerToolRuntimeError",
    "ControllerToolRuntimeMetricsV1",
    "ControllerToolRuntimeProvenanceV1",
    "ResolvedControllerToolInputs",
    "normalize_provider_tool_calls",
    "prevalidate_tool_call_intents",
]
