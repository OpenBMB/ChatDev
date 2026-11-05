"""Short-lived, authenticated bridge to a host-loopback Tool HTTP proxy.

Docker's default bridge cannot reach a proxy listening only on the host's
127.0.0.1. The bridge exists only during one explicitly network-enabled Tool
call. The upstream proxy and any credentials remain on the host.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
import base64
import hmac
import ipaddress
import json
import os
import secrets
import subprocess
import sys
from typing import AsyncIterator, Mapping
from urllib.parse import quote, unquote, urlsplit


class ToolProxyRelayError(RuntimeError):
    """A configured loopback Tool proxy cannot be safely bridged."""


def _debug(event: str) -> None:
    if os.environ.get("SGAR_TOOL_PROXY_RELAY_DEBUG") == "1":
        print(f"tool_proxy_relay:{event}", file=sys.stderr)


def _bridge_network() -> tuple[str, ipaddress.IPv4Network]:
    try:
        result = subprocess.run(
            ["docker", "network", "inspect", "bridge", "--format", "{{json .IPAM.Config}}"],
            capture_output=True, text=True, timeout=5, check=True,
        )
        configs = json.loads(result.stdout)
        for config in configs or []:
            gateway = ipaddress.ip_address(config["Gateway"])
            network = ipaddress.ip_network(config["Subnet"], strict=False)
            if isinstance(gateway, ipaddress.IPv4Address) and gateway in network:
                return str(gateway), network
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        raise ToolProxyRelayError("docker_bridge_gateway_unavailable") from exc
    raise ToolProxyRelayError("docker_bridge_gateway_unavailable")


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, OSError):
        pass
    finally:
        writer.close()


class _Relay:
    def __init__(
        self, upstream_host: str, upstream_port: int,
        upstream_auth: bytes | None,
    ) -> None:
        self.upstream_host = upstream_host
        self.upstream_port = upstream_port
        self.upstream_auth = upstream_auth
        self.token = secrets.token_urlsafe(32)
        self.server: asyncio.AbstractServer | None = None

    async def _handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
    ) -> None:
        upstream_writer: asyncio.StreamWriter | None = None
        try:
            # The relay binds only the Docker gateway and requires a fresh
            # per-call secret. Host routing can source local connections from
            # a non-bridge address, so a source-subnet check is not reliable.
            header = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=10)
            if len(header) > 16384:
                return
            lines = header[:-4].split(b"\r\n")
            if not lines or not lines[0]:
                return
            supplied_auth: bytes | None = None
            forwarded = [lines[0]]
            for line in lines[1:]:
                name, separator, value = line.partition(b":")
                if not separator:
                    return
                if name.lower() == b"proxy-authorization":
                    supplied_auth = value.strip()
                    continue
                forwarded.append(line)
            expected_auth = b"Basic " + base64.b64encode(
                f"sgar:{self.token}".encode("ascii")
            )
            if supplied_auth is None or not hmac.compare_digest(supplied_auth, expected_auth):
                _debug("auth_rejected")
                writer.write(b"HTTP/1.1 407 Proxy Authentication Required\r\nContent-Length: 0\r\n\r\n")
                await writer.drain()
                return
            if self.upstream_auth is not None:
                forwarded.append(b"Proxy-Authorization: Basic " + self.upstream_auth)
            upstream_reader, upstream_writer = await asyncio.wait_for(
                asyncio.open_connection(self.upstream_host, self.upstream_port), timeout=10,
            )
            _debug("upstream_connected")
            upstream_writer.write(b"\r\n".join(forwarded) + b"\r\n\r\n")
            await upstream_writer.drain()
            await asyncio.gather(
                _pipe(reader, upstream_writer),
                _pipe(upstream_reader, writer),
            )
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError,
                asyncio.TimeoutError, ConnectionError, OSError, ValueError) as exc:
            _debug(type(exc).__name__)
        finally:
            if upstream_writer is not None:
                upstream_writer.close()
            writer.close()


@asynccontextmanager
async def bridge_loopback_tool_proxies(
    docker_env: Mapping[str, str], *, network_required: bool,
) -> AsyncIterator[dict[str, str]]:
    """Rewrite only explicit loopback HTTP Tool proxies for one Docker call."""
    environment = dict(docker_env)
    if not network_required:
        yield environment
        return
    loopback: dict[str, tuple[str, int, bytes | None]] = {}
    for key in ("HTTP_PROXY", "HTTPS_PROXY"):
        value = environment.get(key, "")
        if not value:
            continue
        parsed = urlsplit(value)
        try:
            address = ipaddress.ip_address(parsed.hostname or "")
        except ValueError:
            continue
        if not address.is_loopback:
            continue
        try:
            proxy_port = parsed.port
        except ValueError as exc:
            raise ToolProxyRelayError("loopback_tool_proxy_port_invalid") from exc
        if parsed.scheme != "http" or not proxy_port or parsed.path not in ("", "/"):
            raise ToolProxyRelayError("loopback_tool_proxy_scheme_invalid")
        auth = None
        if parsed.username is not None:
            credentials = f"{unquote(parsed.username)}:{unquote(parsed.password or '')}"
            auth = base64.b64encode(credentials.encode("utf-8"))
        loopback[key] = (str(address), proxy_port, auth)
    if not loopback:
        yield environment
        return
    gateway, _network = _bridge_network()
    relays: dict[tuple[str, int, bytes | None], _Relay] = {}
    try:
        for key, upstream in loopback.items():
            relay = relays.get(upstream)
            if relay is None:
                relay = _Relay(*upstream)
                try:
                    relay.server = await asyncio.start_server(
                        relay._handle, host=gateway, port=0, limit=16384,
                    )
                except OSError as exc:
                    raise ToolProxyRelayError("docker_bridge_relay_bind_failed") from exc
                relays[upstream] = relay
            assert relay.server is not None
            port = relay.server.sockets[0].getsockname()[1]
            environment[key] = f"http://sgar:{quote(relay.token)}@{gateway}:{port}"
            environment[key.lower()] = environment[key]
        yield environment
    finally:
        for relay in relays.values():
            assert relay.server is not None
            relay.server.close()
            await relay.server.wait_closed()
