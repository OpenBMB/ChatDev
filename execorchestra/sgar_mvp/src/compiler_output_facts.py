"""Compiler-visible output facts; only the existing realizer grants authority."""
from typing import Any, Mapping
from .output_realization import contract_schema, normalized_artifact_type
from .pipeline_control import canonical_sha256

OUTPUT_FACTS_PROTOCOL = "sgar-compiler-output-facts-v1"
CONVERSION_REQUIREMENTS = {
    "identity": "Same representation; JSON requires matching declared machine schemas.",
    "manifest_payload_extract": "Explicit manifest payload path and matching semantic output contract.",
    "json_object_project": "Declared source/target object schemas, matching retained properties and guaranteed required fields; the existing projection validator must accept them.",
    "json_object_wrap": "One required target property whose schema matches the source schema or declared textual representation.",
    "lossless_serialize": "Supported JSON or textual source serialized to plaintext or file; no semantic transformation.",
}


def output_contract_facts(contract: Mapping[str, Any]) -> dict[str, Any]:
    from .model_response_contracts import require_semantic_json_schema, ModelResponseContractError
    artifact_type = normalized_artifact_type(contract.get("artifact_type")) or None
    candidates = [contract[k] for k in ("schema_hint", "json_schema", "schema") if isinstance(contract.get(k), Mapping)]
    schema = contract_schema(contract)
    status = "missing" if artifact_type == "json" else "not_declared"
    if any(contract.get(k) is not None and not isinstance(contract[k], Mapping) for k in ("json_schema", "schema")):
        status = "invalid"
    elif len({canonical_sha256(dict(v)) for v in candidates}) > 1:
        status = "conflicting"
    elif schema is not None:
        try:
            require_semantic_json_schema(schema)
            status = "available"
        except ModelResponseContractError:
            status = "invalid"
    elif isinstance(contract.get("schema_hint"), str):
        status = "descriptive_only"
    return {"artifact_type": artifact_type, "machine_schema_status": status,
            "schema": dict(schema) if schema is not None else None}


def compiler_output_capabilities(native: Mapping[str, Any], resource_type: str) -> dict[str, Any]:
    semantic = native.get("semantic_output")
    semantic_fact = None
    if isinstance(semantic, Mapping):
        semantic_fact = {**output_contract_facts(semantic), "payload_path": semantic.get("payload_path")}
    return {"protocol": OUTPUT_FACTS_PROTOCOL,
            "output_behavior": "contract_generating" if resource_type in {"Model", "Agent"} else "declared_runtime_output",
            "native": output_contract_facts(native), "semantic": semantic_fact,
            "final_step_eligibility_scope": "Candidate selection only; the selected concrete contract must pass executability validation.",
            "concrete_contract_status": "pending_validation",
            "conversion_rules_ref": "output_conversion_rules in this compiler input",
            "compiler_schema_changes_native_output": False}


def explain_output_rejection(native: Mapping[str, Any], target: Mapping[str, Any], proof: Any) -> dict[str, Any]:
    """Explain an already rejected proof, without authorizing execution."""
    if proof.compatibility in {"exact", "deterministically_convertible"}:
        raise ValueError("output_rejection_requires_failed_proof")
    facts = compiler_output_capabilities(native, "Resource")
    target_facts = output_contract_facts(target)
    reasons = []
    if proof.reason_code in {"representation_contract_artifact_type_missing", "manifest_semantic_payload_path_missing"}:
        reasons.append(proof.reason_code)
    views = [facts["native"]]
    if facts["semantic"] and facts["semantic"].get("payload_path"):
        views.append(facts["semantic"])
    matching = [v for v in views if v["artifact_type"] == target_facts["artifact_type"]]
    if not matching:
        reasons.append("source_target_representation_mismatch")
    for view in matching:
        if view["artifact_type"] != "json":
            continue
        if view["machine_schema_status"] != "available":
            reasons.append("source_machine_schema_" + view["machine_schema_status"])
            continue
        ss, ts = view["schema"], target_facts["schema"]
        if not isinstance(ts, Mapping):
            reasons.append("target_machine_schema_unavailable")
        elif ss.get("type") != ts.get("type"):
            reasons.append("source_target_schema_type_mismatch")
        elif ss.get("type") == "object" and isinstance(ss.get("properties"), Mapping) and isinstance(ts.get("properties"), Mapping):
            sp, tp = ss["properties"], ts["properties"]
            if set(tp) - set(sp):
                reasons.append("target_properties_not_declared_by_source")
            if set(ts.get("required") or ()) - set(ss.get("required") or ()):
                reasons.append("target_required_fields_not_guaranteed")
            if any(sp[k] != tp[k] for k in set(sp) & set(tp)) or not reasons:
                reasons.append("target_constraints_not_guaranteed_by_supported_conversion")
        else:
            reasons.append("target_constraints_not_guaranteed_by_supported_conversion")
    reasons.append("explicit_processing_required")
    return {"protocol": OUTPUT_FACTS_PROTOCOL, "source": facts, "target": dict(target),
            "compatibility": proof.compatibility, "proof_reason": proof.reason_code,
            "reason_codes": list(dict.fromkeys(reasons)),
            "next_actions": ["The current local comparison/conversions did not prove this target; this does not mean the resource lacks task capability. Select a compatible declared output view without requiring verbatim schema annotations.",
                             "Select authorized explicit processing or a controller with declared callable tools and bound inputs.",
                             "Report concrete insufficiency if no authorized executable composition exists; preserve task requirements."]}


def compiler_response_path(path, proposal):
    """Map lowering fields to response fields without interpreting task text."""
    proposal = proposal.get("plan_decision", proposal)
    path = tuple(path)
    if len(path) < 2 or path[0] != "steps":
        return path
    try:
        index = int(path[1]); step = proposal.get("steps", [])[index]
    except (ValueError, TypeError, IndexError):
        return path
    if len(path) < 3:
        return ("steps", index)
    field = path[2]
    if field in {"expected_output_contract", "output_contract"}:
        if step.get("output_role") == "final":
            return ("final_contract",)
        if step.get("output_role") == "intermediate":
            return ("steps", index, "intermediate_contract")
        return ("steps", index, "output_role")
    field = {"input_bindings": "input_mappings", "operation_kind": "capability_operation_id", "entrypoint_id": "capability_operation_id"}.get(field, field)
    if field == "input_mappings" and len(path) > 3 and isinstance(path[3], str):
        for i, binding in enumerate(step.get("input_mappings", [])):
            if binding.get("target_port") == path[3]:
                return ("steps", index, field, i)
        return ("steps", index, field)
    return ("steps", index, field, *path[3:])
