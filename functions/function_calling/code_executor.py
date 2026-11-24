import contextlib
import math
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from utils.code_execution import require_unsafe_code_execution


def execute_code(
    code: str,
    time_out: float | str = 60,
    _context: dict[str, Any] | None = None,
) -> str:
    """
    Execute code and return std outputs and std error.

    Args:
        code (str): Code to execute.
        time_out (float | str): time out, in seconds. Defaults to 60.
        _context (dict, optional): Runtime context containing workspace settings.

    Returns:
        str: std output and std error
    """
    require_unsafe_code_execution("execute_code")

    if not isinstance(code, str):
        return "Setup error: code must be a string"
    if not code.strip():
        return "Setup error: code cannot be empty"

    if isinstance(time_out, bool) or not isinstance(time_out, (int, float, str)):
        return "Setup error: time_out must be a positive number"
    try:
        if isinstance(time_out, str):
            stripped_timeout = time_out.strip()
            if not stripped_timeout:
                return "Setup error: time_out cannot be empty"
            timeout_seconds = float(stripped_timeout)
        else:
            timeout_seconds = float(time_out)
        if not math.isfinite(timeout_seconds):
            return "Setup error: time_out must be a positive number"
        if timeout_seconds <= 0:
            return "Setup error: time_out must be positive"
    except (ValueError, TypeError, OverflowError):
        return "Setup error: time_out must be a positive number"

    def __get_workspace() -> Path:
        env_dir = os.getenv("TEMP_CODE_DIR")
        if env_dir:
            return Path(env_dir).resolve()
        if _context and _context.get("python_workspace_root"):
            return (Path(_context["python_workspace_root"]) / "temp").resolve()
        return Path("temp").resolve()

    def __write_script_file(_code: str, _workspace: Path) -> Path:
        _workspace.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid.uuid4()}.py"
        code_path = _workspace / filename
        code_content = _code if _code.endswith("\n") else _code + "\n"
        code_path.write_text(code_content, encoding="utf-8")
        return code_path

    def __default_interpreter() -> str:
        return sys.executable or "python3"

    script_path = None
    stdout = ""
    stderr = ""

    try:
        workspace = __get_workspace()
        script_path = __write_script_file(code, workspace)

        cmd = [__default_interpreter(), str(script_path.resolve())]

        try:
            completed = subprocess.run(
                cmd,
                cwd=str(workspace),
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
            stdout = completed.stdout.decode("utf-8", errors="replace")
            stderr = completed.stderr.decode("utf-8", errors="replace")
        except subprocess.TimeoutExpired as e:
            stdout = e.stdout.decode("utf-8", errors="replace") if e.stdout else ""
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
            timeout_display = (
                int(timeout_seconds)
                if timeout_seconds.is_integer()
                else timeout_seconds
            )
            stderr += f"\nError: Execution timed out after {timeout_display} seconds."
        except (subprocess.SubprocessError, OSError) as e:
            stderr = f"Execution error: {e!s}"

    except (OSError, ValueError) as e:
        stderr = f"Setup error: {e!s}"
    finally:
        if script_path and script_path.exists():
            with contextlib.suppress(OSError):
                script_path.unlink()

    return stdout + stderr
