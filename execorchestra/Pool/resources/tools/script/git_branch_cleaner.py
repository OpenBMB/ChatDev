"""S-GAR tool — merged-branch audit via the real `git` CLI (git-scm, GPLv2).
Read-only: lists branches already merged into HEAD (candidates for cleanup) for
the repository at <repo_path> (default '.'). Does not delete anything."""
import sys
import os
import subprocess
from _sgar_cli import emit

repo = sys.argv[1] if len(sys.argv) > 1 else "."
if not os.path.exists(repo):
    emit({"status": "error", "message": f"{repo} not found"})
    sys.exit(2)
res = subprocess.run(["git", "-C", repo, "branch", "-a", "--merged"],
                     capture_output=True, text=True, encoding="utf-8",
                     errors="replace", timeout=30)
if res.returncode != 0:
    emit({"status": "error", "tool": "git", "message": res.stderr.strip() or "git branch failed"})
    sys.exit(1)
branches = [b.strip().lstrip("* ").strip() for b in res.stdout.splitlines() if b.strip()]
emit({"status": "success", "tool": "git", "repo": repo,
      "merged_branch_count": len(branches), "merged_branches": branches})
