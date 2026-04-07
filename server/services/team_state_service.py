"""Helpers for managing human-governed team state during workflow runs."""

from __future__ import annotations

import time
import uuid
from copy import deepcopy
import re
from typing import Any, Dict, List, Mapping


def _now() -> float:
    return time.time()


def _trimmed_lines(values: Any) -> List[str]:
    if values is None:
        return []
    if isinstance(values, str):
        values = values.splitlines()
    if not isinstance(values, list):
        return []
    normalized: List[str] = []
    for item in values:
        text = str(item or "").strip()
        if text:
            normalized.append(text)
    return normalized


def _normalize_output_preview(value: Any, *, limit: int = 240) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 1].rstrip()}..."


def _normalize_output_text(value: Any, *, limit: int = 8000) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}..."


def _coerce_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _parse_key_value_lines(value: Any) -> Dict[str, str]:
    text = str(value or "").strip()
    if not text:
        return {}
    parsed: Dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^\s*([A-Za-z][A-Za-z _-]{1,48})\s*:\s*(.+?)\s*$", line)
        if not match:
            continue
        key = re.sub(r"[\s_-]+", "_", match.group(1).strip().lower())
        parsed[key] = match.group(2).strip()
    return parsed


def _normalize_tasks(values: Any) -> List[Dict[str, Any]]:
    if values is None:
        return []
    if isinstance(values, str):
        values = values.splitlines()
    if not isinstance(values, list):
        return []

    tasks: List[Dict[str, Any]] = []
    for index, item in enumerate(values):
        if isinstance(item, Mapping):
            title = str(item.get("title") or item.get("text") or "").strip()
            if not title:
                continue
            task_id = str(item.get("id") or f"task-{index + 1}").strip()
            status = str(item.get("status") or "pending").strip() or "pending"
            owner = str(item.get("owner") or "").strip()
            node_id = str(item.get("node_id") or owner or title).strip()
            tasks.append(
                {
                    "id": task_id,
                    "title": title,
                    "status": status,
                    "owner": owner,
                    "node_id": node_id,
                    "started_at": item.get("started_at"),
                    "completed_at": item.get("completed_at"),
                    "output_preview": _normalize_output_preview(item.get("output_preview")),
                    "output_size": _coerce_int(item.get("output_size")),
                    "reused_replay_output": bool(item.get("reused_replay_output", False)),
                    "reused_at": item.get("reused_at"),
                    "replay_injected_predecessors": [
                        str(value or "").strip()
                        for value in (item.get("replay_injected_predecessors") or [])
                        if str(value or "").strip()
                    ],
                    "injected_at": item.get("injected_at"),
                }
            )
            continue

        title = str(item or "").strip()
        if title:
            tasks.append(
                {
                    "id": f"task-{index + 1}",
                    "title": title,
                    "status": "pending",
                    "owner": "",
                    "node_id": title,
                    "started_at": None,
                    "completed_at": None,
                    "output_preview": "",
                    "output_size": 0,
                    "reused_replay_output": False,
                    "reused_at": None,
                    "replay_injected_predecessors": [],
                    "injected_at": None,
                }
            )
    return tasks


def _normalize_artifacts(values: Any) -> Dict[str, Any]:
    if not isinstance(values, Mapping):
        return {
            "task_outputs": {},
            "replay_context": {
                "target_task_id": "",
                "target_task_title": "",
                "retained_tasks": [],
                "retained_node_ids": [],
                "text": "",
            },
            "token_usage_snapshot": {
                "total_usage": {},
                "node_usages": {},
            },
            "review": {
                "last_directive": {},
            },
        }

    task_outputs_payload = values.get("task_outputs")
    if not isinstance(task_outputs_payload, Mapping):
        task_outputs_payload = {}

    normalized_task_outputs: Dict[str, Any] = {}
    for task_id, item in task_outputs_payload.items():
        key = str(task_id or "").strip()
        if not key or not isinstance(item, Mapping):
            continue
        normalized_task_outputs[key] = {
            "task_id": key,
            "node_id": str(item.get("node_id") or "").strip(),
            "title": str(item.get("title") or "").strip(),
            "status": str(item.get("status") or "").strip() or "pending",
            "output_preview": _normalize_output_preview(item.get("output_preview")),
            "output_text": _normalize_output_text(item.get("output_text")),
            "output_size": _coerce_int(item.get("output_size")),
            "reused_replay_output": bool(item.get("reused_replay_output", False)),
            "reused_at": item.get("reused_at"),
            "replay_injected_predecessors": [
                str(value or "").strip()
                for value in (item.get("replay_injected_predecessors") or [])
                if str(value or "").strip()
            ],
            "injected_at": item.get("injected_at"),
            "updated_at": item.get("updated_at"),
        }

    replay_context_payload = values.get("replay_context")
    if not isinstance(replay_context_payload, Mapping):
        replay_context_payload = {}

    token_usage_snapshot_payload = values.get("token_usage_snapshot")
    if not isinstance(token_usage_snapshot_payload, Mapping):
        token_usage_snapshot_payload = {}

    token_total_usage_payload = token_usage_snapshot_payload.get("total_usage")
    if not isinstance(token_total_usage_payload, Mapping):
        token_total_usage_payload = {}

    token_node_usages_payload = token_usage_snapshot_payload.get("node_usages")
    if not isinstance(token_node_usages_payload, Mapping):
        token_node_usages_payload = {}

    normalized_node_usages: Dict[str, Any] = {}
    for node_id, item in token_node_usages_payload.items():
        key = str(node_id or "").strip()
        if not key or not isinstance(item, Mapping):
            continue
        normalized_node_usages[key] = {
            "input_tokens": _coerce_int(item.get("input_tokens")),
            "output_tokens": _coerce_int(item.get("output_tokens")),
            "total_tokens": _coerce_int(item.get("total_tokens")),
        }

    retained_tasks_payload = replay_context_payload.get("retained_tasks")
    if not isinstance(retained_tasks_payload, list):
        retained_tasks_payload = []

    retained_node_ids_payload = replay_context_payload.get("retained_node_ids")
    if not isinstance(retained_node_ids_payload, list):
        retained_node_ids_payload = []

    retained_tasks: List[Dict[str, Any]] = []
    for item in retained_tasks_payload:
        if not isinstance(item, Mapping):
            continue
        task_id = str(item.get("task_id") or "").strip()
        title = str(item.get("title") or task_id).strip()
        if not task_id or not title:
            continue
        retained_tasks.append(
            {
                "task_id": task_id,
                "title": title,
                "preview": _normalize_output_preview(item.get("preview")),
                "node_id": str(item.get("node_id") or "").strip(),
                "output_text": _normalize_output_text(item.get("output_text")),
            }
        )

    review_payload = values.get("review")
    if not isinstance(review_payload, Mapping):
        review_payload = {}
    last_directive_payload = review_payload.get("last_directive")
    if not isinstance(last_directive_payload, Mapping):
        last_directive_payload = {}

    return {
        "task_outputs": normalized_task_outputs,
        "replay_context": {
            "target_task_id": str(replay_context_payload.get("target_task_id") or "").strip(),
            "target_task_title": str(replay_context_payload.get("target_task_title") or "").strip(),
            "retained_tasks": retained_tasks,
            "retained_node_ids": [
                str(item or "").strip()
                for item in retained_node_ids_payload
                if str(item or "").strip()
            ],
            "text": str(replay_context_payload.get("text") or "").strip(),
        },
        "token_usage_snapshot": {
            "total_usage": {
                "input_tokens": _coerce_int(token_total_usage_payload.get("input_tokens")),
                "output_tokens": _coerce_int(token_total_usage_payload.get("output_tokens")),
                "total_tokens": _coerce_int(token_total_usage_payload.get("total_tokens")),
            },
            "node_usages": normalized_node_usages,
        },
        "review": {
            "last_directive": {
                "reviewer_node_id": str(last_directive_payload.get("reviewer_node_id") or "").strip(),
                "verdict": str(last_directive_payload.get("verdict") or "").strip(),
                "approval_id": str(last_directive_payload.get("approval_id") or "").strip(),
                "replay_target_id": str(last_directive_payload.get("replay_target_id") or "").strip(),
                "replay_target_title": str(last_directive_payload.get("replay_target_title") or "").strip(),
                "note": str(last_directive_payload.get("note") or "").strip(),
                "created_at": last_directive_payload.get("created_at"),
            },
        },
    }


def _normalize_approvals(values: Any) -> List[Dict[str, Any]]:
    if values is None:
        return []
    if not isinstance(values, list):
        return []

    approvals: List[Dict[str, Any]] = []
    for item in values:
        if not isinstance(item, Mapping):
            title = str(item or "").strip()
            if not title:
                continue
            approvals.append(
                {
                    "id": str(uuid.uuid4()),
                    "title": title,
                    "status": "open",
                    "blocking": False,
                    "note": "",
                    "created_at": _now(),
                    "resolved_at": None,
                }
            )
            continue

        title = str(item.get("title") or "").strip()
        if not title:
            continue
        status = str(item.get("status") or "open").strip().lower()
        if status not in {"open", "resolved"}:
            status = "open"
        resolved_at = item.get("resolved_at")
        if status == "resolved" and not resolved_at:
            resolved_at = _now()
        approvals.append(
            {
                "id": str(item.get("id") or uuid.uuid4()),
                "title": title,
                "status": status,
                "blocking": bool(item.get("blocking", False)),
                "note": str(item.get("note") or "").strip(),
                "created_at": float(item.get("created_at") or _now()),
                "resolved_at": resolved_at,
            }
        )
    return approvals


class TeamStateService:
    """Normalizes and compares team state snapshots."""

    def empty_state(self) -> Dict[str, Any]:
        return {
            "mode": "human_governed",
            "goal": "",
            "workflow": {
                "name": "",
                "description": "",
                "organization": "",
                "team_mode": "human_governed",
            },
            "plan": {
                "summary": "",
                "tasks": [],
            },
            "memory": {
                "facts": [],
                "assumptions": [],
                "open_questions": [],
                "decisions": [],
            },
            "approvals": [],
            "artifacts": {
                "task_outputs": {},
                "replay_context": {
                    "target_task_id": "",
                    "target_task_title": "",
                    "retained_tasks": [],
                    "retained_node_ids": [],
                    "text": "",
                },
                "token_usage_snapshot": {
                    "total_usage": {},
                    "node_usages": {},
                },
                "review": {
                    "last_directive": {},
                },
            },
            "replay": {
                "target_task_id": "",
                "target_task_title": "",
                "requested_at": None,
            },
            "meta": {
                "updated_at": None,
                "source": "empty",
            },
        }

    def initialize_state(
        self,
        *,
        yaml_file: str,
        task_prompt: str,
        graph_definition=None,
        existing: Mapping[str, Any] | None = None,
    ) -> Dict[str, Any]:
        workflow_name = str(yaml_file or "").strip()
        description = ""
        organization = ""
        team_mode = "human_governed"
        initial_instruction = ""

        if graph_definition is not None:
            description = str(getattr(graph_definition, "description", "") or "").strip()
            organization = str(getattr(graph_definition, "organization", "") or "").strip()
            team_mode = str(getattr(graph_definition, "team_mode", "") or team_mode).strip() or "human_governed"
            initial_instruction = str(getattr(graph_definition, "initial_instruction", "") or "").strip()

        payload = deepcopy(existing or {})
        payload["goal"] = str(payload.get("goal") or task_prompt or "").strip()
        payload["mode"] = str(payload.get("mode") or team_mode).strip() or "human_governed"

        workflow_payload = payload.get("workflow") or {}
        if not isinstance(workflow_payload, Mapping):
            workflow_payload = {}
        payload["workflow"] = {
            "name": str(workflow_payload.get("name") or workflow_name).strip(),
            "description": str(workflow_payload.get("description") or description).strip(),
            "organization": str(workflow_payload.get("organization") or organization).strip(),
            "team_mode": str(workflow_payload.get("team_mode") or team_mode).strip() or "human_governed",
        }

        plan_payload = payload.get("plan") or {}
        if not isinstance(plan_payload, Mapping):
            plan_payload = {}
        tasks = _normalize_tasks(plan_payload.get("tasks"))
        if not tasks and graph_definition is not None:
            tasks = [
                {
                    "id": str(getattr(node, "id", "") or f"task-{index + 1}").strip(),
                    "title": str(getattr(node, "id", "") or f"Task {index + 1}").strip(),
                    "status": "pending",
                    "owner": str(getattr(node, "id", "") or "").strip(),
                    "node_id": str(getattr(node, "id", "") or "").strip(),
                }
                for index, node in enumerate(getattr(graph_definition, "nodes", []) or [])
                if str(getattr(node, "id", "") or "").strip()
            ]
        payload["plan"] = {
            "summary": str(plan_payload.get("summary") or description or initial_instruction).strip(),
            "tasks": tasks,
        }

        memory_payload = payload.get("memory") or {}
        if not isinstance(memory_payload, Mapping):
            memory_payload = {}
        payload["memory"] = {
            "facts": _trimmed_lines(memory_payload.get("facts")),
            "assumptions": _trimmed_lines(memory_payload.get("assumptions")),
            "open_questions": _trimmed_lines(memory_payload.get("open_questions")),
            "decisions": _trimmed_lines(memory_payload.get("decisions")),
        }

        payload["approvals"] = _normalize_approvals(payload.get("approvals"))
        payload["artifacts"] = _normalize_artifacts(payload.get("artifacts"))
        replay_payload = payload.get("replay") or {}
        if not isinstance(replay_payload, Mapping):
            replay_payload = {}
        payload["replay"] = {
            "target_task_id": str(replay_payload.get("target_task_id") or "").strip(),
            "target_task_title": str(replay_payload.get("target_task_title") or "").strip(),
            "requested_at": replay_payload.get("requested_at"),
        }
        payload["meta"] = {
            "updated_at": _now(),
            "source": "workflow_seed",
        }
        return payload

    def update_task_status_for_node(
        self,
        existing: Mapping[str, Any] | None,
        *,
        node_id: str,
        status: str,
        output_preview: Any = None,
        output_text: Any = None,
        output_size: Any = None,
        reused_replay_output: bool = False,
        replay_injected_predecessors: list[str] | None = None,
    ) -> tuple[Dict[str, Any], Dict[str, Any] | None]:
        payload = self.initialize_state(
            yaml_file=str((existing or {}).get("workflow", {}).get("name") or ""),
            task_prompt=str((existing or {}).get("goal") or ""),
            existing=existing,
        )

        normalized_node_id = str(node_id or "").strip()
        if not normalized_node_id:
            return payload, None
        now = _now()
        normalized_output_preview = _normalize_output_preview(output_preview)
        normalized_output_text = _normalize_output_text(output_text)
        normalized_output_size = _coerce_int(output_size)
        normalized_replay_injected_predecessors = [
            str(value or "").strip()
            for value in (replay_injected_predecessors or [])
            if str(value or "").strip()
        ]

        tasks = list(payload.get("plan", {}).get("tasks", []))
        task_index = -1
        for index, task in enumerate(tasks):
            task_node_id = str(task.get("node_id") or task.get("owner") or task.get("title") or "").strip()
            if task_node_id == normalized_node_id:
                task_index = index
                break

        if task_index < 0:
            tasks.append(
                {
                    "id": normalized_node_id,
                    "title": normalized_node_id,
                    "status": status,
                    "owner": normalized_node_id,
                    "node_id": normalized_node_id,
                    "started_at": now if status == "running" else None,
                    "completed_at": now if status == "done" else None,
                    "output_preview": normalized_output_preview,
                    "output_size": normalized_output_size,
                    "reused_replay_output": bool(reused_replay_output),
                    "reused_at": now if reused_replay_output and status == "done" else None,
                    "replay_injected_predecessors": normalized_replay_injected_predecessors,
                    "injected_at": now if normalized_replay_injected_predecessors else None,
                }
            )
            task = tasks[-1]
        else:
            task = dict(tasks[task_index])
            task["status"] = status
            task.setdefault("owner", normalized_node_id)
            task.setdefault("node_id", normalized_node_id)
            task.setdefault("started_at", None)
            task.setdefault("completed_at", None)
            task.setdefault("output_preview", "")
            task.setdefault("output_size", 0)
            task.setdefault("reused_replay_output", False)
            task.setdefault("reused_at", None)
            task.setdefault("replay_injected_predecessors", [])
            task.setdefault("injected_at", None)
            if status == "running":
                task["started_at"] = task.get("started_at") or now
                task["completed_at"] = None
                task["output_preview"] = ""
                task["output_size"] = 0
                task["reused_replay_output"] = False
                task["reused_at"] = None
                task["replay_injected_predecessors"] = normalized_replay_injected_predecessors
                task["injected_at"] = now if normalized_replay_injected_predecessors else None
            if status == "done":
                task["completed_at"] = now
                task["output_preview"] = normalized_output_preview
                task["output_size"] = normalized_output_size
                task["reused_replay_output"] = bool(reused_replay_output)
                task["reused_at"] = now if reused_replay_output else None
            tasks[task_index] = task

        payload["plan"]["tasks"] = tasks
        artifacts = _normalize_artifacts(payload.get("artifacts"))
        task_outputs = dict(artifacts.get("task_outputs", {}))
        task_outputs[str(task.get("id") or normalized_node_id)] = {
            "task_id": str(task.get("id") or normalized_node_id),
            "node_id": str(task.get("node_id") or normalized_node_id),
            "title": str(task.get("title") or normalized_node_id),
            "status": str(task.get("status") or status),
            "output_preview": str(task.get("output_preview") or ""),
            "output_text": normalized_output_text,
            "output_size": _coerce_int(task.get("output_size")),
            "reused_replay_output": bool(task.get("reused_replay_output", False)),
            "reused_at": task.get("reused_at"),
            "replay_injected_predecessors": list(task.get("replay_injected_predecessors") or []),
            "injected_at": task.get("injected_at"),
            "updated_at": now,
        }
        payload["artifacts"] = {
            **artifacts,
            "task_outputs": task_outputs,
        }
        payload["meta"] = {
            "updated_at": now,
            "source": "runtime_event",
        }
        return payload, task

    def apply_review_directive(
        self,
        existing: Mapping[str, Any] | None,
        *,
        reviewer_node_id: str,
        output_text: Any,
    ) -> tuple[Dict[str, Any], Dict[str, Any] | None]:
        payload = self.initialize_state(
            yaml_file=str((existing or {}).get("workflow", {}).get("name") or ""),
            task_prompt=str((existing or {}).get("goal") or ""),
            existing=existing,
        )

        directives = _parse_key_value_lines(output_text)
        verdict = str(
            directives.get("review_decision")
            or directives.get("review_verdict")
            or directives.get("verdict")
            or ""
        ).strip().upper()
        if verdict not in {"REWORK", "REJECT", "REVISE", "REPLAY"}:
            return payload, None

        replay_target_id = str(
            directives.get("replay_target")
            or directives.get("replay_task")
            or directives.get("rollback_target")
            or directives.get("rollback_task")
            or ""
        ).strip()
        if not replay_target_id:
            return payload, None

        tasks = list(payload.get("plan", {}).get("tasks", []))
        target_task = None
        for task in tasks:
            if not isinstance(task, Mapping):
                continue
            if str(task.get("id") or task.get("node_id") or "").strip() == replay_target_id:
                target_task = task
                break

        replay_target_title = str((target_task or {}).get("title") or replay_target_id).strip()
        note = str(
            directives.get("review_note")
            or directives.get("approval_note")
            or directives.get("review_summary")
            or ""
        ).strip()
        now = _now()

        payload["replay"] = {
            "target_task_id": replay_target_id,
            "target_task_title": replay_target_title,
            "requested_at": now,
        }

        approval = {
            "id": f"review-replay-{reviewer_node_id}-{int(now * 1000)}",
            "title": f"Review requested replay from {replay_target_title}",
            "status": "open",
            "blocking": True,
            "note": note,
            "created_at": now,
            "resolved_at": None,
        }
        approvals = _normalize_approvals(payload.get("approvals"))
        approvals.append(approval)
        payload["approvals"] = approvals

        artifacts = _normalize_artifacts(payload.get("artifacts"))
        payload["artifacts"] = {
            **artifacts,
            "review": {
                "last_directive": {
                    "reviewer_node_id": str(reviewer_node_id or "").strip(),
                    "verdict": verdict,
                    "approval_id": str(approval["id"] or "").strip(),
                    "replay_target_id": replay_target_id,
                    "replay_target_title": replay_target_title,
                    "note": note,
                    "created_at": now,
                },
            },
        }
        payload["meta"] = {
            "updated_at": now,
            "source": "review_directive",
        }
        return payload, {
            "reviewer_node_id": str(reviewer_node_id or "").strip(),
            "verdict": verdict,
            "replay_target_id": replay_target_id,
            "replay_target_title": replay_target_title,
            "note": note,
            "approval": approval,
        }

    def merge_state(self, existing: Mapping[str, Any] | None, incoming: Mapping[str, Any] | None) -> Dict[str, Any]:
        base = self.empty_state()
        if existing:
            base = self.initialize_state(
                yaml_file=str((existing.get("workflow") or {}).get("name") or ""),
                task_prompt=str(existing.get("goal") or ""),
                existing=existing,
            )

        payload = deepcopy(base)
        incoming = deepcopy(incoming or {})
        if "goal" in incoming:
            payload["goal"] = str(incoming.get("goal") or "").strip()
        if "mode" in incoming:
            payload["mode"] = str(incoming.get("mode") or payload["mode"]).strip() or payload["mode"]

        workflow_payload = incoming.get("workflow")
        if isinstance(workflow_payload, Mapping):
            for key in ("name", "description", "organization", "team_mode"):
                if key in workflow_payload:
                    payload["workflow"][key] = str(workflow_payload.get(key) or "").strip()

        plan_payload = incoming.get("plan")
        if isinstance(plan_payload, Mapping):
            if "summary" in plan_payload:
                payload["plan"]["summary"] = str(plan_payload.get("summary") or "").strip()
            if "tasks" in plan_payload:
                payload["plan"]["tasks"] = _normalize_tasks(plan_payload.get("tasks"))

        memory_payload = incoming.get("memory")
        if isinstance(memory_payload, Mapping):
            for key in ("facts", "assumptions", "open_questions", "decisions"):
                if key in memory_payload:
                    payload["memory"][key] = _trimmed_lines(memory_payload.get(key))

        if "approvals" in incoming:
            payload["approvals"] = _normalize_approvals(incoming.get("approvals"))

        artifacts_payload = incoming.get("artifacts")
        if isinstance(artifacts_payload, Mapping):
            payload["artifacts"] = _normalize_artifacts(artifacts_payload)

        replay_payload = incoming.get("replay")
        if isinstance(replay_payload, Mapping):
            payload["replay"] = {
                "target_task_id": str(replay_payload.get("target_task_id") or "").strip(),
                "target_task_title": str(replay_payload.get("target_task_title") or "").strip(),
                "requested_at": replay_payload.get("requested_at"),
            }

        payload["meta"] = {
            "updated_at": _now(),
            "source": "user_update",
        }
        return payload

    def build_update_events(self, previous: Mapping[str, Any] | None, current: Mapping[str, Any]) -> List[Dict[str, Any]]:
        previous = deepcopy(previous or self.empty_state())
        current = deepcopy(current)
        events: List[Dict[str, Any]] = [
            {
                "type": "team_state_updated",
                "data": {
                    "team_state": current,
                },
            }
        ]

        if previous.get("plan") != current.get("plan"):
            events.append(
                {
                    "type": "plan_updated",
                    "data": {
                        "plan": current.get("plan", {}),
                        "team_state": current,
                    },
                }
            )

        if previous.get("memory") != current.get("memory"):
            events.append(
                {
                    "type": "memory_updated",
                    "data": {
                        "memory": current.get("memory", {}),
                        "team_state": current,
                    },
                }
            )

        if previous.get("replay") != current.get("replay"):
            events.append(
                {
                    "type": "replay_requested",
                    "data": {
                        "replay": current.get("replay", {}),
                        "team_state": current,
                    },
                }
            )

        prev_review = (((previous.get("artifacts") or {}).get("review") or {}).get("last_directive") or {})
        curr_review = (((current.get("artifacts") or {}).get("review") or {}).get("last_directive") or {})
        if prev_review != curr_review and curr_review:
            events.append(
                {
                    "type": "review_replay_suggested",
                    "data": {
                        "review": curr_review,
                        "replay": current.get("replay", {}),
                        "team_state": current,
                    },
                }
            )

        prev_approvals = {item["id"]: item for item in previous.get("approvals", []) if isinstance(item, Mapping)}
        curr_approvals = {item["id"]: item for item in current.get("approvals", []) if isinstance(item, Mapping)}

        for approval_id, approval in curr_approvals.items():
            prev_status = str((prev_approvals.get(approval_id) or {}).get("status") or "")
            curr_status = str(approval.get("status") or "")
            if curr_status == "open" and prev_status != "open":
                events.append(
                    {
                        "type": "approval_required",
                        "data": {
                            "approval": approval,
                            "team_state": current,
                        },
                    }
                )
            if curr_status == "resolved" and prev_status != "resolved":
                events.append(
                    {
                        "type": "approval_resolved",
                        "data": {
                            "approval": approval,
                            "team_state": current,
                        },
                    }
                )

        return events
