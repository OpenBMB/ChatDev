# Python SDK Determinism

## Overview

The Python SDK runs workflows in a sandbox that provides automatic protection against many non-deterministic operations.

## Why Determinism Matters: History Replay

Temporal provides durable execution through **History Replay**. When a Worker needs to restore workflow state (after a crash, cache eviction, or to continue after a long timer), it re-executes the workflow code from the beginning, which requires the workflow code to be **deterministic**.

## Forbidden Operations

- Direct I/O (network, filesystem)
- Threading operations
- `subprocess` calls
- Global mutable state modification
- `time.sleep()` (use `workflow.sleep(timedelta(...))`)
- and so on

## Safe Builtin Alternatives to Common Non Deterministic Things

| Forbidden | Safe Alternative |
|-----------|------------------|
| `datetime.now()` | `workflow.now()` |
| `datetime.utcnow()` | `workflow.now()` |
| `random.random()` | `rng = workflow.random() ; rng.randint(1, 100)` |
| `uuid.uuid4()` | `workflow.uuid4()` |
| `time.time()` | `workflow.now().timestamp()` |

## Testing Replay Compatibility

Use the `Replayer` class to verify your code changes are compatible with existing histories. See the Workflow Replay Testing section of `references/python/testing.md`.

## Sandbox Behavior

The sandbox:
- Isolates global state via `exec` compilation
- Restricts non-deterministic library calls via proxy objects
- Passes through standard library with restrictions

See more info at `references/python/determinism-protection.md`

## Best Practices

1. Use `workflow.now()` for all time operations
2. Use `workflow.random()` for random values
3. Use `workflow.uuid4()` for unique identifiers
4. Pass through third-party libraries explicitly
5. Test with replay to catch non-determinism
6. Keep workflows focused on orchestration, delegate I/O to activities
7. Use `workflow.logger` instead of print() for replay-safe logging
