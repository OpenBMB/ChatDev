"""One-shot, fixed-identity system Full Generation fallback."""

from __future__ import annotations

import asyncio
import json
import threading
from copy import deepcopy
from typing import Any, Callable, Literal, Mapping

from pydantic import ValidationError

from .model_accounting import (
    AccountingPersistenceError,
    BudgetControlError,
    ModelCallContext,
    PricingCatalogError,
    RunCostLedger,
)
from .model_transport import (
    SyncModelTransportPort,
    classify_transport_exception,
    model_request_sha256,
    require_sync_model_transport,
)
from .model_response_contracts import (
    normalize_structured_response_mode,
    system_role_requirement,
    system_role_response_format,
    validate_structured_response_content,
)
from .pipeline_control import canonical_json_bytes, canonical_sha256
from .recovery_control import (
    FULL_GENERATION_PROTOCOL,
    FullGenerationDraft,
    FullGenerationInputEnvelope,
    RecoveryControlError,
    SystemFullGenerationPolicy,
)
from .resource_runtime import (
    ResourceCallResult,
    ResourceCallStatus,
    ResourceFailure,
)


FULL_GENERATION_PROMPT_VERSION = "system-full-generation-v2"
FULL_GENERATION_MAX_TRANSPORT_ATTEMPTS = 3
FULL_GENERATION_SYSTEM_PROMPT = (
    "You are SGAR's one-shot system Full Generation fallback. Return exactly one strict "
    "JSON object matching sgar-full-generation-v2 with artifact_type, content, and a short "
    "concise_rationale. Produce a complete replacement artifact satisfying the supplied "
    "public contract. Use only public context, registered successful checkpoints, and the "
    "authorized_materials view. A material marked full contains all available semantic "
    "content; bounded contains only the supplied stable excerpt; descriptor_only contains "
    "no readable content. Never claim to have read content that was not supplied. Do not "
    "mention or infer candidates, Gold, validators, hidden feedback, host paths, secrets, "
    "failed partial artifacts, or chain-of-thought. Preserve content exactly inside the "
    "content string. Follow the delivery language declared by the public contract; keep "
    "framework-authored rationale text in English."
)
FULL_GENERATION_PROMPT_SHA256 = canonical_sha256(
    {
        "version": FULL_GENERATION_PROMPT_VERSION,
        "prompt": FULL_GENERATION_SYSTEM_PROMPT,
        "protocol": FULL_GENERATION_PROTOCOL,
    }
)


def build_full_generation_call_kwargs(
    envelope: FullGenerationInputEnvelope,
) -> dict[str, Any]:
    policy = envelope.system_policy
    system_prompt = FULL_GENERATION_SYSTEM_PROMPT
    selected_mode = normalize_structured_response_mode(policy.response_mode)
    kwargs: dict[str, Any] = {
        "model": policy.api_model_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": canonical_json_bytes(envelope.model_dump(mode="json")).decode(
                    "utf-8"
                ),
            },
        ],
        "temperature": policy.temperature,
        "max_tokens": policy.max_tokens,
        "stream": policy.allow_streaming,
    }
    kwargs["response_format"] = system_role_response_format(
        "full_generation",
        mode=selected_mode,
    )
    return kwargs


def _response_content(response: Any, *, streaming: bool) -> str:
    if not streaming:
        try:
            content = response.choices[0].message.content
        except Exception as exc:
            raise RecoveryControlError("full_generation_response_content_missing") from exc
        if not isinstance(content, str) or not content:
            raise RecoveryControlError("full_generation_response_content_invalid")
        return content
    parts: list[str] = []
    try:
        for chunk in response:
            choices = getattr(chunk, "choices", None) or ()
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            content = getattr(delta, "content", None)
            if isinstance(content, str):
                parts.append(content)
    except Exception as exc:
        raise RecoveryControlError("full_generation_stream_consumption_failed") from exc
    joined = "".join(parts)
    if not joined:
        raise RecoveryControlError("full_generation_stream_content_missing")
    return joined


def _failure_result(
    *,
    envelope: FullGenerationInputEnvelope,
    responsibility: Literal["framework", "infrastructure", "research", "budget"],
    failure_stage: str,
    failure_code: str,
    error: BaseException | None,
    request_sha256: str,
    attempts: tuple[dict[str, Any], ...],
    response_received: bool,
    retryable: bool = False,
) -> ResourceCallResult:
    return ResourceCallResult(
        call_id=f"full-generation:{envelope.input_sha256}",
        resource_id=envelope.system_policy.resource_id,
        entrypoint_id="invoke",
        status=ResourceCallStatus(f"{responsibility}_failure"),
        failure=ResourceFailure.create(
            responsibility=responsibility,
            failure_stage=failure_stage,
            failure_code=failure_code,
            error=error,
            retryable=retryable,
            response_received=response_received,
        ),
        usage_reference=(
            f"full_generation:{envelope.input_sha256}" if attempts else None
        ),
        execution_audit={
            "protocol": FULL_GENERATION_PROTOCOL,
            "request_sha256": request_sha256,
            "attempts": list(attempts),
            "response_received": response_received,
            "semantic_normalization_applied": False,
        },
        provenance={
            "input_sha256": envelope.input_sha256,
            "candidate_pool_sha256": envelope.candidate_pool_sha256,
            "failure_evidence_sha256": list(envelope.failure_evidence_sha256),
            "system_policy_sha256": envelope.system_policy.policy_sha256,
            "authorized_material_view_sha256": envelope.authorized_materials.view_sha256,
            "authorized_material_audit": envelope.authorized_materials.audit_projection(),
        },
        output_contract_status="failed",
    )


class FullGenerationExecutor:
    def __init__(
        self,
        *,
        transport: SyncModelTransportPort,
        cost_ledger: RunCostLedger,
        system_policy: SystemFullGenerationPolicy,
    ) -> None:
        normalize_structured_response_mode(system_policy.response_mode)
        if (
            cost_ledger.catalog.pricing_catalog_sha256
            != system_policy.pricing_catalog_sha256
        ):
            raise RecoveryControlError("full_generation_pricing_catalog_mismatch")
        price = cost_ledger.catalog.resolve(
            resource_id=system_policy.resource_id,
            api_model_id=system_policy.api_model_id,
        )
        if price.resource_id != system_policy.resource_id:
            raise RecoveryControlError("full_generation_model_identity_mismatch")
        if (
            system_policy.prompt_version != FULL_GENERATION_PROMPT_VERSION
            or system_policy.prompt_sha256 != FULL_GENERATION_PROMPT_SHA256
        ):
            raise RecoveryControlError("full_generation_prompt_identity_mismatch")
        self.transport = require_sync_model_transport(transport)
        self.cost_ledger = cost_ledger
        self.system_policy = system_policy
        self._condition = threading.Condition(threading.RLock())
        self._inflight: set[str] = set()
        self._cache: dict[str, ResourceCallResult] = {}

    def execute(
        self,
        envelope: FullGenerationInputEnvelope,
        *,
        payload_guard: Callable[[Mapping[str, Any]], None] | None = None,
    ) -> ResourceCallResult:
        if envelope.system_policy.policy_sha256 != self.system_policy.policy_sha256:
            raise RecoveryControlError("full_generation_request_policy_mismatch")
        key = envelope.input_sha256
        with self._condition:
            while key in self._inflight:
                self._condition.wait()
            if key in self._cache:
                return self._cache[key]
            self._inflight.add(key)
        try:
            result = self._execute_once(envelope, payload_guard=payload_guard)
            with self._condition:
                self._cache[key] = result
            return result
        finally:
            with self._condition:
                self._inflight.discard(key)
                self._condition.notify_all()

    def _execute_once(
        self,
        envelope: FullGenerationInputEnvelope,
        *,
        payload_guard: Callable[[Mapping[str, Any]], None] | None,
    ) -> ResourceCallResult:
        api_kwargs = build_full_generation_call_kwargs(envelope)
        request_sha256 = model_request_sha256(api_kwargs)
        operation_id = f"full_generation:{envelope.input_sha256}"
        context = ModelCallContext(
            operation_id=operation_id,
            stage="full_generation",
            subtask_id=envelope.revision.subtask_id,
            subtask_revision=envelope.revision.subtask_revision,
            selected_resource_id=self.system_policy.resource_id,
            model_resource_id=self.system_policy.resource_id,
        )
        attempts: list[dict[str, Any]] = []
        response: Any = None
        for attempt in range(1, FULL_GENERATION_MAX_TRANSPORT_ATTEMPTS + 1):
            if model_request_sha256(api_kwargs) != request_sha256:
                raise RecoveryControlError("full_generation_request_hash_changed")
            if payload_guard is not None:
                try:
                    payload_guard(deepcopy(api_kwargs))
                except asyncio.CancelledError:
                    raise
                except BaseException as exc:
                    return _failure_result(
                        envelope=envelope,
                        responsibility="framework",
                        failure_stage="full_generation_payload_guard",
                        failure_code="full_generation_payload_guard_failed",
                        error=exc,
                        request_sha256=request_sha256,
                        attempts=tuple(attempts),
                        response_received=False,
                    )
            try:
                response = self.transport.send(
                    ledger=self.cost_ledger,
                    context=context,
                    **deepcopy(api_kwargs),
                )
            except asyncio.CancelledError:
                raise
            except BudgetControlError as exc:
                attempts.append({"attempt": attempt, "outcome": "budget_failure"})
                return _failure_result(
                    envelope=envelope,
                    responsibility="budget",
                    failure_stage="full_generation_transport",
                    failure_code="budget_control",
                    error=exc,
                    request_sha256=request_sha256,
                    attempts=tuple(attempts),
                    response_received=False,
                )
            except (PricingCatalogError, AccountingPersistenceError) as exc:
                attempts.append({"attempt": attempt, "outcome": "framework_failure"})
                return _failure_result(
                    envelope=envelope,
                    responsibility="framework",
                    failure_stage="full_generation_accounting",
                    failure_code="full_generation_accounting_failed",
                    error=exc,
                    request_sha256=request_sha256,
                    attempts=tuple(attempts),
                    response_received=False,
                )
            except BaseException as exc:
                retryable, code = classify_transport_exception(exc)
                attempts.append(
                    {
                        "attempt": attempt,
                        "outcome": (
                            "infrastructure_failure" if retryable else "framework_failure"
                        ),
                        "failure_code": code,
                    }
                )
                if retryable and attempt < FULL_GENERATION_MAX_TRANSPORT_ATTEMPTS:
                    continue
                return _failure_result(
                    envelope=envelope,
                    responsibility="infrastructure" if retryable else "framework",
                    failure_stage="full_generation_transport",
                    failure_code=code,
                    error=exc,
                    request_sha256=request_sha256,
                    attempts=tuple(attempts),
                    response_received=False,
                    retryable=False,
                )
            attempts.append({"attempt": attempt, "outcome": "success"})
            break
        if response is None:
            raise RecoveryControlError("full_generation_transport_terminal_state_missing")
        try:
            raw_content = _response_content(
                response,
                streaming=self.system_policy.allow_streaming,
            )
            decoded = validate_structured_response_content(
                raw_content,
                requirement=system_role_requirement("full_generation"),
                mode=self.system_policy.response_mode,
            )
            draft = FullGenerationDraft.model_validate_json(
                json.dumps(decoded, ensure_ascii=False),
                strict=True,
            )
        except (RecoveryControlError, ValidationError, ValueError) as exc:
            return _failure_result(
                envelope=envelope,
                responsibility="research",
                failure_stage="full_generation_protocol",
                failure_code="full_generation_response_schema_invalid",
                error=exc,
                request_sha256=request_sha256,
                attempts=tuple(attempts),
                response_received=True,
            )
        expected_type = str(envelope.contract_projection.get("artifact_type") or "")
        if not expected_type or draft.artifact_type != expected_type:
            return _failure_result(
                envelope=envelope,
                responsibility="research",
                failure_stage="full_generation_output_contract",
                failure_code="full_generation_artifact_type_mismatch",
                error=None,
                request_sha256=request_sha256,
                attempts=tuple(attempts),
                response_received=True,
            )
        canonical_value: Any = draft.content
        if expected_type == "json":
            try:
                canonical_value = json.loads(draft.content)
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                return _failure_result(
                    envelope=envelope,
                    responsibility="research",
                    failure_stage="full_generation_output_contract",
                    failure_code="full_generation_json_invalid",
                    error=exc,
                    request_sha256=request_sha256,
                    attempts=tuple(attempts),
                    response_received=True,
                )
        return ResourceCallResult(
            call_id=f"full-generation:{envelope.input_sha256}",
            resource_id=self.system_policy.resource_id,
            entrypoint_id="invoke",
            status=ResourceCallStatus.SUCCESS,
            canonical_value=canonical_value,
            presentation=draft.content,
            usage_reference=operation_id,
            execution_audit={
                "protocol": FULL_GENERATION_PROTOCOL,
                "request_sha256": request_sha256,
                "attempts": attempts,
                "response_received": True,
                "semantic_normalization_applied": False,
                "system_fallback_resource_id": self.system_policy.resource_id,
            },
            provenance={
                "input_sha256": envelope.input_sha256,
                "candidate_pool_sha256": envelope.candidate_pool_sha256,
                "failure_evidence_sha256": list(envelope.failure_evidence_sha256),
                "system_policy_sha256": envelope.system_policy.policy_sha256,
                "authorized_material_view_sha256": envelope.authorized_materials.view_sha256,
                "authorized_material_audit": envelope.authorized_materials.audit_projection(),
            },
            output_contract_status="checked",
        )


__all__ = [
    "FULL_GENERATION_PROMPT_SHA256",
    "FULL_GENERATION_PROMPT_VERSION",
    "FULL_GENERATION_SYSTEM_PROMPT",
    "FullGenerationExecutor",
    "build_full_generation_call_kwargs",
]
