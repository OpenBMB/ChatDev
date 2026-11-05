# Python SDK Error Handling

## Overview

The Python SDK uses `ApplicationError` for application-specific errors and provides comprehensive retry policy configuration. Generally, the following information about errors and retryability applies across activities, child workflows and Nexus operations.

## Application Errors

```python
from temporalio import activity
from temporalio.exceptions import ApplicationError

@activity.defn
async def validate_order(order: Order) -> None:
    if not order.is_valid():
        raise ApplicationError(
            "Invalid order",
            type="ValidationError",
        )
```

## Non-Retryable Errors

```python
from dataclasses import dataclass
from temporalio import activity
from temporalio.exceptions import ApplicationError

@dataclass
class ChargeCardInput:
    card_number: str
    amount: float

@activity.defn
async def charge_card(input: ChargeCardInput) -> str:
    if not is_valid_card(input.card_number):
        raise ApplicationError(
            "Permanent failure - invalid credit card",
            type="PaymentError",
            non_retryable=True,  # Will not retry activity
        )
    return await process_payment(input.card_number, input.amount)
```

## Handling Activity Errors

```python
from datetime import timedelta
from temporalio import workflow
from temporalio.exceptions import ActivityError, ApplicationError

@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self) -> str:
        try:
            return await workflow.execute_activity(
                risky_activity,
                start_to_close_timeout=timedelta(minutes=5),
            )
        except ActivityError as e:
            workflow.logger.error(f"Activity failed: {e}")
            # Handle or re-raise
            raise ApplicationError("Workflow failed due to activity error")
```

## Retry Policy Configuration

```python
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self) -> str:
        result = await workflow.execute_activity(
            my_activity,
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(
                maximum_interval=timedelta(minutes=1),
                maximum_attempts=5,
                non_retryable_error_types=["ValidationError", "PaymentError"],
            ),
        )
        return result
```

Only set options such as maximum_interval, maximum_attempts etc. if you have a domain-specific reason to.
If not, prefer to leave them at their defaults.

## Timeout Configuration

```python
from datetime import timedelta
from temporalio import workflow

@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self) -> str:
        return await workflow.execute_activity(
            my_activity,
            start_to_close_timeout=timedelta(minutes=5),      # Single attempt
            schedule_to_close_timeout=timedelta(minutes=30),  # Including retries
            heartbeat_timeout=timedelta(minutes=2),          # Between heartbeats
        )
```

## Workflow Failure

```python
from temporalio import workflow
from temporalio.exceptions import ApplicationError

@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self) -> str:
        if some_condition:
            raise ApplicationError(
                "Cannot process order",
                type="BusinessError",
            )
        return "success"
```

**Note:** Do not use `non_retryable=` with `ApplicationError` inside a worklow (as opposed to an activity).

## Best Practices

1. Use specific error types for different failure modes
2. Mark permanent failures as non-retryable
3. Configure appropriate retry policies
4. Log errors before re-raising
5. Use `ActivityError` to catch activity failures in workflows
6. Design code to be idempotent for safe retries (see more at `references/core/patterns.md`)
