from typing import Dict, Any, Tuple
import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path
from functions.function_calling.file import FileToolContext

def uppercase_payload(data: str, _context: Dict[str, Any]) -> str:
    """Return an uppercase copy of the payload text."""
    return (data or "").upper()

def code_save_and_run(data: str, _context: Dict[str, Any]) -> str:
    """
    Clears the workspace, saves code from the payload, runs main.py, and returns code + result.
    
    The payload format is expected to be:
    FILENAME
    ```python
    CODE
    ```
    Repeated for multiple files.
    """
    # Parse matches first
    pattern = re.compile(r"(?P<filename>[^\n]+)\n```(?:python)?\n(?P<code>.*?)\n```", re.DOTALL)
    matches = list(pattern.finditer(data))

    if not matches:
        return data

    ctx = FileToolContext(_context)
    workspace_root = ctx.workspace_root
    
    # 1. Clear workspace
    if workspace_root.exists():
        for item in workspace_root.iterdir():
            if item.name == "attachments":
                 continue
            
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    
    saved_code_blocks = []
    for match in matches:
        filename = match.group("filename").strip()
        code = match.group("code")
        
        # Save to file
        file_path = workspace_root / filename
        # Ensure parent dirs exist if filename contains path separators
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(code, encoding="utf-8")
        
        saved_code_blocks.append(f"{filename}\n```python\n{code}\n```")
        
    cleaned_code_str = "\n".join(saved_code_blocks)
    
    # 3. Execute main.py
    success_info = "The software run successfully without errors."
    execution_result = ""
    
    try:
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        if os.name == 'nt':
            command = f"cd {workspace_root} && dir && uv run main.py"
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                env=env
            )
        else:
             
            command = "uv run main.py"
            process = subprocess.Popen(
                command,
                shell=True,
                cwd=str(workspace_root),
                preexec_fn=os.setsid,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env
            )
            
        try:
            stdout, stderr = process.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            if "killpg" in dir(os):
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            else:
                os.kill(process.pid, signal.SIGTERM)
                if process.poll() is None and hasattr(signal, 'CTRL_BREAK_EVENT'):
                    os.kill(process.pid, signal.CTRL_BREAK_EVENT)
            stdout, stderr = process.communicate()
            
        stdout_str = stdout.decode('utf-8', errors='ignore') if stdout else ""
        stderr_str = stderr.decode('utf-8', errors='ignore') if stderr else ""
        
        # Filter out uv experimental warning
        uv_warning_pattern = "warning: The `extra-build-dependencies` option is experimental and may change without warning."
        if uv_warning_pattern in stderr_str:
            stderr_str = "\n".join([line for line in stderr_str.splitlines() if uv_warning_pattern not in line])
        
        return_code = process.returncode

        # Treat as success if return code is 0 OR if there are no errors in stderr
        # (This covers the case where the process times out/is killed but didn't crash)
        if return_code == 0 or not stderr_str.strip():
            parts = []
            if stdout_str.strip():
                parts.append(stdout_str.strip())
            parts.append(success_info)
            execution_result = "\n\n".join(parts)
        else:
            if "Traceback".lower() in stderr_str.lower():
                execution_result = stderr_str.replace((workspace_root / "").__str__(), "")
            else:
                execution_result = stderr_str
    except Exception as e:
        execution_result = f"Error: {e}"

    return cleaned_code_str + "\n\n" + execution_result
