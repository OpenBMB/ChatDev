"""Hash-sealed audit facts for control-plane schema capability probes."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Literal, Mapping

from pydantic import Field, field_validator, model_validator

from .atomic_io import temporary_sibling_path
from .model_response_contracts import CapabilityProbeEvidence, OutputFormatRequirement
from .pipeline_control import FrozenContract, canonical_json_bytes, canonical_sha256
from .terminal_failure import TerminalFailureEnvelope


SYSTEM_ROLE_SCHEMA_PROBE_AUDIT_PROTOCOL_V2 = "sgar-system-role-schema-probes-v2"
SYSTEM_ROLE_SCHEMA_PROBE_AUDIT_PROTOCOL_V3 = "sgar-system-role-schema-probes-v3"
SYSTEM_ROLE_SCHEMA_PROBE_AUDIT_PROTOCOL_V4 = "sgar-system-role-schema-probes-v4"
SYSTEM_ROLE_SCHEMA_PROBE_AUDIT_PROTOCOL_V5 = "sgar-system-role-schema-probes-v5"
SYSTEM_ROLE_SCHEMA_PROBE_AUDIT_PROTOCOL = "sgar-system-role-schema-probes-v6"
SystemRoleProbeAttemptStatus = Literal["verified", "rejected", "aborted"]
SystemRoleProbeAuditStatus = Literal["in_progress", "verified", "terminated"]


def _validate_sha256(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
        raise ValueError(f"{field_name}_invalid")
    return normalized


def _accounting_projection(value: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    operation_id = str(value.get("operation_id") or "").strip()
    provider_attempt_id = str(value.get("provider_attempt_id") or "").strip()
    has_provider_attempt_ids = "provider_attempt_ids" in value
    provider_attempt_ids = tuple(
        str(item).strip()
        for item in value.get("provider_attempt_ids", ())
        if str(item).strip()
    )
    projected: dict[str, Any] = {}
    if operation_id:
        projected["operation_id"] = operation_id
    if provider_attempt_id:
        projected["provider_attempt_id"] = provider_attempt_id
    if has_provider_attempt_ids:
        projected["provider_attempt_ids"] = list(provider_attempt_ids)
    return projected or None


class SystemRoleProbeAttempt(FrozenContract):
    role: str = Field(min_length=1)
    attempt_index: int = Field(ge=1)
    resource_id: str
    model_id: str = Field(min_length=1)
    endpoint_identity_sha256: str
    requirement_sha256: str
    schema_sha256: str
    wire_schema_protocol: str | None = None
    wire_schema_sha256: str | None = None
    attempted_enforcement_modes: tuple[str, ...] = ()
    selected_enforcement_mode: str | None = None
    evidence_sha256: str | None = None
    status: SystemRoleProbeAttemptStatus
    reason_code: str = Field(min_length=1)
    accounting_reference: dict[str, Any] | None = None
    attempt_sha256: str = ""

    @field_validator(
        "endpoint_identity_sha256",
        "requirement_sha256",
        "schema_sha256",
        "wire_schema_sha256",
        "evidence_sha256",
    )
    @classmethod
    def _hashes(cls, value: str | None, info: Any) -> str | None:
        return _validate_sha256(value, field_name=info.field_name)

    @field_validator("accounting_reference", mode="before")
    @classmethod
    def _accounting_reference(cls, value: Any) -> dict[str, Any] | None:
        return _accounting_projection(value if isinstance(value, Mapping) else None)

    @model_validator(mode="after")
    def _seal(self) -> "SystemRoleProbeAttempt":
        projected = self.model_dump(mode="python", exclude={"attempt_sha256"})
        expected = canonical_sha256(projected)
        if self.attempt_sha256 and self.attempt_sha256 != expected:
            raise ValueError("system_role_probe_attempt_sha256_mismatch")
        object.__setattr__(self, "attempt_sha256", expected)
        return self


class SystemRoleProbeAudit(FrozenContract):
    protocol: Literal[
        SYSTEM_ROLE_SCHEMA_PROBE_AUDIT_PROTOCOL_V2,
        SYSTEM_ROLE_SCHEMA_PROBE_AUDIT_PROTOCOL_V3,
        SYSTEM_ROLE_SCHEMA_PROBE_AUDIT_PROTOCOL_V4,
        SYSTEM_ROLE_SCHEMA_PROBE_AUDIT_PROTOCOL_V5,
        SYSTEM_ROLE_SCHEMA_PROBE_AUDIT_PROTOCOL,
    ] = (
        SYSTEM_ROLE_SCHEMA_PROBE_AUDIT_PROTOCOL
    )
    run_id: str = Field(min_length=1)
    status: SystemRoleProbeAuditStatus
    attempts: tuple[SystemRoleProbeAttempt, ...] = ()
    selected_models: dict[str, dict[str, str]] = Field(default_factory=dict)
    authority_source: Literal["unbound", "release_receipt", "git_runtime"] = "unbound"
    applied_ready_state_sha256: str | None = None
    control_probe_receipt_sha256: str | None = None
    control_probe_result_sha256: str | None = None
    sealed_release_probe_receipt_sha256: str | None = None
    sealed_release_probe_result_sha256: str | None = None
    terminal_failure: TerminalFailureEnvelope | None = None
    audit_sha256: str = ""

    @model_validator(mode="after")
    def _validate_and_seal(self) -> "SystemRoleProbeAudit":
        for field_name in (
            "sealed_release_probe_receipt_sha256",
            "sealed_release_probe_result_sha256",
            "applied_ready_state_sha256",
            "control_probe_receipt_sha256",
            "control_probe_result_sha256",
        ):
            value = getattr(self, field_name)
            if value is not None:
                _validate_sha256(value, field_name=field_name)
        if (self.control_probe_receipt_sha256 is None) != (self.control_probe_result_sha256 is None):
            raise ValueError("git_control_probe_hash_pair_required")
        if self.control_probe_receipt_sha256 is not None and self.authority_source != "git_runtime":
            raise ValueError("git_control_probe_authority_mismatch")
        if self.status == "terminated" and self.terminal_failure is None:
            raise ValueError("terminated_system_role_probe_audit_requires_failure")
        if self.status != "terminated" and self.terminal_failure is not None:
            raise ValueError("nonterminal_system_role_probe_audit_has_failure")
        if (
            self.terminal_failure is not None
            and self.terminal_failure.run_id
            and self.terminal_failure.run_id != self.run_id
        ):
            raise ValueError("system_role_probe_audit_run_id_mismatch")
        projected = self.model_dump(mode="python", exclude={"audit_sha256"})
        expected = canonical_sha256(projected)
        accepted_hashes = {expected}
        if self.protocol != SYSTEM_ROLE_SCHEMA_PROBE_AUDIT_PROTOCOL:
            projected = {key: value for key, value in projected.items()
                         if key not in {"control_probe_receipt_sha256", "control_probe_result_sha256"}}
            if self.control_probe_receipt_sha256 is not None:
                raise ValueError("git_control_probe_requires_v6")
            accepted_hashes.add(canonical_sha256(projected))
        if self.protocol not in {SYSTEM_ROLE_SCHEMA_PROBE_AUDIT_PROTOCOL, SYSTEM_ROLE_SCHEMA_PROBE_AUDIT_PROTOCOL_V5}:
            accepted_hashes.add(
                canonical_sha256(
                    {
                        key: value
                        for key, value in projected.items()
                        if key
                        not in {"authority_source", "applied_ready_state_sha256"}
                    }
                )
            )
        if self.audit_sha256 and self.audit_sha256 not in accepted_hashes:
            raise ValueError("system_role_probe_audit_sha256_mismatch")
        if not self.audit_sha256:
            object.__setattr__(self, "audit_sha256", expected)
        return self


class SystemRoleProbeAuditStore:
    """Atomically persist every Probe attempt without prompt or response bodies."""

    def __init__(self, output_dir: str | Path, *, run_id: str) -> None:
        self.path = Path(output_dir).resolve() / "system_role_schema_probes.json"
        self.run_id = str(run_id)
        self._lock = threading.RLock()
        self._attempts: list[SystemRoleProbeAttempt] = []
        self._selected_models: dict[str, dict[str, str]] = {}
        self._status: SystemRoleProbeAuditStatus = "in_progress"
        self._terminal_failure: TerminalFailureEnvelope | None = None
        self._sealed_release_probe_receipt_sha256: str | None = None
        self._sealed_release_probe_result_sha256: str | None = None
        self._authority_source: Literal[
            "unbound", "release_receipt", "git_runtime"
        ] = "unbound"
        self._applied_ready_state_sha256: str | None = None
        self._control_probe_receipt_sha256: str | None = None
        self._control_probe_result_sha256: str | None = None
        self._write()

    @property
    def status(self) -> SystemRoleProbeAuditStatus:
        with self._lock:
            return self._status

    def _next_attempt_index(self, role: str) -> int:
        return 1 + sum(1 for item in self._attempts if item.role == role)

    def _snapshot(self) -> SystemRoleProbeAudit:
        return SystemRoleProbeAudit(
            run_id=self.run_id,
            status=self._status,
            attempts=tuple(self._attempts),
            selected_models=dict(self._selected_models),
            authority_source=self._authority_source,
            applied_ready_state_sha256=self._applied_ready_state_sha256,
            control_probe_receipt_sha256=self._control_probe_receipt_sha256,
            control_probe_result_sha256=self._control_probe_result_sha256,
            sealed_release_probe_receipt_sha256=(
                self._sealed_release_probe_receipt_sha256
            ),
            sealed_release_probe_result_sha256=(
                self._sealed_release_probe_result_sha256
            ),
            terminal_failure=self._terminal_failure,
        )

    def _write(self) -> SystemRoleProbeAudit:
        audit = self._snapshot()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = temporary_sibling_path(self.path)
        try:
            temporary.write_bytes(
                canonical_json_bytes(audit.model_dump(mode="json")) + b"\n"
            )
            os.replace(temporary, self.path)
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        return audit

    def record_evidence(
        self,
        *,
        role: str,
        resource_id: str,
        model_id: str,
        requirement: OutputFormatRequirement,
        evidence: CapabilityProbeEvidence,
    ) -> SystemRoleProbeAttempt:
        with self._lock:
            attempt = SystemRoleProbeAttempt(
                role=role,
                attempt_index=self._next_attempt_index(role),
                resource_id=resource_id,
                model_id=model_id,
                endpoint_identity_sha256=evidence.endpoint_identity_sha256,
                requirement_sha256=requirement.requirement_sha256,
                schema_sha256=str(requirement.schema_sha256),
                wire_schema_protocol=evidence.wire_schema_protocol,
                wire_schema_sha256=evidence.wire_schema_sha256,
                attempted_enforcement_modes=evidence.attempted_enforcement_modes,
                selected_enforcement_mode=evidence.selected_enforcement_mode,
                evidence_sha256=evidence.evidence_sha256,
                status=("verified" if evidence.outcome == "live_verified" else "rejected"),
                reason_code=evidence.reason_code,
                accounting_reference=evidence.accounting_reference,
            )
            self._attempts.append(attempt)
            self._write()
            return attempt

    def record_aborted(
        self,
        *,
        role: str,
        resource_id: str,
        model_id: str,
        requirement: OutputFormatRequirement,
        endpoint_identity_sha256: str,
        reason_code: str,
        accounting_reference: Mapping[str, Any] | None = None,
    ) -> SystemRoleProbeAttempt:
        with self._lock:
            attempt = SystemRoleProbeAttempt(
                role=role,
                attempt_index=self._next_attempt_index(role),
                resource_id=resource_id,
                model_id=model_id,
                endpoint_identity_sha256=endpoint_identity_sha256,
                requirement_sha256=requirement.requirement_sha256,
                schema_sha256=str(requirement.schema_sha256),
                wire_schema_protocol=(
                    requirement.portable_wire_schema.protocol
                    if requirement.portable_wire_schema is not None
                    else None
                ),
                wire_schema_sha256=requirement.wire_schema_sha256,
                evidence_sha256=None,
                status="aborted",
                reason_code=reason_code,
                accounting_reference=accounting_reference,
            )
            self._attempts.append(attempt)
            self._write()
            return attempt

    def select_model(
        self,
        *,
        role: str,
        resource_id: str,
        model_id: str,
        response_mode: str = "native_strict_schema",
    ) -> None:
        with self._lock:
            self._selected_models[str(role)] = {
                "resource_id": str(resource_id),
                "model_id": str(model_id),
                "response_mode": str(response_mode),
            }
            self._write()

    def bind_sealed_receipt(
        self,
        *,
        receipt_file_sha256: str,
        result_sha256: str,
    ) -> None:
        with self._lock:
            self._authority_source = "release_receipt"
            self._control_probe_receipt_sha256 = None
            self._control_probe_result_sha256 = None
            self._applied_ready_state_sha256 = None
            self._sealed_release_probe_receipt_sha256 = _validate_sha256(
                receipt_file_sha256,
                field_name="sealed_release_probe_receipt_sha256",
            )
            self._sealed_release_probe_result_sha256 = _validate_sha256(
                result_sha256,
                field_name="sealed_release_probe_result_sha256",
            )
            self._write()

    def bind_git_runtime(
        self, *, applied_ready_state_sha256: str,
        control_probe_receipt_sha256: str | None = None,
        control_probe_result_sha256: str | None = None,
    ) -> None:
        with self._lock:
            self._authority_source = "git_runtime"
            self._control_probe_receipt_sha256 = _validate_sha256(
                control_probe_receipt_sha256, field_name="control_probe_receipt_sha256",
            )
            self._control_probe_result_sha256 = _validate_sha256(
                control_probe_result_sha256, field_name="control_probe_result_sha256",
            )
            self._sealed_release_probe_receipt_sha256 = None
            self._sealed_release_probe_result_sha256 = None
            self._applied_ready_state_sha256 = _validate_sha256(
                applied_ready_state_sha256,
                field_name="applied_ready_state_sha256",
            )
            self._write()

    def mark_verified(self) -> SystemRoleProbeAudit:
        with self._lock:
            if self._status == "terminated":
                return self._snapshot()
            if self._authority_source == "unbound":
                raise ValueError("system_role_probe_audit_authority_unbound")
            self._status = "verified"
            self._terminal_failure = None
            return self._write()

    def terminate(self, failure: TerminalFailureEnvelope) -> SystemRoleProbeAudit:
        with self._lock:
            if self._status == "verified":
                return self._snapshot()
            self._status = "terminated"
            self._terminal_failure = failure
            return self._write()


__all__ = [
    "SYSTEM_ROLE_SCHEMA_PROBE_AUDIT_PROTOCOL",
    "SYSTEM_ROLE_SCHEMA_PROBE_AUDIT_PROTOCOL_V2",
    "SYSTEM_ROLE_SCHEMA_PROBE_AUDIT_PROTOCOL_V3",
    "SYSTEM_ROLE_SCHEMA_PROBE_AUDIT_PROTOCOL_V4",
    "SYSTEM_ROLE_SCHEMA_PROBE_AUDIT_PROTOCOL_V5",
    "SystemRoleProbeAttempt",
    "SystemRoleProbeAudit",
    "SystemRoleProbeAuditStore",
]
