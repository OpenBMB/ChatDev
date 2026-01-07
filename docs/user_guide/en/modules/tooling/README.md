# Tooling Module Overview

DevAll currently exposes two tool binding modes for agent nodes:
1. **Function Tooling** – call in-repo Python functions from `functions/function_calling/`, with JSON Schema auto-generated from type hints.
2. **MCP Tooling** – connect to external services that implement the Model Context Protocol, including FastMCP, Claude Desktop, or any MCP-compatible tool stack.

All tooling configs hang off `AgentConfig.tooling`:
```yaml
nodes:
  - id: solve
    type: agent
    config:
      provider: openai
      model: gpt-4o-mini
      prompt_template: solver
      tooling:
        type: function
        config:
          tools:
            - name: describe_available_files
            - name: load_file
          auto_load: true
          timeout: 20
```

## 1. Lifecycle
1. **Parse** – `ToolingConfig` selects `FunctionToolConfig`, `McpRemoteConfig`, or `McpLocalConfig` based on `type`. Field definitions live in `entity/configs/tooling.py`.
2. **Runtime** – When the LLM chooses a tool, the executor injects `_context` (attachment store, workspace paths, etc.) for Function tools or forwards the request through MCP.
3. **Completion** – Tool outputs are appended to the agent message stream and, when relevant, registered as attachments (e.g., `load_file`).

## 2. Documentation Map
- [function.md](function.md) – Function Tooling config, context injection, best practices.
- [function_catalog.md](function_catalog.md) – Built-in function list with usage notes.
- [mcp.md](mcp.md) – MCP Tooling config, auto-launch, FastMCP example, security guidance.

## 3. Quick Comparison
| Dimension | Function | MCP |
| --- | --- | --- |
| Deployment | In-process Python functions shipped with the backend. | Remote: call an HTTP MCP endpoint. Local: launch a process and talk over stdio. |
| Schemas | Derived from annotations + `ParamMeta`. | Provided by the MCP server's JSON Schema. |
| Context | `_context` provides attachments + workspace helpers automatically. | Depends on the MCP server implementation. |
| Typical use | File I/O, local scripts, internal APIs. | Third-party tool suites, browsers, database agents. |

## 4. Security Notes
- Function Tooling runs inside the backend process, so keep functions least-privileged and avoid executing arbitrary shell commands without validation.
- MCP Tooling now has explicit **remote (HTTP)** and **local (stdio)** modes. Remote only needs an existing server URL; Local launches your binary, so constrain the command/env vars and rely on `wait_for_log` + timeouts to detect readiness.
- Tools that mutate attachments or `code_workspace/` should respect the lifecycle described in the [Attachment guide](../../attachments.md) (Chinese for now) to avoid leaking artifacts.
