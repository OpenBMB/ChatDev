"""External-substrate wiring probe; does not run Planner or solve a task."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from .executors import DumbExecutor, HostPythonExecutor
from .runtime_abstraction import RuntimeInjectionError, runtime_binding
from .resource_runtime import ResourceDefinition
from .resource_runtime import (
    ExecutionWorldDescriptor,
    ResourceCallRequest,
    ResourceExecutionContext,
    ResourceRuntime,
)
from .execution_events import RunExecutionLedger
from .pipeline_control import canonical_sha256
from .formal_contracts import MaterialDescriptorV1
from .tool_execution_provider import PreparedToolDispatch, ToolExecutionProvider


async def verify_contract(runtime):
    root = Path(__file__).resolve().parents[2]
    manifest_path = root / "Pool/resources/tools/registry/python_script/python_script_runner.json"
    manifest = json.loads(manifest_path.read_text())
    definition = ResourceDefinition.from_manifest(manifest)
    source = root / "Pool/resources/tools/script/python_script_runner.py"
    source_text = source.read_bytes().decode("utf-8")
    scratch = "/app/.sgar-runtime-probe-" + hashlib.sha256(runtime.runtime_id.encode()).hexdigest()[:12]
    generated = "from pathlib import Path\nPath('payload.txt').write_text('step-a-artifact\\n', encoding='utf-8')\n"
    consumer = "from pathlib import Path\nvalue=Path('payload.txt').read_text(encoding='utf-8')\nPath('consumed.txt').write_text('consumed:'+value, encoding='utf-8')\n"
    checks = {}
    try:
        await runtime.write_text(scratch + "/runner.py", source_text)
        await runtime.write_text(scratch + "/generated.py", generated)
        await runtime.write_text(scratch + "/consumer.py", consumer)
        prepared = PreparedToolDispatch(
            subtask_description="RUNTIME_CONTRACT_TEST_ONLY", context_data="",
            dispatch_locator=definition.entrypoint("invoke").dispatch,
            command="python3", args=(scratch + "/runner.py", scratch + "/generated.py", "--cwd", scratch),
            execution_substrate_mode="external", runtime_kind="python_script", timeout_sec=30,
            runtime_environment={"image_id": "external-current-trial:" + runtime.trial_id},
        )
        provider = ToolExecutionProvider(prepared, execution_substrate=runtime)
        request = SimpleNamespace(
            resource_definition=definition, entrypoint_id="invoke",
            execution_world=provider.execution_world, call_id="contract-tool-call",
            output_contract=definition.entrypoint("invoke").output_contract,
            logical_step_id="step-a-produce", depends_on=(),
            resolved_bindings={"output_artifact": scratch + "/payload.txt"},
        )
        with runtime_binding(runtime, mode="external"):
            result = await provider(request)
            checks["provider_success"] = str(result.status.value) == "success"
            consumer_prepared = PreparedToolDispatch(
                subtask_description="RUNTIME_CROSS_STEP_DATAFLOW_TEST", context_data="",
                dispatch_locator=definition.entrypoint("invoke").dispatch,
                command="python3", args=(scratch + "/runner.py", scratch + "/consumer.py", "--cwd", scratch),
                execution_substrate_mode="external", runtime_kind="python_script", timeout_sec=30,
                runtime_environment={"image_id": "external-current-trial:" + runtime.trial_id},
            )
            consumer_provider = ToolExecutionProvider(consumer_prepared, execution_substrate=runtime)
            consumer_request = SimpleNamespace(
                resource_definition=definition, entrypoint_id="invoke",
                execution_world=consumer_provider.execution_world, call_id="step-b-consume",
                output_contract=definition.entrypoint("invoke").output_contract,
                logical_step_id="step-b-consume", depends_on=("step-a-produce",),
                resolved_bindings={"input_artifact": scratch + "/payload.txt"},
            )
            consumed = await consumer_provider(consumer_request)
            checks["cross_step_provider_success"] = str(consumed.status.value) == "success"
            for executor in (DumbExecutor(), HostPythonExecutor(str(root))):
                try:
                    await executor.execute("exit 0", "", args=[])
                except RuntimeInjectionError:
                    checks[type(executor).__name__ + "_blocked"] = True
                else:
                    checks[type(executor).__name__ + "_blocked"] = False
        checks["task_payload_readback"] = await runtime.read_text(scratch + "/payload.txt") == "step-a-artifact\n"
        checks["cross_step_consumed"] = await runtime.read_text(scratch + "/consumed.txt") == "consumed:step-a-artifact\n"
        checks["cross_step_same_task_state"] = any(
            item["request"].get("logical_step_id") == "step-b-consume"
            and item["request"].get("depends_on") == ["step-a-produce"]
            and item["request"].get("bindings", {}).get("input_artifact") == scratch + "/payload.txt"
            for item in runtime.records
        )
        checks["task_payload_exists"] = await runtime.exists(scratch + "/payload.txt")
        checks["missing_task_path"] = not await runtime.exists(scratch + "/absent")
        try:
            await runtime.read_text(str(root / "README.md"))
        except RuntimeInjectionError:
            checks["host_path_blocked"] = True
        checks["no_host_task_file"] = not Path(scratch).exists()
        checks["single_provider_dispatch"] = provider.dispatch_count == 1 and consumer_provider.dispatch_count == 1
        return {"classification": "RUNTIME_INJECTION_CONTRACT_ONLY_NOT_RARE_TF",
                "checks": checks, "passed": all(checks.values()),
                "resource_id": definition.resource_id,
                "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                "wrapper_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "generated_payload_origin": "test-generated stand-in, NOT model generated",
                "resource_runtime_dependencies": "NOT_VALIDATED_BY_THIS_WIRING_PROBE",
                "provider_result": result.model_dump(mode="json"),
                "generation_calls": 0, "embedding_calls": 0,
                "dag": [{"step_id": "step-a-produce", "depends_on": [], "output": scratch + "/payload.txt"},
                        {"step_id": "step-b-consume", "depends_on": ["step-a-produce"],
                         "input_binding": scratch + "/payload.txt", "output": scratch + "/consumed.txt"}]}
    finally:
        runtime.call("exec_argv", argv=["python3", "-c", "import shutil; shutil.rmtree(" + repr(scratch) + ")"])


async def verify_production_contract(runtime, output_dir: str):
    """Exercise formal ResourceRuntime publication and downstream binding."""
    root = Path(__file__).resolve().parents[2]
    manifest_path = root / "Pool/resources/tools/registry/python_script/python_script_runner.json"
    manifest = json.loads(manifest_path.read_text())
    definition = ResourceDefinition.from_manifest(manifest)
    source = root / "Pool/resources/tools/script/python_script_runner.py"
    scratch = "/app/.sgar-production-probe-" + hashlib.sha256(runtime.runtime_id.encode()).hexdigest()[:12]
    generated = "from pathlib import Path\nPath('payload.txt').write_text('formal-artifact\\n', encoding='utf-8')\n"
    consumer = (
        "from pathlib import Path\n"
        f"value=Path({(scratch + '/payload.txt')!r}).read_text(encoding='utf-8')\n"
        "Path('consumed.txt').write_text('consumed:'+value, encoding='utf-8')\n"
    )
    await runtime.write_text(scratch + "/runner.py", source.read_text(encoding="utf-8"))
    await runtime.write_text(scratch + "/generated.py", generated)
    await runtime.write_text(scratch + "/consumer.py", consumer)
    ledger = RunExecutionLedger(output_dir=output_dir, run_id="production-contract-ledger")
    formal_runtime = ResourceRuntime(ledger=ledger)

    def request_for(step_id, script, depends_on, bindings, upstream=()):
        prepared = PreparedToolDispatch(
            subtask_description="FORMAL_PRODUCTION_MAPPING_PROBE", context_data="",
            dispatch_locator=definition.entrypoint("invoke").dispatch,
            command="python3", args=(scratch + "/runner.py", script, "--cwd", scratch),
            execution_substrate_mode="external", runtime_kind="python_script", timeout_sec=30,
            sandbox_scope=runtime.step_scope(step_id=step_id, depends_on=tuple(depends_on), attempt=1),
        )
        provider = ToolExecutionProvider(prepared, execution_substrate=runtime)
        request_world = prepared.execution_world()
        context = ResourceExecutionContext(
            run_id=runtime.runtime_id, graph_revision=0, subtask_id="production-probe",
            subtask_revision=0, candidate_pool_sha256=canonical_sha256([definition.resource_id]),
            candidate_resource_ids=(definition.resource_id,), selected_resource_ids=(definition.resource_id,),
            plan_sha256=canonical_sha256({"probe": "formal-production-mapping"}), step_id=step_id,
            attempt=1, sandbox_scope_sha256=request_world.sandbox_scope_sha256,
        )
        materials = tuple(
            MaterialDescriptorV1(
                source_id="artifact:" + handle.handle_id,
                logical_name=Path(handle.tool_path).name,
                artifact_type=handle.artifact_type,
                content_sha256=handle.provenance["content_sha256"],
                original_bytes=handle.provenance["byte_size"], included_bytes=0,
                coverage_status="handle_only", handle_id=handle.handle_id,
                runtime_path=handle.tool_path,
            )
            for handle in upstream
        )
        return ResourceCallRequest(
            resource_definition=definition, execution_context=context, resolved_bindings=dict(bindings),
            capability_operation_id="tool.python_script_runner.v1::python_execution",
            semantic_task_contract={"step_id": step_id, "depends_on": list(depends_on)},
            upstream_artifact_handles=tuple(upstream), acceptance_requirements=("Return declared JSON.",),
            execution_world=request_world, resource_native_output_contract=dict(definition.entrypoint("invoke").output_contract),
            target_output_contract=dict(definition.base_output_contract),
            authorized_materials=materials,
            provenance_source_ids=tuple(item.source_id for item in materials),
        ), provider

    first_request, first_provider = request_for(
        "step-a-produce", scratch + "/generated.py", (),
        {"script_path": scratch + "/generated.py", "args": [], "cwd": scratch},
    )
    first = await formal_runtime.execute(first_request, provider=first_provider)
    if first.status.value != "success" or not first.artifacts:
        raise RuntimeError("production_probe_artifact_publication_failed")
    handle = first.artifacts[0]
    second_request, second_provider = request_for(
        "step-b-consume", scratch + "/consumer.py", ("step-a-produce",),
        {"script_path": scratch + "/consumer.py", "args": [], "cwd": scratch}, (handle,),
    )
    second = await formal_runtime.execute(second_request, provider=second_provider)
    consumed = await runtime.read_text(scratch + "/consumed.txt")
    checks = {
        "formal_producer_success": first.status.value == "success",
        "task_backed_handle_published": bool(handle.tool_path) and not handle.host_path,
        "publication_hash_present": bool((handle.provenance or {}).get("content_sha256")),
        "formal_consumer_success": second.status.value == "success",
        "downstream_binding_consumed": consumed == "consumed:formal-artifact\n",
        "explicit_dependency": second_request.semantic_task_contract["depends_on"] == ["step-a-produce"],
        "no_host_mirror": not Path(scratch).exists(),
    }
    runtime.call("exec_argv", argv=["python3", "-c", "import shutil; shutil.rmtree(" + repr(scratch) + ")"])
    ledger.close()
    return {
        "classification": "HARBOR_PRODUCTION_ARTIFACT_MAPPING_CONTRACT_ONLY_NOT_RARE_TF",
        "checks": checks, "passed": all(checks.values()),
        "resource_id": definition.resource_id,
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "dag": [
            {"step_id": "step-a-produce", "depends_on": [], "artifact_handle": handle.model_dump(mode="json")},
            {"step_id": "step-b-consume", "depends_on": ["step-a-produce"], "input_binding": handle.tool_path},
        ],
    }
