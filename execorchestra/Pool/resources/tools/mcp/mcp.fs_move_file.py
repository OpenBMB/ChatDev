import sys
from _mcplib import a
from _mcp_mutation import run_mutation

sys.exit(run_mutation("mcp-server-filesystem", ["/app"], "move_file",
                     {"source": a(1), "destination": a(2)}))
