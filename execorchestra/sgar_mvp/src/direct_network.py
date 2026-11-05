"""Application-level direct networking, independent of host proxy settings.

No registry, shell profile, machine environment or original resource is edited.
Explicitly injected HTTP clients remain caller-owned (including offline mocks).
"""
from __future__ import annotations

import os
import hashlib
from pathlib import Path
from typing import Any, Mapping, TYPE_CHECKING

if TYPE_CHECKING:
    import httpx

PROXY_VARIABLES = (
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "FTP_PROXY",
    "http_proxy", "https_proxy", "all_proxy", "ftp_proxy",
)
BYPASS_VARIABLES = ("NO_PROXY", "no_proxy")

TOOL_PROXY_VARIABLES = (
    "SGAR_TOOL_HTTP_PROXY",
    "SGAR_TOOL_HTTPS_PROXY",
    "SGAR_TOOL_NO_PROXY",
)
MODEL_PROXY_VARIABLE = "SGAR_MODEL_PROXY"

# Project-scoped credentials that may be resolved from the private .env file
# and injected into the selected Tool container. Keep this list explicit so a
# model/API credential cannot be forwarded to arbitrary resource processes.
PROJECT_TOOL_ENV_NAMES = ("HYPOTHESIS_API_TOKEN",)


def load_model_proxy(project_root: str | os.PathLike[str] | None = None) -> str:
    """Load the proxy reserved for external model API traffic."""
    value = os.environ.get(MODEL_PROXY_VARIABLE, "").strip()
    if value:
        return value.strip('"').strip("'")

    root = Path(project_root).resolve() if project_root else Path(__file__).resolve().parents[2]
    env_path = root / ".env"
    if not env_path.is_file():
        return ""
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, raw_value = line.split("=", 1)
            if name.strip() == MODEL_PROXY_VARIABLE:
                return raw_value.strip().strip('"').strip("'")
    except OSError:
        return ""
    return ""


def load_tool_proxy_config(project_root: str | os.PathLike[str] | None = None) -> dict[str, str]:
    """Load optional project-scoped Tool proxy values without mutating the process."""
    values: dict[str, str] = {}
    root = Path(project_root).resolve() if project_root else Path.cwd().resolve()
    env_path = root / ".env"
    if env_path.is_file():
        try:
            for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, value = line.split("=", 1)
                name = name.strip()
                if name in TOOL_PROXY_VARIABLES:
                    values[name] = value.strip().strip('"').strip("'")
        except OSError:
            values = {}
    for name in TOOL_PROXY_VARIABLES:
        if name in os.environ:
            values[name] = os.environ.get(name, "").strip()
    return {name: values.get(name, "") for name in TOOL_PROXY_VARIABLES}


def load_project_tool_environment(
    project_root: str | os.PathLike[str] | None = None,
    names: tuple[str, ...] = PROJECT_TOOL_ENV_NAMES,
) -> dict[str, str]:
    """Resolve explicitly allowlisted Tool credentials without logging values."""

    root = Path(project_root).resolve() if project_root else Path.cwd().resolve()
    dotenv_values: dict[str, str] = {}
    env_path = root / ".env"
    if env_path.is_file():
        try:
            for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, value = line.split("=", 1)
                if name.strip() in names:
                    dotenv_values[name.strip()] = value.strip().strip('"').strip("'")
        except OSError:
            dotenv_values = {}
    return {
        name: str(os.environ.get(name, "").strip() or dotenv_values.get(name, ""))
        for name in names
        if str(os.environ.get(name, "").strip() or dotenv_values.get(name, ""))
    }


def project_tool_environment_configured(
    name: str,
    project_root: str | os.PathLike[str] | None = None,
) -> bool:
    """Return whether an allowlisted project Tool variable has a value."""

    return bool(load_project_tool_environment(project_root, (name,)).get(name))


def tool_proxy_audit(config: Mapping[str, str]) -> dict[str, Any]:
    """Return a credential-free proxy status and stable configuration fingerprint."""
    normalized = {name: str(config.get(name, "") or "") for name in TOOL_PROXY_VARIABLES}
    fingerprint = hashlib.sha256(
        "\n".join(f"{name}={normalized[name]}" for name in TOOL_PROXY_VARIABLES).encode("utf-8")
    ).hexdigest()
    return {
        "proxy_enabled": bool(normalized["SGAR_TOOL_HTTP_PROXY"] or normalized["SGAR_TOOL_HTTPS_PROXY"]),
        "proxy_no_proxy_configured": bool(normalized["SGAR_TOOL_NO_PROXY"]),
        "proxy_config_fingerprint": fingerprint,
    }


def direct_environment(environment: Mapping[str, str]) -> dict[str, str]:
    """Build a child environment without inherited proxy routes."""
    result = {key: value for key, value in environment.items()
              if key.lower() not in {"http_proxy", "https_proxy", "all_proxy", "ftp_proxy", "no_proxy"}}
    # urllib/requests use these on Linux; the nonempty mapping also prevents
    # urllib from falling back to the Windows system proxy registry.
    result.update({key: "*" for key in BYPASS_VARIABLES})
    return result


def configure_direct_network() -> None:
    """Apply direct routing to this SGAR process and its inherited children."""
    for key in tuple(os.environ):
        if key.lower() in {"http_proxy", "https_proxy", "all_proxy", "ftp_proxy", "no_proxy"}:
            del os.environ[key]
    os.environ.update({key: "*" for key in BYPASS_VARIABLES})


def direct_sync_http_client(**kwargs: Any) -> httpx.Client:
    from openai import DefaultHttpxClient
    kwargs["trust_env"] = False
    proxy = load_model_proxy()
    if proxy:
        kwargs["proxy"] = proxy
    return DefaultHttpxClient(**kwargs)


def direct_async_http_client(**kwargs: Any) -> httpx.AsyncClient:
    from openai import DefaultAsyncHttpxClient
    kwargs["trust_env"] = False
    proxy = load_model_proxy()
    if proxy:
        kwargs["proxy"] = proxy
    return DefaultAsyncHttpxClient(**kwargs)


def direct_container_environment_args(
    *,
    proxy_config: Mapping[str, str] | None = None,
    network_required: bool = False,
    network_policy_mode: str = "disabled",
) -> list[str]:
    """Pass proxy variable names without placing proxy values in Docker argv."""
    result = []
    for name in PROXY_VARIABLES:
        result.extend(("-e", name))
    for name in BYPASS_VARIABLES:
        result.extend(("-e", name))
    # Values are supplied through the subprocess environment, never argv.
    # The argument list contains names only so credentials cannot leak.
    return result


def tool_proxy_environment(
    config: Mapping[str, str] | None = None,
    *,
    network_required: bool = False,
    network_policy_mode: str = "disabled",
) -> dict[str, str]:
    """Return proxy values for a child environment, with no credentials in argv."""
    if not network_required or network_policy_mode != "declared":
        return {}
    values = config or {}
    http = str(values.get("SGAR_TOOL_HTTP_PROXY", "") or "")
    https = str(values.get("SGAR_TOOL_HTTPS_PROXY", "") or "")
    no_proxy = str(values.get("SGAR_TOOL_NO_PROXY", "") or ("" if http or https else "*"))
    return {
        "HTTP_PROXY": http,
        "HTTPS_PROXY": https,
        "NO_PROXY": no_proxy,
        "http_proxy": http,
        "https_proxy": https,
        "no_proxy": no_proxy,
    }


def model_api_urlopen(request: Any, *, timeout: float = 120):
    """urllib-compatible response for model endpoints with an explicit proxy.

    Internal IP literals and localhost remain local. Proxy decisions do not
    depend on the inherited NO_PROXY="*" used for isolated runtime startup.
    """
    import ipaddress
    import io
    import urllib.error
    import urllib.response
    from urllib.parse import urlsplit
    import httpx

    host = (urlsplit(request.full_url).hostname or "").rstrip(".").lower()
    local = host == "localhost" or host.endswith(".localhost")
    try:
        local = local or not ipaddress.ip_address(host).is_global
    except ValueError:
        pass
    proxy = None if local else (load_model_proxy() or None)
    try:
        with httpx.Client(trust_env=False, proxy=proxy, timeout=timeout, follow_redirects=True) as client:
            response = client.request(request.get_method(), request.full_url,
                                      content=request.data, headers=dict(request.header_items()))
    except httpx.HTTPError as exc:
        raise urllib.error.URLError("model_api_transport_failed") from exc
    if response.status_code >= 400:
        raise urllib.error.HTTPError(request.full_url, response.status_code,
                                     "model_api_http_error", response.headers,
                                     io.BytesIO(response.content))
    return urllib.response.addinfourl(io.BytesIO(response.content), response.headers,
                                     str(response.url), response.status_code)
