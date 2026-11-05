"""S-GAR wrapper — Vulture dead-code finder (https://github.com/jendrikseipp/vulture, MIT)."""
import sys
import os
import subprocess
from _sgar_cli import emit, first_arg

f = first_arg("Usage: python python_dead_code_scanner.py <file_or_dir>")
if not os.path.exists(f):
    emit({"status": "error", "message": f"{f} not found"})
    sys.exit(2)
res = subprocess.run(["vulture", f], capture_output=True, text=True,
                     encoding="utf-8", errors="replace", timeout=120)
findings = [ln for ln in res.stdout.splitlines() if ln.strip()]
emit({"status": "success", "tool": "vulture", "target": f,
      "exit_code": res.returncode, "dead_code_count": len(findings),
      "findings": findings, "stderr": res.stderr or None})
