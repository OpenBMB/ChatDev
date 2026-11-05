import sys
from _mcplib import a, workspace_root
from _mcp_mutation import run_mutation

repo = a(1, workspace_root())
sys.exit(run_mutation("python", ["-m", "mcp_server_git", "--repository", repo], "git_commit",
                     {"repo_path": repo, "message": a(2)}))
