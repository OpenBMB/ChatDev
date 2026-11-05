# Java Gotchas

Java-specific mistakes and anti-patterns. See also [Common Gotchas](../core/gotchas.md) for language-agnostic concepts.

## Non-Deterministic Operations

**Critical: The Java SDK has NO sandbox.** Unlike Python (which uses a sandbox) or TypeScript (which uses V8 isolation), the Java SDK relies entirely on developer conventions. Non-deterministic calls silently succeed during initial execution but cause `NonDeterministicException` on replay.

Forbidden in workflow code — use the Temporal `Workflow.*` equivalents instead:
- `Thread.sleep` → `Workflow.sleep`
- `UUID.randomUUID` → `Workflow.randomUUID`
- `Math.random` → `Workflow.newRandom`
- `System.currentTimeMillis` → `Workflow.currentTimeMillis`
- `new Thread` → `Async.function`
- `synchronized` blocks → unnecessary (workflow code runs under a global lock)

See `references/java/determinism.md` for the full table of forbidden operations, safe alternatives, and detailed examples.

## Wrong Retry Classification

**Example:** Transient networks errors should be retried. Authentication errors should not be.
See `references/java/error-handling.md` to understand how to classify errors.

## Heartbeating

### Forgetting to Heartbeat Long Activities

```java
// BAD - No heartbeat, can't detect stuck activities
@Override
public void processLargeFile(String path) {
    for (String chunk : readChunks(path)) {
        process(chunk); // Takes hours, no heartbeat
    }
}

// GOOD - Regular heartbeats with progress
@Override
public void processLargeFile(String path) {
    int i = 0;
    for (String chunk : readChunks(path)) {
        Activity.getExecutionContext().heartbeat("Processing chunk " + i++);
        process(chunk);
    }
}
```

### Heartbeat Timeout Too Short

```java
// BAD - Heartbeat timeout shorter than processing time
ActivityOptions options = ActivityOptions.newBuilder()
    .setStartToCloseTimeout(Duration.ofMinutes(30))
    .setHeartbeatTimeout(Duration.ofSeconds(10)) // Too short!
    .build();

// GOOD - Heartbeat timeout allows for processing variance
ActivityOptions options = ActivityOptions.newBuilder()
    .setStartToCloseTimeout(Duration.ofMinutes(30))
    .setHeartbeatTimeout(Duration.ofMinutes(2))
    .build();
```

Set heartbeat timeout as high as acceptable for your use case — each heartbeat counts as an action.

## Cancellation

### Not Handling Workflow Cancellation

```java
// BAD - Cleanup doesn't run on cancellation
public class BadWorkflow implements MyWorkflow {
    @Override
    public void run() {
        activities.acquireResource();
        activities.doWork();
        activities.releaseResource(); // Never runs if cancelled!
    }
}
```

```java
// GOOD - Use try/finally with CancellationScope.nonCancellable
import io.temporal.workflow.CancellationScope;
import io.temporal.workflow.Workflow;

public class GoodWorkflow implements MyWorkflow {
    @Override
    public void run() {
        activities.acquireResource();
        try {
            activities.doWork();
        } finally {
            CancellationScope scope = Workflow.newDetachedCancellationScope(
                () -> activities.releaseResource()
            );
            scope.run();
        }
    }
}
```

### Not Handling Activity Cancellation

Activities must **opt in** to receive cancellation. This requires:
1. **Heartbeating** - Cancellation is delivered via heartbeat
2. **Catching CanceledFailure** - Thrown when heartbeat detects cancellation

```java
// BAD - Activity ignores cancellation
@Override
public void longActivity() {
    doExpensiveWork(); // Runs to completion even if cancelled
}
```

```java
// GOOD - Heartbeat and catch cancellation
import io.temporal.activity.Activity;
import io.temporal.failure.CanceledFailure;

@Override
public void longActivity() {
    try {
        for (int i = 0; i < items.size(); i++) {
            Activity.getExecutionContext().heartbeat(i);
            process(items.get(i));
        }
    } catch (CanceledFailure e) {
        cleanup();
        throw e;
    }
}
```

## Testing

### Not Testing Failures

It is important to make sure workflows work as expected under failure paths in addition to happy paths. Please see `references/java/testing.md` for more info.

### Not Testing Replay

Replay tests help you test that you do not have hidden sources of non-determinism bugs in your workflow code, and should be considered in addition to standard testing. This is especially critical in Java since there is no sandbox. Please see `references/java/testing.md` for more info.

## Timers and Sleep

### Using Thread.sleep

```java
// BAD - Thread.sleep is not deterministic during replay
public class BadWorkflow implements MyWorkflow {
    @Override
    public void run() {
        try {
            Thread.sleep(60000); // Non-deterministic!
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}
```

```java
// GOOD - Use Workflow.sleep for deterministic timers
import io.temporal.workflow.Workflow;
import java.time.Duration;

public class GoodWorkflow implements MyWorkflow {
    @Override
    public void run() {
        Workflow.sleep(Duration.ofSeconds(60)); // Deterministic
    }
}
```

**Why this matters:** `Thread.sleep` uses the system clock, which differs between original execution and replay. `Workflow.sleep` creates a durable timer in the event history, ensuring consistent behavior during replay. Unlike Python and TypeScript, there is no sandbox to catch this — the call silently succeeds and only fails on replay.
