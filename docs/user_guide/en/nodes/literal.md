# Literal Node

The Literal node is used to output fixed text content. When the node is triggered, it ignores all inputs and directly outputs a predefined message.

## Configuration

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `content` | text | Yes | - | Fixed text content to output, cannot be empty |
| `role` | string | No | `user` | Message role: `user` or `assistant` |

## Core Concepts

### Fixed Output

Characteristics of the Literal node:
- **Ignores input**: Regardless of what upstream content is passed in, it does not affect the output
- **Fixed content**: Outputs the same `content` every time it executes
- **Role marking**: Output message carries the specified role identifier

### Message Role

- `user`: Indicates this is a message sent by the user
- `assistant`: Indicates this is a message sent by the assistant (AI)

The role setting affects how downstream nodes process the message.

## When to Use

- **Fixed prompt injection**: Inject fixed instructions or context into the workflow
- **Testing and debugging**: Use fixed input to test downstream nodes
- **Default responses**: Return fixed messages under specific conditions
- **Process initialization**: Serve as the starting point of a workflow to provide initial content

## Examples

### Basic Usage

```yaml
nodes:
  - id: Welcome Message
    type: literal
    config:
      content: |
        Welcome to the intelligent assistant! Please describe your needs.
      role: assistant
```

### Injecting Fixed Context

```yaml
nodes:
  - id: Context Injector
    type: literal
    config:
      content: |
        Please note the following rules:
        1. Answers must be concise and clear
        2. Reply in English
        3. If uncertain, please state so
      role: user

  - id: Assistant
    type: agent
    config:
      provider: openai
      name: gpt-4o

edges:
  - from: Context Injector
    to: Assistant
```

### Fixed Responses in Conditional Branches

```yaml
nodes:
  - id: Classifier
    type: agent
    config:
      provider: openai
      name: gpt-4o
      role: Determine user intent, reply with KNOWN or UNKNOWN

  - id: Known Response
    type: literal
    config:
      content: I can help you complete this task.
      role: assistant

  - id: Unknown Response
    type: literal
    config:
      content: Sorry, I cannot understand your request. Please describe it in a different way.
      role: assistant

edges:
  - from: Classifier
    to: Known Response
    condition:
      type: keyword
      config:
        any: [KNOWN]
  - from: Classifier
    to: Unknown Response
    condition:
      type: keyword
      config:
        any: [UNKNOWN]
```

### Testing Purposes

```yaml
nodes:
  - id: Test Input
    type: literal
    config:
      content: |
        This is a test text for verifying downstream processing logic.
        Contains multiple lines.
      role: user

  - id: Processor
    type: python
    config:
      timeout_seconds: 30

edges:
  - from: Test Input
    to: Processor

start: [Test Input]
```

## Notes

- The `content` field cannot be an empty string
- Use YAML multi-line string syntax `|` for writing long text
- Choose the correct `role` to ensure downstream nodes process the message correctly
