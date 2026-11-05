import sys
from _mcplib import a, workspace_root
from _mcp_mutation import run_mutation

repo = a(1, workspace_root())
sys.exit(run_mutation("python", ["-m", "mcp_server_git", "--repository", repo], "git_create_branch",
                     {"repo_path": repo, "branch_name": a(2)}))
