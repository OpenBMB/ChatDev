"""S-GAR tool — git blame authorship analysis via the real `git` CLI (git-scm, GPLv2).
Runs `git blame --line-porcelain <file>` and aggregates line counts per author."""
import sys
import os
import subprocess
import collections
from _sgar_cli import emit, first_arg

f = first_arg("Usage: python git_blame_analyzer.py <file_path>")
if not os.path.exists(f):
    emit({"status": "error", "message": f"{f} not found"})
    sys.exit(2)
repo = os.path.dirname(os.path.abspath(f)) or "."
res = subprocess.run(["git", "-C", repo, "blame", "--line-porcelain", os.path.abspath(f)],
                     capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
if res.returncode != 0:
    emit({"status": "error", "tool": "git", "message": res.stderr.strip() or "git blame failed"})
    sys.exit(1)
authors = collections.Counter()
total = 0
for line in res.stdout.splitlines():
    if line.startswith("author "):
        authors[line[len("author "):]] += 1
        total += 1
emit({"status": "success", "tool": "git", "file": f, "total_lines": total,
      "lines_by_author": dict(authors.most_common())})
