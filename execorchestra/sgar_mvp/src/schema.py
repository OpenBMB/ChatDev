"""
S-GAR Contract Layer (schema.py)
================================
Defines the core data contracts shared across all S-GAR subsystems:
Routing Model (Planner + Router), Execution Layer, and Entry Layer.

All inter-module communication flows through these Pydantic V2 models
to enforce strict type safety at serialization boundaries.
"""

import json
import math
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from .pipeline_control import (
    CandidatePoolSnapshot,
    RetrievalConfidenceEvidence,
    SubtaskRevisionRef,
    canonical_sha256,
)
from .terminal_failure import TerminalFailureEnvelope
from .formal_contracts import (
    ExecutionResourceRequirementV1,
    NodeSemanticContractV2,
    SemanticEdgeContractV2,
    SemanticRequirementDeclarationV1,
)


# ─────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────

class ArtifactType(str, Enum):
    """Expected output artifact type produced by an execution node."""
    CODE = "code"
    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"
    PLAINTEXT = "plaintext"
    FILE = "file"
    DIRECTORY = "directory"
    BUNDLE = "bundle"


class ExecutionMode(str, Enum):
    """Physical execution routing mode determined by the Router."""
    BYPASS = "BYPASS_MODE"
    SEMI_GENERATIVE = "SEMI_GENERATIVE_MODE"
    FULL_GENERATIVE = "FULL_GENERATIVE_MODE"
    # Backward-compatible legacy mode. New routing code should prefer
    # SEMI_GENERATIVE for model/agent-assisted execution.
    GENERATIVE = "GENERATIVE_MODE"


class ManifestType(str, Enum):
    """Resource type registered in the resource pool."""
    MODEL = "Model"
    AGENT = "Agent"
    SKILL = "Skill"
    TOOL = "Tool"
    RESOURCE = "Resource"
    DEVICE = "Device"
    # Backward-compatible aliases for older modules.
    GENERATIVE_MODEL = "Model"
    PHYSICAL_TOOL = "Tool"


class EvaluationVerdict(str, Enum):
    """Controlled evaluator verdict for training-safe quality labels."""
    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"


class EvaluationFailureType(str, Enum):
    """Failure taxonomy emitted by the structured Evaluator."""
    NONE = "none"
    FORMAT_INVALID = "format_invalid"
    MISSING_REQUIRED_CONTENT = "missing_required_content"
    DEPENDENCY_NOT_USED = "dependency_not_used"
    FACTUAL_MISMATCH = "factual_mismatch"
    CONTRACT_VIOLATION = "contract_violation"
    HALLUCINATED_CONTENT = "hallucinated_content"
    TOOL_OUTPUT_MISMATCH = "tool_output_mismatch"
    EVALUATOR_INCONCLUSIVE = "evaluator_inconclusive"


class TrainingLabel(str, Enum):
    """High-level sample label used by downstream training pipelines."""
    GOOD_CASE = "good_case"
    REPAIRABLE_CASE = "repairable_case"
    BAD_RESOURCE_PLAN = "bad_resource_plan"
    BAD_MODEL_OUTPUT = "bad_model_output"
    INFRA_NOISE = "infra_noise"
    EVALUATOR_NOISE = "evaluator_noise"
    CAPABILITY_MISMATCH = "capability_mismatch"


class ExecutionStrictness(str, Enum):
    """Runtime strictness policy for execution validation."""
    BALANCED = "balanced"


class OperationKind(str, Enum):
    """Semantic Tool operation kinds describe what a Tool does;
    manifest runtime describes how it executes.
    """
    PRODUCE_ARTIFACT = "produce_artifact"
    INSPECT_INPUT = "inspect_input"
    RUN_TOOL = "run_tool"
    EXECUTE_SCRIPT = "execute_script"
    RUN_TESTS = "run_tests"
    VALIDATE_ARTIFACT = "validate_artifact"
    SYNTHESIZE_FINAL = "synthesize_final"
    CALL_MODEL = "call_model"
    CALL_AGENT = "call_agent"
    APPLY_CONTEXT_HINT = "apply_context_hint"
    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    EDIT_FILE = "edit_file"
    LIST_DIRECTORY = "list_directory"
    SEARCH_FILES = "search_files"
    INSPECT_METADATA = "inspect_metadata"
    CREATE_DIRECTORY = "create_directory"
    MOVE_PATH = "move_path"
    INSPECT_VERSION_CONTROL = "inspect_version_control"
    MUTATE_VERSION_CONTROL = "mutate_version_control"
    EXTRACT_DOCUMENT = "extract_document"
    CONVERT_FORMAT = "convert_format"
    PARSE_DATA = "parse_data"
    QUERY_DATA = "query_data"
    TRANSFORM_DATA = "transform_data"
    ANALYZE_DATA = "analyze_data"
    ANALYZE_CODE = "analyze_code"
    LINT_CODE = "lint_code"
    FORMAT_CODE = "format_code"
    AUDIT_SECURITY = "audit_security"
    QUERY_API = "query_api"
    SEARCH_KNOWLEDGE = "search_knowledge"
    LOOKUP_REFERENCE = "lookup_reference"
    RESOLVE_NETWORK = "resolve_network"
    FETCH_LIVE_DATA = "fetch_live_data"
    ANALYZE_TEXT = "analyze_text"
    COMPUTE_MATH = "compute_math"
    GENERATE_MEDIA = "generate_media"


class TaskStage(str, Enum):
    """Planner-level node stage used only for lightweight execution compatibility."""
    ANALYZE_CONTEXT = "analyze_context"
    IMPLEMENT_SOURCE = "implement_source"
    GENERATE_TESTS = "generate_tests"
    RUN_TESTS = "run_tests"
    SYNTHESIZE_FINAL = "synthesize_final"
    PRODUCE_ARTIFACT = "produce_artifact"
    ENVIRONMENT_SETUP = "environment_setup"


class PlannerExecutionMode(str, Enum):
    """Planner intent without pre-binding a concrete resource."""

    RESOURCE_GROUNDED = "resource_grounded"
    GENERATIVE = "generative"
    HYBRID = "hybrid"


class NodeFailureCategory(str, Enum):
    """Broad failure category used to decide whether graph-level replan is allowed."""
    SYSTEM_DETERMINISTIC = "system_deterministic"
    PROVIDER = "provider"
    MODEL_CONTENT = "model_content"
    RESOURCE_SELECTION = "resource_selection"
    BUDGET = "budget"
    DAG_CONTRACT = "dag_contract"
    UNKNOWN = "unknown"


class NodeExecutionStatus(str, Enum):
    """Final node execution status under the selected strictness policy."""
    SUCCESS = "success"
    SUCCESS_WITH_WARNINGS = "success_with_warnings"
    STRUCTURED_FAILURE = "structured_failure"


class NodeExecutionOutcome(BaseModel):
    """Structured node outcome for stable reporting and replan decisions."""
    status: NodeExecutionStatus = Field(...)
    strictness: ExecutionStrictness = Field(default=ExecutionStrictness.BALANCED)
    failure_category: Optional[NodeFailureCategory] = Field(default=None)
    failure_type: Optional[str] = Field(default=None)
    failure_reason: Optional[str] = Field(default=None)
    retry_allowed: bool = Field(default=False)
    graph_replan_allowed: bool = Field(default=False)
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    terminal_failure: Optional[TerminalFailureEnvelope] = Field(default=None)


# ─────────────────────────────────────────────
# Mathematical Contract Primitives
# ─────────────────────────────────────────────

class Vector(BaseModel):
    """Dense vector representation in the S-GAR latent space."""
    embedding: List[float] = Field(..., description="Dense vector coefficients")
    dim: int = Field(..., description="Dimensionality of the vector")


class QueryRetrievalProfile(BaseModel):
    """Separated query representation for dual-path resource retrieval."""

    capability: Vector = Field(..., description="Query vector for capability matching")
    constraint: Optional[Vector] = Field(
        default=None,
        description="Optional query vector for explicitly enabled soft-constraint retrieval",
    )
    raw_query: Optional[Vector] = Field(
        default=None,
        description="Original task-query vector used by explicit multi-view retrieval",
    )
    capability_text: str = Field(default="", description="Auditable capability query text")
    constraint_text: str = Field(default="", description="Auditable soft-constraint query text")
    raw_query_text: str = Field(default="", description="Original unexpanded retrieval query")
    hard_requirements: Dict[str, Any] = Field(
        default_factory=dict,
        description="Deterministic task requirements; never embedded into v_con",
    )
    profile_version: str = Field(
        default="typed-query-v1",
        description="Query-profile construction version",
    )
    generation_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        exclude=True,
        description="Additive HyDE generation and model-accounting references.",
    )


class Utility(BaseModel):
    """Utility parameters for calculating the Advantage function Ap."""
    latency_ms: float = Field(..., description="Expected latency in milliseconds")
    cost_factor: float = Field(..., description="Abstract cost factor (token / API cost)")
    success_rate: float = Field(default=0.99, description="Historical success rate ∈ [0, 1]")


class CapabilityMatrix(BaseModel):
    """Capability slots for intelligent routing and cost-based fallbacks."""
    cost_level: int = Field(default=1, description="Higher integer means more expensive.")
    code_score: float = Field(default=0.5, description="Model code proficiency [0, 1]")
    logic_score: float = Field(default=0.5, description="Model logical reasoning [0, 1]")


class EvaluationDimensionScores(BaseModel):
    """Fixed evaluator scoring dimensions, each normalized to [0.0, 1.0]."""
    format_compliance: float = Field(default=0.0, ge=0.0, le=1.0)
    contract_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    dependency_grounding: float = Field(default=0.0, ge=0.0, le=1.0)
    factual_consistency: float = Field(default=0.0, ge=0.0, le=1.0)
    completeness: float = Field(default=0.0, ge=0.0, le=1.0)
    actionability: float = Field(default=0.0, ge=0.0, le=1.0)


class EvaluationResult(BaseModel):
    """Structured Router Evaluator result used for routing, repair, and training logs."""
    verdict: EvaluationVerdict = Field(..., description="pass, fail, or inconclusive")
    passed: bool = Field(
        default=False,
        description="Convenience boolean equivalent of verdict == pass",
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Evaluator confidence")
    failure_type: EvaluationFailureType = Field(..., description="Controlled failure taxonomy")
    dimension_scores: EvaluationDimensionScores = Field(
        default_factory=EvaluationDimensionScores,
        description="Fixed quality dimensions for training data",
    )
    critical_issues: List[str] = Field(
        default_factory=list,
        description="At most three concise blocking issues",
    )
    repair_hint: Optional[str] = Field(
        default=None,
        description="Concise repair hint when the failure is repairable",
    )
    training_label: TrainingLabel = Field(
        default=TrainingLabel.EVALUATOR_NOISE,
        description="Training sample category inferred by the evaluator",
    )
    profile_used: bool = Field(
        default=False,
        description="Whether evaluation used an artifact profile instead of full output",
    )
    escalated_full_output: bool = Field(
        default=False,
        description="Whether a profile-based evaluation was escalated to full output",
    )
    evaluator_model: Optional[str] = Field(default=None, description="Evaluator model ID")


class Manifest(BaseModel):
    """
    Unified mathematical contract M = (id, type, v_cap, v_con, U).

    Each resource (model, tool, skill) in the S-GAR resource pool is
    registered as a Manifest. The Router uses v_cap / v_con for similarity
    retrieval and U for advantage-based adjudication.
    """
    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Unique resource identifier")
    type: ManifestType = Field(..., description="Resource category")
    v_cap: Vector = Field(..., description="Capability vector (what it solves)")
    v_con: Vector = Field(..., description="Constraint vector (I/O & environment)")
    utility: Utility = Field(..., description="Utility metrics for routing")
    capabilities: Optional[CapabilityMatrix] = Field(default=None, description="Spectrum capabilities for Fallback routing")

    @property
    def advantage_score(self) -> float:
        """
        Advantage Parameter: Ap = (success_rate / cost_factor) × (1 / log₁₀(10 + latency_ms))
        Higher Ap indicates a more cost-effective resource.
        """
        latency_penalty = math.log10(10 + self.utility.latency_ms)
        return (self.utility.success_rate / (self.utility.cost_factor + 1e-3)) / latency_penalty


# ─────────────────────────────────────────────
# Planner Output Contracts
# ─────────────────────────────────────────────

_ARTIFACT_TYPE_ALIASES = {
    "text": "plaintext",
    "plain_text": "plaintext",
    "structured_analysis": "markdown",
    "analysis": "markdown",
    "report": "markdown",
    "document": "markdown",
    "doc": "markdown",
    "python": "code",
    "py": "code",
    "source_code": "code",
    "script": "code",
    "json_object": "json",
    "json_schema": "json",
    "csv_file": "csv",
    "instruction_hint": "plaintext",
    "planning_hint": "plaintext",
    "validator_hint": "plaintext",
    "tool_macro_hint": "plaintext",
    "agent_protocol_hint": "plaintext",
    "unused": "plaintext",
}


def _normalize_artifact_type_value(value: Any) -> Any:
    if isinstance(value, ArtifactType):
        return value
    if value is None:
        return None
    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    return _ARTIFACT_TYPE_ALIASES.get(normalized, normalized)


class ProducedFileContract(BaseModel):
    """Expected file produced by a subtask-level output contract."""
    path_hint: str = Field(..., description="Expected filename or relative path hint")
    artifact_type: str = Field(default="plaintext", description="File artifact type, such as csv/json/code")
    required: bool = Field(default=True, description="Whether the file is required")
    schema_hint: Any = Field(default=None, description="Optional schema, columns, or structural hint")

    @model_validator(mode="before")
    @classmethod
    def normalize_path_hint(cls, value: Any) -> Any:
        if isinstance(value, str):
            return {"path_hint": value}
        if isinstance(value, dict) and not value.get("path_hint"):
            for key in ("name", "path", "filename", "file"):
                if value.get(key):
                    updated = dict(value)
                    updated["path_hint"] = value[key]
                    return updated
        return value

    @field_validator("schema_hint", mode="before")
    @classmethod
    def normalize_schema_hint(cls, value: Any) -> Any:
        if value is None or isinstance(value, (str, bool, int, float)):
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("produced_file_schema_hint_not_json_serializable")
            return value
        if isinstance(value, (list, tuple, dict)):
            return json.loads(
                json.dumps(
                    value,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                )
            )
        raise ValueError("produced_file_schema_hint_not_json_serializable")


class RegexFindallAcceptanceProbe(BaseModel):
    """A bounded public-example oracle for a Python re.findall deliverable."""

    protocol: Literal["sgar-regex-findall-acceptance-probe-v1"]
    input_text: str = Field(max_length=2048)
    expected_matches: List[str] = Field(max_length=32)
    requirement_quote: str = Field(min_length=1, max_length=512)


from .evidence_requirements import EvidenceSourceDeclaration


class SubtaskOutputContract(EvidenceSourceDeclaration):
    """Stable node-level deliverable contract created by the Planner."""
    content_kind: Literal["value", "json_schema_document"] = "value"
    syntax_validator: Literal["python_regex", "python_regex_findall_string", "python_regex_findall_whole_match"] | None = None
    artifact_type: ArtifactType = Field(..., description="Final artifact type for the subtask")
    output_extension: str = Field(default="", description="Expected file extension for the final artifact")
    required_content: List[str] = Field(default_factory=list, description="Content that must appear in the artifact")
    produced_files: List[ProducedFileContract] = Field(default_factory=list)
    json_schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Authoritative JSON Schema for a JSON artifact. Natural-language schema hints "
            "and interface metadata are not substitutes for this field."
        ),
    )
    interface_contract: Dict[str, Any] = Field(default_factory=dict)
    grounding_requirements: List[str] = Field(default_factory=list)
    acceptance_criteria: List[str] = Field(default_factory=list)
    acceptance_probes: List[RegexFindallAcceptanceProbe] = Field(default_factory=list, max_length=4)
    downstream_consumers: List[str] = Field(default_factory=list)

    @field_validator("artifact_type", mode="before")
    @classmethod
    def normalize_artifact_type(cls, value: Any, info: ValidationInfo) -> Any:
        if (info.context or {}).get("strict_plan_protocol"):
            if value is None or isinstance(value, ArtifactType):
                return value
            if isinstance(value, str) and value in {item.value for item in ArtifactType}:
                return value
            raise ValueError("strict Plan requires a canonical artifact_type")
        return _normalize_artifact_type_value(value)

    @model_validator(mode="after")
    def validate_syntax_validator(self):
        from .text_format_contract import text_format_from_contract
        text_format_from_contract({"interface_contract": self.interface_contract,
                                   "artifact_type": self.artifact_type,
                                   "content_kind": self.content_kind})
        if self.acceptance_probes and self.syntax_validator not in (
            "python_regex", "python_regex_findall_string", "python_regex_findall_whole_match"
        ):
            raise ValueError("regex_acceptance_probes_require_python_regex")
        if self.syntax_validator in ("python_regex", "python_regex_findall_string", "python_regex_findall_whole_match") and (
            self.artifact_type != ArtifactType.PLAINTEXT or self.content_kind != "value"
        ):
            raise ValueError("python_regex_requires_plaintext_value")
        return self

    @field_validator("json_schema", mode="before")
    @classmethod
    def normalize_json_schema(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError("subtask_json_schema_must_be_object")
        return json.loads(
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        )


class ArtifactValidationProfile(BaseModel):
    """Compact validation status for an executed task artifact."""
    status: str = Field(default="not_run", description="passed, failed, or not_run")
    issues: List[str] = Field(default_factory=list)


class ArtifactProfile(BaseModel):
    """Runtime profile of the actual artifact produced by one task."""
    task_id: str = Field(..., description="Task ID that produced this artifact")
    artifact_type: str = Field(default="plaintext")
    artifact_path: Optional[str] = Field(default=None)
    artifact_aliases: List[str] = Field(default_factory=list)
    summary: str = Field(default="")
    observed_outputs: Dict[str, Any] = Field(default_factory=dict)
    validation: ArtifactValidationProfile = Field(default_factory=ArtifactValidationProfile)
    handoff_notes: List[str] = Field(default_factory=list)


class ResolvedLocalFileProfile(BaseModel):
    """A local file path visible to the current subtask as context."""
    path: str = Field(..., description="Local path mentioned in the task context")
    status: str = Field(default="available")
    content_available_as_context: bool = Field(default=False)
    origin: str = Field(default="current_subtask")
    role: str = Field(default="input")


class ArtifactHandle(BaseModel):
    """Runtime-only reference to a concrete input, artifact, overlay, or validation result."""
    handle_id: str = Field(..., description="Stable runtime handle ID for this run")
    kind: str = Field(
        ...,
        description=(
            "input_file, source_overlay, test_overlay, task_final, step_artifact, "
            "contract_alias, tool_output, or validation_result"
        ),
    )
    producer_task: Optional[str] = Field(default=None)
    producer_step: Optional[str] = Field(default=None)
    logical_path: Optional[str] = Field(default=None)
    host_path: Optional[str] = Field(default=None)
    tool_path: Optional[str] = Field(default=None)
    artifact_type: str = Field(default="plaintext")
    validation_status: str = Field(default="not_run")
    current_run: bool = Field(default=False)
    path_kind: str = Field(
        default="",
        description="file, directory, path, value, or empty when not yet classified",
    )
    extension: str = Field(
        default="",
        description="Normalized path extension, including the leading dot",
    )
    exists: Optional[bool] = Field(
        default=None,
        description="Observed path existence, when known",
    )
    provenance: Dict[str, Any] = Field(default_factory=dict)


def _canonical_json_object_text(value: Any, *, error_code: str) -> str:
    if isinstance(value, dict):
        decoded = value
    else:
        try:
            decoded = json.loads(str(value or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(error_code) from exc
    if not isinstance(decoded, dict):
        raise ValueError(error_code)
    try:
        return json.dumps(
            decoded,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(error_code) from exc


class DependencyInputContractV1(BaseModel):
    """Model-owned data-interface contract for one authoritative DAG edge."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol: Literal["sgar-dependency-input-contract-v1"] = (
        "sgar-dependency-input-contract-v1"
    )
    producer_id: str = Field(..., min_length=1)
    input_slot: str = Field(..., min_length=1)
    accepted_artifact_types: tuple[str, ...] = Field(..., min_length=1)
    accepted_extensions: tuple[str, ...] = Field(...)
    consumption_mode: Literal["context_content", "artifact_handle"]
    required_interface_contract_json: str = "{}"
    required: Literal[True] = True

    @field_validator("producer_id", "input_slot")
    @classmethod
    def _nonempty_identity(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("dependency_input_identity_missing")
        return normalized

    @field_validator("accepted_artifact_types", mode="before")
    @classmethod
    def _artifact_types(cls, value: Any) -> tuple[str, ...]:
        if not isinstance(value, (list, tuple)):
            raise ValueError("dependency_input_artifact_types_invalid")
        normalized = sorted(
            {
                str(item or "").strip().lower().replace("-", "_").replace(" ", "_")
                for item in value
                if str(item or "").strip()
            }
        )
        if not normalized:
            raise ValueError("dependency_input_artifact_types_empty")
        return tuple(normalized)

    @field_validator("accepted_extensions", mode="before")
    @classmethod
    def _extensions(cls, value: Any) -> tuple[str, ...]:
        if not isinstance(value, (list, tuple)):
            raise ValueError("dependency_input_extensions_invalid")
        normalized: set[str] = set()
        for item in value:
            raw = str(item or "").strip().lower()
            if not raw:
                normalized.add("")
            else:
                normalized.add(raw if raw.startswith(".") else f".{raw}")
        return tuple(sorted(normalized))

    @field_validator("required_interface_contract_json", mode="before")
    @classmethod
    def _required_interface(cls, value: Any) -> str:
        return _canonical_json_object_text(
            value,
            error_code="dependency_input_interface_contract_invalid",
        )

    @property
    def input_contract_sha256(self) -> str:
        return canonical_sha256(self.model_dump(mode="json"))


class DagEdgeContractV1(BaseModel):
    """Immutable projection binding producer output to consumer input."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol: Literal["sgar-dag-edge-contract-v1"] = "sgar-dag-edge-contract-v1"
    producer_id: str
    consumer_id: str
    input_slot: str
    producer_subtask_revision: int = Field(default=0, ge=0)
    consumer_subtask_revision: int = Field(default=0, ge=0)
    producer_artifact_type: str
    producer_output_extension: str
    producer_interface_contract_json: str
    accepted_artifact_types: tuple[str, ...]
    accepted_extensions: tuple[str, ...]
    consumption_mode: Literal["context_content", "artifact_handle"]
    required_interface_contract_json: str
    required: Literal[True] = True
    producer_output_contract_sha256: str
    consumer_input_contract_sha256: str
    edge_contract_sha256: str = ""

    @field_validator(
        "producer_output_contract_sha256",
        "consumer_input_contract_sha256",
    )
    @classmethod
    def _contract_hash(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
            raise ValueError("dag_edge_contract_hash_invalid")
        return normalized

    @field_validator(
        "producer_interface_contract_json",
        "required_interface_contract_json",
        mode="before",
    )
    @classmethod
    def _interface_contract(cls, value: Any) -> str:
        return _canonical_json_object_text(
            value,
            error_code="dag_edge_interface_contract_invalid",
        )

    @model_validator(mode="after")
    def _seal_edge(self) -> "DagEdgeContractV1":
        if self.producer_id == self.consumer_id:
            raise ValueError("dag_edge_self_dependency")
        expected = canonical_sha256(
            self.model_dump(mode="json", exclude={"edge_contract_sha256"})
        )
        if self.edge_contract_sha256 and self.edge_contract_sha256 != expected:
            raise ValueError("dag_edge_contract_sha256_mismatch")
        object.__setattr__(self, "edge_contract_sha256", expected)
        return self


class DownstreamConsumptionHint(BaseModel):
    """How a downstream task is expected to consume the current artifact."""
    consumer_id: str = Field(..., description="Downstream task ID")
    expects: str = Field(default="")
    edge_contract_sha256: str = ""


class ContextPacket(BaseModel):
    """Runtime context visibility packet shown to the Router/Plan Compiler."""
    current_subtask: Dict[str, Any] = Field(default_factory=dict)
    current_output_contract: Dict[str, Any] = Field(default_factory=dict)
    upstream_artifact_profiles: List[ArtifactProfile] = Field(default_factory=list)
    upstream_context_availability: Dict[str, str] = Field(default_factory=dict)
    resolved_local_files: List[ResolvedLocalFileProfile] = Field(default_factory=list)
    downstream_consumption: List[DownstreamConsumptionHint] = Field(default_factory=list)
    incoming_edge_contracts: List[DagEdgeContractV1] = Field(default_factory=list)
    outgoing_edge_contracts: List[DagEdgeContractV1] = Field(default_factory=list)
    incoming_semantic_edges_v2: List[SemanticEdgeContractV2] = Field(default_factory=list)
    outgoing_semantic_edges_v2: List[SemanticEdgeContractV2] = Field(default_factory=list)
    artifact_handles: List[ArtifactHandle] = Field(default_factory=list)
    validation_handles: List[ArtifactHandle] = Field(default_factory=list)
    handle_resolution_rules: Dict[str, Any] = Field(default_factory=dict)


class Subtask(BaseModel):
    """A single node in the Planner-generated task DAG."""
    id: str = Field(..., description="Subtask identifier (e.g. task_1)")
    role: str = Field(..., description="Assigned agent role (e.g. 'Software Engineer')")
    description: str = Field(..., description="Detailed task description")
    expected_output: str = Field(..., description="Expected deliverable specification")
    depends_on: List[str] = Field(default_factory=list, description="Upstream task IDs this node depends on")
    dependency_inputs: List[DependencyInputContractV1] = Field(
        default_factory=list,
        description="Exactly one explicit input contract for every authoritative dependency edge",
    )
    incoming_edge_contracts: List[DagEdgeContractV1] = Field(
        default_factory=list,
        description="System-derived immutable edge contracts admitted for this consumer",
    )
    artifact_type: ArtifactType = Field(..., description="Expected output artifact type")
    output_extension: str = Field(
        default="",
        description="File extension for the output artifact (e.g. '.py', '.js', '.html'). "
                    "If empty, inferred from artifact_type."
    )
    output_contract: Optional[SubtaskOutputContract] = Field(
        default=None,
        description="Stable Planner-defined deliverable contract for this node",
    )
    task_stage: Optional[TaskStage] = Field(
        default=None,
        description="Optional normalized Planner stage; missing values use a generic production stage.",
    )
    planning_execution_mode: Optional[PlannerExecutionMode] = Field(
        default=None,
        description="Planner-only classification: resource_grounded, generative, or hybrid.",
    )
    capability_evidence: List[str] = Field(
        default_factory=list,
        description="Advisory capability-card IDs supporting grounded work; not a resource binding.",
    )
    capability_gap: Optional[str] = Field(
        default=None,
        description="Explicit unavailable capability for a grounded requirement.",
    )
    semantic_requirements: List[SemanticRequirementDeclarationV1] = Field(
        default_factory=list,
        description=(
            "Evidence-bound model decisions that are deterministically compiled into "
            "execution obligations; downstream components must not re-infer them from prose."
        ),
    )
    execution_requirements: List[ExecutionResourceRequirementV1] = Field(
        default_factory=list,
        description="User-declared resource relations bound to exact request clauses.",
    )
    semantic_contract_v2: Optional[NodeSemanticContractV2] = Field(
        default=None,
        description="Planner V6 role-oriented semantics before resource selection",
    )
    incoming_semantic_edges_v2: List[SemanticEdgeContractV2] = Field(
        default_factory=list,
        description="Framework-derived V6 semantic producer/consumer edges",
    )

    @field_validator("task_stage", mode="before")
    @classmethod
    def normalize_task_stage(cls, value: Any) -> Any:
        if value is None or isinstance(value, TaskStage):
            return value
        normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "analysis": "analyze_context",
            "analyze": "analyze_context",
            "diagnose": "analyze_context",
            "read": "analyze_context",
            "inspect": "analyze_context",
            "context": "analyze_context",
            "fix_source": "implement_source",
            "source_fix": "implement_source",
            "repair_source": "implement_source",
            "implementation": "implement_source",
            "implement": "implement_source",
            "write_tests": "generate_tests",
            "update_tests": "generate_tests",
            "test_generation": "generate_tests",
            "pytest_generation": "generate_tests",
            "pytest": "run_tests",
            "test_run": "run_tests",
            "validate_tests": "run_tests",
            "final": "synthesize_final",
            "final_delivery": "synthesize_final",
            "summary": "synthesize_final",
            "report": "synthesize_final",
            "generate": "produce_artifact",
        }
        normalized = aliases.get(normalized, normalized)
        return normalized if normalized in {item.value for item in TaskStage} else None


class PlannerOutput(BaseModel):
    """Complete DAG output produced by the Planner."""
    subtasks: List[Subtask] = Field(..., description="Topologically ordered subtask list")
    edge_contracts: List[DagEdgeContractV1] = Field(
        default_factory=list,
        description="System-derived immutable data contracts for all DAG edges",
    )
    semantic_edge_contracts_v2: List[SemanticEdgeContractV2] = Field(
        default_factory=list,
        description="Planner V6 semantic DAG edges before executable binding",
    )


class SubtaskFeedback(BaseModel):
    """Feedback from semantic gatekeeper for subtask granularity validation."""
    is_valid: bool = Field(..., description="Whether the subtask granularity is valid")
    feedback_reason: Optional[str] = Field(
        default=None,
        description="Detailed rejection reason when granularity is invalid"
    )


class DAGPatch(BaseModel):
    """Local DAG topology patch for replacing one node with refined subtasks."""
    target_node_id: str = Field(..., description="Original node ID to be replaced")
    new_nodes: List[Subtask] = Field(..., description="Newly decomposed replacement nodes")
    downstream_updates: Dict[str, List[str]] = Field(
        ...,
        description="Updated depends_on list for each affected downstream node"
    )


class GranularityRejectionException(Exception):
    """Raised when a subtask fails granularity validation."""
    def __init__(self, failed_subtask: Subtask, feedback: SubtaskFeedback) -> None:
        self.failed_subtask: Subtask = failed_subtask
        self.feedback: SubtaskFeedback = feedback
        message: str = feedback.feedback_reason or "Subtask granularity validation failed."
        super().__init__(message)


# ─────────────────────────────────────────────
# Routing Decision Contract
# ─────────────────────────────────────────────

class RoutingMetrics(BaseModel):
    """Quantitative metrics from the Router's adjudication."""
    similarity: float = Field(..., description="Hybrid similarity score")
    advantage: float = Field(..., description="Advantage parameter Ap")


class RoutingDecision(BaseModel):
    """Structured result of Router adjudication for a single subtask."""
    mode: ExecutionMode = Field(..., description="Determined execution mode")
    resource: Manifest = Field(..., description="Selected resource manifest")
    metrics: RoutingMetrics = Field(..., description="Adjudication metrics")


class TypedResourceRef(BaseModel):
    """Type-preserving reference to a resource selected or considered by Router."""
    resource_id: str = Field(..., description="Resource ID from manifest")
    resource_type: ManifestType = Field(..., description="Resource type from manifest")
    base_model: Optional[str] = Field(
        default=None,
        description=(
            "Provider API model ID used on the wire for a Model; legacy internal "
            "resource IDs are accepted only at the runtime normalization boundary"
        ),
    )
    similarity: Optional[float] = Field(
        default=None,
        description="Similarity score for retrieval-derived candidates",
    )
    advantage_score: Optional[float] = Field(
        default=None,
        description="Single-resource advantage score kept as a feature",
    )
    candidate_origin: str = Field(
        default="retrieval",
        description="How this candidate entered the routing bundle",
    )
    injected_reason: Optional[str] = Field(
        default=None,
        description="Reason for system-side candidate completion, if any",
    )


class DependencySlot(BaseModel):
    """Natural-language dependency slot used for typed secondary retrieval."""
    slot_id: str = Field(..., description="Stable dependency slot identifier")
    description: str = Field(..., description="Natural-language dependency description")
    allowed_types: List[ManifestType] = Field(
        ...,
        description="Allowed resource types for this dependency slot",
    )
    top_k_per_type: int = Field(
        default=3,
        description="Maximum number of candidates retained per allowed type",
    )
    required: bool = Field(default=True, description="Whether this dependency is required")


class DependencySelection(BaseModel):
    """Candidates and selected resource for one dependency slot."""
    slot_id: str = Field(..., description="Dependency slot identifier")
    required: bool = Field(default=True, description="Whether this dependency slot is required")
    selected: Optional[TypedResourceRef] = Field(
        default=None,
        description="Selected dependency resource, or None when abandoned",
    )
    candidates: List[TypedResourceRef] = Field(
        default_factory=list,
        description="Type-preserving candidates for this slot",
    )


class ResourceInputBinding(BaseModel):
    """Runtime input binding requested by a resource application plan."""
    name: str = Field(..., description="Input parameter name")
    kind: str = Field(..., description="Input kind, such as file_path, text, json, or artifact_ref")
    required: bool = Field(default=True, description="Whether this input is required")
    source: Optional[str] = Field(
        default=None,
        description="Optional source hint, such as a resource_id, file path, or step output key",
    )


class ResourceOutputContract(BaseModel):
    """Expected output contract for a resource application step."""
    content_kind: Literal["value", "json_schema_document"] = "value"
    artifact_type: Optional[ArtifactType] = Field(
        default=None,
        description="Expected artifact type produced by the step",
    )
    schema_hint: Any = Field(
        default=None,
        description="Optional structured schema or field hint for the step output",
    )
    description: Optional[str] = Field(
        default=None,
        description="Natural-language description of the step output",
    )

    @field_validator("artifact_type", mode="before")
    @classmethod
    def normalize_artifact_type(cls, value: Any) -> Any:
        return _normalize_artifact_type_value(value)

    @field_validator("schema_hint", mode="before")
    @classmethod
    def normalize_schema_hint(cls, value: Any, info: ValidationInfo) -> Any:
        if (info.context or {}).get("strict_plan_protocol"):
            if value is None or isinstance(value, str):
                return value
            raise ValueError("strict Plan schema_hint must already be a string")
        if value is None or isinstance(value, (str, bool, int, float)):
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("resource_output_schema_hint_not_json_serializable")
            return value
        if isinstance(value, (list, tuple, dict)):
            return json.loads(
                json.dumps(
                    value,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                )
            )
        raise ValueError("resource_output_schema_hint_not_json_serializable")


class ResourceUsageDecision(BaseModel):
    """Plan-level decision describing how one selected resource is used."""
    resource_id: str = Field(..., description="Resource ID from the compact bundle")
    decision: str = Field(
        default="use",
        description="Compatibility field; selected-only plans emit use and omit skipped candidates",
    )
    use_as: str = Field(
        default="executable_step",
        description=(
            "executable_step, agent_base_model, instruction_hint, planning_hint, "
            "intermediate_evidence, validator, validator_hint, tool_macro_hint, "
            "agent_protocol_hint, or context_resource"
        ),
    )
    attached_to_steps: List[str] = Field(
        default_factory=list,
        description="Step IDs this resource influences when not directly executed",
    )
    reason: Optional[str] = Field(default=None, description="Brief plan-compiler rationale")


class ResourceApplicationStep(BaseModel):
    """One dynamic resource usage step generated by the Router policy model."""
    step_id: str = Field(..., description="Stable step identifier within one plan")
    step_type: Optional[str] = Field(
        default=None,
        description=(
            "read_resource, run_tool, call_model, call_agent, apply_skill_hint, "
            "execute_generated_code, validate_artifact, or synthesize_final"
        ),
    )
    resource_id: str = Field(..., description="Resource used by this step")
    capability_operation: Optional[str] = Field(
        default=None,
        description="Canonical exact Tool capability selected from the candidate card.",
    )
    operation_kind: Optional[OperationKind] = Field(
        default=None,
        description="Runtime-normalized execution semantic for this step",
    )
    intent: str = Field(..., description="How the policy intends to use this resource")
    input_bindings: Dict[str, Any] = Field(
        default_factory=dict,
        description="Input name to source hint mapping for this step",
    )
    output_key: str = Field(..., description="Key used to pass this step output downstream")
    expected_output_contract: Optional[ResourceOutputContract] = Field(
        default=None,
        description="Expected output contract for this step",
    )

    @field_validator("operation_kind", mode="before")
    @classmethod
    def normalize_operation_kind(cls, value: Any, info: ValidationInfo) -> Any:
        if (info.context or {}).get("strict_plan_protocol"):
            if value is None or isinstance(value, OperationKind):
                return value
            if isinstance(value, str) and value in {item.value for item in OperationKind}:
                return value
            raise ValueError("strict Plan requires a canonical operation_kind")
        if value is None or isinstance(value, OperationKind):
            return value
        normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "generate": "produce_artifact",
            "generate_artifact": "produce_artifact",
            "materialize": "produce_artifact",
            "read": "inspect_input",
            "read_file": "inspect_input",
            "invoke_tool": "run_tool",
            "call_tool": "run_tool",
            "transform": "run_tool",
            "analyze": "run_tool",
            "process": "run_tool",
            "execute_generated_code": "execute_script",
            "run_code": "execute_script",
            "execute_code": "execute_script",
            "pytest": "run_tests",
            "test": "run_tests",
            "validator": "validate_artifact",
            "validate": "validate_artifact",
            "final": "synthesize_final",
            "synthesis": "synthesize_final",
            "model": "call_model",
            "agent": "call_agent",
            "context": "apply_context_hint",
            "hint": "apply_context_hint",
        }
        normalized = aliases.get(normalized, normalized)
        if normalized in {item.value for item in OperationKind}:
            return normalized
        # Policy cards historically exposed exact capability names through
        # operation_kind. Accept known names but normalize execution to the
        # registered broad OperationKind; unknown names must remain visible as
        # a validation error instead of silently becoming None.
        from .capability_operations import CAPABILITY_OPERATION_REGISTRY

        if normalized in CAPABILITY_OPERATION_REGISTRY:
            return CAPABILITY_OPERATION_REGISTRY[normalized]["execution_operation_kind"]
        raise ValueError(f"unknown operation_kind: {normalized}")

    @field_validator("capability_operation", mode="before")
    @classmethod
    def validate_capability_operation(cls, value: Any, info: ValidationInfo) -> Any:
        if value is None:
            return None
        normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
        if (info.context or {}).get("strict_plan_protocol") and (
            not isinstance(value, str) or value != normalized
        ):
            raise ValueError("strict Plan requires a canonical capability_operation")
        # Exact Tool capabilities are manifest-owned and cannot be globally
        # enumerated here.  ResourceDefinition/Plan validation checks the value
        # against the selected frozen manifest before execution.
        return normalized or None

    @field_validator("input_bindings", mode="before")
    @classmethod
    def normalize_input_bindings(cls, value: Any, info: ValidationInfo) -> Dict[str, Any]:
        if (info.context or {}).get("strict_plan_protocol"):
            if isinstance(value, dict):
                return value
            raise ValueError("strict Plan input_bindings must already be an object")
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, list):
            merged: Dict[str, Any] = {}
            for item in value:
                if not isinstance(item, dict):
                    continue
                name = item.get("name") or item.get("input") or item.get("key")
                if name:
                    merged[str(name)] = item.get("value", item)
            return merged
        return {}


class ResourceApplicationPlan(BaseModel):
    """Dynamic plan describing how selected resources should be applied."""
    is_sufficient: bool = Field(
        ...,
        description="Whether this resource application plan can solve the subtask",
    )
    selected_resource_ids: List[str] = Field(
        default_factory=list,
        description="Selected resource IDs from the candidate bundle",
    )
    resource_usage: List[ResourceUsageDecision] = Field(
        default_factory=list,
        description="Usage records for selected resources only; omitted candidates are implicitly skipped",
    )
    steps: List[ResourceApplicationStep] = Field(
        default_factory=list,
        description="Ordered resource application steps",
    )
    final_output_from: Optional[str] = Field(
        default=None,
        description="Output key of the step that provides the final subtask artifact",
    )
    expected_execution_mode: ExecutionMode = Field(
        default=ExecutionMode.SEMI_GENERATIVE,
        description="Expected execution mode for this application plan",
    )
    reason: Optional[str] = Field(default=None, description="Policy rationale for the plan")


class BundleAdvantageMetrics(BaseModel):
    """Deterministic group-level advantage metrics for a selected resource bundle."""
    semantic_fit: float = Field(..., description="Task and dependency semantic fit")
    required_slot_coverage: float = Field(..., description="Required dependency coverage")
    input_binding_coverage: float = Field(
        default=1.0,
        description="Whether required runtime inputs appear bindable for the application plan",
    )
    output_contract_compatibility: float = Field(
        default=1.0,
        description="Whether the planned final output contract is compatible with the subtask",
    )
    joint_success: float = Field(..., description="Estimated joint success probability")
    total_cost_factor: float = Field(..., description="Estimated total bundle cost factor")
    total_latency_ms: float = Field(..., description="Estimated total bundle latency")
    baseline_efficiency: float = Field(..., description="Full-generative baseline efficiency")
    bundle_efficiency: float = Field(..., description="Selected bundle efficiency")
    bundle_advantage_score: float = Field(
        ...,
        description="Relative advantage against the full-generative baseline",
    )
    threshold: float = Field(..., description="Decision threshold for bundle advantage")
    passed: bool = Field(..., description="Whether the bundle passes the advantage gate")
    baseline_missing: bool = Field(
        default=False,
        description="Whether baseline model utility was unavailable",
    )
    plan_advantage_score: Optional[float] = Field(
        default=None,
        description="Alias for bundle_advantage_score when an application plan is evaluated",
    )


class BundleAdequacyDecision(BaseModel):
    """Router policy decision over a typed candidate bundle."""
    is_sufficient: bool = Field(
        ...,
        description="Whether selected resources are sufficient for the subtask",
    )
    selected_resources: List[TypedResourceRef] = Field(
        default_factory=list,
        description="Selected resources from the candidate bundle",
    )
    expected_execution_mode: ExecutionMode = Field(
        default=ExecutionMode.SEMI_GENERATIVE,
        description="Expected execution mode for the selected bundle",
    )
    application_plan: Optional[ResourceApplicationPlan] = Field(
        default=None,
        description="Dynamic resource application plan for this selected bundle",
    )
    reason: Optional[str] = Field(default=None, description="Policy rationale")


class AnchorExpansionAttempt(BaseModel):
    """One Top-K anchor-prefix expansion attempt."""
    attempt_index: int = Field(..., description="1-based attempt index")
    anchor_resources: List[TypedResourceRef] = Field(
        default_factory=list,
        description="Top-K prefix used as anchors in this attempt",
    )
    candidate_resources: List[TypedResourceRef] = Field(
        default_factory=list,
        description="Deduplicated typed candidate bundle",
    )
    candidate_resource_cards: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Compact resource cards shown to the Plan Compiler",
    )
    typed_candidate_counts: Dict[str, int] = Field(
        default_factory=dict,
        description="Resource-type counts after compact bundle compression",
    )
    context_packet: Dict[str, Any] = Field(
        default_factory=dict,
        description="Runtime context visibility packet shown to the Plan Compiler",
    )
    dependency_selections: List[DependencySelection] = Field(
        default_factory=list,
        description="Dependency slots and candidates used in this attempt",
    )
    bundle_decision: Optional[BundleAdequacyDecision] = Field(default=None)
    advantage_metrics: Optional[BundleAdvantageMetrics] = Field(default=None)
    failure_type: Optional[str] = Field(default=None)
    failure_reason: Optional[str] = Field(default=None)
    repair_attempted: bool = Field(
        default=False,
        description="Whether same-bundle local repair was attempted",
    )
    repair_success: bool = Field(
        default=False,
        description="Whether same-bundle local repair produced an accepted artifact",
    )
    repair_failure_type: Optional[str] = Field(
        default=None,
        description="Failure type after local repair, if repair failed",
    )
    repair_reason: Optional[str] = Field(
        default=None,
        description="Evaluator or format feedback used for local repair",
    )
    evaluation_result: Optional[EvaluationResult] = Field(
        default=None,
        description="Structured evaluator result for this attempt, if available",
    )
    repair_evaluation_result: Optional[EvaluationResult] = Field(
        default=None,
        description="Structured evaluator result after same-bundle repair, if available",
    )
    produced_file_status: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Execution-time status for required produced_files in the task contract",
    )
    lineage_warnings: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Non-fatal artifact lineage warnings, such as derived final blocks diverging from upstream artifacts",
    )
    execution_step_trace: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Compact runtime trace for executed application-plan steps",
    )
    blocked_resources: List[str] = Field(
        default_factory=list,
        description="Resource IDs blocked after infrastructure failures in this attempt",
    )
    blocked_base_models: List[str] = Field(
        default_factory=list,
        description="Base model IDs blocked after infrastructure failures in this attempt",
    )


class RoutingSession(BaseModel):
    """Stateful routing session for one subtask across anchor expansion attempts."""
    subtask_id: str = Field(..., description="Subtask ID")
    revision: Optional[SubtaskRevisionRef] = Field(
        default=None,
        description="Explicit graph/subtask revision bound to the frozen candidate pool.",
    )
    candidate_pool_snapshot: Optional[CandidatePoolSnapshot] = Field(
        default=None,
        description="Immutable formal candidate pool; absent only on legacy sessions.",
    )
    retrieval_evidence: Optional[RetrievalConfidenceEvidence] = Field(
        default=None,
        description="Evidence-only retrieval confidence; never a runtime replan trigger.",
    )
    frozen_candidate_resources: List[TypedResourceRef] = Field(
        default_factory=list,
        description="Exact ordered legacy refs materialized from candidate_pool_snapshot.",
    )
    execution_strictness: ExecutionStrictness = Field(
        default=ExecutionStrictness.BALANCED,
        description="Runtime validation strictness applied to this session",
    )
    execution_status: Optional[NodeExecutionStatus] = Field(
        default=None,
        description="Final node execution status after applying strictness policy",
    )
    execution_outcome: Optional[NodeExecutionOutcome] = Field(
        default=None,
        description="Structured final outcome for report and replan control",
    )
    execution_warnings: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Non-blocking warnings accepted under balanced strictness",
    )
    top_k_resources: List[TypedResourceRef] = Field(
        default_factory=list,
        description="Initial Top-K retrieval results as typed refs",
    )
    top_k_scores: Dict[str, float] = Field(
        default_factory=dict,
        description="Resource ID to retrieval similarity",
    )
    granularity_threshold: float = Field(..., description="Retrieval gate threshold")
    attempts: List[AnchorExpansionAttempt] = Field(default_factory=list)
    final_mode: Optional[ExecutionMode] = Field(default=None)
    policy_expected_mode: Optional[ExecutionMode] = Field(
        default=None,
        description="Mode expected by Router policy for the accepted plan",
    )
    actual_runtime_mode: Optional[ExecutionMode] = Field(
        default=None,
        description="Mode that was actually executed at runtime",
    )
    fallback_used: bool = Field(
        default=False,
        description="Whether actual full-generative fallback was invoked",
    )
    final_training_label: Optional[TrainingLabel] = Field(
        default=None,
        description="Training label inferred for the final accepted or failed path",
    )
    final_selected_resources: List[TypedResourceRef] = Field(default_factory=list)
    blocked_resources: List[str] = Field(
        default_factory=list,
        description="Resource IDs temporarily blocked within this routing session",
    )
    blocked_base_models: List[str] = Field(
        default_factory=list,
        description="Base model IDs temporarily blocked within this routing session",
    )
