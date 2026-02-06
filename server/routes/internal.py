"""Internal API routes for inter-process communication.

These endpoints are used by MCP servers and other local processes to push
data into the WebSocket pipeline. Access is restricted to localhost.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from server.state import get_websocket_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/internal", tags=["internal"])


class ToolReportPayload(BaseModel):
    """Payload for MCP reporter tool-report POST requests."""
    session_id: str
    node_id: str = ""
    report_type: str  # "progress" or "issue"
    # Progress fields
    message: Optional[str] = None
    phase: Optional[str] = None
    # Issue fields
    description: Optional[str] = None
    severity: Optional[str] = "info"


def _is_localhost(request: Request) -> bool:
    """Check if the request originates from localhost."""
    client = request.client
    if client is None:
        return False
    host = client.host
    return host in ("127.0.0.1", "::1", "localhost")


@router.post("/tool-report")
async def tool_report(payload: ToolReportPayload, request: Request) -> Dict[str, Any]:
    """Receive a tool report from the MCP reporter and forward it via WebSocket."""
    if not _is_localhost(request):
        return {"status": "rejected", "detail": "localhost only"}

    manager = get_websocket_manager()

    if payload.session_id not in manager.active_connections:
        logger.debug(
            "tool-report for unknown session %s (may have disconnected)",
            payload.session_id,
        )
        return {"status": "ok", "delivered": False}

    if payload.report_type == "progress":
        log_message = f"[Progress] {payload.message or ''}"
        if payload.phase:
            log_message = f"[Progress:{payload.phase}] {payload.message or ''}"
        details: Dict[str, Any] = {
            "semantic_report": True,
            "report_type": "progress",
            "phase": payload.phase or "",
            "tool_name": "chatdev:report_progress",
        }
    elif payload.report_type == "issue":
        severity = payload.severity or "info"
        log_message = f"[Issue:{severity}] {payload.description or ''}"
        details = {
            "semantic_report": True,
            "report_type": "issue",
            "severity": severity,
            "tool_name": "chatdev:report_issue",
        }
    else:
        return {"status": "error", "detail": f"unknown report_type: {payload.report_type}"}

    ws_message = {
        "type": "log",
        "data": {
            "level": "INFO",
            "message": log_message,
            "node_id": payload.node_id,
            "event_type": "TOOL_CALL",
            "details": details,
        },
    }

    await manager.send_message(payload.session_id, ws_message)
    return {"status": "ok", "delivered": True}
