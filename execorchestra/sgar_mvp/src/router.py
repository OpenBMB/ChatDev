"""
S-GAR Routing Model - Type-faithful Router
==========================================
Implements retrieval-based granularity gating, Top-K anchor expansion,
typed dependency retrieval, policy bundle assembly, and group-level
bundle advantage scoring.
"""

from __future__ import annotations

from . import terminal_progress

from sgar_mvp.src.direct_network import direct_sync_http_client

from copy import deepcopy
import json
import hashlib
import math
import os
import re
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
from loguru import logger
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError

from .capability_operations import (
    CAPABILITY_OPERATION_REGISTRY,
    execution_operation_kind_for_tool,
    manifest_capability_operations,
    normalize_capability_operation,
    normalize_task_general_operation_kinds,
    tool_allowed_operation_kinds,
)
from .capability_registry import GLOBAL_CAPABILITY_REGISTRY
from .llm_compat import create_chat_completion_with_compat, is_response_format_unsupported_error
from .control_models import is_control_model_failover_failure
from .runtime_requirements import DependencyGate
from .binding_protocol import (
    BindingProtocolError,
    container_dependency_references,
    normalize_contract_kind,
    normalize_step_reference,
    parse_binding_source,
)
from .retrieval_policy import DEFAULT_POLICY_PATH, load_retrieval_policy
from .model_accounting import ModelAccountingError, RunCostLedger
from .model_transport import (
    ModelTransportError,
    ProviderEndpointIdentity,
    SyncModelTransportPort,
    classify_transport_exception,
    require_sync_model_transport,
)
from .model_response_contracts import (
    StructuredResponseModeInput,
    normalize_structured_response_mode,
    system_role_requirement,
    system_role_response_format,
    validate_structured_response_content,
)
from .retrieval_runtime import FrozenCandidatePoolResult, typed_refs_from_frozen_pool
from .schema import (
    AnchorExpansionAttempt,
    ArtifactType,
    BundleAdequacyDecision,
    BundleAdvantageMetrics,
    DependencySelection,
    DependencySlot,
    ExecutionMode,
    GranularityRejectionException,
    Manifest,
    ManifestType,
    OperationKind,
    QueryRetrievalProfile,
    ResourceApplicationPlan,
    ResourceApplicationStep,
    ResourceOutputContract,
    ResourceUsageDecision,
    RoutingDecision,
    RoutingMetrics,
    RoutingSession,
    Subtask,
    SubtaskFeedback,
    TypedResourceRef,
    Vector,
)


_DEFAULT_NATURAL_DEP_TYPES = [
    ManifestType.TOOL,
    ManifestType.SKILL,
    ManifestType.RESOURCE,
    ManifestType.AGENT,
]

_RETRIEVAL_POLICY = load_retrieval_policy()
_TYPED_RETRIEVAL_QUOTA = {
    ManifestType(resource_type): quota
    for resource_type, quota in _RETRIEVAL_POLICY.initial_quotas().items()
}
_COMPACT_BUNDLE_QUOTA = {
    ManifestType(resource_type): quota
    for resource_type, quota in _RETRIEVAL_POLICY.compact_quotas().items()
}


PLAN_COMPILER_TRANSPORT_RETRY_MAX = 2
PLAN_COMPILER_PROMPT_JSON_SUFFIX = (
    " Provider JSON mode may be unavailable; still return exactly one valid JSON object as plain text."
)

PLAN_COMPILER_COMPACT_BUNDLE_POLICY = {
    "all_candidates_are_optional": True,
    "selected_only_output": True,
    "omit_unselected_candidates": True,
    "allowed_use_as": [
        "executable_step",
        "agent_base_model",
        "instruction_hint",
        "planning_hint",
        "intermediate_evidence",
        "validator",
        "validator_hint",
        "tool_macro_hint",
        "agent_protocol_hint",
        "context_resource",
    ],
    "allowed_step_type": [
        "read_resource",
        "run_tool",
        "call_model",
        "call_agent",
        "apply_skill_hint",
        "execute_generated_code",
        "validate_artifact",
        "synthesize_final",
    ],
    "operation_kind_is_required": True,
    "allowed_operation_kind_by_resource_type": {
        "Model": {
            "call_model": "Call the model for reasoning/intermediate output without a strict artifact contract.",
            "produce_artifact": "Call the model to produce a concrete artifact matching expected_output_contract.",
            "synthesize_final": "Call the model to produce the subtask's FINAL artifact.",
        },
        "Agent": {
            "call_agent": "Delegate to the agent for intermediate work.",
            "produce_artifact": "Delegate to the agent to produce a concrete artifact.",
            "synthesize_final": "Delegate to the agent to produce the FINAL artifact.",
        },
        "Skill": {
            "apply_context_hint": "Inject the skill as guidance/context; skills are not executed."
        },
        "Resource": {
            "inspect_input": "Read/inject the resource content as context."
        },
    },
}

PLAN_COMPILER_CANDIDATE_COMPLETION_POLICY = {
    "global_retrieval_is_primary": True,
    "supplemental_candidates_are_optional": True,
    "supplemental_candidate_origin": "capability_completion",
    "note": (
        "Resources with candidate_origin=capability_completion were added "
        "only because the current bundle lacked a Model/Agent finalizer. "
        "Use them only if the subtask requires synthesis or generation."
    ),
}

PLAN_COMPILER_RATIONALE_POLICY = {
    "plan_reason_max_sentences": 2,
    "resource_reason_max_sentences": 1,
    "step_intent_max_sentences": 1,
    "no_chain_of_thought": True,
    "do_not_explain_unselected_candidates": True,
}

PLAN_COMPILER_SYSTEM_PROMPT = (
    "You are the S-GAR Plan Compiler policy model. Build a dynamic ResourceApplicationPlan "
    "using English framework-authored intent and rationale while preserving literal identifiers "
    "exactly. "
    "for the subtask using only resource_id values from candidate_bundle. Do not invent IDs. "
    "Select and compose Model, Agent, Tool, Skill, and Resource candidates in one unified plan; "
    "do not emit disconnected pairwise mini-plans. Return only resources that are actually used. "
    "Omitted candidates are implicitly skipped: never emit skip or unused resource_usage records, "
    "and set decision='use' for every emitted resource_usage item. "
    "Use context_packet to understand available upstream artifacts, resolved local files, "
    "the current_output_contract, and downstream_consumption. Upstream task artifacts are "
    "task context, not resources: do not mark a bundle insufficient because task_1/task_2 "
    "or other upstream artifacts are absent from candidate_bundle when context_packet marks "
    "them available_as_context. Use file_reader/artifact_inspector only when deterministic "
    "file inspection is needed beyond already resolved context. The final step must satisfy "
    "current_output_contract and must not downgrade the subtask's final artifact type. "
    "candidate_bundle is a compact view, not the full manifest. resource_type is static; "
    "use_as and step_type describe how each selected resource participates. If candidates are insufficient, return "
    "is_sufficient=false. A Tool may be final only when its output matches the requested "
    "artifact. If a Tool produces intermediate evidence, continue with a Model or Agent step "
    "to synthesize the final artifact. A Skill usually acts as instruction_hint, planning_hint, "
    "validator_hint, tool_macro_hint, or agent_protocol_hint; execute it only if it has a clear "
    "runtime. Honor Skill required_resource_ids and portability: bind apply_skill_hint output "
    "to its consuming Model, Agent, or Tool step and select explicit dependency steps when "
    "required. Request optional Skill references only through input_bindings.skill_references "
    "using paths listed in reference_topics. A Resource should be read/injected by the system. "
    "Every call_agent step must bind "
    "input_bindings.base_model={resource_id: <selected Model resource_id>}. Emit that Model in "
    "selected_resource_ids and resource_usage with use_as='agent_base_model' and attached_to_steps "
    "containing the Agent step_id. The bound Model is an execution dependency and must not receive "
    "a separate call_model step unless the plan independently needs one. Agent IDs must never be "
    "used as API model names. Every selected Tool, Skill, or Resource that contributes to another "
    "step must be represented by an explicit step and connected through output_key/input_bindings. "
    "Generated code must only run "
    "through an explicit execute_generated_code step with a runner Tool; the upstream Model "
    "step that writes code should set expected_output_contract.artifact_type='code'. Validation must be an "
    "explicit validate_artifact step when final files need checking. Each input binding is one "
    "unambiguous source: a scalar/structured literal, {resource_id: string}, {from_step: string, "
    "output_key: string}, {path: string}, {artifact_handle: string}, or {literal: value}. "
    "Lists and objects are structured literal values, not prioritized fallback hints; do not "
    "combine multiple source variants in one binding object. "
    "context_packet.artifact_handles and context_packet.validation_handles are the preferred "
    "way to reference current-run artifacts. For run_tests, validate_artifact, or "
    "execute_generated_code tool targets, bind input paths as {artifact_handle: handle_id} "
    "whenever a matching handle exists. Raw bench_cases/... workspace paths are original "
    "inputs by default; use them only for inspect_input or explicit validate_input_files. "
    "If a final synthesis step only needs pytest/validator evidence, consume an upstream "
    "validation_result handle as context instead of re-running pytest. If a required handle "
    "is absent, return is_sufficient=false with reason artifact_handle_missing. "
    "For a Tool whose candidate card advertises execute_script, bind generated code through "
    "the Tool card's declared input contract and use explicit from_step/output_key references. "
    "For pytest-style single-file validators, bind target_path to one generated test file; "
    "only artifact_validator-style tools should receive target_paths. "
    "EVERY step MUST include an operation_kind. For a Tool step, choose exactly one value from "
    "that selected candidate card's allowed_operation_kinds; no other Tool operation kind is valid. "
    "For a Tool step, capability_operation may be set only to one of that card's capability_operations; "
    "operation_kind is the card's execution_operation_kind and capability_operation is the exact semantic "
    "capability. Never invent either value. "
    "Legacy operation_kind='run_tool' is valid only when that selected Tool card explicitly advertises "
    "run_tool. For Model, Agent, Skill, and Resource steps, choose from "
    "compact_bundle_policy.allowed_operation_kind_by_resource_type for that step's resource_type. "
    "Never leave operation_kind null. "
    "final_output_from MUST be exactly the output_key of one of the steps you list — it is a "
    "reference to an actual step output, NEVER a free-form deliverable name (e.g. do not invent "
    "'quality_report' or 'final_report' unless a step literally has that output_key). When the "
    "subtask's deliverable combines several step outputs (e.g. merging flake8, bandit and radon "
    "results into one report), you MUST add a final step with step_type='synthesize_final' and "
    "operation_kind='synthesize_final' that consumes those step outputs via input_bindings "
    "({from_step, output_key}) and produces the deliverable; then set final_output_from to that "
    "synthesis step's output_key. A single tool's output may be final only when it already "
    "satisfies the requested artifact type. "
    "Do not choose a resource as an executable_step when its dependency_status is blocked. "
    "If generated Python code can be implemented with standard library modules, prefer that "
    "over third-party imports that are not listed as available or installable in the runtime card. "
    "Give a concise auditable rationale: application_plan.reason is at most two sentences, every "
    "selected resource_usage.reason is one sentence, and every step.intent is one sentence. "
    "Do not reveal chain-of-thought or explain unselected candidates. "
    "Return strict JSON matching: {is_sufficient: bool, selected_resources: "
    "[{resource_id, resource_type, base_model?}], expected_execution_mode: "
    "BYPASS_MODE|SEMI_GENERATIVE_MODE|FULL_GENERATIVE_MODE, reason: string|null, "
    "application_plan: {is_sufficient: bool, selected_resource_ids: [string], "
    "resource_usage: [{resource_id: string, decision: use, use_as: string, "
    "attached_to_steps: [string], reason: string|null}], steps: [{step_id: string, "
    "step_type: read_resource|run_tool|call_model|call_agent|apply_skill_hint|"
    "execute_generated_code|validate_artifact|synthesize_final, resource_id: string, "
    "capability_operation?: string, "
    "operation_kind: string (REQUIRED; for a Tool pick from the selected candidate card's "
    "allowed_operation_kinds; for other resource types pick from their compact bundle menu), "
    "intent: string, input_bindings: object, output_key: string, expected_output_contract?: "
    "{artifact_type?: string, schema_hint?: string, description?: string}}], "
    "final_output_from: string|null, expected_execution_mode: "
    "BYPASS_MODE|SEMI_GENERATIVE_MODE|FULL_GENERATIVE_MODE, reason: string|null}}."
)


def _policy_request_hash(call_kwargs: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        dict(call_kwargs),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def plan_compiler_static_material() -> Dict[str, Any]:
    """Return the exact versioned framework material used by compiler requests.

    This is registered as a provenance source before any guard check.  Keeping
    the request builder and source material on the same constants prevents a
    fixed policy number, schema literal, or prompt token from being mistaken
    for hidden evaluation data.
    """

    return {
        "protocol": "plan-compiler-static-material-v1",
        "payload_contract": {
            "compact_bundle_policy": deepcopy(PLAN_COMPILER_COMPACT_BUNDLE_POLICY),
            "candidate_completion_policy": deepcopy(
                PLAN_COMPILER_CANDIDATE_COMPLETION_POLICY
            ),
            "rationale_policy": deepcopy(PLAN_COMPILER_RATIONALE_POLICY),
        },
        "system_prompt": PLAN_COMPILER_SYSTEM_PROMPT,
        "prompt_json_suffix": PLAN_COMPILER_PROMPT_JSON_SUFFIX,
        "request_defaults": {"temperature": 0.0},
        "response_formats": {
            "json_schema": _router_response_format_json_schema(),
            "json_object": {"type": "json_object"},
            "prompt_json": None,
        },
    }


def build_plan_compiler_payload(
    *,
    subtask: Subtask,
    context_packet: Mapping[str, Any] | None,
    anchor_resources: Sequence[Mapping[str, Any]],
    candidate_cards: Sequence[Mapping[str, Any]],
    dependency_slots: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Build the exact logical compiler payload without issuing a request."""

    return {
        "subtask": {
            "id": subtask.id,
            "description": subtask.description,
            "expected_output": subtask.expected_output,
            "artifact_type": subtask.artifact_type.value,
            "output_contract": (
                subtask.output_contract.model_dump(mode="json")
                if subtask.output_contract is not None
                else None
            ),
        },
        "context_packet": dict(context_packet or {}),
        "anchor_resources": [dict(item) for item in anchor_resources],
        "candidate_bundle": [dict(item) for item in candidate_cards],
        "compact_bundle_policy": deepcopy(PLAN_COMPILER_COMPACT_BUNDLE_POLICY),
        "dependency_slots": [dict(item) for item in dependency_slots],
        "candidate_completion_policy": deepcopy(
            PLAN_COMPILER_CANDIDATE_COMPLETION_POLICY
        ),
        "rationale_policy": deepcopy(PLAN_COMPILER_RATIONALE_POLICY),
    }


def build_plan_compiler_call_kwargs(
    payload: Mapping[str, Any],
    *,
    model_id: str,
    response_mode: StructuredResponseModeInput | Literal["prompt_json"],
    portable_schema: bool = True,
) -> Dict[str, Any]:
    """Build the exact provider envelope used by the fixed-pass compiler."""

    messages = [
        {"role": "system", "content": PLAN_COMPILER_SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    call_kwargs: Dict[str, Any] = {
        "model": model_id,
        "messages": messages,
        "temperature": 0.0,
    }
    if response_mode == "prompt_json":
        call_kwargs["messages"][0]["content"] += PLAN_COMPILER_PROMPT_JSON_SUFFIX
        return call_kwargs
    selected_mode = normalize_structured_response_mode(response_mode)
    if selected_mode == "native_strict_schema":
        call_kwargs["response_format"] = (
            system_role_response_format(
                "router_policy",
                mode="native_strict_schema",
            )
            if portable_schema
            else _router_response_format_json_schema()
        )
    else:
        call_kwargs["response_format"] = system_role_response_format(
            "router_policy",
            mode="json_object_local_validator",
        )
    return call_kwargs


def _assert_strict_payload_preserved(raw: Any, parsed: Any, path: str = "decision") -> None:
    """Reject any schema coercion, filtering, or alias repair in fixed-pass mode."""

    if isinstance(raw, Mapping):
        if not isinstance(parsed, Mapping):
            raise ValueError(f"plan_protocol_failure: schema rewrote {path}")
        for key, value in raw.items():
            if key not in parsed:
                raise ValueError(
                    f"plan_protocol_failure: schema dropped unknown field {path}.{key}"
                )
            _assert_strict_payload_preserved(value, parsed[key], f"{path}.{key}")
        return
    if isinstance(raw, list):
        if not isinstance(parsed, list) or len(raw) != len(parsed):
            raise ValueError(f"plan_protocol_failure: schema rewrote list {path}")
        for index, value in enumerate(raw):
            _assert_strict_payload_preserved(value, parsed[index], f"{path}[{index}]")
        return
    if type(raw) is not type(parsed) or raw != parsed:
        raise ValueError(f"plan_protocol_failure: schema coerced {path}")


def _retryable_policy_transport(exc: Exception) -> tuple[bool, str, bool, str]:
    """Classify provider failures by type/status without message guessing.

    ``response_received`` means a semantic model response was received.  HTTP
    error envelopes are transport failures, not model responses.
    """

    _shared_retryable, shared_failure_type = classify_transport_exception(exc)
    if shared_failure_type == "provider_timeout":
        return True, shared_failure_type, False, "infrastructure"
    if shared_failure_type == "provider_exact_schema_unsupported":
        return False, shared_failure_type, False, "framework"
    target: BaseException = exc
    seen: set[int] = set()
    while id(target) not in seen:
        seen.add(id(target))
        if isinstance(target, (APIConnectionError, APITimeoutError)):
            return True, "provider_connection_error", False, "infrastructure"
        if isinstance(target, RateLimitError):
            return True, "provider_rate_limit", False, "infrastructure"
        if isinstance(target, APIStatusError):
            status = int(getattr(target, "status_code", 0) or 0)
            if status in {408, 409, 429, 500, 502, 503, 504}:
                return (
                    True,
                    "provider_rate_limit" if status == 429 else "provider_http_error",
                    False,
                    "infrastructure",
                )
            # A permanent HTTP rejection contains no semantic compiler
            # payload.  It therefore cannot be evidence of a research-level
            # Plan choice; the fixed request/configuration must fail closed as
            # framework responsibility.
            return False, "provider_http_error", False, "framework"
        nested = getattr(target, "__cause__", None)
        if not isinstance(nested, BaseException):
            break
        target = nested
    return False, "provider_non_transport_error", False, "research"


def _classify_router_provider_exception(exc: Exception) -> tuple[str, str]:
    """Structured provider label without importing executor internals."""

    _retryable, failure_type, _response_received, _responsibility = (
        _retryable_policy_transport(exc)
    )
    return failure_type, f"{type(exc).__name__}: {exc}"


def _router_response_format_json_schema() -> Dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "sgar_plan_compiler_decision",
            "strict": False,
            "schema": BundleAdequacyDecision.model_json_schema(),
        },
    }


def _balanced_json_object_candidates(text: str) -> List[str]:
    candidates: List[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    escaped = False
    for idx, ch in enumerate(text or ""):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = idx
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                candidates.append(text[start : idx + 1])
                start = None
    return candidates


def _extract_unique_json_object(text: str, expected_keys: tuple[str, ...]) -> Dict[str, Any]:
    raw = str(text or "").strip()
    candidates: List[str] = [raw]
    fence_pattern = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
    candidates.extend(match.group(1).strip() for match in fence_pattern.finditer(raw))
    candidates.extend(_balanced_json_object_candidates(raw))
    seen_text: set[str] = set()
    valid_by_normalized: Dict[str, Dict[str, Any]] = {}
    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate or candidate in seen_text:
            continue
        seen_text.add(candidate)
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue
        if not isinstance(parsed, dict):
            continue
        if expected_keys and not any(key in parsed for key in expected_keys):
            continue
        normalized = json.dumps(parsed, ensure_ascii=False, sort_keys=True)
        valid_by_normalized[normalized] = parsed
    if len(valid_by_normalized) != 1:
        raise ValueError("policy_invalid_output: expected exactly one valid JSON object")
    return next(iter(valid_by_normalized.values()))

_COMPACT_BUNDLE_TOTAL_MAX = _RETRIEVAL_POLICY.compact_total_max
_DEFAULT_RETRIEVAL_POLICY_PATH = str(DEFAULT_POLICY_PATH)
_TYPE_SIMILARITY_WEIGHTS: Dict[ManifestType, Tuple[float, float]] = {
    ManifestType(resource_type): weights
    for resource_type, weights in _RETRIEVAL_POLICY.weights().items()
}


class SGARRouter:
    """
    Type-faithful Router for S-GAR.

    Legacy API:
        adjudicate(query_vec, library) -> RoutingDecision

    New API:
        start_session(subtask, query_vec, library) -> RoutingSession
        build_attempt(session, subtask, library) -> AnchorExpansionAttempt | None
        record_attempt_failure(session, attempt, failure_type, reason) -> None
    """

    def __init__(
        self,
        confidence_threshold: float = 0.85,
        granularity_threshold: float = 0.35,
        bundle_advantage_threshold: float = 1.0,
        policy_api_key: Optional[str] = None,
        policy_base_url: str = "https://api.openai.com/v1",
        policy_model: str = "gpt-5.6-sol",
        policy_model_chain: Optional[Sequence[str]] = None,
        baseline_model_id: Optional[str] = None,
        resource_index: Optional[Dict[str, Dict[str, Any]]] = None,
        max_anchor_attempts: int = 3,
        execute_low_advantage_on_exhaustion: bool = True,
        enable_intelligent_resource_completion: bool = True,
        supplemental_model_ids: Optional[Sequence[str]] = None,
        max_supplemental_models: int = 2,
        retrieval_strategy: Optional[str] = None,
        retrieval_type_weights: Optional[Dict[str, Tuple[float, float]]] = None,
        typed_retrieval_quotas: Optional[Dict[str, int]] = None,
        compact_bundle_quotas: Optional[Dict[str, int]] = None,
        compact_bundle_total_max: Optional[int] = None,
        trust_effective_pool_readiness: bool = False,
        cost_ledger: Optional[RunCostLedger] = None,
        policy_transport: Optional[SyncModelTransportPort] = None,
        policy_response_modes: Optional[Mapping[str, StructuredResponseModeInput]] = None,
        # Kept for compatibility with older construction sites. They are ignored
        # because granularity is now retrieval-gated instead of LLM-gated.
        gatekeeper_api_key: Optional[str] = None,
        gatekeeper_base_url: str = "https://api.openai.com/v1",
        gatekeeper_model: str = "gpt-5.6-sol",
    ) -> None:
        self.confidence_threshold = confidence_threshold
        self.granularity_threshold = granularity_threshold
        self.bundle_advantage_threshold = bundle_advantage_threshold
        self.policy_model = policy_model
        if isinstance(policy_model_chain, str):
            self.policy_model_chain = [policy_model_chain]
        else:
            chain = list(policy_model_chain or [policy_model])
            self.policy_model_chain = []
            seen_models: set[str] = set()
            for model_id in chain:
                model_text = str(model_id or "").strip()
                if not model_text or model_text in seen_models:
                    continue
                seen_models.add(model_text)
                self.policy_model_chain.append(model_text)
            if not self.policy_model_chain:
                self.policy_model_chain = [policy_model]
        self.policy_response_modes = {
            str(model_id): normalize_structured_response_mode(mode)
            for model_id, mode in dict(policy_response_modes or {}).items()
        }
        self.baseline_model_id = baseline_model_id or policy_model
        self.resource_index: Dict[str, Dict[str, Any]] = resource_index or {}
        self.max_anchor_attempts = max_anchor_attempts
        self.execute_low_advantage_on_exhaustion = execute_low_advantage_on_exhaustion
        self.enable_intelligent_resource_completion = enable_intelligent_resource_completion
        if isinstance(supplemental_model_ids, str):
            self.supplemental_model_ids = [supplemental_model_ids]
        else:
            self.supplemental_model_ids = list(supplemental_model_ids or [])
        self.max_supplemental_models = max(0, max_supplemental_models)
        self.retrieval_strategy = self._resolve_retrieval_strategy(retrieval_strategy)
        self.retrieval_type_weights = {
            ManifestType(resource_type): tuple(weights)
            for resource_type, weights in (retrieval_type_weights or _RETRIEVAL_POLICY.weights()).items()
        }
        self.typed_retrieval_quotas = {
            ManifestType(resource_type): int(quota)
            for resource_type, quota in (typed_retrieval_quotas or _RETRIEVAL_POLICY.initial_quotas()).items()
        }
        self.compact_bundle_quotas = {
            ManifestType(resource_type): int(quota)
            for resource_type, quota in (compact_bundle_quotas or _RETRIEVAL_POLICY.compact_quotas()).items()
        }
        self.compact_bundle_total_max = int(
            compact_bundle_total_max or _RETRIEVAL_POLICY.compact_total_max
        )
        # Retrieval evaluation can bind the effective pool to a frozen RC1
        # readiness hash. In that mode, repeating host/Docker dependency probes
        # would make retrieval depend on transient infrastructure state. Normal
        # execution keeps the runtime dependency gate enabled.
        self.trust_effective_pool_readiness = bool(trust_effective_pool_readiness)
        self.cost_ledger = cost_ledger
        self.dependency_gate = DependencyGate()
        self.cost_floor = 0.01
        self.latency_floor_ms = 10.0
        self.unknown_success_rate = 0.5
        self.epsilon = 1e-3
        # Publicly auditable summary of the latest explicit-candidate Plan
        # Compiler call.  Experiment runners persist this separately from the
        # executable plan so Gold injection metadata never enters the prompt.
        self.last_plan_compiler_trace: Dict[str, Any] = {}
        self._last_policy_call_metadata: Dict[str, Any] = {}
        self._frozen_pool_results: Dict[str, Any] = {}

        if policy_api_key == "":
            resolved_api_key = None
        else:
            resolved_api_key = (
                policy_api_key
                or gatekeeper_api_key
                or os.environ.get("LLM_API_KEY")
            )
        self._policy_transport: Optional[SyncModelTransportPort] = None
        if policy_transport is not None:
            self._policy_transport = require_sync_model_transport(policy_transport)
        elif resolved_api_key:
            sdk_client = OpenAI(
                http_client=direct_sync_http_client(),
                api_key=resolved_api_key,
                base_url=policy_base_url,
                timeout=60.0,
                max_retries=0,
            )
            self._policy_transport = SyncModelTransportPort.from_sdk_client(
                client=sdk_client,
                endpoint_identity=ProviderEndpointIdentity.create(
                    provider="openai_compatible",
                    base_url=policy_base_url,
                    credential_environment_variable="LLM_API_KEY",
                    timeout_seconds=60.0,
                ),
            )
        else:
            logger.warning(
                "[Router] Policy model unavailable; using deterministic fallback bundle policy."
            )

        logger.info(
            "[Router] Initialized | confidence={:.2f} | granularity={:.2f} | "
            "bundle_adv={:.2f} | retrieval={}",
            self.confidence_threshold,
            self.granularity_threshold,
            self.bundle_advantage_threshold,
            self.retrieval_strategy,
        )

    @property
    def policy_transport_client(self) -> SyncModelTransportPort:
        """Expose the typed transport without exposing the SDK client."""

        if self._policy_transport is None:
            raise RuntimeError("router_policy_transport_unavailable")
        return self._policy_transport

    @staticmethod
    def _resolve_retrieval_strategy(explicit: Optional[str]) -> str:
        allowed = {
            "capability_only",
            "raw_capability_rrf",
            "concatenated_hyde",
            "dual_hyde",
            "dual_hard",
            "dual_hard_utility",
        }
        if explicit:
            if explicit not in allowed:
                raise ValueError(f"Unsupported retrieval strategy: {explicit}")
            return explicit
        environment = os.environ.get("SGAR_RETRIEVAL_STRATEGY", "").strip()
        if environment:
            if environment not in allowed:
                raise ValueError(f"Unsupported SGAR_RETRIEVAL_STRATEGY: {environment}")
            return environment
        try:
            configured = load_retrieval_policy().active_strategy
            if configured in allowed:
                return configured
        except Exception:
            pass
        return "capability_only"

    # -- Vector Operations -------------------------------------------------

    @staticmethod
    def compute_similarity(query_vec: Vector, target_vec: Vector) -> float:
        """Cosine similarity between two latent vectors."""
        v1 = np.array(query_vec.embedding)
        v2 = np.array(target_vec.embedding)
        return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-9))

    def retrieve_top_k(
        self,
        query: Vector | QueryRetrievalProfile,
        library: List[Manifest],
        k: int = 3,
        *,
        apply_hard_gates: Optional[bool] = None,
        apply_utility_rerank: bool = True,
    ) -> List[Tuple[Manifest, float]]:
        """
        Retrieve resources with separated capability/constraint vectors.

        A legacy ``Vector`` remains accepted and is used for both paths. New
        runtime entrypoints always provide ``QueryRetrievalProfile``.
        """
        scored: List[Tuple[Manifest, float]] = []
        if isinstance(query, QueryRetrievalProfile):
            cap_query = query.capability
            con_query = query.constraint
            task_requirements = query.hard_requirements
        else:
            cap_query = query
            con_query = query
            task_requirements = {}
        hard_gates_enabled = (
            self.retrieval_strategy in {"dual_hard", "dual_hard_utility"}
            if apply_hard_gates is None
            else apply_hard_gates
        )
        eligible_manifests: List[Manifest] = []
        for manifest in library:
            if hard_gates_enabled and not self._passes_query_hard_gate(
                manifest,
                task_requirements,
            ):
                continue
            eligible_manifests.append(manifest)

        if self.retrieval_strategy == "raw_capability_rrf":
            if not isinstance(query, QueryRetrievalProfile) or query.raw_query is None:
                raise ValueError(
                    "raw_capability_rrf requires QueryRetrievalProfile.raw_query"
                )
            rrf_k = 60.0
            normalizer = 2.0 / (rrf_k + 1.0)
            capability_ranked = sorted(
                eligible_manifests,
                key=lambda manifest: (
                    self.compute_similarity(query.capability, manifest.v_cap),
                    manifest.id,
                ),
                reverse=True,
            )
            raw_ranked = sorted(
                eligible_manifests,
                key=lambda manifest: (
                    self.compute_similarity(query.raw_query, manifest.v_cap),
                    manifest.id,
                ),
                reverse=True,
            )
            capability_ranks = {
                manifest.id: rank
                for rank, manifest in enumerate(capability_ranked, start=1)
            }
            raw_ranks = {
                manifest.id: rank
                for rank, manifest in enumerate(raw_ranked, start=1)
            }
            for manifest in eligible_manifests:
                fused = (
                    1.0 / (rrf_k + capability_ranks[manifest.id])
                    + 1.0 / (rrf_k + raw_ranks[manifest.id])
                ) / normalizer
                scored.append((manifest, fused))
            scored.sort(key=lambda item: (item[1], item[0].id), reverse=True)
            return scored[:k]

        for manifest in eligible_manifests:
            sim_cap = self.compute_similarity(cap_query, manifest.v_cap)
            if self.retrieval_strategy == "capability_only":
                hybrid_score = sim_cap
            else:
                if con_query is None:
                    raise ValueError(
                        f"{self.retrieval_strategy} requires QueryRetrievalProfile.constraint"
                    )
                sim_con = self.compute_similarity(con_query, manifest.v_con)
                w_cap, w_con = self.retrieval_type_weights.get(
                    manifest.type,
                    (0.70, 0.30),
                )
                hybrid_score = w_cap * sim_cap + w_con * sim_con
            if apply_utility_rerank and self.retrieval_strategy == "dual_hard_utility":
                hybrid_score += self._empirical_retrieval_utility_adjustment(manifest)
            scored.append((manifest, hybrid_score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]

    def retrieve_top_k_by_type(
        self,
        query: Vector | QueryRetrievalProfile,
        library: List[Manifest],
        quotas: Optional[Dict[ManifestType, int]] = None,
        *,
        apply_hard_gates: Optional[bool] = None,
        apply_utility_rerank: bool = True,
    ) -> Dict[ManifestType, List[Tuple[Manifest, float]]]:
        """Rank inside each resource type; raw cosine scores are not compared across types."""

        resolved_quotas = quotas or self.typed_retrieval_quotas
        typed: Dict[ManifestType, List[Tuple[Manifest, float]]] = {}
        for manifest_type, quota in resolved_quotas.items():
            if quota <= 0:
                continue
            pool = [manifest for manifest in library if manifest.type == manifest_type]
            if not pool:
                continue
            typed[manifest_type] = self.retrieve_top_k(
                query,
                pool,
                k=min(quota, len(pool)),
                apply_hard_gates=apply_hard_gates,
                apply_utility_rerank=apply_utility_rerank,
            )
        return typed

    def _passes_query_hard_gate(
        self,
        manifest: Manifest,
        task_requirements: Dict[str, Any],
    ) -> bool:
        ref = self._ref_from_manifest(manifest)
        if not self._passes_hard_gate(ref):
            return False
        raw = self.resource_index.get(manifest.id, {})
        if manifest.type == ManifestType.MODEL:
            model_block = raw.get("type_specific", {}).get("model", {})
            supports = model_block.get("supports", {}) if isinstance(model_block, dict) else {}
            for feature in task_requirements.get("required_model_features", []):
                if supports.get(feature) is not True:
                    return False
            minimum = task_requirements.get("min_context_tokens")
            if minimum:
                context_value = model_block.get("context_window")
                match = re.search(
                    r"(\d+(?:\.\d+)?)\s*([km]?)",
                    str(context_value or "").lower().replace(",", ""),
                )
                if not match:
                    return False
                available = float(match.group(1))
                if match.group(2) == "k":
                    available *= 1_000
                elif match.group(2) == "m":
                    available *= 1_000_000
                if int(available) < int(minimum):
                    return False
        elif manifest.type == ManifestType.SKILL:
            skill_block = raw.get("type_specific", {}).get("skill", {})
            query_text = str(task_requirements.get("original_query") or "").lower()
            avoid_when = (
                skill_block.get("avoid_when", [])
                if isinstance(skill_block, dict)
                else []
            )
            for cue in avoid_when:
                normalized = str(cue).strip().lower()
                if len(normalized) >= 5 and normalized in query_text:
                    return False
        return True

    def _empirical_retrieval_utility_adjustment(self, manifest: Manifest) -> float:
        raw = self.resource_index.get(manifest.id, {})
        utility = raw.get("utility", {}) if isinstance(raw, dict) else {}
        memory = raw.get("memory", {}) if isinstance(raw, dict) else {}
        attempts = int(utility.get("attempts") or 0)
        trajectory_count = len(memory.get("success_trajectories", []) or []) + len(
            memory.get("failure_reflections", []) or []
        )
        if attempts <= 0 or trajectory_count < attempts:
            return 0.0
        success = min(max(float(utility.get("expected_success_rate") or 0.5), 0.0), 1.0)
        return 0.05 * (success - 0.5)

    # -- New Session API ---------------------------------------------------

    def start_session(
        self,
        subtask: Subtask,
        query_vec: Vector | QueryRetrievalProfile,
        library: List[Manifest],
        k: int = 3,
    ) -> RoutingSession:
        """Start a type-faithful routing session after retrieval gate validation."""
        candidates = self.retrieve_top_k(query_vec, library, k=k)
        if not candidates:
            raise ValueError("[Router] Empty resource library - cannot route.")

        top_resource, top_similarity = candidates[0]
        if top_similarity < self.granularity_threshold:
            feedback_reason = (
                "Top-1 resource similarity is below the retrieval gate threshold. "
                "The node may be too coarse, semantically unclear, or in a resource blind spot. "
                f"Top-1 resource: {top_resource.id}; "
                f"Top-1 similarity: {top_similarity:.4f}; "
                f"Threshold: {self.granularity_threshold:.4f}. "
                "Please split this node into more concrete subtasks that map to a single "
                "capability or a small set of explicit dependencies."
            )
            raise GranularityRejectionException(
                subtask,
                SubtaskFeedback(is_valid=False, feedback_reason=feedback_reason),
            )

        top_refs = [self._ref_from_manifest(m, similarity=s) for m, s in candidates]
        session = RoutingSession(
            subtask_id=subtask.id,
            top_k_resources=top_refs,
            top_k_scores={m.id: s for m, s in candidates},
            granularity_threshold=self.granularity_threshold,
        )
        logger.info(
            "[Router] Retrieval gate passed for {} | top1={} | sim={:.4f}",
            subtask.id,
            top_resource.id,
            top_similarity,
        )
        return session

    def start_frozen_session(
        self,
        subtask: Subtask,
        frozen_result: FrozenCandidatePoolResult,
        library: List[Manifest],
    ) -> RoutingSession:
        """Start the formal session from one revision-bound frozen pool.

        The candidate generator is deliberately outside Router.  This method
        only materializes the immutable snapshot for the existing Plan
        Compiler; it performs no retrieval, threshold gate, completion, or
        compression.
        """

        if frozen_result.contract_projection.revision.subtask_id != subtask.id:
            raise ValueError("frozen_candidate_revision_subtask_mismatch")
        refs = typed_refs_from_frozen_pool(frozen_result, library)
        snapshot_ids = [
            item.resource_id
            for item in frozen_result.candidate_pool_snapshot.candidates
        ]
        if [item.resource_id for item in refs] != snapshot_ids:
            raise ValueError("frozen_candidate_materialization_order_mismatch")
        if not refs:
            raise ValueError("frozen_candidate_pool_empty")
        base_ids = {
            resource_id
            for values in frozen_result.base_candidate_ids_by_type.values()
            for resource_id in values
        }
        base_refs = [item for item in refs if item.resource_id in base_ids]
        session = RoutingSession(
            subtask_id=subtask.id,
            revision=frozen_result.contract_projection.revision,
            candidate_pool_snapshot=frozen_result.candidate_pool_snapshot,
            retrieval_evidence=frozen_result.confidence_evidence,
            frozen_candidate_resources=refs,
            top_k_resources=base_refs,
            top_k_scores={
                item.resource_id: float(item.similarity or 0.0)
                for item in base_refs
            },
            # Confidence is evidence-only in retrieval-runtime-v1.  A numeric
            # granularity threshold would be misleading and is never applied.
            granularity_threshold=0.0,
        )
        self._frozen_pool_results[
            frozen_result.candidate_pool_snapshot.candidate_pool_sha256
        ] = frozen_result
        logger.info(
            "[Router] Frozen candidate pool bound for {} | revision={} | counts={} | hash={}",
            subtask.id,
            frozen_result.contract_projection.revision.model_dump(mode="json"),
            self._type_counts(refs),
            frozen_result.candidate_pool_snapshot.candidate_pool_sha256,
        )
        terminal_progress.frozen_candidates(frozen_result, refs)
        return session

    def build_attempt(
        self,
        session: RoutingSession,
        subtask: Subtask,
        library: List[Manifest],
        context_packet: Optional[Dict[str, Any]] = None,
    ) -> Optional[AnchorExpansionAttempt]:
        """
        Build the next anchor-prefix attempt.

        Returns None when all anchor attempts are exhausted and the caller should
        downgrade to FULL_GENERATIVE_MODE.
        """
        if session.candidate_pool_snapshot is not None:
            return self._build_frozen_pool_attempt(
                session,
                subtask,
                library,
                context_packet=context_packet,
            )
        max_attempts = min(self.max_anchor_attempts, len(session.top_k_resources))
        previous_ids = (
            {r.resource_id for r in session.attempts[-1].candidate_resources}
            if session.attempts
            else set()
        )

        for attempt_index in range(len(session.attempts) + 1, max_attempts + 1):
            anchors = session.top_k_resources[:attempt_index]
            active_library = self._filter_blocked_manifests(session, library)
            dependency_selections, candidate_resources = self._build_candidate_bundle(
                anchors, active_library
            )
            candidate_resources = self._build_typed_candidate_bundle(
                subtask,
                anchors,
                active_library,
                dependency_selections,
                candidate_resources,
            )
            agent_dependency_selections, candidate_resources = (
                self._expand_agent_dependency_candidates(
                    candidate_resources,
                    active_library,
                    dependency_selections,
                )
            )
            dependency_selections = list(dependency_selections) + agent_dependency_selections
            skill_dependency_selections, candidate_resources = (
                self._expand_skill_dependency_candidates(
                    candidate_resources,
                    active_library,
                    dependency_selections,
                )
            )
            dependency_selections = list(dependency_selections) + skill_dependency_selections
            candidate_resources = self._complete_intelligent_candidates(
                subtask,
                candidate_resources,
                active_library,
            )
            candidate_resources = self._compress_candidate_bundle(
                subtask,
                candidate_resources,
                active_library,
            )
            candidate_resources = self._filter_blocked_refs(session, candidate_resources)
            candidate_ids = {r.resource_id for r in candidate_resources}

            if previous_ids and candidate_ids.issubset(previous_ids):
                attempt = AnchorExpansionAttempt(
                    attempt_index=attempt_index,
                    anchor_resources=anchors,
                    candidate_resources=candidate_resources,
                    candidate_resource_cards=[
                        self._resource_card(r) for r in candidate_resources
                    ],
                    typed_candidate_counts=self._type_counts(candidate_resources),
                    context_packet=context_packet or {},
                    dependency_selections=dependency_selections,
                    failure_type="candidate_bundle_not_expanded",
                    failure_reason="Anchor expansion did not add any new resource IDs.",
                )
                session.attempts.append(attempt)
                previous_ids = candidate_ids
                logger.warning(
                    "[Router] Attempt {} skipped for {}: candidate bundle did not expand.",
                    attempt_index,
                    session.subtask_id,
                )
                continue

            attempt = AnchorExpansionAttempt(
                attempt_index=attempt_index,
                anchor_resources=anchors,
                candidate_resources=candidate_resources,
                candidate_resource_cards=[
                    self._resource_card(r) for r in candidate_resources
                ],
                typed_candidate_counts=self._type_counts(candidate_resources),
                context_packet=context_packet or {},
                dependency_selections=dependency_selections,
            )

            try:
                decision = self._decide_bundle(
                    subtask=subtask,
                    anchors=anchors,
                    candidate_resources=candidate_resources,
                    dependency_selections=dependency_selections,
                    context_packet=context_packet,
                )
                attempt.bundle_decision = decision
            except Exception as exc:
                message = str(exc)
                provider_failure, provider_message = _classify_router_provider_exception(exc)
                if provider_failure in {
                    "provider_connection_error",
                    "provider_stream_error",
                    "provider_rate_limit",
                    "provider_auth_error",
                    "model_unavailable",
                }:
                    attempt.failure_type = provider_failure
                    attempt.failure_reason = provider_message
                    GLOBAL_CAPABILITY_REGISTRY.record_error(self.policy_model, provider_failure, provider_message)
                elif "policy_hallucinated_resource" in message:
                    attempt.failure_type = "policy_hallucinated_resource"
                elif "policy_invalid_plan" in message:
                    attempt.failure_type = "policy_invalid_plan"
                else:
                    attempt.failure_type = "policy_invalid_output"
                    attempt.failure_reason = message
                if "policy_invalid_plan" in message or "policy_hallucinated_resource" in message:
                    # A policy plan that replaces a required runtime Tool is
                    # invalid, but that must not terminate execution. Compile
                    # the deterministic runtime-tool plan from the same
                    # candidate bundle and continue with real execution.
                    attempt.bundle_decision = self._fallback_bundle_decision(
                        anchors,
                        candidate_resources,
                        dependency_selections,
                        subtask=subtask,
                        reason=f"Recovered from invalid policy resource/plan: {message}",
                    )
                    attempt.failure_type = None
                    attempt.failure_reason = None
                else:
                    session.attempts.append(attempt)
                    logger.warning(
                        "[Router] Bundle policy failed for {} attempt {}: {}",
                        session.subtask_id,
                        attempt_index,
                        exc,
                    )
                    return attempt

            if not attempt.bundle_decision.is_sufficient:
                attempt.failure_type = "bundle_insufficient"
                plan_reason = (
                    attempt.bundle_decision.application_plan.reason
                    if attempt.bundle_decision.application_plan is not None
                    else None
                )
                attempt.failure_reason = (
                    attempt.bundle_decision.reason
                    or plan_reason
                    or "Policy marked bundle insufficient."
                )
                session.attempts.append(attempt)
                logger.warning(
                    "[Router] Bundle insufficient for {} attempt {}: {}",
                    session.subtask_id,
                    attempt_index,
                    attempt.failure_reason,
                )
                return attempt

            metrics = self.compute_bundle_advantage(
                selected_resources=attempt.bundle_decision.selected_resources,
                anchor_resources=anchors,
                dependency_selections=dependency_selections,
                library=library,
                application_plan=attempt.bundle_decision.application_plan,
                subtask=subtask,
            )
            attempt.advantage_metrics = metrics
            if not metrics.passed:
                selected_ids = [
                    r.resource_id for r in attempt.bundle_decision.selected_resources
                ]
                attempt.failure_reason = (
                    f"bundle_advantage_score={metrics.bundle_advantage_score:.4f} "
                    f"< threshold={metrics.threshold:.4f}; "
                    f"selected_resources={selected_ids}; "
                    f"semantic_fit={metrics.semantic_fit:.4f}; "
                    f"joint_success={metrics.joint_success:.4f}; "
                    f"cost={metrics.total_cost_factor:.4f}; "
                    f"latency={metrics.total_latency_ms:.1f}; "
                    f"baseline_eff={metrics.baseline_efficiency:.4f}"
                )
                if self.execute_low_advantage_on_exhaustion:
                    attempt.failure_type = "bundle_low_advantage_observed"
                    session.attempts.append(attempt)
                    logger.warning(
                        "[Router] Bundle low advantage for {} attempt {}: {:.4f} < {:.4f}; executing sufficient plan and recording advantage as observation | selected={}",
                        session.subtask_id,
                        attempt_index,
                        metrics.bundle_advantage_score,
                        metrics.threshold,
                        selected_ids,
                    )
                    return attempt

                attempt.failure_type = "bundle_low_advantage"
                session.attempts.append(attempt)
                logger.warning(
                    "[Router] Bundle low advantage for {} attempt {}: {:.4f} < {:.4f} | selected={}",
                    session.subtask_id,
                    attempt_index,
                    metrics.bundle_advantage_score,
                    metrics.threshold,
                    selected_ids,
                )
                return attempt

            session.attempts.append(attempt)
            logger.success(
                "[Router] Bundle passed for {} attempt {} | advantage={:.4f}",
                session.subtask_id,
                attempt_index,
                metrics.bundle_advantage_score,
            )
            return attempt

        session.final_mode = ExecutionMode.FULL_GENERATIVE
        return None

    def _build_frozen_pool_attempt(
        self,
        session: RoutingSession,
        subtask: Subtask,
        library: List[Manifest],
        *,
        context_packet: Optional[Dict[str, Any]],
    ) -> Optional[AnchorExpansionAttempt]:
        """Compile from the exact frozen pool without any candidate mutation."""

        snapshot = session.candidate_pool_snapshot
        if snapshot is None:
            raise ValueError("frozen_candidate_snapshot_missing")
        result = self._frozen_pool_results.get(snapshot.candidate_pool_sha256)
        if result is None:
            raise ValueError("frozen_candidate_result_not_registered")
        attempt_index = len(session.attempts) + 1
        if attempt_index > max(1, self.max_anchor_attempts):
            session.final_mode = ExecutionMode.FULL_GENERATIVE
            return None

        candidate_resources = list(session.frozen_candidate_resources)
        snapshot_ids = [item.resource_id for item in snapshot.candidates]
        if [item.resource_id for item in candidate_resources] != snapshot_ids:
            raise ValueError("frozen_candidate_resources_changed")
        ref_by_id = {item.resource_id: item for item in candidate_resources}
        edge_groups: Dict[str, List[TypedResourceRef]] = {}
        for edge in result.dependency_edges:
            child = ref_by_id.get(edge.child_resource_id)
            if child is None:
                raise ValueError("frozen_dependency_edge_outside_snapshot")
            slot_id = edge.dependency_slot or (
                f"{edge.requirement_kind}:{edge.parent_resource_id}"
            )
            edge_groups.setdefault(slot_id, []).append(child)
        dependency_selections = [
            DependencySelection(
                slot_id=slot_id,
                required=True,
                selected=None,
                candidates=self._dedupe_refs(candidates),
            )
            for slot_id, candidates in sorted(edge_groups.items())
        ]

        cards: List[Dict[str, Any]] = []
        for ref in candidate_resources:
            card = self._resource_card(ref)
            card["required_candidate_edges"] = [
                edge.model_dump(mode="json")
                for edge in result.dependency_edges
                if edge.parent_resource_id == ref.resource_id
            ]
            card["optional_dependency_hints"] = [
                hint.model_dump(mode="json")
                for hint in result.optional_dependency_hints
                if hint.parent_resource_id == ref.resource_id
            ]
            cards.append(card)

        attempt = AnchorExpansionAttempt(
            attempt_index=attempt_index,
            anchor_resources=[],
            candidate_resources=candidate_resources,
            candidate_resource_cards=cards,
            typed_candidate_counts=self._type_counts(candidate_resources),
            context_packet=context_packet or {},
            dependency_selections=dependency_selections,
        )
        try:
            decision = self._decide_bundle(
                subtask=subtask,
                anchors=[],
                candidate_resources=candidate_resources,
                dependency_selections=dependency_selections,
                context_packet=context_packet,
                candidate_cards=cards,
                strict_plan_protocol=True,
                transport_retry_max=PLAN_COMPILER_TRANSPORT_RETRY_MAX,
                allow_control_model_failover=False,
                allow_deterministic_fallback=False,
            )
            attempt.bundle_decision = decision
        except Exception as exc:
            message = str(exc)
            provider_failure, provider_message = _classify_router_provider_exception(exc)
            if provider_failure in {
                "provider_connection_error",
                "provider_stream_error",
                "provider_rate_limit",
                "provider_auth_error",
                "model_unavailable",
            }:
                attempt.failure_type = provider_failure
                attempt.failure_reason = provider_message
                GLOBAL_CAPABILITY_REGISTRY.record_error(
                    self.policy_model,
                    provider_failure,
                    provider_message,
                )
            elif "policy_hallucinated_resource" in message:
                attempt.failure_type = "policy_hallucinated_resource"
            elif "policy_invalid_plan" in message:
                attempt.failure_type = "policy_invalid_plan"
            else:
                attempt.failure_type = "policy_invalid_output"
                attempt.failure_reason = message
            session.attempts.append(attempt)
            return attempt

        if attempt.bundle_decision is None:
            attempt.failure_type = "policy_invalid_plan"
            attempt.failure_reason = "Plan Compiler returned no bundle decision."
            session.attempts.append(attempt)
            return attempt
        if not attempt.bundle_decision.is_sufficient:
            attempt.failure_type = "bundle_insufficient"
            plan_reason = (
                attempt.bundle_decision.application_plan.reason
                if attempt.bundle_decision.application_plan is not None
                else None
            )
            attempt.failure_reason = (
                attempt.bundle_decision.reason
                or plan_reason
                or "Policy marked frozen candidate pool insufficient."
            )
            session.attempts.append(attempt)
            return attempt

        metrics = self.compute_bundle_advantage(
            selected_resources=attempt.bundle_decision.selected_resources,
            anchor_resources=[],
            dependency_selections=dependency_selections,
            library=library,
            application_plan=attempt.bundle_decision.application_plan,
            subtask=subtask,
        )
        attempt.advantage_metrics = metrics
        if not metrics.passed:
            attempt.failure_reason = (
                f"bundle_advantage_score={metrics.bundle_advantage_score:.4f} "
                f"< threshold={metrics.threshold:.4f}; candidate_pool_sha256="
                f"{snapshot.candidate_pool_sha256}"
            )
            attempt.failure_type = (
                "bundle_low_advantage_observed"
                if self.execute_low_advantage_on_exhaustion
                else "bundle_low_advantage"
            )
        session.attempts.append(attempt)
        if [item.resource_id for item in attempt.candidate_resources] != snapshot_ids:
            raise ValueError("plan_compiler_candidate_set_changed")
        return attempt

    def _filter_blocked_manifests(
        self,
        session: RoutingSession,
        library: Sequence[Manifest],
    ) -> List[Manifest]:
        """Return resources still eligible after current-session infra blocks."""
        blocked_resources = set(session.blocked_resources)
        blocked_models = set(session.blocked_base_models)
        filtered: List[Manifest] = []
        for manifest in library:
            if manifest.id in blocked_resources:
                continue
            base_model = self._default_base_model(manifest.id, manifest.type)
            if manifest.type == ManifestType.MODEL and (
                manifest.id in blocked_models or base_model in blocked_models
            ):
                continue
            if manifest.type == ManifestType.AGENT and base_model in blocked_models:
                continue
            filtered.append(manifest)
        return filtered

    def _filter_blocked_refs(
        self,
        session: RoutingSession,
        refs: Sequence[TypedResourceRef],
    ) -> List[TypedResourceRef]:
        """Remove resources/base models blocked by infra failures in this session."""
        blocked_resources = set(session.blocked_resources)
        blocked_models = set(session.blocked_base_models)
        filtered: List[TypedResourceRef] = []
        for ref in refs:
            if ref.resource_id in blocked_resources:
                continue
            if ref.resource_type == ManifestType.MODEL:
                model_id = ref.base_model or ref.resource_id
                if model_id in blocked_models:
                    continue
            if ref.resource_type == ManifestType.AGENT and ref.base_model in blocked_models:
                continue
            filtered.append(ref)
        return filtered

    def block_infra_failure(
        self,
        session: RoutingSession,
        attempt: AnchorExpansionAttempt,
        selected_resources: Sequence[TypedResourceRef],
        failure_type: str,
        result_cost_metric: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Temporarily block failed infra resources within a single routing session."""
        if failure_type not in {
            "provider_connection_error",
            "provider_stream_error",
            "provider_rate_limit",
            "model_unavailable",
        }:
            return

        blocked_resources = set(session.blocked_resources)
        blocked_base_models = set(session.blocked_base_models)
        result_cost_metric = result_cost_metric or {}
        metric_base_model = result_cost_metric.get("base_model") or result_cost_metric.get("model")
        metric_resource = result_cost_metric.get("agent_id") or result_cost_metric.get("resource_id")

        if metric_resource:
            blocked_resources.add(str(metric_resource))
        else:
            for ref in selected_resources:
                if ref.resource_type in {ManifestType.AGENT, ManifestType.MODEL}:
                    blocked_resources.add(ref.resource_id)

        if metric_base_model:
            blocked_base_models.add(str(metric_base_model))
        elif not metric_resource:
            for ref in selected_resources:
                if ref.resource_type == ManifestType.MODEL:
                    blocked_base_models.add(str(ref.base_model or ref.resource_id))
                elif ref.resource_type == ManifestType.AGENT and ref.base_model:
                    blocked_base_models.add(str(ref.base_model))

        session.blocked_resources = sorted(blocked_resources)
        session.blocked_base_models = sorted(blocked_base_models)
        attempt.blocked_resources = list(session.blocked_resources)
        attempt.blocked_base_models = list(session.blocked_base_models)
        logger.warning(
            "[Router] Infra block applied for {} | resources={} | base_models={}",
            session.subtask_id,
            session.blocked_resources,
            session.blocked_base_models,
        )

    def record_attempt_failure(
        self,
        session: RoutingSession,
        attempt: AnchorExpansionAttempt,
        failure_type: str,
        failure_reason: str,
    ) -> None:
        """Record post-execution failure on the attempt before expansion."""
        attempt.failure_type = failure_type
        attempt.failure_reason = failure_reason
        if failure_type.startswith("tool_") or failure_type == "operation_misuse":
            decision = attempt.bundle_decision
            failed_tool_ids = {
                ref.resource_id
                for ref in (decision.selected_resources if decision is not None else [])
                if ref.resource_type == ManifestType.TOOL
            }
            if failed_tool_ids:
                session.blocked_resources = sorted(
                    set(session.blocked_resources) | failed_tool_ids
                )
                attempt.blocked_resources = list(session.blocked_resources)
                logger.warning(
                    "[Router] Tool execution block applied for {} | resources={}",
                    session.subtask_id,
                    sorted(failed_tool_ids),
                )
        logger.warning(
            "[Router] Attempt {} for {} failed after execution | {}: {}",
            attempt.attempt_index,
            session.subtask_id,
            failure_type,
            failure_reason,
        )

    def has_remaining_attempts(self, session: RoutingSession) -> bool:
        return len(session.attempts) < min(self.max_anchor_attempts, len(session.top_k_resources))

    def select_best_observed_bundle(
        self, session: RoutingSession
    ) -> Optional[AnchorExpansionAttempt]:
        """
        Pick the best policy-sufficient bundle that was skipped only because of
        low advantage. This keeps full generation as a true last resort while
        preserving the advantage score as training data instead of a hard veto.
        """
        candidates: List[AnchorExpansionAttempt] = []
        for attempt in session.attempts:
            decision = attempt.bundle_decision
            if decision is None or not decision.is_sufficient or not decision.selected_resources:
                continue
            if attempt.advantage_metrics is None:
                continue
            if attempt.failure_type not in {
                None,
                "bundle_low_advantage",
                "bundle_low_advantage_observed",
            }:
                continue
            candidates.append(attempt)

        if not candidates:
            return None

        return max(
            candidates,
            key=lambda attempt: attempt.advantage_metrics.bundle_advantage_score,
        )

    # -- Bundle Advantage --------------------------------------------------

    def compute_bundle_advantage(
        self,
        selected_resources: Sequence[TypedResourceRef],
        anchor_resources: Sequence[TypedResourceRef],
        dependency_selections: Sequence[DependencySelection],
        library: List[Manifest],
        application_plan: Optional[ResourceApplicationPlan] = None,
        subtask: Optional[Subtask] = None,
    ) -> BundleAdvantageMetrics:
        """Compute group-level resource/plan advantage against full-generation baseline."""
        selected = list(selected_resources)
        selected_ids = {r.resource_id for r in selected}
        anchor_ids = {r.resource_id for r in anchor_resources}

        if not selected:
            return self._zero_advantage_metrics(required_slot_coverage=0.0)

        missing_required = False
        for selection in dependency_selections:
            if not selection.required:
                continue
            slot_candidate_ids = {c.resource_id for c in selection.candidates}
            if not slot_candidate_ids or selected_ids.isdisjoint(slot_candidate_ids):
                missing_required = True
                break

        if missing_required:
            return self._zero_advantage_metrics(required_slot_coverage=0.0)

        selected_anchor_sims = [
            r.similarity for r in selected if r.resource_id in anchor_ids and r.similarity is not None
        ]
        anchor_sims = [r.similarity for r in anchor_resources if r.similarity is not None]
        task_anchor_fit = max(selected_anchor_sims or anchor_sims or [0.0])

        dependency_fit = 1.0
        has_natural_slot = False
        for selection in dependency_selections:
            for candidate in selection.candidates:
                if candidate.resource_id in selected_ids and candidate.similarity is not None:
                    dependency_fit *= max(candidate.similarity, 0.0)
                    has_natural_slot = True
                    break
        if not has_natural_slot:
            dependency_fit = 1.0

        input_binding_coverage = self._estimate_input_binding_coverage(
            application_plan,
            selected,
            subtask,
        )
        output_contract_compatibility = self._estimate_output_contract_compatibility(
            application_plan,
            subtask,
        )

        semantic_fit = (
            max(task_anchor_fit, 0.0)
            * dependency_fit
            * input_binding_coverage
            * output_contract_compatibility
        )
        required_slot_coverage = 1.0

        joint_success = 1.0
        total_cost_factor = 0.0
        total_latency_ms = 0.0
        for ref in selected:
            success, cost, latency = self._normalized_utility(ref, library)
            joint_success *= success
            total_cost_factor += cost
            total_latency_ms += latency

        baseline_efficiency, baseline_missing = self._baseline_efficiency(library)
        bundle_efficiency = (
            semantic_fit
            * required_slot_coverage
            * joint_success
            / ((total_cost_factor + self.epsilon) * math.log10(10 + total_latency_ms))
        )
        bundle_advantage_score = bundle_efficiency / max(baseline_efficiency, self.epsilon)
        passed = bundle_advantage_score >= self.bundle_advantage_threshold

        return BundleAdvantageMetrics(
            semantic_fit=semantic_fit,
            required_slot_coverage=required_slot_coverage,
            input_binding_coverage=input_binding_coverage,
            output_contract_compatibility=output_contract_compatibility,
            joint_success=joint_success,
            total_cost_factor=total_cost_factor,
            total_latency_ms=total_latency_ms,
            baseline_efficiency=baseline_efficiency,
            bundle_efficiency=bundle_efficiency,
            bundle_advantage_score=bundle_advantage_score,
            threshold=self.bundle_advantage_threshold,
            passed=passed,
            baseline_missing=baseline_missing,
            plan_advantage_score=bundle_advantage_score,
        )

    def _zero_advantage_metrics(self, required_slot_coverage: float) -> BundleAdvantageMetrics:
        baseline = 1.0
        return BundleAdvantageMetrics(
            semantic_fit=0.0,
            required_slot_coverage=required_slot_coverage,
            input_binding_coverage=0.0 if required_slot_coverage == 0.0 else 1.0,
            output_contract_compatibility=1.0,
            joint_success=0.0,
            total_cost_factor=0.0,
            total_latency_ms=0.0,
            baseline_efficiency=baseline,
            bundle_efficiency=0.0,
            bundle_advantage_score=0.0,
            threshold=self.bundle_advantage_threshold,
            passed=False,
        )

    def _estimate_input_binding_coverage(
        self,
        application_plan: Optional[ResourceApplicationPlan],
        selected_resources: Sequence[TypedResourceRef],
        subtask: Optional[Subtask],
    ) -> float:
        """
        Light-weight plan gate for required inputs.

        This is intentionally conservative but generic: if a required file-like
        input is declared, the plan must either bind it, select a Resource, or
        mention an existing-looking path in the subtask. Exact path resolution is
        still done by the Orchestrator preflight before execution.
        """
        if application_plan is None or not application_plan.steps:
            return 1.0

        selected_resource_ids = {r.resource_id for r in selected_resources}
        has_resource = any(r.resource_type == ManifestType.RESOURCE for r in selected_resources)
        task_text = subtask.description if subtask is not None else ""
        path_like_tokens = re.findall(r"[\w./:\\-]+\.[A-Za-z0-9]{1,8}", task_text)

        for step in application_plan.steps:
            raw = self.resource_index.get(step.resource_id, {})
            for contract in self._manifest_input_contracts(raw):
                if not bool(contract.get("required", True)):
                    continue
                name = str(contract.get("name", ""))
                kind = self._contract_kind(contract)
                # Binding presence is structural.  Empty strings/lists, zero,
                # false, and explicit null remain values for typed preflight to
                # validate; the Router must not erase them by truthiness.
                if name in step.input_bindings:
                    continue
                if kind in {"file_path", "artifact_ref"}:
                    if has_resource or path_like_tokens:
                        continue
                    return 0.0
                if step.resource_id in selected_resource_ids:
                    continue
                return 0.0
        return 1.0

    def _estimate_output_contract_compatibility(
        self,
        application_plan: Optional[ResourceApplicationPlan],
        subtask: Optional[Subtask],
    ) -> float:
        """Estimate whether a planned final Tool output can satisfy the requested artifact."""
        if application_plan is None or not application_plan.final_output_from:
            return 1.0
        if subtask is None:
            return 1.0

        final_step = next(
            (
                step for step in application_plan.steps
                if step.output_key == application_plan.final_output_from
            ),
            None,
        )
        if final_step is None:
            return 0.0

        raw = self.resource_index.get(final_step.resource_id, {})
        resource_type = self._coerce_manifest_type(
            raw.get("type", {}).get("resource_type") or raw.get("resource_type")
        )
        if resource_type != ManifestType.TOOL:
            return 1.0

        artifact_value = self._manifest_output_artifact(raw)
        if artifact_value is None and final_step.expected_output_contract is not None:
            if final_step.expected_output_contract.artifact_type is not None:
                artifact_value = final_step.expected_output_contract.artifact_type.value

        if artifact_value is None:
            return 0.0
        return 1.0 if artifact_value == subtask.artifact_type.value else 0.0

    # -- Legacy Adjudication ----------------------------------------------

    def route_task(
        self,
        subtask: Subtask,
        query_vec: Vector,
        library: List[Manifest],
    ) -> RoutingDecision:
        """Backward-compatible entrypoint using retrieval gate and legacy decision."""
        self.start_session(subtask, query_vec, library)
        return self._adjudicate_core(query_vec, library)

    def adjudicate(
        self,
        query_vec: Vector,
        library: List[Manifest],
        subtask: Optional[Subtask] = None,
    ) -> RoutingDecision:
        """Backward-compatible single-resource adjudication API."""
        if subtask is not None:
            self.start_session(subtask, query_vec, library)
        return self._adjudicate_core(query_vec, library)

    def _adjudicate_core(self, query_vec: Vector, library: List[Manifest]) -> RoutingDecision:
        candidates = self.retrieve_top_k(query_vec, library, k=3)
        if not candidates:
            raise ValueError("[Router] Empty resource library - cannot adjudicate.")

        best_resource, similarity = candidates[0]
        ap = best_resource.advantage_score
        if similarity >= self.confidence_threshold and ap > 5.0:
            mode = ExecutionMode.BYPASS
        else:
            mode = ExecutionMode.SEMI_GENERATIVE

        return RoutingDecision(
            mode=mode,
            resource=best_resource,
            metrics=RoutingMetrics(similarity=similarity, advantage=ap),
        )

    # -- Candidate Bundle Internals ---------------------------------------

    def _build_candidate_bundle(
        self,
        anchors: Sequence[TypedResourceRef],
        library: List[Manifest],
    ) -> Tuple[List[DependencySelection], List[TypedResourceRef]]:
        anchor_refs = [
            anchor.model_copy(
                update={"candidate_origin": "anchor", "injected_reason": None}
            )
            for anchor in anchors
        ]
        explicit_refs: List[TypedResourceRef] = []
        dependency_selections: List[DependencySelection] = []

        for anchor in anchor_refs:
            explicit_ids, slots = self._extract_dependencies(anchor.resource_id)
            dependency_origin = (
                "agent_dependency_hint"
                if anchor.resource_type == ManifestType.AGENT
                else "explicit_dependency"
            )
            for dep_id in explicit_ids:
                dep_ref = self._ref_from_resource_id(dep_id, library)
                if dep_ref is not None:
                    explicit_refs.append(
                        dep_ref.model_copy(
                            update={
                                "candidate_origin": dependency_origin,
                                "injected_reason": f"anchor:{anchor.resource_id}",
                            }
                        )
                    )
                else:
                    logger.warning("[Router] Unresolved explicit dependency: {}", dep_id)

            for slot in slots:
                candidates = self._retrieve_dependency_slot(slot, library)
                if anchor.resource_type == ManifestType.AGENT:
                    candidates = [
                        candidate.model_copy(
                            update={
                                "candidate_origin": "agent_dependency_hint",
                                "injected_reason": (
                                    f"agent:{anchor.resource_id};slot:{slot.slot_id}"
                                ),
                            }
                        )
                        for candidate in candidates
                    ]
                dependency_selections.append(
                    DependencySelection(
                        slot_id=slot.slot_id,
                        required=slot.required,
                        selected=None,
                        candidates=candidates,
                    )
                )

        return dependency_selections, self._dedupe_refs(
            anchor_refs
            + explicit_refs
            + [c for s in dependency_selections for c in s.candidates]
        )

    def _build_typed_candidate_bundle(
        self,
        subtask: Subtask,
        anchors: Sequence[TypedResourceRef],
        library: List[Manifest],
        dependency_selections: Sequence[DependencySelection],
        existing_refs: Sequence[TypedResourceRef],
        query_profile: Optional[QueryRetrievalProfile] = None,
    ) -> List[TypedResourceRef]:
        """Add fixed per-type retrieval candidates before compact-bundle compression."""
        refs: List[TypedResourceRef] = list(existing_refs)
        existing_ids = {ref.resource_id for ref in refs}

        from .resource_compatibility import (
            current_node_contract_text,
            filter_hard_compatible_manifests,
        )

        query_text = (
            f"{current_node_contract_text(subtask)}\n"
            f"Artifact type: {subtask.artifact_type.value}"
        )

        compatible_library = filter_hard_compatible_manifests(
            subtask,
            library,
            self.resource_index,
        )
        query_vec = query_profile
        try:
            from .resource_loader import encode_query_profile

            query_vec = query_profile or encode_query_profile(
                query_text,
                use_hyde=True,
                cost_ledger=self.cost_ledger,
                subtask_id=subtask.id,
                subtask_revision=0,
            )
            typed_retrieved = self.retrieve_top_k_by_type(
                query_vec,
                compatible_library,
                quotas=self.typed_retrieval_quotas,
            )
        except (ModelAccountingError, ModelTransportError):
            raise
        except Exception as exc:
            logger.warning("[Router] Typed retrieval fell back to anchor/dependency refs: {}", exc)
            typed_retrieved = {}

        for manifest_type, retrieved in typed_retrieved.items():
            for manifest, score in retrieved:
                if manifest.id in existing_ids:
                    continue
                refs.append(
                    self._ref_from_manifest(manifest, similarity=score).model_copy(
                        update={
                            "candidate_origin": "typed_retrieval",
                            "injected_reason": f"type_quota:{manifest_type.value}",
                        }
                    )
                )
                existing_ids.add(manifest.id)

        # Keep dependency-slot alternatives as first-class candidates; they are
        # already typed and often carry role information absent from global search.
        for selection in dependency_selections:
            for candidate in selection.candidates:
                if candidate.resource_id in existing_ids:
                    continue
                refs.append(candidate)
                existing_ids.add(candidate.resource_id)

        for anchor in anchors:
            if anchor.resource_id in existing_ids:
                continue
            refs.append(anchor)
            existing_ids.add(anchor.resource_id)

        # Embedding retrieval is deliberately broad, but it can still bury a
        # concrete executable behind generic models or unrelated tools.  Add
        # strong runtime/domain matches before compression so a matching REST
        # or MCP tool remains routable even when its embedding score is weak.
        for manifest in compatible_library:
            if manifest.id in existing_ids or manifest.type != ManifestType.TOOL:
                continue
            candidate = self._ref_from_manifest(manifest, similarity=0.0)
            if self._runtime_intent_match(subtask, candidate):
                refs.append(candidate.model_copy(update={
                    "candidate_origin": "capability_completion",
                    "injected_reason": "runtime_intent_match",
                }))
                existing_ids.add(manifest.id)

        logger.info(
            "[Router] Typed candidate pool for {} | counts={}",
            subtask.id,
            self._type_counts(refs),
        )
        return self._dedupe_refs(refs)

    @staticmethod
    def _trace_ref(ref: TypedResourceRef) -> Dict[str, Any]:
        return {
            "resource_id": ref.resource_id,
            "resource_type": ref.resource_type.value,
            "similarity": float(ref.similarity or 0.0),
            "candidate_origin": ref.candidate_origin,
            "injected_reason": ref.injected_reason,
        }

    def build_candidate_trace(
        self,
        subtask: Subtask,
        library: List[Manifest],
        *,
        query_profile: Optional[QueryRetrievalProfile] = None,
    ) -> Dict[str, Any]:
        """Run candidate construction without invoking the Plan Compiler.

        This is the public evaluation boundary for retrieval experiments. It uses
        the same compatibility, dependency expansion, completion, and compression
        helpers as normal routing, but deliberately excludes anchor attempts and
        all policy-model calls.
        """

        from .resource_compatibility import (
            classify_tool_compatibility,
            current_node_contract_text,
            filter_hard_compatible_manifests,
            normalize_subtask_contract,
        )
        from .resource_loader import encode_query_profile

        query_text = (
            f"{current_node_contract_text(subtask)}\n"
            f"Artifact type: {subtask.artifact_type.value}"
        )
        profile = query_profile or encode_query_profile(query_text, use_hyde=True)
        compatible_library = filter_hard_compatible_manifests(
            subtask,
            library,
            self.resource_index,
        )
        compatible_ids = {manifest.id for manifest in compatible_library}
        node_contract = normalize_subtask_contract(subtask)
        compatibility_rejected: List[Dict[str, Any]] = []
        compatibility_warnings: List[Dict[str, Any]] = []
        for manifest in library:
            if manifest.type != ManifestType.TOOL:
                continue
            raw = self.resource_index.get(manifest.id, {})
            if not isinstance(raw, dict):
                continue
            decision = classify_tool_compatibility(node_contract, raw)
            record = {
                "resource_id": manifest.id,
                "resource_type": manifest.type.value,
                "verdict": decision.verdict.value,
                "filter_reasons": list(decision.reasons),
                "soft_reasons": list(decision.soft_reasons),
            }
            if manifest.id not in compatible_ids:
                compatibility_rejected.append(record)
            elif decision.soft_reasons:
                compatibility_warnings.append(record)

        typed_pre_hard = self.retrieve_top_k_by_type(
            profile,
            compatible_library,
            quotas=self.typed_retrieval_quotas,
            apply_hard_gates=False,
            apply_utility_rerank=False,
        )
        typed = self.retrieve_top_k_by_type(
            profile,
            compatible_library,
            quotas=self.typed_retrieval_quotas,
            apply_hard_gates=None,
            apply_utility_rerank=True,
        )
        typed_refs = [
            self._ref_from_manifest(manifest, similarity=score).model_copy(
                update={
                    "candidate_origin": "typed_retrieval",
                    "injected_reason": f"type_quota:{manifest_type.value}",
                }
            )
            for manifest_type, ranked in typed.items()
            for manifest, score in ranked
        ]
        hard_rejected = [
            {
                "resource_id": manifest.id,
                "resource_type": manifest.type.value,
                "filter_reason": "query_hard_gate",
            }
            for ranked in typed_pre_hard.values()
            for manifest, _ in ranked
            if not self._passes_query_hard_gate(manifest, profile.hard_requirements)
        ]

        candidates = self._build_typed_candidate_bundle(
            subtask,
            [],
            compatible_library,
            [],
            typed_refs,
            query_profile=profile,
        )
        agent_selections, candidates = self._expand_agent_dependency_candidates(
            candidates,
            compatible_library,
            [],
            query_profile=profile,
        )
        skill_selections, candidates = self._expand_skill_dependency_candidates(
            candidates,
            compatible_library,
            agent_selections,
            query_profile=profile,
        )
        candidates = self._complete_intelligent_candidates(
            subtask,
            candidates,
            compatible_library,
        )
        pre_compression = self._dedupe_refs(candidates)
        compact = self._compress_candidate_bundle(
            subtask,
            pre_compression,
            compatible_library,
        )

        dependency_ids = {
            ref.resource_id
            for ref in pre_compression
            if ref.candidate_origin in {"agent_dependency_hint", "skill_dependency_hint", "dependency_slot"}
        }
        runtime_ids = {
            ref.resource_id
            for ref in pre_compression
            if ref.candidate_origin in {"runtime_intent", "domain_specific_tool"}
            or str(ref.injected_reason or "").startswith("runtime_intent")
        }
        return {
            "strategy": self.retrieval_strategy,
            "query_profile": {
                "raw_query_text": profile.raw_query_text,
                "capability_text": profile.capability_text,
                "constraint_text": profile.constraint_text,
                "hard_requirements": profile.hard_requirements,
                "profile_version": profile.profile_version,
            },
            "typed_semantic_candidates": {
                manifest_type.value: [
                    {
                        "resource_id": manifest.id,
                        "resource_type": manifest.type.value,
                        "score": float(score),
                    }
                    for manifest, score in ranked
                ]
                for manifest_type, ranked in typed.items()
            },
            "compatibility_rejected_candidates": compatibility_rejected,
            "compatibility_warnings": compatibility_warnings,
            "hard_rejected_candidates": hard_rejected,
            "dependency_added_candidates": [
                self._trace_ref(ref) for ref in pre_compression if ref.resource_id in dependency_ids
            ],
            "runtime_intent_candidates": [
                self._trace_ref(ref) for ref in pre_compression if ref.resource_id in runtime_ids
            ],
            "pre_compression_candidates": [self._trace_ref(ref) for ref in pre_compression],
            "compact_candidates": [self._trace_ref(ref) for ref in compact],
            "dependency_slots": [
                selection.model_dump(mode="json")
                for selection in list(agent_selections) + list(skill_selections)
            ],
        }

    def compile_application_plan(
        self,
        subtask: Subtask,
        explicit_candidates: Sequence[TypedResourceRef | Dict[str, Any] | str],
        library: List[Manifest],
        *,
        context_packet: Optional[Dict[str, Any]] = None,
        input_payload_guard: Optional[Callable[[Mapping[str, Any]], None]] = None,
        invocation_identity: Optional[Mapping[str, Any]] = None,
        transport_retry_max: int = PLAN_COMPILER_TRANSPORT_RETRY_MAX,
    ) -> BundleAdequacyDecision:
        """Compile a plan from an explicit, already-constructed candidate set.

        This is the experiment-safe public boundary for controlled candidate
        studies.  It reuses the production Plan Compiler and validator, does
        not retrieve or silently add resources, and rejects IDs outside the
        supplied library.
        """

        manifest_by_id = {manifest.id: manifest for manifest in library}
        refs: List[TypedResourceRef] = []
        for candidate in explicit_candidates:
            if isinstance(candidate, TypedResourceRef):
                resource_id = candidate.resource_id
                ref = candidate
            elif isinstance(candidate, str):
                resource_id = candidate
                manifest = manifest_by_id.get(resource_id)
                if manifest is None:
                    raise ValueError(
                        f"experiment_candidate_outside_library: {resource_id}"
                    )
                ref = self._ref_from_manifest(manifest)
            elif isinstance(candidate, dict):
                resource_id = str(
                    candidate.get("resource_id") or candidate.get("id") or ""
                ).strip()
                manifest = manifest_by_id.get(resource_id)
                if manifest is None:
                    raise ValueError(
                        f"experiment_candidate_outside_library: {resource_id}"
                    )
                ref = self._ref_from_manifest(
                    manifest,
                    similarity=float(
                        candidate.get("similarity", candidate.get("score", 0.0))
                        or 0.0
                    ),
                ).model_copy(
                    update={
                        "candidate_origin": str(
                            candidate.get("candidate_origin") or "explicit_candidate"
                        ),
                        "injected_reason": candidate.get("injected_reason"),
                    }
                )
            else:
                raise TypeError(
                    "explicit_candidates entries must be resource IDs, mappings, "
                    "or TypedResourceRef objects"
                )
            if resource_id not in manifest_by_id:
                raise ValueError(
                    f"experiment_candidate_outside_library: {resource_id}"
                )
            refs.append(ref)

        refs = self._dedupe_refs(refs)
        if not refs:
            raise ValueError("experiment_empty_candidate_set")

        identity = {
            "subtask_id": subtask.id,
            **{
                str(key): value
                for key, value in dict(invocation_identity or {}).items()
                if str(key) != "subtask_id"
            },
        }
        self.last_plan_compiler_trace = {
            "subtask_id": subtask.id,
            "invocation_identity": identity,
            "policy_model": self.policy_model,
            "candidate_resource_ids": [ref.resource_id for ref in refs],
            "candidate_count": len(refs),
            "context_packet_present": bool(context_packet),
            "status": "started",
        }
        self._last_policy_call_metadata = {}
        try:
            decision = self._decide_bundle(
                subtask=subtask,
                anchors=[],
                candidate_resources=refs,
                dependency_selections=[],
                context_packet=context_packet,
                strict_plan_protocol=True,
                input_payload_guard=input_payload_guard,
                transport_retry_max=max(0, int(transport_retry_max)),
                allow_control_model_failover=False,
            )
        except Exception as exc:
            self.last_plan_compiler_trace.update(
                {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "policy_call": dict(self._last_policy_call_metadata),
                }
            )
            raise
        self.last_plan_compiler_trace.update(
            {
                "status": "completed",
                "policy_model": self.policy_model,
                "decision": decision.model_dump(mode="json"),
                "policy_call": dict(self._last_policy_call_metadata),
            }
        )
        return decision

    def _compress_candidate_bundle(
        self,
        subtask: Subtask,
        refs: Sequence[TypedResourceRef],
        library: List[Manifest],
    ) -> List[TypedResourceRef]:
        """Conservatively compress typed candidates into compact Plan Compiler input."""
        from .resource_compatibility import filter_hard_compatible_candidates

        compatible_refs = filter_hard_compatible_candidates(
            subtask,
            refs,
            self.resource_index,
        )
        eligible = [ref for ref in compatible_refs if self._passes_hard_gate(ref)]
        scored = [
            (self._candidate_bundle_score(subtask, ref, library), ref)
            for ref in self._dedupe_refs(eligible)
        ]
        scored.sort(key=lambda item: item[0], reverse=True)

        selected: List[TypedResourceRef] = []
        per_type_counts: Dict[ManifestType, int] = {}
        family_seen: Dict[Tuple[ManifestType, str], int] = {}
        ref_by_id = {ref.resource_id: ref for _, ref in scored}

        def can_add(ref: TypedResourceRef) -> bool:
            if ref.resource_id in {item.resource_id for item in selected}:
                return True
            type_limit = self.compact_bundle_quotas.get(ref.resource_type, 0)
            if type_limit <= 0 or per_type_counts.get(ref.resource_type, 0) >= type_limit:
                return False
            if len(selected) >= self.compact_bundle_total_max:
                return False
            family_key = (ref.resource_type, self._family_id(ref.resource_id))
            return not (
                family_seen.get(family_key, 0) >= 1
                and not self._family_dedup_exception(ref, selected, subtask)
            )

        def add_ref(ref: TypedResourceRef) -> bool:
            if ref.resource_id in {item.resource_id for item in selected}:
                return True
            if not can_add(ref):
                return False
            selected.append(ref)
            per_type_counts[ref.resource_type] = per_type_counts.get(ref.resource_type, 0) + 1
            family_key = (ref.resource_type, self._family_id(ref.resource_id))
            family_seen[family_key] = family_seen.get(family_key, 0) + 1
            return True

        # Reserve a small number of complementary execution intents before
        # considering optional Agent/Skill bundles.  Otherwise required
        # dependencies of merely *candidate* Skills can consume the Tool
        # budget and displace a direct PDF reader, test runner, or file reader.
        # This is slot-shaped preservation only; it does not select a final
        # workflow or force the Plan Compiler to use any resource.
        runtime_matches = [
            item for item in scored
            if self._runtime_intent_match(subtask, item[1])
        ]
        runtime_matches.sort(
            key=lambda item: (
                2.0 * self._runtime_intent_specificity(subtask, item[1])
                + item[0]
            ),
            reverse=True,
        )
        reserved_runtime_slots: set[str] = set()
        for score, ref in runtime_matches:
            if len(reserved_runtime_slots) >= 2:
                break
            if ref.resource_type != ManifestType.TOOL:
                continue
            slot = self._runtime_intent_slot(subtask, ref)
            if slot in reserved_runtime_slots:
                continue
            if per_type_counts.get(ref.resource_type, 0) >= self.compact_bundle_quotas.get(ref.resource_type, 0):
                break
            if add_ref(ref):
                reserved_runtime_slots.add(slot)

        # Reserve only explicit required dependencies, and only together with
        # the parent candidate that makes them necessary. Recommended and
        # optional hints remain ordinary scored candidates. Runtime anchors
        # already selected above retain priority over these conditional groups.
        required_groups: List[Tuple[float, List[TypedResourceRef]]] = []
        for parent_score, parent in scored:
            required_ids = self._required_dependency_ids(parent.resource_id)
            required_refs = [ref_by_id[item] for item in required_ids if item in ref_by_id]
            if required_refs:
                required_groups.append((parent_score, [parent, *required_refs]))
        required_groups.sort(key=lambda item: item[0], reverse=True)
        for _, group in required_groups:
            pending = [ref for ref in group if ref.resource_id not in {item.resource_id for item in selected}]
            projected_type_counts = dict(per_type_counts)
            feasible = len(selected) + len(pending) <= self.compact_bundle_total_max
            for ref in pending:
                projected_type_counts[ref.resource_type] = projected_type_counts.get(ref.resource_type, 0) + 1
                if projected_type_counts[ref.resource_type] > self.compact_bundle_quotas.get(ref.resource_type, 0):
                    feasible = False
            if not feasible:
                continue
            if all(can_add(ref) for ref in pending):
                for ref in pending:
                    add_ref(ref)

        for score, ref in scored:
            if ref.resource_id in {item.resource_id for item in selected}:
                continue
            required_ids = self._required_dependency_ids(ref.resource_id)
            if required_ids and not set(required_ids).issubset(
                {item.resource_id for item in selected}
            ):
                # A conditional resource is not independently executable when
                # its declared required dependency could not fit. Keeping the
                # parent alone would expose an invalid bundle to the compiler.
                continue
            type_limit = self.compact_bundle_quotas.get(ref.resource_type, 0)
            if type_limit <= 0:
                continue
            if per_type_counts.get(ref.resource_type, 0) >= type_limit:
                continue
            family_id = self._family_id(ref.resource_id)
            family_key = (ref.resource_type, family_id)
            if family_seen.get(family_key, 0) >= 1 and not self._family_dedup_exception(ref, selected, subtask):
                continue
            add_ref(ref)
            if len(selected) >= self.compact_bundle_total_max:
                break

        if (
            any(ref.resource_type == ManifestType.AGENT for ref in selected)
            and not any(ref.resource_type == ManifestType.MODEL for ref in selected)
        ):
            model_candidate = next(
                (ref for _, ref in scored if ref.resource_type == ManifestType.MODEL),
                None,
            )
            if model_candidate is not None:
                add_ref(model_candidate)
        selected = selected[: self.compact_bundle_total_max]
        logger.info(
            "[Router] Compact bundle for {} | counts={} | ids={}",
            subtask.id,
            self._type_counts(selected),
            [ref.resource_id for ref in selected],
        )
        return self._dedupe_refs(selected)

    def _type_counts(self, refs: Sequence[TypedResourceRef]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for ref in refs:
            key = ref.resource_type.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    def _extract_dependencies(self, resource_id: str) -> Tuple[List[str], List[DependencySlot]]:
        raw = self.resource_index.get(resource_id, {})
        routing = raw.get("routing", {}) if isinstance(raw, dict) else {}
        type_specific = raw.get("type_specific", {}) if isinstance(raw, dict) else {}
        agent_block = type_specific.get("agent", {}) if isinstance(type_specific, dict) else {}
        skill_block = type_specific.get("skill", {}) if isinstance(type_specific, dict) else {}
        raw_deps: List[Any] = []
        for candidate in (
            raw.get("dependency_slots"),
            routing.get("dependency_slots") if isinstance(routing, dict) else None,
            raw.get("dependencies"),
            raw.get("dependence"),
            raw.get("depends"),
        ):
            if isinstance(candidate, list):
                raw_deps.extend(candidate)
            elif candidate is not None:
                raw_deps.append(candidate)
        if isinstance(agent_block, dict):
            for key in ("recommended_dependency_ids", "allowed_dependency_ids"):
                candidate = agent_block.get(key)
                if isinstance(candidate, list):
                    raw_deps.extend(candidate)
        if isinstance(skill_block, dict):
            for key in ("required_resource_ids", "optional_resource_ids"):
                candidate = skill_block.get(key)
                if isinstance(candidate, list):
                    raw_deps.extend(candidate)
        if isinstance(raw_deps, dict):
            raw_deps = [raw_deps]
        if not isinstance(raw_deps, list):
            return [], []

        explicit_ids: List[str] = []
        slots: List[DependencySlot] = []
        for idx, item in enumerate(raw_deps):
            if isinstance(item, str):
                if item in self.resource_index:
                    explicit_ids.append(item)
                else:
                    slots.append(
                        DependencySlot(
                            slot_id=f"{resource_id}_dep_{idx}",
                            description=item,
                            allowed_types=list(_DEFAULT_NATURAL_DEP_TYPES),
                        )
                    )
                continue

            if not isinstance(item, dict):
                continue

            dep_id = item.get("resource_id") or item.get("id")
            if dep_id:
                explicit_ids.append(str(dep_id))
                continue

            description = item.get("description") or item.get("query") or item.get("name")
            if not description:
                continue

            raw_allowed = item.get("allowed_types") or item.get("resource_types") or []
            allowed = [self._coerce_manifest_type(t) for t in raw_allowed]
            allowed = [t for t in allowed if t is not None]
            if not allowed:
                allowed = list(_DEFAULT_NATURAL_DEP_TYPES)

            slots.append(
                DependencySlot(
                    slot_id=str(item.get("slot_id") or item.get("name") or f"{resource_id}_dep_{idx}"),
                    description=str(description),
                    allowed_types=allowed,
                    top_k_per_type=int(item.get("top_k_per_type", 3)),
                    required=bool(item.get("required", True)),
                )
            )
        return list(dict.fromkeys(explicit_ids)), slots

    def _required_dependency_ids(self, resource_id: str) -> List[str]:
        """Return only dependencies explicitly declared as required."""

        raw = self.resource_index.get(resource_id, {})
        if not isinstance(raw, dict):
            return []
        required: List[str] = []
        type_specific = raw.get("type_specific", {})
        if isinstance(type_specific, dict):
            skill = type_specific.get("skill", {})
            agent = type_specific.get("agent", {})
            if isinstance(skill, dict):
                required.extend(str(item) for item in skill.get("required_resource_ids", []) if item)
            if isinstance(agent, dict):
                required.extend(str(item) for item in agent.get("required_dependency_ids", []) if item)
        routing = raw.get("routing", {}) if isinstance(raw.get("routing"), dict) else {}
        for source in (
            raw.get("dependency_slots", []),
            raw.get("dependencies", []),
            routing.get("dependency_slots", []),
        ):
            values = source if isinstance(source, list) else [source]
            for item in values:
                if not isinstance(item, dict) or not bool(item.get("required", False)):
                    continue
                dependency_id = item.get("resource_id") or item.get("id")
                if dependency_id:
                    required.append(str(dependency_id))
        return list(dict.fromkeys(required))

    def _with_query_similarity(
        self,
        ref: TypedResourceRef,
        library: Sequence[Manifest],
        query_profile: Optional[QueryRetrievalProfile],
    ) -> TypedResourceRef:
        if query_profile is None:
            return ref
        manifest = next((item for item in library if item.id == ref.resource_id), None)
        if manifest is None:
            return ref
        ranked = self.retrieve_top_k(
            query_profile,
            [manifest],
            k=1,
            apply_hard_gates=False,
            apply_utility_rerank=False,
        )
        if not ranked:
            return ref
        return ref.model_copy(update={"similarity": float(ranked[0][1])})

    def _expand_agent_dependency_candidates(
        self,
        candidate_resources: Sequence[TypedResourceRef],
        library: List[Manifest],
        existing_selections: Sequence[DependencySelection],
        query_profile: Optional[QueryRetrievalProfile] = None,
    ) -> Tuple[List[DependencySelection], List[TypedResourceRef]]:
        """Expose Agent dependency hints without forcing the Plan Compiler to use them."""
        refs = list(candidate_resources)
        existing_ids = {ref.resource_id for ref in refs}
        existing_slot_ids = {selection.slot_id for selection in existing_selections}
        selections: List[DependencySelection] = []

        for agent_ref in [
            ref for ref in candidate_resources if ref.resource_type == ManifestType.AGENT
        ]:
            explicit_ids, slots = self._extract_dependencies(agent_ref.resource_id)
            for dependency_id in explicit_ids:
                if dependency_id in existing_ids:
                    refs = [
                        self._with_query_similarity(ref, library, query_profile)
                        if ref.resource_id == dependency_id
                        else ref
                        for ref in refs
                    ]
                    continue
                dependency_ref = self._ref_from_resource_id(dependency_id, library)
                if dependency_ref is None:
                    logger.warning(
                        "[Router] Unresolved Agent dependency hint: agent={} dependency={}",
                        agent_ref.resource_id,
                        dependency_id,
                    )
                    continue
                dependency_ref = self._with_query_similarity(
                    dependency_ref, library, query_profile
                )
                refs.append(
                    dependency_ref.model_copy(
                        update={
                            "candidate_origin": "agent_dependency_hint",
                            "injected_reason": f"agent:{agent_ref.resource_id}",
                        }
                    )
                )
                existing_ids.add(dependency_id)

            for slot in slots:
                if slot.slot_id in existing_slot_ids:
                    continue
                candidates = [
                    candidate.model_copy(
                        update={
                            "candidate_origin": "agent_dependency_hint",
                            "injected_reason": (
                                f"agent:{agent_ref.resource_id};slot:{slot.slot_id}"
                            ),
                        }
                    )
                    for candidate in self._retrieve_dependency_slot(
                        slot,
                        library,
                        query_profile=query_profile,
                    )
                ]
                selections.append(
                    DependencySelection(
                        slot_id=slot.slot_id,
                        required=slot.required,
                        selected=None,
                        candidates=candidates,
                    )
                )
                existing_slot_ids.add(slot.slot_id)
                for candidate in candidates:
                    if candidate.resource_id in existing_ids:
                        continue
                    refs.append(candidate)
                    existing_ids.add(candidate.resource_id)

        return selections, self._dedupe_refs(refs)

    def _expand_skill_dependency_candidates(
        self,
        candidate_resources: Sequence[TypedResourceRef],
        library: List[Manifest],
        existing_selections: Sequence[DependencySelection],
        query_profile: Optional[QueryRetrievalProfile] = None,
    ) -> Tuple[List[DependencySelection], List[TypedResourceRef]]:
        """Expose selected Skill dependency hints without forcing their use."""
        refs = list(candidate_resources)
        existing_ids = {ref.resource_id for ref in refs}
        existing_slot_ids = {
            selection.slot_id for selection in existing_selections
        }
        selections: List[DependencySelection] = []

        for skill_ref in [
            ref for ref in candidate_resources
            if ref.resource_type == ManifestType.SKILL
        ]:
            explicit_ids, slots = self._extract_dependencies(skill_ref.resource_id)
            for dependency_id in explicit_ids:
                if dependency_id in existing_ids:
                    refs = [
                        self._with_query_similarity(ref, library, query_profile)
                        if ref.resource_id == dependency_id
                        else ref
                        for ref in refs
                    ]
                    continue
                dependency_ref = self._ref_from_resource_id(dependency_id, library)
                if dependency_ref is None:
                    logger.warning(
                        "[Router] Unresolved Skill dependency hint: skill={} dependency={}",
                        skill_ref.resource_id,
                        dependency_id,
                    )
                    continue
                dependency_ref = self._with_query_similarity(
                    dependency_ref, library, query_profile
                )
                refs.append(
                    dependency_ref.model_copy(
                        update={
                            "candidate_origin": "skill_dependency_hint",
                            "injected_reason": f"skill:{skill_ref.resource_id}",
                        }
                    )
                )
                existing_ids.add(dependency_id)

            for slot in slots:
                if slot.slot_id in existing_slot_ids:
                    continue
                candidates = [
                    candidate.model_copy(
                        update={
                            "candidate_origin": "skill_dependency_hint",
                            "injected_reason": (
                                f"skill:{skill_ref.resource_id};slot:{slot.slot_id}"
                            ),
                        }
                    )
                    for candidate in self._retrieve_dependency_slot(
                        slot,
                        library,
                        query_profile=query_profile,
                    )
                ]
                selections.append(
                    DependencySelection(
                        slot_id=slot.slot_id,
                        required=slot.required,
                        selected=None,
                        candidates=candidates,
                    )
                )
                existing_slot_ids.add(slot.slot_id)
                for candidate in candidates:
                    if candidate.resource_id in existing_ids:
                        continue
                    refs.append(candidate)
                    existing_ids.add(candidate.resource_id)

        return selections, self._dedupe_refs(refs)

    def _retrieve_dependency_slot(
        self,
        slot: DependencySlot,
        library: List[Manifest],
        query_profile: Optional[QueryRetrievalProfile] = None,
    ) -> List[TypedResourceRef]:
        if query_profile is None:
            from .resource_loader import encode_query_profile

            query_vec = encode_query_profile(slot.description, use_hyde=True)
        else:
            # Candidate-trace evaluation must share the single audited query
            # profile across semantic retrieval and every dependency expansion.
            # This prevents hidden Provider calls and makes --no-hyde truthful.
            query_vec = query_profile
        allowed = set(slot.allowed_types)
        refs: List[TypedResourceRef] = []
        typed = self.retrieve_top_k_by_type(
            query_vec,
            library,
            quotas={item: slot.top_k_per_type for item in allowed},
        )
        for manifest_type in slot.allowed_types:
            for manifest, score in typed.get(manifest_type, []):
                refs.append(
                    self._ref_from_manifest(manifest, similarity=score).model_copy(
                        update={
                            "candidate_origin": "dependency_slot",
                            "injected_reason": f"slot:{slot.slot_id}",
                        }
                    )
                )
        return refs

    def _complete_intelligent_candidates(
        self,
        subtask: Subtask,
        candidate_resources: Sequence[TypedResourceRef],
        library: List[Manifest],
    ) -> List[TypedResourceRef]:
        """
        Add minimal low-cost Model candidates when the bundle needs an
        intelligent finalizer or contains an Agent that requires a runtime Model.
        """
        candidates = list(candidate_resources)
        if not self.enable_intelligent_resource_completion:
            return candidates
        candidates = self._inject_domain_specific_tools(subtask, candidates, library)
        if self.max_supplemental_models <= 0:
            return candidates

        has_model = any(ref.resource_type == ManifestType.MODEL for ref in candidates)
        has_agent = any(ref.resource_type == ManifestType.AGENT for ref in candidates)
        if has_model:
            return candidates

        if not has_agent and self._has_direct_final_output_candidate(candidates, subtask):
            return candidates

        existing_ids = {ref.resource_id for ref in candidates}
        supplemental = self._select_supplemental_models(library, existing_ids)
        if not supplemental:
            logger.warning(
                "[Router] No healthy supplemental Model candidates available for {}.",
                subtask.id,
            )
            return candidates

        logger.info(
            "[Router] Added supplemental Model candidates for {}{}: {}",
            subtask.id,
            " to support Agent execution" if has_agent else "",
            [ref.resource_id for ref in supplemental],
        )
        return self._dedupe_refs(candidates + supplemental)

    @staticmethod
    def _subtask_requires_side_artifact_execution(subtask: Subtask) -> bool:
        """Return true when the task contract asks for concrete side files."""
        contract = getattr(subtask, "output_contract", None)
        if contract is None:
            return False
        if hasattr(contract, "model_dump"):
            try:
                contract_data = contract.model_dump(mode="json")
            except Exception:
                contract_data = {}
        elif isinstance(contract, dict):
            contract_data = contract
        else:
            contract_data = {}
        produced_files = contract_data.get("produced_files") or []
        if not isinstance(produced_files, list):
            return False
        primary_type = str(getattr(getattr(subtask, "artifact_type", None), "value", subtask.artifact_type) or "").lower()
        required_types: List[str] = []
        for item in produced_files:
            required = bool(item.get("required", True)) if isinstance(item, dict) else True
            if not required:
                continue
            path_hint = item.get("path_hint") if isinstance(item, dict) else item
            if not path_hint:
                continue
            artifact_type = str((item.get("artifact_type") if isinstance(item, dict) else "") or "").lower()
            if not artifact_type:
                ext = os.path.splitext(str(path_hint))[1].lower()
                artifact_type = {
                    ".py": "code",
                    ".json": "json",
                    ".csv": "csv",
                    ".md": "markdown",
                    ".txt": "plaintext",
                }.get(ext, "")
            if artifact_type:
                required_types.append(artifact_type)
        if not required_types:
            return False
        has_cross_type = any(item_type != primary_type for item_type in required_types)
        return any(
            item_type in {"csv", "json", "plaintext"} and (has_cross_type or item_type != primary_type)
            for item_type in required_types
        )

    def _inject_domain_specific_tools(
        self,
        subtask: Subtask,
        candidate_resources: List[TypedResourceRef],
        library: List[Manifest],
    ) -> List[TypedResourceRef]:
        """Add deterministic high-precision tools when task text clearly names a domain."""
        text = (
            f"{subtask.description}\n{subtask.expected_output}\n{subtask.artifact_type.value}"
        ).lower()
        existing_ids = {ref.resource_id for ref in candidate_resources}
        inject_manifests: List[Tuple[Manifest, str]] = []

        code_exec_related = any(marker in text for marker in ("execute", "run", "script", '\u6267\u884c', '\u8fd0\u884c', '\u751f\u6210\u4ee3\u7801'))
        side_artifact_related = self._subtask_requires_side_artifact_execution(subtask)

        if code_exec_related or subtask.artifact_type == ArtifactType.CODE or side_artifact_related:
            executable_tools = [
                manifest
                for manifest in library
                if manifest.type == ManifestType.TOOL
                and "execute_script" in tool_allowed_operation_kinds(
                    self.resource_index.get(manifest.id, {})
                )
            ]
            if executable_tools:
                executable_tools.sort(key=lambda item: item.advantage_score, reverse=True)
                inject_manifests.append(
                    (executable_tools[0], "capability:generated_code_execution")
                )

        injected: List[TypedResourceRef] = []
        for manifest, reason in inject_manifests:
            resource_id = manifest.id
            if resource_id in existing_ids:
                continue
            injected.append(
                self._ref_from_manifest(manifest).model_copy(
                    update={
                        "candidate_origin": "domain_injection",
                        "injected_reason": reason,
                    }
                )
            )
            existing_ids.add(resource_id)

        if injected:
            logger.info(
                "[Router] Injected domain-specific tools for {}: {}",
                subtask.id,
                [ref.resource_id for ref in injected],
            )
        return self._dedupe_refs(injected + candidate_resources)

    def _has_direct_final_output_candidate(
        self,
        candidate_resources: Sequence[TypedResourceRef],
        subtask: Subtask,
    ) -> bool:
        """Return true when a non-intelligent candidate can directly satisfy the artifact."""
        for ref in candidate_resources:
            if ref.resource_type in {ManifestType.MODEL, ManifestType.AGENT}:
                return True
            if ref.resource_type not in {ManifestType.TOOL, ManifestType.RESOURCE}:
                continue
            raw = self.resource_index.get(ref.resource_id, {})
            if self._manifest_output_artifact(raw) == subtask.artifact_type.value:
                return True
        return False

    def _select_supplemental_models(
        self,
        library: List[Manifest],
        existing_ids: set[str],
    ) -> List[TypedResourceRef]:
        """Choose healthy low-cost model candidates without doing per-type full retrieval."""
        model_by_id = {
            manifest.id: manifest
            for manifest in library
            if manifest.type == ManifestType.MODEL and manifest.id not in existing_ids
        }

        ordered: List[Manifest] = []
        for model_id in self.supplemental_model_ids:
            manifest = self._manifest_by_id_or_model_id(model_id, library)
            if manifest is not None and manifest.id in existing_ids:
                manifest = None
            if manifest is not None and manifest not in ordered:
                ordered.append(manifest)

        if not ordered:
            avoid_ids = set()
            for model_id in (self.policy_model, self.baseline_model_id):
                manifest = self._manifest_by_id_or_model_id(model_id, library)
                avoid_ids.add(manifest.id if manifest else model_id)
            pool = [
                manifest for manifest in model_by_id.values()
                if manifest.id not in avoid_ids
            ]
            if not pool:
                pool = list(model_by_id.values())
            ordered = sorted(
                pool,
                key=lambda manifest: manifest.advantage_score,
                reverse=True,
            )

        refs: List[TypedResourceRef] = []
        for manifest in ordered[: self.max_supplemental_models]:
            refs.append(
                self._ref_from_manifest(manifest).model_copy(
                    update={
                        "candidate_origin": "capability_completion",
                        "injected_reason": "missing_intelligent_finalizer",
                    }
                )
            )
        return refs

    def _decide_bundle(
        self,
        subtask: Subtask,
        anchors: Sequence[TypedResourceRef],
        candidate_resources: Sequence[TypedResourceRef],
        dependency_selections: Sequence[DependencySelection],
        context_packet: Optional[Dict[str, Any]] = None,
        candidate_cards: Optional[Sequence[Mapping[str, Any]]] = None,
        strict_plan_protocol: bool = False,
        input_payload_guard: Optional[Callable[[Mapping[str, Any]], None]] = None,
        transport_retry_max: int = 0,
        allow_control_model_failover: bool = True,
        allow_deterministic_fallback: bool = True,
    ) -> BundleAdequacyDecision:
        if self._policy_transport is None:
            if strict_plan_protocol or not allow_deterministic_fallback:
                raise RuntimeError("plan_compiler_unavailable: no policy client is configured")
            return self._fallback_bundle_decision(
                anchors,
                candidate_resources,
                dependency_selections,
                subtask=subtask,
                reason="Deterministic fallback policy used because no Router policy client is configured.",
            )

        candidate_ids = {r.resource_id for r in candidate_resources}
        if candidate_cards is None:
            resolved_candidate_cards = [
                self._resource_card(r) for r in candidate_resources
            ]
        else:
            resolved_candidate_cards = [dict(card) for card in candidate_cards]
            resource_order = [item.resource_id for item in candidate_resources]
            card_order = [str(item.get("resource_id") or "") for item in resolved_candidate_cards]
            if card_order != resource_order:
                raise ValueError("plan_compiler_candidate_card_order_mismatch")
        payload = build_plan_compiler_payload(
            subtask=subtask,
            context_packet=context_packet,
            anchor_resources=[r.model_dump(mode="json") for r in anchors],
            candidate_cards=resolved_candidate_cards,
            dependency_slots=[
                selection.model_dump(mode="json")
                for selection in dependency_selections
            ],
        )
        self._last_policy_input_payload = payload
        self._last_policy_call_metadata = {
            "attempts": [],
            "attempt_count": 0,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "strict_plan_protocol": strict_plan_protocol,
            "input_payload": payload,
        }
        if input_payload_guard is not None:
            register_source = getattr(input_payload_guard, "register_source", None)
            if callable(register_source):
                register_source(
                    "static_framework:plan_compiler",
                    origin="static_framework",
                    material=plan_compiler_static_material(),
                )
                register_source(
                    "static_framework:plan_compiler_runtime",
                    origin="static_framework",
                    material={"model_id": self.policy_model},
                    parent_source_ids=("static_framework:plan_compiler",),
                )
                register_source(
                    "candidate_bundle:plan_compiler_cards",
                    origin="candidate_bundle",
                    material=payload["candidate_bundle"],
                    parent_source_ids=("candidate_bundle",),
                )
            input_payload_guard(payload)
        payload_provenance_hash = str(
            getattr(input_payload_guard, "provenance_hash", "") or ""
        )
        def response_mode_for(model_id: str) -> str:
            configured_modes = getattr(self, "policy_response_modes", None)
            if configured_modes is None and strict_plan_protocol:
                return "native_strict_schema"
            selected_mode = dict(configured_modes or {}).get(model_id)
            if selected_mode is not None:
                return selected_mode
            if GLOBAL_CAPABILITY_REGISTRY.allows(model_id, "structured_outputs_ok"):
                return "json_schema"
            if GLOBAL_CAPABILITY_REGISTRY.allows(model_id, "json_mode_ok"):
                return "json_object"
            return "prompt_json"

        def call_policy(model_id: str, mode: str):
            call_kwargs = build_plan_compiler_call_kwargs(
                payload,
                model_id=model_id,
                response_mode=mode,
                portable_schema=bool(getattr(self, "policy_response_modes", None)),
            )
            request_hash = _policy_request_hash(call_kwargs)
            last_error: Optional[Exception] = None
            retry_limit = max(0, int(transport_retry_max))
            if strict_plan_protocol:
                retry_limit = min(PLAN_COMPILER_TRANSPORT_RETRY_MAX, retry_limit)
            cost_ledger = getattr(self, "cost_ledger", None)
            accounting_context = (
                cost_ledger.new_operation(
                    stage="plan_compiler",
                    subtask_id=subtask.id,
                    subtask_revision=0,
                )
                if cost_ledger is not None
                else None
            )
            for transport_attempt in range(1, retry_limit + 2):
                try:
                    if input_payload_guard is not None:
                        input_payload_guard(deepcopy(call_kwargs))
                    if strict_plan_protocol:
                        # Fixed-pass transport retry must be the exact same API
                        # request.  Compatibility helpers may delete parameters
                        # or issue an internal second request, so formal runs use
                        # the provider client directly.
                        result = self._policy_transport.send(
                            ledger=cost_ledger,
                            context=accounting_context,
                            **deepcopy(call_kwargs),
                        )
                    else:
                        result = create_chat_completion_with_compat(
                            self._policy_transport,
                            registry=GLOBAL_CAPABILITY_REGISTRY,
                            cost_ledger=cost_ledger,
                            accounting_context=accounting_context,
                            **deepcopy(call_kwargs),
                        )
                    transport_record = {
                        "model_id": model_id,
                        "response_format_mode": mode,
                        "transport_attempt": transport_attempt,
                        "request_hash": request_hash,
                        "provenance_hash": payload_provenance_hash,
                        "status": "success",
                        "response_received": True,
                        "retryable": False,
                        "responsibility": None,
                    }
                    transport_attempts.append(transport_record)
                    self._last_policy_call_metadata.update(
                        {
                            "request_hash": request_hash,
                            "transport_attempt": transport_attempt,
                            "response_received": True,
                            "retryable": False,
                            "responsibility": None,
                            "transport_attempts": list(transport_attempts),
                            "model_accounting_reference": getattr(
                                result,
                                "accounting_reference",
                                None,
                            ),
                            "request_hashes": list(
                                dict.fromkeys(
                                    item["request_hash"] for item in transport_attempts
                                )
                            ),
                            "provenance_hashes": [
                                item["provenance_hash"] for item in transport_attempts
                            ],
                        }
                    )
                    return result
                except Exception as exc:
                    if isinstance(exc, (ModelAccountingError, ModelTransportError)):
                        raise
                    last_error = exc
                    retryable, structured_type, response_received, responsibility = (
                        _retryable_policy_transport(exc)
                    )
                    will_retry = retryable and transport_attempt <= retry_limit
                    transport_record = {
                        "model_id": model_id,
                        "response_format_mode": mode,
                        "transport_attempt": transport_attempt,
                        "request_hash": request_hash,
                        "provenance_hash": payload_provenance_hash,
                        "status": "failed",
                        "failure_type": structured_type,
                        "response_received": response_received,
                        "retryable": retryable,
                        "responsibility": responsibility,
                        "will_retry": will_retry,
                        "error_type": type(exc).__name__,
                    }
                    transport_attempts.append(transport_record)
                    self._last_policy_call_metadata.update(
                        {
                            "request_hash": request_hash,
                            "transport_attempt": transport_attempt,
                            "response_received": response_received,
                            "retryable": retryable,
                            "responsibility": responsibility,
                            "transport_attempts": list(transport_attempts),
                            "request_hashes": list(
                                dict.fromkeys(
                                    item["request_hash"] for item in transport_attempts
                                )
                            ),
                            "provenance_hashes": [
                                item["provenance_hash"] for item in transport_attempts
                            ],
                        }
                    )
                    if not will_retry:
                        raise
            raise last_error or RuntimeError("plan_compiler_transport_exhausted")

        response = None
        policy_attempts: List[Dict[str, Any]] = []
        transport_attempts: List[Dict[str, Any]] = []
        last_policy_error: Optional[Exception] = None
        policy_models = (
            list(self.policy_model_chain)
            if allow_control_model_failover
            else list(self.policy_model_chain[:1])
        )
        if strict_plan_protocol:
            policy_models = list(self.policy_model_chain[:1])
        for model_index, model_id in enumerate(policy_models):
            response_mode = response_mode_for(model_id)
            if strict_plan_protocol and response_mode not in {
                "native_strict_schema",
                "json_object_local_validator",
            }:
                raise ValueError("router_policy_response_mode_not_preverified")
            try:
                response = call_policy(model_id, response_mode)
                if not strict_plan_protocol and response_mode in {
                    "json_schema",
                    "native_strict_schema",
                }:
                    GLOBAL_CAPABILITY_REGISTRY.record_success(model_id, "structured_outputs_ok")
                elif not strict_plan_protocol and response_mode in {
                    "json_object",
                    "json_object_local_validator",
                }:
                    GLOBAL_CAPABILITY_REGISTRY.record_success(model_id, "json_mode_ok")
                policy_attempts.append(
                    {
                        "model_id": model_id,
                        "status": "success",
                        "response_format_mode": response_mode,
                    }
                )
                self.policy_model = model_id
                break
            except Exception as exc:
                if isinstance(exc, (ModelAccountingError, ModelTransportError)):
                    raise
                message = str(exc)
                last_policy_error = exc
                if (
                    not strict_plan_protocol
                    and response_mode == "json_schema"
                    and is_response_format_unsupported_error(exc)
                ):
                    GLOBAL_CAPABILITY_REGISTRY.record_failure(
                        model_id,
                        "structured_outputs_ok",
                        "capability_unsupported",
                        message,
                    )
                    logger.warning(
                        "[Router] Policy structured outputs rejected for {}; retrying with JSON object mode.",
                        model_id,
                    )
                    try:
                        response = call_policy(model_id, "json_object")
                        GLOBAL_CAPABILITY_REGISTRY.record_success(model_id, "json_mode_ok")
                        policy_attempts.append(
                            {
                                "model_id": model_id,
                                "status": "success",
                                "response_format_mode": "json_object",
                                "schema_downgrade": True,
                            }
                        )
                        self.policy_model = model_id
                        break
                    except Exception as retry_exc:
                        if is_response_format_unsupported_error(retry_exc):
                            GLOBAL_CAPABILITY_REGISTRY.record_failure(
                                model_id,
                                "json_mode_ok",
                                "capability_unsupported",
                                str(retry_exc),
                            )
                            logger.warning(
                                "[Router] Policy JSON object mode rejected for {}; retrying prompt-only JSON.",
                                model_id,
                            )
                            try:
                                response = call_policy(model_id, "prompt_json")
                                policy_attempts.append(
                                    {
                                        "model_id": model_id,
                                        "status": "success",
                                        "response_format_mode": "prompt_json",
                                        "schema_downgrade": True,
                                    }
                                )
                                self.policy_model = model_id
                                break
                            except Exception as prompt_exc:
                                last_policy_error = prompt_exc
                        else:
                            last_policy_error = retry_exc
                elif (
                    not strict_plan_protocol
                    and response_mode == "json_object"
                    and is_response_format_unsupported_error(exc)
                ):
                    GLOBAL_CAPABILITY_REGISTRY.record_failure(
                        model_id,
                        "json_mode_ok",
                        "capability_unsupported",
                        message,
                    )
                    logger.warning(
                        "[Router] Policy JSON object mode rejected for {}; retrying prompt-only JSON.",
                        model_id,
                    )
                    try:
                        response = call_policy(model_id, "prompt_json")
                        policy_attempts.append(
                            {
                                "model_id": model_id,
                                "status": "success",
                                "response_format_mode": "prompt_json",
                                "schema_downgrade": True,
                            }
                        )
                        self.policy_model = model_id
                        break
                    except Exception as prompt_exc:
                        last_policy_error = prompt_exc

                failure_type, provider_message = _classify_router_provider_exception(last_policy_error or exc)
                if not strict_plan_protocol:
                    GLOBAL_CAPABILITY_REGISTRY.record_error(
                        model_id, failure_type, provider_message
                    )
                policy_attempts.append(
                    {
                        "model_id": model_id,
                        "status": "failed",
                        "failure_type": failure_type,
                        "reason": provider_message,
                        "response_format_mode": response_mode,
                    }
                )
                self._last_policy_call_metadata.update(
                    {
                        "attempts": list(policy_attempts),
                        "attempt_count": len(policy_attempts),
                        "transport_attempts": list(transport_attempts),
                        "transport_attempt_count": len(transport_attempts),
                        "request_hashes": list(
                            dict.fromkeys(
                                item["request_hash"] for item in transport_attempts
                            )
                        ),
                    }
                )
                if is_control_model_failover_failure(failure_type) and model_index >= len(policy_models) - 1:
                    if strict_plan_protocol or not allow_deterministic_fallback:
                        raise last_policy_error or exc
                    return self._fallback_bundle_decision(
                        anchors,
                        candidate_resources,
                        dependency_selections,
                        subtask=subtask,
                        reason=(
                            "Deterministic fallback policy used after control_model_chain_exhausted "
                            f"for Router policy: {policy_attempts}"
                        ),
                    )
                if not is_control_model_failover_failure(failure_type):
                    raise last_policy_error or exc
                logger.warning(
                    "[Router] Policy model {} failed with {}; trying next control model.",
                    model_id,
                    failure_type,
                )
        if response is None:
            raise last_policy_error or RuntimeError("control_model_chain_exhausted")
        usage = getattr(response, "usage", None)
        self._last_policy_call_metadata = {
            "attempts": policy_attempts,
            "attempt_count": len(policy_attempts),
            "model_accounting_reference": getattr(
                response,
                "accounting_reference",
                None,
            ),
            "transport_attempts": transport_attempts,
            "transport_attempt_count": len(transport_attempts),
            "request_hashes": list(
                dict.fromkeys(item["request_hash"] for item in transport_attempts)
            ),
            "request_hash": transport_attempts[-1]["request_hash"] if transport_attempts else None,
            "provenance_hash": (
                transport_attempts[-1].get("provenance_hash")
                if transport_attempts
                else payload_provenance_hash
            ),
            "provenance_hashes": [
                item.get("provenance_hash", "") for item in transport_attempts
            ],
            "transport_attempt": transport_attempts[-1]["transport_attempt"] if transport_attempts else 0,
            "response_received": bool(transport_attempts and transport_attempts[-1]["response_received"]),
            "retryable": bool(transport_attempts and transport_attempts[-1]["retryable"]),
            "responsibility": transport_attempts[-1].get("responsibility") if transport_attempts else None,
            "usage": {
                "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
                "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
                "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
            },
            "strict_plan_protocol": strict_plan_protocol,
        }
        raw = response.choices[0].message.content or "{}"
        self._last_policy_call_metadata["raw_response"] = raw
        self._last_policy_call_metadata["input_payload"] = payload
        try:
            if strict_plan_protocol:
                raw_payload = validate_structured_response_content(
                    raw,
                    requirement=system_role_requirement("router_policy"),
                    mode=response_mode,
                )
            else:
                raw_payload = self._load_policy_payload(raw)
        except Exception as exc:
            if strict_plan_protocol or not allow_deterministic_fallback:
                raise ValueError(
                    f"policy_invalid_output: invalid Plan Compiler JSON: {exc}"
                ) from exc
            logger.warning(
                "[Router] Policy returned invalid JSON for {}; using deterministic plan fallback: {}",
                subtask.id,
                exc,
            )
            return self._fallback_bundle_decision(
                anchors,
                candidate_resources,
                dependency_selections,
                subtask=subtask,
                reason=(
                    f"Deterministic fallback policy used after policy_invalid_output: {exc}; "
                    f"control_policy_attempts={policy_attempts}"
                ),
            )
        candidate_map = {r.resource_id: r for r in candidate_resources}
        normalized_payload = self._normalize_policy_payload(
            raw_payload,
            candidate_map,
            subtask,
            strict_plan_protocol=strict_plan_protocol,
        )
        try:
            decision = BundleAdequacyDecision.model_validate(
                normalized_payload,
                context={"strict_plan_protocol": strict_plan_protocol},
            )
        except Exception as exc:
            if strict_plan_protocol:
                raise ValueError(
                    f"plan_protocol_failure: invalid Plan Compiler schema: {exc}"
                ) from exc
            raise

        if strict_plan_protocol:
            _assert_strict_payload_preserved(
                normalized_payload,
                decision.model_dump(mode="json"),
            )

        if strict_plan_protocol:
            self._require_protocol_fields(
                decision,
                {"selected_resources", "expected_execution_mode", "application_plan"},
                "Plan Compiler decision",
            )

        selected: List[TypedResourceRef] = []
        selected_refs = list(decision.selected_resources)
        if (
            not strict_plan_protocol
            and not selected_refs
            and decision.application_plan is not None
        ):
            selected_refs = [
                candidate_map[resource_id]
                for resource_id in decision.application_plan.selected_resource_ids
                if resource_id in candidate_map
            ]

        for ref in selected_refs:
            if ref.resource_id not in candidate_ids:
                raise ValueError(f"policy_hallucinated_resource: {ref.resource_id}")
            candidate_ref = candidate_map[ref.resource_id]
            selected.append(
                candidate_ref.model_copy(
                    update={"base_model": ref.base_model or candidate_ref.base_model}
                )
            )

        application_plan = decision.application_plan
        if strict_plan_protocol and decision.is_sufficient and application_plan is None:
            raise ValueError(
                "plan_protocol_failure: sufficient decision requires application_plan"
            )
        if application_plan is None and selected:
            if strict_plan_protocol:
                raise ValueError(
                    "plan_protocol_failure: selected resources require an explicit application_plan"
                )
            application_plan = self._default_application_plan(
                selected,
                decision.expected_execution_mode,
                decision.reason,
            )
        if application_plan is not None:
            application_plan = self._validate_application_plan(
                application_plan,
                candidate_ids,
                subtask=subtask,
                strict_plan_protocol=strict_plan_protocol,
            )
            if strict_plan_protocol:
                selected_ids = [ref.resource_id for ref in selected]
                if len(selected_ids) != len(set(selected_ids)):
                    raise ValueError(
                        "plan_protocol_failure: duplicate selected_resources"
                    )
                if selected_ids != list(application_plan.selected_resource_ids):
                    raise ValueError(
                        "plan_protocol_failure: selected_resources and "
                        "application_plan.selected_resource_ids must match exactly"
                    )
                if decision.expected_execution_mode != application_plan.expected_execution_mode:
                    raise ValueError(
                        "plan_protocol_failure: decision and application_plan "
                        "expected_execution_mode mismatch"
                    )
            else:
                selected = self._complete_selected_refs_from_plan(
                    selected,
                    application_plan,
                    candidate_map,
                )
            selected = self._apply_agent_model_bindings(
                selected,
                application_plan,
                candidate_map,
            )

        expected_mode = (
            application_plan.expected_execution_mode
            if application_plan is not None
            else decision.expected_execution_mode
        )
        decision_reason = decision.reason
        if policy_attempts:
            policy_note = f"control_policy_attempts={policy_attempts}"
            decision_reason = f"{decision_reason}; {policy_note}" if decision_reason else policy_note
        return decision.model_copy(
            update={
                "selected_resources": selected,
                "expected_execution_mode": expected_mode,
                "application_plan": application_plan,
                "reason": decision_reason,
            }
        )

    def _fallback_bundle_decision(
        self,
        anchors: Sequence[TypedResourceRef],
        candidate_resources: Sequence[TypedResourceRef],
        dependency_selections: Sequence[DependencySelection],
        subtask: Optional[Subtask] = None,
        reason: Optional[str] = None,
    ) -> BundleAdequacyDecision:
        selected = self._fallback_selected_resources(
            anchors,
            candidate_resources,
            dependency_selections,
            subtask,
        )
        fallback_reason = reason or "Deterministic fallback policy used because no Router policy client is configured."
        expected_mode = self._infer_execution_mode(selected)
        application_plan = (
            self._fallback_application_plan_for_subtask(
                selected,
                candidate_resources,
                subtask,
                expected_mode,
                fallback_reason,
            )
            if subtask is not None
            else self._default_application_plan(selected, expected_mode, fallback_reason)
        )
        candidate_map = {ref.resource_id: ref for ref in candidate_resources}
        selected = self._complete_selected_refs_from_plan(
            selected,
            application_plan,
            candidate_map,
        )
        selected = self._apply_agent_model_bindings(
            selected,
            application_plan,
            candidate_map,
        )

        return BundleAdequacyDecision(
            is_sufficient=bool(selected),
            selected_resources=selected,
            expected_execution_mode=expected_mode,
            application_plan=application_plan,
            reason=fallback_reason,
        )

    def _fallback_selected_resources(
        self,
        anchors: Sequence[TypedResourceRef],
        candidate_resources: Sequence[TypedResourceRef],
        dependency_selections: Sequence[DependencySelection],
        subtask: Optional[Subtask],
    ) -> List[TypedResourceRef]:
        """Choose a minimal executable set when the policy model emits unusable JSON."""
        # The fallback is still a Plan Compiler and must obey the same compact
        # candidate boundary as the model policy.  Dependency selections retain
        # pre-compression alternatives for audit, but selecting one of those
        # hidden alternatives produces a plan whose resource is unavailable to
        # downstream preflight.  Use only the explicit compact candidates.
        candidates = self._dedupe_refs(list(candidate_resources))
        selected: List[TypedResourceRef] = []

        def add(ref: Optional[TypedResourceRef]) -> None:
            if ref is None:
                return
            if ref.resource_id not in {item.resource_id for item in selected}:
                selected.append(ref)

        artifact_type = ""
        if subtask is not None:
            artifact_type = subtask.artifact_type.value
        is_test_task = self._is_test_artifact_task(subtask)
        requests_pytest_run = self._subtask_requests_pytest_run(subtask)
        requests_execution = self._subtask_requests_code_execution(subtask)

        intelligent_ref = next(
            (r for r in candidates if r.resource_type in {ManifestType.MODEL, ManifestType.AGENT}),
            None,
        )
        runtime_model_ref = next(
            (r for r in candidates if r.resource_type == ManifestType.MODEL),
            None,
        )
        python_runner = self._first_tool_with_capability(candidates, "execute_script")
        pytest_runner = self._first_tool_with_capability(candidates, "run_tests")
        primary_tool = next((r for r in candidates if r.resource_type == ManifestType.TOOL), None)
        runtime_tool = next(
            (r for r in candidates if subtask is not None and self._runtime_intent_match(subtask, r)),
            None,
        )

        if artifact_type in {"code", "json", "csv", "markdown", "plaintext"}:
            add(runtime_tool)
            add(intelligent_ref)
            if (
                intelligent_ref is not None
                and intelligent_ref.resource_type == ManifestType.AGENT
            ):
                add(runtime_model_ref)
            if requests_pytest_run:
                add(pytest_runner)
            elif requests_execution:
                add(python_runner)
        if not selected:
            add(primary_tool)
            add(intelligent_ref)
            if (
                intelligent_ref is not None
                and intelligent_ref.resource_type == ManifestType.AGENT
            ):
                add(runtime_model_ref)
        if not selected and candidates:
            add(candidates[0])
        return selected

    @staticmethod
    def _subtask_text(subtask: Optional[Subtask]) -> str:
        if subtask is None:
            return ""
        from .resource_compatibility import current_node_contract_text

        return f"{subtask.id}\n{subtask.role}\n{current_node_contract_text(subtask)}".lower()

    def _is_test_artifact_task(self, subtask: Optional[Subtask]) -> bool:
        """Return true only when the subtask is expected to produce test code."""
        if subtask is None:
            return False
        artifact_type = subtask.artifact_type.value if subtask.artifact_type else ""
        if artifact_type != ArtifactType.CODE.value:
            return False
        text = self._subtask_text(subtask)
        if any(token in text for token in ("read", "inspect", "analyze", "diagnose", "audit", '\u8bfb\u53d6', '\u5206\u6790', '\u8bca\u65ad')):
            if not re.search(r"\b(write|create|add|update|generate|fix)\b.{0,60}\b(pytest|tests?|test cases?)\b", text):
                return False
        if re.search(r"\b(write|create|add|update|generate|fix)\b.{0,60}\b(pytest|tests?|test cases?)\b", text):
            return True
        if re.search(r"\b(pytest|tests?)\b.{0,60}\b(file|code|artifact|case|cases)\b", text):
            return True
        return any(
            token in text
            for token in (
                "test code",
                "pytest file",
                "test file",
                "test_http",
                '\u8865\u5145\u6d4b\u8bd5',
                '\u4fee\u6b63\u6d4b\u8bd5',
                '\u751f\u6210\u6d4b\u8bd5',
                '\u7f16\u5199\u6d4b\u8bd5',
                '\u6d4b\u8bd5\u4ee3\u7801',
                '\u6d4b\u8bd5\u7528\u4f8b',
            )
        )

    def _subtask_requests_code_execution(self, subtask: Optional[Subtask]) -> bool:
        if subtask is None:
            return False
        if subtask.artifact_type != ArtifactType.CODE:
            return False
        text = self._subtask_text(subtask)
        if self._is_test_artifact_task(subtask):
            return False
        return bool(re.search(r"\b(execute|run)\b", text) or any(token in text for token in ('\u8fd0\u884c', '\u6267\u884c')))

    def _subtask_requests_pytest_run(self, subtask: Optional[Subtask]) -> bool:
        if subtask is None:
            return False
        text = self._subtask_text(subtask)
        if self._is_test_artifact_task(subtask):
            return False
        return bool(
            "run_tests" in text
            or re.search(r"\b(run|execute|verify)\b.{0,80}\b(pytest|tests?)\b", text)
        )

    def _fallback_application_plan_for_subtask(
        self,
        selected: Sequence[TypedResourceRef],
        candidate_resources: Sequence[TypedResourceRef],
        subtask: Optional[Subtask],
        expected_mode: ExecutionMode,
        reason: Optional[str],
    ) -> ResourceApplicationPlan:
        """Build a conservative model-first plan that can still execute validators."""
        if subtask is None:
            return self._default_application_plan(selected, expected_mode, reason)

        selected_by_id = {ref.resource_id: ref for ref in selected}
        candidate_by_id = {ref.resource_id: ref for ref in candidate_resources}
        text = self._subtask_text(subtask)
        is_test_task = self._is_test_artifact_task(subtask)
        requests_pytest_run = self._subtask_requests_pytest_run(subtask)
        requests_execution = self._subtask_requests_code_execution(subtask)
        artifact_type = subtask.artifact_type
        model_ref = next(
            (
                ref for ref in selected
                if ref.resource_type in {ManifestType.MODEL, ManifestType.AGENT}
            ),
            None,
        )
        if model_ref is None:
            model_ref = next(
                (
                    ref for ref in candidate_resources
                    if ref.resource_type in {ManifestType.MODEL, ManifestType.AGENT}
                ),
                None,
            )
            if model_ref is not None:
                selected_by_id[model_ref.resource_id] = model_ref
        runtime_model_ref = next(
            (
                ref
                for ref in selected_by_id.values()
                if ref.resource_type == ManifestType.MODEL
            ),
            None,
        ) or next(
            (
                ref
                for ref in candidate_resources
                if ref.resource_type == ManifestType.MODEL
            ),
            None,
        )
        if model_ref is not None and model_ref.resource_type == ManifestType.AGENT:
            if runtime_model_ref is None:
                return ResourceApplicationPlan(
                    is_sufficient=False,
                    selected_resource_ids=[],
                    resource_usage=[],
                    steps=[],
                    final_output_from=None,
                    expected_execution_mode=expected_mode,
                    reason="Deterministic fallback cannot execute the selected Agent without a Model candidate.",
                )
            selected_by_id[runtime_model_ref.resource_id] = runtime_model_ref
        pytest_ref = self._first_tool_with_capability(
            list(selected_by_id.values()) + list(candidate_by_id.values()),
            "run_tests",
        )
        python_runner_ref = self._first_tool_with_capability(
            list(selected_by_id.values()) + list(candidate_by_id.values()),
            "execute_script",
        )
        runtime_ref = next(
            (
                ref for ref in list(selected) + list(candidate_resources)
                if self._runtime_intent_match(subtask, ref)
            ),
            None,
        )
        if runtime_ref is not None:
            selected_by_id[runtime_ref.resource_id] = runtime_ref

        steps: List[ResourceApplicationStep] = []
        final_output_from: Optional[str] = None
        if runtime_ref is not None:
            raw_runtime = self.resource_index.get(runtime_ref.resource_id, {})
            declared_artifact = self._manifest_output_artifact(raw_runtime) or "json"
            if str(declared_artifact).lower() in {"text", "plain_text"}:
                declared_artifact = ArtifactType.PLAINTEXT.value
            try:
                tool_artifact = ArtifactType(declared_artifact)
            except ValueError:
                tool_artifact = ArtifactType.JSON
            runtime_bindings: Dict[str, Any] = {}
            path_candidates = [
                item.strip("'\"`.,;:()[]{}")
                for item in re.findall(r"(?:[A-Za-z]:)?[A-Za-z0-9_.:/\\-]+", text)
                if "/" in item or "\\" in item
            ]
            for contract in self._manifest_input_contracts(raw_runtime):
                name = str(contract.get("name") or "")
                kind = str(contract.get("kind") or "").lower()
                if name in {"pattern", "query", "search_pattern"}:
                    quoted = re.findall(r"['\"]([^'\"]+)['\"]", text)
                    if quoted:
                        runtime_bindings[name] = quoted[-1]
                        continue
                if not name or not path_candidates:
                    continue
                matching = [
                    path for path in path_candidates
                    if kind not in {"file_path", "directory_path"}
                    or (kind == "file_path" and "." in os.path.basename(path))
                    or (kind == "directory_path" and "." not in os.path.basename(path))
                ]
                if matching:
                    # Prefer the path whose basename is explicitly named in the
                    # task, then prefer the most specific (longest) path.  A
                    # filesystem task commonly mentions both its root directory
                    # and a target file; choosing the first textual path makes
                    # file reads nondeterministically bind to the directory.
                    def path_score(path: str) -> tuple[int, int, int]:
                        normalized = path.lower().replace("\\", "/")
                        basename = os.path.basename(normalized)
                        explicit_name = int(
                            bool(basename)
                            and re.search(
                                rf"(?<![a-z0-9_]){re.escape(basename)}(?![a-z0-9_])",
                                text,
                            ) is not None
                        )
                        kind_score = (
                            1
                            if kind == "file_path" and "." in basename
                            else 1
                            if kind == "directory_path" and "." not in basename
                            else 0
                        )
                        return explicit_name, kind_score, len(normalized)

                    runtime_bindings[name] = max(matching, key=path_score)
            runtime_output_key = f"{subtask.id}_runtime_tool_result"
            steps.append(
                ResourceApplicationStep(
                    step_id="run_runtime_tool",
                    step_type="run_tool",
                    resource_id=runtime_ref.resource_id,
                    operation_kind=self._safe_tool_operation_kind(raw_runtime),
                    intent=(
                        f"Execute the concrete runtime tool required by this subtask: "
                        f"{subtask.description}"
                    ),
                    input_bindings=runtime_bindings,
                    output_key=runtime_output_key,
                    expected_output_contract=ResourceOutputContract(
                        artifact_type=tool_artifact,
                        description="Concrete runtime Tool result.",
                    ),
                )
            )
            final_output_from = runtime_output_key
            # A structured Tool result cannot itself satisfy a prose/report
            # contract.  Preserve the real Tool execution, then compile the
            # result through the selected model as an explicit final bridge.
            text_bridge = tool_artifact == ArtifactType.PLAINTEXT and artifact_type in {
                ArtifactType.PLAINTEXT,
                ArtifactType.MARKDOWN,
            }
            if tool_artifact != artifact_type and not text_bridge and model_ref is not None:
                selected_by_id[model_ref.resource_id] = model_ref
                synthesis_bindings: Dict[str, Any] = {
                    "runtime_tool_result": {
                        "from_step": "run_runtime_tool",
                        "output_key": runtime_output_key,
                    }
                }
                if (
                    model_ref.resource_type == ManifestType.AGENT
                    and runtime_model_ref is not None
                ):
                    synthesis_bindings["base_model"] = {
                        "resource_id": runtime_model_ref.resource_id
                    }
                steps.append(
                    ResourceApplicationStep(
                        step_id="synthesize_final",
                        step_type="synthesize_final",
                        resource_id=model_ref.resource_id,
                        operation_kind="synthesize_final",
                        intent=(
                            "Synthesize the final requested report from the concrete "
                            "runtime Tool result; do not invent or replace the Tool evidence."
                        ),
                        input_bindings=synthesis_bindings,
                        output_key="final_synthesis",
                        expected_output_contract=ResourceOutputContract(
                            artifact_type=artifact_type,
                            description="Final report grounded in the runtime Tool result.",
                        ),
                    )
                )
                final_output_from = "final_synthesis"
        elif requests_pytest_run and pytest_ref is not None:
            selected_by_id[pytest_ref.resource_id] = pytest_ref
            steps.append(
                ResourceApplicationStep(
                    step_id="run_pytest",
                    step_type="validate_artifact",
                    resource_id=pytest_ref.resource_id,
                    operation_kind="run_tests",
                    intent="Run current-run pytest artifacts for this test execution node.",
                    input_bindings={},
                    output_key="pytest_result",
                    expected_output_contract=ResourceOutputContract(
                        artifact_type=ArtifactType.JSON,
                        description="Pytest execution result.",
                    ),
                )
            )
            final_output_from = "pytest_result"
        elif model_ref is not None:
            output_key = "test_code" if is_test_task else "final_artifact"
            agent_binding = (
                {"base_model": {"resource_id": runtime_model_ref.resource_id}}
                if model_ref.resource_type == ManifestType.AGENT
                and runtime_model_ref is not None
                else {}
            )
            steps.append(
                ResourceApplicationStep(
                    step_id="generate_artifact",
                    step_type=(
                        "call_agent"
                        if model_ref.resource_type == ManifestType.AGENT
                        else "call_model"
                    ),
                    resource_id=model_ref.resource_id,
                    operation_kind="produce_artifact",
                    intent=(
                        "Generate the subtask's requested artifact from the current task context, "
                        "upstream artifact profiles, and output contract."
                    ),
                    input_bindings=agent_binding,
                    output_key=output_key,
                    expected_output_contract=ResourceOutputContract(
                        artifact_type=artifact_type,
                        description="Final artifact aligned with the Planner output contract.",
                    ),
                )
            )
            final_output_from = output_key

        if (
            python_runner_ref is not None
            and final_output_from
            and artifact_type == ArtifactType.CODE
            and requests_execution
        ):
            selected_by_id[python_runner_ref.resource_id] = python_runner_ref
            steps.append(
                ResourceApplicationStep(
                    step_id="execute_generated_code",
                    step_type="execute_generated_code",
                    resource_id=python_runner_ref.resource_id,
                    operation_kind="execute_script",
                    intent="Execute the generated Python artifact when the subtask explicitly requires execution.",
                    input_bindings={
                        "script_path": {
                            "from_step": "generate_artifact",
                            "output_key": final_output_from,
                        },
                        "cwd": ".",
                    },
                    output_key="execution_result",
                    expected_output_contract=ResourceOutputContract(
                        artifact_type=ArtifactType.JSON,
                        description="Generated code execution result.",
                    ),
                )
            )

        if not steps:
            return self._default_application_plan(list(selected_by_id.values()), expected_mode, reason)

        selected_ids = list(
            dict.fromkeys(
                [step.resource_id for step in steps]
                + (
                    [runtime_model_ref.resource_id]
                    if (
                        model_ref is not None
                        and model_ref.resource_type == ManifestType.AGENT
                        and runtime_model_ref is not None
                    )
                    else []
                )
            )
        )
        step_ids_by_resource: Dict[str, List[str]] = {}
        for step in steps:
            step_ids_by_resource.setdefault(step.resource_id, []).append(step.step_id)
        return ResourceApplicationPlan(
            is_sufficient=True,
            selected_resource_ids=selected_ids,
            resource_usage=[
                ResourceUsageDecision(
                    resource_id=resource_id,
                    decision="use",
                    use_as=(
                        "agent_base_model"
                        if (
                            runtime_model_ref is not None
                            and resource_id == runtime_model_ref.resource_id
                            and model_ref is not None
                            and model_ref.resource_type == ManifestType.AGENT
                        )
                        else "executable_step"
                    ),
                    attached_to_steps=(
                        step_ids_by_resource.get(model_ref.resource_id, [])
                        if (
                            runtime_model_ref is not None
                            and resource_id == runtime_model_ref.resource_id
                            and model_ref is not None
                            and model_ref.resource_type == ManifestType.AGENT
                        )
                        else step_ids_by_resource.get(resource_id, [])
                    ),
                    reason="Derived by deterministic Plan Compiler fallback.",
                )
                for resource_id in selected_ids
            ],
            steps=steps,
            final_output_from=final_output_from,
            expected_execution_mode=expected_mode,
            reason=reason,
        )

    def _load_policy_payload(self, raw: str) -> Dict[str, Any]:
        return _extract_unique_json_object(
            raw,
            expected_keys=("is_sufficient", "selected_resources", "application_plan"),
        )

    def _normalize_policy_artifact_type(self, value: Any, subtask: Subtask) -> Any:
        if value is None:
            return None
        normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
        if normalized in {"text", "plain_text"}:
            return "plaintext"
        if normalized in {"structured_analysis", "analysis", "report", "document", "doc"}:
            return subtask.artifact_type.value if subtask.artifact_type else "markdown"
        if normalized in {"python", "py", "source_code", "script"}:
            return "code"
        if normalized in {"json_object", "json_schema"}:
            return "json"
        if normalized == "csv_file":
            return "csv"
        return normalized

    def _normalize_schema_hint(self, value: Any) -> Any:
        if value is None or isinstance(value, str):
            return value
        if isinstance(value, (list, tuple)):
            return ", ".join(str(item) for item in value)
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        return str(value)

    def _is_policy_context_reference(self, resource_id: Any) -> bool:
        """Detect policy strings that refer to task context rather than resource IDs."""
        text = str(resource_id or "").strip()
        if not text:
            return False
        lowered = text.replace("\\", "/").lower()
        if lowered in {
            "resolved_local_file",
            "resolved_local_files",
            "local_file",
            "input_file",
            "input_files",
            "current_subtask",
            "context_packet",
            "task_context",
            "upstream_artifact",
            "upstream_artifacts",
            "upstream_context",
            "previous_artifact",
            "previous_artifacts",
        }:
            return True
        if re.match(r"^[a-z]:/", lowered):
            return True
        if lowered.startswith(
            (
                "/app/",
                "./",
                "../",
                "bench_cases/",
                "sgar_mvp/execution_outputs/",
                "generated_artifacts/",
            )
        ):
            return True
        if "/" in lowered and re.search(r"\.[a-z0-9]{1,10}($|[?#])", lowered):
            return True
        return False

    def _first_model_candidate_id(self, candidate_map: Dict[str, TypedResourceRef]) -> Optional[str]:
        for ref in candidate_map.values():
            if ref.resource_type == ManifestType.MODEL:
                return ref.resource_id
        return None

    def _collect_plan_input_references(self, steps: Sequence[Dict[str, Any]]) -> Tuple[set[str], set[str]]:
        step_ids: set[str] = set()
        output_keys: set[str] = set()

        for step in steps:
            if not isinstance(step, dict):
                continue
            bindings = step.get("input_bindings")
            if not isinstance(bindings, Mapping):
                continue
            try:
                referenced_steps, referenced_outputs = container_dependency_references(
                    bindings
                )
            except BindingProtocolError as exc:
                raise ValueError(f"plan_protocol_failure: {exc}") from exc
            step_ids.update(referenced_steps)
            output_keys.update(referenced_outputs)
        return step_ids, output_keys

    def _normalize_policy_payload(
        self,
        payload: Dict[str, Any],
        candidate_map: Dict[str, TypedResourceRef],
        subtask: Subtask,
        *,
        strict_plan_protocol: bool = False,
    ) -> Dict[str, Any]:
        # A formal fixed-pass Plan is evidence.  Strict mode may copy it for
        # isolation, but it must never repair, coerce, filter, or supplement
        # any semantic field before validation.
        normalized = deepcopy(payload or {})
        if strict_plan_protocol:
            return normalized
        mode_aliases = {
            "bypass": "BYPASS_MODE",
            "bypass_mode": "BYPASS_MODE",
            "tool": "BYPASS_MODE",
            "semi": "SEMI_GENERATIVE_MODE",
            "semi_generative": "SEMI_GENERATIVE_MODE",
            "semi_generative_mode": "SEMI_GENERATIVE_MODE",
            "generative": "FULL_GENERATIVE_MODE",
            "full": "FULL_GENERATIVE_MODE",
            "full_generative": "FULL_GENERATIVE_MODE",
            "full_generative_mode": "FULL_GENERATIVE_MODE",
        }
        for key in ("expected_execution_mode",):
            if key in normalized:
                mode_key = str(normalized.get(key) or "").strip().lower().replace("-", "_")
                normalized[key] = mode_aliases.get(mode_key, normalized.get(key))
        selected_resources = normalized.get("selected_resources")
        if isinstance(selected_resources, list):
            normalized_selected = []
            for item in selected_resources:
                if isinstance(item, str) and item in candidate_map:
                    normalized_selected.append(candidate_map[item].model_dump(mode="json"))
                elif isinstance(item, str) and self._is_policy_context_reference(item):
                    continue
                elif isinstance(item, dict):
                    resource_id = str(item.get("resource_id") or item.get("id") or "")
                    if resource_id and resource_id not in candidate_map and self._is_policy_context_reference(resource_id):
                        continue
                    if resource_id and "resource_id" not in item:
                        item = {**item, "resource_id": resource_id}
                    if resource_id in candidate_map and not item.get("resource_type"):
                        item = {**item, "resource_type": candidate_map[resource_id].resource_type.value}
                    normalized_selected.append(item)
            normalized["selected_resources"] = normalized_selected
        plan = normalized.get("application_plan")
        if not isinstance(plan, dict):
            return normalized
        for key in ("expected_execution_mode",):
            if key in plan:
                mode_key = str(plan.get(key) or "").strip().lower().replace("-", "_")
                plan[key] = mode_aliases.get(mode_key, plan.get(key))
        if not plan.get("selected_resource_ids") and normalized.get("selected_resources"):
            plan["selected_resource_ids"] = [
                item.get("resource_id")
                for item in normalized["selected_resources"]
                if isinstance(item, dict) and item.get("resource_id")
            ]
        elif isinstance(plan.get("selected_resource_ids"), list):
            plan["selected_resource_ids"] = [
                resource_id
                for resource_id in plan.get("selected_resource_ids") or []
                if str(resource_id) in candidate_map
                or not self._is_policy_context_reference(resource_id)
            ]

        final_output_from = plan.get("final_output_from")
        steps = plan.get("steps")
        if isinstance(steps, list):
            normalized_steps = []
            removed_pseudo_reads = []
            converted_pseudo_reads = []
            referenced_step_ids, referenced_output_keys = self._collect_plan_input_references(steps)
            fallback_model_id = self._first_model_candidate_id(candidate_map)
            for step in steps:
                if not isinstance(step, dict):
                    continue
                step_type_aliases = {
                    "model": "call_model",
                    "llm": "call_model",
                    "call_llm": "call_model",
                    "agent": "call_agent",
                    "tool": "run_tool",
                    "run": "run_tool",
                    "execute_code": "execute_generated_code",
                    "run_code": "execute_generated_code",
                    "execute_python": "execute_generated_code",
                    "validator": "validate_artifact",
                    "validate": "validate_artifact",
                    "final": "synthesize_final",
                    "synthesis": "synthesize_final",
                    "synthesize": "synthesize_final",
                    "read": "read_resource",
                    "resource": "read_resource",
                    "skill": "apply_skill_hint",
                }
                raw_step_type = str(step.get("step_type") or "").strip().lower().replace("-", "_")
                if raw_step_type in step_type_aliases and not strict_plan_protocol:
                    step["step_type"] = step_type_aliases[raw_step_type]
                contract = step.get("expected_output_contract")
                if isinstance(contract, dict):
                    if "artifact_type" in contract:
                        contract["artifact_type"] = self._normalize_policy_artifact_type(
                            contract.get("artifact_type"),
                            subtask,
                        )
                    if "schema_hint" in contract:
                        contract["schema_hint"] = self._normalize_schema_hint(contract.get("schema_hint"))
                resource_id = str(step.get("resource_id") or "")
                ref = candidate_map.get(resource_id)
                step_type = str(step.get("step_type") or "").strip().lower()
                is_final_step = (
                    step.get("output_key") == final_output_from
                    or step.get("step_id") == final_output_from
                )
                is_referenced_step = (
                    str(step.get("step_id") or "") in referenced_step_ids
                    or str(step.get("output_key") or "") in referenced_output_keys
                )
                if (
                    not strict_plan_protocol
                    and ref is None
                    and self._is_policy_context_reference(resource_id)
                ):
                    if step_type in {"read_resource", "context_resource", "apply_skill_hint", ""}:
                        if fallback_model_id and (is_final_step or is_referenced_step):
                            step["resource_id"] = fallback_model_id
                            step["step_type"] = "synthesize_final" if is_final_step else "call_model"
                            converted_pseudo_reads.append(
                                str(step.get("step_id") or step.get("output_key") or resource_id)
                            )
                            ref = candidate_map.get(fallback_model_id)
                        else:
                            removed_pseudo_reads.append(
                                str(step.get("step_id") or step.get("output_key") or resource_id)
                            )
                            continue
                if ref is not None:
                    if ref.resource_type == ManifestType.TOOL:
                        raw_tool = self.resource_index.get(resource_id, {})
                        allowed_capabilities = sorted(tool_allowed_operation_kinds(raw_tool))
                        supplied_capability = normalize_capability_operation(
                            step.get("capability_operation")
                        )
                        supplied_operation = normalize_capability_operation(
                            step.get("operation_kind")
                        )
                        derived_operation: Optional[str] = None
                        if len(allowed_capabilities) == 1:
                            # Manifest-derived protocol completion is safe: no
                            # task text or Case identity participates.
                            capability = allowed_capabilities[0]
                            step["capability_operation"] = capability
                            derived_operation = self._execution_kind_for_capability(
                                capability, raw_tool
                            )
                            step["operation_kind"] = derived_operation
                        elif supplied_capability in allowed_capabilities:
                            step["capability_operation"] = supplied_capability
                            derived_operation = self._execution_kind_for_capability(
                                supplied_capability, raw_tool
                            )
                            step["operation_kind"] = derived_operation
                        elif supplied_operation in allowed_capabilities:
                            step["capability_operation"] = supplied_operation
                            derived_operation = self._execution_kind_for_capability(
                                supplied_operation, raw_tool
                            )
                            step["operation_kind"] = derived_operation
                        if (
                            not strict_plan_protocol
                            and supplied_operation == "run_tool"
                            and derived_operation
                            and derived_operation != "run_tool"
                        ):
                            note = (
                                "normalized_tool_operation_kind="
                                f"run_tool->{derived_operation};resource_id={resource_id}"
                            )
                            plan["reason"] = (
                                str(plan.get("reason") or "").strip() + f" [{note}]"
                            ).strip()
                    if (
                        ref.resource_type == ManifestType.TOOL
                        and not str(step.get("operation_kind") or "").strip()
                    ):
                        step["operation_kind"] = self._safe_tool_operation_kind(
                            self.resource_index.get(resource_id, {})
                        )
                        step["step_type"] = "run_tool"
                    if (
                        not strict_plan_protocol
                        and ref.resource_type == ManifestType.MODEL
                        and step_type in {"read_resource", "context_resource"}
                    ):
                        if is_final_step:
                            step["step_type"] = "synthesize_final"
                        elif is_referenced_step:
                            step["step_type"] = "call_model"
                            converted_pseudo_reads.append(
                                str(step.get("step_id") or step.get("output_key") or resource_id)
                            )
                        else:
                            removed_pseudo_reads.append(
                                str(step.get("step_id") or step.get("output_key") or resource_id)
                            )
                            continue
                    elif (
                        not strict_plan_protocol
                        and ref.resource_type == ManifestType.MODEL
                        and step_type == "validate_artifact"
                    ):
                        step["step_type"] = (
                            "synthesize_final"
                            if is_final_step
                            else "call_model"
                        )
                    elif (
                        not strict_plan_protocol
                        and ref.resource_type == ManifestType.TOOL
                        and step_type not in {"run_tool", "execute_generated_code", "validate_artifact"}
                    ):
                        step["step_type"] = "run_tool"
                        step["operation_kind"] = self._safe_tool_operation_kind(
                            self.resource_index.get(resource_id, {})
                        )
                    elif not strict_plan_protocol and ref.resource_type == ManifestType.SKILL:
                        step["step_type"] = "apply_skill_hint"
                    elif not strict_plan_protocol and ref.resource_type == ManifestType.RESOURCE:
                        step["step_type"] = "read_resource"
                    if (
                        ref.resource_type == ManifestType.TOOL
                        and str(step.get("operation_kind") or "").strip().lower() == "run_tool"
                    ):
                        normalized_kind = self._safe_tool_operation_kind(
                            self.resource_index.get(resource_id, {})
                        )
                        if normalized_kind != "run_tool":
                            step["operation_kind"] = normalized_kind
                            note = (
                                "normalized_tool_operation_kind="
                                f"run_tool->{normalized_kind};resource_id={resource_id}"
                            )
                            plan["reason"] = (
                                str(plan.get("reason") or "").strip() + f" [{note}]"
                            ).strip()
                normalized_steps.append(step)
            if removed_pseudo_reads or converted_pseudo_reads:
                plan["steps"] = normalized_steps
                notes = []
                if removed_pseudo_reads:
                    notes.append("removed_context_pseudo_read=" + ",".join(removed_pseudo_reads))
                if converted_pseudo_reads:
                    notes.append("converted_context_pseudo_read=" + ",".join(converted_pseudo_reads))
                note = ";".join(notes)
                plan["reason"] = (str(plan.get("reason") or "").strip() + f" [{note}]").strip()
                steps = normalized_steps

            # Plan completion: guarantee the final step actually produces the
            # subtask's requested artifact. The control policy produces two kinds of
            # under-specified plans that both leave a structured tool output standing
            # in for a textual deliverable the tool cannot emit:
            #   (1) final_output_from names an intended deliverable (e.g.
            #       "quality_report") that no step produces — a dangling reference;
            #   (2) final_output_from points at a Tool step whose declared output
            #       (e.g. bandit -> json) cannot be the requested markdown/plaintext
            #       report.
            # In both cases the planner assigns a report artifact_type to a subtask
            # whose executor is a structured-output tool, and the bridge can only be
            # decided here (the planner does not know which tool will run). So append
            # the missing synthesize_final model step that consumes the tool outputs
            # and produces the requested artifact, and repoint final_output_from to
            # it. The tools then run as real intermediate steps and a model composes
            # the deliverable — deterministic compile-time completion, not a runtime
            # fallback. Structured targets (code/json/csv) are left untouched so a
            # genuine format incompatibility is still surfaced by preflight.
            report_types = {"markdown", "plaintext"}
            if (
                not strict_plan_protocol
                and isinstance(steps, list)
                and steps
                and final_output_from
            ):
                pairs = [
                    (str(s.get("step_id") or ""), str(s.get("output_key") or ""))
                    for s in steps
                    if isinstance(s, dict)
                ]
                existing_keys = {ok for _, ok in pairs if ok}
                existing_ids = {sid for sid, _ in pairs if sid}
                want_type = subtask.artifact_type.value

                producing_step = None
                for candidate_step in steps:
                    if not isinstance(candidate_step, dict):
                        continue
                    if (
                        candidate_step.get("output_key") == final_output_from
                        or candidate_step.get("step_id") == final_output_from
                    ):
                        producing_step = candidate_step
                        break

                needs_synthesis = False
                if final_output_from not in existing_keys and final_output_from not in existing_ids:
                    # (1) dangling final reference
                    needs_synthesis = True
                elif producing_step is not None and want_type in report_types:
                    # (2) a Tool would be final but cannot emit the requested report
                    prod_ref = candidate_map.get(str(producing_step.get("resource_id") or ""))
                    if prod_ref is not None and prod_ref.resource_type == ManifestType.TOOL:
                        prod_raw = self.resource_index.get(str(producing_step.get("resource_id") or ""), {})
                        prod_oc = self._manifest_output_contract(prod_raw)
                        declared_type = prod_oc.get("artifact_type") if isinstance(prod_oc, dict) else None
                        allowed_types = (prod_raw.get("constraint", {}) or {}).get("artifact_output", [])
                        satisfies = declared_type == want_type or (
                            isinstance(allowed_types, list) and want_type in allowed_types
                        )
                        if not satisfies:
                            needs_synthesis = True

                if needs_synthesis:
                    model_id = self._first_model_candidate_id(candidate_map)
                    if model_id:
                        input_bindings = {
                            ok: {"from_step": sid, "output_key": ok}
                            for sid, ok in pairs
                            if sid and ok
                        }
                        synth_output_key = f"final_synthesis_{subtask.id}"
                        steps.append(
                            {
                                "step_id": f"step_{synth_output_key}",
                                "step_type": "synthesize_final",
                                "resource_id": model_id,
                                "operation_kind": "synthesize_final",
                                "intent": (
                                    f"Synthesize the final {want_type} deliverable by "
                                    "combining the upstream step outputs."
                                ),
                                "input_bindings": input_bindings,
                                "output_key": synth_output_key,
                                "expected_output_contract": {"artifact_type": want_type},
                            }
                        )
                        plan["steps"] = steps
                        plan["final_output_from"] = synth_output_key
                        final_output_from = synth_output_key
                        selected_ids = plan.get("selected_resource_ids")
                        if not isinstance(selected_ids, list):
                            selected_ids = []
                        if model_id not in selected_ids:
                            selected_ids.append(model_id)
                        plan["selected_resource_ids"] = selected_ids
                        plan["reason"] = (
                            str(plan.get("reason") or "").strip()
                            + " [injected_synthesize_final]"
                        ).strip()

        usage = plan.get("resource_usage")
        if isinstance(usage, list):
            allowed_use_as = {
                "executable_step",
                "agent_base_model",
                "instruction_hint",
                "planning_hint",
                "intermediate_evidence",
                "validator",
                "validator_hint",
                "tool_macro_hint",
                "agent_protocol_hint",
                "context_resource",
            }
            step_items = steps if isinstance(steps, list) else []
            used_resource_ids = {
                str(step.get("resource_id"))
                for step in step_items
                if isinstance(step, dict) and step.get("resource_id")
            }
            normalized_usage = []
            for item in usage:
                if not isinstance(item, dict):
                    continue
                resource_id = str(item.get("resource_id") or item.get("id") or "")
                if resource_id and resource_id not in candidate_map and self._is_policy_context_reference(resource_id):
                    continue
                if resource_id and "resource_id" not in item:
                    item["resource_id"] = resource_id
                decision = str(item.get("decision") or "use").lower()
                if decision != "use":
                    continue
                item["decision"] = "use"
                use_as = str(item.get("use_as") or "executable_step").lower()
                if use_as not in allowed_use_as:
                    use_as = (
                        "executable_step"
                        if item.get("resource_id") in used_resource_ids
                        else "context_resource"
                    )
                item["use_as"] = use_as
                normalized_usage.append(item)
            plan["resource_usage"] = normalized_usage

        if final_output_from and isinstance(steps, list):
            for step in steps:
                if not isinstance(step, dict):
                    continue
                if step.get("output_key") != final_output_from and step.get("step_id") != final_output_from:
                    continue
                contract = step.setdefault("expected_output_contract", {})
                if isinstance(contract, dict):
                    contract["artifact_type"] = subtask.artifact_type.value
                break

        return normalized

    # -- Resource Helpers --------------------------------------------------

    def _resource_card(self, ref: TypedResourceRef) -> Dict[str, Any]:
        """Build a compact runtime card shown to the Plan Compiler policy."""
        from retrieval_profiles import declared_resource_limits, declared_task_context, reviewed_problem_space
        raw = self.resource_index.get(ref.resource_id, {})
        capability = raw.get("capability", {}) if isinstance(raw, dict) else {}
        constraint = raw.get("constraint", {}) if isinstance(raw, dict) else {}
        execution = raw.get("execution", {}) if isinstance(raw, dict) else {}
        type_specific = raw.get("type_specific", {}) if isinstance(raw, dict) else {}
        skill_block = type_specific.get("skill", {}) if isinstance(type_specific, dict) else {}
        model_block = type_specific.get("model", {}) if isinstance(type_specific, dict) else {}
        output_contract = self._manifest_output_contract(raw)
        inputs = [
            item.get("name") or item.get("kind") or "input"
            for item in self._manifest_input_contracts(raw)
        ]
        outputs: List[str] = []
        if output_contract.get("artifact_type"):
            outputs.append(str(output_contract["artifact_type"]))
        artifact_output = constraint.get("artifact_output")
        if isinstance(artifact_output, list):
            outputs.extend(str(item) for item in artifact_output if item not in outputs)

        cost_hint = "low"
        utility = raw.get("utility", {}) if isinstance(raw, dict) else {}
        try:
            cost = float(utility.get("token_cost_factor") or 0.01)
        except (TypeError, ValueError):
            cost = 0.01
        if cost > 2:
            cost_hint = "high"
        elif cost > 0.2:
            cost_hint = "medium"

        risk_hint = "low"
        runtime = str(execution.get("runtime") or "").lower()
        if ref.resource_type == ManifestType.TOOL and ("script" in runtime or execution.get("uri")):
            risk_hint = "medium"
        if str(execution.get("execution_risk") or "").lower() in {"high", "dangerous"}:
            risk_hint = "high"

        card: Dict[str, Any] = {
            "resource_id": ref.resource_id,
            "resource_type": ref.resource_type.value,
            "status": raw.get("status", "active") if isinstance(raw, dict) else "active",
            "family_id": self._resource_family_label(ref.resource_id),
            "base_model": ref.base_model,
            "candidate_origin": ref.candidate_origin,
            "injected_reason": ref.injected_reason,
            "similarity": ref.similarity,
            "can_do": capability.get("core_primitives", []),
            "problem_space": declared_task_context(raw) if ref.resource_type != ManifestType.SKILL else reviewed_problem_space(raw),
            "domain_tags": capability.get("domain_tags", []),
            "inputs": inputs or [constraint.get("io_signature", "")],
            "outputs": outputs or [constraint.get("io_signature", "")],
            "limitations": declared_resource_limits(raw),
            "cost_hint": cost_hint,
            "risk_hint": risk_hint,
            "selection_notes": [
                note for note in [
                    ref.candidate_origin,
                    ref.injected_reason,
                    f"runtime:{execution.get('runtime')}" if execution.get("runtime") else "",
                ] if note
            ][:4],
        }
        if ref.resource_type == ManifestType.MODEL:
            card["model"] = {
                "model_id": model_block.get("model_id") or execution.get("model_id") or ref.base_model,
                "context_window": model_block.get("context_window"),
            }
        if ref.resource_type == ManifestType.SKILL:
            card["skill"] = {
                "skill_kind": skill_block.get("skill_kind") or "planning_hint",
                "portability": skill_block.get("portability") or "pure_prompt",
                "workflow_hint": skill_block.get("workflow_hint", [])
                if isinstance(skill_block.get("workflow_hint", []), list)
                else [],
                "recommended_roles": skill_block.get("recommended_roles", [])
                if isinstance(skill_block.get("recommended_roles", []), list)
                else [],
                "avoid_when": skill_block.get("avoid_when", [])
                if isinstance(skill_block.get("avoid_when", []), list)
                else [],
                "required_resource_ids": skill_block.get(
                    "required_resource_ids", []
                )
                if isinstance(
                    skill_block.get("required_resource_ids", []), list
                )
                else [],
                "optional_resource_ids": skill_block.get(
                    "optional_resource_ids", []
                )
                if isinstance(
                    skill_block.get("optional_resource_ids", []), list
                )
                else [],
                "reference_topics": [
                    item.get("path")
                    for item in skill_block.get("reference_catalog", [])
                    if isinstance(item, dict) and item.get("path")
                ]
                if isinstance(
                    skill_block.get("reference_catalog", []), list
                )
                else [],
            }
        if ref.resource_type == ManifestType.TOOL:
            card["allowed_operation_kinds"] = sorted(tool_allowed_operation_kinds(raw))
            card["capability_operations"] = sorted(tool_allowed_operation_kinds(raw))
            card["execution_operation_kind"] = execution_operation_kind_for_tool(raw)
            card["execution"] = {
                "runtime": execution.get("runtime"),
                "has_uri": bool(execution.get("uri")),
            }
            if self.trust_effective_pool_readiness:
                runtime_requirements = raw.get("runtime_requirements", {})
                card["runtime_requirements"] = {
                    "runtime_profile": runtime_requirements.get("runtime_profile"),
                    "dependency_status": "ready_rc1",
                    "install_policy": runtime_requirements.get("install_policy"),
                    "missing_dependencies": [],
                    "install_packages": [],
                    "reason": "frozen_effective_pool_readiness",
                }
            else:
                dependency_result = self.dependency_gate.assess(ref.resource_id, raw)
                card["runtime_requirements"] = {
                    "runtime_profile": dependency_result.runtime_profile,
                    "dependency_status": dependency_result.dependency_status,
                    "install_policy": dependency_result.install_policy,
                    "missing_dependencies": dependency_result.missing_python_packages
                    + dependency_result.missing_commands,
                    "install_packages": dependency_result.install_packages,
                    "reason": dependency_result.reason,
                }
        return card

    def _default_application_plan(
        self,
        selected: Sequence[TypedResourceRef],
        expected_mode: ExecutionMode,
        reason: Optional[str],
    ) -> ResourceApplicationPlan:
        """Create a compatibility plan when the policy only returns selected_resources."""
        steps: List[ResourceApplicationStep] = []
        final_output_from: Optional[str] = None
        selected_refs = list(selected)
        agent_ref = next(
            (ref for ref in selected_refs if ref.resource_type == ManifestType.AGENT),
            None,
        )
        agent_model_ref = (
            next(
                (ref for ref in selected_refs if ref.resource_type == ManifestType.MODEL),
                None,
            )
            if agent_ref is not None
            else None
        )
        if agent_ref is not None and agent_model_ref is None:
            return ResourceApplicationPlan(
                is_sufficient=False,
                selected_resource_ids=[],
                resource_usage=[],
                steps=[],
                final_output_from=None,
                expected_execution_mode=expected_mode,
                reason="Compatibility plan cannot execute an Agent without a selected Model.",
            )

        execution_refs = [
            ref
            for ref in selected_refs
            if agent_model_ref is None or ref.resource_id != agent_model_ref.resource_id
        ]
        if agent_ref is not None:
            execution_refs = [
                ref for ref in execution_refs if ref.resource_id != agent_ref.resource_id
            ] + [agent_ref]
        preferred_final = agent_ref or next(
            (
                ref for ref in execution_refs
                if ref.resource_type == ManifestType.MODEL
            ),
            None,
        )
        final_ref = preferred_final or (execution_refs[-1] if execution_refs else None)
        prior_outputs: List[Dict[str, str]] = []

        for idx, ref in enumerate(execution_refs, start=1):
            output_key = f"{ref.resource_id}_output"
            raw = self.resource_index.get(ref.resource_id, {})
            artifact_value = self._manifest_output_artifact(raw)
            output_contract = self._manifest_output_contract(raw)
            contract = ResourceOutputContract(
                artifact_type=self._artifact_type_from_value(artifact_value),
                description=output_contract.get("description"),
            )
            input_bindings: Dict[str, Any] = {}
            if ref.resource_type == ManifestType.AGENT and agent_model_ref is not None:
                input_bindings["base_model"] = {
                    "resource_id": agent_model_ref.resource_id
                }
                if prior_outputs:
                    input_bindings["resource_inputs"] = list(prior_outputs)
            steps.append(
                ResourceApplicationStep(
                    step_id=f"step_{idx}",
                    step_type=self._infer_step_type_for_ref(ref),
                    resource_id=ref.resource_id,
                    operation_kind=(
                        self._safe_tool_operation_kind(raw)
                        if ref.resource_type == ManifestType.TOOL
                        else None
                    ),
                    intent=(
                        f"Apply {ref.resource_id} ({ref.resource_type.value}) "
                        "according to its manifest affordance for this subtask."
                    ),
                    input_bindings=input_bindings,
                    output_key=output_key,
                    expected_output_contract=contract,
                )
            )
            prior_outputs.append({"output_key": output_key})
            if final_ref is not None and ref.resource_id == final_ref.resource_id:
                final_output_from = output_key

        usage: List[ResourceUsageDecision] = []
        step_ids_by_resource = {
            step.resource_id: [step.step_id]
            for step in steps
        }
        for ref in selected_refs:
            if agent_model_ref is not None and ref.resource_id == agent_model_ref.resource_id:
                agent_step = next(
                    step for step in steps if step.resource_id == agent_ref.resource_id
                )
                usage.append(
                    ResourceUsageDecision(
                        resource_id=ref.resource_id,
                        decision="use",
                        use_as="agent_base_model",
                        attached_to_steps=[agent_step.step_id],
                        reason="Selected as the runtime Model for the Agent step.",
                    )
                )
                continue
            usage.append(
                ResourceUsageDecision(
                    resource_id=ref.resource_id,
                    decision="use",
                    use_as=(
                        "instruction_hint"
                        if ref.resource_type == ManifestType.SKILL
                        else "context_resource"
                        if ref.resource_type == ManifestType.RESOURCE
                        else "executable_step"
                    ),
                    attached_to_steps=step_ids_by_resource.get(ref.resource_id, []),
                    reason="Default compatibility plan selected this resource.",
                )
            )

        return ResourceApplicationPlan(
            is_sufficient=bool(execution_refs),
            selected_resource_ids=[ref.resource_id for ref in selected_refs],
            resource_usage=usage,
            steps=steps,
            final_output_from=final_output_from,
            expected_execution_mode=expected_mode,
            reason=reason,
        )

    @staticmethod
    def _safe_tool_operation_kind(raw: Dict[str, Any]) -> str:
        """Return a sole specific Tool kind, otherwise the legacy fallback."""
        return execution_operation_kind_for_tool(raw)

    @staticmethod
    def _execution_kind_for_capability(
        capability_operation: str,
        raw: Dict[str, Any],
    ) -> str:
        spec = CAPABILITY_OPERATION_REGISTRY.get(capability_operation)
        if spec is not None:
            return str(spec["execution_operation_kind"])
        if capability_operation in {item.value for item in OperationKind}:
            return capability_operation
        return execution_operation_kind_for_tool(raw)

    def _first_tool_with_capability(
        self,
        refs: Sequence[TypedResourceRef],
        capability_operation: str,
    ) -> Optional[TypedResourceRef]:
        """Resolve a Tool role from Manifest capabilities, never a fixed ID."""

        seen: set[str] = set()
        for ref in refs:
            if ref.resource_id in seen or ref.resource_type != ManifestType.TOOL:
                continue
            seen.add(ref.resource_id)
            if capability_operation in tool_allowed_operation_kinds(
                self.resource_index.get(ref.resource_id, {})
            ):
                return ref
        return None

    def _infer_step_type_for_ref(self, ref: TypedResourceRef) -> str:
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

    def _complete_selected_refs_from_plan(
        self,
        selected: Sequence[TypedResourceRef],
        application_plan: ResourceApplicationPlan,
        candidate_map: Dict[str, TypedResourceRef],
    ) -> List[TypedResourceRef]:
        """Ensure every used or executed resource in the plan is available downstream."""
        selected_by_id = {ref.resource_id: ref for ref in selected}
        ordered_ids: List[str] = []
        for resource_id in application_plan.selected_resource_ids:
            ordered_ids.append(resource_id)
        for step in application_plan.steps:
            ordered_ids.append(step.resource_id)
        for usage in application_plan.resource_usage:
            if str(usage.decision).lower() == "use":
                ordered_ids.append(usage.resource_id)

        for resource_id in ordered_ids:
            if resource_id in selected_by_id:
                continue
            candidate = candidate_map.get(resource_id)
            if candidate is not None:
                selected_by_id[resource_id] = candidate

        return list(selected_by_id.values())

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

    def _resource_type_from_index(self, resource_id: str) -> Optional[ManifestType]:
        raw = self.resource_index.get(resource_id, {})
        if not isinstance(raw, dict):
            return None
        return self._coerce_manifest_type(
            raw.get("type", {}).get("resource_type") or raw.get("resource_type")
        )

    def _normalize_step_output_bindings(
        self,
        value: Any,
        prior_step_outputs: Dict[str, str],
        prior_output_keys: set[str],
        *,
        allow_normalization: bool = True,
    ) -> Any:
        if isinstance(value, list):
            return [
                self._normalize_step_output_bindings(
                    item,
                    prior_step_outputs,
                    prior_output_keys,
                    allow_normalization=allow_normalization,
                )
                for item in value
            ]
        if not isinstance(value, Mapping):
            return deepcopy(value)

        try:
            source = parse_binding_source(value)
        except BindingProtocolError as exc:
            raise ValueError(f"plan_protocol_failure: {exc}") from exc
        # Ordinary objects and explicit literals are opaque data.  In
        # particular, nested from_step/output_key-looking fields inside them
        # never become DAG dependencies.
        if source.variant != "step_output":
            return deepcopy(value)

        from_step = source.from_step
        output_key = source.output_key
        if from_step:
            from_step = str(from_step)
            if from_step not in prior_step_outputs:
                raise ValueError(
                    f"policy_invalid_plan: input binding references unavailable or later step {from_step}"
                )
            expected_output_key = prior_step_outputs[from_step]
            if output_key and str(output_key) != expected_output_key:
                raise ValueError(
                    "policy_invalid_plan: input binding output_key does not match "
                    f"from_step {from_step}"
                )
        elif output_key and str(output_key) not in prior_output_keys:
            raise ValueError(
                f"policy_invalid_plan: input binding references unavailable output_key {output_key}"
            )
        if not allow_normalization:
            return deepcopy(value)
        return normalize_step_reference(value, prior_step_outputs)

    def _apply_agent_model_bindings(
        self,
        selected: Sequence[TypedResourceRef],
        plan: ResourceApplicationPlan,
        candidate_map: Dict[str, TypedResourceRef],
    ) -> List[TypedResourceRef]:
        """Resolve selected Model resources to API IDs on their bound Agent refs."""
        agent_api_models: Dict[str, str] = {}
        for step in plan.steps:
            agent_ref = candidate_map.get(step.resource_id)
            if (
                agent_ref is None
                or agent_ref.resource_type != ManifestType.AGENT
                or str(step.step_type or "").lower() not in {"call_agent", "synthesize_final"}
            ):
                continue
            model_resource_id = self._binding_resource_id(
                step.input_bindings.get("base_model")
            )
            if not model_resource_id:
                continue
            model_ref = candidate_map.get(model_resource_id)
            if model_ref is None or model_ref.resource_type != ManifestType.MODEL:
                continue
            agent_api_models[step.resource_id] = (
                model_ref.base_model
                or self._model_api_id_from_raw(
                    self.resource_index.get(model_resource_id, {})
                )
                or model_resource_id
            )

        return [
            ref.model_copy(update={"base_model": agent_api_models[ref.resource_id]})
            if ref.resource_id in agent_api_models
            else ref
            for ref in selected
        ]

    @staticmethod
    def _require_protocol_fields(value: Any, fields: set[str], label: str) -> None:
        present = set(getattr(value, "model_fields_set", set()))
        missing = sorted(fields - present)
        if missing:
            raise ValueError(
                f"plan_protocol_failure: {label} missing explicit fields "
                + ",".join(missing)
            )

    def _validate_strict_application_plan(
        self,
        plan: ResourceApplicationPlan,
        candidate_ids: set[str],
        subtask: Optional[Subtask],
    ) -> ResourceApplicationPlan:
        """Validate a fixed-pass compiler Plan without semantic repair."""

        self._require_protocol_fields(
            plan,
            {
                "selected_resource_ids",
                "resource_usage",
                "steps",
                "final_output_from",
                "expected_execution_mode",
            },
            "application_plan",
        )
        selected_ids = list(plan.selected_resource_ids)
        if len(selected_ids) != len(set(selected_ids)):
            raise ValueError("plan_protocol_failure: duplicate selected_resource_ids")
        unknown_selected = [item for item in selected_ids if item not in candidate_ids]
        if unknown_selected:
            raise ValueError(
                "policy_hallucinated_resource: " + ",".join(unknown_selected)
            )

        usage_by_resource: Dict[str, ResourceUsageDecision] = {}
        for usage in plan.resource_usage:
            self._require_protocol_fields(
                usage,
                {"decision", "use_as", "attached_to_steps"},
                f"resource_usage[{usage.resource_id}]",
            )
            if usage.resource_id in usage_by_resource:
                raise ValueError(
                    f"plan_protocol_failure: duplicate resource_usage {usage.resource_id}"
                )
            if usage.resource_id not in candidate_ids:
                raise ValueError(f"policy_hallucinated_resource: {usage.resource_id}")
            if usage.resource_id not in selected_ids:
                raise ValueError(
                    "plan_protocol_failure: resource_usage is not selected: "
                    f"{usage.resource_id}"
                )
            if usage.decision != "use":
                raise ValueError(
                    "plan_protocol_failure: selected-only resource_usage decision "
                    f"must be use: {usage.resource_id}"
                )
            usage_by_resource[usage.resource_id] = usage
        if set(usage_by_resource) != set(selected_ids):
            raise ValueError(
                "plan_protocol_failure: resource_usage IDs must exactly match "
                "selected_resource_ids"
            )

        output_keys: set[str] = set()
        step_ids: set[str] = set()
        step_id_to_output_key: Dict[str, str] = {}
        final_step: Optional[ResourceApplicationStep] = None
        allowed_step_types = {
            ManifestType.TOOL: {"run_tool", "execute_generated_code", "validate_artifact"},
            ManifestType.MODEL: {"call_model", "synthesize_final"},
            ManifestType.AGENT: {"call_agent", "synthesize_final"},
            ManifestType.SKILL: {"apply_skill_hint"},
            ManifestType.RESOURCE: {"read_resource"},
        }
        allowed_non_tool_operations = {
            ManifestType.MODEL: {
                "call_model": {"call_model", "produce_artifact"},
                "synthesize_final": {"synthesize_final"},
            },
            ManifestType.AGENT: {
                "call_agent": {"call_agent", "produce_artifact"},
                "synthesize_final": {"synthesize_final"},
            },
            ManifestType.SKILL: {"apply_skill_hint": {"apply_context_hint"}},
            ManifestType.RESOURCE: {"read_resource": {"inspect_input"}},
        }

        for step in plan.steps:
            self._require_protocol_fields(
                step,
                {"step_type", "operation_kind", "input_bindings"},
                f"step[{step.step_id}]",
            )
            if not step.step_type:
                raise ValueError(
                    f"plan_protocol_failure: step_type missing for {step.step_id}"
                )
            if step.operation_kind is None:
                raise ValueError(
                    f"plan_protocol_failure: operation_kind missing for {step.step_id}"
                )
            if step.resource_id not in candidate_ids:
                raise ValueError(f"policy_hallucinated_resource: {step.resource_id}")
            if step.resource_id not in selected_ids:
                raise ValueError(
                    "plan_protocol_failure: step resource is not selected: "
                    f"{step.resource_id}"
                )
            if step.step_id in step_ids:
                raise ValueError(f"plan_protocol_failure: duplicate step_id {step.step_id}")
            if step.output_key in output_keys:
                raise ValueError(
                    f"plan_protocol_failure: duplicate output_key {step.output_key}"
                )

            resource_type = self._resource_type_from_index(step.resource_id)
            if resource_type not in allowed_step_types:
                raise ValueError(
                    "plan_protocol_failure: unsupported or missing resource_type for "
                    f"{step.resource_id}"
                )
            if step.step_type not in allowed_step_types[resource_type]:
                raise ValueError(
                    "plan_protocol_failure: step_type "
                    f"{step.step_type} is incompatible with {resource_type.value} "
                    f"{step.resource_id}"
                )
            operation_value = step.operation_kind.value
            if resource_type == ManifestType.TOOL:
                self._require_protocol_fields(
                    step,
                    {"capability_operation"},
                    f"Tool step[{step.step_id}]",
                )
                if not step.capability_operation:
                    raise ValueError(
                        "plan_protocol_failure: Tool step requires capability_operation: "
                        f"{step.step_id}"
                    )
                raw_tool = self.resource_index.get(step.resource_id, {})
                allowed_capabilities = set(tool_allowed_operation_kinds(raw_tool))
                if step.capability_operation not in allowed_capabilities:
                    raise ValueError(
                        "plan_protocol_failure: capability_operation "
                        f"{step.capability_operation} is not declared by {step.resource_id}"
                    )
                expected_operation = self._execution_kind_for_capability(
                    step.capability_operation,
                    raw_tool,
                )
                if operation_value != expected_operation:
                    raise ValueError(
                        "plan_protocol_failure: operation_kind does not match "
                        f"capability_operation for {step.step_id}; "
                        f"expected={expected_operation},actual={operation_value}"
                    )
            else:
                allowed_operations = allowed_non_tool_operations[resource_type][
                    step.step_type
                ]
                if operation_value not in allowed_operations:
                    raise ValueError(
                        "plan_protocol_failure: operation_kind "
                        f"{operation_value} is incompatible with step_type "
                        f"{step.step_type} for {step.resource_id}"
                    )

            for binding in step.input_bindings.values():
                self._normalize_step_output_bindings(
                    binding,
                    step_id_to_output_key,
                    output_keys,
                    allow_normalization=False,
                )
            output_keys.add(step.output_key)
            step_ids.add(step.step_id)
            step_id_to_output_key[step.step_id] = step.output_key
            if step.output_key == plan.final_output_from:
                final_step = step

        for usage in plan.resource_usage:
            unknown_steps = set(usage.attached_to_steps) - step_ids
            if unknown_steps:
                raise ValueError(
                    "plan_protocol_failure: resource_usage references unknown steps "
                    + ",".join(sorted(unknown_steps))
                )
        step_resource_ids = {step.resource_id for step in plan.steps}
        for resource_id in set(selected_ids) - step_resource_ids:
            usage = usage_by_resource[resource_id]
            if not usage.attached_to_steps:
                raise ValueError(
                    "plan_protocol_failure: selected non-step resource must declare "
                    f"attached_to_steps: {resource_id}"
                )

        if plan.is_sufficient:
            if not plan.steps:
                raise ValueError("plan_protocol_failure: sufficient plan has no steps")
            if not plan.final_output_from:
                raise ValueError("plan_protocol_failure: missing final_output_from")
            if plan.final_output_from not in output_keys:
                raise ValueError(
                    "plan_protocol_failure: final_output_from must be an exact "
                    f"output_key, got {plan.final_output_from}"
                )
            if final_step is None or final_step.expected_output_contract is None:
                raise ValueError(
                    "plan_protocol_failure: final step missing expected_output_contract"
                )
            self._require_protocol_fields(
                final_step.expected_output_contract,
                {"artifact_type"},
                f"final contract[{final_step.step_id}]",
            )
            if final_step.expected_output_contract.artifact_type is None:
                raise ValueError(
                    "plan_protocol_failure: final contract missing artifact_type"
                )
            if (
                subtask is not None
                and final_step.expected_output_contract.artifact_type
                != subtask.artifact_type
            ):
                raise ValueError(
                    "plan_protocol_failure: final contract artifact_type does not "
                    "match the subtask output contract"
                )

        selected_id_set = set(selected_ids)
        for step in plan.steps:
            if self._resource_type_from_index(step.resource_id) != ManifestType.AGENT:
                continue
            model_resource_id = self._binding_resource_id(
                step.input_bindings.get("base_model")
            )
            if not model_resource_id or model_resource_id not in selected_id_set:
                raise ValueError(
                    f"plan_protocol_failure: Agent step {step.step_id} has no selected base_model"
                )
            if self._resource_type_from_index(model_resource_id) != ManifestType.MODEL:
                raise ValueError(
                    f"plan_protocol_failure: Agent base_model is not a Model: {model_resource_id}"
                )
            model_usage = usage_by_resource.get(model_resource_id)
            if (
                model_usage is None
                or model_usage.use_as != "agent_base_model"
                or step.step_id not in model_usage.attached_to_steps
            ):
                raise ValueError(
                    "plan_protocol_failure: bound Model must use_as=agent_base_model "
                    f"and attach to {step.step_id}"
                )
        return plan

    def _validate_application_plan(
        self,
        plan: ResourceApplicationPlan,
        candidate_ids: set[str],
        subtask: Optional[Subtask] = None,
        *,
        strict_plan_protocol: bool = False,
    ) -> ResourceApplicationPlan:
        """Validate policy plan references without constraining dynamic usage intent."""
        if strict_plan_protocol:
            return self._validate_strict_application_plan(
                plan.model_copy(deep=True),
                candidate_ids,
                subtask,
            )
        selected_ids: List[str] = []
        for resource_id in plan.selected_resource_ids:
            if resource_id not in candidate_ids:
                if self._is_policy_context_reference(resource_id):
                    continue
                raise ValueError(f"policy_hallucinated_resource: {resource_id}")
            selected_ids.append(resource_id)
        plan.selected_resource_ids = selected_ids

        cleaned_usage: List[ResourceUsageDecision] = []
        for usage in plan.resource_usage:
            usage.decision = str(usage.decision or "use").lower()
            usage.use_as = str(usage.use_as or "executable_step")
            if usage.resource_id not in candidate_ids:
                if self._is_policy_context_reference(usage.resource_id):
                    continue
                raise ValueError(f"policy_hallucinated_resource: {usage.resource_id}")
            if usage.decision != "use":
                continue
            cleaned_usage.append(usage)
        plan.resource_usage = cleaned_usage

        output_keys: set[str] = set()
        step_ids: set[str] = set()
        step_id_to_output_key: Dict[str, str] = {}
        cleaned_steps: List[ResourceApplicationStep] = []
        for step in plan.steps:
            if step.resource_id not in candidate_ids:
                if self._is_policy_context_reference(step.resource_id) and str(step.step_type or "").lower() in {
                    "read_resource",
                    "context_resource",
                    "apply_skill_hint",
                }:
                    continue
                raise ValueError(f"policy_hallucinated_resource: {step.resource_id}")
            if not step.step_type:
                raw = self.resource_index.get(step.resource_id, {})
                resource_type = self._coerce_manifest_type(
                    raw.get("type", {}).get("resource_type") or raw.get("resource_type")
                )
                if resource_type is not None:
                    step.step_type = self._infer_step_type_for_ref(
                        TypedResourceRef(resource_id=step.resource_id, resource_type=resource_type)
                    )
            resource_type = self._resource_type_from_index(step.resource_id)
            allowed_step_types = {
                ManifestType.TOOL: {"run_tool", "execute_generated_code", "validate_artifact"},
                ManifestType.MODEL: {"call_model", "synthesize_final"},
                ManifestType.AGENT: {"call_agent", "synthesize_final"},
                ManifestType.SKILL: {"apply_skill_hint"},
                ManifestType.RESOURCE: {"read_resource"},
            }
            if (
                resource_type in allowed_step_types
                and str(step.step_type or "") not in allowed_step_types[resource_type]
            ):
                raise ValueError(
                    "plan_protocol_failure: step_type "
                    f"{step.step_type} is incompatible with {resource_type.value} "
                    f"{step.resource_id}"
                )
            if resource_type == ManifestType.TOOL:
                raw_tool = self.resource_index.get(step.resource_id, {})
                allowed_capabilities = sorted(tool_allowed_operation_kinds(raw_tool))
                if len(allowed_capabilities) == 1:
                    step.capability_operation = allowed_capabilities[0]
                elif not step.capability_operation:
                    raise ValueError(
                        "plan_protocol_failure: multi-capability Tool requires an explicit "
                        f"capability_operation: {step.resource_id}"
                    )
                if step.capability_operation not in allowed_capabilities:
                    raise ValueError(
                        "plan_protocol_failure: capability_operation "
                        f"{step.capability_operation} is not declared by {step.resource_id}; "
                        f"allowed={allowed_capabilities}"
                    )
                step.operation_kind = OperationKind(
                    self._execution_kind_for_capability(
                        step.capability_operation,
                        raw_tool,
                    )
                )
            if step.output_key in output_keys:
                raise ValueError(f"policy_invalid_plan: duplicate output_key {step.output_key}")
            if step.step_id in step_ids:
                raise ValueError(f"policy_invalid_plan: duplicate step_id {step.step_id}")
            step.input_bindings = {
                name: self._normalize_step_output_bindings(
                    binding,
                    step_id_to_output_key,
                    output_keys,
                )
                for name, binding in step.input_bindings.items()
            }
            output_keys.add(step.output_key)
            step_ids.add(step.step_id)
            step_id_to_output_key[step.step_id] = step.output_key
            cleaned_steps.append(step)
        plan.steps = cleaned_steps

        if subtask is not None:
            task_text = self._subtask_text(subtask)
            read_only_task = bool(
                any(marker in task_text for marker in ("read", "inspect", "list", "search", "metadata", "contents", '\u6811', '\u8bfb\u53d6', '\u68c0\u67e5'))
                and not any(marker in task_text for marker in ("write", "edit", "delete", "remove", "move", "create", "modify", '\u4fee\u6539', '\u521b\u5efa', '\u5220\u9664'))
            )
            if read_only_task:
                for step in plan.steps:
                    raw = self.resource_index.get(step.resource_id, {})
                    routing = raw.get("routing", {}) if isinstance(raw, dict) else {}
                    family = str(routing.get("family") or "").lower() if isinstance(routing, dict) else ""
                    manifest_blob = json.dumps(raw, ensure_ascii=False).lower()
                    mutating = (
                        "mutation" in family
                        or any(marker in family for marker in ("git-add", "git-commit", "file-edit", "file-write", "file-delete", "file-move"))
                        or any(marker in manifest_blob for marker in ("replace exact text", "add files to the index", "delete a file", "move or rename"))
                    )
                    if mutating and str(step.operation_kind or "").lower() == "run_tool":
                        raise ValueError(
                            f"policy_invalid_plan: mutating Tool {step.resource_id} cannot execute for a read-only subtask"
                        )
            if any(marker in task_text for marker in ("search", "grep", "pattern", '\u641c\u7d22')):
                for step in plan.steps:
                    raw = self.resource_index.get(step.resource_id, {})
                    family = str((raw.get("routing", {}) or {}).get("family") or "").lower()
                    if str(step.operation_kind or "").lower() == "run_tool" and family in {
                        "filesystem-discovery",
                        "filesystem-listing",
                    }:
                        raise ValueError(
                            f"policy_invalid_plan: directory listing Tool {step.resource_id} cannot satisfy a search subtask"
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
                    attached_to_steps=step_ids_by_resource.get(resource_id, []),
                    reason="Derived from application_plan steps.",
                )
                for resource_id in step_ids_by_resource
            ]

        selected_ids = list(plan.selected_resource_ids)
        for step in plan.steps:
            if step.resource_id not in selected_ids:
                selected_ids.append(step.resource_id)
        for usage in plan.resource_usage:
            if usage.resource_id not in selected_ids:
                selected_ids.append(usage.resource_id)
        plan.selected_resource_ids = selected_ids

        selected_id_set = set(selected_ids)
        usage_by_resource = {usage.resource_id: usage for usage in plan.resource_usage}
        step_resource_ids = {step.resource_id for step in plan.steps}
        for usage in plan.resource_usage:
            unknown_steps = set(usage.attached_to_steps) - step_ids
            if unknown_steps:
                raise ValueError(
                    "policy_invalid_plan: resource_usage references unknown attached_to_steps "
                    + ",".join(sorted(unknown_steps))
                )
        for resource_id in selected_id_set - step_resource_ids:
            usage = usage_by_resource.get(resource_id)
            if usage is None or not usage.attached_to_steps:
                raise ValueError(
                    "policy_invalid_plan: selected non-step resource must declare use_as "
                    f"and attached_to_steps: {resource_id}"
                )

        for step in plan.steps:
            if self._resource_type_from_index(step.resource_id) != ManifestType.AGENT:
                continue
            model_resource_id = self._binding_resource_id(
                step.input_bindings.get("base_model")
            )
            if not model_resource_id:
                raise ValueError(
                    f"agent_missing_base_model: Agent step {step.step_id} has no base_model binding"
                )
            if model_resource_id not in candidate_ids:
                raise ValueError(
                    f"policy_hallucinated_resource: Agent base Model {model_resource_id}"
                )
            if model_resource_id not in selected_id_set:
                raise ValueError(
                    f"agent_missing_base_model: Model {model_resource_id} is not selected"
                )
            if self._resource_type_from_index(model_resource_id) != ManifestType.MODEL:
                raise ValueError(
                    f"agent_invalid_base_model: {model_resource_id} is not a Model resource"
                )
            model_usage = usage_by_resource.get(model_resource_id)
            if (
                model_usage is None
                or model_usage.use_as != "agent_base_model"
                or step.step_id not in model_usage.attached_to_steps
            ):
                raise ValueError(
                    "agent_invalid_base_model: bound Model must use_as=agent_base_model "
                    f"and attach to {step.step_id}"
                )

        if plan.is_sufficient:
            if not plan.steps:
                raise ValueError("policy_invalid_plan: sufficient plan has no steps")
            if not plan.final_output_from:
                raise ValueError("policy_invalid_plan: missing final_output_from")
            if plan.final_output_from not in output_keys:
                mapped_output = step_id_to_output_key.get(plan.final_output_from)
                if mapped_output is None:
                    raise ValueError(
                        f"policy_invalid_plan: final_output_from {plan.final_output_from} is not a step output_key"
                    )
                plan = plan.model_copy(update={"final_output_from": mapped_output})
            if subtask is not None:
                for idx, step in enumerate(plan.steps):
                    if step.output_key != plan.final_output_from:
                        continue
                    contract = step.expected_output_contract
                    if contract is None:
                        step.expected_output_contract = ResourceOutputContract(
                            artifact_type=subtask.artifact_type,
                            description="Final output aligned with the Planner output_contract.",
                        )
                    elif (
                        contract.artifact_type == ArtifactType.PLAINTEXT
                        and subtask.artifact_type != ArtifactType.PLAINTEXT
                    ):
                        plan.steps[idx] = step.model_copy(
                            update={
                                "expected_output_contract": contract.model_copy(
                                    update={"artifact_type": subtask.artifact_type}
                                )
                            }
                        )
                    break
        return plan

    def _passes_hard_gate(self, ref: TypedResourceRef) -> bool:
        """Only remove resources that are clearly unusable at runtime."""
        raw = self.resource_index.get(ref.resource_id, {})
        status = str(raw.get("status") or raw.get("execution", {}).get("execution_status") or "active").lower()
        if status in {"unavailable", "disabled", "inactive"}:
            return False
        if ref.resource_type == ManifestType.DEVICE:
            return False
        risk = str(raw.get("execution", {}).get("execution_risk") or raw.get("constraint", {}).get("execution_risk") or "").lower()
        if risk in {"forbidden", "disallowed", "unsafe"}:
            return False
        if ref.resource_type == ManifestType.TOOL and not self.trust_effective_pool_readiness:
            dependency_result = self.dependency_gate.assess(ref.resource_id, raw)
            if dependency_result.is_blocked:
                logger.warning(
                    "[Router] Skipping dependency-blocked resource {} | {}",
                    ref.resource_id,
                    dependency_result.reason,
                )
                return False
        if ref.resource_type == ManifestType.SKILL:
            execution = raw.get("execution", {}) if isinstance(raw, dict) else {}
            if execution.get("runtime") != "prompt_skill":
                return False
            uri = str(execution.get("uri") or "")
            if not uri.startswith("file://"):
                return False
            project_root = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..")
            )
            skill_path = os.path.abspath(
                os.path.join(project_root, uri.removeprefix("file://"))
            )
            if not os.path.isfile(skill_path):
                return False
            skill_block = raw.get("type_specific", {}).get("skill", {})
            required_ids = (
                skill_block.get("required_resource_ids", [])
                if isinstance(skill_block, dict)
                else []
            )
            for dependency_id in required_ids:
                dependency_raw = self.resource_index.get(str(dependency_id))
                if not isinstance(dependency_raw, dict):
                    return False
                dependency_status = str(
                    dependency_raw.get("status")
                    or dependency_raw.get("execution", {}).get(
                        "execution_status"
                    )
                    or "active"
                ).lower()
                if dependency_status in {"unavailable", "disabled", "inactive"}:
                    return False
                dependency_type = (
                    dependency_raw.get("resource_type")
                    or dependency_raw.get("type", {}).get("resource_type")
                )
                if (
                    dependency_type == "Tool"
                    and not self.trust_effective_pool_readiness
                ):
                    dependency_result = self.dependency_gate.assess(
                        str(dependency_id),
                        dependency_raw,
                    )
                    if dependency_result.is_blocked:
                        return False
        provenance = raw.get("provenance", {}) if isinstance(raw, dict) else {}
        license_value = str(provenance.get("license") or raw.get("license") or "").lower()
        trust_level = str(provenance.get("trust_level") or raw.get("trust_level") or "").lower()
        if license_value in {"forbidden", "disallowed", "not_allowed", "restricted_blocked"}:
            return False
        if trust_level in {"blocked", "untrusted", "malicious"}:
            return False
        return True

    def _candidate_bundle_score(
        self,
        subtask: Subtask,
        ref: TypedResourceRef,
        library: List[Manifest],
    ) -> float:
        """Small deterministic score used only for compact-bundle ordering."""
        raw = self.resource_index.get(ref.resource_id, {})
        score = float(ref.similarity or 0.0) * 10.0
        if ref.candidate_origin == "anchor":
            score += 2.0
        elif ref.candidate_origin in {
            "domain_injection",
            "explicit_dependency",
            "agent_dependency_hint",
            "skill_dependency_hint",
        }:
            score += 1.5
        elif ref.candidate_origin == "dependency_slot":
            score += 1.0

        output_artifact = self._manifest_output_artifact(raw)
        artifact_outputs = raw.get("constraint", {}).get("artifact_output", [])
        if output_artifact == subtask.artifact_type.value:
            score += 2.0
        elif isinstance(artifact_outputs, list) and subtask.artifact_type.value in artifact_outputs:
            score += 1.2

        if self._manifest_input_contracts(raw):
            score += 0.4
        if self._role_matches_subtask(subtask, ref):
            score += 1.2
        if self._runtime_intent_match(subtask, ref):
            # Runtime/domain evidence is stronger than a small embedding
            # difference for executable resources.
            score += 5.0
        if ref.resource_type == ManifestType.MODEL and ref.base_model:
            score += 0.8
        if ref.resource_type == ManifestType.TOOL and raw.get("execution", {}).get("uri"):
            score += 0.6

        success, cost, latency = self._normalized_utility(ref, library)
        score += min(max(success, 0.0), 1.0)
        if cost > 2.0:
            score -= 1.0
        elif cost <= 0.05:
            score += 0.4
        if latency > 60000:
            score -= 0.4
        return score

    def _role_matches_subtask(self, subtask: Subtask, ref: TypedResourceRef) -> bool:
        text = f"{subtask.description}\n{subtask.expected_output}\n{subtask.artifact_type.value}".lower()
        rid = ref.resource_id.lower()
        raw = self.resource_index.get(ref.resource_id, {})
        capability_text = json.dumps(raw.get("capability", {}), ensure_ascii=False).lower()
        blob = f"{rid}\n{capability_text}"
        if any(marker in text for marker in ("csv", "clean", '\u6e05\u6d17', '\u6570\u636e')) and any(
            marker in blob for marker in ("csv", "data", "clean", "pandas")
        ):
            return True
        if any(marker in text for marker in ("execute", "run", '\u6267\u884c', '\u8fd0\u884c', "script", "code")) and any(
            marker in blob for marker in ("runner", "execute", "pytest", "python")
        ):
            return True
        if any(marker in text for marker in ("validate", "verify", '\u68c0\u67e5', '\u9a8c\u8bc1', "test")) and any(
            marker in blob for marker in ("validator", "pytest", "check", "schema")
        ):
            return True
        if subtask.artifact_type == ArtifactType.CODE and ref.resource_type == ManifestType.MODEL:
            return any(marker in blob for marker in ("code", "coder", "gpt", "qwen", "claude"))
        return False

    def _runtime_intent_match(self, subtask: Subtask, ref: TypedResourceRef) -> bool:
        """Match concrete runtime tools using manifest language, not embeddings alone."""
        if ref.resource_type != ManifestType.TOOL:
            return False
        raw = self.resource_index.get(ref.resource_id, {})
        execution = raw.get("execution", {}) if isinstance(raw, dict) else {}
        runtime = str(execution.get("runtime") or "").lower()
        routing = raw.get("routing", {}) if isinstance(raw, dict) else {}
        tags = routing.get("intent_tags", []) if isinstance(routing, dict) else []
        family = routing.get("family", "") if isinstance(routing, dict) else ""
        negative_intents = routing.get("negative_intents", []) if isinstance(routing, dict) else []
        domains = raw.get("capability", {}).get("domain_tags", []) if isinstance(raw.get("capability"), dict) else []
        primitives = raw.get("capability", {}).get("core_primitives", []) if isinstance(raw.get("capability"), dict) else []
        manifest_text = " ".join([ref.resource_id, runtime, str(family), *map(str, tags), *map(str, domains), *map(str, primitives)]).lower()
        task_text = self._subtask_text(subtask)

        # A Tool's wrapper runtime is an implementation detail.  Match the
        # declared semantic operation first so network-capable Python wrappers
        # (for example a web-search adapter) receive the same deterministic
        # completion treatment as REST and MCP tools.
        task_operations = normalize_task_general_operation_kinds(task_text)
        manifest_operations = set(tool_allowed_operation_kinds(raw))
        manifest_operations.update(manifest_capability_operations(raw))
        if task_operations & manifest_operations:
            return True

        runtime_markers = {
            "rest_api": ("api", "rest", "http", "https", "endpoint", "weather", "exchange rate", "world bank", "arxiv", '\u641c\u7d22', '\u68c0\u7d22', '\u67e5\u8be2'),
            "mcp_server": (
                "mcp", "filesystem", "directory", "git", "repository", "worktree",
                "supplied file", "source file", "local file", "supplied files",
                '\u6587\u4ef6\u7cfb\u7edf', '\u76ee\u5f55', '\u4ed3\u5e93',
            ),
            "python_library": (
                "pdf", "pdfplumber", "pypdf", "csv", "excel", "xml", "python library"
            ),
        }
        markers = runtime_markers.get(runtime)
        if runtime == "python_script":
            test_manifest = any(
                marker in manifest_text
                for marker in ("pytest", "test runner", "test-execution", "execute_pytest")
            )
            test_task = any(
                marker in task_text
                for marker in (
                    "pytest", "run tests", "failing test", "tests pass",
                    "test suite", "pass all tests", "all tests", "tests must pass",
                    "pass the supplied", "subprocess tests",
                )
            )
            if test_manifest and test_task:
                return True
            security_manifest = any(
                marker in manifest_text
                for marker in ("bandit", "security scan", "security-audit", "vulnerability")
            )
            security_task = any(
                marker in task_text
                for marker in ("security", "vulnerability", "path traversal", "injection")
            )
            if security_manifest and security_task:
                return True
            runner_manifest = any(
                marker in manifest_text
                for marker in ("script runner", "execute_python", "python_script_runner")
            )
            runner_task = any(
                marker in task_text
                for marker in ("execute the script", "run the script", "run python", "execute code")
            )
            if runner_manifest and runner_task:
                return True
            return False
        if runtime == "shell_script":
            return any(marker in manifest_text for marker in ("latex", "pdflatex", "deterministic-latex")) and any(
                marker in task_text for marker in ("latex", "pdflatex", "tex source", "tex file", "document compilation")
            )
        if "sql" in task_text and any(
            marker in manifest_text
            for marker in ("sqlglot", "sql dialect", "dialect transpilation", "transpile")
        ) and any(
            marker in task_text for marker in ("transpile", "translate", "source dialect", "target dialect")
        ):
            return True
        if not markers or not any(marker in task_text for marker in markers):
            return False
        if runtime == "python_library" and "pdf" in task_text:
            if not any(marker in manifest_text for marker in ("pdf", "pdfplumber", "pypdf")):
                return False
            if any(marker in manifest_text for marker in ("extract", "preview", "page")):
                return True
        # Resolve unambiguous operation anchors before negative-intent checks.
        # Otherwise a tree request can share generic words such as
        # ``directory`` with the manifest's "list immediate entries" negative
        # example and be rejected incorrectly.
        if runtime == "mcp_server" and any(
            marker in manifest_text for marker in ("directory-tree", "recursive_directory_traversal", "directory_tree_generation")
        ) and any(marker in task_text for marker in ("recursive", "directory tree", "tree structure", '\u9012\u5f52', '\u76ee\u5f55\u6811')):
            return True
        if runtime == "mcp_server" and any(
            marker in manifest_text for marker in ("filesystem-discovery", "list_directory", "list immediate directory")
        ) and any(marker in task_text for marker in ("list the direct contents", "immediate directory entries", '\u5217\u51fa', '\u76f4\u63a5\u5185\u5bb9')):
            return True
        if runtime == "mcp_server" and "metadata" in manifest_text and any(
            marker in task_text for marker in ("metadata", "attributes", "timestamps")
        ):
            return True
        if runtime == "mcp_server" and any(
            marker in manifest_text
            for marker in ("file-search", "content-search", "search_files_by_pattern", "find_matching_content")
        ) and any(marker in task_text for marker in ("search", "grep", "pattern", '\u5339\u914d', '\u641c\u7d22')):
            return True
        task_tokens = {
            token for token in re.findall(r"[a-z0-9_\-]+|[\u4e00-\u9fff]+", task_text)
            if len(token) > 1
        }
        for negative in negative_intents:
            negative_tokens = {
                token for token in re.findall(r"[a-z0-9_\-]+|[\u4e00-\u9fff]+", str(negative).lower())
                if len(token) > 1
            }
            negative_overlap = task_tokens & negative_tokens
            if negative_tokens and (
                len(negative_overlap) >= 2
                and len(negative_overlap) / len(negative_tokens) >= 0.25
            ):
                return False
        if any(str(negative).lower() in task_text for negative in negative_intents):
            return False
        # Generic words such as ``api``, ``metadata`` and ``search`` occur in
        # many otherwise unrelated manifests.  They are routing context, not a
        # domain discriminator.  Require a distinctive manifest token before a
        # concrete runtime tool can displace model/agent candidates.
        routing_stopwords = {
            "api", "rest", "http", "https", "endpoint", "data", "information",
            "metadata", "lookup", "look", "up", "retrieve", "query", "search",
            "find", "get", "return", "result", "results", "read", "inspect",
            "file", "files", "directory", "directories", "local", "one", "named",
            "provider", "object", "shared", "json", "envelope", "output",
            "reference", "python", "library", "code", "source", "test", "tests",
            "testing",
        }
        distinctive_task_tokens = task_tokens - routing_stopwords
        distinctive_manifest_tokens = {
            token
            for token in re.findall(r"[a-z0-9_\-]+|[\u4e00-\u9fff]+", manifest_text)
            if len(token) > 1 and token not in routing_stopwords
        }
        overlap = distinctive_task_tokens & distinctive_manifest_tokens
        if runtime == "rest_api":
            # REST is an execution family, not a domain.  A concrete API may
            # be selected only when the task names one of its domain anchors;
            # words like metadata/file must never route a filesystem task to a
            # food, weather, or finance endpoint.
            domain_anchors = {
                token
                for token in [*map(str, domains), *map(str, primitives)]
                for token in re.findall(r"[a-z0-9_\-]+|[\u4e00-\u9fff]+", token.lower())
                if len(token) >= 4 and token not in routing_stopwords
            }
            return bool(overlap & domain_anchors)
        if runtime == "mcp_server":
            # Keep MCP operations separated inside the shared server family.
            # A Git mutation tool must not satisfy a filesystem inspection
            # request merely because both mention paths/files.
            git_manifest = bool({"git", "repository", "worktree", "commit", "staged"} & distinctive_manifest_tokens)
            git_task = bool({"git", "repository", "worktree", "commit", "staged"} & distinctive_task_tokens)
            if git_manifest and not git_task:
                return False
            if any(
                marker in manifest_text
                for marker in ("read several named files", "multiple source files", "read_multiple")
            ) and any(
                marker in task_text
                for marker in ("supplied files", "source files", "multiple files")
            ):
                return True
            mutation_manifest = bool(
                {"edit", "write", "delete", "remove", "move", "create", "add", "replace", "rename"}
                & distinctive_manifest_tokens
            )
            inspection_task = bool(
                {"read", "inspect", "list", "search", "metadata", "tree", "recursive"}
                & task_tokens
            )
            mutation_task = bool(
                {"edit", "write", "delete", "remove", "move", "create", "add", "replace", "rename"}
                & task_tokens
            )
            if mutation_manifest and inspection_task and not mutation_task:
                return False
            if "metadata" in manifest_text and any(
                marker in task_text for marker in ("metadata", "attributes", "size", "timestamps", "type")
            ):
                return True
            if any(marker in manifest_text for marker in ("read_text_file", "file-reading", "file contents")) and any(
                marker in task_text for marker in ("read", "contents", "content")
            ):
                return True
            if any(marker in manifest_text for marker in ("directory-tree", "recursive_directory_traversal", "directory_tree_generation")) and any(
                marker in task_text for marker in ("recursive", "directory tree", "tree structure", '\u9012\u5f52', '\u76ee\u5f55\u6811')
            ):
                return True
        return bool(overlap)

    def _runtime_intent_specificity(self, subtask: Subtask, ref: TypedResourceRef) -> float:
        raw = self.resource_index.get(ref.resource_id, {})
        routing = raw.get("routing", {}) if isinstance(raw, dict) else {}
        tags = routing.get("intent_tags", []) if isinstance(routing, dict) else []
        task_tokens = {
            token for token in re.findall(r"[a-z0-9_\-]+|[\u4e00-\u9fff]+", self._subtask_text(subtask))
            if len(token) > 1
        }
        return max(
            (
                len(task_tokens & {
                    token for token in re.findall(r"[a-z0-9_\-]+|[\u4e00-\u9fff]+", str(tag).lower())
                    if len(token) > 1
                }) / max(len(str(tag).split()), 1)
                for tag in tags
            ),
            default=0.0,
        )

    def _runtime_intent_slot(self, subtask: Subtask, ref: TypedResourceRef) -> str:
        """Return a coarse execution slot without naming a concrete resource."""

        raw = self.resource_index.get(ref.resource_id, {})
        execution = raw.get("execution", {}) if isinstance(raw, dict) else {}
        routing = raw.get("routing", {}) if isinstance(raw, dict) else {}
        runtime = str(execution.get("runtime") or "unknown").lower()
        family = str(routing.get("family") or "").lower()
        capability = raw.get("capability", {}) if isinstance(raw, dict) else {}
        blob = " ".join(
            [
                ref.resource_id,
                family,
                str(capability.get("summary") or ""),
                *map(str, routing.get("intent_tags", []) or []),
            ]
        ).lower()
        if any(marker in blob for marker in ("pytest", "test runner", "test-execution")):
            return "test_execution"
        if any(marker in blob for marker in ("security scan", "security-audit", "bandit")):
            return "security_analysis"
        if any(marker in blob for marker in ("read file", "file-reading", "file contents")):
            return "file_read"
        if "pdf" in blob and any(marker in blob for marker in ("extract", "preview", "page")):
            return "pdf_extract"
        if "sql" in blob and any(marker in blob for marker in ("dialect", "transpil", "sqlglot")):
            return "sql_transpile"
        if any(marker in blob for marker in ("execute script", "script runner", "execute_python")):
            return "code_execution"
        # The Manifest family is descriptive evidence, not a deduplication
        # key. It is used only to avoid reserving two identical runtime intents.
        return f"{runtime}:{family or 'general'}"

    def _family_id(self, resource_id: str) -> str:
        raw = self.resource_index.get(resource_id, {})
        routing = raw.get("routing", {}) if isinstance(raw, dict) else {}
        family_id = routing.get("family_id")
        if family_id:
            return str(family_id)
        # Absence of an explicit semantic family means the resource is unique.
        # Vendor/namespace prefixes do not imply substitutability.
        return resource_id

    def _family_dedup_exception(
        self,
        ref: TypedResourceRef,
        selected: Sequence[TypedResourceRef],
        subtask: Subtask,
    ) -> bool:
        """Allow same-family resources when they cover materially different I/O or roles."""
        raw = self.resource_index.get(ref.resource_id, {})
        output = self._manifest_output_artifact(raw)
        inputs = {
            str(item.get("name"))
            for item in self._manifest_input_contracts(raw)
            if item.get("name")
        }
        for existing in selected:
            if existing.resource_type != ref.resource_type:
                continue
            if self._family_id(existing.resource_id) != self._family_id(ref.resource_id):
                continue
            existing_raw = self.resource_index.get(existing.resource_id, {})
            existing_output = self._manifest_output_artifact(existing_raw)
            existing_inputs = {
                str(item.get("name"))
                for item in self._manifest_input_contracts(existing_raw)
                if item.get("name")
            }
            if output and existing_output and output != existing_output:
                return True
            if inputs and existing_inputs and inputs != existing_inputs:
                return True
            if self._role_matches_subtask(subtask, ref) and not self._role_matches_subtask(subtask, existing):
                return True
        return False

    def _ensure_minimum_executable_coverage(
        self,
        subtask: Subtask,
        selected: List[TypedResourceRef],
        scored: Sequence[Tuple[float, TypedResourceRef]],
    ) -> List[TypedResourceRef]:
        """Keep at least one intelligent finalizer and useful tool when available."""
        selected_ids = {ref.resource_id for ref in selected}
        has_model_or_agent = any(ref.resource_type in {ManifestType.MODEL, ManifestType.AGENT} for ref in selected)
        has_tool = any(ref.resource_type == ManifestType.TOOL for ref in selected)

        def add_first(predicate) -> None:
            nonlocal selected_ids
            for _, candidate in scored:
                if candidate.resource_id in selected_ids:
                    continue
                if predicate(candidate):
                    selected.append(candidate)
                    selected_ids.add(candidate.resource_id)
                    break

        if not has_model_or_agent:
            add_first(lambda ref: ref.resource_type in {ManifestType.MODEL, ManifestType.AGENT})
        if not has_tool:
            add_first(lambda ref: ref.resource_type == ManifestType.TOOL)

        text = f"{subtask.description}\n{subtask.expected_output}".lower()
        if any(marker in text for marker in ("execute", "run", '\u6267\u884c', '\u8fd0\u884c', "script", "code")):
            add_first(
                lambda ref: ref.resource_type == ManifestType.TOOL
                and "execute_script" in tool_allowed_operation_kinds(
                    self.resource_index.get(ref.resource_id, {})
                )
            )
        # Preserve at least one concrete runtime tool for an API/MCP request;
        # a model is allowed to synthesize a report, but not to replace the
        # requested side effect/query with generic code generation.
        add_first(lambda ref: self._runtime_intent_match(subtask, ref))
        return selected

    def _resource_family_label(self, resource_id: str) -> str:
        return self._family_id(resource_id)

    def _manifest_input_contracts(self, raw: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not isinstance(raw, dict):
            return []
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
        if not isinstance(raw, dict):
            return {}
        output_contract = raw.get("output_contract")
        if isinstance(output_contract, dict):
            return output_contract
        output_contract = raw.get("io", {}).get("output_contract")
        if isinstance(output_contract, dict):
            return output_contract
        return {}

    def _manifest_output_artifact(self, raw: Dict[str, Any]) -> Optional[str]:
        if not isinstance(raw, dict):
            return None
        output_contract = self._manifest_output_contract(raw)
        artifact = output_contract.get("artifact_type")
        if artifact:
            return str(artifact)
        return None

    def _contract_kind(self, contract: Dict[str, Any]) -> str:
        return normalize_contract_kind(contract)

    def _artifact_type_from_value(self, value: Optional[str]) -> Optional[ArtifactType]:
        if not value:
            return None
        try:
            return ArtifactType(str(value))
        except ValueError:
            return None

    def _infer_execution_mode(self, selected: Sequence[TypedResourceRef]) -> ExecutionMode:
        types = {r.resource_type for r in selected}
        if ManifestType.TOOL in types and ManifestType.MODEL not in types and ManifestType.AGENT not in types:
            return ExecutionMode.BYPASS
        if ManifestType.MODEL in types or ManifestType.AGENT in types or selected:
            return ExecutionMode.SEMI_GENERATIVE
        return ExecutionMode.FULL_GENERATIVE

    def _dedupe_refs(self, refs: Sequence[TypedResourceRef]) -> List[TypedResourceRef]:
        seen: set[str] = set()
        deduped: List[TypedResourceRef] = []
        for ref in refs:
            if ref.resource_id in seen:
                continue
            seen.add(ref.resource_id)
            deduped.append(ref)
        return deduped

    def _manifest_by_id(self, resource_id: str, library: List[Manifest]) -> Optional[Manifest]:
        return next((m for m in library if m.id == resource_id), None)

    def _model_api_id_from_raw(self, raw: Dict[str, Any]) -> Optional[str]:
        if not isinstance(raw, dict):
            return None
        type_specific = raw.get("type_specific", {})
        model_block = type_specific.get("model", {}) if isinstance(type_specific, dict) else {}
        execution = raw.get("execution", {}) if isinstance(raw.get("execution", {}), dict) else {}
        return (
            model_block.get("model_id")
            or execution.get("model_id")
            or execution.get("default_base_model")
        )

    def _manifest_model_api_id(self, manifest: Manifest) -> Optional[str]:
        if manifest.type != ManifestType.MODEL:
            return None
        raw = self.resource_index.get(manifest.id, {})
        return self._model_api_id_from_raw(raw) or manifest.id

    def _manifest_by_id_or_model_id(
        self, resource_id_or_model_id: str, library: List[Manifest]
    ) -> Optional[Manifest]:
        if not resource_id_or_model_id:
            return None
        exact = self._manifest_by_id(resource_id_or_model_id, library)
        if exact is not None:
            return exact
        needle = str(resource_id_or_model_id)
        for manifest in library:
            if manifest.type != ManifestType.MODEL:
                continue
            if self._manifest_model_api_id(manifest) == needle:
                return manifest
        return None

    def _ref_from_resource_id(
        self, resource_id: str, library: List[Manifest]
    ) -> Optional[TypedResourceRef]:
        manifest = self._manifest_by_id_or_model_id(resource_id, library)
        if manifest is not None:
            return self._ref_from_manifest(manifest)
        raw = self.resource_index.get(resource_id)
        if raw is None:
            return None
        resource_type = self._coerce_manifest_type(
            raw.get("type", {}).get("resource_type") or raw.get("resource_type")
        )
        if resource_type is None:
            return None
        return TypedResourceRef(
            resource_id=resource_id,
            resource_type=resource_type,
            base_model=self._default_base_model(resource_id, resource_type),
        )

    def _ref_from_manifest(
        self, manifest: Manifest, similarity: Optional[float] = None
    ) -> TypedResourceRef:
        return TypedResourceRef(
            resource_id=manifest.id,
            resource_type=manifest.type,
            base_model=self._default_base_model(manifest.id, manifest.type),
            similarity=similarity,
            advantage_score=manifest.advantage_score,
        )

    def _default_base_model(self, resource_id: str, resource_type: ManifestType) -> Optional[str]:
        raw = self.resource_index.get(resource_id, {})
        if resource_type == ManifestType.MODEL:
            return self._model_api_id_from_raw(raw) or resource_id
        return None

    def _coerce_manifest_type(self, value: Any) -> Optional[ManifestType]:
        if isinstance(value, ManifestType):
            return value
        if value is None:
            return None
        normalized = {
            "model": ManifestType.MODEL,
            "generative_model": ManifestType.MODEL,
            "agent": ManifestType.AGENT,
            "mas": ManifestType.AGENT,
            "multiagent": ManifestType.AGENT,
            "multiagent_system": ManifestType.AGENT,
            "multi_agent_system": ManifestType.AGENT,
            "skill": ManifestType.SKILL,
            "tool": ManifestType.TOOL,
            "physical_tool": ManifestType.TOOL,
            "resource": ManifestType.RESOURCE,
            "device": ManifestType.DEVICE,
        }.get(str(value).strip().lower())
        if normalized is not None:
            return normalized
        try:
            return ManifestType(str(value))
        except ValueError:
            return None

    def _normalized_utility(
        self, ref: TypedResourceRef, library: List[Manifest]
    ) -> Tuple[float, float, float]:
        manifest = self._manifest_by_id_or_model_id(ref.resource_id, library)
        if manifest is None and ref.resource_type == ManifestType.AGENT and ref.base_model:
            manifest = self._manifest_by_id_or_model_id(ref.base_model, library)
        if manifest is None:
            return self.unknown_success_rate, self.cost_floor, self.latency_floor_ms

        success = manifest.utility.success_rate
        cost = manifest.utility.cost_factor
        latency = manifest.utility.latency_ms
        if success <= 0:
            success = self.unknown_success_rate
        if cost <= 0:
            cost = self.cost_floor
        if latency <= 0:
            latency = self.latency_floor_ms
        return min(max(success, 0.01), 1.0), max(cost, self.cost_floor), max(latency, self.latency_floor_ms)

    def _baseline_efficiency(self, library: List[Manifest]) -> Tuple[float, bool]:
        baseline = self._manifest_by_id_or_model_id(self.baseline_model_id, library)
        baseline_missing = baseline is None
        if baseline is None:
            model_candidates = [m for m in library if m.type == ManifestType.MODEL]
            baseline = model_candidates[0] if model_candidates else None
        if baseline is None:
            return 1.0, True
        success = baseline.utility.success_rate if baseline.utility.success_rate > 0 else 0.75
        cost = baseline.utility.cost_factor if baseline.utility.cost_factor > 0 else 5.0
        latency = baseline.utility.latency_ms if baseline.utility.latency_ms > 0 else 30000.0
        efficiency = success / ((cost + self.epsilon) * math.log10(10 + latency))
        return efficiency, baseline_missing
