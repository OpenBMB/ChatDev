"""Hook that scans a node workspace for newly created files."""

import hashlib
import logging
import mimetypes
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

from entity.configs import Node
from entity.messages import MessageBlockType
from utils.attachments import AttachmentRecord, AttachmentStore
from utils.human_prompt import PromptChannel


@dataclass
class WorkspaceArtifact:
    """Represents a file artifact detected by the workspace hook."""

    node_id: str
    attachment_id: str
    file_name: str
    relative_path: str
    absolute_path: str
    mime_type: Optional[str]
    size: Optional[int]
    sha256: Optional[str]
    data_uri: Optional[str]
    created_at: float
    change_type: str
    extra: Dict[str, object]


@dataclass
class _FileSignature:
    sha256: str
    size: int


@dataclass
class _TrackedEntry:
    sha256: str
    attachment_id: str
    absolute_path: str
    mime_type: Optional[str]
    size: Optional[int]
    data_uri: Optional[str]


class WorkspaceArtifactHook:
    """Detects workspace file changes for selected node types."""

    def __init__(
        self,
        *,
        attachment_store: AttachmentStore,
        emit_callback: Callable[[List[WorkspaceArtifact]], None],
        node_types: Optional[Sequence[str]] = None,
        exclude_dirs: Optional[Sequence[str]] = None,
        max_files_scanned: int = 500,
        max_bytes_scanned: int = 500 * 1024 * 1024,
        prompt_channel: Optional[PromptChannel] = None,
    ) -> None:
        self.attachment_store = attachment_store
        self.emit_callback = emit_callback
        self.node_types: Set[str] = set(node_types or {"python", "agent"})
        self.exclude_dirs = set(exclude_dirs or {"attachments", "__pycache__"})
        self.max_files_scanned = max_files_scanned
        self.max_bytes_scanned = max_bytes_scanned
        self.logger = logging.getLogger(__name__)
        self._snapshots: Dict[str, Dict[str, _FileSignature]] = {}
        self._last_emitted: Dict[str, _TrackedEntry] = {}
        self.prompt_channel = prompt_channel

    def can_handle(self, node: Node) -> bool:
        return node.node_type in self.node_types

    def get_prompt_channel(self) -> Optional[PromptChannel]:
        return self.prompt_channel

    def before_node(self, node: Node, workspace: Path) -> None:
        if not self.can_handle(node):
            return
        snapshot, _ = self._snapshot(workspace)
        self._snapshots[node.id] = snapshot

    def after_node(
        self,
        node: Node,
        workspace: Path,
        *,
        success: bool,
    ) -> None:
        if not success or not self.can_handle(node):
            self._snapshots.pop(node.id, None)
            return

        before = self._snapshots.pop(node.id, {})
        after, truncated = self._snapshot(workspace)
        if not after and not self._last_emitted:
            return

        changed_paths = [
            Path(path_str)
            for path_str, signature in after.items()
            if path_str not in before or before[path_str].sha256 != signature.sha256
        ]

        artifacts: List[WorkspaceArtifact] = []
        for relative_path in changed_paths:
            signature = after[str(relative_path)]
            full_path = workspace / relative_path
            if not full_path.exists() or not full_path.is_file():
                continue
            try:
                tracked = self._last_emitted.get(str(relative_path))
                change_type = "created" if tracked is None else "updated"
                record = self._register_artifact(
                    full_path,
                    relative_path,
                    node,
                    attachment_id=tracked.attachment_id if tracked else None,
                )
            except Exception as exc:
                self.logger.warning(
                    "Failed to register artifact %s for node %s: %s",
                    relative_path,
                    node.id,
                    exc,
                )
                continue
            artifacts.append(
                self._to_artifact(
                    record,
                    node,
                    relative_path,
                    full_path,
                    change_type=change_type,
                )
            )
            self._last_emitted[str(relative_path)] = _TrackedEntry(
                sha256=signature.sha256,
                attachment_id=record.ref.attachment_id or "",
                absolute_path=str(full_path),
                mime_type=record.ref.mime_type,
                size=record.ref.size,
                data_uri=record.ref.data_uri,
            )

        if not truncated:
            deleted_paths = [
                relative_path
                for relative_path in list(self._last_emitted.keys())
                if relative_path not in after
            ]
            for relative_path in deleted_paths:
                tracked = self._last_emitted.pop(relative_path, None)
                if not tracked:
                    continue
                artifacts.append(
                    WorkspaceArtifact(
                        node_id=node.id,
                        attachment_id=tracked.attachment_id,
                        file_name=Path(relative_path).name,
                        relative_path=relative_path,
                        absolute_path=tracked.absolute_path,
                        mime_type=tracked.mime_type,
                        size=tracked.size,
                        sha256=tracked.sha256,
                        data_uri=tracked.data_uri,
                        created_at=time.time(),
                        change_type="deleted",
                        extra={
                            "hook": "workspace_scan",
                            "relative_path": relative_path,
                        },
                    )
                )

        if artifacts:
            self.emit_callback(artifacts)

    def _snapshot(self, workspace: Path) -> Tuple[Dict[str, _FileSignature], bool]:
        entries: Dict[str, _FileSignature] = {}
        total_bytes = 0
        file_count = 0
        for root, dirs, files in os.walk(workspace):
            rel_root = Path(root).relative_to(workspace)
            dirs[:] = [d for d in dirs if not self._is_excluded(rel_root / d)]
            for filename in files:
                rel_path = rel_root / filename
                if self._is_excluded(rel_path):
                    continue
                full_path = Path(root) / filename
                try:
                    stat = full_path.stat()
                    sha256 = self._hash_file(full_path)
                except OSError:
                    continue
                file_count += 1
                total_bytes += stat.st_size
                entries[str(rel_path)] = _FileSignature(sha256=sha256, size=stat.st_size)
                if file_count >= self.max_files_scanned or total_bytes >= self.max_bytes_scanned:
                    self.logger.warning(
                        "Workspace scan truncated (files=%s total_bytes=%s)",
                        file_count,
                        total_bytes,
                    )
                    return entries, True
        return entries, False

    def _is_excluded(self, rel_path: Path) -> bool:
        if not rel_path.parts:
            return False
        return rel_path.parts[0] in self.exclude_dirs

    def _register_artifact(
        self,
        full_path: Path,
        relative_path: Path,
        node: Node,
        *,
        attachment_id: Optional[str] = None,
    ) -> AttachmentRecord:
        mime_type = mimetypes.guess_type(relative_path.name)[0] or "application/octet-stream"
        return self.attachment_store.register_file(
            full_path,
            kind=MessageBlockType.from_mime_type(mime_type),
            mime_type=mime_type,
            display_name=full_path.name,
            copy_file=False,
            persist=True,
            deduplicate=False,
            attachment_id=attachment_id,
            extra={
                "node_id": node.id,
                "relative_path": str(relative_path),
                "hook": "workspace_scan",
            },
        )

    def _to_artifact(
        self,
        record: AttachmentRecord,
        node: Node,
        relative_path: Path,
        full_path: Path,
        *,
        change_type: str,
    ) -> WorkspaceArtifact:
        ref = record.ref
        return WorkspaceArtifact(
            node_id=node.id,
            attachment_id=ref.attachment_id or "",
            file_name=ref.name or full_path.name,
            relative_path=str(relative_path),
            absolute_path=str(full_path),
            mime_type=ref.mime_type,
            size=ref.size,
            sha256=ref.sha256,
            data_uri=ref.data_uri,
            created_at=time.time(),
            change_type=change_type,
            extra=dict(record.extra),
        )

    def _hash_file(self, path: Path) -> str:
        hasher = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
