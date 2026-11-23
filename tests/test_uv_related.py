from unittest.mock import Mock, patch

import pytest

from functions.function_calling.uv_related import (
    WorkspaceCommandContext,
    _validate_args,
    _validate_env,
    _validate_packages,
    init_python_env,
    install_python_packages,
    uv_run,
)


def test_validate_packages_string_coercion():
    assert _validate_packages("requests") == ["requests"]
    assert _validate_packages("requests, numpy  pandas") == [
        "requests",
        "numpy",
        "pandas",
    ]
    assert _validate_packages(["requests>=2.0.0", "click"]) == [
        "requests>=2.0.0",
        "click",
    ]


def test_validate_packages_errors():
    with pytest.raises(ValueError, match="at least one package is required"):
        _validate_packages(None)
    with pytest.raises(ValueError, match="package names cannot be empty"):
        _validate_packages("")
    with pytest.raises(ValueError, match="package names cannot be empty"):
        _validate_packages(["   "])
    with pytest.raises(ValueError, match="flags are not allowed"):
        _validate_packages(["-r", "requirements.txt"])
    with pytest.raises(ValueError, match="unsafe characters detected"):
        _validate_packages(["requests;rm -rf /"])
    with pytest.raises(TypeError, match="package entries must be strings"):
        _validate_packages([123])


def test_validate_args():
    assert _validate_args(None) == []
    assert _validate_args("") == []
    assert _validate_args("--verbose --count 3") == ["--verbose", "--count", "3"]
    assert _validate_args(["--flag", "value"]) == ["--flag", "value"]
    with pytest.raises(TypeError, match="args entries must be strings"):
        _validate_args([123])
    with pytest.raises(ValueError, match="args entries cannot be empty"):
        _validate_args(["  "])


def test_validate_env():
    assert _validate_env(None) == {}
    assert _validate_env({"API_KEY": "secret", "PORT": 8000}) == {
        "API_KEY": "secret",
        "PORT": "8000",
    }
    assert _validate_env('{"FOO": "bar"}') == {"FOO": "bar"}
    with pytest.raises(
        ValueError, match="environment variable keys must be non-empty strings"
    ):
        _validate_env({"": "val"})


def test_workspace_context(tmp_path):
    with pytest.raises(ValueError, match="_context is required"):
        WorkspaceCommandContext(None)

    with pytest.raises(ValueError, match="python_workspace_root missing"):
        WorkspaceCommandContext({})

    with pytest.raises(ValueError, match="python_workspace_root cannot be empty"):
        WorkspaceCommandContext({"python_workspace_root": "   "})

    ctx = WorkspaceCommandContext({"python_workspace_root": str(tmp_path)})
    assert ctx.workspace_root == tmp_path.resolve()

    resolved = ctx.resolve_under_workspace("sub/script.py")
    assert resolved == tmp_path.resolve() / "sub" / "script.py"

    with pytest.raises(ValueError, match="outside workspace root"):
        ctx.resolve_under_workspace("../outside.py")


@patch.dict("os.environ", {"MAC_ALLOW_UNSAFE_CODE_EXECUTION": "1"})
@patch("functions.function_calling.uv_related.subprocess.run")
def test_install_python_packages(mock_run, tmp_path):
    mock_run.return_value = Mock(returncode=0, stdout="installed", stderr="")
    ctx = {"python_workspace_root": str(tmp_path)}

    res = install_python_packages("requests, numpy", upgrade="true", _context=ctx)
    assert res["returncode"] == 0
    cmd = mock_run.call_args.args[0]
    assert cmd == ["uv", "add", "--upgrade", "requests", "numpy"]

    res_no_up = install_python_packages(["flask"], upgrade=False, _context=ctx)
    assert res_no_up["returncode"] == 0
    assert mock_run.call_args.args[0] == ["uv", "add", "flask"]


@patch.dict("os.environ", {"MAC_ALLOW_UNSAFE_CODE_EXECUTION": "1"})
@patch("functions.function_calling.uv_related.subprocess.run")
def test_init_python_env_new_workspace(mock_run, tmp_path):
    mock_run.return_value = Mock(returncode=0, stdout="ok", stderr="")
    ctx = {"python_workspace_root": str(tmp_path)}

    # Fresh directory without pyproject.toml -> runs uv init, uv venv, uv lock
    res = init_python_env(python_version="3.12", _context=ctx)
    assert len(res["steps"]) == 3
    assert res["steps"][0]["step"] == "uv init"
    assert res["steps"][1]["step"] == "uv venv"
    assert res["steps"][2]["step"] == "uv lock"

    # Calls sequence
    calls = [call.args[0] for call in mock_run.call_args_list]
    assert calls[0] == ["uv", "init", "--bare", "--no-workspace"]
    assert calls[1] == ["uv", "venv", "--python", "3.12"]
    assert calls[2] == ["uv", "lock"]


@patch.dict("os.environ", {"MAC_ALLOW_UNSAFE_CODE_EXECUTION": "1"})
@patch("functions.function_calling.uv_related.subprocess.run")
def test_init_python_env_existing_workspace(mock_run, tmp_path):
    mock_run.return_value = Mock(returncode=0, stdout="ok", stderr="")
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='test'\nversion='0.1.0'\n"
    )
    ctx = {"python_workspace_root": str(tmp_path)}

    # When pyproject.toml already exists -> skips uv init
    res = init_python_env(_context=ctx)
    assert len(res["steps"]) == 2
    assert res["steps"][0]["step"] == "uv venv"
    assert res["steps"][1]["step"] == "uv lock"

    calls = [call.args[0] for call in mock_run.call_args_list]
    assert calls[0] == ["uv", "venv"]
    assert calls[1] == ["uv", "lock"]


@patch.dict("os.environ", {"MAC_ALLOW_UNSAFE_CODE_EXECUTION": "1"})
@patch("functions.function_calling.uv_related.subprocess.run")
def test_uv_run_module_and_script(mock_run, tmp_path):
    mock_run.return_value = Mock(returncode=0, stdout="out", stderr="")
    ctx = {"python_workspace_root": str(tmp_path)}

    # module execution
    res = uv_run(module="myapp", args="--port 5000", env={"FOO": "BAR"}, _context=ctx)
    assert res["returncode"] == 0
    cmd = mock_run.call_args.args[0]
    assert cmd == ["uv", "run", "python", "-m", "myapp", "--port", "5000"]

    # script execution
    script_file = tmp_path / "run.py"
    script_file.write_text("print('hello')")
    res_script = uv_run(script="run.py", _context=ctx)
    assert res_script["returncode"] == 0
    assert mock_run.call_args.args[0] == ["uv", "run", str(script_file.resolve())]

    # mutual exclusion error
    with pytest.raises(ValueError, match="Provide exactly one"):
        uv_run(module="foo", script="bar.py", _context=ctx)
