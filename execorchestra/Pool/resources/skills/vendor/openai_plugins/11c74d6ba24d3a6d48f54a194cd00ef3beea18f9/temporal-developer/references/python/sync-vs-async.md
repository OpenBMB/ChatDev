# Python SDK: Sync vs Async Activities

## Overview

The Temporal Python SDK supports multiple ways of implementing Activities:

- **Asynchronous** using `asyncio`
- **Synchronous multithreaded** using `concurrent.futures.ThreadPoolExecutor`
- **Synchronous multiprocess** using `concurrent.futures.ProcessPoolExecutor`

Choosing the correct approach is critical—incorrect usage can cause sporadic failures and difficult-to-diagnose bugs.

## Recommendation: Default to Synchronous

Activities should be synchronous by default. Use async only when certain the code doesn't block the event loop.

## The Event Loop Problem

The Python async event loop runs in a single thread. When any task runs, no other tasks can execute until an `await` is reached. If code makes a blocking call (file I/O, synchronous HTTP, etc.), the entire event loop freezes.

**Consequences of blocking the event loop:**
- Worker cannot communicate with Temporal Server
- Workflow progress blocks across the worker
- Potential deadlocks and unpredictable behavior
- Difficult-to-diagnose bugs

## How the SDK Handles Each Type

### Synchronous Activities

- Run in the `activity_executor`, which you must provide
- Protected from accidentally blocking the global event loop
- Multiple activities run in parallel via OS thread scheduling
- Thread pool provides preemptive switching between tasks

```python
from concurrent.futures import ThreadPoolExecutor
from temporalio.worker import Worker

with ThreadPoolExecutor(max_workers=100) as executor:
    worker = Worker(
        client,
        task_queue="my-queue",
        workflows=[MyWorkflow],
        activities=[my_sync_activity],
        activity_executor=executor,
    )
    await worker.run()
```

### Asynchronous Activities

- Share the default asyncio event loop with the Temporal worker
- Any blocking call freezes the entire loop
- Require async-safe libraries throughout

```python
@activity.defn
async def my_async_activity(name: str) -> str:
    # Must use async-safe libraries only
    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://api.example.com/{name}") as response:
            return await response.text()
```

## HTTP Libraries: A Critical Choice

| Library | Type | Safe in Async Activity? |
|---------|------|------------------------|
| `requests` | Blocking | No - blocks event loop |
| `urllib3` | Blocking | No - blocks event loop |
| `aiohttp` | Async | Yes |
| `httpx` | Both | Yes (use async mode) |

**Example: Wrong way (blocks event loop)**
```python
@activity.defn
async def bad_activity(url: str) -> str:
    import requests
    response = requests.get(url)  # BLOCKS the event loop!
    return response.text
```

**Example: Correct way (async-safe)**
```python
@activity.defn
async def good_activity(url: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()
```

## Running Blocking Code in Async Activities

If blocking code must run in an async activity, offload it to a thread:

```python
import asyncio

@activity.defn
async def activity_with_blocking_call() -> str:
    # Run blocking code in a thread pool
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, blocking_function)
    return result

# Or use asyncio.to_thread (Python 3.9+)
@activity.defn
async def activity_with_blocking_call_v2() -> str:
    result = await asyncio.to_thread(blocking_function)
    return result
```

## When to Use Async Activities

Use async activities only when:

1. All code paths are async-safe (no blocking calls)
2. Using async-native libraries (aiohttp, asyncpg, motor, etc.)
3. Performance benefits are needed for I/O-bound operations
4. The team understands async constraints

## When to Use Sync Activities

Use sync activities when:

1. Making HTTP calls with `requests` or similar blocking libraries
2. Performing file I/O operations
3. Using database drivers that aren't async-native
4. Uncertain whether code is async-safe
5. Integrating with legacy or third-party synchronous code

## Debugging Tip

If experiencing sporadic bugs, hangs, or timeouts:

1. Convert async activities to sync
2. Test thoroughly
3. If bugs disappear, the original async activity had blocking calls

## Threading Considerations

### Multi-Core Usage

For CPU-bound work and multi-core usage:

- Prefer multiple worker processes and/or threaded synchronous activities.
- Use ProcessPoolExecutor for synchronous activities only if you understand and accept the extra complexity and different cancellation semantics.

### Separate Workers for Workflows vs Activities

Some teams deploy:
- Workflow-only workers (CPU-bound, need deadlock detection)
- Activity-only workers (I/O-bound, may need more parallelism)

This prevents resource contention and allows independent scaling.

## Complete Example: Sync Activity with ThreadPoolExecutor

```python
import urllib.parse
import requests
from concurrent.futures import ThreadPoolExecutor
from temporalio import activity
from temporalio.client import Client
from temporalio.worker import Worker

@activity.defn
def greet_in_spanish(name: str) -> str:
    """Synchronous activity using requests library."""
    url = f"http://localhost:9999/get-spanish-greeting?name={urllib.parse.quote(name)}"
    response = requests.get(url)
    return response.text

async def main():
    client = await Client.connect("localhost:7233", namespace="default")

    with ThreadPoolExecutor(max_workers=100) as executor:
        worker = Worker(
            client,
            task_queue="greeting-tasks",
            workflows=[GreetingWorkflow],
            activities=[greet_in_spanish],
            activity_executor=executor,
        )
        await worker.run()
```

## Complete Example: Async Activity with aiohttp

```python
import aiohttp
import urllib.parse
from temporalio import activity
from temporalio.client import Client
from temporalio.worker import Worker

class TranslateActivities:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session

    @activity.defn
    async def greet_in_spanish(self, name: str) -> str:
        """Async activity using aiohttp - safe for event loop."""
        url = f"http://localhost:9999/get-spanish-greeting?name={urllib.parse.quote(name)}"
        async with self.session.get(url) as response:
            return await response.text()

async def main():
    client = await Client.connect("localhost:7233", namespace="default")

    async with aiohttp.ClientSession() as session:
        activities = TranslateActivities(session)
        worker = Worker(
            client,
            task_queue="greeting-tasks",
            workflows=[GreetingWorkflow],
            activities=[activities.greet_in_spanish],
        )
        await worker.run()
```

## Summary

| Aspect | Sync Activities | Async Activities |
|--------|-----------------|------------------|
| Default choice | Yes | Only when certain |
| Blocking calls | Safe (runs in thread pool) | Dangerous (blocks event loop) |
| HTTP library | `requests`, `httpx` | `aiohttp`, `httpx` (async) |
| Executor needed | Yes (`ThreadPoolExecutor`) | No |
| Debugging | Easier | Harder (timing issues) |
