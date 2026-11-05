"""S-GAR wrapper — Pyflakes static analyzer (https://github.com/PyCQA/pyflakes, MIT).
Runs the recognized pyflakes checker over a Python file."""
import sys
import os
import subprocess
from _sgar_cli import emit, first_arg

f = first_arg("Usage: python python_static_analyzer.py <file_path>")
if not os.path.exists(f):
    emit({"status": "error", "message": f"{f} not found"})
    sys.exit(2)
res = subprocess.run([sys.executable, "-m", "pyflakes", f],
                     capture_output=True, text=True, encoding="utf-8",
                     errors="replace", timeout=120)
issues = [ln for ln in (res.stdout + res.stderr).splitlines() if ln.strip()]
emit({"status": "success", "tool": "pyflakes", "target": f,
      "exit_code": res.returncode, "issue_count": len(issues), "issues": issues})
