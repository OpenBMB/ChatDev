"""Build the S-GAR dual-vector FAISS index.

``v_cap`` and ``v_con`` are intentionally generated from different textual
views.  Hard executability requirements and utility metrics are stored as index
metadata and never embedded into the constraint vector.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import pickle
import uuid
from pathlib import Path
from typing import Any, Dict, List

import certifi
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from sgar_mvp.src.bge_encoding import (
    prepare_passage_texts,
)
from sgar_mvp.src.embedding_runtime import (
    EmbeddingRuntimeIdentityV2,
    EmbeddingRuntimeConfigV1,
    IndexMetaV2,
    LocalEmbeddingEncoder,
    load_embedding_release_config,
)
from sgar_mvp.src.capability_cards import build_capability_consistency_report
from sgar_mvp.src.retrieval_policy import load_retrieval_policy
from sgar_mvp.src.release_environment import require_release_storage_path
from sgar_mvp.src.release_source_seal import (
    load_and_verify_source_seal,
    source_seal_reference,
)

from retrieval_profiles import (
    PROFILE_VERSION,
    build_constraint_profile,
    deduplicate_exact_skill_packages,
    validate_resource_profiles,
)


PROJECT_ROOT = Path(__file__).resolve().parent
CATALOG_FILE = PROJECT_ROOT / "Pool" / "resources" / "json" / "combine.json"
RESOURCES_FILE = PROJECT_ROOT / "Pool" / "resources" / "json" / "effective_combine.json"
# The active pool is the frozen R_exp v1.3 projection.  The RC1 readiness
# report is retained for historical maintenance and must not feed a new index.
READINESS_FILE = PROJECT_ROOT / "sgar_mvp" / "config" / "r_exp_v1_3_readiness.json"
INDEX_DIR = PROJECT_ROOT / "Pool" / "index_meta"
CAP_INDEX_FILE = INDEX_DIR / "faiss_cap.index"
CON_INDEX_FILE = INDEX_DIR / "faiss_con.index"
METADATA_FILE = INDEX_DIR / "resource_meta.pkl"
AUDIT_FILE = INDEX_DIR / "retrieval_profile_audit.json"
BUILD_MANIFEST_FILE = INDEX_DIR / "index_build_manifest.json"
EMBEDDING_RELEASE_CONFIG_FILE = (
    PROJECT_ROOT / "sgar_mvp" / "config" / "embedding_release.json"
)
_FORMAL_RETRIEVAL_POLICY = load_retrieval_policy()
EMBED_MODEL = _FORMAL_RETRIEVAL_POLICY.embedding_model

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)


def load_resources(path: Path = RESOURCES_FILE) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON array")
    # Empty legacy aggregate entries are never valid retrievable resources.
    resources = [item for item in payload if isinstance(item, dict) and item.get("resource_id")]
    from sgar_mvp.src.model_selection import require_registered_models
    require_registered_models(resources)
    print(f"[build_index] Loaded {len(resources)} valid resources")
    return resources


NON_INDEXABLE_STATUSES = {"inactive", "disabled", "unavailable"}


def is_indexable_resource(resource: dict) -> bool:
    from sgar_mvp.src.model_selection import is_candidate_resource
    if not is_candidate_resource(resource):
        return False
    status = str(resource.get("status") or "").strip().lower()
    execution = resource.get("execution")
    if not isinstance(execution, dict):
        execution = {}
    execution_status = str(execution.get("execution_status") or "").strip().lower()
    return bool(resource.get("resource_id")) and not (
        status in NON_INDEXABLE_STATUSES
        or execution_status in NON_INDEXABLE_STATUSES
    )


def filter_indexable_resources(resources: list[dict]) -> list[dict]:
    return [resource for resource in resources if is_indexable_resource(resource)]


def resource_to_cap_text(resource: Dict[str, Any]) -> str:
    """Backward-compatible public helper used by existing audits/tests."""

    if not isinstance(resource.get("capability"), dict):
        return str(resource.get("resource_id") or resource.get("id") or "")
    return build_constraint_profile(resource).capability_text


def resource_to_con_text(resource: Dict[str, Any]) -> str:
    """Backward-compatible public helper for the typed soft-constraint view."""

    if not isinstance(resource.get("constraint"), dict):
        return str(resource.get("resource_id") or resource.get("id") or "")
    return build_constraint_profile(resource).soft_constraint_text


def embed_passages(texts: List[str], model: SentenceTransformer) -> np.ndarray:
    vectors = model.encode(
        prepare_passage_texts(texts),
        batch_size=16,
        show_progress_bar=True,
        normalize_embeddings=True,
    )
    return np.asarray(vectors, dtype="float32")


def embed_texts(texts: List[str], model: SentenceTransformer) -> np.ndarray:
    """Backward-compatible alias with corrected passage semantics."""

    return embed_passages(texts, model)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_vector_contract(
    cap_vectors: np.ndarray,
    con_vectors: np.ndarray,
    *,
    expected_rows: int,
    expected_dimension: int,
) -> None:
    if cap_vectors.shape != con_vectors.shape:
        raise ValueError(
            "Capability/constraint vector shape mismatch: "
            f"{cap_vectors.shape} != {con_vectors.shape}"
        )
    if cap_vectors.shape != (expected_rows, expected_dimension):
        raise ValueError(
            "Embedding output/index shape mismatch: "
            f"{cap_vectors.shape} != {(expected_rows, expected_dimension)}"
        )
    if not np.isfinite(cap_vectors).all() or not np.isfinite(con_vectors).all():
        raise ValueError("Embedding vectors contain non-finite values")
    for name, vectors in (("capability", cap_vectors), ("constraint", con_vectors)):
        norms = np.linalg.norm(vectors, axis=1)
        if not np.allclose(norms, np.ones_like(norms), rtol=1e-4, atol=1e-4):
            raise ValueError(f"{name} vectors are not L2-normalized")


def _commit_index_generation(
    *,
    output_dir: Path,
    cap_index: faiss.Index,
    con_index: faiss.Index,
    metadata: Dict[str, Any],
    audit: Dict[str, Any],
    source_seal: Dict[str, Any],
) -> Dict[str, Any]:
    """Commit a complete index generation with a last-written hash manifest."""

    output_dir.mkdir(parents=True, exist_ok=True)
    temporary_token = uuid.uuid4().hex
    destinations = {
        CAP_INDEX_FILE.name: output_dir / CAP_INDEX_FILE.name,
        CON_INDEX_FILE.name: output_dir / CON_INDEX_FILE.name,
        METADATA_FILE.name: output_dir / METADATA_FILE.name,
        AUDIT_FILE.name: output_dir / AUDIT_FILE.name,
    }
    temporary = {
        name: destination.with_name(f".{destination.name}.{temporary_token}.tmp")
        for name, destination in destinations.items()
    }
    manifest_path = output_dir / BUILD_MANIFEST_FILE.name
    manifest_tmp = manifest_path.with_name(
        f".{manifest_path.name}.{temporary_token}.tmp"
    )
    try:
        faiss.write_index(cap_index, str(temporary[CAP_INDEX_FILE.name]))
        faiss.write_index(con_index, str(temporary[CON_INDEX_FILE.name]))
        temporary[METADATA_FILE.name].write_bytes(
            pickle.dumps(metadata, protocol=pickle.HIGHEST_PROTOCOL)
        )
        temporary[AUDIT_FILE.name].write_text(
            json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        file_hashes = {
            name: _sha256_file(path) for name, path in temporary.items()
        }
        generation_id = _canonical_json_sha256(
            {
                "embedding_configuration_sha256": metadata[
                    "embedding_runtime_config"
                ]["configuration_sha256"],
                "embedding_identity_sha256": metadata[
                    "embedding_runtime_identity"
                ]["identity_sha256"],
                "resource_order_sha256": metadata["resource_order_sha256"],
                "release_source_seal_sha256": source_seal["seal_sha256"],
                "files_sha256": file_hashes,
            }
        )[:32]
        manifest = {
            "protocol": "sgar-retrieval-index-build-v1",
            "generation_id": generation_id,
            "embedding_configuration_sha256": metadata[
                "embedding_runtime_config"
            ]["configuration_sha256"],
            "embedding_identity_sha256": metadata[
                "embedding_runtime_identity"
            ]["identity_sha256"],
            "embedding_runtime_identity_v2_sha256": metadata[
                "embedding_runtime_identity_v2"
            ]["identity_sha256"],
            "index_meta_v2_sha256": metadata["index_meta_v2"][
                "index_meta_sha256"
            ],
            "resource_count": len(metadata["idx_to_id"]),
            "resource_order_sha256": metadata["resource_order_sha256"],
            "dimension": int(metadata["dim"]),
            "release_source_seal": source_seal_reference(source_seal),
            "build_code_sha256": _sha256_file(Path(__file__).resolve()),
            "files_sha256": file_hashes,
        }
        manifest["manifest_sha256"] = _canonical_json_sha256(manifest)
        manifest_tmp.write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        for name, destination in destinations.items():
            temporary[name].replace(destination)
        manifest_tmp.replace(manifest_path)
        return manifest
    finally:
        for path in (*temporary.values(), manifest_tmp):
            if path.exists():
                path.unlink()


def build_faiss_index(vectors: np.ndarray) -> faiss.Index:
    if len(vectors.shape) != 2 or vectors.shape[0] == 0:
        raise ValueError("Cannot build a FAISS index from an empty/non-matrix vector set")
    index = faiss.IndexFlatIP(int(vectors.shape[1]))
    index.add(vectors)
    return index


def build_metadata(
    resources: List[Dict[str, Any]],
    cap_vectors: np.ndarray,
    con_vectors: np.ndarray,
    duplicate_aliases: Dict[str, str],
    *,
    readiness: Dict[str, Any],
    readiness_hash: str,
    embedding_config: EmbeddingRuntimeConfigV1 | None = None,
    embedding_identity: Dict[str, Any] | None = None,
    embedding_runtime_identity_v2: Dict[str, Any] | None = None,
    source_seal: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    profiles = [build_constraint_profile(resource) for resource in resources]
    runtime_config = embedding_config or load_embedding_release_config(
        EMBEDDING_RELEASE_CONFIG_FILE
    )
    resource_ids = tuple(resource["resource_id"] for resource in resources)
    runtime_identity_v2 = (
        EmbeddingRuntimeIdentityV2.model_validate(embedding_runtime_identity_v2)
        if embedding_runtime_identity_v2
        else None
    )
    index_meta_v2 = (
        IndexMetaV2(
            embedding_runtime_identity=runtime_identity_v2,
            resource_manifest_sha256=_canonical_json_sha256(resources),
            resource_id_order=resource_ids,
            resource_id_order_sha256=_canonical_json_sha256(resource_ids),
            capability_vectors_sha256=hashlib.sha256(
                np.ascontiguousarray(cap_vectors, dtype="float32").tobytes()
            ).hexdigest(),
            constraint_vectors_sha256=hashlib.sha256(
                np.ascontiguousarray(con_vectors, dtype="float32").tobytes()
            ).hexdigest(),
            faiss_dimension=int(cap_vectors.shape[1]),
            vector_count=int(cap_vectors.shape[0]),
        ).model_dump(mode="json")
        if runtime_identity_v2 is not None
        else {}
    )
    return {
        "schema_version": 3,
        "profile_version": PROFILE_VERSION,
        "embedding_model": runtime_config.model_id,
        "bge_prefix": (
            runtime_config.capability_query_instruction
            if runtime_config.family == "bge"
            else ""
        ),
        "query_prefix": runtime_config.capability_query_instruction,
        "passage_prefix": runtime_config.document_instruction,
        "encoding_policy_version": runtime_config.protocol,
        "embedding_runtime_config": runtime_config.model_dump(mode="json"),
        "embedding_runtime_identity": embedding_identity or {},
        "embedding_runtime_identity_v2": embedding_runtime_identity_v2 or {},
        "index_meta_v2": index_meta_v2,
        "catalog_sha256": readiness.get("catalog_sha256"),
        "readiness_report_sha256": readiness_hash,
        "model_health_sha256": readiness.get("evidence", {}).get("model_health_sha256"),
        "docker_image": readiness.get("evidence", {}).get("docker_image"),
        "docker_image_id": readiness.get("evidence", {}).get("docker_image_id"),
        "docker_repo_digests": readiness.get("evidence", {}).get("docker_repo_digests", []),
        "id_to_resource": {resource["resource_id"]: resource for resource in resources},
        "idx_to_id": {index: resource["resource_id"] for index, resource in enumerate(resources)},
        "id_to_idx": {resource["resource_id"]: index for index, resource in enumerate(resources)},
        "resource_order_sha256": _canonical_json_sha256(
            resource_ids
        ),
        "cap_vectors": cap_vectors.tolist(),
        "con_vectors": con_vectors.tolist(),
        "dim": int(cap_vectors.shape[1]),
        "capability_texts": {
            profile.resource_id: profile.capability_text for profile in profiles
        },
        "constraint_texts": {
            profile.resource_id: profile.soft_constraint_text for profile in profiles
        },
        "hard_requirements": {
            profile.resource_id: profile.hard_requirements for profile in profiles
        },
        "utility_profiles": {
            profile.resource_id: profile.utility_profile for profile in profiles
        },
        "manifest_hashes": {
            profile.resource_id: profile.manifest_hash for profile in profiles
        },
        "duplicate_resource_aliases": duplicate_aliases,
        "release_source_seal": (
            source_seal_reference(source_seal) if source_seal is not None else None
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build typed S-GAR dual-vector indices")
    parser.add_argument(
        "--allow-core-profile-errors",
        action="store_true",
        help="Write an index despite Model/Agent/Skill/Resource validation errors.",
    )
    parser.add_argument(
        "--release-source-seal",
        type=Path,
        required=True,
        help="ReleaseSourceSealV1 that binds this complete fresh index generation.",
    )
    parser.add_argument(
        "--embedding-release-config",
        type=Path,
        default=EMBEDDING_RELEASE_CONFIG_FILE,
        help="Fixed Qwen release configuration; model weights must already be local.",
    )
    parser.add_argument(
        "--resources-file",
        type=Path,
        default=RESOURCES_FILE,
        help="Readiness-gated effective catalog to index.",
    )
    parser.add_argument(
        "--readiness-report",
        type=Path,
        default=READINESS_FILE,
        help="RC1 readiness report authorizing every indexed resource.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="New empty version directory under SGAR_RELEASE_STORAGE_ROOT; formal promotion is separate.",
    )
    args = parser.parse_args()

    source_seal_path = args.release_source_seal.expanduser().resolve()
    source_seal = load_and_verify_source_seal(
        source_seal_path,
        project_root=PROJECT_ROOT,
        allowed_stages=("release",),
    )
    embedding_config = load_embedding_release_config(
        args.embedding_release_config.resolve()
    )

    output_dir = require_release_storage_path(
        args.output_dir, code="formal_index_staging_directory_outside_storage_root"
    )
    if output_dir == INDEX_DIR.resolve():
        raise ValueError("formal_index_build_must_use_versioned_staging_directory")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("versioned_index_output_directory_not_empty")
    cap_index_file = output_dir / CAP_INDEX_FILE.name
    con_index_file = output_dir / CON_INDEX_FILE.name
    metadata_file = output_dir / METADATA_FILE.name
    audit_file = output_dir / AUDIT_FILE.name

    readiness_bytes = args.readiness_report.read_bytes()
    readiness = json.loads(readiness_bytes.decode("utf-8-sig"))
    allowed_ids = set(readiness.get("effective_resource_ids") or [])
    from sgar_mvp.src.model_selection import require_admitted_candidate_models
    model_health = json.loads((PROJECT_ROOT / "sgar_mvp/runtime_state/model_ready_state.json").read_text(encoding="utf-8-sig"))
    if (readiness.get("evidence") or {}).get("model_health_sha256") != model_health.get("health_sha256"):
        raise ValueError("index_readiness_health_identity_mismatch")
    supplied_resources = load_resources(args.resources_file)
    require_admitted_candidate_models(supplied_resources, model_health, root=PROJECT_ROOT)
    raw_resources = filter_indexable_resources(supplied_resources)
    canonical_resources = load_resources(CATALOG_FILE)
    catalog_consistency = build_capability_consistency_report(
        {
            str(item["resource_id"]): item
            for item in canonical_resources
        }
    )
    if catalog_consistency.sealable_resource_count != catalog_consistency.resource_count:
        failures = [
            f"{item.resource_id}:{','.join(item.issue_codes)}"
            for item in catalog_consistency.items
            if not item.sealable
        ]
        raise ValueError(
            "Canonical resource catalog is not execution-ready and English: "
            + "; ".join(failures[:20])
        )
    actual_ids = {item["resource_id"] for item in raw_resources}
    if actual_ids != allowed_ids:
        missing = sorted(allowed_ids - actual_ids)
        unexpected = sorted(actual_ids - allowed_ids)
        raise ValueError(
            "Effective catalog/readiness mismatch: "
            f"missing={missing[:20]}, unexpected={unexpected[:20]}"
        )
    if any(
        item.get("resource_type") == "Resource"
        or item.get("type", {}).get("resource_type") == "Resource"
        for item in raw_resources
    ):
        raise ValueError("RC1 effective catalog must not contain Resource entries")
    audit = validate_resource_profiles(raw_resources, PROJECT_ROOT)
    resources, duplicate_aliases = deduplicate_exact_skill_packages(raw_resources)
    audit["indexed_resource_count"] = len(resources)
    audit["duplicate_resource_aliases"] = duplicate_aliases

    if audit["errors"] and not args.allow_core_profile_errors:
        examples = ", ".join(
            f"{item['resource_id']}:{item['code']}" for item in audit["errors"][:10]
        )
        raise ValueError(
            "Core retrieval-profile validation failed. "
            f"No index generation was committed. Examples: {examples}"
        )

    profiles = [build_constraint_profile(resource) for resource in resources]
    cap_texts = [profile.capability_text for profile in profiles]
    con_texts = [profile.soft_constraint_text for profile in profiles]
    print(f"[build_index] Profile version: {PROFILE_VERSION}")
    print(f"[build_index] Exact duplicate Skill aliases: {len(duplicate_aliases)}")

    print("[build_index] Resolving pinned local Qwen embedding model...")
    embedding_runtime = LocalEmbeddingEncoder(embedding_config)
    embedding_identity = embedding_runtime.identity()
    embedding_identity_v2 = embedding_runtime.runtime_identity_v2()
    print(
        "[build_index] Loading offline embedding snapshot "
        f"{embedding_identity.local_snapshot_locator}"
    )
    embedding_runtime.load()
    print("[build_index] Encoding capability vectors...")
    cap_vectors = embedding_runtime.encode_documents(cap_texts, batch_size=16)
    print("[build_index] Encoding soft-constraint vectors...")
    con_vectors = embedding_runtime.encode_documents(con_texts, batch_size=16)
    _validate_vector_contract(
        cap_vectors,
        con_vectors,
        expected_rows=len(resources),
        expected_dimension=embedding_config.output_dimension,
    )

    cap_index = build_faiss_index(cap_vectors)
    con_index = build_faiss_index(con_vectors)
    metadata = build_metadata(
        resources,
        cap_vectors,
        con_vectors,
        duplicate_aliases,
        readiness=readiness,
        readiness_hash="sha256:" + hashlib.sha256(readiness_bytes).hexdigest(),
        embedding_config=embedding_config,
        embedding_identity=embedding_identity.model_dump(mode="json"),
        embedding_runtime_identity_v2=embedding_identity_v2.model_dump(mode="json"),
        source_seal=source_seal,
    )

    source_seal = load_and_verify_source_seal(
        source_seal_path,
        project_root=PROJECT_ROOT,
        allowed_stages=("release",),
    )
    current_health = json.loads((PROJECT_ROOT / "sgar_mvp/runtime_state/model_ready_state.json").read_text(encoding="utf-8-sig"))
    if current_health.get("health_sha256") != model_health["health_sha256"]:
        raise ValueError("index_health_changed_during_build")
    require_admitted_candidate_models(resources, current_health, root=PROJECT_ROOT)
    manifest = _commit_index_generation(
        output_dir=output_dir,
        cap_index=cap_index,
        con_index=con_index,
        metadata=metadata,
        audit=audit,
        source_seal=source_seal,
    )

    print(
        "[build_index] Saved "
        f"{cap_index.ntotal} resources, dim={metadata['dim']}, "
        f"profile={PROFILE_VERSION}"
    )
    print(f"[build_index] Audit: {audit_file}")
    print(
        "[build_index] Generation manifest: "
        f"{output_dir / BUILD_MANIFEST_FILE.name} "
        f"({manifest['manifest_sha256']})"
    )
    print(f"[build_index] Output directory: {output_dir}")


if __name__ == "__main__":
    main()
