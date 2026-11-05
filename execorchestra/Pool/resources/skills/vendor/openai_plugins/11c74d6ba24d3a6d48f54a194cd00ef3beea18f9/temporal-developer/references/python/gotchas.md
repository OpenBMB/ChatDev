# Python Gotchas

Python-specific mistakes and anti-patterns. See also [Common Gotchas](references/core/gotchas.md) for language-agnostic concepts.

## File Organization

### Importing Activities into Workflow Files

**The Problem**: The Python sandbox reloads workflow files on every task. Importing heavy activity modules slows down workers.

```python
# BAD - activities.py gets reloaded constantly
# workflows.py
from activities import my_activity

@workflow.defn
class MyWorkflow:
    pass

# GOOD - Pass-through import
# workflows.py
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from activities import my_activity

@workflow.defn
class MyWorkflow:
    pass
```

`references/python/determinism-protection.md` contains more info about the Python sandbox.

### Mixing Workflows and Activities

```python
# BAD - Everything in one file
# app.py
@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self):
        await workflow.execute_activity(my_activity, ...)

@activity.defn
async def my_activity():
    # Heavy imports, I/O, etc.
    pass

# GOOD - Separate files
# workflows.py
@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self):
        await workflow.execute_activity(my_activity, ...)

# activities.py
@activity.defn
async def my_activity():
    pass
```

## Async vs Sync Activities

The Temporal Python SDK supports both async and sync activities. See `references/python/sync-vs-async.md` to understand which to choose. Below are important anti-patterns for both aysnc and sync activities.

### Blocking in Async Activities

```python
# BAD - Blocks the event loop
@activity.defn
async def process_file(path: str) -> str:
    with open(path) as f:  # Blocking I/O in async!
        return f.read()

# GOOD Option 1 - Use sync activity with executor
@activity.defn
def process_file(path: str) -> str:
    with open(path) as f:
        return f.read()

# Register with executor in worker
Worker(
    client,
    task_queue="my-queue",
    activities=[process_file],
    activity_executor=ThreadPoolExecutor(max_workers=10),
)

# GOOD Option 2 - Use async I/O
@activity.defn
async def process_file(path: str) -> str:
    async with aiofiles.open(path) as f:
        return await f.read()
```

### Missing Executor for Sync Activities

```python
# BAD - Sync activity REQUIRES executor
@activity.defn
def slow_computation(data: str) -> str:
    return heavy_cpu_work(data)

Worker(
    client,
    task_queue="my-queue",
    activities=[slow_computation],
    # Missing activity_executor! --> THIS IMMEDIATELY RAISES AN EXCEPTION!
)

# GOOD - Provide executor
Worker(
    client,
    task_queue="my-queue",
    activities=[slow_computation],
    activity_executor=ThreadPoolExecutor(max_workers=10),
)
```

## Wrong Retry Classification

**Example:** Transient networks errors should be retried. Authentication errors should not be.
See `references/python/error-handling.md` to understand how to classify errors.

## Heartbeating

### Forgetting to Heartbeat Long Activities

```python
# BAD - No heartbeat, can't detect stuck activities
@activity.defn
async def process_large_file(path: str):
    async for chunk in read_chunks(path):
        process(chunk)  # Takes hours, no heartbeat

# GOOD - Regular heartbeats with progress
@activity.defn
async def process_large_file(path: str):
    async for i, chunk in enumerate(read_chunks(path)):
        activity.heartbeat(f"Processing chunk {i}")
        process(chunk)
```

### Heartbeat Timeout Too Short

```python
# BAD - Heartbeat timeout shorter than processing time
await workflow.execute_activity(
    process_chunk,
    start_to_close_timeout=timedelta(minutes=30),
    heartbeat_timeout=timedelta(seconds=10),  # Too short!
)

# GOOD - Heartbeat timeout allows for processing variance
await workflow.execute_activity(
    process_chunk,
    start_to_close_timeout=timedelta(minutes=30),
    heartbeat_timeout=timedelta(minutes=2),
)
```

Set heartbeat timeout as high as acceptable for your use case — each heartbeat counts as an action.

## Cancellation

### Not Handling Workflow Cancellation

```python
# BAD - Cleanup doesn't run on cancellation
@workflow.defn
class BadWorkflow:
    @workflow.run
    async def run(self) -> None:
        await workflow.execute_activity(
            acquire_resource,
            start_to_close_timeout=timedelta(minutes=5),
        )
        await workflow.execute_activity(
            do_work,
            start_to_close_timeout=timedelta(minutes=5),
        )
        await workflow.execute_activity(
            release_resource,  # Never runs if cancelled!
            start_to_close_timeout=timedelta(minutes=5),
        )

# GOOD - Use try/finally for cleanup
@workflow.defn
class GoodWorkflow:
    @workflow.run
    async def run(self) -> None:
        await workflow.execute_activity(
            acquire_resource,
            start_to_close_timeout=timedelta(minutes=5),
        )
        try:
            await workflow.execute_activity(
                do_work,
                start_to_close_timeout=timedelta(minutes=5),
            )
        finally:
            # Runs even on cancellation
            await workflow.execute_activity(
                release_resource,
                start_to_close_timeout=timedelta(minutes=5),
            )
```

### Not Handling Activity Cancellation

Activities must **opt in** to receive cancellation. This requires:
1. **Heartbeating** - Cancellation is delivered via heartbeat
2. **Catching the cancellation exception** - Exception is raised when heartbeat detects cancellation

**Cancellation exceptions:**
- Async activities: `asyncio.CancelledError`
- Sync threaded activities: `temporalio.exceptions.CancelledError`

```python
# BAD - Activity ignores cancellation
@activity.defn
async def long_activity() -> None:
    await do_expensive_work()  # Runs to completion even if cancelled
```

```python
# GOOD - Heartbeat and catch cancellation
@activity.defn
async def long_activity() -> None:
    try:
        for item in items:
            activity.heartbeat()
            await process(item)
    except asyncio.CancelledError:
        await cleanup()
        raise
```

## Testing

### Not Testing Failures

It is important to make sure workflows work as expected under failure paths in addition to happy paths. Please see `references/python/testing.md` for more info.

### Not Testing Replay

Replay tests help you test that you do not have hidden sources of non-determinism bugs in your workflow code, and should be considered in addition to standard testing. Please see `references/python/testing.md` for more info.

## Timers and Sleep

### Using asyncio.sleep

```python
# BAD: asyncio.sleep is not deterministic during replay
import asyncio

@workflow.defn
class BadWorkflow:
    @workflow.run
    async def run(self) -> None:
        await asyncio.sleep(60)  # Non-deterministic!
```

```python
# GOOD: Use workflow.sleep for deterministic timers
from temporalio import workflow
from datetime import timedelta

@workflow.defn
class GoodWorkflow:
    @workflow.run
    async def run(self) -> None:
        await workflow.sleep(timedelta(seconds=60))  # Deterministic
        # Or with string duration:
        await workflow.sleep("1 minute")
```

**Why this matters:** `asyncio.sleep` uses the system clock, which differs between original execution and replay. `workflow.sleep` creates a durable timer in the event history, ensuring consistent behavior during replay.
