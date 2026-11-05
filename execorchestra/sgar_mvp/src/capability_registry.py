"""Runtime model capability registry for S-GAR.

The registry records observed provider/model behavior without hardcoding
vendor-specific exclusion lists. Executors consult it to adapt request
parameters, while health checks can write factual probe results that the
runtime reads opportunistically.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_GATE_PATH = os.path.join(PROJECT_ROOT, "sgar_mvp", "config", "model_health.json")


@dataclass
class ModelCapabilityState:
    """Observed runtime capabilities for one model id."""

    text_ok: Optional[bool] = None
    streaming_ok: Optional[bool] = None
    json_mode_ok: Optional[bool] = None
    structured_outputs_ok: Optional[bool] = None
    temperature_ok: Optional[bool] = None
    reasoning_effort_low_ok: Optional[bool] = None
    required_tool_choice_ok: Optional[bool] = None
    named_tool_choice_ok: Optional[bool] = None
    last_error_type: Optional[str] = None
    last_error_message: Optional[str] = None
    updated_at: Optional[str] = None
    capability_evidence: Dict[str, str] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CapabilityRegistry:
    """In-memory model capability registry with optional health-gate bootstrap."""

    def __init__(self, health_gate_path: str = DEFAULT_GATE_PATH) -> None:
        self.health_gate_path = health_gate_path
        self._states: Dict[str, ModelCapabilityState] = {}
        self.load_health_gate(health_gate_path)

    def load_health_gate(self, path: Optional[str] = None) -> None:
        """Load factual probe results if a health-gate file exists."""
        gate_path = path or self.health_gate_path
        if not gate_path or not os.path.exists(gate_path):
            return
        try:
            with open(gate_path, "r", encoding="utf-8-sig") as f:
                payload = json.load(f)
        except Exception:
            return

        for item in payload.get("models", []):
            if not isinstance(item, dict):
                continue
            model_id = item.get("model_id")
            if not model_id:
                continue
            state = self._states.setdefault(str(model_id), ModelCapabilityState())
            status = str(item.get("status") or "").lower()
            if status == "ok":
                state.text_ok = True
            elif status == "unavailable":
                state.text_ok = False
                state.last_error_type = "model_unavailable"

            capabilities = item.get("capabilities")
            if isinstance(capabilities, dict):
                for key in (
                    "text_ok",
                    "streaming_ok",
                    "json_mode_ok",
                    "structured_outputs_ok",
                    "temperature_ok",
                    "required_tool_choice_ok",
                    "named_tool_choice_ok",
                ):
                    if key in capabilities and capabilities[key] is not None:
                        setattr(state, key, bool(capabilities[key]))

            evidence = item.get("capability_evidence")
            if isinstance(evidence, dict):
                state.capability_evidence = {
                    str(key): str(value.get("status") or "not_checked")
                    for key, value in evidence.items()
                    if isinstance(value, dict)
                }
                json_status = state.capability_evidence.get("json_mode")
                strict_status = state.capability_evidence.get(
                    "generic_strict_schema"
                )
                if json_status == "live_verified":
                    state.json_mode_ok = True
                elif json_status == "unsupported":
                    state.json_mode_ok = False
                if strict_status == "live_verified":
                    state.structured_outputs_ok = True
                elif strict_status == "unsupported":
                    state.structured_outputs_ok = False

            for key in ("text_ok", "streaming_ok", "json_mode_ok", "structured_outputs_ok", "temperature_ok", "reasoning_effort_low_ok", "required_tool_choice_ok", "named_tool_choice_ok"):
                if key in item and item[key] is not None:
                    setattr(state, key, bool(item[key]))

            state.last_error_type = item.get("error_code") or item.get("error_type") or state.last_error_type
            state.last_error_message = item.get("message") or state.last_error_message
            state.updated_at = item.get("checked_at") or payload.get("generated_at") or _utc_now()

    def get(self, model_id: str) -> ModelCapabilityState:
        return self._states.setdefault(str(model_id), ModelCapabilityState())

    def allows(self, model_id: str, capability: str) -> bool:
        """Return False only when a capability is known to be unsupported."""
        value = getattr(self.get(model_id), capability, None)
        return value is not False

    def explicitly_allows(self, model_id: str, capability: str) -> bool:
        """Authorize an optional request field only after positive evidence."""

        return getattr(self.get(model_id), capability, None) is True

    def record_success(self, model_id: str, capability: str) -> None:
        state = self.get(model_id)
        setattr(state, capability, True)
        state.updated_at = _utc_now()

    def record_failure(
        self,
        model_id: str,
        capability: str,
        error_type: str,
        message: str = "",
    ) -> None:
        state = self.get(model_id)
        setattr(state, capability, False)
        state.last_error_type = error_type
        state.last_error_message = message[:500]
        state.updated_at = _utc_now()

    def record_error(self, model_id: str, error_type: str, message: str = "") -> None:
        state = self.get(model_id)
        state.last_error_type = error_type
        state.last_error_message = message[:500]
        state.updated_at = _utc_now()

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        return {model_id: asdict(state) for model_id, state in self._states.items()}


GLOBAL_CAPABILITY_REGISTRY = CapabilityRegistry()
