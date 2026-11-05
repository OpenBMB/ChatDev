# TypeScript Workflow V8 Sandboxing

## Overview

The TypeScript SDK runs workflows in a V8 sandbox that provides automatic protection against non-deterministic operations, and replaces common non-deterministic function calls with deterministic variants.

## Import Blocking

The sandbox blocks imports of `fs`, `https` modules, and any Node/DOM APIs. Otherwise, workflow code can import any package as long as it does not reference Node.js or DOM APIs.

**Note**: If you must use a library that references a Node.js or DOM API and you are certain that those APIs are not used at runtime, add that module to the `ignoreModules` list:

```ts
const worker = await Worker.create({
  workflowsPath: require.resolve('./workflows'), // bundlerOptions only apply with workflowsPath
  activities: require('./activities'),
  taskQueue: 'my-task-queue',
  bundlerOptions: {
    // These modules may be imported (directly or transitively),
    // but will be excluded from the Workflow bundle.
    ignoreModules: ['fs', 'http', 'crypto'],
  },
});
```

**Important**: Excluded modules are completely unavailable at runtime. Any attempt to call functions from these modules will throw an error. Only exclude modules when you are certain the code paths using them will never execute during workflow execution.

**Note**: Modules with the `node:` prefix (e.g., `node:fs`) require additional webpack configuration to ignore. You may need to configure the bundler's `externals` or use webpack `resolve.alias` to handle these imports.

Use this with *extreme caution*.


## Function Replacement

Functions like `Math.random()`, `Date`, and `setTimeout()` are replaced by deterministic versions.

Date-related functions return the timestamp at which the current workflow task was initially executed. That timestamp remains the same when the workflow task is replayed, and only advances when a durable operation occurs (like `sleep()`). For example:

```ts
import { sleep } from '@temporalio/workflow';

// this prints the *exact* same timestamp repeatedly
for (let x = 0; x < 10; ++x) {
  console.log(Date.now());
}

// this prints timestamps increasing roughly 1s each iteration
for (let x = 0; x < 10; ++x) {
  await sleep('1 second');
  console.log(Date.now());
}
```

Generally, this is the behavior you want.

Additionally, `FinalizationRegistry` and `WeakRef` are removed because v8's garbage collector is not deterministic.
