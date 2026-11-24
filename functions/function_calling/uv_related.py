"""Utility tool to manage Python environments via uv."""

import os
import re
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from utils.code_execution import require_unsafe_code_execution

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


def _build_timeout_message(
    step: str | None, timeout_value: float, stdout: str, stderr: str
) -> str:
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

    def __init__(self, ctx: dict[str, Any] | None):
        if ctx is None:
            raise ValueError("_context is required for uv tools")
        self.workspace_root = self._require_workspace(ctx.get("python_workspace_root"))
        self._raw_ctx = ctx

    @staticmethod
    def _require_workspace(raw_path: Any) -> Path:
        if raw_path is None:
            raise ValueError("python_workspace_root missing from _context")
        raw_str = str(raw_path).strip()
        if not raw_str:
            raise ValueError("python_workspace_root cannot be empty")
        path = Path(raw_str).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def resolve_under_workspace(self, relative_path: str | Path) -> Path:
        candidate = Path(relative_path)
        absolute = (
            candidate if candidate.is_absolute() else self.workspace_root / candidate
        )
        absolute = absolute.expanduser().resolve()
        if (
            self.workspace_root not in absolute.parents
            and absolute != self.workspace_root
        ):
            raise ValueError("script path is outside workspace root")
        return absolute


def _split_package_specs(raw: str) -> list[str]:
    """Split package string on commas or whitespace while preserving commas inside brackets."""
    items: list[str] = []
    current: list[str] = []
    in_bracket = False
    for char in raw:
        if char == "[":
            in_bracket = True
            current.append(char)
        elif char == "]":
            in_bracket = False
            current.append(char)
        elif char in (",", " ", "\t", "\n", "\r") and not in_bracket:
            if current:
                items.append("".join(current).strip())
                current = []
        else:
            current.append(char)
    if current:
        items.append("".join(current).strip())
    return [item for item in items if item]


def _validate_packages(packages: Sequence[str] | str | None) -> list[str]:
    if packages is None:
        raise ValueError("at least one package is required")
    if isinstance(packages, str):
        raw = packages.strip()
        if not raw:
            raise ValueError("package names cannot be empty")
        items = _split_package_specs(raw)
    elif isinstance(packages, Sequence):
        items = list(packages)
    else:
        raise TypeError("packages must be a string or a sequence of strings")

    normalized: list[str] = []
    for pkg in items:
        if not isinstance(pkg, str):
            raise TypeError("package entries must be strings")
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
        raise TypeError("timeout_seconds must be a number")
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
        raise TypeError("timeout_seconds must be a number")

    if value <= 0:
        raise ValueError("timeout_seconds must be positive")
    return value


def _validate_flag_args(args: Sequence[str] | None) -> list[str]:
    normalized: list[str] = []
    if not args:
        return normalized
    for arg in args:
        if not isinstance(arg, str):
            raise TypeError("extra args must be strings")
        stripped = arg.strip()
        if not stripped:
            raise ValueError("extra args cannot be empty")
        if not stripped.startswith("-"):
            raise ValueError(f"extra args must be flags, got {arg}")
        normalized.append(stripped)
    return normalized


def _validate_args(args: Sequence[str] | str | None) -> list[str]:
    normalized: list[str] = []
    if not args:
        return normalized
    if isinstance(args, str):
        items = [a.strip() for a in args.split() if a.strip()]
    elif isinstance(args, Sequence):
        items = list(args)
    else:
        raise TypeError("args must be a string or a sequence of strings")

    for arg in items:
        if not isinstance(arg, str):
            raise TypeError("args entries must be strings")
        stripped = arg.strip()
        if not stripped:
            raise ValueError("args entries cannot be empty")
        normalized.append(stripped)
    return normalized


def _validate_env(env: Mapping[str, Any] | str | None) -> dict[str, str]:
    if env is None:
        return {}
    if isinstance(env, str):
        import json

        try:
            parsed = json.loads(env)
            if isinstance(parsed, Mapping):
                env = parsed
        except (json.JSONDecodeError, ValueError):
            pass
    if not isinstance(env, Mapping):
        raise TypeError("environment variable mapping required")
    result: dict[str, str] = {}
    for key, value in env.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("environment variable keys must be non-empty strings")
        result[key.strip()] = str(value)
    return result


def _run_uv_command(
    cmd: list[str],
    workspace_root: Path,
    *,
    step: str | None = None,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    require_unsafe_code_execution("uv command")
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
    timeout_seconds: float | None = None,
    # extra_args: Sequence[str] | None = None,
    _context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Install Python packages inside the workspace using uv add."""

    ctx = WorkspaceCommandContext(_context)
    safe_packages = _validate_packages(packages)
    timeout = _coerce_timeout_seconds(timeout_seconds)

    if isinstance(upgrade, str):
        upgrade = upgrade.strip().lower() in ("true", "1", "yes")
    elif isinstance(upgrade, (int, float)):
        upgrade = bool(upgrade)

    cmd: list[str] = ["uv", "add"]
    if upgrade:
        cmd.append("--upgrade")

    # if extra_args:
    #     flags = _validate_flag_args(extra_args)
    #     cmd.extend(flags)

    cmd.extend(safe_packages)
    result = _run_uv_command(cmd, ctx.workspace_root, step="uv add", timeout=timeout)
    # result["workspace_root"] = str(ctx.workspace_root)
    return result


def init_python_env(
    *,
    # recreate: bool = False,
    python_version: str | None = None,
    timeout_seconds: float | None = None,
    # lock_args: Sequence[str] | None = None,
    # venv_args: Sequence[str] | None = None,
    _context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run uv init, uv venv, and uv lock inside the workspace."""

    ctx = WorkspaceCommandContext(_context)
    steps: list[dict[str, Any]] = []
    timeout = _coerce_timeout_seconds(timeout_seconds)

    pyproject = ctx.workspace_root / "pyproject.toml"
    if not pyproject.exists():
        init_cmd: list[str] = ["uv", "init", "--bare", "--no-workspace"]
        init_result = _run_uv_command(
            init_cmd, ctx.workspace_root, step="uv init", timeout=timeout
        )
        steps.append(init_result)
        if init_result["returncode"] != 0:
            return {
                "workspace_root": str(ctx.workspace_root),
                "steps": steps,
            }

    venv_cmd: list[str] = ["uv", "venv"]
    # if recreate:
    #     venv_cmd.append("--recreate")
    # venv_cmd.extend(_validate_flag_args(venv_args))
    if python_version is not None:
        python_spec = str(python_version).strip()
        if not python_spec:
            raise ValueError("python argument cannot be empty")
        venv_cmd.extend(["--python", python_spec])

    venv_result = _run_uv_command(
        venv_cmd, ctx.workspace_root, step="uv venv", timeout=timeout
    )
    steps.append(venv_result)
    if venv_result["returncode"] != 0:
        return {
            "workspace_root": str(ctx.workspace_root),
            "steps": steps,
        }

    lock_cmd: list[str] = ["uv", "lock"]
    # lock_cmd.extend(_validate_flag_args(lock_args))
    lock_result = _run_uv_command(
        lock_cmd, ctx.workspace_root, step="uv lock", timeout=timeout
    )
    steps.append(lock_result)

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
    _context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute uv run for a module or script inside the workspace root."""

    ctx = WorkspaceCommandContext(_context)
    timeout_seconds = _coerce_timeout_seconds(timeout_seconds)

    has_module = module is not None
    has_script = script is not None
    if has_module == has_script:
        raise ValueError("Provide exactly one of module or script")

    cmd: list[str] = ["uv", "run"]
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
