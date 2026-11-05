"""Durable publication of revision-bound frozen candidate pools.

This module is the only formal serialization boundary between Stage 2
retrieval and the Router/Compiler production chain.  It deliberately accepts
the exact protocol type rather than a mapping or compatibility wrapper.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any, Callable, Literal, Mapping

from pydantic import Field, field_validator, model_validator

from .atomic_io import bounded_path_component, temporary_sibling_path
from .pipeline_control import (
    FrozenContract,
    SubtaskRevisionRef,
    canonical_json_bytes,
    canonical_sha256,
)
from .retrieval_runtime import FrozenCandidatePoolResult


FROZEN_CANDIDATE_PUBLICATION_PROTOCOL = "sgar-candidate-pool-publication-v1"


class FrozenCandidatePublicationError(RuntimeError):
    """Raised when a frozen candidate pool cannot be published durably."""


class FrozenCandidatePoolPublication(FrozenContract):
    protocol: Literal["sgar-candidate-pool-publication-v1"] = (
        FROZEN_CANDIDATE_PUBLICATION_PROTOCOL
    )
    run_id: str = Field(min_length=1)
    revision: SubtaskRevisionRef
    contract_sha256: str
    profile_sha256: str
    candidate_pool_sha256: str
    retrieval_evidence_sha256: str
    model_accounting_reference: Mapping[str, Any] | None = None
    candidate_artifact_locator: str = Field(min_length=1)
    candidate_artifact_sha256: str
    started_event_id: str = Field(min_length=1)
    frozen_event_id: str = Field(min_length=1)
    publication_sha256: str = ""

    @field_validator(
        "contract_sha256",
        "profile_sha256",
        "candidate_pool_sha256",
        "retrieval_evidence_sha256",
        "candidate_artifact_sha256",
    )
    @classmethod
    def _validate_sha256(cls, value: str) -> str:
        normalized = str(value).strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", normalized):
            raise ValueError("candidate_publication_sha256_invalid")
        return normalized

    @field_validator("candidate_artifact_locator")
    @classmethod
    def _validate_locator(cls, value: str) -> str:
        normalized = str(value).replace("\\", "/")
        if normalized.startswith("/") or re.match(r"(?i)^[a-z]:/", normalized):
            raise ValueError("candidate_publication_locator_must_be_relative")
        if any(part in {"", ".", ".."} for part in normalized.split("/")):
            raise ValueError("candidate_publication_locator_invalid")
        return normalized

    @model_validator(mode="after")
    def _seal_publication(self) -> "FrozenCandidatePoolPublication":
        projection = self.model_dump(mode="python", exclude={"publication_sha256"})
        expected = canonical_sha256(projection)
        if self.publication_sha256:
            if self.publication_sha256.lower() != expected:
                raise ValueError("candidate_publication_identity_mismatch")
        object.__setattr__(self, "publication_sha256", expected)
        return self


FormalEventWriter = Callable[[Mapping[str, Any]], None]


def _safe_subtask_id(value: str) -> str:
    return bounded_path_component(value, fallback="subtask")


def _artifact_locator(revision: SubtaskRevisionRef) -> str:
    return (
        "candidate_pools/"
        f"{revision.graph_revision}_{_safe_subtask_id(revision.subtask_id)}_"
        f"{revision.subtask_revision}.json"
    )


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = temporary_sibling_path(path)
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _load_existing_publication(path: Path) -> FrozenCandidatePoolPublication:
    try:
        return FrozenCandidatePoolPublication.model_validate_json(
            path.read_text(encoding="utf-8-sig", errors="strict")
        )
    except Exception as exc:
        raise FrozenCandidatePublicationError(
            "candidate_publication_commit_invalid"
        ) from exc


def persist_frozen_candidate_pool(
    *,
    frozen_result: FrozenCandidatePoolResult,
    run_id: str,
    run_dir: str | Path,
    event_writer: FormalEventWriter,
) -> FrozenCandidatePoolPublication:
    """Publish one immutable candidate pool and its lifecycle evidence.

    An existing artifact without a matching commit marker is intentionally not
    reusable: a prior event or persistence step may have failed after the
    semantic work completed.
    """

    normalized_run_id = str(run_id).strip()
    if not normalized_run_id:
        raise FrozenCandidatePublicationError("candidate_publication_run_id_empty")
    root = Path(run_dir).resolve()
    revision = frozen_result.revision
    locator = _artifact_locator(revision)
    artifact_path = root / Path(locator)
    commit_path = artifact_path.with_suffix(".publication.json")
    artifact_payload = canonical_json_bytes(frozen_result.model_dump(mode="json"))
    artifact_sha256 = hashlib.sha256(artifact_payload).hexdigest()
    event_identity = {
        "run_id": normalized_run_id,
        "revision": revision.model_dump(mode="json"),
        "candidate_pool_sha256": (
            frozen_result.candidate_pool_snapshot.candidate_pool_sha256
        ),
        "retrieval_evidence_sha256": frozen_result.retrieval_evidence_sha256,
    }
    started_event_id = canonical_sha256(
        {**event_identity, "event_type": "candidate_pool_publication_started"}
    )
    frozen_event_id = canonical_sha256(
        {**event_identity, "event_type": "candidate_pool_frozen"}
    )
    expected = FrozenCandidatePoolPublication(
        run_id=normalized_run_id,
        revision=revision,
        contract_sha256=frozen_result.contract_projection.contract_sha256,
        profile_sha256=frozen_result.ideal_resource_profile.profile_sha256,
        candidate_pool_sha256=(
            frozen_result.candidate_pool_snapshot.candidate_pool_sha256
        ),
        retrieval_evidence_sha256=frozen_result.retrieval_evidence_sha256,
        model_accounting_reference=(
            frozen_result.ideal_resource_profile.model_accounting_reference
        ),
        candidate_artifact_locator=locator,
        candidate_artifact_sha256=artifact_sha256,
        started_event_id=started_event_id,
        frozen_event_id=frozen_event_id,
    )

    if commit_path.exists():
        existing = _load_existing_publication(commit_path)
        if existing != expected:
            raise FrozenCandidatePublicationError(
                "candidate_publication_commit_conflict"
            )
        if not artifact_path.is_file():
            raise FrozenCandidatePublicationError(
                "candidate_publication_artifact_missing"
            )
        if hashlib.sha256(artifact_path.read_bytes()).hexdigest() != artifact_sha256:
            raise FrozenCandidatePublicationError(
                "candidate_publication_artifact_hash_mismatch"
            )
        return existing

    if artifact_path.exists():
        raise FrozenCandidatePublicationError(
            "candidate_publication_incomplete_artifact_exists"
        )

    try:
        event_writer(
            {
                "event_type": "candidate_pool_publication_started",
                "event_id": started_event_id,
                "stage": "candidate_pool_preparation",
                **event_identity,
            }
        )
        _atomic_write_bytes(artifact_path, artifact_payload)
        event_writer(
            {
                "event_type": "candidate_pool_frozen",
                "event_id": frozen_event_id,
                "stage": "candidate_pool_preparation",
                **event_identity,
                "contract_sha256": expected.contract_sha256,
                "profile_sha256": expected.profile_sha256,
                "model_accounting_reference": expected.model_accounting_reference,
                "candidate_pool_artifact": locator,
                "candidate_pool_artifact_sha256": artifact_sha256,
                "type_quota_evidence": [
                    item.model_dump(mode="json")
                    for item in frozen_result.type_quota_evidence
                ],
            }
        )
        _atomic_write_bytes(
            commit_path,
            canonical_json_bytes(expected.model_dump(mode="json")),
        )
    except FrozenCandidatePublicationError:
        raise
    except Exception as exc:
        raise FrozenCandidatePublicationError(
            "candidate_publication_persistence_failed"
        ) from exc
    return expected


__all__ = [
    "FROZEN_CANDIDATE_PUBLICATION_PROTOCOL",
    "FrozenCandidatePoolPublication",
    "FrozenCandidatePublicationError",
    "persist_frozen_candidate_pool",
]
