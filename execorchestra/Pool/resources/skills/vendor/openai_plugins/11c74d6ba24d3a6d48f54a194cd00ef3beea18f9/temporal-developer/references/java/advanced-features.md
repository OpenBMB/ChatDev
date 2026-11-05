# Java SDK Advanced Features

## Schedules

Create recurring workflow executions.

```java
import io.temporal.client.schedules.*;

ScheduleClient scheduleClient = ScheduleClient.newInstance(service);

// Create a schedule
String scheduleId = "daily-report";
ScheduleHandle handle = scheduleClient.createSchedule(
    scheduleId,
    Schedule.newBuilder()
        .setAction(
            ScheduleActionStartWorkflow.newBuilder()
                .setWorkflowType(DailyReportWorkflow.class)
                .setOptions(
                    WorkflowOptions.newBuilder()
                        .setWorkflowId("daily-report")
                        .setTaskQueue("reports")
                        .build()
                )
                .build()
        )
        .setSpec(
            ScheduleSpec.newBuilder()
                .setIntervals(
                    List.of(new ScheduleIntervalSpec(Duration.ofDays(1)))
                )
                .build()
        )
        .build(),
    ScheduleOptions.newBuilder().build()
);

// Manage schedules
ScheduleHandle scheduleHandle = scheduleClient.getHandle(scheduleId);
scheduleHandle.pause("Maintenance window");
scheduleHandle.unpause();
scheduleHandle.trigger();  // Run immediately
scheduleHandle.delete();
```

## Async Activity Completion

For activities that complete asynchronously (e.g., human tasks, external callbacks).
If you configure a heartbeat timeout on this activity, the external completer is responsible for sending heartbeats via the async handle.

**Note:** If the external system can reliably Signal back with the result and doesn't need to Heartbeat or receive Cancellation, consider using **signals** instead.

```java
public class ApprovalActivitiesImpl implements ApprovalActivities {
    @Override
    public String requestApproval(String requestId) {
        ActivityExecutionContext ctx = Activity.getExecutionContext();

        // Get task token for async completion
        byte[] taskToken = ctx.getTaskToken();

        // Store task token for later completion (e.g., in database)
        storeTaskToken(requestId, taskToken);

        // Mark this activity as waiting for external completion
        ctx.doNotCompleteOnReturn();

        return null; // Return value is ignored
    }
}

// Later, complete the activity from another process
public void completeApproval(String requestId, boolean approved) {
    WorkflowServiceStubs service = WorkflowServiceStubs.newLocalServiceStubs();
    WorkflowClient client = WorkflowClient.newInstance(service);

    ActivityCompletionClient completionClient = client.newActivityCompletionClient();

    byte[] taskToken = getTaskToken(requestId);

    if (approved) {
        completionClient.complete(taskToken, "approved");
    } else {
        completionClient.completeExceptionally(
            taskToken,
            new RuntimeException("Rejected")
        );
    }
}
```

## Worker Tuning

Configure worker performance settings.

```java
WorkerOptions workerOptions = WorkerOptions.newBuilder()
    // Max concurrent workflow task executions (default: 200)
    .setMaxConcurrentWorkflowTaskExecutionSize(200)
    // Max concurrent activity executions (default: 200)
    .setMaxConcurrentActivityExecutionSize(200)
    // Max concurrent local activity executions (default: 200)
    .setMaxConcurrentLocalActivityExecutionSize(200)
    // Max workflow task pollers (default: 5)
    .setMaxConcurrentWorkflowTaskPollers(5)
    // Max activity task pollers (default: 5)
    .setMaxConcurrentActivityTaskPollers(5)
    .build();

WorkerFactory factory = WorkerFactory.newInstance(client);
Worker worker = factory.newWorker("my-queue", workerOptions);
worker.registerWorkflowImplementationTypes(MyWorkflowImpl.class);
worker.registerActivitiesImplementations(new MyActivitiesImpl());
factory.start();
```

## Workflow Failure Exception Types

Control which exceptions cause workflow failures vs workflow task failures.

By default, only `ApplicationFailure` (and its subclasses) fail the workflow execution. All other exceptions fail the **workflow task**, causing the task to retry indefinitely until the code is fixed or the workflow is terminated.

### Per-Workflow Configuration

Use `WorkflowImplementationOptions` to specify which exception types should fail the workflow:

```java
Worker worker = factory.newWorker("my-queue");
worker.registerWorkflowImplementationTypes(
    WorkflowImplementationOptions.newBuilder()
        .setFailWorkflowExceptionTypes(
            IllegalArgumentException.class,
            CustomBusinessException.class
        )
        .build(),
    MyWorkflowImpl.class
);
```

With this configuration, `IllegalArgumentException` and `CustomBusinessException` thrown from the workflow will fail the workflow execution instead of just the workflow task.

### Worker-Level Configuration

Apply to all workflows registered on the worker:

```java
WorkerFactoryOptions factoryOptions = WorkerFactoryOptions.newBuilder()
    .setWorkflowHostLocalTaskQueueScheduleToStartTimeout(Duration.ofSeconds(10))
    .build();
WorkerFactory factory = WorkerFactory.newInstance(client, factoryOptions);

Worker worker = factory.newWorker("my-queue");
// Register each workflow type with its own failure exception types
worker.registerWorkflowImplementationTypes(
    WorkflowImplementationOptions.newBuilder()
        .setFailWorkflowExceptionTypes(
            IllegalArgumentException.class,
            CustomBusinessException.class
        )
        .build(),
    MyWorkflowImpl.class,
    AnotherWorkflowImpl.class
);
```

- **Tip for testing:** Set `setFailWorkflowExceptionTypes(Throwable.class)` so any unhandled exception fails the workflow immediately rather than retrying the workflow task forever. This surfaces bugs faster.
