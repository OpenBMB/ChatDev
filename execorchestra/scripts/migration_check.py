"""Offline source/configuration checks; never starts services or sends model requests."""
from __future__ import annotations

import argparse
import ast
import json
import os
import platform
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def inspect(root: Path, *, stage: str, backend: str, environment=None):
    environment = os.environ if environment is None else environment
    checks = []

    def check(name, passed, action):
        checks.append({"name": name, "passed": bool(passed), "action": "" if passed else action})

    def read(name):
        try:
            return json.loads((root / name).read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return None

    check("python_3_11_or_newer", sys.version_info >= (3, 11), "Install Python 3.11 or newer.")
    for name in ["README.md", "requirements.txt", "scripts/run.sh", "examples/task.txt",
                 "scripts/prepare_release.py", "sgar_mvp/docker/Dockerfile.runtime",
                 "sgar_mvp/config.example.json", "configs/embedding_release.example.json",
                 "configs/retrieval_policy.example.json", "sgar_mvp/src/proxy_retry.py",
                 "sgar_mvp/src/research_navigation_audit.py", "scripts/embedding_server.py", "requirements-embedding.txt"]:
        check("source:" + name, (root / name).is_file(), "Restore this file from the migration commit.")

    catalog = read("Pool/resources/json/combine.json")
    pool = read("sgar_mvp/config/candidate_pool.json")
    profile = read("sgar_mvp/config/model_profile.json")
    policy = read("sgar_mvp/config/control_role_policy.json")
    try:
        by_id = {r["resource_id"]: r for r in catalog}
        check("catalog_unique_ids", len(by_id) == len(catalog), "Repair duplicate catalog entries.")
        check("candidate_membership", set(pool["resource_ids"]) <= by_id.keys(), "Restore the matching candidate catalog.")
        fields = ["role", "resource_id", "api_model_id", "reasoning_effort", "temperature", "allow_model_failover", "response_mode"]
        project = lambda rows: [{key: row.get(key) for key in fields} for row in rows]
        check("control_profile_matches_policy", project(profile["roles"]) == project(policy["roles"]),
              "Use the matching control profile and role policy.")
        check("control_models_registered", all(r["resource_id"] in by_id and
            by_id[r["resource_id"]]["execution"]["model_id"] == r["api_model_id"] for r in profile["roles"]),
            "Restore control model registration and catalog entries.")
    except (KeyError, TypeError, ValueError):
        check("resource_configuration_readable", False, "Restore valid catalog, candidate, model profile and policy JSON.")

    embedding = read("configs/embedding_release.example.json")
    runtime = embedding.get("runtime", {}) if isinstance(embedding, dict) else {}
    check("embedding_reference", runtime.get("model_id") == "Qwen/Qwen3-Embedding-4B" and
          runtime.get("output_dimension") == 2560 and runtime.get("normalize") is True,
          "Use the matching 4B embedding configuration; rebuild an index after changing its identity.")
    try:
        tree = ast.parse((root / "scripts/embedding_server.py").read_text(encoding="utf-8"))
        constants = {node.targets[0].id: ast.literal_eval(node.value) for node in tree.body
                     if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                     and node.targets[0].id in {"MODEL_ID", "REVISION", "DIMENSION", "MAX_TOKENS"}}
        check("embedding_service_identity", all(constants.get(key) == runtime.get(field) for key, field in
              [("MODEL_ID", "api_model_id"), ("REVISION", "revision"), ("DIMENSION", "output_dimension"), ("MAX_TOKENS", "max_tokens")]),
              "Use the matching embedding service and tokenizer/model revision.")
    except (OSError, SyntaxError, ValueError):
        check("embedding_service_identity", False, "Restore the pinned embedding service source.")

    if stage == "configured":
        check("linux_runtime", platform.system() == "Linux", "Run the framework on a supported Linux host.")
        check("container_command", shutil.which(backend) is not None, "Install/configure " + backend + " on the target host.")
        for key in ["LLM_API_KEY", "LLM_BASE_URL", "SGAR_EMBEDDING_API_KEY"]:
            value = environment.get(key, "").strip()
            check("environment:" + key, bool(value) and not value.startswith("${"), "Export " + key + " from private configuration.")
        for name in ["sgar_mvp/config.json", "sgar_mvp/config/embedding_release.json", "sgar_mvp/config/retrieval_policy.json",
                     "sgar_mvp/runtime_state/model_ready_state.json", "sgar_mvp/runtime_state/control_role_probe_receipt.json",
                     "sgar_mvp/config/resource_readiness_rc1.json", "Pool/index_meta/index_build_manifest.json"]:
            check("prepared:" + name, (root / name).is_file(), "Complete the corresponding prepare_release stage on this host.")
        lock = "sgar_mvp/config/rc1_runtime_lock.json" if backend == "docker" else "sgar_mvp/config/apptainer_runtime_lock.json"
        check("runtime_lock", (root / lock).is_file(), "Verify and seal the target runtime before readiness.")
        local = read("sgar_mvp/config/embedding_release.json")
        token_path = ((local or {}).get("runtime") or {}).get("tokenizer_path", "")
        token_dir = Path(token_path) if token_path else None
        if token_dir is not None and not token_dir.is_absolute():
            token_dir = root / token_dir
        check("embedding_tokenizer", token_dir is not None and token_dir.is_dir(), "Download the matching tokenizer and configure its path.")

    passed = all(row["passed"] for row in checks)
    return {"stage": stage, "backend": backend, "status": "passed" if passed else "incomplete",
            "live_probes_performed": False, "end_to_end_verified": False, "checks": checks,
            "note": "Offline checks do not prove service availability, index freshness, or task accuracy. Run prepare_release check and a real task on the target server."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["source", "configured"], default="source")
    parser.add_argument("--backend", choices=["docker", "apptainer"], default="docker")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = inspect(ROOT, stage=args.stage, backend=args.backend)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("Migration " + args.stage + " check: " + report["status"])
        for row in report["checks"]:
            print(("[OK] " if row["passed"] else "[TODO] ") + row["name"])
            if row["action"]:
                print("       " + row["action"])
        print(report["note"])
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
