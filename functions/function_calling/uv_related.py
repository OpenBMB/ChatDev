"""Utility tool to manage Python environments via uv."""

import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

_SAFE_PACKAGE_RE = re.compile(r"^[A-Za-z0-9_.\-+=<>!\[\],@:/]+$")
_DEFAULT_TIMEOUT = float(os.getenv("LIB_INSTALL_TIMEOUT", "120"))
_OUTPUT_SNIPPET_LIMIT = 240


def _trim_output_preview(stdout: str, stderr: str) -> str | None:
    """Return a short preview from stdout or stderr for error messaging."""

    preview_source = stdout.strip() or stderr.strip()
    if not preview_source:
        return None
    if len(preview_source) <= _OUTPUT_SNIPPET_LIMIT:
        return preview_source
    return f"{preview_source[:_OUTPUT_SNIPPET_LIMIT].rstrip()}... [truncated]"


def _build_timeout_message(step: str | None, timeout_value: float, stdout: str, stderr: str) -> str:
    """Create a descriptive timeout error message with optional output preview."""

    label = "uv command"
    if step:
        label = f"{label} ({step})"
    message = f"{label} timed out after {timeout_value} seconds"
    preview = _trim_output_preview(stdout, stderr)
    if preview:
        return f"{message}. Last output: {preview}"
    return message


class WorkspaceCommandContext:
    """Resolve the workspace root from the injected runtime context."""

    def __init__(self, ctx: Dict[str, Any] | None):
        if ctx is None:
            raise ValueError("_context is required for uv tools")
        self.workspace_root = self._require_workspace(ctx.get("python_workspace_root"))
        self._raw_ctx = ctx

    @staticmethod
    def _require_workspace(raw_path: Any) -> Path:
        if raw_path is None:
            raise ValueError("python_workspace_root missing from _context")
        path = Path(raw_path).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def resolve_under_workspace(self, relative_path: str | Path) -> Path:
        candidate = Path(relative_path)
        absolute = candidate if candidate.is_absolute() else self.workspace_root / candidate
        absolute = absolute.expanduser().resolve()
        if self.workspace_root not in absolute.parents and absolute != self.workspace_root:
            raise ValueError("script path is outside workspace root")
        return absolute


def _validate_packages(packages: Sequence[str]) -> List[str]:
    normalized: List[str] = []
    for pkg in packages:
        if not isinstance(pkg, str):
            raise ValueError("package entries must be strings")
        stripped = pkg.strip()
        if not stripped:
            raise ValueError("package names cannot be empty")
        if not _SAFE_PACKAGE_RE.match(stripped):
            raise ValueError(f"unsafe characters detected in package spec {pkg}")
        if stripped.startswith("-"):
            raise ValueError(f"flags are not allowed in packages list: {pkg}")
        normalized.append(stripped)
    if not normalized:
        raise ValueError("at least one package is required")
    return normalized


def _coerce_timeout_seconds(timeout_seconds: Any) -> float | None:
    if timeout_seconds is None:
        return None
    if isinstance(timeout_seconds, bool):
        raise ValueError("timeout_seconds must be a number")
    if isinstance(timeout_seconds, (int, float)):
        value = float(timeout_seconds)
    elif isinstance(timeout_seconds, str):
        raw = timeout_seconds.strip()
        if not raw:
            raise ValueError("timeout_seconds cannot be empty")
        try:
            if re.fullmatch(r"[+-]?\d+", raw):
                value = float(int(raw))
            else:
                value = float(raw)
        except ValueError as exc:
            raise ValueError("timeout_seconds must be a number") from exc
    else:
        raise ValueError("timeout_seconds must be a number")

    if value <= 0:
        raise ValueError("timeout_seconds must be positive")
    return value


def _validate_flag_args(args: Sequence[str] | None) -> List[str]:
    normalized: List[str] = []
    if not args:
        return normalized
    for arg in args:
        if not isinstance(arg, str):
            raise ValueError("extra args must be strings")
        stripped = arg.strip()
        if not stripped:
            raise ValueError("extra args cannot be empty")
        if not stripped.startswith("-"):
            raise ValueError(f"extra args must be flags, got {arg}")
        normalized.append(stripped)
    return normalized


def _validate_args(args: Sequence[str] | None) -> List[str]:
    normalized: List[str] = []
    if not args:
        return normalized
    for arg in args:
        if not isinstance(arg, str):
            raise ValueError("args entries must be strings")
        stripped = arg.strip()
        if not stripped:
            raise ValueError("args entries cannot be empty")
        normalized.append(stripped)
    return normalized


def _validate_env(env: Mapping[str, str] | None) -> Dict[str, str]:
    if env is None:
        return {}
    result: Dict[str, str] = {}
    for key, value in env.items():
        if not isinstance(key, str) or not key:
            raise ValueError("environment variable keys must be non-empty strings")
        if not isinstance(value, str):
            raise ValueError("environment variable values must be strings")
        result[key] = value
    return result


def _run_uv_command(
    cmd: List[str],
    workspace_root: Path,
    *,
    step: str | None = None,
    env: Dict[str, str] | None = None,
    timeout: float | None = None,
) -> Dict[str, Any]:
    timeout_value = _DEFAULT_TIMEOUT if timeout is None else timeout
    env_vars = None if env is None else {**os.environ, **env}
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(workspace_root),
            capture_output=True,
            text=True,
            timeout=timeout_value,
            check=False,
            env=env_vars,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("uv command not found in PATH") from exc
    except subprocess.TimeoutExpired as exc:
        stdout_text = exc.stdout
        if stdout_text is None:
            stdout_text = getattr(exc, "output", "") or ""
        stderr_text = exc.stderr or ""
        message = _build_timeout_message(step, timeout_value, stdout_text, stderr_text)
        return {
            "command": cmd,
            "stdout": stdout_text,
            "stderr": stderr_text,
            "returncode": None,
            "step": step,
            "timed_out": True,
            "timeout": timeout_value,
            "error": message,
        }

    return {
        "command": cmd,
        "stdout": completed.stdout or "",
        "stderr": completed.stderr or "",
        "returncode": completed.returncode,
        # "cwd": str(workspace_root),
        "step": step,
    }


def install_python_packages(
    packages: Sequence[str],
    *,
    upgrade: bool = False,
    # extra_args: Sequence[str] | None = None,
    _context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Install Python packages inside the workspace using uv add."""

    ctx = WorkspaceCommandContext(_context)
    safe_packages = _validate_packages(packages)
    cmd: List[str] = ["uv", "add"]
    if upgrade:
        cmd.append("--upgrade")

    # if extra_args:
    #     flags = _validate_flag_args(extra_args)
    #     cmd.extend(flags)

    cmd.extend(safe_packages)
    result = _run_uv_command(cmd, ctx.workspace_root, step="uv add")
    # result["workspace_root"] = str(ctx.workspace_root)
    return result


def init_python_env(
    *,
    # recreate: bool = False,
    python_version: str | None = None,
    # lock_args: Sequence[str] | None = None,
    # venv_args: Sequence[str] | None = None,
    _context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Run uv lock and uv venv inside the workspace."""

    ctx = WorkspaceCommandContext(_context)
    steps: List[Dict[str, Any]] = []

    lock_cmd: List[str] = ["uv", "lock"]
    # lock_cmd.extend(_validate_flag_args(lock_args))
    lock_result = _run_uv_command(lock_cmd, ctx.workspace_root, step="uv lock")
    steps.append(lock_result)
    if lock_result["returncode"] != 0:
        return {
            "workspace_root": str(ctx.workspace_root),
            "steps": steps,
        }

    venv_cmd: List[str] = ["uv", "venv"]
    # if recreate:
    #     venv_cmd.append("--recreate")
    # venv_cmd.extend(_validate_flag_args(venv_args))
    if python_version is not None:
        python_spec = python_version.strip()
        if not python_spec:
            raise ValueError("python argument cannot be empty")
        venv_cmd.extend(["--python", python_spec])

    venv_result = _run_uv_command(venv_cmd, ctx.workspace_root, step="uv venv")
    steps.append(venv_result)

    init_cmd: List[str] = ["uv", "init", "--bare", "--no-workspace"]
    init_result = _run_uv_command(init_cmd, ctx.workspace_root, step="uv init")
    steps.append(init_result)

    return {
        "workspace_root": str(ctx.workspace_root),
        "steps": steps,
    }


def uv_run(
    *,
    module: str | None = None,
    script: str | None = None,
    args: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    timeout_seconds: float | None = None,
    _context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Execute uv run for a module or script inside the workspace root."""

    ctx = WorkspaceCommandContext(_context)
    timeout_seconds = _coerce_timeout_seconds(timeout_seconds)

    has_module = module is not None
    has_script = script is not None
    if has_module == has_script:
        raise ValueError("Provide exactly one of module or script")

    cmd: List[str] = ["uv", "run"]
    if has_module:
        module_name = module.strip()
        if not module_name:
            raise ValueError("module cannot be empty")
        cmd.extend(["python", "-m", module_name])
    else:
        script_value = script.strip() if isinstance(script, str) else script
        if not script_value:
            raise ValueError("script cannot be empty")
        script_path = ctx.resolve_under_workspace(script_value)
        cmd.append(str(script_path))

    cmd.extend(_validate_args(args))
    env_overrides = _validate_env(env)
    result = _run_uv_command(
        cmd,
        ctx.workspace_root,
        step="uv run",
        env=env_overrides,
        timeout=timeout_seconds,
    )
    result["workspace_root"] = str(ctx.workspace_root)
    return result
