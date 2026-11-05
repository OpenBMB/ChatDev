"""Typed, pool-blind contracts for the production Profiler."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator, model_validator, model_serializer

from .pipeline_control import FrozenContract, canonical_sha256


PROFILER_INPUT_PROTOCOL = "sgar-profiler-input-v1"
PROFILER_OUTPUT_PROTOCOL = "sgar-profiler-output-v2"
PROFILER_GENERATION_POLICY_PROTOCOL = "sgar-profiler-generation-policy-v2"
PROFILER_GENERATION_POLICY_EXPERIMENT_PROTOCOL = "sgar-profiler-generation-policy-v3"
PROFILER_PROVIDER_CAPABILITY_PROTOCOL = "sgar-profiler-provider-capability-v1"
SOL_RESOURCE_ID = "model.gpt_5_6_sol.v1"
SOL_API_MODEL_ID = "gpt-5.6-sol"
PROFILER_NORMAL_OUTPUT_CAP = 8192
PROFILER_TRUNCATION_RETRY_OUTPUT_CAP = 16384
PROFILER_OUTPUT_CAP_PROBE_ORDER = (
    PROFILER_NORMAL_OUTPUT_CAP,
    PROFILER_TRUNCATION_RETRY_OUTPUT_CAP,
)
ProfilerReasoningEffort = Literal["low", "medium", "high", "xhigh", "max"]
ProfilerResponseMode = Literal["native_strict_schema", "json_object_local_validator"]


def _validated_sha256(value: str, *, code: str) -> str:
    normalized = str(value).strip().lower()
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise ValueError(code)
    return normalized


class ProfilerSubtaskContractV1(FrozenContract):
    role_intent: str = ""
    description: str = Field(min_length=1)
    expected_output: str = Field(min_length=1)
    execution_mode: str | None = None


class ProfilerMaterialDescriptorV1(FrozenContract):
    logical_name: str = Field(min_length=1)
    source_name: str | None = None
    artifact_type: str = Field(min_length=1)
    content_sha256: str
    coverage_status: Literal["complete", "partial", "handle_only"] = "handle_only"
    original_bytes: int | None = Field(default=None, ge=0)
    included_bytes: int | None = Field(default=None, ge=0)
    included_content_sha256: str | None = None
    handle_available: bool = True
    container_inventory: dict[str, Any] = Field(default_factory=dict)

    @model_serializer(mode="wrap")
    def _serialize_observations(self, handler):
        result = handler(self)
        if not self.container_inventory:
            result.pop("container_inventory", None)
        return result

    @field_validator("content_sha256", "included_content_sha256")
    @classmethod
    def _hash_is_valid(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
            raise ValueError("profiler_material_sha256_invalid")
        return normalized


class ProfilerInputEnvelopeV1(FrozenContract):
    """Only the current subtask contract; no candidate or pool information."""

    protocol: Literal[PROFILER_INPUT_PROTOCOL] = PROFILER_INPUT_PROTOCOL
    revision: dict[str, Any]
    subtask: ProfilerSubtaskContractV1
    semantic_requirements: tuple[dict[str, Any], ...] = ()
    execution_requirements: tuple[dict[str, Any], ...] = ()
    materials: tuple[ProfilerMaterialDescriptorV1, ...] = ()
    dag_inputs: tuple[dict[str, Any], ...] = ()
    output_contract: dict[str, Any]
    source_content_policy: Literal["preserve_original"] = "preserve_original"
    internal_output_language: Literal["en"] = "en"
    contract_sha256: str
    envelope_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "ProfilerInputEnvelopeV1":
        material_keys = [
            (item.logical_name, item.artifact_type, item.content_sha256)
            for item in self.materials
        ]
        if material_keys != sorted(material_keys) or len(material_keys) != len(
            set(material_keys)
        ):
            raise ValueError("profiler_materials_not_unique_sorted")
        projection = self.model_dump(mode="python", exclude={"envelope_sha256"})
        expected = canonical_sha256(projection)
        if self.envelope_sha256 and self.envelope_sha256 != expected:
            raise ValueError("profiler_envelope_sha256_mismatch")
        object.__setattr__(self, "envelope_sha256", expected)
        return self


class ProfilerOutputV2(FrozenContract):
    """Production output with a visible summary that is never embedded."""

    capability_text: str = Field(min_length=1)
    constraint_text: str = Field(min_length=1)
    think: str = Field(min_length=1)


class ProfilerGenerationPolicyV2(FrozenContract):
    """Exact request policy; an endpoint probe seals its effective cap."""

    protocol: Literal[
        PROFILER_GENERATION_POLICY_PROTOCOL,
        PROFILER_GENERATION_POLICY_EXPERIMENT_PROTOCOL,
    ] = (
        PROFILER_GENERATION_POLICY_PROTOCOL
    )
    resource_id: str = SOL_RESOURCE_ID
    api_model_id: str = SOL_API_MODEL_ID
    prompt_version: str = Field(min_length=1)
    reasoning_effort: ProfilerReasoningEffort
    requested_max_output_tokens: Literal[8192] = 8192
    truncation_retry_max_output_tokens: Literal[16384] = 16384
    output_cap_probe_order: tuple[int, ...] = PROFILER_OUTPUT_CAP_PROBE_ORDER
    effective_max_output_tokens: int | None = Field(default=None, ge=16384, le=16384)
    temperature: float | None = None
    response_mode: ProfilerResponseMode = "native_strict_schema"
    max_model_attempts: Literal[2] = 2
    max_transport_attempts_per_model_attempt: Literal[3] = 3
    allow_model_failover: Literal[False] = False
    allow_direct_fallback: Literal[False] = False
    policy_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "ProfilerGenerationPolicyV2":
        if self.protocol == PROFILER_GENERATION_POLICY_PROTOCOL and (
            self.resource_id != SOL_RESOURCE_ID
            or self.api_model_id != SOL_API_MODEL_ID
            or self.reasoning_effort != "xhigh"
        ):
            raise ValueError("profiler_generation_policy_v2_identity_invalid")
        if self.temperature is not None:
            raise ValueError("profiler_reasoning_temperature_must_be_omitted")
        if self.output_cap_probe_order != PROFILER_OUTPUT_CAP_PROBE_ORDER:
            raise ValueError("profiler_output_cap_probe_order_invalid")
        if (
            self.effective_max_output_tokens is not None
            and self.effective_max_output_tokens not in self.output_cap_probe_order
        ):
            raise ValueError("profiler_effective_output_cap_not_probed")
        projection = self.model_dump(mode="python", exclude={"policy_sha256"})
        expected = canonical_sha256(projection)
        if self.policy_sha256 and self.policy_sha256 != expected:
            raise ValueError("profiler_generation_policy_sha256_mismatch")
        object.__setattr__(self, "policy_sha256", expected)
        return self

    @property
    def request_output_cap(self) -> int:
        if self.effective_max_output_tokens is None:
            raise ValueError("profiler_provider_output_cap_unsealed")
        return self.requested_max_output_tokens


class ProfilerProviderCapabilityV1(FrozenContract):
    """Evidence that one exact provider endpoint accepts the production request."""

    protocol: Literal[PROFILER_PROVIDER_CAPABILITY_PROTOCOL] = (
        PROFILER_PROVIDER_CAPABILITY_PROTOCOL
    )
    endpoint_identity_sha256: str
    transport_kind: Literal["chat_completions", "responses"]
    resource_id: str = SOL_RESOURCE_ID
    api_model_id: str = SOL_API_MODEL_ID
    supported_reasoning_efforts: tuple[ProfilerReasoningEffort, ...]
    accepted_output_cap: Literal[16384] = 16384
    accepted_response_mode: ProfilerResponseMode
    finish_reason_semantics: dict[str, str]
    reasoning_usage_available: bool
    reasoning_content_available: bool
    probed_at: str = Field(min_length=1)
    probe_request_sha256: str
    probe_response_sha256: str
    capability_sha256: str = ""

    @field_validator(
        "endpoint_identity_sha256",
        "probe_request_sha256",
        "probe_response_sha256",
    )
    @classmethod
    def _hash_is_valid(cls, value: str, info: Any) -> str:
        return _validated_sha256(value, code=f"{info.field_name}_invalid")

    @model_validator(mode="after")
    def _seal(self) -> "ProfilerProviderCapabilityV1":
        if self.accepted_output_cap not in PROFILER_OUTPUT_CAP_PROBE_ORDER:
            raise ValueError("profiler_provider_output_cap_not_in_probe_order")
        efforts = tuple(dict.fromkeys(self.supported_reasoning_efforts))
        if efforts != self.supported_reasoning_efforts or not efforts:
            raise ValueError("profiler_provider_reasoning_efforts_invalid")
        if not self.probed_at.endswith(("Z", "+00:00")):
            raise ValueError("profiler_provider_probe_time_not_utc")
        projection = self.model_dump(mode="python", exclude={"capability_sha256"})
        expected = canonical_sha256(projection)
        if self.capability_sha256 and self.capability_sha256 != expected:
            raise ValueError("profiler_provider_capability_sha256_mismatch")
        object.__setattr__(self, "capability_sha256", expected)
        return self


__all__ = [
    "PROFILER_INPUT_PROTOCOL",
    "PROFILER_OUTPUT_PROTOCOL",
    "PROFILER_GENERATION_POLICY_PROTOCOL",
    "PROFILER_GENERATION_POLICY_EXPERIMENT_PROTOCOL",
    "PROFILER_OUTPUT_CAP_PROBE_ORDER",
    "PROFILER_NORMAL_OUTPUT_CAP",
    "PROFILER_TRUNCATION_RETRY_OUTPUT_CAP",
    "PROFILER_PROVIDER_CAPABILITY_PROTOCOL",
    "SOL_API_MODEL_ID",
    "SOL_RESOURCE_ID",
    "ProfilerGenerationPolicyV2",
    "ProfilerInputEnvelopeV1",
    "ProfilerMaterialDescriptorV1",
    "ProfilerOutputV2",
    "ProfilerProviderCapabilityV1",
    "ProfilerSubtaskContractV1",
]
