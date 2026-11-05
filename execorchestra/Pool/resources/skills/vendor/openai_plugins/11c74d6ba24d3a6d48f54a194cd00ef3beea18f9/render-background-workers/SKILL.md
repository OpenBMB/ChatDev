---
name: render-background-workers
description: >-
  Sets up and configures background workers on Render for queue-based job
  processing. Use when the user needs to process async jobs, consume from a
  queue, run Celery/Sidekiq/BullMQ/Asynq/Oban workers, handle graceful
  shutdown with SIGTERM, wire a worker to Key Value (Redis), or choose between
  workers and cron jobs for background work.
  Trigger terms: background worker, async jobs, queue consumer, Celery,
  Sidekiq, BullMQ, Asynq, Oban, job processing, SIGTERM, graceful shutdown.
license: MIT
compatibility: Render background worker services
metadata:
  author: Render
  version: "1.0.0"
  category: compute
---

# Render Background Workers

This skill explains **worker** services on Render: processes that **consume jobs from a queue** instead of serving HTTP. Pair with **render-blueprints**, **render-env-vars**, and **render-networking** when wiring `render.yaml` and private connectivity.

## When to Use

- Designing or debugging **queue-backed workers** (Celery, Sidekiq, BullMQ, Asynq, etc.)
- Choosing between a **worker**, **Cron Job**, or **Workflow** for background work
- Configuring **Render Key Value** as a **broker** (not a cache) with correct **eviction policy**
- Implementing **graceful shutdown** so in-flight jobs are not lost on deploy

Per-framework setup and signal-handling detail: `references/queue-framework-setup.md`, `references/graceful-shutdown.md`.

## How Workers Work

- **Long-running services** with **no inbound (HTTP) traffic**. Render does not expose a public URL or internal hostname for workers the way it does for web or private services—**workers cannot receive private network traffic directed at them**.
- The typical pattern is a **poll loop**: the process connects to a **queue backend** (often **Render Key Value**, Redis-compatible **Valkey 8**) and **pulls jobs**.
- Workers **can initiate outbound connections** on the private network—to **PostgreSQL**, **Key Value**, **private services**, **web services** (internal URLs), and the public internet—subject to your plan and firewall rules.

## Queue Framework Overview

| Framework | Language | Queue backend | Notes |
|-----------|----------|---------------|--------|
| Celery | Python | Redis / Key Value | Most common Python task queue |
| Sidekiq | Ruby | Redis / Key Value | Standard for Rails |
| BullMQ | Node.js | Redis / Key Value | Modern Node queue (Redis-based) |
| Asynq | Go | Redis / Key Value | Go async task processing |
| Oban | Elixir | **Postgres** (not Redis) | Queue stored in the database |

## Pairing with Key Value

- Use **Render Key Value** as the **job broker** when your framework expects Redis.
- Set **maxmemory policy** to **`noeviction`**. **`allkeys-lru`** and similar policies are for **caches**; evicting queue keys **drops jobs**.
- Wire **`REDIS_URL`** (or your framework’s equivalent) via **`fromService`** with `type: keyvalue` and `property: connectionString` in the Blueprint.
- **Blueprints require `ipAllowList`** on Key Value—include the CIDRs that should reach the instance (often `[]` for private-network-only access; see **render-blueprints** / Key Value field reference).

See `references/queue-framework-setup.md` for minimal app + YAML examples.

## Worker vs Cron vs Workflow

| Need | Use | Why |
|------|-----|-----|
| Always-on queue consumer | **Background Worker** | Polls continuously; long-lived process |
| Periodic scheduled task | **Cron Job** | Runs on a schedule, **exits**; **12h max** per run |
| Distributed parallel compute | **Workflow** | Each run gets its own instance; fan-out patterns |
| High-volume or bursty jobs | **Workflow** | Scales per run; **no idle instance cost** between runs |

## Graceful Shutdown

- Before stopping an instance, Render sends **`SIGTERM`**, then waits up to **`maxShutdownDelaySeconds`** (**1–300**, **default 30**) before **`SIGKILL`**.
- Workers should: **(1)** stop accepting new jobs, **(2)** finish the current job or **checkpoint** progress, **(3)** close connections, **(4)** exit **0**.
- Set **`maxShutdownDelaySeconds`** to at least your **longest safe job duration** (see Dashboard or Blueprint).

Language- and framework-specific handlers: `references/graceful-shutdown.md`.

## Blueprint Configuration

Minimal pattern: **`type: worker`**, **`runtime`**, **`buildCommand`**, **`startCommand`**, and **`envVars`** wired from Key Value.

```yaml
services:
  - type: keyvalue
    name: jobs
    plan: starter
    region: oregon
    ipAllowList: []

  - type: worker
    name: task-worker
    runtime: python
    region: oregon
    plan: starter
    buildCommand: pip install -r requirements.txt
    startCommand: celery -A tasks worker --loglevel=info
    envVars:
      - key: REDIS_URL
        fromService:
          name: jobs
          type: keyvalue
          property: connectionString
```

Optional: **`maxShutdownDelaySeconds`** on the worker service for longer draining jobs.

## References

| Topic | File |
|--------|------|
| Celery, Sidekiq, BullMQ, Asynq, Oban setup + YAML | `references/queue-framework-setup.md` |
| SIGTERM, `maxShutdownDelaySeconds`, per-language patterns | `references/graceful-shutdown.md` |

## Related Skills

- **render-deploy** — First deploy, CLI, service creation
- **render-blueprints** — Full `render.yaml` schema, `fromService`, projects
- **render-networking** — Private URLs, what can call what
- **render-scaling** — Worker plans, instance counts, limits
