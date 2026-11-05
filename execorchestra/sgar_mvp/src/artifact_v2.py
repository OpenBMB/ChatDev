"""General, byte-preserving artifact contracts and evidence adapters.

The module is deliberately driven by an explicitly declared representation and
format.  It never infers an artifact from a query, Case identifier, resource
name, or historical failure.  Source paths are accepted only at the private
staging boundary and never appear in returned descriptors.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import io
import json
import mimetypes
import os
import re
import stat
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from xml.etree import ElementTree

from .evaluation_contracts import (
    ARTIFACT_EVIDENCE_PROTOCOL_V2,
    ArtifactDescriptorV2,
    ArtifactMemberDescriptorV2,
    ArtifactRepresentation,
    FinalArtifactCandidateV2,
    MachineContractEvidence,
)
from .pipeline_control import canonical_json_bytes, canonical_sha256


class ArtifactV2Error(RuntimeError):
    pass


class ArtifactV2MachineContractError(ArtifactV2Error):
    def __init__(self, failure_code: str) -> None:
        super().__init__(failure_code)
        self.failure_code = failure_code


_TEXT_FORMATS = {
    "markdown",
    "plaintext",
    "text",
    "json",
    "jsonl",
    "csv",
    "html",
    "python",
    "javascript",
    "typescript",
    "java",
    "c",
    "cpp",
    "csharp",
    "go",
    "rust",
    "sql",
    "shell",
    "yaml",
    "xml",
}
_OOXML_EXTENSIONS = {".docx", ".xlsx", ".pptx"}
_CODE_FORMATS = {
    "python",
    "javascript",
    "typescript",
    "java",
    "c",
    "cpp",
    "csharp",
    "go",
    "rust",
    "sql",
    "shell",
}
_EXTENSION_FORMATS = {
    ".md": "markdown",
    ".txt": "plaintext",
    ".json": "json",
    ".jsonl": "jsonl",
    ".ndjson": "jsonl",
    ".csv": "csv",
    ".html": "html",
    ".htm": "html",
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".java": "java",
    ".c": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cs": "csharp",
    ".go": "go",
    ".rs": "rust",
    ".sql": "sql",
    ".sh": "shell",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".xml": "xml",
    ".pdf": "pdf",
    ".tex": "code",
    ".doc": "doc",
    ".docx": "docx",
    ".xls": "xls",
    ".xlsx": "xlsx",
    ".ppt": "ppt",
    ".pptx": "pptx",
}


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _is_reparse(path: Path) -> bool:
    try:
        value = path.lstat()
    except OSError as exc:
        raise ArtifactV2Error("artifact_v2_path_unreadable") from exc
    return bool(stat.S_ISLNK(value.st_mode) or int(getattr(value, "st_file_attributes", 0)) & 0x400)


def assert_safe_source_path(path: str | Path) -> Path:
    source = Path(path).absolute()
    if not source.exists():
        raise ArtifactV2Error("artifact_v2_source_missing")
    chain: list[Path] = []
    cursor = source
    while cursor != cursor.parent:
        chain.append(cursor)
        cursor = cursor.parent
    for component in reversed(chain):
        if component.exists() and _is_reparse(component):
            raise ArtifactV2Error("artifact_v2_reparse_forbidden")
    return source


def normalize_format_id(format_id: str, extension: str = "") -> str:
    value = str(format_id or "").strip().lower().replace("_", "-")
    if value == "ndjson" or (value == "json" and str(extension).lower() in {".jsonl", ".ndjson"}):
        value = "jsonl"
    if not value:
        value = _EXTENSION_FORMATS.get(str(extension or "").lower(), "binary")
    if not re.fullmatch(r"[a-z0-9][a-z0-9.+-]{0,63}", value):
        raise ArtifactV2Error("artifact_v2_format_id_invalid")
    return value


def is_text_format(format_id: str, extension: str = "") -> bool:
    """Whether the registered format can be materialized as UTF-8 text.

    This classifies representation only; content and task correctness remain
    the responsibility of the existing machine contract and evaluator.
    """
    return normalize_format_id(format_id, extension) in _TEXT_FORMATS | {"code"}


def media_type_for(format_id: str, extension: str = "") -> str:
    explicit = {
        "markdown": "text/markdown",
        "plaintext": "text/plain",
        "text": "text/plain",
        "json": "application/json",
        "jsonl": "application/x-ndjson",
        "csv": "text/csv",
        "html": "text/html",
        "python": "text/x-python",
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "directory": "application/vnd.sgar.directory",
        "bundle": "application/vnd.sgar.bundle",
    }.get(format_id)
    if explicit:
        return explicit
    guessed, _ = mimetypes.guess_type("artifact" + str(extension or ""))
    return guessed or ("text/plain" if format_id in _TEXT_FORMATS else "application/octet-stream")


def _strict_utf8(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ArtifactV2MachineContractError("artifact_v2_text_not_utf8") from exc


class _HTMLStructureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.visible: list[str] = []
        self.headings: list[str] = []
        self._heading: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.depth += 1
        if tag.lower() in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._heading = []

    def handle_endtag(self, tag: str) -> None:
        if self.depth <= 0:
            raise ArtifactV2MachineContractError("artifact_html_structure_invalid")
        if self._heading is not None and tag.lower() in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            heading = " ".join("".join(self._heading).split())
            if heading:
                self.headings.append(heading)
            self._heading = None
        self.depth -= 1

    def handle_data(self, data: str) -> None:
        if data:
            self.visible.append(data)
            if self._heading is not None:
                self._heading.append(data)


def _validate_ooxml(content: bytes, extension: str) -> tuple[str, ...]:
    checks = ["zip_structure", "ooxml_content_types"]
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = set(archive.namelist())
            if "[Content_Types].xml" not in names:
                raise ArtifactV2MachineContractError("artifact_ooxml_content_types_missing")
            ElementTree.fromstring(archive.read("[Content_Types].xml"))
            required_root = {
                ".docx": "word/document.xml",
                ".xlsx": "xl/workbook.xml",
                ".pptx": "ppt/presentation.xml",
            }.get(extension.lower())
            if required_root and required_root not in names:
                raise ArtifactV2MachineContractError("artifact_ooxml_primary_part_missing")
            if required_root:
                ElementTree.fromstring(archive.read(required_root))
                checks.append("ooxml_primary_xml")
    except ArtifactV2MachineContractError:
        raise
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
        raise ArtifactV2MachineContractError("artifact_ooxml_invalid") from exc
    return tuple(checks)


def validate_file_machine_contract(
    content: bytes,
    *,
    format_id: str,
    extension: str = "",
) -> tuple[tuple[str, ...], str]:
    """Validate only format-level facts that can be proven deterministically."""

    fmt = normalize_format_id(format_id, extension)
    checks = ["content_hash", "byte_size"]
    semantic_status = "unavailable"
    if fmt in _TEXT_FORMATS:
        text = _strict_utf8(content)
        checks.append("utf8")
        semantic_status = "available"
        if fmt == "jsonl":
            from .model_response_contracts import strict_json_loads
            try:
                for line in text.splitlines():
                    strict_json_loads(line)
            except ValueError as exc:
                raise ArtifactV2MachineContractError("artifact_jsonl_invalid") from exc
            checks.append("jsonl_parse")
        elif fmt == "json":
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                raise ArtifactV2MachineContractError("artifact_json_invalid") from exc
            checks.append("json_parse")
        elif fmt == "csv":
            try:
                rows = list(csv.reader(io.StringIO(text), strict=True))
            except csv.Error as exc:
                raise ArtifactV2MachineContractError("artifact_csv_invalid") from exc
            if not rows:
                raise ArtifactV2MachineContractError("artifact_csv_empty")
            checks.append("csv_parse")
        elif fmt == "html":
            parser = _HTMLStructureParser()
            try:
                parser.feed(text)
                parser.close()
            except (ArtifactV2MachineContractError, Exception) as exc:
                if isinstance(exc, ArtifactV2MachineContractError):
                    raise
                raise ArtifactV2MachineContractError("artifact_html_invalid") from exc
            if parser.depth != 0:
                raise ArtifactV2MachineContractError("artifact_html_structure_invalid")
            checks.append("html_parse")
        elif fmt == "python":
            try:
                ast.parse(text)
            except SyntaxError as exc:
                raise ArtifactV2MachineContractError("artifact_python_invalid") from exc
            checks.append("python_parse")
        elif fmt in _CODE_FORMATS:
            # Other languages are never passed through Python's parser.  UTF-8
            # integrity is the only universal machine contract until a locked,
            # versioned language parser is configured.
            checks.append("declared_language_text")
            semantic_status = "bounded"
    elif fmt in {"docx", "xlsx", "pptx"} or extension.lower() in _OOXML_EXTENSIONS:
        checks.extend(_validate_ooxml(content, extension))
        semantic_status = "bounded"
    elif fmt == "pdf":
        if not content.startswith(b"%PDF-") or b"%%EOF" not in content[-4096:]:
            raise ArtifactV2MachineContractError("artifact_pdf_structure_invalid")
        checks.append("pdf_structure")
        semantic_status = "bounded"
    else:
        checks.append("binary_integrity")
    return tuple(dict.fromkeys(checks)), semantic_status


def _tree_projection(path: Path) -> tuple[list[dict[str, Any]], int]:
    root = path.resolve()
    projection: list[dict[str, Any]] = []
    total = 0
    for child in sorted(path.rglob("*"), key=lambda item: item.relative_to(path).as_posix()):
        assert_safe_source_path(child)
        resolved = child.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ArtifactV2Error("artifact_v2_tree_scope_escape") from exc
        relative = child.relative_to(path).as_posix()
        if child.is_dir():
            projection.append({"relative_path": relative, "kind": "directory"})
            continue
        if not child.is_file():
            raise ArtifactV2Error("artifact_v2_tree_entry_kind_unsupported")
        digest = hashlib.sha256()
        size = 0
        with child.open("rb") as handle:
            while True:
                block = handle.read(1024 * 1024)
                if not block:
                    break
                digest.update(block)
                size += len(block)
        projection.append(
            {
                "relative_path": relative,
                "kind": "file",
                "content_sha256": digest.hexdigest(),
                "byte_size": size,
            }
        )
        total += size
    return projection, total


def tree_identity(path: str | Path) -> tuple[str, tuple[ArtifactMemberDescriptorV2, ...], int]:
    root = assert_safe_source_path(path)
    if not root.is_dir():
        raise ArtifactV2Error("artifact_v2_directory_expected")
    projection, total = _tree_projection(root)
    tree_sha = canonical_sha256(projection)
    members: list[ArtifactMemberDescriptorV2] = []
    for item in projection:
        relative = str(item["relative_path"])
        if item["kind"] == "directory":
            nested_projection = [
                candidate
                for candidate in projection
                if candidate["relative_path"] == relative
                or str(candidate["relative_path"]).startswith(relative + "/")
            ]
            members.append(
                ArtifactMemberDescriptorV2(
                    logical_locator=f"artifact://member/{relative}",
                    relative_path=relative,
                    representation="directory",
                    format_id="directory",
                    media_type="application/vnd.sgar.directory",
                    tree_sha256=canonical_sha256(nested_projection),
                    byte_size=sum(int(x.get("byte_size") or 0) for x in nested_projection),
                )
            )
        else:
            extension = Path(relative).suffix.lower()
            fmt = normalize_format_id("", extension)
            members.append(
                ArtifactMemberDescriptorV2(
                    logical_locator=f"artifact://member/{relative}",
                    relative_path=relative,
                    representation="file",
                    format_id=fmt,
                    media_type=media_type_for(fmt, extension),
                    extension=extension,
                    content_sha256=str(item["content_sha256"]),
                    byte_size=int(item["byte_size"]),
                )
            )
    return tree_sha, tuple(members), total


def descriptor_for_bytes(
    content: bytes,
    *,
    representation: ArtifactRepresentation = ArtifactRepresentation.INLINE_TEXT,
    format_id: str,
    extension: str,
    logical_locator: str,
    provenance_source_ids: Sequence[str],
) -> ArtifactDescriptorV2:
    if representation not in {ArtifactRepresentation.INLINE_TEXT, ArtifactRepresentation.FILE}:
        raise ArtifactV2Error("artifact_v2_byte_representation_invalid")
    fmt = normalize_format_id(format_id, extension)
    checks, semantic_status = validate_file_machine_contract(
        content, format_id=fmt, extension=extension
    )
    return ArtifactDescriptorV2(
        representation=representation,
        format_id=fmt,
        media_type=media_type_for(fmt, extension),
        extension=extension,
        content_sha256=sha256_bytes(content),
        byte_size=len(content),
        logical_locator=logical_locator,
        provenance_source_ids=tuple(provenance_source_ids),
        contract_status="pass",
        machine_check_ids=checks,
        semantic_evidence_status=semantic_status,
    )


def descriptor_for_path(
    source_path: str | Path,
    *,
    format_id: str,
    extension: str,
    logical_locator: str,
    provenance_source_ids: Sequence[str],
    as_bundle: bool = False,
    primary_member: str | None = None,
    required_members: Iterable[str] = (),
) -> ArtifactDescriptorV2:
    path = assert_safe_source_path(source_path)
    if path.is_file():
        return descriptor_for_bytes(
            path.read_bytes(),
            representation=ArtifactRepresentation.FILE,
            format_id=format_id,
            extension=extension or path.suffix.lower(),
            logical_locator=logical_locator,
            provenance_source_ids=provenance_source_ids,
        )
    if not path.is_dir():
        raise ArtifactV2Error("artifact_v2_path_kind_invalid")
    tree_sha, members, total = tree_identity(path)
    required = {str(item).replace("\\", "/") for item in required_members}
    member_paths = {item.relative_path for item in members}
    missing = sorted(required - member_paths)
    if missing:
        raise ArtifactV2MachineContractError("artifact_bundle_required_member_missing")
    adjusted = tuple(
        ArtifactMemberDescriptorV2.model_validate(
            {
                **item.model_dump(mode="python", exclude={"member_sha256"}),
                "required": item.relative_path in required or not required,
            }
        )
        for item in members
    )
    representation = ArtifactRepresentation.BUNDLE if as_bundle else ArtifactRepresentation.DIRECTORY
    return ArtifactDescriptorV2(
        representation=representation,
        format_id="bundle" if as_bundle else "directory",
        media_type=media_type_for("bundle" if as_bundle else "directory"),
        extension=extension,
        tree_sha256=tree_sha,
        bundle_sha256=(
            canonical_sha256(
                {
                    "tree_sha256": tree_sha,
                    "primary_member": primary_member,
                    "members": [item.model_dump(mode="json") for item in adjusted],
                }
            )
            if as_bundle
            else None
        ),
        byte_size=total,
        logical_locator=logical_locator,
        primary_member=primary_member,
        members=adjusted,
        provenance_source_ids=tuple(provenance_source_ids),
        contract_status="pass",
        machine_check_ids=(
            "bundle_tree_hash",
            "required_members",
            "member_hashes",
        )
        if as_bundle
        else ("directory_tree_hash", "member_hashes"),
        semantic_evidence_status="bounded" if members else "unavailable",
    )


def machine_evidence_for_descriptor(descriptor: ArtifactDescriptorV2) -> MachineContractEvidence:
    return MachineContractEvidence(
        status="pass" if descriptor.contract_status == "pass" else "fail",
        check_ids=descriptor.machine_check_ids,
        evidence_ids=tuple(f"machine:{item}" for item in descriptor.machine_check_ids),
    )


def build_candidate_v2(
    *,
    artifact_revision: Any,
    descriptor: ArtifactDescriptorV2,
    execution_result_sha256: str,
    output_contract_sha256: str,
    candidate_pool_sha256: str,
    plan_sha256: str | None,
    recovery_operation_sha256: str | None,
    execution_event_ids: Sequence[str] = (),
    source_handle_ids: Sequence[str] = (),
) -> FinalArtifactCandidateV2:
    return FinalArtifactCandidateV2(
        artifact_revision=artifact_revision,
        execution_result_sha256=execution_result_sha256,
        descriptor=descriptor,
        output_contract_sha256=output_contract_sha256,
        candidate_pool_sha256=candidate_pool_sha256,
        plan_sha256=plan_sha256,
        recovery_operation_sha256=recovery_operation_sha256,
        execution_event_ids=tuple(execution_event_ids),
        source_handle_ids=tuple(source_handle_ids),
    )


@dataclass(frozen=True)
class ArtifactEvidenceV2:
    protocol: str
    descriptor_sha256: str
    evidence_status: str
    public_content: str
    evidence_sha256: str
    machine_evidence_ids: tuple[str, ...]
    structure: Mapping[str, Any]


def _bounded_text(text: str, max_bytes: int) -> tuple[str, bool]:
    raw = text.encode("utf-8")
    if len(raw) <= max_bytes:
        return text, True
    bounded = raw[:max_bytes]
    while bounded:
        try:
            return bounded.decode("utf-8", errors="strict"), False
        except UnicodeDecodeError as exc:
            if exc.end != len(bounded):
                raise
            bounded = bounded[: exc.start]
    return "", False


def _ooxml_text(content: bytes, format_id: str) -> tuple[str, Mapping[str, Any]]:
    text_parts: list[str] = []
    structure: dict[str, Any] = {"parts": []}
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        prefixes = {
            "docx": ("word/document.xml",),
            "xlsx": ("xl/sharedStrings.xml", "xl/workbook.xml"),
            "pptx": tuple(
                sorted(name for name in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name))
            ),
        }.get(format_id, ())
        for name in prefixes:
            if name not in archive.namelist():
                continue
            root = ElementTree.fromstring(archive.read(name))
            values = [item.text for item in root.iter() if item.text and item.text.strip()]
            text_parts.extend(values)
            structure["parts"].append({"locator": name, "text_nodes": len(values)})
    return "\n".join(text_parts), structure


def build_evidence_v2(
    *,
    descriptor: ArtifactDescriptorV2,
    content: bytes | None = None,
    source_path: str | Path | None = None,
    max_bytes: int = 65536,
) -> ArtifactEvidenceV2:
    """Build stable evidence from format and structure, never task keywords."""

    structure: dict[str, Any] = {
        "representation": descriptor.representation.value,
        "format_id": descriptor.format_id,
        "media_type": descriptor.media_type,
        "byte_size": descriptor.byte_size,
    }
    public_content = ""
    complete = False
    if descriptor.representation in {ArtifactRepresentation.INLINE_TEXT, ArtifactRepresentation.FILE}:
        if content is None and source_path is not None:
            content = assert_safe_source_path(source_path).read_bytes()
        if content is None:
            raise ArtifactV2Error("artifact_v2_evidence_content_missing")
        if sha256_bytes(content) != descriptor.content_sha256:
            raise ArtifactV2Error("artifact_v2_evidence_hash_mismatch")
        if descriptor.format_id in _TEXT_FORMATS:
            text = _strict_utf8(content)
            if descriptor.format_id == "html":
                parser = _HTMLStructureParser()
                parser.feed(text)
                parser.close()
                public_content = "\n".join(
                    part for part in (" ".join("".join(parser.visible).split()), *parser.headings) if part
                )
                structure["headings"] = parser.headings
            else:
                public_content = text
            public_content, complete = _bounded_text(public_content, max_bytes)
        elif descriptor.format_id in {"docx", "xlsx", "pptx"}:
            extracted, ooxml_structure = _ooxml_text(content, descriptor.format_id)
            structure.update(ooxml_structure)
            public_content, complete = _bounded_text(extracted, max_bytes)
        elif descriptor.format_id == "pdf":
            structure["pdf_header"] = content[:8].decode("ascii", errors="replace")
            structure["page_marker_count"] = content.count(b"/Type /Page")
    else:
        structure["members"] = [
            {
                "relative_path": item.relative_path,
                "representation": item.representation,
                "format_id": item.format_id,
                "media_type": item.media_type,
                "byte_size": item.byte_size,
                "content_sha256": item.content_sha256,
                "tree_sha256": item.tree_sha256,
                "required": item.required,
            }
            for item in descriptor.members
        ]
        encoded = json.dumps(structure, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        public_content, complete = _bounded_text(encoded, max_bytes)
    evidence_status = (
        "complete"
        if complete and descriptor.semantic_evidence_status == "available"
        else "bounded"
        if public_content
        else "machine_only"
    )
    identity = {
        "protocol": ARTIFACT_EVIDENCE_PROTOCOL_V2,
        "descriptor_sha256": descriptor.descriptor_sha256,
        "evidence_status": evidence_status,
        "public_content_sha256": sha256_bytes(public_content.encode("utf-8")),
        "structure": structure,
        "machine_evidence_ids": [f"machine:{item}" for item in descriptor.machine_check_ids],
    }
    return ArtifactEvidenceV2(
        protocol=ARTIFACT_EVIDENCE_PROTOCOL_V2,
        descriptor_sha256=descriptor.descriptor_sha256,
        evidence_status=evidence_status,
        public_content=public_content,
        evidence_sha256=canonical_sha256(identity),
        machine_evidence_ids=tuple(identity["machine_evidence_ids"]),
        structure=structure,
    )


__all__ = [
    "ArtifactEvidenceV2",
    "ArtifactV2Error",
    "ArtifactV2MachineContractError",
    "assert_safe_source_path",
    "build_candidate_v2",
    "build_evidence_v2",
    "descriptor_for_bytes",
    "descriptor_for_path",
    "machine_evidence_for_descriptor",
    "media_type_for",
    "normalize_format_id",
    "sha256_bytes",
    "tree_identity",
    "validate_file_machine_contract",
]
