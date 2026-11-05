# Determinism in Temporal Workflows

This document provides a conceptual-level overview to determinism in Temporal. Additional language-specific determinism information is available at `references/{your_language}/determinism.md`.

## Overview

Temporal workflows must be deterministic because of **history replay** - the mechanism that enables durable execution.

## Why Determinism Matters

### The Replay Mechanism

When a Worker needs to restore workflow state (after crash, cache eviction, or continuing after a long timer), it **re-executes the workflow code from the beginning**. But instead of re-running external actions, it uses results stored in the Event History.

```
Initial Execution:
  Code runs → Generates Commands → Server stores as Events

Replay (Recovery):
  Code runs again → Generates Commands → SDK compares to Events
  If match: Use stored results, continue
  If mismatch: NondeterminismError!
```

### Commands and Events

Every workflow operation generates a Command that becomes an Event, here are some examples:

| Workflow Code | Command Generated | Event Stored |
|--------------|-------------------|--------------|
| Execute activity | `ScheduleActivityTask` | `ActivityTaskScheduled` |
| Sleep/timer | `StartTimer` | `TimerStarted` |
| Child workflow | `StartChildWorkflowExecution` | `ChildWorkflowExecutionStarted` |
| Complete workflow | `CompleteWorkflowExecution` | `WorkflowExecutionCompleted` |

### Non-Determinism Example

```
First Run (11:59 AM):
  if datetime.now().hour < 12:  → True
    execute_activity(morning_task)  → Command: ScheduleActivityTask("morning_task")

Replay (12:01 PM):
  if datetime.now().hour < 12:  → False
    execute_activity(afternoon_task)  → Command: ScheduleActivityTask("afternoon_task")

Result: Commands don't match history → NondeterminismError
```

## Sources of Non-Determinism

### Time-Based Operations
- `datetime.now()`, `time.time()`, `Date.now()`
- Different value on each execution

### Random Values
- `random.random()`, `Math.random()`, `uuid.uuid4()`
- Different value on each execution

### External State
- Reading files, environment variables, databases, networking / HTTP calls
- State may change between executions

### Non-Deterministic Iteration
- Map/dict iteration order (in some languages)
- Set iteration order

### Threading/Concurrency
- Race conditions produce different outcomes
- Non-deterministic ordering

## **Central Concept**: Place Non-Determinism within Activities

In Temporal, activities are the primary mechanism for making non-deterministic code durable and persisted in workflow history. Generally speaking, you should place sources of non-determinism in activities, which provides durability and recording of results, as well as automated retries and more. See `references/{your_language}/{your_language}.md` for the language you are working in for how to do this in practice.

For a few simple cases, like timestamps, random values, UUIDs, etc. the Temporal SDK in your language may provide durable variants that are simple to use. See `references/{your_language}/determinism.md` for the language you are working in for more info.

## SDK Protection Mechanisms
Each Temporal SDK language provides a different level of protection against non-determinism:

- Python: The Python SDK runs workflows in a sandbox that intercepts and aborts non-deterministic calls early at runtime.
- TypeScript: The TypeScript SDK runs workflows in an isolated V8 sandbox, intercepting many common sources of non-determinism and replacing them automatically with deterministic variants.
- Java: The Java SDK has no sandbox. Determinism is enforced by developer conventions — the SDK provides `Workflow.*` APIs as safe alternatives (e.g., `Workflow.sleep()` instead of `Thread.sleep()`), and non-determinism is only detected at replay time via `NonDeterministicException`. A static analysis tool (`temporal-workflowcheck`, beta) can catch violations at build time. Cooperative threading under a global lock eliminates the need for synchronization.
- Go: The Go SDK has no runtime sandbox. Therefore, non-determinism bugs will never be immediately appararent, and are usually only observable during replay. The optional `workflowcheck` static analysis tool can be used to check for many sources of non-determinism at compile time.

Regardless of which SDK you are using, it is your responsibility to ensure that workflow code does not contain sources of non-determinism. Use SDK-specific tools as well as replay tests for doing so.

## Detecting Non-Determinism

### During Execution
- `NondeterminismError` raised when Commands don't match Events
- Workflow becomes blocked until code is fixed

### Testing with Replay

Replay tests verify that workflows follow identical code paths when re-run, by attempting to replay recorded executions. See the replay testing section of `references/{your_language}/testing.md` for information on how to write these tests.

## Recovery from Non-Determinism

### Accidental Change
If you accidentally introduced non-determinism:
1. Revert code to match what's in history
2. Restart worker
3. Workflow auto-recovers

### Intentional Change
If you need to change workflow logic:
1. Use the **Patching API** to support both old and new code paths
2. Or terminate old workflows and start new ones with updated code

See `versioning.md` for patching details.

## Best Practices

1. **Use SDK-provided alternatives** for time, random, UUID
2. **Move I/O to activities** - workflows should only orchestrate
3. **Test with replay** before deploying workflow changes
4. **Use patching** for intentional changes to running workflows
5. **Keep workflows focused** - complex logic increases non-determinism risk
