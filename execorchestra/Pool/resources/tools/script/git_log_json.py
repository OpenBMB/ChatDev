"""S-GAR tool — git log as JSON via the real `git` CLI (git-scm, GPLv2).
argv: <repo_path> [count]  (defaults: '.', 20)."""
import sys
import os
import subprocess
from _sgar_cli import emit

repo = sys.argv[1] if len(sys.argv) > 1 else "."
count = sys.argv[2] if len(sys.argv) > 2 and str(sys.argv[2]).isdigit() else "20"
if not os.path.exists(repo):
    emit({"status": "error", "message": f"{repo} not found"})
    sys.exit(2)
fmt = "%H%x1f%an%x1f%ad%x1f%s"
res = subprocess.run(["git", "-C", repo, "log", "-n", count, f"--pretty=format:{fmt}",
                      "--date=iso"], capture_output=True, text=True,
                     encoding="utf-8", errors="replace", timeout=30)
if res.returncode != 0:
    emit({"status": "error", "tool": "git", "message": res.stderr.strip() or "git log failed"})
    sys.exit(1)
logs = []
for line in res.stdout.splitlines():
    if line:
        commit, author, date, subject = (line.split("\x1f", 3) + ["", "", "", ""])[:4]
        logs.append({"commit": commit, "author": author, "date": date, "subject": subject})
emit({"status": "success", "tool": "git", "repo": repo, "count": len(logs), "logs": logs})
