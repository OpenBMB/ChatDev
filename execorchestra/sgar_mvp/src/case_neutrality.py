"""Case-neutrality audit for production framework source.

The audit rejects hard-coded request/case identity branching and exact
invocation-derived literals without persisting the inspected values.  Generic
query and capability classification remains outside this boundary because it
does not bind execution to one request identity.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .pipeline_control import canonical_sha256


CASE_NEUTRALITY_AUDIT_PROTOCOL = "sgar-case-neutrality-audit-v2"
_SENSITIVE_IDENTIFIERS = frozenset({"request_id", "case_id", "case_name"})
_STRING_MATCH_METHODS = frozenset(
    {"startswith", "endswith", "find", "index", "rfind", "rindex"}
)
_REGEX_MATCH_METHODS = frozenset({"match", "fullmatch", "search"})
_INPUT_SELECTOR_IDENTIFIERS = frozenset({"logical_name", "source_name"})
_INPUT_COLLECTION_TOKENS = frozenset({"input", "inputs"})
_INPUT_SELECTOR_SHAPE_TOKENS = frozenset(
    {"map", "mapping", "name", "names", "selector"}
)
_RESOURCE_TOKENS = frozenset(
    {"adapter", "candidate", "executor", "model", "provider", "resource", "tool"}
)
_SELECTION_TOKENS = frozenset({"choose", "resolve", "route", "select"})


def _production_source_paths(root: Path) -> tuple[Path, ...]:
    paths = [root / "sgar_mvp" / "main.py", root / "sgar_mvp" / "real_case_batch.py"]
    paths.extend(sorted((root / "sgar_mvp" / "src").glob("*.py")))
    return tuple(sorted({path.resolve() for path in paths if path.is_file()}))


def _identifier_is_sensitive(value: str) -> bool:
    normalized = str(value or "").strip().casefold()
    return any(
        normalized == item or normalized.endswith("_" + item)
        for item in _SENSITIVE_IDENTIFIERS
    )


def _contains_sensitive_selector(node: ast.AST) -> bool:
    for item in ast.walk(node):
        if isinstance(item, ast.Name) and _identifier_is_sensitive(item.id):
            return True
        if isinstance(item, ast.Attribute) and _identifier_is_sensitive(item.attr):
            return True
        if (
            isinstance(item, ast.Call)
            and isinstance(item.func, ast.Attribute)
            and item.func.attr == "get"
            and item.args
            and isinstance(item.args[0], ast.Constant)
            and isinstance(item.args[0].value, str)
            and _identifier_is_sensitive(item.args[0].value)
        ):
            return True
        if (
            isinstance(item, ast.Subscript)
            and isinstance(item.slice, ast.Constant)
            and isinstance(item.slice.value, str)
            and _identifier_is_sensitive(item.slice.value)
        ):
            return True
    return False


def _contains_match_literal(node: ast.AST) -> bool:
    return any(
        isinstance(item, ast.Constant)
        and isinstance(item.value, str)
        and not _identifier_is_sensitive(item.value)
        for item in ast.walk(node)
    )


def _control_flow_findings(tree: ast.AST, *, locator: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        finding_kind = ""
        if isinstance(node, ast.Compare):
            operands = (node.left, *node.comparators)
            if any(
                (
                    _contains_sensitive_selector(left)
                    and _contains_match_literal(right)
                )
                or (
                    _contains_sensitive_selector(right)
                    and _contains_match_literal(left)
                )
                for left, right in zip(operands, operands[1:])
            ):
                finding_kind = "identity_literal_comparison"
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if (
                node.func.attr in _STRING_MATCH_METHODS
                and _contains_sensitive_selector(node.func.value)
                and any(_contains_match_literal(argument) for argument in node.args)
            ):
                finding_kind = "identity_string_match"
            elif (
                node.func.attr in _REGEX_MATCH_METHODS
                and any(_contains_sensitive_selector(argument) for argument in node.args)
                and any(_contains_match_literal(argument) for argument in node.args)
            ):
                finding_kind = "identity_regex_match"
        elif isinstance(node, ast.Match) and _contains_sensitive_selector(node.subject):
            if any(_contains_match_literal(case.pattern) for case in node.cases):
                finding_kind = "identity_literal_match"
        if finding_kind:
            findings.append(
                {
                    "locator": locator,
                    "line": int(getattr(node, "lineno", 0)),
                    "finding_kind": finding_kind,
                }
            )
    return findings


def _identifier_tokens(value: str) -> frozenset[str]:
    snake_case = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(value or ""))
    return frozenset(
        token.casefold()
        for token in re.split(r"[^A-Za-z0-9]+", snake_case)
        if token
    )


def _identifier_is_input_selector(value: str) -> bool:
    snake_case = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(value or ""))
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", snake_case).strip("_").casefold()
    return any(
        normalized == selector
        or normalized.startswith(selector + "_")
        or normalized.endswith("_" + selector)
        for selector in _INPUT_SELECTOR_IDENTIFIERS
    )


def _node_has_explicit_input_selector(node: ast.AST) -> bool:
    """Return whether an AST surface explicitly addresses an input selector.

    Content containers such as ``payload``, ``row`` and ``record`` are
    intentionally excluded.  Their field names belong to the attachment data
    namespace and must never become invocation-derived source literals.
    """

    for item in ast.walk(node):
        if isinstance(item, ast.Name):
            tokens = _identifier_tokens(item.id)
            if _identifier_is_input_selector(item.id) or (
                tokens & _INPUT_COLLECTION_TOKENS
                and tokens & _INPUT_SELECTOR_SHAPE_TOKENS
            ):
                return True
        if isinstance(item, ast.Attribute):
            tokens = _identifier_tokens(item.attr)
            if _identifier_is_input_selector(item.attr) or (
                tokens & _INPUT_COLLECTION_TOKENS
                and tokens & _INPUT_SELECTOR_SHAPE_TOKENS
            ):
                return True
        if (
            isinstance(item, ast.Call)
            and isinstance(item.func, ast.Attribute)
            and item.func.attr == "get"
            and item.args
            and isinstance(item.args[0], ast.Constant)
            and isinstance(item.args[0].value, str)
            and _identifier_is_input_selector(item.args[0].value)
        ):
            return True
        if (
            isinstance(item, ast.Subscript)
            and isinstance(item.slice, ast.Constant)
            and isinstance(item.slice.value, str)
            and _identifier_is_input_selector(item.slice.value)
        ):
            return True
    return False


def _call_is_resource_selector(node: ast.AST) -> bool:
    tokens: set[str] = set()
    for item in ast.walk(node):
        if isinstance(item, ast.Name):
            tokens.update(_identifier_tokens(item.id))
        elif isinstance(item, ast.Attribute):
            tokens.update(_identifier_tokens(item.attr))
    return bool(tokens & _RESOURCE_TOKENS and tokens & _SELECTION_TOKENS)


def _matching_field_literals(
    node: ast.AST,
    field_hashes: Mapping[str, str],
) -> tuple[tuple[ast.Constant, str], ...]:
    matches: list[tuple[ast.Constant, str]] = []
    for item in ast.walk(node):
        if (
            isinstance(item, ast.Constant)
            and isinstance(item.value, str)
            and item.value in field_hashes
        ):
            matches.append((item, field_hashes[item.value]))
    return tuple(matches)


def _control_selector_findings(
    tree: ast.AST,
    *,
    locator: str,
    selector_hashes: Mapping[str, str],
) -> list[dict[str, Any]]:
    """Find control-selector use without inspecting attachment content."""

    if not selector_hashes:
        return []
    findings: dict[tuple[str, int, str], dict[str, Any]] = {}

    def record(node: ast.AST, kind: str, literal_sha256: str) -> None:
        line = int(getattr(node, "lineno", 0))
        key = (kind, line, literal_sha256)
        findings[key] = {
            "locator": locator,
            "line": line,
            "finding_kind": kind,
            "literal_sha256": literal_sha256,
        }

    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and _node_has_explicit_input_selector(node):
            for literal, digest in _matching_field_literals(node, selector_hashes):
                record(literal, "control_selector_comparison", digest)

        if isinstance(node, ast.Subscript):
            if _node_has_explicit_input_selector(node.value):
                for literal, digest in _matching_field_literals(
                    node.slice, selector_hashes
                ):
                    record(literal, "control_selector_subscript", digest)
            continue

        if isinstance(node, ast.Call):
            arguments = (*node.args, *(item.value for item in node.keywords))
            if _call_is_resource_selector(node.func):
                for argument in arguments:
                    for literal, digest in _matching_field_literals(
                        argument, selector_hashes
                    ):
                        record(literal, "control_selector_resource_selection", digest)

            if not isinstance(node.func, ast.Attribute):
                continue
            receiver_is_input = _node_has_explicit_input_selector(node.func.value)
            if node.func.attr == "get" and receiver_is_input and node.args:
                for literal, digest in _matching_field_literals(
                    node.args[0], selector_hashes
                ):
                    record(literal, "control_selector_lookup", digest)
            elif node.func.attr in _STRING_MATCH_METHODS and receiver_is_input:
                for argument in arguments:
                    for literal, digest in _matching_field_literals(
                        argument, selector_hashes
                    ):
                        record(literal, "control_selector_string_match", digest)
            elif node.func.attr in _REGEX_MATCH_METHODS:
                arguments_have_input = any(
                    _node_has_explicit_input_selector(argument)
                    for argument in arguments
                )
                if arguments_have_input:
                    for argument in arguments:
                        for literal, digest in _matching_field_literals(
                            argument, selector_hashes
                        ):
                            record(literal, "control_selector_regex_match", digest)
            continue

        condition: ast.AST | None = None
        if isinstance(node, (ast.If, ast.IfExp, ast.While)):
            condition = node.test
        elif isinstance(node, ast.comprehension):
            for item in node.ifs:
                if _node_has_explicit_input_selector(item):
                    for literal, digest in _matching_field_literals(
                        item, selector_hashes
                    ):
                        record(literal, "control_selector_condition", digest)
        if condition is not None and _node_has_explicit_input_selector(condition):
            for literal, digest in _matching_field_literals(
                condition, selector_hashes
            ):
                record(literal, "control_selector_condition", digest)

        if isinstance(node, ast.Match) and _node_has_explicit_input_selector(
            node.subject
        ):
            for case in node.cases:
                for literal, digest in _matching_field_literals(
                    case.pattern, selector_hashes
                ):
                    record(literal, "control_selector_match", digest)

    return list(findings.values())


def _invocation_literal_groups(
    invocation: Any | None,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    if invocation is None:
        return (), (), ()
    hard_identity_values: list[str] = [
        str(getattr(invocation, "request_id", "") or ""),
        str(getattr(invocation, "case_id", "") or ""),
        str(getattr(invocation, "case_name", "") or ""),
    ]
    selector_values: list[str] = []
    content_identities: list[str] = []
    for descriptor in tuple(getattr(invocation, "public_inputs", ()) or ()):
        selector_values.extend(
            (
                str(getattr(descriptor, "logical_name", "") or ""),
                str(getattr(descriptor, "source_name", "") or ""),
            )
        )
        content_sha256 = str(getattr(descriptor, "content_sha256", "") or "")
        if content_sha256:
            content_identities.append(content_sha256)
    return (
        tuple(
            dict.fromkeys(
                value for value in hard_identity_values if len(value.strip()) >= 8
            )
        ),
        tuple(dict.fromkeys(value for value in selector_values if value.strip())),
        tuple(dict.fromkeys(content_identities)),
    )


def audit_production_case_neutrality(
    project_root: str | Path,
    *,
    invocation: Any | None = None,
    forbidden_literals: Sequence[str] = (),
) -> dict[str, Any]:
    """Audit production Python without serializing request-specific material."""

    root = Path(project_root).resolve()
    explicit = tuple(str(value) for value in forbidden_literals if str(value))
    hard_identities, input_selectors, content_identities = _invocation_literal_groups(
        invocation
    )
    hard_literals = tuple(dict.fromkeys((*hard_identities, *explicit)))
    literal_hashes = {value: canonical_sha256(value) for value in hard_literals}
    semantic_values = tuple(dict.fromkeys(input_selectors))
    semantic_literal_hashes = {
        value: canonical_sha256(value)
        for value in semantic_values
        if value not in literal_hashes
    }
    control_flow: list[dict[str, Any]] = []
    literal_occurrences: list[dict[str, Any]] = []
    unreadable: list[str] = []
    scanned: list[dict[str, Any]] = []

    for path in _production_source_paths(root):
        locator = path.relative_to(root).as_posix()
        try:
            source = path.read_text(encoding="utf-8-sig", errors="strict")
            tree = ast.parse(source, filename=locator)
        except (OSError, UnicodeError, SyntaxError):
            unreadable.append(locator)
            continue
        scanned.append({"locator": locator, "source_sha256": canonical_sha256(source)})
        control_flow.extend(_control_flow_findings(tree, locator=locator))
        control_flow.extend(
            _control_selector_findings(
                tree,
                locator=locator,
                selector_hashes=semantic_literal_hashes,
            )
        )
        for value, value_sha256 in literal_hashes.items():
            offset = source.find(value)
            while offset >= 0:
                literal_occurrences.append(
                    {
                        "locator": locator,
                        "line": source.count("\n", 0, offset) + 1,
                        "literal_sha256": value_sha256,
                    }
                )
                offset = source.find(value, offset + max(1, len(value)))

    control_flow.sort(key=lambda item: (item["locator"], item["line"], item["finding_kind"]))
    literal_occurrences.sort(
        key=lambda item: (item["locator"], item["line"], item["literal_sha256"])
    )
    namespace_policy = {
        "case_identity": {
            "literal_count": len(literal_hashes),
            "literal_set_sha256": canonical_sha256(sorted(literal_hashes.values())),
            "production_source_scan": "exact_identity",
        },
        "control_selector": {
            "literal_count": len(semantic_literal_hashes),
            "literal_set_sha256": canonical_sha256(
                sorted(semantic_literal_hashes.values())
            ),
            "production_source_scan": "explicit_selector_control_flow",
        },
        "content_schema": {
            "input_count": len(content_identities),
            "content_identity_set_sha256": canonical_sha256(
                sorted(content_identities)
            ),
            "production_source_scan": "not_permitted",
        },
    }
    projection = {
        "protocol": CASE_NEUTRALITY_AUDIT_PROTOCOL,
        "valid": not (control_flow or literal_occurrences or unreadable),
        "scanned_file_count": len(scanned),
        "scanned_source_sha256": canonical_sha256(scanned),
        "forbidden_literal_count": len(literal_hashes) + len(semantic_literal_hashes),
        "forbidden_literal_set_sha256": canonical_sha256(
            sorted((*literal_hashes.values(), *semantic_literal_hashes.values()))
        ),
        "namespace_policy": namespace_policy,
        "namespace_policy_sha256": canonical_sha256(namespace_policy),
        "control_flow_findings": control_flow,
        "literal_occurrences": literal_occurrences,
        "unreadable_sources": sorted(set(unreadable)),
    }
    return {**projection, "audit_sha256": canonical_sha256(projection)}


__all__ = [
    "CASE_NEUTRALITY_AUDIT_PROTOCOL",
    "audit_production_case_neutrality",
]
