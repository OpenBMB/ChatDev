# Go SDK Patterns

## Signals

In Go, signals are received via channels, not handler functions.

```go
func OrderWorkflow(ctx workflow.Context) (string, error) {
    approved := false
    var items []string

    approveCh := workflow.GetSignalChannel(ctx, "approve")
    addItemCh := workflow.GetSignalChannel(ctx, "add-item")

    // Listen for signals in a goroutine so workflow can proceed
    workflow.Go(ctx, func(ctx workflow.Context) {
        for {
            selector := workflow.NewSelector(ctx)
            selector.AddReceive(approveCh, func(c workflow.ReceiveChannel, more bool) {
                c.Receive(ctx, &approved)
            })
            selector.AddReceive(addItemCh, func(c workflow.ReceiveChannel, more bool) {
                var item string
                c.Receive(ctx, &item)
                items = append(items, item)
            })
            selector.Select(ctx)
        }
    })

    // Wait for approval
    workflow.Await(ctx, func() bool { return approved })
    return fmt.Sprintf("Processed %d items", len(items)), nil
}
```

### Blocking receive from a single channel

When waiting on a single signal, no Selector is needed:

```go
var approveInput ApproveInput
workflow.GetSignalChannel(ctx, "approve").Receive(ctx, &approveInput)
```

## Queries

**Important:** Queries must NOT modify workflow state. Query handlers run outside workflow context -- do not call `workflow.Go()`, `workflow.NewChannel()`, or any blocking workflow functions.

```go
func StatusWorkflow(ctx workflow.Context) error {
    currentState := "started"
    progress := 0

    err := workflow.SetQueryHandler(ctx, "get-status", func() (string, error) {
        return currentState, nil
    })
    if err != nil {
        return err
    }

    err = workflow.SetQueryHandler(ctx, "get-progress", func() (int, error) {
        return progress, nil
    })
    if err != nil {
        return err
    }

    // Workflow logic updates currentState and progress as it runs
    currentState = "running"
    for i := 0; i < 100; i++ {
        progress = i
        err := workflow.ExecuteActivity(
            workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
                StartToCloseTimeout: time.Minute,
            }),
            ProcessItem, i,
        ).Get(ctx, nil)
        if err != nil {
            currentState = "failed"
            return err
        }
    }
    currentState = "done"
    return nil
}
```

## Updates

```go
func OrderWorkflow(ctx workflow.Context) (int, error) {
    var items []string

    err := workflow.SetUpdateHandlerWithOptions(
        ctx,
        "add-item",
        func(ctx workflow.Context, item string) (int, error) {
            // Handler can mutate workflow state and return a value
            items = append(items, item)
            return len(items), nil
        },
        workflow.UpdateHandlerOptions{
            Validator: func(ctx workflow.Context, item string) error {
                if item == "" {
                    return fmt.Errorf("item cannot be empty")
                }
                if len(items) >= 100 {
                    return fmt.Errorf("order is full")
                }
                return nil
            },
        },
    )
    if err != nil {
        return 0, err
    }

    // Block until cancelled
    _ = ctx.Done().Receive(ctx, nil)
    return len(items), nil
}
```

**Important:** Validators must NOT mutate workflow state or do anything blocking (no activities, sleeps, or other commands). They are read-only, similar to query handlers. Return an error to reject the update; return `nil` to accept.

## Child Workflows

```go
func ParentWorkflow(ctx workflow.Context, orders []Order) ([]string, error) {
    cwo := workflow.ChildWorkflowOptions{
        WorkflowExecutionTimeout: 30 * time.Minute,
    }
    ctx = workflow.WithChildOptions(ctx, cwo)

    var results []string
    for _, order := range orders {
        var result string
        err := workflow.ExecuteChildWorkflow(ctx, ProcessOrderWorkflow, order).Get(ctx, &result)
        if err != nil {
            return nil, err
        }
        results = append(results, result)
    }
    return results, nil
}
```

### Child Workflow Options

```go
import enumspb "go.temporal.io/api/enums/v1"

cwo := workflow.ChildWorkflowOptions{
    WorkflowID: fmt.Sprintf("child-%s", workflow.GetInfo(ctx).WorkflowExecution.ID),

    // ParentClosePolicy - what happens to child when parent closes
    // PARENT_CLOSE_POLICY_TERMINATE (default), PARENT_CLOSE_POLICY_ABANDON, PARENT_CLOSE_POLICY_REQUEST_CANCEL
    ParentClosePolicy: enumspb.PARENT_CLOSE_POLICY_ABANDON,

    WorkflowExecutionTimeout: 10 * time.Minute,
    WorkflowTaskTimeout:      time.Minute,
}
ctx = workflow.WithChildOptions(ctx, cwo)

future := workflow.ExecuteChildWorkflow(ctx, ChildWorkflow, input)

// Wait for child to start (important for ABANDON policy)
if err := future.GetChildWorkflowExecution().Get(ctx, nil); err != nil {
    return err
}
```

## Handles to External Workflows

```go
func CoordinatorWorkflow(ctx workflow.Context, targetWorkflowID string) error {
    // Signal an external workflow
    err := workflow.SignalExternalWorkflow(ctx, targetWorkflowID, "", "data-ready", payload).Get(ctx, nil)
    if err != nil {
        return err
    }

    // Cancel an external workflow
    err = workflow.RequestCancelExternalWorkflow(ctx, targetWorkflowID, "").Get(ctx, nil)
    return err
}
```

## Parallel Execution

Use `workflow.Go` to launch parallel work and `workflow.Selector` to collect results.

```go
func ParallelWorkflow(ctx workflow.Context, items []string) ([]string, error) {
    actCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
        StartToCloseTimeout: 5 * time.Minute,
    })

    // Launch activities in parallel
    futures := make([]workflow.Future, len(items))
    for i, item := range items {
        futures[i] = workflow.ExecuteActivity(actCtx, ProcessItem, item)
    }

    // Collect all results
    results := make([]string, len(items))
    for i, future := range futures {
        if err := future.Get(ctx, &results[i]); err != nil {
            return nil, err
        }
    }
    return results, nil
}
```

### Using workflow.Go for background goroutines

```go
ch := workflow.NewChannel(ctx)

workflow.Go(ctx, func(ctx workflow.Context) {
    // Background work
    var result string
    _ = workflow.ExecuteActivity(actCtx, SomeActivity).Get(ctx, &result)
    ch.Send(ctx, result)
})

var result string
ch.Receive(ctx, &result)
```

## Selector Pattern

`workflow.Selector` replaces Go's native `select` -- required for deterministic workflow execution. Use it to wait on multiple channels, futures, and timers simultaneously.

```go
func ApprovalWorkflow(ctx workflow.Context) (string, error) {
    actCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
        StartToCloseTimeout: 5 * time.Minute,
    })

    var outcome string
    signalCh := workflow.GetSignalChannel(ctx, "approve")
    actFuture := workflow.ExecuteActivity(actCtx, AutoReviewActivity)

    // Cancel timer if signal or activity wins
    timerCtx, cancelTimer := workflow.WithCancel(ctx)
    timer := workflow.NewTimer(timerCtx, 24*time.Hour)

    selector := workflow.NewSelector(ctx)

    // Branch 1: Signal received
    selector.AddReceive(signalCh, func(c workflow.ReceiveChannel, more bool) {
        var approved bool
        c.Receive(ctx, &approved)
        cancelTimer()
        if approved {
            outcome = "approved-by-signal"
        } else {
            outcome = "rejected-by-signal"
        }
    })

    // Branch 2: Activity completed
    selector.AddFuture(actFuture, func(f workflow.Future) {
        var result string
        _ = f.Get(ctx, &result)
        cancelTimer()
        outcome = result
    })

    // Branch 3: Timeout
    selector.AddFuture(timer, func(f workflow.Future) {
        if err := f.Get(ctx, nil); err == nil {
            outcome = "timed-out"
        }
        // If timer was cancelled, err is CanceledError -- ignore
    })

    selector.Select(ctx) // Blocks until one branch fires
    return outcome, nil
}
```

Key points:
- `AddReceive(channel, callback)` -- fires when a channel has a message (must consume with `c.Receive`)
- `AddFuture(future, callback)` -- fires when a future resolves (once per Selector)
- `AddDefault(callback)` -- fires immediately if nothing else is ready
- `Select(ctx)` -- blocks until one branch fires; call multiple times to process multiple events

## Continue-as-New

```go
func LongRunningWorkflow(ctx workflow.Context, state WorkflowState) (string, error) {
    for {
        state = processBatch(ctx, state)

        if state.IsComplete {
            return "done", nil
        }

        // Check if history is getting large
        if workflow.GetInfo(ctx).GetContinueAsNewSuggested() {
            return "", workflow.NewContinueAsNewError(ctx, LongRunningWorkflow, state)
        }
    }
}
```

Drain signals before continue-as-new to avoid signal loss:

```go
for {
    var signalVal string
    ok := signalChan.ReceiveAsync(&signalVal)
    if !ok {
        break
    }
    // process signal
}
return "", workflow.NewContinueAsNewError(ctx, LongRunningWorkflow, state)
```

## Cancellation Handling

Use `ctx.Done()` to detect cancellation and `workflow.NewDisconnectedContext` for cleanup that must run even after cancellation.

```go
func MyWorkflow(ctx workflow.Context) error {
    actCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
        StartToCloseTimeout: time.Hour,
    })

    err := workflow.ExecuteActivity(actCtx, LongRunningActivity).Get(ctx, nil)
    if err != nil && temporal.IsCanceledError(ctx.Err()) {
        // Workflow was cancelled -- run cleanup with a disconnected context
        workflow.GetLogger(ctx).Info("Workflow cancelled, running cleanup")
        disconnectedCtx, _ := workflow.NewDisconnectedContext(ctx)
        disconnectedCtx = workflow.WithActivityOptions(disconnectedCtx, workflow.ActivityOptions{
            StartToCloseTimeout: 5 * time.Minute,
        })
        _ = workflow.ExecuteActivity(disconnectedCtx, CleanupActivity).Get(disconnectedCtx, nil)
        return err // Return CanceledError
    }
    return err
}
```

## Saga Pattern (Compensations)

**Important:** Compensation activities should be idempotent -- they may be retried (as with ALL activities).

Use `workflow.NewDisconnectedContext` when running compensations so they execute even if the workflow is cancelled.

```go
func OrderWorkflow(ctx workflow.Context, order Order) (string, error) {
    actCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
        StartToCloseTimeout: 5 * time.Minute,
    })

    var compensations []func(ctx workflow.Context) error

    // Helper to run all compensations in reverse, using a disconnected context
    // so compensations run even if the workflow is cancelled.
    runCompensations := func() {
        disconnectedCtx, _ := workflow.NewDisconnectedContext(ctx)
        compCtx := workflow.WithActivityOptions(disconnectedCtx, workflow.ActivityOptions{
            StartToCloseTimeout: 5 * time.Minute,
        })
        for i := len(compensations) - 1; i >= 0; i-- {
            if err := compensations[i](compCtx); err != nil {
                workflow.GetLogger(ctx).Error("Compensation failed", "error", err)
            }
        }
    }

    // Register compensation BEFORE running the activity.
    // If the activity completes the effect but fails on return,
    // we still need the compensation.
    compensations = append(compensations, func(ctx workflow.Context) error {
        return workflow.ExecuteActivity(ctx, ReleaseInventoryIfReserved, order).Get(ctx, nil)
    })
    if err := workflow.ExecuteActivity(actCtx, ReserveInventory, order).Get(ctx, nil); err != nil {
        runCompensations()
        return "", err
    }

    compensations = append(compensations, func(ctx workflow.Context) error {
        return workflow.ExecuteActivity(ctx, RefundPaymentIfCharged, order).Get(ctx, nil)
    })
    if err := workflow.ExecuteActivity(actCtx, ChargePayment, order).Get(ctx, nil); err != nil {
        runCompensations()
        return "", err
    }

    if err := workflow.ExecuteActivity(actCtx, ShipOrder, order).Get(ctx, nil); err != nil {
        runCompensations()
        return "", err
    }

    return "Order completed", nil
}
```

## Wait Condition with Timeout

```go
func ApprovalWorkflow(ctx workflow.Context) (string, error) {
    approved := false

    // Set up signal handler
    workflow.Go(ctx, func(ctx workflow.Context) {
        workflow.GetSignalChannel(ctx, "approve").Receive(ctx, &approved)
    })

    // Wait with 24-hour timeout -- returns (conditionMet, error)
    conditionMet, err := workflow.AwaitWithTimeout(ctx, 24*time.Hour, func() bool {
        return approved
    })
    if err != nil {
        return "", err
    }

    if conditionMet {
        return "approved", nil
    }
    return "auto-rejected due to timeout", nil
}
```

Without timeout:

```go
err := workflow.Await(ctx, func() bool { return ready })
```

## Waiting for All Handlers to Finish

Signal and update handlers may run activities asynchronously. Use `workflow.Await` with `workflow.AllHandlersFinished` before completing or continuing-as-new to prevent the workflow from closing while handlers are still running.

```go
func MyWorkflow(ctx workflow.Context) (string, error) {
    // ... register handlers, main workflow logic ...

    // Before exiting, wait for all handlers to finish
    err := workflow.Await(ctx, func() bool {
        return workflow.AllHandlersFinished(ctx)
    })
    if err != nil {
        return "", err
    }
    return "done", nil
}
```

## Activity Heartbeat Details

### WHY:
- **Support activity cancellation** -- Cancellations are delivered via heartbeat; activities that don't heartbeat won't know they've been cancelled
- **Resume progress after worker failure** -- Heartbeat details persist across retries

### WHEN:
- **Cancellable activities** -- Any activity that should respond to cancellation
- **Long-running activities** -- Track progress for resumability
- **Checkpointing** -- Save progress periodically

```go
func ProcessLargeFile(ctx context.Context, filePath string) (string, error) {
    // Recover from previous attempt
    startIdx := 0
    if activity.HasHeartbeatDetails(ctx) {
        if err := activity.GetHeartbeatDetails(ctx, &startIdx); err == nil {
            startIdx++ // Resume from next item
        }
    }

    lines := readFileLines(filePath)

    for i := startIdx; i < len(lines); i++ {
        processLine(lines[i])

        // Heartbeat with progress -- if cancelled, ctx will be cancelled
        activity.RecordHeartbeat(ctx, i)

        if ctx.Err() != nil {
            // Activity was cancelled
            cleanup()
            return "", ctx.Err()
        }
    }

    return "completed", nil
}
```

## Timers

```go
func TimerWorkflow(ctx workflow.Context) (string, error) {
    // Simple sleep
    err := workflow.Sleep(ctx, time.Hour)
    if err != nil {
        return "", err
    }

    // Timer as a Future -- for use with Selector
    timerCtx, cancelTimer := workflow.WithCancel(ctx)
    timer := workflow.NewTimer(timerCtx, 30*time.Minute)

    // Cancel the timer when no longer needed
    cancelTimer()

    return "Timer fired", nil
}
```

## Local Activities

**Purpose**: Reduce latency for short, lightweight operations by skipping the task queue. ONLY use these when necessary for performance. Do NOT use these by default, as they are not durable and distributed.

```go
func MyWorkflow(ctx workflow.Context) (string, error) {
    lao := workflow.LocalActivityOptions{
        StartToCloseTimeout: 5 * time.Second,
    }
    ctx = workflow.WithLocalActivityOptions(ctx, lao)

    var result string
    err := workflow.ExecuteLocalActivity(ctx, QuickLookup, "key").Get(ctx, &result)
    if err != nil {
        return "", err
    }
    return result, nil
}
```
