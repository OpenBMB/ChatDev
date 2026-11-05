"""Perform fresh, low-cost RC1 liveness and representative capability probes."""

from __future__ import annotations

import argparse
import base64
import io
import math
import struct
import wave
import zlib
import concurrent.futures
import copy
import secrets
import subprocess
import tempfile
import hashlib
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Literal

import certifi
from openai import OpenAI
from pydantic import BaseModel, ConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SGAR_ROOT = PROJECT_ROOT / "sgar_mvp"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sgar_mvp.src.direct_network import direct_sync_http_client

from sgar_mvp.src.capability_registry import GLOBAL_CAPABILITY_REGISTRY
from sgar_mvp.src.atomic_io import temporary_sibling_path
from sgar_mvp.src.llm_compat import create_chat_completion_with_compat
from sgar_mvp.src.model_response_contracts import (
    OutputFormatRequirement,
    ModelResponseContractError,
    build_exact_schema_probe_request,
    strict_json_loads,
    classify_capability_probe_exception,
    structured_response_format,
    validate_structured_response_content,
    validate_json_schema_instance,
)
from sgar_mvp.src.model_transport import (
    ProviderEndpointIdentity,
    SyncModelTransportPort,
    production_model_endpoint_identity,
    create_production_model_transport_bundle,
    model_request_sha256,
)
from sgar_mvp.src.pipeline_control import canonical_sha256
from sgar_mvp.src.retrieval_runtime import load_applied_model_ready_state
from sgar_mvp.src.model_accounting import (
    ModelPricingCatalog, ModelCostPolicy, RunCostLedger, CanonicalTokenUsage,
    calculate_actual_model_cost_usd,
)


DEFAULT_CATALOG = PROJECT_ROOT / "Pool" / "resources" / "json" / "models.json"
DEFAULT_CONFIG = SGAR_ROOT / "config.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / ".codex-provider-health" / "runs"
DEFAULT_READY_STATE = SGAR_ROOT / "runtime_state" / "model_ready_state.json"
READY_STATE_PROTOCOL = "sgar-model-ready-state-v1"
READY_STATE_SCHEMA_VERSION = 6
DEFAULT_TRANSIENT_RETRIES = 3
STRUCTURED_OUTPUT_CAPABILITIES = frozenset(
    {"generic_strict_schema", "json_mode"}
)
TRANSIENT_MARKERS = (
    "timeout",
    "timed out",
    "connection error",
    "connection reset",
    "server disconnected",
    "temporarily unavailable",
    "rate limit",
    "rate_limit",
    "429",
    "502",
    "503",
    "504",
)
MODEL_MISSING_MARKERS = (
    "model_not_found",
    "model not found",
    "no available channel",
    "no available model",
    "does not exist",
    "invalid model",
    "unknown model",
)
UNSUPPORTED_MARKERS = (
    "unsupported",
    "does not support",
    "not supported",
)
def _vision_probe_png() -> str:
    # Synthetic RGB image; 224x224 also respects providers' minimum dimensions.
    # No local or user image data is sent.
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (struct.pack("!I", len(data)) + kind + data
                + struct.pack("!I", zlib.crc32(kind + data) & 0xFFFFFFFF))

    pixels = (b"\x00" + b"\xff\x00\x00" * 224) * 224
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack("!2I5B", 224, 224, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b""))
    return base64.b64encode(png).decode("ascii")


VISION_PROBE_PNG = _vision_probe_png()


def _audio_probe_wav() -> str:
    sample_rate = 16000
    frame_count = sample_rate // 2
    frames = bytearray()
    for index in range(frame_count):
        sample = int(12000 * math.sin(2 * math.pi * 440 * index / sample_rate))
        frames.extend(struct.pack("<h", sample))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate)
        stream.writeframes(bytes(frames))
    return base64.b64encode(buffer.getvalue()).decode("ascii")


AUDIO_PROBE_WAV = _audio_probe_wav()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_env_value(*names: str) -> str:
    values: dict[str, str] = {}
    env_file = PROJECT_ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    for name in names:
        value = os.environ.get(name, "").strip() or values.get(name, "")
        if value:
            return value
    return ""


def model_info(manifest: dict[str, Any]) -> dict[str, Any]:
    model = (manifest.get("type_specific") or {}).get("model") or {}
    execution = manifest.get("execution") or {}
    supports = model.get("supports") if isinstance(model.get("supports"), dict) else {}
    return {
        "resource_id": str(manifest["resource_id"]),
        "model_id": str(model.get("model_id") or execution.get("model_id") or ""),
        "provider": str(model.get("provider") or "unknown"),
        "family": str(model.get("family") or "unknown"),
        "catalog_status": str(manifest.get("status") or "active").lower(),
        "supports": {str(key): bool(value) for key, value in supports.items()},
        "input_modalities": tuple(
            sorted(
                str(item).strip().lower()
                for item in model.get("input_modalities") or ()
                if str(item).strip()
            )
        ),
    }


def classify_exception(exc: Exception) -> tuple[str, str, str]:
    message = str(exc)
    structured = classify_capability_probe_exception(exc)
    if structured.reason_code != "capability_probe_inconclusive_failure":
        return structured.outcome, structured.reason_code, message[:500]
    lowered = message.lower()
    body = getattr(exc, "body", None)
    code = ""
    if isinstance(body, dict):
        error = body.get("error", body)
        if isinstance(error, dict):
            code = str(error.get("code") or "")
            message = str(error.get("message") or message)
            lowered = message.lower()
    if code.lower() in {"model_not_found", "model_not_exist", "model_not_available"} or any(
        marker in lowered for marker in MODEL_MISSING_MARKERS
    ):
        return "unavailable", code or "model_not_found", message[:500]
    if any(marker in lowered for marker in ("unauthorized", "invalid api key", "401", "403")):
        return "blocked", code or "auth_error", message[:500]
    if any(marker in lowered for marker in TRANSIENT_MARKERS):
        return "transient_failure", code or "provider_or_transport_failure", message[:500]
    if any(marker in lowered for marker in UNSUPPORTED_MARKERS):
        return "unsupported", code or "capability_unsupported", message[:500]
    return "probe_failed", code or "capability_probe_inconclusive_failure", message[:500]


def provider_failure_details(exc: Exception) -> dict[str, Any]:
    """Keep routing diagnostics without provider messages, payloads or secrets."""
    body = getattr(exc, "body", None)
    error = body.get("error", body) if isinstance(body, dict) else {}
    if not isinstance(error, dict):
        error = {}
    result: dict[str, Any] = {"exception_type": type(exc).__name__}
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        result["http_status"] = status
    for field in ("code", "type", "param"):
        value = error.get(field) or getattr(exc, field, None)
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.\[\]-]{1,80}", value):
            result[f"provider_{field}"] = value
    return result


def run_with_infrastructure_retries(
    operation: Callable[[], Any],
    *,
    retries: int,
    delay_seconds: float,
) -> tuple[Any | None, dict[str, Any] | None, int]:
    max_attempts = max(1, int(retries) + 1)
    for attempt in range(1, max_attempts + 1):
        try:
            return operation(), None, attempt
        except Exception as exc:
            status, code, message = classify_exception(exc)
            failure = {"status": status, "error_code": code, "message": message,
                       "provider_error": provider_failure_details(exc)}
            if status != "transient_failure" or attempt >= max_attempts:
                return None, failure, attempt
            if delay_seconds > 0:
                time.sleep(delay_seconds)
    raise AssertionError("unreachable")


def text_probe(
    client: SyncModelTransportPort,
    model_id: str,
    max_tokens: int,
) -> str:
    response = create_chat_completion_with_compat(
        client,
        registry=GLOBAL_CAPABILITY_REGISTRY,
        model=model_id,
        messages=[{"role": "user", "content": "Return exactly OK."}],
        temperature=0,
        max_tokens=max(16, max_tokens),
    )
    content = str(response.choices[0].message.content or "").strip()
    if not content:
        raise RuntimeError("empty model response")
    return content


def generic_strict_schema_requirement() -> OutputFormatRequirement:
    return OutputFormatRequirement(
        artifact_type="json",
        structured=True,
        strict_required=True,
        json_schema={
            "type": "object",
            "properties": {"ok": {"type": "boolean", "const": True}},
            "required": ["ok"],
            "additionalProperties": False,
        },
        schema_source="health.generic_strict_schema",
    )


def json_mode_requirement() -> OutputFormatRequirement:
    return OutputFormatRequirement(
        artifact_type="json",
        structured=True,
        strict_required=True,
        json_schema={
            "type": "object",
            "properties": {"probe": {"type": "string", "const": "ok"}},
            "required": ["probe"],
            "additionalProperties": False,
        },
        schema_source="health.json_mode",
    )


def capability_contract_metadata(capability: str) -> dict[str, Any]:
    if capability == "generic_strict_schema":
        requirement = generic_strict_schema_requirement()
        projection = requirement.portable_wire_schema
        if projection is None:
            raise RuntimeError("health_strict_probe_wire_schema_missing")
        return {
            "response_mode": "native_strict_schema",
            "probe_protocol": "sgar-health-json-v2",
            "requires_full_json_response": True,
            "schema_sha256": requirement.schema_sha256,
            "wire_schema_protocol": projection.protocol,
            "wire_schema_sha256": projection.wire_schema_sha256,
        }
    if capability == "json_mode":
        requirement = json_mode_requirement()
        projection = requirement.portable_wire_schema
        if projection is None:
            raise RuntimeError("health_json_probe_wire_schema_missing")
        return {
            "response_mode": "json_object_local_validator",
            "probe_protocol": "sgar-health-json-v2",
            "requires_full_json_response": True,
            "schema_sha256": requirement.schema_sha256,
            "wire_schema_protocol": projection.protocol,
            "wire_schema_sha256": projection.wire_schema_sha256,
        }
    if capability == "tool_result_continuation":
        return {
            "probe_protocol": "sgar-health-continuation-v2",
            "response_validation": "exact_token_after_outer_whitespace",
        }
    if capability == "vision":
        return {
            "probe_protocol": "sgar-vision-color-v2",
            "image_sha256": hashlib.sha256(base64.b64decode(VISION_PROBE_PNG)).hexdigest(),
            "image_width": 224,
            "image_height": 224,
            "response_validation": "red_color_word",
        }
    if capability == "audio_input":
        return {
            "probe_protocol": "sgar-audio-tone-v1",
            "audio_sha256": hashlib.sha256(
                base64.b64decode(AUDIO_PROBE_WAV)
            ).hexdigest(),
            "audio_format": "wav",
            "sample_rate_hz": 16000,
            "duration_ms": 500,
            "response_validation": "tone_token",
        }
    return {}


def validate_probe_json_content(
    content: str, *, requirement: OutputFormatRequirement, mode: str,
) -> Any:
    # Capability evidence uses the same full-JSON boundary as ExactCapabilityProbeService.
    # Runtime ingress normalization may extract an unambiguous JSON object, but
    # extracting a snippet does not prove that a provider's output mode worked.
    try:
        strict_json_loads(content)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        raise ModelResponseContractError("capability_probe_invalid_json_response") from exc
    return validate_structured_response_content(content, requirement=requirement, mode=mode)


def capability_probe(client: SyncModelTransportPort, model_id: str, capability: str, max_tokens: int) -> Any:
    if capability == "json_mode":
        requirement = json_mode_requirement()
        response = client.send(
            model=model_id,
            messages=[
                {
                    "role": "user",
                    "content": 'Return only this JSON object: {"probe":"ok"}.',
                }
            ],
            max_tokens=max(16, max_tokens),
            response_format=structured_response_format(
                requirement,
                mode="json_object_local_validator",
            ),
        )
        return validate_probe_json_content(
            str(response.choices[0].message.content or ""),
            requirement=requirement,
            mode="json_object_local_validator",
        )
    if capability == "generic_strict_schema":
        requirement = generic_strict_schema_requirement()
        request = build_exact_schema_probe_request(
            model_id=model_id, requirement=requirement, mode="native_strict_schema",
        )
        # Keep the health token budget and its existing omission of temperature;
        # the formal probe builder supplies the unambiguous synthetic JSON prompt.
        request.pop("temperature", None)
        request["max_tokens"] = max(256, max_tokens)
        response = client.send(**request)
        value = validate_probe_json_content(
            str(response.choices[0].message.content or ""),
            requirement=requirement,
            mode="native_strict_schema",
        )
        return value
    if capability in {"tool_calling", "tool_result_continuation"}:
        return _tool_exchange(client.send, model_id, max(32, max_tokens),
                              continuation=capability == "tool_result_continuation",
                              normalize_outer_whitespace=True)

    if capability == "vision":
        response = client.send(
            model=model_id,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Reply with one English color word for this image."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{VISION_PROBE_PNG}"
                            },
                        },
                    ],
                }
            ],
            max_tokens=max(16, max_tokens),
        )
        content = str(response.choices[0].message.content or "").strip()
        if not content:
            raise RuntimeError("vision probe returned empty content")
        if content.casefold().strip(" .!\r\n\t") != "red":
            raise RuntimeError("vision_probe_color_mismatch")
        return content
    if capability == "audio_input":
        response = client.send(
            model=model_id,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Reply exactly TONE if the attached audio contains "
                                "a steady audible tone; otherwise reply exactly SILENCE."
                            ),
                        },
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": AUDIO_PROBE_WAV,
                                "format": "wav",
                            },
                        },
                    ],
                }
            ],
            max_tokens=max(16, max_tokens),
        )
        content = str(response.choices[0].message.content or "").strip()
        if content.casefold().strip(" .!\r\n\t") != "tone":
            raise RuntimeError("audio_probe_tone_mismatch")
        return content
    raise ValueError(f"Unknown capability probe: {capability}")


def representative_assignments(models: list[dict[str, Any]]) -> dict[str, set[str]]:
    assignments = {item["resource_id"]: set() for item in models}
    for capability in (
        "json_mode",
        "tool_calling",
        "tool_result_continuation",
        "vision",
        "audio_input",
    ):
        groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for item in models:
            declared_capability = (
                "tool_calling"
                if capability == "tool_result_continuation"
                else capability
            )
            declared = (
                "audio" in item["input_modalities"]
                if capability == "audio_input"
                else item["supports"].get(declared_capability)
            )
            if declared:
                groups.setdefault((item["provider"], item["family"]), []).append(item)
        for candidates in groups.values():
            chosen = sorted(candidates, key=lambda item: item["model_id"])[0]
            assignments[chosen["resource_id"]].add(capability)
    return assignments


def all_capability_assignments(models: list[dict[str, Any]]) -> dict[str, set[str]]:
    assignments: dict[str, set[str]] = {}
    for item in models:
        probes = {"json_mode", "generic_strict_schema"}
        if item["supports"].get("tool_calling"):
            probes.add("tool_calling")
            probes.add("tool_result_continuation")
        if item["supports"].get("vision"):
            probes.add("vision")
        if "audio" in item["input_modalities"]:
            probes.add("audio_input")
        assignments[item["resource_id"]] = probes
    return assignments


def derive_ready_state(
    *,
    text_status: str,
    text_ok: bool,
    capability_evidence: dict[str, Any],
    capability_assignments: set[str],
) -> dict[str, Any]:
    """Derive the endpoint-ready state used by formal runtime selection.

    A Model must answer the basic text probe and demonstrate SGAR's formal
    single-attempt native strict-schema mode.  JSON-object mode remains useful
    capability evidence, but it is not a fallback under the Golden execution
    policy.  Capabilities explicitly declared by the manifest and assigned for
    live verification (currently tool calling and vision) must also pass.
    """

    reasons: list[str] = []
    observed: dict[str, str] = {}
    for capability in sorted(capability_assignments):
        raw = capability_evidence.get(capability)
        status = str(raw.get("status") or "missing") if isinstance(raw, dict) else "missing"
        observed[capability] = status

    if not text_ok or text_status not in {"ok", "ready", "live_verified"}:
        reasons.append(f"text_probe:{text_status or 'unknown'}")

    structured_assigned = STRUCTURED_OUTPUT_CAPABILITIES.intersection(
        capability_assignments
    )
    structured_live = sorted(
        capability
        for capability in structured_assigned
        if observed.get(capability) == "live_verified"
    )
    strict_status = observed.get("generic_strict_schema")
    if structured_assigned != STRUCTURED_OUTPUT_CAPABILITIES:
        reasons.append("structured_output_probe_set_incomplete")
    elif strict_status != "live_verified":
        reasons.append("native_strict_schema_not_live_verified")

    for capability in sorted(
        capability_assignments - STRUCTURED_OUTPUT_CAPABILITIES
    ):
        if observed.get(capability) != "live_verified":
            reasons.append(f"declared_capability_not_live_verified:{capability}")

    failed_statuses = {
        status for status in observed.values() if status != "live_verified"
    }
    if not reasons:
        readiness_status = "ready"
    elif text_status == "transient_failure" or "transient_failure" in failed_statuses:
        readiness_status = "transient_failure"
    elif text_status == "unavailable" or (
        strict_status == "unsupported"
    ):
        readiness_status = "unavailable"
    else:
        readiness_status = "blocked"

    return {
        "protocol": READY_STATE_PROTOCOL,
        "status": readiness_status,
        "reason_codes": reasons,
        "structured_output_modes_live_verified": structured_live,
        "capability_statuses": observed,
    }


def check_one(
    info: dict[str, Any],
    *,
    api_key: str,
    credential_environment_variable: str,
    base_url: str,
    timeout_seconds: float,
    max_tokens: int,
    retries: int,
    retry_delay_seconds: float,
    capability_assignments: set[str],
    transport: SyncModelTransportPort | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    checked_at = utc_now()
    if transport is None:
        sdk_client = OpenAI(
            http_client=direct_sync_http_client(),
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds,
            max_retries=0,
        )
        client = SyncModelTransportPort.from_sdk_client(
            client=sdk_client,
            endpoint_identity=ProviderEndpointIdentity.create(
                provider="openai_compatible",
                base_url=base_url,
                credential_environment_variable=credential_environment_variable,
                timeout_seconds=timeout_seconds,
            ),
        )
    else:
        client = transport
    _, failure, attempts = run_with_infrastructure_retries(
        lambda: text_probe(client, info["model_id"], max_tokens),
        retries=retries,
        delay_seconds=retry_delay_seconds,
    )
    if failure:
        result = {
            **info,
            "status": failure["status"],
            "text_ok": False,
            "checked_at": checked_at,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "attempt_count": attempts,
            "error_code": failure["error_code"],
            "provider_error": failure["provider_error"],
            "message_sha256": hashlib.sha256(
                str(failure["message"]).encode("utf-8")
            ).hexdigest(),
            "capability_evidence": {
                key: {"status": "provider_declared" if value else "not_declared"}
                for key, value in info["supports"].items()
            },
        }
        result["ready_state"] = derive_ready_state(
            text_status=str(result["status"]),
            text_ok=False,
            capability_evidence=dict(result["capability_evidence"]),
            capability_assignments=capability_assignments,
        )
        return result

    capability_evidence = {
        key: {"status": "provider_declared" if value else "not_declared"}
        for key, value in info["supports"].items()
    }
    for capability in sorted(capability_assignments):
        cap_started = time.perf_counter()
        contract_metadata = capability_contract_metadata(capability)
        value, failure, capability_attempts = run_with_infrastructure_retries(
            lambda: capability_probe(
                client,
                info["model_id"],
                capability,
                max_tokens,
            ),
            retries=retries,
            delay_seconds=retry_delay_seconds,
        )
        if failure is None:
            capability_evidence[capability] = {
                "status": "live_verified",
                "attempt_count": capability_attempts,
                "latency_ms": round((time.perf_counter() - cap_started) * 1000, 2),
                "evidence": value,
                **contract_metadata,
            }
        else:
            capability_evidence[capability] = {
                "status": failure["status"],
                "attempt_count": capability_attempts,
                "error_code": failure["error_code"],
                "provider_error": failure["provider_error"],
                "message_sha256": hashlib.sha256(
                    str(failure["message"]).encode("utf-8")
                ).hexdigest(),
                "latency_ms": round((time.perf_counter() - cap_started) * 1000, 2),
                **contract_metadata,
            }
    # Reasoning remains declaration-only by design; answer quality is not used
    # as a subjective capability probe.
    result = {
        **info,
        "status": "ok",
        "text_ok": True,
        "checked_at": checked_at,
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "attempt_count": attempts,
        "error_code": None,
        "message": "ok",
        "capability_evidence": capability_evidence,
    }
    result["ready_state"] = derive_ready_state(
        text_status="ok",
        text_ok=True,
        capability_evidence=capability_evidence,
        capability_assignments=capability_assignments,
    )
    return result



# Supplemental evidence uses the existing v6 state and monetary ledger.
CONTINUATION = "tool_result_continuation"
CONTINUATION_REPORT = "sgar-continuation-supplement-v1"
PROBE_SCHEMA = {
    "type": "object", "properties": {"value": {"type": "string"}},
    "required": ["value"], "additionalProperties": False,
}
PROBE_TOOL = {"type": "function", "function": {
    "name": "get_probe_value", "description": "Return the supplied probe value.",
    "parameters": PROBE_SCHEMA,
}}
PROBE_MESSAGE = {
    "role": "user",
    "content": "Call get_probe_value with value RC1. After its Tool result, "
               "reply with exactly the continuation_token from that result.",
}


class CapabilityUpdateError(RuntimeError):
    def __init__(self, code: str, *, state_changed: bool = False):
        super().__init__(code)
        self.code = code
        self.state_changed = state_changed


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CapabilityUpdateError(code)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _strict_json(raw: str | bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            _require(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    def invalid(_value: str) -> Any:
        raise CapabilityUpdateError("nonfinite_json")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


class _StrictReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class EvidenceFile(_StrictReport):
    path: str
    sha256: str


class ProbeRound(_StrictReport):
    round: int
    operation_id: str
    request_sha256: str
    request: EvidenceFile
    response: EvidenceFile | None = None
    provider_attempt_id: str | None = None
    validation: Literal["pending", "passed"] = "pending"


class ContinuationReport(_StrictReport):
    kind: Literal["sgar-continuation-supplement-v1"] = CONTINUATION_REPORT
    capability: Literal["tool_result_continuation"] = CONTINUATION
    checked_at: str
    source: dict[str, str]
    binding: dict[str, str]
    probe_policy: dict[str, Any]
    probe_policy_sha256: str
    rounds: list[ProbeRound]
    files: dict[str, EvidenceFile]
    outcome: Literal["success", "failed", "already_verified"]
    applicable: bool
    first_failure: str | None
    secondary_failures: list[str]
    report_sha256: str


def _source_identity(root: Path) -> dict[str, str]:
    def git(*args: str) -> bytes:
        return subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), *args],
            check=True, capture_output=True,
        ).stdout
    _require(not git("status", "--porcelain", "--untracked-files=no").strip(),
             "capability_source_not_clean")
    # The running script must be the byte-identical script in this source identity.
    _require(git("show", "HEAD:./sgar_mvp/scripts/check_model_health.py")
             == Path(__file__).read_bytes(), "capability_source_script_mismatch")
    return {"head": git("rev-parse", "HEAD").decode().strip(),
            "tree": git("rev-parse", "HEAD^{tree}").decode().strip()}


def _state_path() -> Path:
    return PROJECT_ROOT / "sgar_mvp/runtime_state/model_ready_state.json"


def _file_sha(path: Path) -> str | None:
    return _sha(path.read_bytes()) if path.exists() else None


def _file_reference(root: Path, name: str) -> EvidenceFile:
    return EvidenceFile(path=name, sha256=_sha((root / name).read_bytes()))


def _read_evidence(root: Path, ref: EvidenceFile) -> bytes:
    path = (root / ref.path).resolve()
    _require(not Path(ref.path).is_absolute()
             and path.is_relative_to(root.resolve()), "evidence_path_escape")
    raw = path.read_bytes()
    _require(_sha(raw) == ref.sha256, "evidence_file_sha_mismatch")
    return raw


def _binding(args: argparse.Namespace, resource_id: str) -> tuple[
    dict[str, Any], dict[str, str], ModelPricingCatalog, bool
]:
    raw = _state_path().read_bytes()
    _require(_sha(raw) == args.expected_ready_state_file_sha256, "base_state_changed")
    state = _strict_json(raw)
    # This is the original loader; no local equivalent or bypass is used.
    applied = load_applied_model_ready_state(
        PROJECT_ROOT, expected_endpoint_identity_sha256=args.expected_endpoint_identity_sha256,
    )
    _require(_state_path().read_bytes() == raw, "base_state_changed")
    _require(state["schema_version"] == 6, "base_state_version_not_v6")
    _require(isinstance(state.get("base_url"), str)
             and production_model_endpoint_identity(base_url=state["base_url"]).identity_sha256
             == applied.endpoint_identity_sha256, "base_endpoint_inconsistent")
    catalog_raw = args.catalog.read_bytes()
    _require(catalog_raw == (PROJECT_ROOT / "Pool/resources/json/models.json").read_bytes(),
             "targeted_full_catalog_required")
    manifests = _strict_json(catalog_raw)
    selected = [m for m in manifests if m.get("resource_id") == resource_id]
    records = [m for m in state["models"] if m.get("resource_id") == resource_id]
    ready = [m for m in applied.models if m.resource_id == resource_id]
    _require(len(selected) == len(records) == len(ready) == 1, "target_not_uniquely_ready")
    manifest, record, loaded = selected[0], records[0], ready[0]
    info = model_info(manifest)
    _require(manifest.get("resource_type") == "Model"
             and info["catalog_status"] == "active", "target_catalog_inactive")
    _require(info["model_id"] == record.get("model_id") == loaded.model_id,
             "target_model_identity_mismatch")
    _require(manifest["execution"].get("model_id") == info["model_id"],
             "target_model_identity_mismatch")
    _require(sum(m.get("model_id") == loaded.model_id for m in state["models"]) == 1,
             "target_duplicate_api_identity")
    statuses = record["ready_state"].get("capability_statuses", {})
    evidence = record.get("capability_evidence", {})
    _require(record.get("text_ok") is True and record.get("status") in {"ok", "ready", "live_verified"},
             "target_text_evidence_inconsistent")
    for capability in ("generic_strict_schema", "tool_calling"):
        _require(statuses.get(capability) == "live_verified"
                 and evidence.get(capability, {}).get("status") == "live_verified"
                 and capability in loaded.capabilities_live_verified,
                 "target_prerequisite_unverified")
    _require("generic_strict_schema" in loaded.structured_output_modes_live_verified,
             "target_strict_mode_inconsistent")
    values = [statuses.get(CONTINUATION), evidence.get(CONTINUATION, {}).get("status")]
    verified = values == ["live_verified", "live_verified"]
    if not verified:
        _require(all(v in (None, "unknown") for v in values),
                 "continuation_not_missing_or_inconsistent")
    pricing = ModelPricingCatalog.from_manifest_file(args.catalog)
    price = pricing.resolve(resource_id=resource_id, api_model_id=loaded.model_id)
    _require(pricing.resource_pool_sha256 == _sha(catalog_raw), "catalog_changed")
    binding = {
        "resource_id": resource_id, "api_model_id": price.api_model_id,
        "endpoint_identity_sha256": applied.endpoint_identity_sha256,
        "base_file_sha256": _sha(raw), "base_health_sha256": applied.health_sha256,
        "target_record_sha256": canonical_sha256(record),
        "catalog_file_sha256": _sha(catalog_raw),
        "target_manifest_sha256": canonical_sha256(manifest),
        "pricing_catalog_sha256": pricing.pricing_catalog_sha256,
        "system_cost_policy_file_sha256": _sha(
            (PROJECT_ROOT / "sgar_mvp/config/model_cost_policy.json").read_bytes()),
    }
    return state, binding, pricing, verified


def _probe_policy(max_tokens: int, limit: str) -> tuple[dict[str, Any], ModelCostPolicy]:
    amount = Decimal(limit).normalize()
    _require(amount.is_finite() and Decimal("0") < amount <= Decimal("0.50"),
             "targeted_cost_limit_invalid")
    _require(type(max_tokens) is int and 1 <= max_tokens <= 256, "targeted_max_tokens_invalid")
    cost = ModelCostPolicy(mode="stop_after_limit", warning_usd=amount, limit_usd=amount)
    policy = {
        "capability": CONTINUATION, "max_tokens": max_tokens, "send_ceiling": 2,
        "sdk_retries": 0, "transport_retries": 0, "fallbacks": 0,
        "schema_sha256": canonical_sha256(PROBE_SCHEMA), "cost": cost.snapshot(),
    }
    return policy, cost


def _first_action(response: Any) -> dict[str, Any]:
    choices = response.choices
    _require(len(choices) == 1 and choices[0].index == 0, "probe_choice_invalid")
    choice = choices[0]
    _require(choice.finish_reason == "tool_calls", "probe_action_finish_invalid")
    message = choice.message
    _require(not getattr(message, "refusal", None), "probe_refusal")
    calls = message.tool_calls or []
    _require(len(calls) == 1, "probe_action_count_invalid")
    call = calls[0]
    _require(call.type == "function" and isinstance(call.id, str) and bool(call.id.strip()),
             "probe_call_identity_invalid")
    _require(call.function.name == "get_probe_value", "probe_function_invalid")
    arguments = _strict_json(call.function.arguments)
    _require(validate_json_schema_instance(arguments, PROBE_SCHEMA)[0]
             and arguments == {"value": "RC1"}, "probe_arguments_invalid")
    return {"role": "assistant", "content": None, "tool_calls": [{
        "id": call.id, "type": "function",
        "function": {"name": call.function.name, "arguments": call.function.arguments},
    }]}


def _final_token(
    response: Any, token: str, *, normalize_outer_whitespace: bool = False,
) -> dict[str, Any]:
    choices = response.choices
    _require(len(choices) == 1 and choices[0].index == 0, "probe_choice_invalid")
    choice = choices[0]
    message = choice.message
    _require(choice.finish_reason == "stop", "probe_final_finish_invalid")
    _require(not getattr(message, "refusal", None), "probe_refusal")
    _require(not message.tool_calls, "probe_final_has_tool_calls")
    content = message.content
    if normalize_outer_whitespace and isinstance(content, str):
        content = content.strip()
    _require(content == token, "probe_challenge_mismatch")
    return {"role": "assistant", "content": token, "tool_calls": []}


def _tool_exchange(
    send: Callable[..., Any], model_id: str, max_tokens: int, *,
    continuation: bool, observe: Callable[[int, dict[str, Any]], None] | None = None,
    normalize_outer_whitespace: bool = False,
) -> dict[str, Any]:
    first = send(model=model_id, messages=[copy.deepcopy(PROBE_MESSAGE)],
                 max_tokens=max_tokens, tools=[copy.deepcopy(PROBE_TOOL)], tool_choice="auto")
    action = _first_action(first)
    projection = {"index": 0, "finish_reason": "tool_calls", "refusal": False, "message": action}
    if observe:
        observe(1, projection)
    if not continuation:
        return {"tool_call_count": 1}
    token = secrets.token_hex(24)
    tool_result = {"role": "tool", "tool_call_id": action["tool_calls"][0]["id"],
                   "content": json.dumps({"value": "RC1", "continuation_token": token})}
    final = send(model=model_id, messages=[copy.deepcopy(PROBE_MESSAGE), action, tool_result],
                 max_tokens=max_tokens, tools=[copy.deepcopy(PROBE_TOOL)])
    final_message = _final_token(
        final, token, normalize_outer_whitespace=normalize_outer_whitespace,
    )
    if observe:
        observe(2, {"index": 0, "finish_reason": "stop", "refusal": False,
                    "message": final_message})
    return {"tool_call_id_bound": True,
            "continuation_content_sha256": _sha(token.encode())}


def _ledger_complete(summary: dict[str, Any], count: int) -> None:
    _require(summary["provider_reported_cost_complete"] is True
             and summary["started_call_count"] == count
             and summary["finished_call_count"] == count
             and summary["pending_call_count"] == 0
             and summary["blocked_call_count"] == 0,
             "probe_accounting_incomplete")


def _targeted_transport(base_url: str) -> SyncModelTransportPort:
    _require(os.environ.get("SGAR_EXTERNAL_MODEL_NETWORK_DISABLED") != "1",
             "external_model_network_disabled")
    key = load_env_value("LLM_API_KEY")
    _require(bool(key), "production_credential_missing")
    return create_production_model_transport_bundle(api_key=key, base_url=base_url).sync


def probe_missing_continuation(
    args: argparse.Namespace, *, transport: SyncModelTransportPort | None = None,
) -> ContinuationReport:
    source = _source_identity(PROJECT_ROOT)
    _state, binding, pricing, already = _binding(args, args.model_resource_id[0])
    endpoint = production_model_endpoint_identity(base_url=args.base_url)
    _require(endpoint.identity_sha256 == args.expected_endpoint_identity_sha256,
             "probe_endpoint_identity_mismatch")
    policy, cost = _probe_policy(args.max_tokens, args.cost_stop_usd)
    out = args.capability_output_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    rounds: list[ProbeRound] = []
    files: dict[str, EvidenceFile] = {}
    failure: str | None = None
    secondary: list[str] = []
    ledger: RunCostLedger | None = None
    outcome = "already_verified" if already else "failed"
    try:
        ledger = RunCostLedger(catalog=pricing, policy=cost, output_dir=out)
        if not already:
            port = transport if transport is not None else _targeted_transport(args.base_url)
            _require(port.endpoint_identity == endpoint, "transport_endpoint_mismatch")

            def send(**request: Any) -> Any:
                _require(len(rounds) < 2, "probe_send_ceiling")
                _ledger_complete(ledger.summary(), len(rounds))
                context = ledger.new_operation(
                    stage="retrieval_format_probe", model_resource_id=binding["resource_id"],
                    selected_resource_id=binding["resource_id"],
                    request_policy_sha256=canonical_sha256(policy),
                )
                number = len(rounds) + 1
                name = f"round{number}.request.json"
                write_json(out / name, request)
                item = ProbeRound(round=number, operation_id=context.operation_id,
                                  request_sha256=model_request_sha256(request),
                                  request=_file_reference(out, name))
                rounds.append(item)
                response = port.send(ledger=ledger, context=context, **request)
                reference = response.accounting_reference
                _require(reference is not None and reference["operation_id"] == context.operation_id,
                         "probe_accounting_reference_missing")
                rounds[-1] = item.model_copy(update={
                    "provider_attempt_id": reference["provider_attempt_id"],
                })
                _ledger_complete(ledger.summary(), number)
                return response

            def observe(number: int, projection: dict[str, Any]) -> None:
                name = f"round{number}.response.json"
                write_json(out / name, projection)
                rounds[number - 1] = rounds[number - 1].model_copy(update={
                    "response": _file_reference(out, name), "validation": "passed",
                })

            _tool_exchange(send, binding["api_model_id"], args.max_tokens,
                           continuation=True, observe=observe)
            outcome = "success"
        _require(_source_identity(PROJECT_ROOT) == source, "probe_source_changed")
        _new_state, current, _prices, _verified = _binding(args, binding["resource_id"])
        _require(current == binding, "probe_binding_changed")
    except BaseException as exc:
        failure = exc.code if isinstance(exc, CapabilityUpdateError) else type(exc).__name__
        outcome = "failed"
    finally:
        if ledger is not None:
            try:
                summary = ledger.close()
                if outcome == "success":
                    _ledger_complete(summary, 2)
            except BaseException as exc:
                code = exc.code if isinstance(exc, CapabilityUpdateError) else type(exc).__name__
                if failure is None:
                    failure = code
                else:
                    secondary.append(code)
                outcome = "failed"
        for name in ("model_calls.jsonl", "cost_summary.json", "model_pricing_snapshot.json"):
            if (out / name).is_file():
                files[name] = _file_reference(out, name)
    payload = dict(
        checked_at=utc_now(), source=source, binding=binding, probe_policy=policy,
        probe_policy_sha256=canonical_sha256(policy), rounds=rounds, files=files,
        outcome=outcome, applicable=outcome == "success", first_failure=failure,
        secondary_failures=secondary, report_sha256="",
    )
    report = ContinuationReport(**payload)
    if report.applicable:
        try:
            _verify_probe_evidence(report, out, pricing)
        except BaseException as exc:
            report = report.model_copy(update={
                "outcome": "failed", "applicable": False,
                "first_failure": exc.code if isinstance(exc, CapabilityUpdateError) else type(exc).__name__,
            })
    unsigned = report.model_dump(mode="json", exclude={"report_sha256"})
    report = report.model_copy(update={"report_sha256": canonical_sha256(unsigned)})
    write_json(out / "continuation-report.json", report.model_dump(mode="json"))
    return report


def _verify_probe_evidence(
    report: ContinuationReport, directory: Path, pricing: ModelPricingCatalog,
) -> None:
    _require(report.outcome == "success" and report.applicable
             and report.first_failure is None and not report.secondary_failures,
             "report_not_applicable")
    policy, cost_policy = _probe_policy(
        report.probe_policy["max_tokens"], report.probe_policy["cost"]["limit_usd"],
    )
    _require(report.probe_policy == policy
             and report.probe_policy_sha256 == canonical_sha256(policy), "probe_policy_mismatch")
    _require(len(report.rounds) == 2 and [r.round for r in report.rounds] == [1, 2],
             "report_round_count_invalid")
    requests, projections = [], []
    for item in report.rounds:
        _require(item.validation == "passed" and item.response is not None,
                 "round_not_validated")
        request = _strict_json(_read_evidence(directory, item.request))
        _require(model_request_sha256(request) == item.request_sha256, "request_hash_mismatch")
        requests.append(request)
        projections.append(_strict_json(_read_evidence(directory, item.response)))
    first, second = requests
    action, final = projections
    expected_first = {
        "model": report.binding["api_model_id"], "messages": [PROBE_MESSAGE],
        "max_tokens": policy["max_tokens"], "tools": [PROBE_TOOL], "tool_choice": "auto",
    }
    _require(first == expected_first, "first_request_protocol_invalid")
    _require(set(action) == {"index", "finish_reason", "refusal", "message"}
             and action["index"] == 0 and action["finish_reason"] == "tool_calls"
             and action["refusal"] is False, "first_projection_invalid")
    message = action["message"]
    _require(set(message) == {"role", "content", "tool_calls"}
             and message["role"] == "assistant" and message["content"] is None
             and len(message["tool_calls"]) == 1, "first_projection_invalid")
    call = message["tool_calls"][0]
    _require(set(call) == {"id", "type", "function"} and call["type"] == "function"
             and isinstance(call["id"], str) and bool(call["id"].strip())
             and set(call["function"]) == {"name", "arguments"}
             and call["function"]["name"] == "get_probe_value", "first_projection_invalid")
    arguments = _strict_json(call["function"]["arguments"])
    _require(validate_json_schema_instance(arguments, PROBE_SCHEMA)[0]
             and arguments == {"value": "RC1"}, "first_projection_arguments_invalid")
    _require(len(second.get("messages", [])) == 3, "continuation_messages_invalid")
    tool_result = second["messages"][2]
    _require(set(tool_result) == {"role", "tool_call_id", "content"}
             and tool_result["role"] == "tool" and tool_result["tool_call_id"] == call["id"],
             "tool_result_binding_invalid")
    value = _strict_json(tool_result["content"])
    _require(set(value) == {"value", "continuation_token"} and value["value"] == "RC1",
             "tool_result_value_invalid")
    token = value["continuation_token"]
    _require(isinstance(token, str) and len(token) == 48
             and all(c in "0123456789abcdef" for c in token)
             and token not in json.dumps(first), "challenge_invalid")
    _require(second == {"model": first["model"],
                         "messages": [PROBE_MESSAGE, message, tool_result],
                         "max_tokens": first["max_tokens"], "tools": first["tools"]},
             "second_request_protocol_invalid")
    _require(final == {"index": 0, "finish_reason": "stop", "refusal": False,
                       "message": {"role": "assistant", "content": token, "tool_calls": []}},
             "final_projection_invalid")
    _require(set(report.files) == {
        "model_calls.jsonl", "cost_summary.json", "model_pricing_snapshot.json",
    }, "accounting_files_missing")
    events = [_strict_json(line) for line in
              _read_evidence(directory, report.files["model_calls.jsonl"]).splitlines() if line]
    summary = _strict_json(_read_evidence(directory, report.files["cost_summary.json"]))
    snapshot = _strict_json(_read_evidence(directory, report.files["model_pricing_snapshot.json"]))
    _require(snapshot == pricing.snapshot(), "pricing_snapshot_mismatch")
    _ledger_complete(summary, 2)
    _require(summary["resolved_cost_policy"] == cost_policy.snapshot()
             and summary["pricing_catalog_sha256"] == pricing.pricing_catalog_sha256
             and summary["resource_pool_sha256"] == report.binding["catalog_file_sha256"],
             "summary_identity_mismatch")
    starts = [e for e in events if e["event_type"] == "model_call_started"]
    finishes = [e for e in events if e["event_type"] == "model_call_finished"]
    _require(len(starts) == len(finishes) == 2
             and len({r.operation_id for r in report.rounds}) == 2, "ledger_attempt_count_invalid")
    _require([e["event_type"] for e in events if e["event_type"] in {
        "model_call_started", "model_call_finished",
    }] == ["model_call_started", "model_call_finished"] * 2, "ledger_event_order_invalid")
    total = Decimal("0")
    token_totals = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}
    price = pricing.resolve(resource_id=report.binding["resource_id"],
                            api_model_id=report.binding["api_model_id"])
    for number, item in enumerate(report.rounds):
        started, finished = starts[number], finishes[number]
        for event in (started, finished):
            _require(
                event["operation_id"] == item.operation_id
                and event["provider_attempt_id"] == item.provider_attempt_id
                and event["provider_attempt_id"] == item.operation_id + ":1"
                and event["provider_attempt"] == 1
                and event["run_id"] == summary["run_id"]
                and event["stage"] == "retrieval_format_probe"
                and event["model_resource_id"] == report.binding["resource_id"]
                and event["api_model_id"] == report.binding["api_model_id"]
                and event["selected_resource_id"] == report.binding["resource_id"]
                and event["request_sha256"] == item.request_sha256
                and event["pricing_catalog_sha256"] == pricing.pricing_catalog_sha256
                and event["policy_sha256"] == cost_policy.policy_sha256,
                "ledger_round_identity_mismatch",
            )
        _require(started["request_policy_sha256"] == report.probe_policy_sha256
                 and finished["started_event_id"] == started["event_id"]
                 and finished["response_received"] is True
                 and finished["usage_status"] == "provider_reported"
                 and finished["error_code"] is None, "ledger_terminal_invalid")
        usage = CanonicalTokenUsage.model_validate(finished["token_usage"])
        actual = calculate_actual_model_cost_usd(usage, price)
        _require(Decimal(finished["actual_model_cost_usd"]) == actual,
                 "ledger_cost_mismatch")
        total += actual
        for key in token_totals:
            token_totals[key] += getattr(usage, key)
        if number == 0:
            _require(total < cost_policy.limit_usd, "second_send_after_cost_limit")
    _require(Decimal(summary["observed_total_model_cost_usd"]) == total
             and summary["token_usage"] == token_totals, "ledger_summary_mismatch")


def _lock_path(destination: Path) -> Path:
    return destination.with_name(destination.name + ".writer.lock")


def _validate_candidate(raw: bytes, parent: Path, endpoint: str) -> None:
    # The original loader accepts only project_root. Use its original relative path.
    with tempfile.TemporaryDirectory(prefix=".cap-", dir=parent) as temporary:
        root = Path(temporary)
        path = root / "sgar_mvp/runtime_state/model_ready_state.json"
        path.parent.mkdir(parents=True)
        with path.open("xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        load_applied_model_ready_state(root, expected_endpoint_identity_sha256=endpoint)


def _write_ready_state(
    destination: Path, payload: dict[str, Any], *, expected_sha: str | None,
    before_replace: Callable[[], None] | None = None,
    after_replace: Callable[[], None] | None = None,
) -> None:
    """One cooperative writer lock and CAS for full and supplemental applies."""
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    lock = _lock_path(destination)
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise CapabilityUpdateError("ready_state_writer_conflict") from exc
    changed = False
    temporary: Path | None = None
    try:
        os.close(descriptor)
        _require(_file_sha(destination) == expected_sha, "ready_state_compare_and_swap_conflict")
        raw = (json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
        _validate_candidate(raw, destination.parent, payload["endpoint_identity_sha256"])
        temporary = temporary_sibling_path(destination)
        with temporary.open("xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        if before_replace:
            before_replace()
        _require(_file_sha(destination) == expected_sha, "ready_state_compare_and_swap_conflict")
        _require(temporary.read_bytes() == raw, "candidate_bytes_changed")
        os.replace(temporary, destination)
        changed = True
        if after_replace:
            after_replace()
        else:
            _validate_candidate(destination.read_bytes(), destination.parent,
                                payload["endpoint_identity_sha256"])
    except BaseException as exc:
        code = exc.code if isinstance(exc, CapabilityUpdateError) else type(exc).__name__
        raise CapabilityUpdateError(code, state_changed=changed) from exc
    finally:
        primary = sys.exc_info()[1]
        cleanup_failures = []
        for path in (temporary, lock):
            if path is not None:
                try:
                    path.unlink(missing_ok=True)
                except OSError as exc:
                    cleanup_failures.append(type(exc).__name__)
        if cleanup_failures:
            if isinstance(primary, CapabilityUpdateError):
                primary.cleanup_failures = cleanup_failures
            elif primary is None:
                raise CapabilityUpdateError("writer_cleanup_failed", state_changed=changed)


def apply_continuation_report(args: argparse.Namespace) -> dict[str, Any]:
    raw_report = args.apply_continuation_report.read_bytes()
    _require(_sha(raw_report) == args.expected_report_file_sha256, "report_file_sha_mismatch")
    report = ContinuationReport.model_validate(_strict_json(raw_report))
    _require(report.report_sha256 == canonical_sha256(
        report.model_dump(mode="json", exclude={"report_sha256"})), "report_canonical_sha_mismatch")
    _require(_source_identity(PROJECT_ROOT) == report.source, "report_source_mismatch")
    state, binding, pricing, already = _binding(args, report.binding["resource_id"])
    _require(binding == report.binding and not already, "report_base_binding_mismatch")
    _verify_probe_evidence(report, args.apply_continuation_report.parent, pricing)
    before = _state_path().read_bytes()
    _require(_sha(before) == binding["base_file_sha256"], "base_state_changed")
    candidate = copy.deepcopy(state)
    target = next(m for m in candidate["models"] if m["resource_id"] == binding["resource_id"])
    supplement = {
        "status": "live_verified", "checked_at": report.checked_at, "attempt_count": 2,
        "evidence": {
            "report_file_sha256": _sha(raw_report), "report_sha256": report.report_sha256,
            "endpoint_identity_sha256": binding["endpoint_identity_sha256"],
            "model_id": binding["api_model_id"],
            "operation_ids": [r.operation_id for r in report.rounds],
            "provider_attempt_ids": [r.provider_attempt_id for r in report.rounds],
            "accounting_files": {k: v.model_dump() for k, v in report.files.items()},
        },
    }
    target["capability_evidence"][CONTINUATION] = supplement
    target["ready_state"]["capability_statuses"][CONTINUATION] = "live_verified"
    candidate.setdefault("capability_supplements", []).append({
        "before_health_sha256": binding["base_health_sha256"],
        "report_file_sha256": _sha(raw_report), "resource_id": binding["resource_id"],
        "capability": CONTINUATION, "applied_at": utc_now(),
    })
    candidate.pop("health_sha256")
    candidate["health_sha256"] = canonical_sha256(candidate)
    # An independent delta comparison preserves every other field and list order.
    restored = copy.deepcopy(candidate)
    restored["models"] = copy.deepcopy(state["models"])
    restored["health_sha256"] = state["health_sha256"]
    if "capability_supplements" in state:
        restored["capability_supplements"] = state["capability_supplements"]
    else:
        restored.pop("capability_supplements")
    _require(restored == state, "non_target_state_changed")
    output = args.output.resolve()
    _require(output.name != "before-ready-state.json", "receipt_backup_collision")
    output.parent.mkdir(parents=True, exist_ok=False)
    with (output.parent / "before-ready-state.json").open("xb") as handle:
        handle.write(before)
        handle.flush()
        os.fsync(handle.fileno())
    receipt: dict[str, Any] = {
        "kind": "sgar-continuation-apply-receipt-v1", "before_file_sha256": _sha(before),
        "before_health_sha256": state["health_sha256"], "report_file_sha256": _sha(raw_report),
        "target_resource_id": binding["resource_id"], "capability": CONTINUATION,
        "state_changed": False, "outcome": "failed", "loader": "not_checked",
        "changed_fields": ["target.capability_evidence.tool_result_continuation",
                           "target.ready_state.capability_statuses.tool_result_continuation",
                           "capability_supplements", "health_sha256"],
    }

    def precheck() -> None:
        _require(_source_identity(PROJECT_ROOT) == report.source, "apply_source_changed")
        _current_state, current, _pricing, _already = _binding(args, binding["resource_id"])
        _require(current == binding, "apply_binding_changed")

    def postcheck() -> None:
        loaded = load_applied_model_ready_state(
            PROJECT_ROOT, expected_endpoint_identity_sha256=binding["endpoint_identity_sha256"],
        )
        _require(_strict_json(_state_path().read_bytes()) == candidate, "applied_state_changed")
        model = next(m for m in loaded.models if m.resource_id == binding["resource_id"])
        _require(CONTINUATION in model.capabilities_live_verified, "applied_capability_missing")
        receipt["loader"] = "PASS"

    try:
        _write_ready_state(_state_path(), candidate, expected_sha=binding["base_file_sha256"],
                           before_replace=precheck, after_replace=postcheck)
    except BaseException as exc:
        changed = getattr(exc, "state_changed", False)
        receipt.update(state_changed=changed, outcome="failed",
                       first_failure=exc.code if isinstance(exc, CapabilityUpdateError) else type(exc).__name__,
                       after_file_sha256=_file_sha(_state_path()),
                       secondary_failures=getattr(exc, "cleanup_failures", []))
        try:
            write_json(output, receipt)
        except BaseException as secondary:
            raise CapabilityUpdateError(
                "apply_receipt_persistence_failed:" + receipt["first_failure"],
                state_changed=changed,
            ) from secondary
        raise CapabilityUpdateError(receipt["first_failure"], state_changed=changed) from exc
    receipt.update(state_changed=True, outcome="success",
                   after_file_sha256=_file_sha(_state_path()),
                   after_health_sha256=candidate["health_sha256"], applied_at=utc_now())
    try:
        write_json(output, receipt)
    except BaseException as exc:
        # Replacement already happened. No rollback, retry or false not-applied result.
        raise CapabilityUpdateError("apply_receipt_persistence_failed", state_changed=True) from exc

    return receipt


def _targeted_options(args: argparse.Namespace, explicit: set[str]) -> None:
    forbidden = {"--capability-probes", "--apply-ready-state", "--write-gate", "--dry-run",
                 "--config", "--timeout-sec", "--retry-delay-sec", "--freshness-ttl-sec",
                 "--fail-on-nonready"}
    _require(not explicit.intersection(forbidden), "targeted_legacy_options_forbidden")
    for value in (args.expected_ready_state_file_sha256, args.expected_endpoint_identity_sha256):
        _require(isinstance(value, str) and len(value) == 64
                 and all(c in "0123456789abcdef" for c in value), "expected_digest_required")
    if args.probe_missing_continuation:
        _require(len(args.model_resource_id or []) == 1, "targeted_exactly_one_model_required")
        _require(args.api_key_env == "LLM_API_KEY" and bool(args.base_url), "targeted_endpoint_required")
        _require({"--retries", "--concurrency", "--max-tokens", "--base-url"}.issubset(explicit)
                 and args.retries == 0 and args.concurrency == 1, "targeted_request_policy_invalid")
        _require(args.capability_output_dir is not None and args.cost_stop_usd is not None,
                 "targeted_output_and_budget_required")
        _require(args.output is None and args.expected_report_file_sha256 is None,
                 "targeted_apply_options_forbidden")
        _probe_policy(args.max_tokens, args.cost_stop_usd)
    else:
        _require(args.output is not None and args.expected_report_file_sha256 is not None,
                 "targeted_apply_output_digest_required")
        _require(not explicit.intersection({
            "--base-url", "--api-key-env", "--model-resource-id", "--max-tokens", "--retries",
            "--concurrency", "--cost-stop-usd", "--capability-output-dir",
        }), "targeted_probe_options_forbidden")



def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = temporary_sibling_path(path)
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--base-url")
    parser.add_argument("--api-key-env", default="LLM_API_KEY")
    parser.add_argument("--model-resource-id", action="append")
    parser.add_argument("--output", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--probe-missing-continuation", action="store_true",
                      help="LIVE NETWORK: two metered sends; report only. Requires explicit authorization.")
    mode.add_argument("--apply-continuation-report", type=Path,
                      help="OFFLINE: validate a report and update runtime state. Requires explicit authorization.")
    parser.add_argument("--expected-ready-state-file-sha256")
    parser.add_argument("--expected-endpoint-identity-sha256")
    parser.add_argument("--expected-report-file-sha256")
    parser.add_argument("--capability-output-dir", type=Path,
                        help="Probe-only fresh directory; must not exist.")
    parser.add_argument("--cost-stop-usd",
                        help="Probe-only observed-cost stop threshold, >0 and <=0.50 USD.")
    mode.add_argument(
        "--apply-ready-state",
        action="store_true",
        help=(
            "Atomically replace the runtime Model ready-state after a complete "
            "all-capability scan."
        ),
    )
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Run probes and write only the report; do not change runtime ready-state.",
    )
    parser.add_argument(
        "--write-gate",
        type=Path,
        help=(
            "Override the ready-state destination; valid only with "
            "--apply-ready-state."
        ),
    )
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--timeout-sec", type=float, default=60.0)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_TRANSIENT_RETRIES,
        help=(
            "Retries per logical health probe after transient failures only; "
            "the default 3 means at most 4 total attempts."
        ),
    )
    parser.add_argument("--retry-delay-sec", type=float, default=1.0)
    parser.add_argument("--freshness-ttl-sec", type=float, default=3600.0)
    parser.add_argument(
        "--capability-probes",
        choices=("all", "representative", "none"),
        default="all",
    )
    parser.add_argument("--fail-on-nonready", action="store_true")
    args = parser.parse_args(argv)
    tokens = sys.argv[1:] if argv is None else argv
    explicit = {token.split("=", 1)[0] for token in tokens if token.startswith("--")}
    if args.probe_missing_continuation or args.apply_continuation_report:
        try:
            # Keep legacy argparse abbreviation behavior, but require exact option
            # names for the new modes so an abbreviated legacy flag cannot hide.
            known = {name for action in parser._actions for name in action.option_strings}
            _require(explicit.issubset(known), "targeted_abbreviated_options_forbidden")
            _targeted_options(args, explicit)
        except (CapabilityUpdateError, ValueError, ArithmeticError) as exc:
            parser.error(str(exc))
    elif explicit.intersection({
        "--expected-ready-state-file-sha256", "--expected-endpoint-identity-sha256",
        "--expected-report-file-sha256", "--capability-output-dir", "--cost-stop-usd",
    }):
        parser.error("targeted_mode_required")
    return args


def main(argv: list[str] | None = None, *, transport: SyncModelTransportPort | None = None) -> int:
    args = parse_args(argv)
    if args.probe_missing_continuation or args.apply_continuation_report:
        try:
            if args.probe_missing_continuation:
                report = probe_missing_continuation(args, transport=transport)
                print(json.dumps({"outcome": report.outcome, "applicable": report.applicable,
                                  "first_failure": report.first_failure}))
                return 0 if report.outcome in {"success", "already_verified"} else 2
            receipt = apply_continuation_report(args)
            print(json.dumps({"outcome": receipt["outcome"], "state_changed": True}))
            return 0
        except Exception as exc:
            print(json.dumps({
                "outcome": "failed",
                "first_failure": exc.code if isinstance(exc, CapabilityUpdateError) else type(exc).__name__,
                "state_changed": getattr(exc, "state_changed", False),
            }))
            return 2
    if args.retries < 0:
        raise SystemExit("health_probe_retries_must_be_nonnegative")
    if args.write_gate is not None and not args.apply_ready_state:
        raise SystemExit("write_gate_requires_apply_ready_state")
    if args.apply_ready_state:
        if args.model_resource_id:
            raise SystemExit("applied_ready_state_requires_full_catalog_scan")
        if args.capability_probes != "all":
            raise SystemExit("applied_ready_state_requires_all_capability_probes")
        if args.retries < DEFAULT_TRANSIENT_RETRIES:
            raise SystemExit(
                "applied_ready_state_requires_at_least_three_transient_retries"
            )
        if args.api_key_env != "LLM_API_KEY":
            raise SystemExit("applied_ready_state_requires_production_credential_identity")
    destination = args.write_gate or DEFAULT_READY_STATE
    baseline_sha = _file_sha(destination) if args.apply_ready_state else None
    os.environ["SSL_CERT_FILE"] = certifi.where()
    os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
    config = load_json(args.config)
    api_key = load_env_value(args.api_key_env, "LLM_API_KEY", "OPENAI_API_KEY")
    if not api_key:
        raise SystemExit(f"Missing API key: set {args.api_key_env}")
    base_url = (
        args.base_url
        or load_env_value("LLM_BASE_URL", "OPENAI_BASE_URL")
        or (config.get("llm_settings") or {}).get("base_url")
    )
    if not base_url:
        raise SystemExit("Missing model base URL")

    from sgar_mvp.src.model_selection import candidate_health_manifests
    manifests = candidate_health_manifests(load_json(args.catalog), root=PROJECT_ROOT)
    requested = set(args.model_resource_id or [])
    if requested - {item["resource_id"] for item in manifests}:
        raise SystemExit("health_probe_requested_model_not_candidate")
    all_models = [model_info(item) for item in manifests]
    active = [
        item
        for item in all_models
        if item["catalog_status"] not in {"unavailable", "inactive", "disabled"}
        and (not requested or item["resource_id"] in requested)
    ]
    if not active:
        raise SystemExit("No active Model resources selected")
    if args.capability_probes == "all":
        assignments = all_capability_assignments(active)
    elif args.capability_probes == "representative":
        assignments = representative_assignments(active)
    else:
        assignments = {item["resource_id"]: set() for item in active}
    print(f"[ModelHealth] text probes={len(active)} base_url={base_url}")
    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as executor:
        futures = {
            executor.submit(
                check_one,
                item,
                api_key=api_key,
                credential_environment_variable=args.api_key_env,
                base_url=base_url,
                timeout_seconds=args.timeout_sec,
                max_tokens=args.max_tokens,
                retries=args.retries,
                retry_delay_seconds=args.retry_delay_sec,
                capability_assignments=assignments[item["resource_id"]],
            ): item
            for item in active
        }
        for future in concurrent.futures.as_completed(futures):
            item = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                status, code, message = classify_exception(exc)
                result = {
                    **item,
                    "status": status,
                    "text_ok": False,
                    "checked_at": utc_now(),
                    "latency_ms": 0.0,
                    "attempt_count": 1,
                    "error_code": code,
                    "message_sha256": hashlib.sha256(
                        str(message).encode("utf-8")
                    ).hexdigest(),
                    "capability_evidence": {},
                }
                result["ready_state"] = derive_ready_state(
                    text_status=status,
                    text_ok=False,
                    capability_evidence={},
                    capability_assignments=assignments[item["resource_id"]],
                )
            results.append(result)
            print(
                f"[{result['ready_state']['status'].upper():17}] {result['resource_id']} -> "
                f"{result['model_id']} ({result['latency_ms']:.0f} ms)"
            )
    results.sort(key=lambda item: item["resource_id"])
    generated_at = utc_now()
    generated_at_epoch = time.time()
    endpoint_identity = production_model_endpoint_identity(base_url=base_url)
    unavailable_ids = [
        identifier
        for result in results
        if result["status"] == "unavailable"
        for identifier in (result["resource_id"], result["model_id"])
    ]
    ready_models = [
        item
        for item in results
        if (item.get("ready_state") or {}).get("status") == "ready"
    ]
    payload = {
        "schema_version": READY_STATE_SCHEMA_VERSION,
        "ready_state_protocol": READY_STATE_PROTOCOL,
        "generated_at": generated_at,
        "generated_at_epoch": generated_at_epoch,
        "expires_at_epoch": generated_at_epoch + max(0.0, args.freshness_ttl_sec),
        "endpoint_identity_sha256": endpoint_identity.identity_sha256,
        "base_url": base_url,
        "catalog": str(args.catalog),
        "candidate_catalog_sha256": canonical_sha256(manifests),
        "probe_policy": {
            "text_probe": "active configured resource candidates only",
            "infrastructure_retries": args.retries,
            "sdk_retries": 0,
            "timeout_seconds": float(args.timeout_sec),
            "max_tokens": args.max_tokens,
            "concurrency": args.concurrency,
            "retry_delay_seconds": args.retry_delay_sec,
            "vision_probe_protocol": "sgar-vision-color-v2",
            "audio_probe_protocol": "sgar-audio-tone-v1",
            "json_probe_protocol": "sgar-health-json-v2",
            "continuation_probe_protocol": "sgar-health-continuation-v2",
            "capability_probes": args.capability_probes,
            "reasoning_evidence": "provider_declared_only",
        },
        "summary": {
            "catalog_total": len(all_models),
            "probed": len(results),
            "ok": sum(item["status"] == "ok" for item in results),
            "unavailable": sum(item["status"] == "unavailable" for item in results),
            "blocked": sum(item["status"] == "blocked" for item in results),
            "transient_failure": sum(
                item["status"] == "transient_failure" for item in results
            ),
            "text_ok": sum(bool(item["text_ok"]) for item in results),
            "ready": len(ready_models),
            "not_ready": len(results) - len(ready_models),
            "by_ready_status": {
                status: sum(item["ready_state"]["status"] == status for item in results)
                for status in ("ready", "blocked", "unavailable", "transient_failure")
            },
        },
        "unavailable_model_ids": sorted(set(unavailable_ids)),
        "models": results,
    }
    payload["health_sha256"] = canonical_sha256(payload)
    output = args.output or DEFAULT_OUTPUT_DIR / f"model_health_{datetime.now():%Y%m%d_%H%M%S}.json"
    write_json(output, payload)
    latest = DEFAULT_OUTPUT_DIR / "model_health_latest.json"
    latest.parent.mkdir(parents=True, exist_ok=True)
    if output.resolve() != latest.resolve():
        shutil.copyfile(output, latest)
    if args.apply_ready_state:
        destination = args.write_gate or DEFAULT_READY_STATE
        _write_ready_state(destination, payload, expected_sha=baseline_sha)
        print(f"[ModelHealth] ready_state_applied={destination}")
        print(f"[ModelHealth] health_sha256={payload['health_sha256']}")
    else:
        print("[ModelHealth] ready_state_applied=false")
    print(f"[ModelHealth] report={output}")
    nonready = any(
        (item.get("ready_state") or {}).get("status") != "ready"
        for item in results
    )
    return 2 if args.fail_on_nonready and nonready else 0


if __name__ == "__main__":
    raise SystemExit(main())
