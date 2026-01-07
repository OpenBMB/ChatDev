from fastmcp import FastMCP
import random
from datetime import datetime
from typing import Dict, Optional

# Initialize MCP server
mcp = FastMCP(
    "Company Simple MCP Server",
    # api_route="/mcp/",
    debug=True
)


@mcp.tool
def rand_num(a: int, b: int) -> int:
    """Generate a random number between a and b."""
    num = random.randint(a, b)
    print(num)
    return num

if __name__ == "__main__":
    print("Starting simple MCP server...")
    print("Run with: uv run fastmcp run simple_server.py --transport 'streamable-http' --port 8001")
    # mcp.run(transport="streamable-http", host="127.0.0.1", port=8001)
    mcp.run()
