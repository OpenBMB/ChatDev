def run_python_script(script: str, timeout_seconds: int = 60) -> dict:
    """
    Run a short Python script and return a structured result with stdout, stderr, and exit code.

    This tool is intended for agent workflows that need a reliable Python scratchpad for
    calculations, parsing, formatting, or quick validation.
    """
    import os
    import subprocess
    import sys
    import uuid
    from pathlib import Path

    workspace = Path(os.getenv("TEMP_CODE_DIR", "temp")).resolve()
    workspace.mkdir(exist_ok=True)

    script_path = workspace / f"{uuid.uuid4()}.py"
    payload = script if script.endswith("\n") else script + "\n"
    script_path.write_text(payload, encoding="utf-8")

    try:
        completed = subprocess.run(
            [sys.executable or "python3", str(script_path.resolve())],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        return {
            "ok": completed.returncode == 0,
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "exit_code": None,
            "stdout": exc.stdout or "",
            "stderr": (exc.stderr or "") + f"\nError: Execution timed out after {timeout_seconds} seconds.",
        }
    except Exception as exc:
        return {
            "ok": False,
            "exit_code": None,
            "stdout": "",
            "stderr": f"Execution error: {exc}",
        }
    finally:
        try:
            script_path.unlink(missing_ok=True)
        except Exception:
            pass
