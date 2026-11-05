"""Production adapters connecting recovery ports to sealed compiler/runtime facts."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping, Sequence

from .authorized_material import AuthorizedModelMaterialView
from .executable_plan import (
    CompilePurpose,
    CompilerPublicContext,
    PlanRevisionRef,
    RuntimeCapabilities,
    SealedPlanCompilationArtifact,
)
from .executors import ExecutionResult
from .execution_events import ExecutionPersistenceError, RunExecutionLedger
from .full_generation import FullGenerationExecutor
from .model_accounting import ModelPricingCatalog
from .model_transport import SyncModelTransportPort, require_sync_model_transport
from .model_response_contracts import system_role_requirement
from .pipeline_control import (
    canonical_json_bytes,
    canonical_sha256,
    subtask_revision_identity_sha256,
)
from .payload_provenance import ProductionModelPayloadGuard
from .plan_compiler import ExecutablePlanCompiler, PlanCompilerPayloadGuard
from .recovery_control import (
    CompletedStepCheckpoint,
    FailedGenerationRouteRecordV1,
    FullGenerationInputEnvelope,
    RecoveryControlError,
    RecoveryEventLedger,
    SideEffectEvidence,
    SideEffectStatus,
    StructuredExecutionFailureEvidence,
    TemporaryToolTransformDirective,
    executable_step_semantic_sha256,
    failed_generation_route_record,
)
from .recovery_controller import (
    FullGenerationPort,
    PlanCompilationPort,
    PlanExecutionPort,
    PreparedTemporaryToolExecution,
    TemporaryToolPort,
)
from .recovery_runtime import RecoveryExecutionSnapshot
from .resource_runtime import (
    ResourceCallResult,
    ResourceCallStatus,
    ResourceDefinition,
    ResourceFailure,
    resource_result_to_execution_result,
)
from .retrieval_runtime import FrozenCandidatePoolResult
from .schema import ArtifactHandle
from .temporary_tool import (
    RegisteredTemporaryToolSource,
    TemporaryToolGenerationError,
    TemporaryToolGenerator,
    TemporaryToolManager,
)


class SealedCompilerRecoveryPort(PlanCompilationPort):
    def __init__(
        self,
        *,
        run_id: str,
        compiler: ExecutablePlanCompiler,
        candidate_pool: FrozenCandidatePoolResult,
        public_context: CompilerPublicContext,
        resource_definitions: Mapping[str, ResourceDefinition],
        pricing_catalog: ModelPricingCatalog,
        runtime_capabilities: RuntimeCapabilities,
        payload_guard: ProductionModelPayloadGuard,
        temporary_tool_manager: TemporaryToolManager | None = None,
        resource_index: Mapping[str, Mapping[str, Any]] | None = None,
        original_user_query: str = "",
    ) -> None:
        self.run_id = run_id
        self.compiler = compiler
        self.candidate_pool = candidate_pool
        self.public_context = public_context
        self.resource_definitions = dict(resource_definitions)
        self.pricing_catalog = pricing_catalog
        self.runtime_capabilities = runtime_capabilities
        self.original_user_query = original_user_query
        self.payload_guard = payload_guard
        self.temporary_tool_manager = temporary_tool_manager
        self.resource_index = {
            str(key): dict(value)
            for key, value in dict(resource_index or {}).items()
        }
        self.payload_checks: dict[int, tuple[dict[str, Any], ...]] = {}
        self._prior_adaptation_failure_sha256s: list[str] = []
        self._prior_failed_generation_routes: list[
            FailedGenerationRouteRecordV1
        ] = []

    def _compiler_guard(
        self,
        *,
        revision: PlanRevisionRef,
        source_ids: Sequence[str],
    ) -> tuple[Callable[[Mapping[str, Any]], None], PlanCompilerPayloadGuard, int]:
        structural_guard = PlanCompilerPayloadGuard(self.public_context)
        production_guard = self.payload_guard.for_request(
            "plan_compiler"
            if revision.compile_purpose == CompilePurpose.INITIAL
            else "plan_adaptation",
            source_ids=tuple(source_ids),
            request_identity={
                "plan_revision": revision.plan_revision,
                "compile_purpose": revision.compile_purpose.value,
                "candidate_pool_sha256": (
                    self.candidate_pool.candidate_pool_snapshot.candidate_pool_sha256
                ),
            },
        )
        check_start = len(self.payload_guard.checks)

        def check(payload: Mapping[str, Any]) -> None:
            structural_guard(payload)
            production_guard(payload)

        return check, structural_guard, check_start

    def _capture_checks(
        self,
        *,
        plan_revision: int,
        structural_guard: PlanCompilerPayloadGuard,
        production_check_start: int,
    ) -> None:
        self.payload_checks[plan_revision] = (
            *structural_guard.checks,
            *tuple(
                dict(item)
                for item in self.payload_guard.checks[production_check_start:]
            ),
        )

    async def compile_initial(self) -> SealedPlanCompilationArtifact:
        revision = PlanRevisionRef(
            subtask_revision=self.candidate_pool.contract_projection.revision,
            plan_revision=0,
            compile_purpose=CompilePurpose.INITIAL,
        )
        guard, structural_guard, check_start = self._compiler_guard(
            revision=revision,
            source_ids=self.payload_guard.default_source_ids,
        )
        artifact = await asyncio.to_thread(
            self.compiler.compile,
            run_id=self.run_id,
            revision=revision,
            candidate_pool=self.candidate_pool,
            public_context=self.public_context,
            resource_definitions=self.resource_definitions,
            pricing_catalog=self.pricing_catalog,
            runtime_capabilities=self.runtime_capabilities,
            **({"original_user_query": self.original_user_query} if self.original_user_query else {}),
            payload_guard=guard,
        )
        self._capture_checks(
            plan_revision=0,
            structural_guard=structural_guard,
            production_check_start=check_start,
        )
        return artifact

    async def adapt(
        self,
        *,
        previous_artifact: SealedPlanCompilationArtifact,
        snapshot: RecoveryExecutionSnapshot,
        plan_revision: int,
    ) -> SealedPlanCompilationArtifact:
        if previous_artifact.executable_plan is None:
            raise RecoveryControlError("recovery_previous_plan_missing")
        current_failed_route = failed_generation_route_record(
            previous_plan=previous_artifact.executable_plan,
            failure_evidence=snapshot.failure_evidence,
        )
        prior_failed_routes = tuple(
            item
            for item in self._prior_failed_generation_routes
            if item.failure_evidence_sha256
            != snapshot.failure_evidence.evidence_sha256
        )
        revision = PlanRevisionRef(
            subtask_revision=self.candidate_pool.contract_projection.revision,
            plan_revision=plan_revision,
            compile_purpose=CompilePurpose.EXECUTION_ADAPTATION,
        )
        temporary_source: RegisteredTemporaryToolSource | None = None
        failed_resource_id = snapshot.failure_evidence.resource_id
        if self.temporary_tool_manager is not None and failed_resource_id:
            definition = self.resource_definitions.get(failed_resource_id)
            manifest = self.resource_index.get(failed_resource_id)
            if definition is not None and isinstance(manifest, Mapping):
                try:
                    temporary_source = await asyncio.to_thread(
                        self.temporary_tool_manager.register_source_bundle,
                        failed_resource_id=failed_resource_id,
                        candidate_pool_sha256=(
                            previous_artifact.candidate_pool_sha256
                        ),
                        selected_resource_ids=(
                            previous_artifact.executable_plan.selected_resource_ids
                        ),
                        definition=definition,
                        manifest=manifest,
                    )
                except RecoveryControlError:
                    # Ineligibility is research evidence, not a framework fault.
                    # The Compiler may still recompose over the frozen pool.
                    temporary_source = None
        parent_ids = self.payload_guard.default_source_ids
        previous_source_id = (
            f"recovery_previous_plan:{previous_artifact.artifact_sha256}"
        )
        self.payload_guard.register_source(
            previous_source_id,
            origin="validated_plan",
            material=previous_artifact.executable_plan.model_dump(mode="json"),
            parent_source_ids=parent_ids,
            producer={
                "plan_revision": previous_artifact.plan_revision.plan_revision,
                "plan_artifact_sha256": previous_artifact.artifact_sha256,
            },
        )
        failure_source_id = (
            f"recovery_failure:{snapshot.failure_evidence.evidence_sha256}"
        )
        self.payload_guard.register_source(
            failure_source_id,
            origin="current_run_step_output",
            material=snapshot.failure_evidence.model_dump(mode="json"),
            parent_source_ids=parent_ids,
            producer={
                "step_id": snapshot.failure_evidence.step_id or "preflight",
                "material_kind": "structured_recovery_failure",
            },
        )
        source_ids = [*parent_ids, previous_source_id, failure_source_id]
        for route in prior_failed_routes:
            route_source_id = (
                f"recovery_failed_generation_route:{route.record_sha256}"
            )
            self.payload_guard.register_source(
                route_source_id,
                origin="current_run_step_output",
                material=route.model_dump(mode="json"),
                parent_source_ids=parent_ids,
                producer={
                    "resource_id": route.resource_id,
                    "material_kind": "prior_failed_generation_route",
                    "failure_evidence_sha256": route.failure_evidence_sha256,
                },
            )
            source_ids.append(route_source_id)
        for checkpoint in snapshot.checkpoints:
            source_id = f"recovery_checkpoint:{checkpoint.checkpoint_sha256}"
            self.payload_guard.register_source(
                source_id,
                origin="current_run_step_output",
                material=checkpoint.model_dump(mode="json"),
                parent_source_ids=parent_ids,
                producer={
                    "step_id": checkpoint.step_id,
                    "resource_id": checkpoint.resource_id,
                    "material_kind": "completed_step_checkpoint",
                },
            )
            source_ids.append(source_id)
        lineage_source_id = f"recovery_lineage:{snapshot.lineage.lineage_sha256}"
        self.payload_guard.register_source(
            lineage_source_id,
            origin="static_framework",
            material=snapshot.lineage.model_dump(mode="json"),
            parent_source_ids=parent_ids,
            producer={"material_kind": "recovery_lineage"},
        )
        source_ids.append(lineage_source_id)
        if temporary_source is not None:
            temporary_source_id = (
                "temporary_tool_descriptor:"
                + temporary_source.bundle.source_bundle_sha256
            )
            self.payload_guard.register_source(
                temporary_source_id,
                origin="static_framework",
                material=temporary_source.bundle.model_dump(mode="json"),
                parent_source_ids=parent_ids,
                producer={
                    "material_kind": "temporary_tool_source_descriptor",
                    "source_bundle_sha256": (
                        temporary_source.bundle.source_bundle_sha256
                    ),
                },
            )
            source_ids.append(temporary_source_id)
        if snapshot.diagnostic_excerpt:
            diagnostic_source_id = (
                f"recovery_diagnostic:{snapshot.failure_evidence.evidence_sha256}:"
                + canonical_sha256(snapshot.diagnostic_excerpt)
            )
            self.payload_guard.register_source(
                diagnostic_source_id,
                origin="current_run_step_output",
                material=snapshot.diagnostic_excerpt,
                parent_source_ids=(failure_source_id,),
                producer={
                    "step_id": snapshot.failure_evidence.step_id or "preflight",
                    "material_kind": "sanitized_recovery_diagnostic",
                },
            )
            source_ids.append(diagnostic_source_id)
        guard, structural_guard, check_start = self._compiler_guard(
            revision=revision,
            source_ids=source_ids,
        )
        artifact = await asyncio.to_thread(
            self.compiler.adapt,
            run_id=self.run_id,
            revision=revision,
            previous_artifact=previous_artifact,
            failure_evidence=snapshot.failure_evidence,
            checkpoints=snapshot.checkpoints,
            recovery_lineage=snapshot.lineage,
            candidate_pool=self.candidate_pool,
            public_context=self.public_context,
            resource_definitions=self.resource_definitions,
            pricing_catalog=self.pricing_catalog,
            runtime_capabilities=self.runtime_capabilities,
            **({"original_user_query": self.original_user_query} if self.original_user_query else {}),
            prior_adaptation_failure_sha256s=tuple(
                self._prior_adaptation_failure_sha256s
            ),
            prior_failed_generation_routes=prior_failed_routes,
            diagnostic_excerpt=snapshot.diagnostic_excerpt,
            temporary_tool_source=(
                temporary_source.bundle if temporary_source is not None else None
            ),
            payload_guard=guard,
        )
        self._capture_checks(
            plan_revision=plan_revision,
            structural_guard=structural_guard,
            production_check_start=check_start,
        )
        if current_failed_route is not None and all(
            item.record_sha256 != current_failed_route.record_sha256
            for item in self._prior_failed_generation_routes
        ):
            self._prior_failed_generation_routes.append(current_failed_route)
            self._prior_failed_generation_routes = (
                self._prior_failed_generation_routes[-2:]
            )
        if (
            artifact.status != "success"
            and artifact.failure is not None
            and artifact.failure.responsibility == "research"
        ):
            self._prior_adaptation_failure_sha256s.append(
                artifact.failure.message_sha256
            )
        else:
            self._prior_adaptation_failure_sha256s.clear()
        return artifact


class CallableSealedExecutionPort(PlanExecutionPort):
    def __init__(
        self,
        callback: Callable[
            [
                SealedPlanCompilationArtifact,
                Sequence[CompletedStepCheckpoint],
                Mapping[str, ExecutionResult],
            ],
            Awaitable[ExecutionResult],
        ],
    ) -> None:
        self.callback = callback

    async def execute(
        self,
        *,
        artifact: SealedPlanCompilationArtifact,
        checkpoints: Sequence[CompletedStepCheckpoint] = (),
        checkpoint_results: Mapping[str, ExecutionResult] | None = None,
    ) -> ExecutionResult:
        return await self.callback(
            artifact,
            tuple(checkpoints),
            dict(checkpoint_results or {}),
        )


class SystemFullGenerationRecoveryPort(FullGenerationPort):
    def __init__(
        self,
        *,
        executor: FullGenerationExecutor,
        revision: Any,
        public_context: CompilerPublicContext,
        candidate_pool_sha256: str,
        contract_projection: Mapping[str, Any],
        payload_guard: ProductionModelPayloadGuard,
        diagnostic_max_bytes: int,
        material_view_factory: Callable[
            [Sequence[CompletedStepCheckpoint]], AuthorizedModelMaterialView
        ],
    ) -> None:
        self.executor = executor
        self.revision = revision
        self.public_context = public_context
        self.candidate_pool_sha256 = candidate_pool_sha256
        self.contract_projection = dict(contract_projection)
        self.payload_guard = payload_guard
        self.diagnostic_max_bytes = int(diagnostic_max_bytes)
        self.material_view_factory = material_view_factory

    async def generate(
        self,
        *,
        compiler_failure_hashes: Sequence[str],
        execution_failures: Sequence[StructuredExecutionFailureEvidence],
        diagnostic_excerpts: Sequence[str],
        checkpoints: Sequence[CompletedStepCheckpoint],
    ) -> ResourceCallResult:
        material_view = self.material_view_factory(tuple(checkpoints))
        if material_view.revision != self.revision:
            raise RecoveryControlError("full_generation_material_revision_mismatch")
        failure_hashes = tuple(
            dict.fromkeys(
                [
                    *compiler_failure_hashes,
                    *(item.evidence_sha256 for item in execution_failures),
                ]
            )
        )
        parent_ids = self.payload_guard.default_source_ids
        source_ids = list(parent_ids)
        for material in material_view.materials:
            registry_origin = (
                "public_case"
                if material.origin == "public_input"
                else "current_run_step_output"
            )
            self.payload_guard.register_source(
                material.source_id,
                origin=registry_origin,
                material=material.model_dump(mode="json"),
                parent_source_ids=() if registry_origin == "public_case" else parent_ids,
                producer={
                    "material_kind": "authorized_model_material",
                    "origin_kind": material.origin,
                    "material_sha256": material.material_sha256,
                    "revision_sha256": subtask_revision_identity_sha256(
                        self.revision
                    ),
                },
            )
            source_ids.append(material.source_id)
        for index, item in enumerate(compiler_failure_hashes):
            source_id = f"compiler_failure:{index}:{item}"
            self.payload_guard.register_source(
                source_id,
                origin="static_framework",
                material={"compiler_failure_sha256": item},
                parent_source_ids=parent_ids,
                producer={"material_kind": "compiler_failure_hash"},
            )
            source_ids.append(source_id)
        for index, item in enumerate(execution_failures):
            source_id = f"recovery_failure:{index}:{item.evidence_sha256}"
            self.payload_guard.register_source(
                source_id,
                origin="static_framework",
                material=item.model_dump(mode="json"),
                parent_source_ids=parent_ids,
                producer={"material_kind": "structured_recovery_failure"},
            )
            source_ids.append(source_id)
        for index, item in enumerate(checkpoints):
            source_id = f"recovery_checkpoint:{index}:{item.checkpoint_sha256}"
            self.payload_guard.register_source(
                source_id,
                origin="current_run_step_output",
                material=item.model_dump(mode="json"),
                parent_source_ids=parent_ids,
                producer={
                    "step_id": item.step_id,
                    "resource_id": item.resource_id,
                    "material_kind": "completed_step_checkpoint",
                },
            )
            source_ids.append(source_id)
        diagnostic = "\n".join(str(item) for item in diagnostic_excerpts if item)
        raw = diagnostic.encode("utf-8")[: self.diagnostic_max_bytes]
        while raw:
            try:
                diagnostic = raw.decode("utf-8")
                break
            except UnicodeDecodeError:
                raw = raw[:-1]
        if not raw:
            diagnostic = ""
        if diagnostic:
            diagnostic_source_id = "recovery_diagnostic:" + canonical_sha256(
                diagnostic
            )
            diagnostic_parents = tuple(source_ids) or parent_ids
            self.payload_guard.register_source(
                diagnostic_source_id,
                origin="current_run_step_output",
                material=diagnostic,
                parent_source_ids=diagnostic_parents,
                producer={"material_kind": "sanitized_recovery_diagnostic"},
            )
            source_ids.append(diagnostic_source_id)
        envelope = FullGenerationInputEnvelope(
            revision=self.revision,
            contract_projection=self.contract_projection,
            public_context=self.public_context,
            authorized_materials=material_view,
            checkpoints=tuple(checkpoints),
            failure_evidence_sha256=failure_hashes,
            candidate_pool_sha256=self.candidate_pool_sha256,
            system_policy=self.executor.system_policy,
            diagnostic_excerpt=diagnostic,
        )
        bound_guard = self.payload_guard.for_request(
            "full_generation",
            source_ids=tuple(source_ids),
            request_identity={
                "subtask_id": self.revision.subtask_id,
                "subtask_revision_sha256": subtask_revision_identity_sha256(
                    self.revision
                ),
                "candidate_pool_sha256": self.candidate_pool_sha256,
                "full_generation_input_sha256": envelope.input_sha256,
                "authorized_material_view_sha256": material_view.view_sha256,
            },
        )
        return await asyncio.to_thread(
            self.executor.execute,
            envelope,
            payload_guard=bound_guard,
        )


def _temporary_failure_result(
    *,
    directive: TemporaryToolTransformDirective,
    responsibility: str,
    failure_stage: str,
    failure_code: str,
    response_received: bool,
) -> ExecutionResult:
    normalized = (
        responsibility
        if responsibility in {"framework", "infrastructure", "research", "budget"}
        else "framework"
    )
    return ExecutionResult(
        is_success=False,
        output_data="",
        error_log=failure_code,
        cost_metric={
            "failure_type": failure_code,
            "failure_layer": normalized,
            "failure": {
                "responsibility": normalized,
                "failure_stage": failure_stage,
                "failure_code": failure_code,
                "exception_type": "",
                "retryable": False,
                "response_received": bool(response_received),
                "message_sha256": canonical_sha256(
                    {
                        "failure_stage": failure_stage,
                        "failure_code": failure_code,
                    }
                ),
            },
            "application_step_trace": [
                {
                    "step_id": directive.generator_step_id,
                    "status": "failed",
                    "failure_type": failure_code,
                    "failure_layer": normalized,
                }
            ],
            "application_step_outputs": {},
        },
    )


class GenericTemporaryToolRecoveryPort(TemporaryToolPort):
    """Prepare one audited run-local source transformation without pool mutation."""

    def __init__(
        self,
        *,
        manager: TemporaryToolManager,
        generator_transport: SyncModelTransportPort,
        cost_ledger: Any,
        pricing_catalog: ModelPricingCatalog,
        resource_definitions: Mapping[str, ResourceDefinition],
        resource_index: Mapping[str, Mapping[str, Any]],
        payload_guard: ProductionModelPayloadGuard,
        execution_ledger: RunExecutionLedger,
        recovery_ledger: RecoveryEventLedger,
        contract_projection: Mapping[str, Any],
        sandbox_scope_sha256: str,
        register_generated_artifact: Callable[
            [str, str, Path, ArtifactHandle], None
        ],
        candidate_pool: FrozenCandidatePoolResult | None = None,
    ) -> None:
        self.manager = manager
        self.generator_transport = require_sync_model_transport(generator_transport)
        self.cost_ledger = cost_ledger
        self.pricing_catalog = pricing_catalog
        self.resource_definitions = dict(resource_definitions)
        self.resource_index = {
            str(key): dict(value) for key, value in resource_index.items()
        }
        self.payload_guard = payload_guard
        self.execution_ledger = execution_ledger
        self.recovery_ledger = recovery_ledger
        self.contract_projection = dict(contract_projection)
        self.sandbox_scope_sha256 = str(sandbox_scope_sha256)
        self.register_generated_artifact = register_generated_artifact
        self.candidate_pool = candidate_pool

    @staticmethod
    def _directive(
        artifact: SealedPlanCompilationArtifact,
    ) -> TemporaryToolTransformDirective | None:
        validation = artifact.validation_audit
        adaptation = (
            validation.get("adaptation") if isinstance(validation, Mapping) else None
        )
        payload = (
            adaptation.get("temporary_tool_transform")
            if isinstance(adaptation, Mapping)
            else None
        )
        if not isinstance(payload, Mapping):
            return None
        return TemporaryToolTransformDirective.model_validate(payload)

    @staticmethod
    def _agent_instruction(manifest: Mapping[str, Any]) -> str:
        capability = manifest.get("capability")
        if not isinstance(capability, Mapping):
            return ""
        public = {
            "core_primitives": capability.get("core_primitives") or (),
            "problem_space": capability.get("problem_space") or "",
        }
        return canonical_json_bytes(public).decode("utf-8")

    async def prepare(
        self,
        *,
        artifact: SealedPlanCompilationArtifact,
        snapshot: RecoveryExecutionSnapshot,
    ) -> PreparedTemporaryToolExecution | ExecutionResult | None:
        if artifact.status != "success" or artifact.executable_plan is None:
            return None
        directive = self._directive(artifact)
        if directive is None:
            return None
        plan = artifact.executable_plan
        by_step = {item.step_id: item for item in plan.steps}
        generator_step = by_step.get(directive.generator_step_id)
        runner_step = by_step.get(directive.runner_step_id)
        if generator_step is None or runner_step is None:
            return None
        original_definition = self.resource_definitions.get(
            directive.original_resource_id
        )
        generator_definition = self.resource_definitions.get(
            generator_step.resource_id
        )
        runner_definition = self.resource_definitions.get(runner_step.resource_id)
        original_manifest = self.resource_index.get(directive.original_resource_id)
        generator_manifest = self.resource_index.get(generator_step.resource_id) or {}
        if (
            original_definition is None
            or generator_definition is None
            or runner_definition is None
            or not isinstance(original_manifest, Mapping)
        ):
            return None
        if snapshot.failure_evidence.resource_id != directive.original_resource_id:
            return None
        try:
            registered = await asyncio.to_thread(
                self.manager.register_source_bundle,
                failed_resource_id=directive.original_resource_id,
                candidate_pool_sha256=plan.candidate_pool_sha256,
                selected_resource_ids=(directive.original_resource_id,),
                definition=original_definition,
                manifest=original_manifest,
            )
            generation_material = self.manager.generation_material(registered)
        except RecoveryControlError:
            return None

        generator_model_resource_id = generator_step.resource_id
        agent_instruction = ""
        if generator_step.resource_type == "Agent":
            generator_model_resource_id = str(
                generator_step.agent_base_model_resource_id or ""
            )
            if not generator_model_resource_id:
                return None
            agent_instruction = self._agent_instruction(generator_manifest)
            if not agent_instruction:
                return None
        try:
            model_price = self.pricing_catalog.resolve(
                resource_id=generator_model_resource_id
            )
        except Exception:
            return _temporary_failure_result(
                directive=directive,
                responsibility="framework",
                failure_stage="temporary_tool_pricing",
                failure_code="temporary_tool_generator_pricing_unresolved",
                response_received=False,
            )
        selected_mode = "native_strict_schema"
        if self.candidate_pool is not None:
            if (
                self.candidate_pool.candidate_pool_snapshot.candidate_pool_sha256
                != plan.candidate_pool_sha256
            ):
                return _temporary_failure_result(
                    directive=directive,
                    responsibility="framework",
                    failure_stage="temporary_tool_format_contract",
                    failure_code="temporary_tool_candidate_pool_identity_mismatch",
                    response_received=False,
                )
            requirement = system_role_requirement("temporary_tool")
            evidence = next(
                (
                    item
                    for item in self.candidate_pool.capability_probe_evidence
                    if item.resource_id == generator_model_resource_id
                    and item.requirement_sha256 == requirement.requirement_sha256
                ),
                None,
            )
            if evidence is None or not evidence.is_admissible:
                return _temporary_failure_result(
                    directive=directive,
                    responsibility="framework",
                    failure_stage="temporary_tool_format_contract",
                    failure_code="temporary_tool_generator_format_evidence_missing",
                    response_received=False,
                )
            selected_mode = str(
                getattr(evidence, "selected_enforcement_mode", None)
                or "native_strict_schema"
            )
            if selected_mode not in {
                "native_strict_schema",
                "json_object_local_validator",
            }:
                return _temporary_failure_result(
                    directive=directive,
                    responsibility="framework",
                    failure_stage="temporary_tool_format_contract",
                    failure_code="temporary_tool_generator_format_mode_invalid",
                    response_received=False,
                )
        generator = TemporaryToolGenerator(
            transport=self.generator_transport,
            cost_ledger=self.cost_ledger,
            pricing_catalog=self.pricing_catalog,
            response_mode=selected_mode,
            temperature=0.0,
            max_tokens=8192,
        )
        envelope = generator.build_input(
            revision=plan.plan_revision.subtask_revision,
            plan_revision=plan.plan_revision.plan_revision,
            registered=registered,
            generation_material=generation_material,
            generator_definition=generator_definition,
            generator_model_resource_id=generator_model_resource_id,
            generator_model_api_id=model_price.api_model_id,
            runner_resource_id=runner_step.resource_id,
            failure_evidence_sha256=snapshot.failure_evidence.evidence_sha256,
            contract_projection=self.contract_projection,
            diagnostic_excerpt=snapshot.diagnostic_excerpt,
        )
        source_id = f"temporary_tool_source:{registered.bundle.source_bundle_sha256}"
        self.payload_guard.register_source(
            source_id,
            origin="static_framework",
            material=generation_material,
            parent_source_ids=self.payload_guard.default_source_ids,
            producer={
                "material_kind": "audited_temporary_tool_source",
                "source_bundle_sha256": registered.bundle.source_bundle_sha256,
            },
        )
        bound_guard = self.payload_guard.for_request(
            "temporary_tool_generation",
            source_ids=(*self.payload_guard.default_source_ids, source_id),
            request_identity={
                "candidate_pool_sha256": plan.candidate_pool_sha256,
                "plan_revision": plan.plan_revision.plan_revision,
                "generation_input_sha256": envelope.input_sha256,
            },
        )
        request_sha256 = generator.request_sha256(
            envelope=envelope,
            generation_material=generation_material,
            agent_instruction=agent_instruction,
        )
        call_id = f"temporary-tool-generator:{envelope.input_sha256}"
        try:
            call_handle = self.execution_ledger.start_call(
                call_id=call_id,
                resource_id=generator_step.resource_id,
                resource_type=generator_step.resource_type,
                entrypoint_id="invoke",
                runtime_kind="temporary_tool_generation",
                graph_revision=plan.plan_revision.subtask_revision.graph_revision,
                subtask_id=plan.plan_revision.subtask_revision.subtask_id,
                subtask_revision=plan.plan_revision.subtask_revision.subtask_revision,
                step_id=generator_step.step_id,
                attempt=plan.plan_revision.plan_revision,
                request_sha256=request_sha256,
                candidate_pool_sha256=plan.candidate_pool_sha256,
                plan_sha256=plan.plan_sha256,
                sandbox_scope_sha256=self.sandbox_scope_sha256,
            )
        except ExecutionPersistenceError as exc:
            raise RecoveryControlError("temporary_tool_execution_start_failed") from exc
        try:
            generation = await asyncio.to_thread(
                generator.generate,
                envelope=envelope,
                generation_material=generation_material,
                generator_definition=generator_definition,
                payload_guard=bound_guard,
                agent_instruction=agent_instruction,
            )
        except TemporaryToolGenerationError as exc:
            failure_result = ResourceCallResult(
                call_id=call_id,
                resource_id=generator_step.resource_id,
                entrypoint_id="invoke",
                status=ResourceCallStatus(f"{exc.responsibility}_failure"),
                failure=ResourceFailure.create(
                    responsibility=exc.responsibility,
                    failure_stage="temporary_tool_generation",
                    failure_code=exc.code,
                    retryable=False,
                    response_received=exc.response_received,
                ),
                output_contract_status="failed",
                started_event_id=call_handle.started_event_id,
            )
            terminal = self.execution_ledger.finish_call(
                call_handle,
                status=failure_result.status.value,
                result_sha256=failure_result.result_sha256,
                output_contract_status="failed",
                responsibility=exc.responsibility,
                failure_stage="temporary_tool_generation",
                failure_code=exc.code,
                execution_audit_sha256=canonical_sha256({}),
            )
            projected = failure_result.model_copy(
                update={"terminal_event_id": terminal["event_id"]}
            )
            return resource_result_to_execution_result(projected)
        try:
            temporary_artifact = await asyncio.to_thread(
                self.manager.finalize_generated_source,
                registered=registered,
                generated_source=generation.source,
                generator_resource_id=generator_step.resource_id,
                generator_accounting_operation_id=(
                    generation.generator_accounting_operation_id
                ),
                runner_resource_id=runner_step.resource_id,
                candidate_resource_definitions=self.resource_definitions,
                plan_revision=plan.plan_revision.plan_revision,
            )
        except RecoveryControlError:
            failure = ResourceCallResult(
                call_id=call_id,
                resource_id=generator_step.resource_id,
                entrypoint_id="invoke",
                status=ResourceCallStatus.RESEARCH_FAILURE,
                failure=ResourceFailure.create(
                    responsibility="research",
                    failure_stage="temporary_tool_materialization",
                    failure_code="temporary_tool_generated_source_rejected",
                    response_received=True,
                ),
                usage_reference=generation.generator_accounting_operation_id,
                output_contract_status="failed",
                started_event_id=call_handle.started_event_id,
            )
            terminal = self.execution_ledger.finish_call(
                call_handle,
                status=failure.status.value,
                result_sha256=failure.result_sha256,
                output_contract_status="failed",
                responsibility="research",
                failure_stage="temporary_tool_materialization",
                failure_code="temporary_tool_generated_source_rejected",
                usage_reference=generation.generator_accounting_operation_id,
                execution_audit_sha256=canonical_sha256({}),
            )
            return resource_result_to_execution_result(
                failure.model_copy(update={"terminal_event_id": terminal["event_id"]})
            )

        generated_path = (
            self.manager.recovery_root
            / f"plan_revision_{plan.plan_revision.plan_revision}"
            / "generated_tool.py"
        ).resolve(strict=True)
        handle = ArtifactHandle(
            handle_id=(
                f"{plan.plan_revision.subtask_revision.subtask_id}:"
                f"{generator_step.step_id}:temporary_tool"
            ),
            kind="step_artifact",
            producer_task=plan.plan_revision.subtask_revision.subtask_id,
            producer_step=generator_step.step_id,
            logical_path=temporary_artifact.runtime_locator,
            host_path=str(generated_path),
            tool_path=temporary_artifact.runtime_locator,
            artifact_type="code",
            validation_status="checked",
            current_run=True,
        )
        result = ResourceCallResult(
            call_id=call_id,
            resource_id=generator_step.resource_id,
            entrypoint_id="invoke",
            status=ResourceCallStatus.SUCCESS,
            canonical_value=temporary_artifact.runtime_locator,
            presentation=temporary_artifact.runtime_locator,
            artifacts=(handle,),
            usage_reference=generation.generator_accounting_operation_id,
            execution_audit={
                "temporary_tool_artifact_sha256": temporary_artifact.artifact_sha256,
                "source_bundle_sha256": registered.bundle.source_bundle_sha256,
                "request_sha256": generation.request_sha256,
                "transport_attempts": generation.transport_attempts,
            },
            provenance={
                "source_bundle_sha256": registered.bundle.source_bundle_sha256,
                "generated_source_sha256": temporary_artifact.generated_source_sha256,
            },
            output_contract_status="checked",
            started_event_id=call_handle.started_event_id,
        )
        self.execution_ledger.register_artifact(
            call_handle,
            artifact_handle_id=handle.handle_id,
            artifact_type=handle.artifact_type,
            logical_path=handle.tool_path,
            artifact_sha256=temporary_artifact.generated_source_sha256,
        )
        terminal = self.execution_ledger.finish_call(
            call_handle,
            status=result.status.value,
            result_sha256=result.result_sha256,
            output_contract_status=result.output_contract_status,
            usage_reference=result.usage_reference,
            execution_audit_sha256=canonical_sha256(result.execution_audit),
        )
        result = result.model_copy(update={"terminal_event_id": terminal["event_id"]})
        self.register_generated_artifact(
            generator_step.step_id,
            generator_step.output_key,
            generated_path,
            handle,
        )
        subtask_locator = subtask_revision_identity_sha256(
            plan.plan_revision.subtask_revision
        )[:32]
        self.recovery_ledger.persist_artifact(
            (
                "temporary_tool_"
                f"{subtask_locator}_"
                f"{plan.plan_revision.plan_revision}.json"
            ),
            temporary_artifact.model_dump(mode="json"),
        )
        self.recovery_ledger.append_event(
            "temporary_tool_source_registered",
            {
                "plan_revision": plan.plan_revision.plan_revision,
                "source_bundle_sha256": registered.bundle.source_bundle_sha256,
                "temporary_tool_artifact_sha256": temporary_artifact.artifact_sha256,
                "generator_accounting_operation_id": (
                    generation.generator_accounting_operation_id
                ),
            },
        )
        execution_result = resource_result_to_execution_result(result)
        checkpoint = CompletedStepCheckpoint(
            step_id=generator_step.step_id,
            step_semantic_sha256=executable_step_semantic_sha256(generator_step),
            resource_id=generator_step.resource_id,
            entrypoint_id=generator_step.entrypoint_id,
            result_sha256=result.result_sha256,
            resource_call_id=result.call_id,
            artifact_handle_ids=(handle.handle_id,),
            artifact_hashes=(temporary_artifact.generated_source_sha256,),
            provenance_source_ids=(source_id,),
            started_event_id=str(result.started_event_id),
            terminal_event_id=str(result.terminal_event_id),
            side_effect_evidence=SideEffectEvidence(
                status=SideEffectStatus.UNKNOWN_EXTERNAL,
                dispatched=True,
                network_required=True,
                artifact_hashes=(temporary_artifact.generated_source_sha256,),
            ),
        )
        return PreparedTemporaryToolExecution(
            checkpoint=checkpoint,
            checkpoint_result=execution_result,
            artifact_sha256=temporary_artifact.artifact_sha256,
        )


__all__ = [
    "CallableSealedExecutionPort",
    "GenericTemporaryToolRecoveryPort",
    "SealedCompilerRecoveryPort",
    "SystemFullGenerationRecoveryPort",
]
