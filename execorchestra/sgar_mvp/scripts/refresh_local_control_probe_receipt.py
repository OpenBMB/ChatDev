"""Refresh selected control-role receipts for the current Git checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import shutil

from sgar_mvp.main import load_config
from sgar_mvp.scripts.run_release_provider_probes import release_probe_specs
from sgar_mvp.src.control_role_policy import load_control_role_policy
from sgar_mvp.src.local_control_readiness import load_git_control_probe_receipt
from sgar_mvp.src.model_accounting import ModelCostPolicy, ModelPricingCatalog, RunCostLedger
from sgar_mvp.src.model_response_contracts import validate_structured_response_content
from sgar_mvp.src.model_transport import create_production_model_transport_bundle
from sgar_mvp.src.pipeline_control import canonical_json_bytes, canonical_sha256
from sgar_mvp.src.provider_reasoning import observe_provider_reasoning
from sgar_mvp.src.release_provider_receipt import (
    load_and_verify_release_provider_probe_receipt,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RECEIPT_PATH = PROJECT_ROOT / "sgar_mvp/runtime_state/control_role_probe_receipt.json"


def _verified_parent(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    claimed = str(payload.get("result_sha256") or "")
    unsigned = dict(payload)
    unsigned.pop("result_sha256", None)
    if claimed != canonical_sha256(unsigned):
        raise RuntimeError("local_control_parent_receipt_hash_mismatch")
    if payload.get("status") != "passed" or not payload.get("endpoint_identity_sha256"):
        raise RuntimeError("local_control_parent_receipt_invalid")
    return payload


def _response_content(response: object) -> str:
    choices = getattr(response, "choices", None)
    content = getattr(getattr(choices[0], "message", None), "content", None) if choices else None
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("control_probe_response_content_missing")
    return content


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cost-limit-usd", type=Decimal, default=Decimal("10"))
    parser.add_argument("--role", action="append", choices=("profiler", "planner", "plan_compiler", "plan_adaptation", "evaluator"))
    parser.add_argument("--receipt-path", type=Path, default=RECEIPT_PATH)
    parser.add_argument("--parent-receipt-path", type=Path, default=RECEIPT_PATH)
    parser.add_argument(
        "--control-role-policy",
        type=Path,
        default=PROJECT_ROOT / "sgar_mvp/config/control_role_policy.json",
    )
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "sgar_mvp/config.json")
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError("control_probe_output_directory_not_empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    responses_dir = output_dir / "responses"
    responses_dir.mkdir()

    receipt_path = args.receipt_path.resolve()
    parent = _verified_parent(args.parent_receipt_path.resolve())
    role_policy = load_control_role_policy(args.control_role_policy.resolve())
    registered_roles = tuple(item.role for item in role_policy.roles)
    specs = release_probe_specs(role_policy)
    if tuple(item["role"] for item in specs) != registered_roles:
        raise RuntimeError("control_probe_registry_spec_mismatch")
    requested = tuple(dict.fromkeys(args.role or registered_roles))
    selected_roles = tuple(role for role in registered_roles if role in requested)
    if not selected_roles or len(selected_roles) != len(requested):
        raise RuntimeError("control_probe_selected_roles_invalid")
    parent_by_role = {item["role"]: item for item in parent.get("records", [])}
    if set(parent_by_role) != set(registered_roles):
        raise RuntimeError("control_probe_parent_roles_invalid")
    for spec in specs:
        role = spec["role"]
        if role in selected_roles:
            continue
        inherited = parent_by_role[role]
        expected_fields = {
            "request_sha256": spec["request_sha256"],
            "request_policy_sha256": spec["request_policy_sha256"],
            "prompt_sha256": spec["prompt_sha256"],
            "schema_sha256": spec["requirement"].schema_sha256,
        }
        if any(inherited.get(name) != value for name, value in expected_fields.items()):
            raise RuntimeError(f"control_probe_inherited_role_stale:{role}")

    config = load_config(str(args.config.resolve()))
    api_key = str(config.get("llm_key") or "").strip()
    if not api_key or api_key.startswith("${") or api_key == "your_api_key_here":
        raise RuntimeError("control_probe_credential_missing")
    base_url = str((config.get("llm_settings") or {}).get("base_url") or "").strip()
    bundle = create_production_model_transport_bundle(api_key=api_key, base_url=base_url)
    if parent.get("endpoint_identity_sha256") != bundle.endpoint_identity.identity_sha256:
        raise RuntimeError("control_probe_parent_endpoint_mismatch")
    catalog = ModelPricingCatalog.from_manifest_file(
        PROJECT_ROOT / "Pool/resources/json/combine.json",
        required_model_refs=tuple(dict.fromkeys(item.api_model_id for item in role_policy.roles)),
    )
    ledger = RunCostLedger(
        catalog=catalog,
        policy=ModelCostPolicy(
            mode="stop_after_limit",
            warning_usd=args.cost_limit_usd,
            limit_usd=args.cost_limit_usd,
        ),
        output_dir=output_dir,
        run_id="local-control-probe-refresh",
    )
    records = []
    try:
        for spec in specs:
            if spec["role"] not in selected_roles:
                records.append(parent_by_role[spec["role"]])
                continue
            request = dict(spec["request"])
            requirement = spec["requirement"]
            context = ledger.new_operation(
                stage=spec["accounting_stage"],
                selected_resource_id=spec["model_resource_id"],
                model_resource_id=spec["model_resource_id"],
                request_policy_sha256=spec["request_policy_sha256"],
                reasoning_effort=spec["reasoning_effort"],
            )
            response = bundle.sync.send(ledger=ledger, context=context, **request)
            content = _response_content(response)
            (responses_dir / f"{spec['role']}.txt").write_text(content, encoding="utf-8")
            validate_structured_response_content(
                content,
                requirement=requirement,
                mode="native_strict_schema",
            )
            finish_reason = str(getattr(response.choices[0], "finish_reason", "") or "")
            if finish_reason != "stop":
                raise RuntimeError(f"control_probe_finish_reason_invalid:{spec['role']}")
            usage = getattr(response, "usage", None)
            reasoning = observe_provider_reasoning(response)
            records.append(
                {
                    "role": spec["role"],
                    "schema_role": spec["schema_role"],
                    "request_sha256": spec["request_sha256"],
                    "request_policy_sha256": spec["request_policy_sha256"],
                    "prompt_sha256": spec["prompt_sha256"],
                    "requirement_sha256": requirement.requirement_sha256,
                    "wire_schema_sha256": requirement.wire_schema_sha256,
                    "reasoning_effort": spec["reasoning_effort"],
                    "temperature": spec["temperature"],
                    "model_resource_id": spec["model_resource_id"],
                    "api_model_id": spec["api_model_id"],
                    "endpoint_identity_sha256": bundle.endpoint_identity.identity_sha256,
                    "schema_sha256": requirement.schema_sha256,
                    "response_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                    "response_identity_sha256": hashlib.sha256(
                        content.encode("utf-8")
                    ).hexdigest(),
                    "provider_request_id": str(getattr(response, "id", "") or "") or None,
                    "finish_reason": finish_reason,
                    "usage": usage.model_dump(mode="json") if hasattr(usage, "model_dump") else usage,
                    "provider_reasoning_observation": reasoning.model_dump(mode="json"),
                    "accounting_reference": getattr(response, "accounting_reference", None),
                }
            )
    finally:
        accounting = ledger.close()

    payload = {
        "protocol": "sgar-local-control-probe-refresh-v1",
        "status": "passed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider_request_count": len(selected_roles),
        "endpoint_identity_sha256": bundle.endpoint_identity.identity_sha256,
        "registered_roles": list(registered_roles),
        "refreshed_roles": list(selected_roles),
        "records": records,
        "accounting_summary": accounting,
        "parent_receipt": parent,
        "provider_reasoning_plaintext_persisted": False,
    }
    payload["result_sha256"] = canonical_sha256(payload)
    candidate = output_dir / "control_role_probe_receipt.json"
    candidate.write_bytes(canonical_json_bytes(payload) + b"\n")
    load_and_verify_release_provider_probe_receipt(
        candidate,
        expected_endpoint_identity_sha256=bundle.endpoint_identity.identity_sha256,
        control_role_policy=role_policy,
    )
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = receipt_path.with_name(receipt_path.name + ".next")
    shutil.copyfile(candidate, temporary)
    temporary.replace(receipt_path)
    loaded_path, loaded = load_git_control_probe_receipt(
        PROJECT_ROOT,
        config=config,
        expected_endpoint_identity_sha256=bundle.endpoint_identity.identity_sha256,
        control_role_policy=role_policy,
    )
    validation = {
        "protocol": "sgar-local-control-receipt-refresh-result-v1",
        "status": "passed",
        "receipt_path": str(loaded_path),
        "result_sha256": loaded["result_sha256"],
        "registered_roles": list(registered_roles),
        "provider_request_count": len(selected_roles),
        "accounting_summary": accounting,
        "records": records,
    }
    (output_dir / "validation.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
