import json
import shutil
from pathlib import Path

from scripts.migration_check import ROOT, inspect


def test_source_readiness_does_not_claim_online_verification():
    report = inspect(ROOT, stage="source", backend="docker", environment={})
    assert report["status"] == "passed"
    assert report["live_probes_performed"] is False
    assert report["end_to_end_verified"] is False


def test_configured_check_does_not_print_environment_secrets():
    report = inspect(ROOT, stage="configured", backend="docker", environment={
        "LLM_API_KEY": "sentinel-model-credential", "LLM_BASE_URL": "https://private-gateway.invalid/v1",
        "SGAR_EMBEDDING_API_KEY": "sentinel-embedding-credential"})
    text = json.dumps(report)
    assert "sentinel-" not in text
    assert "private-gateway" not in text
    assert report["status"] == "incomplete"  # No live preparation receipts are bundled.


def test_model_profile_mismatch_is_detected(tmp_path):
    for name in ["Pool/resources/json/combine.json", "sgar_mvp/config/candidate_pool.json",
                 "sgar_mvp/config/control_role_policy.json", "sgar_mvp/config/model_profile.json"]:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    profile = tmp_path / "sgar_mvp/config/model_profile.json"
    payload = json.loads(profile.read_text(encoding="utf-8"))
    payload["roles"][0]["api_model_id"] = "different-model"
    profile.write_text(json.dumps(payload), encoding="utf-8")
    report = inspect(tmp_path, stage="source", backend="docker", environment={})
    checks = {row["name"]: row["passed"] for row in report["checks"]}
    assert checks["control_profile_matches_policy"] is False
    assert checks["control_models_registered"] is False
