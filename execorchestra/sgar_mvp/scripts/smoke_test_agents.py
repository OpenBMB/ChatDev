"""Run low-cost real Agent calls and one unified resource-plan smoke test.

The report intentionally stores no API key.  It records the explicit
Agent-to-Model binding, real outputs, timings, retry data, and the unified plan
trace so the run can be audited before formal experiments.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SGAR_ROOT = PROJECT_ROOT / "sgar_mvp"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sgar_mvp.src.executors import AgentExecutor
from sgar_mvp.src.orchestrator import DAGOrchestrator
from sgar_mvp.src.schema import (
    ArtifactType,
    ManifestType,
    ResourceApplicationPlan,
    ResourceApplicationStep,
    ResourceUsageDecision,
    Subtask,
    TypedResourceRef,
)


DEFAULT_MODEL_RESOURCE_ID = "model.gpt_5_4.v1"
MODEL_HEALTH_PATH = SGAR_ROOT / "runtime_state" / "model_ready_state.json"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _resource_type(raw: dict[str, Any]) -> str:
    return str(raw.get("resource_type") or raw.get("type", {}).get("resource_type") or "")


def _model_api_id(raw: dict[str, Any]) -> str:
    return str(
        raw.get("type_specific", {}).get("model", {}).get("model_id")
        or raw.get("execution", {}).get("model_id")
        or ""
    )


def _load_env_value(*names: str) -> str:
    values: dict[str, str] = {}
    env_file = PROJECT_ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    for name in names:
        value = os.environ.get(name, "").strip() or values.get(name, "")
        if value:
            return value
    return ""


def _require_live_model(resource_id: str, model_api_id: str) -> None:
    if not MODEL_HEALTH_PATH.is_file():
        raise RuntimeError("Fresh model health gate is required before Agent smoke tests")
    health = _load_json(MODEL_HEALTH_PATH)
    probe = next(
        (
            item
            for item in health.get("models", [])
            if item.get("resource_id") == resource_id or item.get("model_id") == model_api_id
        ),
        None,
    )
    ready_state = probe.get("ready_state") if isinstance(probe, dict) else None
    if (
        not probe
        or probe.get("status") != "ok"
        or not probe.get("text_ok")
        or not isinstance(ready_state, dict)
        or ready_state.get("status") != "ready"
    ):
        raise RuntimeError(
            f"Agent control Model has no successful fresh text probe: {resource_id} ({model_api_id})"
        )


def _runtime_config() -> tuple[str, str]:
    config = _load_json(SGAR_ROOT / "config.json")
    settings = config.get("llm_settings", {})
    api_key = _load_env_value("LLM_API_KEY", "OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("LLM_API_KEY is not configured in the environment or .env")
    base_url = _load_env_value("LLM_BASE_URL", "OPENAI_BASE_URL") or str(
        settings.get("base_url") or ""
    ).strip()
    if not base_url:
        raise RuntimeError("llm_settings.base_url is missing")
    return api_key, base_url


async def _run_agent_matrix(
    agents: list[dict[str, Any]],
    *,
    api_key: str,
    base_url: str,
    model_api_id: str,
    concurrency: int,
    max_tokens: int,
) -> list[dict[str, Any]]:
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def run_one(manifest: dict[str, Any]) -> dict[str, Any]:
        agent_id = str(manifest["resource_id"])
        executor = AgentExecutor(
            api_key=api_key,
            base_url=base_url,
            model="must-not-be-used-as-agent-fallback",
            project_root=str(PROJECT_ROOT),
        )
        async with semaphore:
            result = await executor.execute(
                (
                    "In at most 20 words, state your role and one concrete deliverable "
                    "you can produce. Do not claim any Tool was run."
                ),
                "",
                agent_manifest=manifest,
                agent_id=agent_id,
                base_model=model_api_id,
                dependencies=[],
                bound_inputs={},
                artifact_type="plaintext",
                expected_output="One non-empty sentence of at most 20 words.",
                max_retries=1,
                max_tokens=max_tokens,
                temperature=0.0,
            )
        return {
            "agent_id": agent_id,
            "bound_model_api_id": model_api_id,
            "success": result.is_success and bool(result.output_data.strip()),
            "output": result.output_data,
            "error": result.error_log,
            "cost_metric": result.cost_metric,
        }

    return await asyncio.gather(*(run_one(manifest) for manifest in agents))


async def _run_joint_plan(
    *,
    api_key: str,
    base_url: str,
    model_resource_id: str,
    model_api_id: str,
    resource_index: dict[str, dict[str, Any]],
    run_dir: Path,
) -> dict[str, Any]:
    skill_id = "skill.superpowers.writing-plans.v1"
    evidence_tool_id = "tool.markdown_table_extractor.v1"
    agent_id = "agent.backend_architecture_expert.v1"
    selected_ids = [
        skill_id,
        evidence_tool_id,
        agent_id,
        model_resource_id,
    ]
    refs = [
        TypedResourceRef(
            resource_id=skill_id,
            resource_type=ManifestType.SKILL,
            candidate_origin="smoke_test",
        ),
        TypedResourceRef(
            resource_id=evidence_tool_id,
            resource_type=ManifestType.TOOL,
            candidate_origin="smoke_test",
        ),
        TypedResourceRef(
            resource_id=agent_id,
            resource_type=ManifestType.AGENT,
            candidate_origin="smoke_test",
        ),
        TypedResourceRef(
            resource_id=model_resource_id,
            resource_type=ManifestType.MODEL,
            base_model=model_api_id,
            candidate_origin="smoke_test",
        ),
    ]
    plan = ResourceApplicationPlan(
        is_sufficient=True,
        selected_resource_ids=selected_ids,
        resource_usage=[
            ResourceUsageDecision(
                resource_id=skill_id,
                decision="use",
                use_as="planning_hint",
                attached_to_steps=["agent_step"],
                reason="Provide a real system-planning method hint.",
            ),
            ResourceUsageDecision(
                resource_id=evidence_tool_id,
                decision="use",
                use_as="intermediate_evidence",
                attached_to_steps=["agent_step"],
                reason="Produce real structured evidence before Agent synthesis.",
            ),
            ResourceUsageDecision(
                resource_id=agent_id,
                decision="use",
                use_as="executable_step",
                attached_to_steps=["agent_step"],
                reason="Apply the backend architecture role to the bound evidence.",
            ),
            ResourceUsageDecision(
                resource_id=model_resource_id,
                decision="use",
                use_as="agent_base_model",
                attached_to_steps=["agent_step"],
                reason="Provide the explicitly selected Agent runtime Model.",
            ),
        ],
        steps=[
            ResourceApplicationStep(
                step_id="load_planning_hint",
                step_type="apply_skill_hint",
                resource_id=skill_id,
                intent="Load the selected planning method for the Agent step.",
                input_bindings={},
                output_key="planning_hint",
            ),
            ResourceApplicationStep(
                step_id="extract_table",
                step_type="run_tool",
                resource_id=evidence_tool_id,
                intent="Extract a real table as intermediate execution evidence.",
                input_bindings={
                    "file_path": {
                        "literal": "sgar_mvp/tests/fixtures/agent_composition_input.md"
                    }
                },
                output_key="table_evidence",
                expected_output_contract={"artifact_type": "json"},
            ),
            ResourceApplicationStep(
                step_id="agent_step",
                step_type="call_agent",
                resource_id=agent_id,
                intent="Synthesize a concise architecture note from only bound inputs.",
                input_bindings={
                    "base_model": {"resource_id": model_resource_id},
                    "method": {"output_key": "planning_hint"},
                    "evidence": {"output_key": "table_evidence"},
                },
                output_key="agent_result",
                expected_output_contract={"artifact_type": "markdown"},
            ),
        ],
        final_output_from="agent_result",
        reason=(
            "Load method guidance, execute a real evidence Tool, bind both outputs "
            "to one Agent and return its explicitly bound result."
        ),
    )
    subtask = Subtask(
        id="agent_joint_smoke",
        role="Backend Architect",
        description=(
            "Produce a concise Markdown architecture note grounded only in the bound "
            "planning hint and extracted table evidence."
        ),
        expected_output=(
            "Markdown with headings for Inputs Used, Proposed Boundaries, and Verification."
        ),
        artifact_type=ArtifactType.MARKDOWN,
    )
    orchestrator = DAGOrchestrator(
        llm_api_key=api_key,
        llm_base_url=base_url,
        model=model_api_id,
        artifact_dir=str(run_dir / "joint_artifacts"),
        trace_path=str(run_dir / "joint_trace.jsonl"),
        max_same_bundle_repair_attempts=0,
        allow_plan_recovery=False,
    )
    ok, failure_type, failure_reason, bindings = orchestrator.preflight_application_plan(
        plan,
        refs,
        refs,
        resource_index,
        subtask,
        "",
    )
    if not ok:
        return {
            "success": False,
            "phase": "preflight",
            "failure_type": failure_type,
            "failure_reason": failure_reason,
            "plan": plan.model_dump(mode="json"),
        }

    result = await orchestrator._execute_application_plan(
        subtask.id,
        plan,
        refs,
        subtask.description,
        "",
        subtask.artifact_type.value,
        subtask.expected_output,
        resource_index,
        bindings,
    )
    trace = result.cost_metric.get("application_step_trace", [])
    agent_steps = [item for item in trace if item.get("step_id") == "agent_step"]
    explicit_binding_ok = bool(
        agent_steps
        and agent_steps[0].get("base_model_resource_id") == model_resource_id
        and agent_steps[0].get("base_model") == model_api_id
    )
    no_independent_model_call = not any(
        item.get("resource_id") == model_resource_id for item in trace
    )
    return {
        "success": bool(result.is_success and explicit_binding_ok and no_independent_model_call),
        "phase": "execution",
        "explicit_agent_model_binding": explicit_binding_ok,
        "model_not_independently_executed": no_independent_model_call,
        "output": result.output_data,
        "error": result.error_log,
        "cost_metric": result.cost_metric,
        "plan": plan.model_dump(mode="json"),
    }


async def _main(args: argparse.Namespace) -> int:
    api_key, base_url = _runtime_config()
    json_dir = PROJECT_ROOT / "Pool" / "resources" / "json"
    agents = _load_json(json_dir / "agents.json")
    combined = _load_json(json_dir / "combine.json")
    resource_index = {
        item["resource_id"]: item
        for item in combined
        if isinstance(item, dict) and item.get("resource_id")
    }
    model = resource_index.get(args.model_resource_id)
    if not model or _resource_type(model) != "Model":
        raise RuntimeError(f"Unknown Model resource: {args.model_resource_id}")
    model_api_id = _model_api_id(model)
    if not model_api_id:
        raise RuntimeError(f"Model resource has no real API model ID: {args.model_resource_id}")
    _require_live_model(args.model_resource_id, model_api_id)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(
        args.output_dir
        or SGAR_ROOT / "execution_outputs" / "agent_smoke" / f"run_{timestamp}"
    )
    run_dir.mkdir(parents=True, exist_ok=True)

    selected_agents = agents
    if args.agent_id:
        requested = set(args.agent_id)
        selected_agents = [item for item in agents if item.get("resource_id") in requested]
        found = {str(item.get("resource_id")) for item in selected_agents}
        if found != requested:
            raise RuntimeError(f"Unknown Agent resources: {sorted(requested - found)}")

    matrix_results: list[dict[str, Any]] = []
    if not args.skip_agent_matrix:
        matrix_results = await _run_agent_matrix(
            selected_agents[: args.limit],
            api_key=api_key,
            base_url=base_url,
            model_api_id=model_api_id,
            concurrency=args.concurrency,
            max_tokens=args.max_tokens,
        )

    joint_result: dict[str, Any] = {"skipped": True}
    if not args.skip_joint_plan:
        joint_result = await _run_joint_plan(
            api_key=api_key,
            base_url=base_url,
            model_resource_id=args.model_resource_id,
            model_api_id=model_api_id,
            resource_index=resource_index,
            run_dir=run_dir,
        )

    report = {
        "timestamp_utc": timestamp,
        "base_url": base_url,
        "model_resource_id": args.model_resource_id,
        "model_api_id": model_api_id,
        "agent_matrix": matrix_results,
        "joint_plan": joint_result,
    }
    report_path = run_dir / "report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    latest_path = SGAR_ROOT / "execution_outputs" / "agent_smoke" / "agent_smoke_latest.json"
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    if report_path.resolve() != latest_path.resolve():
        shutil.copyfile(report_path, latest_path)
    matrix_ok = all(item["success"] for item in matrix_results)
    joint_ok = bool(joint_result.get("skipped") or joint_result.get("success"))
    print(
        f"Agent matrix: {sum(item['success'] for item in matrix_results)}/"
        f"{len(matrix_results)} successful"
    )
    print(f"Joint plan: {'successful' if joint_ok else 'failed'}")
    print(f"Report: {report_path}")
    return 0 if matrix_ok and joint_ok else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-resource-id", default=DEFAULT_MODEL_RESOURCE_ID)
    parser.add_argument("--agent-id", action="append")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--max-tokens", type=int, default=64)
    parser.add_argument("--output-dir")
    parser.add_argument("--skip-agent-matrix", action="store_true")
    parser.add_argument("--skip-joint-plan", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main(parse_args())))
