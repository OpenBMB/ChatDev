"""
S-GAR Execution Layer - DAG Orchestrator
==========================================
Central state machine that:
1. Resolves DAG dependencies to build precise per-node context.
2. Dispatches subtasks to the appropriate Executor (Smart / Dumb).
3. Runs Router Auto-Evaluation with Self-Healing Fallback.
4. Checkpoints intermediate artifacts to disk for observability.
"""

from sgar_mvp.src.direct_network import direct_async_http_client, load_project_tool_environment

import os
import posixpath
import sys
import re
import json
import hashlib
import random
import asyncio
import ast
import copy
import shutil
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, List, Literal, Mapping, Optional, Sequence, Set, Tuple, cast

from loguru import logger
from openai import AsyncOpenAI

from . import terminal_progress

from .executors import (
    AgentExecutor,
    ControllerTurnExecutor,
    DumbExecutor,
    ExecutionResult,
    HostPythonExecutor,
    SmartExecutor,
)
from .schema import (
    AnchorExpansionAttempt,
    DAGPatch,
    ArtifactHandle,
    ArtifactProfile,
    ArtifactValidationProfile,
    ContextPacket,
    DagEdgeContractV1,
    DownstreamConsumptionHint,
    EvaluationDimensionScores,
    EvaluationFailureType,
    EvaluationResult,
    EvaluationVerdict,
    ExecutionStrictness,
    ExecutionMode,
    ManifestType,
    NodeExecutionOutcome,
    NodeExecutionStatus,
    NodeFailureCategory,
    OperationKind,
    ResourceApplicationPlan,
    ResourceApplicationStep,
    ResourceOutputContract,
    ResourceUsageDecision,
    ResolvedLocalFileProfile,
    RoutingSession,
    Subtask,
    SubtaskOutputContract,
    TrainingLabel,
    TypedResourceRef,
)
from .capability_registry import GLOBAL_CAPABILITY_REGISTRY
from .capability_operations import (
    CAPABILITY_TO_EXECUTION_OPERATION,
    normalize_capability_operation,
    tool_allowed_operation_kinds,
)
from .required_operation_evidence import required_operation_evidence_failure
from .executors import _retryable_transport_exception
from .llm_compat import async_create_chat_completion_with_compat, is_response_format_unsupported_error
from .model_accounting import ModelAccountingError, RunCostLedger
from .model_media import (
    ModelMediaProjectionError,
    build_authorized_model_media_parts,
    build_model_media_parts_from_materials,
    build_task_authorized_model_media_parts,
    materialize_task_media_handles,
    build_controller_observation_media_parts,
)
from .model_identity import resolve_model_identity, validate_typed_model_identity
from .model_transport import (
    AsyncModelTransportPort,
    ModelTransportError,
    ProviderEndpointIdentity,
    require_async_model_transport,
)
from .execution_events import RunExecutionLedger
from .formal_serialization import append_formal_jsonl
from .formal_contracts import MaterialDescriptorV1
from .execution_requirements import requires_execution_network
from .pipeline_control import canonical_sha256, subtask_revision_identity_sha256
from .output_realization import OutputRealizer
from .controller_session import (
    ControllerSessionError,
    ControllerSessionResultV1,
    ControllerSessionRunner,
    ControllerSessionSpecV2,
    ControllerSessionSummaryV2,
    load_controller_session_policy,
    required_controller_file_delivery_operation,
)
from .controller_tool_runtime import (
    CONTROLLER_TOOL_RUNTIME_PROTOCOL,
    ControllerToolCallIntentV1,
    ControllerToolDispatchContext,
    ControllerToolInvocationGateway,
    ControllerToolRuntimeError,
    ResolvedControllerToolInputs,
)
from .terminal_failure import (
    TerminalFailureEnvelope,
    highest_severity_terminal_failure,
    terminal_failure_from_execution_result,
)
from .task_invocation import FinalDeliverableContract, TaskInvocation
from .authorized_material import (
    AuthorizedMaterialError,
    AuthorizedMaterialSource,
    AuthorizedModelMaterialView,
    build_authorized_model_material_view,
    public_snapshot_identity,
)
from .executable_plan import SealedPlanCompilationArtifact, StepOutputContract
from .plan_compiler import (
    PROCESS_EXECUTION_LIFECYCLE_RULE,
    build_compiler_public_context,
)
from .plan_lowering import LoweredExecutionPlan
from .model_request_budget import current_tool_timeout
from .payload_provenance import PayloadSourceRegistry, ProductionModelPayloadGuard
from .public_inputs import (
    inspect_internal_metadata_layout,
    path_sha256,
    validate_internal_metadata_scope,
)
from .resource_runtime import (
    ExecutionWorldDescriptor,
    ResourceCallRequest,
    ResourceCallResult,
    ResourceCallStatus,
    ResourceCallValidationError,
    ResourceDefinition,
    ResourceExecutionContext,
    ResourceManifestError,
    ResourceRuntime,
    execution_result_to_resource_result,
    resource_result_to_execution_result,
)
from .retrieval_runtime import (
    RetrievalRuntimeError,
    load_applied_model_ready_state,
)
from .formal_execution import (
    FormalExecutablePlan,
    SealedPlanExecutionEngine,
)
from .recovery_control import (
    CompletedStepCheckpoint,
    RecoveryEventLedger,
    RecoveryPolicy,
    executable_step_semantic_sha256,
)
from .recovery_controller import RecoveryController
from .recovery_integration import (
    CallableSealedExecutionPort,
    GenericTemporaryToolRecoveryPort,
    SealedCompilerRecoveryPort,
    SystemFullGenerationRecoveryPort,
)
from .temporary_tool import TemporaryToolManager
from .artifact_lifecycle import (
    ArtifactLifecycleCoordinator,
    ArtifactLifecycleStore,
    ContextCommitStore,
    MachineContractFailure,
    build_final_artifact_candidate,
    validate_machine_contract,
)
from .artifact_v2 import (
    ArtifactV2Error,
    ArtifactV2MachineContractError,
    build_candidate_v2,
    descriptor_for_bytes,
    descriptor_for_path,
)
from .pipeline_control import SubtaskRevisionRef
from .evaluation_contracts import (
    ArtifactRepresentation,
    ArtifactRevisionRef,
    EvaluationContextSnapshot,
    EvaluationSourceEvidence,
)
from .evaluation_reference import build_evaluation_reference_standard
from .evaluation_runtime import normalize_evaluation_mode
from .process_supervisor import manifest_tool_environment_allowlist
from .tool_execution_provider import (
    PreparedToolDispatch,
    ToolExecutionProvider,
    sandbox_scope_sha256,
    uses_unscoped_host_python,
)
from .control_models import is_control_model_failover_failure
from .runtime_requirements import (
    DependencyGate,
    DependencyCheckResult,
    EnvironmentProfile,
    interpret_tool_status,
    missing_external_python_imports,
    scan_environment,
    scan_python_imports_from_file,
    scan_python_imports_from_text,
)
from .execution_contracts import normalize_artifact_type
from .controller_skills import (
    ControllerSkillError, build_skill_bundle, controller_skill_sources, validate_skill_requirements,
)
from .skill_runtime import (
    DEFAULT_MAX_SKILL_BYTES,
    SkillPackageError,
    SkillPackageLoader,
)


def orchestrator_request_static_material() -> Dict[str, Any]:
    """Fixed prompt glue used while composing downstream Model/Agent requests."""

    return {
        "protocol": "orchestrator-request-static-material-v1",
        "process_execution_lifecycle_rule": PROCESS_EXECUTION_LIFECYCLE_RULE,
        "step_context_fragments": [
            "--- [Plan-Bound Runtime Inputs] ---",
            "--- Skill: ",
            "... (truncated)",
            "--- [Resource Application Step Outputs] ---",
            "--- [Process Execution Lifecycle] ---",
        ],
        "final_contract_fragments": [
            "Task description:",
            "Requested artifact_type:",
            "Planner expected_output:",
            "The final answer must be a complete replacement artifact, not a patch or commentary.",
            "Use upstream actual artifacts and resource step outputs as source material.",
            "Do not claim that local paths are inaccessible when their contents are already injected.",
            "Do not output greetings, explanations outside the artifact, or <think> blocks.",
            "Do not use placeholder imports, placeholder paths, TODO stubs, or names like your_module.",
            "For code artifacts, function names, CLI arguments, and file names mentioned in the Planner expected_output are hard interface requirements. If you prefer a different internal helper name, also provide a thin compatibility wrapper for the required name.",
            "The default generated-code runtime is python-stdlib. Avoid third-party imports unless the selected runtime/tool context explicitly says the dependency is available or installable. When possible, rewrite data handling with standard libraries such as csv, json, pathlib, datetime, and unittest.",
            "ResourceApplicationPlan:",
            "Final output key:",
            "Upstream actual context:",
        ],
    }
from .binding_protocol import (
    BINDING_PROTOCOL,
    BindingFrameworkError,
    BindingProtocolError,
    container_dependency_references,
    dependency_references,
    normalize_contract_kind,
    normalize_step_reference,
    parse_binding_source,
    resolve_binding,
    stringify_literal,
)
from .path_namespace import PathNamespaceError, RuntimePathMap


@dataclass(frozen=True)
class _ExecutionLocalState:
    """Coroutine-local transient state for one execution boundary."""

    sandbox_scope: Dict[str, Any] = field(default_factory=dict)
    runtime_path_map: RuntimePathMap | None = None
    model_payload_guard: Callable[[Mapping[str, Any]], None] | None = None
    allow_semantic_normalization: bool = True
    sealed_entrypoints: Dict[str, str] = field(default_factory=dict)
    formal_execution_active: bool = False


def _canonical_evaluation_output_contract(
    *,
    subtask: Subtask,
    validated_final_output_contract: StepOutputContract | None,
) -> dict[str, Any]:
    """Project the concrete structure without mutating Planner requirements.

    Explicit macro schemas are validated separately against the same bytes.
    Compiler refinement remains visible to publication and downstream consumers.
    """

    if subtask.output_contract is not None:
        projected = copy.deepcopy(subtask.output_contract.model_dump(mode="json"))
    else:
        projected = SubtaskOutputContract(
            artifact_type=subtask.artifact_type,
            output_extension=subtask.output_extension,
            downstream_consumers=list(subtask.depends_on),
        ).model_dump(mode="json")

    if subtask.semantic_contract_v2 is not None:
        projected["content_kind"] = subtask.semantic_contract_v2.output.content_kind
        semantic_syntax = subtask.semantic_contract_v2.output.syntax_validator
        if projected.get("syntax_validator") != semantic_syntax:
            raise RuntimeError("evaluation_syntax_validator_identity_mismatch")

    if validated_final_output_contract is not None:
        semantic_artifact_type = str(projected.get("artifact_type") or "").strip().lower()
        machine_artifact_type = str(
            validated_final_output_contract.artifact_type or ""
        ).strip().lower()
        if not machine_artifact_type or machine_artifact_type != semantic_artifact_type:
            raise RuntimeError("evaluation_machine_artifact_type_identity_mismatch")
        if semantic_artifact_type == "json":
            schema_hint = validated_final_output_contract.schema_hint
            if not isinstance(schema_hint, Mapping):
                raise RuntimeError("evaluation_machine_json_schema_missing")
            projected["json_schema"] = copy.deepcopy(dict(schema_hint))

    return SubtaskOutputContract.model_validate(projected).model_dump(mode="json")


def _validate_direct_final_write_source(
    *,
    plan: ResourceApplicationPlan,
    producer_step: ResourceApplicationStep,
    content: str,
    task_output_contract: SubtaskOutputContract | None,
) -> dict[str, Any] | None:
    """Check declared syntax before passing a direct Model value to a final file write.

    Only an exact content binding qualifies. Other transforms and file writes
    retain their own execution and final delivery checks.
    """

    from .artifact_semantics import requires_content_contract_validation
    if task_output_contract is None or not requires_content_contract_validation(task_output_contract.model_dump(mode="json")):
        return None
    if not _is_direct_final_write_source(
        plan=plan,
        producer_step=producer_step,
    ):
        return None
    from .artifact_semantics import validate_delivery_content

    macro_contract = task_output_contract.model_dump(mode="json")
    execution_contract = macro_contract
    if macro_contract.get("artifact_type") == "json":
        compiled = _validated_delivery_output_contract(plan)
        if compiled is not None and compiled.artifact_type == "json" and compiled.schema_hint is not None:
            execution_contract = {**macro_contract, "json_schema": compiled.schema_hint}
    return validate_delivery_content(content.encode("utf-8"), execution_contract, macro_contract)


def _generated_source_contract(
    *, plan: ResourceApplicationPlan | None, producer_step: ResourceApplicationStep,
) -> dict[str, Any] | None:
    """Derive source syntax from an exact declared file-content handoff."""
    if plan is None:
        return None
    contract = producer_step.expected_output_contract
    if hasattr(contract, "model_dump"):
        contract = contract.model_dump(mode="json")
    if not isinstance(contract, Mapping) or contract.get("artifact_type") != "code":
        return None
    for consumer in plan.steps:
        if consumer.operation_kind != OperationKind.WRITE_FILE:
            continue
        binding = consumer.input_bindings.get("content")
        path = consumer.input_bindings.get("path")
        if (
            isinstance(binding, Mapping)
            and set(binding) == {"from_step", "output_key"}
            and binding["from_step"] == producer_step.step_id
            and binding["output_key"] == producer_step.output_key
            and isinstance(path, Mapping)
            and isinstance(path.get("literal"), str)
            and Path(path["literal"]).suffix.lower() == ".py"
        ):
            return {"language": "python", "delivery_kind": "raw_source", "path": path["literal"]}
    return None


def _execution_lifecycle_context(
    context: str, *, plan: ResourceApplicationPlan | None,
    step: ResourceApplicationStep,
) -> str:
    """Add execution guidance only to a selected generator or process controller.

    This explains call completion; it neither adds acceptance requirements nor
    changes a sealed plan, callable scope, runtime, or native result contract.
    """
    process_operations = {"generated_code_execution", "python_execution", "execute_shell_commands"}

    def executes_process(item: Any) -> bool:
        operation_id = str(getattr(item, "capability_operation_id", "") or "")
        return normalize_capability_operation(operation_id.rsplit("::", 1)[-1]) in process_operations

    spec = getattr(step, "controller_session_spec", None)
    relevant = any(executes_process(item) for item in getattr(spec, "callable_tools", ()))
    contract = step.expected_output_contract
    artifact_type = getattr(contract, "artifact_type", "")
    is_code = str(getattr(artifact_type, "value", artifact_type) or "").casefold() == "code"
    if not relevant and is_code and plan is not None:
        descendants = {step.step_id}
        remaining = list(plan.steps)
        while remaining:
            newly_reached = [item for item in remaining
                             if descendants.intersection(getattr(item, "depends_on", ()) or ())]
            if not newly_reached:
                break
            if any(executes_process(item) for item in newly_reached):
                relevant = True
                break
            descendants.update(item.step_id for item in newly_reached)
            remaining = [item for item in remaining if item not in newly_reached]
    if not relevant:
        return context
    guidance = json.dumps({"execution_guidance": PROCESS_EXECUTION_LIFECYCLE_RULE},
                          ensure_ascii=False, separators=(",", ":"))
    return context + "\n\n--- [Process Execution Lifecycle] ---\n" + guidance


def _is_direct_final_write_source(
    *,
    plan: ResourceApplicationPlan,
    producer_step: ResourceApplicationStep,
) -> bool:
    """Return whether one step supplies unchanged content to the final writer."""

    final_step = next(
        (step for step in plan.steps if step.output_key == plan.final_output_from),
        None,
    )
    if final_step is None or final_step.operation_kind != OperationKind.WRITE_FILE:
        return False
    binding = final_step.input_bindings.get("content")
    if not isinstance(binding, Mapping) or set(binding) != {"from_step", "output_key"}:
        return False
    return bool(
        binding.get("from_step") == producer_step.step_id
        and binding.get("output_key") == producer_step.output_key
    )


def _validated_delivery_output_contract(plan: Any) -> StepOutputContract:
    """Select the unchanged file content's contract rather than a writer receipt."""
    reference = getattr(plan, "final_output", None)
    final_key = (
        reference.output_key if reference is not None
        else plan.final_output_from
    )
    final_step = next(step for step in plan.steps if step.output_key == final_key)
    application = getattr(final_step, "resource_application", None)
    realization = getattr(application, "output_realization_contract", None)
    if getattr(realization, "realization_kind", None) == "materialized_file_side_effect":
        return final_step.expected_output_contract
    if final_step.operation_kind == OperationKind.WRITE_FILE:
        binding = final_step.input_bindings.get("content")
        if isinstance(binding, Mapping) and set(binding) == {"from_step", "output_key"}:
            producer = next((step for step in plan.steps
                             if step.step_id == binding["from_step"]
                             and step.output_key == binding["output_key"]), None)
            if producer is not None:
                return producer.expected_output_contract
    return final_step.expected_output_contract


def _realize_materialized_delivery_result(result: Any, step: Any, record: Any) -> None:
    """Present the verified primary file to evaluation while retaining receipt identity."""
    application = getattr(step, "resource_application", None)
    realization = getattr(application, "output_realization_contract", None)
    if (
        getattr(realization, "realization_kind", None) != "materialized_file_side_effect"
        or record is None or record.origin not in {"external_tool_output", "tool_output"}
        or record.artifact_type != step.expected_output_contract.artifact_type
        or record.artifact_type not in {"json", "plaintext", "code", "markdown", "csv"}
    ):
        return
    raw = Path(record.path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != record.metadata.get("content_sha256"):
        raise RuntimeError("materialized_delivery_content_hash_mismatch")
    receipt = str(result.output_data or "").encode("utf-8")
    result.output_data = raw.decode("utf-8")
    result.cost_metric["materialized_delivery"] = {
        "native_receipt_sha256": hashlib.sha256(receipt).hexdigest(),
        "content_sha256": hashlib.sha256(raw).hexdigest(),
        "byte_size": len(raw), "task_path": record.metadata.get("tool_path"),
    }
    outputs = result.cost_metric.get("application_step_outputs")
    if isinstance(outputs, dict):
        outputs[step.output_key] = result.output_data


def _unwrap_direct_final_python_fence(
    *,
    plan: ResourceApplicationPlan,
    producer_step: ResourceApplicationStep,
    content: str,
    task_output_contract: SubtaskOutputContract | None,
) -> str | None:
    """Remove only an unambiguous Markdown wrapper from generated Python.

    This conversion is limited to an exact Model-to-final-file binding.  It
    neither extracts code from prose nor changes content that already parses.
    """

    if (
        task_output_contract is None
        or str(getattr(task_output_contract.artifact_type, "value", task_output_contract.artifact_type)) != "code"
    ):
        return None
    final_step = next(
        (step for step in plan.steps if step.output_key == plan.final_output_from),
        None,
    )
    if final_step is None or final_step.operation_kind != OperationKind.WRITE_FILE:
        return None
    binding = final_step.input_bindings.get("content")
    if (
        not isinstance(binding, Mapping)
        or set(binding) != {"from_step", "output_key"}
        or binding.get("from_step") != producer_step.step_id
        or binding.get("output_key") != producer_step.output_key
    ):
        return None
    path_binding = final_step.input_bindings.get("path")
    if (
        not isinstance(path_binding, Mapping)
        or set(path_binding) != {"literal"}
        or PurePosixPath(str(path_binding.get("literal") or "")).suffix.lower() != ".py"
    ):
        return None
    try:
        ast.parse(content)
        return None
    except SyntaxError:
        pass
    match = re.fullmatch(
        r"[ \t\r\n]*```(?:python|py)[ \t]*\r?\n(?P<body>.*?)\r?\n```[ \t\r\n]*",
        content,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if match is None or not match.group("body").strip():
        return None
    body = match.group("body") + "\n"
    try:
        ast.parse(body)
    except SyntaxError:
        return None
    return body


def _apply_direct_final_python_fence_conversion(
    result: ExecutionResult,
    *,
    plan: ResourceApplicationPlan,
    producer_step: ResourceApplicationStep,
    task_output_contract: SubtaskOutputContract | None,
) -> None:
    if not result.is_success:
        return
    converted = _unwrap_direct_final_python_fence(
        plan=plan,
        producer_step=producer_step,
        content=result.output_data,
        task_output_contract=task_output_contract,
    )
    if converted is None:
        return
    result.cost_metric["deterministic_output_conversion"] = {
        "kind": "single_python_fence_unwrap",
        "source_sha256": hashlib.sha256(result.output_data.encode("utf-8")).hexdigest(),
        "target_sha256": hashlib.sha256(converted.encode("utf-8")).hexdigest(),
    }
    result.output_data = converted


# ---------------------------------------------
# Prompt Management
# ---------------------------------------------

_PROMPT_DIR = os.path.join(os.path.dirname(__file__), "prompts")


def _load_prompt(filename: str) -> str:
    path = os.path.join(_PROMPT_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"[Orchestrator] Prompt file missing: {path}")
        return ""


_EVALUATOR_TEMPLATE: str = _load_prompt("evaluator_system.txt")


@dataclass
class RuntimeArtifactRecord:
    """Current-run file artifact registered for tool-safe handoff."""
    path: str
    artifact_type: str
    origin: str
    aliases: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RuntimeArtifactRegistry:
    """Runtime-only registry for files produced during this pipeline run."""
    by_task: Dict[str, RuntimeArtifactRecord] = field(default_factory=dict)
    by_step: Dict[str, RuntimeArtifactRecord] = field(default_factory=dict)
    source_overlays: Dict[str, RuntimeArtifactRecord] = field(default_factory=dict)
    validation_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    input_file_handles: Dict[str, ArtifactHandle] = field(default_factory=dict)
    external_handles: Dict[str, ArtifactHandle] = field(default_factory=dict)


class WorkspaceHandleResolver:
    """Thin compatibility helper for current-run handle resolution."""

    def __init__(self, orchestrator: Any):
        self.orchestrator = orchestrator

    def registry_artifact_handles(self, depends_on: Optional[Sequence[str]] = None) -> List[ArtifactHandle]:
        return self.orchestrator._registry_artifact_handles(depends_on)

    def input_file_handles(self, resolved_files: Sequence[ResolvedLocalFileProfile]) -> List[ArtifactHandle]:
        return self.orchestrator._input_file_handles(resolved_files)

    def validation_result_handles(self, depends_on: Optional[Sequence[str]] = None) -> List[ArtifactHandle]:
        return self.orchestrator._validation_result_handles(depends_on)

    def resolve_handle(
        self,
        handle_id: str,
        expected_kinds: Optional[Set[str]] = None,
        expected_artifact_type: Optional[str] = None,
        expected_path_kind: Optional[str] = None,
    ) -> Tuple[bool, str, str, Optional[ArtifactHandle]]:
        return self.orchestrator.resolve_artifact_handle(
            handle_id,
            expected_kinds=expected_kinds,
            expected_artifact_type=expected_artifact_type,
            expected_path_kind=expected_path_kind,
        )

    def resolve_current_run_logical_path(
        self,
        path: str,
        expected_kinds: Optional[Set[str]] = None,
        expected_artifact_type: Optional[str] = None,
    ) -> Tuple[bool, str, str, Optional[ArtifactHandle]]:
        return self.orchestrator._current_run_handle_for_logical_path(
            path,
            expected_kinds=expected_kinds,
            expected_artifact_type=expected_artifact_type,
        )


class SourceOverlayWriter:
    """Thin helper that keeps source/test overlay writes explicit and localized."""

    def __init__(self, orchestrator: Any):
        self.orchestrator = orchestrator

    def register_task_overlays(
        self,
        task_id: str,
        task: Dict[str, Any],
        artifact_type: str,
        text: str,
        output_contract: Dict[str, Any],
        record: RuntimeArtifactRecord,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        return self.orchestrator._register_source_overlays(
            task_id,
            task,
            artifact_type,
            text,
            output_contract,
            record,
        )

    def register_step_overlays(
        self,
        task_id: str,
        task_view: Dict[str, Any],
        step: ResourceApplicationStep,
        output_key: str,
        text: str,
        artifact_type: str,
        output_contract: Dict[str, Any],
        record: RuntimeArtifactRecord,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        return self.orchestrator._register_step_source_overlays(
            task_id,
            task_view,
            step,
            output_key,
            text,
            artifact_type,
            output_contract,
            record,
        )


class PytestTargetResolver:
    """Thin helper documenting that pytest targets must resolve to current-run handles."""

    def __init__(self, orchestrator: Any):
        self.orchestrator = orchestrator

    def prepare_validation_bindings(
        self,
        task_id: str,
        step: ResourceApplicationStep,
        selected: List[TypedResourceRef],
        resource_index: Dict[str, dict],
        desc: str,
        context_data: str,
        step_outputs: Dict[str, str],
    ) -> Tuple[bool, str, str, Dict[str, str]]:
        return self.orchestrator._prepare_validation_bindings(
            task_id,
            step,
            selected,
            resource_index,
            desc,
            context_data,
            step_outputs,
        )


class RuntimeReadinessChecker:
    """Thin helper for dependency/runtime readiness decisions before tool execution."""

    def __init__(self, orchestrator: Any):
        self.orchestrator = orchestrator

    def dependency_result(self, ref: TypedResourceRef, resource_index: Dict[str, dict]):
        return self.orchestrator._dependency_result_for_ref(ref, resource_index)


_DEFAULT_ARTIFACT_EXT = {
    "code": ".py",
    "json": ".json",
    "csv": ".csv",
    "markdown": ".md",
    "plaintext": ".txt",
}


_ORDINARY_TOOL_SEMANTIC_KINDS = frozenset(
    {
        OperationKind.READ_FILE,
        OperationKind.WRITE_FILE,
        OperationKind.EDIT_FILE,
        OperationKind.LIST_DIRECTORY,
        OperationKind.SEARCH_FILES,
        OperationKind.INSPECT_METADATA,
        OperationKind.CREATE_DIRECTORY,
        OperationKind.MOVE_PATH,
        OperationKind.INSPECT_VERSION_CONTROL,
        OperationKind.MUTATE_VERSION_CONTROL,
        OperationKind.EXTRACT_DOCUMENT,
        OperationKind.CONVERT_FORMAT,
        OperationKind.PARSE_DATA,
        OperationKind.QUERY_DATA,
        OperationKind.TRANSFORM_DATA,
        OperationKind.ANALYZE_DATA,
        OperationKind.ANALYZE_CODE,
        OperationKind.LINT_CODE,
        OperationKind.FORMAT_CODE,
        OperationKind.AUDIT_SECURITY,
        OperationKind.QUERY_API,
        OperationKind.SEARCH_KNOWLEDGE,
        OperationKind.LOOKUP_REFERENCE,
        OperationKind.RESOLVE_NETWORK,
        OperationKind.FETCH_LIVE_DATA,
        OperationKind.ANALYZE_TEXT,
        OperationKind.COMPUTE_MATH,
        OperationKind.GENERATE_MEDIA,
    }
)

_ORDINARY_TOOL_EXECUTION_KINDS = frozenset(
    set(_ORDINARY_TOOL_SEMANTIC_KINDS) | {OperationKind.RUN_TOOL}
)

_DIRECT_TOOL_EXECUTION_KINDS = frozenset(
    set(_ORDINARY_TOOL_EXECUTION_KINDS) | {OperationKind.INSPECT_INPUT}
)


def _read_only_network_tool_retry_allowed(
    request: ResourceCallRequest,
    result: ResourceCallResult,
) -> bool:
    """Permit one audited retry only for a failed, read-only HTTP operation."""

    failure = result.failure
    if (
        request.execution_context.attempt != 1
        or not request.execution_world.network_required
        or result.status != ResourceCallStatus.RESEARCH_FAILURE
        or failure is None
        or failure.failure_stage != "resource_execution"
        or failure.failure_code != "resource_process_failed"
    ):
        return False
    entrypoint = request.resource_definition.entrypoint(request.entrypoint_id)
    method_ports = [
        item for item in entrypoint.input_contract
        if str(item.get("name") or "") == "method"
    ]
    if len(method_ports) != 1 or method_ports[0].get("required") is not True:
        return False
    allowed_raw = method_ports[0].get("values")
    if not isinstance(allowed_raw, (list, tuple)):
        return False
    allowed = {str(value).upper() for value in allowed_raw}
    if not allowed or not allowed <= {"GET", "HEAD"}:
        return False
    return str(request.resolved_bindings.get("method") or "").upper() in allowed


# ---------------------------------------------
# Exceptions
# ---------------------------------------------

class PipelineExecutionError(Exception):
    """Raised when a critical node in the pipeline fails unrecoverably."""
    pass

class NodeUnrecoverableError(Exception):
    """Carry first cause and final ownership across the DAG boundary."""

    def __init__(
        self,
        failure: TerminalFailureEnvelope,
        *,
        terminal_failure: TerminalFailureEnvelope | None = None,
        recovery_outcomes: Sequence[Mapping[str, Any]] = (),
        causal_chain: Sequence[Mapping[str, Any]] = (),
    ) -> None:
        if not isinstance(failure, TerminalFailureEnvelope):
            raise TypeError("node_unrecoverable_requires_terminal_failure_envelope")
        resolved_terminal = terminal_failure or failure
        if not isinstance(resolved_terminal, TerminalFailureEnvelope):
            raise TypeError("node_unrecoverable_requires_terminal_failure_envelope")
        super().__init__(resolved_terminal.failure_code)
        self.primary_failure = failure
        self.terminal_failure = resolved_terminal
        # Backward-compatible alias: callers historically read the final owner.
        self.failure = resolved_terminal
        self.recovery_outcomes = tuple(dict(item) for item in recovery_outcomes)
        self.causal_chain = tuple(dict(item) for item in causal_chain)


# ---------------------------------------------
# Global Context (DAG Artifact Store)
# ---------------------------------------------

class GlobalContext:
    """
    In-memory artifact store keyed by task_id.
    Supports both targeted DAG dependency resolution and full-context dump.
    """

    def __init__(
        self,
        *,
        context_commit_store: ContextCommitStore | None = None,
        artifact_store: ArtifactLifecycleStore | None = None,
    ):
        self.artifacts: Dict[str, str] = {}
        self.context_commit_store = context_commit_store
        self.artifact_store = artifact_store
        self.committed_manifests: Dict[str, Any] = {}
        self.exact_artifact_handles: Dict[str, Dict[str, Any]] = {}
        self.legacy_unverified: Set[str] = set()
        if self.context_commit_store is not None and self.artifact_store is not None:
            for commit in self.context_commit_store.committed_artifacts:
                self.add_committed_artifact(commit)

    def add_result(self, task_id: str, output_data: str) -> None:
        """Legacy-only unverified insertion; formal snapshots never consume it."""
        self.artifacts[task_id] = output_data
        self.legacy_unverified.add(task_id)

    def add_committed_artifact(self, commit: Any) -> None:
        if self.artifact_store is None:
            raise RuntimeError("formal_context_artifact_store_missing")
        task_id = commit.artifact_revision.subtask_revision.subtask_id
        descriptor = getattr(commit, "artifact_v2", None)
        artifact_path = self.artifact_store.artifact_path(commit)
        self.exact_artifact_handles[task_id] = {
            "logical_locator": commit.logical_locator,
            "blob_locator": commit.blob_locator,
            "content_sha256": commit.content_sha256,
            "representation": (
                descriptor.representation.value if descriptor is not None else "file"
            ),
            "descriptor_sha256": (
                descriptor.descriptor_sha256 if descriptor is not None else None
            ),
            "committed_manifest_sha256": commit.committed_manifest_sha256,
        }
        if artifact_path.is_file():
            raw = self.artifact_store.read_bytes(commit)
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError:
                content = json.dumps(
                    {
                        "artifact_handle": self.exact_artifact_handles[task_id],
                        "media_type": commit.mime_type,
                        "byte_size": commit.byte_size,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
        else:
            content = json.dumps(
                {
                    "artifact_handle": self.exact_artifact_handles[task_id],
                    "members": (
                        [
                            item.model_dump(mode="json")
                            for item in descriptor.members
                        ]
                        if descriptor is not None
                        else []
                    ),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        self.artifacts[task_id] = content
        self.committed_manifests[task_id] = commit
        self.legacy_unverified.discard(task_id)

    def snapshot_for(self, consumer_revision: Any, declared_dependencies: Sequence[str]) -> Any:
        if self.context_commit_store is None:
            raise RuntimeError("formal_context_commit_store_missing")
        run_id = next(
            (
                item.artifact_revision.run_id
                for item in self.committed_manifests.values()
            ),
            "",
        )
        return self.context_commit_store.snapshot_for(
            consumer_revision=consumer_revision,
            run_id=run_id,
            declared_dependency_refs=declared_dependencies,
        )

    def committed_manifest_for(self, task_id: str) -> Any | None:
        return self.committed_manifests.get(task_id)

    def build_context(self, depends_on: List[str], max_length: int = 8000) -> str:
        """
        Assemble context from exact upstream dependencies only.
        This is the DAG-aware context builder; unrelated artifacts are excluded.
        """
        if not depends_on:
            return "No dependencies."

        parts = []
        for tid in depends_on:
            if tid in self.artifacts:
                parts.append(f"--- [Artifact: {tid}] ---\n{self.artifacts[tid]}\n")
            else:
                logger.warning(f"[Context] Dependency '{tid}' not found in artifact store")

        ctx = "\n".join(parts)
        if len(ctx) > max_length:
            ctx = ctx[-max_length:] + "\n\n... (truncated)"
        return ctx

    def build_full_context(self, max_length: int = 64000) -> str:
        """Concatenate all artifacts for final delivery report."""
        if not self.artifacts:
            return ""
        parts = [
            f"--- [Artifact: {tid}] ---\n{data}\n"
            for tid, data in self.artifacts.items()
        ]
        ctx = "\n".join(parts)
        if len(ctx) > max_length:
            ctx = ctx[-max_length:] + "\n\n... (truncated)"
        return ctx


from .budget_engine import GlobalBudgetManager

# ---------------------------------------------
# DAG Orchestrator
# ---------------------------------------------

def project_controller_session_execution_result(
    session_result: ControllerSessionResultV1,
) -> ExecutionResult:
    """Project the actual Controller result, retaining V2 terminal authority."""
    last_turn = session_result.turns[-1] if session_result.turns else None
    summary = session_result.summary
    v2 = isinstance(summary, ControllerSessionSummaryV2)
    terminal = summary.terminal_failure if v2 else None
    cause = session_result.terminal_failure
    failure_metadata = {}
    if v2:
        failure_metadata = {
            "failure_stage": terminal.failure_stage if terminal else None,
            "failure_code": terminal.failure_code if terminal else session_result.failure_code,
            "resource_call_id": terminal.resource_call_id if terminal else None,
            "controller_terminal_failure": terminal.model_dump(mode="json") if terminal else None,
            "resource_call_ids": list(dict.fromkeys((
                *summary.resource_call_ids,
                *(item.resource_call_id for item in summary.failed_tool_attempts
                  if item.resource_dispatched and item.resource_call_id),
            ))),
            "controller_evidence_incomplete": summary.evidence_incomplete,
        }
    recovery_diagnostic = getattr(session_result, "_recovery_diagnostic", None)
    recovery_execution_audit = getattr(session_result, "_recovery_execution_audit", None)
    return ExecutionResult(
        is_success=session_result.status == "success",
        output_data=session_result.output_data,
        error_log=(
            recovery_diagnostic
            if isinstance(recovery_diagnostic, str) and recovery_diagnostic
            else cause.failure_code if cause else session_result.failure_code
        ),
        cost_metric={
            **failure_metadata,
            **({"execution_audit": dict(recovery_execution_audit)}
               if isinstance(recovery_execution_audit, Mapping) else {}),
            **({"failure": cause.model_dump(mode="json"),
                "failure_stage": cause.failure_stage, "failure_code": cause.failure_code} if cause else {}),
            "latency_ms": session_result.summary.elapsed_ms,
            "failure_type": cause.failure_code if cause else session_result.failure_code,
            "failure_layer": (
                "none"
                if session_result.status == "success"
                else cause.responsibility if cause else "framework"
            ),
            "controller_session_protocol": session_result.protocol,
            "controller_session_result_sha256": session_result.result_sha256,
            "controller_session_spec_sha256": (
                session_result.controller_session_spec_sha256
            ),
            "controller_policy_sha256": (
                session_result.controller_policy_sha256
            ),
            "controller_input_snapshot_sha256": (
                session_result.input_snapshot_sha256
            ),
            "controller_session_summary": session_result.summary.model_dump(
                mode="json"
            ),
            "model_accounting_references": list(
                session_result.summary.model_accounting_references
            ),
            "model_accounting_reference": (
                last_turn.model_accounting_reference
                if last_turn is not None
                else None
            ),
            "transport_audit": (
                last_turn.transport_audit if last_turn is not None else None
            ),
        },
    )


def controller_step_delivery_requirements(
    *,
    expected_output_contract: Mapping[str, Any],
    task_output_contract: Optional[SubtaskOutputContract],
    is_final: bool,
    is_final_content_source: bool = False,
) -> Dict[str, Any]:
    """Bind final requirements to delivery or its unchanged content producer."""
    if is_final and is_final_content_source:
        raise ValueError("controller_delivery_scope_ambiguous")
    if (is_final or is_final_content_source) and task_output_contract is not None:
        produced_files = tuple(getattr(task_output_contract, "produced_files", ()) or ())
        criteria = list(task_output_contract.acceptance_criteria)
        for grounding_requirement in task_output_contract.grounding_requirements:
            if grounding_requirement not in criteria:
                criteria.append(str(grounding_requirement))
        if task_output_contract.grounding_requirements:
            criteria.append(
                "For each factual value, verify the exact supporting source span "
                "matches the requested entity type and scope; do not take a word "
                "from an adjacent entry or substitute an action for a name."
            )
        authoritative_contract = {
            "artifact_type": task_output_contract.artifact_type.value,
            "content_kind": task_output_contract.content_kind,
            **({"output_extension": task_output_contract.output_extension}
               if task_output_contract.output_extension else {}),
            **({"required_content": list(task_output_contract.required_content)}
               if task_output_contract.required_content else {}),
            **({"schema_hint": task_output_contract.json_schema}
               if task_output_contract.json_schema is not None else {}),
            **({"interface_contract": dict(task_output_contract.interface_contract)}
               if task_output_contract.interface_contract else {}),
            **({"syntax_validator": task_output_contract.syntax_validator}
               if task_output_contract.syntax_validator else {}),
            **({"produced_files": [
                item.model_dump(mode="json")
                for item in produced_files
            ]} if produced_files else {}),
        }
        if (
            task_output_contract.artifact_type.value == "json"
            and task_output_contract.json_schema is None
            and expected_output_contract.get("artifact_type") == "json"
            and isinstance(expected_output_contract.get("schema_hint"), Mapping)
        ):
            authoritative_contract["schema_hint"] = copy.deepcopy(
                dict(expected_output_contract["schema_hint"])
            )
        return {
            "delivery_scope": (
                "task_final" if is_final else "final_content_source"
            ),
            **({
                "external_acquisition_mode": "if_needed",
                "conditional_evidence_instruction": (
                    "Inspect supplied material first. Acquire external evidence only for "
                    "requirements it does not establish. For a conditional criterion, cite "
                    "the successful inspection showing either that existing evidence suffices "
                    "or that the missing evidence was acquired. Do not claim that an unknown "
                    "condition is false. Keep explicit source verification and output formats."
                ),
            } if getattr(task_output_contract, "external_acquisition_mode", None) == "if_needed" else {}),
            **({
                "external_discovery_mode": "if_needed",
                "source_discovery_instruction": (
                    "Use supplied source locators directly when sufficient. Discover missing "
                    "sources if needed; preserve explicit searches, actual source inspection "
                    "and verification, and the exact final format."
                ),
            } if getattr(task_output_contract, "external_discovery_mode", None) == "if_needed" else {}),
            "mandatory_acceptance_criteria": criteria,
            "mandatory_acceptance_examples": [
                probe.model_dump(mode="json")
                for probe in task_output_contract.acceptance_probes
            ],
            "mandatory_final_format": {
                "artifact_type": task_output_contract.artifact_type.value,
                "content_kind": task_output_contract.content_kind,
                **({"output_extension": task_output_contract.output_extension}
                   if task_output_contract.output_extension else {}),
                **({"syntax_validator": task_output_contract.syntax_validator}
                   if task_output_contract.syntax_validator else {}),
                **({"interface_contract": dict(task_output_contract.interface_contract)}
                   if task_output_contract.interface_contract else {}),
                **({"produced_files": [
                    item.model_dump(mode="json")
                    for item in produced_files
                ]} if produced_files else {}),
            },
            "mandatory_output_files": [
                item.model_dump(mode="json")
                for item in produced_files
                if item.required
            ],
            "authoritative_final_output_contract": authoritative_contract,
        }
    return {
        "delivery_scope": "step_output",
        "mandatory_acceptance_criteria": (
            [str(expected_output_contract["description"])]
            if expected_output_contract.get("description") else []
        ),
        "mandatory_acceptance_examples": [],
        "mandatory_final_format": {
            key: expected_output_contract[key]
            for key in ("artifact_type", "content_kind", "output_extension")
            if expected_output_contract.get(key) is not None
        },
    }


def controller_generation_token_cap(
    *,
    configured_max_tokens: int,
    delivery_requirements: Mapping[str, Any],
    tool_enabled: bool,
) -> int:
    """Bound short validated values without constraining open-ended artifacts."""

    configured = max(256, int(configured_max_tokens))
    if tool_enabled:
        return configured
    if str(delivery_requirements.get("delivery_scope") or "") not in {
        "task_final",
        "final_content_source",
    }:
        return configured
    final_format = delivery_requirements.get("mandatory_final_format")
    if not isinstance(final_format, Mapping):
        return configured
    artifact_type = str(final_format.get("artifact_type") or "").casefold()
    content_kind = str(final_format.get("content_kind") or "").casefold()
    syntax_validator = str(final_format.get("syntax_validator") or "").strip()
    code_like = artifact_type in {
        "code",
        "python",
        "python_script",
        "python_source",
        "source_code",
    }
    if content_kind == "value" and syntax_validator and not code_like:
        return min(configured, 8192)
    return configured


class DAGOrchestrator:
    """
    Drives the S-GAR execution pipeline.
    """

    def _execution_state(self) -> _ExecutionLocalState:
        state_var = self.__dict__.get("_execution_state_var")
        if state_var is None:
            return self.__dict__.get(
                "_legacy_execution_state",
                _ExecutionLocalState(),
            )
        return state_var.get()

    def _execution_state_context_var(self) -> ContextVar[_ExecutionLocalState]:
        state_var = self.__dict__.get("_execution_state_var")
        if state_var is None:
            state_var = ContextVar(
                f"sgar_execution_state_{id(self)}",
                default=self.__dict__.get(
                    "_legacy_execution_state",
                    _ExecutionLocalState(),
                ),
            )
            self.__dict__["_execution_state_var"] = state_var
        return state_var

    def _replace_execution_state(self, **updates: Any) -> None:
        state = replace(self._execution_state(), **updates)
        state_var = self.__dict__.get("_execution_state_var")
        if state_var is None:
            self.__dict__["_legacy_execution_state"] = state
        else:
            state_var.set(state)

    @property
    def _active_sandbox_scope(self) -> Dict[str, Any]:
        return self._execution_state().sandbox_scope

    @_active_sandbox_scope.setter
    def _active_sandbox_scope(self, value: Mapping[str, Any] | None) -> None:
        self._replace_execution_state(sandbox_scope=dict(value or {}))

    @property
    def _active_runtime_path_map(self) -> RuntimePathMap | None:
        return self._execution_state().runtime_path_map

    @_active_runtime_path_map.setter
    def _active_runtime_path_map(self, value: RuntimePathMap | None) -> None:
        self._replace_execution_state(runtime_path_map=value)

    @property
    def _active_model_payload_guard(
        self,
    ) -> Callable[[Mapping[str, Any]], None] | None:
        return self._execution_state().model_payload_guard

    @_active_model_payload_guard.setter
    def _active_model_payload_guard(
        self,
        value: Callable[[Mapping[str, Any]], None] | None,
    ) -> None:
        self._replace_execution_state(model_payload_guard=value)

    @property
    def _active_allow_semantic_normalization(self) -> bool:
        return self._execution_state().allow_semantic_normalization

    @_active_allow_semantic_normalization.setter
    def _active_allow_semantic_normalization(self, value: bool) -> None:
        self._replace_execution_state(allow_semantic_normalization=bool(value))

    @property
    def _active_sealed_entrypoints(self) -> Dict[str, str]:
        return self._execution_state().sealed_entrypoints

    @_active_sealed_entrypoints.setter
    def _active_sealed_entrypoints(self, value: Mapping[str, str] | None) -> None:
        self._replace_execution_state(sealed_entrypoints=dict(value or {}))

    @property
    def _formal_execution_active(self) -> bool:
        return self._execution_state().formal_execution_active

    @_formal_execution_active.setter
    def _formal_execution_active(self, value: bool) -> None:
        self._replace_execution_state(formal_execution_active=bool(value))

    def __init__(
        self,
        llm_api_key: str,
        llm_base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o",
        budget_manager: GlobalBudgetManager = None,
        cost_ledger: RunCostLedger = None,
        execution_ledger: RunExecutionLedger = None,
        artifact_dir: str = "execution_artifacts",
        max_same_bundle_repair_attempts: int = 0,
        allow_plan_recovery: bool = False,
        max_eval_retries: int = 1,
        eval_profile_threshold_chars: int = 12000,
        execution_strictness: str = "balanced",
        trace_path: Optional[str] = None,
        control_model_chain: Optional[Sequence[str]] = None,
        control_model_metadata: Optional[Dict[str, Any]] = None,
        environment_profile: Optional[EnvironmentProfile] = None,
        execution_max_retries: int = 3,
        execution_max_tokens: int = 8192,
        execution_allow_streaming: bool = True,
        execution_temperature: float = 0.5,
        runtime_preparation_enabled: bool = False,
        runtime_preparation_trace_path: Optional[str] = None,
        runtime_preparation_run_id: str = "",
        runtime_preparer: Optional[Any] = None,
        artifact_lifecycle_coordinator: Optional[ArtifactLifecycleCoordinator] = None,
        artifact_store: Optional[ArtifactLifecycleStore] = None,
        context_commit_store: Optional[ContextCommitStore] = None,
        explicit_input_only: bool = False,
        network_policy_mode: str = "disabled",
        task_invocation: Optional[TaskInvocation] = None,
        async_model_transport: Optional[AsyncModelTransportPort] = None,
        execution_substrate: Optional[Any] = None,
        execution_substrate_mode: str = "default",
        # Direct embedders retain the historical evaluator gate unless the
        # formal entry point explicitly supplies its config mode.
        evaluation_mode: str = "active",
    ):
        self._execution_state_var: ContextVar[_ExecutionLocalState] = ContextVar(
            f"sgar_execution_state_{id(self)}",
            default=_ExecutionLocalState(),
        )
        self.artifact_lifecycle_coordinator = artifact_lifecycle_coordinator
        self.artifact_store = artifact_store
        self.context_commit_store = context_commit_store
        self.explicit_input_only = bool(explicit_input_only)
        self.task_invocation = task_invocation
        if network_policy_mode not in {"disabled", "declared"}:
            raise ValueError("network_policy_mode_invalid")
        self.network_policy_mode = network_policy_mode
        from .runtime_abstraction import require_execution_substrate
        self.execution_substrate = require_execution_substrate(
            execution_substrate, mode=execution_substrate_mode
        )
        self.execution_substrate_mode = str(execution_substrate_mode)
        self.evaluation_mode = normalize_evaluation_mode(evaluation_mode)
        self.context = GlobalContext(
            context_commit_store=context_commit_store,
            artifact_store=artifact_store,
        )
        self.llm_api_key = llm_api_key
        self.llm_base_url = llm_base_url
        import httpx
        self.model = model
        if isinstance(control_model_chain, str):
            self.control_model_chain = [control_model_chain]
        else:
            chain = list(control_model_chain or [model])
            self.control_model_chain = []
            seen_models: Set[str] = set()
            for model_id in chain:
                model_text = str(model_id or "").strip()
                if not model_text or model_text in seen_models:
                    continue
                seen_models.add(model_text)
                self.control_model_chain.append(model_text)
            if not self.control_model_chain:
                self.control_model_chain = [model]
        self.control_model_metadata = control_model_metadata or {}
        if async_model_transport is None:
            sdk_client = AsyncOpenAI(
                http_client=direct_async_http_client(),
                api_key=llm_api_key,
                base_url=llm_base_url,
                timeout=httpx.Timeout(120.0, connect=20.0, read=120.0, write=20.0),
                max_retries=0,
            )
            async_model_transport = AsyncModelTransportPort.from_sdk_client(
                client=sdk_client,
                endpoint_identity=ProviderEndpointIdentity.create(
                    provider="openai_compatible",
                    base_url=llm_base_url,
                    credential_environment_variable="LLM_API_KEY",
                    timeout_seconds=120.0,
                ),
            )
        self.async_model_transport = require_async_model_transport(
            async_model_transport
        )
        self.budget_manager = budget_manager
        self.cost_ledger = cost_ledger
        self.execution_ledger = execution_ledger
        self.output_realizer = OutputRealizer()
        self._formal_trace_required = bool(
            execution_ledger is not None and explicit_input_only
        )
        self.resource_runtime = (
            ResourceRuntime(ledger=execution_ledger)
            if execution_ledger is not None
            else None
        )
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        self.skill_package_loader = SkillPackageLoader(
            self.project_root,
            max_injected_bytes=DEFAULT_MAX_SKILL_BYTES,
        )
        self.artifact_dir = artifact_dir
        self.max_same_bundle_repair_attempts = max(0, max_same_bundle_repair_attempts)
        self.allow_plan_recovery = bool(allow_plan_recovery)
        self.max_eval_retries = max(0, max_eval_retries)
        self.eval_profile_threshold_chars = max(1000, eval_profile_threshold_chars)
        try:
            self.execution_strictness = ExecutionStrictness(execution_strictness)
        except ValueError:
            logger.warning(
                "[Orchestrator] Unknown execution_strictness={} ; falling back to balanced.",
                execution_strictness,
            )
            self.execution_strictness = ExecutionStrictness.BALANCED
        self.trace_path = trace_path or os.path.join(artifact_dir, "trace.jsonl")
        self.carried_over_artifacts: Dict[str, str] = {}
        self._formal_final_runtime_records: Dict[
            str, tuple[RuntimeArtifactRecord, ...]
        ] = {}
        self._formal_final_task_id = ""
        self.artifact_registry = RuntimeArtifactRegistry()
        self._known_local_file_paths: Set[str] = set()
        self.environment_profile = environment_profile or scan_environment()
        self.execution_max_retries = max(1, int(execution_max_retries))
        self.execution_max_tokens = max(256, int(execution_max_tokens))
        self.execution_allow_streaming = bool(execution_allow_streaming)
        self.execution_temperature = float(execution_temperature)
        self.runtime_preparation_enabled = bool(runtime_preparation_enabled)
        self.runtime_preparation_trace_path = (
            runtime_preparation_trace_path
            or os.path.join(os.path.dirname(self.trace_path), "runtime_preparation.jsonl")
        )
        self.runtime_preparation_run_id = str(
            runtime_preparation_run_id or os.path.basename(os.path.abspath(self.artifact_dir))
        )
        self.runtime_preparer = runtime_preparer
        self._runtime_preparation_event_counter = 0
        self.dependency_gate = DependencyGate(self.environment_profile, project_root=self.project_root)
        self.workspace_handle_resolver = WorkspaceHandleResolver(self)
        self.source_overlay_writer = SourceOverlayWriter(self)
        self.pytest_target_resolver = PytestTargetResolver(self)
        self.runtime_readiness_checker = RuntimeReadinessChecker(self)
        self._append_trace(
            "environment_profile",
            self.environment_profile.public_projection(),
        )
        self._append_trace(
            "control_model_chain",
            {
                "stage": "orchestrator_startup",
                "active_control_model": self.model,
                "control_model_chain": list(self.control_model_chain),
                "control_model_metadata": self.control_model_metadata,
            },
        )
        self._append_trace(
            "runtime_preparation_policy",
            {
                "enabled": self.runtime_preparation_enabled,
                "mode": "explicit_pre_execution",
                "inline_install": False,
                "post_failure_auto_heal": False,
                "trace_locator": os.path.basename(
                    self.runtime_preparation_trace_path
                ),
                "run_id": self.runtime_preparation_run_id,
            },
        )
        self._append_runtime_preparation_trace(
            {
                "event_type": "runtime_preparation_policy",
                "run_id": self.runtime_preparation_run_id,
                "enabled": self.runtime_preparation_enabled,
                "mode": "explicit_pre_execution",
                "inline_install": False,
                "post_failure_auto_heal": False,
                "execution_metrics": {"attempt_count": 0, "cost_usd": 0.0},
            }
        )

    def _workspace_root(self) -> str:
        return self.project_root

    def _normalize_path_text(self, value: Any) -> str:
        return str(value or "").strip().strip("'\"`")

    def _to_workspace_relative_path(self, path: str) -> Optional[str]:
        """Return a forward-slash workspace-relative path for workspace-local files."""
        if not path:
            return None
        host_path = self._resolve_candidate_path(path)
        root = os.path.abspath(self._workspace_root())
        try:
            if os.path.commonpath([root, os.path.abspath(host_path)]) != root:
                return None
        except ValueError:
            return None
        return os.path.relpath(host_path, root).replace("\\", "/")

    def _to_tool_path(self, path: str) -> str:
        """Return the path namespace used by the active executor.

        A formal sandbox runs with a Case-specific writable working directory,
        so workspace-relative values would be resolved beneath that directory
        rather than beneath the project mount.  In that mode every
        workspace-local path is therefore absolute in the container namespace.
        Legacy host execution retains the historical workspace-relative form.
        """
        # External benchmark execution keeps framework resource sources on the
        # host only long enough for the substrate to stage them into the task
        # container.  Returning the private host locator here is intentional:
        # it is never sent to the container; JsonLinesExecutionSubstrate
        # rewrites/stages it before issuing exec_argv.  Task-state paths such
        # as /app/... remain unchanged.
        if self.execution_substrate is not None and os.path.isabs(str(path)):
            return str(path)
        path_map = getattr(self, "_active_runtime_path_map", None)
        if path_map is not None:
            return path_map.to_runtime_scalar(str(path))
        rel = self._to_workspace_relative_path(path)
        if rel is None:
            return str(path)
        if getattr(self, "_active_sandbox_scope", None):
            return "/app/" + rel.lstrip("/")
        return rel

    def _to_tool_binding_value(self, value: str) -> str:
        text = str(value)
        if "://" in text and not text.startswith("file://"):
            return text
        path_map = getattr(self, "_active_runtime_path_map", None)
        if path_map is not None:
            task_path = getattr(getattr(self, "execution_substrate", None), "task_path", None)
            if callable(task_path) and text.startswith("/") and "\\" not in text:
                try:
                    return path_map.host_to_runtime(text)
                except PathNamespaceError:
                    return task_path(text)
            return path_map.to_runtime_scalar(text)
        if self._content_looks_like_path(text):
            resolved = self._resolve_candidate_path(text)
            if self._to_workspace_relative_path(resolved) is not None:
                return self._to_tool_path(resolved)
        return text

    def _normalize_tool_path(self, value: Any) -> Optional[str]:
        """Normalize one host/container/workspace path into a tool-safe path."""
        if self._is_absent_binding_value(value):
            return None
        text = self._stringify_binding_value(value).strip()
        resolved = self._resolve_candidate_path(text)
        if not self._is_workspace_path(resolved):
            return None
        return self._to_tool_path(resolved)

    def _normalize_cli_arg_list(
        self,
        value: Any,
        resource_index: Optional[Dict[str, dict]] = None,
        step_outputs: Optional[Dict[str, str]] = None,
    ) -> List[str]:
        """Resolve list contracts without ever invoking shell tokenization."""

        resolved = resolve_binding(
            value,
            {"name": "args", "kind": "list"},
            self._binding_source_registry(resource_index or {}),
            step_outputs or {},
            path_mapper=self._to_tool_binding_value,
        )
        return list(resolved) if isinstance(resolved, list) else [resolved]

    def _normalize_single_file_target(self, value: Any) -> Optional[str]:
        """Resolve and validate a single workspace-local file target."""
        tool_path = self._normalize_tool_path(value)
        if tool_path is None:
            return None
        host_path = self._resolve_candidate_path(tool_path)
        if not os.path.isfile(host_path):
            return None
        return tool_path

    def _system_tool_adapter_path(self, resource_id: str) -> Optional[str]:
        """Return a system-owned adapter for resource tools that need compatibility shims."""
        if bool(getattr(self, "_formal_execution_active", False)):
            raise RuntimeError("formal_system_tool_adapter_forbidden")
        adapters = {
            "tool.pytest_runner.v1": os.path.join(
                os.path.dirname(__file__),
                "tool_adapters",
                "pytest_runner_adapter.py",
            ),
        }
        return adapters.get(resource_id)

    def _is_workspace_path(self, path: str) -> bool:
        return self._to_workspace_relative_path(path) is not None

    def _is_current_run_artifact_path(self, path: str) -> bool:
        if self.execution_substrate is not None:
            # Imported task-container bytes live in this run's artifact
            # directory. Validate their registered host copy without routing
            # the task path through the legacy host resolver.
            try:
                resolved_path = Path(path).resolve(strict=True)
                run_root = Path(self.artifact_dir).resolve(strict=True)
                resolved_path.relative_to(run_root)
            except (OSError, ValueError):
                return False
            return any(
                Path(record.path).resolve() == resolved_path
                for record in (
                    list(self.artifact_registry.by_step.values())
                    + list(self.artifact_registry.by_task.values())
                    + list(self.artifact_registry.source_overlays.values())
                )
            )
        resolved = os.path.abspath(self._resolve_candidate_path(path))
        for record in (
            list(self.artifact_registry.by_step.values())
            + list(self.artifact_registry.by_task.values())
            + list(self.artifact_registry.source_overlays.values())
        ):
            paths = [record.path, *record.aliases]
            if any(os.path.abspath(candidate) == resolved for candidate in paths):
                return True
        return False

    def _artifact_record_for_path(self, path: str) -> Optional[RuntimeArtifactRecord]:
        resolved = os.path.abspath(self._resolve_candidate_path(path))
        for record in (
            list(self.artifact_registry.by_step.values())
            + list(self.artifact_registry.by_task.values())
            + list(self.artifact_registry.source_overlays.values())
        ):
            paths = [record.path, *record.aliases]
            if any(os.path.abspath(candidate) == resolved for candidate in paths):
                return record
        return None

    def _path_provenance(self, path: str) -> str:
        resolved = os.path.abspath(self._resolve_candidate_path(path))
        for record in self.artifact_registry.source_overlays.values():
            if os.path.abspath(record.path) == resolved:
                return "source_overlay"
            if any(os.path.abspath(alias) == resolved for alias in record.aliases):
                return "source_overlay"
        for record in self.artifact_registry.by_step.values():
            if os.path.abspath(record.path) == resolved:
                return "step_artifact" if record.origin == "step_output" else record.origin
            if any(os.path.abspath(alias) == resolved for alias in record.aliases):
                return "contract_alias"
        for record in self.artifact_registry.by_task.values():
            if os.path.abspath(record.path) == resolved:
                return "task_final"
            if any(os.path.abspath(alias) == resolved for alias in record.aliases):
                return "contract_alias"
        rel = self._to_workspace_relative_path(resolved)
        if rel and rel.replace("\\", "/").lower().startswith("bench_cases/"):
            return "resolved_input_file"
        return "text_mention"

    def _current_run_artifact_paths(self, artifact_types: Optional[Set[str]] = None) -> List[str]:
        paths: List[str] = []
        seen: Set[str] = set()
        records = (
            list(self.artifact_registry.source_overlays.values())
            + list(self.artifact_registry.by_step.values())
            + list(self.artifact_registry.by_task.values())
        )
        for record in records:
            if artifact_types and str(record.artifact_type).lower() not in artifact_types:
                continue
            for candidate in [record.path, *record.aliases]:
                if not candidate:
                    continue
                resolved = os.path.abspath(candidate)
                if resolved in seen or not os.path.isfile(resolved):
                    continue
                seen.add(resolved)
                paths.append(resolved)
        return paths

    def _handle_slug(self, value: Any) -> str:
        slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip().replace("\\", "/"))
        return slug.strip("_")[:120] or "artifact"

    def _source_overlay_kind(self, logical_path: str) -> str:
        normalized = str(logical_path or "").replace("\\", "/").lower()
        base = os.path.basename(normalized)
        if "/tests/" in normalized or base.startswith("test_") or base.endswith("_test.py"):
            return "test_overlay"
        return "source_overlay"

    def _artifact_handle_for_record(
        self,
        handle_id: str,
        kind: str,
        record: RuntimeArtifactRecord,
        producer_task: Optional[str] = None,
        producer_step: Optional[str] = None,
        logical_path: Optional[str] = None,
        host_path: Optional[str] = None,
        validation_status: str = "not_run",
    ) -> ArtifactHandle:
        raw_host = host_path or record.path
        resolved_host: Optional[str] = None
        if raw_host:
            is_registered_run_artifact = False
            if (
                bool(getattr(self, "_formal_execution_active", False))
                or self.execution_substrate is not None
            ):
                candidate = Path(raw_host).resolve()
                artifact_root = Path(self.artifact_dir).resolve()
                try:
                    candidate.relative_to(artifact_root)
                    is_registered_run_artifact = candidate.exists()
                except ValueError:
                    pass
            resolved_host = (
                str(Path(raw_host).resolve())
                if is_registered_run_artifact
                else os.path.abspath(self._resolve_candidate_path(raw_host))
            )
        registered_tool_path: Optional[str] = None
        if self.execution_substrate is not None:
            metadata_tool_path = str(record.metadata.get("tool_path") or "").strip()
            if metadata_tool_path:
                task_path = getattr(self.execution_substrate, "task_path", None)
                registered_tool_path = (
                    str(task_path(metadata_tool_path))
                    if callable(task_path)
                    else metadata_tool_path
                )
        return ArtifactHandle(
            handle_id=handle_id,
            kind=kind,
            producer_task=producer_task or record.metadata.get("source_task"),
            producer_step=producer_step or record.metadata.get("source_step"),
            logical_path=logical_path,
            host_path=resolved_host,
            tool_path=(
                registered_tool_path
                or self._artifact_handle_tool_path(resolved_host)
                if resolved_host
                else None
            ),
            artifact_type=str(record.artifact_type or "plaintext"),
            validation_status=validation_status,
            current_run=kind != "input_file",
            provenance={"execution_contract": copy.deepcopy(record.metadata["execution_contract"])}
                if "execution_contract" in record.metadata else {},
        )

    def _artifact_handle_tool_path(self, path: str) -> str:
        """Return the runtime identity for a registered artifact.

        Formal Tool execution deliberately masks the run artifact root and
        exposes only that step's private writable directory. Inline Tool output
        is materialized by the host-side artifact adapter after the executor
        returns, so it is not part of the completed Tool container's writable
        mount. It becomes a read-only checkpoint input for declared downstream
        steps instead. Use the same content-addressed alias that
        ``_formal_step_sandbox_scope`` publishes for those dependencies.

        No arbitrary out-of-scope path is accepted: the fallback is limited to
        existing current-run artifacts beneath ``artifact_dir`` while formal
        execution is active. Every other namespace mismatch remains
        fail-closed.
        """

        try:
            return self._to_tool_path(str(path))
        except PathNamespaceError:
            if not bool(getattr(self, "_formal_execution_active", False)):
                raise
            resolved = Path(path).resolve()
            artifact_root = Path(self.artifact_dir).resolve()
            try:
                resolved.relative_to(artifact_root)
            except ValueError:
                raise
            if not resolved.exists():
                raise
            digest = path_sha256(resolved)
            return f"/app/checkpoints/{digest[:16]}/{resolved.name}"

    def _registry_artifact_handles(
        self,
        depends_on: Optional[Sequence[str]] = None,
    ) -> List[ArtifactHandle]:
        allowed_tasks = {str(item) for item in (depends_on or []) if str(item)}
        handles: List[ArtifactHandle] = []

        # A verified external snapshot can also be stored as a committed blob.
        # Receipts retain distinct provenance, but identical bytes at the same
        # task locator must expose one private host identity to RuntimePathMap.
        # Prefer committed storage; never merge differing content revisions.
        external_hosts: Dict[Tuple[str, str], str] = {}
        if self.execution_substrate is not None:
            records = (
                *self.artifact_registry.source_overlays.values(),
                *self.artifact_registry.by_step.values(),
                *self.artifact_registry.by_task.values(),
            )
            for record in records:
                locator = str(record.metadata.get("tool_path") or "")
                digest = str(record.metadata.get("content_sha256") or "")
                if record.origin != "external_tool_output" or not locator or not re.fullmatch(r"[0-9a-f]{64}", digest):
                    continue
                key = (locator, digest)
                if key not in external_hosts or record.metadata.get("committed_manifest_sha256"):
                    external_hosts[key] = record.path

        def external_host(record: RuntimeArtifactRecord) -> Optional[str]:
            if record.origin != "external_tool_output":
                return None
            return external_hosts.get((
                str(record.metadata.get("tool_path") or ""),
                str(record.metadata.get("content_sha256") or ""),
            ))

        def include_task(task_id: Optional[str]) -> bool:
            if not allowed_tasks:
                return True
            return bool(task_id and task_id in allowed_tasks)

        for logical_path, record in self.artifact_registry.source_overlays.items():
            producer_task = record.metadata.get("source_task")
            if not include_task(producer_task):
                continue
            kind = self._source_overlay_kind(str(logical_path or record.metadata.get("original_workspace_path") or ""))
            handle_id = f"{producer_task or 'run'}:{kind}:{self._handle_slug(logical_path)}"
            handles.append(
                self._artifact_handle_for_record(
                    handle_id,
                    kind,
                    record,
                    producer_task=producer_task,
                    producer_step=record.metadata.get("source_step"),
                    logical_path=str(logical_path or record.metadata.get("original_workspace_path") or ""),
                    host_path=external_host(record),
                )
            )

        for task_id, record in self.artifact_registry.by_task.items():
            if not include_task(task_id):
                continue
            handles.append(
                self._artifact_handle_for_record(
                    f"{task_id}:task_final",
                    "task_final",
                    record,
                    producer_task=task_id,
                    logical_path=self._artifact_handle_tool_path(record.path),
                    host_path=external_host(record),
                )
            )
            for alias in record.aliases:
                if not os.path.isfile(alias):
                    continue
                alias_record = RuntimeArtifactRecord(
                    path=alias,
                    artifact_type=record.artifact_type,
                    origin="contract_alias",
                    metadata=dict(record.metadata),
                )
                logical = self._artifact_handle_tool_path(alias)
                handles.append(
                    self._artifact_handle_for_record(
                        f"{task_id}:contract_alias:{self._handle_slug(logical)}",
                        "contract_alias",
                        alias_record,
                        producer_task=task_id,
                        logical_path=logical,
                        host_path=external_host(alias_record),
                    )
                )

        for key, record in self.artifact_registry.by_step.items():
            parts = key.split(":", 2)
            producer_task = parts[0] if parts else record.metadata.get("source_task")
            producer_step = parts[1] if len(parts) > 1 else record.metadata.get("source_step")
            if not include_task(producer_task):
                continue
            kind = "tool_output" if record.origin == "tool_output" else "step_artifact"
            if record.origin == "derived_final_artifact":
                kind = "step_artifact"
            handles.append(
                self._artifact_handle_for_record(
                    f"{producer_task}:{producer_step}:{self._handle_slug(parts[2] if len(parts) > 2 else record.path)}",
                    kind,
                    record,
                    producer_task=producer_task,
                    producer_step=producer_step,
                    logical_path=self._artifact_handle_tool_path(record.path),
                    host_path=external_host(record),
                )
            )

        unique: List[ArtifactHandle] = []
        seen: Set[str] = set()
        for handle in handles:
            if handle.handle_id in seen:
                continue
            seen.add(handle.handle_id)
            unique.append(handle)
        return unique

    def _input_file_handles(self, resolved_files: Sequence[ResolvedLocalFileProfile]) -> List[ArtifactHandle]:
        handles: List[ArtifactHandle] = []
        seen: Set[str] = set()
        for item in resolved_files:
            if item.role != "input":
                continue
            host_path = self._resolve_candidate_path(item.path)
            if not os.path.isfile(host_path) or not self._is_workspace_path(host_path):
                continue
            logical = self._to_workspace_relative_path(host_path) or self._to_tool_path(host_path)
            handle_id = f"input_file:{self._handle_slug(logical)}"
            if handle_id in seen:
                continue
            seen.add(handle_id)
            handles.append(
                ArtifactHandle(
                    handle_id=handle_id,
                    kind="input_file",
                    producer_task=None,
                    producer_step=None,
                    logical_path=logical,
                    host_path=os.path.abspath(host_path),
                    tool_path=self._to_tool_path(host_path),
                    artifact_type=self._artifact_type_from_path_hint(host_path, fallback="plaintext"),
                    validation_status="not_run",
                    current_run=False,
                )
            )
        return handles

    def _register_input_file_handles(self, handles: Sequence[ArtifactHandle]) -> None:
        """Publish resolved file/directory inputs to the preflight registry.

        The historical registry field is retained for compatibility, but its
        values now include every explicit input handle.  Path-kind validation
        still happens when the handle is resolved for a manifest contract.
        """
        for handle in handles:
            if handle.kind not in {"input_file", "input_directory", "input_path"}:
                continue
            self.artifact_registry.input_file_handles[handle.handle_id] = handle

    def register_input_handles(
        self,
        handles: Sequence[ArtifactHandle | Dict[str, Any]],
    ) -> List[ArtifactHandle]:
        """Register an explicit compiler-visible input handle set for execution."""

        normalized = [
            item if isinstance(item, ArtifactHandle) else ArtifactHandle.model_validate(item)
            for item in handles
        ]
        self._register_input_file_handles(normalized)
        return normalized

    def _resource_runtime_sandbox_scope(self) -> Dict[str, Any]:
        """Build the generic production scope from registered public handles.

        The scope exposes only framework runtime roots, exact public inputs, and
        the current run's writable artifact root.  It never consults a resource
        ID, query, parameter name, or capability description.
        """

        project = Path(self.project_root).resolve()
        writable = Path(self.artifact_dir).resolve()
        if not writable.is_dir():
            raise RuntimeError("resource_runtime_writable_root_missing")
        try:
            writable.relative_to(project)
            writable_is_project_local = True
        except ValueError:
            # ``main.py --run-dir`` intentionally supports a fresh run workspace
            # outside the source checkout (for example on a dedicated data
            # volume).  Expose that exact directory through a fixed runtime
            # alias; never derive or mount its parent volume.
            writable_is_project_local = False

        def route(
            path: Path,
            *,
            path_kind: str = "directory",
            runtime_path: str | None = None,
            allow_external: bool = False,
        ) -> Dict[str, Any]:
            resolved = path.resolve()
            try:
                relative = resolved.relative_to(project)
            except ValueError as exc:
                if not allow_external or not runtime_path:
                    raise RuntimeError("resource_runtime_scope_path_outside_project") from exc
                relative = None
            return {
                "host_path": str(resolved),
                "runtime_path": (
                    runtime_path
                    or "/app/" + (relative.as_posix() if relative is not None else "")
                ),
                "path_kind": path_kind,
            }

        writable_route = route(
            writable,
            runtime_path=(None if writable_is_project_local else "/app/run"),
            allow_external=True,
        )

        runtime_paths = (
            project / "sgar_mvp",
            project / "Pool" / "resources" / "tools",
        )
        if any(not path.is_dir() for path in runtime_paths):
            raise RuntimeError("resource_runtime_root_missing")
        runtime_roots = [route(path) for path in runtime_paths]

        public_inputs: List[Dict[str, Any]] = []
        seen_public: Set[str] = set()
        for handle in self.artifact_registry.input_file_handles.values():
            if not handle.host_path:
                continue
            path = Path(handle.host_path).resolve()
            key = os.path.normcase(str(path))
            if key in seen_public:
                continue
            if not path.exists():
                raise RuntimeError("resource_runtime_public_input_missing")
            try:
                path.relative_to(project)
                public_input_is_project_local = True
            except ValueError:
                public_input_is_project_local = False
                try:
                    path.relative_to(writable)
                except ValueError as exc:
                    raise RuntimeError(
                        "resource_runtime_public_input_outside_allowed_roots"
                    ) from exc
                if not handle.tool_path:
                    raise RuntimeError("resource_runtime_public_input_alias_missing")
            seen_public.add(key)
            public = route(
                path,
                path_kind="directory" if path.is_dir() else "file",
                runtime_path=(str(handle.tool_path) if handle.tool_path else None),
                allow_external=not public_input_is_project_local,
            )
            public["sha256"] = path_sha256(path)
            public_inputs.append(public)

        masks: List[Dict[str, Any]] = []
        seen_masks: Set[str] = set()

        def add_mask(path: Path) -> None:
            if not path.is_dir():
                return
            key = os.path.normcase(str(path.resolve()))
            if key in seen_masks:
                return
            seen_masks.add(key)
            masks.append(route(path))

        # Narrow the broad Python package root before remounting the exact run
        # directory read-write.
        for runtime_path in runtime_paths:
            try:
                writable.relative_to(runtime_path.resolve())
            except ValueError:
                continue
            add_mask(writable)
        # Public inputs located below a runtime root must first hide the broader
        # inherited view; inputs outside runtime roots are not visible until the
        # exact read-only public mount is added.
        for public in public_inputs:
            public_path = Path(public["host_path"])
            for runtime_path in runtime_paths:
                try:
                    public_path.relative_to(runtime_path.resolve())
                except ValueError:
                    continue
                add_mask(public_path if public_path.is_dir() else public_path.parent)

        metadata_layout = inspect_internal_metadata_layout(project)
        scope = {
            "protocol": "sgar-sandbox-scope/v1",
            "runtime_roots": runtime_roots,
            "public_inputs": public_inputs,
            "writable_root": writable_route,
            "working_directory": writable_route["runtime_path"],
            "masked_roots": masks,
            "hidden_roots": [route(path) for path in metadata_layout.hidden_roots],
            "allow_legacy_shell": False,
        }
        validate_internal_metadata_scope(metadata_layout, scope)
        # Constructing the exact map is also the generic route preflight.
        # Public aliases become authoritative only after this passes.
        RuntimePathMap.from_scope(scope)
        return scope

    def _formal_step_sandbox_scope(
        self,
        *,
        step: Any,
        execution_context: ResourceExecutionContext,
    ) -> Dict[str, Any]:
        """Create one isolated writable mount and exact read-only dependencies."""

        if self.execution_substrate is not None:
            scope = self.execution_substrate.step_scope(
                step_id=str(step.step_id),
                depends_on=tuple(getattr(step, "depends_on", ()) or ()),
                attempt=int(getattr(execution_context, "attempt", 1)),
            )
            # External task substrates stage public snapshots through RPC, not
            # host mounts.  The framework still needs exact private
            # host-to-logical aliases while resolving artifact_handle bindings.
            # Without them a valid handle is rejected before Tool dispatch.
            if self.task_invocation is not None:
                for descriptor in self.task_invocation.public_inputs:
                    handle = self.artifact_registry.input_file_handles.get(
                        descriptor.handle_id
                    )
                    if handle is None or not handle.host_path:
                        raise RuntimeError("external_public_input_handle_missing")
                    scope["public_inputs"].append({
                        "host_path": str(handle.host_path),
                        "runtime_path": descriptor.runtime_path,
                        "path_kind": descriptor.path_kind,
                        "sha256": descriptor.content_sha256,
                    })
            # A final artifact produced through the external substrate has two
            # exact identities: a private committed/readback file used for
            # provenance and a persistent task-workspace path used by later
            # Tools.  Preserve that registered pair in the private path map so
            # an artifact_handle can cross subtask boundaries without exposing
            # the control-host path or inventing a checkpoint location.  This
            # is mapping evidence only; authorization still comes from the
            # handle registry and the sealed DAG edge.
            existing_routes = {
                (
                    os.path.normcase(str(Path(item["host_path"]).resolve())),
                    str(item["runtime_path"]),
                )
                for item in scope["public_inputs"]
            }
            registry = getattr(self, "artifact_registry", None)
            has_complete_registry = all(
                hasattr(registry, name)
                for name in ("source_overlays", "by_task", "by_step")
            )
            registered_handles = (
                self._registry_artifact_handles()
                if has_complete_registry else ()
            )
            for handle in registered_handles:
                if not handle.current_run or not handle.host_path or not handle.tool_path:
                    continue
                runtime_path = str(handle.tool_path)
                if runtime_path != "/app" and not runtime_path.startswith(("/app/", "/tmp/")):
                    continue
                host_path = Path(handle.host_path).resolve()
                if not host_path.exists():
                    raise RuntimeError("external_registered_artifact_missing")
                route_key = (os.path.normcase(str(host_path)), runtime_path)
                if route_key in existing_routes:
                    continue
                scope["public_inputs"].append({
                    "host_path": str(host_path),
                    "runtime_path": runtime_path,
                    "path_kind": "directory" if host_path.is_dir() else "file",
                })
                existing_routes.add(route_key)
            RuntimePathMap.from_scope(scope)
            return scope
        base = copy.deepcopy(self._resource_runtime_sandbox_scope())
        project = Path(self.project_root).resolve()
        artifact_root = Path(self.artifact_dir).resolve()
        root_mapper = RuntimePathMap.from_scope(base)
        artifact_runtime_path = root_mapper.host_to_runtime(str(artifact_root))
        masked_hosts = {
            os.path.normcase(str(Path(item["host_path"]).resolve()))
            for item in base["masked_roots"]
        }
        if os.path.normcase(str(artifact_root)) not in masked_hosts:
            base["masked_roots"].append(
                {
                    "host_path": str(artifact_root),
                    "runtime_path": artifact_runtime_path,
                    "path_kind": "directory",
                }
            )

        public_hosts = {
            os.path.normcase(str(Path(item["host_path"]).resolve()))
            for item in base["public_inputs"]
        }
        dependency_steps = set(getattr(step, "depends_on", ()) or ())
        for handle in self._all_artifact_handles():
            if not handle.current_run or not handle.host_path:
                continue
            if handle.producer_step not in dependency_steps:
                continue
            path = Path(handle.host_path).resolve()
            if not path.exists():
                raise RuntimeError("formal_checkpoint_artifact_missing")
            try:
                path.relative_to(artifact_root)
            except ValueError as exc:
                raise RuntimeError(
                    "formal_checkpoint_artifact_outside_run_workspace"
                ) from exc
            key = os.path.normcase(str(path))
            if key in public_hosts:
                continue
            digest = path_sha256(path)
            base["public_inputs"].append(
                {
                    "host_path": str(path),
                    "runtime_path": (
                        f"/app/checkpoints/{digest[:16]}/{path.name}"
                    ),
                    "path_kind": "directory" if path.is_dir() else "file",
                    "sha256": digest,
                }
            )
            public_hosts.add(key)

        safe_step = hashlib.sha256(str(step.step_id).encode("utf-8")).hexdigest()[:16]
        attempt_root = (
            artifact_root
            / "work"
            / f"subtask-{execution_context.subtask_revision}"
            / f"plan-{max(0, execution_context.attempt - 1)}"
            / safe_step
            / "attempt-1"
        )
        attempt_root.mkdir(parents=True, exist_ok=False)
        attempt_runtime_path = root_mapper.host_to_runtime(str(attempt_root))
        base["writable_root"] = {
            "host_path": str(attempt_root),
            "runtime_path": attempt_runtime_path,
            "path_kind": "directory",
        }
        base["working_directory"] = attempt_runtime_path
        return base

    def _validation_result_handles(
        self,
        depends_on: Optional[Sequence[str]] = None,
    ) -> List[ArtifactHandle]:
        allowed_tasks = {str(item) for item in (depends_on or []) if str(item)}
        handles: List[ArtifactHandle] = []
        for key, payload in self.artifact_registry.validation_results.items():
            parts = key.split(":", 2)
            producer_task = parts[0] if parts else payload.get("producer_task")
            if allowed_tasks and producer_task not in allowed_tasks:
                continue
            status = str(payload.get("validation_status") or payload.get("status") or "not_run")
            handles.append(
                ArtifactHandle(
                    handle_id=f"{producer_task}:{parts[1] if len(parts) > 1 else 'validation'}:{self._handle_slug(parts[2] if len(parts) > 2 else key)}",
                    kind="validation_result",
                    producer_task=producer_task,
                    producer_step=parts[1] if len(parts) > 1 else payload.get("producer_step"),
                    logical_path=payload.get("logical_path"),
                    host_path=None,
                    tool_path=None,
                    artifact_type="json",
                    validation_status=status,
                    current_run=True,
                )
            )
        return handles

    def _all_artifact_handles(self) -> List[ArtifactHandle]:
        return (
            self._registry_artifact_handles()
            + list(self.artifact_registry.input_file_handles.values())
            + list(self.artifact_registry.external_handles.values())
            + self._validation_result_handles()
        )

    def resolve_artifact_handle(
        self,
        handle_id: str,
        expected_kinds: Optional[Set[str]] = None,
        expected_artifact_type: Optional[str] = None,
        expected_path_kind: Optional[str] = None,
    ) -> Tuple[bool, str, str, Optional[ArtifactHandle]]:
        normalized_handle_id = str(handle_id or "").strip()
        handles = self._all_artifact_handles()
        matches = [
            handle for handle in handles if handle.handle_id == normalized_handle_id
        ]
        if not matches and normalized_handle_id.startswith("artifact:"):
            unqualified_handle_id = normalized_handle_id.removeprefix("artifact:")
            matches = [
                handle
                for handle in handles
                if handle.handle_id == unqualified_handle_id
            ]
        if not matches:
            return (
                False,
                "artifact_handle_missing",
                f"Artifact handle not found: {normalized_handle_id}",
                None,
            )
        if len(matches) > 1:
            return (
                False,
                "artifact_handle_ambiguous",
                f"Artifact handle is ambiguous: {normalized_handle_id}",
                None,
            )
        handle = matches[0]
        if expected_kinds and handle.kind not in expected_kinds:
            return (
                False,
                "artifact_handle_kind_mismatch",
                f"Handle {handle_id} has kind {handle.kind}, expected one of {sorted(expected_kinds)}.",
                None,
            )
        if expected_artifact_type and handle.artifact_type != expected_artifact_type:
            return (
                False,
                "artifact_type_mismatch",
                f"Handle {handle_id} has artifact_type {handle.artifact_type}, expected {expected_artifact_type}.",
                None,
            )
        if handle.kind != "validation_result" and not (
            self.execution_substrate is not None and handle.tool_path
        ):
            if not handle.host_path or not os.path.exists(handle.host_path):
                return False, "artifact_handle_missing", f"Handle {handle_id} target path is missing.", None
            if expected_path_kind:
                actual_path_kind = "file_path" if os.path.isfile(handle.host_path) else "directory_path" if os.path.isdir(handle.host_path) else "path"
                normalized_expected = self._contract_kind({"kind": expected_path_kind, "name": ""})
                if normalized_expected != "path" and actual_path_kind != normalized_expected:
                    return (
                        False,
                        "artifact_path_type_mismatch",
                        f"Handle {handle_id} target is {actual_path_kind}, expected {normalized_expected}.",
                        None,
                    )
        return True, "", "", handle

    def _current_run_handle_for_logical_path(
        self,
        path: str,
        expected_kinds: Optional[Set[str]] = None,
        expected_artifact_type: Optional[str] = None,
    ) -> Tuple[bool, str, str, Optional[ArtifactHandle]]:
        logical = (self._to_workspace_relative_path(path) or str(path or "")).replace("\\", "/").strip()
        if not logical:
            return False, "artifact_handle_missing", "No logical path provided.", None
        candidates: List[ArtifactHandle] = []
        for handle in self._all_artifact_handles():
            if not handle.current_run or handle.kind == "validation_result":
                continue
            if expected_kinds and handle.kind not in expected_kinds:
                continue
            if expected_artifact_type and handle.artifact_type != expected_artifact_type:
                continue
            handle_paths = {
                str(handle.logical_path or "").replace("\\", "/"),
                str(handle.tool_path or "").replace("\\", "/"),
            }
            if handle.host_path:
                handle_paths.add((self._to_workspace_relative_path(handle.host_path) or "").replace("\\", "/"))
            if logical in handle_paths:
                candidates.append(handle)
        if not candidates:
            return (
                False,
                "raw_path_requires_input_check",
                f"Raw workspace path requires an artifact handle or explicit input-check: {logical}",
                None,
            )
        unique = {candidate.handle_id: candidate for candidate in candidates}
        if len(unique) > 1:
            return False, "artifact_handle_ambiguous", f"Multiple current-run handles match {logical}.", None
        return True, "", "", next(iter(unique.values()))

    def _is_preexisting_bench_test_path(self, path: str) -> bool:
        rel = self._to_workspace_relative_path(path)
        if rel is None:
            return False
        normalized = rel.replace("\\", "/").lower()
        return normalized.startswith("bench_cases/") and "/tests/" in normalized and normalized.endswith(".py")

    def _is_pytest_file_path(self, path: str) -> bool:
        normalized = str(path or "").replace("\\", "/").lower()
        return normalized.endswith(".py") and (
            "/tests/" in normalized
            or os.path.basename(normalized).startswith("test_")
            or os.path.basename(normalized).endswith("_test.py")
        )

    def _preferred_pytest_target_for_record(self, record: RuntimeArtifactRecord) -> str:
        candidates = list(record.aliases) + [record.path]
        source_overlay_paths = {
            os.path.abspath(item.path)
            for item in self.artifact_registry.source_overlays.values()
            if item.path
        }
        for candidate in candidates:
            resolved = os.path.abspath(self._resolve_candidate_path(candidate))
            if (
                resolved in source_overlay_paths
                and os.path.isfile(resolved)
                and self._is_pytest_file_path(resolved)
            ):
                return resolved
        for candidate in candidates:
            resolved = os.path.abspath(self._resolve_candidate_path(candidate))
            if os.path.isfile(resolved) and self._is_pytest_file_path(resolved):
                return resolved
        return record.path

    def _append_trace(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Append one JSONL trace event for later training-data reconstruction."""
        try:
            os.makedirs(os.path.dirname(self.trace_path), exist_ok=True)
            event = {"event_type": event_type, **payload}
            if self._formal_trace_required:
                append_formal_jsonl(self.trace_path, event)
                return
            line = json.dumps(event, ensure_ascii=False, default=str)
            # Lightweight self-check: every trace entry must stay parseable JSONL.
            json.loads(line)
            with open(self.trace_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception as exc:
            if self._formal_trace_required:
                raise
            logger.debug("[Trace] Failed to append {}: {}", event_type, exc)

    @staticmethod
    def _runtime_record_payload(value: Any) -> Dict[str, Any]:
        if value is None:
            return {}
        projector = getattr(value, "public_projection", None)
        if callable(projector):
            payload = projector()
            return payload if isinstance(payload, dict) else {"value": payload}
        if isinstance(value, BaseException):
            return {
                "exception_type": type(value).__name__,
                "message_sha256": canonical_sha256(str(value)),
            }
        dumper = getattr(value, "model_dump", None)
        if callable(dumper):
            payload = dumper()
            return payload if isinstance(payload, dict) else {"value": payload}
        if isinstance(value, dict):
            return dict(value)
        raw = getattr(value, "__dict__", None)
        if isinstance(raw, dict):
            return {
                str(key): item
                for key, item in raw.items()
                if not str(key).startswith("_")
            }
        return {"value": str(value)}

    @staticmethod
    def _manifest_python_package_names(raw_manifest: Optional[Dict[str, Any]]) -> Set[str]:
        requirements = (raw_manifest or {}).get("runtime_requirements") or {}
        names: Set[str] = set()
        for item in requirements.get("python_packages") or []:
            name = (
                str(item.get("name") or item.get("package") or "").strip()
                if isinstance(item, dict)
                else str(item or "").strip()
            )
            if name:
                names.add(name)
        return names

    def _append_runtime_preparation_trace(self, payload: Dict[str, Any]) -> None:
        """Write the explicit system preparation phase to its own audit log."""
        try:
            trace_dir = os.path.dirname(os.path.abspath(self.runtime_preparation_trace_path))
            os.makedirs(trace_dir, exist_ok=True)
            if self._formal_trace_required:
                append_formal_jsonl(self.runtime_preparation_trace_path, payload)
                return
            line = json.dumps(payload, ensure_ascii=False, default=str)
            json.loads(line)
            with open(self.runtime_preparation_trace_path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except Exception as exc:
            if self.runtime_preparation_enabled:
                from .runtime_preparation import RuntimePreparationError

                raise RuntimePreparationError(
                    "Formal runtime preparation trace could not be written.",
                    failure_type="runtime_trace_write_failed",
                    failure_layer="framework_implementation",
                    details={
                        "trace_locator": os.path.basename(
                            self.runtime_preparation_trace_path
                        )
                    },
                ) from exc
            logger.debug("[RuntimePreparationTrace] Failed to append event: {}", exc)

    def _snapshot_runtime_lock(self, handle_payload: Dict[str, Any]) -> str:
        """Copy a resolved overlay lock into the immutable experiment run.

        The cache is intentionally Git-ignored and can be evicted.  A run must
        therefore carry the exact resolved lock that produced its derived image
        so the dependency decision remains auditable after cache cleanup.
        """

        packages = handle_payload.get("packages") or []
        image_id = str(handle_payload.get("image_id") or "").lower()
        base_image_id = str(handle_payload.get("base_image_id") or "").lower()
        if not packages or not image_id or image_id == base_image_id:
            return ""
        lock_path = os.path.abspath(str(handle_payload.get("lock_path") or ""))
        expected_hash = str(handle_payload.get("lock_hash") or "").lower()
        if not lock_path or not os.path.isfile(lock_path):
            from .runtime_preparation import RuntimePreparationError

            raise RuntimePreparationError(
                "Prepared runtime lock is missing before run snapshotting.",
                failure_type="runtime_cache_corrupt",
                failure_layer="framework_implementation",
            )
        try:
            with open(lock_path, "r", encoding="utf-8") as source:
                payload = json.load(source)
            canonical = json.dumps(
                payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        except (OSError, ValueError, TypeError) as exc:
            from .runtime_preparation import RuntimePreparationError

            raise RuntimePreparationError(
                "Prepared runtime lock cannot be parsed for run snapshotting.",
                failure_type="runtime_cache_corrupt",
                failure_layer="framework_implementation",
            ) from exc
        actual_hash = "sha256:" + hashlib.sha256(canonical).hexdigest()
        if actual_hash != expected_hash:
            from .runtime_preparation import RuntimePreparationError

            raise RuntimePreparationError(
                "Prepared runtime lock changed before run snapshotting.",
                failure_type="runtime_cache_corrupt",
                failure_layer="framework_implementation",
                details={"expected_lock_hash": expected_hash, "actual_lock_hash": actual_hash},
            )
        trace_dir = os.path.dirname(os.path.abspath(self.runtime_preparation_trace_path))
        snapshot_dir = os.path.join(trace_dir, "runtime_locks")
        os.makedirs(snapshot_dir, exist_ok=True)
        destination = os.path.join(
            snapshot_dir, f"{expected_hash.removeprefix('sha256:')}.runtime.lock.json"
        )
        if not os.path.isfile(destination):
            temporary = f"{destination}.{os.getpid()}.{random.randrange(1 << 30):08x}.tmp"
            try:
                with open(temporary, "w", encoding="utf-8") as target:
                    json.dump(payload, target, ensure_ascii=False, indent=2)
                os.replace(temporary, destination)
            finally:
                if os.path.exists(temporary):
                    os.remove(temporary)
        return destination

    def _runtime_preparer_instance(self):
        if self.execution_substrate is not None:
            raise RuntimeError("UNBOUND_RUNTIME_PATH:legacy_runtime_preparation")
        if self.runtime_preparer is None:
            from .runtime_preparation import RuntimePreparer

            self.runtime_preparer = RuntimePreparer(project_root=self.project_root)
        return self.runtime_preparer

    def _runtime_preparation_layer(
        self,
        failure_type: str,
        *,
        source_kind: str = "system",
        phase: str = "manifest",
        has_manifest_dependencies: bool = False,
        has_artifact_dependencies: bool = False,
        transient: bool = False,
    ) -> str:
        """Map preparation failures without contaminating research Gap layers."""

        normalized = str(failure_type or "").strip().lower()
        source = str(source_kind or "system").strip().lower()
        if transient or normalized in {
            "runtime_preparation_lock_timeout",
            "runtime_provisioning_timeout",
            "runtime_provisioning_unavailable",
            "runtime_provisioning_infrastructure_failure",
            "runtime_registry_unavailable",
            "runtime_image_pull_failed",
            "runtime_daemon_unavailable",
            "runtime_warmup_timeout",
        }:
            return "infrastructure"
        if normalized in {
            "resource_manifest_incomplete",
            "dependency_integrity_failure",
            "runtime_dependency_policy_denied",
            "runtime_provisioning_config_invalid",
            "runtime_base_lock_invalid",
            "runtime_image_inspect_invalid",
            "runtime_base_image_mismatch",
            "runtime_base_inventory_invalid",
            "runtime_dependency_resolver_invalid",
            "runtime_preparation_disabled",
            "runtime_build_disallowed",
            "runtime_preparation_internal_error",
            "runtime_cache_corrupt",
            "runtime_handle_delivery_error",
            "runtime_verification_protocol_error",
            "runtime_trace_write_failed",
            "runtime_environment_missing",
            "runtime_environment_invalid",
            "legacy_inline_install_forbidden",
        }:
            return "framework_implementation"
        if normalized in {
            "runtime_dependency_spec_invalid",
            "runtime_dependency_spec_unsafe",
        } and source == "system":
            return "framework_implementation"
        if normalized == "runtime_dependency_conflict":
            if has_manifest_dependencies and has_artifact_dependencies:
                return "plan_composition"
            if has_artifact_dependencies or source == "generated-artifact":
                return "task_success"
            if has_manifest_dependencies or source == "manifest":
                return "resource_executability"
            return "plan_composition"
        if source == "generated-artifact" or (
            phase in {"artifact", "side_artifact"} and has_artifact_dependencies
        ):
            return "task_success"
        if source == "manifest" or has_manifest_dependencies:
            return "resource_executability"
        return self._failure_layer_for_type(normalized)

    @staticmethod
    def _runtime_responsibility_for_layer(failure_layer: str) -> str:
        normalized = str(failure_layer or "").strip().lower()
        if normalized in {"framework", "framework_implementation"}:
            return "framework"
        if normalized == "infrastructure":
            return "infrastructure"
        if normalized in {"budget", "budget_control", "experimental_control"}:
            return "budget"
        return "research"

    def _normalize_runtime_preparation_failure(
        self,
        raw_failure: Any,
        *,
        phase: str,
        has_manifest_dependencies: bool = False,
        has_artifact_dependencies: bool = False,
        default_reason: str = "Runtime preparation failed.",
    ) -> Dict[str, Any]:
        """Normalize every preparation producer through one ownership boundary.

        Diagnostics are preserved, but neither ``reason`` nor exception text is
        inspected to decide responsibility.
        """

        payload = self._runtime_record_payload(raw_failure)
        failure_type = str(
            payload.get("failure_type")
            or getattr(raw_failure, "failure_type", "")
            or "runtime_preparation_internal_error"
        )
        source_kind = str(
            payload.get("source_kind")
            or getattr(raw_failure, "source_kind", "")
            or "system"
        )
        transient = bool(
            payload.get("transient", getattr(raw_failure, "transient", False))
        )
        failure_layer = str(
            payload.get("failure_layer")
            or getattr(raw_failure, "failure_layer", "")
        )
        if transient:
            # A transient provisioning failure occurs before resource execution,
            # even when the dependency source is a manifest or generated artifact.
            failure_layer = "infrastructure"
        elif not failure_layer or failure_layer == "runtime_preparation":
            failure_layer = self._runtime_preparation_layer(
                failure_type,
                source_kind=source_kind,
                phase=phase,
                has_manifest_dependencies=has_manifest_dependencies,
                has_artifact_dependencies=has_artifact_dependencies,
                transient=False,
            )
        responsibility = self._runtime_responsibility_for_layer(failure_layer)
        diagnostic = (
            str(raw_failure)
            if isinstance(raw_failure, BaseException)
            else default_reason
        )
        reason = str(
            payload.get("failure_reason")
            or payload.get("reason")
            or payload.get("message")
            or diagnostic
        )
        return {
            "failure_type": failure_type,
            "failure_layer": failure_layer,
            "failure_reason": reason,
            "source_kind": source_kind,
            "transient": transient,
            "failure_stage": "runtime_preparation",
            "responsibility": responsibility,
            # This envelope is emitted only after runtime preparation has
            # returned terminally.  ``transient`` remains diagnostic; the fixed
            # pass framework will not issue another transparent runtime retry.
            "retryable": False,
            "transport_attempt": 0,
            "request_hash": "",
            "response_received": False,
        }

    async def _prepare_step_runtime(
        self,
        *,
        task_id: str,
        step_id: str,
        raw_manifest: Optional[Dict[str, Any]] = None,
        artifact_imports: Optional[Sequence[str]] = None,
        artifact_source: str = "",
        execution_network_required: bool = False,
        phase: str = "manifest",
    ) -> Tuple[Optional[Any], str, Optional[Dict[str, Any]]]:
        """Resolve one immutable runtime handle before starting an executor.

        Runtime preparation is system-owned rather than generated by the Plan
        Compiler.  When the feature is disabled the same path still resolves an
        explicit RC1 base handle, but never asks the preparer to build an overlay.
        """
        from .runtime_preparation import (
            RuntimePreparationRequest,
            collect_manifest_python_dependencies,
            dependencies_from_imports,
            merge_python_dependencies,
        )

        self._runtime_preparation_event_counter += 1
        # A full experiment constructs one orchestrator per case/mode while all
        # instances append to the same run-level trace.  Namespace the readable
        # per-instance counter so IDs never collide at ``0001`` across cases.
        instance_id = getattr(self, "_runtime_preparation_instance_id", "")
        if not instance_id:
            instance_id = uuid.uuid4().hex[:12]
            self._runtime_preparation_instance_id = instance_id
        event_id = (
            f"runtime-preparation-{instance_id}-"
            f"{self._runtime_preparation_event_counter:04d}"
        )

        # An externally owned task container is already the execution runtime.
        # It must not enter the legacy host-side overlay preparer: doing so
        # would attempt to resolve/install host packages for an action that is
        # ultimately dispatched through the task-container RPC substrate and
        # would also violate the external path boundary.  Keep an explicit
        # audit event, but let the external substrate own preparation and
        # image/package provenance.
        if self.execution_substrate is not None:
            self._append_runtime_preparation_trace(
                {
                    "event_type": "runtime_preparation",
                    "event_id": event_id,
                    "run_id": self.runtime_preparation_run_id,
                    "task_id": task_id,
                    "step_id": step_id,
                    "phase": phase,
                    "enabled": self.runtime_preparation_enabled,
                    "status": "skipped",
                    "skip_reason": "external_substrate_owns_task_runtime",
                    "execution_substrate_mode": self.execution_substrate_mode,
                    "execution_metrics": {
                        "attempt_count": 0,
                        "cost_usd": 0.0,
                    },
                }
            )
            return None, event_id, None

        manifest_dependencies = ()
        artifact_dependencies = ()
        try:
            if self.runtime_preparation_enabled:
                if raw_manifest:
                    manifest_dependencies = tuple(
                        collect_manifest_python_dependencies(raw_manifest)
                    )
                if artifact_imports:
                    preparer_policy = self._runtime_preparer_instance()
                    preparer_config = getattr(preparer_policy, "config", {})
                    artifact_dependencies = tuple(
                        dependencies_from_imports(
                            list(artifact_imports),
                            source=artifact_source or f"generated-artifact:{step_id}",
                            allow_same_name_fallback=bool(
                                preparer_config.get("allow_same_name_fallback", True)
                            ),
                        )
                    )
            dependencies = tuple(
                merge_python_dependencies(
                    manifest_dependencies,
                    artifact_dependencies,
                )
            )
        except Exception as exc:
            failure = self._normalize_runtime_preparation_failure(
                exc,
                phase=phase,
                has_manifest_dependencies=bool(manifest_dependencies),
                has_artifact_dependencies=bool(artifact_dependencies),
            )
            self._append_runtime_preparation_trace(
                {
                    "event_type": "runtime_preparation",
                    "event_id": event_id,
                    "run_id": self.runtime_preparation_run_id,
                    "task_id": task_id,
                    "step_id": step_id,
                    "phase": phase,
                    "enabled": self.runtime_preparation_enabled,
                    "status": "failed",
                    "execution_metrics": {
                        "attempt_count": 0,
                        "cost_usd": 0.0,
                    },
                    **failure,
                }
            )
            return None, event_id, failure

        request = RuntimePreparationRequest(
            python_requirements=dependencies,
            execution_network_required=bool(execution_network_required),
            run_id=self.runtime_preparation_run_id or task_id,
            step_id=step_id,
            allow_build=bool(self.runtime_preparation_enabled),
        )
        request_payload = self._runtime_record_payload(request)
        event_base = {
            "event_type": "runtime_preparation",
            "event_id": event_id,
            "run_id": self.runtime_preparation_run_id,
            "task_id": task_id,
            "step_id": step_id,
            "phase": phase,
            "enabled": self.runtime_preparation_enabled,
            "request": request_payload,
            "execution_metrics": {
                "attempt_count": 0,
                "cost_usd": 0.0,
            },
        }
        try:
            preparer = self._runtime_preparer_instance()
            if not dependencies:
                handle = await asyncio.to_thread(
                    preparer.base_handle,
                    execution_network_required=bool(execution_network_required),
                    run_id=self.runtime_preparation_run_id or task_id,
                    step_id=step_id,
                )
            else:
                handle = await preparer.prepare_async(request)
            handle_payload = self._runtime_record_payload(handle)
            status = str(handle_payload.get("status") or "prepared")
            if status.lower() in {"failed", "error", "blocked"}:
                failure = self._normalize_runtime_preparation_failure(
                    handle_payload,
                    phase=phase,
                    has_manifest_dependencies=bool(manifest_dependencies),
                    has_artifact_dependencies=bool(artifact_dependencies),
                    default_reason="Runtime preparation returned a failed handle.",
                )
                self._append_runtime_preparation_trace(
                    {**event_base, "status": "failed", "handle": handle_payload, **failure}
                )
                return None, event_id, failure
            if hasattr(handle, "preparation_event_id") and hasattr(
                handle, "preparation_event_ids"
            ):
                internal_event_id = str(getattr(handle, "preparation_event_id", "") or "")
                joined_ids = tuple(
                    dict.fromkeys(
                        [
                            event_id,
                            internal_event_id,
                            *list(getattr(handle, "preparation_event_ids", ()) or ()),
                        ]
                    )
                )
                handle = replace(
                    handle,
                    preparation_event_id=event_id,
                    preparation_event_ids=joined_ids,
                )
                handle_payload = self._runtime_record_payload(handle)
                if internal_event_id and internal_event_id != event_id:
                    handle_payload["preparer_internal_event_id"] = internal_event_id
            private_handle_payload = (
                handle.model_dump()
                if callable(getattr(handle, "model_dump", None))
                else handle_payload
            )
            lock_snapshot = self._snapshot_runtime_lock(private_handle_payload)
            if lock_snapshot:
                handle_payload["run_lock_snapshot_locator"] = os.path.basename(
                    lock_snapshot
                )
            self._append_runtime_preparation_trace(
                {**event_base, "status": "success", "handle": handle_payload}
            )
            return handle, event_id, None
        except Exception as exc:
            failure = self._normalize_runtime_preparation_failure(
                exc,
                phase=phase,
                has_manifest_dependencies=bool(manifest_dependencies),
                has_artifact_dependencies=bool(artifact_dependencies),
            )
            self._append_runtime_preparation_trace(
                {
                    **event_base,
                    "status": "failed",
                    "failure": self._runtime_record_payload(exc),
                    **failure,
                }
            )
            return None, event_id, failure

    @staticmethod
    def _runtime_preparation_failure_result(
        failure: Dict[str, Any],
        step_trace: Optional[List[Dict[str, Any]]] = None,
    ) -> ExecutionResult:
        failure_type = str(
            failure.get("failure_type") or "runtime_preparation_internal_error"
        )
        failure_reason = str(
            failure.get("failure_reason") or "Runtime preparation failed."
        )
        responsibility = str(failure.get("responsibility") or "framework")
        structured_failure = {
            "failure_stage": str(
                failure.get("failure_stage") or "runtime_preparation"
            ),
            "responsibility": responsibility,
            "failure_code": failure_type,
            "exception_type": "",
            "retryable": bool(failure.get("retryable", False)),
            "transport_attempt": int(failure.get("transport_attempt") or 0),
            "request_hash": str(failure.get("request_hash") or ""),
            "response_received": bool(failure.get("response_received", False)),
            "failure_type": failure_type,
        }
        return ExecutionResult(
            is_success=False,
            output_data="",
            error_log=failure_reason,
            cost_metric={
                # Preparation is a system phase and must not be counted as a
                # resource execution attempt in E1 statistics.
                "attempt_count": 0,
                "failure_type": failure_type,
                "failure_layer": str(
                    failure.get("failure_layer") or "framework_implementation"
                ),
                "failure": structured_failure,
                "runtime_preparation": dict(failure),
                **(
                    {"application_step_trace": step_trace}
                    if step_trace is not None
                    else {}
                ),
            },
        )

    def _pre_dispatch_failure_result(
        self,
        failure_type: str,
        reason: str,
        *,
        failure_stage: str,
        task_id: str,
        step_id: str,
        step_trace: Sequence[Mapping[str, Any]] = (),
        failure_layer: str | None = None,
    ) -> ExecutionResult:
        """Create the formal failure contract before any ResourceRuntime send."""

        failure_layer = failure_layer or self._failure_layer_for_type(failure_type)
        responsibility = self._runtime_responsibility_for_layer(failure_layer)
        execution_ledger = getattr(self, "execution_ledger", None)
        envelope = TerminalFailureEnvelope.create(
            responsibility=responsibility,
            failure_stage=failure_stage,
            failure_code=failure_type,
            retryable=False,
            response_received=False,
            run_id=str(getattr(execution_ledger, "run_id", "") or ""),
            subtask_id=task_id,
            step_id=step_id,
        )
        return ExecutionResult(
            is_success=False,
            output_data="",
            error_log=reason,
            cost_metric={
                "attempt_count": 0,
                "failure_type": failure_type,
                "failure_layer": failure_layer,
                "failure": envelope.model_dump(
                    mode="json",
                    exclude={"failure_sha256", "protocol"},
                ),
                "executability": "not_run",
                "task_success": False,
                "application_step_trace": [dict(item) for item in step_trace],
            },
        )

    @staticmethod
    def _derive_output_contract_from_task(task: Dict[str, Any]) -> SubtaskOutputContract:
        raw_contract = task.get("output_contract")
        if isinstance(raw_contract, dict):
            try:
                return SubtaskOutputContract.model_validate(raw_contract)
            except Exception as exc:
                logger.debug("[ContextPacket] Invalid output_contract for {}: {}", task.get("id"), exc)
        artifact_type = task.get("artifact_type", "plaintext")
        output_extension = task.get("output_extension", "")
        expected = str(task.get("expected_output") or task.get("description") or "")
        required = [line.strip()[:240] for line in expected.splitlines() if line.strip()][:6]
        grounding = [f"must use upstream artifact {dep}" for dep in task.get("depends_on", [])]
        return SubtaskOutputContract(
            artifact_type=artifact_type,
            output_extension=output_extension,
            required_content=required,
            grounding_requirements=grounding,
            acceptance_criteria=[
                "final artifact must satisfy expected_output",
                "must not contain N/A placeholders, inaccessible-path disclaimers, greetings, or reasoning traces",
            ],
        )

    @staticmethod
    def _extract_json_objects_from_text(text: str) -> List[Dict[str, Any]]:
        objects: List[Dict[str, Any]] = []
        if not text:
            return objects
        candidates = [text]
        candidates.extend(re.findall(r"\{.*?\}", text, flags=re.DOTALL))
        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
            except Exception:
                continue
            if isinstance(parsed, dict):
                objects.append(parsed)
        return objects

    def _extract_profile_files(self, artifact: str, result: Optional[ExecutionResult]) -> List[str]:
        files: List[str] = []
        seen: Set[str] = set()

        def add_file(value: Any) -> None:
            if not value:
                return
            path = str(value).strip()
            if "." not in path or path in seen:
                return
            seen.add(path)
            files.append(path)

        if result is not None:
            step_outputs = result.cost_metric.get("application_step_outputs", {})
            if not isinstance(step_outputs, dict):
                step_outputs = {}
            for value in step_outputs.values():
                for obj in self._extract_json_objects_from_text(str(value)):
                    produced = obj.get("produced_files") or obj.get("files") or obj.get("target_paths")
                    if isinstance(produced, list):
                        for item in produced:
                            add_file(item)
                    elif isinstance(produced, str):
                        add_file(produced)
        for match in re.findall(
            r"[A-Za-z0-9_.:/-]+?\.(?:csv|json|py|md|txt)",
            artifact or "",
            flags=re.IGNORECASE,
        ):
            add_file(match.strip('`\'"\uff0c\u3002,.\uff1b;:()[]{}'))
        return files[:20]

    def _task_registry_record(self, task_id: str) -> Optional[RuntimeArtifactRecord]:
        return self.artifact_registry.by_task.get(task_id)

    def _step_registry_record(self, task_id: str, step_id: str, output_key: str) -> Optional[RuntimeArtifactRecord]:
        return self.artifact_registry.by_step.get(f"{task_id}:{step_id}:{output_key}")

    def _step_registry_records_for_hint(self, task_id: str, hint: Any) -> List[RuntimeArtifactRecord]:
        token = str(hint or "").strip()
        if not token:
            return []
        records: List[RuntimeArtifactRecord] = []
        seen: Set[int] = set()
        prefix = f"{task_id}:"
        for key, record in self.artifact_registry.by_step.items():
            if not key.startswith(prefix):
                continue
            _, step_id, output_key = key.split(":", 2)
            if token in {step_id, output_key, key} and id(record) not in seen:
                seen.add(id(record))
                records.append(record)
        return records

    def _dedupe_artifact_records(
        self,
        records: Sequence[RuntimeArtifactRecord],
    ) -> List[RuntimeArtifactRecord]:
        unique: List[RuntimeArtifactRecord] = []
        seen: Set[Tuple[str, str, str]] = set()
        for record in records:
            key = (
                os.path.abspath(record.path),
                str(record.artifact_type),
                str(record.origin),
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(record)
        return unique

    def _step_registry_records_from_binding(
        self,
        task_id: str,
        source_hint: Any,
    ) -> List[RuntimeArtifactRecord]:
        if source_hint is None:
            return []
        if isinstance(source_hint, (list, tuple)):
            records: List[RuntimeArtifactRecord] = []
            for item in source_hint:
                records.extend(self._step_registry_records_from_binding(task_id, item))
            return self._dedupe_artifact_records(records)
        if isinstance(source_hint, dict):
            source = parse_binding_source(source_hint)
            if source.variant != "step_output":
                return []
            records: List[RuntimeArtifactRecord] = []
            step_hint = source.from_step
            output_hint = source.output_key
            if step_hint and output_hint:
                record = self._step_registry_record(task_id, str(step_hint), str(output_hint))
                if record is not None:
                    return [record]
                return []
            if step_hint:
                records.extend(self._step_registry_records_for_hint(task_id, step_hint))
            elif output_hint:
                records.extend(self._step_registry_records_for_hint(task_id, output_hint))
            return self._dedupe_artifact_records(records)
        return self._step_registry_records_for_hint(task_id, source_hint)

    def _binding_refers_to_step_output(
        self,
        source_hint: Any,
        step_outputs: Optional[Dict[str, str]] = None,
        known_step_ids: Optional[Set[str]] = None,
        known_output_keys: Optional[Set[str]] = None,
    ) -> bool:
        """Return true when a binding points at an upstream plan step output."""
        step_outputs = step_outputs or {}
        known_step_ids = known_step_ids or set()
        known_output_keys = known_output_keys or set()
        if source_hint is None:
            return False
        if isinstance(source_hint, (list, tuple)):
            return any(
                self._binding_refers_to_step_output(item, step_outputs, known_step_ids, known_output_keys)
                for item in source_hint
            )
        if isinstance(source_hint, dict):
            source = parse_binding_source(source_hint)
            if source.variant != "step_output":
                return False
            step_hint = source.from_step
            output_hint = source.output_key
            if step_hint and (not known_step_ids or str(step_hint) in known_step_ids or str(step_hint) in step_outputs):
                return True
            if output_hint and (not known_output_keys or str(output_hint) in known_output_keys or str(output_hint) in step_outputs):
                return True
            return bool(step_hint or output_hint)
        hint = str(source_hint or "").strip()
        if not hint:
            return False
        if hint.startswith("output:"):
            hint = hint[len("output:"):]
        return hint in step_outputs or hint in known_step_ids or hint in known_output_keys

    @staticmethod
    def _extension_for_artifact_type(artifact_type: str) -> str:
        normalized = str(artifact_type or "plaintext").lower()
        return {
            "code": ".py",
            "markdown": ".md",
            "json": ".json",
            "csv": ".csv",
            "plaintext": ".txt",
            "text": ".txt",
        }.get(normalized, ".txt")

    def _safe_run_relative_path(self, path_hint: Any) -> Optional[str]:
        raw = str(path_hint or "").strip().strip("'\"`")
        if not raw:
            return None
        if "\\" in raw:
            return None
        raw = raw.replace("/", os.sep)
        if os.path.isabs(raw):
            return None
        parts = [part for part in raw.split(os.sep) if part]
        if not parts or any(part == ".." for part in parts):
            return None
        resolved = os.path.abspath(os.path.join(self.artifact_dir, *parts))
        artifact_root = os.path.abspath(self.artifact_dir)
        try:
            if os.path.commonpath([artifact_root, resolved]) != artifact_root:
                return None
        except ValueError:
            return None
        return resolved

    def _safe_output_overlay_path(self, workspace_relative_path: str) -> Optional[str]:
        raw = str(workspace_relative_path or "").strip().strip("'\"`")
        if not raw:
            return None
        if "\\" in raw:
            return None
        raw = raw.replace("/", os.sep)
        if os.path.isabs(raw):
            return None
        parts = [part for part in raw.split(os.sep) if part]
        if not parts or any(part == ".." for part in parts):
            return None
        resolved = os.path.abspath(os.path.join(self.artifact_dir, *parts))
        artifact_root = os.path.abspath(self.artifact_dir)
        try:
            if os.path.commonpath([artifact_root, resolved]) != artifact_root:
                return None
        except ValueError:
            return None
        return resolved

    def _contract_path_hint_workspace_targets(
        self,
        output_contract: Optional[Dict[str, Any]],
        artifact_type: str,
    ) -> List[str]:
        targets: List[str] = []
        produced_files = []
        if isinstance(output_contract, dict):
            produced_files = output_contract.get("produced_files") or []
        if not isinstance(produced_files, list):
            return targets
        for item in produced_files:
            produced_type = self._produced_file_contract_type(item, fallback=artifact_type)
            if produced_type != artifact_type:
                continue
            path_hint = self._produced_file_path_hint(item)
            if not path_hint:
                continue
            hint = str(path_hint).strip().strip("'\"`")
            if os.path.isabs(hint):
                rel = self._to_workspace_relative_path(hint)
            else:
                candidate_host = self._resolve_candidate_path(hint)
                rel = self._to_workspace_relative_path(candidate_host)
                if rel is None and self._safe_output_overlay_path(hint):
                    rel = hint.replace("\\", "/")
            if rel and self._safe_output_overlay_path(rel):
                targets.append(rel.replace("\\", "/"))
        return targets

    def _source_overlay_candidate_inputs(
        self,
        task: Dict[str, Any],
        output_contract: Optional[Dict[str, Any]],
        artifact_type: str,
    ) -> List[str]:
        texts = [
            str(task.get("description") or ""),
            str(task.get("expected_output") or ""),
        ]
        if isinstance(output_contract, dict):
            texts.extend(str(item) for item in output_contract.get("required_content") or [])
            texts.extend(str(item) for item in output_contract.get("grounding_requirements") or [])
        candidates: List[str] = []
        seen: Set[str] = set()
        ext = self._extension_for_artifact_type(artifact_type)
        for text in texts:
            for path in self._extract_existing_file_paths(text, extensions=[ext]):
                resolved = os.path.abspath(path)
                if resolved in seen:
                    continue
                seen.add(resolved)
                candidates.append(resolved)
        return candidates

    def _task_text_for_overlay(self, task: Dict[str, Any], output_contract: Optional[Dict[str, Any]]) -> str:
        parts = [
            str(task.get("id") or ""),
            str(task.get("role") or ""),
            str(task.get("description") or ""),
            str(task.get("expected_output") or ""),
        ]
        if isinstance(output_contract, dict):
            parts.extend(str(item) for item in output_contract.get("required_content") or [])
            parts.extend(str(item) for item in output_contract.get("grounding_requirements") or [])
        return "\n".join(parts).lower()

    @staticmethod
    def _strip_original_query_section(text: str) -> str:
        return re.split(r"\n\s*Original user query\s*:\s*\n", str(text or ""), maxsplit=1, flags=re.IGNORECASE)[0]

    def _is_source_overlay_task(
        self,
        task: Dict[str, Any],
        output_contract: Optional[Dict[str, Any]],
        artifact_type: str,
    ) -> bool:
        if artifact_type != "code":
            return False
        text = self._strip_original_query_section(self._task_text_for_overlay(task, output_contract))
        action_markers = (
            "fix",
            "update",
            "modify",
            "repair",
            "rewrite",
            "patch",
            "implement",
            '\u4fee\u590d',
            '\u66f4\u65b0',
            '\u4fee\u6539',
            '\u91cd\u5199',
            '\u5b9e\u73b0',
            '\u8865\u5145',
            '\u4fee\u6b63',
        )
        file_markers = (".py", "source", "module", "test_", "pytest", '\u6e90\u7801', '\u6d4b\u8bd5', '\u5b9e\u73b0')
        return any(marker in text for marker in action_markers) and any(marker in text for marker in file_markers)

    def _is_test_overlay_task(
        self,
        task: Dict[str, Any],
        output_contract: Optional[Dict[str, Any]],
        artifact_type: str,
    ) -> bool:
        if artifact_type != "code":
            return False
        text = self._strip_original_query_section(self._task_text_for_overlay(task, output_contract))
        return bool(
            re.search(r"\b(write|create|add|update|generate|fix)\b.{0,80}\b(pytest|tests?|test cases?)\b", text)
            or any(marker in text for marker in ("test_http", "test_", "pytest", '\u6d4b\u8bd5\u4ee3\u7801', '\u6d4b\u8bd5\u7528\u4f8b', '\u8865\u5145\u6d4b\u8bd5', '\u4fee\u6b63\u6d4b\u8bd5'))
        )

    def _infer_source_overlay_targets(
        self,
        task: Dict[str, Any],
        artifact_type: str,
        output_contract: Optional[Dict[str, Any]],
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        warnings: List[Dict[str, Any]] = []
        if artifact_type != "code":
            return [], warnings

        explicit_targets = self._contract_path_hint_workspace_targets(output_contract, artifact_type)
        if explicit_targets:
            return explicit_targets, warnings

        candidates = self._source_overlay_candidate_inputs(task, output_contract, artifact_type)
        if not candidates:
            return [], warnings

        text = self._task_text_for_overlay(task, output_contract)
        is_test_task = self._is_test_overlay_task(task, output_contract, artifact_type)
        scored: List[Tuple[int, str]] = []
        for path in candidates:
            rel = self._to_workspace_relative_path(path)
            if not rel:
                continue
            basename = os.path.basename(path).lower()
            normalized_rel = rel.replace("\\", "/").lower()
            score = 0
            if basename in text:
                score += 20
            stem = os.path.splitext(basename)[0]
            if len(stem) >= 3 and stem in text:
                score += 8
            if is_test_task:
                if "/tests/" in normalized_rel or basename.startswith("test_"):
                    score += 14
                else:
                    score -= 4
            else:
                if "/tests/" not in normalized_rel and not basename.startswith("test_"):
                    score += 10
                else:
                    score -= 4
            scored.append((score, rel.replace("\\", "/")))

        if not scored:
            return [], warnings
        scored.sort(key=lambda item: item[0], reverse=True)
        best_score = scored[0][0]
        best_targets = [rel for score, rel in scored if score == best_score]
        if best_score <= 0:
            warnings.append(
                {
                    "failure_type": "overlay_target_ambiguous",
                    "severity": "warning",
                    "reason": "No input file matched the generated code artifact strongly enough for source overlay.",
                    "candidates": [rel for _, rel in scored[:6]],
                }
            )
            return [], warnings
        if len(best_targets) > 1:
            warnings.append(
                {
                    "failure_type": "overlay_target_ambiguous",
                    "severity": "warning",
                    "reason": "Multiple input files matched the generated code artifact equally for source overlay.",
                    "candidates": best_targets[:6],
                }
            )
            return [], warnings
        return best_targets, warnings

    def _ensure_python_package_init_files(self, overlay_path: str) -> List[str]:
        created: List[str] = []
        if not bool(getattr(self, "_active_allow_semantic_normalization", True)):
            return created
        if not overlay_path.lower().endswith(".py"):
            return created
        artifact_root = os.path.abspath(self.artifact_dir)
        current_dir = os.path.dirname(os.path.abspath(overlay_path))
        while True:
            try:
                if os.path.commonpath([artifact_root, current_dir]) != artifact_root:
                    break
            except ValueError:
                break
            if os.path.abspath(current_dir) == artifact_root:
                break
            if os.path.basename(current_dir).lower() in {"src", "app", "pkg", "tests"}:
                init_path = os.path.join(current_dir, "__init__.py")
                if not os.path.exists(init_path):
                    with open(init_path, "w", encoding="utf-8") as f:
                        f.write("")
                    created.append(os.path.abspath(init_path))
            current_dir = os.path.dirname(current_dir)
        return created

    def _register_source_overlays(
        self,
        task_id: str,
        task: Dict[str, Any],
        artifact_type: str,
        output_data: str,
        output_contract: Optional[Dict[str, Any]],
        final_record: RuntimeArtifactRecord,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        if not bool(getattr(self, "_active_allow_semantic_normalization", True)):
            return [], []
        targets, warnings = self._infer_source_overlay_targets(task, artifact_type, output_contract)
        overlays: List[Dict[str, Any]] = []
        if not targets:
            return overlays, warnings

        for rel in targets:
            overlay_path = self._safe_output_overlay_path(rel)
            if not overlay_path:
                warnings.append(
                    {
                        "failure_type": "unsafe_execution_path",
                        "severity": "warning",
                        "reason": f"Skipped unsafe source overlay target: {rel}",
                    }
                )
                continue
            content, extraction_warnings = self._normalize_content_for_overlay(output_data, artifact_type, rel)
            warnings.extend(extraction_warnings)
            if content is None or not str(content).strip():
                warnings.append(
                    {
                        "failure_type": "contract_code_extraction_ambiguous",
                        "severity": "error",
                        "reason": f"Could not extract code content for source overlay target: {rel}",
                    }
                )
                continue
            if os.path.abspath(overlay_path) == os.path.abspath(final_record.path):
                continue
            os.makedirs(os.path.dirname(overlay_path), exist_ok=True)
            with open(overlay_path, "w", encoding="utf-8", newline="" if artifact_type == "csv" else None) as f:
                f.write(content)
                if not content.endswith("\n"):
                    f.write("\n")
            init_files = self._ensure_python_package_init_files(overlay_path)
            overlay_abs = os.path.abspath(overlay_path)
            if overlay_abs not in {os.path.abspath(path) for path in final_record.aliases}:
                final_record.aliases.append(overlay_abs)
            record = RuntimeArtifactRecord(
                path=overlay_abs,
                artifact_type=artifact_type,
                origin="source_overlay",
                aliases=[],
                metadata={
                    "source_task": task_id,
                    "original_workspace_path": rel,
                    "tool_path": self._to_tool_path(overlay_abs),
                    "package_init_files": init_files,
                },
            )
            self.artifact_registry.source_overlays[rel] = record
            overlays.append(
                {
                    "host_path": overlay_abs,
                    "tool_path": self._to_tool_path(overlay_abs),
                    "original_workspace_path": rel,
                    "artifact_type": artifact_type,
                    "origin": "source_overlay",
                    "package_init_files": [self._to_tool_path(path) for path in init_files],
                }
            )
        return overlays, warnings

    def _register_step_source_overlays(
        self,
        task_id: str,
        task_view: Dict[str, Any],
        step: ResourceApplicationStep,
        output_key: str,
        output_data: str,
        artifact_type: str,
        output_contract: Optional[Dict[str, Any]],
        step_record: RuntimeArtifactRecord,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        if not bool(getattr(self, "_active_allow_semantic_normalization", True)):
            return [], []
        targets, warnings = self._infer_source_overlay_targets(task_view, artifact_type, output_contract)
        overlays: List[Dict[str, Any]] = []
        if not targets:
            return overlays, warnings
        for rel in targets:
            overlay_path = self._safe_output_overlay_path(rel)
            if not overlay_path:
                warnings.append(
                    {
                        "failure_type": "unsafe_execution_path",
                        "severity": "warning",
                        "reason": f"Skipped unsafe step source overlay target: {rel}",
                    }
                )
                continue
            content, extraction_warnings = self._normalize_content_for_overlay(output_data, artifact_type, rel)
            warnings.extend(extraction_warnings)
            if content is None or not str(content).strip():
                warnings.append(
                    {
                        "failure_type": "contract_code_extraction_ambiguous",
                        "severity": "error",
                        "reason": f"Could not extract code content for step source overlay target: {rel}",
                    }
                )
                continue
            os.makedirs(os.path.dirname(overlay_path), exist_ok=True)
            with open(overlay_path, "w", encoding="utf-8", newline="" if artifact_type == "csv" else None) as f:
                f.write(content)
                if not content.endswith("\n"):
                    f.write("\n")
            init_files = self._ensure_python_package_init_files(overlay_path)
            overlay_abs = os.path.abspath(overlay_path)
            if overlay_abs not in {os.path.abspath(path) for path in step_record.aliases}:
                step_record.aliases.append(overlay_abs)
            record = RuntimeArtifactRecord(
                path=overlay_abs,
                artifact_type=artifact_type,
                origin="source_overlay",
                aliases=[],
                metadata={
                    "source_task": task_id,
                    "source_step": step.step_id,
                    "source_output": output_key,
                    "original_workspace_path": rel,
                    "tool_path": self._to_tool_path(overlay_abs),
                    "package_init_files": init_files,
                },
            )
            self.artifact_registry.source_overlays[rel] = record
            overlays.append(
                {
                    "host_path": overlay_abs,
                    "tool_path": self._to_tool_path(overlay_abs),
                    "original_workspace_path": rel,
                    "artifact_type": artifact_type,
                    "origin": "source_overlay",
                    "source_step": step.step_id,
                    "package_init_files": [self._to_tool_path(path) for path in init_files],
                }
            )
        return overlays, warnings

    def _artifact_type_from_path_hint(self, path_hint: Any, fallback: str = "plaintext") -> str:
        ext = os.path.splitext(str(path_hint or ""))[1].lower()
        return {
            ".py": "code",
            ".json": "json",
            ".csv": "csv",
            ".md": "markdown",
            ".txt": "plaintext",
        }.get(ext, fallback)

    def _produced_file_contract_type(self, item: Any, fallback: str = "plaintext") -> str:
        if isinstance(item, dict):
            artifact_type = str(item.get("artifact_type") or "").strip().lower()
            if artifact_type:
                return artifact_type
            return self._artifact_type_from_path_hint(item.get("path_hint"), fallback=fallback)
        return self._artifact_type_from_path_hint(item, fallback=fallback)

    def _produced_file_path_hint(self, item: Any) -> Optional[str]:
        if isinstance(item, dict):
            value = item.get("path_hint") or item.get("path") or item.get("file_path")
        else:
            value = item
        text = str(value or "").strip()
        return text or None

    def _registered_artifact_paths(self) -> Set[str]:
        paths: Set[str] = set()
        for record in (
            list(self.artifact_registry.by_step.values())
            + list(self.artifact_registry.by_task.values())
            + list(self.artifact_registry.source_overlays.values())
        ):
            for candidate in [record.path, *record.aliases]:
                if candidate:
                    paths.add(os.path.abspath(candidate))
        return paths

    def _is_artifact_validator_id(self, resource_id: str) -> bool:
        resource_text = str(resource_id or "")
        return (
            resource_text == "tool.pytest_runner.v1"
            or "artifact_validator" in resource_text
            or "pytest_runner" in resource_text
        )

    def _is_artifact_validator_ref(self, ref: Optional[TypedResourceRef]) -> bool:
        return bool(ref and ref.resource_type == ManifestType.TOOL and self._is_artifact_validator_id(ref.resource_id))

    def _content_looks_like_path(self, value: str) -> bool:
        text = str(value or "").strip()
        if not text or "\n" in text or len(text) > 260:
            return False
        if re.search(r"```|^#\s|\{|\}|\[|\]", text):
            return False
        return bool(re.search(r"\.(py|js|ts|json|csv|md|txt|yaml|yml|toml|ini|sql)$", text, re.IGNORECASE))

    def _content_looks_like_raw_text(self, value: str) -> bool:
        text = str(value or "")
        if "\n" in text or len(text) > 260:
            return True
        return bool(re.search(r"```|^#\s|^\s*[-*]\s+", text, re.MULTILINE))

    def _extract_python_fenced_code(self, text: str) -> Optional[str]:
        match = re.search(r"```(?:python|py)\s*(.*?)```", str(text or ""), re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    def _extract_fenced_blocks(self, text: str) -> List[Tuple[str, str]]:
        blocks: List[Tuple[str, str]] = []
        for match in re.finditer(
            r"```([A-Za-z0-9_+.-]*)\s*\n?(.*?)```",
            str(text or ""),
            flags=re.DOTALL,
        ):
            lang = (match.group(1) or "").strip().lower()
            body = (match.group(2) or "").strip()
            if body:
                blocks.append((lang, body))
        return blocks

    def _extract_fenced_blocks_with_context(self, text: str) -> List[Tuple[str, str, str]]:
        blocks: List[Tuple[str, str, str]] = []
        source = str(text or "")
        for match in re.finditer(
            r"```([A-Za-z0-9_+.-]*)\s*\n?(.*?)```",
            source,
            flags=re.DOTALL,
        ):
            lang = (match.group(1) or "").strip().lower()
            body = (match.group(2) or "").strip()
            if not body:
                continue
            context_start = max(0, match.start() - 500)
            context = source[context_start:match.start()].lower()
            blocks.append((lang, body, context))
        return blocks

    def _normalize_content_for_overlay(
        self,
        text: str,
        artifact_type: str,
        target_rel: str,
    ) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        if not bool(getattr(self, "_active_allow_semantic_normalization", True)):
            return str(text) if text is not None else "", []
        if str(artifact_type or "").lower() != "code":
            return self._normalize_materialized_content(text, artifact_type), []

        blocks = [
            (lang, body, context)
            for lang, body, context in self._extract_fenced_blocks_with_context(text)
            if lang in {"python", "py", ""} and self._looks_like_python_code(body)
        ]
        if not blocks:
            return self._normalize_materialized_content(text, artifact_type), []
        if len(blocks) == 1:
            return blocks[0][1], [
                {
                    "failure_type": "code_block_extracted_for_contract",
                    "severity": "warning",
                    "reason": f"Extracted the only Python code block for {target_rel}.",
                }
            ]

        target_norm = str(target_rel or "").replace("\\", "/").lower()
        basename = os.path.basename(target_norm)
        is_test_target = "/tests/" in target_norm or basename.startswith("test_")
        scored: List[Tuple[int, int, str]] = []
        for idx, (_, body, context) in enumerate(blocks):
            body_lower = body.lower()
            score = 0
            if target_norm and target_norm in context:
                score += 40
            if basename and basename in context:
                score += 30
            if is_test_target:
                if re.search(r"(^|\n)\s*def\s+test_", body):
                    score += 20
                if "pytest" in body_lower:
                    score += 8
                if "from src." in body_lower or "import src" in body_lower:
                    score += 4
            else:
                if re.search(r"(^|\n)\s*def\s+test_", body):
                    score -= 20
                if "from src." in body_lower and "def parse_" not in body_lower:
                    score -= 4
                if re.search(r"(^|\n)\s*def\s+[A-Za-z_][A-Za-z0-9_]*\s*\(", body):
                    score += 8
            scored.append((score, idx, body))
        scored.sort(key=lambda item: item[0], reverse=True)
        if len(scored) >= 2 and scored[0][0] == scored[1][0]:
            return None, [
                {
                    "failure_type": "contract_code_extraction_ambiguous",
                    "severity": "error",
                    "reason": f"Multiple Python code blocks matched {target_rel} equally.",
                    "target": target_rel,
                }
            ]
        return scored[0][2], [
            {
                "failure_type": "code_block_extracted_for_contract",
                "severity": "warning",
                "reason": f"Selected Python code block for {target_rel}.",
            }
        ]

    def _python_interface_summary(self, text: str) -> Dict[str, List[str]]:
        try:
            tree = ast.parse(text or "")
        except SyntaxError:
            return {"functions": [], "classes": []}
        return {
            "functions": [node.name for node in tree.body if isinstance(node, ast.FunctionDef)],
            "classes": [node.name for node in tree.body if isinstance(node, ast.ClassDef)],
        }

    def _json_key_summary(self, text: str) -> List[str]:
        try:
            parsed = json.loads(text or "")
        except Exception:
            return []
        if isinstance(parsed, dict):
            return [str(key) for key in parsed.keys()]
        if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
            keys: List[str] = []
            seen: Set[str] = set()
            for item in parsed[:20]:
                if not isinstance(item, dict):
                    continue
                for key in item.keys():
                    key_s = str(key)
                    if key_s not in seen:
                        seen.add(key_s)
                        keys.append(key_s)
            return keys
        return []

    def _looks_like_python_code(self, text: str) -> bool:
        source = self._extract_python_fenced_code(text) or str(text or "").strip()
        if not source:
            return False
        try:
            ast.parse(source)
            return True
        except SyntaxError:
            pass
        return bool(
            re.search(
                r"(^|\n)\s*(def |class |import |from |if __name__\s*==\s*['\"]__main__['\"])",
                source,
            )
        )

    def _normalize_materialized_content(self, text: str, artifact_type: str) -> str:
        content = str(text or "")
        normalized_type = str(artifact_type or "plaintext").lower()
        if normalized_type == "code":
            content = self._extract_python_fenced_code(content) or self._strip_code_fences(content)
        elif normalized_type == "json":
            stripped = content.strip()
            try:
                content = json.dumps(json.loads(stripped), ensure_ascii=False, indent=2)
            except Exception:
                content = stripped
        return content

    def _infer_artifact_type_from_content(self, text: str, default: str = "plaintext") -> str:
        if bool(getattr(self, "_formal_execution_active", False)):
            raise RuntimeError("formal_artifact_type_inference_forbidden")
        stripped = str(text or "").strip()
        if not stripped:
            return default
        if self._looks_like_python_code(stripped):
            return "code"
        try:
            json.loads(stripped)
            return "json"
        except Exception:
            pass
        lines = stripped.splitlines()
        if lines and "," in lines[0]:
            return "csv"
        if re.search(r"^\s{0,3}#{1,6}\s+", stripped, re.MULTILINE) or "```" in stripped:
            return "markdown"
        return default

    def _materialize_step_output(
        self,
        task_id: str,
        step: ResourceApplicationStep,
        output_key: str,
        text: str,
        artifact_type: str,
        preferred_name: Optional[str] = None,
        exact_bytes: bool = False,
    ) -> Tuple[bool, str, str, Optional[RuntimeArtifactRecord]]:
        # Formal resource output is already realized against its contract.
        # Persist those exact bytes, including for Model/Controller results
        # that do not take the inline Tool realization registration path.
        exact_bytes = exact_bytes or bool(getattr(self, "_formal_execution_active", False))
        from .json_serialization import json_serialization_format
        declared_contract = self._contract_to_dict(step.expected_output_contract)
        jsonl_output = json_serialization_format(declared_contract) == "jsonl"
        exact_bytes = exact_bytes or jsonl_output
        if not exact_bytes and bool(getattr(self, "_active_allow_semantic_normalization", True)):
            content = self._normalize_materialized_content(text, artifact_type)
        else:
            # A fixed-pass run materializes exactly what the selected resource
            # returned.  Fence extraction and JSON reformatting are semantic
            # recovery and would otherwise change the executed/validated Plan.
            content = str(text) if text is not None else ""
        if not content.strip():
            return False, "raw_content_not_materialized", f"Step {step.step_id} output is empty.", None

        generated_dir = os.path.abspath(os.path.join(self.artifact_dir, "generated_artifacts"))
        os.makedirs(generated_dir, exist_ok=True)
        ext = ".jsonl" if jsonl_output else self._extension_for_artifact_type(artifact_type)
        safe_base = re.sub(r"[^A-Za-z0-9_.-]+", "_", preferred_name or f"{task_id}_{step.step_id}_{output_key}")
        if not safe_base.lower().endswith(ext):
            safe_base += ext
        path = os.path.abspath(os.path.join(generated_dir, safe_base))
        try:
            if os.path.commonpath([generated_dir, path]) != generated_dir:
                return False, "unsafe_execution_path", "Materialized step output path escaped artifact directory.", None
        except ValueError:
            return False, "unsafe_execution_path", "Materialized step output path escaped artifact directory.", None

        with open(path, "w", encoding="utf-8", newline="" if exact_bytes or ext == ".csv" else None) as f:
            f.write(content)
            if not exact_bytes and not content.endswith("\n"):
                f.write("\n")
        record = RuntimeArtifactRecord(path=path, artifact_type=artifact_type, origin="step_output")
        self.artifact_registry.by_step[f"{task_id}:{step.step_id}:{output_key}"] = record
        return True, "", "", record

    def _register_realized_inline_result(
        self, task_id: str, step: ResourceApplicationStep,
        result: ExecutionResult, records: Sequence[RuntimeArtifactRecord],
    ) -> List[RuntimeArtifactRecord]:
        """Publish realized inline bytes; retain native files as execution evidence."""
        if not result.is_success or not any(r.metadata.get("inline_provider_output") for r in records):
            return list(records)
        declared = step.expected_output_contract.artifact_type
        declared_type = str(getattr(declared, "value", declared))
        ok, failure, reason, record = self._materialize_step_output(
            task_id, step, step.output_key, result.output_data, declared_type,
            preferred_name=f"{task_id}_{step.step_id}_{step.output_key}_realized",
            exact_bytes=True,
        )
        if not ok or record is None:
            raise RuntimeError(failure or "realized_output_materialization_failed")
        record.origin = "realized_step_output"
        return [r for r in records if not r.metadata.get("inline_provider_output")] + [record]

    async def _read_controller_input_source(self, path: str) -> str | None:
        """Read an explicit task-local program for repeat identity bookkeeping."""
        if self.execution_substrate is None:
            return None
        try:
            path = self.execution_substrate.task_path(path)
            if not await self.execution_substrate.exists(path):
                return None
            return await self.execution_substrate.read_text(path)
        except Exception:
            # Optional dependency evidence never changes Tool dispatch authority
            # or blocks a valid action; unreadable inputs keep the original policy.
            return None

    async def _read_materialized_controller_delivery_state(
        self, *, output_contract: Any,
    ) -> dict[str, Any] | None:
        """Observe required task paths without asserting task correctness.

        This is a bounded current-state view of the already declared delivery,
        not an extra verifier or a permission to terminate a Controller.
        """
        if self.execution_substrate is None:
            return None
        macro = self._contract_to_dict(output_contract)
        required = [item for item in (macro.get("produced_files") or ())
                    if isinstance(item, Mapping) and item.get("required", True)]
        if not required:
            return None
        rows = []
        for item in required:
            hint = self._produced_file_path_hint(item)
            if not hint:
                continue
            path = self.execution_substrate.task_path(hint)
            present = await self.execution_substrate.exists(path)
            row = {"path": path, "artifact_type": self._produced_file_contract_type(item, fallback="file"),
                   "present": present}
            if present and row["artifact_type"] not in {"directory", "bundle"}:
                content = await self.execution_substrate.read_bytes(path)
                row.update(content_sha256=hashlib.sha256(content).hexdigest(), byte_size=len(content))
            rows.append(row)
        return {"required_outputs": rows,
                "all_declared_paths_present": bool(rows) and len(rows) == len(required)
                    and all(row["present"] for row in rows),
                "verification_scope": "declared_path_presence_and_file_identity",
                "semantic_correctness": "not_determined"}

    async def _read_materialized_controller_output(
        self, *, output_contract: Any, delivery_contract: Mapping[str, Any],
    ) -> str | None:
        """Read the declared primary file without asking a Model to reproduce it.

        Readiness/semantic evidence is still checked by the Controller audit.
        File bytes and their original content requirements are checked here and
        again by the existing final artifact/evaluation path.
        """
        if self.execution_substrate is None:
            return None
        macro = self._contract_to_dict(output_contract)
        declared = macro.get("produced_files") or []
        required = [item for item in declared if isinstance(item, Mapping) and item.get("required", True)]
        artifact_type = str(delivery_contract.get("artifact_type") or "")
        if artifact_type not in {"json", "plaintext", "code", "markdown", "csv", "file"}:
            return None
        primary = [item for item in required if self._produced_file_contract_type(
            item, fallback=artifact_type) == artifact_type]
        if artifact_type == "file":
            primary = [item for item in required if self._produced_file_contract_type(
                item, fallback="file") not in {"directory", "bundle"}]
        if len(primary) != 1:
            return None
        for item in required:
            hint = self._produced_file_path_hint(item)
            if not hint or not await self.execution_substrate.exists(self.execution_substrate.task_path(hint)):
                return None
        path = self.execution_substrate.task_path(self._produced_file_path_hint(primary[0]))
        reader = getattr(self.execution_substrate, "read_bytes", None)
        try:
            raw = await reader(path) if callable(reader) else (
                await self.execution_substrate.read_text(path)).encode("utf-8")
        except (OSError, RuntimeError) as exc:
            # This is an opportunistic read between Controller turns. A path
            # may still be a build directory or an incomplete output. Leave
            # execution running; final snapshot/commit still validates the
            # actual required representation and bytes without this fallback.
            logger.debug("Controller output not yet readable at {}: {}", path, type(exc).__name__)
            return None
        from .artifact_semantics import OutputContractViolation, validate_delivery_content
        try:
            file_contract = primary[0]
            if isinstance(file_contract.get("schema_hint"), Mapping):
                validate_delivery_content(raw, {
                    "artifact_type": "json", "schema_hint": file_contract["schema_hint"],
                }, {})
            validate_delivery_content(raw, dict(delivery_contract), macro)
            return raw.decode("utf-8")
        except (OutputContractViolation, UnicodeDecodeError):
            return None

    async def _snapshot_declared_external_outputs(
        self, *, task_id: str, step: ResourceApplicationStep,
        output_contract: Optional[Any],
    ) -> None:
        """Collect task-declared final files independently of Tool receipt shape.

        A shell or program may produce a file without printing a produced_files
        envelope. The declared locator is the input authority; actual substrate
        bytes are the delivery evidence. This does not assert who created a file
        or that its business content is correct.
        """
        if self.execution_substrate is None:
            return
        declared = self._contract_to_dict(output_contract).get("produced_files") or []
        for item in declared if isinstance(declared, list) else ():
            hint = self._produced_file_path_hint(item)
            artifact_type = self._produced_file_contract_type(item, fallback="file")
            if not hint or artifact_type in {"directory", "bundle"}:
                continue
            task_path = self.execution_substrate.task_path(hint)
            if not await self.execution_substrate.exists(task_path):
                continue
            content = await self.execution_substrate.read_bytes(task_path)
            digest = hashlib.sha256(content).hexdigest()
            handle_id = "final-state:" + canonical_sha256({
                "task_id": task_id, "step_id": step.step_id,
                "task_path": task_path, "content_sha256": digest,
            })
            self.artifact_registry.external_handles[handle_id] = ArtifactHandle(
                handle_id=handle_id, kind="tool_output", producer_task=task_id,
                producer_step=step.step_id, logical_path=task_path, tool_path=task_path,
                artifact_type=artifact_type, current_run=True,
                provenance={"content_sha256":digest,"byte_size":len(content),
                            "origin":"declared_final_state_snapshot"},
            )

    @staticmethod
    def _external_artifact_type_matches(handle: ArtifactHandle, expected_type: str) -> bool:
        # `file` describes a physical representation. A checked file handle may
        # also carry a more specific content type, such as plaintext or JSON.
        return handle.artifact_type == expected_type or (
            expected_type == "file"
            and handle.artifact_type not in {"directory", "bundle"}
        )

    def _external_output_handles(
        self,
        output_contract: Optional[Any],
    ) -> tuple[ArtifactHandle, ...]:
        """Select the latest exact external revision for each declared path."""

        if self.execution_substrate is None:
            return ()
        contract = self._contract_to_dict(output_contract)
        produced_files = contract.get("produced_files") or []
        if not isinstance(produced_files, list):
            return ()
        expected: list[tuple[str, str]] = []
        for item in produced_files:
            path_hint = self._produced_file_path_hint(item)
            if not path_hint:
                continue
            try:
                runtime_path = self.execution_substrate.task_path(path_hint)
            except Exception:
                continue
            expected.append((
                runtime_path,
                self._produced_file_contract_type(item, fallback="file"),
            ))
        latest_by_path: Dict[str, ArtifactHandle] = {}
        for handle in self.artifact_registry.external_handles.values():
            tool_path = str(handle.tool_path or "")
            if handle.current_run and tool_path:
                latest_by_path[tool_path] = handle
        return tuple(
            handle
            for runtime_path, expected_type in expected
            if (handle := latest_by_path.get(runtime_path)) is not None
            and self._external_artifact_type_matches(handle, expected_type)
            and re.fullmatch(
                r"[0-9a-f]{64}",
                str((handle.provenance or {}).get("content_sha256") or ""),
            )
        )

    async def _register_external_final_text_artifact(
        self,
        task_id: str,
        step: ResourceApplicationStep,
        handles: Sequence[ArtifactHandle],
        *,
        output_contract: Optional[Any] = None,
    ) -> List[RuntimeArtifactRecord]:
        """Import sealed final side effects as exact evaluation evidence.

        A Tool receipt records execution history, including temporary files.
        When a task contract is available, only its declared deliverable paths
        enter final readback. Intermediate receipts remain in the registry.
        """
        if self.execution_substrate is None:
            return []
        textual_extensions = {
            "plaintext": ".txt", "code": ".py", "json": ".json",
            "csv": ".csv", "markdown": ".md",
        }
        declared_paths = None
        if output_contract is not None:
            declared_paths = {
                self.execution_substrate.task_path(hint)
                for item in (self._contract_to_dict(output_contract).get("produced_files") or ())
                if (hint := self._produced_file_path_hint(item))
            }
        current_path_handles = [
            handle for handle in handles
            if handle.current_run and handle.tool_path
            and (declared_paths is None or handle.tool_path in declared_paths)
        ]
        for handle in current_path_handles:
            # The substrate owns task paths; public system paths use the same
            # canonical task-path validation as dispatch, never a host path.
            if self.execution_substrate.task_path(handle.tool_path) != handle.tool_path:
                raise RuntimeError("external_final_artifact_task_path_invalid")
        # A controller may deliberately refine or normalize a produced file in
        # a later Tool call.  Artifact handles are append-only execution
        # receipts, while a task path names mutable workspace state.  Read back
        # only the last current-run revision of each path; checking every
        # historical receipt against the final bytes incorrectly treats a
        # valid later write as tampering.
        latest_by_path: Dict[str, ArtifactHandle] = {}
        for handle in current_path_handles:
            latest_by_path[str(handle.tool_path)] = handle
        final_handles = list(latest_by_path.values())
        if not final_handles:
            return []
        text_reader = getattr(self.execution_substrate, "read_text", None)
        byte_reader = getattr(self.execution_substrate, "read_bytes", None)
        records: List[RuntimeArtifactRecord] = []
        for handle in final_handles:
            provenance = handle.provenance or {}
            expected_sha = str(provenance.get("content_sha256") or "").lower()
            expected_size = provenance.get("byte_size")
            text_only_readback = (
                not callable(byte_reader)
                and handle.artifact_type in textual_extensions
                and callable(text_reader)
            )
            identity_error_prefix = (
                "external_final_text"
                if text_only_readback else "external_final_artifact"
            )
            if not re.fullmatch(r"[0-9a-f]{64}", expected_sha) or not isinstance(expected_size, int):
                raise RuntimeError(identity_error_prefix + "_identity_missing")
            if callable(byte_reader):
                raw = await byte_reader(handle.tool_path)
            elif text_only_readback:
                raw = (await text_reader(handle.tool_path)).encode("utf-8")
            else:
                raise RuntimeError("external_final_artifact_readback_unavailable")
            if len(raw) != expected_size or hashlib.sha256(raw).hexdigest() != expected_sha:
                raise RuntimeError(identity_error_prefix + "_identity_mismatch")
            directory = Path(self.artifact_dir) / "generated_artifacts"
            directory.mkdir(parents=True, exist_ok=True)
            suffix = PurePosixPath(str(handle.tool_path or "")).suffix
            if not suffix:
                suffix = textual_extensions.get(handle.artifact_type, ".bin")
            path = directory / (
                "external_" + hashlib.sha256(
                    (str(handle.tool_path) + "\0" + expected_sha).encode()
                ).hexdigest()
                + suffix
            )
            if path.exists() and path.read_bytes() != raw:
                raise RuntimeError("external_final_artifact_local_identity_conflict")
            path.write_bytes(raw)
            record = RuntimeArtifactRecord(
                path=str(path),
                artifact_type=handle.artifact_type,
                origin="external_tool_output",
                metadata={
                    "tool_path": handle.tool_path,
                    "handle_id": handle.handle_id,
                    "content_sha256": expected_sha,
                },
            )
            self.artifact_registry.by_step[
                f"{task_id}:{step.step_id}:{step.output_key}:external:{handle.handle_id}"
            ] = record
            records.append(record)
        return records

    def _register_final_derived_artifacts(
        self,
        task_id: str,
        artifact_type: str,
        output_data: str,
        upstream_profiles: Sequence[Any],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Materialize code/JSON blocks embedded in a final document without mutating upstream artifacts."""
        if bool(getattr(self, "_formal_execution_active", False)):
            raise RuntimeError("formal_final_derived_artifact_forbidden")
        if not bool(getattr(self, "_active_allow_semantic_normalization", True)):
            return [], []
        if str(artifact_type or "").lower() != "markdown":
            return [], []

        derived: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []

        for index, (language, body) in enumerate(self._extract_fenced_blocks(output_data), start=1):
            normalized_lang = language.lower()
            block_type = ""
            if normalized_lang == "json" or (not normalized_lang and self._json_key_summary(body)):
                block_type = "json"
            elif normalized_lang in {"python", "py"} or self._looks_like_python_code(body):
                block_type = "code"
            if not block_type:
                continue

            pseudo_step = ResourceApplicationStep(
                step_id=f"derived_final_{index}",
                step_type="synthesize_final",
                resource_id="orchestrator.derived_final_artifact",
                intent="materialize embedded final artifact for lineage tracking",
                input_bindings={},
                output_key=f"derived_final_{index}",
            )
            ok, failure_type, reason, record = self._materialize_step_output(
                task_id,
                pseudo_step,
                pseudo_step.output_key,
                body,
                block_type,
                preferred_name=f"{task_id}_derived_final_{index}",
            )
            if not ok or record is None:
                warnings.append(
                    {
                        "failure_type": "artifact_lineage_mismatch",
                        "severity": "warning",
                        "reason": f"Could not materialize embedded {block_type} block: {reason or failure_type}",
                    }
                )
                continue
            record.origin = "derived_final_artifact"
            record.metadata.update(
                {
                    "source_task": task_id,
                    "language": language or block_type,
                    "tool_path": self._artifact_handle_tool_path(record.path),
                }
            )
            derived.append(
                {
                    "host_path": record.path,
                    "tool_path": self._artifact_handle_tool_path(record.path),
                    "artifact_type": block_type,
                    "language": language or block_type,
                    "origin": record.origin,
                }
            )

        return derived, warnings

    def _register_internal_tool_artifacts(
        self, task_id: str, step: Any, result: ResourceCallResult,
    ) -> List[RuntimeArtifactRecord]:
        """Register observed file effects after the native result passed validation."""
        if result.status != ResourceCallStatus.SUCCESS or self.execution_substrate is not None:
            return []
        records = []
        for handle in result.artifacts:
            if not handle.host_path or handle.provenance.get("runtime") != "isolated_task_state":
                continue
            record = RuntimeArtifactRecord(
                path=handle.host_path, artifact_type=handle.artifact_type, origin="tool_output",
                metadata={"source_step": step.step_id, "source_task": task_id,
                          "source_output": step.output_key, "logical_path": handle.logical_path,
                          "tool_path": handle.tool_path,
                          "content_sha256": handle.provenance["content_sha256"]},
            )
            # A successful new production supersedes this producer's earlier
            # logical file across plan recovery. Keep historical bytes on disk,
            # but do not mount both revisions as competing current inputs.
            for old_key, previous in tuple(self.artifact_registry.by_step.items()):
                if (previous.origin == "tool_output"
                    and previous.metadata.get("source_task") == task_id
                    and previous.metadata.get("source_step") == step.step_id
                    and previous.metadata.get("source_output") == step.output_key
                    and previous.metadata.get("logical_path") == handle.logical_path):
                    del self.artifact_registry.by_step[old_key]
            # One record per host file keeps overwritten files unambiguous
            # across multiple calls inside the same Controller step.
            key = f"{task_id}:{step.step_id}:{step.output_key}:file:{hashlib.sha256(handle.host_path.encode()).hexdigest()}"
            self.artifact_registry.by_step[key] = record
            records.append(record)
        return records

    def _register_controller_tool_artifacts(
        self, task_id: str, step: Any, result: ResourceCallResult,
        produced_handles: List[ArtifactHandle],
    ) -> None:
        """Expose validated current Tool file effects to the next model turn."""
        if result.status != ResourceCallStatus.SUCCESS:
            return
        if self.execution_substrate is None:
            records = self._register_internal_tool_artifacts(task_id, step, result)
            registered = {record.path for record in records}
            produced_handles.extend(handle for handle in result.artifacts
                                    if handle.host_path in registered)
        else:
            for handle in result.artifacts:
                self.artifact_registry.external_handles[handle.handle_id] = handle
                produced_handles.append(handle)

    def _dependency_media_handles(self, task_id: str, step: Any, plan: Any) -> List[ArtifactHandle]:
        """Pass only current files produced in this step's declared DAG ancestry."""
        from .model_media import is_model_media_path
        by_id = {item.step_id: item for item in plan.steps}
        allowed = set()
        pending = list(step.depends_on)
        while pending:
            key = pending.pop()
            if key in allowed or key not in by_id:
                continue
            allowed.add(key)
            pending.extend(by_id[key].depends_on)
        handles = []
        for handle in self.artifact_registry.external_handles.values():
            if (handle.current_run and handle.producer_task == task_id
                    and handle.producer_step in allowed
                    and is_model_media_path(str(handle.tool_path or handle.logical_path or ""))):
                handles.append(handle)
        if self.execution_substrate is None:
            for record in self.artifact_registry.by_step.values():
                meta = record.metadata
                if (record.origin != "tool_output" or meta.get("source_task") != task_id
                        or meta.get("source_step") not in allowed
                        or not is_model_media_path(str(meta.get("tool_path") or record.path))):
                    continue
                digest = meta.get("content_sha256")
                if not digest:
                    continue
                path = Path(record.path)
                if not path.is_file():
                    raise ModelMediaProjectionError("model_media_selected_dependency_missing")
                handle = self._artifact_handle_for_record(
                    handle_id="dependency-media:" + canonical_sha256({"task": task_id,
                        "step": meta["source_step"], "digest": digest, "logical_path": meta.get("logical_path")}),
                    kind="tool_output", record=record, producer_task=task_id,
                    producer_step=meta["source_step"], logical_path=meta.get("logical_path"))
                handles.append(handle.model_copy(update={"provenance": {
                    "content_sha256": digest, "byte_size": path.stat().st_size,
                    "runtime": "isolated_task_state"}}))
        return handles

    def _register_tool_output_artifacts(
        self,
        task_id: str,
        step: ResourceApplicationStep,
        output_data: str,
    ) -> List[RuntimeArtifactRecord]:
        """Register files reported by deterministic tools as current-run artifacts."""
        formal = bool(getattr(self, "_formal_execution_active", False))
        try:
            payload = json.loads(output_data or "{}")
        except Exception:
            return []
        produced = (
            payload.get("artifact_handles")
            if formal and isinstance(payload, dict)
            else payload.get("produced_files")
            if isinstance(payload, dict)
            else []
        )
        if not isinstance(produced, list):
            return []
        records: List[RuntimeArtifactRecord] = []
        for index, item in enumerate(produced):
            if formal:
                if not isinstance(item, dict) or set(item) != {
                    "logical_path",
                    "artifact_type",
                    "content_sha256",
                }:
                    raise RuntimeError("formal_tool_artifact_handle_protocol_invalid")
                item_path = item["logical_path"]
                artifact_type = str(item["artifact_type"] or "").strip()
                expected_sha256 = str(item["content_sha256"] or "").strip().lower()
                if not artifact_type or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
                    raise RuntimeError("formal_tool_artifact_handle_protocol_invalid")
            elif isinstance(item, dict):
                item_path = (
                    item.get("path")
                    or item.get("file_path")
                    or item.get("target_path")
                    or item.get("output_path")
                )
            else:
                item_path = item
            if not item_path:
                continue
            host_path = self._resolve_candidate_path(str(item_path))
            if not os.path.isfile(host_path) or not self._is_workspace_path(host_path):
                continue
            if formal:
                actual_sha256 = hashlib.sha256(Path(host_path).read_bytes()).hexdigest()
                if actual_sha256 != expected_sha256:
                    raise RuntimeError("formal_tool_artifact_content_hash_mismatch")
            else:
                ext = os.path.splitext(host_path)[1].lower()
                artifact_type = {
                    ".py": "code",
                    ".json": "json",
                    ".csv": "csv",
                    ".md": "markdown",
                }.get(ext, "plaintext")
            record = RuntimeArtifactRecord(
                path=host_path,
                artifact_type=artifact_type,
                origin="tool_output",
                metadata={
                    "source_step": step.step_id,
                    "source_output": step.output_key,
                    "tool_path": self._artifact_handle_tool_path(host_path),
                },
            )
            key = f"{task_id}:{step.step_id}:{step.output_key}:produced_{index}"
            self.artifact_registry.by_step[key] = record
            records.append(record)
        return records

    def _register_declared_tool_step_output(
        self,
        task_id: str,
        step: ResourceApplicationStep,
        output_data: str,
    ) -> Optional[RuntimeArtifactRecord]:
        """Materialize an inline Tool result according to its step contract.

        A Tool may return structured content directly instead of returning a
        ``produced_files`` list.  That content is still a concrete current-run
        artifact and must enter the same registry used by downstream bindings
        and task-level ``produced_files`` checks.
        """
        contract = step.expected_output_contract
        declared_type = getattr(contract, "artifact_type", None) if contract else None
        if hasattr(declared_type, "value"):
            declared_type = declared_type.value
        artifact_type = str(declared_type or "").strip().lower()
        if not artifact_type:
            artifact_type = self._infer_artifact_type_from_content(output_data, default="plaintext")

        # Never bless malformed structured output merely because the Policy
        # declared it as JSON.  The semantic contract must remain strict.
        if artifact_type == "json":
            try:
                from .json_serialization import json_serialization_format, parse_json_content
                declared_contract = self._contract_to_dict(contract)
                parse_json_content(str(output_data or ""),
                    serialization_format=json_serialization_format(declared_contract),
                    schema=declared_contract.get("schema_hint") or {})
            except Exception:
                return None

        ok, _, _, record = self._materialize_step_output(
            task_id,
            step,
            step.output_key,
            output_data,
            artifact_type,
        )
        return record if ok else None

    def _write_task_artifact_and_aliases(
        self,
        task_id: str,
        artifact_type: str,
        output_ext: str,
        output_data: str,
        output_contract: Optional[Dict[str, Any]],
    ) -> RuntimeArtifactRecord:
        os.makedirs(self.artifact_dir, exist_ok=True)
        ext = output_ext if output_ext else _DEFAULT_ARTIFACT_EXT.get(artifact_type, self._extension_for_artifact_type(artifact_type))
        primary_path = os.path.abspath(os.path.join(self.artifact_dir, f"{task_id}{ext}"))
        content = output_data if artifact_type in ("code", "json", "csv") else f"# Artifact: {task_id}\n\n{output_data}"
        with open(primary_path, "w", encoding="utf-8", newline="" if artifact_type == "csv" else None) as f:
            f.write(content)

        aliases: List[str] = []
        produced_files = []
        if isinstance(output_contract, dict):
            produced_files = output_contract.get("produced_files") or []
        if isinstance(produced_files, list):
            for item in produced_files:
                path_hint = item.get("path_hint") if isinstance(item, dict) else item
                produced_type = self._produced_file_contract_type(item, fallback=artifact_type)
                if produced_type != artifact_type:
                    continue
                alias_path = self._safe_run_relative_path(path_hint)
                if not alias_path:
                    logger.debug("[ArtifactRegistry] Skipped unsafe contract alias for {}: {}", task_id, path_hint)
                    continue
                if os.path.abspath(alias_path) == primary_path:
                    continue
                os.makedirs(os.path.dirname(alias_path), exist_ok=True)
                shutil.copyfile(primary_path, alias_path)
                aliases.append(os.path.abspath(alias_path))

        record = RuntimeArtifactRecord(
            path=primary_path,
            artifact_type=artifact_type,
            origin="task_final",
            aliases=aliases,
        )
        self.artifact_registry.by_task[task_id] = record
        return record

    def _check_required_produced_files(
        self,
        task_id: str,
        output_contract: Optional[Dict[str, Any]],
        final_record: RuntimeArtifactRecord,
    ) -> Tuple[bool, str, str, List[Dict[str, Any]]]:
        """Verify required produced_files are backed by current-run artifacts."""
        produced_files = []
        if isinstance(output_contract, dict):
            produced_files = output_contract.get("produced_files") or []
        if not isinstance(produced_files, list):
            return True, "", "", []

        registered_paths = self._registered_artifact_paths()
        status: List[Dict[str, Any]] = []
        final_paths = {os.path.abspath(final_record.path), *{os.path.abspath(path) for path in final_record.aliases}}

        for item in produced_files:
            required = True
            if isinstance(item, dict):
                required = bool(item.get("required", True))
            path_hint = self._produced_file_path_hint(item)
            if not path_hint:
                continue
            expected_type = self._produced_file_contract_type(item, fallback=final_record.artifact_type)
            safe_path = self._safe_run_relative_path(path_hint)
            entry: Dict[str, Any] = {
                "path_hint": path_hint,
                "artifact_type": expected_type,
                "required": required,
                "status": "missing",
                "source": "",
                "host_path": "",
            }
            if safe_path is None:
                entry["status"] = "unsafe"
                status.append(entry)
                if required:
                    return (
                        False,
                        "unsafe_contract_alias",
                        f"Required produced file path is unsafe for task {task_id}: {path_hint}",
                        status,
                    )
                continue

            safe_abs = os.path.abspath(safe_path)
            entry["host_path"] = safe_abs
            exact_registered = [
                path for path in registered_paths
                if os.path.isfile(path)
                and os.path.abspath(path) == safe_abs
                and self._artifact_type_from_path_hint(path, fallback=expected_type) == expected_type
            ]
            if exact_registered:
                entry["status"] = "present"
                entry["source"] = "registered_artifact"
                entry["host_path"] = exact_registered[0]
            elif expected_type == final_record.artifact_type:
                if safe_abs in final_paths and os.path.isfile(safe_abs):
                    entry["status"] = "present"
                    entry["source"] = "contract_alias"
                elif os.path.abspath(final_record.path) == safe_abs and os.path.isfile(final_record.path):
                    entry["status"] = "present"
                    entry["source"] = "task_final"
            else:
                matching_registered = [
                    path for path in registered_paths
                    if os.path.isfile(path)
                    and (
                        os.path.abspath(path) == safe_abs
                        or os.path.basename(path).lower() == os.path.basename(safe_abs).lower()
                    )
                    and self._artifact_type_from_path_hint(path, fallback=expected_type) == expected_type
                ]
                if matching_registered:
                    entry["status"] = "present"
                    entry["source"] = "registered_artifact"
                    entry["host_path"] = matching_registered[0]

            status.append(entry)
            if required and entry["status"] != "present":
                return (
                    False,
                    "contract_produced_file_missing",
                    (
                        f"Required produced file for task {task_id} was not materialized as a current-run artifact: "
                        f"{path_hint} ({expected_type})"
                    ),
                    status,
                )

        return True, "", "", status

    def _formal_required_output_status(
        self,
        *,
        task_id: str,
        output_contract: Optional[Any],
        final_artifact_type: str,
        final_record: RuntimeArtifactRecord | None,
        primary_value_available: bool = False,
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """Audit sealed-plan outputs without post-execution semantic materialization.

        A same-type produced-file declaration is a deterministic locator for the
        primary value.  A cross-type side artifact must already be registered by
        the sealed execution under its exact declared path.  The returned
        projection is host-free and safe to persist in formal records.
        """

        contract = self._contract_to_dict(output_contract)
        produced_files = contract.get("produced_files") or []
        if not isinstance(produced_files, list):
            return True, []
        records = list(self.artifact_registry.by_step.values())
        status: List[Dict[str, Any]] = []
        primary_available = final_record is not None or primary_value_available
        valid = primary_available
        for item in produced_files:
            required = bool(item.get("required", True)) if isinstance(item, dict) else True
            path_hint = self._produced_file_path_hint(item)
            expected_type = self._produced_file_contract_type(
                item,
                fallback=final_artifact_type,
            )
            entry: Dict[str, Any] = {
                "path_hint": path_hint,
                "artifact_type": expected_type,
                "required": required,
                "status": "missing",
                "source": "",
                "runtime_locator": "",
            }
            if not path_hint:
                entry.update(
                    {
                        "status": "present" if primary_available else "missing",
                        "source": "primary_result_contract",
                        "runtime_locator": "artifact://primary",
                    }
                )
            elif self.execution_substrate is not None:
                try:
                    runtime_path = self.execution_substrate.task_path(path_hint)
                except Exception:
                    entry["status"] = "unsafe"
                else:
                    latest_by_path: Dict[str, ArtifactHandle] = {}
                    for handle in self.artifact_registry.external_handles.values():
                        tool_path = str(handle.tool_path or "")
                        if handle.current_run and tool_path:
                            latest_by_path[tool_path] = handle
                    latest = latest_by_path.get(runtime_path)
                    matches = [latest] if (
                        latest is not None
                        and self._external_artifact_type_matches(latest, expected_type)
                        and re.fullmatch(
                            r"[0-9a-f]{64}",
                            str((latest.provenance or {}).get("content_sha256") or ""),
                        )
                    ) else []
                    if (
                        final_record is not None
                        and final_record.origin == "external_tool_output"
                        and final_record.metadata.get("tool_path") == runtime_path
                    ):
                        # Revisions may write the same logical path repeatedly.
                        # The final record was read back and hash-checked against
                        # the live substrate; older handles are not evidence for
                        # the selected output.
                        matches = [
                            handle for handle in matches
                            if handle.handle_id == final_record.metadata.get("handle_id")
                            and (handle.provenance or {}).get("content_sha256")
                            == final_record.metadata.get("content_sha256")
                        ]
                    if len(matches) == 1:
                        entry.update(
                            {
                                "status": "present",
                                "source": "external_task_artifact",
                                "runtime_locator": runtime_path,
                            }
                        )
            else:
                safe_path = self._safe_run_relative_path(path_hint)
                if safe_path is None:
                    entry["status"] = "unsafe"
                elif expected_type == final_artifact_type and primary_available:
                    entry.update(
                        {
                            "status": "present",
                            "source": "primary_result_contract",
                            "runtime_locator": self._to_tool_path(safe_path),
                        }
                    )
                else:
                    safe_abs = os.path.abspath(safe_path)
                    matches = [
                        record
                        for record in records
                        if os.path.abspath(record.path) == safe_abs
                        and os.path.isfile(record.path)
                        and record.artifact_type == expected_type
                        and self._is_current_run_artifact_path(record.path)
                    ]
                    if len(matches) == 1:
                        entry.update(
                            {
                                "status": "present",
                                "source": "sealed_step_artifact",
                                "runtime_locator": self._to_tool_path(matches[0].path),
                            }
                        )
            status.append(entry)
            if required and entry["status"] != "present":
                valid = False
        return valid, status

    def _contract_to_dict(self, output_contract: Optional[Any]) -> Dict[str, Any]:
        if output_contract is None:
            return {}
        if isinstance(output_contract, dict):
            return output_contract
        if hasattr(output_contract, "model_dump"):
            try:
                return output_contract.model_dump(mode="json")
            except Exception:
                return {}
        return {}

    def _required_produced_file_entries(
        self,
        output_contract: Optional[Any],
        *,
        final_artifact_type: str = "",
    ) -> List[Dict[str, Any]]:
        """Return safe required produced_files entries with resolved run-local targets."""
        contract = self._contract_to_dict(output_contract)
        produced_files = contract.get("produced_files") or []
        if not isinstance(produced_files, list):
            return []
        entries: List[Dict[str, Any]] = []
        for item in produced_files:
            required = bool(item.get("required", True)) if isinstance(item, dict) else True
            path_hint = self._produced_file_path_hint(item)
            if not required or not path_hint:
                continue
            artifact_type = self._produced_file_contract_type(item, fallback=final_artifact_type or "plaintext")
            safe_path = self._safe_run_relative_path(path_hint)
            if safe_path is None:
                continue
            entries.append(
                {
                    "path_hint": path_hint,
                    "artifact_type": artifact_type,
                    "host_path": os.path.abspath(safe_path),
                    "basename": os.path.basename(str(path_hint).replace("\\", "/")),
                }
            )
        return entries

    def _side_artifact_entries_for_execution(
        self,
        output_contract: Optional[Any],
        *,
        final_artifact_type: str,
    ) -> List[Dict[str, Any]]:
        """Return required side artifacts that may need deterministic execution to exist.

        Same-type produced_files are usually final aliases. They become side
        execution targets only when the same contract also asks for another
        artifact type, which signals a multi-file deliverable.
        """
        entries = self._required_produced_file_entries(
            output_contract,
            final_artifact_type=final_artifact_type,
        )
        if not entries:
            return []
        has_cross_type = any(entry["artifact_type"] != final_artifact_type for entry in entries)
        executable_types = {"csv", "json", "plaintext"}
        side_entries: List[Dict[str, Any]] = []
        for entry in entries:
            artifact_type = str(entry.get("artifact_type") or "").lower()
            ext = os.path.splitext(str(entry.get("path_hint") or ""))[1].lower()
            if artifact_type == "code" or ext == ".py":
                continue
            if artifact_type == "markdown" and ext in {"", ".md"}:
                # Markdown report aliases are usually handled by final synthesis.
                continue
            if artifact_type == final_artifact_type and not has_cross_type:
                continue
            if artifact_type in executable_types or ext in {".csv", ".json", ".txt"}:
                side_entries.append(entry)
        return side_entries

    def _missing_side_artifact_entries(
        self,
        output_contract: Optional[Any],
        final_record: RuntimeArtifactRecord,
    ) -> List[Dict[str, Any]]:
        registered_paths = {os.path.abspath(path) for path in self._registered_artifact_paths()}
        missing: List[Dict[str, Any]] = []
        for entry in self._side_artifact_entries_for_execution(
            output_contract,
            final_artifact_type=final_record.artifact_type,
        ):
            expected_path = os.path.abspath(entry["host_path"])
            if expected_path in registered_paths and os.path.isfile(expected_path):
                continue
            if os.path.isfile(expected_path) and self._is_current_run_artifact_path(expected_path):
                continue
            missing.append(entry)
        return missing

    @staticmethod
    def _python_script_has_executable_entry(source: str) -> bool:
        lowered = (source or "").lower()
        return bool(
            "if __name__" in lowered
            or "argparse" in lowered
            or re.search(r"^\s*def\s+main\s*\(", source or "", flags=re.MULTILINE)
        )

    def _current_run_executable_script_candidates(
        self,
        depends_on: Sequence[str],
        required_entries: Sequence[Dict[str, Any]],
    ) -> List[Tuple[int, RuntimeArtifactRecord]]:
        """Find current-run Python script artifacts suitable for side-output materialization."""
        dep_set = {str(item) for item in depends_on or [] if str(item)}
        required_basenames = {
            str(entry.get("basename") or "").lower()
            for entry in required_entries
            if entry.get("basename")
        }
        records: List[RuntimeArtifactRecord] = []
        records.extend(self.artifact_registry.source_overlays.values())
        records.extend(self.artifact_registry.by_task.values())
        records.extend(self.artifact_registry.by_step.values())

        scored: List[Tuple[int, RuntimeArtifactRecord]] = []
        seen_paths: Set[str] = set()
        for record in records:
            if str(record.artifact_type or "").lower() != "code":
                continue
            path = os.path.abspath(record.path)
            if path in seen_paths or not path.lower().endswith(".py") or not os.path.isfile(path):
                continue
            seen_paths.add(path)
            normalized_path = path.replace("\\", "/").lower()
            logical = str(record.metadata.get("original_workspace_path") or "").replace("\\", "/").lower()
            if "/tests/" in normalized_path or "/tests/" in logical or os.path.basename(path).lower().startswith("test_"):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    source = f.read()
            except OSError:
                continue
            has_entry = self._python_script_has_executable_entry(source)
            if not has_entry:
                continue
            score = 20
            source_task = str(record.metadata.get("source_task") or "")
            if source_task and source_task in dep_set:
                score += 50
            if "argparse" in source:
                score += 10
            if "--output-dir" in source or "--out-dir" in source:
                score += 8
            source_lower = source.lower()
            score += sum(5 for basename in required_basenames if basename and basename in source_lower)
            scored.append((score, record))

        scored.sort(key=lambda item: item[0], reverse=True)
        return scored

    @staticmethod
    def _script_cli_options(source: str) -> List[str]:
        options: List[str] = []
        seen: Set[str] = set()
        for match in re.finditer(r"add_argument\(\s*['\"](--[A-Za-z0-9_-]+)['\"]", source or ""):
            option = match.group(1)
            if option not in seen:
                seen.add(option)
                options.append(option)
        return options

    def _side_artifact_output_dir(self, entries: Sequence[Dict[str, Any]]) -> str:
        data_dirs = [
            os.path.dirname(os.path.abspath(entry["host_path"]))
            for entry in entries
            if str(entry.get("artifact_type") or "").lower() in {"csv", "json", "plaintext"}
        ]
        if not data_dirs:
            return os.path.abspath(self.artifact_dir)
        try:
            common = os.path.commonpath(data_dirs)
        except ValueError:
            return os.path.abspath(self.artifact_dir)
        return common if common else os.path.abspath(self.artifact_dir)

    def _resolved_input_files_from_packet(self, context_packet: Optional[Any]) -> List[str]:
        if context_packet is None:
            return []
        raw_files = getattr(context_packet, "resolved_local_files", None)
        if raw_files is None and isinstance(context_packet, dict):
            raw_files = context_packet.get("resolved_local_files")
        files: List[str] = []
        for item in raw_files or []:
            role = getattr(item, "role", None)
            path = getattr(item, "path", None)
            if isinstance(item, dict):
                role = item.get("role")
                path = item.get("path")
            if role and str(role) != "input":
                continue
            if not path:
                continue
            resolved = self._resolve_candidate_path(str(path))
            if os.path.isfile(resolved) and self._is_workspace_path(resolved):
                files.append(os.path.abspath(resolved))
        return files

    def _input_file_for_cli_option(self, option: str, input_files: Sequence[str]) -> Optional[str]:
        opt = option.lower().lstrip("-")
        scored: List[Tuple[int, str]] = []
        for path in input_files:
            basename = os.path.basename(path).lower()
            ext = os.path.splitext(basename)[1].lower()
            score = 0
            if "csv" in opt and ext == ".csv":
                score += 10
            if "json" in opt and ext == ".json":
                score += 8
            if "mapping" in opt and "mapping" in basename:
                score += 8
            if any(token in opt for token in ("input", "source", "raw", "orders", "order")) and ext == ".csv":
                score += 4
            for token in re.split(r"[^a-z0-9]+", os.path.splitext(basename)[0]):
                if len(token) >= 3 and token in opt:
                    score += 3
            if score > 0:
                scored.append((score, path))
        if not scored:
            return None
        scored.sort(key=lambda item: item[0], reverse=True)
        if len(scored) > 1 and scored[0][0] == scored[1][0]:
            return None
        return scored[0][1]

    def _output_file_for_cli_option(
        self,
        option: str,
        entries: Sequence[Dict[str, Any]],
    ) -> Optional[str]:
        opt = option.lower().lstrip("-")
        scored: List[Tuple[int, str]] = []
        for entry in entries:
            path = str(entry.get("host_path") or "")
            basename = os.path.basename(path).lower()
            ext = os.path.splitext(basename)[1].lower()
            score = 0
            if "csv" in opt and ext == ".csv":
                score += 10
            if "json" in opt and ext == ".json":
                score += 10
            if "clean" in opt and "clean" in basename:
                score += 8
            if "report" in opt and "report" in basename:
                score += 8
            if "output" in opt or "out" in opt:
                score += 2
            if score > 0:
                scored.append((score, path))
        if not scored:
            return None
        scored.sort(key=lambda item: item[0], reverse=True)
        if len(scored) > 1 and scored[0][0] == scored[1][0]:
            return None
        return scored[0][1]

    def _infer_side_artifact_runner_args(
        self,
        script_path: str,
        entries: Sequence[Dict[str, Any]],
        context_packet: Optional[Any],
    ) -> List[str]:
        if bool(getattr(self, "_formal_execution_active", False)):
            raise RuntimeError("formal_side_artifact_runner_inference_forbidden")
        try:
            with open(script_path, "r", encoding="utf-8") as f:
                source = f.read()
        except OSError:
            return []
        options = self._script_cli_options(source)
        if not options:
            return []
        output_dir = self._side_artifact_output_dir(entries)
        input_files = self._resolved_input_files_from_packet(context_packet)
        args: List[str] = []
        used_values: Set[str] = set()
        for option in options:
            opt = option.lower()
            value: Optional[str] = None
            if "output-dir" in opt or "out-dir" in opt or opt.endswith("output-dir"):
                value = output_dir
            elif ("output" in opt or opt.startswith("--out")) and ("dir" not in opt):
                value = self._output_file_for_cli_option(option, entries)
            else:
                value = self._input_file_for_cli_option(option, input_files)
            if not value:
                continue
            tool_value = self._to_tool_binding_value(value)
            if tool_value in used_values:
                continue
            used_values.add(tool_value)
            args.extend([option, tool_value])
        return args

    def _register_existing_required_outputs(
        self,
        task_id: str,
        step: ResourceApplicationStep,
        entries: Sequence[Dict[str, Any]],
    ) -> List[RuntimeArtifactRecord]:
        records: List[RuntimeArtifactRecord] = []
        for index, entry in enumerate(entries):
            path = os.path.abspath(str(entry.get("host_path") or ""))
            if not path or not os.path.isfile(path) or not self._is_workspace_path(path):
                continue
            artifact_type = self._artifact_type_from_path_hint(path, fallback=str(entry.get("artifact_type") or "plaintext"))
            record = RuntimeArtifactRecord(
                path=path,
                artifact_type=artifact_type,
                origin="tool_output",
                metadata={
                    "source_task": task_id,
                    "source_step": step.step_id,
                    "source_output": step.output_key,
                    "contract_path_hint": entry.get("path_hint"),
                    "tool_path": self._to_tool_path(path),
                },
            )
            key = f"{task_id}:{step.step_id}:{step.output_key}:contract_output_{index}"
            self.artifact_registry.by_step[key] = record
            records.append(record)
        return records

    @staticmethod
    def _normalized_artifact_key(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", str(value or "").replace("\\", "/").lower()).strip("_")

    def _textual_side_content_from_final_output(
        self,
        entry: Dict[str, Any],
        final_record: RuntimeArtifactRecord,
        output_data: str,
    ) -> Optional[str]:
        artifact_type = str(entry.get("artifact_type") or "").lower()
        if artifact_type not in {"markdown", "plaintext"}:
            return None
        if final_record.artifact_type in {"markdown", "plaintext"}:
            return output_data
        if final_record.artifact_type != "json":
            return None
        try:
            payload = json.loads(output_data or "{}")
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        basename = os.path.basename(str(entry.get("path_hint") or ""))
        stem = os.path.splitext(basename)[0]
        wanted_keys = {
            self._normalized_artifact_key(stem),
            self._normalized_artifact_key(basename),
            self._normalized_artifact_key(f"{stem}_{artifact_type}"),
            self._normalized_artifact_key(f"{stem}_md"),
            self._normalized_artifact_key(f"{stem}_content"),
        }
        scored: List[Tuple[int, str]] = []
        for key, value in payload.items():
            if not isinstance(value, str) or not value.strip():
                continue
            normalized_key = self._normalized_artifact_key(key)
            score = 0
            if normalized_key in wanted_keys:
                score += 50
            if stem and self._normalized_artifact_key(stem) in normalized_key:
                score += 20
            if artifact_type == "markdown" and any(marker in normalized_key for marker in ("markdown", "md", "report")):
                score += 10
            if "#" in value or "\n-" in value or "\n*" in value:
                score += 5
            if score > 0:
                scored.append((score, value))
        if not scored:
            return None
        scored.sort(key=lambda item: item[0], reverse=True)
        if len(scored) > 1 and scored[0][0] == scored[1][0]:
            return None
        return scored[0][1]

    def _materialize_textual_side_artifacts_from_final_output(
        self,
        task_id: str,
        output_contract: Optional[Any],
        final_record: RuntimeArtifactRecord,
        output_data: str,
    ) -> List[Dict[str, Any]]:
        if bool(getattr(self, "_formal_execution_active", False)):
            raise RuntimeError("formal_textual_side_artifact_materialization_forbidden")
        events: List[Dict[str, Any]] = []
        entries = self._required_produced_file_entries(
            output_contract,
            final_artifact_type=final_record.artifact_type,
        )
        for index, entry in enumerate(entries):
            artifact_type = str(entry.get("artifact_type") or "").lower()
            if artifact_type not in {"markdown", "plaintext"}:
                continue
            target_path = os.path.abspath(str(entry.get("host_path") or ""))
            if not target_path:
                continue
            if os.path.isfile(target_path) and self._is_current_run_artifact_path(target_path):
                continue
            content = self._textual_side_content_from_final_output(entry, final_record, output_data)
            if content is None or not str(content).strip():
                events.append(
                    {
                        "event": "textual_side_artifact_skipped",
                        "path_hint": entry.get("path_hint"),
                        "failure_type": "textual_side_artifact_content_missing",
                    }
                )
                continue
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)
                if not content.endswith("\n"):
                    f.write("\n")
            record = RuntimeArtifactRecord(
                path=target_path,
                artifact_type=artifact_type,
                origin="derived_final_artifact",
                metadata={
                    "source_task": task_id,
                    "source_step": "textual_side_artifact_materializer",
                    "source_output": "final_output",
                    "contract_path_hint": entry.get("path_hint"),
                    "tool_path": self._to_tool_path(target_path),
                },
            )
            key = f"{task_id}:textual_side_artifact_materializer:final_output:contract_text_{index}"
            self.artifact_registry.by_step[key] = record
            events.append(
                {
                    "event": "textual_side_artifact_materialized",
                    "path_hint": entry.get("path_hint"),
                    "tool_path": self._to_tool_path(target_path),
                    "artifact_type": artifact_type,
                }
            )
        return events

    def _materialize_side_artifacts_from_step_outputs(
        self,
        task_id: str,
        output_contract: Optional[Any],
        final_record: RuntimeArtifactRecord,
    ) -> List[Dict[str, Any]]:
        """Map an unambiguous same-type step artifact to a required side file."""
        events: List[Dict[str, Any]] = []
        missing_entries = self._missing_side_artifact_entries(output_contract, final_record)
        for index, entry in enumerate(missing_entries):
            artifact_type = str(entry.get("artifact_type") or "").lower()
            candidates: List[Tuple[str, RuntimeArtifactRecord]] = []
            for key, record in self.artifact_registry.by_step.items():
                if not str(key).startswith(f"{task_id}:"):
                    continue
                if str(record.artifact_type or "").lower() != artifact_type:
                    continue
                if not record.path or not os.path.isfile(record.path):
                    continue
                candidates.append((str(key), record))
            unique_paths = {os.path.abspath(record.path) for _, record in candidates}
            if len(unique_paths) != 1:
                if candidates:
                    events.append(
                        {
                            "event": "step_output_side_artifact_ambiguous",
                            "path_hint": entry.get("path_hint"),
                            "artifact_type": artifact_type,
                            "candidate_paths": sorted(unique_paths),
                        }
                    )
                continue
            source_key, source_record = candidates[0]
            target_path = os.path.abspath(str(entry.get("host_path") or ""))
            if not target_path:
                continue
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            if os.path.abspath(source_record.path) != target_path:
                shutil.copyfile(source_record.path, target_path)
            alias_record = RuntimeArtifactRecord(
                path=target_path,
                artifact_type=artifact_type,
                origin="contract_alias",
                metadata={
                    "source_task": task_id,
                    "source_step_record": source_key,
                    "contract_path_hint": entry.get("path_hint"),
                    "tool_path": self._to_tool_path(target_path),
                },
            )
            self.artifact_registry.by_step[
                f"{task_id}:contract_alias:step_output:{index}"
            ] = alias_record
            events.append(
                {
                    "event": "step_output_side_artifact_materialized",
                    "path_hint": entry.get("path_hint"),
                    "artifact_type": artifact_type,
                    "source_path": self._to_tool_path(source_record.path),
                    "tool_path": self._to_tool_path(target_path),
                }
            )
        return events

    async def _attempt_required_side_artifact_materialization(
        self,
        task_id: str,
        task: Dict[str, Any],
        output_contract: Optional[Any],
        final_record: RuntimeArtifactRecord,
        resource_index: Dict[str, dict],
        context_packet: Optional[Any],
    ) -> List[Dict[str, Any]]:
        """Execute an existing current-run Python script when required side files are missing."""
        if bool(getattr(self, "_formal_execution_active", False)):
            raise RuntimeError("formal_implicit_side_artifact_materialization_forbidden")
        if self.execution_substrate is not None:
            raise RuntimeError("external_side_artifact_materialization_requires_sealed_tool")
        missing_entries = self._missing_side_artifact_entries(output_contract, final_record)
        if not missing_entries:
            return []

        depends_on = list(task.get("depends_on") or [])
        candidates = self._current_run_executable_script_candidates(depends_on, missing_entries)
        trace: List[Dict[str, Any]] = [
            {
                "event": "side_artifact_materialization_needed",
                "missing": [
                    {
                        "path_hint": entry.get("path_hint"),
                        "artifact_type": entry.get("artifact_type"),
                        "tool_path": self._to_tool_path(entry.get("host_path")),
                    }
                    for entry in missing_entries
                ],
            }
        ]
        if not candidates:
            trace.append(
                {
                    "event": "side_artifact_materialization_skipped",
                    "failure_type": "side_artifact_script_missing",
                    "reason": "No current-run executable Python script artifact was available to materialize required side files.",
                }
            )
            return trace
        if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
            trace.append(
                {
                    "event": "side_artifact_materialization_skipped",
                    "failure_type": "side_artifact_script_ambiguous",
                    "candidates": [
                        {
                            "score": score,
                            "tool_path": self._artifact_handle_tool_path(record.path),
                            "source_task": record.metadata.get("source_task"),
                        }
                        for score, record in candidates[:5]
                    ],
                }
            )
            return trace

        _, script_record = candidates[0]
        runner_resource_id = "tool.python_script_runner.v1"
        runner_index = dict(resource_index or {})
        runner_index.setdefault(
            runner_resource_id,
            {
                "resource_type": "Tool",
                "execution": {"uri": "file://Pool/resources/tools/script/python_script_runner.py"},
                "input_contract": [
                    {"name": "script_path", "kind": "file_path", "required": True, "cli_position": 1}
                ],
            },
        )
        runner_ref = TypedResourceRef(resource_id=runner_resource_id, resource_type=ManifestType.TOOL)
        runner_step = ResourceApplicationStep(
            step_id="side_artifact_materializer",
            step_type="execute_generated_code",
            operation_kind=OperationKind.EXECUTE_SCRIPT,
            resource_id=runner_resource_id,
            intent="Execute a current-run Python script to materialize required produced_files declared by the task contract.",
            input_bindings={},
            output_key="side_artifact_execution_result",
        )
        args = self._infer_side_artifact_runner_args(script_record.path, missing_entries, context_packet)
        bindings: Dict[str, Any] = {"script_path": script_record.path, "cwd": "."}
        if args:
            bindings["arg_json"] = list(args)

        dependency_result = self._dependency_result_for_ref(runner_ref, runner_index)
        if dependency_result.is_blocked:
            dependency_failure_type = self._dependency_failure_type_for_result(
                dependency_result
            )
            trace.append(
                {
                    "event": "side_artifact_materialization_failed",
                    "failure_type": dependency_failure_type,
                    "reason": dependency_result.reason,
                }
            )
            return trace
        ok, failure_type, reason, command, command_args = self._build_tool_invocation_from_bindings(
            runner_ref,
            runner_index,
            bindings,
        )
        if not ok:
            trace.append(
                {
                    "event": "side_artifact_materialization_failed",
                    "failure_type": failure_type,
                    "reason": reason,
                }
            )
            return trace

        trace.append(
            {
                "event": "side_artifact_materialization_execute",
                "script_tool_path": self._to_tool_path(script_record.path),
                "source_task": script_record.metadata.get("source_task"),
                "args": args,
            }
        )
        runner_manifest = runner_index.get(runner_resource_id, {})
        allowed_packages = sorted(self._manifest_python_package_names(runner_manifest))
        _, missing_deps, dependency_scan = self._check_python_artifact_dependencies(
            source_path=script_record.path,
            allowed_packages=allowed_packages,
        )
        runtime_handle, preparation_event_id, preparation_failure = await self._prepare_step_runtime(
            task_id=task_id,
            step_id=runner_step.step_id,
            raw_manifest=runner_manifest,
            artifact_imports=missing_deps,
            artifact_source=f"generated_artifact:{task_id}:{runner_step.step_id}",
            execution_network_required=bool(
                (runner_manifest.get("runtime_requirements") or {}).get(
                    "network_required", False
                )
            ),
            phase="side_artifact",
        )
        trace[-1]["python_import_scan"] = dependency_scan
        trace[-1]["runtime_preparation_event_ids"] = [preparation_event_id]
        if preparation_failure is not None:
            trace.append(
                {
                    "event": "side_artifact_materialization_failed",
                    **preparation_failure,
                    "runtime_preparation_event_ids": [preparation_event_id],
                }
            )
            return trace
        dumb_exec = DumbExecutor(timeout_sec=180)
        result = await dumb_exec.execute(
            "Materialize required produced_files from current-run script.",
            "",
            command=command,
            args=command_args,
            runtime_environment=runtime_handle,
            network_required=bool(
                (runner_manifest.get("runtime_requirements") or {}).get(
                    "network_required", False
                )
            ),
        )
        if not result.is_success:
            failure_label, classified_reason = self._classify_runtime_failure(result)
            trace.append(
                {
                    "event": "side_artifact_materialization_failed",
                    "failure_type": failure_label,
                    "reason": classified_reason or result.error_log,
                }
            )
            return trace
        semantic_ok, semantic_failure, semantic_reason, semantic_status = self._semantic_tool_status_failure(
            runner_ref,
            result,
            "execute_generated_code",
        )
        trace.append(
            {
                "event": "side_artifact_materialization_runner_result",
                "semantic_status": semantic_status,
                "output_chars": len(result.output_data or ""),
            }
        )
        if not semantic_ok:
            trace.append(
                {
                    "event": "side_artifact_materialization_failed",
                    "failure_type": semantic_failure,
                    "reason": semantic_reason,
                }
            )
            return trace
        tool_records = self._register_tool_output_artifacts(task_id, runner_step, result.output_data)
        contract_records = self._register_existing_required_outputs(task_id, runner_step, missing_entries)
        trace.append(
            {
                "event": "side_artifact_materialization_registered",
                "tool_outputs": [
                    {"tool_path": self._artifact_handle_tool_path(record.path), "artifact_type": record.artifact_type}
                    for record in tool_records
                ],
                "contract_outputs": [
                    {"tool_path": self._artifact_handle_tool_path(record.path), "artifact_type": record.artifact_type}
                    for record in contract_records
                ],
            }
        )
        return trace

    def _sync_latest_attempt_artifact_status(self, routing: Dict[str, Any], result: Optional[ExecutionResult]) -> None:
        """Expose execution artifact lifecycle checks on the latest routing attempt/report."""
        if result is None:
            return
        session = routing.get("routing_session") if isinstance(routing, dict) else None
        attempts = getattr(session, "attempts", None)
        if not attempts:
            return
        attempt = attempts[-1]
        produced_status = result.cost_metric.get("produced_file_status")
        if isinstance(produced_status, list):
            attempt.produced_file_status = produced_status
        lineage_warnings = result.cost_metric.get("lineage_warnings")
        if isinstance(lineage_warnings, list):
            attempt.lineage_warnings = lineage_warnings

    def _build_artifact_profile(
        self,
        task_id: str,
        artifact_type: str,
        artifact_path: Optional[str],
        artifact: str,
        result: Optional[ExecutionResult],
    ) -> ArtifactProfile:
        observed: Dict[str, Any] = {}
        summary = f"{artifact_type} artifact, {len(artifact or '')} characters"
        registry_record = self._task_registry_record(task_id)
        aliases = list(registry_record.aliases) if registry_record else []
        if artifact_type == "code":
            try:
                tree = ast.parse(artifact or "")
                functions = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
                classes = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]
                observed["functions"] = functions
                observed["classes"] = classes
                observed["has_main_guard"] = "if __name__" in (artifact or "")
                summary = f"Python code with {len(functions)} functions and {len(classes)} classes"
            except Exception as exc:
                observed["parse_error"] = str(exc)
        elif artifact_type == "json":
            try:
                from .json_serialization import json_serialization_format, parse_json_content
                encoding = json_serialization_format({"artifact_type": artifact_type, "path_hint": artifact_path})
                parsed = parse_json_content(artifact or "{}", serialization_format=encoding, schema={})
                if encoding == "jsonl":
                    observed["serialization_format"] = encoding
                if isinstance(parsed, dict):
                    observed["top_level_keys"] = list(parsed.keys())[:40]
                    summary = f"JSON artifact with keys: {', '.join(observed['top_level_keys'][:8])}"
                elif isinstance(parsed, list):
                    observed["list_length"] = len(parsed)
                    summary = f"JSON list artifact with {len(parsed)} items"
            except Exception as exc:
                observed["parse_error"] = str(exc)
        else:
            headings = re.findall(r"^\s{0,3}#{1,6}\s+(.+)$", artifact or "", flags=re.MULTILINE)
            observed["headings"] = headings[:20]
            summary = f"{artifact_type} artifact with {len(headings)} markdown headings"

        files = self._extract_profile_files(artifact or "", result)
        if files:
            observed["files"] = files
            observed["file_origins"] = {
                item: (
                    "current_run_artifact"
                    if registry_record and item in {registry_record.path, *registry_record.aliases}
                    else "mentioned_path"
                )
                for item in files
            }
        if aliases:
            observed["aliases"] = aliases

        issues: List[str] = []
        status = "passed" if result is not None and result.is_success else "not_run"
        if result is not None and isinstance(result.cost_metric.get("evaluation_result"), dict):
            eval_result = result.cost_metric["evaluation_result"]
            if eval_result.get("verdict") == "fail":
                status = "failed"
            issues = list(eval_result.get("critical_issues") or [])
        handoff_notes: List[str] = []
        if observed.get("functions"):
            handoff_notes.append(
                "Downstream code/test tasks can import: "
                + ", ".join(observed["functions"][:8])
            )
        if files:
            origins = observed.get("file_origins", {})
            registered = [item for item in files if origins.get(item) == "current_run_artifact"]
            mentioned = [item for item in files if origins.get(item) != "current_run_artifact"]
            if registered:
                handoff_notes.append("Downstream tasks can use registered files: " + ", ".join(registered[:8]))
            if mentioned:
                handoff_notes.append(
                    "Text mentions file-like paths that are not execution targets unless registered: "
                    + ", ".join(mentioned[:8])
                )
        return ArtifactProfile(
            task_id=task_id,
            artifact_type=artifact_type,
            artifact_path=artifact_path,
            artifact_aliases=aliases,
            summary=summary,
            observed_outputs=observed,
            validation=ArtifactValidationProfile(status=status, issues=issues),
            handoff_notes=handoff_notes,
        )

    def _required_function_names_from_contract_text(self, text: str) -> List[str]:
        names: List[str] = []
        seen: Set[str] = set()
        ignored = {
            "if",
            "for",
            "while",
            "return",
            "print",
            "open",
            "Path",
            "str",
            "int",
            "float",
            "bool",
            "list",
            "dict",
            "set",
            "len",
            "range",
            "json",
            "loads",
            "dumps",
            "datetime",
            "timezone",
            "timedelta",
            "date",
            "pytest",
            "mock",
            "assert",
            "email",
        }
        patterns = [
            r"(?i)\b(?:define|implement|expose|export|provide|include|declare)\s+(?:a\s+)?(?:python\s+)?(?:function|method|def)\s+`?([A-Za-z_][A-Za-z0-9_]*)`?",
            r"(?i)\b(?:exports?|exposes?|provides?)\s+`?([A-Za-z_][A-Za-z0-9_]*)`?\s+(?:function|method)",
            r"(?i)\b(?:function|method|def)\s*[:=]\s*`?([A-Za-z_][A-Za-z0-9_]*)`?",
            r"(?i)\b(?:must|should)\s+(?:define|implement|expose|export|provide|include)\s+`?([A-Za-z_][A-Za-z0-9_]*)`?",
            r"(?i)\b(?:exporting|exposing)\s+`?([A-Za-z_][A-Za-z0-9_]*)`?",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text or ""):
                name = match.group(1)
                if name in ignored or name.lower() in ignored or name in seen:
                    continue
                seen.add(name)
                names.append(name)
        return names[:20]

    def _required_class_names_from_contract_text(self, text: str) -> List[str]:
        names: List[str] = []
        seen: Set[str] = set()
        patterns = [
            r"(?i)\b(?:define|implement|expose|export|provide|include|declare)\s+(?:a\s+)?(?:python\s+)?class\s+`?([A-Za-z_][A-Za-z0-9_]*)`?",
            r"(?i)\bclass\s*[:=]\s*`?([A-Za-z_][A-Za-z0-9_]*)`?",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text or ""):
                name = match.group(1)
                if name in seen:
                    continue
                seen.add(name)
                names.append(name)
        return names[:20]

    def _interface_names_from_output_contract(
        self,
        output_contract: Optional[SubtaskOutputContract],
    ) -> Tuple[List[str], List[str]]:
        if output_contract is None:
            return [], []
        interface = getattr(output_contract, "interface_contract", {}) or {}
        if not isinstance(interface, dict):
            return [], []

        def normalize(value: Any) -> List[str]:
            raw_items: List[Any]
            if isinstance(value, str):
                raw_items = re.split(r"[,;\s]+", value)
            elif isinstance(value, dict):
                raw_items = list(value.values())
            elif isinstance(value, (list, tuple, set)):
                raw_items = list(value)
            else:
                raw_items = []
            names: List[str] = []
            seen: Set[str] = set()
            for item in raw_items:
                text = str(item or "").strip().strip("`'\"")
                if not text:
                    continue
                match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)", text)
                if not match:
                    continue
                name = match.group(1)
                if name not in seen:
                    seen.add(name)
                    names.append(name)
            return names

        functions = normalize(
            interface.get("functions")
            or interface.get("function")
            or interface.get("required_functions")
            or interface.get("exports")
        )
        classes = normalize(
            interface.get("classes")
            or interface.get("class")
            or interface.get("required_classes")
        )
        return functions[:20], classes[:20]

    def _required_python_interfaces(
        self,
        contract_text: str,
        output_contract: Optional[SubtaskOutputContract] = None,
    ) -> Tuple[List[str], List[str], str]:
        functions, classes = self._interface_names_from_output_contract(output_contract)
        if functions or classes:
            return functions, classes, "structured_output_contract"
        return (
            self._required_function_names_from_contract_text(contract_text),
            self._required_class_names_from_contract_text(contract_text),
            "explicit_contract_text",
        )

    def _python_interface_satisfied(self, required: str, existing: Set[str]) -> bool:
        if required in existing:
            return True
        if required.startswith("test_"):
            prefix = required + "_"
            return any(name.startswith(prefix) for name in existing)
        return False

    def _is_test_artifact_contract(
        self,
        expected: str,
        output_contract: Optional[SubtaskOutputContract] = None,
    ) -> bool:
        def path_looks_like_test(path_hint: str) -> bool:
            normalized = path_hint.replace("\\", "/").lower()
            basename = os.path.basename(normalized)
            return (
                "/tests/" in f"/{normalized}"
                or basename.startswith("test_")
                or basename.endswith("_test.py")
            )

        text_parts = [expected or ""]
        if output_contract is not None:
            produced_paths: List[str] = []
            for produced in output_contract.produced_files or []:
                path_hint = str(getattr(produced, "path_hint", "") or "")
                if path_hint:
                    produced_paths.append(path_hint)
                    if path_looks_like_test(path_hint):
                        return True
                    text_parts.append(path_hint)
            if produced_paths:
                return False
            text_parts.extend(output_contract.required_content or [])
            text_parts.extend(output_contract.acceptance_criteria or [])
        text = "\n".join(str(part or "") for part in text_parts).lower()
        return any(
            marker in text
            for marker in (
                "unit test",
                "pytest test",
                'pytest \u6d4b\u8bd5',
                "test file",
                "test code",
                "test_",
                "tests/",
                '\u6d4b\u8bd5\u6587\u4ef6',
                '\u6d4b\u8bd5\u4ee3\u7801',
                '\u6d4b\u8bd5\u7528\u4f8b',
            )
        )

    def _python_code_looks_like_test_artifact(self, tree: ast.AST) -> bool:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                return True
            if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                return True
            if isinstance(node, ast.Assert):
                return True
        return False

    def _append_missing_interface_aliases(self, code: str, contract_text: str) -> Tuple[str, List[str]]:
        required = self._required_function_names_from_contract_text(contract_text)
        if not required:
            return code, []
        try:
            tree = ast.parse(code or "")
        except SyntaxError:
            return code, []
        existing = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        aliases: List[str] = []
        additions: List[str] = []
        for required_name in required:
            if required_name in existing:
                continue
            suffix = required_name.split("_", 1)[-1] if "_" in required_name else required_name
            candidates = [
                name for name in existing
                if name.endswith("_" + suffix) or name == suffix
            ]
            if not candidates:
                continue
            target = sorted(candidates, key=len)[0]
            additions.append(
                "\n\n"
                f"def {required_name}(*args, **kwargs):\n"
                f"    return {target}(*args, **kwargs)\n"
            )
            aliases.append(f"{required_name}->{target}")
            existing.add(required_name)
        if not additions:
            return code, []
        updated = (code.rstrip() + "".join(additions) + "\n")
        try:
            ast.parse(updated)
        except SyntaxError:
            return code, []
        return updated, aliases

    def _check_code_interface_contract(
        self,
        code: str,
        expected: str,
        output_contract: Optional[SubtaskOutputContract] = None,
    ) -> Tuple[bool, str]:
        """Deterministically verify required top-level Python functions when a contract names them."""
        required_functions, required_classes, source = self._required_python_interfaces(
            expected,
            output_contract,
        )
        if not required_functions and not required_classes:
            return True, ""
        try:
            tree = ast.parse(code or "")
        except SyntaxError as exc:
            return False, f"code_syntax_error: {exc}"
        existing_functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        existing_classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
        if self._is_test_artifact_contract(expected, output_contract):
            # A test artifact may import/call business functions listed by the planner;
            # it should only be required to define test-facing interfaces.
            required_functions = [name for name in required_functions if name.startswith("test_")]
            required_classes = [name for name in required_classes if name.startswith("Test")]
            if not required_functions and not required_classes:
                if self._python_code_looks_like_test_artifact(tree):
                    return True, ""
                return (
                    False,
                    "Missing pytest-style test content"
                    f" ({source}): expected at least one test_ function, Test class, or assert statement",
                )
        missing_functions = [
            name for name in required_functions
            if not self._python_interface_satisfied(name, existing_functions)
        ]
        missing_classes = [
            name for name in required_classes
            if not self._python_interface_satisfied(name, existing_classes)
        ]
        if missing_functions:
            return (
                False,
                "Missing required Python interface functions"
                f" ({source}): " + ", ".join(missing_functions[:12]),
            )
        if missing_classes:
            return (
                False,
                "Missing required Python interface classes"
                f" ({source}): " + ", ".join(missing_classes[:12]),
            )
        return True, ""

    def _build_context_packet(
        self,
        task: Dict[str, Any],
        task_list: List[Dict[str, Any]],
        memory_manager: Any,
        context_data: str,
        resolved_file_context: str,
    ) -> ContextPacket:
        task_id = task.get("id", "")
        depends_on = list(task.get("depends_on", []))
        output_contract = self._derive_output_contract_from_task(task)
        upstream_profiles = [
            memory_manager.artifact_profiles[dep_id]
            for dep_id in depends_on
            if dep_id in getattr(memory_manager, "artifact_profiles", {})
        ]
        availability = {
            dep_id: "available_as_context"
            for dep_id in depends_on
            if dep_id in getattr(memory_manager, "artifacts", {}) or dep_id in self.context.artifacts
        }
        source_texts: List[Tuple[str, str]] = [
            ("current_subtask", str(task.get("description") or "")),
            ("current_subtask", str(task.get("expected_output") or "")),
        ]
        for requirement in output_contract.grounding_requirements:
            source_texts.append(("grounding_requirement", str(requirement)))

        resolved_files: List[ResolvedLocalFileProfile] = []
        seen_paths: Set[str] = set()
        for origin, text in source_texts:
            for path in self._extract_existing_file_paths(text):
                if path in seen_paths:
                    continue
                seen_paths.add(path)
                role = "input"
                normalized = path.replace("\\", "/").lower()
                if "/output/" in normalized or normalized.endswith("/output"):
                    role = "mentioned_output"
                    origin = "preexisting_output"
                resolved_files.append(
                    ResolvedLocalFileProfile(
                        path=path,
                        status="available",
                        content_available_as_context=path in resolved_file_context and role == "input",
                        origin=origin,
                        role=role,
                    )
                )
                if role == "input":
                    self._known_local_file_paths.add(path)
        incoming_edges = list(task.get("incoming_edge_contracts") or ())
        outgoing_edges = [
            dict(edge)
            for other in task_list
            for edge in (other.get("incoming_edge_contracts") or ())
            if isinstance(edge, Mapping)
            and str(edge.get("producer_id") or "") == task_id
        ]
        incoming_semantic_edges_v2 = list(task.get("incoming_semantic_edges_v2") or ())
        outgoing_semantic_edges_v2 = [
            dict(edge)
            for other in task_list
            for edge in (other.get("incoming_semantic_edges_v2") or ())
            if isinstance(edge, Mapping)
            and str(edge.get("producer_id") or "") == task_id
        ]
        semantic_contract_v2 = task.get("semantic_contract_v2") or {}
        authorized_public_input_refs = sorted(
            {
                str(item.get("ref") or "").strip()
                for item in (
                    semantic_contract_v2.get("authorized_inputs") or ()
                    if isinstance(semantic_contract_v2, Mapping)
                    else ()
                )
                if isinstance(item, Mapping)
                and str(item.get("source") or "").strip() == "public_input"
                and str(item.get("ref") or "").strip()
            }
        )
        downstream = [
            DownstreamConsumptionHint(
                consumer_id=str(edge.get("consumer_id") or ""),
                expects=(
                    f"input_slot={edge.get('input_slot')};"
                    f"consumption_mode={edge.get('consumption_mode')}"
                ),
                edge_contract_sha256=str(edge.get("edge_contract_sha256") or ""),
            )
            for edge in outgoing_edges
        ]
        input_file_handles = self.workspace_handle_resolver.input_file_handles(resolved_files)
        self._register_input_file_handles(input_file_handles)
        explicit_input_handles = (
            list(self.artifact_registry.input_file_handles.values())
            if self.explicit_input_only
            else []
        )
        packet_handles: list[ArtifactHandle] = []
        seen_handle_ids: set[str] = set()
        for handle in (
            self.workspace_handle_resolver.registry_artifact_handles(depends_on)
            + explicit_input_handles
            + input_file_handles
        ):
            if handle.handle_id in seen_handle_ids:
                continue
            seen_handle_ids.add(handle.handle_id)
            packet_handles.append(handle)
        return ContextPacket(
            current_subtask={
                "id": task_id,
                "description": task.get("description", ""),
                "artifact_type": task.get("artifact_type", "plaintext"),
                "task_stage": task.get("task_stage") or "",
                "semantic_contract_protocol": str(
                    semantic_contract_v2.get("protocol") or ""
                )
                if isinstance(semantic_contract_v2, Mapping)
                else "",
                "authorized_public_input_refs": authorized_public_input_refs,
            },
            current_output_contract=output_contract.model_dump(mode="json"),
            upstream_artifact_profiles=upstream_profiles,
            upstream_context_availability=availability,
            resolved_local_files=resolved_files,
            downstream_consumption=downstream,
            incoming_edge_contracts=incoming_edges,
            outgoing_edge_contracts=outgoing_edges,
            incoming_semantic_edges_v2=incoming_semantic_edges_v2,
            outgoing_semantic_edges_v2=outgoing_semantic_edges_v2,
            artifact_handles=packet_handles,
            validation_handles=self.workspace_handle_resolver.validation_result_handles(depends_on),
            handle_resolution_rules={
                "tool_targets_must_use_handle": True,
                "raw_workspace_paths_are_inputs_only": True,
            },
        )

    def _validate_committed_dependency_edge(
        self,
        *,
        task: Mapping[str, Any],
        producer_id: str,
        consumer_revision: "SubtaskRevisionRef | None" = None,
    ) -> tuple[str, str] | None:
        """Validate one committed upstream handoff against its immutable edge."""

        matching = [
            DagEdgeContractV1.model_validate(item)
            for item in (task.get("incoming_edge_contracts") or ())
            if isinstance(item, Mapping)
            and str(item.get("producer_id") or "") == producer_id
            and str(item.get("consumer_id") or "") == str(task.get("id") or "")
        ]
        if len(matching) != 1:
            return "framework", "dag_edge_contract_missing_or_duplicate"
        edge = matching[0]
        manifest = self.context.committed_manifest_for(producer_id)
        if manifest is None:
            return "framework", "dependency_committed_manifest_missing"
        if manifest.visibility != "committed":
            return "framework", "dependency_artifact_not_committed"
        revision = manifest.artifact_revision.subtask_revision
        if revision.subtask_id != edge.producer_id or (
            revision.subtask_revision != edge.producer_subtask_revision
        ):
            return "framework", "dependency_revision_identity_mismatch"
        # Planner semantics and the refined execution contract are different
        # objects. Identity checks apply to the accepted artifact, not equality
        # between those two stages of contract construction.
        run_id = getattr(getattr(self, "execution_ledger", None), "run_id", None)
        if run_id and manifest.artifact_revision.run_id != run_id:
            return "framework", "dependency_run_identity_mismatch"
        if consumer_revision is not None and revision.graph_revision != consumer_revision.graph_revision:
            return "framework", "dependency_revision_identity_mismatch"
        artifact_type = normalize_artifact_type(manifest.artifact_type)
        expected_artifact_type = normalize_artifact_type(edge.producer_artifact_type)
        extension = str(manifest.extension or "").strip().lower()
        descriptor = manifest.artifact_v2
        # `file` is a representation, while publication may identify the
        # concrete format as binary, JSON, image, etc. Keep declared concrete
        # formats strict; a generic file edge consumes the verified file.
        generic_file = (
            expected_artifact_type == "file"
            and descriptor is not None
            and getattr(descriptor.representation, "value", descriptor.representation) == "file"
        )
        if artifact_type != expected_artifact_type and not generic_file:
            return "research", "dependency_artifact_type_mismatch"
        if (edge.producer_output_extension or not generic_file) and extension != edge.producer_output_extension:
            return "research", "dependency_artifact_extension_mismatch"
        if generic_file:
            accepted_types = {normalize_artifact_type(item) for item in edge.accepted_artifact_types}
            if accepted_types and "file" not in accepted_types and artifact_type not in accepted_types:
                return "research", "dependency_artifact_type_mismatch"
            if edge.accepted_extensions and extension not in edge.accepted_extensions:
                return "research", "dependency_artifact_extension_mismatch"
        if descriptor is not None and (
            normalize_artifact_type(descriptor.format_id) != artifact_type
            or str(descriptor.extension or "").strip().lower() != extension
        ):
            return "research", "dependency_artifact_descriptor_mismatch"
        matching_handles = [
            handle
            for handle in self._registry_artifact_handles((producer_id,))
            if handle.producer_task == producer_id and handle.kind == "task_final"
        ]
        if len(matching_handles) != 1:
            return "framework", "dependency_artifact_handle_missing"
        store = getattr(self.context, "artifact_store", None)
        if store is not None:
            try:
                store.validate_manifest_content(manifest)
                handle_path = Path(matching_handles[0].host_path or "").resolve()
                if handle_path != store.artifact_path(manifest).resolve():
                    return "framework", "dependency_artifact_handle_identity_mismatch"
            except (OSError, RuntimeError, ValueError):
                return "framework", "dependency_artifact_content_drift"
        required_interface = json.loads(edge.required_interface_contract_json)
        if required_interface:
            from .planner_contracts import _mapping_contains
            actual = matching_handles[0].provenance.get("execution_contract", {}).get("interface_contract", {})
            if not _mapping_contains(actual, required_interface):
                return "research", "dependency_interface_contract_mismatch"
        return None

    @staticmethod
    def refresh_ready_queue(
        task_graph: Dict[str, Subtask],
        processed_ids: Set[str],
        ready_queue: List[str],
    ) -> None:
        """
        Recompute ready nodes safely without mutating a dict during iteration.
        """
        queued_ids: Set[str] = set(ready_queue)
        for node_id in list(task_graph.keys()):
            if node_id in processed_ids or node_id in queued_ids:
                continue

            node = task_graph.get(node_id)
            if node is None:
                continue

            deps = list(node.depends_on)
            if all((dep in processed_ids) or (dep not in task_graph) for dep in deps):
                ready_queue.append(node_id)
                queued_ids.add(node_id)

    @staticmethod
    def apply_dag_patch(
        task_graph: Dict[str, Subtask],
        ready_queue: List[str],
        processed_ids: Set[str],
        patch: DAGPatch,
    ) -> None:
        """
        Hot-swap a local DAG subgraph safely and keep scheduler state consistent.
        """
        target_id = patch.target_node_id
        replacement_ids = [node.id for node in patch.new_nodes]

        processed_ids.discard(target_id)
        if target_id in task_graph:
            del task_graph[target_id]
        ready_queue[:] = [node_id for node_id in ready_queue if node_id != target_id]

        for new_node in list(patch.new_nodes):
            task_graph[new_node.id] = new_node
            processed_ids.discard(new_node.id)

        for downstream_id, new_depends in list(patch.downstream_updates.items()):
            downstream_node = task_graph.get(downstream_id)
            if downstream_node is None:
                logger.warning(
                    f"[Reflection] downstream node missing during patch apply: {downstream_id}"
                )
                continue
            downstream_node.depends_on = list(dict.fromkeys(new_depends))

        for node_id, node in list(task_graph.items()):
            deps = list(node.depends_on)
            if target_id not in deps:
                continue

            filtered = [dep for dep in deps if dep != target_id]
            for replacement_id in replacement_ids:
                if replacement_id not in filtered:
                    filtered.append(replacement_id)
            node.depends_on = filtered

        deduped_queue: List[str] = []
        seen_ids: Set[str] = set()
        for node_id in list(ready_queue):
            if node_id in seen_ids:
                continue
            if node_id not in task_graph or node_id in processed_ids:
                continue
            deduped_queue.append(node_id)
            seen_ids.add(node_id)
        ready_queue[:] = deduped_queue

    # -- Router Auto-Evaluation -----------------
    
    async def _router_fix_command(
        self,
        original_cmd: str,
        original_args: list,
        error_log: str,
        *,
        subtask_id: str | None = None,
    ) -> tuple[str, list]:
        """Tier 1 Healing: Ask LLM to fix a broken Bypass command."""
        prompt = (
            "The following local command failed during execution.\n"
            f"Command: {original_cmd}\n"
            f"Args: {original_args}\n\n"
            f"Error Log:\n{error_log}\n\n"
            "Try to repair the command generically. For example, if a data file "
            "was incorrectly executed as a Python script, return the correct script "
            "command and arguments. Return strict JSON with fields 'command' and 'args'."
        )
        try:
            api_kwargs = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            }
            try:
                accounting_context = (
                    self.cost_ledger.new_operation(
                        stage="command_adaptation",
                        subtask_id=subtask_id,
                        subtask_revision=(0 if subtask_id else None),
                    )
                    if self.cost_ledger is not None
                    else None
                )
                resp = await async_create_chat_completion_with_compat(
                    self.async_model_transport,
                    registry=GLOBAL_CAPABILITY_REGISTRY,
                    cost_ledger=self.cost_ledger,
                    accounting_context=accounting_context,
                    **api_kwargs,
                )
            except Exception as exc:
                if not is_response_format_unsupported_error(exc):
                    raise
                GLOBAL_CAPABILITY_REGISTRY.record_failure(
                    self.model,
                    "json_mode_ok",
                    "capability_unsupported",
                    str(exc),
                )
                api_kwargs.pop("response_format", None)
                prompt += "\n\nReturn exactly one valid JSON object as plain text."
                api_kwargs["messages"] = [{"role": "user", "content": prompt}]
                accounting_context = (
                    self.cost_ledger.new_operation(
                        stage="command_adaptation",
                        subtask_id=subtask_id,
                        subtask_revision=(0 if subtask_id else None),
                    )
                    if self.cost_ledger is not None
                    else None
                )
                resp = await async_create_chat_completion_with_compat(
                    self.async_model_transport,
                    registry=GLOBAL_CAPABILITY_REGISTRY,
                    cost_ledger=self.cost_ledger,
                    accounting_context=accounting_context,
                    **api_kwargs,
                )

            import json
            fix_data = json.loads(resp.choices[0].message.content)
            return fix_data.get("command", original_cmd), fix_data.get("args", original_args)
        except (ModelAccountingError, ModelTransportError):
            raise
        except Exception as e:
            logger.warning(f"[Warning] [_router_fix_command] Failed to parse fix: {e}")
            return original_cmd, original_args

    def _default_evaluation_result(
        self,
        verdict: EvaluationVerdict,
        failure_type: EvaluationFailureType,
        reason: str,
        *,
        confidence: float = 0.0,
        profile_used: bool = False,
        escalated_full_output: bool = False,
        training_label: TrainingLabel = TrainingLabel.EVALUATOR_NOISE,
    ) -> EvaluationResult:
        return EvaluationResult(
            verdict=verdict,
            passed=verdict == EvaluationVerdict.PASS,
            confidence=confidence,
            failure_type=failure_type,
            dimension_scores=EvaluationDimensionScores(),
            critical_issues=[reason[:240]] if reason else [],
            repair_hint=None if verdict != EvaluationVerdict.FAIL else reason[:300],
            training_label=training_label,
            profile_used=profile_used,
            escalated_full_output=escalated_full_output,
            evaluator_model=self.model,
        )

    def _extract_json_object(self, text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("```"):
            blocks = re.findall(r"```(?:json)?\s*\n?(.*?)```", stripped, re.DOTALL | re.IGNORECASE)
            if blocks:
                stripped = max(blocks, key=len).strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            return stripped
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            return stripped[start:end + 1]
        return stripped

    def _normalize_evaluation_result(
        self,
        raw_text: str,
        *,
        profile_used: bool,
        escalated_full_output: bool,
    ) -> EvaluationResult:
        try:
            data = json.loads(self._extract_json_object(raw_text))
            if isinstance(data, dict):
                data = self._coerce_evaluation_payload(data)
            result = EvaluationResult.model_validate(data)
        except Exception as exc:
            salvaged = self._salvage_evaluation_result(
                raw_text,
                profile_used=profile_used,
                escalated_full_output=escalated_full_output,
            )
            if salvaged is not None:
                return salvaged
            return self._default_evaluation_result(
                EvaluationVerdict.INCONCLUSIVE,
                EvaluationFailureType.EVALUATOR_INCONCLUSIVE,
                f"Evaluator returned invalid JSON: {exc}",
                confidence=0.0,
                profile_used=profile_used,
                escalated_full_output=escalated_full_output,
                training_label=TrainingLabel.EVALUATOR_NOISE,
            )

        issues = [str(item)[:240] for item in result.critical_issues[:3]]
        repair_hint = result.repair_hint[:300] if result.repair_hint else None
        verdict = result.verdict
        failure_type = result.failure_type
        if verdict == EvaluationVerdict.PASS:
            failure_type = EvaluationFailureType.NONE
        elif verdict == EvaluationVerdict.INCONCLUSIVE:
            failure_type = EvaluationFailureType.EVALUATOR_INCONCLUSIVE
        return result.model_copy(
            update={
                "passed": verdict == EvaluationVerdict.PASS,
                "failure_type": failure_type,
                "critical_issues": issues,
                "repair_hint": repair_hint,
                "profile_used": profile_used,
                "escalated_full_output": escalated_full_output,
                "evaluator_model": self.model,
            }
        )

    def _coerce_evaluation_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Fill safe defaults for minor evaluator schema drift."""
        normalized = dict(data)
        verdict = str(normalized.get("verdict") or "inconclusive").lower()
        if verdict not in {"pass", "fail", "inconclusive"}:
            verdict = "inconclusive"
        normalized["verdict"] = verdict
        normalized["passed"] = bool(normalized.get("passed", verdict == "pass"))

        failure_type = normalized.get("failure_type")
        if not failure_type:
            if verdict == "pass":
                failure_type = EvaluationFailureType.NONE.value
            elif verdict == "inconclusive":
                failure_type = EvaluationFailureType.EVALUATOR_INCONCLUSIVE.value
            else:
                failure_type = EvaluationFailureType.CONTRACT_VIOLATION.value
        try:
            normalized["failure_type"] = EvaluationFailureType(str(failure_type)).value
        except ValueError:
            normalized["failure_type"] = EvaluationFailureType.CONTRACT_VIOLATION.value

        dims = normalized.get("dimension_scores")
        if not isinstance(dims, dict):
            dims = {}
        for key in (
            "format_compliance",
            "contract_coverage",
            "dependency_grounding",
            "factual_consistency",
            "completeness",
            "actionability",
        ):
            try:
                dims[key] = min(max(float(dims.get(key, 0.0)), 0.0), 1.0)
            except (TypeError, ValueError):
                dims[key] = 0.0
        normalized["dimension_scores"] = dims

        issues = normalized.get("critical_issues", [])
        if isinstance(issues, str):
            issues = [issues]
        if not isinstance(issues, list):
            issues = []
        normalized["critical_issues"] = [str(item)[:240] for item in issues[:3]]

        repair_hint = normalized.get("repair_hint")
        normalized["repair_hint"] = str(repair_hint)[:300] if repair_hint else None

        label = normalized.get("training_label")
        if not label:
            label = (
                TrainingLabel.GOOD_CASE.value
                if verdict == "pass"
                else TrainingLabel.EVALUATOR_NOISE.value
                if verdict == "inconclusive"
                else TrainingLabel.REPAIRABLE_CASE.value
            )
        try:
            normalized["training_label"] = TrainingLabel(str(label)).value
        except ValueError:
            normalized["training_label"] = TrainingLabel.EVALUATOR_NOISE.value
        return normalized

    def _salvage_evaluation_result(
        self,
        raw_text: str,
        *,
        profile_used: bool,
        escalated_full_output: bool,
    ) -> Optional[EvaluationResult]:
        """Recover a useful verdict from malformed-but-readable evaluator JSON."""
        verdict_match = re.search(
            r'"verdict"\s*:\s*"(pass|fail|inconclusive)"',
            raw_text,
            flags=re.IGNORECASE,
        )
        if not verdict_match:
            return None
        verdict = EvaluationVerdict(verdict_match.group(1).lower())
        failure_match = re.search(
            r'"failure_type"\s*:\s*"([^"]+)"',
            raw_text,
            flags=re.IGNORECASE,
        )
        failure_type = EvaluationFailureType.EVALUATOR_INCONCLUSIVE
        if failure_match:
            try:
                failure_type = EvaluationFailureType(failure_match.group(1))
            except ValueError:
                failure_type = EvaluationFailureType.CONTRACT_VIOLATION
        elif verdict == EvaluationVerdict.PASS:
            failure_type = EvaluationFailureType.NONE
        elif verdict == EvaluationVerdict.FAIL:
            failure_type = EvaluationFailureType.CONTRACT_VIOLATION

        label = (
            TrainingLabel.GOOD_CASE
            if verdict == EvaluationVerdict.PASS
            else TrainingLabel.EVALUATOR_NOISE
            if verdict == EvaluationVerdict.INCONCLUSIVE
            else TrainingLabel.REPAIRABLE_CASE
        )
        reason = "Evaluator JSON was malformed; salvaged verdict from partial output."
        return self._default_evaluation_result(
            verdict,
            failure_type,
            reason,
            confidence=0.35,
            profile_used=profile_used,
            escalated_full_output=escalated_full_output,
            training_label=label,
        )

    def _artifact_profile(
        self,
        expected_output: str,
        actual_output: str,
        artifact_type: str = "plaintext",
        output_contract: Mapping[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Build a compact, evidence-preserving artifact profile for evaluation."""
        text = actual_output or ""
        profile: Dict[str, Any] = {
            "artifact_type": artifact_type,
            "char_count": len(text),
            "first_excerpt": text[:1600],
            "last_excerpt": text[-1600:] if len(text) > 1600 else "",
        }
        if artifact_type == "json":
            try:
                from .json_serialization import json_serialization_format, parse_json_content
                contract = output_contract or {"artifact_type": artifact_type}
                encoding = json_serialization_format(contract)
                parsed = parse_json_content(text, serialization_format=encoding,
                                            schema=contract.get("json_schema", contract.get("schema_hint")) or {})
                if encoding == "jsonl":
                    profile["serialization_format"] = encoding
                profile["json_parse_ok"] = True
                if isinstance(parsed, dict):
                    profile["top_level_keys"] = list(parsed.keys())[:80]
                elif isinstance(parsed, list):
                    profile["top_level_type"] = "list"
                    profile["list_length"] = len(parsed)
            except Exception as exc:
                profile["json_parse_ok"] = False
                profile["json_error"] = str(exc)[:240]
        elif artifact_type == "markdown":
            headings = re.findall(r"^(#{1,6})\s+(.+)$", text, flags=re.MULTILINE)
            profile["headings"] = [
                {"level": len(level), "title": title.strip()[:160]}
                for level, title in headings[:80]
            ]
            profile["tables_detected"] = len(re.findall(r"^\s*\|.+\|\s*$", text, flags=re.MULTILINE))
            code_blocks = re.findall(r"```(\w+)?\s*\n(.*?)```", text, flags=re.DOTALL)
            profile["code_blocks"] = [
                {
                    "language": lang or "",
                    "char_count": len(block),
                    "excerpt": block[:400],
                }
                for lang, block in code_blocks[:12]
            ]
        else:
            profile["line_count"] = len(text.splitlines())

        expected_terms = [
            term.strip("`*_:-:,.;()[]{} ")
            for term in re.split('[\\s,/\uff0c\u3002\uff1b;\u3001]+', expected_output or "")
            if len(term.strip("`*_:-:,.;()[]{} ")) >= 3
        ]
        unique_terms = list(dict.fromkeys(expected_terms))[:80]
        profile["expected_keyword_hits"] = {term: (term in text) for term in unique_terms[:40]}
        return profile

    def _build_evaluator_prompt(
        self,
        task_desc: str,
        expected_output: str,
        actual_payload: Any,
        *,
        artifact_type: str,
        profile_used: bool,
    ) -> str:
        payload = {
            "task_description": task_desc,
            "expected_output_contract": expected_output,
            "artifact_type": artifact_type,
            "actual_output_is_profile": profile_used,
            "actual_output": actual_payload,
            "allowed_verdicts": ["pass", "fail", "inconclusive"],
            "allowed_failure_types": [item.value for item in EvaluationFailureType],
            "required_dimension_scores": [
                "format_compliance",
                "contract_coverage",
                "dependency_grounding",
                "factual_consistency",
                "completeness",
                "actionability",
            ],
            "allowed_training_labels": [item.value for item in TrainingLabel],
        }
        if _EVALUATOR_TEMPLATE:
            payload_json = json.dumps(payload, ensure_ascii=False)
            if "{evaluation_payload}" in _EVALUATOR_TEMPLATE:
                return _EVALUATOR_TEMPLATE.replace("{evaluation_payload}", payload_json)
        return (
            "You are the S-GAR structured Router Evaluator. Return exactly one JSON object.\n"
            + json.dumps(payload, ensure_ascii=False)
        )

    async def _call_structured_evaluator(
        self,
        prompt: str,
        *,
        profile_used: bool,
        escalated_full_output: bool,
        subtask_id: str | None = None,
        single_semantic_call: bool = False,
    ) -> EvaluationResult:
        last_reason = "Evaluator produced no response."
        control_attempts: List[Dict[str, Any]] = []
        control_models = (
            tuple(self.control_model_chain[:1])
            if single_semantic_call
            else tuple(self.control_model_chain)
        )
        max_attempts = 1 if single_semantic_call else self.max_eval_retries + 1
        for model_index, model_id in enumerate(control_models):
            force_prompt_json = not GLOBAL_CAPABILITY_REGISTRY.allows(model_id, "json_mode_ok")
            model_prompt = prompt
            for attempt in range(1, max_attempts + 1):
                try:
                    api_kwargs: Dict[str, Any] = {
                        "model": model_id,
                        "messages": [{"role": "user", "content": model_prompt}],
                        "temperature": 0.0,
                        "max_tokens": 1200,
                    }
                    if not force_prompt_json:
                        api_kwargs["response_format"] = {"type": "json_object"}
                    accounting_context = (
                        self.cost_ledger.new_operation(
                            stage="evaluator",
                            subtask_id=subtask_id,
                            subtask_revision=(0 if subtask_id else None),
                        )
                        if self.cost_ledger is not None
                        else None
                    )
                    active_guard = getattr(self, "_active_model_payload_guard", None)
                    evaluator_guard = (
                        active_guard.for_request(
                            "evaluator",
                            source_ids=getattr(active_guard, "default_source_ids", ()),
                            request_identity={
                                "step_id": "evaluator",
                                "resource_id": model_id,
                            },
                        )
                        if active_guard is not None
                        and hasattr(active_guard, "for_request")
                        else active_guard
                    )
                    resp = await async_create_chat_completion_with_compat(
                        self.async_model_transport,
                        registry=GLOBAL_CAPABILITY_REGISTRY,
                        cost_ledger=self.cost_ledger,
                        accounting_context=accounting_context,
                        payload_guard=evaluator_guard,
                        **api_kwargs,
                    )

                    text = (resp.choices[0].message.content or "").strip()
                    if not text:
                        last_reason = "Evaluator returned empty output."
                        continue
                    GLOBAL_CAPABILITY_REGISTRY.record_success(model_id, "text_ok")
                    if not force_prompt_json:
                        GLOBAL_CAPABILITY_REGISTRY.record_success(model_id, "json_mode_ok")
                    result = self._normalize_evaluation_result(
                        text,
                        profile_used=profile_used,
                        escalated_full_output=escalated_full_output,
                    )
                    control_attempts.append(
                        {
                            "model_id": model_id,
                            "status": "success",
                            "attempt": attempt,
                            "response_format_mode": "prompt_json" if force_prompt_json else "json_object",
                            "model_accounting_reference": getattr(
                                resp,
                                "accounting_reference",
                                None,
                            ),
                        }
                    )
                    self._append_trace(
                        "control_model_call",
                        {
                            "control_role": "evaluator",
                            "selected_control_model": model_id,
                            "attempted_control_models": control_attempts,
                        },
                    )
                    return result.model_copy(update={"evaluator_model": model_id})
                except (ModelAccountingError, ModelTransportError):
                    raise
                except Exception as exc:
                    retryable_transport, failure_type = _retryable_transport_exception(exc)
                    if (
                        not retryable_transport
                        and is_response_format_unsupported_error(exc)
                    ):
                        failure_type = "capability_unsupported"
                    message = str(exc)
                    last_reason = message
                    GLOBAL_CAPABILITY_REGISTRY.record_error(model_id, failure_type, message)
                    if failure_type == "capability_unsupported" and not force_prompt_json:
                        GLOBAL_CAPABILITY_REGISTRY.record_failure(
                            model_id,
                            "json_mode_ok",
                            "capability_unsupported",
                            message,
                        )
                        force_prompt_json = True
                        model_prompt += "\n\nReturn JSON as plain text; provider JSON mode is unavailable."
                        continue
                    logger.warning("[Evaluator] Error on model {} attempt {}: {}", model_id, attempt, message)
                    if attempt < max_attempts:
                        continue
                    control_attempts.append(
                        {
                            "model_id": model_id,
                            "status": "failed",
                            "failure_type": failure_type,
                            "reason": message,
                        }
                    )
                    if (
                        not single_semantic_call
                        and is_control_model_failover_failure(failure_type)
                        and model_index < len(control_models) - 1
                    ):
                        logger.warning(
                            "[Evaluator] Control model {} failed with {}; trying next control model.",
                            model_id,
                            failure_type,
                        )
                        break
                    return self._default_evaluation_result(
                        EvaluationVerdict.INCONCLUSIVE,
                        EvaluationFailureType.EVALUATOR_INCONCLUSIVE,
                        f"Evaluator API failed or stayed ambiguous: {last_reason}",
                        confidence=0.0,
                        profile_used=profile_used,
                        escalated_full_output=escalated_full_output,
                        training_label=TrainingLabel.EVALUATOR_NOISE,
                    )

        return self._default_evaluation_result(
            EvaluationVerdict.INCONCLUSIVE,
            EvaluationFailureType.EVALUATOR_INCONCLUSIVE,
            f"Evaluator API failed or stayed ambiguous: {last_reason}",
            confidence=0.0,
            profile_used=profile_used,
            escalated_full_output=escalated_full_output,
            training_label=TrainingLabel.EVALUATOR_NOISE,
        )

    async def router_evaluate_result(
        self,
        task_desc: str,
        expected_output: str,
        actual_output: str,
        artifact_type: str = "plaintext",
        subtask_id: Optional[str] = None,
        *,
        single_semantic_call: bool = False,
        output_contract: Mapping[str, Any] | None = None,
    ) -> EvaluationResult:
        """Structured quality gate returning training-friendly evaluator output."""
        use_profile = len(actual_output or "") > self.eval_profile_threshold_chars
        actual_payload: Any = (
            self._artifact_profile(expected_output, actual_output, artifact_type, output_contract)
            if use_profile
            else actual_output
        )
        prompt = self._build_evaluator_prompt(
            task_desc,
            expected_output,
            actual_payload,
            artifact_type=artifact_type,
            profile_used=use_profile,
        )
        result = await self._call_structured_evaluator(
            prompt,
            profile_used=use_profile,
            escalated_full_output=False,
            subtask_id=subtask_id,
            single_semantic_call=single_semantic_call,
        )

        should_escalate = (
            use_profile
            and result.verdict in {EvaluationVerdict.FAIL, EvaluationVerdict.INCONCLUSIVE}
            and result.confidence < 0.7
            and not single_semantic_call
        )
        if should_escalate:
            full_prompt = self._build_evaluator_prompt(
                task_desc,
                expected_output,
                actual_output[:64000],
                artifact_type=artifact_type,
                profile_used=False,
            )
            result = await self._call_structured_evaluator(
                full_prompt,
                profile_used=False,
                escalated_full_output=True,
                subtask_id=subtask_id,
                single_semantic_call=False,
            )

        self._append_trace(
            "evaluation_trace",
            {
                "subtask_id": subtask_id,
                "result": result.model_dump(mode="json"),
            },
        )
        return result

    async def router_evaluate(
        self, task_desc: str, expected_output: str, actual_output: str
    ) -> tuple[bool, str]:
        """Backward-compatible wrapper around structured evaluation."""
        result = await self.router_evaluate_result(task_desc, expected_output, actual_output)
        reason = result.repair_hint or "; ".join(result.critical_issues) or result.failure_type.value
        return result.passed, reason

    # -- Typed Routing Session Execution -----------------------------

    def _resolve_resource_uri(self, uri: str) -> str:
        project_root = self._workspace_root()
        if uri.startswith("file://"):
            uri = uri[len("file://"):]
        path_map = getattr(self, "_active_runtime_path_map", None)
        normalized = str(uri)
        if "\\" in normalized:
            raise RuntimeError("UNBOUND_RUNTIME_PATH:non_posix_resource_uri")
        if path_map is not None and (
            normalized == "/app" or normalized.startswith("/app/")
        ):
            return path_map.runtime_to_host(normalized)
        if path_map is None and normalized.startswith("/app/"):
            # Legacy/unscoped compatibility only.  Every formal E1 call
            # installs RuntimePathMap before resolving an executor path.
            uri = os.path.join(project_root, normalized[len("/app/"):])
        resolved = uri if os.path.isabs(uri) else os.path.abspath(os.path.join(project_root, uri))
        # Resource source files are framework-owned inputs that the external
        # substrate stages into the task container.  Do not force them through
        # the task-state RuntimePathMap (whose /app root is intentionally a
        # private virtual route and does not include host source files).
        if self.execution_substrate is not None:
            return resolved
        if path_map is not None:
            # Round-trip through the declared scope.  This validates a
            # framework-owned Tool URI without widening the mount surface.
            return path_map.runtime_to_host(path_map.host_to_runtime(resolved))
        return resolved

    def _resolve_candidate_path(self, value: str) -> str:
        """Resolve a user/resource supplied path into the workspace when possible."""
        if self.execution_substrate is not None:
            # This resolver is host-filesystem logic.  External/TB task state
            # must use the typed runtime namespace and substrate RPC instead;
            # keeping this guard fail-closed prevents accidental host access.
            raise RuntimeError("UNBOUND_RUNTIME_PATH:legacy_host_path_resolver")
        project_root = self._workspace_root()
        cleaned = str(value).strip().strip('\'"`\u9225\u6ebe\u20ac\u6fc3\u20ac\u6a37\u20ac?,;:!?\u951b\u5c7b\u20ac\u50a6\u7d31\u951b\u6c3e\u7d12\u951b?)[]{}<>')
        if cleaned.startswith("file://"):
            cleaned = cleaned[len("file://"):]
        path_map = getattr(self, "_active_runtime_path_map", None)
        normalized = cleaned
        if "\\" in normalized:
            raise RuntimeError("UNBOUND_RUNTIME_PATH:non_posix_candidate_path")
        if path_map is not None and (
            normalized == "/app" or normalized.startswith("/app/")
        ):
            return path_map.runtime_to_host(normalized)
        if path_map is None and normalized.startswith("/app/"):
            # Legacy/unscoped compatibility only.  Formal execution always
            # validates the reverse mapping above.
            cleaned = os.path.join(project_root, normalized[len("/app/"):])
        if os.path.isabs(cleaned):
            resolved = os.path.abspath(cleaned)
            if path_map is not None:
                return path_map.runtime_to_host(path_map.host_to_runtime(resolved))
            return resolved
        if path_map is not None:
            working_directory = str(
                getattr(self, "_active_sandbox_scope", {}).get("working_directory")
                or path_map.writable_root.runtime_path
            )
            return path_map.runtime_to_host(posixpath.join(working_directory, cleaned))
        resolved = os.path.abspath(os.path.join(project_root, cleaned))
        return resolved

    def _extract_existing_file_paths(
        self,
        text: str,
        extensions: Optional[List[str]] = None,
    ) -> List[str]:
        """Find existing local files in free text without making resource-type assumptions."""
        if bool(getattr(self, "_formal_execution_active", False)):
            raise RuntimeError("formal_query_path_discovery_forbidden")
        if self.explicit_input_only or self.execution_substrate is not None:
            return []
        if not text:
            return []
        normalized_exts = {
            ext.lower() if str(ext).startswith(".") else f".{str(ext).lower()}"
            for ext in (extensions or [])
        }
        # Resolve only Linux/POSIX host paths in this harness.  Task text that
        # mentions another platform remains opaque data and is never treated
        # as a host artifact candidate during formal execution.
        absolute_path_matches = re.findall(
            r"/[^\r\n\"<>|?*]+?\.(?:sql|py|json|md|txt|log|csv|yaml|yml|ini|toml)(?![A-Za-z0-9_])",
            text,
            flags=re.IGNORECASE,
        )
        path_like_matches = re.findall(
            r"[A-Za-z0-9_.:/-]+?\.(?:sql|py|json|md|txt|log|csv|yaml|yml|ini|toml)(?![A-Za-z0-9_])",
            text,
            flags=re.IGNORECASE,
        )
        path_like_matches = absolute_path_matches + path_like_matches
        tokens = path_like_matches + re.split(r'[\s,"\'<>{}\[\]=]+', text)
        paths: List[str] = []
        seen: Set[str] = set()
        for token in tokens:
            cleaned = token.strip().strip('\'"`\u9225\u6ebe\u20ac\u6fc3\u20ac\u6a37\u20ac?,;:!?\u951b\u5c7b\u20ac\u50a6\u7d31\u951b\u6c3e\u7d12\u951b?)[]{}<>')
            if not cleaned:
                continue
            if "." not in cleaned or ("/" not in cleaned and "\\" not in cleaned):
                continue
            full_path = self._resolve_candidate_path(cleaned)
            if normalized_exts and os.path.splitext(full_path)[1].lower() not in normalized_exts:
                continue
            if full_path in seen or not os.path.isfile(full_path):
                continue
            seen.add(full_path)
            paths.append(full_path)
        return paths

    def _step_prefers_current_run_artifact(
        self,
        step: ResourceApplicationStep,
        contract_name: str = "",
    ) -> bool:
        haystack = " ".join(
            [
                str(step.step_id or ""),
                str(step.output_key or ""),
                str(step.intent or ""),
                str(contract_name or ""),
                json.dumps(step.input_bindings or {}, ensure_ascii=False, default=str),
            ]
        ).lower()
        current_markers = (
            "final",
            "generated",
            "current",
            "upstream",
            "artifact",
            "task_",
            "fixed",
            "repaired",
            '\u6700\u7ec8',
            '\u751f\u6210',
            '\u5f53\u524d',
            '\u4e0a\u6e38',
            '\u4ea7\u7269',
            '\u4fee\u590d',
        )
        input_markers = (
            "original",
            "input",
            "source file",
            "raw",
            "provided",
            '\u539f\u59cb',
            '\u8f93\u5165',
            '\u7528\u6237\u63d0\u4f9b',
        )
        has_current = any(marker in haystack for marker in current_markers)
        has_input = any(marker in haystack for marker in input_markers)
        return has_current and not (has_input and not has_current)

    def _current_run_file_candidates_for_step(
        self,
        step: ResourceApplicationStep,
        contract_name: str,
        extensions: Optional[List[str]] = None,
    ) -> List[str]:
        if not self._step_prefers_current_run_artifact(step, contract_name):
            return []
        artifact_types = None
        normalized_exts = {
            ext.lower() if str(ext).startswith(".") else f".{str(ext).lower()}"
            for ext in (extensions or [])
        }
        if normalized_exts:
            ext_to_type = {
                ".py": "code",
                ".json": "json",
                ".csv": "csv",
                ".md": "markdown",
                ".txt": "plaintext",
            }
            artifact_types = {
                ext_to_type[ext]
                for ext in normalized_exts
                if ext in ext_to_type
            }
        candidates: List[str] = []
        for path in self._current_run_artifact_paths(artifact_types=artifact_types):
            ext = os.path.splitext(path)[1].lower()
            if normalized_exts and ext not in normalized_exts:
                continue
            candidates.append(path)
        return candidates

    def _current_run_candidates_for_explicit_path(self, path: str) -> List[str]:
        """Return only current-run artifacts representing the same logical path."""
        path_map = getattr(self, "_active_runtime_path_map", None)
        if bool(getattr(self, "_formal_execution_active", False)) and path_map is not None:
            # Literal file dependencies refer to the producer's logical name,
            # not the consumer's new private working directory. Only records
            # actually mounted in this step can satisfy that dependency.
            logical = posixpath.normpath(str(path))
            candidates: List[str] = []
            for record in self.artifact_registry.by_step.values():
                declared = record.metadata.get("logical_path")
                if not declared or posixpath.normpath(str(declared)) != logical:
                    continue
                try:
                    path_map.host_to_runtime(record.path)
                except PathNamespaceError:
                    continue
                if os.path.isfile(record.path) and record.path not in candidates:
                    candidates.append(record.path)
            return candidates
        artifact_dir = getattr(self, "artifact_dir", None)
        if not artifact_dir:
            return []
        resolved = self._resolve_candidate_path(path)
        logical = (self._to_workspace_relative_path(resolved) or "").replace("\\", "/")
        if not logical:
            return []
        candidates: List[str] = []
        artifact_root = os.path.abspath(artifact_dir)
        for current_path in self._current_run_artifact_paths():
            current_abs = os.path.abspath(current_path)
            identities = {
                (self._to_workspace_relative_path(current_abs) or "").replace("\\", "/")
            }
            try:
                if os.path.commonpath([artifact_root, current_abs]) == artifact_root:
                    identities.add(
                        os.path.relpath(current_abs, artifact_root).replace("\\", "/")
                    )
            except ValueError:
                pass
            if logical in identities:
                candidates.append(current_abs)
        return candidates

    @staticmethod
    def _canonical_host_path(path: str) -> str:
        """Canonicalize a host path for identity comparisons.

        Canonicalize the native Linux host path for identity comparisons.
        """
        return os.path.normcase(os.path.normpath(os.path.abspath(str(path))))

    def _select_file_candidate_for_step(
        self,
        candidate_paths: List[str],
        step: ResourceApplicationStep,
        contract_name: str,
        extensions: Optional[List[str]] = None,
    ) -> Tuple[bool, str, str, Optional[str]]:
        normalized_exts = {
            ext.lower() if str(ext).startswith(".") else f".{str(ext).lower()}"
            for ext in (extensions or [])
        }
        existing: List[str] = []
        seen: Set[str] = set()
        for path in candidate_paths:
            resolved = os.path.abspath(path)
            ext = os.path.splitext(resolved)[1].lower()
            if normalized_exts and ext not in normalized_exts:
                continue
            canonical = self._canonical_host_path(resolved)
            if not os.path.isfile(resolved) or canonical in seen:
                continue
            seen.add(canonical)
            existing.append(resolved)
        if not existing:
            return True, "", "", None
        if len(existing) == 1:
            return True, "", "", existing[0]

        return (
            False,
            "binding_ambiguous",
            (
                f"Step {step.step_id} could not choose a unique file for input '{contract_name}'. "
                f"Candidates: {', '.join(self._to_tool_path(path) for path in existing[:6])}"
            ),
            None,
        )

    def _manifest_input_contracts(self, raw: Dict[str, Any]) -> List[Dict[str, Any]]:
        contracts = raw.get("input_contract")
        if contracts is None:
            contracts = raw.get("io", {}).get("input_contract")
        if contracts is None:
            contracts = raw.get("execution", {}).get("input_bindings")
        if isinstance(contracts, dict):
            contracts = [contracts]
        if isinstance(contracts, list):
            return [item for item in contracts if isinstance(item, dict)]
        return []

    def _manifest_output_contract(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        output_contract = raw.get("output_contract")
        if isinstance(output_contract, dict):
            return output_contract
        output_contract = raw.get("io", {}).get("output_contract")
        if isinstance(output_contract, dict):
            return output_contract
        return {}

    def _manifest_output_artifact(self, raw: Dict[str, Any]) -> Optional[str]:
        output_contract = self._manifest_output_contract(raw)
        if output_contract.get("artifact_type"):
            return str(output_contract["artifact_type"])
        return None

    def _output_contract_matches(self, raw: Dict[str, Any], artifact_type: str) -> bool:
        declared = self._manifest_output_artifact(raw)
        aliases = {"text": "plaintext", "plain_text": "plaintext", "markdown": "markdown"}
        declared = aliases.get(str(declared or "").lower(), declared)
        artifact_type = aliases.get(str(artifact_type or "").lower(), artifact_type)
        if declared is not None and declared == artifact_type:
            return True
        if declared == "plaintext" and artifact_type == "markdown":
            return True
        # Proactively support multi-format compatibility from constraint.artifact_output list
        artifact_output = raw.get("constraint", {}).get("artifact_output", [])
        if isinstance(artifact_output, list) and artifact_type in artifact_output:
            return True
        return False

    def _model_api_id_from_raw(self, raw: Dict[str, Any], fallback: str) -> str:
        if not isinstance(raw, dict):
            return fallback
        type_specific = raw.get("type_specific", {})
        model_block = type_specific.get("model", {}) if isinstance(type_specific, dict) else {}
        execution = raw.get("execution", {}) if isinstance(raw.get("execution", {}), dict) else {}
        return (
            model_block.get("model_id")
            or execution.get("model_id")
            or execution.get("default_base_model")
            or fallback
        )

    def _model_api_id_from_ref(
        self, ref: TypedResourceRef, resource_index: Dict[str, dict]
    ) -> str:
        raw = resource_index.get(ref.resource_id)
        identity = resolve_model_identity(ref.resource_id, raw or {})
        api_model_id = validate_typed_model_identity(identity, ref.base_model)
        cost_ledger = getattr(self, "cost_ledger", None)
        catalog = getattr(cost_ledger, "catalog", None)
        if catalog is not None:
            catalog.resolve(
                resource_id=identity.resource_id,
                api_model_id=api_model_id,
            )
        return api_model_id

    def _find_ref(
        self,
        resource_id: str,
        refs: List[TypedResourceRef],
        resource_index: Dict[str, dict],
    ) -> Optional[TypedResourceRef]:
        found = next((ref for ref in refs if ref.resource_id == resource_id), None)
        if found is not None:
            return found
        raw = resource_index.get(resource_id)
        if not isinstance(raw, dict):
            return None
        try:
            raw_type = raw.get("type", {}).get("resource_type") or raw.get("resource_type")
            if str(raw_type).strip().lower() in {
                "mas",
                "multiagent",
                "multiagent_system",
                "multi_agent_system",
            }:
                resource_type = ManifestType.AGENT
            else:
                resource_type = ManifestType(raw_type)
        except ValueError:
            return None
        base_model = None
        if resource_type == ManifestType.MODEL:
            base_model = self._model_api_id_from_raw(raw, resource_id)
        return TypedResourceRef(
            resource_id=resource_id,
            resource_type=resource_type,
            base_model=base_model,
        )

    @staticmethod
    def _binding_resource_id(binding: Any) -> Optional[str]:
        if isinstance(binding, str):
            return binding
        if isinstance(binding, dict):
            resource_id = (
                binding.get("resource_id")
                or binding.get("from_resource")
                or binding.get("resource")
            )
            return str(resource_id) if resource_id else None
        return None

    @staticmethod
    def _normalize_from_step_binding(
        value: Any,
        step_id_to_output_key: Dict[str, str],
    ) -> Any:
        return normalize_step_reference(value, step_id_to_output_key)

    @staticmethod
    def _binding_output_keys(value: Any) -> List[str]:
        _, keys = dependency_references(value)
        return sorted(keys)

    def _resolve_agent_base_model(
        self,
        step: ResourceApplicationStep,
        plan: ResourceApplicationPlan,
        selected: List[TypedResourceRef],
        resource_index: Dict[str, dict],
    ) -> Tuple[bool, str, str, Optional[str], Optional[str]]:
        """Resolve an Agent's explicit selected Model binding to its API model ID."""
        model_resource_id = self._binding_resource_id(
            step.input_bindings.get("base_model")
        )
        if not model_resource_id:
            return (
                False,
                "agent_missing_base_model",
                f"Agent step {step.step_id} has no input_bindings.base_model resource binding.",
                None,
                None,
            )
        model_ref = self._find_ref(model_resource_id, selected, resource_index)
        if model_ref is None or model_ref.resource_type != ManifestType.MODEL:
            return (
                False,
                "agent_invalid_base_model",
                f"Agent step {step.step_id} binds non-Model resource {model_resource_id}.",
                model_resource_id,
                None,
            )
        if model_resource_id not in plan.selected_resource_ids:
            return (
                False,
                "agent_missing_base_model",
                f"Agent base Model {model_resource_id} is not selected.",
                model_resource_id,
                None,
            )
        model_usage = next(
            (
                usage
                for usage in plan.resource_usage
                if usage.resource_id == model_resource_id
                and usage.use_as == "agent_base_model"
                and step.step_id in usage.attached_to_steps
            ),
            None,
        )
        # ResourceUsageRecord has one role per selected resource.  When the
        # same Model is both an executable Model step and an Agent base Model,
        # lowering records the executable role while the Agent's sealed
        # ``base_model`` binding remains the authoritative second role.  Accept
        # only that exact dual-use shape; a Model that is neither explicitly
        # attached as agent_base_model nor actually executable remains invalid.
        dual_use_model = any(
            usage.resource_id == model_resource_id
            and usage.use_as == "executable_step"
            for usage in plan.resource_usage
        ) and any(
            candidate_step.resource_id == model_resource_id
            and candidate_step.step_id != step.step_id
            for candidate_step in plan.steps
        )
        if model_usage is None and not dual_use_model:
            return (
                False,
                "agent_invalid_base_model",
                "Agent base Model must use_as=agent_base_model and attach to "
                f"step {step.step_id}.",
                model_resource_id,
                None,
            )
        return (
            True,
            "",
            "",
            model_resource_id,
            self._model_api_id_from_ref(model_ref, resource_index),
        )

    def _bound_step_inputs(
        self,
        step: ResourceApplicationStep,
        resource_index: Dict[str, dict],
        step_outputs: Dict[str, str],
    ) -> Tuple[Dict[str, str], Dict[str, str]]:
        """Resolve only inputs explicitly bound to this step."""
        bound_inputs: Dict[str, str] = {}
        bound_outputs: Dict[str, str] = {}
        fixed_pass = not bool(
            getattr(self, "_active_allow_semantic_normalization", True)
        )
        source_registry = self._binding_source_registry(resource_index)
        model_path_mapper = self._model_facing_binding_path_mapper(source_registry)
        for name, source_hint in step.input_bindings.items():
            if name == "base_model":
                continue
            if fixed_pass:
                # Model/Agent inputs are scalar prompt fields, so structured
                # literals remain one canonical JSON value.  Presence is
                # structural: falsey values, including an empty list and null,
                # must not disappear from the request.
                resolved = resolve_binding(
                    source_hint,
                    {"name": str(name), "kind": "text"},
                    source_registry,
                    step_outputs,
                    path_mapper=model_path_mapper,
                )
                bound_inputs[str(name)] = str(resolved)
            else:
                values = self._resolve_source_hint_values(
                    source_hint,
                    resource_index,
                    step_outputs,
                )
                if values:
                    bound_inputs[str(name)] = "\n".join(str(value) for value in values)
            for output_key in self._binding_output_keys(source_hint):
                if output_key in step_outputs:
                    output_value = step_outputs[output_key]
                    bound_outputs[output_key] = (
                        model_path_mapper(str(output_value))
                        if fixed_pass
                        else output_value
                    )
        return bound_inputs, bound_outputs

    @staticmethod
    def _step_execution_context(
        base_context: str,
        bound_inputs: Dict[str, str],
    ) -> str:
        if not bound_inputs:
            return base_context
        parts = [base_context, "--- [Plan-Bound Runtime Inputs] ---"]
        for name, value in bound_inputs.items():
            is_validated_skill = value.startswith("--- Skill: ")
            preview = (
                value
                if is_validated_skill or len(value) <= 12000
                else value[:12000] + "\n... (truncated)"
            )
            parts.append(f"[{name}]\n{preview}")
        return "\n\n".join(part for part in parts if part)

    @staticmethod
    def _context_runtime_handle_id(*, step: Any, source_id: str) -> str:
        """Resolve a sealed source identity without replacing its provenance ID."""
        sources = tuple(getattr(step, "consumed_context_source_ids", ()) or ())
        handles = tuple(getattr(step, "runtime_context_handle_ids", ()) or ())
        if len(set(sources)) != len(sources):
            raise ControllerSessionError("controller_context_source_mapping_ambiguous")
        if source_id not in sources:
            raise ControllerSessionError("controller_context_source_unauthorized")
        # Legacy callers may already use the exact artifact handle as source ID.
        # No aliases are inferred: the artifact resolver must resolve that ID.
        if handles and (len(handles) != len(sources) or any(not value for value in handles)):
            raise ControllerSessionError("controller_context_source_mapping_invalid")
        handle_id = handles[sources.index(source_id)] if handles else source_id
        spec = getattr(step, "controller_session_spec", None)
        for binding in getattr(spec, "context_bindings", ()):
            if binding.source_id == source_id and (
                binding.handle_id.removeprefix("artifact:") != handle_id.removeprefix("artifact:")
            ):
                raise ControllerSessionError("controller_context_source_identity_mismatch")
        return handle_id

    def _resolve_context_source_handle(self, *, step: Any, source_id: str) -> ArtifactHandle:
        handle_id = self._context_runtime_handle_id(step=step, source_id=source_id)
        ok, failure, _, handle = self.resolve_artifact_handle(handle_id)
        if not ok or handle is None:
            raise ControllerSessionError(failure or "controller_context_material_missing")
        if handle.handle_id.removeprefix("artifact:") != handle_id.removeprefix("artifact:"):
            raise ControllerSessionError("controller_context_source_identity_mismatch")
        return handle

    def _resolve_controller_context(self, *, step: Any) -> Dict[str, Any]:
        """Resolve text inline and identify binary media without exposing bytes."""
        spec = step.controller_session_spec
        if spec is None:
            return {}
        # Revalidate even when a caller obtained a spec via model_copy.
        spec = type(spec).model_validate(spec.model_dump(mode="json"))
        authorized = set(getattr(step, "consumed_context_source_ids", ()))
        resolved: Dict[str, Any] = {}
        for binding in spec.context_bindings:
            if binding.source_id not in authorized:
                raise ControllerSessionError("controller_context_source_unauthorized")
            handle = self._resolve_context_source_handle(step=step, source_id=binding.source_id)
            if handle.handle_id.removeprefix("artifact:") != binding.handle_id.removeprefix("artifact:"):
                raise ControllerSessionError("controller_context_source_identity_mismatch")
            if not handle.host_path or not Path(handle.host_path).is_file():
                raise ControllerSessionError("controller_context_material_missing")
            descriptor, content = self._formal_material_descriptor(binding.source_id, handle)
            # Only inline text consumes the context budget. Binary materials
            # remain sealed handles and use the existing media adapter limits.
            if content is not None and descriptor.included_bytes > 2_000_000:
                raise ControllerSessionError("controller_context_material_exceeds_bound")
            if descriptor.content_sha256 != binding.content_sha256:
                raise ControllerSessionError("controller_context_content_hash_mismatch")
            if content is None:
                resolved[binding.source_id] = {
                    "protocol": "sgar-controller-context-material-v1",
                    "delivery": "sealed_model_media",
                    "source_id": binding.source_id,
                    "handle_id": descriptor.handle_id,
                    "logical_name": descriptor.logical_name,
                    "artifact_type": descriptor.artifact_type,
                    "content_sha256": descriptor.content_sha256,
                    "byte_size": descriptor.original_bytes,
                    "coverage_status": descriptor.coverage_status,
                }
            else:
                resolved[binding.source_id] = content
        return resolved

    def _formal_declared_context(
        self,
        *,
        step: Any,
        base_context: str,
        original_query: str,
        task_expected_output: str = "",
        task_output_contract: Optional[SubtaskOutputContract] = None,
        include_task_contract: bool = False,
        include_context_sources: bool = True,
    ) -> str:
        """Project only sealed, explicitly consumed context into Model/Agent calls.

        Tool inputs remain governed by typed artifact-handle bindings. Formal
        Model and Agent steps instead name the exact compiler-visible context
        sources they consume. Re-resolving those source IDs here closes the
        Compiler-to-Runtime boundary without inferring dependencies from prompt
        text or exposing unrelated task context.
        """

        if not bool(getattr(self, "_formal_execution_active", False)):
            return base_context
        source_ids = (
            tuple(dict.fromkeys(
                str(item).strip()
                for item in (getattr(step, "consumed_context_source_ids", ()) or ())
                if str(item).strip()
            ))
            if include_context_sources else ()
        )
        # Compatibility callers that do not supply the structured public
        # objective retain their historical context. The production sealed
        # route always supplies original_query explicitly.
        if not original_query and not source_ids and not include_task_contract:
            return base_context

        parts: List[str] = []
        if original_query:
            parts.append(f"[Original User Query]\n{original_query}")
        if include_task_contract:
            if task_expected_output and task_expected_output not in original_query:
                parts.append(f"[Task Expected Output]\n{task_expected_output}")
            if task_output_contract is not None:
                contract = task_output_contract.model_dump(mode="json")
                required_fields = (
                    "content_kind", "artifact_type", "output_extension",
                    "syntax_validator", "required_content", "produced_files",
                    "json_schema", "interface_contract",
                    "grounding_requirements",
                )
                final_contract = {
                    key: contract[key]
                    for key in required_fields
                    if key in contract and contract[key] not in (None, "", [], {})
                }
                parts.append(
                    "[Final Task Output Contract — preserve for the overall deliverable; "
                    "intermediate steps obey their own sealed step contracts]\n"
                    + json.dumps(final_contract, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":"))
                )
        for source_id in source_ids:
            if not source_id.startswith("artifact:"):
                raise RuntimeError("formal_context_source_id_invalid")
            try:
                handle = self._resolve_context_source_handle(step=step, source_id=source_id)
            except ControllerSessionError as exc:
                raise RuntimeError(str(exc)) from exc
            if not handle.host_path:
                raise RuntimeError("formal_context_source_material_missing")
            source_path = Path(handle.host_path)
            if not source_path.is_file():
                raise RuntimeError("formal_context_source_not_file")
            try:
                raw_bytes = source_path.read_bytes()
                material = raw_bytes.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                # Binary inputs remain sealed artifact handles.  The selected
                # Tool adapter or multimodal Model adapter consumes the exact
                # bytes later from ResourceCallRequest; this text-only context
                # projection must not reject or inline them first.
                parts.append(
                    f"[Declared Non-Text Context Source: {source_id}]\n"
                    + json.dumps(
                        {
                            "artifact_type": str(handle.artifact_type),
                            "byte_size": len(raw_bytes),
                            "content_sha256": hashlib.sha256(raw_bytes).hexdigest(),
                            "delivery": "sealed_artifact_handle",
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                )
                continue
            except OSError as exc:
                raise RuntimeError("formal_context_source_read_failed") from exc
            # The text projection budget does not govern sealed binary media.
            # Those bytes are verified and consumed by the existing adapter.
            if len(raw_bytes) > 2_000_000:
                raise RuntimeError("formal_complete_material_requires_handle_reader")
            parts.append(f"[Declared Context Source: {source_id}]\n{material}")
        return "\n\n".join(parts) if parts else "No declared context sources."

    def _read_resource_snippet(
        self,
        ref: TypedResourceRef,
        resource_index: Dict[str, dict],
        requested_skill_references: Optional[Sequence[str]] = None,
    ) -> str:
        raw = resource_index.get(ref.resource_id, {})
        if ref.resource_type == ManifestType.SKILL:
            return self.skill_package_loader.load(
                raw,
                requested_references=requested_skill_references,
            ).content
        uri = raw.get("execution", {}).get("uri", "")
        formal = bool(getattr(self, "_formal_execution_active", False))
        if not uri:
            if formal:
                raise RuntimeError("formal_resource_uri_missing")
            return f"[{ref.resource_id}] ({ref.resource_type.value})"
        path = self._resolve_resource_uri(uri)
        if not os.path.exists(path):
            if formal:
                raise RuntimeError("formal_resource_material_missing")
            return f"[{ref.resource_id}] ({ref.resource_type.value}) uri={uri}"
        try:
            if formal:
                raw_bytes = Path(path).read_bytes()
                if len(raw_bytes) > 2_000_000:
                    raise RuntimeError(
                        "formal_complete_material_requires_handle_reader"
                    )
                return raw_bytes.decode("utf-8", errors="strict")
            if os.path.getsize(path) > 2_000_000:
                return f"[{ref.resource_id}] ({ref.resource_type.value}) file={path}"
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(6000)
            return f"--- Resource: {ref.resource_id} ({ref.resource_type.value}) ---\n{content}"
        except (OSError, UnicodeDecodeError):
            if formal:
                raise RuntimeError("formal_resource_material_read_failed")
            return f"[{ref.resource_id}] ({ref.resource_type.value}) file={path}"

    def _extract_local_file_context(self, text: str, max_chars_per_file: int = 12000) -> str:
        """
        Bridge local file paths mentioned in the task into LLM-readable context.

        Full-generative models cannot access local paths directly. When a task
        mentions a workspace file, we read a bounded snippet and inject it.
        """
        if self.explicit_input_only or self.execution_substrate is not None:
            return ""
        snippets: List[str] = []
        for full_path in self._extract_existing_file_paths(text):
            try:
                if os.path.getsize(full_path) > 2_000_000:
                    snippets.append(
                        "--- [Local File Available] ---\n"
                        f"Path: {full_path}\n"
                        "File is too large to inline safely.\n"
                    )
                    continue
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(max_chars_per_file)
                snippets.append(
                    f"--- [Local File Content: {full_path}] ---\n"
                    f"{content}\n"
                )
            except Exception as exc:
                logger.warning("[Context] local_file_unavailable | {} | {}", full_path, exc)
                snippets.append(
                    "--- [Local File Read Failed] ---\n"
                    f"Path: {full_path}\nError: {exc}\n"
                )

        return "\n\n".join(snippets)

    def _selected_resource_context(
        self,
        selected: List[TypedResourceRef],
        resource_index: Dict[str, dict],
    ) -> str:
        parts = []
        for ref in selected:
            if ref.resource_type in (ManifestType.RESOURCE, ManifestType.SKILL):
                parts.append(self._read_resource_snippet(ref, resource_index))
            elif ref.resource_type == ManifestType.TOOL:
                raw = resource_index.get(ref.resource_id, {})
                parts.append(
                    f"[Tool: {ref.resource_id}] "
                    f"{raw.get('constraint', {}).get('io_signature', '')} "
                    f"{raw.get('execution', {}).get('uri', '')}"
                )
        return "\n\n".join(parts)

    def _dependency_result_for_ref(
        self,
        ref: TypedResourceRef,
        resource_index: Dict[str, dict],
    ):
        raw = resource_index.get(ref.resource_id, {})
        requirements = raw.get("runtime_requirements") or {}
        if ref.resource_type == ManifestType.TOOL and self.execution_substrate is not None:
            native_file_rpc = getattr(self.execution_substrate, "native_file_rpc", None)
            native = callable(native_file_rpc) and native_file_rpc(raw)
            runtime_profile = "external_native_file_rpc" if native else "external_task_runtime"
            # External Tools use the supplied task container. Host Docker,
            # reference-image availability, and host package inventory cannot
            # decide whether that Tool runs there. Resolve only credentials
            # actually forwarded to its adapter from the same project source
            # used by dispatch, and the task's explicit network policy.
            if not native and isinstance(requirements, Mapping):
                declared_env = tuple(requirements.get("env_vars") or ())
                tool_env = load_project_tool_environment(self.project_root, declared_env) if declared_env else {}
                missing_env = [str(name) for name in declared_env if not tool_env.get(name)]
                if missing_env:
                    return DependencyCheckResult(
                        resource_id=ref.resource_id, runtime_profile=runtime_profile,
                        dependency_status="blocked", missing_env_vars=missing_env,
                        reason="missing environment variables: " + ", ".join(missing_env),
                        failure_type="runtime_environment_drift", responsibility="infrastructure",
                        retryable=False, failure_stage="runtime_dependency_gate",
                    )
                if requirements.get("network_required") and getattr(self.execution_substrate, "network_allowed", True) is False:
                    return DependencyCheckResult(
                        resource_id=ref.resource_id, runtime_profile=runtime_profile,
                        dependency_status="blocked", reason="TASK_NETWORK_POLICY_DENIED",
                        failure_type="runtime_provisioning_infrastructure_failure",
                        responsibility="infrastructure", retryable=False,
                        failure_stage="runtime_dependency_gate",
                    )
            probe = getattr(self.execution_substrate, "resource_incompatibility", None)
            reason = probe(raw) if callable(probe) else "external_runtime_probe_missing"
            if reason:
                return DependencyCheckResult(
                    resource_id=ref.resource_id,
                    runtime_profile=runtime_profile,
                    dependency_status="blocked", reason=reason,
                    failure_type="external_runtime_dependency_blocked",
                    responsibility="infrastructure", retryable=False,
                    failure_stage="runtime_dependency_gate",
                )
            return DependencyCheckResult(
                resource_id=ref.resource_id, runtime_profile=runtime_profile,
                dependency_status="satisfied",
            )
        return self.dependency_gate.assess(ref.resource_id, raw)

    @staticmethod
    def _dependency_failure_type_for_result(dependency_result: Any) -> str:
        """Read the producer-owned dependency label without parsing diagnostics."""

        declared = str(getattr(dependency_result, "failure_type", "") or "").strip()
        if declared:
            return declared
        if bool(getattr(dependency_result, "is_blocked", False)):
            # A blocked dependency without the structured producer contract is
            # an attribution defect.  It is never research evidence.
            return "dependency_failure_contract_missing"
        return ""

    @staticmethod
    def _dependency_failure_contract(dependency_result: Any) -> Dict[str, Any]:
        """Return the fixed failure envelope emitted by DependencyGate."""

        failure_type = DAGOrchestrator._dependency_failure_type_for_result(
            dependency_result
        )
        responsibility = str(
            getattr(dependency_result, "responsibility", "") or ""
        ).strip()
        failure_stage = str(
            getattr(dependency_result, "failure_stage", "") or ""
        ).strip()
        if (
            not failure_type
            or responsibility not in {"framework", "infrastructure", "research", "budget"}
            or not failure_stage
        ):
            failure_type = "dependency_failure_contract_missing"
            responsibility = "framework"
            failure_stage = "runtime_dependency_gate"
            retryable = False
        else:
            retryable = bool(getattr(dependency_result, "retryable", False))
        return {
            "failure_stage": failure_stage,
            "responsibility": responsibility,
            "retryable": retryable,
            "transport_attempt": 0,
            "request_hash": "",
            "response_received": False,
            "failure_type": failure_type,
        }

    def _local_python_module_dirs(self, extra_path: Optional[str] = None) -> List[str]:
        dirs: List[str] = []
        workspace_root = os.path.abspath(self._workspace_root())

        def add_python_roots_from_path(path: Optional[str]) -> None:
            if not path:
                return
            resolved = os.path.abspath(self._resolve_candidate_path(path))
            current = os.path.dirname(resolved) if os.path.isfile(resolved) else resolved
            while current:
                dirs.append(current)
                try:
                    if os.path.commonpath([workspace_root, current]) != workspace_root:
                        break
                except ValueError:
                    break
                if current == workspace_root:
                    break
                parent = os.path.dirname(current)
                if parent == current:
                    break
                current = parent

        for record in self.artifact_registry.source_overlays.values():
            if record.path:
                add_python_roots_from_path(record.path)
            for alias in record.aliases:
                add_python_roots_from_path(alias)
        add_python_roots_from_path(extra_path)
        dirs.extend(
            [
                self.artifact_dir,
                os.path.join(self.artifact_dir, "generated_artifacts"),
            ]
        )
        for known_path in sorted(self._known_local_file_paths):
            add_python_roots_from_path(known_path)
        for record in list(self.artifact_registry.by_task.values()) + list(self.artifact_registry.by_step.values()):
            if record.path:
                add_python_roots_from_path(record.path)
            for alias in record.aliases:
                add_python_roots_from_path(alias)
        dirs.append(self._workspace_root())
        normalized: List[str] = []
        seen: Set[str] = set()
        for path in dirs:
            if not path:
                continue
            resolved = os.path.abspath(path)
            if resolved in seen:
                continue
            seen.add(resolved)
            normalized.append(resolved)
        return normalized

    def _scan_python_import_modules_from_file(self, path: str) -> List[str]:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                tree = ast.parse(f.read())
        except (OSError, SyntaxError):
            return []
        modules: Set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name:
                        modules.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    modules.add(node.module)
        return sorted(modules)

    def _current_run_import_roots_for_python_target(self, target_path: str) -> List[str]:
        modules = self._scan_python_import_modules_from_file(target_path)
        if not modules:
            return []
        python_paths = self._current_run_artifact_paths(artifact_types={"code"})
        roots: List[str] = []
        seen: Set[str] = set()

        def add_root(root: str) -> None:
            resolved = os.path.abspath(root)
            if not os.path.isdir(resolved) or not self._is_workspace_path(resolved):
                return
            if resolved in seen:
                return
            seen.add(resolved)
            roots.append(resolved)

        for module in modules:
            parts = [part for part in str(module).split(".") if part]
            if not parts:
                continue
            lowered_parts = [part.lower() for part in parts]
            module_suffix = "/".join(lowered_parts) + ".py"
            top_marker = f"/{lowered_parts[0]}/"
            for artifact_path in python_paths:
                normalized = os.path.abspath(artifact_path)
                normalized_slash = normalized.replace("\\", "/")
                lowered_slash = normalized_slash.lower()
                if lowered_slash.endswith("/" + module_suffix):
                    root = normalized_slash[: -len(module_suffix)].rstrip("/")
                    add_root(root)
                marker_index = lowered_slash.find(top_marker)
                if marker_index >= 0:
                    add_root(normalized_slash[:marker_index])
        return roots

    # Import-name -> PyPI package-name aliases for the cases where they differ.
    _IMPORT_TO_PIP_PACKAGE = {
        "yaml": "pyyaml", "pil": "pillow", "cv2": "opencv-python-headless",
        "bs4": "beautifulsoup4", "sklearn": "scikit-learn", "dotenv": "python-dotenv",
        "docx": "python-docx", "pptx": "python-pptx", "fitz": "pymupdf",
        "openssl": "pyopenssl", "jwt": "pyjwt", "dateutil": "python-dateutil",
        "attr": "attrs", "yaml_": "pyyaml", "tomli_w": "tomli-w",
    }

    def _imports_to_pip_packages(self, missing_imports: Sequence[str]) -> List[str]:
        """Map missing top-level import names to installable PyPI package names.

        Runtime-compatibility (Layer 0): a generated artifact that imports an
        external package the runtime lacks is a *provisionable* precondition, not
        an automatic failure — install it before executing. Names that already
        match their package (fastapi, pydantic, numpy, ...) pass through.
        """
        packages: List[str] = []
        for name in missing_imports:
            key = str(name or "").strip().lower()
            if not key:
                continue
            packages.append(self._IMPORT_TO_PIP_PACKAGE.get(key, name))
        # de-dupe preserving order
        seen: Set[str] = set()
        return [p for p in packages if not (p in seen or seen.add(p))]

    def _check_python_artifact_dependencies(
        self,
        code_text: Optional[str] = None,
        source_path: Optional[str] = None,
        allowed_packages: Optional[Sequence[str]] = None,
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        imports = (
            scan_python_imports_from_file(source_path)
            if source_path
            else scan_python_imports_from_text(code_text or "")
        )
        missing = missing_external_python_imports(
            imports,
            allowed_packages=allowed_packages or [],
            local_dirs=self._local_python_module_dirs(source_path),
        )
        return (
            not missing,
            missing,
            {
                "imports": imports,
                "missing_dependencies": missing,
                "allowed_packages": list(allowed_packages or []),
                "local_dirs": self._local_python_module_dirs(source_path),
                "source_path": source_path,
            },
        )

    def _tool_pythonpath_env(self, extra_paths: Optional[Sequence[str]] = None) -> Dict[str, str]:
        path_map = getattr(self, "_active_runtime_path_map", None)
        if path_map is not None:
            paths = path_map.runtime_import_roots(list(extra_paths or []))
            if not paths:
                return {}
            joined = ":".join(paths)
            return {
                "PYTHONPATH": joined,
                "SGAR_EXTRA_PYTHONPATH": joined,
            }
        paths: List[str] = []
        seen: Set[str] = set()
        for local_dir in list(extra_paths or []) + self._local_python_module_dirs():
            if not os.path.isdir(local_dir) or not self._is_workspace_path(local_dir):
                continue
            tool_path = self._to_tool_path(local_dir)
            if not tool_path or tool_path in seen:
                continue
            seen.add(tool_path)
            paths.append(tool_path)
        if not paths:
            return {}
        joined = ":".join(paths)
        return {
            "PYTHONPATH": joined,
            "SGAR_EXTRA_PYTHONPATH": joined,
        }

    def _tool_validation_target_paths(self, bindings: Dict[str, str]) -> List[str]:
        raw_values = []
        for key in ("target_path", "target_paths", "file_path", "path", "input_path"):
            if key in bindings:
                raw_values.append(bindings[key])
        targets: List[str] = []
        for raw_value in raw_values:
            value = str(raw_value or "")
            parsed = None
            if value.lower().endswith(".json") and os.path.isfile(self._resolve_candidate_path(value)):
                try:
                    with open(self._resolve_candidate_path(value), "r", encoding="utf-8") as f:
                        parsed = json.load(f)
                except Exception:
                    parsed = None
            if isinstance(parsed, dict) and isinstance(parsed.get("target_paths"), list):
                targets.extend(str(item) for item in parsed["target_paths"])
            else:
                targets.append(value)
        resolved = []
        for target in targets:
            path = self._resolve_candidate_path(target)
            if os.path.isfile(path) and self._is_workspace_path(path):
                resolved.append(path)
        return resolved

    def _semantic_tool_status_failure(
        self,
        ref: TypedResourceRef,
        result: ExecutionResult,
        step_type: str,
    ) -> Tuple[bool, str, str, Optional[Dict[str, Any]]]:
        if bool(getattr(self, "_formal_execution_active", False)):
            raise RuntimeError("formal_semantic_tool_status_inference_forbidden")
        status = interpret_tool_status(result.output_data)
        if status is None:
            return True, "", "", None
        result.cost_metric["tool_semantic_status"] = status["status"]
        result.cost_metric["tool_semantic_payload"] = status["payload"]
        if status["semantic_ok"]:
            return True, "", "", status
        failure_type = (
            "artifact_validation_failed"
            if step_type == "validate_artifact" or self._is_artifact_validator_ref(ref)
            else "tool_semantic_failure"
        )
        reason_text = str(status["reason"] or "")
        if self._is_pytest_runner_ref(ref):
            missing_match = re.search(r"No module named ['\"]([^'\"]+)['\"]", reason_text)
            if missing_match:
                missing_module = missing_match.group(1)
                top_module = missing_module.split(".", 1)[0]
                if "." in missing_module or top_module in {"src", "app", "pkg", "tests"}:
                    failure_type = "pytest_import_overlay_missing"
        return False, failure_type, status["reason"], status

    def _build_tool_invocation(
        self,
        tool_ref: TypedResourceRef,
        resource_index: Dict[str, dict],
        task_text: str,
    ) -> tuple[str, list]:
        if self.execution_substrate is not None:
            raise RuntimeError("external_legacy_tool_invocation_forbidden")
        raw = resource_index.get(tool_ref.resource_id, {})
        uri = raw.get("execution", {}).get("uri", "")
        if uri:
            script_path = self._resolve_resource_uri(uri)
        else:
            script_path = ""

        args = [script_path] if script_path else []
        import re
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        tokens = re.split(r'[\s,"\'<>{}\[\]=]+', task_text)
        for token in tokens:
            cleaned = token.strip().strip('\'"`\u951b\u5c7b\u20ac\u50a6\u7d12\u951b?!?;\u951b?\u951b?)[]{}<>')
            cleaned = re.split('[\u951b\u5c7b\u20ac\u50a6\u7d12\u951b?!?;\u951b\u6c92', cleaned, maxsplit=1)[0].strip()
            if not cleaned or ("." not in cleaned and "/" not in cleaned and "\\" not in cleaned):
                continue
            full_path = os.path.abspath(os.path.join(project_root, cleaned))
            if os.path.exists(full_path) and os.path.isfile(full_path) and full_path not in args:
                args.append(full_path)
        return sys.executable, args

    def _stringify_binding_value(self, value: Any) -> str:
        return stringify_literal(value)

    def _contract_kind(self, contract: Dict[str, Any]) -> str:
        """Use the shared, explicit-kind-authoritative contract semantics."""
        return normalize_contract_kind(contract)

    def _binding_source_registry(
        self,
        resource_index: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build the resolver's private source registry without serializing it."""

        sources: Dict[str, Any] = dict(resource_index or {})
        if getattr(self, "artifact_registry", None) is None:
            return sources
        for handle in self._all_artifact_handles():
            sources[handle.handle_id] = handle
        return sources

    def _registered_binding_path_index(
        self,
        source_registry: Mapping[str, Any],
    ) -> Dict[str, List[Tuple[str, str, Optional[str]]]]:
        """Index exact registered host paths and their portable aliases.

        The index is intentionally handle-owned.  A path merely being inside
        the active runtime scope does not authorize it as a formal binding.
        """

        registered: Dict[str, List[Tuple[str, str, Optional[str]]]] = {}

        def field_value(source: Any, name: str) -> Any:
            if isinstance(source, Mapping):
                return source.get(name)
            return getattr(source, name, None)

        seen_handles: Set[str] = set()
        for source in source_registry.values():
            handle_id = str(field_value(source, "handle_id") or "").strip()
            if not handle_id or handle_id in seen_handles:
                continue
            seen_handles.add(handle_id)
            host_path = field_value(source, "host_path")
            if not host_path:
                continue
            # ArtifactHandle names the portable alias ``tool_path``.  Mapping
            # projections may expose the same identity as ``runtime_path``.
            portable_path = field_value(source, "tool_path") or field_value(
                source, "runtime_path"
            )
            canonical_host = self._canonical_host_path(str(host_path))
            registered.setdefault(canonical_host, []).append(
                (
                    handle_id,
                    str(host_path),
                    str(portable_path) if portable_path else None,
                )
            )
        return registered

    def _formal_portable_binding_tree(
        self,
        value: Any,
        source_registry: Mapping[str, Any],
        *,
        task_runtime_path: bool = False,
    ) -> Any:
        """Project private bindings through exact registered Handle aliases.

        Host paths remain available to private validation, while the returned
        tree is the single portable value reused by trace, ResourceCallRequest,
        and prepared direct argv construction.
        """

        path_map = getattr(self, "_active_runtime_path_map", None)
        registered = self._registered_binding_path_index(source_registry)

        def project(item: Any) -> Any:
            if isinstance(item, Mapping):
                return {str(key): project(nested) for key, nested in item.items()}
            if isinstance(item, (list, tuple)):
                return [project(nested) for nested in item]
            if not isinstance(item, str):
                return item

            # Only POSIX strings can be framework runtime paths.  Do not
            # rewrite backslashes in task data (Windows paths, LaTeX, regex).
            normalized = item
            if normalized == "/app" or normalized.startswith("/app/"):
                if path_map is None:
                    raise BindingProtocolError(
                        "binding_host_path_not_portable",
                        "Formal runtime path has no active runtime namespace.",
                    )
                return path_map.validate_runtime(normalized)

            is_absolute_host_path = bool(
                os.path.isabs(item)
            )
            if not is_absolute_host_path:
                return item

            matches = registered.get(self._canonical_host_path(item), [])
            if len(matches) != 1:
                substrate = getattr(self, "execution_substrate", None)
                task_path = getattr(substrate, "task_path", None)
                if not matches and callable(task_path):
                    # The external substrate owns an isolated filesystem;
                    # absolute task paths are not private control-host paths.
                    # Preserve opaque text exactly. Only declared path ports
                    # are normalized into the substrate's task namespace.
                    if path_map is not None:
                        try:
                            path_map.host_to_runtime(item)
                        except PathNamespaceError:
                            pass
                        else:
                            raise BindingProtocolError(
                                "binding_host_path_not_portable",
                                "Private host path lacks a registered artifact alias.",
                            )
                    return task_path(item) if task_runtime_path else item
                raise BindingProtocolError(
                    "binding_host_path_not_portable",
                    "Formal host binding does not identify exactly one registered artifact handle.",
                )
            _handle_id, registered_host, portable_path = matches[0]
            task_path = getattr(getattr(self, "execution_substrate", None), "task_path", None)
            if portable_path and callable(task_path):
                # External artifacts may have a private imported byte copy.
                # Its registered task alias, not the virtual /app host map,
                # identifies the file in the persistent task filesystem.
                return task_path(portable_path)
            if not portable_path or path_map is None:
                raise BindingProtocolError(
                    "binding_host_path_not_portable",
                    "Registered artifact handle has no portable runtime alias.",
                )
            try:
                portable = path_map.validate_runtime(portable_path)
                round_trip_host = path_map.runtime_to_host(portable)
            except PathNamespaceError as exc:
                raise BindingProtocolError(
                    "binding_host_path_not_portable",
                    "Registered artifact runtime alias is outside the active namespace.",
                ) from exc
            if self._canonical_host_path(round_trip_host) != self._canonical_host_path(
                registered_host
            ):
                raise BindingProtocolError(
                    "binding_host_path_not_portable",
                    "Registered artifact host and runtime identities do not round-trip.",
                )
            return portable

        # Keep the existing portability validator as the final leak boundary.
        return self._portable_binding_tree(project(value))

    def _formal_portable_evidence_bindings(
        self,
        private_bindings: Mapping[str, Any],
        raw_manifest: Mapping[str, Any],
        source_registry: Mapping[str, Any],
    ) -> Dict[str, Any]:
        """Project declared ports and lower typed file targets into task paths."""

        contracts = self._manifest_input_contracts(dict(raw_manifest))
        declared_names = {
            str(contract.get("name") or "").strip()
            for contract in contracts
            if str(contract.get("name") or "").strip()
        }
        definition = ResourceDefinition.from_manifest(raw_manifest)
        file_operation = any(
            operation.execution_operation_kind in {"read_file", "write_file"}
            for operation in (
                definition.capability_card.capability_operations
                if definition.capability_card is not None else ()
            )
        )
        path_map = getattr(self, "_active_runtime_path_map", None)
        path_names = {
            str(contract.get("name") or "").strip()
            for contract in contracts
            if normalize_contract_kind(contract) in {"path", "file_path", "directory_path"}
            or (file_operation and str(contract.get("name") or "").strip() in {
                "path", "file_path", "source_path", "output_path", "destination_path",
            })
        }
        portable = {
            name: self._formal_portable_binding_tree(
                value, source_registry, task_runtime_path=name in path_names,
            )
            for name, value in private_bindings.items()
            if name in declared_names
        }
        for contract in contracts:
            name = str(contract.get("name") or "").strip()
            if name not in path_names:
                continue
            value = portable.get(name)
            if not isinstance(value, str):
                continue
            if not value or "\\" in value or "\x00" in value or ".." in value.split("/"):
                raise BindingProtocolError(
                    "binding_path_out_of_scope",
                    "A file path binding is empty or escapes the task workspace.",
                )
            try:
                substrate = getattr(self, "execution_substrate", None)
                task_path = getattr(substrate, "task_path", None)
                candidate = (
                    task_path(value) if callable(task_path)
                    else value if value.startswith("/")
                    else posixpath.join(
                        str(getattr(self, "_active_sandbox_scope", {}).get("working_directory")
                            or (path_map.writable_root.runtime_path if path_map is not None else "/app")),
                        value,
                    )
                )
                portable[name] = (
                    path_map.validate_runtime(candidate)
                    if path_map is not None and not callable(task_path) else candidate
                )
            except (PathNamespaceError, RuntimeError, ValueError) as exc:
                raise BindingProtocolError(
                    "binding_path_out_of_scope",
                    "A file path binding is outside the task workspace.",
                ) from exc
        return portable

    def _model_facing_binding_path_mapper(
        self,
        source_registry: Mapping[str, Any],
    ) -> Callable[[str], str]:
        """Map registered handle paths without guessing from their spelling.

        A directory handle commonly has no filename extension, so the generic
        path-looking heuristic is insufficient.  The private registry is the
        authority: an exact registered ``host_path`` is replaced by that
        handle's ``runtime_path``/``tool_path`` before a bound value reaches a
        Model or Agent request.  Unrelated strings retain the ordinary portable
        literal behavior.
        """

        registered_paths = self._registered_binding_path_index(source_registry)

        def mapper(value: str) -> str:
            text = str(value)
            is_absolute_host_candidate = bool(
                os.path.isabs(text)
            )
            if is_absolute_host_candidate:
                matches = registered_paths.get(self._canonical_host_path(text), [])
                if len(matches) == 1:
                    _handle_id, _host_path, registered = matches[0]
                    if not registered:
                        registered = self._to_tool_path(text)
                    elif (
                        getattr(self, "_active_sandbox_scope", None)
                        and (
                            "\\" in str(registered)
                            or not str(registered).startswith("/")
                        )
                    ):
                        registered = self._to_tool_path(text)
                    if "\\" in str(registered) or not str(registered).startswith("/"):
                        raise BindingProtocolError(
                            "binding_host_path_not_portable",
                            "Registered artifact handle has no model-facing runtime path.",
                        )
                    return str(registered)
            return self._to_tool_binding_value(text)

        return mapper

    def _portable_binding_value(self, value: Any) -> Any:
        """Validate the already-resolved execution/trace binding boundary.

        Structured bindings are mapped recursively by ``resolve_binding``
        *before* canonical JSON serialization.  A string that merely looks like
        JSON remains opaque here; reparsing or late path rewriting would change
        literal data.  Any remaining absolute host path is therefore a missing
        typed mapping and fails closed instead of being silently repaired.
        """

        path_map = getattr(self, "_active_runtime_path_map", None)
        if isinstance(value, Mapping):
            return {
                str(key): self._portable_binding_value(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [self._portable_binding_value(item) for item in value]
        if not isinstance(value, str):
            return value

        if path_map is not None and "\\" not in value and (
            value == "/app" or value.startswith("/app/")
        ):
            return path_map.validate_runtime(value)
        if path_map is not None and (
            os.path.isabs(value)
        ):
            try:
                path_map.host_to_runtime(value)
            except PathNamespaceError:
                # A model-authored, unregistered absolute path is research
                # behavior.  Preserve it for normal binding/execution failure;
                # the record portability audit independently rejects any real
                # workspace/hidden host root that reaches serialization.
                return value
            raise BindingProtocolError(
                "binding_host_path_not_portable",
                "Typed binding resolution left a registered host path in a formal trace.",
            )
        if value.startswith("/app/") or not hasattr(self, "project_root"):
            return value
        return self._to_tool_binding_value(value)

    def _portable_binding_tree(self, value: Any) -> Any:
        """Public/trace view of a binding tree; never expose the host map."""

        return self._portable_binding_value(value)

    def _path_kind_matches(self, path: str, kind: str) -> bool:
        if kind == "file_path":
            return os.path.isfile(path)
        if kind == "directory_path":
            return os.path.isdir(path)
        if kind == "path":
            return os.path.exists(path)
        return True

    def _registered_path_handle_index(self) -> Dict[str, List[ArtifactHandle]]:
        """Index exact private paths without inferring identity from filenames."""

        registered: Dict[str, List[ArtifactHandle]] = {}
        seen_handles: Set[str] = set()
        for handle in self._all_artifact_handles():
            handle_id = str(handle.handle_id or "").strip()
            if not handle_id or handle_id in seen_handles or not handle.host_path:
                continue
            seen_handles.add(handle_id)
            canonical = self._canonical_host_path(str(handle.host_path))
            registered.setdefault(canonical, []).append(handle)
        return registered

    def _select_path_candidate_for_step(
        self,
        candidate_paths: List[str],
        step: ResourceApplicationStep,
        contract_name: str,
        kind: str,
        extensions: Optional[List[str]] = None,
    ) -> Tuple[bool, str, str, Optional[str]]:
        normalized_exts = {
            ext.lower() if str(ext).startswith(".") else f".{str(ext).lower()}"
            for ext in (extensions or [])
        }
        registered_handles = self._registered_path_handle_index()
        existing: List[str] = []
        mismatched: List[str] = []
        identity_mismatches: List[Tuple[str, str]] = []
        seen: Set[str] = set()
        for path in candidate_paths:
            resolved = os.path.abspath(path)
            canonical = self._canonical_host_path(resolved)
            if not os.path.exists(resolved):
                continue
            if not self._path_kind_matches(resolved, kind):
                mismatched.append(resolved)
                continue
            handle_matches = registered_handles.get(canonical, [])
            if len(handle_matches) > 1:
                return (
                    False,
                    "artifact_handle_ambiguous",
                    "A private path resolves to more than one registered artifact handle.",
                    None,
                )
            typed_handle = handle_matches[0] if handle_matches else None
            if typed_handle is not None:
                if typed_handle.exists is False:
                    return (
                        False,
                        "artifact_handle_missing",
                        f"Registered handle {typed_handle.handle_id} is marked missing.",
                        None,
                    )
                actual_path_kind = "directory" if os.path.isdir(resolved) else "file"
                declared_path_kind = str(typed_handle.path_kind or "").strip().lower()
                declared_path_kind = {
                    "file_path": "file",
                    "directory_path": "directory",
                }.get(declared_path_kind, declared_path_kind)
                if (
                    declared_path_kind in {"file", "directory"}
                    and declared_path_kind != actual_path_kind
                ):
                    return (
                        False,
                        "artifact_path_type_mismatch",
                        (
                            f"Registered handle {typed_handle.handle_id} declares "
                            f"{declared_path_kind}, but its private target is {actual_path_kind}."
                        ),
                        None,
                    )
            if normalized_exts and os.path.isfile(resolved):
                physical_extension = os.path.splitext(resolved)[1].lower()
                semantic_extension = physical_extension
                if typed_handle is not None:
                    declared_extension = str(typed_handle.extension or "").strip().lower()
                    if declared_extension and not declared_extension.startswith("."):
                        return (
                            False,
                            "artifact_handle_extension_identity_mismatch",
                            f"Registered handle {typed_handle.handle_id} has an invalid extension identity.",
                            None,
                        )
                    portable_path = str(typed_handle.tool_path or "").replace("\\", "/")
                    portable_extension = (
                        PurePosixPath(portable_path).suffix.lower()
                        if portable_path
                        else ""
                    )
                    if (
                        declared_extension
                        and portable_path
                        and portable_extension != declared_extension
                    ):
                        return (
                            False,
                            "artifact_handle_extension_identity_mismatch",
                            (
                                f"Registered handle {typed_handle.handle_id} extension does not "
                                "match its portable runtime alias."
                            ),
                            None,
                        )
                    semantic_extension = (
                        declared_extension or portable_extension or physical_extension
                    )
                    if semantic_extension not in normalized_exts:
                        identity_mismatches.append(
                            (
                                "artifact_handle_extension_mismatch",
                                (
                                    f"Registered handle {typed_handle.handle_id} has extension "
                                    f"{semantic_extension or '<none>'}, expected one of "
                                    f"{sorted(normalized_exts)}."
                                ),
                            )
                        )
                        continue
                elif physical_extension not in normalized_exts:
                    continue
            if canonical in seen:
                continue
            seen.add(canonical)
            existing.append(resolved)
        if not existing:
            if identity_mismatches:
                failure_type, reason = identity_mismatches[0]
                return False, failure_type, reason, None
            if mismatched:
                actual = "directory_path" if os.path.isdir(mismatched[0]) else "file_path" if os.path.isfile(mismatched[0]) else "path"
                return (
                    False,
                    "tool_path_type_mismatch",
                    f"Input '{contract_name}' expected {kind}, got {actual}: {self._to_tool_path(mismatched[0])}.",
                    None,
                )
            return True, "", "", None
        if len(existing) == 1:
            return True, "", "", existing[0]

        return (
            False,
            "binding_ambiguous",
            (
                f"Step {step.step_id} could not choose a unique path for input '{contract_name}'. "
                f"Candidates: {', '.join(self._to_tool_path(path) for path in existing[:6])}"
            ),
            None,
        )

    def _is_absent_binding_value(self, value: Any) -> bool:
        if value is None:
            return True
        text = self._stringify_binding_value(value).strip()
        if not text:
            return True
        return text.lower() in {
            "none",
            "null",
            "n/a",
            "na",
            "no dependencies",
            "no dependencies.",
            "not provided",
        }

    def _is_placeholder_path_value(self, value: str) -> bool:
        text = str(value).strip().strip("'\"`")
        lowered = text.lower()
        return (
            self._is_absent_binding_value(text)
            or lowered.startswith("path/to/")
            or lowered.startswith("path\\to\\")
            or (lowered.startswith("<") and lowered.endswith(">"))
        )

    def _normalize_scalar_binding(
        self,
        name: str,
        kind: str,
        value: Any,
        required: bool,
        explicit: bool = False,
    ) -> Tuple[bool, Optional[Any], str]:
        if not explicit and self._is_absent_binding_value(value):
            if required:
                return False, None, f"Missing required input '{name}' ({kind})."
            return True, None, ""

        formal = bool(getattr(self, "_formal_execution_active", False))
        text = self._stringify_binding_value(value)
        if formal and kind not in {"int", "float", "bool", "object", "json"}:
            return True, text, ""
        text = text.strip()
        try:
            if kind == "int":
                parsed = int(text)
                return True, parsed if formal else str(parsed), ""
            if kind == "float":
                parsed = float(text)
                return True, parsed if formal else str(parsed), ""
            if kind == "bool":
                lowered = text.lower()
                if lowered in {"1", "true", "yes", "y", "on"}:
                    return True, True if formal else "true", ""
                if lowered in {"0", "false", "no", "n", "off"}:
                    return True, False if formal else "false", ""
                raise ValueError(f"invalid boolean: {text}")
            if formal and kind in {"object", "json"}:
                # The shared resolver returns argv-safe canonical JSON.
                # Decode it for Runtime; the argv builder encodes it once.
                return True, json.loads(text), ""
        except ValueError:
            if required:
                return False, None, f"Input '{name}' must be {kind}, got {text!r}."
            return True, None, ""

        return True, text, ""

    def _resolve_source_hint_values(
        self,
        source_hint: Any,
        resource_index: Dict[str, dict],
        step_outputs: Dict[str, str],
    ) -> List[str]:
        """Compatibility wrapper around the shared typed resolver."""
        if source_hint is None:
            return []

        normalized_source = source_hint
        if isinstance(source_hint, str):
            if source_hint in resource_index:
                normalized_source = {"resource_id": source_hint}
            elif source_hint in step_outputs:
                normalized_source = {"output_key": source_hint}
            elif source_hint.startswith("output:") and source_hint[len("output:"):] in step_outputs:
                normalized_source = {"output_key": source_hint[len("output:"):]}

        kind = "list" if isinstance(normalized_source, (list, tuple)) else "text"
        resolved = resolve_binding(
            normalized_source,
            {"name": "source", "kind": kind},
            self._binding_source_registry(resource_index),
            step_outputs,
        )
        return list(resolved) if isinstance(resolved, list) else [resolved]

    def _external_declared_path_binding(
        self,
        value: Any,
        *,
        kind: str,
        extensions: Sequence[str],
    ) -> Tuple[bool, str, str, Optional[str]]:
        """Validate a declared task path without inspecting the host workspace."""

        if not isinstance(value, str) or not value.strip():
            return False, "tool_missing_required_input", "Declared task path is missing.", None
        try:
            task_path = self.execution_substrate.task_path(value)
            path_map = getattr(self, "_active_runtime_path_map", None)
            if path_map is not None:
                task_path = path_map.validate_runtime(task_path)
        except (PathNamespaceError, RuntimeError, ValueError):
            return False, "binding_path_out_of_scope", "Declared task path is outside the task workspace.", None
        normalized_exts = {
            ext.lower() if str(ext).startswith(".") else f".{str(ext).lower()}"
            for ext in extensions
        }
        if kind == "file_path" and normalized_exts and PurePosixPath(task_path).suffix.lower() not in normalized_exts:
            return False, "binding_file_extension_mismatch", "Declared task file has an unsupported extension.", None
        return True, "", "", task_path

    def _bind_step_inputs(
        self,
        step: ResourceApplicationStep,
        selected: List[TypedResourceRef],
        resource_index: Dict[str, dict],
        desc: str,
        context_data: str,
        step_outputs: Dict[str, str],
        task_id: Optional[str] = None,
    ) -> Tuple[bool, str, str, Dict[str, Any]]:
        """Resolve declared runtime inputs from resources, task text, context, or prior step outputs."""
        allow_inference = bool(
            getattr(self, "_active_allow_semantic_normalization", True)
        )
        raw = resource_index.get(step.resource_id, {})
        contracts = self._manifest_input_contracts(raw)
        if not contracts:
            try:
                return True, "", "", {
                    key: resolve_binding(
                        value,
                        {"name": key, "kind": "text"},
                        self._binding_source_registry(resource_index),
                        step_outputs,
                        path_mapper=self._to_tool_binding_value,
                    )
                    for key, value in dict(step.input_bindings).items()
                }
            except BindingFrameworkError:
                raise
            except BindingProtocolError as exc:
                return False, exc.code, str(exc), {}

        bound: Dict[str, Any] = {}
        selected_resources = [
            ref for ref in selected if ref.resource_type == ManifestType.RESOURCE
        ]

        for contract in contracts:
            name = str(contract.get("name") or "input")
            kind = self._contract_kind(contract)
            required = bool(contract.get("required", True))
            extensions = [
                ext if str(ext).startswith(".") else f".{ext}"
                for ext in contract.get("extensions", [])
            ]
            has_explicit_binding = bool(
                step.input_bindings and name in step.input_bindings
            )
            source_hint = (
                step.input_bindings.get(name)
                if has_explicit_binding
                else contract.get("source")
            )
            if isinstance(source_hint, dict):
                handle_ref = source_hint.get("artifact_handle") or source_hint.get("handle_id")
                if handle_ref:
                    expected_artifact_type = (
                        contract.get("artifact_type")
                        or contract.get("expected_artifact_type")
                    )
                    ok_handle, handle_failure, handle_reason, handle = self.resolve_artifact_handle(
                        str(handle_ref),
                        expected_artifact_type=str(expected_artifact_type) if expected_artifact_type else None,
                        expected_path_kind=kind if kind in {"file_path", "directory_path"} else None,
                    )
                    if not ok_handle or handle is None:
                        return False, handle_failure, handle_reason, bound
            candidate_values: List[str] = []
            try:
                source_refers_to_step_output = self._binding_refers_to_step_output(
                    source_hint,
                    step_outputs,
                )
                if task_id:
                    for record in self._step_registry_records_from_binding(task_id, source_hint):
                        if os.path.isfile(record.path):
                            candidate_values.append(record.path)
                source_is_present = has_explicit_binding or "source" in contract
                if source_is_present:
                    resolved_value = resolve_binding(
                        source_hint,
                        contract,
                        self._binding_source_registry(resource_index),
                        step_outputs,
                        path_mapper=self._to_tool_binding_value,
                    )
                    if isinstance(resolved_value, list):
                        candidate_values.extend(resolved_value)
                    else:
                        candidate_values.append(resolved_value)
                    value: Any = resolved_value
                else:
                    value = (
                        self._normalize_cli_arg_list(candidate_values, resource_index, step_outputs)
                        if kind == "list" and candidate_values
                        else candidate_values[0] if candidate_values else None
                    )
            except BindingFrameworkError:
                raise
            except BindingProtocolError as exc:
                return False, exc.code, str(exc), bound

            if kind in {"file_path", "directory_path", "path"}:
                if self.execution_substrate is not None:
                    # The external substrate owns /app. Formal bindings have
                    # already resolved the exact artifact handle or declared
                    # source; host existence checks belong to that substrate.
                    if not source_is_present:
                        return False, "tool_missing_required_input", "External task path must be explicitly bound.", bound
                    ok_path, path_failure, path_reason, task_path = self._external_declared_path_binding(
                        value, kind=kind, extensions=extensions,
                    )
                    if not ok_path:
                        return False, path_failure, path_reason, bound
                    bound[name] = task_path
                    continue
                candidate_paths: List[str] = []
                for candidate_value in candidate_values:
                    if self._is_placeholder_path_value(candidate_value):
                        continue
                    candidate_paths.append(self._resolve_candidate_path(candidate_value))
                    if has_explicit_binding:
                        candidate_paths.extend(
                            self._current_run_candidates_for_explicit_path(
                                candidate_value
                            )
                        )
                # Explicit plan bindings are authoritative.  Context, selected
                # resources, and artifact-history inference are fallbacks for
                # unbound contract fields only; mixing them into an explicitly
                # named field can turn two exact bindings into a false
                # ambiguity and silently redirect execution to another file.
                if not source_is_present and allow_inference:
                    candidate_paths.extend(
                        self._current_run_file_candidates_for_step(
                            step,
                            name,
                            extensions=extensions,
                        )
                    )
                    for ref in selected_resources:
                        uri = resource_index.get(ref.resource_id, {}).get("execution", {}).get("uri", "")
                        if uri:
                            candidate_paths.append(self._resolve_resource_uri(uri))
                    if not source_refers_to_step_output:
                        candidate_paths.extend(
                            self._extract_existing_file_paths(
                                desc + "\n" + context_data,
                                extensions=extensions,
                            )
                        )

                ok_select, select_failure, select_reason, selected_path = self._select_path_candidate_for_step(
                    candidate_paths,
                    step,
                    name,
                    kind,
                    extensions=extensions,
                )
                if not ok_select:
                    return False, select_failure, select_reason, bound
                value = selected_path
                if (
                    kind == "directory_path"
                    and value is not None
                    and isinstance(source_hint, str)
                    and not os.path.isabs(source_hint)
                ):
                    value = self._to_tool_path(value)
                if value is not None:
                    bound[f"_{name}_source"] = self._path_provenance(value)
                    bound[f"_{name}_current_run_artifact"] = str(self._is_current_run_artifact_path(value)).lower()

            elif value is None:
                if (
                    allow_inference
                    and kind == "text"
                    and required
                    and context_data
                    and not self._is_absent_binding_value(context_data)
                ):
                    value = context_data
                else:
                    value = None

            if value is None:
                if required:
                    return (
                        False,
                        "tool_missing_required_input",
                        f"Step {step.step_id} could not bind required input '{name}' ({kind}) for {step.resource_id}.",
                        bound,
                    )
                continue
            if kind not in {"file_path", "list"}:
                ok, normalized_value, reason = self._normalize_scalar_binding(
                    name,
                    kind,
                    value,
                    required,
                    explicit=has_explicit_binding,
                )
                if not ok:
                    return (
                        False,
                        "tool_invalid_input",
                        f"Step {step.step_id} invalid input for {step.resource_id}: {reason}",
                        bound,
                    )
                if normalized_value is None:
                    continue
                value = normalized_value
            bound[name] = value

        return True, "", "", bound

    @staticmethod
    def _manifest_cli_option_args(contract: Dict[str, Any], value: Any) -> List[str]:
        """Encode a declared option as argv atoms, never as shell text."""
        flag = str(contract["cli_flag"])
        if contract.get("cli_value_mode") == "flag":
            # The scalar binding boundary canonicalizes booleans to CLI text.
            # Accept that representation as well as native controller booleans;
            # never use string truthiness ("false" must omit the option).
            if isinstance(value, str) and value in {"true", "false"}:
                value = value == "true"
            if not isinstance(value, bool):
                raise ValueError("cli_flag_value_must_be_boolean")
            return [flag] if value else []
        return [flag, value if isinstance(value, str) else stringify_literal(value)]

    def _build_tool_invocation_from_bindings(
        self,
        tool_ref: TypedResourceRef,
        resource_index: Dict[str, dict],
        bindings: Dict[str, Any],
        *,
        formal_resource_runtime: bool = False,
        formal_entrypoint_id: Optional[str] = None,
    ) -> Tuple[bool, str, str, str, List[str]]:
        raw = resource_index.get(tool_ref.resource_id, {})
        formal_entrypoint = None
        if formal_resource_runtime:
            try:
                definition = ResourceDefinition.from_manifest(raw)
                selected_entrypoint_id = formal_entrypoint_id or (
                    definition.entrypoints[0].entrypoint_id
                    if len(definition.entrypoints) == 1
                    else ""
                )
                if not selected_entrypoint_id:
                    return False, "unknown_resource_entrypoint", "Explicit multi-entrypoint Tool requires entrypoint_id.", "", []
                formal_entrypoint = definition.entrypoint(selected_entrypoint_id)
            except ResourceCallValidationError:
                return False, "unknown_resource_entrypoint", "Plan selected an unknown Tool entrypoint.", "", []
            except (ResourceManifestError, ValueError):
                return False, "resource_manifest_invalid", "Tool ResourceDefinition is invalid.", "", []
        uri = (
            formal_entrypoint.dispatch
            if formal_entrypoint is not None
            else raw.get("execution", {}).get("uri", "")
        )
        if not uri:
            return False, "tool_runtime_error", f"Tool {tool_ref.resource_id} has no execution.uri.", "", []
        script_path = self._resolve_resource_uri(uri)
        if not formal_resource_runtime:
            script_path = self._system_tool_adapter_path(tool_ref.resource_id) or script_path
        if not os.path.isfile(script_path):
            return False, "tool_runtime_error", f"Tool script not found: {script_path}", "", []

        contracts = (
            [dict(item) for item in formal_entrypoint.input_contract]
            if formal_entrypoint is not None
            else self._manifest_input_contracts(raw)
        )
        args = [self._to_tool_path(script_path)]
        if formal_resource_runtime:
            # This runner exposes a flag-based adapter even though its manifest
            # declares logical port positions.  Preserve the list as one JSON
            # argv atom and keep cwd out of the child-script argument list.
            # The legacy branch below uses the same public adapter contract.
            if tool_ref.resource_id == "tool.python_script_runner.v1":
                script_binding = (
                    bindings.get("script_path")
                    or bindings.get("path")
                    or bindings.get("file_path")
                )
                if not isinstance(script_binding, str) or not script_binding.strip():
                    return (
                        False,
                        "tool_missing_required_input",
                        f"Tool {tool_ref.resource_id} requires script_path.",
                        "",
                        [],
                    )
                args.append(str(self._portable_binding_value(script_binding)))
                cwd_value = bindings.get("cwd", ".")
                if self._is_absent_binding_value(cwd_value):
                    cwd_value = "."
                # The runner resolves '.' against its authorization root,
                # while a scoped Tool executes in its own working directory.
                # Pass that declared directory explicitly; keep caller-selected
                # directories and unscoped invocation semantics unchanged.
                if cwd_value in (".", "./"):
                    cwd_value = (
                        getattr(self, "_active_sandbox_scope", {}).get("working_directory")
                        or cwd_value
                    )
                cwd_value = self._portable_binding_value(cwd_value)
                args.extend([
                    "--cwd",
                    cwd_value if isinstance(cwd_value, str) else stringify_literal(cwd_value),
                ])
                if "arg_json" in bindings or "args" in bindings:
                    runner_args_source = (
                        bindings.get("arg_json")
                        if "arg_json" in bindings
                        else bindings.get("args")
                    )
                    if isinstance(runner_args_source, (list, tuple)):
                        runner_arg_list = [
                            self._stringify_binding_value(
                                self._portable_binding_value(item)
                            )
                            for item in runner_args_source
                        ]
                    else:
                        runner_arg_list = (
                            self._normalize_cli_arg_list(
                                runner_args_source, resource_index, {}
                            )
                            if runner_args_source is not None
                            else []
                        )
                    args.extend([
                        "--arg-json",
                        json.dumps(runner_arg_list, ensure_ascii=False),
                    ])
                return True, "", "", sys.executable, args

            positional_contracts = sorted(
                contracts,
                key=lambda item: int(item.get("cli_position", 999)),
            )
            for contract in positional_contracts:
                name = str(contract.get("name") or "")
                if name and name in bindings:
                    value = self._portable_binding_value(bindings[name])
                    if contract.get("cli_flag"):
                        args.extend(self._manifest_cli_option_args(contract, value))
                    elif normalize_contract_kind(contract) == "list":
                        # A structured value is one argv atom.  The technical
                        # entrypoint adapter owns the single JSON encoding;
                        # neither the compiler nor the binding resolver may
                        # split or shell-tokenize it.
                        args.append(stringify_literal(value))
                    else:
                        if not isinstance(value, str):
                            value = stringify_literal(value)
                        args.append(value)
                elif bool(contract.get("required", True)):
                    return (
                        False,
                        "tool_missing_required_input",
                        f"Tool {tool_ref.resource_id} requires missing input '{name}'.",
                        "",
                        [],
                    )
            runtime_kind = str((raw.get("execution") or {}).get("runtime") or "")
            return True, "", "", ("sh" if runtime_kind == "shell_script" else sys.executable), args
        if tool_ref.resource_id == "tool.python_script_runner.v1":
            script_binding = bindings.get("script_path") or bindings.get("path") or bindings.get("file_path")
            script_tool_path = self._normalize_single_file_target(script_binding)
            if script_tool_path is None:
                return (
                    False,
                    "tool_missing_required_input",
                    f"Tool {tool_ref.resource_id} requires an existing workspace-local script_path.",
                    "",
                    [],
                )
            args.append(script_tool_path)
            cwd_value = bindings.get("cwd", ".")
            cwd_tool_value = "."
            if not self._is_absent_binding_value(cwd_value) and str(cwd_value).strip() != ".":
                resolved_cwd = self._resolve_candidate_path(str(cwd_value))
                if not os.path.isdir(resolved_cwd) or not self._is_workspace_path(resolved_cwd):
                    return (
                        False,
                        "runner_cwd_error",
                        f"Runner cwd is not a workspace-local directory: {cwd_value}",
                        "",
                        [],
                    )
                cwd_tool_value = self._to_tool_path(resolved_cwd)
            args.extend(["--cwd", cwd_tool_value])
            runner_args_present = "arg_json" in bindings or "args" in bindings
            runner_args_source = bindings.get("arg_json") if "arg_json" in bindings else bindings.get("args")
            if isinstance(runner_args_source, (list, tuple)):
                runner_arg_list = [
                    self._stringify_binding_value(self._portable_binding_value(item))
                    for item in runner_args_source
                ]
            else:
                runner_arg_list = self._normalize_cli_arg_list(runner_args_source, resource_index, {}) if runner_args_source is not None else []
            if runner_args_present:
                args.extend(["--arg-json", json.dumps(runner_arg_list, ensure_ascii=False)])
            logger.info(
                "[Preflight] Tool binding for {} | bindings={}",
                tool_ref.resource_id,
                bindings,
            )
            return True, "", "", sys.executable, args
        positional_contracts = sorted(
            contracts,
            key=lambda item: int(item.get("cli_position", 999)),
        )
        for contract in positional_contracts:
            name = str(contract.get("name") or "")
            if name and name in bindings:
                value = self._portable_binding_value(bindings[name])
                if contract.get("cli_flag"):
                    args.extend(self._manifest_cli_option_args(contract, value))
                elif normalize_contract_kind(contract) == "list":
                    values = value if isinstance(value, list) else [value]
                    args.extend(
                        item if isinstance(item, str) else stringify_literal(item)
                        for item in values
                    )
                else:
                    if not isinstance(value, str):
                        value = stringify_literal(value)
                    args.append(value)
            elif bool(contract.get("required", True)):
                return (
                    False,
                    "tool_missing_required_input",
                    f"Tool {tool_ref.resource_id} requires missing input '{name}'.",
                    "",
                    [],
                )

        logger.info(
            "[Preflight] Tool binding for {} | bindings={}",
            tool_ref.resource_id,
            bindings,
        )
        runtime_kind = str((raw.get("execution") or {}).get("runtime") or "")
        return True, "", "", ("sh" if runtime_kind == "shell_script" else sys.executable), args

    def _infer_step_type(self, step: ResourceApplicationStep, ref: TypedResourceRef) -> str:
        if step.step_type:
            return str(step.step_type)
        if ref.resource_type == ManifestType.TOOL:
            return "run_tool"
        if ref.resource_type == ManifestType.MODEL:
            return "call_model"
        if ref.resource_type == ManifestType.AGENT:
            return "call_agent"
        if ref.resource_type == ManifestType.SKILL:
            return "apply_skill_hint"
        if ref.resource_type == ManifestType.RESOURCE:
            return "read_resource"
        return "read_resource"

    def _step_type_allowed(self, step_type: str, ref: TypedResourceRef) -> bool:
        allowed = {
            ManifestType.TOOL: {"run_tool", "execute_generated_code", "validate_artifact"},
            ManifestType.MODEL: {"call_model", "synthesize_final"},
            ManifestType.AGENT: {"call_agent", "synthesize_final"},
            ManifestType.SKILL: {"apply_skill_hint", "read_resource"},
            ManifestType.RESOURCE: {"read_resource", "context_resource"},
        }
        return step_type in allowed.get(ref.resource_type, set())

    def _is_pytest_runner_ref(self, ref: Optional[TypedResourceRef]) -> bool:
        return bool(ref and ref.resource_type == ManifestType.TOOL and "pytest_runner" in ref.resource_id)

    def _is_python_script_runner_ref(self, ref: Optional[TypedResourceRef]) -> bool:
        return bool(ref and ref.resource_type == ManifestType.TOOL and "python_script_runner" in ref.resource_id)

    _CODE_INPUT_MARKERS = ("script_path", "source_code", "code", "script", "program", "snippet")

    def _tool_expects_code_input(
        self,
        ref: Optional[TypedResourceRef],
        resource_index: Optional[Dict[str, Any]],
    ) -> bool:
        """Contract-driven check: does this Tool's declared input_contract require
        executable code/script as input (i.e. it is a genuine code executor)?

        This replaces name-guessing with the structured signal already present in
        the manifest. A tool whose inputs are file/path-like (e.g. sql_analyzer's
        `file_path`) is NOT a code executor and must not default to EXECUTE_SCRIPT.
        """
        if not ref or ref.resource_type != ManifestType.TOOL or not resource_index:
            return False
        raw = resource_index.get(ref.resource_id, {})
        for contract in self._manifest_input_contracts(raw):
            name = str(contract.get("name", "")).lower()
            if any(marker == name or marker in name.split("_") for marker in self._CODE_INPUT_MARKERS):
                return True
        return False

    def _is_file_reader_ref(self, ref: Optional[TypedResourceRef]) -> bool:
        resource_id = str(getattr(ref, "resource_id", "") or "").lower()
        return bool(ref and ref.resource_type == ManifestType.TOOL and any(
            marker in resource_id
            for marker in (
                "file_reader",
                "artifact_reader",
                "file_inspector",
                "artifact_inspector",
                "fs_read_file",
                "fs_read_multiple",
            )
        ))

    def _is_file_inspection_tool_ref(self, ref: Optional[TypedResourceRef]) -> bool:
        resource_id = str(getattr(ref, "resource_id", "") or "").lower()
        if not ref or ref.resource_type != ManifestType.TOOL:
            return False
        if self._is_python_script_runner_ref(ref) or self._is_pytest_runner_ref(ref) or self._is_artifact_validator_ref(ref):
            return False
        return any(
            marker in resource_id
            for marker in (
                "code_parser",
                "static_analyzer",
                "source_inspector",
                "schema_inspector",
                "ast_parser",
            )
        )

    def _subtask_text_for_semantics(self, subtask: Optional[Subtask]) -> str:
        if subtask is None:
            return ""
        return "\n".join(
            str(part or "")
            for part in (
                subtask.id,
                subtask.role,
                subtask.description,
                subtask.expected_output,
            )
        ).lower()

    def _is_test_artifact_subtask(self, subtask: Optional[Subtask]) -> bool:
        if subtask is None or str(subtask.artifact_type.value) != "code":
            return False
        return self._is_test_artifact_contract(subtask.expected_output, subtask.output_contract)

    def _subtask_requests_script_execution(self, subtask: Optional[Subtask]) -> bool:
        if subtask is None or str(subtask.artifact_type.value) != "code":
            return False
        if self._is_test_artifact_subtask(subtask):
            return False
        contract = subtask.output_contract
        contract_data: Dict[str, Any] = {}
        if isinstance(contract, dict):
            contract_data = contract
        elif contract is not None and hasattr(contract, "model_dump"):
            contract_data = contract.model_dump(mode="json")
        interface_contract = contract_data.get("interface_contract") if isinstance(contract_data, dict) else {}
        if isinstance(interface_contract, dict) and interface_contract.get("cli_args"):
            return True
        text = self._subtask_text_for_semantics(subtask)
        return bool(
            re.search(r"\b(cli|script|executable|command[- ]line|__main__)\b", text)
            or any(token in text for token in ('\u547d\u4ee4\u884c', '\u811a\u672c', '\u53ef\u6267\u884c', "cli", "script"))
        )

    def _step_requests_pytest(self, step: ResourceApplicationStep, subtask: Optional[Subtask]) -> bool:
        subtask_text = ""
        if subtask is not None and str(subtask.artifact_type.value) != "code":
            subtask_text = self._subtask_text_for_semantics(subtask)
        text = "\n".join(
            [
                subtask_text,
                str(step.step_id or ""),
                str(step.output_key or ""),
                str(step.intent or ""),
                json.dumps(step.input_bindings, ensure_ascii=False, default=str),
            ]
        ).lower()
        return bool(
            "pytest" in text
            or re.search(r"\b(run|execute|validate|verify)\b.{0,80}\btests?\b", text)
            or any(token in text for token in ('\u8fd0\u884c\u6d4b\u8bd5', '\u6267\u884c\u6d4b\u8bd5', '\u9a8c\u8bc1\u6d4b\u8bd5'))
        )

    def _step_source_output_key_from_bindings(self, step: ResourceApplicationStep) -> Optional[str]:
        for key in ("script_path", "target_path", "file_path", "path", "input_path", "code", "source", "input"):
            value = step.input_bindings.get(key)
            if isinstance(value, dict):
                output_key = (
                    value.get("output_key")
                    or value.get("from_output")
                    or value.get("artifact_key")
                    or value.get("context_key")
                )
                if output_key:
                    return str(output_key)
            elif isinstance(value, str):
                return value if value else None
        return None

    def _infer_operation_kind(
        self,
        step: ResourceApplicationStep,
        ref: TypedResourceRef,
        subtask: Optional[Subtask],
        plan: Optional[ResourceApplicationPlan] = None,
        resource_index: Optional[Dict[str, Any]] = None,
    ) -> OperationKind:
        if step.operation_kind is not None:
            return step.operation_kind
        step_type = self._infer_step_type(step, ref)
        is_final = bool(plan and step.output_key == plan.final_output_from)
        if ref.resource_type == ManifestType.TOOL:
            raw = (resource_index or {}).get(ref.resource_id, {})
            # An absent manifest has no explicit operation declaration. Do not
            # let the taxonomy's generic run_tool fallback pre-empt the
            # conservative ID/contract heuristics below.
            executable_allowed = (
                {
                    CAPABILITY_TO_EXECUTION_OPERATION.get(kind, kind)
                    for kind in tool_allowed_operation_kinds(raw)
                }
                if raw
                else set()
            )
            if len(executable_allowed) == 1:
                try:
                    return OperationKind(next(iter(executable_allowed)))
                except ValueError:
                    pass
            if self._is_pytest_runner_ref(ref):
                return OperationKind.RUN_TESTS
            if self._is_artifact_validator_ref(ref):
                return OperationKind.VALIDATE_ARTIFACT
            if self._is_file_reader_ref(ref) or self._is_file_inspection_tool_ref(ref) or step_type in {"read_resource", "context_resource"}:
                return OperationKind.INSPECT_INPUT
            if self._is_python_script_runner_ref(ref) or step_type == "execute_generated_code":
                return OperationKind.EXECUTE_SCRIPT
            if step_type == "validate_artifact":
                return OperationKind.VALIDATE_ARTIFACT
            # Contract-driven fallback: only tools whose input_contract actually
            # requires code/script are code executors. Ordinary tools execute their
            # own declared runtime through RUN_TOOL.
            if self._tool_expects_code_input(ref, resource_index):
                return OperationKind.EXECUTE_SCRIPT
            return OperationKind.RUN_TOOL
        if ref.resource_type == ManifestType.MODEL:
            if step_type == "synthesize_final" or is_final:
                return OperationKind.SYNTHESIZE_FINAL if step_type == "synthesize_final" else OperationKind.PRODUCE_ARTIFACT
            return OperationKind.PRODUCE_ARTIFACT if step.expected_output_contract else OperationKind.CALL_MODEL
        if ref.resource_type == ManifestType.AGENT:
            if step_type == "synthesize_final" or is_final:
                return OperationKind.SYNTHESIZE_FINAL if step_type == "synthesize_final" else OperationKind.PRODUCE_ARTIFACT
            return OperationKind.PRODUCE_ARTIFACT if step.expected_output_contract else OperationKind.CALL_AGENT
        if ref.resource_type in {ManifestType.SKILL, ManifestType.RESOURCE}:
            return OperationKind.APPLY_CONTEXT_HINT if ref.resource_type == ManifestType.SKILL else OperationKind.INSPECT_INPUT
        return OperationKind.APPLY_CONTEXT_HINT

    def _operation_kind_allowed(
        self,
        operation_kind: OperationKind,
        ref: TypedResourceRef,
        resource_index: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if ref.resource_type == ManifestType.TOOL:
            if operation_kind == OperationKind.RUN_TOOL:
                return True
            if self._is_pytest_runner_ref(ref):
                return operation_kind == OperationKind.RUN_TESTS
            if self._is_artifact_validator_ref(ref):
                return operation_kind == OperationKind.VALIDATE_ARTIFACT
            if self._is_python_script_runner_ref(ref) or self._tool_expects_code_input(ref, resource_index):
                return operation_kind == OperationKind.EXECUTE_SCRIPT
            if self._is_file_reader_ref(ref) or self._is_file_inspection_tool_ref(ref):
                if operation_kind == OperationKind.INSPECT_INPUT:
                    return True
            raw = (resource_index or {}).get(ref.resource_id, {})
            allowed = tool_allowed_operation_kinds(raw)
            executable_allowed = {
                CAPABILITY_TO_EXECUTION_OPERATION.get(kind, kind)
                for kind in allowed
            }
            return operation_kind.value in executable_allowed
        if ref.resource_type == ManifestType.MODEL:
            return operation_kind in {
                OperationKind.CALL_MODEL,
                OperationKind.PRODUCE_ARTIFACT,
                OperationKind.SYNTHESIZE_FINAL,
            }
        if ref.resource_type == ManifestType.AGENT:
            return operation_kind in {
                OperationKind.CALL_AGENT,
                OperationKind.PRODUCE_ARTIFACT,
                OperationKind.SYNTHESIZE_FINAL,
            }
        if ref.resource_type in {ManifestType.SKILL, ManifestType.RESOURCE}:
            return operation_kind in {OperationKind.APPLY_CONTEXT_HINT, OperationKind.INSPECT_INPUT}
        return False

    def _operation_kind_matches_step_type(
        self,
        operation_kind: OperationKind,
        step_type: str,
        ref: TypedResourceRef,
    ) -> bool:
        """Keep the planner's step label and executable operation aligned."""
        if ref.resource_type != ManifestType.TOOL:
            return True
        if step_type == "run_tool":
            if operation_kind not in _DIRECT_TOOL_EXECUTION_KINDS:
                return False
            if operation_kind != OperationKind.INSPECT_INPUT:
                return True
            return self._is_file_reader_ref(ref) or self._is_file_inspection_tool_ref(ref)
        if step_type == "execute_generated_code":
            return operation_kind == OperationKind.EXECUTE_SCRIPT
        if step_type == "validate_artifact":
            expected = OperationKind.RUN_TESTS if self._is_pytest_runner_ref(ref) else OperationKind.VALIDATE_ARTIFACT
            return operation_kind == expected
        return False

    @staticmethod
    def _formal_operation_kind_matches_step_type(
        operation_kind: OperationKind,
        step_type: str,
        resource_type: ManifestType,
    ) -> bool:
        """Validate compiler-owned semantics without resource-name inference.

        The formal Resource Runtime treats ``operation_kind`` as the framework
        action and ``entrypoint_id`` as the technical dispatch boundary.  It
        therefore validates only the declared resource type and structured step
        label; capability text, parameter names, and resource IDs are irrelevant.
        """
        if resource_type != ManifestType.TOOL:
            return True
        allowed_by_step_type = {
            "run_tool": _DIRECT_TOOL_EXECUTION_KINDS,
            "execute_generated_code": frozenset({OperationKind.EXECUTE_SCRIPT}),
            "validate_artifact": frozenset(
                {OperationKind.RUN_TESTS, OperationKind.VALIDATE_ARTIFACT}
            ),
        }
        return operation_kind in allowed_by_step_type.get(step_type, frozenset())

    def normalize_application_plan_semantics(
        self,
        plan: ResourceApplicationPlan,
        candidate_resources: List[TypedResourceRef],
        selected: List[TypedResourceRef],
        resource_index: Dict[str, dict],
        subtask: Subtask,
    ) -> List[Dict[str, Any]]:
        """Fill omitted semantic labels without changing the compiled plan.

        Runtime normalization may infer schema-compatible labels, but it must
        never add/select/substitute resources, remove or reorder steps, or
        redirect the final output.  Explicitly incompatible labels are left in
        place so preflight can return a structured composition failure.
        """
        candidate_map = {ref.resource_id: ref for ref in candidate_resources}
        notes: List[Dict[str, Any]] = []

        for step in plan.steps:
            ref = candidate_map.get(step.resource_id) or self._find_ref(step.resource_id, selected, resource_index)
            if ref is None:
                continue
            if step.step_type is None:
                step.step_type = self._infer_step_type(step, ref)
                notes.append(
                    {
                        "step_id": step.step_id,
                        "action": "inferred_step_type",
                        "value": step.step_type,
                    }
                )
            if step.operation_kind is None:
                step.operation_kind = self._infer_operation_kind(
                    step,
                    ref,
                    subtask,
                    plan,
                    resource_index,
                )
                notes.append(
                    {
                        "step_id": step.step_id,
                        "action": "inferred_operation_kind",
                        "value": step.operation_kind.value,
                    }
                )
        if notes:
            self._append_trace(
                "application_plan_semantic_normalization",
                {
                    "subtask_id": subtask.id,
                    "notes": notes,
                    "final_output_from": plan.final_output_from,
                    "steps": [step.model_dump(mode="json") for step in plan.steps],
                },
            )
        return notes

    def _step_artifact_type(self, step: ResourceApplicationStep, default_artifact_type: str) -> str:
        contract = step.expected_output_contract
        if contract is not None and contract.artifact_type is not None:
            return contract.artifact_type.value
        return default_artifact_type

    @staticmethod
    def _skill_required_resource_ids(raw: Dict[str, Any]) -> List[str]:
        skill_block = raw.get("type_specific", {}).get("skill", {})
        required = skill_block.get("required_resource_ids", [])
        if not isinstance(required, list):
            return []
        return list(dict.fromkeys(str(item) for item in required if item))

    def _validate_skill_plan_dependencies(
        self,
        skill_step: ResourceApplicationStep,
        plan: ResourceApplicationPlan,
        raw: Dict[str, Any],
        resource_index: Dict[str, dict],
    ) -> Tuple[bool, str]:
        """Require explicit, connected plan resources for conditional Skills."""
        controllers = [step for step in plan.steps
                       if getattr(step, "controller_session_spec", None) is not None
                       and skill_step.output_key in container_dependency_references(step.input_bindings)[1]]
        if controllers:
            try:
                for controller in controllers:
                    validate_skill_requirements(plan, controller, resource_index)
            except ControllerSkillError as exc:
                return False, exc.code
            return True, ""
        selected_ids = set(plan.selected_resource_ids)
        required_ids = self._skill_required_resource_ids(raw)
        steps_by_resource: Dict[str, List[ResourceApplicationStep]] = {}
        for step in plan.steps:
            steps_by_resource.setdefault(step.resource_id, []).append(step)

        def resource_type(resource_id: str) -> Optional[ManifestType]:
            dependency_raw = resource_index.get(resource_id, {})
            raw_type = (
                dependency_raw.get("resource_type")
                or dependency_raw.get("type", {}).get("resource_type")
            )
            try:
                return ManifestType(raw_type)
            except (TypeError, ValueError):
                return None

        for dependency_id in required_ids:
            if dependency_id not in selected_ids:
                return (
                    False,
                    f"Skill {skill_step.resource_id} requires selected resource {dependency_id}.",
                )
            dependency_type = resource_type(dependency_id)
            if dependency_type == ManifestType.TOOL and not steps_by_resource.get(dependency_id):
                return (
                    False,
                    f"Skill {skill_step.resource_id} requires an explicit Tool step for {dependency_id}.",
                )

        consumers = [
            step
            for step in plan.steps
            if skill_step.output_key
            in container_dependency_references(step.input_bindings)[1]
        ]
        if required_ids and not consumers:
            return (
                False,
                f"Skill {skill_step.resource_id} has required resources but its output is not bound to a consumer step.",
            )

        portability = str(
            raw.get("type_specific", {})
            .get("skill", {})
            .get("portability", "pure_prompt")
        )
        if portability == "agent_bound":
            agent_consumers = [
                step
                for step in consumers
                if resource_type(step.resource_id) == ManifestType.AGENT
            ]
            if not agent_consumers:
                return (
                    False,
                    f"Agent-bound Skill {skill_step.resource_id} must feed an explicit Agent step.",
                )
        return True, ""

    def preflight_application_plan(
        self,
        plan: ResourceApplicationPlan,
        candidate_resources: List[TypedResourceRef],
        selected: List[TypedResourceRef],
        resource_index: Dict[str, dict],
        subtask: Subtask,
        context_data: str,
        *,
        allow_semantic_normalization: bool = True,
        formal_resource_runtime: bool = False,
    ) -> Tuple[bool, str, str, Dict[str, Dict[str, Any]]]:
        """Validate a dynamic resource application plan before executing anything."""
        # Preflight is observational: all compatibility normalization happens
        # on a deep copy and never mutates the compiler's plan object.
        plan = plan.model_copy(deep=True)
        if allow_semantic_normalization and any(
            step.operation_kind is None or step.step_type is None for step in plan.steps
        ):
            self.normalize_application_plan_semantics(
                plan,
                candidate_resources,
                selected,
                resource_index,
                subtask,
            )
        candidate_ids = {ref.resource_id for ref in candidate_resources}
        selected_ids = {ref.resource_id for ref in selected}
        step_outputs_seen: Set[str] = set()
        step_id_to_output_key = {step.step_id: step.output_key for step in plan.steps}
        step_ids = set(step_id_to_output_key)
        resolved_bindings: Dict[str, Dict[str, Any]] = {}
        placeholder_outputs: Dict[str, str] = {}
        skill_output_sizes: Dict[str, int] = {}

        if not plan.is_sufficient:
            return False, "bundle_insufficient", plan.reason or "Application plan is insufficient.", {}
        if not plan.steps:
            return False, "policy_invalid_plan", "Application plan has no steps.", {}
        if not plan.final_output_from:
            return False, "policy_invalid_plan", "Application plan has no final_output_from.", {}
        final_output_from = step_id_to_output_key.get(
            plan.final_output_from,
            plan.final_output_from,
        )
        for resource_id in plan.selected_resource_ids:
            if resource_id not in candidate_ids:
                return False, "policy_hallucinated_resource", f"Unknown selected resource_id: {resource_id}", {}
            if resource_id not in selected_ids:
                return False, "policy_invalid_plan", f"Selected resource is unavailable downstream: {resource_id}", {}

        if not plan.resource_usage and not allow_semantic_normalization:
            return (
                False,
                "resource_usage_missing",
                "Strict preflight requires compiler-provided resource_usage.",
                {},
            )
        if not plan.resource_usage:
            step_ids_by_resource: Dict[str, List[str]] = {}
            for step in plan.steps:
                step_ids_by_resource.setdefault(step.resource_id, []).append(step.step_id)
            plan.resource_usage = [
                ResourceUsageDecision(
                    resource_id=resource_id,
                    decision="use",
                    use_as="executable_step",
                    attached_to_steps=attached_steps,
                    reason="Derived from executable application-plan steps.",
                )
                for resource_id, attached_steps in step_ids_by_resource.items()
            ]

        usage_by_resource: Dict[str, ResourceUsageDecision] = {}
        for usage in plan.resource_usage:
            if str(usage.decision or "use").lower() != "use":
                return (
                    False,
                    "policy_invalid_plan",
                    f"Selected-only plan contains non-use resource_usage: {usage.resource_id}",
                    {},
                )
            if usage.resource_id not in plan.selected_resource_ids:
                return (
                    False,
                    "policy_invalid_plan",
                    f"resource_usage item is not selected: {usage.resource_id}",
                    {},
                )
            unknown_attached_steps = set(usage.attached_to_steps) - step_ids
            if unknown_attached_steps:
                return (
                    False,
                    "policy_invalid_plan",
                    "resource_usage references unknown attached_to_steps: "
                    + ",".join(sorted(unknown_attached_steps)),
                    {},
                )
            usage_by_resource[usage.resource_id] = usage

        step_resource_ids = {step.resource_id for step in plan.steps}
        for resource_id in set(plan.selected_resource_ids) - step_resource_ids:
            usage = usage_by_resource.get(resource_id)
            if usage is None or not usage.attached_to_steps:
                return (
                    False,
                    "policy_invalid_plan",
                    "Selected non-step resource must declare use_as and attached_to_steps: "
                    f"{resource_id}",
                    {},
                )

        final_step: Optional[ResourceApplicationStep] = None
        prior_step_ids: Set[str] = set()
        for step in plan.steps:
            if allow_semantic_normalization:
                step.input_bindings = {
                    name: self._normalize_from_step_binding(binding, step_id_to_output_key)
                    for name, binding in step.input_bindings.items()
                }
            try:
                referenced_steps, referenced_outputs = container_dependency_references(
                    step.input_bindings
                )
            except BindingProtocolError as exc:
                return False, exc.code, str(exc), resolved_bindings
            for output_key in referenced_outputs:
                if output_key not in step_outputs_seen:
                    return (
                        False,
                        "plan_input_binding_missing",
                        f"Step {step.step_id} references unavailable or later output_key {output_key}.",
                        resolved_bindings,
                    )
            bound_skill_bytes = sum(
                skill_output_sizes.get(output_key, 0)
                for output_key in referenced_outputs
            )
            if bound_skill_bytes > DEFAULT_MAX_SKILL_BYTES:
                return (
                    False,
                    "skill_context_budget_exceeded",
                    (
                        f"Step {step.step_id} binds {bound_skill_bytes} bytes of Skill "
                        f"context; limit is {DEFAULT_MAX_SKILL_BYTES}."
                    ),
                    resolved_bindings,
                )
            unavailable_steps = referenced_steps - prior_step_ids
            if unavailable_steps:
                return (
                    False,
                    "plan_input_binding_missing",
                    f"Step {step.step_id} references unavailable or later steps: "
                    + ",".join(sorted(unavailable_steps)),
                    resolved_bindings,
                )
            if step.resource_id not in candidate_ids:
                return False, "policy_hallucinated_resource", f"Unknown step resource_id: {step.resource_id}", {}
            if step.resource_id not in selected_ids:
                return False, "policy_invalid_plan", f"Step resource {step.resource_id} is not selected.", {}
            if step.output_key in step_outputs_seen:
                return False, "policy_invalid_plan", f"Duplicate output_key: {step.output_key}", {}
            step_outputs_seen.add(step.output_key)
            if step.output_key == final_output_from:
                final_step = step

            ref = self._find_ref(step.resource_id, selected, resource_index)
            if ref is None:
                return False, "policy_hallucinated_resource", f"Resource not found: {step.resource_id}", {}
            raw = resource_index.get(step.resource_id, {})
            if step.step_type is None and not allow_semantic_normalization:
                return (
                    False,
                    "step_type_missing",
                    f"Step {step.step_id} has no compiler-provided step_type.",
                    resolved_bindings,
                )
            step_type = self._infer_step_type(step, ref)
            if allow_semantic_normalization:
                step.step_type = step_type
            if not self._step_type_allowed(step_type, ref):
                return (
                    False,
                    "policy_invalid_plan",
                    f"Step {step.step_id} uses step_type={step_type} with incompatible resource_type={ref.resource_type.value}.",
                    resolved_bindings,
                )
            if step.operation_kind is None:
                return (
                    False,
                    "operation_kind_missing",
                    (
                        f"Step {step.step_id} ({ref.resource_id}, {ref.resource_type.value}) has no "
                        f"operation_kind. The policy MUST set operation_kind for every step, chosen "
                        f"from the allowed menu for this resource_type. No default is inferred."
                    ),
                    resolved_bindings,
                )
            operation_kind = step.operation_kind
            if (
                not formal_resource_runtime
                and ref.resource_type == ManifestType.TOOL
                and step.capability_operation
            ):
                declared_capabilities = tool_allowed_operation_kinds(raw)
                if step.capability_operation not in declared_capabilities:
                    return (
                        False,
                        "tool_capability_operation_mismatch",
                        f"Step {step.step_id} selects capability_operation="
                        f"{step.capability_operation}, but Tool {step.resource_id} declares "
                        f"{sorted(declared_capabilities)}.",
                        {},
                    )
            if not (
                formal_resource_runtime
                and ref.resource_type == ManifestType.TOOL
            ) and not self._operation_kind_allowed(
                operation_kind,
                ref,
                resource_index,
            ):
                return (
                    False,
                    "operation_misuse",
                    (
                        f"Step {step.step_id} uses operation_kind={operation_kind.value} "
                        f"with incompatible resource {ref.resource_id} ({ref.resource_type.value})."
                    ),
                    resolved_bindings,
                )
            operation_matches_step = (
                self._formal_operation_kind_matches_step_type(
                    operation_kind,
                    step_type,
                    ref.resource_type,
                )
                if formal_resource_runtime
                else self._operation_kind_matches_step_type(
                    operation_kind,
                    step_type,
                    ref,
                )
            )
            if not operation_matches_step:
                return (
                    False,
                    "operation_misuse",
                    (
                        f"Step {step.step_id} uses step_type={step_type} with "
                        f"operation_kind={operation_kind.value}; the pair is inconsistent for "
                        f"Tool {ref.resource_id}."
                    ),
                    resolved_bindings,
                )

            # Precondition check (artifact-flow): EXECUTE_SCRIPT consumes an upstream
            # code artifact. If no upstream step output is bound and the tool does not
            # itself declare a code/script input, the step has nothing to execute.
            # Catch this incompatibility here (pre-execution) instead of letting the
            # executor fail with tool_missing_required_input mid-run.
            if (
                not formal_resource_runtime
                and operation_kind == OperationKind.EXECUTE_SCRIPT
            ):
                has_upstream_code = any(
                    self._binding_refers_to_step_output(
                        value,
                        placeholder_outputs,
                        known_step_ids=set(step_id_to_output_key.keys()),
                        known_output_keys=set(step_id_to_output_key.values()),
                    )
                    for value in step.input_bindings.values()
                )
                if not has_upstream_code and not self._tool_expects_code_input(ref, resource_index):
                    return (
                        False,
                        "precondition_unsatisfied",
                        (
                            f"Step {step.step_id} resolves to EXECUTE_SCRIPT but has no code to run: "
                            f"no upstream step output is bound and {ref.resource_id} declares no "
                            f"code/script input. Routing/artifact-flow incompatibility."
                        ),
                        resolved_bindings,
                    )

            if ref.resource_type == ManifestType.TOOL:
                dependency_result = self._dependency_result_for_ref(ref, resource_index)
                if dependency_result.is_blocked:
                    failure_type = self._dependency_failure_type_for_result(
                        dependency_result
                    )
                    return (
                        False,
                        failure_type,
                        f"Tool {ref.resource_id} dependency check failed: {dependency_result.reason}",
                        resolved_bindings,
                    )
                if formal_resource_runtime:
                    # Formal preflight is contract-driven.  Deferred upstream
                    # values are validated by the DAG/binding protocol above
                    # and resolved immediately before dispatch; no validator,
                    # runner, capability, or parameter-name heuristic is used.
                    try:
                        ResourceDefinition.from_manifest(raw).entrypoint("invoke")
                    except ResourceCallValidationError:
                        return (
                            False,
                            "unknown_resource_entrypoint",
                            f"Tool {ref.resource_id} has no declared invoke entrypoint.",
                            resolved_bindings,
                        )
                    except (ResourceManifestError, ValueError):
                        return (
                            False,
                            "resource_manifest_invalid",
                            f"Tool {ref.resource_id} has an invalid execution manifest.",
                            resolved_bindings,
                        )
                    has_deferred_step_binding = any(
                        self._binding_refers_to_step_output(
                            value,
                            placeholder_outputs,
                            known_step_ids=set(step_id_to_output_key.keys()),
                            known_output_keys=set(step_id_to_output_key.values()),
                        )
                        for value in step.input_bindings.values()
                    )
                    if has_deferred_step_binding:
                        bindings = {}
                        uri = raw.get("execution", {}).get("uri", "")
                        script_path = self._resolve_resource_uri(uri) if uri else ""
                        ok = bool(script_path and os.path.isfile(script_path))
                        failure_type = "" if ok else "tool_runtime_error"
                        reason = "" if ok else "Tool entrypoint dispatch is unavailable."
                    else:
                        ok, failure_type, reason, bindings = self._bind_step_inputs(
                            step,
                            selected,
                            resource_index,
                            subtask.description,
                            context_data,
                            placeholder_outputs,
                            task_id=subtask.id,
                        )
                        if ok:
                            ok, failure_type, reason, _, _ = self._build_tool_invocation_from_bindings(
                                ref,
                                resource_index,
                                bindings,
                                formal_resource_runtime=True,
                            )
                elif self._is_artifact_validator_ref(ref):
                    has_deferred_step_binding = any(
                        self._binding_refers_to_step_output(
                            value,
                            placeholder_outputs,
                            known_step_ids=set(step_id_to_output_key.keys()),
                            known_output_keys=set(step_id_to_output_key.values()),
                        )
                        for value in step.input_bindings.values()
                    )
                    if has_deferred_step_binding:
                        bindings = {}
                        uri = raw.get("execution", {}).get("uri", "")
                        if not uri:
                            ok, failure_type, reason = False, "tool_runtime_error", f"Tool {ref.resource_id} has no execution.uri."
                        else:
                            script_path = self._resolve_resource_uri(uri)
                            ok = os.path.isfile(script_path)
                            failure_type = "" if ok else "tool_runtime_error"
                            reason = "" if ok else f"Tool script not found: {script_path}"
                    else:
                        ok, failure_type, reason, bindings = self._prepare_validation_bindings(
                            subtask.id,
                            step,
                            selected,
                            resource_index,
                            subtask.description,
                            context_data,
                            placeholder_outputs,
                        )
                        if not ok:
                            return False, failure_type, reason, resolved_bindings
                        ok, failure_type, reason, _, _ = self._build_tool_invocation_from_bindings(
                            ref,
                            resource_index,
                            bindings,
                        )
                elif operation_kind == OperationKind.VALIDATE_ARTIFACT:
                    # Domain validators (schema conformance, signature checks,
                    # and similar tools) own complete input contracts and must
                    # execute those contracts directly.  Only registered
                    # artifact/test validators use the current-run target
                    # resolver above.  Treating every VALIDATE_ARTIFACT
                    # operation as a generic artifact checker discards valid
                    # multi-input bindings such as instance+schema.
                    has_deferred_step_binding = any(
                        self._binding_refers_to_step_output(
                            value,
                            placeholder_outputs,
                            known_step_ids=set(step_id_to_output_key.keys()),
                            known_output_keys=set(step_id_to_output_key.values()),
                        )
                        for value in step.input_bindings.values()
                    )
                    if has_deferred_step_binding:
                        bindings = {}
                        uri = raw.get("execution", {}).get("uri", "")
                        if not uri:
                            ok, failure_type, reason = False, "tool_runtime_error", f"Tool {ref.resource_id} has no execution.uri."
                        else:
                            script_path = self._resolve_resource_uri(uri)
                            ok = os.path.isfile(script_path)
                            failure_type = "" if ok else "tool_runtime_error"
                            reason = "" if ok else f"Tool script not found: {script_path}"
                    else:
                        ok, failure_type, reason, bindings = self._bind_step_inputs(
                            step,
                            selected,
                            resource_index,
                            subtask.description,
                            context_data,
                            placeholder_outputs,
                            task_id=subtask.id,
                        )
                        if ok:
                            ok, failure_type, reason, _, _ = self._build_tool_invocation_from_bindings(
                                ref,
                                resource_index,
                                bindings,
                            )
                elif step_type == "execute_generated_code":
                    bindings = {}
                    uri = raw.get("execution", {}).get("uri", "")
                    if not uri:
                        ok, failure_type, reason = False, "tool_runtime_error", f"Tool {ref.resource_id} has no execution.uri."
                    else:
                        script_path = self._resolve_resource_uri(uri)
                        ok = os.path.isfile(script_path)
                        failure_type = "" if ok else "tool_runtime_error"
                        reason = "" if ok else f"Tool script not found: {script_path}"
                    if ok:
                        ok, failure_type, reason, resolved_cwd = (
                            self._resolve_generated_runner_cwd(
                                step,
                                resource_index,
                                placeholder_outputs,
                                defer_step_output=True,
                            )
                        )
                        if ok and resolved_cwd is not None:
                            bindings["cwd"] = self._to_tool_path(resolved_cwd)
                else:
                    has_deferred_step_binding = any(
                        self._binding_refers_to_step_output(
                            value,
                            placeholder_outputs,
                            known_step_ids=set(step_id_to_output_key.keys()),
                            known_output_keys=set(step_id_to_output_key.values()),
                        )
                        for value in step.input_bindings.values()
                    )
                    if has_deferred_step_binding:
                        bindings = {}
                        uri = raw.get("execution", {}).get("uri", "")
                        if not uri:
                            ok, failure_type, reason = False, "tool_runtime_error", f"Tool {ref.resource_id} has no execution.uri."
                        else:
                            script_path = (
                                self._system_tool_adapter_path(ref.resource_id)
                                or self._resolve_resource_uri(uri)
                            )
                            ok = os.path.isfile(script_path)
                            failure_type = "" if ok else "tool_runtime_error"
                            reason = "" if ok else f"Tool script not found: {script_path}"
                    else:
                        ok, failure_type, reason, bindings = self._bind_step_inputs(
                            step,
                            selected,
                            resource_index,
                            subtask.description,
                            context_data,
                            placeholder_outputs,
                            task_id=subtask.id,
                        )
                        if not ok:
                            return False, failure_type, reason, resolved_bindings
                        ok, failure_type, reason, _, _ = self._build_tool_invocation_from_bindings(
                            ref,
                            resource_index,
                            bindings,
                        )
                if not ok:
                    return False, failure_type, reason, resolved_bindings
                resolved_bindings[step.step_id] = bindings

            elif ref.resource_type in {ManifestType.RESOURCE, ManifestType.SKILL}:
                uri = raw.get("execution", {}).get("uri", "")
                if not uri:
                    return (
                        False,
                        "resource_runtime_missing",
                        f"{ref.resource_type.value} {ref.resource_id} has no execution.uri.",
                        {},
                    )
                if not os.path.exists(self._resolve_resource_uri(uri)):
                    return False, "local_file_unavailable", f"Resource file unavailable: {uri}", {}
                if ref.resource_type == ManifestType.SKILL:
                    bound_controller_skill = any(
                        getattr(consumer, "controller_session_spec", None) is not None
                        and step.output_key in container_dependency_references(consumer.input_bindings)[1]
                        for consumer in plan.steps
                    )
                    try:
                        requested_references = (
                            self.skill_package_loader.normalize_requested_references(
                                step.input_bindings.get("skill_references")
                            )
                        )
                        loaded_skill = self.skill_package_loader.load(
                            raw,
                            requested_references=requested_references,
                            **({"verify_integrity": True} if bound_controller_skill else {}),
                        )
                    except SkillPackageError as exc:
                        return False, exc.code, exc.code if bound_controller_skill else str(exc), resolved_bindings
                    dependencies_ok, dependency_reason = (
                        self._validate_skill_plan_dependencies(
                            step,
                            plan,
                            raw,
                            resource_index,
                        )
                    )
                    if not dependencies_ok:
                        return (
                            False,
                            "skill_dependency_missing",
                            dependency_reason,
                            resolved_bindings,
                        )
                    skill_output_sizes[step.output_key] = loaded_skill.total_bytes

            elif ref.resource_type == ManifestType.AGENT:
                agent_uri = raw.get("execution", {}).get("uri", "")
                if not agent_uri or not os.path.isfile(self._resolve_resource_uri(agent_uri)):
                    return (
                        False,
                        "agent_card_unavailable",
                        f"Agent Card unavailable for {ref.resource_id}: {agent_uri}",
                        resolved_bindings,
                    )
                ok, failure_type, reason, _, _ = self._resolve_agent_base_model(
                    step,
                    plan,
                    selected,
                    resource_index,
                )
                if not ok:
                    return False, failure_type, reason, resolved_bindings

            elif ref.resource_type == ManifestType.DEVICE:
                return False, "policy_invalid_plan", f"Device execution is not supported in V1: {ref.resource_id}", {}

            placeholder_outputs[step.output_key] = f"<{step.output_key}>"
            placeholder_outputs[step.step_id] = f"<{step.output_key}>"
            prior_step_ids.add(step.step_id)

        if final_step is None:
            return False, "policy_invalid_plan", f"final_output_from does not match any step output_key: {plan.final_output_from}", {}
        if final_output_from != plan.final_output_from:
            plan.final_output_from = final_output_from

        final_ref = self._find_ref(final_step.resource_id, selected, resource_index)
        final_raw = resource_index.get(final_step.resource_id, {})
        if final_ref and final_ref.resource_type == ManifestType.TOOL:
            if not self._output_contract_matches(final_raw, subtask.artifact_type.value):
                return (
                    False,
                    "tool_output_contract_mismatch",
                    f"Tool {final_ref.resource_id} output_contract does not match requested artifact_type={subtask.artifact_type.value}.",
                    resolved_bindings,
                )

        logger.info(
            "[Preflight] Application plan passed for {} | final_output_from={} | steps={}",
            subtask.id,
            final_output_from,
            [step.resource_id for step in plan.steps],
        )
        return True, "", "", resolved_bindings

    def _application_step_context(
        self,
        base_context: str,
        step_outputs: Dict[str, str],
    ) -> str:
        if not step_outputs:
            return base_context
        parts = [base_context, "\n--- [Resource Application Step Outputs] ---"]
        for key, value in step_outputs.items():
            preview = value if len(value) <= 12000 else value[:12000] + "\n... (truncated)"
            parts.append(f"[{key}]\n{preview}")
        return "\n\n".join(parts)

    def _build_final_output_contract(
        self,
        desc: str,
        expected_output: str,
        artifact_type: str,
        context_data: str,
        plan: Optional[ResourceApplicationPlan] = None,
        step_outputs: Optional[Dict[str, str]] = None,
        repair_feedback: str = "",
    ) -> str:
        """Create the strict final artifact contract shown to Model/Agent steps."""
        parts = [
            f"Task description:\n{desc}",
            f"Requested artifact_type: {artifact_type}",
            f"Planner expected_output:\n{expected_output or desc}",
            "The final answer must be a complete replacement artifact, not a patch or commentary.",
            "Use upstream actual artifacts and resource step outputs as source material.",
            "If upstream context contains SQL schema facts, preserve every table and column; do not invent substitute schemas or omit tables.",
            "Do not claim that local paths are inaccessible when their contents are already injected.",
            "Do not output greetings, explanations outside the artifact, or <think> blocks.",
            "Do not use placeholder imports, placeholder paths, TODO stubs, or names like your_module.",
        ]
        if artifact_type == "code":
            parts.append(
                "For code artifacts, function names, CLI arguments, and file names mentioned in the "
                "Planner expected_output are hard interface requirements. If you prefer a different "
                "internal helper name, also provide a thin compatibility wrapper for the required name."
            )
            parts.append(
                "The default generated-code runtime is python-stdlib. Avoid third-party imports unless "
                "the selected runtime/tool context explicitly says the dependency is available or installable. "
                "When possible, rewrite data handling with standard libraries such as csv, json, pathlib, "
                "datetime, and unittest."
            )
        if plan is not None:
            step_plan = [
                f"{step.step_id}: {step.resource_id} -> {step.output_key}; intent={step.intent}"
                for step in plan.steps
            ]
            parts.append("ResourceApplicationPlan:\n" + "\n".join(step_plan))
            parts.append(f"Final output key: {plan.final_output_from}")
        if context_data:
            preview = context_data if len(context_data) <= 12000 else context_data[:12000] + "\n... (truncated)"
            parts.append("Upstream actual context:\n" + preview)
        if step_outputs:
            parts.append(self._application_step_context("", step_outputs))
        if repair_feedback:
            parts.append("Evaluator or format feedback to repair:\n" + repair_feedback)
        return "\n\n".join(parts)

    def _is_deterministic_execution_failure(self, failure_type: str) -> bool:
        return str(failure_type or "") in {
            "binding_invalid",
            "validation_target_ambiguous",
            "validation_target_missing",
            "raw_content_not_materialized",
            "unsafe_execution_path",
            "unsafe_validation_target",
            "contract_alias_missing",
            "tool_missing_required_input",
            "tool_path_mapping_error",
            "runner_args_invalid",
            "runner_cwd_error",
            "input_file_mount_error",
            "interface_contract_mismatch",
            "placeholder_content",
            "binding_ambiguous",
            "wrong_validation_target",
            "resource_dependency_missing",
            "runtime_profile_unavailable",
            "runtime_warmup_timeout",
            "runtime_image_pull_failed",
            "dependency_install_blocked",
            "dependency_install_failed",
            "dependency_install_timeout",
            "artifact_dependency_missing",
            "tool_semantic_failure",
            "tool_semantic_misuse",
            "operation_misuse",
            "source_overlay_missing",
            "overlay_target_ambiguous",
            "local_import_unresolved",
            "pytest_import_overlay_missing",
            "tool_runtime_timeout",
            "artifact_validation_failed",
            "validation_failed",
            "contract_produced_file_missing",
            "artifact_lineage_mismatch",
            "contract_code_extraction_ambiguous",
        }

    def _is_provider_execution_failure(self, failure_type: str) -> bool:
        return str(failure_type or "") in {
            "provider_connection_error",
            "provider_stream_error",
            "provider_rate_limit",
            "provider_auth_error",
            "model_unavailable",
        }

    def _failure_layer_for_type(self, failure_type: str) -> str:
        """Map a concrete failure label onto the experiment Gap boundary."""
        failure_type = str(failure_type or "").strip().lower()
        if not failure_type:
            return "none"
        if failure_type in {
            "budget_guarded_failure",
            "budgetexhaustederror",
            "budget_control_failure",
        }:
            return "budget_control"
        if self._is_provider_execution_failure(failure_type):
            return "infrastructure"
        if failure_type in {
            "runtime_registry_unavailable",
            "runtime_environment_drift",
            "runtime_preparation_timeout",
            "runtime_preparation_lock_timeout",
            "runtime_provisioning_timeout",
            "runtime_provisioning_unavailable",
            "runtime_provisioning_infrastructure_failure",
            "runtime_image_pull_failed",
            "runtime_daemon_unavailable",
            "runtime_warmup_timeout",
        }:
            return "infrastructure"
        if failure_type in {
            "dependency_failure_contract_missing",
            "resource_manifest_incomplete",
            "dependency_integrity_failure",
            "runtime_dependency_policy_denied",
            "runtime_preparation_internal_error",
            "runtime_provisioning_config_invalid",
            "runtime_base_lock_invalid",
            "runtime_image_inspect_invalid",
            "runtime_base_image_mismatch",
            "runtime_base_inventory_invalid",
            "runtime_dependency_resolver_invalid",
            "runtime_preparation_disabled",
            "runtime_build_disallowed",
            "runtime_cache_corrupt",
            "runtime_handle_delivery_error",
            "runtime_verification_protocol_error",
            "runtime_trace_write_failed",
            "runtime_environment_missing",
            "runtime_environment_invalid",
            "legacy_inline_install_forbidden",
            "artifact_handle_extension_identity_mismatch",
        }:
            return "framework_implementation"
        if failure_type in {
            "artifact_dependency_unresolvable",
            "artifact_dependency_policy_denied",
            "artifact_dependency_conflict",
        }:
            return "task_success"
        if failure_type in {
            "candidate_bundle_not_expanded",
            "policy_invalid_output",
            "policy_invalid_plan",
            "policy_hallucinated_resource",
            "bundle_insufficient",
            "bundle_low_advantage",
            "bundle_low_advantage_observed",
            "plan_input_binding_missing",
            "agent_missing_base_model",
            "agent_invalid_base_model",
            "operation_misuse",
            "binding_invalid",
            "binding_ambiguous",
            "runtime_dependency_conflict",
        }:
            return "plan_composition"
        if failure_type in {
            "format_invalid",
            "missing_required_content",
            "dependency_not_used",
            "factual_mismatch",
            "fact_constraint_violation",
            "contract_violation",
            "interface_contract_mismatch",
            "hallucinated_content",
            "tool_output_mismatch",
            "evaluator_inconclusive",
            "placeholder_content",
        }:
            return "task_success"
        if failure_type in {
            "manifest_load_error",
            "resource_uri_parse_error",
            "executor_implementation_error",
            "adapter_implementation_error",
            "binding_delivery_error",
            "runtime_preparation_internal_error",
            "runtime_cache_corrupt",
            "runtime_handle_delivery_error",
            "runtime_verification_protocol_error",
            "runtime_environment_missing",
            "runtime_environment_invalid",
            "legacy_inline_install_forbidden",
        }:
            return "framework_implementation"
        return "resource_executability"

    def _failure_category_for_type(self, failure_type: str) -> NodeFailureCategory:
        failure_type = str(failure_type or "").strip()
        if failure_type in {"budget_guarded_failure"}:
            return NodeFailureCategory.BUDGET
        if self._is_provider_execution_failure(failure_type):
            return NodeFailureCategory.PROVIDER
        if self._is_deterministic_execution_failure(failure_type):
            return NodeFailureCategory.SYSTEM_DETERMINISTIC
        if failure_type in {
            "candidate_bundle_not_expanded",
            "policy_invalid_output",
            "policy_invalid_plan",
            "policy_hallucinated_resource",
            "bundle_insufficient",
            "bundle_low_advantage",
            "bundle_low_advantage_observed",
        }:
            return NodeFailureCategory.RESOURCE_SELECTION
        if failure_type in {
            "planner_dag_invalid",
            "planner_contract_mismatch",
            "dag_contract_unsatisfied",
        }:
            return NodeFailureCategory.DAG_CONTRACT
        if failure_type in {
            "format_invalid",
            "missing_required_content",
            "dependency_not_used",
            "factual_mismatch",
            "contract_violation",
            "hallucinated_content",
            "tool_output_mismatch",
            "evaluator_inconclusive",
            "placeholder_content",
            "fact_constraint_violation",
            "capability_unsupported",
            "agent_missing_base_model",
            "execution_failed",
        }:
            return NodeFailureCategory.MODEL_CONTENT
        return NodeFailureCategory.UNKNOWN

    def _graph_replan_allowed_for_failure(self, failure_type: str) -> bool:
        return self._failure_category_for_type(failure_type) == NodeFailureCategory.DAG_CONTRACT

    def _coerce_execution_warnings(self, result: Optional[ExecutionResult]) -> List[Dict[str, Any]]:
        if result is None:
            return []
        warnings: List[Dict[str, Any]] = []
        for key in ("execution_warnings", "lineage_warnings"):
            value = result.cost_metric.get(key)
            if isinstance(value, list):
                warnings.extend(item for item in value if isinstance(item, dict))
        return warnings

    def _append_execution_warning(
        self,
        result: ExecutionResult,
        warning_type: str,
        reason: str,
        **extra: Any,
    ) -> None:
        warnings = result.cost_metric.setdefault("execution_warnings", [])
        if not isinstance(warnings, list):
            warnings = []
            result.cost_metric["execution_warnings"] = warnings
        warning = {
            "warning_type": warning_type,
            "reason": str(reason or "")[:500],
            "strictness": self.execution_strictness.value,
        }
        warning.update(extra)
        warnings.append(warning)

    def _build_node_outcome(
        self,
        *,
        status: NodeExecutionStatus,
        failure_type: str = "",
        failure_reason: str = "",
        warnings: Optional[List[Dict[str, Any]]] = None,
    ) -> NodeExecutionOutcome:
        failure_type = str(failure_type or "").strip()
        category = self._failure_category_for_type(failure_type) if failure_type else None
        return NodeExecutionOutcome(
            status=status,
            strictness=self.execution_strictness,
            failure_category=category,
            failure_type=failure_type or None,
            failure_reason=str(failure_reason or "").strip() or None,
            retry_allowed=False,
            graph_replan_allowed=(
                self._graph_replan_allowed_for_failure(failure_type)
                if failure_type
                else False
            ),
            warnings=warnings or [],
        )

    def _sync_session_outcome(
        self,
        session: Optional[RoutingSession],
        outcome: NodeExecutionOutcome,
    ) -> None:
        if session is None:
            return
        session.execution_strictness = self.execution_strictness
        session.execution_status = outcome.status
        session.execution_outcome = outcome
        session.execution_warnings = list(outcome.warnings)

    def _routing_session_from_bundle(self, routing: Dict[str, Any]) -> Optional[RoutingSession]:
        session = routing.get("routing_session") if isinstance(routing, dict) else None
        return session if isinstance(session, RoutingSession) else None

    def _record_node_outcome(
        self,
        routing: Dict[str, Any],
        result: Optional[ExecutionResult],
        *,
        success: bool,
        failure_type: str = "",
        failure_reason: str = "",
    ) -> NodeExecutionOutcome:
        warnings = self._coerce_execution_warnings(result)
        status = (
            NodeExecutionStatus.SUCCESS_WITH_WARNINGS
            if success and warnings
            else NodeExecutionStatus.SUCCESS
            if success
            else NodeExecutionStatus.STRUCTURED_FAILURE
        )
        outcome = self._build_node_outcome(
            status=status,
            failure_type=failure_type,
            failure_reason=failure_reason,
            warnings=warnings,
        )
        if not success and result is not None and isinstance(
            result.cost_metric.get("failure"), Mapping
        ):
            outcome = outcome.model_copy(
                update={
                    "terminal_failure": terminal_failure_from_execution_result(
                        result,
                        run_id=(
                            self.execution_ledger.run_id
                            if self.execution_ledger
                            else ""
                        ),
                    )
                }
            )
        routing["node_outcome"] = outcome.model_dump(mode="json")
        self._sync_session_outcome(self._routing_session_from_bundle(routing), outcome)
        return outcome

    def _node_failure_summary(
        self,
        task_id: str,
        result: Optional[ExecutionResult],
    ) -> TerminalFailureEnvelope | str:
        if result is not None and isinstance(result.cost_metric.get("failure"), Mapping):
            return terminal_failure_from_execution_result(
                result,
                run_id=(self.execution_ledger.run_id if self.execution_ledger else ""),
                subtask_id=task_id,
            )
        if result is None:
            return f"Node {task_id} failed entirely."
        failure_type = str(result.cost_metric.get("failure_type") or "").strip()
        reason = str(result.error_log or "").strip()
        if not reason:
            trace = result.cost_metric.get("application_step_trace")
            if isinstance(trace, list):
                for item in reversed(trace):
                    if not isinstance(item, dict):
                        continue
                    reason = str(item.get("failure_reason") or "").strip()
                    if reason:
                        failure_type = failure_type or str(item.get("failure_type") or "").strip()
                        break
        if failure_type:
            category = self._failure_category_for_type(failure_type).value
            graph_allowed = str(self._graph_replan_allowed_for_failure(failure_type)).lower()
            return (
                f"failure_category={category}; graph_replan_allowed={graph_allowed}; "
                f"failure_type={failure_type}: {reason or f'Node {task_id} failed entirely.'}"
            )
        return reason or f"Node {task_id} failed entirely."

    def _structured_failure_result(self, failure_type: str, reason: str) -> ExecutionResult:
        failure_layer = self._failure_layer_for_type(failure_type)
        return ExecutionResult(
            is_success=False,
            output_data="",
            error_log=reason,
            cost_metric={
                "failure_type": failure_type,
                "failure_layer": failure_layer,
                "executability": (
                    "failed" if failure_layer == "resource_executability" else "not_run"
                ),
                "task_success": False,
                "fallback_skipped_reason": "deterministic_execution_failure",
                "failure_category": self._failure_category_for_type(failure_type).value,
                "graph_replan_allowed": self._graph_replan_allowed_for_failure(failure_type),
                "execution_strictness": self.execution_strictness.value,
            },
        )

    def _full_generative_fallback_guard(self, fallback_attempted: bool) -> Tuple[bool, str]:
        if fallback_attempted:
            return False, "high-cost full-generative fallback already used for this task"
        # Cost policy is enforced at the next network-send boundary.  There is
        # no token estimate or reserve, and monitor mode must never suppress a
        # fallback that the existing recovery logic selected.
        return True, ""

    def _budget_guarded_failure_result(self, reason: str) -> ExecutionResult:
        result = self._structured_failure_result("budget_guarded_failure", reason)
        result.cost_metric["fallback_skipped_reason"] = "budget_guarded_failure"
        return result

    def _augment_description_with_original_query(self, desc: str, original_query: str) -> str:
        original_query = (original_query or "").strip()
        if not original_query or original_query in desc:
            return desc
        return f"{desc}\n\nOriginal user query:\n{original_query}"

    def _extract_schema_tables_from_text(self, text: str) -> Dict[str, Set[str]]:
        """Extract table/column facts from upstream SQL-analyzer JSON or DDL text."""
        tables: Dict[str, Set[str]] = {}

        def add_table(name: Any, columns: Any = None) -> None:
            table_name = str(name or "").strip().strip("`\"[]")
            if not table_name:
                return
            table_columns = tables.setdefault(table_name, set())
            if isinstance(columns, list):
                for column in columns:
                    if isinstance(column, dict):
                        col_name = (
                            column.get("name")
                            or column.get("column")
                            or column.get("column_name")
                        )
                    else:
                        col_name = column
                    col_text = str(col_name or "").strip().strip("`\"[]")
                    if col_text:
                        table_columns.add(col_text)

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                candidate_tables = value.get("tables") or value.get("table_structure")
                if isinstance(candidate_tables, list):
                    for item in candidate_tables:
                        if isinstance(item, dict):
                            add_table(
                                item.get("table")
                                or item.get("name")
                                or item.get("table_name"),
                                item.get("columns") or item.get("fields"),
                            )
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        decoder = json.JSONDecoder()
        for match in re.finditer(r"[\{\[]", text or ""):
            try:
                obj, _ = decoder.raw_decode(text[match.start():])
            except json.JSONDecodeError:
                continue
            walk(obj)

        ddl_pattern = re.compile(
            r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"\[]?(\w+)[`\"\]]?\s*\((.*?)\)\s*;",
            re.IGNORECASE | re.DOTALL,
        )
        for match in ddl_pattern.finditer(text or ""):
            table_name = match.group(1)
            columns = []
            for raw_line in match.group(2).splitlines():
                line = raw_line.strip().rstrip(",")
                if not line:
                    continue
                first_token = line.split(None, 1)[0].strip("`\"[]")
                if first_token.upper() in {
                    "PRIMARY",
                    "FOREIGN",
                    "UNIQUE",
                    "KEY",
                    "CONSTRAINT",
                    "CHECK",
                    "INDEX",
                }:
                    continue
                columns.append(first_token)
            add_table(table_name, columns)

        class_pattern = re.compile(
            r"^\s*class\s+\w+\([^)]*\):(?P<body>.*?)(?=^\s*class\s+\w+\([^)]*\):|\Z)",
            re.IGNORECASE | re.DOTALL | re.MULTILINE,
        )
        for match in class_pattern.finditer(text or ""):
            body = match.group("body")
            table_match = re.search(
                r"__tablename__\s*=\s*['\"]([^'\"]+)['\"]",
                body,
                re.IGNORECASE,
            )
            if not table_match:
                continue
            columns = re.findall(r"^\s*(\w+)\s*=\s*Column\s*\(", body, re.MULTILINE)
            add_table(table_match.group(1), columns)

        return tables

    def _camel_variant(self, name: str) -> str:
        return "".join(part.capitalize() for part in re.split(r"[_\W]+", name) if part)

    def _check_fact_constraints(
        self,
        subtask: Subtask,
        output_data: str,
        artifact_type: str,
        context_data: str,
    ) -> Tuple[bool, str]:
        schema_tables = self._extract_schema_tables_from_text(context_data)
        if not schema_tables:
            return True, ""

        task_text = f"{subtask.description}\n{subtask.expected_output}".lower()
        if not any(
            marker in task_text
            for marker in (
                "crud",
                "fastapi",
                "backend",
                "schema",
                '\u8868\u7ed3\u6784',
                '\u5b89\u5168',
                '\u5ba1\u8ba1',
                "audit",
                "sql",
            )
        ):
            return True, ""

        output_lower = (output_data or "").lower()
        missing_tables: List[str] = []
        for table_name in schema_tables:
            table_lower = table_name.lower()
            variants = {
                table_lower,
                table_lower.replace("_", ""),
                self._camel_variant(table_name).lower(),
            }
            if table_lower.endswith("s") and len(table_lower) > 1:
                variants.add(table_lower[:-1])
            if not any(variant and variant in output_lower for variant in variants):
                missing_tables.append(table_name)

        missing_columns: Dict[str, List[str]] = {}
        if (artifact_type or "").lower() == "code":
            for table_name, columns in schema_tables.items():
                missing = [
                    column
                    for column in sorted(columns)
                    if column.lower() not in output_lower
                ]
                if missing:
                    missing_columns[table_name] = missing

        if missing_tables or missing_columns:
            reasons = []
            if missing_tables:
                reasons.append("missing tables: " + ", ".join(sorted(missing_tables)))
            if missing_columns:
                column_bits = [
                    f"{table}({', '.join(cols)})"
                    for table, cols in sorted(missing_columns.items())
                ]
                reasons.append("missing schema columns: " + "; ".join(column_bits))
            return (
                False,
                "Output violates upstream schema facts; " + " | ".join(reasons),
            )

        return True, ""

    async def _execute_full_generative(
        self,
        desc: str,
        context_data: str,
        artifact_type: str,
        expected_output: str = "",
        feedback: str = "",
        subtask_id: str | None = None,
    ) -> ExecutionResult:
        smart_exec = SmartExecutor(
            api_key=self.llm_api_key,
            base_url=self.llm_base_url,
            model=self.model,
            cost_ledger=self.cost_ledger,
            transport=self.async_model_transport,
        )
        full_context = context_data
        if feedback:
            full_context += f"\n\n--- [Full-Generative Fallback Reason] ---\n{feedback}\n"
        file_context = self._extract_local_file_context(desc + "\n" + full_context)
        if file_context:
            full_context += f"\n\n--- [Resolved Local File Context] ---\n{file_context}\n"
        result = await smart_exec.execute(
            desc,
            full_context,
            model=self.model,
            accounting_stage="full_generation",
            subtask_id=subtask_id,
            subtask_revision=(0 if subtask_id else None),
            artifact_type=artifact_type,
            temperature=self.execution_temperature,
            final_output_contract=self._build_final_output_contract(
                desc,
                expected_output,
                artifact_type,
                full_context,
                repair_feedback=feedback,
            ),
        )
        result.cost_metric["fallback_used"] = True
        result.cost_metric["actual_runtime_mode"] = ExecutionMode.FULL_GENERATIVE.value
        return result

    def _strip_code_fences(self, text: str) -> str:
        stripped = (text or "").strip()
        fence_match = re.search(r"```(?:python|py)?\s*(.*?)```", stripped, re.DOTALL | re.IGNORECASE)
        if fence_match:
            return fence_match.group(1).strip()
        return stripped

    def _materialize_generated_code(
        self,
        task_id: str,
        step: ResourceApplicationStep,
        step_outputs: Dict[str, str],
        resource_index: Dict[str, dict],
    ) -> Tuple[bool, str, str, Dict[str, Any]]:
        """Write an upstream code artifact to a workspace-local file for executor tools."""
        explicit_path_values: List[str] = []
        code_values: List[str] = []
        runner_ref = TypedResourceRef(resource_id=step.resource_id, resource_type=ManifestType.TOOL)
        allowed_packages = sorted(
            self._manifest_python_package_names(resource_index.get(runner_ref.resource_id, {}))
        )

        cwd_ok, cwd_failure_type, cwd_reason, resolved_cwd = (
            self._resolve_generated_runner_cwd(
                step,
                resource_index,
                step_outputs,
                defer_step_output=False,
            )
        )
        if not cwd_ok:
            return False, cwd_failure_type, cwd_reason, {}

        def runner_bindings(script_path: str) -> Dict[str, Any]:
            bindings: Dict[str, Any] = {"script_path": script_path, "cwd": "."}
            if resolved_cwd is not None:
                bindings["cwd"] = resolved_cwd
            args_key = next(
                (
                    key
                    for key in ("arg_json", "args", "cli_args")
                    if key in step.input_bindings
                ),
                None,
            )
            if args_key is not None:
                args_hint = step.input_bindings[args_key]
                args_list = self._normalize_cli_arg_list(args_hint, resource_index, step_outputs)
                # Keep argv structured until the invocation adapter.  Encoding
                # here would turn an argument list into one JSON-string argument
                # and then encode it a second time below.
                bindings["arg_json"] = args_list
            return bindings

        def checked_runner_bindings(script_path: str) -> Tuple[bool, str, str, Dict[str, Any]]:
            _, missing_deps, _ = self._check_python_artifact_dependencies(
                source_path=script_path,
                allowed_packages=allowed_packages,
            )
            b = runner_bindings(script_path)
            # Layer-0: instead of rejecting, hand the missing imports to the main
            # flow to provision (pip install) before running the script.
            if missing_deps:
                b["_sgar_provision"] = ",".join(missing_deps)
            return True, "", "", b

        for binding_value in step.input_bindings.values():
            for record in self._step_registry_records_from_binding(task_id, binding_value):
                if record.artifact_type == "code" and os.path.isfile(record.path):
                    return checked_runner_bindings(record.path)

        for key in ("script_path", "file_path", "path"):
            if key in step.input_bindings:
                explicit_path_values.extend(
                    self._resolve_source_hint_values(step.input_bindings[key], resource_index, step_outputs)
                )
        for key in ("code", "script", "source", "input"):
            if key in step.input_bindings:
                code_values.extend(
                    self._resolve_source_hint_values(step.input_bindings[key], resource_index, step_outputs)
                )

        for value in explicit_path_values:
            resolved = self._resolve_candidate_path(value)
            if os.path.isfile(resolved):
                return checked_runner_bindings(resolved)
            if self._content_looks_like_path(value):
                return (
                    False,
                    "unsafe_execution_path",
                    f"Step {step.step_id} requested script_path that does not exist: {value}",
                    {},
                )
            if self._content_looks_like_raw_text(value):
                code_values.append(value)

        for key in ("output_key", "from_output", "artifact_key", "context_key", "from_step"):
            hint = step.input_bindings.get(key)
            if isinstance(hint, str):
                for record in self._step_registry_records_for_hint(task_id, hint):
                    if record.artifact_type == "code" and os.path.isfile(record.path):
                        return checked_runner_bindings(record.path)
                if hint in step_outputs:
                    code_values.append(step_outputs[hint])

        if (
            not code_values
            and step_outputs
            and bool(getattr(self, "_active_allow_semantic_normalization", True))
        ):
            code_values.append(next(reversed(step_outputs.values())))

        for value in code_values:
            if self._content_looks_like_path(value):
                resolved = self._resolve_candidate_path(value)
                if os.path.isfile(resolved):
                    return True, "", "", runner_bindings(resolved)
                continue
            if not self._looks_like_python_code(value):
                continue
            ok, failure_type, reason, record = self._materialize_step_output(
                task_id,
                step,
                step.output_key,
                value,
                "code",
                preferred_name=f"{step.step_id}_input",
            )
            if ok and record is not None:
                return checked_runner_bindings(record.path)
            return False, failure_type, reason, {}

        if explicit_path_values:
            return (
                False,
                "binding_invalid",
                f"Step {step.step_id} did not receive executable Python code or an existing script path.",
                {},
            )
        if code_values:
            return (
                False,
                "binding_invalid",
                f"Step {step.step_id} received content that is not safe Python code.",
                {},
            )
        return (
            False,
            "tool_missing_required_input",
            f"Step {step.step_id} could not resolve generated code to execute.",
            {},
        )

    def _resolve_generated_runner_cwd(
        self,
        step: ResourceApplicationStep,
        resource_index: Dict[str, dict],
        step_outputs: Dict[str, str],
        *,
        defer_step_output: bool,
    ) -> Tuple[bool, str, str, Optional[str]]:
        """Resolve the generated runner's path-valued ``cwd`` contract.

        The runner manifest declares ``cwd`` as an explicit string, so the
        shared binding resolver correctly keeps its literal opaque.  The runner
        adapter consumes it as a directory, however, and must validate it at
        this boundary.  A Plan-authored path outside the sandbox is a research
        binding/executability failure.  A registered handle that cannot be
        mapped remains a framework invariant.
        """

        cwd_hint = (
            step.input_bindings["cwd"]
            if "cwd" in step.input_bindings
            else step.input_bindings.get("working_dir")
        )
        if cwd_hint is None:
            return True, "", "", None
        try:
            source = parse_binding_source(cwd_hint)
        except BindingProtocolError as exc:
            return False, exc.code, str(exc), None
        if defer_step_output and source.variant == "step_output":
            return True, "", "", None
        try:
            values = self._resolve_source_hint_values(
                cwd_hint,
                resource_index,
                step_outputs,
            )
        except BindingFrameworkError:
            raise
        except BindingProtocolError as exc:
            return False, exc.code, str(exc), None
        if len(values) != 1:
            return (
                False,
                "binding_ambiguous",
                "Generated-code runner cwd must resolve to exactly one directory.",
                None,
            )
        cwd_value = str(values[0])
        if not cwd_value.strip() or cwd_value.strip() == ".":
            return True, "", "", None
        try:
            resolved = self._resolve_candidate_path(cwd_value)
        except PathNamespaceError as exc:
            if source.variant in {"artifact_handle", "resource"}:
                raise BindingFrameworkError(
                    "registered_binding_path_unmappable",
                    "A registered generated-code cwd is not represented by the active sandbox scope.",
                ) from exc
            return (
                False,
                "binding_path_out_of_scope",
                "Generated-code runner cwd is outside the active sandbox scope.",
                None,
            )
        if not os.path.isdir(resolved) or not self._is_workspace_path(resolved):
            return (
                False,
                "runner_cwd_error",
                "Generated-code runner cwd is not an authorized existing directory.",
                None,
            )
        return True, "", "", resolved

    def _prepare_validation_bindings(
        self,
        task_id: str,
        step: ResourceApplicationStep,
        selected: List[TypedResourceRef],
        resource_index: Dict[str, dict],
        desc: str,
        context_data: str,
        step_outputs: Dict[str, str],
    ) -> Tuple[bool, str, str, Dict[str, str]]:
        allow_inference = bool(
            getattr(self, "_active_allow_semantic_normalization", True)
        )
        raw = resource_index.get(step.resource_id, {})
        contracts = self._manifest_input_contracts(raw)
        target_name = "target_paths"
        for contract in contracts:
            name = str(contract.get("name") or "")
            if name in {"target_paths", "target_path", "file_path", "path", "input_path"}:
                target_name = name
                break
        plural_targets = target_name == "target_paths"

        def build_targets(
            paths: List[str],
            target_role: str,
            sources: Optional[List[str]] = None,
            handles: Optional[List[ArtifactHandle]] = None,
        ) -> Tuple[bool, str, str, Dict[str, str]]:
            unique = []
            seen = set()
            for item in paths:
                resolved = self._resolve_candidate_path(item)
                if resolved in seen:
                    continue
                if not self._is_workspace_path(resolved):
                    return (
                        False,
                        "unsafe_validation_target",
                        f"Validation target escaped workspace: {item}",
                        {},
                    )
                if not os.path.isfile(resolved):
                    continue
                if (
                    "pytest_runner" in str(step.resource_id)
                    and target_role != "explicit_input_check"
                    and not self._is_current_run_artifact_path(resolved)
                ):
                    if self._is_preexisting_bench_test_path(resolved):
                        return (
                            False,
                            "wrong_validation_target",
                            "pytest_runner target is a pre-existing bench test file, not a current-run generated artifact.",
                            {},
                        )
                    return (
                        False,
                        "validation_target_missing",
                        "pytest_runner target must come from the current-run artifact registry or a safe task alias.",
                        {},
                    )
                seen.add(resolved)
                unique.append(resolved)
            if not unique:
                return False, "validation_target_missing", f"Step {step.step_id} has no materialized validation target.", {}
            if len(unique) > 1 and not plural_targets:
                return (
                    False,
                    "validation_target_ambiguous",
                    f"Step {step.step_id} resolved multiple validation targets for single-file input '{target_name}'.",
                    {},
                )
            if len(unique) == 1:
                binding = {
                    target_name: self._to_tool_path(unique[0]),
                    "_target_role": target_role,
                    "_target_sources": ",".join(sources or []),
                }
                if handles:
                    binding.update(
                        {
                            "_selected_handle_id": handles[0].handle_id,
                            "_selected_handle_kind": handles[0].kind,
                            "_selected_handle_logical_path": handles[0].logical_path or "",
                            "_selected_handle_tool_path": handles[0].tool_path or "",
                        }
                    )
                return True, "", "", binding
            targets_dir = os.path.abspath(os.path.join(self.artifact_dir, "validation_targets"))
            os.makedirs(targets_dir, exist_ok=True)
            targets_path = os.path.abspath(os.path.join(targets_dir, f"{step.step_id}_targets.json"))
            try:
                if os.path.commonpath([targets_dir, targets_path]) != targets_dir:
                    return False, "unsafe_validation_target", "Validation target path escaped artifact directory.", {}
            except ValueError:
                return False, "unsafe_validation_target", "Validation target path escaped artifact directory.", {}
            with open(targets_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "target_paths": [self._to_tool_path(path) for path in unique],
                        "target_role": target_role,
                        "sources": sources or [],
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            return True, "", "", {
                target_name: self._to_tool_path(targets_path),
                "_target_role": target_role,
                "_target_sources": ",".join(sources or []),
            }

        def explicit_input_check() -> bool:
            mode = (
                step.input_bindings.get("validation_mode")
                or step.input_bindings.get("target_role")
                or step.input_bindings.get("mode")
            )
            if isinstance(mode, str) and mode.lower() in {
                "input",
                "input_file",
                "input_files",
                "validate_input_files",
                "explicit_input_check",
            }:
                return True
            return False

        def expected_validation_kinds() -> Set[str]:
            if "pytest_runner" in str(step.resource_id):
                return {"test_overlay", "step_artifact", "contract_alias"}
            if explicit_input_check():
                return {"input_file", "source_overlay", "test_overlay", "step_artifact", "task_final", "contract_alias", "tool_output"}
            return {"source_overlay", "test_overlay", "step_artifact", "task_final", "contract_alias", "tool_output"}

        def extract_handle_refs(value: Any) -> List[str]:
            refs: List[str] = []
            if isinstance(value, dict):
                handle_id = value.get("artifact_handle") or value.get("handle_id")
                if handle_id:
                    refs.append(str(handle_id))
                for nested in value.values():
                    refs.extend(extract_handle_refs(nested))
            elif isinstance(value, (list, tuple)):
                for item in value:
                    refs.extend(extract_handle_refs(item))
            return refs

        def validator_misuse_reason(source_hint: Any, values: List[str]) -> Optional[str]:
            intent = str(step.intent or "").lower()
            if any(marker in intent for marker in ("read ", "reference", "inject", "parse", "context", "upstream prose")):
                if not explicit_input_check() and not self._binding_refers_to_step_output(source_hint, step_outputs):
                    return "artifact_validator cannot be used as a reader or context parser."
            if explicit_input_check() or self._binding_refers_to_step_output(source_hint, step_outputs):
                return None
            for value in values:
                text = str(value or "")
                if self._content_looks_like_raw_text(text) or "\n" in text:
                    return "artifact_validator target is raw text, not a materialized artifact path."
            return None

        target_hint = step.input_bindings.get(target_name)
        if target_hint is None:
            for key in ("file_path", "path", "input_path", "target_path"):
                if key in step.input_bindings:
                    target_hint = step.input_bindings[key]
                    break

        handle_targets: List[str] = []
        selected_handles: List[ArtifactHandle] = []
        for handle_ref in extract_handle_refs(target_hint):
            ok_h, failure_h, reason_h, handle = self.workspace_handle_resolver.resolve_handle(
                handle_ref,
                expected_kinds=expected_validation_kinds(),
            )
            if not ok_h or handle is None:
                return False, failure_h, reason_h, {}
            if handle.kind == "validation_result":
                return (
                    False,
                    "artifact_handle_kind_mismatch",
                    f"Validation result handle {handle_ref} is evidence, not a file validation target.",
                    {},
                )
            if not handle.host_path:
                return False, "artifact_handle_missing", f"Artifact handle has no file target: {handle_ref}", {}
            handle_targets.append(handle.host_path)
            selected_handles.append(handle)
        if handle_targets:
            return build_targets(
                handle_targets,
                "explicit_input_check" if explicit_input_check() else "generated_artifact",
                [f"artifact_handle:{handle.handle_id}" for handle in selected_handles],
                selected_handles,
            )

        try:
            explicit_values = (
                self._resolve_source_hint_values(
                    target_hint,
                    resource_index,
                    step_outputs,
                )
                if target_hint is not None
                else []
            )
        except BindingProtocolError as exc:
            # A validator may consume a materialized artifact by its exact
            # (task, step, output) registry identity even when the in-memory
            # text output is no longer present.  Defer only that data-plane
            # miss to the registry lookup below.  Malformed/ambiguous source
            # objects remain fail-closed at the shared binding boundary.
            if (
                exc.code != "binding_step_output_missing"
                or not self._binding_refers_to_step_output(
                    target_hint,
                    step_outputs,
                )
            ):
                return False, exc.code, str(exc), {}
            explicit_values = []
        # A literal target binding is itself evidence for semantic validation.
        # Resolution intentionally ignores many non-path literals, so retain the
        # original string here to reject raw prose before any path guessing.
        if isinstance(target_hint, str) and target_hint not in explicit_values:
            explicit_values.append(target_hint)
        misuse_reason = validator_misuse_reason(target_hint, explicit_values)
        if misuse_reason:
            return False, "tool_semantic_misuse", f"Step {step.step_id}: {misuse_reason}", {}

        targets: List[str] = []
        registry_sources = [target_hint] if target_hint is not None else list(step.input_bindings.values())
        registry_source_names: List[str] = []
        for source in registry_sources:
            is_exact_step_binding = (
                isinstance(source, dict)
                and bool(source.get("from_step") or source.get("step_id"))
                and bool(
                    source.get("output_key")
                    or source.get("from_output")
                    or source.get("artifact_key")
                    or source.get("context_key")
                )
            )
            for record in self._step_registry_records_from_binding(task_id, source):
                preferred_path = (
                    self._preferred_pytest_target_for_record(record)
                    if "pytest_runner" in str(step.resource_id)
                    else record.path
                )
                if os.path.isfile(preferred_path):
                    targets.append(preferred_path)
                    registry_source_names.append(
                        "exact_step_registry" if is_exact_step_binding else f"registry:{record.origin}"
                    )
        if targets:
            return build_targets(targets, "generated_artifact", registry_source_names)

        if (
            allow_inference
            and "pytest_runner" in str(step.resource_id)
            and target_hint is None
        ):
            overlay_targets = [
                record.path
                for record in self.artifact_registry.source_overlays.values()
                if record.artifact_type == "code"
                and os.path.isfile(record.path)
                and (
                    "/tests/" in record.metadata.get("original_workspace_path", "").replace("\\", "/").lower()
                    or os.path.basename(record.path).lower().startswith("test_")
                )
            ]
            if overlay_targets:
                return build_targets(overlay_targets, "generated_artifact", ["source_overlay"])

        raw_path_failure: Optional[Tuple[str, str]] = None
        normalized_path_handles: List[ArtifactHandle] = []
        for value in explicit_values:
            text = str(value or "")
            if self._content_looks_like_path(text):
                if not explicit_input_check():
                    ok_h, failure_h, reason_h, handle = self.workspace_handle_resolver.resolve_current_run_logical_path(
                        text,
                        expected_kinds=expected_validation_kinds(),
                        expected_artifact_type="code" if "pytest_runner" in str(step.resource_id) else None,
                    )
                    if ok_h and handle is not None and handle.host_path:
                        targets.append(handle.host_path)
                        registry_source_names.append(f"artifact_handle:{handle.handle_id}")
                        normalized_path_handles.append(handle)
                        continue
                    if failure_h == "artifact_handle_ambiguous":
                        return False, failure_h, reason_h, {}
                    if failure_h:
                        raw_path_failure = (failure_h, reason_h)
                resolved = self._resolve_candidate_path(text)
                if (
                    os.path.isfile(resolved)
                    and self._is_workspace_path(resolved)
                    and (explicit_input_check() or self._is_current_run_artifact_path(resolved))
                ):
                    targets.append(resolved)
                continue
            if self._content_looks_like_raw_text(text):
                if not self._binding_refers_to_step_output(target_hint, step_outputs):
                    continue
                inferred_type = self._infer_artifact_type_from_content(text, default="plaintext")
                ok_m, failure_type, reason, record = self._materialize_step_output(
                    task_id,
                    step,
                    step.output_key,
                    text,
                    inferred_type,
                    preferred_name=f"{step.step_id}_validation_target",
                )
                if not ok_m or record is None:
                    return False, failure_type, reason, {}
                targets.append(record.path)

        if targets:
            role = "explicit_input_check" if explicit_input_check() else "generated_artifact"
            source_label = (
                "current_step_output"
                if self._binding_refers_to_step_output(target_hint, step_outputs)
                else "explicit_current_artifact"
            )
            return build_targets(
                targets,
                role,
                registry_source_names or [source_label],
                normalized_path_handles if len(normalized_path_handles) == len(targets) else None,
            )

        if raw_path_failure and not explicit_input_check():
            return False, raw_path_failure[0], raw_path_failure[1], {}

        if allow_inference and explicit_input_check():
            input_targets = self._extract_existing_file_paths(
                "\n".join(
                    [
                        desc,
                        step.intent or "",
                        json.dumps(step.input_bindings, ensure_ascii=False, default=str),
                    ]
                )
            )
            input_targets = [
                path for path in input_targets
                if self._is_workspace_path(path)
                and os.path.isfile(path)
                and "/output/" not in path.replace("\\", "/").lower()
            ]
            if input_targets:
                return build_targets(input_targets, "explicit_input_check", ["resolved_local_input"])

        if allow_inference and step_outputs:
            latest_key, latest_value = next(reversed(step_outputs.items()))
            inferred_type = self._infer_artifact_type_from_content(latest_value, default="plaintext")
            ok_m, failure_type_m, reason_m, record = self._materialize_step_output(
                task_id,
                step,
                latest_key,
                latest_value,
                inferred_type,
                preferred_name=f"{step.step_id}_{latest_key}_validation_target",
            )
            if ok_m and record is not None:
                return build_targets([record.path], "generated_artifact", [f"step_output:{latest_key}"])
            return False, failure_type_m, reason_m, {}

        return (
            False,
            "validation_target_missing",
            f"Step {step.step_id} could not resolve a generated artifact or explicit input-check target to validate.",
            {},
        )

    def _realize_resource_call_result(
        self,
        *,
        canonical_result: ResourceCallResult,
        resource_application: Any,
    ) -> ExecutionResult:
        """Close a formal Resource result into the sealed node-artifact contract."""

        if canonical_result.status != ResourceCallStatus.SUCCESS:
            return resource_result_to_execution_result(
                canonical_result,
                native_output_contract=(
                    resource_application.resource_native_output_contract
                    if resource_application is not None else None
                ),
            )
        if resource_application is None:
            return resource_result_to_execution_result(canonical_result)
        realization_contract = resource_application.output_realization_contract
        if realization_contract is None:
            return self._structured_failure_result(
                "stage_a_controller_required_not_deterministic",
                "The sealed Resource output cannot be realized deterministically.",
            )
        source_contract = (
            resource_application.available_semantic_output_contract
            if realization_contract.source_view == "semantic"
            else resource_application.resource_native_output_contract
        )
        if not isinstance(source_contract, Mapping):
            return self._structured_failure_result(
                "sealed_output_realization_source_contract_missing",
                "The sealed output realization source contract is unavailable.",
            )
        realization = self.output_realizer.realize(
            resource_call_id=canonical_result.call_id,
            resource_id=canonical_result.resource_id,
            operation_id=resource_application.capability_operation_id,
            native_value=canonical_result.native_value,
            native_content=canonical_result.native_content,
            native_output_sha256=canonical_result.native_output_sha256,
            semantic_view_available=canonical_result.semantic_view_available,
            semantic_value=canonical_result.semantic_value,
            semantic_content=canonical_result.semantic_content,
            semantic_output_sha256=canonical_result.semantic_output_sha256,
            source_contract=source_contract,
            target_contract=resource_application.target_step_output_contract.model_dump(
                mode="json"
            ),
            contract=realization_contract,
        )
        ledger = getattr(self, "execution_ledger", None)
        if ledger is not None:
            ledger.record_output_realization(
                resource_call_id=canonical_result.call_id,
                realization_id=realization.realization_id,
                realization_kind=realization.metrics.realization_kind,
                status=realization.status,
                source_bytes=realization.metrics.source_bytes,
                target_bytes=realization.metrics.target_bytes,
                latency_ms=realization.metrics.latency_ms,
                output_realization_contract_sha256=(
                    realization_contract.contract_sha256
                ),
                realized_output_sha256=(
                    realization.provenance.realized_output_sha256
                    if realization.provenance is not None
                    else None
                ),
                failure_code=realization.failure_code,
            )
        return resource_result_to_execution_result(
            canonical_result,
            realization_result=realization,
        )

    async def _execute_legacy_resource_with_events(
        self,
        *,
        ref: TypedResourceRef,
        raw_manifest: Mapping[str, Any],
        execution_context: Optional[ResourceExecutionContext],
        resolved_bindings: Mapping[str, Any],
        provenance_source_ids: Sequence[str],
        runtime_kind: str,
        network_required: bool,
        provider: Callable[[], Any],
        output_contract: Mapping[str, Any] | None = None,
        dag_edge_contract_sha256s: Sequence[str] = (),
        advisory_profile_refs: Sequence[str] = (),
        capability_operation_id: str = "",
        semantic_task_contract: Mapping[str, Any] | None = None,
        acceptance_requirements: Sequence[str] = (),
        advisory_materials: Sequence[Mapping[str, Any]] = (),
    ) -> ExecutionResult:
        """Record an existing non-Tool kernel without changing or repeating it."""

        if bool(getattr(self, "_formal_execution_active", False)):
            raise RuntimeError("formal_legacy_resource_adapter_forbidden")

        resource_runtime = getattr(self, "resource_runtime", None)
        if resource_runtime is None:
            if self.execution_substrate is not None:
                raise RuntimeError("UNBOUND_RUNTIME_PATH:external_resource_runtime_missing")
            value = provider()
            return await value if asyncio.iscoroutine(value) else value
        if execution_context is None:
            raise RuntimeError("formal_resource_execution_context_missing")
        try:
            definition = ResourceDefinition.from_manifest(raw_manifest)
            definition.entrypoint("invoke")
        except ResourceCallValidationError:
            return ExecutionResult(
                is_success=False,
                output_data="",
                error_log="unknown_resource_entrypoint",
                cost_metric={
                    "failure_type": "unknown_resource_entrypoint",
                    "failure_layer": "research",
                },
            )
        except (ResourceManifestError, ValueError) as exc:
            return ExecutionResult(
                is_success=False,
                output_data="",
                error_log="resource_manifest_invalid",
                cost_metric={
                    "failure_type": "resource_manifest_invalid",
                    "failure_layer": "framework",
                    "failure": {
                        "responsibility": "framework",
                        "failure_stage": "resource_definition",
                        "retryable": False,
                        "response_received": False,
                        "exception_type": type(exc).__name__,
                    },
                },
            )
        world = ExecutionWorldDescriptor(
            runtime_kind=runtime_kind,
            environment_sha256=definition.manifest_sha256,
            dependency_lock_sha256=canonical_sha256(
                definition.runtime_requirements
            ),
            runtime_request_sha256=canonical_sha256(
                {
                    "resource_id": definition.resource_id,
                    "entrypoint_id": "invoke",
                    "runtime_kind": runtime_kind,
                    "plan_sha256": execution_context.plan_sha256,
                    "step_id": execution_context.step_id,
                }
            ),
            sandbox_scope_sha256=execution_context.sandbox_scope_sha256,
            network_required=network_required,
            direct_argv=True,
        )
        request = ResourceCallRequest(
            resource_definition=definition,
            entrypoint_id="invoke",
            execution_context=execution_context,
            resolved_bindings=self._portable_binding_tree(resolved_bindings),
            capability_operation_id=(
                capability_operation_id
                or next(
                    (
                        item.capability_operation_id
                        for item in definition.capability_card.capability_operations
                        if item.entrypoint_id in {None, "invoke"}
                    ),
                    "legacy.invoke",
                )
            ),
            semantic_task_contract=dict(
                semantic_task_contract
                or {"legacy_step_id": execution_context.step_id}
            ),
            advisory_materials=tuple(dict(item) for item in advisory_materials),
            acceptance_requirements=tuple(
                acceptance_requirements
                or ("Return the declared output contract.",)
            ),
            execution_world=world,
            resource_native_output_contract=dict(
                definition.entrypoint("invoke").output_contract
            ),
            target_output_contract=dict(
                output_contract or definition.base_output_contract
            ),
            provenance_source_ids=tuple(provenance_source_ids),
            dag_edge_contract_sha256s=tuple(dag_edge_contract_sha256s),
            advisory_profile_refs=tuple(advisory_profile_refs),
        )

        async def existing_kernel(_request: ResourceCallRequest) -> ExecutionResult:
            value = provider()
            return await value if asyncio.iscoroutine(value) else value

        canonical = await resource_runtime.execute(
            request,
            provider=existing_kernel,
        )
        return resource_result_to_execution_result(canonical)

    @staticmethod
    def _formal_material_descriptor(
        source_id: str,
        handle: ArtifactHandle,
    ) -> tuple[MaterialDescriptorV1, str | None]:
        """Bind an authorized handle to exact bytes without path/type inference.

        UTF-8 files are projected in full for Model/Agent execution. Binary
        material remains handle-only so Tool runtimes can consume it without
        exposing opaque bytes to a model.
        """

        if not handle.host_path:
            content_sha256 = str(
                (handle.provenance or {}).get("content_sha256") or ""
            )
            if not re.fullmatch(r"[0-9a-f]{64}", content_sha256):
                raise RuntimeError("formal_authorized_material_task_hash_missing")
            return (
                MaterialDescriptorV1(
                    source_id=source_id,
                    logical_name=str(handle.logical_path or handle.handle_id),
                    artifact_type=str(handle.artifact_type),
                    content_sha256=content_sha256,
                    original_bytes=int((handle.provenance or {}).get("byte_size") or 0),
                    included_bytes=0,
                    included_sha256=None,
                    coverage_status="handle_only",
                    handle_id=handle.handle_id,
                    runtime_path=handle.tool_path,
                    # A remote-only handle does not prove an encoding either
                    # way. The selected adapter must establish its content.
                    utf8_decodable=None,
                ),
                None,
            )
        source_path = Path(handle.host_path)
        if not source_path.is_file():
            raise RuntimeError("formal_authorized_material_not_regular_file")
        try:
            raw_material = source_path.read_bytes()
        except OSError as exc:
            raise RuntimeError("formal_authorized_material_read_failed") from exc
        try:
            authorized_content = raw_material.decode("utf-8", errors="strict")
            utf8_decodable = True
        except UnicodeDecodeError:
            authorized_content = None
            utf8_decodable = False
        content_sha256 = hashlib.sha256(raw_material).hexdigest()
        return (
            MaterialDescriptorV1(
                source_id=source_id,
                logical_name=str(handle.logical_path or handle.handle_id),
                artifact_type=str(handle.artifact_type),
                content_sha256=content_sha256,
                original_bytes=len(raw_material),
                included_bytes=(len(raw_material) if utf8_decodable else 0),
                included_sha256=(content_sha256 if utf8_decodable else None),
                coverage_status=("complete" if utf8_decodable else "handle_only"),
                handle_id=handle.handle_id,
                runtime_path=handle.tool_path,
                utf8_decodable=utf8_decodable,
            ),
            authorized_content,
        )

    async def _execute_formal_resource_with_events(
        self,
        *,
        ref: TypedResourceRef,
        raw_manifest: Mapping[str, Any],
        execution_context: Optional[ResourceExecutionContext],
        resolved_bindings: Mapping[str, Any],
        provenance_source_ids: Sequence[str],
        runtime_kind: str,
        network_required: bool,
        provider: Callable[[ResourceCallRequest], Any],
        output_contract: Mapping[str, Any] | None = None,
        resource_application: Any = None,
        dag_edge_contract_sha256s: Sequence[str] = (),
        advisory_profile_refs: Sequence[str] = (),
        capability_operation_id: str = "",
        semantic_task_contract: Mapping[str, Any] | None = None,
        acceptance_requirements: Sequence[str] = (),
        advisory_materials: Sequence[Mapping[str, Any]] = (),
    ) -> ExecutionResult:
        """Run a formal non-Tool provider through the canonical result boundary."""

        resource_runtime = getattr(self, "resource_runtime", None)
        if resource_runtime is None:
            raise RuntimeError("formal_resource_runtime_missing")
        if execution_context is None:
            raise RuntimeError("formal_resource_execution_context_missing")
        try:
            definition = ResourceDefinition.from_manifest(raw_manifest)
            definition.entrypoint("invoke")
        except ResourceCallValidationError:
            return self._structured_failure_result(
                "unknown_resource_entrypoint",
                "The sealed Plan names an unknown resource entrypoint.",
            )
        except (ResourceManifestError, ValueError) as exc:
            return ExecutionResult(
                is_success=False,
                output_data="",
                error_log="resource_manifest_invalid",
                cost_metric={
                    "failure_type": "resource_manifest_invalid",
                    "failure_layer": "framework",
                    "failure": {
                        "responsibility": "framework",
                        "failure_stage": "resource_definition",
                        "failure_code": "resource_manifest_invalid",
                        "retryable": False,
                        "response_received": False,
                        "exception_type": type(exc).__name__,
                    },
                },
            )
        world = ExecutionWorldDescriptor(
            runtime_kind=runtime_kind,
            environment_sha256=definition.manifest_sha256,
            dependency_lock_sha256=canonical_sha256(
                definition.runtime_requirements
            ),
            runtime_request_sha256=canonical_sha256(
                {
                    "resource_id": definition.resource_id,
                    "entrypoint_id": "invoke",
                    "runtime_kind": runtime_kind,
                    "plan_sha256": execution_context.plan_sha256,
                    "step_id": execution_context.step_id,
                }
            ),
            sandbox_scope_sha256=execution_context.sandbox_scope_sha256,
            network_required=network_required,
            direct_argv=True,
        )
        upstream_handles: List[ArtifactHandle] = []
        material_descriptors: List[MaterialDescriptorV1] = []
        authorized_material_content: Dict[str, str] = {}
        for source_id in provenance_source_ids:
            if not str(source_id).startswith("artifact:"):
                continue
            ok, failure_code, _, handle = self.resolve_artifact_handle(str(source_id))
            if not ok or handle is None:
                raise RuntimeError(failure_code or "formal_authorized_material_missing")
            upstream_handles.append(handle)
            descriptor, content = self._formal_material_descriptor(str(source_id), handle)
            material_descriptors.append(descriptor)
            if content is not None:
                authorized_material_content[str(source_id)] = content
        request = ResourceCallRequest(
            resource_definition=definition,
            entrypoint_id="invoke",
            execution_context=execution_context,
            resolved_bindings=self._portable_binding_tree(resolved_bindings),
            capability_operation_id=capability_operation_id,
            semantic_task_contract=dict(semantic_task_contract or {}),
            authorized_materials=tuple(material_descriptors),
            authorized_material_content=authorized_material_content,
            upstream_artifact_handles=tuple(upstream_handles),
            advisory_materials=tuple(dict(item) for item in advisory_materials),
            acceptance_requirements=tuple(acceptance_requirements),
            execution_world=world,
            resource_native_output_contract=dict(
                resource_application.resource_native_output_contract
                if resource_application is not None
                else definition.entrypoint("invoke").output_contract
            ),
            target_output_contract=dict(
                output_contract or definition.base_output_contract
            ),
            provenance_source_ids=tuple(provenance_source_ids),
            dag_edge_contract_sha256s=tuple(dag_edge_contract_sha256s),
            advisory_profile_refs=tuple(advisory_profile_refs),
        )

        async def formal_kernel(call_request: ResourceCallRequest):
            value = provider(call_request)
            legacy_result = await value if asyncio.iscoroutine(value) else value
            return execution_result_to_resource_result(
                legacy_result,
                call_id=call_request.call_id,
                resource_id=definition.resource_id,
                entrypoint_id="invoke",
                output_contract=dict(call_request.output_contract),
                provider_result_source=(
                    f"formal_{str(definition.resource_type).lower()}_provider"
                ),
                require_structured_failure=True,
            )

        canonical = await resource_runtime.execute(
            request,
            provider=formal_kernel,
        )
        return self._realize_resource_call_result(
            canonical_result=canonical,
            resource_application=resource_application,
        )

    async def _execute_resource_dag(
        self,
        task_id: str,
        plan: ResourceApplicationPlan,
        selected: List[TypedResourceRef],
        desc: str,
        context_data: str,
        artifact_type: str,
        expected_output: str,
        resource_index: Dict[str, dict],
        resolved_bindings: Dict[str, Dict[str, Any]],
        repair_feedback: str = "",
        task_output_contract: Optional[SubtaskOutputContract] = None,
        resource_execution_context: Optional[ResourceExecutionContext] = None,
        sealed_plan_sha256: Optional[str] = None,
        resume_checkpoints: Optional[Mapping[str, CompletedStepCheckpoint]] = None,
        resume_results: Optional[Mapping[str, ExecutionResult]] = None,
        formal_original_query: str = "",
        required_operation_kinds: Sequence[str] = (),
        required_workspace_effect: bool = False,
    ) -> ExecutionResult:
        """Execute a preflight-validated dynamic resource application plan."""
        step_outputs: Dict[str, str] = {}
        step_results: Dict[str, ExecutionResult] = {}
        step_trace: List[Dict[str, Any]] = []
        step_source_ids: Dict[str, str] = {}
        step_request_source_ids: Dict[str, List[str]] = {}
        verified_skill_loads = {}
        runtime_allowed_packages: Set[str] = set()
        resume_checkpoint_map = dict(resume_checkpoints or {})
        resume_result_map = dict(resume_results or {})
        execute_resource_with_events = (
            self._execute_formal_resource_with_events
            if bool(getattr(self, "_formal_execution_active", False))
            else self._execute_legacy_resource_with_events
        )
        if set(resume_checkpoint_map) != set(resume_result_map):
            raise RuntimeError("resume_checkpoint_result_set_mismatch")
        output_producer_by_key = {
            step.output_key: step.resource_id
            for step in plan.steps
        }
        if resource_execution_context is not None:
            plan_sha256 = sealed_plan_sha256 or canonical_sha256(
                plan.model_dump(mode="json")
            )
            if resource_execution_context.plan_sha256 != plan_sha256:
                raise RuntimeError("resource_execution_context_plan_mismatch")
        skill_producer_ids = set()
        if bool(getattr(self, "_formal_execution_active", False)):
            try:
                for controller in plan.steps:
                    if getattr(controller, "controller_session_spec", None) is not None:
                        validate_skill_requirements(plan, controller, resource_index)
                        skill_producer_ids.update(s.step_id for s in controller_skill_sources(plan, controller, resource_index))
            except (ControllerSkillError, ValueError) as exc:
                code = getattr(exc, "code", "controller_skill_binding_invalid")
                return ExecutionResult(is_success=False, output_data="", error_log=code,
                                       cost_metric={"failure_layer": "framework", "failure_type": code,
                                                    "failure_stage": "controller_skill_binding"})

        def record_step_metrics(result: ExecutionResult) -> None:
            step_trace[-1]["execution_metrics"] = {
                key: value
                for key, value in result.cost_metric.items()
                if key not in {"application_step_trace", "application_step_outputs"}
            }
            result.cost_metric["application_step_outputs"] = dict(step_outputs)
            result.cost_metric["application_step_trace"] = step_trace

        def provenance_source_ids(
            bound_outputs: Mapping[str, Any],
            *,
            request_step_id: str = "",
        ) -> List[str]:
            payload_guard = getattr(self, "_active_model_payload_guard", None)
            upstream_source_ids: List[str] = []
            if request_step_id:
                request_step = next(
                    (item for item in plan.steps if item.step_id == request_step_id),
                    None,
                )
                if request_step is None:
                    raise RuntimeError("formal_request_step_missing")
                for source_id in (
                    getattr(request_step, "consumed_context_source_ids", ()) or ()
                ):
                    normalized_source_id = str(source_id).strip()
                    if normalized_source_id.startswith("artifact:"):
                        handle = self._resolve_context_source_handle(
                            step=request_step, source_id=normalized_source_id
                        )
                        descriptor, content = self._formal_material_descriptor(
                            normalized_source_id,
                            handle,
                        )
                        if payload_guard is not None and hasattr(
                            payload_guard, "register_source"
                        ):
                            normalized_source_id = execution_source_id(
                                f"consumed:{request_step_id}:{normalized_source_id}")
                            payload_guard.register_source(
                                normalized_source_id,
                                origin=(
                                    "public_case"
                                    if handle.kind == "input_file"
                                    else "current_run_step_output"
                                ),
                                material={
                                    "artifact_handle": handle.model_dump(
                                        mode="json", exclude={"host_path"}
                                    ),
                                    "material_descriptor": descriptor.model_dump(
                                        mode="json"
                                    ),
                                    "authorized_content": content,
                                },
                                parent_source_ids=tuple(
                                    getattr(payload_guard, "default_source_ids", ())
                                    or ()
                                ),
                                producer={
                                    "step_id": request_step_id,
                                    "material_kind": "sealed_consumed_context",
                                },
                            )
                    if normalized_source_id and normalized_source_id not in upstream_source_ids:
                        upstream_source_ids.append(normalized_source_id)
            for source_id in step_request_source_ids.get(request_step_id, []):
                if source_id not in upstream_source_ids:
                    upstream_source_ids.append(source_id)
            for output_key in bound_outputs:
                source_id = step_source_ids.get(str(output_key))
                if source_id and source_id not in upstream_source_ids:
                    upstream_source_ids.append(source_id)
            if payload_guard is not None and hasattr(
                payload_guard, "derive_parent_source_ids"
            ):
                return list(
                    payload_guard.derive_parent_source_ids(
                        upstream_source_ids=tuple(upstream_source_ids)
                    )
                )
            return list(
                dict.fromkeys(
                    (*getattr(payload_guard, "default_source_ids", ()), *upstream_source_ids)
                )
            )

        def request_guard_for_step(
            step: ResourceApplicationStep,
            bound_outputs: Mapping[str, Any],
        ) -> Any:
            payload_guard = getattr(self, "_active_model_payload_guard", None)
            if payload_guard is None or not hasattr(payload_guard, "for_request"):
                return payload_guard
            bound_guard = payload_guard.for_request(
                "downstream_model",
                source_ids=provenance_source_ids(
                    bound_outputs,
                    request_step_id=step.step_id,
                ),
                request_identity={
                    "step_id": step.step_id,
                    "output_key": step.output_key,
                    "resource_id": step.resource_id,
                },
            )
            step_trace[-1]["model_request_provenance"] = dict(
                getattr(bound_guard, "attestation", {})
            )
            return bound_guard

        def execution_source_id(source_id: str) -> str:
            if resource_execution_context is None:
                return source_id
            return (f"execution:{resource_execution_context.run_id}:{resource_execution_context.subtask_id}:"
                    f"{resource_execution_context.subtask_revision}:{resource_execution_context.plan_sha256}:"
                    f"{resource_execution_context.attempt}:{source_id}")

        def register_request_source(
            step: ResourceApplicationStep,
            *,
            source_id: str,
            origin: str,
            material: Any,
            parent_source_ids: Sequence[str],
            producer: Mapping[str, Any],
        ) -> None:
            payload_guard = getattr(self, "_active_model_payload_guard", None)
            if payload_guard is None or not hasattr(payload_guard, "register_source"):
                return
            source_id = execution_source_id(source_id)
            source_audit = payload_guard.register_source(
                source_id,
                origin=origin,
                material=material,
                parent_source_ids=parent_source_ids,
                producer=producer,
            )
            step_request_source_ids.setdefault(step.step_id, []).append(source_id)
            step_trace[-1].setdefault("request_sources", []).append(source_audit)

        def register_step_output_source(
            step: ResourceApplicationStep,
            output_data: str,
            bound_outputs: Mapping[str, Any],
            *,
            executor_kind: str,
            execution_metrics: Mapping[str, Any] | None = None,
        ) -> None:
            payload_guard = getattr(self, "_active_model_payload_guard", None)
            if payload_guard is None or not hasattr(payload_guard, "register_source"):
                return
            metrics = dict(execution_metrics or {})
            if executor_kind == "Tool" and getattr(self, "_active_sandbox_scope", None):
                execution_audit = metrics.get("execution_audit")
                scoped_audit_valid = isinstance(execution_audit, Mapping) and (
                    execution_audit.get("direct_argv") is True
                    and execution_audit.get("runtime_argv_host_path_detected") is False
                    and execution_audit.get("host_paths_exposed") is False
                    and execution_audit.get("project_root_mounted") is False
                )
                external_scope = getattr(self, "_active_sandbox_scope", None) or {}
                external_audit_valid = (
                    self.execution_substrate is not None
                    and external_scope.get("protocol") == "sgar-external-task-scope/v1"
                    and isinstance(execution_audit, Mapping)
                    and execution_audit.get("protocol") == "sgar-external-task-scope/v1"
                    and execution_audit.get("task_namespace_validated") is True
                    and execution_audit.get("task_container_rpc") is True
                    and execution_audit.get("host_resource_source_executed") is False
                    and execution_audit.get("runtime_argv_host_path_detected") is False
                    and execution_audit.get("host_paths_exposed") is False
                    and execution_audit.get("project_root_mounted") is False
                )
                if not (scoped_audit_valid or external_audit_valid):
                    raise RuntimeError(
                        "tool_output_provenance_requires_valid_sandbox_audit"
                    )
            if executor_kind in {"Model", "Agent"}:
                transport_audit = metrics.get("transport_audit")
                if not isinstance(transport_audit, Mapping) or not (
                    transport_audit.get("status") == "checked"
                    and transport_audit.get("passed") is True
                    and transport_audit.get("response_received") is True
                ):
                    raise RuntimeError(
                        "model_output_provenance_requires_guarded_response"
                    )
            parents = provenance_source_ids(
                bound_outputs,
                request_step_id=step.step_id,
            )
            source_id = execution_source_id(f"step:{task_id}:{step.step_id}:{step.output_key}")
            source_audit = payload_guard.register_source(
                source_id,
                origin="current_run_step_output",
                material=output_data,
                parent_source_ids=parents,
                producer={
                    "step_id": step.step_id,
                    "output_key": step.output_key,
                    "resource_id": step.resource_id,
                    "executor_kind": executor_kind,
                    "request_hash": str(
                        next(
                            iter(
                                metrics
                                .get("transport_audit", {})
                                .get("request_hashes", [])
                            ),
                            "",
                        )
                    ),
                },
            )
            step_source_ids[step.output_key] = source_id
            step_source_ids[step.step_id] = source_id
            step_trace[-1]["output_provenance"] = source_audit

        def register_checkpoint_output_source(
            step: ResourceApplicationStep,
            checkpoint: CompletedStepCheckpoint,
            output_data: str,
        ) -> None:
            payload_guard = getattr(self, "_active_model_payload_guard", None)
            source_id = (
                f"checkpoint:{task_id}:{step.step_id}:{checkpoint.checkpoint_sha256}"
            )
            if payload_guard is not None and hasattr(payload_guard, "register_source"):
                source_audit = payload_guard.register_source(
                    source_id,
                    origin="current_run_checkpoint_output",
                    material=output_data,
                    parent_source_ids=checkpoint.provenance_source_ids,
                    producer={
                        "step_id": step.step_id,
                        "output_key": step.output_key,
                        "resource_id": step.resource_id,
                        "checkpoint_sha256": checkpoint.checkpoint_sha256,
                        "resource_call_id": checkpoint.resource_call_id,
                    },
                )
                step_trace[-1]["output_provenance"] = source_audit
            step_source_ids[step.output_key] = source_id
            step_source_ids[step.step_id] = source_id

        def step_overlay_task_view(step: ResourceApplicationStep, step_artifact_type: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
            step_contract = step.expected_output_contract.model_dump(mode="json") if step.expected_output_contract else {}
            task_contract = task_output_contract.model_dump(mode="json") if task_output_contract is not None else {}
            produced_files = list(step_contract.get("produced_files") or [])
            produced_files.extend(task_contract.get("produced_files") or [])
            step_description = "\n".join(
                text
                for text in (
                    desc,
                    str(step.intent or ""),
                    str(step_contract.get("description") or ""),
                    " ".join(str(item) for item in task_contract.get("grounding_requirements") or []),
                )
                if text
            )
            step_expected = "\n".join(
                text
                for text in (
                    expected_output,
                    str(step_contract.get("description") or ""),
                    " ".join(str(item) for item in task_contract.get("required_content") or []),
                    str(step.output_key or ""),
                )
                if text
            )
            output_contract = {
                "artifact_type": step_artifact_type,
                "output_extension": self._extension_for_artifact_type(step_artifact_type),
                "required_content": [step_expected] if step_expected else [],
                "produced_files": produced_files,
                "grounding_requirements": [desc, str(step.intent or "")]
                + list(task_contract.get("grounding_requirements") or []),
            }
            return (
                {
                    "id": task_id,
                    "role": "",
                    "description": step_description,
                    "expected_output": step_expected,
                    "artifact_type": step_artifact_type,
                },
                output_contract,
            )

        def formal_step_output_contract(
            step: ResourceApplicationStep,
            fallback: Any,
        ) -> Dict[str, Any]:
            contract = getattr(step, "expected_output_contract", None)
            if contract is not None and hasattr(contract, "model_dump"):
                return dict(contract.model_dump(mode="json"))
            if not isinstance(fallback, Mapping):
                raise RuntimeError("formal_step_output_contract_fallback_must_be_object")
            return dict(cast(Mapping[str, Any], fallback))

        def formal_invocation_kwargs(
            step: ResourceApplicationStep,
            output_contract: Mapping[str, Any],
            *,
            task_context: str | None = None,
        ) -> Dict[str, Any]:
            if not bool(getattr(self, "_formal_execution_active", False)):
                return {}
            capability_operation_id = str(
                getattr(step, "capability_operation_id", "") or ""
            )
            if not capability_operation_id:
                raise RuntimeError("formal_capability_operation_id_missing")
            acceptance = str(
                output_contract.get("description")
                or output_contract.get("expected_output")
                or "Output must satisfy the sealed output contract."
            )
            mandatory = tuple(task_output_contract.acceptance_criteria) if (
                task_context is not None and task_output_contract is not None
            ) else ()
            return {
                "capability_operation_id": capability_operation_id,
                "resource_application": getattr(
                    step, "resource_application", None
                ),
                "semantic_task_contract": {
                    "intent": step.intent,
                    "satisfied_obligation_ids": list(
                        getattr(step, "satisfied_obligation_ids", ()) or ()
                    ),
                    **({"task_context": task_context} if task_context is not None else {}),
                    **({"acceptance_examples": [
                        probe.model_dump(mode="json")
                        for probe in task_output_contract.acceptance_probes
                    ]} if task_context is not None and task_output_contract is not None
                       and task_output_contract.acceptance_probes else {}),
                },
                "acceptance_requirements": mandatory or (acceptance,),
                "advisory_materials": tuple(
                    {"profile_ref": item, "materialization": "required"}
                    for item in (getattr(step, "advisory_profile_refs", ()) or ())
                ),
            }

        async def execute_controller_session_step(
            *,
            step: ResourceApplicationStep,
            controller_execution_context: ResourceExecutionContext | None,
            provider_model_id: str,
            bound_inputs: Mapping[str, Any],
            bound_outputs: Mapping[str, Any],
            task_context: str,
            agent_card: str | None = None,
        ) -> ExecutionResult | None:
            spec = getattr(step, "controller_session_spec", None)
            if spec is None or not bool(
                getattr(self, "_formal_execution_active", False)
            ):
                return None
            if controller_execution_context is None:
                return ExecutionResult(
                    is_success=False,
                    output_data="",
                    error_log="controller_session_identity_mismatch",
                    cost_metric={
                        "failure_type": "controller_session_identity_mismatch",
                        "failure_layer": "framework",
                    },
                )
            tool_runtime = None
            def project_callable_arguments(callable_spec: Any, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
                try:
                    return self._formal_portable_evidence_bindings(
                        arguments, resource_index[callable_spec.resource_id],
                        self._binding_source_registry(resource_index),
                    )
                except (BindingProtocolError, PathNamespaceError) as exc:
                    raise ControllerToolRuntimeError("controller_tool_dynamic_path_out_of_scope") from exc

            controller_produced_handles: List[ArtifactHandle] = []
            if isinstance(spec, ControllerSessionSpecV2):
                active_resource_runtime = getattr(self, "resource_runtime", None)
                if active_resource_runtime is None:
                    return ExecutionResult(
                        is_success=False,
                        output_data="",
                        error_log="formal_resource_runtime_missing",
                        cost_metric={
                            "failure_type": "formal_resource_runtime_missing",
                            "failure_layer": "framework",
                        },
                    )

                callable_by_id = {
                    item.callable_id: item for item in spec.callable_tools
                }

                def typed_binding_value(value: Any, contract: Mapping[str, Any]) -> Any:
                    kind = normalize_contract_kind(contract)
                    if kind == "list":
                        return list(value) if isinstance(value, (list, tuple)) else [value]
                    if kind == "int":
                        return int(value)
                    if kind == "float":
                        return float(value)
                    if kind == "bool":
                        if isinstance(value, bool):
                            return value
                        normalized = str(value).strip().lower()
                        if normalized not in {"true", "false"}:
                            raise ControllerToolRuntimeError(
                                "controller_tool_fixed_binding_type_mismatch"
                            )
                        return normalized == "true"
                    if kind in {"object", "json"}:
                        if isinstance(value, Mapping):
                            return dict(value)
                        try:
                            parsed = json.loads(str(value))
                        except (TypeError, ValueError, json.JSONDecodeError) as exc:
                            raise ControllerToolRuntimeError(
                                "controller_tool_fixed_binding_type_mismatch"
                            ) from exc
                        if not isinstance(parsed, Mapping):
                            raise ControllerToolRuntimeError(
                                "controller_tool_fixed_binding_type_mismatch"
                            )
                        return dict(parsed)
                    return str(value)

                def resolve_fixed_inputs(
                    callable_spec: Any,
                    intent: ControllerToolCallIntentV1,
                ) -> ResolvedControllerToolInputs:
                    del intent
                    raw_tool = resource_index.get(callable_spec.resource_id)
                    if not isinstance(raw_tool, Mapping):
                        raise ControllerToolRuntimeError(
                            "controller_tool_resource_manifest_missing"
                        )
                    contracts = {
                        str(item.get("name") or ""): item
                        for item in callable_spec.operation_input_contract
                    }
                    source_registry = self._binding_source_registry(resource_index)
                    fixed_values: Dict[str, Any] = {}
                    fixed_source_ids: List[str] = []
                    for name, source in callable_spec.fixed_input_bindings.items():
                        contract = contracts.get(name)
                        if not isinstance(contract, Mapping):
                            raise ControllerToolRuntimeError(
                                "controller_tool_fixed_binding_contract_missing"
                            )
                        try:
                            resolved = resolve_binding(
                                source,
                                contract,
                                source_registry,
                                step_outputs,
                                path_mapper=self._to_tool_binding_value,
                            )
                            typed = typed_binding_value(resolved, contract)
                            fixed_values[name] = typed
                            parsed_source = parse_binding_source(source)
                            source_id = ""
                            if parsed_source.variant == "artifact_handle":
                                ok, failure_code, _, handle = self.resolve_artifact_handle(
                                    str(parsed_source.value)
                                )
                                if not ok or handle is None:
                                    raise ControllerToolRuntimeError(
                                        failure_code
                                        or "formal_authorized_material_missing"
                                    )
                                source_id = str(handle.handle_id)
                            elif parsed_source.variant == "resource":
                                source_id = str(parsed_source.value)
                            elif parsed_source.variant == "step_output":
                                for key in (
                                    parsed_source.output_key,
                                    parsed_source.from_step,
                                ):
                                    if key is not None and str(key) in step_source_ids:
                                        source_id = step_source_ids[str(key)]
                                        break
                                if not source_id:
                                    raise ControllerToolRuntimeError(
                                        "controller_tool_fixed_binding_provenance_missing"
                                    )
                            if source_id and source_id not in fixed_source_ids:
                                fixed_source_ids.append(source_id)
                        except ControllerToolRuntimeError:
                            raise
                        except (BindingProtocolError, BindingFrameworkError) as exc:
                            raise ControllerToolRuntimeError(exc.code) from exc
                        except (TypeError, ValueError) as exc:
                            raise ControllerToolRuntimeError(
                                "controller_tool_fixed_binding_type_mismatch"
                            ) from exc

                    try:
                        fixed_values = self._formal_portable_evidence_bindings(
                            fixed_values, raw_tool, source_registry,
                        )
                    except (BindingProtocolError, PathNamespaceError) as exc:
                        raise ControllerToolRuntimeError(
                            getattr(exc, "code", "controller_tool_fixed_path_out_of_scope")
                        ) from exc

                    source_ids = tuple(fixed_source_ids)
                    materials: List[MaterialDescriptorV1] = []
                    material_content: Dict[str, str] = {}
                    upstream_handles: List[ArtifactHandle] = []
                    for source_id in source_ids:
                        if not str(source_id).startswith("artifact:"):
                            continue
                        ok, failure_code, _, handle = self.resolve_artifact_handle(
                            str(source_id)
                        )
                        if not ok or handle is None:
                            raise ControllerToolRuntimeError(
                                failure_code or "formal_authorized_material_missing"
                            )
                        descriptor, content = self._formal_material_descriptor(
                            str(source_id), handle
                        )
                        materials.append(descriptor)
                        upstream_handles.append(handle)
                        if content is not None:
                            material_content[str(source_id)] = content
                    return ResolvedControllerToolInputs(
                        values=fixed_values,
                        provenance_source_ids=source_ids,
                        authorized_materials=tuple(materials),
                        authorized_material_content=material_content,
                        upstream_artifact_handles=tuple(upstream_handles),
                    )

                async def build_dispatch_context(
                    callable_spec: Any,
                    intent: ControllerToolCallIntentV1,
                    complete_inputs: Mapping[str, Any],
                    fixed: ResolvedControllerToolInputs,
                ) -> ControllerToolDispatchContext:
                    if callable_by_id.get(callable_spec.callable_id) != callable_spec:
                        raise ControllerToolRuntimeError(
                            "controller_tool_call_not_authorized"
                        )
                    tool_ref = self._find_ref(
                        callable_spec.resource_id,
                        selected,
                        resource_index,
                    )
                    if tool_ref is None or tool_ref.resource_type != ManifestType.TOOL:
                        raise ControllerToolRuntimeError(
                            "controller_tool_call_not_authorized"
                        )
                    raw_tool = resource_index.get(callable_spec.resource_id)
                    if not isinstance(raw_tool, Mapping):
                        raise ControllerToolRuntimeError(
                            "controller_tool_resource_manifest_missing"
                        )
                    try:
                        definition = ResourceDefinition.from_manifest(raw_tool)
                        entrypoint = definition.entrypoint(callable_spec.entrypoint_id)
                    except (ResourceManifestError, ResourceCallValidationError, ValueError) as exc:
                        raise ControllerToolRuntimeError(
                            "controller_tool_resource_definition_invalid"
                        ) from exc

                    dependency = self.runtime_readiness_checker.dependency_result(
                        tool_ref, resource_index
                    )
                    if dependency.is_blocked:
                        failure = self._dependency_failure_contract(dependency)
                        raise ControllerToolRuntimeError(
                            str(failure["failure_type"]),
                            responsibility=str(failure["responsibility"]),
                        )
                    runtime_requirements = dict(raw_tool.get("runtime_requirements") or {})
                    network_required = requires_execution_network(runtime_requirements, callable_spec)
                    runtime_handle = None
                    if not uses_unscoped_host_python(
                        dependency.runtime_profile, getattr(self, "_active_sandbox_scope", None)
                    ):
                        runtime_handle, _, preparation_failure = await self._prepare_step_runtime(
                            task_id=task_id,
                            step_id=(
                                f"{step.step_id}:controller_tool:"
                                f"{intent.provider_tool_call_id}"
                            ),
                            raw_manifest=raw_tool,
                            execution_network_required=network_required,
                            phase="manifest",
                        )
                        if preparation_failure is not None:
                            raise ControllerToolRuntimeError(
                                str(preparation_failure["failure_type"]),
                                responsibility=str(
                                    preparation_failure["failure_layer"]
                                ),
                            )
                    portable_bindings = self._formal_portable_evidence_bindings(
                        complete_inputs,
                        raw_tool,
                        self._binding_source_registry(resource_index),
                    )
                    ok, failure_code, _, command, args = (
                        self._build_tool_invocation_from_bindings(
                            tool_ref,
                            resource_index,
                            portable_bindings,
                            formal_resource_runtime=True,
                            formal_entrypoint_id=callable_spec.entrypoint_id,
                        )
                    )
                    if not ok:
                        raise ControllerToolRuntimeError(failure_code)
                    try:
                        timeout_seconds = current_tool_timeout(
                            runtime_requirements.get("timeout_seconds")
                        )
                    except (TypeError, ValueError) as exc:
                        raise ControllerToolRuntimeError(
                            "manifest_execution_timeout_invalid"
                        ) from exc
                    declared_tool_env = tuple(
                        str(name).strip()
                        for name in (runtime_requirements.get("env_vars") or [])
                        if str(name).strip()
                    )
                    prepared = PreparedToolDispatch(
                        subtask_description=spec.task_instruction,
                        context_data="",
                        dispatch_locator=entrypoint.dispatch,
                        command=command,
                        args=tuple(args),
                        runtime_environment=runtime_handle,
                        network_required=network_required,
                        sandbox_scope=(
                            getattr(self, "_active_sandbox_scope", {}) or None
                        ),
                        runtime_profile=dependency.runtime_profile,
                        runtime_kind=str(
                            (raw_tool.get("execution") or {}).get("runtime")
                            or "unknown"
                        ),
                        project_root=self.project_root,
                        timeout_sec=timeout_seconds,
                        extra_env=load_project_tool_environment(
                            self.project_root, declared_tool_env,
                        ),
                        allowed_runtime_environment_names=(
                            manifest_tool_environment_allowlist(declared_tool_env)
                        ),
                        network_policy_mode=str(
                            getattr(self, "network_policy_mode", "disabled")
                        ),
                        execution_substrate_mode=self.execution_substrate_mode,
                    )
                    provider = ToolExecutionProvider(
                        prepared, execution_substrate=self.execution_substrate
                    )
                    call_execution_context = controller_execution_context.model_copy(
                        update={
                            "step_id": (
                                f"{step.step_id}:controller_tool:"
                                f"{intent.provider_tool_call_id}"
                            ),
                            "parent_operation_id": (
                                f"controller:{intent.session_id}:{intent.turn_id}"
                            ),
                        }
                    )
                    return ControllerToolDispatchContext(
                        resource_definition=definition,
                        execution_context=call_execution_context,
                        execution_world=provider.execution_world,
                        provider=provider,
                        resolved_bindings=portable_bindings,
                        semantic_task_contract={
                            "intent": "Execute the sealed Controller callable Tool action.",
                            "controller_step_id": step.step_id,
                            "tool_call_intent_sha256": intent.intent_sha256,
                        },
                        acceptance_requirements=(
                            str(
                                callable_spec.controller_result_target_contract.get(
                                    "description"
                                )
                                or "Return the sealed Controller Tool result contract."
                            ),
                        ),
                        authorized_materials=fixed.authorized_materials,
                        authorized_material_content=fixed.authorized_material_content,
                        upstream_artifact_handles=fixed.upstream_artifact_handles,
                        provenance_source_ids=fixed.provenance_source_ids,
                        dag_edge_contract_sha256s=tuple(
                            getattr(step, "consumed_edge_contract_sha256s", ()) or ()
                        ),
                    )

                def register_controller_tool_artifacts(result: ResourceCallResult) -> None:
                    self._register_controller_tool_artifacts(
                        task_id, step, result, controller_produced_handles,
                    )

                tool_runtime = ControllerToolInvocationGateway(
                    callable_tools=spec.callable_tools,
                    resource_runtime=active_resource_runtime,
                    output_realizer=self.output_realizer,
                    fixed_binding_resolver=resolve_fixed_inputs,
                    dispatch_context_factory=build_dispatch_context,
                    execution_ledger=self.execution_ledger,
                    successful_result_observer=register_controller_tool_artifacts,
                )
            skill_bundle = None
            try:
                skill_bundle = build_skill_bundle(
                    plan=plan, consumer=step, resource_index=resource_index,
                    loaded=verified_skill_loads, outputs=step_outputs, results=step_results,
                    source_ids=step_source_ids,
                    plan_sha256=controller_execution_context.plan_sha256,
                )
                if skill_bundle is not None:
                    register_request_source(
                        step, source_id=f"controller-skill:{skill_bundle.bundle_sha256}",
                        origin="current_run_step_output", material=skill_bundle.model_dump(mode="json"),
                        parent_source_ids=tuple(b.producer_source_id for b in skill_bundle.bindings),
                        producer={"step_id": step.step_id, "skill_bundle_sha256": skill_bundle.bundle_sha256},
                    )
            except (ControllerSkillError, ValueError) as exc:
                code = getattr(exc, "code", "controller_skill_binding_invalid")
                failure_result = self._pre_dispatch_failure_result(
                    code, code, failure_stage="controller_skill_binding",
                    task_id=task_id, step_id=step.step_id,
                    failure_layer="framework_implementation",
                )
                if skill_bundle is not None:
                    failure_result.cost_metric["controller_skill_context"] = skill_bundle.metadata()
                return failure_result
            controller_materials: List[MaterialDescriptorV1] = []
            controller_handles: List[ArtifactHandle] = []
            for source_id in (
                getattr(step, "consumed_context_source_ids", ()) or ()
            ):
                normalized_source_id = str(source_id).strip()
                if not normalized_source_id.startswith("artifact:"):
                    continue
                handle = self._resolve_context_source_handle(
                    step=step, source_id=normalized_source_id
                )
                descriptor, _ = self._formal_material_descriptor(
                    normalized_source_id, handle
                )
                controller_materials.append(descriptor)
                controller_handles.append(handle)
            controller_media_parts: list[dict[str, Any]] = []
            controller_media_audit: list[dict[str, Any]] = []
            backing_model_resource_id = str(spec.backing_model_resource_id or "")
            backing_model_manifest = resource_index.get(backing_model_resource_id, {})
            if controller_materials:
                try:
                    controller_handles = await materialize_task_media_handles(controller_handles,
                        execution_substrate=self.execution_substrate,
                        cache_dir=Path(self.artifact_dir) / "media_snapshots")
                    (
                        controller_media_parts,
                        controller_media_audit,
                    ) = build_model_media_parts_from_materials(
                        authorized_materials=controller_materials,
                        upstream_artifact_handles=controller_handles,
                        model_manifest=(
                            backing_model_manifest
                            if isinstance(backing_model_manifest, Mapping)
                            else {}
                        ),
                        model_resource_id=backing_model_resource_id,
                        provider_model_id=provider_model_id,
                        project_root=self.project_root,
                        endpoint_identity_sha256=(
                            self.async_model_transport.endpoint_identity.identity_sha256
                        ),
                    )
                except ModelMediaProjectionError as exc:
                    return ExecutionResult(
                        is_success=False,
                        output_data="",
                        error_log=exc.code,
                        cost_metric={
                            "failure_type": exc.code,
                            "failure_layer": "framework",
                            "failure": {
                                "responsibility": "framework",
                                "failure_stage": "model_media_projection",
                                "failure_code": exc.code,
                                "retryable": False,
                                "response_received": False,
                            },
                        },
                    )
            try:
                dependency_handles = self._dependency_media_handles(task_id, step, plan)
                dependency_parts, dependency_audit = await build_controller_observation_media_parts(
                    dependency_handles, execution_substrate=self.execution_substrate,
                    cache_dir=Path(self.artifact_dir) / "media_snapshots",
                    model_manifest=backing_model_manifest, model_resource_id=backing_model_resource_id,
                    provider_model_id=provider_model_id, project_root=self.project_root,
                    endpoint_identity_sha256=self.async_model_transport.endpoint_identity.identity_sha256)
                known_media = {item.get("content_sha256") for item in controller_media_audit}
                for part, audit in zip(dependency_parts, dependency_audit):
                    if audit.get("content_sha256") not in known_media:
                        controller_media_parts.append(part)
                        controller_media_audit.append(audit)
                        known_media.add(audit.get("content_sha256"))
                if dependency_audit:
                    self._append_trace("dependency_model_media_prepared", {
                        "subtask_id": task_id, "step_id": step.step_id,
                        "model_resource_id": backing_model_resource_id,
                        "model_media_projection": dependency_audit,
                    })
            except ModelMediaProjectionError as exc:
                return self._pre_dispatch_failure_result(
                    exc.code, exc.code, failure_stage="model_media_projection",
                    task_id=task_id, step_id=step.step_id, failure_layer="framework_implementation")

            async def read_controller_media():
                try:
                    return await build_controller_observation_media_parts(controller_produced_handles,
                        execution_substrate=self.execution_substrate,
                        cache_dir=Path(self.artifact_dir) / "media_snapshots",
                        model_manifest=backing_model_manifest,
                        model_resource_id=backing_model_resource_id, provider_model_id=provider_model_id,
                        project_root=self.project_root,
                        endpoint_identity_sha256=self.async_model_transport.endpoint_identity.identity_sha256)
                except ModelMediaProjectionError as exc:
                    raise ControllerSessionError(exc.code) from exc

            turn_executor = ControllerTurnExecutor(
                transport=self.async_model_transport,
                cost_ledger=self.cost_ledger,
                max_retries=self.execution_max_retries,
                max_tokens=self.execution_max_tokens,
                temperature=self.execution_temperature,
            )
            runner = ControllerSessionRunner(
                turn_executor=turn_executor,
                policy=load_controller_session_policy(),
                cost_ledger=self.cost_ledger,
                execution_ledger=self.execution_ledger,
                tool_runtime=tool_runtime,
            )
            is_final_controller_step = bool(
                plan and step.output_key == plan.final_output_from
            )
            is_final_content_source = bool(
                plan
                and not is_final_controller_step
                and _is_direct_final_write_source(
                    plan=plan,
                    producer_step=step,
                )
            )
            intermediate_contract = dict(spec.expected_output_contract)
            if is_final_content_source and task_output_contract is not None:
                delivery_contract = _validated_delivery_output_contract(plan)
                if delivery_contract.artifact_type == task_output_contract.artifact_type.value:
                    intermediate_contract = delivery_contract.model_dump(mode="json")
            delivery_requirements = controller_step_delivery_requirements(
                expected_output_contract=intermediate_contract,
                task_output_contract=task_output_contract,
                is_final=is_final_controller_step,
                is_final_content_source=is_final_content_source,
            )
            async def read_materialized_output() -> str | None:
                return await self._read_materialized_controller_output(
                    output_contract=task_output_contract,
                    delivery_contract=delivery_requirements["authoritative_final_output_contract"],
                )
            async def read_materialized_delivery_state() -> dict[str, Any] | None:
                return await self._read_materialized_controller_delivery_state(
                    output_contract=task_output_contract,
                )
            step_max_tokens = controller_generation_token_cap(
                configured_max_tokens=self.execution_max_tokens,
                delivery_requirements=delivery_requirements,
                tool_enabled=bool(getattr(spec, "callable_tools", ())),
            )
            required_kinds = {
                normalize_capability_operation(kind)
                for kind in required_operation_kinds if str(kind).strip()
            }
            prior_successful_operations = {
                operation_id
                for trace in step_trace if trace.get("status") == "success"
                for operation_id in (
                    [trace["capability_operation_id"]]
                    if trace.get("resource_type") == "Tool"
                    and trace.get("capability_operation_id") else
                    trace.get("successful_tool_operation_ids", ())
                )
            }
            prior_successful_kinds = {
                normalize_capability_operation(operation_id.rsplit("::", 1)[-1])
                for operation_id in prior_successful_operations
            }
            required_callables_by_kind: Dict[str, List[Any]] = {}
            for item in getattr(spec, "callable_tools", ()):
                kind = normalize_capability_operation(
                    item.capability_operation_id.rsplit("::", 1)[-1]
                )
                if kind in required_kinds - prior_successful_kinds:
                    required_callables_by_kind.setdefault(kind, []).append(item)
            required_callable_operations = [
                {
                    "operation_kind": kind,
                    "capability_operation_ids": [
                        item.capability_operation_id for item in items
                    ],
                    "function_names": [item.provider_tool_name for item in items],
                }
                for kind, items in sorted(required_callables_by_kind.items())
            ]
            if required_workspace_effect:
                from .workspace_effects import required_controller_workspace_operation

                workspace_operation = required_controller_workspace_operation(
                    plan=plan,
                    controller_step=step,
                    step_trace=step_trace[:-1],
                    resource_index=resource_index,
                )
                if workspace_operation is not None:
                    required_callable_operations.append(workspace_operation)
            file_delivery_operation = required_controller_file_delivery_operation(
                callable_tools=getattr(spec, "callable_tools", ()),
                delivery_scope=str(
                    delivery_requirements.get("delivery_scope") or ""
                ),
                mandatory_output_files=tuple(
                    delivery_requirements.get("mandatory_output_files") or ()
                ),
                prior_successful_operation_ids=tuple(prior_successful_operations),
            )
            if file_delivery_operation is not None:
                required_callable_operations.append(file_delivery_operation)
            try:
                session_result = await runner.run(
                    run_id=controller_execution_context.run_id,
                    spec=spec,
                    resolved_inputs=dict(bound_inputs),
                    resolved_context=self._resolve_controller_context(step=step),
                    provenance_identities=provenance_source_ids(
                        bound_outputs,
                        request_step_id=step.step_id,
                    ),
                    format_enforcement=getattr(step, "format_enforcement", None),
                    controller_context={
                        "provider_model_id": provider_model_id,
                        "tool_argument_projector": project_callable_arguments,
                        "tool_working_directory": getattr(self, "_active_sandbox_scope", {}).get("working_directory"),
                        "agent_card": agent_card,
                        "task_context": task_context,
                        "generated_source_contract": _generated_source_contract(plan=plan, producer_step=step),
                        "model_media_parts": controller_media_parts,
                        "model_media_audit": controller_media_audit,
                        **delivery_requirements,
                        "required_successful_tool_operations": required_callable_operations,
                        **({
                            "stateful_execution_policy": {
                                "phase_scope": "each_execution_iteration",
                                "phase_order": [
                                    "inspect_relevant_state",
                                    "apply_next_task_action",
                                    "verify_observed_result",
                                ],
                                "preserve_unconsumed_required_sources": True,
                                "final_delivery_requires_all_criteria": True,
                                "evidence_must_describe_current_required_state": True,
                                "optional_diagnostics_are_not_delivery_requirements": True,
                            }
                        } if required_workspace_effect else {}),
                        "max_retries": self.execution_max_retries,
                        "max_tokens": step_max_tokens,
                        "temperature": self.execution_temperature,
                        "model_payload_guard": request_guard_for_step(
                            step, bound_outputs
                        ),
                    },
                    **({"media_part_reader": read_controller_media} if tool_runtime is not None else {}),
                    **({"materialized_output_reader": read_materialized_output}
                       if (is_final_controller_step or is_final_content_source)
                       and self.execution_substrate is not None
                       and "authoritative_final_output_contract" in delivery_requirements else {}),
                    **({"materialized_delivery_state_reader": read_materialized_delivery_state}
                       if is_final_controller_step and self.execution_substrate is not None else {}),
                    **({"input_source_reader": self._read_controller_input_source}
                       if tool_runtime is not None and self.execution_substrate is not None else {}),
                    **({"skill_bundle": skill_bundle} if skill_bundle is not None else {}),
                )
            except ControllerSessionError as exc:
                failure_code = str(exc)
                failure_result = self._pre_dispatch_failure_result(
                    failure_code, failure_code, failure_stage="controller_session_preparation",
                    task_id=task_id, step_id=step.step_id,
                    failure_layer="framework_implementation",
                )
                failure_result.cost_metric["controller_session_spec_sha256"] = spec.spec_sha256
                if skill_bundle is not None:
                    failure_result.cost_metric["controller_skill_context"] = skill_bundle.metadata()
                return failure_result
            projected = project_controller_session_execution_result(session_result)
            if isinstance(session_result.summary, ControllerSessionSummaryV2):
                step_trace[-1]["successful_tool_operation_ids"] = list(
                    session_result.summary.successful_tool_operation_ids
                )
            if (
                projected.is_success
                and self.execution_substrate is not None
                and step.output_key == plan.final_output_from
                and controller_produced_handles
            ):
                await self._register_external_final_text_artifact(
                    task_id, step, controller_produced_handles,
                    output_contract=task_output_contract,
                )
            if skill_bundle is not None:
                if str(session_result.failure_code or "").startswith("controller_skill_"):
                    projected.cost_metric["failure_layer"] = "framework"
                projected.cost_metric["controller_skill_context"] = {
                    **skill_bundle.metadata(),
                    "turn_references": [{
                        "turn_id": turn.turn_id, "request_sha256": turn.request_sha256,
                        "status": turn.status, "transport_status": turn.transport_audit.get("status"),
                        "response_received": turn.transport_audit.get("response_received", False),
                        "model_accounting_reference": turn.model_accounting_reference,
                    } for turn in session_result.turns],
                }
            _apply_direct_final_python_fence_conversion(
                projected,
                plan=plan,
                producer_step=step,
                task_output_contract=task_output_contract,
            )
            return projected

        for step in plan.steps:
            ref = self._find_ref(step.resource_id, selected, resource_index)
            if ref is None:
                return ExecutionResult(
                    is_success=False,
                    output_data="",
                    error_log=f"policy_hallucinated_resource: {step.resource_id}",
                    cost_metric={"failure_type": "policy_hallucinated_resource"},
                )

            raw = resource_index.get(ref.resource_id, {})
            if resource_execution_context is not None:
                if step.step_type is None or step.operation_kind is None:
                    return ExecutionResult(
                        is_success=False,
                        output_data="",
                        error_log="formal_resource_step_semantics_missing",
                        cost_metric={
                            "failure_type": "policy_invalid_plan",
                            "failure_layer": "research",
                        },
                    )
                step_type = str(step.step_type)
                operation_kind = step.operation_kind
            else:
                step_type = self._infer_step_type(step, ref)
                step.step_type = step_type
                operation_kind = self._infer_operation_kind(step, ref, None, plan)
                step.operation_kind = operation_kind
            step_trace.append(
                {
                    "step_id": step.step_id,
                    "step_type": step_type,
                    "operation_kind": operation_kind.value,
                    "resource_id": ref.resource_id,
                    "capability_operation_id": str(
                        getattr(step, "capability_operation_id", "") or ""
                    ),
                    "resource_type": ref.resource_type.value,
                    "output_key": step.output_key,
                    "intent": step.intent,
                    "status": "started",
                }
            )
            checkpoint = resume_checkpoint_map.get(step.step_id)
            if checkpoint is not None:
                reused_result = resume_result_map[step.step_id]
                output = reused_result.output_data
                step_outputs[step.output_key] = output
                step_outputs[step.step_id] = output
                step_results[step.output_key] = reused_result
                register_checkpoint_output_source(step, checkpoint, output)
                if resource_execution_context is None:
                    raise RuntimeError("checkpoint_reuse_requires_formal_execution_context")
                self.execution_ledger.record_reused_call(
                    original_call_id=checkpoint.resource_call_id,
                    resource_id=checkpoint.resource_id,
                    entrypoint_id=checkpoint.entrypoint_id or "invoke",
                    graph_revision=resource_execution_context.graph_revision,
                    subtask_id=resource_execution_context.subtask_id,
                    subtask_revision=resource_execution_context.subtask_revision,
                    step_id=step.step_id,
                    plan_sha256=resource_execution_context.plan_sha256,
                    candidate_pool_sha256=(
                        resource_execution_context.candidate_pool_sha256
                    ),
                    checkpoint_sha256=checkpoint.checkpoint_sha256,
                    result_sha256=checkpoint.result_sha256,
                )
                step_trace[-1].update(
                    {
                        "status": "reused",
                        "checkpoint_sha256": checkpoint.checkpoint_sha256,
                        "resource_call_reference": {
                            "call_id": checkpoint.resource_call_id,
                            "result_sha256": checkpoint.result_sha256,
                            "started_event_id": checkpoint.started_event_id,
                            "terminal_event_id": checkpoint.terminal_event_id,
                        },
                        "side_effect_evidence": checkpoint.side_effect_evidence.model_dump(
                            mode="json"
                        ),
                    }
                )
                terminal_progress.step_output(task_id, step, output, reused=True)
                reused_summary = reused_result.cost_metric.get("controller_session_summary")
                if isinstance(reused_summary, Mapping):
                    step_trace[-1]["successful_tool_operation_ids"] = list(
                        reused_summary.get("successful_tool_operation_ids") or ()
                    )
                continue
            logger.bind(terminal_task=task_id).info(
                "[ResourcePlan] Executing {} with {} ({}) | step_type={} | intent={}",
                step.step_id,
                ref.resource_id,
                ref.resource_type.value,
                step_type,
                step.intent,
            )
            if (
                resource_execution_context is not None
                and bool(getattr(self, "_formal_execution_active", False))
                and (
                    ref.resource_type == ManifestType.TOOL
                    or (
                        isinstance(
                            getattr(step, "controller_session_spec", None),
                            ControllerSessionSpecV2,
                        )
                        and bool(step.controller_session_spec.callable_tools)
                    )
                )
            ):
                step_scope = self._formal_step_sandbox_scope(
                    step=step,
                    execution_context=resource_execution_context,
                )
                self._active_sandbox_scope = step_scope
                self._active_runtime_path_map = RuntimePathMap.from_scope(step_scope)
            bound_inputs, bound_outputs = self._bound_step_inputs(
                step,
                resource_index,
                step_outputs,
            )
            try:
                declared_context = self._formal_declared_context(
                    step=step,
                    base_context=context_data,
                    original_query=formal_original_query,
                )
                model_task_context = (
                    self._formal_declared_context(
                        step=step,
                        base_context="",
                        original_query=formal_original_query,
                        task_expected_output=expected_output,
                        task_output_contract=task_output_contract,
                        include_task_contract=True,
                        include_context_sources=False,
                    )
                    if ref.resource_type in {ManifestType.MODEL, ManifestType.AGENT}
                    else ""
                )
                if ref.resource_type in {ManifestType.MODEL, ManifestType.AGENT}:
                    model_task_context = _execution_lifecycle_context(
                        model_task_context, plan=plan, step=step,
                    )
            except RuntimeError as exc:
                code = str(exc)
                if not code.startswith(("formal_context_", "controller_context_", "artifact_handle_", "formal_complete_material_")):
                    raise
                return self._pre_dispatch_failure_result(
                    code, code, failure_stage="controller_context_preparation",
                    task_id=task_id, step_id=step.step_id, step_trace=step_trace,
                    failure_layer="framework_implementation",
                )
            execution_context = self._step_execution_context(
                declared_context,
                bound_inputs,
            )
            step_resource_context = (
                resource_execution_context.model_copy(
                    update={
                        "step_id": step.step_id,
                        "sandbox_scope_sha256": sandbox_scope_sha256(
                            getattr(self, "_active_sandbox_scope", {}),
                            project_root=self.project_root,
                        ),
                    }
                )
                if resource_execution_context is not None
                else None
            )
            if bound_inputs:
                step_trace[-1]["bound_input_names"] = sorted(bound_inputs)
            if bool(getattr(self, "_formal_execution_active", False)):
                step_trace[-1]["consumed_context_source_ids"] = list(
                    getattr(step, "consumed_context_source_ids", ()) or ()
                )
                step_trace[-1]["consumed_edge_contract_sha256s"] = list(
                    getattr(step, "consumed_edge_contract_sha256s", ()) or ()
                )

            if step_type in {"read_resource", "apply_skill_hint", "context_resource"} and ref.resource_type in (ManifestType.RESOURCE, ManifestType.SKILL):
                loaded_skill = None
                async def read_context_resource(
                    _request: ResourceCallRequest | None = None,
                ) -> ExecutionResult:
                    nonlocal loaded_skill
                    try:
                        requested_references = (
                            self.skill_package_loader.normalize_requested_references(
                                step.input_bindings.get("skill_references")
                            )
                            if ref.resource_type == ManifestType.SKILL
                            else []
                        )
                        if ref.resource_type == ManifestType.SKILL:
                            loaded_skill = self.skill_package_loader.load(
                                resource_index.get(ref.resource_id, {}),
                                requested_references=requested_references,
                                **({"verify_integrity": True} if step.step_id in skill_producer_ids else {}),
                            )
                            resource_output = loaded_skill.content
                        else:
                            resource_output = self._read_resource_snippet(
                                ref,
                                resource_index,
                            )
                        return ExecutionResult(
                            is_success=True,
                            output_data=resource_output,
                            cost_metric={
                                "resource_id": ref.resource_id,
                                "resource_type": ref.resource_type.value,
                                "latency_ms": 0,
                                "attempt_count": 1,
                            },
                        )
                    except SkillPackageError as exc:
                        return ExecutionResult(
                            is_success=False,
                            output_data="",
                            error_log=exc.code,
                            cost_metric={
                                "resource_id": ref.resource_id,
                                "resource_type": ref.resource_type.value,
                                "failure_type": exc.code,
                                "failure_layer": "research",
                                "failure": {
                                    "responsibility": "research",
                                    "failure_stage": "skill_package",
                                    "failure_code": exc.code,
                                    "retryable": False,
                                    "response_received": False,
                                    "exception_type": type(exc).__name__,
                                },
                            },
                        )

                context_result = await execute_resource_with_events(
                    ref=ref,
                    raw_manifest=raw,
                    execution_context=step_resource_context,
                    resolved_bindings=bound_inputs,
                    provenance_source_ids=provenance_source_ids(
                        bound_outputs,
                        request_step_id=step.step_id,
                    ),
                    runtime_kind=str(
                        (raw.get("execution") or {}).get("runtime")
                        or ref.resource_type.value.lower()
                    ),
                    network_required=False,
                    provider=read_context_resource,
                    output_contract=formal_step_output_contract(
                        step,
                        cast(Mapping[str, Any], raw).get("output_contract") or {},
                    ),
                    dag_edge_contract_sha256s=tuple(
                        getattr(step, "consumed_edge_contract_sha256s", ()) or ()
                    ),
                    advisory_profile_refs=tuple(
                        getattr(step, "advisory_profile_refs", ()) or ()
                    ),
                    **formal_invocation_kwargs(
                        step,
                        formal_step_output_contract(
                            step,
                            cast(Mapping[str, Any], raw).get("output_contract") or {},
                        ),
                    ),
                )
                if not context_result.is_success:
                    step_trace[-1]["status"] = "failed"
                    step_trace[-1]["failure_type"] = str(
                        context_result.cost_metric.get("failure_type")
                        or "resource_context_read_failed"
                    )
                    step_trace[-1]["failure_reason"] = context_result.error_log
                    context_result.cost_metric["application_step_trace"] = step_trace
                    return context_result
                output = context_result.output_data
                step_outputs[step.output_key] = output
                step_outputs[step.step_id] = output
                register_step_output_source(
                    step,
                    output,
                    bound_outputs,
                    executor_kind=ref.resource_type.value,
                )
                step_results[step.output_key] = context_result
                if loaded_skill is not None and step.step_id in skill_producer_ids:
                    verified_skill_loads[step.step_id] = loaded_skill
                logger.info(
                    "[ResourcePlan] {} produced context output {} ({} chars)",
                    ref.resource_id,
                    step.output_key,
                    len(output),
                )
                step_trace[-1]["status"] = "success"
                step_trace[-1]["output_chars"] = len(output)
                terminal_progress.step_output(task_id, step, output)
                if loaded_skill is not None:
                    step_trace[-1]["skill_package"] = {
                        "content_hash": loaded_skill.content_hash,
                        "source_commit": loaded_skill.source_commit,
                        "main_bytes": loaded_skill.main_bytes,
                        "total_bytes": loaded_skill.total_bytes,
                        "loaded_references": loaded_skill.loaded_references,
                        "implicit_script_execution": False,
                    }
                record_step_metrics(context_result)
                continue

            if ref.resource_type == ManifestType.TOOL:
                dependency_result = self.runtime_readiness_checker.dependency_result(ref, resource_index)
                step_trace[-1]["dependency_check"] = dependency_result.model_dump()
                declared_package_names = self._manifest_python_package_names(raw)
                runtime_allowed_packages.update(declared_package_names)
                if dependency_result.is_blocked:
                    dependency_failure = self._dependency_failure_contract(
                        dependency_result
                    )
                    dependency_failure_type = dependency_failure["failure_type"]
                    step_trace[-1]["status"] = "failed"
                    step_trace[-1]["failure_type"] = dependency_failure_type
                    step_trace[-1]["failure_responsibility"] = dependency_failure[
                        "responsibility"
                    ]
                    step_trace[-1]["failure_reason"] = dependency_result.reason
                    return ExecutionResult(
                        is_success=False,
                        output_data="",
                        error_log=dependency_result.reason,
                        cost_metric={
                            "failure_type": dependency_failure_type,
                            "failure_layer": dependency_failure["responsibility"],
                            "failure": dependency_failure,
                            "dependency_check": dependency_result.model_dump(),
                            "application_step_trace": step_trace,
                        },
                    )
                runtime_handle = None
                preparation_event_ids: List[str] = []
                runtime_requirements = dict(raw.get("runtime_requirements") or {})
                execution_network_required = requires_execution_network(runtime_requirements, step)
                if not uses_unscoped_host_python(
                    dependency_result.runtime_profile, getattr(self, "_active_sandbox_scope", None)
                ):
                    runtime_handle, prep_event_id, prep_failure = await self._prepare_step_runtime(
                        task_id=task_id,
                        step_id=step.step_id,
                        raw_manifest=raw,
                        execution_network_required=execution_network_required,
                        phase="manifest",
                    )
                    preparation_event_ids.append(prep_event_id)
                    if prep_failure is not None:
                        step_trace[-1]["status"] = "failed"
                        step_trace[-1]["failure_type"] = prep_failure["failure_type"]
                        step_trace[-1]["failure_layer"] = prep_failure["failure_layer"]
                        step_trace[-1]["failure_reason"] = prep_failure["failure_reason"]
                        step_trace[-1]["runtime_preparation_event_ids"] = preparation_event_ids
                        return self._runtime_preparation_failure_result(
                            prep_failure,
                            step_trace,
                        )
                    runtime_payload = self._runtime_record_payload(runtime_handle)
                    step_trace[-1]["runtime_environment_hash"] = runtime_payload.get(
                        "environment_hash"
                    )
                    step_trace[-1]["runtime_image_id"] = runtime_payload.get("image_id")
                    step_trace[-1]["runtime_preparation_event_ids"] = preparation_event_ids
                # Artifact dependencies are local to this step.  They must not
                # leak into later steps merely because an earlier runner needed
                # an additional package.
                runtime_provisioned: Set[str] = set()
                if resource_execution_context is not None:
                    if operation_kind in (
                        set(_DIRECT_TOOL_EXECUTION_KINDS)
                        | {
                            OperationKind.EXECUTE_SCRIPT,
                            OperationKind.RUN_TESTS,
                            OperationKind.VALIDATE_ARTIFACT,
                        }
                    ):
                        ok, failure_type, reason, live_bindings = self._bind_step_inputs(
                            step,
                            selected,
                            resource_index,
                            desc,
                            context_data,
                            step_outputs,
                            task_id=task_id,
                        )
                    else:
                        ok = False
                        failure_type = "operation_misuse"
                        reason = (
                            f"Tool step {step.step_id} has no formal execution group for "
                            f"operation_kind={operation_kind.value}."
                        )
                        live_bindings = {}
                elif (
                    operation_kind == OperationKind.EXECUTE_SCRIPT
                    and (
                        self._is_python_script_runner_ref(ref)
                        or step_type == "execute_generated_code"
                    )
                ):
                    ok, failure_type, reason, live_bindings = self._materialize_generated_code(
                        task_id,
                        step,
                        step_outputs,
                        resource_index,
                    )
                elif (
                    operation_kind == OperationKind.RUN_TESTS
                    or (
                        operation_kind == OperationKind.VALIDATE_ARTIFACT
                        and self._is_artifact_validator_ref(ref)
                    )
                ):
                    ok, failure_type, reason, live_bindings = self.pytest_target_resolver.prepare_validation_bindings(
                        task_id,
                        step,
                        selected,
                        resource_index,
                        desc,
                        context_data,
                        step_outputs,
                    )
                elif (
                    operation_kind in _DIRECT_TOOL_EXECUTION_KINDS
                    or operation_kind == OperationKind.VALIDATE_ARTIFACT
                ):
                    ok, failure_type, reason, live_bindings = self._bind_step_inputs(
                        step,
                        selected,
                        resource_index,
                        desc,
                        context_data,
                        step_outputs,
                        task_id=task_id,
                    )
                else:
                    ok = False
                    failure_type = "operation_misuse"
                    reason = (
                        f"Tool step {step.step_id} has no execution group for "
                        f"operation_kind={operation_kind.value}."
                    )
                    live_bindings = {}
                if not ok:
                    step_trace[-1]["status"] = "failed"
                    step_trace[-1]["failure_type"] = failure_type
                    step_trace[-1]["failure_reason"] = reason
                    return self._pre_dispatch_failure_result(
                        failure_type,
                        reason,
                        failure_stage="resource_binding",
                        task_id=task_id,
                        step_id=step.step_id,
                        step_trace=step_trace,
                    )
                bindings = dict(
                    live_bindings or resolved_bindings.get(step.step_id, {})
                )
                provision_hint = bindings.pop("_sgar_provision", "")
                if provision_hint:
                    runtime_provisioned.update(p for p in provision_hint.split(",") if p)
                portable_evidence_bindings = (
                    self._formal_portable_evidence_bindings(
                        bindings,
                        raw,
                        self._binding_source_registry(resource_index),
                    )
                    if resource_execution_context is not None
                    else self._portable_binding_tree(bindings)
                )
                step_trace[-1]["resolved_bindings"] = portable_evidence_bindings
                validation_target_paths: List[str] = []
                validation_import_roots: List[str] = []
                uses_managed_validation_target = bool(
                    resource_execution_context is None
                    and (
                        operation_kind == OperationKind.RUN_TESTS
                        or (
                            operation_kind == OperationKind.VALIDATE_ARTIFACT
                            and self._is_artifact_validator_ref(ref)
                        )
                    )
                )
                if uses_managed_validation_target:
                    target_paths = self._tool_validation_target_paths(bindings)
                    validation_target_paths = list(target_paths)
                    dependency_issues: List[Dict[str, Any]] = []
                    for target_path in target_paths:
                        if target_path.endswith(".py"):
                            validation_import_roots.extend(
                                self._current_run_import_roots_for_python_target(target_path)
                            )
                            dep_ok, missing_deps, dep_scan = self._check_python_artifact_dependencies(
                                source_path=target_path,
                                allowed_packages=sorted(declared_package_names),
                            )
                            dependency_issues.append(dep_scan)
                            if not dep_ok:
                                # Preserve import names here. The explicit
                                # preparer owns the controlled import-to-package
                                # mapping and lock generation.
                                runtime_provisioned.update(missing_deps)
                    if dependency_issues:
                        step_trace[-1]["python_import_scan"] = dependency_issues
                    if validation_import_roots:
                        step_trace[-1]["import_root_sources"] = [
                            self._to_tool_path(path) for path in validation_import_roots
                        ]
                if runtime_provisioned and not uses_unscoped_host_python(dependency_result.runtime_profile, getattr(self, "_active_sandbox_scope", None)):
                    step_trace[-1]["artifact_dependency_candidates"] = sorted(
                        runtime_provisioned
                    )
                    runtime_handle, artifact_event_id, prep_failure = await self._prepare_step_runtime(
                        task_id=task_id,
                        step_id=step.step_id,
                        raw_manifest=raw,
                        artifact_imports=sorted(runtime_provisioned),
                        artifact_source=f"generated_artifact:{task_id}:{step.step_id}",
                        execution_network_required=execution_network_required,
                        phase="artifact",
                    )
                    preparation_event_ids.append(artifact_event_id)
                    step_trace[-1]["runtime_preparation_event_ids"] = preparation_event_ids
                    if prep_failure is not None:
                        step_trace[-1]["status"] = "failed"
                        step_trace[-1]["failure_type"] = prep_failure["failure_type"]
                        step_trace[-1]["failure_layer"] = prep_failure["failure_layer"]
                        step_trace[-1]["failure_reason"] = prep_failure["failure_reason"]
                        return self._runtime_preparation_failure_result(
                            prep_failure,
                            step_trace,
                        )
                    runtime_payload = self._runtime_record_payload(runtime_handle)
                    step_trace[-1]["runtime_environment_hash"] = runtime_payload.get(
                        "environment_hash"
                    )
                    step_trace[-1]["runtime_image_id"] = runtime_payload.get("image_id")
                    runtime_allowed_packages.update(runtime_provisioned)
                if resource_execution_context is not None:
                    formal_entrypoint_id = str(
                        getattr(self, "_active_sealed_entrypoints", {}).get(
                            step.step_id,
                            "invoke",
                        )
                    )
                    ok, failure_type, reason, command, args = self._build_tool_invocation_from_bindings(
                        ref,
                        resource_index,
                        portable_evidence_bindings,
                        formal_resource_runtime=True,
                        formal_entrypoint_id=formal_entrypoint_id,
                    )
                else:
                    ok, failure_type, reason, command, args = self._build_tool_invocation_from_bindings(
                        ref,
                        resource_index,
                        bindings,
                    )
                if not ok:
                    step_trace[-1]["status"] = "failed"
                    step_trace[-1]["failure_type"] = failure_type
                    step_trace[-1]["failure_reason"] = reason
                    return self._pre_dispatch_failure_result(
                        failure_type,
                        reason,
                        failure_stage="resource_invocation",
                        task_id=task_id,
                        step_id=step.step_id,
                        step_trace=step_trace,
                    )
                active_sandbox_scope = getattr(self, "_active_sandbox_scope", {})
                extra_env = self._tool_pythonpath_env(validation_import_roots)
                declared_tool_env = tuple(
                    str(name).strip()
                    for name in (runtime_requirements.get("env_vars") or [])
                    if str(name).strip()
                )
                extra_env.update(
                    load_project_tool_environment(
                        self.project_root,
                        declared_tool_env,
                    )
                )
                if extra_env:
                    step_trace[-1]["pythonpath_roots"] = extra_env.get("PYTHONPATH", "")
                if validation_target_paths:
                    step_trace[-1]["validation_target_paths"] = [
                        self._to_tool_path(path) for path in validation_target_paths
                    ]
                produced_records: List[RuntimeArtifactRecord] = []

                def register_runtime_artifacts(
                    provider_result: ExecutionResult,
                ) -> Sequence[ArtifactHandle]:
                    if not provider_result.is_success:
                        return ()
                    records = self._register_tool_output_artifacts(
                        task_id,
                        step,
                        provider_result.output_data,
                    )
                    declared_type = getattr(
                        step.expected_output_contract,
                        "artifact_type",
                        None,
                    )
                    if hasattr(declared_type, "value"):
                        declared_type = declared_type.value
                    normalized_declared_type = str(declared_type or "").strip().lower()
                    if not any(
                        str(record.artifact_type or "").lower()
                        == normalized_declared_type
                        for record in records
                    ):
                        declared_record = self._register_declared_tool_step_output(
                            task_id,
                            step,
                            provider_result.output_data,
                        )
                        if declared_record is not None:
                            declared_record.metadata["inline_provider_output"] = True
                            records.append(declared_record)
                    produced_records.extend(records)
                    return tuple(
                        self._artifact_handle_for_record(
                            handle_id=(
                                f"{task_id}:{step.step_id}:resource_runtime:"
                                f"{index}"
                            ),
                            kind="tool_output",
                            record=record,
                            producer_task=task_id,
                            producer_step=step.step_id,
                            logical_path=str(
                                record.metadata.get("tool_path")
                                or self._artifact_handle_tool_path(record.path)
                            ),
                        )
                        for index, record in enumerate(records)
                    )

                active_resource_runtime = getattr(self, "resource_runtime", None)
                if active_resource_runtime is not None:
                    if resource_execution_context is None:
                        raise RuntimeError("formal_resource_execution_context_missing")
                    try:
                        definition = ResourceDefinition.from_manifest(raw)
                        entrypoint = definition.entrypoint(formal_entrypoint_id)
                    except ResourceCallValidationError:
                        return ExecutionResult(
                            is_success=False,
                            output_data="",
                            error_log="unknown_resource_entrypoint",
                            cost_metric={
                                "failure_type": "unknown_resource_entrypoint",
                                "failure_layer": "research",
                                "application_step_trace": step_trace,
                            },
                        )
                    except (ResourceManifestError, ValueError) as exc:
                        return ExecutionResult(
                            is_success=False,
                            output_data="",
                            error_log="resource_manifest_invalid",
                            cost_metric={
                                "failure_type": "resource_manifest_invalid",
                                "failure_layer": "framework",
                                "failure": {
                                    "responsibility": "framework",
                                    "failure_stage": "resource_definition",
                                    "retryable": False,
                                    "response_received": False,
                                    "exception_type": type(exc).__name__,
                                },
                                "application_step_trace": step_trace,
                            },
                        )
                    runtime_requirements = dict(raw.get("runtime_requirements") or {})
                    try:
                        declared_timeout = current_tool_timeout(
                            runtime_requirements.get("timeout_seconds")
                        )
                    except (TypeError, ValueError):
                        declared_timeout = 0
                    if declared_timeout <= 0:
                        return ExecutionResult(
                            is_success=False,
                            output_data="",
                            error_log="manifest_execution_timeout_invalid",
                            cost_metric={
                                "failure_type": "manifest_execution_timeout_invalid",
                                "failure_layer": "framework",
                                "failure": {
                                    "responsibility": "framework",
                                    "failure_stage": "resource_definition",
                                    "failure_code": "manifest_execution_timeout_invalid",
                                    "retryable": False,
                                    "response_received": False,
                                },
                                "application_step_trace": step_trace,
                            },
                        )
                    prepared_dispatch = PreparedToolDispatch(
                        subtask_description=desc,
                        context_data=execution_context,
                        dispatch_locator=entrypoint.dispatch,
                        command=command,
                        args=tuple(args),
                        extra_env=extra_env,
                        allowed_runtime_environment_names=(
                            manifest_tool_environment_allowlist(declared_tool_env)
                        ),
                        runtime_environment=runtime_handle,
                        network_required=execution_network_required,
                        sandbox_scope=active_sandbox_scope or None,
                        runtime_profile=dependency_result.runtime_profile,
                        runtime_kind=str((raw.get("execution") or {}).get("runtime") or "unknown"),
                        project_root=self.project_root,
                        timeout_sec=declared_timeout,
                        network_policy_mode=str(
                            getattr(self, "network_policy_mode", "disabled")
                        ),
                        artifact_adapter=register_runtime_artifacts,
                        execution_substrate_mode=self.execution_substrate_mode,
                    )
                    provider = ToolExecutionProvider(
                        prepared_dispatch, execution_substrate=self.execution_substrate
                    )
                    step_execution_context = step_resource_context
                    output_contract = formal_step_output_contract(
                        step,
                        entrypoint.output_contract,
                    )
                    resource_application = getattr(
                        step, "resource_application", None
                    )
                    if resource_application is None:
                        raise RuntimeError(
                            "formal_tool_resource_application_missing"
                        )
                    tool_source_ids = tuple(
                        provenance_source_ids(
                            bound_outputs,
                            request_step_id=step.step_id,
                        )
                    )
                    tool_upstream_handles: List[ArtifactHandle] = []
                    tool_materials: List[MaterialDescriptorV1] = []
                    tool_material_content: Dict[str, str] = {}
                    for source_id in tool_source_ids:
                        if str(source_id).startswith("artifact:"):
                            ok, failure_code, _, handle = self.resolve_artifact_handle(
                                str(source_id)
                            )
                            if not ok or handle is None:
                                raise RuntimeError(
                                    failure_code or "formal_authorized_material_missing"
                                )
                            tool_upstream_handles.append(handle)
                            descriptor, content = self._formal_material_descriptor(
                                str(source_id), handle
                            )
                            tool_materials.append(descriptor)
                            if content is not None:
                                tool_material_content[str(source_id)] = content
                    request = ResourceCallRequest(
                        resource_definition=definition,
                        entrypoint_id=formal_entrypoint_id,
                        execution_context=step_execution_context,
                        resolved_bindings=portable_evidence_bindings,
                        capability_operation_id=str(
                            getattr(step, "capability_operation_id", "") or ""
                        ),
                        semantic_task_contract={
                            "intent": step.intent,
                            "satisfied_obligation_ids": list(
                                getattr(step, "satisfied_obligation_ids", ()) or ()
                            ),
                        },
                        authorized_materials=tuple(tool_materials),
                        authorized_material_content=tool_material_content,
                        upstream_artifact_handles=tuple(tool_upstream_handles),
                        acceptance_requirements=(
                            str(
                                output_contract.get("description")
                                or "Output must satisfy the sealed output contract."
                            ),
                        ),
                        execution_world=provider.execution_world,
                        resource_native_output_contract=dict(
                            resource_application.resource_native_output_contract
                        ),
                        target_output_contract=output_contract,
                        provenance_source_ids=tool_source_ids,
                        dag_edge_contract_sha256s=tuple(
                            step.consumed_edge_contract_sha256s
                        ),
                    )
                    canonical_result = await active_resource_runtime.execute(
                        request,
                        provider=provider,
                    )
                    if _read_only_network_tool_retry_allowed(request, canonical_result):
                        retry_context = request.execution_context.model_copy(
                            update={"attempt": 2}
                        )
                        retry_request = request.model_copy(
                            update={
                                "call_id": uuid.uuid4().hex,
                                "execution_context": retry_context,
                            }
                        )
                        logger.info(
                            "[ResourcePlan] Retrying read-only network Tool {} "
                            "after a process failure (attempt 2/2)",
                            ref.resource_id,
                        )
                        step_trace[-1]["read_only_tool_retry"] = {
                            "first_call_id": request.call_id,
                            "first_failure_code": canonical_result.failure.failure_code,
                            "retry_call_id": retry_request.call_id,
                            "attempts": 2,
                        }
                        canonical_result = await active_resource_runtime.execute(
                            retry_request,
                            provider=provider,
                        )
                    result = self._realize_resource_call_result(
                        canonical_result=canonical_result,
                        resource_application=resource_application,
                    )
                    if result.is_success:
                        produced_records.extend(self._register_internal_tool_artifacts(
                            task_id, step, canonical_result))
                    if self.execution_substrate is not None:
                        for handle in canonical_result.artifacts:
                            self.artifact_registry.external_handles[handle.handle_id] = handle
                    produced_records = self._register_realized_inline_result(
                        task_id, step, result, produced_records)
                    if (
                        result.is_success
                        and self.execution_substrate is not None
                        and step.output_key == plan.final_output_from
                    ):
                        produced_records.extend(
                            await self._register_external_final_text_artifact(
                                task_id, step, canonical_result.artifacts,
                                output_contract=task_output_contract,
                            )
                        )
                else:
                    if self.execution_substrate is not None:
                        raise RuntimeError(
                            "UNBOUND_RUNTIME_PATH:external_tool_provider_missing"
                        )
                    if uses_unscoped_host_python(dependency_result.runtime_profile, active_sandbox_scope):
                        tool_executor = HostPythonExecutor(
                            project_root=self.project_root,
                            timeout_sec=180,
                        )
                    else:
                        tool_executor = DumbExecutor(timeout_sec=180)
                    result = await tool_executor.execute(
                        desc,
                        execution_context,
                        command=command,
                        args=args,
                        extra_env=extra_env,
                        runtime_environment=runtime_handle,
                        network_required=execution_network_required,
                        **(
                            {"sandbox_scope": active_sandbox_scope}
                            if active_sandbox_scope
                            else {}
                        ),
                    )
                record_step_metrics(result)
                if runtime_provisioned:
                    step_trace[-1]["runtime_prepared_packages"] = sorted(runtime_provisioned)
                if not result.is_success:
                    if bool(getattr(self, "_formal_execution_active", False)):
                        structured_failure = result.cost_metric.get("failure")
                        if not isinstance(structured_failure, Mapping):
                            raise RuntimeError("formal_provider_failure_contract_missing")
                        failure_label = str(
                            structured_failure.get("failure_code")
                            or "formal_resource_execution_failed"
                        )
                        classified_reason = failure_label
                    else:
                        default_failure_label = (
                            "artifact_validation_failed"
                            if operation_kind in {OperationKind.RUN_TESTS, OperationKind.VALIDATE_ARTIFACT}
                            else "tool_runtime_error"
                        )
                        failure_label, classified_reason = self._classify_runtime_failure(result)
                        if failure_label == "execution_failed":
                            failure_label = default_failure_label
                    result.cost_metric["failure_type"] = failure_label
                    result.cost_metric["application_step_trace"] = step_trace
                    step_trace[-1]["status"] = "failed"
                    step_trace[-1]["failure_type"] = failure_label
                    step_trace[-1]["failure_reason"] = classified_reason or result.error_log
                    return result
                if bool(getattr(self, "_formal_execution_active", False)):
                    semantic_ok = True
                    semantic_failure = ""
                    semantic_reason = ""
                    semantic_status = None
                else:
                    (
                        semantic_ok,
                        semantic_failure,
                        semantic_reason,
                        semantic_status,
                    ) = self._semantic_tool_status_failure(
                        ref,
                        result,
                        step_type,
                    )
                if semantic_status is not None:
                    step_trace[-1]["tool_semantic_status"] = semantic_status["status"]
                if not semantic_ok:
                    result.is_success = False
                    result.error_log = semantic_reason
                    result.cost_metric["failure_type"] = semantic_failure
                    result.cost_metric["application_step_trace"] = step_trace
                    step_trace[-1]["status"] = "failed"
                    step_trace[-1]["failure_type"] = semantic_failure
                    step_trace[-1]["failure_reason"] = semantic_reason
                    return result
                evidence_failure = required_operation_evidence_failure(
                    str(getattr(step, "capability_operation_id", "") or ""),
                    required_operation_kinds,
                    result.output_data,
                )
                if evidence_failure is not None:
                    result.is_success = False
                    result.error_log = evidence_failure
                    result.cost_metric["failure_type"] = evidence_failure
                    result.cost_metric["failure_layer"] = "research"
                    result.cost_metric["application_step_trace"] = step_trace
                    step_trace[-1]["status"] = "failed"
                    step_trace[-1]["failure_type"] = evidence_failure
                    step_trace[-1]["failure_reason"] = evidence_failure
                    return result
                step_outputs[step.output_key] = result.output_data
                step_outputs[step.step_id] = result.output_data
                register_step_output_source(
                    step,
                    result.output_data,
                    bound_outputs,
                    executor_kind="Tool",
                    execution_metrics=result.cost_metric,
                )
                step_results[step.output_key] = result
                if operation_kind in {OperationKind.RUN_TESTS, OperationKind.VALIDATE_ARTIFACT}:
                    result_key = f"{task_id}:{step.step_id}:{step.output_key}"
                    self.artifact_registry.validation_results[result_key] = {
                        "producer_task": task_id,
                        "producer_step": step.step_id,
                        "output_key": step.output_key,
                        "status": (
                            semantic_status.get("status")
                            if isinstance(semantic_status, dict)
                            else "passed"
                        ),
                        "validation_status": (
                            "passed"
                            if not isinstance(semantic_status, dict) or bool(semantic_status.get("semantic_ok", True))
                            else "failed"
                        ),
                        "logical_path": ",".join(self._to_tool_path(path) for path in validation_target_paths),
                        "target_paths": [self._to_tool_path(path) for path in validation_target_paths],
                    }
                if active_resource_runtime is None:
                    register_runtime_artifacts(result)
                result.cost_metric["concrete_tool_execution"] = True
                step_trace[-1]["status"] = "success"
                step_trace[-1]["output_chars"] = len(result.output_data)
                terminal_progress.step_output(task_id, step, result.output_data)
                if produced_records:
                    step_trace[-1]["produced_files_registered"] = [
                        {
                            "runtime_path": self._artifact_handle_tool_path(record.path),
                            "artifact_type": record.artifact_type,
                        }
                        for record in produced_records
                    ]
                logger.info(
                    "[ResourcePlan] Tool {} produced {} ({} chars)",
                    ref.resource_id,
                    step.output_key,
                    len(result.output_data),
                )
                continue

            if ref.resource_type == ManifestType.AGENT and step_type in {"call_agent", "synthesize_final"}:
                agent_manifest = resource_index.get(ref.resource_id, {})
                (
                    model_ok,
                    model_failure_type,
                    model_failure_reason,
                    base_model_resource_id,
                    base_model,
                ) = self._resolve_agent_base_model(
                    step,
                    plan,
                    selected,
                    resource_index,
                )
                if not model_ok or not base_model:
                    step_trace[-1]["status"] = "failed"
                    step_trace[-1]["failure_type"] = model_failure_type
                    step_trace[-1]["failure_reason"] = model_failure_reason
                    return ExecutionResult(
                        is_success=False,
                        output_data="",
                        error_log=model_failure_reason,
                        cost_metric={
                            "failure_type": model_failure_type,
                            "application_step_trace": step_trace,
                        },
                    )
                attached_resource_ids = {
                    usage.resource_id
                    for usage in plan.resource_usage
                    if step.step_id in usage.attached_to_steps
                    and usage.resource_id != base_model_resource_id
                }
                attached_resource_ids.update(
                    output_producer_by_key[output_key]
                    for output_key in bound_outputs
                    if output_key in output_producer_by_key
                )
                bound_dependencies = [
                    dependency
                    for dependency in selected
                    if dependency.resource_id in attached_resource_ids
                    and dependency.resource_id != ref.resource_id
                ]
                step_trace[-1]["base_model_resource_id"] = base_model_resource_id
                step_trace[-1]["base_model"] = base_model
                step_trace[-1]["bound_dependency_ids"] = [
                    dependency.resource_id for dependency in bound_dependencies
                ]
                agent_exec = AgentExecutor(
                    api_key=self.llm_api_key,
                    base_url=self.llm_base_url,
                    model=self.model,
                    cost_ledger=self.cost_ledger,
                    transport=self.async_model_transport,
                )
                formal_request = (
                    getattr(self, "_active_model_payload_guard", None) is not None
                )
                agent_card = agent_exec._load_agent_card(
                    agent_manifest,
                    allowed_roots=(
                        Path(agent_exec.project_root) / "Pool" / "resources",
                    )
                    if formal_request
                    else None,
                    require_file=formal_request,
                )
                register_request_source(
                    step,
                    source_id=(
                        f"candidate_resource:{task_id}:{step.step_id}:"
                        f"{ref.resource_id}"
                    ),
                    origin="candidate_bundle",
                    material={
                        "resource_id": ref.resource_id,
                        "agent_card": agent_card,
                        "base_model_resource_id": base_model_resource_id,
                        "base_model": base_model,
                    },
                    parent_source_ids=provenance_source_ids(bound_outputs),
                    producer={
                        "step_id": step.step_id,
                        "output_key": step.output_key,
                        "resource_id": ref.resource_id,
                        "base_model_resource_id": base_model_resource_id,
                        "material_kind": "agent_request",
                    },
                )
                async def execute_agent_kernel(
                    call_request: ResourceCallRequest | None = None,
                ) -> ExecutionResult:
                    media_parts: list[dict[str, Any]] = []
                    media_audit: list[dict[str, Any]] = []
                    if call_request is not None:
                        base_model_manifest = resource_index.get(
                            str(base_model_resource_id), {}
                        )
                        try:
                            media_parts, media_audit = (
                                await build_task_authorized_model_media_parts(
                                    call_request,
                                    execution_substrate=self.execution_substrate,
                                    cache_dir=Path(self.artifact_dir) / "media_snapshots",
                                    model_manifest=(
                                        base_model_manifest
                                        if isinstance(base_model_manifest, Mapping)
                                        else {}
                                    ),
                                    model_resource_id=str(base_model_resource_id),
                                    provider_model_id=str(base_model),
                                    project_root=self.project_root,
                                    endpoint_identity_sha256=(
                                        self.async_model_transport.endpoint_identity.identity_sha256
                                    ),
                                )
                            )
                        except ModelMediaProjectionError as exc:
                            return ExecutionResult(
                                is_success=False,
                                output_data="",
                                error_log=exc.code,
                                cost_metric={
                                    "failure_type": exc.code,
                                    "failure_layer": "framework",
                                    "failure": {
                                        "responsibility": "framework",
                                        "failure_stage": "model_media_projection",
                                        "failure_code": exc.code,
                                        "retryable": False,
                                        "response_received": False,
                                    },
                                },
                            )
                    invocation_payload = (
                        json.dumps(
                            call_request.model_visible_payload(),
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                        if call_request is not None
                        else execution_context
                    )
                    return await agent_exec.execute(
                        str(
                            call_request.semantic_task_contract.get("intent")
                            if call_request is not None
                            else desc
                        ),
                        invocation_payload,
                        agent_manifest=agent_manifest,
                        agent_card=agent_card,
                        agent_id=ref.resource_id,
                        base_model=base_model,
                        base_model_resource_id=base_model_resource_id,
                        subtask_id=task_id,
                        subtask_revision=(
                            step_resource_context.subtask_revision
                            if step_resource_context is not None
                            else 0
                        ),
                        dependencies=([] if call_request is not None else bound_dependencies),
                        bound_inputs=(
                            dict(call_request.resolved_bindings)
                            if call_request is not None
                            else bound_inputs
                        ),
                        artifact_type=artifact_type,
                        expected_output=expected_output,
                        max_retries=self.execution_max_retries,
                        max_tokens=self.execution_max_tokens,
                        temperature=self.execution_temperature,
                        allow_streaming=self.execution_allow_streaming,
                        allow_semantic_normalization=bool(
                            getattr(self, "_active_allow_semantic_normalization", True)
                        ),
                        format_enforcement=getattr(step, "format_enforcement", None),
                        model_payload_guard=request_guard_for_step(step, bound_outputs),
                        final_output_contract=(
                            json.dumps(
                                {
                                    "output_contract": call_request.target_output_contract,
                                    "acceptance_requirements": call_request.acceptance_requirements,
                                },
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                            )
                            if call_request is not None
                            else self._build_final_output_contract(
                                desc,
                                expected_output,
                                self._step_artifact_type(step, artifact_type),
                                execution_context,
                                plan=plan,
                                step_outputs=bound_outputs,
                                repair_feedback=repair_feedback,
                            )
                        ),
                        repair_feedback=repair_feedback,
                        model_media_parts=media_parts,
                        model_media_audit=media_audit,
                    )

                result = await execute_controller_session_step(
                    step=step,
                    controller_execution_context=step_resource_context,
                    provider_model_id=base_model,
                    bound_inputs=bound_inputs,
                    bound_outputs=bound_outputs,
                    task_context=model_task_context,
                    agent_card=agent_card,
                )
                if result is None:
                    result = await execute_resource_with_events(
                        ref=ref,
                        raw_manifest=agent_manifest,
                        execution_context=step_resource_context,
                        resolved_bindings=bound_inputs,
                        provenance_source_ids=provenance_source_ids(
                            bound_outputs,
                            request_step_id=step.step_id,
                        ),
                        runtime_kind="prompt_agent",
                        network_required=True,
                        provider=execute_agent_kernel,
                        output_contract=formal_step_output_contract(
                            step,
                            cast(Mapping[str, Any], agent_manifest).get("output_contract")
                            or {},
                        ),
                        dag_edge_contract_sha256s=tuple(
                            getattr(step, "consumed_edge_contract_sha256s", ()) or ()
                        ),
                        advisory_profile_refs=tuple(
                            getattr(step, "advisory_profile_refs", ()) or ()
                        ),
                        **formal_invocation_kwargs(
                            step,
                            formal_step_output_contract(
                                step,
                                cast(Mapping[str, Any], agent_manifest).get("output_contract")
                                or {},
                            ),
                            task_context=model_task_context,
                        ),
                    )
                record_step_metrics(result)
                if not result.is_success:
                    result.cost_metric["application_step_trace"] = step_trace
                    step_trace[-1]["status"] = "failed"
                    step_trace[-1]["failure_reason"] = result.error_log
                    return result
                step_outputs[step.output_key] = result.output_data
                step_outputs[step.step_id] = result.output_data
                step_artifact_type = self._step_artifact_type(step, artifact_type)
                ok_m, failure_type_m, reason_m, step_record = self._materialize_step_output(
                    task_id,
                    step,
                    step.output_key,
                    result.output_data,
                    step_artifact_type,
                )
                if not ok_m or step_record is None:
                    result.is_success = False
                    result.error_log = reason_m or failure_type_m
                    result.cost_metric["failure_type"] = failure_type_m
                    result.cost_metric["application_step_trace"] = step_trace
                    step_trace[-1]["status"] = "failed"
                    step_trace[-1]["failure_type"] = failure_type_m
                    step_trace[-1]["failure_reason"] = reason_m
                    return result
                register_step_output_source(
                    step,
                    result.output_data,
                    bound_outputs,
                    executor_kind="Agent",
                    execution_metrics=result.cost_metric,
                )
                task_view, overlay_contract = step_overlay_task_view(step, step_artifact_type)
                source_overlays, overlay_warnings = self.source_overlay_writer.register_step_overlays(
                    task_id,
                    task_view,
                    step,
                    step.output_key,
                    result.output_data,
                    step_artifact_type,
                    overlay_contract,
                    step_record,
                )
                if source_overlays:
                    step_trace[-1]["source_overlays"] = source_overlays
                    result.cost_metric.setdefault("source_overlays", []).extend(source_overlays)
                if overlay_warnings:
                    step_trace[-1]["overlay_warnings"] = overlay_warnings
                    result.cost_metric.setdefault("execution_warnings", []).extend(overlay_warnings)
                step_results[step.output_key] = result
                step_trace[-1]["status"] = "success"
                step_trace[-1]["output_chars"] = len(result.output_data)
                terminal_progress.step_output(task_id, step, result.output_data)
                continue

            if ref.resource_type == ManifestType.MODEL and step_type in {"call_model", "synthesize_final"}:
                model_id = self._model_api_id_from_ref(ref, resource_index)
                step_artifact_type = self._step_artifact_type(step, artifact_type)
                register_request_source(
                    step,
                    source_id=(
                        f"candidate_resource:{task_id}:{step.step_id}:"
                        f"{ref.resource_id}"
                    ),
                    origin="candidate_bundle",
                    material={
                        "resource_id": ref.resource_id,
                        "provider_model_id": model_id,
                    },
                    parent_source_ids=provenance_source_ids(bound_outputs),
                    producer={
                        "step_id": step.step_id,
                        "output_key": step.output_key,
                        "resource_id": ref.resource_id,
                        "material_kind": "model_request",
                    },
                )
                smart_exec = SmartExecutor(
                    api_key=self.llm_api_key,
                    base_url=self.llm_base_url,
                    model=model_id,
                    cost_ledger=self.cost_ledger,
                    transport=self.async_model_transport,
                )
                async def execute_model_kernel(
                    call_request: ResourceCallRequest | None = None,
                ) -> ExecutionResult:
                    media_parts: list[dict[str, Any]] = []
                    media_audit: list[dict[str, Any]] = []
                    if call_request is not None:
                        model_manifest = resource_index.get(ref.resource_id, {})
                        try:
                            media_parts, media_audit = (
                                await build_task_authorized_model_media_parts(
                                    call_request,
                                    execution_substrate=self.execution_substrate,
                                    cache_dir=Path(self.artifact_dir) / "media_snapshots",
                                    model_manifest=(
                                        model_manifest
                                        if isinstance(model_manifest, Mapping)
                                        else {}
                                    ),
                                    model_resource_id=ref.resource_id,
                                    provider_model_id=model_id,
                                    project_root=self.project_root,
                                    endpoint_identity_sha256=(
                                        self.async_model_transport.endpoint_identity.identity_sha256
                                    ),
                                )
                            )
                        except ModelMediaProjectionError as exc:
                            return ExecutionResult(
                                is_success=False,
                                output_data="",
                                error_log=exc.code,
                                cost_metric={
                                    "failure_type": exc.code,
                                    "failure_layer": "framework",
                                    "failure": {
                                        "responsibility": "framework",
                                        "failure_stage": "model_media_projection",
                                        "failure_code": exc.code,
                                        "retryable": False,
                                        "response_received": False,
                                    },
                                },
                            )
                    invocation_payload = (
                        json.dumps(
                            call_request.model_visible_payload(),
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                        if call_request is not None
                        else execution_context
                    )
                    return await smart_exec.execute(
                        str(
                            call_request.semantic_task_contract.get("intent")
                            if call_request is not None
                            else desc
                        ),
                        invocation_payload,
                        model=model_id,
                        selected_resource_id=ref.resource_id,
                        model_resource_id=ref.resource_id,
                        subtask_id=task_id,
                        subtask_revision=(
                            step_resource_context.subtask_revision
                            if step_resource_context is not None
                            else 0
                        ),
                        artifact_type=step_artifact_type,
                        temperature=self.execution_temperature,
                        max_retries=self.execution_max_retries,
                        max_tokens=self.execution_max_tokens,
                        allow_streaming=self.execution_allow_streaming,
                        allow_semantic_normalization=bool(
                            getattr(self, "_active_allow_semantic_normalization", True)
                        ),
                        format_enforcement=getattr(step, "format_enforcement", None),
                        model_payload_guard=request_guard_for_step(step, bound_outputs),
                        final_output_contract=(
                            json.dumps(
                                {
                                    "output_contract": call_request.target_output_contract,
                                    "acceptance_requirements": call_request.acceptance_requirements,
                                },
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                            )
                            if call_request is not None
                            else self._build_final_output_contract(
                                desc,
                                expected_output,
                                step_artifact_type,
                                execution_context,
                                plan=plan,
                                step_outputs=bound_outputs,
                                repair_feedback=repair_feedback,
                            )
                        ),
                        repair_feedback=repair_feedback,
                        model_media_parts=media_parts,
                        model_media_audit=media_audit,
                    )

                result = await execute_controller_session_step(
                    step=step,
                    controller_execution_context=step_resource_context,
                    provider_model_id=model_id,
                    bound_inputs=bound_inputs,
                    bound_outputs=bound_outputs,
                    task_context=model_task_context,
                )
                if result is None:
                    result = await execute_resource_with_events(
                        ref=ref,
                        raw_manifest=raw,
                        execution_context=step_resource_context,
                        resolved_bindings=bound_inputs,
                        provenance_source_ids=provenance_source_ids(
                            bound_outputs,
                            request_step_id=step.step_id,
                        ),
                        runtime_kind="model_api",
                        network_required=True,
                        provider=execute_model_kernel,
                        output_contract=formal_step_output_contract(
                            step,
                            cast(Mapping[str, Any], raw).get("output_contract") or {},
                        ),
                        dag_edge_contract_sha256s=tuple(
                            getattr(step, "consumed_edge_contract_sha256s", ()) or ()
                        ),
                        advisory_profile_refs=tuple(
                            getattr(step, "advisory_profile_refs", ()) or ()
                        ),
                        **formal_invocation_kwargs(
                            step,
                            formal_step_output_contract(
                                step,
                                cast(Mapping[str, Any], raw).get("output_contract") or {},
                            ),
                            task_context=model_task_context,
                        ),
                    )
                _apply_direct_final_python_fence_conversion(
                    result,
                    plan=plan,
                    producer_step=step,
                    task_output_contract=task_output_contract,
                )
                record_step_metrics(result)
                if not result.is_success:
                    result.cost_metric["application_step_trace"] = step_trace
                    step_trace[-1]["status"] = "failed"
                    step_trace[-1]["failure_reason"] = result.error_log
                    return result
                from .artifact_semantics import OutputContractViolation

                try:
                    pre_write_validation = _validate_direct_final_write_source(
                        plan=plan,
                        producer_step=step,
                        content=result.output_data,
                        task_output_contract=task_output_contract,
                    )
                except OutputContractViolation as exc:
                    failure_code = exc.failure_code
                    logger.warning(
                        "[ResourcePlan] Pre-write contract rejected task={} step={} code={}",
                        task_id, step.step_id, failure_code,
                    )
                    result.is_success = False
                    result.error_log = failure_code
                    result.cost_metric["failure_type"] = failure_code
                    result.cost_metric["failure_layer"] = "research"
                    result.cost_metric["failure"] = {
                        "responsibility": "research",
                        "failure_stage": "output_contract",
                        "failure_code": failure_code,
                        "retryable": False,
                        "response_received": True,
                    }
                    result.cost_metric["pre_write_contract_validation"] = {
                        "status": "fail", "failure_code": failure_code,
                    }
                    step_trace[-1]["status"] = "failed"
                    step_trace[-1]["failure_type"] = failure_code
                    step_trace[-1]["failure_reason"] = "output_contract_postcondition_failed"
                    step_trace[-1]["postcondition_failure_phase"] = "pre_write"
                    step_trace[-1]["resource_call_status"] = "success"
                    record_step_metrics(result)
                    return result
                if pre_write_validation is not None:
                    result.cost_metric["pre_write_contract_validation"] = pre_write_validation
                step_outputs[step.output_key] = result.output_data
                step_outputs[step.step_id] = result.output_data
                ok_m, failure_type_m, reason_m, step_record = self._materialize_step_output(
                    task_id,
                    step,
                    step.output_key,
                    result.output_data,
                    step_artifact_type,
                )
                if not ok_m or step_record is None:
                    result.is_success = False
                    result.error_log = reason_m or failure_type_m
                    result.cost_metric["failure_type"] = failure_type_m
                    result.cost_metric["application_step_trace"] = step_trace
                    step_trace[-1]["status"] = "failed"
                    step_trace[-1]["failure_type"] = failure_type_m
                    step_trace[-1]["failure_reason"] = reason_m
                    return result
                register_step_output_source(
                    step,
                    result.output_data,
                    bound_outputs,
                    executor_kind="Model",
                    execution_metrics=result.cost_metric,
                )
                task_view, overlay_contract = step_overlay_task_view(step, step_artifact_type)
                source_overlays, overlay_warnings = self.source_overlay_writer.register_step_overlays(
                    task_id,
                    task_view,
                    step,
                    step.output_key,
                    result.output_data,
                    step_artifact_type,
                    overlay_contract,
                    step_record,
                )
                if source_overlays:
                    step_trace[-1]["source_overlays"] = source_overlays
                    result.cost_metric.setdefault("source_overlays", []).extend(source_overlays)
                if overlay_warnings:
                    step_trace[-1]["overlay_warnings"] = overlay_warnings
                    result.cost_metric.setdefault("execution_warnings", []).extend(overlay_warnings)
                step_results[step.output_key] = result
                step_trace[-1]["status"] = "success"
                step_trace[-1]["output_chars"] = len(result.output_data)
                terminal_progress.step_output(task_id, step, result.output_data)
                continue

            step_trace[-1]["status"] = "failed"
            step_trace[-1]["failure_type"] = "policy_invalid_plan"
            return ExecutionResult(
                is_success=False,
                output_data="",
                error_log=f"Unsupported resource_type in application plan: {ref.resource_type.value}",
                cost_metric={
                    "failure_type": "policy_invalid_plan",
                    "application_step_trace": step_trace,
                },
            )

        final_key = plan.final_output_from
        if final_key and final_key in step_results:
            logger.bind(terminal_task=task_id).info("[ResourcePlan] Final output selected from step output {}", final_key)
            final_result = step_results[final_key]
            final_step = next((step for step in plan.steps if step.output_key == final_key), None)
            final_artifact_type = self._step_artifact_type(final_step, artifact_type) if final_step else artifact_type
            if (
                final_artifact_type == "code"
                and final_result.output_data
                and bool(getattr(self, "_active_allow_semantic_normalization", True))
            ):
                normalized_code = self._normalize_materialized_content(final_result.output_data, "code")
                if normalized_code != final_result.output_data:
                    final_result.output_data = normalized_code
                    step_outputs[final_key] = normalized_code
                    final_result.cost_metric["code_block_extracted_for_contract"] = True
                contract_text = "\n".join(
                    text
                    for text in (expected_output, desc)
                    if text
                )
                aligned_code, aliases = self._append_missing_interface_aliases(
                    final_result.output_data,
                    contract_text,
                )
                if aliases:
                    final_result.output_data = aligned_code
                    step_outputs[final_key] = aligned_code
                    final_result.cost_metric["interface_aliases_added"] = aliases
                    if final_step is not None:
                        self._materialize_step_output(
                            task_id,
                            final_step,
                            final_key,
                            aligned_code,
                            "code",
                            preferred_name=f"{task_id}_{final_key}_contract_aligned",
                        )
                    step_trace.append(
                        {
                            "step_id": "interface_contract_alignment",
                            "step_type": "deterministic_repair",
                            "resource_id": "orchestrator.interface_contract",
                            "resource_type": "builtin",
                            "output_key": final_key,
                            "status": "success",
                            "aliases_added": aliases,
                        }
                    )
            terminal_progress.detail("Execution", "Selected output before evaluation", final_result.output_data, task_id)
            final_result.cost_metric["application_step_outputs"] = dict(step_outputs)
            final_result.cost_metric["application_step_trace"] = step_trace
            final_result.cost_metric["final_output_from"] = final_key
            final_result.cost_metric["allowed_python_packages"] = sorted(runtime_allowed_packages)
            return final_result

        return ExecutionResult(
            is_success=False,
            output_data="",
            error_log=f"policy_invalid_plan: final output not produced: {final_key}",
            cost_metric={
                "failure_type": "policy_invalid_plan",
                "application_step_trace": step_trace,
            },
        )

    async def _attempt_same_bundle_repair(
        self,
        plan: ResourceApplicationPlan,
        selected: List[TypedResourceRef],
        subtask: Subtask,
        context_data: str,
        artifact_type: str,
        expected_output: str,
        resource_index: Dict[str, dict],
        failed_result: ExecutionResult,
        failure_type: str,
        failure_reason: str,
    ) -> Optional[ExecutionResult]:
        """Repair a rejected final Model/Agent artifact without rerunning earlier steps."""
        repairable_failures = {
            "format_invalid",
            "missing_required_content",
            "contract_violation",
            "factual_mismatch",
            "interface_contract_mismatch",
            "placeholder_content",
            "artifact_dependency_missing",
        }
        if failure_type not in repairable_failures:
            return None
        if not failed_result.output_data.strip():
            return None
        if not plan.final_output_from:
            return None

        final_step = next(
            (step for step in plan.steps if step.output_key == plan.final_output_from),
            None,
        )
        if final_step is None:
            return None

        final_ref = self._find_ref(final_step.resource_id, selected, resource_index)
        if final_ref is None or final_ref.resource_type not in {ManifestType.MODEL, ManifestType.AGENT}:
            return None

        raw_step_outputs = failed_result.cost_metric.get("application_step_outputs", {})
        step_outputs = dict(raw_step_outputs) if isinstance(raw_step_outputs, dict) else {}
        step_outputs.pop(plan.final_output_from, None)
        repair_feedback = (
            f"Failure type: {failure_type}\n"
            f"Failure reason:\n{failure_reason}\n\n"
            f"Previous rejected output:\n{failed_result.output_data[:20000]}"
        )
        bound_inputs, bound_outputs = self._bound_step_inputs(
            final_step,
            resource_index,
            step_outputs,
        )
        repair_context = self._step_execution_context(context_data, bound_inputs)
        logger.warning(
            "[Repair] Attempting same-bundle repair for {} with {}",
            subtask.id,
            final_ref.resource_id,
        )

        if final_ref.resource_type == ManifestType.AGENT:
            agent_manifest = resource_index.get(final_ref.resource_id, {})
            ok, _, _, base_model_resource_id, base_model = self._resolve_agent_base_model(
                final_step,
                plan,
                selected,
                resource_index,
            )
            if not ok or not base_model:
                return None
            attached_ids = {
                usage.resource_id
                for usage in plan.resource_usage
                if final_step.step_id in usage.attached_to_steps
                and usage.resource_id != base_model_resource_id
            }
            agent_exec = AgentExecutor(
                api_key=self.llm_api_key,
                base_url=self.llm_base_url,
                model=self.model,
                cost_ledger=self.cost_ledger,
                transport=self.async_model_transport,
            )
            result = await agent_exec.execute(
                subtask.description,
                repair_context,
                agent_manifest=agent_manifest,
                agent_id=final_ref.resource_id,
                base_model=base_model,
                base_model_resource_id=base_model_resource_id,
                subtask_id=subtask.id,
                subtask_revision=0,
                dependencies=[
                    ref
                    for ref in selected
                    if ref.resource_id in attached_ids
                    and ref.resource_id != final_ref.resource_id
                ],
                bound_inputs=bound_inputs,
                artifact_type=artifact_type,
                expected_output=expected_output,
                repair_feedback=repair_feedback,
                final_output_contract=self._build_final_output_contract(
                    subtask.description,
                    expected_output,
                    artifact_type,
                    context_data,
                    plan=plan,
                    step_outputs=bound_outputs,
                    repair_feedback=repair_feedback,
                ),
                max_retries=1,
                temperature=self.execution_temperature,
            )
            return result

        model_id = self._model_api_id_from_ref(final_ref, resource_index)
        smart_exec = SmartExecutor(
            api_key=self.llm_api_key,
            base_url=self.llm_base_url,
            model=model_id,
            cost_ledger=self.cost_ledger,
            transport=self.async_model_transport,
        )
        result = await smart_exec.execute(
            subtask.description,
            repair_context,
            model=model_id,
            selected_resource_id=final_ref.resource_id,
            model_resource_id=final_ref.resource_id,
            subtask_id=subtask.id,
            subtask_revision=0,
            artifact_type=artifact_type,
            temperature=self.execution_temperature,
            max_retries=1,
            repair_feedback=repair_feedback,
            final_output_contract=self._build_final_output_contract(
                subtask.description,
                expected_output,
                artifact_type,
                context_data,
                plan=plan,
                step_outputs=step_outputs,
                repair_feedback=repair_feedback,
            ),
        )
        return result

    async def _execute_selected_resources(
        self,
        selected: List[TypedResourceRef],
        desc: str,
        context_data: str,
        artifact_type: str,
        resource_index: Dict[str, dict],
        expected_output: str = "",
    ) -> ExecutionResult:
        selected_context = self._selected_resource_context(selected, resource_index)
        execution_context = context_data
        if selected_context:
            execution_context += f"\n\n--- [Selected Resource Context] ---\n{selected_context}\n"
        file_context = self._extract_local_file_context(desc + "\n" + execution_context)
        if file_context:
            execution_context += f"\n\n--- [Resolved Local File Context] ---\n{file_context}\n"

        agent_ref = next((r for r in selected if r.resource_type == ManifestType.AGENT), None)
        if agent_ref is not None:
            agent_manifest = resource_index.get(agent_ref.resource_id, {})
            base_model_hint = str(agent_ref.base_model or "").strip()
            model_ref = next(
                (
                    candidate
                    for candidate in selected
                    if candidate.resource_type == ManifestType.MODEL
                    and base_model_hint
                    in {
                        candidate.resource_id,
                        str(candidate.base_model or "").strip(),
                    }
                ),
                None,
            )
            if model_ref is None:
                return ExecutionResult(
                    is_success=False,
                    output_data="",
                    error_log=(
                        "agent_missing_base_model: legacy Agent execution requires "
                        "an explicit Router-resolved Model binding"
                    ),
                    cost_metric={
                        "failure_type": "agent_missing_base_model",
                        "failure_layer": "plan_composition",
                    },
                )
            base_model = self._model_api_id_from_ref(model_ref, resource_index)
            agent_exec = AgentExecutor(
                api_key=self.llm_api_key,
                base_url=self.llm_base_url,
                model=self.model,
                cost_ledger=self.cost_ledger,
                transport=self.async_model_transport,
            )
            result = await agent_exec.execute(
                desc,
                execution_context,
                agent_manifest=agent_manifest,
                agent_id=agent_ref.resource_id,
                base_model=base_model,
                base_model_resource_id=model_ref.resource_id,
                dependencies=[r for r in selected if r.resource_id != agent_ref.resource_id],
                artifact_type=artifact_type,
                expected_output=expected_output,
                final_output_contract=self._build_final_output_contract(
                    desc,
                    expected_output,
                    artifact_type,
                    execution_context,
                ),
                temperature=self.execution_temperature,
            )
            return result

        model_ref = next((r for r in selected if r.resource_type == ManifestType.MODEL), None)
        if model_ref is not None:
            model_id = self._model_api_id_from_ref(model_ref, resource_index)
            smart_exec = SmartExecutor(
                api_key=self.llm_api_key,
                base_url=self.llm_base_url,
                model=model_id,
                cost_ledger=self.cost_ledger,
                transport=self.async_model_transport,
            )
            result = await smart_exec.execute(
                desc,
                execution_context,
                model=model_id,
                selected_resource_id=model_ref.resource_id,
                model_resource_id=model_ref.resource_id,
                artifact_type=artifact_type,
                temperature=self.execution_temperature,
                final_output_contract=self._build_final_output_contract(
                    desc,
                    expected_output,
                    artifact_type,
                    execution_context,
                ),
            )
            return result

        tool_ref = next((r for r in selected if r.resource_type == ManifestType.TOOL), None)
        if tool_ref is not None:
            if self.execution_substrate is not None:
                raise RuntimeError(
                    "UNBOUND_RUNTIME_PATH:external_legacy_selected_tool_forbidden"
                )
            dependency_result = self._dependency_result_for_ref(tool_ref, resource_index)
            if dependency_result.is_blocked:
                dependency_failure = self._dependency_failure_contract(
                    dependency_result
                )
                dependency_failure_type = dependency_failure["failure_type"]
                return ExecutionResult(
                    is_success=False,
                    output_data="",
                    error_log=dependency_result.reason,
                    cost_metric={
                        "failure_type": dependency_failure_type,
                        "failure_layer": dependency_failure["responsibility"],
                        "failure": dependency_failure,
                        "dependency_check": dependency_result.model_dump(),
                    },
                )
            tool_manifest = resource_index.get(tool_ref.resource_id, {})
            execution_network_required = bool(
                (tool_manifest.get("runtime_requirements") or {}).get(
                    "network_required", False
                )
            )
            runtime_handle, prep_event_id, prep_failure = await self._prepare_step_runtime(
                task_id=self.runtime_preparation_run_id or "legacy_selected_resources",
                step_id="legacy_selected_tool",
                raw_manifest=tool_manifest,
                execution_network_required=execution_network_required,
                phase="manifest",
            )
            if prep_failure is not None:
                prep_failure["preparation_event_id"] = prep_event_id
                return self._runtime_preparation_failure_result(prep_failure)
            command, args = self._build_tool_invocation(
                tool_ref,
                resource_index,
                desc + "\n" + execution_context,
            )
            dumb_exec = DumbExecutor(timeout_sec=180)
            result = await dumb_exec.execute(
                desc,
                execution_context,
                command=command,
                args=args,
                runtime_environment=runtime_handle,
                network_required=execution_network_required,
            )
            result.cost_metric["runtime_preparation_event_ids"] = [prep_event_id]
            semantic_ok, failure_type, reason, semantic_status = self._semantic_tool_status_failure(
                tool_ref,
                result,
                "run_tool",
            )
            if semantic_status is not None:
                result.cost_metric["tool_semantic_status"] = semantic_status["status"]
            if not semantic_ok:
                result.is_success = False
                result.error_log = reason
                result.cost_metric["failure_type"] = failure_type
            return result

        return await self._execute_full_generative(
            desc,
            execution_context,
            artifact_type,
            expected_output=expected_output,
            feedback="Selected bundle had no directly executable Model, Agent, or Tool.",
        )

    async def _execute_application_plan(self, *args: Any, **kwargs: Any) -> ExecutionResult:
        """Explicit legacy/E1 compatibility alias for the historical DAG kernel."""

        if bool(getattr(self, "_formal_execution_active", False)):
            raise RuntimeError("formal_legacy_application_plan_kernel_forbidden")
        return await self._execute_resource_dag(*args, **kwargs)

    async def execute_sealed_plan(
        self,
        subtask: Subtask,
        artifact: SealedPlanCompilationArtifact,
        candidate_resources: Sequence[TypedResourceRef],
        resource_index: Dict[str, dict],
        *,
        context_data: str = "",
        input_handles: Optional[Sequence[ArtifactHandle | Dict[str, Any]]] = None,
        model_payload_guard: Optional[Callable[[Mapping[str, Any]], None]] = None,
        resume_checkpoints: Sequence[CompletedStepCheckpoint] = (),
        resume_results: Optional[Mapping[str, ExecutionResult]] = None,
        original_query: str = "",
        required_operation_kinds: Sequence[str] = (),
    ) -> Dict[str, Any]:
        """Execute only a successfully sealed, immutably lowered Plan."""
        if subtask.semantic_contract_v2 is not None:
            alignment = (artifact.validation_audit or {}).get("input_alignment")
            if not isinstance(alignment, Mapping) or alignment.get("protocol") != "sgar-input-alignment-v1":
                raise RuntimeError("input_alignment_state_missing_start_new_run")
        if input_handles is not None:
            self.register_input_handles(input_handles)
        active_scope = self._resource_runtime_sandbox_scope()
        lowered = LoweredExecutionPlan.model_validate(artifact.lowered_plan)
        entrypoints = {
            item.step_id: item.entrypoint_id
            for item in lowered.step_templates
            if item.entrypoint_id is not None
        }
        candidate_by_id = {item.resource_id: item for item in candidate_resources}
        resource_definitions: Dict[str, ResourceDefinition] = {}
        environment_facts: Dict[str, Dict[str, Any]] = {}
        controller_backing_model_ids = {
            item.controller_session_spec.backing_model_resource_id
            for item in lowered.step_templates
            if isinstance(item.controller_session_spec, ControllerSessionSpecV2)
        }
        applied_ready_models: Mapping[str, Any] = {}
        if controller_backing_model_ids:
            try:
                applied_ready_state = load_applied_model_ready_state(
                    self.project_root,
                    expected_endpoint_identity_sha256=(
                        self.async_model_transport.endpoint_identity.identity_sha256
                    ),
                )
                applied_ready_models = applied_ready_state.by_resource_id
            except (RetrievalRuntimeError, TypeError, ValueError):
                applied_ready_models = {}
        for candidate in candidate_resources:
            raw = resource_index.get(candidate.resource_id)
            failures: List[str] = []
            if not isinstance(raw, Mapping):
                failures.append("readiness_manifest_missing")
            else:
                try:
                    definition = ResourceDefinition.from_manifest(raw)
                    resource_definitions[candidate.resource_id] = definition
                except (ResourceManifestError, ValueError):
                    failures.append("readiness_manifest_invalid")
                requirements = raw.get("runtime_requirements")
                requirements = requirements if isinstance(requirements, Mapping) else {}
                if candidate.resource_type == ManifestType.TOOL and bool(
                    requirements.get("network_required", False)
                ) and str(
                    getattr(self, "network_policy_mode", "disabled")
                ) == "disabled":
                    failures.append("readiness_network_policy_blocked")
                if candidate.resource_type == ManifestType.TOOL:
                    dependency = self._dependency_result_for_ref(candidate, resource_index)
                    if dependency.is_blocked:
                        failures.append("readiness_runtime_dependency_blocked")
                if candidate.resource_type in {ManifestType.SKILL, ManifestType.RESOURCE}:
                    execution = raw.get("execution")
                    uri = execution.get("uri") if isinstance(execution, Mapping) else None
                    if not uri:
                        failures.append("readiness_declared_resource_uri_missing")
                    else:
                        try:
                            material_path = Path(self._resolve_resource_uri(str(uri)))
                            if not material_path.exists() or not os.access(material_path, os.R_OK):
                                failures.append("readiness_declared_resource_unreadable")
                        except (OSError, ValueError):
                            failures.append("readiness_declared_resource_unreadable")
            facts: Dict[str, Any] = {
                "ready": not failures,
                "failure_codes": tuple(failures),
                "runtime_requirements_sha256": canonical_sha256(
                    dict((raw or {}).get("runtime_requirements") or {})
                    if isinstance(raw, Mapping)
                    else {}
                ),
            }
            if candidate.resource_id in controller_backing_model_ids:
                applied_model = applied_ready_models.get(candidate.resource_id)
                if applied_model is not None:
                    facts.update(
                        {
                            "capability_authority": "applied_ready_state",
                            "operator_approved_capabilities": {
                                capability: {"status": "operator_approved",
                                             "approval_sha256": applied_model.operator_approval_sha256}
                                for capability in applied_model.operator_approved_capabilities
                            },
                            "applied_capabilities": {
                                capability: {"status": "live_verified"}
                                for capability in (
                                    applied_model.capabilities_live_verified
                                )
                            },
                            "controller_tool_runtime_protocol": (
                                CONTROLLER_TOOL_RUNTIME_PROTOCOL
                            ),
                        }
                    )
            environment_facts[candidate.resource_id] = facts
        execution_state_var = self._execution_state_context_var()
        state_token = execution_state_var.set(
            _ExecutionLocalState(
                sandbox_scope=dict(active_scope),
                runtime_path_map=(
                    RuntimePathMap.from_scope(active_scope) if active_scope else None
                ),
                model_payload_guard=model_payload_guard,
                allow_semantic_normalization=False,
                sealed_entrypoints=entrypoints,
                formal_execution_active=True,
            )
        )
        engine = SealedPlanExecutionEngine(run_id=artifact.run_id)

        async def execute_dag(
            formal_plan: FormalExecutablePlan,
            execution_context: ResourceExecutionContext,
            checkpoints: Mapping[str, CompletedStepCheckpoint],
            checkpoint_results: Mapping[str, ExecutionResult],
        ) -> ExecutionResult:
            selected = [
                candidate_by_id[resource_id]
                for resource_id in formal_plan.selected_resource_ids
            ]
            return await self._execute_resource_dag(
                subtask.id,
                formal_plan,
                selected,
                subtask.description,
                context_data,
                subtask.artifact_type.value,
                subtask.expected_output,
                resource_index,
                {},
                task_output_contract=subtask.output_contract,
                resource_execution_context=execution_context,
                sealed_plan_sha256=formal_plan.plan_sha256,
                resume_checkpoints=checkpoints,
                resume_results=checkpoint_results,
                formal_original_query=original_query,
                required_operation_kinds=required_operation_kinds,
                required_workspace_effect=(
                    subtask.semantic_contract_v2 is not None
                    and subtask.semantic_contract_v2.required_effect == "task_workspace_mutation"
                ),
            )

        try:
            return await engine.execute(
                artifact=artifact,
                candidate_resources=candidate_resources,
                resource_definitions=resource_definitions,
                environment_facts=environment_facts,
                sandbox_scope_sha256=sandbox_scope_sha256(
                    active_scope,
                    project_root=self.project_root,
                ),
                execute_dag=execute_dag,
                resume_checkpoints=resume_checkpoints,
                resume_results=resume_results,
            )
        finally:
            execution_state_var.reset(state_token)

    async def execute_application_plan(
        self,
        subtask: Subtask,
        plan: Any,
        selected: List[TypedResourceRef],
        resource_index: Dict[str, dict],
        *,
        context_data: str = "",
        input_handles: Optional[Sequence[ArtifactHandle | Dict[str, Any]]] = None,
        sandbox_scope: Optional[Dict[str, Any]] = None,
        model_payload_guard: Optional[Callable[[Mapping[str, Any]], None]] = None,
        allow_semantic_normalization: bool = True,
        resource_execution_context: Optional[ResourceExecutionContext] = None,
        sealed_plan_sha256: Optional[str] = None,
        sealed_entrypoints: Optional[Mapping[str, str]] = None,
        resume_checkpoints: Optional[Mapping[str, CompletedStepCheckpoint]] = None,
        resume_results: Optional[Mapping[str, ExecutionResult]] = None,
    ) -> Dict[str, Any]:
        """Preflight and execute an explicit plan through production runtime.

        The method intentionally performs no retrieval, resource substitution,
        plan repair, or full-generative fallback.  Its structured return value
        is suitable for experiment traces and preserves the distinction between
        plan validity, resource executability, and downstream task success.
        """

        if bool(getattr(self, "_formal_execution_active", False)):
            raise RuntimeError("formal_legacy_application_plan_forbidden")

        def application_plan_hash(value: ResourceApplicationPlan) -> str:
            payload = value.model_dump(mode="json")
            canonical = json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            return hashlib.sha256(canonical).hexdigest()

        candidate_resources = list(selected)
        application_projection_hash = application_plan_hash(plan)
        validated_plan_hash = sealed_plan_sha256 or application_projection_hash
        working_plan = plan.model_copy(deep=True)
        self._active_sealed_entrypoints = dict(sealed_entrypoints or {})
        if input_handles is not None:
            self.register_input_handles(input_handles)
        if (
            sandbox_scope is None
            and getattr(self, "resource_runtime", None) is not None
        ):
            sandbox_scope = self._resource_runtime_sandbox_scope()
        self._active_sandbox_scope = dict(sandbox_scope or {})
        self._active_runtime_path_map = (
            RuntimePathMap.from_scope(self._active_sandbox_scope)
            if self._active_sandbox_scope
            else None
        )
        self._active_model_payload_guard = model_payload_guard
        # This flag covers both Plan compatibility normalization and the
        # historical post-execution code/alias repair.  A fixed-pass formal run
        # must preserve the exact model/agent artifact for research evaluation.
        self._active_allow_semantic_normalization = bool(allow_semantic_normalization)
        if allow_semantic_normalization:
            self.normalize_application_plan_semantics(
                working_plan,
                candidate_resources,
                selected,
                resource_index,
                subtask,
            )
        if (
            resource_execution_context is None
            and getattr(self, "resource_runtime", None) is not None
        ):
            resource_execution_context = ResourceExecutionContext.legacy(
                run_id=self.execution_ledger.run_id,
                subtask_id=subtask.id,
                step_id="plan",
                selected_resource_ids=[item.resource_id for item in selected],
                plan_sha256=validated_plan_hash,
                sandbox_scope_sha256=sandbox_scope_sha256(
                    self._active_sandbox_scope,
                    project_root=self.project_root,
                ),
            )
        ok, failure_type, failure_reason, resolved_bindings = (
            self.preflight_application_plan(
                working_plan,
                candidate_resources,
                selected,
                resource_index,
                subtask,
                context_data,
                allow_semantic_normalization=False,
                formal_resource_runtime=(
                    getattr(self, "resource_runtime", None) is not None
                ),
            )
        )
        preflight = {
            "ok": ok,
            "failure_type": failure_type,
            "failure_reason": failure_reason,
            "resolved_bindings": self._portable_binding_tree(resolved_bindings),
            "binding_protocol": BINDING_PROTOCOL,
            "plan_hash": application_plan_hash(working_plan),
        }
        plan_sha256 = sealed_plan_sha256 or canonical_sha256(
            working_plan.model_dump(mode="json")
        )
        if (
            resource_execution_context is not None
            and resource_execution_context.plan_sha256 != plan_sha256
        ):
            raise RuntimeError("resource_execution_context_plan_mismatch")
        if not ok:
            result = self._structured_failure_result(
                failure_type or "policy_invalid_plan",
                failure_reason or "Application plan preflight failed.",
            )
            result.cost_metric["fallback_skipped_reason"] = (
                "experiment_explicit_plan_no_recovery"
            )
            return {
                "preflight": preflight,
                "result": result,
                "plan": working_plan,
                "plan_immutability": {
                    "validated_plan_hash": validated_plan_hash,
                    "preflight_plan_hash": validated_plan_hash,
                    "executed_plan_hash": validated_plan_hash,
                    "application_projection_hash": preflight["plan_hash"],
                    "passed": application_projection_hash == preflight["plan_hash"],
                },
            }

        result = await self._execute_resource_dag(
            subtask.id,
            working_plan,
            selected,
            subtask.description,
            context_data,
            subtask.artifact_type.value,
            subtask.expected_output,
            resource_index,
            resolved_bindings,
            task_output_contract=subtask.output_contract,
            resource_execution_context=resource_execution_context,
            sealed_plan_sha256=sealed_plan_sha256,
            resume_checkpoints=resume_checkpoints,
            resume_results=resume_results,
        )
        executed_plan_hash = application_plan_hash(working_plan)
        return {
            "preflight": preflight,
            "result": result,
            "plan": working_plan,
            "plan_immutability": {
                "validated_plan_hash": validated_plan_hash,
                "preflight_plan_hash": validated_plan_hash,
                "executed_plan_hash": validated_plan_hash,
                "application_projection_hash": executed_plan_hash,
                "passed": application_projection_hash == preflight["plan_hash"] == executed_plan_hash,
            },
        }

    def _synthetic_plan_from_selected_resources(
        self,
        selected: List[TypedResourceRef],
        artifact_type: str,
        expected_output: str = "",
    ) -> Optional[ResourceApplicationPlan]:
        """Convert legacy selected-resource execution into the unified plan path."""
        if not selected:
            return None
        model_or_agent = next(
            (ref for ref in selected if ref.resource_type in {ManifestType.MODEL, ManifestType.AGENT}),
            None,
        )
        tool = next((ref for ref in selected if ref.resource_type == ManifestType.TOOL), None)
        resource_or_skill = next(
            (ref for ref in selected if ref.resource_type in {ManifestType.RESOURCE, ManifestType.SKILL}),
            None,
        )
        runtime_model = next(
            (ref for ref in selected if ref.resource_type == ManifestType.MODEL),
            None,
        )

        steps: List[ResourceApplicationStep] = []
        if model_or_agent is not None:
            step_type = "call_agent" if model_or_agent.resource_type == ManifestType.AGENT else "call_model"
            if model_or_agent.resource_type == ManifestType.AGENT and runtime_model is None:
                return None
            steps.append(
                ResourceApplicationStep(
                    step_id="synthetic_generate_final",
                    step_type=step_type,
                    resource_id=model_or_agent.resource_id,
                    intent=(
                        "Generate the current subtask artifact using selected resources, "
                        "context packet, upstream artifacts, and output contract."
                    ),
                    input_bindings=(
                        {"base_model": {"resource_id": runtime_model.resource_id}}
                        if model_or_agent.resource_type == ManifestType.AGENT
                        and runtime_model is not None
                        else {}
                    ),
                    output_key="final_artifact",
                    expected_output_contract=ResourceOutputContract(
                        artifact_type=artifact_type,
                        description=expected_output or "Final artifact aligned with the current subtask contract.",
                    ),
                )
            )
        elif tool is not None:
            steps.append(
                ResourceApplicationStep(
                    step_id="synthetic_run_tool",
                    step_type="run_tool",
                    resource_id=tool.resource_id,
                    intent="Run the selected tool through the unified tool binding path.",
                    input_bindings={},
                    output_key="final_artifact",
                    expected_output_contract=ResourceOutputContract(
                        artifact_type=artifact_type,
                        description=expected_output or "Tool output for the current subtask.",
                    ),
                )
            )
        elif resource_or_skill is not None:
            steps.append(
                ResourceApplicationStep(
                    step_id="synthetic_read_resource",
                    step_type="read_resource",
                    resource_id=resource_or_skill.resource_id,
                    intent="Read selected context resource through the unified plan path.",
                    input_bindings={},
                    output_key="final_artifact",
                    expected_output_contract=ResourceOutputContract(
                        artifact_type="plaintext",
                        description="Context snippet from selected resource.",
                    ),
                )
            )
        if not steps:
            return None

        selected_ids = [steps[0].resource_id]
        if (
            model_or_agent is not None
            and model_or_agent.resource_type == ManifestType.AGENT
            and runtime_model is not None
        ):
            selected_ids.append(runtime_model.resource_id)
        used_id = steps[0].resource_id
        resource_usage = [
            ResourceUsageDecision(
                resource_id=used_id,
                decision="use",
                use_as="executable_step",
                attached_to_steps=[steps[0].step_id],
                reason="Converted from legacy selected-resource execution.",
            )
        ]
        if runtime_model is not None and runtime_model.resource_id in selected_ids and runtime_model.resource_id != used_id:
            resource_usage.append(
                ResourceUsageDecision(
                    resource_id=runtime_model.resource_id,
                    decision="use",
                    use_as="agent_base_model",
                    attached_to_steps=[steps[0].step_id],
                    reason="Selected as the runtime Model for the synthetic Agent step.",
                )
            )
        return ResourceApplicationPlan(
            is_sufficient=True,
            selected_resource_ids=selected_ids,
            resource_usage=resource_usage,
            steps=steps,
            final_output_from="final_artifact",
            expected_execution_mode=self._actual_mode_for_selection(selected),
            reason="Synthetic ResourceApplicationPlan generated for legacy selected-resource path.",
        )

    def _actual_mode_for_selection(self, selected: List[TypedResourceRef]) -> ExecutionMode:
        types = {ref.resource_type for ref in selected}
        if ManifestType.MODEL in types or ManifestType.AGENT in types:
            return ExecutionMode.SEMI_GENERATIVE
        if ManifestType.TOOL in types:
            return ExecutionMode.BYPASS
        return ExecutionMode.SEMI_GENERATIVE

    @staticmethod
    def _assert_frozen_candidate_invariant(
        session: RoutingSession,
        attempt: Optional[AnchorExpansionAttempt] = None,
        *,
        expected_hash: Optional[str] = None,
    ) -> Optional[str]:
        """Fail closed if formal execution drifts from its frozen candidate pool."""

        snapshot = session.candidate_pool_snapshot
        if snapshot is None:
            return None
        candidate_hash = snapshot.candidate_pool_sha256
        if expected_hash is not None and candidate_hash != expected_hash:
            raise ValueError("post_freeze_candidate_pool_hash_changed")
        if session.revision != snapshot.revision:
            raise ValueError("post_freeze_candidate_revision_changed")
        snapshot_ids = [item.resource_id for item in snapshot.candidates]
        materialized_ids = [
            item.resource_id for item in session.frozen_candidate_resources
        ]
        if materialized_ids != snapshot_ids:
            raise ValueError("post_freeze_candidate_resources_changed")
        if attempt is not None and [
            item.resource_id for item in attempt.candidate_resources
        ] != snapshot_ids:
            raise ValueError("plan_compiler_candidate_set_changed")
        return candidate_hash

    async def _execute_sealed_routing_session(
        self,
        *,
        subtask: Subtask,
        context_data: str,
        artifact_type: str,
        expected: str,
        routing: Dict[str, Any],
        original_query: str = "",
        evaluation_contract_holder: Dict[str, Any] | None = None,
    ) -> tuple[bool, ExecutionResult]:
        """Execute the formal sealed-plan path through the RecoveryController."""

        session: RoutingSession = routing["routing_session"]
        frozen_result = routing.get("frozen_candidate_pool")
        retrieval_coordinator = routing.get("retrieval_coordinator")
        compiler = routing.get("executable_plan_compiler")
        resource_definitions = routing.get("resource_definitions")
        runtime_capabilities = routing.get("plan_runtime_capabilities")
        pricing_catalog = routing.get("model_pricing_catalog")
        recovery_policy = routing.get("recovery_policy")
        recovery_ledger = routing.get("recovery_ledger")
        full_generation_executor = routing.get("full_generation_executor")
        strict_plan_only = (
            isinstance(recovery_policy, RecoveryPolicy)
            and recovery_policy.sealed_runtime_mode == "strict_plan_only"
        )
        resource_index = routing.get("resource_index") or {}
        if (
            frozen_result is None
            or compiler is None
            or not isinstance(resource_definitions, Mapping)
            or runtime_capabilities is None
            or pricing_catalog is None
            or not isinstance(recovery_policy, RecoveryPolicy)
            or not isinstance(recovery_ledger, RecoveryEventLedger)
            or (not strict_plan_only and full_generation_executor is None)
        ):
            raise RuntimeError("formal_recovery_context_incomplete")
        candidate_hash = self._assert_frozen_candidate_invariant(session)
        if candidate_hash != frozen_result.candidate_pool_snapshot.candidate_pool_sha256:
            raise RuntimeError("formal_plan_compiler_candidate_hash_mismatch")
        if retrieval_coordinator is None or not callable(
            getattr(retrieval_coordinator, "revalidate_frozen_model_liveness", None)
        ):
            raise RuntimeError("formal_model_liveness_revalidator_missing")
        refreshed_liveness = retrieval_coordinator.revalidate_frozen_model_liveness(
            frozen_result,
            cost_ledger=self.cost_ledger,
        )
        routing["runtime_model_liveness_revalidation"] = {
            "status": "verified",
            "evidence_sha256s": [
                item.evidence_sha256 for item in refreshed_liveness
            ],
            "candidate_pool_sha256": candidate_hash,
        }
        context_packet = routing.get("context_packet") or {}
        public_context = build_compiler_public_context(
            context_packet,
            allowed_upstream_task_ids=tuple(subtask.depends_on),
        )
        registry = PayloadSourceRegistry(
            subtask_id=subtask.id,
            mode="production",
            attempt_id=(
                "recovery:"
                + subtask_revision_identity_sha256(
                    frozen_result.contract_projection.revision
                )
            ),
        )
        registry.register(
            "compiler_public_context",
            origin="public_case",
            material=public_context.model_dump(mode="json"),
            default=True,
        )
        if original_query:
            registry.register(
                "original_user_task",
                origin="public_case",
                material=original_query,
                default=True,
            )
        registry.register(
            "frozen_candidate_pool",
            origin="candidate_bundle",
            material={
                "candidate_pool_sha256": candidate_hash,
                "candidate_ids": [
                    item.resource_id
                    for item in frozen_result.candidate_pool_snapshot.candidates
                ],
            },
            default=True,
        )
        registry.register(
            "resource_runtime_static",
            origin="static_framework",
            material={
                "resource_runtime_protocol": "sgar-resource-runtime-v1",
                "recovery_runtime_protocol": "sgar-recovery-runtime-v1",
            },
            default=True,
        )
        common_source_ids = registry.default_source_ids
        execution_guard = ProductionModelPayloadGuard(registry, default_source_ids=common_source_ids)

        async def execute_artifact(
            artifact: SealedPlanCompilationArtifact,
            checkpoints: Sequence[CompletedStepCheckpoint],
            checkpoint_results: Mapping[str, ExecutionResult],
        ) -> ExecutionResult:
            if artifact.status != "success" or artifact.executable_plan is None:
                raise RuntimeError("recovery_execution_requires_sealed_plan")
            source_id = f"sealed_executable_plan:{artifact.plan_revision.plan_revision}"
            execution_guard.register_source(
                source_id,
                origin="validated_plan",
                material=artifact.executable_plan.model_dump(mode="json"),
                parent_source_ids=("compiler_public_context", "frozen_candidate_pool"),
                producer={
                    "plan_revision": artifact.plan_revision.plan_revision,
                    "plan_sha256": artifact.executable_plan.plan_sha256,
                },
                default=True,
            )
            current_guard = ProductionModelPayloadGuard(
                registry, default_source_ids=(*common_source_ids, source_id))
            from .evidence_acquisition import (
                evidence_route_operations, execution_acquisition_operations, equivalent_acquisition_operations,
            )
            route_operation_ids = [step.capability_operation_id for step in artifact.executable_plan.steps]
            route_operation_ids.extend(
                tool.capability_operation_id for step in artifact.executable_plan.steps
                for tool in getattr(step.controller_session_spec, "callable_tools", ())
            )
            execution_required_operations, _ = evidence_route_operations(
                required=frozen_result.contract_projection.required_operation_kinds,
                acquisition=execution_acquisition_operations(frozen_result.contract_projection),
                acquisition_execution_required=(
                    getattr(frozen_result.contract_projection, "external_acquisition_mode", None) != "if_needed"
                ),
                selected_operation_ids=route_operation_ids,
                equivalent_operation_ids=equivalent_acquisition_operations(resource_definitions.values()),
                network_execution_operation_ids=tuple(
                    item.capability_operation_id
                    for item in (
                        *artifact.executable_plan.steps,
                        *(tool for step in artifact.executable_plan.steps
                          for tool in getattr(step.controller_session_spec, "callable_tools", ())),
                    )
                    if getattr(item, "execution_network_required", None) is True
                ),
            )
            execution = await self.execute_sealed_plan(
                subtask,
                artifact,
                session.frozen_candidate_resources,
                resource_index,
                context_data=context_data,
                input_handles=(context_packet.get("artifact_handles") or ()),
                model_payload_guard=current_guard,
                resume_checkpoints=checkpoints,
                resume_results=checkpoint_results,
                original_query=original_query,
                required_operation_kinds=execution_required_operations,
            )
            execution_guard.checks.extend(current_guard.checks)
            execution_result = execution["result"]
            if (execution_result.is_success and artifact_type == "plaintext"
                    and subtask.output_contract is not None
                    and not subtask.output_contract.produced_files):
                from .text_format_contract import normalize_declared_numeric_text
                value, realization = normalize_declared_numeric_text(
                    execution_result.output_data, self._contract_to_dict(subtask.output_contract),
                    original_request=original_query,
                )
                if realization is not None:
                    execution_result.output_data = value
                    execution_result.cost_metric["output_format_realization"] = realization
            execution_result.cost_metric["input_alignment"] = copy.deepcopy((artifact.validation_audit or {}).get("input_alignment", {}))
            if (
                execution_result.is_success
                and subtask.semantic_contract_v2 is not None
                and subtask.semantic_contract_v2.required_effect == "task_workspace_mutation"
            ):
                from .workspace_effects import audit_workspace_effect_invocation

                trace = execution_result.cost_metric.get("application_step_trace")
                effect_audit = audit_workspace_effect_invocation(
                    plan=artifact.executable_plan,
                    step_trace=trace if isinstance(trace, list) else (),
                    resource_index=resource_index,
                )
                execution_result.cost_metric["workspace_effect_invocation_audit"] = effect_audit
                if effect_audit["status"] != "invoked_successfully":
                    execution_result.is_success = False
                    execution_result.error_log = "workspace_effect_not_observed"
                    execution_result.cost_metric.update({
                        "failure_type": "workspace_effect_not_observed",
                        "failure_layer": "execution",
                        "failure_stage": "workspace_effect_acceptance",
                        "task_success": False,
                    })
            if execution_result.is_success:
                final_output = artifact.executable_plan.final_output
                final_step = next(
                    step for step in artifact.executable_plan.steps
                    if step.step_id == final_output.step_id
                )
                await self._snapshot_declared_external_outputs(
                    task_id=subtask.id, step=final_step,
                    output_contract=subtask.output_contract,
                )
                external_delivery_handles = self._external_output_handles(
                    subtask.output_contract
                )
                if external_delivery_handles:
                    await self._register_external_final_text_artifact(
                        subtask.id,
                        final_step,
                        external_delivery_handles,
                    )
                final_records = self._formal_records_for_output(
                    task_id=subtask.id,
                    step_id=final_output.step_id,
                    output_key=final_output.output_key,
                    output_contract=subtask.output_contract,
                    step=final_step,
                )
                final_record = (
                    final_records[0] if final_records else self.artifact_registry.by_step.get(
                        f"{subtask.id}:{final_output.step_id}:{final_output.output_key}"
                    )
                )
                _realize_materialized_delivery_result(execution_result, final_step, final_record)
                if final_records:
                    self._formal_final_runtime_records[subtask.id] = final_records
                required_outputs_valid, produced_status = self._formal_required_output_status(
                    task_id=subtask.id,
                    output_contract=subtask.output_contract,
                    final_artifact_type=artifact_type,
                    final_record=final_record,
                    primary_value_available=True,
                )
                execution_result.cost_metric["formal_produced_file_status"] = produced_status
                source_support_failure = None
                try:
                    from .artifact_semantics import OutputContractViolation, validate_delivery_content
                    from .source_literal_support import check_source_literal_support
                    if artifact.executable_plan is not None:
                        source_support_failure = check_source_literal_support(
                            plan=artifact.executable_plan,
                            output_contract=subtask.output_contract,
                            artifact_type=artifact_type,
                            final_answer=str(execution_result.output_data or ""),
                            step_outputs=execution_result.cost_metric.get(
                                "application_step_outputs", {}
                            ),
                        )
                        if source_support_failure is not None:
                            raise OutputContractViolation(
                                source_support_failure.failure_code
                            )
                        final_contract = _canonical_evaluation_output_contract(
                            subtask=subtask,
                            validated_final_output_contract=_validated_delivery_output_contract(
                                artifact.executable_plan),
                        )
                        from .artifact_semantics import requires_content_contract_validation
                        if requires_content_contract_validation(final_contract):
                            actual_bytes = Path(final_record.path).read_bytes() if final_record is not None and Path(final_record.path).is_file() else str(execution_result.output_data or "").encode("utf-8")
                            macro_contract = self._contract_to_dict(subtask.output_contract)
                            validation = validate_delivery_content(actual_bytes, final_contract, macro_contract)
                            execution_result.cost_metric["execution_contract_validation"] = validation
                            if not hasattr(self, "_checked_output_material"):
                                self._checked_output_material = {}
                            self._checked_output_material[subtask.id] = (
                                actual_bytes, copy.deepcopy(final_contract), validation,
                                copy.deepcopy(macro_contract))
                    explicit_delivery = (
                        self.task_invocation.final_deliverable_contract
                        if self.task_invocation is not None
                        and subtask.id == self._formal_final_task_id
                        else None
                    )
                    if explicit_delivery is not None:
                        self._validate_explicit_deliverable_machine_contract(
                            subtask_id=subtask.id,
                            contract=explicit_delivery,
                            content=str(execution_result.output_data or "").encode("utf-8"),
                            records=final_records,
                            required_outputs_valid=required_outputs_valid,
                        )
                    else:
                        self._validate_plan_output_machine_contract(
                            subtask_id=subtask.id,
                            content=str(execution_result.output_data or "").encode("utf-8"),
                            artifact_type=artifact_type,
                            extension=str(getattr(subtask, "output_extension", "") or ""),
                            records=final_records,
                            required_outputs_valid=required_outputs_valid,
                            handles_valid=bool(final_records),
                            node_output_contract=subtask.output_contract,
                        )
                except (MachineContractFailure, ArtifactV2MachineContractError, OutputContractViolation) as exc:
                    failure_code = str(getattr(exc, "failure_code", "artifact_contract_invalid"))
                    execution_result.is_success = False
                    execution_result.error_log = failure_code
                    if artifact.executable_plan is not None:
                        from .recovery_runtime import (
                            attribute_step_postcondition_failure,
                        )
                        postcondition_phase = (
                            "source_grounding"
                            if source_support_failure is not None
                            else "output_contract"
                        )
                        failed_step_id = (
                            source_support_failure.failed_step_id
                            if source_support_failure is not None
                            else artifact.executable_plan.final_output.step_id
                        )
                        attribute_step_postcondition_failure(
                            execution_result,
                            step_id=failed_step_id,
                            failure_code=failure_code,
                            phase=postcondition_phase,
                        )
                    execution_result.cost_metric.update(
                        {
                            "failure_type": failure_code,
                            "failure_layer": "research",
                            "machine_contract_evidence": (
                                exc.evidence.model_dump(mode="json")
                                if isinstance(exc, MachineContractFailure)
                                else {
                                    "protocol": "sgar-artifact-evidence-v2",
                                    "status": "fail",
                                    "failure_code": failure_code,
                                }
                            ),
                            "failure": {
                                "responsibility": "research",
                                "failure_stage": (
                                    "source_grounding"
                                    if source_support_failure is not None
                                    else "output_contract"
                                ),
                                "failure_code": failure_code,
                                "exception_type": "",
                                "retryable": False,
                                "response_received": True,
                                "message_sha256": canonical_sha256(failure_code),
                            },
                        }
                    )
                    if source_support_failure is not None:
                        execution_result.cost_metric["source_support_audit"] = {
                            "protocol": "sgar-source-literal-support-v1",
                            "status": "fail",
                            "source_step_id": source_support_failure.source_step_id,
                            "failed_step_id": source_support_failure.failed_step_id,
                            "source_body_sha256": source_support_failure.source_body_sha256,
                        }
            return execution_result

        execution_port = CallableSealedExecutionPort(execute_artifact)

        def material_view_factory(
            checkpoints: Sequence[CompletedStepCheckpoint],
        ) -> AuthorizedModelMaterialView:
            """Join only current-run authorized identities to private paths."""

            sources: list[AuthorizedMaterialSource] = []
            registered_inputs = self.artifact_registry.input_file_handles
            if self.task_invocation is not None:
                for descriptor in self.task_invocation.public_inputs:
                    handle = registered_inputs.get(descriptor.handle_id)
                    if handle is None or not handle.host_path:
                        raise AuthorizedMaterialError(
                            "authorized_public_input_handle_missing"
                        )
                    sources.append(
                        AuthorizedMaterialSource(
                            source_id=f"authorized_public_input:{descriptor.handle_id}",
                            origin="public_input",
                            logical_name=descriptor.logical_name,
                            logical_locator=descriptor.runtime_path,
                            source_path=Path(handle.host_path),
                            expected_sha256=descriptor.content_sha256,
                            expected_byte_size=descriptor.byte_size,
                            expected_kind=descriptor.path_kind,
                            extension=descriptor.extension,
                            media_type=descriptor.media_type,
                        )
                    )

            if self.context.artifact_store is not None:
                for dependency_id in subtask.depends_on:
                    manifest = self.context.committed_manifest_for(dependency_id)
                    if manifest is None:
                        continue
                    self.context.artifact_store.validate_manifest_content(manifest)
                    source_path = self.context.artifact_store.artifact_path(manifest)
                    observed_hash, observed_size, observed_kind = public_snapshot_identity(
                        source_path
                    )
                    descriptor = getattr(manifest, "artifact_v2", None)
                    sources.append(
                        AuthorizedMaterialSource(
                            source_id=(
                                "authorized_committed:"
                                + str(manifest.committed_manifest_sha256)
                            ),
                            origin="committed_dependency",
                            logical_name=str(dependency_id),
                            logical_locator=str(manifest.logical_locator),
                            source_path=source_path,
                            expected_sha256=observed_hash,
                            expected_byte_size=observed_size,
                            expected_kind=observed_kind,
                            extension=str(getattr(manifest, "extension", "") or ""),
                            media_type=str(getattr(manifest, "mime_type", "") or "application/octet-stream"),
                            descriptor=descriptor,
                        )
                    )

            seen_checkpoint_handles: set[str] = set()
            for checkpoint in checkpoints:
                allowed_hashes = set(checkpoint.artifact_hashes)
                for handle_id in checkpoint.artifact_handle_ids:
                    if handle_id in seen_checkpoint_handles:
                        continue
                    seen_checkpoint_handles.add(handle_id)
                    ok, _, _, handle = self.resolve_artifact_handle(handle_id)
                    if not ok or handle is None or not handle.host_path:
                        raise AuthorizedMaterialError(
                            "authorized_checkpoint_handle_missing"
                        )
                    source_path = Path(handle.host_path)
                    observed_hash, observed_size, observed_kind = public_snapshot_identity(
                        source_path
                    )
                    if allowed_hashes and observed_hash not in allowed_hashes:
                        raise AuthorizedMaterialError(
                            "authorized_checkpoint_hash_mismatch"
                        )
                    sources.append(
                        AuthorizedMaterialSource(
                            source_id=f"authorized_checkpoint:{checkpoint.checkpoint_sha256}:{handle_id}",
                            origin="checkpoint",
                            logical_name=handle_id,
                            logical_locator=str(handle.tool_path or handle.logical_path or handle_id),
                            source_path=source_path,
                            expected_sha256=observed_hash,
                            expected_byte_size=observed_size,
                            expected_kind=observed_kind,
                            extension=source_path.suffix.lower(),
                            media_type="application/octet-stream",
                        )
                    )
            return build_authorized_model_material_view(
                run_id=self.execution_ledger.run_id,
                revision=frozen_result.contract_projection.revision,
                sources=tuple(sources),
            )

        full_generation_port = None
        temporary_manager = None
        temporary_tool_port = None
        if not strict_plan_only:
            full_generation_port = SystemFullGenerationRecoveryPort(
                executor=full_generation_executor,
                revision=frozen_result.contract_projection.revision,
                public_context=public_context,
                candidate_pool_sha256=candidate_hash,
                contract_projection=frozen_result.contract_projection.model_dump(mode="json"),
                payload_guard=execution_guard,
                diagnostic_max_bytes=recovery_policy.diagnostic_payload_max_bytes,
                material_view_factory=material_view_factory,
            )
            # Compatibility mode alone may create a run-local temporary Tool.
            self.register_input_handles(context_packet.get("artifact_handles") or ())
            temporary_scope = self._resource_runtime_sandbox_scope()
            temporary_scope_sha256 = sandbox_scope_sha256(
                temporary_scope,
                project_root=self.project_root,
            )
            temporary_root = (
                recovery_ledger.temporary_tools_dir
                / subtask_revision_identity_sha256(
                    frozen_result.contract_projection.revision
                )
            ).resolve()
            project_root = Path(self.project_root).resolve()
            try:
                temporary_runtime_root = (
                    "/app/" + temporary_root.relative_to(project_root).as_posix()
                )
            except ValueError as exc:
                raise RuntimeError("temporary_tool_root_outside_project") from exc
            temporary_manager = TemporaryToolManager(
                project_root=project_root,
                recovery_root=temporary_root,
                recovery_runtime_root=temporary_runtime_root,
                policy=recovery_policy,
                runtime_roots=tuple(
                    item["host_path"] for item in temporary_scope["runtime_roots"]
                ),
                hidden_roots=tuple(
                    item["host_path"]
                    for item in (
                        *temporary_scope.get("hidden_roots", ()),
                        *temporary_scope.get("masked_roots", ()),
                    )
                ),
            )
        compilation_port = SealedCompilerRecoveryPort(
            run_id=self.execution_ledger.run_id,
            compiler=compiler,
            candidate_pool=frozen_result,
            public_context=public_context,
            resource_definitions=resource_definitions,
            pricing_catalog=pricing_catalog,
            runtime_capabilities=runtime_capabilities,
            payload_guard=execution_guard,
            temporary_tool_manager=temporary_manager,
            resource_index=resource_index,
            original_user_query=original_query,
        )

        def register_generated_artifact(
            step_id: str,
            output_key: str,
            path: Path,
            handle: ArtifactHandle,
        ) -> None:
            self.artifact_registry.by_step[
                f"{subtask.id}:{step_id}:{output_key}"
            ] = RuntimeArtifactRecord(
                path=str(path),
                artifact_type=handle.artifact_type,
                origin="temporary_tool",
                metadata={
                    "tool_path": handle.tool_path,
                    "handle_id": handle.handle_id,
                    "ephemeral": True,
                },
            )

        if not strict_plan_only:
            temporary_tool_port = GenericTemporaryToolRecoveryPort(
                manager=temporary_manager,
                generator_transport=full_generation_executor.transport,
                cost_ledger=self.cost_ledger,
                pricing_catalog=pricing_catalog,
                resource_definitions=resource_definitions,
                resource_index=resource_index,
                payload_guard=execution_guard,
                execution_ledger=self.execution_ledger,
                recovery_ledger=recovery_ledger,
                contract_projection=frozen_result.contract_projection.model_dump(mode="json"),
                sandbox_scope_sha256=temporary_scope_sha256,
                register_generated_artifact=register_generated_artifact,
                candidate_pool=frozen_result,
            )
        controller = RecoveryController(
            run_id=self.execution_ledger.run_id,
            policy=recovery_policy,
            ledger=recovery_ledger,
            compilation_port=compilation_port,
            execution_port=execution_port,
            full_generation_port=full_generation_port,
            temporary_tool_port=temporary_tool_port,
        )
        terminal = await controller.execute_subtask(
            subtask=subtask,
            routing_session=session,
            frozen_candidate_pool=frozen_result,
            compiler_context=public_context,
            resource_definitions=resource_definitions,
            runtime_capabilities=runtime_capabilities,
            pricing_catalog=pricing_catalog,
            execution_port=execution_port,
        )
        result = terminal.execution_result
        final_artifact = terminal.final_plan_artifact
        routing["recovery"] = {
            "status": terminal.status,
            "model_response_success": terminal.model_response_success,
            "artifact_ready_for_evaluation": terminal.artifact_ready_for_evaluation,
            "evaluation_eligible": terminal.evaluation_eligible,
            "adaptation_attempts": terminal.adaptation_attempts,
            "full_generation_attempts": terminal.full_generation_attempts,
            "checkpoint_reused_count": terminal.checkpoint_reused_count,
            "plan_artifact_sha256s": list(terminal.plan_artifact_sha256s),
            "failure_evidence_sha256s": list(terminal.failure_evidence_sha256s),
            "temporary_tool_artifact_sha256s": list(
                terminal.temporary_tool_artifact_sha256s
            ),
            "recovery_operation_sha256": (
                terminal.operation_ref.operation_sha256
                if terminal.operation_ref is not None
                else None
            ),
            "compiler_payload_checks": {
                str(key): list(value)
                for key, value in compilation_port.payload_checks.items()
            },
            "primary_failure": (
                terminal.primary_failure.model_dump(mode="json")
                if terminal.primary_failure is not None
                else None
            ),
            "terminal_failure": (
                terminal.terminal_failure.model_dump(mode="json")
                if terminal.terminal_failure is not None
                else None
            ),
            "recovery_outcome": terminal.recovery_outcome,
            "causal_chain": list(terminal.causal_chain),
        }
        routing["plan_compilation"] = {
            "status": (
                final_artifact.status if final_artifact is not None else "full_generation"
            ),
            "artifact_sha256": (
                final_artifact.artifact_sha256 if final_artifact is not None else None
            ),
            "candidate_pool_sha256": candidate_hash,
            "compiler_input_sha256": (
                final_artifact.compiler_input_sha256 if final_artifact is not None else None
            ),
            "accounting_operation_id": (
                final_artifact.accounting_operation_id if final_artifact is not None else None
            ),
            "transport_attempts": (
                len(final_artifact.transport_attempts) if final_artifact is not None else 0
            ),
        }

        if terminal.status != "evaluating" or not terminal.evaluation_eligible:
            result.cost_metric.update(
                {
                    "candidate_pool_sha256": candidate_hash,
                    "recovery_status": terminal.status,
                    "recovery_adaptation_attempts": terminal.adaptation_attempts,
                    "recovery_full_generation_attempts": terminal.full_generation_attempts,
                    "model_response_success": terminal.model_response_success,
                    "artifact_ready_for_evaluation": terminal.artifact_ready_for_evaluation,
                    "evaluation_eligible": terminal.evaluation_eligible,
                    "model_payload_checks": list(execution_guard.checks),
                }
            )
            session.fallback_used = False
            return False, result

        validated_final_output_contract: StepOutputContract | None = None
        validation_step = None
        if final_artifact is not None and final_artifact.executable_plan is not None:
            final_output = final_artifact.executable_plan.final_output
            final_steps = tuple(
                step
                for step in final_artifact.executable_plan.steps
                if step.step_id == final_output.step_id
                and step.output_key == final_output.output_key
            )
            if len(final_steps) != 1:
                raise RuntimeError("evaluation_final_output_contract_identity_missing")
            validated_final_output_contract = _validated_delivery_output_contract(
                final_artifact.executable_plan
            )
            validation_step = final_steps[0]
        canonical_evaluation_contract = _canonical_evaluation_output_contract(
            subtask=subtask,
            validated_final_output_contract=validated_final_output_contract,
        )
        if evaluation_contract_holder is not None:
            evaluation_contract_holder.clear()
            evaluation_contract_holder["contract"] = canonical_evaluation_contract
            evaluation_contract_holder["validation_step"] = validation_step

        def accounting_operation_ids(value: Any) -> set[str]:
            collected: set[str] = set()
            if isinstance(value, Mapping):
                for key, child in value.items():
                    if str(key) in {
                        "model_accounting_reference",
                        "accounting_operation_id",
                        "usage_reference",
                    } and isinstance(child, str) and child:
                        collected.add(child)
                    collected.update(accounting_operation_ids(child))
            elif isinstance(value, (list, tuple)):
                for child in value:
                    collected.update(accounting_operation_ids(child))
            return collected

        actual_cost_operations = tuple(
            sorted(accounting_operation_ids(result.cost_metric))
        )
        routing["plan_compilation"]["execution_accounting_operation_ids"] = list(
            actual_cost_operations
        )
        result.cost_metric.update(
            {
                "plan_compilation_artifact_sha256": (
                    final_artifact.artifact_sha256 if final_artifact is not None else None
                ),
                "candidate_pool_sha256": candidate_hash,
                "validated_plan_sha256": (
                    final_artifact.executable_plan.plan_sha256
                    if final_artifact is not None and final_artifact.executable_plan is not None
                    else None
                ),
                "lowered_plan_semantic_sha256": (
                    final_artifact.lowered_plan_semantic_sha256
                    if final_artifact is not None
                    else None
                ),
                "executed_plan_sha256": (
                    final_artifact.executable_plan.plan_sha256
                    if final_artifact is not None and final_artifact.executable_plan is not None
                    else None
                ),
                "execution_accounting_operation_ids": list(actual_cost_operations),
                "model_payload_checks": list(execution_guard.checks),
                "recovery_status": terminal.status,
                "recovery_adaptation_attempts": terminal.adaptation_attempts,
                "recovery_full_generation_attempts": terminal.full_generation_attempts,
                "model_response_success": terminal.model_response_success,
                "artifact_ready_for_evaluation": terminal.artifact_ready_for_evaluation,
                "evaluation_eligible": terminal.evaluation_eligible,
            }
        )
        if result.is_success:
            execution_guard.register_source(
                "sealed_plan_final_artifact",
                origin="current_run_step_output",
                material=result.output_data,
                parent_source_ids=tuple(dict.fromkeys((*common_source_ids,
                    *((f"sealed_executable_plan:{final_artifact.plan_revision.plan_revision}",) if final_artifact is not None else ())))),
                producer={
                    "step_id": (
                        final_artifact.executable_plan.final_output.step_id
                        if final_artifact is not None and final_artifact.executable_plan is not None
                        else "system_full_generation"
                    ),
                    "output_key": (
                        final_artifact.executable_plan.final_output.output_key
                        if final_artifact is not None and final_artifact.executable_plan is not None
                        else "final_artifact"
                    ),
                    "resource_id": (
                        next(
                            step.resource_id
                            for step in final_artifact.executable_plan.steps
                            if step.step_id == final_artifact.executable_plan.final_output.step_id
                        )
                        if final_artifact is not None and final_artifact.executable_plan is not None
                        else "formal_no_plan_resource"
                    ),
                },
                default=True,
            )
        if result.is_success:
            try:
                required_outputs_valid = True
                if "formal_produced_file_status" not in result.cost_metric:
                    required_outputs_valid, produced_status = self._formal_required_output_status(
                        task_id=subtask.id,
                        output_contract=subtask.output_contract,
                        final_artifact_type=artifact_type,
                        final_record=None,
                        primary_value_available=True,
                    )
                    result.cost_metric["formal_produced_file_status"] = produced_status
                else:
                    required_outputs_valid = all(
                        not bool(item.get("required", True))
                        or item.get("status") == "present"
                        for item in result.cost_metric.get("formal_produced_file_status", [])
                        if isinstance(item, Mapping)
                    )
                explicit_delivery = (
                    self.task_invocation.final_deliverable_contract
                    if self.task_invocation is not None
                    and subtask.id == self._formal_final_task_id
                    else None
                )
                if explicit_delivery is not None:
                    self._validate_explicit_deliverable_machine_contract(
                        subtask_id=subtask.id,
                        contract=explicit_delivery,
                        content=str(result.output_data or "").encode("utf-8"),
                        records=self._formal_final_runtime_records.get(subtask.id, ()),
                        required_outputs_valid=required_outputs_valid,
                    )
                else:
                    self._validate_plan_output_machine_contract(
                        subtask_id=subtask.id,
                        content=str(result.output_data or "").encode("utf-8"),
                        artifact_type=artifact_type,
                        extension=str(getattr(subtask, "output_extension", "") or ""),
                        records=self._formal_final_runtime_records.get(subtask.id, ()),
                        required_outputs_valid=required_outputs_valid,
                        node_output_contract=subtask.output_contract,
                    )
            except (MachineContractFailure, ArtifactV2MachineContractError) as exc:
                failure_code = str(getattr(exc, "failure_code", "artifact_contract_invalid"))
                result.is_success = False
                result.error_log = failure_code
                result.cost_metric.update(
                    {
                        "failure_type": failure_code,
                        "failure_layer": "research",
                        "machine_contract_evidence": (
                            exc.evidence.model_dump(mode="json")
                            if isinstance(exc, MachineContractFailure)
                            else {
                                "protocol": "sgar-artifact-evidence-v2",
                                "status": "fail",
                                "failure_code": failure_code,
                            }
                        ),
                    }
                )
        # Stage 4B owns semantic evaluation after immutable staging.  At this
        # boundary only execution and machine-contract success are considered;
        # Evaluator feedback can never re-enter Recovery.
        passed = bool(result.is_success)
        failure_type = str(result.cost_metric.get("failure_type") or "execution_failed")
        failure_reason = str(result.error_log or failure_type)
        result.cost_metric["model_payload_checks"] = list(execution_guard.checks)
        result.cost_metric["executability"] = "passed" if result.is_success else "failed"
        result.cost_metric["task_success"] = bool(passed)
        if not passed:
            result.cost_metric["failure_type"] = failure_type
            result.cost_metric.setdefault(
                "failure_layer",
                self._failure_layer_for_type(failure_type),
            )
            session.fallback_used = terminal.full_generation_attempts > 0
            return False, result
        selected: list[TypedResourceRef] = []
        if final_artifact is not None and final_artifact.executable_plan is not None:
            selected_by_id = {
                item.resource_id: item for item in session.frozen_candidate_resources
            }
            selected = [
                selected_by_id[item]
                for item in final_artifact.executable_plan.selected_resource_ids
            ]
        actual_mode = (
            self._actual_mode_for_selection(selected)
            if selected
            else ExecutionMode.FULL_GENERATIVE
        )
        session.policy_expected_mode = actual_mode
        session.actual_runtime_mode = actual_mode
        session.final_mode = actual_mode
        session.final_selected_resources = selected
        session.fallback_used = terminal.full_generation_attempts > 0
        session.final_training_label = None
        return True, result

    async def _execute_routing_session(
        self,
        subtask: Subtask,
        context_data: str,
        artifact_type: str,
        expected: str,
        routing: Dict[str, Any],
        original_query: str = "",
        evaluation_contract_holder: Dict[str, Any] | None = None,
    ) -> tuple[bool, ExecutionResult | None]:
        router_runtime = routing.get("router_runtime")
        session: RoutingSession = routing.get("routing_session")
        library = routing.get("library", [])
        resource_index = routing.get("resource_index", {})
        if router_runtime is None or session is None:
            return False, None

        if routing.get("executable_plan_compiler") is not None:
            return await self._execute_sealed_routing_session(
                subtask=subtask,
                context_data=context_data,
                artifact_type=artifact_type,
                expected=expected,
                routing=routing,
                original_query=original_query,
                evaluation_contract_holder=evaluation_contract_holder,
            )

        frozen_candidate_hash = self._assert_frozen_candidate_invariant(session)
        last_failure = ""
        context_packet = routing.get("context_packet") or {}
        full_generative_fallback_attempted = bool(getattr(session, "fallback_used", False))
        best_artifact_candidate: Optional[ExecutionResult] = None
        session.execution_strictness = self.execution_strictness
        while True:
            attempt = router_runtime.build_attempt(
                session,
                subtask,
                library,
                context_packet=context_packet,
            )
            self._assert_frozen_candidate_invariant(
                session,
                attempt,
                expected_hash=frozen_candidate_hash,
            )
            if attempt is None:
                attempt = router_runtime.select_best_observed_bundle(session)
                if attempt is None:
                    if not self.allow_plan_recovery:
                        result = self._structured_failure_result(
                            "bundle_insufficient",
                            last_failure or "Anchor expansion exhausted without an executable plan.",
                        )
                        result.cost_metric["fallback_skipped_reason"] = "experiment_no_hidden_recovery"
                        session.fallback_used = False
                        return False, result
                    allowed, guard_reason = self._full_generative_fallback_guard(full_generative_fallback_attempted)
                    if not allowed:
                        result = self._budget_guarded_failure_result(guard_reason)
                        session.fallback_used = False
                        return False, result
                    full_generative_fallback_attempted = True
                    result = await self._execute_full_generative(
                        subtask.description,
                        context_data,
                        artifact_type,
                        expected_output=expected,
                        feedback=last_failure or "Anchor expansion exhausted.",
                        subtask_id=subtask.id,
                    )
                    session.final_mode = ExecutionMode.FULL_GENERATIVE
                    session.actual_runtime_mode = ExecutionMode.FULL_GENERATIVE
                    session.fallback_used = True
                    return await self._validate_execution_result_preserving_best(
                        subtask,
                        result,
                        artifact_type,
                        expected,
                        context_data,
                        best_artifact_candidate,
                        fallback_stage="anchor_exhausted_full_generation",
                    )
                logger.warning(
                    "[Router] Anchor expansion exhausted for {}; executing best observed low-advantage bundle before full generation.",
                    session.subtask_id,
                )
                attempt.failure_type = "bundle_low_advantage_observed"

            if attempt.failure_type in {
                "candidate_bundle_not_expanded",
                "policy_invalid_output",
                "policy_invalid_plan",
                "policy_hallucinated_resource",
                "bundle_insufficient",
                "bundle_low_advantage",
                "provider_connection_error",
                "provider_stream_error",
                "provider_rate_limit",
                "provider_auth_error",
                "model_unavailable",
            }:
                last_failure = f"{attempt.failure_type}: {attempt.failure_reason}"
                if not self.allow_plan_recovery:
                    result = self._structured_failure_result(
                        attempt.failure_type,
                        attempt.failure_reason or attempt.failure_type,
                    )
                    result.cost_metric["fallback_skipped_reason"] = "experiment_no_hidden_recovery"
                    session.fallback_used = False
                    return False, result
                if router_runtime.has_remaining_attempts(session):
                    continue
                if self._is_provider_execution_failure(attempt.failure_type):
                    result = self._structured_failure_result(attempt.failure_type, attempt.failure_reason or "")
                    result.cost_metric["fallback_skipped_reason"] = "provider_infrastructure_failure"
                    session.fallback_used = False
                    return False, result
                allowed, guard_reason = self._full_generative_fallback_guard(full_generative_fallback_attempted)
                if not allowed:
                    result = self._budget_guarded_failure_result(guard_reason)
                    session.fallback_used = False
                    return False, result
                full_generative_fallback_attempted = True
                result = await self._execute_full_generative(
                    subtask.description,
                    context_data,
                    artifact_type,
                    expected_output=expected,
                    feedback=last_failure,
                    subtask_id=subtask.id,
                )
                session.final_mode = ExecutionMode.FULL_GENERATIVE
                session.actual_runtime_mode = ExecutionMode.FULL_GENERATIVE
                session.fallback_used = True
                return await self._validate_execution_result_preserving_best(
                    subtask,
                    result,
                    artifact_type,
                    expected,
                    context_data,
                    best_artifact_candidate,
                    fallback_stage="attempt_failure_full_generation",
                )

            selected = attempt.bundle_decision.selected_resources if attempt.bundle_decision else []
            application_plan = (
                attempt.bundle_decision.application_plan
                if attempt.bundle_decision
                else None
            )
            if (
                application_plan is None
                and getattr(self, "resource_runtime", None) is None
            ):
                application_plan = self._synthetic_plan_from_selected_resources(
                    selected,
                    artifact_type,
                    expected,
                )
                if application_plan is not None:
                    attempt.failure_reason = (
                        (attempt.failure_reason + " | ") if attempt.failure_reason else ""
                    ) + "Legacy selected-resource path converted to synthetic ResourceApplicationPlan."
            if attempt.bundle_decision is not None:
                session.policy_expected_mode = attempt.bundle_decision.expected_execution_mode
            if application_plan is not None:
                if getattr(self, "resource_runtime", None) is not None:
                    self._active_sandbox_scope = self._resource_runtime_sandbox_scope()
                    self._active_runtime_path_map = RuntimePathMap.from_scope(
                        self._active_sandbox_scope
                    )
                    self._active_allow_semantic_normalization = False
                else:
                    self.normalize_application_plan_semantics(
                        application_plan,
                        attempt.candidate_resources,
                        selected,
                        resource_index,
                        subtask,
                    )
                self._append_trace(
                    "application_plan_trace",
                    {
                        "subtask_id": subtask.id,
                        "attempt_index": attempt.attempt_index,
                        "candidate_pool_sha256": frozen_candidate_hash,
                        "typed_candidate_counts": attempt.typed_candidate_counts,
                        "candidate_resource_cards": attempt.candidate_resource_cards,
                        "context_packet": attempt.context_packet,
                        "plan": application_plan.model_dump(mode="json"),
                    },
                )
            if application_plan is not None:
                ok, failure_type, failure_reason, resolved_bindings = self.preflight_application_plan(
                    application_plan,
                    attempt.candidate_resources,
                    selected,
                    resource_index,
                    subtask,
                    context_data,
                    allow_semantic_normalization=(
                        getattr(self, "resource_runtime", None) is None
                    ),
                    formal_resource_runtime=(
                        getattr(self, "resource_runtime", None) is not None
                    ),
                )
                self._append_trace(
                    "preflight_trace",
                    {
                        "subtask_id": subtask.id,
                        "attempt_index": attempt.attempt_index,
                        "candidate_pool_sha256": frozen_candidate_hash,
                        "ok": ok,
                        "failure_type": failure_type,
                        "failure_reason": failure_reason,
                        "resolved_bindings": resolved_bindings,
                    },
                )
                if not ok:
                    router_runtime.record_attempt_failure(
                        session,
                        attempt,
                        failure_type=failure_type,
                        failure_reason=failure_reason,
                    )
                    last_failure = f"{failure_type}: {failure_reason}"
                    if not self.allow_plan_recovery:
                        result = self._structured_failure_result(failure_type, failure_reason)
                        result.cost_metric["fallback_skipped_reason"] = "experiment_no_hidden_recovery"
                        session.fallback_used = False
                        return False, result
                    if router_runtime.has_remaining_attempts(session):
                        continue
                    if self._is_deterministic_execution_failure(failure_type):
                        result = self._structured_failure_result(failure_type, failure_reason)
                        session.fallback_used = False
                        return False, result
                    allowed, guard_reason = self._full_generative_fallback_guard(full_generative_fallback_attempted)
                    if not allowed:
                        result = self._budget_guarded_failure_result(guard_reason)
                        session.fallback_used = False
                        return False, result
                    full_generative_fallback_attempted = True
                    result = await self._execute_full_generative(
                        subtask.description,
                        context_data,
                        artifact_type,
                        expected_output=expected,
                        feedback=last_failure,
                        subtask_id=subtask.id,
                    )
                    session.final_mode = ExecutionMode.FULL_GENERATIVE
                    session.actual_runtime_mode = ExecutionMode.FULL_GENERATIVE
                    session.fallback_used = True
                    return await self._validate_execution_result_preserving_best(
                        subtask,
                        result,
                        artifact_type,
                        expected,
                        context_data,
                        best_artifact_candidate,
                        fallback_stage="preflight_failure_full_generation",
                    )

                result = await self._execute_resource_dag(
                    subtask.id,
                    application_plan,
                    selected,
                    subtask.description,
                    context_data,
                    artifact_type,
                    expected,
                    resource_index,
                    resolved_bindings,
                    task_output_contract=subtask.output_contract,
                    resource_execution_context=(
                        ResourceExecutionContext(
                            run_id=self.execution_ledger.run_id,
                            graph_revision=session.revision.graph_revision,
                            subtask_id=session.revision.subtask_id,
                            subtask_revision=session.revision.subtask_revision,
                            candidate_pool_sha256=frozen_candidate_hash,
                            candidate_resource_ids=tuple(
                                item.resource_id
                                for item in session.candidate_pool_snapshot.candidates
                            ),
                            selected_resource_ids=tuple(
                                item.resource_id for item in selected
                            ),
                            plan_sha256=canonical_sha256(
                                application_plan.model_dump(mode="json")
                            ),
                            step_id="plan",
                            attempt=max(1, int(attempt.attempt_index) + 1),
                            sandbox_scope_sha256=sandbox_scope_sha256(
                                getattr(self, "_active_sandbox_scope", None),
                                project_root=self.project_root,
                            ),
                        )
                        if getattr(self, "resource_runtime", None) is not None
                        and self.execution_ledger is not None
                        and session.revision is not None
                        and session.candidate_pool_snapshot is not None
                        else None
                    ),
                )
            else:
                if not self.allow_plan_recovery:
                    result = self._structured_failure_result(
                        "policy_invalid_plan",
                        "Plan Compiler did not provide an executable ResourceApplicationPlan.",
                    )
                    result.cost_metric["fallback_skipped_reason"] = "experiment_no_hidden_recovery"
                    session.fallback_used = False
                    return False, result
                allowed, guard_reason = self._full_generative_fallback_guard(full_generative_fallback_attempted)
                if not allowed:
                    result = self._budget_guarded_failure_result(guard_reason)
                    session.fallback_used = False
                    return False, result
                full_generative_fallback_attempted = True
                result = await self._execute_full_generative(
                    subtask.description,
                    context_data,
                    artifact_type,
                    expected_output=expected,
                    feedback="Selected bundle could not be converted into a ResourceApplicationPlan.",
                    subtask_id=subtask.id,
                )
                session.final_mode = ExecutionMode.FULL_GENERATIVE
                session.actual_runtime_mode = ExecutionMode.FULL_GENERATIVE
                session.fallback_used = True
                return await self._validate_execution_result_preserving_best(
                    subtask,
                    result,
                    artifact_type,
                    expected,
                    context_data,
                    best_artifact_candidate,
                    fallback_stage="attempt_failure_full_generation",
                )
            if isinstance(result.cost_metric.get("application_step_trace"), list):
                attempt.execution_step_trace = result.cost_metric["application_step_trace"]
            self._assert_frozen_candidate_invariant(
                session,
                attempt,
                expected_hash=frozen_candidate_hash,
            )
            self._append_trace(
                "execution_trace",
                {
                    "subtask_id": subtask.id,
                    "attempt_index": attempt.attempt_index,
                    "candidate_pool_sha256": frozen_candidate_hash,
                    "selected_resources": [ref.model_dump(mode="json") for ref in selected],
                    "is_success": result.is_success,
                    "failure_type": result.cost_metric.get("failure_type"),
                    "final_output_from": result.cost_metric.get("final_output_from"),
                    "application_step_outputs": result.cost_metric.get(
                        "application_step_outputs",
                        {},
                    ),
                    "cost_metric": {
                        key: value
                        for key, value in result.cost_metric.items()
                        if key not in {"application_step_outputs", "evaluation_result"}
                    },
                },
            )
            if self._is_best_artifact_candidate(result, artifact_type):
                best_artifact_candidate = result
                result.cost_metric["best_artifact_candidate"] = {
                    "subtask_id": subtask.id,
                    "attempt_index": attempt.attempt_index,
                    "candidate_pool_sha256": frozen_candidate_hash,
                    "chars": len(result.output_data or ""),
                    "artifact_type": artifact_type,
                    "source": "application_plan",
                }
            passed, failure_type, failure_reason = await self._classify_execution_result(
                subtask,
                result,
                artifact_type,
                expected,
                context_data,
            )
            executability = "passed" if result.is_success else "failed"
            result.cost_metric["executability"] = executability
            result.cost_metric["task_success"] = bool(passed)
            if not passed:
                result.cost_metric["failure_type"] = failure_type
                existing_layer = str(result.cost_metric.get("failure_layer") or "")
                result.cost_metric["failure_layer"] = (
                    existing_layer
                    if existing_layer not in {"", "none"}
                    else self._failure_layer_for_type(failure_type)
                )
            else:
                result.cost_metric["failure_layer"] = "none"
            self._append_trace(
                "outcome_trace",
                {
                    "subtask_id": subtask.id,
                    "attempt_index": attempt.attempt_index,
                    "candidate_pool_sha256": frozen_candidate_hash,
                    "executability": executability,
                    "task_success": bool(passed),
                    "failure_type": failure_type or None,
                    "failure_layer": result.cost_metric.get("failure_layer"),
                    "failure_reason": failure_reason or None,
                    "evaluation_result": result.cost_metric.get("evaluation_result"),
                },
            )
            if isinstance(result.cost_metric.get("evaluation_result"), dict):
                attempt.evaluation_result = EvaluationResult.model_validate(
                    result.cost_metric["evaluation_result"]
                )
            self._update_resource_utility(selected, passed)
            if passed:
                policy_mode = attempt.bundle_decision.expected_execution_mode if attempt.bundle_decision else ExecutionMode.SEMI_GENERATIVE
                actual_mode = (
                    ExecutionMode.FULL_GENERATIVE
                    if result.cost_metric.get("fallback_used")
                    else self._actual_mode_for_selection(selected)
                )
                session.policy_expected_mode = policy_mode
                session.actual_runtime_mode = actual_mode
                session.final_mode = actual_mode
                session.fallback_used = actual_mode == ExecutionMode.FULL_GENERATIVE
                session.final_selected_resources = selected
                session.final_training_label = (
                    attempt.evaluation_result.training_label
                    if attempt.evaluation_result is not None
                    else TrainingLabel.GOOD_CASE
                )
                return True, result

            if application_plan is not None and self.max_same_bundle_repair_attempts > 0:
                repair_result = await self._attempt_same_bundle_repair(
                    application_plan,
                    selected,
                    subtask,
                    context_data,
                    artifact_type,
                    expected,
                    resource_index,
                    result,
                    failure_type,
                    failure_reason,
                )
                if repair_result is not None:
                    attempt.repair_attempted = True
                    attempt.repair_reason = f"{failure_type}: {failure_reason}"
                    repair_passed, repair_failure_type, repair_failure_reason = await self._classify_execution_result(
                        subtask,
                        repair_result,
                        artifact_type,
                        expected,
                        context_data,
                    )
                    if isinstance(repair_result.cost_metric.get("evaluation_result"), dict):
                        attempt.repair_evaluation_result = EvaluationResult.model_validate(
                            repair_result.cost_metric["evaluation_result"]
                        )
                    if isinstance(repair_result.cost_metric.get("application_step_trace"), list):
                        attempt.execution_step_trace = repair_result.cost_metric["application_step_trace"]
                    self._append_trace(
                        "repair_trace",
                        {
                            "subtask_id": subtask.id,
                            "attempt_index": attempt.attempt_index,
                            "repair_success": repair_passed,
                            "failure_type": failure_type,
                            "failure_reason": failure_reason,
                            "repair_failure_type": repair_failure_type,
                            "repair_failure_reason": repair_failure_reason,
                            "evaluation_result": (
                                attempt.repair_evaluation_result.model_dump(mode="json")
                                if attempt.repair_evaluation_result is not None
                                else None
                            ),
                        },
                    )
                    if repair_passed:
                        attempt.repair_success = True
                        final_step = next(
                            (step for step in application_plan.steps if step.output_key == application_plan.final_output_from),
                            None,
                        )
                        if final_step is not None and application_plan.final_output_from:
                            ok_m, failure_type_m, reason_m, record_m = self._materialize_step_output(
                                subtask.id,
                                final_step,
                                application_plan.final_output_from,
                                repair_result.output_data,
                                artifact_type,
                                preferred_name=f"{subtask.id}_{application_plan.final_output_from}_repair",
                            )
                            if ok_m and record_m is not None:
                                repair_result.cost_metric["repair_materialized_artifact"] = {
                                    "runtime_path": self._to_tool_path(record_m.path),
                                    "artifact_type": record_m.artifact_type,
                                }
                                step_outputs = repair_result.cost_metric.get("application_step_outputs")
                                if isinstance(step_outputs, dict):
                                    step_outputs[application_plan.final_output_from] = repair_result.output_data
                                else:
                                    repair_result.cost_metric["application_step_outputs"] = {
                                        application_plan.final_output_from: repair_result.output_data
                                    }
                            else:
                                repair_result.cost_metric["repair_materialize_warning"] = {
                                    "failure_type": failure_type_m,
                                    "reason": reason_m,
                                }
                        policy_mode = attempt.bundle_decision.expected_execution_mode if attempt.bundle_decision else ExecutionMode.SEMI_GENERATIVE
                        actual_mode = (
                            ExecutionMode.FULL_GENERATIVE
                            if repair_result.cost_metric.get("fallback_used")
                            else self._actual_mode_for_selection(selected)
                        )
                        session.policy_expected_mode = policy_mode
                        session.actual_runtime_mode = actual_mode
                        session.final_mode = actual_mode
                        session.fallback_used = actual_mode == ExecutionMode.FULL_GENERATIVE
                        session.final_selected_resources = selected
                        session.final_training_label = (
                            attempt.repair_evaluation_result.training_label
                            if attempt.repair_evaluation_result is not None
                            else TrainingLabel.GOOD_CASE
                        )
                        logger.success("[Repair] Same-bundle repair passed for {}", subtask.id)
                        return True, repair_result
                    attempt.repair_failure_type = repair_failure_type
                    attempt.repair_reason = f"{repair_failure_type}: {repair_failure_reason}"
                    failure_type = repair_failure_type
                    failure_reason = repair_failure_reason
                    result = repair_result

            router_runtime.block_infra_failure(
                session,
                attempt,
                selected,
                failure_type,
                result.cost_metric,
            )

            router_runtime.record_attempt_failure(
                session,
                attempt,
                failure_type=failure_type,
                failure_reason=failure_reason,
            )
            last_failure = f"{failure_type}: {failure_reason}"
            result.cost_metric["failure_type"] = failure_type
            existing_layer = str(result.cost_metric.get("failure_layer") or "")
            result.cost_metric["failure_layer"] = (
                existing_layer
                if existing_layer not in {"", "none"}
                else self._failure_layer_for_type(failure_type)
            )
            if not self.allow_plan_recovery:
                result.cost_metric["fallback_skipped_reason"] = "experiment_no_hidden_recovery"
                session.fallback_used = False
                return False, result
            if router_runtime.has_remaining_attempts(session):
                continue
            if self._is_deterministic_execution_failure(failure_type):
                result = self._structured_failure_result(failure_type, failure_reason)
                session.fallback_used = False
                return False, result
            if self._is_provider_execution_failure(failure_type):
                result = self._structured_failure_result(failure_type, failure_reason)
                result.cost_metric["fallback_skipped_reason"] = "provider_infrastructure_failure"
                session.fallback_used = False
                return False, result

            allowed, guard_reason = self._full_generative_fallback_guard(full_generative_fallback_attempted)
            if not allowed:
                result = self._budget_guarded_failure_result(guard_reason)
                session.fallback_used = False
                return False, result
            full_generative_fallback_attempted = True
            result = await self._execute_full_generative(
                subtask.description,
                context_data,
                artifact_type,
                expected_output=expected,
                feedback=last_failure,
                subtask_id=subtask.id,
            )
            session.final_mode = ExecutionMode.FULL_GENERATIVE
            session.actual_runtime_mode = ExecutionMode.FULL_GENERATIVE
            session.fallback_used = True
            return await self._validate_execution_result_preserving_best(
                subtask,
                result,
                artifact_type,
                expected,
                context_data,
                best_artifact_candidate,
                fallback_stage="execution_failure_full_generation",
            )

    def _update_resource_utility(self, selected: list, success: bool) -> None:
        """Record runtime utility observations without mutating source resource manifests."""
        if not selected:
            return
        self._append_trace(
            "runtime_utility_observation",
            {
                "success": success,
                "selected_resources": [
                    {
                        "resource_id": getattr(ref, "resource_id", ""),
                        "resource_type": getattr(getattr(ref, "resource_type", None), "value", None),
                    }
                    for ref in selected
                ],
                "manifest_update_skipped": True,
            },
        )
        return
        # Build resource_id → resource_type map for this attempt

    def _classify_runtime_failure(self, result: ExecutionResult) -> tuple[str, str]:
        """Map executor/runtime failures into training-safe failure categories."""
        if bool(getattr(self, "_formal_execution_active", False)):
            raise RuntimeError("formal_error_string_failure_classifier_forbidden")
        metric_failure = result.cost_metric.get("failure_type")
        if metric_failure:
            return str(metric_failure), result.error_log or str(metric_failure)

        error_log = result.error_log or "Executor returned failure."
        lowered = error_log.lower()
        if "capability_unsupported" in lowered or "does not support feature" in lowered:
            return "capability_unsupported", error_log
        if "model_not_found" in lowered:
            return "model_unavailable", error_log
        if (
            "docker execution exceeded" in lowered
            or ("timeouterror" in lowered and "docker" in lowered)
            or ("tool_runtime_timeout" in lowered)
        ):
            return "tool_runtime_timeout", error_log
        if (
            "apiconnectionerror" in lowered
            or "remoteprotocolerror" in lowered
            or "server disconnected" in lowered
            or "stream error" in lowered
            or "peer closed connection" in lowered
            or "incomplete chunked" in lowered
            or "without sending complete message body" in lowered
            or "internal_error" in lowered
            or "http2 protocol error" in lowered
            or "connection" in lowered
            or "timeout" in lowered
        ):
            if "stream" in lowered or "chunked" in lowered or "peer closed" in lowered:
                return "provider_stream_error", error_log
            return "provider_connection_error", error_log
        if "invalid agent base_model" in lowered or "agent_missing_base_model" in lowered:
            return "agent_missing_base_model", error_log
        if "tool_missing_required_input" in lowered:
            return "tool_missing_required_input", error_log
        if "usage: python pytest_runner.py <target_path>" in lowered:
            return "tool_missing_required_input", error_log
        if "/app/e:" in lowered or "\\app\\e:" in lowered or "outside workspace" in lowered:
            return "tool_path_mapping_error", error_log
        if "validation_target_missing" in lowered:
            return "validation_target_missing", error_log
        if "validation_target_ambiguous" in lowered:
            return "validation_target_ambiguous", error_log
        if "unsafe_validation_target" in lowered or "target path is outside" in lowered:
            return "unsafe_validation_target", error_log
        if "wrong_validation_target" in lowered:
            return "wrong_validation_target", error_log
        if "runner_cwd_error" in lowered or ("cwd" in lowered and "workspace" in lowered):
            return "runner_cwd_error", error_log
        if "input_file_mount_error" in lowered or ("no such file or directory" in lowered and "bench_cases" in lowered):
            return "input_file_mount_error", error_log
        if "interface_contract_mismatch" in lowered:
            return "interface_contract_mismatch", error_log
        if "tool_output_contract_mismatch" in lowered:
            return "tool_output_contract_mismatch", error_log
        if "dockerdesktop" in lowered or "docker daemon" in lowered or "docker api" in lowered:
            if "timed out" in lowered or "timeout" in lowered:
                return "runtime_warmup_timeout", error_log
            return "runtime_profile_unavailable", error_log
        if "runtime_warmup_timeout" in lowered:
            return "runtime_warmup_timeout", error_log
        if "runtime_image_pull_failed" in lowered:
            return "runtime_image_pull_failed", error_log
        if "resource_dependency_missing" in lowered or "runtime_profile_unavailable" in lowered:
            return "resource_dependency_missing", error_log
        if "dependency_install_timeout" in lowered:
            return "dependency_install_timeout", error_log
        if "dependency_install_failed" in lowered:
            return "dependency_install_failed", error_log
        if "artifact_dependency_missing" in lowered:
            return "artifact_dependency_missing", error_log
        missing_match = re.search(r"No module named ['\"]([^'\"]+)['\"]", error_log)
        if missing_match:
            missing_module = missing_match.group(1)
            top_module = missing_module.split(".", 1)[0]
            if "." in missing_module or top_module in {"src", "app", "pkg", "tests"}:
                return "pytest_import_overlay_missing", error_log
        if "tool_semantic_failure" in lowered:
            return "tool_semantic_failure", error_log
        if "agent_runtime_error" in lowered:
            return "agent_runtime_error", error_log
        return "execution_failed", error_log

    def _detect_placeholder_content(self, content: str, artifact_type: str) -> Optional[str]:
        """Reject runnable/deliverable artifacts that still contain placeholder references."""
        text = str(content or "")
        if not text.strip():
            return None
        patterns = [
            (r"\bfrom\s+your_[A-Za-z0-9_]*\s+import\b", "placeholder module import"),
            (r"\bimport\s+your_[A-Za-z0-9_]*\b", "placeholder module import"),
            (r"\byour_cleaning_module\b", "placeholder module name"),
            (r"\byour_module\b", "placeholder module name"),
            (r"\bpath/to/[^\s`'\"\)]+", "placeholder path"),
            (r"<[^>\n]*(?:path|file|module|function)[^>\n]*>", "placeholder angle-bracket token"),
            (r"\breplace\s+with\s+(?:the\s+)?(?:actual|real|your)\b", "replacement placeholder instruction"),
            (r"\bN/A\s+placeholder\b", "N/A placeholder"),
        ]
        if artifact_type == "code":
            patterns.append((r"(?im)^\s*#?\s*TODO\b", "TODO placeholder in code"))
        for pattern, reason in patterns:
            if re.search(pattern, text, flags=re.IGNORECASE):
                return reason
        return None

    def _is_evaluator_scope_warning(
        self,
        subtask: Subtask,
        eval_result: EvaluationResult,
        artifact_type: str,
        reason: str,
    ) -> bool:
        """Balanced mode: ignore evaluator complaints that belong to downstream nodes."""
        if self.execution_strictness != ExecutionStrictness.BALANCED:
            return False
        if eval_result.failure_type not in {
            EvaluationFailureType.MISSING_REQUIRED_CONTENT,
            EvaluationFailureType.CONTRACT_VIOLATION,
            EvaluationFailureType.DEPENDENCY_NOT_USED,
            EvaluationFailureType.EVALUATOR_INCONCLUSIVE,
        }:
            return False
        current_text = (
            f"{subtask.role}\n{subtask.description}\n{subtask.expected_output}"
        ).lower()
        reason_text = " ".join(
            [
                reason,
                eval_result.repair_hint or "",
                " ".join(eval_result.critical_issues),
            ]
        ).lower()

        current_is_test_task = any(
            token in current_text
            for token in ("pytest", "test", "tests", "unittest", "qa", '\u9a8c\u8bc1', '\u6d4b\u8bd5')
        )
        evaluator_asks_for_tests = any(
            token in reason_text
            for token in ("pytest", "unit test", "unit tests", "test file", "tests", '\u6d4b\u8bd5')
        )
        if evaluator_asks_for_tests and not current_is_test_task:
            return True

        current_is_final_doc = artifact_type in {"markdown", "plaintext"} and any(
            token in current_text
            for token in ("final", "summary", "report", "markdown", '\u603b\u7ed3', '\u62a5\u544a', '\u6700\u7ec8')
        )
        evaluator_asks_for_final_doc = any(
            token in reason_text
            for token in (
                "final report",
                "final summary",
                "final deliverable",
                "overall report",
                "markdown report",
                '\u603b\u7ed3',
                '\u62a5\u544a',
                '\u6700\u7ec8\u4ea4\u4ed8',
            )
        )
        if evaluator_asks_for_final_doc and not current_is_final_doc:
            return True

        downstream_scope_markers = (
            "downstream",
            "next task",
            "later task",
            "subsequent task",
            "overall task",
            "end-to-end",
            '\u540e\u7eed',
            '\u4e0b\u6e38',
        )
        return any(marker in reason_text for marker in downstream_scope_markers)

    async def _classify_execution_result(
        self,
        subtask: Subtask,
        result: ExecutionResult,
        artifact_type: str,
        expected: str,
        context_data: str = "",
        *,
        single_evaluator_handoff: bool = False,
    ) -> tuple[bool, str, str]:
        from .resource_compatibility import current_node_contract_text

        node_expected = current_node_contract_text(subtask)
        if not result.is_success:
            failure_type, failure_reason = self._classify_runtime_failure(result)
            return False, failure_type, failure_reason
        is_valid, struct_err = SmartExecutor.validate_artifact(result.output_data, artifact_type)
        if not is_valid:
            return False, "format_invalid", struct_err
        placeholder_reason = self._detect_placeholder_content(result.output_data, artifact_type)
        if placeholder_reason:
            result.cost_metric["placeholder_content"] = placeholder_reason
            return False, "placeholder_content", placeholder_reason
        fact_ok, fact_reason = self._check_fact_constraints(
            subtask,
            result.output_data,
            artifact_type,
            context_data,
        )
        if not fact_ok:
            result.cost_metric["fact_constraint_violation"] = fact_reason
            return False, "fact_constraint_violation", fact_reason
        if artifact_type == "code":
            allowed_packages = result.cost_metric.get("allowed_python_packages") or []
            dep_ok, missing_deps, dep_scan = self._check_python_artifact_dependencies(
                code_text=result.output_data,
                allowed_packages=allowed_packages,
            )
            result.cost_metric["python_import_scan"] = dep_scan
            if not dep_ok:
                dependency_contract = "\n".join(
                    str(value or "")
                    for value in (node_expected, expected, subtask.expected_output)
                ).lower()
                requires_stdlib = any(
                    marker in dependency_contract
                    for marker in (
                        "stdlib",
                        "standard library",
                        "no third-party",
                        "without third-party",
                    )
                )
                if requires_stdlib:
                    return (
                        False,
                        "artifact_dependency_missing",
                        "Generated code violates the stdlib-only output contract; "
                        + "external imports: "
                        + ", ".join(missing_deps),
                    )
                # Layer-0: a generated code *deliverable* importing external
                # packages is not a defect — importing fastapi in FastAPI code is
                # correct. The packages are provisioned (pip install) if/when the
                # code is actually executed by a downstream runner. Record the
                # provisioning need; do not reject the artifact.
                result.cost_metric["provision_on_execute"] = self._imports_to_pip_packages(missing_deps)
            interface_ok, interface_reason = self._check_code_interface_contract(
                result.output_data,
                node_expected,
                subtask.output_contract,
            )
            if not interface_ok:
                result.cost_metric["interface_contract_mismatch"] = interface_reason
                return False, "interface_contract_mismatch", interface_reason
        if node_expected:
            if (
                result.cost_metric.get("concrete_tool_execution")
                and any(marker in f"{subtask.description} {node_expected}".lower() for marker in ("read the complete", "read the full", '\u5b8c\u6574\u5185\u5bb9', '\u5168\u90e8\u5185\u5bb9'))
                and result.output_data.strip()
            ):
                result.cost_metric["tool_evidence_acceptance"] = "non_empty_complete_read"
                return True, "", ""
            if self.evaluation_mode != "active":
                result.cost_metric["semantic_evaluation"] = {
                    "mode": self.evaluation_mode,
                    "performed": False,
                    "authority": "external_verifier",
                }
                return True, "", ""
            # Planner expected_output can retain the original composite query.
            # The quality gate must evaluate this node's contract only, or it
            # will demand sibling/downstream artifacts from a single subtask.
            eval_result = await self.router_evaluate_result(
                subtask.description,
                node_expected,
                result.output_data,
                artifact_type=artifact_type,
                subtask_id=subtask.id,
                single_semantic_call=single_evaluator_handoff,
                output_contract=subtask.output_contract.model_dump(mode="json") if subtask.output_contract else None,
            )
            result.cost_metric["evaluation_result"] = eval_result.model_dump(mode="json")
            if eval_result.verdict == EvaluationVerdict.INCONCLUSIVE:
                logger.warning(
                    "[Evaluator] Inconclusive judgment for {}; accepting structurally valid output as evaluator_noise.",
                    subtask.id,
                )
                result.cost_metric["evaluation_soft_pass"] = True
                return True, "", ""
            if not eval_result.passed:
                reason = (
                    eval_result.repair_hint
                    or "; ".join(eval_result.critical_issues)
                    or eval_result.failure_type.value
                )
                if "evaluator json was malformed" in str(reason or "").lower():
                    self._append_execution_warning(
                        result,
                        "evaluator_inconclusive",
                        reason,
                        evaluator_failure_type=eval_result.failure_type.value,
                    )
                    result.cost_metric["evaluation_malformed_soft_pass"] = True
                    logger.warning(
                        "[Evaluator] Malformed evaluator JSON for {}; accepting structurally valid artifact under balanced strictness.",
                        subtask.id,
                    )
                    return True, "", ""
                if self._is_evaluator_scope_warning(subtask, eval_result, artifact_type, reason):
                    self._append_execution_warning(
                        result,
                        "evaluator_scope_warning",
                        reason,
                        evaluator_failure_type=eval_result.failure_type.value,
                    )
                    result.cost_metric["evaluation_scope_soft_pass"] = True
                    logger.warning(
                        "[Evaluator] Scope warning for {}; accepting artifact under balanced strictness: {}",
                        subtask.id,
                        reason,
                    )
                    return True, "", ""
                return False, eval_result.failure_type.value, reason
        return True, "", ""

    async def _validate_execution_result(
        self,
        subtask: Subtask,
        result: ExecutionResult,
        artifact_type: str,
        expected: str,
        context_data: str = "",
    ) -> tuple[bool, ExecutionResult]:
        passed, failure_type, failure_reason = await self._classify_execution_result(
            subtask,
            result,
            artifact_type,
            expected,
            context_data,
        )
        if not passed:
            result.cost_metric["failure_type"] = failure_type
            existing_layer = str(result.cost_metric.get("failure_layer") or "")
            result.cost_metric["failure_layer"] = (
                existing_layer
                if existing_layer not in {"", "none"}
                else self._failure_layer_for_type(failure_type)
            )
            result.cost_metric["executability"] = (
                "passed" if result.is_success else "failed"
            )
            result.cost_metric["task_success"] = False
            result.error_log = failure_reason or result.error_log
        else:
            result.cost_metric["failure_layer"] = "none"
            result.cost_metric["executability"] = "passed"
            result.cost_metric["task_success"] = True
        return passed, result

    def _is_best_artifact_candidate(self, result: Optional[ExecutionResult], artifact_type: str) -> bool:
        if result is None or not result.is_success or not str(result.output_data or "").strip():
            return False
        is_valid, _ = SmartExecutor.validate_artifact(result.output_data, artifact_type)
        return bool(is_valid)

    @staticmethod
    def _bounded_utf8_text(value: str, max_bytes: int) -> str:
        raw = str(value or "").encode("utf-8")
        if len(raw) <= max_bytes:
            return str(value or "")
        bounded = raw[:max_bytes]
        while bounded:
            try:
                return bounded.decode("utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                if exc.end != len(bounded):
                    raise
                bounded = bounded[: exc.start]
        return ""

    @staticmethod
    def _collect_event_ids(value: Any) -> tuple[str, ...]:
        collected: list[str] = []

        def visit(item: Any, key: str = "") -> None:
            if isinstance(item, Mapping):
                for child_key, child in item.items():
                    visit(child, str(child_key))
            elif isinstance(item, (list, tuple)):
                for child in item:
                    visit(child, key)
            elif key.endswith("event_id") and isinstance(item, str) and item:
                collected.append(item)

        visit(value)
        return tuple(dict.fromkeys(collected))

    def _formal_records_for_output(
        self,
        *,
        task_id: str,
        step_id: str,
        output_key: str,
        output_contract: Optional[Any] = None,
        step: Any = None,
    ) -> tuple[RuntimeArtifactRecord, ...]:
        """Return exact current-run records for one sealed output.

        The lookup is identity-based.  It does not inspect filenames or output
        contents and therefore works for arbitrary extensions and directories.
        """

        base = f"{task_id}:{step_id}:{output_key}"
        selected: list[RuntimeArtifactRecord] = []
        seen: set[str] = set()
        for key, record in self.artifact_registry.by_step.items():
            if key != base and not key.startswith(base + ":"):
                continue
            absolute = os.path.abspath(record.path)
            if self.execution_substrate is not None and record.origin == "external_tool_output":
                # Preserve receipt order until the latest-revision selection
                # below, even when repeated verified bytes share storage.
                selected.append(record)
                continue
            if absolute in seen:
                continue
            seen.add(absolute)
            selected.append(record)
        if self.execution_substrate is not None and selected:
            # Receipts are append-only, but a task path names mutable state.
            # The writer and final snapshot can both register that same path.
            # Use its latest verified readback for acceptance/publication;
            # retain the historical records in the registry as evidence.
            latest_external: dict[str, RuntimeArtifactRecord] = {}
            for record in selected:
                tool_path = str(record.metadata.get("tool_path") or "")
                if record.origin == "external_tool_output" and tool_path:
                    latest_external[tool_path] = record
            selected = [
                record for record in selected
                if record.origin != "external_tool_output"
                or not record.metadata.get("tool_path")
                or latest_external[str(record.metadata["tool_path"])] is record
            ]
            declared = self._contract_to_dict(output_contract).get("produced_files") or []
            expected_paths: set[str] = set()
            for item in declared if isinstance(declared, list) else ():
                hint = self._produced_file_path_hint(item)
                if not hint:
                    continue
                try:
                    expected_paths.add(self.execution_substrate.task_path(hint))
                except Exception:
                    continue
            matching = [
                record for record in selected
                if record.origin == "external_tool_output"
                and str(record.metadata.get("tool_path") or "") in expected_paths
            ]
            if matching:
                selected = matching + [record for record in selected if record not in matching]
        contract = self._contract_to_dict(output_contract)
        kind = str(contract.get("artifact_type") or "")
        declared = contract.get("produced_files") or ()
        primary_file_declared = any(
            isinstance(item, Mapping) and bool(item.get("required", True))
            and bool(self._produced_file_path_hint(item))
            and str(item.get("artifact_type") or kind) in {kind, "file"}
            for item in declared
        )
        application = getattr(step, "resource_application", None)
        realization = getattr(application, "output_realization_contract", None)
        if (
            self.execution_substrate is None
            and kind in {"code", "json", "csv", "markdown", "plaintext"}
            and getattr(realization, "realization_kind", None) == "materialized_file_side_effect"
        ):
            # Local Docker reports a writer receipt and separately inventories
            # actual file effects. Select only the exact declared primary file
            # from this producer, just as the external-substrate path does.
            def relative_locator(value: Any) -> str | None:
                if not isinstance(value, str) or not value:
                    return None
                path = PurePosixPath(value.replace("\\", "/"))
                if path.is_absolute() or ".." in path.parts or str(path) == ".":
                    return None
                return str(path)

            expected = {
                relative_locator(self._produced_file_path_hint(item))
                for item in declared if isinstance(item, Mapping)
                and bool(item.get("required", True))
                and str(item.get("artifact_type") or kind) in {kind, "file"}
            } - {None}
            if len(expected) == 1:
                matched = [
                    record for record in selected
                    if record.origin == "tool_output"
                    and record.artifact_type in {kind, "file"}
                    and record.metadata.get("source_task") == task_id
                    and record.metadata.get("source_step") == step_id
                    and record.metadata.get("source_output") == output_key
                    and relative_locator(record.metadata.get("logical_path")) in expected
                ]
                if len(matched) > 1:
                    raise RuntimeError("materialized_delivery_file_ambiguous")
                if matched:
                    original = matched[0]
                    path = Path(original.path)
                    expected_sha = original.metadata.get("content_sha256")
                    if (
                        not isinstance(expected_sha, str)
                        or re.fullmatch(r"[0-9a-f]{64}", expected_sha) is None
                        or not path.is_file() or path.is_symlink()
                        or hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha
                    ):
                        raise RuntimeError("materialized_delivery_content_hash_mismatch")
                    # The declared type selects the validator; it does not
                    # assert that the observed bytes satisfy that validator.
                    primary = replace(original, artifact_type=kind)
                    selected = [primary, *(record for record in selected if record is not original)]
        if kind in {"code", "json", "csv", "markdown", "plaintext"} and not primary_file_declared:
            # Nested controller Tool calls register observed files before the
            # controller's value.  Their insertion order is evidence history,
            # not the final-output identity sealed by the Compiler.
            primary = self.artifact_registry.by_step.get(base)
            if primary is not None and primary in selected:
                selected = [primary, *(record for record in selected if record is not primary)]
        return tuple(selected)

    def _explicit_final_deliverable_contract(
        self,
        *,
        subtask_id: str,
        task_list: Sequence[Mapping[str, Any]],
        node_output_contract: Any = None,
    ) -> FinalDeliverableContract | None:
        invocation = self.task_invocation
        if (
            invocation is not None and invocation.final_deliverable_contract is not None
            and task_list and str(task_list[-1].get("id") or "") == subtask_id
        ):
            return invocation.final_deliverable_contract
        return self._declared_node_tree_contract(node_output_contract)

    def _declared_node_tree_contract(self, output_contract: Any) -> FinalDeliverableContract | None:
        """Represent a declared file collection without inventing its members."""
        output = self._contract_to_dict(output_contract)
        kind = str(output.get("artifact_type") or "")
        if kind not in {"bundle", "directory"}:
            return None
        members = []
        for item in output.get("produced_files") or ():
            if not isinstance(item, Mapping) or not item.get("required", True):
                continue
            if str(item.get("artifact_type") or "") in {"bundle", "directory"}:
                continue
            hint = self._produced_file_path_hint(item)
            if hint:
                record = RuntimeArtifactRecord(
                    path="", artifact_type="file", origin="declared_member",
                    metadata={"contract_path_hint": hint},
                )
                members.append(self._record_contract_locator(record))
        return FinalDeliverableContract(
            representation=kind, format_id=kind, required_members=tuple(members),
        )

    @staticmethod
    def _record_contract_locator(record: RuntimeArtifactRecord) -> str:
        value = str(
            record.metadata.get("contract_path_hint")
            or record.metadata.get("tool_path")
            or ""
        )
        normalized = value.replace("\\", "/").strip()
        if normalized.startswith("/app/"):
            normalized = normalized.removeprefix("/app/")
        else:
            normalized = normalized.lstrip("./")
            if normalized.startswith("app/"):
                normalized = normalized.removeprefix("app/")
        return normalized

    def _prepare_formal_publication_source(
        self,
        *,
        subtask_id: str,
        records: Sequence[RuntimeArtifactRecord],
        fallback_record: RuntimeArtifactRecord,
        contract: FinalDeliverableContract | None,
    ) -> tuple[Path, str, str, bool, str | None, tuple[str, ...]]:
        """Choose or assemble the artifact strictly from explicit identities.

        Multi-file assembly is allowed only when the request contract declares
        member paths.  No basename, query, parameter-name, or content heuristic
        participates in the assignment.
        """

        candidates = list(records) or [fallback_record]
        unique: list[RuntimeArtifactRecord] = []
        seen: set[str] = set()
        for record in candidates:
            path = Path(record.path).absolute()
            if str(path) in seen:
                continue
            if not path.exists() or not self._is_current_run_artifact_path(str(path)):
                raise RuntimeError("formal_final_artifact_source_invalid")
            seen.add(str(path))
            unique.append(record)
        if not unique:
            raise RuntimeError("formal_final_artifact_source_missing")

        if contract is None:
            path = Path(fallback_record.path).absolute()
            return path, "", path.suffix.lower(), False, None, ()

        representation = contract.representation
        if representation in {"inline_text", "file"}:
            preferred = Path(fallback_record.path).absolute()
            file_paths = [Path(item.path).absolute() for item in unique if Path(item.path).is_file()]
            if preferred.is_file():
                source = preferred
            elif len(file_paths) == 1:
                source = file_paths[0]
            else:
                raise ArtifactV2MachineContractError(
                    "formal_final_file_source_ambiguous"
                )
            return (
                source,
                contract.format_id,
                contract.extension or source.suffix.lower(),
                False,
                None,
                (),
            )

        directory_paths = [
            Path(item.path).absolute() for item in unique if Path(item.path).is_dir()
        ]
        if len(directory_paths) == 1:
            return (
                directory_paths[0],
                contract.format_id,
                contract.extension,
                representation == "bundle",
                contract.primary_member,
                contract.required_members,
            )
        if len(directory_paths) > 1:
            raise ArtifactV2MachineContractError("formal_final_tree_source_ambiguous")

        required = tuple(contract.required_members)
        if not required:
            raise ArtifactV2MachineContractError("formal_final_tree_members_undeclared")
        assignments: dict[str, RuntimeArtifactRecord] = {}
        remaining = list(unique)
        for member in required:
            matches = [
                record
                for record in remaining
                if self._record_contract_locator(record) == member
            ]
            if len(matches) > 1:
                raise ArtifactV2MachineContractError(
                    "formal_final_tree_member_ambiguous"
                )
            if len(matches) == 1:
                assignments[member] = matches[0]
                remaining.remove(matches[0])
        if contract.primary_member and contract.primary_member not in assignments:
            if fallback_record in remaining:
                assignments[contract.primary_member] = fallback_record
                remaining.remove(fallback_record)
        missing = [member for member in required if member not in assignments]
        if len(missing) == 1 and len(remaining) == 1:
            assignments[missing[0]] = remaining[0]
            remaining = []
            missing = []
        if missing:
            raise ArtifactV2MachineContractError(
                "formal_final_tree_required_member_unresolved"
            )

        assembly_root = (
            Path(self.artifact_dir)
            / "artifacts"
            / "publication_sources"
            / canonical_sha256(
                {
                    "subtask_id": subtask_id,
                    "contract_sha256": contract.contract_sha256,
                    "records": [
                        {
                            "member": member,
                            "record_origin": record.origin,
                            "record_tool_path": record.metadata.get("tool_path"),
                            "record_sha256": path_sha256(Path(record.path)),
                        }
                        for member, record in sorted(assignments.items())
                    ],
                }
            )
        )
        if not assembly_root.exists():
            assembly_root.mkdir(parents=True, exist_ok=False)
            try:
                for member, record in assignments.items():
                    destination = assembly_root / member
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    source = Path(record.path).absolute()
                    if source.is_dir():
                        shutil.copytree(source, destination, symlinks=False)
                    elif source.is_file():
                        shutil.copy2(source, destination)
                    else:
                        raise RuntimeError("formal_final_tree_member_kind_invalid")
            except Exception:
                shutil.rmtree(assembly_root, ignore_errors=True)
                raise
        return (
            assembly_root,
            contract.format_id,
            contract.extension,
            representation == "bundle",
            contract.primary_member,
            contract.required_members,
        )

    def _validate_plan_output_machine_contract(
        self,
        *,
        subtask_id: str,
        content: bytes,
        artifact_type: str,
        extension: str,
        records: Sequence[RuntimeArtifactRecord],
        required_outputs_valid: bool,
        handles_valid: bool = True,
        node_output_contract: Any = None,
    ) -> None:
        """Validate file bytes through the same representation used at publication.

        A controller completion receipt is not the physical file. Existing
        value contracts retain their format checks; file contracts use the
        selected current-run material, whose exact bytes were read back.
        """
        if artifact_type in {"bundle", "directory"}:
            if not handles_valid:
                raise ArtifactV2MachineContractError("artifact_handle_invalid")
            contract = self._declared_node_tree_contract(node_output_contract)
            if contract is None:
                raise ArtifactV2MachineContractError("artifact_tree_contract_missing")
            self._validate_explicit_deliverable_machine_contract(
                subtask_id=subtask_id, contract=contract, content=content,
                records=records, required_outputs_valid=required_outputs_valid,
            )
            return
        if artifact_type != "file":
            validate_machine_contract(
                content=content, artifact_type=artifact_type, extension=extension,
                required_produced_files_present=required_outputs_valid,
                handles_valid=handles_valid,
            )
            return
        if not required_outputs_valid:
            raise ArtifactV2MachineContractError("required_produced_file_missing")
        if not handles_valid or not records:
            raise ArtifactV2MachineContractError("artifact_handle_invalid")
        source, fmt, ext, _, _, _ = self._prepare_formal_publication_source(
            subtask_id=subtask_id, records=records,
            fallback_record=records[0], contract=None,
        )
        if not source.is_file():
            raise ArtifactV2MachineContractError("artifact_file_source_required")
        descriptor_for_path(
            source, format_id=fmt, extension=extension or ext,
            logical_locator=f"artifact://{subtask_id}/final",
            provenance_source_ids=("sealed_plan_final_artifact",),
        )

    def _validate_explicit_deliverable_machine_contract(
        self,
        *,
        subtask_id: str,
        contract: FinalDeliverableContract,
        content: bytes,
        records: Sequence[RuntimeArtifactRecord],
        required_outputs_valid: bool,
    ) -> None:
        if not required_outputs_valid:
            raise ArtifactV2MachineContractError("required_produced_file_missing")
        if contract.representation in {"inline_text", "file"} and not records:
            descriptor_for_bytes(
                content,
                representation=ArtifactRepresentation(contract.representation),
                format_id=contract.format_id,
                extension=contract.extension,
                logical_locator=f"artifact://{subtask_id}/final",
                provenance_source_ids=("sealed_plan_final_artifact",),
            )
            return
        if not records:
            raise ArtifactV2MachineContractError("artifact_tree_handle_missing")
        source, format_id, extension, as_bundle, primary, required = (
            self._prepare_formal_publication_source(
                subtask_id=subtask_id,
                records=records,
                fallback_record=records[0],
                contract=contract,
            )
        )
        descriptor_for_path(
            source,
            format_id=format_id,
            extension=extension,
            logical_locator=f"artifact://{subtask_id}/final",
            provenance_source_ids=("sealed_plan_final_artifact",),
            as_bundle=as_bundle,
            primary_member=primary,
            required_members=required,
        )

    def _bound_output_schema_checks(self, *, step: Any, content: bytes) -> list[dict[str, Any]]:
        """Use only response_format bindings on the selected final execution step."""
        from .artifact_semantics import check_bound_schema_content
        if step is None:
            return []
        checks: list[dict[str, Any]] = []
        for binding in step.context_bindings:
            if binding.target_port != "response_format":
                continue
            if binding.source_id not in step.consumed_context_source_ids:
                raise RuntimeError("evaluation_schema_source_unauthorized")
            ok, failure, _, handle = self.resolve_artifact_handle(binding.handle_id)
            if not ok or handle is None:
                raise RuntimeError(failure or "evaluation_schema_source_missing")
            if handle.handle_id.removeprefix("artifact:") != binding.handle_id.removeprefix("artifact:"):
                raise RuntimeError("evaluation_schema_source_identity_mismatch")
            descriptor, schema_content = self._formal_material_descriptor(binding.source_id, handle)
            if descriptor.content_sha256 != binding.content_sha256:
                raise RuntimeError("evaluation_schema_source_content_mismatch")
            from .json_serialization import json_serialization_format
            encoding = json_serialization_format(step.expected_output_contract.model_dump(mode="json"))
            report = (check_bound_schema_content(content, schema_content, serialization_format=encoding or "json") if schema_content is not None
                      else {"status": "unknown", "reason": "bound_schema_content_unavailable", "references_fetched": False})
            report.update(artifact_content_sha256=hashlib.sha256(content).hexdigest(),
                          source_id=binding.source_id, schema_content_sha256=binding.content_sha256,
                          step_id=step.step_id, target_port=binding.target_port)
            if report not in checks:
                checks.append(report)
        return checks

    async def _publish_formal_artifact(
        self,
        *,
        subtask: Subtask,
        task_list: Sequence[Mapping[str, Any]],
        routing: Dict[str, Any],
        result: ExecutionResult,
        artifact_type: str,
        output_ext: str,
        original_public_objective: str,
        produced_file_status: Sequence[Mapping[str, Any]],
        record: RuntimeArtifactRecord,
        records: Sequence[RuntimeArtifactRecord] = (),
        evaluation_contract: Mapping[str, Any] | None = None,
        validation_step: Any = None,
    ) -> Any:
        if (
            self.artifact_lifecycle_coordinator is None
            or self.artifact_store is None
            or self.context_commit_store is None
            or self.execution_ledger is None
        ):
            raise RuntimeError("formal_artifact_lifecycle_context_incomplete")
        frozen_result = routing.get("frozen_candidate_pool")
        if frozen_result is None:
            raise RuntimeError("formal_artifact_candidate_pool_missing")
        revision = frozen_result.contract_projection.revision
        artifact_revision = ArtifactRevisionRef(
            run_id=self.execution_ledger.run_id,
            subtask_revision=revision,
            artifact_revision=0,
        )
        downstream_edge_contracts: list[DagEdgeContractV1] = []
        dag_descriptors: list[dict[str, Any]] = []
        for task in task_list:
            task_id = str(task.get("id") or "")
            contract = self._contract_to_dict(task.get("output_contract"))
            descriptor = {
                "subtask_id": task_id,
                "depends_on": list(task.get("depends_on") or ()),
                "contract_sha256": canonical_sha256(contract),
                "incoming_edge_contract_sha256s": sorted(
                    str(item.get("edge_contract_sha256") or "")
                    for item in (task.get("incoming_edge_contracts") or ())
                    if isinstance(item, Mapping)
                    and str(item.get("edge_contract_sha256") or "")
                ),
            }
            dag_descriptors.append(descriptor)
            if subtask.id in descriptor["depends_on"]:
                matching_edges = [
                    DagEdgeContractV1.model_validate(item)
                    for item in (task.get("incoming_edge_contracts") or ())
                    if isinstance(item, Mapping)
                    and str(item.get("producer_id") or "") == subtask.id
                    and str(item.get("consumer_id") or "") == task_id
                ]
                if len(matching_edges) != 1:
                    raise RuntimeError(
                        "formal_downstream_edge_contract_missing_or_duplicate"
                    )
                downstream_edge_contracts.extend(matching_edges)
        if evaluation_contract is None:
            raise RuntimeError("formal_evaluation_contract_missing")
        canonical_evaluation_contract = copy.deepcopy(dict(evaluation_contract))
        standard = build_evaluation_reference_standard(
            artifact_revision=artifact_revision,
            subtask=subtask,
            downstream_edge_contracts=downstream_edge_contracts,
            evaluation_contract=canonical_evaluation_contract,
        )
        deliverable_contract = self._explicit_final_deliverable_contract(
            subtask_id=subtask.id,
            task_list=task_list,
            node_output_contract=subtask.output_contract,
        )
        (
            source_path,
            declared_format_id,
            declared_extension,
            as_bundle,
            primary_member,
            required_members,
        ) = self._prepare_formal_publication_source(
            subtask_id=subtask.id,
            records=records,
            fallback_record=record,
            contract=deliverable_contract,
        )
        from .artifact_semantics import validate_delivery_content, OutputContractViolation
        publication_path = source_path / primary_member if source_path.is_dir() and primary_member else source_path
        bound_schema_checks: list[dict[str, Any]] = []
        from .artifact_semantics import requires_content_contract_validation
        if requires_content_contract_validation(canonical_evaluation_contract):
            material = publication_path.read_bytes()
            prior = getattr(self, "_checked_output_material", {}).pop(subtask.id, None)
            # Reuse checks only for exactly the same bytes and execution contract.
            # The private cache is never serialized; no new contract hash gate.
            macro_contract = self._contract_to_dict(subtask.output_contract)
            validation = (copy.deepcopy(prior[2]) if prior is not None
                and prior[0] == material and prior[1] == canonical_evaluation_contract
                and prior[3] == macro_contract
                else validate_delivery_content(material, canonical_evaluation_contract, macro_contract))
            result.cost_metric["publication_contract_validation"] = validation
            bound_schema_checks = self._bound_output_schema_checks(step=validation_step, content=material)
            validation["bound_schema_checks"] = bound_schema_checks
            for check in bound_schema_checks:
                if check["status"] == "fail":
                    raise OutputContractViolation("artifact_bound_schema_mismatch:" + str(check["reason"]))
        logical_locator = (
            f"artifact://{revision.graph_revision}/{subtask.id}/{revision.subtask_revision}"
        )
        if deliverable_contract is not None and deliverable_contract.logical_name:
            logical_locator = f"{logical_locator}/{deliverable_contract.logical_name}"
        try:
            descriptor = descriptor_for_path(
                source_path,
                format_id=declared_format_id,
                extension=(declared_extension or output_ext or source_path.suffix.lower()),
                logical_locator=logical_locator,
                provenance_source_ids=("sealed_plan_final_artifact",),
                as_bundle=as_bundle,
                primary_member=primary_member,
                required_members=required_members,
            )
        except ArtifactV2Error as exc:
            raise RuntimeError("formal_artifact_v2_descriptor_failed") from exc
        produced_ok = all(
            not bool(item.get("required", True)) or item.get("status") == "present"
            for item in produced_file_status
            if isinstance(item, Mapping)
        )
        plan_sha256 = str(result.cost_metric.get("executed_plan_sha256") or "") or None
        recovery_operation_sha256 = str(
            (routing.get("recovery") or {}).get("recovery_operation_sha256") or ""
        ) or None
        execution_result_sha256 = canonical_sha256(
            {
                "is_success": result.is_success,
                "artifact_descriptor_sha256": descriptor.descriptor_sha256,
                "candidate_pool_sha256": frozen_result.candidate_pool_snapshot.candidate_pool_sha256,
                "plan_sha256": plan_sha256,
                "recovery_operation_sha256": recovery_operation_sha256,
            }
        )
        candidate = build_candidate_v2(
            artifact_revision=artifact_revision,
            descriptor=descriptor,
            output_contract_sha256=standard.output_contract_sha256,
            candidate_pool_sha256=frozen_result.candidate_pool_snapshot.candidate_pool_sha256,
            execution_result_sha256=execution_result_sha256,
            plan_sha256=plan_sha256,
            recovery_operation_sha256=recovery_operation_sha256,
            execution_event_ids=self._collect_event_ids(result.cost_metric),
            source_handle_ids=tuple(
                item
                for item in (
                    str(record.metadata.get("handle_id") or ""),
                )
                if item
            ),
        )
        if not produced_ok:
            validate_machine_contract(
                content=b"",
                artifact_type="plaintext",
                required_produced_files_present=False,
            )
        execution_accounting_ids = tuple(
            str(item)
            for item in (result.cost_metric.get("execution_accounting_operation_ids") or ())
            if str(item)
        )
        dependency_manifests = [
            self.context.committed_manifest_for(dependency)
            for dependency in subtask.depends_on
        ]
        dependency_manifests = [item for item in dependency_manifests if item is not None]
        evaluation_material_sources: list[AuthorizedMaterialSource] = []
        registered_inputs = self.artifact_registry.input_file_handles
        if self.task_invocation is not None:
            for input_descriptor in self.task_invocation.public_inputs:
                handle = registered_inputs.get(input_descriptor.handle_id)
                if handle is None or not handle.host_path:
                    raise RuntimeError("evaluation_public_input_handle_missing")
                evaluation_material_sources.append(
                    AuthorizedMaterialSource(
                        source_id=(
                            f"evaluation_public_input:{input_descriptor.handle_id}"
                        ),
                        origin="public_input",
                        logical_name=input_descriptor.logical_name,
                        logical_locator=input_descriptor.runtime_path,
                        source_path=Path(handle.host_path),
                        expected_sha256=input_descriptor.content_sha256,
                        expected_byte_size=input_descriptor.byte_size,
                        expected_kind=input_descriptor.path_kind,
                        extension=input_descriptor.extension,
                        media_type=input_descriptor.media_type,
                    )
                )
        for dependency_manifest in dependency_manifests:
            self.artifact_store.validate_manifest_content(dependency_manifest)
            dependency_path = self.artifact_store.artifact_path(
                dependency_manifest
            )
            observed_hash, observed_size, observed_kind = public_snapshot_identity(
                dependency_path
            )
            if observed_kind not in {"file", "directory"}:
                raise RuntimeError("evaluation_dependency_kind_invalid")
            evaluation_material_sources.append(
                AuthorizedMaterialSource(
                    source_id=(
                        "evaluation_committed_dependency:"
                        + dependency_manifest.committed_manifest_sha256
                    ),
                    origin="committed_dependency",
                    logical_name=(
                        dependency_manifest.artifact_revision.subtask_revision.subtask_id
                    ),
                    logical_locator=dependency_manifest.logical_locator,
                    source_path=dependency_path,
                    expected_sha256=observed_hash,
                    expected_byte_size=observed_size,
                    expected_kind=cast(Literal["file", "directory"], observed_kind),
                    extension=dependency_manifest.extension,
                    media_type=dependency_manifest.mime_type,
                    descriptor=dependency_manifest.artifact_v2,
                )
            )
        evaluation_material_view = build_authorized_model_material_view(
            run_id=self.execution_ledger.run_id,
            revision=revision,
            sources=evaluation_material_sources,
        )
        evaluation_source_evidence = tuple(
            EvaluationSourceEvidence(
                source_id=item.source_id,
                origin=item.origin,
                logical_name=item.logical_name,
                logical_locator=item.logical_locator,
                representation=item.representation,
                media_type=item.media_type,
                content_sha256=item.content_sha256,
                descriptor_sha256=item.descriptor_sha256,
                coverage_status=item.coverage_status,
                byte_size=item.byte_size,
                public_content=item.authorized_content,
                public_content_sha256=item.authorized_content_sha256,
                structure_evidence=dict(item.structure_evidence),
            )
            for item in evaluation_material_view.materials
        )
        public_objective = self._bounded_utf8_text(original_public_objective, 65536)
        registry = PayloadSourceRegistry(
            subtask_id=subtask.id,
            mode="production_evaluation",
            attempt_id=artifact_revision.revision_sha256,
        )
        registry.register(
            "evaluation_reference",
            origin="public_case",
            material=standard.model_dump(mode="json"),
            default=True,
        )
        guard = ProductionModelPayloadGuard(registry)
        evaluation_source_registry_ids: list[str] = []
        for index, source in enumerate(evaluation_source_evidence, 1):
            registry_id = f"evaluation_source_{index}"
            registry.register(
                registry_id,
                origin="public_case",
                material=source.model_dump(mode="json"),
                producer={
                    "source_id": source.source_id,
                    "origin": source.origin,
                    "source_evidence_sha256": source.source_evidence_sha256,
                },
                default=True,
            )
            evaluation_source_registry_ids.append(registry_id)
        staged_holder: Dict[str, Any] = {}

        def evaluation_context_factory(staged: Any) -> EvaluationContextSnapshot:
            if bound_schema_checks:
                actual_hash = staged.artifact_v2.content_sha256
                if primary_member:
                    actual_hash = next((m.content_sha256 for m in staged.artifact_v2.members
                                        if m.relative_path == primary_member), None)
                if any(check["artifact_content_sha256"] != actual_hash for check in bound_schema_checks):
                    raise RuntimeError("evaluation_schema_checked_content_changed")
            evaluation_context = EvaluationContextSnapshot(
                current_revision=revision,
                original_public_objective=public_objective,
                original_public_objective_sha256=canonical_sha256(public_objective),
                current_contract=copy.deepcopy(canonical_evaluation_contract),
                macro_delivery_standard={
                    "framework_publication_facts": {
                        "authority": "framework_read_only",
                        "evaluation_stage": "staged_pre_export",
                        "artifact_revision": staged.artifact_revision.model_dump(mode="json"),
                        "artifact_manifest_sha256": staged.manifest_sha256,
                        "formal_export": "not_performed_at_this_stage",
                        "bound_schema_checks": copy.deepcopy(bound_schema_checks),
                        "delivery_responsibility": "Deterministic top-level copy and naming after acceptance and commit; not member renaming, content rewriting or remote side effects.",
                        "final_target": (
                            deliverable_contract.model_dump(mode="json", include={
                                "representation", "format_id", "logical_name", "primary_member", "required_members",
                            }) if deliverable_contract is not None else None
                        ),
                        **({"contract_scope": subtask.semantic_contract_v2.output.contract_scope}
                           if subtask.semantic_contract_v2 is not None else {}),
                    },
                    "input_alignment": copy.deepcopy(result.cost_metric.get("input_alignment", {})),
                    "task": subtask.description, "expected_output": subtask.expected_output,
                    "output_contract": subtask.output_contract.model_dump(mode="json") if subtask.output_contract else {},
                    "semantic_contract": subtask.semantic_contract_v2.model_dump(mode="json") if subtask.semantic_contract_v2 else {},
                },
                document_validation=dict(result.cost_metric.get("publication_contract_validation", {}).get("document_validation", {})),
                dag_contract_descriptors=tuple(dag_descriptors),
                downstream_consumer_descriptors=tuple(
                    item.model_dump(mode="json")
                    for item in downstream_edge_contracts
                ),
                dependency_committed_manifest_sha256s=tuple(
                    item.committed_manifest_sha256 for item in dependency_manifests
                ),
                dependency_artifact_descriptors=tuple(
                    {
                        "subtask_id": item.artifact_revision.subtask_revision.subtask_id,
                        "artifact_type": item.artifact_type,
                        "content_sha256": item.content_sha256,
                        "contract_sha256": item.output_contract_sha256,
                        "logical_locator": item.logical_locator,
                        "committed_manifest_sha256": item.committed_manifest_sha256,
                    }
                    for item in dependency_manifests
                ),
                source_evidence=evaluation_source_evidence,
                staged_artifact_manifest_sha256=staged.manifest_sha256,
                plan_sha256=plan_sha256,
                recovery_operation_sha256=recovery_operation_sha256,
                provenance_source_ids=(
                    "evaluation_reference",
                    "evaluation_context",
                    "staged_artifact_content",
                    *evaluation_source_registry_ids,
                ),
            )
            registry.register(
                "evaluation_context",
                origin="public_case",
                material=evaluation_context.model_dump(mode="json"),
                default=True,
            )
            registry.register(
                "staged_artifact_content",
                origin="current_run_step_output",
                material=descriptor.model_dump(mode="json"),
                parent_source_ids=("evaluation_reference", "evaluation_context"),
                producer={
                    "subtask_id": subtask.id,
                    "artifact_manifest_sha256": staged.manifest_sha256,
                },
                default=True,
            )
            staged_holder["manifest"] = staged
            return evaluation_context

        def payload_guard_factory(review_index: int) -> Any:
            staged = staged_holder.get("manifest")
            if staged is None:
                raise RuntimeError("formal_staged_artifact_context_missing")
            return guard.for_request(
                "evaluator_review" if review_index else "evaluator",
                source_ids=guard.default_source_ids,
                request_identity={
                    "subtask_id": subtask.id,
                    "review_index": review_index,
                    "artifact_manifest_sha256": staged.manifest_sha256,
                },
            )

        publication = await self.artifact_lifecycle_coordinator.publish_v2(
            candidate=candidate,
            content=None,
            source_path=source_path,
            reference_standard=standard,
            evaluation_context_factory=evaluation_context_factory,
            payload_guard_factory=payload_guard_factory,
            execution_accounting_operation_ids=execution_accounting_ids,
        )
        routing["evaluation"] = {
            "mode": publication.evaluation_mode,
            "status": publication.status,
            "observed_status": publication.observed_evaluation_status,
            "review_triggered": publication.review_triggered,
            "failure_code": publication.failure_code,
            "staged_manifest_sha256": publication.staged.manifest_sha256,
            "evaluation_decision_sha256": (
                publication.decision.decision_sha256 if publication.decision else None
            ),
            "verified_manifest_sha256": (
                publication.verified.verified_manifest_sha256 if publication.verified else None
            ),
            "committed_manifest_sha256": (
                publication.committed.committed_manifest_sha256 if publication.committed else None
            ),
            "quarantine_sha256": (
                publication.quarantined.quarantine_sha256 if publication.quarantined else None
            ),
            "accounting_operation_ids": list(publication.evaluation_accounting_operation_ids),
            "observed_evaluation_decision_sha256": publication.observed_evaluation_decision_sha256,
            "payload_checks": list(guard.checks),
        }
        result.cost_metric["artifact_lifecycle"] = dict(routing["evaluation"])
        return publication

    async def _validate_execution_result_preserving_best(
        self,
        subtask: Subtask,
        result: ExecutionResult,
        artifact_type: str,
        expected: str,
        context_data: str,
        best_artifact_candidate: Optional[ExecutionResult],
        *,
        fallback_stage: str,
    ) -> tuple[bool, ExecutionResult]:
        passed, validated = await self._validate_execution_result(
            subtask,
            result,
            artifact_type,
            expected,
            context_data,
        )
        if passed:
            return True, validated
        failure_type = str(validated.cost_metric.get("failure_type") or "")
        if (
            best_artifact_candidate is not None
            and self._is_best_artifact_candidate(best_artifact_candidate, artifact_type)
            and (not str(validated.output_data or "").strip() or failure_type in {"format_invalid", "artifact_empty"})
        ):
            reason = validated.error_log or failure_type or "Fallback did not produce a usable artifact."
            self._append_execution_warning(
                best_artifact_candidate,
                "best_artifact_retained",
                reason,
                fallback_stage=fallback_stage,
            )
            best_artifact_candidate.cost_metric["best_artifact_retained"] = {
                "fallback_stage": fallback_stage,
                "discarded_failure_type": failure_type,
                "discarded_reason": reason,
            }
            return True, best_artifact_candidate
        return False, validated

    # -- Main Pipeline --------------------------

    async def run_pipeline(
        self,
        task_list: List[Dict[str, Any]],
        routing_bundles: Dict[str, dict],
    ) -> GlobalContext:
        """
        Execute the full DAG pipeline utilizing topological async concurrency
        and HiRAG Context Compression.
        """
        n = len(task_list)
        logger.info(f"[Orchestrator] Parallel Pipeline started with {n} nodes")
        self._formal_final_task_id = (
            str(task_list[-1].get("id") or "") if task_list else ""
        )

        _DEFAULT_EXT = {
            "code": ".py", "json": ".json", "csv": ".csv",
            "markdown": ".md", "plaintext": ".txt",
        }

        # -- HiRAG Memory Manager --
        class HierarchicalMemoryManager:
            def __init__(self, transport, model, cost_ledger):
                self.transport = require_async_model_transport(transport)
                self.model = model
                self.cost_ledger = cost_ledger
                self.contracts = {}
                self.artifacts = {}
                self.artifact_types = {}
                self.artifact_profiles = {}
            
            def _keep_exact(self, artifact_type: str, artifact: str) -> bool:
                if artifact_type in {"json", "code"}:
                    return len(artifact) <= 50000
                return len(artifact) <= 12000

            async def compress_artifact(
                self,
                task_id: str,
                desc: str,
                artifact: str,
                artifact_type: str = "",
            ) -> str:
                self.artifact_types[task_id] = artifact_type
                if self._keep_exact(artifact_type, artifact):
                    self.artifacts[task_id] = artifact
                else:
                    self.artifacts[task_id] = artifact[:50000] + "\n... (exact artifact truncated)"

                if len(artifact) < 1000 or artifact_type in {"json"}:
                    self.contracts[task_id] = artifact
                    return artifact
                prompt = f"Abstract the following artifact into a precise interface contract containing strictly [Key Conclusions] and [Output Schema] so downstream agents can use it. Task was: {desc}\n\nArtifact: `{artifact[:4000]}...`"
                try:
                    accounting_context = (
                        self.cost_ledger.new_operation(
                            stage="context_compression",
                            subtask_id=task_id,
                            subtask_revision=0,
                        )
                        if self.cost_ledger is not None
                        else None
                    )
                    resp = await async_create_chat_completion_with_compat(
                        self.transport,
                        registry=GLOBAL_CAPABILITY_REGISTRY,
                        cost_ledger=self.cost_ledger,
                        accounting_context=accounting_context,
                        model=self.model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.0,
                        max_tokens=300,
                    )
                    summary = resp.choices[0].message.content
                    self.contracts[task_id] = summary
                    logger.info(f"[HiRAG] Compressed node {task_id} context ({len(artifact)} -> {len(summary)} chars)")
                    return summary
                except (ModelAccountingError, ModelTransportError):
                    raise
                except Exception as e:
                    logger.warning(f"[HiRAG] Compression failed for {task_id}: {e}")
                    self.contracts[task_id] = artifact[:500] + "...(raw)"
                    return self.contracts[task_id]

        memory_manager = HierarchicalMemoryManager(
            self.async_model_transport,
            self.model,
            self.cost_ledger,
        )

        task_events = {t["id"]: asyncio.Event() for t in task_list}
        node_errors = {}

        # If context already has artifacts (from Tier-3 re-plans), preload their
        # actual outputs as downstream contracts even when the node is no longer
        # present in the current DAG.
        self.carried_over_artifacts = {}
        for task_id, existing_artifact in self.context.artifacts.items():
            existing_record = self._task_registry_record(task_id)
            existing_artifact_type = existing_record.artifact_type if existing_record else self._infer_artifact_type_from_content(existing_artifact)
            contract = (
                existing_artifact
                if len(existing_artifact) <= 1000
                else existing_artifact[:1000] + "\n... (carried-over actual artifact truncated)"
            )
            memory_manager.contracts[task_id] = contract
            memory_manager.artifacts[task_id] = existing_artifact[:50000]
            memory_manager.artifact_types[task_id] = existing_artifact_type
            memory_manager.artifact_profiles[task_id] = self._build_artifact_profile(
                task_id,
                existing_artifact_type,
                existing_record.path if existing_record else None,
                existing_artifact,
                None,
            )
            if task_id in task_events:
                task_events[task_id].set()
            else:
                self.carried_over_artifacts[task_id] = contract
        if isinstance(routing_bundles, dict):
            routing_bundles["_carried_over_artifacts"] = dict(self.carried_over_artifacts)

        async def _execute_node(idx, task):
            task_id = task.get("id", f"node_{idx}")
            if task_events[task_id].is_set():
                # Already completed in a previous replan
                return

            base_desc = task.get("description", "")
            routing_original_query = (
                routing_bundles.get("_original_query", "")
                if isinstance(routing_bundles, dict)
                else ""
            )
            original_query = task.get("original_query") or routing_original_query
            desc = self._augment_description_with_original_query(base_desc, original_query)
            depends_on = task.get("depends_on", [])
            artifact_type = task.get("artifact_type", "plaintext")
            output_ext = task.get("output_extension", "")
            explicit_delivery = self._explicit_final_deliverable_contract(
                subtask_id=task_id,
                task_list=task_list,
            )
            if explicit_delivery is not None and explicit_delivery.extension:
                output_ext = explicit_delivery.extension

            # Await dependencies
            for dep_id in depends_on:
                if dep_id in task_events:
                    await task_events[dep_id].wait()
                    if dep_id in node_errors:
                        upstream_failure = node_errors[dep_id]
                        node_errors[task_id] = (
                            TerminalFailureEnvelope.create(
                                responsibility="research",
                                failure_stage="dependency_cascade",
                                failure_code="upstream_dependency_failed",
                                run_id=(
                                    self.execution_ledger.run_id
                                    if self.execution_ledger
                                    else ""
                                ),
                                subtask_id=task_id,
                                primary_failure_sha256=(
                                    upstream_failure.failure_sha256
                                    if isinstance(
                                        upstream_failure, TerminalFailureEnvelope
                                    )
                                    else None
                                ),
                            )
                            if isinstance(upstream_failure, TerminalFailureEnvelope)
                            else f"Dependency {dep_id} failed."
                        )
                        task_events[task_id].set()
                        return
                elif dep_id in self.context.artifacts:
                    logger.info(
                        "[Orchestrator] Dependency {} for {} satisfied by carried-over artifact.",
                        dep_id,
                        task_id,
                    )
                    continue
                else:
                    node_errors[task_id] = TerminalFailureEnvelope.create(
                        responsibility="research",
                        failure_stage="dag_connection",
                        failure_code="declared_dependency_missing",
                        run_id=(
                            self.execution_ledger.run_id if self.execution_ledger else ""
                        ),
                        subtask_id=task_id,
                    )
                    task_events[task_id].set()
                    return

            routing = routing_bundles.get(task_id, {})
            if routing.get("executable_plan_compiler") is not None:
                for dep_id in depends_on:
                    edge_failure = self._validate_committed_dependency_edge(
                        task=task,
                        producer_id=dep_id,
                        consumer_revision=routing["frozen_candidate_pool"].contract_projection.revision,
                    )
                    if edge_failure is None:
                        continue
                    responsibility, failure_code = edge_failure
                    node_errors[task_id] = TerminalFailureEnvelope.create(
                        responsibility=responsibility,
                        failure_stage="dag_edge_handoff",
                        failure_code=failure_code,
                        run_id=(
                            self.execution_ledger.run_id
                            if self.execution_ledger
                            else ""
                        ),
                        subtask_id=task_id,
                    )
                    task_events[task_id].set()
                    return
            mode = routing.get("execution_mode", "GENERATIVE_MODE")
            kwargs = dict(routing.get("kwargs", {}))
            kwargs["artifact_type"] = artifact_type

            logger.info(f"\nStarting {task_id} (deps satisfied: {depends_on}) | mode={mode}")

            # Step 1: DAG context resolution via HiRAG Contracts
            context_pieces = []
            if original_query:
                context_pieces.append(f"[Original User Query]\n{original_query}")
            for dep_id in depends_on:
                contract = memory_manager.contracts.get(dep_id, "N/A")
                exact_artifact = memory_manager.artifacts.get(
                    dep_id,
                    self.context.artifacts.get(dep_id, ""),
                )
                if exact_artifact:
                    preview = (
                        exact_artifact
                        if len(exact_artifact) <= 50000
                        else exact_artifact[:50000] + "\n... (actual artifact truncated)"
                    )
                    context_pieces.append(f"[{dep_id} actual artifact]\n{preview}")
                if contract and contract != exact_artifact:
                    context_pieces.append(f"[{dep_id} interface contract]\n{contract}")
            context_data = "\n".join(context_pieces) if context_pieces else "No dependencies."
            expected = task.get("expected_output", "") or task.get("description", "")
            task_output_contract = self._derive_output_contract_from_task(task)
            local_file_source = "\n".join(
                [
                    desc,
                    expected,
                    "\n".join(task_output_contract.grounding_requirements),
                ]
            )
            resolved_file_context = self._extract_local_file_context(local_file_source)
            if resolved_file_context:
                context_data += f"\n\n--- [Resolved Local File Context] ---\n{resolved_file_context}\n"
            context_packet = self._build_context_packet(
                task,
                task_list,
                memory_manager,
                context_data,
                resolved_file_context,
            )
            routing["context_packet"] = context_packet.model_dump(mode="json")

            from .resource_compatibility import current_node_contract_text
            from pydantic import ValidationError

            # Carry every declared field through execution; normalize only runtime values.
            try:
                subtask_model = Subtask.model_validate({
                    **task,
                    "id": task_id,
                    "role": task.get("role", ""),
                    "description": base_desc,
                    "expected_output": expected,
                    "depends_on": list(depends_on),
                    "dependency_inputs": list(task.get("dependency_inputs") or ()),
                    "incoming_edge_contracts": list(task.get("incoming_edge_contracts") or ()),
                    "artifact_type": artifact_type,
                    "output_extension": output_ext,
                    "output_contract": context_packet.current_output_contract,
                })
            except ValidationError as exc:
                node_errors[task_id] = TerminalFailureEnvelope.create(
                    responsibility="framework",
                    failure_stage="runtime_subtask_projection",
                    failure_code="runtime_subtask_contract_invalid",
                    exception=exc,
                    run_id=self.execution_ledger.run_id if self.execution_ledger else "",
                    subtask_id=task_id,
                )
                task_events[task_id].set()
                return
            node_expected = current_node_contract_text(subtask_model)
            subtask_model.expected_output = node_expected

            # -- Tier 1: Local Dumb Execution & Fixing --
            node_success = False
            result = None
            evaluation_contract_holder: Dict[str, Any] = {}
            if routing.get("routing_session") is not None and routing.get("router_runtime") is not None:
                node_success, result = await self._execute_routing_session(
                    subtask=subtask_model,
                    context_data=context_data,
                    artifact_type=artifact_type,
                    expected=node_expected,
                    routing=routing,
                    original_query=original_query,
                    evaluation_contract_holder=evaluation_contract_holder,
                )

                if node_success and result and result.is_success:
                    formal_publication = routing.get("executable_plan_compiler") is not None
                    exact_formal_records = self._formal_final_runtime_records.pop(
                        task_id, ()
                    )
                    exact_formal_record = (
                        exact_formal_records[0] if exact_formal_records else None
                    )
                    if formal_publication and exact_formal_record is not None:
                        record = exact_formal_record
                        self.artifact_registry.by_task[task_id] = record
                    else:
                        record = self._write_task_artifact_and_aliases(
                            task_id,
                            artifact_type,
                            output_ext,
                            result.output_data,
                            context_packet.current_output_contract,
                        )
                    if formal_publication:
                        produced_status = list(
                            result.cost_metric.get("formal_produced_file_status") or []
                        )
                        ok_contract = all(
                            not bool(item.get("required", True))
                            or item.get("status") == "present"
                            for item in produced_status
                            if isinstance(item, Mapping)
                        )
                        contract_failure = "contract_produced_file_missing"
                        contract_reason = contract_failure
                    else:
                        source_overlays, overlay_warnings = self.source_overlay_writer.register_task_overlays(
                            task_id,
                            task,
                            artifact_type,
                            result.output_data,
                            context_packet.current_output_contract,
                            record,
                        )
                        if source_overlays:
                            result.cost_metric["source_overlays"] = source_overlays
                        if overlay_warnings:
                            existing_warnings = result.cost_metric.setdefault("execution_warnings", [])
                            if isinstance(existing_warnings, list):
                                existing_warnings.extend(overlay_warnings)
                        upstream_profiles_for_lineage = [
                            memory_manager.artifact_profiles[dep_id]
                            for dep_id in depends_on
                            if dep_id in getattr(memory_manager, "artifact_profiles", {})
                        ]
                        derived_artifacts, lineage_warnings = self._register_final_derived_artifacts(
                            task_id,
                            artifact_type,
                            result.output_data,
                            upstream_profiles_for_lineage,
                        )
                        if derived_artifacts:
                            result.cost_metric["derived_final_artifacts"] = derived_artifacts
                        if lineage_warnings:
                            result.cost_metric["lineage_warnings"] = lineage_warnings
                        step_side_events = self._materialize_side_artifacts_from_step_outputs(
                            task_id,
                            context_packet.current_output_contract,
                            record,
                        )
                        if step_side_events:
                            result.cost_metric["step_output_side_artifact_materialization"] = step_side_events
                            self._append_trace(
                                "step_output_side_artifact_materialization_trace",
                                {"subtask_id": task_id, "events": step_side_events},
                            )
                        side_artifact_events = await self._attempt_required_side_artifact_materialization(
                            task_id,
                            task,
                            context_packet.current_output_contract,
                            record,
                            routing.get("resource_index", {}),
                            context_packet,
                        )
                        if side_artifact_events:
                            result.cost_metric["side_artifact_materialization"] = side_artifact_events
                            self._append_trace(
                                "side_artifact_materialization_trace",
                                {
                                    "subtask_id": task_id,
                                    "events": side_artifact_events,
                                },
                            )
                        textual_side_events = self._materialize_textual_side_artifacts_from_final_output(
                            task_id,
                            context_packet.current_output_contract,
                            record,
                            result.output_data,
                        )
                        if textual_side_events:
                            result.cost_metric["textual_side_artifact_materialization"] = textual_side_events
                            self._append_trace(
                                "textual_side_artifact_materialization_trace",
                                {
                                    "subtask_id": task_id,
                                    "events": textual_side_events,
                                },
                            )
                        ok_contract, contract_failure, contract_reason, produced_status = self._check_required_produced_files(
                            task_id,
                            context_packet.current_output_contract,
                            record,
                        )
                    result.cost_metric["produced_file_status"] = produced_status
                    self._sync_latest_attempt_artifact_status(routing, result)
                    if not ok_contract:
                        result.is_success = False
                        result.error_log = contract_reason
                        result.cost_metric["failure_type"] = contract_failure
                        if formal_publication:
                            contract_envelope = TerminalFailureEnvelope.create(
                                responsibility="research",
                                failure_stage="output_contract",
                                failure_code=contract_failure,
                                response_received=True,
                                run_id=(
                                    self.execution_ledger.run_id
                                    if self.execution_ledger
                                    else ""
                                ),
                                subtask_id=task_id,
                            )
                            result.cost_metric["failure"] = contract_envelope.model_dump(
                                mode="json", exclude={"failure_sha256", "protocol"}
                            )
                        routing.setdefault("execution_failures", []).append(
                            {
                                "failure_type": contract_failure,
                                "failure_reason": contract_reason,
                                "produced_file_status": produced_status,
                            }
                        )
                        self._record_node_outcome(
                            routing,
                            result,
                            success=False,
                            failure_type=contract_failure,
                            failure_reason=contract_reason,
                        )
                        node_errors[task_id] = self._node_failure_summary(task_id, result)
                        task_events[task_id].set()
                        return

                    if formal_publication:
                        try:
                            publication = await self._publish_formal_artifact(
                                subtask=subtask_model,
                                task_list=task_list,
                                routing=routing,
                                result=result,
                                artifact_type=artifact_type,
                                output_ext=output_ext,
                                original_public_objective=original_query,
                                produced_file_status=produced_status,
                                record=record,
                                records=exact_formal_records,
                                evaluation_contract=evaluation_contract_holder.get("contract"),
                                validation_step=evaluation_contract_holder.get("validation_step"),
                            )
                        except asyncio.CancelledError:
                            raise
                        except Exception as exc:
                            from .artifact_semantics import OutputContractViolation
                            # Keep a path-free diagnostic for failures before the
                            # artifact ledger can record its first stage event.
                            origin = exc.__traceback__
                            while origin is not None and origin.tb_next is not None:
                                origin = origin.tb_next
                            raw_code = str(exc)
                            safe_code = (
                                raw_code
                                if re.fullmatch(r"[a-z][a-z0-9_:-]{0,95}", raw_code)
                                else "unstructured"
                            )
                            logger.error(
                                "[ArtifactPublication] type={} code={} function={} line={}",
                                type(exc).__name__,
                                safe_code,
                                origin.tb_frame.f_code.co_name if origin is not None else "unknown",
                                origin.tb_lineno if origin is not None else 0,
                            )
                            is_contract_failure = isinstance(exc, OutputContractViolation)
                            publication_failure = TerminalFailureEnvelope.create(
                                responsibility="research" if is_contract_failure else "framework",
                                failure_stage="output_contract" if is_contract_failure else "artifact_publication",
                                failure_code=exc.failure_code if is_contract_failure else "artifact_publication_failed",
                                exception=exc,
                                run_id=(
                                    self.execution_ledger.run_id
                                    if self.execution_ledger
                                    else ""
                                ),
                                subtask_id=task_id,
                            )
                            result.is_success = False
                            result.error_log = publication_failure.failure_code
                            result.cost_metric.update(
                                {
                                    "failure_type": publication_failure.failure_code,
                                    "failure_layer": publication_failure.responsibility,
                                    "failure": publication_failure.model_dump(
                                        mode="json",
                                        exclude={"failure_sha256", "protocol"},
                                    ),
                                    "task_success": False,
                                }
                            )
                            self._record_node_outcome(
                                routing,
                                result,
                                success=False,
                                failure_type=publication_failure.failure_code,
                                failure_reason=publication_failure.failure_code,
                            )
                            node_errors[task_id] = publication_failure
                            task_events[task_id].set()
                            return
                        if publication.status != "committed" or publication.committed is None:
                            result.is_success = False
                            failure_type = publication.failure_code or (
                                "artifact_quality_failure"
                                if publication.status == "fail"
                                else "evaluation_inconclusive"
                                if publication.status in {"inconclusive", "protocol_inconclusive"}
                                else f"evaluation_{publication.status}"
                            )
                            result.error_log = failure_type
                            failure_envelope = publication.terminal_failure
                            if failure_envelope is None:
                                failure_envelope = TerminalFailureEnvelope.create(
                                    responsibility=(
                                        "infrastructure"
                                        if publication.status == "infrastructure_failure"
                                        else "budget"
                                        if publication.status == "budget_failure"
                                        else "framework"
                                        if publication.status == "framework_failure"
                                        else "research"
                                    ),
                                    failure_stage="artifact_publication",
                                    failure_code=failure_type,
                                    run_id=(
                                        self.execution_ledger.run_id
                                        if self.execution_ledger
                                        else ""
                                    ),
                                    subtask_id=task_id,
                                )
                            result.cost_metric.update(
                                {
                                    "failure_type": failure_type,
                                    "failure_layer": failure_envelope.responsibility,
                                    "failure": failure_envelope.model_dump(
                                        mode="json", exclude={"failure_sha256", "protocol"}
                                    ),
                                    "task_success": False,
                                }
                            )
                            self._record_node_outcome(
                                routing,
                                result,
                                success=False,
                                failure_type=failure_type,
                                failure_reason=failure_type,
                            )
                            node_errors[task_id] = failure_envelope
                            task_events[task_id].set()
                            return
                        self.context.add_committed_artifact(publication.committed)
                        committed_path = os.path.abspath(
                            os.path.join(
                                self.artifact_store.output_dir,
                                publication.committed.blob_locator,
                            )
                        )
                        record.metadata["committed_manifest_sha256"] = (
                            publication.committed.committed_manifest_sha256
                        )
                        record.metadata["committed_blob_locator"] = (
                            publication.committed.blob_locator
                        )
                        record.path = committed_path
                        record.metadata["execution_contract"] = copy.deepcopy(evaluation_contract_holder["contract"])
                    else:
                        self.context.add_result(task_id, result.output_data)
                    if formal_publication:
                        # Exact committed content remains authoritative.  A
                        # derived HiRAG view is optional and must never replace
                        # or precede the commit; v1 therefore retains the exact
                        # artifact without an extra semantic call.
                        memory_manager.artifact_types[task_id] = artifact_type
                        memory_manager.artifacts[task_id] = result.output_data
                        memory_manager.contracts[task_id] = result.output_data
                    else:
                        await memory_manager.compress_artifact(
                            task_id,
                            desc,
                            result.output_data,
                            artifact_type,
                        )

                    profile = self._build_artifact_profile(
                        task_id,
                        artifact_type,
                        record.path,
                        result.output_data,
                        result,
                    )
                    memory_manager.artifact_profiles[task_id] = profile
                    routing["artifact_profile"] = profile.model_dump(mode="json")
                    routing_bundles.setdefault("_artifact_profiles", {})[task_id] = profile.model_dump(mode="json")
                    self._record_node_outcome(routing, result, success=True)
                else:
                    failure_type, failure_reason = self._classify_runtime_failure(result) if result is not None else ("execution_failed", "Node produced no result.")
                    self._record_node_outcome(
                        routing,
                        result,
                        success=False,
                        failure_type=failure_type,
                        failure_reason=failure_reason,
                    )
                    node_errors[task_id] = self._node_failure_summary(task_id, result)

                task_events[task_id].set()
                return

            if mode == "BYPASS_MODE":
                if self.execution_substrate is not None:
                    raise RuntimeError(
                        "UNBOUND_RUNTIME_PATH:external_legacy_bypass_forbidden"
                    )
                dumb_exec = DumbExecutor(timeout_sec=kwargs.get("timeout_sec", 180))
                cmd_candidate = kwargs.get("command", desc)
                args_candidate = kwargs.get("args", [])
                runtime_handle, prep_event_id, prep_failure = await self._prepare_step_runtime(
                    task_id=task_id,
                    step_id="legacy_bypass",
                    execution_network_required=bool(kwargs.get("network_required", False)),
                    phase="base",
                )
                if prep_failure is not None:
                    prep_failure["preparation_event_id"] = prep_event_id
                    result = self._runtime_preparation_failure_result(prep_failure)
                    self._record_node_outcome(
                        routing,
                        result,
                        success=False,
                        failure_type=prep_failure["failure_type"],
                        failure_reason=prep_failure["failure_reason"],
                    )
                    node_errors[task_id] = self._node_failure_summary(task_id, result)
                    task_events[task_id].set()
                    return

                for bypass_attempt in range(1, 4):
                    kw_copy = dict(kwargs)
                    kw_copy.pop("install_packages", None)
                    kw_copy.pop("allow_dynamic_install", None)
                    kw_copy["command"] = cmd_candidate
                    kw_copy["args"] = args_candidate
                    kw_copy["runtime_environment"] = runtime_handle
                    kw_copy["network_required"] = bool(
                        kwargs.get("network_required", False)
                    )
                    
                    result = await dumb_exec.execute(desc, context_data, **kw_copy)
                    if result.is_success:
                        node_success = True
                        break
                    else:
                        logger.warning(f"[Tier-1 Fallback] Bypass failed: {result.error_log}")
                        if bypass_attempt < 3:
                            cmd_candidate, args_candidate = await self._router_fix_command(
                                cmd_candidate,
                                args_candidate,
                                result.error_log,
                                subtask_id=task_id,
                            )
                
                if not node_success:
                    logger.error("[Tier-1 Factor exhausted]. Down-grading to Generative...")
                    mode = "GENERATIVE_MODE"
                    context_data += f"\n\n[System Note: Physical tool '{kwargs.get('command')}' failed. Please generate.]"

            # -- Tier 2: Generative Mode with LLM Validation --
            if mode == "GENERATIVE_MODE":
                smart_exec = SmartExecutor(
                    api_key=self.llm_api_key,
                    base_url=self.llm_base_url,
                    model=self.model,
                    cost_ledger=self.cost_ledger,
                    transport=self.async_model_transport,
                )
                fallbacks = list(routing.get("fallback_models", []))
                max_eval_retries = 3
                current_model = self.model
                eval_feedback = ""
                kw_copy = dict(kwargs)
                kw_copy["final_output_contract"] = self._build_final_output_contract(
                    base_desc,
                    node_expected,
                    artifact_type,
                    context_data,
                )
                
                for eval_round in range(1, max_eval_retries + 1):
                    kw_copy["model"] = current_model
                    kw_copy["repair_feedback"] = eval_feedback
                    kw_copy["accounting_stage"] = "full_generation"
                    kw_copy["subtask_id"] = task_id
                    kw_copy["subtask_revision"] = 0
                    result = await smart_exec.execute(base_desc, context_data, **kw_copy)
                    
                    if not result.is_success:
                        passed_gates = False
                        eval_feedback = result.error_log or "Execution crashed"
                    else:
                        passed_gates = True
                        is_valid, struct_err = SmartExecutor.validate_artifact(result.output_data, artifact_type)
                        if not is_valid:
                            eval_feedback = f"format_invalid: {struct_err}"
                            passed_gates = False
                        
                        if passed_gates and node_expected:
                            eval_result = await self.router_evaluate_result(
                                base_desc,
                                node_expected,
                                result.output_data,
                                artifact_type=artifact_type,
                                subtask_id=task_id,
                            )
                            result.cost_metric["evaluation_result"] = eval_result.model_dump(mode="json")
                            if eval_result.verdict == EvaluationVerdict.INCONCLUSIVE:
                                logger.warning(
                                    "[Evaluator] Inconclusive judgment for {}; continuing with evaluator_noise label.",
                                    task_id,
                                )
                                result.cost_metric["evaluation_soft_pass"] = True
                            elif not eval_result.passed:
                                eval_feedback = (
                                    eval_result.repair_hint
                                    or "; ".join(eval_result.critical_issues)
                                    or eval_result.failure_type.value
                                )
                                if self._is_evaluator_scope_warning(
                                    subtask_model,
                                    eval_result,
                                    artifact_type,
                                    eval_feedback,
                                ):
                                    self._append_execution_warning(
                                        result,
                                        "evaluator_scope_warning",
                                        eval_feedback,
                                        evaluator_failure_type=eval_result.failure_type.value,
                                    )
                                    result.cost_metric["evaluation_scope_soft_pass"] = True
                                else:
                                    passed_gates = False
                                    if "evaluator json was malformed" in str(eval_feedback or "").lower():
                                        self._append_execution_warning(
                                            result,
                                            "evaluator_inconclusive",
                                            eval_feedback,
                                            evaluator_failure_type=eval_result.failure_type.value,
                                        )
                                        result.cost_metric["evaluation_malformed_soft_pass"] = True
                                        passed_gates = True
                    
                    if passed_gates:
                        logger.success(f"[Eval] {task_id} PASSED (round {eval_round})")
                        node_success = True
                        break
                        
                    if fallbacks and eval_round < max_eval_retries:
                        is_code_err = (
                            "format_invalid" in eval_feedback
                            or "Syntax" in eval_feedback
                            or "code" in eval_feedback.lower()
                        )
                        
                        current_cap = next((m.get("capabilities", {}) for m in fallbacks if m.get("id") == current_model), {})
                        if not current_cap: current_cap = {"cost_level": 1, "code_score": 0.5, "logic_score": 0.5}
                        
                        candidates = []
                        for m in fallbacks:
                            cap = m.get("capabilities", {})
                            if not cap: continue
                            if m.get("id") == current_model: continue
                            
                            # Escalation logic based on CapabilityMatrix
                            if is_code_err and cap.get("code_score", 0.0) > current_cap.get("code_score", 0.0):
                                candidates.append(m)
                            elif not is_code_err and cap.get("logic_score", 0.0) > current_cap.get("logic_score", 0.0):
                                candidates.append(m)
                            elif cap.get("cost_level", 0) > current_cap.get("cost_level", 0):
                                candidates.append(m)
                        
                        if candidates:
                            candidates.sort(key=lambda x: (x.get("capabilities", {}).get("cost_level", 99), -x.get("capabilities", {}).get("logic_score", 0.0)))
                            current_model = candidates[0].get("id", random.choice(fallbacks).get("id"))
                            logger.warning(f"[Tier-2 Fallback] Capability Escalation Rescheduling {task_id} to {current_model}")
                            context_data += f"\n\n--- [Evaluator Feedback] ---\nFailure feedback: {eval_feedback}\n"
                        else:
                            logger.warning(f"[Tier-2] No stronger models available for escalation.")
                            break
                    else:
                        break

            # Step 4: Result handling & File save
            if node_success and result and result.is_success:
                record = self._write_task_artifact_and_aliases(
                    task_id,
                    artifact_type,
                    output_ext,
                    result.output_data,
                    context_packet.current_output_contract,
                )
                source_overlays, overlay_warnings = self.source_overlay_writer.register_task_overlays(
                    task_id,
                    task,
                    artifact_type,
                    result.output_data,
                    context_packet.current_output_contract,
                    record,
                )
                if source_overlays:
                    result.cost_metric["source_overlays"] = source_overlays
                if overlay_warnings:
                    existing_warnings = result.cost_metric.setdefault("execution_warnings", [])
                    if isinstance(existing_warnings, list):
                        existing_warnings.extend(overlay_warnings)
                upstream_profiles_for_lineage = [
                    memory_manager.artifact_profiles[dep_id]
                    for dep_id in depends_on
                    if dep_id in getattr(memory_manager, "artifact_profiles", {})
                ]
                derived_artifacts, lineage_warnings = self._register_final_derived_artifacts(
                    task_id,
                    artifact_type,
                    result.output_data,
                    upstream_profiles_for_lineage,
                )
                if derived_artifacts:
                    result.cost_metric["derived_final_artifacts"] = derived_artifacts
                if lineage_warnings:
                    result.cost_metric["lineage_warnings"] = lineage_warnings
                step_side_events = self._materialize_side_artifacts_from_step_outputs(
                    task_id,
                    context_packet.current_output_contract,
                    record,
                )
                if step_side_events:
                    result.cost_metric["step_output_side_artifact_materialization"] = step_side_events
                    self._append_trace(
                        "step_output_side_artifact_materialization_trace",
                        {"subtask_id": task_id, "events": step_side_events},
                    )
                side_artifact_events = await self._attempt_required_side_artifact_materialization(
                    task_id,
                    task,
                    context_packet.current_output_contract,
                    record,
                    routing.get("resource_index", {}),
                    context_packet,
                )
                if side_artifact_events:
                    result.cost_metric["side_artifact_materialization"] = side_artifact_events
                    self._append_trace(
                        "side_artifact_materialization_trace",
                        {
                            "subtask_id": task_id,
                            "events": side_artifact_events,
                        },
                    )
                textual_side_events = self._materialize_textual_side_artifacts_from_final_output(
                    task_id,
                    context_packet.current_output_contract,
                    record,
                    result.output_data,
                )
                if textual_side_events:
                    result.cost_metric["textual_side_artifact_materialization"] = textual_side_events
                    self._append_trace(
                        "textual_side_artifact_materialization_trace",
                        {
                            "subtask_id": task_id,
                            "events": textual_side_events,
                        },
                    )
                ok_contract, contract_failure, contract_reason, produced_status = self._check_required_produced_files(
                    task_id,
                    context_packet.current_output_contract,
                    record,
                )
                result.cost_metric["produced_file_status"] = produced_status
                self._sync_latest_attempt_artifact_status(routing, result)
                if not ok_contract:
                    result.is_success = False
                    result.error_log = contract_reason
                    result.cost_metric["failure_type"] = contract_failure
                    routing.setdefault("execution_failures", []).append(
                        {
                            "failure_type": contract_failure,
                            "failure_reason": contract_reason,
                            "produced_file_status": produced_status,
                        }
                    )
                    self._record_node_outcome(
                        routing,
                        result,
                        success=False,
                        failure_type=contract_failure,
                        failure_reason=contract_reason,
                    )
                    node_errors[task_id] = self._node_failure_summary(task_id, result)
                    task_events[task_id].set()
                    return

                self.context.add_result(task_id, result.output_data)
                
                # Compress into HiRAG Memory
                await memory_manager.compress_artifact(
                    task_id,
                    desc,
                    result.output_data,
                    artifact_type,
                )

                profile = self._build_artifact_profile(
                    task_id,
                    artifact_type,
                    record.path,
                    result.output_data,
                    result,
                )
                memory_manager.artifact_profiles[task_id] = profile
                routing["artifact_profile"] = profile.model_dump(mode="json")
                routing_bundles.setdefault("_artifact_profiles", {})[task_id] = profile.model_dump(mode="json")
                self._record_node_outcome(routing, result, success=True)
                
            else:
                if result is None:
                    failure_type, failure_reason = (
                        "execution_failed",
                        "Node produced no result.",
                    )
                elif bool(getattr(self, "_formal_execution_active", False)):
                    structured_failure = result.cost_metric.get("failure")
                    if not isinstance(structured_failure, Mapping):
                        raise RuntimeError("formal_provider_failure_contract_missing")
                    failure_type = str(
                        structured_failure.get("failure_code")
                        or "formal_resource_execution_failed"
                    )
                    failure_reason = failure_type
                else:
                    failure_type, failure_reason = self._classify_runtime_failure(
                        result
                    )
                self._record_node_outcome(
                    routing,
                    result,
                    success=False,
                    failure_type=failure_type,
                    failure_reason=failure_reason,
                )
                node_errors[task_id] = self._node_failure_summary(task_id, result)

            # Signal downstream listeners
            task_events[task_id].set()

        # Scatter the tasks and let topological Event waits orchestrate scheduling automatically!
        await asyncio.gather(*[_execute_node(idx, task) for idx, task in enumerate(task_list)])

        if node_errors:
            failed_id = list(node_errors.keys())[0]
            logger.error(f"Pipeline halted due to cascading errors. First failure: {failed_id}")
            failure_records: list[
                tuple[
                    str,
                    TerminalFailureEnvelope,
                    TerminalFailureEnvelope,
                    str | None,
                ]
            ] = []
            for task_id, node_failure in node_errors.items():
                if not isinstance(node_failure, TerminalFailureEnvelope):
                    node_failure = TerminalFailureEnvelope.create(
                        responsibility="research",
                        failure_stage="legacy_node_execution",
                        failure_code="legacy_node_unrecoverable",
                        run_id=(
                            self.execution_ledger.run_id
                            if self.execution_ledger
                            else ""
                        ),
                        subtask_id=task_id,
                    )
                routing = routing_bundles.get(task_id, {})
                recovery = (
                    routing.get("recovery")
                    if isinstance(routing, Mapping)
                    and isinstance(routing.get("recovery"), Mapping)
                    else {}
                )

                def recovery_failure(key: str) -> TerminalFailureEnvelope | None:
                    payload = recovery.get(key)
                    if not isinstance(payload, Mapping):
                        return None
                    try:
                        return TerminalFailureEnvelope.model_validate(payload)
                    except Exception:
                        return None

                failure_records.append(
                    (
                        task_id,
                        recovery_failure("primary_failure") or node_failure,
                        recovery_failure("terminal_failure") or node_failure,
                        (
                            str(recovery.get("recovery_outcome"))
                            if recovery.get("recovery_outcome") is not None
                            else None
                        ),
                    )
                )

            first_failure = failure_records[0][1]
            terminal_failure = highest_severity_terminal_failure(
                [item[2] for item in failure_records]
            )
            recovery_outcomes = tuple(
                {
                    "subtask_id": task_id,
                    "outcome": outcome,
                }
                for task_id, _primary, _terminal, outcome in sorted(
                    failure_records,
                    key=lambda item: item[0],
                )
                if outcome is not None
            )
            causal_chain: list[dict[str, Any]] = []

            def append_failure(
                *,
                subtask_id: str,
                kind: str,
                failure: TerminalFailureEnvelope,
            ) -> None:
                causal_chain.append(
                    {
                        "sequence": len(causal_chain),
                        "kind": kind,
                        "subtask_id": subtask_id,
                        "responsibility": failure.responsibility,
                        "failure_stage": failure.failure_stage,
                        "failure_code": failure.failure_code,
                        "failure_sha256": failure.failure_sha256,
                    }
                )

            for task_id, primary, terminal, outcome in failure_records:
                append_failure(
                    subtask_id=task_id,
                    kind="primary_failure",
                    failure=primary,
                )
                if outcome not in {None, "none"}:
                    causal_chain.append(
                        {
                            "sequence": len(causal_chain),
                            "kind": "recovery_outcome",
                            "subtask_id": task_id,
                            "outcome": outcome,
                        }
                    )
                if terminal.failure_sha256 != primary.failure_sha256:
                    append_failure(
                        subtask_id=task_id,
                        kind="terminal_failure",
                        failure=terminal,
                    )
            raise NodeUnrecoverableError(
                first_failure,
                terminal_failure=terminal_failure,
                recovery_outcomes=recovery_outcomes,
                causal_chain=causal_chain,
            )

        logger.success(f"\nAll {n} nodes executed successfully via DAG Parallel Plane!")
        return self.context
