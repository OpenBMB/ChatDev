# Temporal Java SDK Reference

## Overview

The Temporal Java SDK (`io.temporal:temporal-sdk`) uses an interface + implementation pattern for both Workflows and Activities. Java 8+ required; Java 21+ strongly recommended for virtual thread support.

## Quick Start

**Add Dependencies:**

Gradle:
```groovy
implementation 'io.temporal:temporal-sdk:1.+'
```

Maven:
```xml
<dependency>
    <groupId>io.temporal</groupId>
    <artifactId>temporal-sdk</artifactId>
    <version>[1.0,)</version>
</dependency>
```

**GreetActivities.java** - Activity interface:
```java
package greetingapp;

import io.temporal.activity.ActivityInterface;
import io.temporal.activity.ActivityMethod;

@ActivityInterface
public interface GreetActivities {

    @ActivityMethod
    String greet(String name);
}
```

**GreetActivitiesImpl.java** - Activity implementation:
```java
package greetingapp;

public class GreetActivitiesImpl implements GreetActivities {

    @Override
    public String greet(String name) {
        return "Hello, " + name + "!";
    }
}
```

**GreetingWorkflow.java** - Workflow interface:
```java
package greetingapp;

import io.temporal.workflow.WorkflowInterface;
import io.temporal.workflow.WorkflowMethod;

@WorkflowInterface
public interface GreetingWorkflow {

    @WorkflowMethod
    String greet(String name);
}
```

**GreetingWorkflowImpl.java** - Workflow implementation:
```java
package greetingapp;

import io.temporal.activity.ActivityOptions;
import io.temporal.workflow.Workflow;

import java.time.Duration;

public class GreetingWorkflowImpl implements GreetingWorkflow {

    private final GreetActivities activities = Workflow.newActivityStub(
        GreetActivities.class,
        ActivityOptions.newBuilder()
            .setStartToCloseTimeout(Duration.ofSeconds(30))
            .build()
    );

    @Override
    public String greet(String name) {
        return activities.greet(name);
    }
}
```

**GreetingWorker.java** - Worker setup:
```java
package greetingapp;

import io.temporal.client.WorkflowClient;
import io.temporal.serviceclient.WorkflowServiceStubs;
import io.temporal.worker.Worker;
import io.temporal.worker.WorkerFactory;

public class GreetingWorker {

    public static void main(String[] args) {
        // Create gRPC stubs for local dev server (localhost:7233)
        WorkflowServiceStubs service = WorkflowServiceStubs.newLocalServiceStubs();

        // Create client
        WorkflowClient client = WorkflowClient.newInstance(service);

        // Create factory and worker
        WorkerFactory factory = WorkerFactory.newInstance(client);
        Worker worker = factory.newWorker("greeting-queue");

        // Register workflow and activity implementations
        worker.registerWorkflowImplementationTypes(GreetingWorkflowImpl.class);
        worker.registerActivitiesImplementations(new GreetActivitiesImpl());

        // Start polling
        factory.start();
    }
}
```

**Start the dev server:** Start `temporal server start-dev` in the background.

**Start the worker:** Run `GreetingWorker.main()` (e.g., `./gradlew run` or `mvn compile exec:java -Dexec.mainClass="greetingapp.GreetingWorker"`).

**Starter.java** - Start a workflow execution:
```java
package greetingapp;

import io.temporal.client.WorkflowClient;
import io.temporal.client.WorkflowOptions;
import io.temporal.serviceclient.WorkflowServiceStubs;

import java.util.UUID;

public class Starter {

    public static void main(String[] args) {
        WorkflowServiceStubs service = WorkflowServiceStubs.newLocalServiceStubs();
        WorkflowClient client = WorkflowClient.newInstance(service);

        GreetingWorkflow workflow = client.newWorkflowStub(
            GreetingWorkflow.class,
            WorkflowOptions.newBuilder()
                .setWorkflowId(UUID.randomUUID().toString())
                .setTaskQueue("greeting-queue")
                .build()
        );

        String result = workflow.greet("my name");
        System.out.println("Result: " + result);
    }
}
```

**Run the workflow:** Run `Starter.main()`. Should output: `Result: Hello, my name!`.

## Key Concepts

### Workflow Definition
- Annotate interface with `@WorkflowInterface`
- Put any state initialization logic in the workflow constructor to guarantee that it happens before signals/updates arrive. If your state initialization logic requires the workflow parameters, then add the `@WorkflowInit` decorator and parameters to your constructor.
- Annotate entry point method with `@WorkflowMethod` (exactly one per interface)
- Use `@SignalMethod` for signal handlers
- Use `@QueryMethod` for query handlers
- Use `@UpdateMethod` for update handlers
- Implementation class implements the interface

### Activity Definition
- Annotate interface with `@ActivityInterface`
- Optionally annotate methods with `@ActivityMethod` (for custom names)
- Implementation class can throw any exception
- Call from workflow via `Workflow.newActivityStub()`

### Worker Setup
- `WorkflowServiceStubs` -- gRPC connection to Temporal Server
- `WorkflowClient` -- client used by worker to communicate with server
- `WorkerFactory` -- creates Worker instances
- `Worker` -- polls a single Task Queue, register workflows and activities on it
- Call `factory.start()` to begin polling

## File Organization Best Practice

**Keep Workflow and Activity definitions in separate files.** Separating them is good practice for clarity and maintainability.

```
greetingapp/
├── GreetActivities.java        # Activity interface
├── GreetActivitiesImpl.java    # Activity implementation
├── GreetingWorkflow.java       # Workflow interface
├── GreetingWorkflowImpl.java   # Workflow implementation
├── GreetingWorker.java         # Worker setup
└── Starter.java                # Client code to start workflows
```

## Determinism Rules

The Java SDK has **no sandbox**. The developer is fully responsible for writing deterministic workflow code. All non-deterministic operations must happen in Activities.

**Do not use in workflow code:**
- `Thread` / `new Thread()` -- use `Workflow.newTimer()` or `Async.function()`
- `synchronized` / `Lock` -- workflow code is single-threaded
- `UUID.randomUUID()` -- use `Workflow.randomUUID()`
- `Math.random()` -- use `Workflow.newRandom()`
- `System.currentTimeMillis()` / `Instant.now()` -- use `Workflow.currentTimeMillis()`
- File I/O, network calls, database access -- use Activities
- `Thread.sleep()` -- use `Workflow.sleep()`
- Mutable static fields -- workflow instances must not share state

**Use Workflow.* APIs instead:**
- `Workflow.sleep()` for timers
- `Workflow.currentTimeMillis()` for current time
- `Workflow.randomUUID()` for UUIDs
- `Workflow.newRandom()` for random numbers
- `Workflow.getLogger()` for replay-safe logging

See `references/core/determinism.md` for detailed determinism rules.

## Common Pitfalls

1. **Non-deterministic code in workflows** - Use `Workflow.*` APIs instead of standard Java APIs; perform I/O in Activities
2. **Forgetting `@WorkflowInterface` or `@ActivityInterface`** - Annotations are required on interfaces for registration
3. **Multiple `@WorkflowMethod` on one interface** - Only one `@WorkflowMethod` is allowed per `@WorkflowInterface`
4. **Using `Thread.sleep()` in workflows** - Use `Workflow.sleep()` for deterministic timers
5. **Forgetting to heartbeat** - Long-running activities need `Activity.getExecutionContext().heartbeat()`
6. **Using `System.out.println()` in workflows** - Use `Workflow.getLogger()` for replay-safe logging
7. **Not registering activities as instances** - `registerActivitiesImplementations()` takes object instances (`new MyActivitiesImpl()`), not classes
8. **Blocking the workflow thread** - Never perform I/O or long computations in workflow code; use Activities
9. **Sharing mutable state between workflow instances** - Each workflow execution must be independent

## Writing Tests

See `references/java/testing.md` for info on writing tests.

## Additional Resources

### Reference Files
- **`references/java/patterns.md`** - Signals, queries, child workflows, saga pattern, etc.
- **`references/java/determinism.md`** - Determinism rules and safe alternatives for Java
- **`references/java/gotchas.md`** - Java-specific mistakes and anti-patterns
- **`references/java/error-handling.md`** - ApplicationFailure, retry policies, non-retryable errors
- **`references/java/observability.md`** - Logging, metrics, tracing, Search Attributes
- **`references/java/testing.md`** - TestWorkflowEnvironment, time-skipping, activity mocking
- **`references/java/advanced-features.md`** - Schedules, worker tuning, and more
- **`references/java/data-handling.md`** - Data converters, Jackson, payload encryption
- **`references/java/versioning.md`** - Patching API, workflow type versioning, Worker Versioning
