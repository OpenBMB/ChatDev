# Go SDK Versioning

For conceptual overview and guidance on choosing an approach, see `references/core/versioning.md`.

## GetVersion API

`workflow.GetVersion` safely performs backwards-incompatible changes to Workflow Definitions. It returns the version to branch on, recording the result as a marker in the Event History.

```go
v := workflow.GetVersion(ctx, "changeID", workflow.DefaultVersion, maxSupported)
```

- `changeID`: unique string identifying the change
- `minSupported`: oldest version still supported (`workflow.DefaultVersion` is `-1`)
- `maxSupported`: current/newest version
- Returns `maxSupported` for new executions; returns the recorded version on replay

### Three-Step Lifecycle

**Step 1: Add GetVersion with both code paths**

Original code calls `ActivityA`. You want to replace it with `ActivityC`:

```go
v := workflow.GetVersion(ctx, "Step1", workflow.DefaultVersion, 1)
if v == workflow.DefaultVersion {
	// Old code path (for replay of existing workflows)
	err = workflow.ExecuteActivity(ctx, ActivityA, data).Get(ctx, &result1)
} else {
	// New code path
	err = workflow.ExecuteActivity(ctx, ActivityC, data).Get(ctx, &result1)
}
```

For new executions, `GetVersion` returns `1` and records a marker. For replay of pre-change workflows (no marker), it returns `DefaultVersion` (`-1`).

**Step 2: Remove old branch (increase minSupported)**

After all `DefaultVersion` Workflow Executions have completed:

```go
v := workflow.GetVersion(ctx, "Step1", 1, 1)
// Only the new code path remains
err = workflow.ExecuteActivity(ctx, ActivityC, data).Get(ctx, &result1)
```

Keep the `GetVersion` call even with a single branch. This ensures:
1. If an older execution replays on this code, it fails fast instead of proceeding incorrectly
2. If you need further changes, you just bump `maxSupported`

**Step 3: Further changes (bump maxSupported)**

Later, replace `ActivityC` with `ActivityD`:

```go
v := workflow.GetVersion(ctx, "Step1", 1, 2)
if v == 1 {
	err = workflow.ExecuteActivity(ctx, ActivityC, data).Get(ctx, &result1)
} else {
	err = workflow.ExecuteActivity(ctx, ActivityD, data).Get(ctx, &result1)
}
```

After all version-1 executions complete, collapse again:

```go
_ = workflow.GetVersion(ctx, "Step1", 2, 2)
err = workflow.ExecuteActivity(ctx, ActivityD, data).Get(ctx, &result1)
```

### Using GetVersion in Loops

The return value for a given `changeID` is immutable once recorded. In loops, append the iteration number to the `changeID`:

```go
for i := 0; i < 10; i++ {
	v := workflow.GetVersion(ctx, fmt.Sprintf("myChange-%d", i), workflow.DefaultVersion, 1)
	if v == workflow.DefaultVersion {
		// old path
	} else {
		// new path
	}
}
```

## Workflow Type Versioning

Create a new Workflow Type for incompatible changes:

```go
// Original
func MyWorkflow(ctx workflow.Context, input Input) (string, error) {
	// v1 implementation
}

// New version
func MyWorkflowV2(ctx workflow.Context, input Input) (string, error) {
	// v2 implementation
}
```

Register both with the Worker:

```go
w := worker.New(c, "my-task-queue", worker.Options{})
w.RegisterWorkflow(MyWorkflow)
w.RegisterWorkflow(MyWorkflowV2)
```

Route new executions to the new type. Old workflows continue on the old type. Check for open executions before removing the old type:

```bash
temporal workflow list --query 'WorkflowType = "MyWorkflow" AND ExecutionStatus = "Running"'
```

## Worker Versioning

Worker Versioning manages versions at the deployment level, allowing multiple Worker versions to run simultaneously.

### Key Concepts

**Worker Deployment**: A logical service grouping similar Workers together (e.g., "loan-processor"). All versions of your code live under this umbrella.

**Worker Deployment Version**: A specific snapshot of your code identified by a deployment name and Build ID (e.g., "loan-processor:v1.0" or "loan-processor:abc123").

### Configuring Workers for Versioning

```go
w := worker.New(c, "my-task-queue", worker.Options{
	DeploymentOptions: worker.DeploymentOptions{
		UseVersioning: true,
		Version: worker.WorkerDeploymentVersion{
			DeploymentName: "my-service",
			BuildId:        "v1.0.0", // or git commit hash
		},
		DefaultVersioningBehavior: workflow.VersioningBehaviorPinned,
	},
})
```

**Configuration fields:**
- `UseVersioning`: enables Worker Versioning
- `Version`: identifies the Worker Deployment Version (deployment name + build ID)
- `DefaultVersioningBehavior`: `VersioningBehaviorPinned` or `VersioningBehaviorAutoUpgrade`
- Build ID: typically a git commit hash, version number, or timestamp

### PINNED vs AUTO_UPGRADE Behaviors

**PINNED Behavior**

Workflows stay locked to their original Worker version.

**When to use PINNED:**
- Short-running workflows (minutes to hours)
- Consistency is critical (e.g., financial transactions)
- You want to eliminate version compatibility complexity
- Building new applications and want simplest development experience

**AUTO_UPGRADE Behavior**

Workflows can move to newer versions.

**When to use AUTO_UPGRADE:**
- Long-running workflows (weeks or months)
- Workflows need to benefit from bug fixes during execution
- Migrating from traditional rolling deployments
- You are already using GetVersion for version transitions

**Important:** AUTO_UPGRADE workflows still need GetVersion to handle version transitions safely since they can move between Worker versions.

### Worker Configuration with Default Behavior

```go
// For short-running workflows, prefer PINNED
w := worker.New(c, "orders-task-queue", worker.Options{
	DeploymentOptions: worker.DeploymentOptions{
		UseVersioning: true,
		Version: worker.WorkerDeploymentVersion{
			DeploymentName: "order-service",
			BuildId:        os.Getenv("BUILD_ID"),
		},
		DefaultVersioningBehavior: workflow.VersioningBehaviorPinned,
	},
})
```

### Deployment Strategies

**Blue-Green Deployments**

Maintain two environments and switch traffic between them:
1. Deploy new code to idle environment
2. Run tests and validation
3. Switch traffic to new environment
4. Keep old environment for instant rollback

**Rainbow Deployments**

Multiple versions run simultaneously:
- New workflows use latest version
- Existing workflows complete on their original version
- Add new versions alongside existing ones
- Gradually sunset old versions as workflows complete

This works well with Kubernetes where you manage multiple ReplicaSets running different Worker versions.

Deploy a new version, then set it as current:

```bash
temporal worker deployment set-current-version \
  --deployment-name my-service \
  --build-id v2.0.0
```

### Querying Workflows by Worker Version

```bash
# Find workflows on a specific Worker version
temporal workflow list --query \
  'TemporalWorkerDeploymentVersion = "my-service:v1.0.0" AND ExecutionStatus = "Running"'
```

## Best Practices

1. **Keep GetVersion calls** even when only a single branch remains -- it guards against stale replays and simplifies future changes
2. **Use `TemporalChangeVersion` search attribute** to find Workflows running on old versions:
   ```bash
   temporal workflow list --query \
     'WorkflowType = "MyWorkflow" AND ExecutionStatus = "Running" AND TemporalChangeVersion = "Step1"'
   ```
3. **Test with replay** before removing old branches to verify determinism is preserved
4. **Prefer Worker Versioning** for large-scale deployments to avoid accumulating patching branches
