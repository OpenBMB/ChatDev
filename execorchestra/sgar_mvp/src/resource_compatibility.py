"""Deterministic Tool compatibility gate used before semantic ranking.

The gate is intentionally Tool-only.  Model, Agent, Skill, and Resource
candidates bypass it unchanged so adding execution contracts cannot reduce
their recall.  Missing Tool metadata produces UNKNOWN (kept); only an explicit
contract contradiction produces INCOMPATIBLE (removed).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import re
from typing import Any, Dict, Iterable, Sequence

from .schema import ManifestType, Subtask, TypedResourceRef
from .capability_operations import (
    manifest_capability_operations,
    normalize_task_general_operation_kinds,
    normalize_task_capability_operations,
    tool_allowed_operation_kinds,
)


class CompatibilityVerdict(str, Enum):
    COMPATIBLE = "compatible"
    UNKNOWN = "unknown"
    INCOMPATIBLE = "incompatible"


@dataclass(frozen=True)
class NormalizedNodeContract:
    operation_kinds: frozenset[str]
    general_operation_kinds: frozenset[str]
    runtime: str | None
    input_kinds: frozenset[str]
    output_kind: str | None
    domains: frozenset[str]
    side_effect: str
    requires_complete_output: bool = False
    data_formats: frozenset[str] = frozenset()


@dataclass(frozen=True)
class CompatibilityDecision:
    verdict: CompatibilityVerdict
    reasons: tuple[str, ...] = ()
    soft_reasons: tuple[str, ...] = ()


_GENERIC_DOMAINS = {
    "data", "document", "documents", "docs", "file", "files", "text",
    "utility", "conversion", "analysis", "automation", "api", "web",
}

# Domain labels are semantic evidence, not exact string identities.  Keep the
# ontology small and explicit so unrelated domains remain isolated while
# adjacent labels such as ``language-detection`` and ``nlp`` can interoperate.
_DOMAIN_COMPATIBILITY_GROUPS = (
    frozenset({"nlp", "language-detection", "probabilistic-text-language-detection"}),
    frozenset({"math", "symbolic-math", "computer-algebra"}),
    frozenset({"filesystem", "local-filesystem", "path-management"}),
)


def _domains_compatible(left: Iterable[str], right: Iterable[str]) -> bool:
    left_set = set(left)
    right_set = set(right)
    if left_set & right_set:
        return True
    return any(left_set & group and right_set & group for group in _DOMAIN_COMPATIBILITY_GROUPS)


def _explicit_tool_general_operation_kinds(kinds: Iterable[str]) -> frozenset[str]:
    """Return semantic Tool kinds, excluding the legacy ``run_tool`` fallback."""
    return frozenset(kind for kind in kinds if kind != "run_tool")


def _strip_original_query(text: str) -> str:
    return re.split(
        r"\n\s*Original user query\s*:\s*\n",
        str(text or ""),
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()


def current_node_contract_text(subtask: Subtask) -> str:
    """Canonical node-local contract shared by routing, execution, and evaluation."""
    contract = subtask.output_contract
    contract_lines: list[str] = []
    description = _strip_original_query(subtask.description)
    if description:
        contract_lines.append(description)
    if contract is not None:
        contract_lines.extend(str(item).strip() for item in contract.required_content if str(item).strip())
        contract_lines.extend(str(item).strip() for item in contract.acceptance_criteria if str(item).strip())
        contract_lines.extend(str(item).strip() for item in contract.grounding_requirements if str(item).strip())
    return "\n".join(contract_lines).strip()


def _text_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9_+.-]+|[\u4e00-\u9fff]+", value.lower())
        if len(token) > 1
    }


def _normalized_input_kind(name: str, kind: str) -> str:
    name = name.lower()
    kind = kind.lower().replace("-", "_").replace(" ", "_")
    if kind in {"directory_path", "dir_path", "folder_path", "directory"}:
        return "directory_path"
    if kind in {"file_path", "filepath"}:
        return "file_path"
    if "director" in name or name in {"dir", "folder", "root"}:
        return "directory_path"
    if "path" in name or name.endswith("_file") or name in {"file", "filename"}:
        return "file_path"
    aliases = {
        "filepath": "file_path",
        "directory": "directory_path",
        "dir_path": "directory_path",
        "folder_path": "directory_path",
        "str": "string",
        "object": "json",
        "dict": "json",
    }
    return aliases.get(kind, kind)


def _task_runtime(text: str) -> str | None:
    if "mcp" in text:
        return "mcp_server"
    if any(word in text for word in ("rest api", "http api", "api endpoint")):
        return "rest_api"
    if any(word in text for word in ("python library", "python package")):
        return "python_library"
    return None


def _operation_inference_text(subtask: Subtask) -> str:
    """Keep positive contract clauses without treating prohibitions as intent."""
    prohibition = re.compile("\\b(?:do not|don't|must not|avoid)\\b|\u4e0d\u8981|\u4e0d\u5f97", re.IGNORECASE)
    bullet_prefix = re.compile('^\\s*(?:[-*\u2022]|\\d+[.)\u3001])\\s*')
    clauses: list[str] = []
    for line in current_node_contract_text(subtask).splitlines():
        line = bullet_prefix.sub("", line).strip()
        for clause in re.split('(?<=[.;\u3002\uff1b!?])\\s*', line):
            clause = clause.strip()
            if not clause:
                continue
            match = prohibition.search(clause)
            if match is None:
                clauses.append(clause)
                continue
            positive_prefix = re.sub('(?:,|\uff0c)?\\s*(?:but|however|\u4f46\u662f|\u4f46)?\\s*$', "", clause[:match.start()], flags=re.IGNORECASE).strip()
            if positive_prefix:
                clauses.append(positive_prefix)
    return "\n".join(clauses)


def normalize_subtask_contract(subtask: Subtask) -> NormalizedNodeContract:
    local_text = _operation_inference_text(subtask).lower()
    operations = normalize_task_capability_operations(local_text)
    general_operations = normalize_task_general_operation_kinds(local_text)
    input_kinds: set[str] = set()
    domains: set[str] = set()
    if re.search(r"\b[^\s]+\.pdf\b", local_text) or "pdf" in local_text:
        input_kinds.add("file_path")
        domains.add("pdf")
    if (
        general_operations & {"list_directory"}
        or any(op in operations for op in {"list_immediate_directory_entries", "recursive_directory_traversal", "search_files_by_pattern", "create_directory"})
    ):
        input_kinds.add("directory_path")
        domains.add("filesystem")
    if any(op in operations for op in {"read_text_file", "inspect_path_metadata", "edit_file_content"}):
        input_kinds.add("file_path")
        domains.add("filesystem")
    if "detect_language_candidates" in operations:
        domains.add("language-detection")
    side_effect = "write" if operations & {"edit_file_content", "create_directory"} else "read"
    requires_complete_output = bool(re.search(
        '\\b(?:all|every|complete|entire|full|preserve)\\b|\u5b8c\u6574|\u5168\u90e8|\u6240\u6709|\u4fdd\u7559\u6240\u6709',
        local_text,
    ))
    data_formats = frozenset(
        fmt for fmt in ("json", "yaml", "csv", "xml", "toml", "sql", "markdown", "html")
        if re.search(rf"\b{fmt}\b", local_text)
    )
    return NormalizedNodeContract(
        operation_kinds=frozenset(operations),
        general_operation_kinds=frozenset(general_operations),
        runtime=_task_runtime(local_text),
        input_kinds=frozenset(input_kinds),
        output_kind=(
            subtask.output_contract.artifact_type.value
            if subtask.output_contract is not None
            else None
        ),
        domains=frozenset(domains),
        side_effect=side_effect,
        requires_complete_output=requires_complete_output,
        data_formats=data_formats,
    )


def _manifest_input_kinds(manifest: Dict[str, Any]) -> set[str]:
    contracts = manifest.get("input_contract") or manifest.get("io", {}).get("input_contract") or []
    return {
        _normalized_input_kind(str(item.get("name", "")), str(item.get("kind", "")))
        for item in contracts
        if isinstance(item, dict) and (item.get("kind") or item.get("name"))
    }


def _manifest_domains(manifest: Dict[str, Any]) -> set[str]:
    capability = manifest.get("capability", {}) if isinstance(manifest.get("capability"), dict) else {}
    domains = {
        token
        for value in capability.get("domain_tags", []) or []
        for token in _text_tokens(str(value))
    }
    return domains - _GENERIC_DOMAINS


def _manifest_semantic_output_kind(manifest: Dict[str, Any]) -> str | None:
    """Read only a declared semantic result kind, never a transport envelope.

    A Tool's ``output_contract.artifact_type`` describes how its immediate
    result is serialized (often JSON), while a node contract describes the
    final deliverable after possible bridge/synthesis steps.  Comparing those
    two fields during pre-plan retrieval would discard valid tools such as a
    JSON-wrapped PDF extractor for a plaintext report.  Hard output filtering
    is therefore reserved for an explicit semantic declaration.
    """
    value = manifest.get("semantic_output_kind")
    if value is None:
        output_contract = manifest.get("output_contract")
        if not isinstance(output_contract, dict):
            io_contract = manifest.get("io", {}) if isinstance(manifest.get("io"), dict) else {}
            output_contract = io_contract.get("output_contract")
        if isinstance(output_contract, dict):
            value = output_contract.get("semantic_output_kind")
    return str(value).strip().lower() or None if value is not None else None


def _manifest_returns_truncated_preview(manifest: Dict[str, Any]) -> bool:
    """Whether the manifest explicitly limits results to a preview/truncation."""
    constraint = manifest.get("constraint") if isinstance(manifest.get("constraint"), dict) else {}
    capability = manifest.get("capability") if isinstance(manifest.get("capability"), dict) else {}
    text = " ".join(
        str(value)
        for value in [
            capability.get("summary", ""),
            capability.get("description", ""),
            constraint.get("output_shape", ""),
            *(constraint.get("limitations", []) or []),
        ]
    ).lower()
    return any(marker in text for marker in (
        "preview", "returns only", "return only", "first at most", "first 800", "only the first",
    ))


def _manifest_data_formats(manifest: Dict[str, Any]) -> frozenset[str]:
    """Return concrete data formats named by a Tool's semantic manifest text."""
    capability = manifest.get("capability") if isinstance(manifest.get("capability"), dict) else {}
    routing = manifest.get("routing") if isinstance(manifest.get("routing"), dict) else {}
    io_contract = manifest.get("io") if isinstance(manifest.get("io"), dict) else {}
    text = " ".join(
        str(value)
        for value in [
            manifest.get("resource_id", ""),
            capability.get("summary", ""),
            capability.get("description", ""),
            capability.get("problem_space", ""),
            routing.get("family", ""),
            *(routing.get("intent_tags", []) or []),
            io_contract,
            manifest.get("input_contract", []),
            manifest.get("output_contract", {}),
        ]
    ).lower()
    return frozenset(
        fmt for fmt in ("json", "yaml", "csv", "xml", "toml", "sql", "markdown", "html")
        if re.search(rf"\b{fmt}\b", text)
    )


def _manifest_negative_intents(manifest: Dict[str, Any]) -> str:
    routing = manifest.get("routing") if isinstance(manifest.get("routing"), dict) else {}
    values = routing.get("negative_intents", []) or []
    if isinstance(values, str):
        values = [values]
    return " ".join(str(value) for value in values).lower()


def _manifest_side_effect(manifest: Dict[str, Any], operations: set[str]) -> str:
    if operations & {"edit_file_content", "create_directory", "replace_text_fragment"}:
        return "write"
    routing = manifest.get("routing", {}) if isinstance(manifest.get("routing"), dict) else {}
    declared = str(routing.get("side_effect") or manifest.get("side_effect") or "").lower()
    if declared in {"write", "mutation", "mutating", "destructive"}:
        return "write"
    return "read"


def classify_tool_compatibility(
    contract: NormalizedNodeContract,
    manifest: Dict[str, Any],
) -> CompatibilityDecision:
    execution = manifest.get("execution", {}) if isinstance(manifest.get("execution"), dict) else {}
    runtime = str(execution.get("runtime") or "").lower() or None
    operations = manifest_capability_operations(manifest)
    general_operations = _explicit_tool_general_operation_kinds(
        tool_allowed_operation_kinds(manifest)
    )
    input_kinds = _manifest_input_kinds(manifest)
    output_kind = _manifest_semantic_output_kind(manifest)
    data_formats = _manifest_data_formats(manifest)
    negative_intents = _manifest_negative_intents(manifest)
    domains = _manifest_domains(manifest)
    side_effect = _manifest_side_effect(manifest, operations)
    hard_reasons: list[str] = []
    soft_reasons: list[str] = []
    has_positive_evidence = False

    if contract.runtime and runtime and contract.runtime != runtime:
        hard_reasons.append(f"runtime:{runtime}!={contract.runtime}")
    elif contract.runtime and runtime:
        has_positive_evidence = True
    if (
        contract.general_operation_kinds
        and general_operations
        and contract.general_operation_kinds.isdisjoint(general_operations)
    ):
        soft_reasons.append("operation_kind_mismatch")
    elif contract.general_operation_kinds and not general_operations:
        soft_reasons.append("operation_kind_unclassified")
    elif contract.general_operation_kinds and general_operations:
        has_positive_evidence = True
    if (
        "parse_data" in contract.general_operation_kinds
        and "json schema" in negative_intents
        and "parse_data" not in general_operations
    ):
        soft_reasons.append("negative_intent_mismatch")
    if contract.operation_kinds & operations:
        has_positive_evidence = True
    if contract.output_kind and output_kind and contract.output_kind != output_kind:
        hard_reasons.append(f"output_kind:{output_kind}!={contract.output_kind}")
    if contract.requires_complete_output and _manifest_returns_truncated_preview(manifest):
        hard_reasons.append("output_completeness_mismatch")
    if len(contract.data_formats) >= 2 and data_formats and not contract.data_formats.issubset(data_formats):
        # Node-level contracts commonly name source, intermediate, and final
        # formats. A single Tool need not support all of them because the Plan
        # Compiler may connect it through explicit transformation steps.
        soft_reasons.append("data_format_mismatch")
    if contract.input_kinds and input_kinds:
        path_kinds = {"file_path", "directory_path"}
        required_paths = contract.input_kinds & path_kinds
        offered_paths = input_kinds & path_kinds
        if required_paths and offered_paths and required_paths.isdisjoint(offered_paths):
            hard_reasons.append("input_kind_mismatch")
        elif required_paths and offered_paths:
            has_positive_evidence = True
    if contract.domains and domains and not _domains_compatible(contract.domains, domains):
        soft_reasons.append("domain_mismatch")
    elif contract.domains and domains:
        has_positive_evidence = True
    if contract.side_effect == "read" and side_effect == "write":
        hard_reasons.append("side_effect_mismatch")

    if hard_reasons:
        return CompatibilityDecision(
            CompatibilityVerdict.INCOMPATIBLE,
            tuple(hard_reasons),
            tuple(soft_reasons),
        )
    return CompatibilityDecision(
        CompatibilityVerdict.COMPATIBLE if has_positive_evidence else CompatibilityVerdict.UNKNOWN,
        (),
        tuple(soft_reasons),
    )


def filter_hard_compatible_candidates(
    subtask: Subtask,
    refs: Sequence[TypedResourceRef],
    resource_index: Dict[str, Dict[str, Any]],
) -> list[TypedResourceRef]:
    contract = normalize_subtask_contract(subtask)
    kept: list[TypedResourceRef] = []
    for ref in refs:
        if ref.resource_type != ManifestType.TOOL:
            kept.append(ref)
            continue
        raw = resource_index.get(ref.resource_id)
        if not isinstance(raw, dict):
            kept.append(ref)
            continue
        decision = classify_tool_compatibility(contract, raw)
        if decision.verdict != CompatibilityVerdict.INCOMPATIBLE:
            kept.append(ref)
    return kept


def filter_hard_compatible_manifests(
    subtask: Subtask,
    manifests: Sequence[Any],
    resource_index: Dict[str, Dict[str, Any]],
) -> list[Any]:
    """Return the pre-ranking library with explicit Tool mismatches removed."""
    contract = normalize_subtask_contract(subtask)
    kept: list[Any] = []
    for manifest in manifests:
        if getattr(manifest, "type", None) != ManifestType.TOOL:
            kept.append(manifest)
            continue
        resource_id = str(getattr(manifest, "id", ""))
        raw = resource_index.get(resource_id)
        if not isinstance(raw, dict):
            kept.append(manifest)
            continue
        decision = classify_tool_compatibility(contract, raw)
        if decision.verdict != CompatibilityVerdict.INCOMPATIBLE:
            kept.append(manifest)
    return kept
