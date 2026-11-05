"""Hash-only observation of optional provider-native reasoning fields."""

from __future__ import annotations

import hashlib
from typing import Any, Literal, Mapping

from pydantic import Field, model_validator

from .pipeline_control import FrozenContract, canonical_sha256


PROVIDER_REASONING_OBSERVATION_PROTOCOL = "sgar-provider-reasoning-observation-v1"


class ProviderReasoningObservationV1(FrozenContract):
    """Non-reversible metadata; provider reasoning plaintext is never retained."""

    protocol: Literal[PROVIDER_REASONING_OBSERVATION_PROTOCOL] = (
        PROVIDER_REASONING_OBSERVATION_PROTOCOL
    )
    available: bool
    byte_count: int = Field(ge=0)
    content_sha256: str | None = None
    reasoning_tokens: int = Field(ge=0)
    trust: Literal["provider_specific_unverified"] = "provider_specific_unverified"
    observation_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "ProviderReasoningObservationV1":
        if self.available != (self.byte_count > 0 and self.content_sha256 is not None):
            raise ValueError("provider_reasoning_observation_shape_invalid")
        if self.content_sha256 is not None:
            value = self.content_sha256.strip().lower()
            if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
                raise ValueError("provider_reasoning_content_sha256_invalid")
            object.__setattr__(self, "content_sha256", value)
        projection = self.model_dump(mode="python", exclude={"observation_sha256"})
        expected = canonical_sha256(projection)
        if self.observation_sha256 and self.observation_sha256 != expected:
            raise ValueError("provider_reasoning_observation_sha256_mismatch")
        object.__setattr__(self, "observation_sha256", expected)
        return self


def _reasoning_text(response: Any) -> str:
    try:
        message = response.choices[0].message
    except (AttributeError, IndexError, TypeError):
        return ""
    for field_name in ("reasoning_content", "reasoning", "analysis"):
        value = getattr(message, field_name, None)
        if isinstance(value, str) and value.strip():
            return value
    if isinstance(message, Mapping):
        for field_name in ("reasoning_content", "reasoning", "analysis"):
            value = message.get(field_name)
            if isinstance(value, str) and value.strip():
                return value
    return ""


def _reasoning_tokens(response: Any) -> int:
    usage = getattr(response, "usage", None)
    details = getattr(usage, "completion_tokens_details", None)
    if isinstance(details, Mapping):
        return int(details.get("reasoning_tokens") or 0)
    return int(getattr(details, "reasoning_tokens", 0) or 0)


def observe_provider_reasoning(response: Any) -> ProviderReasoningObservationV1:
    """Compute a hash-only observation without returning or writing plaintext."""

    text = _reasoning_text(response)
    payload = text.encode("utf-8")
    return ProviderReasoningObservationV1(
        available=bool(payload),
        byte_count=len(payload),
        content_sha256=hashlib.sha256(payload).hexdigest() if payload else None,
        reasoning_tokens=_reasoning_tokens(response),
    )


__all__ = [
    "PROVIDER_REASONING_OBSERVATION_PROTOCOL",
    "ProviderReasoningObservationV1",
    "observe_provider_reasoning",
]
