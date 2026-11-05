"""Typed, canonical user-message envelope for Planner calls."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal, Mapping, Sequence, cast

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from .capability_cards import (
    RESOURCE_CAPABILITY_CARD_PROTOCOL,
    CapabilityCard,
    CapabilityOperationV2,
)
from .pipeline_control import canonical_json_bytes, canonical_sha256
from .planner_capability_catalog import PlannerCapabilityCatalogV1
from .text_format_contract import (
    TextFormatContract,
    exact_final_response_from_request,
)


PLANNER_INPUT_PROTOCOL = "sgar-planner-input-v1"
PLANNER_INPUT_V2_PROTOCOL = "sgar-planner-input-v2"
_PUBLIC_INVOCATION_MARKER = "\n\n[SGAR_PUBLIC_INVOCATION]\n"
_COMPLETED_ARTIFACT_EXCERPT_CHARS = 500
_PLANNER_INLINE_INPUT_LIMIT_BYTES = 16 * 1024
_PLANNER_EXCERPT_LIMIT_CHARS = 4096
_PLANNER_TOTAL_INLINE_INPUT_BYTES = 32 * 1024
_PLANNER_DETAILED_INPUT_LIMIT = 32


class _PlannerInputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PlannerPublicInputV1(_PlannerInputModel):
    protocol: str
    logical_name: str = Field(min_length=1)
    handle_id: str = Field(min_length=1)
    evidence_source_id: str = Field(min_length=1)
    runtime_path: str = Field(min_length=1)
    path_kind: Literal["file", "directory"]
    source_name: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    extension: str
    content_sha256: str
    byte_size: int = Field(ge=0)
    entry_count: int = Field(ge=0)
    inline_text: str | None
    content_available_as_context: bool
    tree_manifest_sha256: str | None
    original_bytes: int = Field(default=0, ge=0)
    included_bytes: int = Field(default=0, ge=0)
    included_sha256: str | None = None
    coverage_status: Literal["complete", "handle_only"] = "handle_only"
    utf8_decodable: bool | None = None
    execution_contract: dict[str, Any] = Field(default_factory=dict)

    @model_serializer(mode="wrap")
    def _serialize_execution_contract(self, handler):
        payload = handler(self)
        if not self.execution_contract:
            payload.pop("execution_contract", None)
        return payload

    @model_validator(mode="before")
    @classmethod
    def _material_coverage(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        projected = dict(value)
        handle_id = str(projected.get("handle_id") or "").strip()
        if handle_id:
            projected.setdefault("evidence_source_id", f"artifact:{handle_id}")
        byte_size = int(projected.get("byte_size") or 0)
        inline_text = projected.get("inline_text")
        projected.setdefault("original_bytes", byte_size)
        if isinstance(inline_text, str):
            encoded = inline_text.encode("utf-8")
            projected.setdefault("included_bytes", len(encoded))
            projected.setdefault("included_sha256", hashlib.sha256(encoded).hexdigest())
            projected.setdefault("coverage_status", "complete")
            projected.setdefault("utf8_decodable", True)
        else:
            projected.setdefault("included_bytes", 0)
            projected.setdefault("included_sha256", None)
            projected.setdefault("coverage_status", "handle_only")
        return projected

    @model_validator(mode="after")
    def _validate_material_coverage(self) -> "PlannerPublicInputV1":
        if self.evidence_source_id != f"artifact:{self.handle_id}":
            raise ValueError("planner_public_input_evidence_source_id_mismatch")
        if self.original_bytes != self.byte_size:
            raise ValueError("planner_public_input_original_bytes_mismatch")
        if self.coverage_status == "complete":
            if self.inline_text is None or self.included_sha256 is None:
                raise ValueError("planner_public_input_complete_material_missing")
            if self.included_bytes != self.original_bytes:
                raise ValueError("planner_public_input_complete_bytes_mismatch")
            if self.included_sha256 != self.content_sha256:
                raise ValueError("planner_public_input_complete_hash_mismatch")
        elif self.inline_text is not None or self.included_bytes != 0:
            raise ValueError("planner_public_input_handle_only_has_content")
        return self


class PlannerFinalDeliverableV1(_PlannerInputModel):
    protocol: str
    representation: Literal["inline_text", "file", "directory", "bundle"]
    format_id: str = Field(min_length=1)
    media_type: str | None
    extension: str
    logical_name: str | None = None
    runtime_path: str | None = None
    primary_member: str | None
    required_members: list[str]
    contract_sha256: str

    @model_serializer(mode="wrap")
    def _serialize_optional_runtime_path(self, handler):
        payload = handler(self)
        if self.runtime_path is None:
            payload.pop("runtime_path", None)
        return payload


class PlannerCapabilityPortV1(_PlannerInputModel):
    name: str
    kind: str
    required: bool


class PlannerCapabilityCardV1(_PlannerInputModel):
    protocol: Literal["sgar-resource-capability-card-v2"] = (
        RESOURCE_CAPABILITY_CARD_PROTOCOL
    )
    resource_id: str
    resource_type: str
    summary: str
    operations: list[str]
    inputs: list[PlannerCapabilityPortV1]
    outputs: list[str]
    domains: list[str]
    limitations: list[str]
    availability: str
    evidence_level: str
    capability_operations: list[CapabilityOperationV2] = Field(default_factory=list)
    summary_status: Literal["declared", "unknown"] = "unknown"
    card_sha256: str = ""


class PlannerCompletedArtifactV1(_PlannerInputModel):
    task_id: str = Field(min_length=1)
    content_excerpt: str
    original_utf8_bytes: int = Field(ge=0)
    truncated: bool
    content_sha256: str


class PlannerProtectedContractV1(_PlannerInputModel):
    task_id: str = Field(min_length=1)
    contract: dict[str, Any]
    contract_sha256: str


class PlannerSourceClauseV1(_PlannerInputModel):
    """A deterministic locator into model-visible request or contract data."""

    clause_id: str = Field(min_length=1)
    source_kind: Literal[
        "request_text", "final_deliverable_contract", "protected_output_contract"
    ]
    content_sha256: str
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)
    json_pointer: str | None = None

    @model_validator(mode="after")
    def _locator_shape(self) -> "PlannerSourceClauseV1":
        if self.source_kind == "request_text":
            if (
                self.char_start is None
                or self.char_end is None
                or self.char_end <= self.char_start
                or self.json_pointer is not None
            ):
                raise ValueError("planner_request_clause_locator_invalid")
        elif (
            self.char_start is not None
            or self.char_end is not None
            or not self.json_pointer
        ):
            raise ValueError("planner_contract_clause_locator_invalid")
        return self


class PlannerInputEnvelopeV1(_PlannerInputModel):
    protocol: Literal["sgar-planner-input-v1"] = PLANNER_INPUT_PROTOCOL
    request_text: str = Field(min_length=1)
    public_invocation_protocol: str | None
    public_inputs: list[PlannerPublicInputV1]
    public_context_descriptors: list[dict[str, Any]]
    final_deliverable_contract: PlannerFinalDeliverableV1 | None
    source_clauses: list[PlannerSourceClauseV1]
    is_replanning: bool
    completed_artifacts: list[PlannerCompletedArtifactV1]
    protected_output_contracts: list[PlannerProtectedContractV1]
    capability_cards: list[PlannerCapabilityCardV1]
    envelope_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "PlannerInputEnvelopeV1":
        clause_ids = [item.clause_id for item in self.source_clauses]
        if not clause_ids or len(clause_ids) != len(set(clause_ids)):
            raise ValueError("planner_source_clause_catalog_invalid")
        expected = canonical_sha256(
            self.model_dump(mode="json", exclude={"envelope_sha256"})
        )
        if self.envelope_sha256 and self.envelope_sha256 != expected:
            raise ValueError("planner_input_envelope_sha256_mismatch")
        object.__setattr__(self, "envelope_sha256", expected)
        return self

    def user_message(self) -> str:
        return canonical_json_bytes(self.model_dump(mode="json")).decode("utf-8")


class PlannerRequestV2(_PlannerInputModel):
    text: str = Field(min_length=1)
    language: str = Field(min_length=1)


class PlannerPublicInputV2(_PlannerInputModel):
    input_ref: str = Field(min_length=1)
    logical_name: str = Field(min_length=1)
    artifact_type: Literal[
        "code", "json", "csv", "markdown", "plaintext", "file", "directory", "bundle",
        "xlsx", "xls", "docx", "doc", "pptx", "ppt", "pdf", "audio", "image",
    ]
    media_type: str = Field(min_length=1)
    access_mode: Literal["complete", "controlled_excerpt", "descriptor_only"]
    shape_summary: str = Field(min_length=1)
    content_excerpt: str


class PlannerCompletedOutputV2(_PlannerInputModel):
    output_ref: str = Field(min_length=1)
    logical_name: str = Field(min_length=1)
    artifact_type: Literal[
        "code", "json", "csv", "markdown", "plaintext", "file", "directory", "bundle"
    ]
    semantic_description: str = Field(min_length=1)


class PlannerFinalDeliverableV2(_PlannerInputModel):
    logical_name: str = Field(min_length=1)
    artifact_type: Literal[
        "code", "json", "csv", "markdown", "plaintext", "file", "directory", "bundle"
    ]
    requirements: list[str] = Field(min_length=1)
    contract_authority: Literal["explicit", "request_only"] = "request_only"
    representation: Literal["inline_text", "file", "directory", "bundle"] | None = None
    required_members: list[str] = Field(default_factory=list)
    runtime_path: str | None = None
    text_format: TextFormatContract | None = None

    @model_serializer(mode="wrap")
    def _serialize_optional_runtime_path(self, handler):
        payload = handler(self)
        if self.runtime_path is None:
            payload.pop("runtime_path", None)
        return payload

    @model_validator(mode="after")
    def _text_format_shape(self) -> "PlannerFinalDeliverableV2":
        if self.text_format is not None and (
            self.contract_authority != "explicit"
            or self.artifact_type != "plaintext"
            or self.representation != "inline_text"
        ):
            raise ValueError("planner_final_text_format_requires_explicit_inline_plaintext")
        return self


class PlannerLimitsV2(_PlannerInputModel):
    maximum_nodes: Literal[24] = 24


class PlannerInputEnvelopeV2(_PlannerInputModel):
    """The complete model-visible Planner V6 request envelope."""

    protocol: Literal[PLANNER_INPUT_V2_PROTOCOL] = PLANNER_INPUT_V2_PROTOCOL
    request: PlannerRequestV2
    public_inputs: list[PlannerPublicInputV2]
    completed_outputs: list[PlannerCompletedOutputV2]
    final_deliverable: PlannerFinalDeliverableV2
    capability_context: list[dict[str, Any]]
    source_clauses: list[PlannerSourceClauseV1] = Field(default_factory=list)
    limits: PlannerLimitsV2 = Field(default_factory=PlannerLimitsV2)

    @model_validator(mode="after")
    def _references(self) -> "PlannerInputEnvelopeV2":
        public_refs = [item.input_ref for item in self.public_inputs]
        completed_refs = [item.output_ref for item in self.completed_outputs]
        if len(public_refs) != len(set(public_refs)):
            raise ValueError("planner_v2_public_input_ref_duplicate")
        if len(completed_refs) != len(set(completed_refs)):
            raise ValueError("planner_v2_completed_output_ref_duplicate")
        if set(public_refs) & set(completed_refs):
            raise ValueError("planner_v2_input_reference_namespace_collision")
        return self

    @property
    def envelope_sha256(self) -> str:
        return canonical_sha256(self.model_dump(mode="json"))

    def user_message(self) -> str:
        payload = self.model_dump(mode="json")
        if len(self.public_inputs) > _PLANNER_DETAILED_INPUT_LIMIT:
            detailed = [
                item for item in self.public_inputs if item.content_excerpt
            ][:_PLANNER_DETAILED_INPUT_LIMIT]
            selected = {item.input_ref for item in detailed}
            for item in self.public_inputs:
                if len(detailed) >= _PLANNER_DETAILED_INPUT_LIMIT:
                    break
                if item.input_ref not in selected:
                    detailed.append(item)
                    selected.add(item.input_ref)
            payload["public_inputs"] = [item.model_dump(mode="json") for item in detailed]
            payload["public_input_index"] = {
                "protocol": "sgar-planner-public-input-index-v1",
                "columns": ["input_ref", "logical_name_if_different", "artifact_type", "access_mode"],
                "rows": [
                    [
                        item.input_ref,
                        item.logical_name if item.logical_name != item.input_ref else "",
                        item.artifact_type,
                        item.access_mode,
                    ]
                    for item in self.public_inputs
                ],
                "indexed_only_content": "Read through an authorized runtime handle before using file contents.",
            }
        return canonical_json_bytes(payload).decode("utf-8")


def _split_public_invocation(query: str) -> tuple[str, dict[str, Any] | None]:
    if _PUBLIC_INVOCATION_MARKER not in query:
        return query, None
    request_text, encoded = query.rsplit(_PUBLIC_INVOCATION_MARKER, 1)
    try:
        decoded_value: Any = json.loads(encoded)
    except (TypeError, ValueError, json.JSONDecodeError):
        return query, None
    if not isinstance(decoded_value, dict):
        return query, None
    decoded = cast(dict[str, Any], decoded_value)
    if not str(decoded.get("protocol") or ""):
        return query, None
    return request_text, decoded


def _object_sequence(value: Any, *, failure_code: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(failure_code)
    result: list[dict[str, Any]] = []
    for raw_item in cast(Sequence[Any], value):
        if not isinstance(raw_item, Mapping):
            raise ValueError(failure_code)
        result.append(dict(cast(Mapping[str, Any], raw_item)))
    return result


def _completed_artifacts(
    values: Mapping[str, Any] | None,
) -> list[PlannerCompletedArtifactV1]:
    result: list[PlannerCompletedArtifactV1] = []
    for task_id, value in sorted((values or {}).items(), key=lambda item: str(item[0])):
        content = str(value)
        encoded = content.encode("utf-8")
        result.append(
            PlannerCompletedArtifactV1(
                task_id=str(task_id),
                content_excerpt=content[:_COMPLETED_ARTIFACT_EXCERPT_CHARS],
                original_utf8_bytes=len(encoded),
                truncated=len(content) > _COMPLETED_ARTIFACT_EXCERPT_CHARS,
                content_sha256=hashlib.sha256(encoded).hexdigest(),
            )
        )
    return result


def _protected_contracts(
    values: Mapping[str, Mapping[str, Any]] | None,
) -> list[PlannerProtectedContractV1]:
    result: list[PlannerProtectedContractV1] = []
    for task_id, value in sorted((values or {}).items(), key=lambda item: str(item[0])):
        contract = dict(value)
        result.append(
            PlannerProtectedContractV1(
                task_id=str(task_id),
                contract=contract,
                contract_sha256=canonical_sha256(contract),
            )
        )
    return result


def _source_clause_catalog(
    *,
    request_text: str,
    final_contract: PlannerFinalDeliverableV1 | None,
    protected_contracts: Sequence[PlannerProtectedContractV1],
) -> list[PlannerSourceClauseV1]:
    clauses: list[PlannerSourceClauseV1] = []
    for index, match in enumerate(re.finditer(r"(?m)^\s*\S.*$", request_text), start=1):
        start = match.start()
        end = match.end()
        content = request_text[start:end]
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        clauses.append(
            PlannerSourceClauseV1(
                clause_id=f"request:{index:04d}:{digest[:12]}",
                source_kind="request_text",
                content_sha256=digest,
                char_start=start,
                char_end=end,
            )
        )
    if not clauses:
        raise ValueError("planner_request_clause_catalog_empty")
    if final_contract is not None:
        clauses.append(
            PlannerSourceClauseV1(
                clause_id=(
                    "public_contract:final_deliverable:"
                    f"{final_contract.contract_sha256[:12]}"
                ),
                source_kind="final_deliverable_contract",
                content_sha256=final_contract.contract_sha256,
                json_pointer="/final_deliverable_contract",
            )
        )
    for item in protected_contracts:
        clauses.append(
            PlannerSourceClauseV1(
                clause_id=(
                    f"protected_contract:{item.task_id}:"
                    f"{item.contract_sha256[:12]}"
                ),
                source_kind="protected_output_contract",
                content_sha256=item.contract_sha256,
                json_pointer=f"/protected_output_contracts/{item.task_id}",
            )
        )
    return clauses


def build_planner_input_envelope(
    *,
    query: str,
    completed_artifacts: Mapping[str, Any] | None,
    original_contracts: Mapping[str, Mapping[str, Any]] | None,
    capability_cards: Sequence[CapabilityCard],
) -> PlannerInputEnvelopeV1:
    request_text, public = _split_public_invocation(str(query))
    public = public or {}
    final_contract = public.get("final_deliverable_contract")
    public_inputs = _object_sequence(
        public.get("public_inputs"),
        failure_code="planner_public_inputs_not_object_sequence",
    )
    context_descriptors = _object_sequence(
        public.get("public_context_descriptors"),
        failure_code="planner_public_context_descriptors_not_object_sequence",
    )
    typed_final_contract = (
        PlannerFinalDeliverableV1.model_validate(final_contract)
        if isinstance(final_contract, Mapping)
        else None
    )
    typed_protected_contracts = _protected_contracts(original_contracts)
    return PlannerInputEnvelopeV1(
        request_text=request_text,
        public_invocation_protocol=(
            str(public.get("protocol")) if public.get("protocol") else None
        ),
        public_inputs=[
            PlannerPublicInputV1.model_validate(item)
            for item in public_inputs
        ],
        public_context_descriptors=context_descriptors,
        final_deliverable_contract=typed_final_contract,
        source_clauses=_source_clause_catalog(
            request_text=request_text,
            final_contract=typed_final_contract,
            protected_contracts=typed_protected_contracts,
        ),
        is_replanning=bool(completed_artifacts),
        completed_artifacts=_completed_artifacts(completed_artifacts),
        protected_output_contracts=typed_protected_contracts,
        capability_cards=[
            PlannerCapabilityCardV1.model_validate(card.model_dump(mode="json"))
            for card in capability_cards
        ],
    )


def _portable_artifact_type(
    *,
    extension: str = "",
    media_type: str = "",
    path_kind: str = "file",
    format_id: str = "",
    preserve_input_modality: bool = False,
) -> str:
    if str(path_kind).strip().lower() == "directory":
        return "directory"
    normalized_extension = str(extension).strip().lower()
    normalized_media = str(media_type).strip().lower()
    normalized_format = str(format_id).strip().lower()
    by_extension = {
        ".py": "code", ".js": "code", ".ts": "code", ".java": "code",
        ".v": "code", ".ml": "code", ".mli": "code", ".hs": "code",
        ".vo": "file", ".vok": "file",
        ".json": "json", ".csv": "csv", ".md": "markdown",
        ".markdown": "markdown", ".txt": "plaintext",
    }
    if preserve_input_modality:
        by_extension.update({
            ".xlsx": "xlsx", ".xls": "xls", ".pdf": "pdf",
            ".docx": "docx", ".doc": "doc",
            ".pptx": "pptx", ".ppt": "ppt",
            ".mp3": "audio", ".wav": "audio", ".m4a": "audio",
            ".flac": "audio", ".ogg": "audio",
            ".png": "image", ".jpg": "image", ".jpeg": "image", ".webp": "image",
        })
    if normalized_extension in by_extension:
        return by_extension[normalized_extension]
    for token, artifact_type in (
        ("json", "json"), ("csv", "csv"), ("markdown", "markdown"),
        ("text", "plaintext"), ("code", "code"), ("bundle", "bundle"),
        ("directory", "directory"),
    ):
        if token in normalized_media or token in normalized_format:
            return artifact_type
    if preserve_input_modality:
        for token, artifact_type in (
            ("spreadsheet", "xlsx"), ("excel", "xlsx"), ("pdf", "pdf"),
            ("wordprocessing", "docx"), ("msword", "doc"),
            ("presentation", "pptx"), ("powerpoint", "ppt"),
            ("audio", "audio"), ("image", "image"),
        ):
            if token in normalized_media or token in normalized_format:
                return artifact_type
    return "file"


def _request_language(text: str) -> str:
    cjk = sum("\u3400" <= character <= "\u9fff" for character in text)
    latin = sum(character.isascii() and character.isalpha() for character in text)
    return "zh" if cjk > latin else "en"


def _planner_public_inputs_v2(
    values: Sequence[Mapping[str, Any]],
    *,
    request_text: str,
) -> list[PlannerPublicInputV2]:
    inputs = [PlannerPublicInputV1.model_validate(raw) for raw in values]
    request_lower = request_text.casefold()

    def priority(index: int) -> tuple[int, int]:
        name = str(inputs[index].source_name or inputs[index].logical_name).casefold()
        basename = name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        # Prefer material explicitly named by the request, followed by concise
        # repository orientation. Every other input remains addressable by ref.
        if basename and basename in request_lower:
            return (0, index)
        if any(token in basename for token in ("readme", "agents.md", "instructions", "task.md")):
            return (1, index)
        return (2, index)

    excerpts: dict[int, str] = {}
    remaining = _PLANNER_TOTAL_INLINE_INPUT_BYTES
    for index in sorted(range(len(inputs)), key=priority):
        if len(excerpts) >= _PLANNER_DETAILED_INPUT_LIMIT:
            break
        inline_text = inputs[index].inline_text
        if not inline_text or remaining <= 0:
            continue
        per_file_limit = (
            len(inline_text)
            if len(inline_text.encode("utf-8")) <= _PLANNER_INLINE_INPUT_LIMIT_BYTES
            else _PLANNER_EXCERPT_LIMIT_CHARS
        )
        limited = inline_text[:per_file_limit]
        encoded = limited.encode("utf-8")[:remaining]
        excerpt = encoded.decode("utf-8", errors="ignore")
        if excerpt:
            excerpts[index] = excerpt
            remaining -= len(excerpt.encode("utf-8"))

    result: list[PlannerPublicInputV2] = []
    for index, item in enumerate(inputs):
        input_ref = str(item.logical_name).strip()
        logical_name = str(item.source_name or item.logical_name).strip()
        inline_text = item.inline_text if isinstance(item.inline_text, str) else ""
        inline_bytes = len(inline_text.encode("utf-8")) if inline_text else 0
        content_excerpt = excerpts.get(index, "")
        if content_excerpt and inline_bytes <= _PLANNER_INLINE_INPUT_LIMIT_BYTES and content_excerpt == inline_text:
            access_mode = "complete"
        elif content_excerpt:
            access_mode = "controlled_excerpt"
        else:
            access_mode = "descriptor_only"
        artifact_type = _portable_artifact_type(
            extension=item.extension,
            media_type=item.media_type,
            path_kind=item.path_kind,
            preserve_input_modality=True,
        )
        shape_parts = [
            f"{artifact_type} {item.path_kind}",
            f"{item.entry_count} declared entries" if item.entry_count else "single declared artifact",
        ]
        inventory = item.execution_contract.get("container_inventory")
        if isinstance(inventory, Mapping):
            shape_parts.append("observed container directory (member contents unread): "
                               + json.dumps(inventory, ensure_ascii=False, separators=(",", ":")))
        if access_mode == "complete":
            shape_parts.append("complete authorized text is included")
        elif access_mode == "controlled_excerpt":
            shape_parts.append("a controlled authorized excerpt is included")
        else:
            shape_parts.append("content is available only through a runtime artifact handle")
        result.append(
            PlannerPublicInputV2(
                input_ref=input_ref,
                logical_name=logical_name,
                artifact_type=artifact_type,
                media_type=item.media_type,
                access_mode=cast(Any, access_mode),
                shape_summary="; ".join(shape_parts),
                content_excerpt=content_excerpt,
            )
        )
    return result


def _planner_completed_outputs_v2(
    completed_artifacts: Mapping[str, Any] | None,
    original_contracts: Mapping[str, Mapping[str, Any]] | None,
) -> list[PlannerCompletedOutputV2]:
    result: list[PlannerCompletedOutputV2] = []
    contracts = original_contracts or {}
    for task_id in sorted((completed_artifacts or {}), key=str):
        raw_contract = dict(contracts.get(str(task_id), {}))
        nested = raw_contract.get("output_contract")
        contract = dict(nested) if isinstance(nested, Mapping) else raw_contract
        artifact_type = _portable_artifact_type(
            extension=str(contract.get("output_extension") or raw_contract.get("output_extension") or ""),
            format_id=str(contract.get("artifact_type") or raw_contract.get("artifact_type") or ""),
        )
        produced_files = contract.get("produced_files")
        logical_name = str(task_id)
        if isinstance(produced_files, Sequence) and not isinstance(produced_files, (str, bytes)):
            for produced in produced_files:
                if isinstance(produced, Mapping) and produced.get("path_hint"):
                    logical_name = str(produced["path_hint"])
                    break
        required_content = contract.get("required_content")
        description = "Previously completed and immutable output"
        if isinstance(required_content, Sequence) and not isinstance(required_content, (str, bytes)):
            values = [str(item).strip() for item in required_content if str(item).strip()]
            if values:
                description = "; ".join(values[:6])
        result.append(
            PlannerCompletedOutputV2(
                output_ref=str(task_id),
                logical_name=logical_name,
                artifact_type=cast(Any, artifact_type),
                semantic_description=description,
            )
        )
    return result



def _planner_final_deliverable_v2(
    value: Mapping[str, Any] | None,
    *,
    request_text: str,
) -> PlannerFinalDeliverableV2:
    if value is None:
        exact_response = exact_final_response_from_request(request_text)
        if exact_response is not None:
            _literal, text_format = exact_response
            return PlannerFinalDeliverableV2(
                logical_name="final_response",
                artifact_type="plaintext",
                requirements=[text_format.requirement_quote],
                contract_authority="explicit",
                representation="inline_text",
                text_format=text_format,
            )
        return PlannerFinalDeliverableV2(
            logical_name="requested_deliverable",
            artifact_type="file",
            requirements=["Produce the complete user-requested deliverable"],
            contract_authority="request_only",
        )
    typed = PlannerFinalDeliverableV1.model_validate(value)
    logical_name = str(
        typed.logical_name
        or typed.primary_member
        or f"delivery{typed.extension or ''}"
    ).strip()
    requirements = [str(item).strip() for item in typed.required_members if str(item).strip()]
    if not requirements:
        requirements = ["Satisfy the declared final deliverable contract"]
    return PlannerFinalDeliverableV2(
        logical_name=logical_name,
        artifact_type=cast(
            Any,
            _portable_artifact_type(
                extension=typed.extension,
                media_type=typed.media_type or "",
                format_id=typed.format_id,
                path_kind=("directory" if typed.representation == "directory" else "file"),
            ),
        ),
        requirements=requirements,
        contract_authority="explicit",
        representation=typed.representation,
        required_members=list(typed.required_members),
        runtime_path=typed.runtime_path,
    )


def build_planner_input_envelope_v2(
    *,
    query: str,
    completed_artifacts: Mapping[str, Any] | None,
    original_contracts: Mapping[str, Mapping[str, Any]] | None,
    capability_catalog: PlannerCapabilityCatalogV1,
) -> PlannerInputEnvelopeV2:
    """Build the compact V6 model input and keep runtime identities outside it."""

    request_text, public = _split_public_invocation(str(query))
    public = public or {}
    public_inputs = _object_sequence(
        public.get("public_inputs"),
        failure_code="planner_public_inputs_not_object_sequence",
    )
    final_deliverable = public.get("final_deliverable_contract")
    return PlannerInputEnvelopeV2(
        request=PlannerRequestV2(
            text=request_text,
            language=_request_language(request_text),
        ),
        public_inputs=_planner_public_inputs_v2(public_inputs, request_text=request_text),
        completed_outputs=_planner_completed_outputs_v2(
            completed_artifacts,
            original_contracts,
        ),
        final_deliverable=_planner_final_deliverable_v2(
            cast(Mapping[str, Any], final_deliverable)
            if isinstance(final_deliverable, Mapping)
            else None,
            request_text=request_text,
        ),
        capability_context=capability_catalog.model_projection(),
        source_clauses=_source_clause_catalog(
            request_text=request_text,
            final_contract=None,
            protected_contracts=(),
        ),
    )


__all__ = [
    "PLANNER_INPUT_PROTOCOL",
    "PLANNER_INPUT_V2_PROTOCOL",
    "PlannerInputEnvelopeV1",
    "PlannerInputEnvelopeV2",
    "PlannerSourceClauseV1",
    "build_planner_input_envelope",
    "build_planner_input_envelope_v2",
]
