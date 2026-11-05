# Go SDK Advanced Features

## Schedules

Create recurring workflow executions using the Schedule API.

```go
scheduleHandle, err := c.ScheduleClient().Create(ctx, client.ScheduleOptions{
    ID: "daily-report",
    Spec: client.ScheduleSpec{
        CronExpressions: []string{"0 9 * * *"},
    },
    Action: &client.ScheduleWorkflowAction{
        ID:        "daily-report-workflow",
        Workflow:  DailyReportWorkflow,
        TaskQueue: "reports",
    },
})
```

Using intervals instead of cron:

```go
scheduleHandle, err := c.ScheduleClient().Create(ctx, client.ScheduleOptions{
    ID: "hourly-sync",
    Spec: client.ScheduleSpec{
        Intervals: []client.ScheduleIntervalSpec{
            {Every: time.Hour},
        },
    },
    Action: &client.ScheduleWorkflowAction{
        ID:        "hourly-sync-workflow",
        Workflow:  SyncWorkflow,
        TaskQueue: "sync",
    },
})
```

Manage schedules:

```go
handle := c.ScheduleClient().GetHandle(ctx, "daily-report")

// Pause / unpause
handle.Pause(ctx, client.SchedulePauseOptions{Note: "Maintenance window"})
handle.Unpause(ctx, client.ScheduleUnpauseOptions{Note: "Maintenance complete"})

// Trigger immediately
handle.Trigger(ctx, client.ScheduleTriggerOptions{})

// Describe
desc, err := handle.Describe(ctx)

// Delete
handle.Delete(ctx)
```

## Async Activity Completion

For activities that complete asynchronously (e.g., human tasks, external callbacks).
If you configure a heartbeat_timeout on this activity, the external completer is responsible for sending heartbeats via the async handle.
If you do NOT set a heartbeat_timeout, no heartbeats are required.

**Note:** If the external system that completes the asynchronous action can reliably be trusted to do the task and Signal back with the result, and it doesn't need to Heartbeat or receive Cancellation, then consider using **signals** instead.

**Step 1: Return `activity.ErrResultPending` from the activity.**

```go
func RequestApproval(ctx context.Context, requestID string) (string, error) {
    activityInfo := activity.GetInfo(ctx)
    taskToken := activityInfo.TaskToken

    // Store taskToken externally (e.g., database) for later completion
    err := storeTaskToken(requestID, taskToken)
    if err != nil {
        return "", err
    }

    // Signal that this activity will be completed externally
    return "", activity.ErrResultPending
}
```

**Step 2: Complete from another process using the task token.**

```go
temporalClient, err := client.Dial(client.Options{})

// Complete the activity
err = temporalClient.CompleteActivity(ctx, taskToken, "approved", nil)

// Or fail it
err = temporalClient.CompleteActivity(ctx, taskToken, nil, errors.New("rejected"))
```

Or complete by ID (no task token needed):

```go
err = temporalClient.CompleteActivityByID(ctx, namespace, workflowID, runID, activityID, "approved", nil)
```

## Worker Tuning

Configure `worker.Options` for production workloads:

```go
w := worker.New(c, "my-task-queue", worker.Options{
    // Max concurrent activity executions (default: 1000)
    MaxConcurrentActivityExecutionSize: 500,

    // Max concurrent workflow task executions (default: 1000)
    MaxConcurrentWorkflowTaskExecutionSize: 500,

    // Max concurrent activity task pollers (default: 2)
    MaxConcurrentActivityTaskPollers: 4,

    // Max concurrent workflow task pollers (default: 2)
    MaxConcurrentWorkflowTaskPollers: 4,

    // Graceful shutdown timeout (default: 0)
    WorkerStopTimeout: 30 * time.Second,
})
```

Scale pollers based on task queue throughput. If you observe high schedule-to-start latency, increase the number of pollers or add more workers.

## Sessions

Go-specific feature for routing multiple activities to the same worker. All activities using the session context execute on the same worker host.

**Enable on the worker:**

```go
w := worker.New(c, "fileprocessing", worker.Options{
    EnableSessionWorker:               true,
    MaxConcurrentSessionExecutionSize: 100, // default: 1000
})
```

**Use in a workflow:**

```go
func FileProcessingWorkflow(ctx workflow.Context, file FileParam) error {
    ao := workflow.ActivityOptions{
        StartToCloseTimeout: time.Minute,
    }
    ctx = workflow.WithActivityOptions(ctx, ao)

    sessionCtx, err := workflow.CreateSession(ctx, &workflow.SessionOptions{
        CreationTimeout:  time.Minute,
        ExecutionTimeout: 10 * time.Minute,
    })
    if err != nil {
        return err
    }
    defer workflow.CompleteSession(sessionCtx)

    // All three activities run on the same worker
    var downloadResult string
    err = workflow.ExecuteActivity(sessionCtx, DownloadFile, file.URL).Get(sessionCtx, &downloadResult)
    if err != nil {
        return err
    }

    var processResult string
    err = workflow.ExecuteActivity(sessionCtx, ProcessFile, downloadResult).Get(sessionCtx, &processResult)
    if err != nil {
        return err
    }

    err = workflow.ExecuteActivity(sessionCtx, UploadFile, processResult).Get(sessionCtx, nil)
    return err
}
```

Key points:
- `workflow.ErrSessionFailed` is returned if the worker hosting the session dies
- `CompleteSession` releases resources -- always call it (use `defer`)
- Use case: file processing (download, process, upload on same host), GPU workloads, or any pipeline needing local state
- `MaxConcurrentSessionExecutionSize` on `worker.Options` limits how many sessions a single worker can handle

**Limitations:**
- Sessions do not survive worker process restarts — if the worker dies, the session fails and activities must be retried from the workflow level
- There is no server-side support for sessions — the Go SDK implements them entirely client-side using internal task queue routing
- Session concurrency limiting is per-process, not per-host — only one worker process per host if you rely on this

**Relationship to worker-specific task queues:** Sessions are essentially a convenience API over the "worker-specific task queue" pattern, where each worker creates a unique task queue and routes activities to it. For simple cases where you don't need separate activities (e.g., download + process + upload can be one unit), consider using a single long-running activity with heartbeating instead.
