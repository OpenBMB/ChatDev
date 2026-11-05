"""Offline, re-entrant lifecycle primitives for frozen retrieval.

The production retrieval stack has three independent lifetimes:

* index metadata and frozen vectors;
* the local embedding model;
* the paid HyDE transport.

This module owns the local embedding snapshot identity.  It deliberately does
not import ``sentence_transformers`` or construct a provider client, so static
readiness checks remain offline and side-effect free.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from .pipeline_control import FrozenContract, canonical_sha256


LOCAL_EMBEDDING_IDENTITY_PROTOCOL = "sgar-local-embedding-identity-v2"


class RetrievalLifecycleError(RuntimeError):
    """Structured configuration failure raised before any paid retrieval call."""

    def __init__(self, failure_code: str) -> None:
        super().__init__(failure_code)
        self.failure_code = str(failure_code)
        self.failure_responsibility = "framework"
        self.failure_stage = "retrieval_configuration"
        self.retryable = False
        self.response_received = False


class LocalEmbeddingIdentity(FrozenContract):
    """Host-free identity for the pinned local embedding snapshot."""

    protocol: Literal[LOCAL_EMBEDDING_IDENTITY_PROTOCOL] = (
        LOCAL_EMBEDDING_IDENTITY_PROTOCOL
    )
    embedding_model_id: str = Field(min_length=1)
    embedding_model_revision: str | None = None
    local_snapshot_locator: str = Field(min_length=1)
    snapshot_content_sha256: str
    native_embedding_dimension: int = Field(gt=0)
    embedding_dimension: int = Field(gt=0)
    index_dimension: int = Field(gt=0)
    encoding_configuration_sha256: str
    offline_only: Literal[True] = True
    identity_sha256: str = ""

    @field_validator("snapshot_content_sha256")
    @classmethod
    def _validate_snapshot_hash(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
            raise ValueError("embedding_snapshot_sha256_invalid")
        return normalized

    @model_validator(mode="after")
    def _seal_identity(self) -> "LocalEmbeddingIdentity":
        if self.embedding_dimension != self.index_dimension:
            raise ValueError("embedding_index_dimension_mismatch")
        if self.embedding_dimension > self.native_embedding_dimension:
            raise ValueError("embedding_output_exceeds_native_dimension")
        if self.embedding_model_revision is not None:
            revision = self.embedding_model_revision.strip().lower()
            if len(revision) != 40 or any(ch not in "0123456789abcdef" for ch in revision):
                raise ValueError("embedding_model_revision_invalid")
            object.__setattr__(self, "embedding_model_revision", revision)
        if len(self.encoding_configuration_sha256) != 64 or any(
            ch not in "0123456789abcdef" for ch in self.encoding_configuration_sha256
        ):
            raise ValueError("embedding_configuration_sha256_invalid")
        projection = self.model_dump(mode="python", exclude={"identity_sha256"})
        expected = canonical_sha256(projection)
        if self.identity_sha256 and self.identity_sha256.strip().lower() != expected:
            raise ValueError("embedding_identity_sha256_mismatch")
        object.__setattr__(self, "identity_sha256", expected)
        return self


def _hub_cache_root() -> Path:
    explicit = os.environ.get("HUGGINGFACE_HUB_CACHE", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()
    hf_home = os.environ.get("HF_HOME", "").strip()
    if hf_home:
        return (Path(hf_home).expanduser() / "hub").resolve()
    xdg_cache = os.environ.get("XDG_CACHE_HOME", "").strip()
    if xdg_cache:
        return (Path(xdg_cache).expanduser() / "huggingface" / "hub").resolve()
    return (Path.home() / ".cache" / "huggingface" / "hub").resolve()


def _model_cache_folder(model_id: str) -> str:
    normalized = str(model_id).strip().strip("/")
    if not normalized or normalized.startswith(".") or ".." in normalized.split("/"):
        raise RetrievalLifecycleError("embedding_model_id_invalid")
    return "models--" + normalized.replace("/", "--")


def resolve_local_embedding_snapshot(
    model_id: str,
    *,
    revision: str | None = None,
    cache_root: Path | None = None,
    require_sentence_transformers_modules: bool = True,
) -> tuple[Path, str]:
    """Resolve a Hugging Face snapshot without invoking hub networking."""

    root = (cache_root or _hub_cache_root()).expanduser().resolve()
    repository = root / _model_cache_folder(model_id)
    selected_revision = str(revision or "").strip()
    if not selected_revision:
        main_ref = repository / "refs" / "main"
        if not main_ref.is_file():
            raise RetrievalLifecycleError("embedding_snapshot_ref_missing")
        try:
            selected_revision = main_ref.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError) as exc:
            raise RetrievalLifecycleError("embedding_snapshot_ref_unreadable") from exc
    if (
        len(selected_revision) != 40
        or any(ch not in "0123456789abcdefABCDEF" for ch in selected_revision)
    ):
        raise RetrievalLifecycleError("embedding_snapshot_revision_invalid")
    snapshot = (repository / "snapshots" / selected_revision).resolve()
    try:
        snapshot.relative_to(repository.resolve())
    except ValueError as exc:
        raise RetrievalLifecycleError("embedding_snapshot_scope_escape") from exc
    if not snapshot.is_dir():
        raise RetrievalLifecycleError("embedding_snapshot_missing")
    required = (
        ("config.json", "modules.json")
        if require_sentence_transformers_modules
        else ("config.json",)
    )
    if any(not (snapshot / name).is_file() for name in required):
        raise RetrievalLifecycleError("embedding_snapshot_incomplete")
    locator = (
        f"hf-cache/{_model_cache_folder(model_id)}/snapshots/"
        f"{selected_revision.lower()}"
    )
    return snapshot, locator


def _hash_file(path: Path, digest: Any) -> None:
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)


def snapshot_content_sha256(snapshot: Path) -> str:
    """Hash a snapshot tree by stable relative name and exact file content."""

    root = snapshot.resolve()
    repository_root = root.parents[1] if root.parent.name == "snapshots" else root
    digest = hashlib.sha256()
    files = sorted(
        (item for item in root.rglob("*") if item.is_file()),
        key=lambda item: item.relative_to(root).as_posix(),
    )
    if not files:
        raise RetrievalLifecycleError("embedding_snapshot_empty")
    for item in files:
        try:
            resolved = item.resolve(strict=True)
            resolved.relative_to(repository_root)
        except (OSError, ValueError) as exc:
            raise RetrievalLifecycleError("embedding_snapshot_scope_escape") from exc
        relative = item.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(item.stat().st_size.to_bytes(8, "big"))
        _hash_file(item, digest)
    return digest.hexdigest()


def snapshot_embedding_dimension(snapshot: Path) -> int:
    """Read the architecture dimension from the pinned local config."""

    try:
        payload = json.loads((snapshot / "config.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RetrievalLifecycleError("embedding_snapshot_config_invalid") from exc
    for field_name in ("sentence_embedding_dimension", "hidden_size", "d_model"):
        value = payload.get(field_name)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
    raise RetrievalLifecycleError("embedding_snapshot_dimension_missing")


def build_local_embedding_identity(
    *,
    model_id: str,
    index_dimension: int,
    revision: str | None = None,
    encoding_configuration: dict[str, Any] | None = None,
    cache_root: Path | None = None,
) -> tuple[LocalEmbeddingIdentity, Path]:
    snapshot, locator = resolve_local_embedding_snapshot(
        model_id,
        revision=revision,
        cache_root=cache_root,
        require_sentence_transformers_modules=(
            encoding_configuration is None
            or encoding_configuration.get("pooling") == "sentence_transformers"
        ),
    )
    native_embedding_dimension = snapshot_embedding_dimension(snapshot)
    configuration_sha256 = canonical_sha256(
        encoding_configuration
        or {
            "model_id": model_id,
            "revision": revision,
            "output_dimension": int(index_dimension),
            "legacy_default": True,
        }
    )
    resolved_revision = snapshot.name.lower()
    identity = LocalEmbeddingIdentity(
        embedding_model_id=str(model_id).strip(),
        embedding_model_revision=resolved_revision,
        local_snapshot_locator=locator,
        snapshot_content_sha256=snapshot_content_sha256(snapshot),
        native_embedding_dimension=native_embedding_dimension,
        embedding_dimension=int(index_dimension),
        index_dimension=int(index_dimension),
        encoding_configuration_sha256=configuration_sha256,
    )
    return identity, snapshot
