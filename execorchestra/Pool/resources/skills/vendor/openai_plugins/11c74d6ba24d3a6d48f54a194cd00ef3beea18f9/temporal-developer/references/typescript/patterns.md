# TypeScript SDK Patterns

## Signals

```typescript
import { defineSignal, setHandler, condition } from '@temporalio/workflow';

const approveSignal = defineSignal<[boolean]>('approve');
const addItemSignal = defineSignal<[string]>('addItem');

export async function orderWorkflow(): Promise<string> {
  let approved = false;
  const items: string[] = [];

  setHandler(approveSignal, (value) => {
    approved = value;
  });

  setHandler(addItemSignal, (item) => {
    items.push(item);
  });

  await condition(() => approved);
  return `Processed ${items.length} items`;
}
```

## Dynamic Signal Handlers

For handling signals with names not known at compile time. Use cases for this pattern are rare — most workflows should use statically defined signal handlers.

```typescript
import { setDefaultSignalHandler, condition } from '@temporalio/workflow';

export async function dynamicSignalWorkflow(): Promise<Record<string, unknown[]>> {
  const signals: Record<string, unknown[]> = {};

  setDefaultSignalHandler((signalName: string, ...args: unknown[]) => {
    if (!signals[signalName]) {
      signals[signalName] = [];
    }
    signals[signalName].push(args);
  });

  await condition(() => signals['done'] !== undefined);
  return signals;
}
```

## Queries

**Important:** Queries must NOT modify workflow state or have side effects.

```typescript
import { defineQuery, setHandler } from '@temporalio/workflow';

const statusQuery = defineQuery<string>('status');
const progressQuery = defineQuery<number>('progress');

export async function progressWorkflow(): Promise<void> {
  let status = 'running';
  let progress = 0;

  setHandler(statusQuery, () => status);
  setHandler(progressQuery, () => progress);

  for (let i = 0; i < 100; i++) {
    progress = i;
    await doWork();
  }
  status = 'completed';
}
```

## Dynamic Query Handlers

For handling queries with names not known at compile time. Use cases for this pattern are rare — most workflows should use statically defined query handlers.

```typescript
import { setDefaultQueryHandler } from '@temporalio/workflow';

export async function dynamicQueryWorkflow(): Promise<void> {
  const state: Record<string, unknown> = {
    status: 'running',
    progress: 0,
  };

  setDefaultQueryHandler((queryName: string) => {
    return state[queryName];
  });

  // ... workflow logic
}
```

## Updates

```typescript
import { defineUpdate, setHandler, condition } from '@temporalio/workflow';

// Define the update - specify return type and argument types
export const addItemUpdate = defineUpdate<number, [string]>('addItem');
export const addItemValidatedUpdate = defineUpdate<number, [string]>('addItemValidated');

export async function orderWorkflow(): Promise<string> {
  const items: string[] = [];
  let completed = false;

  // Simple update handler - returns new item count
  setHandler(addItemUpdate, (item: string) => {
    items.push(item);
    return items.length;
  });

  // Update handler with validator - rejects invalid input before execution
  setHandler(
    addItemValidatedUpdate,
    (item: string) => {
      items.push(item);
      return items.length;
    },
    {
      validator: (item: string) => {
        if (!item) throw new Error('Item cannot be empty');
        if (items.length >= 100) throw new Error('Order is full');
      },
    }
  );

  await condition(() => completed);
  return `Order with ${items.length} items completed`;
}
```

**Important:** Validators must NOT mutate workflow state or do anything blocking (no activities, sleeps, or other commands). They are read-only, similar to query handlers. Throw an error to reject the update; return normally to accept.

## Child Workflows

```typescript
import { executeChild } from '@temporalio/workflow';

export async function parentWorkflow(orders: Order[]): Promise<string[]> {
  const results: string[] = [];

  for (const order of orders) {
    const result = await executeChild(processOrderWorkflow, {
      args: [order],
      workflowId: `order-${order.id}`,
    });
    results.push(result);
  }

  return results;
}
```

### Child Workflow Options

```typescript
import { executeChild, ParentClosePolicy, ChildWorkflowCancellationType } from '@temporalio/workflow';

const result = await executeChild(childWorkflow, {
  args: [input],
  workflowId: `child-${workflowInfo().workflowId}`,

  // ParentClosePolicy - what happens to child when parent closes
  // TERMINATE (default), ABANDON, REQUEST_CANCEL
  parentClosePolicy: ParentClosePolicy.TERMINATE,

  // ChildWorkflowCancellationType - how cancellation is handled
  // WAIT_CANCELLATION_COMPLETED (default), WAIT_CANCELLATION_REQUESTED, TRY_CANCEL, ABANDON
  cancellationType: ChildWorkflowCancellationType.WAIT_CANCELLATION_COMPLETED,
});
```

## Handles to External Workflows

```typescript
import { getExternalWorkflowHandle } from '@temporalio/workflow';
import { mySignal } from './other-workflows';

export async function coordinatorWorkflow(targetWorkflowId: string): Promise<void> {
  const handle = getExternalWorkflowHandle(targetWorkflowId);

  // Signal the external workflow
  await handle.signal(mySignal, { data: 'payload' });

  // Or cancel it
  await handle.cancel();
}
```

## Parallel Execution

```typescript
export async function parallelWorkflow(items: string[]): Promise<string[]> {
  return await Promise.all(
    items.map((item) => processItem(item))
  );
}
```

## Continue-as-New

```typescript
import { continueAsNew, workflowInfo } from '@temporalio/workflow';

export async function longRunningWorkflow(state: State): Promise<string> {
  while (true) {
    state = await processNextBatch(state);

    if (state.isComplete) {
      return 'done';
    }

    const info = workflowInfo();
    if (info.continueAsNewSuggested || info.historyLength > 10000) {
      await continueAsNew<typeof longRunningWorkflow>(state);
    }
  }
}
```

## Saga Pattern

**Important:** Compensation activities should be idempotent.

```typescript
import { CancellationScope, log } from '@temporalio/workflow';

export async function sagaWorkflow(order: Order): Promise<string> {
  const compensations: Array<() => Promise<void>> = [];

  try {
    // IMPORTANT: Save compensation BEFORE calling the activity
    // If activity fails after completing but before returning,
    // compensation must still be registered
    compensations.push(() => releaseInventory(order));
    await reserveInventory(order);

    compensations.push(() => refundPayment(order));
    await chargePayment(order);

    await shipOrder(order);
    return 'Order completed';
  } catch (err) {
    // nonCancellable ensures compensations run even if the workflow is cancelled
    await CancellationScope.nonCancellable(async () => {
      for (const compensate of compensations.reverse()) {
        try {
          await compensate();
        } catch (compErr) {
          log.warn('Compensation failed', { error: compErr });
        }
      }
    });
    throw err;
  }
}
```

## Cancellation Scopes

Cancellation scopes control how cancellation propagates to activities and child workflows. Use them for cleanup logic, timeouts, and manual cancellation.

```typescript
import { CancellationScope, sleep } from '@temporalio/workflow';

export async function scopedWorkflow(): Promise<void> {
  // Non-cancellable scope - runs even if workflow cancelled
  await CancellationScope.nonCancellable(async () => {
    await cleanupActivity();
  });

  // Timeout scope
  await CancellationScope.withTimeout('5 minutes', async () => {
    await longRunningActivity();
  });

  // Manual cancellation
  const scope = new CancellationScope();
  const promise = scope.run(() => someActivity());
  scope.cancel();
}
```

## Triggers (Promise-like Signals)

**WHY**: Triggers provide a one-shot promise that resolves when a signal is received. Cleaner than condition() for single-value signals.

**WHEN to use**:
- Waiting for a single response (approval, completion notification)
- Converting signal-based events into awaitable promises

```typescript
import { Trigger } from '@temporalio/workflow';

export async function triggerWorkflow(): Promise<string> {
  const approvalTrigger = new Trigger<boolean>();

  setHandler(approveSignal, (approved) => {
    approvalTrigger.resolve(approved);
  });

  const approved = await approvalTrigger;
  return approved ? 'Approved' : 'Rejected';
}
```

## Wait Condition with Timeout

```typescript
import { condition, CancelledFailure } from '@temporalio/workflow';

export async function approvalWorkflow(): Promise<string> {
  let approved = false;

  setHandler(approveSignal, () => {
    approved = true;
  });

  // Wait for approval with 24-hour timeout
  const gotApproval = await condition(() => approved, '24 hours');

  if (gotApproval) {
    return 'approved';
  } else {
    return 'auto-rejected due to timeout';
  }
}
```

## Waiting for All Handlers to Finish

Signal and update handlers should generally be non-async (avoid running activities from them). Otherwise, the workflow may complete before handlers finish their execution. However, making handlers non-async sometimes requires workarounds that add complexity.

When async handlers are necessary, use `condition(allHandlersFinished)` at the end of your workflow (or before continue-as-new) to prevent completion until all pending handlers complete.

```typescript
import { condition, allHandlersFinished } from '@temporalio/workflow';

export async function handlerAwareWorkflow(): Promise<string> {
  // ... main workflow logic ...

  // Before exiting, wait for all handlers to finish
  await condition(allHandlersFinished);
  return 'done';
}
```

## Activity Heartbeat Details

### WHY:
- **Support activity cancellation** - Cancellations are delivered via heartbeat; activities that don't heartbeat won't know they've been cancelled
- **Resume progress after worker failure** - Heartbeat details persist across retries

### WHEN:
- **Cancellable activities** - Any activity that should respond to cancellation
- **Long-running activities** - Track progress for resumability
- **Checkpointing** - Save progress periodically

```typescript
import { heartbeat, activityInfo, CancelledFailure } from '@temporalio/activity';

export async function processLargeFile(filePath: string): Promise<string> {
  const info = activityInfo();
  // Get heartbeat details from previous attempt (if any)
  const startLine: number = info.heartbeatDetails ?? 0;

  const lines = await readFileLines(filePath);

  try {
    for (let i = startLine; i < lines.length; i++) {
      await processLine(lines[i]);
      // Heartbeat with progress
      // If activity is cancelled, heartbeat() throws CancelledFailure
      heartbeat(i + 1);
    }
    return 'completed';
  } catch (e) {
    if (e instanceof CancelledFailure) {
      // Perform cleanup on cancellation
      await cleanup();
    }
    throw e;
  }
}
```

## Timers

```typescript
import { sleep } from '@temporalio/workflow';

export async function timerWorkflow(): Promise<string> {
  await sleep('1 hour');
  return 'Timer fired';
}
```

## Local Activities

**Purpose**: Reduce latency for short, lightweight operations by skipping the task queue. ONLY use these when necessary for performance. Do NOT use these by default, as they are not durable and distributed.

```typescript
import { proxyLocalActivities } from '@temporalio/workflow';
import type * as activities from './activities';

const { quickLookup } = proxyLocalActivities<typeof activities>({
  startToCloseTimeout: '5 seconds',
});

export async function localActivityWorkflow(): Promise<string> {
  const result = await quickLookup('key');
  return result;
}
```
