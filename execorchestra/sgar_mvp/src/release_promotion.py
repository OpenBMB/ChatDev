"""Atomic Qwen retrieval activation and receipt-driven rollback."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import pickle
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .control_role_policy import load_control_role_policy
from .embedding_runtime import (
    EmbeddingRuntimeConfigV1,
    EmbeddingRuntimeIdentityV2,
    IndexMetaV2,
)
from .internal_language import build_prompt_surface_registry, prompt_file_text
from .model_response_contracts import system_role_schema
from .pipeline_control import canonical_json_bytes, canonical_sha256
from .profiler_protocol import ProfilerProviderCapabilityV1
from .release_source_seal import load_and_verify_source_seal, source_seal_reference
from .release_environment import is_approved_release_branch, require_release_storage_path
from .release_provider_receipt import load_and_verify_release_provider_probe_receipt
from .retrieval_policy import RetrievalPolicy, load_retrieval_policy


PROMOTION_RECEIPT_PROTOCOL = "sgar-retrieval-promotion-receipt-v8"
ROLLBACK_RECEIPT_PROTOCOL = "sgar-retrieval-rollback-receipt-v1"
INDEX_FILE_NAMES = (
    "faiss_cap.index",
    "faiss_con.index",
    "resource_meta.pkl",
    "retrieval_profile_audit.json",
    "index_build_manifest.json",
)
_OPTIONAL_LEGACY_BASELINE_FILES = frozenset({"index_build_manifest.json"})
_EFFECTIVE_POOL_SOURCE_PATH = "Pool/resources/json/effective_combine.json"
_INDEX_MANIFEST_PROTOCOL = "sgar-retrieval-index-build-v1"
_FINALIZE_COMMIT_MESSAGE = "chore: finalize release retrieval promotion"
_SOURCE_SEAL_REFERENCE_KEYS = {
    "protocol",
    "stage",
    "seal_sha256",
    "source_collection_sha256",
    "git_branch",
    "git_head",
    "git_tree",
    "framework_source_clean",
    "planner_prompt_identity",
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _run_git(project_root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
    )
    return completed.stdout.strip()


def _git_paths(project_root: Path, *arguments: str) -> set[str]:
    # Git diff names are repository-relative even when invoked in a subproject.
    # Keep paths outside the project visible so unrelated changes still fail
    # the exact approved-change-set checks below.
    prefix = _run_git(project_root, "rev-parse", "--show-prefix")
    return {
        (item[len(prefix):] if item.startswith(prefix)
         else "../" * len(Path(prefix).parts) + item).replace("\\", "/")
        for item in _run_git(project_root, *arguments).split("\0")
        if item
    }


def _expected_active_targets(project_root: Path) -> dict[str, Path]:
    root = project_root.resolve()
    targets = {
        "retrieval_policy.json": root / "sgar_mvp" / "config" / "retrieval_policy.json"
    }
    targets.update(
        {name: root / "Pool" / "index_meta" / name for name in INDEX_FILE_NAMES}
    )
    return targets


def _require_sha256(value: Any, *, code: str) -> str:
    normalized = str(value or "").strip().lower()
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise RuntimeError(code)
    return normalized


def _require_git_oid(value: Any, *, code: str) -> str:
    normalized = str(value or "").strip().lower()
    if len(normalized) != 40 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise RuntimeError(code)
    return normalized


def _source_file_sha256(
    source_seal: Mapping[str, Any],
    relative_path: str,
    *,
    code: str,
) -> str:
    files = source_seal.get("files_sha256")
    value = files.get(relative_path) if isinstance(files, Mapping) else None
    normalized = str(value or "").strip().lower()
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise RuntimeError(code)
    return normalized


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        shutil.copy2(source, temporary)
        if _sha256_file(temporary) != _sha256_file(source):
            raise RuntimeError("release_atomic_copy_hash_mismatch")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_bytes(canonical_json_bytes(dict(payload)) + b"\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _load_and_verify_promotion_receipt(
    *,
    project_root: Path,
    promotion_receipt_path: Path,
    expected_parent_release_source_seal_sha256: str | None = None,
    verify_current_after_hashes: bool = True,
    verify_backups: bool = False,
) -> dict[str, Any]:
    root = project_root.resolve()
    receipt_path = require_release_storage_path(
        promotion_receipt_path,
        code="release_promotion_receipt_outside_storage_root",
    )
    if not receipt_path.is_file():
        raise RuntimeError("release_promotion_receipt_missing")
    try:
        payload = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("release_promotion_receipt_invalid") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("release_promotion_receipt_invalid")
    claimed = _require_sha256(
        payload.get("receipt_sha256"),
        code="release_promotion_receipt_hash_missing",
    )
    unsigned = dict(payload)
    unsigned.pop("receipt_sha256", None)
    if claimed != canonical_sha256(unsigned):
        raise RuntimeError("release_promotion_receipt_hash_mismatch")
    if payload.get("protocol") != PROMOTION_RECEIPT_PROTOCOL:
        raise RuntimeError("release_promotion_receipt_protocol_invalid")
    if payload.get("status") != "activated_pending_commit":
        raise RuntimeError("release_promotion_receipt_status_invalid")

    source_ref = payload.get("release_source_seal")
    if (
        not isinstance(source_ref, Mapping)
        or set(source_ref) != _SOURCE_SEAL_REFERENCE_KEYS
        or source_ref.get("protocol") != "sgar-release-source-seal-v1"
        or source_ref.get("stage") != "release"
        or not is_approved_release_branch(source_ref.get("git_branch"))
        or source_ref.get("git_branch") != _run_git(root, "branch", "--show-current")
        or source_ref.get("framework_source_clean") is not True
        or not isinstance(source_ref.get("planner_prompt_identity"), Mapping)
    ):
        raise RuntimeError("release_promotion_receipt_source_seal_invalid")
    source_sha = _require_sha256(
        source_ref.get("seal_sha256"),
        code="release_promotion_receipt_source_seal_invalid",
    )
    _require_sha256(
        source_ref.get("source_collection_sha256"),
        code="release_promotion_receipt_source_seal_invalid",
    )
    _require_git_oid(
        source_ref.get("git_head"),
        code="release_promotion_receipt_source_seal_invalid",
    )
    _require_git_oid(
        source_ref.get("git_tree"),
        code="release_promotion_receipt_source_seal_invalid",
    )
    if (
        expected_parent_release_source_seal_sha256 is not None
        and source_sha != expected_parent_release_source_seal_sha256
    ):
        raise RuntimeError("release_promotion_receipt_source_seal_mismatch")

    expected_targets = _expected_active_targets(root)
    files = payload.get("files")
    if not isinstance(files, Mapping) or set(files) != set(expected_targets):
        raise RuntimeError("release_promotion_receipt_target_set_invalid")
    for name, expected_target in expected_targets.items():
        details = files.get(name)
        if not isinstance(details, Mapping):
            raise RuntimeError(f"release_promotion_receipt_target_invalid:{name}")
        target = Path(str(details.get("target_path") or "")).resolve()
        if target != expected_target.resolve():
            raise RuntimeError(f"release_promotion_receipt_target_path_invalid:{name}")
        after_sha = _require_sha256(
            details.get("after_sha256"),
            code=f"release_promotion_receipt_after_hash_invalid:{name}",
        )
        if verify_current_after_hashes and (
            not target.is_file() or _sha256_file(target) != after_sha
        ):
            raise RuntimeError(f"release_promotion_after_hash_mismatch:{name}")

        existed_before = details.get("existed_before", True)
        if existed_before is not True and existed_before is not False:
            raise RuntimeError(f"release_promotion_receipt_existence_invalid:{name}")
        before_sha = details.get("before_sha256")
        backup_path = details.get("backup_path")
        if existed_before:
            before_sha = _require_sha256(
                before_sha,
                code=f"release_promotion_receipt_before_hash_invalid:{name}",
            )
            if verify_backups:
                backup = require_release_storage_path(
                    Path(str(backup_path or "")),
                    code=f"release_promotion_backup_outside_storage_root:{name}",
                )
                if not backup.is_file() or _sha256_file(backup) != before_sha:
                    raise RuntimeError(f"release_promotion_backup_hash_mismatch:{name}")
        elif before_sha is not None or backup_path is not None:
            raise RuntimeError(f"release_promotion_receipt_absent_baseline_invalid:{name}")
    return payload


def _verify_index_generation(staging_dir: Path, source_seal: Mapping[str, Any]) -> dict[str, Any]:
    root = require_release_storage_path(staging_dir, code="release_staging_index_outside_storage_root")
    missing = [name for name in INDEX_FILE_NAMES if not (root / name).is_file()]
    if missing:
        raise RuntimeError(f"release_staging_index_incomplete:{','.join(missing)}")
    manifest_path = root / "index_build_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    claimed = str(manifest.get("manifest_sha256") or "")
    unsigned = dict(manifest)
    unsigned.pop("manifest_sha256", None)
    if claimed != canonical_sha256(unsigned):
        raise RuntimeError("release_index_manifest_hash_mismatch")
    seal_ref = manifest.get("release_source_seal") or {}
    if seal_ref.get("seal_sha256") != source_seal.get("seal_sha256"):
        raise RuntimeError("release_index_source_seal_mismatch")
    if int(manifest.get("dimension") or 0) != 1024:
        raise RuntimeError("release_index_dimension_invalid")
    for name, expected in (manifest.get("files_sha256") or {}).items():
        candidate = root / str(name)
        if not candidate.is_file() or _sha256_file(candidate) != expected:
            raise RuntimeError(f"release_index_file_hash_mismatch:{name}")
    with (root / "resource_meta.pkl").open("rb") as handle:
        metadata = pickle.load(handle)
    resource_ids = tuple((metadata.get("index_meta_v2") or {}).get("resource_id_order") or ())
    if (not resource_ids or len(set(resource_ids)) != len(resource_ids)
            or len(resource_ids) != int(manifest.get("resource_count") or 0)
            or set(resource_ids) != set(metadata.get("id_to_resource") or {})
            or len(resource_ids) != int((metadata.get("index_meta_v2") or {}).get("vector_count") or 0)):
        raise RuntimeError("release_index_resource_count_invalid")
    runtime = metadata.get("embedding_runtime_config") or {}
    if (
        runtime.get("candidate_id") != "qwen3-embedding-0.6b-bf16-1024"
        or runtime.get("model_id") != "Qwen/Qwen3-Embedding-0.6B"
        or runtime.get("dtype") != "bfloat16"
        or int(runtime.get("output_dimension") or 0) != 1024
        or runtime.get("pooling") != "last_token"
        or runtime.get("normalize") is not True
    ):
        raise RuntimeError("release_index_embedding_identity_invalid")
    if metadata.get("release_source_seal", {}).get("seal_sha256") != source_seal.get(
        "seal_sha256"
    ):
        raise RuntimeError("release_index_metadata_source_seal_mismatch")
    return {"manifest": manifest, "metadata": metadata, "root": root}


def _verify_active_release_baseline(
    *,
    policy_path: Path,
    index_dir: Path,
    base_policy: RetrievalPolicy,
) -> dict[str, Any]:
    """Verify the current release before a sealed-to-sealed upgrade.

    A pending policy is the only supported initial-activation baseline.  An
    already released policy may be upgraded only when its policy, manifest,
    and every active index artifact still agree byte-for-byte.  This check is
    intentionally independent from staging-index verification so a valid new
    release can never hide drift in the rollback baseline.
    """

    identity: dict[str, Any] = {
        "activation_mode": "initial_pending",
        "policy_version": base_policy.policy_version,
        "policy_sha256": base_policy.sha256(),
        "policy_file_sha256": _sha256_file(policy_path),
        "release_source_seal_sha256": base_policy.release_source_seal_sha256,
        "index_build_manifest_sha256": base_policy.index_build_manifest_sha256,
    }
    if not base_policy.release_sealed:
        return identity

    missing = [name for name in INDEX_FILE_NAMES if not (index_dir / name).is_file()]
    if missing:
        raise RuntimeError(f"release_active_baseline_incomplete:{','.join(missing)}")

    manifest_path = index_dir / "index_build_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("release_active_manifest_invalid") from exc
    if not isinstance(manifest, dict):
        raise RuntimeError("release_active_manifest_invalid")
    claimed = str(manifest.get("manifest_sha256") or "")
    unsigned = dict(manifest)
    unsigned.pop("manifest_sha256", None)
    if claimed != canonical_sha256(unsigned):
        raise RuntimeError("release_active_manifest_hash_mismatch")
    if claimed != base_policy.index_build_manifest_sha256:
        raise RuntimeError("release_active_manifest_policy_mismatch")

    seal_ref = manifest.get("release_source_seal") or {}
    if not isinstance(seal_ref, dict):
        raise RuntimeError("release_active_manifest_source_seal_invalid")
    if seal_ref.get("seal_sha256") != base_policy.release_source_seal_sha256:
        raise RuntimeError("release_active_manifest_source_seal_mismatch")
    if int(manifest.get("resource_count") or 0) <= 0:
        raise RuntimeError("release_active_manifest_resource_count_invalid")
    if int(manifest.get("dimension") or 0) != 1024:
        raise RuntimeError("release_active_manifest_dimension_invalid")

    generation_id = str(manifest.get("generation_id") or "")
    expected_versions = {
        f"retrieval-policy-v6-{generation_id}",
        f"retrieval-policy-v7-{generation_id}",
    }
    if not generation_id or base_policy.policy_version not in expected_versions:
        raise RuntimeError("release_active_policy_generation_mismatch")

    files_sha256 = manifest.get("files_sha256") or {}
    required_manifest_files = set(INDEX_FILE_NAMES[:-1])
    if not isinstance(files_sha256, dict) or set(files_sha256) != required_manifest_files:
        raise RuntimeError("release_active_manifest_file_set_invalid")
    actual_files: dict[str, str] = {}
    for name in INDEX_FILE_NAMES[:-1]:
        actual = _sha256_file(index_dir / name)
        if actual != files_sha256.get(name):
            raise RuntimeError(f"release_active_index_file_hash_mismatch:{name}")
        actual_files[name] = actual

    policy_index_hashes = {
        "faiss_cap.index": base_policy.index_sha256.get("capability"),
        "faiss_con.index": base_policy.index_sha256.get("constraint"),
        "resource_meta.pkl": base_policy.index_sha256.get("metadata"),
    }
    for name, expected in policy_index_hashes.items():
        if actual_files[name] != expected:
            raise RuntimeError(f"release_active_index_policy_mismatch:{name}")

    try:
        with (index_dir / "resource_meta.pkl").open("rb") as handle:
            baseline_metadata = pickle.load(handle)
        baseline_ids = tuple((baseline_metadata.get("idx_to_id") or {}).values())
    except Exception as exc:
        raise RuntimeError("release_active_metadata_invalid") from exc
    if (not baseline_ids or len(set(baseline_ids)) != len(baseline_ids)
            or len(baseline_ids) != int(manifest["resource_count"])):
        raise RuntimeError("release_active_manifest_resource_count_invalid")
    identity.update(
        {
            "activation_mode": "sealed_release_upgrade",
            "generation_id": generation_id,
            "active_files_sha256": actual_files,
            "baseline_verification_sha256": canonical_sha256(
                {
                    "policy_sha256": identity["policy_sha256"],
                    "policy_file_sha256": identity["policy_file_sha256"],
                    "release_source_seal_sha256": identity[
                        "release_source_seal_sha256"
                    ],
                    "index_build_manifest_sha256": claimed,
                    "active_files_sha256": actual_files,
                }
            ),
        }
    )
    return identity


def _metadata_semantic_sha256(metadata: Mapping[str, Any]) -> str:
    projection = copy.deepcopy(dict(metadata))
    projection.pop("release_source_seal", None)
    return hashlib.sha256(
        pickle.dumps(projection, protocol=pickle.HIGHEST_PROTOCOL)
    ).hexdigest()


def _contains_source_seal_identity(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key) in {"release_source_seal", "release_source_seal_sha256"}:
                return True
            if _contains_source_seal_identity(child):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_source_seal_identity(item) for item in value)
    return False


def _validate_rebind_metadata(
    *,
    metadata: Mapping[str, Any],
    manifest: Mapping[str, Any],
    policy: RetrievalPolicy,
    expected_source_seal_sha256: str,
) -> dict[str, Any]:
    if manifest.get("protocol") != _INDEX_MANIFEST_PROTOCOL:
        raise RuntimeError("release_rebind_manifest_protocol_invalid")
    metadata_source_ref = metadata.get("release_source_seal")
    if (
        not isinstance(metadata_source_ref, Mapping)
        or metadata_source_ref.get("seal_sha256") != expected_source_seal_sha256
    ):
        raise RuntimeError("release_rebind_metadata_source_seal_mismatch")

    raw_runtime = metadata.get("embedding_runtime_config") or {}
    runtime_identity = metadata.get("embedding_runtime_identity") or {}
    raw_runtime_v2 = metadata.get("embedding_runtime_identity_v2") or {}
    raw_index_meta = metadata.get("index_meta_v2") or {}
    if not all(
        isinstance(item, Mapping)
        for item in (raw_runtime, runtime_identity, raw_runtime_v2, raw_index_meta)
    ):
        raise RuntimeError("release_rebind_embedding_identity_invalid")
    try:
        runtime = EmbeddingRuntimeConfigV1.model_validate(raw_runtime).model_dump(
            mode="python"
        )
        runtime_v2 = EmbeddingRuntimeIdentityV2.model_validate(
            raw_runtime_v2
        ).model_dump(mode="python")
        index_meta = IndexMetaV2.model_validate(raw_index_meta).model_dump(
            mode="python"
        )
    except (TypeError, ValueError) as exc:
        raise RuntimeError("release_rebind_embedding_identity_invalid") from exc
    if (
        runtime.get("candidate_id") != policy.embedding_candidate_id
        or runtime.get("model_id") != policy.embedding_model
        or runtime.get("dtype") != "bfloat16"
        or int(runtime.get("output_dimension") or 0) != 1024
        or runtime.get("pooling") != "last_token"
        or runtime.get("normalize") is not True
        or runtime_v2.get("identity_sha256")
        != policy.embedding_runtime_identity_sha256
        or index_meta.get("index_meta_sha256") != policy.index_meta_sha256
        or index_meta.get("embedding_runtime_identity") != runtime_v2
    ):
        raise RuntimeError("release_rebind_embedding_identity_invalid")
    if (
        manifest.get("embedding_configuration_sha256")
        != runtime.get("configuration_sha256")
        or manifest.get("embedding_identity_sha256")
        != runtime_identity.get("identity_sha256")
        or manifest.get("embedding_runtime_identity_v2_sha256")
        != runtime_v2.get("identity_sha256")
        or manifest.get("index_meta_v2_sha256")
        != index_meta.get("index_meta_sha256")
    ):
        raise RuntimeError("release_rebind_manifest_embedding_identity_mismatch")

    resource_ids = tuple(index_meta.get("resource_id_order") or ())
    resource_order_sha = canonical_sha256(resource_ids)
    if (
        not resource_ids
        or len(set(resource_ids)) != len(resource_ids)
        or set(resource_ids) != set(metadata.get("id_to_resource") or {})
        or int(index_meta.get("vector_count") or 0) != len(resource_ids)
        or int(index_meta.get("faiss_dimension") or 0) != 1024
        or metadata.get("resource_order_sha256") != resource_order_sha
        or index_meta.get("resource_id_order_sha256") != resource_order_sha
        or manifest.get("resource_order_sha256") != resource_order_sha
        or int(manifest.get("resource_count") or 0) != len(resource_ids)
        or int(manifest.get("dimension") or 0) != 1024
    ):
        raise RuntimeError("release_rebind_resource_identity_invalid")

    capability_vectors = np.ascontiguousarray(
        metadata.get("cap_vectors"), dtype="float32"
    )
    constraint_vectors = np.ascontiguousarray(
        metadata.get("con_vectors"), dtype="float32"
    )
    if capability_vectors.shape != (len(resource_ids), 1024) or constraint_vectors.shape != (
        len(resource_ids),
        1024,
    ):
        raise RuntimeError("release_rebind_vector_shape_invalid")
    capability_sha = hashlib.sha256(capability_vectors.tobytes()).hexdigest()
    constraint_sha = hashlib.sha256(constraint_vectors.tobytes()).hexdigest()
    if (
        capability_sha != index_meta.get("capability_vectors_sha256")
        or constraint_sha != index_meta.get("constraint_vectors_sha256")
    ):
        raise RuntimeError("release_rebind_vector_identity_invalid")
    return {
        "resource_count": len(resource_ids),
        "resource_order_sha256": resource_order_sha,
        "embedding_configuration_sha256": runtime.get("configuration_sha256"),
        "embedding_identity_sha256": runtime_identity.get("identity_sha256"),
        "embedding_runtime_identity_sha256": runtime_v2.get("identity_sha256"),
        "index_meta_sha256": index_meta.get("index_meta_sha256"),
        "capability_vectors_sha256": capability_sha,
        "constraint_vectors_sha256": constraint_sha,
        "metadata_semantic_sha256": _metadata_semantic_sha256(metadata),
    }


def rebind_release_index_generation(
    *,
    project_root: Path,
    source_seal_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    if not is_approved_release_branch(_run_git(root, "branch", "--show-current")):
        raise RuntimeError("release_rebind_branch_invalid")
    source_seal = load_and_verify_source_seal(
        source_seal_path,
        project_root=root,
        allowed_stages=("release",),
    )
    output = require_release_storage_path(output_dir, code="release_rebind_output_outside_storage_root")
    if output.exists():
        raise RuntimeError("release_rebind_output_not_fresh")

    policy_path = root / "sgar_mvp" / "config" / "retrieval_policy.json"
    index_dir = root / "Pool" / "index_meta"
    policy = load_retrieval_policy(policy_path)
    if not policy.release_sealed:
        raise RuntimeError("release_rebind_requires_sealed_active_baseline")
    baseline = _verify_active_release_baseline(
        policy_path=policy_path,
        index_dir=index_dir,
        base_policy=policy,
    )
    if baseline.get("activation_mode") != "sealed_release_upgrade":
        raise RuntimeError("release_rebind_requires_sealed_active_baseline")
    sealed_pool_sha = _source_file_sha256(
        source_seal,
        _EFFECTIVE_POOL_SOURCE_PATH,
        code="release_rebind_effective_pool_identity_invalid",
    )
    if sealed_pool_sha != policy.effective_pool_sha256:
        raise RuntimeError("release_rebind_effective_pool_drift")

    manifest_path = index_dir / "index_build_manifest.json"
    try:
        parent_manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        with (index_dir / "resource_meta.pkl").open("rb") as handle:
            parent_metadata = pickle.load(handle)
        audit = json.loads(
            (index_dir / "retrieval_profile_audit.json").read_text(
                encoding="utf-8-sig"
            )
        )
    except (OSError, UnicodeError, json.JSONDecodeError, pickle.PickleError) as exc:
        raise RuntimeError("release_rebind_active_generation_invalid") from exc
    if not isinstance(parent_manifest, dict) or not isinstance(parent_metadata, Mapping):
        raise RuntimeError("release_rebind_active_generation_invalid")
    if _contains_source_seal_identity(audit):
        raise RuntimeError("release_rebind_audit_source_identity_unsupported")
    invariants = _validate_rebind_metadata(
        metadata=parent_metadata,
        manifest=parent_manifest,
        policy=policy,
        expected_source_seal_sha256=str(policy.release_source_seal_sha256),
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{uuid.uuid4().hex}.tmp")
    temporary.mkdir(parents=False, exist_ok=False)
    try:
        for name in (
            "faiss_cap.index",
            "faiss_con.index",
            "retrieval_profile_audit.json",
        ):
            _atomic_copy(index_dir / name, temporary / name)

        rebound_metadata = copy.deepcopy(dict(parent_metadata))
        rebound_metadata["release_source_seal"] = source_seal_reference(source_seal)
        if _metadata_semantic_sha256(rebound_metadata) != invariants[
            "metadata_semantic_sha256"
        ]:
            raise RuntimeError("release_rebind_metadata_semantic_drift")
        (temporary / "resource_meta.pkl").write_bytes(
            pickle.dumps(rebound_metadata, protocol=pickle.HIGHEST_PROTOCOL)
        )
        file_hashes = {
            name: _sha256_file(temporary / name) for name in INDEX_FILE_NAMES[:-1]
        }
        build_code_sha = _sha256_file(Path(__file__).resolve())
        generation_projection = {
            "generation_kind": "identity_rebind",
            "parent_generation_id": parent_manifest.get("generation_id"),
            "parent_manifest_sha256": parent_manifest.get("manifest_sha256"),
            "release_source_seal_sha256": source_seal.get("seal_sha256"),
            "resource_order_sha256": invariants["resource_order_sha256"],
            "embedding_runtime_identity_v2_sha256": invariants[
                "embedding_runtime_identity_sha256"
            ],
            "files_sha256": file_hashes,
            "build_code_sha256": build_code_sha,
        }
        rebound_manifest = dict(parent_manifest)
        rebound_manifest.pop("manifest_sha256", None)
        rebound_manifest.update(
            {
                "protocol": _INDEX_MANIFEST_PROTOCOL,
                "generation_id": canonical_sha256(generation_projection)[:32],
                "generation_kind": "identity_rebind",
                "parent_generation_id": parent_manifest.get("generation_id"),
                "parent_manifest_sha256": parent_manifest.get("manifest_sha256"),
                "release_source_seal": source_seal_reference(source_seal),
                "build_code_sha256": build_code_sha,
                "files_sha256": file_hashes,
            }
        )
        rebound_manifest["manifest_sha256"] = canonical_sha256(rebound_manifest)
        _atomic_write(temporary / "index_build_manifest.json", rebound_manifest)

        verified = _verify_index_generation(temporary, source_seal)
        rebound_invariants = _validate_rebind_metadata(
            metadata=verified["metadata"],
            manifest=verified["manifest"],
            policy=policy,
            expected_source_seal_sha256=str(source_seal["seal_sha256"]),
        )
        for field_name in (
            "resource_count",
            "resource_order_sha256",
            "embedding_configuration_sha256",
            "embedding_identity_sha256",
            "embedding_runtime_identity_sha256",
            "index_meta_sha256",
            "capability_vectors_sha256",
            "constraint_vectors_sha256",
            "metadata_semantic_sha256",
        ):
            if rebound_invariants[field_name] != invariants[field_name]:
                raise RuntimeError(f"release_rebind_invariant_drift:{field_name}")
        old_faiss = {
            name: _sha256_file(index_dir / name)
            for name in ("faiss_cap.index", "faiss_con.index")
        }
        new_faiss = {
            name: _sha256_file(temporary / name)
            for name in ("faiss_cap.index", "faiss_con.index")
        }
        if new_faiss != old_faiss:
            raise RuntimeError("release_rebind_faiss_hash_drift")
        if output.exists():
            raise RuntimeError("release_rebind_output_not_fresh")
        temporary.rename(output)
        return {
            "status": "rebound",
            "output_directory": str(output),
            "parent_generation_id": parent_manifest.get("generation_id"),
            "parent_manifest_sha256": parent_manifest.get("manifest_sha256"),
            "generation_id": rebound_manifest["generation_id"],
            "manifest_sha256": rebound_manifest["manifest_sha256"],
            "old_faiss_sha256": old_faiss,
            "new_faiss_sha256": new_faiss,
            "resource_count": invariants["resource_count"],
            "resource_order_sha256": invariants["resource_order_sha256"],
            "embedding_runtime_identity_sha256": invariants[
                "embedding_runtime_identity_sha256"
            ],
            "index_meta_sha256": invariants["index_meta_sha256"],
        }
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise


def build_released_policy(
    *,
    source_seal: Mapping[str, Any],
    index_manifest: Mapping[str, Any],
    index_metadata: Mapping[str, Any],
    provider_capability: ProfilerProviderCapabilityV1,
    provider_probe_receipt: Mapping[str, Any],
    base_policy: RetrievalPolicy,
) -> RetrievalPolicy:
    if "xhigh" not in provider_capability.supported_reasoning_efforts:
        raise RuntimeError("release_profiler_xhigh_capability_missing")
    if provider_capability.accepted_response_mode != "native_strict_schema":
        raise RuntimeError("release_profiler_response_mode_invalid")
    registry = build_prompt_surface_registry()
    profiler_records = [item for item in registry.records if item.role == "profiler"]
    if len(profiler_records) != 1:
        raise RuntimeError("release_profiler_prompt_registry_identity_invalid")
    profiler_prompt_sha256 = hashlib.sha256(
        prompt_file_text("profiler_system.txt").encode("utf-8")
    ).hexdigest()
    if profiler_records[0].template_sha256 != profiler_prompt_sha256:
        raise RuntimeError("release_profiler_prompt_hash_mismatch")
    control_policy = load_control_role_policy()
    runtime = index_metadata["embedding_runtime_config"]
    runtime_v2 = index_metadata["embedding_runtime_identity_v2"]
    index_meta_v2 = index_metadata["index_meta_v2"]
    files_sha256 = index_manifest["files_sha256"]
    effective_pool_sha256 = _source_file_sha256(
        source_seal,
        _EFFECTIVE_POOL_SOURCE_PATH,
        code="release_effective_pool_source_identity_invalid",
    )
    payload = base_policy.model_dump(mode="json")
    payload.update(
        {
            "policy_version": f"retrieval-policy-v7-{index_manifest['generation_id']}",
            "active_strategy": "capability_only",
            "candidate_strategy": "capability_only",
            "profile_version": str(index_metadata["profile_version"]),
            "resource_pool_commit": str(source_seal["git_head"]),
            "embedding_model": "Qwen/Qwen3-Embedding-0.6B",
            "effective_pool_sha256": effective_pool_sha256,
            "index_sha256": {
                "capability": str(files_sha256["faiss_cap.index"]),
                "constraint": str(files_sha256["faiss_con.index"]),
                "metadata": str(files_sha256["resource_meta.pkl"]),
            },
            "embedding_candidate_id": str(runtime["candidate_id"]),
            "embedding_runtime_identity_sha256": str(runtime_v2["identity_sha256"]),
            "index_meta_sha256": str(index_meta_v2["index_meta_sha256"]),
            "index_build_manifest_sha256": str(index_manifest["manifest_sha256"]),
            "release_source_seal_sha256": str(source_seal["seal_sha256"]),
            "prompt_registry_sha256": registry.registry_sha256,
            "profiler_prompt_sha256": profiler_prompt_sha256,
            "profiler_schema_sha256": canonical_sha256(system_role_schema("hyde")),
            "control_role_policy_sha256": control_policy.policy_sha256,
            "control_provider_probe_receipt_sha256": str(
                provider_probe_receipt["result_sha256"]
            ),
        }
    )
    payload["hyde"].update(
        {
            "reasoning_effort": "xhigh",
            "temperature": None,
            "provider_capability_sha256": provider_capability.capability_sha256,
            "response_mode": provider_capability.accepted_response_mode,
        }
    )
    return RetrievalPolicy.model_validate(payload)


def promote_release_retrieval(
    *,
    project_root: Path,
    source_seal_path: Path,
    staging_index_dir: Path,
    provider_capability_path: Path,
    provider_probe_results_path: Path,
    backup_dir: Path,
    receipt_path: Path,
    failure_inject_after: int | None = None,
) -> dict[str, Any]:
    root = project_root.resolve()
    source_seal = load_and_verify_source_seal(
        source_seal_path,
        project_root=root,
        allowed_stages=("release",),
    )
    verified = _verify_index_generation(staging_index_dir, source_seal)
    capability = ProfilerProviderCapabilityV1.model_validate_json(
        provider_capability_path.read_text(encoding="utf-8-sig")
    )
    probe_results_file = provider_probe_results_path.resolve()
    probe_results = load_and_verify_release_provider_probe_receipt(
        probe_results_file,
        expected_endpoint_identity_sha256=capability.endpoint_identity_sha256,
        expected_source_seal_sha256=str(source_seal["seal_sha256"]),
    )
    if (
        probe_results.get("profiler_provider_capability_sha256")
        != capability.capability_sha256
    ):
        raise RuntimeError("release_profiler_capability_probe_receipt_mismatch")
    policy_path = root / "sgar_mvp" / "config" / "retrieval_policy.json"
    index_dir = root / "Pool" / "index_meta"
    base_policy = load_retrieval_policy(policy_path)
    baseline_identity = _verify_active_release_baseline(
        policy_path=policy_path,
        index_dir=index_dir,
        base_policy=base_policy,
    )
    released_policy = build_released_policy(
        source_seal=source_seal,
        index_manifest=verified["manifest"],
        index_metadata=verified["metadata"],
        provider_capability=capability,
        provider_probe_receipt=probe_results,
        base_policy=base_policy,
    )

    backup = require_release_storage_path(backup_dir, code="release_backup_outside_storage_root")
    receipt = require_release_storage_path(receipt_path, code="release_receipt_outside_storage_root")
    if backup.exists() and any(backup.iterdir()):
        raise RuntimeError("release_backup_directory_not_empty")
    backup.mkdir(parents=True, exist_ok=True)
    targets = {"retrieval_policy.json": policy_path}
    targets.update({name: index_dir / name for name in INDEX_FILE_NAMES})
    backups: dict[str, dict[str, Any]] = {}
    for name, target in targets.items():
        existed_before = target.is_file()
        if not existed_before and name not in _OPTIONAL_LEGACY_BASELINE_FILES:
            raise RuntimeError(f"release_existing_target_missing:{name}")
        details: dict[str, Any] = {
            "target_path": str(target.resolve()),
            "existed_before": existed_before,
            "backup_path": None,
            "before_sha256": None,
        }
        if existed_before:
            destination = backup / name
            _atomic_copy(target, destination)
            details.update(
                {
                    "backup_path": str(destination.resolve()),
                    "before_sha256": _sha256_file(target),
                }
            )
        backups[name] = details

    applied = 0
    try:
        for name in INDEX_FILE_NAMES:
            _atomic_copy(verified["root"] / name, index_dir / name)
            applied += 1
            if failure_inject_after == applied:
                raise RuntimeError("release_promotion_failure_injected")
        _atomic_write(policy_path, released_policy.model_dump(mode="json"))
        applied += 1
        if failure_inject_after == applied:
            raise RuntimeError("release_promotion_failure_injected")
    except BaseException:
        for name, details in backups.items():
            target = Path(details["target_path"])
            if details["existed_before"]:
                _atomic_copy(Path(details["backup_path"]), target)
            else:
                target.unlink(missing_ok=True)
        raise

    for name, details in backups.items():
        details["after_sha256"] = _sha256_file(Path(details["target_path"]))
    payload: dict[str, Any] = {
        "protocol": PROMOTION_RECEIPT_PROTOCOL,
        "status": "activated_pending_commit",
        "activation_mode": baseline_identity["activation_mode"],
        "baseline_identity": baseline_identity,
        "release_source_seal": source_seal_reference(source_seal),
        "staging_index_path": str(verified["root"]),
        "index_build_manifest_sha256": verified["manifest"]["manifest_sha256"],
        "provider_capability_sha256": capability.capability_sha256,
        "provider_probe_results_path": str(probe_results_file),
        "provider_probe_results_file_sha256": _sha256_file(probe_results_file),
        "provider_probe_results_sha256": probe_results["result_sha256"],
        "retrieval_policy_sha256": released_policy.sha256(),
        "backup_directory": str(backup),
        "files": backups,
    }
    payload["receipt_sha256"] = canonical_sha256(payload)
    _atomic_write(receipt, payload)
    return payload


def finalize_release_promotion(
    *,
    project_root: Path,
    promotion_receipt_path: Path,
    evidence_path: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    evidence = require_release_storage_path(
        evidence_path,
        code="release_finalize_evidence_outside_storage_root",
    )
    if evidence.exists():
        raise RuntimeError("release_finalize_evidence_not_fresh")
    receipt = _load_and_verify_promotion_receipt(
        project_root=root,
        promotion_receipt_path=promotion_receipt_path,
        verify_current_after_hashes=True,
        verify_backups=True,
    )
    source_ref = receipt["release_source_seal"]
    branch = _run_git(root, "branch", "--show-current")
    if not is_approved_release_branch(branch) or branch != source_ref.get("git_branch"):
        raise RuntimeError("release_finalize_branch_invalid")

    staged_before = _git_paths(
        root,
        "diff",
        "--cached",
        "--name-only",
        "-z",
        "--no-renames",
    )
    if staged_before:
        raise RuntimeError("release_finalize_preexisting_staged_changes")
    expected_targets = _expected_active_targets(root)
    files = receipt["files"]
    approved_names = sorted(
        name
        for name, details in files.items()
        if details.get("before_sha256") != details.get("after_sha256")
    )
    if not approved_names:
        raise RuntimeError("release_finalize_approved_change_set_empty")
    approved_paths = sorted(
        expected_targets[name].relative_to(root).as_posix() for name in approved_names
    )
    approved_set = set(approved_paths)
    unstaged_before = _git_paths(
        root,
        "diff",
        "--name-only",
        "-z",
        "--no-renames",
    )
    if unstaged_before != approved_set:
        raise RuntimeError("release_finalize_tracked_diff_mismatch")

    parent_head = _run_git(root, "rev-parse", "HEAD")
    try:
        _run_git(root, "add", "--", *approved_paths)
        cached = _git_paths(
            root,
            "diff",
            "--cached",
            "--name-only",
            "-z",
            "--no-renames",
        )
        if cached != approved_set:
            raise RuntimeError("release_finalize_cached_diff_mismatch")
        remaining = _git_paths(
            root,
            "diff",
            "--name-only",
            "-z",
            "--no-renames",
        )
        if remaining:
            raise RuntimeError("release_finalize_unstaged_diff_after_add")
        _load_and_verify_promotion_receipt(
            project_root=root,
            promotion_receipt_path=promotion_receipt_path,
            verify_current_after_hashes=True,
            verify_backups=True,
        )
        _run_git(root, "commit", "-m", _FINALIZE_COMMIT_MESSAGE)
    except BaseException:
        if _run_git(root, "rev-parse", "HEAD") == parent_head:
            subprocess.run(
                ["git", "restore", "--staged", "--", *approved_paths],
                cwd=root,
                check=False,
                capture_output=True,
            )
        raise

    commit_sha = _run_git(root, "rev-parse", "HEAD")
    if commit_sha == parent_head or _run_git(root, "rev-parse", "HEAD^") != parent_head:
        raise RuntimeError("release_finalize_commit_parent_invalid")
    if _git_paths(
        root,
        "diff-tree",
        "--no-commit-id",
        "--name-only",
        "-r",
        "-z",
        "HEAD",
    ) != approved_set:
        raise RuntimeError("release_finalize_commit_path_set_invalid")
    if _git_paths(
        root,
        "diff",
        "--name-only",
        "-z",
        "--no-renames",
    ) or _git_paths(
        root,
        "diff",
        "--cached",
        "--name-only",
        "-z",
        "--no-renames",
    ):
        raise RuntimeError("release_finalize_tracked_tree_not_clean")
    _load_and_verify_promotion_receipt(
        project_root=root,
        promotion_receipt_path=promotion_receipt_path,
        verify_current_after_hashes=True,
        verify_backups=True,
    )

    after_sha256: dict[str, str] = {}
    for name in approved_names:
        relative = expected_targets[name].relative_to(root).as_posix()
        expected_sha = str(files[name]["after_sha256"])
        blob = subprocess.run(
            ["git", "show", f"HEAD:./{relative}"],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout
        if hashlib.sha256(blob).hexdigest() != expected_sha:
            raise RuntimeError(f"release_finalize_committed_blob_mismatch:{name}")
        after_sha256[relative] = expected_sha

    payload: dict[str, Any] = {
        "evidence_kind": "release_promotion_finalize",
        "format_version": 1,
        "status": "committed",
        "promotion_receipt_path": str(promotion_receipt_path.resolve()),
        "promotion_receipt_file_sha256": _sha256_file(
            promotion_receipt_path.resolve()
        ),
        "promotion_receipt_sha256": receipt["receipt_sha256"],
        "parent_release_source_seal_sha256": source_ref["seal_sha256"],
        "approved_paths": approved_paths,
        "after_sha256": after_sha256,
        "parent_head": parent_head,
        "commit_sha": commit_sha,
        "commit_tree": _run_git(root, "rev-parse", "HEAD^{tree}"),
    }
    payload["evidence_sha256"] = canonical_sha256(payload)
    if evidence.exists():
        raise RuntimeError("release_finalize_evidence_not_fresh")
    _atomic_write(evidence, payload)
    return payload


def rollback_release_retrieval(*, receipt_path: Path, output_path: Path) -> dict[str, Any]:
    receipt_file = require_release_storage_path(receipt_path, code="rollback_receipt_outside_storage_root")
    payload = json.loads(receipt_file.read_text(encoding="utf-8-sig"))
    claimed = str(payload.get("receipt_sha256") or "")
    unsigned = dict(payload)
    unsigned.pop("receipt_sha256", None)
    if claimed != canonical_sha256(unsigned):
        raise RuntimeError("rollback_promotion_receipt_hash_mismatch")
    restored: dict[str, str | None] = {}
    for name, details in (payload.get("files") or {}).items():
        target = Path(str(details["target_path"])).resolve()
        # Receipts created before the legacy-absence field existed described
        # only files that had backups, so absence of the field means True.
        if details.get("existed_before", True) is False:
            target.unlink(missing_ok=True)
            restored[name] = None
            continue
        source = require_release_storage_path(
            Path(str(details["backup_path"])),
            code="rollback_backup_outside_storage_root",
        )
        if _sha256_file(source) != details["before_sha256"]:
            raise RuntimeError(f"rollback_backup_hash_mismatch:{name}")
        _atomic_copy(source, target)
        restored[name] = _sha256_file(target)
    rollback: dict[str, Any] = {
        "protocol": ROLLBACK_RECEIPT_PROTOCOL,
        "status": "rolled_back",
        "promotion_receipt_sha256": claimed,
        "restored_files_sha256": restored,
    }
    rollback["receipt_sha256"] = canonical_sha256(rollback)
    _atomic_write(
        require_release_storage_path(output_path, code="rollback_output_outside_storage_root"),
        rollback,
    )
    return rollback


__all__ = [
    "INDEX_FILE_NAMES",
    "PROMOTION_RECEIPT_PROTOCOL",
    "ROLLBACK_RECEIPT_PROTOCOL",
    "_verify_active_release_baseline",
    "build_released_policy",
    "finalize_release_promotion",
    "promote_release_retrieval",
    "rebind_release_index_generation",
    "rollback_release_retrieval",
]
