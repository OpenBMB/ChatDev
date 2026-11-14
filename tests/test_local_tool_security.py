"""Exercise the actual upload route without importing the workflow runtime."""

import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from server.local_security import allowed_browser_origins
from utils.function_catalog import FunctionCatalog


@pytest.fixture
def local_tools(tmp_path, monkeypatch):
    monkeypatch.delenv("CORS_ALLOW_ORIGINS", raising=False)
    spec = importlib.util.spec_from_file_location(
        "local_tools_under_test",
        Path(__file__).resolve().parents[1] / "server/routes/tools.py",
    )
    routes = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, routes)
    spec.loader.exec_module(routes)
    catalog = FunctionCatalog(tmp_path)
    monkeypatch.setattr(routes, "FUNCTION_CALLING_DIR", tmp_path)
    monkeypatch.setattr(routes, "get_function_catalog", lambda: catalog)
    app = FastAPI()
    app.include_router(routes.router)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_browser_origins(),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app, tmp_path


def client_for(app, host="127.0.0.1"):
    return TestClient(app, base_url="http://127.0.0.1:8000", client=(host, 12345))


def session_token(client):
    response = client.get(
        "/api/tools/local/session",
        headers={"X-ChatDev-Local": "1", "Origin": "http://localhost:5173"},
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    return response.json()["token"]


@pytest.mark.parametrize("token", [None, "incorrect", "非有效令牌"])
def test_unauthorized_upload_does_not_write_or_execute(local_tools, token):
    app, directory = local_tools
    headers = {} if token is None else {"X-ChatDev-Tool-Token": token.encode("utf-8")}
    with client_for(app) as client:
        response = client.post(
            "/api/tools/local", headers=headers,
            json={"filename": "probe.py", "content": "raise RuntimeError('must not execute')"},
        )
    assert response.status_code == 403
    assert list(directory.iterdir()) == []


def test_authorized_upload_preserves_install_and_load(local_tools):
    app, directory = local_tools
    marker = directory / "executed.txt"
    source = f"from pathlib import Path\nPath({str(marker)!r}).write_text('ok')\n"
    with client_for(app) as client:
        token = session_token(client)
        response = client.post(
            "/api/tools/local",
            headers={"X-ChatDev-Tool-Token": token, "Origin": "http://localhost:5173"},
            json={"filename": "probe.py", "content": source},
        )
    assert response.status_code == 200
    assert (directory / "probe.py").read_text() == source
    assert marker.read_text() == "ok"


@pytest.mark.parametrize("origin", ["https://evil.example", "null", "http://localhost:5174"])
def test_disallowed_origin_cannot_get_token_or_upload(local_tools, origin):
    app, directory = local_tools
    with client_for(app) as client:
        token = session_token(client)
        headers = {"Origin": origin, "X-ChatDev-Local": "1", "X-ChatDev-Tool-Token": token}
        assert client.get("/api/tools/local/session", headers=headers).status_code == 403
        response = client.post(
            "/api/tools/local", headers=headers,
            json={"filename": "probe", "content": "pass"},
        )
    assert response.status_code == 403
    assert list(directory.iterdir()) == []


def test_session_requires_custom_header(local_tools):
    app, _ = local_tools
    with client_for(app) as client:
        assert client.get("/api/tools/local/session").status_code == 403


@pytest.mark.parametrize("peer,host", [
    ("192.0.2.10", "127.0.0.1:8000"),
    ("127.0.0.1", "evil.example:8000"),
])
def test_remote_peer_and_rebinding_host_rejected_even_with_token(local_tools, peer, host):
    app, directory = local_tools
    with client_for(app) as local:
        token = session_token(local)
    with client_for(app, peer) as client:
        headers = {"Host": host, "X-ChatDev-Local": "1", "X-ChatDev-Tool-Token": token}
        assert client.get("/api/tools/local/session", headers=headers).status_code == 403
        response = client.post(
            "/api/tools/local", headers=headers,
            json={"filename": "probe", "content": "pass"},
        )
    assert response.status_code == 403
    assert list(directory.iterdir()) == []


def test_untrusted_browser_preflight_is_rejected(local_tools):
    app, _ = local_tools
    with client_for(app) as client:
        response = client.options("/api/tools/local/session", headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-ChatDev-Local",
        })
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_cors_wildcard_does_not_authorize_token_access(monkeypatch):
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "*,http://localhost:5173")
    assert allowed_browser_origins() == ["http://localhost:5173"]
