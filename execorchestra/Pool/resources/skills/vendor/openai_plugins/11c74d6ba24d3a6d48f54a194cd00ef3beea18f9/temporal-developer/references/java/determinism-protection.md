# Java Determinism Protection

## Overview

The Java SDK has **no sandbox** (only Python and TypeScript have sandboxing). Java relies on developer conventions and runtime replay detection to enforce determinism. A static analysis tool (`temporal-workflowcheck`) is available in beta.

## Forbidden Operations

```java
// BAD: Non-deterministic operations in workflow code
Thread.sleep(1000);
UUID id = UUID.randomUUID();
double val = Math.random();
long now = System.currentTimeMillis();
new Thread(() -> doWork()).start();
CompletableFuture.supplyAsync(() -> compute());

// GOOD: Deterministic Workflow.* alternatives
Workflow.sleep(Duration.ofSeconds(1));
String id = Workflow.randomUUID().toString();
int val = Workflow.newRandom().nextInt();
long now = Workflow.currentTimeMillis();
Promise<Void> promise = Async.procedure(() -> doWork());
CompletablePromise<String> promise = Workflow.newPromise();
```

## Static Analysis with `temporal-workflowcheck`

**Warning:** This tool is in beta.

`temporal-workflowcheck` scans compiled bytecode to detect non-deterministic operations in workflow code. It catches threading, I/O, randomization, system time access, and non-final static field access — including transitive violations through call chains.

### Setup (Gradle)

Add the dependency as a compile-only check:

```groovy
dependencies {
    implementation 'io.temporal:temporal-sdk:1.+'
    compileOnly 'io.temporal:temporal-workflowcheck:1.+'
}
```

See the [Gradle sample](https://github.com/temporalio/sdk-java/tree/master/temporal-workflowcheck/samples/gradle) for full task configuration.

### Setup (Maven)

See the [Maven sample](https://github.com/temporalio/sdk-java/tree/master/temporal-workflowcheck/samples/maven) for POM configuration.

### Running Manually

Download the `-all.jar` from Maven Central (`io.temporal:temporal-workflowcheck`) and run:

```bash
java -jar temporal-workflowcheck-<version>-all.jar check <classpath-entries>
```

### Suppressing False Positives

Use the `@WorkflowCheck.SuppressWarnings` annotation on methods:

```java
@WorkflowCheck.SuppressWarnings(invalidMembers = "currentTimeMillis")
public long getCurrentMillis() {
    return System.currentTimeMillis();
}
```

Or use a `.properties` configuration file with `--config <path>` for third-party library false positives.

## Convention-Based Enforcement

Java workflow code runs in a cooperative threading model where only one workflow thread executes at a time under a global lock. The SDK does not intercept or block non-deterministic calls. Instead, non-determinism is detected at **replay time**: if replayed code produces results that differ from the recorded history, the SDK throws a `NonDeterministicException`.

Use both `temporal-workflowcheck` (static, pre-deploy) and `WorkflowReplayer` (replay testing) to catch non-determinism before production.

## Best Practices

1. Run `temporal-workflowcheck` in CI to catch non-deterministic code statically
2. Always use `Workflow.*` APIs instead of standard Java equivalents for time, randomness, UUIDs, sleeping, and threading
3. Test all workflow code changes with `WorkflowReplayer` against recorded histories
4. Keep workflows focused on orchestration logic; move all I/O and side effects into activities
5. Avoid mutable static state shared across workflow instances
