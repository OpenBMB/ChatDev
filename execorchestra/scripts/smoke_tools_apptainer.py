"""Use the original smoke fixtures/classifier with the Apptainer backend."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import subprocess
import time
from types import SimpleNamespace

from scripts.smoke_tools import smoke_args
from sgar_mvp.scripts import run_tool_smoke_tests as original
from sgar_mvp.src.apptainer_runtime import ApptainerExecutionSubstrate
from sgar_mvp.src.direct_network import load_tool_proxy_config, tool_proxy_environment
from sgar_mvp.src.resource_runtime import ResourceDefinition


ROOT = Path(__file__).resolve().parents[1]
SERVICE_ENV_NAMES = ("SEARXNG_BASE_URL", "ZOTERO_TRANSLATION_SERVER_URL",
                     "HYPOTHESIS_API_URL", "HYPOTHESIS_API_TOKEN",
                     "SGAR_BROWSER_BASE_URL", "SGAR_BROWSER_TOKEN")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("image", "image-sha256", "apptainer", "tools-prefix", "output-root"):
        parser.add_argument("--" + name, required=True, type=str)
    parser.add_argument("--tool-id", action="append")
    parser.add_argument("--network", choices=("offline", "online", "all"), default="all")
    parser.add_argument("--timeout-sec", type=int, default=120)
    parser.add_argument("--transient-retries", type=int, default=1)
    args = parser.parse_args()
    output = Path(args.output_root).resolve()
    output.mkdir(parents=True, exist_ok=False)
    os.chmod(output, 0o700)
    catalog = json.loads((ROOT / "Pool/resources/json/effective_tools.json").read_text())
    requested = set(args.tool_id or [])
    if requested - {item["resource_id"] for item in catalog}:
        raise ValueError("unknown_requested_tool")
    tools = [item for item in catalog if (not requested or item["resource_id"] in requested)
             and (args.network == "all" or bool(item["runtime_requirements"]["network_required"]) == (args.network == "online"))]
    if not tools:
        raise ValueError("empty_tool_selection")
    env = tool_proxy_environment(load_tool_proxy_config(ROOT), network_required=True,
                                 network_policy_mode="declared")
    env.update({name: os.environ[name] for name in SERVICE_ENV_NAMES if os.environ.get(name)})
    def runtime(name):
        return ApptainerExecutionSubstrate(image=Path(args.image), image_sha256=args.image_sha256,
            apptainer=Path(args.apptainer), tools_prefix=Path(args.tools_prefix),
            state_dir=output / name, run_id=name, trial_id=name, network_allowed=True,
            network_env=env)
    fixture_runtime = runtime("fixture-runtime")
    template = fixture_runtime.app_dir / "fixture_template"
    def build_binary(code, ignored_host_root):
        result = fixture_runtime.call("exec_argv", argv=["python3", "-c", code, "/app/fixture_template"], timeout_sec=60)
        return subprocess.CompletedProcess([], result["return_code"], result["stdout"], result["stderr"])
    original.build_fixture_template(template, "sgar-runtime:rc1", binary_runner=build_binary)
    evidence = output / "evidence"; evidence.mkdir()
    results = []
    for item in tools:
        rid = item["resource_id"]
        requirements = item["runtime_requirements"]
        row = {"resource_id": rid, "checked_at": original.utc_now(), "status": "blocked",
               "smoke_passed": False, "attempt_count": 0, "runtime_backend": "apptainer",
               "runtime_image_sha256": args.image_sha256}
        if requirements["runtime_profile"] == "task-container":
            # Keep this visible. No claim that a task-specific browser/compiler
            # became available merely because the generic runtime started.
            row["failure_type"] = "task_specific_image_required"
        elif (requirements.get("install_policy") != "never" or
              (requirements.get("docker_image") != "sgar-runtime:rc1" and not
               (requirements["runtime_profile"] == "host-python-stdlib" and not requirements.get("docker_image")))):
            row["failure_type"] = "runtime_policy_mismatch"
        else:
            engine = runtime(rid.replace(".", "_"))
            workspace = engine.app_dir / "workspace"
            original.prepare_tool_workspace(rid, template, workspace)
            argv = smoke_args(item, Path("/app/workspace"))
            definition = ResourceDefinition.from_manifest(item)
            request = SimpleNamespace(resource_definition=definition, entrypoint_id="invoke")
            source = engine._dispatch_source_path(request, project_root=str(ROOT))
            row["source_hash"] = original.sha256(source.read_bytes())
            if row["source_hash"] != item["provenance"]["source_hash"]:
                row["failure_type"] = "source_hash_mismatch"
            elif argv is None:
                row["failure_type"] = "smoke_case_missing"
            else:
                _, staged = engine._stage_resource_source(request, project_root=str(ROOT))
                interpreter = "sh" if item["execution"]["runtime"] == "shell_script" else "python3"
                for attempt in range(1, args.transient_retries + 2):
                    start = time.monotonic()
                    result = engine.call("exec_argv", argv=[interpreter, str(staged), *argv],
                        timeout_sec=args.timeout_sec,
                        network_required=bool(requirements["network_required"]),
                        extra_env={"SGAR_WORKSPACE_ROOT": "/app/workspace", "SGAR_HOST_WORKSPACE_ROOT": "/app"})
                    stdout, stderr = result["stdout"], result["stderr"]
                    status, passed, failure = original.classify_result(
                        return_code=result["return_code"], stdout=stdout, stderr=stderr,
                        network_required=bool(requirements["network_required"]))
                    if result.get("error_type"):
                        status, passed, failure = "blocked", False, result["error_type"]
                    row.update(status=status, smoke_passed=passed, failure_type=failure or None,
                        attempt_count=attempt, return_code=result["return_code"],
                        latency_ms=round((time.monotonic()-start)*1000,2),
                        output_sha256=original.sha256(stdout.encode()), output_bytes=len(stdout.encode()))
                    for stream, content in (("stdout", stdout), ("stderr", stderr)):
                        # Evidence is private. Strip known credentials if a library
                        # includes a proxy URL in its error rather than its type.
                        for key, value in env.items():
                            if value and ("TOKEN" in key or "PROXY" in key):
                                content = content.replace(value, "<redacted>")
                        file = evidence / f"{rid}.{stream}.txt"
                        file.write_text(content, encoding="utf-8")
                        file.chmod(0o600)
                        row[stream + "_artifact"] = original.artifact_reference(file)
                    if status != "transient_failure" or attempt > args.transient_retries:
                        break
                    time.sleep(1)
        results.append(row)
        print(json.dumps({"resource_id": rid, "status": row["status"], "failure_type": row.get("failure_type")}), flush=True)
        report = {"schema_version": 1, "runtime_backend": "apptainer",
                  "runtime_image_sha256": args.image_sha256, "generated_at": original.utc_now(),
                  "selection": {"network": args.network, "requested_ids": sorted(requested)},
                  "summary": dict(Counter(x["status"] for x in results)), "tools": results,
                  "complete": len(results) == len(tools), "expected_count": len(tools)}
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return 0 if all(x["smoke_passed"] for x in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
