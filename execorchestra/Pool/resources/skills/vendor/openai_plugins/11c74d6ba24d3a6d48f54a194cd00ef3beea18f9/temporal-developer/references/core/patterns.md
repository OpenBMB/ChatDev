# Temporal Workflow Patterns

## Overview

Common patterns for building robust Temporal workflows.
See the language-specific references for the language you are working in:
- `references/{language}/{language}.md` for the root level documentation for that language
- `references/{language}/patterns.md` for language-specific example code of the patterns in this file.

## Signals

**Purpose**: Send data to a running workflow asynchronously (fire-and-forget).

**When to Use**:
- Human approval workflows
- Adding items to a workflow's queue
- Notifying workflow of external events
- Live configuration updates

**Characteristics**:
- Asynchronous - sender doesn't wait for response
- Can mutate workflow state
- Durable - signals are persisted in history
- Can be sent before workflow starts (signal-with-start)

**Example Flow**:
```
Client                    Workflow
  │                          │
  │──── signal(approve) ────▶│
  │                          │ (updates state)
  │                          │
  │◀──── (no response) ──────│
```

**Note:** A related but distinct pattern to signals is async activity completion. This is an advanced feature, which you may consider if the external system that would deliver the signal is unreliable and might fail to Signal, or
you want the external process to Heartbeat or receive Cancellation. If this may be the case, look at language-specific advanced features for your SDK language (`references/{your_language}/advanced-features.md`).

## Queries

**Purpose**: Read workflow state synchronously without modifying it.

**When to Use**:
- Building dashboards showing workflow progress
- Health checks and monitoring
- Debugging workflow state
- Exposing current status to external systems

**Characteristics**:
- Synchronous - caller waits for response
- Read-only - must not modify state
- Not recorded in history
- Executes on the worker, not persisted
- Can run even on completed workflows

**Example Flow**:
```
Client                    Workflow
  │                          │
  │──── query(status) ──────▶│
  │                          │ (reads state)
  │◀──── "processing" ───────│
```

## Updates

**Purpose**: Modify workflow state and receive a response synchronously.

**When to Use**:
- Operations that need confirmation (add item, return count)
- Validation before accepting changes
- Replace signal+query combinations
- Request-response patterns within workflow

**Characteristics**:
- Synchronous - caller waits for completion
- Can mutate state AND return values
- Supports validators to reject invalid updates before they even get persisted into history
- **Validators must NOT mutate workflow state or block** (no activities, sleeps, or commands) — they are read-only, similar to query handlers
- Recorded in history

**Example Flow**:
```
Client                    Workflow
  │                          │
  │──── update(addItem) ────▶│
  │                          │ (validates, modifies state)
  │◀──── {count: 5} ─────────│
```

## Child Workflows

**When to Use**:
- Prevent history from growing too large
- Isolate failure domains (child can fail without failing parent)
- Different retry policies for different parts

**Characteristics**:
- Own history (doesn't bloat parent)
- Independent lifecycle options (ParentClosePolicy)
- Can be cancelled independently
- Results returned to parent

**Parent Close Policies**:
- `TERMINATE` - Child terminated when parent closes (default)
- `ABANDON` - Child continues running independently
- `REQUEST_CANCEL` - Cancellation requested but not forced

**Note:** Do not need to use child workflows simply for breaking complex logic down into smaller pieces. Standard programming abstractions within a workflow can already be used for that.

## Continue-as-New

**Purpose**: Prevent unbounded history growth by "restarting" with fresh history.

**When to Use**:
- Long-running workflows (entity workflows, subscriptions)
- Workflows with many iterations
- When history approaches 10,000+ events
- Periodic cleanup of accumulated state

**How It Works**:
```
Workflow (history: 10,000 events)
    │
    │ continueAsNew(currentState)
    ▼
New Workflow Execution (history: 0 events)
    │ (same workflow ID, fresh history)
    │ (receives currentState as input)
```

**Best Practice**: Check `historyLength` or `continueAsNewSuggested` periodically.

## Saga Pattern

**Purpose**: Distributed transactions with compensation for failures.

**When to Use**:
- Multi-step operations that span services
- Operations requiring rollback on failure
- Financial transactions, order processing
- Booking systems with multiple reservations

**How It Works**:
```
Step 1: Reserve inventory
  └─ Compensation: Release inventory

Step 2: Charge payment
  └─ Compensation: Refund payment

Step 3: Ship order
  └─ Compensation: Cancel shipment

On failure at step 3:
  Execute: Refund payment (step 2 compensation)
  Execute: Release inventory (step 1 compensation)
```

**Implementation Pattern**:
1. Track compensation actions as you complete each step
2. On failure, execute compensations in reverse order
3. Handle compensation failures gracefully (log, alert, manual intervention)

## Parallel Execution

**Purpose**: Run multiple independent operations concurrently.

**When to Use**:
- Processing multiple items that don't depend on each other
- Calling multiple APIs simultaneously
- Fan-out/fan-in patterns
- Reducing total workflow duration

**Patterns**:
- `Promise` / `asyncio` - Use traditional concurrency helpers (e.g. wait for all, wait for first, etc)
- Partial failure handling - Continue with successful results

## Entity Workflow Pattern

**Purpose**: Model long-lived entities as workflows that handle events.

**When to Use**:
- Subscription management
- User sessions
- Shopping carts
- Any stateful entity receiving events over time

**How It Works**:
```
Entity Workflow (user-123)
    │
    ├── Receives signal: AddItem
    │   └── Updates state
    │
    ├── Receives signal: UpdateQuantity
    │   └── Updates state
    │
    ├── Receives query: GetCart
    │   └── Returns current state
    │
    └── continueAsNew when history grows
```

## Timer Patterns

**Purpose**: Durable delays that survive worker restarts.

**Use Cases**:
- Scheduled reminders
- Timeout handling
- Delayed actions
- Polling with intervals

**Characteristics**:
- Timers are durable (persisted in history)
- Can be cancelled

## Polling Patterns

### Frequent Polling

**Purpose**: Frequently (once per second of faster) repeatedly check external state until condition met.

**Implementation**:

```
# Inside Activity (polling_activity):
while not condition_met:
    result = await call_external_api()
    if result.done:
        break
    activity.heartbeat("Invoking activity")
    await sleep(poll_interval)


# In workflow code:
workflow.execute_activity(
    polling_activity,
    PollingActivityInput(...),
    start_to_close_timeout=timedelta(seconds=60),
    heartbeat_timeout=timedelta(seconds=2),
)
```

To ensure that polling_activity is restarted in a timely manner, we make sure that it heartbeats on every iteration. Note that heartbeating only works if we set the heartbeat_timeout to a shorter value than the Activity start_to_close_timeout timeout

**Advantage:** Because the polling loop is inside the activity, this does not pollute the workflow history.

### Infrequent Polling

**Purpose**: Infrequently (once per minute or slower) repeatedly poll an external service.

**Implementation**:

Define an Activity which fails (raises an exception) exactly when polling is not completed.

The polling loop is accomplished via activity retries, by setting the following Retry options:
- backoff_coefficient: to 1
- initial_interval: to the polling interval (e.g. 60 seconds)

This will enable the Activity to be retried exactly on the set interval.

**Advantage:**  Individual Activity retries are not recorded in Workflow History, so this approach can poll for a very long time without affecting the history size.

## Idempotency Patterns

**Purpose**: Ensure activities can be safely retried and replayed without causing duplicate side effects.

**Why It Matters**: Temporal may re-execute activities during retries (on failure) or replay (on worker restart). Without idempotency, this can cause duplicate charges, duplicate emails, duplicate database entries, etc.

### Using Idempotency Keys

Pass a unique identifier to external services so they can detect and deduplicate repeated requests:

```
Activity: charge_payment(order_id, amount)
    │
    └── Call payment API with:
            amount: $100
            idempotency_key: "order-{order_id}"
        │
        └── Payment provider deduplicates based on key
            (second call with same key returns original result)
```

**Good idempotency key sources**:
- Workflow ID (unique per workflow execution)
- Business identifier (order ID, transaction ID)
- Workflow ID + activity name + attempt number

### Check-Before-Act Pattern

Query the external system's state before making changes:

```
Activity: send_welcome_email(user_id)
    │
    ├── Check: Has welcome email been sent for user_id?
    │   │
    │   ├── YES: Return early (already done)
    │   │
    │   └── NO: Send email, mark as sent
```

### Designing Idempotent Activities

1. **Use unique identifiers** as idempotency keys with external APIs
2. **Check before acting**: Query current state before making changes
3. **Make operations repeatable**: Ensure calling twice produces the same result
4. **Record outcomes**: Store transaction IDs or results for verification
5. **Leverage external system features**: Many APIs (Stripe, AWS, etc.) have built-in idempotency key support

### Tracking State in Workflows

For complex multi-step operations, track completion status in workflow state:

```
Workflow State:
    payment_completed: false
    shipment_created: false

Run:
    if not payment_completed:
        charge_payment(...)
        payment_completed = true

    if not shipment_created:
        create_shipment(...)
        shipment_created = true
```

This ensures that on replay, already-completed steps are skipped.

## Large Data Handling

**Purpose**: Handle data that exceeds Temporal's payload limits without polluting workflow history.

**Limits** (see `references/core/gotchas.md` for details):
- Max 2MB per individual payload
- Max 4MB per gRPC message
- Max 50MB for workflow history (aim for <10MB)

**Key Principle**: Large data should never flow through workflow history. Activities read and write large data directly, passing only small references through the workflow.

**Wrong Approach**:
```
Workflow
    │
    ├── downloadFromStorage(ref) ──▶ returns large data (enters history)
    │
    ├── processData(largeData) ────▶ large data as argument (enters history AGAIN)
    │
    └── uploadToStorage(result) ───▶ large data as argument (enters history AGAIN)
```

This defeats the purpose—large data enters workflow history multiple times.

**Correct Approach**:
```
Workflow
    │
    └── processLargeData(inputRef) ──▶ returns outputRef (small string)
                │
                └── Activity internally:
                        download(inputRef) → process → upload → return outputRef
```

The workflow only handles references (small strings). The activity does all large data operations internally.

**Implementation Pattern**:
1. Accept a reference (URL, S3 key, database ID) as activity input
2. Download/fetch the large data inside the activity
3. Process the data inside the activity
4. Upload/store the result inside the activity
5. Return only a reference to the result

**Other Strategies**:
- **Compression**: Use a PayloadCodec to compress data automatically
- **Chunking**: Split large collections across multiple activities, each handling a subset

## Activity Heartbeating

**Purpose**: Enable cancellation delivery and progress tracking for long-running activities.

**Why Heartbeat**:
1. **Support activity cancellation** - Cancellations are delivered to activities via heartbeat. Activities that don't heartbeat won't know they've been cancelled.
2. **Resume progress after failure** - Heartbeat details persist across retries, allowing activities to resume where they left off.
3. **Detect stuck activities** - If an activity stops heartbeating, Temporal can time it out and retry.

**How Cancellation Works**:
```
Workflow requests activity cancellation
    │
    ▼
Temporal Service marks activity for cancellation
    │
    ▼
Activity calls heartbeat()
    │
    ├── Not cancelled: heartbeat succeeds, continues
    │
    └── Cancelled: heartbeat raises exception
            Activity can catch this to perform cleanup
```

**Key Point**: If an activity never heartbeats, it will run to completion even if cancelled—it has no way to learn about the cancellation.

## Local Activities

**Purpose**: Reduce latency for short, lightweight operations by skipping the task queue. ONLY use these when necessary for performance. Do NOT use these by default, as they are not durable and distributed.

**When to Use**:
- Short operations completing in milliseconds/seconds
- High-frequency calls where task queue overhead is significant
- Low-latency requirements where you can't afford task queue round-trip

**Characteristics**:
- Executes on the same worker that runs the workflow
- No task queue round-trip (lower latency)
- Still recorded in history
- Should complete quickly (default timeout is short)

**Trade-offs**:
- Less visibility in Temporal UI (no separate task)
- Must complete on the same worker
- Not suitable for long-running operations
- **Risk with consecutive local activities:** Local activity completions are only persisted when the current Workflow Task completes. Calling multiple local activities in a row (with nothing in between to yield the Workflow Task) increases the risk of losing work if the worker crashes mid-sequence. If you need a chain of operations with durable checkpoints between each step, use regular activities instead.

## Choosing Between Patterns

| Need | Pattern |
|------|---------|
| Send data, don't need response | Signal |
| Read state, no modification | Query |
| Modify state, need response | Update |
| Break down large workflow | Child Workflow |
| Prevent history growth | Continue-as-New |
| Rollback on failure | Saga |
| Process items concurrently | Parallel Execution |
| Long-lived stateful entity | Entity Workflow |
| Safe retries/replays | Idempotency |
| Low-latency short operations | Local Activities |
