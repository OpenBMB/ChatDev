"""
Automatic agent-visibility integration for ChatDev workflows.

Subclasses WorkflowLogger so that every workflow run — regardless of which
YAML is used — streams live events to the agent-visibility dashboard at
http://localhost:4242 (override with VISIBILITY_URL env var).

Usage: injected automatically via execute_sync.py; no YAML changes needed.
"""

import json
import os
import re
import threading
import urllib.request
from typing import Any, Dict, List, Optional

from entity.enums import EventType, LogLevel
from utils.logger import WorkflowLogger

_DASHBOARD_URL = os.environ.get("VISIBILITY_URL", "http://localhost:4242")

# Map node types to dashboard roles
_TYPE_TO_ROLE = {
    "agent": "worker",
    "human": "worker",
    "python_runner": "coder",
    "orchestrator": "orchestrator",
}

# Heuristic role upgrade based on node label keywords
_LABEL_ROLE_HINTS = {
    "ceo": "orchestrator",
    "chief": "orchestrator",
    "manager": "orchestrator",
    "director": "orchestrator",
    "orchestrat": "orchestrator",
    "coder": "coder",
    "programmer": "coder",
    "developer": "coder",
    "engineer": "coder",
    "reviewer": "critic",
    "critic": "critic",
    "tester": "critic",
    "qa": "critic",
    "research": "researcher",
    "analyst": "researcher",
}


def _post(tool: str, args: dict) -> None:
    """Fire-and-forget POST to the visibility dashboard in a background thread."""
    clean = {k: v for k, v in args.items() if v is not None}

    def _do():
        try:
            body = json.dumps({"tool": tool, "args": clean}, default=str).encode()
            req = urllib.request.Request(
                f"{_DASHBOARD_URL}/tool",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=2)
        except Exception:
            pass  # dashboard being down must never crash a workflow

    threading.Thread(target=_do, daemon=True).start()


def _reset_sync() -> None:
    """Synchronous reset — call this before queuing any new-run events."""
    try:
        req = urllib.request.Request(
            f"{_DASHBOARD_URL}/reset",
            data=b"",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=2)
    except Exception:
        pass


def _slug(label: str) -> str:
    """'Chief Executive Officer' → 'chief_executive_officer'"""
    return re.sub(r"[^a-z0-9]+", "_", (label or "").lower()).strip("_") or "unknown"


def _infer_role(node_id: str, node_type: str) -> str:
    """Infer a dashboard role from node label and type."""
    label_lower = (node_id or "").lower()
    for keyword, role in _LABEL_ROLE_HINTS.items():
        if keyword in label_lower:
            return role
    return _TYPE_TO_ROLE.get(node_type or "agent", "worker")


class VisibilityLogger(WorkflowLogger):
    """
    Drop-in replacement for WorkflowLogger that automatically mirrors all
    workflow events to the agent-visibility dashboard.

    Intercepts add_log() *before* the parent's log-level filter so that
    EDGE_PROCESS (DEBUG) events are never silently dropped.
    """

    def __init__(
        self,
        workflow_id: str = None,
        log_level: LogLevel = LogLevel.DEBUG,
        use_structured_logging: bool = True,
        log_to_console: bool = True,
        *,
        task_prompt: str = None,
        graph_config=None,
    ) -> None:
        super().__init__(workflow_id, log_level, use_structured_logging, log_to_console)
        self._vis_task = task_prompt or "Workflow run"
        self._vis_registered: set = set()
        self._graph_config = graph_config

    def add_log(
        self,
        level: LogLevel,
        message: str = None,
        node_id: str = None,
        event_type: EventType = None,
        details: Dict[str, Any] = None,
        duration: float = None,
    ):
        # Forward to the dashboard BEFORE the parent's level filter so we
        # never miss DEBUG-level events (e.g. EDGE_PROCESS / trace arrows).
        self._forward(level, message, node_id, event_type, details or {}, duration)
        return super().add_log(level, message, node_id, event_type, details, duration)

    # ------------------------------------------------------------------
    # Internal event mapping
    # ------------------------------------------------------------------

    def _forward(
        self,
        level: LogLevel,
        message: Optional[str],
        node_id: Optional[str],
        event_type: Optional[EventType],
        details: Dict[str, Any],
        duration: Optional[float],
    ) -> None:
        ms = round(duration * 1000) if duration else None

        if event_type == EventType.WORKFLOW_START:
            self._vis_registered.clear()
            self._send_initial_state(self._vis_task)

        elif event_type == EventType.NODE_START and node_id:
            agent_id = _slug(node_id)
            # Lazy-register if not already done via graph definition
            if agent_id not in self._vis_registered:
                _post("register_agent", {"id": agent_id, "label": node_id, "role": "worker"})
                self._vis_registered.add(agent_id)
            _post("set_agent_state", {"agent_id": agent_id, "status": "active"})
            _post("log_event", {
                "agent": agent_id,
                "event_type": "start",
                "message": message or f"{node_id} started",
            })

        elif event_type == EventType.TOOL_CALL and node_id:
            agent_id = _slug(node_id)
            tool_name = details.get("tool_name", "tool")
            success = details.get("success", True)
            output = details.get("tool_result")
            # log_tool_call populates the Tools tab
            _post("log_tool_call", {
                "agent": agent_id,
                "tool_name": tool_name,
                "output": str(output)[:2000] if output else None,
                "error": None if success is not False else str(output),
                "latency_ms": ms,
            })
            # Also send a human-readable event to the log feed
            _post("log_event", {
                "agent": agent_id,
                "event_type": "tool" if success is not False else "fail",
                "message": f"Called {tool_name}",
                "latency_ms": ms,
            })

        elif event_type == EventType.MODEL_CALL and node_id:
            agent_id = _slug(node_id)
            model = details.get("model_name", "llm")
            response = details.get("output")
            # log_generation populates the Tools tab with the LLM turn
            _post("log_generation", {
                "agent": agent_id,
                "model": model,
                "response": str(response)[:4000] if response else None,
                "latency_ms": ms,
            })
            _post("log_event", {
                "agent": agent_id,
                "event_type": "reply",
                "message": f"LLM call ({model})",
                "latency_ms": ms,
            })

        elif event_type == EventType.EDGE_PROCESS and node_id:
            to_node = details.get("to_node")
            if to_node:
                _post("trace_step", {
                    "from_agent": _slug(node_id),
                    "to_agent": _slug(to_node),
                    "arrow_type": "result",
                })

        elif event_type == EventType.NODE_END and node_id:
            agent_id = _slug(node_id)
            _post("log_event", {
                "agent": agent_id,
                "event_type": "done",
                "message": message or f"{node_id} finished",
                "latency_ms": ms,
            })
            _post("set_agent_state", {"agent_id": agent_id, "status": "done"})
            # Store the node output in the Memory tab
            output = details.get("output") if details else None
            if output:
                _post("set_memory", {
                    "key": node_id,
                    "value": str(output)[:300],
                    "op": "write",
                })

        elif event_type == EventType.WORKFLOW_END:
            success = details.get("success", True)
            _post("finish_run", {"status": "done" if success else "error"})

    def _send_initial_state(self, task: str) -> None:
        """
        Called synchronously after reset. Posts set_goal then registers the
        full graph so the canvas is populated before any node runs.
        All calls are inline (not threaded) to preserve ordering.
        """
        _post("set_goal", {"goal": task})

        if not self._graph_config:
            return

        try:
            nodes: List = self._graph_config.get_node_definitions()
            edges: List = self._graph_config.get_edge_definitions()
        except Exception:
            return

        for node in nodes:
            agent_id = _slug(node.id)
            role = _infer_role(node.id, getattr(node, "type", "agent"))
            _post("register_agent", {"id": agent_id, "label": node.id, "role": role})
            self._vis_registered.add(agent_id)

        for edge in edges:
            source = getattr(edge, "source", None)
            target = getattr(edge, "target", None)
            if source and target:
                _post("trace_step", {
                    "from_agent": _slug(source),
                    "to_agent": _slug(target),
                    "arrow_type": "msg",
                })

        # Build plan with correct schema: {agent, task, depends_on}
        node_index = {node.id: i for i, node in enumerate(nodes)}
        plan_tasks = []
        for i, node in enumerate(nodes):
            incoming = [
                node_index[e.source]
                for e in edges
                if getattr(e, "target", None) == node.id and e.source in node_index
            ]
            plan_tasks.append({
                "agent": _slug(node.id),
                "task": node.id,
                "depends_on": incoming,
            })
        _post("set_plan", {"tasks": plan_tasks})
