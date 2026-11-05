"""Canonical model identity resolution at SGAR resource boundaries."""

from __future__ import annotations

from typing import Any, Mapping

from pydantic import Field, field_validator

from .pipeline_control import FrozenContract, canonical_sha256


MODEL_IDENTITY_PROTOCOL = "sgar-resolved-model-identity-v1"


class ModelIdentityError(ValueError):
    """A model manifest or typed reference has an ambiguous wire identity."""

    def __init__(self, error_code: str) -> None:
        super().__init__(error_code)
        self.error_code = str(error_code)
        self.failure_responsibility = "framework"
        self.retryable = False
        self.response_received = False


class ResolvedModelIdentity(FrozenContract):
    protocol: str = MODEL_IDENTITY_PROTOCOL
    resource_id: str = Field(min_length=1)
    api_model_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    manifest_sha256: str

    @field_validator("resource_id", "api_model_id", "provider")
    @classmethod
    def _strip_identity(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("model_identity_empty")
        return normalized

    @field_validator("manifest_sha256")
    @classmethod
    def _validate_hash(cls, value: str) -> str:
        normalized = str(value).strip().lower()
        if len(normalized) != 64 or any(
            character not in "0123456789abcdef" for character in normalized
        ):
            raise ValueError("model_manifest_sha256_invalid")
        return normalized


def _resource_type(raw: Mapping[str, Any]) -> str:
    nested = raw.get("type")
    nested_type = nested.get("resource_type") if isinstance(nested, Mapping) else None
    return str(raw.get("resource_type") or nested_type or "").strip()


def resolve_model_identity(
    resource_id: str,
    raw_manifest: Mapping[str, Any],
) -> ResolvedModelIdentity:
    """Resolve the only API identity authorized by one immutable manifest."""

    if not isinstance(raw_manifest, Mapping):
        raise ModelIdentityError("model_manifest_not_mapping")
    normalized_resource_id = str(resource_id or "").strip()
    declared_resource_id = str(
        raw_manifest.get("resource_id") or raw_manifest.get("id") or ""
    ).strip()
    if not normalized_resource_id or declared_resource_id != normalized_resource_id:
        raise ModelIdentityError("model_resource_identity_mismatch")
    if _resource_type(raw_manifest).strip().lower() != "model":
        raise ModelIdentityError("model_resource_type_mismatch")

    type_specific = raw_manifest.get("type_specific")
    model_block = (
        type_specific.get("model") if isinstance(type_specific, Mapping) else None
    )
    execution = raw_manifest.get("execution")
    execution = execution if isinstance(execution, Mapping) else {}
    typed_model_id = str(
        model_block.get("model_id") if isinstance(model_block, Mapping) else ""
    ).strip()
    execution_model_id = str(execution.get("model_id") or "").strip()
    if typed_model_id and execution_model_id and typed_model_id != execution_model_id:
        raise ModelIdentityError("model_api_identity_conflict")
    api_model_id = typed_model_id or execution_model_id
    if not api_model_id:
        raise ModelIdentityError("model_api_identity_missing")

    typed_provider = str(
        model_block.get("provider") if isinstance(model_block, Mapping) else ""
    ).strip()
    execution_provider = str(execution.get("provider") or "").strip()
    root_provider = str(raw_manifest.get("provider") or "").strip()
    declared_providers = {
        item for item in (typed_provider, execution_provider, root_provider) if item
    }
    if len(declared_providers) > 1:
        raise ModelIdentityError("model_provider_identity_conflict")
    provider = next(iter(declared_providers), "openai_compatible")

    return ResolvedModelIdentity(
        resource_id=normalized_resource_id,
        api_model_id=api_model_id,
        provider=provider,
        manifest_sha256=canonical_sha256(raw_manifest),
    )


def validate_typed_model_identity(
    identity: ResolvedModelIdentity,
    supplied_base_model: str | None,
) -> str:
    """Normalize the one supported legacy representation, reject all others."""

    supplied = str(supplied_base_model or "").strip()
    if not supplied or supplied in {identity.resource_id, identity.api_model_id}:
        return identity.api_model_id
    raise ModelIdentityError("model_identity_mismatch")


__all__ = [
    "MODEL_IDENTITY_PROTOCOL",
    "ModelIdentityError",
    "ResolvedModelIdentity",
    "resolve_model_identity",
    "validate_typed_model_identity",
]
