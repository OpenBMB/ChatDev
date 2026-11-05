"""Case-independent, metered model liveness probes used before pool freeze."""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any, Callable, Literal, Mapping

from pydantic import Field, field_validator, model_validator

from .model_accounting import BudgetControlError, ModelAccountingError, RunCostLedger
from .model_identity import ResolvedModelIdentity
from .model_transport import (
    ModelTransportCapabilityError,
    ModelTransportError,
    SyncModelTransportPort,
    require_sync_model_transport,
)
from .pipeline_control import FrozenContract, canonical_sha256


MODEL_LIVENESS_PROTOCOL = "sgar-model-liveness-probe-v1"
DEFAULT_LIVENESS_TTL_SECONDS = 10 * 60
ModelLivenessOutcome = Literal[
    "live_verified",
    "permanent_unavailable",
    "transient_failure",
    "not_checked",
]


class ModelLivenessProbeError(RuntimeError):
    def __init__(
        self,
        error_code: str,
        *,
        responsibility: str = "framework",
    ) -> None:
        super().__init__(error_code)
        self.error_code = str(error_code)
        self.failure_responsibility = str(responsibility)
        self.retryable = False
        self.response_received = False


class ModelLivenessEvidence(FrozenContract):
    protocol: str = MODEL_LIVENESS_PROTOCOL
    resource_id: str = Field(min_length=1)
    api_model_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    manifest_sha256: str
    endpoint_identity_sha256: str
    request_sha256: str
    attempt_count: int = Field(ge=0, le=2)
    outcome: ModelLivenessOutcome
    reason_code: str = Field(min_length=1)
    checked_at_epoch: float
    expires_at_epoch: float
    accounting_reference: dict[str, Any] | None = None
    evidence_sha256: str = ""

    @field_validator(
        "manifest_sha256",
        "endpoint_identity_sha256",
        "request_sha256",
        "evidence_sha256",
    )
    @classmethod
    def _validate_hash(cls, value: str, info: Any) -> str:
        if info.field_name == "evidence_sha256" and not value:
            return value
        normalized = str(value).strip().lower()
        if len(normalized) != 64 or any(
            character not in "0123456789abcdef" for character in normalized
        ):
            raise ValueError(f"{info.field_name}_invalid")
        return normalized

    @model_validator(mode="after")
    def _seal(self) -> "ModelLivenessEvidence":
        if self.expires_at_epoch < self.checked_at_epoch:
            raise ValueError("model_liveness_expiry_invalid")
        if self.outcome == "not_checked" and self.attempt_count != 0:
            raise ValueError("unchecked_liveness_has_attempts")
        projection = self.model_dump(mode="python", exclude={"evidence_sha256"})
        expected = canonical_sha256(projection)
        if self.evidence_sha256 and self.evidence_sha256 != expected:
            raise ValueError("model_liveness_evidence_sha256_mismatch")
        object.__setattr__(self, "evidence_sha256", expected)
        return self

    def is_fresh(self, now_epoch: float) -> bool:
        return self.checked_at_epoch <= now_epoch < self.expires_at_epoch


class _CacheEntry:
    def __init__(self) -> None:
        self.in_flight = True
        self.evidence: ModelLivenessEvidence | None = None


def _status_code(exc: BaseException) -> int | None:
    direct = getattr(exc, "status_code", None)
    if isinstance(direct, int):
        return direct
    response = getattr(exc, "response", None)
    nested = getattr(response, "status_code", None)
    return nested if isinstance(nested, int) else None


def _no_response_infrastructure_failure(exc: BaseException) -> bool:
    name = type(exc).__name__.lower()
    return any(token in name for token in ("timeout", "connection", "connecterror"))


class ModelLivenessProbeService:
    """Single-flight liveness verification keyed by endpoint and model identity."""

    def __init__(
        self,
        transport: SyncModelTransportPort | None,
        *,
        ttl_seconds: float = DEFAULT_LIVENESS_TTL_SECONDS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.transport = (
            require_sync_model_transport(transport) if transport is not None else None
        )
        self.ttl_seconds = max(0.0, float(ttl_seconds))
        self.clock = clock
        self._condition = threading.Condition(threading.RLock())
        self._cache: dict[tuple[str, str, str, str], _CacheEntry] = {}

    def _key(self, identity: ResolvedModelIdentity) -> tuple[str, str, str, str]:
        endpoint_hash = (
            self.transport.endpoint_identity.identity_sha256
            if self.transport is not None
            else "0" * 64
        )
        return (
            endpoint_hash,
            identity.resource_id,
            identity.api_model_id,
            MODEL_LIVENESS_PROTOCOL,
        )

    @staticmethod
    def _request(identity: ResolvedModelIdentity) -> dict[str, Any]:
        return {
            "model": identity.api_model_id,
            "messages": [
                {
                    "role": "user",
                    "content": "Reply with OK. This is a synthetic liveness check.",
                }
            ],
            "max_tokens": 8,
            "temperature": 0.0,
            "stream": False,
        }

    def probe(
        self,
        *,
        identity: ResolvedModelIdentity,
        cost_ledger: RunCostLedger | None = None,
        subtask_id: str | None = None,
        subtask_revision: int | None = None,
        force_refresh: bool = False,
    ) -> ModelLivenessEvidence:
        key = self._key(identity)
        with self._condition:
            while True:
                entry = self._cache.get(key)
                if entry is None:
                    entry = _CacheEntry()
                    self._cache[key] = entry
                    break
                while entry.in_flight and self._cache.get(key) is entry:
                    self._condition.wait()
                if self._cache.get(key) is not entry:
                    continue
                if (
                    not force_refresh
                    and entry.evidence is not None
                    and entry.evidence.is_fresh(self.clock())
                ):
                    return entry.evidence
                entry = _CacheEntry()
                self._cache[key] = entry
                break

        try:
            evidence = self._probe_uncached(
                identity=identity,
                cost_ledger=cost_ledger,
                subtask_id=subtask_id,
                subtask_revision=subtask_revision,
            )
        except (asyncio.CancelledError, KeyboardInterrupt):
            with self._condition:
                if self._cache.get(key) is entry:
                    self._cache.pop(key, None)
                entry.in_flight = False
                self._condition.notify_all()
            raise
        except Exception:
            with self._condition:
                if self._cache.get(key) is entry:
                    self._cache.pop(key, None)
                entry.in_flight = False
                self._condition.notify_all()
            raise
        with self._condition:
            entry.evidence = evidence
            entry.in_flight = False
            self._condition.notify_all()
        return evidence

    def _probe_uncached(
        self,
        *,
        identity: ResolvedModelIdentity,
        cost_ledger: RunCostLedger | None,
        subtask_id: str | None,
        subtask_revision: int | None,
    ) -> ModelLivenessEvidence:
        checked_at = self.clock()
        endpoint_hash = (
            self.transport.endpoint_identity.identity_sha256
            if self.transport is not None
            else "0" * 64
        )
        request = self._request(identity)
        request_sha256 = canonical_sha256(request)
        common = {
            "resource_id": identity.resource_id,
            "api_model_id": identity.api_model_id,
            "provider": identity.provider,
            "manifest_sha256": identity.manifest_sha256,
            "endpoint_identity_sha256": endpoint_hash,
            "request_sha256": request_sha256,
            "checked_at_epoch": checked_at,
            "expires_at_epoch": checked_at + self.ttl_seconds,
        }
        if self.transport is None:
            return ModelLivenessEvidence(
                **common,
                attempt_count=0,
                outcome="not_checked",
                reason_code="model_liveness_transport_not_configured",
            )

        context = (
            cost_ledger.new_operation(
                stage="model_liveness_probe",
                subtask_id=subtask_id,
                subtask_revision=subtask_revision,
                selected_resource_id=identity.resource_id,
                model_resource_id=identity.resource_id,
            )
            if cost_ledger is not None
            else None
        )

        def accounting_reference() -> dict[str, Any] | None:
            if cost_ledger is None or context is None:
                return None
            try:
                return cost_ledger.operation_reference(context.operation_id)
            except Exception:
                return None

        for attempt in range(1, 3):
            try:
                response = self.transport.send(
                    ledger=cost_ledger,
                    context=context,
                    **request,
                )
            except BudgetControlError:
                raise
            except (ModelAccountingError, ModelTransportCapabilityError) as exc:
                raise ModelLivenessProbeError(
                    "model_liveness_accounting_or_transport_contract_failure"
                ) from exc
            except ModelTransportError as exc:
                raise ModelLivenessProbeError(
                    "model_liveness_transport_contract_failure"
                ) from exc
            except Exception as exc:
                status = _status_code(exc)
                if status in {401, 403}:
                    raise ModelLivenessProbeError(
                        "model_liveness_authentication_failure"
                    ) from exc
                if status == 404:
                    return ModelLivenessEvidence(
                        **common,
                        attempt_count=attempt,
                        outcome="permanent_unavailable",
                        reason_code="provider_model_not_found",
                        accounting_reference=accounting_reference(),
                    )
                retryable_no_response = (
                    status is not None and status >= 500
                ) or _no_response_infrastructure_failure(exc)
                if retryable_no_response and attempt < 2:
                    continue
                if retryable_no_response or status == 429:
                    return ModelLivenessEvidence(
                        **common,
                        attempt_count=attempt,
                        outcome="transient_failure",
                        reason_code="provider_model_liveness_transient_failure",
                        accounting_reference=accounting_reference(),
                    )
                raise ModelLivenessProbeError(
                    "model_liveness_unclassified_provider_failure"
                ) from exc
            else:
                reference = getattr(response, "accounting_reference", None)
                if not isinstance(reference, Mapping):
                    reference = accounting_reference()
                return ModelLivenessEvidence(
                    **common,
                    attempt_count=attempt,
                    outcome="live_verified",
                    reason_code="provider_model_live_verified",
                    accounting_reference=(dict(reference) if isinstance(reference, Mapping) else None),
                )
        raise AssertionError("model liveness probe must return or raise")


__all__ = [
    "DEFAULT_LIVENESS_TTL_SECONDS",
    "MODEL_LIVENESS_PROTOCOL",
    "ModelLivenessEvidence",
    "ModelLivenessOutcome",
    "ModelLivenessProbeError",
    "ModelLivenessProbeService",
]
