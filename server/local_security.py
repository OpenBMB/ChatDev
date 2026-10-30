"""Access checks for installing trusted Python tools in the local app."""

import ipaddress
import os
import secrets

from fastapi import HTTPException, Request


_LOCAL_TOOL_TOKEN = secrets.token_urlsafe(32)
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def allowed_browser_origins() -> list[str]:
    configured = os.getenv("CORS_ALLOW_ORIGINS")
    if configured is not None:
        # Wildcards must never authorize reading the local session token.
        return [origin.strip() for origin in configured.split(",") if origin.strip() and origin.strip() != "*"]
    return ["http://localhost:5173", "http://127.0.0.1:5173"]


def require_local_tool_access(request: Request) -> None:
    try:
        local_client = request.client is not None and ipaddress.ip_address(request.client.host).is_loopback
    except ValueError:
        local_client = False
    # Check Host as well as the peer address to reject DNS rebinding.
    if not local_client or request.url.hostname not in _LOCAL_HOSTS:
        raise HTTPException(status_code=403, detail="Tool installation is only available locally")

    origin = request.headers.get("origin")
    if origin is not None and origin not in allowed_browser_origins():
        raise HTTPException(status_code=403, detail="Browser origin is not allowed")


def local_tool_session(request: Request) -> dict[str, str]:
    require_local_tool_access(request)
    # A custom header prevents cross-origin simple requests from reading a token.
    if request.headers.get("x-chatdev-local") != "1":
        raise HTTPException(status_code=403, detail="Local session header is required")
    return {"token": _LOCAL_TOOL_TOKEN}


def require_local_tool_token(request: Request) -> None:
    require_local_tool_access(request)
    token = request.headers.get("x-chatdev-tool-token", "")
    if not secrets.compare_digest(token.encode("utf-8"), _LOCAL_TOOL_TOKEN.encode("utf-8")):
        raise HTTPException(status_code=403, detail="Valid local tool token is required")
