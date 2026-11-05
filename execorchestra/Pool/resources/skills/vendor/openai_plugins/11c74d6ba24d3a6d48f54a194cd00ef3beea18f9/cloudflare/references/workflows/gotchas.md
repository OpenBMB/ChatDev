# Gotchas & Debugging

## Common Errors

### "Step Timeout"

**Cause:** Step execution exceeding 10 minute default timeout or configured timeout
**Solution:** Set custom timeout with `step.do('long operation', {timeout: '30 minutes'}, async () => {...})` or increase CPU limit in wrangler.jsonc (max 5min CPU time)

### "waitForEvent Timeout"

**Cause:** Event not received within timeout period (default 24h, max 365d)
**Solution:** Wrap in try-catch to handle timeout gracefully and proceed with default behavior

### "Non-Deterministic Step Names"

**Cause:** Using dynamic values like `Date.now()` in step names causes replay issues
**Solution:** Use deterministic values like `event.instanceId` for step names

### "State Lost in Variables"

**Cause:** Using module-level or local variables to store state which is lost on hibernation
**Solution:** Return values from `step.do()` which are automatically persisted: `const total = await step.do('step 1', async () => 10)`

### "Non-Deterministic Conditionals"

**Cause:** Using non-deterministic logic (like `Date.now()`) outside steps in conditionals
**Solution:** Move non-deterministic operations inside steps: `const isLate = await step.do('check', async () => Date.now() > deadline)`

### "Large Step Returns Exceeding Limit"

**Cause:** Returning data >1 MiB from step
**Solution:** Store large data in R2 and return only reference: `{ key: 'r2-object-key' }`

### "Step Exceeded CPU Limit But Ran for < 30s"

**Cause:** Confusion between CPU time (active compute) and wall-clock time (includes I/O waits)
**Solution:** Network requests, database queries, and sleeps don't count toward CPU. 30s limit = 30s of active processing

### "Idempotency Violation"

**Cause:** Step operations not idempotent, causing duplicate charges or actions on retry
**Solution:** Check if operation already completed before executing (e.g., check if customer already charged)

### "Instance ID Collision"

**Cause:** Reusing instance IDs causing conflicts
**Solution:** Use unique IDs with timestamp: `await env.MY_WORKFLOW.create({ id: \`${userId}-${Date.now()}\`, params: {} })`

### "Instance Data Disappeared After Completion"

**Cause:** Completed/errored instances are automatically deleted after retention period (3 days free / 30 days paid)
**Solution:** Export critical data to KV/R2/D1 before workflow completes

### "Missing await on step.do"

**Cause:** Forgetting to await step.do() causing fire-and-forget behavior
**Solution:** Always await step operations: `await step.do('task', ...)`

## Limits

| Limit | Free | Paid | Notes |
|-------|------|------|-------|
| CPU per step | 10ms | 30s (default), 5min (max) | Set via `limits.cpu_ms` in wrangler.jsonc |
| Step state | 1 MiB | 1 MiB | Per step return value |
| Instance state | 100 MB | 1 GB | Total state per workflow instance |
| Steps per workflow | 1,024 | 1,024 | `step.sleep()` doesn't count |
| Executions per day | 100k | Unlimited | Daily execution limit |
| Concurrent instances | 25 | 10k | Maximum concurrent workflows; waiting state excluded |
| Queued instances | 100k | 1M | Maximum queued workflow instances |
| Subrequests per step | 50 | 1,000 | Maximum outbound requests per step |
| State retention | 3 days | 30 days | How long completed instances kept |
| Step timeout default | 10 min | 10 min | Per attempt |
| waitForEvent timeout default | 24h | 24h | Maximum 365 days |
| waitForEvent timeout max | 365 days | 365 days | Maximum wait time |

**Note:** Instances in `waiting` state (from `step.sleep` or `step.waitForEvent`) don't count toward concurrent instance limit, allowing millions of sleeping workflows.

## Pricing

| Metric | Free | Paid | Notes |
|--------|------|------|-------|
| Requests | 100k/day | 10M/mo + $0.30/M | Workflow invocations |
| CPU time | 10ms/invoke | 30M CPU-ms/mo + $0.02/M CPU-ms | Actual CPU usage |
| Storage | 1 GB | 1 GB/mo + $0.20/GB-mo | All instances (running/errored/sleeping/completed) |

## References

- [Official Docs](https://developers.cloudflare.com/workflows/)
- [Get Started Guide](https://developers.cloudflare.com/workflows/get-started/guide/)
- [Workers API](https://developers.cloudflare.com/workflows/build/workers-api/)
- [REST API](https://developers.cloudflare.com/api/resources/workflows/)
- [Examples](https://developers.cloudflare.com/workflows/examples/)
- [Limits](https://developers.cloudflare.com/workflows/reference/limits/)
- [Pricing](https://developers.cloudflare.com/workflows/reference/pricing/)

See: [README.md](./README.md), [configuration.md](./configuration.md), [api.md](./api.md), [patterns.md](./patterns.md)
