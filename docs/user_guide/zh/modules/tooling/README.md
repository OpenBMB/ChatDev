# Tooling 模块总览

DevAll 目前支持两类工具绑定到 Agent 节点：
1. **Function Tooling**：调用仓库内的 Python 函数（`functions/function_calling/`），通过 JSON Schema 自动生成工具签名。
2. **MCP Tooling**：连接符合 Model Context Protocol 的外部服务，可直接复用 FastMCP、Claude Desktop 等工具生态。

所有 Tooling 配置都挂载在 `AgentConfig.tooling`：
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

## 1. 生命周期
1. 解析阶段：`ToolingConfig` 根据 `type` 选择 `FunctionToolConfig`、`McpRemoteConfig` 或 `McpLocalConfig`，字段定义来自 `entity/configs/tooling.py`。
2. 运行阶段：Agent 节点根据响应启用工具调用；当 LLM 选择某工具时，执行器会将 `_context`（附件仓库、workspace 路径等）注入函数或通过 MCP 发送请求。
3. 结束阶段：工具输出写入 Agent 消息流，必要时注册为附件（如 `load_file`）。

## 2. 文档结构
- [function.md](function.md)：Function Tooling 配置、上下文注入、最佳实践。
- [function_catalog.md](function_catalog.md)：仓库内置函数清单与示例。
- [mcp.md](mcp.md)：MCP 工具配置、自动启动、FastMCP 示例、安全提示。

## 3. 快速对比
| 维度 | Function | MCP |
| --- | --- | --- |
| 部署 | 同进程调用本地 Python 函数 | Remote：直连 HTTP 服务；Local：拉起本地进程并通过 stdio 连接 |
| Schemas | 自动从类型注解 + `ParamMeta` 生成 | 由 MCP JSON Schema 提供 |
| 上下文 | 自动注入 `_context`（附件/workspace） | 取决于 MCP 服务器实现 |
| 典型用途 | 文件操作、本地脚本、内部 API | 第三方工具合集、浏览器、数据库代理 |

## 4. 安全提示
- Function Tooling 运行在后端进程中，应确保函数遵循最小权限原则；不要在函数中执行不受控的命令。
- MCP Tooling 分为 **Remote (HTTP)** 与 **Local (stdio)**。Remote 仅配置已有服务器地址；Local 会拉起进程，请使用受控脚本并限制环境变量，必要时通过 `wait_for_log` 等字段判断进程是否就绪。
- 若工具可能修改附件或 workspace，请结合 [附件指南](../../attachments.md) 了解生命周期与清理策略。
