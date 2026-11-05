"""Typed MCP mutation acknowledgments with the server error flag preserved.

The acknowledgment confirms invocation only; callers must check the requested
workspace state separately. Path-bearing server prose is not a public receipt.
"""
import asyncio

from _mcplib import _call, emit, workspace_root


def run_mutation(command, args, operation, arguments, timeout=90):
    args = [workspace_root() if str(item) == "/app" else item for item in args]

    async def invoke():
        return await asyncio.wait_for(_call(command, args, operation, arguments), timeout)

    try:
        result = asyncio.run(invoke())
    except Exception as exc:
        emit({"status": "error", "operation": operation, "completed": False,
              "error_code": "mcp_transport_failure", "error_type": type(exc).__name__})
        return 1
    if result.get("is_error") is not False:
        emit({"status": "error", "operation": operation, "completed": False,
              "error_code": "mcp_operation_failed"})
        # The transport completed. The manifest's result_status declaration
        # makes this a failed operation that a Controller can inspect/recover.
        return 0
    emit({"status": "success", "operation": operation, "completed": True})
    return 0
