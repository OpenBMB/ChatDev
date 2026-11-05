"""Control-plane model chain selection for S-GAR.

This module gates Planner/Router/Evaluator model choices using the factual
model_health.json report. It intentionally does not select task execution
resources from the resource pool.
"""

from __future__ import annotations

import json
import os
import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .executors import _retryable_transport_exception
from .pipeline_control import canonical_sha256


DEFAULT_SYSTEM_MODEL_CHAIN = [
    "gpt-5.6-sol",
]

FAILOVER_FAILURE_TYPES = {
    "provider_connection_error",
    "provider_stream_error",
    "provider_rate_limit",
    "provider_server_error",
    "provider_authorization_error",
    "provider_model_unavailable",
    "model_unavailable",
    "schema_exhausted",
    "json_parse_exhausted",
    "empty_response_exhausted",
    "planner_response_schema_invalid",
    "planner_wire_schema_invalid",
    "planner_semantic_ir_invalid",
}


@dataclass
class ControlModelSelector:
    """Health-gated control-plane model chain."""

    configured_chain: List[str]
    available_models: List[str]
    skipped_models: List[Dict[str, Any]] = field(default_factory=list)
    enable_failover: bool = False
    health_gate: str = "require_ok"
    health_path: str = ""
    health_loaded: bool = False

    @classmethod
    def from_settings(
        cls,
        llm_settings: Dict[str, Any],
        *,
        project_root: str,
    ) -> "ControlModelSelector":
        default_model = str(llm_settings.get("model") or DEFAULT_SYSTEM_MODEL_CHAIN[0])
        raw_chain = llm_settings.get("system_model_chain")
        if raw_chain is None:
            raw_chain = [default_model]
        elif isinstance(raw_chain, str):
            raw_chain = [raw_chain]
        configured_chain = _dedupe_model_ids(raw_chain) or [default_model]

        enable_failover = bool(llm_settings.get("enable_control_model_failover", False))
        if not enable_failover:
            configured_chain = [configured_chain[0]]

        health_gate = str(llm_settings.get("control_model_health_gate") or "require_ok")
        health_path = llm_settings.get("model_health_path")
        if not health_path:
            health_path = os.path.join(project_root, "sgar_mvp", "config", "model_health.json")
        elif not os.path.isabs(str(health_path)):
            health_path = os.path.join(project_root, str(health_path))

        health_models, health_loaded = _load_health_models(str(health_path))
        available: List[str] = []
        skipped: List[Dict[str, Any]] = []
        for model_id in configured_chain:
            record = health_models.get(model_id)
            ok, reason = _health_record_allows(model_id, record, health_loaded, health_gate)
            if ok:
                available.append(model_id)
            else:
                skipped.append(
                    {
                        "model_id": model_id,
                        "reason": reason,
                        "health_status": record.get("status") if isinstance(record, dict) else None,
                        "text_ok": record.get("text_ok") if isinstance(record, dict) else None,
                    }
                )

        return cls(
            configured_chain=configured_chain,
            available_models=available,
            skipped_models=skipped,
            enable_failover=enable_failover,
            health_gate=health_gate,
            health_path=str(health_path),
            health_loaded=health_loaded,
        )

    def primary_model(self, fallback: Optional[str] = None) -> str:
        if self.available_models:
            return self.available_models[0]
        if fallback:
            return str(fallback)
        return (
            self.configured_chain[0]
            if self.configured_chain
            else DEFAULT_SYSTEM_MODEL_CHAIN[0]
        )

    def execution_chain(self, fallback: Optional[str] = None) -> List[str]:
        if self.available_models:
            return list(self.available_models)
        return [self.primary_model(fallback)]

    def report_payload(self) -> Dict[str, Any]:
        return {
            "configured_system_model_chain": list(self.configured_chain),
            "health_filtered_system_model_chain": list(self.available_models),
            "skipped_control_models": list(self.skipped_models),
            "enable_control_model_failover": self.enable_failover,
            "control_model_health_gate": self.health_gate,
            "model_health_path": self.health_path,
            "model_health_loaded": self.health_loaded,
        }

    def public_projection(self, *, project_root: str) -> Dict[str, Any]:
        """Return a host-free control-plane identity for formal records."""

        health_path = os.path.abspath(self.health_path) if self.health_path else ""
        root = os.path.abspath(project_root)
        locator = ""
        if health_path:
            try:
                relative = os.path.relpath(health_path, root).replace("\\", "/")
                locator = (
                    relative
                    if relative != ".." and not relative.startswith("../")
                    else "external-health-report"
                )
            except ValueError:
                locator = "external-health-report"
        health_sha256 = ""
        if health_path and os.path.isfile(health_path):
            with open(health_path, "rb") as handle:
                health_sha256 = hashlib.sha256(handle.read()).hexdigest()
        return {
            "configured_system_model_chain": list(self.configured_chain),
            "health_filtered_system_model_chain": list(self.available_models),
            "skipped_control_models": list(self.skipped_models),
            "enable_control_model_failover": self.enable_failover,
            "control_model_health_gate": self.health_gate,
            "model_health_locator": locator,
            "model_health_sha256": health_sha256,
            "model_health_loaded": self.health_loaded,
        }


def classify_control_model_exception(exc: Exception) -> Tuple[str, str]:
    """Classify failures that may justify switching control-plane models."""
    explicit_failure_code = getattr(exc, "failure_code", None)
    explicit_responsibility = getattr(exc, "responsibility", None)
    if isinstance(explicit_failure_code, str) and explicit_failure_code:
        if explicit_responsibility == "infrastructure":
            failure_type = (
                explicit_failure_code
                if explicit_failure_code in FAILOVER_FAILURE_TYPES
                else "provider_connection_error"
            )
        elif explicit_failure_code in {
            "planner_response_schema_invalid",
            "planner_contract_conflict",
        }:
            failure_type = explicit_failure_code
        else:
            failure_type = explicit_failure_code
        diagnostic = {
            "failure_code": explicit_failure_code,
            "exception_type": type(exc).__name__,
            "message_sha256": canonical_sha256(
                {
                    "exception_type": type(exc).__name__,
                    "failure_code": explicit_failure_code,
                }
            ),
        }
        return failure_type, json.dumps(diagnostic, sort_keys=True, separators=(",", ":"))
    cause = getattr(exc, "__cause__", None)
    target = cause if isinstance(cause, Exception) else exc
    _retryable, failure_type = _retryable_transport_exception(target)
    message = f"{type(target).__name__}: {target}"
    lowered = f"{failure_type} {message} {exc}".lower()
    if failure_type in FAILOVER_FAILURE_TYPES:
        classified = failure_type
    elif "schema_exhausted" in lowered:
        classified = "schema_exhausted"
    elif "json_parse_exhausted" in lowered or "json output failed" in lowered:
        classified = "json_parse_exhausted"
    elif "empty response" in lowered:
        classified = "empty_response_exhausted"
    else:
        classified = failure_type
    diagnostic = {
        "failure_code": classified,
        "exception_type": type(target).__name__,
        "message_sha256": canonical_sha256(
            {
                "exception_type": type(target).__name__,
                "message": str(target),
            }
        ),
    }
    return classified, json.dumps(diagnostic, sort_keys=True, separators=(",", ":"))


def is_control_model_failover_failure(failure_type: str) -> bool:
    return failure_type in FAILOVER_FAILURE_TYPES


def _dedupe_model_ids(raw_chain: Sequence[Any]) -> List[str]:
    result: List[str] = []
    seen: set[str] = set()
    for item in raw_chain:
        model_id = str(item or "").strip()
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        result.append(model_id)
    return result


def _load_health_models(path: str) -> Tuple[Dict[str, Dict[str, Any]], bool]:
    if not path or not os.path.exists(path):
        return {}, False
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            payload = json.load(f)
    except Exception:
        return {}, False
    models: Dict[str, Dict[str, Any]] = {}
    for item in payload.get("models", []):
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("model_id") or "").strip()
        if model_id:
            models[model_id] = item
    return models, True


def _health_record_allows(
    model_id: str,
    record: Optional[Dict[str, Any]],
    health_loaded: bool,
    health_gate: str,
) -> Tuple[bool, str]:
    if str(health_gate or "").lower() not in {"require_ok", "strict"}:
        return True, "health_gate_disabled"
    if not health_loaded:
        return False, "health_file_missing"
    if not isinstance(record, dict):
        return False, "health_missing"
    status = str(record.get("status") or "").lower()
    text_ok = record.get("text_ok")
    if status != "ok":
        return False, status or "status_not_ok"
    if text_ok is False:
        return False, "text_not_ok"
    return True, "ok"
