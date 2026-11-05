# Go SDK Error Handling

## Overview

The Go SDK uses error return values (not exceptions). All Temporal errors implement the `error` interface. Activity errors returned to workflows are wrapped in `*temporal.ActivityError`; use `errors.As` to unwrap them.

## Application Errors

```go
import "go.temporal.io/sdk/temporal"

func ValidateOrder(ctx context.Context, order Order) error {
	if !order.IsValid() {
		return temporal.NewApplicationError(
			"Invalid order",
			"ValidationError",
		)
	}
	return nil
}
```

`temporal.NewApplicationError(message, errType, details...)` creates a retryable `*temporal.ApplicationError`. Use `NewApplicationErrorWithCause` to include a wrapped cause.

## Non-Retryable Errors

```go
func ChargeCard(ctx context.Context, input ChargeCardInput) (string, error) {
	if !isValidCard(input.CardNumber) {
		return "", temporal.NewNonRetryableApplicationError(
			"Permanent failure - invalid credit card",
			"PaymentError",
			nil, // cause
		)
	}
	return processPayment(input.CardNumber, input.Amount)
}
```

`temporal.NewNonRetryableApplicationError(message, errType, cause, details...)` is always non-retryable regardless of RetryPolicy. You can also mark error types as non-retryable in the RetryPolicy instead:

```go
RetryPolicy: &temporal.RetryPolicy{
	NonRetryableErrorTypes: []string{"PaymentError", "ValidationError"},
},
```

## Handling Activity Errors in Workflows

```go
import (
	"errors"

	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/workflow"
)

func MyWorkflow(ctx workflow.Context) (string, error) {
	var result string
	err := workflow.ExecuteActivity(ctx, RiskyActivity).Get(ctx, &result)
	if err != nil {
		var applicationErr *temporal.ApplicationError
		if errors.As(err, &applicationErr) {
			switch applicationErr.Type() {
			case "ValidationError":
				// handle validation error
			case "PaymentError":
				// handle payment error
			default:
				// handle unknown error type
			}
		}

		var timeoutErr *temporal.TimeoutError
		if errors.As(err, &timeoutErr) {
			switch timeoutErr.TimeoutType() {
			case enumspb.TIMEOUT_TYPE_START_TO_CLOSE:
				// handle start-to-close timeout
			case enumspb.TIMEOUT_TYPE_HEARTBEAT:
				// handle heartbeat timeout
			}
		}

		var canceledErr *temporal.CanceledError
		if errors.As(err, &canceledErr) {
			// handle cancellation
		}

		var panicErr *temporal.PanicError
		if errors.As(err, &panicErr) {
			// panicErr.Error() and panicErr.StackTrace()
		}

		return "", err
	}
	return result, nil
}
```

## Retry Configuration

```go
import (
	"time"

	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/workflow"
)

func MyWorkflow(ctx workflow.Context) error {
	ao := workflow.ActivityOptions{
		StartToCloseTimeout: 10 * time.Minute,
		RetryPolicy: &temporal.RetryPolicy{
			InitialInterval:        time.Second,
			BackoffCoefficient:     2.0,
			MaximumInterval:        time.Minute,
			MaximumAttempts:        5,
			NonRetryableErrorTypes: []string{"ValidationError", "PaymentError"},
		},
	}
	ctx = workflow.WithActivityOptions(ctx, ao)
	return workflow.ExecuteActivity(ctx, MyActivity).Get(ctx, nil)
}
```

Only set options such as `MaximumInterval`, `MaximumAttempts`, etc. if you have a domain-specific reason to. If not, prefer to leave them at their defaults.

## Timeout Configuration

```go
ao := workflow.ActivityOptions{
	StartToCloseTimeout:    5 * time.Minute,  // Single attempt max duration
	ScheduleToCloseTimeout: 30 * time.Minute, // Total time including retries
	ScheduleToStartTimeout: 10 * time.Minute, // Time waiting in task queue
	HeartbeatTimeout:       2 * time.Minute,  // Between heartbeats
}
ctx = workflow.WithActivityOptions(ctx, ao)
```

- **StartToCloseTimeout**: Max time for a single Activity Task Execution. Prefer this over ScheduleToCloseTimeout.
- **ScheduleToCloseTimeout**: Total time including retries.
- **ScheduleToStartTimeout**: Time an Activity Task can wait in the Task Queue before a Worker picks it up. Rarely needed.
- **HeartbeatTimeout**: Max time between heartbeats. Required for long-running activities to detect failures.

Either `StartToCloseTimeout` or `ScheduleToCloseTimeout` must be set.

## Workflow Failure

Returning any error from a workflow function fails the execution. Return `nil` for success.

**Important Go-specific behavior:** In the Go SDK, returning any error from a workflow fails the workflow execution by default — there is no automatic retry. This differs from other SDKs (Python, TypeScript) where non-`ApplicationError` exceptions cause the workflow task to retry indefinitely. In Go, if you want workflow-level retries, you must explicitly set a `RetryPolicy` on the `StartWorkflowOptions`.

```go
func MyWorkflow(ctx workflow.Context) (string, error) {
	if someCondition {
		return "", temporal.NewApplicationError(
			"Cannot process order",
			"BusinessError",
		)
	}
	return "success", nil
}
```

To prevent workflow retry, return a non-retryable error:

```go
return "", temporal.NewNonRetryableApplicationError(
	"Unrecoverable failure",
	"FatalError",
	nil,
)
```

**Note:** If an activity returns a non-retryable error, the workflow receives an `*temporal.ActivityError` wrapping it. To fail the workflow without retry, wrap it in a new `NewNonRetryableApplicationError`.

## Best Practices

1. Use specific error types for different failure modes
2. Mark permanent failures as non-retryable
3. Set appropriate timeouts; prefer `StartToCloseTimeout` over `ScheduleToCloseTimeout`
4. Let Temporal handle retries via RetryPolicy rather than implementing retry logic yourself
5. Use `errors.As` to unwrap and inspect specific error types
6. Design activities to be idempotent for safe retries (see `references/core/patterns.md`)
