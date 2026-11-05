"""S-GAR wrapper — git submodule status via the real `git` CLI (https://git-scm.com, GPLv2).
Reports the submodule status of the repository at <repo_path>."""
from _sgar_cli import run_cli, first_arg

r = first_arg("Usage: python git_submodule_status.py <repo_path>")
run_cli("git", ["git", "-C", r, "submodule", "status", "--recursive"],
        input_path=r, ok_returncodes=(0,))
