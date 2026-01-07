# Human Node

The Human node is used to introduce human interaction during workflow execution, allowing users to view the current state and provide input through the Web UI. This node blocks workflow execution until the user submits a response.

## Configuration

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `description` | text | No | - | Task description displayed to the user, explaining the operation that requires human completion |

## Core Concepts

### Blocking Wait Mechanism

When the workflow reaches a Human node:
1. The workflow pauses, waiting for human input
2. The Web UI displays the current context and task description
3. The user enters a response in the interface
4. The workflow continues execution, passing the user input to downstream nodes

### Web UI Interaction

- Human nodes are presented as a conversation in the Launch interface
- Users can view previous execution history
- Supports attachment uploads (e.g., files, images)

## When to Use

- **Review and confirmation**: Have humans review LLM output before continuing
- **Modification suggestions**: Collect user suggestions for modifying generated content
- **Critical decisions**: Points where human judgment is needed to continue
- **Data supplementation**: When additional information from the user is needed
- **Quality control**: Introduce human quality checks at critical nodes

## Examples

### Basic Configuration

```yaml
nodes:
  - id: Human Reviewer
    type: human
    config:
      description: Please review the above content. If satisfied, enter ACCEPT; otherwise, enter your modification suggestions.
```

### Human-Machine Collaboration Loop

```yaml
nodes:
  - id: Article Writer
    type: agent
    config:
      provider: openai
      name: gpt-4o
      api_key: ${API_KEY}
      role: You are a professional writer who writes articles based on user requirements.

  - id: Human Reviewer
    type: human
    config:
      description: |
        Please review the article:
        - If satisfied with the result, enter ACCEPT to end the process
        - Otherwise, enter modification suggestions to continue iterating

edges:
  - from: Article Writer
    to: Human Reviewer
  - from: Human Reviewer
    to: Article Writer
    condition:
      type: keyword
      config:
        none: [ACCEPT]
        case_sensitive: false
```

### Multi-Stage Review

```yaml
nodes:
  - id: Draft Generator
    type: agent
    config:
      provider: openai
      name: gpt-4o

  - id: Content Review
    type: human
    config:
      description: Please review content accuracy. Enter APPROVED or modification suggestions.

  - id: Final Reviewer
    type: human
    config:
      description: Final confirmation. Enter PUBLISH to publish or REJECT to reject.

edges:
  - from: Draft Generator
    to: Content Review
  - from: Content Review
    to: Final Reviewer
    condition:
      type: keyword
      config:
        any: [APPROVED]
```

## Best Practices

- Clearly explain expected operations and keywords in the `description`
- Use conditional edges with keywords to implement flow control
- Consider adding timeout mechanisms to avoid infinite workflow waiting
