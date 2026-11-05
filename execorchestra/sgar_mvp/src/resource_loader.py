"""
S-GAR Resource Loader — Bridge between Pool/resources/json/combine.json and MVP
================================================================================
Replaces the original load_model_pool() and _mock_embedding() in main.py.

Reads the real V2 Schema resources from combine.json, binds precomputed local
embeddings via retrieve.py, and constructs Manifest objects for the Router.
"""

from __future__ import annotations

import os
import sys
import json

# Add project root to path so we can import retrieve
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
DEFAULT_MODEL_HEALTH_GATE = os.path.join(
    PROJECT_ROOT, "sgar_mvp", "config", "model_health.json"
)

from loguru import logger
from typing import Any, Dict, List, Mapping, Tuple

from .model_accounting import RunCostLedger

from .schema import (
    Manifest,
    ManifestType,
    QueryRetrievalProfile,
    Utility,
    Vector,
)
from .capability_operations import validate_tool_manifest_operations
from .execution_contracts import validate_tool_execution_contract
from .capability_cards import (
    CapabilityCard,
    build_capability_cards,
    select_capability_cards,
)


# ─── Extended ManifestType Mapping ────────────
# Maps our V2 resource_type strings to ManifestType enum values
_TYPE_MAP = {
    "Model":    ManifestType.MODEL,
    "Agent":    ManifestType.AGENT,
    "MAS":      ManifestType.AGENT,
    "MultiAgentSystem": ManifestType.AGENT,
    "Skill":    ManifestType.SKILL,
    "Tool":     ManifestType.TOOL,
    "Resource": ManifestType.RESOURCE,
    "Device":   ManifestType.DEVICE,
}


def _load_current_resource_index() -> Dict[str, Dict[str, Any]]:
    """Load current raw manifests so runtime routing reflects edited resource JSON."""
    combine_path = os.path.join(PROJECT_ROOT, "Pool", "resources", "json", "combine.json")
    if not os.path.exists(combine_path):
        return {}

    with open(combine_path, "r", encoding="utf-8-sig") as f:
        raw_resources = json.load(f)

    if not isinstance(raw_resources, list) or not all(isinstance(r, dict) for r in raw_resources):
        raise ValueError("resource_catalog_schema_invalid")
    index: Dict[str, Dict[str, Any]] = {}
    for item in raw_resources:
        resource_id = item.get("resource_id") or item.get("id")
        if resource_id:
            if resource_id in index:
                raise ValueError(f"resource_catalog_duplicate_id:{resource_id}")
            legacy_type = item.get("type")
            legacy_type = legacy_type.get("resource_type") if isinstance(legacy_type, Mapping) else None
            canonical_type = item.get("resource_type")
            if canonical_type and legacy_type and canonical_type != legacy_type:
                raise ValueError(f"resource_catalog_type_conflict:{resource_id}")
            resource_type = canonical_type or legacy_type or "Tool"
            if resource_type == "Tool":
                valid, errors = validate_tool_manifest_operations(item)
                if not valid:
                    raise ValueError(
                        f"Invalid capability operation declaration for {resource_id}: {', '.join(errors)}"
                    )
                valid, errors = validate_tool_execution_contract(item)
                if not valid:
                    raise ValueError(
                        f"Invalid Tool execution contract for {resource_id}: {', '.join(errors)}"
                    )
            index[resource_id] = item
    from .model_selection import require_registered_models
    require_registered_models(index.values(), root=PROJECT_ROOT, complete=True)
    return index


def load_resource_index_static() -> Dict[str, Dict[str, Any]]:
    """Load raw manifests without initializing embeddings or retrieval state.

    Framework conformance and offline Plan replay require manifest contracts,
    but must remain network-free and must not instantiate an encoder.  Formal
    retrieval continues to use ``load_real_pool_with_index``.
    """

    return _load_current_resource_index()


def _load_unavailable_model_ids(
    health_path: str = DEFAULT_MODEL_HEALTH_GATE,
) -> set[str]:
    """Do not let an endpoint-unbound snapshot delete formal candidates.

    Endpoint and freshness validation is performed by ``RetrievalRuntimeIdentity``;
    live pre-freeze probing is the authoritative availability gate.  This loader
    therefore preserves pool membership and ranking for that later decision.
    """
    if not os.path.exists(health_path):
        return set()

    try:
        with open(health_path, "r", encoding="utf-8-sig") as f:
            payload = json.load(f)
    except Exception as exc:
        logger.warning(f"[ResourceLoader] Ignoring unreadable model health gate: {exc}")
        return set()

    return set()


def _model_api_id_from_raw(raw: Dict[str, Any]) -> str | None:
    if not isinstance(raw, dict):
        return None
    type_specific = raw.get("type_specific", {})
    model_block = type_specific.get("model", {}) if isinstance(type_specific, dict) else {}
    execution = raw.get("execution", {}) if isinstance(raw.get("execution", {}), dict) else {}
    return (
        model_block.get("model_id")
        or execution.get("model_id")
        or execution.get("default_base_model")
    )


def _manifest_from_raw(
    resource_id: str,
    raw: Dict[str, Any],
    cap_vec: List[float],
    con_vec: List[float],
    dim: int,
) -> Manifest:
    resource_type = raw.get("type", {}).get("resource_type") or raw.get("resource_type", "Tool")
    manifest_type = _TYPE_MAP.get(resource_type, ManifestType.TOOL)

    util = raw.get("utility", {})
    latency = util.get("latency_ms", 100.0)
    cost = util.get("token_cost_factor", 0.01)
    success = util.get("expected_success_rate", 0.5)
    attempts = int(util.get("attempts") or 0)
    memory = raw.get("memory", {}) if isinstance(raw.get("memory", {}), dict) else {}
    trajectory_count = len(memory.get("success_trajectories", []) or []) + len(
        memory.get("failure_reflections", []) or []
    )
    empirical_success = attempts > 0 and trajectory_count >= attempts

    # Avoid zero cost/latency causing unstable advantage scores.
    if cost <= 0:
        # Unknown price must be neutral, not an artificial near-zero advantage.
        cost = 0.5
    if not empirical_success:
        success = 0.5
    elif success <= 0:
        success = 0.5
    if latency <= 0:
        latency = 10.0

    from .schema import CapabilityMatrix
    caps = None
    if manifest_type == ManifestType.MODEL:
        caps = CapabilityMatrix(cost_level=2, code_score=0.5, logic_score=0.5)

    return Manifest(
        id=resource_id,
        type=manifest_type,
        v_cap=Vector(embedding=cap_vec, dim=dim),
        v_con=Vector(embedding=con_vec, dim=dim),
        utility=Utility(
            latency_ms=latency,
            cost_factor=cost,
            success_rate=success,
        ),
        capabilities=caps,
    )


def _validate_indexed_projection(raw: Mapping[str, Any], metadata: Mapping[str, Any]) -> None:
    """Reject stale retrieval views before pairing current manifests with vectors.

    Utility, health observations, and provenance are not embedded. Comparing the
    projected views avoids requiring a rebuild for unrelated bookkeeping alone.
    """
    from retrieval_profiles import PROFILE_VERSION, build_constraint_profile

    profile = build_constraint_profile(raw)
    if metadata.get("profile_version") != PROFILE_VERSION:
        raise ValueError("resource_index_profile_version_mismatch")
    for key, expected in (("capability_texts", profile.capability_text),
                          ("constraint_texts", profile.soft_constraint_text),
                          ("hard_requirements", profile.hard_requirements)):
        stored = metadata.get(key)
        if not isinstance(stored, Mapping) or profile.resource_id not in stored:
            raise ValueError(f"resource_index_projection_missing:{profile.resource_id}:{key}")
        if stored[profile.resource_id] != expected:
            raise ValueError(f"resource_index_projection_stale:{profile.resource_id}:{key}")


def _load_real_pool_internal() -> Tuple[List[Manifest], List[str], Dict[str, Dict[str, Any]]]:
    """
    Load the real resource pool with matching precomputed local embeddings.

    Returns:
        (manifests, fallback_model_ids, resource_index)
    """
    import retrieve

    # Ensure the retrieval engine is loaded (loads FAISS + metadata)
    retrieve._engine.ensure_loaded()

    resources = retrieve.get_all_resources()
    index_metadata = retrieve.get_index_metadata()
    duplicate_aliases = index_metadata.get("duplicate_resource_aliases", {})
    current_resource_index = _load_current_resource_index()
    unavailable_model_ids = _load_unavailable_model_ids()
    dim = retrieve.get_embedding_dim()

    manifests = []
    fallback_ids = []
    resource_index: Dict[str, Dict[str, Any]] = {}

    for r in resources:
        resource_id = r["resource_id"]
        # combine.json is authoritative for pool membership: a resource that was
        # removed from combine.json (e.g. tools pruned from the pool) is dropped
        # even if a stale vector still exists in the FAISS index.
        raw = current_resource_index.get(resource_id)
        if raw is None:
            continue
        resource_type = raw.get("type", {}).get("resource_type") or raw.get("resource_type", "Tool")
        model_api_id = _model_api_id_from_raw(raw)
        if resource_type == "Model" and (
            resource_id in unavailable_model_ids or model_api_id in unavailable_model_ids
        ):
            logger.warning(
                "[ResourceLoader] Skipping unavailable model from health gate: {}",
                model_api_id or resource_id,
            )
            continue
        resource_index[resource_id] = raw

        _validate_indexed_projection(raw, index_metadata)
        # Get pre-computed real vectors
        cap_vec, con_vec = retrieve.get_resource_vectors(resource_id)

        manifest = _manifest_from_raw(resource_id, raw, cap_vec, con_vec, dim)
        manifests.append(manifest)

        # Collect model IDs as fallbacks
        from .model_selection import is_candidate_resource
        if resource_type == "Model" and is_candidate_resource(raw):
            fallback_ids.append(resource_id)

    indexed_ids = {m.id for m in manifests}
    excluded_catalog_ids = sorted(
        resource_id
        for resource_id in current_resource_index
        if resource_id not in indexed_ids and resource_id not in duplicate_aliases
    )
    if excluded_catalog_ids:
        logger.info(
            "[ResourceLoader] {} catalog resources are intentionally absent from "
            "the effective index; no zero-vector fallback was created",
            len(excluded_catalog_ids),
        )

    logger.info(
        f"[ResourceLoader] Loaded {len(manifests)} real resources "
        f"(dim={dim}), {len(fallback_ids)} indexed models"
    )
    return manifests, fallback_ids, resource_index


def load_real_pool() -> Tuple[List[Manifest], List[str]]:
    """
    Backward-compatible pool loader.

    Returns:
        (manifests, fallback_model_ids)
    """
    manifests, fallback_ids, _ = _load_real_pool_internal()
    return manifests, fallback_ids


def load_real_pool_with_index() -> Tuple[List[Manifest], List[str], Dict[str, Dict[str, Any]]]:
    """
    Load manifests plus a raw resource index for dependency and executor lookup.

    Returns:
        (manifests, fallback_model_ids, resource_index)
    """
    return _load_real_pool_internal()


def select_planner_capability_cards(
    query: str,
    resource_index: Dict[str, Dict[str, Any]],
    *,
    limit: int = 10,
) -> List[CapabilityCard]:
    """Build a bounded Resource-Aware Planner view from the locked local index.

    This is an offline semantic pre-pass only: it does not call HyDE, mutate the
    formal candidate pool, or apply a second lexical/resource-name selector.
    Failure is surfaced before the Planner request instead of silently changing
    Resource-Aware semantics.
    """

    if limit <= 0:
        return []
    import retrieve

    seed_resources = retrieve.direct_retrieve(
        query,
        top_k=max(limit * 2, 12),
        verbose=False,
    )
    seed_ids = [
        str(resource.get("resource_id") or resource.get("id") or "")
        for resource in seed_resources
        if isinstance(resource, dict)
        and str(resource.get("resource_id") or resource.get("id") or "")
        in resource_index
    ]
    return select_capability_cards(
        query,
        build_capability_cards(resource_index),
        retrieved_resource_ids=seed_ids,
        limit=limit,
    )


def encode_query_profile(
    query_text: str,
    use_hyde: bool = True,
    *,
    cost_ledger: RunCostLedger | None = None,
    subtask_id: str | None = None,
    subtask_revision: int | None = None,
) -> QueryRetrievalProfile:
    """Encode independent capability and soft-constraint query vectors."""

    import retrieve

    profile = retrieve.encode_query_profile(
        query_text,
        use_hyde=use_hyde,
        cost_ledger=cost_ledger,
        subtask_id=subtask_id,
        subtask_revision=subtask_revision,
    )
    dim = retrieve.get_embedding_dim()
    return QueryRetrievalProfile(
        capability=Vector(embedding=profile.capability_vector, dim=dim),
        constraint=Vector(embedding=profile.constraint_vector, dim=dim),
        raw_query=(
            Vector(embedding=profile.raw_query_vector, dim=dim)
            if profile.raw_query_vector is not None
            else None
        ),
        capability_text=profile.capability_text,
        constraint_text=profile.constraint_text,
        raw_query_text=profile.raw_query_text,
        hard_requirements=profile.hard_requirements,
        profile_version=profile.profile_version,
        generation_metadata=profile.generation_metadata,
    )


def encode_query_vector(query_text: str, use_hyde: bool = True) -> Vector:
    """
    Encode a subtask description into a real query Vector.
    Replaces _mock_embedding() for query-side vectors.

    If use_hyde=True, uses HyDE to generate a structured capability description
    before encoding (recommended for better precision).
    """
    # Backward-compatible legacy API. New routing paths call
    # ``encode_query_profile`` so v_cap and v_con never share one query vector.
    return encode_query_profile(query_text, use_hyde=use_hyde).capability
