"""Run exactly five admitted Sol release probes.

This command is intentionally separate from admission.  It requires an exact
operator authorization token, disables SDK retry, persists metering before each
send, and never writes provider-native reasoning plaintext.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sgar_mvp.main import load_config
from sgar_mvp.src.control_role_policy import ControlRolePolicyV1, load_control_role_policy
from sgar_mvp.src.model_accounting import (
    ModelCostPolicy,
    ModelPricingCatalog,
    RunCostLedger,
)
from sgar_mvp.src.model_response_contracts import (
    build_exact_schema_probe_request,
    system_role_requirement,
    validate_structured_response_content,
)
from sgar_mvp.src.model_transport import (
    create_production_model_transport_bundle,
    model_request_sha256,
)
from sgar_mvp.src.pipeline_control import canonical_json_bytes, canonical_sha256
from sgar_mvp.src.planner import DEFAULT_PLANNER_MAX_OUTPUT_TOKENS
from sgar_mvp.src.profiler_protocol import ProfilerProviderCapabilityV1
from sgar_mvp.src.provider_reasoning import observe_provider_reasoning
from sgar_mvp.src.release_environment import require_release_storage_path
from sgar_mvp.src.release_source_seal import (
    load_and_verify_source_seal,
    source_seal_reference,
)


AUTHORIZATION_TOKEN = "AUTHORIZED_RELEASE_PROBES_5"
RESULT_PROTOCOL = "sgar-release-control-provider-probes-v2"
CHECKPOINT_PROTOCOL = "sgar-release-control-provider-probe-checkpoint-v1"
FAILURE_PROTOCOL = "sgar-release-control-provider-probe-failure-v1"


def release_probe_specs(
    control_role_policy: ControlRolePolicyV1 | None = None,
) -> tuple[dict[str, Any], ...]:
    """Return the exact deterministic requests shared with cost admission."""

    control = control_role_policy or load_control_role_policy()
    definitions = (
        ("profiler", "hyde", "retrieval_format_probe", 16384),
        ("planner", "planner", "planner_decompose", DEFAULT_PLANNER_MAX_OUTPUT_TOKENS),
        ("plan_compiler", "plan_compiler", "plan_compiler", None),
        ("plan_adaptation", "plan_adaptation", "command_adaptation", None),
        ("evaluator", "evaluator", "evaluator", 8192),
    )
    records: list[dict[str, Any]] = []
    for public_role, schema_role, accounting_stage, cap in definitions:
        role_policy = control.for_role(public_role)  # type: ignore[arg-type]
        requirement = system_role_requirement(schema_role)
        request = build_exact_schema_probe_request(
            model_id=role_policy.api_model_id,
            requirement=requirement,
            request_fields=role_policy.request_fields(),
        )
        if cap is not None:
            request["max_tokens"] = cap
        if any(request.get(name) != value for name, value in role_policy.request_fields().items()):
            raise RuntimeError("release_probe_request_policy_invalid")
        records.append(
            {
                "role": public_role,
                "schema_role": schema_role,
                "accounting_stage": accounting_stage,
                "request_policy_sha256": role_policy.role_policy_sha256,
                "model_resource_id": role_policy.resource_id,
                "api_model_id": role_policy.api_model_id,
                "reasoning_effort": role_policy.reasoning_effort,
                "temperature": role_policy.temperature,
                "requirement": requirement,
                "request": request,
                "request_sha256": model_request_sha256(request),
                "prompt_sha256": canonical_sha256(request["messages"]),
            }
        )
    return tuple(records)


def _read_sealed_json(path: Path, *, hash_field: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    claimed = str(payload.get(hash_field) or "")
    unsigned = dict(payload)
    unsigned.pop(hash_field, None)
    if claimed != canonical_sha256(unsigned):
        raise RuntimeError(f"release_probe_{hash_field}_mismatch")
    return payload


def _response_content(response: Any) -> str:
    choices = getattr(response, "choices", None)
    if not choices:
        raise RuntimeError("release_probe_response_choices_missing")
    content = getattr(getattr(choices[0], "message", None), "content", None)
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("release_probe_response_content_missing")
    return content


def _finish_reason(response: Any) -> str:
    choices = getattr(response, "choices", None)
    value = getattr(choices[0], "finish_reason", None) if choices else None
    return str(value or "")


def _append_probe_checkpoint(
    path: Path,
    *,
    ordinal: int,
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Persist one validated probe before the runner can advance."""

    payload: dict[str, Any] = {
        "protocol": CHECKPOINT_PROTOCOL,
        "ordinal": int(ordinal),
        "role": str(record["role"]),
        "record": dict(record),
    }
    payload["checkpoint_sha256"] = canonical_sha256(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as handle:
        handle.write(canonical_json_bytes(payload) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())
    return payload


def _write_probe_failure(
    path: Path,
    *,
    completed_roles: list[str],
    failed_role: str | None,
    exc: BaseException,
    checkpoint_path: Path,
) -> None:
    failure_code = str(getattr(exc, "failure_code", "") or "").strip()
    if not failure_code:
        candidate = str(exc).split(":", 1)[0].strip()
        failure_code = (
            candidate
            if candidate
            and all(character.isalnum() or character in "_-" for character in candidate)
            else type(exc).__name__
        )
    payload: dict[str, Any] = {
        "protocol": FAILURE_PROTOCOL,
        "status": "failed",
        "completed_roles": list(completed_roles),
        "failed_role": failed_role,
        "exception_type": type(exc).__name__,
        "failure_code": failure_code,
        "checkpoint_file_sha256": (
            hashlib.sha256(checkpoint_path.read_bytes()).hexdigest()
            if checkpoint_path.is_file()
            else None
        ),
    }
    payload["failure_sha256"] = canonical_sha256(payload)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(canonical_json_bytes(payload) + b"\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admission", type=Path, required=True)
    parser.add_argument("--release-source-seal", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "sgar_mvp/config.json")
    parser.add_argument("--authorization-token", required=True)
    args = parser.parse_args()
    if args.authorization_token != AUTHORIZATION_TOKEN:
        raise RuntimeError("release_probe_explicit_authorization_missing")
    output = require_release_storage_path(
        args.output_dir, code="release_probe_output_outside_storage_root"
    )
    if output.exists() and any(output.iterdir()):
        raise RuntimeError("release_probe_output_directory_not_empty")
    output.mkdir(parents=True, exist_ok=True)

    seal = load_and_verify_source_seal(
        args.release_source_seal,
        project_root=PROJECT_ROOT,
        allowed_stages=("release",),
    )
    admission = _read_sealed_json(args.admission.resolve(), hash_field="admission_sha256")
    if (
        admission.get("protocol") != "sgar-release-probe-cost-admission-v2"
        or admission.get("admitted") is not True
        or admission.get("network_requests_authorized") is not False
        or int(admission.get("provider_request_count") or 0) != 5
        or int(admission.get("legal_automatic_retry_request_count", -1)) != 0
        or int(admission.get("disaster_upper_bound_provider_request_count") or 0)
        != 5
        or (admission.get("release_source_seal") or {}).get("seal_sha256")
        != seal.get("seal_sha256")
    ):
        raise RuntimeError("release_probe_admission_invalid")

    control_role_policy = load_control_role_policy()
    specs = release_probe_specs(control_role_policy)
    admitted_requests = {
        str(item["role"]): str(item["request_sha256"])
        for item in admission.get("probes") or ()
    }
    if admitted_requests != {
        str(item["role"]): str(item["request_sha256"]) for item in specs
    }:
        raise RuntimeError("release_probe_request_not_admitted")

    config = load_config(str(args.config.resolve()))
    configured_key = str((config or {}).get("llm_key") or "").strip()
    if (
        not config
        or not configured_key
        or configured_key.startswith("${")
        or configured_key == "your_api_key_here"
    ):
        raise RuntimeError("release_probe_credential_missing")
    settings = dict(config.get("llm_settings") or {})
    base_url = str(settings.get("base_url") or "https://api.openai.com/v1")
    bundle = create_production_model_transport_bundle(
        api_key=configured_key,
        base_url=base_url,
    )
    catalog = ModelPricingCatalog.from_manifest_file(
        PROJECT_ROOT / "Pool/resources/json/combine.json",
        required_model_refs=("gpt-5.6-sol",),
    )
    cost_limit = Decimal(str(admission["cost_limit_usd"]))
    ledger = RunCostLedger(
        catalog=catalog,
        policy=ModelCostPolicy(
            mode="stop_after_limit",
            warning_usd=cost_limit,
            limit_usd=cost_limit,
        ),
        output_dir=output,
        run_id=f"release-probes-{str(seal['seal_sha256'])[:16]}",
    )

    results: list[dict[str, Any]] = []
    checkpoint_path = output / "release_provider_probe_checkpoints.jsonl"
    failed_role: str | None = None
    try:
        for ordinal, item in enumerate(specs, start=1):
            failed_role = str(item["role"])
            request = dict(item["request"])
            context = ledger.new_operation(
                stage=item["accounting_stage"],
                selected_resource_id=item["model_resource_id"],
                model_resource_id=item["model_resource_id"],
                request_policy_sha256=item["request_policy_sha256"],
                reasoning_effort=item["reasoning_effort"],
            )
            response = bundle.sync.send(ledger=ledger, context=context, **request)
            content = _response_content(response)
            parsed = validate_structured_response_content(
                content,
                requirement=item["requirement"],
                mode="native_strict_schema",
            )
            del parsed
            finish_reason = _finish_reason(response)
            if finish_reason != "stop":
                raise RuntimeError(f"release_probe_finish_reason_invalid:{item['role']}")
            reasoning = observe_provider_reasoning(response)
            record = {
                "role": item["role"],
                "schema_role": item["schema_role"],
                "request_sha256": item["request_sha256"],
                "request_policy_sha256": item["request_policy_sha256"],
                "prompt_sha256": item["prompt_sha256"],
                "reasoning_effort": item["reasoning_effort"],
                "temperature": item["temperature"],
                "model_resource_id": item["model_resource_id"],
                "api_model_id": item["api_model_id"],
                "endpoint_identity_sha256": bundle.endpoint_identity.identity_sha256,
                "schema_sha256": item["requirement"].schema_sha256,
                "response_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "finish_reason": finish_reason,
                "usage": (
                    response.usage.model_dump(mode="json")
                    if getattr(response, "usage", None) is not None
                    and hasattr(response.usage, "model_dump")
                    else getattr(response, "usage", None)
                ),
                "provider_reasoning_observation": reasoning.model_dump(mode="json"),
                "accounting_reference": getattr(response, "accounting_reference", None),
            }
            _append_probe_checkpoint(
                checkpoint_path,
                ordinal=ordinal,
                record=record,
            )
            results.append(record)
            failed_role = None

        profiler = results[0]
        profiler_reasoning = profiler["provider_reasoning_observation"]
        capability = ProfilerProviderCapabilityV1(
            endpoint_identity_sha256=bundle.endpoint_identity.identity_sha256,
            transport_kind="chat_completions",
            resource_id=str(profiler["model_resource_id"]),
            api_model_id=str(profiler["api_model_id"]),
            supported_reasoning_efforts=(str(profiler["reasoning_effort"]),),
            accepted_output_cap=16384,
            accepted_response_mode="native_strict_schema",
            finish_reason_semantics={"stop": "complete", "length": "truncated"},
            reasoning_usage_available=(
                profiler_reasoning.get("reasoning_tokens") is not None
            ),
            reasoning_content_available=bool(profiler_reasoning.get("available")),
            probed_at=datetime.now(timezone.utc).isoformat(),
            probe_request_sha256=str(profiler["request_sha256"]),
            probe_response_sha256=str(profiler["response_sha256"]),
        )
        capability_path = output / "profiler_provider_capability.json"
        capability_path.write_bytes(
            canonical_json_bytes(capability.model_dump(mode="json")) + b"\n"
        )
        payload: dict[str, Any] = {
            "protocol": RESULT_PROTOCOL,
            "status": "passed",
            "provider_request_count": len(results),
            "release_source_seal": source_seal_reference(seal),
            "admission_sha256": admission["admission_sha256"],
            "endpoint_identity_sha256": bundle.endpoint_identity.identity_sha256,
            "pricing_catalog_sha256": catalog.pricing_catalog_sha256,
            "records": results,
            "checkpoint_file_sha256": hashlib.sha256(
                checkpoint_path.read_bytes()
            ).hexdigest(),
            "profiler_provider_capability_sha256": capability.capability_sha256,
            "provider_reasoning_plaintext_persisted": False,
        }
        payload["result_sha256"] = canonical_sha256(payload)
        (output / "release_provider_probe_results.json").write_bytes(
            canonical_json_bytes(payload) + b"\n"
        )
        print(output / "release_provider_probe_results.json")
        print(capability_path)
        return 0
    except BaseException as exc:
        _write_probe_failure(
            output / "release_provider_probe_failure.json",
            completed_roles=[str(item["role"]) for item in results],
            failed_role=failed_role,
            exc=exc,
            checkpoint_path=checkpoint_path,
        )
        raise
    finally:
        ledger.close()


if __name__ == "__main__":
    raise SystemExit(main())
