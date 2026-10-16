"""Guard untrusted code entry points and processor file writes."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from runtime import sdk
from entity.configs import Node
from entity.configs.node.tooling import McpLocalConfig
from entity.messages import Message, MessageRole
from functions.edge_processor import transformers
from functions.function_calling.code_executor import execute_code
from functions.function_calling import uv_related, video
from runtime.node.agent.tool import tool_manager
from runtime.node.executor.base import ExecutionContext
from runtime.node.executor.python_executor import PythonNodeExecutor
from server.routes import execute_sync, workflows
from utils.attachments import AttachmentStore
from utils.code_execution import UNSAFE_CODE_EXECUTION_ENV, require_unsafe_code_execution
from utils.error_handler import add_exception_handlers
from utils.exceptions import SecurityError


@pytest.fixture(autouse=True)
def disable_execution(monkeypatch):
    monkeypatch.delenv(UNSAFE_CODE_EXECUTION_ENV, raising=False)


@pytest.fixture
def workspace_context(tmp_path):
    workspace = tmp_path / "session" / "code_workspace"
    store = AttachmentStore(workspace / "attachments")
    (workspace / "keep.txt").write_text("original")
    (store.root / "input.txt").write_text("attachment")
    return {
        "python_workspace_root": workspace,
        "graph_directory": workspace.parent,
        "attachment_store": store,
    }


@pytest.fixture
def fake_launch(monkeypatch):
    process = Mock(returncode=0)
    process.communicate.return_value = (b"executed\n", b"")
    launch = Mock(return_value=process)
    monkeypatch.setattr(transformers.subprocess, "Popen", launch)
    return launch


def _code_block(filename, code="print('ok')"):
    return f"{filename}\n```python\n{code}\n```"


@pytest.mark.parametrize("value", [None, "", "0", "false", "no", "off", "typo"])
def test_execution_requires_explicit_opt_in(monkeypatch, value):
    if value is not None:
        monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, value)
    with pytest.raises(SecurityError, match=UNSAFE_CODE_EXECUTION_ENV):
        require_unsafe_code_execution("test operation")


@pytest.mark.parametrize("value", ["1", "true", "YES", " on "])
def test_explicit_opt_in_is_supported(monkeypatch, value):
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, value)
    require_unsafe_code_execution("test operation")


def test_disabled_processor_does_not_clear_or_write_files(workspace_context, fake_launch):
    workspace_context[UNSAFE_CODE_EXECUTION_ENV] = "1"
    workspace_context["vars"] = {UNSAFE_CODE_EXECUTION_ENV: "1"}
    with pytest.raises(SecurityError, match=UNSAFE_CODE_EXECUTION_ENV):
        transformers.code_save_and_run(_code_block("main.py"), workspace_context)
    workspace = workspace_context["python_workspace_root"]
    assert (workspace / "keep.txt").read_text() == "original"
    assert not (workspace / "main.py").exists()
    fake_launch.assert_not_called()


@pytest.mark.parametrize("filename", [
    "../../escaped.py", "src/../../escaped.py", "src/../main.py",
    r"..\..\escaped.py", r"C:\escaped.py", "C:escaped.py",
    r"\\server\share\escaped.py", "attachments/changed.py",
    r"attachments\changed.py", "attachments", ".", "..", " ", "bad\x00name.py",
])
def test_processor_validates_all_files_before_clearing(
    workspace_context, fake_launch, monkeypatch, filename
):
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, "1")
    payload = _code_block("main.py") + "\n" + _code_block(filename)
    with pytest.raises(SecurityError):
        transformers.code_save_and_run(payload, workspace_context)
    workspace = workspace_context["python_workspace_root"]
    assert (workspace / "keep.txt").read_text() == "original"
    assert (workspace / "attachments/input.txt").read_text() == "attachment"
    assert not (workspace / "main.py").exists()
    fake_launch.assert_not_called()


def test_processor_rejects_absolute_path(workspace_context, tmp_path, fake_launch, monkeypatch):
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, "1")
    target = tmp_path / "outside.py"
    with pytest.raises(SecurityError):
        transformers.code_save_and_run(_code_block(str(target)), workspace_context)
    assert not target.exists()
    assert (workspace_context["python_workspace_root"] / "keep.txt").exists()
    fake_launch.assert_not_called()


@pytest.mark.parametrize("target_kind", ["outside", "attachments"])
def test_processor_rejects_symlink_targets(
    workspace_context, tmp_path, fake_launch, monkeypatch, target_kind
):
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, "1")
    workspace = workspace_context["python_workspace_root"]
    target = tmp_path / "outside" if target_kind == "outside" else workspace / "attachments"
    target.mkdir(exist_ok=True)
    (workspace / "alias").symlink_to(target, target_is_directory=True)
    with pytest.raises(SecurityError):
        transformers.code_save_and_run(_code_block("alias/changed.py"), workspace_context)
    assert not (target / "changed.py").exists()
    assert (workspace / "keep.txt").exists()
    assert (workspace / "alias").is_symlink()
    fake_launch.assert_not_called()


@pytest.mark.parametrize("filename", [
    "Attachments/input.txt", "ATTACHMENTS/nested/new.py", "aTtAcHmEnTs",
])
def test_processor_rejects_attachment_case_aliases(
    workspace_context, fake_launch, monkeypatch, filename
):
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, "1")
    workspace = workspace_context["python_workspace_root"]
    attachments = workspace / "attachments"
    alias = workspace / "Attachments"
    if not alias.exists() or not alias.samefile(attachments):
        pytest.skip("Requires a case-insensitive filesystem")

    payload = _code_block("main.py") + "\n" + _code_block(filename, "REVIEW_MARKER")
    with pytest.raises(SecurityError, match="attachments"):
        transformers.code_save_and_run(payload, workspace_context)

    assert (attachments / "input.txt").read_text() == "attachment"
    assert not (attachments / "nested").exists()
    assert (workspace / "keep.txt").read_text() == "original"
    assert not (workspace / "main.py").exists()
    fake_launch.assert_not_called()


def test_processor_cleanup_preserves_attachment_directory_with_different_case(
    workspace_context, fake_launch, monkeypatch
):
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, "1")
    workspace = workspace_context["python_workspace_root"]
    attachments = workspace / "attachments"
    alias = workspace / "Attachments"
    if not alias.exists() or not alias.samefile(attachments):
        pytest.skip("Requires a case-insensitive filesystem")

    temporary = workspace / "inputs_to_rename"
    attachments.rename(temporary)
    temporary.rename(alias)
    assert "Attachments" in {item.name for item in workspace.iterdir()}

    transformers.code_save_and_run(_code_block("main.py"), workspace_context)

    assert (attachments / "input.txt").read_text() == "attachment"
    assert (workspace / "main.py").exists()
    assert not (workspace / "keep.txt").exists()
    fake_launch.assert_called_once()


def test_processor_allows_distinct_case_sensitive_directory(
    workspace_context, fake_launch, monkeypatch
):
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, "1")
    workspace = workspace_context["python_workspace_root"]
    alias = workspace / "Attachments"
    if alias.exists():
        pytest.skip("Requires a case-sensitive filesystem")

    transformers.code_save_and_run(_code_block("Attachments/new.py", "VALUE = 1"), workspace_context)

    assert (alias / "new.py").read_text() == "VALUE = 1"
    assert (workspace / "attachments/input.txt").read_text() == "attachment"
    fake_launch.assert_called_once()


def test_enabled_processor_preserves_nested_files_and_attachments(
    workspace_context, tmp_path, fake_launch, monkeypatch
):
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, "1")
    workspace = workspace_context["python_workspace_root"]
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("external")
    (workspace / "old_link").symlink_to(outside, target_is_directory=True)
    payload = _code_block("main.py") + "\n" + _code_block("src/helpers.py", "VALUE = 1")
    result = transformers.code_save_and_run(payload, workspace_context)
    assert (workspace / "main.py").read_text() == "print('ok')"
    assert (workspace / "src/helpers.py").read_text() == "VALUE = 1"
    assert not (workspace / "keep.txt").exists()
    assert not (workspace / "old_link").is_symlink()
    assert (outside / "keep.txt").read_text() == "external"
    assert (workspace / "attachments/input.txt").read_text() == "attachment"
    assert "executed" in result
    args, kwargs = fake_launch.call_args
    assert args == (["uv", "run", "main.py"],)
    assert kwargs["cwd"] == str(workspace)
    assert not kwargs.get("shell", False)


@pytest.mark.parametrize("target_kind", ["inside", "outside"])
def test_processor_rejects_linked_attachments_before_cleanup(
    workspace_context, tmp_path, fake_launch, monkeypatch, target_kind
):
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, "1")
    workspace = workspace_context["python_workspace_root"]
    target = (workspace if target_kind == "inside" else tmp_path) / "inputs"
    attachments = workspace / "attachments"
    attachments.rename(target)
    attachments.symlink_to(target, target_is_directory=True)
    with pytest.raises(SecurityError, match="symbolic link"):
        transformers.code_save_and_run(_code_block("main.py"), workspace_context)
    assert (target / "input.txt").read_text() == "attachment"
    assert (workspace / "keep.txt").read_text() == "original"
    assert not (workspace / "main.py").exists()
    fake_launch.assert_not_called()


def _python_executor(workspace, env=None):
    context = ExecutionContext(
        tool_manager=Mock(), function_manager=Mock(), log_manager=Mock(),
        global_state={"python_workspace_root": workspace, "vars": {UNSAFE_CODE_EXECUTION_ENV: "1"}},
    )
    node = Node.from_dict(
        {"id": "Runner", "type": "python", "config": {"env": env or {}}}, path="node"
    )
    return PythonNodeExecutor(context), node


def test_python_node_env_cannot_enable_execution(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    executor, node = _python_executor(workspace, {UNSAFE_CODE_EXECUTION_ENV: "1"})
    run = Mock(side_effect=AssertionError("Must not start a process"))
    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(SecurityError, match=UNSAFE_CODE_EXECUTION_ENV):
        executor.execute(node, [Message(role=MessageRole.USER, content="print('ok')")])
    assert not workspace.exists()
    run.assert_not_called()


def test_enabled_python_node_executes_harmless_code(tmp_path, monkeypatch):
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, "1")
    executor, node = _python_executor(tmp_path / "workspace")
    messages = executor.execute(node, [Message(role=MessageRole.USER, content="print(6 * 7)")])
    assert messages[0].text_content().strip() == "42"


def test_execute_code_is_blocked_before_saving_script(tmp_path, monkeypatch):
    temp_code_dir = tmp_path / "scripts"
    monkeypatch.setenv("TEMP_CODE_DIR", str(temp_code_dir))
    with pytest.raises(SecurityError, match=UNSAFE_CODE_EXECUTION_ENV):
        execute_code("print('ok')")
    assert not temp_code_dir.exists()


def test_execute_code_works_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, "1")
    monkeypatch.setenv("TEMP_CODE_DIR", str(tmp_path))
    assert execute_code("print(6 * 7)").strip() == "42"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("operation", ["run", "install", "init"])
def test_uv_entry_points_cannot_override_server_policy(workspace_context, monkeypatch, operation):
    run = Mock(side_effect=AssertionError("Must not start a process"))
    monkeypatch.setattr(uv_related.subprocess, "run", run)
    with pytest.raises(SecurityError, match=UNSAFE_CODE_EXECUTION_ENV):
        if operation == "run":
            uv_related.uv_run(
                module="example", env={UNSAFE_CODE_EXECUTION_ENV: "1"}, _context=workspace_context
            )
        elif operation == "install":
            uv_related.install_python_packages(["example"], _context=workspace_context)
        else:
            uv_related.init_python_env(_context=workspace_context)
    run.assert_not_called()


def test_uv_run_is_available_when_enabled(workspace_context, monkeypatch):
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, "1")
    run = Mock(return_value=subprocess.CompletedProcess([], 0, stdout="ok", stderr=""))
    monkeypatch.setattr(uv_related.subprocess, "run", run)
    result = uv_related.uv_run(module="example", _context=workspace_context)
    assert result["returncode"] == 0
    assert run.call_args.args[0] == ["uv", "run", "python", "-m", "example"]


def test_manim_is_blocked_before_clearing_media(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    media = tmp_path / "media"
    media.mkdir()
    (media / "keep.txt").write_text("original")
    with pytest.raises(SecurityError, match=UNSAFE_CODE_EXECUTION_ENV):
        video.render_manim("unused.py")
    assert (media / "keep.txt").read_text() == "original"


def test_local_mcp_env_cannot_enable_execution(monkeypatch):
    create_client = Mock(side_effect=AssertionError("Must not start MCP"))
    monkeypatch.setattr(tool_manager, "_StdioClientWrapper", create_client)
    manager = tool_manager.ToolManager()
    config = McpLocalConfig.from_dict(
        {"command": sys.executable, "env": {UNSAFE_CODE_EXECUTION_ENV: "1"}}, path="tooling"
    )
    with pytest.raises(SecurityError, match=UNSAFE_CODE_EXECUTION_ENV):
        manager._get_stdio_client(config, config.cache_key())
    create_client.assert_not_called()


def test_local_mcp_opt_in_and_cached_client_policy(monkeypatch):
    manager = tool_manager.ToolManager()
    config = McpLocalConfig.from_dict({"command": sys.executable}, path="tooling")
    create_client = Mock()
    monkeypatch.setattr(tool_manager, "_StdioClientWrapper", create_client)
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, "1")
    assert manager._get_stdio_client(config, config.cache_key()) is create_client.return_value
    monkeypatch.delenv(UNSAFE_CODE_EXECUTION_ENV)
    with pytest.raises(SecurityError):
        manager._get_stdio_client(config, config.cache_key())
    create_client.assert_called_once_with(config)


def _workflow(kind, code):
    graph = {
        "id": "execution_policy_test", "start": ["Source"],
        "nodes": [
            {"id": "Source", "type": "literal", "config": {"content": code, "role": "assistant"}},
            {"id": "Runner", "type": "python" if kind == "python" else "passthrough", "config": {}},
        ],
        "edges": [{"from": "Source", "to": "Runner", "trigger": True, "carry_data": True}],
    }
    if kind == "processor":
        graph["edges"][0]["process"] = {"type": "function", "config": {"name": "code_save_and_run"}}
    else:
        graph["nodes"][1]["config"]["env"] = {UNSAFE_CODE_EXECUTION_ENV: "1"}
    return {"version": "0.4.0", "vars": {UNSAFE_CODE_EXECUTION_ENV: "1"}, "graph": graph}


@pytest.fixture
def workflow_api(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    yaml_dir = tmp_path / "yaml_instance"
    yaml_dir.mkdir()
    for module in (sdk, execute_sync, workflows):
        monkeypatch.setattr(module, "YAML_DIR", yaml_dir)
    app = FastAPI()
    add_exception_handlers(app)
    app.include_router(workflows.router)
    app.include_router(execute_sync.router)
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("kind", ["python", "processor"])
@pytest.mark.parametrize("accept", ["application/json", "text/event-stream"])
def test_uploaded_workflow_cannot_enable_execution(workflow_api, tmp_path, kind, accept):
    code = _code_block("main.py") if kind == "processor" else "print('ok')"
    response = workflow_api.post(
        "/api/workflows/upload/content",
        json={"filename": "policy.yaml", "content": yaml.safe_dump(_workflow(kind, code))},
    )
    assert response.status_code == 200
    response = workflow_api.post(
        "/api/workflow/run", headers={"Accept": accept},
        json={"yaml_file": "policy.yaml", "task_prompt": "test", "session_name": "session_policy"},
    )
    if accept == "application/json":
        assert response.status_code == 403
    else:
        assert response.status_code == 200
        assert "event: error" in response.text
        assert "event: completed" not in response.text
    assert UNSAFE_CODE_EXECUTION_ENV in response.text
    assert not list((tmp_path / "WareHouse").rglob("*.py"))


@pytest.mark.parametrize("accept", ["application/json", "text/event-stream"])
def test_uploaded_processor_cannot_plant_module_even_when_enabled(
    workflow_api, tmp_path, monkeypatch, fake_launch, accept
):
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, "1")
    code = _code_block("../../../functions/function_calling/planted.py", "VALUE = 1")
    response = workflow_api.post(
        "/api/workflows/upload/content",
        json={"filename": "traversal.yaml", "content": yaml.safe_dump(_workflow("processor", code))},
    )
    assert response.status_code == 200
    response = workflow_api.post(
        "/api/workflow/run", headers={"Accept": accept},
        json={"yaml_file": "traversal.yaml", "task_prompt": "test", "session_name": "session_policy"},
    )
    if accept == "application/json":
        assert response.status_code == 403
    else:
        assert "event: error" in response.text
        assert "event: completed" not in response.text
    assert "Invalid code filename" in response.text
    assert not (tmp_path / "functions").exists()
    fake_launch.assert_not_called()


@pytest.mark.parametrize("kind", ["python", "processor"])
def test_uploaded_workflow_runs_after_server_opt_in(
    workflow_api, monkeypatch, fake_launch, kind
):
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, "1")
    code = _code_block("main.py") if kind == "processor" else "print('ok')"
    workflow_api.post(
        "/api/workflows/upload/content",
        json={"filename": "enabled.yaml", "content": yaml.safe_dump(_workflow(kind, code))},
    )
    # subprocess.run uses Popen as a context manager; keep this test deterministic.
    if kind == "python":
        monkeypatch.setattr(subprocess, "run", Mock(return_value=subprocess.CompletedProcess([], 0, b"ok\n", b"")))
    response = workflow_api.post(
        "/api/workflow/run",
        json={"yaml_file": "enabled.yaml", "task_prompt": "test", "session_name": "session_enabled"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert "ok" in response.json()["final_message"] or "executed" in response.json()["final_message"]
