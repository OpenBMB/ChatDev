from _mcplib import run, a
thought = a(1, "Analyze the problem")
run("mcp.sequential_thinking", "mcp-server-sequential-thinking", [], "sequentialthinking",
    {"thought": thought, "thoughtNumber": 1, "totalThoughts": 1, "nextThoughtNeeded": False})
