#!/usr/bin/env python3
"""Bounded SGAR adapter for the upstream HTTPX client."""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import socket
import sys
import time
from urllib.parse import urlparse
from urllib.request import proxy_bypass_environment

import httpx


def emit(value: dict) -> None:
    print(json.dumps(value, ensure_ascii=False))


def emit_business_error(reason_code: str) -> int:
    # A failed fetch is an observation the caller can use to choose another
    # public source.  Keep process failures for actual adapter/runtime faults.
    emit({"status": "error", "tool": "httpx", "reason_code": reason_code})
    return 0


def _network_reason(exc: Exception) -> tuple[str, bool]:
    """Classify transport facts without exposing exception messages or credentials."""
    name = type(exc).__name__
    reasons = {
        "ConnectTimeout": ("network_connect_timeout", True),
        "ReadTimeout": ("network_read_timeout", True),
        "WriteTimeout": ("network_write_timeout", True),
        "PoolTimeout": ("network_pool_timeout", True),
        "ConnectError": ("network_connect_error", True),
        "ReadError": ("network_read_error", True),
        "RemoteProtocolError": ("network_remote_protocol_error", True),
        "ProxyError": ("network_proxy_error", True),
        "TooManyRedirects": ("redirect_limit_exceeded", False),
        "UnsupportedProtocol": ("url_protocol_unsupported", False),
    }
    return reasons.get(name, ("network_request_failed", False))


def _diagnostic(url: str, attempt: int, reason: str, started: float) -> None:
    # Keep the public result schema stable. Evidence contains no URL query,
    # response body, credentials, headers, or raw provider exception.
    print(json.dumps({
        "event": "http_attempt", "url_sha256": hashlib.sha256(url.encode()).hexdigest(),
        "attempt": attempt, "reason_code": reason,
        "elapsed_ms": round((time.monotonic() - started) * 1000),
    }), file=sys.stderr)


def _request(args, url: str) -> dict:
    started = time.monotonic()
    deadline = started + args.timeout_ms / 1000.0
    for attempt in (1, 2):
        remaining = max(0.001, deadline - time.monotonic())
        try:
            with httpx.Client(
                follow_redirects=args.follow_redirects,
                timeout=httpx.Timeout(remaining), trust_env=False,
                proxy=_configured_proxy(url),
                headers={"User-Agent": "SGARResearch/1.0 (automated academic evaluation; HTTPX client)"},
            ) as client:
                with client.stream(args.method, url) as response:
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > args.max_bytes:
                            _diagnostic(url, attempt, "response_too_large", started)
                            return {"status": "error", "tool": "httpx", "reason_code": "response_too_large"}
                    result = {
                        "status": "success" if response.status_code < 400 else "error",
                        "tool": "httpx", "url": str(response.url),
                        "http_status": response.status_code,
                        "headers": dict(response.headers),
                        "body": bytes(body).decode(response.encoding or "utf-8", errors="replace"),
                        "redirect_chain": [str(item.url) for item in response.history],
                    }
                    if response.status_code < 400:
                        return result
                    result["reason_code"] = "http_status_error"
                    transient = response.status_code in {502, 503, 504}
                    reason = "http_" + str(response.status_code)
        except (httpx.HTTPError, OSError) as exc:
            reason, transient = _network_reason(exc)
            result = {"status": "error", "tool": "httpx", "reason_code": reason}
        _diagnostic(url, attempt, reason, started)
        # GET/HEAD only. One fast transport retry shares the original deadline;
        # a timeout that consumed it, a 403/404/429, and a size failure do not retry.
        if not transient or attempt == 2 or deadline - time.monotonic() < 1.0:
            return result
        time.sleep(0.2)
    return result


def _configured_proxy(url: str) -> str | None:
    parsed = urlparse(url)
    proxy = os.environ.get("HTTPS_PROXY" if parsed.scheme == "https" else "HTTP_PROXY") or None
    if proxy and proxy_bypass_environment(parsed.hostname or "", {"no": os.environ.get("NO_PROXY", "")}):
        return None
    return proxy


def _public_url(raw: str) -> str:
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Perform a bounded HTTPX request")
    parser.add_argument("method", choices=("GET", "HEAD"))
    parser.add_argument("url")
    parser.add_argument("--timeout-ms", type=int, default=15000)
    parser.add_argument("--max-bytes", type=int, default=1_000_000)
    parser.add_argument("--follow-redirects", action="store_true")
    args = parser.parse_args()
    if args.timeout_ms < 1 or args.timeout_ms > 120_000:
        return emit_business_error("timeout_option_invalid")
    if args.max_bytes < 1 or args.max_bytes > 10_000_000:
        return emit_business_error("size_option_invalid")
    try:
        url = _public_url(args.url)
        emit(_request(args, url))
        return 0
    except ValueError as exc:
        return emit_business_error(str(exc))
    except socket.gaierror:
        return emit_business_error("network_dns_error")
    except (httpx.HTTPError, OSError) as exc:
        return emit_business_error(_network_reason(exc)[0])


if __name__ == "__main__":
    raise SystemExit(main())
