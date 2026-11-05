"""Isolated production run workspaces and terminal manifest persistence."""

from __future__ import annotations

import os
import hashlib
import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Mapping

from pydantic import Field, field_validator, model_validator

from .pipeline_control import FrozenContract, canonical_json_bytes, canonical_sha256
from .portability_audit import audit_run_portability
from .terminal_failure import TerminalFailureEnvelope
from .path_policy import is_private_host_path_value


RUN_WORKSPACE_PROTOCOL = "sgar-run-workspace-v1"
RUN_MANIFEST_PROTOCOL_V1 = "sgar-run-manifest-v1"
RUN_MANIFEST_PROTOCOL = "sgar-run-manifest-v2"
_TERMINAL_STATUSES = {
    "succeeded",
    "research_failure",
    "infrastructure_failure",
    "framework_failure",
    "budget_failure",
    "interrupted",
}
_SECRET_KEYS = re.compile(
    r"(?i)^(?:api[_-]?key|authorization|password|secret|access[_-]?token|"
    r"refresh[_-]?token|bearer[_-]?token)$"
)


class RunWorkspaceError(RuntimeError):
    """Raised before log/model initialization for an unsafe run directory."""


class StructuredRunFailure(FrozenContract):
    responsibility: Literal[
        "framework", "infrastructure", "research", "budget", "interrupted"
    ]
    failure_stage: str = Field(min_length=1)
    failure_code: str = Field(min_length=1)
    exception_type: str = ""
    retryable: bool = False
    message_sha256: str

    @field_validator("message_sha256")
    @classmethod
    def _validate_hash(cls, value: str) -> str:
        normalized = value.lower()
        if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
            raise ValueError("message_sha256_invalid")
        return normalized


class RunManifest(FrozenContract):
    protocol: Literal[RUN_MANIFEST_PROTOCOL_V1, RUN_MANIFEST_PROTOCOL] = RUN_MANIFEST_PROTOCOL
    workspace_protocol: Literal[RUN_WORKSPACE_PROTOCOL] = RUN_WORKSPACE_PROTOCOL
    run_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    invocation_sha256: str
    status: Literal[
        "initializing",
        "running",
        "succeeded",
        "research_failure",
        "infrastructure_failure",
        "framework_failure",
        "budget_failure",
        "interrupted",
    ]
    phases: Mapping[str, str] = Field(default_factory=dict)
    identities: Mapping[str, Any] = Field(default_factory=dict)
    primary_failure: StructuredRunFailure | None = None
    recovery_outcome: Mapping[str, Any] | None = None
    terminal_failure: StructuredRunFailure | None = None
    causal_chain: tuple[Mapping[str, Any], ...] = ()
    secondary_audit_failures: tuple[Mapping[str, Any], ...] = ()
    ledger_hashes: Mapping[str, str] = Field(default_factory=dict)
    unmatched_calls: Mapping[str, int] = Field(default_factory=dict)
    framework_source_clean: bool | None = None
    framework_gate_passed: bool | None = None
    manifest_valid: bool = False
    pipeline_succeeded: bool = False
    real_case_passed: bool | None = None
    manifest_sha256: str

    @field_validator("invocation_sha256", "manifest_sha256")
    @classmethod
    def _validate_sha(cls, value: str, info: Any) -> str:
        normalized = value.lower()
        if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
            raise ValueError(f"{info.field_name}_invalid")
        return normalized

    @model_validator(mode="after")
    def _validate_identity(self) -> "RunManifest":
        excluded = {"manifest_sha256"}
        if self.protocol == RUN_MANIFEST_PROTOCOL_V1:
            excluded.update(
                {
                    "framework_gate_passed",
                    "manifest_valid",
                    "pipeline_succeeded",
                    "real_case_passed",
                }
            )
        projection = self.model_dump(mode="python", exclude=excluded)
        if canonical_sha256(projection) != self.manifest_sha256:
            raise ValueError("run_manifest_sha256_mismatch")
        if self.status.endswith("failure") and self.primary_failure is None:
            raise ValueError("failed_run_requires_primary_failure")
        return self


class RunManifestStore:
    def __init__(
        self,
        *,
        run_dir: Path,
        run_id: str,
        request_id: str,
        invocation_sha256: str,
    ) -> None:
        self.run_dir = run_dir.resolve()
        self.path = self.run_dir / "run_manifest.json"
        self._lock = threading.RLock()
        self._portability_secret_values: tuple[str, ...] = ()
        self._portability_hidden_values: tuple[str, ...] = ()
        self._state: dict[str, Any] = {
            "protocol": RUN_MANIFEST_PROTOCOL,
            "workspace_protocol": RUN_WORKSPACE_PROTOCOL,
            "run_id": run_id,
            "request_id": request_id,
            "invocation_sha256": invocation_sha256,
            "status": "initializing",
            "phases": {},
            "identities": {},
            "primary_failure": None,
            "recovery_outcome": None,
            "terminal_failure": None,
            "causal_chain": [],
            "secondary_audit_failures": [],
            "ledger_hashes": {},
            "unmatched_calls": {},
            "framework_source_clean": None,
            "framework_gate_passed": None,
            "manifest_valid": False,
            "pipeline_succeeded": False,
            "real_case_passed": None,
        }
        self._write()

    def set_private_portability_needles(
        self,
        *,
        secret_values: tuple[str, ...] = (),
        hidden_values: tuple[str, ...] = (),
    ) -> None:
        """Register private comparison values without serializing them."""

        with self._lock:
            self._portability_secret_values = tuple(
                value for value in secret_values if value
            )
            self._portability_hidden_values = tuple(
                value for value in hidden_values if value
            )

    def bind_invocation(
        self,
        *,
        request_id: str,
        invocation_sha256: str,
        identities: Mapping[str, Any] | None = None,
    ) -> RunManifest:
        """Replace the pre-snapshot bootstrap identity with the sealed request."""

        with self._lock:
            if self._state["status"] != "initializing":
                raise RunWorkspaceError("run_invocation_must_bind_while_initializing")
            self._state["request_id"] = request_id
            self._state["invocation_sha256"] = invocation_sha256
            if identities:
                merged = dict(self._state["identities"])
                merged.update(dict(identities))
                self._state["identities"] = merged
            return self._write()

    def _write(self) -> RunManifest:
        projection = dict(self._state)
        manifest = RunManifest(
            **projection,
            manifest_sha256=canonical_sha256(projection),
        )
        temporary = self.path.with_name(f".rm-{uuid.uuid4().hex[:8]}.tmp")
        payload = canonical_json_bytes(manifest.model_dump(mode="json"))
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.path)
        return manifest

    def mark_running(self, *, identities: Mapping[str, Any] | None = None) -> RunManifest:
        with self._lock:
            self._state["status"] = "running"
            if identities:
                merged = dict(self._state["identities"])
                merged.update(dict(identities))
                self._state["identities"] = merged
            return self._write()

    def update_phase(self, phase: str, status: str) -> RunManifest:
        with self._lock:
            phases = dict(self._state["phases"])
            phases[str(phase)] = str(status)
            self._state["phases"] = phases
            return self._write()

    def update_identities(self, identities: Mapping[str, Any]) -> RunManifest:
        with self._lock:
            merged = dict(self._state["identities"])
            merged.update(dict(identities))
            self._state["identities"] = merged
            return self._write()

    def set_ledger_evidence(
        self,
        *,
        ledger_hashes: Mapping[str, str],
        unmatched_calls: Mapping[str, int],
    ) -> RunManifest:
        with self._lock:
            self._state["ledger_hashes"] = dict(ledger_hashes)
            self._state["unmatched_calls"] = dict(unmatched_calls)
            return self._write()

    def add_secondary_audit_failure(self, payload: Mapping[str, Any]) -> RunManifest:
        with self._lock:
            failures = list(self._state["secondary_audit_failures"])
            failures.append(dict(payload))
            self._state["secondary_audit_failures"] = failures
            return self._write()

    def terminal(
        self,
        status: Literal[
            "succeeded",
            "research_failure",
            "infrastructure_failure",
            "framework_failure",
            "budget_failure",
            "interrupted",
        ],
        *,
        primary_failure: StructuredRunFailure | None = None,
        terminal_failure: StructuredRunFailure | None = None,
        ledger_hashes: Mapping[str, str] | None = None,
        unmatched_calls: Mapping[str, int] | None = None,
        framework_source_clean: bool | None = None,
        recovery_outcome: Mapping[str, Any] | None = None,
        causal_chain: tuple[Mapping[str, Any], ...] = (),
        real_case_passed: bool | None = None,
    ) -> RunManifest:
        with self._lock:
            if ledger_hashes is None or unmatched_calls is None:
                evidence = collect_run_ledger_evidence(
                    self.run_dir,
                    expected_run_id=str(self._state["run_id"]),
                )
                if ledger_hashes is None:
                    ledger_hashes = evidence["ledger_hashes"]
                if unmatched_calls is None:
                    unmatched_calls = evidence["unmatched_calls"]
            self._state["status"] = status
            self._state["primary_failure"] = (
                primary_failure.model_dump(mode="json")
                if primary_failure is not None
                else None
            )
            self._state["terminal_failure"] = (
                (terminal_failure or primary_failure).model_dump(mode="json")
                if terminal_failure is not None or primary_failure is not None
                else None
            )
            self._state["recovery_outcome"] = (
                dict(recovery_outcome) if recovery_outcome is not None else None
            )
            self._state["causal_chain"] = [dict(item) for item in causal_chain]
            self._state["ledger_hashes"] = dict(ledger_hashes)
            self._state["unmatched_calls"] = dict(unmatched_calls)
            self._state["framework_gate_passed"] = bool(
                self._state.get("phases", {}).get("framework_conformance") == "passed"
            )
            self._state["pipeline_succeeded"] = status == "succeeded"
            self._state["real_case_passed"] = (
                bool(real_case_passed) if real_case_passed is not None else None
            )
            if framework_source_clean is not None:
                self._state["framework_source_clean"] = framework_source_clean
            self._state["phases"] = {
                **dict(self._state["phases"]),
                "run_portability": "checking",
            }
            self._state["identities"] = {
                **dict(self._state["identities"]),
                "run_portability_protocol": "sgar-run-portability-audit-v1",
            }
            self._write()
            portability = audit_run_portability(
                self.run_dir,
                host_roots=(self.run_dir, self.run_dir.parent),
                secret_values=self._portability_secret_values,
                hidden_values=self._portability_hidden_values,
            )
            phases = dict(self._state["phases"])
            phases["run_portability"] = (
                "passed" if portability["valid"] else "failed"
            )
            self._state["phases"] = phases
            if not portability["valid"]:
                existing = self._state.get("primary_failure")
                self._state["status"] = "framework_failure"
                self._state["pipeline_succeeded"] = False
                self._state["real_case_passed"] = False
                failure = sanitized_run_failure(
                    responsibility="framework",
                    failure_stage="run_portability",
                    failure_code="formal_run_portability_audit_failed",
                )
                if existing:
                    failures = list(self._state["secondary_audit_failures"])
                    failures.append(failure.model_dump(mode="json"))
                    self._state["secondary_audit_failures"] = failures
                else:
                    self._state["primary_failure"] = failure.model_dump(mode="json")
                self._state["terminal_failure"] = failure.model_dump(mode="json")
                chain = list(self._state.get("causal_chain") or ())
                chain.append(
                    {
                        "sequence": len(chain),
                        "kind": "terminal_audit_failure",
                        "subtask_id": "",
                        "responsibility": failure.responsibility,
                        "failure_stage": failure.failure_stage,
                        "failure_code": failure.failure_code,
                        "message_sha256": failure.message_sha256,
                    }
                )
                self._state["causal_chain"] = chain
            self._state["manifest_valid"] = True
            return self._write()


class RunWorkspace(FrozenContract):
    protocol: Literal[RUN_WORKSPACE_PROTOCOL] = RUN_WORKSPACE_PROTOCOL
    run_id: str = Field(min_length=1)
    run_dir: str = Field(min_length=1, exclude=True)

    def path(self) -> Path:
        return Path(self.run_dir)


def create_run_workspace(
    *,
    output_root: Path,
    explicit_run_dir: Path | None = None,
) -> RunWorkspace:
    """Create a fresh run directory before any log file is opened."""

    run_id = uuid.uuid4().hex
    if explicit_run_dir is not None:
        target = explicit_run_dir.absolute()
        if target.exists():
            if not target.is_dir():
                raise RunWorkspaceError("run_dir_not_directory")
            try:
                first_entry = next(target.iterdir(), None)
            except OSError as exc:
                raise RunWorkspaceError("run_dir_not_readable") from exc
            if first_entry is not None:
                raise RunWorkspaceError("run_dir_must_be_new_or_empty")
        else:
            target.mkdir(parents=True, exist_ok=False)
    else:
        root = output_root.absolute()
        root.mkdir(parents=True, exist_ok=True)
        # Keep the directory component compact enough for Windows' legacy
        # MAX_PATH boundary while retaining the full run_id inside manifests.
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = root / f"{timestamp}_{run_id[:12]}"
        target.mkdir(parents=False, exist_ok=False)
    return RunWorkspace(run_id=run_id, run_dir=str(target.resolve()))


def sanitized_run_failure(
    *,
    responsibility: Literal[
        "framework", "infrastructure", "research", "budget", "interrupted"
    ],
    failure_stage: str,
    failure_code: str,
    exception: BaseException | None = None,
    retryable: bool = False,
) -> StructuredRunFailure:
    message = str(exception) if exception is not None else failure_code
    return StructuredRunFailure(
        responsibility=responsibility,
        failure_stage=failure_stage,
        failure_code=failure_code,
        exception_type=type(exception).__name__ if exception is not None else "",
        retryable=retryable,
        message_sha256=canonical_sha256(message),
    )


def structured_run_failure_from_terminal(
    failure: TerminalFailureEnvelope,
) -> StructuredRunFailure:
    """Project the causal terminal fact into the stable RunManifest v1 schema."""

    if not isinstance(failure, TerminalFailureEnvelope):
        raise RunWorkspaceError("terminal_failure_envelope_required")
    return StructuredRunFailure(
        responsibility=failure.responsibility,
        failure_stage=failure.failure_stage,
        failure_code=failure.failure_code,
        exception_type=failure.exception_type,
        retryable=failure.retryable,
        message_sha256=failure.message_sha256,
    )


_LEDGER_PATHS = (
    "model_calls.jsonl",
    "model_pricing_snapshot.json",
    "cost_summary.json",
    "system_role_schema_probes.json",
    "run_events.jsonl",
    "execution_summary.json",
    "recovery/recovery_events.jsonl",
    "recovery/recovery_summary.json",
    "evaluation/evaluation_events.jsonl",
    "evaluation/evaluation_summary.json",
    "artifacts/artifact_events.jsonl",
    "artifacts/context_commits.jsonl",
    "artifacts/artifact_summary.json",
    "artifacts/context_summary.json",
    "trace.jsonl",
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _read_summary(path: Path) -> Mapping[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RunWorkspaceError("run_summary_invalid") from exc
    if not isinstance(payload, Mapping):
        raise RunWorkspaceError("run_summary_root_invalid")
    return payload


def _read_jsonl_events(path: Path) -> tuple[list[Mapping[str, Any]], int]:
    """Read public ledger facts without allowing a corrupt line to hide a run.

    The terminal manifest must still be writable when a component ledger is
    damaged.  The caller records the parse error as an unmatched framework
    invariant instead of propagating the raw exception or silently treating
    the ledger as empty.
    """

    if not path.is_file():
        return [], 0
    events: list[Mapping[str, Any]] = []
    errors = 0
    try:
        with path.open("r", encoding="utf-8-sig", errors="strict") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    errors += 1
                    continue
                if not isinstance(event, Mapping):
                    errors += 1
                    continue
                events.append(event)
    except (OSError, UnicodeError):
        return [], 1
    return events, errors


def _unmatched_event_count(
    events: list[Mapping[str, Any]],
    *,
    started_types: set[str],
    terminal_types: set[str],
    identity_key: str,
    standalone_terminal_types: set[str] | None = None,
) -> int:
    started: set[str] = set()
    terminal: set[str] = set()
    unbound_started = 0
    unbound_terminal = 0
    standalone = standalone_terminal_types or set()
    for event in events:
        event_type = str(event.get("event_type") or "")
        identity = str(event.get(identity_key) or "")
        if event_type in started_types:
            if identity:
                started.add(identity)
            else:
                unbound_started += 1
        elif event_type in terminal_types:
            if identity:
                terminal.add(identity)
            elif event_type not in standalone:
                unbound_terminal += 1
    orphan_terminal = terminal - started
    if standalone:
        standalone_ids = {
            str(event.get(identity_key) or "")
            for event in events
            if str(event.get("event_type") or "") in standalone
        }
        orphan_terminal -= standalone_ids
    return (
        len(started - terminal)
        + len(orphan_terminal)
        + max(0, unbound_started - unbound_terminal)
        + max(0, unbound_terminal - unbound_started)
    )


def collect_run_ledger_evidence(
    run_dir: str | Path,
    *,
    expected_run_id: str | None = None,
) -> dict[str, Any]:
    """Recompute ledger hashes and open operations from append-only facts."""

    root = Path(run_dir).resolve()
    ledger_hashes = {
        locator: _sha256_file(root / locator)
        for locator in _LEDGER_PATHS
        if (root / locator).is_file()
    }
    candidate_dir = root / "candidate_pools"
    if candidate_dir.is_dir():
        for candidate_path in sorted(candidate_dir.glob("*.json")):
            locator = candidate_path.relative_to(root).as_posix()
            ledger_hashes[locator] = _sha256_file(candidate_path)
    model_events, model_errors = _read_jsonl_events(root / "model_calls.jsonl")
    execution_events, execution_errors = _read_jsonl_events(root / "run_events.jsonl")
    recovery_events, recovery_errors = _read_jsonl_events(
        root / "recovery" / "recovery_events.jsonl"
    )
    evaluation_events, evaluation_errors = _read_jsonl_events(
        root / "evaluation" / "evaluation_events.jsonl"
    )
    artifact_events, artifact_errors = _read_jsonl_events(
        root / "artifacts" / "artifact_events.jsonl"
    )
    context_events, context_errors = _read_jsonl_events(
        root / "artifacts" / "context_commits.jsonl"
    )
    summary_errors = 0
    run_identity_mismatches = 0
    for summary_path in (
        root / "cost_summary.json",
        root / "execution_summary.json",
        root / "recovery" / "recovery_summary.json",
        root / "evaluation" / "evaluation_summary.json",
        root / "artifacts" / "artifact_summary.json",
        root / "artifacts" / "context_summary.json",
    ):
        try:
            summary = _read_summary(summary_path)
            if summary and expected_run_id is not None:
                if str(summary.get("run_id") or "") != str(expected_run_id):
                    run_identity_mismatches += 1
        except RunWorkspaceError:
            summary_errors += 1
    unmatched = {
        "model_calls": _unmatched_event_count(
            model_events,
            started_types={"model_call_started"},
            terminal_types={"model_call_finished"},
            identity_key="provider_attempt_id",
        ),
        "resource_calls": _unmatched_event_count(
            execution_events,
            started_types={"resource_call_started"},
            terminal_types={
                "resource_call_finished",
                "resource_call_blocked",
                "resource_call_interrupted",
            },
            identity_key="call_id",
            standalone_terminal_types={"resource_call_blocked"},
        ),
        "recovery_calls": _unmatched_event_count(
            recovery_events,
            started_types={"recovery_started"},
            terminal_types={"recovery_terminal", "recovery_interrupted"},
            identity_key="recovery_identity_sha256",
        ),
        "evaluation_calls": _unmatched_event_count(
            evaluation_events,
            started_types={"evaluation_started", "evaluation_review_started"},
            terminal_types={
                "evaluation_finished",
                "evaluation_review_finished",
                "evaluation_interrupted",
            },
            identity_key="evaluation_operation_id",
        ),
        "artifact_operations": _unmatched_event_count(
            artifact_events,
            started_types={"artifact_stage_started"},
            terminal_types={
                "artifact_staged",
                "artifact_quarantined",
                "artifact_committed",
                "artifact_stage_interrupted",
            },
            identity_key="artifact_revision_sha256",
        ),
        "context_commits": _unmatched_event_count(
            context_events,
            started_types={"artifact_commit_started"},
            terminal_types={"artifact_committed", "artifact_commit_interrupted"},
            identity_key="artifact_revision_sha256",
        ),
        "ledger_audit_errors": (
            model_errors
            + execution_errors
            + recovery_errors
            + evaluation_errors
            + artifact_errors
            + context_errors
            + summary_errors
            + run_identity_mismatches
        ),
        "run_identity_mismatches": run_identity_mismatches,
    }
    return {
        "ledger_hashes": dict(sorted(ledger_hashes.items())),
        "unmatched_calls": unmatched,
    }


def _unsafe_public_projection(value: Any) -> str | None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if _SECRET_KEYS.fullmatch(str(key)):
                return str(key)
            found = _unsafe_public_projection(item)
            if found:
                return found
        return None
    if isinstance(value, (list, tuple)):
        for item in value:
            found = _unsafe_public_projection(item)
            if found:
                return found
        return None
    if isinstance(value, str) and (
        is_private_host_path_value(value)
    ):
        return "host_path"
    return None


def validate_run_manifest(
    run_dir: str | Path,
    *,
    require_production_conformance: bool = False,
) -> dict[str, Any]:
    """Independently validate one terminal production run."""

    root = Path(run_dir).resolve()
    path = root / "run_manifest.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig", errors="strict"))
        manifest = RunManifest.model_validate(payload)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise RunWorkspaceError("terminal_run_manifest_invalid") from exc
    if manifest.status not in _TERMINAL_STATUSES:
        raise RunWorkspaceError("run_manifest_not_terminal")
    unsafe = _unsafe_public_projection(manifest.model_dump(mode="json"))
    if unsafe:
        raise RunWorkspaceError("run_manifest_public_projection_unsafe")
    portability = audit_run_portability(
        root,
        host_roots=(root, root.parent),
    )
    ledger_unreadable_is_terminal_diagnostic = bool(
        manifest.status == "framework_failure"
        and manifest.phases.get("run_portability") == "failed"
        and portability["unreadable_formal_records"]
        and set(portability["unreadable_formal_records"]).issubset(_LEDGER_PATHS)
        and int(manifest.unmatched_calls.get("ledger_audit_errors", 0)) > 0
        and not portability["host_path_occurrences"]
        and not portability["secret_occurrences"]
        and not portability["hidden_value_occurrences"]
    )
    if not portability["valid"] and not ledger_unreadable_is_terminal_diagnostic:
        raise RunWorkspaceError("run_manifest_portability_audit_invalid")
    if (
        manifest.phases.get("run_portability") != "passed"
        and not ledger_unreadable_is_terminal_diagnostic
    ):
        raise RunWorkspaceError("run_manifest_portability_audit_missing")
    evidence = collect_run_ledger_evidence(root, expected_run_id=manifest.run_id)
    if dict(manifest.ledger_hashes) != evidence["ledger_hashes"]:
        raise RunWorkspaceError("run_manifest_ledger_hash_mismatch")
    if dict(manifest.unmatched_calls) != evidence["unmatched_calls"]:
        raise RunWorkspaceError("run_manifest_unmatched_call_mismatch")
    complete = not any(evidence["unmatched_calls"].values())
    if manifest.status == "succeeded" and not complete:
        raise RunWorkspaceError("successful_run_has_unmatched_calls")
    framework_gate_passed = False
    conformance_path = root / "framework_conformance.json"
    if conformance_path.is_file():
        from .production_conformance import validate_production_conformance_report

        try:
            conformance = validate_production_conformance_report(
                conformance_path,
                expected_invocation_sha256=manifest.invocation_sha256,
                require_valid=False,
            )
        except Exception as exc:
            raise RunWorkspaceError("run_manifest_conformance_invalid") from exc
        framework_gate_passed = bool(
            conformance.get("valid") is True
            and manifest.phases.get("framework_conformance") == "passed"
            and manifest.identities.get("framework_conformance_sha256")
            == conformance.get("report_sha256")
            and manifest.framework_source_clean is True
        )
    pipeline_succeeded = manifest.status == "succeeded"
    production_ready = framework_gate_passed and pipeline_succeeded
    if require_production_conformance and not framework_gate_passed:
        legitimate_gate_failure = bool(
            manifest.status in {"framework_failure", "interrupted"}
            and manifest.phases.get("pipeline") != "running"
        )
        if not legitimate_gate_failure:
            raise RunWorkspaceError("run_manifest_production_conformance_missing")
    return {
        "protocol": RUN_MANIFEST_PROTOCOL,
        "valid": True,
        "run_id": manifest.run_id,
        "request_id": manifest.request_id,
        "status": manifest.status,
        "complete": complete,
        "framework_gate_passed": framework_gate_passed,
        "manifest_valid": True,
        "pipeline_succeeded": pipeline_succeeded,
        "real_case_passed": manifest.real_case_passed,
        "production_ready": production_ready,
        "portability_audit": portability,
        "manifest_sha256": manifest.manifest_sha256,
        **evidence,
    }


__all__ = [
    "RUN_MANIFEST_PROTOCOL",
    "RUN_MANIFEST_PROTOCOL_V1",
    "RUN_WORKSPACE_PROTOCOL",
    "RunManifest",
    "RunManifestStore",
    "RunWorkspace",
    "RunWorkspaceError",
    "StructuredRunFailure",
    "collect_run_ledger_evidence",
    "create_run_workspace",
    "sanitized_run_failure",
    "validate_run_manifest",
]
