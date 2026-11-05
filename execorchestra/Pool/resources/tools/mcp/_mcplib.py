"""Shared MCP client for mcp_server tool wrappers.
Launches a real recognized MCP server as a subprocess, performs the MCP stdio
handshake, calls one tool, and returns its result. Uses the official `mcp` SDK.
"""
import sys, json, asyncio, os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

def emit(o):
    payload = json.dumps(o, ensure_ascii=False, default=str) + "\n"
    try:
        sys.stdout.write(payload)
        sys.stdout.flush()
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        safe_payload = payload.encode(encoding, errors="replace").decode(encoding, errors="replace")
        sys.stdout.write(safe_payload)
        sys.stdout.flush()

async def _call(command, args, tool, arguments):
    params = StdioServerParameters(command=command, args=list(args), env=None)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool(tool, arguments or {})
            blocks = []
            for c in (res.content or []):
                blocks.append(getattr(c, "text", None) or getattr(c, "data", None) or str(c))
            return {"is_error": bool(getattr(res, "isError", False)), "content": blocks}

def run(tool_id, command, args, tool, arguments, timeout=90):
    # Manifests and wrappers use the container mount name, while direct host
    # execution has no /app mount. Normalize the runtime root once here so all
    # filesystem MCP tools behave identically in both execution environments.
    args = [workspace_root() if str(item) == "/app" else item for item in args]
    async def _m():
        return await asyncio.wait_for(_call(command, args, tool, arguments), timeout)
    try:
        r = asyncio.run(_m())
        emit({"status": "success", "tool": tool_id, "mcp_server": command, "mcp_tool": tool, "result": r})
    except Exception as e:
        emit({"status": "error", "tool": tool_id, "message": f"{type(e).__name__}: {e}"})
        sys.exit(1)

def a(i, d=None): return sys.argv[i] if len(sys.argv) > i else d

def workspace_root():
    configured = os.environ.get("SGAR_WORKSPACE_ROOT")
    if configured and os.path.isdir(configured):
        return configured
    return os.getcwd()
