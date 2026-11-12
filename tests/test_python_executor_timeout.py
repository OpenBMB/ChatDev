"""Tests for PythonNodeExecutor timeout stream handling and output preservation."""

import subprocess
from unittest.mock import Mock

import pytest

from entity.configs import Node
from entity.messages import Message, MessageRole
from runtime.node.executor.base import ExecutionContext
from runtime.node.executor.python_executor import PythonNodeExecutor
from utils.code_execution import UNSAFE_CODE_EXECUTION_ENV


@pytest.fixture
def python_executor_fixture(tmp_path, monkeypatch):
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, "1")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    context = ExecutionContext(
        tool_manager=Mock(),
        function_manager=Mock(),
        log_manager=Mock(),
        global_state={
            "python_workspace_root": workspace,
            "vars": {UNSAFE_CODE_EXECUTION_ENV: "1"},
        },
    )
    node = Node.from_dict(
        {
            "id": "TestRunner",
            "type": "python",
            "config": {"timeout_seconds": 1, "encoding": "utf-8"},
        },
        path="node",
    )
    return PythonNodeExecutor(context), node, workspace


def test_python_executor_timeout_preserves_stdout_and_stderr(
    python_executor_fixture, monkeypatch
):
    executor, node, workspace = python_executor_fixture

    def mock_run(*args, **kwargs):
        exc = subprocess.TimeoutExpired(cmd=["python3", "script.py"], timeout=1)
        exc.stdout = b"partial stdout line\n"
        exc.stderr = b"partial stderr diagnostic\n"
        raise exc

    monkeypatch.setattr(subprocess, "run", mock_run)

    messages = executor.execute(
        node, [Message(role=MessageRole.USER, content="import time; time.sleep(2)")]
    )
    assert len(messages) == 1
    msg = messages[0]

    assert msg.role == MessageRole.ASSISTANT
    assert "==CODE EXECUTION FAILED==" in msg.content
    assert "Script did not finish within 1s" in msg.content
    assert "stderr:\npartial stderr diagnostic\n" in msg.content
    assert (
        "partial stdout line" not in msg.content
    )  # stdout should not leak into stderr content section

    assert msg.metadata["stderr"] == "partial stderr diagnostic\n"
    assert msg.metadata["stdout"] == "partial stdout line\n"
    assert msg.metadata["workspace"] == str(workspace)


def test_python_executor_timeout_handles_empty_streams(
    python_executor_fixture, monkeypatch
):
    executor, node, _workspace = python_executor_fixture

    def mock_run(*args, **kwargs):
        exc = subprocess.TimeoutExpired(cmd=["python3", "script.py"], timeout=1)
        exc.stdout = None
        exc.stderr = None
        raise exc

    monkeypatch.setattr(subprocess, "run", mock_run)

    messages = executor.execute(
        node, [Message(role=MessageRole.USER, content="import time; time.sleep(2)")]
    )
    assert len(messages) == 1
    msg = messages[0]

    assert "==CODE EXECUTION FAILED==" in msg.content
    assert "Script did not finish within 1s" in msg.content
    assert "stderr" not in msg.metadata
    assert "stdout" not in msg.metadata


def test_python_executor_timeout_handles_output_fallback(
    python_executor_fixture, monkeypatch
):
    executor, node, _workspace = python_executor_fixture

    def mock_run(*args, **kwargs):
        exc = subprocess.TimeoutExpired(
            cmd=["python3", "script.py"],
            timeout=1,
            output=b"legacy output buffer",
            stderr=b"error trace",
        )
        raise exc

    monkeypatch.setattr(subprocess, "run", mock_run)

    messages = executor.execute(
        node, [Message(role=MessageRole.USER, content="import time; time.sleep(2)")]
    )
    assert len(messages) == 1
    msg = messages[0]

    assert msg.metadata["stdout"] == "legacy output buffer"
    assert msg.metadata["stderr"] == "error trace"
    assert "stderr:\nerror trace" in msg.content
