"""Attachment storage and serialization helpers."""

import base64
import hashlib
import json
import mimetypes
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from entity.messages import AttachmentRef, MessageBlock, MessageBlockType

DEFAULT_INLINE_LIMIT = 512 * 1024  # 512 KB


@dataclass
class AttachmentRecord:
    """Stores metadata about an attachment tracked inside a workflow run."""

    ref: AttachmentRef
    kind: MessageBlockType = MessageBlockType.FILE
    description: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ref": self.ref.to_dict(),
            "kind": self.kind.value,
            "description": self.description,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AttachmentRecord":
        ref_data = data.get("ref") or {}
        raw_kind = data.get("kind", MessageBlockType.FILE.value)
        try:
            kind = MessageBlockType(raw_kind)
        except ValueError:
            kind = MessageBlockType.FILE
        return cls(
            ref=AttachmentRef.from_dict(ref_data),
            kind=kind,
            description=data.get("description"),
            extra=data.get("extra") or {},
        )

    def as_message_block(self) -> MessageBlock:
        """Convert to a MessageBlock referencing this attachment."""
        return MessageBlock(
            type=self.kind,
            attachment=self.ref.copy(),
            data=dict(self.extra),
        )


class AttachmentStore:
    """Filesystem-backed attachment manifest for a workflow execution."""

    def __init__(self, root_dir: Path | str, inline_size_limit: int = DEFAULT_INLINE_LIMIT) -> None:
        self.root = Path(root_dir)
        self.inline_size_limit = inline_size_limit
        self.root.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.root / "attachments_manifest.json"
        self._records: Dict[str, AttachmentRecord] = {}
        self._persistent_ids: set[str] = set()
        self._hash_index: Dict[str, str] = {}
        self._load_manifest()

    def register_file(
        self,
        file_path: Path | str,
        *,
        kind: MessageBlockType = MessageBlockType.FILE,
        display_name: Optional[str] = None,
        mime_type: Optional[str] = None,
        attachment_id: Optional[str] = None,
        copy_file: bool = True,
        description: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
        persist: bool = True,
        deduplicate: bool = False,
    ) -> AttachmentRecord:
        """Register a local file and return its attachment record."""
        source = Path(file_path)
        if not source.exists():
            raise FileNotFoundError(f"Attachment source not found: {source}")

        guessed_mime = mime_type or (mimetypes.guess_type(source.name)[0] or "application/octet-stream")
        attachment_id = attachment_id or uuid.uuid4().hex
        sha256_source = _sha256_file(source)

        if deduplicate:
            existing = self._find_duplicate_by_hash(
                sha256_source,
                copy_file=copy_file,
                source_path=source,
            )
            if existing:
                return existing
        if copy_file:
            target_dir = self.root / attachment_id
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / source.name
            shutil.copy2(source, target_path)
        else:
            target_path = source.resolve()

        size = target_path.stat().st_size
        sha256 = sha256_source or _sha256_file(target_path)
        data_uri = None
        # if size <= self.inline_size_limit:
        #     data_uri = encode_file_to_data_uri(target_path, guessed_mime)

        ref = AttachmentRef(
            attachment_id=attachment_id,
            mime_type=guessed_mime,
            name=display_name or source.name,
            size=size,
            sha256=sha256,
            local_path=str(target_path),
            data_uri=data_uri,
        )
        record = AttachmentRecord(
            ref=ref,
            kind=kind,
            description=description,
            extra=dict(extra) if extra else {},
        )
        self._records[attachment_id] = record
        if sha256:
            self._hash_index[sha256] = attachment_id
        if persist:
            self._persistent_ids.add(attachment_id)
            self._save_manifest()
        else:
            self._persistent_ids.discard(attachment_id)
        return record

    def register_bytes(
        self,
        data: bytes | bytearray,
        *,
        kind: MessageBlockType = MessageBlockType.FILE,
        mime_type: Optional[str] = None,
        display_name: Optional[str] = None,
        attachment_id: Optional[str] = None,
        description: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
        persist: bool = True,
    ) -> AttachmentRecord:
        """Register an in-memory payload as an attachment."""

        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("register_bytes expects bytes or bytearray data")

        attachment_id = attachment_id or uuid.uuid4().hex
        filename = display_name or _default_filename_for_mime(mime_type)

        target_dir = self.root / attachment_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / filename
        with target_path.open("wb") as handle:
            handle.write(bytes(data))

        return self.register_file(
            target_path,
            kind=kind,
            display_name=display_name or filename,
            mime_type=mime_type,
            attachment_id=attachment_id,
            copy_file=False,
            description=description,
            extra=extra,
            persist=persist,
        )

    def register_remote_file(
        self,
        *,
        remote_file_id: str,
        name: str,
        mime_type: Optional[str] = None,
        size: Optional[int] = None,
        kind: MessageBlockType = MessageBlockType.FILE,
        attachment_id: Optional[str] = None,
        description: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
        persist: bool = True,
    ) -> AttachmentRecord:
        """Register an already-uploaded file (e.g., OpenAI file ID)."""
        attachment_id = attachment_id or uuid.uuid4().hex
        ref = AttachmentRef(
            attachment_id=attachment_id,
            mime_type=mime_type,
            name=name,
            size=size,
            remote_file_id=remote_file_id,
        )
        record = AttachmentRecord(ref=ref, kind=kind, description=description, extra=extra or {})
        self._records[attachment_id] = record
        if persist:
            self._persistent_ids.add(attachment_id)
            self._save_manifest()
        else:
            self._persistent_ids.discard(attachment_id)
        if ref.sha256:
            self._hash_index[ref.sha256] = attachment_id
        return record

    def update_remote_file_id(self, attachment_id: str, remote_file_id: str) -> None:
        """Attach a provider file_id to an existing record (after upload)."""
        record = self._records.get(attachment_id)
        if not record:
            raise KeyError(f"Attachment '{attachment_id}' not found")
        record.ref.remote_file_id = remote_file_id
        if attachment_id in self._persistent_ids:
            self._save_manifest()

    def get(self, attachment_id: str) -> AttachmentRecord | None:
        return self._records.get(attachment_id)

    def to_message_block(self, attachment_id: str) -> MessageBlock:
        record = self._records.get(attachment_id)
        if not record:
            raise KeyError(f"Attachment '{attachment_id}' not found")
        return record.as_message_block()

    def list_records(self) -> Dict[str, AttachmentRecord]:
        return dict(self._records)

    def export_manifest(self) -> Dict[str, Any]:
        return {
            attachment_id: record.to_dict()
            for attachment_id, record in self._records.items()
            if attachment_id in self._persistent_ids
        }

    def _find_duplicate_by_hash(
        self,
        sha256: Optional[str],
        *,
        copy_file: bool,
        source_path: Optional[Path],
    ) -> Optional[AttachmentRecord]:
        if not sha256:
            return None
        existing_id = self._hash_index.get(sha256)
        if not existing_id:
            return None
        record = self._records.get(existing_id)
        if not record:
            self._hash_index.pop(sha256, None)
            return None
        if not copy_file and source_path is not None:
            existing_path = record.ref.local_path
            if not existing_path:
                return None
            try:
                if Path(existing_path).resolve() != source_path.resolve():
                    return None
            except FileNotFoundError:
                return None
        return record

    def ingest_record(
        self,
        record: AttachmentRecord,
        *,
        copy_file: bool = True,
        persist: bool = True,
    ) -> AttachmentRecord:
        """
        Import an existing attachment record (e.g., from a session upload) into this store.
        Optionally copies the underlying file into the store directory.
        """
        source_ref = record.ref
        attachment_id = source_ref.attachment_id or uuid.uuid4().hex
        new_ref = source_ref.copy()
        new_ref.attachment_id = attachment_id

        local_path = source_ref.local_path
        if local_path and copy_file:
            source_path = Path(local_path)
            if source_path.exists():
                target_dir = self.root / attachment_id
                target_dir.mkdir(parents=True, exist_ok=True)
                target_path = target_dir / source_path.name
                shutil.copy2(source_path, target_path)
                new_ref.local_path = str(target_path)
        self._records[attachment_id] = AttachmentRecord(
            ref=new_ref,
            kind=record.kind,
            description=record.description,
            extra=dict(record.extra),
        )
        if persist:
            self._persistent_ids.add(attachment_id)
            self._save_manifest()
        else:
            self._persistent_ids.discard(attachment_id)
        if new_ref.sha256:
            self._hash_index[new_ref.sha256] = attachment_id
        return self._records[attachment_id]

    def _load_manifest(self) -> None:
        if not self.manifest_path.exists():
            return
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        for attachment_id, record_data in data.items():
            try:
                record = AttachmentRecord.from_dict(record_data)
            except Exception:
                continue
            self._records[attachment_id] = record
            self._persistent_ids.add(attachment_id)
            if record.ref.sha256:
                self._hash_index[record.ref.sha256] = attachment_id

    def _save_manifest(self) -> None:
        serialized = self.export_manifest()
        self.manifest_path.write_text(json.dumps(serialized, ensure_ascii=False, indent=2), encoding="utf-8")


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def encode_file_to_data_uri(path: Path, mime_type: str) -> str:
    data = path.read_bytes()
    encoded = base64.b64encode(data).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def _default_filename_for_mime(mime_type: Optional[str]) -> str:
    if mime_type:
        ext = mimetypes.guess_extension(mime_type)
        if ext:
            return f"attachment{ext}"
    return "attachment.bin"
