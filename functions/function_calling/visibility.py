"""
Agent-visibility integration for ChatDev workflows.

Provides function tools that stream agent events to the agent-visibility
dashboard (https://github.com/yourusername/agent-visibility-cli).

Start the dashboard before running your workflow:
    node src/server.js        # dashboard on http://localhost:4242

Then add any of the functions below to your agent's tooling list.
All calls are fire-and-forget — a missing dashboard never crashes the workflow.
"""

import json
import os
import urllib.error
import urllib.request
from typing import Annotated, Literal, Optional

from utils.function_catalog import ParamMeta

_DASHBOARD_URL = os.environ.get("VISIBILITY_URL", "http://localhost:4242")


def _post(tool: str, args: dict) -> str:
    """Fire-and-forget POST to the visibility dashboard. Returns status string."""
    body = json.dumps({"tool": tool, "args": args}).encode()
    try:
        req = urllib.request.Request(
            f"{_DASHBOARD_URL}/tool",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=2)
        return "ok"
    except Exception as exc:
        return f"visibility dashboard unreachable: {exc}"


def set_goal(
    goal: Annotated[str, ParamMeta(description="Short description of the overall run goal or task")],
    run_id: Annotated[
        Optional[str],
        ParamMeta(description="Optional unique run identifier; auto-generated if omitted"),
    ] = None,
) -> str:
    """
    Set the run goal and mark the workflow as started on the visibility dashboard.

    Call this once at the beginning of a workflow run, before registering agents.
    The goal text is displayed prominently in the dashboard header.
    """
    args: dict = {"goal": goal}
    if run_id:
        args["run_id"] = run_id
    return _post("set_goal", args)


def register_agent(
    agent_id: Annotated[str, ParamMeta(description="Unique identifier for this agent (e.g. 'pm', 'coder')")],
    label: Annotated[str, ParamMeta(description="Human-readable display name shown on the dashboard canvas")],
    role: Annotated[
        Literal["orchestrator", "worker", "researcher", "coder", "critic", "synthesiser"],
        ParamMeta(description="Agent role, controls the icon and colour on the canvas"),
    ],
    model: Annotated[Optional[str], ParamMeta(description="Model name, e.g. 'gpt-4o'")] = None,
    reports_to: Annotated[
        Optional[str], ParamMeta(description="agent_id of the parent/supervisor agent")
    ] = None,
    color: Annotated[
        Optional[str], ParamMeta(description="Override hex colour for this agent's node, e.g. '#7c3aed'")
    ] = None,
) -> str:
    """
    Register an agent with the visibility dashboard.

    Creates a node on the canvas for the agent. Call this for every agent in
    the workflow, ideally before the agent starts its first task.
    """
    args: dict = {"id": agent_id, "label": label, "role": role}
    if model:
        args["model"] = model
    if reports_to:
        args["reports_to"] = reports_to
    if color:
        args["color"] = color
    return _post("register_agent", args)


def log_event(
    agent: Annotated[str, ParamMeta(description="agent_id of the agent generating this event")],
    event_type: Annotated[
        Literal[
            "start", "plan", "route", "reply", "tool",
            "result", "pass", "fail", "retry", "warn", "error", "done",
        ],
        ParamMeta(description="Event category; controls icon and colour in the event log"),
    ],
    message: Annotated[str, ParamMeta(description="Human-readable description of what happened")],
    tokens: Annotated[
        Optional[int], ParamMeta(description="Token count for this step, if known")
    ] = None,
    latency_ms: Annotated[
        Optional[float], ParamMeta(description="Wall-clock latency of this step in milliseconds")
    ] = None,
) -> str:
    """
    Log an agent event to the visibility dashboard event feed.

    Use this liberally to narrate what an agent is doing — planning, calling a
    tool, producing a result, hitting an error, and so on.
    """
    args: dict = {"agent": agent, "event_type": event_type, "message": message}
    if tokens is not None:
        args["tokens"] = tokens
    if latency_ms is not None:
        args["latency_ms"] = latency_ms
    return _post("log_event", args)


def trace_step(
    from_agent: Annotated[str, ParamMeta(description="agent_id of the sender")],
    to_agent: Annotated[str, ParamMeta(description="agent_id of the receiver")],
    label: Annotated[
        Optional[str], ParamMeta(description="Short label shown on the arrow, e.g. 'handoff plan'")
    ] = None,
    arrow_type: Annotated[
        Literal["msg", "result", "retry", "tool"],
        ParamMeta(description="Arrow style: msg=blue, result=green, retry=orange, tool=purple"),
    ] = "msg",
) -> str:
    """
    Draw a directed arrow between two agents on the visibility canvas.

    Call this whenever one agent hands work to another, so the dashboard shows
    the message flow in real time.
    """
    args: dict = {"from_agent": from_agent, "to_agent": to_agent, "arrow_type": arrow_type}
    if label:
        args[label] = label
    return _post("trace_step", args)


def set_agent_state(
    agent_id: Annotated[str, ParamMeta(description="agent_id to update")],
    status: Annotated[
        Literal["idle", "running", "active", "done", "error"],
        ParamMeta(description="New status; controls the badge colour on the canvas node"),
    ],
) -> str:
    """
    Update an agent's status badge on the visibility dashboard.

    Use 'active' or 'running' when the agent starts working, and 'done' or
    'error' when it finishes.
    """
    return _post("set_agent_state", {"agent_id": agent_id, "status": status})


def set_plan(
    tasks: Annotated[
        list,
        ParamMeta(
            description=(
                "List of task objects, each with at minimum an 'id' and 'label' field "
                "and optionally 'agent' (agent_id responsible) and 'status'."
            )
        ),
    ],
) -> str:
    """
    Publish the workflow task plan to the Plan tab on the visibility dashboard.

    Pass a list of task dicts, e.g.:
        [{"id": "t1", "label": "Write code", "agent": "coder"},
         {"id": "t2", "label": "Review code", "agent": "reviewer"}]
    """
    return _post("set_plan", {"tasks": tasks})


def finish_run(
    status: Annotated[
        Literal["done", "error"],
        ParamMeta(description="Final run status"),
    ] = "done",
) -> str:
    """
    Mark the current workflow run as complete on the visibility dashboard.

    Call this in the last agent or a teardown step. The dashboard will stop
    its live timer and display the final status badge.
    """
    return _post("finish_run", {"status": status})
