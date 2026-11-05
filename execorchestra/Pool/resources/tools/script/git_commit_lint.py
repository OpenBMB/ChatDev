"""S-GAR wrapper — gitlint (https://jorisroovers.com/gitlint, MIT).
Lints a commit message file with the recognized gitlint tool."""
import sys
import os
import subprocess
from _sgar_cli import emit, first_arg

f = first_arg("Usage: python git_commit_lint.py <commit_msg_file>")
if not os.path.exists(f):
    emit({"status": "error", "message": f"{f} not found"})
    sys.exit(2)
res = subprocess.run(["gitlint", "--msg-filename", f],
                     capture_output=True, text=True, encoding="utf-8",
                     errors="replace", timeout=60)
violations = [ln for ln in res.stdout.splitlines() if ln.strip()]
emit({"status": "success", "tool": "gitlint", "target": f,
      "exit_code": res.returncode, "clean": res.returncode == 0,
      "violations": violations, "stderr": res.stderr or None})
