import sys
from _mcplib import a
from _mcp_mutation import run_mutation

sys.exit(run_mutation("mcp-server-filesystem", ["/app"], "edit_file",
                     {"path": a(1), "edits": [{"oldText": a(2), "newText": a(3)}]}))
