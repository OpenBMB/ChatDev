# Temporal Python SDK Reference

## Overview

The Temporal Python SDK (`temporalio`) provides a fully async, type-safe approach to building durable workflows. Python 3.9+ required. Workflows run in a sandbox by default for determinism protection.

## Quick Demo of Temporal

**Add Dependency on Temporal:** In the package management system of the Python project you are working on, add a dependency on `temporalio`.

**activities/greet.py** - Activity definitions (separate file for performance):
```python
from temporalio import activity

@activity.defn
def greet(name: str) -> str:
    return f"Hello, {name}!"
```

**workflows/greeting.py** - Workflow definition (import activities through sandbox):
```python
from datetime import timedelta
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from activities.greet import greet

@workflow.defn
class GreetingWorkflow:
    @workflow.run
    async def run(self, name: str) -> str:
        return await workflow.execute_activity(
            greet, name, start_to_close_timeout=timedelta(seconds=30)
        )
```

**worker.py** - Worker setup (imports activity and workflow, runs indefinitely and processes tasks):
```python
import asyncio
import concurrent.futures
from temporalio.client import Client
from temporalio.worker import Worker

# Import the activity and workflow from our other files
from activities.greet import greet
from workflows.greeting import GreetingWorkflow

async def main():
    # Create client connected to server at the given address
    # This is the default port for `temporal server start-dev`
    client = await Client.connect("localhost:7233")

    # Run the worker
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as activity_executor:
        worker = Worker(
          client,
          task_queue="my-task-queue",
          workflows=[GreetingWorkflow],
          activities=[greet],
          activity_executor=activity_executor,
        )
        await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
```

**Start the dev server:** Start `temporal server start-dev` in the background.

**Start the worker:** Start `python worker.py` in the background (appropriately adjust command for your project, like `uv run python worker.py`)

**starter.py** - Start a workflow execution:
```python
import asyncio
from temporalio.client import Client
import uuid

# Import the workflow from the previous code
from workflows.greeting import GreetingWorkflow

async def main():
    # Create client connected to server at the given address
    client = await Client.connect("localhost:7233")

    # Execute a workflow
    result = await client.execute_workflow(GreetingWorkflow.run, "my name", id=str(uuid.uuid4()), task_queue="my-task-queue")

    print(f"Result: {result}")

if __name__ == "__main__":
    asyncio.run(main())
```

**Run the workflow:** Run `python starter.py` (or uv run, etc.). Should output: `Result: Hello, my-name!`.


## Key Concepts

### Workflow Definition
- Use `@workflow.defn` decorator on class
- Put any state initialization logic in the `__init__` of your workflow class to guarantee that it happens before signals/updates arrive. If your state initialization logic requires the workflow parameters, then add the `@workflow.init` decorator and parameters to your `__init__`.
- Use `@workflow.run` on the entry point method
- Must be async (`async def`)
- Use `@workflow.signal`, `@workflow.query`, `@workflow.update` for handlers

### Activity Definition
- Use `@activity.defn` decorator
- Can be sync or async functions
- **Default to sync activities** - safer and easier to debug
- Sync activities need `activity_executor` (ThreadPoolExecutor)
- Async activities require async-safe libraries throughout (e.g., `aiohttp` not `requests`)

See `sync-vs-async.md` for detailed guidance on choosing between sync and async.

### Worker Setup
- Connect client, create Worker with workflows and activities
- Run the worker
- Activities can specify custom executor

### Determinism

**Workflow code must be deterministic!**. All sources of non-determinism should either use Temporal-provided actions or (primarily) be defined in Activities. Read `references/core/determinism.md` and `references/python/determinism.md` to understand more.

## File Organization Best Practice

**Keep Workflow definitions in separate files from Activity definitions.** The Python SDK sandbox reloads Workflow definition files on every execution for determinism protection. Minimizing file contents improves Worker performance.

```
my_temporal_app/
├── workflows/
│   └── greeting.py      # Only Workflow classes
├── activities/
│   └── translate.py     # Only Activity functions/classes
├── worker.py            # Worker setup, imports both
└── starter.py           # Client code to start workflows
```

**In the Workflow file, import Activities through the sandbox:**
```python
# workflows/greeting.py
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from activities.translate import TranslateActivities
```

## Common Pitfalls

1. **Non-deterministic code in workflows** - Use activities for all non-deterministic and/or fallible code
2. **Blocking in async activities** - Use sync activities or async-safe libraries only
3. **Missing executor for sync activities** - Add `activity_executor=ThreadPoolExecutor()`
4. **Forgetting to heartbeat** - Long activities need `activity.heartbeat()`
5. **Using gevent** - Incompatible with SDK
6. **Using `print()` in workflows** - Use `workflow.logger` instead for replay-safe logging
7. **Mixing Workflows and Activities in same file** - Causes unnecessary reloads, hurts performance, bad structure
8. **Forgetting to wait on activity calls** - `workflow.execute_activity()` is async; you must eventually await it (directly or via `asyncio.gather()` for parallel execution)

## Writing Tests

See `references/python/testing.md` for info on writing tests.

## Additional Resources

### Reference Files
- **`references/python/patterns.md`** - Signals, queries, child workflows, saga pattern, etc.
- **`references/python/determinism.md`** - Sandbox behavior, safe alternatives, pass-through pattern, history replay
- **`references/python/gotchas.md`** - Python-specific mistakes and anti-patterns
- **`references/python/error-handling.md`** - ApplicationError, retry policies, non-retryable errors, idempotency
- **`references/python/observability.md`** - Logging, metrics, tracing, Search Attributes
- **`references/python/testing.md`** - WorkflowEnvironment, time-skipping, activity mocking
- **`references/python/sync-vs-async.md`** - Sync vs async activities, event loop blocking, executor configuration
- **`references/python/advanced-features.md`** - Schedules, worker tuning, and more
- **`references/python/data-handling.md`** - Data converters, Pydantic, payload encryption
- **`references/python/versioning.md`** - Patching API, workflow type versioning, Worker Versioning
- **`references/python/determinism-protection.md`** - Python sandbox specifics, forbidden operations, pass-through imports
- **`references/python/ai-patterns.md`** - LLM integration, Pydantic data converter, AI workflow patterns
