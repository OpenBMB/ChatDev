from _mcplib import run, a
repo=a(1,"/app")
run("mcp.git_branch_list","python",["-m","mcp_server_git","--repository",repo],"git_branch",{"repo_path":repo,"branch_type":"local"})
