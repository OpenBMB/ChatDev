# Python Node

The Python node is used to execute Python scripts or inline code within workflows, implementing custom data processing, API calls, file operations, and other logic. Scripts are executed in the shared `code_workspace/` directory and can access workflow context data.

## Configuration

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `interpreter` | string | No | Current Python | Python interpreter path |
| `args` | list[str] | No | `[]` | Startup arguments appended to the interpreter |
| `env` | dict[str, str] | No | `{}` | Additional environment variables, overrides system defaults |
| `timeout_seconds` | int | No | `60` | Script execution timeout (seconds) |
| `encoding` | string | No | `utf-8` | Encoding for parsing stdout/stderr |

## Core Concepts

### Code Workspace

Python scripts are executed within the `code_workspace/` directory:
- Scripts can read and write files in this directory
- Multiple Python nodes share the same workspace
- The workspace persists for the duration of a single workflow execution

### Input/Output

- **Input**: Outputs from upstream nodes are passed as environment variables or standard input
- **Output**: The script's stdout output will be passed as a Message to downstream nodes

## When to Use

- **Data processing**: Parse JSON/XML, data transformation, formatting
- **API calls**: Call third-party services, fetch external data
- **File operations**: Read/write files, generate reports
- **Complex calculations**: Mathematical operations, algorithm implementations
- **Glue logic**: Custom logic connecting different nodes

## Examples

### Basic Configuration

```yaml
nodes:
  - id: Data Processor
    type: python
    config:
      timeout_seconds: 120
      env:
        key: value
```

### Specifying Interpreter and Arguments

```yaml
nodes:
  - id: Script Runner
    type: python
    config:
      interpreter: /usr/bin/python3.11
      timeout_seconds: 300
      encoding: utf-8
```

### Typical Workflow Example

```yaml
nodes:
  - id: LLM Generator
    type: agent
    config:
      provider: openai
      name: gpt-4o
      api_key: ${API_KEY}
      role: You need to generate executable Python code based on user input. The code should be wrapped in ```python ```.

  - id: Result Parser
    type: python
    config:
      timeout_seconds: 30

edges:
  - from: LLM Generator
    to: Result Parser
```

## Notes

- Ensure script files are placed in the `code_workspace/` directory
- Long-running scripts should have an appropriately increased `timeout_seconds`
- Use `env` to pass additional environment variables, accessible in scripts via `os.getenv`
