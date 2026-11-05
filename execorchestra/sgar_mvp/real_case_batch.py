"""Process-isolated supervisor for user-approved SGAR real-case acceptance runs."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Sequence

from pydantic import Field, field_validator, model_validator

from .src.atomic_io import temporary_sibling_path
from .src.pipeline_control import FrozenContract, canonical_json_bytes, canonical_sha256
from .src.portability_audit import audit_run_portability
from .src.batch_supervisor import (
    BatchSupervisorError,
    launch_supervised_case,
    verify_case_cost,
    write_custom_launcher_evidence,
)
from .src.secret_policy import FORMAL_PROVIDER_CREDENTIAL_ENV_ALLOWLIST
from .src.run_workspace import (
    RunManifestStore,
    RunWorkspaceError,
    create_run_workspace,
    sanitized_run_failure,
    validate_run_manifest,
)
from .src.task_invocation import resolve_task_request


REAL_CASE_SUITE_PROTOCOL = "sgar-real-case-suite-v1"
REAL_CASE_BATCH_PROTOCOL = "sgar-real-case-batch-v2"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class RealCaseBatchError(RuntimeError):
    pass


class RealCaseSpec(FrozenContract):
    case_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    request_manifest: str = Field(min_length=1)
    network_policy: Literal["disabled", "declared"] = "disabled"
    enabled: bool = True
    timeout_seconds: int = Field(default=7200, ge=60, le=86400)

    @field_validator("case_id")
    @classmethod
    def _case_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for char in normalized):
            raise ValueError("real_case_id_invalid")
        return normalized


class RealCaseSuite(FrozenContract):
    protocol: Literal[REAL_CASE_SUITE_PROTOCOL] = REAL_CASE_SUITE_PROTOCOL
    suite_id: str = Field(min_length=1)
    cases: tuple[RealCaseSpec, ...]
    suite_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "RealCaseSuite":
        identities = [item.case_id for item in self.cases]
        if len(identities) != len(set(identities)):
            raise ValueError("real_case_id_duplicate")
        if not identities:
            raise ValueError("real_case_suite_empty")
        expected = canonical_sha256(self.model_dump(mode="python", exclude={"suite_sha256"}))
        if self.suite_sha256 and self.suite_sha256 != expected:
            raise ValueError("real_case_suite_sha256_mismatch")
        object.__setattr__(self, "suite_sha256", expected)
        return self


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = temporary_sibling_path(path)
    try:
        with temporary.open("xb") as handle:
            handle.write(canonical_json_bytes(payload))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_real_case_suite(path: str | Path) -> tuple[RealCaseSuite, dict[str, Path]]:
    source = Path(path).resolve()
    suite_root = source.parent
    try:
        payload = json.loads(source.read_text(encoding="utf-8-sig", errors="strict"))
        suite = RealCaseSuite.model_validate(payload)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise RealCaseBatchError("real_case_suite_invalid") from exc
    manifests: dict[str, Path] = {}
    for case in suite.cases:
        manifest = Path(case.request_manifest)
        if not manifest.is_absolute():
            manifest = source.parent / manifest
        manifests[case.case_id] = manifest.resolve()
        if case.enabled:
            resolve_task_request(
                request_manifest=manifests[case.case_id],
                query=None,
                query_file=None,
                query_file_encoding="utf-8-sig",
                named_inputs=(),
                input_manifest=None,
                allowed_public_input_roots=(suite_root,),
                project_root=PROJECT_ROOT,
            )
    return suite, manifests


def _new_batch_root(output_root: Path) -> tuple[str, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    batch_id = uuid.uuid4().hex
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = output_root / f"{timestamp}_{batch_id[:12]}"
    target.mkdir(exist_ok=False)
    return batch_id, target


CaseLauncher = Callable[[Sequence[str], int], int]


def _parse_total_cost_limit(value: Decimal | str | float | None, *, dry_run: bool) -> Decimal | None:
    if dry_run and value is None:
        return None
    if value is None:
        raise RealCaseBatchError("max_total_cost_usd_required")
    try:
        limit = Decimal(str(value))
    except InvalidOperation as exc:
        raise RealCaseBatchError("max_total_cost_usd_invalid") from exc
    if not limit.is_finite() or limit <= 0:
        raise RealCaseBatchError("max_total_cost_usd_invalid")
    return limit


def _cleanup_run_containers(run_id: str) -> dict[str, Any]:
    """Remove only containers bearing the exact child run label."""
    try:
        found = subprocess.run(
            ["docker", "ps", "-aq", "--filter", f"label=sgar.run={run_id}"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=15,
            text=True,
            encoding="utf-8",
            errors="strict",
        )
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return {"checked": False, "residual_count": None, "cleanup_verified": False}
    identities = [line.strip() for line in found.stdout.splitlines() if line.strip()]
    if identities:
        subprocess.run(
            ["docker", "rm", "-f", *identities],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=30,
        )
    verify = subprocess.run(
        ["docker", "ps", "-aq", "--filter", f"label=sgar.run={run_id}"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=15,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    remaining = [line for line in verify.stdout.splitlines() if line.strip()]
    return {
        "checked": True,
        "residual_count": len(remaining),
        "cleanup_verified": not remaining,
    }


def _terminal_manifest_dirs(case_root: Path) -> list[Path]:
    return sorted(
        path.parent
        for path in case_root.glob("*/run_manifest.json")
        if path.is_file()
    )


def _write_supervisor_terminal_manifest(
    *,
    case_root: Path,
    case: RealCaseSpec,
    suite: RealCaseSuite,
    request_manifest_sha256: str,
    exit_code: int,
) -> Path:
    """Guarantee a terminal record when the isolated child cannot do so."""

    workspace = create_run_workspace(output_root=case_root)
    interrupted = exit_code == 124
    store = RunManifestStore(
        run_dir=workspace.path(),
        run_id=workspace.run_id,
        request_id=case.case_id,
        invocation_sha256=canonical_sha256(
            {
                "protocol": "sgar-task-invocation-v1",
                "case_id": case.case_id,
                "suite_sha256": suite.suite_sha256,
                "request_manifest_sha256": request_manifest_sha256,
                "supervisor_terminal": True,
            }
        ),
    )
    store.update_phase(
        "supervisor",
        "process_timeout" if interrupted else "process_exit_without_terminal",
    )
    store.update_identities(
        {
            "real_case_suite_sha256": suite.suite_sha256,
            "request_manifest_sha256": request_manifest_sha256,
            "supervisor_terminal": True,
        }
    )
    store.terminal(
        "interrupted" if interrupted else "framework_failure",
        primary_failure=sanitized_run_failure(
            responsibility="interrupted" if interrupted else "framework",
            failure_stage="case_process",
            failure_code=(
                "case_process_timeout"
                if interrupted
                else "case_process_exited_without_terminal_manifest"
            ),
        ),
        framework_source_clean=None,
    )
    return workspace.path()


def run_real_case_batch(
    *,
    suite_path: str | Path,
    output_root: str | Path,
    config_path: str | Path,
    python_executable: str = sys.executable,
    launcher: Callable[[Sequence[str], int], int] | None = None,
    dry_run: bool = False,
    require_production_conformance: bool = True,
    max_total_cost_usd: Decimal | str | float | None = None,
) -> dict[str, Any]:
    total_cost_limit = _parse_total_cost_limit(max_total_cost_usd, dry_run=dry_run)
    suite, manifests = load_real_case_suite(suite_path)
    suite_root = Path(suite_path).resolve().parent
    batch_id, batch_root = _new_batch_root(Path(output_root).resolve())
    records: list[dict[str, Any]] = []
    active_cases = [item for item in suite.cases if item.enabled]
    observed_total = Decimal("0")
    cost_evidence_complete = True
    budget_stop_reason = ""
    blocked_case_ids: list[str] = []

    for case in suite.cases:
        if not case.enabled:
            records.append(
                {
                    "case_id": case.case_id,
                    "category": case.category,
                    "enabled": False,
                    "status": "disabled",
                }
            )
            continue
        request_manifest = manifests[case.case_id]
        resolved_request = resolve_task_request(
            request_manifest=request_manifest,
            query=None,
            query_file=None,
            query_file_encoding="utf-8-sig",
            named_inputs=(),
            input_manifest=None,
            allowed_public_input_roots=(suite_root,),
            project_root=PROJECT_ROOT,
        )
        request_manifest_sha256 = resolved_request.request_source_sha256
        if dry_run:
            records.append(
                {
                    "case_id": case.case_id,
                    "category": case.category,
                    "enabled": True,
                    "status": "validated",
                    "network_policy": case.network_policy,
                    "request_manifest_sha256": request_manifest_sha256,
                }
            )
            continue

        if budget_stop_reason or (
            total_cost_limit is not None and observed_total >= total_cost_limit
        ):
            if not budget_stop_reason:
                budget_stop_reason = "max_total_cost_reached"
            blocked_case_ids.append(case.case_id)
            records.append(
                {
                    "case_id": case.case_id,
                    "category": case.category,
                    "enabled": True,
                    "launched": False,
                    "status": "not_started",
                    "blocked_reason": budget_stop_reason,
                    "request_manifest_sha256": request_manifest_sha256,
                }
            )
            continue

        case_root = batch_root / "cases" / case.case_id
        case_root.mkdir(parents=True, exist_ok=False)
        command = [
            python_executable,
            "-m",
            "sgar_mvp.main",
            "--request-manifest",
            str(request_manifest),
            "--public-input-root",
            str(suite_root),
            "--config",
            str(Path(config_path).resolve()),
            "--output-root",
            str(case_root),
            "--network-policy",
            case.network_policy,
        ]
        if launcher is None:
            secret_values = tuple(
                os.environ.get(name, "")
                for name in FORMAL_PROVIDER_CREDENTIAL_ENV_ALLOWLIST
                if os.environ.get(name)
            )
            try:
                process_result = launch_supervised_case(
                    command,
                    timeout_seconds=case.timeout_seconds,
                    case_root=case_root,
                    secret_values=secret_values,
                    host_roots=(Path(suite_path).resolve().parent, Path(config_path).resolve().parent),
                )
            except BatchSupervisorError:
                process_result = write_custom_launcher_evidence(case_root, exit_code=125)
        else:
            process_result = write_custom_launcher_evidence(
                case_root,
                exit_code=int(launcher(command, case.timeout_seconds)),
            )
        exit_code = process_result.exit_code

        run_dirs = _terminal_manifest_dirs(case_root)
        supervisor_terminal_created = False
        if not run_dirs:
            run_dirs = [
                _write_supervisor_terminal_manifest(
                    case_root=case_root,
                    case=case,
                    suite=suite,
                    request_manifest_sha256=request_manifest_sha256,
                    exit_code=exit_code,
                )
            ]
            supervisor_terminal_created = True
        record: dict[str, Any] = {
            "case_id": case.case_id,
            "category": case.category,
            "enabled": True,
            "launched": True,
            "network_policy": case.network_policy,
            "process_exit_code": exit_code,
            "terminal_manifest_count": len(run_dirs),
            "supervisor_terminal_created": supervisor_terminal_created,
            "supervisor_process_sha256": process_result.process_sha256,
            "supervisor_stdout": dict(process_result.stdout),
            "supervisor_stderr": dict(process_result.stderr),
            "supervisor_output_limited": process_result.output_limited,
            "supervisor_cleanup_verified": process_result.cleanup_verified,
        }
        if len(run_dirs) == 1:
            try:
                validation = validate_run_manifest(
                    run_dirs[0],
                    require_production_conformance=require_production_conformance,
                )
                record.update(
                    {
                        "status": validation["status"],
                        "child_manifest_status": validation["status"],
                        "run_id": validation["run_id"],
                        "run_manifest_sha256": validation["manifest_sha256"],
                        "manifest_valid": True,
                        "ledger_complete": validation["complete"],
                    }
                )
                if launcher is None:
                    container_cleanup = _cleanup_run_containers(validation["run_id"])
                else:
                    container_cleanup = {
                        "checked": False,
                        "residual_count": 0,
                        "cleanup_verified": True,
                    }
                record["container_cleanup"] = container_cleanup
                if not container_cleanup["cleanup_verified"]:
                    record.update(
                        {
                            "status": "framework_failure",
                            "failure_code": "case_container_cleanup_unverified",
                        }
                    )
                try:
                    cost_evidence = verify_case_cost(
                        run_dirs[0], expected_run_id=validation["run_id"]
                    )
                    record["cost_evidence"] = cost_evidence
                    observed_total += Decimal(
                        cost_evidence["observed_total_model_cost_usd"]
                    )
                except BatchSupervisorError as exc:
                    cost_evidence_complete = False
                    budget_stop_reason = "case_cost_evidence_incomplete"
                    record["cost_evidence"] = {
                        "valid": False,
                        "failure_code": exc.failure_code,
                    }
                if (
                    exit_code not in {0, 124}
                    and validation["status"]
                    not in {"framework_failure", "interrupted"}
                ):
                    record.update(
                        {
                            "status": "framework_failure",
                            "failure_code": "process_manifest_status_mismatch",
                            "process_status_consistent": False,
                        }
                    )
                else:
                    record["process_status_consistent"] = True
            except RunWorkspaceError as exc:
                record.update(
                    {
                        "status": "framework_failure",
                        "manifest_valid": False,
                        "failure_code": str(exc),
                    }
                )
        else:
            record.update(
                {
                    "status": "framework_failure",
                    "manifest_valid": False,
                    "failure_code": "terminal_manifest_count_invalid",
                }
            )
        records.append(record)
        _atomic_json(
            batch_root / "batch_progress.json",
            {
                "protocol": REAL_CASE_BATCH_PROTOCOL,
                "batch_id": batch_id,
                "suite_sha256": suite.suite_sha256,
                "records": records,
            },
        )

    attempted = [item for item in records if item.get("launched") is True]
    terminal = [item for item in attempted if item.get("manifest_valid") is True]
    framework_failures = [
        item for item in attempted if item.get("status") == "framework_failure"
    ]
    research_failures = [
        item for item in attempted if item.get("status") == "research_failure"
    ]
    infrastructure_failures = [
        item for item in attempted if item.get("status") == "infrastructure_failure"
    ]
    budget_failures = [
        item for item in attempted if item.get("status") == "budget_failure"
    ]
    interrupted = [
        item for item in attempted if item.get("status") == "interrupted"
    ]
    unhandled_process_crashes = [
        item
        for item in attempted
        if item.get("supervisor_terminal_created") is True
        and item.get("status") == "framework_failure"
    ]
    projection = {
        "protocol": REAL_CASE_BATCH_PROTOCOL,
        "batch_id": batch_id,
        "suite_id": suite.suite_id,
        "suite_sha256": suite.suite_sha256,
        "dry_run": dry_run,
        "max_total_cost_usd": (
            format(total_cost_limit, ".12f") if total_cost_limit is not None else None
        ),
        "observed_total_model_cost_usd": format(observed_total, ".12f"),
        "cost_evidence_complete": cost_evidence_complete,
        "budget_stop_reason": budget_stop_reason,
        "blocked_case_ids": blocked_case_ids,
        "budget_overshoot_usd": (
            format(max(observed_total - total_cost_limit, Decimal("0")), ".12f")
            if total_cost_limit is not None
            else "0.000000000000"
        ),
        "configured_case_count": len(suite.cases),
        "enabled_case_count": len(active_cases),
        "attempted_case_count": 0 if dry_run else len(attempted),
        "terminal_run_manifest_count": 0 if dry_run else len(terminal),
        "framework_failure_count": 0 if dry_run else len(framework_failures),
        "research_failure_count": 0 if dry_run else len(research_failures),
        "infrastructure_failure_count": (
            0 if dry_run else len(infrastructure_failures)
        ),
        "budget_failure_count": 0 if dry_run else len(budget_failures),
        "interrupted_count": 0 if dry_run else len(interrupted),
        "supervisor_terminal_count": (
            0
            if dry_run
            else sum(bool(item.get("supervisor_terminal_created")) for item in attempted)
        ),
        "unhandled_process_crash_count": (
            0 if dry_run else len(unhandled_process_crashes)
        ),
        "all_terminal_manifests_valid": bool(
            dry_run or len(terminal) == len(attempted)
        ),
        "framework_valid": bool(dry_run or not framework_failures),
        "batch_valid": bool(
            dry_run
            or (
                not framework_failures
                and cost_evidence_complete
                and all(item.get("manifest_valid") is True for item in attempted)
            )
        ),
        "records": records,
    }
    private_secrets = tuple(
        os.environ.get(name, "")
        for name in FORMAL_PROVIDER_CREDENTIAL_ENV_ALLOWLIST
        if os.environ.get(name)
    )
    portability = audit_run_portability(
        batch_root,
        host_roots=(batch_root, Path(suite_path).resolve().parent, Path(config_path).resolve().parent),
        secret_values=private_secrets,
    )
    projection["batch_portability_audit"] = portability
    if not portability["valid"]:
        projection["batch_valid"] = False
        projection["framework_valid"] = False
    summary = {**projection, "summary_sha256": canonical_sha256(projection)}
    _atomic_json(batch_root / "real_case_batch_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument(
        "--config",
        default=str(Path(__file__).resolve().parent / "config.json"),
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-total-cost-usd")
    args = parser.parse_args()
    summary = run_real_case_batch(
        suite_path=args.suite,
        output_root=args.output_root,
        config_path=args.config,
        dry_run=args.dry_run,
        max_total_cost_usd=args.max_total_cost_usd,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2))
    raise SystemExit(0 if summary["batch_valid"] else 2)


if __name__ == "__main__":
    main()


__all__ = [
    "REAL_CASE_BATCH_PROTOCOL",
    "REAL_CASE_SUITE_PROTOCOL",
    "RealCaseBatchError",
    "RealCaseSpec",
    "RealCaseSuite",
    "load_real_case_suite",
    "run_real_case_batch",
]
