"""Attachment helpers shared by HTTP routes and executors."""

import logging
import mimetypes
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import UploadFile

from entity.messages import MessageBlock, MessageBlockType
from utils.attachments import AttachmentStore, AttachmentRecord
from utils.exceptions import SecurityError, ValidationError
from utils.workspace_paths import resolve_workspace_path, session_directory_name


class AttachmentService:
    """Handles attachment lifecycle per session."""

    def __init__(self, *, root: Path | str = Path("WareHouse")) -> None:
        self.logger = logging.getLogger(__name__)
        self.attachments_root = Path(root)
        self.attachments_root.mkdir(parents=True, exist_ok=True)
        env_flag = os.environ.get("MAC_AUTO_CLEAN_ATTACHMENTS", "0").strip().lower()
        self.clean_on_cleanup = env_flag in {"1", "true", "yes"}

    def prepare_session_workspace(self, session_id: str) -> Path:
        return self._session_attachments_path(session_id, create=True)

    def cleanup_session(self, session_id: str) -> None:
        attachment_dir = self._session_attachments_path(session_id, create=False)
        if not attachment_dir:
            return
        if self.clean_on_cleanup:
            shutil.rmtree(attachment_dir, ignore_errors=True)
            self.logger.info("Cleaned attachment directory for session %s", session_id)
        else:
            self.logger.info(
                "Attachment cleanup disabled; preserved files for session %s", session_id
            )

    def get_attachment_store(self, session_id: str) -> AttachmentStore:
        path = self.prepare_session_workspace(session_id)
        return AttachmentStore(path)

    @staticmethod
    def _safe_upload_filename(raw: Optional[str]) -> str:
        """Reduce a client-supplied upload filename to a safe basename.

        The multipart ``filename`` is attacker-controlled. Joining it onto the
        temporary upload directory verbatim allows path traversal (e.g.
        ``../../../etc/cron.d/x``): the write target escapes the temp dir and the
        cleanup step then unlinks the same traversed path, yielding arbitrary
        file write and delete. Normalise both POSIX and Windows separators and
        keep only the final path component so the write stays confined.
        """
        candidate = os.path.basename((raw or "").replace("\\", "/")).strip()
        if not candidate or candidate in {".", ".."}:
            return "upload.bin"
        return candidate

    async def save_upload_file(self, session_id: str, upload: UploadFile) -> AttachmentRecord:
        self._session_attachments_path(session_id, create=False)
        filename = self._safe_upload_filename(upload.filename)
        temp_dir = Path(tempfile.mkdtemp(prefix="mac_upload_"))
        temp_path = temp_dir / filename
        try:
            with temp_path.open("wb") as buffer:
                while True:
                    chunk = await upload.read(1024 * 1024)
                    if not chunk:
                        break
                    buffer.write(chunk)
            store = self.get_attachment_store(session_id)
            mime_type = upload.content_type or mimetypes.guess_type(filename)[0]
            record = store.register_file(
                temp_path,
                kind=MessageBlockType.from_mime_type(mime_type),
                display_name=filename,
                mime_type=mime_type,
                extra={
                    "source": "user_upload",
                    "origin": "web_upload",
                    "session_id": session_id,
                },
            )
            return record
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            try:
                temp_dir.rmdir()
            except OSError:
                pass

    def build_attachment_blocks(
        self,
        session_id: str,
        attachment_ids: List[str],
        *,
        target_store: Optional[AttachmentStore] = None,
    ) -> List[MessageBlock]:
        if not attachment_ids:
            return []
        source_store = self.get_attachment_store(session_id)
        source_root = source_store.root.resolve()
        target_root = target_store.root.resolve() if target_store else None
        blocks: List[MessageBlock] = []
        for attachment_id in attachment_ids:
            record = source_store.get(attachment_id)
            if not record:
                continue
            if target_store:
                copy_required = target_root != source_root
                record = target_store.ingest_record(record, copy_file=copy_required)
            blocks.append(record.as_message_block())
        return blocks

    def list_attachment_manifests(self, session_id: str) -> Dict[str, Any]:
        store = self.get_attachment_store(session_id)
        return store.export_manifest()

    def resolve_uploaded_paths(self, session_id: str, attachments: List[str]) -> List[str]:
        """Accept only registered uploads belonging to the specified session."""
        root = self._session_attachments_path(session_id, create=False)
        if root is None:
            raise SecurityError("Attachment upload session does not exist")
        manifest = root / "attachments_manifest.json"
        if manifest.is_symlink():
            raise SecurityError("Attachment manifest must not be a symbolic link")
        store = AttachmentStore(root)
        uploaded = {}
        for attachment_id in store.export_manifest():
            record = store.get(attachment_id)
            if (
                record.extra.get("origin") == "web_upload"
                and record.extra.get("session_id") == session_id
                and record.ref.local_path
            ):
                uploaded[attachment_id] = Path(record.ref.local_path)

        paths = []
        for value in attachments:
            try:
                source = uploaded.get(value)
                if source is None:
                    requested = Path(value).expanduser().resolve()
                    source = next((path for path in uploaded.values() if path.resolve() == requested), None)
                if source is None:
                    raise SecurityError("Attachment must reference a registered upload in attachment_session_id")
                resolved = source.resolve()
                if source.is_symlink() or not resolved.is_relative_to(root) or not resolved.is_file():
                    raise SecurityError("Attachment source must stay inside its upload session")
                paths.append(str(resolved))
            except (OSError, RuntimeError, ValueError) as exc:
                raise SecurityError("Invalid uploaded attachment source") from exc
        return paths

    def _session_attachments_path(self, session_id: str, *, create: bool = True) -> Optional[Path]:
        session_dir_name = session_directory_name(session_id)
        current = self.attachments_root
        for part in (session_dir_name, "code_workspace", "attachments"):
            current = current / part
            if current.is_symlink():
                raise ValidationError("Upload session paths must not contain symbolic links", field="session_id")
        path = resolve_workspace_path(
            self.attachments_root, session_dir_name, "code_workspace", "attachments"
        )
        if create:
            path.mkdir(parents=True, exist_ok=True)
            return path
        return path if path.exists() else None
