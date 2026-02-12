# Loop Timer Node

The Loop Timer node is a loop control node used to limit the duration of a loop in a workflow. Through a time-tracking mechanism, it suppresses output before reaching the preset time limit, and only releases the message to trigger outgoing edges when the time limit is reached, thereby terminating the loop.

## Configuration

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `max_duration` | float | Yes | `60.0` | Maximum loop duration, must be > 0 |
| `duration_unit` | string | Yes | `"seconds"` | Time unit: "seconds", "minutes", or "hours" |
| `reset_on_emit` | bool | No | `true` | Whether to reset the timer after reaching the limit |
| `message` | text | No | - | Message content to send to downstream when time limit is reached |

## Core Concepts

### How It Works

The Loop Timer node maintains an internal timer with the following behavior:

1. **On first trigger**: Timer starts tracking elapsed time
2. **Elapsed time < `max_duration`**: **No output is produced**, outgoing edges are not triggered
3. **Elapsed time >= `max_duration`**: Output message is produced, triggering outgoing edges

This "suppress-release" mechanism allows the Loop Timer to precisely control when a loop terminates based on time rather than iteration count.

### Topological Structure Requirements

The Loop Timer node has special placement requirements in the graph structure:

```
    ┌──────────────────────────────────────┐
    ▼                                      │
  Agent ──► Human ─────► Loop Timer ──┬──┘
    ▲         │                        │
    └─────────┘                        ▼
                                  End Node (outside loop)
```

> **Important**: Since Loop Timer **produces no output until the time limit is reached**:
> - **Human must connect to both Agent and Loop Timer**: This way the "continue loop" edge is handled by Human → Agent, while Loop Timer only handles time tracking
> - **Loop Timer must connect to Agent (inside loop)**: So it's recognized as an in-loop node, avoiding premature loop termination
> - **Loop Timer must connect to End Node (outside loop)**: When the time limit is reached, trigger the out-of-loop node to terminate the entire loop execution

### Timer State

- Timer state persists throughout the entire workflow execution
- Timer starts on the first trigger to the Loop Timer node
- When `reset_on_emit: true`, the timer resets after reaching the limit
- When `reset_on_emit: false`, the timer continues running after reaching the limit, outputting on every subsequent trigger

## When to Use

- **Time-based constraints**: Enforce time limits for loops (e.g., "review must complete within 5 minutes")
- **Timeout protection**: Serve as a "circuit breaker" to prevent runaway processes
- **Variable iteration time**: When each loop iteration takes unpredictable time, but total duration must be bounded

## Examples

### Basic Usage

```yaml
nodes:
  - id: Time Guard
    type: loop_timer
    config:
      max_duration: 5
      duration_unit: minutes
      reset_on_emit: true
      message: Time limit reached (5 minutes), process terminated.
```

### Time-Limited Review Loop

This is the most typical use case for Loop Timer:

```yaml
graph:
  id: timed_review_loop
  description: Review loop with 5-minute time limit
  
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

    - id: Loop Gate
      type: loop_timer
      config:
        max_duration: 5
        duration_unit: minutes
        message: Time limit (5 minutes) reached, process automatically ended.

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
    
    # Condition 2: User enters modification suggestions -> Trigger both Writer to continue loop AND Loop Gate to track time
    - from: Reviewer
      to: Writer
      condition:
        type: keyword
        config:
          none: [ACCEPT]
    
    - from: Reviewer
      to: Loop Gate
      condition:
        type: keyword
        config:
          none: [ACCEPT]
    
    # Loop Gate connects to Writer (keeps it inside the loop)
    - from: Loop Gate
      to: Writer
    
    # When Loop Gate reaches time limit: Trigger Final Output to end the process
    - from: Loop Gate
      to: Final Output

  start: [Writer]
  end: [Final Output]
```

**Execution Flow Explanation**:
1. User first enters modification suggestions → Triggers both Writer (continue loop) and Loop Gate (track time, no output)
2. User enters modification suggestions again → Triggers both Writer (continue loop) and Loop Gate (track time, no output)
3. After 5 minutes of elapsed time → Loop Gate outputs message triggering Final Output, terminating the loop
4. Or at any time user enters ACCEPT → Goes directly to Final Output to end

## Notes

- `max_duration` must be a positive number (> 0)
- `duration_unit` must be one of: "seconds", "minutes", "hours"
- Loop Timer **produces no output until the time limit is reached**, outgoing edges will not trigger
- Ensure Loop Timer connects to both in-loop and out-of-loop nodes
- The `message` field is optional, default message is `"Time limit reached (N units)"`
- Timer starts on the first trigger to the Loop Timer node
