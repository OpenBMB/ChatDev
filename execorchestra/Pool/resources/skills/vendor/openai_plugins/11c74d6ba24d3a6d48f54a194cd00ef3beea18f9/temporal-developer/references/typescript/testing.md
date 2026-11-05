# TypeScript SDK Testing

## Overview

The TypeScript SDK provides `TestWorkflowEnvironment` for testing workflows with time-skipping and activity mocking support. Use `createTimeSkipping()` for automatic time advancement when testing workflows with timers, or `createLocal()` for a full local server without time-skipping.

**Note:** Prefer to use `createLocal()` for full-featured support. Only use `createTimeSkipping()` if you genuinely need time skipping for testing your workflow.

## Test Environment Setup

```typescript
import { TestWorkflowEnvironment } from '@temporalio/testing';
import { Worker } from '@temporalio/worker';

describe('Workflow', () => {
  let testEnv: TestWorkflowEnvironment;

  before(async () => {
    testEnv = await TestWorkflowEnvironment.createLocal();
  });

  after(async () => {
    await testEnv?.teardown();
  });

  it('runs workflow', async () => {
    const { client, nativeConnection } = testEnv;

    const worker = await Worker.create({
      connection: nativeConnection,
      taskQueue: 'test',
      workflowsPath: require.resolve('./workflows'),
      activities: require('./activities'),
    });

    await worker.runUntil(async () => {
      const result = await client.workflow.execute(greetingWorkflow, {
        taskQueue: 'test',
        workflowId: 'test-workflow',
        args: ['World'],
      });
      expect(result).toEqual('Hello, World!');
    });
  });
});
```

## Activity Mocking

```typescript
const worker = await Worker.create({
  connection: nativeConnection,
  taskQueue: 'test',
  workflowsPath: require.resolve('./workflows'),
  activities: {
    // Mock activity implementation
    greet: async (name: string) => `Mocked: ${name}`,
  },
});
```

## Testing Signals and Queries

```typescript
import { defineQuery, defineSignal } from '@temporalio/workflow';

// Define query and signal (typically in a shared file)
const getStatusQuery = defineQuery<string>('getStatus');
const approveSignal = defineSignal('approve');

it('handles signals and queries', async () => {
  await worker.runUntil(async () => {
    const handle = await client.workflow.start(approvalWorkflow, {
      taskQueue: 'test',
      workflowId: 'approval-test',
    });

    // Query current state
    const status = await handle.query(getStatusQuery);
    expect(status).toEqual('pending');

    // Send signal
    await handle.signal(approveSignal);

    // Wait for completion
    const result = await handle.result();
    expect(result).toEqual('Approved!');
  });
});
```

## Testing Failure Cases

Test that workflows handle errors correctly:

```typescript
import { TestWorkflowEnvironment } from '@temporalio/testing';
import { Worker } from '@temporalio/worker';
import { WorkflowFailedError } from '@temporalio/client';
import assert from 'assert';

describe('Failure handling', () => {
  let testEnv: TestWorkflowEnvironment;

  before(async () => {
    testEnv = await TestWorkflowEnvironment.createLocal();
  });

  after(async () => {
    await testEnv?.teardown();
  });

  it('handles activity failure', async () => {
    const { client, nativeConnection } = testEnv;

    const worker = await Worker.create({
      connection: nativeConnection,
      taskQueue: 'test',
      workflowsPath: require.resolve('./workflows'),
      activities: {
        // Mock activity that always fails
        myActivity: async () => {
          throw new Error('Activity failed');
        },
      },
    });

    await worker.runUntil(async () => {
      try {
        await client.workflow.execute(myWorkflow, {
          workflowId: 'test-failure',
          taskQueue: 'test',
        });
        assert.fail('Expected workflow to fail');
      } catch (err) {
        assert(err instanceof WorkflowFailedError);
      }
    });
  });
});
```

## Replay Testing

```typescript
import { Worker } from '@temporalio/worker';
import { Client, Connection } from '@temporalio/client';
import fs from 'fs';

describe('Replay', () => {
  it('replays workflow history from JSON file', async () => {
    // Load history from a JSON file (exported from Web UI or Temporal CLI)
    const filePath = './history_file.json';
    const history = JSON.parse(await fs.promises.readFile(filePath, 'utf8'));

    await Worker.runReplayHistory(
      {
        workflowsPath: require.resolve('./workflows'),
      },
      history,
      'my-workflow-id' // Optional: provide workflowId if your workflow depends on it
    );
  });

  it('replays workflow history from server', async () => {
    // Fetch history programmatically using the client
    const connection = await Connection.connect({ address: 'localhost:7233' });
    const client = new Client({ connection, namespace: 'default' });
    const handle = client.workflow.getHandle('my-workflow-id');
    const history = await handle.fetchHistory();

    await Worker.runReplayHistory(
      {
        workflowsPath: require.resolve('./workflows'),
      },
      history,
      'my-workflow-id'
    );
  });
});
```

## Activity Testing

Test activities in isolation without running a workflow:

```typescript
import { MockActivityEnvironment } from '@temporalio/testing';
import { CancelledFailure } from '@temporalio/activity';
import { myActivity } from './activities';
import assert from 'assert';

describe('Activity tests', () => {
  it('completes successfully', async () => {
    const env = new MockActivityEnvironment();
    const result = await env.run(myActivity, 'input');
    assert.equal(result, 'expected output');
  });

  it('handles cancellation', async () => {
    const env = new MockActivityEnvironment();
    // Cancel the activity after a short delay
    setTimeout(() => env.cancel(), 100);
    try {
      await env.run(longRunningActivity, 'input');
      assert.fail('Expected cancellation');
    } catch (err) {
      assert(err instanceof CancelledFailure);
    }
  });
});
```

**Note:** `MockActivityEnvironment` provides `heartbeat()` and cancellation support for testing activity behavior.

## Best Practices

1. Use time-skipping for workflows with timers
2. Mock external dependencies in activities
3. Test replay compatibility when changing workflow code
4. Use unique workflow IDs per test
5. Clean up test environment after tests
