"""JSON content semantics and declared file encoding, without rewriting bytes."""
from pathlib import PurePosixPath
from typing import Any, Mapping


def json_serialization_format(contract: Mapping[str, Any]) -> str | None:
    artifact = getattr(contract.get("artifact_type"), "value", contract.get("artifact_type"))
    interface = contract.get("interface_contract") or {}
    declared = contract.get("serialization_format") or (
        interface.get("serialization_format") if isinstance(interface, Mapping) else None)
    if declared is not None and (declared not in {"json", "jsonl"} or artifact != "json"):
        raise ValueError("json_serialization_contract_invalid")
    if artifact != "json":
        return None
    extensions = {str(contract.get("output_extension") or "").lower()}
    if contract.get("path_hint"):
        extensions.add(PurePosixPath(str(contract["path_hint"])).suffix.lower())
    required = [p for p in contract.get("produced_files", ()) if isinstance(p, Mapping)
                and p.get("required", True) and p.get("artifact_type") == "json"]
    if len(required) == 1:
        extensions.add(PurePosixPath(str(required[0].get("path_hint") or "")).suffix.lower())
    if extensions.intersection({".jsonl", ".ndjson"}):
        if declared == "json":
            raise ValueError("json_serialization_path_conflict")
        return "jsonl"
    return declared or "json"


JSONL_GENERATION_INSTRUCTION = (
    "FILE ENCODING: JSON Lines. Return one JSON record per line, without an enclosing "
    "array, Markdown, commentary, or blank records. If the content Schema is an array, "
    "it constrains the sequence of records; its items Schema constrains each line. "
    "Otherwise the Schema constrains each record. Preserve all required fields and order."
)


def json_schema_is_sequence(schema: Mapping[str, Any]) -> bool:
    """Resolve the semantic root, including schemas compiled through local refs."""
    from .model_response_contracts import _resolve_schema_ref
    if not isinstance(schema, Mapping):
        return False

    def root_types(node: Mapping[str, Any], seen: frozenset[str]) -> set[str]:
        ref = node.get("$ref")
        if isinstance(ref, str):
            if ref in seen:
                return set()
            return root_types(_resolve_schema_ref(schema, ref), seen | {ref})
        declared = node.get("type")
        if isinstance(declared, str):
            return {declared}
        if isinstance(declared, list):
            return set(declared)
        for keyword in ("anyOf", "oneOf", "allOf"):
            branches = node.get(keyword)
            if isinstance(branches, list):
                kinds = [root_types(branch, seen) for branch in branches if isinstance(branch, Mapping)]
                if keyword == "allOf":
                    kinds = [kind for kind in kinds if kind]
                return set().union(*kinds) if kinds else set()
        return set()

    types = root_types(schema, frozenset())
    return "array" in types and types <= {"array", "null"}


def serialize_json_lines(value: Any, schema: Mapping[str, Any]) -> str:
    """A declared representation adapter retaining field values and record order."""
    import json
    records = value if json_schema_is_sequence(schema) else [value]
    return "".join(json.dumps(record, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
                   + "\n" for record in records)


def parse_json_content(text: str, *, serialization_format: str, schema: Mapping[str, Any]) -> Any:
    from .model_response_contracts import strict_json_loads
    if serialization_format != "jsonl":
        return strict_json_loads(text)
    records = [strict_json_loads(line) for line in text.splitlines()]
    if json_schema_is_sequence(schema):
        return records
    if not records:
        raise ValueError("jsonl_records_missing")
    return records
