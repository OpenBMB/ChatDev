"""Regression coverage for session traversal through uploads and workflow runs."""

import asyncio
import io
from pathlib import Path
from unittest.mock import Mock
from urllib.parse import urlencode

import pytest
from fastapi import FastAPI, UploadFile
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from runtime import sdk
from entity.graph_config import GraphConfig
from server import state
from server.routes import execute_sync, uploads, websocket
from server.services.attachment_service import AttachmentService
from server.services.websocket_manager import WebSocketManager
from utils.exceptions import ValidationError
from workflow.graph_context import GraphContext
from workflow.runtime.runtime_builder import RuntimeBuilder


TRAVERSAL = "session_../../../functions/function_calling/pocplant"
INVALID_NAMES = [
    TRAVERSAL,
    "../outside",
    "session_a/../../outside",
    "/tmp/session_absolute",
    r"session_..\..\outside",
    r"C:\outside",
    "C:outside",
    r"\\server\share",
    ".",
    "..",
    "session_\x00invalid",
    "session_\ninvalid",
]
DEMO_YAML = Path(__file__).resolve().parents[1] / "yaml_instance/demo_loop_counter.yaml"


@pytest.fixture
def graph_config(tmp_path):
    return GraphConfig.from_definition(
        sdk.load_config(DEMO_YAML).graph,
        name="session_safe",
        output_root=tmp_path / "WareHouse",
    )


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = WebSocketManager()
    monkeypatch.setattr(manager, "_start_gc", lambda: None)
    monkeypatch.setattr(state, "websocket_manager", manager)
    app = FastAPI()
    app.include_router(execute_sync.router)
    app.include_router(uploads.router)
    app.include_router(websocket.router)
    with TestClient(app) as client:
        yield client, manager


@pytest.mark.parametrize("name", INVALID_NAMES)
def test_graph_rejects_invalid_names_before_creating_directories(graph_config, name):
    graph_config.name = name
    with pytest.raises(ValidationError):
        GraphContext(graph_config)
    assert not graph_config.output_root.exists()


@pytest.mark.parametrize("name", ["session_ok-123", "demo.v1", "My project", "\u6d4b\u8bd5"])
def test_graph_preserves_valid_names_and_timestamp_behavior(graph_config, name):
    graph_config.name = name
    graph = GraphContext(graph_config)
    assert graph.directory.parent == graph_config.output_root.resolve()
    assert graph.directory.is_dir()
    if "session_" in name:
        assert graph.directory.name == name
    else:
        assert graph.directory.name.startswith(name + "_")
        assert graph.directory.name[len(name) + 1:].isdigit()


def test_fixed_output_directory_is_still_confined(graph_config):
    graph_config.name = "task_001"
    graph_config.metadata["fixed_output_dir"] = True
    assert GraphContext(graph_config).directory == graph_config.output_root / "task_001"
    graph_config.name = "../outside"
    with pytest.raises(ValidationError):
        GraphContext(graph_config)


def test_graph_rejects_existing_session_symlink(graph_config, tmp_path):
    outside = tmp_path / "functions"
    outside.mkdir()
    graph_config.output_root.mkdir()
    (graph_config.output_root / graph_config.name).symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValidationError, match="escapes"):
        GraphContext(graph_config)
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("builder", [sdk._build_task_input, execute_sync._build_task_input])
@pytest.mark.parametrize("linked_part", ["code_workspace", "code_workspace/attachments"])
def test_attachment_copy_rejects_escaping_symlinks(graph_config, tmp_path, builder, linked_part):
    graph = GraphContext(graph_config)
    outside = tmp_path / "functions"
    outside.mkdir()
    link = graph.directory / linked_part
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(outside, target_is_directory=True)
    source = tmp_path / "notes.txt"
    source.write_text("sample")
    with pytest.raises(ValidationError, match="escapes"):
        builder(graph, "test", [source])
    assert list(outside.iterdir()) == []


def test_runtime_rejects_workspace_symlink_without_attachments(graph_config, tmp_path):
    graph = GraphContext(graph_config)
    outside = tmp_path / "functions"
    outside.mkdir()
    (graph.directory / "code_workspace").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValidationError, match="escapes"):
        RuntimeBuilder(graph).build(logger=Mock())
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("accept", ["application/json", "text/event-stream"])
@pytest.mark.parametrize("name", INVALID_NAMES)
def test_http_rejects_bad_session_before_starting_worker(api, monkeypatch, accept, name):
    client, _ = api
    worker = Mock(side_effect=AssertionError("Workflow must not start"))
    monkeypatch.setattr(execute_sync, "run_in_threadpool", worker)
    monkeypatch.setattr(execute_sync.threading, "Thread", worker)
    response = client.post(
        "/api/workflow/run",
        headers={"Accept": accept},
        json={"yaml_file": str(DEMO_YAML), "task_prompt": "test", "session_name": name},
    )
    assert response.status_code == 400
    assert "session_name" in response.json()["detail"]
    worker.assert_not_called()


@pytest.mark.parametrize("streaming", [False, True])
def test_direct_runner_rejects_traversal_before_loading_config(tmp_path, monkeypatch, streaming):
    module = execute_sync if streaming else sdk
    loader = Mock(side_effect=AssertionError("Config must not load"))
    monkeypatch.setattr(module, "load_config", loader)
    monkeypatch.setattr(module, "OUTPUT_ROOT", tmp_path / "WareHouse")
    kwargs = dict(
        yaml_file=DEMO_YAML,
        task_prompt="test",
        attachments=[],
        session_name=TRAVERSAL,
    )
    with pytest.raises(ValidationError):
        if streaming:
            execute_sync._run_workflow_with_logger(
                **kwargs, variables=None, log_level=None, log_callback=lambda *_: None
            )
        else:
            sdk.run_workflow(**kwargs)
    loader.assert_not_called()
    assert not (tmp_path / "WareHouse").exists()


@pytest.mark.parametrize("name", INVALID_NAMES)
def test_websocket_rejects_bad_session_without_registering_connection(api, name):
    client, manager = api
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws?" + urlencode({"session_id": name})):
            pytest.fail("Invalid session must not be accepted")
    assert exc.value.code == 1008
    assert not manager.active_connections


@pytest.mark.parametrize("name", [TRAVERSAL, r"session_..\..\outside", ".."])
def test_upload_service_rejects_bad_session_before_reading_file(tmp_path, name):
    service = AttachmentService(root=tmp_path / "WareHouse")
    upload = UploadFile(filename="sample.py", file=io.BytesIO(b"VALUE = 1\n"))
    with pytest.raises(ValidationError):
        asyncio.run(service.save_upload_file(name, upload))
    assert upload.file.tell() == 0
    assert list(service.attachments_root.iterdir()) == []


@pytest.mark.parametrize("session_name", [None, "   "])
def test_workflow_still_generates_default_session_name(api, tmp_path, session_name):
    client, _ = api
    payload = {"yaml_file": str(DEMO_YAML), "task_prompt": "test"}
    if session_name is not None:
        payload["session_name"] = session_name
    response = client.post("/api/workflow/run", json=payload)
    assert response.status_code == 200
    output_dir = Path(response.json()["output_dir"])
    assert output_dir.parent == tmp_path / "WareHouse"
    assert output_dir.name.startswith("sdk_demo_loop_counter_")


def test_generated_websocket_session_can_reconnect(api):
    client, manager = api
    with client.websocket_connect("/ws") as ws:
        session_id = ws.receive_json()["data"]["session_id"]
        assert session_id in manager.active_connections
    session = manager.session_store.create_session(
        session_id=session_id, yaml_file=str(DEMO_YAML), task_prompt="test"
    )
    session.append_message({"type": "test", "data": "replayed"})
    with client.websocket_connect("/ws?" + urlencode({"session_id": session_id})) as ws:
        assert ws.receive_json()["data"]["session_id"] == session_id
        assert ws.receive_json() == {"type": "test", "data": "replayed"}
        assert ws.receive_json()["type"] == "session_resumed"


@pytest.mark.parametrize("accept", ["application/json", "text/event-stream"])
def test_upload_then_workflow_round_trip_and_traversal_block(api, tmp_path, accept):
    client, _ = api
    with client.websocket_connect("/ws?session_id=upload_test") as ws:
        assert ws.receive_json()["data"]["session_id"] == "upload_test"
        response = client.post(
            "/api/uploads/upload_test",
            files={"file": ("sample.py", b"VALUE = 1\n", "text/x-python")},
        )
        assert response.status_code == 200
        assert client.get("/api/uploads/upload_test").status_code == 200
    sources = list((tmp_path / "WareHouse/session_upload_test").rglob("sample.py"))
    assert len(sources) == 1
    payload = {
        "yaml_file": str(DEMO_YAML),
        "task_prompt": "test",
        "attachments": [str(sources[0])],
        "attachment_session_id": "upload_test",
        "session_name": TRAVERSAL,
    }
    response = client.post("/api/workflow/run", headers={"Accept": accept}, json=payload)
    assert response.status_code == 400
    assert not (tmp_path / "functions").exists()

    payload["session_name"] = "session_safe_run"
    response = client.post("/api/workflow/run", headers={"Accept": accept}, json=payload)
    assert response.status_code == 200
    if accept == "text/event-stream":
        assert "event: completed" in response.text
        assert "event: error" not in response.text
    else:
        assert response.json()["status"] == "completed"
    stored = list((tmp_path / "WareHouse/session_safe_run").rglob("sample.py"))
    assert len(stored) == 1
    assert stored[0].read_bytes() == b"VALUE = 1\n"


@pytest.mark.parametrize("linked_part", ["", "code_workspace", "code_workspace/attachments"])
def test_upload_endpoints_reject_escaping_symlinks(api, tmp_path, linked_part):
    client, _ = api
    outside = tmp_path / "functions"
    outside.mkdir()
    link = tmp_path / "WareHouse/session_upload_test" / linked_part
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(outside, target_is_directory=True)
    with client.websocket_connect("/ws?session_id=upload_test") as ws:
        ws.receive_json()
        assert client.get("/api/uploads/upload_test").status_code == 400
        response = client.post(
            "/api/uploads/upload_test", files={"file": ("sample.py", b"VALUE = 1\n")}
        )
        assert response.status_code == 400
    assert list(outside.iterdir()) == []
