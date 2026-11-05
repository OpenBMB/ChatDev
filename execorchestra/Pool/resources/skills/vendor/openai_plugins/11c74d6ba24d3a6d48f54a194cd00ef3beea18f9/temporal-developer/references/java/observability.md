# Java SDK Observability

## Overview

The Java SDK provides observability through replay-safe logging, Micrometer-based metrics, and visibility (Search Attributes).

## Logging

### Workflow Logging (Replay-Safe)

Use `Workflow.getLogger()` for replay-safe logging that suppresses duplicate messages during replay:

```java
public class OrderWorkflowImpl implements OrderWorkflow {
    private static final Logger logger = Workflow.getLogger(OrderWorkflowImpl.class);

    @Override
    public String run(Order order) {
        logger.info("Workflow started for order {}", order.getId());

        String result = Workflow.newActivityStub(OrderActivities.class,
            ActivityOptions.newBuilder()
                .setStartToCloseTimeout(Duration.ofMinutes(5))
                .build()
        ).processOrder(order);

        logger.info("Activity completed with result {}", result);
        return result;
    }
}
```

The workflow logger automatically:
- Suppresses duplicate logs during replay
- Includes workflow context (workflow ID, run ID, etc.)
- Uses SLF4J under the hood

### Activity Logging

Use standard SLF4J loggers in activities. Activity context is available via `Activity.getExecutionContext()`:

```java
public class OrderActivitiesImpl implements OrderActivities {
    private static final Logger logger =
        LoggerFactory.getLogger(OrderActivitiesImpl.class);

    @Override
    public String processOrder(Order order) {
        logger.info("Processing order {}", order.getId());

        // Access activity context for metadata
        ActivityExecutionContext ctx = Activity.getExecutionContext();
        logger.info("Activity ID: {}, attempt: {}",
            ctx.getInfo().getActivityId(),
            ctx.getInfo().getAttempt());

        // Perform work...
        logger.info("Order processed successfully");
        return "completed";
    }
}
```

## Customizing the Logger

The Java SDK uses SLF4J. Configure your preferred backend:

### Logback (logback.xml)

```xml
<configuration>
    <appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
        <encoder>
            <pattern>%d{HH:mm:ss.SSS} [%thread] %-5level %logger{36} - %msg%n</pattern>
        </encoder>
    </appender>

    <!-- Suppress noisy Temporal internals -->
    <logger name="io.temporal.internal" level="WARN"/>

    <root level="INFO">
        <appender-ref ref="STDOUT"/>
    </root>
</configuration>
```

Log4j2 is also supported as an SLF4J backend with equivalent configuration.

## Metrics

### Micrometer with Prometheus

The Java SDK uses Micrometer for metrics collection. Configure with `MicrometerClientStatsReporter`:

```java
import io.micrometer.prometheus.PrometheusConfig;
import io.micrometer.prometheus.PrometheusMeterRegistry;
import io.temporal.common.reporter.MicrometerClientStatsReporter;
import com.uber.m3.tally.RootScopeBuilder;
import com.uber.m3.tally.Scope;
import com.uber.m3.util.Duration;

// Set up Prometheus registry
PrometheusMeterRegistry registry = new PrometheusMeterRegistry(PrometheusConfig.DEFAULT);

// Create the Temporal metrics scope
Scope scope = new RootScopeBuilder()
    .reporter(new MicrometerClientStatsReporter(registry))
    .reportEvery(Duration.ofSeconds(10));

// Apply to service stubs
WorkflowServiceStubs service = WorkflowServiceStubs.newServiceStubs(
    WorkflowServiceStubsOptions.newBuilder()
        .setMetricsScope(scope)
        .build()
);

// Expose Prometheus endpoint (e.g., via HTTP server)
// registry.scrape() returns the metrics in Prometheus format
```

### Key SDK Metrics

- `temporal_request` — Client requests to server
- `temporal_workflow_task_execution_latency` — Workflow task processing time
- `temporal_activity_execution_latency` — Activity execution time
- `temporal_workflow_task_replay_latency` — Replay duration

## Best Practices

1. Use `Workflow.getLogger()` in workflows, standard SLF4J loggers in activities
2. Do not use `System.out.println()` in workflows — it produces duplicate output on replay
3. Configure Micrometer metrics for production monitoring
4. Use Search Attributes for business-level visibility — see `references/java/data-handling.md`
