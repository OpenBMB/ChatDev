"""Explicit, immutable production task input and snapshot contracts.

The public protocol never contains a host path.  Host paths are retained only
inside :class:`PreparedTaskInvocation` so the sandbox can mount the immutable
snapshot created before any paid model call.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import posixpath
import shutil
import stat
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping, Sequence

from pydantic import Field, field_validator, model_serializer, model_validator

from .atomic_io import temporary_sibling_path
from .execution_contracts import infer_artifact_type_from_path
from .input_discovery import observe_container_inventory
from .pipeline_control import FrozenContract, canonical_json_bytes, canonical_sha256


TASK_INVOCATION_PROTOCOL = "sgar-task-invocation-v1"
PUBLIC_INPUT_SNAPSHOT_PROTOCOL = "sgar-public-input-snapshot-v1"
DEFAULT_INLINE_TEXT_MAX_BYTES = 64 * 1024
FINAL_DELIVERABLE_CONTRACT_PROTOCOL = "sgar-final-deliverable-contract-v1"
_DIRECTORY_PROMOTION_ATTEMPTS = 6
_DIRECTORY_PROMOTION_BASE_DELAY_SECONDS = 0.025
_TRANSIENT_WINDOWS_PROMOTION_ERRORS = frozenset({5, 32, 33})


class TaskInvocationError(ValueError):
    """Raised before paid work when a production invocation is invalid."""


class InputSnapshotPolicy(FrozenContract):
    protocol: Literal[PUBLIC_INPUT_SNAPSHOT_PROTOCOL] = PUBLIC_INPUT_SNAPSHOT_PROTOCOL
    inline_text_max_bytes: int = Field(
        default=DEFAULT_INLINE_TEXT_MAX_BYTES,
        ge=0,
    )
    # Explicit callers may impose an input budget.  By default, preserve the
    # complete authorized material and let filesystem/benchmark limits apply.
    single_file_max_bytes: int | None = Field(default=None, ge=1)
    request_total_max_bytes: int | None = Field(default=None, ge=1)
    directory_max_entries: int | None = Field(default=None, ge=1)


class FinalDeliverableContract(FrozenContract):
    """Explicit, representation-oriented final publication contract.

    This contract is deliberately independent from the current Planner's
    five-value semantic artifact enum.  It is the stable compatibility surface
    that a future Resource-Aware Planner can consume directly.
    """

    protocol: Literal[FINAL_DELIVERABLE_CONTRACT_PROTOCOL] = (
        FINAL_DELIVERABLE_CONTRACT_PROTOCOL
    )
    representation: Literal["inline_text", "file", "directory", "bundle"]
    format_id: str = Field(min_length=1)
    media_type: str | None = None
    extension: str = ""
    logical_name: str | None = None
    runtime_path: str | None = None
    primary_member: str | None = None
    required_members: tuple[str, ...] = ()
    contract_sha256: str = ""

    @model_serializer(mode="wrap")
    def _serialize_optional_runtime_path(self, handler):
        payload = handler(self)
        if self.runtime_path is None:
            payload.pop("runtime_path", None)
        return payload

    @field_validator("runtime_path")
    @classmethod
    def _validate_delivery_runtime_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if (
            not value.startswith("/")
            or posixpath.normpath(value) != value
            or "\\" in value
            or "\x00" in value
        ):
            raise ValueError("final_deliverable_runtime_path_invalid")
        return value

    @model_validator(mode="before")
    @classmethod
    def _normalize_compatibility_shape(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        payload = dict(value)
        if "representation" not in payload:
            artifact_type = str(
                payload.get("artifact_type") or payload.get("format_id") or "plaintext"
            ).strip().lower()
            payload["representation"] = (
                artifact_type if artifact_type in {"directory", "bundle"} else "file"
            )
        if "format_id" not in payload:
            payload["format_id"] = str(
                payload.pop("artifact_type", None) or payload.pop("format", None) or "binary"
            )
        if "extension" not in payload and "output_extension" in payload:
            payload["extension"] = payload.pop("output_extension")
        if "primary_member" not in payload and "primary_artifact" in payload:
            payload["primary_member"] = payload.pop("primary_artifact")
        if "required_members" not in payload and "side_artifacts" in payload:
            raw_members = payload.pop("side_artifacts")
            if isinstance(raw_members, Sequence) and not isinstance(raw_members, (str, bytes)):
                payload["required_members"] = [
                    str(item.get("path") or item.get("logical_name") or "")
                    if isinstance(item, Mapping)
                    else str(item)
                    for item in raw_members
                ]
        return payload

    @field_validator("format_id")
    @classmethod
    def _validate_format_id(cls, value: str) -> str:
        normalized = value.strip().lower().replace("_", "-")
        if not normalized or not all(
            char.isascii() and (char.isalnum() or char in ".+-")
            for char in normalized
        ):
            raise ValueError("final_deliverable_format_id_invalid")
        return normalized

    @field_validator("extension")
    @classmethod
    def _validate_extension(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized and (
            not normalized.startswith(".")
            or any(char in normalized for char in ("/", "\\", "\x00"))
        ):
            raise ValueError("final_deliverable_extension_invalid")
        return normalized

    @field_validator("primary_member")
    @classmethod
    def _validate_primary_member(cls, value: str | None) -> str | None:
        return None if value is None else cls._validate_member_path(value)

    @field_validator("logical_name")
    @classmethod
    def _validate_logical_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        if (
            not normalized
            or normalized in {".", ".."}
            or len(normalized) > 255
            or any(char in normalized for char in ("/", "\\", "\x00"))
            or (len(normalized) >= 2 and normalized[1] == ":")
        ):
            raise ValueError("final_deliverable_logical_name_invalid")
        return normalized

    @field_validator("required_members")
    @classmethod
    def _validate_required_members(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(cls._validate_member_path(value) for value in values)
        if len(normalized) != len(set(normalized)):
            raise ValueError("final_deliverable_required_member_duplicate")
        return normalized

    @staticmethod
    def _validate_member_path(value: str) -> str:
        normalized = str(value).replace("\\", "/").strip()
        parts = normalized.split("/")
        if (
            not normalized
            or normalized.startswith("/")
            or len(normalized) > 512
            or any(part in {"", ".", ".."} for part in parts)
            or (len(normalized) >= 2 and normalized[1] == ":")
            or "\x00" in normalized
        ):
            raise ValueError("final_deliverable_member_path_invalid")
        return normalized

    @model_validator(mode="after")
    def _seal(self) -> "FinalDeliverableContract":
        if self.runtime_path is not None and self.representation not in {"file", "directory"}:
            raise ValueError("final_deliverable_runtime_path_requires_single_artifact")
        if self.representation not in {"directory", "bundle"} and (
            self.primary_member is not None or self.required_members
        ):
            raise ValueError("final_deliverable_members_require_tree_representation")
        if self.representation == "bundle" and self.primary_member is not None:
            if self.required_members and self.primary_member not in self.required_members:
                raise ValueError("final_deliverable_primary_member_not_required")
        if (
            self.logical_name is not None
            and self.representation in {"inline_text", "file"}
            and self.extension
            and not self.logical_name.lower().endswith(self.extension)
        ):
            raise ValueError("final_deliverable_logical_name_extension_mismatch")
        projection = self.model_dump(mode="python", exclude={"contract_sha256"})
        expected = canonical_sha256(projection)
        if self.contract_sha256 and self.contract_sha256 != expected:
            raise ValueError("final_deliverable_contract_sha256_mismatch")
        object.__setattr__(self, "contract_sha256", expected)
        return self


class PublicInputDescriptor(FrozenContract):
    protocol: Literal[PUBLIC_INPUT_SNAPSHOT_PROTOCOL] = PUBLIC_INPUT_SNAPSHOT_PROTOCOL
    logical_name: str = Field(min_length=1)
    handle_id: str = Field(min_length=1)
    runtime_path: str = Field(min_length=1)
    path_kind: Literal["file", "directory"]
    source_name: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    extension: str = ""
    content_sha256: str
    byte_size: int = Field(ge=0)
    entry_count: int = Field(default=0, ge=0)
    inline_text: str | None = None
    content_available_as_context: bool = False
    tree_manifest_sha256: str | None = None
    execution_contract: dict[str, Any] = Field(default_factory=dict)

    @model_serializer(mode="wrap")
    def _serialize_execution_contract(self, handler):
        payload = handler(self)
        if not self.execution_contract:
            payload.pop("execution_contract", None)
        return payload

    @field_validator("logical_name")
    @classmethod
    def _validate_logical_name(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("public_input_logical_name_empty")
        if value in {".", ".."} or any(char in value for char in ("/", "\\", "\x00")):
            raise ValueError("public_input_logical_name_invalid")
        return value

    @field_validator("runtime_path")
    @classmethod
    def _validate_runtime_path(cls, value: str) -> str:
        text = str(value or "")
        normalized = posixpath.normpath(text)
        if (
            "\\" in text
            or normalized != text.rstrip("/")
            or not normalized.startswith("/app/inputs/")
        ):
            raise ValueError("public_input_runtime_path_invalid")
        return normalized

    @field_validator("content_sha256", "tree_manifest_sha256")
    @classmethod
    def _validate_hash(cls, value: str | None, info: Any) -> str | None:
        if value is None:
            return None
        normalized = value.lower()
        if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
            raise ValueError(f"{info.field_name}_invalid")
        return normalized

    @model_validator(mode="after")
    def _validate_shape(self) -> "PublicInputDescriptor":
        if self.path_kind == "directory":
            if self.inline_text is not None or self.content_available_as_context:
                raise ValueError("directory_input_cannot_be_inlined")
            if not self.tree_manifest_sha256:
                raise ValueError("directory_input_tree_hash_missing")
        elif self.entry_count != 0 or self.tree_manifest_sha256 is not None:
            raise ValueError("file_input_cannot_have_tree_metadata")
        if self.content_available_as_context != (self.inline_text is not None):
            raise ValueError("inline_content_availability_mismatch")
        return self

    def planner_view(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        return payload


class TaskInvocation(FrozenContract):
    protocol: Literal[TASK_INVOCATION_PROTOCOL] = TASK_INVOCATION_PROTOCOL
    request_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    public_inputs: tuple[PublicInputDescriptor, ...] = ()
    final_deliverable_contract: FinalDeliverableContract | None = None
    public_context_descriptors: tuple[Mapping[str, Any], ...] = ()
    input_snapshot_sha256: str
    invocation_sha256: str

    @field_validator("request_id")
    @classmethod
    def _validate_request_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("request_id_empty")
        return normalized

    @field_validator("input_snapshot_sha256", "invocation_sha256")
    @classmethod
    def _validate_sha(cls, value: str, info: Any) -> str:
        normalized = value.lower()
        if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
            raise ValueError(f"{info.field_name}_invalid")
        return normalized

    @model_validator(mode="after")
    def _validate_identity(self) -> "TaskInvocation":
        logical_names = [item.logical_name for item in self.public_inputs]
        if len(logical_names) != len(set(logical_names)):
            raise ValueError("public_input_logical_name_duplicate")
        projection = self.model_dump(mode="python", exclude={"invocation_sha256"})
        if canonical_sha256(projection) != self.invocation_sha256:
            raise ValueError("task_invocation_sha256_mismatch")
        return self

    def planner_request_text(self) -> str:
        """Return a host-free compatibility request for the current Planner.

        The exact user query remains an immutable field.  The appended block is
        a protocol adapter, not inferred text and not a source of new inputs.
        """

        if (
            not self.public_inputs
            and not self.public_context_descriptors
            and self.final_deliverable_contract is None
        ):
            return self.query
        public_block = {
            "protocol": self.protocol,
            "public_inputs": [item.planner_view() for item in self.public_inputs],
            "public_context_descriptors": [dict(item) for item in self.public_context_descriptors],
            "final_deliverable_contract": (
                self.final_deliverable_contract.model_dump(mode="json")
                if self.final_deliverable_contract is not None
                else None
            ),
        }
        return (
            self.query
            + "\n\n[SGAR_PUBLIC_INVOCATION]\n"
            + canonical_json_bytes(public_block).decode("utf-8")
        )


@dataclass(frozen=True)
class InputSourceSpec:
    logical_name: str
    source_path: Path
    execution_contract: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class ResolvedTaskRequest:
    """Single private request projection shared by every formal entry point."""

    exact_query: str
    request_id: str
    input_specs: tuple[InputSourceSpec, ...]
    public_context_descriptors: tuple[dict[str, Any], ...]
    final_deliverable_contract: dict[str, Any] | None
    request_source_sha256: str
    allowed_public_input_roots: tuple[Path, ...] = ()


@dataclass(frozen=True)
class PreparedTaskInvocation:
    invocation: TaskInvocation
    snapshot_paths_by_handle: Mapping[str, Path]
    snapshot_manifest_path: Path

    def internal_handles(self) -> tuple[dict[str, Any], ...]:
        handles: list[dict[str, Any]] = []
        for descriptor in self.invocation.public_inputs:
            snapshot_path = self.snapshot_paths_by_handle.get(descriptor.handle_id)
            if snapshot_path is None:
                raise TaskInvocationError("public_input_snapshot_handle_missing")
            if not snapshot_path.exists():
                raise TaskInvocationError("public_input_snapshot_target_missing")

            expected_is_directory = descriptor.path_kind == "directory"
            if snapshot_path.is_dir() != expected_is_directory:
                raise TaskInvocationError("public_input_snapshot_path_kind_mismatch")

            descriptor_extension = str(descriptor.extension or "").lower()
            if descriptor_extension and not descriptor_extension.startswith("."):
                raise TaskInvocationError(
                    "public_input_snapshot_extension_identity_mismatch"
                )
            runtime_extension = posixpath.splitext(descriptor.runtime_path)[1].lower()
            source_extension = posixpath.splitext(descriptor.source_name)[1].lower()
            # A final dot is part of a legal filename, not a file extension.
            # Path.suffix and the snapshot descriptor both represent it as
            # extensionless; preserve that identity across POSIX paths.
            runtime_extension = "" if runtime_extension == "." else runtime_extension
            source_extension = "" if source_extension == "." else source_extension
            if expected_is_directory:
                if descriptor_extension:
                    raise TaskInvocationError(
                        "public_input_snapshot_extension_identity_mismatch"
                    )
                artifact_type = "directory"
            else:
                if not snapshot_path.is_file():
                    raise TaskInvocationError(
                        "public_input_snapshot_path_kind_mismatch"
                    )
                if not (
                    descriptor_extension == runtime_extension == source_extension
                ):
                    raise TaskInvocationError(
                        "public_input_snapshot_extension_identity_mismatch"
                    )
                artifact_type = infer_artifact_type_from_path(
                    descriptor.runtime_path,
                    default="file",
                )
            handles.append(
                {
                    "handle_id": descriptor.handle_id,
                    "kind": (
                        "input_directory"
                        if descriptor.path_kind == "directory"
                        else "input_file"
                    ),
                    "producer_task": None,
                    "producer_step": None,
                    "logical_name": descriptor.logical_name,
                    "logical_path": descriptor.runtime_path.removeprefix("/app/"),
                    "host_path": str(snapshot_path),
                    "tool_path": descriptor.runtime_path,
                    "artifact_type": artifact_type,
                    "validation_status": "public_input_snapshot_verified",
                    "current_run": True,
                    "path_kind": descriptor.path_kind,
                    "extension": descriptor_extension,
                    "exists": True,
                    "provenance": (
                        {"execution_contract": dict(descriptor.execution_contract)}
                        if descriptor.execution_contract
                        else {}
                    ),
                }
            )
        return tuple(handles)


def _hash_snapshot_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _inspect_snapshot_directory(
    root: Path,
) -> tuple[str, int, tuple[dict[str, Any], ...]]:
    entries: list[dict[str, Any]] = []
    total_size = 0

    def walk(current: Path, prefix: Path) -> None:
        nonlocal total_size
        with os.scandir(current) as iterator:
            children = sorted(list(iterator), key=lambda item: item.name)
        for child in children:
            child_path = Path(child.path)
            relative = (prefix / child.name).as_posix()
            if child.is_symlink() or _is_reparse_point(child_path):
                raise TaskInvocationError("public_input_snapshot_indirection_forbidden")
            if child.is_dir(follow_symlinks=False):
                entries.append({"path": relative, "kind": "directory"})
                walk(child_path, prefix / child.name)
            elif child.is_file(follow_symlinks=False):
                digest, size = _hash_snapshot_file(child_path)
                total_size += size
                entries.append(
                    {
                        "path": relative,
                        "kind": "file",
                        "sha256": digest,
                        "byte_size": size,
                    }
                )
            else:
                raise TaskInvocationError("public_input_snapshot_special_entry_forbidden")

    walk(root, Path())
    entries.sort(key=lambda item: str(item["path"]))
    tree_hash = canonical_sha256({"kind": "directory", "entries": entries})
    return tree_hash, total_size, tuple(entries)


def verify_prepared_task_invocation(
    prepared: PreparedTaskInvocation,
) -> dict[str, Any]:
    """Recompute the immutable public-input snapshot without using source paths."""

    try:
        manifest_path = _assert_source_chain_is_direct(
            prepared.snapshot_manifest_path
        )
    except (TaskInvocationError, OSError) as exc:
        raise TaskInvocationError(
            "public_input_snapshot_manifest_indirection_forbidden"
        ) from exc
    input_root = manifest_path.parent
    if manifest_path.name != "input_snapshot.json" or input_root.name != "inputs":
        raise TaskInvocationError("public_input_snapshot_layout_invalid")
    try:
        manifest_payload = json.loads(
            prepared.snapshot_manifest_path.read_text(
                encoding="utf-8-sig", errors="strict"
            )
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TaskInvocationError("public_input_snapshot_manifest_invalid") from exc
    if not isinstance(manifest_payload, Mapping):
        raise TaskInvocationError("public_input_snapshot_manifest_root_invalid")
    snapshot_hash = manifest_payload.get("snapshot_sha256")
    projection = dict(manifest_payload)
    projection.pop("snapshot_sha256", None)
    if canonical_sha256(projection) != snapshot_hash:
        raise TaskInvocationError("public_input_snapshot_manifest_hash_mismatch")
    if snapshot_hash != prepared.invocation.input_snapshot_sha256:
        raise TaskInvocationError("public_input_snapshot_identity_mismatch")

    records = manifest_payload.get("inputs")
    if not isinstance(records, list) or len(records) != len(
        prepared.invocation.public_inputs
    ):
        raise TaskInvocationError("public_input_snapshot_record_count_mismatch")
    record_by_handle: dict[str, Mapping[str, Any]] = {}
    for record in records:
        if not isinstance(record, Mapping) or not isinstance(
            record.get("descriptor"), Mapping
        ):
            raise TaskInvocationError("public_input_snapshot_record_invalid")
        descriptor_payload = record["descriptor"]
        handle_id = str(descriptor_payload.get("handle_id") or "")
        if not handle_id or handle_id in record_by_handle:
            raise TaskInvocationError("public_input_snapshot_handle_invalid")
        record_by_handle[handle_id] = record

    verified_bytes = 0
    for descriptor in prepared.invocation.public_inputs:
        snapshot_path = prepared.snapshot_paths_by_handle.get(descriptor.handle_id)
        record = record_by_handle.get(descriptor.handle_id)
        if snapshot_path is None or record is None:
            raise TaskInvocationError("public_input_snapshot_handle_missing")
        try:
            direct_snapshot = _assert_source_chain_is_direct(snapshot_path)
            relative_snapshot = direct_snapshot.relative_to(input_root)
        except (TaskInvocationError, OSError) as exc:
            raise TaskInvocationError(
                "public_input_snapshot_indirection_forbidden"
            ) from exc
        except ValueError as exc:
            raise TaskInvocationError("public_input_snapshot_outside_input_root") from exc
        if not relative_snapshot.parts or relative_snapshot.parts[0] not in {
            "blobs",
            "trees",
        }:
            raise TaskInvocationError("public_input_snapshot_layout_invalid")
        if dict(record["descriptor"]) != descriptor.model_dump(mode="json"):
            raise TaskInvocationError("public_input_snapshot_descriptor_mismatch")
        if descriptor.path_kind == "file":
            if not direct_snapshot.is_file():
                raise TaskInvocationError("public_input_snapshot_kind_mismatch")
            digest, size = _hash_snapshot_file(direct_snapshot)
            tree_entries: tuple[dict[str, Any], ...] = ()
        else:
            if not direct_snapshot.is_dir():
                raise TaskInvocationError("public_input_snapshot_kind_mismatch")
            digest, size, tree_entries = _inspect_snapshot_directory(direct_snapshot)
            if list(tree_entries) != list(record.get("tree_entries") or []):
                raise TaskInvocationError("public_input_snapshot_tree_mismatch")
        if digest != descriptor.content_sha256 or size != descriptor.byte_size:
            raise TaskInvocationError("public_input_snapshot_content_mismatch")
        verified_bytes += size
    if verified_bytes != int(manifest_payload.get("total_byte_size", -1)):
        raise TaskInvocationError("public_input_snapshot_total_size_mismatch")
    return {
        "protocol": PUBLIC_INPUT_SNAPSHOT_PROTOCOL,
        "valid": True,
        "input_count": len(prepared.invocation.public_inputs),
        "total_byte_size": verified_bytes,
        "snapshot_sha256": prepared.invocation.input_snapshot_sha256,
    }


def _is_reparse_point(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    if callable(is_junction):
        try:
            if is_junction():
                return True
        except OSError:
            return True
    try:
        attributes = getattr(os.lstat(path), "st_file_attributes", 0)
    except OSError:
        return True
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _reject_link(path: Path, *, code: str) -> None:
    if path.is_symlink() or os.path.islink(path) or _is_reparse_point(path):
        raise TaskInvocationError(code)


def _assert_source_chain_is_direct(path: Path) -> Path:
    if not os.path.lexists(path):
        raise TaskInvocationError("public_input_source_missing")
    absolute = path.absolute()
    chain = list(reversed(absolute.parents)) + [absolute]
    for item in chain:
        if not os.path.lexists(item):
            continue
        _reject_link(item, code="public_input_source_indirection_forbidden")
    resolved = absolute.resolve(strict=True)
    if not resolved.is_file() and not resolved.is_dir():
        raise TaskInvocationError("public_input_source_kind_unsupported")
    return resolved


def _path_contains(root: Path, candidate: Path) -> bool:
    try:
        common = os.path.commonpath((str(root), str(candidate)))
    except ValueError:
        return False
    return os.path.normcase(os.path.normpath(common)) == os.path.normcase(
        os.path.normpath(str(root))
    )


def _paths_overlap(first: Path, second: Path) -> bool:
    return _path_contains(first, second) or _path_contains(second, first)


def normalize_public_input_roots(
    roots: Sequence[str | Path],
    *,
    project_root: Path | None = None,
    run_dir: Path | None = None,
) -> tuple[Path, ...]:
    """Validate operator-authorized, read-only roots for file-backed ingress."""

    normalized: list[Path] = []
    for raw in roots:
        root = _assert_source_chain_is_direct(Path(raw))
        if not root.is_dir():
            raise TaskInvocationError("public_input_root_not_directory")
        anchor = Path(root.anchor).resolve(strict=True)
        if os.path.normcase(str(root)) == os.path.normcase(str(anchor)):
            raise TaskInvocationError("public_input_root_filesystem_root_forbidden")
        if any(_paths_overlap(root, existing) for existing in normalized):
            raise TaskInvocationError("public_input_roots_overlap")
        normalized.append(root)

    if project_root is not None:
        project = Path(project_root).resolve(strict=True)
        protected = (
            project / ".git",
            project / ".codex",
            project / ".agents",
            project / "sgar_mvp",
            project / "Pool" / "resources" / "tools",
        )
        for root in normalized:
            if os.path.normcase(str(root)) == os.path.normcase(str(project)):
                raise TaskInvocationError("public_input_root_project_root_forbidden")
            if any(
                os.path.lexists(item) and _paths_overlap(root, item.resolve(strict=False))
                for item in protected
            ):
                raise TaskInvocationError("public_input_root_protected_overlap")

    if run_dir is not None:
        run = Path(run_dir).resolve(strict=False)
        if any(_paths_overlap(root, run) for root in normalized):
            raise TaskInvocationError("public_input_root_run_workspace_overlap")
    return tuple(normalized)


def _authorize_file_backed_input(
    path: Path,
    *,
    allowed_roots: Sequence[Path],
) -> Path:
    if not allowed_roots:
        raise TaskInvocationError("public_input_root_required")
    source = _assert_source_chain_is_direct(Path(path))
    matches = [root for root in allowed_roots if _path_contains(root, source)]
    if not matches:
        raise TaskInvocationError("public_input_source_outside_authorized_roots")
    if len(matches) != 1:
        raise TaskInvocationError("public_input_source_authority_ambiguous")
    return source


def _stream_copy_file(
    source: Path,
    target: Path,
    *,
    single_file_max_bytes: int | None,
    remaining_total_bytes: int | None,
) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as reader, target.open("xb") as writer:
        while True:
            chunk = reader.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if single_file_max_bytes is not None and size > single_file_max_bytes:
                raise TaskInvocationError("public_input_single_file_limit_exceeded")
            if remaining_total_bytes is not None and size > remaining_total_bytes:
                raise TaskInvocationError("public_input_request_size_limit_exceeded")
            digest.update(chunk)
            writer.write(chunk)
        writer.flush()
        os.fsync(writer.fileno())
    return digest.hexdigest(), size


def _atomic_write_json(path: Path, payload: Any) -> None:
    if path.exists():
        raise TaskInvocationError("public_input_snapshot_manifest_exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = temporary_sibling_path(path)
    data = canonical_json_bytes(payload)
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _snapshot_file(
    source: Path,
    *,
    blobs_dir: Path,
    policy: InputSnapshotPolicy,
    remaining_total_bytes: int | None,
) -> tuple[Path, str, int]:
    temporary = blobs_dir / f".input-{uuid.uuid4().hex}.tmp"
    try:
        digest, size = _stream_copy_file(
            source,
            temporary,
            single_file_max_bytes=policy.single_file_max_bytes,
            remaining_total_bytes=remaining_total_bytes,
        )
        target = blobs_dir / digest
        if target.exists():
            temporary.unlink()
        else:
            os.replace(temporary, target)
        if target.stat().st_size != size:
            raise TaskInvocationError("public_input_snapshot_size_mismatch")
        return target, digest, size
    finally:
        if temporary.exists():
            temporary.unlink()


def _snapshot_directory(
    source: Path,
    *,
    trees_dir: Path,
    policy: InputSnapshotPolicy,
    remaining_total_bytes: int | None,
) -> tuple[Path, str, int, tuple[dict[str, Any], ...]]:
    temporary = trees_dir / f".tree-{uuid.uuid4().hex}.tmp"
    temporary.mkdir(parents=True, exist_ok=False)
    entries: list[dict[str, Any]] = []
    total_size = 0
    entry_count = 0

    def walk(source_dir: Path, target_dir: Path, relative_prefix: Path) -> None:
        nonlocal total_size, entry_count
        with os.scandir(source_dir) as iterator:
            children = sorted(list(iterator), key=lambda item: item.name)
        for child in children:
            child_path = Path(child.path)
            relative = (relative_prefix / child.name).as_posix()
            entry_count += 1
            if policy.directory_max_entries is not None and entry_count > policy.directory_max_entries:
                raise TaskInvocationError("public_input_directory_entry_limit_exceeded")
            if child.is_symlink() or _is_reparse_point(child_path):
                raise TaskInvocationError("public_input_directory_indirection_forbidden")
            if child.is_dir(follow_symlinks=False):
                target_child = target_dir / child.name
                target_child.mkdir()
                entries.append({"path": relative, "kind": "directory"})
                walk(child_path, target_child, relative_prefix / child.name)
            elif child.is_file(follow_symlinks=False):
                target_child = target_dir / child.name
                digest, size = _stream_copy_file(
                    child_path,
                    target_child,
                    single_file_max_bytes=policy.single_file_max_bytes,
                    remaining_total_bytes=(
                        None if remaining_total_bytes is None
                        else remaining_total_bytes - total_size
                    ),
                )
                total_size += size
                entries.append(
                    {
                        "path": relative,
                        "kind": "file",
                        "sha256": digest,
                        "byte_size": size,
                    }
                )
            else:
                raise TaskInvocationError("public_input_directory_special_entry_forbidden")

    try:
        walk(source, temporary, Path())
        entries.sort(key=lambda item: str(item["path"]))
        tree_hash = canonical_sha256({"kind": "directory", "entries": entries})
        target = trees_dir / tree_hash
        if target.exists():
            shutil.rmtree(temporary)
        else:
            _promote_directory_snapshot(temporary, target)
        return target, tree_hash, total_size, tuple(entries)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def _promote_directory_snapshot(temporary: Path, target: Path) -> None:
    """Promote a content-addressed tree through bounded transient-I/O retries."""

    for attempt in range(_DIRECTORY_PROMOTION_ATTEMPTS):
        if target.exists():
            shutil.rmtree(temporary)
            return
        try:
            os.replace(temporary, target)
            return
        except OSError as exc:
            # A concurrent producer may have atomically published the same
            # content-addressed tree between the existence check and replace.
            if target.exists():
                shutil.rmtree(temporary)
                return
            winerror = getattr(exc, "winerror", None)
            retryable = isinstance(exc, PermissionError) or (
                winerror in _TRANSIENT_WINDOWS_PROMOTION_ERRORS
            )
            if not retryable or attempt + 1 >= _DIRECTORY_PROMOTION_ATTEMPTS:
                raise TaskInvocationError(
                    "public_input_directory_snapshot_promotion_failed"
                ) from exc
            time.sleep(_DIRECTORY_PROMOTION_BASE_DELAY_SECONDS * (2**attempt))


def _read_inline_text(path: Path, *, size: int, limit: int) -> str | None:
    if size > limit:
        return None
    try:
        # Decode the authoritative bytes directly. ``Path.read_text`` performs
        # universal-newline translation, which breaks the content hash/byte
        # identity required by MaterialDescriptorV1 on Windows.
        return path.read_bytes().decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return None


def _runtime_path(spec: InputSourceSpec, *, source: Path) -> str:
    if source.is_dir():
        return f"/app/inputs/{spec.logical_name}"
    return f"/app/inputs/{spec.logical_name}/{source.name}"


def prepare_task_invocation(
    *,
    query: str,
    input_specs: Sequence[InputSourceSpec],
    run_dir: Path,
    request_id: str | None = None,
    final_deliverable_contract: Mapping[str, Any] | None = None,
    public_context_descriptors: Sequence[Mapping[str, Any]] = (),
    policy: InputSnapshotPolicy | None = None,
    allowed_public_input_roots: Sequence[str | Path] = (),
    project_root: Path | None = None,
) -> PreparedTaskInvocation:
    """Snapshot every explicit input before returning a production request."""

    if not isinstance(query, str) or not query:
        raise TaskInvocationError("task_query_empty")
    effective_policy = policy or InputSnapshotPolicy()
    authorized_roots = normalize_public_input_roots(
        allowed_public_input_roots,
        project_root=project_root,
        run_dir=run_dir,
    )
    logical_names = [item.logical_name for item in input_specs]
    if len(logical_names) != len(set(logical_names)):
        raise TaskInvocationError("public_input_logical_name_duplicate")
    for name in logical_names:
        PublicInputDescriptor._validate_logical_name(name)
    authorized_specs = tuple(
        (
            spec,
            _authorize_file_backed_input(
                spec.source_path,
                allowed_roots=authorized_roots,
            ),
        )
        for spec in input_specs
    )

    input_root = run_dir / "inputs"
    blobs_dir = input_root / "blobs"
    trees_dir = input_root / "trees"
    blobs_dir.mkdir(parents=True, exist_ok=False)
    trees_dir.mkdir(parents=True, exist_ok=False)

    descriptors: list[PublicInputDescriptor] = []
    snapshot_records: list[dict[str, Any]] = []
    private_paths: dict[str, Path] = {}
    total_size = 0

    for spec, source in authorized_specs:
        remaining = (
            None if effective_policy.request_total_max_bytes is None
            else effective_policy.request_total_max_bytes - total_size
        )
        if remaining is not None and remaining < 0:
            raise TaskInvocationError("public_input_request_size_limit_exceeded")
        runtime_path = _runtime_path(spec, source=source)
        if source.is_file():
            snapshot_path, digest, size = _snapshot_file(
                source,
                blobs_dir=blobs_dir,
                policy=effective_policy,
                remaining_total_bytes=remaining,
            )
            total_size += size
            inline_text = _read_inline_text(
                snapshot_path,
                size=size,
                limit=effective_policy.inline_text_max_bytes,
            )
            media_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
            handle_id = "public_input_" + canonical_sha256(
                {"logical_name": spec.logical_name, "sha256": digest, "kind": "file"}
            )[:20]
            execution_contract = dict(spec.execution_contract or {})
            inventory = observe_container_inventory(snapshot_path, extension=source.suffix)
            if inventory:
                execution_contract["container_inventory"] = inventory
            descriptor = PublicInputDescriptor(
                logical_name=spec.logical_name,
                handle_id=handle_id,
                runtime_path=runtime_path,
                path_kind="file",
                source_name=source.name,
                media_type=media_type,
                extension=source.suffix.lower(),
                content_sha256=digest,
                byte_size=size,
                inline_text=inline_text,
                content_available_as_context=inline_text is not None,
                execution_contract=execution_contract,
            )
            tree_entries: tuple[dict[str, Any], ...] = ()
        else:
            snapshot_path, digest, size, tree_entries = _snapshot_directory(
                source,
                trees_dir=trees_dir,
                policy=effective_policy,
                remaining_total_bytes=remaining,
            )
            total_size += size
            handle_id = "public_input_" + canonical_sha256(
                {"logical_name": spec.logical_name, "sha256": digest, "kind": "directory"}
            )[:20]
            descriptor = PublicInputDescriptor(
                logical_name=spec.logical_name,
                handle_id=handle_id,
                runtime_path=runtime_path,
                path_kind="directory",
                source_name=source.name,
                media_type="inode/directory",
                extension="",
                content_sha256=digest,
                byte_size=size,
                entry_count=len(tree_entries),
                tree_manifest_sha256=digest,
                execution_contract=dict(spec.execution_contract or {}),
            )
        descriptors.append(descriptor)
        private_paths[handle_id] = snapshot_path
        snapshot_records.append(
            {
                "descriptor": descriptor.model_dump(mode="json"),
                "tree_entries": list(tree_entries),
            }
        )

    snapshot_projection = {
        "protocol": PUBLIC_INPUT_SNAPSHOT_PROTOCOL,
        "policy": effective_policy.model_dump(mode="json"),
        "inputs": snapshot_records,
        "total_byte_size": total_size,
    }
    snapshot_sha256 = canonical_sha256(snapshot_projection)
    snapshot_payload = {**snapshot_projection, "snapshot_sha256": snapshot_sha256}
    snapshot_manifest = input_root / "input_snapshot.json"
    _atomic_write_json(snapshot_manifest, snapshot_payload)

    provisional = {
        "protocol": TASK_INVOCATION_PROTOCOL,
        "request_id": str(request_id or uuid.uuid4().hex),
        "query": query,
        "public_inputs": [item.model_dump(mode="json") for item in descriptors],
        "final_deliverable_contract": (
            FinalDeliverableContract.model_validate(final_deliverable_contract).model_dump(
                mode="json"
            )
            if final_deliverable_contract is not None
            else None
        ),
        "public_context_descriptors": [dict(item) for item in public_context_descriptors],
        "input_snapshot_sha256": snapshot_sha256,
    }
    invocation = TaskInvocation(
        **provisional,
        invocation_sha256=canonical_sha256(provisional),
    )
    return PreparedTaskInvocation(
        invocation=invocation,
        snapshot_paths_by_handle=private_paths,
        snapshot_manifest_path=snapshot_manifest,
    )


def parse_named_input(value: str, *, base_dir: Path) -> InputSourceSpec:
    name, separator, raw_path = str(value).partition("=")
    if not separator or not name or not raw_path:
        raise TaskInvocationError("input_argument_must_be_name_equals_path")
    source = Path(raw_path)
    if not source.is_absolute():
        source = base_dir / source
    return InputSourceSpec(logical_name=name, source_path=source)


def load_input_manifest(path: Path) -> tuple[InputSourceSpec, ...]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TaskInvocationError("input_manifest_invalid") from exc
    raw_items: Iterable[Any]
    if isinstance(payload, Mapping):
        raw_items = payload.get("inputs", payload)
        if isinstance(raw_items, Mapping):
            raw_items = [
                {"name": str(name), "path": raw_path}
                for name, raw_path in raw_items.items()
            ]
    else:
        raw_items = payload
    if not isinstance(raw_items, Sequence) or isinstance(raw_items, (str, bytes)):
        raise TaskInvocationError("input_manifest_items_invalid")
    specs: list[InputSourceSpec] = []
    for item in raw_items:
        if not isinstance(item, Mapping):
            raise TaskInvocationError("input_manifest_item_invalid")
        name = str(item.get("name") or item.get("logical_name") or "")
        raw_path = item.get("path")
        if not name or not isinstance(raw_path, str) or not raw_path:
            raise TaskInvocationError("input_manifest_item_invalid")
        source = Path(raw_path)
        if not source.is_absolute():
            source = path.parent / source
        execution_contract = item.get("execution_contract")
        if execution_contract is not None and not isinstance(execution_contract, Mapping):
            raise TaskInvocationError("input_manifest_execution_contract_invalid")
        specs.append(InputSourceSpec(
            logical_name=name,
            source_path=source,
            execution_contract=(
                dict(execution_contract) if isinstance(execution_contract, Mapping) else None
            ),
        ))
    return tuple(specs)


def load_request_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TaskInvocationError("request_manifest_invalid") from exc
    if not isinstance(payload, Mapping):
        raise TaskInvocationError("request_manifest_root_invalid")
    result = dict(payload)
    raw_inputs = result.get("inputs", ())
    if not isinstance(raw_inputs, Sequence) or isinstance(raw_inputs, (str, bytes)):
        raise TaskInvocationError("request_manifest_inputs_invalid")
    specs: list[InputSourceSpec] = []
    for item in raw_inputs:
        if not isinstance(item, Mapping):
            raise TaskInvocationError("request_manifest_input_invalid")
        name = str(item.get("name") or item.get("logical_name") or "")
        raw_path = item.get("path")
        if not name or not isinstance(raw_path, str) or not raw_path:
            raise TaskInvocationError("request_manifest_input_invalid")
        source = Path(raw_path)
        if not source.is_absolute():
            source = path.parent / source
        execution_contract = item.get("execution_contract")
        if execution_contract is not None and not isinstance(execution_contract, Mapping):
            raise TaskInvocationError("request_manifest_execution_contract_invalid")
        specs.append(InputSourceSpec(
            logical_name=name,
            source_path=source,
            execution_contract=(
                dict(execution_contract) if isinstance(execution_contract, Mapping) else None
            ),
        ))
    result["input_specs"] = tuple(specs)
    return result


def _read_exact_query_file(path: Path, *, encoding: str) -> tuple[str, str]:
    try:
        raw = path.read_bytes()
        return raw.decode(encoding, errors="strict"), hashlib.sha256(raw).hexdigest()
    except (OSError, UnicodeError, LookupError) as exc:
        raise TaskInvocationError("query_file_decode_failed") from exc


def _validate_unique_input_names(specs: Sequence[InputSourceSpec]) -> None:
    names = [str(item.logical_name).strip() for item in specs]
    if any(not name for name in names):
        raise TaskInvocationError("public_input_logical_name_empty")
    if len(names) != len(set(names)):
        raise TaskInvocationError("public_input_logical_name_duplicate")


def resolve_task_request(
    *,
    request_manifest: Path | None,
    query: str | None,
    query_file: Path | None,
    query_file_encoding: str,
    named_inputs: Sequence[str],
    input_manifest: Path | None,
    allowed_public_input_roots: Sequence[str | Path] = (),
    project_root: Path | None = None,
    run_dir: Path | None = None,
) -> ResolvedTaskRequest:
    """Resolve formal task arguments once, without snapshotting or paid work."""

    authorized_roots = normalize_public_input_roots(
        allowed_public_input_roots,
        project_root=project_root,
        run_dir=run_dir,
    )

    if request_manifest is not None:
        if (
            query is not None
            or query_file is not None
            or bool(named_inputs)
            or input_manifest is not None
        ):
            raise TaskInvocationError("request_manifest_cannot_be_combined")
        manifest_path = _authorize_file_backed_input(
            Path(request_manifest),
            allowed_roots=authorized_roots,
        )
        payload = load_request_manifest(manifest_path)
        has_query = "query" in payload
        has_query_file = "query_file" in payload
        if has_query == has_query_file:
            raise TaskInvocationError("request_manifest_query_must_be_exactly_one")
        if has_query:
            exact_query = payload.get("query")
            if not isinstance(exact_query, str):
                raise TaskInvocationError("request_manifest_query_invalid")
            query_source_sha256 = hashlib.sha256(exact_query.encode("utf-8")).hexdigest()
        else:
            raw_query_file = payload.get("query_file")
            if not isinstance(raw_query_file, str) or not raw_query_file:
                raise TaskInvocationError("request_manifest_query_file_invalid")
            manifest_query_file = Path(raw_query_file)
            if not manifest_query_file.is_absolute():
                manifest_query_file = manifest_path.parent / manifest_query_file
            encoding = str(payload.get("query_file_encoding") or "utf-8-sig")
            authorized_query_file = _authorize_file_backed_input(
                manifest_query_file,
                allowed_roots=authorized_roots,
            )
            exact_query, query_source_sha256 = _read_exact_query_file(
                authorized_query_file,
                encoding=encoding,
            )
        public_context = payload.get("public_context_descriptors") or ()
        if not isinstance(public_context, (list, tuple)) or not all(
            isinstance(item, Mapping) for item in public_context
        ):
            raise TaskInvocationError("request_public_context_invalid")
        deliverable = payload.get("final_deliverable_contract")
        if deliverable is not None and not isinstance(deliverable, Mapping):
            raise TaskInvocationError("request_deliverable_contract_invalid")
        specs = tuple(
            InputSourceSpec(
                logical_name=spec.logical_name,
                source_path=_authorize_file_backed_input(
                    spec.source_path,
                    allowed_roots=authorized_roots,
                ),
            )
            for spec in payload["input_specs"]
        )
        _validate_unique_input_names(specs)
        source_projection = {
            "source_kind": "request_manifest",
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "query_source_sha256": query_source_sha256,
            "query_sha256": canonical_sha256(exact_query),
        }
        source_sha256 = canonical_sha256(source_projection)
        request_id = str(payload.get("request_id") or f"request-{source_sha256[:32]}").strip()
        if not request_id:
            raise TaskInvocationError("request_id_empty")
        return ResolvedTaskRequest(
            exact_query=exact_query,
            request_id=request_id,
            input_specs=specs,
            public_context_descriptors=tuple(dict(item) for item in public_context),
            final_deliverable_contract=(dict(deliverable) if deliverable is not None else None),
            request_source_sha256=source_sha256,
            allowed_public_input_roots=authorized_roots,
        )

    if (query is None) == (query_file is None):
        raise TaskInvocationError("query_and_query_file_must_be_exactly_one")
    if query is not None:
        exact_query = query
        query_source_sha256 = hashlib.sha256(query.encode("utf-8")).hexdigest()
    else:
        assert query_file is not None
        resolved_query_file = _authorize_file_backed_input(
            Path(query_file),
            allowed_roots=authorized_roots,
        )
        exact_query, query_source_sha256 = _read_exact_query_file(
            resolved_query_file,
            encoding=str(query_file_encoding or "utf-8-sig"),
        )

    specs = [parse_named_input(item, base_dir=Path.cwd()) for item in named_inputs]
    input_manifest_sha256: str | None = None
    if input_manifest is not None:
        resolved_input_manifest = _authorize_file_backed_input(
            Path(input_manifest),
            allowed_roots=authorized_roots,
        )
        specs.extend(load_input_manifest(resolved_input_manifest))
        try:
            input_manifest_sha256 = hashlib.sha256(
                resolved_input_manifest.read_bytes()
            ).hexdigest()
        except OSError as exc:
            raise TaskInvocationError("input_manifest_invalid") from exc
    specs = [
        InputSourceSpec(
            logical_name=spec.logical_name,
            source_path=_authorize_file_backed_input(
                spec.source_path,
                allowed_roots=authorized_roots,
            ),
        )
        for spec in specs
    ]
    _validate_unique_input_names(specs)
    source_projection = {
        "source_kind": "cli",
        "query_source_sha256": query_source_sha256,
        "query_sha256": canonical_sha256(exact_query),
        "named_inputs_sha256": canonical_sha256(tuple(str(item) for item in named_inputs)),
        "input_manifest_sha256": input_manifest_sha256,
    }
    source_sha256 = canonical_sha256(source_projection)
    return ResolvedTaskRequest(
        exact_query=exact_query,
        request_id=f"request-{source_sha256[:32]}",
        input_specs=tuple(specs),
        public_context_descriptors=(),
        final_deliverable_contract=None,
        request_source_sha256=source_sha256,
        allowed_public_input_roots=authorized_roots,
    )
