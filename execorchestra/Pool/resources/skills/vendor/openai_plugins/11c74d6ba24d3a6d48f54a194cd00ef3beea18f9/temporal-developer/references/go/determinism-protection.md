# Go Workflow Determinism Protection

## Overview

The Go SDK has no runtime sandbox (only Python and TypeScript have sandboxing). Determinism is enforced by **developer convention** and **optional static analysis**. The Go SDK will not intercept or replace non-deterministic calls at runtime. The Go SDK does perform a limited runtime command-ordering check, but catching non-deterministic code before deployment requires the `workflowcheck` tool and testing, in particular replay tests (see `references/go/testing.md`).

## workflowcheck Static Analysis

### Install

```bash
go install go.temporal.io/sdk/contrib/tools/workflowcheck@latest
```

### Run

```bash
workflowcheck ./...
```

No output means all registered workflows are deterministic. Non-deterministic code produces hierarchical output showing the call chain to the offending code.

Use `-show-pos` for exact file positions:

```bash
workflowcheck -show-pos ./...
```

### What It Detects

**Non-deterministic functions/variables:**
- `time.Now` -- obtaining current time
- `time.Sleep` -- sleeping
- `crypto/rand.Reader` -- crypto random reader
- `math/rand.globalRand` -- global pseudorandom
- `os.Stdin`, `os.Stdout`, `os.Stderr` -- standard I/O streams

**Non-deterministic Go constructs:**
- Starting a goroutine (`go func()`)
- Sending to a channel
- Receiving from a channel
- Iterating over a channel via `range`
- Iterating over a map via `range`

### Limitations

`workflowcheck` cannot catch everything. It does **not** detect:
- Global variable mutation
- Non-determinism via reflection
- Runtime-conditional non-determinism

### Suppressing False Positives

Add `//workflowcheck:ignore` on or directly above the offending line:

```go
now := time.Now() //workflowcheck:ignore
```

For broader suppression, use a YAML config file:

```yaml
# workflowcheck.config.yaml
decls:
  path/to/package.MyDeterministicFunc: false
```

```bash
workflowcheck -config workflowcheck.config.yaml ./...
```

## Determinism Rules

**You must:**
- Use `workflow.Go(ctx, func(ctx workflow.Context) { ... })` instead of `go`
- Use `workflow.NewChannel(ctx)` instead of `chan`
- Use `workflow.NewSelector(ctx)` instead of `select`
- Use `workflow.Sleep(ctx, duration)` instead of `time.Sleep()`
- Use `workflow.Now(ctx)` instead of `time.Now()`
- Use `workflow.GetLogger(ctx)` instead of `fmt.Println` / `log.Println`
- Sort map keys before iterating, or use `workflow.SideEffect` / an activity

**You must not:**
- Start native goroutines
- Use native channels or `select`
- Call `time.Now()` or `time.Sleep()`
- Use `math/rand` global functions or `crypto/rand.Reader`
- Access `os.Stdin`, `os.Stdout`, or `os.Stderr`
- Mutate global variables
- Make network calls, file I/O, or database queries (use activities)

## Best Practices

1. **Run `workflowcheck` in CI / pre-commit** -- catch non-deterministic code before it reaches production
2. **Keep workflow code thin** -- workflows should orchestrate; delegate all I/O and non-deterministic work to activities
3. **Use struct methods for activities** -- keeps imports clean and avoids pulling non-deterministic dependencies into workflow files
4. **Separate workflow and activity files** -- reduces the surface area that `workflowcheck` needs to analyze and keeps concerns isolated
5. **Test with replay** after any workflow code change to verify backward compatibility
