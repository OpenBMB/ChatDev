"""S-GAR wrapper — git tags via the real `git` CLI (https://git-scm.com, GPLv2).
Lists tags of the repository at <repo_path> with their target commits."""
from _sgar_cli import run_cli, first_arg

r = first_arg("Usage: python git_tags_inspector.py <repo_path>")
run_cli("git", ["git", "-C", r, "tag", "-l",
                "--format=%(refname:short)\t%(objectname:short)\t%(creatordate:iso)"],
        input_path=r, ok_returncodes=(0,))
