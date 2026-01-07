# Agent Node

The Agent node is the most fundamental node type in the DevAll platform, used to invoke Large Language Models (LLMs) for text generation, conversation, reasoning, and other tasks. It supports multiple model providers (OpenAI, Gemini, etc.) and can be configured with advanced features like tool calling, chain-of-thought, and memory.

## Configuration

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `provider` | string | Yes | `openai` | Model provider name, e.g., `openai`, `gemini` |
| `name` | string | Yes | - | Model name, e.g., `gpt-4o`, `gemini-2.0-flash-001` |
| `role` | text | No | - | System prompt |
| `base_url` | string | No | Provider default | API endpoint URL, supports `${VAR}` placeholders |
| `api_key` | string | No | - | API key, recommend using environment variable `${API_KEY}` |
| `params` | dict | No | `{}` | Model call parameters (temperature, top_p, etc.) |
| `tooling` | object | No | - | Tool calling configuration, see [Tooling Module](../modules/tooling/README.md) |
| `thinking` | object | No | - | Chain-of-thought configuration, e.g., chain-of-thought, reflection |
| `memories` | list | No | `[]` | Memory binding configuration, see [Memory Module](../modules/memory.md) |
| `retry` | object | No | - | Automatic retry strategy configuration |

### Retry Strategy Configuration (retry)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | `true` | Whether to enable automatic retry |
| `max_attempts` | int | `5` | Maximum number of attempts (including first attempt) |
| `min_wait_seconds` | float | `1.0` | Minimum backoff wait time |
| `max_wait_seconds` | float | `6.0` | Maximum backoff wait time |
| `retry_on_status_codes` | list[int] | `[408,409,425,429,500,502,503,504]` | HTTP status codes that trigger retry |

## When to Use

- **Text generation**: Writing, translation, summarization, Q&A, etc.
- **Intelligent conversation**: Multi-turn dialogue, customer service bots
- **Tool calling**: Enable the model to call external APIs or execute functions
- **Complex reasoning**: Use with thinking configuration for deep thought
- **Knowledge retrieval**: Use with memories to implement RAG patterns

## Examples

### Basic Configuration

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
        You are a professional technical documentation writer. Please answer questions in clear and concise language.
      params:
        temperature: 0.7
        max_tokens: 2000
```

### Configuring Tool Calling

```yaml
nodes:
  - id: Assistant
    type: agent
    config:
      provider: openai
      name: gpt-4o
      api_key: ${API_KEY}
      tooling:
        type: function  # Tool type: function, mcp_remote, mcp_local
        config:
          tools:  # List of function tools from functions/function_calling/ directory
            - name: describe_available_files
            - name: load_file
          timeout: 20  # Optional: execution timeout (seconds)
```

### Configuring MCP Tools (Remote HTTP)

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
          server: http://localhost:8080/mcp  # MCP server endpoint
          headers:  # Optional: custom request headers
            Authorization: Bearer ${MCP_TOKEN}
          timeout: 30  # Optional: request timeout (seconds)
```

### Configuring MCP Tools (Local stdio)

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
          command: uvx  # Launch command
          args: ["mcp-server-sqlite", "--db-path", "data.db"]
          cwd: ${WORKSPACE}  # Optional, usually not needed
          env:  # Optional, usually not needed
            DEBUG: "true"
          startup_timeout: 10  # Optional: startup timeout (seconds)
```

### Gemini Multimodal Configuration

```yaml
nodes:
  - id: Vision Agent
    type: agent
    config:
      provider: gemini
      base_url: https://generativelanguage.googleapis.com
      api_key: ${GEMINI_API_KEY}
      name: gemini-2.5-flash-image
      role: You need to generate corresponding image content based on user input.
```

### Configuring Retry Strategy

```yaml
nodes:
  - id: Robust Agent
    type: agent
    config:
      provider: openai
      name: gpt-4o
      api_key: ${API_KEY}
      retry:  # Retry is enabled by default, you can customize it
        enabled: true
        max_attempts: 3
        min_wait_seconds: 2.0
        max_wait_seconds: 10.0
```

## Related Documentation

- [Tooling Module Configuration](../modules/tooling/README.md)
- [Memory Module Configuration](../modules/memory.md)
- [Workflow Authoring Guide](../workflow_authoring.md)
