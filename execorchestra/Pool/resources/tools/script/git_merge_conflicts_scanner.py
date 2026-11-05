"""S-GAR wrapper — merge-conflict scan via the real `git` CLI (https://git-scm.com, GPLv2).
Uses `git grep` to find unresolved conflict markers among tracked files in the
repository at <repo_path>."""
import sys
import os
import subprocess
from _sgar_cli import emit, first_arg

r = first_arg("Usage: python git_merge_conflicts_scanner.py <repo_path>")
if not os.path.exists(r):
    emit({"status": "error", "message": f"{r} not found"})
    sys.exit(2)
# git grep exits 0 if matches found, 1 if none. Conflict markers are 7 chars.
res = subprocess.run(
    ["git", "-C", r, "grep", "-nE", r"^(<<<<<<<|=======|>>>>>>>)"],
    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
)
lines = [ln for ln in res.stdout.splitlines() if ln.strip()]
files = sorted({ln.split(":", 1)[0] for ln in lines})
emit({"status": "success", "tool": "git", "target": r,
      "conflicted_files": files, "conflict_marker_count": len(lines),
      "markers": lines[:200]})
