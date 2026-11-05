"""The only production boundary that sends OpenAI-compatible chat requests."""

from __future__ import annotations

from . import terminal_progress

from sgar_mvp.src.direct_network import direct_async_http_client, direct_sync_http_client

import asyncio
import hashlib
import json
import os
import time
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Awaitable, Callable, Mapping

from pydantic import BaseModel
from openai import (
    AsyncOpenAI,
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
    RateLimitError,
)

from .model_accounting import ModelCallContext, ModelCallHandle, RunCostLedger
from .model_request_budget import ModelAttemptTimeout, current_attempt_timeout
from .pipeline_control import FrozenContract, canonical_sha256


MODEL_TRANSPORT_PROTOCOL = "sgar-model-transport-v2"
PRODUCTION_MODEL_TRANSPORT_PROVIDER = "openai_compatible"
PRODUCTION_MODEL_TRANSPORT_CREDENTIAL_ENV = "LLM_API_KEY"
PRODUCTION_MODEL_TRANSPORT_TIMEOUT_SECONDS = 1200.0
TEXT_REQUEST_CHAT_OVERHEAD_TOKEN_BOUND = 1024


class ModelTransportError(RuntimeError):
    pass


class ModelTransportCapabilityError(ModelTransportError):
    """Raised before a request when a sync/async capability is miswired."""

    error_code = "model_transport_capability_mismatch"


class ProviderEndpointIdentity(FrozenContract):
    """Secret-free identity shared by both provider ports."""

    protocol: str = MODEL_TRANSPORT_PROTOCOL
    provider: str
    base_url_identity: str
    credential_environment_variable: str
    timeout_seconds: float
    max_retries: int = 0
    identity_sha256: str

    @classmethod
    def create(
        cls,
        *,
        provider: str,
        base_url: str,
        credential_environment_variable: str,
        timeout_seconds: float,
        max_retries: int = 0,
    ) -> "ProviderEndpointIdentity":
        payload = {
            "protocol": MODEL_TRANSPORT_PROTOCOL,
            "provider": str(provider).strip(),
            "base_url_identity": hashlib.sha256(
                str(base_url).strip().rstrip("/").encode("utf-8")
            ).hexdigest(),
            "credential_environment_variable": str(
                credential_environment_variable
            ).strip(),
            "timeout_seconds": float(timeout_seconds),
            "max_retries": int(max_retries),
        }
        if not payload["provider"]:
            raise ModelTransportError("model_transport_provider_missing")
        if not payload["credential_environment_variable"]:
            raise ModelTransportError("model_transport_credential_name_missing")
        if payload["timeout_seconds"] <= 0 or payload["max_retries"] != 0:
            raise ModelTransportError("model_transport_endpoint_policy_invalid")
        return cls(**payload, identity_sha256=canonical_sha256(payload))


def production_model_endpoint_identity(*, base_url: str) -> ProviderEndpointIdentity:
    """Return the one endpoint identity shared by probes and formal runtime."""

    return ProviderEndpointIdentity.create(
        provider=PRODUCTION_MODEL_TRANSPORT_PROVIDER,
        base_url=base_url,
        credential_environment_variable=PRODUCTION_MODEL_TRANSPORT_CREDENTIAL_ENV,
        timeout_seconds=PRODUCTION_MODEL_TRANSPORT_TIMEOUT_SECONDS,
        max_retries=0,
    )


class SyncModelTransportPort:
    """Explicit synchronous chat-completion capability."""

    error_code = ModelTransportCapabilityError.error_code

    def __init__(
        self,
        *,
        endpoint_identity: ProviderEndpointIdentity,
        sender: Callable[..., "MeteredChatResponse"],
    ) -> None:
        if not callable(sender):
            raise ModelTransportCapabilityError(self.error_code)
        self.endpoint_identity = endpoint_identity
        self._sender = sender

    @classmethod
    def from_sdk_client(
        cls,
        *,
        client: OpenAI,
        endpoint_identity: ProviderEndpointIdentity,
    ) -> "SyncModelTransportPort":
        if not isinstance(client, OpenAI) or isinstance(client, AsyncOpenAI):
            raise ModelTransportCapabilityError(cls.error_code)

        def sender(
            *,
            ledger: RunCostLedger | None = None,
            context: ModelCallContext | None = None,
            **api_kwargs: Any,
        ) -> "MeteredChatResponse":
            return send_chat_completion(
                client,
                ledger=ledger,
                context=context,
                **api_kwargs,
            )

        return cls(
            endpoint_identity=endpoint_identity,
            sender=sender,
        )

    @classmethod
    def from_sender(
        cls,
        *,
        sender: Callable[..., "MeteredChatResponse"],
        endpoint_identity: ProviderEndpointIdentity,
    ) -> "SyncModelTransportPort":
        return cls(endpoint_identity=endpoint_identity, sender=sender)

    from_sender_for_testing = from_sender

    def send(
        self,
        *,
        ledger: RunCostLedger | None = None,
        context: ModelCallContext | None = None,
        **api_kwargs: Any,
    ) -> "MeteredChatResponse":
        return self._sender(ledger=ledger, context=context, **api_kwargs)


class AsyncModelTransportPort:
    """Explicit asynchronous chat-completion capability."""

    error_code = ModelTransportCapabilityError.error_code

    def __init__(
        self,
        *,
        endpoint_identity: ProviderEndpointIdentity,
        sender: Callable[..., Awaitable["MeteredChatResponse"]],
    ) -> None:
        if not callable(sender):
            raise ModelTransportCapabilityError(self.error_code)
        self.endpoint_identity = endpoint_identity
        self._sender = sender

    @classmethod
    def from_sdk_client(
        cls,
        *,
        client: AsyncOpenAI,
        endpoint_identity: ProviderEndpointIdentity,
    ) -> "AsyncModelTransportPort":
        if not isinstance(client, AsyncOpenAI) or isinstance(client, OpenAI):
            raise ModelTransportCapabilityError(cls.error_code)

        async def sender(
            *,
            ledger: RunCostLedger | None = None,
            context: ModelCallContext | None = None,
            **api_kwargs: Any,
        ) -> "MeteredChatResponse":
            return await async_send_chat_completion(
                client,
                ledger=ledger,
                context=context,
                **api_kwargs,
            )

        return cls(
            endpoint_identity=endpoint_identity,
            sender=sender,
        )

    @classmethod
    def from_sender(
        cls,
        *,
        sender: Callable[..., Awaitable["MeteredChatResponse"]],
        endpoint_identity: ProviderEndpointIdentity,
    ) -> "AsyncModelTransportPort":
        return cls(endpoint_identity=endpoint_identity, sender=sender)

    from_sender_for_testing = from_sender

    async def send(
        self,
        *,
        ledger: RunCostLedger | None = None,
        context: ModelCallContext | None = None,
        **api_kwargs: Any,
    ) -> "MeteredChatResponse":
        return await self._sender(ledger=ledger, context=context, **api_kwargs)


@dataclass(frozen=True)
class ModelTransportBundle:
    """Typed pair created from one endpoint policy and credential source."""

    sync: SyncModelTransportPort
    async_port: AsyncModelTransportPort
    endpoint_identity: ProviderEndpointIdentity
    capability_sha256: str
    protocol: str = MODEL_TRANSPORT_PROTOCOL


def create_model_transport_bundle(
    *,
    api_key: str,
    base_url: str,
    provider: str = "openai_compatible",
    credential_environment_variable: str = "LLM_API_KEY",
    timeout_seconds: float = 60.0,
    sync_http_client: Any | None = None,
    async_http_client: Any | None = None,
) -> ModelTransportBundle:
    """Create sync and async SDK clients from one immutable identity."""

    if not str(api_key):
        raise ModelTransportError("model_transport_credential_missing")
    if (
        os.environ.get("SGAR_EXTERNAL_MODEL_NETWORK_DISABLED") == "1"
        and sync_http_client is None
        and async_http_client is None
    ):
        raise ModelTransportError("external_model_network_disabled")
    endpoint = ProviderEndpointIdentity.create(
        provider=provider,
        base_url=base_url,
        credential_environment_variable=credential_environment_variable,
        timeout_seconds=timeout_seconds,
        max_retries=0,
    )
    sync_client = (
        OpenAI(
            http_client=direct_sync_http_client(),
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds,
            max_retries=0,
        )
        if sync_http_client is None
        else OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds,
            max_retries=0,
            http_client=sync_http_client,
        )
    )
    async_client = (
        AsyncOpenAI(
            http_client=direct_async_http_client(),
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds,
            max_retries=0,
        )
        if async_http_client is None
        else AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds,
            max_retries=0,
            http_client=async_http_client,
        )
    )
    sync_port = SyncModelTransportPort.from_sdk_client(
        client=sync_client,
        endpoint_identity=endpoint,
    )
    async_port = AsyncModelTransportPort.from_sdk_client(
        client=async_client,
        endpoint_identity=endpoint,
    )
    capability_payload = {
        "protocol": MODEL_TRANSPORT_PROTOCOL,
        "endpoint_identity_sha256": endpoint.identity_sha256,
        "capabilities": ["sync_chat_completions", "async_chat_completions"],
    }
    return ModelTransportBundle(
        sync=sync_port,
        async_port=async_port,
        endpoint_identity=endpoint,
        capability_sha256=canonical_sha256(capability_payload),
    )


def create_production_model_transport_bundle(
    *,
    api_key: str,
    base_url: str,
    sync_http_client: Any | None = None,
    async_http_client: Any | None = None,
) -> ModelTransportBundle:
    """Create the sealed production transport without caller-owned policy knobs."""

    return create_model_transport_bundle(
        api_key=api_key,
        base_url=base_url,
        provider=PRODUCTION_MODEL_TRANSPORT_PROVIDER,
        credential_environment_variable=PRODUCTION_MODEL_TRANSPORT_CREDENTIAL_ENV,
        timeout_seconds=PRODUCTION_MODEL_TRANSPORT_TIMEOUT_SECONDS,
        sync_http_client=sync_http_client,
        async_http_client=async_http_client,
    )


def legacy_sync_transport_from_client(
    *,
    client: Any,
    endpoint_identity: ProviderEndpointIdentity,
) -> SyncModelTransportPort:
    """Isolate an explicitly legacy OpenAI-compatible client at the boundary.

    Formal production composition uses :func:`create_model_transport_bundle`.
    This adapter exists only for legacy/offline APIs whose tests inject a
    minimal compatible client; metering still occurs through the one SDK send
    boundary in this module.
    """

    def sender(
        *,
        ledger: RunCostLedger | None = None,
        context: ModelCallContext | None = None,
        **api_kwargs: Any,
    ) -> "MeteredChatResponse":
        return send_chat_completion(
            client,
            ledger=ledger,
            context=context,
            **api_kwargs,
        )

    return SyncModelTransportPort.from_sender(
        sender=sender,
        endpoint_identity=endpoint_identity,
    )


def require_sync_model_transport(value: Any) -> SyncModelTransportPort:
    if not isinstance(value, SyncModelTransportPort):
        raise ModelTransportCapabilityError(ModelTransportCapabilityError.error_code)
    return value


def require_async_model_transport(value: Any) -> AsyncModelTransportPort:
    if not isinstance(value, AsyncModelTransportPort):
        raise ModelTransportCapabilityError(ModelTransportCapabilityError.error_code)
    return value


def classify_transport_exception(exc: BaseException) -> tuple[bool, str]:
    """Classify provider transport failures without inspecting message text.

    The result is deliberately limited to provider exception classes and HTTP
    status codes.  Callers remain responsible for deciding their retry budget;
    this helper only provides the shared structured producer classification.
    """

    target: BaseException = exc
    seen: set[int] = set()
    while id(target) not in seen:
        seen.add(id(target))
        code = str(getattr(target, "code", "") or "").strip().lower()
        parameter = str(getattr(target, "param", "") or "").strip().lower()
        body = getattr(target, "body", None)
        if isinstance(body, Mapping):
            error = body.get("error", body)
            if isinstance(error, Mapping):
                code = str(error.get("code") or code).strip().lower()
                parameter = str(error.get("param") or parameter).strip().lower()
        if code in {
            "invalid_json_schema",
            "unsupported_json_schema",
            "unsupported_response_format",
            "response_format_unsupported",
            "structured_outputs_not_supported",
        } or "json_schema" in parameter.replace("-", "_"):
            return False, "provider_exact_schema_unsupported"
        if isinstance(target, (ModelAttemptTimeout, APITimeoutError)):
            return True, "provider_timeout"
        if isinstance(target, APIConnectionError):
            return True, "provider_connection_error"
        if isinstance(target, RateLimitError):
            return True, "provider_rate_limit"
        status_code = getattr(target, "status_code", None)
        if isinstance(target, APIStatusError) or isinstance(status_code, int):
            status = int(status_code or 0)
            if status == 408:
                # Some gateways express an upstream generation timeout as an
                # HTTP response. It is still a transport failure, not an
                # invalid Compiler/schema request. Callers retain their own
                # retry budget and unknown-usage accounting policy.
                return True, "provider_timeout"
            if status == 429:
                return True, "provider_rate_limit"
            if 500 <= status <= 599:
                return True, "provider_server_error"
            if status in {401, 403}:
                return False, "provider_authorization_error"
            if status == 404:
                return False, "provider_model_unavailable"
            return False, "provider_non_retryable_status"
        nested = target.__cause__ or target.__context__
        if not isinstance(nested, BaseException):
            break
        target = nested
    return False, "provider_non_transport_error"


def _request_json_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _request_json_value(value.model_dump(mode="json"))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, Mapping):
        return {
            str(key): _request_json_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_request_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ModelTransportError(f"unhashable_model_request_type:{type(value).__name__}")


def model_request_sha256(api_kwargs: Mapping[str, Any]) -> str:
    try:
        payload = json.dumps(
            _request_json_value(api_kwargs),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ModelTransportError("model_request_is_not_canonical_json") from exc
    return hashlib.sha256(payload).hexdigest()


def _text_request_token_upper_bounds(
    api_kwargs: Mapping[str, Any],
) -> tuple[int | None, int | None, str | None]:
    """Return conservative token bounds for text-only, output-capped requests.

    Canonical UTF-8 byte length bounds tokenizer tokens for text payloads; a
    fixed chat-envelope allowance covers provider message framing.  Requests
    carrying media stay unbounded because remote media tokenization is not
    determined by request bytes.
    """

    def contains_media(value: Any) -> bool:
        if isinstance(value, Mapping):
            item_type = str(value.get("type") or "").strip().lower()
            if item_type in {
                "image", "image_url", "input_image", "audio", "input_audio",
                "video", "input_video", "file", "input_file",
            }:
                return True
            return any(contains_media(item) for item in value.values())
        if isinstance(value, (list, tuple)):
            return any(contains_media(item) for item in value)
        return False

    if contains_media(api_kwargs.get("messages")):
        return None, None, None
    output_limit = api_kwargs.get("max_completion_tokens")
    if output_limit is None:
        output_limit = api_kwargs.get("max_tokens")
    if type(output_limit) is not int or output_limit <= 0:
        return None, None, None
    try:
        payload = json.dumps(
            _request_json_value(api_kwargs),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        return None, None, None
    return (
        len(payload) + TEXT_REQUEST_CHAT_OVERHEAD_TOKEN_BOUND,
        output_limit,
        "canonical_utf8_bytes_plus_chat_overhead",
    )


class MeteredChatResponse:
    """Transparent response proxy that settles streaming usage exactly once."""

    def __init__(
        self,
        response: Any,
        *,
        ledger: RunCostLedger | None,
        handle: ModelCallHandle | None,
        stream: bool,
        async_stream: bool,
        deadline_monotonic: float | None = None,
    ) -> None:
        self._response = response
        self._ledger = ledger
        self._handle = handle
        self._stream = bool(stream)
        self._async_stream = bool(async_stream)
        self._deadline_monotonic = deadline_monotonic
        self._settled = not self._stream
        self._observed_usage: Any = None
        self.accounting_reference = (
            ledger.accounting_reference(handle)
            if ledger is not None and handle is not None
            else None
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._response, name)

    def _capture_usage(self, item: Any) -> None:
        usage = getattr(item, "usage", None)
        if usage is not None:
            self._observed_usage = usage

    def _settle(self, *, error: BaseException | None = None) -> None:
        if self._settled:
            return
        self._settled = True
        if self._ledger is not None and self._handle is not None:
            self._ledger.finish_call(
                self._handle,
                response_received=True,
                usage=self._observed_usage,
                error=error,
                completion_status="stream_interrupted" if error else "stream_consumed",
            )
            self.accounting_reference = self._ledger.accounting_reference(self._handle)

    def __iter__(self):
        if not self._stream or self._async_stream:
            return iter(self._response)

        def consume():
            try:
                for item in self._response:
                    self._capture_usage(item)
                    yield item
            except BaseException as exc:
                self._settle(error=exc)
                raise
            else:
                self._settle()

        return consume()

    def __aiter__(self):
        if not self._stream or not self._async_stream:
            return self._response.__aiter__()

        async def consume():
            try:
                iterator = self._response.__aiter__()
                while True:
                    try:
                        if self._deadline_monotonic is None:
                            item = await iterator.__anext__()
                        else:
                            remaining = self._deadline_monotonic - time.monotonic()
                            if remaining <= 0:
                                raise ModelAttemptTimeout("Model stream exceeded its attempt deadline")
                            try:
                                item = await asyncio.wait_for(iterator.__anext__(), timeout=remaining)
                            except asyncio.TimeoutError as exc:
                                raise ModelAttemptTimeout("Model stream exceeded its attempt deadline") from exc
                    except StopAsyncIteration:
                        break
                    self._capture_usage(item)
                    yield item
            except BaseException as exc:
                self._settle(error=exc)
                raise
            else:
                self._settle()
            finally:
                close = getattr(self._response, "close", None)
                if close is not None:
                    try:
                        await asyncio.wait_for(close(), timeout=1.0)
                    except Exception as exc:
                        # Cleanup must not overwrite the already-settled
                        # response/failure or consume the downstream reserve.
                        terminal_progress.transport_detail(exc)

        return consume()


def _cache_billing_mode(value: Any) -> tuple[str, str]:
    """Read actual cache markers without changing the outbound request."""
    ttls: set[str] = set()
    def visit(node: Any) -> None:
        if isinstance(node, Mapping):
            marker = node.get("cache_control")
            if isinstance(marker, Mapping) and marker.get("type") == "ephemeral":
                ttls.add(str(marker.get("ttl") or "5m"))
            for child in node.values():
                visit(child)
        elif isinstance(node, (list, tuple)):
            for child in node:
                visit(child)
    visit(value)
    return ("explicit", next(iter(ttls)) if len(ttls) == 1 else "mixed") if ttls else ("implicit", "5m")


def _begin(
    *,
    ledger: RunCostLedger | None,
    context: ModelCallContext | None,
    api_kwargs: Mapping[str, Any],
) -> tuple[ModelCallHandle | None, str]:
    request_hash = model_request_sha256(api_kwargs)
    if ledger is None:
        return None, request_hash
    if context is None:
        raise ModelTransportError("metered_model_call_requires_context")
    model_ref = str(api_kwargs.get("model") or "").strip()
    if not model_ref:
        raise ModelTransportError("model_request_has_no_model_identity")
    input_upper, output_upper, upper_bound_basis = _text_request_token_upper_bounds(
        api_kwargs
    )
    cache_mode, cache_ttl = _cache_billing_mode(api_kwargs)
    return (
        ledger.start_call(
            context=context,
            model_ref=model_ref,
            request_sha256=request_hash,
            request_input_token_upper_bound=input_upper,
            request_output_token_upper_bound=output_upper,
            request_cost_upper_bound_basis=upper_bound_basis,
            cache_read_mode=cache_mode,
            cache_write_ttl=cache_ttl,
        ),
        request_hash,
    )


def send_chat_completion(
    client: Any,
    *,
    ledger: RunCostLedger | None = None,
    context: ModelCallContext | None = None,
    **api_kwargs: Any,
) -> MeteredChatResponse:
    """Send one sync request. Retry/compatibility decisions remain with callers."""

    timeout = current_attempt_timeout(context.stage if context is not None else "")
    # This is an SDK transport option, never part of the provider payload/hash.
    if timeout is not None:
        client = client.with_options(timeout=timeout, max_retries=0)
    handle, _ = _begin(ledger=ledger, context=context, api_kwargs=api_kwargs)
    try:
        response = client.chat.completions.create(**api_kwargs)
    except BaseException as exc:
        original_error = exc
        if isinstance(exc, APITimeoutError):
            converted = ModelAttemptTimeout(
                "Provider SDK timeout; provider usage is unknown"
            )
            converted.__cause__ = exc
            exc = converted
        terminal_progress.transport_detail(exc)
        if ledger is not None and handle is not None:
            ledger.finish_call(
                handle,
                response_received=False,
                error=exc,
                completion_status="provider_exception",
            )
        if exc is not original_error:
            raise exc from original_error
        raise
    stream = bool(api_kwargs.get("stream", False))
    if ledger is not None and handle is not None and not stream:
        ledger.finish_call(
            handle,
            response_received=True,
            usage=getattr(response, "usage", None),
        )
    return MeteredChatResponse(
        response,
        ledger=ledger,
        handle=handle,
        stream=stream,
        async_stream=False,
    )


async def async_send_chat_completion(
    client: Any,
    *,
    ledger: RunCostLedger | None = None,
    context: ModelCallContext | None = None,
    **api_kwargs: Any,
) -> MeteredChatResponse:
    """Send one async request. Retry/compatibility decisions remain with callers."""

    timeout = current_attempt_timeout(context.stage if context is not None else "")
    handle, _ = _begin(ledger=ledger, context=context, api_kwargs=api_kwargs)
    deadline = None if timeout is None else time.monotonic() + timeout
    try:
        if timeout is None:
            response = await client.chat.completions.create(**api_kwargs)
        else:
            try:
                response = await asyncio.wait_for(
                    client.chat.completions.create(**api_kwargs), timeout=timeout,
                )
            except asyncio.TimeoutError as exc:
                raise ModelAttemptTimeout(
                    f"Model attempt exceeded {timeout:.3f}s; provider usage is unknown"
                ) from exc
    except BaseException as exc:
        original_error = exc
        if isinstance(exc, APITimeoutError):
            converted = ModelAttemptTimeout(
                "Provider SDK timeout; provider usage is unknown"
            )
            converted.__cause__ = exc
            exc = converted
        terminal_progress.transport_detail(exc)
        if ledger is not None and handle is not None:
            ledger.finish_call(
                handle,
                response_received=False,
                error=exc,
                completion_status="provider_exception",
            )
        if exc is not original_error:
            raise exc from original_error
        raise
    stream = bool(api_kwargs.get("stream", False))
    if ledger is not None and handle is not None and not stream:
        ledger.finish_call(
            handle,
            response_received=True,
            usage=getattr(response, "usage", None),
        )
    return MeteredChatResponse(
        response,
        ledger=ledger,
        handle=handle,
        stream=stream,
        async_stream=True,
        deadline_monotonic=deadline,
    )


__all__ = [
    "AsyncModelTransportPort",
    "MODEL_TRANSPORT_PROTOCOL",
    "PRODUCTION_MODEL_TRANSPORT_CREDENTIAL_ENV",
    "PRODUCTION_MODEL_TRANSPORT_PROVIDER",
    "PRODUCTION_MODEL_TRANSPORT_TIMEOUT_SECONDS",
    "MeteredChatResponse",
    "ModelTransportBundle",
    "ModelTransportCapabilityError",
    "ModelTransportError",
    "ProviderEndpointIdentity",
    "SyncModelTransportPort",
    "async_send_chat_completion",
    "classify_transport_exception",
    "create_model_transport_bundle",
    "create_production_model_transport_bundle",
    "legacy_sync_transport_from_client",
    "model_request_sha256",
    "production_model_endpoint_identity",
    "require_async_model_transport",
    "require_sync_model_transport",
    "send_chat_completion",
]
