"""Auditable language policy for model-visible SGAR framework text.

The policy applies only to framework-authored instructions and labels. User
requests, public materials, resource manifests, and quoted evidence remain
byte-preserving data and are never translated by this module.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from pydantic import Field, model_validator

from .pipeline_control import FrozenContract, canonical_sha256


INTERNAL_LANGUAGE_POLICY_PROTOCOL = "sgar-internal-language-policy-v1"
PROMPT_SURFACE_REGISTRY_PROTOCOL = "sgar-prompt-surface-registry-v1"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMPT_ROOT = Path(__file__).resolve().parent / "prompts"
_CJK_INSTRUCTION = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


class InternalLanguagePolicyV1(FrozenContract):
    """Framework-level language boundary; it is not a model output contract."""

    protocol: Literal[INTERNAL_LANGUAGE_POLICY_PROTOCOL] = (
        INTERNAL_LANGUAGE_POLICY_PROTOCOL
    )
    framework_instruction_language: Literal["en"] = "en"
    internal_model_output_language: Literal["en"] = "en"
    source_content_policy: Literal["preserve_original"] = "preserve_original"
    delivery_language_policy: Literal["explicit_or_match_request"] = (
        "explicit_or_match_request"
    )
    policy_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "InternalLanguagePolicyV1":
        projection = self.model_dump(mode="python", exclude={"policy_sha256"})
        expected = canonical_sha256(projection)
        if self.policy_sha256 and self.policy_sha256 != expected:
            raise ValueError("internal_language_policy_sha256_mismatch")
        object.__setattr__(self, "policy_sha256", expected)
        return self


INTERNAL_LANGUAGE_POLICY = InternalLanguagePolicyV1()


@dataclass(frozen=True)
class PromptSurfaceSource:
    role: str
    protocol_version: str
    template_source: str
    text: str
    response_schema_sha256: str = ""
    few_shot_sha256: str = ""
    dynamic_renderer: str = "canonical_typed_user_data"
    model_policy: str = "role_configuration"
    response_mode_policy: str = "native_strict_preferred"
    output_budget_policy: str = "role_configuration"


class PromptSurfaceRecordV1(FrozenContract):
    role: str = Field(min_length=1)
    protocol_version: str = Field(min_length=1)
    template_source: str = Field(min_length=1)
    template_sha256: str
    response_schema_sha256: str = ""
    language_policy_sha256: str
    few_shot_sha256: str = ""
    dynamic_renderer: str = Field(min_length=1)
    model_policy: str = Field(min_length=1)
    response_mode_policy: str = Field(min_length=1)
    output_budget_policy: str = Field(min_length=1)


class PromptSurfaceRegistryV1(FrozenContract):
    protocol: Literal[PROMPT_SURFACE_REGISTRY_PROTOCOL] = (
        PROMPT_SURFACE_REGISTRY_PROTOCOL
    )
    language_policy: InternalLanguagePolicyV1
    records: tuple[PromptSurfaceRecordV1, ...]
    registry_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "PromptSurfaceRegistryV1":
        roles = [item.role for item in self.records]
        if roles != sorted(roles) or len(roles) != len(set(roles)):
            raise ValueError("prompt_surface_roles_not_unique_sorted")
        projection = self.model_dump(mode="python", exclude={"registry_sha256"})
        expected = canonical_sha256(projection)
        if self.registry_sha256 and self.registry_sha256 != expected:
            raise ValueError("prompt_surface_registry_sha256_mismatch")
        object.__setattr__(self, "registry_sha256", expected)
        return self


def prompt_file_text(filename: str) -> str:
    path = (PROMPT_ROOT / filename).resolve()
    try:
        path.relative_to(PROMPT_ROOT.resolve())
    except ValueError as exc:
        raise ValueError("prompt_template_scope_escape") from exc
    return path.read_text(encoding="utf-8-sig")


def assert_english_framework_instruction(text: str, *, source: str) -> None:
    """Reject CJK inside registered framework templates.

    Dynamic user data and resource text are intentionally never passed here.
    """

    match = _CJK_INSTRUCTION.search(str(text))
    if match is not None:
        raise ValueError(f"framework_prompt_contains_cjk:{source}:{match.start()}")


def _schema_sha256(role: str) -> str:
    try:
        from .model_response_contracts import system_role_requirement

        return system_role_requirement(role).wire_schema_sha256
    except (KeyError, ValueError):
        return ""


def registered_prompt_sources() -> tuple[PromptSurfaceSource, ...]:
    """Return the authoritative production prompt inventory.

    Inline constants are imported rather than copied so the recorded hash is
    always bound to the bytes used by the request builder.
    """

    from .full_generation import (
        FULL_GENERATION_PROMPT_VERSION,
        FULL_GENERATION_SYSTEM_PROMPT,
    )
    from .executors import AGENT_EXECUTOR_SYSTEM_PROMPT
    from .plan_compiler import (
        PLAN_ADAPTATION_PROMPT_VERSION,
        PLAN_ADAPTATION_SYSTEM_PROMPT_V1,
        PLAN_COMPILER_PROMPT_VERSION,
        PLAN_COMPILER_SYSTEM_PROMPT_V3,
        _COMPILER_FEW_SHOT_JSON,
    )
    from .planner import (
        PLANNER_FEW_SHOT_SHA256,
        PLANNER_REPLAN_PROMPT_VERSION,
        PLANNER_REPLAN_SYSTEM_PROMPT,
        _PLANNER_PROMPT_VERSION,
    )
    from .router import PLAN_COMPILER_SYSTEM_PROMPT
    from .temporary_tool import (
        TEMPORARY_TOOL_GENERATION_PROMPT_VERSION,
        TEMPORARY_TOOL_GENERATION_SYSTEM_PROMPT,
    )

    profiler_text = prompt_file_text("profiler_system.txt")
    return tuple(
        sorted(
            (
                PromptSurfaceSource(
                    role="agent",
                    protocol_version="sgar-agent-execution-input-v1",
                    template_source="sgar_mvp.src.executors:AGENT_EXECUTOR_SYSTEM_PROMPT",
                    text=AGENT_EXECUTOR_SYSTEM_PROMPT,
                    dynamic_renderer="agent_execution_renderer_v1",
                ),
                PromptSurfaceSource(
                    role="evaluator",
                    protocol_version="sgar-evaluator-policy-v2",
                    template_source="sgar_mvp/src/prompts/evaluator_system.txt",
                    text=prompt_file_text("evaluator_system.txt"),
                    response_schema_sha256=_schema_sha256("evaluator"),
                ),
                PromptSurfaceSource(
                    role="executor",
                    protocol_version="sgar-resource-invocation-v2",
                    template_source="sgar_mvp/src/prompts/executor_system.txt",
                    text=prompt_file_text("executor_system.txt"),
                    dynamic_renderer="resource_invocation_renderer_v2",
                ),
                PromptSurfaceSource(
                    role="full_generation",
                    protocol_version=FULL_GENERATION_PROMPT_VERSION,
                    template_source="sgar_mvp.src.full_generation:FULL_GENERATION_SYSTEM_PROMPT",
                    text=FULL_GENERATION_SYSTEM_PROMPT,
                    response_schema_sha256=_schema_sha256("full_generation"),
                ),
                PromptSurfaceSource(
                    role="plan_adaptation",
                    protocol_version=PLAN_ADAPTATION_PROMPT_VERSION,
                    template_source="sgar_mvp.src.plan_compiler:PLAN_ADAPTATION_SYSTEM_PROMPT_V1",
                    text=PLAN_ADAPTATION_SYSTEM_PROMPT_V1,
                    response_schema_sha256=_schema_sha256("plan_adaptation"),
                ),
                PromptSurfaceSource(
                    role="plan_compiler",
                    protocol_version=PLAN_COMPILER_PROMPT_VERSION,
                    template_source="sgar_mvp.src.plan_compiler:PLAN_COMPILER_SYSTEM_PROMPT_V3",
                    text=PLAN_COMPILER_SYSTEM_PROMPT_V3,
                    response_schema_sha256=_schema_sha256("plan_compiler"),
                    few_shot_sha256=hashlib.sha256(
                        _COMPILER_FEW_SHOT_JSON.encode("utf-8")
                    ).hexdigest(),
                ),
                PromptSurfaceSource(
                    role="planner",
                    protocol_version=_PLANNER_PROMPT_VERSION,
                    template_source="sgar_mvp/src/prompts/planner_system.txt",
                    text=prompt_file_text("planner_system.txt"),
                    response_schema_sha256=_schema_sha256("planner"),
                    few_shot_sha256=PLANNER_FEW_SHOT_SHA256,
                ),
                PromptSurfaceSource(
                    role="planner_replan",
                    protocol_version=PLANNER_REPLAN_PROMPT_VERSION,
                    template_source="sgar_mvp.src.planner:PLANNER_REPLAN_SYSTEM_PROMPT",
                    text=PLANNER_REPLAN_SYSTEM_PROMPT,
                ),
                PromptSurfaceSource(
                    role="profiler",
                    protocol_version="sgar-profiler-output-v2",
                    template_source="sgar_mvp/src/prompts/profiler_system.txt",
                    text=profiler_text,
                    response_schema_sha256=_schema_sha256("hyde"),
                    few_shot_sha256=hashlib.sha256(
                        profiler_text.split("<few_shots>", 1)[-1].encode("utf-8")
                    ).hexdigest(),
                    model_policy="sol_only_exact_configuration",
                    response_mode_policy="probed_native_strict_or_local_validator",
                    output_budget_policy="profiler_generation_policy_v2",
                ),
                PromptSurfaceSource(
                    role="router_policy",
                    protocol_version="legacy-router-policy-readonly-v1",
                    template_source="sgar_mvp.src.router:PLAN_COMPILER_SYSTEM_PROMPT",
                    text=PLAN_COMPILER_SYSTEM_PROMPT,
                    response_schema_sha256=_schema_sha256("router_policy"),
                ),
                PromptSurfaceSource(
                    role="temporary_tool",
                    protocol_version=TEMPORARY_TOOL_GENERATION_PROMPT_VERSION,
                    template_source="sgar_mvp.src.temporary_tool:TEMPORARY_TOOL_GENERATION_SYSTEM_PROMPT",
                    text=TEMPORARY_TOOL_GENERATION_SYSTEM_PROMPT,
                    response_schema_sha256=_schema_sha256("temporary_tool"),
                ),
            ),
            key=lambda item: item.role,
        )
    )


def build_prompt_surface_registry() -> PromptSurfaceRegistryV1:
    records: list[PromptSurfaceRecordV1] = []
    for source in registered_prompt_sources():
        assert_english_framework_instruction(source.text, source=source.template_source)
        records.append(
            PromptSurfaceRecordV1(
                role=source.role,
                protocol_version=source.protocol_version,
                template_source=source.template_source,
                template_sha256=hashlib.sha256(source.text.encode("utf-8")).hexdigest(),
                response_schema_sha256=source.response_schema_sha256,
                language_policy_sha256=INTERNAL_LANGUAGE_POLICY.policy_sha256,
                few_shot_sha256=source.few_shot_sha256,
                dynamic_renderer=source.dynamic_renderer,
                model_policy=source.model_policy,
                response_mode_policy=source.response_mode_policy,
                output_budget_policy=source.output_budget_policy,
            )
        )
    return PromptSurfaceRegistryV1(
        language_policy=INTERNAL_LANGUAGE_POLICY,
        records=tuple(records),
    )


def resolve_delivery_language(
    request_text: str,
    *,
    explicit_language: str | None = None,
) -> str:
    """Resolve delivery language without translating or rewriting source text."""

    if explicit_language and explicit_language.strip():
        return explicit_language.strip()
    text = str(request_text)
    cjk_count = len(_CJK_INSTRUCTION.findall(text))
    latin_count = sum(character.isascii() and character.isalpha() for character in text)
    return "zh" if cjk_count > latin_count else "en"


def prompt_registry_json() -> str:
    return json.dumps(
        build_prompt_surface_registry().model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


__all__ = [
    "INTERNAL_LANGUAGE_POLICY",
    "INTERNAL_LANGUAGE_POLICY_PROTOCOL",
    "PROMPT_SURFACE_REGISTRY_PROTOCOL",
    "InternalLanguagePolicyV1",
    "PromptSurfaceRecordV1",
    "PromptSurfaceRegistryV1",
    "assert_english_framework_instruction",
    "build_prompt_surface_registry",
    "prompt_file_text",
    "prompt_registry_json",
    "registered_prompt_sources",
    "resolve_delivery_language",
]
