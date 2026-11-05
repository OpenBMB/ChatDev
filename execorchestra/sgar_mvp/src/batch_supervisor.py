"""Bounded, sanitized child-process capture and cross-case cost verification."""

from __future__ import annotations

import codecs
import hashlib
import json
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Sequence

from .atomic_io import temporary_sibling_path
from .model_accounting import (
    MODEL_COST_SUMMARY_PROTOCOL,
    SUPPORTED_MODEL_CALL_LEDGER_PROTOCOLS,
)
from .pipeline_control import canonical_json_bytes, canonical_sha256
from .secret_policy import sanitize_sensitive_text


SUPERVISOR_PROCESS_PROTOCOL = "sgar-supervisor-process-v1"
DEFAULT_SUPERVISOR_STREAM_LIMIT_BYTES = 32 * 1024 * 1024


class BatchSupervisorError(RuntimeError):
    def __init__(self, failure_code: str) -> None:
        super().__init__(failure_code)
        self.failure_code = failure_code


@dataclass(frozen=True)
class SupervisorProcessResult:
    exit_code: int
    timed_out: bool
    output_limited: bool
    cleanup_verified: bool
    stdout: Mapping[str, Any]
    stderr: Mapping[str, Any]
    process_sha256: str


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = temporary_sibling_path(path)
    with temporary.open("xb") as handle:
        handle.write(canonical_json_bytes(payload))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


class _BoundedCapture(threading.Thread):
    def __init__(
        self,
        *,
        stream,
        destination: Path,
        limit_bytes: int,
        limit_event: threading.Event,
        secret_values: Sequence[str],
        host_roots: Sequence[str],
    ) -> None:
        super().__init__(daemon=True)
        self.stream = stream
        self.destination = destination
        self.limit_bytes = limit_bytes
        self.limit_event = limit_event
        self.secret_values = tuple(secret_values)
        self.host_roots = tuple(host_roots)
        self.raw_bytes_observed = 0
        self.logged_bytes = 0
        self.utf8_valid = True
        self.sha256 = hashlib.sha256()
        self.sanitization_counts = {
            "secret": 0,
            "host_path": 0,
            "hidden": 0,
            "authorization": 0,
        }
        self.failure_code = ""

    def run(self) -> None:
        validator = codecs.getincrementaldecoder("utf-8")("strict")
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        tail = ""
        try:
            with self.destination.open("xb") as output:
                while True:
                    chunk = self.stream.read(65536)
                    if not chunk:
                        break
                    self.raw_bytes_observed += len(chunk)
                    try:
                        validator.decode(chunk, final=False)
                    except UnicodeDecodeError:
                        self.utf8_valid = False
                        validator = codecs.getincrementaldecoder("utf-8")("replace")
                    text = tail + decoder.decode(chunk, final=False)
                    if len(text) > 512:
                        emit, tail = text[:-512], text[-512:]
                    else:
                        emit, tail = "", text
                    if emit:
                        self._write_sanitized(output, emit)
                    if self.limit_event.is_set():
                        break
                tail += decoder.decode(b"", final=True)
                if tail and not self.limit_event.is_set():
                    self._write_sanitized(output, tail)
                output.flush()
                os.fsync(output.fileno())
        except Exception:
            self.failure_code = "supervisor_capture_failed"
            self.limit_event.set()

    def _write_sanitized(self, output, text: str) -> None:
        sanitized, counts = sanitize_sensitive_text(
            text,
            secret_values=self.secret_values,
            host_roots=self.host_roots,
        )
        for key, value in counts.items():
            self.sanitization_counts[key] += value
        payload = sanitized.encode("utf-8")
        remaining = self.limit_bytes - self.logged_bytes
        if len(payload) > remaining:
            if remaining > 0:
                bounded = payload[:remaining]
                output.write(bounded)
                self.sha256.update(bounded)
                self.logged_bytes += len(bounded)
            self.limit_event.set()
            return
        output.write(payload)
        self.sha256.update(payload)
        self.logged_bytes += len(payload)

    def evidence(self, locator: str) -> dict[str, Any]:
        return {
            "locator": locator,
            "byte_size": self.logged_bytes,
            "raw_bytes_observed": self.raw_bytes_observed,
            "sha256": self.sha256.hexdigest(),
            "utf8_valid": self.utf8_valid,
            "sanitization_counts": dict(self.sanitization_counts),
            "failure_code": self.failure_code,
        }


def _terminate_process_tree(process: subprocess.Popen[bytes], *, force: bool) -> None:
    if process.poll() is not None and not force:
        return
    if os.name == "nt":
        command = ["taskkill", "/PID", str(process.pid), "/T"]
        if force:
            command.append("/F")
        subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return
    try:
        os.killpg(process.pid, signal.SIGKILL if force else signal.SIGTERM)
    except (OSError, ProcessLookupError):
        pass


def launch_supervised_case(
    command: Sequence[str],
    *,
    timeout_seconds: int,
    case_root: str | Path,
    stream_limit_bytes: int = DEFAULT_SUPERVISOR_STREAM_LIMIT_BYTES,
    secret_values: Sequence[str] = (),
    host_roots: Sequence[str | Path] = (),
) -> SupervisorProcessResult:
    """Launch one isolated child with bounded, value-safe stream capture."""

    root = Path(case_root).resolve()
    stdout_path = root / "supervisor_stdout.log"
    stderr_path = root / "supervisor_stderr.log"
    if stream_limit_bytes <= 0:
        raise BatchSupervisorError("supervisor_stream_limit_invalid")
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
    try:
        process = subprocess.Popen(
            list(command),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=flags,
            start_new_session=os.name != "nt",
        )
    except OSError as exc:
        raise BatchSupervisorError("case_process_launch_failed") from exc
    assert process.stdout is not None and process.stderr is not None
    limit_event = threading.Event()
    private_roots = tuple(str(item) for item in host_roots) + (str(root),)
    stdout_capture = _BoundedCapture(
        stream=process.stdout,
        destination=stdout_path,
        limit_bytes=stream_limit_bytes,
        limit_event=limit_event,
        secret_values=secret_values,
        host_roots=private_roots,
    )
    stderr_capture = _BoundedCapture(
        stream=process.stderr,
        destination=stderr_path,
        limit_bytes=stream_limit_bytes,
        limit_event=limit_event,
        secret_values=secret_values,
        host_roots=private_roots,
    )
    stdout_capture.start()
    stderr_capture.start()
    deadline = time.monotonic() + timeout_seconds
    timed_out = False
    while process.poll() is None:
        if limit_event.wait(timeout=0.05):
            break
        if time.monotonic() >= deadline:
            timed_out = True
            break
    output_limited = limit_event.is_set()
    if process.poll() is None and (timed_out or output_limited):
        _terminate_process_tree(process, force=False)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _terminate_process_tree(process, force=True)
            process.wait(timeout=10)
    exit_code = int(process.wait())
    stdout_capture.join(timeout=10)
    stderr_capture.join(timeout=10)
    capture_incomplete = stdout_capture.is_alive() or stderr_capture.is_alive()
    cleanup_verified = process.poll() is not None and not capture_incomplete
    if capture_incomplete:
        output_limited = True
    if timed_out:
        exit_code = 124
    elif output_limited:
        exit_code = 126
    stdout_evidence = stdout_capture.evidence("supervisor_stdout.log")
    stderr_evidence = stderr_capture.evidence("supervisor_stderr.log")
    projection = {
        "protocol": SUPERVISOR_PROCESS_PROTOCOL,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "output_limited": output_limited,
        "cleanup_verified": cleanup_verified,
        "stdout": stdout_evidence,
        "stderr": stderr_evidence,
        "command_identity_sha256": canonical_sha256(
            {"executable_name": Path(str(command[0])).name, "argument_count": len(command)}
        ),
    }
    process_sha256 = canonical_sha256(projection)
    _atomic_json(root / "supervisor_process.json", {**projection, "process_sha256": process_sha256})
    return SupervisorProcessResult(
        exit_code=exit_code,
        timed_out=timed_out,
        output_limited=output_limited,
        cleanup_verified=cleanup_verified,
        stdout=stdout_evidence,
        stderr=stderr_evidence,
        process_sha256=process_sha256,
    )


def write_custom_launcher_evidence(case_root: str | Path, *, exit_code: int) -> SupervisorProcessResult:
    """Test/injected launcher adapter with the same public evidence shape."""
    root = Path(case_root).resolve()
    empty_sha = hashlib.sha256(b"").hexdigest()
    stream = {
        "locator": "supervisor_stdout.log",
        "byte_size": 0,
        "raw_bytes_observed": 0,
        "sha256": empty_sha,
        "utf8_valid": True,
        "sanitization_counts": {"secret": 0, "host_path": 0, "hidden": 0, "authorization": 0},
        "failure_code": "",
    }
    (root / "supervisor_stdout.log").write_bytes(b"")
    (root / "supervisor_stderr.log").write_bytes(b"")
    stderr = {**stream, "locator": "supervisor_stderr.log"}
    projection = {
        "protocol": SUPERVISOR_PROCESS_PROTOCOL,
        "exit_code": int(exit_code),
        "timed_out": int(exit_code) == 124,
        "output_limited": int(exit_code) == 126,
        "cleanup_verified": True,
        "stdout": stream,
        "stderr": stderr,
        "command_identity_sha256": canonical_sha256({"injected_launcher": True}),
    }
    process_sha256 = canonical_sha256(projection)
    _atomic_json(root / "supervisor_process.json", {**projection, "process_sha256": process_sha256})
    return SupervisorProcessResult(
        exit_code=int(exit_code),
        timed_out=int(exit_code) == 124,
        output_limited=int(exit_code) == 126,
        cleanup_verified=True,
        stdout=stream,
        stderr=stderr,
        process_sha256=process_sha256,
    )


def verify_case_cost(run_dir: str | Path, *, expected_run_id: str) -> dict[str, Any]:
    """Recompute observed cost from the append-only model ledger."""
    root = Path(run_dir).resolve()
    summary_path = root / "cost_summary.json"
    events_path = root / "model_calls.jsonl"
    if not summary_path.is_file() or not events_path.is_file():
        raise BatchSupervisorError("case_cost_evidence_missing")
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8-sig", errors="strict"))
        events = [
            json.loads(line)
            for line in events_path.read_text(encoding="utf-8-sig", errors="strict").splitlines()
            if line.strip()
        ]
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BatchSupervisorError("case_cost_evidence_invalid") from exc
    if summary.get("schema_version") != MODEL_COST_SUMMARY_PROTOCOL or summary.get("run_id") != expected_run_id:
        raise BatchSupervisorError("case_cost_summary_identity_invalid")
    if summary.get("provider_reported_cost_complete") is not True:
        raise BatchSupervisorError("case_cost_summary_incomplete")
    started: set[str] = set()
    finished: set[str] = set()
    total = Decimal("0")
    for event in events:
        if event.get("schema_version") not in SUPPORTED_MODEL_CALL_LEDGER_PROTOCOLS:
            raise BatchSupervisorError("case_model_ledger_protocol_invalid")
        identity = str(event.get("provider_attempt_id") or "")
        if event.get("event_type") == "model_call_started":
            started.add(identity)
        elif event.get("event_type") == "model_call_finished":
            finished.add(identity)
            value = event.get("actual_model_cost_usd")
            if value is None:
                raise BatchSupervisorError("case_cost_usage_incomplete")
            try:
                total += Decimal(str(value))
            except InvalidOperation as exc:
                raise BatchSupervisorError("case_cost_value_invalid") from exc
    if not started or started != finished:
        raise BatchSupervisorError("case_model_ledger_incomplete")
    try:
        supplied = Decimal(str(summary.get("observed_total_model_cost_usd")))
    except InvalidOperation as exc:
        raise BatchSupervisorError("case_cost_summary_total_invalid") from exc
    if total != supplied:
        raise BatchSupervisorError("case_cost_summary_ledger_mismatch")
    return {
        "valid": True,
        "observed_total_model_cost_usd": format(total, ".12f"),
        "provider_reported_cost_complete": True,
        "cost_summary_sha256": hashlib.sha256(summary_path.read_bytes()).hexdigest(),
        "model_ledger_sha256": hashlib.sha256(events_path.read_bytes()).hexdigest(),
        "finished_call_count": len(finished),
    }


__all__ = [
    "BatchSupervisorError",
    "DEFAULT_SUPERVISOR_STREAM_LIMIT_BYTES",
    "SUPERVISOR_PROCESS_PROTOCOL",
    "SupervisorProcessResult",
    "launch_supervised_case",
    "verify_case_cost",
    "write_custom_launcher_evidence",
]
