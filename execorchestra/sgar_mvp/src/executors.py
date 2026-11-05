"""
S-GAR Execution Layer — Executors
==================================
Physical execution nodes that process individual subtasks.

- DumbExecutor:  BYPASS_MODE — runs local scripts in a sandboxed subprocess.
- SmartExecutor: GENERATIVE_MODE — invokes LLM API with streaming, retry,
                 artifact-type-aware prompting, and output pre-cleaning.
"""

from sgar_mvp.src.direct_network import (
    direct_async_http_client, direct_environment, direct_container_environment_args,
    load_tool_proxy_config, tool_proxy_audit, tool_proxy_environment,
)

import re
import os
import sys
import asyncio
import time
import traceback
import shlex
import hashlib
import json
import posixpath
import copy
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable, Mapping, Sequence

from pydantic import BaseModel, Field
from openai import (
    AsyncOpenAI,
)
from loguru import logger

from .schema import ArtifactType, TypedResourceRef
from .runtime_abstraction import require_legacy_runtime
from .capability_registry import GLOBAL_CAPABILITY_REGISTRY
from .public_inputs import (
    InternalMetadataLayoutError,
    inspect_internal_metadata_layout,
    validate_internal_metadata_scope,
    verify_public_input_path,
)
from .model_accounting import (
    AccountingPersistenceError,
    BudgetControlError,
    ModelCallContext,
    PricingCatalogError,
    RunCostLedger,
)
from .model_transport import (
    AsyncModelTransportPort,
    ModelTransportError,
    ProviderEndpointIdentity,
    classify_transport_exception,
    require_async_model_transport,
)
from .model_request_budget import (
    ModelAttemptTimeout, ModelTimeBudgetError, model_attempts_remaining,
    require_retry_time,
)
from .model_response_contracts import (
    normalize_portable_wire_instance,
    project_portable_wire_schema,
    structured_response_format_from_contract,
    strict_json_loads,
    validate_json_schema_instance,
)
from .pipeline_control import canonical_json_bytes, canonical_sha256
from .terminal_failure import TerminalFailureEnvelope
from .path_namespace import RuntimePathMap
from .internal_language import INTERNAL_LANGUAGE_POLICY
from .model_media import compose_model_user_content
from .process_supervisor import (
    DockerCallIdentity,
    DockerProcessSupervisor,
    MAX_NORMAL_TIMEOUT_SECONDS,
    NetworkExecutionPolicy,
    ProcessCapturePolicy,
    ProcessOutputLimitExceeded,
    ProcessSupervisionError,
    sanitize_diagnostic,
)
from .tool_proxy_relay import ToolProxyRelayError, bridge_loopback_tool_proxies


TRANSPORT_RETRY_PROTOCOL = "same-request-initial-plus-2-v1"
AGENT_EXECUTOR_SYSTEM_PROMPT = (
    "You are the S-GAR prompt-agent runtime. Follow the Agent Card supplied as typed "
    "user data, but use only runtime inputs explicitly bound by the sealed plan. Agent "
    "Card dependency names are compatibility hints, not proof that a dependency ran. "
    "Never claim a Tool ran unless its actual result is present in bound inputs. Preserve "
    "source content and literal identifiers exactly, follow the declared artifact delivery "
    "language, and output only the requested artifact."
)


def _json_contract_requires_object(contract: dict[str, Any]) -> bool:
    """Use object-only JSON mode only when the declared root requires an object.

    This is a conservative transport choice, not a replacement for instance
    validation. Unknown roots and unions keep their full JSON value contract.
    Local references use the same root document as the output validator.
    """
    root = contract.get("schema_hint")
    if not isinstance(root, dict):
        return False

    def requires_object(node: Any, refs: frozenset[str] = frozenset()) -> bool:
        if not isinstance(node, dict):
            return False
        if "$ref" in node:
            ref = node["$ref"]
            if not isinstance(ref, str) or not ref.startswith("#/") or ref in refs:
                return False
            target: Any = root
            for part in ref[2:].split("/"):
                key = part.replace("~1", "/").replace("~0", "~")
                if not isinstance(target, dict) or key not in target:
                    return False
                target = target[key]
            return requires_object(target, refs | {ref})
        declared = node.get("type")
        if declared == "object" or declared == ["object"]:
            return True
        for keyword in ("anyOf", "oneOf"):
            alternatives = node.get(keyword)
            if isinstance(alternatives, list) and alternatives and all(
                requires_object(item, refs) for item in alternatives
            ):
                return True
        conjunction = node.get("allOf")
        return isinstance(conjunction, list) and any(
            requires_object(item, refs) for item in conjunction
        )

    return requires_object(root)


def _validated_format_enforcement(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("format_enforcement_must_be_object")
    projected = copy.deepcopy(value)
    supplied = str(projected.pop("format_contract_sha256", ""))
    if supplied != canonical_sha256(projected):
        raise ValueError("format_enforcement_contract_sha256_mismatch")
    mode = str(value.get("selected_enforcement_mode") or "")
    if mode not in {"native_strict_schema", "json_object_local_validator"}:
        raise ValueError("format_enforcement_mode_invalid")
    schema = value.get("schema")
    if not isinstance(schema, dict) or not schema:
        raise ValueError("format_enforcement_schema_missing")
    if mode == "native_strict_schema":
        wire_schema = value.get("wire_schema")
        if not isinstance(wire_schema, dict) or not wire_schema:
            raise ValueError("format_enforcement_wire_schema_missing")
        if str(value.get("wire_schema_sha256") or "") != canonical_sha256(wire_schema):
            raise ValueError("format_enforcement_wire_schema_hash_mismatch")
    return copy.deepcopy(value)


def _apply_format_enforcement(
    api_kwargs: Dict[str, Any],
    enforcement: dict[str, Any],
) -> None:
    mode = str(enforcement["selected_enforcement_mode"])
    api_kwargs["stream"] = False
    api_kwargs["response_format"] = structured_response_format_from_contract(
        mode=mode,
        requirement_sha256=str(enforcement.get("requirement_sha256") or ""),
        wire_schema=enforcement.get("wire_schema"),
        wire_schema_sha256=enforcement.get("wire_schema_sha256"),
    )


def _validate_enforced_output(
    content: str,
    enforcement: dict[str, Any] | None,
) -> tuple[bool, str | None]:
    if enforcement is None:
        return True, None
    try:
        parsed = strict_json_loads(content)
    except (ValueError, json.JSONDecodeError):
        return False, "$:json_parse"
    if str(enforcement.get("selected_enforcement_mode")) == "native_strict_schema":
        parsed = normalize_portable_wire_instance(parsed, enforcement["schema"])
    return validate_json_schema_instance(parsed, enforcement["schema"])


def _normalize_enforced_root_value(content: str, enforcement: dict[str, Any] | None) -> str:
    """Publish the task value, never its provider-only root envelope."""
    if enforcement is None:
        return content
    if enforcement.get("serialization_format") == "jsonl":
        value = strict_json_loads(content)
        if enforcement["selected_enforcement_mode"] == "native_strict_schema":
            value = normalize_portable_wire_instance(value, enforcement["schema"])
        from .json_serialization import serialize_json_lines
        return serialize_json_lines(value, enforcement["schema"])
    if enforcement["selected_enforcement_mode"] != "native_strict_schema":
        return content
    projection = project_portable_wire_schema(enforcement["schema"])
    if "root_value_enveloped" not in projection.reason_codes:
        return content
    parsed = strict_json_loads(content)
    normalized = normalize_portable_wire_instance(parsed, enforcement["schema"])
    if normalized == parsed:
        return content
    return canonical_json_bytes(normalized).decode("utf-8")


def _request_hash(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _retryable_transport_exception(exc: BaseException) -> tuple[bool, str]:
    """Backward-compatible alias for the shared structured classifier."""

    return classify_transport_exception(exc)


def _transport_audit(
    *,
    request_hashes: List[str],
    provenance_hashes: List[str],
    retry_responsibilities: List[str],
    response_received: bool,
) -> Dict[str, Any]:
    passed = (
        0 <= len(request_hashes) <= 3
        and len(set(request_hashes)) <= 1
        and len(provenance_hashes) in {0, len(request_hashes)}
        and len(set(provenance_hashes)) <= 1
        and len(retry_responsibilities) == max(0, len(request_hashes) - 1)
        and all(item == "infrastructure" for item in retry_responsibilities)
    )
    return {
        "status": "checked",
        "passed": passed,
        "protocol": TRANSPORT_RETRY_PROTOCOL,
        "attempt_count": len(request_hashes),
        "request_hashes": list(request_hashes),
        "provenance_hashes": list(provenance_hashes),
        "retry_responsibilities": list(retry_responsibilities),
        "response_received": bool(response_received),
    }


def _failure_record(
    *,
    failure_stage: str,
    responsibility: str,
    retryable: bool,
    transport_attempt: int,
    request_hash: str,
    response_received: bool,
    failure_type: str,
) -> Dict[str, Any]:
    """Build the executor failure contract without interpreting error text."""

    return {
        "failure_stage": failure_stage,
        "failure_origin": failure_stage,
        "responsibility": responsibility,
        "retryable": bool(retryable),
        "transport_attempt": int(transport_attempt),
        "request_hash": str(request_hash),
        "response_received": bool(response_received),
        "failure_type": str(failure_type),
        "stack_fingerprint_sha256": canonical_sha256(
            {
                "failure_origin": failure_stage,
                "responsibility": responsibility,
                "failure_type": str(failure_type),
            }
        ),
    }


def _secondary_audit_failure(
    *,
    failure_origin: str,
    failure_code: str,
    error: BaseException,
) -> Dict[str, Any]:
    return {
        "responsibility": "framework",
        "failure_origin": str(failure_origin),
        "failure_code": str(failure_code),
        "stack_fingerprint_sha256": canonical_sha256(
            {
                "failure_origin": str(failure_origin),
                "failure_code": str(failure_code),
                "exception_type": type(error).__name__,
            }
        ),
    }


def _safe_capability_error_audit(
    model_id: str,
    failure_type: str,
    message: str,
) -> List[Dict[str, Any]]:
    try:
        GLOBAL_CAPABILITY_REGISTRY.record_error(model_id, failure_type, message)
    except Exception as exc:
        return [
            _secondary_audit_failure(
                failure_origin="capability_registry",
                failure_code="capability_registry_record_error_failed",
                error=exc,
            )
        ]
    return []


class _TransportRequestFailure(RuntimeError):
    def __init__(
        self,
        original: BaseException,
        *,
        audit: Dict[str, Any],
        failure: Dict[str, Any],
        accounting_reference: Optional[Dict[str, Any]] = None,
        secondary_audit_failures: Sequence[Dict[str, Any]] = (),
    ) -> None:
        super().__init__(str(original))
        self.original = original
        self.audit = audit
        self.failure = failure
        self.accounting_reference = accounting_reference
        self.secondary_audit_failures = tuple(
            dict(item) for item in secondary_audit_failures
        )


def _guard_model_payload(
    guard: Optional[Callable[[Dict[str, Any]], Any]],
    payload: Dict[str, Any],
) -> None:
    """Run a fail-closed guard against a copy of the exact provider payload."""

    if guard is None:
        return
    result = guard(copy.deepcopy(payload))
    if result is False:
        raise ValueError("model payload guard rejected the request")
    if isinstance(result, dict) and result.get("passed") is not True:
        raise ValueError("model payload guard did not return passed=true")


async def _request_with_transport_retry(
    transport: AsyncModelTransportPort,
    api_kwargs: Dict[str, Any],
    *,
    max_attempts: int,
    model_payload_guard: Optional[Callable[[Dict[str, Any]], Any]] = None,
    cost_ledger: Optional[RunCostLedger] = None,
    accounting_context: Optional[ModelCallContext] = None,
) -> tuple[Any, Dict[str, Any]]:
    """Issue one immutable model request with transport-only retries.

    A retry is permitted only when no model response was returned and the
    provider exception has an explicit transport type or retryable HTTP status.
    Compatibility, schema, truncation, and all other semantic recovery belongs
    outside this transport boundary and therefore never changes the request.
    """

    frozen_payload = copy.deepcopy(api_kwargs)
    expected_hash = _request_hash(frozen_payload)
    request_hashes: List[str] = []
    provenance_hashes: List[str] = []
    retry_responsibilities: List[str] = []
    attempts = max(1, min(3, int(max_attempts or 1)))

    for attempt in range(1, attempts + 1):
        attempt_payload = copy.deepcopy(frozen_payload)
        current_hash = _request_hash(attempt_payload)
        if current_hash != expected_hash:
            audit = _transport_audit(
                request_hashes=request_hashes,
                provenance_hashes=provenance_hashes,
                retry_responsibilities=retry_responsibilities,
                response_received=False,
            )
            failure = _failure_record(
                failure_stage="downstream_model_request",
                responsibility="framework",
                retryable=False,
                transport_attempt=len(request_hashes),
                request_hash=expected_hash,
                response_received=False,
                failure_type="transport_request_changed",
            )
            raise _TransportRequestFailure(
                RuntimeError("transport request changed between attempts"),
                audit=audit,
                failure=failure,
            )

        try:
            # The guard runs for every actual provider attempt.  It receives a
            # copy so it cannot mutate the request that is sent or retried.
            _guard_model_payload(model_payload_guard, attempt_payload)
        except Exception as exc:
            audit = _transport_audit(
                request_hashes=request_hashes,
                provenance_hashes=provenance_hashes,
                retry_responsibilities=retry_responsibilities,
                response_received=False,
            )
            failure = _failure_record(
                failure_stage="model_payload_guard",
                responsibility="framework",
                retryable=False,
                transport_attempt=len(request_hashes),
                request_hash=expected_hash,
                response_received=False,
                failure_type="model_payload_guard_failed",
            )
            raise _TransportRequestFailure(exc, audit=audit, failure=failure) from exc

        request_hashes.append(current_hash)
        provenance_hash = str(
            getattr(model_payload_guard, "provenance_hash", "") or ""
        )
        if provenance_hash:
            provenance_hashes.append(provenance_hash)
        try:
            # Do not use the compatibility helper here: that helper can issue a
            # second, modified request after a provider capability rejection.
            with model_attempts_remaining(attempts - attempt + 1):
                response = await transport.send(
                    ledger=cost_ledger,
                    context=accounting_context,
                    **attempt_payload,
                )
        except Exception as exc:
            if isinstance(exc, BudgetControlError):
                retryable, failure_type = False, str(exc.error_code)
                explicit_responsibility = "budget"
            elif isinstance(
                exc,
                (AccountingPersistenceError, PricingCatalogError, ModelTransportError),
            ):
                retryable, failure_type = False, type(exc).__name__
                explicit_responsibility = "framework"
            else:
                retryable, failure_type = _retryable_transport_exception(exc)
                explicit_responsibility = None
            # An attempt deadline means the provider may still have consumed
            # the complete request and its billing is unknown.  Repeating the
            # identical long-running request hides the structured failure from
            # plan recovery and can multiply both latency and exposure.  Let
            # the recovery controller choose another frozen candidate instead.
            # Short transport faults such as 429/503 remain eligible for the
            # bounded same-request retry policy below.
            same_request_retryable = (
                retryable and not isinstance(exc, ModelAttemptTimeout)
            )
            if (
                same_request_retryable
                and attempt < attempts
                and not (cost_ledger is not None and cost_ledger.is_exhausted)
            ):
                delay = min(5, 2 ** (attempt - 1))
                try:
                    require_retry_time(delay)
                except ModelTimeBudgetError as budget_exc:
                    exc = budget_exc
                    retryable, failure_type = False, budget_exc.error_code
                    explicit_responsibility = "budget"
                else:
                    retry_responsibilities.append("infrastructure")
                    await asyncio.sleep(delay)
                    continue

            responsibility = explicit_responsibility or (
                "infrastructure" if retryable else "framework"
            )
            audit = _transport_audit(
                request_hashes=request_hashes,
                provenance_hashes=provenance_hashes,
                retry_responsibilities=retry_responsibilities,
                response_received=False,
            )
            failure = _failure_record(
                failure_stage="downstream_model_transport",
                responsibility=responsibility,
                # This is the terminal branch: either the error was never
                # retryable or the fixed initial-plus-two budget is exhausted.
                retryable=False,
                transport_attempt=len(request_hashes),
                request_hash=expected_hash,
                response_received=False,
                failure_type=failure_type,
            )
            accounting_reference: Optional[Dict[str, Any]] = None
            secondary_audit_failures: List[Dict[str, Any]] = []
            if cost_ledger is not None and accounting_context is not None:
                try:
                    accounting_reference = cost_ledger.operation_reference(
                        accounting_context.operation_id
                    )
                except Exception as audit_exc:
                    secondary_audit_failures.append(
                        _secondary_audit_failure(
                            failure_origin="model_accounting_projection",
                            failure_code="model_accounting_reference_failed",
                            error=audit_exc,
                        )
                    )
            raise _TransportRequestFailure(
                exc,
                audit=audit,
                failure=failure,
                accounting_reference=accounting_reference,
                secondary_audit_failures=secondary_audit_failures,
            ) from exc

        return response, _transport_audit(
            request_hashes=request_hashes,
            provenance_hashes=provenance_hashes,
            retry_responsibilities=retry_responsibilities,
            response_received=True,
        )

    raise AssertionError("transport retry loop must return or raise")


# ─────────────────────────────────────────────
# Execution Result Contract
# ─────────────────────────────────────────────

class ExecutionResult(BaseModel):
    """Standardized result returned by all executor types."""
    is_success: bool = Field(..., description="Whether execution succeeded")
    output_data: str = Field(..., description="Clean artifact content")
    error_log: Optional[str] = Field(None, description="Error trace if failed")
    cost_metric: Dict[str, Any] = Field(
        default_factory=dict, description="Metrics (latency_ms, tokens, etc.)"
    )


# ─────────────────────────────────────────────
# Prompt Management
# ─────────────────────────────────────────────

_PROMPT_DIR = os.path.join(os.path.dirname(__file__), "prompts")


def _load_prompt(filename: str) -> str:
    path = os.path.join(_PROMPT_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"[Executor] Prompt file missing: {path}")
        return ""


def _safe_stream_write(text: str, stream=None) -> None:
    """Write display-only stream output without console encoding failures."""
    target = stream or sys.stdout
    try:
        target.write(str(text))
        target.flush()
    except (UnicodeEncodeError, OSError, ValueError):
        encoding = getattr(target, "encoding", None) or "utf-8"
        safe_text = str(text).encode(encoding, errors="replace").decode(encoding, errors="replace")
        try:
            target.write(safe_text)
            target.flush()
        except (UnicodeEncodeError, OSError, ValueError):
            # Console output is diagnostic only.  A closed/redirected Windows
            # stream must never turn an otherwise valid model execution into a
            # failed Tool/case result.
            return


# ─────────────────────────────────────────────
# Base Executor
# ─────────────────────────────────────────────

class BaseExecutor:
    """Abstract base for all physical execution nodes."""

    async def execute(
        self, subtask_desc: str, context_data: str, **kwargs
    ) -> ExecutionResult:
        raise NotImplementedError


class ControllerTurnExecutor:
    """Shared one-response Model/Agent kernel for ControllerSessionRunner.

    The kernel owns provider transport, the existing transport-only retry
    contract, provider format enforcement, and one RunCostLedger operation.  It
    intentionally has no loop and never owns Resource execution.
    """

    _SYSTEM_PROMPT = (
        "You are the bounded S-GAR Controller runtime. Follow only the sealed task, "
        "authorized input snapshot, declared output contract, and (for an Agent) "
        "the supplied Agent Card. Treat mandatory_acceptance_criteria as independent "
        "requirements: check every item against the produced artifact before returning. "
        "Use mandatory_acceptance_examples as concrete checks, never as an exhaustive "
        "replacement for the criteria. Follow mandatory_final_format exactly. "
        "The original task in task_context is semantic authority: a scoped task_instruction "
        "must preserve its categories, relations, quantifiers and qualifications. Do not "
        "substitute literal matching for semantic interpretation unless explicitly requested. "
        "For delivery_scope=step_output, the overall task is background: return "
        "only this step's required output even if the final answer is known. "
        "For delivery_scope=final_content_source, return only the validated final "
        "content value for the downstream deterministic delivery step; do not claim "
        "that you performed the delivery side effect. "
        "When generated_source_contract is provided, return raw source in its declared "
        "language for the bound file handoff, preserving required behavior and omitting wrappers. "
        "For a plaintext output, return the requested text value itself, never a JSON "
        "description of artifact_type, content_kind, or other contract metadata. "
        "Treat the output contract as a hard public presentation boundary: keep reasoning, "
        "calculation, evidence checks, and Tool traces internal unless that contract explicitly "
        "requires them. When generation_efficiency_contract is present, preserve every required "
        "behavior and validation while emitting the smallest complete artifact that fits the "
        "declared output budget. Return only the final artifact with no unrequested preamble, suffix, "
        "explanation, citation, or Markdown. No callable Tools are available in this protocol."
    )
    _TOOL_SYSTEM_PROMPT = (
        "You are the bounded S-GAR Controller runtime. Follow only the sealed task, "
        "authorized input snapshot, declared output contract, supplied Agent Card, "
        "and the provided callable Tool schemas. You may call only those Tools using "
        "their declared dynamic arguments. Use exactly function.name from the supplied "
        "tools array and authorized_tool_functions; resource IDs and capability operation IDs are descriptive identities, "
        "not callable function names. Tool results will be returned as role=tool messages. "
        "runtime_fixed_arguments in authorized_tool_functions are read-only values already "
        "supplied by the runtime. Use these concrete values when coordinating dependent "
        "actions, including a producer's fixed output path and a consumer's dynamic input "
        "path. If the consumer's input path is fixed, write or repair that exact program "
        "path through an authorized writer; a different file does not revise that consumer. "
        "Do not guess another path or include fixed arguments in your Tool call. "
        "Treat mandatory_acceptance_criteria as independent requirements: check every "
        "item before the final response. Use mandatory_acceptance_examples as concrete "
        "checks, never as an exhaustive replacement for the criteria, and follow "
        "mandatory_final_format exactly. For delivery_scope=step_output, the "
        "original task in task_context remains semantic authority; task_instruction scopes "
        "your operation without redefining its categories, relations or qualifications. "
        "Do not substitute literal matching for semantic interpretation unless requested. The "
        "overall task is background: return only this step's required output. "
        "For delivery_scope=final_content_source, return only the validated final "
        "content value for the downstream deterministic delivery step. "
        "Check "
        "that any required file/artifact content is exactly the content you intend to return; "
        "do not claim completion from an unverified tool result. For command or runner Tools, "
        "inspect the structured status plus exit_code or return_code: a nonzero code, a false/failed "
        "status, or an inner command failure is failure evidence even when the Tool transport itself "
        "returned a result. When a shell program includes diagnostics after execution, "
        "preserve the executed program's status and distinguish its result from those "
        "diagnostics; the final shell command's success does not verify earlier commands. "
        "Repair and verify the task state before claiming completion. "
        "materialized_delivery_state is the runtime's current declared-path and file-identity "
        "observation, not a semantic verdict. When the required artifact is implemented and "
        "supported by current evidence, return the declared completion without rewriting it "
        "or adding optional checks merely to obtain another receipt. Distinguish unavailable "
        "optional self-checks from failed required operations; never claim an unavailable check "
        "passed or waive an explicitly requested test, library, invocation, or behavior. "
        "Each required_successful_tool_operation must have a successful Tool result "
        "before you return a final artifact; a failed call or a search snippet is not "
        "proof that a required source-content operation succeeded. "
        "When stateful_execution_policy is present, apply its phase_order to each "
        "execution iteration: inspect the facts needed for the next action, implement "
        "that task action, and inspect its result before revising it. Preserve source "
        "evidence still needed later; satisfy every criterion before final delivery. "
        "Use execution_budget to reserve room for implementation, verification, and "
        "a grounded final response. Once the next action is supported, proceed instead "
        "of exhausting the session on background inspection. Reuse earlier observations "
        "only while they still describe current state; later changes or contradictory "
        "results require revalidation of the affected claims. "
        "Use pending_required_tool_operations as the current evidence frontier. "
        "Observe each bounded batch before deciding the next Tool actions. "
        "When source search and fetch are both required, use search results to obtain "
        "candidate URLs and fetch a plausible source before issuing more searches. "
        "If search records are empty, broaden or reformulate the query; do not repeat "
        "the same search or exhaust the Tool budget on discovery alone. Follow any "
        "stricter Tool-call limits in task_instruction. "
        "When no Tool call is needed, follow format_instruction when supplied. "
        "If finalization_evidence_contract is present, return its internal JSON evidence "
        "envelope. All public-output instructions, including FINAL OUTPUT in task_instruction, "
        "apply only to final_output or to the validated materialized file as directed. "
        "Otherwise return the final artifact directly. For a plaintext public artifact, use the requested "
        "text value itself, never a JSON description of artifact_type, content_kind, "
        "or other contract metadata. Treat the output contract as a hard public presentation "
        "boundary: keep reasoning, calculation, evidence checks, and Tool traces internal unless "
        "that contract explicitly requires them. The public artifact must have no "
        "unrequested preamble, suffix, explanation, citation, or Markdown."
    )

    def __init__(
        self,
        *,
        transport: AsyncModelTransportPort,
        cost_ledger: Optional[RunCostLedger] = None,
        max_retries: int = 3,
        max_tokens: int = 8192,
        temperature: float = 0.3,
        model_payload_guard: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ) -> None:
        self.transport = require_async_model_transport(transport)
        self.cost_ledger = cost_ledger
        self.max_retries = max(1, min(3, int(max_retries or 1)))
        self.max_tokens = max(1, int(max_tokens))
        self.temperature = float(temperature)
        self.model_payload_guard = model_payload_guard

    @staticmethod
    def _tool_call_views(value: Any) -> tuple[dict[str, Any], ...]:
        views: list[dict[str, Any]] = []
        for index, item in enumerate(value or ()):
            if hasattr(item, "model_dump"):
                raw = item.model_dump(mode="json")
            elif isinstance(item, dict):
                raw = dict(item)
            else:
                raw = {"representation": str(type(item).__name__)}
            function = raw.get("function") if isinstance(raw, dict) else None
            arguments = (
                function.get("arguments")
                if isinstance(function, dict)
                else raw.get("arguments")
                if isinstance(raw, dict)
                else None
            )
            views.append(
                {
                    "index": index,
                    "tool_call_id": str(raw.get("id") or "") if isinstance(raw, dict) else "",
                    "name": (
                        str(function.get("name") or "")
                        if isinstance(function, dict)
                        else str(raw.get("name") or "")
                        if isinstance(raw, dict)
                        else ""
                    ),
                    # Stage B never executes or persists dynamic arguments.  A
                    # hash is sufficient to prove a non-empty unauthorized action.
                    "arguments_sha256": canonical_sha256(arguments),
                }
            )
        return tuple(views)

    async def execute_turn(self, **kwargs: Any) -> Any:
        from .controller_session import ControllerSessionSpecV2, ControllerTurnResultV1
        from .controller_tool_runtime import (
            ControllerToolRuntimeError,
            normalize_provider_tool_calls,
        )
        from .controller_tooling import project_provider_tool_schema

        started = time.perf_counter()
        spec = kwargs["spec"]
        snapshot = kwargs["snapshot"]
        turn_id = str(kwargs["turn_id"])
        turn_index = int(kwargs["turn_index"])
        controller_context = dict(kwargs.get("controller_context") or {})
        finalization_evidence_audit = bool(
            controller_context.get("controller_finalization_evidence_audit")
        )
        model_id = str(controller_context.get("provider_model_id") or "").strip()
        agent_card = controller_context.get("agent_card")
        if not model_id or (
            spec.controller_resource_type == "Agent"
            and not str(agent_card or "").strip()
        ):
            empty_sha256 = canonical_sha256("")
            return ControllerTurnResultV1(
                session_id=snapshot.session_id,
                turn_id=turn_id,
                turn_index=turn_index,
                status="failure",
                transport_audit={"status": "not_started"},
                request_sha256=canonical_sha256(
                    {
                        "session_id": snapshot.session_id,
                        "turn_id": turn_id,
                        "backing_model_resource_id": spec.backing_model_resource_id,
                    }
                ),
                response_sha256=empty_sha256,
                candidate_sha256=empty_sha256,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                failure_code="controller_backing_model_not_ready",
            )

        provider_tools = tuple(dict(item) for item in (kwargs.get("provider_tools") or ()))
        tool_session = isinstance(spec, ControllerSessionSpecV2)
        tool_enabled = bool(provider_tools)
        finalization_only = bool(
            controller_context.get("controller_finalization_only", False)
        )
        expected_output_contract = spec.expected_output_contract
        declared_authoritative_contract = controller_context.get(
            "authoritative_final_output_contract"
        )
        if (
            controller_context.get("delivery_scope")
            in {"task_final", "final_content_source"}
            and isinstance(declared_authoritative_contract, Mapping)
        ):
            expected_output_contract = dict(declared_authoritative_contract)
        from .json_serialization import json_serialization_format, JSONL_GENERATION_INSTRUCTION
        jsonl_output = json_serialization_format(expected_output_contract) == "jsonl"
        output_artifact_type = (
            str(expected_output_contract.get("artifact_type") or "").strip().casefold()
            if isinstance(expected_output_contract, Mapping)
            else ""
        )
        code_generation_output = output_artifact_type in {
            "code", "python", "python_script", "python_source", "source_code",
        }

        def early_failure(code: str) -> Any:
            empty_sha256 = canonical_sha256("")
            return ControllerTurnResultV1(
                session_id=snapshot.session_id,
                turn_id=turn_id,
                turn_index=turn_index,
                status="failure",
                transport_audit={"status": "not_started"},
                request_sha256=canonical_sha256(
                    {
                        "session_id": snapshot.session_id,
                        "turn_id": turn_id,
                        "provider_tools": provider_tools,
                    }
                ),
                response_sha256=empty_sha256,
                candidate_sha256=empty_sha256,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                failure_code=code,
            )

        if (
            isinstance(spec, ControllerSessionSpecV2)
            and not tool_enabled
            and not finalization_only
        ):
            return early_failure("controller_provider_tool_scope_missing")
        if finalization_only and tool_enabled:
            return early_failure("controller_finalization_tool_scope_present")
        if tool_enabled:
            if not isinstance(spec, ControllerSessionSpecV2):
                return early_failure("controller_provider_tool_scope_not_authorized")
            sealed_tools = tuple(
                project_provider_tool_schema(item) for item in spec.callable_tools
            )
            if len(provider_tools) != len(sealed_tools) or any(
                canonical_sha256(actual) != expected.provider_tool_schema_sha256
                for actual, expected in zip(provider_tools, spec.callable_tools)
            ):
                return early_failure(
                    "controller_provider_tool_schema_identity_changed"
                )
            if any(
                canonical_sha256(actual) != canonical_sha256(sealed)
                for actual, sealed in zip(provider_tools, sealed_tools)
            ):
                return early_failure(
                    "controller_provider_tool_schema_identity_changed"
                )

        enforcement = _validated_format_enforcement(kwargs.get("format_enforcement"))
        if tool_enabled and enforcement is not None:
            return early_failure("controller_tool_native_format_enforcement_forbidden")
        from .controller_request_projection import project_controller_input_snapshot
        base_payload: Dict[str, Any] = {
            "protocol": "sgar-controller-turn-input-v1",
            "session_id": snapshot.session_id,
            "turn_id": turn_id,
            "turn_index": turn_index,
            **({"execution_budget": dict(controller_context["execution_budget"])}
               if tool_session and controller_context.get("execution_budget") else {}),
            "controller_resource_id": spec.controller_resource_id,
            "controller_resource_type": spec.controller_resource_type,
            "backing_model_resource_id": spec.backing_model_resource_id,
            "task_instruction": spec.task_instruction,
            "delivery_scope": str(controller_context.get("delivery_scope") or "task_final"),
            "requirement_interpretation": {
                "semantic_authority": "original task in task_context",
                "step_scope": "task_instruction",
                "requirements": "mandatory_acceptance_criteria",
                "output_format": ["expected_output_contract", "mandatory_final_format"],
            },
            **({"tool_working_directory": controller_context["tool_working_directory"]}
               if tool_enabled and controller_context.get("tool_working_directory") else {}),
            **({"execution_path_contract": {
                "tool_logical_workspace_root": controller_context["tool_working_directory"],
                "generated_process_cwd_rule": (
                    "Use the actual process working directory or relative paths inside "
                    "generated programs; do not hard-code the Tool logical root."
                ),
                "intermediate_creation_rule": (
                    "Input inventories list existing inputs, not all writable files. "
                    "Necessary intermediate files may be created through bound mutator "
                    "Tools within their declared writable scope; preserve exact final paths."
                ),
            }} if tool_enabled and controller_context.get("tool_working_directory") else {}),
            **({"task_context": str(controller_context["task_context"])}
               if controller_context.get("task_context") is not None else {}),
            "mandatory_acceptance_criteria": list(
                controller_context.get("mandatory_acceptance_criteria") or ()
            ),
            **{key: controller_context[key] for key in (
                "external_acquisition_mode", "conditional_evidence_instruction",
                "external_discovery_mode", "source_discovery_instruction",
            ) if controller_context.get(key)},
            **({"execution_check_progress": dict(controller_context["execution_check_progress"])}
               if controller_context.get("execution_check_progress") else {}),
            "mandatory_acceptance_examples": list(
                controller_context.get("mandatory_acceptance_examples") or ()
            ),
            "mandatory_final_format": dict(
                controller_context.get("mandatory_final_format") or {}
            ),
            **({"required_successful_tool_operations": list(
                controller_context.get("required_successful_tool_operations") or ()
            )} if tool_enabled and controller_context.get("required_successful_tool_operations") else {}),
            **({"pending_required_tool_operations": list(
                controller_context.get("pending_required_tool_operations") or ()
            )} if tool_enabled and controller_context.get("pending_required_tool_operations") else {}),
            **({"pending_required_tool_functions": list(
                controller_context.get("pending_required_tool_functions") or ()
            )} if tool_enabled and controller_context.get("pending_required_tool_functions") else {}),
            **({"stateful_execution_policy": dict(
                controller_context.get("stateful_execution_policy") or {}
            )} if tool_enabled and controller_context.get("stateful_execution_policy") else {}),
            **({"materialized_delivery_state": dict(controller_context["materialized_delivery_state"])}
               if tool_session and controller_context.get("materialized_delivery_state") else {}),
            **project_controller_input_snapshot(snapshot.model_dump(mode="json")),
            "expected_output_contract": expected_output_contract,
            **({"generated_source_contract": dict(controller_context["generated_source_contract"])}
               if controller_context.get("generated_source_contract") else {}),
            **({"generation_efficiency_contract": {
                "maximum_output_tokens": int(
                    controller_context.get("max_tokens") or self.max_tokens
                ),
                "completion_priority": [
                    "complete_required_behavior_and_exact_output_contract",
                    "smallest_source_that_preserves_required_behavior",
                ],
                "rules": [
                    "Finish materially below the output limit; do not restate the task or requirements in the artifact.",
                    "Omit comments, docstrings, tutorials, examples, duplicated checks, and internal test scaffolding unless the output contract explicitly requires them.",
                    "Keep concise runtime validation needed for the mandatory acceptance criteria; never remove required behavior, format, or delivery checks to save tokens.",
                ],
            }} if not tool_enabled and code_generation_output else {}),
            "agent_card": str(agent_card) if agent_card is not None else None,
            "callable_tool_scope": list(spec.callable_tool_scope),
            **({"authorized_tool_functions": [
                {"function_name": item.provider_tool_name,
                 "dynamic_argument_names": [port["name"] for port in item.dynamic_input_ports],
                 **({"arguments_example": {}} if not item.dynamic_input_ports else {}),
                 "runtime_fixed_arguments": {
                     name: binding["literal"]
                     for name, binding in item.fixed_input_bindings.items()
                     if isinstance(binding, Mapping) and "literal" in binding
                 },
                 "runtime_bound_argument_names": list(item.fixed_input_bindings)}
                for item in spec.callable_tools
            ]} if tool_enabled else {}),
            "dynamic_argument_authority": spec.dynamic_argument_authority,
            "tool_result_continuation": spec.tool_result_continuation,
        }
        if finalization_evidence_audit:
            if controller_context.get("finalization_evidence_contract"):
                base_payload["finalization_evidence_contract"] = dict(
                    controller_context["finalization_evidence_contract"]
                )
            base_payload["requirement_interpretation"]["output_format_scope"] = "final_output"
            base_payload["format_instruction"] = (
                "When returning a final answer, use the internal JSON evidence-audit envelope "
                "in finalization_evidence_contract. Continue native Tool calls while required "
                "work remains and Tools are available. The task's FINAL OUTPUT instruction, "
                "expected_output_contract and mandatory_final_format apply to the exact "
                "result string in final_output. The runtime validates and unwraps that "
                "field for public delivery; keep audit fields outside the public result."
            )
            if controller_context.get("materialized_delivery_available"):
                base_payload["requirement_interpretation"]["output_format_scope"] = "materialized_file"
                base_payload["format_instruction"] = (
                    "When returning a final answer, use the internal JSON evidence-audit envelope. "
                    "Continue native Tool calls when required work remains. Audit readiness and "
                    "each original acceptance criterion against the Tool evidence. The runtime "
                    "has read and format-validated the declared delivery file and delivers its "
                    "bytes unchanged. Set final_output to an empty string; do not regenerate "
                    "the file content or substitute the audit envelope for the public result."
                )
        if jsonl_output and enforcement is None:
            materialized_audit = bool(
                finalization_evidence_audit
                and controller_context.get("materialized_delivery_available")
            )
            base_payload["final_artifact_encoding"] = {
                "format": "jsonl",
                "scope": ("materialized_file" if materialized_audit else
                          "final_output" if finalization_evidence_audit else "final_artifact"),
                "instruction": JSONL_GENERATION_INSTRUCTION,
                "phase_rule": (
                    "Preserve the validated materialized file bytes and return an empty final_output "
                    "inside the required audit envelope; do not regenerate the file."
                    if materialized_audit else
                    "Apply this encoding only to the final_output string inside the required audit "
                    "envelope; retain the outer audit object."
                    if finalization_evidence_audit else
                    "This encoding applies only to final artifact content. While required work "
                    "remains, use the native Tool-call protocol and its declared arguments."
                ),
            }
        controller_media_parts = tuple(
            controller_context.get("model_media_parts") or ()
        )
        controller_media_audit = list(
            controller_context.get("model_media_audit") or ()
        )
        from .workspace_inventory_projection import project_runtime_fixed_arguments
        base_payload = project_runtime_fixed_arguments(base_payload)
        skill_bundle = kwargs.get("skill_bundle")
        skill_content = None
        if skill_bundle is not None:
            from .controller_skills import ControllerSkillError, apply_skill_context, verify_skill_messages
            try:
                skill_content = apply_skill_context(skill_bundle, spec, snapshot, base_payload)
            except (ControllerSkillError, ValueError) as exc:
                return early_failure(getattr(exc, "code", "controller_skill_bundle_invalid"))
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    self._TOOL_SYSTEM_PROMPT if tool_session else self._SYSTEM_PROMPT
                ),
            },
            {
                "role": "user",
                "content": compose_model_user_content(
                    json.dumps(
                        base_payload,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    controller_media_parts,
                ),
            },
        ]
        if skill_content is not None:
            messages.append({"role": "user", "content": skill_content})
        for message in kwargs.get("conversation_messages") or ():
            role = str(message.get("role") or "")
            content = str(message.get("content") or "")
            if role == "tool":
                tool_call_id = str(message.get("tool_call_id") or "").strip()
                if not tool_session or not tool_call_id:
                    raise ValueError("controller_conversation_tool_message_invalid")
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": content,
                    }
                )
                continue
            if role not in {"assistant", "user"}:
                raise ValueError("controller_conversation_role_invalid")
            projected_message: dict[str, Any] = {"role": role, "content": content}
            if role == "assistant" and message.get("tool_calls"):
                if not tool_session:
                    raise ValueError("controller_conversation_tool_call_invalid")
                projected_message["tool_calls"] = list(message["tool_calls"])
            messages.append(projected_message)

        api_kwargs: Dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "max_tokens": int(controller_context.get("max_tokens") or self.max_tokens),
            "stream": False,
        }
        if GLOBAL_CAPABILITY_REGISTRY.explicitly_allows(
            model_id, "reasoning_effort_low_ok"
        ):
            api_kwargs["reasoning_effort"] = "low"
        if tool_enabled:
            api_kwargs["tools"] = list(provider_tools)
            if controller_context.get("pending_required_tool_operations"):
                pending_functions = tuple(sorted(set(
                    str(item)
                    for item in (
                        controller_context.get("pending_required_tool_functions")
                        or ()
                    )
                    if str(item).strip()
                )))
                authorized_functions = {
                    item.provider_tool_name for item in spec.callable_tools
                }
                if not set(pending_functions).issubset(authorized_functions):
                    return early_failure(
                        "controller_pending_tool_function_not_authorized"
                    )
                choice_capability = (
                    "named_tool_choice_ok" if len(pending_functions) == 1
                    else "required_tool_choice_ok"
                )
                # Native tool support does not imply support for forced choice.
                # Pending operations remain in the prompt and are checked by
                # the runtime even when the optional provider hint is omitted.
                if GLOBAL_CAPABILITY_REGISTRY.explicitly_allows(
                    model_id, choice_capability
                ):
                    api_kwargs["tool_choice"] = (
                        {
                            "type": "function",
                            "function": {"name": pending_functions[0]},
                        }
                        if len(pending_functions) == 1
                        else "required"
                    )
        if (
            finalization_evidence_audit
            and not tool_enabled
            and GLOBAL_CAPABILITY_REGISTRY.explicitly_allows(
                model_id, "json_mode_ok"
            )
        ):
            api_kwargs["response_format"] = {"type": "json_object"}
        if GLOBAL_CAPABILITY_REGISTRY.explicitly_allows(model_id, "temperature_ok"):
            api_kwargs["temperature"] = float(
                controller_context.get("temperature", self.temperature)
            )
        if enforcement is not None and not finalization_evidence_audit:
            _apply_format_enforcement(api_kwargs, enforcement)
        elif (
            not tool_enabled
            and not finalization_evidence_audit
            and not jsonl_output
            and str(spec.expected_output_contract.get("artifact_type") or "").lower()
            == "json"
        ):
            if (
                _json_contract_requires_object(spec.expected_output_contract)
                and GLOBAL_CAPABILITY_REGISTRY.explicitly_allows(model_id, "json_mode_ok")
            ):
                api_kwargs["response_format"] = {"type": "json_object"}
            else:
                base_payload["format_instruction"] = (
                    "Return exactly one JSON value satisfying expected_output_contract.schema_hint. "
                    "Preserve the declared root type; do not add an object wrapper or Markdown."
                )
                messages[1]["content"] = compose_model_user_content(
                    json.dumps(
                        base_payload,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    controller_media_parts,
                )
        if skill_bundle is not None:
            try:
                verify_skill_messages(skill_bundle, messages)
            except (ControllerSkillError, ValueError) as exc:
                return early_failure(getattr(exc, "code", "controller_skill_render_identity_mismatch"))
        operation_id = f"controller:{snapshot.session_id}:{turn_id}"
        accounting_context = (
            ModelCallContext(
                operation_id=operation_id,
                stage=(
                    "agent_execution"
                    if spec.controller_resource_type == "Agent"
                    else "model_execution"
                ),
                subtask_id=spec.subtask_id,
                subtask_revision=spec.subtask_revision,
                selected_resource_id=spec.controller_resource_id,
                model_resource_id=spec.backing_model_resource_id,
                agent_id=(
                    spec.controller_resource_id
                    if spec.controller_resource_type == "Agent"
                    else None
                ),
                request_policy_sha256=spec.controller_session_policy_sha256,
                reasoning_effort=api_kwargs.get("reasoning_effort"),
            )
            if self.cost_ledger is not None
            else None
        )
        try:
            response, transport_audit = await _request_with_transport_retry(
                self.transport,
                api_kwargs,
                max_attempts=int(
                    controller_context.get("max_retries") or self.max_retries
                ),
                model_payload_guard=(
                    controller_context.get("model_payload_guard")
                    or self.model_payload_guard
                ),
                cost_ledger=self.cost_ledger,
                accounting_context=accounting_context,
            )
        except _TransportRequestFailure as exc:
            from .input_volume import controller_input_volume
            failure_code = (
                "controller_time_limit"
                if exc.failure.get("failure_type") == ModelTimeBudgetError.error_code
                else
                "controller_cost_limit"
                if exc.failure.get("responsibility") == "budget"
                else "controller_transport_failure"
            )
            request_hash = str(exc.failure.get("request_hash") or "").removeprefix(
                "sha256:"
            )
            return ControllerTurnResultV1(
                session_id=snapshot.session_id,
                turn_id=turn_id,
                turn_index=turn_index,
                status="failure",
                transport_audit={
                    **dict(exc.audit),
                    "model_media_projection": controller_media_audit,
                    "input_volume": controller_input_volume(spec, snapshot),
                },
                model_accounting_reference=exc.accounting_reference,
                request_sha256=request_hash,
                response_sha256=canonical_sha256({"response_received": False}),
                candidate_sha256=canonical_sha256(""),
                latency_ms=(time.perf_counter() - started) * 1000,
                failure_code=failure_code,
                terminal_failure=TerminalFailureEnvelope.create(
                    responsibility=exc.failure.get("responsibility", "framework"),
                    failure_stage=exc.failure.get("failure_stage", "downstream_model_transport"),
                    failure_code=exc.failure.get("failure_type", failure_code),
                    response_received=bool(exc.failure.get("response_received", False)),
                    retryable=bool(exc.failure.get("retryable", False)),
                    exception_type=type(exc.original).__name__,
                    message_sha256=exc.failure.get("stack_fingerprint_sha256"),
                    subtask_id=spec.subtask_id,
                    subtask_revision=spec.subtask_revision,
                    request_sha256=request_hash or None,
                    model_operation_id=(exc.accounting_reference or {}).get("operation_id"),
                ),
            )

        try:
            transport_audit = {
                **dict(transport_audit),
                "model_media_projection": controller_media_audit,
            }
            choice = response.choices[0]
            message = choice.message
            content = str(message.content or "")
            finish_reason = str(choice.finish_reason or "") or None
            raw_tool_calls = getattr(message, "tool_calls", None)
            transport_audit["provider_tool_call_count"] = len(raw_tool_calls or ())
            usage = getattr(response, "usage", None)
            token_usage = {
                "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
                "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
                "cached_tokens": int(
                    getattr(
                        getattr(usage, "prompt_tokens_details", None),
                        "cached_tokens",
                        0,
                    )
                    or 0
                ),
                "reasoning_tokens": int(
                    getattr(
                        getattr(usage, "completion_tokens_details", None),
                        "reasoning_tokens",
                        0,
                    )
                    or 0
                ),
            }
        except Exception:
            return ControllerTurnResultV1(
                session_id=snapshot.session_id,
                turn_id=turn_id,
                turn_index=turn_index,
                status="failure",
                transport_audit=transport_audit,
                model_accounting_reference=getattr(response, "accounting_reference", None),
                request_sha256=str(transport_audit["request_hashes"][0]).removeprefix(
                    "sha256:"
                ),
                response_sha256=canonical_sha256({"response_received": True}),
                candidate_sha256=canonical_sha256(""),
                latency_ms=(time.perf_counter() - started) * 1000,
                failure_code="controller_transport_failure",
            )

        if tool_enabled and raw_tool_calls:
            try:
                normalized_calls = normalize_provider_tool_calls(
                    session_id=snapshot.session_id,
                    turn_id=turn_id,
                    raw_tool_calls=tuple(raw_tool_calls),
                    callable_tools=spec.callable_tools,
                    argument_projector=controller_context.get("tool_argument_projector"),
                )
                tool_calls = tuple(
                    item.model_dump(mode="json") for item in normalized_calls
                )
            except ControllerToolRuntimeError as exc:
                return ControllerTurnResultV1(
                    session_id=snapshot.session_id,
                    turn_id=turn_id,
                    turn_index=turn_index,
                    status="failure",
                    content=content,
                    finish_reason=finish_reason,
                    transport_audit=transport_audit,
                    token_usage=token_usage,
                    model_accounting_reference=getattr(
                        response, "accounting_reference", None
                    ),
                    request_sha256=str(
                        transport_audit["request_hashes"][0]
                    ).removeprefix("sha256:"),
                    response_sha256=canonical_sha256(
                        {
                            "content": content,
                            "tool_calls_invalid": True,
                            "finish_reason": finish_reason,
                            "token_usage": token_usage,
                        }
                    ),
                    candidate_sha256=canonical_sha256(content),
                    latency_ms=(time.perf_counter() - started) * 1000,
                    failure_code=exc.code,
                )
        else:
            tool_calls = self._tool_call_views(raw_tool_calls)

        status = "failure" if finish_reason == "length" else "success"
        failure_code = (
            "controller_provider_truncation" if finish_reason == "length" else None
        )
        return ControllerTurnResultV1(
            session_id=snapshot.session_id,
            turn_id=turn_id,
            turn_index=turn_index,
            status=status,
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            transport_audit=transport_audit,
            token_usage=token_usage,
            model_accounting_reference=getattr(response, "accounting_reference", None),
            request_sha256=str(transport_audit["request_hashes"][0]).removeprefix(
                "sha256:"
            ),
            response_sha256=canonical_sha256(
                {
                    "content": content,
                    "tool_calls": tool_calls,
                    "finish_reason": finish_reason,
                    "token_usage": token_usage,
                }
            ),
            candidate_sha256=canonical_sha256(content),
            latency_ms=(time.perf_counter() - started) * 1000,
            failure_code=failure_code,
        )


# ─────────────────────────────────────────────
# DumbExecutor (BYPASS_MODE)
# ─────────────────────────────────────────────

class DumbExecutor(BaseExecutor):
    """
    Execute local commands in a prepared Docker runtime with timeout enforcement.

    Dependency resolution and installation are intentionally outside this class.
    Callers must pass a prepared runtime environment whose ``image_id`` is an
    immutable Docker content identifier.  This keeps resource execution separate
    from the auditable runtime-preparation phase.
    """

    def __init__(self, timeout_sec: int = 30, max_auto_heals: int = 0):
        self.timeout_sec = max(
            1,
            min(MAX_NORMAL_TIMEOUT_SECONDS, int(timeout_sec)),
        )
        if max_auto_heals:
            logger.warning(
                "[Sandbox] max_auto_heals is deprecated and ignored; "
                "runtime dependencies must be prepared before execution."
            )
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    def _to_container_arg(self, p: str) -> str:
        """Map Linux project paths; preserve task data arguments byte-for-byte."""
        p_str = str(p)
        root_str = self.project_root
        if (
            p_str.lower() == root_str.lower()
            or p_str.lower().startswith(root_str.lower().rstrip("/") + "/")
        ):
            return "/app" + p_str[len(root_str):]
        return p_str

    def _project_path(self, value: Any, *, field: str, kind: str) -> str:
        """Resolve and validate one host path without widening its scope."""
        text = str(value or "").strip()
        if not text or not os.path.isabs(text):
            raise ValueError(f"{field} must be an absolute host path")
        path = os.path.abspath(text)
        project = os.path.abspath(self.project_root)
        try:
            if os.path.commonpath([path, project]) != project:
                raise ValueError(f"{field} must remain inside the project")
            if os.path.commonpath([os.path.realpath(path), os.path.realpath(project)]) != os.path.realpath(project):
                raise ValueError(f"{field} resolves outside the project")
        except ValueError as exc:
            if str(exc).startswith(field):
                raise
            raise ValueError(f"{field} must remain inside the project") from exc
        if not os.path.exists(path):
            raise ValueError(f"{field} does not exist")
        if kind == "file" and not os.path.isfile(path):
            raise ValueError(f"{field} must be a file")
        if kind == "directory" and not os.path.isdir(path):
            raise ValueError(f"{field} must be a directory")
        return path

    def _is_project_path(self, value: Any) -> bool:
        text = str(value or "").strip()
        if not text or not os.path.isabs(text):
            return False
        path = os.path.abspath(text)
        project = os.path.abspath(self.project_root)
        try:
            return (
                os.path.commonpath([path, project]) == project
                and os.path.commonpath(
                    [os.path.realpath(path), os.path.realpath(project)]
                )
                == os.path.realpath(project)
            )
        except ValueError:
            return False

    def _external_workspace_path(
        self,
        value: Any,
        *,
        field: str,
        kind: str,
        workspace_root: str,
        allow_workspace_root: bool = False,
    ) -> str:
        """Validate one exact route below the scope-authorized external workspace."""

        text = str(value or "").strip()
        if not text or not os.path.isabs(text):
            raise ValueError(f"{field} must be an absolute host path")
        path = os.path.abspath(text)
        workspace = os.path.abspath(str(workspace_root))
        if self._is_project_path(path):
            raise ValueError(f"{field} external route must remain outside the project")
        try:
            contained = os.path.commonpath([path, workspace]) == workspace
        except ValueError:
            contained = False
        if not contained or (path == workspace and not allow_workspace_root):
            raise ValueError(
                f"{field} must remain inside the exact external run workspace"
            )
        resolved_workspace = os.path.realpath(workspace)
        resolved_path = os.path.realpath(path)
        if (
            os.path.normcase(resolved_workspace) != os.path.normcase(workspace)
            or os.path.normcase(resolved_path) != os.path.normcase(path)
        ):
            raise ValueError(
                f"{field} may not contain a symlink, junction, or reparse point"
            )
        try:
            if os.path.commonpath([resolved_path, resolved_workspace]) != resolved_workspace:
                raise ValueError(
                    f"{field} resolves outside the exact external run workspace"
                )
        except ValueError as exc:
            if str(exc).startswith(field):
                raise
            raise ValueError(
                f"{field} resolves outside the exact external run workspace"
            ) from exc
        if not os.path.exists(path):
            raise ValueError(f"{field} does not exist")
        if kind == "file" and not os.path.isfile(path):
            raise ValueError(f"{field} must be a file")
        if kind == "directory" and not os.path.isdir(path):
            raise ValueError(f"{field} must be a directory")
        return path

    def _runtime_path(self, host_path: str, value: Any, *, field: str) -> str:
        expected = self._to_container_arg(host_path)
        if value is None:
            runtime = expected
        else:
            runtime = str(value).strip()
            if "\\" in runtime:
                raise ValueError(
                    f"{field}.runtime_path must be a normalized absolute POSIX path"
                )
        normalized = posixpath.normpath(runtime)
        if (
            normalized != runtime.rstrip("/")
            or not (normalized == "/app" or normalized.startswith("/app/"))
        ):
            raise ValueError(
                f"{field}.runtime_path must be a normalized absolute POSIX path under /app"
            )
        return normalized

    @staticmethod
    def _path_contains(parent: str, child: str) -> bool:
        try:
            return os.path.commonpath([os.path.abspath(parent), os.path.abspath(child)]) == os.path.abspath(parent)
        except ValueError:
            return False

    def _scope_entry(
        self,
        value: Any,
        *,
        field: str,
        directory_only: bool = False,
        external_workspace: str | None = None,
    ) -> Dict[str, str]:
        payload = dict(value) if isinstance(value, dict) else {"host_path": value}
        declared_kind = str(payload.get("path_kind") or "").strip().lower()
        if directory_only:
            kind = "directory"
            if declared_kind and declared_kind != kind:
                raise ValueError(f"{field}.path_kind must be directory")
        elif declared_kind:
            if declared_kind not in {"file", "directory"}:
                raise ValueError(f"{field}.path_kind must be file or directory")
            kind = declared_kind
        else:
            candidate = str(payload.get("host_path") or "")
            kind = "directory" if os.path.isdir(candidate) else "file"
        raw_host_path = payload.get("host_path")
        if self._is_project_path(raw_host_path):
            host_path = self._project_path(raw_host_path, field=field, kind=kind)
        elif external_workspace is not None:
            if not payload.get("runtime_path"):
                raise ValueError(
                    f"{field}.runtime_path is required for an external route"
                )
            host_path = self._external_workspace_path(
                raw_host_path,
                field=field,
                kind=kind,
                workspace_root=external_workspace,
            )
        else:
            host_path = self._project_path(raw_host_path, field=field, kind=kind)
        runtime_path = self._runtime_path(
            host_path,
            payload.get("runtime_path"),
            field=field,
        )
        return {
            "host_path": host_path,
            "runtime_path": runtime_path,
            "path_kind": kind,
        }

    def _normalize_sandbox_scope(self, value: Any) -> Dict[str, Any]:
        """Validate the explicit sandbox contract and return exact mount entries."""
        if hasattr(value, "model_dump"):
            try:
                value = value.model_dump(mode="python")
            except TypeError:
                value = value.model_dump()
        if not isinstance(value, dict):
            raise ValueError("sandbox_scope must be a mapping")
        protocol = str(value.get("protocol") or "").strip()
        if protocol != "sgar-sandbox-scope/v1":
            raise ValueError("sandbox_scope.protocol must be sgar-sandbox-scope/v1")

        project = os.path.abspath(self.project_root)
        raw_masked = value.get("masked_roots")
        if not isinstance(raw_masked, list):
            raise ValueError("sandbox_scope.masked_roots must be a list")
        external_mask_indexes: list[int] = []
        for index, raw in enumerate(raw_masked):
            payload = dict(raw) if isinstance(raw, dict) else {"host_path": raw}
            if not self._is_project_path(payload.get("host_path")):
                external_mask_indexes.append(index)
        if len(external_mask_indexes) > 1:
            raise ValueError("sandbox_scope may authorize only one external run workspace")

        external_workspace: str | None = None
        external_mask_index: int | None = None
        external_mask_entry: Dict[str, str] | None = None
        if external_mask_indexes:
            external_mask_index = external_mask_indexes[0]
            raw_anchor = raw_masked[external_mask_index]
            if not isinstance(raw_anchor, dict):
                raise ValueError(
                    "external run workspace requires an explicit scope route"
                )
            declared_kind = str(raw_anchor.get("path_kind") or "directory").strip().lower()
            if declared_kind != "directory":
                raise ValueError("external run workspace must be a directory")
            raw_anchor_path = str(raw_anchor.get("host_path") or "").strip()
            if not raw_anchor_path or not os.path.isabs(raw_anchor_path):
                raise ValueError("external run workspace must be an absolute host path")
            candidate_workspace = os.path.abspath(raw_anchor_path)
            anchor = os.path.abspath(Path(candidate_workspace).anchor)
            if os.path.normcase(candidate_workspace) == os.path.normcase(anchor):
                raise ValueError("external run workspace may not be a filesystem root")
            external_workspace = self._external_workspace_path(
                candidate_workspace,
                field="external_run_workspace",
                kind="directory",
                workspace_root=candidate_workspace,
                allow_workspace_root=True,
            )
            anchor_runtime_path = self._runtime_path(
                external_workspace,
                raw_anchor.get("runtime_path"),
                field=f"masked_roots[{external_mask_index}]",
            )
            if anchor_runtime_path != "/app/run":
                raise ValueError(
                    "external run workspace must use the fixed /app/run runtime root"
                )
            external_mask_entry = {
                "host_path": external_workspace,
                "runtime_path": anchor_runtime_path,
                "path_kind": "directory",
            }

        raw_runtime_roots = value.get("runtime_roots")
        if not isinstance(raw_runtime_roots, list) or not raw_runtime_roots:
            raise ValueError("sandbox_scope.runtime_roots must be a non-empty list")
        runtime_roots = [
            self._scope_entry(
                item,
                field=f"runtime_roots[{index}]",
                directory_only=True,
            )
            for index, item in enumerate(raw_runtime_roots)
        ]
        runtime_host_paths: set[str] = set()
        runtime_paths: set[str] = set()
        for index, entry in enumerate(runtime_roots):
            host_path = os.path.abspath(entry["host_path"])
            if host_path == project:
                raise ValueError("runtime_roots may not mount the complete project root")
            relative = os.path.relpath(host_path, project).replace("\\", "/")
            if relative.split("/", 1)[0].startswith("."):
                raise ValueError(
                    f"runtime_roots[{index}] may not expose a hidden project root"
                )
            host_key = os.path.normcase(host_path)
            runtime_key = entry["runtime_path"]
            if host_key in runtime_host_paths or runtime_key in runtime_paths:
                raise ValueError("runtime_roots must be unique")
            if any(
                self._path_contains(existing["host_path"], host_path)
                or self._path_contains(host_path, existing["host_path"])
                for existing in runtime_roots[:index]
            ):
                raise ValueError("runtime_roots may not overlap")
            runtime_host_paths.add(host_key)
            runtime_paths.add(runtime_key)

        raw_public = value.get("public_inputs")
        if raw_public is None and "public_roots" in value:
            raw_public = value.get("public_roots")
        if not isinstance(raw_public, list):
            raise ValueError("sandbox_scope.public_inputs must be a list")
        public_inputs = []
        for index, item in enumerate(raw_public):
            payload = dict(item) if isinstance(item, dict) else {"host_path": item}
            entry = self._scope_entry(
                payload,
                field=f"public_inputs[{index}]",
                external_workspace=external_workspace,
            )
            descriptor_sha256 = str(payload.get("sha256") or "").strip().lower()
            if not re.fullmatch(r"[0-9a-f]{64}", descriptor_sha256):
                raise ValueError(
                    f"public_inputs[{index}].sha256 must be a full lowercase SHA-256"
                )
            verified = verify_public_input_path(
                path=Path(entry["host_path"]),
                workspace_root=Path(
                    external_workspace
                    if external_workspace is not None
                    and not self._is_project_path(entry["host_path"])
                    else self.project_root
                ),
                expected_path_kind=entry["path_kind"],
                expected_sha256=descriptor_sha256,
            )
            entry["host_path"] = str(verified)
            entry["sha256"] = descriptor_sha256
            public_inputs.append(entry)

        writable = self._scope_entry(
            value.get("writable_root"),
            field="writable_root",
            directory_only=True,
            external_workspace=external_workspace,
        )
        masked_roots = []
        for index, item in enumerate(raw_masked):
            if index == external_mask_index:
                assert external_mask_entry is not None
                masked_roots.append(external_mask_entry)
            else:
                masked_roots.append(
                    self._scope_entry(
                        item,
                        field=f"masked_roots[{index}]",
                        directory_only=True,
                    )
                )
        raw_hidden = value.get("hidden_roots") or []
        if not isinstance(raw_hidden, list):
            raise ValueError("sandbox_scope.hidden_roots must be a list")
        hidden_roots = [
            self._scope_entry(item, field=f"hidden_roots[{index}]", directory_only=True)
            for index, item in enumerate(raw_hidden)
        ]

        if external_workspace is not None:
            if self._is_project_path(writable["host_path"]):
                raise ValueError(
                    "external run workspace requires an external isolated writable_root"
                )
            if not writable["runtime_path"].startswith("/app/run/"):
                raise ValueError(
                    "external writable_root must be isolated below /app/run"
                )
            # Each route has already been checked for containment in the
            # explicit run workspace. The run anchor stays stable when both
            # producer and consumer live in a deeper work/plan subtree; it
            # must not depend on this step's incidental common path prefix.

        # Mounting the project root would otherwise leave alternate copies of
        # masked assets reachable through VCS objects or agent/editor metadata.
        # Require every present internal metadata directory to be explicitly
        # hidden.  Unsupported file/link forms fail closed rather than leak.
        metadata_layout = inspect_internal_metadata_layout(Path(self.project_root))
        hidden_host_paths = {
            os.path.normcase(os.path.abspath(entry["host_path"]))
            for entry in hidden_roots
        }
        for internal in metadata_layout.hidden_roots:
            if os.path.normcase(os.path.abspath(internal)) not in hidden_host_paths:
                raise ValueError(
                    f"internal metadata root must be hidden: {internal.name}"
                )

        for entry in [*masked_roots, *hidden_roots]:
            if os.path.abspath(entry["host_path"]) == project:
                raise ValueError("sandbox_scope may not mask the project root")
        for public in public_inputs:
            inherited_from_runtime = any(
                self._path_contains(runtime["host_path"], public["host_path"])
                for runtime in runtime_roots
            )
            if inherited_from_runtime and not any(
                self._path_contains(mask["host_path"], public["host_path"])
                for mask in masked_roots
            ):
                raise ValueError(
                    "public input inherited from a runtime root must be contained by a masked root"
                )
            if self._path_contains(public["host_path"], writable["host_path"]) or self._path_contains(
                writable["host_path"], public["host_path"]
            ):
                raise ValueError("public inputs and writable_root may not overlap")
            for hidden in hidden_roots:
                if self._path_contains(hidden["host_path"], public["host_path"]) or self._path_contains(
                    public["host_path"], hidden["host_path"]
                ):
                    raise ValueError("public inputs and hidden_roots may not overlap")
        for hidden in hidden_roots:
            if self._path_contains(hidden["host_path"], writable["host_path"]) or self._path_contains(
                writable["host_path"], hidden["host_path"]
            ):
                raise ValueError("hidden_roots and writable_root may not overlap")
        for runtime_root in runtime_roots:
            # A later mask may safely narrow a broader runtime root.  The
            # inverse would hide the runtime root itself and is invalid.
            if any(
                self._path_contains(protected["host_path"], runtime_root["host_path"])
                for protected in [*masked_roots, *hidden_roots]
            ):
                raise ValueError("runtime_roots may not be inside masked or hidden roots")
            for protected in [*public_inputs, writable]:
                if self._path_contains(protected["host_path"], runtime_root["host_path"]):
                    raise ValueError("runtime_roots may not be inside public or writable roots")
                if self._path_contains(runtime_root["host_path"], protected["host_path"]):
                    narrowed_by_mask = any(
                        self._path_contains(runtime_root["host_path"], mask["host_path"])
                        and self._path_contains(mask["host_path"], protected["host_path"])
                        for mask in masked_roots
                    )
                    if not narrowed_by_mask:
                        raise ValueError(
                            "runtime root overlap with public/writable requires an intervening mask"
                        )

        working_directory = str(
            value.get("working_directory") or writable["runtime_path"]
        ).replace("\\", "/")
        working_directory = posixpath.normpath(working_directory)
        writable_runtime = writable["runtime_path"]
        if not (
            working_directory == writable_runtime
            or working_directory.startswith(writable_runtime.rstrip("/") + "/")
        ):
            raise ValueError("working_directory must remain inside writable_root")

        normalized_scope = {
            "protocol": protocol,
            "runtime_roots": runtime_roots,
            "public_inputs": public_inputs,
            "writable_root": writable,
            "masked_roots": masked_roots,
            "hidden_roots": hidden_roots,
            "working_directory": working_directory,
            "allow_legacy_shell": bool(value.get("allow_legacy_shell", False)),
        }
        validate_internal_metadata_scope(metadata_layout, normalized_scope)
        path_map = RuntimePathMap.from_scope(normalized_scope)
        mapped_entries = [*runtime_roots, *public_inputs, writable]
        for entry in mapped_entries:
            runtime_path = entry["runtime_path"]
            if path_map.host_to_runtime(entry["host_path"]) != runtime_path:
                raise ValueError(
                    "sandbox scope host/runtime route does not match its explicit alias"
                )
            round_trip_host = path_map.runtime_to_host(runtime_path)
            if os.path.normcase(os.path.realpath(os.path.abspath(round_trip_host))) != os.path.normcase(
                os.path.realpath(os.path.abspath(entry["host_path"]))
            ):
                raise ValueError(
                    "sandbox scope runtime/host route does not round-trip to the declared host path"
                )
        path_map.validate_runtime(working_directory)
        return normalized_scope

    @staticmethod
    def _scope_audit(scope: Optional[Dict[str, Any]], *, legacy_shell: bool) -> Dict[str, Any]:
        if scope is None:
            payload: Dict[str, Any] = {
                "protocol": "legacy-unscoped",
                "direct_argv": not legacy_shell,
                "allow_legacy_shell": True,
                "working_directory": "/app",
                "mounts": [{"target": "/app", "access": "rw", "purpose": "project"}],
                "project_root_mounted": True,
            }
        else:
            mounts = [
                {
                    "target": "/app",
                    "access": "masked_readonly",
                    "purpose": "runtime_root_base",
                }
            ]
            mounts.extend(
                {
                    "target": entry["runtime_path"],
                    "access": "ro",
                    "purpose": "runtime_root",
                    "path_kind": "directory",
                }
                for entry in scope["runtime_roots"]
            )
            mounts.extend(
                {"target": entry["runtime_path"], "access": "masked_readonly", "purpose": "masked"}
                for entry in scope["masked_roots"]
            )
            mounts.extend(
                {"target": entry["runtime_path"], "access": "masked_readonly", "purpose": "hidden"}
                for entry in scope["hidden_roots"]
            )
            mounts.extend(
                {
                    "target": entry["runtime_path"],
                    "access": "ro",
                    "purpose": "public_input",
                    "path_kind": entry["path_kind"],
                    "sha256": entry["sha256"],
                }
                for entry in scope["public_inputs"]
            )
            mounts.append(
                {
                    "target": scope["writable_root"]["runtime_path"],
                    "access": "rw",
                    "purpose": "writable_root",
                    "path_kind": "directory",
                }
            )
            payload = {
                "protocol": scope["protocol"],
                "direct_argv": not legacy_shell,
                "allow_legacy_shell": scope["allow_legacy_shell"],
                "working_directory": scope["working_directory"],
                "mounts": mounts,
                "project_root_mounted": False,
            }
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return {
            **payload,
            "scope_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            "host_paths_exposed": False,
        }


    @staticmethod
    def _runtime_environment_field(
        runtime_environment: Any,
        name: str,
        default: Any = None,
    ) -> Any:
        if isinstance(runtime_environment, dict):
            return runtime_environment.get(name, default)
        if hasattr(runtime_environment, name):
            return getattr(runtime_environment, name)
        model_dump = getattr(runtime_environment, "model_dump", None)
        if callable(model_dump):
            try:
                payload = model_dump(mode="python")
            except TypeError:
                payload = model_dump()
            if isinstance(payload, dict):
                return payload.get(name, default)
        return default

    @staticmethod
    def _structured_runtime_failure(
        failure_type: str,
        message: str,
        *,
        extra_metrics: Optional[Dict[str, Any]] = None,
        responsibility: str = "framework",
        failure_stage: str = "runtime_preflight",
        retryable: bool = False,
    ) -> ExecutionResult:
        failure = _failure_record(
            failure_stage=failure_stage,
            responsibility=responsibility,
            retryable=retryable,
            transport_attempt=0,
            request_hash="",
            response_received=False,
            failure_type=failure_type,
        )
        metrics: Dict[str, Any] = {
            "latency_ms": 0,
            "attempt_count": 0,
            "failure_type": failure_type,
            "failure_layer": responsibility,
            "failure": failure,
        }
        metrics.update(extra_metrics or {})
        return ExecutionResult(
            is_success=False,
            output_data="",
            error_log=message,
            cost_metric=metrics,
        )

    @staticmethod
    async def _docker_probe_ok(*argv: str, env: Dict[str, str]) -> bool:
        """Run a bounded Docker control-plane probe using exit status only."""

        try:
            probe = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                env=env,
            )
            try:
                await asyncio.wait_for(probe.communicate(), timeout=15)
            except asyncio.TimeoutError:
                probe.kill()
                await probe.communicate()
                return False
            return probe.returncode == 0
        except Exception:
            return False

    @classmethod
    async def _classify_docker_launch_failure(
        cls,
        image_id: str,
        env: Dict[str, str],
    ) -> tuple[str, str]:
        """Separate control-plane drift from framework-generated run arguments.

        Docker exit status 125 means the selected command never ran, but it can
        represent either an unavailable daemon/image or an invalid framework
        launch specification.  Two bounded, read-only probes make that
        distinction without interpreting provider-, platform-, or Case-specific
        diagnostic text.
        """

        if not await cls._docker_probe_ok(
            "docker", "info", "--format", "{{.ServerVersion}}", env=env
        ):
            return "infrastructure", "runtime_daemon_unavailable"
        if not await cls._docker_probe_ok(
            "docker", "image", "inspect", image_id, env=env
        ):
            return "infrastructure", "runtime_image_unavailable"
        return "framework", "runtime_launch_invalid"

    async def execute(
        self, subtask_desc: str, context_data: str, **kwargs
    ) -> ExecutionResult:
        require_legacy_runtime("DumbExecutor.execute")
        start = time.time()
        command = kwargs.get("command", subtask_desc)
        raw_args = kwargs.get("args", [])
        if raw_args is None:
            args: list = []
        elif isinstance(raw_args, (list, tuple)):
            args = list(raw_args)
        else:
            return self._structured_runtime_failure(
                "structured_argv_invalid",
                "Executor args must be a structured list or tuple.",
            )
        if not str(command or "").strip() or "\x00" in str(command):
            return self._structured_runtime_failure(
                "structured_argv_invalid",
                "Executor command must be a non-empty string without NUL bytes.",
            )
        if any("\x00" in str(item) for item in args):
            return self._structured_runtime_failure(
                "structured_argv_invalid",
                "Executor arguments may not contain NUL bytes.",
            )
        install_packages = [
            str(item).strip()
            for item in (kwargs.get("install_packages") or [])
            if str(item).strip()
        ]
        extra_env = kwargs.get("extra_env") or {}
        allow_dynamic_install = bool(kwargs.get("allow_dynamic_install", False))
        if install_packages or allow_dynamic_install:
            return self._structured_runtime_failure(
                "legacy_inline_install_forbidden",
                (
                    "Inline dependency installation is forbidden. Prepare an immutable "
                    "runtime environment before invoking the executor."
                ),
                extra_metrics={"install_packages": install_packages},
            )

        runtime_environment = kwargs.get("runtime_environment")
        if runtime_environment is None:
            return self._structured_runtime_failure(
                "runtime_environment_missing",
                "A prepared runtime_environment is required for Docker execution.",
            )

        runtime_image_id = str(
            self._runtime_environment_field(runtime_environment, "image_id", "") or ""
        ).strip()
        if not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", runtime_image_id):
            return self._structured_runtime_failure(
                "runtime_environment_invalid",
                "runtime_environment.image_id must be an immutable sha256 Docker image ID.",
                extra_metrics={"runtime_image_id": runtime_image_id},
            )

        network_required = bool(
            self._runtime_environment_field(
                runtime_environment,
                "execution_network_required",
                self._runtime_environment_field(
                    runtime_environment,
                    "network_required",
                    False,
                ),
            )
        )
        if "network_required" in kwargs and bool(kwargs.get("network_required")) != network_required:
            return self._structured_runtime_failure(
                "runtime_environment_invalid",
                "Executor network policy does not match the prepared runtime handle.",
                extra_metrics={
                    "runtime_image_id": runtime_image_id,
                    "prepared_network_required": network_required,
                },
            )
        formal_supervision = bool(kwargs.get("formal_supervision", False))
        try:
            network_policy = NetworkExecutionPolicy(
                mode=str(
                    kwargs.get("network_policy_mode")
                    or ("disabled" if formal_supervision else "declared")
                ),
                allowed_proxy_names=tuple(
                    kwargs.get("allowed_proxy_environment_names")
                    or NetworkExecutionPolicy().allowed_proxy_names
                ),
                allowed_environment_names=tuple(
                    kwargs.get("allowed_runtime_environment_names")
                    or NetworkExecutionPolicy().allowed_environment_names
                ),
            )
        except (TypeError, ValueError):
            return self._structured_runtime_failure(
                "network_policy_invalid",
                "The versioned network execution policy is invalid.",
            )
        if not network_policy.permits(network_required=network_required):
            return self._structured_runtime_failure(
                "network_policy_disabled",
                "The selected Tool declares network access but this run disabled Tool networking.",
                responsibility="research",
                failure_stage="execution_policy",
            )

        raw_scope = kwargs.get("sandbox_scope")
        scope: Optional[Dict[str, Any]] = None
        if raw_scope is not None:
            try:
                scope = self._normalize_sandbox_scope(raw_scope)
            except InternalMetadataLayoutError:
                return self._structured_runtime_failure(
                    "internal_metadata_layout_invalid",
                    "The repository metadata layout is invalid for isolated execution.",
                    extra_metrics={"runtime_image_id": runtime_image_id},
                )
            except (TypeError, ValueError) as exc:
                return self._structured_runtime_failure(
                    "sandbox_scope_invalid",
                    f"Invalid explicit sandbox scope: {exc}",
                    extra_metrics={"runtime_image_id": runtime_image_id},
                )
        legacy_shell = bool(kwargs.get("legacy_shell", False))
        if legacy_shell and scope is not None and not scope["allow_legacy_shell"]:
            return self._structured_runtime_failure(
                "legacy_shell_forbidden",
                "Legacy shell execution is disabled by the explicit sandbox scope.",
                extra_metrics={"runtime_image_id": runtime_image_id},
            )

        logger.info(
            "[Sandbox] Invoking direct argv ({} argument(s), network={})",
            len(args),
            network_policy.mode,
        )

        linux_args = [self._to_container_arg(a) for a in args]
        docker_env = direct_environment(os.environ)
        docker_env["MSYS_NO_PATHCONV"] = "1"
        docker_env["SGAR_WORKSPACE_ROOT"] = "/app"
        docker_args = ["docker", "run", "--rm"]
        if not network_required:
            docker_args.extend(["--network", "none"])
        docker_args.extend([
            "-e", "SGAR_WORKSPACE_ROOT=/app",
        ])
        # Override inherited host, Docker-client and image proxy defaults.
        # --network none above still controls resources without network permission.
        proxy_config = load_tool_proxy_config(self.project_root)
        proxy_audit = tool_proxy_audit(proxy_config)
        docker_env.update(
            tool_proxy_environment(
                proxy_config,
                network_required=network_required,
                network_policy_mode=network_policy.mode,
            )
        )
        docker_args.extend(
            direct_container_environment_args(
                proxy_config=proxy_config,
                network_required=network_required,
                network_policy_mode=network_policy.mode,
            )
        )
        for key, value in dict(extra_env).items():
            key_text = str(key or "").strip()
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key_text):
                continue
            if key_text.lower() in {"http_proxy", "https_proxy", "all_proxy", "ftp_proxy", "no_proxy"}:
                return self._structured_runtime_failure(
                    "runtime_proxy_override_forbidden",
                    "SGAR resource processes use direct network connections.",
                    responsibility="research", failure_stage="execution_policy",
                )
            if formal_supervision and key_text not in set(
                network_policy.allowed_environment_names
            ):
                return self._structured_runtime_failure(
                    "runtime_environment_variable_forbidden",
                    "A Tool requested an environment variable outside the versioned allowlist.",
                    responsibility="research",
                    failure_stage="execution_policy",
                )
            docker_env[key_text] = str(value)
            # As with proxy variables, keep environment values out of argv and
            # any command-line based execution trace.
            docker_args.extend(["-e", key_text])
        if scope is not None:
            docker_args.extend([
                "--read-only",
                "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges",
                "--pids-limit", "256",
                "--tmpfs", "/tmp:rw,noexec,nosuid,size=128m",
                "--tmpfs", "/app:ro,noexec,nosuid,nodev,size=16m",
            ])
            for entry in scope["runtime_roots"]:
                docker_args.extend([
                    "-v",
                    f"{entry['host_path']}:{entry['runtime_path']}:ro",
                ])
            seen_masks: set[str] = set()
            for entry in [*scope["masked_roots"], *scope["hidden_roots"]]:
                target = entry["runtime_path"]
                if target in seen_masks:
                    continue
                seen_masks.add(target)
                docker_args.extend([
                    "--tmpfs",
                    f"{target}:ro,noexec,nosuid,nodev,size=16m",
                ])
            # Mount order is intentional: exact public inputs override their
            # masked parent without exposing undeclared sibling fixtures.
            for entry in scope["public_inputs"]:
                docker_args.extend([
                    "-v",
                    f"{entry['host_path']}:{entry['runtime_path']}:ro",
                ])
            writable = scope["writable_root"]
            docker_args.extend([
                "-v",
                f"{writable['host_path']}:{writable['runtime_path']}:rw",
            ])
            working_directory = scope["working_directory"]
        else:
            docker_args.extend(["-v", f"{self.project_root}:/app"])
            working_directory = "/app"

        control_root = (
            Path(scope["writable_root"]["host_path"]) / ".sgar-control"
            if scope is not None
            else Path.cwd()
        )
        call_identity = DockerCallIdentity.create(
            run_id=str(kwargs.get("run_id") or "legacy-run"),
            call_id=str(kwargs.get("resource_call_id") or hashlib.sha256(
                json.dumps(
                    [str(command), [str(item) for item in args]],
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()),
            step_id=str(kwargs.get("step_id") or "legacy-step"),
            attempt=max(1, int(kwargs.get("attempt") or 1)),
            control_root=control_root,
        )
        if formal_supervision:
            docker_args[3:3] = call_identity.docker_options()

        command_text = str(command)
        command_name = os.path.basename(command_text.replace("\\", "/")).lower()
        linux_cmd = (
            "python"
            if re.fullmatch(r"python(?:\d+(?:\.\d+)*)?(?:\.exe)?", command_name)
            else self._to_container_arg(command_text)
        )
        runtime_argv = [linux_cmd, *(str(arg) for arg in linux_args)]
        host_root = re.sub(r"/+", "/", self.project_root.replace("\\", "/")).lower()
        if any(
            host_root
            in re.sub(r"/+", "/", str(item).replace("\\", "/")).lower()
            for item in runtime_argv
        ):
            return self._structured_runtime_failure(
                "runtime_argv_host_path_forbidden",
                "Runtime argv still contains the host workspace path after path resolution.",
                extra_metrics={
                    "runtime_image_id": runtime_image_id,
                    "execution_audit": {
                        **self._scope_audit(scope, legacy_shell=legacy_shell),
                        "runtime_argv_count": len(runtime_argv),
                        "runtime_argv_host_path_detected": True,
                    },
                },
            )
        docker_args.extend(["-w", working_directory, runtime_image_id])
        if legacy_shell:
            quoted_args = " ".join(shlex.quote(str(arg)) for arg in linux_args)
            inner_cmd = f"{shlex.quote(linux_cmd)} {quoted_args}".strip()
            docker_args.extend(["sh", "-c", inner_cmd])
        else:
            docker_args.extend(runtime_argv)
        execution_audit = self._scope_audit(scope, legacy_shell=legacy_shell)
        execution_audit.update(
            {
                "runtime_argv_count": len(runtime_argv),
                "runtime_argv_hash": hashlib.sha256(
                    json.dumps(
                        runtime_argv,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest(),
                "runtime_argv_host_path_detected": False,
            }
        )
        runtime_metrics = {
            "runtime_image_id": runtime_image_id,
            "runtime_base_image_id": self._runtime_environment_field(
                runtime_environment, "base_image_id", ""
            ),
            "runtime_request_hash": self._runtime_environment_field(
                runtime_environment, "request_hash", ""
            ),
            "runtime_environment_hash": self._runtime_environment_field(
                runtime_environment, "environment_hash", ""
            ),
            "runtime_lock_hash": self._runtime_environment_field(
                runtime_environment, "lock_hash", ""
            ),
            "runtime_cache_hit": bool(
                self._runtime_environment_field(runtime_environment, "cache_hit", False)
            ),
            "runtime_preparation_event_id": self._runtime_environment_field(
                runtime_environment, "preparation_event_id", ""
            ),
            "runtime_preparation_event_ids": list(
                self._runtime_environment_field(
                    runtime_environment, "preparation_event_ids", []
                )
                or []
            ),
            "network_mode": "enabled" if network_required else "none",
            "network_policy_protocol": "sgar-network-policy-v1",
            "network_policy_mode": network_policy.mode,
            **proxy_audit,
            "attempt_count": 1,
            "execution_audit": execution_audit,
            "sandbox_scope_hash": execution_audit["scope_hash"],
        }
        try:
            capture_policy = ProcessCapturePolicy(
                stdout_limit_bytes=int(
                    kwargs.get("stdout_limit_bytes") or 256 * 1024 * 1024
                ),
                stderr_limit_bytes=int(
                    kwargs.get("stderr_limit_bytes") or 256 * 1024 * 1024
                ),
            )
        except (TypeError, ValueError):
            return self._structured_runtime_failure(
                "process_capture_policy_invalid",
                "The versioned process capture policy is invalid.",
            )
        supervisor = DockerProcessSupervisor(
            capture_policy=capture_policy,
            verify_cleanup=formal_supervision,
        )
        forbidden_diagnostics = [
            self.project_root,
            *(str(value) for value in dict(extra_env).values()),
            *(
                str(os.environ.get(name) or "")
                for name in network_policy.allowed_proxy_names
                if name.lower() != "no_proxy"
            ),
        ]
        try:
            async with bridge_loopback_tool_proxies(
                docker_env, network_required=network_required,
            ) as routed_env:
                for proxy_name in ("HTTP_PROXY", "HTTPS_PROXY"):
                    routed_proxy = routed_env.get(proxy_name, "")
                    if routed_proxy and routed_proxy != docker_env.get(proxy_name, ""):
                        forbidden_diagnostics.append(routed_proxy)
                docker_env = routed_env
                supervised = await supervisor.run(
                    docker_args,
                    env=docker_env,
                    timeout_seconds=self.timeout_sec,
                    identity=call_identity,
                )
            latency = (time.time() - start) * 1000
            capture_audit = {
                "protocol": "sgar-process-capture-v1",
                "stdout": supervised.stdout.audit(),
                "stderr": supervised.stderr.audit(),
                "container_identity_sha256": supervised.container_identity_sha256,
                "container_cleanup_verified": supervised.cleanup_verified,
            }
            runtime_metrics["process_capture"] = capture_audit
            if not supervised.cleanup_verified:
                return self._structured_runtime_failure(
                    "container_cleanup_unverified",
                    "The call-scoped container cleanup could not be verified.",
                    responsibility="framework",
                    failure_stage="runtime_cleanup",
                    extra_metrics={**runtime_metrics, "latency_ms": latency},
                )
            if supervised.returncode == 0 and supervised.stdout.text is None:
                return self._structured_runtime_failure(
                    "process_stdout_not_utf8",
                    "Binary stdout must be returned through a declared artifact handle.",
                    responsibility="research",
                    failure_stage="output_contract",
                    extra_metrics={**runtime_metrics, "latency_ms": latency},
                )
            stdout = supervised.stdout.text or ""
            stderr_text = supervised.stderr.text
            sanitized_stderr, diagnostic_audit = sanitize_diagnostic(
                stderr_text if stderr_text is not None else "<binary-stderr>",
                forbidden_values=forbidden_diagnostics,
            )
            runtime_metrics["diagnostic_audit"] = diagnostic_audit
            if supervised.returncode == 0:
                logger.info(f"[Sandbox] Success ({len(stdout)} chars) in {latency:.0f}ms")
                return ExecutionResult(
                    is_success=True,
                    output_data=stdout,
                    error_log=None,
                    cost_metric={
                        **runtime_metrics,
                        "latency_ms": latency,
                        "return_code": supervised.returncode,
                    },
                )

            logger.warning(f"[Sandbox] Exit code {supervised.returncode}")
            # Docker reserves 125 for failures in the Docker invocation itself
            # (before the selected command runs).  This phase/exit-code signal
            # is stable and does not inspect case-dependent stderr text.
            if supervised.returncode == 125:
                responsibility, failure_type = await self._classify_docker_launch_failure(
                    runtime_image_id,
                    docker_env,
                )
            else:
                responsibility, failure_type = "research", "resource_process_failed"
            failure = _failure_record(
                failure_stage=(
                    "runtime_launch"
                    if supervised.returncode == 125
                    else "resource_execution"
                ),
                responsibility=responsibility,
                retryable=False,
                transport_attempt=0,
                request_hash="",
                response_received=supervised.returncode != 125,
                failure_type=failure_type,
            )
            # A completed command's stdout may contain its error explanation.
            # Keep it only as bounded, sanitized failure evidence, never success.
            diagnostic_stdout, stdout_diagnostic_audit = sanitize_diagnostic(
                stdout, forbidden_values=forbidden_diagnostics,
            )
            runtime_metrics["stdout_diagnostic_audit"] = stdout_diagnostic_audit
            return ExecutionResult(
                is_success=False,
                output_data=diagnostic_stdout if supervised.returncode != 125 else "",
                error_log=sanitized_stderr,
                cost_metric={
                    **runtime_metrics,
                    "latency_ms": latency,
                    "return_code": supervised.returncode,
                    "failure_type": failure_type,
                    "failure_layer": responsibility,
                    "failure": failure,
                },
            )
        except ToolProxyRelayError as exc:
            return self._structured_runtime_failure(
                str(exc),
                "The configured Tool proxy is unreachable from the isolated Docker network.",
                responsibility="framework",
                failure_stage="runtime_network",
                extra_metrics=runtime_metrics,
            )
        except asyncio.TimeoutError:
            cleanup_verified = await supervisor.cleanup(call_identity, env=docker_env)
            failure = _failure_record(
                failure_stage="resource_execution",
                responsibility="research",
                retryable=False,
                transport_attempt=0,
                request_hash="",
                response_received=False,
                failure_type="tool_runtime_timeout",
            )
            return ExecutionResult(
                is_success=False,
                output_data="",
                error_log="tool_runtime_timeout",
                cost_metric={
                    **runtime_metrics,
                    "latency_ms": (time.time() - start) * 1000,
                    "container_cleanup_verified": cleanup_verified,
                    "failure_type": "tool_runtime_timeout",
                    "failure_layer": "research",
                    "failure": failure,
                },
            )
        except ProcessOutputLimitExceeded as exc:
            cleanup_verified = await supervisor.cleanup(call_identity, env=docker_env)
            failure = _failure_record(
                failure_stage="resource_execution",
                responsibility="research",
                retryable=False,
                transport_attempt=0,
                request_hash="",
                response_received=False,
                failure_type="process_output_limit_exceeded",
            )
            return ExecutionResult(
                is_success=False,
                output_data="",
                error_log="process_output_limit_exceeded",
                cost_metric={
                    **runtime_metrics,
                    "latency_ms": (time.time() - start) * 1000,
                    "limited_stream": exc.stream_name,
                    "observed_bytes": exc.observed_bytes,
                    "limit_bytes": exc.limit_bytes,
                    "container_cleanup_verified": cleanup_verified,
                    "failure_type": "process_output_limit_exceeded",
                    "failure_layer": "research",
                    "failure": failure,
                },
            )
        except asyncio.CancelledError:
            cleanup_verified = await supervisor.cleanup(call_identity, env=docker_env)
            return ExecutionResult(
                is_success=False,
                output_data="",
                error_log="resource_execution_interrupted",
                cost_metric={
                    **runtime_metrics,
                    "latency_ms": (time.time() - start) * 1000,
                    "container_cleanup_verified": cleanup_verified,
                    "failure_type": "resource_execution_interrupted",
                    "failure_layer": "interrupted",
                    "failure": {
                        "responsibility": "interrupted",
                        "failure_stage": "resource_execution",
                        "failure_code": "resource_execution_interrupted",
                        "retryable": False,
                        "response_received": False,
                    },
                },
            )
        except (OSError, ProcessSupervisionError):
            failure = _failure_record(
                failure_stage="runtime_launch",
                responsibility="infrastructure",
                retryable=False,
                transport_attempt=0,
                request_hash="",
                response_received=False,
                failure_type="runtime_profile_unavailable",
            )
            return ExecutionResult(
                is_success=False,
                output_data="",
                error_log="runtime_profile_unavailable",
                cost_metric={
                    **runtime_metrics,
                    "latency_ms": (time.time() - start) * 1000,
                    "failure_type": "runtime_profile_unavailable",
                    "failure_layer": "infrastructure",
                    "failure": failure,
                },
            )


class HostPythonExecutor(BaseExecutor):
    """Run explicitly trusted, stdlib-only project tools in the active Python env.

    This executor is deliberately narrow: it accepts only a workspace-local
    ``.py`` entrypoint, never invokes a shell, never installs dependencies, and
    is used only by manifests declaring ``host-python-stdlib``.
    """

    def __init__(self, project_root: str, timeout_sec: int = 180):
        self.project_root = os.path.abspath(project_root)
        self.timeout_sec = max(1, int(timeout_sec))

    def _workspace_script(self, value: Any) -> Optional[str]:
        text = str(value or "").strip().strip("'\"")
        if text.startswith("/app/"):
            text = os.path.join(self.project_root, text[len("/app/") :])
        elif not os.path.isabs(text):
            text = os.path.join(self.project_root, text)
        path = os.path.abspath(text)
        try:
            if os.path.commonpath([path, self.project_root]) != self.project_root:
                return None
        except ValueError:
            return None
        if not path.endswith(".py") or not os.path.isfile(path):
            return None
        return path

    async def execute(
        self,
        subtask_desc: str,
        context_data: str,
        **kwargs: Any,
    ) -> ExecutionResult:
        require_legacy_runtime("HostPythonExecutor.execute")
        start = time.time()
        args = list(kwargs.get("args") or [])
        install_packages = list(kwargs.get("install_packages") or [])
        if install_packages:
            return ExecutionResult(
                is_success=False,
                output_data="",
                error_log="HostPythonExecutor forbids dynamic dependency installation.",
                cost_metric={
                    "latency_ms": 0,
                    "failure_type": "dependency_install_blocked",
                    "runtime_profile": "host-python-stdlib",
                    "attempt_count": 0,
                },
            )
        if not args:
            return ExecutionResult(
                is_success=False,
                output_data="",
                error_log="HostPythonExecutor requires a Python script argument.",
                cost_metric={
                    "latency_ms": 0,
                    "failure_type": "tool_runtime_error",
                    "runtime_profile": "host-python-stdlib",
                    "attempt_count": 0,
                },
            )
        script_path = self._workspace_script(args[0])
        if script_path is None:
            return ExecutionResult(
                is_success=False,
                output_data="",
                error_log=f"Untrusted or missing host Python entrypoint: {args[0]}",
                cost_metric={
                    "latency_ms": 0,
                    "failure_type": "unsafe_execution_path",
                    "runtime_profile": "host-python-stdlib",
                    "attempt_count": 0,
                },
            )

        env = os.environ.copy()
        env["SGAR_WORKSPACE_ROOT"] = self.project_root
        env["SGAR_HOST_WORKSPACE_ROOT"] = self.project_root
        for key, value in dict(kwargs.get("extra_env") or {}).items():
            key_text = str(key or "").strip()
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key_text):
                env[key_text] = str(value)

        command = [sys.executable, script_path, *(str(arg) for arg in args[1:])]
        logger.info("[HostPython] Invoking trusted tool: {}", " ".join(command))
        try:
            proc = await asyncio.create_subprocess_exec(
                *command,
                cwd=self.project_root,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self.timeout_sec,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return ExecutionResult(
                    is_success=False,
                    output_data="",
                    error_log=f"Host Python execution exceeded {self.timeout_sec}s.",
                    cost_metric={
                        "latency_ms": (time.time() - start) * 1000,
                        "failure_type": "tool_runtime_timeout",
                        "runtime_profile": "host-python-stdlib",
                        "attempt_count": 1,
                    },
                )
        except Exception:
            return ExecutionResult(
                is_success=False,
                output_data="",
                error_log=traceback.format_exc(),
                cost_metric={
                    "latency_ms": (time.time() - start) * 1000,
                    "failure_type": "tool_runtime_error",
                    "runtime_profile": "host-python-stdlib",
                    "attempt_count": 1,
                },
            )

        stdout = stdout_b.decode(errors="ignore").strip() if stdout_b else ""
        stderr = stderr_b.decode(errors="ignore").strip() if stderr_b else ""
        latency = (time.time() - start) * 1000
        return ExecutionResult(
            is_success=proc.returncode == 0,
            output_data=stdout,
            error_log=None if proc.returncode == 0 else (stderr or stdout),
            cost_metric={
                "latency_ms": latency,
                "return_code": proc.returncode,
                "runtime_profile": "host-python-stdlib",
                "attempt_count": 1,
                **(
                    {}
                    if proc.returncode == 0
                    else {"failure_type": "tool_runtime_error"}
                ),
            },
        )


# ─────────────────────────────────────────────
# SmartExecutor (GENERATIVE_MODE)
# ─────────────────────────────────────────────

class SmartExecutor(BaseExecutor):
    """
    Invokes an LLM endpoint with:
    - Artifact-type-aware prompting (code / json / markdown / plaintext)
    - Streaming output for real-time observability
    - Automatic retry with exponential backoff (max 3 attempts)
    - Post-generation output pre-cleaning
    """

    _PROMPT_TEMPLATE: str = _load_prompt("executor_system.txt")

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o",
        cost_ledger: Optional[RunCostLedger] = None,
        transport: Optional[AsyncModelTransportPort] = None,
    ):
        import httpx
        if transport is None:
            endpoint = ProviderEndpointIdentity.create(
                provider="openai_compatible",
                base_url=base_url,
                credential_environment_variable="LLM_API_KEY",
                timeout_seconds=120.0,
            )
            transport = AsyncModelTransportPort.from_sdk_client(
                client=AsyncOpenAI(
                    http_client=direct_async_http_client(),
                    api_key=api_key,
                    base_url=base_url,
                    timeout=httpx.Timeout(120.0, connect=20.0, read=120.0, write=20.0),
                    max_retries=0,
                ),
                endpoint_identity=endpoint,
            )
        self.transport = require_async_model_transport(transport)
        self.model = model
        self.cost_ledger = cost_ledger

    # ── Output Pre-Cleaning ────────────────────

    @staticmethod
    def _clean_output(text: str, artifact_type: str) -> str:
        """
        Ruthlessly strips conversational waste and markdown artifacts
        from LLM output. Handles both closed and unclosed code fences.
        """
        text = text.strip()
        text = re.sub(r"<think\b[^>]*>.*?</think>\s*", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<think\b[^>]*>.*", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"</think>\s*", "", text, flags=re.IGNORECASE).strip()

        if artifact_type in (ArtifactType.CODE.value, "code"):
            # 1. Try extracting from closed fences: ```python ... ```
            blocks = re.findall(r"```(?:\w+)?\s*\n?(.*?)```", text, re.DOTALL)
            if blocks:
                return max(blocks, key=len).strip()

            # 2. Handle UNCLOSED fence: ```python\n...EOF (stream truncated)
            unclosed = re.match(r"^```(?:\w+)?\s*\n(.*)", text, re.DOTALL)
            if unclosed:
                return unclosed.group(1).strip()

            # 3. Line-by-line cleanup: remove any fence markers + fluff
            lines = text.split("\n")
            fluff_start = {"Here ", "Sure", "Certainly", '\u5f53\u7136', '\u597d\u7684', '\u4ee5\u4e0b', "```"}
            fluff_end = {"Hope ", '\u5982\u6709', '\u5e0c\u671b', "Let me", "```"}
            while lines and any(lines[0].strip().startswith(p) for p in fluff_start):
                lines.pop(0)
            while lines and any(lines[-1].strip().startswith(p) for p in fluff_end):
                lines.pop()
            return "\n".join(lines).strip()

        elif artifact_type in (ArtifactType.JSON.value, "json"):
            blocks = re.findall(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
            if blocks:
                return max(blocks, key=len).strip()
            # Handle unclosed JSON fence
            unclosed = re.match(r"^```(?:json)?\s*\n(.*)", text, re.DOTALL)
            if unclosed:
                return unclosed.group(1).strip()

        return text

    @staticmethod
    def validate_artifact(content: str, artifact_type: str) -> tuple[bool, str]:
        """
        Programmatic validation of artifact content.
        Returns (is_valid, error_message).
        """
        if not content or not content.strip():
            return False, "Empty artifact content"

        if artifact_type in (ArtifactType.CODE.value, "code"):
            # Check for leftover markdown fences
            if content.strip().startswith("```"):
                return False, "Artifact still contains markdown fence markers"
            # Try Python compilation check
            try:
                compile(content, "<artifact>", "exec")
            except SyntaxError as e:
                return False, f"SyntaxError at line {e.lineno}: {e.msg}"

        elif artifact_type in (ArtifactType.JSON.value, "json"):
            import json as json_mod
            try:
                json_mod.loads(content)
            except json_mod.JSONDecodeError as e:
                return False, f"Invalid JSON: {e.msg}"

        return True, "OK"

    # ── Core Execution ─────────────────────────

    async def execute(
        self, subtask_desc: str, context_data: str, **kwargs
    ) -> ExecutionResult:
        start = time.time()
        artifact_type = kwargs.get("artifact_type", "plaintext")
        dynamic_model = kwargs.get("model", self.model)
        max_retries = max(1, min(3, int(kwargs.get("max_retries", 3) or 1)))
        allow_semantic_normalization = bool(
            kwargs.get("allow_semantic_normalization", True)
        )
        final_output_contract = kwargs.get("final_output_contract", "")
        repair_feedback = kwargs.get("repair_feedback", "")
        model_media_parts = kwargs.get("model_media_parts") or ()
        model_media_audit = list(kwargs.get("model_media_audit") or ())
        try:
            format_enforcement = _validated_format_enforcement(
                kwargs.get("format_enforcement")
            )
        except ValueError as exc:
            return ExecutionResult(
                is_success=False,
                output_data="",
                error_log=str(exc),
                cost_metric={
                    "failure_type": "format_enforcement_contract_invalid",
                    "failure_layer": "framework",
                    "attempt_count": 0,
                },
            )

        system_prompt = self._PROMPT_TEMPLATE or (
            "You are a strict S-GAR Machine Executor. Output only the artifact "
            "declared by the typed user payload."
        )
        prompt_payload: Dict[str, Any] = {
            "protocol": "sgar-model-execution-input-v1",
            "task_contract": subtask_desc,
            "artifact_type": artifact_type,
            "bound_dependency_context": context_data,
            "final_output_contract": final_output_contract or None,
            "repair_feedback": repair_feedback or None,
            "source_content_policy": "preserve_original",
            "delivery_language_policy": (
                INTERNAL_LANGUAGE_POLICY.delivery_language_policy
            ),
        }

        logger.info(
            f"[SmartExecutor] model={dynamic_model} | "
            f"artifact={artifact_type} | retries={max_retries}"
        )

        json_artifact = artifact_type in ("json", ArtifactType.JSON.value)
        force_prompt_json = (
            format_enforcement is None
            and not GLOBAL_CAPABILITY_REGISTRY.explicitly_allows(
                dynamic_model, "json_mode_ok"
            )
        )
        if json_artifact and force_prompt_json:
            prompt_payload["format_instruction"] = (
                "Return one valid JSON object as plain text because provider JSON mode "
                "is not authorized for this model identity."
            )
        prompt = json.dumps(
            prompt_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

        use_stream = (
            bool(kwargs.get("allow_streaming", True))
            and not model_media_parts
            and GLOBAL_CAPABILITY_REGISTRY.explicitly_allows(
                dynamic_model, "streaming_ok"
            )
            and format_enforcement is None
        )
        api_kwargs: Dict[str, Any] = {
            "model": dynamic_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": compose_model_user_content(
                        prompt, model_media_parts
                    ),
                },
            ],
            "max_tokens": kwargs.get("max_tokens", 8192),
            "stream": use_stream,
        }
        if GLOBAL_CAPABILITY_REGISTRY.explicitly_allows(
            dynamic_model, "temperature_ok"
        ):
            api_kwargs["temperature"] = kwargs.get("temperature", 0.3)
        json_mode_requested = json_artifact and not force_prompt_json
        if json_mode_requested:
            api_kwargs["response_format"] = {"type": "json_object"}
        if format_enforcement is not None:
            _apply_format_enforcement(api_kwargs, format_enforcement)
            use_stream = False
            json_mode_requested = (
                format_enforcement["selected_enforcement_mode"]
                == "json_object_local_validator"
            )

        try:
            cost_ledger = getattr(self, "cost_ledger", None)
            accounting_context = (
                cost_ledger.new_operation(
                    stage=str(kwargs.get("accounting_stage") or "model_execution"),
                    subtask_id=(str(kwargs["subtask_id"]) if kwargs.get("subtask_id") else None),
                    subtask_revision=(
                        int(kwargs.get("subtask_revision", 0))
                        if kwargs.get("subtask_id")
                        else None
                    ),
                    selected_resource_id=kwargs.get("selected_resource_id"),
                    model_resource_id=kwargs.get("model_resource_id"),
                )
                if cost_ledger is not None
                else None
            )
            response, transport_audit = await _request_with_transport_retry(
                self.transport,
                api_kwargs,
                max_attempts=max_retries,
                model_payload_guard=kwargs.get("model_payload_guard"),
                cost_ledger=cost_ledger,
                accounting_context=accounting_context,
            )
        except _TransportRequestFailure as exc:
            failure = exc.failure
            message = str(exc.original)
            secondary_audit_failures = list(exc.secondary_audit_failures)
            secondary_audit_failures.extend(_safe_capability_error_audit(
                dynamic_model,
                failure["failure_type"],
                message,
            ))
            latency = (time.time() - start) * 1000
            return ExecutionResult(
                is_success=False,
                output_data="",
                error_log=message,
                cost_metric={
                    "latency_ms": latency,
                    "model": dynamic_model,
                    "failure_type": failure["failure_type"],
                    "failure_message": message,
                    "attempt_count": exc.audit["attempt_count"],
                    "retry_events": [],
                    "failure_layer": failure["responsibility"],
                    "failure": failure,
                    "transport_audit": exc.audit,
                    "model_accounting_reference": exc.accounting_reference,
                    "secondary_audit_failures": secondary_audit_failures,
                    "model_media_projection": model_media_audit,
                },
            )

        pieces: list[str] = []
        token_usage: Dict[str, Any] = {}
        finish_reason = None
        try:
            if use_stream:
                _safe_stream_write(
                    f"\n[Stream] [{dynamic_model}] Generating "
                    f"(transport attempts={transport_audit['attempt_count']})...\n",
                )
                async for chunk in response:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta is not None and getattr(delta, "content", None):
                        piece = delta.content
                        pieces.append(piece)
                        _safe_stream_write(piece)
                    if chunk.choices and chunk.choices[0].finish_reason:
                        finish_reason = chunk.choices[0].finish_reason
                    if hasattr(chunk, "usage") and chunk.usage:
                        token_usage = {
                            "prompt_tokens": getattr(chunk.usage, "prompt_tokens", 0),
                            "completion_tokens": getattr(chunk.usage, "completion_tokens", 0),
                            "cached_tokens": getattr(
                                getattr(chunk.usage, "prompt_tokens_details", None),
                                "cached_tokens",
                                0,
                            ),
                        }
                _safe_stream_write("\n[Stream complete]\n")
                GLOBAL_CAPABILITY_REGISTRY.record_success(dynamic_model, "streaming_ok")
            else:
                pieces.append(response.choices[0].message.content or "")
                finish_reason = response.choices[0].finish_reason
                if response.usage:
                    token_usage = {
                        "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                        "completion_tokens": getattr(response.usage, "completion_tokens", 0),
                        "cached_tokens": getattr(
                            getattr(response.usage, "prompt_tokens_details", None),
                            "cached_tokens",
                            0,
                        ),
                    }
        except Exception as exc:
            # A response object was already returned.  Even if a stream later
            # fails, fixed-pass execution never sends another semantic request.
            request_hash = transport_audit["request_hashes"][0]
            failure = _failure_record(
                failure_stage="downstream_model_response",
                responsibility="research",
                retryable=False,
                transport_attempt=transport_audit["attempt_count"],
                request_hash=request_hash,
                response_received=True,
                failure_type="model_response_processing_failed",
            )
            latency = (time.time() - start) * 1000
            return ExecutionResult(
                is_success=False,
                output_data="",
                error_log=str(exc),
                cost_metric={
                    "latency_ms": latency,
                    "model": dynamic_model,
                    "failure_type": failure["failure_type"],
                    "failure_message": str(exc),
                    "attempt_count": transport_audit["attempt_count"],
                    "retry_events": [],
                    "failure_layer": "research",
                    "failure": failure,
                    "transport_audit": transport_audit,
                    "model_accounting_reference": getattr(
                        response, "accounting_reference", None
                    ),
                    "model_media_projection": model_media_audit,
                },
            )

        raw = "".join(pieces)
        clean = (
            self._clean_output(raw, artifact_type)
            if allow_semantic_normalization
            else raw
        )
        latency = (time.time() - start) * 1000
        if finish_reason == "length":
            request_hash = transport_audit["request_hashes"][0]
            failure = _failure_record(
                failure_stage="downstream_model_response",
                responsibility="research",
                retryable=False,
                transport_attempt=transport_audit["attempt_count"],
                request_hash=request_hash,
                response_received=True,
                failure_type="provider_truncation",
            )
            return ExecutionResult(
                is_success=False,
                output_data="",
                error_log="finish_reason=length",
                cost_metric={
                    "latency_ms": latency,
                    "model": dynamic_model,
                    "failure_type": "provider_truncation",
                    "failure_message": "finish_reason=length",
                    "attempt_count": transport_audit["attempt_count"],
                    "retry_events": [],
                    "failure_layer": "research",
                    "failure": failure,
                    "transport_audit": transport_audit,
                    "model_accounting_reference": getattr(
                        response, "accounting_reference", None
                    ),
                    "model_media_projection": model_media_audit,
                },
            )

        format_valid, format_reason = _validate_enforced_output(
            clean,
            format_enforcement,
        )
        if not format_valid:
            request_hash = transport_audit["request_hashes"][0]
            failure = _failure_record(
                failure_stage="downstream_model_response",
                responsibility="research",
                retryable=False,
                transport_attempt=transport_audit["attempt_count"],
                request_hash=request_hash,
                response_received=True,
                failure_type="model_output_schema_invalid",
            )
            return ExecutionResult(
                is_success=False,
                output_data="",
                error_log=str(format_reason or "model_output_schema_invalid"),
                cost_metric={
                    "latency_ms": latency,
                    "model": dynamic_model,
                    "failure_type": failure["failure_type"],
                    "failure_layer": "research",
                    "failure": failure,
                    "attempt_count": transport_audit["attempt_count"],
                    "transport_audit": transport_audit,
                    "format_enforcement_mode": format_enforcement[
                        "selected_enforcement_mode"
                    ],
                    "format_contract_sha256": format_enforcement[
                        "format_contract_sha256"
                    ],
                    "model_accounting_reference": getattr(
                        response, "accounting_reference", None
                    ),
                    "model_media_projection": model_media_audit,
                },
            )

        clean = _normalize_enforced_root_value(clean, format_enforcement)
        GLOBAL_CAPABILITY_REGISTRY.record_success(dynamic_model, "text_ok")
        if json_mode_requested:
            GLOBAL_CAPABILITY_REGISTRY.record_success(dynamic_model, "json_mode_ok")
        logger.info(
            f"[SmartExecutor] Done in {latency:.0f}ms "
            f"({len(clean)} chars clean, finish_reason={finish_reason})"
        )
        return ExecutionResult(
            is_success=True,
            output_data=clean,
            cost_metric={
                "latency_ms": latency,
                "model": dynamic_model,
                "token_usage": token_usage,
                "json_mode_requested": json_mode_requested,
                "prompt_only_json": json_artifact and force_prompt_json,
                "format_enforcement_mode": (
                    format_enforcement["selected_enforcement_mode"]
                    if format_enforcement is not None
                    else None
                ),
                "format_contract_sha256": (
                    format_enforcement["format_contract_sha256"]
                    if format_enforcement is not None
                    else None
                ),
                "temperature_requested": kwargs.get("temperature", 0.3),
                "temperature_control": (
                    "unsupported"
                    "supported"
                    if GLOBAL_CAPABILITY_REGISTRY.get(dynamic_model).temperature_ok is True
                    else "unsupported"
                    if GLOBAL_CAPABILITY_REGISTRY.get(dynamic_model).temperature_ok is False
                    else "unknown_omitted"
                ),
                "attempt_count": transport_audit["attempt_count"],
                "retry_events": [],
                "failure_layer": "none",
                "semantic_normalization_applied": allow_semantic_normalization,
                "transport_audit": transport_audit,
                "model_accounting_reference": getattr(
                    response, "accounting_reference", None
                ),
                "model_media_projection": model_media_audit,
            },
        )


# ─────────────────────────────────────────────
# AgentExecutor (SEMI_GENERATIVE_MODE)
# ─────────────────────────────────────────────

def load_agent_card_text(
    agent_manifest: Dict[str, Any],
    *,
    project_root: str | Path,
    allowed_roots: Sequence[str | Path] | None = None,
    require_file: bool = False,
) -> str:
    """Load one frozen Agent Card without permitting a workspace escape."""

    uri = str(agent_manifest.get("execution", {}).get("uri", "") or "")
    if not uri:
        return ""
    if uri.startswith("file://"):
        uri = uri[len("file://"):]
    root = Path(project_root).resolve()
    candidate = Path(uri)
    resolved = (
        candidate.resolve()
        if candidate.is_absolute()
        else (root / candidate).resolve()
    )
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("agent_card_path_outside_project") from exc
    if allowed_roots:
        allowed = [Path(item).resolve() for item in allowed_roots]
        if not any(
            resolved == allowed_root or resolved.is_relative_to(allowed_root)
            for allowed_root in allowed
        ):
            raise ValueError("agent_card_path_outside_frozen_resource_roots")
    try:
        return resolved.read_text(encoding="utf-8")
    except FileNotFoundError:
        if require_file:
            raise ValueError("agent_card_file_missing")
        logger.warning("[AgentExecutor] Agent card not found: {}", resolved)
        return ""


class AgentExecutor(BaseExecutor):
    """
    Executes a prompt-agent resource through its real base model.

    Agent identity is recorded separately from model billing: agent_id is the
    selected resource, while base_model is the actual API model argument.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o",
        project_root: Optional[str] = None,
        cost_ledger: Optional[RunCostLedger] = None,
        transport: Optional[AsyncModelTransportPort] = None,
    ):
        import httpx
        if transport is None:
            endpoint = ProviderEndpointIdentity.create(
                provider="openai_compatible",
                base_url=base_url,
                credential_environment_variable="LLM_API_KEY",
                timeout_seconds=120.0,
            )

            transport = AsyncModelTransportPort.from_sdk_client(
                client=AsyncOpenAI(
                    http_client=direct_async_http_client(),
                    api_key=api_key,
                    base_url=base_url,
                    timeout=httpx.Timeout(120.0, connect=20.0, read=120.0, write=20.0),
                    max_retries=0,
                ),
                endpoint_identity=endpoint,
            )
        self.transport = require_async_model_transport(transport)
        self.model = model
        self.cost_ledger = cost_ledger
        self.project_root = project_root or os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )

    def _resolve_uri(self, uri: str) -> str:
        if uri.startswith("file://"):
            uri = uri[len("file://"):]
        if os.path.isabs(uri):
            return uri
        return os.path.abspath(os.path.join(self.project_root, uri))

    def _load_agent_card(
        self,
        agent_manifest: Dict[str, Any],
        *,
        allowed_roots: Sequence[str | Path] | None = None,
        require_file: bool = False,
    ) -> str:
        return load_agent_card_text(
            agent_manifest,
            project_root=self.project_root,
            allowed_roots=allowed_roots,
            require_file=require_file,
        )

    async def execute(
        self,
        subtask_desc: str,
        context_data: str,
        **kwargs: Any,
    ) -> ExecutionResult:
        start = time.time()
        agent_manifest: Dict[str, Any] = kwargs.get("agent_manifest", {})
        dependencies: List[TypedResourceRef] = kwargs.get("dependencies", [])
        artifact_type = kwargs.get("artifact_type", "plaintext")
        agent_id = agent_manifest.get("resource_id", kwargs.get("agent_id", "unknown_agent"))
        expected_output = kwargs.get("expected_output", "")
        final_output_contract = kwargs.get("final_output_contract", "")
        repair_feedback = kwargs.get("repair_feedback", "")
        model_media_parts = kwargs.get("model_media_parts") or ()
        model_media_audit = list(kwargs.get("model_media_audit") or ())
        max_retries = max(1, min(3, int(kwargs.get("max_retries", 3) or 1)))
        allow_semantic_normalization = bool(
            kwargs.get("allow_semantic_normalization", True)
        )
        bound_inputs: Dict[str, str] = kwargs.get("bound_inputs", {})
        try:
            format_enforcement = _validated_format_enforcement(
                kwargs.get("format_enforcement")
            )
        except ValueError as exc:
            return ExecutionResult(
                is_success=False,
                output_data="",
                error_log=str(exc),
                cost_metric={
                    "failure_type": "format_enforcement_contract_invalid",
                    "failure_layer": "framework",
                    "attempt_count": 0,
                },
            )

        base_model = kwargs.get("base_model")
        if not base_model or str(base_model).startswith("agent_"):
            return ExecutionResult(
                is_success=False,
                output_data="",
                error_log=f"Invalid Agent base_model: {base_model}",
                cost_metric={
                    "latency_ms": (time.time() - start) * 1000,
                    "agent_id": agent_id,
                    "base_model": base_model,
                    "failure_type": "agent_missing_base_model",
                    "failure_layer": "plan_composition",
                    "attempt_count": 0,
                },
            )

        supplied_agent_card = kwargs.get("agent_card")
        agent_card = (
            str(supplied_agent_card)
            if supplied_agent_card is not None
            else self._load_agent_card(agent_manifest)
        )
        if not agent_card.strip():
            return ExecutionResult(
                is_success=False,
                output_data="",
                error_log=f"Agent Card unavailable: {agent_id}",
                cost_metric={
                    "latency_ms": (time.time() - start) * 1000,
                    "agent_id": agent_id,
                    "base_model": base_model,
                    "failure_type": "agent_card_unavailable",
                    "failure_layer": "resource_executability",
                    "attempt_count": 0,
                },
            )
        system_prompt = AGENT_EXECUTOR_SYSTEM_PROMPT
        user_payload: Dict[str, Any] = {
            "protocol": "sgar-agent-execution-input-v1",
            "agent_id": agent_id,
            "agent_card": agent_card,
            "task_contract": subtask_desc,
            "artifact_type": artifact_type,
            "expected_output_contract": expected_output,
            "final_output_contract": final_output_contract or None,
            "repair_feedback": repair_feedback or None,
            "upstream_dag_context": context_data,
            "bound_dependency_resources": [
                {
                    "resource_id": dependency.resource_id,
                    "resource_type": dependency.resource_type.value,
                }
                for dependency in dependencies
            ],
            "plan_bound_runtime_inputs": dict(bound_inputs),
            "source_content_policy": "preserve_original",
            "delivery_language_policy": (
                INTERNAL_LANGUAGE_POLICY.delivery_language_policy
            ),
        }

        json_artifact = artifact_type in ("json", ArtifactType.JSON.value)
        force_prompt_json = (
            format_enforcement is None
            and not GLOBAL_CAPABILITY_REGISTRY.explicitly_allows(
                str(base_model), "json_mode_ok"
            )
        )
        if json_artifact and force_prompt_json:
            user_payload["format_instruction"] = (
                "Return one valid JSON object as plain text because provider JSON mode "
                "is not authorized for this model identity."
            )
        user_prompt = json.dumps(
            user_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

        use_stream = (
            bool(kwargs.get("allow_streaming", True))
            and not model_media_parts
            and GLOBAL_CAPABILITY_REGISTRY.explicitly_allows(
                str(base_model), "streaming_ok"
            )
            and format_enforcement is None
        )
        api_kwargs: Dict[str, Any] = {
            "model": base_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": compose_model_user_content(
                        user_prompt, model_media_parts
                    ),
                },
            ],
            "max_tokens": kwargs.get("max_tokens", 8192),
            "stream": use_stream,
        }
        if GLOBAL_CAPABILITY_REGISTRY.explicitly_allows(
            str(base_model), "temperature_ok"
        ):
            api_kwargs["temperature"] = kwargs.get("temperature", 0.3)
        json_mode_requested = json_artifact and not force_prompt_json
        if json_mode_requested:
            api_kwargs["response_format"] = {"type": "json_object"}
        if format_enforcement is not None:
            _apply_format_enforcement(api_kwargs, format_enforcement)
            use_stream = False
            json_mode_requested = (
                format_enforcement["selected_enforcement_mode"]
                == "json_object_local_validator"
            )

        logger.info(
            "[AgentExecutor] agent={} | base_model={} | fixed transport attempts<= {}",
            agent_id,
            base_model,
            max_retries,
        )
        try:
            cost_ledger = getattr(self, "cost_ledger", None)
            accounting_context = (
                cost_ledger.new_operation(
                    stage="agent_execution",
                    subtask_id=(str(kwargs["subtask_id"]) if kwargs.get("subtask_id") else None),
                    subtask_revision=(
                        int(kwargs.get("subtask_revision", 0))
                        if kwargs.get("subtask_id")
                        else None
                    ),
                    selected_resource_id=str(agent_id),
                    model_resource_id=kwargs.get("base_model_resource_id"),
                    agent_id=str(agent_id),
                )
                if cost_ledger is not None
                else None
            )
            response, transport_audit = await _request_with_transport_retry(
                self.transport,
                api_kwargs,
                max_attempts=max_retries,
                model_payload_guard=kwargs.get("model_payload_guard"),
                cost_ledger=cost_ledger,
                accounting_context=accounting_context,
            )
        except _TransportRequestFailure as exc:
            failure = exc.failure
            message = str(exc.original)
            secondary_audit_failures = list(exc.secondary_audit_failures)
            secondary_audit_failures.extend(_safe_capability_error_audit(
                str(base_model),
                failure["failure_type"],
                message,
            ))
            latency = (time.time() - start) * 1000
            return ExecutionResult(
                is_success=False,
                output_data="",
                error_log=message,
                cost_metric={
                    "latency_ms": latency,
                    "agent_id": agent_id,
                    "base_model": base_model,
                    "failure_type": failure["failure_type"],
                    "failure_message": message,
                    "attempt_count": exc.audit["attempt_count"],
                    "retry_events": [],
                    "failure_layer": failure["responsibility"],
                    "failure": failure,
                    "transport_audit": exc.audit,
                    "model_accounting_reference": exc.accounting_reference,
                    "secondary_audit_failures": secondary_audit_failures,
                    "model_media_projection": model_media_audit,
                },
            )

        pieces: list[str] = []
        token_usage: Dict[str, Any] = {}
        finish_reason = None
        try:
            if use_stream:
                async for chunk in response:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta is not None and getattr(delta, "content", None):
                        pieces.append(delta.content)
                    if chunk.choices and chunk.choices[0].finish_reason:
                        finish_reason = chunk.choices[0].finish_reason
                    if hasattr(chunk, "usage") and chunk.usage:
                        token_usage = {
                            "prompt_tokens": getattr(chunk.usage, "prompt_tokens", 0),
                            "completion_tokens": getattr(chunk.usage, "completion_tokens", 0),
                            "cached_tokens": getattr(
                                getattr(chunk.usage, "prompt_tokens_details", None),
                                "cached_tokens",
                                0,
                            ),
                        }
                GLOBAL_CAPABILITY_REGISTRY.record_success(str(base_model), "streaming_ok")
            else:
                pieces.append(response.choices[0].message.content or "")
                finish_reason = response.choices[0].finish_reason
                if response.usage:
                    token_usage = {
                        "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                        "completion_tokens": getattr(response.usage, "completion_tokens", 0),
                        "cached_tokens": getattr(
                            getattr(response.usage, "prompt_tokens_details", None),
                            "cached_tokens",
                            0,
                        ),
                    }
        except Exception as exc:
            # The provider returned a response object.  Parsing or streaming
            # failures are terminal research outcomes, never transport retries.
            request_hash = transport_audit["request_hashes"][0]
            failure = _failure_record(
                failure_stage="downstream_agent_response",
                responsibility="research",
                retryable=False,
                transport_attempt=transport_audit["attempt_count"],
                request_hash=request_hash,
                response_received=True,
                failure_type="agent_response_processing_failed",
            )
            message = str(exc)
            GLOBAL_CAPABILITY_REGISTRY.record_error(
                str(base_model),
                failure["failure_type"],
                message,
            )
            latency = (time.time() - start) * 1000
            return ExecutionResult(
                is_success=False,
                output_data="",
                error_log=message,
                cost_metric={
                    "latency_ms": latency,
                    "agent_id": agent_id,
                    "base_model": base_model,
                    "failure_type": failure["failure_type"],
                    "failure_message": message,
                    "attempt_count": transport_audit["attempt_count"],
                    "retry_events": [],
                    "failure_layer": "research",
                    "failure": failure,
                    "transport_audit": transport_audit,
                    "model_accounting_reference": getattr(
                        response, "accounting_reference", None
                    ),
                    "model_media_projection": model_media_audit,
                },
            )

        raw = "".join(pieces)
        clean = (
            SmartExecutor._clean_output(raw, artifact_type)
            if allow_semantic_normalization
            else raw
        )
        latency = (time.time() - start) * 1000
        if finish_reason == "length":
            request_hash = transport_audit["request_hashes"][0]
            failure = _failure_record(
                failure_stage="downstream_agent_response",
                responsibility="research",
                retryable=False,
                transport_attempt=transport_audit["attempt_count"],
                request_hash=request_hash,
                response_received=True,
                failure_type="provider_truncation",
            )
            return ExecutionResult(
                is_success=False,
                output_data="",
                error_log="finish_reason=length",
                cost_metric={
                    "latency_ms": latency,
                    "agent_id": agent_id,
                    "base_model": base_model,
                    "failure_type": failure["failure_type"],
                    "failure_message": "finish_reason=length",
                    "attempt_count": transport_audit["attempt_count"],
                    "retry_events": [],
                    "failure_layer": "research",
                    "failure": failure,
                    "transport_audit": transport_audit,
                    "model_accounting_reference": getattr(
                        response, "accounting_reference", None
                    ),
                    "model_media_projection": model_media_audit,
                },
            )

        format_valid, format_reason = _validate_enforced_output(
            clean,
            format_enforcement,
        )
        if not format_valid:
            request_hash = transport_audit["request_hashes"][0]
            failure = _failure_record(
                failure_stage="downstream_agent_response",
                responsibility="research",
                retryable=False,
                transport_attempt=transport_audit["attempt_count"],
                request_hash=request_hash,
                response_received=True,
                failure_type="agent_output_schema_invalid",
            )
            return ExecutionResult(
                is_success=False,
                output_data="",
                error_log=str(format_reason or "agent_output_schema_invalid"),
                cost_metric={
                    "latency_ms": latency,
                    "agent_id": agent_id,
                    "base_model": base_model,
                    "failure_type": failure["failure_type"],
                    "failure_layer": "research",
                    "failure": failure,
                    "attempt_count": transport_audit["attempt_count"],
                    "transport_audit": transport_audit,
                    "format_enforcement_mode": format_enforcement[
                        "selected_enforcement_mode"
                    ],
                    "format_contract_sha256": format_enforcement[
                        "format_contract_sha256"
                    ],
                    "model_accounting_reference": getattr(
                        response, "accounting_reference", None
                    ),
                    "model_media_projection": model_media_audit,
                },
            )

        clean = _normalize_enforced_root_value(clean, format_enforcement)
        GLOBAL_CAPABILITY_REGISTRY.record_success(str(base_model), "text_ok")
        if json_mode_requested:
            GLOBAL_CAPABILITY_REGISTRY.record_success(str(base_model), "json_mode_ok")
        logger.info(
            "[AgentExecutor] agent={} | base_model={} | done in {:.0f}ms",
            agent_id,
            base_model,
            latency,
        )
        return ExecutionResult(
            is_success=True,
            output_data=clean,
            error_log=None,
            cost_metric={
                "latency_ms": latency,
                "agent_id": agent_id,
                "base_model": base_model,
                "token_usage": token_usage,
                "json_mode_requested": json_mode_requested,
                "prompt_only_json": json_artifact and force_prompt_json,
                "format_enforcement_mode": (
                    format_enforcement["selected_enforcement_mode"]
                    if format_enforcement is not None
                    else None
                ),
                "format_contract_sha256": (
                    format_enforcement["format_contract_sha256"]
                    if format_enforcement is not None
                    else None
                ),
                "temperature_requested": kwargs.get("temperature", 0.3),
                "temperature_control": (
                    "supported"
                    if GLOBAL_CAPABILITY_REGISTRY.get(str(base_model)).temperature_ok is True
                    else "unsupported"
                    if GLOBAL_CAPABILITY_REGISTRY.get(str(base_model)).temperature_ok is False
                    else "unknown_omitted"
                ),
                "attempt_count": transport_audit["attempt_count"],
                "retry_events": [],
                "failure_layer": "none",
                "semantic_normalization_applied": allow_semantic_normalization,
                "transport_audit": transport_audit,
                "model_accounting_reference": getattr(
                    response, "accounting_reference", None
                ),
                "model_media_projection": model_media_audit,
            },
        )


def formal_executor_static_material() -> Dict[str, Any]:
    """Versioned static prompt/request material for formal Model and Agent calls.

    Dynamic task, Plan, candidate, manifest, and upstream-output material is
    registered separately.  This envelope contains only framework-owned prompt
    templates and fixed-pass request controls, so low-entropy literals such as
    ``0``, ``false``, or ``4096`` cannot be mistaken for hidden evaluator data.
    """

    return {
        "protocol": "formal-executor-static-material-v1",
        "controller_prompt_template": ControllerTurnExecutor._SYSTEM_PROMPT,
        "controller_stage_b_authority": {
            "callable_tool_scope": [],
            "dynamic_argument_authority": "none",
            "tool_result_continuation": "disabled",
        },
        "smart_prompt_template": SmartExecutor._PROMPT_TEMPLATE,
        "smart_fixed_fragments": [
            "--- Final Output Contract ---",
            "Follow the task expected_output exactly.",
            "Output the complete final artifact only. Do not output greetings, explanations, <think> blocks, local-path access disclaimers, patch/diff fragments, placeholder imports, placeholder paths, or TODO stubs.",
            "JSON compatibility note: this model is known or suspected not to support provider JSON mode. Return a single valid JSON object as plain text.",
        ],
        "agent_fixed_fragments": [
            "You are executing as an S-GAR prompt-agent. Follow the Agent Card, respect only the runtime inputs explicitly bound by the ResourceApplicationPlan, and output only the requested artifact. Dependency names in the Agent Card are non-exhaustive compatibility hints, not proof that a dependency was executed. Never claim a Tool ran unless its actual result is present in the bound inputs.",
            "No bound dependency resources.",
            "No additional plan-bound runtime inputs.",
            "Task:",
            "Expected artifact type:",
            "Expected output contract:",
            "Upstream DAG context:",
            "Bound dependency resources:",
            "Plan-bound runtime inputs:",
            "--- Final Output Contract ---",
            "Output the complete final artifact only. Do not output greetings, explanations, <think> blocks, local-path access disclaimers, or patch/diff fragments.",
            "JSON compatibility note: this base model is known or suspected not to support provider JSON mode. Return one valid JSON object as plain text.",
        ],
        "formal_request_controls": {
            "transport_attempt_max": 3,
            "max_tokens": 4096,
            "temperature": 0.0,
            "stream": False,
            "response_format": {"type": "json_object"},
        },
    }
