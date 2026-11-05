"""Fixed worker entrypoint: contract probes or the guarded real SGAR pipeline."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys


# The benchmark's own deadline and the run cost policy bound a formal trial.
# Transport request caps are opt-in diagnostics; they must not reject a valid
# case solely because it needed more retrieval or generation rounds.
DEFAULT_MAX_EMBEDDING_REQUESTS = None


def minimal_public_input_roots(source_paths) -> tuple[Path, ...]:
    """Return the least broad non-overlapping roots implied by source files.

    A task manifest may contain files from both a directory and one of its
    descendants.  The invocation contract correctly rejects overlapping roots,
    so the adapter must collapse the redundant descendant before crossing that
    boundary.  This does not widen authority: every retained root is still the
    parent of at least one declared source file.
    """

    candidates = sorted(
        {Path(path).resolve().parent for path in source_paths},
        key=lambda path: (len(path.parts), str(path)),
    )
    retained: list[Path] = []
    for candidate in candidates:
        if any(candidate == root or candidate.is_relative_to(root) for root in retained):
            continue
        retained.append(candidate)
    return tuple(sorted(retained, key=str))


async def run(args, protocol_output):
    from sgar_mvp.src.external_worker_runtime import JsonLinesExecutionSubstrate
    runtime = JsonLinesExecutionSubstrate(
        input_stream=sys.stdin, output_stream=protocol_output,
        run_id=args.run_id, trial_id=args.trial_id,
        network_allowed=args.network_policy == "declared",
    )
    if args.mode == "contract":
        from sgar_mvp.src.external_runtime_contract import verify_contract
        return await verify_contract(runtime)
    if args.mode == "production-contract":
        from sgar_mvp.src.external_runtime_contract import verify_production_contract
        return await verify_production_contract(runtime, args.output_dir)
    # This check precedes config secrets, main import, model/retrieval and task IO.
    runtime.require_pipeline_ready()
    from sgar_mvp.main import load_config, run_pipeline
    config = load_config(args.config, resolve_secrets=True)
    if not config:
        raise RuntimeError("SGAR_CONFIG_MISSING")
    task_invocation = None
    if args.task_state_manifest:
        from sgar_mvp.src.task_invocation import InputSourceSpec, prepare_task_invocation

        manifest = json.loads(
            Path(args.task_state_manifest).read_text(encoding="utf-8")
        )
        records = manifest.get("records") if isinstance(manifest, dict) else None
        if not isinstance(records, list):
            raise RuntimeError("SGAR_TASK_STATE_MANIFEST_INVALID")
        specs = tuple(
            InputSourceSpec(
                logical_name=str(item["logical_name"]),
                source_path=Path(str(item["source_path"])).resolve(),
                execution_contract=(
                    dict(item.get("execution_contract") or {})
                    if isinstance(item.get("execution_contract"), dict)
                    else None
                ),
            )
            for item in records
            if isinstance(item, dict)
            and item.get("logical_name")
            and item.get("source_path")
        )
        roots = minimal_public_input_roots(item.source_path for item in specs)
        task_invocation = prepare_task_invocation(
            query=args.query,
            input_specs=specs,
            run_dir=Path(args.output_dir),
            allowed_public_input_roots=roots,
            final_deliverable_contract=(
                manifest.get("final_deliverable_contract")
                if isinstance(manifest, dict)
                else None
            ),
        )
    status = await run_pipeline(
        config, args.query, args.output_dir, args.report_path,
        execution_substrate_mode="external", execution_substrate=runtime,
        run_id=args.run_id,
        network_policy_mode=args.network_policy,
        require_final_delivery=not args.allow_missing_delivery,
        max_generation_requests=args.max_generation_requests,
        max_embedding_requests=args.max_embedding_requests,
        task_invocation=task_invocation,
        method_deadline_monotonic=getattr(args, "method_deadline_monotonic", None),
    )
    return {"pipeline_status": str(status), "actions": runtime.records}


def main():
    parser = argparse.ArgumentParser()
    for name in ("config", "query", "output-dir", "report-path", "run-id", "trial-id"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--task-state-manifest", default=None)
    parser.add_argument("--network-policy", choices=("disabled", "declared"), default="disabled")
    parser.add_argument("--allow-missing-delivery", action="store_true")
    parser.add_argument("--mode", choices=("pipeline", "contract", "production-contract"), default="pipeline")
    parser.add_argument("--max-generation-requests", type=int, default=None)
    parser.add_argument("--method-deadline-monotonic", type=float, default=None)
    parser.add_argument(
        "--max-embedding-requests",
        type=int,
        default=DEFAULT_MAX_EMBEDDING_REQUESTS,
    )
    args = parser.parse_args()
    protocol_output = sys.stdout
    # Existing SGAR components can print progress; it must not corrupt the pipe.
    sys.stdout = sys.stderr
    status, code = "completed", 0
    try:
        result = asyncio.run(run(args, protocol_output))
    except Exception as exc:
        status, code = "error", 1
        result = {"error_type": type(exc).__name__, "error": str(exc)}
    terminal = {"protocol": "sgar-external-substrate-terminal-v1", "run_id": args.run_id,
                "trial_id": args.trial_id, "status": status, "mode": args.mode,
                "result": result}
    root = Path(args.output_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / "worker_terminal.json").write_text(json.dumps(terminal, indent=2) + "\n")
    protocol_output.write(json.dumps(terminal, ensure_ascii=True) + "\n")
    protocol_output.flush()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
