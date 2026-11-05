# Temporal TypeScript SDK Reference

## Overview

The Temporal TypeScript SDK provides a modern Promise based approach to building durable workflows. Workflows are bundled and run in an isolated runtime with automatic replacements for determinism protection.

**CRITICAL**: All `@temporalio/*` packages must have the same version number.

## Understanding Replay

Temporal workflows are durable through history replay. For details on how this works, see `references/core/determinism.md`.

## Quick Start

**Add Dependencies:** Install the Temporal SDK packages (use the package manager appropriate for your project):
```bash
npm install @temporalio/client @temporalio/worker @temporalio/workflow @temporalio/activity
```

Note: if you are working in production, it is strongly advised to use ~ version constraints, i.e.  `npm install ... --save-prefix='~'` if using NPM.

**activities.ts** - Activity definitions (separate file to distinguish workflow vs activity code):
```typescript
export async function greet(name: string): Promise<string> {
  return `Hello, ${name}!`;
}
```

**workflows.ts** - Workflow definition (use type-only imports for activities):
```typescript
import { proxyActivities } from '@temporalio/workflow';
import type * as activities from './activities';

const { greet } = proxyActivities<typeof activities>({
  startToCloseTimeout: '1 minute',
});

export async function greetingWorkflow(name: string): Promise<string> {
  return await greet(name);
}
```

**worker.ts** - Worker setup (imports activities and workflows, runs indefinitely):
```typescript
import { Worker } from '@temporalio/worker';
import * as activities from './activities';

async function run() {
  const worker = await Worker.create({
    workflowsPath: require.resolve('./workflows'), // For production, use workflowBundle instead
    activities,
    taskQueue: 'greeting-queue',
  });
  await worker.run();
}

run().catch(console.error);
```

**Start the dev server:** Start `temporal server start-dev` in the background.

**Start the worker:** Run `npx ts-node worker.ts` in the background.

**client.ts** - Start a workflow execution:
```typescript
import { Client } from '@temporalio/client';
import { greetingWorkflow } from './workflows';
import { v4 as uuid } from 'uuid';

async function run() {
  const client = new Client();

  const result = await client.workflow.execute(greetingWorkflow, {
    workflowId: uuid(),
    taskQueue: 'greeting-queue',
    args: ['my name'],
  });

  console.log(`Result: ${result}`);
}

run().catch(console.error);
```

**Run the workflow:** Run `npx ts-node client.ts`. Should output: `Result: Hello, my name!`.

## Key Concepts

### Workflow Definition
- Async functions exported from workflow file
- Use `proxyActivities()` with type-only imports
- Use `defineSignal()`, `defineQuery()`, `defineUpdate()`, `setHandler()` for handlers

### Activity Definition
- Regular async functions
- Can perform I/O, network calls, etc.
- Use `heartbeat()` for long operations

### Worker Setup
- Use `Worker.create()` with `workflowsPath` (dev) or `workflowBundle` (production) - see `references/typescript/gotchas.md`
- Import activities directly (not via proxy)

## File Organization Best Practice

**Keep Workflow definitions in separate files from Activity definitions.** The TypeScript SDK bundles workflow files separately. Minimizing workflow file contents improves Worker startup time.

```
my_temporal_app/
├── workflows/
│   └── greeting.ts      # Only Workflow functions
├── activities/
│   └── translate.ts     # Only Activity functions
├── worker.ts            # Worker setup, imports both
└── client.ts            # Client code to start workflows
```

**In the Workflow file, use type-only imports for activities:**
```typescript
// workflows/greeting.ts
import { proxyActivities } from '@temporalio/workflow';
import type * as activities from '../activities/translate';

const { translate } = proxyActivities<typeof activities>({
  startToCloseTimeout: '1 minute',
});
```

## Determinism Rules

The TypeScript SDK runs workflows in an isolated V8 sandbox.

**Automatic replacements:**
- `Math.random()` → deterministic seeded PRNG
- `Date.now()` → workflow start time
- `setTimeout` → deterministic timer

**Safe to use:**
- `sleep()` from `@temporalio/workflow`
- `condition()` for waiting
- Standard JavaScript operations

See `references/typescript/determinism.md` for detailed rules.

## Common Pitfalls

1. **Importing activities without `type`** - Use `import type * as activities`
2. **Version mismatch** - All @temporalio packages must match
3. **Direct I/O in workflows** - Use activities for external calls
4. **Missing `proxyActivities`** - Required to call activities from workflows
5. **Forgetting to bundle workflows** - Worker needs `workflowsPath` or `workflowBundle`
6. **Using workflowsPath in production** - Use `workflowBundle` for production (see `references/typescript/gotchas.md`)
7. **Forgetting to heartbeat** - Long-running activities need `heartbeat()` calls
8. **Logging in workflows** - For observability, use `import { log } from '@temporalio/workflow'` (routes through sinks). For temporary print debugging, `console.log()` is fine—it's direct and immediate, whereas `log` may lose messages on workflow errors.
9. **Forgetting to wait on activity calls** - Activity calls return Promises; you must eventually await them (directly or via `Promise.all()` for parallel execution)

## Writing Tests

See `references/typescript/testing.md` for info on writing tests.

## Additional Resources

### Reference Files
- **`references/typescript/patterns.md`** - Signals, queries, child workflows, saga pattern, etc.
- **`references/typescript/determinism.md`** - Essentials of determinism in TypeScript
- **`references/typescript/gotchas.md`** - TypeScript-specific mistakes and anti-patterns
- **`references/typescript/error-handling.md`** - ApplicationFailure, retry policies, non-retryable errors
- **`references/typescript/observability.md`** - Logging, metrics, tracing
- **`references/typescript/testing.md`** - TestWorkflowEnvironment, time-skipping, activity mocking
- **`references/typescript/advanced-features.md`** - Schedules, worker tuning, and more
- **`references/typescript/data-handling.md`** - Data converters, payload encryption, etc.
- **`references/typescript/versioning.md`** - Patching API, workflow type versioning, Worker Versioning
- **`references/typescript/determinism-protection.md`** - V8 sandbox and bundling
