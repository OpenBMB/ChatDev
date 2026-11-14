"""Regression tests for HTTP attachment sources and generated attachment paths."""

import base64
import io
import sys
import zipfile
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from entity.messages import AttachmentRef, Message, MessageBlock, MessageBlockType, MessageRole
from runtime import sdk
from runtime.node.agent import ModelResponse, ProviderRegistry
from runtime.node.executor.agent_executor import AgentNodeExecutor
from runtime.node.executor.base import ExecutionContext
from server import state
from server.routes import execute_sync, sessions, uploads, websocket, workflows
from server.services.websocket_manager import WebSocketManager
from utils.attachments import AttachmentStore
from utils.error_handler import add_exception_handlers
from utils.exceptions import SecurityError


DEMO = Path(__file__).resolve().parents[1] / "yaml_instance/demo_loop_counter.yaml"
CONTENT = b"generated attachment content"


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MAC_ALLOW_UNSAFE_CODE_EXECUTION", "0")
    manager = WebSocketManager()
    monkeypatch.setattr(state, "websocket_manager", manager)
    monkeypatch.setattr(sessions, "WARE_HOUSE_DIR", tmp_path / "WareHouse")
    yaml_dir = tmp_path / "yaml_instance"
    yaml_dir.mkdir()
    for module in (sdk, execute_sync, workflows):
        monkeypatch.setattr(module, "YAML_DIR", yaml_dir)
    app = FastAPI()
    add_exception_handlers(app)
    for module in (execute_sync, sessions, uploads, websocket, workflows):
        app.include_router(module.router)
    with TestClient(app) as client:
        yield client, manager


def upload(client, sid, data=b"uploaded input"):
    with client.websocket_connect("/ws?session_id=" + sid) as ws:
        ws.receive_json()
        response = client.post("/api/uploads/" + sid, files={"file": ("input.txt", data)})
        assert response.status_code == 200, response.text
        manifest = client.get("/api/uploads/" + sid).json()["attachments"]
        attachment_id = response.json()["attachment_id"]
        return attachment_id, Path(manifest[attachment_id]["ref"]["local_path"])


def request_run(client, accept, **overrides):
    payload = {"yaml_file": str(DEMO), "task_prompt": "test", "session_name": "session_result"}
    payload.update(overrides)
    return client.post("/api/workflow/run", headers={"Accept": accept}, json=payload)


def archive_contents(client, sid):
    response = client.get(f"/api/sessions/{sid}/download")
    assert response.status_code == 200, response.text
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


@pytest.mark.parametrize("accept", ["application/json", "text/event-stream"])
@pytest.mark.parametrize("source_kind", ["absolute", "relative", "symlink", "unregistered", "other_session", "other_id"])
def test_http_rejects_untrusted_sources_before_copying(api, tmp_path, accept, source_kind):
    client, _ = api
    own_id, own_path = upload(client, "owner")
    other_id, other_path = upload(client, "other", b"other session secret")
    secret = tmp_path / "secret.txt"
    secret.write_text("outside workspace secret")
    if source_kind == "symlink":
        own_path.unlink()
        own_path.symlink_to(secret)
    unregistered = own_path.parent / "unregistered.txt"
    unregistered.write_text("not uploaded")
    source = {"absolute": str(secret), "relative": "secret.txt", "symlink": own_id,
              "unregistered": str(unregistered), "other_session": str(other_path), "other_id": other_id}[source_kind]
    response = request_run(client, accept, attachments=[own_id, source], attachment_session_id="owner")
    assert response.status_code == 403, response.text
    assert not (tmp_path / "WareHouse/session_result").exists()
    assert client.get("/api/sessions/result/download").status_code == 404
    assert secret.read_text() == "outside workspace secret"


@pytest.mark.parametrize("accept", ["application/json", "text/event-stream"])
def test_http_paths_without_upload_session_are_rejected(api, tmp_path, accept):
    client, _ = api
    secret = tmp_path / "secret.txt"
    secret.write_text("secret")
    response = request_run(client, accept, attachments=[str(secret)])
    assert response.status_code == 403
    assert "attachment_session_id" in response.text
    assert not (tmp_path / "WareHouse/session_result").exists()


@pytest.mark.parametrize("accept", ["application/json", "text/event-stream"])
@pytest.mark.parametrize("use_id", [False, True])
def test_uploaded_attachment_runs_and_downloads(api, accept, use_id):
    client, _ = api
    attachment_id, path = upload(client, "owner")
    response = request_run(client, accept, attachments=[attachment_id if use_id else str(path)],
                           attachment_session_id="owner")
    assert response.status_code == 200, response.text
    assert "Final summary released" in response.text
    assert "event: error" not in response.text
    contents = archive_contents(client, "result")
    assert b"uploaded input" in contents.values()


def test_local_sdk_still_accepts_explicit_file_paths(api, tmp_path):
    local = tmp_path / "local.txt"
    local.write_bytes(b"local CLI input")
    result = sdk.run_workflow(DEMO, task_prompt="test", attachments=[local], session_name="session_sdk")
    assert result.final_message.text_content() == "Final summary released"
    assert next(result.meta_info.output_dir.rglob("local.txt")).read_bytes() == b"local CLI input"


def test_download_preserves_empty_directories(api, tmp_path):
    client, _ = api
    (tmp_path / "WareHouse/session_empty/nested").mkdir(parents=True)
    contents = archive_contents(client, "empty")
    assert "session_empty/" in contents
    assert "session_empty/nested/" in contents


def test_prefixed_sessions_have_separate_uploads_execution_and_downloads(api, tmp_path):
    client, manager = api
    first_id, first_path = upload(client, "foo", b"first")
    second_id, second_path = upload(client, "session_foo", b"second")
    assert first_path.is_relative_to(tmp_path / "WareHouse/session_foo")
    assert second_path.is_relative_to(tmp_path / "WareHouse/session_session_foo")
    assert set(manager.attachment_service.list_attachment_manifests("foo")) == {first_id}
    assert set(manager.attachment_service.list_attachment_manifests("session_foo")) == {second_id}
    for sid, attachment_id, expected in (("foo", first_id, b"first"), ("session_foo", second_id, b"second")):
        contents = archive_contents(client, sid)
        assert expected in contents.values()
        assert (b"second" if expected == b"first" else b"first") not in contents.values()
        assert manager.attachment_service.build_attachment_blocks(sid, [attachment_id])
    assert not manager.attachment_service.build_attachment_blocks("foo", [second_id])


@pytest.mark.parametrize("kind", ["file", "directory", "dangling", "loop"])
def test_download_skips_links_and_preserves_regular_files(api, tmp_path, kind):
    client, _ = api
    secret_dir = tmp_path / "outside"
    secret_dir.mkdir()
    (secret_dir / "secret.txt").write_text("secret")
    session = tmp_path / "WareHouse/session_download"
    session.mkdir()
    (session / "run.log").write_bytes(b"workflow log")
    target = {"file": secret_dir / "secret.txt", "directory": secret_dir,
              "dangling": secret_dir / "missing", "loop": session / "link"}[kind]
    (session / "link").symlink_to(target, target_is_directory=kind == "directory")
    contents = archive_contents(client, "download")
    assert contents["session_download/run.log"] == b"workflow log"
    assert not any("link" in Path(name).parts for name in contents)
    assert b"secret" not in contents.values()


def test_download_still_rejects_linked_session_root(api, tmp_path):
    client, _ = api
    secret_dir = tmp_path / "outside"
    secret_dir.mkdir()
    (secret_dir / "secret.txt").write_text("secret")
    (tmp_path / "WareHouse/session_download").symlink_to(secret_dir, target_is_directory=True)
    response = client.get("/api/sessions/download/download")
    assert response.status_code in (400, 403)
    assert "application/zip" not in response.headers.get("content-type", "")


def test_download_with_venv_interpreter_links(api, tmp_path):
    client, _ = api
    session = tmp_path / "WareHouse/session_venv"
    venv = session / "code_workspace/.venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "bin/python").symlink_to(sys.executable)
    (venv / "bin/python3").symlink_to("python")
    (venv / "pyvenv.cfg").write_bytes(b"include-system-site-packages = false\n")
    (session / "run.log").write_bytes(b"workflow completed")
    contents = archive_contents(client, "venv")
    assert contents["session_venv/run.log"] == b"workflow completed"
    assert contents["session_venv/code_workspace/.venv/pyvenv.cfg"] == (venv / "pyvenv.cfg").read_bytes()
    assert "session_venv/code_workspace/.venv/bin/python" not in contents
    assert "session_venv/code_workspace/.venv/bin/python3" not in contents


@pytest.fixture
def agent(tmp_path):
    workspace = tmp_path / "workspace"
    store = AttachmentStore(workspace / "attachments")
    context = ExecutionContext(tool_manager=Mock(), function_manager=Mock(), log_manager=Mock(),
                               global_state={"python_workspace_root": workspace, "attachment_store": store})
    return AgentNodeExecutor(context), workspace, store


def attachment_message(name="result.txt", attachment_id="generated", local_path=None):
    ref = AttachmentRef(attachment_id=attachment_id, name=name, mime_type="text/plain",
                        local_path=str(local_path) if local_path else None,
                        data_uri=None if local_path else "data:text/plain;base64," + base64.b64encode(CONTENT).decode())
    return Message(role=MessageRole.ASSISTANT, content=[MessageBlock(type=MessageBlockType.FILE, attachment=ref)])


@pytest.mark.parametrize("field", ["node_id", "name", "attachment_id"])
@pytest.mark.parametrize("value", ["../outside", "/absolute", r"..\outside", "C:outside", ".", "..", "bad\x00name"])
def test_generated_paths_reject_untrusted_components(agent, tmp_path, field, value):
    executor, workspace, store = agent
    node_id = value if field == "node_id" else "Generator"
    message = attachment_message(**({field: value} if field != "node_id" else {}))
    with pytest.raises(SecurityError):
        executor._persist_message_attachments(message, node_id)
    assert not (workspace / "generated").exists()
    assert not store.export_manifest()


@pytest.mark.parametrize("part", ["generated", "generated/Generator", "generated/Generator/result.txt"])
def test_generated_paths_reject_symlinks(agent, tmp_path, part):
    executor, workspace, _ = agent
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "result.txt"
    sentinel.write_text("original")
    link = workspace / part
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(sentinel if part.endswith(".txt") else outside, target_is_directory=not part.endswith(".txt"))
    with pytest.raises(SecurityError):
        executor._persist_message_attachments(attachment_message(), "Generator")
    assert sentinel.read_text() == "original"


@pytest.mark.parametrize("linked", [False, True])
def test_generated_local_source_cannot_read_outside(agent, tmp_path, linked):
    executor, workspace, _ = agent
    secret = tmp_path / "secret.txt"
    secret.write_text("secret")
    source = secret
    if linked:
        source = workspace / "alias.txt"
        source.symlink_to(secret)
    with pytest.raises(SecurityError):
        executor._persist_message_attachments(attachment_message(local_path=source), "Generator")
    assert not (workspace / "generated").exists()


@pytest.mark.parametrize("local", [False, True])
def test_generated_attachment_normal_round_trip(agent, local):
    executor, workspace, store = agent
    source = None
    if local:
        source = workspace / "input.txt"
        source.write_bytes(CONTENT)
    message = attachment_message(local_path=source)
    executor._persist_message_attachments(message, "Image Generator")
    target = workspace / "generated/Image Generator/result.txt"
    assert target.read_bytes() == CONTENT
    assert Path(message.blocks()[0].attachment.local_path) == target
    assert store.get("generated").ref.local_path == str(target)


def test_generated_image_infers_extension_from_data_uri(agent):
    executor, workspace, _ = agent
    message = attachment_message(name=None)
    ref = message.blocks()[0].attachment
    ref.mime_type = None
    ref.data_uri = "data:image/png;base64," + base64.b64encode(CONTENT).decode()
    executor._persist_message_attachments(message, "Generator")
    assert (workspace / "generated/Generator/generated.png").read_bytes() == CONTENT
    assert message.blocks()[0].attachment.mime_type == "image/png"


@pytest.mark.parametrize("accept", ["application/json", "text/event-stream"])
@pytest.mark.parametrize("malicious", ["node", "name", "id", "none"])
def test_agent_attachment_security_reaches_http_api(api, tmp_path, monkeypatch, accept, malicious):
    client, _ = api
    outside = tmp_path / "outside"
    node_id = str(outside) if malicious == "node" else "Generator"
    message = attachment_message(name="../../../../escaped.txt" if malicious == "name" else "result.txt",
                                 attachment_id="../../escape" if malicious == "id" else "generated")
    provider = Mock()
    provider.call_model.return_value = ModelResponse(message=message)
    monkeypatch.setattr(ProviderRegistry, "get_provider", lambda _: Mock(return_value=provider))
    definition = {"version": "0.4.0", "graph": {"id": "attachment_test", "start": [node_id], "nodes": [
        {"id": node_id, "type": "agent", "config": {"provider": "openai", "name": "test-model",
                                                       "api_key": "local-test", "role": "test"}},
    ], "edges": []}}
    response = client.post("/api/workflows/upload/content", json={"filename": "agent.yaml", "content": yaml.safe_dump(definition)})
    assert response.status_code == 200, response.text
    response = request_run(client, accept, yaml_file="agent.yaml")
    if malicious == "none":
        assert response.status_code == 200, response.text
        assert "event: error" not in response.text
        assert CONTENT in archive_contents(client, "result").values()
    elif accept == "text/event-stream":
        assert response.status_code == 200
        assert "event: error" in response.text
        assert "event: completed" not in response.text
    else:
        assert response.status_code == 403, response.text
    assert not outside.exists()
    assert not (tmp_path / "escaped.txt").exists()
