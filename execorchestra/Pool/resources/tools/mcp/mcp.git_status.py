from _mcplib import run, a

repo=a(1,"/app")
run("mcp.git_status", "python", ["-m","mcp_server_git","--repository",repo], "git_status", {"repo_path":a(1)})
