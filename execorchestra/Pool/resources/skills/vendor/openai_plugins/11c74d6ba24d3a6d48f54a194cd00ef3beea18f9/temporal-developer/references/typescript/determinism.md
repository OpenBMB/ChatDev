# TypeScript SDK Determinism

## Overview

The TypeScript SDK runs workflows in an isolated V8 sandbox that automatically provides determinism.

## Why Determinism Matters

Temporal provides durable execution through **History Replay**. When a Worker needs to restore workflow state (after a crash, cache eviction, or to continue after a long timer), it re-executes the workflow code from the beginning, which requires the workflow code to be **deterministic**.

## Temporal's V8 Sandbox

The Temporal TypeScript SDK executes all workflow code in sandbox, which (among other things), replaces common non-deterministic functions with deterministic variants. As an example, consider the code below:

```ts
export async function myWorkflow(): Promise<string> {
  await importData();

  if (Math.random() > 0.5) {
    await sleep('30 minutes');
  }

  return await sendReport();
}
```

The Temporal workflow sandbox will use the same random seed when replaying a workflow, so the above code will **deterministically** generate pseudo-random numbers. For UUIDs, use `uuid4()` from `@temporalio/workflow` which also uses the seeded PRNG.

See `references/typescript/determinism-protection.md` for more information about the sandbox.

## Forbidden Operations

```typescript
// DO NOT do these in workflows:
import fs from 'fs';           // Node.js modules
fetch('https://...');          // Network I/O
```

Most non-determinism and side effects, such as the above, should be wrapped in Activities.

## Testing Replay Compatibility

Use `Worker.runReplayHistory()` to verify your code changes are compatible with existing histories. See the Workflow Replay Testing section of `references/typescript/testing.md`.

## Best Practices

1. Use type-only imports for activities in workflow files
2. Match all @temporalio package versions
3. Prefer `sleep()` from workflow package — `setTimeout` works but `sleep()` handles cancellation scopes more clearly
4. Keep workflows focused on orchestration
5. Test with replay to verify determinism
