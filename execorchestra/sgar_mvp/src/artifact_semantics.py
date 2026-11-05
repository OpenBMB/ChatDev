"""Artifact purpose and local schema-document syntax, separate from execution support."""
from collections.abc import Mapping
import json
import re
import subprocess
import sys
from typing import Any

from .text_format_contract import text_format_from_contract

_TYPES = {"null", "boolean", "object", "array", "number", "integer", "string"}
_MAPS = {"properties", "patternProperties", "$defs", "definitions", "dependentSchemas"}
_SINGLE = {"additionalProperties", "unevaluatedProperties", "contains", "additionalItems",
           "unevaluatedItems", "propertyNames", "not", "if", "then", "else"}
_LISTS = {"allOf", "anyOf", "oneOf", "prefixItems"}
_COUNTS = {"minLength", "maxLength", "minItems", "maxItems", "minProperties", "maxProperties", "minContains", "maxContains"}
_NUMBERS = {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf"}
_STRINGS = {"$schema", "$id", "$ref", "$dynamicRef", "$anchor", "$dynamicAnchor", "$comment", "title", "description", "format", "pattern", "contentEncoding", "contentMediaType"}
_KNOWN = _MAPS | _SINGLE | _LISTS | _COUNTS | _NUMBERS | _STRINGS | {
    "type", "required", "enum", "const", "items", "uniqueItems", "default", "examples",
    "readOnly", "writeOnly", "deprecated", "dependentRequired", "dependencies", "$vocabulary", "contentSchema"}


def require_artifact_semantics(*, content_kind: str, artifact_type: Any, schema: Any) -> None:
    if content_kind not in {"value", "json_schema_document"}:
        raise ValueError("artifact_content_kind_unknown")
    if content_kind == "json_schema_document" and artifact_type != "json":
        raise ValueError("schema_document_requires_json_artifact")
    # The outer shape cannot prove what a document means. Actual document syntax
    # and task semantics are checked after generation, not guessed from keywords.


def inspect_schema_document(value: Any) -> dict[str, Any]:
    """Check known keyword syntax without executing or fetching references.

    This is deliberately not a full dialect validator. Uncovered features are
    reported separately; their presence is not evidence of invalidity.
    """
    errors: list[str] = []
    uncovered: set[str] = set()
    def strings(v: Any) -> bool:
        return isinstance(v, list) and all(isinstance(x, str) for x in v) and len(v) == len(set(v))
    def visit(node: Any, path: str, depth: int = 0) -> None:
        if isinstance(node, bool):
            return
        if not isinstance(node, Mapping):
            errors.append(path + ":schema_must_be_object_or_boolean")
            return
        if depth > 64:
            uncovered.add("nesting_beyond_local_check_limit")
            return
        for key, val in node.items():
            loc = path + "." + key
            if key not in _KNOWN:
                uncovered.add("keyword:" + key)
            if key == "$schema":
                uncovered.add("dialect_specific_rules")
            if key in {"$ref", "$dynamicRef", "$vocabulary", "format", "pattern", "dependencies", "contentSchema"}:
                uncovered.add("semantic_feature:" + key)
            if key in _STRINGS and not isinstance(val, str):
                errors.append(loc + ":expected_string")
            elif key == "type":
                types = [val] if isinstance(val, str) else val
                if not strings(types) or not types or any(t not in _TYPES for t in types):
                    errors.append(loc + ":invalid_type")
            elif key == "required" and not strings(val):
                errors.append(loc + ":expected_unique_strings")
            elif key == "enum":
                if not isinstance(val, list) or not val:
                    errors.append(loc + ":expected_nonempty_array")
            elif key in _COUNTS and (type(val) is not int or val < 0):
                errors.append(loc + ":expected_nonnegative_integer")
            elif key in _NUMBERS:
                if key in {"exclusiveMinimum", "exclusiveMaximum"} and isinstance(val, bool):
                    uncovered.add("legacy_exclusive_bound_dialect")
                elif type(val) not in {int, float} or (key == "multipleOf" and val <= 0):
                    errors.append(loc + ":invalid_numeric_bound")
            elif key in {"uniqueItems", "readOnly", "writeOnly", "deprecated"} and not isinstance(val, bool):
                errors.append(loc + ":expected_boolean")
            elif key in _MAPS:
                if not isinstance(val, Mapping):
                    errors.append(loc + ":expected_object")
                else:
                    for name, child in val.items(): visit(child, loc + "." + name, depth + 1)
            elif key in _SINGLE or key == "contentSchema":
                visit(val, loc, depth + 1)
            elif key in _LISTS:
                if not isinstance(val, list) or not val:
                    errors.append(loc + ":expected_nonempty_array")
                else:
                    for i, child in enumerate(val): visit(child, loc + "[" + str(i) + "]", depth + 1)
            elif key == "items":
                if isinstance(val, list):
                    uncovered.add("legacy_tuple_items_dialect")
                    for i, child in enumerate(val): visit(child, loc + "[" + str(i) + "]", depth + 1)
                else: visit(val, loc, depth + 1)
            elif key == "dependentRequired":
                if not isinstance(val, Mapping) or any(not strings(v) for v in val.values()):
                    errors.append(loc + ":expected_string_array_map")
    visit(value, "$")
    return {"status": "invalid" if errors else "partial" if uncovered else "checked",
            "coverage": "known_keyword_syntax_only", "errors": errors,
            "uncovered_features": sorted(uncovered), "references_fetched": False}


def validate_schema_document(value: Any) -> bool:
    return inspect_schema_document(value)["status"] != "invalid"


_REGEX_PROBE_CHILD = r"""
import json, re, sys
payload = json.load(sys.stdin)
pattern = re.compile(payload["pattern"], re.MULTILINE)
actual = [re.findall(pattern, item["input_text"]) for item in payload["probes"]]
json.dump(actual, sys.stdout, ensure_ascii=False)
"""


def _utf8_preview(value: Any, byte_limit: int) -> str:
    return str(value).encode("utf-8", errors="replace")[:byte_limit].decode(
        "utf-8", errors="ignore"
    )


def _regex_probe_mismatch_diagnostic(
    *, probe_index: int, probe: Mapping[str, Any], actual: Any
) -> str:
    """Expose one bounded public counterexample without echoing probe inputs."""
    expected = probe["expected_matches"]
    actual_values = actual if isinstance(actual, list) else [actual]
    detail = {
        "probe_index": probe_index,
        "requirement_quote": _utf8_preview(probe["requirement_quote"], 96),
        "expected_match_count": len(expected),
        "expected_preview": [_utf8_preview(value, 32) for value in expected[:2]],
        "actual_match_count": len(actual_values),
        "actual_preview": [_utf8_preview(value, 32) for value in actual_values[:2]],
    }
    encoded = json.dumps(detail, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(encoded.encode("utf-8")) <= 768:
        return encoded
    # Pathological control-character escaping must not create an unbounded prompt.
    return json.dumps(
        {
            "probe_index": probe_index,
            "expected_match_count": len(expected),
            "actual_match_count": len(actual_values),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _validate_regex_acceptance_probes(pattern: str, probes: Any) -> dict[str, Any] | None:
    """Run bounded public examples in a separate interpreter before file writes."""
    if not probes:
        return None
    if not isinstance(probes, list) or len(probes) > 4:
        raise OutputContractViolation("artifact_python_regex_probe_contract_invalid")
    for probe in probes:
        if (
            not isinstance(probe, Mapping)
            or probe.get("protocol") != "sgar-regex-findall-acceptance-probe-v1"
            or not isinstance(probe.get("input_text"), str)
            or len(probe["input_text"]) > 2048
            or not isinstance(probe.get("expected_matches"), list)
            or len(probe["expected_matches"]) > 32
            or any(not isinstance(value, str) for value in probe["expected_matches"])
            or not isinstance(probe.get("requirement_quote"), str)
            or not probe["requirement_quote"].strip()
        ):
            raise OutputContractViolation("artifact_python_regex_probe_contract_invalid")
    payload = json.dumps({"pattern": pattern, "probes": probes}, ensure_ascii=False)
    try:
        result = subprocess.run(
            [sys.executable, "-I", "-c", _REGEX_PROBE_CHILD],
            input=payload, text=True, capture_output=True, timeout=3, check=False,
        )
    except subprocess.TimeoutExpired:
        raise OutputContractViolation("artifact_python_regex_probe_timeout") from None
    except OSError:
        raise OutputContractViolation("artifact_python_regex_probe_execution_failed") from None
    if result.returncode != 0:
        raise OutputContractViolation("artifact_python_regex_probe_execution_failed")
    try:
        actual = json.loads(result.stdout)
    except ValueError:
        raise OutputContractViolation("artifact_python_regex_probe_execution_failed") from None
    if not isinstance(actual, list) or len(actual) != len(probes):
        raise OutputContractViolation("artifact_python_regex_probe_execution_failed")
    for probe_index, (got, probe) in enumerate(zip(actual, probes)):
        if got != probe["expected_matches"]:
            raise OutputContractViolation(
                "artifact_python_regex_acceptance_probe_failed",
                diagnostic=_regex_probe_mismatch_diagnostic(
                    probe_index=probe_index, probe=probe, actual=got
                ),
            )
    return {"status": "pass", "kind": "python_regex_findall", "probes_checked": len(probes)}


class OutputContractViolation(ValueError):
    def __init__(self, failure_code: str, *, diagnostic: str | None = None):
        super().__init__(failure_code)
        self.failure_code = failure_code
        self.diagnostic = diagnostic


def is_output_contract_echo(content: str, contract: Mapping[str, Any]) -> bool:
    """Detect a control envelope returned in place of a non-JSON artifact.

    A JSON object is valid task data when the declared artifact is JSON. For a
    text artifact, an object containing only our output-contract metadata and
    repeating the declared type/kind is the contract, not the requested value.
    """
    if contract.get("artifact_type") == "json" or contract.get("content_kind", "value") != "value":
        return False
    try:
        value = json.loads(content)
    except (TypeError, ValueError):
        return False
    if not isinstance(value, dict):
        return False
    keys = set(value)
    metadata_keys = {
        "artifact_type", "content_kind", "output_extension", "description",
        "required_content", "grounding_requirements", "acceptance_criteria",
        "acceptance_probes", "syntax_validator", "produced_files",
        "interface_contract", "schema_hint", "json_schema",
    }
    return (
        {"artifact_type", "content_kind"} <= keys <= metadata_keys
        and value["artifact_type"] == contract.get("artifact_type")
        and value["content_kind"] == contract.get("content_kind", "value")
    )


def requires_content_contract_validation(contract: Mapping[str, Any]) -> bool:
    interface = contract.get("interface_contract")
    return (
        contract.get("artifact_type") == "json"
        or contract.get("syntax_validator") is not None
        or (isinstance(interface, Mapping) and interface.get("text_format") is not None)
    )


def _validate_text_format(content: bytes, contract: Mapping[str, Any]) -> dict[str, Any] | None:
    try:
        text_format = text_format_from_contract(contract)
    except ValueError:
        raise OutputContractViolation("artifact_text_format_contract_invalid") from None
    if text_format is None:
        return None
    try:
        text = content.decode("utf-8", errors="strict")
    except UnicodeError:
        raise OutputContractViolation("artifact_text_format_utf8_invalid") from None
    # Keep untrusted generated regexes out of the long-lived control process.
    # This is a local validation bound, not a task or generation timeout.
    child = "import json,re,sys; p=json.load(sys.stdin); print(json.dumps(re.fullmatch(p['pattern'],p['text']) is not None))"
    try:
        result = subprocess.run([sys.executable, "-I", "-c", child],
            input=json.dumps({"pattern": text_format.fullmatch_pattern, "text": text}),
            text=True, capture_output=True, timeout=3, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise OutputContractViolation("artifact_text_format_validation_unavailable") from None
    if result.returncode != 0 or result.stdout.strip() not in {"true", "false"}:
        raise OutputContractViolation("artifact_text_format_validation_unavailable")
    if result.stdout.strip() != "true":
        raise OutputContractViolation("artifact_text_format_mismatch")
    return {"status": "pass", "coverage": "declared_fullmatch_only", "output_rewritten": False}


def validate_output_contract_content(content: bytes, contract: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the delivered bytes against declared local content constraints."""
    from .model_response_contracts import strict_json_loads, validate_json_schema_instance, local_json_schema_support
    report: dict[str, Any] = {"status": "pass", "document_validation": {}}
    text_format_report = _validate_text_format(content, contract)
    if text_format_report is not None:
        report["text_format_validation"] = text_format_report
    syntax_validator = contract.get("syntax_validator")
    if syntax_validator not in (None, "python_regex", "python_regex_findall_string", "python_regex_findall_whole_match"):
        raise OutputContractViolation("artifact_syntax_validator_unsupported")
    if syntax_validator is not None:
        if contract.get("artifact_type") != "plaintext":
            raise OutputContractViolation("artifact_python_regex_type_invalid")
        try:
            pattern = content.decode("utf-8")
        except UnicodeError:
            raise OutputContractViolation("artifact_python_regex_utf8_invalid") from None
        if not pattern.strip() or len(content) > 65536:
            raise OutputContractViolation("artifact_python_regex_size_invalid")
        try:
            compiled = re.compile(pattern, re.MULTILINE)
        except re.error:
            raise OutputContractViolation("artifact_python_regex_syntax_invalid") from None
        if syntax_validator == "python_regex_findall_whole_match" and compiled.groups:
            raise OutputContractViolation("artifact_python_regex_captures_forbidden")
        if syntax_validator == "python_regex_findall_string" and compiled.groups > 1:
            raise OutputContractViolation("artifact_python_regex_findall_tuple_forbidden")
        acceptance_report = _validate_regex_acceptance_probes(
            pattern, contract.get("acceptance_probes")
        )
        if acceptance_report is not None:
            report["acceptance_probe_validation"] = acceptance_report
        report["syntax_validation"] = {
            "kind": syntax_validator, "status": "pass", "engine": "python_re",
            "coverage": (
                "compile_and_findall_whole_match_shape"
                if syntax_validator == "python_regex_findall_whole_match"
                else "compile_and_findall_string_shape"
                if syntax_validator == "python_regex_findall_string"
                else "compile_only"
            ),
        }
    if syntax_validator is None and contract.get("acceptance_probes"):
        raise OutputContractViolation("artifact_python_regex_probe_contract_invalid")
    if contract.get("artifact_type") != "json":
        try:
            text = content.decode("utf-8")
        except UnicodeError:
            text = ""
        if is_output_contract_echo(text, contract):
            raise OutputContractViolation("artifact_output_contract_echo")
        return report  # Other formats retain their existing descriptor/interface checks.
    schema = contract.get("json_schema", contract.get("schema_hint"))
    from .json_serialization import json_serialization_format, json_schema_is_sequence, parse_json_content
    try:
        encoding = json_serialization_format(contract)
        value = parse_json_content(content.decode("utf-8"), serialization_format=encoding,
                                   schema=schema if isinstance(schema, Mapping) else {})
    except (ValueError, UnicodeError):
        raise OutputContractViolation("artifact_json_invalid") from None
    if schema is None:
        raise OutputContractViolation("artifact_execution_schema_missing")
    if not isinstance(schema, Mapping):
        raise OutputContractViolation("artifact_execution_schema_unsupported")
    supported, _ = local_json_schema_support(schema)
    if not supported:
        raise OutputContractViolation("artifact_execution_schema_unsupported")
    instances = value if encoding == "jsonl" and not json_schema_is_sequence(schema) else [value]
    for instance in instances:
        valid, reason = validate_json_schema_instance(instance, schema)
        if not valid:
            raise OutputContractViolation("artifact_execution_schema_mismatch:" + str(reason))
    if encoding == "jsonl":
        report["serialization_validation"] = {"format": "jsonl", "records": len(value), "output_rewritten": False}
    if contract.get("content_kind", "value") == "json_schema_document":
        report["document_validation"] = inspect_schema_document(value)
        if report["document_validation"]["status"] == "invalid":
            raise OutputContractViolation("artifact_schema_document_invalid")
    return report


def validate_delivery_content(
    content: bytes,
    execution_contract: Mapping[str, Any],
    macro_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Check both declared structures against the same bytes, never schema hashes."""
    from .json_serialization import json_serialization_format
    encoding = json_serialization_format(macro_contract)
    effective = dict(execution_contract)
    if encoding == "jsonl" and effective.get("artifact_type") == "json":
        effective["serialization_format"] = "jsonl"
    report = validate_output_contract_content(content, effective)
    macro_format = (macro_contract.get("interface_contract") or {}).get("text_format")
    execution_format = (execution_contract.get("interface_contract") or {}).get("text_format")
    if macro_format is not None:
        if macro_format != execution_format:
            try:
                _validate_text_format(content, macro_contract)
            except OutputContractViolation as exc:
                raise OutputContractViolation("artifact_macro_requirement_conflict:" + exc.failure_code) from None
        report["explicit_macro_text_format"] = "pass"
    macro_schema = macro_contract.get("json_schema")
    if execution_contract.get("artifact_type") == "json" and macro_schema is not None:
        if macro_schema != execution_contract.get("json_schema", execution_contract.get("schema_hint")):
            try:
                validate_output_contract_content(content, macro_contract)
            except OutputContractViolation as exc:
                raise OutputContractViolation("artifact_macro_requirement_conflict:" + exc.failure_code) from None
        report["explicit_macro_structure"] = "pass"
    return report


def check_bound_schema_content(content: bytes, schema_content: str, *, serialization_format: str = "json") -> dict[str, Any]:
    """Check one explicit validation document; never infer bindings or fetch refs."""
    from .model_response_contracts import strict_json_loads, local_json_schema_support, validate_json_schema_instance
    report: dict[str, Any] = {"coverage": "supported_local_schema_subset", "references_fetched": False}
    try:
        schema = strict_json_loads(schema_content)
    except (ValueError, UnicodeError):
        return {**report, "status": "unknown", "reason": "bound_schema_json_invalid"}
    syntax = inspect_schema_document(schema)
    if syntax["status"] == "invalid":
        return {**report, "status": "unknown", "reason": "bound_schema_syntax_invalid", "details": syntax["errors"]}
    # Ref resolution and format/dialect extensions outside our local subset must
    # not become false machine proofs. Values inside const/enum are plain data.
    limitations = set(syntax["uncovered_features"]) - {"dialect_specific_rules", "semantic_feature:$ref"}
    def inspect(node: Any) -> None:
        if isinstance(node, bool):
            return
        dialect = node.get("$schema")
        if dialect is not None and dialect not in {
            "https://json-schema.org/draft/2020-12/schema", "https://json-schema.org/draft/2019-09/schema",
            "http://json-schema.org/draft-07/schema#",
        }:
            limitations.add("unsupported_dialect")
        for keyword in ("$id", "$anchor", "format"):
            if keyword in node:
                limitations.add("uncovered_semantics:" + keyword)
        if "$ref" in node and set(node) - {"$ref", "$defs", "definitions", "$schema", "title", "description", "$comment"}:
            limitations.add("ref_sibling_constraints")
        for key, value in node.items():
            if key in _MAPS:
                for child in value.values(): inspect(child)
            elif key in _SINGLE or key == "contentSchema": inspect(value)
            elif key in _LISTS:
                for child in value: inspect(child)
            elif key == "items":
                for child in value if isinstance(value, list) else [value]: inspect(child)
    try:
        inspect(schema)
        supported, reasons = local_json_schema_support(schema, allow_boolean=True)
        limitations.update(reasons)
    except (ValueError, TypeError, RecursionError):
        return {**report, "status": "unknown", "reason": "bound_schema_outside_local_support"}
    if not supported or limitations:
        return {**report, "status": "unknown", "reason": "bound_schema_outside_local_support", "details": sorted(limitations)}
    try:
        from .json_serialization import parse_json_content, json_schema_is_sequence
        value = parse_json_content(content.decode("utf-8"), serialization_format=serialization_format, schema=schema)
    except (ValueError, UnicodeError):
        return {**report, "status": "fail", "reason": "bound_schema_instance_json_invalid"}
    try:
        instances = value if serialization_format == "jsonl" and not json_schema_is_sequence(schema) else [value]
        valid, reason = True, None
        for instance in instances:
            valid, reason = validate_json_schema_instance(instance, schema)
            if not valid:
                break
    except (ValueError, TypeError, RecursionError):
        return {**report, "status": "unknown", "reason": "bound_schema_outside_local_support"}
    return {**report, "status": "pass" if valid else "fail", "reason": reason}
