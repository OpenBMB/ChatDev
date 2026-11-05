"""Single source of truth for typed SGAR retrieval policy."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, Literal

from pydantic import BaseModel, Field, model_validator


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_PATH = PROJECT_ROOT / "sgar_mvp" / "config" / "retrieval_policy.json"
RETRIEVAL_STRATEGIES = {
    "capability_only",
    "capability_constraint_weighted",
}


class TypeRetrievalPolicy(BaseModel):
    capability_weight: float = Field(ge=0.0, le=1.0)
    constraint_weight: float = Field(ge=0.0, le=1.0)
    initial_quota: int = Field(ge=0)
    compact_quota: int = Field(ge=0)
    recall_threshold: float = Field(default=0.95, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> "TypeRetrievalPolicy":
        if abs(self.capability_weight + self.constraint_weight - 1.0) > 1e-9:
            raise ValueError("capability and constraint weights must sum to one")
        if self.compact_quota > self.initial_quota:
            raise ValueError("compact quota cannot exceed initial quota")
        return self


class HyDEPolicy(BaseModel):
    generation_protocol: Literal[
        "sgar-profiler-generation-policy-v2",
        "sgar-profiler-generation-policy-v3",
    ] = (
        "sgar-profiler-generation-policy-v2"
    )
    resource_id: str = Field(pattern=r"^model\.[A-Za-z0-9][A-Za-z0-9_.:-]*$")
    api_model_id: str = Field(min_length=1)
    prompt_version: Literal["ideal-resource-profiler-en-v3"]
    reasoning_effort: Literal["low", "medium", "high", "xhigh", "max"]
    temperature: float | None = None
    requested_max_output_tokens: Literal[8192] = 8192
    truncation_retry_max_output_tokens: Literal[16384] = 16384
    output_cap_probe_order: tuple[int, ...] = (8192, 16384)
    max_tokens: Literal[8192] = 8192
    output_format: Literal["json"] = "json"
    formal_stability_runs: int = Field(default=3, ge=2)
    max_model_attempts: Literal[2] = 2
    max_transport_attempts_per_model_attempt: Literal[3] = 3
    allow_model_failover: Literal[False] = False
    allow_direct_fallback: Literal[False] = False
    provider_capability_sha256: str | None = None
    response_mode: Literal["native_strict_schema", "json_object_local_validator"] | None = None

    @model_validator(mode="after")
    def validate_profiler_policy(self) -> "HyDEPolicy":
        if self.generation_protocol == "sgar-profiler-generation-policy-v2" and (
            self.resource_id != "model.gpt_5_6_sol.v1"
            or self.api_model_id != "gpt-5.6-sol"
            or self.reasoning_effort != "xhigh"
        ):
            raise ValueError("profiler generation v2 identity is not authoritative")
        if self.output_cap_probe_order != (8192, 16384):
            raise ValueError("profiler output-cap probe order is not authoritative")
        if self.max_tokens != self.requested_max_output_tokens:
            raise ValueError("profiler normal output cap is not authoritative")
        if self.truncation_retry_max_output_tokens != self.output_cap_probe_order[-1]:
            raise ValueError("profiler truncation retry cap is not authoritative")
        if self.provider_capability_sha256 is not None:
            value = self.provider_capability_sha256.strip().lower()
            if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
                raise ValueError("profiler provider capability hash is invalid")
            self.provider_capability_sha256 = value
        if (self.provider_capability_sha256 is None) != (self.response_mode is None):
            raise ValueError("profiler provider capability identity is incomplete")
        return self


class PromotionThresholds(BaseModel):
    semantic_bundle_coverage: float = 0.95
    runtime_bundle_coverage: float = 0.95
    compact_bundle_coverage: float = 0.90
    top1_accuracy: float = 0.80
    stability_jaccard: float = 0.90
    invalid_candidate_occupancy: float = 0.0


class RetrievalPolicy(BaseModel):
    policy_version: str
    active_strategy: str
    candidate_strategy: str
    resource_pool_commit: str
    profile_version: str
    embedding_model: str
    bge_prefix: str
    effective_pool_sha256: str
    index_sha256: Dict[str, str]
    embedding_candidate_id: str | None = None
    embedding_runtime_identity_sha256: str | None = None
    index_meta_sha256: str | None = None
    index_build_manifest_sha256: str | None = None
    release_source_seal_sha256: str | None = None
    prompt_registry_sha256: str | None = None
    profiler_prompt_sha256: str | None = None
    profiler_schema_sha256: str | None = None
    control_role_policy_sha256: str | None = None
    control_provider_probe_receipt_sha256: str | None = None
    type_policies: Dict[str, TypeRetrievalPolicy]
    compact_total_max: int = Field(default=12, gt=0)
    hyde: HyDEPolicy
    promotion_thresholds: PromotionThresholds = Field(default_factory=PromotionThresholds)

    @model_validator(mode="after")
    def validate_policy(self) -> "RetrievalPolicy":
        if self.active_strategy not in RETRIEVAL_STRATEGIES:
            raise ValueError(f"unsupported active strategy: {self.active_strategy}")
        if self.candidate_strategy not in RETRIEVAL_STRATEGIES:
            raise ValueError(f"unsupported candidate strategy: {self.candidate_strategy}")
        required_types = {"Model", "Agent", "Skill", "Tool", "Resource"}
        if set(self.type_policies) != required_types:
            raise ValueError("type_policies must define Model/Agent/Skill/Tool/Resource")
        if self.type_policies["Resource"].initial_quota != 0:
            raise ValueError("Resource quota must be zero in RC1")
        if sum(item.compact_quota for item in self.type_policies.values()) > self.compact_total_max:
            raise ValueError("compact per-type quotas exceed compact_total_max")
        release_fields = (
            self.embedding_candidate_id,
            self.embedding_runtime_identity_sha256,
            self.index_meta_sha256,
            self.index_build_manifest_sha256,
            self.release_source_seal_sha256,
            self.prompt_registry_sha256,
            self.profiler_prompt_sha256,
            self.profiler_schema_sha256,
            self.control_role_policy_sha256,
            self.control_provider_probe_receipt_sha256,
            self.hyde.provider_capability_sha256,
            self.hyde.response_mode,
        )
        pending = self.policy_version in {
            "retrieval-policy-v6-pending-release",
            "retrieval-policy-v7-pending-release",
        }
        released_v6 = self.policy_version.startswith("retrieval-policy-v6-")
        released_v7 = self.policy_version.startswith("retrieval-policy-v7-")
        if not pending and not (released_v6 or released_v7):
            raise ValueError("retrieval policy is not a supported release")
        if self.local_pool_update and self.release_source_seal_sha256 is not None:
            raise ValueError("local_model_pool_cannot_claim_release_seal")
        if pending:
            if any(value is not None for value in release_fields):
                raise ValueError("pending retrieval policy contains release identity")
        else:
            required_release_fields = (
                release_fields
                if released_v7
                else tuple(
                    value
                    for index, value in enumerate(release_fields)
                    if index != 9
                )
            )
            if self.local_pool_update:
                required_release_fields = release_fields[:4] + release_fields[5:]
            if any(value is None for value in required_release_fields):
                raise ValueError("released retrieval policy identity is incomplete")
            if released_v6 and self.control_provider_probe_receipt_sha256 is not None:
                raise ValueError("V6 retrieval policy cannot bind the V7 control probe receipt")
            if not self.local_pool_update and (
                self.embedding_model != "Qwen/Qwen3-Embedding-0.6B"
                or self.embedding_candidate_id != "qwen3-embedding-0.6b-bf16-1024"
            ):
                raise ValueError("released retrieval embedding identity is not fixed Qwen")
            if not self.local_pool_update and (
                self.active_strategy != "capability_only"
                or self.candidate_strategy != "capability_only"
            ):
                raise ValueError("released retrieval strategy is not capability_only")
            if not self.local_pool_update and self.hyde.reasoning_effort != "xhigh":
                raise ValueError("released profiler reasoning effort is not xhigh")
            for value in (
                self.embedding_runtime_identity_sha256,
                self.index_meta_sha256,
                self.index_build_manifest_sha256,
                self.release_source_seal_sha256,
                self.prompt_registry_sha256,
                self.profiler_prompt_sha256,
                self.profiler_schema_sha256,
                self.control_role_policy_sha256,
                *(
                    (self.control_provider_probe_receipt_sha256,)
                    if released_v7
                    else ()
                ),
            ):
                if self.local_pool_update and value is None:
                    continue
                normalized = str(value).strip().lower()
                if len(normalized) != 64 or any(
                    character not in "0123456789abcdef" for character in normalized
                ):
                    raise ValueError("released retrieval identity hash is invalid")
        return self

    @property
    def local_pool_update(self) -> bool:
        """An index-bound local generation, never a sealed source release."""
        return self.policy_version.startswith("retrieval-policy-v7-local-")

    @property
    def index_bound(self) -> bool:
        return self.release_sealed or self.local_pool_update

    @property
    def release_sealed(self) -> bool:
        return not self.local_pool_update and self.policy_version not in {
            "retrieval-policy-v6-pending-release",
            "retrieval-policy-v7-pending-release",
        }

    def canonical_payload(self) -> str:
        return json.dumps(self.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_payload().encode("utf-8")).hexdigest()

    def weights(self) -> Dict[str, tuple[float, float]]:
        return {
            resource_type: (item.capability_weight, item.constraint_weight)
            for resource_type, item in self.type_policies.items()
        }

    def initial_quotas(self) -> Dict[str, int]:
        return {key: item.initial_quota for key, item in self.type_policies.items()}

    def compact_quotas(self) -> Dict[str, int]:
        return {key: item.compact_quota for key, item in self.type_policies.items()}


def load_retrieval_policy(path: Path = DEFAULT_POLICY_PATH) -> RetrievalPolicy:
    return RetrievalPolicy.model_validate_json(path.read_text(encoding="utf-8-sig"))


def policy_sha256(path: Path = DEFAULT_POLICY_PATH) -> str:
    return load_retrieval_policy(path).sha256()
