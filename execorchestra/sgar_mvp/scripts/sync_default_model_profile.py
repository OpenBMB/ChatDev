"""Project the human-edited default model profile into runtime policy files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sgar_mvp.src.control_role_policy import (
    CONTROL_ROLE_POLICY_PROTOCOL,
    load_control_model_profile,
)
from sgar_mvp.src.retrieval_policy import load_retrieval_policy


ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = ROOT / "sgar_mvp/config/model_profile.json"
POLICY_PATH = ROOT / "sgar_mvp/config/control_role_policy.json"
RETRIEVAL_PATH = ROOT / "sgar_mvp/config/retrieval_policy.json"
CONFIG_PATH = ROOT / "sgar_mvp/config.json"


def _write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def projected_payloads() -> dict[Path, dict]:
    profile = load_control_model_profile(PROFILE_PATH)
    policy = profile.policy(protocol=CONTROL_ROLE_POLICY_PROTOCOL)
    retrieval = load_retrieval_policy(RETRIEVAL_PATH)
    retrieval_payload = retrieval.model_dump(mode="json")
    profiler = profile.for_role("profiler")
    retrieval_payload["control_role_policy_sha256"] = policy.policy_sha256
    # The receipt loader compares every role identity and request hash against
    # the new policy, so an old receipt remains fail-closed until refreshed.
    retrieval_payload["hyde"].update(
        {
            "generation_protocol": "sgar-profiler-generation-policy-v3",
            "resource_id": profiler.resource_id,
            "api_model_id": profiler.api_model_id,
            "reasoning_effort": profiler.reasoning_effort,
            "temperature": profiler.temperature,
        }
    )
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    planner = profile.for_role("planner")
    config["llm_settings"]["model"] = planner.api_model_id
    config["llm_settings"]["system_model_chain"] = [planner.api_model_id]
    config["llm_settings"]["evaluation_mode"] = profile.evaluation_mode
    config.setdefault("runtime_settings", {})["model_profile_path"] = (
        "sgar_mvp/config/model_profile.json"
    )
    return {
        POLICY_PATH: policy.model_dump(mode="json"),
        RETRIEVAL_PATH: retrieval_payload,
        CONFIG_PATH: config,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = projected_payloads()
    mismatches = [
        str(path.relative_to(ROOT))
        for path, payload in expected.items()
        if json.loads(path.read_text(encoding="utf-8-sig")) != payload
    ]
    if args.check:
        if mismatches:
            raise RuntimeError("default_model_profile_out_of_sync:" + ",".join(mismatches))
        print("default model profile is synchronized")
        return 0
    for path, payload in expected.items():
        _write(path, payload)
    print("synchronized default model profile; refresh control receipt before running")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
