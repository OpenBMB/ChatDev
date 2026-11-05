"""Deterministic Planner contract projection and validation."""

from __future__ import annotations

import copy
from dataclasses import dataclass
import inspect
import json
from pathlib import PurePosixPath
from typing import Any, Dict, List, Mapping, Sequence, TypedDict, cast

from .pipeline_control import canonical_sha256
from .schema import (
    ArtifactType,
    DagEdgeContractV1,
    DependencyInputContractV1,
    PlannerOutput,
    ProducedFileContract,
    Subtask,
    SubtaskOutputContract,
    TaskStage,
)


_ARTIFACT_ALIASES = {
    "python": "code",
    "py": "code",
    "script": "code",
    "source": "code",
    "source_code": "code",
    "report": "markdown",
    "document": "markdown",
    "doc": "markdown",
    "structured_analysis": "markdown",
    "analysis": "markdown",
    "text": "plaintext",
    "plain_text": "plaintext",
    "json_object": "json",
    "json_schema": "json",
    "csv_file": "csv",
    "folder": "directory",
    "archive": "bundle",
}

_EXTENSION_ARTIFACT = {
    ".json": "json",
    ".jsonl": "json",
    ".ndjson": "json",
    ".csv": "csv",
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "plaintext",
    ".py": "code",
    ".js": "code",
    ".ts": "code",
    ".java": "code",
    ".cpp": "code",
    ".go": "code",
    ".rs": "code",
    # Coq/Lean/OCaml and similar source files are code artifacts even when
    # they are not Python.  The produced-file path is authoritative for the
    # physical extension; this prevents a model-default `.py` from leaking
    # into a `.v` source contract.
    ".v": "code",
    ".vok": "file",
    ".vo": "file",
    ".ml": "code",
    ".mli": "code",
    ".hs": "code",
    ".tex": "code",
}

_DEFAULT_EXTENSION = {
    "code": ".py",
    "json": ".json",
    "csv": ".csv",
    "markdown": ".md",
    "plaintext": ".txt",
    "file": "",
    "directory": "",
    "bundle": "",
}


class PlannerContractConflict(ValueError):
    """A model-owned Planner contract violates a shared invariant."""

    failure_code = "planner_contract_conflict"

    def __init__(
        self,
        paths: Sequence[str],
        invariant_ids: Sequence[str],
        *,
        failure_code: str | None = None,
    ) -> None:
        if failure_code:
            self.failure_code = str(failure_code)
        self.paths = tuple(dict.fromkeys(str(item) for item in paths if str(item)))
        self.invariant_ids = tuple(
            dict.fromkeys(str(item) for item in invariant_ids if str(item))
        )
        super().__init__(self.failure_code)


class PlannerGenerationError(RuntimeError):
    """Stable terminal error for Planner protocol and contract failures."""

    def __init__(
        self,
        failure_code: str,
        *,
        responsibility: str = "research",
        response_received: bool = True,
        retryable: bool = False,
        cause: Exception | None = None,
        paths: Sequence[str] = (),
        invariant_ids: Sequence[str] = (),
        response_sha256: str | None = None,
        request_sha256: str | None = None,
        cost_status: str = "known",
        canonical_contract_sha256: str | None = None,
        retry_count: int = 0,
    ) -> None:
        self.failure_code = str(failure_code)
        self.failure_stage = "planner_generation"
        self.responsibility = str(responsibility)
        self.response_received = bool(response_received)
        self.retryable = bool(retryable)
        self.cause = cause
        self.paths = tuple(dict.fromkeys(str(item) for item in paths if str(item)))
        self.invariant_ids = tuple(
            dict.fromkeys(str(item) for item in invariant_ids if str(item))
        )
        self.response_sha256 = response_sha256
        self.request_sha256 = request_sha256
        self.cost_status = str(cost_status)
        self.canonical_contract_sha256 = canonical_contract_sha256
        self.retry_count = max(0, int(retry_count))
        super().__init__(self.failure_code)


class PlannerContractAuditV1(TypedDict):
    protocol: str
    projection_version: str
    planner_response_sha256: str | None
    canonical_contract_sha256: str | None
    model_owned_semantics_sha256: str | None
    semantic_round_trip: bool
    warning_codes: List[str]
    conflict_paths: List[str]
    invariant_ids: List[str]
    edge_contracts_sha256: str | None
    audit_sha256: str


@dataclass(frozen=True)
class PlannerContractProjection:
    """Canonical Planner output plus a sealed, host-free audit projection."""

    output: PlannerOutput
    canonical_contract_sha256: str
    edge_contracts: tuple[DagEdgeContractV1, ...]
    edge_contracts_sha256: str
    audit: PlannerContractAuditV1


PlannerContractProjectionV1 = PlannerContractProjection


def canonical_artifact_type(value: Any) -> str:
    raw = str(getattr(value, "value", value) or "").strip().lower()
    normalized = raw.replace("-", "_").replace(" ", "_")
    return _ARTIFACT_ALIASES.get(normalized, normalized)


def default_extension(artifact_type: Any) -> str:
    return _DEFAULT_EXTENSION.get(canonical_artifact_type(artifact_type), ".txt")


def _known_extension(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    lowered = raw.lower()
    dotted = lowered if lowered.startswith(".") else f".{lowered}"
    # Known extensions have one canonical spelling.  Unknown/custom values
    # remain exactly as supplied so projection cannot rewrite model semantics.
    return dotted if dotted in _EXTENSION_ARTIFACT else raw


def _known_extension_artifact(value: Any) -> str | None:
    return _EXTENSION_ARTIFACT.get(_known_extension(value))


def _produced_file_extensions(contract: SubtaskOutputContract) -> tuple[str, ...]:
    """Return distinct physical suffixes declared by required output files."""

    extensions: list[str] = []
    for item in contract.produced_files:
        if not item.required:
            continue
        path = str(item.path_hint or "").replace("\\", "/")
        suffix = PurePosixPath(path).suffix.lower()
        if not suffix or suffix == ".":
            continue
        if suffix not in extensions:
            extensions.append(suffix)
    return tuple(extensions)


def _model_owned_semantics(
    output: PlannerOutput,
    *,
    baseline: PlannerOutput | None = None,
) -> Dict[str, Any]:
    values: List[Dict[str, Any]] = []
    baseline_subtasks = list(baseline.subtasks) if baseline is not None else list(output.subtasks)
    for index, subtask in enumerate(output.subtasks):
        payload = cast(Dict[str, Any], subtask.model_dump(mode="json"))
        payload.pop("incoming_edge_contracts", None)
        primary_type = canonical_artifact_type(payload.get("artifact_type"))
        payload["artifact_type"] = primary_type
        contract = payload.get("output_contract")
        if isinstance(contract, dict):
            contract["artifact_type"] = canonical_artifact_type(contract.get("artifact_type"))
            if primary_type in {"bundle", "directory"}:
                contract.pop("output_extension", None)
            if baseline is not None and index < len(baseline_subtasks):
                baseline_contract = baseline_subtasks[index].output_contract
                if baseline_contract is None:
                    payload["output_contract"] = None
                elif not str(baseline_contract.output_extension or "").strip():
                    contract.pop("output_extension", None)
        baseline_subtask = baseline_subtasks[index] if index < len(baseline_subtasks) else None
        if baseline_subtask is not None and baseline_subtask.output_contract is None:
            payload["output_contract"] = None
        elif (
            baseline_subtask is not None
            and isinstance(contract, dict)
            and baseline_subtask.output_contract is not None
            and not str(baseline_subtask.output_contract.output_extension or "").strip()
        ):
            contract.pop("output_extension", None)
        if baseline_subtask is not None and not str(baseline_subtask.output_extension or "").strip():
            payload.pop("output_extension", None)
        if primary_type in {"bundle", "directory"}:
            payload.pop("output_extension", None)
        if baseline_subtask is not None and baseline_subtask.task_stage is None:
            payload.pop("task_stage", None)
        values.append(payload)
    return {"subtasks": values}


def _json_object(value: str) -> Dict[str, Any]:
    decoded = json.loads(value)
    if not isinstance(decoded, dict):
        raise ValueError("edge_interface_contract_not_object")
    return cast(Dict[str, Any], decoded)


def _mapping_contains(actual: Any, required: Any) -> bool:
    """Return whether an explicit producer interface satisfies a required subset."""

    if (
        isinstance(actual, Mapping)
        and isinstance(required, Mapping)
        and "capabilities" in required
    ):
        actual_mapping = cast(Mapping[str, Any], actual)
        required_mapping = cast(Mapping[str, Any], required)
        actual_items = actual_mapping.get("capabilities")
        required_items = required_mapping.get("capabilities")
        if not isinstance(actual_items, list) or not isinstance(required_items, list):
            return False
        actual_by_id: dict[str, Mapping[str, Any]] = {}
        for raw_item in cast(list[Any], actual_items):
            if not isinstance(raw_item, Mapping):
                continue
            item = cast(Mapping[str, Any], raw_item)
            capability_id = str(item.get("capability_id") or "")
            if capability_id:
                actual_by_id[capability_id] = item
        for raw_requirement in cast(list[Any], required_items):
            if not isinstance(raw_requirement, Mapping):
                return False
            requirement = cast(Mapping[str, Any], raw_requirement)
            candidate = actual_by_id.get(str(requirement.get("capability_id")))
            if candidate is None:
                return False
            for identity_field in ("kind", "name"):
                if candidate.get(identity_field) != requirement.get(identity_field):
                    return False
            required_version = requirement.get("version")
            if required_version is not None and candidate.get("version") != required_version:
                return False
            if not _mapping_contains(
                candidate.get("properties", {}),
                requirement.get("properties", {}),
            ):
                return False
        return True

    if isinstance(required, Mapping):
        if not isinstance(actual, Mapping):
            return False
        actual_mapping = cast(Mapping[Any, Any], actual)
        required_mapping = cast(Mapping[Any, Any], required)
        return all(
            key in actual_mapping and _mapping_contains(actual_mapping[key], value)
            for key, value in required_mapping.items()
        )
    if isinstance(required, list):
        if not isinstance(actual, list):
            return False
        actual_items = cast(list[Any], actual)
        required_items = cast(list[Any], required)
        return all(item in actual_items for item in required_items)
    return actual == required


def _project_edge_contracts(
    subtasks: Sequence[Subtask],
) -> tuple[list[DagEdgeContractV1], list[str], list[str]]:
    by_id = {item.id: item for item in subtasks}
    paths: list[str] = []
    invariant_ids: list[str] = []
    edges: list[DagEdgeContractV1] = []

    for consumer in subtasks:
        declared_inputs = list(consumer.dependency_inputs)
        by_producer: Dict[str, list[DependencyInputContractV1]] = {}
        for item in declared_inputs:
            by_producer.setdefault(item.producer_id, []).append(item)
        if not consumer.depends_on and declared_inputs:
            paths.append(f"subtasks[{consumer.id}].dependency_inputs")
            invariant_ids.append("root_dependency_inputs_empty")
        extra_producers = sorted(set(by_producer) - set(consumer.depends_on))
        if extra_producers:
            paths.append(f"subtasks[{consumer.id}].dependency_inputs")
            invariant_ids.append("dependency_input_matches_authoritative_edge")
        slots = [item.input_slot for item in declared_inputs]
        if len(slots) != len(set(slots)):
            paths.append(f"subtasks[{consumer.id}].dependency_inputs")
            invariant_ids.append("dependency_input_slot_unique")

        for producer_id in consumer.depends_on:
            contracts = by_producer.get(producer_id, [])
            edge_path = f"subtasks[{consumer.id}].dependency_inputs[{producer_id}]"
            if len(contracts) != 1:
                paths.append(edge_path)
                invariant_ids.append("dependency_input_exactly_once")
                continue
            input_contract = contracts[0]
            producer = by_id.get(producer_id)
            if producer is None:
                paths.append(edge_path)
                invariant_ids.append("dependency_input_producer_exists")
                continue
            if producer.id == consumer.id:
                paths.append(edge_path)
                invariant_ids.append("dependency_input_not_self")
                continue
            output_contract = producer.output_contract
            if output_contract is None:
                paths.append(f"subtasks[{producer.id}].output_contract")
                invariant_ids.append("dependency_producer_output_contract_exists")
                continue

            producer_type = canonical_artifact_type(output_contract.artifact_type)
            producer_extension = _known_extension(
                output_contract.output_extension or producer.output_extension
            )
            edge_valid = True
            if producer_type not in set(input_contract.accepted_artifact_types):
                paths.append(f"{edge_path}.accepted_artifact_types")
                invariant_ids.append("dependency_artifact_type_compatible")
                edge_valid = False
            if producer_extension not in set(input_contract.accepted_extensions):
                paths.append(f"{edge_path}.accepted_extensions")
                invariant_ids.append("dependency_extension_compatible")
                edge_valid = False
            required_interface = _json_object(
                input_contract.required_interface_contract_json
            )
            producer_interface = dict(output_contract.interface_contract)
            if not _mapping_contains(producer_interface, required_interface):
                paths.append(f"{edge_path}.required_interface_contract_json")
                invariant_ids.append("dependency_interface_contract_compatible")
                edge_valid = False
            if not edge_valid:
                continue
            edges.append(
                DagEdgeContractV1(
                    producer_id=producer.id,
                    consumer_id=consumer.id,
                    input_slot=input_contract.input_slot,
                    producer_artifact_type=producer_type,
                    producer_output_extension=producer_extension,
                    producer_interface_contract_json=producer_interface,
                    accepted_artifact_types=input_contract.accepted_artifact_types,
                    accepted_extensions=input_contract.accepted_extensions,
                    consumption_mode=input_contract.consumption_mode,
                    required_interface_contract_json=required_interface,
                    producer_output_contract_sha256=canonical_sha256(
                        output_contract.model_dump(mode="json")
                    ),
                    consumer_input_contract_sha256=(
                        input_contract.input_contract_sha256
                    ),
                )
            )

    edges.sort(key=lambda item: (item.producer_id, item.consumer_id, item.input_slot))
    return edges, paths, invariant_ids


def _normalize_produced_files(
    subtask: Subtask,
    contract: SubtaskOutputContract,
    *,
    paths: List[str],
    invariant_ids: List[str],
) -> SubtaskOutputContract:
    normalized_files: List[ProducedFileContract] = []
    primary_type = canonical_artifact_type(subtask.artifact_type)
    for index, produced in enumerate(contract.produced_files):
        item_type = canonical_artifact_type(produced.artifact_type)
        normalized = produced.model_copy(update={"artifact_type": item_type})
        normalized_files.append(normalized)

    required = [
        (index, item)
        for index, item in enumerate(normalized_files)
        if bool(item.required)
    ]
    primary_matches = []
    for index, item in required:
        path_type = _known_extension_artifact(item.path_hint)
        if item.artifact_type == primary_type:
            primary_matches.append(index)
            if path_type is not None and path_type != primary_type:
                paths.append(
                    f"subtasks[{subtask.id}].output_contract.produced_files[{index}].path_hint"
                )
                invariant_ids.append("primary_produced_file_path_matches_artifact_type")
    if required and not primary_matches and primary_type not in {"bundle", "directory"}:
        paths.append(f"subtasks[{subtask.id}].output_contract.produced_files")
        invariant_ids.append("required_produced_file_has_primary_type")

    return contract.model_copy(update={"produced_files": normalized_files})


def project_planner_contract(
    output: PlannerOutput,
    *,
    planner_response_sha256: str | None = None,
    require_edge_contracts: bool = True,
) -> PlannerContractProjection:
    """Project a Planner response without changing model-owned semantics."""

    normalized_subtasks: List[Subtask] = []
    conflict_paths: List[str] = []
    invariant_ids: List[str] = []
    warnings: List[str] = []
    expected_consumers: Dict[str, List[str]] = {
        subtask.id: [] for subtask in output.subtasks
    }
    for downstream in output.subtasks:
        for dependency in downstream.depends_on:
            if dependency in expected_consumers:
                expected_consumers[dependency].append(downstream.id)

    for subtask in output.subtasks:
        primary_type = canonical_artifact_type(subtask.artifact_type)
        contract = subtask.output_contract
        if contract is None:
            contract = SubtaskOutputContract(
                artifact_type=ArtifactType(primary_type),
                output_extension=default_extension(primary_type),
            )
            warnings.append(f"subtasks[{subtask.id}].output_contract_defaulted")

        nested_type = canonical_artifact_type(contract.artifact_type)
        if nested_type != primary_type:
            conflict_paths.append(f"subtasks[{subtask.id}].output_contract.artifact_type")
            invariant_ids.append("top_level_nested_artifact_type_equal")

        top_extension = _known_extension(subtask.output_extension)
        nested_extension = _known_extension(contract.output_extension)
        container_artifact = primary_type in {"bundle", "directory"}
        if container_artifact:
            if top_extension or nested_extension:
                warnings.append(
                    f"subtasks[{subtask.id}].container_output_extension_omitted"
                )
            top_extension = ""
            nested_extension = ""
        elif top_extension and nested_extension and top_extension != nested_extension:
            conflict_paths.append(f"subtasks[{subtask.id}].output_extension")
            invariant_ids.append("top_level_nested_extension_equal")
        output_extension = top_extension or nested_extension or default_extension(primary_type)
        produced_extensions = _produced_file_extensions(contract)
        if not container_artifact and len(produced_extensions) == 1:
            produced_extension = produced_extensions[0]
            if output_extension != produced_extension:
                # The physical produced-file declaration is the strongest
                # source of extension truth.  Correct only this derived
                # metadata field; task semantics and content contracts stay
                # untouched.  This handles e.g. a Coq `.v` file accidentally
                # paired with the generic code default `.py`.
                output_extension = produced_extension
                warnings.append(
                    f"subtasks[{subtask.id}].output_extension_derived_from_produced_file"
                )

        for extension, path in (
            (output_extension, f"subtasks[{subtask.id}].output_extension"),
            (nested_extension, f"subtasks[{subtask.id}].output_contract.output_extension"),
        ):
            extension_type = _known_extension_artifact(extension)
            if extension_type is not None and extension_type != primary_type:
                conflict_paths.append(path)
                invariant_ids.append("known_extension_matches_artifact_type")

        contract = _normalize_produced_files(
            subtask,
            contract,
            paths=conflict_paths,
            invariant_ids=invariant_ids,
        )
        from .model_response_contracts import (
            ModelResponseContractError,
            OutputFormatRequirement,
        )

        try:
            OutputFormatRequirement.from_contract_projection(contract)
        except ModelResponseContractError:
            conflict_paths.append(
                f"subtasks[{subtask.id}].output_contract.json_schema"
            )
            invariant_ids.append("json_output_has_enforceable_semantic_schema")
        declared_consumers = list(dict.fromkeys(contract.downstream_consumers))
        expected_for_subtask = list(
            dict.fromkeys(expected_consumers.get(subtask.id, []))
        )
        unexpected_consumers = [
            consumer
            for consumer in declared_consumers
            if consumer not in expected_for_subtask
        ]
        if unexpected_consumers:
            conflict_paths.append(
                f"subtasks[{subtask.id}].output_contract.downstream_consumers"
            )
            invariant_ids.append(
                "downstream_consumer_has_reciprocal_dependency"
            )
        derived_consumers = list(
            dict.fromkeys(declared_consumers + expected_for_subtask)
        )
        if derived_consumers != declared_consumers:
            warnings.append(
                f"subtasks[{subtask.id}].downstream_consumers_derived"
            )
        from .json_serialization import json_serialization_format
        interface = dict(contract.interface_contract)
        encoding = json_serialization_format({**contract.model_dump(mode="json"),
            "artifact_type": primary_type, "output_extension": output_extension})
        if encoding == "jsonl":
            interface["serialization_format"] = encoding
        canonical_contract = contract.model_copy(
            update={
                "artifact_type": ArtifactType(primary_type),
                "output_extension": output_extension,
                "downstream_consumers": derived_consumers,
                "interface_contract": interface,
            }
        )
        canonical_stage = subtask.task_stage or TaskStage.PRODUCE_ARTIFACT
        normalized_subtasks.append(
            subtask.model_copy(
                update={
                    "artifact_type": ArtifactType(primary_type),
                    "output_extension": output_extension,
                    "output_contract": canonical_contract,
                    "task_stage": canonical_stage,
                }
            )
        )

    if conflict_paths:
        raise PlannerContractConflict(conflict_paths, invariant_ids)

    edge_contracts, edge_paths, edge_invariants = _project_edge_contracts(
        normalized_subtasks
    )
    if edge_paths and require_edge_contracts:
        raise PlannerContractConflict(
            edge_paths,
            edge_invariants,
            failure_code="planner_edge_contract_conflict",
        )
    if edge_paths:
        edge_contracts = []
        warnings.append("planner_edge_contract_projection_deferred")
    incoming_by_consumer: Dict[str, list[DagEdgeContractV1]] = {}
    for edge in edge_contracts:
        incoming_by_consumer.setdefault(edge.consumer_id, []).append(edge)
    normalized_subtasks = [
        item.model_copy(
            update={
                "incoming_edge_contracts": incoming_by_consumer.get(item.id, [])
            }
        )
        for item in normalized_subtasks
    ]
    projected = output.model_copy(
        update={
            "subtasks": normalized_subtasks,
            "edge_contracts": edge_contracts,
        }
    )
    semantic_before = _model_owned_semantics(output)
    semantic_after = _model_owned_semantics(projected, baseline=output)
    # Missing reciprocal consumer declarations are a compatible derived view,
    # not a model-owned semantic change.  Extra declarations were rejected
    # above, so only the authoritative dependency projection is normalized.
    comparable_before = copy.deepcopy(semantic_before)
    before_subtasks = comparable_before.get("subtasks", [])
    after_subtasks = semantic_after.get("subtasks", [])
    for index, before_subtask in enumerate(before_subtasks):
        if index >= len(after_subtasks):
            break
        # Output extensions are physical delivery metadata derived from
        # required produced-file paths.  Keep the canonical derived value
        # out of the model-semantic round-trip comparison.
        before_subtask["output_extension"] = after_subtasks[index].get(
            "output_extension", before_subtask.get("output_extension")
        )
        before_contract = before_subtask.get("output_contract")
        after_contract = after_subtasks[index].get("output_contract")
        if isinstance(before_contract, dict) and isinstance(after_contract, dict):
            before_contract["output_extension"] = after_contract.get(
                "output_extension", before_contract.get("output_extension")
            )
            before_contract["downstream_consumers"] = list(
                after_contract.get("downstream_consumers", [])
            )
    semantic_round_trip = comparable_before == semantic_after
    if not semantic_round_trip:
        raise RuntimeError("planner_contract_projection_semantic_round_trip_failure")

    canonical_hash = canonical_sha256(projected.model_dump(mode="json"))
    edge_contracts_hash = canonical_sha256(
        [item.model_dump(mode="json") for item in edge_contracts]
    )
    audit_projection = cast(PlannerContractAuditV1, {
        "protocol": "sgar-planner-contract-audit-v1",
        "projection_version": "planner-contract-projection-v3",
        "planner_response_sha256": planner_response_sha256,
        "canonical_contract_sha256": canonical_hash,
        "model_owned_semantics_sha256": canonical_sha256(semantic_before),
        "semantic_round_trip": semantic_round_trip,
        "warning_codes": sorted(set(warnings)),
        "conflict_paths": [],
        "invariant_ids": [],
        "edge_contracts_sha256": edge_contracts_hash,
    })
    audit_projection["audit_sha256"] = canonical_sha256(audit_projection)
    return PlannerContractProjection(
        output=projected,
        canonical_contract_sha256=canonical_hash,
        edge_contracts=tuple(edge_contracts),
        edge_contracts_sha256=edge_contracts_hash,
        audit=audit_projection,
    )


def project_planner_contract_v2(
    output: PlannerOutput,
    *,
    planner_response_sha256: str | None = None,
) -> PlannerContractProjection:
    """Project V6 semantics without inventing execution strategy or Schema."""

    if not output.subtasks or any(
        item.semantic_contract_v2 is None for item in output.subtasks
    ):
        raise PlannerContractConflict(
            ["subtasks.semantic_contract_v2"],
            ["planner_v6_semantic_contract_present"],
        )
    normalized: list[Subtask] = []
    conflicts: list[str] = []
    invariants: list[str] = []
    for item in output.subtasks:
        semantic = item.semantic_contract_v2
        assert semantic is not None
        if semantic.task_id != item.id:
            conflicts.append(f"subtasks[{item.id}].semantic_contract_v2.task_id")
            invariants.append("planner_v6_semantic_task_identity_matches")
        if semantic.role_intent != item.role or semantic.task != item.description:
            conflicts.append(f"subtasks[{item.id}].semantic_contract_v2")
            invariants.append("planner_v6_semantic_text_projection_matches")
        if semantic.output.artifact_type != canonical_artifact_type(item.artifact_type):
            conflicts.append(
                f"subtasks[{item.id}].semantic_contract_v2.output.artifact_type"
            )
            invariants.append("planner_v6_semantic_output_type_matches")
        contract = item.output_contract
        if contract is None:
            conflicts.append(f"subtasks[{item.id}].output_contract")
            invariants.append("planner_v6_compatibility_output_contract_present")
            continue
        if contract.syntax_validator != semantic.output.syntax_validator:
            conflicts.append(
                f"subtasks[{item.id}].output_contract.syntax_validator"
            )
            invariants.append("planner_v6_syntax_validator_projection_matches")
        if tuple(contract.acceptance_criteria) != tuple(
            semantic.acceptance_conditions
        ):
            conflicts.append(
                f"subtasks[{item.id}].output_contract.acceptance_criteria"
            )
            invariants.append("planner_v6_acceptance_projection_matches")
        container_artifact = canonical_artifact_type(item.artifact_type) in {
            "bundle",
            "directory",
        }
        output_extension = (
            ""
            if container_artifact
            else (
                str(item.output_extension).strip()
                or str(contract.output_extension).strip()
                or default_extension(item.artifact_type)
            )
        )
        produced_extensions = _produced_file_extensions(contract)
        if not container_artifact and len(produced_extensions) == 1:
            # V6 carries the semantic contract separately from the legacy
            # compatibility extension fields.  Derive the latter from the
            # required physical file name so a `.v` source cannot be treated
            # as generic `.py` merely because the artifact type is `code`.
            output_extension = produced_extensions[0]
        from .json_serialization import json_serialization_format
        interface = dict(contract.interface_contract)
        encoding = json_serialization_format({**contract.model_dump(mode="json"),
            "artifact_type": canonical_artifact_type(item.artifact_type),
            "output_extension": output_extension})
        if encoding == "jsonl":
            interface["serialization_format"] = encoding
        normalized_contract = contract.model_copy(
            update={"output_extension": output_extension, "interface_contract": interface}
        )
        normalized.append(
            item.model_copy(
                update={
                    "output_extension": output_extension,
                    "output_contract": normalized_contract,
                    "task_stage": item.task_stage or TaskStage.PRODUCE_ARTIFACT,
                }
            )
        )
    if conflicts:
        raise PlannerContractConflict(conflicts, invariants)

    edges, edge_paths, edge_invariants = _project_edge_contracts(normalized)
    if edge_paths:
        raise PlannerContractConflict(
            edge_paths,
            edge_invariants,
            failure_code="planner_v6_edge_contract_conflict",
        )
    incoming_by_consumer: Dict[str, list[DagEdgeContractV1]] = {}
    for edge in edges:
        incoming_by_consumer.setdefault(edge.consumer_id, []).append(edge)
    normalized = [
        item.model_copy(
            update={
                "incoming_edge_contracts": incoming_by_consumer.get(item.id, [])
            }
        )
        for item in normalized
    ]
    projected = output.model_copy(
        update={"subtasks": normalized, "edge_contracts": edges}
    )
    canonical_hash = canonical_sha256(projected.model_dump(mode="json"))
    edge_hash = canonical_sha256(
        [edge.model_dump(mode="json") for edge in edges]
    )
    semantic_projection = [
        item.semantic_contract_v2.model_dump(mode="json")
        for item in normalized
        if item.semantic_contract_v2 is not None
    ]
    audit_projection = cast(PlannerContractAuditV1, {
        "protocol": "sgar-planner-contract-audit-v1",
        "projection_version": "planner-contract-projection-v4-wire-v6",
        "planner_response_sha256": planner_response_sha256,
        "canonical_contract_sha256": canonical_hash,
        "model_owned_semantics_sha256": canonical_sha256(semantic_projection),
        "semantic_round_trip": True,
        "warning_codes": [],
        "conflict_paths": [],
        "invariant_ids": [],
        "edge_contracts_sha256": edge_hash,
    })
    audit_projection["audit_sha256"] = canonical_sha256(audit_projection)
    return PlannerContractProjection(
        output=projected,
        canonical_contract_sha256=canonical_hash,
        edge_contracts=tuple(edges),
        edge_contracts_sha256=edge_hash,
        audit=audit_projection,
    )


def planner_contract_audit_from_failure(
    error: Exception,
    *,
    planner_response_sha256: str | None = None,
) -> Dict[str, Any]:
    paths = list(getattr(error, "paths", ()))
    invariant_ids = list(getattr(error, "invariant_ids", ()))
    projection = cast(PlannerContractAuditV1, {
        "protocol": "sgar-planner-contract-audit-v1",
        "projection_version": "planner-contract-projection-v3",
        "planner_response_sha256": planner_response_sha256,
        "canonical_contract_sha256": None,
        "model_owned_semantics_sha256": None,
        "semantic_round_trip": False,
        "warning_codes": [],
        "conflict_paths": paths,
        "invariant_ids": invariant_ids,
        "edge_contracts_sha256": None,
    })
    projection["audit_sha256"] = canonical_sha256(projection)
    return projection


def validate_planner_subtask_contract(subtask: Subtask) -> None:
    """Validate a Subtask before it is admitted to Retrieval."""

    if subtask.semantic_contract_v2 is not None:
        semantic = subtask.semantic_contract_v2
        if semantic.task_id != subtask.id:
            raise PlannerContractConflict(
                [f"subtasks[{subtask.id}].semantic_contract_v2.task_id"],
                ["planner_v6_semantic_task_identity_matches"],
            )
        if semantic.role_intent != subtask.role or semantic.task != subtask.description:
            raise PlannerContractConflict(
                [f"subtasks[{subtask.id}].semantic_contract_v2"],
                ["planner_v6_semantic_text_projection_matches"],
            )
        if semantic.output.artifact_type != canonical_artifact_type(subtask.artifact_type):
            raise PlannerContractConflict(
                [f"subtasks[{subtask.id}].semantic_contract_v2.output.artifact_type"],
                ["planner_v6_semantic_output_type_matches"],
            )
        if (subtask.output_contract is None or
            subtask.output_contract.syntax_validator != semantic.output.syntax_validator):
            raise PlannerContractConflict(
                [f"subtasks[{subtask.id}].output_contract.syntax_validator"],
                ["planner_v6_syntax_validator_projection_matches"],
            )
        if {edge.producer_id for edge in subtask.incoming_semantic_edges_v2} != set(
            subtask.depends_on
        ):
            raise PlannerContractConflict(
                [f"subtasks[{subtask.id}].incoming_semantic_edges_v2"],
                ["planner_v6_semantic_edge_parity"],
            )
        return

    isolated = subtask.model_copy(
        update={
            "depends_on": [],
            "dependency_inputs": [],
            "incoming_edge_contracts": [],
        }
    )
    if isolated.output_contract is not None:
        isolated = isolated.model_copy(
            update={
                "output_contract": isolated.output_contract.model_copy(
                    update={"downstream_consumers": []}
                )
            }
        )
    project_planner_contract(PlannerOutput(subtasks=[isolated]))


def audit_planner_contract_gate() -> Dict[str, Any]:
    """Zero-cost behavior and source gate for format-authority drift."""

    from .planner import SGARPlanner
    from .planner_wire import (
        PLANNER_WIRE_PROTOCOL,
        planner_probe_wire_payload,
        project_planner_wire_payload,
    )

    projection_source = inspect.getsource(project_planner_contract)
    coercion_source = inspect.getsource(SGARPlanner._coerce_planner_payload)
    forbidden_projection_tokens = (
        ".description",
        ".expected_output",
        ".grounding_requirements",
        ".required_content",
    )
    forbidden_coercion_calls = (
        "_infer_planner_artifact_type(",
        "_final_delivery_artifact_type(",
        "_is_final_delivery_contract(",
        "_looks_like_read_only_subtask(",
        "_infer_task_stage(",
    )
    explicit = Subtask(
        id="contract-gate",
        role="Producer",
        description="Use a Markdown input to produce the declared result.",
        expected_output="A JSON result based on the supplied Markdown.",
        artifact_type=ArtifactType.JSON,
        output_extension=".json",
        output_contract=SubtaskOutputContract(
            artifact_type=ArtifactType.JSON,
            output_extension=".json",
            json_schema={
                "type": "object",
                "properties": {"result": {"type": "string"}},
                "required": ["result"],
                "additionalProperties": False,
            },
            grounding_requirements=["The input descriptor is Markdown."],
        ),
    )
    behavior = project_planner_contract(PlannerOutput(subtasks=[explicit]))
    wire_payload = planner_probe_wire_payload()
    wire_output = project_planner_wire_payload(wire_payload)
    wire_behavior = project_planner_contract_v2(wire_output)
    checks = {
        "explicit_type_preserved": (
            behavior.output.subtasks[0].artifact_type is ArtifactType.JSON
            and behavior.output.subtasks[0].output_extension == ".json"
        ),
        "projection_ignores_textual_format_hints": not any(
            token in projection_source for token in forbidden_projection_tokens
        ),
        "coercion_has_no_textual_format_inference": not any(
            token in coercion_source for token in forbidden_coercion_calls
        ),
        "semantic_round_trip": bool(behavior.audit["semantic_round_trip"]),
        "live_wire_protocol_v6": wire_payload.get("protocol") == PLANNER_WIRE_PROTOCOL,
        "v6_semantic_contract_projects": all(
            item.semantic_contract_v2 is not None for item in wire_output.subtasks
        ),
        "v6_semantic_edge_projects": len(wire_behavior.edge_contracts) == 1,
    }
    projection = {
        "protocol": "sgar-planner-contract-gate-v1",
        "checks": checks,
        "canonical_contract_sha256": behavior.canonical_contract_sha256,
        "typed_wire_contract_sha256": wire_behavior.canonical_contract_sha256,
    }
    return {
        **projection,
        "valid": all(checks.values()),
        "audit_sha256": canonical_sha256(projection),
    }
