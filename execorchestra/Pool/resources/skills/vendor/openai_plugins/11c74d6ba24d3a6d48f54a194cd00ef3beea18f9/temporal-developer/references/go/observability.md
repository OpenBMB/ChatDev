# Go SDK Observability

## Overview

The Go SDK provides replay-safe logging via `workflow.GetLogger`, metrics via the Tally library with Prometheus export, and tracing via OpenTelemetry, OpenTracing, or Datadog.

## Logging / Replay-Aware Logging

### Workflow Logging

Use `workflow.GetLogger(ctx)` for replay-safe logging. This logger automatically suppresses duplicate messages during replay.

```go
func MyWorkflow(ctx workflow.Context, input string) (string, error) {
    logger := workflow.GetLogger(ctx)
    logger.Info("Workflow started", "input", input)

    var result string
    err := workflow.ExecuteActivity(ctx, MyActivity, input).Get(ctx, &result)
    if err != nil {
        logger.Error("Activity failed", "error", err)
        return "", err
    }

    logger.Info("Workflow completed", "result", result)
    return result, nil
}
```

The workflow logger automatically:
- Suppresses duplicate logs during replay
- Includes workflow context (workflow ID, run ID, etc.)

### Activity Logging

Use `activity.GetLogger(ctx)` for context-aware activity logging:

```go
func MyActivity(ctx context.Context, input string) (string, error) {
    logger := activity.GetLogger(ctx)
    logger.Info("Processing input", "input", input)
    // ...
    return "done", nil
}
```

Activity logger includes:
- Activity ID, type, and task queue
- Workflow ID and run ID
- Attempt number (for retries)

### Adding Persistent Fields

Use `log.With` to create a logger with key-value pairs included in every entry:

```go
logger := log.With(workflow.GetLogger(ctx), "orderId", orderId, "customerId", customerId)
logger.Info("Processing order")  // includes orderId and customerId
```

## Customizing the Logger

Set a custom logger via `client.Options{Logger: myLogger}`. Implement the `log.Logger` interface (Debug, Info, Warn, Error methods).

### Using slog (Go 1.21+)

```go
import (
    "log/slog"
    "os"

    tlog "go.temporal.io/sdk/log"
)

slogHandler := slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelDebug})
logger := tlog.NewStructuredLogger(slog.New(slogHandler))

c, err := client.Dial(client.Options{
    Logger: logger,
})
```

### Using Third-Party Loggers (Logrus, Zap, etc.)

Use the [logur](https://github.com/logur/logur) adapter package:

```go
import (
    "github.com/sirupsen/logrus"
    logrusadapter "logur.dev/adapter/logrus"
    "logur.dev/logur"
)

logger := logur.LoggerToKV(logrusadapter.New(logrus.New()))
c, err := client.Dial(client.Options{
    Logger: logger,
})
```

## Metrics

Use the Tally library (`go.temporal.io/sdk/contrib/tally`) with Prometheus:

```go
import (
    sdktally "go.temporal.io/sdk/contrib/tally"
    "github.com/uber-go/tally/v4"
    "github.com/uber-go/tally/v4/prometheus"
)

func newPrometheusScope(c prometheus.Configuration) tally.Scope {
    reporter, err := c.NewReporter(
        prometheus.ConfigurationOptions{},
    )
    if err != nil {
        log.Fatalln("error creating prometheus reporter", err)
    }
    scopeOpts := tally.ScopeOptions{
        CacheReporter:  reporter,
        Separator:      "_",
        SanitizeOptions: &sdktally.PrometheusSanitizeOptions,
    }
    scope, _ := tally.NewRootScope(scopeOpts, time.Second)
    scope = sdktally.NewPrometheusNamingScope(scope)
    return scope
}

c, err := client.Dial(client.Options{
    MetricsHandler: sdktally.NewMetricsHandler(newPrometheusScope(prometheus.Configuration{
        ListenAddress: "0.0.0.0:9090",
        TimerType:     "histogram",
    })),
})
```

Key SDK metrics:
- `temporal_workflow_task_execution_latency` -- Workflow task processing time
- `temporal_activity_execution_latency` -- Activity execution time
- `temporal_workflow_task_replay_latency` -- Replay duration
- `temporal_request` -- Client requests to server
- `temporal_activity_schedule_to_start_latency` -- Time from scheduling to start

## Search Attributes (Visibility)

See the Search Attributes section of `references/go/data-handling.md`

## Best Practices

1. Always use `workflow.GetLogger(ctx)` in workflows -- never `fmt.Println` or `log.Println` (they produce duplicates on replay)
2. Use `activity.GetLogger(ctx)` in activities for structured context
3. Set up Prometheus metrics in production
4. Use search attributes for operational visibility and debugging
5. Use `workflow.IsReplaying(ctx)` only for custom side-effect-free logging -- the built-in logger handles replay suppression automatically
