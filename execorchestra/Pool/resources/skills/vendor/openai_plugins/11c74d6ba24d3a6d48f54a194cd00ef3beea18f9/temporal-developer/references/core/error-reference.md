# Common Error Types Reference

| Error Type | Error identifier (if any) | Where to Find | What Happened | Recovery | Link to additional info (if any) |
|------------|---------------|---------------|---------------|----------|----------|
| **Non-determinism** | TMPRL1100 | `WorkflowTaskFailed` in history | Replay doesn't match history | Analyze error first. **If accidental**: fix code to match history → restart worker. **If intentional v2 change**: terminate → start fresh workflow. | https://github.com/temporalio/rules/blob/main/rules/TMPRL1100.md |
| **Deadlock** | TMPRL1101 | `WorkflowTaskFailed` in history, worker logs | Workflow blocked too long (deadlock detected) | Remove blocking operations from workflow code (no I/O, no sleep, no threading locks). Use Temporal primitives instead. | https://github.com/temporalio/rules/blob/main/rules/TMPRL1101.md |
| **Unfinished handlers** | TMPRL1102 | `WorkflowTaskFailed` in history | Workflow completed while update/signal handlers still running | Ensure all handlers complete before workflow finishes. Use `workflow.wait_condition()` to wait for handler completion. | https://github.com/temporalio/rules/blob/main/rules/TMPRL1102.md |
| **Payload overflow** | TMPRL1103 | `WorkflowTaskFailed` or `ActivityTaskFailed` in history | Payload size limit exceeded (default 2MB) | Reduce payload size. Use external storage (S3, database) for large data and pass references instead. | https://github.com/temporalio/rules/blob/main/rules/TMPRL1103.md |
| **Workflow code bug** |  | `WorkflowTaskFailed` in history | Bug in workflow logic | Fix code → Restart worker → Workflow auto-resumes |  |
| **Missing workflow** |  | Worker logs | Workflow not registered | Add to worker.py → Restart worker |  |
| **Missing activity** |  | Worker logs | Activity not registered | Add to worker.py → Restart worker |  |
| **Activity bug** |  | `ActivityTaskFailed` in history | Bug in activity code | Fix code → Restart worker → Auto-retries |  |
| **Activity retries** |  | `ActivityTaskFailed` (count >2) | Repeated failures | Fix code → Restart worker → Auto-retries |  |
| **Sandbox violation** |  | Worker logs | Bad imports in workflow | Fix workflow.py imports → Restart worker |  |
| **Task queue mismatch** |  | Workflow never starts | Different queues in starter/worker | Align task queue names |  |
| **Timeout** |  | Status = TIMED_OUT | Operation too slow | Increase timeout config |  |

## Workflow Status Reference

| Status | Meaning | Action |
|--------|---------|--------|
| `RUNNING` | Workflow in progress | Wait, or check if stalled |
| `COMPLETED` | Successfully finished | Get result, verify correctness |
| `FAILED` | Error during execution | Analyze error |
| `CANCELED` | Explicitly canceled | Review reason |
| `TERMINATED` | Force-stopped | Review reason |
| `TIMED_OUT` | Exceeded timeout | Increase timeout |

## See Also

- [Common Gotchas](gotchas.md) - Anti-patterns that cause these errors
- [Troubleshooting](troubleshooting.md) - Decision trees for diagnosing issues
