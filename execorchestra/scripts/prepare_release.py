"""Prepare a reader-owned checkout without historical runtime evidence."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PREPARATION_STAGES = ("health", "control", "tools", "agents", "readiness", "index", "check")


def prepare_all(*, allow_unavailable=False, runtime_backend="docker"):
    """Run the existing first-run stages in order; stop at the first failure."""
    target = ROOT / "Pool/index_meta"
    if target.exists() and any(target.iterdir()):
        raise RuntimeError("Pool/index_meta already exists. Reuse the prepared index for tasks, "
                           "or back it up before rebuilding. No preparation requests were sent.")
    for number, stage in enumerate(PREPARATION_STAGES, 1):
        print(f"[{number}/{len(PREPARATION_STAGES)}] Preparing: {stage}", flush=True)
        options = []
        if stage == "readiness":
            options.extend(("--runtime-backend", runtime_backend))
            if allow_unavailable:
                options.append("--allow-unavailable")
        run("scripts.prepare_release", stage, *options)

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))

def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def run(module, *args):
    subprocess.run([sys.executable, "-m", module, *map(str, args)], cwd=ROOT, check=True)

def initialize():
    """Materialize ignored local files; never overwrite reader configuration."""
    for name in ("embedding_release", "retrieval_policy"):
        target = ROOT / f"sgar_mvp/config/{name}.json"
        if not target.exists():
            shutil.copyfile(ROOT / f"configs/{name}.example.json", target)
    config = ROOT / "sgar_mvp/config.json"
    if not config.exists():
        shutil.copyfile(ROOT / "sgar_mvp/config.example.json", config)
    catalog = read(ROOT / "Pool/resources/json/combine.json")
    by_id = {x["resource_id"]: x for x in catalog}
    ids = read(ROOT / "sgar_mvp/config/candidate_pool.json")["resource_ids"]
    effective = [by_id[x] for x in ids]
    for name, rows in (("effective_combine", effective),
                       ("effective_tools", [x for x in effective if x["resource_type"] == "Tool"])):
        target = ROOT / f"Pool/resources/json/{name}.json"
        if not target.exists():
            write(target, rows)
    print("Local templates initialized. Existing files were preserved.")

def bind_control_identity(policy):
    from sgar_mvp.main import load_config
    from sgar_mvp.src.control_role_policy import load_control_role_policy
    from sgar_mvp.src.internal_language import build_prompt_surface_registry, prompt_file_text
    from sgar_mvp.src.model_response_contracts import system_role_schema
    from sgar_mvp.src.model_transport import create_production_model_transport_bundle
    from sgar_mvp.src.pipeline_control import canonical_sha256
    from sgar_mvp.src.profiler_protocol import ProfilerProviderCapabilityV1
    from sgar_mvp.src.release_provider_receipt import load_and_verify_release_provider_probe_receipt
    config = load_config(str(ROOT / "sgar_mvp/config.json"))
    transport = create_production_model_transport_bundle(
        api_key=config["llm_key"], base_url=config["llm_settings"]["base_url"])
    control = load_control_role_policy()
    receipt = load_and_verify_release_provider_probe_receipt(
        ROOT / "sgar_mvp/runtime_state/control_role_probe_receipt.json",
        expected_endpoint_identity_sha256=transport.endpoint_identity.identity_sha256,
        control_role_policy=control)
    profiler = receipt["records"][0]
    observation = profiler["provider_reasoning_observation"]
    capability = ProfilerProviderCapabilityV1(
        endpoint_identity_sha256=receipt["endpoint_identity_sha256"],
        transport_kind="chat_completions",
        resource_id=profiler["model_resource_id"], api_model_id=profiler["api_model_id"],
        supported_reasoning_efforts=(profiler["reasoning_effort"],),
        accepted_output_cap=16384, accepted_response_mode="native_strict_schema",
        finish_reason_semantics={"stop": "complete", "length": "truncated"},
        reasoning_usage_available=observation.get("reasoning_tokens") is not None,
        reasoning_content_available=bool(observation.get("available")),
        probed_at=receipt["generated_at"],
        probe_request_sha256=profiler["request_sha256"],
        probe_response_sha256=profiler["response_sha256"])
    write(ROOT / "sgar_mvp/runtime_state/profiler_provider_capability.json", capability.model_dump(mode="json"))
    policy.update(
        prompt_registry_sha256=build_prompt_surface_registry().registry_sha256,
        profiler_prompt_sha256=hashlib.sha256(prompt_file_text("profiler_system.txt").encode()).hexdigest(),
        profiler_schema_sha256=canonical_sha256(system_role_schema("hyde")),
        control_role_policy_sha256=control.policy_sha256,
        control_provider_probe_receipt_sha256=receipt["result_sha256"])
    policy["hyde"].update(provider_capability_sha256=capability.capability_sha256,
                          response_mode=capability.accepted_response_mode)
    return policy

def readiness(allow_unavailable=False, runtime_backend="docker"):
    """Use fresh smoke/health evidence and preserve the configured candidate set."""
    from sgar_mvp.src.resource_readiness import RC1ReadinessBuilder
    from sgar_mvp.src.model_selection import validated_candidate_ready_ids
    paths = {
        "tool_smoke": "sgar_mvp/execution_outputs/tool_smoke/tool_smoke_latest.json",
        "model_health": "sgar_mvp/runtime_state/model_ready_state.json",
        "agent_smoke": "sgar_mvp/execution_outputs/agent_smoke/agent_smoke_latest.json",
        "runtime_lock": "sgar_mvp/config/rc1_runtime_lock.json",
    }
    if runtime_backend == "apptainer":
        paths["runtime_lock"] = "sgar_mvp/config/apptainer_runtime_lock.json"
    evidence = {key: read(ROOT / path) for key, path in paths.items()}
    validated_candidate_ready_ids(evidence["model_health"], root=ROOT)
    catalog = read(ROOT / "Pool/resources/json/combine.json")
    report, ready = RC1ReadinessBuilder(ROOT, catalog, **evidence).build()
    expected = read(ROOT / "sgar_mvp/config/candidate_pool.json")["resource_ids"]
    by_id = {x["resource_id"]: x for x in ready}
    missing = sorted(set(expected) - set(by_id))
    report["distribution_candidate_ids"] = expected
    report["unavailable_distribution_candidates"] = missing
    write(ROOT / "sgar_mvp/runtime_state/preparation_report.json", report)
    if missing and not allow_unavailable:
        raise RuntimeError("Resources unavailable; inspect runtime_state/preparation_report.json. "
                           "No effective catalog was changed. --allow-unavailable explicitly selects a reduced pool.")
    effective = [by_id[x] for x in expected if x in by_id]
    if not effective or not any(x["resource_type"] == "Model" for x in effective):
        raise RuntimeError("No usable candidate models; repair provider access first.")
    report["effective_resource_ids"] = [x["resource_id"] for x in effective]
    report["summary"]["effective_total"] = len(effective)
    report["evidence"]["model_health_sha256"] = evidence["model_health"]["health_sha256"]
    write(ROOT / "sgar_mvp/config/resource_readiness_rc1.json", report)
    write(ROOT / "Pool/resources/json/effective_combine.json", effective)
    write(ROOT / "Pool/resources/json/effective_tools.json", [x for x in effective if x["resource_type"] == "Tool"])
    print(json.dumps({"effective": len(effective), "unavailable": missing}))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["init", "all", *PREPARATION_STAGES])
    parser.add_argument("--allow-unavailable", action="store_true")
    parser.add_argument("--runtime-backend", choices=("docker", "apptainer"), default="docker",
                        help="Runtime identity for the readiness stage; Docker remains the default.")
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        raise SystemExit("Python 3.11 or newer is required.")
    os.chdir(ROOT)
    if args.stage == "init":
        initialize()
    elif args.stage == "all":
        prepare_all(allow_unavailable=args.allow_unavailable, runtime_backend=args.runtime_backend)
    elif args.stage == "health":
        run("sgar_mvp.scripts.check_model_health", "--config", "sgar_mvp/config.json",
            "--output", "sgar_mvp/runtime_state/model_health_report.json", "--apply-ready-state",
            "--capability-probes", "all", "--retries", "3", "--concurrency", "4")
    elif args.stage == "control":
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        run("sgar_mvp.scripts.bootstrap_control_roles", "--output-dir", f"sgar_mvp/runtime_state/control-{stamp}")
    elif args.stage == "tools":
        run("scripts.smoke_tools")
    elif args.stage == "agents":
        run("sgar_mvp.scripts.smoke_test_agents",
            "--model-resource-id", "model.gpt_5_6_luna.v1", "--max-tokens", "512", "--skip-joint-plan")
    elif args.stage == "readiness":
        readiness(args.allow_unavailable, runtime_backend=args.runtime_backend)
    elif args.stage == "index":
        from sgar_mvp.scripts.bootstrap_index import build
        target = ROOT / "Pool/index_meta"
        if target.exists() and any(target.iterdir()):
            raise RuntimeError("Pool/index_meta already exists. Move it to a private backup before rebuilding.")
        print(json.dumps(build(ROOT / "sgar_mvp/config/embedding_release.json", target)))
        shutil.copyfile(target / "retrieval_policy.json", ROOT / "sgar_mvp/config/retrieval_policy.json")
    else:
        from sgar_mvp.main import load_config
        from sgar_mvp.src.model_transport import create_production_model_transport_bundle
        from sgar_mvp.src.retrieval_runtime import build_retrieval_runtime_identity
        config = load_config(str(ROOT / "sgar_mvp/config.json"))
        bundle = create_production_model_transport_bundle(api_key=config["llm_key"], base_url=config["llm_settings"]["base_url"])
        identity = build_retrieval_runtime_identity(project_root=ROOT,
            provider_endpoint_identity_sha256=bundle.endpoint_identity.identity_sha256)
        print(json.dumps({"retrieval_identity": identity.identity_sha256, "network_calls": 0}))

if __name__ == "__main__":
    main()
