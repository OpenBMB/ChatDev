from _mcplib import run, a

repo=a(1,"/app")
run("mcp.git_show", "python", ["-m","mcp_server_git","--repository",repo], "git_show", {"repo_path":a(1), "revision":a(2)})
