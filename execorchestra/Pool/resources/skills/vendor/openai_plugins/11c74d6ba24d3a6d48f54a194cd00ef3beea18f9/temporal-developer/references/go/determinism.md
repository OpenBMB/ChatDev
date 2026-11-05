# Go SDK Determinism

## Overview

The Go SDK has NO runtime sandbox (unlike Python/TypeScript). Workflows must be deterministic for replay, and determinism is enforced entirely by developer convention and optional static analysis via the `workflowcheck` tool (see `references/go/determinism-protection.md`).

## Why Determinism Matters: History Replay

Temporal provides durable execution through **History Replay**. When a Worker restores workflow state, it re-executes workflow code from the beginning. This requires the code to be **deterministic**. See `references/core/determinism.md` for a deep explanation.

## Forbidden Operations

Do not use any of the following in workflow code:

- **Native goroutines** (`go func()`) -- use `workflow.Go()` instead
- **Native channels** (`chan`, send, receive, `range` over channel) -- use `workflow.Channel` instead
- **Native `select`** -- use `workflow.Selector` instead
- **`time.Now()`** -- use `workflow.Now(ctx)` instead
- **`time.Sleep()`** -- use `workflow.Sleep(ctx, duration)` instead
- **`math/rand` global** (e.g., `rand.Intn()`) -- use `workflow.SideEffect` instead
- **`crypto/rand.Reader`** -- use an activity instead
- **`os.Stdin` / `os.Stdout` / `os.Stderr`** -- use `workflow.GetLogger(ctx)` for logging
- **Map range iteration** (`for k, v := range myMap`) -- sort keys first, then iterate
- **Mutating global variables** -- use local state or `workflow.SideEffect`
- **Anonymous functions as local activities** -- the name is derived from the function and will be non-deterministic across replays; always use named functions for local activities

## Safe Builtin Alternatives

| Instead of | Use |
|---|---|
| `go func() { ... }()` | `workflow.Go(ctx, func(ctx workflow.Context) { ... })` |
| `chan T` | `workflow.NewChannel(ctx)` / `workflow.NewBufferedChannel(ctx, size)` |
| `select { ... }` | `workflow.NewSelector(ctx)` |
| `time.Now()` | `workflow.Now(ctx)` |
| `time.Sleep(d)` | `workflow.Sleep(ctx, d)` |
| `rand.Intn(100)` | `workflow.SideEffect(ctx, func(ctx workflow.Context) interface{} { return rand.Intn(100) })` |
| `uuid.New()` | `workflow.SideEffect` or pass as activity result |
| `log.Println(...)` | `workflow.GetLogger(ctx).Info(...)` |

## Testing Replay Compatibility

Use `worker.WorkflowReplayer` to verify code changes are compatible with existing histories. See the Workflow Replay Testing section of `references/go/testing.md`

## Best Practices

1. Run `workflowcheck ./...` in CI to catch non-deterministic code early
2. Always use `workflow.*` APIs instead of native Go concurrency and time primitives
3. Move all I/O operations (network, filesystem, database) into activities
4. Sort map keys before iterating if you must iterate over a map in workflow code
5. Use `workflow.GetLogger(ctx)` instead of `fmt.Println` or `log.Println` for replay-safe logging
6. Keep workflow code focused on orchestration; delegate non-deterministic work to activities
7. Test with replay after making changes to workflow definitions
