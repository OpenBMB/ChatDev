"""S-GAR wrapper — git log via the real `git` CLI (https://git-scm.com, GPLv2).
Emits the recent commit history of <repo_path> as structured records.
Optional second arg = max number of commits (default 50)."""
import sys
from _sgar_cli import run_cli, first_arg

r = first_arg("Usage: python git_log_pretty_format.py <repo_path> [max_count]")
n = sys.argv[2] if len(sys.argv) > 2 and str(sys.argv[2]).isdigit() else "50"
run_cli("git", ["git", "-C", r, "log", f"-n{n}",
                "--pretty=format:%h\t%an\t%ad\t%s", "--date=iso"],
        input_path=r, ok_returncodes=(0,))
