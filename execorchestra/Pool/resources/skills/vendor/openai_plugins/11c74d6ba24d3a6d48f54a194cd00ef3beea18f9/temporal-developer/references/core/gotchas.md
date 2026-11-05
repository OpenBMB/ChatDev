# Common Temporal Gotchas

Common mistakes and anti-patterns in Temporal development. Learning from these saves significant debugging time.

This document provides a general overview of conceptual-level gotchas in Temporal. The exact form that these take and symptoms can vary by SDK language. See `references/{your_language}/gotchas.md` for language-specific info on common mistakes.

## Non-Idempotent Activities

**The Problem**: Activities may execute more than once due to retries or Worker failures. If an activity calls an external service without an idempotency key, you may charge a customer twice, send duplicate emails, or create duplicate records.

**Symptoms**:
- Duplicate side effects (double charges, duplicate notifications)
- Data inconsistencies after retries

**The Fix**: Always use idempotency keys when calling external services. Use the workflow ID, activity ID, or a domain-specific identifier (like order ID) as the key.

**Note:** Local Activities skip the task queue for lower latency, but they're still subject to retries. The same idempotency rules apply.

## Side Effects & Non-Determinism in Workflow Code

**The Problem**: Code in workflow functions runs on first execution AND on every replay. Any side effect (logging, notifications, metrics, etc.) will happen multiple times and non-deterministic code (IO, current time, random numbers, threading, etc.) won't replay correctly.

**Symptoms**:
- Non-determinism errors
- Sandbox violations, depending on SDK language
- Duplicate log entries
- Multiple notifications for the same event
- Inflated metrics

**The Fix**:
- Use Temporal replay-aware managed side effects for common, non-business logic cases:
    - Temporal workflow logging
    - Temporal date time
    - Temporal UUID generation
    - Temporal random number generation
- Put all other side effects in Activities

See `references/core/determinism.md` for more info.

## Multiple Workers with Different Code

**The Problem**: If Worker A runs part of a workflow with code v1, then Worker B (with code v2) picks it up, replay may produce different Commands.

**Symptoms**:
- Non-determinism errors after deploying new code
- Errors mentioning "command mismatch" or "unexpected command"

**The Fix**:
- Use Worker Versioning for production deployments
- Use patching APIs
- During development: kill old workers before starting new ones
- Ensure all workers run identical code

**Note:** Workflows started with old code continue running after you change the code, which can then induce the above issues. During development (NOT production), you may want to terminate stale workflows (`temporal workflow terminate --workflow-id <id>`).

See `references/core/versioning.md` for more info.

## Failing Activities Too Quickly

**The Problem**: Using aggressive activity retry policies that give up too easily.

**Symptoms**:
- Workflows failing on transient errors
- Unnecessary workflow failures during brief outages

**The Fix**: Use appropriate activity retry policies. Let Temporal handle transient failures with exponential backoff. Reserve `maximum_attempts=1` for truly non-retryable operations.

## Query Handler & Update Validator Mistakes

### Modifying State in Queries & Update Validators

**The Problem**: Queries and update validators are read-only. Modifying state causes non-determinism on replay, and must strictly be avoided.

**Symptoms**:
- State inconsistencies after workflow replay
- Non-determinism errors

**The Fix**: Queries and update validators must only read state. Use Updates for operations that need to modify state AND return a result.

### Blocking in Queries & Update Validators

**The Problem**: Queries and update validators must return immediately. They cannot await activities, child workflows, timers, or conditions.

**Symptoms**:
- Query / update validators timeouts
- Deadlocks

**The Fix**: Queries and update validators must only look at current state. Use Signals or Updates to trigger async operations.

### Query vs Signal vs Update

| Operation | Modifies State? | Returns Result? | Can Block? | Use For |
|-----------|-----------------|-----------------|------------|---------|
| **Query** | No | Yes | No | Read current state |
| **Signal** | Yes | No | Yes | Fire-and-forget mutations |
| **Update** | Yes | Yes | Yes | Mutations needing results |

**Key rule**: Query to peek, Signal to push, Update to pop.

## File Organization Issues

Each SDK has specific requirements for how workflow and activity code should be organized. Mixing them incorrectly causes sandbox issues, bundling problems, or performance degradation.

See language-specific gotchas for details.

## Testing Mistakes

### Only Testing Happy Paths

**The Problem**: Not testing what happens when things go wrong.

**Questions to answer**:
- What happens when an Activity exhausts all retries?
- What happens when a workflow is cancelled mid-execution?
- What happens during a Worker restart?

**The Fix**: Test failure scenarios explicitly. Mock activities to fail, test cancellation handling, use replay testing.

### Not Testing Replay Compatibility

**The Problem**: Changing workflow code without verifying existing workflows can still replay.

**Symptoms**:
- Non-determinism errors after deployment
- Stuck workflows that can't make progress

**The Fix**: Use replay testing against saved histories from production or staging.

## Error Handling Mistakes

### Swallowing Errors

**The Problem**: Catching errors without proper handling hides failures.

**Symptoms**:
- Silent failures
- Workflows completing "successfully" despite errors
- Difficult debugging

**The Fix**: Log errors and make deliberate decisions. Either re-raise, use a fallback, or explicitly document why ignoring is safe.

### Wrong Retry Classification

**The Problem**: Marking transient errors as non-retryable, or permanent errors as retryable.

**Symptoms**:
- Workflows failing on temporary network issues (if marked non-retryable)
- Infinite retries on invalid input (if marked retryable)

**The Fix**:
- **Retryable**: Network errors, timeouts, rate limits, temporary unavailability
- **Non-retryable**: Invalid input, authentication failures, business rule violations, resource not found

## Cancellation Handling

### Not Handling Workflow Cancellation

**The Problem**: When a workflow is cancelled, cleanup code after the cancellation point doesn't run unless explicitly protected.

**Symptoms**:
- Resources not released after cancellation
- Incomplete compensation/rollback
- Leaked state

**The Fix**: Use language-specific cancellation scopes or try/finally blocks to ensure cleanup runs even on cancellation. See language-specific gotchas for implementation details.

### Not Handling Activity Cancellation

**The Problem**: Activities must opt in to receive cancellation. Without proper handling, a cancelled activity continues running to completion, wasting resources.

**Requirements for activity cancellation**:
1. **Heartbeating** - Cancellation is delivered via heartbeat. Activities that don't heartbeat won't know they've been cancelled.
2. **Checking for cancellation** - Activity must explicitly check for cancellation or await a cancellation signal.

**Symptoms**:
- Cancelled activities running to completion
- Wasted compute on work that will be discarded
- Delayed workflow cancellation

**The Fix**: Heartbeat regularly and check for cancellation. See language-specific gotchas for implementation patterns.

## Payload Size Limits

**The Problem**: Temporal has built-in limits on payload sizes. Exceeding them causes workflows to fail.

**Limits**:
- Max 2MB per individual payload
- Max 4MB per gRPC message
- Max 50MB for complete workflow history (aim for <10MB in practice)

**Symptoms**:
- Payload too large errors
- gRPC message size exceeded errors
- Workflow history growing unboundedly

**The Fix**: Store large data externally (S3/GCS) and pass references, use compression codecs, or chunk data across multiple activities. See the Large Data Handling pattern in `references/core/patterns.md`.
