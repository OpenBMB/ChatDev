from _mcplib import run, a
repo=a(1,"/app"); args={"repo_path":repo}
if a(2): args["max_count"]=int(a(2))
run("mcp.git_log","python",["-m","mcp_server_git","--repository",repo],"git_log",args)
