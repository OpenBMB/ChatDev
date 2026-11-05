# TypeScript SDK Versioning

For conceptual overview and guidance on choosing an approach, see `references/core/versioning.md`.

## Patching API

The Patching API lets you change Workflow Definitions without causing non-deterministic behavior in running Workflows.

### The patched() Function

The `patched()` function takes a `patchId` string and returns a boolean:

```typescript
import { patched } from '@temporalio/workflow';

export async function myWorkflow(): Promise<void> {
  if (patched('my-change-id')) {
    // New code path
    await newImplementation();
  } else {
    // Old code path (for replay of existing executions)
    await oldImplementation();
  }
}
```

**How it works:**
- If the Workflow is running for the first time, `patched()` returns `true` and inserts a marker into the Event History
- During replay, if the history contains a marker with the same `patchId`, `patched()` returns `true`
- During replay, if no matching marker exists, `patched()` returns `false`

**TypeScript-specific behavior:** Unlike Python/.NET/Ruby, `patched()` is not memoized when it returns `false`. This means you can use `patched()` in loops. However, if a single patch requires coordinated behavioral changes at different points in your workflow, you may need to manually memoize the result:

```typescript
const useNewBehavior = patched('my-change');
// Use useNewBehavior at multiple points in workflow
```

### Three-Step Patching Process

Patching is a three-step process for safely deploying changes.

**Warning:** Failing to follow this process correctly will result in non-determinism errors for in-flight workflows.

#### Step 1: Patch in New Code

Add the patch alongside the old code:

```typescript
import { patched } from '@temporalio/workflow';

// Original code sent fax notifications
export async function shippingConfirmation(): Promise<void> {
  if (patched('changedNotificationType')) {
    await sendEmail();  // New code
  } else {
    await sendFax();    // Old code for replay
  }
  await sleep('1 day');
}
```

#### Step 2: Deprecate the Patch

Once all Workflows using the old code have completed, deprecate the patch:

```typescript
import { deprecatePatch } from '@temporalio/workflow';

export async function shippingConfirmation(): Promise<void> {
  deprecatePatch('changedNotificationType');
  await sendEmail();
  await sleep('1 day');
}
```

The `deprecatePatch()` function records a marker that does not fail replay when Workflow code does not emit it, allowing a transition period.

#### Step 3: Remove the Patch

After all Workflows using `deprecatePatch` have completed, remove it entirely:

```typescript
export async function shippingConfirmation(): Promise<void> {
  await sendEmail();
  await sleep('1 day');
}
```

### Query Filters for Versioned Workflows

Use List Filters to find Workflows by version:

```
# Find running Workflows with a specific patch
WorkflowType = "shippingConfirmation" AND ExecutionStatus = "Running" AND TemporalChangeVersion = "changedNotificationType"

# Find running Workflows without the patch (started before patching)
WorkflowType = "shippingConfirmation" AND ExecutionStatus = "Running" AND TemporalChangeVersion IS NULL
```

## Workflow Type Versioning

An alternative to patching is creating new Workflow functions for incompatible changes:

```typescript
// Original Workflow
export async function pizzaWorkflow(order: PizzaOrder): Promise<OrderConfirmation> {
  // Original implementation
}

// New version with incompatible changes
export async function pizzaWorkflowV2(order: PizzaOrder): Promise<OrderConfirmation> {
  // Updated implementation
}
```

Register both Workflows with the Worker:

```typescript
const worker = await Worker.create({
  workflowsPath: require.resolve('./workflows'), // Use workflowBundle for production
  taskQueue: 'pizza-queue',
});
```

Update client code to start new Workflows with the new type:

```typescript
// Start new executions with V2
await client.workflow.start(pizzaWorkflowV2, {
  workflowId: 'order-123',
  taskQueue: 'pizza-queue',
  args: [order],
});
```

Use List Filters to check for remaining V1 executions:

```
WorkflowType = "pizzaWorkflow" AND ExecutionStatus = "Running"
```

After all V1 executions complete, remove the old Workflow function.

## Worker Versioning

Worker Versioning allows multiple Worker versions to run simultaneously, routing Workflows to specific versions without code-level patching. Workflows are pinned to the Worker Deployment Version they started on.

> **Note:** Worker Versioning is currently in Public Preview. The legacy Worker Versioning API (before 2025) will be removed from Temporal Server in March 2026.

### Key Concepts

- **Worker Deployment**: A logical name for your application (e.g., "order-service")
- **Worker Deployment Version**: A specific build identified by deployment name + Build ID
- **Workflow Pinning**: Workflows complete on the Worker Deployment Version they started on

### Configuring Workers for Versioning

```typescript
import { Worker, NativeConnection } from '@temporalio/worker';

const worker = await Worker.create({
  workflowsPath: require.resolve('./workflows'),  // Use workflowBundle for production
  taskQueue: 'my-queue',
  connection: await NativeConnection.connect({ address: 'temporal:7233' }),
  workerDeploymentOptions: {
    useWorkerVersioning: true,
    version: {
      deploymentName: 'order-service',
      buildId: '1.0.0',  // Git hash, semver, build number, etc.
    },
  },
});
```

**Configuration options:**
- `useWorkerVersioning`: Enables Worker Versioning
- `version.deploymentName`: Logical name for your service (consistent across versions)
- `version.buildId`: Unique identifier for this build

### Deployment Workflow

1. Deploy new Worker version with a new `buildId`
2. Use the Temporal CLI to set the new version as current:
   ```bash
   temporal worker deployment set-current-version \
     --deployment-name order-service \
     --build-id 2.0.0
   ```
3. New Workflows start on the new version
4. Existing Workflows continue on their original version until completion
5. Decommission old Workers once all their Workflows complete

### When to Use Worker Versioning

Worker Versioning is best suited for:
- **Short-running Workflows**: Old Workers only need to run briefly during deployment transitions
- **Frequent deployments**: Eliminates the need for code-level patching on every change
- **Blue-green deployments**: Run old and new versions simultaneously with traffic control

For long-running Workflows, consider combining Worker Versioning with the Patching API, or use Continue-as-New to move Workflows to newer versions.

## Best Practices

1. Use descriptive `patchId` names that explain the change
2. Follow the three-step patching process completely before removing patches
3. Use List Filters to verify no running Workflows before removing version support
4. Keep Worker Deployment names consistent across all versions
5. Use unique, traceable Build IDs (git hashes, semver, timestamps)
6. Test version transitions with replay tests before deploying
