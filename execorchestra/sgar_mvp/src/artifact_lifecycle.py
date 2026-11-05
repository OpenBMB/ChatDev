"""Content-addressed artifact staging and atomic committed Context visibility."""

from __future__ import annotations

from . import terminal_progress

import ast
import asyncio
import csv
import hashlib
import io
import json
import os
import shutil
import stat
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .evaluation_contracts import (
    ARTIFACT_EVENT_PROTOCOL,
    ArtifactRevisionRef,
    ArtifactTreeEntry,
    ArtifactRepresentation,
    CommittedArtifactManifest,
    CommittedContextSnapshot,
    EvaluationContractError,
    EvaluationDecision,
    EvaluationVerdict,
    FinalArtifactCandidate,
    FinalArtifactCandidateV2,
    MachineContractEvidence,
    QuarantinedArtifactManifest,
    StagedArtifactManifest,
    VerifiedArtifactManifest,
    assert_evaluation_projection_safe,
)
from .artifact_v2 import (
    ArtifactV2Error,
    descriptor_for_bytes,
    descriptor_for_path,
    machine_evidence_for_descriptor,
)
from .pipeline_control import (
    SubtaskRevisionRef,
    canonical_json_bytes,
    canonical_sha256,
    subtask_revision_identity_sha256,
)
from .terminal_failure import TerminalFailureEnvelope


class ArtifactLifecycleError(RuntimeError):
    pass


class ArtifactPersistenceError(ArtifactLifecycleError):
    pass


def _short_atomic_sibling(target: Path) -> Path:
    """Return a short same-directory temporary path for atomic replacement.

    Content-addressed targets and manifest names are intentionally long.  A
    temporary name must not repeat that identity: doing so can push an
    otherwise valid nested artifact beyond the legacy Windows path limit.
    Keeping the temporary object in the same directory preserves same-volume
    atomic rename semantics.
    """

    return target.parent / (".sgar-tmp-" + uuid.uuid4().hex[:12])


class MachineContractFailure(ArtifactLifecycleError):
    def __init__(self, failure_code: str, evidence: MachineContractEvidence) -> None:
        super().__init__(failure_code)
        self.failure_code = failure_code
        self.evidence = evidence


def raw_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _mime_type(artifact_type: str) -> str:
    return {
        "code": "text/x-python",
        "json": "application/json",
        "csv": "text/csv",
        "markdown": "text/markdown",
        "plaintext": "text/plain",
    }.get(artifact_type, "application/octet-stream")


def validate_machine_contract(
    *,
    content: bytes,
    artifact_type: str,
    extension: str = "",
    required_produced_files_present: bool = True,
    handles_valid: bool = True,
) -> MachineContractEvidence:
    check_ids = ["artifact_type", "content_hash", "required_produced_files", "artifact_handles"]
    evidence_ids = ["machine:artifact_type", "machine:content_hash"]
    failures: list[str] = []
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = ""
        failures.append("artifact_not_utf8")
    if artifact_type == "json" and not failures:
        check_ids.append("json_parse")
        try:
            json.loads(text)
            evidence_ids.append("machine:json_parse")
        except json.JSONDecodeError:
            failures.append("artifact_json_invalid")
    elif artifact_type == "csv" and not failures:
        check_ids.append("csv_parse")
        try:
            rows = list(csv.reader(io.StringIO(text)))
            if not rows:
                raise ValueError("empty")
            evidence_ids.append("machine:csv_parse")
        except (csv.Error, ValueError):
            failures.append("artifact_csv_invalid")
    elif artifact_type == "code" and not failures:
        check_ids.append("code_parse")
        normalized_extension = str(extension or "").strip().lower()
        # `code` is a semantic category, not a Python-language assertion.
        # Python keeps its AST check; other declared source languages are
        # validated for UTF-8/non-empty delivery here and must be checked by
        # their selected deterministic compiler or official verifier.
        if normalized_extension in {".v", ".ml", ".mli", ".hs", ".rs", ".go", ".java", ".c", ".h", ".cpp", ".cc"}:
            evidence_ids.append("machine:code_parse")
        else:
            try:
                ast.parse(text)
                evidence_ids.append("machine:code_parse")
            except SyntaxError:
                failures.append("artifact_code_invalid")
    elif artifact_type not in {"markdown", "plaintext", "json", "csv", "code"}:
        failures.append("artifact_type_unsupported")
    if not required_produced_files_present:
        failures.append("required_produced_file_missing")
    else:
        evidence_ids.append("machine:required_produced_files")
    if not handles_valid:
        failures.append("artifact_handle_invalid")
    else:
        evidence_ids.append("machine:artifact_handles")
    evidence = MachineContractEvidence(
        status="fail" if failures else "pass",
        check_ids=tuple(check_ids),
        evidence_ids=tuple(evidence_ids),
    )
    if failures:
        raise MachineContractFailure(failures[0], evidence)
    return evidence


def build_final_artifact_candidate(
    *,
    artifact_revision: ArtifactRevisionRef,
    content: bytes,
    artifact_type: str,
    extension: str,
    logical_locator: str,
    output_contract_sha256: str,
    candidate_pool_sha256: str,
    execution_result_sha256: str,
    plan_sha256: str | None,
    recovery_operation_sha256: str | None,
    provenance_source_ids: Sequence[str],
    execution_event_ids: Sequence[str] = (),
    source_handle_ids: Sequence[str] = (),
    required_produced_files_present: bool = True,
    handles_valid: bool = True,
) -> FinalArtifactCandidate:
    machine = validate_machine_contract(
        content=content,
        artifact_type=artifact_type,
        extension=extension,
        required_produced_files_present=required_produced_files_present,
        handles_valid=handles_valid,
    )
    return FinalArtifactCandidate(
        artifact_revision=artifact_revision,
        execution_result_sha256=execution_result_sha256,
        content_sha256=raw_sha256(content),
        byte_size=len(content),
        artifact_type=artifact_type,
        extension=extension,
        mime_type=_mime_type(artifact_type),
        logical_locator=logical_locator,
        output_contract_sha256=output_contract_sha256,
        candidate_pool_sha256=candidate_pool_sha256,
        plan_sha256=plan_sha256,
        recovery_operation_sha256=recovery_operation_sha256,
        execution_event_ids=tuple(execution_event_ids),
        source_handle_ids=tuple(source_handle_ids),
        provenance_source_ids=tuple(provenance_source_ids),
        machine_contract_status=machine,
    )


class ArtifactEventLedger:
    def __init__(self, *, artifacts_dir: Path, run_id: str) -> None:
        self.artifacts_dir = artifacts_dir
        self.run_id = str(run_id).strip()
        if not self.run_id:
            raise ArtifactPersistenceError("artifact_run_id_empty")
        self.events_path = artifacts_dir / "artifact_events.jsonl"
        self.context_events_path = artifacts_dir / "context_commits.jsonl"
        self.summary_path = artifacts_dir / "artifact_summary.json"
        self.context_summary_path = artifacts_dir / "context_summary.json"
        self._events: list[dict[str, Any]] = []
        self._context_events: list[dict[str, Any]] = []
        self._lock = threading.RLock()
        for path in (self.events_path, self.context_events_path):
            if path.exists() and path.stat().st_size:
                raise ArtifactPersistenceError("artifact_ledger_already_exists")
        self.write_summaries()

    def _append(self, path: Path, target: list[dict[str, Any]], event: dict[str, Any]) -> dict[str, Any]:
        assert_evaluation_projection_safe(event)
        serialized = canonical_json_bytes(event).decode("utf-8")
        with self._lock:
            try:
                with path.open("a", encoding="utf-8", newline="\n") as handle:
                    handle.write(serialized + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
            except OSError as exc:
                raise ArtifactPersistenceError("artifact_event_write_failed") from exc
            target.append(event)
            self.write_summaries()
        return dict(event)

    def append_artifact(self, event_type: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._append(
            self.events_path,
            self._events,
            {
                "schema_version": ARTIFACT_EVENT_PROTOCOL,
                "event_type": str(event_type),
                "event_id": uuid.uuid4().hex,
                "run_id": self.run_id,
                **dict(payload),
            },
        )

    def append_context(self, event_type: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._append(
            self.context_events_path,
            self._context_events,
            {
                "schema_version": "sgar-context-commit-v1",
                "event_type": str(event_type),
                "event_id": uuid.uuid4().hex,
                "run_id": self.run_id,
                **dict(payload),
            },
        )

    def artifact_summary(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        staged: set[str] = set()
        terminal: set[str] = set()
        for event in self._events:
            event_type = str(event.get("event_type") or "")
            counts[event_type] = counts.get(event_type, 0) + 1
            ref = str(event.get("artifact_revision_sha256") or "")
            if event_type == "artifact_stage_started" and ref:
                staged.add(ref)
            if event_type in {
                "artifact_staged",
                "artifact_quarantined",
                "artifact_committed",
                "artifact_stage_interrupted",
            } and ref:
                terminal.add(ref)
        return {
            "schema_version": ARTIFACT_EVENT_PROTOCOL,
            "run_id": self.run_id,
            "event_count": len(self._events),
            "event_counts": counts,
            "unmatched_artifact_operations": sorted(staged - terminal),
            "ledger_sha256": canonical_sha256(self._events),
        }

    def context_summary(self) -> dict[str, Any]:
        started = {
            str(item.get("artifact_revision_sha256"))
            for item in self._context_events
            if item.get("event_type") == "artifact_commit_started"
        }
        committed = {
            str(item.get("artifact_revision_sha256"))
            for item in self._context_events
            if item.get("event_type") == "artifact_committed"
        }
        interrupted = {
            str(item.get("artifact_revision_sha256"))
            for item in self._context_events
            if item.get("event_type") == "artifact_commit_interrupted"
        }
        return {
            "schema_version": "sgar-context-commit-v1",
            "run_id": self.run_id,
            "event_count": len(self._context_events),
            "unmatched_context_commits": sorted(started - committed - interrupted),
            "interrupted_context_commits": sorted(interrupted),
            "ledger_sha256": canonical_sha256(self._context_events),
        }

    def durable_committed_identities(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    str(item.get("artifact_revision_sha256") or "")
                    for item in self._context_events
                    if item.get("event_type") == "artifact_committed"
                    and item.get("artifact_revision_sha256")
                }
            )
        )

    @staticmethod
    def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
        temporary = _short_atomic_sibling(path)
        try:
            with temporary.open("xb") as handle:
                handle.write(canonical_json_bytes(payload))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except OSError as exc:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise ArtifactPersistenceError("artifact_summary_write_failed") from exc

    def write_summaries(self) -> None:
        self._atomic_json(self.summary_path, self.artifact_summary())
        self._atomic_json(self.context_summary_path, self.context_summary())

    def close(self) -> tuple[dict[str, Any], dict[str, Any]]:
        artifact_summary = self.artifact_summary()
        for identity in artifact_summary["unmatched_artifact_operations"]:
            self.append_artifact(
                "artifact_stage_interrupted",
                {
                    "artifact_revision_sha256": identity,
                    "failure_code": "artifact_normal_shutdown_interrupted",
                },
            )
        context_summary = self.context_summary()
        for identity in context_summary["unmatched_context_commits"]:
            self.append_context(
                "artifact_commit_interrupted",
                {
                    "artifact_revision_sha256": identity,
                    "failure_code": "context_commit_normal_shutdown_interrupted",
                },
            )
        self.write_summaries()
        return self.artifact_summary(), self.context_summary()


def _is_reparse(path: Path) -> bool:
    try:
        value = path.lstat()
    except OSError as exc:
        raise ArtifactLifecycleError("artifact_path_unreadable") from exc
    return bool(
        stat.S_ISLNK(value.st_mode)
        or int(getattr(value, "st_file_attributes", 0)) & 0x400
    )


def _assert_no_reparse_components(path: Path) -> None:
    """Reject a source reached through any symlink/junction/reparse component."""

    absolute = path.absolute()
    chain: list[Path] = []
    cursor = absolute
    while cursor != cursor.parent:
        chain.append(cursor)
        cursor = cursor.parent
    for component in reversed(chain):
        if component.exists() and _is_reparse(component):
            raise ArtifactLifecycleError("artifact_path_reparse_forbidden")


def _tree_entries(path: Path) -> tuple[tuple[ArtifactTreeEntry, ...], int]:
    root = path.resolve()
    entries: list[ArtifactTreeEntry] = []
    total = 0
    for child in sorted(path.rglob("*"), key=lambda item: item.relative_to(path).as_posix()):
        _assert_no_reparse_components(child)
        if child.is_dir():
            continue
        resolved = child.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ArtifactLifecycleError("artifact_tree_scope_escape") from exc
        content = child.read_bytes()
        entries.append(
            ArtifactTreeEntry(
                relative_path=child.relative_to(path).as_posix(),
                content_sha256=raw_sha256(content),
                byte_size=len(content),
            )
        )
        total += len(content)
    return tuple(entries), total


class ArtifactLifecycleStore:
    def __init__(self, *, output_dir: str | Path, run_id: str) -> None:
        self.output_dir = Path(output_dir).resolve()
        self.artifacts_dir = self.output_dir / "artifacts"
        self.blobs_dir = self.artifacts_dir / "blobs"
        self.manifests_dir = self.artifacts_dir / "manifests"
        self.quarantined_dir = self.artifacts_dir / "quarantined"
        try:
            for path in (
                self.blobs_dir,
                self.manifests_dir,
                self.quarantined_dir,
            ):
                path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ArtifactPersistenceError("artifact_store_initialization_failed") from exc
        self.ledger = ArtifactEventLedger(artifacts_dir=self.artifacts_dir, run_id=run_id)
        self._lock = threading.RLock()
        self._staged: dict[str, StagedArtifactManifest] = {}
        self._verified: dict[str, VerifiedArtifactManifest] = {}
        self._quarantined: dict[str, QuarantinedArtifactManifest] = {}

    def _write_blob(self, content: bytes, content_sha256: str) -> str:
        if raw_sha256(content) != content_sha256:
            raise ArtifactLifecycleError("artifact_content_hash_mismatch")
        target = self.blobs_dir / content_sha256
        locator = target.relative_to(self.output_dir).as_posix()
        if target.exists():
            if raw_sha256(target.read_bytes()) != content_sha256:
                raise ArtifactPersistenceError("artifact_existing_blob_hash_mismatch")
            return locator
        temporary = _short_atomic_sibling(target)
        try:
            with temporary.open("xb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        except OSError as exc:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise ArtifactPersistenceError("artifact_blob_write_failed") from exc
        return locator

    def _write_manifest(self, name: str, payload: Mapping[str, Any]) -> Path:
        target = self.manifests_dir / name
        serialized = canonical_json_bytes(payload)
        if target.exists():
            if target.read_bytes() == serialized:
                return target
            raise ArtifactPersistenceError("artifact_manifest_hash_conflict")
        temporary = _short_atomic_sibling(target)
        try:
            with temporary.open("xb") as handle:
                handle.write(serialized)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        except OSError as exc:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise ArtifactPersistenceError("artifact_manifest_write_failed") from exc
        return target

    def _write_tree_v2(self, source: Path, identity_sha256: str) -> str:
        """Copy one directory/bundle without dropping empty directories."""

        target = self.blobs_dir / identity_sha256
        locator = target.relative_to(self.output_dir).as_posix()
        if target.exists():
            if not target.is_dir():
                raise ArtifactPersistenceError("artifact_v2_existing_tree_kind_mismatch")
            return locator
        temporary = _short_atomic_sibling(target)
        try:
            temporary.mkdir()
            for item in sorted(source.rglob("*"), key=lambda value: value.relative_to(source).as_posix()):
                _assert_no_reparse_components(item)
                destination = temporary / item.relative_to(source)
                if item.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                if not item.is_file():
                    raise ArtifactLifecycleError("artifact_v2_tree_entry_kind_unsupported")
                destination.parent.mkdir(parents=True, exist_ok=True)
                with item.open("rb") as source_handle, destination.open("xb") as target_handle:
                    shutil.copyfileobj(source_handle, target_handle, length=1024 * 1024)
                    target_handle.flush()
                    os.fsync(target_handle.fileno())
            os.replace(temporary, target)
        except (OSError, ArtifactLifecycleError) as exc:
            shutil.rmtree(temporary, ignore_errors=True)
            if isinstance(exc, ArtifactLifecycleError):
                raise
            raise ArtifactPersistenceError("artifact_v2_tree_write_failed") from exc
        return locator

    def stage_v2(
        self,
        *,
        candidate: FinalArtifactCandidateV2,
        content: bytes | None = None,
        source_path: str | Path | None = None,
        accounting_operation_ids: Sequence[str] = (),
    ) -> StagedArtifactManifest:
        """Stage bytes, a file, a directory, or a bundle as one immutable unit."""

        descriptor = candidate.descriptor
        identity = candidate.artifact_revision.revision_sha256
        if (content is None) == (source_path is None):
            raise ArtifactLifecycleError("artifact_v2_exactly_one_source_required")
        source: Path | None = None
        if source_path is not None:
            source = Path(source_path).absolute()
            _assert_no_reparse_components(source)
            if not source.exists():
                raise ArtifactLifecycleError("artifact_v2_source_missing")
        if descriptor.representation in {
            ArtifactRepresentation.INLINE_TEXT,
            ArtifactRepresentation.FILE,
        }:
            raw = content if content is not None else source.read_bytes() if source is not None else b""
            observed = descriptor_for_bytes(
                raw,
                representation=descriptor.representation,
                format_id=descriptor.format_id,
                extension=descriptor.extension,
                logical_locator=descriptor.logical_locator,
                provenance_source_ids=descriptor.provenance_source_ids,
            )
            if observed.descriptor_sha256 != descriptor.descriptor_sha256:
                raise ArtifactLifecycleError("artifact_v2_source_descriptor_mismatch")
            storage_sha = descriptor.content_sha256 or ""
            locator = self._write_blob(raw, storage_sha)
            tree_entries: tuple[ArtifactTreeEntry, ...] = ()
        else:
            if source is None or not source.is_dir():
                raise ArtifactLifecycleError("artifact_v2_directory_source_required")
            observed = descriptor_for_path(
                source,
                format_id=descriptor.format_id,
                extension=descriptor.extension,
                logical_locator=descriptor.logical_locator,
                provenance_source_ids=descriptor.provenance_source_ids,
                as_bundle=descriptor.representation is ArtifactRepresentation.BUNDLE,
                primary_member=descriptor.primary_member,
                required_members=(item.relative_path for item in descriptor.members if item.required),
            )
            if observed.descriptor_sha256 != descriptor.descriptor_sha256:
                raise ArtifactLifecycleError("artifact_v2_source_descriptor_mismatch")
            storage_sha = descriptor.bundle_sha256 or descriptor.tree_sha256 or ""
            locator = self._write_tree_v2(source, storage_sha)
            tree_entries = tuple(
                ArtifactTreeEntry(
                    relative_path=item.relative_path,
                    content_sha256=item.content_sha256,
                    byte_size=item.byte_size,
                )
                for item in descriptor.members
                if item.representation == "file" and item.content_sha256 is not None
            )
        with self._lock:
            existing = self._staged.get(identity)
            if existing is not None:
                if existing.artifact_v2 != descriptor:
                    raise ArtifactLifecycleError("artifact_v2_revision_content_conflict")
                return existing
            self.ledger.append_artifact(
                "artifact_stage_started",
                {
                    "artifact_revision_sha256": identity,
                    "candidate_sha256": candidate.candidate_sha256,
                    "content_sha256": storage_sha,
                    "artifact_descriptor_sha256": descriptor.descriptor_sha256,
                },
            )
            machine = machine_evidence_for_descriptor(descriptor)
            manifest = StagedArtifactManifest(
                artifact_revision=candidate.artifact_revision,
                candidate_sha256=candidate.candidate_sha256,
                artifact_type=descriptor.format_id,
                content_sha256=storage_sha,
                tree_sha256=descriptor.tree_sha256,
                tree_entries=tree_entries,
                byte_size=descriptor.byte_size,
                mime_type=descriptor.media_type,
                extension=descriptor.extension,
                logical_locator=descriptor.logical_locator,
                blob_locator=locator,
                output_contract_sha256=candidate.output_contract_sha256,
                execution_result_sha256=candidate.execution_result_sha256,
                candidate_pool_sha256=candidate.candidate_pool_sha256,
                plan_sha256=candidate.plan_sha256,
                recovery_operation_sha256=candidate.recovery_operation_sha256,
                source_handle_ids=candidate.source_handle_ids,
                provenance_source_ids=descriptor.provenance_source_ids,
                execution_event_ids=candidate.execution_event_ids,
                accounting_operation_ids=tuple(accounting_operation_ids),
                machine_evidence_sha256=machine.evidence_sha256,
                artifact_v2=descriptor,
            )
            self._write_manifest(
                f"{identity}.staged.json", manifest.model_dump(mode="json")
            )
            self.ledger.append_artifact(
                "artifact_staged",
                {
                    "artifact_revision_sha256": identity,
                    "staged_manifest_sha256": manifest.manifest_sha256,
                    "content_sha256": storage_sha,
                    "artifact_descriptor_sha256": descriptor.descriptor_sha256,
                    "visibility": "staged",
                },
            )
            self._staged[identity] = manifest
            terminal_progress.artifact("Generated; awaiting evaluation", manifest)
            return manifest

    def stage_bytes(
        self,
        *,
        candidate: FinalArtifactCandidate,
        content: bytes,
        accounting_operation_ids: Sequence[str] = (),
    ) -> StagedArtifactManifest:
        identity = candidate.artifact_revision.revision_sha256
        with self._lock:
            if identity in self._staged:
                existing = self._staged[identity]
                if existing.content_sha256 != candidate.content_sha256:
                    raise ArtifactLifecycleError("artifact_revision_content_conflict")
                return existing
            self.ledger.append_artifact(
                "artifact_stage_started",
                {
                    "artifact_revision_sha256": identity,
                    "candidate_sha256": candidate.candidate_sha256,
                    "content_sha256": candidate.content_sha256,
                },
            )
            locator = self._write_blob(content, candidate.content_sha256)
            manifest = StagedArtifactManifest(
                artifact_revision=candidate.artifact_revision,
                candidate_sha256=candidate.candidate_sha256,
                artifact_type=candidate.artifact_type,
                content_sha256=candidate.content_sha256,
                byte_size=len(content),
                mime_type=candidate.mime_type,
                extension=candidate.extension,
                logical_locator=candidate.logical_locator,
                blob_locator=locator,
                output_contract_sha256=candidate.output_contract_sha256,
                execution_result_sha256=candidate.execution_result_sha256,
                candidate_pool_sha256=candidate.candidate_pool_sha256,
                plan_sha256=candidate.plan_sha256,
                recovery_operation_sha256=candidate.recovery_operation_sha256,
                source_handle_ids=candidate.source_handle_ids,
                provenance_source_ids=candidate.provenance_source_ids,
                execution_event_ids=candidate.execution_event_ids,
                accounting_operation_ids=tuple(accounting_operation_ids),
                machine_evidence_sha256=candidate.machine_contract_status.evidence_sha256,
            )
            self._write_manifest(
                f"{identity}.staged.json",
                manifest.model_dump(mode="json"),
            )
            self.ledger.append_artifact(
                "artifact_staged",
                {
                    "artifact_revision_sha256": identity,
                    "staged_manifest_sha256": manifest.manifest_sha256,
                    "content_sha256": manifest.content_sha256,
                    "visibility": "staged",
                },
            )
            self._staged[identity] = manifest
            terminal_progress.artifact("Generated; awaiting evaluation", manifest)
            return manifest

    def stage_path(
        self,
        *,
        candidate: FinalArtifactCandidate,
        source_path: str | Path,
        accounting_operation_ids: Sequence[str] = (),
    ) -> StagedArtifactManifest:
        path = Path(source_path).absolute()
        _assert_no_reparse_components(path)
        if path.is_file():
            return self.stage_bytes(
                candidate=candidate,
                content=path.read_bytes(),
                accounting_operation_ids=accounting_operation_ids,
            )
        if not path.is_dir():
            raise ArtifactLifecycleError("artifact_path_kind_invalid")
        entries, total = _tree_entries(path)
        tree_sha = canonical_sha256([item.model_dump(mode="json") for item in entries])
        target = self.blobs_dir / tree_sha
        if target.exists():
            if not target.is_dir():
                raise ArtifactPersistenceError("artifact_existing_tree_kind_mismatch")
            existing_entries, _ = _tree_entries(target)
            existing_sha = canonical_sha256(
                [item.model_dump(mode="json") for item in existing_entries]
            )
            if existing_sha != tree_sha:
                raise ArtifactPersistenceError("artifact_existing_tree_hash_mismatch")
        else:
            temporary = _short_atomic_sibling(target)
            try:
                temporary.mkdir()
                for entry in entries:
                    source = path / entry.relative_path
                    destination = temporary / entry.relative_path
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with destination.open("xb") as handle:
                        handle.write(source.read_bytes())
                        handle.flush()
                        os.fsync(handle.fileno())
                os.replace(temporary, target)
            except OSError as exc:
                shutil.rmtree(temporary, ignore_errors=True)
                raise ArtifactPersistenceError("artifact_tree_write_failed") from exc
        identity = candidate.artifact_revision.revision_sha256
        self.ledger.append_artifact(
            "artifact_stage_started",
            {
                "artifact_revision_sha256": identity,
                "candidate_sha256": candidate.candidate_sha256,
                "content_sha256": tree_sha,
            },
        )
        manifest = StagedArtifactManifest(
            artifact_revision=candidate.artifact_revision,
            candidate_sha256=candidate.candidate_sha256,
            artifact_type=candidate.artifact_type,
            content_sha256=tree_sha,
            tree_sha256=tree_sha,
            tree_entries=tuple(entries),
            byte_size=total,
            mime_type="application/vnd.sgar.directory",
            extension=candidate.extension,
            logical_locator=candidate.logical_locator,
            blob_locator=target.relative_to(self.output_dir).as_posix(),
            output_contract_sha256=candidate.output_contract_sha256,
            execution_result_sha256=candidate.execution_result_sha256,
            candidate_pool_sha256=candidate.candidate_pool_sha256,
            plan_sha256=candidate.plan_sha256,
            recovery_operation_sha256=candidate.recovery_operation_sha256,
            source_handle_ids=candidate.source_handle_ids,
            provenance_source_ids=candidate.provenance_source_ids,
            execution_event_ids=candidate.execution_event_ids,
            accounting_operation_ids=tuple(accounting_operation_ids),
            machine_evidence_sha256=candidate.machine_contract_status.evidence_sha256,
        )
        self._write_manifest(f"{identity}.staged.json", manifest.model_dump(mode="json"))
        self.ledger.append_artifact(
            "artifact_staged",
            {
                "artifact_revision_sha256": identity,
                "staged_manifest_sha256": manifest.manifest_sha256,
                "content_sha256": manifest.content_sha256,
                "visibility": "staged",
            },
        )
        self._staged[identity] = manifest
        terminal_progress.artifact("Generated; awaiting evaluation", manifest)
        return manifest

    def read_bytes(self, manifest: StagedArtifactManifest | CommittedArtifactManifest) -> bytes:
        path = (self.output_dir / manifest.blob_locator).resolve()
        try:
            path.relative_to(self.blobs_dir)
        except ValueError as exc:
            raise ArtifactLifecycleError("artifact_blob_locator_escape") from exc
        if not path.is_file():
            raise ArtifactLifecycleError("artifact_blob_not_file")
        content = path.read_bytes()
        if raw_sha256(content) != manifest.content_sha256:
            raise ArtifactLifecycleError("artifact_blob_hash_drift")
        return content

    def artifact_path(
        self, manifest: StagedArtifactManifest | CommittedArtifactManifest
    ) -> Path:
        path = (self.output_dir / manifest.blob_locator).resolve()
        try:
            path.relative_to(self.blobs_dir)
        except ValueError as exc:
            raise ArtifactLifecycleError("artifact_blob_locator_escape") from exc
        return path

    def validate_manifest_content(
        self, manifest: StagedArtifactManifest | CommittedArtifactManifest
    ) -> None:
        path = self.artifact_path(manifest)
        descriptor = manifest.artifact_v2
        if descriptor is None:
            if path.is_file():
                if raw_sha256(path.read_bytes()) != manifest.content_sha256:
                    raise ArtifactLifecycleError("artifact_blob_hash_drift")
                return
            if path.is_dir():
                entries, _ = _tree_entries(path)
                if canonical_sha256(
                    [item.model_dump(mode="json") for item in entries]
                ) != manifest.content_sha256:
                    raise ArtifactLifecycleError("artifact_tree_hash_drift")
                return
            raise ArtifactLifecycleError("artifact_blob_missing")
        try:
            if descriptor.representation in {
                ArtifactRepresentation.INLINE_TEXT,
                ArtifactRepresentation.FILE,
            }:
                if not path.is_file():
                    raise ArtifactLifecycleError("artifact_v2_blob_kind_drift")
                observed = descriptor_for_bytes(
                    path.read_bytes(),
                    representation=descriptor.representation,
                    format_id=descriptor.format_id,
                    extension=descriptor.extension,
                    logical_locator=descriptor.logical_locator,
                    provenance_source_ids=descriptor.provenance_source_ids,
                )
            else:
                if not path.is_dir():
                    raise ArtifactLifecycleError("artifact_v2_blob_kind_drift")
                observed = descriptor_for_path(
                    path,
                    format_id=descriptor.format_id,
                    extension=descriptor.extension,
                    logical_locator=descriptor.logical_locator,
                    provenance_source_ids=descriptor.provenance_source_ids,
                    as_bundle=descriptor.representation is ArtifactRepresentation.BUNDLE,
                    primary_member=descriptor.primary_member,
                    required_members=(item.relative_path for item in descriptor.members if item.required),
                )
        except ArtifactV2Error as exc:
            raise ArtifactLifecycleError("artifact_v2_content_validation_failed") from exc
        if observed.descriptor_sha256 != descriptor.descriptor_sha256:
            raise ArtifactLifecycleError("artifact_v2_content_hash_drift")

    def verify(
        self,
        *,
        manifest: StagedArtifactManifest,
        decision: EvaluationDecision,
    ) -> VerifiedArtifactManifest:
        if decision.verdict is not EvaluationVerdict.PASS:
            raise EvaluationContractError("only_pass_decision_can_verify_artifact")
        if decision.artifact_manifest_sha256 != manifest.manifest_sha256:
            raise EvaluationContractError("verification_artifact_identity_mismatch")
        try:
            self.validate_manifest_content(manifest)
        except ArtifactLifecycleError as exc:
            raise ArtifactLifecycleError("artifact_content_changed_after_evaluation") from exc
        event = self.ledger.append_artifact(
            "artifact_verified",
            {
                "artifact_revision_sha256": manifest.artifact_revision.revision_sha256,
                "staged_manifest_sha256": manifest.manifest_sha256,
                "evaluation_decision_sha256": decision.decision_sha256,
                "content_sha256": manifest.content_sha256,
            },
        )
        verified = VerifiedArtifactManifest(
            artifact_revision=manifest.artifact_revision,
            staged_manifest_sha256=manifest.manifest_sha256,
            evaluation_decision_sha256=decision.decision_sha256,
            machine_evidence_sha256=manifest.machine_evidence_sha256,
            verified_content_sha256=manifest.content_sha256,
            verification_event_id=event["event_id"],
        )
        self._write_manifest(
            f"{manifest.artifact_revision.revision_sha256}.verified.json",
            verified.model_dump(mode="json"),
        )
        self._verified[manifest.artifact_revision.revision_sha256] = verified
        terminal_progress.artifact("Accepted; awaiting submission", manifest)
        return verified

    def quarantine(
        self,
        *,
        manifest: StagedArtifactManifest,
        reason_code: str,
        final_decision: EvaluationDecision | None,
    ) -> QuarantinedArtifactManifest:
        quarantined = QuarantinedArtifactManifest(
            artifact_revision=manifest.artifact_revision,
            staged_manifest_sha256=manifest.manifest_sha256,
            final_decision_sha256=(final_decision.decision_sha256 if final_decision else None),
            reason_code=reason_code,
        )
        target = self.quarantined_dir / (
            manifest.artifact_revision.revision_sha256 + ".json"
        )
        serialized = canonical_json_bytes(quarantined.model_dump(mode="json"))
        if target.exists() and target.read_bytes() != serialized:
            raise ArtifactPersistenceError("artifact_quarantine_hash_conflict")
        if not target.exists():
            temporary = _short_atomic_sibling(target)
            try:
                with temporary.open("xb") as handle:
                    handle.write(serialized)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, target)
            except OSError as exc:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
                raise ArtifactPersistenceError("artifact_quarantine_write_failed") from exc
        self.ledger.append_artifact(
            "artifact_quarantined",
            {
                "artifact_revision_sha256": manifest.artifact_revision.revision_sha256,
                "staged_manifest_sha256": manifest.manifest_sha256,
                "reason_code": reason_code,
                "quarantine_sha256": quarantined.quarantine_sha256,
            },
        )
        self._quarantined[manifest.artifact_revision.revision_sha256] = quarantined
        terminal_progress.artifact("Withheld", manifest, reason_code)
        return quarantined


class ContextCommitStore:
    def __init__(self, *, artifact_store: ArtifactLifecycleStore) -> None:
        self.artifact_store = artifact_store
        self._committed: dict[str, CommittedArtifactManifest] = {}
        self._by_subtask_revision: dict[tuple[str, int, str, int], str] = {}
        self._dependency_events: dict[str, threading.Event] = {}
        self._lock = threading.RLock()
        self._restore_durable_commits()

    @staticmethod
    def _key(ref: ArtifactRevisionRef) -> tuple[str, int, str, int]:
        revision = ref.subtask_revision
        return (
            ref.run_id,
            revision.graph_revision,
            revision.subtask_id,
            revision.subtask_revision,
        )

    def _restore_durable_commits(self) -> None:
        """Rebuild visibility only from a manifest with a durable terminal event."""

        for identity in self.artifact_store.ledger.durable_committed_identities():
            if not identity:
                continue
            path = self.artifact_store.manifests_dir / f"{identity}.committed.json"
            if not path.is_file():
                raise ArtifactPersistenceError("committed_event_manifest_missing")
            try:
                manifest = CommittedArtifactManifest.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
            except (OSError, ValueError) as exc:
                raise ArtifactPersistenceError("committed_manifest_invalid") from exc
            if manifest.artifact_revision.revision_sha256 != identity:
                raise ArtifactPersistenceError("committed_manifest_identity_mismatch")
            if manifest.artifact_revision.run_id != self.artifact_store.ledger.run_id:
                raise ArtifactPersistenceError("committed_manifest_cross_run")
            try:
                self.artifact_store.validate_manifest_content(manifest)
            except ArtifactLifecycleError as exc:
                raise ArtifactPersistenceError("committed_artifact_hash_drift") from exc
            key = self._key(manifest.artifact_revision)
            existing = self._by_subtask_revision.get(key)
            if existing and existing != identity:
                raise ArtifactPersistenceError("multiple_commits_for_subtask_revision")
            self._committed[identity] = manifest
            self._by_subtask_revision[key] = identity
            self._dependency_events.setdefault(identity, threading.Event()).set()

    def commit(
        self,
        *,
        staged: StagedArtifactManifest,
        verified: VerifiedArtifactManifest,
        decision: EvaluationDecision,
    ) -> CommittedArtifactManifest:
        if verified.staged_manifest_sha256 != staged.manifest_sha256:
            raise ArtifactLifecycleError("commit_staged_verified_mismatch")
        if verified.evaluation_decision_sha256 != decision.decision_sha256:
            raise ArtifactLifecycleError("commit_verified_decision_mismatch")
        if decision.verdict is not EvaluationVerdict.PASS:
            raise ArtifactLifecycleError("commit_requires_pass_decision")
        identity = staged.artifact_revision.revision_sha256
        key = self._key(staged.artifact_revision)
        with self._lock:
            existing = self._committed.get(identity)
            if existing is not None:
                return existing
            conflict = self._by_subtask_revision.get(key)
            if conflict and conflict != identity:
                raise ArtifactLifecycleError("context_revision_already_committed")
            self.artifact_store.ledger.append_context(
                "artifact_commit_started",
                {
                    "artifact_revision_sha256": identity,
                    "staged_manifest_sha256": staged.manifest_sha256,
                    "verified_manifest_sha256": verified.verified_manifest_sha256,
                },
            )
            commit_event_id = uuid.uuid4().hex
            committed = CommittedArtifactManifest(
                artifact_revision=staged.artifact_revision,
                staged_manifest_sha256=staged.manifest_sha256,
                verified_manifest_sha256=verified.verified_manifest_sha256,
                evaluation_decision_sha256=decision.decision_sha256,
                content_sha256=staged.content_sha256,
                blob_locator=staged.blob_locator,
                logical_locator=staged.logical_locator,
                artifact_type=staged.artifact_type,
                extension=staged.extension,
                mime_type=staged.mime_type,
                byte_size=staged.byte_size,
                output_contract_sha256=staged.output_contract_sha256,
                candidate_pool_sha256=staged.candidate_pool_sha256,
                plan_sha256=staged.plan_sha256,
                recovery_operation_sha256=staged.recovery_operation_sha256,
                source_handle_ids=staged.source_handle_ids,
                provenance_source_ids=staged.provenance_source_ids,
                execution_event_ids=staged.execution_event_ids,
                accounting_operation_ids=staged.accounting_operation_ids,
                artifact_v2=staged.artifact_v2,
                commit_event_id=commit_event_id,
            )
            self.artifact_store._write_manifest(
                f"{identity}.committed.json",
                committed.model_dump(mode="json"),
            )
            self.artifact_store.ledger.append_context(
                "artifact_committed",
                {
                    "event_id": commit_event_id,
                    "artifact_revision_sha256": identity,
                    "committed_manifest_sha256": committed.committed_manifest_sha256,
                    "content_sha256": committed.content_sha256,
                },
            )
            self.artifact_store.ledger.append_artifact(
                "artifact_committed",
                {
                    "artifact_revision_sha256": identity,
                    "committed_manifest_sha256": committed.committed_manifest_sha256,
                    "content_sha256": committed.content_sha256,
                    "visibility": "committed",
                },
            )
            # Only after the committed manifest and terminal event are durable
            # does in-memory Context become visible.
            self._committed[identity] = committed
            self._by_subtask_revision[key] = identity
            self._dependency_events.setdefault(identity, threading.Event()).set()
            terminal_progress.artifact("Committed; available to downstream tasks", committed)
            return committed

    def committed_for(
        self,
        *,
        run_id: str,
        graph_revision: int,
        subtask_id: str,
        subtask_revision: int,
    ) -> CommittedArtifactManifest | None:
        identity = self._by_subtask_revision.get(
            (run_id, graph_revision, subtask_id, subtask_revision)
        )
        return self._committed.get(identity or "")

    def snapshot_for(
        self,
        *,
        consumer_revision: SubtaskRevisionRef,
        run_id: str,
        declared_dependency_refs: Sequence[str],
    ) -> CommittedContextSnapshot:
        artifacts: list[CommittedArtifactManifest] = []
        for dependency in declared_dependency_refs:
            candidates = [
                item
                for item in self._committed.values()
                if item.artifact_revision.run_id == run_id
                and item.artifact_revision.subtask_revision.graph_revision
                == consumer_revision.graph_revision
                and item.artifact_revision.subtask_revision.subtask_id == dependency
            ]
            if not candidates:
                continue
            candidates.sort(
                key=lambda item: item.artifact_revision.subtask_revision.subtask_revision,
                reverse=True,
            )
            artifacts.append(candidates[0])
        snapshot = CommittedContextSnapshot(
            consumer_revision=consumer_revision,
            declared_dependency_refs=tuple(declared_dependency_refs),
            committed_artifacts=tuple(artifacts),
            exact_content_available=True,
            derived_summary_available=False,
        )
        self.artifact_store.ledger.append_context(
            "context_snapshot_created",
            {
                "consumer_revision_sha256": subtask_revision_identity_sha256(
                    consumer_revision
                ),
                "snapshot_sha256": snapshot.snapshot_sha256,
                "committed_manifest_sha256s": [
                    item.committed_manifest_sha256 for item in artifacts
                ],
            },
        )
        return snapshot

    @property
    def committed_artifacts(self) -> tuple[CommittedArtifactManifest, ...]:
        return tuple(self._committed.values())


@dataclass(frozen=True)
class ArtifactPublicationResult:
    status: str
    staged: StagedArtifactManifest
    decision: EvaluationDecision | None
    verified: VerifiedArtifactManifest | None
    committed: CommittedArtifactManifest | None
    quarantined: QuarantinedArtifactManifest | None
    review_triggered: bool
    failure_code: str | None
    evaluation_accounting_operation_ids: tuple[str, ...]
    terminal_failure: TerminalFailureEnvelope | None = None
    evaluation_mode: str = "active"
    observed_evaluation_status: str | None = None
    observed_evaluation_decision_sha256: str | None = None


class ArtifactLifecycleCoordinator:
    """The only formal staged -> evaluated -> committed publication flow."""

    def __init__(
        self,
        *,
        artifact_store: ArtifactLifecycleStore,
        context_store: ContextCommitStore,
        evaluation_coordinator: Any,
        evaluation_mode: str = "active",
        static_evaluation_coordinator: Any | None = None,
    ) -> None:
        self.artifact_store = artifact_store
        self.context_store = context_store
        self.evaluation_coordinator = evaluation_coordinator
        normalized_mode = str(evaluation_mode or "off").strip().lower()
        if normalized_mode not in {"off", "silent", "active"}:
            raise ArtifactLifecycleError("evaluation_mode_invalid")
        self.evaluation_mode = normalized_mode
        self.static_evaluation_coordinator = static_evaluation_coordinator

    async def _silent_fallback(
        self,
        *,
        manifest: StagedArtifactManifest,
        content: bytes,
        standard: Any,
        context: Any,
        payload_guard_factory: Any,
    ) -> Any:
        """Produce a deterministic acceptance decision after a non-gating review."""
        coordinator = self.static_evaluation_coordinator
        if coordinator is None:
            raise ArtifactLifecycleError("silent_evaluation_static_fallback_missing")
        return await coordinator.evaluate(
            manifest=manifest,
            content=content,
            standard=standard,
            context=context,
            payload_guard_factory=payload_guard_factory,
        )

    def _commit_decision(
        self,
        *,
        staged: StagedArtifactManifest,
        decision: EvaluationDecision,
    ) -> tuple[VerifiedArtifactManifest, CommittedArtifactManifest]:
        verified = self.artifact_store.verify(manifest=staged, decision=decision)
        committed = self.context_store.commit(
            staged=staged,
            verified=verified,
            decision=decision,
        )
        return verified, committed

    async def publish(
        self,
        *,
        candidate: FinalArtifactCandidate,
        content: bytes,
        reference_standard: Any,
        evaluation_context: Any,
        payload_guard_factory: Any,
        execution_accounting_operation_ids: Sequence[str] = (),
    ) -> ArtifactPublicationResult:
        staged = self.artifact_store.stage_bytes(
            candidate=candidate,
            content=content,
            accounting_operation_ids=execution_accounting_operation_ids,
        )
        try:
            outcome = await self.evaluation_coordinator.evaluate(
                manifest=staged,
                content=content,
                standard=reference_standard,
                context=evaluation_context,
                payload_guard_factory=payload_guard_factory,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            if self.evaluation_mode != "silent":
                raise
            fallback = await self._silent_fallback(
                manifest=staged,
                content=content,
                standard=reference_standard,
                context=evaluation_context,
                payload_guard_factory=payload_guard_factory,
            )
            assert fallback.final_decision is not None
            verified, committed = self._commit_decision(
                staged=staged, decision=fallback.final_decision
            )
            return ArtifactPublicationResult(
                status="committed",
                staged=staged,
                decision=fallback.final_decision,
                verified=verified,
                committed=committed,
                quarantined=None,
                review_triggered=False,
                failure_code=None,
                evaluation_accounting_operation_ids=(),
                evaluation_mode=self.evaluation_mode,
                observed_evaluation_status="framework_failure",
                observed_evaluation_decision_sha256=None,
            )
        observed_status = outcome.status
        if self.evaluation_mode == "silent":
            fallback = await self._silent_fallback(
                manifest=staged,
                content=content,
                standard=reference_standard,
                context=evaluation_context,
                payload_guard_factory=payload_guard_factory,
            )
            assert fallback.final_decision is not None
            verified, committed = self._commit_decision(
                staged=staged, decision=fallback.final_decision
            )
            return ArtifactPublicationResult(
                status="committed",
                staged=staged,
                decision=fallback.final_decision,
                verified=verified,
                committed=committed,
                quarantined=None,
                review_triggered=outcome.review_triggered,
                failure_code=None,
                evaluation_accounting_operation_ids=outcome.accounting_operation_ids,
                evaluation_mode=self.evaluation_mode,
                observed_evaluation_status=observed_status,
                observed_evaluation_decision_sha256=(
                    outcome.final_decision.decision_sha256
                    if outcome.final_decision is not None
                    else None
                ),
            )
        if outcome.status == "pass" and outcome.final_decision is not None:
            verified, committed = self._commit_decision(
                staged=staged, decision=outcome.final_decision
            )
            return ArtifactPublicationResult(
                status="committed",
                staged=staged,
                decision=outcome.final_decision,
                verified=verified,
                committed=committed,
                quarantined=None,
                review_triggered=outcome.review_triggered,
                failure_code=None,
                evaluation_accounting_operation_ids=outcome.accounting_operation_ids,
                evaluation_mode=self.evaluation_mode,
                observed_evaluation_status=observed_status,
                observed_evaluation_decision_sha256=(
                    outcome.final_decision.decision_sha256
                    if outcome.final_decision is not None
                    else None
                ),
            )
        reason_by_status = {
            "fail": "artifact_quality_failure",
            "inconclusive": "evaluation_inconclusive",
            "protocol_inconclusive": "evaluation_protocol_inconclusive",
            "infrastructure_failure": "evaluation_infrastructure_failure",
            "framework_failure": "evaluation_framework_failure",
            "budget_failure": "evaluation_budget_failure",
            "interrupted": "evaluation_interrupted",
        }
        reason = reason_by_status.get(outcome.status)
        quarantined = None
        if reason is not None:
            quarantined = self.artifact_store.quarantine(
                manifest=staged,
                reason_code=reason,
                final_decision=outcome.final_decision,
            )
        return ArtifactPublicationResult(
            status=outcome.status,
            staged=staged,
            decision=outcome.final_decision,
            verified=None,
            committed=None,
            quarantined=quarantined,
            review_triggered=outcome.review_triggered,
            failure_code=outcome.failure_code,
            evaluation_accounting_operation_ids=outcome.accounting_operation_ids,
            terminal_failure=outcome.terminal_failure,
            evaluation_mode=self.evaluation_mode,
            observed_evaluation_status=observed_status,
            observed_evaluation_decision_sha256=(
                outcome.final_decision.decision_sha256
                if outcome.final_decision is not None
                else None
            ),
        )

    async def publish_v2(
        self,
        *,
        candidate: FinalArtifactCandidateV2,
        content: bytes | None,
        source_path: str | Path | None,
        reference_standard: Any,
        evaluation_context_factory: Any,
        payload_guard_factory: Any,
        execution_accounting_operation_ids: Sequence[str] = (),
    ) -> ArtifactPublicationResult:
        """Stage and publish a byte/file/directory/bundle without coercion."""

        staged = self.artifact_store.stage_v2(
            candidate=candidate,
            content=content,
            source_path=source_path,
            accounting_operation_ids=execution_accounting_operation_ids,
        )
        evaluation_context = evaluation_context_factory(staged)
        evaluation_content = b""
        if candidate.descriptor.representation in {
            ArtifactRepresentation.INLINE_TEXT,
            ArtifactRepresentation.FILE,
        }:
            if content is not None:
                evaluation_content = content
            elif source_path is not None:
                evaluation_content = Path(source_path).read_bytes()
        try:
            outcome = await self.evaluation_coordinator.evaluate(
                manifest=staged,
                content=evaluation_content,
                standard=reference_standard,
                context=evaluation_context,
                payload_guard_factory=payload_guard_factory,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if self.evaluation_mode == "silent":
                fallback = await self._silent_fallback(
                    manifest=staged,
                    content=evaluation_content,
                    standard=reference_standard,
                    context=evaluation_context,
                    payload_guard_factory=payload_guard_factory,
                )
                assert fallback.final_decision is not None
                verified, committed = self._commit_decision(
                    staged=staged, decision=fallback.final_decision
                )
                return ArtifactPublicationResult(
                    status="committed",
                    staged=staged,
                    decision=fallback.final_decision,
                    verified=verified,
                    committed=committed,
                    quarantined=None,
                    review_triggered=False,
                    failure_code=None,
                    evaluation_accounting_operation_ids=(),
                    evaluation_mode=self.evaluation_mode,
                    observed_evaluation_status="framework_failure",
                    observed_evaluation_decision_sha256=None,
                )
            revision = staged.artifact_revision.subtask_revision
            terminal_failure = TerminalFailureEnvelope.create(
                responsibility="framework",
                failure_stage="evaluation",
                failure_code="evaluation_framework_exception",
                exception=exc,
                run_id=staged.artifact_revision.run_id,
                graph_revision=revision.graph_revision,
                subtask_id=revision.subtask_id,
                subtask_revision=revision.subtask_revision,
            )
            quarantined = self.artifact_store.quarantine(
                manifest=staged,
                reason_code="evaluation_framework_failure",
                final_decision=None,
            )
            return ArtifactPublicationResult(
                status="framework_failure",
                staged=staged,
                decision=None,
                verified=None,
                committed=None,
                quarantined=quarantined,
                review_triggered=False,
                failure_code=terminal_failure.failure_code,
                evaluation_accounting_operation_ids=(),
                terminal_failure=terminal_failure,
                evaluation_mode=self.evaluation_mode,
                observed_evaluation_status="framework_failure",
                observed_evaluation_decision_sha256=None,
            )
        observed_status = outcome.status
        if self.evaluation_mode == "silent":
            fallback = await self._silent_fallback(
                manifest=staged,
                content=evaluation_content,
                standard=reference_standard,
                context=evaluation_context,
                payload_guard_factory=payload_guard_factory,
            )
            assert fallback.final_decision is not None
            verified, committed = self._commit_decision(
                staged=staged, decision=fallback.final_decision
            )
            return ArtifactPublicationResult(
                status="committed",
                staged=staged,
                decision=fallback.final_decision,
                verified=verified,
                committed=committed,
                quarantined=None,
                review_triggered=outcome.review_triggered,
                failure_code=None,
                evaluation_accounting_operation_ids=outcome.accounting_operation_ids,
                evaluation_mode=self.evaluation_mode,
                observed_evaluation_status=observed_status,
                observed_evaluation_decision_sha256=(
                    outcome.final_decision.decision_sha256
                    if outcome.final_decision is not None
                    else None
                ),
            )
        if outcome.status == "pass" and outcome.final_decision is not None:
            verified, committed = self._commit_decision(
                staged=staged, decision=outcome.final_decision
            )
            return ArtifactPublicationResult(
                status="committed",
                staged=staged,
                decision=outcome.final_decision,
                verified=verified,
                committed=committed,
                quarantined=None,
                review_triggered=outcome.review_triggered,
                failure_code=None,
                evaluation_accounting_operation_ids=outcome.accounting_operation_ids,
                evaluation_mode=self.evaluation_mode,
                observed_evaluation_status=observed_status,
                observed_evaluation_decision_sha256=(
                    outcome.final_decision.decision_sha256
                    if outcome.final_decision is not None
                    else None
                ),
            )
        reason_by_status = {
            "fail": "artifact_quality_failure",
            "inconclusive": "evaluation_inconclusive",
            "protocol_inconclusive": "evaluation_protocol_inconclusive",
            "infrastructure_failure": "evaluation_infrastructure_failure",
            "framework_failure": "evaluation_framework_failure",
            "budget_failure": "evaluation_budget_failure",
            "interrupted": "evaluation_interrupted",
        }
        reason = reason_by_status.get(outcome.status)
        quarantined = (
            self.artifact_store.quarantine(
                manifest=staged,
                reason_code=reason,
                final_decision=outcome.final_decision,
            )
            if reason is not None
            else None
        )
        return ArtifactPublicationResult(
            status=outcome.status,
            staged=staged,
            decision=outcome.final_decision,
            verified=None,
            committed=None,
            quarantined=quarantined,
            review_triggered=outcome.review_triggered,
            failure_code=outcome.failure_code,
            evaluation_accounting_operation_ids=outcome.accounting_operation_ids,
            terminal_failure=outcome.terminal_failure,
            evaluation_mode=self.evaluation_mode,
            observed_evaluation_status=observed_status,
            observed_evaluation_decision_sha256=(
                outcome.final_decision.decision_sha256
                if outcome.final_decision is not None
                else None
            ),
        )


__all__ = [
    "ArtifactEventLedger",
    "ArtifactLifecycleError",
    "ArtifactLifecycleCoordinator",
    "ArtifactLifecycleStore",
    "ArtifactPublicationResult",
    "ArtifactPersistenceError",
    "ContextCommitStore",
    "MachineContractFailure",
    "build_final_artifact_candidate",
    "raw_sha256",
    "validate_machine_contract",
]
