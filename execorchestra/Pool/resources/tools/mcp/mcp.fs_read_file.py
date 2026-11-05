"""Read UTF-8 text without silently replacing undecodable input bytes."""
import sys
from _mcplib import a, run

path = a(1)
try:
    with open(path, "r", encoding="utf-8", errors="strict") as source:
        while source.read(65536):
            pass
except UnicodeError:
    print("file_input_encoding_unsupported: expected UTF-8 text", file=sys.stderr)
    raise SystemExit(2)
except OSError:
    # Let the MCP server retain its normal path/permission failure contract.
    pass

run("mcp.fs_read_file", "mcp-server-filesystem", ["/app"], "read_text_file", {"path": path})
