# Java SDK Determinism

## Overview

The Java SDK has **no sandbox** (only Python and TypeScript have sandboxing). The Java SDK relies on developer conventions to enforce determinism. The SDK provides `Workflow.*` APIs as safe replacements for common non-deterministic operations. A static analysis tool (`temporal-workflowcheck`, beta) can catch violations at build time — see `references/java/determinism-protection.md`.

## Why Determinism Matters: History Replay

Temporal provides durable execution through **History Replay**. When a Worker needs to restore workflow state (after a crash, cache eviction, or to continue after a long timer), it re-executes the workflow code from the beginning, which requires the workflow code to be **deterministic**.

## SDK Protection

Java workflow code runs in a cooperative threading model where only one workflow thread executes at a time under a global lock. The SDK does not intercept or block non-deterministic calls at runtime. If you call a forbidden operation, it will silently succeed during the initial execution but cause a `NonDeterministicException` when the workflow is replayed.

`temporal-workflowcheck` (static analysis, beta) and `WorkflowReplayer` (replay testing) can help uncover some violations, but they are not exhaustive — careful code review and adherence to the rules below remain essential.

## Forbidden Operations

- `Thread.sleep()` — blocks the real thread, bypasses Temporal timers
- `new Thread()` or thread pools — breaks the cooperative threading model
- `synchronized` blocks and explicit locks — can deadlock with the workflow executor
- `UUID.randomUUID()` — non-deterministic across replays
- `Math.random()` or `new Random()` — non-deterministic across replays
- `System.currentTimeMillis()` or `Instant.now()` — non-deterministic across replays
- Direct I/O (network, filesystem, database) — side effects must run in activities
- Mutable global/static state — shared state breaks isolation between workflow instances
- `CompletableFuture` — bypasses the workflow scheduler; use `Promise` instead

## Safe Builtin Alternatives

| Forbidden | Safe Alternative |
|-----------|------------------|
| `Thread.sleep(millis)` | `Workflow.sleep(Duration.ofMillis(millis))` |
| `UUID.randomUUID()` | `Workflow.randomUUID()` |
| `Math.random()` | `Workflow.newRandom().nextInt()` |
| `System.currentTimeMillis()` | `Workflow.currentTimeMillis()` |
| `new Thread(runnable)` | `Async.function(func)` / `Async.procedure(proc)` |
| `CompletableFuture<T>` | `Promise<T>` / `CompletablePromise<T>` |
| `BlockingQueue<T>` | `WorkflowQueue<T>` |
| `Future<T>` | `Promise<T>` |

## Testing Replay Compatibility

Use the `WorkflowReplayer` class to verify your code changes are compatible with existing histories. See the Workflow Replay Testing section of `references/java/testing.md`.

## Best Practices

1. Use `Workflow.currentTimeMillis()` for all time operations
2. Use `Workflow.newRandom()` for random values
3. Use `Workflow.randomUUID()` for unique identifiers
4. Use `Async.function()` / `Async.procedure()` instead of raw threads
5. Use `Promise` and `CompletablePromise` instead of `CompletableFuture`
6. Test with `WorkflowReplayer` to catch non-determinism
7. Keep workflows focused on orchestration, delegate I/O to activities
8. Use `Workflow.getLogger()` for replay-safe logging
