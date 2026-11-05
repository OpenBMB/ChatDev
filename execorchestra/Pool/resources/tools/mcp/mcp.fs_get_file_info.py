from _mcplib import run, a

run("mcp.fs_get_file_info", "mcp-server-filesystem", ["/app"], "get_file_info", {"path":a(1)})
