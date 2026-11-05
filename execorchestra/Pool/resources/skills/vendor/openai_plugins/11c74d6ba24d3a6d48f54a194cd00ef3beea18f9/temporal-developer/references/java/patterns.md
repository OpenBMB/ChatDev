# Java SDK Patterns

## Signals

```java
@WorkflowInterface
public interface OrderWorkflow {
    @WorkflowMethod
    String run();

    @SignalMethod
    void approve();

    @SignalMethod
    void addItem(String item);
}

public class OrderWorkflowImpl implements OrderWorkflow {
    private boolean approved = false;
    private final List<String> items = new ArrayList<>();

    @Override
    public void approve() {
        this.approved = true;
    }

    @Override
    public void addItem(String item) {
        this.items.add(item);
    }

    @Override
    public String run() {
        Workflow.await(() -> this.approved);
        return "Processed " + this.items.size() + " items";
    }
}
```

### Dynamic Signal Handlers

For handling signals with names not known at compile time. Use cases for this pattern are rare — most workflows should use statically defined signal handlers.

```java
public class DynamicSignalWorkflowImpl implements DynamicSignalWorkflow {
    private final Map<String, List<String>> signals = new HashMap<>();

    @Override
    public String run() {
        Workflow.registerListener(
            (DynamicSignalHandler) (signalName, encodedArgs) -> {
                signals.computeIfAbsent(signalName, k -> new ArrayList<>())
                    .add(encodedArgs.get(0, String.class));
            });
        // ... workflow logic ...
    }
}
```

## Queries

**Important:** Queries must NOT modify workflow state or have side effects.

```java
@WorkflowInterface
public interface StatusWorkflow {
    @WorkflowMethod
    String run();

    @QueryMethod
    String getStatus();

    @QueryMethod
    int getProgress();
}

public class StatusWorkflowImpl implements StatusWorkflow {
    private String status = "pending";
    private int progress = 0;

    @Override
    public String getStatus() {
        return this.status;
    }

    @Override
    public int getProgress() {
        return this.progress;
    }

    @Override
    public String run() {
        MyActivities activities = Workflow.newActivityStub(
            MyActivities.class,
            ActivityOptions.newBuilder()
                .setStartToCloseTimeout(Duration.ofMinutes(1))
                .build());

        this.status = "running";
        for (int i = 0; i < 100; i++) {
            this.progress = i;
            activities.processItem(i);
        }
        this.status = "completed";
        return "done";
    }
}
```

### Dynamic Query Handlers

For handling queries with names not known at compile time. Use cases for this pattern are rare — most workflows should use statically defined query handlers.

```java
Workflow.registerListener(
    (DynamicQueryHandler) (queryName, encodedArgs) -> {
        if (queryName.equals("getField")) {
            String fieldName = encodedArgs.get(0, String.class);
            return fields.get(fieldName);
        }
        return null;
    });
```

## Updates

```java
@WorkflowInterface
public interface OrderWorkflow {
    @WorkflowMethod
    String run();

    @UpdateMethod
    int addItem(String item);

    @UpdateValidatorMethod(updateName = "addItem")
    void validateAddItem(String item);
}

public class OrderWorkflowImpl implements OrderWorkflow {
    private final List<String> items = new ArrayList<>();

    @Override
    public int addItem(String item) {
        this.items.add(item);
        return this.items.size(); // Returns new count to caller
    }

    @Override
    public void validateAddItem(String item) {
        if (item == null || item.isEmpty()) {
            throw new IllegalArgumentException("Item cannot be empty");
        }
        if (this.items.size() >= 100) {
            throw new IllegalArgumentException("Order is full");
        }
    }

    // ... run() ...
}
```

**Important:** Validators must NOT mutate workflow state or do anything blocking (no activities, sleeps, or other commands). They are read-only, similar to query handlers. Throw an exception to reject the update; return normally to accept.

## Child Workflows

```java
public class MyWorkflowImpl implements MyWorkflow {
    @Override
    public List<String> run(List<Order> orders) {
        List<String> results = new ArrayList<>();
        for (Order order : orders) {
            ProcessOrderWorkflow child = Workflow.newChildWorkflowStub(
                ProcessOrderWorkflow.class,
                ChildWorkflowOptions.newBuilder()
                    .setWorkflowId("order-" + order.getId())
                    .build());
            results.add(child.run(order));
        }
        return results;
    }
}
```

## Child Workflow Options

```java
ChildWorkflowOptions options = ChildWorkflowOptions.newBuilder()
    .setWorkflowId("child-workflow-id")
    // Control what happens to child when parent closes
    .setParentClosePolicy(ParentClosePolicy.PARENT_CLOSE_POLICY_ABANDON)
    // Control what happens to child when parent is cancelled
    .setCancellationType(ChildWorkflowCancellationType.WAIT_CANCELLATION_COMPLETED)
    .setWorkflowExecutionTimeout(Duration.ofMinutes(10))
    .build();

ProcessOrderWorkflow child = Workflow.newChildWorkflowStub(
    ProcessOrderWorkflow.class, options);
```

## Handles to External Workflows

```java
public class MyWorkflowImpl implements MyWorkflow {
    @Override
    public void run(String targetWorkflowId) {
        // Get handle to external workflow
        TargetWorkflow external = Workflow.newExternalWorkflowStub(
            TargetWorkflow.class, targetWorkflowId);

        // Signal the external workflow
        external.dataReady(dataPayload);

        // Or cancel it using untyped stub
        ExternalWorkflowStub untypedExternal =
            Workflow.newUntypedExternalWorkflowStub(targetWorkflowId);
        untypedExternal.cancel();
    }
}
```

## Parallel Execution

```java
public class MyWorkflowImpl implements MyWorkflow {
    @Override
    public List<String> run(List<String> items) {
        MyActivities activities = Workflow.newActivityStub(
            MyActivities.class,
            ActivityOptions.newBuilder()
                .setStartToCloseTimeout(Duration.ofMinutes(5))
                .build());

        // Execute activities in parallel
        List<Promise<String>> promises = new ArrayList<>();
        for (String item : items) {
            promises.add(Async.function(activities::processItem, item));
        }

        // Wait for all to complete
        Promise.allOf(promises).get();

        // Collect results
        List<String> results = new ArrayList<>();
        for (Promise<String> promise : promises) {
            results.add(promise.get());
        }
        return results;
    }
}
```

## Continue-as-New

```java
public class MyWorkflowImpl implements MyWorkflow {
    @Override
    public String run(WorkflowState state) {
        while (true) {
            state = processBatch(state);

            if (state.isComplete()) {
                return "done";
            }

            // Continue with fresh history before hitting limits
            if (Workflow.getInfo().isContinueAsNewSuggested()) {
                Workflow.continueAsNew(state);
            }
        }
    }
}
```

## Saga Pattern (Compensations)

**Important:** Compensation activities should be idempotent — they may be retried (as with ALL activities).

```java
public class MyWorkflowImpl implements MyWorkflow {
    @Override
    public String run(Order order) {
        MyActivities activities = Workflow.newActivityStub(
            MyActivities.class,
            ActivityOptions.newBuilder()
                .setStartToCloseTimeout(Duration.ofMinutes(5))
                .build());

        List<Runnable> compensations = new ArrayList<>();

        try {
            // Note - we save the compensation BEFORE running the activity,
            // because the following could happen:
            // 1. reserveInventory starts running
            // 2. it does successfully reserve inventory
            // 3. but then fails for some other reason (timeout, reporting metrics, etc.)
            // 4. in that case, the activity would have failed, but the effect still happened
            // So, the compensation needs to handle both reserved and unreserved states.
            compensations.add(() -> activities.releaseInventoryIfReserved(order));
            activities.reserveInventory(order);

            compensations.add(() -> activities.refundPaymentIfCharged(order));
            activities.chargePayment(order);

            activities.shipOrder(order);

            return "Order completed";

        } catch (Exception e) {
            Workflow.getLogger(MyWorkflowImpl.class)
                .error("Order failed, running compensations", e);
            // Use a detached cancellation scope so compensations run even if
            // the workflow itself was cancelled.
            CancellationScope compensationScope = Workflow.newDetachedCancellationScope(() -> {
                Collections.reverse(compensations);
                for (Runnable compensate : compensations) {
                    try {
                        compensate.run();
                    } catch (Exception compErr) {
                        Workflow.getLogger(MyWorkflowImpl.class)
                            .error("Compensation failed", compErr);
                    }
                }
            });
            compensationScope.run();
            throw Workflow.wrap(e);
        }
    }
}
```

## Cancellation Scopes

```java
public class MyWorkflowImpl implements MyWorkflow {
    @Override
    public String run() {
        try {
            MyActivities activities = Workflow.newActivityStub(
                MyActivities.class,
                ActivityOptions.newBuilder()
                    .setStartToCloseTimeout(Duration.ofHours(1))
                    .build());

            activities.longRunningActivity();
            return "completed";

        } catch (CanceledFailure e) {
            // Workflow was cancelled - perform cleanup
            Workflow.getLogger(MyWorkflowImpl.class)
                .info("Workflow cancelled, running cleanup");

            // Use nonCancellable scope so cleanup activities still run
            CancellationScope cleanupScope = Workflow.newDetachedCancellationScope(
                () -> {
                    MyActivities activities = Workflow.newActivityStub(
                        MyActivities.class,
                        ActivityOptions.newBuilder()
                            .setStartToCloseTimeout(Duration.ofMinutes(5))
                            .build());
                    activities.cleanupActivity();
                });
            cleanupScope.run();
            throw e; // Re-throw to mark workflow as cancelled
        }
    }
}
```

Timeout scope:

```java
CancellationScope timeoutScope = Workflow.newCancellationScope(
    () -> {
        // This scope will be cancelled after 30 minutes
        activities.longRunningActivity();
    });
timeoutScope.run();
// Cancel after timeout
Workflow.newTimer(Duration.ofMinutes(30)).thenApply(r -> {
    timeoutScope.cancel();
    return null;
});
```

## Wait Condition with Timeout

```java
public class MyWorkflowImpl implements MyWorkflow {
    private boolean approved = false;

    @Override
    public String run() {
        // Wait for approval with 24-hour timeout
        boolean received = Workflow.await(Duration.ofHours(24), () -> this.approved);
        if (received) {
            return "approved";
        }
        return "auto-rejected due to timeout";
    }
}
```

## Waiting for All Handlers to Finish

Signal and update handlers should generally be non-async (avoid running activities from them). Otherwise, the workflow may complete before handlers finish their execution. However, making handlers non-async sometimes requires workarounds that add complexity.

When handlers do run async operations, call `Workflow.await(() -> Workflow.isEveryHandlerFinished())` at the end of your workflow (or before continue-as-new) to prevent completion until all pending handlers complete.

```java
public class MyWorkflowImpl implements MyWorkflow {
    @Override
    public String run() {
        // ... main workflow logic ...

        // Before exiting, wait for all handlers to finish
        Workflow.await(() -> Workflow.isEveryHandlerFinished());
        return "done";
    }
}
```

## Activity Heartbeat Details

### WHY:
- **Support activity cancellation** — Cancellations are delivered via heartbeat; activities that don't heartbeat won't know they've been cancelled
- **Resume progress after worker failure** — Heartbeat details persist across retries

### WHEN:
- **Cancellable activities** — Any activity that should respond to cancellation
- **Long-running activities** — Track progress for resumability
- **Checkpointing** — Save progress periodically

```java
@ActivityInterface
public interface MyActivities {
    @ActivityMethod
    String processLargeFile(String filePath);
}

public class MyActivitiesImpl implements MyActivities {
    @Override
    public String processLargeFile(String filePath) {
        ActivityExecutionContext ctx = Activity.getExecutionContext();

        // Get heartbeat details from previous attempt (if any)
        Optional<Integer> lastLine = ctx.getHeartbeatDetails(Integer.class);
        int startLine = lastLine.orElse(0);

        try {
            List<String> lines = readFile(filePath);
            for (int i = startLine; i < lines.size(); i++) {
                processLine(lines.get(i));

                // Heartbeat with progress
                // If cancelled, heartbeat() throws CanceledFailure
                ctx.heartbeat(i + 1);
            }
            return "completed";
        } catch (ActivityCompletionException e) {
            // CanceledFailure extends ActivityCompletionException
            cleanup();
            throw e;
        }
    }
}
```

Set `heartbeatTimeout` in `ActivityOptions` to enable heartbeat-based failure detection:

```java
ActivityOptions options = ActivityOptions.newBuilder()
    .setStartToCloseTimeout(Duration.ofHours(1))
    .setHeartbeatTimeout(Duration.ofSeconds(30))
    .build();
```

## Timers

```java
public class MyWorkflowImpl implements MyWorkflow {
    @Override
    public String run() {
        Workflow.sleep(Duration.ofHours(1));

        return "Timer fired";
    }
}
```

## Local Activities

**Purpose**: Reduce latency for short, lightweight operations by skipping the task queue. ONLY use these when necessary for performance. Do NOT use these by default, as they are not durable and distributed.

```java
public class MyWorkflowImpl implements MyWorkflow {
    @Override
    public String run() {
        MyActivities localActivities = Workflow.newLocalActivityStub(
            MyActivities.class,
            LocalActivityOptions.newBuilder()
                .setStartToCloseTimeout(Duration.ofSeconds(5))
                .build());

        String result = localActivities.quickLookup("key");
        return result;
    }
}
```
