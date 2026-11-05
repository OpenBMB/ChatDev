"""Bounded Controller Session contracts and deterministic state machine.

Stage B deliberately exposes no callable Tool surface.  This module owns the
session loop, final-contract validation, bounded validation feedback, and
host-free evidence; provider transport remains in ``ControllerTurnExecutor``.
"""

from __future__ import annotations

from . import terminal_progress

import asyncio
import ast
import hashlib
import json
import math
import os
import posixpath
import re
import shlex
import time
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Any, Awaitable, Callable, Literal, Mapping, Protocol, Sequence

from pydantic import Field, PrivateAttr, field_validator, model_serializer, model_validator

from .controller_tooling import (
    ControllerCallableToolSpecV1,
    project_provider_tool_schema,
    require_unique_provider_tool_names,
)
from .controller_tool_runtime import (
    CONTROLLER_TOOL_RUNTIME_PROTOCOL,
    ControllerToolCallIntentV1,
    ControllerToolInvocationResultV1,
    ControllerToolRuntimeError,
    ControllerToolTerminalContext,
    prevalidate_tool_call_intents,
)
from .model_response_contracts import (
    ModelResponseContractError,
    normalize_portable_wire_instance,
    require_semantic_json_schema,
    strict_json_loads,
    validate_json_schema_instance,
)
from .pipeline_control import FrozenContract, canonical_json_bytes, canonical_sha256
from .terminal_failure import TerminalFailureEnvelope
from .text_format_contract import authoritative_exact_final_literal
from .controller_skills import ControllerSkillError, SkillContextBundleV1, validate_skill_snapshot
from .path_policy import is_private_host_path_value
from .required_operation_evidence import required_operation_evidence_failure
from .model_request_budget import model_completion_window


CONTROLLER_SESSION_POLICY_PROTOCOL = "sgar-controller-session-policy-v1"
CONTROLLER_SESSION_PROTOCOL = "sgar-controller-session-v1"
CONTROLLER_SESSION_V2_PROTOCOL = "sgar-controller-session-v2"
CONTROLLER_INPUT_SNAPSHOT_PROTOCOL = "sgar-controller-input-snapshot-v1"
CONTROLLER_TURN_PROTOCOL = "sgar-controller-turn-v1"
CONTROLLER_VALIDATION_FEEDBACK_PROTOCOL = "sgar-controller-validation-feedback-v1"
CONTROLLER_SESSION_RESULT_PROTOCOL = "sgar-controller-session-result-v2"
CONTROLLER_SESSION_SUMMARY_PROTOCOL = "sgar-controller-session-summary-v1"
CONTROLLER_SESSION_SUMMARY_V2_PROTOCOL = "sgar-controller-session-summary-v2"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MAX_FEEDBACK_REASON_BYTES = 1024
_TOOL_CONTROLLER_OUTPUT_CAP = 12_288

# These failures describe model-authored calls rejected before dispatch.
# Exhausting their existing correction budget is an execution/model failure,
# not a broken runtime binding or a changed sealed Tool identity.
_REPAIRABLE_PROVIDER_TOOL_FAILURES = frozenset({
    # Normalization validates the complete action batch before any dispatch.
    "controller_provider_tool_name_missing",
    "controller_provider_tool_call_id_missing",
    "controller_provider_tool_call_id_duplicate",
    "controller_tool_call_not_authorized",
    "controller_tool_arguments_json_invalid",
    "controller_tool_arguments_not_object",
    "controller_tool_dynamic_argument_undeclared",
    "controller_tool_dynamic_argument_required_missing",
    "controller_tool_dynamic_argument_contract_mismatch",
    "controller_tool_fixed_argument_override",
})


class ControllerSessionError(ValueError):
    """A sealed session contract or deterministic state invariant failed."""


def _require_sha256(value: str, *, field_name: str) -> str:
    normalized = str(value or "").strip().lower()
    if not _SHA256.fullmatch(normalized):
        raise ValueError(f"{field_name}_must_be_sha256_hex")
    return normalized


def _host_path_locator(value: Any, locator: str = "$") -> str | None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            found = _host_path_locator(item, f"{locator}.{key}")
            if found:
                return found
        return None
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found = _host_path_locator(item, f"{locator}[{index}]")
            if found:
                return found
        return None
    if isinstance(value, str) and is_private_host_path_value(value):
        return locator
    return None


def _ensure_host_free(value: Any, *, field_name: str) -> Any:
    locator = _host_path_locator(value)
    if locator:
        raise ValueError(f"{field_name}_contains_host_path:{locator}")
    return value


def _canonical_value(value: Any) -> Any:
    return json.loads(canonical_json_bytes(value).decode("utf-8"))


class ControllerSessionPolicyV1(FrozenContract):
    """System-owned exploration budget; never supplied by Planner/Compiler."""

    protocol: Literal[CONTROLLER_SESSION_POLICY_PROTOCOL] = (
        CONTROLLER_SESSION_POLICY_PROTOCOL
    )
    max_turns: int = Field(ge=1)
    max_tool_calls: int = Field(ge=0)
    max_semantic_repairs: int = Field(ge=0)
    max_same_call_repeats: int = Field(ge=1)
    max_same_failure_repeats: int = Field(ge=1)
    max_inline_tool_result_bytes: int = Field(ge=1)
    cost_authority: Literal["existing_run_cost_policy"] = "existing_run_cost_policy"
    policy_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "ControllerSessionPolicyV1":
        projection = self.model_dump(mode="python", exclude={"policy_sha256"})
        expected = canonical_sha256(projection)
        if self.policy_sha256:
            supplied = _require_sha256(
                self.policy_sha256, field_name="controller_session_policy_sha256"
            )
            if supplied != expected:
                raise ValueError("controller_session_policy_sha256_mismatch")
        object.__setattr__(self, "policy_sha256", expected)
        return self


def load_controller_session_policy(
    path: str | Path | None = None,
) -> ControllerSessionPolicyV1:
    """Load the single committed policy with strict validation and sealing."""

    policy_path = (
        Path(path)
        if path is not None
        else Path(__file__).resolve().parents[1]
        / "config"
        / "controller_session_policy.json"
    )
    try:
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ControllerSessionError("controller_session_policy_load_failed") from exc
    try:
        return ControllerSessionPolicyV1.model_validate(payload)
    except (TypeError, ValueError) as exc:
        raise ControllerSessionError("controller_session_policy_invalid") from exc


class ControllerContextBindingV1(FrozenContract):
    """An exact material binding derived from the Compiler's authorized input."""

    target_port: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    handle_id: str = Field(min_length=1)
    content_sha256: str

    @model_validator(mode="after")
    def _identity(self) -> "ControllerContextBindingV1":
        _ensure_host_free(self.model_dump(mode="python"), field_name="controller_context_binding")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.:-]*", self.target_port):
            raise ValueError("controller_context_port_invalid")
        if not self.source_id.startswith("artifact:") or self.source_id != self.source_id.strip():
            raise ValueError("controller_context_source_identity_invalid")
        _require_sha256(self.content_sha256, field_name="controller_context_content_sha256")
        return self


class ContextBoundContract(FrozenContract):
    """Internal material wiring; absent bindings retain historical serialization."""

    context_bindings: tuple[ControllerContextBindingV1, ...] = ()

    @model_serializer(mode="wrap")
    def _serialize_context(self, handler: Any) -> dict[str, Any]:
        result = handler(self)
        if not self.context_bindings:
            result.pop("context_bindings", None)
        return result

    @model_validator(mode="after")
    def _context_ports(self) -> "ContextBoundContract":
        identities = tuple((item.target_port, item.source_id, item.handle_id, item.content_sha256)
                           for item in self.context_bindings)
        if identities != tuple(sorted(set(identities))) or len(set(
            (item.target_port, item.source_id) for item in self.context_bindings
        )) != len(identities):
            raise ValueError("controller_context_binding_duplicate_or_not_canonical")
        sources: dict[str, tuple[str, str]] = {}
        for item in self.context_bindings:
            identity = (item.handle_id, item.content_sha256)
            if item.source_id in sources and sources[item.source_id] != identity:
                raise ValueError("controller_context_source_identity_ambiguous")
            sources[item.source_id] = identity
        # A declared value and one or more sealed context materials may target
        # the same Model/Agent port.  They remain separate channels in the plan
        # and receive collision-free descriptor names in the controller input
        # snapshot; neither channel overwrites or relabels the other.
        return self


class ControllerSessionSpecV1(ContextBoundContract):
    """Framework-derived plan authority for one Model or Agent controller."""

    protocol: Literal[CONTROLLER_SESSION_PROTOCOL] = CONTROLLER_SESSION_PROTOCOL
    subtask_id: str = Field(min_length=1)
    subtask_revision: int = Field(ge=0)
    controller_step_id: str = Field(min_length=1)
    controller_resource_id: str = Field(min_length=1)
    controller_resource_type: Literal["Model", "Agent"]
    backing_model_resource_id: str = Field(min_length=1)
    task_instruction: str = Field(min_length=1)
    declared_input_bindings: dict[str, Any] = Field(default_factory=dict)
    expected_output_contract: dict[str, Any]
    controller_session_policy_sha256: str
    callable_tool_scope: tuple[str, ...] = ()
    dynamic_argument_authority: Literal["none"] = "none"
    tool_result_continuation: Literal["disabled"] = "disabled"
    spec_sha256: str = ""

    @field_validator("controller_session_policy_sha256")
    @classmethod
    def _policy_hash(cls, value: str) -> str:
        return _require_sha256(value, field_name="controller_session_policy_sha256")

    @model_validator(mode="before")
    @classmethod
    def _canonicalize(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        projection = _canonical_value(dict(value))
        _ensure_host_free(projection, field_name="controller_session_spec")
        return projection

    @model_validator(mode="after")
    def _seal(self) -> "ControllerSessionSpecV1":
        if self.controller_resource_type == "Model" and (
            self.backing_model_resource_id != self.controller_resource_id
        ):
            raise ValueError("model_controller_backing_model_identity_mismatch")
        if self.callable_tool_scope:
            raise ValueError("controller_stage_b_tool_scope_must_be_empty")
        projection = self.model_dump(mode="python", exclude={"spec_sha256"})
        expected = canonical_sha256(projection)
        if self.spec_sha256:
            supplied = _require_sha256(
                self.spec_sha256, field_name="controller_session_spec_sha256"
            )
            if supplied != expected:
                raise ValueError("controller_session_spec_sha256_mismatch")
        object.__setattr__(self, "spec_sha256", expected)
        return self


class ControllerSessionSpecV2(ContextBoundContract):
    """Non-empty callable scope sealed for the future Stage-C2 runtime."""

    protocol: Literal[CONTROLLER_SESSION_V2_PROTOCOL] = CONTROLLER_SESSION_V2_PROTOCOL
    subtask_id: str = Field(min_length=1)
    subtask_revision: int = Field(ge=0)
    controller_step_id: str = Field(min_length=1)
    controller_resource_id: str = Field(min_length=1)
    controller_resource_type: Literal["Model", "Agent"]
    backing_model_resource_id: str = Field(min_length=1)
    task_instruction: str = Field(min_length=1)
    declared_input_bindings: dict[str, Any] = Field(default_factory=dict)
    expected_output_contract: dict[str, Any]
    controller_session_policy_sha256: str
    callable_tool_scope: tuple[str, ...]
    callable_tools: tuple[ControllerCallableToolSpecV1, ...]
    dynamic_argument_authority: Literal["sealed_callable_tool_contracts"] = (
        "sealed_callable_tool_contracts"
    )
    tool_result_continuation: Literal["enabled"] = "enabled"
    spec_sha256: str = ""

    @field_validator("controller_session_policy_sha256")
    @classmethod
    def _policy_hash(cls, value: str) -> str:
        return _require_sha256(value, field_name="controller_session_policy_sha256")

    @model_validator(mode="before")
    @classmethod
    def _canonicalize(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        projection = _canonical_value(dict(value))
        _ensure_host_free(projection, field_name="controller_session_spec_v2")
        return projection

    @model_validator(mode="after")
    def _seal(self) -> "ControllerSessionSpecV2":
        if self.controller_resource_type == "Model" and (
            self.backing_model_resource_id != self.controller_resource_id
        ):
            raise ValueError("model_controller_backing_model_identity_mismatch")
        if not self.callable_tools:
            raise ValueError("controller_session_v2_callable_scope_empty")
        if self.callable_tools != tuple(
            sorted(self.callable_tools, key=lambda item: item.callable_id)
        ):
            raise ValueError("controller_callable_tools_not_canonical")
        callable_ids = tuple(item.callable_id for item in self.callable_tools)
        if callable_ids != tuple(sorted(set(callable_ids))):
            raise ValueError("controller_callable_tool_identity_duplicate")
        if self.callable_tool_scope != callable_ids:
            raise ValueError("controller_callable_tool_scope_identity_mismatch")
        require_unique_provider_tool_names(self.callable_tools)
        projection = self.model_dump(mode="python", exclude={"spec_sha256"})
        expected = canonical_sha256(projection)
        if self.spec_sha256:
            supplied = _require_sha256(
                self.spec_sha256, field_name="controller_session_spec_sha256"
            )
            if supplied != expected:
                raise ValueError("controller_session_spec_sha256_mismatch")
        object.__setattr__(self, "spec_sha256", expected)
        return self


ControllerSessionSpec = ControllerSessionSpecV1 | ControllerSessionSpecV2


def derive_controller_session_spec(
    *,
    subtask_id: str,
    subtask_revision: int,
    controller_step_id: str,
    controller_resource_id: str,
    controller_resource_type: str,
    backing_model_resource_id: str | None,
    task_instruction: str,
    declared_input_bindings: Mapping[str, Any],
    expected_output_contract: Mapping[str, Any],
    policy: ControllerSessionPolicyV1 | None = None,
    callable_tools: Sequence[ControllerCallableToolSpecV1] = (),
    context_bindings: Sequence[ControllerContextBindingV1] = (),
) -> ControllerSessionSpec:
    active_policy = policy or load_controller_session_policy()
    if controller_resource_type not in {"Model", "Agent"}:
        raise ControllerSessionError("controller_resource_not_authorized")
    backing = (
        controller_resource_id
        if controller_resource_type == "Model"
        else str(backing_model_resource_id or "").strip()
    )
    if not backing:
        raise ControllerSessionError("controller_backing_model_not_ready")
    shared = {
        "subtask_id": subtask_id,
        "subtask_revision": subtask_revision,
        "controller_step_id": controller_step_id,
        "controller_resource_id": controller_resource_id,
        "controller_resource_type": controller_resource_type,
        "backing_model_resource_id": backing,
        "task_instruction": task_instruction,
        "declared_input_bindings": dict(declared_input_bindings),
        "context_bindings": tuple(context_bindings),
        "expected_output_contract": dict(expected_output_contract),
        "controller_session_policy_sha256": active_policy.policy_sha256,
    }
    if callable_tools:
        sealed_tools = tuple(sorted(callable_tools, key=lambda item: item.callable_id))
        require_unique_provider_tool_names(sealed_tools)
        return ControllerSessionSpecV2(
            **shared,
            callable_tool_scope=tuple(item.callable_id for item in sealed_tools),
            callable_tools=sealed_tools,
        )
    return ControllerSessionSpecV1(
        **shared,
    )


class ControllerInputDescriptorV1(FrozenContract):
    name: str = Field(min_length=1)
    binding_sha256: str
    content_sha256: str
    content_bytes: int = Field(ge=0)
    bounded_content: Any
    artifact_refs: tuple[str, ...] = ()
    logical_refs: tuple[str, ...] = ()

    @field_validator("binding_sha256", "content_sha256")
    @classmethod
    def _hash(cls, value: str, info: Any) -> str:
        return _require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _host_free(self) -> "ControllerInputDescriptorV1":
        _ensure_host_free(
            self.model_dump(mode="python"), field_name="controller_input_descriptor"
        )
        return self


class ControllerSessionInputSnapshotV1(FrozenContract):
    protocol: Literal[CONTROLLER_INPUT_SNAPSHOT_PROTOCOL] = (
        CONTROLLER_INPUT_SNAPSHOT_PROTOCOL
    )
    session_id: str = Field(min_length=1)
    spec_sha256: str
    resolved_input_descriptors: tuple[ControllerInputDescriptorV1, ...]
    provenance_identities: tuple[str, ...] = ()
    snapshot_sha256: str = ""

    @field_validator("spec_sha256")
    @classmethod
    def _spec_hash(cls, value: str) -> str:
        return _require_sha256(value, field_name="controller_session_spec_sha256")

    @model_validator(mode="after")
    def _seal(self) -> "ControllerSessionInputSnapshotV1":
        names = tuple(item.name for item in self.resolved_input_descriptors)
        if names != tuple(sorted(set(names))):
            raise ValueError("controller_input_snapshot_names_not_unique_sorted")
        if self.provenance_identities != tuple(
            sorted(set(self.provenance_identities))
        ):
            raise ValueError("controller_input_provenance_not_unique_sorted")
        projection = self.model_dump(mode="python", exclude={"snapshot_sha256"})
        _ensure_host_free(projection, field_name="controller_input_snapshot")
        expected = canonical_sha256(projection)
        if self.snapshot_sha256:
            supplied = _require_sha256(
                self.snapshot_sha256, field_name="controller_input_snapshot_sha256"
            )
            if supplied != expected:
                raise ValueError("controller_input_snapshot_sha256_mismatch")
        object.__setattr__(self, "snapshot_sha256", expected)
        return self


def _binding_refs(value: Any) -> tuple[tuple[str, ...], tuple[str, ...]]:
    artifacts: set[str] = set()
    logical: set[str] = set()

    def visit(item: Any, key: str | None = None) -> None:
        if isinstance(item, Mapping):
            for child_key, child in item.items():
                visit(child, str(child_key))
        elif isinstance(item, (list, tuple)):
            for child in item:
                visit(child, key)
        elif isinstance(item, str) and item.startswith("artifact:"):
            artifacts.add(item)
        elif isinstance(item, str) and key in {
            "path",
            "logical_path",
            "logical_locator",
            "semantic_ref",
        }:
            logical.add(item)

    visit(value)
    return tuple(sorted(artifacts)), tuple(sorted(logical))


class _BoundedHTMLText(HTMLParser):
    """Extract visible page text without executing or fetching any content."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.hidden_depth += 1
        elif tag in {"p", "div", "section", "article", "li", "br", "h1", "h2", "h3", "h4", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.hidden_depth = max(0, self.hidden_depth - 1)
        elif tag in {"p", "div", "section", "article", "li", "h1", "h2", "h3", "h4", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
            self.parts.append(data)


def _original_query_for_evidence(task_context: str, *, fallback: str) -> str:
    """Use the public objective as the main evidence query when it is sealed."""
    marker = "[Original User Query]\n"
    if marker not in task_context:
        return fallback
    query = task_context.split(marker, 1)[1].split("\n\n[", 1)[0].strip()
    return query or fallback


def _bounded_web_evidence_input(
    value: Any, *, task: str, max_bytes: int, secondary_task: str = "",
) -> Any:
    """Project an oversized fetched HTML body into labelled, query-relevant evidence.

    The full native Tool result stays in the execution ledger. This projection is
    explicitly partial and carries a digest of the source body; it cannot be used
    to prove that absent text does not occur elsewhere in the page.
    """
    if len(canonical_json_bytes(value)) <= max_bytes:
        return value
    try:
        envelope = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError):
        return value
    if not isinstance(envelope, dict) or not isinstance(envelope.get("body"), str):
        return value
    body = envelope["body"]
    headers = envelope.get("headers")
    media_type = str(headers.get("content-type", "")).lower() if isinstance(headers, dict) else ""
    if not ("text/html" in media_type or body.lstrip().lower().startswith(("<!doctype html", "<html"))):
        return value
    if not isinstance(envelope.get("url"), str) or not envelope.get("url"):
        return value
    parser = _BoundedHTMLText()
    parser.feed(body)
    visible = re.sub(r"[ \t]+", " ", "".join(parser.parts))
    visible = re.sub(r"\n\s*\n+", "\n", visible).strip()
    if not visible:
        return value
    stop = {"about", "after", "also", "answer", "based", "before", "command", "exactly", "final", "from", "have", "into", "name", "only", "other", "output", "page", "return", "source", "that", "their", "there", "this", "using", "verify", "which", "with"}
    width, stride = 1000, 700
    windows = [(start, visible[start:start + width]) for start in range(0, len(visible), stride)]
    def ranked_windows(query: str) -> list[tuple[int, str]]:
        terms = list(dict.fromkeys(
            token.lower()
            for token in re.findall(r"[A-Za-z][A-Za-z0-9_]{3,}|\d{4}", query)
            if token.lower() not in stop
        ))[:40]
        if not terms:
            return []
        frequencies = {
            term: sum(term in fragment.lower() for _, fragment in windows)
            for term in terms
        }
        return sorted(
            (item for item in windows if any(term in item[1].lower() for term in terms)),
            key=lambda item: (
                -sum(
                    1.0 + math.log((len(windows) + 1) / (frequencies[term] + 1))
                    for term in terms if term in item[1].lower()
                ),
                item[0],
            ),
        )

    # The public question determines most excerpts. Compiler instructions may
    # add a narrower subgoal, but their output-format boilerplate cannot crowd
    # the question's evidence out of the bounded context.
    chosen: list[tuple[int, str]] = [(0, visible[:width])]
    primary_target = 11
    for ranking, target in (
        (ranked_windows(task), primary_target),
        (ranked_windows(secondary_task), 14),
    ):
        for item in ranking:
            if len(chosen) >= target:
                break
            if all(abs(item[0] - previous[0]) >= stride for previous in chosen):
                chosen.append(item)
    projected = dict(envelope)
    projected["body_projection"] = {
        "kind": "bounded_visible_html_excerpts_v2",
        "complete": False,
        "original_body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "original_body_bytes": len(body.encode("utf-8")),
        "visible_text_characters": len(visible),
        "warning": "Excerpts are partial. Verify claims from shown text; absence in excerpts does not prove absence from the source.",
    }
    while chosen:
        projected["body"] = "\n".join(
            f"[visible source characters {start}-{start + len(fragment)}]\n{fragment}"
            for start, fragment in sorted(chosen, key=lambda item: item[0])
        )
        serialized = canonical_json_bytes(projected).decode("utf-8")
        # Snapshot descriptors contain this JSON as a string, so their wire
        # size includes a second layer of quote and backslash escaping.
        if len(canonical_json_bytes(serialized)) <= max_bytes:
            return serialized
        chosen.pop(-1)
    return value


def _failed_tool_observation_guidance(
    recent_results: Sequence["ControllerToolInvocationResultV1"],
) -> dict[str, Any] | None:
    failed_routes = sorted(
        {
            (
                str(getattr(item.observation, "callable_id", "unknown_callable")),
                str(getattr(item.observation, "resource_id", "unknown_resource")),
                str(getattr(
                    item.observation,
                    "capability_operation_id",
                    "unknown_operation",
                )),
                str(
                    getattr(item.observation, "failure_code", None)
                    or "tool_observation_failed"
                ),
            )
            for item in recent_results
            if item.observation.status != "success"
        }
    )
    if not failed_routes:
        return None
    # Native, contract-validated diagnostics distinguish acquisition failure
    # from a program defect. Do not spend a generation rewriting working code
    # merely because an external endpoint could not be reached.
    network_diagnostics = []
    input_diagnostics = []
    for item in recent_results:
        if item.observation.status == "success":
            continue
        public = getattr(item.observation, "public_result", None)
        native = public.get("native_result") if isinstance(public, Mapping) else None
        if not isinstance(native, Mapping):
            continue
        reason = str(native.get("reason_code") or "")
        if reason in {"invalid_url", "url_policy_invalid", "url_syntax_invalid",
                      "url_destination_disallowed", "url_protocol_unsupported",
                      "destination_outside_workspace", "local_file_io_failed"}:
            input_diagnostics.append({"reason_code": reason})
        if (reason.startswith("network_") or reason in {
            "http_status_error", "response_too_large", "redirect_limit_exceeded", "redirect_limit",
        }):
            network_diagnostics.append({
                "reason_code": reason,
                **({"http_status": native["http_status"]} if "http_status" in native else {}),
            })
    if input_diagnostics and len(input_diagnostics) + len(network_diagnostics) == sum(
        item.observation.status != "success" for item in recent_results
    ):
        return {"role": "user", "content": json.dumps({
            "framework_progress_status": "tool_input_or_destination_failed",
            "latest_diagnostic": input_diagnostics[-1],
            "instruction": (
                "Use the returned reason to correct the Tool argument: supply a complete HTTP(S) URL "
                "as a plain string, without Markdown or surrounding quotes, derived from task input "
                "or observed discovery. A destination policy refusal is distinct from a network error; "
                "use an authorized destination/source, never bypass its policy. A local file IO error "
                "requires checking the declared workspace destination and write access, not changing "
                "working task code. Retry a revised action, not an unchanged failure; preserve all "
                "original source, date and delivery requirements. A download receipt is not read content."
            ),
        }, sort_keys=True, separators=(",", ":"))}
    if network_diagnostics and len(network_diagnostics) == sum(
        item.observation.status != "success" for item in recent_results
    ):
        return {"role": "user", "content": json.dumps({
            "framework_progress_status": "source_acquisition_failed",
            "latest_diagnostic": network_diagnostics[-1],
            "instruction": (
                "The fetch did not establish source evidence. For persistent network errors "
                "or 403/404, use another authorized source or discovery route; do not rewrite "
                "working task code or repeatedly extend the same timeout. For 429 respect "
                "server backoff. For response_too_large use supported bounded extraction, "
                "download/local processing, or an adequate declared byte limit. If available "
                "sources/tools are exhausted, report ready=false; never invent evidence."
            ),
        }, sort_keys=True, separators=(",", ":"))}
    if all(route[3] in {"declared_result_status_failure", "resource_process_failed"}
           for route in failed_routes):
        return {
            "role": "user",
            "content": json.dumps({
                "framework_progress_status": "task_execution_failed",
                "required_action_order": [
                    "inspect_the_returned_execution_diagnostic",
                    "correct_the_command_input_or_observed_task_state",
                    "verify_the_revised_action_with_a_bound_tool",
                ],
                "instruction": (
                    "The selected Tool returned a task execution failure, not proof that "
                    "its capability is unavailable. Use its diagnostic to correct the input, "
                    "program, or authorized task state. A revised action may use the same "
                    "bound Tool. Do not repeat an unchanged failed attempt, treat its output "
                    "as successful evidence, or claim completion without verification."
                ),
            }, sort_keys=True, separators=(",", ":")),
        }
    return {
        "role": "user",
        "content": json.dumps({
            "framework_progress_status": "tool_observation_failed",
            "failed_routes": [
                {
                    "callable_id": callable_id,
                    "resource_id": resource_id,
                    "capability_operation_id": capability_operation_id,
                    "failure_code": failure_code,
                }
                for (
                    callable_id,
                    resource_id,
                    capability_operation_id,
                    failure_code,
                ) in failed_routes
            ],
            "required_action_order": [
                "do_not_repeat_the_same_failed_callable_route",
                "select_a_bound_operation_compatible_with_the_observed_representation",
                "terminate_without_guessing_when_no_compatible_route_is_bound",
            ],
            "instruction": (
                "A failed Tool observation is not source evidence. Use a different "
                "authorized operation with compatible encoding or representation when "
                "one is bound. The listed callable route is blocked for the same failure "
                "class; changing only the path, query wording, or call label is not "
                "progress. Do not invoke the final mutator, guess, or claim completion "
                "while required source evidence remains unread."
            ),
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    }


def _tool_declared_recovery_diagnostic(
    results: Sequence["ControllerToolInvocationResultV1"],
    *, callable_id: str | None = None,
) -> str | None:
    """Carry the validated native business failure across outer plan recovery."""
    for item in reversed(results):
        observation = item.observation
        if (observation.status != "failure"
                or observation.failure_code != "declared_result_status_failure"
                or (callable_id is not None and observation.callable_id != callable_id)):
            continue
        public = observation.public_result
        native = public.get("native_result") if isinstance(public, Mapping) else None
        if isinstance(native, Mapping):
            return canonical_json_bytes({
                "failure_code": observation.failure_code,
                "native_result": dict(native),
            }).decode("utf-8")
    return None


def _tool_process_recovery_diagnostic(
    results: Sequence["ControllerToolInvocationResultV1"],
) -> str | None:
    """Return only the latest validated process diagnostic from Tool observations."""

    for item in reversed(results):
        observation = item.observation
        public = observation.public_result
        if observation.status != "failure" or not isinstance(public, Mapping):
            continue
        native = public.get("native_result")
        diagnostic = (
            native.get("process_diagnostic")
            if isinstance(native, Mapping)
            else None
        )
        if not isinstance(diagnostic, Mapping):
            continue
        return canonical_json_bytes({
            "failure_code": observation.failure_code,
            "process_diagnostic": dict(diagnostic),
        }).decode("utf-8")
    return None


def _tool_failure_route_fingerprint(
    result: "ControllerToolInvocationResultV1",
    *,
    dynamic_arguments_sha256: str | None = None,
) -> str:
    """Separate revised task actions from repeated capability incompatibility.

    Program/command failures depend on the supplied action and observed result;
    one generic nonzero-exit code must not block every repair through that Tool.
    Representation incompatibilities retain their existing route-level guard.
    """

    observation = result.observation
    if observation.status == "success":
        raise ValueError("successful_tool_result_has_no_failure_route")
    identity = {
        "callable_id": observation.callable_id,
        "failure_code": observation.failure_code,
        "failure_responsibility": observation.failure_responsibility,
    }
    if observation.failure_code in {"declared_result_status_failure", "resource_process_failed"}:
        identity.update(
            dynamic_arguments_sha256=dynamic_arguments_sha256,
            native_output_sha256=observation.native_output_sha256,
        )
    return canonical_sha256(identity)


def _project_tool_observation_for_model(
    observation: Mapping[str, Any], *, task: str, secondary_task: str,
    max_bytes: int,
) -> dict[str, Any]:
    """Keep a successful Tool result successful while bounding its context.

    The original observation and output digests remain unchanged.  The model
    receives labelled excerpts, so omitted content is never evidence of absence.
    """
    full = dict(observation)
    if len(canonical_json_bytes(full)) <= max_bytes:
        return full
    original = full.pop("public_result")
    full.update({
        "public_result_complete": False,
        "public_result_source_sha256": canonical_sha256(original),
        "public_result_source_bytes": len(canonical_json_bytes(original)),
        "public_result_projection_warning": (
            "Partial excerpts only. Do not infer absence from omitted content; "
            "request a narrower Tool result when more evidence is needed."
        ),
    })
    room = max_bytes - len(canonical_json_bytes(full)) - 96
    if room > 512:
        web = _bounded_web_evidence_input(
            original, task=task, secondary_task=secondary_task,
            max_bytes=room,
        )
        if web != original:
            full["public_result"] = web
            if len(canonical_json_bytes(full)) <= max_bytes:
                full["public_result_projection_kind"] = "bounded_web_evidence"
                if len(canonical_json_bytes(full)) <= max_bytes:
                    return full
                full.pop("public_result_projection_kind")
            full.pop("public_result", None)

    source = canonical_json_bytes(original).decode("utf-8")
    terms = set(re.findall(r"[A-Za-z][A-Za-z0-9_]{3,}|\d{4}",
                           task + " " + secondary_task, flags=re.IGNORECASE))
    terms = {term.casefold() for term in terms if term.casefold() not in {
        "about", "answer", "from", "into", "only", "output", "return",
        "source", "that", "this", "using", "which", "with",
    }}
    width, stride = 900, 750
    windows = [(i, source[i:i + width]) for i in range(0, len(source), stride)]
    ranked = sorted(windows[1:], key=lambda item: (
        -sum(term in item[1].casefold() for term in terms), item[0],
    ))
    chosen = windows[:1]
    for item in ranked:
        if len(chosen) >= 10:
            break
        if all(abs(item[0] - prior[0]) >= stride for prior in chosen):
            chosen.append(item)
    while chosen:
        full["public_result"] = {
            "kind": "bounded_tool_result_excerpts_v1",
            "excerpts": [
                {"start_character": start, "text": fragment}
                for start, fragment in sorted(chosen)
            ],
        }
        if len(canonical_json_bytes(full)) <= max_bytes:
            return full
        chosen.pop()
    full["public_result"] = {"kind": "tool_result_reference_only_v1"}
    return full


_CONTEXT_DESCRIPTOR_PREFIX = "__sgar_context__:"


def _context_descriptor_name(target_port: str, declared_names: set[str]) -> str:
    """Keep sealed context distinct when it shares a logical Model port."""

    if target_port not in declared_names:
        return target_port
    name = _CONTEXT_DESCRIPTOR_PREFIX + target_port
    if name in declared_names:
        raise ControllerSessionError("controller_context_descriptor_name_collision")
    return name


def build_controller_input_snapshot(
    *,
    run_id: str,
    spec: ControllerSessionSpec,
    resolved_inputs: Mapping[str, Any],
    policy: ControllerSessionPolicyV1,
    provenance_identities: Sequence[str] = (),
    resolved_context: Mapping[str, Any] | None = None,
) -> ControllerSessionInputSnapshotV1:
    if spec.controller_session_policy_sha256 != policy.policy_sha256:
        raise ControllerSessionError("controller_policy_identity_mismatch")
    declared_names = set(spec.declared_input_bindings)
    if set(resolved_inputs) != declared_names:
        raise ControllerSessionError("controller_input_contract_invalid")
    descriptors: list[ControllerInputDescriptorV1] = []
    context_values = dict(resolved_context or {})
    if set(context_values) != {item.source_id for item in spec.context_bindings}:
        raise ControllerSessionError("controller_context_material_missing_or_undeclared")
    port_bindings: dict[str, list[ControllerContextBindingV1]] = {}
    for binding in spec.context_bindings:
        port_bindings.setdefault(binding.target_port, []).append(binding)
    for port, bindings in sorted(port_bindings.items()):
        materials = []
        for binding in bindings:
            content = context_values[binding.source_id]
            if isinstance(content, str):
                raw = content.encode("utf-8")
                if hashlib.sha256(raw).hexdigest() != binding.content_sha256:
                    raise ControllerSessionError("controller_context_content_hash_mismatch")
                projected_content: Any = content
            elif isinstance(content, Mapping):
                projected_content = _canonical_value(content)
                _ensure_host_free(
                    projected_content,
                    field_name="controller_context_material",
                )
                if projected_content.get("delivery") != "sealed_model_media":
                    raise ControllerSessionError("controller_context_material_invalid")
                if projected_content.get("source_id") != binding.source_id:
                    raise ControllerSessionError("controller_context_source_identity_mismatch")
                if projected_content.get("content_sha256") != binding.content_sha256:
                    raise ControllerSessionError("controller_context_content_hash_mismatch")
                projected_handle = str(projected_content.get("handle_id") or "")
                if (
                    projected_handle.removeprefix("artifact:")
                    != binding.handle_id.removeprefix("artifact:")
                ):
                    raise ControllerSessionError("controller_context_source_identity_mismatch")
                if projected_content.get("coverage_status") != "handle_only":
                    raise ControllerSessionError("controller_context_material_invalid")
            else:
                raise ControllerSessionError("controller_context_material_not_utf8")
            materials.append({"source_id": binding.source_id,
                              "source_content_sha256": binding.content_sha256,
                              "content": projected_content})
        material = materials[0] if len(materials) == 1 else {"materials": materials}
        binding_identity = [item.model_dump(mode="json") for item in bindings]
        descriptors.append(ControllerInputDescriptorV1(
            name=_context_descriptor_name(port, declared_names),
            binding_sha256=canonical_sha256(binding_identity[0] if len(bindings) == 1 else binding_identity),
            content_sha256=canonical_sha256(material),
            content_bytes=len(canonical_json_bytes(material)),
            bounded_content=material,
            artifact_refs=tuple(item.source_id for item in bindings),
        ))
    for name in sorted(declared_names):
        content = _canonical_value(resolved_inputs[name])
        _ensure_host_free(content, field_name=f"controller_input:{name}")
        encoded = canonical_json_bytes(content)
        # Planned dependencies are required evidence. The inline Tool-result
        # budget controls optional observations, not declared Model inputs;
        # dropping or rejecting them here changes the executable Plan.
        binding = spec.declared_input_bindings[name]
        artifact_refs, logical_refs = _binding_refs(binding)
        descriptors.append(
            ControllerInputDescriptorV1(
                name=name,
                binding_sha256=canonical_sha256(binding),
                content_sha256=canonical_sha256(content),
                content_bytes=len(encoded),
                bounded_content=content,
                artifact_refs=artifact_refs,
                logical_refs=logical_refs,
            )
        )
    session_id = canonical_sha256(
        {
            "protocol": CONTROLLER_SESSION_PROTOCOL,
            "run_id": str(run_id),
            "spec_sha256": spec.spec_sha256,
        }
    )
    return ControllerSessionInputSnapshotV1(
        session_id=session_id,
        spec_sha256=spec.spec_sha256,
        resolved_input_descriptors=tuple(sorted(descriptors, key=lambda item: item.name)),
        provenance_identities=tuple(sorted(set(str(item) for item in provenance_identities))),
    )


class ControllerTurnResultV1(FrozenContract):
    protocol: Literal[CONTROLLER_TURN_PROTOCOL] = CONTROLLER_TURN_PROTOCOL
    session_id: str = Field(min_length=1)
    turn_id: str = Field(min_length=1)
    turn_index: int = Field(ge=1)
    status: Literal["success", "failure"]
    content: str = ""
    tool_calls: tuple[dict[str, Any], ...] = ()
    finish_reason: str | None = None
    transport_audit: dict[str, Any] = Field(default_factory=dict)
    token_usage: dict[str, Any] = Field(default_factory=dict)
    model_accounting_reference: dict[str, Any] | None = None
    request_sha256: str
    response_sha256: str
    candidate_sha256: str
    latency_ms: float = Field(ge=0)
    failure_code: str | None = None
    terminal_failure: TerminalFailureEnvelope | None = None

    @field_validator("request_sha256", "response_sha256", "candidate_sha256")
    @classmethod
    def _hash(cls, value: str, info: Any) -> str:
        return _require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _validate_result(self) -> "ControllerTurnResultV1":
        if self.status == "failure" and not self.failure_code:
            raise ValueError("controller_turn_failure_code_missing")
        if self.status == "success" and (self.failure_code or self.terminal_failure):
            raise ValueError("controller_turn_success_has_failure_code")
        _ensure_host_free(
            self.model_dump(mode="python"), field_name="controller_turn_result"
        )
        return self


class ValidationFeedbackV1(FrozenContract):
    protocol: Literal[CONTROLLER_VALIDATION_FEEDBACK_PROTOCOL] = (
        CONTROLLER_VALIDATION_FEEDBACK_PROTOCOL
    )
    target_contract_sha256: str
    error_path: str = Field(min_length=1)
    error_category: str = Field(min_length=1)
    bounded_reason: str = Field(min_length=1, max_length=1024)
    previous_candidate_sha256: str
    feedback_sha256: str = ""

    @field_validator("target_contract_sha256", "previous_candidate_sha256")
    @classmethod
    def _hash(cls, value: str, info: Any) -> str:
        return _require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _seal(self) -> "ValidationFeedbackV1":
        projection = self.model_dump(mode="python", exclude={"feedback_sha256"})
        _ensure_host_free(projection, field_name="controller_validation_feedback")
        expected = canonical_sha256(projection)
        if self.feedback_sha256:
            supplied = _require_sha256(
                self.feedback_sha256, field_name="validation_feedback_sha256"
            )
            if supplied != expected:
                raise ValueError("validation_feedback_sha256_mismatch")
        object.__setattr__(self, "feedback_sha256", expected)
        return self


class ControllerSessionSummaryV1(FrozenContract):
    protocol: Literal[CONTROLLER_SESSION_SUMMARY_PROTOCOL] = (
        CONTROLLER_SESSION_SUMMARY_PROTOCOL
    )
    session_id: str = Field(min_length=1)
    actual_turns: int = Field(ge=0)
    semantic_repairs: int = Field(ge=0)
    terminal_status: Literal["success", "failure"]
    terminal_failure_code: str | None = None
    elapsed_ms: float = Field(ge=0)
    controller_resource_id: str = Field(min_length=1)
    backing_model_resource_id: str = Field(min_length=1)
    input_snapshot_sha256: str
    policy_sha256: str
    model_accounting_references: tuple[dict[str, Any], ...] = ()
    summary_sha256: str = ""

    @field_validator("input_snapshot_sha256", "policy_sha256")
    @classmethod
    def _hash(cls, value: str, info: Any) -> str:
        return _require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _seal(self) -> "ControllerSessionSummaryV1":
        if self.terminal_status == "success" and self.terminal_failure_code:
            raise ValueError("successful_controller_summary_has_failure_code")
        if self.terminal_status == "failure" and not self.terminal_failure_code:
            raise ValueError("failed_controller_summary_missing_failure_code")
        projection = self.model_dump(mode="python", exclude={"summary_sha256"})
        _ensure_host_free(projection, field_name="controller_session_summary")
        expected = canonical_sha256(projection)
        if self.summary_sha256 and self.summary_sha256 != expected:
            raise ValueError("controller_session_summary_sha256_mismatch")
        object.__setattr__(self, "summary_sha256", expected)
        return self


class ControllerSessionSummaryV2(FrozenContract):
    """Additive C2 evidence without changing the sealed Stage-B V1 summary."""

    protocol: Literal[CONTROLLER_SESSION_SUMMARY_V2_PROTOCOL] = (
        CONTROLLER_SESSION_SUMMARY_V2_PROTOCOL
    )
    runtime_protocol: Literal[CONTROLLER_TOOL_RUNTIME_PROTOCOL] = (
        CONTROLLER_TOOL_RUNTIME_PROTOCOL
    )
    session_id: str = Field(min_length=1)
    actual_turns: int = Field(ge=0)
    semantic_repairs: int = Field(ge=0)
    terminal_status: Literal["success", "failure"]
    terminal_failure_code: str | None = None
    elapsed_ms: float = Field(ge=0)
    controller_resource_id: str = Field(min_length=1)
    backing_model_resource_id: str = Field(min_length=1)
    input_snapshot_sha256: str
    policy_sha256: str
    model_accounting_references: tuple[dict[str, Any], ...] = ()
    tool_call_count: int = Field(ge=0)
    tool_success_count: int = Field(ge=0)
    tool_failure_count: int = Field(ge=0)
    tool_observation_bytes: int = Field(ge=0)
    resource_call_ids: tuple[str, ...] = ()
    controller_tool_provenance_ids: tuple[str, ...] = ()
    tool_observation_sha256s: tuple[str, ...] = ()
    successful_tool_operation_ids: tuple[str, ...] = ()
    terminal_failure: ControllerToolTerminalContext | None = None
    failed_tool_attempts: tuple[ControllerToolTerminalContext, ...] = ()
    requested_tool_action_count: int = Field(default=0, ge=0)
    accepted_tool_action_count: int = Field(default=0, ge=0)
    evidence_incomplete: bool = False
    secondary_audit_failures: tuple[str, ...] = ()
    summary_sha256: str = ""

    @field_validator("input_snapshot_sha256", "policy_sha256")
    @classmethod
    def _hash(cls, value: str, info: Any) -> str:
        return _require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _seal(self) -> "ControllerSessionSummaryV2":
        if self.terminal_status == "success" and self.terminal_failure_code:
            raise ValueError("successful_controller_summary_has_failure_code")
        if self.terminal_status == "failure" and not self.terminal_failure_code:
            raise ValueError("failed_controller_summary_missing_failure_code")
        if self.tool_success_count + self.tool_failure_count != self.tool_call_count:
            raise ValueError("controller_tool_summary_count_mismatch")
        if not (
            len(self.resource_call_ids)
            == len(self.controller_tool_provenance_ids)
            == len(self.tool_observation_sha256s)
            <= self.tool_call_count
        ):
            raise ValueError("controller_tool_summary_reference_count_mismatch")
        if len(self.successful_tool_operation_ids) > self.tool_success_count:
            raise ValueError("controller_tool_success_operation_count_mismatch")
        projection = self.model_dump(mode="python", exclude={"summary_sha256"})
        _ensure_host_free(projection, field_name="controller_session_summary_v2")
        expected = canonical_sha256(projection)
        if self.summary_sha256 and self.summary_sha256 != expected:
            raise ValueError("controller_session_summary_sha256_mismatch")
        object.__setattr__(self, "summary_sha256", expected)
        return self


class ControllerSessionResultV1(FrozenContract):
    protocol: Literal[CONTROLLER_SESSION_RESULT_PROTOCOL] = (
        CONTROLLER_SESSION_RESULT_PROTOCOL
    )
    status: Literal["success", "failure"]
    output_data: str = ""
    failure_code: str | None = None
    terminal_failure: TerminalFailureEnvelope | None = None
    controller_session_spec_sha256: str
    controller_policy_sha256: str
    input_snapshot_sha256: str
    turns: tuple[ControllerTurnResultV1, ...] = ()
    validation_feedback: tuple[ValidationFeedbackV1, ...] = ()
    summary: ControllerSessionSummaryV1 | ControllerSessionSummaryV2
    result_sha256: str = ""
    # A bounded, already sanitized process diagnostic may be passed directly to
    # Recovery without becoming part of the sealed/public session artifact.
    # It is intentionally private so ledgers and summaries retain hashes and
    # failure identity rather than raw diagnostic text.
    _recovery_diagnostic: str | None = PrivateAttr(default=None)
    _recovery_execution_audit: dict[str, Any] | None = PrivateAttr(default=None)

    @field_validator(
        "controller_session_spec_sha256",
        "controller_policy_sha256",
        "input_snapshot_sha256",
    )
    @classmethod
    def _hash(cls, value: str, info: Any) -> str:
        return _require_sha256(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _seal(self) -> "ControllerSessionResultV1":
        if self.status == "success":
            if self.failure_code or self.terminal_failure or not self.turns:
                raise ValueError("successful_controller_session_result_invalid")
        elif not self.failure_code:
            raise ValueError("failed_controller_session_result_missing_code")
        projection = self.model_dump(mode="python", exclude={"result_sha256"})
        _ensure_host_free(projection, field_name="controller_session_result")
        expected = canonical_sha256(projection)
        if self.result_sha256 and self.result_sha256 != expected:
            raise ValueError("controller_session_result_sha256_mismatch")
        object.__setattr__(self, "result_sha256", expected)
        return self


class ControllerTurnExecutorPort(Protocol):
    async def execute_turn(self, **kwargs: Any) -> ControllerTurnResultV1: ...


class ControllerToolRuntimePort(Protocol):
    async def execute_tool_call(
        self,
        *,
        intent: ControllerToolCallIntentV1,
        max_inline_result_bytes: int,
    ) -> ControllerToolInvocationResultV1: ...


def _validation_feedback(
    *, target_contract: Mapping[str, Any], candidate_sha256: str, reason: str
) -> ValidationFeedbackV1:
    bounded = str(reason or "$:invalid")
    bounded = bounded.encode("utf-8", errors="replace")[:_MAX_FEEDBACK_REASON_BYTES].decode(
        "utf-8", errors="ignore"
    )
    parts = bounded.split(":")
    error_path = parts[0] if parts and parts[0] else "$"
    error_category = parts[1] if len(parts) > 1 and parts[1] else "invalid"
    return ValidationFeedbackV1(
        target_contract_sha256=canonical_sha256(target_contract),
        error_path=error_path,
        error_category=error_category,
        bounded_reason=bounded,
        previous_candidate_sha256=candidate_sha256,
    )


from .artifact_semantics import (
    OutputContractViolation,
    is_output_contract_echo,
    requires_content_contract_validation,
    validate_output_contract_content,
    validate_schema_document,
)


def _output_contract_violation_reason(path: str, exc: OutputContractViolation) -> str:
    reason = f"{path}:{exc.failure_code}"
    if exc.diagnostic:
        reason += f":{exc.diagnostic}"
    return reason


_CONTROLLER_TEXT_WRITE_OPERATIONS = frozenset({
    "write_complete_text_file",
    "write_text_file",
})


def _normalized_delivery_path(value: Any) -> str:
    return str(value or "").strip().replace("\\", "/").rstrip("/")


def required_controller_file_delivery_operation(
    *,
    callable_tools: Sequence[ControllerCallableToolSpecV1],
    delivery_scope: str,
    mandatory_output_files: Sequence[Mapping[str, Any]],
    prior_successful_operation_ids: Sequence[str] = (),
) -> dict[str, Any] | None:
    """Require the bound writer for one exact task-final file.

    A callable Tool being attached to a Controller step only proves that the
    Tool was available.  When the final delivery contract names one required
    file and the Compiler bound a text writer to that path, successful use of
    that writer is part of the executable contract rather than an optional
    Controller choice.
    """

    if delivery_scope != "task_final" or len(mandatory_output_files) != 1:
        return None
    required_file = mandatory_output_files[0]
    if not isinstance(required_file, Mapping) or required_file.get("required") is False:
        return None
    required_path = _normalized_delivery_path(required_file.get("path_hint"))
    if not required_path:
        return None
    prior = {str(item) for item in prior_successful_operation_ids}
    matching: list[ControllerCallableToolSpecV1] = []
    for item in callable_tools:
        operation_name = item.capability_operation_id.rsplit("::", 1)[-1]
        if operation_name not in _CONTROLLER_TEXT_WRITE_OPERATIONS:
            continue
        fixed = item.fixed_input_bindings.get("path")
        fixed_path = _normalized_delivery_path(
            fixed.get("literal")
            if isinstance(fixed, Mapping) and "literal" in fixed
            else None
        )
        if not fixed_path or not (
            fixed_path == required_path
            or fixed_path.endswith(f"/{required_path.lstrip('/')}")
        ):
            continue
        matching.append(item)
    if not matching or any(
        item.capability_operation_id in prior for item in matching
    ):
        return None
    return {
        "operation_kind": "required_file_delivery",
        "capability_operation_ids": [
            item.capability_operation_id for item in matching
        ],
        "function_names": [item.provider_tool_name for item in matching],
    }


def _controller_tool_argument(
    *,
    callable_tool: ControllerCallableToolSpecV1,
    intent: ControllerToolCallIntentV1,
    name: str,
) -> Any:
    fixed = callable_tool.fixed_input_bindings.get(name)
    if isinstance(fixed, Mapping) and "literal" in fixed:
        return fixed["literal"]
    return intent.normalized_dynamic_arguments.get(name)


class _ControllerInputRevisions:
    """Repeat identity follows successful text writes to relevant input paths.

    This is session-local bookkeeping, not additional Tool authority. Public
    call identities, paths and receipts remain unchanged. Unknown state keeps
    the existing repeat policy; unrelated or identical writes do not reset it.
    """

    def __init__(self, working_directory: str = "") -> None:
        self.working_directory = working_directory
        self.content_hashes: dict[str, str] = {}
        self.input_sources: dict[str, str] = {}
        self.source_read_attempts: set[str] = set()

    def _path(self, value: Any) -> str | None:
        if not isinstance(value, str) or not value.strip():
            return None
        path = PurePosixPath(value.replace("\\", "/"))
        if not path.is_absolute() and self.working_directory:
            path = PurePosixPath(self.working_directory) / path
        return posixpath.normpath(str(path))

    def _explicit_inputs(
        self, tool: ControllerCallableToolSpecV1, intent: ControllerToolCallIntentV1,
    ) -> set[str]:
        paths: set[str] = set()
        for port in getattr(tool, "operation_input_contract", ()):
            if str(port.get("kind") or port.get("type") or "") in {
                "path", "file_path", "directory_path",
            }:
                path = self._path(_controller_tool_argument(
                    callable_tool=tool, intent=intent, name=str(port.get("name") or ""),
                ))
                if path:
                    paths.add(path)
        if str(getattr(tool, "capability_operation_id", "")).rsplit("::", 1)[-1] != "execute_shell_commands":
            return paths
        script = _controller_tool_argument(callable_tool=tool, intent=intent, name="script")
        if not isinstance(script, str):
            return paths
        try:
            lexer = shlex.shlex(script, posix=True, punctuation_chars=";&|()\n")
            lexer.whitespace, lexer.whitespace_split = " \t\r", True
            directory = self.working_directory
            command_start, cd_argument = True, False
            for token in lexer:
                if token and all(char in ";&|()\n" for char in token):
                    command_start, cd_argument = True, False
                    continue
                if command_start and token == "cd":
                    cd_argument, command_start = True, False
                    continue
                if cd_argument:
                    if token == "--":
                        continue
                    directory = posixpath.normpath(
                        token if token.startswith("/") else posixpath.join(directory, token)
                    ) if not token.startswith("-") and not any(c in token for c in "$`~") else ""
                    cd_argument = False
                    continue
                command_start = False
                if any(c in token for c in "$`~") or token.startswith("-"):
                    continue
                path = self._path(token) if token.startswith("/") else (
                    posixpath.normpath(posixpath.join(directory, token)) if directory else None
                )
                if path and (path in self.content_hashes or "/" in token or PurePosixPath(token).suffix):
                    paths.add(path)
        except ValueError:
            pass
        return paths

    def _local_dependencies(self, path: str, source: str) -> set[str]:
        """Follow literal file references and local imports, never execute source."""
        directory = posixpath.dirname(path)
        dependencies: set[str] = set()
        if path.endswith(".py"):
            try:
                tree = ast.parse(source)
            except (SyntaxError, ValueError):
                return dependencies
            modules: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value:
                    candidate = posixpath.normpath(posixpath.join(directory, node.value))
                    if candidate in self.content_hashes:
                        dependencies.add(candidate)
                elif isinstance(node, ast.Import):
                    modules.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    base = directory
                    for _ in range(max(0, node.level - 1)):
                        base = posixpath.dirname(base)
                    prefix = (node.module or "").replace(".", "/")
                    for module in [prefix, *(posixpath.join(prefix, a.name) for a in node.names)]:
                        for candidate in (posixpath.join(base, module + ".py"),
                                          posixpath.join(base, module, "__init__.py")):
                            if candidate in self.input_sources:
                                dependencies.add(posixpath.normpath(candidate))
            for module in modules:
                for base in {directory, self.working_directory}:
                    if not base:
                        continue
                    stem = posixpath.join(base, module.replace(".", "/"))
                    for candidate in (stem + ".py", posixpath.join(stem, "__init__.py")):
                        if candidate in self.input_sources:
                            dependencies.add(posixpath.normpath(candidate))
        else:
            # Quoted includes are explicit local dependencies. System headers
            # and computed references are unknown, not inferred from filenames.
            for name in re.findall(r'^\s*#\s*include\s*"([^"\n]+)"', source, re.MULTILINE):
                candidate = posixpath.normpath(posixpath.join(directory, name))
                if candidate in self.input_sources:
                    dependencies.add(candidate)
        return dependencies

    async def capture_input_sources(
        self, tool: ControllerCallableToolSpecV1, intent: ControllerToolCallIntentV1,
        reader: Callable[[str], Awaitable[str | None]] | None,
    ) -> None:
        """Inspect only explicit consumer paths after a known workspace write.

        Original build/entry scripts can reference generated files without being
        rewritten themselves. Cache their source for dependency bookkeeping;
        unknown or unreadable source retains the ordinary repeat policy.
        """
        if reader is None or not self.content_hashes or (
            tool.capability_operation_id.rsplit("::", 1)[-1] in _CONTROLLER_TEXT_WRITE_OPERATIONS
        ):
            return
        for path in sorted(self._explicit_inputs(tool, intent)):
            # This reader supplies dependency source, not task data. Known
            # writer revisions remain tracked regardless of extension.
            if (path in self.input_sources or path in self.source_read_attempts
                    or (path not in self.content_hashes
                        and PurePosixPath(path).suffix.lower() not in {
                            ".py", ".c", ".h", ".cc", ".cpp", ".hpp"})):
                continue
            self.source_read_attempts.add(path)
            try:
                content = await reader(path)
            except Exception:
                continue  # Optional identity evidence is not a new execution gate.
            if isinstance(content, str):
                self.input_sources[path] = content

    def fingerprint(
        self, tool: ControllerCallableToolSpecV1, intent: ControllerToolCallIntentV1,
    ) -> str:
        if str(getattr(tool, "capability_operation_id", "")).rsplit("::", 1)[-1] in _CONTROLLER_TEXT_WRITE_OPERATIONS:
            # The destination is an output, not an input revision. Content is
            # already part of the sealed call fingerprint.
            return intent.call_fingerprint_sha256
        revisions = {}
        pending = list(self._explicit_inputs(tool, intent))
        visited: set[str] = set()
        while pending:
            path = pending.pop()
            if path in visited:
                continue
            visited.add(path)
            if path in self.content_hashes:
                revisions[path] = self.content_hashes[path]
            if path in self.input_sources:
                pending.extend(self._local_dependencies(path, self.input_sources[path]))
        if not revisions:
            return intent.call_fingerprint_sha256
        return canonical_sha256({
            "call_fingerprint_sha256": intent.call_fingerprint_sha256,
            "known_input_content_sha256s": revisions,
        })

    def observe(
        self, tool: ControllerCallableToolSpecV1, intent: ControllerToolCallIntentV1,
        result: ControllerToolInvocationResultV1,
    ) -> None:
        if result.observation.status != "success" or (
            tool.capability_operation_id.rsplit("::", 1)[-1]
            not in _CONTROLLER_TEXT_WRITE_OPERATIONS
        ):
            return
        path = self._path(_controller_tool_argument(
            callable_tool=tool, intent=intent, name="path",
        ))
        content = _controller_tool_argument(
            callable_tool=tool, intent=intent, name="content",
        )
        if path and isinstance(content, str):
            self.content_hashes[path] = hashlib.sha256(content.encode("utf-8")).hexdigest()
            self.input_sources[path] = content


def _validate_authoritative_controller_write_intents(
    *,
    intents: Sequence[ControllerToolCallIntentV1],
    callable_tools: Sequence[ControllerCallableToolSpecV1],
    controller_context: Mapping[str, Any],
) -> None:
    """Validate a single declared final file before a Controller writes it.

    Intermediate files and multi-file bundles are deliberately excluded because
    one task-level content contract cannot safely be applied to every helper or
    bundle member.
    """

    if controller_context.get("delivery_scope") != "task_final":
        return
    required_files = controller_context.get("mandatory_output_files")
    if not isinstance(required_files, (list, tuple)) or len(required_files) != 1:
        return
    required_file = required_files[0]
    if not isinstance(required_file, Mapping):
        return
    required_path = _normalized_delivery_path(required_file.get("path_hint"))
    if not required_path:
        return
    declared_contract = controller_context.get("authoritative_final_output_contract")
    if not isinstance(declared_contract, Mapping):
        return
    contract = dict(declared_contract)
    examples = controller_context.get("mandatory_acceptance_examples")
    if examples and not contract.get("acceptance_probes"):
        contract["acceptance_probes"] = list(examples)
    if not requires_content_contract_validation(contract):
        return

    tools_by_id = {item.callable_id: item for item in callable_tools}
    for intent in intents:
        callable_tool = tools_by_id.get(intent.callable_id)
        if callable_tool is None:
            continue
        operation_name = callable_tool.capability_operation_id.rsplit("::", 1)[-1]
        if operation_name not in _CONTROLLER_TEXT_WRITE_OPERATIONS:
            continue
        proposed_path = _normalized_delivery_path(
            _controller_tool_argument(
                callable_tool=callable_tool,
                intent=intent,
                name="path",
            )
        )
        if (
            proposed_path != required_path
            and not proposed_path.endswith(f"/{required_path.lstrip('/')}")
        ):
            continue
        proposed_content = _controller_tool_argument(
            callable_tool=callable_tool,
            intent=intent,
            name="content",
        )
        if not isinstance(proposed_content, str):
            continue
        validate_output_contract_content(proposed_content.encode("utf-8"), contract)


_SINGLE_CODE_FENCE = re.compile(
    r"\A[ \t]*`{3}[A-Za-z0-9_.+-]*[ \t]*\r?\n"
    r"(?P<body>.*)\r?\n[ \t]*`{3}[ \t]*\Z",
    re.DOTALL,
)


def _validate_final_candidate(
    content: str,
    contract: Mapping[str, Any],
    *,
    format_enforcement: Mapping[str, Any] | None,
    generated_source_contract: Mapping[str, Any] | None = None,
) -> tuple[bool, str, str | None]:
    artifact_type = str(contract.get("artifact_type") or "plaintext").strip().lower()
    if not content or not content.strip():
        return False, content, "$:empty"
    if artifact_type != "json":
        if is_output_contract_echo(content, contract):
            return False, content, "$:output_contract_echo"
        python_source = bool(generated_source_contract and generated_source_contract.get("language") == "python")
        if artifact_type == "code" or python_source:
            fenced = _SINGLE_CODE_FENCE.fullmatch(content)
            if fenced is not None:
                content = fenced.group("body")
            elif "```" in content and not python_source:
                return False, content, "$:code_wrapper"
        if python_source:
            # A generated raw-source handoff can arrive in a single artifact
            # envelope. Its JSON dictionary is also valid Python syntax, but
            # executing that dictionary never executes the contained program.
            # Project only this unambiguous wrapper, preserving source bytes;
            # declared JSON/text artifacts never enter this branch. Pairs keep
            # duplicate keys from being silently resolved during projection.
            try:
                envelope = json.loads(content, object_pairs_hook=tuple)
            except (TypeError, ValueError):
                envelope = None
            wrapped = dict(envelope) if isinstance(envelope, tuple) else {}
            if (isinstance(envelope, tuple) and len(wrapped) == len(envelope)
                    and {"artifact"} <= set(wrapped) <= {"artifact", "content_kind"}
                    and wrapped.get("content_kind", "value") == "value"
                    and isinstance(wrapped.get("artifact"), str)):
                content = wrapped["artifact"]
                if not content.strip():
                    return False, content, "$:empty"
            try:
                ast.parse(content)
            except (SyntaxError, ValueError) as exc:
                reason = f"$:generated_source_python_syntax:line={getattr(exc, 'lineno', None)}:{str(getattr(exc, 'msg', exc))[:160]}"
                return False, content, reason
        from .text_format_contract import normalize_declared_numeric_text
        content, _ = normalize_declared_numeric_text(content, contract)
        if requires_content_contract_validation(contract):
            try:
                validate_output_contract_content(content.encode("utf-8"), contract)
            except OutputContractViolation as exc:
                return False, content, _output_contract_violation_reason("$", exc)
        return True, content, None
    schema_value = contract.get("schema_hint")
    from .json_serialization import json_serialization_format
    if json_serialization_format(contract) == "jsonl":
        try:
            validate_output_contract_content(content.encode("utf-8"), contract)
        except OutputContractViolation as exc:
            return False, content, _output_contract_violation_reason("$", exc)
        return True, content, None
    if not isinstance(schema_value, Mapping):
        return False, content, "$:schema_missing"
    try:
        schema = require_semantic_json_schema(schema_value)
        parsed = strict_json_loads(content)
    except (ModelResponseContractError, ValueError, json.JSONDecodeError):
        return False, content, "$:json_parse"
    normalized = parsed
    if (
        isinstance(format_enforcement, Mapping)
        and format_enforcement.get("selected_enforcement_mode")
        == "native_strict_schema"
    ):
        normalized = normalize_portable_wire_instance(parsed, schema)
    valid, reason = validate_json_schema_instance(normalized, schema)
    if not valid:
        return False, content, reason or "$:schema"
    if contract.get("content_kind", "value") == "json_schema_document" and not validate_schema_document(normalized):
        return False, content, "$:invalid_schema_document"
    if normalized != parsed:
        return True, canonical_json_bytes(normalized).decode("utf-8"), None
    return True, content, None


def _missing_required_tool_operations(
    required: Sequence[Mapping[str, Any]],
    tool_results: Sequence[ControllerToolInvocationResultV1],
) -> tuple[str, ...]:
    return tuple(sorted({
        str(item["operation_kind"])
        for item in required
        if item.get("operation_kind")
        and not any(
            result.observation.status == "success"
            and result.observation.capability_operation_id
            in (item.get("capability_operation_ids") or ())
            and required_operation_evidence_failure(
                result.observation.capability_operation_id,
                (str(item["operation_kind"]),),
                result.observation.public_result,
            ) is None
            for result in tool_results
        )
    }))


def _pending_required_tool_functions(
    required: Sequence[Mapping[str, Any]],
    pending_operation_kinds: Sequence[str],
) -> tuple[str, ...]:
    pending = set(str(item) for item in pending_operation_kinds)
    return tuple(sorted({
        str(function_name)
        for item in required
        if str(item.get("operation_kind") or "") in pending
        for function_name in (item.get("function_names") or ())
        if str(function_name).strip()
    }))


def _controller_finalization_only_turn(
    *,
    turn_index: int,
    max_turns: int,
    tool_results: Sequence[ControllerToolInvocationResultV1],
    pending_required_operations: Sequence[str] = (),
) -> bool:
    """Reserve only the last turn; earlier turns can finish required Tool work."""

    return bool(
        turn_index >= max_turns
        and not pending_required_operations
        and any(item.observation.status == "success" for item in tool_results)
    )


def _project_parameterized_evidence_receipt(content: str) -> dict[str, Any] | None:
    """Decode a complete internal receipt; never interpret it as a Tool action.

    Some responses serialize the receipt fields in parameter tags. Container
    labels confer no execution authority. All five fields must be present once;
    action arguments, prose, mixed containers and incomplete values do not match.
    Closing container tags may be absent after the last complete parameter.
    """

    envelope = re.fullmatch(
        r"<tool_call>\s*<function=[A-Za-z_][A-Za-z0-9_.:-]*>\s*"
        r"(?P<body>[\s\S]*?)(?:\s*</function>\s*</tool_call>)?",
        content,
    )
    if envelope is None:
        return None
    body = envelope.group("body")
    fields: dict[str, Any] = {}
    position = 0
    boolean_fields = {"ready", "latest_observation_supports_completion"}
    reference_fields = {"latest_observation_id", "latest_observation_sha256"}
    allowed = boolean_fields | reference_fields | {"criterion_evidence", "final_output"}
    for match in re.finditer(
        r"<parameter=(?P<name>[A-Za-z_][A-Za-z0-9_]*)>(?P<value>[\s\S]*?)</parameter>", body,
    ):
        name, value = match.group("name"), match.group("value")
        if body[position:match.start()].strip() or name not in allowed or name in fields:
            return None
        position = match.end()
        if name in boolean_fields or name == "criterion_evidence":
            try:
                fields[name] = json.loads(value)
            except (TypeError, ValueError):
                return None
        elif name in reference_fields:
            fields[name] = value.strip()
        else:
            # Remove only the tag-line delimiters, never trim delivered content
            # or decode quotes/entities/escapes within the string payload.
            if value.startswith("\r\n"):
                value = value[2:]
            elif value.startswith("\n"):
                value = value[1:]
            if value.endswith("\r\n"):
                value = value[:-2]
            elif value.endswith("\n"):
                value = value[:-1]
            fields[name] = value
    if body[position:].strip():
        return None
    short_fields = boolean_fields | {"criterion_evidence", "final_output", "latest_observation_id"}
    legacy_fields = (short_fields - {"latest_observation_id"}) | {"latest_observation_sha256"}
    return fields if set(fields) in (short_fields, legacy_fields) else None


def _validate_finalization_evidence_audit(
    content: str,
    *,
    acceptance_criteria: Sequence[str],
    tool_results: Sequence[ControllerToolInvocationResultV1],
    materialized_output: str | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> tuple[bool, str, str | None]:
    """Validate one model-authored evidence envelope before public delivery."""

    def reject(code: str, **details: Any) -> tuple[bool, str, str]:
        if diagnostics is not None:
            diagnostics.update(error_code=code, **details)
        return False, "", "$:" + code

    # This envelope is an internal receipt, not the user's delivered artifact.
    # A single JSON fence can be projected without changing evidence or output
    # values; all field, reference, coverage and final-output checks still run.
    receipt_text = str(content or "").strip()
    fenced_receipt = re.fullmatch(r"```(?:json)?[ \t]*\r?\n(?P<body>[\s\S]*?)\r?\n```", receipt_text, re.IGNORECASE)
    if fenced_receipt is not None:
        receipt_text = fenced_receipt.group("body")
    try:
        audit = json.loads(receipt_text)
    except (TypeError, ValueError, json.JSONDecodeError):
        audit = _project_parameterized_evidence_receipt(receipt_text)
        if audit is None:
            return reject("finalization_evidence_audit_json_invalid", issue="return_one_json_object_using_response_template")
        if diagnostics is not None:
            diagnostics["receipt_projection"] = "parameter_envelope"
    if not isinstance(audit, Mapping):
        return reject("finalization_evidence_audit_not_object", actual_type=type(audit).__name__)
    required_fields = {
        "ready",
        "latest_observation_sha256",
        "latest_observation_supports_completion",
        "criterion_evidence",
        "final_output",
    }
    short_fields = (required_fields - {"latest_observation_sha256"}) | {"latest_observation_id"}
    short_references = set(audit) == short_fields
    if set(audit) not in (required_fields, short_fields):
        return reject("finalization_evidence_audit_shape_invalid", expected_fields=sorted(short_fields),
                      issue="use_exact_template_fields_or_the_supported_legacy_hash_fields")
    if not tool_results:
        return False, "", "$:finalization_evidence_missing"

    latest = tool_results[-1].observation
    ready = audit.get("ready")
    latest_supports = audit.get("latest_observation_supports_completion")
    if not isinstance(ready, bool) or not isinstance(latest_supports, bool):
        return reject("finalization_evidence_boolean_invalid", expected_boolean_fields=["ready", "latest_observation_supports_completion"])
    references = {
        f"obs_{index}": item.observation.observation_sha256
        for index, item in enumerate(tool_results, start=1)
    }
    latest_reference = (
        references.get(audit.get("latest_observation_id"))
        if short_references and isinstance(audit.get("latest_observation_id"), str)
        else audit.get("latest_observation_sha256")
    )
    if latest_reference != latest.observation_sha256:
        return reject("finalization_latest_observation_mismatch", expected_latest_reference=(
            f"obs_{len(tool_results)}" if short_references else latest.observation_sha256))
    if ready and latest_supports and latest.status != "success":
        return False, "", "$:finalization_latest_observation_unsatisfied"

    rows = audit.get("criterion_evidence")
    if not isinstance(rows, list):
        return reject("finalization_criterion_evidence_invalid", expected_type="array")
    successful_hashes = {
        item.observation.observation_sha256
        for item in tool_results
        if item.observation.status == "success"
    }
    covered: set[int] = set()
    cited: set[int] = set()
    for row_number, row in enumerate(rows):
        reference_key = "observation_ids" if short_references else "observation_sha256s"
        if not isinstance(row, Mapping) or set(row) != {"criterion_index", reference_key}:
            return reject("finalization_criterion_evidence_shape_invalid", row_number=row_number,
                          expected_fields=["criterion_index", reference_key])
        index = row.get("criterion_index")
        citations = row.get(reference_key)
        issue = None
        invalid_positions: list[int] = []
        if not isinstance(index, int) or isinstance(index, bool):
            issue = "criterion_index_must_be_integer"
        elif index < 0 or index >= len(acceptance_criteria):
            issue = "criterion_index_out_of_range"
        elif index in covered:
            issue = "duplicate_criterion_index"
        elif not isinstance(citations, list):
            issue = "references_must_be_array"
        elif ready and not citations:
            issue = "ready_true_requires_supporting_evidence"
        else:
            invalid_positions = [position for position, item in enumerate(citations)
                                 if not isinstance(item, str)
                                 or (references.get(item) if short_references else item) not in successful_hashes]
            if invalid_positions:
                issue = "references_must_name_successful_observations"
        if issue:
            return reject("finalization_criterion_evidence_unbound", row_number=row_number,
                          issue=issue, allowed_criterion_indices=list(range(len(acceptance_criteria))),
                          invalid_reference_positions=invalid_positions,
                          successful_references=([name for name, digest in references.items() if digest in successful_hashes]
                                                 if short_references else sorted(successful_hashes)))
        covered.add(index)
        if citations:
            cited.add(index)
    if ready and covered != set(range(len(acceptance_criteria))):
        return reject("finalization_criterion_coverage_incomplete",
                      missing_criterion_indices=sorted(set(range(len(acceptance_criteria))) - covered))

    final_output = materialized_output if materialized_output is not None else audit.get("final_output")
    if not ready:
        return reject("finalization_evidence_unsatisfied",
                      missing_criterion_indices=sorted(set(range(len(acceptance_criteria))) - cited))
    if not isinstance(final_output, str) or not final_output:
        return False, "", "$:finalization_output_missing"
    return True, final_output, None


def _finalization_evidence_contract(
    tool_results: Sequence[ControllerToolInvocationResultV1],
    acceptance_criteria: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Model-visible references resolve to the existing immutable observations."""
    return {
        **({"response_template": {
            "ready": False,
            "latest_observation_id": f"obs_{len(tool_results)}",
            "latest_observation_supports_completion": False,
            "criterion_evidence": [{"criterion_index": index, "observation_ids": []}
                                   for index in range(len(acceptance_criteria))],
            "final_output": "",
        }, "template_usage": (
            "Fill this response shape from actual observations. Indices refer to the same-order "
            "mandatory_acceptance_criteria. Empty references and ready=false assert no completion. "
            "Set ready=true only after every criterion has supporting evidence; never copy a "
            "reference merely because it is allowed. Preserve already materialized output bytes."
        )} if acceptance_criteria is not None else {}),
        "latest_observation_id": f"obs_{len(tool_results)}",
        "observations": [
            {"id": f"obs_{index}", "status": item.observation.status,
             "operation": item.observation.capability_operation_id}
            for index, item in enumerate(tool_results, start=1)
        ],
        "instruction": (
            "While required work remains and Tools are available, call the appropriate Tool. "
            "Execute an already prepared required verification before rewriting implementations "
            "without new evidence. A file-write receipt proves a write, not a successful test. "
            "Match each criterion to the scope of its observation: syntax/import checks prove "
            "loadability, and readback proves delivered bytes, not runtime behavior. For a "
            "behavior criterion, exercise the relevant operation with task-appropriate inputs "
            "and inspect its result using available Tools; reuse valid checks that already "
            "cover it. Missing coverage is unverified, not completion. Choose checks from "
            "the original task and public observations, never hidden verifier expectations. "
            "For a final response return one internal JSON object with exactly ready (boolean), "
            "latest_observation_id, latest_observation_supports_completion (boolean), "
            "criterion_evidence (array), and final_output (string). Each criterion_evidence row "
            "has exactly criterion_index (zero-based integer) and observation_ids (array of IDs "
            "from observations above). With ready=true cover every mandatory acceptance criterion "
            "once with non-empty references to successful observations that actually support it. "
            "Later contradictory results or changes invalidate earlier evidence; unrelated "
            "diagnostic failures do not. With ready=false use empty references or omit rows for "
            "unverified criteria, and set final_output to an empty string. Never invent evidence. "
            "The latest observation may be unrelated: mark latest_observation_supports_completion "
            "false and cite still-valid earlier observations. final_output alone must satisfy "
            "the exact user delivery format; the runtime removes the internal envelope."
        ),
    }


def _controller_validation_category(reason: str | None) -> str | None:
    if not reason:
        return None
    if reason in {
        "$:finalization_evidence_unsatisfied", "$:finalization_output_missing",
        "$:finalization_evidence_missing", "$:finalization_latest_observation_unsatisfied",
    } or str(reason).startswith(("$:finalization_explicit_checks_unexecuted", "$:finalization_required_paths_missing")):
        return "verification_incomplete"
    if reason.startswith("$:finalization_"):
        return "evidence_protocol_invalid"
    return "output_contract_invalid"


def _authoritative_tool_terminal_output(
    *,
    expected_output_contract: Mapping[str, Any],
    original_request: str,
    required_operations: Sequence[Mapping[str, Any]],
    tool_results: Sequence[ControllerToolInvocationResultV1],
) -> str | None:
    """Realize an exact final literal after all declared Tool duties succeed."""
    if not required_operations:
        return None
    if _missing_required_tool_operations(required_operations, tool_results):
        return None
    return authoritative_exact_final_literal(
        expected_output_contract, original_request,
    )


class ControllerSessionRunner:
    """Run one sealed Controller Session with bounded contract-only repair."""

    def __init__(
        self,
        *,
        turn_executor: ControllerTurnExecutorPort,
        policy: ControllerSessionPolicyV1 | None = None,
        cost_ledger: Any = None,
        execution_ledger: Any = None,
        tool_runtime: ControllerToolRuntimePort | None = None,
    ) -> None:
        self.turn_executor = turn_executor
        self.policy = policy or load_controller_session_policy()
        self.cost_ledger = cost_ledger
        self.execution_ledger = execution_ledger
        self.tool_runtime = tool_runtime

    async def run(
        self,
        *,
        run_id: str,
        spec: ControllerSessionSpec,
        resolved_inputs: Mapping[str, Any],
        provenance_identities: Sequence[str] = (),
        format_enforcement: Mapping[str, Any] | None = None,
        controller_context: Mapping[str, Any] | None = None,
        skill_bundle: SkillContextBundleV1 | None = None,
        resolved_context: Mapping[str, Any] | None = None,
        materialized_output_reader: Callable[[], Awaitable[str | None]] | None = None,
        materialized_delivery_state_reader: Callable[[], Awaitable[Mapping[str, Any] | None]] | None = None,
        input_source_reader: Callable[[str], Awaitable[str | None]] | None = None,
        media_part_reader: Callable[[], Awaitable[tuple[list[dict[str, Any]], list[dict[str, Any]]]]] | None = None,
    ) -> ControllerSessionResultV1:
        started = time.perf_counter()
        tool_enabled = isinstance(spec, ControllerSessionSpecV2)
        if tool_enabled and self.tool_runtime is None:
            raise ControllerSessionError("controller_tool_runtime_continuation_not_enabled")
        if spec.controller_session_policy_sha256 != self.policy.policy_sha256:
            raise ControllerSessionError("controller_policy_identity_mismatch")
        task_context = str((controller_context or {}).get("task_context") or "")
        task_for_projection = _original_query_for_evidence(
            task_context, fallback=spec.task_instruction,
        )
        secondary_task = spec.task_instruction if task_for_projection != spec.task_instruction else ""
        from .execution_check_progress import ExplicitCheckProgress
        check_progress = ExplicitCheckProgress(
            original_request=(task_for_projection if "[Original User Query]\n" in task_context else ""),
            task_instruction=spec.task_instruction,
            callable_tools=getattr(spec, "callable_tools", ()) if tool_enabled else (),
        )
        bounded_inputs = {
            name: _bounded_web_evidence_input(
                value, task=task_for_projection,
                max_bytes=self.policy.max_inline_tool_result_bytes,
                secondary_task=secondary_task,
            )
            for name, value in resolved_inputs.items()
        }
        snapshot = build_controller_input_snapshot(
            run_id=run_id,
            spec=spec,
            resolved_inputs=bounded_inputs,
            policy=self.policy,
            provenance_identities=provenance_identities,
            resolved_context=resolved_context,
        )
        ledger = self.execution_ledger
        skill_metadata = {}
        if skill_bundle is not None:
            try:
                validate_skill_snapshot(skill_bundle, spec, snapshot)
                skill_metadata = skill_bundle.metadata()
            except (ControllerSkillError, ValueError) as exc:
                raise ControllerSessionError(getattr(exc, "code", "controller_skill_bundle_invalid")) from exc
        if ledger is not None:
            ledger.record_controller_session_started(
                session_id=snapshot.session_id,
                controller_session_spec_sha256=spec.spec_sha256,
                controller_policy_sha256=self.policy.policy_sha256,
                input_snapshot_sha256=snapshot.snapshot_sha256,
                controller_resource_id=spec.controller_resource_id,
                backing_model_resource_id=spec.backing_model_resource_id,
                **skill_metadata,
            )

        turns: list[ControllerTurnResultV1] = []
        feedback_items: list[ValidationFeedbackV1] = []
        conversation_messages: list[dict[str, Any]] = []
        accounting_references: list[dict[str, Any]] = []
        failure_counts: dict[str, int] = {}
        tool_fingerprint_counts: dict[str, int] = {}
        input_revisions = _ControllerInputRevisions(
            str((controller_context or {}).get("tool_working_directory") or "")
        )
        callable_tools_by_id = {item.callable_id: item for item in spec.callable_tools} if tool_enabled else {}
        last_tool_failure_route: str | None = None
        consecutive_tool_failure_routes = 0
        tool_results: list[ControllerToolInvocationResultV1] = []
        failed_tool_attempts: list[ControllerToolTerminalContext] = []
        requested_tool_action_count = 0
        accepted_tool_action_count = 0
        tool_call_attempt_count = 0
        tool_success_count = 0
        tool_failure_count = 0
        required_operations = tuple(
            (controller_context or {}).get("required_successful_tool_operations") or ()
        ) if tool_enabled else ()
        acceptance_criteria = tuple(
            str(item)
            for item in (
                (controller_context or {}).get("mandatory_acceptance_criteria")
                or ()
            )
            if str(item).strip()
        ) if tool_enabled else ()
        authoritative_output_contract = spec.expected_output_contract
        declared_authoritative_contract = (controller_context or {}).get(
            "authoritative_final_output_contract"
        )
        if (
            (controller_context or {}).get("delivery_scope")
            in {"task_final", "final_content_source"}
            and isinstance(declared_authoritative_contract, Mapping)
        ):
            authoritative_output_contract = dict(declared_authoritative_contract)
            examples = (controller_context or {}).get(
                "mandatory_acceptance_examples"
            )
            if examples and not authoritative_output_contract.get(
                "acceptance_probes"
            ):
                authoritative_output_contract["acceptance_probes"] = list(
                    examples
                )
        stalled_required_batches = 0
        progress_notice_sent = False
        truncation_repairs = 0
        final_validation_reason: str | None = None
        materialized_delivery_state: Mapping[str, Any] | None = None
        delivery_state_observed_after_tool_count = -1
        materialized_output: str | None = None
        output_observed_after_tool_count = -1

        def finalize(
            *, status: Literal["success", "failure"], output: str = "", failure: str | None = None,
            terminal: ControllerToolTerminalContext | None = None,
            responsibility: str = "framework",
            failure_envelope: TerminalFailureEnvelope | None = None,
        ) -> ControllerSessionResultV1:
            if failure_envelope is not None:
                failure = failure_envelope.failure_code
            if tool_enabled and status == "failure" and terminal is None:
                terminal = ControllerToolTerminalContext(
                    failure_stage=failure_envelope.failure_stage if failure_envelope else "controller_session", failure_code=str(failure),
                    responsibility=responsibility, session_id=snapshot.session_id,
                )
            if status == "failure" and failure_envelope is None:
                failure_envelope = TerminalFailureEnvelope.create(
                    responsibility=terminal.responsibility if terminal else responsibility,
                    failure_stage=terminal.failure_stage if terminal else "controller_session",
                    failure_code=terminal.failure_code if terminal else str(failure),
                    run_id=run_id, subtask_id=spec.subtask_id,
                    subtask_revision=spec.subtask_revision,
                    response_received=bool(turns and turns[-1].transport_audit.get("response_received")),
                    resource_call_id=terminal.resource_call_id if terminal else None,
                )
            elapsed_ms = (time.perf_counter() - started) * 1000
            summary_fields = {
                "session_id": snapshot.session_id,
                "actual_turns": len(turns),
                "semantic_repairs": len(feedback_items),
                "terminal_status": status,
                "terminal_failure_code": failure,
                "elapsed_ms": elapsed_ms,
                "controller_resource_id": spec.controller_resource_id,
                "backing_model_resource_id": spec.backing_model_resource_id,
                "input_snapshot_sha256": snapshot.snapshot_sha256,
                "policy_sha256": self.policy.policy_sha256,
                "model_accounting_references": tuple(accounting_references),
            }
            if tool_enabled:
                observations = tuple(item.observation for item in tool_results)
                summary: ControllerSessionSummaryV1 | ControllerSessionSummaryV2 = (
                    ControllerSessionSummaryV2(
                        **summary_fields,
                        terminal_failure=terminal,
                        failed_tool_attempts=tuple(failed_tool_attempts),
                        requested_tool_action_count=requested_tool_action_count,
                        accepted_tool_action_count=accepted_tool_action_count,
                        evidence_incomplete=any(item.evidence_incomplete for item in failed_tool_attempts),
                        tool_call_count=tool_call_attempt_count,
                        tool_success_count=tool_success_count,
                        tool_failure_count=tool_failure_count,
                        tool_observation_bytes=sum(
                            item.metrics.observation_bytes for item in tool_results
                        ),
                        resource_call_ids=tuple(
                            item.resource_call_id for item in observations
                        ),
                        controller_tool_provenance_ids=tuple(
                            item.provenance_sha256 for item in observations
                        ),
                        tool_observation_sha256s=tuple(
                            item.observation_sha256 for item in observations
                        ),
                        successful_tool_operation_ids=tuple(sorted({
                            item.capability_operation_id for item in observations
                            if item.status == "success"
                            and required_operation_evidence_failure(
                                item.capability_operation_id,
                                (item.capability_operation_id.rsplit("::", 1)[-1],),
                                item.public_result,
                            ) is None
                        })),
                    )
                )
            else:
                summary = ControllerSessionSummaryV1(**summary_fields)
            result = ControllerSessionResultV1(
                status=status,
                output_data=output,
                failure_code=failure,
                terminal_failure=failure_envelope,
                controller_session_spec_sha256=spec.spec_sha256,
                controller_policy_sha256=self.policy.policy_sha256,
                input_snapshot_sha256=snapshot.snapshot_sha256,
                turns=tuple(turns),
                validation_feedback=tuple(feedback_items),
                summary=summary,
            )
            try:
                if ledger is not None:
                    if status == "success":
                        ledger.record_controller_session_finished(
                            session_id=snapshot.session_id,
                            controller_session_spec_sha256=spec.spec_sha256,
                            controller_policy_sha256=self.policy.policy_sha256,
                            input_snapshot_sha256=snapshot.snapshot_sha256,
                            controller_resource_id=spec.controller_resource_id,
                            backing_model_resource_id=spec.backing_model_resource_id,
                            terminal_status="success",
                            actual_turns=len(turns),
                            semantic_repairs=len(feedback_items),
                            tool_call_count=tool_call_attempt_count,
                            runtime_protocol=(
                                CONTROLLER_TOOL_RUNTIME_PROTOCOL if tool_enabled else None
                            ),
                            elapsed_ms=elapsed_ms,
                            result_sha256=result.result_sha256,
                        )
                    else:
                        ledger.record_controller_session_failed(
                            session_id=snapshot.session_id,
                            controller_session_spec_sha256=spec.spec_sha256,
                            controller_policy_sha256=self.policy.policy_sha256,
                            input_snapshot_sha256=snapshot.snapshot_sha256,
                            controller_resource_id=spec.controller_resource_id,
                            backing_model_resource_id=spec.backing_model_resource_id,
                            terminal_status="failure",
                            actual_turns=len(turns),
                            semantic_repairs=len(feedback_items),
                            tool_call_count=tool_call_attempt_count,
                            runtime_protocol=(
                                CONTROLLER_TOOL_RUNTIME_PROTOCOL if tool_enabled else None
                            ),
                            elapsed_ms=elapsed_ms,
                            failure_code=str(failure),
                            controller_validation_reason=(
                                ":".join(final_validation_reason.split(":")[:2])
                                if final_validation_reason else None
                            ),
                            controller_validation_category=_controller_validation_category(final_validation_reason),
                            remaining_tool_calls=max(0, self.policy.max_tool_calls - tool_call_attempt_count),
                            declared_output_paths_present=(
                                materialized_delivery_state.get("all_declared_paths_present")
                                if materialized_delivery_state else None
                            ),
                            result_sha256=result.result_sha256,
                        )
            except Exception:
                if not tool_enabled:
                    raise
                # The terminal write was attempted once. Re-seal only the returned
                # projection; never retry a possibly already persisted event.
                terminal = terminal or ControllerToolTerminalContext(
                    failure_stage="controller_session_accounting",
                    failure_code="controller_session_terminal_persistence_failed",
                    responsibility="framework", session_id=snapshot.session_id,
                    evidence_incomplete=True,
                )
                summary_data = summary.model_dump(mode="python", exclude={"summary_sha256"})
                summary_data.update(
                    terminal_status="failure", terminal_failure_code=terminal.failure_code,
                    terminal_failure=terminal, evidence_incomplete=True,
                    secondary_audit_failures=("controller_session_terminal_persistence_failed",),
                )
                result_data = result.model_dump(mode="python", exclude={"result_sha256"})
                result_data.update(status="failure", output_data="", failure_code=terminal.failure_code,
                                   summary=ControllerSessionSummaryV2(**summary_data),
                                   terminal_failure=TerminalFailureEnvelope.create(
                                       responsibility=terminal.responsibility,
                                       failure_stage=terminal.failure_stage,
                                       failure_code=terminal.failure_code,
                                       run_id=run_id, subtask_id=spec.subtask_id,
                                       subtask_revision=spec.subtask_revision,
                                       primary_failure_sha256=failure_envelope.failure_sha256 if failure_envelope and failure_envelope.failure_code != terminal.failure_code else None))
                result = ControllerSessionResultV1(**result_data)
            if status == "failure":
                if tool_enabled:
                    callable_by_id = {
                        item.callable_id: item for item in spec.callable_tools
                    }
                    invoked = [
                        callable_by_id.get(item.observation.callable_id)
                        for item in tool_results
                    ]
                    effects_known = all(
                        item is not None and (
                            item.side_effects == "none"
                            or (item.side_effects == "declared" and item.effect_targets
                                and set(item.effect_targets) <= {"task_workspace"})
                        )
                        for item in invoked
                    )
                    result._recovery_execution_audit = {
                        "controller_tool_observations_complete": bool(
                            tool_call_attempt_count == len(tool_results)
                            and not result.summary.evidence_incomplete
                        ),
                        "controller_observed_tool_count": len(tool_results),
                        "network_required": bool(tool_results and not effects_known),
                        "writable_scope": any(
                            item is not None and "task_workspace" in item.effect_targets
                            for item in invoked
                        ),
                    }
                process_diagnostic = (
                    _tool_process_recovery_diagnostic(tool_results)
                    if failure == "resource_process_failed" else None
                )
                if failure == "declared_result_status_failure":
                    process_diagnostic = _tool_declared_recovery_diagnostic(
                        tool_results,
                        callable_id=terminal.callable_id if terminal is not None else None,
                    )
                if process_diagnostic is not None:
                    result._recovery_diagnostic = process_diagnostic
                else:
                    from .input_volume import controller_input_volume
                    result._recovery_diagnostic = canonical_json_bytes({
                        "failure_code": result.failure_code,
                        "input_volume": controller_input_volume(spec, snapshot),
                        "controller_validation_reason": final_validation_reason,
                        "controller_validation_category": _controller_validation_category(final_validation_reason),
                        "completed_tool_observation_count": len(tool_results),
                        **({"execution_check_progress": check_progress.projection()}
                           if check_progress.checks else {}),
                        "successful_tool_observation_refs": [
                            {"observation_id": f"obs_{index}",
                             "observation_sha256": item.observation.observation_sha256,
                             "operation_id": item.observation.capability_operation_id}
                            for index, item in enumerate(tool_results, start=1)
                            if item.observation.status == "success"
                        ],
                        **({"materialized_delivery_state": dict(materialized_delivery_state),
                            "delivery_state_observed_after_tool_count": delivery_state_observed_after_tool_count}
                           if materialized_delivery_state is not None else {}),
                        "recent_tool_observations": [
                            {
                                "operation_id": item.observation.capability_operation_id,
                                "status": item.observation.status,
                                "observation_sha256": item.observation.observation_sha256,
                                "result_excerpt": canonical_json_bytes(
                                    item.observation.public_result
                                ).decode("utf-8")[:768],
                            }
                            for item in tool_results[-4:]
                        ],
                        "instruction": (
                            "Reuse completed step checkpoints and inspect current task state. "
                            "These excerpts are observations, not new authority or proof that "
                            "all requirements hold. Recompose only unfinished work. "
                            "input_volume reports bytes, not tokens or proof of a provider limit. "
                            "For input-related transport failure, consider a derived representation "
                            "before resending the same bulk input. Preserve completed checkpoints; "
                            "add a compatible processing step for unfinished work when needed, "
                            "without discarding required evidence or changing the final contract."
                        ),
                    }).decode("utf-8")
            return result

        # Normal work keeps its existing turn budget. Only an internal evidence
        # protocol repair may use otherwise-unused semantic repair slots after
        # the final work turn; it cannot dispatch another Tool or relax delivery.
        for turn_index in range(1, self.policy.max_turns + self.policy.max_semantic_repairs + 1):
            closing_protocol_repair = turn_index > self.policy.max_turns
            if closing_protocol_repair and not (
                tool_enabled and acceptance_criteria and tool_results
                and _controller_validation_category(final_validation_reason) == "evidence_protocol_invalid"
            ):
                return finalize(status="failure", failure="controller_turn_limit", responsibility="budget")
            if self.cost_ledger is not None:
                exhausted = getattr(self.cost_ledger, "is_exhausted", False)
                is_exhausted = (
                    exhausted() if callable(exhausted) else bool(exhausted)
                )
                if is_exhausted:
                    return finalize(status="failure", failure="controller_cost_limit", responsibility="budget")
            turn_id = canonical_sha256(
                {"session_id": snapshot.session_id, "turn_index": turn_index}
            )
            if ledger is not None:
                ledger.record_controller_turn_started(
                    session_id=snapshot.session_id,
                    turn_id=turn_id,
                    turn_index=turn_index,
                    controller_session_spec_sha256=spec.spec_sha256,
                    controller_policy_sha256=self.policy.policy_sha256,
                    input_snapshot_sha256=snapshot.snapshot_sha256,
                    **skill_metadata,
                )
            pending_required_operations = _missing_required_tool_operations(
                required_operations, tool_results,
            ) if required_operations else ()
            protocol_repair_only = bool(
                tool_enabled and tool_results and _controller_validation_category(final_validation_reason)
                == "evidence_protocol_invalid"
            )
            finalization_only = bool(
                tool_enabled
                and (closing_protocol_repair or protocol_repair_only or (not check_progress.pending() and _controller_finalization_only_turn(
                    turn_index=turn_index,
                    max_turns=self.policy.max_turns,
                    tool_results=tool_results,
                    pending_required_operations=pending_required_operations,
                )))
            )
            finalization_evidence_audit = bool(
                tool_enabled and acceptance_criteria and tool_results
            )
            if (finalization_only or finalization_evidence_audit) and materialized_output_reader is not None and (
                output_observed_after_tool_count != len(tool_results)
            ):
                materialized_output = await materialized_output_reader()
                output_observed_after_tool_count = len(tool_results)
            turn_context = dict(controller_context or {})
            if check_progress.checks:
                turn_context["execution_check_progress"] = check_progress.projection()
            if finalization_evidence_audit:
                turn_context["controller_finalization_evidence_audit"] = True
                turn_context["finalization_evidence_contract"] = _finalization_evidence_contract(tool_results, acceptance_criteria)
            if tool_enabled and materialized_delivery_state_reader is not None and (
                delivery_state_observed_after_tool_count != len(tool_results)
            ):
                try:
                    materialized_delivery_state = await materialized_delivery_state_reader()
                except Exception as exc:
                    # This additional observation is advisory. Existing readback,
                    # required-operation and final delivery gates still decide
                    # acceptance; a failed optional observation adds no new gate.
                    materialized_delivery_state = {
                        "verification_scope": "observation_unavailable",
                        "exception_type": type(exc).__name__,
                        "semantic_correctness": "not_determined",
                    }
                delivery_state_observed_after_tool_count = len(tool_results)
            if materialized_delivery_state is not None:
                turn_context["materialized_delivery_state"] = dict(materialized_delivery_state)
            if materialized_output is not None:
                turn_context["materialized_delivery_available"] = True
            if tool_enabled:
                turn_context["execution_budget"] = {
                    "max_model_turns": self.policy.max_turns,
                    "current_turn": turn_index,
                    "remaining_model_turns_including_current": max(0, self.policy.max_turns - turn_index + 1),
                    "planned_finalization_turn": self.policy.max_turns,
                    "remaining_tool_calls": max(0, self.policy.max_tool_calls - tool_call_attempt_count),
                    **({"phase": "finalization_protocol_repair",
                        "remaining_protocol_repairs_including_current":
                            self.policy.max_semantic_repairs - len(feedback_items) + 1}
                       if closing_protocol_repair else {}),
                }
                requested_cap = int(
                    turn_context.get("max_tokens") or _TOOL_CONTROLLER_OUTPUT_CAP
                )
                turn_context["max_tokens"] = requested_cap
            if pending_required_operations:
                turn_context["pending_required_tool_operations"] = list(
                    pending_required_operations
                )
                pending_functions = _pending_required_tool_functions(
                    required_operations, pending_required_operations,
                )
                if pending_functions:
                    turn_context["pending_required_tool_functions"] = list(
                        pending_functions
                    )
            if finalization_only:
                turn_context["controller_finalization_only"] = True
                if finalization_evidence_audit:
                    instruction = {
                        "framework_phase": "finalization_evidence_audit",
                        "instruction": (
                            "Repair only the evidence-audit JSON using the existing observations; "
                            "do not repeat edits or checks. If actual work remains unverified, "
                            "return ready=false so it can continue within the remaining budget. "
                            if protocol_repair_only else
                            "This is the final budgeted turn. Tools are no longer available. "
                            "Use the same finalization_evidence_contract and report only what "
                            "the current observations support. Unexecuted required checks remain "
                            "unverified; a missing check is not a protocol-format error."
                        ),
                    }
                else:
                    instruction = {
                        "framework_phase": "finalization_only",
                        "pending_required_tool_operations": list(
                            pending_required_operations
                        ),
                        "instruction": (
                            "No further Tool calls are available in this bounded "
                            "session. Return only the final completion required by "
                            "the authoritative output contract, grounded in the "
                            "Tool observations already received. Preserve every required "
                            "format; omit reasoning, calculation, evidence, citations, preamble, "
                            "and suffix unless the contract explicitly requires that content. "
                            "Do not claim an unsatisfied operation succeeded."
                        ),
                    }
                conversation_messages.append({
                    "role": "user",
                    "content": json.dumps(
                        instruction,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                })
            try:
                if media_part_reader is not None:
                    media_parts, media_audit = await media_part_reader()
                    turn_context["model_media_parts"] = list(turn_context.get("model_media_parts") or ()) + media_parts
                    turn_context["model_media_audit"] = list(turn_context.get("model_media_audit") or ()) + media_audit
                # Timing eligibility is a framework observation, not a model
                # assertion of correctness. Keep Tools callable and keep the
                # same evidence, explicit-check and artifact delivery gates.
                completion_window = bool(
                    finalization_evidence_audit
                    and materialized_output is not None
                    and not pending_required_operations
                    and not check_progress.pending()
                    and tool_results[-1].observation.status == "success"
                    and not any(
                        isinstance(item, Mapping) and item.get("present") is False
                        for item in (materialized_delivery_state or {}).get("required_outputs", ())
                    )
                )
                with model_completion_window(completion_window):
                    turn = await self.turn_executor.execute_turn(
                        spec=spec,
                        snapshot=snapshot,
                        turn_id=turn_id,
                        turn_index=turn_index,
                        conversation_messages=tuple(conversation_messages),
                        provider_tools=(
                            tuple(project_provider_tool_schema(item) for item in spec.callable_tools)
                            if tool_enabled and not finalization_only
                            else ()
                        ),
                        format_enforcement=(
                            None
                            if tool_enabled
                            else dict(format_enforcement)
                            if format_enforcement is not None
                            else None
                        ),
                        controller_context=turn_context,
                        **({"skill_bundle": skill_bundle} if skill_bundle is not None else {}),
                    )
            except asyncio.CancelledError as exc:
                # Seal the Controller boundary before cancellation propagates to
                # recovery.  The unfinished provider turn is not counted as a
                # completed turn, and no request is retried here.
                terminal_result = finalize(
                    status="failure",
                    failure="controller_cancelled",
                    responsibility="interrupted",
                )
                setattr(exc, "controller_session_result", terminal_result)
                raise
            except Exception as exc:
                # Keep an executor defect inside the Controller boundary so the
                # recovery layer receives a complete, typed terminal record.
                return finalize(
                    status="failure",
                    failure_envelope=TerminalFailureEnvelope.create(
                        responsibility="framework",
                        failure_stage="controller_turn_execution",
                        failure_code="controller_turn_execution_failed",
                        run_id=run_id,
                        subtask_id=spec.subtask_id,
                        subtask_revision=spec.subtask_revision,
                        exception_type=type(exc).__name__,
                        message_sha256=canonical_sha256({
                            "exception_type": type(exc).__name__,
                            "message": str(exc),
                        }),
                    ),
                )
            if turn.session_id != snapshot.session_id or turn.turn_id != turn_id:
                return finalize(
                    status="failure", failure="controller_session_identity_mismatch"
                )
            turns.append(turn)
            if turn.model_accounting_reference is not None:
                accounting_references.append(dict(turn.model_accounting_reference))
            if ledger is not None:
                ledger.record_controller_turn_finished(
                    session_id=snapshot.session_id,
                    turn_id=turn.turn_id,
                    turn_index=turn.turn_index,
                    status=turn.status,
                    controller_session_spec_sha256=spec.spec_sha256,
                    controller_policy_sha256=self.policy.policy_sha256,
                    input_snapshot_sha256=snapshot.snapshot_sha256,
                    model_accounting_reference=turn.model_accounting_reference,
                    request_sha256=turn.request_sha256,
                    response_sha256=turn.response_sha256,
                    candidate_sha256=turn.candidate_sha256,
                    latency_ms=turn.latency_ms,
                    failure_code=turn.failure_code,
                    finish_reason=turn.finish_reason,
                    response_content_chars=len(turn.content or ""),
                    provider_tool_call_count=turn.transport_audit.get("provider_tool_call_count"),
                    normalized_tool_call_count=len(turn.tool_calls),
                    **({"input_volume": turn.transport_audit["input_volume"]}
                       if "input_volume" in turn.transport_audit else {}),
                    **skill_metadata,
                )
            if turn.status == "failure":
                if turn.terminal_failure is not None:
                    return finalize(status="failure", failure=turn.failure_code,
                        responsibility=turn.terminal_failure.responsibility,
                        failure_envelope=turn.terminal_failure)
                failure_code = str(turn.failure_code or "controller_transport_failure")
                if failure_code.startswith("controller_skill_"):
                    return finalize(status="failure", failure=failure_code, responsibility="framework")
                if (
                    failure_code == "controller_provider_truncation"
                    and tool_enabled
                    and truncation_repairs < 1
                    and len(feedback_items) < self.policy.max_semantic_repairs
                    and turn_index < self.policy.max_turns
                ):
                    truncation_repairs += 1
                    feedback = _validation_feedback(
                        target_contract=authoritative_output_contract,
                        candidate_sha256=turn.candidate_sha256,
                        reason="$.response:provider_truncation",
                    )
                    feedback_items.append(feedback)
                    if ledger is not None:
                        ledger.record_controller_validation_feedback(
                            session_id=snapshot.session_id,
                            turn_id=turn.turn_id,
                            controller_session_spec_sha256=spec.spec_sha256,
                            controller_policy_sha256=self.policy.policy_sha256,
                            input_snapshot_sha256=snapshot.snapshot_sha256,
                            feedback_sha256=feedback.feedback_sha256,
                            target_contract_sha256=feedback.target_contract_sha256,
                            previous_candidate_sha256=feedback.previous_candidate_sha256,
                        )
                    conversation_messages.append({
                        "role": "user",
                        "content": json.dumps({
                            "failure_code": failure_code,
                            "tool_executed": False,
                            "pending_required_tool_operations": list(
                                pending_required_operations
                            ),
                            "maximum_output_tokens": requested_cap,
                            "instruction": (
                                "The previous response exceeded the output limit and was not accepted. "
                                "Return only the next required authorized Tool call when an operation "
                                "is still pending. If all required Tool operations already succeeded, "
                                "do not repeat them; return only the concise final completion required "
                                "by the authoritative output contract. Omit explanation, copied input, "
                                "and Markdown fences."
                            ),
                        }, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                    })
                    continue
                if failure_code in {
                    "controller_backing_model_not_ready",
                    "controller_cost_limit",
                    "controller_provider_truncation",
                }:
                    responsibility = (
                        "budget"
                        if failure_code == "controller_cost_limit"
                        else "research"
                        if failure_code == "controller_provider_truncation"
                        else "framework"
                    )
                    return finalize(
                        status="failure",
                        failure=failure_code,
                        responsibility=responsibility,
                    )
                if tool_enabled and failure_code in _REPAIRABLE_PROVIDER_TOOL_FAILURES:
                    # Provider tool-call normalization happens before dispatch.
                    # A wrong name or malformed dynamic argument can be corrected
                    # against the sealed Tool schema without executing that call.
                    # Supplying a runtime-owned fixed argument is rejected too;
                    # ask for a conforming call without changing its fixed value.
                    # No rejected call is dispatched. Host/scope violations and
                    # schema identity changes remain terminal.
                    assert isinstance(spec, ControllerSessionSpecV2)
                    fingerprint = canonical_sha256(
                        {"failure_code": failure_code, "candidate_sha256": turn.candidate_sha256}
                    )
                    failure_counts[fingerprint] = failure_counts.get(fingerprint, 0) + 1
                    if (
                        failure_counts[fingerprint] < self.policy.max_same_failure_repeats
                        and len(feedback_items) < self.policy.max_semantic_repairs
                        and turn_index < self.policy.max_turns
                    ):
                        feedback = _validation_feedback(
                            target_contract=spec.expected_output_contract,
                            candidate_sha256=turn.candidate_sha256,
                            reason=(
                                "$.tools:unauthorized_function_name"
                                if failure_code == "controller_tool_call_not_authorized"
                                else "$.tools:omit_runtime_fixed_arguments"
                                if failure_code == "controller_tool_fixed_argument_override"
                                else "$.tools:provider_call_envelope_invalid"
                                if failure_code.startswith("controller_provider_tool_")
                                else "$.tools:dynamic_arguments_invalid"
                            ),
                        )
                        feedback_items.append(feedback)
                        if ledger is not None:
                            ledger.record_controller_validation_feedback(
                                session_id=snapshot.session_id,
                                turn_id=turn.turn_id,
                                controller_session_spec_sha256=spec.spec_sha256,
                                controller_policy_sha256=self.policy.policy_sha256,
                                input_snapshot_sha256=snapshot.snapshot_sha256,
                                feedback_sha256=feedback.feedback_sha256,
                                target_contract_sha256=feedback.target_contract_sha256,
                                previous_candidate_sha256=feedback.previous_candidate_sha256,
                            )
                        conversation_messages.append({
                            "role": "user",
                            "content": json.dumps({
                                "failure_code": failure_code,
                                "tool_executed": False,
                                "instruction": (
                                    "Call only an authorized function_name exactly as listed. "
                                    "Include a non-empty, unique call id and function.name in each native tool call. "
                                    "No calls from the rejected response executed; do not repeat earlier successful work. "
                                    "Supply exactly the required dynamic arguments with "
                                    "the declared types; omit undeclared and fixed arguments."
                                ),
                                "authorized_tool_functions": [
                                    {"function_name": item.provider_tool_name,
                                     "dynamic_argument_names": [port["name"] for port in item.dynamic_input_ports],
                                     **({"arguments_example": {}} if not item.dynamic_input_ports else {}),
                                     **({"runtime_bound_argument_names": list(item.fixed_input_bindings)}
                                        if failure_code == "controller_tool_fixed_argument_override" else {})}
                                    for item in spec.callable_tools
                                ],
                            }, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                        })
                        continue
                    return finalize(
                        status="failure", failure=failure_code,
                        responsibility="research",
                    )
                if tool_enabled and failure_code.startswith(
                    ("controller_tool_", "controller_provider_tool_")
                ):
                    return finalize(status="failure", failure=failure_code,
                                    responsibility="budget" if failure_code == "controller_cost_limit" else "framework")
                return finalize(
                    status="failure",
                    failure="controller_transport_failure",
                    responsibility="research",
                )
            if turn.tool_calls:
                requested_tool_action_count += len(turn.tool_calls)
                if not tool_enabled or finalization_only:
                    return finalize(
                        status="failure", failure="CONTROLLER_TOOL_CALL_NOT_AUTHORIZED"
                    )
                assert isinstance(spec, ControllerSessionSpecV2)
                assert self.tool_runtime is not None
                try:
                    proposed_tool_calls = turn.tool_calls
                    if pending_required_operations:
                        # Required operations form an adaptive frontier: observe
                        # each result before authorizing the next action. Providers
                        # may still emit several calls in one response even when
                        # instructed to call one function. Accept only the first
                        # proposed action, observe it, and ask for a fresh decision;
                        # the remaining calls were conditioned on evidence that did
                        # not yet exist and therefore are never dispatched.
                        proposed_tool_calls = turn.tool_calls[:1]
                    proposed_tool_calls = tuple(
                        item if isinstance(item, ControllerToolCallIntentV1)
                        else ControllerToolCallIntentV1.model_validate(item)
                        for item in proposed_tool_calls
                    )
                    for intent in proposed_tool_calls:
                        if intent.callable_id in callable_tools_by_id:
                            await input_revisions.capture_input_sources(
                                callable_tools_by_id[intent.callable_id], intent, input_source_reader,
                            )
                    repeat_fingerprints = {
                        intent.provider_tool_call_id: input_revisions.fingerprint(
                            callable_tools_by_id[intent.callable_id], intent,
                        )
                        for intent in proposed_tool_calls
                        if isinstance(intent, ControllerToolCallIntentV1)
                        and intent.callable_id in callable_tools_by_id
                    }
                    intents = prevalidate_tool_call_intents(
                        intents=proposed_tool_calls,
                        callable_tools=spec.callable_tools,
                        session_id=snapshot.session_id,
                        turn_id=turn_id,
                        current_tool_call_count=tool_call_attempt_count,
                        prior_fingerprint_counts=tool_fingerprint_counts,
                        max_tool_calls=self.policy.max_tool_calls,
                        max_same_call_repeats=self.policy.max_same_call_repeats,
                        repeat_fingerprints=repeat_fingerprints,
                    )
                    _validate_authoritative_controller_write_intents(
                        intents=intents,
                        callable_tools=spec.callable_tools,
                        controller_context=controller_context or {},
                    )
                except (ControllerToolRuntimeError, TypeError, ValueError) as exc:
                    failure_code = getattr(
                        exc,
                        "code",
                        getattr(
                            exc,
                            "failure_code",
                            "controller_tool_call_intent_invalid",
                        ),
                    )
                    if isinstance(exc, OutputContractViolation):
                        diagnostic = str(exc.diagnostic or "")
                        fingerprint = canonical_sha256({
                            "failure_code": failure_code,
                            "candidate_sha256": turn.candidate_sha256,
                        })
                        failure_counts[fingerprint] = failure_counts.get(fingerprint, 0) + 1
                        if (
                            failure_counts[fingerprint]
                            < self.policy.max_same_failure_repeats
                            and len(feedback_items) < self.policy.max_semantic_repairs
                            and turn_index < self.policy.max_turns
                        ):
                            feedback = _validation_feedback(
                                target_contract=authoritative_output_contract,
                                candidate_sha256=turn.candidate_sha256,
                                reason=_output_contract_violation_reason(
                                    "$.tools.content", exc
                                ),
                            )
                            feedback_items.append(feedback)
                            if ledger is not None:
                                ledger.record_controller_validation_feedback(
                                    session_id=snapshot.session_id,
                                    turn_id=turn.turn_id,
                                    controller_session_spec_sha256=spec.spec_sha256,
                                    controller_policy_sha256=self.policy.policy_sha256,
                                    input_snapshot_sha256=snapshot.snapshot_sha256,
                                    feedback_sha256=feedback.feedback_sha256,
                                    target_contract_sha256=feedback.target_contract_sha256,
                                    previous_candidate_sha256=feedback.previous_candidate_sha256,
                                )
                            repair_payload = {
                                "failure_code": failure_code,
                                "tool_executed": False,
                                "instruction": (
                                    "The proposed content for the declared final file "
                                    "failed its authoritative deterministic output "
                                    "validator before any write occurred. Correct the "
                                    "content against the unchanged mandatory acceptance "
                                    "criteria, examples, and final format, then issue only "
                                    "the required write call. Do not weaken requirements "
                                    "or repeat invalid content."
                                ),
                            }
                            if diagnostic:
                                repair_payload["validator_diagnostic"] = diagnostic
                            conversation_messages.append({
                                "role": "user",
                                "content": json.dumps(
                                    repair_payload,
                                    ensure_ascii=False,
                                    sort_keys=True,
                                    separators=(",", ":"),
                                ),
                            })
                            continue
                    if failure_code in {
                        "controller_tool_call_limit",
                        "controller_tool_unobserved_batch_limit",
                    }:
                        # No member of an oversized turn was dispatched. Give the
                        # controller one bounded opportunity to use the remaining
                        # allowance or conclude from evidence already observed.
                        # Never silently execute a prefix of a proposed batch.
                        fingerprint = canonical_sha256({
                            "failure_code": failure_code,
                            "candidate_sha256": turn.candidate_sha256,
                        })
                        failure_counts[fingerprint] = failure_counts.get(fingerprint, 0) + 1
                        if (
                            failure_counts[fingerprint] < self.policy.max_same_failure_repeats
                            and len(feedback_items) < self.policy.max_semantic_repairs
                            and turn_index < self.policy.max_turns
                        ):
                            feedback = _validation_feedback(
                                target_contract=spec.expected_output_contract,
                                candidate_sha256=turn.candidate_sha256,
                                reason=("$.tools:batch_exceeds_remaining_allowance"
                                        if failure_code == "controller_tool_call_limit"
                                        else "$.tools:batch_requires_intermediate_observation"),
                            )
                            feedback_items.append(feedback)
                            if ledger is not None:
                                ledger.record_controller_validation_feedback(
                                    session_id=snapshot.session_id,
                                    turn_id=turn.turn_id,
                                    controller_session_spec_sha256=spec.spec_sha256,
                                    controller_policy_sha256=self.policy.policy_sha256,
                                    input_snapshot_sha256=snapshot.snapshot_sha256,
                                    feedback_sha256=feedback.feedback_sha256,
                                    target_contract_sha256=feedback.target_contract_sha256,
                                    previous_candidate_sha256=feedback.previous_candidate_sha256,
                                )
                            remaining = max(0, self.policy.max_tool_calls - tool_call_attempt_count)
                            per_turn = 1
                            conversation_messages.append({
                                "role": "user",
                                "content": json.dumps({
                                    "failure_code": failure_code,
                                    "tool_executed": False,
                                    "requested_tool_calls": len(turn.tool_calls),
                                    "remaining_tool_calls": remaining,
                                    "maximum_tool_calls_this_turn": min(remaining, per_turn)
                                    if failure_code == "controller_tool_unobserved_batch_limit"
                                    else remaining,
                                    "pending_required_tool_operations": list(pending_required_operations),
                                    "instruction": (
                                        "Use the evidence already obtained to return a valid final answer "
                                        "if it is sufficient. Otherwise request no more than "
                                        "maximum_tool_calls_this_turn authorized Tool calls, "
                                        "then inspect their results before choosing more actions. "
                                        "If evidence remains insufficient, state that honestly; "
                                        "do not guess or weaken the output contract."
                                    ),
                                }, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                            })
                            continue
                    return finalize(
                        status="failure", failure=str(failure_code),
                        terminal=ControllerToolTerminalContext(
                            failure_stage=getattr(exc, "failure_stage", "controller_tool_prevalidation"),
                            failure_code=str(failure_code),
                            responsibility=getattr(exc, "responsibility", "framework"),
                            session_id=snapshot.session_id, turn_id=turn_id,
                        ),
                    )
                accepted_tool_action_count += len(intents)
                for intent in intents:
                    repeat_key = repeat_fingerprints.get(
                        intent.provider_tool_call_id, intent.call_fingerprint_sha256,
                    )
                    tool_fingerprint_counts[repeat_key] = tool_fingerprint_counts.get(repeat_key, 0) + 1
                    if ledger is not None:
                        ledger.record_controller_tool_call_validated(
                            session_id=snapshot.session_id,
                            turn_id=turn_id,
                            provider_tool_call_id=intent.provider_tool_call_id,
                            callable_id=intent.callable_id,
                            intent_sha256=intent.intent_sha256,
                            dynamic_arguments_sha256=(
                                intent.dynamic_arguments_sha256
                            ),
                            runtime_protocol=CONTROLLER_TOOL_RUNTIME_PROTOCOL,
                        )
                action_message = {
                    "role": "assistant",
                    "content": turn.content,
                    "tool_calls": [
                        {
                            "id": intent.provider_tool_call_id,
                            "type": "function",
                            "function": {
                                "name": intent.provider_tool_name,
                                "arguments": canonical_json_bytes(
                                    intent.normalized_dynamic_arguments
                                ).decode("utf-8"),
                            },
                        }
                        for intent in intents
                    ],
                }
                observations: list[dict[str, Any]] = []
                repeated_failure_route_terminal: ControllerToolTerminalContext | None = None
                for intent in intents:
                    tool_call_attempt_count += 1
                    invocation = None
                    audit_references = None
                    terminal_error = None
                    cancellation = None
                    try:
                        received = await self.tool_runtime.execute_tool_call(
                            intent=intent,
                            max_inline_result_bytes=self.policy.max_inline_tool_result_bytes,
                        )
                        if not isinstance(received, ControllerToolInvocationResultV1):
                            raise ControllerToolRuntimeError("controller_tool_invocation_result_invalid")
                        audit_references = received.audit_references_for(intent)
                        invocation = received
                        # Consumption belongs to the same boundary as Gateway dispatch.
                        public_content = canonical_json_bytes(
                            _project_tool_observation_for_model(
                                {**invocation.observation.public_projection(),
                                 "observation_id": f"obs_{len(tool_results) + 1}"},
                                task=task_for_projection,
                                secondary_task=secondary_task,
                                max_bytes=self.policy.max_inline_tool_result_bytes,
                            )
                        ).decode("utf-8")
                    except (asyncio.CancelledError, KeyboardInterrupt, SystemExit) as exc:
                        cancellation = exc
                        terminal_error = ControllerToolRuntimeError(
                            "controller_tool_cancelled",
                            failure_stage=("controller_tool_observation_consumption" if audit_references
                                           else "controller_tool_runtime"),
                            terminal_context=getattr(exc, "terminal_context", None),
                        )
                    except Exception as exc:
                        terminal_error = exc if isinstance(exc, ControllerToolRuntimeError) else (
                            ControllerToolRuntimeError(
                                "controller_tool_observation_consumption_failed",
                                failure_stage="controller_tool_observation_consumption",
                            )
                        )
                    if terminal_error is not None:
                        tool_failure_count += 1
                        invocation = invocation or terminal_error.invocation_result
                        if isinstance(invocation, ControllerToolInvocationResultV1):
                            tool_results.append(invocation)
                        else:
                            invocation = None
                        terminal = terminal_error.terminal_context
                        if audit_references is not None:
                            terminal = audit_references.terminal_context(terminal_error)
                        if terminal is None:
                            obs = invocation.observation if invocation else None
                            terminal = ControllerToolTerminalContext(
                                failure_stage=terminal_error.failure_stage,
                                failure_code=terminal_error.code,
                                responsibility=terminal_error.responsibility,
                                session_id=snapshot.session_id, turn_id=turn_id,
                                provider_tool_call_id=intent.provider_tool_call_id,
                                callable_id=intent.callable_id,
                                resource_call_id=obs.resource_call_id if obs else None,
                                resource_dispatched=obs is not None,
                                resource_outcome="result_received" if obs else "unknown",
                                observation_sha256=obs.observation_sha256 if obs else None,
                                provenance_sha256=obs.provenance_sha256 if obs else None,
                                realized_output_sha256=obs.realized_output_sha256 if obs else None,
                                evidence_incomplete=True,
                            )
                        failed_tool_attempts.append(terminal)
                        terminal_result = finalize(
                            status="failure", failure=terminal.failure_code, terminal=terminal,
                        )
                        if cancellation is not None:
                            cancellation.terminal_context = terminal
                            cancellation.session_result = terminal_result
                            raise cancellation
                        return terminal_result
                    assert invocation is not None
                    tool_results.append(invocation)
                    terminal_progress.controller_observation(spec.subtask_id, spec.controller_step_id, turn_index, invocation.observation)
                    check_progress.observe(intent, invocation, f"obs_{len(tool_results)}")
                    input_revisions.observe(
                        callable_tools_by_id[intent.callable_id], intent, invocation,
                    )
                    if invocation.observation.status == "success":
                        tool_success_count += 1
                        last_tool_failure_route = None
                        consecutive_tool_failure_routes = 0
                    else:
                        tool_failure_count += 1
                        failure_route = _tool_failure_route_fingerprint(
                            invocation, dynamic_arguments_sha256=intent.dynamic_arguments_sha256,
                        )
                        if failure_route == last_tool_failure_route:
                            consecutive_tool_failure_routes += 1
                        else:
                            last_tool_failure_route = failure_route
                            consecutive_tool_failure_routes = 1
                        if (
                            repeated_failure_route_terminal is None
                            and consecutive_tool_failure_routes
                            >= self.policy.max_same_failure_repeats
                        ):
                            observation = invocation.observation
                            original_failure = audit_references.original_resource_failure
                            failure_stage = (
                                original_failure.failure_stage
                                if original_failure is not None
                                else "controller_tool_observation"
                            )
                            responsibility = str(
                                observation.failure_responsibility or "research"
                            )
                            if responsibility not in {
                                "framework", "infrastructure", "research", "budget"
                            }:
                                responsibility = "framework"
                            route_error = ControllerToolRuntimeError(
                                str(observation.failure_code or "tool_observation_failed"),
                                responsibility=responsibility,
                                failure_stage=failure_stage,
                            )
                            repeated_failure_route_terminal = (
                                audit_references.terminal_context(route_error)
                            )
                            failed_tool_attempts.append(
                                repeated_failure_route_terminal
                            )
                    observations.append({
                        "role": "tool", "tool_call_id": intent.provider_tool_call_id,
                        "content": public_content,
                    })
                    if os.environ.get("SGAR_RESEARCH_NAVIGATION_TRACE") == "1" and getattr(ledger, "output_dir", None):
                        from .research_navigation_audit import record_navigation
                        record_navigation(ledger.output_dir, intent.normalized_dynamic_arguments, public_content)
                conversation_messages.append(action_message)
                conversation_messages.extend(observations)
                failure_guidance = _failed_tool_observation_guidance(
                    tool_results[-len(intents):]
                )
                if failure_guidance is not None:
                    conversation_messages.append(failure_guidance)
                if repeated_failure_route_terminal is not None:
                    return finalize(
                        status="failure",
                        failure=repeated_failure_route_terminal.failure_code,
                        terminal=repeated_failure_route_terminal,
                    )
                if pending_required_operations:
                    still_missing = _missing_required_tool_operations(
                        required_operations, tool_results,
                    )
                    if set(still_missing) < set(pending_required_operations):
                        stalled_required_batches = 0
                        progress_notice_sent = False
                    elif still_missing:
                        stalled_required_batches += 1
                        if stalled_required_batches >= 2 and not progress_notice_sent:
                            conversation_messages.append({
                                "role": "user",
                                "content": json.dumps({
                                    "framework_progress_status": "required_operation_not_advanced",
                                    "pending_required_tool_operations": list(still_missing),
                                    "instruction": (
                                        "Use the observed Tool results to advance a pending "
                                        "operation. Change the route if the current one cannot "
                                        "produce its required evidence; do not treat repeated "
                                        "calls to an already satisfied operation as completion."
                                    ),
                                }, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                            })
                            progress_notice_sent = True
                authoritative_output = _authoritative_tool_terminal_output(
                    expected_output_contract=authoritative_output_contract,
                    original_request=task_for_projection,
                    required_operations=required_operations,
                    tool_results=tool_results,
                )
                if authoritative_output is not None and not check_progress.pending():
                    return finalize(status="success", output=authoritative_output)
                if turn_index >= self.policy.max_turns:
                    return finalize(
                        status="failure", failure="controller_turn_limit", responsibility="budget"
                    )
                continue
            finalization_diagnostics: dict[str, Any] = {}
            authoritative_output = (
                _authoritative_tool_terminal_output(
                    expected_output_contract=authoritative_output_contract,
                    original_request=task_for_projection,
                    required_operations=required_operations,
                    tool_results=tool_results,
                )
                if tool_enabled
                else None
            )
            if authoritative_output is not None and not check_progress.pending():
                valid, output, reason = True, authoritative_output, None
            else:
                candidate_content = turn.content
                if materialized_output is None and tool_enabled and tool_results and materialized_output_reader is not None:
                    materialized_output = await materialized_output_reader()
                if finalization_evidence_audit:
                    grounded, candidate_content, reason = (
                        _validate_finalization_evidence_audit(
                            turn.content,
                            acceptance_criteria=acceptance_criteria,
                            tool_results=tool_results,
                            materialized_output=materialized_output,
                            diagnostics=finalization_diagnostics,
                        )
                    )
                    if not grounded:
                        valid, output = False, ""
                    else:
                        valid, output, reason = _validate_final_candidate(
                            candidate_content, authoritative_output_contract,
                            format_enforcement=None,
                            generated_source_contract=(controller_context or {}).get("generated_source_contract"),
                        )
                else:
                    valid, output, reason = _validate_final_candidate(
                        materialized_output if materialized_output is not None else candidate_content,
                        authoritative_output_contract,
                        format_enforcement=(
                            None if tool_enabled else format_enforcement
                        ),
                        generated_source_contract=(controller_context or {}).get("generated_source_contract"),
                    )
                if valid and tool_enabled:
                    missing_operations = _missing_required_tool_operations(
                        required_operations, tool_results,
                    )
                    if missing_operations:
                        valid = False
                        reason = (
                            "$:required_tool_operations_not_successful:"
                            + ",".join(missing_operations)
                        )
            if (
                valid and tool_enabled
                and (controller_context or {}).get("delivery_scope") == "task_final"
                and materialized_delivery_state is not None
                and materialized_delivery_state.get("verification_scope")
                == "declared_path_presence_and_file_identity"
            ):
                missing_paths = [
                    str(item["path"])
                    for item in materialized_delivery_state.get("required_outputs", ())
                    if isinstance(item, Mapping) and item.get("present") is False
                    and item.get("path")
                ]
                if missing_paths:
                    # The final artifact gate already requires these paths.
                    # Return the observed absence to this active session before
                    # paying for a new plan. Do not prescribe a writer or reject
                    # a step whose following consumer will materialize its value.
                    valid = False
                    reason = "$:finalization_required_paths_missing:" + json.dumps(
                        missing_paths, ensure_ascii=False, separators=(",", ":"),
                    )
            if valid:
                if check_progress.pending():
                    valid = False
                    reason = "$:finalization_explicit_checks_unexecuted:" + ",".join(
                        item["check_id"] for item in check_progress.pending()
                    )
            if valid:
                return finalize(status="success", output=output)

            final_validation_reason = str(reason or "$:invalid")
            evidence_rejected = final_validation_reason.startswith("$:finalization_")
            if evidence_rejected and ledger is not None:
                recorder = getattr(ledger, "record_controller_finalization_diagnostic", None)
                if callable(recorder):
                    recorder(session_id=snapshot.session_id, turn_id=turn.turn_id,
                             candidate_content=turn.content,
                             candidate_sha256=turn.candidate_sha256,
                             validation_reason=final_validation_reason,
                             diagnostics=finalization_diagnostics,
                             acceptance_criteria=list(acceptance_criteria),
                             evidence_contract=_finalization_evidence_contract(tool_results, acceptance_criteria))
            fingerprint = canonical_sha256(
                {
                    "reason": reason,
                    "candidate_sha256": turn.candidate_sha256,
                }
            )
            failure_counts[fingerprint] = failure_counts.get(fingerprint, 0) + 1
            if failure_counts[fingerprint] >= self.policy.max_same_failure_repeats:
                return finalize(status="failure", failure="controller_no_progress", responsibility="research")
            if len(feedback_items) >= self.policy.max_semantic_repairs:
                return finalize(
                    status="failure",
                    failure=("controller_required_operation_unsatisfied"
                             if str(reason).startswith("$:required_tool_operations_not_successful:")
                             else "controller_finalization_evidence_unsatisfied"
                             if evidence_rejected
                             else "controller_turn_limit"),
                    responsibility=("research"
                                    if evidence_rejected or str(reason).startswith("$:required_tool_operations_not_successful:")
                                    else "budget"),
                )
            if turn_index >= self.policy.max_turns and not (
                tool_enabled and acceptance_criteria and tool_results
                and _controller_validation_category(final_validation_reason) == "evidence_protocol_invalid"
            ):
                return finalize(
                    status="failure",
                    failure=("controller_required_operation_unsatisfied"
                             if str(reason).startswith("$:required_tool_operations_not_successful:")
                             else "controller_finalization_evidence_unsatisfied"
                             if evidence_rejected
                             else "controller_turn_limit"),
                    responsibility=("research"
                                    if evidence_rejected or str(reason).startswith("$:required_tool_operations_not_successful:")
                                    else "budget"),
                )
            feedback = _validation_feedback(
                target_contract=authoritative_output_contract,
                candidate_sha256=turn.candidate_sha256,
                reason=str(reason or "$:invalid"),
            )
            feedback_items.append(feedback)
            if ledger is not None:
                ledger.record_controller_validation_feedback(
                    session_id=snapshot.session_id,
                    turn_id=turn.turn_id,
                    controller_session_spec_sha256=spec.spec_sha256,
                    controller_policy_sha256=self.policy.policy_sha256,
                    input_snapshot_sha256=snapshot.snapshot_sha256,
                    feedback_sha256=feedback.feedback_sha256,
                    target_contract_sha256=feedback.target_contract_sha256,
                    previous_candidate_sha256=feedback.previous_candidate_sha256,
                    validation_reason=feedback.bounded_reason.split(":", 2)[1],
                    validation_category=_controller_validation_category(final_validation_reason),
                )
            conversation_messages.extend(
                (
                    {"role": "assistant", "content": turn.content},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {**feedback.model_dump(mode="json"),
                             **({"evidence_audit_correction": {
                                 "diagnostics": finalization_diagnostics,
                                 "instruction": (
                                     "Correct the identified envelope field or row using the existing observations "
                                     "and response_template. Do not rerun successful edits or checks to repair "
                                     "a reference. If evidence is genuinely missing, report ready=false; never "
                                     "invent support. Public output remains in final_output or the materialized file."
                                 ),
                             }} if finalization_diagnostics else {})},
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    },
                )
            )

        return finalize(status="failure", failure="controller_turn_limit", responsibility="budget")


__all__ = [
    "CONTROLLER_SESSION_POLICY_PROTOCOL",
    "CONTROLLER_SESSION_PROTOCOL",
    "CONTROLLER_SESSION_V2_PROTOCOL",
    "CONTROLLER_SESSION_SUMMARY_V2_PROTOCOL",
    "ControllerInputDescriptorV1",
    "ControllerSessionError",
    "ControllerSessionInputSnapshotV1",
    "ControllerSessionPolicyV1",
    "ControllerSessionResultV1",
    "ControllerSessionRunner",
    "ControllerSessionSpec",
    "ControllerSessionSpecV1",
    "ControllerSessionSpecV2",
    "ControllerSessionSummaryV1",
    "ControllerSessionSummaryV2",
    "ControllerToolRuntimePort",
    "ControllerTurnResultV1",
    "ValidationFeedbackV1",
    "build_controller_input_snapshot",
    "derive_controller_session_spec",
    "load_controller_session_policy",
]
