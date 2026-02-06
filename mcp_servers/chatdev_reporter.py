"""ChatDev Reporter MCP Server.

Stdio MCP server that Claude Code uses to report semantic progress
and issues back to the ChatDev UI. Communicates via HTTP POST to the
ChatDev backend which forwards messages over WebSocket.

Environment variables (set by claude_code_provider via --mcp-config):
  CHATDEV_SERVER_URL  - Backend URL (default: http://127.0.0.1:8000)
  CHATDEV_SESSION_ID  - Active WebSocket session ID
  CHATDEV_NODE_ID     - Current workflow node ID
"""

import os

import requests
from fastmcp import FastMCP

mcp = FastMCP("ChatDev Reporter")

_SERVER_URL = os.environ.get("CHATDEV_SERVER_URL", "http://127.0.0.1:8000")
_SESSION_ID = os.environ.get("CHATDEV_SESSION_ID", "")
_NODE_ID = os.environ.get("CHATDEV_NODE_ID", "")


def _post_report(report_type: str, payload: dict) -> dict:
    url = f"{_SERVER_URL}/api/internal/tool-report"
    body = {
        "session_id": _SESSION_ID,
        "node_id": _NODE_ID,
        "report_type": report_type,
        **payload,
    }
    try:
        resp = requests.post(url, json=body, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, OSError) as exc:
        return {"status": "error", "detail": str(exc)}


@mcp.tool
def report_progress(message: str, phase: str = "") -> str:
    """Report progress to ChatDev UI. Use at natural transition points
    such as finishing analysis, starting implementation, running tests, etc.
    Keep reports concise (1-2 sentences)."""
    _post_report("progress", {"message": message, "phase": phase})
    return f"Progress reported: {message}"


@mcp.tool
def report_issue(description: str, severity: str = "info") -> str:
    """Report an issue or warning to ChatDev UI.
    severity: info, warning, or error."""
    _post_report("issue", {"description": description, "severity": severity})
    return f"Issue reported ({severity}): {description}"


if __name__ == "__main__":
    mcp.run()
