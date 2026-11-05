"""Deterministic request sizing and lossless sharing of repeated resource facts."""
from copy import deepcopy
from typing import Any, Mapping

from .pipeline_control import canonical_json_bytes


def share_backing_model_facts(projection: dict[str, Any]) -> dict[str, Any]:
    """Store identical Model/Agent backing facts once, retaining a lossless reference."""
    compact = deepcopy(projection)
    table = {}
    fields = ("structured_output_capability", "generation_reliability")
    for card in compact["candidate_cards"]:
        if card["resource_type"] == "Model" and all(field in card for field in fields):
            table[card["resource_id"]] = {field:card.pop(field) for field in fields}
            card["model_execution_fact_ref"] = card["resource_id"]
    for card in compact["candidate_cards"]:
        mappings = (("backing_model_capabilities", fields[0]),
                    ("backing_model_generation_reliability", fields[1]))
        ids = set(card.get("backing_model_capabilities", {}))
        if not ids or ids != set(card.get("backing_model_generation_reliability", {})):
            continue
        if all(model_id in table and canonical_json_bytes(card[field][model_id]) == canonical_json_bytes(table[model_id][fact])
               for field,fact in mappings for model_id in ids):
            for field,_ in mappings:
                card.pop(field)
            card["backing_model_fact_refs"] = sorted(ids)
    if not table:
        return projection
    compact["model_execution_facts"] = table
    return compact if len(canonical_json_bytes(compact)) < len(canonical_json_bytes(projection)) else projection


def share_resource_cost_facts(projection: dict[str, Any]) -> dict[str, Any]:
    """Reference the existing comparison only when the complete cost profile is identical."""
    compact = deepcopy(projection)
    costs = {entry["resource_id"]: entry["cost_profile"]
             for entry in compact.get("non_model_cost_comparison", ())}
    for card in compact["candidate_cards"]:
        profile = card.get("resource_cost_profile")
        rid = card["resource_id"]
        if profile is not None and rid in costs and canonical_json_bytes(profile) == canonical_json_bytes(costs[rid]):
            card.pop("resource_cost_profile")
            card["resource_cost_profile_ref"] = rid
    return compact if len(canonical_json_bytes(compact)) < len(canonical_json_bytes(projection)) else projection


def share_model_pricing_facts(projection: dict[str, Any]) -> dict[str, Any]:
    """Keep comparison prices once, preserving all card-local pricing evidence."""
    fields = ("resource_id", "api_model_id", "input_per_m", "cache_per_m",
              "output_per_m", "pricing_unit")
    compact = deepcopy(projection)
    prices = {entry["resource_id"]: entry
              for entry in compact.get("model_cost_comparison", ())}
    changed = False
    for card in compact["candidate_cards"]:
        profile = card.get("model_pricing")
        price = prices.get(card["resource_id"])
        if (card.get("resource_type") == "Model" and isinstance(profile, Mapping)
                and price is not None and all(
                    field in profile and field in price
                    and canonical_json_bytes(profile[field]) == canonical_json_bytes(price[field])
                    for field in fields)):
            card["model_pricing"] = {key: value for key, value in profile.items() if key not in fields}
            card["model_pricing_ref"] = card["resource_id"]
            changed = True
    if not changed:
        return projection
    compact["model_pricing_reference_rule"] = {
        "table": "model_cost_comparison", "key": "resource_id", "shared_fields": list(fields),
        "rule": "Merge these referenced fields with the card-local model_pricing evidence; all prices and provenance are preserved.",
    }
    return compact if len(canonical_json_bytes(compact)) < len(canonical_json_bytes(projection)) else projection


def share_composed_context_facts(projection: dict[str, Any]) -> dict[str, Any]:
    """Share exact common option fields; retain every option and local binding."""
    options = projection.get("framework_composed_context_options", ())
    if len(options) < 2 or any(not isinstance(option, Mapping) for option in options):
        return projection
    # These identify the concrete choice and its evidence. Keep them local even
    # if a small view happens to make one identical across every option.
    local_fields = {"resource_id", "resource_type", "capability_operation_id",
                    "target_port", "option_sha256", "delivery_evidence_sha256s"}
    common = {
        key: deepcopy(value) for key, value in options[0].items()
        if key not in local_fields and all(
            key in option and canonical_json_bytes(option[key]) == canonical_json_bytes(value)
            for option in options[1:])
    }
    if not common:
        return projection
    compact = deepcopy(projection)
    compact["framework_composed_context_options"] = [
        {key: value for key, value in option.items() if key not in common}
        for option in compact["framework_composed_context_options"]
    ]
    compact["shared_composed_context_option_facts"] = common
    compact["composed_context_option_reference_rule"] = (
        "Merge shared_composed_context_option_facts into every framework_composed_context_options entry. "
        "The shared fields are identical, not defaults; local resource, operation, port, option identity "
        "and delivery evidence stay distinct. Respond with the original source IDs and wire bindings."
    )
    return compact if len(canonical_json_bytes(compact)) < len(canonical_json_bytes(projection)) else projection


def share_resource_output_facts(projection: dict[str, Any]) -> dict[str, Any]:
    """Share only byte-identical output fact pairs across resource cards.

    Resource IDs, operation eligibility, ports, bindings and all differing facts
    stay on their original cards. The table is a representation of existing
    facts, never a new output contract or a default for another resource.
    """
    from collections import defaultdict

    groups = defaultdict(list)
    for index, card in enumerate(projection.get("candidate_cards", ())):
        facts = card.get("shared_operation_output_facts")
        if isinstance(facts, Mapping):
            groups[canonical_json_bytes(facts)].append(index)
    repeated = [(encoded, indices) for encoded, indices in groups.items() if len(indices) > 1]
    if not repeated:
        return projection
    compact = deepcopy(projection)
    table = {}
    for encoded, indices in repeated:
        ref = "output_facts_" + str(len(table) + 1)
        facts = compact["candidate_cards"][indices[0]]["shared_operation_output_facts"]
        # Avoid expanding small pairs with the table and per-card reference.
        old_size = sum(len(canonical_json_bytes({"shared_operation_output_facts": facts})) for _ in indices)
        new_size = len(canonical_json_bytes({ref: facts})) + sum(
            len(canonical_json_bytes({"shared_operation_output_facts_ref": ref})) for _ in indices)
        if new_size >= old_size:
            continue
        table[ref] = deepcopy(facts)
        for index in indices:
            card = compact["candidate_cards"][index]
            card.pop("shared_operation_output_facts")
            card["shared_operation_output_facts_ref"] = ref
    if not table:
        return projection
    compact["resource_output_facts"] = table
    compact["resource_output_facts_reference_rule"] = (
        "For a card with shared_operation_output_facts_ref, read that exact entry from "
        "resource_output_facts as the card's shared_operation_output_facts, applying it to "
        "each operation on that card. These are identical existing facts, not defaults. "
        "Keep card-local eligibility, operation IDs, inputs and artifact bindings distinct."
    )
    return compact if len(canonical_json_bytes(compact)) < len(canonical_json_bytes(projection)) else projection


def compiler_request_metrics(api_kwargs: Mapping[str, Any]) -> dict[str, Any]:
    """Count actual constructed request blocks, without values, keys or Provider calls."""
    import json
    messages = api_kwargs.get("messages") or ()
    result = {"request_json_bytes": len(canonical_json_bytes(api_kwargs)),
              "response_format_bytes": len(canonical_json_bytes(api_kwargs.get("response_format") or {})),
              "message_bytes_by_role": {}}
    for message in messages:
        role = message.get("role") or "unknown"
        count = len(str(message.get("content") or "").encode("utf-8"))
        result["message_bytes_by_role"][role] = result["message_bytes_by_role"].get(role, 0) + count
    if messages:
        payload = json.loads(messages[-1]["content"])
        result["user_blocks_bytes"] = {key: len(canonical_json_bytes(value)) for key, value in payload.items()}
        compiler_input = payload.get("compiler_input", payload.get("base_compiler_input", {}))
        result["compiler_input_sections_bytes"] = {key: len(canonical_json_bytes(value))
                                                   for key, value in compiler_input.items()}
    return result


def share_resource_input_facts(projection: dict[str, Any]) -> dict[str, Any]:
    """Reference byte-identical base port contracts without dropping any IO fact."""
    from collections import defaultdict
    groups = defaultdict(list)
    for index, card in enumerate(projection.get("candidate_cards", ())):
        ports = card.get("base_input_contract")
        if isinstance(ports, list) and ports:
            groups[canonical_json_bytes(ports)].append(index)
    compact = deepcopy(projection)
    table = {}
    for encoded, indices in groups.items():
        if len(indices) < 2:
            continue
        ref = "input_ports_" + str(len(table) + 1)
        table[ref] = deepcopy(compact["candidate_cards"][indices[0]]["base_input_contract"])
        for index in indices:
            card = compact["candidate_cards"][index]
            card.pop("base_input_contract")
            card["base_input_contract_ref"] = ref
    if not table:
        return projection
    compact["resource_input_contracts"] = table
    compact["resource_input_contract_reference_rule"] = (
        "For base_input_contract_ref, read the exact base_input_contract from resource_input_contracts. "
        "All port names, types, descriptions and requirements are preserved. Operation-local contracts "
        "and bindings remain authoritative; this reference does not add ports or substitute task instructions."
    )
    return compact if len(canonical_json_bytes(compact)) < len(canonical_json_bytes(projection)) else projection
