"""Run one frozen SGAR method across the complete official GAIA validation split."""
from __future__ import annotations

import argparse
import asyncio
import importlib
import json
from pathlib import Path
import shutil
import sys
import time
import uuid
from typing import Any

from evaluation.gaia.adapter import AgentVisibleTask, EvaluatorRecord, GaiaTaskAdapter


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _final_output(run_root: Path) -> tuple[Path | None, str]:
    path = next((item for item in (run_root / "final_output.md", run_root / "final_output.txt") if item.is_file()), None)
    return path, path.read_text(encoding="utf-8") if path else ""


def _failure_class(status: str, error: dict[str, Any] | None, score: float) -> str | None:
    if score >= 1.0:
        return None
    if status == "task_timeout":
        return "timeout"
    if error:
        error_type = str(error.get("type") or "unknown").casefold()
        if "rate" in error_type or "limit" in str(error.get("message") or "").casefold():
            return "provider_rate_limit"
        if "timeout" in error_type or "timeout" in str(error.get("message") or "").casefold():
            return "timeout"
        if "connection" in error_type or "transport" in error_type:
            return "provider_transport"
        return "runner_exception"
    if status in {"provider_rate_limit", "provider_transport", "runner_exception"}:
        return status
    if status == "structured_failure":
        return status
    return "scorer_mismatch"


def _structured_failure_class(run_root: Path) -> str | None:
    events = run_root / "run_events.jsonl"
    if events.is_file():
        for event in reversed(_jsonl(events)):
            if event.get("event_type") == "controller_session_failed":
                code = event.get("failure_code")
                if isinstance(code, str) and code:
                    return code
    report = run_root / "experiment_report.md"
    if not report.is_file():
        return None
    text = report.read_text(encoding="utf-8", errors="replace")
    mappings = (
        ("required_input_missing", "plan_compiler_required_input_missing"),
        ("planner_response_schema_invalid", "planner_response_schema_invalid"),
        ("NodeUnrecoverableError", "node_unrecoverable"),
    )
    return next((label for marker, label in mappings if marker in text), None)


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_phase_records(
    task_root: Path,
    *,
    experiment_id: str,
    trial_id: str,
    task_id: str,
    level: int | None,
    method_id: str,
    environment_started_at: str,
    environment_ready_at: str | None,
    environment_seconds: float | None,
    agent_started_at: str | None,
    agent_finished_at: str | None,
    agent_seconds: float | None,
    verifier_started_at: str | None,
    verifier_finished_at: str | None,
    verifier_seconds: float | None,
    trial_started_at: str,
    trial_finished_at: str,
    e2e_seconds: float,
    timeout_sec: float | None,
    status: str,
    termination_reason: str,
    failure_class: str | None,
    failure: dict[str, Any] | None,
    reward: float | None,
    cost: dict[str, Any],
    execution: dict[str, Any],
    final_path: Path | None,
    verifier_record: dict[str, Any],
) -> None:
    """Persist canonical timing sidecars without changing native RARE logs."""
    _write_json(task_root / "environment_manifest.json", {
        "protocol": "sgar-gaia-environment-v1",
        "task_id": task_id,
        "environment_setup_started_at": environment_started_at,
        "environment_ready_at": environment_ready_at,
        "environment_setup_seconds": environment_seconds,
        "environment_mode": "host_native_gaia",
        "environment_failure": failure if failure_class == "infrastructure_failure" else None,
    })
    _write_json(task_root / "verifier_record.json", verifier_record)
    _write_json(task_root / "artifact_manifest.json", {
        "protocol": "sgar-gaia-artifacts-v1",
        "task_id": task_id,
        "final_output_path": str(final_path) if final_path else None,
        "native_cost_summary": str(task_root / "cost_summary.json") if (task_root / "cost_summary.json").is_file() else None,
        "native_execution_summary": str(task_root / "execution_summary.json") if (task_root / "execution_summary.json").is_file() else None,
    })
    _write_json(task_root / "trial_record.json", {
        "protocol": "sgar-gaia-trial-record-v1",
        "experiment_id": experiment_id,
        "trial_id": trial_id,
        "benchmark_id": "gaia/2023-validation",
        "benchmark_version": "2023",
        "task_id": task_id,
        "task_level": level,
        "method_id": method_id,
        "harness_version": "rare-tf-gaia-runner-v1",
        "trial_started_at": trial_started_at,
        "trial_finished_at": trial_finished_at,
        "environment_setup_seconds": environment_seconds,
        "agent_start": agent_started_at,
        "agent_end": agent_finished_at,
        "agent_execution_seconds": agent_seconds,
        "verifier_start": verifier_started_at,
        "verifier_end": verifier_finished_at,
        "verifier_seconds": verifier_seconds,
        "e2e_wall_clock_seconds": e2e_seconds,
        "timeout_limit_seconds": timeout_sec,
        "timeout_scope": "agent_phase_only" if timeout_sec is not None else "none_gaia_official_timeout",
        "status": status,
        "termination_reason": termination_reason,
        "failure_class": failure_class,
        "failure": failure,
        "official_reward": reward,
        "cost_summary": cost,
        "execution_summary": execution,
        "phase_boundary_policy": {
            "environment_setup_excluded_from_agent": True,
            "verifier_excluded_from_agent": True,
            "cleanup_excluded_from_agent": True,
            "rare_owned_runtime_preparation_in_agent": True,
        },
    })


def _prepare_task_inputs(
    *,
    row: dict[str, Any],
    dataset_root: Path,
    output_root: Path,
    sgar_root: Path,
    invocation_module: Any,
    trial_id: str,
) -> dict[str, Any]:
    """Prepare one GAIA task and return phase metadata without starting RARE."""
    task_id = str(row["task_id"])
    task_root = output_root / "tasks" / task_id
    input_root = output_root / "inputs" / task_id
    environment_started_at = _utc_now()
    environment_started_mono = time.monotonic()
    try:
        task_root.mkdir(parents=True, exist_ok=False)
        input_root.mkdir(parents=True, exist_ok=False)
        raw_names = row.get("file_name") or []
        raw_names = [raw_names] if isinstance(raw_names, str) else list(raw_names)
        names = [str(name).removeprefix("2023/validation/") for name in raw_names]
        for name, relative_name in zip(raw_names, names):
            source = (dataset_root / "raw/2023/validation" / relative_name).resolve()
            if dataset_root.resolve() not in source.parents or not source.is_file():
                raise ValueError("gaia_attachment_outside_frozen_snapshot")
            target = input_root / relative_name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        task = AgentVisibleTask(task_id, str(row["Question"]), int(row["Level"]), tuple(names), "2023_validation")
        evaluator = EvaluatorRecord(task_id, None, row["Final answer"], "2023_validation")
        adapter = GaiaTaskAdapter(dataset_root=input_root, split="2023_validation")
        prepared = invocation_module.prepare_task_invocation(
            query=task.question,
            input_specs=tuple(invocation_module.InputSourceSpec(logical_name=name, source_path=input_root / name) for name in names),
            run_dir=task_root,
            request_id=f"gaia-v1-{task_id}-{trial_id}",
            allowed_public_input_roots=(input_root,),
            project_root=sgar_root,
        )
    except Exception as exc:
        task_root.mkdir(parents=True, exist_ok=True)
        return {
            "task_root": task_root,
            "input_root": input_root,
            "environment_started_at": environment_started_at,
            "environment_ready_at": None,
            "environment_seconds": time.monotonic() - environment_started_mono,
            "error": {"type": type(exc).__name__, "message": str(exc)},
        }
    return {
        "task_root": task_root,
        "input_root": input_root,
        "task": task,
        "evaluator": evaluator,
        "adapter": adapter,
        "prepared": prepared,
        "environment_started_at": environment_started_at,
        "environment_ready_at": _utc_now(),
        "environment_seconds": time.monotonic() - environment_started_mono,
        "error": None,
    }


async def run_validation(
    dataset_root: Path,
    sgar_root: Path,
    experiment_manifest: Path,
    output_root: Path,
    *,
    config_path: Path | None = None,
    task_timeout_sec: float | None = None,
    task_ids: set[str] | None = None,
    max_tasks: int | None = None,
    network_policy_mode: str = "disabled",
    diagnostic_allow_manifest_drift: bool = False,
) -> dict[str, Any]:
    manifest = _json(experiment_manifest)
    if manifest.get("status") != "FROZEN" or not (manifest.get("freeze_gate") or {}).get("passed"):
        raise ValueError("gaia_experiment_manifest_not_frozen")
    sys.path.insert(0, str(sgar_root.resolve()))
    identity_checker = importlib.import_module("evaluation.gaia.check_manifest_identity")
    manifest_identity = identity_checker.check_identity(
        sgar_root.resolve(), experiment_manifest.resolve(), Path(__file__).resolve().parent
    )
    if not manifest_identity["ready_for_exact_manifest_run"] and not diagnostic_allow_manifest_drift:
        raise ValueError(
            "gaia_experiment_manifest_identity_mismatch:"
            + ",".join(manifest_identity["mismatches"])
        )
    if not manifest_identity["ready_for_exact_manifest_run"] and diagnostic_allow_manifest_drift:
        if max_tasks not in {0, 1} or (max_tasks == 1 and (not task_ids or len(task_ids) != 1)):
            raise ValueError("gaia_manifest_drift_diagnostic_requires_one_explicit_task")
    dataset_manifest = _json(dataset_root / "dataset_manifest.json")
    if dataset_manifest.get("task_count") != 165 or not dataset_manifest.get("immutable"):
        raise ValueError("gaia_dataset_snapshot_not_frozen")
    visible_rows = _jsonl(dataset_root / "views/agent_visible.jsonl")
    evaluator_by_id = {row["task_id"]: row for row in _jsonl(dataset_root / "views/evaluator_only.jsonl")}
    if len(visible_rows) != 165 or set(evaluator_by_id) != {row["task_id"] for row in visible_rows}:
        raise ValueError("gaia_dataset_views_identity_mismatch")

    sgar_main = importlib.import_module("sgar_mvp.main")
    invocation_module = importlib.import_module("sgar_mvp.src.task_invocation")
    resolved_config = (config_path or (sgar_root / "sgar_mvp/config.json")).resolve()
    config = sgar_main.load_config(str(resolved_config), resolve_secrets=True)
    if config is None:
        raise ValueError("gaia_sgar_config_missing")
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "manifest_identity_audit.json").write_text(
        json.dumps(manifest_identity, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    results: list[dict[str, Any]] = []
    started = time.monotonic()
    selected_rows = [row for row in visible_rows if task_ids is None or str(row["task_id"]) in task_ids]
    if max_tasks is not None:
        selected_rows = selected_rows[:max_tasks]
    experiment_id = str(manifest.get("experiment_id") or "rare-tf-gaia")
    for index, row in enumerate(selected_rows):
        task_id = str(row["task_id"])
        trial_id = str(uuid.uuid4())
        trial_started_mono = time.monotonic()
        trial_started_at = _utc_now()
        prep = _prepare_task_inputs(
            row={**row, "Final answer": evaluator_by_id[task_id]["Final answer"]},
            dataset_root=dataset_root,
            output_root=output_root,
            sgar_root=sgar_root,
            invocation_module=invocation_module,
            trial_id=trial_id,
        )
        task_root = prep["task_root"]
        environment_started_at = prep["environment_started_at"]
        environment_ready_at = prep["environment_ready_at"]
        environment_seconds = prep["environment_seconds"]
        if prep["error"] is not None:
            trial_finished_at = _utc_now()
            e2e_seconds = time.monotonic() - trial_started_mono
            _write_phase_records(
                task_root,
                experiment_id=experiment_id,
                trial_id=trial_id,
                task_id=task_id,
                level=int(row["Level"]),
                method_id=manifest["method_id"],
                environment_started_at=environment_started_at,
                environment_ready_at=environment_ready_at,
                environment_seconds=environment_seconds,
                agent_started_at=None,
                agent_finished_at=None,
                agent_seconds=None,
                verifier_started_at=None,
                verifier_finished_at=None,
                verifier_seconds=None,
                trial_started_at=trial_started_at,
                trial_finished_at=trial_finished_at,
                e2e_seconds=e2e_seconds,
                timeout_sec=task_timeout_sec,
                status="infrastructure_failure",
                termination_reason="environment_setup_failure",
                failure_class="infrastructure_failure",
                failure=prep["error"],
                reward=None,
                cost={},
                execution={},
                final_path=None,
                verifier_record={
                    "protocol": "sgar-gaia-verifier-v1",
                    "task_id": task_id,
                    "status": "not_started",
                    "reason": "environment_setup_failure",
                },
            )
            results.append({
                "task_id": task_id,
                "level": int(row["Level"]),
                "ordinal": index + 1,
                "method_id": manifest["method_id"],
                "status": "infrastructure_failure",
                "failure": prep["error"],
                "failure_taxonomy": "infrastructure_failure",
                "score": 0.0,
                "cost_usd": None,
                "model_calls": 0,
                "tokens": {},
                "agent_delegations": 0,
                "tool_calls": 0,
                "environment_setup_seconds": environment_seconds,
                "agent_execution_seconds": None,
                "verifier_seconds": None,
                "e2e_wall_clock_seconds": e2e_seconds,
                "timeout_limit_seconds": task_timeout_sec,
                "trial_id": trial_id,
            })
            continue
        task = prep["task"]
        evaluator = prep["evaluator"]
        adapter = prep["adapter"]
        prepared = prep["prepared"]
        local_config = dict(config)
        local_config["runtime_settings"] = {
            **dict(config.get("runtime_settings") or {}),
            "output_root": str(task_root),
            "temporary_directory": str(task_root / "runtime_tmp"),
            "pip_cache_directory": str(task_root / "pip_cache"),
        }
        error = None
        agent_started_at = _utc_now()
        agent_started_mono = time.monotonic()
        agent_finished_at = None
        agent_seconds = None
        timeout_triggered = False
        try:
            pipeline_call = sgar_main.run_pipeline(
                local_config, task.question, str(task_root), str(task_root / "experiment_report.md"),
                run_id=f"gaia-v1-{task_id}", task_invocation=prepared,
                max_generation_requests=(
                    None if manifest["budget"]["max_generation_requests_per_task"] is None
                    else int(manifest["budget"]["max_generation_requests_per_task"])
                ),
                max_embedding_requests=(
                    None if manifest["budget"]["max_embedding_requests_per_task"] is None
                    else int(manifest["budget"]["max_embedding_requests_per_task"])
                ),
                network_policy_mode=network_policy_mode,
            )
            if task_timeout_sec is None:
                status = await pipeline_call
            else:
                status = await asyncio.wait_for(pipeline_call, timeout=task_timeout_sec)
        except asyncio.TimeoutError:
            timeout_triggered = True
            status = "task_timeout"
            error = {"type": "TaskTimeoutError", "message": f"agent phase exceeded {task_timeout_sec}s"}
        except Exception as exc:
            status = "runner_exception"
            error = {"type": type(exc).__name__, "message": str(exc)}
        finally:
            agent_finished_at = _utc_now()
            agent_seconds = time.monotonic() - agent_started_mono
        final_path, final = _final_output(task_root)
        verifier_started_at = _utc_now()
        verifier_started_mono = time.monotonic()
        evaluation = adapter.evaluate(task, evaluator, final)
        verifier_finished_at = _utc_now()
        verifier_seconds = time.monotonic() - verifier_started_mono
        trial_finished_at = _utc_now()
        e2e_seconds = time.monotonic() - trial_started_mono
        cost = _json(task_root / "cost_summary.json") if (task_root / "cost_summary.json").exists() else {}
        execution = _json(task_root / "execution_summary.json") if (task_root / "execution_summary.json").exists() else {}
        failure_taxonomy = _structured_failure_class(task_root) if str(status) == "structured_failure" else None
        reward = float(evaluation["scorer"]["score"])
        failure_taxonomy = failure_taxonomy or _failure_class(str(status), error, reward)
        termination_reason = "task_timeout" if timeout_triggered else ("finished" if reward > 0 else str(status))
        verifier_record = {
            "protocol": "sgar-gaia-verifier-v1",
            "task_id": task_id,
            "status": "ok",
            "reward": reward,
            "scorer": evaluation,
            "verifier_started_at": verifier_started_at,
            "verifier_finished_at": verifier_finished_at,
            "verifier_seconds": verifier_seconds,
        }
        _write_phase_records(
            task_root,
            experiment_id=experiment_id,
            trial_id=trial_id,
            task_id=task_id,
            level=task.level,
            method_id=manifest["method_id"],
            environment_started_at=environment_started_at,
            environment_ready_at=environment_ready_at,
            environment_seconds=environment_seconds,
            agent_started_at=agent_started_at,
            agent_finished_at=agent_finished_at,
            agent_seconds=agent_seconds,
            verifier_started_at=verifier_started_at,
            verifier_finished_at=verifier_finished_at,
            verifier_seconds=verifier_seconds,
            trial_started_at=trial_started_at,
            trial_finished_at=trial_finished_at,
            e2e_seconds=e2e_seconds,
            timeout_sec=task_timeout_sec,
            status=str(status),
            termination_reason=termination_reason,
            failure_class=failure_taxonomy,
            failure=error,
            reward=reward,
            cost=cost,
            execution=execution,
            final_path=final_path,
            verifier_record=verifier_record,
        )
        result = {
            "task_id": task_id,
            "level": task.level,
            "ordinal": index + 1,
            "method_id": manifest["method_id"],
            "experiment_manifest_sha256": manifest["manifest_sha256"],
            "resource_pool_hash": manifest_identity["checks"]["resources.effective_pool_sha256"]["current"],
            "declared_resource_pool_hash": manifest["resources"]["effective_pool_sha256"],
            "formal_comparable": manifest_identity["ready_for_exact_manifest_run"],
            "status": str(status),
            "raw_final_output_path": str(final_path) if final_path else None,
            "model_answer": evaluation["answer"],
            "score": evaluation["scorer"]["score"],
            "failure": error,
            "failure_taxonomy": failure_taxonomy,
            "model_calls": cost.get("started_call_count", 0),
            "tokens": cost.get("token_usage", {}),
            "cost_usd": cost.get("observed_total_model_cost_usd"),
            "agent_delegations": execution.get("controller_session_count", 0),
            "tool_calls": execution.get("by_resource_type", {}).get("Tool", 0),
            "environment_setup_seconds": environment_seconds,
            "agent_execution_seconds": agent_seconds,
            "verifier_seconds": verifier_seconds,
            "e2e_wall_clock_seconds": e2e_seconds,
            "timeout_limit_seconds": task_timeout_sec,
            "trial_id": trial_id,
        }
        (task_root / "benchmark_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        results.append(result)

    levels = {level: [row for row in results if row["level"] == level] for level in (1, 2, 3)}
    total_cost = sum(float(row["cost_usd"] or 0) for row in results)
    summary = {
        "protocol": "sgar-gaia-validation-results-v1",
        "experiment_manifest_sha256": manifest["manifest_sha256"],
        "formal_comparable": manifest_identity["ready_for_exact_manifest_run"],
        "manifest_identity_mismatches": manifest_identity["mismatches"],
        "task_count": len(results),
        "accuracy": sum(row["score"] for row in results) / max(len(results), 1),
        "level_accuracy": {
            f"L{level}": sum(row["score"] for row in rows) / max(len(rows), 1)
            for level, rows in levels.items()
        },
        "total_cost_usd": total_cost,
        "mean_cost_usd": total_cost / max(len(results), 1),
        "model_calls": sum(row["model_calls"] for row in results),
        "agent_delegations": sum(row["agent_delegations"] for row in results),
        "tool_calls": sum(row["tool_calls"] for row in results),
        "input_tokens": sum((row["tokens"] or {}).get("input_tokens", 0) for row in results),
        "output_tokens": sum((row["tokens"] or {}).get("output_tokens", 0) for row in results),
        "latency_seconds": time.monotonic() - started,
        "failure_taxonomy": {
            key: sum(1 for row in results if row["failure_taxonomy"] == key)
            for key in sorted({row["failure_taxonomy"] for row in results if row["failure_taxonomy"]})
        },
        "results": results,
    }
    (output_root / "validation_results.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--sgar-root", type=Path, required=True)
    parser.add_argument("--experiment-manifest", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument(
        "--task-timeout-sec",
        type=float,
        default=None,
        help="Optional local cap for the RARE agent phase only; GAIA has no official task wall timeout.",
    )
    parser.add_argument("--task-id", action="append", dest="task_ids")
    parser.add_argument("--max-tasks", type=int, default=None)
    parser.add_argument(
        "--network-policy", choices=("disabled", "declared"), default="disabled",
        help="Permit network access only for Tools that declare it.",
    )
    parser.add_argument(
        "--diagnostic-allow-manifest-drift", action="store_true",
        help="Label a single-case diagnostic as non-comparable when the frozen manifest drifts.",
    )
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run_validation(
        args.dataset_root.resolve(),
        args.sgar_root.resolve(),
        args.experiment_manifest.resolve(),
        args.output_root.resolve(),
        config_path=args.config.resolve() if args.config else None,
        task_timeout_sec=args.task_timeout_sec,
        task_ids=set(args.task_ids) if args.task_ids else None,
        max_tasks=args.max_tasks,
        network_policy_mode=args.network_policy,
        diagnostic_allow_manifest_drift=args.diagnostic_allow_manifest_drift,
    )), ensure_ascii=False, indent=2))
