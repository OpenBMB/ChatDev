# Temporal Troubleshooting Guide

## Workflow Diagnosis Decision Tree

```
Workflow not behaving as expected?
│
├─▶ What is the workflow status?
│   │
│   ├─▶ RUNNING (but no progress)
│   │   └─▶ Go to: "Workflow Stuck" section
│   │
│   ├─▶ FAILED
│   │   └─▶ Go to: "Workflow Failed" section
│   │
│   ├─▶ TIMED_OUT
│   │   └─▶ Go to: "Timeout Issues" section
│   │
│   └─▶ COMPLETED (but wrong result)
│       └─▶ Go to: "Wrong Result" section
```

## Workflow Stuck (RUNNING but No Progress)

### Decision Tree

```
Workflow stuck in RUNNING?
│
├─▶ Is a worker running?
│   │
│   ├─▶ NO: Start a worker
│   │   └─▶ See references/core/dev-management.md
│   │
│   └─▶ YES: Is it on the correct task queue?
│       │
│       ├─▶ NO: Start worker with correct task queue
│       │
│       └─▶ YES: Check for non-determinism
│           │
│           ├─▶ NondeterminismError in logs?
│           │   └─▶ Go to: "Non-Determinism" section
│           │
│           ├─▶ Check history for task failures
│           │   └─▶ Run: `temporal workflow show --workflow-id <id>`
│           │       │
│           │       ├─▶ WorkflowTaskFailed event?
│           │       │   └─▶ Check error type in event details
│           │       │       └─▶ Go to relevant section in error-reference.md
│           │       │
│           │       └─▶ ActivityTaskFailed event?
│           │           └─▶ Go to: "Activity Keeps Retrying" section
│           │
│           └─▶ No errors in logs or history?
│               └─▶ Check if workflow is waiting for signal/timer
```

### Common Causes

1. **No worker running**
   - See references/core/dev-management.md

2. **Worker on wrong task queue**
   - Check: Worker logs for task queue name
   - Fix: Start worker with matching task queue

3. **Worker has stale code**
   - Check: Worker startup time vs code changes
   - Fix: Restart worker with updated code

4. **Workflow waiting for signal**
   - Check: Workflow history for pending signals
   - Fix: Send expected signal or check signal sender

5. **Activity stuck/timing out**
   - Check: Activity retry attempts in history
   - Fix: Investigate activity failure, increase timeout

## Non-Determinism Errors

### Decision Tree

```
NondeterminismError?
│
├─▶ Was code intentionally changed?
│   │
│   ├─▶ YES: Do you need to support in-flight workflows?
│   │   │
│   │   ├─▶ YES (production): Use patching API
│   │   │   └─▶ See: references/core/versioning.md
│   │   │
│   │   └─▶ NO (local dev/testing): Terminate or reset workflow
│   │       └─▶ `temporal workflow terminate --workflow-id <id>`
│   │       └─▶ Then start fresh with new code
│   │
│   └─▶ NO: Accidental change
│       │
│       ├─▶ Can you identify the change?
│       │   │
│       │   ├─▶ YES: Revert and restart worker. Note, this doesn't always work if workflow has progressed past the change (may induce other code paths), so may need to reset workflow.
│       │   │
│       │   └─▶ NO: Compare current code to expected history
│       │       └─▶ Check: Activity names, order, parameters
```

### Common Causes

1. **Changed call order**
   ```
   # Before           # After (BREAKS)
   await activity_a   await activity_b
   await activity_b   await activity_a
   ```

2. **Changed call name**
   ```
   # Before                    # After (BREAKS)
   await process_order(...)    await handle_order(...)
   ```

3. **Added/removed call**
   - Adding new activity mid-workflow
   - Removing activity that was previously called

4. **Using non-deterministic code**
   - `datetime.now()` in workflow (use `workflow.now()`)
   - `random.random()` in workflow (use `workflow.random()`)

### Recovery

**Accidental Change:**
1. Identify the change
2. Revert code to match history
3. Restart worker
4. Workflow automatically recovers

**Intentional Change:**
1. Use patching API for gradual migration
2. Or terminate old workflows, start new ones

## Workflow Failed

### Decision Tree

```
Workflow status = FAILED?
│
├─▶ Check workflow error message
│   │
│   ├─▶ Application error (your code)
│   │   └─▶ Fix the bug, start new workflow
│   │
│   ├─▶ NondeterminismError
│   │   └─▶ Go to: "Non-Determinism" section
│   │
│   └─▶ Timeout error
│       └─▶ Go to: "Timeout Issues" section
```

### Common Causes

1. **Unhandled exception in workflow**
   - Check error message and stack trace
   - Fix bug in workflow code

2. **Activity exhausted retries**
   - All retry attempts failed
   - Check activity logs for root cause

3. **Non-retryable error thrown**
   - Error marked as non-retryable
   - Intentional failure, check business logic

## Timeout Issues

### Timeout Types

| Timeout | Scope | What It Limits |
|---------|-------|----------------|
| `WorkflowExecutionTimeout` | Entire workflow | Total time including retries and continue-as-new |
| `WorkflowRunTimeout` | Single run | Time for one run (before continue-as-new) |
| `ScheduleToCloseTimeout` | Activity | Total time including retries |
| `StartToCloseTimeout` | Activity | Single attempt time |
| `HeartbeatTimeout` | Activity | Time between heartbeats |

### Diagnosis

```
Timeout error?
│
├─▶ Which timeout?
│   │
│   ├─▶ Workflow timeout
│   │   └─▶ Increase timeout or optimize workflow. Better yet, consider removing the workflow timeout, as it is generally discouraged unless *necessary* for your use case.
│   │
│   ├─▶ ScheduleToCloseTimeout
│   │   └─▶ Activity taking too long overall (including retries)
│   │
│   ├─▶ StartToCloseTimeout
│   │   └─▶ Single activity attempt too slow
│   │
│   └─▶ HeartbeatTimeout
│       └─▶ Activity not heartbeating frequently enough
│           └─▶ Add heartbeat() calls in long activities
```

### Fixes

1. **Increase timeout** if operation legitimately takes longer
2. **Add heartbeats** to long-running activities
3. **Optimize activity** to complete faster
4. **Break into smaller activities** for better granularity

## Activity Keeps Retrying

### Decision Tree

```
Activity retrying repeatedly?
│
├─▶ Check activity error
│   │
│   ├─▶ Transient error (network, timeout)
│   │   └─▶ Expected behavior, will eventually succeed
│   │
│   ├─▶ Permanent error (bug, invalid input)
│   │   └─▶ Fix the bug or mark as non-retryable
│   │
│   └─▶ Resource exhausted
│       └─▶ Add backoff, check rate limits
```

### Common Causes

1. **Bug in activity code**
   - Fix the bug
   - Consider marking certain errors as non-retryable

2. **External service down**
   - Retries are working as intended
   - Monitor service recovery

3. **Invalid input**
   - Validate inputs before activity
   - Return non-retryable error for bad input

## Wrong Result (Completed but Incorrect)

### Diagnosis

1. **Check workflow history** for unexpected activity results
2. **Verify activity implementations** produce correct output
3. **Check for race conditions** in parallel execution
4. **Verify signal handling** if signals are involved

### Common Causes

1. **Activity bug** - Wrong logic in activity
2. **Stale data** - Activity using outdated information
3. **Signal ordering** - Signals processed in unexpected order
4. **Parallel execution** - Race condition in concurrent operations

## Worker Issues

### Worker Not Starting

```
Worker won't start?
│
├─▶ Connection error
│   └─▶ Check Temporal server is running
│       └─▶ `temporal server start-dev` (start in background, see references/core/dev-management.md)
│
├─▶ Registration error
│   └─▶ Check workflow/activity definitions are valid
│
└─▶ Other errors (imports, etc.)
    └─▶ Debug those errors as usual.
```

### Worker Crashing

1. **Out of memory** - Reduce concurrent tasks, check for leaks
2. **Unhandled exception** - Add error handling
3. **Dependency issue** - Check package versions

## Useful Commands

```bash
# Check Temporal server
temporal server start-dev

# List workflows
temporal workflow list

# Describe specific workflow
temporal workflow describe --workflow-id <id>

# Show workflow history
temporal workflow show --workflow-id <id>

# Terminate stuck workflow
temporal workflow terminate --workflow-id <id>

# Reset workflow to specific point
temporal workflow reset --workflow-id <id> --event-id <event-id>
```

## Quick Reference: Status → Action

| Status | First Check | Common Fix |
|--------|-------------|------------|
| RUNNING (stuck) | Worker running? | Start/restart worker |
| FAILED | Error message | Fix bug, handle error |
| TIMED_OUT | Which timeout? | Increase timeout or optimize |
| TERMINATED | Who terminated? | Check audit log |
| CANCELED | Cancellation source | Expected or investigate |

## See Also

- [Common Gotchas](gotchas.md) - Anti-patterns that cause these issues
- [Error Reference](error-reference.md) - Quick error type lookup
