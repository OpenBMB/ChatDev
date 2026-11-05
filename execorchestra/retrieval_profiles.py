"""Typed retrieval profiles for the S-GAR resource pool.

The resource manifests intentionally keep their existing V1 wire format.  This
module projects those manifests into three independent routing views:

* capability text: what the resource can do;
* soft constraint text: task/resource I/O compatibility suitable for embedding;
* hard requirements: executable facts that must be checked deterministically.

Provider credentials, local paths, dependency availability, prices, and
historical success counters are deliberately excluded from the constraint
embedding.  Mixing those fields into one semantic vector makes the score both
unstable and difficult to interpret.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence


PROFILE_VERSION = "typed-constraint-v8"
ACTIVE_LIFECYCLES = {"active_core", "active_conditional"}
ACTIVE_STATUSES = {"", "active", "available", "ok", "ready"}


def _list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    return [value]


def _strings(value: Any) -> List[str]:
    output: List[str] = []
    for item in _list(value):
        if isinstance(item, Mapping):
            text = json.dumps(item, ensure_ascii=False, sort_keys=True)
        else:
            text = str(item).strip()
        if text and text not in output:
            output.append(text)
    return output


def resource_type(raw: Mapping[str, Any]) -> str:
    legacy = raw.get("type")
    if isinstance(legacy, Mapping):
        legacy_value = legacy.get("resource_type")
    else:
        legacy_value = None
    return str(raw.get("resource_type") or legacy_value or "Unknown")


def _type_block(raw: Mapping[str, Any], name: str) -> Dict[str, Any]:
    type_specific = raw.get("type_specific")
    if not isinstance(type_specific, Mapping):
        return {}
    block = type_specific.get(name)
    return dict(block) if isinstance(block, Mapping) else {}


def _input_contract(raw: Mapping[str, Any]) -> List[Dict[str, Any]]:
    io = raw.get("io")
    io_contract = io.get("input_contract") if isinstance(io, Mapping) else None
    value = io_contract if isinstance(io_contract, list) else raw.get("input_contract", [])
    return [dict(item) for item in _list(value) if isinstance(item, Mapping)]


def _output_contract(raw: Mapping[str, Any]) -> Dict[str, Any]:
    io = raw.get("io")
    io_contract = io.get("output_contract") if isinstance(io, Mapping) else None
    value = io_contract if isinstance(io_contract, Mapping) else raw.get("output_contract", {})
    return dict(value) if isinstance(value, Mapping) else {}


def _format_inputs(contracts: Sequence[Mapping[str, Any]]) -> str:
    formatted: List[str] = []
    for item in contracts:
        name = str(item.get("name") or "input")
        kind = str(item.get("kind") or "unknown")
        requirement = "required" if item.get("required", True) else "optional"
        port = f"{name}:{kind}:{requirement}"
        description = str(item.get("description") or "").strip()
        if description:
            port += " (" + description + ")"
        formatted.append(port)
    return ", ".join(formatted)


def _format_output(contract: Mapping[str, Any]) -> str:
    artifact = str(contract.get("artifact_type") or contract.get("kind") or "unknown")
    description = str(contract.get("description") or "").strip()
    schema = contract.get("schema_hint")
    parts = [artifact]
    if description:
        parts.append(description)
    if schema:
        parts.append(
            json.dumps(schema, ensure_ascii=False, sort_keys=True)
            if isinstance(schema, (dict, list))
            else str(schema)
        )
    return " | ".join(parts)


def _context_tokens(value: Any) -> int | None:
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value or "").strip().lower().replace(",", "")
    if not text:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*([km]?)", text)
    if not match:
        return None
    number = float(match.group(1))
    suffix = match.group(2)
    if suffix == "k":
        number *= 1_000
    elif suffix == "m":
        number *= 1_000_000
    return int(number)


def model_modality_support(model: Mapping[str, Any], modality: str, direction: str) -> bool | None:
    """Declared modality support, with unknown preserved for legacy metadata."""
    normalized = str(modality).strip().lower()
    normalized = {"images": "image", "videos": "video"}.get(normalized, normalized)
    declared = model.get(f"{direction}_modalities")
    if isinstance(declared, list):
        return normalized in declared
    if direction == "input" and normalized == "image":
        supports = model.get("supports")
        value = supports.get("vision") if isinstance(supports, Mapping) else None
        return value if isinstance(value, bool) else None
    # The pre-profile model contract is a text completion endpoint. Other
    # modalities must not be inferred from a model name or a prose keyword.
    return True if normalized == "text" else None


def model_context_tokens(model: Mapping[str, Any]) -> int | None:
    """Do not promote a configured extension beyond the documented native limit.

    Neither declaration substitutes for live gateway admission evidence.
    """
    configured = _context_tokens(model.get("context_window"))
    documented = model.get("documented_context_tokens")
    if isinstance(documented, int) and not isinstance(documented, bool) and documented > 0:
        return min(configured, documented) if configured else documented
    return configured


def _context_class(tokens: int | None) -> str:
    if tokens is None:
        return "unspecified"
    if tokens >= 1_000_000:
        return "million-token"
    if tokens >= 200_000:
        return "very-long"
    if tokens >= 100_000:
        return "long"
    if tokens >= 32_000:
        return "medium"
    return "standard"


def _manifest_hash(raw: Mapping[str, Any]) -> str:
    payload = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _natural_identifier(raw: Mapping[str, Any]) -> str:
    identifier = str(raw.get("resource_id") or raw.get("id") or "")
    if not identifier:
        return ""
    parts = identifier.split(".")
    if len(parts) >= 3:
        parts = parts[1:-1]
    return " ".join(parts).replace("_", " ").replace("-", " ").strip()


def _valid_empirical_utility(raw: Mapping[str, Any]) -> bool:
    """Only trust counters that are backed by stored trajectories.

    Older generated manifests use successes=attempts=10 as a synthetic default.
    Such counters must not change retrieval order.
    """

    utility = raw.get("utility")
    memory = raw.get("memory")
    if not isinstance(utility, Mapping) or not isinstance(memory, Mapping):
        return False
    attempts = int(utility.get("attempts") or 0)
    if attempts <= 0:
        return False
    successes = _list(memory.get("success_trajectories"))
    failures = _list(memory.get("failure_reflections"))
    return len(successes) + len(failures) >= attempts


@dataclass(frozen=True)
class ResourceRetrievalProfile:
    resource_id: str
    resource_type: str
    capability_text: str
    soft_constraint_text: str
    hard_requirements: Dict[str, Any]
    utility_profile: Dict[str, Any]
    profile_version: str
    manifest_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def reviewed_problem_space(raw: Mapping[str, Any]) -> str:
    """Select reviewed SGAR prose without rewriting the source description."""
    cap = raw.get("capability")
    cap = cap if isinstance(cap, Mapping) else {}
    provenance = raw.get("provenance")
    review = provenance.get("semantic_review") if isinstance(provenance, Mapping) else {}
    if (resource_type(raw) == "Skill" and isinstance(review, Mapping)
            and review.get("policy") == "reviewed-skill-semantics-v2"
            and cap.get("summary")):
        return str(cap["summary"]).strip()
    return str(cap.get("problem_space") or "").strip()


def declared_task_context(raw: Mapping[str, Any]) -> str:
    """Keep declared task details in cards without generating a new summary.

    Tool summaries are often just titles; the longer declared description and
    problem space carry operational scope. Exact duplicates add no information.
    Reviewed Skill summaries continue to replace the source prose only in views.
    """
    cap = raw.get("capability")
    cap = cap if isinstance(cap, Mapping) else {}
    if resource_type(raw) in {"Tool", "Model"}:
        parts = _strings([cap.get("summary") or "", reviewed_problem_space(raw),
                          cap.get("description") or ""])
    else:
        parts = _strings([cap.get("summary") or reviewed_problem_space(raw)])
    if resource_type(raw) in {"Tool", "Agent"}:
        # Port identity stays unchanged; descriptions are prose for the planner,
        # not additions to the operation contract or its hash.
        descriptions = [f"{p.get('name') or 'input'}: {str(p['description']).strip()}"
                        for p in _input_contract(raw) if p.get("description")]
        if descriptions:
            parts.append("Input descriptions: " + "; ".join(descriptions))
    if resource_type(raw) == "Model":
        model = _type_block(raw, "model")
        for key in ("supports", "input_modalities", "output_modalities", "thinking_mode",
                    "native_protocol", "evidence_status", "gateway_verification_status"):
            if key in model:
                parts.append(key.replace("_", " ").capitalize() + ": " +
                             json.dumps(model[key], ensure_ascii=False, sort_keys=True))
        context = model_context_tokens(model)
        if context is not None:
            parts.append(f"Declared context tokens: {context}")
    if resource_type(raw) in {"Tool", "Agent", "Model"}:
        output = _output_contract(raw)
        if output:
            parts.append("Declared result: " + _format_output(output))
    return "\n".join(parts)


def declared_resource_limits(raw: Mapping[str, Any]) -> List[str]:
    """Preserve manifest-declared boundaries; never generate restrictions."""
    routing = raw.get("routing")
    con = raw.get("constraint")
    limits = _strings(routing.get("negative_intents")) if isinstance(routing, Mapping) else []
    if isinstance(con, Mapping):
        limits.extend(_strings(con.get("limitations")))
    if resource_type(raw) == "Model":
        limits.extend(_strings(_type_block(raw, "model").get("limitations")))
    if resource_type(raw) == "Skill":
        limits.extend(_strings(_type_block(raw, "skill").get("avoid_when")))
    return list(dict.fromkeys(limits))


def build_capability_text(raw: Mapping[str, Any]) -> str:
    cap = raw.get("capability")
    cap = cap if isinstance(cap, Mapping) else {}
    rtype = resource_type(raw)
    parts = [f"Resource type: {rtype}"]
    natural_name = _natural_identifier(raw)
    task_summary = str(cap.get("summary") or "").strip()
    if rtype == "Tool" and task_summary:
        # IDs are invocation identities, not evidence that a named operation is
        # implemented. Prefer the existing factual task statement for Tools.
        parts.append("Tool task: " + task_summary)
    elif natural_name and rtype != "Model":
        label = {
            "Agent": "Agent role",
            "Skill": "Skill method",
            "Tool": "Tool operation",
            "Model": "Model identity",
            "Resource": "Resource identity",
        }.get(rtype, "Resource identity")
        parts.append(f"{label}: {natural_name}")
    primitives = _strings(cap.get("core_primitives"))
    problem_space = reviewed_problem_space(raw)
    tags = _strings(cap.get("domain_tags"))
    if primitives:
        parts.append("Core capabilities: " + ", ".join(primitives))
    if problem_space:
        parts.append("Applicable problem space: " + problem_space)
    if tags:
        parts.append("Domains: " + ", ".join(tags))

    if rtype == "Model":
        model = _type_block(raw, "model")
        supports = model.get("supports") if isinstance(model.get("supports"), Mapping) else {}
        # Mapping insertion order is not semantic and differs between the
        # canonical catalog and sorted candidate-pool snapshots.  Sort keys
        # so indexed projections are byte-stable across both views.
        enabled = [str(key) for key, value in sorted(supports.items()) if value is True]
        if enabled:
            parts.append("Declared model capabilities: " + ", ".join(enabled))
        # Operational facts align with Profiler tasks; provider prestige and
        # version names are metadata, not a substitute for task suitability.
        for key, label in (("input_modalities", "Documented input modalities"),
                           ("output_modalities", "Documented output modalities")):
            if model.get(key):
                parts.append(label + ": " + ", ".join(_strings(model[key])))
        mode = model.get("thinking_mode")
        if mode and mode not in {"unknown", "supplier_alias_unverified", "alias_backend_unverified"}:
            parts.append("Documented thinking mode: " + str(mode).replace("_", " "))
    elif rtype == "Agent":
        agent = _type_block(raw, "agent")
        agent_kind = agent.get("agent_kind")
        if agent_kind:
            parts.append(f"Agent form: {agent_kind}")
    elif rtype == "Skill":
        skill = _type_block(raw, "skill")
        # Remove only exact repeated phrases within this positive document.
        # Distinct workflow steps remain intact, and raw metadata is untouched.
        primitive_keys = {" ".join(p.split()).casefold() for p in primitives}
        workflows = [p for p in _strings(skill.get("workflow_hint"))
                     if " ".join(p.split()).casefold() not in primitive_keys]
        roles = _strings(skill.get("recommended_roles"))
        if workflows:
            parts.append("Workflow guidance: " + ", ".join(workflows))
        if roles:
            parts.append("Recommended roles: " + ", ".join(roles))
    elif rtype == "Tool":
        tool = _type_block(raw, "tool")
        if tool.get("tool_kind"):
            parts.append(f"Tool kind: {tool['tool_kind']}")
        if tool.get("language"):
            parts.append(f"Implementation language: {tool['language']}")
        routing = raw.get("routing")
        routing = routing if isinstance(routing, Mapping) else {}
        routing_family = str(routing.get("family") or "").strip()
        intent_tags = _strings(routing.get("intent_tags"))
        if routing_family:
            parts.append(f"Routing family: {routing_family}")
        if intent_tags:
            parts.append("Positive routing intents: " + ", ".join(intent_tags))
        # negative_intents are deterministic exclusion rules.  Embedding them
        # in the positive capability view would increase similarity to tasks
        # the tool explicitly cannot perform.
    elif rtype == "Resource":
        affordance = raw.get("affordance")
        if isinstance(affordance, Mapping):
            can_do = _strings(affordance.get("can_do"))
            if can_do:
                parts.append("Provides: " + ", ".join(can_do))

    if rtype in {"Tool", "Agent"}:
        # Describe actual declared ports and operations, without copying the
        # negative routing intents into a positive semantic document.
        con = raw.get("constraint") if isinstance(raw.get("constraint"), Mapping) else {}
        operations = _strings(con.get("operation_kinds"))
        if operations:
            parts.append("Declared operations: " + ", ".join(operations))
        inputs = _input_contract(raw)
        output = _output_contract(raw)
        if inputs:
            parts.append("Task inputs: " + _format_inputs(inputs))
        if output:
            parts.append("Task result: " + _format_output(output))
    return "\n".join(parts)


def _base_soft_constraint_parts(raw: Mapping[str, Any]) -> List[str]:
    con = raw.get("constraint")
    con = con if isinstance(con, Mapping) else {}
    inputs = _input_contract(raw)
    output = _output_contract(raw)
    artifact_inputs = _strings(con.get("artifact_input"))
    artifact_outputs = _strings(con.get("artifact_output"))
    operation_kinds = _strings(con.get("operation_kinds"))
    parts: List[str] = []
    if inputs:
        parts.append("Accepted inputs: " + _format_inputs(inputs))
    elif artifact_inputs:
        parts.append("Accepted input artifacts: " + ", ".join(artifact_inputs))
    if output:
        parts.append("Produced output: " + _format_output(output))
    elif artifact_outputs:
        parts.append("Produced output artifacts: " + ", ".join(artifact_outputs))
    if artifact_inputs and inputs:
        parts.append("Compatible input artifacts: " + ", ".join(artifact_inputs))
    if artifact_outputs and output:
        parts.append("Compatible output artifacts: " + ", ".join(artifact_outputs))
    if operation_kinds:
        parts.append("Interaction modes: " + ", ".join(operation_kinds))
    return parts


def build_soft_constraint_text(raw: Mapping[str, Any]) -> str:
    """Build type-specific compatibility text without executable hard facts."""

    rtype = resource_type(raw)
    parts = [f"Compatibility profile for {rtype}"]
    parts.extend(_base_soft_constraint_parts(raw))

    if rtype == "Model":
        model = _type_block(raw, "model")
        supports = model.get("supports") if isinstance(model.get("supports"), Mapping) else {}
        enabled = [str(key) for key, value in sorted(supports.items()) if value is True]
        disabled = [str(key) for key, value in sorted(supports.items()) if value is False]
        context_tokens = model_context_tokens(model)
        input_modalities = _strings(model.get("input_modalities"))
        if not input_modalities:
            input_modalities = ["text"] + (["image"] if supports.get("vision") is True else [])
        output_modes = _strings(model.get("output_modalities")) or ["text"]
        if supports.get("json_mode") is True:
            output_modes.append("json")
        if supports.get("coding") is True:
            output_modes.append("code")
        parts.extend(
            [
                "Input modalities: " + ", ".join(input_modalities),
                "Output modes: " + ", ".join(output_modes),
                "Context class: " + _context_class(context_tokens),
            ]
        )
        if enabled:
            parts.append("Supported interaction features: " + ", ".join(enabled))
        if disabled:
            parts.append("Unsupported interaction features: " + ", ".join(disabled))
        if model.get("thinking_mode"):
            parts.append("Thinking mode: " + str(model["thinking_mode"]).replace("_", " "))
        if model.get("native_protocol"):
            parts.append("Documented native protocol: " + str(model["native_protocol"]))
        if model.get("limitations"):
            parts.append("Documented boundaries: " + "; ".join(_strings(model["limitations"])))
    elif rtype == "Agent":
        cap = raw.get("capability")
        cap = cap if isinstance(cap, Mapping) else {}
        problem_space = str(cap.get("problem_space") or "").strip()
        if problem_space:
            parts.append("Role and task boundary: " + problem_space)
    elif rtype == "Skill":
        skill = _type_block(raw, "skill")
        if skill.get("skill_kind"):
            parts.append(f"Instruction form: {skill['skill_kind']}")
        if skill.get("portability"):
            parts.append(f"Portable usage mode: {skill['portability']}")
        roles = _strings(skill.get("recommended_roles"))
        workflows = _strings(skill.get("workflow_hint"))
        if roles:
            parts.append("Suitable roles: " + ", ".join(roles))
        if workflows:
            parts.append("Applicable workflow stages: " + ", ".join(workflows))
        # avoid_when is intentionally absent: it is a negative deterministic cue.
    elif rtype == "Tool":
        tool = _type_block(raw, "tool")
        if tool.get("deterministic") is not None:
            parts.append(f"Deterministic operation: {bool(tool['deterministic'])}")
        if tool.get("tool_kind"):
            parts.append(f"Invocation form: {tool['tool_kind']}")
        routing = raw.get("routing")
        routing = routing if isinstance(routing, Mapping) else {}
        routing_family = str(routing.get("family") or "").strip()
        intent_tags = _strings(routing.get("intent_tags"))
        if routing_family:
            parts.append(f"Routing compatibility family: {routing_family}")
        if intent_tags:
            parts.append("Compatible task intents: " + ", ".join(intent_tags))

        constraint = raw.get("constraint")
        constraint = constraint if isinstance(constraint, Mapping) else {}
        io_signature = str(constraint.get("io_signature") or "").strip()
        accepted_inputs = _strings(constraint.get("accepted_inputs"))
        output_shape = str(constraint.get("output_shape") or "").strip()
        limitations = _strings(constraint.get("limitations"))
        if io_signature:
            parts.append("I/O contract: " + io_signature)
        if accepted_inputs:
            parts.append("Accepted input boundary: " + ", ".join(accepted_inputs))
        if output_shape:
            parts.append("Output shape: " + output_shape)
        if limitations:
            parts.append("Operational boundary: " + ", ".join(limitations))
        # routing.negative_intents stays out of the embedding and is evaluated
        # by the deterministic compatibility layer.
    elif rtype == "Resource":
        tags = raw.get("type")
        tags = tags.get("resource_tag") if isinstance(tags, Mapping) else []
        if tags:
            parts.append("Content formats: " + ", ".join(_strings(tags)))
        affordance = raw.get("affordance")
        if isinstance(affordance, Mapping):
            typical_outputs = _strings(affordance.get("typical_outputs"))
            if typical_outputs:
                parts.append("Consumable as: " + ", ".join(typical_outputs))

    if len(parts) == 1:
        legacy_signature = str(
            (raw.get("constraint") or {}).get("io_signature")
            if isinstance(raw.get("constraint"), Mapping)
            else ""
        ).strip()
        if legacy_signature:
            parts.append("Legacy I/O contract: " + legacy_signature)
    return "\n".join(parts)


def build_hard_requirements(raw: Mapping[str, Any]) -> Dict[str, Any]:
    rtype = resource_type(raw)
    con = raw.get("constraint")
    con = con if isinstance(con, Mapping) else {}
    execution = raw.get("execution")
    execution = execution if isinstance(execution, Mapping) else {}
    hard: Dict[str, Any] = {
        "status": str(raw.get("status") or "active"),
        "execution_status": str(execution.get("execution_status") or "active"),
        "runtime": execution.get("runtime"),
        "uri": execution.get("uri"),
        "environment": _strings(con.get("env_requirements")),
    }

    if rtype == "Model":
        model = _type_block(raw, "model")
        supports = model.get("supports") if isinstance(model.get("supports"), Mapping) else {}
        hard.update(
            {
                "model_id": model.get("model_id") or execution.get("model_id"),
                "provider": model.get("provider"),
                "context_tokens": model_context_tokens(model),
                "supports": dict(supports),
                "input_modalities": model.get("input_modalities"),
                "output_modalities": model.get("output_modalities"),
                "thinking_mode": model.get("thinking_mode", "unknown"),
                "native_protocol": model.get("native_protocol"),
                "evidence_status": model.get("evidence_status", "unknown"),
                "limitations": _strings(model.get("limitations")),
            }
        )
    elif rtype == "Agent":
        agent = _type_block(raw, "agent")
        hard.update(
            {
                "agent_card_uri": agent.get("agent_card_uri") or execution.get("uri"),
                "requires_selected_model": True,
            }
        )
    elif rtype == "Skill":
        skill = _type_block(raw, "skill")
        hard.update(
            {
                "portability": skill.get("portability"),
                "required_resource_ids": _strings(skill.get("required_resource_ids")),
                "reference_catalog": _list(skill.get("reference_catalog")),
                "main_file_bytes": skill.get("main_file_bytes"),
                "max_injected_bytes": (
                    skill.get("max_injected_bytes")
                    or execution.get("max_injected_bytes")
                    or 131_072
                ),
                "avoid_when": _strings(skill.get("avoid_when")),
            }
        )
    elif rtype == "Tool":
        tool = _type_block(raw, "tool")
        hard.update(
            {
                "language": tool.get("language"),
                "deterministic": tool.get("deterministic"),
                "side_effects": _strings(tool.get("side_effects")),
            }
        )
    elif rtype == "Resource":
        hard["readable_uri_required"] = True
    return hard


def build_utility_profile(raw: Mapping[str, Any]) -> Dict[str, Any]:
    utility = raw.get("utility")
    utility = utility if isinstance(utility, Mapping) else {}
    attempts = int(utility.get("attempts") or 0)
    successes = int(utility.get("successes") or 0)
    empirical = _valid_empirical_utility(raw)
    return {
        "latency_ms": float(utility.get("latency_ms") or 0.0),
        "token_cost_factor": float(utility.get("token_cost_factor") or 0.0),
        "expected_success_rate": float(utility.get("expected_success_rate") or 0.5),
        "successes": successes,
        "attempts": attempts,
        "empirical": empirical,
        "ranking_enabled": empirical,
    }


def build_constraint_profile(raw: Mapping[str, Any]) -> ResourceRetrievalProfile:
    return ResourceRetrievalProfile(
        resource_id=str(raw.get("resource_id") or raw.get("id") or ""),
        resource_type=resource_type(raw),
        capability_text=build_capability_text(raw),
        soft_constraint_text=build_soft_constraint_text(raw),
        hard_requirements=build_hard_requirements(raw),
        utility_profile=build_utility_profile(raw),
        profile_version=PROFILE_VERSION,
        manifest_hash=_manifest_hash(raw),
    )


def resolve_file_uri(uri: str | None, project_root: Path) -> Path | None:
    if not uri or not str(uri).startswith("file://"):
        return None
    raw_path = str(uri)[len("file://") :].replace("/", str(Path("/")))
    path = Path(raw_path)
    return path if path.is_absolute() else (project_root / path).resolve()


def _file_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_package_reference(main_file: Path, relative_path: str) -> Path | None:
    """Resolve a declared Skill reference without permitting package escape."""

    package_root = main_file.parent.resolve()
    candidate = (package_root / relative_path).resolve()
    try:
        candidate.relative_to(package_root)
    except ValueError:
        return None
    return candidate


def validate_resource_profiles(
    resources: Sequence[Mapping[str, Any]],
    project_root: Path,
    strict_types: Iterable[str] = ("Model", "Agent", "Skill", "Resource"),
) -> Dict[str, Any]:
    """Return a build-time audit.  The caller decides whether errors are fatal."""

    strict = set(strict_types)
    ids = [str(item.get("resource_id") or item.get("id") or "") for item in resources]
    id_set = {item for item in ids if item}
    duplicate_ids = sorted({item for item in id_set if ids.count(item) > 1})
    errors: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []

    for raw in resources:
        profile = build_constraint_profile(raw)
        rid = profile.resource_id or "<missing>"
        rtype = profile.resource_type
        target = errors if rtype in strict else warnings
        if not profile.resource_id:
            target.append({"resource_id": rid, "code": "missing_resource_id"})
            continue
        hard = profile.hard_requirements
        if str(hard.get("status") or "").lower() not in ACTIVE_STATUSES:
            continue
        if str(hard.get("execution_status") or "").lower() not in ACTIVE_STATUSES:
            target.append({"resource_id": rid, "code": "inactive_execution"})
        uri = hard.get("uri")
        if rtype in {"Agent", "Skill", "Tool", "Resource"}:
            if not uri:
                target.append({"resource_id": rid, "code": "missing_execution_uri"})
            else:
                resolved = resolve_file_uri(str(uri), project_root)
                if resolved is not None and not resolved.exists():
                    target.append({"resource_id": rid, "code": "missing_execution_file"})
        if rtype == "Model" and not hard.get("model_id"):
            target.append({"resource_id": rid, "code": "missing_model_id"})
        if rtype == "Agent":
            agent = _type_block(raw, "agent")
            card_uri = hard.get("agent_card_uri")
            if not card_uri:
                target.append({"resource_id": rid, "code": "missing_agent_card"})
            else:
                card_path = resolve_file_uri(str(card_uri), project_root)
                declared_hash = str(agent.get("agent_card_hash") or "")
                if card_path is not None and card_path.exists() and declared_hash:
                    if _file_sha256(card_path) != declared_hash:
                        target.append(
                            {"resource_id": rid, "code": "agent_card_hash_mismatch"}
                        )
            dependency_ids = set(
                _strings(agent.get("recommended_dependency_ids"))
                + _strings(agent.get("allowed_dependency_ids"))
            )
            for missing in sorted(dependency_ids - id_set):
                warnings.append(
                    {
                        "resource_id": rid,
                        "code": "missing_agent_dependency_hint",
                        "detail": missing,
                    }
                )
            routing = raw.get("routing")
            routing = routing if isinstance(routing, Mapping) else {}
            for slot in _list(routing.get("dependency_slots")):
                if not isinstance(slot, Mapping):
                    continue
                invalid_types = sorted(
                    set(_strings(slot.get("allowed_types")))
                    - {"Model", "Agent", "Tool", "Skill", "Resource", "Device"}
                )
                for invalid_type in invalid_types:
                    target.append(
                        {
                            "resource_id": rid,
                            "code": "invalid_agent_dependency_type",
                            "detail": invalid_type,
                        }
                    )
        if rtype == "Skill":
            required = set(_strings(hard.get("required_resource_ids")))
            for missing in sorted(required - id_set):
                target.append(
                    {
                        "resource_id": rid,
                        "code": "missing_required_resource",
                        "detail": missing,
                    }
                )
            size = int(hard.get("main_file_bytes") or 0)
            limit = int(hard.get("max_injected_bytes") or 131_072)
            if size > limit:
                target.append({"resource_id": rid, "code": "skill_context_budget_exceeded"})
            skill_uri = hard.get("uri")
            main_file = resolve_file_uri(str(skill_uri), project_root) if skill_uri else None
            if main_file is not None and main_file.exists():
                declared_size = int(hard.get("main_file_bytes") or 0)
                if declared_size and main_file.stat().st_size != declared_size:
                    target.append(
                        {"resource_id": rid, "code": "skill_main_file_size_mismatch"}
                    )
                for reference in _list(hard.get("reference_catalog")):
                    if not isinstance(reference, Mapping):
                        continue
                    relative_path = str(reference.get("path") or "").strip()
                    if not relative_path:
                        if reference.get("required", False):
                            target.append(
                                {
                                    "resource_id": rid,
                                    "code": "missing_skill_reference_path",
                                }
                            )
                        continue
                    resolved_reference = _resolve_package_reference(
                        main_file, relative_path
                    )
                    if resolved_reference is None:
                        target.append(
                            {
                                "resource_id": rid,
                                "code": "skill_reference_path_escape",
                                "detail": relative_path,
                            }
                        )
                    elif reference.get("required", False) and not resolved_reference.is_file():
                        target.append(
                            {
                                "resource_id": rid,
                                "code": "missing_skill_reference",
                                "detail": relative_path,
                            }
                        )

    for duplicate in duplicate_ids:
        errors.append({"resource_id": duplicate, "code": "duplicate_resource_id"})
    return {
        "profile_version": PROFILE_VERSION,
        "resource_count": len(resources),
        "errors": errors,
        "warnings": warnings,
        "valid": not errors,
    }


def deduplicate_exact_skill_packages(
    resources: Sequence[Mapping[str, Any]],
) -> tuple[List[Mapping[str, Any]], Dict[str, str]]:
    """Remove only byte-identical Skill packages from the retrieval index."""

    grouped: Dict[str, List[Mapping[str, Any]]] = {}
    passthrough: List[Mapping[str, Any]] = []
    for raw in resources:
        provenance = raw.get("provenance")
        source_hash = provenance.get("source_hash") if isinstance(provenance, Mapping) else None
        if resource_type(raw) != "Skill" or not source_hash:
            passthrough.append(raw)
            continue
        grouped.setdefault(str(source_hash), []).append(raw)

    aliases: Dict[str, str] = {}
    for items in grouped.values():
        def priority(item: Mapping[str, Any]) -> tuple[int, int, str]:
            provenance = item.get("provenance")
            provenance = provenance if isinstance(provenance, Mapping) else {}
            lifecycle = str(provenance.get("lifecycle") or "")
            lifecycle_rank = 0 if lifecycle == "active_core" else 1
            quality = -int(provenance.get("quality_score") or 0)
            return lifecycle_rank, quality, str(item.get("resource_id") or "")

        ordered = sorted(items, key=priority)
        canonical = ordered[0]
        passthrough.append(canonical)
        canonical_id = str(canonical.get("resource_id"))
        for duplicate in ordered[1:]:
            aliases[str(duplicate.get("resource_id"))] = canonical_id
    return passthrough, aliases
