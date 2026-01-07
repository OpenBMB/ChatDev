# Agent 节点

Agent 节点是 DevAll 平台中最核心的节点类型，用于调用大语言模型 (LLM) 完成文本生成、对话、推理等任务。它支持多种模型提供商（OpenAI、Gemini 等），并可配置工具调用、思维链、记忆等高级功能。

## 配置项

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `provider` | string | 是 | `openai` | 模型提供商名称，如 `openai`、`gemini` |
| `name` | string | 是 | - | 模型名称，如 `gpt-4o`、`gemini-2.0-flash-001` |
| `role` | text | 否 | - | 系统提示词 (System Prompt) |
| `base_url` | string | 否 | 提供商默认 | API 端点 URL，支持 `${VAR}` 占位符 |
| `api_key` | string | 否 | - | API 密钥，建议使用环境变量 `${API_KEY}` |
| `params` | dict | 否 | `{}` | 模型调用参数（temperature、top_p 等） |
| `tooling` | object | 否 | - | 工具调用配置，详见 [Tooling 模块](../modules/tooling/README.md) |
| `thinking` | object | 否 | - | 思维链配置，如 chain-of-thought、reflection |
| `memories` | list | 否 | `[]` | 记忆绑定配置，详见 [Memory 模块](../modules/memory.md) |
| `retry` | object | 否 | - | 自动重试策略配置 |

### 重试策略配置 (retry)

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enabled` | bool | `true` | 是否启用自动重试 |
| `max_attempts` | int | `5` | 最大尝试次数（含首次） |
| `min_wait_seconds` | float | `1.0` | 最小退避等待时间 |
| `max_wait_seconds` | float | `6.0` | 最大退避等待时间 |
| `retry_on_status_codes` | list[int] | `[408,409,425,429,500,502,503,504]` | 触发重试的 HTTP 状态码 |

## 何时使用

- **文本生成**：写作、翻译、摘要、问答等
- **智能对话**：多轮对话、客服机器人
- **工具调用**：让模型调用外部 API 或执行函数
- **复杂推理**：配合 thinking 配置进行深度思考
- **知识检索**：配合 memories 实现 RAG 模式

## 示例

### 基础配置

```yaml
nodes:
  - id: Writer
    type: agent
    config:
      provider: openai
      base_url: ${BASE_URL}
      api_key: ${API_KEY}
      name: gpt-4o
      role: |
        你是一位专业的技术文档撰写者，请用清晰简洁的语言回答问题。
      params:
        temperature: 0.7
        max_tokens: 2000
```

### 配置工具调用

```yaml
nodes:
  - id: Assistant
    type: agent
    config:
      provider: openai
      name: gpt-4o
      api_key: ${API_KEY}
      tooling:
        type: function  # 工具类型：function, mcp_remote, mcp_local
        config:
          tools:  # 函数工具列表，来自 functions/function_calling/ 目录
            - name: describe_available_files
            - name: load_file
          timeout: 20  # 可选：执行超时（秒）
```

### 配置 MCP 工具（Remote HTTP）

```yaml
nodes:
  - id: MCP Agent
    type: agent
    config:
      provider: openai
      name: gpt-4o
      api_key: ${API_KEY}
      tooling:
        type: mcp_remote
        config:
          server: http://localhost:8080/mcp  # MCP 服务器端点
          headers:  # 可选：自定义请求头
            Authorization: Bearer ${MCP_TOKEN}
          timeout: 30  # 可选：请求超时（秒）
```

### 配置 MCP 工具（Local stdio）

```yaml
nodes:
  - id: Local MCP Agent
    type: agent
    config:
      provider: openai
      name: gpt-4o
      api_key: ${API_KEY}
      tooling:
        type: mcp_local
        config:
          command: uvx  # 启动命令
          args: ["mcp-server-sqlite", "--db-path", "data.db"]
          cwd: ${WORKSPACE}  # 可选，一般不需要配置
          env:  # 可选，一般不需要配置
            DEBUG: "true"
          startup_timeout: 10  # 可选：启动超时（秒）
```

### Gemini 多模态配置

```yaml
nodes:
  - id: Vision Agent
    type: agent
    config:
      provider: gemini
      base_url: https://generativelanguage.googleapis.com
      api_key: ${GEMINI_API_KEY}
      name: gemini-2.5-flash-image
      role: 你需要根据用户的输入，生成相应的图像内容。
```

### 配置重试策略

```yaml
nodes:
  - id: Robust Agent
    type: agent
    config:
      provider: openai
      name: gpt-4o
      api_key: ${API_KEY}
      retry:  # retry 默认启用，可以自己配置
        enabled: true
        max_attempts: 3
        min_wait_seconds: 2.0
        max_wait_seconds: 10.0
```

## 相关文档

- [Tooling 模块配置](../modules/tooling/README.md)
- [Memory 模块配置](../modules/memory.md)
- [工作流编排指南](../workflow_authoring.md)
