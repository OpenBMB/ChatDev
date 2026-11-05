import sys
from _mcplib import a
from _mcp_mutation import run_mutation

sys.exit(run_mutation("mcp-server-filesystem", ["/app"], "create_directory", {"path": a(1)}))
