# Python SDK Testing

## Overview

You test Temporal Python Workflows using the Temporal testing package plus a normal Python test framework like pytest. The Temporal Python SDK provides `WorkflowEnvironment` for testing workflows in a local environment and `ActivityEnvironment` for isolated activity testing.

## Workflow Test Environment

The core pattern is:

1. Start a test WorkflowEnvironment (`WorkflowEnvironment.start_local()`).
2. Start a Worker in that environment with your Workflow and Activities registered.
3. Use the environment’s client to execute the Workflow, using a fresh UUID for the task queue name and workflow ID.
4. Assert on the result or status.

`WorkflowEnvironment.start_local` configures a ready-to-go local environment for running and testing workflows:

```python
import uuid
import pytest

from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from activities import my_activity
from workflows import MyWorkflow

@pytest.mark.asyncio
async def test_workflow():
    task_queue_name = str(uuid.uuid4())
    async with await WorkflowEnvironment.start_local() as env:
        async with Worker(
            env.client,
            task_queue=task_queue_name,
            workflows=[MyWorkflow],
            activities=[my_activity],
        ):
            result = await env.client.execute_workflow(
                MyWorkflow.run,
                "input",
                id=str(uuid.uuid4()),
                task_queue=task_queue_name,
            )
```

Conveniently, the local `env` can be shared among tests, e.g. via a pytest fixture.

If your workflows / tests involve long durations (such as using Temporal timers / sleeps), then you can use the time-skipping environment, via `WorkflowEnvironment.start_time_skipping()`.
Only use time-skipping if you must. It can *not* be shared among tests.

## Mocking Activities

```python
import uuid
import pytest

from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from workflows import MyWorkflow

@activity.defn(name="compose_greeting")
async def compose_greeting_mocked(input: str) -> str:
    return "mocked result"

@pytest.mark.asyncio
async def test_with_mock():
    task_queue_name = str(uuid.uuid4())
    async with await WorkflowEnvironment.start_local() as env:
        async with Worker(
            env.client,
            task_queue=task_queue_name,
            workflows=[MyWorkflow],
            activities=[compose_greeting_mocked],
        ):
            result = await env.client.execute_workflow(...)
```

## Testing Signals and Queries

```python
@pytest.mark.asyncio
async def test_signals():
    async with await WorkflowEnvironment.start_local() as env:
        async with Worker(...):
            handle = await env.client.start_workflow(...) # same arguments as to execute_workflow

            # Send signal
            await handle.signal(MyWorkflow.my_signal, "data")

            # Query state
            status = await handle.query(MyWorkflow.get_status)
            assert status == "expected"

            # Wait for completion
            result = await handle.result()
```

## Testing Failure Cases

Below shows an example of how to test failure cases:

```python
# Test failure scenarios
@pytest.mark.asyncio
async def test_activity_failure_handling():
    async with await WorkflowEnvironment.start_local() as env:
        # An example activity that always fails
        @activity.defn
        async def failing_activity() -> str:
            raise ApplicationError("Simulated failure", non_retryable=True)

        async with Worker(...):
            with pytest.raises(WorkflowFailureError):
                await env.client.execute_workflow(...)
```

## Workflow Replay Testing

```python
import json
import pytest
import uuid
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from workflows import MyWorkflow

@pytest.mark.asyncio
async def test_replay():
    with open("example-history.json", "r") as f:
        history_json = json.load(f)

    replayer = Replayer(workflows=[MyWorkflow])

    # From JSON file
    await replayer.replay_workflow(
        WorkflowHistory.from_json(str(uuid.uuid4()), history_json)
    )
```


## Activity Testing

```python
import pytest

from temporalio.testing import ActivityEnvironment

@pytest.mark.asyncio
async def test_activity():
    env = ActivityEnvironment()
    result = await env.run(my_activity, "arg1", "arg2")
    assert result == "expected"
```

## Best Practices

1. Use the `WorkflowEnvironment.start_local` environment for most testing
2. Use time-skipping environment for workflows with durable timers / durable sleeps.
3. Mock external dependencies in activities
4. Test replay compatibility, especially when changing workflow code
5. Test signal/query handlers explicitly
6. Use unique workflow IDs and task queues per test to avoid conflicts. Easiest is a `uuid.uuid4()`
