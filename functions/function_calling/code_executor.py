def execute_code(code: str, time_out: int = 60) -> str:
    """
    Execute code and return std outputs and std error.

    Args:
        code (str): Code to execute.
        time_out (int): time out, in second.

    Returns:
        str: std output and std error
    """
    import os
    import sys
    import subprocess
    import uuid
    from pathlib import Path

    def __write_script_file(_code: str):
        _workspace = Path(os.getenv('TEMP_CODE_DIR', 'temp'))
        _workspace.mkdir(exist_ok=True)
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
        script_path = __write_script_file(code)
        workspace = script_path.parent

        cmd = [__default_interpreter(), str(script_path)]

        try:
            completed = subprocess.run(
                cmd,
                cwd=str(workspace),
                capture_output=True,
                timeout=time_out,
                check=False
            )
            stdout = completed.stdout.decode('utf-8', errors="replace")
            stderr = completed.stderr.decode('utf-8', errors="replace")
        except subprocess.TimeoutExpired as e:
            stdout = e.stdout.decode('utf-8', errors="replace") if e.stdout else ""
            stderr = e.stderr.decode('utf-8', errors="replace") if e.stderr else ""
            stderr += f"\nError: Execution timed out after {time_out} seconds."
        except Exception as e:
            stderr = f"Execution error: {str(e)}"

    except Exception as e:
        stderr = f"Setup error: {str(e)}"
    finally:
        if script_path and script_path.exists():
            try:
                os.remove(script_path)
            except Exception:
                pass

    return stdout + stderr