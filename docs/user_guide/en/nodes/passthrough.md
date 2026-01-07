# Passthrough Node

The Passthrough node is the simplest node type. It performs no operations and passes received messages to downstream nodes. By default, it only passes the **last message**. It is primarily used for graph structure "wire management" optimization and context control.

## Configuration

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `only_last_message` | bool | No | `true` | Whether to pass only the last message. Set to `false` to pass all messages. |

### Basic Configuration

```yaml
config: {}  # Uses default configuration, only passes the last message
```

### Pass All Messages

```yaml
config:
  only_last_message: false  # Pass all received messages
```

## Core Concepts

### Pass-through Behavior

- Receives all messages passed from upstream
- **By default, only passes the last message** (`only_last_message: true`)
- When `only_last_message: false`, passes all messages
- Does not perform any content processing or transformation

### Graph Structure Optimization

The core value of the Passthrough node is not in data processing, but in **graph structure optimization** ("wire management"):
- Makes complex edge connections clearer
- Centrally manages outgoing edge configurations (such as `keep_message`)
- Serves as a logical dividing point, improving workflow readability

## Key Uses

### 1. As an Entry Node to Preserve Initial Context

Using Passthrough as the workflow entry node, combined with the `keep_message: true` edge configuration, ensures that the user's initial task is always preserved in the context and won't be overwritten by subsequent node outputs:

```yaml
nodes:
  - id: Task Keeper
    type: passthrough
    config: {}

  - id: Worker A
    type: agent
    config:
      provider: openai
      name: gpt-4o

  - id: Worker B
    type: agent
    config:
      provider: openai
      name: gpt-4o

edges:
  # Distribute tasks from entry, preserving original message
  - from: Task Keeper
    to: Worker A
    keep_message: true  # Preserve initial task context

  - from: Task Keeper
    to: Worker B
    keep_message: true

start: [Task Keeper]
```

**Effect**: Both Worker A and Worker B can see the user's original input, not just the output from the previous node.

### 2. Filtering Redundant Output in Loops

In workflows containing loops, nodes within the loop may produce a large amount of intermediate output. Passing all outputs to subsequent nodes would cause context bloat. Using a Passthrough node allows you to **pass only the final result of the loop**:

```yaml
nodes:
  - id: Iterative Improver
    type: agent
    config:
      provider: openai
      name: gpt-4o
      role: Continuously improve output based on feedback

  - id: Evaluator
    type: agent
    config:
      provider: openai
      name: gpt-4o
      role: |
        Evaluate output quality, reply GOOD or provide improvement suggestions

  - id: Result Filter
    type: passthrough
    config: {}

  - id: Final Processor
    type: agent
    config:
      provider: openai
      name: gpt-4o
      role: Post-process the final result

edges:
  - from: Iterative Improver
    to: Evaluator
  
  # Loop: Return to improvement node when evaluation fails
  - from: Evaluator
    to: Iterative Improver
    condition:
      type: keyword
      config:
        none: [GOOD]
  
  # Loop ends: Filter through Passthrough, only pass the last message
  - from: Evaluator
    to: Result Filter
    condition:
      type: keyword
      config:
        any: [GOOD]
  
  - from: Result Filter
    to: Final Processor

start: [Iterative Improver]
end: [Final Processor]
```

**Effect**: Regardless of how many loop iterations occur, `Final Processor` will only receive the last output from `Evaluator` (the one indicating quality passed), not all intermediate results.

## Other Uses

- **Placeholder**: Reserve node positions during design phase
- **Conditional branching**: Implement routing logic with conditional edges
- **Debugging observation point**: Insert nodes for easy observation in the workflow

## Examples

### Basic Usage

```yaml
nodes:
  - id: Router
    type: passthrough
    config: {}
```

### Conditional Routing

```yaml
nodes:
  - id: Classifier
    type: agent
    config:
      provider: openai
      name: gpt-4o
      role: |
        Classify input content, reply TECHNICAL or BUSINESS

  - id: Router
    type: passthrough
    config: {}

  - id: Tech Handler
    type: agent
    config:
      provider: openai
      name: gpt-4o

  - id: Biz Handler
    type: agent
    config:
      provider: openai
      name: gpt-4o

edges:
  - from: Classifier
    to: Router
  - from: Router
    to: Tech Handler
    condition:
      type: keyword
      config:
        any: [TECHNICAL]
  - from: Router
    to: Biz Handler
    condition:
      type: keyword
      config:
        any: [BUSINESS]
```

## Best Practices

- Use meaningful node IDs that describe their topological role (e.g., `Task Keeper`, `Result Filter`)
- When used as an entry node, configure outgoing edges with `keep_message: true` to preserve context
- Use after loops to filter out redundant intermediate output
