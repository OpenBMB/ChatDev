"""Write one text file through the filesystem MCP server.

A successful write is acknowledged without replaying the server's path-bearing
message into a model-visible Tool observation. The MCP error flag is authoritative.
"""

import asyncio
import sys

from _mcplib import _call, a, emit, workspace_root


TOOL_ID = "mcp.fs_write_file"
SERVER = "mcp-server-filesystem"
OPERATION = "write_file"


async def _write_file():
    return await asyncio.wait_for(
        _call(SERVER, [workspace_root()], OPERATION,
              {"path": a(1), "content": a(2)}),
        timeout=90,
    )


def main():
    try:
        result = asyncio.run(_write_file())
    except Exception as exc:
        emit({"status": "error", "tool": TOOL_ID,
              "message": f"MCP invocation failed: {type(exc).__name__}"})
        return 1
    if result.get("is_error") is not False:
        emit({"status": "error", "tool": TOOL_ID,
              "message": "MCP write_file reported an error"})
        return 1
    emit({"status": "success", "tool": TOOL_ID, "mcp_server": SERVER,
          "mcp_tool": OPERATION,
          "result": {"is_error": False,
                     "content": ["write_file completed successfully"]}})
    return 0


if __name__ == "__main__":
    sys.exit(main())
