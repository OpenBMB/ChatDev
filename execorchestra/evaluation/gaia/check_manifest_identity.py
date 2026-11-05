"""Read-only check that a GAIA experiment manifest matches the SGAR checkout.

This checks the identities that can drift while a historical frozen manifest
still exists. It does not inspect credentials, contact providers, or run cases.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def check_identity(root: Path, manifest_path: Path, gaia_root: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    profile = json.loads(
        (root / "sgar_mvp/config/model_profile.json").read_text(encoding="utf-8")
    )
    index = json.loads(
        (root / "Pool/index_meta/index_build_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    actual_roles = {
        role["role"]: role["api_model_id"] for role in profile["roles"]
    }
    checks: dict[str, dict] = {}

    def compare(name: str, expected: object, actual: object) -> None:
        checks[name] = {
            "match": expected == actual,
            "manifest": expected,
            "current": actual,
        }

    compare("manifest_status", "FROZEN", manifest.get("status"))
    compare("code.commit", manifest["code"]["sgar_git_commit"], _git(root, "rev-parse", "HEAD"))
    dirty = _git(root, "status", "--porcelain", "--untracked-files=normal")
    checks["code.clean_worktree"] = {
        "match": not dirty,
        "manifest": True,
        "current": not bool(dirty),
        "changed_entry_count": len(dirty.splitlines()),
    }
    for role in (
        "planner", "profiler", "plan_compiler", "plan_adaptation", "evaluator"
    ):
        compare(f"models.{role}", manifest["models"].get(role), actual_roles.get(role))
    compare(
        "models.control_role_policy_sha256",
        manifest["models"].get("control_role_policy_sha256"),
        _sha256(root / "sgar_mvp/config/control_role_policy.json"),
    )
    file_fields = {
        "resources.catalog_sha256": "Pool/resources/json/combine.json",
        "resources.effective_pool_sha256": "Pool/resources/json/effective_combine.json",
        "retrieval.index_manifest_sha256": "Pool/index_meta/index_build_manifest.json",
        "retrieval.retrieval_policy_sha256": "sgar_mvp/config/retrieval_policy.json",
        "retrieval.capability_index_sha256": "Pool/index_meta/faiss_cap.index",
        "retrieval.constraint_index_sha256": "Pool/index_meta/faiss_con.index",
        "retrieval.metadata_index_sha256": "Pool/index_meta/resource_meta.pkl",
    }
    for dotted_name, relative_path in file_fields.items():
        section, field = dotted_name.split(".")
        compare(dotted_name, manifest[section].get(field), _sha256(root / relative_path))
    compare(
        "budget.model_cost_policy_sha256",
        manifest["budget"].get("model_cost_policy_sha256"),
        _sha256(root / "sgar_mvp/config/model_cost_policy.json"),
    )
    compare(
        "retrieval.generation_id",
        manifest["retrieval"].get("generation_id"),
        index.get("generation_id"),
    )
    gaia_code_files = {
        "adapter_sha256": "adapter.py",
        "answer_adapter_sha256": "answer.py",
        "scorer_wrapper_sha256": "scorer.py",
        "synthetic_runner_sha256": "run_synthetic.py",
        "dataset_freezer_sha256": "freeze_dataset.py",
        "experiment_finalizer_sha256": "finalize_experiment_manifest.py",
        "validation_runner_sha256": "run_validation.py",
    }
    for field, filename in gaia_code_files.items():
        compare(f"code.{field}", manifest["code"].get(field), _sha256(gaia_root / filename))
    compare(
        "evaluation.scorer_sha256",
        manifest["evaluation"].get("scorer_sha256"),
        _sha256(Path(manifest["evaluation"]["scorer_source"])),
    )
    dataset_manifest_path = Path(manifest["dataset"]["manifest"])
    dataset = (
        json.loads(dataset_manifest_path.read_text(encoding="utf-8"))
        if dataset_manifest_path.is_file()
        else {}
    )
    for field in (
        "manifest_sha256", "revision", "task_count", "level_counts",
        "task_ids_sha256", "raw_tree_sha256", "gold_separated", "immutable",
    ):
        compare(f"dataset.{field}", manifest["dataset"].get(field), dataset.get(field))
    for view in ("agent_visible", "evaluator_only"):
        compare(
            f"dataset.{view}_sha256",
            dataset.get(f"{view}_sha256"),
            _sha256(dataset_manifest_path.parent / "views" / f"{view}.jsonl"),
        )
    mismatches = [name for name, result in checks.items() if not result["match"]]
    return {
        "protocol": "sgar-gaia-manifest-identity-audit-v1",
        "manifest": str(manifest_path),
        "project_root": str(root),
        "gaia_root": str(gaia_root),
        "ready_for_exact_manifest_run": not mismatches,
        "mismatches": mismatches,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--gaia-root", type=Path, required=True)
    args = parser.parse_args()
    result = check_identity(
        args.project_root.resolve(), args.manifest.resolve(), args.gaia_root.resolve()
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ready_for_exact_manifest_run"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
