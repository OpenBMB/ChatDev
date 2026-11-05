# Graceful shutdown for Render workers

Render stops worker instances during **deploys**, **manual restarts**, and **scale-in** events. Your process must **exit cleanly** within the configured window or work may be **lost** or **duplicated** (depending on your queue’s ack/retry semantics).

## Platform behavior

1. Render sends **`SIGTERM`** to your process.
2. The platform waits up to **`maxShutdownDelaySeconds`** (**1–300**, **default 30**).
3. If the process is still running, Render sends **`SIGKILL`** (not catchable).

Configure **`maxShutdownDelaySeconds`** in the **Dashboard** (service settings) or in **`render.yaml`** on the worker service. Set it to cover your **longest job** you are willing to let complete during shutdown (plus buffer for flushing metrics, closing DB pools, etc.).

## General pattern

1. **Stop accepting new jobs** — stop the consumer loop, pause polling, or drain the framework’s internal fetch.
2. **Finish the current job** or **checkpoint** durable progress so another worker can resume safely.
3. **Close connections** — Redis/Postgres pools, HTTP clients.
4. **Exit with code 0** when done.

## Python

**Low-level handler**

```python
import signal
import sys

def handle_sigterm(signum, frame):
    # set a flag; main loop checks it and stops dequeuing
    global shutting_down
    shutting_down = True

signal.signal(signal.SIGTERM, handle_sigterm)
```

**Celery** — use lifecycle signals such as **`worker_shutting_down`** to run cleanup; ensure tasks honor a **soft time limit** or cooperative cancel flag so shutdown can finish within **`maxShutdownDelaySeconds`**.

## Ruby (Sidekiq)

Sidekiq **handles SIGTERM** by default: it stops fetching new work and waits for in-flight jobs up to a **configurable timeout** (`:timeout` in Sidekiq options, in seconds). Align that timeout with Render’s **`maxShutdownDelaySeconds`** (Sidekiq timeout should be **≤** platform delay minus a small margin).

## Node.js

```javascript
let accept = true;

process.on("SIGTERM", async () => {
  accept = false;
  await worker.close(); // BullMQ: stops accepting, waits for active jobs
  process.exit(0);
});
```

**BullMQ** — prefer **`worker.close()`** (and **`queue.close()`** where applicable) so active jobs complete per library defaults; tune **`stalledInterval`** / job locks if you need stricter bounds.

## Go

Use **`signal.NotifyContext`** (or `signal.Notify` + `context.WithCancel`) to cancel a root context passed into your consumer loop and job handlers; wait on **`sync.WaitGroup`** or channels until in-flight work finishes, then exit.

```go
ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, syscall.SIGINT)
defer stop()
// run consumer until ctx.Done(), then drain workers
```

## Anti-patterns

- **Ignoring SIGTERM** — the process survives until **`SIGKILL`**, often **mid-job**, causing **lost work** or **stuck** queue entries.
- **`maxShutdownDelaySeconds` too low** for your p95 job duration — frequent **hard kills** and retries.
- **No idempotency** — if a job is retried after an ambiguous failure at shutdown, **duplicate side effects** can occur.

## Checklist

| Item | Action |
|------|--------|
| Delay | Set **`maxShutdownDelaySeconds`** ≥ longest graceful completion you need |
| Consumer | On SIGTERM, **stop dequeuing** first |
| Jobs | **Idempotent** handlers or explicit **checkpoints** |
| Framework | Use built-in **drain** / **close** APIs (Sidekiq, BullMQ, Celery signals) where available |
