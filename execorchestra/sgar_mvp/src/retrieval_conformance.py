"""No-network activation gate for the formal frozen retrieval runtime."""

from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
from typing import Any, Mapping

from .atomic_io import temporary_sibling_path
from .resource_loader import load_real_pool_with_index
from .retrieval_runtime import (
    FORMAL_TYPED_QUOTAS,
    RetrievalRuntimeIdentity,
    build_retrieval_runtime_identity,
    validate_loaded_retrieval_backend,
)


CONFORMANCE_SCHEMA = "sgar-retrieval-conformance-v1"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = temporary_sibling_path(path)
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _function_node(tree: ast.AST, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    ]
    if len(matches) != 1:
        raise ValueError(f"conformance_function_identity_invalid:{name}")
    return matches[0]


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _called_attributes(node: ast.AST) -> set[str]:
    return {
        child.func.attr
        for child in ast.walk(node)
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute)
    }


def _called_names(node: ast.AST) -> set[str]:
    return {
        child.func.id
        for child in ast.walk(node)
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
    }


def _formal_call_graph(root: Path) -> dict[str, Any]:
    main_tree = ast.parse(_source(root / "sgar_mvp" / "main.py"))
    router_tree = ast.parse(
        _source(root / "sgar_mvp" / "src" / "router.py")
    )
    orchestrator_tree = ast.parse(
        _source(root / "sgar_mvp" / "src" / "orchestrator.py")
    )
    main_function = _function_node(main_tree, "_run_pipeline_with_cost_ledger")
    frozen_router = _function_node(router_tree, "_build_frozen_pool_attempt")
    orchestrator_function = _function_node(orchestrator_tree, "_execute_routing_session")
    main_calls = _called_attributes(main_function)
    frozen_calls = _called_attributes(frozen_router)
    orchestrator_calls = _called_attributes(orchestrator_function)
    main_named_calls = _called_names(main_function)
    router_constructors = [
        child
        for child in ast.walk(main_function)
        if isinstance(child, ast.Call)
        and isinstance(child.func, ast.Name)
        and child.func.id == "SGARRouter"
    ]
    router_transport_disabled = bool(
        len(router_constructors) == 1
        and any(
            item.arg == "policy_transport"
            and isinstance(item.value, ast.Constant)
            and item.value.value is None
            for item in router_constructors[0].keywords
        )
    )
    sealed_calls = [
        child
        for child in ast.walk(orchestrator_function)
        if isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
        and child.func.attr == "_execute_sealed_routing_session"
    ]
    legacy_build_calls = [
        child
        for child in ast.walk(orchestrator_function)
        if isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
        and child.func.attr == "build_attempt"
    ]
    sealed_path_precedes_legacy_router = bool(
        len(sealed_calls) == 1
        and len(legacy_build_calls) == 1
        and sealed_calls[0].lineno < legacy_build_calls[0].lineno
    )
    forbidden_formal_calls = {
        "start_session",
        "incremental_replan",
        "encode_query_profile",
        "_build_candidate_bundle",
        "_build_typed_candidate_bundle",
        "_expand_agent_dependency_candidates",
        "_expand_skill_dependency_candidates",
        "_complete_intelligent_candidates",
        "_compress_candidate_bundle",
        "_inject_domain_specific_tools",
        "_runtime_intent_match",
        "_fallback_bundle_decision",
    }
    observed_forbidden = sorted(
        (main_calls | frozen_calls | orchestrator_calls) & forbidden_formal_calls
    )
    decide_calls = [
        child
        for child in ast.walk(frozen_router)
        if isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
        and child.func.attr == "_decide_bundle"
    ]
    deterministic_fallback_disabled = bool(
        len(decide_calls) == 1
        and any(
            item.arg == "allow_deterministic_fallback"
            and isinstance(item.value, ast.Constant)
            and item.value.value is False
            for item in decide_calls[0].keywords
        )
    )
    strict_protocol_enabled = bool(
        len(decide_calls) == 1
        and any(
            item.arg == "strict_plan_protocol"
            and isinstance(item.value, ast.Constant)
            and item.value.value is True
            for item in decide_calls[0].keywords
        )
    )
    retry_keywords = [
        item.value
        for item in (decide_calls[0].keywords if len(decide_calls) == 1 else ())
        if item.arg == "transport_retry_max"
    ]
    transport_retry_max = (
        2
        if len(retry_keywords) == 1
        and isinstance(retry_keywords[0], ast.Name)
        and retry_keywords[0].id == "PLAN_COMPILER_TRANSPORT_RETRY_MAX"
        else None
    )
    control_model_failover_disabled = bool(
        len(decide_calls) == 1
        and any(
            item.arg == "allow_control_model_failover"
            and isinstance(item.value, ast.Constant)
            and item.value.value is False
            for item in decide_calls[0].keywords
        )
    )
    return {
        "prepare_candidate_pool_present": "prepare_candidate_pool" in main_calls,
        "start_frozen_session_present": "start_frozen_session" in main_calls,
        "post_freeze_orchestrator_retrieval_calls": sorted(
            orchestrator_calls & {"prepare_candidate_pool", "prepare_ideal_profile"}
        ),
        "forbidden_formal_calls": observed_forbidden,
        "deterministic_candidate_fallback_disabled": deterministic_fallback_disabled,
        "formal_plan_compiler_strict_protocol": strict_protocol_enabled,
        "formal_plan_compiler_transport_retry_max": transport_retry_max,
        "formal_control_model_failover_disabled": control_model_failover_disabled,
        "candidate_compression_enabled": "_compress_candidate_bundle" in frozen_calls,
        "live_system_role_probe_calls": sorted(
            main_named_calls & {"_probe_system_role"}
        ),
        "executable_plan_compiler_present": "ExecutablePlanCompiler" in main_named_calls,
        "router_policy_transport_disabled": router_transport_disabled,
        "sealed_compiler_path_precedes_legacy_router": sealed_path_precedes_legacy_router,
    }


def _unmetered_model_sends(root: Path) -> list[str]:
    allowed = (root / "sgar_mvp" / "src" / "model_transport.py").resolve()
    findings: list[str] = []
    production_paths = [root / "sgar_mvp" / "main.py"] + sorted(
        (root / "sgar_mvp" / "src").glob("*.py")
    )
    for path in production_paths:
        tree = ast.parse(_source(path))
        direct_send = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "create":
                continue
            completions = node.func.value
            chat = completions.value if isinstance(completions, ast.Attribute) else None
            if (
                isinstance(completions, ast.Attribute)
                and completions.attr == "completions"
                and isinstance(chat, ast.Attribute)
                and chat.attr == "chat"
            ):
                direct_send = True
                break
        if direct_send and path.resolve() != allowed:
            findings.append(path.relative_to(root).as_posix())
    return sorted(findings)


def _forbidden_production_imports(root: Path) -> list[str]:
    findings: list[str] = []
    for path in (root / "sgar_mvp" / "src").glob("*.py"):
        tree = ast.parse(_source(path))
        modules = {
            str(node.module or "")
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        modules.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        if any(
            "retrieval_eval" in module or "experiment_one.cases" in module
            for module in modules
        ):
            findings.append(path.relative_to(root).as_posix())
    return sorted(findings)


def _validate_loaded_pool(identity: RetrievalRuntimeIdentity) -> dict[str, Any]:
    library, _fallback_ids, resource_index = load_real_pool_with_index()
    validate_loaded_retrieval_backend(identity, resource_index=resource_index)
    library_ids = {item.id for item in library}
    index_ids = set(resource_index)
    effective_resource_ids = {
        item.resource_id
        for item in identity.availability_records
        if item.in_effective_pool
    }
    runtime_eligible_resource_ids = set(identity.eligible_resource_ids)
    from .model_selection import is_candidate_resource
    type_counts = {
        resource_type: sum(
            1
            for item in library
            if item.type.value == resource_type and is_candidate_resource(resource_index[item.id])
        )
        for resource_type in FORMAL_TYPED_QUOTAS
    }
    shortfalls = {
        resource_type: max(0, quota - type_counts.get(resource_type, 0))
        for resource_type, quota in FORMAL_TYPED_QUOTAS.items()
        if quota > 0 and type_counts.get(resource_type, 0) < quota
    }
    return {
        "library_resource_count": len(library_ids),
        "index_resource_count": len(index_ids),
        "effective_resource_count": len(effective_resource_ids),
        "eligible_resource_count": len(runtime_eligible_resource_ids),
        "library_matches_identity": library_ids == effective_resource_ids,
        "index_matches_identity": index_ids == effective_resource_ids,
        "type_counts": type_counts,
        "quota_shortfalls": shortfalls,
    }


def run_retrieval_conformance(
    *,
    project_root: str | Path = PROJECT_ROOT,
    provider_compatibility: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run static and local-index checks without constructing any model client."""

    root = Path(project_root).resolve()
    errors: list[str] = []
    try:
        identity = build_retrieval_runtime_identity(
            project_root=root,
            provider_compatibility=provider_compatibility,
            require_release_sealed=True,
        )
        pool = _validate_loaded_pool(identity)
        call_graph = _formal_call_graph(root)
        unmetered = _unmetered_model_sends(root)
        forbidden_imports = _forbidden_production_imports(root)
        if not pool["library_matches_identity"]:
            errors.append("loaded_library_identity_mismatch")
        if not pool["index_matches_identity"]:
            errors.append("loaded_resource_index_identity_mismatch")
        # Quotas cap base candidates. Partial inventory is diagnostic, while
        # an entirely absent enabled resource type still fails pool validation.
        if any(pool["type_counts"].get(kind, 0) == 0
               for kind, quota in FORMAL_TYPED_QUOTAS.items() if quota > 0):
            errors.append("formal_required_resource_type_empty")
        if not call_graph["prepare_candidate_pool_present"]:
            errors.append("formal_prepare_candidate_pool_missing")
        if not call_graph["start_frozen_session_present"]:
            errors.append("formal_start_frozen_session_missing")
        if call_graph["forbidden_formal_calls"]:
            errors.append("legacy_candidate_logic_reachable")
        if call_graph["post_freeze_orchestrator_retrieval_calls"]:
            errors.append("post_freeze_retrieval_reachable")
        if not call_graph["deterministic_candidate_fallback_disabled"]:
            errors.append("formal_deterministic_candidate_fallback_enabled")
        if not call_graph["formal_plan_compiler_strict_protocol"]:
            errors.append("formal_plan_compiler_protocol_not_strict")
        if call_graph["formal_plan_compiler_transport_retry_max"] != 2:
            errors.append("formal_plan_compiler_transport_retry_not_fixed")
        if not call_graph["formal_control_model_failover_disabled"]:
            errors.append("formal_control_model_failover_enabled")
        if call_graph["candidate_compression_enabled"]:
            errors.append("formal_candidate_compression_enabled")
        if call_graph["live_system_role_probe_calls"]:
            errors.append("formal_live_system_role_probe_reachable")
        if not call_graph["executable_plan_compiler_present"]:
            errors.append("formal_executable_plan_compiler_missing")
        if not call_graph["router_policy_transport_disabled"]:
            errors.append("formal_router_policy_transport_enabled")
        if not call_graph["sealed_compiler_path_precedes_legacy_router"]:
            errors.append("formal_sealed_compiler_path_not_authoritative")
        if unmetered:
            errors.append("unmetered_production_model_sends")
        if forbidden_imports:
            errors.append("production_imports_retrieval_gold_or_cases")
        return {
            "schema_version": CONFORMANCE_SCHEMA,
            "valid": not errors,
            "errors": errors,
            "retrieval_runtime_identity": identity.model_dump(mode="json"),
            "pool_check": pool,
            "formal_call_graph": call_graph,
            "unmetered_production_model_sends": unmetered,
            "forbidden_production_imports": forbidden_imports,
            "network_requests_made": 0,
            "paid_model_calls_made": 0,
            "held_out_test_accesses": [],
        }
    except Exception as exc:
        return {
            "schema_version": CONFORMANCE_SCHEMA,
            "valid": False,
            "errors": [str(getattr(exc, "error_code", type(exc).__name__))],
            "network_requests_made": 0,
            "paid_model_calls_made": 0,
            "held_out_test_accesses": [],
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    parser.add_argument("--output")
    args = parser.parse_args()
    report = run_retrieval_conformance(project_root=args.project_root)
    if args.output:
        _atomic_json(Path(args.output), report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    raise SystemExit(0 if report.get("valid") is True else 2)


if __name__ == "__main__":
    main()


__all__ = ["CONFORMANCE_SCHEMA", "run_retrieval_conformance"]
