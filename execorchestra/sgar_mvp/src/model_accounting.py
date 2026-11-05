"""Strict model-pricing and cost contracts for S-GAR.

The first layer in this module is intentionally pure: it parses the immutable
resource-pool pricing snapshot, normalizes provider-reported usage, and
calculates Decimal-denominated USD cost.  Runtime transport and ledger wiring
build on these contracts without changing routing semantics.
"""

from __future__ import annotations

from . import terminal_progress

import hashlib
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, Mapping, Sequence

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from .atomic_io import temporary_sibling_path
from .pipeline_control import canonical_sha256


MODEL_PRICING_PROTOCOL = "sgar-model-pricing-v1"
MODEL_USAGE_PROTOCOL = "sgar-model-usage-v1"
MODEL_COST_POLICY_PROTOCOL = "model-cost-policy-v1"
COST_BREAKDOWN_PROTOCOL = "sgar-model-cost-breakdown-v1"
MODEL_CALL_LEDGER_PROTOCOL_V1 = "sgar-model-call-ledger-v1"
MODEL_CALL_LEDGER_PROTOCOL = "sgar-model-call-ledger-v2"
SUPPORTED_MODEL_CALL_LEDGER_PROTOCOLS = frozenset(
    {MODEL_CALL_LEDGER_PROTOCOL_V1, MODEL_CALL_LEDGER_PROTOCOL}
)
MODEL_COST_SUMMARY_PROTOCOL = "sgar-model-cost-summary-v1"
PRICING_UNIT = "USD_per_million_tokens"
USD_JSON_QUANTUM = Decimal("0.000000000001")
MILLION_TOKENS = Decimal(1_000_000)


class ModelAccountingError(ValueError):
    """Base error for strict pricing, usage, and policy failures."""

    # ``main.py`` can run both as a package and as a script, which creates two
    # import namespaces in legacy deployments.  This stable marker preserves
    # fail-closed accounting semantics without relying on class identity.
    is_model_accounting_error = True


class PricingCatalogError(ModelAccountingError):
    pass


class UnknownModelPricingError(PricingCatalogError):
    pass


class AmbiguousModelPricingError(PricingCatalogError):
    pass


class TokenUsageError(ModelAccountingError):
    pass


class ModelCostPolicyError(ModelAccountingError):
    pass


class AccountingPersistenceError(ModelAccountingError):
    """Accounting failed before a provider request was authorized."""

    responsibility = "framework"
    failure_stage = "model_accounting"
    retryable = False
    response_received = False
    error_code = "model_accounting_persistence_failed"


class BudgetControlError(ModelAccountingError):
    """A cost policy deliberately blocked a not-yet-sent model request."""

    responsibility = "budget"
    failure_stage = "budget_control"
    retryable = False
    response_received = False
    error_code = "model_cost_limit_reached"


class UsageUnknownBudgetError(BudgetControlError):
    error_code = "model_cost_usage_unknown"


class RequestCountBudgetError(BudgetControlError):
    error_code = "generation_request_limit_reached"


class FrozenAccountingContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _decimal(value: Any, *, field_name: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{field_name}_must_be_decimal")
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field_name}_must_be_decimal") from exc
    if not result.is_finite() or result < 0:
        raise ValueError(f"{field_name}_must_be_finite_nonnegative")
    return result


def format_usd(value: Decimal) -> str:
    """Serialize USD with exactly twelve decimal places."""

    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise ModelAccountingError("usd_value_must_be_finite_nonnegative_decimal")
    return format(value.quantize(USD_JSON_QUANTUM), ".12f")


class ModelPrice(FrozenAccountingContract):
    protocol: Literal[MODEL_PRICING_PROTOCOL] = MODEL_PRICING_PROTOCOL
    resource_id: str = Field(min_length=1)
    api_model_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    input_per_m: Decimal
    cache_per_m: Decimal | None
    output_per_m: Decimal
    pricing_unit: Literal[PRICING_UNIT] = PRICING_UNIT
    source_manifest_sha256: str
    # Backend-only tariffs; ModelPricingEvidence keeps the compiler's existing three fields.
    billing_rules: dict[str, Any] = Field(default_factory=dict)

    def __hash__(self) -> int:
        # Catalog lookup de-duplicates frozen prices in a set. Tariff dictionaries
        # are covered by the source identity, rather than Python's dict hash.
        return hash((self.resource_id, self.api_model_id, self.source_manifest_sha256))

    @field_validator("input_per_m", "cache_per_m", "output_per_m", mode="before")
    @classmethod
    def _validate_price(cls, value: Any, info: Any) -> Decimal | None:
        if info.field_name == "cache_per_m" and value is None:
            return None
        return _decimal(value, field_name=info.field_name)

    @field_validator("resource_id", "api_model_id", "provider")
    @classmethod
    def _strip_identity(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("model_price_identity_empty")
        return normalized

    @field_validator("source_manifest_sha256")
    @classmethod
    def _validate_manifest_hash(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
            raise ValueError("source_manifest_sha256_invalid")
        return normalized


class ModelPricingCatalog:
    """Immutable, exact lookup catalog derived only from the resource manifest."""

    def __init__(self, prices: Sequence[ModelPrice], *, resource_pool_sha256: str):
        ordered = tuple(sorted(prices, key=lambda item: (item.resource_id, item.api_model_id)))
        if not ordered:
            raise PricingCatalogError("pricing_catalog_has_no_models")
        by_resource: dict[str, ModelPrice] = {}
        by_api: dict[str, ModelPrice] = {}
        for price in ordered:
            if price.source_manifest_sha256 != resource_pool_sha256:
                raise PricingCatalogError("model_price_source_manifest_mismatch")
            if price.resource_id in by_resource:
                raise PricingCatalogError(f"duplicate_model_resource_id:{price.resource_id}")
            if price.api_model_id in by_api:
                raise PricingCatalogError(f"duplicate_api_model_id:{price.api_model_id}")
            by_resource[price.resource_id] = price
            by_api[price.api_model_id] = price
        self._prices = ordered
        self._by_resource = MappingProxyType(by_resource)
        self._by_api = MappingProxyType(by_api)
        self.resource_pool_sha256 = resource_pool_sha256
        self.pricing_catalog_sha256 = canonical_sha256(
            {
                "protocol": MODEL_PRICING_PROTOCOL,
                "resource_pool_sha256": resource_pool_sha256,
                "models": [item.model_dump(mode="json") for item in ordered],
            }
        )

    @property
    def prices(self) -> tuple[ModelPrice, ...]:
        return self._prices

    @property
    def model_count(self) -> int:
        return len(self._prices)

    @classmethod
    def from_manifest_file(
        cls,
        path: str | Path,
        *,
        required_model_refs: Sequence[str] = (),
    ) -> "ModelPricingCatalog":
        manifest_path = Path(path)
        try:
            raw = manifest_path.read_bytes()
        except OSError as exc:
            raise PricingCatalogError("pricing_manifest_unreadable") from exc
        manifest_sha256 = hashlib.sha256(raw).hexdigest()
        try:
            payload = json.loads(raw.decode("utf-8"), parse_float=Decimal)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PricingCatalogError("pricing_manifest_invalid_json") from exc
        if not isinstance(payload, list):
            raise PricingCatalogError("pricing_manifest_root_must_be_array")

        prices: list[ModelPrice] = []
        for index, resource in enumerate(payload):
            if not isinstance(resource, Mapping):
                raise PricingCatalogError(f"pricing_manifest_resource_not_object:{index}")
            if resource.get("resource_type") != "Model":
                continue
            resource_id = resource.get("resource_id")
            execution = resource.get("execution")
            type_specific = resource.get("type_specific")
            if not isinstance(execution, Mapping) or not isinstance(type_specific, Mapping):
                raise PricingCatalogError(f"model_manifest_shape_invalid:{resource_id}")
            model_specific = type_specific.get("model")
            if not isinstance(model_specific, Mapping):
                raise PricingCatalogError(f"model_type_specific_missing:{resource_id}")
            execution_model_id = execution.get("model_id")
            typed_model_id = model_specific.get("model_id")
            if not isinstance(execution_model_id, str) or not execution_model_id.strip():
                raise PricingCatalogError(f"api_model_id_missing:{resource_id}")
            if typed_model_id is not None and typed_model_id != execution_model_id:
                raise PricingCatalogError(f"api_model_id_conflict:{resource_id}")
            pricing = model_specific.get("pricing")
            if not isinstance(pricing, Mapping):
                raise PricingCatalogError(f"model_pricing_missing:{resource_id}")
            required_keys = {"input_per_m", "cache_per_m", "output_per_m"}
            missing = sorted(required_keys - set(pricing))
            if missing:
                raise PricingCatalogError(
                    f"model_pricing_fields_missing:{resource_id}:{','.join(missing)}"
                )
            unit = model_specific.get("pricing_unit")
            if unit != PRICING_UNIT:
                raise PricingCatalogError(f"model_pricing_unit_invalid:{resource_id}")
            try:
                price = ModelPrice(
                    resource_id=resource_id,
                    api_model_id=execution_model_id,
                    provider=(
                        model_specific.get("provider")
                        or execution.get("provider")
                        or resource.get("provider")
                    ),
                    input_per_m=pricing["input_per_m"],
                    cache_per_m=pricing["cache_per_m"],
                    output_per_m=pricing["output_per_m"],
                    pricing_unit=unit,
                    source_manifest_sha256=manifest_sha256,
                    billing_rules=model_specific.get("pricing_rules") or {},
                )
            except Exception as exc:
                raise PricingCatalogError(f"model_pricing_invalid:{resource_id}") from exc
            prices.append(price)

        catalog = cls(prices, resource_pool_sha256=manifest_sha256)
        for model_ref in required_model_refs:
            catalog.resolve(model_ref=model_ref)
        return catalog

    def resolve(
        self,
        *,
        model_ref: str | None = None,
        resource_id: str | None = None,
        api_model_id: str | None = None,
    ) -> ModelPrice:
        """Resolve exact identities; never fuzzy-match names or legacy tags."""

        if model_ref is not None:
            if resource_id is not None or api_model_id is not None:
                raise PricingCatalogError("model_ref_cannot_be_combined_with_explicit_identity")
            matches = {
                item
                for item in (
                    self._by_resource.get(model_ref),
                    self._by_api.get(model_ref),
                )
                if item is not None
            }
            if not matches:
                raise UnknownModelPricingError(f"unknown_model:{model_ref}")
            if len(matches) != 1:
                raise AmbiguousModelPricingError(f"ambiguous_model:{model_ref}")
            return next(iter(matches))

        if resource_id is None and api_model_id is None:
            raise PricingCatalogError("model_identity_required")
        resource_match = self._by_resource.get(resource_id) if resource_id is not None else None
        api_match = self._by_api.get(api_model_id) if api_model_id is not None else None
        if resource_id is not None and resource_match is None:
            raise UnknownModelPricingError(f"unknown_model_resource_id:{resource_id}")
        if api_model_id is not None and api_match is None:
            raise UnknownModelPricingError(f"unknown_api_model_id:{api_model_id}")
        if resource_match is not None and api_match is not None and resource_match != api_match:
            raise AmbiguousModelPricingError("resource_and_api_model_identity_disagree")
        return resource_match or api_match  # type: ignore[return-value]

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": MODEL_PRICING_PROTOCOL,
            "pricing_unit": PRICING_UNIT,
            "model_count": self.model_count,
            "resource_pool_sha256": self.resource_pool_sha256,
            "pricing_catalog_sha256": self.pricing_catalog_sha256,
            "models": [item.model_dump(mode="json") for item in self._prices],
        }


class CanonicalTokenUsage(FrozenAccountingContract):
    protocol: Literal[MODEL_USAGE_PROTOCOL] = MODEL_USAGE_PROTOCOL
    input_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(ge=0)
    cache_write_input_tokens: int = Field(default=0, ge=0)
    cache_write_1h_input_tokens: int = Field(default=0, ge=0)
    cache_read_mode: Literal["implicit", "explicit"] = "implicit"
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    usage_source: Literal["provider_reported"] = "provider_reported"

    @model_validator(mode="after")
    def _validate_usage(self) -> "CanonicalTokenUsage":
        if self.cached_input_tokens > self.input_tokens:
            raise ValueError("cached_input_tokens_exceed_input_tokens")
        if self.cached_input_tokens + self.cache_write_input_tokens > self.input_tokens:
            raise ValueError("cache_components_exceed_input_tokens")
        if self.cache_write_1h_input_tokens > self.cache_write_input_tokens:
            raise ValueError("cache_write_1h_exceeds_total")
        if self.total_tokens != self.input_tokens + self.output_tokens:
            raise ValueError("total_tokens_conflicts_with_components")
        return self


def _usage_mapping(usage: Any) -> Mapping[str, Any]:
    if usage is None:
        raise TokenUsageError("provider_usage_missing")
    if isinstance(usage, Mapping):
        return usage
    model_dump = getattr(usage, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, Mapping):
            return dumped
    values: dict[str, Any] = {}
    for key in (
        "prompt_tokens",
        "input_tokens",
        "completion_tokens",
        "output_tokens",
        "total_tokens",
        "cached_tokens",
        "cache_read_input_tokens",
        "cache_creation_input_tokens",
        "cache_creation",
        "prompt_tokens_details",
        "input_tokens_details",
    ):
        if hasattr(usage, key):
            values[key] = getattr(usage, key)
    if not values:
        raise TokenUsageError("provider_usage_unreadable")
    return values


def _nonnegative_integer(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TokenUsageError(f"{field_name}_must_be_integer")
    if value < 0:
        raise TokenUsageError(f"{field_name}_must_be_nonnegative")
    return value


def _alias_value(
    source: Mapping[str, Any],
    aliases: Sequence[str],
    *,
    field_name: str,
    required: bool,
) -> int | None:
    observed = [
        _nonnegative_integer(source[key], field_name=field_name)
        for key in aliases
        if key in source and source[key] is not None
    ]
    if not observed:
        if required:
            raise TokenUsageError(f"{field_name}_missing")
        return None
    if len(set(observed)) != 1:
        raise TokenUsageError(f"{field_name}_alias_conflict")
    return observed[0]


UsageNormalizationStatus = Literal[
    "direct",
    "aliases_equal",
    "total_disambiguated",
    "invalid",
    "not_available",
]


def _observed_alias_values(
    source: Mapping[str, Any],
    aliases: Sequence[str],
    *,
    field_name: str,
) -> list[int]:
    observed = [
        _nonnegative_integer(source[key], field_name=field_name)
        for key in aliases
        if key in source and source[key] is not None
    ]
    if not observed:
        raise TokenUsageError(f"{field_name}_missing")
    return observed


def _normalize_token_usage_with_status(
    usage: Any,
) -> tuple[CanonicalTokenUsage, UsageNormalizationStatus]:
    """Normalize aliases without guessing which provider field is authoritative."""

    source = dict(_usage_mapping(usage))
    cache_nodes = [source]
    for key in ("prompt_tokens_details", "input_tokens_details", "cache_creation"):
        node = source.get(key)
        if callable(getattr(node, "model_dump", None)):
            node = node.model_dump()
        if isinstance(node, Mapping):
            cache_nodes.append(node)
            child = node.get("cache_creation")
            if isinstance(child, Mapping):
                cache_nodes.append(child)

    def cache_count(*names: str) -> int | None:
        observed = [
            _nonnegative_integer(node[name], field_name=names[0])
            for node in cache_nodes for name in names
            if node.get(name) is not None
        ]
        if len(set(observed)) > 1:
            raise TokenUsageError(names[0] + "_alias_conflict")
        return observed[0] if observed else None

    write_total = cache_count("cache_creation_input_tokens", "cache_write_tokens")
    write_5m = cache_count("ephemeral_5m_input_tokens")
    write_1h = cache_count("ephemeral_1h_input_tokens") or 0
    if write_total is None:
        write_total = (write_5m or 0) + write_1h
    elif write_5m is not None and write_total != write_5m + write_1h:
        raise TokenUsageError("cache_write_ttl_components_conflict")
    native_cache = (
        "prompt_tokens" not in source
        and ("cache_read_input_tokens" in source or "cache_creation_input_tokens" in source)
    )
    if native_cache and source.get("input_tokens") is not None:
        # Native Anthropic input_tokens excludes cache read/write, unlike chat usage.
        source["input_tokens"] = (
            _nonnegative_integer(source["input_tokens"], field_name="input_tokens")
            + (cache_count("cache_read_input_tokens") or 0) + write_total
        )
    input_observations = _observed_alias_values(
        source,
        ("prompt_tokens", "input_tokens"),
        field_name="input_tokens",
    )
    output_observations = _observed_alias_values(
        source,
        ("completion_tokens", "output_tokens"),
        field_name="output_tokens",
    )
    input_values = sorted(set(input_observations))
    output_values = sorted(set(output_observations))
    aliases_conflict = len(input_values) > 1 or len(output_values) > 1
    total = _alias_value(
        source,
        ("total_tokens",),
        field_name="total_tokens",
        required=False,
    )
    if aliases_conflict:
        if total is None:
            raise TokenUsageError("provider_usage_alias_conflict_without_total")
        compatible = [
            (input_value, output_value)
            for input_value in input_values
            for output_value in output_values
            if input_value + output_value == total
        ]
        if not compatible:
            raise TokenUsageError("provider_usage_alias_conflict_has_no_total_match")
        if len(compatible) != 1:
            raise TokenUsageError("provider_usage_alias_conflict_has_multiple_total_matches")
        input_tokens, output_tokens = compatible[0]
        normalization_status: UsageNormalizationStatus = "total_disambiguated"
    else:
        input_tokens = input_values[0]
        output_tokens = output_values[0]
        normalization_status = (
            "aliases_equal"
            if len(input_observations) > 1 or len(output_observations) > 1
            else "direct"
        )
    cached_observations: list[int] = []
    if source.get("cache_read_input_tokens") is not None:
        cached_observations.append(_nonnegative_integer(source["cache_read_input_tokens"], field_name="cached_input_tokens"))
    if source.get("cached_tokens") is not None:
        cached_observations.append(
            _nonnegative_integer(source["cached_tokens"], field_name="cached_input_tokens")
        )
    for detail_key in ("prompt_tokens_details", "input_tokens_details"):
        details = source.get(detail_key)
        if details is None:
            continue
        if not isinstance(details, Mapping):
            model_dump = getattr(details, "model_dump", None)
            details = model_dump() if callable(model_dump) else {
                "cached_tokens": getattr(details, "cached_tokens", None)
            }
        if isinstance(details, Mapping) and details.get("cached_tokens") is not None:
            cached_observations.append(
                _nonnegative_integer(
                    details["cached_tokens"],
                    field_name="cached_input_tokens",
                )
            )
    if len(set(cached_observations)) > 1:
        raise TokenUsageError("cached_input_tokens_alias_conflict")
    cached_tokens = cached_observations[0] if cached_observations else 0
    expected_total = input_tokens + output_tokens
    if total is None:
        total = expected_total
    if total != expected_total:
        raise TokenUsageError("total_tokens_conflicts_with_components")
    try:
        canonical = CanonicalTokenUsage(
            input_tokens=input_tokens,
            cached_input_tokens=cached_tokens,
            cache_write_input_tokens=write_total,
            cache_write_1h_input_tokens=write_1h,
            cache_read_mode="explicit" if native_cache else "implicit",
            output_tokens=output_tokens,
            total_tokens=total,
        )
    except Exception as exc:
        raise TokenUsageError("provider_usage_invalid") from exc
    return canonical, normalization_status


def normalize_token_usage(usage: Any) -> CanonicalTokenUsage:
    """Normalize supported OpenAI-compatible usage shapes, fail-closed."""

    normalized, _status = _normalize_token_usage_with_status(usage)
    return normalized


def calculate_actual_model_cost_usd(
    usage: CanonicalTokenUsage,
    price: ModelPrice,
) -> Decimal:
    """Calculate exact observed USD cost without binary floating point."""

    if price.billing_rules:
        from .official_pricing import official_token_cost, IncompleteOfficialPricing
        try:
            return official_token_cost(
                price.billing_rules,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cached_input_tokens=usage.cached_input_tokens,
                cache_write_input_tokens=usage.cache_write_input_tokens,
                cache_write_1h_input_tokens=usage.cache_write_1h_input_tokens,
                cache_read_mode=usage.cache_read_mode,
            )
        except IncompleteOfficialPricing as exc:
            raise PricingCatalogError(str(exc)) from exc
    return calculate_model_cost_from_token_counts(
        input_tokens=usage.input_tokens,
        cached_input_tokens=usage.cached_input_tokens,
        output_tokens=usage.output_tokens,
        input_per_m=price.input_per_m,
        cache_per_m=price.cache_per_m,
        output_per_m=price.output_per_m,
    )


def calculate_model_cost_from_token_counts(
    *,
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
    input_per_m: Any,
    cache_per_m: Any,
    output_per_m: Any,
) -> Decimal:
    """Shared pure formula used by production accounting and frozen E1 reports."""

    usage = CanonicalTokenUsage(
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
    )
    input_rate = _decimal(input_per_m, field_name="input_per_m")
    if cache_per_m is None and usage.cached_input_tokens:
        raise PricingCatalogError("cache_read_price_unknown")
    cache_rate = Decimal(0) if cache_per_m is None else _decimal(cache_per_m, field_name="cache_per_m")
    output_rate = _decimal(output_per_m, field_name="output_per_m")
    uncached_input = max(usage.input_tokens - usage.cached_input_tokens, 0)
    return (
        Decimal(uncached_input) * input_rate
        + Decimal(usage.cached_input_tokens) * cache_rate
        + Decimal(usage.output_tokens) * output_rate
    ) / MILLION_TOKENS


class CostControlMode(str, Enum):
    MONITOR = "monitor"
    STOP_AFTER_LIMIT = "stop_after_limit"


class ModelCostPolicy(FrozenAccountingContract):
    schema_version: Literal[MODEL_COST_POLICY_PROTOCOL] = MODEL_COST_POLICY_PROTOCOL
    mode: Literal["monitor", "stop_after_limit"] = "monitor"
    warning_usd: Decimal = Decimal("10")
    limit_usd: Decimal = Decimal("10")
    strict_pricing: Literal[True] = True
    unknown_model: Literal["reject"] = "reject"

    @field_validator("warning_usd", "limit_usd", mode="before")
    @classmethod
    def _validate_threshold(cls, value: Any, info: Any) -> Decimal:
        return _decimal(value, field_name=info.field_name)

    @property
    def policy_sha256(self) -> str:
        return canonical_sha256(self.model_dump(mode="json"))

    def snapshot(self) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        data["warning_usd"] = format_usd(self.warning_usd)
        data["limit_usd"] = format_usd(self.limit_usd)
        data["policy_sha256"] = self.policy_sha256
        return data


def load_model_cost_policy(
    path: str | Path,
    *,
    local_cost_control: Mapping[str, Any] | None = None,
) -> ModelCostPolicy:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"), parse_float=Decimal)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ModelCostPolicyError("model_cost_policy_unreadable") from exc
    if not isinstance(payload, Mapping):
        raise ModelCostPolicyError("model_cost_policy_root_must_be_object")
    merged = dict(payload)
    overrides = dict(local_cost_control or {})
    unsupported = sorted(set(overrides) - {"mode", "warning_usd", "limit_usd"})
    if unsupported:
        raise ModelCostPolicyError(
            f"unsupported_local_cost_control_keys:{','.join(unsupported)}"
        )
    merged.update(overrides)
    try:
        return ModelCostPolicy.model_validate(merged)
    except Exception as exc:
        raise ModelCostPolicyError("model_cost_policy_invalid") from exc


class CostBreakdown(FrozenAccountingContract):
    schema_version: Literal[COST_BREAKDOWN_PROTOCOL] = COST_BREAKDOWN_PROTOCOL
    operation_id: str = Field(min_length=1)
    provider_attempt_id: str = Field(min_length=1)
    stage: str = Field(min_length=1)
    subtask_id: str | None = None
    subtask_revision: int | None = Field(default=None, ge=0)
    selected_resource_id: str | None = None
    model_resource_id: str = Field(min_length=1)
    api_model_id: str = Field(min_length=1)
    request_sha256: str
    pricing_catalog_sha256: str
    token_usage: CanonicalTokenUsage
    actual_model_cost_usd: Decimal
    response_received: Literal[True] = True
    usage_status: Literal["provider_reported"] = "provider_reported"
    agent_id: str | None = None

    @field_validator("actual_model_cost_usd", mode="before")
    @classmethod
    def _validate_cost(cls, value: Any) -> Decimal:
        return _decimal(value, field_name="actual_model_cost_usd")

    @field_validator("request_sha256", "pricing_catalog_sha256")
    @classmethod
    def _validate_hash(cls, value: str, info: Any) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
            raise ValueError(f"{info.field_name}_invalid")
        return normalized

    @model_validator(mode="after")
    def _validate_revision_pair(self) -> "CostBreakdown":
        if (self.subtask_id is None) != (self.subtask_revision is None):
            raise ValueError("subtask_id_and_revision_must_appear_together")
        return self

    @field_serializer("actual_model_cost_usd")
    def _serialize_cost(self, value: Decimal) -> str:
        return format_usd(value)


ModelCallStage = Literal[
    "planner_decompose",
    "planner_replan",
    "retrieval_hyde",
    "retrieval_format_probe",
    "model_liveness_probe",
    "plan_compiler",
    "command_adaptation",
    "model_execution",
    "agent_execution",
    "evaluator",
    "evaluator_review",
    "context_compression",
    "full_generation",
]


class ModelCallContext(FrozenAccountingContract):
    """Non-secret attribution carried by one semantic model operation."""

    operation_id: str = Field(default_factory=lambda: uuid.uuid4().hex, min_length=1)
    stage: ModelCallStage
    subtask_id: str | None = None
    subtask_revision: int | None = Field(default=None, ge=0)
    selected_resource_id: str | None = None
    model_resource_id: str | None = None
    agent_id: str | None = None
    request_policy_sha256: str | None = None
    reasoning_effort: str | None = None

    @model_validator(mode="after")
    def _validate_subtask_identity(self) -> "ModelCallContext":
        if (self.subtask_id is None) != (self.subtask_revision is None):
            raise ValueError("subtask_id_and_revision_must_appear_together")
        if self.request_policy_sha256 is not None:
            value = self.request_policy_sha256.strip().lower()
            if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
                raise ValueError("model_call_request_policy_sha256_invalid")
            object.__setattr__(self, "request_policy_sha256", value)
        return self


class ModelCallHandle(FrozenAccountingContract):
    cache_read_mode: Literal["implicit", "explicit"] = "implicit"
    cache_write_ttl: Literal["5m", "1h", "mixed"] = "5m"
    run_id: str
    started_event_id: str
    operation_id: str
    provider_attempt_id: str
    provider_attempt: int = Field(ge=1)
    stage: str
    subtask_id: str | None = None
    subtask_revision: int | None = None
    selected_resource_id: str | None = None
    model_resource_id: str
    api_model_id: str
    provider: str
    agent_id: str | None = None
    request_policy_sha256: str | None = None
    reasoning_effort: str | None = None
    request_sha256: str
    pricing_catalog_sha256: str
    policy_sha256: str
    request_input_token_upper_bound: int | None = Field(default=None, ge=0)
    request_output_token_upper_bound: int | None = Field(default=None, ge=0)
    request_cost_upper_bound_usd: Decimal | None = None
    request_cost_upper_bound_basis: str | None = None

    @field_validator(
        "request_sha256",
        "pricing_catalog_sha256",
        "policy_sha256",
        "request_policy_sha256",
    )
    @classmethod
    def _validate_identity_hash(cls, value: str | None, info: Any) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(
            character not in "0123456789abcdef" for character in normalized
        ):
            raise ValueError(f"{info.field_name}_invalid")
        return normalized

    @field_validator("request_cost_upper_bound_usd", mode="before")
    @classmethod
    def _validate_request_cost_upper_bound(cls, value: Any) -> Decimal | None:
        if value is None:
            return None
        return _decimal(value, field_name="request_cost_upper_bound_usd")

    @field_serializer("request_cost_upper_bound_usd")
    def _serialize_request_cost_upper_bound(self, value: Decimal | None) -> str | None:
        return format_usd(value) if value is not None else None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _message_sha256(exc: BaseException | None) -> str | None:
    if exc is None:
        return None
    payload = f"{type(exc).__name__}:{str(exc)}".encode("utf-8", errors="replace")
    return hashlib.sha256(payload).hexdigest()


def _structured_error_code(exc: BaseException | None) -> str | None:
    if exc is None:
        return None
    explicit = getattr(exc, "error_code", None)
    if explicit:
        return str(explicit)
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return f"provider_http_{status}"
    return type(exc).__name__


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = temporary_sibling_path(path)
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(
                payload,
                handle,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
                allow_nan=False,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise


class RunCostLedger:
    """Thread-safe append-only accounting fact source for one pipeline run."""

    def __init__(
        self,
        *,
        catalog: ModelPricingCatalog,
        policy: ModelCostPolicy,
        output_dir: str | Path,
        run_id: str | None = None,
        max_generation_requests: int | None = None,
    ) -> None:
        self.catalog = catalog
        if max_generation_requests is not None and (
            type(max_generation_requests) is not int or max_generation_requests < 0
        ):
            raise ValueError("invalid_generation_request_limit")
        self.max_generation_requests = max_generation_requests
        self.policy = policy
        self.output_dir = Path(output_dir)
        self.run_id = str(run_id or uuid.uuid4().hex)
        self.events_path = self.output_dir / "model_calls.jsonl"
        self.pricing_snapshot_path = self.output_dir / "model_pricing_snapshot.json"
        self.summary_path = self.output_dir / "cost_summary.json"
        self._lock = threading.RLock()
        self._operation_attempts: dict[str, int] = {}
        self._pending: dict[str, ModelCallHandle] = {}
        self._terminal: dict[str, dict[str, Any]] = {}
        self._blocked_calls: list[dict[str, Any]] = []
        self._warnings: list[dict[str, Any]] = []
        self._persistence_failures: list[str] = []
        self._warning_emitted = False
        self._limit_reached = False
        self._usage_unknown = False

        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            if self.events_path.exists() and self.events_path.stat().st_size:
                raise AccountingPersistenceError("model_call_ledger_already_exists")
            _atomic_write_json(self.pricing_snapshot_path, catalog.snapshot())
            self.write_summary()
        except AccountingPersistenceError:
            raise
        except Exception as exc:
            raise AccountingPersistenceError("model_accounting_initialization_failed") from exc

    @property
    def current_spend_decimal(self) -> Decimal:
        with self._lock:
            return sum(
                (
                    item["actual_model_cost_usd"]
                    for item in self._terminal.values()
                    if isinstance(item.get("actual_model_cost_usd"), Decimal)
                ),
                Decimal("0"),
            )

    @property
    def current_unreported_cost_upper_bound_decimal(self) -> Decimal:
        """Conservative exposure for calls whose provider usage is unavailable."""

        with self._lock:
            return sum(
                (
                    item["unreported_cost_upper_bound_usd"]
                    for item in self._terminal.values()
                    if isinstance(item.get("unreported_cost_upper_bound_usd"), Decimal)
                ),
                Decimal("0"),
            )

    @property
    def current_cost_exposure_decimal(self) -> Decimal:
        return self.current_spend_decimal + self.current_unreported_cost_upper_bound_decimal

    @property
    def current_spend(self) -> float:
        return float(self.current_spend_decimal)

    @property
    def max_budget(self) -> float:
        return float(self.policy.limit_usd)

    @property
    def is_exhausted(self) -> bool:
        return bool(
            self.policy.mode == CostControlMode.STOP_AFTER_LIMIT.value
            and (self._limit_reached or self._usage_unknown)
        )

    def new_operation(
        self,
        *,
        stage: ModelCallStage,
        subtask_id: str | None = None,
        subtask_revision: int | None = None,
        selected_resource_id: str | None = None,
        model_resource_id: str | None = None,
        agent_id: str | None = None,
        request_policy_sha256: str | None = None,
        reasoning_effort: str | None = None,
    ) -> ModelCallContext:
        return ModelCallContext(
            stage=stage,
            subtask_id=subtask_id,
            subtask_revision=subtask_revision,
            selected_resource_id=selected_resource_id,
            model_resource_id=model_resource_id,
            agent_id=agent_id,
            request_policy_sha256=request_policy_sha256,
            reasoning_effort=reasoning_effort,
        )

    def _append_event(self, event: Mapping[str, Any]) -> None:
        serialized = json.dumps(
            event,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        try:
            with self.events_path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(serialized)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        except Exception as exc:
            raise AccountingPersistenceError("model_call_event_append_failed") from exc
        terminal_progress.observe_model(event)

    def _blocked(self, *, context: ModelCallContext, reason: str) -> None:
        event = {
            "schema_version": MODEL_CALL_LEDGER_PROTOCOL,
            "event_type": "model_call_blocked",
            "event_id": uuid.uuid4().hex,
            "timestamp_utc": _utc_now(),
            "run_id": self.run_id,
            "operation_id": context.operation_id,
            "stage": context.stage,
            "subtask_id": context.subtask_id,
            "subtask_revision": context.subtask_revision,
            "request_policy_sha256": context.request_policy_sha256,
            "reasoning_effort": context.reasoning_effort,
            "reason": reason,
            "policy_sha256": self.policy.policy_sha256,
        }
        self._append_event(event)
        self._blocked_calls.append(event)

    def start_call(
        self,
        *,
        context: ModelCallContext,
        model_ref: str,
        request_sha256: str,
        request_input_token_upper_bound: int | None = None,
        request_output_token_upper_bound: int | None = None,
        request_cost_upper_bound_basis: str | None = None,
        cache_read_mode: Literal["implicit", "explicit"] = "implicit",
        cache_write_ttl: Literal["5m", "1h", "mixed"] = "5m",
    ) -> ModelCallHandle:
        """Persist authorization before the network send; failure means no send."""

        with self._lock:
            if (self.max_generation_requests is not None and
                    len(self._terminal) + len(self._pending) >= self.max_generation_requests):
                self._blocked(context=context, reason="generation_request_limit_reached")
                raise RequestCountBudgetError("Generation request budget exhausted before send")
            if self.policy.mode == CostControlMode.STOP_AFTER_LIMIT.value:
                if self._usage_unknown:
                    self._blocked(context=context, reason="provider_usage_unknown")
                    raise UsageUnknownBudgetError(
                        "Provider usage is unknown; stop_after_limit cannot verify the budget."
                    )
                if self._limit_reached:
                    self._blocked(context=context, reason="observed_limit_reached")
                    raise BudgetControlError(
                        "Observed model cost limit was reached; the next call is blocked."
                    )
            try:
                if context.model_resource_id:
                    price = self.catalog.resolve(
                        resource_id=context.model_resource_id,
                        api_model_id=(
                            model_ref
                            if model_ref in {item.api_model_id for item in self.catalog.prices}
                            else None
                        ),
                    )
                    if model_ref not in {price.resource_id, price.api_model_id}:
                        raise UnknownModelPricingError(
                            f"model_reference_disagrees_with_context:{model_ref}"
                        )
                else:
                    price = self.catalog.resolve(model_ref=model_ref)
            except PricingCatalogError:
                self._blocked(context=context, reason="model_pricing_unresolved")
                raise

            request_cost_upper_bound: Decimal | None = None
            if (
                request_input_token_upper_bound is not None
                and request_output_token_upper_bound is not None
            ):
                if (
                    type(request_input_token_upper_bound) is not int
                    or request_input_token_upper_bound < 0
                    or type(request_output_token_upper_bound) is not int
                    or request_output_token_upper_bound < 0
                ):
                    raise ModelAccountingError("request_token_upper_bound_invalid")
                request_cost_upper_bound = calculate_actual_model_cost_usd(
                    CanonicalTokenUsage(
                        input_tokens=request_input_token_upper_bound,
                        cached_input_tokens=0,
                        output_tokens=request_output_token_upper_bound,
                        total_tokens=request_input_token_upper_bound + request_output_token_upper_bound,
                    ), price,
                )
                # A missing response may also have billed explicit cache creation.
                if cache_read_mode == "explicit" and price.billing_rules:
                    from .official_pricing import effective_rates
                    rates = effective_rates(price.billing_rules, request_input_token_upper_bound)
                    write_key = "cache_write_1h_per_m" if cache_write_ttl in {"1h", "mixed"} else "cache_write_per_m"
                    write_rate = rates.get(write_key)
                    if write_rate is not None:
                        surcharge = max(Decimal(0), Decimal(str(write_rate)) - Decimal(str(rates["input_per_m"])))
                        request_cost_upper_bound += Decimal(request_input_token_upper_bound) * surcharge / MILLION_TOKENS

            attempt = self._operation_attempts.get(context.operation_id, 0) + 1
            self._operation_attempts[context.operation_id] = attempt
            provider_attempt_id = f"{context.operation_id}:{attempt}"
            started_event_id = uuid.uuid4().hex
            handle = ModelCallHandle(
                run_id=self.run_id,
                cache_read_mode=cache_read_mode,
                cache_write_ttl=cache_write_ttl,
                started_event_id=started_event_id,
                operation_id=context.operation_id,
                provider_attempt_id=provider_attempt_id,
                provider_attempt=attempt,
                stage=context.stage,
                subtask_id=context.subtask_id,
                subtask_revision=context.subtask_revision,
                selected_resource_id=context.selected_resource_id,
                model_resource_id=price.resource_id,
                api_model_id=price.api_model_id,
                provider=price.provider,
                agent_id=context.agent_id,
                request_policy_sha256=context.request_policy_sha256,
                reasoning_effort=context.reasoning_effort,
                request_sha256=request_sha256,
                pricing_catalog_sha256=self.catalog.pricing_catalog_sha256,
                policy_sha256=self.policy.policy_sha256,
                request_input_token_upper_bound=request_input_token_upper_bound,
                request_output_token_upper_bound=request_output_token_upper_bound,
                request_cost_upper_bound_usd=request_cost_upper_bound,
                request_cost_upper_bound_basis=(
                    request_cost_upper_bound_basis
                    if request_cost_upper_bound is not None
                    else None
                ),
            )
            event = {
                "schema_version": MODEL_CALL_LEDGER_PROTOCOL,
                "event_type": "model_call_started",
                "event_id": started_event_id,
                "timestamp_utc": _utc_now(),
                **handle.model_dump(mode="json", exclude={"started_event_id"}),
            }
            self._append_event(event)
            self._pending[provider_attempt_id] = handle
            # Keep the public summary aligned with the append-only ledger even
            # if an outer benchmark supervisor later terminates this process.
            # A pending call is intentionally incomplete rather than zero-cost
            # complete evidence.
            self.write_summary()
            return handle

    def finish_call(
        self,
        handle: ModelCallHandle,
        *,
        response_received: bool,
        usage: Any = None,
        error: BaseException | None = None,
        completion_status: str = "completed",
    ) -> dict[str, Any]:
        """Settle once. Post-response persistence errors never discard a response."""

        with self._lock:
            existing = self._terminal.get(handle.provider_attempt_id)
            if existing is not None:
                return dict(existing)
            usage_status: str
            normalization_status: UsageNormalizationStatus = "not_available"
            canonical_usage: CanonicalTokenUsage | None = None
            actual_cost: Decimal | None = None
            usage_error_code: str | None = None
            if not response_received:
                usage_status = "no_response"
            elif usage is None:
                usage_status = "missing"
            else:
                try:
                    canonical_usage, normalization_status = (
                        _normalize_token_usage_with_status(usage)
                    )
                    if handle.cache_read_mode == "explicit":
                        update = {"cache_read_mode": "explicit"}
                        if handle.cache_write_ttl == "1h":
                            update["cache_write_1h_input_tokens"] = canonical_usage.cache_write_input_tokens
                        elif handle.cache_write_ttl == "mixed" and canonical_usage.cache_write_input_tokens and not canonical_usage.cache_write_1h_input_tokens:
                            raise PricingCatalogError("cache_write_mixed_ttl_usage_missing")
                        canonical_usage = canonical_usage.model_copy(update=update)
                    price = self.catalog.resolve(
                        resource_id=handle.model_resource_id,
                        api_model_id=handle.api_model_id,
                    )
                    actual_cost = calculate_actual_model_cost_usd(canonical_usage, price)
                    usage_status = "provider_reported"
                except TokenUsageError as exc:
                    usage_status = "invalid"
                    normalization_status = "invalid"
                    usage_error_code = str(exc).split(":", 1)[0]
                except PricingCatalogError as exc:
                    # Missing billing evidence must not discard a valid model response.
                    usage_status = "unpriced"
                    usage_error_code = str(exc)

            cost_breakdown = (
                CostBreakdown(
                    operation_id=handle.operation_id,
                    provider_attempt_id=handle.provider_attempt_id,
                    stage=handle.stage,
                    subtask_id=handle.subtask_id,
                    subtask_revision=handle.subtask_revision,
                    selected_resource_id=handle.selected_resource_id,
                    model_resource_id=handle.model_resource_id,
                    api_model_id=handle.api_model_id,
                    request_sha256=handle.request_sha256,
                    pricing_catalog_sha256=handle.pricing_catalog_sha256,
                    token_usage=canonical_usage,
                    actual_model_cost_usd=actual_cost,
                    agent_id=handle.agent_id,
                )
                if canonical_usage is not None and actual_cost is not None
                else None
            )
            provider_billing_unknown = bool(
                (response_received and usage_status != "provider_reported")
                or getattr(error, "provider_execution_unknown", False)
            )
            unreported_cost_upper_bound = (
                handle.request_cost_upper_bound_usd
                if provider_billing_unknown
                else None
            )
            terminal = {
                "schema_version": MODEL_CALL_LEDGER_PROTOCOL,
                "event_type": "model_call_finished",
                "event_id": uuid.uuid4().hex,
                "timestamp_utc": _utc_now(),
                "run_id": handle.run_id,
                "started_event_id": handle.started_event_id,
                "operation_id": handle.operation_id,
                "provider_attempt_id": handle.provider_attempt_id,
                "provider_attempt": handle.provider_attempt,
                "stage": handle.stage,
                "subtask_id": handle.subtask_id,
                "subtask_revision": handle.subtask_revision,
                "selected_resource_id": handle.selected_resource_id,
                "model_resource_id": handle.model_resource_id,
                "api_model_id": handle.api_model_id,
                "provider": handle.provider,
                "agent_id": handle.agent_id,
                "request_sha256": handle.request_sha256,
                "pricing_catalog_sha256": handle.pricing_catalog_sha256,
                "policy_sha256": handle.policy_sha256,
                "response_received": bool(response_received),
                "completion_status": str(completion_status),
                "usage_status": usage_status,
                "usage_normalization_status": normalization_status,
                "token_usage": (
                    canonical_usage.model_dump(mode="json") if canonical_usage else None
                ),
                "actual_model_cost_usd": (
                    format_usd(actual_cost) if actual_cost is not None else None
                ),
                "cost_breakdown": (
                    cost_breakdown.model_dump(mode="json")
                    if cost_breakdown is not None
                    else None
                ),
                "provider_billing_unknown": provider_billing_unknown,
                "unreported_cost_upper_bound_usd": (
                    format_usd(unreported_cost_upper_bound)
                    if unreported_cost_upper_bound is not None
                    else None
                ),
                "error_code": _structured_error_code(error),
                "message_sha256": _message_sha256(error),
                "usage_error_code": usage_error_code,
                "provider_usage": (
                    json.loads(json.dumps(dict(_usage_mapping(usage)), default=lambda value: value.model_dump() if callable(getattr(value, "model_dump", None)) else str(value)))
                    if usage is not None and canonical_usage is not None else None
                ),
            }
            try:
                self._append_event(terminal)
            except AccountingPersistenceError as exc:
                self._persistence_failures.append(str(exc))

            internal = dict(terminal)
            internal["actual_model_cost_usd"] = actual_cost
            internal["token_usage_object"] = canonical_usage
            internal["unreported_cost_upper_bound_usd"] = unreported_cost_upper_bound
            self._terminal[handle.provider_attempt_id] = internal
            self._pending.pop(handle.provider_attempt_id, None)
            if provider_billing_unknown and unreported_cost_upper_bound is None:
                # A client-side deadline cannot prove that the provider did
                # not generate/bill. Strict cost mode may continue only when
                # the request carried an auditable conservative upper bound.
                self._usage_unknown = True
            if (
                self.policy.mode == CostControlMode.STOP_AFTER_LIMIT.value
                and self.current_cost_exposure_decimal >= self.policy.limit_usd
            ):
                self._limit_reached = True
            if (
                not self._warning_emitted
                and self.current_cost_exposure_decimal >= self.policy.warning_usd
            ):
                self._emit_warning()
            # Model responses are already durable in model_calls.jsonl.  Mirror
            # the settled state after every call so abrupt Tool/runtime failure
            # cannot leave the initialization-time all-zero summary behind.
            try:
                self.write_summary()
            except AccountingPersistenceError:
                # Post-response persistence failures must never discard or
                # repeat a provider response; close() will retry the summary.
                pass
            return self._public_terminal(internal)

    def _emit_warning(self) -> None:
        self._warning_emitted = True
        event = {
            "schema_version": MODEL_CALL_LEDGER_PROTOCOL,
            "event_type": "model_cost_warning",
            "event_id": uuid.uuid4().hex,
            "timestamp_utc": _utc_now(),
            "run_id": self.run_id,
            "observed_total_model_cost_usd": format_usd(self.current_spend_decimal),
            "total_model_cost_upper_bound_usd": format_usd(
                self.current_cost_exposure_decimal
            ),
            "warning_usd": format_usd(self.policy.warning_usd),
            "policy_sha256": self.policy.policy_sha256,
        }
        try:
            self._append_event(event)
        except AccountingPersistenceError as exc:
            self._persistence_failures.append(str(exc))
        self._warnings.append(event)

    @staticmethod
    def _public_terminal(internal: Mapping[str, Any]) -> dict[str, Any]:
        public = {
            key: value
            for key, value in internal.items()
            if key != "token_usage_object"
        }
        for field_name in (
            "actual_model_cost_usd",
            "unreported_cost_upper_bound_usd",
        ):
            if isinstance(public.get(field_name), Decimal):
                public[field_name] = format_usd(public[field_name])
        return public

    def accounting_reference(self, handle: ModelCallHandle) -> dict[str, Any]:
        """Return only stable join keys; the ledger remains the cost fact source."""

        return {
            "operation_id": handle.operation_id,
            "provider_attempt_id": handle.provider_attempt_id,
            **self.operation_reference(handle.operation_id),
        }

    def operation_reference(self, operation_id: str) -> dict[str, Any]:
        with self._lock:
            attempts = [
                item
                for item in self._terminal.values()
                if item.get("operation_id") == operation_id
            ]
            attempts.extend(
                handle.model_dump(mode="python")
                for handle in self._pending.values()
                if handle.operation_id == operation_id
            )

            def ordinal(item: Mapping[str, Any]) -> int:
                text = str(item.get("provider_attempt_id") or "")
                try:
                    return int(text.rsplit(":", 1)[1])
                except (IndexError, ValueError):
                    return 0

            ordered = sorted(attempts, key=ordinal)
            return {
                "operation_id": operation_id,
                "provider_attempt_ids": [
                    str(item.get("provider_attempt_id")) for item in ordered
                ],
            }

    def summary(self) -> dict[str, Any]:
        with self._lock:
            by_model: dict[str, dict[str, Any]] = {}
            by_stage: dict[str, dict[str, Any]] = {}
            by_subtask: dict[str, dict[str, Any]] = {}
            total_input = total_cached = total_output = total_write = total_write_1h = 0

            def add(bucket: dict[str, dict[str, Any]], key: str, item: Mapping[str, Any]) -> None:
                target = bucket.setdefault(
                    key,
                    {
                        "attempt_count": 0,
                        "response_count": 0,
                        "input_tokens": 0,
                        "cached_input_tokens": 0,
                        "cache_write_input_tokens": 0,
                        "cache_write_1h_input_tokens": 0,
                        "output_tokens": 0,
                        "observed_model_cost_usd": Decimal("0"),
                    },
                )
                target["attempt_count"] += 1
                if item.get("response_received"):
                    target["response_count"] += 1
                usage = item.get("token_usage_object")
                if isinstance(usage, CanonicalTokenUsage):
                    target["input_tokens"] += usage.input_tokens
                    target["cached_input_tokens"] += usage.cached_input_tokens
                    target["cache_write_input_tokens"] += usage.cache_write_input_tokens
                    target["cache_write_1h_input_tokens"] += usage.cache_write_1h_input_tokens
                    target["output_tokens"] += usage.output_tokens
                cost = item.get("actual_model_cost_usd")
                if isinstance(cost, Decimal):
                    target["observed_model_cost_usd"] += cost

            for item in self._terminal.values():
                usage = item.get("token_usage_object")
                if isinstance(usage, CanonicalTokenUsage):
                    total_input += usage.input_tokens
                    total_cached += usage.cached_input_tokens
                    total_write += usage.cache_write_input_tokens
                    total_write_1h += usage.cache_write_1h_input_tokens
                    total_output += usage.output_tokens
                add(by_model, str(item["model_resource_id"]), item)
                add(by_stage, str(item["stage"]), item)
                add(by_subtask, str(item.get("subtask_id") or "__global__"), item)

            def serialize_buckets(source: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
                return {
                    key: {
                        **value,
                        "observed_model_cost_usd": format_usd(
                            value["observed_model_cost_usd"]
                        ),
                    }
                    for key, value in sorted(source.items())
                }

            missing = sum(
                1 for item in self._terminal.values() if item.get("usage_status") == "missing"
            )
            invalid = sum(
                1 for item in self._terminal.values() if item.get("usage_status") == "invalid"
            )
            no_response = sum(
                1
                for item in self._terminal.values()
                if item.get("usage_status") == "no_response"
            )
            unpriced = sum(1 for item in self._terminal.values() if item.get("usage_status") == "unpriced")
            complete = not (
                missing
                or invalid
                or no_response
                or unpriced
                or self._pending
                or self._persistence_failures
            )
            total = self.current_spend_decimal
            unreported_upper_bound = self.current_unreported_cost_upper_bound_decimal
            total_upper_bound = total + unreported_upper_bound
            overshoot = max(total - self.policy.limit_usd, Decimal("0"))
            exposure_overshoot = max(total_upper_bound - self.policy.limit_usd, Decimal("0"))
            return {
                "schema_version": MODEL_COST_SUMMARY_PROTOCOL,
                "run_id": self.run_id,
                "pricing_catalog_sha256": self.catalog.pricing_catalog_sha256,
                "resource_pool_sha256": self.catalog.resource_pool_sha256,
                "resolved_cost_policy": self.policy.snapshot(),
                "observed_total_model_cost_usd": format_usd(total),
                "unreported_cost_upper_bound_usd": format_usd(unreported_upper_bound),
                "total_model_cost_upper_bound_usd": format_usd(total_upper_bound),
                "provider_reported_cost_complete": complete,
                "token_usage": {
                    "input_tokens": total_input,
                    "cached_input_tokens": total_cached,
                    "cache_write_input_tokens": total_write,
                    "cache_write_1h_input_tokens": total_write_1h,
                    "output_tokens": total_output,
                },
                "by_model": serialize_buckets(by_model),
                "by_stage": serialize_buckets(by_stage),
                "by_subtask": serialize_buckets(by_subtask),
                "started_call_count": len(self._terminal) + len(self._pending),
                "max_generation_requests": self.max_generation_requests,
                "finished_call_count": len(self._terminal),
                "pending_call_count": len(self._pending),
                "response_usage_missing_count": missing,
                "response_usage_invalid_count": invalid,
                "response_usage_unpriced_count": unpriced,
                "no_response_attempt_count": no_response,
                "warning_count": len(self._warnings),
                "blocked_call_count": len(self._blocked_calls),
                "accounting_persistence_failure_count": len(self._persistence_failures),
                "budget_status": {
                    "mode": self.policy.mode,
                    "warning_emitted": self._warning_emitted,
                    "limit_reached": self._limit_reached,
                    "usage_unknown_blocks_next_call": bool(
                        self.policy.mode == CostControlMode.STOP_AFTER_LIMIT.value
                        and self._usage_unknown
                    ),
                    "unreported_usage_bounded": bool(
                        unreported_upper_bound > 0 and not self._usage_unknown
                    ),
                    "overshoot_usd": format_usd(overshoot),
                    "exposure_overshoot_usd": format_usd(exposure_overshoot),
                },
            }

    def operation_cost_summary(
        self,
        operation_ids: Sequence[str],
    ) -> dict[str, Any]:
        """Return a read-only cost projection for exact operation references.

        This helper does not mutate accounting state and does not create a
        second billing source.  It is used by subsystem reports (for example
        Recovery) to join their hash-only operation references back to the
        Stage 1 ledger.
        """

        requested = tuple(dict.fromkeys(str(item) for item in operation_ids if item))
        with self._lock:
            terminal = [
                item
                for item in self._terminal.values()
                if str(item.get("operation_id") or "") in requested
            ]
            pending_ids = {
                str(item.get("operation_id") or "")
                for item in self._pending.values()
                if str(item.get("operation_id") or "") in requested
            }
            observed_ids = {
                str(item.get("operation_id") or "") for item in terminal
            }
            total = sum(
                (
                    item["actual_model_cost_usd"]
                    for item in terminal
                    if isinstance(item.get("actual_model_cost_usd"), Decimal)
                ),
                Decimal("0"),
            )
            unreported_upper_bound = sum(
                (
                    item["unreported_cost_upper_bound_usd"]
                    for item in terminal
                    if isinstance(item.get("unreported_cost_upper_bound_usd"), Decimal)
                ),
                Decimal("0"),
            )
            incomplete_statuses = {
                "missing",
                "invalid",
                "no_response",
                "unpriced",
            }
            incomplete_ids = {
                str(item.get("operation_id") or "")
                for item in terminal
                if item.get("usage_status") in incomplete_statuses
            }
            missing_ids = sorted(set(requested) - observed_ids - pending_ids)
            return {
                "operation_ids": list(requested),
                "observed_operation_ids": sorted(observed_ids),
                "missing_operation_ids": missing_ids,
                "pending_operation_ids": sorted(pending_ids),
                "usage_incomplete_operation_ids": sorted(incomplete_ids),
                "attempt_count": len(terminal) + sum(
                    1
                    for item in self._pending.values()
                    if str(item.get("operation_id") or "") in requested
                ),
                "observed_model_cost_usd": format_usd(total),
                "unreported_cost_upper_bound_usd": format_usd(
                    unreported_upper_bound
                ),
                "total_model_cost_upper_bound_usd": format_usd(
                    total + unreported_upper_bound
                ),
                "provider_reported_cost_complete": not (
                    missing_ids or pending_ids or incomplete_ids
                ),
            }

    def write_summary(self) -> dict[str, Any]:
        with self._lock:
            summary = self.summary()
            try:
                _atomic_write_json(self.summary_path, summary)
            except Exception as exc:
                self._persistence_failures.append(type(exc).__name__)
                raise AccountingPersistenceError("cost_summary_write_failed") from exc
            return summary

    def close(self) -> dict[str, Any]:
        return self.write_summary()


__all__ = [
    "COST_BREAKDOWN_PROTOCOL",
    "MODEL_CALL_LEDGER_PROTOCOL",
    "MODEL_CALL_LEDGER_PROTOCOL_V1",
    "MODEL_COST_POLICY_PROTOCOL",
    "MODEL_PRICING_PROTOCOL",
    "MODEL_USAGE_PROTOCOL",
    "PRICING_UNIT",
    "SUPPORTED_MODEL_CALL_LEDGER_PROTOCOLS",
    "AmbiguousModelPricingError",
    "AccountingPersistenceError",
    "BudgetControlError",
    "CanonicalTokenUsage",
    "CostBreakdown",
    "CostControlMode",
    "ModelAccountingError",
    "ModelCostPolicy",
    "ModelCostPolicyError",
    "ModelPrice",
    "ModelPricingCatalog",
    "ModelCallContext",
    "ModelCallHandle",
    "ModelCallStage",
    "PricingCatalogError",
    "TokenUsageError",
    "UnknownModelPricingError",
    "UsageUnknownBudgetError",
    "UsageNormalizationStatus",
    "RunCostLedger",
    "calculate_actual_model_cost_usd",
    "calculate_model_cost_from_token_counts",
    "format_usd",
    "load_model_cost_policy",
    "normalize_token_usage",
]
