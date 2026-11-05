"""Regression tests: ToolManager.get_tool_specs inside a running event loop.

Issue #709: the MCP spec builders called asyncio.run() unconditionally, which
raises "RuntimeError: asyncio.run() cannot be called from a running event loop"
when get_tool_specs() is invoked from a thread that already runs an event loop
(e.g. FastAPI handlers, async tests, or embedded async runtimes).
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List

from entity.configs import ToolingConfig
from entity.configs.node.tooling import McpLocalConfig, McpRemoteConfig
from runtime.node.agent.tool.tool_manager import ToolManager


@dataclass
class _FakeMcpTool:
    name: str
    description: str = ""
    inputSchema: Dict[str, Any] = field(
        default_factory=lambda: {"type": "object", "properties": {}}
    )


def _remote_tooling_config(server: str = "http://127.0.0.1:9/sse") -> ToolingConfig:
    return ToolingConfig(
        type="mcp_remote",
        config=McpRemoteConfig(server=server, path="node.tooling.mcp_remote"),
        path="node.tooling",
    )


def _local_tooling_config() -> ToolingConfig:
    return ToolingConfig(
        type="mcp_local",
        config=McpLocalConfig(
            command="python", args=["-m", "fake_mcp_server"], path="node.tooling.mcp_local"
        ),
        path="node.tooling",
    )


def test_get_tool_specs_inside_running_loop_mcp_remote(monkeypatch) -> None:
    manager = ToolManager()

    async def fake_fetch_http(self, server_url, *, headers=None, timeout=None, attempts=3):
        await asyncio.sleep(0)  # genuinely exercise the running loop
        return [_FakeMcpTool("remote_echo", description="echo over http")]

    monkeypatch.setattr(ToolManager, "_fetch_mcp_tools_http", fake_fetch_http)
    config = _remote_tooling_config()

    async def scenario() -> List[Any]:
        # A loop is running in this thread; get_tool_specs() is synchronous.
        return manager.get_tool_specs([config])

    specs = asyncio.run(scenario())
    assert [spec.name for spec in specs] == ["remote_echo"]
    assert specs[0].metadata["mode"] == "remote"


def test_get_tool_specs_inside_running_loop_mcp_local(monkeypatch) -> None:
    manager = ToolManager()

    async def fake_fetch_stdio(self, config, launch_key):
        await asyncio.sleep(0)
        return [_FakeMcpTool("stdio_echo", description="echo over stdio")]

    monkeypatch.setattr(ToolManager, "_fetch_mcp_tools_stdio", fake_fetch_stdio)
    config = _local_tooling_config()

    async def scenario() -> List[Any]:
        return manager.get_tool_specs([config])

    specs = asyncio.run(scenario())
    assert [spec.name for spec in specs] == ["stdio_echo"]
    assert specs[0].metadata["mode"] == "local"


def test_get_tool_specs_without_running_loop_mcp_remote(monkeypatch) -> None:
    """The plain synchronous path must keep working (no loop in this thread)."""
    manager = ToolManager()

    async def fake_fetch_http(self, server_url, *, headers=None, timeout=None, attempts=3):
        await asyncio.sleep(0)
        return [_FakeMcpTool("sync_echo")]

    monkeypatch.setattr(ToolManager, "_fetch_mcp_tools_http", fake_fetch_http)
    config = _remote_tooling_config()

    specs = manager.get_tool_specs([config])
    assert [spec.name for spec in specs] == ["sync_echo"]
