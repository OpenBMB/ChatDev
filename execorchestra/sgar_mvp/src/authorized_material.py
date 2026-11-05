"""Authorized, bounded model material views for one formal recovery request.

The material layer is deliberately independent from retrieval and resource
selection.  It can expose verified public inputs and already-authorized run
artifacts to the one-shot Full Generation fallback, but it never turns those
inputs into resources or candidates and never persists their contents.
"""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from pydantic import Field, field_validator, model_validator

from .artifact_v2 import (
    ArtifactV2Error,
    build_evidence_v2,
    descriptor_for_path,
)
from .evaluation_contracts import ArtifactDescriptorV2
from .pipeline_control import (
    FrozenContract,
    SubtaskRevisionRef,
    canonical_json_bytes,
    canonical_sha256,
    subtask_revision_identity_sha256,
)


AUTHORIZED_MODEL_MATERIAL_PROTOCOL = "sgar-authorized-model-material-v1"
DEFAULT_PER_SOURCE_MATERIAL_BYTES = 64 * 1024
DEFAULT_TOTAL_MATERIAL_BYTES = 256 * 1024


class AuthorizedMaterialError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = str(code)
        super().__init__(self.code)


def _require_sha256(value: str, *, field_name: str) -> str:
    normalized = str(value or "").strip().lower()
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise ValueError(f"{field_name}_must_be_sha256")
    return normalized


def _utf8_prefix(value: str, maximum: int) -> str:
    raw = value.encode("utf-8")
    if len(raw) <= maximum:
        return value
    clipped = raw[: max(0, maximum)]
    while clipped:
        try:
            return clipped.decode("utf-8")
        except UnicodeDecodeError:
            clipped = clipped[:-1]
    return ""


def _is_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise AuthorizedMaterialError("authorized_material_source_unreadable") from exc
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    return bool(stat.S_ISLNK(metadata.st_mode) or attributes & 0x400)


def _file_sha256(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def public_snapshot_identity(path: str | Path) -> tuple[str, int, str]:
    """Recompute the TaskInvocation snapshot identity without following links."""

    source = Path(path).absolute()
    if not source.exists() or _is_reparse(source):
        raise AuthorizedMaterialError("authorized_material_snapshot_invalid")
    if source.is_file():
        digest, size = _file_sha256(source)
        return digest, size, "file"
    if not source.is_dir():
        raise AuthorizedMaterialError("authorized_material_snapshot_kind_unsupported")
    entries: list[dict[str, Any]] = []
    total = 0
    root = source.resolve()
    for child in sorted(source.rglob("*"), key=lambda item: item.relative_to(source).as_posix()):
        if _is_reparse(child):
            raise AuthorizedMaterialError("authorized_material_snapshot_indirection_forbidden")
        try:
            child.resolve().relative_to(root)
        except ValueError as exc:
            raise AuthorizedMaterialError("authorized_material_snapshot_scope_escape") from exc
        relative = child.relative_to(source).as_posix()
        if child.is_dir():
            entries.append({"path": relative, "kind": "directory"})
        elif child.is_file():
            digest, size = _file_sha256(child)
            total += size
            entries.append(
                {
                    "path": relative,
                    "kind": "file",
                    "sha256": digest,
                    "byte_size": size,
                }
            )
        else:
            raise AuthorizedMaterialError("authorized_material_snapshot_kind_unsupported")
    return canonical_sha256({"kind": "directory", "entries": entries}), total, "directory"


@dataclass(frozen=True)
class AuthorizedMaterialSource:
    """Private source binding.  ``source_path`` is never serialized."""

    source_id: str
    origin: Literal["public_input", "committed_dependency", "checkpoint"]
    logical_name: str
    logical_locator: str
    source_path: Path
    expected_sha256: str
    expected_byte_size: int
    expected_kind: Literal["file", "directory"]
    extension: str = ""
    media_type: str = "application/octet-stream"
    descriptor: ArtifactDescriptorV2 | None = None


class AuthorizedModelMaterial(FrozenContract):
    protocol: Literal[AUTHORIZED_MODEL_MATERIAL_PROTOCOL] = (
        AUTHORIZED_MODEL_MATERIAL_PROTOCOL
    )
    source_id: str = Field(min_length=1)
    origin: Literal["public_input", "committed_dependency", "checkpoint"]
    logical_name: str = Field(min_length=1)
    logical_locator: str = Field(min_length=1)
    representation: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    extension: str = ""
    content_sha256: str | None = None
    tree_sha256: str | None = None
    descriptor_sha256: str
    evidence_kind: Literal["full", "bounded", "descriptor_only"]
    coverage_status: Literal["complete", "bounded", "machine_only"]
    byte_size: int = Field(ge=0)
    authorized_content: str = ""
    authorized_content_sha256: str = ""
    authorized_content_bytes: int = Field(default=0, ge=0)
    structure_evidence: Mapping[str, Any] = Field(default_factory=dict)
    material_sha256: str = ""

    @field_validator(
        "content_sha256",
        "tree_sha256",
        "descriptor_sha256",
        "authorized_content_sha256",
    )
    @classmethod
    def _hashes(cls, value: str | None, info: Any) -> str | None:
        if value is None:
            return None
        return _require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _seal(self) -> "AuthorizedModelMaterial":
        content_raw = self.authorized_content.encode("utf-8")
        observed_content_hash = hashlib.sha256(content_raw).hexdigest()
        if self.authorized_content_sha256 and self.authorized_content_sha256 != observed_content_hash:
            raise ValueError("authorized_material_content_sha256_mismatch")
        if self.authorized_content_bytes not in {0, len(content_raw)}:
            raise ValueError("authorized_material_content_size_mismatch")
        if self.evidence_kind == "descriptor_only" and self.authorized_content:
            raise ValueError("descriptor_only_material_contains_content")
        object.__setattr__(self, "authorized_content_sha256", observed_content_hash)
        object.__setattr__(self, "authorized_content_bytes", len(content_raw))
        projection = self.model_dump(
            mode="python",
            exclude={"authorized_content", "material_sha256"},
        )
        expected = canonical_sha256(projection)
        if self.material_sha256 and self.material_sha256 != expected:
            raise ValueError("authorized_material_sha256_mismatch")
        object.__setattr__(self, "material_sha256", expected)
        return self

    def audit_projection(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude={"authorized_content"})


class AuthorizedModelMaterialView(FrozenContract):
    protocol: Literal[AUTHORIZED_MODEL_MATERIAL_PROTOCOL] = (
        AUTHORIZED_MODEL_MATERIAL_PROTOCOL
    )
    run_id: str = Field(min_length=1)
    revision: SubtaskRevisionRef
    materials: tuple[AuthorizedModelMaterial, ...]
    total_material_bytes: int = Field(ge=0)
    source_ids: tuple[str, ...]
    source_provenance_sha256: str
    view_sha256: str = ""

    @field_validator("source_provenance_sha256")
    @classmethod
    def _source_hash(cls, value: str) -> str:
        return _require_sha256(value, field_name="source_provenance_sha256")

    @model_validator(mode="after")
    def _seal(self) -> "AuthorizedModelMaterialView":
        expected_ids = tuple(item.source_id for item in self.materials)
        if self.source_ids != expected_ids or len(expected_ids) != len(set(expected_ids)):
            raise ValueError("authorized_material_source_identity_mismatch")
        observed_size = sum(item.authorized_content_bytes for item in self.materials)
        if self.total_material_bytes != observed_size:
            raise ValueError("authorized_material_total_size_mismatch")
        projection = {
            "protocol": self.protocol,
            "run_id": self.run_id,
            "revision": self.revision.model_dump(mode="json"),
            "material_sha256s": [item.material_sha256 for item in self.materials],
            "total_material_bytes": self.total_material_bytes,
            "source_ids": list(self.source_ids),
            "source_provenance_sha256": self.source_provenance_sha256,
        }
        expected = canonical_sha256(projection)
        if self.view_sha256 and self.view_sha256 != expected:
            raise ValueError("authorized_material_view_sha256_mismatch")
        object.__setattr__(self, "view_sha256", expected)
        return self

    def audit_projection(self) -> dict[str, Any]:
        return {
            "protocol": self.protocol,
            "run_id": self.run_id,
            "revision": self.revision.model_dump(mode="json"),
            "materials": [item.audit_projection() for item in self.materials],
            "total_material_bytes": self.total_material_bytes,
            "source_ids": list(self.source_ids),
            "source_provenance_sha256": self.source_provenance_sha256,
            "view_sha256": self.view_sha256,
        }


def _structure_summary(descriptor: ArtifactDescriptorV2, structure: Mapping[str, Any]) -> dict[str, Any]:
    members = structure.get("members")
    return {
        "representation": descriptor.representation.value,
        "format_id": descriptor.format_id,
        "media_type": descriptor.media_type,
        "byte_size": descriptor.byte_size,
        "machine_check_ids": list(descriptor.machine_check_ids),
        "semantic_evidence_status": descriptor.semantic_evidence_status,
        "structure_sha256": canonical_sha256(dict(structure)),
        "member_count": len(members) if isinstance(members, list) else 0,
        "headings": list(structure.get("headings") or ())[:64],
        "parts": list(structure.get("parts") or ())[:64],
        "pdf_header": structure.get("pdf_header"),
        "page_marker_count": structure.get("page_marker_count"),
    }


def _fair_allocations(lengths: Sequence[int], maximum: int) -> tuple[int, ...]:
    allocations = [0 for _ in lengths]
    active = [index for index, value in enumerate(lengths) if value > 0]
    remaining = max(0, maximum)
    while active and remaining > 0:
        share = max(1, remaining // len(active))
        progressed = False
        next_active: list[int] = []
        for index in active:
            wanted = lengths[index] - allocations[index]
            take = min(wanted, share, remaining)
            if take > 0:
                allocations[index] += take
                remaining -= take
                progressed = True
            if allocations[index] < lengths[index]:
                next_active.append(index)
        if not progressed:
            break
        active = next_active
    return tuple(allocations)


def build_authorized_model_material_view(
    *,
    run_id: str,
    revision: SubtaskRevisionRef,
    sources: Sequence[AuthorizedMaterialSource],
    per_source_max_bytes: int = DEFAULT_PER_SOURCE_MATERIAL_BYTES,
    total_max_bytes: int = DEFAULT_TOTAL_MATERIAL_BYTES,
) -> AuthorizedModelMaterialView:
    if per_source_max_bytes <= 0 or total_max_bytes <= 0:
        raise AuthorizedMaterialError("authorized_material_limit_invalid")
    source_ids = [item.source_id for item in sources]
    if len(source_ids) != len(set(source_ids)):
        raise AuthorizedMaterialError("authorized_material_source_duplicate")

    prepared: list[tuple[AuthorizedMaterialSource, ArtifactDescriptorV2, Any, str]] = []
    for source in sources:
        observed_hash, observed_size, observed_kind = public_snapshot_identity(source.source_path)
        if (
            observed_hash != source.expected_sha256
            or observed_size != source.expected_byte_size
            or observed_kind != source.expected_kind
        ):
            raise AuthorizedMaterialError("authorized_material_source_identity_mismatch")
        descriptor = source.descriptor
        if descriptor is None:
            try:
                descriptor = descriptor_for_path(
                    source.source_path,
                    format_id="",
                    extension=source.extension,
                    logical_locator=source.logical_locator,
                    provenance_source_ids=(source.source_id,),
                )
            except ArtifactV2Error as exc:
                raise AuthorizedMaterialError("authorized_material_descriptor_failed") from exc
        evidence = build_evidence_v2(
            descriptor=descriptor,
            source_path=source.source_path,
            max_bytes=per_source_max_bytes,
        )
        prepared.append((source, descriptor, evidence, evidence.public_content))

    lengths = [len(item[3].encode("utf-8")) for item in prepared]
    allocations = _fair_allocations(lengths, total_max_bytes)
    materials: list[AuthorizedModelMaterial] = []
    for (source, descriptor, evidence, content), allocation in zip(prepared, allocations):
        bounded_content = _utf8_prefix(content, allocation)
        if not bounded_content:
            evidence_kind: Literal["full", "bounded", "descriptor_only"] = "descriptor_only"
        elif evidence.evidence_status == "complete" and len(bounded_content.encode("utf-8")) == len(content.encode("utf-8")):
            evidence_kind = "full"
        else:
            evidence_kind = "bounded"
        coverage_status: Literal["complete", "bounded", "machine_only"] = (
            "complete"
            if evidence_kind == "full"
            else "bounded"
            if evidence_kind == "bounded"
            else "machine_only"
        )
        materials.append(
            AuthorizedModelMaterial(
                source_id=source.source_id,
                origin=source.origin,
                logical_name=source.logical_name,
                logical_locator=source.logical_locator,
                representation=descriptor.representation.value,
                media_type=descriptor.media_type,
                extension=descriptor.extension,
                content_sha256=descriptor.content_sha256,
                tree_sha256=descriptor.tree_sha256,
                descriptor_sha256=descriptor.descriptor_sha256,
                evidence_kind=evidence_kind,
                coverage_status=coverage_status,
                byte_size=descriptor.byte_size,
                authorized_content=bounded_content,
                structure_evidence=_structure_summary(descriptor, evidence.structure),
            )
        )
    provenance_projection = {
        "revision_sha256": subtask_revision_identity_sha256(revision),
        "sources": [
            {
                "source_id": source.source_id,
                "origin": source.origin,
                "expected_sha256": source.expected_sha256,
                "logical_locator": source.logical_locator,
            }
            for source in sources
        ],
    }
    return AuthorizedModelMaterialView(
        run_id=run_id,
        revision=revision,
        materials=tuple(materials),
        total_material_bytes=sum(item.authorized_content_bytes for item in materials),
        source_ids=tuple(source_ids),
        source_provenance_sha256=canonical_sha256(provenance_projection),
    )


__all__ = [
    "AUTHORIZED_MODEL_MATERIAL_PROTOCOL",
    "AuthorizedMaterialError",
    "AuthorizedMaterialSource",
    "AuthorizedModelMaterial",
    "AuthorizedModelMaterialView",
    "DEFAULT_PER_SOURCE_MATERIAL_BYTES",
    "DEFAULT_TOTAL_MATERIAL_BYTES",
    "build_authorized_model_material_view",
    "public_snapshot_identity",
]
