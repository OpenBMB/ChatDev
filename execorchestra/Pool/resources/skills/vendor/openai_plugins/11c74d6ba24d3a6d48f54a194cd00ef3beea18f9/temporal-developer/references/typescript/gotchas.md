# TypeScript Gotchas

TypeScript-specific mistakes and anti-patterns. See also [Common Gotchas](../core/gotchas.md) for language-agnostic concepts.

## Activity Imports

### Importing Implementations Instead of Types

**The Problem**: Importing activity implementations brings Node.js code into the V8 workflow sandbox, causing bundling errors or runtime failures.

```typescript
// BAD - Brings actual code into workflow sandbox
import * as activities from './activities';

const { greet } = proxyActivities<typeof activities>({
  startToCloseTimeout: '1 minute',
});

// GOOD - Type-only import
import type * as activities from './activities';

const { greet } = proxyActivities<typeof activities>({
  startToCloseTimeout: '1 minute',
});
```

### Importing Node.js Modules in Workflows

```typescript
// BAD - fs is not available in workflow sandbox
import * as fs from 'fs';

export async function myWorkflow(): Promise<void> {
  const data = fs.readFileSync('file.txt'); // Will fail!
}

// GOOD - File I/O belongs in activities
export async function myWorkflow(): Promise<void> {
  const data = await activities.readFile('file.txt');
}
```

## Bundling Issues

### Using workflowsPath in Production

`workflowsPath` runs the bundler at Worker startup, which is slow and not suitable for production. Use `workflowBundle` with pre-bundled code instead.

```typescript
// OK for development/testing, BAD for production - bundles at startup
const worker = await Worker.create({
  workflowsPath: require.resolve('./workflows'),
  // ...
});

// GOOD for production - use pre-bundled code
import { bundleWorkflowCode } from '@temporalio/worker';

// Build step (run once at build time)
const bundle = await bundleWorkflowCode({
  workflowsPath: require.resolve('./workflows'),
});
await fs.promises.writeFile('./workflow-bundle.js', bundle.code);

// Worker startup (fast, no bundling)
const worker = await Worker.create({
  workflowBundle: {
    codePath: require.resolve('./workflow-bundle.js'),
  },
  // ...
});
```

### Missing Dependencies in Workflow Bundle

```typescript
// If using external packages in workflows, ensure they're bundled

// worker.ts
const worker = await Worker.create({
  workflowsPath: require.resolve('./workflows'),
  bundlerOptions: {
    // Exclude Node.js-only packages that cause bundling errors
    // WARNING: Modules listed here will be completely unavailable
    // at workflow runtime - any imports will fail
    ignoreModules: ['some-node-only-package'],
  },
});
```

### Package Version Mismatches

All `@temporalio/*` packages must have the same version. This can be verified by running `npm ls` or the appropriate command for your package manager.

### Package Version Constraints - Prod vs. Non-Prod

For production apps, you should use ~ version constraints (bug fixes only) on Temporal packages. For non-production apps, you may use ^ constraints (the npm default) instead.

## Wrong Retry Classification

A common mistake is treating transient errors as permanent (or vice versa):

- **Transient errors** (retry): network timeouts, temporary service unavailability, rate limits
- **Permanent errors** (don't retry): invalid input, authentication failure, resource not found

```typescript
// BAD: Retrying a permanent error
throw ApplicationFailure.create({ message: 'User not found' });
// This will retry indefinitely!

// GOOD: Mark permanent errors as non-retryable
throw ApplicationFailure.nonRetryable('User not found');
```

For detailed guidance on error classification and retry policies, see `error-handling.md`.

## Cancellation

### Not Handling Workflow Cancellation

```typescript
// BAD - Cleanup doesn't run on cancellation
export async function workflowWithCleanup(): Promise<void> {
  await activities.acquireResource();
  await activities.doWork();
  await activities.releaseResource(); // Never runs if cancelled!
}

// GOOD - Use CancellationScope for cleanup
import { CancellationScope } from '@temporalio/workflow';

export async function workflowWithCleanup(): Promise<void> {
  await activities.acquireResource();
  try {
    await activities.doWork();
  } finally {
    // Run cleanup even on cancellation
    await CancellationScope.nonCancellable(async () => {
      await activities.releaseResource();
    });
  }
}
```

### Not Handling Activity Cancellation

Activities must **opt in** to receive cancellation. This requires:
1. **Heartbeating** - Cancellation is delivered via heartbeat
2. **Checking for cancellation** - Either await `Context.current().cancelled` or use `cancellationSignal()`

```typescript
// BAD - Activity ignores cancellation
export async function longActivity(): Promise<void> {
  await doExpensiveWork(); // Runs to completion even if cancelled
}
```

```typescript
// GOOD - Heartbeat in background and race work against cancellation promise
import { Context, CancelledFailure } from '@temporalio/activity';

export async function longActivity(): Promise<void> {
  // Heartbeat in background so cancellation can be delivered
  let heartbeatEnabled = true;
  (async () => {
    while (heartbeatEnabled) {
      await Context.current().sleep(5000);
      Context.current().heartbeat();
    }
  })().catch(() => {});

  try {
    await Promise.race([
      Context.current().cancelled,  // Rejects with CancelledFailure
      doExpensiveWork(),
    ]);
  } catch (err) {
    if (err instanceof CancelledFailure) {
      await cleanup();
    }
    throw err;
  } finally {
    heartbeatEnabled = false;
  }
}
```

```typescript
// GOOD - Use AbortSignal with libraries that support it
import fetch from 'node-fetch';
import { cancellationSignal, heartbeat } from '@temporalio/activity';
import type { AbortSignal as FetchAbortSignal } from 'node-fetch/externals';

export async function cancellableFetch(url: string): Promise<Uint8Array> {
  const response = await fetch(url, { signal: cancellationSignal() as FetchAbortSignal });

  const contentLength = parseInt(response.headers.get('Content-Length')!);
  let bytesRead = 0;
  const chunks: Buffer[] = [];

  for await (const chunk of response.body) {
    if (!(chunk instanceof Buffer)) throw new TypeError('Expected Buffer');
    bytesRead += chunk.length;
    chunks.push(chunk);
    heartbeat(bytesRead / contentLength);  // Heartbeat to keep cancellation delivery alive
  }
  return Buffer.concat(chunks);
}
```

**Note:** `Promise.race` doesn't stop the losing promise—it continues running. Use `cancellationSignal()` or explicitly abort sub-operations when cleanup requires stopping in-flight work.

## Heartbeating

### Forgetting to Heartbeat Long Activities

```typescript
// BAD - No heartbeat, can't detect stuck activities
export async function processLargeFile(path: string): Promise<void> {
  for await (const chunk of readChunks(path)) {
    await processChunk(chunk); // Takes hours, no heartbeat
  }
}

// GOOD - Regular heartbeats with progress
import { heartbeat } from '@temporalio/activity';

export async function processLargeFile(path: string): Promise<void> {
  let i = 0;
  for await (const chunk of readChunks(path)) {
    heartbeat(`Processing chunk ${i++}`);
    await processChunk(chunk);
  }
}
```

### Heartbeat Timeout Too Short

```typescript
// BAD - Heartbeat timeout shorter than processing time
const { processChunk } = proxyActivities<typeof activities>({
  startToCloseTimeout: '30 minutes',
  heartbeatTimeout: '10 seconds', // Too short!
});

// GOOD - Heartbeat timeout allows for processing variance
const { processChunk } = proxyActivities<typeof activities>({
  startToCloseTimeout: '30 minutes',
  heartbeatTimeout: '2 minutes',
});
```

Set heartbeat timeout as high as acceptable for your use case — each heartbeat counts as an action.

## Testing

### Not Testing Failures

```typescript
import { TestWorkflowEnvironment } from '@temporalio/testing';
import { Worker } from '@temporalio/worker';

test('handles activity failure', async () => {
  const env = await TestWorkflowEnvironment.createTimeSkipping();

  const worker = await Worker.create({
    connection: env.nativeConnection,
    taskQueue: 'test',
    workflowsPath: require.resolve('./workflows'),
    activities: {
      // Activity that always fails
      riskyOperation: async () => {
        throw ApplicationFailure.nonRetryable('Simulated failure');
      },
    },
  });

  await worker.runUntil(async () => {
    await expect(
      env.client.workflow.execute(riskyWorkflow, {
        workflowId: 'test-failure',
        taskQueue: 'test',
      })
    ).rejects.toThrow('Simulated failure');
  });

  await env.teardown();
});
```

### Not Testing Replay

```typescript
import { Worker } from '@temporalio/worker';
import * as fs from 'fs';

test('replay compatibility', async () => {
  const history = JSON.parse(await fs.promises.readFile('./fixtures/workflow_history.json', 'utf8'));

  // Fails if current code is incompatible with history
  await Worker.runReplayHistory(
    {
      workflowsPath: require.resolve('./workflows'),
    },
    history,
  );
});
```

## Timers and Sleep

`setTimeout` works in workflows (the SDK mocks it), but `sleep()` from `@temporalio/workflow` is preferred because its interaction with cancellation scopes is more intuitive. See Timers in `references/typescript/patterns.md`.
