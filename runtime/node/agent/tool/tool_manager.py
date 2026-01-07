"""Tool management for function calling and MCP."""

import asyncio
import base64
import binascii
from dataclasses import dataclass
import inspect
import logging
import mimetypes
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

from fastmcp import Client
from fastmcp.client.client import CallToolResult as FastMcpCallToolResult
from fastmcp.client.transports import StreamableHttpTransport, StdioTransport
from mcp import types

from entity.configs import ToolingConfig, ConfigError
from entity.configs.node.tooling import FunctionToolConfig, McpLocalConfig, McpRemoteConfig
from entity.messages import MessageBlock, MessageBlockType
from entity.tool_spec import ToolSpec
from utils.attachments import AttachmentStore
from utils.function_manager import FUNCTION_CALLING_DIR, FunctionManager

logger = logging.getLogger(__name__)

DEFAULT_MCP_HTTP_TIMEOUT = 10.0


@dataclass
class _FunctionManagerCacheEntry:
    manager: FunctionManager
    auto_loaded: bool = False


class ToolManager:
    """Manage function tools for agent nodes."""

    def __init__(self) -> None:
        self._functions_dir: Path = FUNCTION_CALLING_DIR
        self._function_managers: Dict[Path, _FunctionManagerCacheEntry] = {}
        self._mcp_tool_cache: Dict[str, List[Any]] = {}
        self._mcp_stdio_clients: Dict[str, "_StdioClientWrapper"] = {}

    def _get_function_manager(self) -> FunctionManager:
        entry = self._function_managers.get(self._functions_dir)
        if entry is None:
            entry = _FunctionManagerCacheEntry(manager=FunctionManager(self._functions_dir))
            self._function_managers[self._functions_dir] = entry
        return entry.manager

    def _ensure_functions_loaded(self, auto_load: bool) -> None:
        if not auto_load:
            return
        entry = self._function_managers.setdefault(
            self._functions_dir,
            _FunctionManagerCacheEntry(manager=FunctionManager(self._functions_dir))
        )
        if not entry.auto_loaded:
            entry.manager.load_functions()
            entry.auto_loaded = True

    async def _fetch_mcp_tools_http(
        self,
        server_url: str,
        *,
        headers: Dict[str, str] | None = None,
        timeout: float | None = None,
        attempts: int = 3,
    ) -> List[Any]:
        delay = 0.5
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                client = Client(
                    transport=StreamableHttpTransport(server_url, headers=headers or None),
                    timeout=timeout or DEFAULT_MCP_HTTP_TIMEOUT,
                )
                async with client:
                    return await client.list_tools()
            except Exception as exc:  # pragma: no cover - passthrough to caller
                last_error = exc
                if attempt == attempts:
                    raise
                await asyncio.sleep(delay)
                delay *= 2
        if last_error:
            raise last_error
        return []

    async def _fetch_mcp_tools_stdio(self, config: McpLocalConfig, launch_key: str) -> List[Any]:
        client = self._get_stdio_client(config, launch_key)
        return client.list_tools()

    def get_tool_specs(self, tool_configs: List[ToolingConfig] | None) -> List[ToolSpec]:
        """Return provider-agnostic tool specifications for the given config list."""
        if not tool_configs:
            return []

        specs: List[ToolSpec] = []
        seen_tools: set[str] = set()

        for idx, tool_config in enumerate(tool_configs):
            current_specs: List[ToolSpec] = []
            if tool_config.type == "function":
                config = tool_config.as_config(FunctionToolConfig)
                if not config:
                    raise ValueError("Function tooling configuration missing")
                current_specs = self._build_function_specs(config)
            elif tool_config.type == "mcp_remote":
                config = tool_config.as_config(McpRemoteConfig)
                if not config:
                    raise ValueError("MCP remote configuration missing")
                current_specs = self._build_mcp_remote_specs(config)
            elif tool_config.type == "mcp_local":
                config = tool_config.as_config(McpLocalConfig)
                if not config:
                    raise ValueError("MCP local configuration missing")
                current_specs = self._build_mcp_local_specs(config)
            else:
                 # Skip unknown types or raise error? Existing code raised error in execute but ignored in get_specs?
                 # Better to ignore or log warning for robustness, but let's stick to safe behavior.
                 pass

            prefix = tool_config.prefix
            for spec in current_specs:
                original_name = spec.name
                final_name = f"{prefix}_{original_name}" if prefix else original_name

                if final_name in seen_tools:
                    raise ConfigError(
                        f"Duplicate tool name '{final_name}' detected. "
                        f"Please use a unique 'prefix' in your tooling configuration."
                    )
                seen_tools.add(final_name)

                # Update spec
                spec.name = final_name
                spec.metadata["_config_index"] = idx
                spec.metadata["original_name"] = original_name
                specs.append(spec)

        return specs

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        tool_config: ToolingConfig,
        *,
        tool_context: Dict[str, Any] | None = None,
    ) -> Any:
        """Execute a tool using the provided configuration."""
        if tool_config.type == "function":
            config = tool_config.as_config(FunctionToolConfig)
            if not config:
                raise ValueError("Function tooling configuration missing")
            return self._execute_function_tool(tool_name, arguments, config, tool_context)

        if tool_config.type == "mcp_remote":
            config = tool_config.as_config(McpRemoteConfig)
            if not config:
                raise ValueError("MCP remote configuration missing")
            return await self._execute_mcp_remote_tool(tool_name, arguments, config, tool_context)

        if tool_config.type == "mcp_local":
            config = tool_config.as_config(McpLocalConfig)
            if not config:
                raise ValueError("MCP local configuration missing")
            return await self._execute_mcp_local_tool(tool_name, arguments, config, tool_context)

        raise ValueError(f"Unsupported tool type: {tool_config.type}")

    def _build_function_specs(self, config: FunctionToolConfig) -> List[ToolSpec]:
        self._ensure_functions_loaded(config.auto_load)
        specs: List[ToolSpec] = []
        for tool in config.tools:
            parameters = tool.get("parameters")
            if not isinstance(parameters, Mapping):
                parameters = {"type": "object", "properties": {}}
            specs.append(
                ToolSpec(
                    name=tool.get("name", ""),
                    description=tool.get("description") or "",
                    parameters=parameters,
                    metadata={"source": "function"},
                )
            )
        return specs

    def _build_mcp_remote_specs(self, config: McpRemoteConfig) -> List[ToolSpec]:
        cache_key = f"remote:{config.cache_key()}"
        tools = self._mcp_tool_cache.get(cache_key)
        if tools is None:
            tools = asyncio.run(
                self._fetch_mcp_tools_http(
                    config.server,
                    headers=config.headers,
                    timeout=config.timeout,
                )
            )
            self._mcp_tool_cache[cache_key] = tools

        specs: List[ToolSpec] = []
        for tool in tools:
            specs.append(
                ToolSpec(
                    name=tool.name,
                    description=tool.description or "",
                    parameters=tool.inputSchema or {"type": "object", "properties": {}},
                    metadata={"source": "mcp", "server": config.server, "mode": "remote"},
                )
            )
        return specs

    def _build_mcp_local_specs(self, config: McpLocalConfig) -> List[ToolSpec]:
        launch_key = config.cache_key()
        if not launch_key:
            raise ValueError("MCP local configuration missing launch key")

        cache_key = f"stdio:{launch_key}"
        tools = self._mcp_tool_cache.get(cache_key)
        if tools is None:
            tools = asyncio.run(self._fetch_mcp_tools_stdio(config, launch_key))
            self._mcp_tool_cache[cache_key] = tools

        specs: List[ToolSpec] = []
        for tool in tools:
            specs.append(
                ToolSpec(
                    name=tool.name,
                    description=tool.description or "",
                    parameters=tool.inputSchema or {"type": "object", "properties": {}},
                    metadata={"source": "mcp", "server": "stdio", "mode": "local"},
                )
            )
        return specs

    def _execute_function_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        config: FunctionToolConfig,
        tool_context: Dict[str, Any] | None = None,
    ) -> Any:
        mgr = self._get_function_manager()
        if config.auto_load:
            mgr.load_functions()
        func = mgr.get_function(tool_name)
        if func is None:
            raise ValueError(f"Tool {tool_name} not found in {self._functions_dir}")

        call_args = dict(arguments or {})
        if (
            tool_context is not None
            # and "_context" not in call_args
            and self._function_accepts_context(func)
        ):
            call_args["_context"] = tool_context
        return func(**call_args)

    def _function_accepts_context(self, func: Any) -> bool:
        try:
            signature = inspect.signature(func)
        except (ValueError, TypeError):
            return False
        for param in signature.parameters.values():
            if param.kind is inspect.Parameter.VAR_KEYWORD:
                return True
            if param.name == "_context" and param.kind in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            ):
                return True
        return False

    async def _execute_mcp_remote_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        config: McpRemoteConfig,
        tool_context: Dict[str, Any] | None = None,
    ) -> Any:
        client = Client(
            transport=StreamableHttpTransport(config.server, headers=config.headers or None),
            timeout=config.timeout or DEFAULT_MCP_HTTP_TIMEOUT,
        )
        async with client:
            result = await client.call_tool(tool_name, arguments)
        return self._normalize_mcp_result(tool_name, result, tool_context)

    async def _execute_mcp_local_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        config: McpLocalConfig,
        tool_context: Dict[str, Any] | None = None,
    ) -> Any:
        launch_key = config.cache_key()
        if not launch_key:
            raise ValueError("MCP local configuration missing launch key")
        stdio_client = self._get_stdio_client(config, launch_key)
        result = stdio_client.call_tool(tool_name, arguments)
        return self._normalize_mcp_result(tool_name, result, tool_context)

    def _normalize_mcp_result(
        self,
        tool_name: str,
        result: FastMcpCallToolResult,
        tool_context: Dict[str, Any] | None,
    ) -> Any:
        attachment_store = self._extract_attachment_store(tool_context)
        blocks = self._convert_mcp_content_to_blocks(tool_name, result.content, attachment_store)
        if blocks:
            return blocks
        if result.structured_content is not None:
            return result.structured_content
        if result.content:
            content = result.content[0]
            if isinstance(content, types.TextContent):
                return content.text
            return str(content)
        return None

    def _extract_attachment_store(self, tool_context: Dict[str, Any] | None) -> AttachmentStore | None:
        if not tool_context:
            return None
        candidate = tool_context.get("attachment_store")
        if isinstance(candidate, AttachmentStore):
            return candidate
        if candidate is not None:
            logger.warning(
                "attachment_store in tool_context is not AttachmentStore (got %s)",
                type(candidate).__name__,
            )
        return None

    def _convert_mcp_content_to_blocks(
        self,
        tool_name: str,
        contents: Sequence[types.ContentBlock] | None,
        attachment_store: AttachmentStore | None,
    ) -> List[MessageBlock]:
        blocks: List[MessageBlock] = []
        if not contents:
            return blocks
        for idx, content in enumerate(contents):
            converted = self._convert_single_mcp_block(tool_name, content, idx, attachment_store)
            if converted:
                blocks.extend(converted)
        return blocks

    def _convert_single_mcp_block(
        self,
        tool_name: str,
        content: types.ContentBlock,
        block_index: int,
        attachment_store: AttachmentStore | None,
    ) -> List[MessageBlock]:
        if isinstance(content, types.TextContent):
            return [MessageBlock.text_block(content.text)]
        if isinstance(content, types.ImageContent):
            return self._materialize_mcp_binary_block(
                tool_name,
                content.data,
                content.mimeType,
                MessageBlockType.IMAGE,
                block_index,
                attachment_store,
            )
        if isinstance(content, types.AudioContent):
            return self._materialize_mcp_binary_block(
                tool_name,
                content.data,
                content.mimeType,
                MessageBlockType.AUDIO,
                block_index,
                attachment_store,
            )
        if isinstance(content, types.EmbeddedResource):
            resource = content.resource
            if isinstance(resource, types.TextResourceContents):
                data_payload = {
                    "uri": str(resource.uri),
                    "mime_type": resource.mimeType,
                }
                return [
                    MessageBlock(
                        type=MessageBlockType.TEXT,
                        text=resource.text,
                        data={k: v for k, v in data_payload.items() if v is not None},
                    )
                ]
            if isinstance(resource, types.BlobResourceContents):
                extra = {
                    "resource_uri": str(resource.uri),
                }
                return self._materialize_mcp_binary_block(
                    tool_name,
                    resource.blob,
                    resource.mimeType,
                    self._message_block_type_from_mime(resource.mimeType),
                    block_index,
                    attachment_store,
                    extra=extra,
                )
        if isinstance(content, types.ResourceLink):
            data_payload = {
                "uri": str(content.uri),
                "mime_type": content.mimeType,
                "description": content.description,
            }
            return [
                MessageBlock(
                    type=MessageBlockType.DATA,
                    text=content.description or f"Resource link: {content.uri}",
                    data={k: v for k, v in data_payload.items() if v is not None},
                )
            ]
        logger.warning("Unhandled MCP content block type: %s", type(content).__name__)
        return []

    def _materialize_mcp_binary_block(
        self,
        tool_name: str,
        payload_b64: str,
        mime_type: str | None,
        block_type: MessageBlockType,
        block_index: int,
        attachment_store: AttachmentStore | None,
        *,
        extra: Dict[str, Any] | None = None,
    ) -> List[MessageBlock]:
        display_name = self._build_attachment_name(tool_name, block_type, block_index, mime_type)
        try:
            binary = base64.b64decode(payload_b64)
        except (binascii.Error, ValueError) as exc:
            logger.warning("Failed to decode MCP %s payload for %s: %s", block_type.value, tool_name, exc)
            return [
                MessageBlock.text_block(
                    f"[failed to decode {block_type.value} content from {tool_name}]"
                )
            ]

        metadata = {
            "source": "mcp_tool",
            "tool_name": tool_name,
            "block_type": block_type.value,
        }
        if extra:
            metadata.update(extra)

        if attachment_store is None:
            placeholder = (
                f"[binary content omitted: {display_name} ({mime_type or 'application/octet-stream'})]"
            )
            return [
                MessageBlock(
                    type=MessageBlockType.TEXT,
                    text=placeholder,
                    data={**metadata, "reason": "attachment_store_missing", "mime_type": mime_type},
                )
            ]

        record = attachment_store.register_bytes(
            binary,
            kind=block_type,
            mime_type=mime_type,
            display_name=display_name,
            extra=metadata,
        )
        return [record.as_message_block()]

    def _build_attachment_name(
        self,
        tool_name: str,
        block_type: MessageBlockType,
        block_index: int,
        mime_type: str | None,
    ) -> str:
        base = f"{tool_name}_{block_type.value}_{block_index + 1}".strip() or "attachment"
        safe_base = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in base)
        ext = mimetypes.guess_extension(mime_type or "") or ""
        return f"{safe_base}{ext}"

    def _message_block_type_from_mime(self, mime_type: str | None) -> MessageBlockType:
        if not mime_type:
            return MessageBlockType.FILE
        if mime_type.startswith("image/"):
            return MessageBlockType.IMAGE
        if mime_type.startswith("audio/"):
            return MessageBlockType.AUDIO
        if mime_type.startswith("video/"):
            return MessageBlockType.VIDEO
        return MessageBlockType.FILE

    def _get_stdio_client(self, config: McpLocalConfig, launch_key: str) -> "_StdioClientWrapper":
        client = self._mcp_stdio_clients.get(launch_key)
        if client is None:
            client = _StdioClientWrapper(config)
            self._mcp_stdio_clients[launch_key] = client
        return client


class _StdioClientWrapper:
    def __init__(self, config: McpLocalConfig) -> None:
        env = os.environ.copy() if config.inherit_env else {}
        env.update(config.env)
        env_payload = env or None
        transport = StdioTransport(
            command=config.command,
            args=list(config.args),
            env=env_payload,
            cwd=config.cwd,
            keep_alive=True,
        )
        self._client = Client(transport=transport)
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        init_future = asyncio.run_coroutine_threadsafe(self._initialize(), self._loop)
        init_future.result()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def _initialize(self) -> None:
        self._lock = asyncio.Lock()
        await self._client.__aenter__()

    def list_tools(self) -> List[Any]:
        future = asyncio.run_coroutine_threadsafe(self._call("list_tools"), self._loop)
        return future.result()

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        future = asyncio.run_coroutine_threadsafe(
            self._call("call_tool", name, arguments),
            self._loop,
        )
        return future.result()

    async def _call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        async with self._lock:
            func = getattr(self._client, method)
            return await func(*args, **kwargs)

    def close(self) -> None:
        future = asyncio.run_coroutine_threadsafe(self._shutdown(), self._loop)
        future.result()
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join()

    async def _shutdown(self) -> None:
        async with self._lock:
            await self._client.__aexit__(None, None, None)
