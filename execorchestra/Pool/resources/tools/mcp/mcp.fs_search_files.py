from _mcplib import run, a

run("mcp.fs_search_files", "mcp-server-filesystem", ["/app"], "search_files", {"path":a(1), "pattern":a(2)})
