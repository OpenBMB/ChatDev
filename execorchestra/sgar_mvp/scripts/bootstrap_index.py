"""Build a complete unsealed local index using the configured embedding API."""

from __future__ import annotations

import argparse
import hashlib
import json
import pickle
from pathlib import Path

import faiss
import numpy as np

from build_index import (
    CATALOG_FILE,
    PROJECT_ROOT,
    RESOURCES_FILE,
    _canonical_json_sha256,
    _sha256_file,
    _validate_vector_contract,
    build_faiss_index,
    build_metadata,
    deduplicate_exact_skill_packages,
    filter_indexable_resources,
    load_resources,
)
from retrieval_profiles import PROFILE_VERSION, build_constraint_profile, validate_resource_profiles
from sgar_mvp.src.embedding_runtime import LocalEmbeddingEncoder, load_embedding_release_config
from sgar_mvp.src.pipeline_control import canonical_sha256
from sgar_mvp.src.retrieval_policy import RetrievalPolicy


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def build(config_path: Path, output_dir: Path) -> dict:
    config = load_embedding_release_config(config_path.resolve())
    if config.backend != "openai_compatible":
        raise ValueError("local_api_build_requires_openai_compatible_config")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("local_api_output_directory_not_empty")
    # This unsealed Git bootstrap consumes prepare_release.readiness output.
    # build_index's legacy default belongs to the separate frozen experiment.
    readiness_path = PROJECT_ROOT / "sgar_mvp/config/resource_readiness_rc1.json"
    readiness_bytes = readiness_path.read_bytes()
    readiness = json.loads(readiness_bytes.decode("utf-8-sig"))
    raw_resources = filter_indexable_resources(load_resources(RESOURCES_FILE))
    allowed_ids = set(readiness.get("effective_resource_ids") or [])
    if {item["resource_id"] for item in raw_resources} != allowed_ids:
        raise ValueError("effective_catalog_readiness_mismatch")
    load_resources(CATALOG_FILE)
    audit = validate_resource_profiles(raw_resources, PROJECT_ROOT)
    resources, duplicate_aliases = deduplicate_exact_skill_packages(raw_resources)
    audit["indexed_resource_count"] = len(resources)
    audit["duplicate_resource_aliases"] = duplicate_aliases
    if audit["errors"]:
        raise ValueError("core_retrieval_profile_validation_failed")
    profiles = [build_constraint_profile(resource) for resource in resources]
    encoder = LocalEmbeddingEncoder(config)
    identity = encoder.identity()
    identity_v2 = encoder.runtime_identity_v2()
    encoder.load()
    cap_vectors = encoder.encode_documents([item.capability_text for item in profiles], batch_size=16)
    con_vectors = encoder.encode_documents([item.soft_constraint_text for item in profiles], batch_size=16)
    encoder.close()
    _validate_vector_contract(cap_vectors, con_vectors, expected_rows=len(resources), expected_dimension=config.output_dimension)
    metadata = build_metadata(
        resources, cap_vectors, con_vectors, duplicate_aliases,
        readiness=readiness,
        readiness_hash="sha256:" + hashlib.sha256(readiness_bytes).hexdigest(),
        embedding_config=config,
        embedding_identity=identity.model_dump(mode="json"),
        embedding_runtime_identity_v2=identity_v2.model_dump(mode="json"),
        source_seal=None,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    faiss.write_index(build_faiss_index(cap_vectors), str(output_dir / "faiss_cap.index"))
    faiss.write_index(build_faiss_index(con_vectors), str(output_dir / "faiss_con.index"))
    (output_dir / "resource_meta.pkl").write_bytes(pickle.dumps(metadata, protocol=pickle.HIGHEST_PROTOCOL))
    _write(output_dir / "retrieval_profile_audit.json", audit)
    files = {name: _sha256_file(output_dir / name) for name in ("faiss_cap.index", "faiss_con.index", "resource_meta.pkl", "retrieval_profile_audit.json")}
    generation_id = canonical_sha256({"embedding": identity_v2.identity_sha256, "files": files, "resource_order": metadata["resource_order_sha256"]})[:32]
    manifest = {
        "protocol": "sgar-retrieval-index-build-v1",
        "generation_kind": "local_model_pool_full_rebuild",
        "generation_id": generation_id,
        "release_source_seal": None,
        "catalog_sha256": _sha256_file(CATALOG_FILE),
        "effective_pool_sha256": _sha256_file(RESOURCES_FILE),
        "embedding_configuration_sha256": config.configuration_sha256,
        "embedding_identity_sha256": identity.identity_sha256,
        "embedding_runtime_identity_v2_sha256": identity_v2.identity_sha256,
        "index_meta_v2_sha256": metadata["index_meta_v2"]["index_meta_sha256"],
        "resource_count": len(resources),
        "resource_order_sha256": metadata["resource_order_sha256"],
        "dimension": metadata["dim"],
        "files_sha256": {key: value for key, value in files.items() if key != "retrieval_profile_audit.json"},
        "build_code_sha256": _sha256_file(Path(__file__).resolve()),
    }
    manifest["manifest_sha256"] = canonical_sha256(manifest)
    _write(output_dir / "index_build_manifest.json", manifest)
    policy = _read(PROJECT_ROOT / "sgar_mvp/config/retrieval_policy.json")
    policy.update(
        policy_version="retrieval-policy-v7-local-" + generation_id,
        embedding_candidate_id=config.candidate_id,
        embedding_model=config.model_id,
        embedding_runtime_identity_sha256=identity_v2.identity_sha256,
        index_meta_sha256=metadata["index_meta_v2"]["index_meta_sha256"],
        index_build_manifest_sha256=manifest["manifest_sha256"],
        release_source_seal_sha256=None,
        effective_pool_sha256=manifest["effective_pool_sha256"],
        index_sha256={"capability": files["faiss_cap.index"], "constraint": files["faiss_con.index"], "metadata": files["resource_meta.pkl"]},
    )
    from scripts.prepare_release import bind_control_identity
    policy = bind_control_identity(policy)
    RetrievalPolicy.model_validate(policy)
    _write(output_dir / "retrieval_policy.json", policy)
    return {"output_dir": str(output_dir), "resource_count": len(resources), "dimension": config.output_dimension, "generation_id": generation_id, "embedding_identity_sha256": identity_v2.identity_sha256}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--embedding-config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.embedding_config, args.output_dir), indent=2))
