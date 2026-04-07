"""Helpers for passing a completed workflow result into follow-up workflows."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from entity.enums import LogLevel
from server.settings import YAML_DIR


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _validate_workflow_filename(filename: str, *, require_yaml_extension: bool = True) -> str:
    value = (filename or "").strip()
    if not value:
        raise ValueError("Workflow filename cannot be empty")
    if ".." in value or value.startswith(("/", "\\")):
        raise ValueError("Workflow filename cannot contain path traversal")
    if not re.match(r"^[a-zA-Z0-9._-]+$", value):
        raise ValueError("Workflow filename can only contain letters, digits, dots, underscores, and hyphens")
    if require_yaml_extension and not value.endswith((".yaml", ".yml")):
        raise ValueError("Workflow filename must end with .yaml or .yml")
    return Path(value).name


def _normalize_workflow_filename(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw or raw.lower() in {"stop", "none", "null", "__stop__"}:
        return ""
    if not raw.endswith((".yaml", ".yml")):
        raw = f"{raw}.yaml"
    return _validate_workflow_filename(raw, require_yaml_extension=True)


def load_handoffs_from_workflow(yaml_file: str | Path, variables: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    """Load graph.handoffs from a workflow file without executing it."""

    from check.check import load_config

    yaml_path = Path(yaml_file).expanduser()
    if not yaml_path.is_absolute() and not yaml_path.exists():
        name = str(yaml_path)
        if not name.endswith((".yaml", ".yml")):
            name = f"{name}.yaml"
        yaml_path = YAML_DIR / _validate_workflow_filename(name, require_yaml_extension=True)

    design = load_config(yaml_path, vars_override=dict(variables or {}))
    handoffs = getattr(design.graph, "handoffs", None) or []
    return [dict(item) for item in handoffs if isinstance(item, Mapping)]


def normalize_handoff_config(handoff: Mapping[str, Any], *, index: int = 0) -> dict[str, Any]:
    """Normalize one handoff config entry into a predictable shape."""

    raw_target = handoff.get("target_workflow") or handoff.get("yaml_file") or handoff.get("workflow") or handoff.get("target")
    raw_router = handoff.get("router_workflow") or handoff.get("router")
    routes = {}
    if isinstance(handoff.get("routes"), Mapping):
        routes = {
            str(route_key or "").strip(): _normalize_workflow_filename(route_target)
            for route_key, route_target in handoff.get("routes", {}).items()
            if str(route_key or "").strip()
        }

    return {
        "id": str(handoff.get("id") or f"handoff_{index + 1}").strip(),
        "enabled": bool(handoff.get("enabled", True)),
        "mode": str(handoff.get("mode") or ("route" if raw_router and routes else "direct")).strip().lower(),
        "target_workflow": _normalize_workflow_filename(raw_target),
        "router_workflow": _normalize_workflow_filename(raw_router),
        "routes": routes,
        "input_from": str(handoff.get("input_from") or "final_message").strip(),
        "prompt_template": str(handoff.get("prompt_template") or "").strip(),
        "router_prompt_template": str(handoff.get("router_prompt_template") or "").strip(),
        "prompt_prefix": str(handoff.get("prompt_prefix") or "").strip(),
        "session_name": str(handoff.get("session_name") or "").strip(),
        "variables": dict(handoff.get("variables") or {}) if isinstance(handoff.get("variables"), Mapping) else {},
    }


def iter_enabled_handoffs(handoffs: list[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    normalized = []
    for index, handoff in enumerate(handoffs or []):
        if not isinstance(handoff, Mapping):
            continue
        item = normalize_handoff_config(handoff, index=index)
        if not item["enabled"]:
            continue
        if item["target_workflow"] or (
            item["mode"] in {"route", "router", "ai_router"}
            and item["router_workflow"]
            and item["routes"]
        ):
            normalized.append(item)
    return normalized


def build_handoff_prompt(
    handoff: Mapping[str, Any],
    *,
    source_workflow: str,
    final_message: str,
    results: Any = None,
    token_usage: Any = None,
) -> str:
    results_json = json.dumps(results or {}, ensure_ascii=False, indent=2, default=str)
    token_usage_json = json.dumps(token_usage or {}, ensure_ascii=False, indent=2, default=str)
    payload_json = json.dumps(
        {
            "source_workflow": source_workflow,
            "final_message": final_message,
            "results": results or {},
            "token_usage": token_usage or {},
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    )
    values = _SafeFormatDict(
        source_workflow=source_workflow,
        final_message=final_message,
        results_json=results_json,
        token_usage_json=token_usage_json,
        payload_json=payload_json,
    )

    template = str(handoff.get("prompt_template") or "").strip()
    if template:
        return template.format_map(values).strip()

    input_from = str(handoff.get("input_from") or "final_message").strip()
    if input_from == "results":
        body = results_json
    elif input_from == "token_usage":
        body = token_usage_json
    elif input_from in {"json", "payload", "envelope"}:
        body = payload_json
    else:
        body = final_message

    prefix = str(handoff.get("prompt_prefix") or "").strip()
    lines = [
        f"上游工作流: {source_workflow}",
        "上游输出:",
        body or "(上游工作流没有返回文本输出)",
    ]
    if prefix:
        lines.insert(0, prefix)
    return "\n\n".join(lines).strip()


def build_router_prompt(
    handoff: Mapping[str, Any],
    *,
    source_workflow: str,
    final_message: str,
    results: Any = None,
    token_usage: Any = None,
) -> str:
    routes = dict(handoff.get("routes") or {})
    route_options = "\n".join(
        f"- {key}: {target or 'STOP'}"
        for key, target in routes.items()
    )
    values = _SafeFormatDict(
        source_workflow=source_workflow,
        final_message=final_message,
        results_json=json.dumps(results or {}, ensure_ascii=False, indent=2, default=str),
        token_usage_json=json.dumps(token_usage or {}, ensure_ascii=False, indent=2, default=str),
        routes=route_options,
    )
    template = str(handoff.get("router_prompt_template") or "").strip()
    if template:
        return template.format_map(values).strip()

    return (
        "你是 MovieDev 的工作流路由器。请阅读上游工作流结果，并只选择一个后续路由。\n\n"
        f"上游工作流: {source_workflow}\n\n"
        f"可选路由:\n{route_options}\n\n"
        "上游最终输出:\n"
        f"{final_message or '(空)'}\n\n"
        "请只输出 JSON，格式如下：\n"
        "{\"route\":\"路由名\", \"reason\":\"一句话原因\"}"
    ).strip()


def parse_route_decision(decision_text: str, routes: Mapping[str, str]) -> tuple[str, str]:
    text = str(decision_text or "").strip()
    reason = ""
    if text:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, Mapping):
                route = str(parsed.get("route") or parsed.get("decision") or parsed.get("target") or "").strip()
                reason = str(parsed.get("reason") or "").strip()
                if route:
                    return _match_route_key(route, routes), reason
        except json.JSONDecodeError:
            pass

    lowered = text.lower()
    for prefix in ("route:", "decision:", "target:"):
        marker_index = lowered.find(prefix)
        if marker_index >= 0:
            route_line = text[marker_index + len(prefix):].strip().splitlines()[0].strip()
            return _match_route_key(route_line, routes), reason

    for key in routes:
        if key and key.lower() in lowered:
            return key, reason
    return "", reason


def _match_route_key(value: str, routes: Mapping[str, str]) -> str:
    candidate = str(value or "").strip().strip('"').strip("'")
    if candidate in routes:
        return candidate
    lowered = candidate.lower()
    for key in routes:
        if key.lower() == lowered:
            return key
    return ""


def run_handoff(
    handoff: Mapping[str, Any],
    *,
    source_workflow: str,
    final_message: str,
    results: Any = None,
    token_usage: Any = None,
    variables: Mapping[str, Any] | None = None,
    log_level: LogLevel | None = None,
) -> dict[str, Any]:
    """Run one follow-up workflow and return a compact result payload."""

    from runtime.sdk import run_workflow

    normalized = normalize_handoff_config(handoff)
    if normalized["mode"] in {"route", "router", "ai_router"}:
        return _run_routed_handoff(
            normalized,
            source_workflow=source_workflow,
            final_message=final_message,
            results=results,
            token_usage=token_usage,
            variables=variables,
            log_level=log_level,
        )

    prompt = build_handoff_prompt(
        normalized,
        source_workflow=source_workflow,
        final_message=final_message,
        results=results,
        token_usage=token_usage,
    )
    next_variables = {
        **dict(variables or {}),
        **dict(normalized.get("variables") or {}),
    }
    result = run_workflow(
        normalized["target_workflow"],
        task_prompt=prompt,
        variables=next_variables,
        session_name=normalized["session_name"] or None,
        log_level=log_level,
    )
    next_message = result.final_message.text_content() if result.final_message else ""
    return {
        "id": normalized["id"],
        "status": "completed",
        "source_workflow": source_workflow,
        "target_workflow": normalized["target_workflow"],
        "input_from": normalized["input_from"],
        "final_message": next_message,
        "token_usage": result.meta_info.token_usage,
        "output_dir": str(result.meta_info.output_dir.resolve()),
    }


def _run_routed_handoff(
    handoff: Mapping[str, Any],
    *,
    source_workflow: str,
    final_message: str,
    results: Any = None,
    token_usage: Any = None,
    variables: Mapping[str, Any] | None = None,
    log_level: LogLevel | None = None,
) -> dict[str, Any]:
    from runtime.sdk import run_workflow

    next_variables = {
        **dict(variables or {}),
        **dict(handoff.get("variables") or {}),
    }
    router_prompt = build_router_prompt(
        handoff,
        source_workflow=source_workflow,
        final_message=final_message,
        results=results,
        token_usage=token_usage,
    )
    router_result = run_workflow(
        handoff["router_workflow"],
        task_prompt=router_prompt,
        variables=next_variables,
        session_name=f"{handoff['id']}_router" if handoff.get("id") else None,
        log_level=log_level,
    )
    router_message = router_result.final_message.text_content() if router_result.final_message else ""
    route_key, reason = parse_route_decision(router_message, dict(handoff.get("routes") or {}))
    target_workflow = dict(handoff.get("routes") or {}).get(route_key, "")
    base_payload = {
        "id": handoff["id"],
        "mode": "route",
        "source_workflow": source_workflow,
        "router_workflow": handoff["router_workflow"],
        "route": route_key,
        "reason": reason,
        "router_final_message": router_message,
        "router_token_usage": router_result.meta_info.token_usage,
    }
    if not route_key:
        return {
            **base_payload,
            "status": "failed",
            "message": "Router workflow did not return a route that matches configured routes.",
        }
    if not target_workflow:
        return {
            **base_payload,
            "status": "stopped",
            "target_workflow": "",
            "final_message": "",
            "token_usage": None,
            "output_dir": "",
        }

    downstream_prompt = build_handoff_prompt(
        handoff,
        source_workflow=source_workflow,
        final_message=final_message,
        results=results,
        token_usage=token_usage,
    )
    downstream_result = run_workflow(
        target_workflow,
        task_prompt=downstream_prompt,
        variables=next_variables,
        session_name=handoff.get("session_name") or None,
        log_level=log_level,
    )
    downstream_message = downstream_result.final_message.text_content() if downstream_result.final_message else ""
    return {
        **base_payload,
        "status": "completed",
        "target_workflow": target_workflow,
        "input_from": handoff.get("input_from") or "final_message",
        "final_message": downstream_message,
        "token_usage": downstream_result.meta_info.token_usage,
        "output_dir": str(downstream_result.meta_info.output_dir.resolve()),
    }


def run_handoffs(
    handoffs: list[Mapping[str, Any]] | None,
    *,
    source_workflow: str,
    final_message: str,
    results: Any = None,
    token_usage: Any = None,
    variables: Mapping[str, Any] | None = None,
    log_level: LogLevel | None = None,
) -> list[dict[str, Any]]:
    outputs = []
    for handoff in iter_enabled_handoffs(handoffs):
        outputs.append(
            run_handoff(
                handoff,
                source_workflow=source_workflow,
                final_message=final_message,
                results=results,
                token_usage=token_usage,
                variables=variables,
                log_level=log_level,
            )
        )
    return outputs
