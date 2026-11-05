"""Provider compatibility helpers for OpenAI-compatible chat APIs.

The routing stack talks to several OpenAI-compatible relays. Some models accept
the usual OpenAI chat parameters while others reject a subset such as
``temperature``. These helpers keep the default request shape for compatible
models, then retry without rejected optional parameters when a provider clearly
reports that incompatibility.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .model_accounting import ModelCallContext, RunCostLedger
from .model_transport import (
    AsyncModelTransportPort,
    SyncModelTransportPort,
    require_async_model_transport,
    require_sync_model_transport,
)


def extract_provider_error_message(exc: Exception) -> str:
    """Return the provider-facing error message when OpenAI wraps it."""
    message = str(exc)
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error", body)
        if isinstance(error, dict):
            message = str(error.get("message") or message)
    return message


def is_temperature_unsupported_error(exc: Exception | str) -> bool:
    """Detect errors caused by models rejecting the temperature parameter."""
    message = extract_provider_error_message(exc) if isinstance(exc, Exception) else str(exc)
    lowered = message.lower()
    return any(
        marker in lowered
        for marker in (
            "`temperature` is deprecated",
            "temperature is deprecated",
            "unsupported parameter: 'temperature'",
            'unsupported parameter: "temperature"',
            "temperature parameter is not supported",
            "temperature is not supported",
            "does not support temperature",
            "temperature unsupported",
        )
    )


def is_response_format_unsupported_error(exc: Exception | str) -> bool:
    """Detect provider rejection of JSON/structured response_format."""
    message = extract_provider_error_message(exc) if isinstance(exc, Exception) else str(exc)
    lowered = message.lower()
    return any(
        marker in lowered
        for marker in (
            "does not support feature",
            "unsupported feature",
            "structured-outputs",
            "structured outputs",
            "response_format",
            "json mode",
        )
    )


def prepare_chat_kwargs_for_model(
    api_kwargs: Dict[str, Any],
    *,
    registry: Optional[Any] = None,
) -> Dict[str, Any]:
    """Apply known runtime capability facts before calling the provider."""
    prepared = dict(api_kwargs)
    model_id = str(prepared.get("model") or "")
    if registry is not None and model_id and not registry.allows(model_id, "temperature_ok"):
        prepared.pop("temperature", None)
    return prepared


def _record_temperature_failure(
    model_id: str,
    registry: Optional[Any],
    message: str,
) -> None:
    if registry is None or not model_id:
        return
    registry.record_failure(
        model_id,
        "temperature_ok",
        "temperature_unsupported",
        message,
    )


def _record_temperature_success(model_id: str, registry: Optional[Any], api_kwargs: Dict[str, Any]) -> None:
    if registry is None or not model_id or "temperature" not in api_kwargs:
        return
    registry.record_success(model_id, "temperature_ok")


def create_chat_completion_with_compat(
    transport: SyncModelTransportPort,
    *,
    registry: Optional[Any] = None,
    cost_ledger: Optional[RunCostLedger] = None,
    accounting_context: Optional[ModelCallContext] = None,
    **api_kwargs: Any,
) -> Any:
    """Call sync chat.completions.create, retrying without unsupported temperature."""
    transport = require_sync_model_transport(transport)
    prepared = prepare_chat_kwargs_for_model(api_kwargs, registry=registry)
    model_id = str(prepared.get("model") or api_kwargs.get("model") or "")
    try:
        response = transport.send(
            ledger=cost_ledger,
            context=accounting_context,
            **prepared,
        )
        _record_temperature_success(model_id, registry, prepared)
        return response
    except Exception as exc:
        if "temperature" not in prepared or not is_temperature_unsupported_error(exc):
            raise
        message = extract_provider_error_message(exc)
        _record_temperature_failure(model_id, registry, message)
        retry_kwargs = dict(prepared)
        retry_kwargs.pop("temperature", None)
        response = transport.send(
            ledger=cost_ledger,
            context=accounting_context,
            **retry_kwargs,
        )
        return response


async def async_create_chat_completion_with_compat(
    transport: AsyncModelTransportPort,
    *,
    registry: Optional[Any] = None,
    cost_ledger: Optional[RunCostLedger] = None,
    accounting_context: Optional[ModelCallContext] = None,
    payload_guard: Optional[Any] = None,
    **api_kwargs: Any,
) -> Any:
    """Call async chat.completions.create, retrying without unsupported temperature."""
    transport = require_async_model_transport(transport)
    prepared = prepare_chat_kwargs_for_model(api_kwargs, registry=registry)
    model_id = str(prepared.get("model") or api_kwargs.get("model") or "")
    try:
        if payload_guard is not None:
            payload_guard(dict(prepared))
        response = await transport.send(
            ledger=cost_ledger,
            context=accounting_context,
            **prepared,
        )
        _record_temperature_success(model_id, registry, prepared)
        return response
    except Exception as exc:
        if "temperature" not in prepared or not is_temperature_unsupported_error(exc):
            raise
        message = extract_provider_error_message(exc)
        _record_temperature_failure(model_id, registry, message)
        retry_kwargs = dict(prepared)
        retry_kwargs.pop("temperature", None)
        if payload_guard is not None:
            payload_guard(dict(retry_kwargs))
        response = await transport.send(
            ledger=cost_ledger,
            context=accounting_context,
            **retry_kwargs,
        )
        return response
