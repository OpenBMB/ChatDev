"""Host-free publication of verified, committed deliverables.

Absolute paths are private implementation details at this boundary. The formal
return value is an immutable, content-addressed publication record. The
explicitly named legacy helper is the only compatibility API returning host
paths, and those values must never be serialized into a formal record.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from loguru import logger
from pydantic import Field, field_validator, model_validator

from .atomic_io import temporary_sibling_path
from .artifact_v2 import descriptor_for_path
from .evaluation_contracts import ArtifactRepresentation
from .orchestrator import GlobalContext
from .pipeline_control import FrozenContract, canonical_json_bytes, canonical_sha256

if TYPE_CHECKING:
    from .task_invocation import FinalDeliverableContract


DELIVERY_PUBLICATION_PROTOCOL = "sgar-delivery-publication-v1"
_EXT_MAP = {"code": ".py", "json": ".json", "markdown": ".md", "plaintext": ".txt"}


class DeliveryPublication(FrozenContract):
    protocol: Literal[DELIVERY_PUBLICATION_PROTOCOL] = DELIVERY_PUBLICATION_PROTOCOL
    logical_locator: str = Field(min_length=1)
    representation: str = Field(min_length=1)
    format_id: str = Field(min_length=1)
    content_sha256: str
    byte_size: int = Field(ge=0)
    delivery_manifest_locator: str = Field(min_length=1)
    commit_manifest_sha256: str
    lineage_sha256: str
    publication_sha256: str

    @field_validator("logical_locator", "delivery_manifest_locator")
    @classmethod
    def _locator_is_host_free(cls, value: str) -> str:
        normalized = value.replace("\\", "/").lstrip("./")
        if not normalized or normalized.startswith("/") or ":" in normalized.split("/", 1)[0]:
            raise ValueError("delivery_locator_must_be_relative")
        if any(part in {"", ".", ".."} for part in normalized.split("/")):
            raise ValueError("delivery_locator_invalid")
        return normalized

    @field_validator("content_sha256", "commit_manifest_sha256", "lineage_sha256", "publication_sha256")
    @classmethod
    def _hash_is_valid(cls, value: str, info) -> str:
        normalized = value.lower()
        if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
            raise ValueError(f"{info.field_name}_invalid")
        return normalized

    @model_validator(mode="after")
    def _identity_matches(self) -> "DeliveryPublication":
        projection = self.model_dump(mode="python", exclude={"publication_sha256"})
        if canonical_sha256(projection) != self.publication_sha256:
            raise ValueError("delivery_publication_sha256_mismatch")
        return self


@dataclass(frozen=True)
class DeliveryOutcome:
    """Formal publication plus process-private copied paths."""

    publication: DeliveryPublication
    _deliverable_path: Path
    _manifest_path: Path

    def private_path(self, label: Literal["final_deliverable", "delivery_manifest"]) -> Path:
        return self._deliverable_path if label == "final_deliverable" else self._manifest_path

    def legacy_absolute_paths(self) -> dict[str, str]:
        """Explicit compatibility projection; never a formal record."""
        return {
            "final_deliverable": str(self._deliverable_path.resolve()),
            "delivery_manifest": str(self._manifest_path.resolve()),
        }


def _atomic_json(path: Path, payload: dict) -> None:
    temporary = temporary_sibling_path(path)
    with temporary.open("xb") as handle:
        handle.write(canonical_json_bytes(payload))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _copy_committed(source: Path, destination: Path, *, is_tree: bool) -> None:
    temporary = temporary_sibling_path(destination)
    try:
        if is_tree:
            shutil.copytree(source, temporary, symlinks=False)
        else:
            with source.open("rb") as src, temporary.open("xb") as dst:
                shutil.copyfileobj(src, dst)
                dst.flush()
                os.fsync(dst.fileno())
        os.replace(temporary, destination)
    except OSError:
        try:
            shutil.rmtree(temporary) if temporary.is_dir() else temporary.unlink()
        except OSError:
            pass
        raise


def extract_deliverables(
    context: GlobalContext,
    task_list: list[dict],
    output_dir: str = "execution_artifacts",
    *,
    emit_log: bool = True,
    final_deliverable_contract: FinalDeliverableContract | None = None,
) -> DeliveryOutcome | None:
    """Publish the final committed artifact without exposing a host path."""
    if not task_list:
        return None
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    last_task = task_list[-1]
    last_id = str(last_task.get("id") or "")
    committed = context.committed_manifest_for(last_id)
    if context.context_commit_store is None or committed is None:
        if emit_log:
            logger.warning("[Delivery] Final node has no committed artifact: {}", last_id)
        return None

    source = output / committed.blob_locator
    if not source.exists():
        if emit_log:
            logger.warning("[Delivery] Committed blob is unavailable: {}", last_id)
        return None
    descriptor = committed.artifact_v2
    is_tree = bool(
        descriptor is not None
        and descriptor.representation in {ArtifactRepresentation.DIRECTORY, ArtifactRepresentation.BUNDLE}
    )
    if is_tree:
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
            if emit_log:
                logger.error("[Delivery] Committed tree hash drift: {}", last_id)
            return None
    else:
        if not source.is_file():
            if emit_log:
                logger.warning("[Delivery] Committed blob kind invalid: {}", last_id)
            return None
        if hashlib.sha256(source.read_bytes()).hexdigest() != committed.content_sha256:
            if emit_log:
                logger.error("[Delivery] Committed blob hash drift: {}", last_id)
            return None

    fallback_ext = str(last_task.get("output_extension") or _EXT_MAP.get(last_task.get("artifact_type", "plaintext"), ".txt"))
    friendly_name = (
        final_deliverable_contract.logical_name
        if final_deliverable_contract is not None
        and final_deliverable_contract.logical_name is not None
        else "final_bundle"
        if descriptor is not None and descriptor.representation is ArtifactRepresentation.BUNDLE
        else "final_output"
        if is_tree
        else f"final_output{committed.extension or fallback_ext}"
    )
    destination = output / friendly_name
    if destination.exists():
        raise FileExistsError("delivery_destination_already_exists")
    _copy_committed(source, destination, is_tree=is_tree)

    if is_tree:
        delivered = descriptor_for_path(
            destination,
            format_id=descriptor.format_id,
            extension=descriptor.extension,
            logical_locator=descriptor.logical_locator,
            provenance_source_ids=descriptor.provenance_source_ids,
            as_bundle=descriptor.representation is ArtifactRepresentation.BUNDLE,
            primary_member=descriptor.primary_member,
            required_members=(item.relative_path for item in descriptor.members if item.required),
        )
        if delivered.descriptor_sha256 != descriptor.descriptor_sha256:
            raise RuntimeError("delivery_tree_hash_mismatch")
    elif hashlib.sha256(destination.read_bytes()).hexdigest() != committed.content_sha256:
        raise RuntimeError("delivery_content_hash_mismatch")

    representation = (
        descriptor.representation.value
        if descriptor is not None and hasattr(descriptor.representation, "value")
        else str(descriptor.representation if descriptor is not None else "file")
    )
    format_id = str(descriptor.format_id if descriptor is not None else last_task.get("artifact_type") or "binary")
    lineage = canonical_sha256(
        {
            "artifact_revision_sha256": committed.artifact_revision.revision_sha256,
            "candidate_pool_sha256": committed.candidate_pool_sha256,
            "plan_sha256": committed.plan_sha256,
            "recovery_operation_sha256": committed.recovery_operation_sha256,
            "evaluation_decision_sha256": committed.evaluation_decision_sha256,
            "committed_manifest_sha256": committed.committed_manifest_sha256,
        }
    )
    projection = {
        "protocol": DELIVERY_PUBLICATION_PROTOCOL,
        "logical_locator": friendly_name,
        "representation": representation,
        "format_id": format_id,
        "content_sha256": committed.content_sha256,
        "byte_size": committed.byte_size,
        "delivery_manifest_locator": "delivery_manifest.json",
        "commit_manifest_sha256": committed.committed_manifest_sha256,
        "lineage_sha256": lineage,
    }
    publication = DeliveryPublication(**projection, publication_sha256=canonical_sha256(projection))
    manifest = {
        "schema_version": "sgar-artifact-v2" if descriptor is not None else "sgar-artifact-commit-v1",
        "publication": publication.model_dump(mode="json"),
        "artifact_revision_sha256": committed.artifact_revision.revision_sha256,
        "committed_manifest_sha256": committed.committed_manifest_sha256,
        "content_sha256": committed.content_sha256,
        "candidate_pool_sha256": committed.candidate_pool_sha256,
        "plan_sha256": committed.plan_sha256,
        "recovery_operation_sha256": committed.recovery_operation_sha256,
        "evaluation_decision_sha256": committed.evaluation_decision_sha256,
        "source_handle_ids": list(committed.source_handle_ids),
        "provenance_source_ids": list(committed.provenance_source_ids),
        "execution_event_ids": list(committed.execution_event_ids),
        "accounting_operation_ids": list(committed.accounting_operation_ids),
        "delivery_locator": friendly_name,
        "artifact_descriptor": descriptor.model_dump(mode="json") if descriptor is not None else None,
    }
    manifest_path = output / "delivery_manifest.json"
    _atomic_json(manifest_path, manifest)
    if emit_log:
        logger.success(
            "[Delivery] Committed final deliverable -> {} ({} bytes, sha256={})",
            friendly_name,
            committed.byte_size,
            committed.content_sha256,
        )
    return DeliveryOutcome(publication, destination, manifest_path)


def extract_deliverables_legacy(
    context: GlobalContext,
    task_list: list[dict],
    output_dir: str = "execution_artifacts",
) -> dict[str, str]:
    """Explicit in-memory compatibility wrapper returning absolute paths."""
    outcome = extract_deliverables(context, task_list, output_dir=output_dir)
    return outcome.legacy_absolute_paths() if outcome is not None else {}


__all__ = [
    "DELIVERY_PUBLICATION_PROTOCOL",
    "DeliveryOutcome",
    "DeliveryPublication",
    "extract_deliverables",
    "extract_deliverables_legacy",
]
