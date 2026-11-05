# Python SDK Patterns

## Signals

```python
@workflow.defn
class OrderWorkflow:
    def __init__(self):
        self._approved = False
        self._items = []

    @workflow.signal
    async def approve(self) -> None:
        self._approved = True

    @workflow.signal
    async def add_item(self, item: str) -> None:
        self._items.append(item)

    @workflow.run
    async def run(self) -> str:
        # Wait for approval
        await workflow.wait_condition(lambda: self._approved)
        return f"Processed {len(self._items)} items"
```

### Dynamic Signal Handlers

For handling signals with names not known at compile time. Use cases for this pattern are rare — most workflows should use statically defined signal handlers.

```python
@workflow.defn
class DynamicSignalWorkflow:
    def __init__(self):
        self._signals: dict[str, list[Any]] = {}

    @workflow.signal(dynamic=True)
    async def handle_signal(self, name: str, args: Sequence[RawValue]) -> None:
        if name not in self._signals:
            self._signals[name] = []
        self._signals[name].append(workflow.payload_converter().from_payload(args[0]))
```

## Queries

**Important:** Queries must NOT modify workflow state or have side effects.

```python
@workflow.defn
class StatusWorkflow:
    def __init__(self):
        self._status = "pending"
        self._progress = 0

    @workflow.query
    def get_status(self) -> str:
        return self._status

    @workflow.query
    def get_progress(self) -> int:
        return self._progress

    @workflow.run
    async def run(self) -> str:
        self._status = "running"
        for i in range(100):
            self._progress = i
            await workflow.execute_activity(
                process_item, i,
                start_to_close_timeout=timedelta(minutes=1)
            )
        self._status = "completed"
        return "done"
```

### Dynamic Query Handlers

For handling queries with names not known at compile time. Use cases for this pattern are rare — most workflows should use statically defined query handlers.

```python
@workflow.query(dynamic=True)
def handle_query(self, name: str, args: Sequence[RawValue]) -> Any:
    if name == "get_field":
        field_name = workflow.payload_converter().from_payload(args[0])
        return getattr(self, f"_{field_name}", None)
```

## Updates

```python
@workflow.defn
class OrderWorkflow:
    def __init__(self):
        self._items: list[str] = []

    @workflow.update
    async def add_item(self, item: str) -> int:
        self._items.append(item)
        return len(self._items)  # Returns new count to caller

    @add_item.validator
    def validate_add_item(self, item: str) -> None:
        if not item:
            raise ValueError("Item cannot be empty")
        if len(self._items) >= 100:
            raise ValueError("Order is full")
```

**Important:** Validators must NOT mutate workflow state or do anything blocking (no activities, sleeps, or other commands). They are read-only, similar to query handlers. Raise an exception to reject the update; return `None` to accept.

## Child Workflows

```python
@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self, orders: list[Order]) -> list[str]:
        results = []
        for order in orders:
            result = await workflow.execute_child_workflow(
                ProcessOrderWorkflow.run,
                order,
                id=f"order-{order.id}",
                # Control what happens to child when parent completes
                parent_close_policy=workflow.ParentClosePolicy.ABANDON,
            )
            results.append(result)
        return results
```

## Handles to External Workflows

```python
@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self, target_workflow_id: str) -> None:
        # Get handle to external workflow
        handle = workflow.get_external_workflow_handle(target_workflow_id)

        # Signal the external workflow
        await handle.signal(TargetWorkflow.data_ready, data_payload)

        # Or cancel it
        await handle.cancel()
```

## Parallel Execution

```python
@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self, items: list[str]) -> list[str]:
        # Execute activities in parallel
        tasks = [
            workflow.execute_activity(
                process_item, item,
                start_to_close_timeout=timedelta(minutes=5)
            )
            for item in items
        ]
        return await asyncio.gather(*tasks)
```

### Deterministic Alternatives to asyncio

Generally, asyncio is OK to use in Temoral workflows. But some asyncio calls are non-deterministic. Use Temporal's deterministic alternatives for safer concurrent operations:

```python
# workflow.wait() - like asyncio.wait()
done, pending = await workflow.wait(
    futures,
    return_when=workflow.WaitConditionResult.FIRST_COMPLETED
)

# workflow.as_completed() - like asyncio.as_completed()
async for future in workflow.as_completed(futures):
    result = await future
    # Process each result as it completes
```

## Continue-as-New

```python
@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self, state: WorkflowState) -> str:
        while True:
            state = await process_batch(state)

            if state.is_complete:
                return "done"

            # Continue with fresh history before hitting limits
            if workflow.info().is_continue_as_new_suggested():
                workflow.continue_as_new(args=[state])
```

## Saga Pattern (Compensations)

**Important:** Compensation activities should be idempotent - they may be retried (as with ALL activities).

```python
@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self, order: Order) -> str:
        compensations: list[Callable[[], Awaitable[None]]] = []

        try:
            # Note - we save the compensation before running the activity,
            # because the following could happen:
            # 1. reserve_inventory starts running
            # 2. it does successfully reserve inventory
            # 3. but then fails for some other reason (timeout, reporting metrics, etc.)
            # 4. in that case, the activity would have failed, but we still did the effect of reserving inventory
            # So, we need to make sure we have a compensation already on the stack to handle that.
            # This means the compensation needs to handle both the cases of reserved or unreserved inventory.
            compensations.append(lambda: workflow.execute_activity(
                release_inventory_if_reserved, order,
                start_to_close_timeout=timedelta(minutes=5)
            ))
            await workflow.execute_activity(
                reserve_inventory, order,
                start_to_close_timeout=timedelta(minutes=5)
            )

            compensations.append(lambda: workflow.execute_activity(
                refund_payment_if_charged, order,
                start_to_close_timeout=timedelta(minutes=5)
            ))
            await workflow.execute_activity(
                charge_payment, order,
                start_to_close_timeout=timedelta(minutes=5)
            )

            await workflow.execute_activity(
                ship_order, order,
                start_to_close_timeout=timedelta(minutes=5)
            )

            return "Order completed"

        except Exception as e:
            workflow.logger.error(f"Order failed: {e}, running compensations")
            # asyncio.shield ensures compensations run even if the workflow is cancelled.
            async def run_compensations():
                for compensate in reversed(compensations):
                    try:
                        await compensate()
                    except Exception as comp_err:
                        workflow.logger.error(f"Compensation failed: {comp_err}")
            await asyncio.shield(asyncio.ensure_future(run_compensations()))
            raise
```

## Cancellation Handling - leverages standard asyncio cancellation

```python
@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self) -> str:
        try:
            await workflow.execute_activity(
                long_running_activity,
                start_to_close_timeout=timedelta(hours=1),
            )
            return "completed"
        except asyncio.CancelledError:
            # Workflow was cancelled - perform cleanup
            workflow.logger.info("Workflow cancelled, running cleanup")
            # Cleanup activities still run even after cancellation
            await workflow.execute_activity(
                cleanup_activity,
                start_to_close_timeout=timedelta(minutes=5),
            )
            raise  # Re-raise to mark workflow as cancelled
```

## Wait Condition with Timeout

```python
@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self) -> str:
        self._approved = False

        # Wait for approval with 24-hour timeout
        try:
            await workflow.wait_condition(
                lambda: self._approved,
                timeout=timedelta(hours=24)
            )
            return "approved"
        except asyncio.TimeoutError:
            return "auto-rejected due to timeout"
```

## Waiting for All Handlers to Finish

Signal and update handlers should generally be non-async (avoid running activities from them). Otherwise, the workflow may complete before handlers finish their execution. However, making handlers non-async sometimes requires workarounds that add complexity.

When async handlers are necessary, use `wait_condition(all_handlers_finished)` at the end of your workflow (or before continue-as-new) to prevent completion until all pending handlers complete.

```python
@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self) -> str:
        # ... main workflow logic ...

        # Before exiting, wait for all handlers to finish
        await workflow.wait_condition(workflow.all_handlers_finished)
        return "done"
```

## Activity Heartbeat Details

### WHY:
- **Support activity cancellation** - Cancellations are delivered via heartbeat; activities that don't heartbeat won't know they've been cancelled
- **Resume progress after worker failure** - Heartbeat details persist across retries

**Cancellation exceptions:**
- Async activities: `asyncio.CancelledError`
- Sync threaded activities: `temporalio.exceptions.CancelledError`

### WHEN:
- **Cancellable activities** - Any activity that should respond to cancellation
- **Long-running activities** - Track progress for resumability
- **Checkpointing** - Save progress periodically

```python
from temporalio.exceptions import CancelledError

@activity.defn
def process_large_file(file_path: str) -> str:
    # Get heartbeat details from previous attempt (if any)
    heartbeat_details = activity.info().heartbeat_details
    start_line = heartbeat_details[0] if heartbeat_details else 0

    try:
        with open(file_path) as f:
            for i, line in enumerate(f):
                if i < start_line:
                    continue  # Skip already processed lines

                process_line(line)

                # Heartbeat with progress
                # If cancelled, heartbeat() raises CancelledError
                activity.heartbeat(i + 1)

        return "completed"
    except CancelledError:
        # Perform cleanup on cancellation
        cleanup()
        raise
```

## Timers

```python
@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self) -> str:
        await workflow.sleep(timedelta(hours=1))

        return "Timer fired"
```

## Local Activities

**Purpose**: Reduce latency for short, lightweight operations by skipping the task queue. ONLY use these when necessary for performance. Do NOT use these by default, as they are not durable and distributed.

```python
@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self) -> str:
        result = await workflow.execute_local_activity(
            quick_lookup,
            "key",
            start_to_close_timeout=timedelta(seconds=5),
        )
        return result
```

## Using Pydantic Models

See `references/python/data-handling.md`.
