# Go Gotchas

Go-specific mistakes and anti-patterns. See also [Common Gotchas](references/core/gotchas.md) for language-agnostic concepts.

## Goroutines and Concurrency

### Using Native Go Concurrency Primitives

**The Problem**: Native `go`, `chan`, and `select` are non-deterministic and will cause replay failures.

```go
// BAD - Native goroutine
func MyWorkflow(ctx workflow.Context) error {
	go func() { // Non-deterministic!
		// do work
	}()
	return nil
}

// GOOD - Use workflow.Go
func MyWorkflow(ctx workflow.Context) error {
	workflow.Go(ctx, func(gCtx workflow.Context) {
		// do work
	})
	return nil
}
```

```go
// BAD - Native channel
func MyWorkflow(ctx workflow.Context) error {
	ch := make(chan string) // Non-deterministic!
	return nil
}

// GOOD - Use workflow.Channel
func MyWorkflow(ctx workflow.Context) error {
	ch := workflow.NewChannel(ctx)
	return nil
}
```

```go
// BAD - Native select
select {
case val := <-ch1:
	// handle
case val := <-ch2:
	// handle
}

// GOOD - Use workflow.Selector
selector := workflow.NewSelector(ctx)
selector.AddReceive(ch1, func(c workflow.ReceiveChannel, more bool) {
	var val string
	c.Receive(ctx, &val)
	// handle
})
selector.AddReceive(ch2, func(c workflow.ReceiveChannel, more bool) {
	var val string
	c.Receive(ctx, &val)
	// handle
})
selector.Select(ctx)
```

## Non-Deterministic Operations

### Map Iteration

```go
// BAD - Map range order is randomized
for k, v := range myMap {
	// Non-deterministic order!
}

// GOOD - Sort keys first
keys := make([]string, 0, len(myMap))
for k := range myMap {
	keys = append(keys, k)
}
sort.Strings(keys)
for _, k := range keys {
	v := myMap[k]
	// Deterministic order
}
```

### Time and Randomness

```go
// BAD
t := time.Now()           // System clock, non-deterministic
time.Sleep(time.Second)   // Not replay-safe
r := rand.Intn(100)       // Non-deterministic

// GOOD
t := workflow.Now(ctx)                     // Deterministic
workflow.Sleep(ctx, time.Second)           // Durable timer
encoded := workflow.SideEffect(ctx, func(ctx workflow.Context) interface{} {
	return rand.Intn(100)
})
var r int
encoded.Get(&r)
```

Use the `workflowcheck` static analysis tool to catch non-deterministic calls. For false positives, annotate with `//workflowcheck:ignore` on the line above.

### Anonymous Functions as Local Activities

**The Problem**: The Go SDK derives the local activity name from the function. Anonymous functions get a non-deterministic name that can change across builds, causing replay failures.

```go
// BAD - anonymous function: name is non-deterministic
workflow.ExecuteLocalActivity(ctx, func(ctx context.Context) (string, error) {
    return "result", nil
})

// GOOD - named function: stable, deterministic name
func QuickLookup(ctx context.Context) (string, error) {
    return "result", nil
}

workflow.ExecuteLocalActivity(ctx, QuickLookup)
```

Always use named functions for local activities (and regular activities).

## Wrong Retry Classification

**Example:** Transient network errors should be retried. Authentication errors should not be.
See `references/go/error-handling.md` for detailed guidance on error classification and retry policies.

## Heartbeating

### Forgetting to Heartbeat Long Activities

```go
// BAD - No heartbeat, can't detect stuck activities or receive cancellation
func ProcessLargeFile(ctx context.Context, path string) error {
	for _, chunk := range readChunks(path) {
		process(chunk) // Takes hours, no heartbeat
	}
	return nil
}

// GOOD - Regular heartbeats with progress
func ProcessLargeFile(ctx context.Context, path string) error {
	for i, chunk := range readChunks(path) {
		activity.RecordHeartbeat(ctx, fmt.Sprintf("Processing chunk %d", i))
		process(chunk)
	}
	return nil
}
```

### Heartbeat Timeout Too Short

```go
// BAD - Heartbeat timeout shorter than processing time
ao := workflow.ActivityOptions{
	StartToCloseTimeout: 30 * time.Minute,
	HeartbeatTimeout:    10 * time.Second, // Too short!
}

// GOOD - Heartbeat timeout allows for processing variance
ao := workflow.ActivityOptions{
	StartToCloseTimeout: 30 * time.Minute,
	HeartbeatTimeout:    2 * time.Minute,
}
```

Set heartbeat timeout as high as acceptable for your use case -- each heartbeat counts as an action.

## Cancellation

### Not Handling Workflow Cancellation

```go
// BAD - Cleanup doesn't run on cancellation
func BadWorkflow(ctx workflow.Context) error {
	_ = workflow.ExecuteActivity(ctx, AcquireResource).Get(ctx, nil)
	_ = workflow.ExecuteActivity(ctx, DoWork).Get(ctx, nil)
	_ = workflow.ExecuteActivity(ctx, ReleaseResource).Get(ctx, nil) // Never runs if cancelled!
	return nil
}

// GOOD - Use defer with NewDisconnectedContext for cleanup
func GoodWorkflow(ctx workflow.Context) error {
	defer func() {
		if !errors.Is(ctx.Err(), workflow.ErrCanceled) {
			return
		}
		newCtx, _ := workflow.NewDisconnectedContext(ctx)
		_ = workflow.ExecuteActivity(newCtx, ReleaseResource).Get(newCtx, nil)
	}()

	err := workflow.ExecuteActivity(ctx, AcquireResource).Get(ctx, nil)
	if err != nil {
		return err
	}
	return workflow.ExecuteActivity(ctx, DoWork).Get(ctx, nil)
}
```

### Not Handling Activity Cancellation

Activities must **opt in** to receive cancellation. This requires:
1. **Heartbeating** - Cancellation is delivered via heartbeat
2. **Checking ctx.Done()** - Detect when cancellation arrives

```go
// BAD - Activity ignores cancellation
func LongActivity(ctx context.Context) error {
	doExpensiveWork() // Runs to completion even if cancelled
	return nil
}

// GOOD - Heartbeat and check ctx.Done()
func LongActivity(ctx context.Context) error {
	for i, item := range items {
		select {
		case <-ctx.Done():
			cleanup()
			return ctx.Err()
		default:
			activity.RecordHeartbeat(ctx, fmt.Sprintf("Processing item %d", i))
			process(item)
		}
	}
	return nil
}
```

## Testing

### Not Testing Failures

It is important to make sure workflows work as expected under failure paths in addition to happy paths. Please see `references/go/testing.md` for more info.

### Not Testing Replay

Replay tests help you test that you do not have hidden sources of non-determinism bugs in your workflow code, and should be considered in addition to standard testing. Please see `references/go/testing.md` for more info.

## Timers and Sleep

### Using time.Sleep Instead of workflow.Sleep

```go
// BAD: time.Sleep is not deterministic during replay
func BadWorkflow(ctx workflow.Context) error {
	time.Sleep(60 * time.Second) // Non-deterministic!
	return nil
}

// GOOD: Use workflow.Sleep for deterministic timers
func GoodWorkflow(ctx workflow.Context) error {
	workflow.Sleep(ctx, 60*time.Second) // Deterministic
	return nil
}
```

### Using time.After Instead of workflow.NewTimer

```go
// BAD: time.After is not replay-safe
func BadWorkflow(ctx workflow.Context) error {
	<-time.After(5 * time.Minute) // Non-deterministic!
	return nil
}

// GOOD: Use workflow.NewTimer for durable timers
func GoodWorkflow(ctx workflow.Context) error {
	timer := workflow.NewTimer(ctx, 5*time.Minute)
	_ = timer.Get(ctx, nil) // Deterministic, durable
	return nil
}
```

### Using time.Now() Instead of workflow.Now()

```go
// BAD: time.Now() differs between execution and replay
deadline := time.Now().Add(24 * time.Hour)

// GOOD: workflow.Now() is replay-safe
deadline := workflow.Now(ctx).Add(24 * time.Hour)
```

**Why this matters:** `time.Now()`, `time.Sleep()`, and `time.After()` use the system clock, which differs between original execution and replay. The `workflow.*` equivalents create durable, deterministic entries in the event history.
