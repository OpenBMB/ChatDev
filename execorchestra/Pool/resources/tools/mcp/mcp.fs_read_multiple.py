from _mcplib import run, a

run("mcp.fs_read_multiple", "mcp-server-filesystem", ["/app"], "read_multiple_files", {"paths":[x for x in a(1,"").split(",") if x]})
