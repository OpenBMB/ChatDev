"""Case-agnostic serialization of public local inputs.

The model-facing representation deliberately uses the runtime namespace only.
Host paths are returned separately for the executor and must never be serialized
into an LLM request.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence


PUBLIC_INPUT_PROTOCOL = "public-input-v2"
INTERNAL_METADATA_ROOT_NAMES = (".git", ".hg", ".svn", ".agents", ".codex")
INTERNAL_METADATA_LAYOUT_PROTOCOL = "sgar-internal-metadata-layout-v1"
_MAX_GITFILE_BYTES = 4096
_OPAQUE_SUFFIXES = {
    ".doc",
    ".docx",
    ".gif",
    ".jpeg",
    ".jpg",
    ".ods",
    ".pdf",
    ".png",
    ".ppt",
    ".pptx",
    ".webp",
    ".xls",
    ".xlsx",
    ".zip",
}


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _is_reparse_point(path: Path) -> bool:
    """Return whether *path* is a link-like filesystem indirection.

    ``Path.is_symlink`` is not sufficient on Windows: directory junctions and
    other reparse points can resolve outside the declared public tree without
    being reported as POSIX-style symlinks.
    """

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
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse_flag)


def _reject_link(path: Path, *, label: str) -> None:
    if path.is_symlink() or os.path.islink(path) or _is_reparse_point(path):
        raise ValueError(f"public_input_symlink_forbidden:{label}")


def directory_entries(path: Path) -> list[Dict[str, Any]]:
    """Return a deterministic tree including empty directories."""

    root = path.resolve(strict=True)
    entries: list[Dict[str, Any]] = []

    def walk(directory: Path) -> None:
        # Reject an indirection before descending into it.  ``rglob`` can walk
        # junctions on some Python/Windows combinations before the body gets a
        # chance to inspect the entry.
        for item in sorted(directory.iterdir(), key=lambda candidate: candidate.name):
            relative = item.relative_to(root).as_posix()
            _reject_link(item, label=relative)
            resolved = item.resolve(strict=True)
            if not _is_within(resolved, root):
                raise ValueError(f"public_input_path_escape:{relative}")
            if resolved.is_dir():
                entries.append({"path": relative, "kind": "directory"})
                walk(resolved)
            elif resolved.is_file():
                entries.append(
                    {
                        "path": relative,
                        "kind": "file",
                        "sha256": file_sha256(resolved),
                    }
                )
            else:
                raise ValueError(f"public_input_unsupported_entry:{relative}")

    walk(root)
    entries.sort(key=lambda entry: str(entry["path"]))
    return entries


def path_sha256(path: Path) -> str:
    _reject_link(path, label=str(path))
    resolved = path.resolve(strict=True)
    if resolved.is_file():
        return file_sha256(resolved)
    if resolved.is_dir():
        return canonical_hash({"kind": "directory", "entries": directory_entries(resolved)})
    raise FileNotFoundError(resolved)


def verify_public_input_path(
    *,
    path: Path,
    workspace_root: Path,
    expected_path_kind: str,
    expected_sha256: str,
) -> Path:
    """Revalidate the exact public bytes immediately before a sandbox mount."""

    workspace = workspace_root.resolve(strict=True)
    _reject_link(path, label=str(path))
    resolved = path.resolve(strict=True)
    if not _is_within(resolved, workspace):
        raise ValueError("public_input_outside_workspace")
    actual_kind = "directory" if resolved.is_dir() else "file" if resolved.is_file() else ""
    if actual_kind != str(expected_path_kind or ""):
        raise ValueError("public_input_path_kind_changed")
    expected_digest = str(expected_sha256 or "").strip().lower()
    if not expected_digest:
        raise ValueError("public_input_sha256_missing")
    if path_sha256(resolved).lower() != expected_digest:
        raise ValueError("public_input_sha256_changed")
    return resolved


class InternalMetadataLayoutError(ValueError):
    """A content-free framework failure for an unsafe metadata layout."""

    failure_code = "internal_metadata_layout_invalid"

    def __init__(self, layout_error_code: str) -> None:
        self.layout_error_code = str(layout_error_code or "metadata_layout_invalid")
        super().__init__(f"internal_metadata_layout:{self.layout_error_code}")


@dataclass(frozen=True)
class InternalMetadataEntry:
    name: str
    layout_type: str
    marker_path: Path
    target_path: Path | None = None


@dataclass(frozen=True)
class InternalMetadataLayout:
    workspace_root: Path
    entries: tuple[InternalMetadataEntry, ...]

    @property
    def hidden_roots(self) -> tuple[Path, ...]:
        return tuple(
            entry.marker_path
            for entry in self.entries
            if entry.layout_type == "directory"
        )

    def audit(self) -> Dict[str, Any]:
        if any(entry.layout_type == "gitfile" for entry in self.entries):
            layout_type = "gitfile"
        elif self.entries:
            layout_type = "directory"
        else:
            layout_type = "absent"
        projection: Dict[str, Any] = {
            "protocol": INTERNAL_METADATA_LAYOUT_PROTOCOL,
            "valid": True,
            "layout_type": layout_type,
            "present_names": [entry.name for entry in self.entries],
        }
        projection["layout_sha256"] = canonical_hash(projection)
        return projection


def _metadata_error(code: str) -> InternalMetadataLayoutError:
    return InternalMetadataLayoutError(code)


def _reject_metadata_indirection(path: Path, *, code: str) -> None:
    try:
        link_like = path.is_symlink() or os.path.islink(path) or _is_reparse_point(path)
    except OSError as exc:
        raise _metadata_error(code) from exc
    if link_like:
        raise _metadata_error(code)


def _parse_gitfile(candidate: Path) -> InternalMetadataEntry:
    try:
        size = candidate.stat().st_size
    except OSError as exc:
        raise _metadata_error("gitfile_read_failed") from exc
    if size <= 0 or size > _MAX_GITFILE_BYTES:
        raise _metadata_error("gitfile_size_invalid")
    try:
        payload = candidate.read_bytes()
    except OSError as exc:
        raise _metadata_error("gitfile_read_failed") from exc
    if len(payload) != size or b"\x00" in payload:
        raise _metadata_error("gitfile_syntax_invalid")
    if payload.endswith(b"\r\n"):
        line = payload[:-2]
    elif payload.endswith(b"\n"):
        line = payload[:-1]
    else:
        line = payload
    if b"\r" in line or b"\n" in line or not line.startswith(b"gitdir: "):
        raise _metadata_error("gitfile_syntax_invalid")
    target_bytes = line[len(b"gitdir: ") :]
    if not target_bytes or target_bytes.strip() != target_bytes:
        raise _metadata_error("gitfile_syntax_invalid")
    try:
        target_text = os.fsdecode(target_bytes)
    except (TypeError, UnicodeError) as exc:
        raise _metadata_error("gitfile_encoding_invalid") from exc
    if not target_text or any(0xD800 <= ord(char) <= 0xDFFF for char in target_text):
        raise _metadata_error("gitfile_encoding_invalid")
    raw_target = Path(target_text)
    target = raw_target if raw_target.is_absolute() else candidate.parent / raw_target
    if not os.path.lexists(target):
        raise _metadata_error("gitfile_target_invalid")
    _reject_metadata_indirection(target, code="gitfile_target_indirection")
    try:
        resolved_target = target.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise _metadata_error("gitfile_target_invalid") from exc
    if not resolved_target.is_dir():
        raise _metadata_error("gitfile_target_invalid")
    return InternalMetadataEntry(
        name=".git",
        layout_type="gitfile",
        marker_path=candidate.resolve(strict=True),
        target_path=resolved_target,
    )


def inspect_internal_metadata_layout(workspace_root: Path) -> InternalMetadataLayout:
    """Classify hidden repository metadata without exposing its contents."""

    workspace = workspace_root.resolve(strict=True)
    entries: list[InternalMetadataEntry] = []
    for name in INTERNAL_METADATA_ROOT_NAMES:
        candidate = workspace / name
        if not os.path.lexists(candidate):
            continue
        _reject_metadata_indirection(candidate, code="metadata_entry_indirection")
        try:
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise _metadata_error("metadata_entry_invalid") from exc
        if resolved.is_dir():
            if not _is_within(resolved, workspace):
                raise _metadata_error("metadata_entry_outside_workspace")
            entries.append(
                InternalMetadataEntry(
                    name=name,
                    layout_type="directory",
                    marker_path=resolved,
                )
            )
            continue
        if name == ".git" and resolved.is_file():
            entries.append(_parse_gitfile(candidate))
            continue
        raise _metadata_error("metadata_entry_not_directory")
    return InternalMetadataLayout(workspace_root=workspace, entries=tuple(entries))


def internal_metadata_layout_audit(workspace_root: Path) -> Dict[str, Any]:
    return inspect_internal_metadata_layout(workspace_root).audit()


def internal_metadata_roots(workspace_root: Path) -> tuple[Path, ...]:
    """Return metadata directories that require tmpfs masking.

    A standard linked-worktree ``.git`` gitfile is validated by the same
    classifier but is intentionally not represented as a directory mount.
    """

    return inspect_internal_metadata_layout(workspace_root).hidden_roots


def _scope_host_entries(scope: Mapping[str, Any]) -> tuple[tuple[Path, str], ...]:
    entries: list[tuple[Path, str]] = []
    for field in ("runtime_roots", "public_inputs"):
        raw_entries = scope.get(field) or ()
        if isinstance(raw_entries, Mapping) or isinstance(raw_entries, (str, bytes)):
            raw_entries = (raw_entries,)
        for raw in raw_entries:
            if not isinstance(raw, Mapping) or not raw.get("host_path"):
                continue
            path_kind = str(raw.get("path_kind") or "directory")
            entries.append((Path(str(raw["host_path"])).resolve(strict=False), path_kind))
    writable = scope.get("writable_root")
    if isinstance(writable, Mapping) and writable.get("host_path"):
        entries.append(
            (
                Path(str(writable["host_path"])).resolve(strict=False),
                str(writable.get("path_kind") or "directory"),
            )
        )
    return tuple(entries)


def _paths_overlap(
    left: Path,
    left_kind: str,
    right: Path,
    right_kind: str,
) -> bool:
    if os.path.normcase(str(left)) == os.path.normcase(str(right)):
        return True
    if left_kind == "directory" and _is_within(right, left):
        return True
    if right_kind == "directory" and _is_within(left, right):
        return True
    return False


def validate_internal_metadata_scope(
    layout: InternalMetadataLayout,
    scope: Mapping[str, Any],
) -> None:
    """Reject any runtime/public/writable route that exposes a gitfile layout."""

    protected: list[tuple[Path, str]] = []
    for entry in layout.entries:
        if entry.layout_type != "gitfile":
            continue
        protected.append((entry.marker_path, "file"))
        if entry.target_path is not None:
            protected.append((entry.target_path, "directory"))
    for protected_path, protected_kind in protected:
        for route_path, route_kind in _scope_host_entries(scope):
            if _paths_overlap(protected_path, protected_kind, route_path, route_kind):
                raise _metadata_error("metadata_route_exposure")


@dataclass(frozen=True)
class PublicInput:
    fixture_id: str
    role: str
    host_path: Path
    workspace_relative_path: str
    runtime_path: str
    path_kind: str
    sha256: str
    content: str | None = None
    directory_entries: tuple[Mapping[str, Any], ...] = ()

    @property
    def handle_id(self) -> str:
        seed = canonical_hash(
            {
                "fixture_id": self.fixture_id,
                "role": self.role,
                "workspace_relative_path": self.workspace_relative_path,
                "sha256": self.sha256,
            }
        )[:16]
        return f"public_input_{seed}"

    def model_view(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "fixture_id": self.fixture_id,
            "role": self.role,
            "path": self.runtime_path,
            "logical_path": self.workspace_relative_path,
            "runtime_path": self.runtime_path,
            "path_kind": self.path_kind,
            "sha256": self.sha256,
            "status": "available",
            "origin": "public_input",
            "content_available_as_context": self.content is not None,
        }
        if self.content is not None:
            payload["content"] = self.content
        if self.path_kind == "directory":
            payload["directory_entries"] = [dict(item) for item in self.directory_entries]
            payload["directory_files"] = [
                str(item["path"])
                for item in self.directory_entries
                if item.get("kind") == "file"
            ]
        return payload

    def public_handle(self) -> Dict[str, Any]:
        return {
            "handle_id": self.handle_id,
            "kind": "input_directory" if self.path_kind == "directory" else "input_file",
            "logical_path": self.workspace_relative_path,
            "host_path": None,
            "tool_path": self.runtime_path,
            "artifact_type": "directory" if self.path_kind == "directory" else "file",
            "validation_status": "public_input_verified",
            "current_run": True,
        }

    def internal_handle(self) -> Dict[str, Any]:
        payload = self.public_handle()
        payload["host_path"] = str(self.host_path)
        return payload


def serialize_public_input(
    *,
    fixture_id: str,
    role: str,
    path: Path,
    workspace_root: Path,
    opaque_suffixes: Iterable[str] = _OPAQUE_SUFFIXES,
) -> PublicInput:
    workspace = workspace_root.resolve(strict=True)
    _reject_link(path, label=str(path))
    resolved = path.resolve(strict=True)
    if not _is_within(resolved, workspace):
        raise ValueError("public_input_outside_workspace")
    relative = resolved.relative_to(workspace).as_posix()
    runtime_path = f"/app/{relative}"
    if resolved.is_dir():
        entries = tuple(directory_entries(resolved))
        return PublicInput(
            fixture_id=str(fixture_id),
            role=str(role),
            host_path=resolved,
            workspace_relative_path=relative,
            runtime_path=runtime_path,
            path_kind="directory",
            sha256=canonical_hash({"kind": "directory", "entries": entries}),
            directory_entries=entries,
        )
    if not resolved.is_file():
        raise ValueError("public_input_not_file_or_directory")
    content: str | None = None
    if resolved.suffix.lower() not in {str(item).lower() for item in opaque_suffixes}:
        try:
            content = resolved.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = None
    return PublicInput(
        fixture_id=str(fixture_id),
        role=str(role),
        host_path=resolved,
        workspace_relative_path=relative,
        runtime_path=runtime_path,
        path_kind="file",
        sha256=file_sha256(resolved),
        content=content,
    )


def descriptor_hash(inputs: Sequence[PublicInput]) -> str:
    return canonical_hash([item.model_view() for item in inputs])
