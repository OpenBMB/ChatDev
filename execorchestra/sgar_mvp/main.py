"""
S-GAR MVP — End-to-End Pipeline Entry Point
=============================================
Orchestrates the full S-GAR pipeline:

    User Query → [Routing Model] → [Execution Layer] → Final Delivery

Architecture Layers:
    ┌──────────────────────────────────────────┐
    │  Routing Model   (planner.py + router.py)│
    ├──────────────────────────────────────────┤
    │  Execution Layer (executors.py +         │
    │                   orchestrator.py)        │
    ├──────────────────────────────────────────┤
    │  Contract Layer  (schema.py)             │
    └──────────────────────────────────────────┘
"""

import os
import sys
import json
import random
import asyncio
import argparse
import hashlib
import re
import subprocess
import tempfile
import uuid
import time
from pathlib import Path
from typing import Any, Mapping

from loguru import logger

# Fix SSL cert path for Windows (httpx / openai)
import certifi
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

# Direct-script compatibility needs the repository root, never the package
# directory itself. Adding ``sgar_mvp`` to sys.path makes the same source
# importable as both ``src.*`` and ``sgar_mvp.src.*`` and splits class identity.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sgar_mvp.src import terminal_progress
from sgar_mvp.src.runtime_bootstrap import configure_runtime, prepare_retrieval_environment
from sgar_mvp.src.model_request_budget import ModelRequestBudget, model_request_budget
from sgar_mvp.src.runtime_abstraction import bound_pipeline
from sgar_mvp.src.schema import (
    Manifest, Vector, Utility, ManifestType,
    ExecutionMode, PlannerOutput, RoutingDecision, RoutingMetrics,
    Subtask, SubtaskOutputContract,
)
from sgar_mvp.src.capability_cards import (
    CapabilityCard,
    build_capability_consistency_report,
    build_capability_cards,
)
from sgar_mvp.src.pipeline_control import SubtaskRevisionRef, canonical_sha256
from sgar_mvp.src.task_invocation import (
    PreparedTaskInvocation,
    ResolvedTaskRequest,
    TaskInvocationError,
    prepare_task_invocation,
    resolve_task_request,
)
from sgar_mvp.src.run_workspace import (
    RunManifestStore,
    RunWorkspaceError,
    collect_run_ledger_evidence,
    create_run_workspace,
    sanitized_run_failure,
    structured_run_failure_from_terminal,
)
from sgar_mvp.src.terminal_failure import TerminalFailureEnvelope
from sgar_mvp.src.production_conformance import run_production_conformance
from sgar_mvp.src.secret_policy import FormalSecretPolicyError, validate_formal_secret_config
from sgar_mvp.src.executable_plan import (
    RuntimeCapabilities,
    build_runtime_material_adapter_capabilities,
)
from sgar_mvp.src.plan_compiler import (
    ExecutablePlanCompiler,
    PlanCompilationStore,
)
from sgar_mvp.src.control_role_policy import (
    CONTROL_ROLE_POLICY_PROTOCOL,
    ControlRoleInvocationPolicyV1,
    load_control_role_policy,
    load_control_model_profile,
    require_policy_matches_model_profile,
)
from sgar_mvp.src.local_control_readiness import load_git_control_probe_receipt
from sgar_mvp.src.release_provider_receipt import (
    RELEASE_PROVIDER_PROBE_ROLES,
    resolve_activated_release_provider_probe_receipt,
)
from sgar_mvp.src.resource_runtime import (
    CANONICAL_RESULT_PROTOCOL,
    EXECUTION_WORLD_PROTOCOL,
    RESOURCE_CALL_PROTOCOL,
    RESOURCE_RUNTIME_PROTOCOL,
    ResourceDefinition,
    supported_runtime_kinds,
)
from sgar_mvp.src.planner import DEFAULT_PLANNER_MAX_OUTPUT_TOKENS, SGARPlanner
from sgar_mvp.src.planner_contracts import PlannerGenerationError
from sgar_mvp.src.router import SGARRouter
from sgar_mvp.src.orchestrator import DAGOrchestrator, NodeUnrecoverableError
from sgar_mvp.src.reporter import (
    generate_report,
    upsert_execution_section,
    upsert_model_cost_section,
    upsert_recovery_section,
)
from sgar_mvp.src.delivery import extract_deliverables
from sgar_mvp.src.artifact_lifecycle import (
    ArtifactLifecycleCoordinator,
    ArtifactLifecycleError,
    ArtifactLifecycleStore,
    ContextCommitStore,
)
from sgar_mvp.src.evaluation_contracts import EvaluatorPolicy
from sgar_mvp.src.evaluation_runtime import (
    EvaluationCoordinator,
    EvaluationEventLedger,
    EvaluationRuntimeError,
    StaticEvaluationCoordinator,
    load_evaluator_policy,
    normalize_evaluation_mode,
    resolve_evaluator_model,
)
from sgar_mvp.src.resource_loader import (
    load_real_pool_with_index,
    load_resource_index_static,
)
from sgar_mvp.src.runtime_requirements import scan_environment, warmup_docker_runtime
from sgar_mvp.src.model_selection import control_model_index
from sgar_mvp.src.control_models import (
    ControlModelSelector,
    DEFAULT_SYSTEM_MODEL_CHAIN,
    classify_control_model_exception,
    is_control_model_failover_failure,
)
from sgar_mvp.src.model_accounting import (
    BudgetControlError,
    ModelAccountingError,
    ModelPricingCatalog,
    RunCostLedger,
    load_model_cost_policy,
)
from sgar_mvp.src.model_transport import (
    ModelTransportCapabilityError,
    SyncModelTransportPort,
    classify_transport_exception,
    create_production_model_transport_bundle,
    production_model_endpoint_identity,
)
from sgar_mvp.src.model_response_contracts import (
    CapabilityProbeEvidence,
    ExactCapabilityProbeService,
    ModelResponseContractError,
    normalize_capability_probe_enforcement_policy,
    normalize_structured_response_mode,
    system_role_requirement,
)
from sgar_mvp.src.system_role_probe_audit import SystemRoleProbeAuditStore
from sgar_mvp.src.execution_events import ExecutionEventError, RunExecutionLedger
from sgar_mvp.src.full_generation import (
    FULL_GENERATION_PROMPT_SHA256,
    FULL_GENERATION_PROMPT_VERSION,
    FullGenerationExecutor,
)
from sgar_mvp.src.recovery_control import (
    RecoveryControlError,
    RecoveryEventLedger,
    RecoveryPersistenceError,
    RecoveryPolicy,
    load_recovery_policy,
    resolve_system_full_generation_policy,
)
from sgar_mvp.src.retrieval_policy import load_retrieval_policy
from sgar_mvp.src.retrieval_runtime import (
    AppliedReadyStateCapabilityService,
    FrozenCandidatePoolResult,
    RetrievalCoordinator,
    RetrievalPreparationError,
    RetrievalRuntimeError,
    RetrievalRuntimeIdentity,
    build_retrieval_runtime_identity,
    load_applied_model_ready_state,
    project_retrieval_contract,
    validate_loaded_retrieval_backend,
)
from sgar_mvp.src.runtime_policy_context import bind_retrieval_policy_path
from sgar_mvp.src.embedding_runtime import embedding_request_budget
from sgar_mvp.src.frozen_candidate_publication import (
    persist_frozen_candidate_pool,
)
from sgar_mvp.src.formal_serialization import append_formal_jsonl
from sgar_mvp.src.public_inputs import InternalMetadataLayoutError


# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PIPELINE_BUDGET_USD = 10.0
DEFAULT_USER_QUERY = (
    "The SQL file Pool/resources/resources/ecommerce_schema.sql contains an e-commerce database schema. "
    "Extract its table names and column definitions, then design a RESTful API specification based on the schema. "
    "Using FastAPI, implement the tables' core CRUD operations and combine the code and API specification in a Markdown technical document."
)


def _portable_artifact_type(*, extension: str, media_type: str, path_kind: str) -> str:
    if path_kind == "directory":
        return "directory"
    normalized_extension = str(extension or "").strip().lower()
    by_extension = {
        ".csv": "csv",
        ".json": "json",
        ".md": "markdown",
        ".markdown": "markdown",
        ".txt": "plaintext",
        ".xlsx": "xlsx",
        ".xls": "xls",
        ".docx": "docx",
        ".doc": "doc",
        ".pptx": "pptx",
        ".ppt": "ppt",
        ".pdf": "pdf",
        ".mp3": "audio",
        ".wav": "audio",
        ".m4a": "audio",
        ".flac": "audio",
        ".ogg": "audio",
        ".png": "image",
        ".jpg": "image",
        ".jpeg": "image",
        ".webp": "image",
        ".v": "code",
        ".vo": "file",
        ".py": "code",
        ".js": "code",
        ".ts": "code",
    }
    if normalized_extension in by_extension:
        return by_extension[normalized_extension]
    normalized_media = str(media_type or "").strip().lower()
    if "csv" in normalized_media:
        return "csv"
    if "json" in normalized_media:
        return "json"
    if "markdown" in normalized_media:
        return "markdown"
    if normalized_media.startswith("text/"):
        return "plaintext"
    if normalized_media.startswith("audio/"):
        return "audio"
    if normalized_media.startswith("image/"):
        return "image"
    if normalized_media == "application/pdf":
        return "pdf"
    if "spreadsheet" in normalized_media or "excel" in normalized_media:
        return "xlsx"
    if "wordprocessing" in normalized_media:
        return "docx"
    if "msword" in normalized_media:
        return "doc"
    if "presentation" in normalized_media:
        return "pptx"
    if "powerpoint" in normalized_media:
        return "ppt"
    return "file"


def _portable_public_context_for_subtask(
    subtask: Subtask,
    task_invocation: PreparedTaskInvocation | None,
) -> tuple[dict[str, Any], ...]:
    """Project only root-node, evidence-cited inputs into host-free metadata.

    Downstream nodes consume immutable dependency contracts and runtime artifacts;
    they must not silently regain access to the original query or public inputs.
    """

    if task_invocation is None:
        return ()
    semantic_v2 = subtask.semantic_contract_v2
    explicit_public_refs = (
        {
            item.ref
            for item in semantic_v2.authorized_inputs
            if item.source == "public_input"
        }
        if semantic_v2 is not None
        else set()
    )
    if semantic_v2 is None and subtask.depends_on:
        return ()
    cited_ids = {
        str(source_id)
        for requirement in subtask.semantic_requirements
        for source_id in requirement.evidence_source_ids
    }
    descriptors: list[dict[str, Any]] = []
    for item in task_invocation.invocation.public_inputs:
        evidence_id = f"artifact:{item.handle_id}"
        if semantic_v2 is not None:
            if str(item.logical_name) not in explicit_public_refs:
                continue
        elif evidence_id not in cited_ids:
            continue
        descriptors.append(
            {
                "logical_name": item.logical_name,
                "source_name": item.source_name,
                "artifact_type": _portable_artifact_type(
                    extension=item.extension,
                    media_type=item.media_type,
                    path_kind=item.path_kind,
                ),
                "sha256": item.content_sha256,
                "coverage_status": "handle_only",
                "original_bytes": item.byte_size,
                "included_bytes": 0,
                "included_content_sha256": None,
                "handle_available": True,
                "content_acquisition_required": (
                    str(
                        item.execution_contract.get("inventory_artifact_role")
                        or ""
                    ).strip()
                    != "framework_metadata_only"
                ),
                **({"container_inventory": item.execution_contract["container_inventory"]}
                   if item.execution_contract.get("container_inventory") else {}),
            }
        )
    return tuple(descriptors)


def _authoritative_final_json_schema(
    task_invocation: PreparedTaskInvocation | None,
) -> dict[str, Any] | None:
    """Return the one invocation-owned authoritative JSON Schema, if present."""

    if task_invocation is None:
        return None
    descriptors = [
        item
        for item in task_invocation.invocation.public_context_descriptors
        if str(item.get("kind") or "") == "authoritative_json_schema"
    ]
    if not descriptors:
        return None
    if len(descriptors) != 1:
        raise ValueError("authoritative_final_json_schema_identity_invalid")
    raw_schema = descriptors[0].get("schema")
    if not isinstance(raw_schema, Mapping):
        raise ValueError("authoritative_final_json_schema_invalid")
    try:
        canonical = json.loads(
            json.dumps(
                dict(raw_schema),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("authoritative_final_json_schema_invalid") from exc
    if not isinstance(canonical, dict):
        raise ValueError("authoritative_final_json_schema_invalid")
    return canonical


def _bind_authoritative_final_schema(
    planner_output: PlannerOutput,
    task_invocation: PreparedTaskInvocation | None,
) -> PlannerOutput:
    """Bind the invocation-owned schema to the sole semantic final node."""

    authoritative_schema = _authoritative_final_json_schema(task_invocation)
    if authoritative_schema is None:
        return planner_output
    final_indexes = [
        index
        for index, subtask in enumerate(planner_output.subtasks)
        if subtask.semantic_contract_v2 is not None
        and subtask.semantic_contract_v2.output.contract_scope == "final_deliverable"
    ]
    if len(final_indexes) != 1:
        raise ValueError("authoritative_final_node_identity_invalid")
    final_index = final_indexes[0]
    final_subtask = planner_output.subtasks[final_index]
    if final_subtask.artifact_type.value != "json":
        raise ValueError("authoritative_final_schema_artifact_type_invalid")
    if final_subtask.output_contract is None:
        raise ValueError("authoritative_final_output_contract_missing")
    existing_schema = final_subtask.output_contract.json_schema
    if existing_schema is not None:
        if canonical_sha256(existing_schema) != canonical_sha256(authoritative_schema):
            raise ValueError("authoritative_final_json_schema_conflict")
        return planner_output

    contract_payload = final_subtask.output_contract.model_dump(mode="json")
    contract_payload["json_schema"] = authoritative_schema
    bound_contract = SubtaskOutputContract.model_validate(contract_payload)
    subtasks = list(planner_output.subtasks)
    subtasks[final_index] = final_subtask.model_copy(
        update={"output_contract": bound_contract}
    )
    return planner_output.model_copy(update={"subtasks": subtasks})


def _bind_task_text_authority(
    planner_output: PlannerOutput,
    task_invocation: PreparedTaskInvocation | None,
) -> PlannerOutput:
    """Carry the exact request into every node that declares text-only input.

    Planner semantics may summarize a request, but a task_text_only node has
    no material edge from which omitted literals can be recovered. The exact
    invocation query is therefore authoritative node input. Material-bound
    nodes retain their deliberately scoped inputs and never receive this text.
    """

    if task_invocation is None:
        return planner_output
    request_text = str(task_invocation.invocation.query)
    marker = "[SGAR_AUTHORITATIVE_REQUEST]"
    subtasks: list[Subtask] = []
    changed = False
    for subtask in planner_output.subtasks:
        semantic = subtask.semantic_contract_v2
        if semantic is None or semantic.input_requirement != "task_text_only":
            subtasks.append(subtask)
            continue
        if request_text in semantic.task:
            subtasks.append(subtask)
            continue
        authoritative_task = (
            f"{semantic.task.rstrip()}\n\n{marker}\n{request_text}"
        )
        semantic_payload = semantic.model_dump(mode="python")
        semantic_payload.update({
            "task": authoritative_task,
            "contract_sha256": "",
        })
        bound_semantic = semantic.__class__.model_validate(semantic_payload)
        description = str(subtask.description)
        if request_text not in description:
            description = f"{description.rstrip()}\n\n{marker}\n{request_text}"
        subtasks.append(
            subtask.model_copy(
                update={
                    "description": description,
                    "semantic_contract_v2": bound_semantic,
                }
            )
        )
        changed = True
    return (
        planner_output.model_copy(update={"subtasks": subtasks})
        if changed
        else planner_output
    )


def _model_api_id_from_raw(raw: dict | None) -> str:
    """Resolve the exact API model ID declared by one Model manifest."""

    raw = raw if isinstance(raw, dict) else {}
    type_specific = raw.get("type_specific")
    type_specific = type_specific if isinstance(type_specific, dict) else {}
    model_block = type_specific.get("model")
    model_block = model_block if isinstance(model_block, dict) else {}
    execution = raw.get("execution")
    execution = execution if isinstance(execution, dict) else {}
    return str(
        model_block.get("model_id")
        or execution.get("model_id")
        or execution.get("default_base_model")
        or ""
    ).strip()


def _resource_id_for_api_model(
    resource_index: dict[str, dict],
    api_model_id: str,
) -> str:
    matches = sorted(
        resource_id
        for resource_id, raw in resource_index.items()
        if _model_api_id_from_raw(raw) == str(api_model_id)
    )
    if len(matches) != 1:
        raise ModelResponseContractError("system_model_resource_identity_unresolvable")
    return matches[0]


def _probe_system_role(
    *,
    probe_service: ExactCapabilityProbeService,
    role: str,
    resource_id: str,
    api_model_id: str,
    cost_ledger: RunCostLedger,
    audit_store: SystemRoleProbeAuditStore,
    planner_require_capability_fields: bool = False,
    request_policy: ControlRoleInvocationPolicyV1 | None = None,
) -> CapabilityProbeEvidence:
    requirement = system_role_requirement(
        role,
        planner_require_capability_fields=planner_require_capability_fields,
    )

    def abort_probe(exc: BaseException) -> None:
        failure = _system_role_probe_exception_failure(
            exc,
            role=role,
            run_id=cost_ledger.run_id,
        )
        audit_store.record_aborted(
            role=role,
            resource_id=resource_id,
            model_id=api_model_id,
            requirement=requirement,
            endpoint_identity_sha256=(
                probe_service.transport.endpoint_identity.identity_sha256
                if probe_service.transport is not None
                else "0" * 64
            ),
            reason_code=failure.failure_code,
            accounting_reference=getattr(exc, "accounting_reference", None),
        )
        audit_store.terminate(failure)

    try:
        evidence = probe_service.probe(
            resource_id=resource_id,
            model_id=api_model_id,
            requirement=requirement,
            cost_ledger=cost_ledger,
            request_fields=(
                request_policy.request_fields() if request_policy is not None else None
            ),
            request_policy_sha256=(
                request_policy.role_policy_sha256
                if request_policy is not None
                else None
            ),
        )
    except (asyncio.CancelledError, KeyboardInterrupt) as exc:
        abort_probe(exc)
        raise
    except Exception as exc:
        abort_probe(exc)
        raise
    audit_store.record_evidence(
        role=role,
        resource_id=resource_id,
        model_id=api_model_id,
        requirement=requirement,
        evidence=evidence,
    )
    return evidence


def _system_role_probe_exception_failure(
    exc: BaseException,
    *,
    role: str,
    run_id: str,
) -> TerminalFailureEnvelope:
    if isinstance(exc, BudgetControlError):
        responsibility = "budget"
        failure_code = str(getattr(exc, "error_code", "model_cost_limit_reached"))
    elif isinstance(exc, ModelAccountingError):
        responsibility = "framework"
        failure_code = str(
            getattr(exc, "error_code", "model_accounting_failure")
        )
    elif isinstance(exc, (asyncio.CancelledError, KeyboardInterrupt)):
        responsibility = "interrupted"
        failure_code = "system_role_schema_probe_interrupted"
    elif isinstance(exc, (ModelTransportCapabilityError, ModelResponseContractError)):
        responsibility = "framework"
        failure_code = str(
            getattr(exc, "error_code", "system_role_schema_probe_contract_invalid")
        )
    else:
        _retryable, transport_code = classify_transport_exception(exc)
        if transport_code != "provider_non_transport_error":
            responsibility = "infrastructure"
            failure_code = transport_code
        else:
            responsibility = "framework"
            failure_code = "system_role_schema_probe_internal_error"
    return TerminalFailureEnvelope.create(
        responsibility=responsibility,
        failure_stage=f"{role}_schema_probe",
        failure_code=failure_code,
        exception=exc,
        retryable=responsibility == "infrastructure",
        response_received=bool(getattr(exc, "response_received", False)),
        run_id=run_id,
    )


def _system_role_probe_evidence_failure(
    evidence: CapabilityProbeEvidence,
    *,
    role: str,
    run_id: str,
) -> TerminalFailureEnvelope:
    framework_reason_codes = {
        "capability_probe_transport_not_configured",
        "probe_transport_capability_miswired",
    }
    research_reason_codes = {
        "capability_probe_empty_response",
        "capability_probe_invalid_json_response",
        "capability_probe_schema_invalid_response",
    }
    if evidence.reason_code in framework_reason_codes:
        responsibility = "framework"
    elif evidence.reason_code in research_reason_codes:
        responsibility = "research"
    else:
        responsibility = "infrastructure"
    return TerminalFailureEnvelope.create(
        responsibility=responsibility,
        failure_stage=f"{role}_schema_probe",
        failure_code=evidence.reason_code,
        retryable=evidence.outcome == "transient_failure",
        response_received=evidence.response_sha256 is not None,
        run_id=run_id,
        message_sha256=evidence.message_sha256,
        model_operation_id=str(
            (evidence.accounting_reference or {}).get("operation_id") or ""
        ) or None,
    )


def _provider_compatibility_projection(base_url: str) -> dict[str, str]:
    """Return no provider verdict without endpoint-bound capability evidence."""

    del base_url
    return {}


def _filter_models_for_provider(
    library: list[Manifest],
    fallback_ids: list[str],
    resource_index: dict[str, dict],
    llm_settings: dict,
    base_url: str,
) -> tuple[list[Manifest], list[str], dict[str, dict]]:
    """Preserve recall until endpoint-bound evidence proves incompatibility."""

    del llm_settings, base_url
    return list(library), list(fallback_ids), dict(resource_index)


def load_config(path: str = "config.json", *, resolve_secrets: bool = True) -> dict | None:
    """Load runtime settings, preferring environment/.env overrides."""
    full = path if os.path.isabs(path) else os.path.join(SCRIPT_DIR, path)
    if not os.path.exists(full):
        logger.warning("Config not found at configured locator.")
        return None
    with open(full, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Keep secrets out of config.json: explicit environment variables or the
    # project-root .env file always override a legacy literal llm_key.
    if resolve_secrets:
        api_key = _load_env_key()
        if api_key:
            config["llm_key"] = api_key

        base_url = _load_env_value("LLM_BASE_URL", "OPENAI_BASE_URL")
        if base_url:
            config.setdefault("llm_settings", {})["base_url"] = base_url.rstrip("/")

    return config


def _runtime_policy_path(
    config: Mapping[str, Any],
    setting_name: str,
    default_relative_path: str,
) -> Path:
    runtime_settings = config.get("runtime_settings")
    runtime_settings = runtime_settings if isinstance(runtime_settings, Mapping) else {}
    raw = runtime_settings.get(setting_name, default_relative_path)
    if not isinstance(raw, str) or not raw.strip():
        raise RuntimeError(f"runtime_{setting_name}_invalid")
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = Path(PROJECT_ROOT) / candidate
    resolved = candidate.resolve()
    project_root = Path(PROJECT_ROOT).resolve()
    if not resolved.is_relative_to(project_root) or not resolved.is_file():
        raise RuntimeError(f"runtime_{setting_name}_invalid")
    return resolved


def _load_env_value(*names: str) -> str:
    """Resolve each preferred name from process env or project-root .env."""
    dotenv_values: dict[str, str] = {}
    env_path = os.path.join(PROJECT_ROOT, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, value = line.split("=", 1)
                dotenv_values[name.strip()] = value.strip()

    # Formal production model traffic has exactly one credential authority.
    # Do not silently fall back to another provider variable: doing so makes
    # readiness depend on unrelated host state and weakens the secret audit.
    for name in names:
        value = os.environ.get(name, "").strip() or dotenv_values.get(name, "")
        if value:
            return value
    return ""


def _load_env_key() -> str:
    """Read the shared LLM credential without logging it."""
    return _load_env_value("LLM_API_KEY")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for reusable experiment runs."""
    parser = argparse.ArgumentParser(description="Run the S-GAR MVP pipeline.")
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Exact user query text. Use exactly one of --query and --query-file.",
    )
    parser.add_argument(
        "--query-file",
        type=str,
        default=None,
        help="Text file containing the exact user query.",
    )
    parser.add_argument(
        "--query-file-encoding",
        type=str,
        default="utf-8-sig",
        help="Explicit query-file encoding (default: utf-8-sig, strict).",
    )
    parser.add_argument(
        "--input",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="Explicit public file or directory input. May be repeated.",
    )
    parser.add_argument(
        "--input-manifest",
        type=str,
        default=None,
        help="JSON input manifest. Relative paths resolve from the manifest directory.",
    )
    parser.add_argument(
        "--public-input-root",
        action="append",
        default=[],
        metavar="PATH",
        help=(
            "Explicit read-only root for file-backed public input. May be repeated; "
            "every manifest, query file, and input must remain in exactly one root."
        ),
    )
    parser.add_argument(
        "--request-manifest",
        type=str,
        default=None,
        help="Complete JSON TaskInvocation request manifest.",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.json",
        help="Path to config JSON. Relative paths are resolved from sgar_mvp/.",
    )
    parser.add_argument(
        "--output-root",
        type=str,
        default=None,
        help="Run root; defaults to runtime_settings.output_root in local config.",
    )
    parser.add_argument(
        "--run-dir",
        type=str,
        default=None,
        help="Use an explicitly named new or empty run directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Deprecated alias for --run-dir.",
    )
    parser.add_argument(
        "--report-path",
        type=str,
        default=None,
        help="Path for the Markdown execution report. Defaults to <output-dir>/experiment_report.md.",
    )
    parser.add_argument(
        "--log-path",
        type=str,
        default=None,
        help="Path for pipeline log. Defaults to <output-dir>/pipeline.log.",
    )
    parser.add_argument(
        "--network-policy",
        choices=("disabled", "declared"),
        default="disabled",
        help="Tool network policy. Network is disabled unless explicitly declared.",
    )
    parser.add_argument(
        "--planner-variant",
        choices=("baseline", "resource_aware"),
        default="resource_aware",
        help=(
            "Planner mode. resource_aware supplies a bounded, frozen-pool "
            "capability view; cited evidence is revalidated before candidate freeze."
        ),
    )
    parser.add_argument('--max-generation-requests', type=int, default=None,
                        help='Optional existing pipeline generation-request limit.')
    parser.add_argument('--deadline-sec', type=int, default=None,
                        help='Optional existing pipeline deadline in seconds.')
    parser.add_argument(
        "--runtime-authority",
        choices=("git", "release"),
        default=None,
        help=(
            "Runtime authority; defaults to local runtime_settings, then git. git uses the current checkout and applied "
            "ready-state; release enables the sealed release attestation gates."
        ),
    )
    parser.add_argument(
        "--source-seal",
        type=str,
        default=None,
        help=(
            "Required hash-sealed source identity for strict dirty-working-tree "
            "evaluation or locally activated validation."
        ),
    )
    parser.add_argument(
        "--sealed-local-validation",
        action="store_true",
        help=(
            "Validate a dirty Local checkout only when --source-seal and the "
            "sealed retrieval environment are both present."
        ),
    )
    args = parser.parse_args()
    for name in ('max_generation_requests', 'deadline_sec'):
        value = getattr(args, name)
        if value is not None and value <= 0:
            parser.error('--' + name.replace('_', '-') + ' must be positive')
    return args


def resolve_user_query(args: argparse.Namespace) -> str:
    """Resolve the exact user query without stripping or encoding repair."""
    if args.query is not None:
        return args.query
    if args.query_file:
        try:
            with open(
                args.query_file,
                "r",
                encoding=args.query_file_encoding,
                errors="strict",
            ) as f:
                return f.read()
        except (OSError, UnicodeError, LookupError) as exc:
            raise TaskInvocationError("query_file_decode_failed") from exc
    return DEFAULT_USER_QUERY


def diagnose_and_repair_query_text(query: str) -> tuple[str, dict]:
    """Compatibility diagnostic that never rewrites production input."""
    text = query or ""
    diagnostics = {
        "query_encoding_warning": "\ufffd" in text,
        "repair_applied": False,
        "reason": (
            "unicode_replacement_character_present"
            if "\ufffd" in text
            else ""
        ),
    }
    return text, diagnostics


def _public_query_reference(query: str) -> str:
    """Return a content-addressed public reference without copying query text.

    The exact Unicode query remains available to the production pipeline in
    memory.  Reports and traces intentionally persist only this identity so a
    user-supplied host path or credential-like value cannot become public run
    metadata.
    """

    raw = query.encode("utf-8")
    return (
        "<task-query "
        f"sha256={canonical_sha256(query)} utf8_bytes={len(raw)}>"
    )


def _public_run_locator(path: str, *, run_dir: str) -> str:
    """Project a run-owned path to a host-free logical locator."""

    candidate = Path(path).resolve()
    root = Path(run_dir).resolve()
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        return f"artifact:{canonical_sha256(str(candidate))}"
    return relative.as_posix()


def _resolve_task_request_arguments(
    args: argparse.Namespace,
    *,
    run_dir: Path | None = None,
) -> ResolvedTaskRequest:
    return resolve_task_request(
        request_manifest=(Path(args.request_manifest) if args.request_manifest else None),
        query=args.query,
        query_file=(Path(args.query_file) if args.query_file else None),
        query_file_encoding=args.query_file_encoding,
        named_inputs=tuple(args.input),
        input_manifest=(Path(args.input_manifest) if args.input_manifest else None),
        allowed_public_input_roots=tuple(
            Path(item) for item in getattr(args, "public_input_root", ())
        ),
        project_root=Path(PROJECT_ROOT),
        run_dir=run_dir,
    )


def _protected_contract_guard(subtask: Subtask) -> dict | None:
    artifact_type = subtask.artifact_type.value
    ext = subtask.output_extension or ""
    contract = subtask.output_contract
    produced_files = contract.produced_files if contract is not None else []
    protected = (
        artifact_type in {"code", "json", "csv"}
        or ext.lower() in {".py", ".json", ".csv"}
        or bool(produced_files)
    )
    if not protected:
        return None
    return {
        "id": subtask.id,
        "role": subtask.role,
        "description": subtask.description,
        "expected_output": subtask.expected_output,
        "depends_on": list(subtask.depends_on),
        "artifact_type": artifact_type,
        "output_extension": ext,
        "task_stage": subtask.task_stage.value if subtask.task_stage is not None else None,
        "output_contract": contract.model_dump(mode="json") if contract is not None else None,
    }


def _collect_protected_contracts(planner_output: PlannerOutput) -> dict[str, dict]:
    guards: dict[str, dict] = {}
    for subtask in planner_output.subtasks:
        guard = _protected_contract_guard(subtask)
        if guard is not None:
            guards[subtask.id] = guard
    return guards


def _subtask_satisfies_guard(subtask: Subtask, guard: dict) -> bool:
    guard_type = str(guard.get("artifact_type") or "")
    guard_ext = str(guard.get("output_extension") or "").lower()
    if guard_type and subtask.artifact_type.value == guard_type:
        return True
    if guard_ext and str(subtask.output_extension or "").lower() == guard_ext:
        return True
    guard_contract = guard.get("output_contract") or {}
    guard_files = {
        str(item.get("path_hint"))
        for item in guard_contract.get("produced_files", [])
        if isinstance(item, dict) and item.get("path_hint")
    }
    current_contract = subtask.output_contract
    current_files = set()
    if current_contract is not None:
        current_files = {
            str(item.path_hint)
            for item in current_contract.produced_files
            if item.path_hint
        }
    return bool(guard_files and guard_files.intersection(current_files))


def preserve_replan_contracts(
    planner_output: PlannerOutput,
    original_contracts: dict[str, dict],
    completed_artifacts: dict,
) -> PlannerOutput:
    """Prevent graph-level replans from silently downgrading protected artifact contracts."""
    if not original_contracts:
        return planner_output

    subtasks = list(planner_output.subtasks)
    by_id = {subtask.id: idx for idx, subtask in enumerate(subtasks)}
    completed_ids = set(completed_artifacts.keys())
    changed = False

    for original_id, guard in original_contracts.items():
        if original_id in completed_ids:
            continue
        if original_id in by_id:
            idx = by_id[original_id]
            current = subtasks[idx]
            updates = {}
            if current.artifact_type.value != guard["artifact_type"]:
                updates["artifact_type"] = guard["artifact_type"]
            if guard.get("output_extension") and current.output_extension != guard["output_extension"]:
                updates["output_extension"] = guard["output_extension"]
            if guard.get("output_contract"):
                updates["output_contract"] = SubtaskOutputContract.model_validate(guard["output_contract"])
            if guard.get("expected_output") and current.expected_output != guard["expected_output"]:
                updates["expected_output"] = guard["expected_output"]
            if guard.get("task_stage") and current.task_stage != guard["task_stage"]:
                updates["task_stage"] = guard["task_stage"]
            if updates:
                subtasks[idx] = current.model_copy(update=updates)
                changed = True
            continue

        if any(_subtask_satisfies_guard(subtask, guard) for subtask in subtasks):
            continue

        completion_id = f"{original_id}_contract_completion"
        suffix = 2
        existing_ids = {subtask.id for subtask in subtasks}
        while completion_id in existing_ids:
            completion_id = f"{original_id}_contract_completion_{suffix}"
            suffix += 1
        subtasks.append(
            Subtask(
                id=completion_id,
                role=f"{guard.get('role') or 'contract'}_completion",
                description=(
                    "Complete the preserved output contract from the original plan. "
                    + str(guard.get("description") or "")
                ),
                expected_output=str(guard.get("expected_output") or guard.get("description") or ""),
                depends_on=list(completed_ids),
                artifact_type=guard["artifact_type"],
                output_extension=guard.get("output_extension") or "",
                task_stage=guard.get("task_stage"),
                output_contract=(
                    SubtaskOutputContract.model_validate(guard["output_contract"])
                    if guard.get("output_contract")
                    else None
                ),
            )
        )
        changed = True

    return planner_output.model_copy(update={"subtasks": subtasks}) if changed else planner_output


def _apply_patch_to_planner_output(planner_output: PlannerOutput, patch) -> PlannerOutput:
    """Apply a local DAG patch to PlannerOutput without mutating during iteration."""
    task_graph = {node.id: node.model_copy(deep=True) for node in planner_output.subtasks}
    ready_queue: list[str] = []
    processed_ids: set[str] = set()
    DAGOrchestrator.apply_dag_patch(task_graph, ready_queue, processed_ids, patch)
    return planner_output.model_copy(update={"subtasks": list(task_graph.values())})


def _append_jsonl(path: str, event: dict) -> None:
    """Append a JSONL training trace event without coupling it to logger output."""
    append_formal_jsonl(path, event)


def _atomic_write_json(path: str, payload: object) -> None:
    """Persist one deterministic JSON artifact without exposing a half-written file."""

    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(
            payload,
            handle,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            default=str,
        )
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _validate_loaded_retrieval_inputs(
    identity: RetrievalRuntimeIdentity,
    library: list[Manifest],
    resource_index: dict[str, dict],
    *,
    policy_path: str | Path | None = None,
) -> None:
    """Bind the in-memory pool/index view to the pre-paid immutable identity."""

    validate_loaded_retrieval_backend(
        identity,
        resource_index=resource_index,
        policy_path=policy_path,
    )

    library_ids = {item.id for item in library}
    index_ids = set(resource_index)
    eligible_ids = set(identity.eligible_resource_ids)
    if library_ids != eligible_ids or index_ids != eligible_ids:
        raise RetrievalRuntimeError("retrieval_loaded_pool_identity_mismatch")
    if len(library) != len(library_ids):
        raise RetrievalRuntimeError("retrieval_loaded_pool_duplicate_resource_id")
    for manifest in library:
        raw = resource_index.get(manifest.id)
        raw_type_block = raw.get("type") if isinstance(raw, dict) else None
        raw_type = str(
            (raw_type_block.get("resource_type") if isinstance(raw_type_block, dict) else None)
            or (raw.get("resource_type") if isinstance(raw, dict) else None)
            or ""
        )
        if raw_type != manifest.type.value:
            raise RetrievalRuntimeError("retrieval_loaded_manifest_type_mismatch")


def _build_resource_definitions(
    resource_index: dict[str, dict],
) -> dict[str, ResourceDefinition]:
    """Project the frozen effective pool once, before any Planner call."""

    definitions: dict[str, ResourceDefinition] = {}
    for resource_id in sorted(resource_index):
        raw = resource_index[resource_id]
        definition = ResourceDefinition.from_manifest(raw)
        if definition.resource_id != resource_id:
            raise RetrievalRuntimeError("resource_definition_index_identity_mismatch")
        definitions[resource_id] = definition
    return definitions


def _plan_compiler_response_mode(
    raw_model_manifest: dict,
    *,
    configured_mode: str | None = None,
) -> str:
    """Require strict schema mode for every machine-parsed system role."""

    if configured_mode is not None:
        try:
            mode = normalize_structured_response_mode(configured_mode)
        except ModelResponseContractError as exc:
            raise ValueError("formal_system_role_requires_exact_json_schema") from exc
        if mode != "native_strict_schema":
            raise ValueError("formal_system_role_requires_exact_json_schema")
    del raw_model_manifest
    return "native_strict_schema"


def _plan_runtime_capabilities(
    resource_index: dict[str, dict],
    *,
    runtime_image: str,
) -> RuntimeCapabilities:
    artifact_types = sorted(
        {
            str((raw.get("output_contract") or {}).get("artifact_type") or "unknown")
            for raw in resource_index.values()
        }
    )
    resource_types = sorted(
        {
            str(
                (
                    (raw.get("type") or {}).get("resource_type")
                    if isinstance(raw.get("type"), dict)
                    else None
                )
                or raw.get("resource_type")
                or "Resource"
            )
            for raw in resource_index.values()
        }
    )
    return RuntimeCapabilities(
        runtime_image_id=str(runtime_image),
        supported_runtime_kinds=supported_runtime_kinds(resource_types),
        supported_entrypoint_dispatch_kinds=supported_runtime_kinds(resource_types),
        network_policy="declared_only",
        artifact_contract_support=tuple(artifact_types),
        material_adapter_capabilities=(
            build_runtime_material_adapter_capabilities(resource_types)
        ),
        protocol_versions={
            "resource_runtime": RESOURCE_RUNTIME_PROTOCOL,
            "resource_call": RESOURCE_CALL_PROTOCOL,
            "canonical_result": CANONICAL_RESULT_PROTOCOL,
            "execution_world": EXECUTION_WORLD_PROTOCOL,
        },
    )


def _record_frozen_retrieval(
    *,
    trace_path: str,
    output_dir: str,
    run_id: str,
    frozen_result: FrozenCandidatePoolResult,
) -> str:
    """Persist the host-free frozen result and its structured lifecycle events."""

    for attempt in frozen_result.retrieval_attempts:
        _append_jsonl(
            trace_path,
            {
                "event_type": "retrieval_attempt",
                "stage": "candidate_pool_preparation",
                "revision": frozen_result.contract_projection.revision.model_dump(mode="json"),
                "attempt": attempt.model_dump(mode="json"),
            },
        )
    publication = persist_frozen_candidate_pool(
        frozen_result=frozen_result,
        run_id=run_id,
        run_dir=output_dir,
        event_writer=lambda event: _append_jsonl(trace_path, dict(event)),
    )
    return publication.candidate_artifact_locator


def _model_liveness_manifest_identity(run_dir: str | Path) -> dict[str, object]:
    """Project only hashes from published candidate liveness evidence."""

    candidate_root = Path(run_dir) / "candidate_pools"
    entries: list[dict[str, object]] = []
    if candidate_root.is_dir():
        for path in sorted(candidate_root.glob("*.json")):
            if path.name.endswith(".publication.json"):
                continue
            frozen = FrozenCandidatePoolResult.model_validate_json(
                path.read_text(encoding="utf-8-sig", errors="strict")
            )
            evidence_hashes = [
                item.evidence_sha256 for item in frozen.model_liveness_evidence
            ]
            entries.append(
                {
                    "revision_sha256": canonical_sha256(frozen.revision),
                    "candidate_pool_sha256": (
                        frozen.candidate_pool_snapshot.candidate_pool_sha256
                    ),
                    "retrieval_evidence_sha256": frozen.retrieval_evidence_sha256,
                    "model_liveness_evidence_sha256": canonical_sha256(
                        evidence_hashes
                    ),
                }
            )
    return {
        "model_liveness_candidate_set_count": len(entries),
        "model_liveness_evidence_sha256": canonical_sha256(entries),
        "model_liveness_candidate_sets": entries,
    }


def _dag_edge_manifest_identity(run_dir: str | Path) -> dict[str, object]:
    """Project content-free Planner edge identities into the Run Manifest."""

    trace_path = Path(run_dir) / "trace.jsonl"
    edge_hashes: list[str] = []
    edge_set_hash = canonical_sha256([])
    if trace_path.is_file():
        with trace_path.open("r", encoding="utf-8-sig", errors="strict") as handle:
            for line in handle:
                if not line.strip():
                    continue
                event = json.loads(line)
                if event.get("event_type") != "planner_trace":
                    continue
                edges = event.get("dag_edge_contracts") or []
                edge_hashes = sorted(
                    str(item.get("edge_contract_sha256") or "")
                    for item in edges
                    if isinstance(item, Mapping)
                    and str(item.get("edge_contract_sha256") or "")
                )
                edge_set_hash = canonical_sha256(edges)
    return {
        "dag_edge_contract_count": len(edge_hashes),
        "dag_edge_contract_sha256s": edge_hashes,
        "dag_edge_contracts_sha256": edge_set_hash,
    }


def _planner_attempt_manifest_identity(run_dir: str | Path) -> dict[str, object]:
    """Project the complete content-free Planner attempt history into the manifest."""

    evidence_path = Path(run_dir) / "planner_attempts.jsonl"
    records: list[dict[str, object]] = []
    if evidence_path.is_file():
        with evidence_path.open("r", encoding="utf-8-sig", errors="strict") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise RuntimeError(
                        f"planner_attempt_evidence_record_invalid:{line_number}"
                    )
                claimed = str(record.get("attempt_evidence_sha256") or "")
                unsigned = dict(record)
                unsigned.pop("attempt_evidence_sha256", None)
                if claimed != canonical_sha256(unsigned):
                    raise RuntimeError(
                        f"planner_attempt_evidence_hash_mismatch:{line_number}"
                    )
                if "raw_response" in record or "provider_reasoning" in record:
                    raise RuntimeError("planner_attempt_evidence_contains_private_content")
                records.append(dict(record))
    return {
        "planner_attempt_evidence_protocol": "sgar-planner-attempt-evidence-v1",
        "planner_attempt_count": len(records),
        "planner_attempt_history_sha256": canonical_sha256(records),
        "planner_attempt_file_sha256": (
            hashlib.sha256(evidence_path.read_bytes()).hexdigest()
            if evidence_path.is_file()
            else None
        ),
        "planner_attempt_history": records,
    }


def _is_system_execution_failure(message: str) -> bool:
    lowered = str(message or "").lower()
    if "graph_replan_allowed=false" in lowered:
        return True
    if any(
        marker in lowered
        for marker in (
            "failure_category=system_deterministic",
            "failure_category=provider",
            "failure_category=model_content",
            "failure_category=resource_selection",
            "failure_category=budget",
        )
    ):
        return True
    return any(
        marker in lowered
        for marker in (
            "validation_target_ambiguous",
            "validation_target_missing",
            "tool_semantic_misuse",
            "binding_ambiguous",
            "tool_path_mapping_error",
            "runner_cwd_error",
            "artifact_dependency_missing",
            "resource_dependency_missing",
            "runtime_profile_unavailable",
            "runtime_warmup_timeout",
            "runtime_image_pull_failed",
            "environment_preflight_failed",
            "dependency_install_blocked",
            "dependency_install_failed",
            "dependency_install_timeout",
            "tool_semantic_failure",
            "tool_semantic_misuse",
            "contract_produced_file_missing",
            "contract_code_extraction_ambiguous",
            "placeholder_content",
            "format_invalid",
            "provider_connection_error",
            "provider_stream_error",
            "model_unavailable",
            "budget_guarded_failure",
        )
    )


# ─────────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────────

def _session_status_value(session) -> str:
    status = getattr(session, "execution_status", None)
    if status is None:
        return ""
    return getattr(status, "value", str(status))


def _pipeline_recovery_outcome_projection(
    recovery_outcomes: object,
) -> Mapping[str, object] | None:
    items = sorted(
        (
            dict(item)
            for item in (recovery_outcomes or ())
            if isinstance(item, Mapping)
        ),
        key=lambda item: str(item.get("subtask_id") or ""),
    )
    return (
        {
            "protocol": "sgar-recovery-outcomes-v1",
            "subtasks": items,
        }
        if items
        else None
    )


def _successful_pipeline_status(routing_bundles: dict) -> str:
    saw_session = False
    saw_warning = False
    for bundle in routing_bundles.values():
        if not isinstance(bundle, dict):
            continue
        session = bundle.get("routing_session")
        if session is None:
            continue
        saw_session = True
        status = _session_status_value(session)
        if status == "structured_failure" or status == "":
            return _structured_pipeline_failure(
                responsibility="framework",
                failure_stage="pipeline_status",
                failure_code="routing_session_failure_missing_terminal_envelope",
            )
        attempts = getattr(session, "attempts", None) or []
        hard_failures = {
            "operation_kind_missing",
            "operation_misuse",
            "tool_runtime_error",
            "tool_semantic_failure",
            "tool_semantic_misuse",
            "binding_ambiguous",
            "tool_path_type_mismatch",
        }
        has_hard_failure = any(
            str(getattr(attempt, "failure_type", "") or "") in hard_failures
            for attempt in attempts
        )
        has_successful_attempt = any(
            bool(getattr(attempt, "repair_success", False))
            or any(
                str(getattr(step, "status", "") or "") == "success"
                for step in (getattr(attempt, "execution_step_trace", None) or [])
            )
            for attempt in attempts
        )
        if has_hard_failure and not has_successful_attempt:
            return _structured_pipeline_failure(
                responsibility="framework",
                failure_stage="pipeline_status",
                failure_code="routing_attempt_failure_missing_terminal_envelope",
            )
        if status == "success_with_warnings":
            saw_warning = True
    if not saw_session:
        return _structured_pipeline_failure(
            responsibility="framework",
            failure_stage="pipeline_status",
            failure_code="pipeline_finalized_session_missing",
        )
    recovery_outcomes: list[dict[str, object]] = []
    causal_chain: list[dict[str, object]] = []
    for subtask_id in sorted(str(item) for item in routing_bundles):
        bundle = routing_bundles.get(subtask_id)
        recovery = bundle.get("recovery") if isinstance(bundle, Mapping) else None
        if not isinstance(recovery, Mapping):
            continue
        outcome = recovery.get("recovery_outcome")
        if outcome is not None:
            recovery_outcomes.append(
                {"subtask_id": subtask_id, "outcome": str(outcome)}
            )
        for item in recovery.get("causal_chain") or ():
            code = str(item or "")
            if not code:
                continue
            causal_chain.append(
                {
                    "sequence": len(causal_chain),
                    "kind": "recovered_event",
                    "subtask_id": subtask_id,
                    "failure_code": code,
                }
            )
    return PipelineTerminalStatus(
        "success_with_warnings" if saw_warning else "complete_success",
        recovery_outcomes=tuple(recovery_outcomes),
        causal_chain=tuple(causal_chain),
    )


class PipelineTerminalStatus(str):
    """String-compatible pipeline result carrying structured terminal ownership."""

    def __new__(
        cls,
        value: str,
        *,
        responsibility: str = "research",
        failure_stage: str = "pipeline",
        failure_code: str = "pipeline_structured_failure",
        failure: TerminalFailureEnvelope | None = None,
        primary_failure: TerminalFailureEnvelope | None = None,
        terminal_failure: TerminalFailureEnvelope | None = None,
        recovery_outcomes: tuple[Mapping[str, object], ...] = (),
        causal_chain: tuple[Mapping[str, object], ...] = (),
    ) -> "PipelineTerminalStatus":
        instance = str.__new__(cls, value)
        resolved_terminal = terminal_failure or failure or primary_failure
        resolved_primary = primary_failure or failure or terminal_failure
        instance.responsibility = (
            resolved_terminal.responsibility
            if resolved_terminal is not None
            else responsibility
        )
        instance.failure_stage = (
            resolved_terminal.failure_stage
            if resolved_terminal is not None
            else failure_stage
        )
        instance.failure_code = (
            resolved_terminal.failure_code
            if resolved_terminal is not None
            else failure_code
        )
        instance.primary_failure = resolved_primary
        instance.terminal_failure = resolved_terminal
        instance.failure = resolved_terminal
        instance.recovery_outcomes = tuple(
            dict(item) for item in recovery_outcomes
        )
        instance.causal_chain = tuple(dict(item) for item in causal_chain)
        return instance


def _pipeline_terminal_projection(status: object) -> dict[str, object]:
    terminal = getattr(status, "terminal_failure", None) or getattr(
        status, "failure", None
    )
    primary = getattr(status, "primary_failure", None) or terminal
    if not isinstance(primary, TerminalFailureEnvelope) or not isinstance(
        terminal, TerminalFailureEnvelope
    ):
        raise TypeError("pipeline_terminal_projection_requires_failures")
    recovery_outcome = _pipeline_recovery_outcome_projection(
        getattr(status, "recovery_outcomes", ())
    )
    causal_chain = tuple(
        dict(item)
        for item in (getattr(status, "causal_chain", ()) or ())
        if isinstance(item, Mapping)
    )
    if not causal_chain:
        causal: list[dict[str, object]] = [
            {
                "sequence": 0,
                "kind": "primary_failure",
                "subtask_id": primary.subtask_id,
                "responsibility": primary.responsibility,
                "failure_stage": primary.failure_stage,
                "failure_code": primary.failure_code,
                "failure_sha256": primary.failure_sha256,
            }
        ]
        if terminal.failure_sha256 != primary.failure_sha256:
            causal.append(
                {
                    "sequence": 1,
                    "kind": "terminal_failure",
                    "subtask_id": terminal.subtask_id,
                    "responsibility": terminal.responsibility,
                    "failure_stage": terminal.failure_stage,
                    "failure_code": terminal.failure_code,
                    "failure_sha256": terminal.failure_sha256,
                }
            )
        causal_chain = tuple(causal)
    return {
        "status": terminal.run_status,
        "primary_failure": structured_run_failure_from_terminal(primary),
        "terminal_failure": structured_run_failure_from_terminal(terminal),
        "recovery_outcome": recovery_outcome,
        "causal_chain": causal_chain,
    }


def _structured_pipeline_failure(
    *,
    responsibility: str,
    failure_stage: str,
    failure_code: str,
    exception_type: str = "",
    message_sha256: str | None = None,
    response_received: bool = False,
) -> PipelineTerminalStatus:
    if responsibility not in {
        "framework",
        "infrastructure",
        "research",
        "budget",
        "interrupted",
    }:
        responsibility = "framework"
        failure_stage = "failure_contract"
        failure_code = "pipeline_failure_responsibility_invalid"
    failure = TerminalFailureEnvelope.create(
        responsibility=responsibility,
        failure_stage=failure_stage,
        failure_code=failure_code,
        exception_type=exception_type,
        message_sha256=message_sha256,
        response_received=response_received,
    )
    return PipelineTerminalStatus(
        "structured_failure",
        responsibility=responsibility,
        failure_stage=failure_stage,
        failure_code=failure_code,
        failure=failure,
    )


def _pipeline_status_from_terminal_failure(
    failure: TerminalFailureEnvelope,
) -> PipelineTerminalStatus:
    return PipelineTerminalStatus(
        "structured_failure",
        responsibility=failure.responsibility,
        failure_stage=failure.failure_stage,
        failure_code=failure.failure_code,
        failure=failure,
    )


def _execution_terminal_failure_status(execution_summary: dict) -> PipelineTerminalStatus:
    """Derive ownership only from ResourceRuntime terminal event producers."""

    counts = dict(execution_summary.get("by_responsibility") or {})
    for responsibility in (
        "framework",
        "interrupted",
        "infrastructure",
        "budget",
        "research",
    ):
        if int(counts.get(responsibility) or 0) > 0:
            return _structured_pipeline_failure(
                responsibility=responsibility,
                failure_stage="execution",
                failure_code="resource_execution_terminal_failure",
            )
    return _structured_pipeline_failure(
        responsibility="research",
        failure_stage="pipeline",
        failure_code="pipeline_structured_failure",
    )


def _final_pipeline_log_label(status: str) -> str:
    if status == "complete_success":
        return "S-GAR MVP - Complete (success)"
    if status == "success_with_warnings":
        return "S-GAR MVP - Complete (success_with_warnings)"
    return "S-GAR MVP - Structured Failure"


def _terminal_pipeline_log_lines(status: str) -> list[str]:
    """Return terminal status lines derived only from the strict pipeline result."""
    return [_final_pipeline_log_label(status)]


def _planner_parse_metadata_with_control_trace(
    planner: SGARPlanner,
    *,
    selected_model: str,
    attempted_models: list[dict],
) -> dict:
    metadata = dict(getattr(planner, "last_parse_metadata", {}) or {})
    metadata["selected_control_model"] = selected_model
    metadata["attempted_control_models"] = [item.get("model_id") for item in attempted_models]
    metadata["control_model_failover_reasons"] = [
        {
            "model_id": item.get("model_id"),
            "failure_type": item.get("failure_type"),
            "reason": item.get("reason"),
        }
        for item in attempted_models
        if item.get("failure_type")
    ]
    return metadata


def _decompose_with_control_models(
    *,
    llm_key: str,
    base_url: str,
    control_models: list[str],
    failover_enabled: bool,
    budget_manager,
    cost_ledger=None,
    user_query: str,
    completed_artifacts: dict | None,
    original_contracts: dict[str, dict] | None,
    capability_cards: list[CapabilityCard] | None = None,
    sync_model_transport: SyncModelTransportPort | None = None,
    response_modes: Mapping[str, str] | None = None,
    planner_max_output_tokens: int | None = None,
    planner_role_policy: ControlRoleInvocationPolicyV1 | None = None,
    planner_attempt_evidence_path: str | None = None,
) -> tuple[SGARPlanner, PlannerOutput, list[dict]]:
    attempted: list[dict] = []
    last_error: Exception | None = None
    for idx, model_id in enumerate(control_models):
        planner = SGARPlanner(
            api_key=llm_key,
            base_url=base_url,
            model=model_id,
            budget_manager=budget_manager,
            cost_ledger=cost_ledger,
            transport=sync_model_transport,
            strict_response_schema=True,
            response_mode=(response_modes or {}).get(model_id),
            max_output_tokens=planner_max_output_tokens,
            role_policy=planner_role_policy,
            attempt_evidence_path=planner_attempt_evidence_path,
        )
        try:
            output = planner.decompose_task(
                user_query,
                completed_artifacts=completed_artifacts,
                original_contracts=original_contracts,
                capability_cards=capability_cards,
            )
            parse_mode = str(getattr(planner, "last_parse_metadata", {}).get("parse_mode") or "")
            if (
                failover_enabled
                and parse_mode == "deterministic_fallback"
                and idx < len(control_models) - 1
            ):
                attempted.append(
                    {
                        "model_id": model_id,
                        "status": "failed",
                        "failure_type": "schema_exhausted",
                        "reason": "Planner exhausted provider JSON/schema modes and used deterministic fallback.",
                    }
                )
                logger.warning(
                    "[ControlModel] Planner model {} exhausted schema modes; trying next control model.",
                    model_id,
                )
                continue
            # A deterministic DAG is a valid planner result.  It must proceed
            # through Router and real execution; treating it as schema
            # exhaustion prevented every Tool case from reaching execution
            # whenever the provider emitted a locally repairable contract.
            attempted.append({"model_id": model_id, "status": "success"})
            planner.last_parse_metadata = _planner_parse_metadata_with_control_trace(
                planner,
                selected_model=model_id,
                attempted_models=attempted,
            )
            return planner, output, attempted
        except ModelAccountingError:
            raise
        except (asyncio.CancelledError, KeyboardInterrupt):
            raise
        except Exception as exc:
            last_error = exc
            failure_type, message = classify_control_model_exception(exc)
            attempted.append(
                {
                    "model_id": model_id,
                    "status": "failed",
                    "failure_type": failure_type,
                    "reason": message,
                }
            )
            if not failover_enabled or idx >= len(control_models) - 1 or not is_control_model_failover_failure(failure_type):
                raise
            logger.warning(
                "[ControlModel] Planner model {} failed with {}; trying next control model.",
                model_id,
                failure_type,
            )
    raise ModelResponseContractError("control_model_chain_exhausted") from last_error


def _planner_generation_failure(
    exc: BaseException,
    *,
    run_id: str,
) -> TerminalFailureEnvelope:
    if isinstance(exc, PlannerGenerationError):
        return TerminalFailureEnvelope.create(
            responsibility=exc.responsibility,
            failure_stage=exc.failure_stage,
            failure_code=exc.failure_code,
            exception=exc,
            retryable=exc.retryable,
            response_received=exc.response_received,
            run_id=run_id,
            request_sha256=exc.request_sha256,
        )
    if isinstance(exc, BudgetControlError):
        return TerminalFailureEnvelope.create(
            responsibility="budget",
            failure_stage="planner_generation",
            failure_code=str(getattr(exc, "error_code", "model_cost_limit_reached")),
            exception=exc,
            run_id=run_id,
        )
    if isinstance(exc, ModelAccountingError):
        return TerminalFailureEnvelope.create(
            responsibility="framework",
            failure_stage="model_accounting",
            failure_code=str(getattr(exc, "error_code", "model_accounting_failure")),
            exception=exc,
            run_id=run_id,
        )
    if isinstance(exc, (asyncio.CancelledError, KeyboardInterrupt)):
        return TerminalFailureEnvelope.create(
            responsibility="interrupted",
            failure_stage="planner_generation",
            failure_code="planner_generation_interrupted",
            exception=exc,
            run_id=run_id,
        )
    failure_type, _message = classify_control_model_exception(
        exc if isinstance(exc, Exception) else Exception(type(exc).__name__)
    )
    if failure_type in {
        "schema_exhausted",
        "json_parse_exhausted",
        "empty_response_exhausted",
    }:
        responsibility = "research"
        failure_code = "planner_generation_schema_invalid"
        response_received = True
    elif failure_type in {
        "provider_connection_error",
        "provider_stream_error",
        "provider_rate_limit",
        "provider_server_error",
        "provider_authorization_error",
        "provider_model_unavailable",
        "provider_non_retryable_status",
        "model_unavailable",
    }:
        responsibility = "infrastructure"
        failure_code = failure_type
        response_received = False
    else:
        responsibility = "framework"
        failure_code = "planner_generation_control_failure"
        response_received = False
    return TerminalFailureEnvelope.create(
        responsibility=responsibility,
        failure_stage="planner_generation",
        failure_code=failure_code,
        exception=exc,
        retryable=responsibility == "infrastructure",
        response_received=response_received,
        run_id=run_id,
    )


async def _run_pipeline_with_cost_ledger(
    config: dict,
    user_query: str,
    output_dir: str,
    report_path: str,
    cost_ledger: RunCostLedger,
    execution_ledger: RunExecutionLedger,
    recovery_policy: RecoveryPolicy,
    recovery_ledger: RecoveryEventLedger,
    evaluator_policy: EvaluatorPolicy | None,
    evaluation_ledger: EvaluationEventLedger,
    artifact_store: ArtifactLifecycleStore,
    context_commit_store: ContextCommitStore,
    system_role_probe_audit: SystemRoleProbeAuditStore,
    query_diagnostics: dict | None = None,
    task_invocation: PreparedTaskInvocation | None = None,
    network_policy_mode: str = "disabled",
    planner_variant: str = "resource_aware",
    runtime_authority: str = "git",
    execution_substrate: object | None = None,
    execution_substrate_mode: str = "default",
    require_final_delivery: bool = True,
) -> str:
    llm_key = config["llm_key"]
    llm_settings = config.get("llm_settings", {})
    evaluation_mode = normalize_evaluation_mode(
        llm_settings.get("evaluation_mode")
    )
    capability_probe_enforcement_policy = (
        normalize_capability_probe_enforcement_policy(
            llm_settings.get("capability_probe_enforcement_policy")
        )
    )
    control_role_policy_path = _runtime_policy_path(
        config,
        "control_role_policy_path",
        "sgar_mvp/config/control_role_policy.json",
    )
    retrieval_policy_path = _runtime_policy_path(
        config,
        "retrieval_policy_path",
        "sgar_mvp/config/retrieval_policy.json",
    )
    model_profile_path = None
    runtime_settings = config.get("runtime_settings")
    if isinstance(runtime_settings, Mapping) and runtime_settings.get("model_profile_path"):
        model_profile_path = _runtime_policy_path(
            config,
            "model_profile_path",
            "sgar_mvp/config/model_profile.json",
        )
    # Bind the selected policy before any resource-loader path can import the
    # lazy retrieval backend.  This is essential for isolated experiment
    # policies and is a no-op identity check for the default production policy.
    bind_retrieval_policy_path(retrieval_policy_path)
    control_role_policy = load_control_role_policy(control_role_policy_path)
    retrieval_policy = load_retrieval_policy(retrieval_policy_path)
    if model_profile_path is None and control_role_policy.protocol == CONTROL_ROLE_POLICY_PROTOCOL:
        model_profile_path = Path(PROJECT_ROOT) / "sgar_mvp/config/model_profile.json"
    if model_profile_path is not None:
        profile = load_control_model_profile(model_profile_path)
        try:
            require_policy_matches_model_profile(control_role_policy, profile)
        except ValueError as exc:
            raise RuntimeError("control_policy_model_profile_mismatch") from exc
        if evaluation_mode != profile.evaluation_mode:
            raise RuntimeError("evaluation_mode_model_profile_mismatch")
        if (
            retrieval_policy.embedding_model != profile.embedding_model
            or retrieval_policy.embedding_candidate_id != profile.embedding_candidate_id
        ):
            raise RuntimeError("embedding_model_profile_mismatch")
    base_url = llm_settings.get("base_url", "https://api.openai.com/v1")
    configured_model = llm_settings.get("model", DEFAULT_SYSTEM_MODEL_CHAIN[0])
    model_transport_bundle = create_production_model_transport_bundle(
        api_key=llm_key,
        base_url=base_url,
    )
    if runtime_authority not in {"git", "release"}:
        raise RuntimeError("runtime_authority_invalid")
    if (
        runtime_authority == "release"
        and control_role_policy.protocol != CONTROL_ROLE_POLICY_PROTOCOL
    ):
        raise RuntimeError("experimental_control_policy_forbidden_in_release")
    planner_policy = control_role_policy.for_role("planner")
    configured_chain = tuple(llm_settings.get("system_model_chain") or ())
    if configured_model != planner_policy.api_model_id or configured_chain not in {
        (),
        (planner_policy.api_model_id,),
    }:
        raise RuntimeError("configured_planner_control_policy_mismatch")
    profiler_policy = control_role_policy.for_role("profiler")
    if (
        retrieval_policy.hyde.resource_id != profiler_policy.resource_id
        or retrieval_policy.hyde.api_model_id != profiler_policy.api_model_id
        or retrieval_policy.hyde.reasoning_effort != profiler_policy.reasoning_effort
        or retrieval_policy.hyde.temperature != profiler_policy.temperature
        or retrieval_policy.control_role_policy_sha256
        != control_role_policy.policy_sha256
    ):
        raise RuntimeError("profiler_control_policy_mismatch")
    if evaluation_mode != "off":
        if evaluator_policy is None:
            raise RuntimeError("evaluator_policy_missing")
        evaluator_role_policy = control_role_policy.for_role("evaluator")
        if (
            evaluator_policy.model_resource_id != evaluator_role_policy.resource_id
            or evaluator_policy.reasoning_effort != evaluator_role_policy.reasoning_effort
            or evaluator_policy.temperature != evaluator_role_policy.temperature
        ):
            raise RuntimeError("evaluator_control_policy_mismatch")
    if runtime_authority == "release":
        provider_probe_receipt_path, provider_probe_receipt = (
            resolve_activated_release_provider_probe_receipt(
                PROJECT_ROOT,
                expected_endpoint_identity_sha256=(
                    model_transport_bundle.endpoint_identity.identity_sha256
                ),
            )
        )
        system_role_probe_audit.bind_sealed_receipt(
            receipt_file_sha256=hashlib.sha256(
                provider_probe_receipt_path.read_bytes()
            ).hexdigest(),
            result_sha256=str(provider_probe_receipt["result_sha256"]),
        )
    else:
        provider_probe_receipt_path, provider_probe_receipt = load_git_control_probe_receipt(
            PROJECT_ROOT, config=config,
            expected_endpoint_identity_sha256=(
                model_transport_bundle.endpoint_identity.identity_sha256
            ),
            control_role_policy=control_role_policy,
        )
    provider_probe_records = {
        str(item["role"]): dict(item) for item in provider_probe_receipt["records"]
    }
    if tuple(provider_probe_records) != RELEASE_PROVIDER_PROBE_ROLES:
        raise RuntimeError("control_probe_role_order_mismatch")
    public_query_reference = _public_query_reference(user_query)
    trace_path = os.path.join(output_dir, "trace.jsonl")
    if os.path.exists(trace_path):
        os.remove(trace_path)
    runtime_mode = "external" if execution_substrate is not None else "native"
    _append_jsonl(
        trace_path,
        {
            "event_type": "runtime_mode",
            "stage": "main_startup",
            "runtime_mode": runtime_mode,
            "execution_substrate_mode": execution_substrate_mode,
            "execution_substrate_id": (
                str(getattr(execution_substrate, "runtime_id", ""))
                if execution_substrate is not None
                else None
            ),
        },
    )
    retrieval_identity = build_retrieval_runtime_identity(
        project_root=PROJECT_ROOT,
        provider_compatibility=_provider_compatibility_projection(base_url),
        provider_endpoint_identity_sha256=(
            model_transport_bundle.endpoint_identity.identity_sha256
        ),
        require_release_sealed=(runtime_authority == "release"),
        honor_release_environment=(runtime_authority == "release"),
        policy_path=retrieval_policy_path,
    )
    _atomic_write_json(
        os.path.join(output_dir, "retrieval_runtime_identity.json"),
        retrieval_identity.model_dump(mode="json"),
    )
    applied_ready_state = None
    if runtime_authority == "git":
        applied_ready_state = load_applied_model_ready_state(
            PROJECT_ROOT,
            expected_endpoint_identity_sha256=(
                model_transport_bundle.endpoint_identity.identity_sha256
            ),
        )
        system_role_probe_audit.bind_git_runtime(
            applied_ready_state_sha256=applied_ready_state.health_sha256,
            control_probe_receipt_sha256=hashlib.sha256(
                provider_probe_receipt_path.read_bytes()
            ).hexdigest(),
            control_probe_result_sha256=str(provider_probe_receipt["result_sha256"]),
        )
        capability_probe_service: Any = AppliedReadyStateCapabilityService(
            applied_ready_state,
            enforcement_policy=capability_probe_enforcement_policy,
        )
    else:
        capability_probe_service = ExactCapabilityProbeService(
            model_transport_bundle.sync,
            cache_path=os.path.join(
                PROJECT_ROOT,
                ".sgar_cache",
                "model_response_capability_probes.json",
            ),
            enforcement_policy=capability_probe_enforcement_policy,
        )

    retrieval_coordinator = RetrievalCoordinator(
        retrieval_identity,
        sync_model_transport=model_transport_bundle.sync,
        capability_probe_service=capability_probe_service,
        runtime_incompatibility=(
            getattr(execution_substrate, "resource_incompatibility", None)
            if execution_substrate is not None
            else None
        ),
        model_readiness_authority=(
            "applied_ready_state" if runtime_authority == "git" else "live_probe"
        ),
    )
    # Fixed internal roles have independent evidence, outside candidate health.
    control_selector = ControlModelSelector(
        configured_chain=[control_role_policy.for_role("planner").api_model_id],
        available_models=[str(provider_probe_records["planner"]["api_model_id"])],
        health_gate=("sealed_role_probes" if runtime_authority == "release"
                     else "verified_role_probes"),
        health_path=str(provider_probe_receipt_path),
        health_loaded=True,
    )
    control_model_chain = control_selector.execution_chain(configured_model)
    model = control_selector.primary_model(configured_model)
    planner_role_policy = control_role_policy.for_role("planner")
    if model != planner_role_policy.api_model_id:
        raise RuntimeError("sealed_planner_control_policy_model_mismatch")
    if not control_selector.available_models and llm_settings.get("system_model_chain"):
        logger.error(
            "[ControlModel] No health-gated control models available: {}",
            control_selector.public_projection(project_root=PROJECT_ROOT),
        )
        failure = TerminalFailureEnvelope.create(
            responsibility="infrastructure",
            failure_stage="control_model_health_gate",
            failure_code="control_model_health_chain_unavailable",
            run_id=cost_ledger.run_id,
        )
        system_role_probe_audit.terminate(failure)
        return PipelineTerminalStatus(
            "structured_failure",
            responsibility=failure.responsibility,
            failure_stage=failure.failure_stage,
            failure_code=failure.failure_code,
            failure=failure,
        )
    environment_profile = scan_environment(
        probe_docker=(runtime_authority == "release")
    )
    # Single source of truth for the execution runtime image. Executors read the
    # same env var (SGAR_RUNTIME_IMAGE); config.docker_python_image can override.
    runtime_image = os.environ.get("SGAR_RUNTIME_IMAGE") or llm_settings.get(
        "docker_python_image", "python:3.11"
    )
    os.environ["SGAR_RUNTIME_IMAGE"] = runtime_image
    if runtime_authority == "release" and environment_profile.docker_available:
        environment_profile.docker_warmup = warmup_docker_runtime(
            environment_profile,
            image=runtime_image,
            timeout_sec=llm_settings.get("docker_warmup_timeout_sec", 300),
            workspace_root=PROJECT_ROOT,
        )
    _append_jsonl(
        trace_path,
        {
            "event_type": "environment_profile",
            "stage": "main_startup",
            "profile": environment_profile.public_projection(),
        },
    )
    _append_jsonl(
        trace_path,
        {
            "event_type": "control_model_chain",
            "stage": "main_startup",
            **control_selector.public_projection(project_root=PROJECT_ROOT),
        },
    )
    logger.info(
        "[ControlModel] configured={} available={} skipped={}",
        control_selector.configured_chain,
        control_selector.available_models,
        control_selector.skipped_models,
    )
    logger.info(
        "[Environment] docker_cli={} docker_daemon={} docker_ready={} reason={}",
        environment_profile.docker_cli_available,
        environment_profile.docker_daemon_available,
        environment_profile.docker_available,
        (
            "ok"
            if not environment_profile.docker_error
            else canonical_sha256(environment_profile.docker_error)
        ),
    )
    if environment_profile.docker_warmup:
        logger.info(
            "[Environment] docker_warmup={}",
            environment_profile.public_projection()["docker_warmup"],
        )

    # Existing orchestration code reads the compatibility budget properties,
    # while the metered transport remains the sole charging authority.
    budget_manager = cost_ledger

    planner = None
    completed_artifacts = {}
    original_contracts: dict[str, dict] = {}
    replan_history: list[dict] = []
    # Experiments can disable graph-level recovery without changing the normal
    # product default.  A value of zero means one planner pass and no hidden
    # graph replan or granularity patch.
    MAX_PLANNER_REPLANS = max(0, int(llm_settings.get("max_planner_replans", 2)))
    replan_count = 0
    pipeline_status = "structured_failure"

    # Load the exact effective pool/index once for the complete run.  Its
    # in-memory identity is checked against the pre-paid immutable snapshot and
    # never refreshed after Planner or execution begins.
    control_index = control_model_index(
        load_resource_index_static().values(), root=PROJECT_ROOT
    )
    control_definitions = _build_resource_definitions(control_index)
    library, fallback_ids, resource_index = load_real_pool_with_index()
    library, fallback_ids, resource_index = _filter_models_for_provider(
        library,
        fallback_ids,
        resource_index,
        llm_settings,
        base_url,
    )
    eligible_resource_ids = set(retrieval_identity.eligible_resource_ids)
    library = [item for item in library if item.id in eligible_resource_ids]
    fallback_ids = [
        resource_id
        for resource_id in fallback_ids
        if resource_id in eligible_resource_ids
    ]
    resource_index = {
        resource_id: raw
        for resource_id, raw in resource_index.items()
        if resource_id in eligible_resource_ids
    }
    _validate_loaded_retrieval_inputs(
        retrieval_identity,
        library,
        resource_index,
        policy_path=retrieval_policy_path,
    )
    capability_consistency = build_capability_consistency_report(resource_index)
    capability_report_path = os.path.join(
        output_dir,
        "plan_compiler",
        "capability_catalog_consistency.json",
    )
    _atomic_write_json(
        capability_report_path,
        capability_consistency.model_dump(mode="json"),
    )
    _append_jsonl(
        trace_path,
        {
            "event_type": "capability_catalog_consistency",
            "stage": "main_startup",
            "resource_count": capability_consistency.resource_count,
            "sealable_resource_count": (
                capability_consistency.sealable_resource_count
            ),
            "report_sha256": capability_consistency.report_sha256,
        },
    )
    if (
        capability_consistency.sealable_resource_count
        != capability_consistency.resource_count
    ):
        raise RuntimeError("resource_capability_catalog_unsealable")
    planner_probe_record = provider_probe_records["planner"]
    model = str(planner_probe_record["api_model_id"])
    control_resource_id = _resource_id_for_api_model(control_index, model)
    if control_resource_id != planner_probe_record["model_resource_id"]:
        raise RuntimeError("control_planner_probe_resource_identity_mismatch")
    control_model_chain = [model]
    verified_control_modes = {model: "native_strict_schema"}
    system_role_probe_audit.select_model(
        role="planner",
        resource_id=control_resource_id,
        model_id=model,
        response_mode="native_strict_schema",
    )
    profiler_probe_record = provider_probe_records["profiler"]
    if (
        profiler_probe_record["model_resource_id"]
        != retrieval_identity.hyde_resource_id
        or profiler_probe_record["api_model_id"]
        != retrieval_identity.hyde_api_model_id
    ):
        raise RuntimeError("control_profiler_probe_resource_identity_mismatch")
    retrieval_coordinator.set_hyde_response_mode("native_strict_schema")
    system_role_probe_audit.select_model(
        role="profiler",
        resource_id=retrieval_identity.hyde_resource_id,
        model_id=retrieval_identity.hyde_api_model_id,
        response_mode="native_strict_schema",
    )
    planner_capability_cards: list[CapabilityCard] = []
    if planner_variant == "resource_aware":
        planner_capability_cards = list(
            build_capability_cards(resource_index).values()
        )
        if not planner_capability_cards:
            failure = TerminalFailureEnvelope.create(
                responsibility="framework",
                failure_stage="planner_startup",
                failure_code="planner_capability_context_empty",
                run_id=cost_ledger.run_id,
            )
            system_role_probe_audit.terminate(failure)
            return _pipeline_status_from_terminal_failure(failure)
    planner_capability_context_sha256 = canonical_sha256(
        [card.model_dump(mode="json") for card in planner_capability_cards]
    )
    _append_jsonl(
        trace_path,
        {
            "event_type": "planner_capability_context",
            "stage": "planner_startup",
            "planner_variant": planner_variant,
            "card_count": len(planner_capability_cards),
            "capability_context_sha256": planner_capability_context_sha256,
            "candidate_pool_effect": "abstract_role_context_only",
        },
    )
    try:
        resource_definitions = _build_resource_definitions(resource_index)
    except RetrievalRuntimeError as exc:
        failure = TerminalFailureEnvelope.create(
            responsibility="framework",
            failure_stage="resource_runtime_startup",
            failure_code="resource_definition_index_identity_mismatch",
            exception=exc,
            run_id=cost_ledger.run_id,
        )
        system_role_probe_audit.terminate(failure)
        return _pipeline_status_from_terminal_failure(failure)
    evaluator_manifest = None
    evaluator_definition = None
    resolved_evaluator_model = None
    if evaluation_mode != "off":
        assert evaluator_policy is not None
        evaluator_manifest = control_index.get(evaluator_policy.model_resource_id)
        if not isinstance(evaluator_manifest, dict):
            raise EvaluationRuntimeError("evaluator_model_not_in_control_catalog")
        evaluator_definition = control_definitions.get(evaluator_policy.model_resource_id)
        if evaluator_definition is None:
            raise EvaluationRuntimeError("evaluator_resource_definition_missing")
        evaluator_response_mode = _plan_compiler_response_mode(
            evaluator_manifest,
            configured_mode=llm_settings.get("evaluator_response_mode"),
        )
        resolved_evaluator_model = resolve_evaluator_model(
            policy=evaluator_policy,
            pricing_catalog=cost_ledger.catalog,
            manifest=evaluator_manifest,
            availability_status=evaluator_definition.status,
            response_mode=evaluator_response_mode,
        )
    strict_plan_only = recovery_policy.sealed_runtime_mode == "strict_plan_only"
    full_generation_manifest = None
    full_generation_definition = None
    full_generation_response_mode = None
    system_full_generation_policy = None
    if not strict_plan_only:
        full_generation_manifest = control_index.get(
            recovery_policy.full_generation_model_resource_id
        )
        if not isinstance(full_generation_manifest, dict):
            raise RecoveryControlError("full_generation_model_not_in_control_catalog")
        full_generation_definition = control_definitions.get(
            recovery_policy.full_generation_model_resource_id
        )
        if full_generation_definition is None:
            raise RecoveryControlError("full_generation_resource_definition_missing")
        full_generation_response_mode = _plan_compiler_response_mode(
            full_generation_manifest,
            configured_mode=llm_settings.get("full_generation_response_mode"),
        )
        system_full_generation_policy = resolve_system_full_generation_policy(
            recovery_policy=recovery_policy,
            pricing_catalog=cost_ledger.catalog,
            manifest=full_generation_manifest,
            response_mode=full_generation_response_mode,
            temperature=float(llm_settings.get("execution_temperature", 0.5)),
            max_tokens=int(llm_settings.get("execution_max_tokens", 8192)),
            allow_streaming=bool(llm_settings.get("execution_allow_streaming", True)),
            prompt_version=FULL_GENERATION_PROMPT_VERSION,
            prompt_sha256=FULL_GENERATION_PROMPT_SHA256,
            availability_status=full_generation_definition.status,
        )
    gen_models = [
        manifest.model_dump()
        for manifest in library
        if manifest.type == ManifestType.MODEL and manifest.id in fallback_ids
    ]
    router = SGARRouter(
        confidence_threshold=0.75,
        # Retrieval confidence is evidence-only in formal runtime v1.
        granularity_threshold=0.0,
        bundle_advantage_threshold=llm_settings.get("bundle_advantage_threshold", 1.0),
        # The formal Router is a deterministic control plane.  Keeping the
        # legacy policy transport absent makes accidental model-policy entry
        # fail before any provider request.
        policy_api_key="",
        policy_base_url=base_url,
        policy_model=llm_settings.get("router_policy_model", model),
        policy_model_chain=control_model_chain,
        policy_response_modes={},
        baseline_model_id=llm_settings.get("full_generation_baseline_model", model),
        resource_index=resource_index,
        execute_low_advantage_on_exhaustion=llm_settings.get(
            "execute_low_advantage_on_exhaustion", True
        ),
        # Formal frozen sessions never enter legacy candidate completion.  Keep
        # the constructor flag false as an additional static/runtime barrier.
        enable_intelligent_resource_completion=False,
        supplemental_model_ids=[],
        max_supplemental_models=0,
        cost_ledger=cost_ledger,
        policy_transport=None,
    )
    compiler_invocation_policy = control_role_policy.for_role("plan_compiler")
    adaptation_invocation_policy = control_role_policy.for_role("plan_adaptation")
    compiler_target_price = cost_ledger.catalog.resolve(
        model_ref=compiler_invocation_policy.resource_id
    )
    if (
        compiler_target_price.resource_id != compiler_invocation_policy.resource_id
        or compiler_target_price.api_model_id != compiler_invocation_policy.api_model_id
    ):
        raise ModelResponseContractError("control_role_policy_catalog_identity_mismatch")
    compiler_target_manifest = control_index.get(compiler_target_price.resource_id)
    if not isinstance(compiler_target_manifest, dict):
        failure = TerminalFailureEnvelope.create(
            responsibility="framework",
            failure_stage="plan_compiler_startup",
            failure_code="plan_compiler_model_not_in_control_catalog",
            run_id=cost_ledger.run_id,
        )
        system_role_probe_audit.terminate(failure)
        return _pipeline_status_from_terminal_failure(failure)
    compiler_targets: list[dict[str, Any]] = [
        {
            "resource_id": compiler_target_price.resource_id,
            "api_model_id": compiler_target_price.api_model_id,
            "manifest": compiler_target_manifest,
        }
    ]
    required_role_models = []
    if resolved_evaluator_model is not None:
        required_role_models.append(
            (
                "evaluator",
                resolved_evaluator_model.resource_id,
                resolved_evaluator_model.api_model_id,
            )
        )
    if system_full_generation_policy is not None:
        raise RecoveryControlError("sealed_release_forbids_full_generation")
    for compiler_target in compiler_targets:
        required_role_models.extend(
            (
                (
                    "plan_compiler",
                    compiler_target["resource_id"],
                    compiler_target["api_model_id"],
                ),
                (
                    "plan_adaptation",
                    compiler_target["resource_id"],
                    compiler_target["api_model_id"],
                ),
            )
        )
    verified_role_modes: dict[str, str] = {}
    verified_role_identity_modes: dict[tuple[str, str, str], str] = {}
    for role, resource_id, api_model_id in required_role_models:
        expected_policy = control_role_policy.for_role(role)
        record = provider_probe_records[role]
        if (
            record["model_resource_id"] != resource_id
            or record["api_model_id"] != api_model_id
        ):
            raise RuntimeError(f"control_{role}_probe_resource_identity_mismatch")
        if record["reasoning_effort"] != expected_policy.reasoning_effort:
            raise RuntimeError(f"control_{role}_probe_reasoning_effort_mismatch")
        if record.get("temperature") != expected_policy.temperature:
            raise RuntimeError(f"control_{role}_probe_temperature_mismatch")
        verified_role_modes.setdefault(role, "native_strict_schema")
        verified_role_identity_modes[(role, resource_id, api_model_id)] = (
            "native_strict_schema"
        )
        system_role_probe_audit.select_model(
            role=role,
            resource_id=resource_id,
            model_id=api_model_id,
            response_mode="native_strict_schema",
        )
    if evaluation_mode != "off":
        assert evaluator_policy is not None
        assert evaluator_manifest is not None
        assert evaluator_definition is not None
        evaluator_response_mode = verified_role_modes["evaluator"]
        resolved_evaluator_model = resolve_evaluator_model(
            policy=evaluator_policy,
            pricing_catalog=cost_ledger.catalog,
            manifest=evaluator_manifest,
            availability_status=evaluator_definition.status,
            response_mode=evaluator_response_mode,
        )
    primary_compiler_target = compiler_targets[0]
    plan_response_mode = verified_role_identity_modes[
        (
            "plan_compiler",
            primary_compiler_target["resource_id"],
            primary_compiler_target["api_model_id"],
        )
    ]
    system_role_probe_audit.mark_verified()
    compiler_store = PlanCompilationStore(
        Path(output_dir),
        run_id=cost_ledger.run_id,
    )
    executable_plan_compiler = ExecutablePlanCompiler(
        transport=model_transport_bundle.sync,
        cost_ledger=cost_ledger,
        compiler_model_resource_id=primary_compiler_target["resource_id"],
        compiler_model_api_id=primary_compiler_target["api_model_id"],
        store=compiler_store,
        response_mode=verified_role_identity_modes[
            (
                "plan_compiler",
                primary_compiler_target["resource_id"],
                primary_compiler_target["api_model_id"],
            )
        ],
        adaptation_response_mode=verified_role_identity_modes[
            (
                "plan_adaptation",
                primary_compiler_target["resource_id"],
                primary_compiler_target["api_model_id"],
            )
        ],
        control_role_policy=control_role_policy,
        capability_probe_service=capability_probe_service,
        candidate_compact_quotas=retrieval_policy.compact_quotas(),
        candidate_compact_total_max=retrieval_policy.compact_total_max,
    )
    full_generation_executor = (
        FullGenerationExecutor(
            transport=model_transport_bundle.sync,
            cost_ledger=cost_ledger,
            system_policy=system_full_generation_policy,
        )
        if system_full_generation_policy is not None
        else None
    )
    evaluation_coordinator = (
        EvaluationCoordinator(
            transport=model_transport_bundle.async_port,
            resolved_model=resolved_evaluator_model,
            policy=evaluator_policy,
            cost_ledger=cost_ledger,
            event_ledger=evaluation_ledger,
        )
        if evaluation_mode != "off"
        else StaticEvaluationCoordinator(
            mode="off",
            event_ledger=evaluation_ledger,
        )
    )
    static_evaluation_coordinator = StaticEvaluationCoordinator(
        mode="off",
        event_ledger=evaluation_ledger,
    )
    artifact_lifecycle_coordinator = ArtifactLifecycleCoordinator(
        artifact_store=artifact_store,
        context_store=context_commit_store,
        evaluation_coordinator=evaluation_coordinator,
        evaluation_mode=evaluation_mode,
        static_evaluation_coordinator=static_evaluation_coordinator,
    )
    plan_runtime_capabilities = _plan_runtime_capabilities(
        resource_index,
        runtime_image=runtime_image,
    )
    _append_jsonl(
        trace_path,
        {
            "event_type": "plan_compiler_runtime_identity",
            "stage": "main_startup",
            "compiler_model_resource_id": primary_compiler_target["resource_id"],
            "compiler_model_api_id": primary_compiler_target["api_model_id"],
            "response_mode": plan_response_mode,
            "control_role_policy_sha256": control_role_policy.policy_sha256,
            "compiler_role_policy_sha256": (
                compiler_invocation_policy.role_policy_sha256
            ),
            "adaptation_role_policy_sha256": (
                adaptation_invocation_policy.role_policy_sha256
            ),
            "reasoning_effort": compiler_invocation_policy.reasoning_effort,
            "temperature": compiler_invocation_policy.temperature,
            "allow_model_failover": False,
            "verified_compiler_model_chain": [
                {
                    "resource_id": item["resource_id"],
                    "api_model_id": item["api_model_id"],
                    "plan_compiler_response_mode": verified_role_identity_modes[
                        ("plan_compiler", item["resource_id"], item["api_model_id"])
                    ],
                    "plan_adaptation_response_mode": verified_role_identity_modes[
                        ("plan_adaptation", item["resource_id"], item["api_model_id"])
                    ],
                }
                for item in compiler_targets
            ],
            "pricing_catalog_sha256": cost_ledger.catalog.pricing_catalog_sha256,
            "runtime_capabilities_sha256": (
                plan_runtime_capabilities.capabilities_sha256
            ),
            "recovery_policy_sha256": recovery_policy.policy_sha256,
            "sealed_runtime_mode": recovery_policy.sealed_runtime_mode,
            "full_generation_policy_sha256": (
                system_full_generation_policy.policy_sha256
                if system_full_generation_policy is not None
                else None
            ),
            "full_generation_model_resource_id": (
                system_full_generation_policy.resource_id
                if system_full_generation_policy is not None
                else None
            ),
            "full_generation_model_api_id": (
                system_full_generation_policy.api_model_id
                if system_full_generation_policy is not None
                else None
            ),
            "evaluation_mode": evaluation_mode,
            "evaluator_policy_sha256": (
                evaluator_policy.policy_sha256 if evaluator_policy is not None else None
            ),
            "evaluator_model_resource_id": (
                resolved_evaluator_model.resource_id if resolved_evaluator_model else None
            ),
            "evaluator_model_api_id": (
                resolved_evaluator_model.api_model_id if resolved_evaluator_model else None
            ),
            "evaluator_response_mode": (
                resolved_evaluator_model.response_mode if resolved_evaluator_model else None
            ),
            "evaluator_identity_sha256": (
                resolved_evaluator_model.identity_sha256 if resolved_evaluator_model else None
            ),
        },
    )

    while replan_count <= MAX_PLANNER_REPLANS:
        if replan_count > 0:
            logger.warning(f"[Safety Hook] Initiating Tier-3 Graph-Level Replan ({replan_count}/{MAX_PLANNER_REPLANS})...")

        # ── Phase 1: Planner ───────────────────────
        logger.info("-" * 60)
        logger.info("Phase 1: Task Decomposition (Planner)")
        logger.info("-" * 60)
        
        planner_query = (
            task_invocation.invocation.planner_request_text()
            if task_invocation is not None
            else user_query
        )
        try:
            planner, planner_output, planner_control_attempts = (
                _decompose_with_control_models(
                    llm_key=llm_key,
                    base_url=base_url,
                    control_models=control_model_chain,
                    failover_enabled=False,
                    budget_manager=budget_manager,
                    cost_ledger=cost_ledger,
                    user_query=planner_query,
                    completed_artifacts=(
                        completed_artifacts if replan_count > 0 else None
                    ),
                    original_contracts=(
                        original_contracts if replan_count > 0 else None
                    ),
                    capability_cards=planner_capability_cards or None,
                    sync_model_transport=model_transport_bundle.sync,
                    response_modes=verified_control_modes,
                    # The formal Planner owns its sealed 32K -> 64K-on-length
                    # protocol. A legacy local config value must not widen or
                    # otherwise alter the first production request.
                    planner_max_output_tokens=DEFAULT_PLANNER_MAX_OUTPUT_TOKENS,
                    planner_role_policy=planner_role_policy,
                    planner_attempt_evidence_path=os.path.join(
                        output_dir,
                        "planner_attempts.jsonl",
                    ),
                )
            )
        except (asyncio.CancelledError, KeyboardInterrupt):
            raise
        except Exception as exc:
            failure = _planner_generation_failure(
                exc,
                run_id=cost_ledger.run_id,
            )
            return _pipeline_status_from_terminal_failure(failure)
        if replan_count > 0:
            planner_output = preserve_replan_contracts(
                planner_output,
                original_contracts,
                completed_artifacts,
            )
        planner_output = _bind_authoritative_final_schema(
            planner_output,
            task_invocation,
        )
        planner_output = _bind_task_text_authority(
            planner_output,
            task_invocation,
        )
        if replan_count == 0:
            original_contracts = _collect_protected_contracts(planner_output)
        replan_history.append(
            {
                "replan_count": replan_count,
                "planner_parse_metadata": getattr(planner, "last_parse_metadata", {}),
                "planner_contract_audit": getattr(planner, "last_contract_audit", {}),
                "planner_control_model_attempts": planner_control_attempts,
                "planner_variant": planner_variant,
                "planner_capability_context_sha256": planner_capability_context_sha256,
                "planner_capability_resource_pool_sha256": (
                    planner_capability_context_sha256
                ),
                "subtasks": [
                    {
                        "id": subtask.id,
                        "artifact_type": subtask.artifact_type.value,
                        "output_extension": subtask.output_extension,
                        "task_stage": subtask.task_stage.value if subtask.task_stage is not None else None,
                        "planning_execution_mode": (
                            subtask.planning_execution_mode.value
                            if subtask.planning_execution_mode is not None
                            else None
                        ),
                        "capability_evidence": list(subtask.capability_evidence),
                        "capability_gap": subtask.capability_gap,
                        "depends_on": list(subtask.depends_on),
                    }
                    for subtask in planner_output.subtasks
                ],
                "dag_edge_contract_sha256s": [
                    edge.edge_contract_sha256
                    for edge in planner_output.edge_contracts
                ],
                "dag_edge_contracts_sha256": canonical_sha256(
                    [
                        edge.model_dump(mode="json")
                        for edge in planner_output.edge_contracts
                    ]
                ),
                "protected_contracts": list(original_contracts.keys()),
            }
        )
        _append_jsonl(
            trace_path,
            {
                "event_type": "planner_trace",
                "replan_count": replan_count,
                "query_sha256": canonical_sha256(user_query),
                "query_utf8_bytes": len(user_query.encode("utf-8")),
                "planner_parse_metadata": getattr(planner, "last_parse_metadata", {}),
                "planner_contract_audit": getattr(planner, "last_contract_audit", {}),
                "planner_control_model_attempts": planner_control_attempts,
                "subtasks": [subtask.model_dump(mode="json") for subtask in planner_output.subtasks],
                "dag_edge_contracts": [
                    edge.model_dump(mode="json")
                    for edge in planner_output.edge_contracts
                ],
            },
        )


        # ── Phase 2: Router Adjudication ───────────
        logger.info("-" * 60)
        logger.info("Phase 2: Router Adjudication")
        logger.info("-" * 60)

        while True:
            decisions: list[RoutingDecision] = []
            task_list: list[dict] = []
            routing_bundles: dict[str, dict] = {
                "_original_query": user_query,
                "_task_invocation": (
                    task_invocation.invocation.model_dump(mode="json")
                    if task_invocation is not None
                    else None
                ),
                "_query_diagnostics": query_diagnostics or {},
                "_replan_history": list(replan_history),
                "_environment_profile": environment_profile.public_projection(),
                "_control_model_chain": control_selector.public_projection(
                    project_root=PROJECT_ROOT
                ),
                "_planner_parse_metadata": getattr(planner, "last_parse_metadata", {}),
                "_planner_parse_history": list(getattr(planner, "parse_metadata_history", [])),
                "_model_cost_summary": cost_ledger.summary(),
                "_execution_summary": execution_ledger.summary(),
                "_recovery_summary": recovery_ledger.summary(),
                "_evaluation_summary": evaluation_ledger.summary(),
                "_artifact_summary": artifact_store.ledger.artifact_summary(),
                "_context_summary": artifact_store.ledger.context_summary(),
                "_retrieval_runtime_identity": retrieval_identity.model_dump(mode="json"),
                "_recovery_runtime_identity": {
                    "recovery_policy_sha256": recovery_policy.policy_sha256,
                    "sealed_runtime_mode": recovery_policy.sealed_runtime_mode,
                    "full_generation_policy_sha256": (
                        system_full_generation_policy.policy_sha256
                        if system_full_generation_policy is not None
                        else None
                    ),
                    "full_generation_model_resource_id": (
                        system_full_generation_policy.resource_id
                        if system_full_generation_policy is not None
                        else None
                    ),
                    "full_generation_model_api_id": (
                        system_full_generation_policy.api_model_id
                        if system_full_generation_policy is not None
                        else None
                    ),
                },
                "_dag_edge_contracts": [
                    edge.model_dump(mode="json")
                    for edge in planner_output.edge_contracts
                ],
                "_dag_edge_contracts_sha256": canonical_sha256(
                    [
                        edge.model_dump(mode="json")
                        for edge in planner_output.edge_contracts
                    ]
                ),
            }

            for subtask in planner_output.subtasks:
                revision = SubtaskRevisionRef(
                    graph_revision=replan_count,
                    subtask_id=subtask.id,
                    subtask_revision=0,
                )
                public_context = _portable_public_context_for_subtask(
                    subtask,
                    task_invocation,
                )
                contract_projection = project_retrieval_contract(
                    revision,
                    subtask,
                    public_context=public_context,
                )
                _append_jsonl(
                    trace_path,
                    {
                        "event_type": "retrieval_started",
                        "stage": "candidate_pool_preparation",
                        "revision": revision.model_dump(mode="json"),
                        "contract_sha256": contract_projection.contract_sha256,
                        "retrieval_runtime_identity_sha256": (
                            retrieval_identity.identity_sha256
                        ),
                    },
                )
                try:
                    frozen_result = retrieval_coordinator.prepare_candidate_pool(
                        revision,
                        subtask,
                        retrieval_identity,
                        library,
                        resource_index,
                        cost_ledger,
                        public_context=public_context,
                    )
                except RetrievalPreparationError as exc:
                    for attempt in exc.attempts:
                        _append_jsonl(
                            trace_path,
                            {
                                "event_type": "retrieval_attempt",
                                "stage": "candidate_pool_preparation",
                                "revision": revision.model_dump(mode="json"),
                                "attempt": attempt.model_dump(mode="json"),
                            },
                        )
                    _append_jsonl(
                        trace_path,
                        {
                            "event_type": "retrieval_terminal",
                            "stage": "candidate_pool_preparation",
                            "revision": revision.model_dump(mode="json"),
                            "contract_sha256": contract_projection.contract_sha256,
                            "failure_code": exc.error_code,
                            "failure_responsibility": exc.failure_responsibility,
                            "response_received": exc.response_received,
                            "exception_type": exc.exception_type,
                            "message_sha256": exc.message_sha256,
                        },
                    )
                    routing_bundles[subtask.id] = {
                        "retrieval_terminal_failure": {
                            "failure_code": exc.error_code,
                            "failure_responsibility": exc.failure_responsibility,
                            "response_received": exc.response_received,
                            "exception_type": exc.exception_type,
                            "message_sha256": exc.message_sha256,
                        }
                    }
                    routing_bundles["_model_cost_summary"] = cost_ledger.summary()
                    generate_report(
                        public_query_reference,
                        planner_output,
                        decisions,
                        output_path=report_path,
                        routing_bundles=routing_bundles,
                    )
                    logger.error(
                        "[Retrieval] Terminal candidate-pool failure for {}: code={} responsibility={}",
                        subtask.id,
                        exc.error_code,
                        exc.failure_responsibility,
                    )
                    return _structured_pipeline_failure(
                        responsibility=exc.failure_responsibility,
                        failure_stage="retrieval",
                        failure_code=exc.error_code,
                        exception_type=exc.exception_type,
                        message_sha256=exc.message_sha256,
                        response_received=exc.response_received,
                    )

                candidate_pool_artifact = _record_frozen_retrieval(
                    trace_path=trace_path,
                    output_dir=output_dir,
                    run_id=cost_ledger.run_id,
                    frozen_result=frozen_result,
                )
                session = router.start_frozen_session(subtask, frozen_result, library)

                # Preserve the complete admitted node, including optional semantics.
                task_list.append({
                    **subtask.model_dump(mode="json"),
                    "original_query": user_query,
                })

                # Compatibility-only report projection.  This is one candidate,
                # not the resource selected by the Plan Compiler.
                top_ref = (
                    session.top_k_resources[0]
                    if session.top_k_resources
                    else session.frozen_candidate_resources[0]
                )
                top_manifest = next(m for m in library if m.id == top_ref.resource_id)
                legacy_decision = RoutingDecision(
                    mode=ExecutionMode.SEMI_GENERATIVE,
                    resource=top_manifest,
                    metrics=RoutingMetrics(
                        similarity=session.top_k_scores.get(top_ref.resource_id, 0.0),
                        advantage=top_manifest.advantage_score,
                    ),
                )
                decisions.append(legacy_decision)
                routing_bundles[subtask.id] = {
                    "execution_mode": ExecutionMode.SEMI_GENERATIVE.value,
                    "kwargs": {"model": model, "temperature": 0.5},
                    "fallback_models": gen_models,
                    "routing_session": session,
                    "router_runtime": router,
                    "library": library,
                    "resource_index": resource_index,
                    "original_query": user_query,
                    "frozen_candidate_pool": frozen_result,
                    "retrieval_coordinator": retrieval_coordinator,
                    "executable_plan_compiler": executable_plan_compiler,
                    "resource_definitions": {
                        candidate.resource_id: resource_definitions[
                            candidate.resource_id
                        ]
                        for candidate in frozen_result.candidate_pool_snapshot.candidates
                    },
                    "model_pricing_catalog": cost_ledger.catalog,
                    "plan_runtime_capabilities": plan_runtime_capabilities,
                    "recovery_policy": recovery_policy,
                    "recovery_ledger": recovery_ledger,
                    "full_generation_executor": full_generation_executor,
                    "candidate_pool_artifact": candidate_pool_artifact,
                }
                _append_jsonl(
                    trace_path,
                    {
                        "event_type": "routing_trace",
                        "subtask_id": subtask.id,
                        "revision": revision.model_dump(mode="json"),
                        "candidate_pool_sha256": (
                            frozen_result.candidate_pool_snapshot.candidate_pool_sha256
                        ),
                        "session": session.model_dump(mode="json"),
                    },
                )

            break

        routing_bundles["_model_cost_summary"] = cost_ledger.summary()
        routing_bundles["_execution_summary"] = execution_ledger.summary()
        routing_bundles["_recovery_summary"] = recovery_ledger.summary()

        # ── Generate Visual Report ─────────────────
        generate_report(
            public_query_reference,
            planner_output,
            decisions,
            output_path=report_path,
            routing_bundles=routing_bundles,
        )

        # ── Phase 3: DAG Execution ─────────────────
        logger.info("-" * 60)
        logger.info("Phase 3: DAG Execution")
        logger.info("-" * 60)

        orchestrator = DAGOrchestrator(
            llm_api_key=llm_key,
            llm_base_url=base_url,
            model=model,
            budget_manager=budget_manager,
            cost_ledger=cost_ledger,
            execution_ledger=execution_ledger,
            artifact_dir=output_dir,
            max_same_bundle_repair_attempts=llm_settings.get(
                "max_same_bundle_repair_attempts", 0
            ),
            allow_plan_recovery=llm_settings.get("allow_plan_recovery", False),
            # Stage 4A performs one evaluator handoff only.  Evaluator retry and
            # inconclusive review belong to Stage 4B.
            max_eval_retries=0,
            eval_profile_threshold_chars=llm_settings.get(
                "eval_profile_threshold_chars", 12000
            ),
            execution_strictness=llm_settings.get("execution_strictness", "balanced"),
            trace_path=trace_path,
            control_model_chain=control_model_chain,
            control_model_metadata=control_selector.public_projection(
                project_root=PROJECT_ROOT
            ),
            environment_profile=environment_profile,
            execution_max_retries=llm_settings.get("execution_max_retries", 3),
            execution_max_tokens=llm_settings.get("execution_max_tokens", 8192),
            execution_allow_streaming=llm_settings.get("execution_allow_streaming", True),
            runtime_preparation_enabled=llm_settings.get(
                "runtime_preparation_enabled", False
            ),
            runtime_preparation_trace_path=llm_settings.get(
                "runtime_preparation_trace_path"
            ),
            runtime_preparation_run_id=llm_settings.get(
                "runtime_preparation_run_id"
            ),
            artifact_lifecycle_coordinator=artifact_lifecycle_coordinator,
            artifact_store=artifact_store,
            context_commit_store=context_commit_store,
            # External benchmark substrates own the task filesystem.  Never
            # infer host files from free-form benchmark instructions there;
            # task-state paths must remain runtime (/app) paths and cross the
            # RPC boundary only through typed bindings/handles.
            explicit_input_only=(
                task_invocation is not None or execution_substrate is not None
            ),
            network_policy_mode=network_policy_mode,
            task_invocation=(
                task_invocation.invocation if task_invocation is not None else None
            ),
            async_model_transport=model_transport_bundle.async_port,
            execution_substrate=execution_substrate,
            execution_substrate_mode=execution_substrate_mode,
            evaluation_mode=evaluation_mode,
        )
        if task_invocation is not None:
            orchestrator.register_input_handles(task_invocation.internal_handles())
        # Inject recovered contextual artifacts before executing
        for k, v in completed_artifacts.items():
            orchestrator.context.add_result(k, v)

        try:
            final_ctx = await orchestrator.run_pipeline(task_list, routing_bundles)
            for task_id, bundle in routing_bundles.items():
                if not isinstance(bundle, dict) or bundle.get("routing_session") is None:
                    continue
                _append_jsonl(
                    trace_path,
                    {
                        "event_type": "routing_trace",
                        "stage": "final",
                        "subtask_id": task_id,
                        "session": bundle["routing_session"].model_dump(mode="json"),
                    },
                )

            routing_bundles["_model_cost_summary"] = cost_ledger.summary()
            routing_bundles["_execution_summary"] = execution_ledger.summary()
            routing_bundles["_recovery_summary"] = recovery_ledger.summary()
            routing_bundles["_evaluation_summary"] = evaluation_ledger.summary()
            routing_bundles["_artifact_summary"] = artifact_store.ledger.artifact_summary()
            routing_bundles["_context_summary"] = artifact_store.ledger.context_summary()

            # ── Phase 4: Delivery ──────────────────
            logger.info("-" * 60)
            logger.info("Phase 4: Final Delivery")
            logger.info("-" * 60)

            try:
                delivery = extract_deliverables(
                    final_ctx,
                    task_list,
                    output_dir=output_dir,
                    final_deliverable_contract=(
                        task_invocation.invocation.final_deliverable_contract
                        if task_invocation is not None
                        else None
                    ),
                )
            except Exception as exc:
                raise NodeUnrecoverableError(
                    TerminalFailureEnvelope.create(
                        responsibility="framework",
                        failure_stage="delivery",
                        failure_code="delivery_publication_failed",
                        exception=exc,
                        run_id=cost_ledger.run_id,
                    )
                ) from exc
            if delivery is not None:
                publication = delivery.publication
                logger.success(
                    "  final_deliverable → {} ({} bytes, sha256={})",
                    publication.logical_locator,
                    publication.byte_size,
                    publication.content_sha256,
                )
                logger.success(
                    "  delivery_manifest → {}",
                    publication.delivery_manifest_locator,
                )

            if task_list and delivery is None and require_final_delivery:
                raise NodeUnrecoverableError(
                    TerminalFailureEnvelope.create(
                        responsibility="framework",
                        failure_stage="delivery",
                        failure_code="final_delivery_requires_committed_final_artifact",
                        run_id=cost_ledger.run_id,
                    )
                )

            generate_report(
                public_query_reference,
                planner_output,
                decisions,
                output_path=report_path,
                routing_bundles=routing_bundles,
            )
            
            # Entire pipeline success, break out of replan loop
            pipeline_status = _successful_pipeline_status(routing_bundles)
            break

        except NodeUnrecoverableError as e:
            logger.error(
                "[Pipeline] Structured node failure: {}",
                type(e).__name__,
            )
            generate_report(
                public_query_reference,
                planner_output,
                decisions,
                output_path=report_path,
                routing_bundles=routing_bundles,
            )
            # Preserve diagnostics, but never turn a post-freeze execution
            # failure into another retrieval/Planner pass.  The candidate pool
            # is immutable for this Subtask revision.
            completed_artifacts.update(orchestrator.context.artifacts)
            logger.error(
                "[Candidate Freeze] Execution failed after candidate freeze; "
                "post-freeze retrieval and graph replan are forbidden for this revision."
            )
            pipeline_status = PipelineTerminalStatus(
                "structured_failure",
                primary_failure=e.primary_failure,
                terminal_failure=e.terminal_failure,
                recovery_outcomes=e.recovery_outcomes,
                causal_chain=e.causal_chain,
            )
            break
        except Exception as e:
            logger.error(
                "[Framework] Unhandled pipeline exception: {}",
                type(e).__name__,
            )
            generate_report(
                public_query_reference,
                planner_output,
                decisions,
                output_path=report_path,
                routing_bundles=routing_bundles,
            )
            raise


# ─────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────
    return pipeline_status


def _configured_pricing_refs(
    llm_settings: dict,
    *,
    retrieval_policy_path: str | Path | None = None,
) -> list[str]:
    """Collect exact configured model IDs without fuzzy or legacy-tag matching."""

    refs: list[str] = []

    def add(value) -> None:
        values = value if isinstance(value, (list, tuple)) else [value]
        for item in values:
            text = str(item or "").strip()
            if text and text not in refs:
                refs.append(text)

    configured_model = llm_settings.get("model", DEFAULT_SYSTEM_MODEL_CHAIN[0])
    add(configured_model)
    add(llm_settings.get("system_model_chain", []))
    add(llm_settings.get("full_generation_baseline_model", configured_model))
    add(llm_settings.get("supplemental_model_ids", []))
    for key in (
        "planner_model",
        "fallback_model",
        "context_compression_model",
    ):
        add(llm_settings.get(key))
    add(load_retrieval_policy(retrieval_policy_path).hyde.api_model_id)
    return refs


@bound_pipeline
async def run_pipeline(
    config: dict,
    user_query: str,
    output_dir: str,
    report_path: str,
    query_diagnostics: dict | None = None,
    task_invocation: PreparedTaskInvocation | None = None,
    network_policy_mode: str = "disabled",
    run_id: str | None = None,
    planner_variant: str = "resource_aware",
    runtime_authority: str = "git",
    *,
    execution_substrate: object | None = None,
    execution_substrate_mode: str = "default",
    max_generation_requests: int | None = None,
    max_embedding_requests: int | None = None,
    require_final_delivery: bool = True,
    method_deadline_monotonic: float | None = None,
) -> str:
    """Initialize accounting before paid work and finalize it on every exit."""

    prepare_retrieval_environment(runtime_authority)
    llm_settings = dict(config.get("llm_settings", {}) or {})
    evaluation_mode = normalize_evaluation_mode(
        llm_settings.get("evaluation_mode")
    )
    retrieval_policy_path = _runtime_policy_path(
        config,
        "retrieval_policy_path",
        "sgar_mvp/config/retrieval_policy.json",
    )
    evaluator_policy_path = _runtime_policy_path(
        config,
        "evaluator_policy_path",
        "sgar_mvp/config/evaluator_policy.json",
    )
    recovery_policy = load_recovery_policy(
        os.path.join(SCRIPT_DIR, "config", "recovery_policy.json")
    )
    evaluator_policy = (
        load_evaluator_policy(evaluator_policy_path)
        if evaluation_mode != "off"
        else None
    )
    required_model_refs = _configured_pricing_refs(
        llm_settings,
        retrieval_policy_path=retrieval_policy_path,
    )
    required_model_refs.append(recovery_policy.full_generation_model_resource_id)
    if evaluator_policy is not None:
        required_model_refs.append(evaluator_policy.model_resource_id)
    catalog = ModelPricingCatalog.from_manifest_file(
        os.path.join(PROJECT_ROOT, "Pool", "resources", "json", "combine.json"),
        required_model_refs=list(dict.fromkeys(required_model_refs)),
    )
    policy = load_model_cost_policy(
        os.path.join(SCRIPT_DIR, "config", "model_cost_policy.json"),
        local_cost_control=llm_settings.get("cost_control"),
    )
    cost_ledger = RunCostLedger(
        catalog=catalog,
        policy=policy,
        output_dir=output_dir,
        run_id=run_id,
        max_generation_requests=max_generation_requests,
    )
    try:
        execution_ledger = RunExecutionLedger(
            output_dir=output_dir,
            run_id=cost_ledger.run_id,
        )
    except Exception:
        cost_ledger.close()
        raise
    try:
        recovery_ledger = RecoveryEventLedger(
            output_dir=output_dir,
            run_id=cost_ledger.run_id,
        )
    except Exception:
        execution_ledger.close()
        cost_ledger.close()
        raise
    try:
        evaluation_ledger = EvaluationEventLedger(
            output_dir=output_dir,
            run_id=cost_ledger.run_id,
        )
        artifact_store = ArtifactLifecycleStore(
            output_dir=output_dir,
            run_id=cost_ledger.run_id,
        )
        context_commit_store = ContextCommitStore(artifact_store=artifact_store)
        system_role_probe_audit = SystemRoleProbeAuditStore(
            output_dir,
            run_id=cost_ledger.run_id,
        )
    except Exception:
        recovery_ledger.close()
        execution_ledger.close()
        cost_ledger.close()
        raise
    try:
        request_budget = ModelRequestBudget(
            deadline_monotonic=method_deadline_monotonic,
        )
        _atomic_write_json(
            os.path.join(output_dir, "model_request_budget.json"), request_budget.record(),
        )
        with model_request_budget(request_budget), embedding_request_budget(max_embedding_requests) as embedding_budget:
            try:
                result = await _run_pipeline_with_cost_ledger(
                    config,
                    user_query,
                    output_dir,
                    report_path,
                    cost_ledger,
                    execution_ledger,
                    recovery_policy,
                    recovery_ledger,
                    evaluator_policy,
                    evaluation_ledger,
                    artifact_store,
                    context_commit_store,
                    system_role_probe_audit=system_role_probe_audit,
                    query_diagnostics=query_diagnostics,
                    task_invocation=task_invocation,
                    network_policy_mode=network_policy_mode,
                    planner_variant=planner_variant,
                    runtime_authority=runtime_authority,
                    execution_substrate=execution_substrate,
                    execution_substrate_mode=execution_substrate_mode,
                    require_final_delivery=require_final_delivery,
                )
            finally:
                _atomic_write_json(
                    os.path.join(output_dir, "embedding_summary.json"),
                    embedding_budget.summary(),
                )
        if system_role_probe_audit.status == "in_progress":
            terminal = getattr(result, "failure", None)
            if not isinstance(terminal, TerminalFailureEnvelope):
                terminal = TerminalFailureEnvelope.create(
                    responsibility="framework",
                    failure_stage="system_role_schema_probe",
                    failure_code="system_role_schema_probe_audit_incomplete",
                    run_id=cost_ledger.run_id,
                )
                result = _pipeline_status_from_terminal_failure(terminal)
            system_role_probe_audit.terminate(terminal)
        return result
    except BudgetControlError as exc:
        failure = TerminalFailureEnvelope.create(
            responsibility="budget",
            failure_stage="budget_control",
            failure_code=str(getattr(exc, "error_code", "model_cost_limit_reached")),
            exception=exc,
            run_id=cost_ledger.run_id,
        )
        system_role_probe_audit.terminate(failure)
        return _pipeline_status_from_terminal_failure(failure)
    except ModelAccountingError as exc:
        failure = TerminalFailureEnvelope.create(
            responsibility="framework",
            failure_stage="model_accounting",
            failure_code=str(getattr(exc, "error_code", "model_accounting_failure")),
            exception=exc,
            run_id=cost_ledger.run_id,
        )
        system_role_probe_audit.terminate(failure)
        return _pipeline_status_from_terminal_failure(failure)
    except (ModelTransportCapabilityError, ModelResponseContractError) as exc:
        failure = TerminalFailureEnvelope.create(
            responsibility="framework",
            failure_stage="system_role_schema_probe",
            failure_code=str(
                getattr(exc, "error_code", "system_role_schema_probe_contract_invalid")
            ),
            exception=exc,
            run_id=cost_ledger.run_id,
        )
        system_role_probe_audit.terminate(failure)
        return _pipeline_status_from_terminal_failure(failure)
    except (asyncio.CancelledError, KeyboardInterrupt) as exc:
        failure = TerminalFailureEnvelope.create(
            responsibility="interrupted",
            failure_stage="pipeline",
            failure_code="pipeline_interrupted",
            exception=exc,
            run_id=cost_ledger.run_id,
        )
        try:
            system_role_probe_audit.terminate(failure)
        finally:
            raise
    except Exception as exc:
        failure = TerminalFailureEnvelope.create(
            responsibility="framework",
            failure_stage="system_role_schema_probe",
            failure_code="system_role_schema_probe_sequence_aborted",
            exception=exc,
            run_id=cost_ledger.run_id,
        )
        system_role_probe_audit.terminate(failure)
        raise
    finally:
        try:
            execution_summary = execution_ledger.close()
        except ExecutionEventError as exc:
            logger.error(
                "[ResourceRuntime] Failed to persist final summary: {}",
                type(exc).__name__,
            )
            execution_summary = execution_ledger.summary()
        try:
            summary = cost_ledger.close()
        except ModelAccountingError as exc:
            logger.error("[ModelCost] Failed to persist final summary: {}", type(exc).__name__)
            summary = cost_ledger.summary()
        recovery_references = recovery_ledger.summary().get(
            "model_accounting_references", []
        )
        recovery_cost_projection = cost_ledger.operation_cost_summary(
            recovery_references
        )
        try:
            recovery_summary = recovery_ledger.close(
                model_cost_projection=recovery_cost_projection
            )
        except RecoveryPersistenceError as exc:
            logger.error(
                "[Recovery] Failed to persist final summary: {}",
                type(exc).__name__,
            )
            recovery_summary = recovery_ledger.summary()
        try:
            evaluation_summary = evaluation_ledger.close()
        except Exception as exc:
            logger.error(
                "[Evaluation] Failed to persist final summary: {}",
                type(exc).__name__,
            )
            evaluation_summary = evaluation_ledger.summary()
        try:
            artifact_summary, context_summary = artifact_store.ledger.close()
        except Exception as exc:
            logger.error(
                "[Artifacts] Failed to persist final lifecycle summaries: {}",
                type(exc).__name__,
            )
            artifact_summary = artifact_store.ledger.artifact_summary()
            context_summary = artifact_store.ledger.context_summary()
        try:
            upsert_model_cost_section(report_path, summary)
        except Exception as exc:
            logger.error("[ModelCost] Failed to update report section: {}", type(exc).__name__)
        try:
            upsert_execution_section(report_path, execution_summary)
        except Exception as exc:
            logger.error(
                "[ResourceRuntime] Failed to update report section: {}",
                type(exc).__name__,
            )
        try:
            upsert_recovery_section(report_path, recovery_summary)
        except Exception as exc:
            logger.error(
                "[Recovery] Failed to update report section: {}",
                type(exc).__name__,
            )
        try:
            from sgar_mvp.src.reporter import upsert_evaluation_artifact_section

            upsert_evaluation_artifact_section(
                report_path,
                evaluation_summary=evaluation_summary,
                artifact_summary=artifact_summary,
                context_summary=context_summary,
            )
        except Exception as exc:
            logger.error(
                "[Evaluation] Failed to update report section: {}",
                type(exc).__name__,
            )


def _terminal_exit_code(terminal_status: str) -> int:
    status = str(terminal_status or "").strip().lower()
    if status == "succeeded":
        return 0
    if status == "interrupted":
        return 130
    return 1


def _finalized_terminal_state(
    pipeline_status: str, provisional_status: str, manifest: Any,
) -> tuple[str, str]:
    """Use final audit results for both the CLI summary and process exit."""
    final_status = str(manifest.status)
    if final_status != provisional_status:
        pipeline_status = "structured_failure"
    return pipeline_status, final_status


def _git_checkout_runtime_identity(project_root: str | Path = PROJECT_ROOT) -> dict[str, Any]:
    """Describe the imported checkout without manufacturing a release attestation."""

    root = Path(project_root).resolve()

    def git(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *arguments],
            cwd=root,
            text=True,
            encoding="utf-8",
            errors="strict",
            capture_output=True,
            check=check,
        )

    try:
        branch = git("branch", "--show-current").stdout.strip()
        head = git("rev-parse", "HEAD").stdout.strip()
        tree = git("rev-parse", "HEAD^{tree}").stdout.strip()
        unstaged = git("diff", "--quiet", "--no-ext-diff", check=False).returncode
        staged = git("diff", "--cached", "--quiet", "--no-ext-diff", check=False).returncode
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("git_runtime_identity_unavailable") from exc
    if unstaged not in {0, 1} or staged not in {0, 1}:
        raise RuntimeError("git_runtime_dirty_state_unavailable")
    dirty = bool(unstaged or staged)
    return {
        "source_authority": "git_worktree",
        "branch": branch,
        "git_head": head,
        "git_tree": tree,
        "tracked_dirty": dirty,
        "runtime_classification": (
            "experimental_uncommitted" if dirty else "git_commit"
        ),
        "release_attestation": "not_requested",
    }


def main():
    args = parse_args()
    bootstrap_config = load_config(args.config, resolve_secrets=False) or {}
    runtime_settings = bootstrap_config.get("runtime_settings") or {}
    configure_runtime(args, config=bootstrap_config, project_root=Path(PROJECT_ROOT))
    auto_refresh = bool(runtime_settings.get("auto_refresh_control_receipt", False))
    default_profile = str(runtime_settings.get("model_profile_path") or "").replace("\\", "/")
    is_default_profile = default_profile == "sgar_mvp/config/model_profile.json"
    if (
        args.runtime_authority == "git"
        and auto_refresh
        and is_default_profile
        and os.environ.get("SGAR_SKIP_AUTO_CONTROL_PROBE") != "1"
    ):
        refresh_root = Path(tempfile.mkdtemp(prefix="sgar-control-probe-refresh-"))
        commands = (
            [sys.executable, "-m", "sgar_mvp.scripts.sync_default_model_profile"],
            [
                sys.executable,
                "-m",
                "sgar_mvp.scripts.refresh_local_control_probe_receipt",
                "--output-dir",
                str(refresh_root),
                "--config",
                str(args.config),
            ],
        )
        for command in commands:
            try:
                subprocess.run(command, cwd=PROJECT_ROOT, check=True)
            except (OSError, subprocess.CalledProcessError) as exc:
                raise SystemExit("SGAR control model profile refresh failed") from exc
    if args.runtime_authority == "git" and (
        args.source_seal or args.sealed_local_validation
    ):
        raise SystemExit(
            "--source-seal/--sealed-local-validation require --runtime-authority release"
        )
    if args.runtime_authority == "release" and bool(args.source_seal) != bool(
        args.sealed_local_validation
    ):
        raise SystemExit(
            "--source-seal and --sealed-local-validation must be supplied together"
        )
    if args.sealed_local_validation:
        if os.environ.get("SGAR_SEALED_LOCAL_VALIDATION") != "1":
            raise SystemExit("sealed local validation environment is not active")
        configured_seal = os.environ.get("SGAR_SOURCE_SEAL_PATH")
        if not configured_seal or Path(configured_seal).resolve() != Path(
            args.source_seal
        ).resolve():
            raise SystemExit("sealed local validation source identity mismatch")
    if args.run_dir and args.output_dir:
        raise SystemExit("--run-dir and deprecated --output-dir cannot be combined")
    explicit_run_dir = args.run_dir or args.output_dir
    try:
        workspace = create_run_workspace(
            output_root=Path(args.output_root),
            explicit_run_dir=(Path(explicit_run_dir) if explicit_run_dir else None),
        )
    except RunWorkspaceError as exc:
        raise SystemExit(f"SGAR run workspace rejected: {type(exc).__name__}") from exc

    output_dir = str(workspace.path())
    bootstrap_request_id = uuid.uuid4().hex
    bootstrap_identity = canonical_sha256(
        {
            "protocol": "sgar-task-invocation-v1",
            "request_id": bootstrap_request_id,
            "status": "input_snapshot_pending",
        }
    )
    manifest_store = RunManifestStore(
        run_dir=workspace.path(),
        run_id=workspace.run_id,
        request_id=bootstrap_request_id,
        invocation_sha256=bootstrap_identity,
    )

    try:
        resolved_request = _resolve_task_request_arguments(
            args,
            run_dir=workspace.path(),
        )
        prepared_invocation = prepare_task_invocation(
            query=resolved_request.exact_query,
            input_specs=resolved_request.input_specs,
            run_dir=workspace.path(),
            request_id=resolved_request.request_id,
            final_deliverable_contract=resolved_request.final_deliverable_contract,
            public_context_descriptors=resolved_request.public_context_descriptors,
            allowed_public_input_roots=(
                resolved_request.allowed_public_input_roots
            ),
            project_root=Path(PROJECT_ROOT),
        )
        manifest_store.bind_invocation(
            request_id=prepared_invocation.invocation.request_id,
            invocation_sha256=prepared_invocation.invocation.invocation_sha256,
            identities={
                "public_input_snapshot_sha256": (
                    prepared_invocation.invocation.input_snapshot_sha256
                ),
                "task_invocation_protocol": prepared_invocation.invocation.protocol,
                "request_source_sha256": resolved_request.request_source_sha256,
            },
        )
    except (TaskInvocationError, OSError, ValueError) as exc:
        manifest_store.terminal(
            "framework_failure",
            primary_failure=sanitized_run_failure(
                responsibility="framework",
                failure_stage="task_invocation",
                failure_code="task_invocation_invalid",
                exception=exc,
            ),
        )
        raise SystemExit("SGAR task invocation rejected before paid work") from exc

    run_root = workspace.path().resolve()

    def isolated_output_path(value: str | None, default_name: str) -> Path:
        candidate = Path(value).absolute() if value else run_root / default_name
        try:
            candidate.resolve(strict=False).relative_to(run_root)
        except ValueError as exc:
            raise RunWorkspaceError("run_output_path_outside_workspace") from exc
        if candidate.exists():
            raise RunWorkspaceError("run_output_path_exists")
        candidate.parent.mkdir(parents=True, exist_ok=True)
        return candidate

    try:
        report_path_obj = isolated_output_path(args.report_path, "experiment_report.md")
        log_path_obj = isolated_output_path(args.log_path, "pipeline.log")
    except RunWorkspaceError as exc:
        manifest_store.terminal(
            "framework_failure",
            primary_failure=sanitized_run_failure(
                responsibility="framework",
                failure_stage="run_workspace",
                failure_code="run_output_path_invalid",
                exception=exc,
            ),
        )
        raise SystemExit("SGAR output path rejected before logging") from exc

    report_path = str(report_path_obj)
    log_path = str(log_path_obj)
    logger.add(log_path, mode="x", encoding="utf-8", level="INFO")
    progress_path = run_root / "progress.log"
    terminal_progress.configure(progress_path=(
        progress_path if progress_path not in {log_path_obj.resolve(), report_path_obj.resolve()} else None
    ))
    terminal_progress.location("Run directory", run_root, run_root)
    terminal_progress.location("Full log", log_path, run_root)
    manifest_store.mark_running()
    logger.info("=" * 60)

    framework_source_clean = False
    if args.runtime_authority == "git":
        try:
            git_identity = _git_checkout_runtime_identity(PROJECT_ROOT)
        except Exception as exc:
            manifest_store.terminal(
                "framework_failure",
                primary_failure=sanitized_run_failure(
                    responsibility="framework",
                    failure_stage="runtime_authority",
                    failure_code="git_runtime_identity_invalid",
                    exception=exc,
                ),
            )
            return 1
        framework_source_clean = not bool(git_identity["tracked_dirty"])
        manifest_store.update_identities(
            {"runtime_authority": "git", **git_identity}
        )
    else:
        manifest_store.update_identities(
            {
                "runtime_authority": "release",
                "source_authority": "release_attestation",
            }
        )
    logger.info("S-GAR MVP — End-to-End Pipeline")
    logger.info("=" * 60)

    raw_config = load_config(args.config, resolve_secrets=False)
    try:
        if raw_config is None:
            raise FormalSecretPolicyError("formal_configuration_missing")
        secret_policy = validate_formal_secret_config(raw_config)
    except FormalSecretPolicyError as exc:
        manifest_store.terminal(
            "framework_failure",
            primary_failure=sanitized_run_failure(
                responsibility="framework",
                failure_stage="secret_policy",
                failure_code=exc.failure_code,
                exception=exc,
            ),
        )
        logger.error("Formal secret policy rejected the runtime configuration.")
        return 1

    config = load_config(args.config)
    if not config or config.get("llm_key") == "your_api_key_here":
        logger.error("Invalid config.json — please set a valid llm_key.")
        manifest_store.terminal(
            "framework_failure",
            primary_failure=sanitized_run_failure(
                responsibility="framework",
                failure_stage="configuration",
                failure_code="llm_configuration_invalid",
            ),
        )
        return 1
    manifest_store.set_private_portability_needles(
        secret_values=(str(config.get("llm_key") or ""),)
    )
    manifest_store.update_identities(
        {
            "formal_secret_policy_protocol": secret_policy.protocol,
            "formal_secret_policy_sha256": secret_policy.policy_sha256,
        }
    )

    if args.runtime_authority == "git":
        try:
            base_url = str(
                (config.get("llm_settings") or {}).get(
                    "base_url", "https://api.openai.com/v1"
                )
            )
            endpoint_identity = production_model_endpoint_identity(base_url=base_url)
            runtime_identity = build_retrieval_runtime_identity(
                project_root=PROJECT_ROOT,
                provider_compatibility=_provider_compatibility_projection(base_url),
                provider_endpoint_identity_sha256=endpoint_identity.identity_sha256,
                require_release_sealed=False,
                honor_release_environment=False,
            )
            ready_state = load_applied_model_ready_state(
                PROJECT_ROOT,
                expected_endpoint_identity_sha256=endpoint_identity.identity_sha256,
            )
            active_manifest = json.loads(
                (
                    Path(PROJECT_ROOT)
                    / "Pool"
                    / "index_meta"
                    / "index_build_manifest.json"
                ).read_text(encoding="utf-8-sig")
            )
            manifest_store.update_identities(
                {
                    "model_ready_state_sha256": ready_state.health_sha256,
                    "model_ready_count": len(ready_state.models),
                    "provider_endpoint_identity_sha256": endpoint_identity.identity_sha256,
                    "retrieval_runtime_identity_sha256": runtime_identity.identity_sha256,
                    "active_retrieval_generation_id": active_manifest.get(
                        "generation_id"
                    ),
                }
            )
        except Exception as exc:
            manifest_store.terminal(
                "framework_failure",
                primary_failure=sanitized_run_failure(
                    responsibility="framework",
                    failure_stage="runtime_authority",
                    failure_code="git_runtime_authority_invalid",
                    exception=exc,
                ),
            )
            return 1

    if args.runtime_authority == "git":
        manifest_store.update_phase("framework_conformance", "not_requested")
        manifest_store.update_identities(
            {"release_attestation": "not_requested"}
        )
    else:
        manifest_store.update_phase("framework_conformance", "running")
        try:
            base_url = str(
                (config.get("llm_settings") or {}).get(
                    "base_url", "https://api.openai.com/v1"
                )
            )
            conformance = run_production_conformance(
                prepared_invocation=prepared_invocation,
                request_source_sha256=resolved_request.request_source_sha256,
                run_dir=workspace.path(),
                config=raw_config,
                network_policy_mode=args.network_policy,
                project_root=PROJECT_ROOT,
                provider_compatibility=_provider_compatibility_projection(base_url),
                require_docker=True,
                require_source_clean=True,
                source_seal_path=args.source_seal,
            )
            manifest_store.update_identities(
                {
                    "framework_conformance_protocol": conformance.get("protocol"),
                    "framework_conformance_sha256": conformance.get("report_sha256"),
                    **dict(conformance.get("identities") or {}),
                }
            )
            framework_source_clean = bool(
                (conformance.get("checks") or {})
                .get("framework_source", {})
                .get("framework_source_clean")
            )
            if conformance.get("valid") is not True:
                conformance_errors = {
                    str(item) for item in (conformance.get("errors") or ())
                }
                failure_code = (
                    "internal_metadata_layout_invalid"
                    if "internal_metadata_layout_invalid" in conformance_errors
                    else "production_conformance_invalid"
                )
                manifest_store.update_phase("framework_conformance", "failed")
                manifest_store.terminal(
                    "framework_failure",
                    primary_failure=sanitized_run_failure(
                        responsibility="framework",
                        failure_stage="framework_conformance",
                        failure_code=failure_code,
                    ),
                    framework_source_clean=bool(
                        (conformance.get("checks") or {})
                        .get("framework_source", {})
                        .get("framework_source_clean")
                    ),
                )
                logger.error("Production conformance failed before paid work.")
                return 1
            manifest_store.update_phase("framework_conformance", "passed")
        except KeyboardInterrupt as exc:
            manifest_store.update_phase("framework_conformance", "interrupted")
            manifest_store.terminal(
                "interrupted",
                primary_failure=sanitized_run_failure(
                    responsibility="interrupted",
                    failure_stage="framework_conformance",
                    failure_code="user_interrupted",
                    exception=exc,
                ),
                framework_source_clean=False,
            )
            return 130
        except Exception as exc:
            manifest_store.update_phase("framework_conformance", "failed")
            manifest_store.terminal(
                "framework_failure",
                primary_failure=sanitized_run_failure(
                    responsibility="framework",
                    failure_stage="framework_conformance",
                    failure_code="production_conformance_exception",
                    exception=exc,
                ),
                framework_source_clean=False,
            )
            logger.error(
                "Production conformance raised before paid work: {}",
                type(exc).__name__,
            )
            return 1

    user_query, query_diagnostics = diagnose_and_repair_query_text(
        prepared_invocation.invocation.query
    )
    if query_diagnostics.get("query_encoding_warning"):
        logger.warning(
            "[Input] Query encoding warning: {} | repair_applied={}",
            query_diagnostics.get("reason"),
            query_diagnostics.get("repair_applied"),
        )

    logger.info("Run ID: {}", workspace.run_id)
    logger.info("Explicit public inputs: {}", len(prepared_invocation.invocation.public_inputs))

    terminal_status = "framework_failure"
    primary_failure = None
    terminal_manifest_failure = None
    recovery_outcome = None
    causal_chain: tuple[Mapping[str, object], ...] = ()
    try:
        manifest_store.update_phase("pipeline", "running")
        pipeline_status = asyncio.run(
            run_pipeline(
                config,
                user_query,
                output_dir,
                report_path,
                query_diagnostics=query_diagnostics,
                task_invocation=prepared_invocation,
                network_policy_mode=args.network_policy,
                run_id=workspace.run_id,
                planner_variant=args.planner_variant,
                runtime_authority=args.runtime_authority,
                max_generation_requests=args.max_generation_requests,
                method_deadline_monotonic=(
                    time.monotonic() + args.deadline_sec
                    if args.deadline_sec is not None else None
                ),
            )
        )
        if pipeline_status in {"complete_success", "success_with_warnings"}:
            terminal_status = "succeeded"
            recovery_outcome = _pipeline_recovery_outcome_projection(
                getattr(pipeline_status, "recovery_outcomes", ())
            )
            causal_chain = tuple(
                dict(item)
                for item in (getattr(pipeline_status, "causal_chain", ()) or ())
                if isinstance(item, Mapping)
            )
            manifest_store.update_phase("pipeline", "succeeded")
        else:
            projection = _pipeline_terminal_projection(pipeline_status)
            terminal_status = str(projection["status"])
            manifest_store.update_phase("pipeline", terminal_status)
            primary_failure = projection["primary_failure"]
            terminal_manifest_failure = projection["terminal_failure"]
            recovery_outcome = projection["recovery_outcome"]
            causal_chain = projection["causal_chain"]
    except BudgetControlError as exc:
        failure = TerminalFailureEnvelope.create(
            responsibility="budget",
            failure_stage="budget_control",
            failure_code=str(getattr(exc, "error_code", "model_cost_limit_reached")),
            exception=exc,
            run_id=workspace.run_id,
        )
        pipeline_status = _pipeline_status_from_terminal_failure(failure)
        projection = _pipeline_terminal_projection(pipeline_status)
        terminal_status = str(projection["status"])
        primary_failure = projection["primary_failure"]
        terminal_manifest_failure = projection["terminal_failure"]
        causal_chain = projection["causal_chain"]
    except ModelAccountingError as exc:
        logger.error(
            "[ModelCost] Pricing/accounting configuration failed before a paid call: {}",
            type(exc).__name__,
        )
        failure = TerminalFailureEnvelope.create(
            responsibility="framework",
            failure_stage="model_accounting",
            failure_code=str(
                getattr(exc, "error_code", "model_accounting_configuration_failed")
            ),
            exception=exc,
            run_id=workspace.run_id,
        )
        pipeline_status = _pipeline_status_from_terminal_failure(failure)
        projection = _pipeline_terminal_projection(pipeline_status)
        terminal_status = str(projection["status"])
        primary_failure = projection["primary_failure"]
        terminal_manifest_failure = projection["terminal_failure"]
        causal_chain = projection["causal_chain"]
    except (asyncio.CancelledError, KeyboardInterrupt) as exc:
        failure = TerminalFailureEnvelope.create(
            responsibility="interrupted",
            failure_stage="pipeline",
            failure_code=(
                "pipeline_cancelled"
                if isinstance(exc, asyncio.CancelledError)
                else "user_interrupted"
            ),
            exception=exc,
            run_id=workspace.run_id,
        )
        pipeline_status = _pipeline_status_from_terminal_failure(failure)
        projection = _pipeline_terminal_projection(pipeline_status)
        terminal_status = str(projection["status"])
        primary_failure = projection["primary_failure"]
        terminal_manifest_failure = projection["terminal_failure"]
        causal_chain = projection["causal_chain"]
    except Exception as exc:
        retryable, transport_code = classify_transport_exception(exc)
        if transport_code != "provider_non_transport_error":
            responsibility = "infrastructure"
            failure_stage = "provider_transport"
            failure_code = transport_code
        elif isinstance(exc, InternalMetadataLayoutError):
            responsibility = "framework"
            failure_stage = "internal_metadata_layout"
            failure_code = exc.failure_code
        elif isinstance(exc, RecoveryControlError):
            responsibility = "framework"
            failure_stage = "recovery_configuration"
            failure_code = "recovery_configuration_failed"
        elif isinstance(exc, (EvaluationRuntimeError, ArtifactLifecycleError)):
            responsibility = "framework"
            failure_stage = "evaluation_artifact_runtime"
            failure_code = "evaluation_artifact_runtime_failed"
        elif isinstance(exc, RetrievalRuntimeError):
            projected_responsibility = str(
                getattr(exc, "failure_responsibility", "framework")
            )
            responsibility = (
                projected_responsibility
                if projected_responsibility
                in {"framework", "infrastructure", "research", "budget"}
                else "framework"
            )
            failure_stage = "candidate_model_liveness"
            failure_code = str(
                getattr(exc, "error_code", "pipeline_subsystem_contract_failed")
            )
        elif isinstance(exc, ExecutionEventError):
            responsibility = "framework"
            failure_stage = "pipeline_subsystem"
            failure_code = "pipeline_subsystem_contract_failed"
        else:
            responsibility = "framework"
            failure_stage = "pipeline_unclassified_exception"
            exception_token = re.sub(
                r"[^a-z0-9]+",
                "_",
                type(exc).__name__.strip().lower(),
            ).strip("_") or "unknown"
            failure_code = f"pipeline_unclassified_{exception_token}"
        failure = TerminalFailureEnvelope.create(
            responsibility=responsibility,
            failure_stage=failure_stage,
            failure_code=failure_code,
            exception=exc,
            retryable=retryable if responsibility == "infrastructure" else False,
            run_id=workspace.run_id,
        )
        pipeline_status = _pipeline_status_from_terminal_failure(failure)
        projection = _pipeline_terminal_projection(pipeline_status)
        terminal_status = str(projection["status"])
        primary_failure = projection["primary_failure"]
        terminal_manifest_failure = projection["terminal_failure"]
        causal_chain = projection["causal_chain"]
    finally:
        try:
            manifest_store.update_identities(
                {
                    **_model_liveness_manifest_identity(workspace.path()),
                    **_dag_edge_manifest_identity(workspace.path()),
                    **_planner_attempt_manifest_identity(workspace.path()),
                }
            )
        except Exception as exc:
            manifest_store.add_secondary_audit_failure(
                sanitized_run_failure(
                    responsibility="framework",
                    failure_stage="run_manifest",
                    failure_code="terminal_evidence_manifest_projection_failed",
                    exception=exc,
                ).model_dump(mode="json")
            )
            if terminal_status == "succeeded":
                primary_failure = sanitized_run_failure(
                    responsibility="framework",
                    failure_stage="run_manifest",
                    failure_code="terminal_evidence_manifest_projection_failed",
                    exception=exc,
                )
                terminal_manifest_failure = primary_failure
                terminal_status = "framework_failure"
        ledger_evidence = collect_run_ledger_evidence(
            workspace.path(),
            expected_run_id=workspace.run_id,
        )
        if terminal_status != "interrupted" and any(
            ledger_evidence["unmatched_calls"].values()
        ):
            audit_failure = sanitized_run_failure(
                responsibility="framework",
                failure_stage="run_manifest",
                failure_code=(
                    "terminal_run_ledger_audit_invalid"
                    if ledger_evidence["unmatched_calls"].get(
                        "ledger_audit_errors", 0
                    )
                    else "terminal_run_has_unmatched_calls"
                ),
            )
            if primary_failure is None:
                primary_failure = audit_failure
                terminal_manifest_failure = audit_failure
                terminal_status = "framework_failure"
            else:
                manifest_store.add_secondary_audit_failure(
                    audit_failure.model_dump(mode="json")
                )
            causal_chain = (
                *causal_chain,
                {
                    "sequence": len(causal_chain),
                    "kind": "terminal_audit_failure",
                    "subtask_id": "",
                    "responsibility": audit_failure.responsibility,
                    "failure_stage": audit_failure.failure_stage,
                    "failure_code": audit_failure.failure_code,
                    "message_sha256": audit_failure.message_sha256,
                },
            )
        manifest_store.update_phase("pipeline", terminal_status)
        final_manifest = manifest_store.terminal(
            terminal_status,
            primary_failure=primary_failure,
            terminal_failure=terminal_manifest_failure,
            recovery_outcome=recovery_outcome,
            causal_chain=causal_chain,
            ledger_hashes=ledger_evidence["ledger_hashes"],
            unmatched_calls=ledger_evidence["unmatched_calls"],
            framework_source_clean=framework_source_clean,
        )
    pipeline_status, terminal_status = _finalized_terminal_state(
        pipeline_status, terminal_status, final_manifest,
    )
    final_message = _terminal_pipeline_log_lines(pipeline_status)[0]
    if pipeline_status == "structured_failure":
        logger.error(final_message)
    else:
        logger.info(final_message)
    terminal_progress.final_summary(pipeline_status, run_root, report_path, log_path, manifest=final_manifest)
    return _terminal_exit_code(terminal_status)


if __name__ == "__main__":
    raise SystemExit(main())
