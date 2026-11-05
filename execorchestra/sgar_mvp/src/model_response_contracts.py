"""Deterministic response-format contracts and capability evidence.

The module is shared by control-plane roles and retrieved Model resources.  It
contains no Case data and never infers capability from provider or model names.
"""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import math
import os
import re
import threading
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, time as datetime_time
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator

from .atomic_io import temporary_sibling_path
from .model_accounting import ModelAccountingError, RunCostLedger
from .model_transport import (
    ModelTransportCapabilityError,
    SyncModelTransportPort,
    classify_transport_exception,
    require_sync_model_transport,
)
from .pipeline_control import FrozenContract, canonical_json_bytes, canonical_sha256


MODEL_RESPONSE_CONTRACT_PROTOCOL = "sgar-model-response-contract-v1"
PORTABLE_WIRE_SCHEMA_PROTOCOL = "sgar-portable-wire-schema-v1"
STRUCTURED_ROLE_CONTRACT_PROTOCOL = "sgar-structured-role-contract-v2"
CAPABILITY_PROBE_PROTOCOL_V1 = "sgar-exact-capability-probe-v1"
CAPABILITY_PROBE_PROTOCOL = "sgar-exact-capability-probe-v2"
CAPABILITY_PROBE_CACHE_PROTOCOL_V1 = "sgar-capability-probe-cache-v1"
CAPABILITY_PROBE_CACHE_PROTOCOL_V2 = "sgar-capability-probe-cache-v2"
CAPABILITY_PROBE_CACHE_PROTOCOL = "sgar-capability-probe-cache-v3"
DEFAULT_PROBE_TTL_SECONDS = 24 * 60 * 60

ProbeOutcome = Literal[
    "live_verified",
    "operator_approved",
    "unsupported",
    "probe_failed",
    "transient_failure",
    "blocked",
    "not_checked",
]
CapabilityProbeEnforcementPolicy = Literal[
    "adaptive_fallback",
    "single_attempt",
]
DEFAULT_CAPABILITY_PROBE_ENFORCEMENT_POLICY: CapabilityProbeEnforcementPolicy = (
    "adaptive_fallback"
)
FormatEnforcementMode = Literal[
    "native_strict_schema",
    "json_object_local_validator",
    "intermediate_text_only",
]
StructuredResponseMode = Literal[
    "native_strict_schema",
    "json_object_local_validator",
]
StructuredResponseModeInput = Literal[
    "native_strict_schema",
    "json_object_local_validator",
    "json_schema",
    "json_object",
]


def normalize_capability_probe_enforcement_policy(
    value: Any = None,
) -> CapabilityProbeEnforcementPolicy:
    if value is None:
        return DEFAULT_CAPABILITY_PROBE_ENFORCEMENT_POLICY
    normalized = str(value).strip()
    if normalized not in {"adaptive_fallback", "single_attempt"}:
        raise ModelResponseContractError(
            "capability_probe_enforcement_policy_invalid"
        )
    return cast(CapabilityProbeEnforcementPolicy, normalized)

STRUCTURED_INGRESS_NORMALIZATION_PROTOCOL = (
    "sgar-structured-ingress-normalization-v1"
)

_LOCAL_SCHEMA_ANNOTATION_KEYWORDS = frozenset(
    {
        "$anchor",
        "$comment",
        "$id",
        "$schema",
        "default",
        "deprecated",
        "description",
        "examples",
        "readOnly",
        "title",
        "writeOnly",
    }
)
_LOCAL_SCHEMA_ASSERTION_KEYWORDS = frozenset(
    {
        "$defs",
        "$ref",
        "additionalProperties",
        "allOf",
        "anyOf",
        "const",
        "definitions",
        "enum",
        "exclusiveMaximum",
        "exclusiveMinimum",
        "format",
        "items",
        "maxItems",
        "maxLength",
        "maxProperties",
        "maximum",
        "minItems",
        "minLength",
        "minProperties",
        "minimum",
        "multipleOf",
        "oneOf",
        "pattern",
        "properties",
        "required",
        "type",
        "uniqueItems",
    }
)
_LOCAL_SCHEMA_TYPES = frozenset(
    {"array", "boolean", "integer", "null", "number", "object", "string"}
)
_LOCAL_SCHEMA_FORMATS = frozenset(
    {
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
    }
)
_RFC3339_DATE_TIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})$"
)
_RFC3339_TIME = re.compile(
    r"^\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})$"
)
_ISO8601_DURATION = re.compile(
    r"^P(?=\d|T\d)(?:\d+Y)?(?:\d+M)?(?:\d+D)?(?:T(?=\d)(?:\d+H)?(?:\d+M)?(?:\d+(?:\.\d+)?S)?)?$"
)
_URI_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*$")
_PERCENT_ESCAPE_INVALID = re.compile(r"%(?![0-9A-Fa-f]{2})")
_JSON_POINTER = re.compile(r"^(?:/(?:[^~/]|~[01])*)*$")
_RELATIVE_JSON_POINTER = re.compile(r"^(?:0|[1-9]\d*)(?:#|(?:/(?:[^~/]|~[01])*)*)$")


class ModelResponseContractError(ValueError):
    pass


class PortableWireSchema(FrozenContract):
    """Provider-facing schema projection with a separate stable identity."""

    protocol: Literal[PORTABLE_WIRE_SCHEMA_PROTOCOL] = PORTABLE_WIRE_SCHEMA_PROTOCOL
    internal_schema_sha256: str
    wire_schema: dict[str, Any]
    wire_schema_sha256: str
    native_eligible: bool = True
    reason_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _seal(self) -> "PortableWireSchema":
        if self.internal_schema_sha256 and len(self.internal_schema_sha256) != 64:
            raise ValueError("portable_wire_internal_schema_hash_invalid")
        expected = canonical_sha256(self.wire_schema)
        if self.wire_schema_sha256 and self.wire_schema_sha256 != expected:
            raise ValueError("portable_wire_schema_hash_mismatch")
        object.__setattr__(self, "wire_schema_sha256", expected)
        object.__setattr__(self, "reason_codes", tuple(sorted(set(self.reason_codes))))
        return self


class StructuredIngressNormalizationV1(FrozenContract):
    """Content-free evidence for deterministic response ingress repair."""

    protocol: Literal["sgar-structured-ingress-normalization-v1"] = (
        "sgar-structured-ingress-normalization-v1"
    )
    extracted_json_object: bool = False
    actions: tuple[str, ...] = ()
    raw_response_sha256: str
    normalized_response_sha256: str
    audit_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "StructuredIngressNormalizationV1":
        object.__setattr__(self, "actions", tuple(dict.fromkeys(self.actions)))
        expected = canonical_sha256(
            self.model_dump(mode="python", exclude={"audit_sha256"})
        )
        if self.audit_sha256 and self.audit_sha256 != expected:
            raise ValueError("structured_ingress_normalization_audit_sha256_mismatch")
        object.__setattr__(self, "audit_sha256", expected)
        return self


def strict_json_loads(value: str) -> Any:
    def reject_constant(token: str) -> None:
        raise ValueError(f"non_finite_json_number:{token}")

    return json.loads(value, parse_constant=reject_constant)


def _canonical_json_value(value: Any) -> Any:
    return json.loads(canonical_json_bytes(value).decode("utf-8"))


def canonicalize_json_schema(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ModelResponseContractError("response_schema_must_be_nonempty_object")
    canonical = _canonical_json_value(dict(value))
    if not isinstance(canonical, dict) or not canonical:
        raise ModelResponseContractError("response_schema_must_be_nonempty_object")
    root_type = canonical.get("type")
    if root_type is not None and not isinstance(root_type, (str, list)):
        raise ModelResponseContractError("response_schema_type_invalid")
    return canonical


_PORTABLE_WIRE_KEYWORDS = frozenset(
    {
        "type",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "enum",
        "anyOf",
    }
)
_PORTABLE_LOCAL_ONLY_KEYWORDS = frozenset(
    {
        "$anchor",
        "$comment",
        "$id",
        "$schema",
        "default",
        "deprecated",
        "description",
        "examples",
        "exclusiveMaximum",
        "exclusiveMinimum",
        "format",
        "maxItems",
        "maxLength",
        "maxProperties",
        "maximum",
        "minItems",
        "minLength",
        "minProperties",
        "minimum",
        "multipleOf",
        "pattern",
        "readOnly",
        "title",
        "uniqueItems",
        "writeOnly",
    }
)


def _schema_allows_null(schema: Mapping[str, Any]) -> bool:
    expected_type = schema.get("type")
    if expected_type == "null":
        return True
    if isinstance(expected_type, Sequence) and not isinstance(expected_type, (str, bytes)):
        if "null" in expected_type:
            return True
    for keyword in ("anyOf", "oneOf"):
        alternatives = schema.get(keyword)
        if isinstance(alternatives, Sequence) and not isinstance(alternatives, (str, bytes)):
            if any(isinstance(item, Mapping) and _schema_allows_null(item) for item in alternatives):
                return True
    return False


def _portable_schema_is_valid(schema: Mapping[str, Any]) -> bool:
    def inspect(node: Mapping[str, Any]) -> bool:
        if any(key not in _PORTABLE_WIRE_KEYWORDS for key in node):
            return False
        expected_type = node.get("type")
        if expected_type is not None:
            declared = (
                [expected_type]
                if isinstance(expected_type, str)
                else list(expected_type)
                if isinstance(expected_type, Sequence)
                and not isinstance(expected_type, (str, bytes))
                else []
            )
            if not declared or any(item not in _LOCAL_SCHEMA_TYPES for item in declared):
                return False
        properties = node.get("properties")
        if properties is not None:
            if not isinstance(properties, Mapping):
                return False
            required = node.get("required")
            if not isinstance(required, Sequence) or isinstance(required, (str, bytes)):
                return False
            if set(str(item) for item in required) != set(str(item) for item in properties):
                return False
            if node.get("additionalProperties") is not False:
                return False
            if not all(isinstance(child, Mapping) and inspect(child) for child in properties.values()):
                return False
        items = node.get("items")
        if items is not None and (not isinstance(items, Mapping) or not inspect(items)):
            return False
        alternatives = node.get("anyOf")
        if alternatives is not None:
            if not isinstance(alternatives, Sequence) or isinstance(alternatives, (str, bytes)):
                return False
            if len(alternatives) != 2 or not all(
                isinstance(item, Mapping) and inspect(item) for item in alternatives
            ):
                return False
            if sum(_schema_allows_null(item) for item in alternatives) != 1:
                return False
        return True

    return inspect(schema)


def _string_literals_require_local_validation(values: Sequence[Any]) -> bool:
    """Multiline text literals are not part of the portable strict wire subset."""
    return any(isinstance(value, str) and ("\n" in value or "\r" in value) for value in values)


def _wire_root_excludes_objects(schema: Mapping[str, Any]) -> bool:
    """A root wrapper is unambiguous only when an internal object is impossible."""
    declared = schema.get("type")
    if isinstance(declared, str):
        return declared != "object"
    if isinstance(declared, list) and declared:
        return "object" not in declared
    alternatives = schema.get("anyOf")
    return bool(isinstance(alternatives, list) and alternatives and all(
        isinstance(item, Mapping) and _wire_root_excludes_objects(item)
        for item in alternatives
    ))


def project_portable_wire_schema(schema: Mapping[str, Any]) -> PortableWireSchema:
    """Project a full internal schema onto SGAR's provider-neutral strict subset."""

    internal = canonicalize_json_schema(schema)
    internal_supported, internal_reasons = local_json_schema_support(internal)
    if not internal_supported:
        raise ModelResponseContractError(
            "portable_wire_internal_schema_unsupported:"
            + ",".join(internal_reasons)
        )
    reasons: set[str] = set()
    native_eligible = True
    def project(node: Mapping[str, Any], *, ref_stack: tuple[str, ...] = ()) -> dict[str, Any]:
        nonlocal native_eligible
        ref = node.get("$ref")
        if ref is not None:
            if not isinstance(ref, str) or not ref.startswith("#/"):
                native_eligible = False
                reasons.add("external_ref_not_portable")
                return {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
            if ref in ref_stack:
                native_eligible = False
                reasons.add("recursive_ref_not_portable")
                return {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
            target = _resolve_schema_ref(internal, ref)
            reasons.add("local_ref_inlined")
            return project(target, ref_stack=ref_stack + (ref,))

        if "allOf" in node or "oneOf" in node:
            native_eligible = False
            reasons.add("complex_union_not_portable")

        any_of = node.get("anyOf")
        if any_of is not None:
            semantic_siblings = set(node) - {
                "anyOf",
                "$defs",
                "definitions",
            } - _PORTABLE_LOCAL_ONLY_KEYWORDS
            if (
                not isinstance(any_of, Sequence)
                or isinstance(any_of, (str, bytes))
                or len(any_of) != 2
                or not all(isinstance(item, Mapping) for item in any_of)
                or sum(_schema_allows_null(item) for item in any_of) != 1
                or bool(semantic_siblings)
            ):
                native_eligible = False
                reasons.add("complex_union_not_portable")
            else:
                return {
                    "anyOf": [
                        project(item, ref_stack=ref_stack)
                        for item in any_of
                        if isinstance(item, Mapping)
                    ]
                }

        projected: dict[str, Any] = {}
        expected_type = node.get("type")
        if isinstance(expected_type, Sequence) and not isinstance(expected_type, (str, bytes)):
            declared_types = list(expected_type)
            non_null_types = [item for item in declared_types if item != "null"]
            if "null" in declared_types and len(non_null_types) == 1:
                projected = {
                    "anyOf": [
                        project(
                            {
                                **{
                                    key: value
                                    for key, value in node.items()
                                    if key != "type"
                                },
                                "type": non_null_types[0],
                            },
                            ref_stack=ref_stack,
                        ),
                        {"type": "null"},
                    ]
                }
                reasons.add("nullable_type_projected_to_any_of")
                return projected
            native_eligible = False
            reasons.add("complex_type_union_not_portable")
        elif expected_type is not None:
            projected["type"] = _canonical_json_value(expected_type)
        if "const" in node:
            projected["enum"] = [_canonical_json_value(node["const"])]
            reasons.add("const_projected_to_enum")
        elif "enum" in node:
            projected["enum"] = _canonical_json_value(node["enum"])

        enum_values = projected.get("enum")
        if isinstance(enum_values, list) and _string_literals_require_local_validation(enum_values):
            if projected.get("type") == "string" or all(isinstance(value, str) for value in enum_values):
                # Keep the full literal constraint in the internal schema and
                # model-visible contract. The provider only enforces its type;
                # local validation still checks exact JSON string equality.
                projected.pop("enum")
                projected.setdefault("type", "string")
                reasons.add("local_only_constraint:multiline_string_literal")
            else:
                # Do not invent a root type for mixed or composite literals.
                # Existing capability admission decides whether another mode
                # is authorized; projection does not enable a fallback itself.
                native_eligible = False
                reasons.add("multiline_literal_without_portable_string_type")

        properties = node.get("properties")
        is_object = expected_type == "object" or isinstance(properties, Mapping)
        if is_object:
            if not isinstance(properties, Mapping):
                properties = {}
            additional = node.get("additionalProperties")
            if additional is not False and not properties:
                native_eligible = False
                reasons.add("dynamic_object_not_portable")
            elif additional is not None and additional is not False:
                native_eligible = False
                reasons.add("dynamic_object_not_portable")
            original_required = {
                str(item)
                for item in node.get("required", ())
                if isinstance(item, str)
            }
            projected_properties: dict[str, Any] = {}
            for key, child in sorted(properties.items(), key=lambda item: str(item[0])):
                if not isinstance(child, Mapping):
                    raise ModelResponseContractError("portable_wire_property_schema_invalid")
                child_projection = project(child, ref_stack=ref_stack)
                if str(key) not in original_required and not _schema_allows_null(child):
                    child_projection = {
                        "anyOf": [child_projection, {"type": "null"}],
                    }
                    reasons.add("optional_property_uses_null_sentinel")
                projected_properties[str(key)] = child_projection
            projected["properties"] = projected_properties
            projected["required"] = sorted(projected_properties)
            projected["additionalProperties"] = False

        if expected_type == "array" or "items" in node:
            items = node.get("items")
            if not isinstance(items, Mapping):
                native_eligible = False
                reasons.add("array_items_not_portable")
            else:
                projected["items"] = project(items, ref_stack=ref_stack)

        for keyword in node:
            if keyword in _PORTABLE_LOCAL_ONLY_KEYWORDS:
                reasons.add(f"local_only_keyword:{keyword}")
            elif keyword not in _PORTABLE_WIRE_KEYWORDS | {
                "$defs",
                "$ref",
                "definitions",
                "const",
                "allOf",
                "oneOf",
            }:
                native_eligible = False
                reasons.add(f"unsupported_keyword:{keyword}")
        if not projected:
            native_eligible = False
            reasons.add("unconstrained_schema_not_portable")
            projected = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
        return projected

    wire_schema = canonicalize_json_schema(project(internal))
    if _wire_root_excludes_objects(wire_schema):
        # Providers require an object at the wire root. The task's array/scalar
        # schema remains authoritative; only the transport representation changes.
        wire_schema = canonicalize_json_schema({
            "type": "object", "properties": {"value": wire_schema},
            "required": ["value"], "additionalProperties": False,
        })
        reasons.add("root_value_enveloped")
    elif wire_schema.get("type") != "object":
        # An object-valued union could make automatic unwrapping ambiguous.
        native_eligible = False
        reasons.add("root_object_union_not_portable")
    if not _portable_schema_is_valid(wire_schema):
        raise ModelResponseContractError("portable_wire_schema_projection_invalid")
    return PortableWireSchema(
        internal_schema_sha256=canonical_sha256(internal),
        wire_schema=wire_schema,
        wire_schema_sha256=canonical_sha256(wire_schema),
        native_eligible=native_eligible,
        reason_codes=tuple(reasons),
    )


def _normalized_enum_token(value: str) -> str:
    return re.sub(r"[-\s]+", "_", value.strip().casefold())


def normalize_portable_wire_instance(
    value: Any,
    schema: Mapping[str, Any],
    *,
    actions: list[str] | None = None,
) -> Any:
    """Losslessly normalize portable wire mechanics before local validation.

    Only unambiguous schema-directed repairs are permitted: optional null
    sentinels are omitted, forbidden extra keys are ignored, and string
    const/enum values are canonicalized when exactly one declared value matches.
    Required semantic fields and unknown values are never synthesized.
    """

    root = schema
    recorded_actions = actions if actions is not None else []
    if isinstance(value, Mapping) and set(value) == {"value"}:
        projection = project_portable_wire_schema(schema)
        if "root_value_enveloped" in projection.reason_codes:
            value = value["value"]
            recorded_actions.append("root_value_unwrapped:$")

    def normalize(item: Any, node: Mapping[str, Any], path: str) -> Any:
        if "$ref" in node:
            return normalize(
                item,
                _resolve_schema_ref(root, str(node["$ref"])),
                path,
            )
        for keyword in ("anyOf", "oneOf"):
            alternatives = node.get(keyword)
            if isinstance(alternatives, Sequence) and not isinstance(alternatives, (str, bytes)):
                valid_candidates: dict[str, tuple[Any, list[str]]] = {}
                for alternative in alternatives:
                    if not isinstance(alternative, Mapping):
                        continue
                    candidate_actions: list[str] = []
                    candidate = normalize_with_actions(
                        item,
                        alternative,
                        path,
                        candidate_actions,
                    )
                    valid, _reason = validate_json_schema_instance(
                        candidate,
                        alternative,
                        root_schema=root,
                    )
                    if valid:
                        key = canonical_json_bytes(candidate).decode("utf-8")
                        valid_candidates[key] = (candidate, candidate_actions)
                if len(valid_candidates) == 1:
                    candidate, candidate_actions = next(
                        iter(valid_candidates.values())
                    )
                    recorded_actions.extend(candidate_actions)
                    return candidate
        if isinstance(item, dict):
            properties = node.get("properties")
            properties = properties if isinstance(properties, Mapping) else {}
            required = {str(name) for name in node.get("required", ())}
            additional = node.get("additionalProperties", True)
            normalized: dict[str, Any] = {}
            for key, child in item.items():
                child_schema = properties.get(key)
                if not isinstance(child_schema, Mapping):
                    child_path = f"{path}.{key}"
                    if additional is False:
                        recorded_actions.append(f"extra_field_removed:{child_path}")
                        continue
                    if isinstance(additional, Mapping):
                        normalized[key] = normalize(child, additional, child_path)
                        continue
                    normalized[key] = child
                    continue
                if child is None and key not in required and not _schema_allows_null(child_schema):
                    recorded_actions.append(
                        f"optional_null_omitted:{path}.{key}"
                    )
                    continue
                normalized[key] = normalize(child, child_schema, f"{path}.{key}")
            return normalized
        if isinstance(item, list) and isinstance(node.get("items"), Mapping):
            return [
                normalize(child, node["items"], f"{path}[{index}]")
                for index, child in enumerate(item)
            ]
        if isinstance(item, str):
            declared: list[str] = []
            if isinstance(node.get("const"), str):
                declared.append(str(node["const"]))
            enum_values = node.get("enum")
            if isinstance(enum_values, Sequence) and not isinstance(
                enum_values, (str, bytes)
            ):
                declared.extend(str(value) for value in enum_values if isinstance(value, str))
            if declared and item not in declared and not _string_literals_require_local_validation(declared):
                # Multiline literals carry exact content, not spelling aliases.
                # Never replace missing line breaks, casing or whitespace with
                # a declared answer before the full local contract check.
                token = _normalized_enum_token(item)
                matches = [
                    value for value in dict.fromkeys(declared)
                    if _normalized_enum_token(value) == token
                ]
                if len(matches) == 1:
                    recorded_actions.append(f"enum_canonicalized:{path}")
                    return matches[0]
        return item

    def normalize_with_actions(
        item: Any,
        node: Mapping[str, Any],
        path: str,
        child_actions: list[str],
    ) -> Any:
        nonlocal recorded_actions
        parent_actions = recorded_actions
        recorded_actions = child_actions
        try:
            return normalize(item, node, path)
        finally:
            recorded_actions = parent_actions

    return normalize(value, root, "$")


def _balanced_json_object_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    escaped = False
    for index, character in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == "{":
            if depth == 0:
                start = index
            depth += 1
        elif character == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                candidates.append(text[start : index + 1])
                start = None
    return candidates


def _decode_unique_json_object(content: str) -> tuple[Any, bool]:
    try:
        return strict_json_loads(content), False
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    decoded_objects: list[Any] = []
    # Balanced top-level scanning also sees an object inside a Markdown fence,
    # without counting that same lexical object twice.  Count occurrences, not
    # content hashes: two identical objects are still an ambiguous response.
    for candidate in _balanced_json_object_candidates(content or ""):
        try:
            decoded = strict_json_loads(candidate)
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
        if not isinstance(decoded, Mapping):
            continue
        decoded_objects.append(decoded)
    if len(decoded_objects) != 1:
        raise ModelResponseContractError("structured_response_json_invalid")
    return decoded_objects[0], True


def normalize_structured_response_content(
    content: str,
    *,
    requirement: "OutputFormatRequirement",
    mode: str,
    instance_normalizer: Callable[
        [Any], tuple[Any, Sequence[str]]
    ] | None = None,
) -> tuple[Any, StructuredIngressNormalizationV1]:
    """Normalize one structured response and return content-free audit evidence."""

    decoded, extracted = _decode_unique_json_object(content)
    actions: list[str] = []
    normalize_structured_response_mode(mode)
    decoded = normalize_portable_wire_instance(
        decoded,
        requirement.json_schema or {},
        actions=actions,
    )
    if instance_normalizer is not None:
        decoded, role_actions = instance_normalizer(decoded)
        actions.extend(str(action) for action in role_actions)
    valid, reason = validate_json_schema_instance(
        decoded,
        requirement.json_schema or {},
    )
    if not valid:
        raise ModelResponseContractError(
            f"structured_response_schema_invalid:{reason or 'unknown'}"
        )
    audit = StructuredIngressNormalizationV1(
        extracted_json_object=extracted,
        actions=tuple(actions),
        raw_response_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        normalized_response_sha256=canonical_sha256(decoded),
    )
    return decoded, audit


def project_portable_wire_instance(value: Any, schema: Mapping[str, Any]) -> Any:
    """Project one valid internal value onto the strict portable wire shape."""

    internal = canonicalize_json_schema(schema)
    projection = project_portable_wire_schema(internal)
    if not projection.native_eligible:
        raise ModelResponseContractError("portable_wire_instance_not_native_eligible")
    valid, reason = validate_json_schema_instance(value, internal)
    if not valid:
        raise ModelResponseContractError(
            f"portable_wire_internal_instance_invalid:{reason or 'unknown'}"
        )

    def nullable_wire_non_null_branch(
        node: Mapping[str, Any],
    ) -> Mapping[str, Any] | None:
        union_keywords = [
            keyword for keyword in ("anyOf", "oneOf") if keyword in node
        ]
        if len(union_keywords) != 1 or set(node) != {union_keywords[0]}:
            return None
        alternatives = node.get(union_keywords[0])
        if (
            not isinstance(alternatives, Sequence)
            or isinstance(alternatives, (str, bytes))
            or len(alternatives) != 2
            or not all(isinstance(alternative, Mapping) for alternative in alternatives)
        ):
            return None
        null_indexes = [
            index
            for index, alternative in enumerate(alternatives)
            if set(alternative) == {"type"} and alternative.get("type") == "null"
        ]
        if len(null_indexes) != 1:
            return None
        non_null = alternatives[1 - null_indexes[0]]
        return non_null if isinstance(non_null, Mapping) else None

    def project(item: Any, node: Mapping[str, Any], wire: Mapping[str, Any]) -> Any:
        if "$ref" in node:
            return project(item, _resolve_schema_ref(internal, str(node["$ref"])), wire)
        for keyword in ("anyOf", "oneOf"):
            alternatives = node.get(keyword)
            semantic_wire = wire
            if not _schema_allows_null(node):
                wrapped_semantic_wire = nullable_wire_non_null_branch(wire)
                if wrapped_semantic_wire is not None:
                    semantic_wire = wrapped_semantic_wire
            wire_alternatives = semantic_wire.get("anyOf")
            if wire_alternatives is None:
                wire_alternatives = semantic_wire.get("oneOf")
            if (
                isinstance(alternatives, Sequence)
                and not isinstance(alternatives, (str, bytes))
                and isinstance(wire_alternatives, Sequence)
                and not isinstance(wire_alternatives, (str, bytes))
                and len(wire_alternatives) == len(alternatives)
            ):
                for index, alternative in enumerate(alternatives):
                    if not isinstance(alternative, Mapping):
                        continue
                    alternative_valid, _ = validate_json_schema_instance(
                        item,
                        alternative,
                        root_schema=internal,
                    )
                    if alternative_valid:
                        wire_alternative = wire_alternatives[index]
                        if not isinstance(wire_alternative, Mapping):
                            raise ModelResponseContractError(
                                "portable_wire_instance_union_branch_invalid"
                            )
                        return project(item, alternative, wire_alternative)
        if item is not None:
            non_null_wire = nullable_wire_non_null_branch(wire)
            if non_null_wire is not None:
                wire = non_null_wire
        if isinstance(item, dict):
            properties = node.get("properties")
            properties = properties if isinstance(properties, Mapping) else {}
            wire_properties = wire.get("properties")
            wire_properties = (
                wire_properties if isinstance(wire_properties, Mapping) else {}
            )
            projected: dict[str, Any] = {}
            for key, wire_child in wire_properties.items():
                if not isinstance(wire_child, Mapping):
                    raise ModelResponseContractError(
                        "portable_wire_instance_property_schema_invalid"
                    )
                child = properties.get(key)
                if key not in item:
                    projected[str(key)] = None
                    continue
                if not isinstance(child, Mapping):
                    raise ModelResponseContractError(
                        "portable_wire_instance_internal_property_missing"
                    )
                projected[str(key)] = project(item[key], child, wire_child)
            return projected
        if isinstance(item, list):
            child = node.get("items")
            wire_child = wire.get("items")
            if isinstance(child, Mapping) and isinstance(wire_child, Mapping):
                return [project(entry, child, wire_child) for entry in item]
        return item

    if "root_value_enveloped" in projection.reason_codes:
        value_schema = projection.wire_schema["properties"]["value"]
        wire_value = {"value": project(value, internal, value_schema)}
    else:
        wire_value = project(value, internal, projection.wire_schema)
    wire_valid, wire_reason = validate_json_schema_instance(
        wire_value,
        projection.wire_schema,
    )
    if not wire_valid:
        raise ModelResponseContractError(
            f"portable_wire_instance_invalid:{wire_reason or 'unknown'}"
        )
    return wire_value


def structured_response_format(
    requirement: "OutputFormatRequirement",
    *,
    mode: Literal["native_strict_schema", "json_object_local_validator"],
) -> dict[str, Any]:
    if mode == "json_object_local_validator":
        return structured_response_format_from_contract(
            mode=mode,
            requirement_sha256=requirement.requirement_sha256,
        )
    projection = requirement.portable_wire_schema
    if projection is None or not projection.native_eligible:
        raise ModelResponseContractError("portable_wire_schema_not_native_eligible")
    return structured_response_format_from_contract(
        mode=mode,
        requirement_sha256=requirement.requirement_sha256,
        wire_schema=projection.wire_schema,
        wire_schema_sha256=projection.wire_schema_sha256,
    )


def structured_response_format_from_contract(
    *,
    mode: str,
    requirement_sha256: str,
    wire_schema: Mapping[str, Any] | None = None,
    wire_schema_sha256: str | None = None,
) -> dict[str, Any]:
    """Build a response format from a frozen format-contract projection."""

    selected_mode = normalize_structured_response_mode(mode)
    normalized_requirement_hash = str(requirement_sha256).strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", normalized_requirement_hash):
        raise ModelResponseContractError("structured_response_requirement_hash_invalid")
    if selected_mode == "json_object_local_validator":
        return {"type": "json_object"}
    if not isinstance(wire_schema, Mapping):
        raise ModelResponseContractError("structured_response_wire_schema_missing")
    canonical_wire_schema = canonicalize_json_schema(wire_schema)
    if not _portable_schema_is_valid(canonical_wire_schema):
        raise ModelResponseContractError("structured_response_wire_schema_invalid")
    expected_wire_hash = canonical_sha256(canonical_wire_schema)
    if wire_schema_sha256 is not None and str(wire_schema_sha256) != expected_wire_hash:
        raise ModelResponseContractError("structured_response_wire_schema_hash_mismatch")
    return {
        "type": "json_schema",
        "json_schema": {
            "name": f"sgar_{normalized_requirement_hash[:24]}",
            "strict": True,
            "schema": canonical_wire_schema,
        },
    }


def normalize_structured_response_mode(
    value: StructuredResponseModeInput | str,
) -> StructuredResponseMode:
    normalized = str(value).strip()
    aliases: dict[str, StructuredResponseMode] = {
        "json_schema": "native_strict_schema",
        "json_object": "json_object_local_validator",
        "native_strict_schema": "native_strict_schema",
        "json_object_local_validator": "json_object_local_validator",
    }
    try:
        return aliases[normalized]
    except KeyError as exc:
        raise ModelResponseContractError("structured_response_mode_invalid") from exc


class StructuredRoleContractV2(FrozenContract):
    """One auditable contract shared by a structured role's prompt and validator."""

    protocol: Literal[STRUCTURED_ROLE_CONTRACT_PROTOCOL] = STRUCTURED_ROLE_CONTRACT_PROTOCOL
    role: str = Field(min_length=1)
    model_output_schema: dict[str, Any]
    portable_wire_schema: dict[str, Any]
    selected_response_mode: StructuredResponseMode
    dynamic_invariant: dict[str, Any] = Field(default_factory=dict)
    prompt_contract: dict[str, Any] = Field(default_factory=dict)
    projector_version: str = "none"
    model_schema_sha256: str = ""
    post_validator_schema_sha256: str = ""
    wire_schema_sha256: str = ""
    invariant_sha256: str = ""
    request_invariant_sha256: str = ""
    domain_validator_invariant_sha256: str = ""
    prompt_contract_sha256: str = ""
    projector_sha256: str = ""
    contract_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "StructuredRoleContractV2":
        schema = canonicalize_json_schema(self.model_output_schema)
        wire = canonicalize_json_schema(self.portable_wire_schema)
        if not _portable_schema_is_valid(wire):
            raise ModelResponseContractError("structured_role_wire_schema_invalid")
        domain_invariant_hash = canonical_sha256(self.dynamic_invariant)
        request_invariant = self.prompt_contract.get(
            "dynamic_invariant",
            self.dynamic_invariant,
        )
        request_invariant_hash = canonical_sha256(request_invariant)
        # Compiler roles intentionally expose a strict model-owned subset of
        # the complete local validator contract.  Both identities remain
        # sealed independently.  Other structured roles retain the original
        # parity requirement so this compiler-only split cannot widen their
        # model-facing contract accidentally.
        if (
            request_invariant_hash != domain_invariant_hash
            and self.role not in {"plan_compiler", "plan_adaptation"}
        ):
            raise ModelResponseContractError(
                "structured_role_invariant_parity_mismatch"
            )
        prompt_hash = canonical_sha256(self.prompt_contract)
        projector_hash = canonical_sha256(
            {"version": self.projector_version, "role": self.role}
        )
        contract_projection = self.model_dump(
            mode="python",
            exclude={
                "model_schema_sha256",
                "post_validator_schema_sha256",
                "wire_schema_sha256",
                "invariant_sha256",
                "request_invariant_sha256",
                "domain_validator_invariant_sha256",
                "prompt_contract_sha256",
                "projector_sha256",
                "contract_sha256",
            },
        )
        expected = canonical_sha256(contract_projection)
        supplied = {
            "model_schema_sha256": self.model_schema_sha256,
            "post_validator_schema_sha256": self.post_validator_schema_sha256,
            "wire_schema_sha256": self.wire_schema_sha256,
            "invariant_sha256": self.invariant_sha256,
            "request_invariant_sha256": self.request_invariant_sha256,
            "domain_validator_invariant_sha256": self.domain_validator_invariant_sha256,
            "prompt_contract_sha256": self.prompt_contract_sha256,
            "projector_sha256": self.projector_sha256,
            "contract_sha256": self.contract_sha256,
        }
        expected_values = {
            "model_schema_sha256": canonical_sha256(schema),
            "post_validator_schema_sha256": canonical_sha256(schema),
            "wire_schema_sha256": canonical_sha256(wire),
            "invariant_sha256": domain_invariant_hash,
            "request_invariant_sha256": request_invariant_hash,
            "domain_validator_invariant_sha256": domain_invariant_hash,
            "prompt_contract_sha256": prompt_hash,
            "projector_sha256": projector_hash,
            "contract_sha256": expected,
        }
        for field_name, value in supplied.items():
            if value and value != expected_values[field_name]:
                raise ModelResponseContractError(f"{field_name}_mismatch")
            object.__setattr__(self, field_name, expected_values[field_name])
        object.__setattr__(self, "model_output_schema", schema)
        object.__setattr__(self, "portable_wire_schema", wire)
        return self


def _role_dynamic_invariant(role: str) -> dict[str, Any]:
    normalized = str(role).strip().lower()
    common = {
        "no_extra_fields": True,
        "response_is_single_json_object": True,
        "model_must_not_emit_framework_identity": True,
    }
    if normalized == "plan_compiler":
        return {
            **common,
            "catalog": "compiler_invariant_catalog_v2",
            "final_output_requires_subtask_contract": True,
            "literal_json_must_parse": True,
            "step_output_requires_declared_dependency": True,
            "model_owned_projection_round_trip": True,
        }
    if normalized == "plan_adaptation":
        return {
            **common,
            "catalog": "compiler_invariant_catalog_v2",
            "preserved_checkpoints_unchanged": True,
            "rerun_forbidden_signatures_unchanged": True,
        }
    if normalized == "evaluator":
        return {
            **common,
            "catalog": "evaluation_slot_invariant_catalog_v2",
            "criterion_slots_exactly_once": True,
            "evidence_slots_must_be_scoped": True,
            "pass_or_fail_requires_evidence": True,
            "repairability_only_for_fail": True,
            "framework_aggregates_verdict_and_label": True,
        }
    return common


def build_structured_role_contract(
    role: str,
    *,
    mode: StructuredResponseModeInput,
    planner_require_capability_fields: bool = False,
    projector_version: str = "none",
    request_dynamic_invariant: Mapping[str, Any] | None = None,
    domain_validator_dynamic_invariant: Mapping[str, Any] | None = None,
) -> StructuredRoleContractV2:
    selected_mode = normalize_structured_response_mode(mode)
    model_schema = system_role_schema(
        role,
        planner_require_capability_fields=planner_require_capability_fields,
    )
    requirement = OutputFormatRequirement(
        artifact_type="json",
        structured=True,
        strict_required=True,
        json_schema=model_schema,
        schema_source=f"system_role.{str(role).strip().lower()}",
    )
    wire = (
        requirement.portable_wire_schema.wire_schema
        if requirement.portable_wire_schema is not None
        else {}
    )
    default_invariant = _role_dynamic_invariant(role)
    request_invariant = dict(request_dynamic_invariant or default_invariant)
    domain_invariant = dict(domain_validator_dynamic_invariant or default_invariant)
    prompt_contract = {
        "model_output_schema": model_schema,
        "selected_response_mode": selected_mode,
        "dynamic_invariant": request_invariant,
        "projector_version": projector_version,
    }
    return StructuredRoleContractV2(
        role=str(role).strip().lower(),
        model_output_schema=model_schema,
        portable_wire_schema=wire,
        selected_response_mode=selected_mode,
        dynamic_invariant=domain_invariant,
        prompt_contract=prompt_contract,
        projector_version=projector_version,
    )


def structured_role_prompt_projection(
    contract: StructuredRoleContractV2,
    *,
    selected_mode: StructuredResponseModeInput | None = None,
) -> dict[str, Any]:
    """Project exactly one authoritative schema placement for a model boundary.

    Native strict providers receive the wire schema only in ``response_format``.
    JSON-object providers receive the internal schema once in the prompt for the
    local validator.  Hashes remain visible in both modes without duplicating
    internal, wire, and validator schemas.
    """

    mode = normalize_structured_response_mode(
        selected_mode if selected_mode is not None else contract.selected_response_mode
    )
    projection: dict[str, Any] = {
        "protocol": contract.protocol,
        "role": contract.role,
        "selected_response_mode": mode,
        "dynamic_invariant": contract.prompt_contract["dynamic_invariant"],
        "projector_version": contract.projector_version,
        "model_schema_sha256": contract.model_schema_sha256,
        "post_validator_schema_sha256": contract.post_validator_schema_sha256,
        "wire_schema_sha256": contract.wire_schema_sha256,
        "invariant_sha256": contract.invariant_sha256,
        "request_invariant_sha256": contract.request_invariant_sha256,
        "domain_validator_invariant_sha256": contract.domain_validator_invariant_sha256,
        "prompt_contract_sha256": contract.prompt_contract_sha256,
        "projector_sha256": contract.projector_sha256,
        "contract_sha256": contract.contract_sha256,
    }
    if mode == "json_object_local_validator":
        projection["authoritative_schema"] = contract.model_output_schema
    return projection


def validate_structured_response_content(
    content: str,
    *,
    requirement: "OutputFormatRequirement",
    mode: str,
) -> Any:
    decoded, _audit = normalize_structured_response_content(
        content,
        requirement=requirement,
        mode=mode,
    )
    return decoded


def system_role_response_format(
    role: str,
    *,
    mode: Literal["native_strict_schema", "json_object_local_validator"],
    planner_require_capability_fields: bool = False,
) -> dict[str, Any]:
    return structured_response_format(
        system_role_requirement(
            role,
            planner_require_capability_fields=planner_require_capability_fields,
        ),
        mode=mode,
    )


def _schema_candidates(projection: Any) -> list[tuple[str, dict[str, Any]]]:
    candidates: list[tuple[str, dict[str, Any]]] = []
    if hasattr(projection, "json_schema"):
        explicit = getattr(projection, "json_schema", None)
        if explicit is None:
            return []
        if not isinstance(explicit, Mapping):
            raise ModelResponseContractError("typed_output_schema_must_be_object")
        return [
            (
                "json_schema",
                canonicalize_json_schema(cast(Mapping[str, Any], explicit)),
            )
        ]
    interface = getattr(projection, "interface_contract", {})
    if isinstance(interface, Mapping):
        for key in ("json_schema", "output_schema", "schema"):
            value = interface.get(key)
            if isinstance(value, Mapping):
                candidates.append((f"interface_contract.{key}", canonicalize_json_schema(value)))
    for index, produced in enumerate(getattr(projection, "produced_files", ()) or ()):
        value = getattr(produced, "schema_hint", None)
        if isinstance(value, Mapping):
            candidates.append(
                (f"produced_files[{index}].schema_hint", canonicalize_json_schema(value))
            )
    return candidates


def require_semantic_json_schema(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return a canonical, locally enforceable, non-vacuous JSON Schema.

    A bare object schema is not an output contract: it proves only that the
    provider returned braces. Object roots must therefore be closed or have a
    typed additional-properties contract, and arrays must declare item shape.
    """

    schema = canonicalize_json_schema(value)
    supported, reasons = local_json_schema_support(schema)
    if not supported:
        reason = reasons[0] if reasons else "unknown"
        raise ModelResponseContractError(
            f"typed_output_schema_not_locally_enforceable:{reason}"
        )
    def require_node(
        node: Mapping[str, Any],
        *,
        locator: str,
        ref_stack: tuple[str, ...] = (),
    ) -> None:
        declared_type = node.get("type")
        declared_types: set[str] = set()
        if isinstance(declared_type, str):
            declared_types.add(declared_type)
        elif isinstance(declared_type, Sequence) and not isinstance(
            declared_type,
            (str, bytes),
        ):
            declared_type_values = cast(Sequence[Any], declared_type)
            if not all(isinstance(item, str) for item in declared_type_values):
                raise ModelResponseContractError(
                    f"typed_output_schema_type_invalid:{locator}"
                )
            declared_types.update(cast(Sequence[str], declared_type_values))
        alternatives = tuple(
            key for key in ("allOf", "anyOf", "oneOf") if key in node
        )
        if (
            not declared_types
            and not alternatives
            and "$ref" not in node
            and "const" not in node
            and "enum" not in node
        ):
            raise ModelResponseContractError(
                f"typed_output_schema_root_type_missing:{locator}"
            )
        if "$ref" in node:
            ref = str(node["$ref"])
            if ref in ref_stack:
                raise ModelResponseContractError(
                    f"typed_output_schema_recursive_ref:{locator}"
                )
            require_node(
                _resolve_schema_ref(schema, ref),
                locator=f"{locator}.$ref",
                ref_stack=(*ref_stack, ref),
            )
        for keyword in alternatives:
            branches = node.get(keyword)
            if (
                not isinstance(branches, Sequence)
                or isinstance(branches, (str, bytes))
                or not branches
            ):
                raise ModelResponseContractError(
                    f"typed_output_schema_combinator_empty:{locator}.{keyword}"
                )
            for index, branch in enumerate(cast(Sequence[Any], branches)):
                if not isinstance(branch, Mapping) or not branch:
                    raise ModelResponseContractError(
                        f"typed_output_schema_combinator_branch_vacuous:"
                        f"{locator}.{keyword}[{index}]"
                    )
                require_node(
                    cast(Mapping[str, Any], branch),
                    locator=f"{locator}.{keyword}[{index}]",
                    ref_stack=ref_stack,
                )
        if "object" in declared_types:
            properties = node.get("properties")
            additional = node.get("additionalProperties")
            properties_mapping = (
                cast(Mapping[str, Any], properties)
                if isinstance(properties, Mapping)
                else None
            )
            additional_mapping = (
                cast(Mapping[str, Any], additional)
                if isinstance(additional, Mapping)
                else None
            )
            has_properties = bool(properties_mapping)
            typed_mapping = bool(additional_mapping)
            if not has_properties and not typed_mapping:
                raise ModelResponseContractError(
                    f"typed_output_schema_object_vacuous:{locator}"
                )
            if additional is None or additional is True:
                raise ModelResponseContractError(
                    f"typed_output_schema_object_open:{locator}"
                )
            required = node.get("required", ())
            if required is not None and not isinstance(required, (list, tuple)):
                raise ModelResponseContractError(
                    f"typed_output_schema_required_invalid:{locator}"
                )
            if isinstance(required, (list, tuple)) and any(
                not isinstance(item, str)
                or properties_mapping is None
                or item not in properties_mapping
                for item in cast(Sequence[Any], required)
            ):
                raise ModelResponseContractError(
                    f"typed_output_schema_required_unknown_property:{locator}"
                )
            for name, child in (properties_mapping or {}).items():
                if not isinstance(child, Mapping) or not child:
                    raise ModelResponseContractError(
                        f"typed_output_schema_property_vacuous:{locator}.properties.{name}"
                    )
                require_node(
                    cast(Mapping[str, Any], child),
                    locator=f"{locator}.properties.{name}",
                    ref_stack=ref_stack,
                )
            if additional_mapping is not None:
                require_node(
                    additional_mapping,
                    locator=f"{locator}.additionalProperties",
                    ref_stack=ref_stack,
                )
        if "array" in declared_types:
            items = node.get("items")
            if not isinstance(items, Mapping) or not items:
                raise ModelResponseContractError(
                    f"typed_output_schema_array_items_missing:{locator}"
                )
            require_node(
                cast(Mapping[str, Any], items),
                locator=f"{locator}.items",
                ref_stack=ref_stack,
            )

    require_node(schema, locator="$")
    return schema


class OutputFormatRequirement(FrozenContract):
    protocol: Literal[MODEL_RESPONSE_CONTRACT_PROTOCOL] = MODEL_RESPONSE_CONTRACT_PROTOCOL
    artifact_type: str = Field(min_length=1)
    structured: bool
    strict_required: bool
    json_schema: dict[str, Any] | None = None
    schema_source: str = "none"
    input_modality: str = "text"
    requirement_sha256: str = ""

    @field_validator("json_schema", mode="before")
    @classmethod
    def _canonical_schema(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, Mapping):
            raise ValueError("output_format_schema_must_be_object")
        return canonicalize_json_schema(value)

    @model_validator(mode="after")
    def _seal(self) -> "OutputFormatRequirement":
        if self.strict_required and not self.structured:
            raise ValueError("strict_output_format_must_be_structured")
        if self.json_schema is not None and not self.structured:
            raise ValueError("schema_requires_structured_output")
        projected = self.model_dump(mode="python", exclude={"requirement_sha256"})
        expected = canonical_sha256(projected)
        if self.requirement_sha256 and self.requirement_sha256 != expected:
            raise ValueError("output_format_requirement_sha256_mismatch")
        object.__setattr__(self, "requirement_sha256", expected)
        return self

    @property
    def schema_sha256(self) -> str | None:
        return (
            canonical_sha256(self.json_schema)
            if self.json_schema is not None
            else None
        )

    @property
    def portable_wire_schema(self) -> PortableWireSchema | None:
        if self.json_schema is None:
            return None
        return project_portable_wire_schema(self.json_schema)

    @property
    def wire_schema_sha256(self) -> str | None:
        projection = self.portable_wire_schema
        return projection.wire_schema_sha256 if projection is not None else None

    @property
    def response_format_name(self) -> str:
        return f"sgar_{self.requirement_sha256[:24]}"

    @classmethod
    def from_json_schema(
        cls,
        *,
        artifact_type: str,
        json_schema: Mapping[str, Any],
        schema_source: str,
    ) -> "OutputFormatRequirement":
        """Bind one already-authoritative schema without fabricating a projection.

        Planner V6 intentionally leaves executable JSON Schema construction to
        the Plan Compiler.  Once the Compiler has produced that schema, this
        constructor creates the same exact-schema requirement used by legacy
        contract projections and capability probes.
        """

        normalized_type = str(artifact_type or "").strip().lower()
        if normalized_type != "json":
            raise ModelResponseContractError(
                "typed_output_schema_requires_json_artifact"
            )
        return cls(
            artifact_type=normalized_type,
            structured=True,
            strict_required=True,
            json_schema=require_semantic_json_schema(json_schema),
            schema_source=str(schema_source or "compiler_generated"),
        )

    @classmethod
    def from_contract_projection(cls, projection: Any) -> "OutputFormatRequirement":
        raw_artifact_type = getattr(projection, "artifact_type", "plaintext") or "plaintext"
        artifact_type = str(getattr(raw_artifact_type, "value", raw_artifact_type))
        candidates = _schema_candidates(projection)
        distinct = {canonical_sha256(schema) for _source, schema in candidates}
        if len(distinct) > 1:
            raise ModelResponseContractError("typed_output_schema_conflict")
        if candidates:
            source, schema = candidates[0]
            if artifact_type.strip().lower() != "json":
                raise ModelResponseContractError(
                    "typed_output_schema_requires_json_artifact"
                )
            return cls(
                artifact_type=artifact_type,
                structured=True,
                strict_required=True,
                json_schema=require_semantic_json_schema(schema),
                schema_source=source,
            )
        if artifact_type.strip().lower() == "json":
            raise ModelResponseContractError("typed_json_output_schema_missing")
        return cls(
            artifact_type=artifact_type,
            structured=False,
            strict_required=False,
        )


OutputSchemaPhase = Literal[
    "not_structured",
    "authoritative_schema",
    "compiler_pending",
    "invalid_missing",
]


def classify_output_schema_phase(projection: Any) -> OutputSchemaPhase:
    """Classify schema ownership without weakening the legacy strict boundary.

    Only a V6 semantic node may defer a JSON schema to the Compiler.  Legacy
    contracts that declare JSON without a schema remain invalid, and schemas on
    non-JSON artifacts remain an immediate contract error.
    """

    raw_artifact_type = getattr(projection, "artifact_type", "plaintext") or "plaintext"
    artifact_type = str(getattr(raw_artifact_type, "value", raw_artifact_type)).strip().lower()
    candidates = _schema_candidates(projection)
    distinct = {canonical_sha256(schema) for _source, schema in candidates}
    if len(distinct) > 1:
        raise ModelResponseContractError("typed_output_schema_conflict")
    if candidates:
        if artifact_type != "json":
            raise ModelResponseContractError(
                "typed_output_schema_requires_json_artifact"
            )
        return "authoritative_schema"
    if artifact_type != "json":
        return "not_structured"
    if getattr(projection, "semantic_contract_v2", None) is not None:
        return "compiler_pending"
    return "invalid_missing"


class CapabilityProbeEvidence(FrozenContract):
    protocol: Literal[CAPABILITY_PROBE_PROTOCOL_V1, CAPABILITY_PROBE_PROTOCOL] = (
        CAPABILITY_PROBE_PROTOCOL
    )
    resource_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    endpoint_identity_sha256: str
    requirement_sha256: str
    schema_sha256: str
    wire_schema_protocol: str | None = None
    wire_schema_sha256: str | None = None
    input_modality: str = "text"
    authority_source: Literal["live_probe", "applied_ready_state", "operator_approval"] = "live_probe"
    outcome: ProbeOutcome
    reason_code: str = Field(min_length=1)
    checked_at_epoch: float = Field(ge=0)
    expires_at_epoch: float = Field(ge=0)
    response_sha256: str | None = None
    message_sha256: str | None = None
    request_policy_sha256: str | None = None
    request_sha256: str | None = None
    reasoning_effort: str | None = None
    accounting_reference: dict[str, Any] | None = None
    attempted_enforcement_modes: tuple[
        Literal["native_strict_schema", "json_object_local_validator"], ...
    ] = ()
    selected_enforcement_mode: Literal[
        "native_strict_schema", "json_object_local_validator"
    ] | None = None
    fallback_trigger_reason_code: str | None = None
    evidence_sha256: str = ""

    @property
    def is_admissible(self) -> bool:
        return self.outcome == "live_verified" or (
            self.outcome == "operator_approved" and self.authority_source == "operator_approval"
        )

    @property
    def is_applied_admission(self) -> bool:
        return self.is_admissible and self.authority_source in {"applied_ready_state", "operator_approval"}

    @field_validator(
        "endpoint_identity_sha256",
        "requirement_sha256",
        "schema_sha256",
        "wire_schema_sha256",
        "response_sha256",
        "message_sha256",
        "request_policy_sha256",
        "request_sha256",
    )
    @classmethod
    def _hashes(cls, value: str | None, info: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip().lower()
        if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
            raise ValueError(f"{info.field_name}_invalid")
        return normalized

    @model_validator(mode="after")
    def _seal(self) -> "CapabilityProbeEvidence":
        if self.expires_at_epoch < self.checked_at_epoch:
            raise ValueError("capability_probe_expiry_precedes_check")
        manual = self.outcome == "operator_approved"
        if manual != (self.authority_source == "operator_approval"):
            raise ValueError("operator_approval_authority_mismatch")
        if manual and (self.message_sha256 is None or self.response_sha256 is not None
                       or self.selected_enforcement_mode is None or self.attempted_enforcement_modes
                       or self.reason_code not in {"operator_approved_generic_strict_schema", "operator_approved_json_mode"}):
            raise ValueError("operator_approval_evidence_invalid")
        if self.outcome == "live_verified" and self.response_sha256 is None:
            raise ValueError("verified_probe_requires_response_hash")
        has_wire_identity = self.wire_schema_protocol is not None or self.wire_schema_sha256 is not None
        if self.outcome == "live_verified" and has_wire_identity:
            if self.selected_enforcement_mode is None:
                raise ValueError("verified_probe_requires_selected_enforcement_mode")
        if (
            self.selected_enforcement_mode is not None
            and not manual
            and self.selected_enforcement_mode not in self.attempted_enforcement_modes
        ):
            raise ValueError("selected_enforcement_mode_not_attempted")
        if has_wire_identity:
            if self.wire_schema_protocol != PORTABLE_WIRE_SCHEMA_PROTOCOL:
                raise ValueError("capability_probe_wire_schema_protocol_invalid")
            if self.wire_schema_sha256 is None:
                raise ValueError("capability_probe_wire_schema_hash_missing")
        projected = self.model_dump(mode="python", exclude={"evidence_sha256"})
        expected = canonical_sha256(projected)
        expected_hashes = {expected}
        # Preserve validation of evidence written before the explicit authority
        # source was introduced.  New evidence always seals the field.
        pre_authority_projection = {
            key: value for key, value in projected.items() if key != "authority_source"
        }
        expected_hashes.add(canonical_sha256(pre_authority_projection))
        if (
            self.request_policy_sha256 is None
            and self.request_sha256 is None
            and self.reasoning_effort is None
        ):
            pre_request_policy_projection = {
                key: value
                for key, value in projected.items()
                if key
                not in {
                    "request_policy_sha256",
                    "request_sha256",
                    "reasoning_effort",
                }
            }
            expected_hashes.add(canonical_sha256(pre_request_policy_projection))
            expected_hashes.add(
                canonical_sha256(
                    {
                        key: value
                        for key, value in pre_authority_projection.items()
                        if key
                        not in {
                            "request_policy_sha256",
                            "request_sha256",
                            "reasoning_effort",
                        }
                    }
                )
            )
        if self.protocol == CAPABILITY_PROBE_PROTOCOL_V1:
            legacy_projection = {
                key: value
                for key, value in projected.items()
                if key
                not in {
                    "wire_schema_protocol",
                    "wire_schema_sha256",
                    "attempted_enforcement_modes",
                    "selected_enforcement_mode",
                    "fallback_trigger_reason_code",
                    "request_policy_sha256",
                    "request_sha256",
                    "reasoning_effort",
                    "authority_source",
                }
            }
            expected_hashes.add(canonical_sha256(legacy_projection))
        if self.evidence_sha256 and self.evidence_sha256 not in expected_hashes:
            raise ValueError("capability_probe_evidence_sha256_mismatch")
        if not self.evidence_sha256:
            object.__setattr__(self, "evidence_sha256", expected)
        return self

    def is_fresh(self, now_epoch: float) -> bool:
        return float(now_epoch) < self.expires_at_epoch


class ProbeFailureClassification(FrozenContract):
    outcome: Literal["unsupported", "probe_failed", "transient_failure", "blocked"]
    reason_code: str = Field(min_length=1)
    message_sha256: str


def _provider_error_fields(exc: BaseException) -> tuple[int | None, str, str, str]:
    status = getattr(exc, "status_code", None)
    status_code = int(status) if isinstance(status, int) else None
    code = str(getattr(exc, "code", "") or "").strip().lower()
    parameter = str(getattr(exc, "param", "") or "").strip().lower()
    message = str(exc)
    body = getattr(exc, "body", None)
    if isinstance(body, Mapping):
        error = body.get("error", body)
        if isinstance(error, Mapping):
            code = str(error.get("code") or code).strip().lower()
            parameter = str(error.get("param") or parameter).strip().lower()
            message = str(error.get("message") or message)
    return status_code, code, parameter, message


def classify_capability_probe_exception(exc: BaseException) -> ProbeFailureClassification:
    status, code, parameter, message = _provider_error_fields(exc)
    message_hash = hashlib.sha256(message.encode("utf-8", errors="replace")).hexdigest()
    if isinstance(exc, ModelTransportCapabilityError):
        return ProbeFailureClassification(
            outcome="probe_failed",
            reason_code="probe_transport_capability_miswired",
            message_sha256=message_hash,
        )
    if isinstance(exc, ModelResponseContractError) and str(exc) in {
        "capability_probe_empty_response",
        "capability_probe_invalid_json_response",
        "capability_probe_schema_invalid_response",
    }:
        return ProbeFailureClassification(
            outcome="probe_failed",
            reason_code=str(exc),
            message_sha256=message_hash,
        )
    normalized_parameter = parameter.replace("-", "_")
    schema_codes = {
        "invalid_json_schema",
        "unsupported_response_format",
        "unsupported_json_schema",
        "response_format_unsupported",
        "structured_outputs_not_supported",
    }
    parameter_is_schema = (
        "response_format" in normalized_parameter
        or "json_schema" in normalized_parameter
    )
    if code in schema_codes or (parameter_is_schema and status in {400, 404, 409, 422, 429}):
        return ProbeFailureClassification(
            outcome="unsupported",
            reason_code="provider_exact_schema_unsupported",
            message_sha256=message_hash,
        )
    # Some OpenAI-compatible gateways wrap deterministic upstream errors in
    # HTTP 429/500. Preserve explicit business evidence before HTTP classification.
    # A rejected request is not evidence that the model lacks the capability.
    normalized_message = message.lower().replace("-", "_").replace(" ", "_")
    if code in {"bad_response_status_code", "unsupported_feature"} and (
        "structured_outputs" in normalized_message
        and any(marker in normalized_message for marker in
                ("does_not_support", "not_supported", "not_support", "unsupported"))
    ):
        return ProbeFailureClassification(
            outcome="unsupported",
            reason_code="provider_exact_schema_unsupported",
            message_sha256=message_hash,
        )
    if code in {"invalid_parameter_error", "invalid_parameter", "invalid_request_error"}:
        return ProbeFailureClassification(
            outcome="probe_failed",
            reason_code="provider_request_invalid",
            message_sha256=message_hash,
        )
    if code == "empty_model_response":
        return ProbeFailureClassification(
            outcome="transient_failure",
            reason_code="provider_empty_response",
            message_sha256=message_hash,
        )
    transient, transport_code = classify_transport_exception(exc)
    if transient:
        return ProbeFailureClassification(
            outcome="transient_failure",
            reason_code=transport_code,
            message_sha256=message_hash,
        )
    if status in {401, 403}:
        return ProbeFailureClassification(
            outcome="blocked",
            reason_code="provider_authorization_blocked",
            message_sha256=message_hash,
        )
    unavailable_model_codes = {
        "deployment_not_found",
        "model_not_available",
        "model_not_found",
        "unsupported_model",
    }
    parameter_is_schema = (
        "response_format" in normalized_parameter
        or "json_schema" in normalized_parameter
    )
    if status in {400, 404, 409, 422} and parameter_is_schema:
        return ProbeFailureClassification(
            outcome="unsupported",
            reason_code="provider_exact_schema_unsupported",
            message_sha256=message_hash,
        )
    if status in {400, 404, 422} and code in unavailable_model_codes:
        return ProbeFailureClassification(
            outcome="unsupported",
            reason_code="provider_model_unavailable",
            message_sha256=message_hash,
        )
    if transport_code == "provider_model_unavailable":
        return ProbeFailureClassification(
            outcome="unsupported",
            reason_code=transport_code,
            message_sha256=message_hash,
        )
    return ProbeFailureClassification(
        outcome="probe_failed",
        reason_code="capability_probe_inconclusive_failure",
        message_sha256=message_hash,
    )


def _resolve_schema_ref(root: Mapping[str, Any], ref: str) -> Mapping[str, Any]:
    if not ref.startswith("#/"):
        raise ModelResponseContractError("external_json_schema_ref_unsupported")
    current: Any = root
    for part in ref[2:].split("/"):
        key = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, Mapping) or key not in current:
            raise ModelResponseContractError("json_schema_ref_unresolvable")
        current = current[key]
    if not isinstance(current, Mapping):
        raise ModelResponseContractError("json_schema_ref_target_invalid")
    return current


def _valid_hostname(value: str) -> bool:
    if not value or len(value.rstrip(".")) > 253:
        return False
    try:
        ascii_value = value.rstrip(".").encode("idna").decode("ascii")
    except UnicodeError:
        return False
    labels = ascii_value.split(".")
    return all(
        0 < len(label) <= 63
        and label[0] != "-"
        and label[-1] != "-"
        and re.fullmatch(r"[A-Za-z0-9-]+", label) is not None
        for label in labels
    )


def _valid_email(value: str) -> bool:
    if len(value) > 254 or value.count("@") != 1:
        return False
    local_part, domain = value.rsplit("@", 1)
    if (
        not local_part
        or len(local_part) > 64
        or local_part.startswith(".")
        or local_part.endswith(".")
        or ".." in local_part
        or re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+", local_part) is None
    ):
        return False
    return _valid_hostname(domain)


def _valid_uri_reference(value: str, *, require_scheme: bool) -> bool:
    if any(character.isspace() for character in value) or _PERCENT_ESCAPE_INVALID.search(value):
        return False
    try:
        parsed = urlsplit(value)
        if parsed.port is not None and not (0 <= parsed.port <= 65535):
            return False
    except ValueError:
        return False
    if require_scheme:
        return bool(parsed.scheme and _URI_SCHEME.fullmatch(parsed.scheme))
    return not parsed.scheme or bool(_URI_SCHEME.fullmatch(parsed.scheme))


def _validate_json_schema_format(value: str, declared_format: str) -> bool:
    try:
        if declared_format == "date":
            return date.fromisoformat(value).isoformat() == value
        if declared_format == "date-time":
            if _RFC3339_DATE_TIME.fullmatch(value) is None:
                return False
            parsed = datetime.fromisoformat(value.replace("z", "+00:00").replace("Z", "+00:00"))
            return parsed.tzinfo is not None
        if declared_format == "time":
            if _RFC3339_TIME.fullmatch(value) is None:
                return False
            parsed = datetime_time.fromisoformat(
                value.replace("z", "+00:00").replace("Z", "+00:00")
            )
            return parsed.tzinfo is not None
        if declared_format == "duration":
            return _ISO8601_DURATION.fullmatch(value) is not None
        if declared_format in {"email", "idn-email"}:
            return _valid_email(value)
        if declared_format in {"hostname", "idn-hostname"}:
            return _valid_hostname(value)
        if declared_format == "ipv4":
            return isinstance(ipaddress.ip_address(value), ipaddress.IPv4Address)
        if declared_format == "ipv6":
            return isinstance(ipaddress.ip_address(value), ipaddress.IPv6Address)
        if declared_format in {"uri", "iri"}:
            return _valid_uri_reference(value, require_scheme=True)
        if declared_format in {"uri-reference", "iri-reference"}:
            return _valid_uri_reference(value, require_scheme=False)
        if declared_format == "uuid":
            return str(uuid.UUID(value)) == value.lower()
        if declared_format == "regex":
            re.compile(value)
            return True
        if declared_format == "json-pointer":
            return _JSON_POINTER.fullmatch(value) is not None
        if declared_format == "relative-json-pointer":
            return _RELATIVE_JSON_POINTER.fullmatch(value) is not None
    except (ValueError, re.error):
        return False
    return False


def _json_value_identity(value: Any) -> Any:
    # JSON numbers compare by value, while booleans remain a separate type.
    if isinstance(value, Mapping):
        return ("object", frozenset((key, _json_value_identity(item)) for key, item in value.items()))
    if isinstance(value, list):
        return ("array", tuple(_json_value_identity(item) for item in value))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return ("number", value)
    return (type(value), value)


def _json_values_equal(left: Any, right: Any) -> bool:
    return _json_value_identity(left) == _json_value_identity(right)


def validate_json_schema_instance(
    value: Any,
    schema: Mapping[str, Any] | bool,
    *,
    root_schema: Mapping[str, Any] | None = None,
    locator: str = "$",
) -> tuple[bool, str | None]:
    """Validate the deterministic JSON-Schema subset emitted by SGAR contracts."""

    if isinstance(schema, bool):
        return (True, None) if schema else (False, f"{locator}:false_schema")
    root = root_schema if root_schema is not None else schema
    if "$ref" in schema:
        target = _resolve_schema_ref(root, str(schema["$ref"]))
        return validate_json_schema_instance(value, target, root_schema=root, locator=locator)
    if "const" in schema and not _json_values_equal(value, schema["const"]):
        return False, f"{locator}:const"
    if "enum" in schema and not any(_json_values_equal(value, item) for item in schema["enum"]):
        return False, f"{locator}:enum"
    if "allOf" in schema:
        for item in schema["allOf"]:
            ok, reason = validate_json_schema_instance(value, item, root_schema=root, locator=locator)
            if not ok:
                return ok, reason
    if "anyOf" in schema:
        outcomes = [
            validate_json_schema_instance(value, item, root_schema=root, locator=locator)[0]
            for item in schema["anyOf"]
        ]
        if not any(outcomes):
            return False, f"{locator}:anyOf"
    if "oneOf" in schema:
        outcomes = [
            validate_json_schema_instance(value, item, root_schema=root, locator=locator)[0]
            for item in schema["oneOf"]
        ]
        if sum(outcomes) != 1:
            return False, f"{locator}:oneOf"

    expected_type = schema.get("type")
    allowed_types = [expected_type] if isinstance(expected_type, str) else list(expected_type or ())
    type_checks: dict[str, Callable[[Any], bool]] = {
        "null": lambda item: item is None,
        "boolean": lambda item: isinstance(item, bool),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
        "string": lambda item: isinstance(item, str),
        "array": lambda item: isinstance(item, list),
        "object": lambda item: isinstance(item, dict),
    }
    if allowed_types and not any(type_checks.get(item, lambda _value: False)(value) for item in allowed_types):
        return False, f"{locator}:type"

    if isinstance(value, dict):
        required = {str(item) for item in schema.get("required", ())}
        missing = sorted(required - set(value))
        if missing:
            return False, f"{locator}:required:{missing[0]}"
        properties = schema.get("properties")
        properties = properties if isinstance(properties, Mapping) else {}
        for key, item in value.items():
            if key in properties and isinstance(properties[key], (Mapping, bool)):
                ok, reason = validate_json_schema_instance(
                    item,
                    properties[key],
                    root_schema=root,
                    locator=f"{locator}.{key}",
                )
                if not ok:
                    return ok, reason
            elif schema.get("additionalProperties") is False:
                return False, f"{locator}:additionalProperties:{key}"
            elif isinstance(schema.get("additionalProperties"), Mapping):
                ok, reason = validate_json_schema_instance(
                    item,
                    schema["additionalProperties"],
                    root_schema=root,
                    locator=f"{locator}.{key}",
                )
                if not ok:
                    return ok, reason
        minimum_properties = schema.get("minProperties")
        if isinstance(minimum_properties, int) and len(value) < minimum_properties:
            return False, f"{locator}:minProperties"
        maximum_properties = schema.get("maxProperties")
        if isinstance(maximum_properties, int) and len(value) > maximum_properties:
            return False, f"{locator}:maxProperties"
    if isinstance(value, str):
        minimum_length = schema.get("minLength")
        if isinstance(minimum_length, int) and len(value) < minimum_length:
            return False, f"{locator}:minLength"
        maximum_length = schema.get("maxLength")
        if isinstance(maximum_length, int) and len(value) > maximum_length:
            return False, f"{locator}:maxLength"
        pattern = schema.get("pattern")
        if isinstance(pattern, str):
            try:
                matches = re.search(pattern, value) is not None
            except re.error as exc:
                raise ModelResponseContractError("json_schema_pattern_invalid") from exc
            if not matches:
                return False, f"{locator}:pattern"
        declared_format = schema.get("format")
        if isinstance(declared_format, str) and not _validate_json_schema_format(
            value,
            declared_format,
        ):
            return False, f"{locator}:format:{declared_format}"
    if isinstance(value, list) and isinstance(schema.get("items"), (Mapping, bool)):
        for index, item in enumerate(value):
            ok, reason = validate_json_schema_instance(
                item,
                schema["items"],
                root_schema=root,
                locator=f"{locator}[{index}]",
            )
            if not ok:
                return ok, reason
    if isinstance(value, list):
        minimum_items = schema.get("minItems")
        if isinstance(minimum_items, int) and len(value) < minimum_items:
            return False, f"{locator}:minItems"
        maximum_items = schema.get("maxItems")
        if isinstance(maximum_items, int) and len(value) > maximum_items:
            return False, f"{locator}:maxItems"
        if schema.get("uniqueItems") is True:
            identities = [_json_value_identity(item) for item in value]
            if len(set(identities)) != len(identities):
                return False, f"{locator}:uniqueItems"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and not math.isfinite(value):
            return False, f"{locator}:finite"
        minimum = schema.get("minimum")
        if isinstance(minimum, (int, float)) and value < minimum:
            return False, f"{locator}:minimum"
        maximum = schema.get("maximum")
        if isinstance(maximum, (int, float)) and value > maximum:
            return False, f"{locator}:maximum"
        exclusive_minimum = schema.get("exclusiveMinimum")
        if isinstance(exclusive_minimum, (int, float)) and value <= exclusive_minimum:
            return False, f"{locator}:exclusiveMinimum"
        exclusive_maximum = schema.get("exclusiveMaximum")
        if isinstance(exclusive_maximum, (int, float)) and value >= exclusive_maximum:
            return False, f"{locator}:exclusiveMaximum"
        multiple_of = schema.get("multipleOf")
        if isinstance(multiple_of, (int, float)) and multiple_of > 0:
            quotient = value / multiple_of
            if not math.isclose(quotient, round(quotient), rel_tol=1e-9, abs_tol=1e-9):
                return False, f"{locator}:multipleOf"
    return True, None


def local_json_schema_support(
    schema: Mapping[str, Any] | bool,
    *, allow_boolean: bool = False,
) -> tuple[bool, tuple[str, ...]]:
    """Return whether SGAR's deterministic local validator covers the schema."""

    root = schema
    reasons: set[str] = set()

    def inspect(
        node: Mapping[str, Any] | bool,
        locator: str,
        ref_stack: tuple[str, ...] = (),
    ) -> None:
        if isinstance(node, bool):
            if not allow_boolean:
                reasons.add(f"non_object_subschema:{locator}")
            return
        for keyword in node:
            if (
                keyword not in _LOCAL_SCHEMA_ANNOTATION_KEYWORDS
                and keyword not in _LOCAL_SCHEMA_ASSERTION_KEYWORDS
            ):
                reasons.add(f"unsupported_keyword:{keyword}")

        expected_type = node.get("type")
        declared_types = (
            [expected_type]
            if isinstance(expected_type, str)
            else list(expected_type or ())
            if isinstance(expected_type, Sequence)
            and not isinstance(expected_type, (str, bytes))
            else []
        )
        if expected_type is not None and not declared_types:
            reasons.add(f"invalid_type_declaration:{locator}")
        if any(item not in _LOCAL_SCHEMA_TYPES for item in declared_types):
            reasons.add(f"unsupported_type:{locator}")

        ref = node.get("$ref")
        if ref is not None:
            if not isinstance(ref, str) or not ref.startswith("#/"):
                reasons.add(f"unsupported_ref:{locator}")
            elif ref in ref_stack:
                reasons.add(f"recursive_ref:{locator}")
            else:
                try:
                    target = _resolve_schema_ref(root, ref)
                except ModelResponseContractError:
                    reasons.add(f"unresolvable_ref:{locator}")
                else:
                    inspect(target, f"{locator}.$ref", ref_stack + (ref,))

        pattern = node.get("pattern")
        if pattern is not None:
            if not isinstance(pattern, str):
                reasons.add(f"invalid_pattern:{locator}")
            else:
                try:
                    re.compile(pattern)
                except re.error:
                    reasons.add(f"invalid_pattern:{locator}")

        declared_format = node.get("format")
        if declared_format is not None:
            if not isinstance(declared_format, str):
                reasons.add(f"invalid_format:{locator}")
            elif declared_format not in _LOCAL_SCHEMA_FORMATS:
                reasons.add(f"unsupported_format:{declared_format}")

        properties = node.get("properties")
        if properties is not None:
            if not isinstance(properties, Mapping):
                reasons.add(f"invalid_properties:{locator}")
            else:
                for key, child in properties.items():
                    if isinstance(child, (Mapping, bool)):
                        inspect(child, f"{locator}.properties.{key}", ref_stack)
                    else:
                        reasons.add(f"non_object_subschema:{locator}.properties.{key}")

        additional = node.get("additionalProperties")
        if additional is not None and not isinstance(additional, bool):
            if isinstance(additional, Mapping):
                inspect(additional, f"{locator}.additionalProperties", ref_stack)
            else:
                reasons.add(f"invalid_additional_properties:{locator}")

        items = node.get("items")
        if items is not None:
            if isinstance(items, (Mapping, bool)):
                inspect(items, f"{locator}.items", ref_stack)
            else:
                reasons.add(f"unsupported_items_shape:{locator}")

        for keyword in ("allOf", "anyOf", "oneOf"):
            alternatives = node.get(keyword)
            if alternatives is None:
                continue
            if not isinstance(alternatives, Sequence) or isinstance(
                alternatives, (str, bytes)
            ):
                reasons.add(f"invalid_{keyword}:{locator}")
                continue
            for index, child in enumerate(alternatives):
                if isinstance(child, (Mapping, bool)):
                    inspect(child, f"{locator}.{keyword}[{index}]", ref_stack)
                else:
                    reasons.add(f"non_object_subschema:{locator}.{keyword}[{index}]")

        for keyword in ("$defs", "definitions"):
            definitions = node.get(keyword)
            if definitions is None:
                continue
            if not isinstance(definitions, Mapping):
                reasons.add(f"invalid_{keyword}:{locator}")
                continue
            for key, child in definitions.items():
                if isinstance(child, (Mapping, bool)):
                    inspect(child, f"{locator}.{keyword}.{key}", ref_stack)
                else:
                    reasons.add(f"non_object_subschema:{locator}.{keyword}.{key}")

    inspect(schema, "$")
    ordered = tuple(sorted(reasons))
    return not ordered, ordered


def minimal_json_schema_instance(
    schema: Mapping[str, Any],
    *,
    root_schema: Mapping[str, Any] | None = None,
) -> Any:
    root = root_schema or schema
    if "$ref" in schema:
        return minimal_json_schema_instance(
            _resolve_schema_ref(root, str(schema["$ref"])),
            root_schema=root,
        )
    if "const" in schema:
        return schema["const"]
    enum = schema.get("enum")
    if isinstance(enum, Sequence) and not isinstance(enum, (str, bytes)) and enum:
        return enum[0]
    for keyword in ("anyOf", "oneOf"):
        alternatives = schema.get(keyword)
        if isinstance(alternatives, Sequence) and alternatives:
            for alternative in alternatives:
                if not isinstance(alternative, Mapping):
                    continue
                candidate = minimal_json_schema_instance(
                    alternative,
                    root_schema=root,
                )
                valid, _reason = validate_json_schema_instance(
                    candidate,
                    schema,
                    root_schema=root,
                )
                if valid:
                    return candidate
            raise ModelResponseContractError("json_schema_minimal_alternative_missing")

    expected_type = schema.get("type")
    allowed_types = (
        [expected_type]
        if isinstance(expected_type, str)
        else list(expected_type or ())
    )
    selected_type = next((item for item in allowed_types if item != "null"), None)
    if selected_type is None and "null" in allowed_types:
        return None
    if selected_type == "object" or isinstance(schema.get("properties"), Mapping):
        properties = schema.get("properties")
        properties = properties if isinstance(properties, Mapping) else {}
        return {
            key: minimal_json_schema_instance(properties[key], root_schema=root)
            for key in schema.get("required", ())
            if key in properties and isinstance(properties[key], Mapping)
        }
    if selected_type == "array":
        count = int(schema.get("minItems") or 0)
        items = schema.get("items")
        if count and not isinstance(items, Mapping):
            raise ModelResponseContractError("json_schema_minimal_array_items_missing")
        return [
            minimal_json_schema_instance(items, root_schema=root)
            for _index in range(count)
        ]
    if selected_type == "string":
        minimum_length = max(0, int(schema.get("minLength") or 0))
        value = "x" * minimum_length
        return value
    if selected_type == "integer":
        value = int(schema.get("minimum") or 0)
        if isinstance(schema.get("exclusiveMinimum"), (int, float)):
            value = max(value, int(schema["exclusiveMinimum"]) + 1)
        return value
    if selected_type == "number":
        value = float(schema.get("minimum") or 0.0)
        if isinstance(schema.get("exclusiveMinimum"), (int, float)):
            value = max(value, float(schema["exclusiveMinimum"]) + 1.0)
        return value
    if selected_type == "boolean":
        return False
    if selected_type == "null":
        return None
    return {}


def build_exact_schema_probe_request(
    *,
    model_id: str,
    requirement: OutputFormatRequirement,
    mode: Literal["native_strict_schema", "json_object_local_validator"] = (
        "native_strict_schema"
    ),
    request_fields: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if requirement.json_schema is None:
        raise ModelResponseContractError("exact_probe_requires_schema")
    if requirement.schema_source == "system_role.planner":
        from .planner_wire import planner_probe_wire_payload

        example = planner_probe_wire_payload()
    else:
        example = minimal_json_schema_instance(requirement.json_schema)
    valid, _reason = validate_json_schema_instance(
        example,
        requirement.json_schema,
    )
    if not valid:
        raise ModelResponseContractError("exact_probe_synthetic_example_invalid")
    provider_example = (
        project_portable_wire_instance(example, requirement.json_schema)
        if mode == "native_strict_schema"
        else example
    )
    example_text = canonical_json_bytes(provider_example).decode("utf-8")
    contract_context = ""
    if requirement.schema_source in {"system_role.plan_compiler", "system_role.plan_adaptation"}:
        # This literal is part of the already measured FORMAT probe, not the live prompt.
        # Its request/schema fingerprints still invalidate receipts when probe content changes.
        version = ("executable-plan-compiler-v27-input-alignment"
            if requirement.schema_source.endswith(".plan_compiler")
            else "executable-plan-adaptation-v14-input-alignment")
        contract_context = ("Control contract revision: " + version + ". Original task requirements "
            "and Planner macro standards govern Compiler implementation choices. "
            "Do not turn unverified guesses into output constraints. ")
    elif requirement.schema_source == "system_role.evaluator":
        # Keep the exact format-only probe independent from production prose revisions.
        contract_context = ("Control contract revision: task-first-evaluator-en-v7-input-alignment. "
            "Evaluate task requirements and macro delivery standards against actual evidence. "
            "Machine schema conformance does not override explicit task requirements. ")
    request = {
        "model": str(model_id),
        "messages": [
            {
                "role": "user",
                "content": (
                    contract_context + "Return the following public synthetic JSON value exactly. "
                    "Do not use external or user data:\n"
                    f"{example_text}"
                ),
            }
        ],
        "max_tokens": max(256, min(2048, len(example_text) + 128)),
        "temperature": 0.0,
        "stream": False,
        "response_format": structured_response_format(requirement, mode=mode),
    }
    normalized_fields = dict(request_fields or {})
    unsupported = sorted(
        set(normalized_fields).difference({"reasoning_effort", "temperature"})
    )
    if unsupported:
        raise ModelResponseContractError("exact_probe_request_fields_unsupported")
    if "reasoning_effort" in normalized_fields:
        effort = str(normalized_fields["reasoning_effort"]).strip()
        if effort not in {"low", "medium", "high", "xhigh", "max"}:
            raise ModelResponseContractError("exact_probe_reasoning_effort_invalid")
        request.pop("temperature", None)
        request["reasoning_effort"] = effort
    if "temperature" in normalized_fields:
        try:
            temperature = float(normalized_fields["temperature"])
        except (TypeError, ValueError) as exc:
            raise ModelResponseContractError(
                "exact_probe_temperature_invalid"
            ) from exc
        if not 0.0 <= temperature <= 2.0:
            raise ModelResponseContractError("exact_probe_temperature_invalid")
        request["temperature"] = temperature
    return request


def _model_response_content(response: Any) -> str:
    choices = getattr(response, "choices", None)
    if choices is None and isinstance(response, Mapping):
        choices = response.get("choices")
    if not isinstance(choices, Sequence) or isinstance(choices, (str, bytes)) or not choices:
        raise ModelResponseContractError("capability_probe_empty_response")
    first = choices[0]
    message = getattr(first, "message", None)
    if message is None and isinstance(first, Mapping):
        message = first.get("message")
    content = getattr(message, "content", None)
    if content is None and isinstance(message, Mapping):
        content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ModelResponseContractError("capability_probe_empty_response")
    return content


class _ProbeCacheEntry:
    def __init__(self) -> None:
        self.in_flight = True
        self.evidence: CapabilityProbeEvidence | None = None


class ExactCapabilityProbeService:
    """Single-flight exact-schema probes with endpoint- and schema-bound TTLs."""

    def __init__(
        self,
        transport: SyncModelTransportPort | None,
        *,
        ttl_seconds: float = DEFAULT_PROBE_TTL_SECONDS,
        clock: Callable[[], float] = time.time,
        cache_path: str | Path | None = None,
        enforcement_policy: CapabilityProbeEnforcementPolicy | str = (
            DEFAULT_CAPABILITY_PROBE_ENFORCEMENT_POLICY
        ),
    ) -> None:
        self.transport = (
            require_sync_model_transport(transport) if transport is not None else None
        )
        self.ttl_seconds = max(0.0, float(ttl_seconds))
        self.clock = clock
        self.cache_path = Path(cache_path).resolve() if cache_path is not None else None
        self.enforcement_policy = normalize_capability_probe_enforcement_policy(
            enforcement_policy
        )
        self._condition = threading.Condition(threading.RLock())
        self._cache: dict[tuple[str, ...], _ProbeCacheEntry] = {}
        self._load_persistent_cache()

    def _ttl_for(self, outcome: ProbeOutcome) -> float:
        if outcome in {"live_verified", "unsupported"}:
            return self.ttl_seconds
        if outcome == "probe_failed":
            return min(self.ttl_seconds, 60 * 60)
        if outcome == "blocked":
            return min(self.ttl_seconds, 15 * 60)
        if outcome == "transient_failure":
            return min(self.ttl_seconds, 5 * 60)
        return 0.0

    @staticmethod
    def _evidence_key(evidence: CapabilityProbeEvidence) -> tuple[str, ...]:
        return (
            evidence.resource_id,
            evidence.model_id,
            evidence.endpoint_identity_sha256,
            evidence.requirement_sha256,
            evidence.schema_sha256,
            str(evidence.wire_schema_sha256 or ""),
            evidence.input_modality,
            str(evidence.request_policy_sha256 or ""),
            str(evidence.reasoning_effort or ""),
            CAPABILITY_PROBE_PROTOCOL,
        )

    def _evidence_matches_enforcement_policy(
        self,
        evidence: CapabilityProbeEvidence,
    ) -> bool:
        if self.enforcement_policy == "adaptive_fallback":
            return True
        return (
            len(evidence.attempted_enforcement_modes) == 1
            and evidence.fallback_trigger_reason_code is None
        )

    def _load_persistent_cache(self) -> None:
        if self.cache_path is None or not self.cache_path.is_file():
            return
        try:
            payload = strict_json_loads(self.cache_path.read_text(encoding="utf-8"))
            if not isinstance(payload, Mapping) or payload.get("protocol") != CAPABILITY_PROBE_CACHE_PROTOCOL:
                return
            now = self.clock()
            for raw in payload.get("entries", ()):
                evidence = CapabilityProbeEvidence.model_validate(raw)
                if (
                    evidence.protocol != CAPABILITY_PROBE_PROTOCOL
                    or evidence.wire_schema_protocol != PORTABLE_WIRE_SCHEMA_PROTOCOL
                    or not evidence.wire_schema_sha256
                ):
                    continue
                if not evidence.is_fresh(now):
                    continue
                if not self._evidence_matches_enforcement_policy(evidence):
                    continue
                entry = _ProbeCacheEntry()
                entry.in_flight = False
                entry.evidence = evidence
                self._cache[self._evidence_key(evidence)] = entry
        except (OSError, ValueError, TypeError):
            return

    def _persist_cache(self) -> None:
        if self.cache_path is None:
            return
        now = self.clock()
        entries = [
            self._persistent_evidence(entry.evidence)
            for _key, entry in sorted(self._cache.items())
            if not entry.in_flight
            and entry.evidence is not None
            and entry.evidence.is_fresh(now)
            and entry.evidence.outcome in {"live_verified", "unsupported"}
        ]
        payload = {
            "protocol": CAPABILITY_PROBE_CACHE_PROTOCOL,
            "entries": [
                item.model_dump(mode="json", exclude={"accounting_reference"})
                for item in entries
            ],
        }
        target = self.cache_path
        temporary: Path | None = None
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = temporary_sibling_path(target)
            temporary.write_bytes(canonical_json_bytes(payload) + b"\n")
            os.replace(temporary, target)
        except OSError:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    @staticmethod
    def _persistent_evidence(
        evidence: CapabilityProbeEvidence,
    ) -> CapabilityProbeEvidence:
        payload = evidence.model_dump(
            mode="python",
            exclude={"accounting_reference", "evidence_sha256"},
        )
        return CapabilityProbeEvidence(**payload, accounting_reference=None)

    def _key(
        self,
        *,
        resource_id: str,
        model_id: str,
        requirement: OutputFormatRequirement,
        request_fields: Mapping[str, Any] | None,
        request_policy_sha256: str | None,
    ) -> tuple[str, ...]:
        endpoint = (
            self.transport.endpoint_identity.identity_sha256
            if self.transport is not None
            else "0" * 64
        )
        request_binding_sha256 = str(request_policy_sha256 or "")
        if not request_binding_sha256 and request_fields:
            request_binding_sha256 = canonical_sha256(dict(request_fields))
        return (
            str(resource_id),
            str(model_id),
            endpoint,
            requirement.requirement_sha256,
            str(requirement.schema_sha256 or ""),
            str(requirement.wire_schema_sha256 or ""),
            requirement.input_modality,
            request_binding_sha256,
            str((request_fields or {}).get("reasoning_effort") or ""),
            CAPABILITY_PROBE_PROTOCOL,
        )

    def probe(
        self,
        *,
        resource_id: str,
        model_id: str,
        requirement: OutputFormatRequirement,
        cost_ledger: RunCostLedger | None = None,
        subtask_id: str | None = None,
        subtask_revision: int | None = None,
        request_fields: Mapping[str, Any] | None = None,
        request_policy_sha256: str | None = None,
    ) -> CapabilityProbeEvidence:
        if requirement.json_schema is None:
            raise ModelResponseContractError("exact_probe_requires_schema")
        key = self._key(
            resource_id=resource_id,
            model_id=model_id,
            requirement=requirement,
            request_fields=request_fields,
            request_policy_sha256=request_policy_sha256,
        )
        with self._condition:
            while True:
                entry = self._cache.get(key)
                if entry is None:
                    entry = _ProbeCacheEntry()
                    self._cache[key] = entry
                    break
                while entry.in_flight and self._cache.get(key) is entry:
                    self._condition.wait()
                if self._cache.get(key) is not entry:
                    continue
                if (
                    entry.evidence is not None
                    and entry.evidence.is_fresh(self.clock())
                    and self._evidence_matches_enforcement_policy(entry.evidence)
                ):
                    return entry.evidence
                entry = _ProbeCacheEntry()
                self._cache[key] = entry
                break

        def clear_in_flight() -> None:
            with self._condition:
                if self._cache.get(key) is entry:
                    self._cache.pop(key, None)
                entry.in_flight = False
                self._condition.notify_all()

        try:
            evidence = self._probe_uncached(
                resource_id=resource_id,
                model_id=model_id,
                requirement=requirement,
                cost_ledger=cost_ledger,
                subtask_id=subtask_id,
                subtask_revision=subtask_revision,
                request_fields=request_fields,
                request_policy_sha256=request_policy_sha256,
            )
        except (asyncio.CancelledError, KeyboardInterrupt):
            clear_in_flight()
            raise
        except Exception:
            clear_in_flight()
            raise
        with self._condition:
            entry.evidence = evidence
            entry.in_flight = False
            self._persist_cache()
            self._condition.notify_all()
        return evidence

    def _probe_uncached(
        self,
        *,
        resource_id: str,
        model_id: str,
        requirement: OutputFormatRequirement,
        cost_ledger: RunCostLedger | None,
        subtask_id: str | None,
        subtask_revision: int | None,
        request_fields: Mapping[str, Any] | None,
        request_policy_sha256: str | None,
    ) -> CapabilityProbeEvidence:
        checked_at = self.clock()
        wire_projection = requirement.portable_wire_schema
        if wire_projection is None:
            raise ModelResponseContractError("exact_probe_requires_wire_schema")
        endpoint_hash = (
            self.transport.endpoint_identity.identity_sha256
            if self.transport is not None
            else "0" * 64
        )
        common = {
            "resource_id": str(resource_id),
            "model_id": str(model_id),
            "endpoint_identity_sha256": endpoint_hash,
            "requirement_sha256": requirement.requirement_sha256,
            "schema_sha256": str(requirement.schema_sha256),
            "wire_schema_protocol": wire_projection.protocol,
            "wire_schema_sha256": wire_projection.wire_schema_sha256,
            "input_modality": requirement.input_modality,
            "request_policy_sha256": request_policy_sha256,
            "reasoning_effort": (
                str((request_fields or {}).get("reasoning_effort"))
                if (request_fields or {}).get("reasoning_effort") is not None
                else None
            ),
            "checked_at_epoch": checked_at,
        }
        if self.transport is None:
            return CapabilityProbeEvidence(
                **common,
                outcome="not_checked",
                reason_code="capability_probe_transport_not_configured",
                expires_at_epoch=checked_at + self._ttl_for("not_checked"),
            )
        context = (
            cost_ledger.new_operation(
                stage="retrieval_format_probe",
                subtask_id=subtask_id,
                subtask_revision=subtask_revision,
                selected_resource_id=resource_id,
                model_resource_id=resource_id,
                request_policy_sha256=request_policy_sha256,
                reasoning_effort=(request_fields or {}).get("reasoning_effort"),
            )
            if cost_ledger is not None
            else None
        )
        response: Any = None
        content: Any = None
        attempted_modes: list[
            Literal["native_strict_schema", "json_object_local_validator"]
        ] = []
        fallback_trigger_reason_code: str | None = None
        request_sha256: str | None = None

        def operation_accounting_reference() -> dict[str, Any] | None:
            if cost_ledger is None or context is None:
                return None
            return cost_ledger.operation_reference(context.operation_id)

        def annotate_accounting_reference(exc: BaseException) -> None:
            reference = operation_accounting_reference()
            if reference is None:
                return
            try:
                setattr(exc, "accounting_reference", reference)
            except (AttributeError, TypeError):
                pass

        def send_probe(
            mode: Literal["native_strict_schema", "json_object_local_validator"],
        ) -> tuple[Any, str, Any]:
            nonlocal request_sha256
            attempted_modes.append(mode)
            request = build_exact_schema_probe_request(
                model_id=model_id,
                requirement=requirement,
                mode=mode,
                request_fields=request_fields,
            )
            request_sha256 = canonical_sha256(request)
            current_response = self.transport.send(
                ledger=cost_ledger,
                context=context,
                **request,
            )
            current_content = _model_response_content(current_response)
            try:
                parsed = strict_json_loads(current_content)
            except (json.JSONDecodeError, ValueError) as exc:
                raise ModelResponseContractError(
                    "capability_probe_invalid_json_response"
                ) from exc
            if mode == "native_strict_schema":
                parsed = normalize_portable_wire_instance(
                    parsed,
                    requirement.json_schema or {},
                )
            valid, _reason = validate_json_schema_instance(
                parsed,
                requirement.json_schema or {},
            )
            if not valid:
                raise ModelResponseContractError(
                    "capability_probe_schema_invalid_response"
                )
            if requirement.schema_source == "system_role.planner":
                try:
                    from .planner_wire import project_planner_wire_payload
                    from .planner_contracts import (
                        project_planner_contract,
                        project_planner_contract_v2,
                    )

                    planner_output = project_planner_wire_payload(
                        cast(Mapping[str, Any], parsed)
                    )
                    if planner_output.subtasks and all(
                        item.semantic_contract_v2 is not None
                        for item in planner_output.subtasks
                    ):
                        project_planner_contract_v2(planner_output)
                    else:
                        project_planner_contract(planner_output)
                except Exception as exc:
                    raise ModelResponseContractError(
                        "capability_probe_planner_semantic_projection_invalid"
                    ) from exc
            return current_response, current_content, parsed

        try:
            if wire_projection.native_eligible:
                try:
                    response, content, _parsed = send_probe("native_strict_schema")
                except (ModelAccountingError, ModelTransportCapabilityError):
                    raise
                except (asyncio.CancelledError, KeyboardInterrupt):
                    raise
                except Exception as native_exc:
                    classified = classify_capability_probe_exception(native_exc)
                    if classified.reason_code != "provider_exact_schema_unsupported":
                        raise
                    if self.enforcement_policy == "single_attempt":
                        accounting_reference = getattr(
                            response, "accounting_reference", None
                        )
                        if accounting_reference is None:
                            accounting_reference = operation_accounting_reference()
                        return CapabilityProbeEvidence(
                            **common,
                            outcome=classified.outcome,
                            reason_code=classified.reason_code,
                            expires_at_epoch=(
                                checked_at + self._ttl_for(classified.outcome)
                            ),
                            message_sha256=classified.message_sha256,
                            accounting_reference=accounting_reference,
                            request_sha256=request_sha256,
                            attempted_enforcement_modes=tuple(attempted_modes),
                            selected_enforcement_mode=None,
                        )
                    fallback_trigger_reason_code = classified.reason_code
                else:
                    return CapabilityProbeEvidence(
                        **common,
                        outcome="live_verified",
                        reason_code="provider_exact_schema_live_verified",
                        expires_at_epoch=checked_at + self._ttl_for("live_verified"),
                        response_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                        accounting_reference=getattr(response, "accounting_reference", None),
                        request_sha256=request_sha256,
                        attempted_enforcement_modes=tuple(attempted_modes),
                        selected_enforcement_mode="native_strict_schema",
                    )

            response, content, _parsed = send_probe("json_object_local_validator")
            return CapabilityProbeEvidence(
                **common,
                outcome="live_verified",
                reason_code="provider_json_object_local_validator_live_verified",
                expires_at_epoch=checked_at + self._ttl_for("live_verified"),
                response_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                accounting_reference=getattr(response, "accounting_reference", None),
                request_sha256=request_sha256,
                attempted_enforcement_modes=tuple(attempted_modes),
                selected_enforcement_mode="json_object_local_validator",
                fallback_trigger_reason_code=fallback_trigger_reason_code,
            )
        except (ModelAccountingError, ModelTransportCapabilityError) as exc:
            annotate_accounting_reference(exc)
            raise
        except (asyncio.CancelledError, KeyboardInterrupt) as exc:
            annotate_accounting_reference(exc)
            raise
        except Exception as exc:
            classified = classify_capability_probe_exception(exc)
            reason_code = classified.reason_code
            accounting_reference = getattr(response, "accounting_reference", None)
            if accounting_reference is None:
                accounting_reference = operation_accounting_reference()
            return CapabilityProbeEvidence(
                **common,
                outcome=classified.outcome,
                reason_code=reason_code,
                expires_at_epoch=checked_at + self._ttl_for(classified.outcome),
                response_sha256=(
                    hashlib.sha256(content.encode("utf-8")).hexdigest()
                    if isinstance(content, str)
                    else None
                ),
                message_sha256=classified.message_sha256,
                accounting_reference=accounting_reference,
                request_sha256=request_sha256,
                attempted_enforcement_modes=tuple(attempted_modes),
            )


def system_role_schema(
    role: str,
    *,
    planner_require_capability_fields: bool = False,
) -> dict[str, Any]:
    normalized = str(role).strip().lower()
    if normalized == "planner":
        from .planner_wire import PlannerOutputWireV6

        # Capability context is input-only in V6.  It never changes the small
        # response schema or asks the Planner to echo pool evidence.
        return canonicalize_json_schema(PlannerOutputWireV6.model_json_schema())
    if normalized == "hyde":
        return {
            "type": "object",
            "properties": {
                "capability_text": {"type": "string", "minLength": 1},
                "constraint_text": {"type": "string", "minLength": 1},
                "think": {"type": "string", "minLength": 1},
            },
            "required": ["capability_text", "constraint_text", "think"],
            "additionalProperties": False,
        }
    if normalized == "plan_compiler":
        from .executable_plan import CompilerDecisionProposalV3

        return canonicalize_json_schema(CompilerDecisionProposalV3.model_json_schema())
    if normalized == "router_policy":
        from .schema import BundleAdequacyDecision

        return canonicalize_json_schema(BundleAdequacyDecision.model_json_schema())
    if normalized == "plan_adaptation":
        from .recovery_control import PlanAdaptationDecisionV3

        return canonicalize_json_schema(PlanAdaptationDecisionV3.model_json_schema())
    if normalized == "evaluator":
        from .evaluation_runtime import EvaluationAssessmentProposalV2

        return canonicalize_json_schema(EvaluationAssessmentProposalV2.model_json_schema())
    if normalized == "full_generation":
        from .recovery_control import FullGenerationDraft

        return canonicalize_json_schema(FullGenerationDraft.model_json_schema())
    if normalized == "temporary_tool":
        from .temporary_tool import TemporaryToolGenerationDraft

        return canonicalize_json_schema(TemporaryToolGenerationDraft.model_json_schema())
    raise ModelResponseContractError("system_role_schema_unknown")


def system_role_requirement(
    role: str,
    *,
    planner_require_capability_fields: bool = False,
) -> OutputFormatRequirement:
    normalized = str(role).strip().lower()
    return OutputFormatRequirement(
        artifact_type="json",
        structured=True,
        strict_required=True,
        json_schema=system_role_schema(
            normalized,
            planner_require_capability_fields=planner_require_capability_fields,
        ),
        schema_source=f"system_role.{normalized}",
    )


SYSTEM_MODEL_ROLES = (
    "planner",
    "hyde",
    "plan_compiler",
    "router_policy",
    "plan_adaptation",
    "evaluator",
    "full_generation",
    "temporary_tool",
)


__all__ = [
    "CAPABILITY_PROBE_PROTOCOL",
    "CAPABILITY_PROBE_PROTOCOL_V1",
    "CAPABILITY_PROBE_CACHE_PROTOCOL",
    "CAPABILITY_PROBE_CACHE_PROTOCOL_V1",
    "CAPABILITY_PROBE_CACHE_PROTOCOL_V2",
    "CapabilityProbeEnforcementPolicy",
    "DEFAULT_CAPABILITY_PROBE_ENFORCEMENT_POLICY",
    "DEFAULT_PROBE_TTL_SECONDS",
    "MODEL_RESPONSE_CONTRACT_PROTOCOL",
    "PORTABLE_WIRE_SCHEMA_PROTOCOL",
    "SYSTEM_MODEL_ROLES",
    "CapabilityProbeEvidence",
    "ExactCapabilityProbeService",
    "FormatEnforcementMode",
    "ModelResponseContractError",
    "OutputFormatRequirement",
    "OutputSchemaPhase",
    "PortableWireSchema",
    "ProbeFailureClassification",
    "ProbeOutcome",
    "StructuredResponseMode",
    "StructuredResponseModeInput",
    "StructuredRoleContractV2",
    "StructuredIngressNormalizationV1",
    "STRUCTURED_ROLE_CONTRACT_PROTOCOL",
    "STRUCTURED_INGRESS_NORMALIZATION_PROTOCOL",
    "build_structured_role_contract",
    "build_exact_schema_probe_request",
    "canonicalize_json_schema",
    "classify_capability_probe_exception",
    "classify_output_schema_phase",
    "minimal_json_schema_instance",
    "normalize_portable_wire_instance",
    "normalize_capability_probe_enforcement_policy",
    "normalize_structured_response_content",
    "normalize_structured_response_mode",
    "local_json_schema_support",
    "require_semantic_json_schema",
    "project_portable_wire_schema",
    "project_portable_wire_instance",
    "structured_response_format",
    "structured_response_format_from_contract",
    "structured_role_prompt_projection",
    "system_role_response_format",
    "system_role_requirement",
    "system_role_schema",
    "strict_json_loads",
    "validate_json_schema_instance",
    "validate_structured_response_content",
]
