"""Generic, run-local temporary Tool source management.

Eligibility is derived exclusively from manifest identities, declared runtime
roots, immutable hashes, and filesystem safety checks.  No resource-specific
adapter or task-text rule is permitted here.
"""

from __future__ import annotations

import os
import re
import shutil
import threading
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Sequence

from pydantic import Field, ValidationError, field_validator, model_validator

from .model_accounting import (
    AccountingPersistenceError,
    BudgetControlError,
    ModelCallContext,
    ModelPricingCatalog,
    PricingCatalogError,
    RunCostLedger,
)
from .model_transport import (
    SyncModelTransportPort,
    classify_transport_exception,
    model_request_sha256,
    require_sync_model_transport,
)
from .model_response_contracts import (
    StructuredResponseModeInput,
    normalize_structured_response_mode,
    system_role_requirement,
    system_role_response_format,
    validate_structured_response_content,
)
from .pipeline_control import FrozenContract, SubtaskRevisionRef, canonical_json_bytes, canonical_sha256
from .public_inputs import path_sha256
from .recovery_control import (
    RecoveryControlError,
    RecoveryPolicy,
    TemporarySourceDescriptor,
    TemporaryToolArtifact,
    TemporaryToolSourceBundle,
    assert_recovery_projection_safe,
)
from .resource_runtime import ResourceDefinition


_SOURCE_SECRET_LITERAL = re.compile(
    r"(?i)(?:api[_-]?key|authorization|password|secret|token)\s*=\s*['\"][^'\"]+['\"]"
)

TEMPORARY_TOOL_GENERATION_PROMPT_VERSION = "temporary-tool-generation-v1"
TEMPORARY_TOOL_GENERATION_SYSTEM_PROMPT = (
    "You are SGAR's audited temporary Tool source transformer. Return exactly one "
    "strict JSON object containing protocol, source, and concise_rationale. Produce a "
    "complete UTF-8 replacement for the primary implementation using only the supplied "
    "registered source bundle, public contract, and redacted failure evidence. Do not "
    "emit markdown fences, shell commands, dependency installation, new network access, "
    "host paths, secrets, hidden validation data, or chain-of-thought."
    " Keep concise_rationale in English and preserve literal source identifiers exactly."
)
TEMPORARY_TOOL_GENERATION_PROMPT_SHA256 = canonical_sha256(
    {
        "version": TEMPORARY_TOOL_GENERATION_PROMPT_VERSION,
        "prompt": TEMPORARY_TOOL_GENERATION_SYSTEM_PROMPT,
    }
)
TEMPORARY_TOOL_GENERATION_MAX_TRANSPORT_ATTEMPTS = 3


class TemporaryToolGenerationInput(FrozenContract):
    protocol: Literal["sgar-temporary-tool-generation-v1"] = (
        "sgar-temporary-tool-generation-v1"
    )
    revision: SubtaskRevisionRef
    plan_revision: int = Field(ge=1, le=2)
    candidate_pool_sha256: str
    original_resource_id: str = Field(min_length=1)
    source_bundle_sha256: str
    generation_material_sha256: str
    generator_resource_id: str = Field(min_length=1)
    generator_model_resource_id: str = Field(min_length=1)
    generator_model_api_id: str = Field(min_length=1)
    runner_resource_id: str = Field(min_length=1)
    failure_evidence_sha256: str
    contract_projection: dict[str, Any] = Field(default_factory=dict)
    diagnostic_excerpt: str = Field(default="", max_length=8192)
    prompt_version: Literal[TEMPORARY_TOOL_GENERATION_PROMPT_VERSION] = (
        TEMPORARY_TOOL_GENERATION_PROMPT_VERSION
    )
    prompt_sha256: Literal[TEMPORARY_TOOL_GENERATION_PROMPT_SHA256] = (
        TEMPORARY_TOOL_GENERATION_PROMPT_SHA256
    )
    input_sha256: str = ""

    @field_validator(
        "candidate_pool_sha256",
        "source_bundle_sha256",
        "generation_material_sha256",
        "failure_evidence_sha256",
    )
    @classmethod
    def _hash_fields(cls, value: str, info: Any) -> str:
        normalized = str(value or "").strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", normalized):
            raise ValueError(f"{info.field_name}_invalid")
        return normalized

    @model_validator(mode="after")
    def _seal(self) -> "TemporaryToolGenerationInput":
        if len(self.diagnostic_excerpt.encode("utf-8")) > 8192:
            raise ValueError("temporary_tool_generation_diagnostic_too_large")
        projection = self.model_dump(mode="python", exclude={"input_sha256"})
        assert_recovery_projection_safe(projection)
        expected = canonical_sha256(projection)
        if self.input_sha256 and self.input_sha256 != expected:
            raise ValueError("temporary_tool_generation_input_hash_mismatch")
        object.__setattr__(self, "input_sha256", expected)
        return self


class TemporaryToolGenerationDraft(FrozenContract):
    protocol: Literal["sgar-temporary-tool-generation-v1"] = (
        "sgar-temporary-tool-generation-v1"
    )
    source: str = Field(min_length=1)
    concise_rationale: str = Field(default="")


class TemporaryToolGenerationResult(FrozenContract):
    protocol: Literal["sgar-temporary-tool-generation-v1"] = (
        "sgar-temporary-tool-generation-v1"
    )
    source: str = Field(min_length=1)
    generator_resource_id: str = Field(min_length=1)
    generator_model_resource_id: str = Field(min_length=1)
    generator_accounting_operation_id: str = Field(min_length=1)
    request_sha256: str
    transport_attempts: int = Field(ge=1, le=3)
    response_received: Literal[True] = True
    result_sha256: str = ""

    @field_validator("request_sha256")
    @classmethod
    def _request_hash(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", normalized):
            raise ValueError("temporary_tool_generation_request_hash_invalid")
        return normalized

    @model_validator(mode="after")
    def _seal(self) -> "TemporaryToolGenerationResult":
        projection = self.model_dump(mode="python", exclude={"result_sha256"})
        expected = canonical_sha256(projection)
        if self.result_sha256 and self.result_sha256 != expected:
            raise ValueError("temporary_tool_generation_result_hash_mismatch")
        object.__setattr__(self, "result_sha256", expected)
        return self


class TemporaryToolGenerationError(RecoveryControlError):
    def __init__(
        self,
        code: str,
        *,
        responsibility: Literal["framework", "infrastructure", "research", "budget"],
        response_received: bool,
        request_sha256: str | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.responsibility = responsibility
        self.response_received = bool(response_received)
        self.request_sha256 = request_sha256


@dataclass(frozen=True)
class RegisteredTemporaryToolSource:
    bundle: TemporaryToolSourceBundle
    primary_path: Path
    supporting_paths: tuple[Path, ...]
    source_texts: tuple[str, ...]


def _normalized_manifest_hash(value: Any, *, field_name: str) -> str:
    text = str(value or "").strip().lower()
    if text.startswith("sha256:"):
        text = text[7:]
    if not re.fullmatch(r"[0-9a-f]{64}", text):
        raise RecoveryControlError(f"{field_name}_invalid")
    return text


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


class TemporaryToolManager:
    def __init__(
        self,
        *,
        project_root: str | Path,
        recovery_root: str | Path,
        recovery_runtime_root: str,
        policy: RecoveryPolicy,
        runtime_roots: Sequence[str | Path],
        hidden_roots: Sequence[str | Path] = (),
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=True)
        self.recovery_root = Path(recovery_root).resolve()
        self.recovery_runtime_root = str(recovery_runtime_root).rstrip("/")
        if not self.recovery_runtime_root.startswith("/app/"):
            raise RecoveryControlError("temporary_tool_runtime_root_invalid")
        self.policy = policy
        self.runtime_roots = tuple(Path(item).resolve(strict=True) for item in runtime_roots)
        self.hidden_roots = tuple(Path(item).resolve(strict=True) for item in hidden_roots)
        if not self.runtime_roots:
            raise RecoveryControlError("temporary_tool_runtime_roots_empty")
        self.recovery_root.mkdir(parents=True, exist_ok=True)

    def _source_path(self, uri: Any) -> Path:
        text = str(uri or "").strip()
        if not text.startswith("file://"):
            raise RecoveryControlError("temporary_tool_source_not_local_file")
        locator = text[7:].replace("\\", "/")
        if not locator or locator.startswith("/") or ".." in Path(locator).parts:
            raise RecoveryControlError("temporary_tool_source_locator_invalid")
        candidate = self.project_root.joinpath(*locator.split("/"))
        try:
            path_sha256(candidate)
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise RecoveryControlError("temporary_tool_source_missing") from exc
        except ValueError as exc:
            raise RecoveryControlError("temporary_tool_source_indirection_forbidden") from exc
        if not resolved.is_file() or not _within(resolved, self.project_root):
            raise RecoveryControlError("temporary_tool_source_scope_invalid")
        if not any(_within(resolved, root) for root in self.runtime_roots):
            raise RecoveryControlError("temporary_tool_source_outside_runtime_roots")
        if any(_within(resolved, root) for root in self.hidden_roots):
            raise RecoveryControlError("temporary_tool_source_hidden")
        return resolved

    def _runtime_locator(self, path: Path) -> str:
        relative = path.relative_to(self.project_root).as_posix()
        return f"/app/{relative}"

    def register_source_bundle(
        self,
        *,
        failed_resource_id: str,
        candidate_pool_sha256: str,
        selected_resource_ids: Sequence[str],
        definition: ResourceDefinition,
        manifest: Mapping[str, Any],
    ) -> RegisteredTemporaryToolSource:
        if failed_resource_id != definition.resource_id:
            raise RecoveryControlError("temporary_tool_failed_resource_identity_mismatch")
        if definition.resource_type != "Tool":
            raise RecoveryControlError("temporary_tool_source_requires_tool")
        if failed_resource_id not in set(selected_resource_ids):
            raise RecoveryControlError("temporary_tool_resource_not_selected")
        if str(manifest.get("resource_id") or "") != failed_resource_id:
            raise RecoveryControlError("temporary_tool_manifest_identity_mismatch")
        execution = manifest.get("execution")
        provenance = manifest.get("provenance")
        if not isinstance(execution, Mapping) or not isinstance(provenance, Mapping):
            raise RecoveryControlError("temporary_tool_manifest_source_identity_missing")
        dispatch = str(execution.get("uri") or "").strip()
        local_uri = str(provenance.get("local_implementation_uri") or "").strip()
        if not dispatch.startswith("file://") or dispatch != local_uri:
            raise RecoveryControlError("temporary_tool_dispatch_source_mismatch")
        if not any(item.dispatch == dispatch for item in definition.entrypoints):
            raise RecoveryControlError("temporary_tool_definition_dispatch_mismatch")

        primary = self._source_path(dispatch)
        primary_expected = _normalized_manifest_hash(
            provenance.get("source_hash"),
            field_name="temporary_tool_primary_source_hash",
        )
        if path_sha256(primary) != primary_expected:
            raise RecoveryControlError("temporary_tool_primary_source_hash_mismatch")
        supporting_raw = provenance.get("supporting_source_hashes") or {}
        if not isinstance(supporting_raw, Mapping):
            raise RecoveryControlError("temporary_tool_supporting_hashes_invalid")
        supporting: list[tuple[str, Path, str]] = []
        for uri, expected in sorted(supporting_raw.items(), key=lambda item: str(item[0])):
            path = self._source_path(uri)
            expected_hash = _normalized_manifest_hash(
                expected,
                field_name="temporary_tool_supporting_source_hash",
            )
            if path_sha256(path) != expected_hash:
                raise RecoveryControlError("temporary_tool_supporting_source_hash_mismatch")
            supporting.append((str(uri), path, expected_hash))

        paths = (primary, *(item[1] for item in supporting))
        if len(paths) > self.policy.temporary_tool_bundle_max_files:
            raise RecoveryControlError("temporary_tool_bundle_file_limit_exceeded")
        sizes = tuple(path.stat().st_size for path in paths)
        if sizes[0] > self.policy.temporary_tool_source_max_bytes:
            raise RecoveryControlError("temporary_tool_primary_size_limit_exceeded")
        if sum(sizes) > self.policy.temporary_tool_bundle_max_bytes:
            raise RecoveryControlError("temporary_tool_bundle_size_limit_exceeded")
        texts: list[str] = []
        for path in paths:
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                raise RecoveryControlError("temporary_tool_source_not_utf8") from exc
            assert_recovery_projection_safe(content)
            if _SOURCE_SECRET_LITERAL.search(content):
                raise RecoveryControlError("temporary_tool_source_secret_literal")
            texts.append(content)
        descriptors = (
            TemporarySourceDescriptor(
                logical_runtime_locator=self._runtime_locator(primary),
                source_sha256=primary_expected,
                size_bytes=sizes[0],
                relationship="primary",
            ),
            *(
                TemporarySourceDescriptor(
                    logical_runtime_locator=self._runtime_locator(path),
                    source_sha256=expected_hash,
                    size_bytes=size,
                    relationship="supporting",
                )
                for (_, path, expected_hash), size in zip(supporting, sizes[1:])
            ),
        )
        bundle = TemporaryToolSourceBundle(
            original_resource_id=failed_resource_id,
            original_source_sha256=primary_expected,
            sources=descriptors,
            primary_runtime_locator=self._runtime_locator(primary),
            candidate_pool_sha256=candidate_pool_sha256,
        )
        return RegisteredTemporaryToolSource(
            bundle=bundle,
            primary_path=primary,
            supporting_paths=tuple(item[1] for item in supporting),
            source_texts=tuple(texts),
        )

    def generation_material(self, registered: RegisteredTemporaryToolSource) -> dict[str, Any]:
        return {
            "bundle": registered.bundle.model_dump(mode="json"),
            "sources": [
                {
                    "logical_runtime_locator": descriptor.logical_runtime_locator,
                    "source_sha256": descriptor.source_sha256,
                    "relationship": descriptor.relationship,
                    "content": content,
                }
                for descriptor, content in zip(
                    registered.bundle.sources,
                    registered.source_texts,
                )
            ],
        }

    def finalize_generated_source(
        self,
        *,
        registered: RegisteredTemporaryToolSource,
        generated_source: str,
        generator_resource_id: str,
        generator_accounting_operation_id: str,
        runner_resource_id: str,
        candidate_resource_definitions: Mapping[str, ResourceDefinition],
        plan_revision: int,
    ) -> TemporaryToolArtifact:
        generator = candidate_resource_definitions.get(generator_resource_id)
        runner = candidate_resource_definitions.get(runner_resource_id)
        if generator is None or generator.resource_type not in {"Model", "Agent"}:
            raise RecoveryControlError("temporary_tool_generator_not_candidate_model_or_agent")
        if runner is None or runner.resource_type != "Tool":
            raise RecoveryControlError("temporary_tool_runner_not_candidate_tool")
        raw = generated_source.encode("utf-8")
        if not raw or len(raw) > self.policy.temporary_tool_source_max_bytes:
            raise RecoveryControlError("temporary_tool_generated_source_size_invalid")
        assert_recovery_projection_safe(generated_source)
        if _SOURCE_SECRET_LITERAL.search(generated_source):
            raise RecoveryControlError("temporary_tool_generated_source_secret_literal")
        for descriptor, path in zip(
            registered.bundle.sources,
            (registered.primary_path, *registered.supporting_paths),
        ):
            if path_sha256(path) != descriptor.source_sha256:
                raise RecoveryControlError("temporary_tool_original_source_changed")
        attempt_dir = self.recovery_root / f"plan_revision_{plan_revision}"
        attempt_dir.mkdir(parents=True, exist_ok=True)
        generated_path = attempt_dir / "generated_tool.py"
        if generated_path.exists():
            if generated_path.read_bytes() != raw:
                raise RecoveryControlError("temporary_tool_generated_source_overwrite_forbidden")
        else:
            temporary = attempt_dir / ".generated_tool.py.tmp"
            try:
                with temporary.open("xb") as handle:
                    handle.write(raw)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, generated_path)
            finally:
                temporary.unlink(missing_ok=True)
        supporting_dir = attempt_dir / "support"
        supporting_dir.mkdir(exist_ok=True)
        names = [path.name for path in registered.supporting_paths]
        if len(names) != len(set(names)):
            raise RecoveryControlError("temporary_tool_supporting_basename_collision")
        for path in registered.supporting_paths:
            target = supporting_dir / path.name
            if target.exists() and path_sha256(target) != path_sha256(path):
                raise RecoveryControlError("temporary_tool_supporting_copy_conflict")
            if not target.exists():
                shutil.copyfile(path, target)
        generated_hash = path_sha256(generated_path)
        runtime_locator = (
            f"{self.recovery_runtime_root}/plan_revision_{plan_revision}/generated_tool.py"
        )
        provenance_sha256 = canonical_sha256(
            {
                "source_bundle_sha256": registered.bundle.source_bundle_sha256,
                "generated_source_sha256": generated_hash,
                "generator_resource_id": generator_resource_id,
                "generator_accounting_operation_id": generator_accounting_operation_id,
                "runner_resource_id": runner_resource_id,
                "candidate_pool_sha256": registered.bundle.candidate_pool_sha256,
                "plan_revision": plan_revision,
            }
        )
        artifact = TemporaryToolArtifact(
            original_resource_id=registered.bundle.original_resource_id,
            original_source_sha256=registered.bundle.original_source_sha256,
            support_bundle_sha256=registered.bundle.source_bundle_sha256,
            generated_source_sha256=generated_hash,
            generator_resource_id=generator_resource_id,
            generator_accounting_operation_id=generator_accounting_operation_id,
            runner_resource_id=runner_resource_id,
            runtime_locator=runtime_locator,
            candidate_pool_sha256=registered.bundle.candidate_pool_sha256,
            plan_revision=plan_revision,
            provenance_sha256=provenance_sha256,
        )
        for descriptor, path in zip(
            registered.bundle.sources,
            (registered.primary_path, *registered.supporting_paths),
        ):
            if path_sha256(path) != descriptor.source_sha256:
                raise RecoveryControlError("temporary_tool_original_source_mutated")
        return artifact


class TemporaryToolGenerator:
    """Meter one strict source-generation operation over an audited bundle.

    Model generators resolve directly to themselves. Agent generators must name
    their frozen candidate base Model explicitly; accounting is attributed to
    that Model while the selected Agent remains the semantic generator identity.
    """

    def __init__(
        self,
        *,
        transport: SyncModelTransportPort,
        cost_ledger: RunCostLedger,
        pricing_catalog: ModelPricingCatalog,
        response_mode: StructuredResponseModeInput = "json_schema",
        temperature: float = 0.0,
        max_tokens: int = 8192,
    ) -> None:
        response_mode = normalize_structured_response_mode(response_mode)
        self.transport = require_sync_model_transport(transport)
        self.cost_ledger = cost_ledger
        self.pricing_catalog = pricing_catalog
        self.response_mode = response_mode
        self.temperature = float(temperature)
        self.max_tokens = int(max_tokens)
        self._condition = threading.Condition(threading.RLock())
        self._cache: dict[str, TemporaryToolGenerationResult | TemporaryToolGenerationError] = {}
        self._inflight: set[str] = set()

    @staticmethod
    def build_input(
        *,
        revision: SubtaskRevisionRef,
        plan_revision: int,
        registered: RegisteredTemporaryToolSource,
        generation_material: Mapping[str, Any],
        generator_definition: ResourceDefinition,
        generator_model_resource_id: str,
        generator_model_api_id: str,
        runner_resource_id: str,
        failure_evidence_sha256: str,
        contract_projection: Mapping[str, Any],
        diagnostic_excerpt: str = "",
    ) -> TemporaryToolGenerationInput:
        return TemporaryToolGenerationInput(
            revision=revision,
            plan_revision=plan_revision,
            candidate_pool_sha256=registered.bundle.candidate_pool_sha256,
            original_resource_id=registered.bundle.original_resource_id,
            source_bundle_sha256=registered.bundle.source_bundle_sha256,
            generation_material_sha256=canonical_sha256(generation_material),
            generator_resource_id=generator_definition.resource_id,
            generator_model_resource_id=generator_model_resource_id,
            generator_model_api_id=generator_model_api_id,
            runner_resource_id=runner_resource_id,
            failure_evidence_sha256=failure_evidence_sha256,
            contract_projection=dict(contract_projection),
            diagnostic_excerpt=diagnostic_excerpt,
        )

    def _call_kwargs(
        self,
        envelope: TemporaryToolGenerationInput,
        generation_material: Mapping[str, Any],
        *,
        agent_instruction: str = "",
    ) -> dict[str, Any]:
        if canonical_sha256(generation_material) != envelope.generation_material_sha256:
            raise TemporaryToolGenerationError(
                "temporary_tool_generation_material_hash_mismatch",
                responsibility="framework",
                response_received=False,
            )
        assert_recovery_projection_safe(agent_instruction)
        system_prompt = TEMPORARY_TOOL_GENERATION_SYSTEM_PROMPT
        payload = {
            "input": envelope.model_dump(mode="json"),
            "registered_source_material": dict(generation_material),
            "public_agent_instruction": agent_instruction or None,
            "source_content_policy": "preserve_original",
        }
        kwargs: dict[str, Any] = {
            "model": envelope.generator_model_api_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": canonical_json_bytes(payload).decode("utf-8"),
                },
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        kwargs["response_format"] = system_role_response_format(
            "temporary_tool",
            mode=self.response_mode,
        )
        return kwargs

    def request_sha256(
        self,
        *,
        envelope: TemporaryToolGenerationInput,
        generation_material: Mapping[str, Any],
        agent_instruction: str = "",
    ) -> str:
        """Return the exact immutable transport hash before any ledger start."""

        return model_request_sha256(
            self._call_kwargs(
                envelope,
                generation_material,
                agent_instruction=agent_instruction,
            )
        )

    def generate(
        self,
        *,
        envelope: TemporaryToolGenerationInput,
        generation_material: Mapping[str, Any],
        generator_definition: ResourceDefinition,
        payload_guard: Callable[[Mapping[str, Any]], None],
        agent_instruction: str = "",
    ) -> TemporaryToolGenerationResult:
        if generator_definition.resource_id != envelope.generator_resource_id:
            raise TemporaryToolGenerationError(
                "temporary_tool_generator_identity_mismatch",
                responsibility="framework",
                response_received=False,
            )
        if generator_definition.resource_type not in {"Model", "Agent"}:
            raise TemporaryToolGenerationError(
                "temporary_tool_generator_type_invalid",
                responsibility="research",
                response_received=False,
            )
        price = self.pricing_catalog.resolve(
            resource_id=envelope.generator_model_resource_id,
            api_model_id=envelope.generator_model_api_id,
        )
        if generator_definition.resource_type == "Model" and (
            price.resource_id != generator_definition.resource_id
        ):
            raise TemporaryToolGenerationError(
                "temporary_tool_model_generator_pricing_identity_mismatch",
                responsibility="framework",
                response_received=False,
            )
        if generator_definition.resource_type == "Agent" and not agent_instruction:
            raise TemporaryToolGenerationError(
                "temporary_tool_agent_instruction_missing",
                responsibility="framework",
                response_received=False,
            )
        key = envelope.input_sha256
        with self._condition:
            while key in self._inflight:
                self._condition.wait()
            cached = self._cache.get(key)
            if isinstance(cached, TemporaryToolGenerationResult):
                return cached
            if isinstance(cached, TemporaryToolGenerationError):
                raise cached
            self._inflight.add(key)
        try:
            result = self._generate_once(
                envelope=envelope,
                generation_material=generation_material,
                generator_definition=generator_definition,
                payload_guard=payload_guard,
                agent_instruction=agent_instruction,
            )
            with self._condition:
                self._cache[key] = result
            return result
        except TemporaryToolGenerationError as exc:
            with self._condition:
                self._cache[key] = exc
            raise
        finally:
            with self._condition:
                self._inflight.discard(key)
                self._condition.notify_all()

    def _generate_once(
        self,
        *,
        envelope: TemporaryToolGenerationInput,
        generation_material: Mapping[str, Any],
        generator_definition: ResourceDefinition,
        payload_guard: Callable[[Mapping[str, Any]], None],
        agent_instruction: str,
    ) -> TemporaryToolGenerationResult:
        try:
            api_kwargs = self._call_kwargs(
                envelope,
                generation_material,
                agent_instruction=agent_instruction,
            )
            request_sha256 = model_request_sha256(api_kwargs)
        except TemporaryToolGenerationError:
            raise
        except BaseException as exc:
            raise TemporaryToolGenerationError(
                "temporary_tool_generation_request_invalid",
                responsibility="framework",
                response_received=False,
            ) from exc
        operation_id = f"temporary_tool_generation:{envelope.input_sha256}"
        context = ModelCallContext(
            operation_id=operation_id,
            stage="command_adaptation",
            subtask_id=envelope.revision.subtask_id,
            subtask_revision=envelope.revision.subtask_revision,
            selected_resource_id=envelope.generator_resource_id,
            model_resource_id=envelope.generator_model_resource_id,
            agent_id=(
                envelope.generator_resource_id
                if generator_definition.resource_type == "Agent"
                else None
            ),
        )
        response: Any = None
        attempts = 0
        for attempt in range(1, TEMPORARY_TOOL_GENERATION_MAX_TRANSPORT_ATTEMPTS + 1):
            attempts = attempt
            if model_request_sha256(api_kwargs) != request_sha256:
                raise TemporaryToolGenerationError(
                    "temporary_tool_generation_request_hash_changed",
                    responsibility="framework",
                    response_received=False,
                    request_sha256=request_sha256,
                )
            try:
                payload_guard(deepcopy(api_kwargs))
            except BaseException as exc:
                raise TemporaryToolGenerationError(
                    "temporary_tool_generation_payload_guard_failed",
                    responsibility="framework",
                    response_received=False,
                    request_sha256=request_sha256,
                ) from exc
            try:
                response = self.transport.send(
                    ledger=self.cost_ledger,
                    context=context,
                    **deepcopy(api_kwargs),
                )
            except BudgetControlError as exc:
                raise TemporaryToolGenerationError(
                    "budget_control",
                    responsibility="budget",
                    response_received=False,
                    request_sha256=request_sha256,
                ) from exc
            except (PricingCatalogError, AccountingPersistenceError) as exc:
                raise TemporaryToolGenerationError(
                    "temporary_tool_generation_accounting_failed",
                    responsibility="framework",
                    response_received=False,
                    request_sha256=request_sha256,
                ) from exc
            except BaseException as exc:
                retryable, code = classify_transport_exception(exc)
                if retryable and attempt < TEMPORARY_TOOL_GENERATION_MAX_TRANSPORT_ATTEMPTS:
                    continue
                raise TemporaryToolGenerationError(
                    code,
                    responsibility="infrastructure" if retryable else "framework",
                    response_received=False,
                    request_sha256=request_sha256,
                ) from exc
            break
        if response is None:
            raise TemporaryToolGenerationError(
                "temporary_tool_generation_transport_terminal_state_missing",
                responsibility="framework",
                response_received=False,
                request_sha256=request_sha256,
            )
        try:
            content = response.choices[0].message.content
            if not isinstance(content, str) or not content:
                raise ValueError("temporary_tool_generation_content_missing")
            decoded = validate_structured_response_content(
                content,
                requirement=system_role_requirement("temporary_tool"),
                mode=self.response_mode,
            )
            draft = TemporaryToolGenerationDraft.model_validate_json(
                canonical_json_bytes(decoded).decode("utf-8"),
                strict=True,
            )
        except (AttributeError, IndexError, TypeError, ValueError, ValidationError) as exc:
            raise TemporaryToolGenerationError(
                "temporary_tool_generation_response_schema_invalid",
                responsibility="research",
                response_received=True,
                request_sha256=request_sha256,
            ) from exc
        assert_recovery_projection_safe(draft.source)
        if _SOURCE_SECRET_LITERAL.search(draft.source):
            raise TemporaryToolGenerationError(
                "temporary_tool_generated_source_secret_literal",
                responsibility="research",
                response_received=True,
                request_sha256=request_sha256,
            )
        return TemporaryToolGenerationResult(
            source=draft.source,
            generator_resource_id=envelope.generator_resource_id,
            generator_model_resource_id=envelope.generator_model_resource_id,
            generator_accounting_operation_id=operation_id,
            request_sha256=request_sha256,
            transport_attempts=attempts,
        )


__all__ = [
    "RegisteredTemporaryToolSource",
    "TEMPORARY_TOOL_GENERATION_PROMPT_SHA256",
    "TEMPORARY_TOOL_GENERATION_PROMPT_VERSION",
    "TemporaryToolGenerationDraft",
    "TemporaryToolGenerationError",
    "TemporaryToolGenerationInput",
    "TemporaryToolGenerationResult",
    "TemporaryToolGenerator",
    "TemporaryToolManager",
]
