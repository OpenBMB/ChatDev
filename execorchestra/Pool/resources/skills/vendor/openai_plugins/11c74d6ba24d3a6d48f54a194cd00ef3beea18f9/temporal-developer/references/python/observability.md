# Python SDK Observability

## Overview

The Python SDK provides comprehensive observability through logging, metrics, tracing, and visibility (Search Attributes).

## Logging

### Workflow Logging (Replay-Safe)

Use `workflow.logger` for replay-safe logging that avoids duplicate messages:

```python
@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self, name: str) -> str:
        workflow.logger.info("Workflow started", extra={"name": name})

        result = await workflow.execute_activity(
            my_activity,
            start_to_close_timeout=timedelta(minutes=5),
        )

        workflow.logger.info("Activity completed", extra={"result": result})
        return result
```

The workflow logger automatically:
- Suppresses duplicate logs during replay
- Includes workflow context (workflow ID, run ID, etc.)

### Activity Logging

Use `activity.logger` for context-aware activity logging:

```python
@activity.defn
async def process_order(order_id: str) -> str:
    activity.logger.info(f"Processing order {order_id}")

    # Perform work...

    activity.logger.info("Order processed successfully")
    return "completed"
```

Activity logger includes:
- Activity ID, type, and task queue
- Workflow ID and run ID
- Attempt number (for retries)

### Customizing Logger Configuration

```python
import logging

# Applies to temporalio.workflow.logger and temporalio.activity.logger, as Temporal inherits the default logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
```

## Metrics

### Enabling SDK Metrics

```python
from temporalio.client import Client
from temporalio.runtime import Runtime, TelemetryConfig, PrometheusConfig

# Create a custom runtime
runtime = Runtime(
    telemetry=TelemetryConfig(
        metrics=PrometheusConfig(bind_address="0.0.0.0:9000")
    )
)

# Set it as the global default BEFORE any Client/Worker is created
# Do this only ONCE.
Runtime.set_default(runtime, error_if_already_set=True)
# error_if_already_set can be False if you want to overwrite an existing default without raising.

# ...elsewhere, client = ... as usual
```

### Key SDK Metrics

- `temporal_request` - Client requests to server
- `temporal_workflow_task_execution_latency` - Workflow task processing time
- `temporal_activity_execution_latency` - Activity execution time
- `temporal_workflow_task_replay_latency` - Replay duration


## Search Attributes (Visibility)

See the Search Attributes section of `references/python/data-handling.md`

## Best Practices

1. Use `workflow.logger` in workflows, `activity.logger` in activities
2. Don't use print() in workflows - it will produce duplicate output on replay
3. Configure metrics for production monitoring
4. Use Search Attributes for business-level visibility
