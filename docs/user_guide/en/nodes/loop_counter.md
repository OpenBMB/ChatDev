# Loop Counter Node

The Loop Counter node is a loop control node used to limit the number of iterations of a loop in a workflow. Through a counting mechanism, it suppresses output before reaching the preset limit, and only releases the message to trigger outgoing edges when the limit is reached, thereby terminating the loop.

## Configuration

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `max_iterations` | int | Yes | `10` | Maximum number of loop iterations, must be ≥ 1 |
| `reset_on_emit` | bool | No | `true` | Whether to reset the counter after reaching the limit |
| `message` | text | No | - | Message content to send to downstream when limit is reached |

## Core Concepts

### How It Works

The Loop Counter node maintains an internal counter with the following behavior:

1. **Each time it is triggered**: Counter +1
2. **Counter < `max_iterations`**: **No output is produced**, outgoing edges are not triggered
3. **Counter = `max_iterations`**: Output message is produced, triggering outgoing edges

This "suppress-release" mechanism allows the Loop Counter to precisely control when a loop terminates.

### Topological Structure Requirements

The Loop Counter node has special placement requirements in the graph structure:

```
    ┌──────────────────────────────────────┐
    ▼                                      │
  Agent ──► Human ─────► Loop Counter ──┬──┘
    ▲         │                         │
    └─────────┘                         ▼
                                   End Node (outside loop)
```

> **Important**: Since Loop Counter **produces no output until the limit is reached**:
> - **Human must connect to both Agent and Loop Counter**: This way the "continue loop" edge is handled by Human → Agent, while Loop Counter only handles counting
> - **Loop Counter must connect to Agent (inside loop)**: So it's recognized as an in-loop node, avoiding premature loop termination
> - **Loop Counter must connect to End Node (outside loop)**: When the limit is reached, trigger the out-of-loop node to terminate the entire loop execution

### Counter State

- Counter state persists throughout the entire workflow execution
- When `reset_on_emit: true`, the counter resets to 0 after reaching the limit
- When `reset_on_emit: false`, the counter continues accumulating after reaching the limit, outputting on every subsequent trigger

## When to Use

- **Preventing infinite loops**: Set a safety limit for human-machine interaction loops
- **Iteration control**: Limit the maximum number of self-improvement iterations for an Agent
- **Timeout protection**: Serve as a "circuit breaker" for process execution

## Examples

### Basic Usage

```yaml
nodes:
  - id: Iteration Guard
    type: loop_counter
    config:
      max_iterations: 5
      reset_on_emit: true
      message: Maximum iteration count reached, process terminated.
```

### Human-Machine Interaction Loop Protection

This is the most typical use case for Loop Counter:

```yaml
graph:
  id: review_loop
  description: Review loop with iteration limit
  
  nodes:
    - id: Writer
      type: agent
      config:
        provider: openai
        name: gpt-4o
        role: Improve articles based on user feedback

    - id: Reviewer
      type: human
      config:
        description: |
          Review the article, enter ACCEPT to accept or provide modification suggestions.

    - id: Loop Guard
      type: loop_counter
      config:
        max_iterations: 3
        message: Maximum modification count (3 times) reached, process automatically ended.

    - id: Final Output
      type: passthrough
      config: {}

  edges:
    # Main loop: Writer -> Reviewer
    - from: Writer
      to: Reviewer
    
    # Condition 1: User enters ACCEPT -> End
    - from: Reviewer
      to: Final Output
      condition:
        type: keyword
        config:
          any: [ACCEPT]
    
    # Condition 2: User enters modification suggestions -> Trigger both Writer to continue loop AND Loop Guard to count
    - from: Reviewer
      to: Writer
      condition:
        type: keyword
        config:
          none: [ACCEPT]
    
    - from: Reviewer
      to: Loop Guard
      condition:
        type: keyword
        config:
          none: [ACCEPT]
    
    # Loop Guard connects to Writer (keeps it inside the loop)
    - from: Loop Guard
      to: Writer
    
    # When Loop Guard reaches limit: Trigger Final Output to end the process
    - from: Loop Guard
      to: Final Output

  start: [Writer]
  end: [Final Output]
```

**Execution Flow Explanation**:
1. User first enters modification suggestions → Triggers both Writer (continue loop) and Loop Guard (count 1, no output)
2. User enters modification suggestions again → Triggers both Writer (continue loop) and Loop Guard (count 2, no output)
3. User enters modification suggestions for the third time → Writer continues execution, Loop Guard count 3 reaches limit, outputs message triggering Final Output, terminating the loop
4. Or at any time user enters ACCEPT → Goes directly to Final Output to end

## Notes

- `max_iterations` must be a positive integer (≥ 1)
- Loop Counter **produces no output until the limit is reached**, outgoing edges will not trigger
- Ensure Loop Counter connects to both in-loop and out-of-loop nodes
- The `message` field is optional, default message is `"Loop limit reached (N)"`
