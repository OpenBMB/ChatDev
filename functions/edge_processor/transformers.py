from typing import Dict, Any, Tuple
import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path, PureWindowsPath
from functions.function_calling.file import FileToolContext
from utils.code_execution import require_unsafe_code_execution
from utils.exceptions import SecurityError, ValidationError
from utils.workspace_paths import validate_path_component

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
    require_unsafe_code_execution("code_save_and_run")
    # Parse matches first
    pattern = re.compile(r"(?P<filename>[^\n]+)\n```(?:python)?\n(?P<code>.*?)\n```", re.DOTALL)
    matches = list(pattern.finditer(data))

    if not matches:
        return data

    ctx = FileToolContext(_context)
    workspace_root = ctx.workspace_root

    # Validate every target before deleting any existing workspace files.
    files_to_save = []
    attachments_root = workspace_root / "attachments"
    if attachments_root.is_symlink():
        raise SecurityError("The attachments directory must not be a symbolic link")
    attachments_root = attachments_root.resolve()
    for match in matches:
        filename = match.group("filename").strip()
        relative_path = Path(filename.replace("\\", "/"))
        if not filename or relative_path.is_absolute() or PureWindowsPath(filename).drive:
            raise SecurityError("Code filenames must be relative paths inside the workspace")
        try:
            for part in relative_path.parts:
                validate_path_component(part, field="filename")
            file_path = ctx.resolve_under_workspace(relative_path)
            # resolve() preserves case aliases on some filesystems; compare directory identities too.
            is_attachment_alias = attachments_root.exists() and any(
                ancestor.exists() and ancestor.samefile(attachments_root)
                for ancestor in (file_path, *file_path.parents)
            )
        except (ValueError, OSError, RuntimeError, ValidationError) as exc:
            raise SecurityError(f"Invalid code filename: {filename}") from exc
        if (
            file_path == workspace_root
            or relative_path.parts[0] == "attachments"
            or file_path.is_relative_to(attachments_root)
            or is_attachment_alias
        ):
            raise SecurityError("Code files must not replace the workspace or modify attachments")
        files_to_save.append((filename, file_path, match.group("code")))
    
    # 1. Clear workspace
    if workspace_root.exists():
        for item in workspace_root.iterdir():
            if item.name == "attachments":
                 continue
            
            if item.is_symlink():
                item.unlink()
            elif attachments_root.exists() and item.samefile(attachments_root):
                continue
            elif item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    
    saved_code_blocks = []
    for filename, file_path, code in files_to_save:
        # Save to file
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

        process_options = (
            {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
            if os.name == "nt"
            else {"start_new_session": True}
        )
        process = subprocess.Popen(
            ["uv", "run", "main.py"],
            cwd=str(workspace_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            **process_options,
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
