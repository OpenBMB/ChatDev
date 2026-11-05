"""Deterministic, compact Planner views projected from resource manifests."""

from __future__ import annotations

import re
from typing import Any, Iterable, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from .capability_operations import (
    CAPABILITY_TO_EXECUTION_OPERATION,
    manifest_capability_operations,
)
from .pipeline_control import canonical_sha256


RESOURCE_CAPABILITY_CARD_PROTOCOL = "sgar-resource-capability-card-v2"
RESOURCE_CAPABILITY_REPORT_PROTOCOL = "sgar-resource-capability-report-v1"
_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


_EVIDENCE_LEVEL = {
    "Tool": "executable",
    "Model": "generative",
    "Agent": "delegated",
    "Skill": "guidance",
    "Resource": "grounding_source",
    "Device": "environment",
}

_TYPE_LIMITATIONS = {
    "Model": ("Generates from supplied context; it does not prove external facts or external actions.",),
    "Agent": ("Delegated capability may require supporting resources for grounded observations or actions.",),
    "Skill": ("Planning or execution guidance only; not an independent executor.",),
    "Resource": ("Provides existing grounding context; it does not perform an external action.",),
    "Device": ("Provides an execution environment or hardware affordance, not task content by itself.",),
}

class CapabilityPort(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    kind: str = "unknown"
    required: bool = False
    content_encoding: Literal["utf-8"] | None = None

    @model_serializer(mode="wrap")
    def _declared_content_constraints(self, handler):
        value = handler(self)
        # Preserve existing sealed operation identities when no content
        # constraint was declared. Do not infer one from a name or file suffix.
        if self.content_encoding is None:
            value.pop("content_encoding", None)
        return value


class CapabilityOperationV2(BaseModel):
    """Manifest-derived operation identity without task- or ID-based inference."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    capability_operation_id: str
    declared_operation: str
    execution_operation_kind: str
    entrypoint_id: str | None
    input_ports: list[CapabilityPort] = Field(default_factory=list)
    output_semantics: list[str] = Field(default_factory=list)
    accepted_artifact_types: list[str] = Field(default_factory=list)
    produced_artifact_types: list[str] = Field(default_factory=list)
    # A Tool's JSON result envelope may be distinct from the physical artifact
    # it materializes (for example, a write-file MCP result vs. a Markdown file).
    # Keep this declaration separate so final delivery can be proven without
    # pretending that the transport envelope is the task artifact.
    materialized_artifact_types: list[str] = Field(default_factory=list)
    determinism: Literal["deterministic", "nondeterministic", "unknown"] = "unknown"
    material_access: Literal["inline", "artifact_handle", "both", "none", "unknown"] = "unknown"
    side_effects: Literal["none", "declared", "unknown"] = "unknown"
    effect_targets: list[Literal["task_workspace"]] = Field(default_factory=list)
    modalities: list[str] = Field(default_factory=list)
    evidence_status: Literal["declared", "partial", "unknown"] = "unknown"
    operation_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "CapabilityOperationV2":
        if self.effect_targets and self.side_effects != "declared":
            raise ValueError("effect_targets_require_declared_side_effect")
        expected = canonical_sha256(
            self.model_dump(mode="python", exclude={"operation_sha256"})
        )
        if self.operation_sha256 and self.operation_sha256 != expected:
            raise ValueError("capability_operation_sha256_mismatch")
        object.__setattr__(self, "operation_sha256", expected)
        return self


class CapabilityCard(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    protocol: Literal[RESOURCE_CAPABILITY_CARD_PROTOCOL] = RESOURCE_CAPABILITY_CARD_PROTOCOL
    resource_id: str
    resource_type: str
    summary: str
    operations: list[str] = Field(default_factory=list)
    inputs: list[CapabilityPort] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    availability: str = "unknown"
    evidence_level: str
    capability_operations: list[CapabilityOperationV2] = Field(default_factory=list)
    summary_status: Literal["declared", "unknown"] = "unknown"
    card_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "CapabilityCard":
        ids = [item.capability_operation_id for item in self.capability_operations]
        if len(ids) != len(set(ids)):
            raise ValueError("capability_operation_id_duplicate")
        expected = canonical_sha256(
            self.model_dump(mode="python", exclude={"card_sha256"})
        )
        if self.card_sha256 and self.card_sha256 != expected:
            raise ValueError("resource_capability_card_sha256_mismatch")
        object.__setattr__(self, "card_sha256", expected)
        return self


class CapabilityConsistencyItemV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    resource_id: str
    resource_type: str
    sealable: bool
    issue_codes: tuple[str, ...] = ()
    card_sha256: str


class CapabilityCatalogConsistencyReportV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    protocol: Literal[RESOURCE_CAPABILITY_REPORT_PROTOCOL] = (
        RESOURCE_CAPABILITY_REPORT_PROTOCOL
    )
    resource_count: int = Field(ge=0)
    sealable_resource_count: int = Field(ge=0)
    items: tuple[CapabilityConsistencyItemV1, ...]
    report_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "CapabilityCatalogConsistencyReportV1":
        if self.resource_count != len(self.items):
            raise ValueError("capability_report_resource_count_mismatch")
        if self.sealable_resource_count != sum(item.sealable for item in self.items):
            raise ValueError("capability_report_sealable_count_mismatch")
        expected = canonical_sha256(
            self.model_dump(mode="python", exclude={"report_sha256"})
        )
        if self.report_sha256 and self.report_sha256 != expected:
            raise ValueError("capability_report_sha256_mismatch")
        object.__setattr__(self, "report_sha256", expected)
        return self


def _resource_type(manifest: Mapping[str, Any]) -> str:
    nested = manifest.get("type")
    if isinstance(nested, Mapping) and nested.get("resource_type"):
        return str(nested["resource_type"])
    return str(manifest.get("resource_type") or "Resource")


def _io_contract(manifest: Mapping[str, Any], key: str) -> Any:
    io = manifest.get("io")
    if isinstance(io, Mapping) and io.get(key) is not None:
        return io.get(key)
    return manifest.get(key)


def _compact_outputs(contract: Any) -> list[str]:
    if isinstance(contract, list):
        values = []
        for item in contract:
            if isinstance(item, Mapping):
                value = item.get("semantic_type") or item.get("name") or item.get("kind")
                if value:
                    values.append(str(value))
        return list(dict.fromkeys(values))
    if not isinstance(contract, Mapping):
        return []
    values = []
    for key in ("semantic_output_kind", "artifact_type", "format"):
        if contract.get(key):
            values.append(str(contract[key]))
    schema_hint = contract.get("schema_hint")
    if schema_hint and not values:
        values.append(str(schema_hint))
    return list(dict.fromkeys(values))


def _canonical_artifact_type(value: Any) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_")
    return {
        "coq_source": "code",
        "text": "plaintext",
        "text/plain": "plaintext",
    }.get(
        normalized, normalized
    )


# Transport envelopes describe how bytes cross a provider boundary.  A
# declared capability operation can narrow the semantic value carried by that
# envelope.  Keep the two facts together so a code-generation operation may
# feed a typed code writer while ordinary text operations remain plaintext.
_OPERATION_SEMANTIC_OUTPUT_TYPES: dict[str, tuple[str, ...]] = {
    "code_generation": ("code",),
}


def _compact_inputs(contract: Any) -> list[CapabilityPort]:
    if not isinstance(contract, list):
        return []
    return [
        CapabilityPort(
            name=str(item["name"]),
            kind=str(item.get("semantic_type") or item.get("kind") or "unknown"),
            required=bool(item.get("required", False)),
            content_encoding=item.get("content_encoding"),
        )
        for item in contract
        if isinstance(item, Mapping) and item.get("name")
    ]


def _availability(manifest: Mapping[str, Any]) -> str:
    execution = manifest.get("execution")
    execution_status = execution.get("execution_status") if isinstance(execution, Mapping) else None
    status = str(execution_status or manifest.get("status") or "unknown").lower()
    if status in {"active", "available", "ready", "healthy"}:
        return "available"
    if status in {"inactive", "unavailable", "disabled", "failed"}:
        return "unavailable"
    return "unknown"


def _default_execution_operation(resource_type: str) -> str:
    return {
        "Tool": "run_tool",
        "Model": "call_model",
        "Agent": "call_agent",
        "Skill": "apply_context_hint",
        "Resource": "inspect_input",
        "Device": "environment_dependency",
    }.get(resource_type, "unknown")


def _declared_entrypoints(manifest: Mapping[str, Any]) -> list[str]:
    execution = manifest.get("execution")
    if not isinstance(execution, Mapping):
        return []
    raw = execution.get("entrypoints")
    if raw is None:
        return ["invoke"] if execution.get("uri") else []
    if not isinstance(raw, list):
        return []
    return [
        str(item.get("entrypoint_id"))
        for item in raw
        if isinstance(item, Mapping) and item.get("entrypoint_id")
    ]


def _material_access(
    inputs: list[CapabilityPort],
    *,
    resource_type: str = "",
    accepted_artifact_types: tuple[str, ...] | list[str] = (),
) -> str:
    path_kinds = {"path", "file_path", "directory_path", "artifact_handle"}
    inline_kinds = {
        "text",
        "string",
        "json",
        "object",
        "list",
        "int",
        "float",
        "bool",
        "chat_messages",
        "messages",
        "structured_data",
        "table",
    }

    def is_path_port(port: CapabilityPort) -> bool:
        name = port.name.strip().casefold().replace("-", "_")
        return bool(
            port.kind in path_kinds
            or name in {
                "path", "file", "file_path", "directory", "directory_path",
                "repo_path", "project_path", "proj_dir", "workspace_path",
            }
            or name.endswith(("_file_path", "_directory_path", "_repo_path"))
        )

    has_path = any(is_path_port(item) for item in inputs)
    has_inline = any(
        item.kind in inline_kinds and not is_path_port(item)
        for item in inputs
    )
    declared_media = {
        str(item).strip().lower().replace("-", "_")
        for item in accepted_artifact_types
        if str(item).strip()
    }
    if (
        has_inline
        and resource_type in {"Model", "Agent"}
        and declared_media.intersection({"image", "audio"})
    ):
        # The sealed runtime projects authorized image/audio handles into the
        # chat_messages port after exact byte verification.
        has_path = True
    if has_path and has_inline:
        return "both"
    if has_path:
        return "artifact_handle"
    if has_inline:
        return "inline"
    return "none" if inputs else "unknown"


def _operation_determinism(
    *,
    resource_type: str,
    execution: Mapping[str, Any],
    semantics: Mapping[str, Any],
    type_specific: Mapping[str, Any],
) -> str:
    """Project execution character only from declared structural metadata.

    An explicit manifest declaration is authoritative.  A standard model chat
    runtime is intrinsically generative, so its operation is known to be
    nondeterministic even when older manifests predate ``execution_semantics``.
    No corresponding inference is made for Tools, Skills, Resources, Devices,
    or opaque Agent runtimes; those remain fail-closed as ``unknown``.
    """

    declared = str(semantics.get("determinism") or "").strip().casefold()
    if declared in {"deterministic", "nondeterministic", "unknown"}:
        return declared
    type_block = type_specific.get(resource_type.casefold())
    if isinstance(type_block, Mapping):
        deterministic = type_block.get("deterministic")
        if isinstance(deterministic, bool):
            return "deterministic" if deterministic else "nondeterministic"
    runtime = str(execution.get("runtime") or "").strip().casefold()
    if resource_type == "Model" and runtime in {
        "llm_chat_completion",
        "openai_chat_completion",
        "chat_completion",
    }:
        return "nondeterministic"
    return "unknown"


def _declared_capability_operations(
    manifest: Mapping[str, Any],
    *,
    resource_type: str,
) -> list[str]:
    """Project operations from explicit manifest capability declarations."""

    declared = set(manifest_capability_operations(dict(manifest)))
    type_specific = manifest.get("type_specific")
    type_specific = type_specific if isinstance(type_specific, Mapping) else {}
    model = type_specific.get("model")
    model = model if isinstance(model, Mapping) else {}
    supports = model.get("supports")
    supports = supports if isinstance(supports, Mapping) else {}
    if resource_type == "Model" and supports.get("coding") is True:
        declared.add("code_generation")
    return sorted(declared)


def _capability_operations(
    manifest: Mapping[str, Any],
    *,
    resource_id: str,
    resource_type: str,
    inputs: list[CapabilityPort],
    outputs: list[str],
) -> list[CapabilityOperationV2]:
    capability = manifest.get("capability")
    capability = capability if isinstance(capability, Mapping) else {}
    declared = _declared_capability_operations(
        manifest,
        resource_type=resource_type,
    )
    if not declared:
        return []
    entrypoints = _declared_entrypoints(manifest)
    operation_entrypoints = capability.get("operation_entrypoints")
    operation_entrypoints = (
        operation_entrypoints if isinstance(operation_entrypoints, Mapping) else {}
    )
    execution = manifest.get("execution")
    execution = execution if isinstance(execution, Mapping) else {}
    entrypoint_records = {
        str(item.get("entrypoint_id")): item
        for item in (execution.get("entrypoints") or ())
        if isinstance(item, Mapping) and item.get("entrypoint_id")
    }
    semantics = capability.get("execution_semantics")
    semantics = semantics if isinstance(semantics, Mapping) else {}
    type_specific = manifest.get("type_specific")
    type_specific = type_specific if isinstance(type_specific, Mapping) else {}
    determinism = _operation_determinism(
        resource_type=resource_type,
        execution=execution,
        semantics=semantics,
        type_specific=type_specific,
    )
    side_effects = str(semantics.get("side_effects") or "unknown")
    if side_effects not in {"none", "declared", "unknown"}:
        side_effects = "unknown"
    effect_targets = semantics.get("effect_targets") or ()
    if not isinstance(effect_targets, (list, tuple)):
        raise ValueError("effect_targets_must_be_list")
    effect_targets = sorted({str(item) for item in effect_targets})
    modalities = [
        str(item) for item in (semantics.get("modalities") or ()) if str(item)
    ]
    constraint = manifest.get("constraint")
    constraint = constraint if isinstance(constraint, Mapping) else {}

    def artifact_types(value: Any) -> list[str]:
        raw_values = value if isinstance(value, (list, tuple, set)) else [value]
        return sorted(
            {
                _canonical_artifact_type(item)
                for item in raw_values
                if str(item or "").strip()
            }
        )

    accepted_artifact_types = artifact_types(constraint.get("artifact_input"))
    declared_produced_artifact_types = artifact_types(
        constraint.get("artifact_output")
    )
    declared_materialized_artifact_types = artifact_types(
        constraint.get("materialized_artifact_types")
    )
    if not declared_produced_artifact_types:
        declared_produced_artifact_types = sorted(
            {
                _canonical_artifact_type(item)
                for item in outputs
                if _canonical_artifact_type(item)
            }
        )
    result: list[CapabilityOperationV2] = []
    for operation in declared:
        entrypoint_id = operation_entrypoints.get(operation)
        if entrypoint_id is None and len(entrypoints) == 1:
            entrypoint_id = entrypoints[0]
        if entrypoint_id is not None and str(entrypoint_id) not in entrypoints:
            entrypoint_id = None
        entrypoint_record = entrypoint_records.get(str(entrypoint_id))
        operation_inputs = (
            _compact_inputs(entrypoint_record.get("input_contract"))
            if entrypoint_record is not None
            else list(inputs)
        )
        operation_outputs = (
            _compact_outputs(entrypoint_record.get("output_contract"))
            if entrypoint_record is not None
            else list(outputs)
        )
        operation_produced_types = sorted(
            {
                *(
                    _canonical_artifact_type(item)
                    for item in operation_outputs
                    if _canonical_artifact_type(item)
                ),
                *declared_produced_artifact_types,
                *_OPERATION_SEMANTIC_OUTPUT_TYPES.get(operation, ()),
            }
        )
        mapped_kind = CAPABILITY_TO_EXECUTION_OPERATION.get(
            operation,
            _default_execution_operation(resource_type),
        )
        evidence_status = (
            "declared"
            if operation != "invoke" and entrypoint_id is not None
            else "partial"
            if entrypoint_id is not None
            else "unknown"
        )
        result.append(
            CapabilityOperationV2(
                capability_operation_id=f"{resource_id}::{operation}",
                declared_operation=operation,
                execution_operation_kind=mapped_kind,
                entrypoint_id=str(entrypoint_id) if entrypoint_id is not None else None,
                input_ports=operation_inputs,
                output_semantics=operation_outputs,
                accepted_artifact_types=accepted_artifact_types,
                produced_artifact_types=operation_produced_types,
                materialized_artifact_types=declared_materialized_artifact_types,
                determinism=determinism,
                material_access=_material_access(
                    operation_inputs,
                    resource_type=resource_type,
                    accepted_artifact_types=accepted_artifact_types,
                ),
                side_effects=side_effects,
                effect_targets=effect_targets,
                modalities=modalities,
                evidence_status=evidence_status,
            )
        )
    return result


def build_capability_card(manifest: Mapping[str, Any]) -> CapabilityCard:
    """Project one raw manifest without any LLM call or generated claims."""
    capability = manifest.get("capability")
    capability = capability if isinstance(capability, Mapping) else {}
    routing = manifest.get("routing")
    routing = routing if isinstance(routing, Mapping) else {}
    resource_type = _resource_type(manifest)
    from retrieval_profiles import declared_task_context
    summary = declared_task_context(manifest)
    raw_inputs = _io_contract(manifest, "input_contract")
    inputs = _compact_inputs(raw_inputs)
    from retrieval_profiles import declared_resource_limits
    limitations = declared_resource_limits(manifest)
    limitations.extend(_TYPE_LIMITATIONS.get(resource_type, ()))
    resource_id = str(manifest.get("resource_id") or manifest.get("id") or "unknown")
    outputs = _compact_outputs(_io_contract(manifest, "output_contract"))
    operations = _declared_capability_operations(
        manifest,
        resource_type=resource_type,
    )
    return CapabilityCard(
        resource_id=resource_id,
        resource_type=resource_type,
        summary=summary,
        operations=operations,
        inputs=inputs,
        outputs=outputs,
        domains=[str(item) for item in (capability.get("domain_tags") or [])],
        limitations=list(dict.fromkeys(limitations)),
        availability=_availability(manifest),
        evidence_level=_EVIDENCE_LEVEL.get(resource_type, "context"),
        capability_operations=_capability_operations(
            manifest,
            resource_id=resource_id,
            resource_type=resource_type,
            inputs=inputs,
            outputs=outputs,
        ),
        summary_status="declared" if summary else "unknown",
    )


def build_capability_cards(resource_index: Mapping[str, Mapping[str, Any]]) -> dict[str, CapabilityCard]:
    """Build in-memory cards for the current resource snapshot."""
    from .model_selection import is_candidate_resource
    return {resource_id: build_capability_card(manifest) for resource_id, manifest in resource_index.items()
            if is_candidate_resource(manifest)}


def resource_semantic_cjk_paths(manifest: Mapping[str, Any]) -> tuple[str, ...]:
    """Return model-visible resource semantic paths containing CJK text."""

    roots = {
        "capability": manifest.get("capability"),
        "constraint": manifest.get("constraint"),
        "routing": manifest.get("routing"),
        "limitations": manifest.get("limitations"),
        "type.resource_tag": (
            manifest.get("type", {}).get("resource_tag")
            if isinstance(manifest.get("type"), Mapping)
            else None
        ),
    }
    findings: list[str] = []

    def visit(value: Any, path: str) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                visit(item, f"{path}.{key}" if path else str(key))
        elif isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                visit(item, f"{path}[{index}]")
        elif isinstance(value, str) and _CJK.search(value):
            findings.append(path)

    for root_path, value in roots.items():
        if value is not None:
            visit(value, root_path)
    return tuple(sorted(set(findings)))


def build_capability_consistency_report(
    resource_index: Mapping[str, Mapping[str, Any]],
) -> CapabilityCatalogConsistencyReportV1:
    """Report only manifest-provable capability gaps; never synthesize claims."""

    items: list[CapabilityConsistencyItemV1] = []
    known_types = {"Tool", "Model", "Agent", "Skill", "Resource", "Device"}
    for index_resource_id, manifest in sorted(resource_index.items()):
        card = build_capability_card(manifest)
        issues: list[str] = []
        if not index_resource_id or card.resource_id != index_resource_id:
            issues.append("resource_identity_mismatch")
        if card.resource_type not in known_types:
            issues.append("resource_type_unknown")
        if card.summary_status == "unknown":
            issues.append("summary_unknown")
        if card.availability == "unknown":
            issues.append("availability_unknown")
        if not card.capability_operations:
            issues.append("capability_operations_unknown")
        if resource_semantic_cjk_paths(manifest):
            issues.append("model_visible_semantics_non_english")
        for operation in card.capability_operations:
            if operation.entrypoint_id is None:
                issues.append("operation_entrypoint_unknown")
            if operation.execution_operation_kind == "unknown":
                issues.append("execution_operation_kind_unknown")
            if operation.evidence_status == "unknown":
                issues.append("operation_evidence_unknown")
            if any(port.kind == "unknown" for port in operation.input_ports):
                issues.append("input_port_type_unknown")
            if not operation.output_semantics and card.resource_type != "Device":
                issues.append("output_contract_unknown")
            if not operation.produced_artifact_types and card.resource_type != "Device":
                issues.append("produced_artifact_type_unknown")
        try:
            # Local import avoids a module-initialization cycle: ResourceDefinition
            # itself builds the capability card used by this report.
            from .resource_runtime import (
                ResourceDefinition,
                ResourceManifestError,
                runtime_adapter_supported,
            )

            definition = ResourceDefinition.from_manifest(manifest)
        except (ResourceManifestError, TypeError, ValueError):
            issues.append("resource_execution_contract_invalid")
        else:
            runtime_kind = str(
                definition.runtime_requirements.get("runtime_kind") or ""
            )
            if not runtime_adapter_supported(card.resource_type, runtime_kind):
                issues.append("runtime_adapter_unsupported")
        issue_codes = tuple(sorted(set(issues)))
        fatal = {
            "resource_identity_mismatch",
            "resource_type_unknown",
            "capability_operations_unknown",
            "operation_entrypoint_unknown",
            "execution_operation_kind_unknown",
            "operation_evidence_unknown",
            "input_port_type_unknown",
            "output_contract_unknown",
            "produced_artifact_type_unknown",
            "model_visible_semantics_non_english",
            "resource_execution_contract_invalid",
            "runtime_adapter_unsupported",
        }
        items.append(
            CapabilityConsistencyItemV1(
                resource_id=index_resource_id,
                resource_type=card.resource_type,
                sealable=not bool(set(issue_codes) & fatal),
                issue_codes=issue_codes,
                card_sha256=card.card_sha256,
            )
        )
    return CapabilityCatalogConsistencyReportV1(
        resource_count=len(items),
        sealable_resource_count=sum(item.sealable for item in items),
        items=tuple(items),
    )


def select_capability_cards(
    query: str,
    cards: Mapping[str, CapabilityCard],
    *,
    retrieved_resource_ids: Iterable[str] = (),
    limit: int = 10,
) -> list[CapabilityCard]:
    """Project the local semantic retrieval order into bounded Planner cards.

    The query is intentionally not reparsed here.  Formal Resource-Aware
    planning obtains relevance from the locked embedding/index runtime, so
    resource IDs, filenames, task keywords and historical cases cannot create
    a second hidden routing policy.  ``query`` remains in the compatibility
    signature for offline callers.
    """

    del query
    selected: list[CapabilityCard] = []
    for resource_id in dict.fromkeys(str(item) for item in retrieved_resource_ids):
        card = cards.get(resource_id)
        if card is None or card.availability == "unavailable":
            continue
        selected.append(card)
        if len(selected) >= max(0, limit):
            break
    return selected


def serialize_capability_cards(cards: Iterable[CapabilityCard]) -> str:
    """Render a bounded Planner context; full manifests remain private."""
    lines = []
    for card in cards:
        inputs = ", ".join(
            f"{item.name}:{item.kind}{'*' if item.required else ''}" for item in card.inputs
        ) or "none declared"
        lines.extend([
            f"[{card.resource_type}/{card.evidence_level}] {card.resource_id}",
            f"Does: {card.summary}",
            f"Operations: {', '.join(card.operations) or 'none declared'}",
            f"Inputs: {inputs}",
            f"Outputs: {', '.join(card.outputs) or 'unspecified'}",
            f"Status: {card.availability}",
        ])
        if card.limitations:
            lines.append(f"Limits: {'; '.join(card.limitations)}")
        lines.append("")
    return "\n".join(lines).strip()
