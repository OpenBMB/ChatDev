"""No-cost production activation gate for the formal SGAR runtime.

The gate constructs only OpenAI SDK clients backed by in-memory MockTransport.
It binds the already snapshotted request to immutable pool/index/policy
identities, validates every Tool and model execution surface, probes local
persistence, and optionally verifies the pre-existing Docker image with
networking disabled.  No real provider socket is permitted.
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import hashlib
import json
import os
import socket
import shutil
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping, Sequence

import httpx

from .artifact_lifecycle import ArtifactLifecycleStore
from .control_models import DEFAULT_SYSTEM_MODEL_CHAIN
from .case_neutrality import audit_production_case_neutrality
from .authorized_material import (
    AuthorizedMaterialSource,
    build_authorized_model_material_view,
    public_snapshot_identity,
)
from .evaluation_runtime import (
    EvaluationEventLedger,
    load_evaluator_policy,
    resolve_evaluator_model,
)
from .execution_events import RunExecutionLedger
from .full_generation import (
    FULL_GENERATION_PROMPT_SHA256,
    FULL_GENERATION_PROMPT_VERSION,
)
from .atomic_io import temporary_sibling_path
from .model_accounting import ModelPricingCatalog, RunCostLedger, load_model_cost_policy
from .model_transport import (
    ModelTransportCapabilityError,
    ProviderEndpointIdentity,
    SyncModelTransportPort,
    create_model_transport_bundle,
    model_request_sha256,
    production_model_endpoint_identity,
    require_async_model_transport,
    require_sync_model_transport,
)
from .model_response_contracts import (
    ExactCapabilityProbeService,
    ModelResponseContractError,
    StructuredResponseModeInput,
    minimal_json_schema_instance,
    normalize_structured_response_mode,
    system_role_requirement,
)
from .model_liveness import ModelLivenessProbeService
from .pipeline_control import SubtaskRevisionRef, canonical_json_bytes, canonical_sha256
from .payload_provenance import (
    PayloadProvenanceError,
    PayloadSourceRegistry,
    ProductionModelPayloadGuard,
)
from .planner_contracts import audit_planner_contract_gate
from .public_inputs import internal_metadata_layout_audit
from .formal_serialization import append_formal_jsonl
from .frozen_candidate_publication import persist_frozen_candidate_pool
from .input_compatibility import run_generic_input_compatibility_probe
from .internal_language import build_prompt_surface_registry, prompt_file_text
from .recovery_control import (
    RecoveryEventLedger,
    load_recovery_policy,
    resolve_system_full_generation_policy,
)
from .resource_loader import load_real_pool_with_index, load_resource_index_static
from .resource_runtime import (
    ExecutionWorldDescriptor,
    ResourceCallRequest,
    ResourceCallResult,
    ResourceCallStatus,
    ResourceDefinition,
    ResourceExecutionContext,
    ResourceRuntime,
)
from .retrieval_conformance import run_retrieval_conformance
from .retrieval_runtime import (
    RetrievalCoordinator,
    RetrievalRuntimeIdentity,
    build_retrieval_runtime_identity,
    typed_refs_from_frozen_pool,
)
from .schema import (
    ArtifactType,
    QueryRetrievalProfile,
    Subtask,
    SubtaskOutputContract,
    Vector,
)
from .module_identity import audit_canonical_module_identity
from .run_workspace import collect_run_ledger_evidence
from .runtime_requirements import scan_environment
from .secret_policy import validate_formal_secret_config
from .release_source_seal import (
    load_and_verify_source_seal,
    source_seal_reference,
)
from .structured_response_boundaries import (
    probe_structured_response_boundary_transport,
)
from .terminal_failure import (
    TerminalFailureEnvelope,
    highest_severity_terminal_failure,
)
from .task_invocation import (
    PreparedTaskInvocation,
    resolve_task_request,
    verify_prepared_task_invocation,
)


PRODUCTION_CONFORMANCE_PROTOCOL = "sgar-production-conformance-v3"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORMAL_RUNTIME_KINDS = ("python_script", "python_library", "rest_api", "mcp_server")
TERMINAL_REPORT_NAME = "framework_conformance.json"


class ProductionConformanceError(RuntimeError):
    """A no-cost activation invariant failed."""

    def __init__(self, failure_code: str) -> None:
        super().__init__(failure_code)
        self.failure_code = str(failure_code)
        self.failure_responsibility = "framework"
        self.failure_stage = "production_conformance"
        self.retryable = False
        self.response_received = False


_NETWORK_AUDIT_LOCK = threading.RLock()


class _NoNetworkAudit:
    """Count and reject Python socket construction during no-cost conformance."""

    def __init__(self) -> None:
        self.request_count = 0
        self._original_create_connection: Any = None
        self._original_getaddrinfo: Any = None

    def start(self) -> None:
        _NETWORK_AUDIT_LOCK.acquire()
        self._original_create_connection = socket.create_connection
        self._original_getaddrinfo = socket.getaddrinfo
        audit = self

        def blocked_create_connection(*_args: Any, **_kwargs: Any) -> Any:
            audit.request_count += 1
            raise ProductionConformanceError("conformance_network_request_forbidden")

        def blocked_getaddrinfo(*_args: Any, **_kwargs: Any) -> Any:
            audit.request_count += 1
            raise ProductionConformanceError("conformance_network_request_forbidden")

        socket.create_connection = blocked_create_connection
        socket.getaddrinfo = blocked_getaddrinfo

    def stop(self) -> None:
        if self._original_create_connection is not None:
            socket.create_connection = self._original_create_connection
            socket.getaddrinfo = self._original_getaddrinfo
            self._original_create_connection = None
            self._original_getaddrinfo = None
            _NETWORK_AUDIT_LOCK.release()


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = temporary_sibling_path(path)
    try:
        with temporary.open("xb") as handle:
            handle.write(canonical_json_bytes(payload))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _load_catalog(root: Path) -> tuple[list[Mapping[str, Any]], Path]:
    path = root / "Pool" / "resources" / "json" / "combine.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProductionConformanceError("resource_catalog_invalid") from exc
    if not isinstance(payload, list) or not all(isinstance(item, Mapping) for item in payload):
        raise ProductionConformanceError("resource_catalog_root_invalid")
    return payload, path


def _response_mode(
    manifest: Mapping[str, Any],
    configured: Any = None,
) -> StructuredResponseModeInput:
    if configured is not None:
        try:
            mode = normalize_structured_response_mode(str(configured))
        except ModelResponseContractError as exc:
            raise ProductionConformanceError(
                "formal_system_role_requires_exact_json_schema"
            ) from exc
        if mode != "native_strict_schema":
            raise ProductionConformanceError(
                "formal_system_role_requires_exact_json_schema"
            )
    del manifest
    return "native_strict_schema"


def _source_identity(root: Path) -> dict[str, Any]:
    paths = [root / "sgar_mvp" / "main.py", root / "sgar_mvp" / "real_case_batch.py"]
    paths.extend(sorted((root / "sgar_mvp" / "src").glob("*.py")))
    existing = sorted({path.resolve() for path in paths if path.is_file()})
    records = [
        {
            "locator": path.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in existing
    ]
    try:
        proc = subprocess.run(
            [
                "git",
                "status",
                "--porcelain=v1",
                "--",
                "sgar_mvp/main.py",
                "sgar_mvp/real_case_batch.py",
                "sgar_mvp/src",
                "sgar_mvp/config/real_case_acceptance.template.json",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        clean = proc.returncode == 0 and not proc.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        clean = False
    projection = {"files": records}
    return {
        "framework_source_sha256": canonical_sha256(projection),
        "framework_source_file_count": len(records),
        "framework_source_clean": clean,
    }


def framework_source_identity(project_root: str | Path = PROJECT_ROOT) -> dict[str, Any]:
    """Public, host-free source identity shared by readiness gates."""
    return _source_identity(Path(project_root).resolve())


def _formal_execution_call_graph(root: Path) -> dict[str, Any]:
    formal_path = root / "sgar_mvp" / "src" / "formal_execution.py"
    orchestrator_path = root / "sgar_mvp" / "src" / "orchestrator.py"
    formal_tree = ast.parse(formal_path.read_text(encoding="utf-8-sig"))
    orchestrator_tree = ast.parse(orchestrator_path.read_text(encoding="utf-8-sig"))

    forbidden_imports: list[str] = []
    for node in ast.walk(formal_tree):
        if isinstance(node, ast.ImportFrom) and any(
            token in str(node.module or "")
            for token in ("experiment_one", "gold", "validator")
        ):
            forbidden_imports.append(str(node.module))
        if isinstance(node, ast.Import):
            forbidden_imports.extend(
                alias.name
                for alias in node.names
                if any(token in alias.name for token in ("experiment_one", "gold", "validator"))
            )

    engine_nodes = [
        node
        for node in ast.walk(formal_tree)
        if isinstance(node, ast.ClassDef) and node.name == "SealedPlanExecutionEngine"
    ]
    if len(engine_nodes) != 1:
        raise ProductionConformanceError("formal_execution_engine_identity_invalid")
    called = {
        node.func.attr
        for node in ast.walk(engine_nodes[0])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    forbidden_calls = sorted(
        called
        & {
            "execute_application_plan",
            "_execute_application_plan",
            "_execute_legacy_resource_with_events",
            "_attempt_same_bundle_repair",
            "_execute_full_generative",
        }
    )
    orchestrator_calls = {
        node.func.attr
        for node in ast.walk(orchestrator_tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    return {
        "sealed_engine_present": True,
        "legacy_calls_from_sealed_engine": forbidden_calls,
        "forbidden_imports": sorted(set(forbidden_imports)),
        "orchestrator_sealed_entry_present": "execute_sealed_plan" in orchestrator_calls,
    }


def _adapt_resource_surfaces(
    catalog: Sequence[Mapping[str, Any]],
    effective_index: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    tools = [item for item in catalog if str(item.get("resource_type")) == "Tool"]
    failures: list[str] = []
    runtime_counts: dict[str, int] = {}
    for item in tools:
        resource_id = str(item.get("resource_id") or "")
        try:
            definition = ResourceDefinition.from_manifest(item)
            if definition.resource_id != resource_id:
                raise ProductionConformanceError("resource_definition_identity_mismatch")
            runtime = str((item.get("execution") or {}).get("runtime") or "unknown")
            runtime_counts[runtime] = runtime_counts.get(runtime, 0) + 1
        except Exception:
            failures.append(canonical_sha256(resource_id)[:16])

    synthetic: list[dict[str, Any]] = []
    for runtime in FORMAL_RUNTIME_KINDS:
        manifest = {
            "resource_id": f"synthetic.{runtime}",
            "resource_type": "Tool",
            "status": "active",
            "capability": {
                "summary": "Exercise one declared synthetic runtime adapter.",
                "operation_kinds": ["run_tool"],
            },
            "constraint": {"artifact_output": ["plaintext"]},
            "execution": {"runtime": runtime, "uri": f"memory://{runtime}/invoke"},
            "input_contract": [{"name": "value", "kind": "string", "required": False}],
            "output_contract": {"artifact_type": "plaintext"},
            "runtime_requirements": {"network_required": runtime == "rest_api"},
        }
        definition = ResourceDefinition.from_manifest(manifest)
        synthetic.append(
            {
                "runtime": runtime,
                "entrypoint_id": definition.entrypoints[0].entrypoint_id,
                "manifest_sha256": definition.manifest_sha256,
            }
        )
    return {
        "catalog_tool_count": len(tools),
        "effective_resource_count": len(effective_index),
        "adapted_tool_count": len(tools) - len(failures),
        "adaptation_failure_hashes": sorted(failures),
        "runtime_counts": dict(sorted(runtime_counts.items())),
        "synthetic_dispatch_surfaces": synthetic,
    }


def _synthetic_resource_runtime_probes(*, run_dir: Path) -> dict[str, Any]:
    """Exercise all declared runtime kinds through the canonical ResourceRuntime."""

    # ``run_dir`` is already the conformance root.  Repeating the component and
    # retaining a full UUID pushed atomic temp files over the traditional
    # Windows path limit in otherwise valid long workspaces.
    probe_root = run_dir / "runtime_probes" / uuid.uuid4().hex[:12]
    probe_root.mkdir(parents=True, exist_ok=False)
    ledger = RunExecutionLedger(
        output_dir=probe_root,
        run_id="conformance-runtime-v2",
    )
    records: list[dict[str, Any]] = []
    provider_calls: dict[str, int] = {runtime: 0 for runtime in FORMAL_RUNTIME_KINDS}

    def provider(request: ResourceCallRequest) -> ResourceCallResult:
        runtime = request.execution_world.runtime_kind
        provider_calls[runtime] += 1
        bindings = request.resolved_bindings
        if bindings.get("zero") != 0 or bindings.get("disabled") is not False:
            raise ProductionConformanceError("synthetic_typed_binding_mismatch")
        if bindings.get("items") != [] or bindings.get("nested") != {"text": '\u503c'}:
            raise ProductionConformanceError("synthetic_structured_binding_mismatch")

        if runtime == "python_script":
            value = {"runtime": runtime, "dispatch": "direct_argv"}
        elif runtime == "python_library":
            value = {"runtime": runtime, "typed_argument_count": len(bindings)}
        elif runtime == "rest_api":
            fake_transport = lambda payload: {"transport": "in_memory", "payload": payload}
            value = {"runtime": runtime, **fake_transport("ok")}
        elif runtime == "mcp_server":
            child = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-c",
                    (
                        "import json,sys; request=json.loads(sys.stdin.read()); "
                        "print(json.dumps({'transport':'stdio','id':request['id']}))"
                    ),
                ],
                input=json.dumps({"id": "probe"}),
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            if child.returncode != 0:
                raise ProductionConformanceError("synthetic_mcp_stdio_failed")
            value = {"runtime": runtime, **json.loads(child.stdout)}
        else:
            raise ProductionConformanceError("synthetic_runtime_unknown")
        return ResourceCallResult(
            call_id=request.call_id,
            resource_id=request.resource_definition.resource_id,
            entrypoint_id=request.entrypoint_id,
            status=ResourceCallStatus.SUCCESS,
            canonical_value=value,
            presentation=json.dumps(value, ensure_ascii=False, sort_keys=True),
            execution_audit={
                "runtime_kind": runtime,
                "direct_argv": request.execution_world.direct_argv,
                "network_requests_made": 0,
            },
            provenance={"source_ids": list(request.provenance_source_ids)},
            output_contract_status="checked",
        )

    runtime = ResourceRuntime(ledger=ledger, provider=provider)
    try:
        for runtime_kind in FORMAL_RUNTIME_KINDS:
            resource_id = f"synthetic.{runtime_kind}.v1"
            definition = ResourceDefinition.from_manifest(
                {
                    "resource_id": resource_id,
                    "resource_type": "Tool",
                    "status": "active",
                    "capability": {
                        "summary": "Exercise one declared synthetic runtime adapter.",
                        "operation_kinds": ["run_tool"],
                    },
                    "constraint": {"artifact_output": ["json"]},
                    "execution": {
                        "runtime": runtime_kind,
                        "uri": f"memory://{runtime_kind}/invoke",
                    },
                    "input_contract": [
                        {"name": "zero", "kind": "integer", "required": True},
                        {"name": "disabled", "kind": "boolean", "required": True},
                        {"name": "items", "kind": "array", "required": True},
                        {"name": "nested", "kind": "object", "required": True},
                    ],
                    "output_contract": {
                        "artifact_type": "json",
                        "schema_hint": {
                            "type": "object",
                            "properties": {
                                "runtime": {"type": "string"},
                                "dispatch": {"type": "string"},
                                "typed_argument_count": {"type": "integer"},
                                "transport": {"type": "string"},
                                "payload": {"type": "string"},
                                "id": {"type": "string"},
                            },
                            "required": ["runtime"],
                            "additionalProperties": False,
                        },
                    },
                    "runtime_requirements": {"network_required": False},
                }
            )
            plan_sha256 = canonical_sha256(
                {"runtime": runtime_kind, "resource_id": resource_id}
            )
            scope_sha256 = canonical_sha256(
                {"runtime": runtime_kind, "scope": "synthetic"}
            )
            context = ResourceExecutionContext(
                run_id=ledger.run_id,
                graph_revision=0,
                subtask_id=f"probe-{runtime_kind}",
                subtask_revision=0,
                candidate_pool_sha256=canonical_sha256(
                    {"candidate_resources": [resource_id]}
                ),
                candidate_resource_ids=(resource_id,),
                selected_resource_ids=(resource_id,),
                plan_sha256=plan_sha256,
                step_id=f"step-{runtime_kind}",
                attempt=1,
                sandbox_scope_sha256=scope_sha256,
            )
            world = ExecutionWorldDescriptor(
                runtime_kind=runtime_kind,
                writable_root_runtime_path="/app/work",
                working_directory="/app/work",
                environment_sha256=canonical_sha256({"env": "synthetic"}),
                dependency_lock_sha256=canonical_sha256({"lock": runtime_kind}),
                runtime_request_sha256=canonical_sha256({"request": runtime_kind}),
                sandbox_scope_sha256=scope_sha256,
                network_required=False,
                direct_argv=True,
            )
            request = ResourceCallRequest(
                call_id=f"call-{runtime_kind}",
                resource_definition=definition,
                entrypoint_id="invoke",
                execution_context=context,
                resolved_bindings={
                    "zero": 0,
                    "disabled": False,
                    "items": [],
                    "nested": {"text": '\u503c'},
                },
                capability_operation_id=next(
                    item.capability_operation_id
                    for item in definition.capability_card.capability_operations
                    if item.entrypoint_id in {None, "invoke"}
                ),
                semantic_task_contract={"intent": f"probe {runtime_kind}"},
                acceptance_requirements=("Return the declared synthetic result.",),
                execution_world=world,
                output_contract=dict(definition.base_output_contract),
                provenance_source_ids=("source:synthetic-public",),
            )
            result = asyncio.run(runtime.execute(request))
            records.append(
                {
                    "runtime": runtime_kind,
                    "status": result.status.value,
                    "request_sha256": request.request_sha256,
                    "result_sha256": result.result_sha256,
                    "started_terminal_paired": bool(
                        result.started_event_id and result.terminal_event_id
                    ),
                    "plan_sha256": context.plan_sha256,
                    "direct_argv": world.direct_argv,
                }
            )
        summary = ledger.close()
    except Exception:
        ledger.close()
        raise
    return {
        "valid": bool(
            len(records) == len(FORMAL_RUNTIME_KINDS)
            and all(item["status"] == "success" for item in records)
            and all(item["started_terminal_paired"] for item in records)
            and all(provider_calls[item] == 1 for item in FORMAL_RUNTIME_KINDS)
            and not summary.get("unmatched_call_ids")
            and not summary.get("orphan_terminal_call_ids")
        ),
        "runtime_records": records,
        "provider_call_counts": provider_calls,
        "unmatched_call_count": len(summary.get("unmatched_call_ids") or ()),
        "network_requests_made": 0,
    }


def _synthetic_frozen_candidate_publication_probe(
    *,
    run_dir: Path,
    identity: RetrievalRuntimeIdentity,
) -> dict[str, Any]:
    """Exercise the default HyDE adapter and Stage 2 publication without a provider."""

    probe_parent = run_dir / "cp"
    probe_parent.mkdir(parents=True, exist_ok=True)
    root = probe_parent / str(len(tuple(probe_parent.iterdir())))
    root.mkdir(parents=True, exist_ok=False)
    library, _fallback_ids, resource_index = load_real_pool_with_index()
    eligible_ids = set(identity.eligible_resource_ids)
    library = [item for item in library if item.id in eligible_ids]
    resource_index = {
        resource_id: raw
        for resource_id, raw in resource_index.items()
        if resource_id in eligible_ids
    }
    if not library or set(resource_index) != {item.id for item in library}:
        raise ProductionConformanceError("candidate_probe_pool_identity_mismatch")
    dimension = library[0].v_cap.dim
    vector = [1.0] + [0.0] * (dimension - 1)
    profile = QueryRetrievalProfile(
        capability=Vector(embedding=vector, dim=dimension),
        constraint=Vector(embedding=vector, dim=dimension),
        raw_query=Vector(embedding=vector, dim=dimension),
    )

    requests: list[dict[str, Any]] = []
    prompt_registry = build_prompt_surface_registry()
    profiler_prompt_record = next(
        item for item in prompt_registry.records if item.role == "profiler"
    )
    profiler_prompt_text = prompt_file_text("profiler_system.txt")

    def sender(*, ledger: Any = None, context: Any = None, **api_kwargs: Any) -> Any:
        del ledger, context
        role = "hyde"
        messages = api_kwargs.get("messages") or ()
        if messages:
            content = str(messages[-1].get("content") or "")
            if content == "Reply with OK. This is a synthetic liveness check.":
                requests.append(
                    {
                        "role": "model_liveness",
                        "request_sha256": model_request_sha256(api_kwargs),
                        "response_format_type": "",
                    }
                )
                return SimpleNamespace(accounting_reference=None)
            exact_probe_prefix = (
                "Return the following public synthetic JSON value exactly. "
                "Do not use external or user data:\n"
            )
            if content.startswith(exact_probe_prefix):
                response_content = content.removeprefix(exact_probe_prefix)
                json.loads(response_content)
                requests.append(
                    {
                        "role": "retrieval_format_probe",
                        "request_sha256": model_request_sha256(api_kwargs),
                        "response_format_type": str(
                            (api_kwargs.get("response_format") or {}).get("type") or ""
                        ),
                    }
                )
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(content=response_content)
                        )
                    ],
                    usage=SimpleNamespace(
                        prompt_tokens=1,
                        completion_tokens=1,
                        total_tokens=2,
                    ),
                    accounting_reference=None,
                )
            try:
                descriptor = json.loads(content)
            except json.JSONDecodeError:
                descriptor = None
            if isinstance(descriptor, Mapping) and descriptor.get("role"):
                role = str(descriptor["role"])
        requirement = system_role_requirement(role)
        response_instance = minimal_json_schema_instance(requirement.json_schema or {})
        if role == "hyde":
            response_instance = {
                "capability_text": (
                    "Transforms a declared typed input into a schema-valid JSON "
                    "artifact and verifies the serialized result."
                ),
                "constraint_text": (
                    "Consumes only the declared complete input and emits exactly "
                    "one JSON artifact matching the supplied output contract."
                ),
                "think": (
                    "The typed input, complete-material obligation, and JSON output "
                    "contract determine the capability and constraint descriptions."
                ),
            }
        response_content = json.dumps(
            response_instance,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        requests.append(
            {
                "role": role,
                "request_sha256": model_request_sha256(api_kwargs),
                "system_prompt_sha256": hashlib.sha256(
                    str(
                        next(
                            (
                                message.get("content")
                                for message in messages
                                if message.get("role") == "system"
                            ),
                            "",
                        )
                    ).encode("utf-8")
                ).hexdigest(),
                "response_format_type": str(
                    (api_kwargs.get("response_format") or {}).get("type") or ""
                ),
            }
        )
        return SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content=response_content))
            ],
            usage=SimpleNamespace(
                prompt_tokens=1,
                completion_tokens=1,
                total_tokens=2,
            ),
            accounting_reference=None,
        )

    transport = SyncModelTransportPort.from_sender_for_testing(
        sender=sender,
        endpoint_identity=ProviderEndpointIdentity.create(
            provider="conformance",
            base_url="https://structured-boundary.invalid/v1",
            credential_environment_variable="LLM_API_KEY",
            timeout_seconds=1,
        ),
    )
    boundary_probe = probe_structured_response_boundary_transport(transport)
    if not boundary_probe["valid"]:
        structured_probe = {
            "valid": False,
            "boundary_probe": boundary_probe,
            "adapter_records": [],
            "fake_transport_call_count": len(requests),
            "paid_model_calls_made": 0,
            "network_requests_made": 0,
        }
        return {
            "valid": False,
            "event_types": [],
            "paid_model_calls_made": 0,
            "network_requests_made": 0,
            "structured_response_adapter_probe": structured_probe,
        }
    revision = SubtaskRevisionRef(
        graph_revision=0,
        subtask_id="conformance_candidate_publication",
        subtask_revision=0,
    )
    subtask = Subtask(
        id=revision.subtask_id,
        role="conformance",
        description="Transform one declared public input into a JSON artifact.",
        expected_output="A valid JSON artifact.",
        artifact_type=ArtifactType.JSON,
        output_extension=".json",
        output_contract=SubtaskOutputContract(
            artifact_type=ArtifactType.JSON,
            output_extension=".json",
            json_schema={
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
                "additionalProperties": False,
            },
        ),
    )
    frozen_by_mode: dict[str, Any] = {}
    adapter_records: list[dict[str, Any]] = []
    for response_mode in (
        "native_strict_schema",
        "json_object_local_validator",
    ):
        before = len(requests)
        coordinator = RetrievalCoordinator(
            identity,
            profile_encoder=lambda _artifact: profile,
            local_text_encoder=lambda _text: vector,
            prompt_text=profiler_prompt_text,
            prompt_version=identity.hyde_prompt_version,
            sync_model_transport=transport,
            capability_probe_service=ExactCapabilityProbeService(
                transport,
                clock=lambda: 1000.0,
            ),
            model_liveness_probe_service=ModelLivenessProbeService(
                transport,
                clock=lambda: 1000.0,
            ),
            hyde_response_mode=response_mode,
        )
        frozen_by_mode[response_mode] = coordinator.prepare_candidate_pool(
            revision,
            subtask,
            identity,
            library,
            resource_index,
            None,
        )
        current_requests = requests[before:]
        adapter_requests = [item for item in current_requests if item["role"] == "hyde"]
        liveness_requests = [
            item for item in current_requests if item["role"] == "model_liveness"
        ]
        format_probe_requests = [
            item for item in current_requests if item["role"] == "retrieval_format_probe"
        ]
        requirement = system_role_requirement("hyde")
        adapter_records.append(
            {
                "mode": response_mode,
                "request_sha256": (
                    adapter_requests[0]["request_sha256"]
                    if len(adapter_requests) == 1
                    else None
                ),
                "wire_schema_sha256": requirement.wire_schema_sha256,
                "prompt_registry_sha256": prompt_registry.registry_sha256,
                "registered_system_prompt_sha256": profiler_prompt_record.template_sha256,
                "sent_system_prompt_sha256": (
                    adapter_requests[0]["system_prompt_sha256"]
                    if len(adapter_requests) == 1
                    else None
                ),
                "prompt_registry_match": bool(
                    len(adapter_requests) == 1
                    and adapter_requests[0]["system_prompt_sha256"]
                    == profiler_prompt_record.template_sha256
                    and requirement.wire_schema_sha256
                    == profiler_prompt_record.response_schema_sha256
                ),
                "response_format_type": (
                    adapter_requests[0]["response_format_type"]
                    if len(adapter_requests) == 1
                    else ""
                ),
                "call_count": len(adapter_requests),
                "model_liveness_probe_count": len(liveness_requests),
                "retrieval_format_probe_count": len(format_probe_requests),
                "live_format_evidence_count": len(
                    frozen_by_mode[response_mode].capability_probe_evidence
                ),
                "candidate_pool_sha256": frozen_by_mode[
                    response_mode
                ].candidate_pool_snapshot.candidate_pool_sha256,
            }
        )
    frozen = frozen_by_mode["native_strict_schema"]
    trace_path = root / "trace.jsonl"
    publication = persist_frozen_candidate_pool(
        frozen_result=frozen,
        run_id="conformance-candidate-publication-v1",
        run_dir=root,
        event_writer=lambda event: append_formal_jsonl(trace_path, event),
    )
    refs = typed_refs_from_frozen_pool(frozen, library)
    snapshot_ids = tuple(
        item.resource_id for item in frozen.candidate_pool_snapshot.candidates
    )
    event_types = [
        json.loads(line)["event_type"]
        for line in trace_path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    structured_probe = {
        "valid": bool(
            boundary_probe["valid"]
            and len(adapter_records) == 2
            and all(item["call_count"] == 1 for item in adapter_records)
            and all(item["prompt_registry_match"] for item in adapter_records)
            and all(
                item["model_liveness_probe_count"] >= 1
                for item in adapter_records
            )
            and all(
                item["retrieval_format_probe_count"] >= 1
                and item["live_format_evidence_count"] >= 1
                for item in adapter_records
            )
            and [item["response_format_type"] for item in adapter_records]
            == ["json_schema", "json_object"]
            and len({item["candidate_pool_sha256"] for item in adapter_records}) == 1
        ),
        "boundary_probe": boundary_probe,
        "adapter_records": adapter_records,
        "fake_transport_call_count": len(requests),
        "paid_model_calls_made": 0,
        "network_requests_made": 0,
    }
    return {
        "valid": bool(
            tuple(item.resource_id for item in refs) == snapshot_ids
            and publication.candidate_pool_sha256
            == frozen.candidate_pool_snapshot.candidate_pool_sha256
            and event_types
            == ["candidate_pool_publication_started", "candidate_pool_frozen"]
            and structured_probe["valid"]
        ),
        "candidate_count": len(snapshot_ids),
        "candidate_pool_sha256": publication.candidate_pool_sha256,
        "retrieval_evidence_sha256": publication.retrieval_evidence_sha256,
        "publication_sha256": publication.publication_sha256,
        "event_types": event_types,
        "paid_model_calls_made": 0,
        "network_requests_made": 0,
        "structured_response_adapter_probe": structured_probe,
    }


def _model_transport_v2_probe() -> dict[str, Any]:
    """Exercise real sync/async OpenAI SDK shapes without opening a socket."""

    provider_requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal provider_requests
        provider_requests += 1
        return httpx.Response(
            200,
            request=request,
            json={
                "id": f"mock-{provider_requests}",
                "object": "chat.completion",
                "created": 0,
                "model": "conformance-model",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "{}"},
                    }
                ],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            },
        )

    sync_http = httpx.Client(transport=httpx.MockTransport(handler))
    async_http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        bundle = create_model_transport_bundle(
            api_key="conformance-sentinel-not-a-real-key",
            base_url="https://mock.invalid/v1",
            credential_environment_variable="LLM_API_KEY",
            timeout_seconds=1,
            sync_http_client=sync_http,
            async_http_client=async_http,
        )
        sync_response = bundle.sync.send(
            model="conformance-model",
            messages=[{"role": "user", "content": "sync compiler/full generation"}],
            stream=False,
        )

        async def call_async() -> str:
            response = await bundle.async_port.send(
                model="conformance-model",
                messages=[{"role": "user", "content": "async evaluator"}],
                stream=False,
            )
            return str(response.choices[0].message.content)

        async_content = asyncio.run(call_async())
        before_mismatch = provider_requests
        mismatches: list[str] = []
        for value, requirement in (
            (bundle.sync, require_async_model_transport),
            (bundle.async_port, require_sync_model_transport),
        ):
            try:
                requirement(value)
            except ModelTransportCapabilityError as exc:
                mismatches.append(str(exc))
        return {
            "valid": bool(
                str(sync_response.choices[0].message.content) == "{}"
                and async_content == "{}"
                and provider_requests == 2
                and before_mismatch == provider_requests
                and len(mismatches) == 2
                and bundle.sync.endpoint_identity.identity_sha256
                == bundle.async_port.endpoint_identity.identity_sha256
            ),
            "protocol": bundle.protocol,
            "endpoint_identity_sha256": bundle.endpoint_identity.identity_sha256,
            "capability_sha256": bundle.capability_sha256,
            "mock_provider_request_count": provider_requests,
            "mismatch_request_count": provider_requests - before_mismatch,
            "mismatch_codes": mismatches,
        }
    finally:
        sync_http.close()
        asyncio.run(async_http.aclose())


def _authorized_material_view_probe(*, run_dir: Path) -> dict[str, Any]:
    root = run_dir / "authorized_material_probe" / uuid.uuid4().hex[:12]
    root.mkdir(parents=True, exist_ok=False)
    marker = "synthetic-public-material-5f2c79d1"
    text_path = root / "7b0f8f23a1.txt"
    binary_path = root / "2d19c640be.bin"
    text_path.write_text(marker * 5000, encoding="utf-8", newline="")
    binary_path.write_bytes(b"\x00\xff\x10\x80")
    sources: list[AuthorizedMaterialSource] = []
    for index, path in enumerate((text_path, binary_path)):
        digest, size, kind = public_snapshot_identity(path)
        sources.append(
            AuthorizedMaterialSource(
                source_id=(
                    f"conformance-material:{index}:"
                    + canonical_sha256({"source": index})[:20]
                ),
                origin="public_input",
                logical_name=canonical_sha256({"logical": index})[:20],
                logical_locator=f"/app/inputs/{canonical_sha256({'locator': index})[:20]}",
                source_path=path,
                expected_sha256=digest,
                expected_byte_size=size,
                expected_kind=kind,
                extension=path.suffix,
            )
        )
    revision = SubtaskRevisionRef(
        graph_revision=0,
        subtask_id="conformance-authorized-material",
        subtask_revision=0,
    )
    view = build_authorized_model_material_view(
        run_id="conformance-authorized-material-v1",
        revision=revision,
        sources=tuple(sources),
    )
    audit = view.audit_projection()
    serialized_audit = canonical_json_bytes(audit).decode("utf-8")
    return {
        "valid": bool(
            len(view.materials) == 2
            and view.materials[0].evidence_kind in {"full", "bounded"}
            and marker in view.materials[0].authorized_content
            and view.materials[1].evidence_kind == "descriptor_only"
            and marker not in serialized_audit
            and str(root) not in serialized_audit
            and view.total_material_bytes <= 256 * 1024
        ),
        "source_count": len(view.materials),
        "evidence_kinds": [item.evidence_kind for item in view.materials],
        "total_material_bytes": view.total_material_bytes,
        "audit_content_free": marker not in serialized_audit,
    }


def _terminal_failure_matrix_probe() -> dict[str, Any]:
    expected = {
        "framework": "framework_failure",
        "infrastructure": "infrastructure_failure",
        "research": "research_failure",
        "budget": "budget_failure",
        "interrupted": "interrupted",
    }
    facts = [
        TerminalFailureEnvelope.create(
            responsibility=responsibility,
            failure_stage="conformance_injected_stage",
            failure_code="same-visible-text",
            run_id="conformance-failure-v1",
            subtask_id="conformance-node",
            source_event_ids=(f"event-{responsibility}",),
        )
        for responsibility in expected
    ]
    selected = highest_severity_terminal_failure(facts)
    return {
        "valid": bool(
            all(item.run_status == expected[item.responsibility] for item in facts)
            and len({item.failure_sha256 for item in facts}) == len(facts)
            and all(item.source_event_ids for item in facts)
            and selected.responsibility == "framework"
        ),
        "status_by_responsibility": {
            item.responsibility: item.run_status for item in facts
        },
        "failure_sha256s": [item.failure_sha256 for item in facts],
        "primary_failure_preserved": True,
        "highest_severity_responsibility": selected.responsibility,
    }


def _payload_provenance_closure_probe() -> dict[str, Any]:
    registry = PayloadSourceRegistry(
        subtask_id="conformance-provenance",
        mode="production",
        attempt_id="conformance-attempt",
    )
    registry.register(
        "conformance:public",
        origin="public_case",
        material={"objective": "public"},
        default=True,
    )
    registry.register(
        "conformance:pool",
        origin="candidate_bundle",
        material={"candidate_ids": ["model.synthetic.v1"]},
        default=True,
    )
    registry.register(
        "conformance:plan",
        origin="validated_plan",
        material={"steps": ["step-one"]},
        parent_source_ids=registry.default_source_ids,
        default=True,
    )
    registry.register(
        "conformance:checkpoint",
        origin="current_run_checkpoint_output",
        material={"output": "reused"},
        parent_source_ids=registry.default_source_ids,
    )
    guard = ProductionModelPayloadGuard(registry)
    parents = guard.derive_parent_source_ids(
        upstream_source_ids=("conformance:checkpoint",)
    )
    request = guard.register_source(
        "conformance:request-resource",
        origin="candidate_bundle",
        material={"resource_id": "model.synthetic.v1"},
        parent_source_ids=parents,
    )
    source_ids = (*parents, str(request["source_id"]))
    bound = guard.for_request(
        "downstream_model",
        source_ids=source_ids,
        request_identity={"step_id": "step-one"},
    )
    bound({"messages": [{"role": "user", "content": "public reused"}]})
    strict_unknown_rejected = False
    try:
        guard.derive_parent_source_ids(
            upstream_source_ids=("conformance:unregistered",)
        )
    except PayloadProvenanceError as exc:
        strict_unknown_rejected = exc.code == "provenance_source_missing"
    attested_ids = tuple(
        str(item.get("source_id") or "") for item in bound.attestation["sources"]
    )
    return {
        "valid": bool(
            parents
            == (
                "conformance:public",
                "conformance:pool",
                "conformance:plan",
                "conformance:checkpoint",
            )
            and attested_ids == source_ids
            and strict_unknown_rejected
            and guard.checks[-1]["passed"] is True
        ),
        "derived_parent_source_ids": list(parents),
        "attested_source_ids": list(attested_ids),
        "strict_unknown_parent_rejected": strict_unknown_rejected,
        "checkpoint_origin_accepted": True,
        "payload_guard_passed": bool(guard.checks[-1]["passed"]),
    }


def _compiler_schema_observability_probe() -> dict[str, Any]:
    from pydantic import ValidationError

    from .executable_plan import CompilerPlanDraft
    from .plan_compiler import plan_compiler_schema_failure_audit

    response_sha256 = canonical_sha256("synthetic-schema-invalid-response")
    try:
        CompilerPlanDraft.model_validate(
            {
                "is_sufficient": True,
                "steps": "not-a-step-sequence",
                "final_output": None,
            },
            strict=True,
        )
    except ValidationError as exc:
        audit = plan_compiler_schema_failure_audit(
            exc,
            response_sha256=response_sha256,
            adaptation=False,
        )
    else:
        raise ProductionConformanceError("schema_invalid_probe_unexpectedly_valid")
    serialized = canonical_json_bytes(audit).decode("utf-8")
    return {
        "valid": bool(
            audit["validation_error_count"] >= 1
            and audit["validation_error_path_hashes"]
            and audit["expected_schema_sha256"]
            and audit["response_sha256"] == response_sha256
            and "not-a-step-sequence" not in serialized
        ),
        **audit,
        "responsibility": "research",
        "failure_layer": "protocol",
        "next_recovery_action": "full_generation",
        "raw_response_persisted": False,
    }


def _schema_invalid_recovery_transition_probe(
    *, run_dir: Path, project_root: Path = PROJECT_ROOT
) -> dict[str, Any]:
    """Prove Compiler failure recovery stays diagnostic and cannot be evaluated."""

    from types import SimpleNamespace

    from .executable_plan import (
        CompilePurpose,
        PlanCompilationFailure,
        PlanRevisionRef,
        SealedPlanCompilationArtifact,
    )
    from .recovery_controller import RecoveryController

    probe_parent = run_dir / "rc"
    probe_parent.mkdir(parents=True, exist_ok=True)
    root = probe_parent / str(len(tuple(probe_parent.iterdir())))
    root.mkdir(parents=True, exist_ok=False)
    revision = SubtaskRevisionRef(
        graph_revision=0,
        subtask_id="conformance-schema-invalid",
        subtask_revision=0,
    )
    candidate_hash = canonical_sha256("conformance-frozen-candidate-pool")
    plan_revision = PlanRevisionRef(
        subtask_revision=revision,
        plan_revision=0,
        compile_purpose=CompilePurpose.INITIAL,
    )
    failure = PlanCompilationFailure(
        responsibility="research",
        failure_stage="plan_compiler_protocol",
        failure_code="plan_compiler_response_schema_invalid",
        failure_layer="protocol",
        response_received=True,
        message_sha256=canonical_sha256("strict-schema-invalid"),
    )
    failed_artifact = SealedPlanCompilationArtifact.model_construct(
        run_id="conformance-recovery-v1",
        plan_revision=plan_revision,
        status="failed",
        contract_sha256=canonical_sha256("contract"),
        candidate_pool_sha256=candidate_hash,
        retrieval_evidence_sha256=canonical_sha256("retrieval"),
        pricing_catalog_sha256=canonical_sha256("pricing"),
        prompt_sha256=canonical_sha256("prompt"),
        compiler_input_sha256=canonical_sha256("compiler-input"),
        compiler_model_resource_id="model.conformance.compiler",
        compiler_model_api_id="conformance-compiler",
        failure=failure,
        artifact_sha256=canonical_sha256("failed-compiler-artifact"),
    )

    class CompilationPort:
        calls = 0

        async def compile_initial(self) -> Any:
            self.calls += 1
            return failed_artifact

        async def adapt(self, **_kwargs: Any) -> Any:
            raise AssertionError("schema-invalid initial compile must not adapt")

    class ExecutionPort:
        calls = 0

        async def execute(self, **_kwargs: Any) -> Any:
            self.calls += 1
            raise AssertionError("failed initial compile must not execute")

    class FullGenerationPort:
        calls = 0

        async def generate(self, **_kwargs: Any) -> ResourceCallResult:
            self.calls += 1
            return ResourceCallResult(
                call_id="conformance-full-generation-call",
                resource_id="model.gpt_5_6_sol.v1",
                entrypoint_id="invoke",
                status=ResourceCallStatus.SUCCESS,
                canonical_value={"ok": True},
                presentation='{"ok":true}',
                usage_reference="conformance-full-generation-operation",
                output_contract_status="checked",
            )

    compilation = CompilationPort()
    execution = ExecutionPort()
    full_generation = FullGenerationPort()
    ledger = RecoveryEventLedger(
        output_dir=root,
        run_id="conformance-recovery-v1",
    )
    controller = RecoveryController(
        run_id="conformance-recovery-v1",
        policy=load_recovery_policy(
            project_root / "sgar_mvp" / "config" / "recovery_policy.json"
        ),
        ledger=ledger,
        compilation_port=compilation,
        execution_port=execution,
        full_generation_port=full_generation,
    )
    snapshot = SimpleNamespace(
        revision=revision,
        candidate_pool_sha256=candidate_hash,
    )
    result = asyncio.run(
        controller.execute_subtask(
            subtask=SimpleNamespace(id=revision.subtask_id),
            routing_session=SimpleNamespace(candidate_pool_snapshot=snapshot),
            frozen_candidate_pool=SimpleNamespace(candidate_pool_snapshot=snapshot),
            compiler_context=SimpleNamespace(),
            resource_definitions={},
            runtime_capabilities=SimpleNamespace(),
            pricing_catalog=SimpleNamespace(),
        )
    )
    summary = ledger.close()
    return {
        "valid": bool(
            result.status == "research_failure"
            and result.adaptation_attempts == 0
            and result.full_generation_attempts == 0
            and not result.model_response_success
            and not result.artifact_ready_for_evaluation
            and not result.evaluation_eligible
            and result.terminal_failure is not None
            and result.terminal_failure.responsibility == "research"
            and result.terminal_failure.failure_code
            == "plan_compiler_response_schema_invalid"
            and compilation.calls == 1
            and execution.calls == 0
            and full_generation.calls == 0
            and result.operation_ref is not None
            and result.operation_ref.candidate_pool_sha256 == candidate_hash
            and int(summary.get("incomplete_calls") or 0) == 0
        ),
        "compiler_semantic_calls": compilation.calls,
        "adaptation_calls": 0,
        "full_generation_calls": full_generation.calls,
        "execution_calls_before_fallback": execution.calls,
        "candidate_pool_sha256_preserved": bool(
            result.operation_ref is not None
            and result.operation_ref.candidate_pool_sha256 == candidate_hash
        ),
        "terminal_status": result.status,
        "model_response_success": result.model_response_success,
        "artifact_ready_for_evaluation": result.artifact_ready_for_evaluation,
        "evaluation_eligible": result.evaluation_eligible,
        "terminal_failure_responsibility": (
            result.terminal_failure.responsibility
            if result.terminal_failure is not None
            else None
        ),
        "terminal_failure_code": (
            result.terminal_failure.failure_code
            if result.terminal_failure is not None
            else None
        ),
    }
def _artifact_commit_delivery_probe(*, run_dir: Path) -> dict[str, Any]:
    """Exercise staged -> verified -> committed -> host-free delivery."""

    from .artifact_lifecycle import (
        ContextCommitStore,
        build_final_artifact_candidate,
    )
    from .delivery import extract_deliverables
    from .evaluation_contracts import (
        ArtifactEvidenceBundle,
        ArtifactRevisionRef,
        CriterionResult,
        CriterionStatus,
        EvaluationDecision,
        EvaluationDimensionScores,
        EvaluationVerdict,
        EvidenceReference,
    )
    from .evaluation_reference import build_evaluation_reference_standard
    from .orchestrator import GlobalContext
    from .schema import ArtifactType, SubtaskOutputContract

    probe_parent = run_dir / "ap"
    probe_parent.mkdir(parents=True, exist_ok=True)
    root = probe_parent / str(len(tuple(probe_parent.iterdir())))
    root.mkdir(parents=True, exist_ok=False)
    run_id = "conformance-artifact-publication-v1"
    revision = SubtaskRevisionRef(
        graph_revision=0,
        subtask_id="conformance-final-node",
        subtask_revision=0,
    )
    artifact_revision = ArtifactRevisionRef(
        run_id=run_id,
        subtask_revision=revision,
    )
    output_contract = SubtaskOutputContract(
        artifact_type=ArtifactType.JSON,
        output_extension=".json",
        required_content=("Return the declared JSON value.",),
        json_schema={
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
            "additionalProperties": False,
        },
    )
    subtask = Subtask(
        id=revision.subtask_id,
        role="conformance",
        description="Produce the declared synthetic JSON value.",
        expected_output="A valid JSON artifact.",
        artifact_type=ArtifactType.JSON,
        output_extension=".json",
        output_contract=output_contract,
    )
    content = b'{"ok":true}'
    identity = canonical_sha256("conformance-artifact-publication")
    candidate = build_final_artifact_candidate(
        artifact_revision=artifact_revision,
        content=content,
        artifact_type="json",
        extension=".json",
        logical_locator="artifact://conformance-final-node/result.json",
        output_contract_sha256=canonical_sha256(
            output_contract.model_dump(mode="json")
        ),
        candidate_pool_sha256=identity,
        execution_result_sha256=identity,
        plan_sha256=identity,
        recovery_operation_sha256=identity,
        provenance_source_ids=("conformance:sealed-plan-output",),
    )
    store = ArtifactLifecycleStore(output_dir=root, run_id=run_id)
    context_store = ContextCommitStore(artifact_store=store)
    staged = store.stage_bytes(candidate=candidate, content=content)
    standard = build_evaluation_reference_standard(
        artifact_revision=artifact_revision,
        subtask=subtask,
    )
    evidence = EvidenceReference(
        evidence_id="artifact:full",
        kind="full",
        content_sha256=staged.content_sha256,
        start_offset=0,
        end_offset=staged.byte_size,
        locator="artifact://full",
    )
    bundle = ArtifactEvidenceBundle(
        artifact_manifest_sha256=staged.manifest_sha256,
        reference_standard_sha256=standard.reference_standard_sha256,
        review_index=0,
        coverage_status="complete",
        total_byte_size=staged.byte_size,
        included_byte_size=staged.byte_size,
        evidence=(evidence,),
        criterion_evidence={
            item.criterion_id: (evidence.evidence_id,) for item in standard.criteria
        },
        public_content=content.decode("utf-8"),
    )
    decision = EvaluationDecision(
        verdict=EvaluationVerdict.PASS,
        failure_code=None,
        confidence=1.0,
        criterion_results=tuple(
            CriterionResult(
                criterion_id=item.criterion_id,
                status=CriterionStatus.PASS,
                evidence_ids=(evidence.evidence_id,),
                concise_reason="Synthetic conformance evidence is complete.",
            )
            for item in standard.criteria
        ),
        dimension_scores=EvaluationDimensionScores(),
        critical_issues=(),
        training_label="good_case",
        reference_standard_sha256=standard.reference_standard_sha256,
        evidence_bundle_sha256=bundle.evidence_bundle_sha256,
        artifact_manifest_sha256=staged.manifest_sha256,
        context_snapshot_sha256=identity,
        evaluator_model_resource_id="model.gpt_5_6_sol.v1",
        evaluator_api_model_id="gpt-5.6-sol",
        accounting_operation_id="conformance-evaluator-operation",
        request_sha256=identity,
        response_sha256=identity,
    )
    verified = store.verify(manifest=staged, decision=decision)
    committed = context_store.commit(
        staged=staged,
        verified=verified,
        decision=decision,
    )
    global_context = GlobalContext(
        context_commit_store=context_store,
        artifact_store=store,
    )
    delivery = extract_deliverables(
        global_context,
        [
            {
                "id": revision.subtask_id,
                "artifact_type": "json",
                "output_extension": ".json",
            }
        ],
        output_dir=str(root),
        emit_log=False,
    )
    artifact_summary, context_summary = store.ledger.close()
    publication = delivery.publication if delivery is not None else None
    serialized_publication = (
        canonical_json_bytes(publication.model_dump(mode="json")).decode("utf-8")
        if publication is not None
        else ""
    )
    return {
        "valid": bool(
            publication is not None
            and publication.content_sha256 == committed.content_sha256
            and publication.logical_locator == "final_output.json"
            and str(root) not in serialized_publication
            and not artifact_summary.get("unmatched_artifact_operations")
            and not context_summary.get("unmatched_context_commits")
        ),
        "content_sha256": committed.content_sha256,
        "publication_complete": publication is not None,
        "host_free_publication": str(root) not in serialized_publication,
    }


def _persistence_probe(
    *,
    run_dir: Path,
    catalog: ModelPricingCatalog,
    cost_policy: Any,
) -> dict[str, Any]:
    # Keep the probe path bounded for Windows.  The caller already supplies a
    # dedicated conformance directory, and uniqueness within one process does
    # not require a second nested ``conformance`` component or a full UUID.
    root = run_dir / "persistence_probes" / uuid.uuid4().hex[:12]
    root.mkdir(parents=True, exist_ok=False)
    run_id = "conformance-" + uuid.uuid4().hex
    cost = RunCostLedger(catalog=catalog, policy=cost_policy, output_dir=root, run_id=run_id)
    execution = RunExecutionLedger(output_dir=root, run_id=run_id)
    recovery = RecoveryEventLedger(output_dir=root, run_id=run_id)
    evaluation = EvaluationEventLedger(output_dir=root, run_id=run_id)
    artifacts = ArtifactLifecycleStore(output_dir=root, run_id=run_id)
    try:
        cost_summary = cost.close()
        execution_summary = execution.close()
        recovery_summary = recovery.close()
        evaluation_summary = evaluation.close()
        artifact_summary, context_summary = artifacts.ledger.close()
    finally:
        pass
    evidence = collect_run_ledger_evidence(root)
    return {
        "valid": not any(int(value) for value in evidence["unmatched_calls"].values()),
        "ledger_count": len(evidence["ledger_hashes"]),
        "summaries_complete": bool(
            cost_summary.get("complete", True)
            and execution_summary.get("complete", True)
            and int(recovery_summary.get("incomplete_calls") or 0) == 0
            and evaluation_summary.get("complete", True)
            and not artifact_summary.get("unmatched_artifact_operations")
            and not context_summary.get("unmatched_context_commits")
        ),
    }


def _docker_probe(*, image: str, require_docker: bool) -> dict[str, Any]:
    profile = scan_environment(
        extra_packages=(),
        extra_commands=(),
        required_env_vars=(),
        docker_images=(image,),
        docker_check_timeout_sec=20,
        docker_check_attempts=1,
    )
    image_record = dict(profile.docker_images.get(image) or {})
    available = bool(
        profile.docker_cli_available
        and profile.docker_daemon_available
        and image_record.get("available") is True
    )
    result: dict[str, Any] = {
        "required": bool(require_docker),
        "docker_cli_available": bool(profile.docker_cli_available),
        "docker_daemon_available": bool(profile.docker_daemon_available),
        "image_available": image_record.get("available") is True,
        "runtime_image_id": str(image_record.get("id") or ""),
        "probe_executed": False,
        "probe_passed": not require_docker,
    }
    if not require_docker:
        return result
    if not available:
        result["probe_passed"] = False
        return result
    docker = shutil.which("docker") or "docker"
    try:
        proc = subprocess.run(
            [
                docker,
                "run",
                "--rm",
                "--network",
                "none",
                "--label",
                "sgar.conformance=true",
                image,
                "python",
                "-c",
                "import json; print(json.dumps({'sgar': 'ok'}))",
            ],
            capture_output=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        result["probe_executed"] = True
        result["probe_passed"] = False
        return result
    result["probe_executed"] = True
    result["probe_passed"] = proc.returncode == 0 and proc.stdout.strip() == b'{"sgar": "ok"}'
    return result


def _count_paid_model_calls(run_dir: Path) -> int:
    count = 0
    for path in run_dir.rglob("model_calls.jsonl"):
        try:
            lines = path.read_text(encoding="utf-8-sig", errors="strict").splitlines()
        except (OSError, UnicodeError):
            continue
        for line in lines:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("event_type") == "model_call_started":
                count += 1
    return count


def _build_provider_retrieval_identity(
    *,
    project_root: Path,
    base_url: str,
    provider_compatibility: Mapping[str, Any] | None,
) -> RetrievalRuntimeIdentity:
    provider_endpoint_identity = production_model_endpoint_identity(
        base_url=base_url
    )
    return build_retrieval_runtime_identity(
        project_root=project_root,
        provider_compatibility=provider_compatibility,
        provider_endpoint_identity_sha256=provider_endpoint_identity.identity_sha256,
        require_release_sealed=True,
    )


def run_production_conformance(
    *,
    prepared_invocation: PreparedTaskInvocation,
    request_source_sha256: str | None = None,
    run_dir: str | Path,
    config: Mapping[str, Any],
    network_policy_mode: str = "disabled",
    project_root: str | Path = PROJECT_ROOT,
    provider_compatibility: Mapping[str, Any] | None = None,
    require_docker: bool = True,
    require_source_clean: bool = True,
    source_seal_path: str | Path | None = None,
) -> dict[str, Any]:
    """Run the complete no-cost activation gate and persist its sealed report."""

    root = Path(project_root).resolve()
    output = Path(run_dir).resolve()
    probe_output = output
    scratch_root: Path | None = None
    if sys.platform == "win32":
        scratch_parent = root / ".sgar_cache" / "t"
        scratch_parent.mkdir(parents=True, exist_ok=True)
        scratch_root = scratch_parent / f"c-{uuid.uuid4().hex[:8]}"
        scratch_root.mkdir(parents=False, exist_ok=False)
        probe_output = scratch_root
    errors: list[str] = []
    checks: dict[str, Any] = {}
    identities: dict[str, Any] = {}
    active_stage = "initialization"
    network_audit = _NoNetworkAudit()
    network_audit.start()
    try:
        if network_policy_mode not in {"disabled", "declared"}:
            raise ProductionConformanceError("network_policy_mode_invalid")
        checks["input_snapshot"] = verify_prepared_task_invocation(prepared_invocation)
        module_identity = audit_canonical_module_identity(project_root=root)
        checks["module_identity"] = module_identity
        if not module_identity["valid"]:
            errors.append("module_namespace_duplicate")
            raise ProductionConformanceError("module_namespace_duplicate")
        active_stage = "internal_metadata_layout"
        metadata_layout = internal_metadata_layout_audit(root)
        checks["internal_metadata_layout"] = metadata_layout
        if not metadata_layout["valid"]:
            errors.append("internal_metadata_layout_invalid")
            raise ProductionConformanceError("internal_metadata_layout_invalid")
        secret_policy = validate_formal_secret_config(config, raise_on_error=False)
        checks["secret_policy"] = secret_policy.as_dict()
        if not secret_policy.valid:
            errors.append("formal_literal_credential_forbidden")
        active_stage = "case_neutrality"
        configured_case_literals = config.get("case_neutrality_forbidden_literals") or ()
        if isinstance(configured_case_literals, (str, bytes)):
            configured_case_literals = (configured_case_literals,)
        checks["case_neutrality"] = audit_production_case_neutrality(
            root,
            invocation=prepared_invocation.invocation,
            forbidden_literals=tuple(configured_case_literals),
        )
        if not checks["case_neutrality"]["valid"]:
            errors.append("case_neutrality_invalid")
        active_stage = "planner_contract_gate"
        checks["planner_contract_gate"] = audit_planner_contract_gate()
        if not checks["planner_contract_gate"]["valid"]:
            errors.append("planner_contract_gate_invalid")
        active_stage = "generic_input_compatibility"
        checks["generic_input_compatibility"] = (
            run_generic_input_compatibility_probe(probe_output)
        )
        if not checks["generic_input_compatibility"]["valid"]:
            errors.append("generic_input_compatibility_invalid")
        # The reusable retrieval conformance validates the complete effective
        # pool.  Provider filtering is a separate immutable identity because
        # its loaded in-memory view is filtered later by the production entry.
        active_stage = "retrieval"
        retrieval = run_retrieval_conformance(project_root=root)
        llm_settings = dict(config.get("llm_settings") or {})
        provider_retrieval_identity = _build_provider_retrieval_identity(
            project_root=root,
            base_url=str(
                llm_settings.get("base_url") or "https://api.openai.com/v1"
            ),
            provider_compatibility=provider_compatibility,
        )
        checks["retrieval"] = {
            "valid": retrieval.get("valid") is True,
            "errors": list(retrieval.get("errors") or []),
            "pool_check": retrieval.get("pool_check") or {},
            "formal_call_graph": retrieval.get("formal_call_graph") or {},
            "unmetered_production_model_sends": retrieval.get(
                "unmetered_production_model_sends"
            )
            or [],
            "forbidden_production_imports": retrieval.get("forbidden_production_imports")
            or [],
        }
        if not checks["retrieval"]["valid"]:
            errors.append("retrieval_conformance_invalid")

        import retrieve

        embedding_identity = retrieve.get_local_embedding_identity()
        checks["local_embedding"] = {
            "valid": bool(
                embedding_identity.offline_only
                and embedding_identity.embedding_dimension
                == embedding_identity.index_dimension
            ),
            **embedding_identity.model_dump(mode="json"),
        }
        if not checks["local_embedding"]["valid"]:
            errors.append("local_embedding_identity_invalid")

        catalog_payload, catalog_path = _load_catalog(root)
        pricing = ModelPricingCatalog.from_manifest_file(catalog_path)
        configured_refs: list[str] = []

        def add_model_ref(value: Any) -> None:
            values = value if isinstance(value, (list, tuple)) else (value,)
            for item in values:
                text = str(item or "").strip()
                if text and text not in configured_refs:
                    configured_refs.append(text)

        configured_model = llm_settings.get("model", DEFAULT_SYSTEM_MODEL_CHAIN[0])
        add_model_ref(configured_model)
        add_model_ref(llm_settings.get("system_model_chain") or ())
        add_model_ref(llm_settings.get("router_policy_model", configured_model))
        add_model_ref(llm_settings.get("full_generation_baseline_model", configured_model))
        add_model_ref(llm_settings.get("supplemental_model_ids") or ())
        for key in (
            "planner_model",
            "fallback_model",
            "context_compression_model",
        ):
            add_model_ref(llm_settings.get(key))
        retrieval_identity_payload = provider_retrieval_identity.model_dump(mode="json")
        add_model_ref(retrieval_identity_payload.get("hyde_api_model_id"))
        for model_ref in configured_refs:
            pricing.resolve(model_ref=model_ref)
        from .model_selection import load_model_selection, registered_models, require_registered_models
        require_registered_models(catalog_payload, root=root, complete=True)
        registered = registered_models(load_model_selection(root))
        checks["pricing"] = {
            "valid": {p.resource_id for p in pricing.prices} == set(registered),
            "model_count": pricing.model_count,
            "configured_model_ref_count": len(configured_refs),
            "pricing_catalog_sha256": pricing.pricing_catalog_sha256,
            "resource_pool_sha256": pricing.resource_pool_sha256,
        }
        if not checks["pricing"]["valid"]:
            errors.append("pricing_model_count_invalid")

        effective_index = load_resource_index_static()
        checks["resource_surfaces"] = _adapt_resource_surfaces(
            catalog_payload, effective_index
        )
        if checks["resource_surfaces"]["adaptation_failure_hashes"]:
            errors.append("resource_definition_adaptation_failed")
        if {
            item["runtime"]
            for item in checks["resource_surfaces"]["synthetic_dispatch_surfaces"]
        } != set(FORMAL_RUNTIME_KINDS):
            errors.append("synthetic_runtime_surface_incomplete")
        checks["resource_runtime_probes"] = _synthetic_resource_runtime_probes(
            run_dir=probe_output
        )
        if not checks["resource_runtime_probes"]["valid"]:
            errors.append("synthetic_resource_runtime_probe_failed")
        active_stage = "candidate_publication_probe"
        candidate_publication_probe = _synthetic_frozen_candidate_publication_probe(
            run_dir=probe_output,
            identity=provider_retrieval_identity,
        )
        checks["candidate_publication_probe"] = candidate_publication_probe
        checks["structured_response_adapter_probe"] = candidate_publication_probe.get(
            "structured_response_adapter_probe",
            {
                "valid": False,
                "paid_model_calls_made": 0,
                "network_requests_made": 0,
            },
        )
        if not checks["candidate_publication_probe"]["valid"]:
            errors.append("synthetic_candidate_publication_probe_failed")
        if not checks["structured_response_adapter_probe"]["valid"]:
            errors.append("structured_response_adapter_probe_failed")

        active_stage = "model_transport_v2"
        checks["model_transport_v2"] = _model_transport_v2_probe()
        if not checks["model_transport_v2"]["valid"]:
            errors.append("model_transport_v2_probe_failed")
        active_stage = "authorized_material_view"
        checks["authorized_material_view"] = _authorized_material_view_probe(
            run_dir=probe_output
        )
        if not checks["authorized_material_view"]["valid"]:
            errors.append("authorized_material_view_probe_failed")
        active_stage = "compiler_schema_observability"
        checks["compiler_schema_observability"] = (
            _compiler_schema_observability_probe()
        )
        if not checks["compiler_schema_observability"]["valid"]:
            errors.append("compiler_schema_observability_probe_failed")
        active_stage = "schema_invalid_recovery_transition"
        checks["schema_invalid_recovery_transition"] = (
            _schema_invalid_recovery_transition_probe(
                run_dir=probe_output,
                project_root=root,
            )
        )
        if not checks["schema_invalid_recovery_transition"]["valid"]:
            errors.append("schema_invalid_recovery_transition_probe_failed")
        active_stage = "terminal_failure_matrix"
        checks["terminal_failure_matrix"] = _terminal_failure_matrix_probe()
        if not checks["terminal_failure_matrix"]["valid"]:
            errors.append("terminal_failure_matrix_probe_failed")
        active_stage = "payload_provenance_closure"
        checks["payload_provenance_closure"] = _payload_provenance_closure_probe()
        if not checks["payload_provenance_closure"]["valid"]:
            errors.append("payload_provenance_closure_probe_failed")
        active_stage = "artifact_commit_delivery"
        checks["artifact_commit_delivery"] = _artifact_commit_delivery_probe(
            run_dir=probe_output
        )
        if not checks["artifact_commit_delivery"]["valid"]:
            errors.append("artifact_commit_delivery_probe_failed")

        active_stage = "control_policy_identity"
        recovery_policy = load_recovery_policy(
            root / "sgar_mvp" / "config" / "recovery_policy.json"
        )
        evaluator_policy = load_evaluator_policy(
            root / "sgar_mvp" / "config" / "evaluator_policy.json"
        )
        cost_policy = load_model_cost_policy(
            root / "sgar_mvp" / "config" / "model_cost_policy.json",
            local_cost_control=llm_settings.get("cost_control"),
        )
        # Internal role identity is independent of candidate eligibility.
        # Actual control requests remain gated by the sealed role probe receipt.
        from .model_selection import control_model_index
        control_index = control_model_index(catalog_payload, root=root)
        evaluator_manifest = control_index.get(evaluator_policy.model_resource_id)
        recovery_manifest = control_index.get(
            recovery_policy.full_generation_model_resource_id
        )
        if not isinstance(evaluator_manifest, Mapping) or not isinstance(
            recovery_manifest, Mapping
        ):
            raise ProductionConformanceError("fixed_control_model_missing")
        evaluator = resolve_evaluator_model(
            policy=evaluator_policy,
            pricing_catalog=pricing,
            manifest=evaluator_manifest,
            availability_status=ResourceDefinition.from_manifest(evaluator_manifest).status,
            response_mode=_response_mode(
                evaluator_manifest, llm_settings.get("evaluator_response_mode")
            ),
        )
        full_generation = resolve_system_full_generation_policy(
            recovery_policy=recovery_policy,
            pricing_catalog=pricing,
            manifest=recovery_manifest,
            availability_status=ResourceDefinition.from_manifest(recovery_manifest).status,
            response_mode=_response_mode(
                recovery_manifest, llm_settings.get("full_generation_response_mode")
            ),
            temperature=float(llm_settings.get("execution_temperature", 0.5)),
            max_tokens=int(llm_settings.get("execution_max_tokens", 8192)),
            allow_streaming=bool(llm_settings.get("execution_stream", True)),
            prompt_version=FULL_GENERATION_PROMPT_VERSION,
            prompt_sha256=FULL_GENERATION_PROMPT_SHA256,
        )
        checks["control_policies"] = {
            "valid": True,
            "cost_policy_sha256": cost_policy.policy_sha256,
            "recovery_policy_sha256": recovery_policy.policy_sha256,
            "evaluator_policy_sha256": evaluator_policy.policy_sha256,
            "evaluator_model_identity_sha256": evaluator.identity_sha256,
            "full_generation_policy_sha256": full_generation.policy_sha256,
        }

        active_stage = "formal_execution_call_graph"
        checks["formal_execution"] = _formal_execution_call_graph(root)
        if (
            checks["formal_execution"]["legacy_calls_from_sealed_engine"]
            or checks["formal_execution"]["forbidden_imports"]
            or not checks["formal_execution"]["orchestrator_sealed_entry_present"]
        ):
            errors.append("formal_execution_call_graph_invalid")

        active_stage = "framework_source_identity"
        source = _source_identity(root)
        checks["framework_source"] = source
        sealed_working_tree = None
        if source_seal_path is not None:
            sealed_working_tree = load_and_verify_source_seal(
                Path(source_seal_path),
                project_root=root,
                allowed_stages=("release", "activated"),
            )
            checks["sealed_working_tree"] = {
                "valid": True,
                **source_seal_reference(sealed_working_tree),
            }
            identities["source_seal_sha256"] = sealed_working_tree["seal_sha256"]
        if (
            require_source_clean
            and not source["framework_source_clean"]
            and sealed_working_tree is None
        ):
            errors.append("framework_source_dirty")

        checks["network_policy"] = {
            "valid": True,
            "mode": network_policy_mode,
            "tool_default_network_disabled": network_policy_mode == "disabled",
        }
        active_stage = "persistence"
        checks["persistence"] = _persistence_probe(
            run_dir=probe_output,
            catalog=pricing,
            cost_policy=cost_policy,
        )
        if not checks["persistence"]["valid"] or not checks["persistence"][
            "summaries_complete"
        ]:
            errors.append("conformance_persistence_invalid")

        active_stage = "docker"
        runtime_images = {
            str((item.get("runtime_requirements") or {}).get("docker_image") or "")
            for item in catalog_payload
            if str(item.get("resource_type")) == "Tool"
        }
        runtime_images.discard("")
        if len(runtime_images) != 1:
            raise ProductionConformanceError("runtime_image_identity_not_unique")
        runtime_image = next(iter(runtime_images))
        checks["docker"] = _docker_probe(image=runtime_image, require_docker=require_docker)
        if require_docker and not checks["docker"]["probe_passed"]:
            errors.append("docker_production_probe_failed")

        retrieval_identity = retrieval_identity_payload
        identities = {
            "task_invocation_sha256": prepared_invocation.invocation.invocation_sha256,
            "request_source_sha256": (
                request_source_sha256
                or canonical_sha256(
                    {
                        "task_invocation_sha256": (
                            prepared_invocation.invocation.invocation_sha256
                        )
                    }
                )
            ),
            "public_input_snapshot_sha256": prepared_invocation.invocation.input_snapshot_sha256,
            "module_identity_sha256": module_identity["audit_sha256"],
            "internal_metadata_layout_sha256": metadata_layout["layout_sha256"],
            "local_embedding_identity_sha256": embedding_identity.identity_sha256,
            "retrieval_runtime_identity_sha256": retrieval_identity.get("identity_sha256"),
            "pool_sha256": retrieval_identity.get("pool_sha256"),
            "index_sha256": retrieval_identity.get("index_sha256"),
            "policy_sha256": retrieval_identity.get("policy_sha256"),
            "availability_sha256": retrieval_identity.get("availability_sha256"),
            "pricing_catalog_sha256": pricing.pricing_catalog_sha256,
            "recovery_policy_sha256": recovery_policy.policy_sha256,
            "evaluator_policy_sha256": evaluator_policy.policy_sha256,
            "network_policy_mode": network_policy_mode,
            "runtime_image_id": checks["docker"].get("runtime_image_id"),
            "framework_source_sha256": source["framework_source_sha256"],
            "formal_secret_policy_sha256": secret_policy.policy_sha256,
            **(
                {"source_seal_sha256": sealed_working_tree["seal_sha256"]}
                if sealed_working_tree is not None
                else {}
            ),
        }
    except Exception as exc:
        if not isinstance(exc, ProductionConformanceError):
            errors.append(f"conformance_stage_{active_stage}")
        errors.append(
            str(
                getattr(
                    exc,
                    "failure_code",
                    getattr(exc, "error_code", type(exc).__name__),
                )
            )
        )
    finally:
        network_audit.stop()

    paid_model_calls = _count_paid_model_calls(output)
    if probe_output != output:
        paid_model_calls += _count_paid_model_calls(probe_output)
    if scratch_root is not None:
        target = str(scratch_root)
        if scratch_root.is_absolute() and not target.startswith("\\\\?\\"):
            target = f"\\\\?\\{target}"
        try:
            shutil.rmtree(target)
        except OSError:
            errors.append("conformance_probe_cleanup_failed")
    if network_audit.request_count:
        errors.append("conformance_network_request_detected")
    if paid_model_calls:
        errors.append("conformance_paid_model_call_detected")

    projection = {
        "protocol": PRODUCTION_CONFORMANCE_PROTOCOL,
        "valid": not errors,
        "errors": sorted(set(errors)),
        "checks": checks,
        "identities": identities,
        "network_requests_made": network_audit.request_count,
        "paid_model_calls_made": paid_model_calls,
        "held_out_test_accesses": [],
    }
    report = {**projection, "report_sha256": canonical_sha256(projection)}
    _atomic_json(output / TERMINAL_REPORT_NAME, report)
    return report


def validate_production_conformance_report(
    path: str | Path,
    *,
    expected_invocation_sha256: str | None = None,
    require_valid: bool = True,
) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8-sig", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProductionConformanceError("production_conformance_report_invalid") from exc
    if not isinstance(payload, Mapping):
        raise ProductionConformanceError("production_conformance_report_root_invalid")
    projection = dict(payload)
    supplied = str(projection.pop("report_sha256", ""))
    if canonical_sha256(projection) != supplied:
        raise ProductionConformanceError("production_conformance_report_hash_mismatch")
    if payload.get("protocol") != PRODUCTION_CONFORMANCE_PROTOCOL:
        raise ProductionConformanceError("production_conformance_report_protocol_invalid")
    if require_valid and payload.get("valid") is not True:
        raise ProductionConformanceError("production_conformance_report_not_valid")
    if expected_invocation_sha256 is not None and (
        (payload.get("identities") or {}).get("task_invocation_sha256")
        != expected_invocation_sha256
    ):
        raise ProductionConformanceError("production_conformance_invocation_mismatch")
    if payload.get("network_requests_made") != 0 or payload.get("paid_model_calls_made") != 0:
        raise ProductionConformanceError("production_conformance_not_no_cost")
    return dict(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request-manifest", required=True)
    parser.add_argument(
        "--public-input-root",
        action="append",
        required=True,
        help="Authorized read-only root for the request manifest and its inputs.",
    )
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--config", default=str(PROJECT_ROOT / "sgar_mvp" / "config.json"))
    parser.add_argument("--network-policy", choices=("disabled", "declared"), default="disabled")
    parser.add_argument("--skip-docker-probe", action="store_true")
    parser.add_argument("--source-seal", type=Path)
    args = parser.parse_args()

    from .task_invocation import prepare_task_invocation

    request_path = Path(args.request_manifest).resolve()
    request = resolve_task_request(
        request_manifest=request_path,
        query=None,
        query_file=None,
        query_file_encoding="utf-8-sig",
        named_inputs=(),
        input_manifest=None,
        allowed_public_input_roots=tuple(Path(item) for item in args.public_input_root),
        project_root=PROJECT_ROOT,
        run_dir=Path(args.run_dir),
    )
    prepared = prepare_task_invocation(
        query=request.exact_query,
        input_specs=request.input_specs,
        run_dir=Path(args.run_dir).resolve(),
        request_id=request.request_id,
        final_deliverable_contract=request.final_deliverable_contract,
        public_context_descriptors=request.public_context_descriptors,
        allowed_public_input_roots=request.allowed_public_input_roots,
        project_root=PROJECT_ROOT,
    )
    config = json.loads(Path(args.config).read_text(encoding="utf-8-sig"))
    report = run_production_conformance(
        prepared_invocation=prepared,
        request_source_sha256=request.request_source_sha256,
        run_dir=args.run_dir,
        config=config,
        network_policy_mode=args.network_policy,
        require_docker=not args.skip_docker_probe,
        source_seal_path=args.source_seal,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    raise SystemExit(0 if report["valid"] else 2)


if __name__ == "__main__":
    main()


__all__ = [
    "PRODUCTION_CONFORMANCE_PROTOCOL",
    "ProductionConformanceError",
    "framework_source_identity",
    "run_production_conformance",
    "validate_production_conformance_report",
]
