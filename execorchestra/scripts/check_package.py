"""Offline integrity checks for the distributed framework and resource catalog."""
from pathlib import Path
import hashlib
import json
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]

def main():
    from sgar_mvp.src.skill_package_identity import skill_package_fingerprint
    from sgar_mvp.src.control_role_policy import load_control_role_policy
    from sgar_mvp.src.retrieval_policy import RetrievalPolicy
    from sgar_mvp.src.model_accounting import ModelPricingCatalog
    catalog = json.loads((ROOT / "Pool/resources/json/combine.json").read_text())
    by_id = {x["resource_id"]: x for x in catalog}
    assert len(by_id) == len(catalog), "duplicate resource ID"
    selected = json.loads((ROOT / "sgar_mvp/config/candidate_pool.json").read_text())
    assert set(selected["resource_ids"]) <= set(by_id), "missing configured resource"
    assert dict(Counter(by_id[x]["resource_type"] for x in selected["resource_ids"])) == selected["counts"]
    checked_packages = 0
    checked_files = 0
    for item in catalog:
        uri = str((item.get("execution") or {}).get("uri") or "")
        if not uri.startswith("file://"):
            continue
        path = (ROOT / uri[7:]).resolve()
        assert path.is_relative_to(ROOT) and path.is_file(), item["resource_id"]
        declared = (item.get("provenance") or {}).get("source_hash")
        if declared:
            assert declared == "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(), item["resource_id"]
        checked_files += 1
        if item["resource_type"] == "Skill":
            fingerprint, _ = skill_package_fingerprint(path.parent)
            assert item["provenance"]["package_hash"] == "sha256:" + fingerprint, item["resource_id"]
            checked_packages += 1
    control = load_control_role_policy(ROOT / "sgar_mvp/config/control_role_policy.json")
    lock = json.loads((ROOT / "Pool/resources/json/skills.lock.json").read_text())
    for package in lock["packages"]:
        if package["resource_id"] in by_id:
            assert package["package_hash"] == by_id[package["resource_id"]]["provenance"]["package_hash"], package["resource_id"]
    bundles_path = ROOT / "sgar_mvp/config/external_python_bundles.json"
    for bundle in json.loads(bundles_path.read_text())["bundles"]:
        archive = (bundles_path.parent / bundle["archive"]).resolve()
        assert archive.is_relative_to(ROOT) and archive.is_file()
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == bundle["sha256"]
    RetrievalPolicy.model_validate(json.loads((ROOT / "configs/retrieval_policy.example.json").read_text()))
    ModelPricingCatalog.from_manifest_file(ROOT / "Pool/resources/json/combine.json",
        required_model_refs=tuple(dict.fromkeys(x.api_model_id for x in control.roles)))
    print(json.dumps({"status": "passed", "catalog_resources": len(catalog),
        "configured_candidates": selected["counts"], "implementation_files_checked": checked_files,
        "skill_packages_checked": checked_packages, "provider_requests": 0}, indent=2))

if __name__ == "__main__":
    main()
