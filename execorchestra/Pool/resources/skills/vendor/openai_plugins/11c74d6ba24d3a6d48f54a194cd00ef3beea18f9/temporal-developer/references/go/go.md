# Temporal Go SDK Reference

## Overview

The Temporal Go SDK (`go.temporal.io/sdk`) provides a strongly-typed, idiomatic Go approach to building durable workflows. Workflows are regular exported Go functions.

## Quick Start

**Add Dependency:** In your Go module, add the Temporal SDK:
```bash
go get go.temporal.io/sdk
```

**workflows/greeting.go** - Workflow definition:
```go
package workflows

import (
	"time"

	"go.temporal.io/sdk/workflow"
)

func GreetingWorkflow(ctx workflow.Context, name string) (string, error) {
	ao := workflow.ActivityOptions{
		StartToCloseTimeout: time.Minute,
	}
	ctx = workflow.WithActivityOptions(ctx, ao)

	var result string
	err := workflow.ExecuteActivity(ctx, "Greet", name).Get(ctx, &result)
	if err != nil {
		return "", err
	}
	return result, nil
}
```

**activities/greet.go** - Activity definition:
```go
package activities

import (
	"context"
	"fmt"
)

type Activities struct{}

func (a *Activities) Greet(ctx context.Context, name string) (string, error) {
	return fmt.Sprintf("Hello, %s!", name), nil
}
```

**worker/main.go** - Worker setup:
```go
package main

import (
	"log"

	"yourmodule/activities"
	"yourmodule/workflows"

	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/worker"
)

func main() {
	c, err := client.Dial(client.Options{})
	if err != nil {
		log.Fatalln("Unable to create client", err)
	}
	defer c.Close()

	w := worker.New(c, "my-task-queue", worker.Options{})

	w.RegisterWorkflow(workflows.GreetingWorkflow)
	w.RegisterActivity(&activities.Activities{})

	err = w.Run(worker.InterruptCh())
	if err != nil {
		log.Fatalln("Unable to start worker", err)
	}
}
```

**Start the dev server:** Start `temporal server start-dev` in the background.

**Start the worker:** Run `go run worker/main.go` in the background.

**starter/main.go** - Start a workflow execution:
```go
package main

import (
	"context"
	"fmt"
	"log"

	"yourmodule/workflows"

	"github.com/google/uuid"
	"go.temporal.io/sdk/client"
)

func main() {
	c, err := client.Dial(client.Options{})
	if err != nil {
		log.Fatalln("Unable to create client", err)
	}
	defer c.Close()

	options := client.StartWorkflowOptions{
		ID:        uuid.NewString(),
		TaskQueue: "my-task-queue",
	}

	we, err := c.ExecuteWorkflow(context.Background(), options, workflows.GreetingWorkflow, "my name")
	if err != nil {
		log.Fatalln("Unable to execute workflow", err)
	}

	var result string
	err = we.Get(context.Background(), &result)
	if err != nil {
		log.Fatalln("Unable to get workflow result", err)
	}

	fmt.Println("Result:", result)
}
```

**Run the workflow:** Run `go run starter/main.go`. Should output: `Result: Hello, my name!`.

## Key Concepts

### Workflow Definition
- Exported function with `workflow.Context` as the first parameter
- Returns `(ResultType, error)` or just `error`
- Signature: `func MyWorkflow(ctx workflow.Context, input MyInput) (MyOutput, error)`
- Use `workflow.SetQueryHandler()`, `workflow.SetUpdateHandler()` for handlers
- Register with `w.RegisterWorkflow(MyWorkflow)`

### Activity Definition
- Regular function or struct methods with `context.Context` as the first parameter
- Struct methods are preferred for dependency injection
- Signature: `func (a *Activities) MyActivity(ctx context.Context, input string) (string, error)`
- Register struct with `w.RegisterActivity(&Activities{})` (registers all exported methods)

### Worker Setup
- Create client with `client.Dial(client.Options{})`
- Create worker with `worker.New(c, "task-queue", worker.Options{})`
- Register workflows and activities
- Run with `w.Run(worker.InterruptCh())`

### Determinism

**Workflow code must be deterministic!** The Go SDK has no sandbox -- determinism is enforced by convention and tooling.

Use Temporal replacements instead of native Go constructs:
- `workflow.Go()` instead of `go` (goroutines)
- `workflow.Channel` instead of `chan`
- `workflow.Selector` instead of `select`
- `workflow.Sleep()` instead of `time.Sleep()`
- `workflow.Now()` instead of `time.Now()`
- `workflow.GetLogger()` instead of `log` / `fmt.Println` for replay-safe logging

Use the **`workflowcheck`** static analysis tool to catch non-deterministic code:
```bash
go install go.temporal.io/sdk/contrib/tools/workflowcheck@latest
workflowcheck ./...
```

Read `references/core/determinism.md` and `references/go/determinism.md` to understand more.

## File Organization Best Practice

**Use separate packages for workflows, activities, and worker.** Activities as struct methods enable dependency injection at the worker level.

```
myapp/
├── workflows/
│   └── greeting.go      # Only Workflow functions
├── activities/
│   └── greet.go          # Activity struct and methods
├── worker/
│   └── main.go           # Worker setup, imports both
└── starter/
    └── main.go           # Client code to start workflows
```

**Activities as struct methods for dependency injection:**
```go
// activities/greet.go
type Activities struct {
    HTTPClient *http.Client
    DB         *sql.DB
}

func (a *Activities) FetchData(ctx context.Context, url string) (string, error) {
    // Use a.HTTPClient, a.DB, etc.
}
```

```go
// worker/main.go - inject dependencies at worker startup
activities := &activities.Activities{
    HTTPClient: http.DefaultClient,
    DB:         db,
}
w.RegisterActivity(activities)
```

## Common Pitfalls

1. **Using native goroutines/channels/select** - Use `workflow.Go()`, `workflow.Channel`, `workflow.Selector`
2. **Using `time.Sleep` or `time.Now`** - Use `workflow.Sleep()` and `workflow.Now()`
3. **Iterating over maps with `range`** - Map iteration order is non-deterministic; sort keys first
4. **Forgetting to register workflows/activities** - Worker will fail tasks for unregistered types
5. **Registering activity functions instead of struct** - Use `w.RegisterActivity(&Activities{})` not `w.RegisterActivity(a.MyMethod)`
6. **Forgetting to heartbeat** - Long-running activities need `activity.RecordHeartbeat(ctx, details)`
7. **Using `fmt.Println` in workflows** - Use `workflow.GetLogger(ctx)` for replay-safe logging
8. **Not setting Activity timeouts** - `StartToCloseTimeout` or `ScheduleToCloseTimeout` is required in `ActivityOptions`

## Writing Tests

See `references/go/testing.md` for info on writing tests.

## Additional Resources

### Reference Files
- **`references/go/patterns.md`** - Signals, queries, child workflows, saga pattern, etc.
- **`references/go/determinism.md`** - Determinism rules, workflowcheck tool, safe alternatives
- **`references/go/gotchas.md`** - Go-specific mistakes and anti-patterns
- **`references/go/error-handling.md`** - ApplicationError, retry policies, non-retryable errors
- **`references/go/observability.md`** - Logging, metrics, tracing, Search Attributes
- **`references/go/testing.md`** - TestWorkflowEnvironment, time-skipping, activity mocking
- **`references/go/advanced-features.md`** - Schedules, worker tuning, and more
- **`references/go/data-handling.md`** - Data converters, payload codecs, encryption
- **`references/go/versioning.md`** - Patching API (`workflow.GetVersion`), Worker Versioning
- **`references/go/determinism-protection.md`** - Information on **`workflowcheck`** tool to help statically check for determinism issues.
