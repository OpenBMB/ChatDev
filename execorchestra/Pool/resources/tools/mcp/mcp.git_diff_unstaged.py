from _mcplib import run, a

repo=a(1,"/app")
run("mcp.git_diff_unstaged", "python", ["-m","mcp_server_git","--repository",repo], "git_diff_unstaged", {"repo_path":a(1)})
