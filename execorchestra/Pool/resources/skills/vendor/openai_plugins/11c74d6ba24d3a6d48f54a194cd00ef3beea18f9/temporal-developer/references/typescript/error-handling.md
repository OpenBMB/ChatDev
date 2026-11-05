# TypeScript SDK Error Handling

## Overview

The TypeScript SDK uses `ApplicationFailure` for application errors with support for non-retryable marking.

## Application Failures

```typescript
import { ApplicationFailure } from '@temporalio/workflow';

export async function myWorkflow(): Promise<void> {
  throw ApplicationFailure.create({
    message: 'Invalid input',
    type: 'ValidationError',
    nonRetryable: true,
  });
}
```

## Activity Errors

```typescript
import { ApplicationFailure } from '@temporalio/activity';

export async function validateActivity(input: string): Promise<void> {
  if (!isValid(input)) {
    throw ApplicationFailure.create({
      message: `Invalid input: ${input}`,
      type: 'ValidationError',
      nonRetryable: true,
    });
  }
}
```

## Handling Errors in Workflows

```typescript
import { proxyActivities, ApplicationFailure, log } from '@temporalio/workflow';
import type * as activities from './activities';

const { riskyActivity } = proxyActivities<typeof activities>({
  startToCloseTimeout: '5 minutes',
});

export async function workflowWithErrorHandling(): Promise<string> {
  try {
    return await riskyActivity();
  } catch (err) {
    if (err instanceof ApplicationFailure) {
      log.warn('Activity failed', { type: err.type, message: err.message });
    }
    throw err;
  }
}
```

## Retry Configuration

```typescript
const { myActivity } = proxyActivities<typeof activities>({
  startToCloseTimeout: '10 minutes',
  retry: {
    initialInterval: '1s',
    backoffCoefficient: 2,
    maximumInterval: '1m',
    maximumAttempts: 5,
    nonRetryableErrorTypes: ['ValidationError', 'PaymentError'],
  },
});
```

**Note:** Only set retry options if you have a domain-specific reason to. The defaults are suitable for most use cases.

## Timeout Configuration

```typescript
const { myActivity } = proxyActivities<typeof activities>({
  startToCloseTimeout: '5 minutes',      // Single attempt
  scheduleToCloseTimeout: '30 minutes',  // Including retries
  heartbeatTimeout: '30 seconds',        // Between heartbeats
});
```

## Workflow Failure

Workflows can throw errors to indicate failure:

```typescript
import { ApplicationFailure } from '@temporalio/workflow';

export async function myWorkflow(): Promise<string> {
  if (someCondition) {
    throw ApplicationFailure.create({
      message: 'Workflow failed due to invalid state',
      type: 'InvalidStateError',
    });
  }
  return 'success';
}
```

**Warning:** Do NOT use `nonRetryable: true` for workflow failures in most cases. Unlike activities, workflow retries are controlled by the caller, not retry policies. Use `nonRetryable` only for errors that are truly unrecoverable (e.g., invalid input that will never be valid).

## Idempotency

For idempotency patterns (using keys, making activities granular), see `core/patterns.md`.

## Best Practices

1. Use specific error types for different failure modes
2. Set `nonRetryable: true` for permanent failures in activities
3. Configure `nonRetryableErrorTypes` in retry policy
4. Log errors before re-raising
5. Use `ApplicationFailure` to catch activity failures in workflows
6. Use the appropriate `log` import for your context:
   - In workflows: `import { log } from '@temporalio/workflow'` (replay-safe)
   - In activities: `import { log } from '@temporalio/activity'`
