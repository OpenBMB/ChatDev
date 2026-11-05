"""Append-only execution facts for the generic S-GAR resource runtime.

The ledger stores identities, hashes, and structured failure metadata only.  It
deliberately does not persist requests, outputs, prompts, host paths, or raw
exception text.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Mapping

from pydantic import Field, model_validator

from .atomic_io import temporary_sibling_path
from .pipeline_control import FrozenContract, canonical_json_bytes
from .path_policy import is_windows_absolute_path


EXECUTION_EVENT_PROTOCOL = "sgar-execution-events-v1"


class ExecutionEventError(RuntimeError):
    """Base error for execution-ledger invariants."""


class ExecutionPersistenceError(ExecutionEventError):
    """Raised when an execution fact cannot be persisted durably."""


class ExecutionCallHandle(FrozenContract):
    protocol: Literal[EXECUTION_EVENT_PROTOCOL] = EXECUTION_EVENT_PROTOCOL
    run_id: str = Field(min_length=1)
    call_id: str = Field(min_length=1)
    started_event_id: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    resource_type: str = Field(min_length=1)
    entrypoint_id: str = Field(min_length=1)
    runtime_kind: str = "unknown"
    graph_revision: int = Field(ge=0)
    subtask_id: str = Field(min_length=1)
    subtask_revision: int = Field(ge=0)
    step_id: str = Field(min_length=1)
    attempt: int = Field(ge=1)
    request_sha256: str = Field(min_length=64, max_length=64)
    candidate_pool_sha256: str = Field(min_length=64, max_length=64)
    plan_sha256: str = Field(min_length=64, max_length=64)
    sandbox_scope_sha256: str = Field(min_length=64, max_length=64)

    @classmethod
    def _validate_sha256(cls, value: str, *, field_name: str) -> str:
        normalized = str(value or "").strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", normalized):
            raise ValueError(f"{field_name}_must_be_sha256_hex")
        return normalized

    @model_validator(mode="after")
    def _validate_hashes(self) -> "ExecutionCallHandle":
        for field_name in (
            "request_sha256",
            "candidate_pool_sha256",
            "plan_sha256",
            "sandbox_scope_sha256",
        ):
            self._validate_sha256(getattr(self, field_name), field_name=field_name)
        return self


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_host_path(value: str) -> bool:
    text = str(value)
    return bool(
        is_windows_absolute_path(text)
        or text.startswith("file:///")
    )


def _assert_host_free(value: Any, *, locator: str = "event") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            _assert_host_free(item, locator=f"{locator}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_host_free(item, locator=f"{locator}[{index}]")
        return
    if isinstance(value, str) and _is_host_path(value):
        raise ExecutionEventError(f"host_path_in_execution_event:{locator}")


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = temporary_sibling_path(path)
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def summarize_execution_events(events: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Recompute the public execution summary from append-only facts."""

    started: dict[str, Mapping[str, Any]] = {}
    terminal: dict[str, Mapping[str, Any]] = {}
    artifacts = 0
    event_counts: Counter[str] = Counter()
    by_resource_type: Counter[str] = Counter()
    by_runtime_kind: Counter[str] = Counter()
    by_status: Counter[str] = Counter()
    by_responsibility: Counter[str] = Counter()
    by_failure_stage: Counter[str] = Counter()
    model_usage_references: set[str] = set()
    standalone_blocked: set[str] = set()
    reused_checkpoints: set[str] = set()
    resource_wall_time_ms = 0.0
    resource_runtime_ms = 0.0
    resource_input_bytes = 0
    resource_native_output_bytes = 0
    resource_semantic_output_bytes = 0
    realization_count = 0
    realization_success_count = 0
    realization_failure_count = 0
    realization_latency_ms = 0.0
    realization_source_bytes = 0
    realization_target_bytes = 0
    realization_by_kind: Counter[str] = Counter()
    controller_sessions_started: set[str] = set()
    controller_sessions_terminal: dict[str, Mapping[str, Any]] = {}
    controller_turn_count = 0
    controller_validation_feedback_count = 0
    controller_elapsed_ms = 0.0
    controller_model_accounting_references: set[str] = set()
    controller_tool_call_count = 0
    controller_tool_success_count = 0
    controller_tool_failure_count = 0
    controller_tool_observation_bytes = 0
    controller_tool_resource_call_ids: set[str] = set()
    controller_tool_provenance_ids: set[str] = set()
    controller_tool_observation_sha256s: set[str] = set()

    for event in events:
        event_type = str(event.get("event_type") or "")
        event_counts[event_type] += 1
        call_id = str(event.get("call_id") or "")
        if event_type == "resource_call_started" and call_id:
            started[call_id] = event
            by_resource_type[str(event.get("resource_type") or "unknown")] += 1
            by_runtime_kind[str(event.get("runtime_kind") or "unknown")] += 1
        elif event_type in {
            "resource_call_finished",
            "resource_call_blocked",
            "resource_call_interrupted",
        } and call_id:
            terminal[call_id] = event
            if event_type == "resource_call_blocked":
                standalone_blocked.add(call_id)
            by_status[str(event.get("status") or "unknown")] += 1
            responsibility = event.get("responsibility")
            if responsibility:
                by_responsibility[str(responsibility)] += 1
            failure_stage = event.get("failure_stage")
            if failure_stage:
                by_failure_stage[str(failure_stage)] += 1
            usage_reference = event.get("usage_reference")
            if usage_reference:
                model_usage_references.add(str(usage_reference))
            resource_wall_time_ms += float(event.get("wall_time_ms") or 0)
            resource_runtime_ms += float(event.get("runtime_ms") or 0)
            resource_input_bytes += int(event.get("input_bytes") or 0)
            resource_native_output_bytes += int(
                event.get("native_output_bytes") or 0
            )
            resource_semantic_output_bytes += int(
                event.get("semantic_output_bytes") or 0
            )
        elif event_type == "artifact_registered":
            artifacts += 1
        elif event_type == "resource_call_reused":
            checkpoint_sha256 = str(event.get("checkpoint_sha256") or "")
            if checkpoint_sha256:
                reused_checkpoints.add(checkpoint_sha256)
        elif event_type == "output_realization_finished":
            realization_count += 1
            status = str(event.get("status") or "failure")
            if status == "success":
                realization_success_count += 1
            else:
                realization_failure_count += 1
            realization_by_kind[str(event.get("realization_kind") or "unknown")] += 1
            realization_latency_ms += float(event.get("latency_ms") or 0)
            realization_source_bytes += int(event.get("source_bytes") or 0)
            realization_target_bytes += int(event.get("target_bytes") or 0)
        elif event_type == "controller_session_started":
            session_id = str(event.get("session_id") or "")
            if session_id:
                controller_sessions_started.add(session_id)
        elif event_type == "controller_turn_finished":
            controller_turn_count += 1
            reference = event.get("model_accounting_reference")
            if isinstance(reference, Mapping):
                operation_id = str(reference.get("operation_id") or "")
                if operation_id:
                    controller_model_accounting_references.add(operation_id)
        elif event_type == "controller_validation_feedback":
            controller_validation_feedback_count += 1
        elif event_type == "controller_tool_call_finished":
            controller_tool_call_count += 1
            if event.get("status") == "success":
                controller_tool_success_count += 1
            else:
                controller_tool_failure_count += 1
            resource_call_id = str(event.get("resource_call_id") or "")
            if resource_call_id:
                controller_tool_resource_call_ids.add(resource_call_id)
            provenance_id = str(event.get("provenance_sha256") or "")
            if provenance_id:
                controller_tool_provenance_ids.add(provenance_id)
        elif event_type == "controller_tool_observation_created":
            controller_tool_observation_bytes += int(
                event.get("observation_bytes") or 0
            )
            observation_sha = str(event.get("observation_sha256") or "")
            if observation_sha:
                controller_tool_observation_sha256s.add(observation_sha)
        elif event_type in {
            "controller_session_finished",
            "controller_session_failed",
        }:
            session_id = str(event.get("session_id") or "")
            if session_id:
                controller_sessions_terminal[session_id] = event
            controller_elapsed_ms += float(event.get("elapsed_ms") or 0)

    unmatched = sorted(set(started) - set(terminal))
    orphan_terminal = sorted(set(terminal) - set(started) - standalone_blocked)
    canonical_events = b"\n".join(canonical_json_bytes(event) for event in events)
    return {
        "schema_version": EXECUTION_EVENT_PROTOCOL,
        "execution_mode": (
            "hybrid"
            if controller_sessions_started and started
            else "controller_session"
            if controller_sessions_started
            else "resource_runtime"
        ),
        "event_count": len(events),
        "event_counts": dict(sorted(event_counts.items())),
        "started_count": len(started),
        "terminal_count": len(terminal),
        "unmatched_call_ids": unmatched,
        "orphan_terminal_call_ids": orphan_terminal,
        "complete": not unmatched and not orphan_terminal,
        "artifact_count": artifacts,
        "reused_call_count": len(reused_checkpoints),
        "resource_call_count": len(started),
        "resource_call_success_count": sum(
            1 for item in terminal.values() if item.get("status") == "success"
        ),
        "resource_call_failure_count": sum(
            1 for item in terminal.values() if item.get("status") != "success"
        ),
        "resource_wall_time_ms": resource_wall_time_ms,
        "resource_runtime_ms": resource_runtime_ms,
        "resource_input_bytes": resource_input_bytes,
        "resource_native_output_bytes": resource_native_output_bytes,
        "resource_semantic_output_bytes": resource_semantic_output_bytes,
        "realization_count": realization_count,
        "realization_success_count": realization_success_count,
        "realization_failure_count": realization_failure_count,
        "realization_latency_ms": realization_latency_ms,
        "realization_source_bytes": realization_source_bytes,
        "realization_target_bytes": realization_target_bytes,
        "artifact_bytes": realization_target_bytes,
        "elapsed_time_ms": (
            resource_wall_time_ms + realization_latency_ms + controller_elapsed_ms
        ),
        "realization_by_kind": dict(sorted(realization_by_kind.items())),
        "realization_model_provider_monetary_cost": 0,
        "by_resource_type": dict(sorted(by_resource_type.items())),
        "by_runtime_kind": dict(sorted(by_runtime_kind.items())),
        "by_status": dict(sorted(by_status.items())),
        "by_responsibility": dict(sorted(by_responsibility.items())),
        "by_failure_stage": dict(sorted(by_failure_stage.items())),
        "model_usage_references": sorted(model_usage_references),
        "model_usage_reference_count": len(model_usage_references),
        "controller_session_count": len(controller_sessions_started),
        "controller_session_success_count": sum(
            1
            for item in controller_sessions_terminal.values()
            if item.get("event_type") == "controller_session_finished"
        ),
        "controller_session_failure_count": sum(
            1
            for item in controller_sessions_terminal.values()
            if item.get("event_type") == "controller_session_failed"
        ),
        "controller_turn_count": controller_turn_count,
        "controller_semantic_repair_count": controller_validation_feedback_count,
        "controller_elapsed_ms": controller_elapsed_ms,
        "controller_model_accounting_operation_ids": sorted(
            controller_model_accounting_references
        ),
        "controller_model_accounting_reference_count": len(
            controller_model_accounting_references
        ),
        "controller_monetary_entries_copied": False,
        "controller_tool_call_count": controller_tool_call_count,
        "controller_tool_success_count": controller_tool_success_count,
        "controller_tool_failure_count": controller_tool_failure_count,
        "controller_tool_observation_bytes": controller_tool_observation_bytes,
        "controller_tool_resource_call_ids": sorted(
            controller_tool_resource_call_ids
        ),
        "controller_tool_provenance_ids": sorted(
            controller_tool_provenance_ids
        ),
        "controller_tool_observation_sha256s": sorted(
            controller_tool_observation_sha256s
        ),
        "controller_tool_monetary_entries_copied": False,
        "execution_ledger_sha256": hashlib.sha256(canonical_events).hexdigest(),
        "host_path_occurrences": [],
        "safety_audit": {
            "host_free": True,
            "secret_fields_recorded": False,
            "raw_outputs_recorded": False,
        },
    }


class RunExecutionLedger:
    """Thread-safe append-only fact source for resource execution."""

    def __init__(self, *, output_dir: str | Path, run_id: str) -> None:
        self.output_dir = Path(output_dir)
        self.run_id = str(run_id).strip()
        if not self.run_id:
            raise ExecutionEventError("execution_run_id_empty")
        self.events_path = self.output_dir / "run_events.jsonl"
        self.summary_path = self.output_dir / "execution_summary.json"
        self._lock = threading.RLock()
        self._events: list[dict[str, Any]] = []
        self._pending: dict[str, ExecutionCallHandle] = {}
        self._terminal: dict[str, dict[str, Any]] = {}
        self._closed = False
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            if self.events_path.exists() and self.events_path.stat().st_size:
                raise ExecutionPersistenceError("execution_ledger_already_exists")
            self.write_summary()
        except ExecutionEventError:
            raise
        except Exception as exc:
            raise ExecutionPersistenceError("execution_ledger_initialization_failed") from exc

    def _append_event(self, event: Mapping[str, Any]) -> dict[str, Any]:
        payload = dict(event)
        _assert_host_free(payload)
        serialized = json.dumps(
            payload,
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
            raise ExecutionPersistenceError("execution_event_append_failed") from exc
        self._events.append(payload)
        return payload

    def start_call(
        self,
        *,
        call_id: str,
        resource_id: str,
        resource_type: str,
        entrypoint_id: str,
        runtime_kind: str,
        graph_revision: int,
        subtask_id: str,
        subtask_revision: int,
        step_id: str,
        attempt: int,
        request_sha256: str,
        candidate_pool_sha256: str,
        plan_sha256: str,
        sandbox_scope_sha256: str,
    ) -> ExecutionCallHandle:
        with self._lock:
            if self._closed:
                raise ExecutionPersistenceError("execution_ledger_closed")
            if call_id in self._pending or call_id in self._terminal:
                raise ExecutionEventError("duplicate_resource_call_id")
            handle = ExecutionCallHandle(
                run_id=self.run_id,
                call_id=call_id,
                started_event_id=uuid.uuid4().hex,
                resource_id=resource_id,
                resource_type=resource_type,
                entrypoint_id=entrypoint_id,
                runtime_kind=runtime_kind,
                graph_revision=graph_revision,
                subtask_id=subtask_id,
                subtask_revision=subtask_revision,
                step_id=step_id,
                attempt=attempt,
                request_sha256=request_sha256,
                candidate_pool_sha256=candidate_pool_sha256,
                plan_sha256=plan_sha256,
                sandbox_scope_sha256=sandbox_scope_sha256,
            )
            event = {
                "schema_version": EXECUTION_EVENT_PROTOCOL,
                "event_type": "resource_call_started",
                "event_id": handle.started_event_id,
                "timestamp_utc": _utc_now(),
                **handle.model_dump(mode="json", exclude={"started_event_id", "protocol"}),
            }
            self._append_event(event)
            self._pending[call_id] = handle
            return handle

    def record_world_prepared(
        self,
        handle: ExecutionCallHandle,
        *,
        execution_world_sha256: str,
        runtime_image_id: str,
        direct_argv: bool,
        network_required: bool,
    ) -> str:
        with self._lock:
            if handle.call_id not in self._pending:
                raise ExecutionEventError("execution_world_without_started_call")
            event_id = uuid.uuid4().hex
            self._append_event(
                {
                    "schema_version": EXECUTION_EVENT_PROTOCOL,
                    "event_type": "execution_world_prepared",
                    "event_id": event_id,
                    "timestamp_utc": _utc_now(),
                    "run_id": self.run_id,
                    "call_id": handle.call_id,
                    "resource_id": handle.resource_id,
                    "entrypoint_id": handle.entrypoint_id,
                    "execution_world_sha256": execution_world_sha256,
                    "runtime_image_id": runtime_image_id,
                    "direct_argv": bool(direct_argv),
                    "network_required": bool(network_required),
                }
            )
            return event_id

    def record_reused_call(
        self,
        *,
        original_call_id: str,
        resource_id: str,
        entrypoint_id: str,
        graph_revision: int,
        subtask_id: str,
        subtask_revision: int,
        step_id: str,
        plan_sha256: str,
        candidate_pool_sha256: str,
        checkpoint_sha256: str,
        result_sha256: str,
    ) -> dict[str, Any]:
        """Record checkpoint reuse without fabricating a dispatch or terminal pair."""

        hashes = {
            "plan_sha256": plan_sha256,
            "candidate_pool_sha256": candidate_pool_sha256,
            "checkpoint_sha256": checkpoint_sha256,
            "result_sha256": result_sha256,
        }
        for field_name, value in hashes.items():
            ExecutionCallHandle._validate_sha256(value, field_name=field_name)
        with self._lock:
            if self._closed:
                raise ExecutionPersistenceError("execution_ledger_closed")
            if any(
                item.get("event_type") == "resource_call_reused"
                and item.get("checkpoint_sha256") == checkpoint_sha256
                and item.get("plan_sha256") == plan_sha256
                for item in self._events
            ):
                raise ExecutionEventError("duplicate_checkpoint_reuse_event")
            return self._append_event(
                {
                    "schema_version": EXECUTION_EVENT_PROTOCOL,
                    "event_type": "resource_call_reused",
                    "event_id": uuid.uuid4().hex,
                    "timestamp_utc": _utc_now(),
                    "run_id": self.run_id,
                    "original_call_id": str(original_call_id),
                    "resource_id": str(resource_id),
                    "entrypoint_id": str(entrypoint_id),
                    "graph_revision": int(graph_revision),
                    "subtask_id": str(subtask_id),
                    "subtask_revision": int(subtask_revision),
                    "step_id": str(step_id),
                    **hashes,
                }
            )

    def finish_call(
        self,
        handle: ExecutionCallHandle,
        *,
        status: str,
        result_sha256: str,
        output_contract_status: str,
        responsibility: str | None = None,
        failure_stage: str | None = None,
        failure_code: str | None = None,
        usage_reference: str | None = None,
        execution_audit_sha256: str | None = None,
        wall_time_ms: float = 0,
        runtime_ms: float = 0,
        input_bytes: int = 0,
        native_output_bytes: int = 0,
        semantic_output_bytes: int = 0,
    ) -> dict[str, Any]:
        with self._lock:
            existing = self._terminal.get(handle.call_id)
            if existing is not None:
                raise ExecutionEventError("duplicate_resource_call_terminal")
            if handle.call_id not in self._pending:
                raise ExecutionEventError("terminal_event_without_started_call")
            event = {
                "schema_version": EXECUTION_EVENT_PROTOCOL,
                "event_type": "resource_call_finished",
                "event_id": uuid.uuid4().hex,
                "timestamp_utc": _utc_now(),
                "run_id": self.run_id,
                "call_id": handle.call_id,
                "started_event_id": handle.started_event_id,
                "resource_id": handle.resource_id,
                "resource_type": handle.resource_type,
                "entrypoint_id": handle.entrypoint_id,
                "runtime_kind": handle.runtime_kind,
                "step_id": handle.step_id,
                "attempt": handle.attempt,
                "request_sha256": handle.request_sha256,
                "status": status,
                "responsibility": responsibility,
                "failure_stage": failure_stage,
                "failure_code": failure_code,
                "result_sha256": result_sha256,
                "output_contract_status": output_contract_status,
                "usage_reference": usage_reference,
                "execution_audit_sha256": execution_audit_sha256,
                "wall_time_ms": max(0.0, float(wall_time_ms)),
                "runtime_ms": max(0.0, float(runtime_ms)),
                "input_bytes": max(0, int(input_bytes)),
                "native_output_bytes": max(0, int(native_output_bytes)),
                "semantic_output_bytes": max(0, int(semantic_output_bytes)),
            }
            persisted = self._append_event(event)
            self._terminal[handle.call_id] = persisted
            self._pending.pop(handle.call_id, None)
            return dict(persisted)

    def record_output_realization(
        self,
        *,
        resource_call_id: str,
        realization_id: str,
        realization_kind: str,
        status: str,
        source_bytes: int,
        target_bytes: int,
        latency_ms: float,
        output_realization_contract_sha256: str,
        realized_output_sha256: str | None = None,
        failure_code: str | None = None,
    ) -> dict[str, Any]:
        """Append one host-free realization metric to the execution ledger."""

        with self._lock:
            if self._closed:
                raise ExecutionPersistenceError("execution_ledger_closed")
            return self._append_event(
                {
                    "schema_version": EXECUTION_EVENT_PROTOCOL,
                    "event_type": "output_realization_finished",
                    "event_id": uuid.uuid4().hex,
                    "timestamp_utc": _utc_now(),
                    "run_id": self.run_id,
                    "call_id": str(resource_call_id),
                    "realization_id": str(realization_id),
                    "realization_kind": str(realization_kind),
                    "status": str(status),
                    "source_bytes": max(0, int(source_bytes)),
                    "target_bytes": max(0, int(target_bytes)),
                    "latency_ms": max(0.0, float(latency_ms)),
                    "output_realization_contract_sha256": str(
                        output_realization_contract_sha256
                    ),
                    "realized_output_sha256": realized_output_sha256,
                    "failure_code": failure_code,
                    "model_provider_monetary_cost": 0,
                }
            )

    def block_call(
        self,
        *,
        call_id: str,
        resource_id: str,
        entrypoint_id: str,
        status: str,
        responsibility: str,
        failure_stage: str,
        failure_code: str,
        request_sha256: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if call_id in self._pending or call_id in self._terminal:
                raise ExecutionEventError("duplicate_resource_call_id")
            event = {
                "schema_version": EXECUTION_EVENT_PROTOCOL,
                "event_type": "resource_call_blocked",
                "event_id": uuid.uuid4().hex,
                "timestamp_utc": _utc_now(),
                "run_id": self.run_id,
                "call_id": call_id,
                "resource_id": resource_id,
                "entrypoint_id": entrypoint_id,
                "status": status,
                "responsibility": responsibility,
                "failure_stage": failure_stage,
                "failure_code": failure_code,
                "request_sha256": request_sha256,
            }
            persisted = self._append_event(event)
            self._terminal[call_id] = persisted
            return dict(persisted)

    def _record_controller_event(
        self, event_type: str, **fields: Any
    ) -> dict[str, Any]:
        with self._lock:
            if self._closed:
                raise ExecutionPersistenceError("execution_ledger_closed")
            return self._append_event(
                {
                    "schema_version": EXECUTION_EVENT_PROTOCOL,
                    "event_type": event_type,
                    "event_id": uuid.uuid4().hex,
                    "timestamp_utc": _utc_now(),
                    "run_id": self.run_id,
                    **fields,
                }
            )

    def record_controller_session_started(self, **fields: Any) -> dict[str, Any]:
        return self._record_controller_event("controller_session_started", **fields)

    def record_controller_turn_started(self, **fields: Any) -> dict[str, Any]:
        return self._record_controller_event("controller_turn_started", **fields)

    def record_controller_turn_finished(self, **fields: Any) -> dict[str, Any]:
        reference = fields.get("model_accounting_reference")
        if isinstance(reference, Mapping):
            fields["model_accounting_reference"] = {
                "operation_id": reference.get("operation_id"),
                "provider_attempt_ids": list(
                    reference.get("provider_attempt_ids") or ()
                ),
            }
        return self._record_controller_event("controller_turn_finished", **fields)

    def record_controller_validation_feedback(
        self, **fields: Any
    ) -> dict[str, Any]:
        return self._record_controller_event(
            "controller_validation_feedback", **fields
        )

    def record_controller_finalization_diagnostic(self, **fields: Any) -> dict[str, Any] | None:
        """Keep rejected model receipts in a private sidecar, not the fact ledger.

        Optional diagnostics cannot change execution acceptance or delivery. The
        event contains only an identity/hash; raw task text stays in the run's
        diagnostic file and is never fed into another case.
        """
        with self._lock:
            if self._closed:
                return None
            payload = {"protocol": "sgar-controller-finalization-diagnostic-v1", **fields}
            try:
                digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
                relative = Path("controller_audits") / f"{digest}.json"
                target = self.output_dir / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                _atomic_write_json(target, payload)
                return self._record_controller_event(
                    "controller_finalization_diagnostic",
                    session_id=fields.get("session_id"), turn_id=fields.get("turn_id"),
                    candidate_sha256=fields.get("candidate_sha256"),
                    diagnostic_sha256=digest, diagnostic_locator=relative.as_posix(),
                    validation_reason=fields.get("validation_reason"),
                )
            except (OSError, TypeError, ValueError, ExecutionPersistenceError):
                return None

    def record_controller_tool_call_validated(self, **fields: Any) -> dict[str, Any]:
        return self._record_controller_event(
            "controller_tool_call_validated", **fields
        )

    def record_controller_tool_call_started(self, **fields: Any) -> dict[str, Any]:
        return self._record_controller_event("controller_tool_call_started", **fields)

    def record_controller_tool_call_finished(self, **fields: Any) -> dict[str, Any]:
        return self._record_controller_event("controller_tool_call_finished", **fields)

    def record_controller_tool_observation_created(
        self, **fields: Any
    ) -> dict[str, Any]:
        return self._record_controller_event(
            "controller_tool_observation_created", **fields
        )

    def record_controller_session_finished(self, **fields: Any) -> dict[str, Any]:
        return self._record_controller_event("controller_session_finished", **fields)

    def record_controller_session_failed(self, **fields: Any) -> dict[str, Any]:
        return self._record_controller_event("controller_session_failed", **fields)

    def register_artifact(
        self,
        handle: ExecutionCallHandle,
        *,
        artifact_handle_id: str,
        artifact_type: str,
        logical_path: str | None,
        artifact_sha256: str | None,
    ) -> str:
        with self._lock:
            event_id = uuid.uuid4().hex
            self._append_event(
                {
                    "schema_version": EXECUTION_EVENT_PROTOCOL,
                    "event_type": "artifact_registered",
                    "event_id": event_id,
                    "timestamp_utc": _utc_now(),
                    "run_id": self.run_id,
                    "call_id": handle.call_id,
                    "artifact_handle_id": artifact_handle_id,
                    "artifact_type": artifact_type,
                    "logical_path": logical_path,
                    "artifact_sha256": artifact_sha256,
                }
            )
            return event_id

    def interrupt_pending(self, *, reason_code: str = "pipeline_shutdown") -> None:
        with self._lock:
            for call_id, handle in list(self._pending.items()):
                event = {
                    "schema_version": EXECUTION_EVENT_PROTOCOL,
                    "event_type": "resource_call_interrupted",
                    "event_id": uuid.uuid4().hex,
                    "timestamp_utc": _utc_now(),
                    "run_id": self.run_id,
                    "call_id": call_id,
                    "started_event_id": handle.started_event_id,
                    "resource_id": handle.resource_id,
                    "resource_type": handle.resource_type,
                    "entrypoint_id": handle.entrypoint_id,
                    "runtime_kind": handle.runtime_kind,
                    "status": "interrupted",
                    "responsibility": None,
                    "failure_stage": "execution",
                    "failure_code": reason_code,
                }
                persisted = self._append_event(event)
                self._terminal[call_id] = persisted
                self._pending.pop(call_id, None)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            payload = summarize_execution_events(self._events)
            payload["run_id"] = self.run_id
            return payload

    def write_summary(self) -> dict[str, Any]:
        with self._lock:
            payload = self.summary()
            try:
                _atomic_write_json(self.summary_path, payload)
            except Exception as exc:
                raise ExecutionPersistenceError("execution_summary_write_failed") from exc
            return payload

    def close(self) -> dict[str, Any]:
        with self._lock:
            if not self._closed:
                self.interrupt_pending()
                self._closed = True
            return self.write_summary()


__all__ = [
    "EXECUTION_EVENT_PROTOCOL",
    "ExecutionCallHandle",
    "ExecutionEventError",
    "ExecutionPersistenceError",
    "RunExecutionLedger",
    "summarize_execution_events",
]
