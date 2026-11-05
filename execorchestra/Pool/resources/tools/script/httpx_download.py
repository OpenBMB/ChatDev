#!/usr/bin/env python3
"""Acquire one public HTTP response as exact bytes in the task workspace."""
from __future__ import annotations
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import socket
import tempfile
from urllib.parse import urljoin, urlparse
from urllib.request import proxy_bypass_environment
import httpx


def _configured_proxy(url: str) -> str | None:
    parsed = urlparse(url)
    proxy = os.environ.get("HTTPS_PROXY" if parsed.scheme == "https" else "HTTP_PROXY") or None
    if proxy and proxy_bypass_environment(parsed.hostname or "", {"no": os.environ.get("NO_PROXY", "")}):
        return None
    return proxy


def public_url(raw: str) -> str:
    try:
        parsed = urlparse(raw)
        host = parsed.hostname
        port = parsed.port
    except (TypeError, ValueError):
        raise ValueError("url_syntax_invalid") from None
    if (parsed.scheme not in {"http", "https"} or not host
            or any(char.isspace() for char in raw)):
        raise ValueError("url_syntax_invalid")
    if os.environ.get("SGAR_HTTPX_ALLOW_PRIVATE") == "1":
        return raw
    host = parsed.hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith(".localhost"):
        raise ValueError("url_destination_disallowed")
    try:
        addresses = {ipaddress.ip_address(host)}
    except ValueError:
        if _configured_proxy(raw):
            # A configured HTTP proxy resolves the destination. Local DNS can
            # disagree with that route; its answers are not connection targets.
            # The operator-managed proxy owns hostname resolution/access policy.
            # Private IP literals and localhost remain rejected above/below.
            return raw
        addresses = {ipaddress.ip_address(info[4][0]) for info in socket.getaddrinfo(
            host, port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)}
    if any(a.is_private or a.is_loopback or a.is_link_local or a.is_reserved for a in addresses):
        raise ValueError("url_destination_disallowed")
    return raw


def download(url: str, output_path: str, *, timeout_ms: int = 60000,
             max_bytes: int = 20 * 1024 * 1024) -> dict:
    temporary = None
    io_phase = "network"
    try:
        if timeout_ms < 1 or max_bytes < 1:
            raise ValueError('invalid_options')
        root = Path(os.environ.get('SGAR_WORKSPACE_ROOT') or os.getcwd()).resolve()
        destination = Path(output_path)
        destination = (destination if destination.is_absolute() else Path.cwd() / destination).resolve()
        if root not in destination.parents:
            raise ValueError('destination_outside_workspace')
        current = public_url(url)
        for _ in range(11):
            parsed = urlparse(current)
            proxy = os.environ.get('HTTPS_PROXY' if parsed.scheme == 'https' else 'HTTP_PROXY') or None
            if proxy and proxy_bypass_environment(parsed.hostname or '', {'no': os.environ.get('NO_PROXY', '')}):
                proxy = None
            with httpx.Client(follow_redirects=False, timeout=timeout_ms / 1000,
                              trust_env=False, proxy=proxy,
                              headers={"User-Agent": "SGARResearch/1.0 (automated academic evaluation; HTTPX client)"}) as client:
                with client.stream('GET', current) as response:
                    if response.is_redirect and response.headers.get('location'):
                        current = public_url(urljoin(current, response.headers['location']))
                        continue
                    if response.status_code != 200:
                        return {'status': 'error', 'reason_code': 'http_status_error',
                                'http_status': response.status_code}
                    io_phase = "filesystem"
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    digest = hashlib.sha256();size = 0
                    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as target:
                        temporary = Path(target.name)
                        for chunk in response.iter_bytes():
                            size += len(chunk)
                            if size > max_bytes:
                                raise ValueError('response_too_large')
                            target.write(chunk);digest.update(chunk)
                    temporary.replace(destination);temporary = None
                    return {'status': 'success', 'url': str(response.url), 'http_status': 200,
                            'byte_size': size, 'content_sha256': digest.hexdigest(),
                            'content_type': response.headers.get('content-type', '')}
        return {'status': 'error', 'reason_code': 'redirect_limit_exceeded'}
    except ValueError as exc:
        return {'status': 'error', 'reason_code': str(exc)}
    except httpx.HTTPError as exc:
        reasons = {
            'ConnectTimeout': 'network_connect_timeout', 'ReadTimeout': 'network_read_timeout',
            'WriteTimeout': 'network_write_timeout', 'PoolTimeout': 'network_pool_timeout',
            'ConnectError': 'network_connect_error', 'ReadError': 'network_read_error',
            'RemoteProtocolError': 'network_remote_protocol_error', 'ProxyError': 'network_proxy_error',
            'TooManyRedirects': 'redirect_limit_exceeded', 'UnsupportedProtocol': 'url_protocol_unsupported',
        }
        return {'status': 'error', 'reason_code': reasons.get(type(exc).__name__, 'network_request_failed')}
    except OSError:
        return {'status': 'error', 'reason_code': (
            'local_file_io_failed' if io_phase == 'filesystem' else 'network_dns_error')}
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass  # Preserve the original failure receipt if cleanup itself fails.


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url')
    parser.add_argument('output_path', help='Task-workspace destination; use the real file extension.')
    parser.add_argument('--timeout-ms', type=int, default=60000)
    parser.add_argument('--max-bytes', type=int, default=20 * 1024 * 1024)
    args = parser.parse_args()
    print(json.dumps(download(args.url, args.output_path, timeout_ms=args.timeout_ms,
                              max_bytes=args.max_bytes), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
