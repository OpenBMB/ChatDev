"""CCS Security Guard for ChatDev code execution.

Integrates CCS runtime verification into ChatDev's execute_code() function,
protecting against RCE, SSRF, and credential leakage in AI-generated code.

Usage:
    from examples.ccs_security.ccs_guard import safe_execute_code
    result = safe_execute_code("print('hello world')")
"""
import logging
import subprocess
import os
import sys
import uuid
from pathlib import Path

try:
    from ccs_verifier import Verifier, Command
    from ccs_verifier.builtin_rules import RCERule, SSRFRule, CredentialLeakRule
    CCS_AVAILABLE = True
except ImportError:
    CCS_AVAILABLE = False

logger = logging.getLogger(__name__)

_VERIFIER = None

def _get_verifier():
    """Lazy-initialize CCS verifier."""
    global _VERIFIER
    if not CCS_AVAILABLE:
        return None
    if _VERIFIER is None:
        _VERIFIER = Verifier(rules=[RCERule(), SSRFRule(), CredentialLeakRule()])
    return _VERIFIER


def safe_execute_code(code: str, time_out: int = 60, agent_id: str = "chatdev-agent") -> str:
    """CCS-verified code execution for ChatDev.

    Verifies AI-generated code through CCS before execution.
    Blocks RCE patterns, SSRF attempts, and credential access.

    Args:
        code: Python code to execute.
        time_out: Timeout in seconds.
        agent_id: Agent identifier for audit trail.

    Returns:
        stdout + stderr from execution, or CCS denial message.
    """
    verifier = _get_verifier()
    if verifier is not None:
        cmd = Command(
            agent_id=agent_id,
            tool="python_execute",
            params={"code": code},
        )
        result = verifier.verify(cmd)
        if result.verdict.value == "deny":
            reason = getattr(result, "reason", "policy violation") or "policy violation"
            logger.warning(f"[CCS] Code execution denied | reason={reason}")
            return f"[CCS] Code execution denied: {reason}"

    # Delegate to original ChatDev execute_code logic
    def _write_script(_code):
        _workspace = Path(os.getenv('TEMP_CODE_DIR', 'temp')).resolve()
        _workspace.mkdir(exist_ok=True)
        filename = f"{uuid.uuid4()}.py"
        code_path = _workspace / filename
        code_content = _code if _code.endswith("\n") else _code + "\n"
        code_path.write_text(code_content, encoding="utf-8")
        return code_path

    script_path = None
    stdout = ""
    stderr = ""
    try:
        script_path = _write_script(code)
        workspace = script_path.parent
        cmd = [sys.executable or "python3", str(script_path.resolve())]
        try:
            completed = subprocess.run(cmd, cwd=str(workspace), capture_output=True, timeout=time_out, check=False)
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
