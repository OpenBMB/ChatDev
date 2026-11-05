"""Run the external substrate contracts or a task in an allocated Slurm job."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import time


async def run(args):
    from sgar_mvp.src.apptainer_runtime import ApptainerExecutionSubstrate
    runtime = ApptainerExecutionSubstrate(
        image=Path(args.image), image_sha256=args.image_sha256,
        state_dir=Path(args.output_dir) / "task-state", run_id=args.run_id, trial_id=args.run_id,
        apptainer=Path(args.apptainer), tools_prefix=Path(args.tools_prefix),
        network_allowed=args.network_policy == "declared",
        network_env={name: os.environ[name] for name in args.tool_env if name in os.environ},
    )
    runtime.require_pipeline_ready()
    if args.mode == "contract":
        from sgar_mvp.src.external_runtime_contract import verify_production_contract
        result = await verify_production_contract(runtime, str(Path(args.output_dir) / "contract"))
        # The existing checker predates this adapter; keep its checks but use an
        # accurate classification for this backend, not the Harbor label.
        result["classification"] = "APPTAINER_RESOURCE_AND_ARTIFACT_CONTRACT_ONLY"
    else:
        query = args.query
        prepared = None
        if args.query_file or args.input:
            from sgar_mvp.src.task_invocation import resolve_task_request, prepare_task_invocation
            run_dir = Path(args.output_dir).resolve() / "pipeline"
            run_dir.mkdir(parents=True, exist_ok=True)
            request = resolve_task_request(request_manifest=None, query=args.query,
                query_file=Path(args.query_file) if args.query_file else None, query_file_encoding="utf-8",
                named_inputs=args.input, input_manifest=None,
                allowed_public_input_roots=args.input_root,
                project_root=Path(__file__).resolve().parents[1], run_dir=run_dir)
            query = request.exact_query
            prepared = prepare_task_invocation(query=query, input_specs=request.input_specs,
                run_dir=run_dir, request_id=request.request_id,
                final_deliverable_contract=request.final_deliverable_contract,
                public_context_descriptors=request.public_context_descriptors,
                allowed_public_input_roots=request.allowed_public_input_roots,
                project_root=Path(__file__).resolve().parents[1])
        if not query:
            raise ValueError("--query or --query-file is required for pipeline mode")
        from sgar_mvp.main import load_config, run_pipeline
        config = load_config(str(Path(args.config).expanduser().resolve()), resolve_secrets=True)
        if not config:
            raise RuntimeError("SGAR_CONFIG_MISSING")
        status = await run_pipeline(
            config, query, str(Path(args.output_dir) / "pipeline"),
            str(Path(args.output_dir) / "report.md"),
            execution_substrate_mode="external", execution_substrate=runtime,
            run_id=args.run_id, network_policy_mode=args.network_policy,
            require_final_delivery=True,
            max_generation_requests=args.max_generation_requests,
            task_invocation=prepared,
            method_deadline_monotonic=time.monotonic()+args.deadline_sec if args.deadline_sec else None,
        )
        result = {"pipeline_status": str(status),
                  "passed": str(status) in {"complete_success", "success_with_warnings"}}
    result.update(runtime_backend="apptainer", image_sha256=runtime.image_sha256,
                  action_count=len(runtime.records))
    target = Path(args.output_dir) / "apptainer-result.json"
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    target.chmod(0o600)
    print(json.dumps(result, ensure_ascii=True))
    if not result["passed"]:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("contract", "pipeline"), default="contract")
    for name in ("image", "image-sha256", "output-dir", "run-id", "apptainer", "tools-prefix"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--config", default="sgar_mvp/config.json")
    query_group = parser.add_mutually_exclusive_group()
    query_group.add_argument("--query")
    query_group.add_argument("--query-file")
    parser.add_argument("--input", action="append", default=[], help="Named public input: name=path")
    parser.add_argument("--input-root", action="append", default=[], help="Explicit authorized directory for public inputs")
    parser.add_argument("--deadline-sec", type=int)
    parser.add_argument("--network-policy", choices=("disabled", "declared"), default="disabled")
    parser.add_argument("--tool-env", action="append", default=[], metavar="VARIABLE_NAME",
                        help="Explicitly pass this environment variable to network-enabled tools only.")
    parser.add_argument("--max-generation-requests", type=int)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
