"""S-GAR wrapper — git diff --stat via the real `git` CLI (git-scm, GPLv2).
Summarizes the working-tree diff of the repository at <repo_path> (default '.')."""
import sys
from _sgar_cli import run_cli

r = sys.argv[1] if len(sys.argv) > 1 else "."
run_cli("git", ["git", "-C", r, "diff", "--stat"], input_path=r, ok_returncodes=(0,))
