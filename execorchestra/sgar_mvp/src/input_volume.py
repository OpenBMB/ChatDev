"""Byte facts for compilation and recovery; never an input admission limit."""
from typing import Any


def workspace_data_handoff(descriptors) -> dict[str, Any] | None:
    sources = []
    for descriptor in descriptors:
        contract = descriptor.execution_contract
        if contract.get("contract_kind") != "workspace_file_inventory":
            continue
        total = contract.get("total_known_file_bytes")
        if type(total) is not int or total <= 0:
            continue
        sources.append({
            "source_id": descriptor.provenance_source_id,
            **{key: contract[key] for key in (
                "file_count", "known_size_file_count", "total_known_file_bytes",
                "largest_known_file_bytes",
            ) if key in contract},
        })
    if not sources:
        return None
    return {
        "sources": sources,
        "unit": "bytes_not_tokens",
        "producer_instruction": (
            "Specify the computation/extraction, coverage and result representation needed "
            "by the next step. Reading every byte and printing it unchanged is raw transfer, "
            "not preprocessing. Prefer native processing; generate only a missing transform."
        ),
        "consumer_instruction": (
            "Name the remaining semantic operation and bind its necessary evidence. If the "
            "input structure is unknown, inspect it before implementing a processor, using "
            "an explicit step or an authorized controller. A structural sample does not "
            "replace full-data processing or required semantic evidence."
        ),
        "coverage": (
            "Preserve originals and task/output requirements. Choose derived values, precise "
            "excerpts or supported media only when sufficient; retain full input when needed. "
            "This guides route selection, without a new size limit or mandatory model call."
        ),
    }


def controller_input_volume(spec, snapshot) -> dict[str, Any]:
    """Describe actual bound material, without copying source content into recovery."""
    rows = []
    for item in snapshot.resolved_input_descriptors:
        row = {"input_name": item.name, "content_bytes": item.content_bytes,
               "content_sha256": item.content_sha256}
        binding = spec.declared_input_bindings.get(item.name)
        if isinstance(binding, dict):
            # Only typed identity fields; never literal input data or paths.
            row.update({key: binding[key] for key in (
                "source_kind", "step_id", "from_step", "output_key", "source_id")
                        if isinstance(binding.get(key), str)})
        rows.append(row)
    rows.sort(key=lambda row: (-row["content_bytes"], row["input_name"]))
    return {"unit": "bytes_not_tokens", "input_count": len(rows),
            "total_content_bytes": sum(row["content_bytes"] for row in rows),
            "largest_inputs": rows[:4], "listed_input_count": min(4, len(rows)),
            "full_inputs_preserved": True}
