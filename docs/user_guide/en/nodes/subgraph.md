# Subgraph Node

The Subgraph node allows embedding another workflow graph into the current workflow, enabling process reuse and modular design. Subgraphs can come from external YAML files or be defined inline in the configuration.

## Configuration

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `type` | string | Yes | - | Subgraph source type: `file` or `config` |
| `config` | object | Yes | - | Contains different configurations depending on `type` |

### File Type Configuration

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `path` | string | Yes | Subgraph file path (relative to `yaml_instance/` or absolute path) |

### Config Type Configuration

Inline definition of the complete subgraph structure, containing the same fields as the top-level `graph`:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Subgraph identifier |
| `description` | string | No | Subgraph description |
| `log_level` | string | No | Log level (DEBUG/INFO) |
| `nodes` | list | Yes | Node list |
| `edges` | list | No | Edge list |
| `start` | list | No | Entry node list |
| `end` | list | No | Exit node list |
| `memory` | list | No | Memory definitions specific to the subgraph |

## Core Concepts

### Modular Reuse

Extract commonly used process fragments into independent YAML files that can be reused by multiple workflows:
- Example: Package an "article polishing" process as a subgraph
- Different main workflows can call this subgraph

### Variable Inheritance

Subgraphs inherit `vars` variable definitions from the parent graph, supporting cross-level variable passing.

### Execution Isolation

Subgraphs execute as independent units with their own:
- Node namespace
- Log level configuration
- Memory definitions (optional)

## When to Use

- **Process reuse**: Multiple workflows sharing the same sub-processes
- **Modular design**: Breaking complex processes into manageable smaller units
- **Team collaboration**: Different teams maintaining different subgraph modules

## Examples

### Referencing External File

```yaml
nodes:
  - id: Review Process
    type: subgraph
    config:
      type: file
      config:
        path: common/review_flow.yaml
```

### Inline Subgraph Definition

```yaml
nodes:
  - id: Translation Unit
    type: subgraph
    config:
      type: config
      config:
        id: translation_subgraph
        description: Multi-language translation subprocess
        nodes:
          - id: Translator
            type: agent
            config:
              provider: openai
              name: gpt-4o
              role: You are a professional translator who translates content to the target language.
          - id: Proofreader
            type: agent
            config:
              provider: openai
              name: gpt-4o
              role: You are a proofreading expert who checks and polishes translated content.
        edges:
          - from: Translator
            to: Proofreader
        start: [Translator]
        end: [Proofreader]
```

### Combining Multiple Subgraphs

```yaml
nodes:
  - id: Input Handler
    type: agent
    config:
      provider: openai
      name: gpt-4o

  - id: Analysis Module
    type: subgraph
    config:
      type: file
      config:
        path: modules/analysis.yaml

  - id: Report Module
    type: subgraph
    config:
      type: file
      config:
        path: modules/report_gen.yaml

edges:
  - from: Input Handler
    to: Analysis Module
  - from: Analysis Module
    to: Report Module
```

## Notes

- Subgraph file paths support relative paths (based on `yaml_instance/`) and absolute paths
- Avoid circular nesting (A references B, B references A)
- The subgraph's `start` and `end` nodes determine how data flows in and out, which decides how the subgraph processes messages from the parent graph and which node's final output is returned to the parent graph
