# MCP Tooling Guide

MCP tooling is split into two explicit modes: **Remote (HTTP)** and **Local (stdio)**. They map to `tooling.type: mcp_remote` and `tooling.type: mcp_local`. The legacy `type: mcp` schema is no longer supported.

## 1. Mode overview
| Mode | Tooling type | When to use | Key fields |
| --- | --- | --- | --- |
| Remote | `mcp_remote` | A hosted HTTP(S) MCP server (FastMCP, Claude Desktop Connector, custom gateways) | `server`, `headers`, `timeout` |
| Local | `mcp_local` | A local executable that speaks MCP over stdio (Blender MCP, CLI tools, etc.) | `command`, `args`, `cwd`, `env`, timeouts |

## 2. `McpRemoteConfig`
| Field | Description |
| --- | --- |
| `server` | Required. MCP HTTP(S) endpoint, e.g. `https://api.example.com/mcp`. |
| `headers` | Optional. Extra HTTP headers such as `Authorization`. |
| `timeout` | Optional per-request timeout (seconds). |

**YAML example**
```yaml
nodes:
  - id: remote_mcp
    type: agent
    config:
      tooling:
        type: mcp_remote
        config:
          server: https://mcp.mycompany.com/mcp
          headers:
            Authorization: Bearer ${MY_MCP_TOKEN}
          timeout: 15
```
DevAll connects to the URL for each list/call request and passes `headers`. If the server is unreachable, an error is raised immediately—there is no local fallback.

## 3. `McpLocalConfig` fields
`mcp_local` declares the process arguments directly under `config`:
- `command` / `args`: executable and arguments (e.g., `uvx blender-mcp`).
- `cwd`: optional working directory.
- `env` / `inherit_env`: environment overrides.
- `startup_timeout`: max seconds to wait for `wait_for_log`.
- `wait_for_log`: regex matched against stdout to mark readiness.

**YAML example**
```yaml
nodes:
  - id: local_mcp
    type: agent
    config:
      tooling:
        type: mcp_local
        config:
          command: uvx
          args:
            - blender-mcp
          cwd: ${REPO_ROOT}
          wait_for_log: "MCP ready"
          startup_timeout: 8
```
DevAll keeps the process alive and relays MCP frames over stdio.

## 4. FastMCP sample server
`mcp_example/mcp_server.py`:
```python
from fastmcp import FastMCP
import random

mcp = FastMCP("Company Simple MCP Server", debug=True)

@mcp.tool
def rand_num(a: int, b: int) -> int:
    return random.randint(a, b)

if __name__ == "__main__":
    mcp.run()
```
Launch:
```bash
uv run fastmcp run mcp_example/mcp_server.py --transport streamable-http --port 8010
```
- Remote mode: set `server` to `http://127.0.0.1:8010/mcp`.
- Local mode: run the script with `transport=stdio` and point `command` to that invocation.

## 5. Security & operations
- **Network exposure**: Remote mode should sit behind HTTPS + ACL/API keys. Local mode still has access to the host filesystem, so keep the script sandboxed.
- **Resource cleanup**: Local mode processes are terminated by DevAll; make sure they gracefully handle SIGTERM/SIGKILL.
- **Logs**: Emit a clear readiness line that matches `wait_for_log` to debug startup issues.
- **Auth**: Remote mode handles tokens via `headers`; Local mode can receive secrets via `env` (never commit them).
- **Multi-session**: If the MCP server is single-tenant, cap concurrency (e.g., `max_concurrency=1`) and share the same YAML config.

## 6. Debugging checklist
1. Remote: ping the HTTP endpoint via curl or `fastmcp client`. Local: run the binary manually and confirm the readiness log.
2. Start DevAll (optionally with `--reload`) and observe backend logs for tool discovery.
3. When calls fail, inspect the Web UI tool traces or the structured logs under `logs/`.
