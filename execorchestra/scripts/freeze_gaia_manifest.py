"""Bind the reader's prepared checkout to a separately acquired GAIA dataset."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from scripts.prepare_release import ROOT, read, write
from evaluation.gaia.finalize_experiment_manifest import finalize
from evaluation.gaia.check_manifest_identity import check_identity

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "sgar_mvp/runtime_state/gaia_manifest.json")
    args = parser.parse_args()
    gaia = ROOT / "evaluation/gaia"
    pending = {"method_id": "ExecOrchestra", "experiment_id": "execorchestra-gaia",
               "code": {}, "models": {}, "resources": {}, "retrieval": {}, "budget": {}, "evaluation": {}}
    pending["code"]["sgar_git_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    for key, name in {
        "adapter_sha256": "adapter.py", "answer_adapter_sha256": "answer.py",
        "scorer_wrapper_sha256": "scorer.py", "synthetic_runner_sha256": "run_synthetic.py",
        "dataset_freezer_sha256": "freeze_dataset.py", "experiment_finalizer_sha256": "finalize_experiment_manifest.py",
        "validation_runner_sha256": "run_validation.py",
    }.items(): pending["code"][key] = digest(gaia / name)
    pending["models"] = {x["role"]: x["api_model_id"] for x in read(ROOT / "sgar_mvp/config/model_profile.json")["roles"]}
    pending["models"]["control_role_policy_sha256"] = digest(ROOT / "sgar_mvp/config/control_role_policy.json")
    for section, fields in {
        "resources": {"catalog_sha256": "Pool/resources/json/combine.json", "effective_pool_sha256": "Pool/resources/json/effective_combine.json"},
        "retrieval": {"index_manifest_sha256": "Pool/index_meta/index_build_manifest.json", "retrieval_policy_sha256": "sgar_mvp/config/retrieval_policy.json",
                      "capability_index_sha256": "Pool/index_meta/faiss_cap.index", "constraint_index_sha256": "Pool/index_meta/faiss_con.index", "metadata_index_sha256": "Pool/index_meta/resource_meta.pkl"},
        "budget": {"model_cost_policy_sha256": "sgar_mvp/config/model_cost_policy.json"},
    }.items():
        for key, filename in fields.items():
            value = digest(ROOT / filename)
            if value is None: raise RuntimeError("Preparation incomplete: " + filename)
            pending[section][key] = value
    pending["retrieval"]["generation_id"] = read(ROOT / "Pool/index_meta/index_build_manifest.json")["generation_id"]
    pending["budget"].update(max_generation_requests_per_task=None, max_embedding_requests_per_task=None)
    pending["evaluation"] = {"scorer_source": str(gaia / "scorer.py"), "scorer_sha256": digest(gaia / "scorer.py")}
    stage = ROOT / "sgar_mvp/runtime_state/gaia_manifest.pending.json"
    write(stage, pending)
    finalize(stage, args.dataset_root.resolve() / "dataset_manifest.json", args.output.resolve())
    audit = check_identity(ROOT, args.output.resolve(), gaia)
    write(ROOT / "sgar_mvp/runtime_state/gaia_manifest_audit.json", audit)
    if not audit["ready_for_exact_manifest_run"]:
        raise RuntimeError("Manifest identity mismatch: " + ",".join(audit["mismatches"]))
    print("GAIA manifest validated: " + str(args.output))

if __name__ == "__main__":
    main()
