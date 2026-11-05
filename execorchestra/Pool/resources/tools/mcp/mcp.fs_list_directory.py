from _mcplib import run, a

run("mcp.fs_list_directory", "mcp-server-filesystem", ["/app"], "list_directory", {"path":a(1)})
