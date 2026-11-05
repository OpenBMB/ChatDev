# Interactive Workflows

Interactive workflows are workflows that use Temporal features such as signals or updates to pause and wait for external input. When testing and debugging these types of workflows you can send them input via the Temporal CLI.

## Signals

Fire-and-forget messages to a workflow.

```bash
# Send signal to workflow
temporal workflow signal \
  --workflow-id <id> \
  --name "signal_name" \
  --input '{"key": "value"}'
```

## Updates

Request-response style interaction (returns a value).

```bash
# Send update to workflow
temporal workflow update execute \
  --workflow-id <id> \
  --name "update_name" \
  --input '{"approved": true}'
```

## Queries

Read-only inspection of workflow state.

```bash
# Query workflow state (read-only)
temporal workflow query \
  --workflow-id <id> \
  --name "get_status"
```

## Typical Steps for Testing Interactive Workflows

```bash
# 1. Start worker (command is project dependent)
# 2. Start workflow (command is project dependent) This code should output the workflow ID, if not, modify it to.
temporal workflow signal --workflow-id <WORKFLOW_ID> --name "signal_name" --input '{"key": "value"}' # 3. Send it interactive events, e.g. a signal.
# 4. Wait for workflow to complete (use Temporal CLI to check status)
# 5. Read workflow result, using the Temporal CLI
# 6. Cleanup the worker process if needed.
```
