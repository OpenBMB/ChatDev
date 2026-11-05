# Java SDK Error Handling

## Overview

The Java SDK uses `ApplicationFailure` for application-specific errors and `RetryOptions` for retry configuration. Generally, the following information about errors and retryability applies across activities, child workflows and Nexus operations.

## Application Errors

```java
import io.temporal.activity.ActivityInterface;
import io.temporal.activity.ActivityMethod;
import io.temporal.failure.ApplicationFailure;

@ActivityInterface
public interface OrderActivities {
    @ActivityMethod
    void validateOrder(Order order);
}

public class OrderActivitiesImpl implements OrderActivities {
    @Override
    public void validateOrder(Order order) {
        if (!order.isValid()) {
            throw ApplicationFailure.newFailure(
                "Invalid order",
                "ValidationError"
            );
        }
    }
}
```

Any exception that is not an `ApplicationFailure` is automatically converted to one, with the fully qualified class name as the type. For example, throwing `new NullPointerException("msg")` is equivalent to `ApplicationFailure.newFailure("msg", "java.lang.NullPointerException")`.

## Non-Retryable Errors

```java
import io.temporal.failure.ApplicationFailure;

public class PaymentActivitiesImpl implements PaymentActivities {
    @Override
    public String chargeCard(String cardNumber, double amount) {
        if (!isValidCard(cardNumber)) {
            throw ApplicationFailure.newNonRetryableFailure(
                "Permanent failure - invalid credit card",
                "PaymentError"
            );
        }
        return processPayment(cardNumber, amount);
    }
}
```

You can also mark error types as non-retryable via `RetryOptions.setDoNotRetry()`:

```java
RetryOptions retryOptions = RetryOptions.newBuilder()
    .setDoNotRetry(
        CreditCardProcessingException.class.getName(),
        "ValidationError"
    )
    .build();
```

Use `newNonRetryableFailure()` when the **activity implementer** knows the error is permanent. Use `setDoNotRetry()` when the **caller** wants to control retryability.

## Activity Errors

Activity failures are always wrapped in `ActivityFailure`. The original exception becomes the `cause`:

- `ActivityFailure` → `ApplicationFailure` (application error)
- `ActivityFailure` → `TimeoutFailure` (timeout)
- `ActivityFailure` → `CanceledFailure` (cancellation)

## Handling Activity Errors

```java
import io.temporal.failure.ActivityFailure;
import io.temporal.failure.ApplicationFailure;
import io.temporal.failure.TimeoutFailure;
import io.temporal.workflow.Workflow;

public class MyWorkflowImpl implements MyWorkflow {
    @Override
    public String run() {
        try {
            return activities.riskyOperation();
        } catch (ActivityFailure af) {
            if (af.getCause() instanceof ApplicationFailure) {
                ApplicationFailure appFailure = (ApplicationFailure) af.getCause();
                String type = appFailure.getType();
                // Handle based on error type
            } else if (af.getCause() instanceof TimeoutFailure) {
                // Handle timeout
            }
            throw ApplicationFailure.newFailure(
                "Workflow failed due to activity error",
                "WorkflowError"
            );
        }
    }
}
```

## Retry Policy Configuration

```java
import io.temporal.activity.ActivityOptions;
import io.temporal.common.RetryOptions;
import io.temporal.workflow.Workflow;

import java.time.Duration;

public class MyWorkflowImpl implements MyWorkflow {

    private final MyActivities activities = Workflow.newActivityStub(
        MyActivities.class,
        ActivityOptions.newBuilder()
            .setStartToCloseTimeout(Duration.ofMinutes(10))
            .setRetryOptions(RetryOptions.newBuilder()
                .setMaximumInterval(Duration.ofMinutes(1))
                .setMaximumAttempts(5)
                .setDoNotRetry("ValidationError", "PaymentError")
                .build())
            .build()
    );

    @Override
    public String run() {
        return activities.myActivity();
    }
}
```

Only set options such as `maximumInterval`, `maximumAttempts` etc. if you have a domain-specific reason to. If not, prefer to leave them at their defaults.

## Timeout Configuration

```java
ActivityOptions options = ActivityOptions.newBuilder()
    .setStartToCloseTimeout(Duration.ofMinutes(5))      // Single attempt
    .setScheduleToCloseTimeout(Duration.ofMinutes(30))   // Including retries
    .setHeartbeatTimeout(Duration.ofMinutes(2))          // Between heartbeats
    .build();
```

## Workflow Failure

**IMPORTANT:** Only `ApplicationFailure` causes a workflow to fail. Any other exception thrown from workflow code causes the workflow task to retry indefinitely, not the workflow itself.

```java
import io.temporal.failure.ApplicationFailure;

public class MyWorkflowImpl implements MyWorkflow {
    @Override
    public String run() {
        if (someCondition) {
            throw ApplicationFailure.newFailure(
                "Cannot process order",
                "BusinessError"
            );
        }
        return "success";
    }
}
```

To allow other exception types to fail the workflow instead of causing infinite task retries, see `references/java/advanced-features.md` for configuring `setFailWorkflowExceptionTypes()`.

Use checked exceptions with `Workflow.wrap()` to rethrow them as unchecked:

```java
try {
    return someCall();
} catch (Exception e) {
    throw Workflow.wrap(e);
}
```

## Best Practices

1. Use specific error types for different failure modes
2. Mark permanent failures as non-retryable
3. Configure appropriate retry policies
4. Log errors before re-raising
5. Catch `ActivityFailure` (not `ApplicationFailure`) for activity failures in workflows
6. Design code to be idempotent for safe retries (see more at `references/core/patterns.md`)
7. Use `ApplicationFailure.newFailure()` to fail workflows — other exceptions cause infinite task retries
