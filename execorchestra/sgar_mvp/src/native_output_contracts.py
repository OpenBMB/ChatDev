"""Explicit native representation contracts, separate from task semantics."""
from collections.abc import Mapping
from typing import Any
from .model_response_contracts import canonicalize_json_schema, require_semantic_json_schema

JSON_VALUE_SCHEMA = {
    'description': 'Native JSON representation only; no field or task-delivery guarantee.',
    'type': ['object', 'array', 'string', 'number', 'boolean', 'null'],
}

def native_json_value_only(contract: Mapping[str, Any]) -> bool:
    if contract.get('native_json_contract_scope') != 'value_only':
        return False
    schemas = [contract[k] for k in ('schema_hint', 'json_schema', 'schema')
               if isinstance(contract.get(k), Mapping)]
    return bool(schemas) and all(dict(schema) == JSON_VALUE_SCHEMA for schema in schemas)

def require_native_json_schema(contract: Mapping[str, Any], schema: Mapping[str, Any]) -> dict:
    if native_json_value_only(contract):
        return canonicalize_json_schema(schema)
    return require_semantic_json_schema(schema)
