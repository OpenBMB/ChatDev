"""Unit tests for execute_code function tool."""

import pytest

from functions.function_calling.code_executor import execute_code
from utils.code_execution import UNSAFE_CODE_EXECUTION_ENV
from utils.exceptions import SecurityError


@pytest.fixture(autouse=True)
def disable_execution_by_default(monkeypatch):
    monkeypatch.delenv(UNSAFE_CODE_EXECUTION_ENV, raising=False)


def test_execute_code_security_gate_without_env(tmp_path, monkeypatch):
    monkeypatch.setenv("TEMP_CODE_DIR", str(tmp_path))
    with pytest.raises(SecurityError, match=UNSAFE_CODE_EXECUTION_ENV):
        execute_code("print('blocked')")


def test_execute_code_basic_stdout(tmp_path, monkeypatch):
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, "1")
    monkeypatch.setenv("TEMP_CODE_DIR", str(tmp_path))
    res = execute_code("print('hello world')")
    assert res.strip() == "hello world"
    assert list(tmp_path.iterdir()) == []


def test_execute_code_with_stderr(tmp_path, monkeypatch):
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, "1")
    monkeypatch.setenv("TEMP_CODE_DIR", str(tmp_path))
    code = "import sys\nsys.stdout.write('out')\nsys.stderr.write('err')"
    res = execute_code(code)
    assert "out" in res
    assert "err" in res
    assert list(tmp_path.iterdir()) == []


def test_execute_code_syntax_error(tmp_path, monkeypatch):
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, "1")
    monkeypatch.setenv("TEMP_CODE_DIR", str(tmp_path))
    res = execute_code("def broken_syntax(")
    assert "SyntaxError" in res
    assert list(tmp_path.iterdir()) == []


def test_execute_code_invalid_code_type(monkeypatch):
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, "1")
    assert execute_code(None) == "Setup error: code must be a string"
    assert execute_code(12345) == "Setup error: code must be a string"
    assert execute_code(["print(1)"]) == "Setup error: code must be a string"


def test_execute_code_empty_code(monkeypatch):
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, "1")
    assert execute_code("") == "Setup error: code cannot be empty"
    assert execute_code("   \n\t  ") == "Setup error: code cannot be empty"


def test_execute_code_string_timeout_coercion(tmp_path, monkeypatch):
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, "1")
    monkeypatch.setenv("TEMP_CODE_DIR", str(tmp_path))
    res = execute_code("print(10 * 10)", time_out="30")
    assert res.strip() == "100"


def test_execute_code_invalid_timeout(monkeypatch):
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, "1")
    assert (
        execute_code("print(1)", time_out=True)
        == "Setup error: time_out must be a positive number"
    )
    assert (
        execute_code("print(1)", time_out=False)
        == "Setup error: time_out must be a positive number"
    )
    assert (
        execute_code("print(1)", time_out="invalid")
        == "Setup error: time_out must be a positive number"
    )
    assert (
        execute_code("print(1)", time_out="") == "Setup error: time_out cannot be empty"
    )
    assert (
        execute_code("print(1)", time_out=[10])
        == "Setup error: time_out must be a positive number"
    )
    assert (
        execute_code("print(1)", time_out=0) == "Setup error: time_out must be positive"
    )
    assert (
        execute_code("print(1)", time_out=-5)
        == "Setup error: time_out must be positive"
    )


def test_execute_code_timeout_expired(tmp_path, monkeypatch):
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, "1")
    monkeypatch.setenv("TEMP_CODE_DIR", str(tmp_path))
    code = "import time\ntime.sleep(2)"
    res = execute_code(code, time_out=0.1)
    assert "Error: Execution timed out after 0.1 seconds." in res
    assert list(tmp_path.iterdir()) == []


def test_execute_code_nested_temp_directory(tmp_path, monkeypatch):
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, "1")
    nested_dir = tmp_path / "a" / "b" / "c" / "scripts"
    monkeypatch.setenv("TEMP_CODE_DIR", str(nested_dir))
    res = execute_code("print('nested-ok')")
    assert res.strip() == "nested-ok"
    assert nested_dir.exists()
    assert list(nested_dir.iterdir()) == []


def test_execute_code_with_context_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, "1")
    monkeypatch.delenv("TEMP_CODE_DIR", raising=False)
    workspace = tmp_path / "workspace_session"
    ctx = {"python_workspace_root": str(workspace)}
    res = execute_code("print('ctx-ok')", _context=ctx)
    assert res.strip() == "ctx-ok"
    assert (workspace / "temp").exists()
    assert list((workspace / "temp").iterdir()) == []
