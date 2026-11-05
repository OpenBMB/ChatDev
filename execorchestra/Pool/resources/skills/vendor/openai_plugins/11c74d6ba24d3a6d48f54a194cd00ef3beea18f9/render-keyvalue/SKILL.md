---
name: render-keyvalue
description: >-
  Provisions and configures Render Key Value (Redis-compatible Valkey 8)
  instances for caching, session storage, and job queues. Use when the user
  needs Redis, Key Value, Valkey, a cache, session store, job queue backend,
  or needs to configure maxmemory policy, ipAllowList, connection strings,
  or internal vs external access.
  Trigger terms: Key Value, Redis, Valkey, cache, session store, REDIS_URL,
  maxmemory, ipAllowList, allkeys-lru, noeviction.
license: MIT
compatibility: Render Key Value instances (free and paid plans)
metadata:
  author: Render
  version: "1.0.0"
  category: data
---

# Render Key Value

Render Key Value provides low-latency, Redis-compatible in-memory storage running **Valkey 8**. Use it as a shared cache, session store, or job queue backend. Compatible with virtually all Redis client libraries.

## When to Use

- Adding a **cache** or **session store** to a web app
- Wiring a **job queue** backend for Celery, Sidekiq, BullMQ, Asynq, or Oban
- Choosing the right **maxmemory policy** (cache vs queue)
- Configuring **ipAllowList** in Blueprints (required field)
- Connecting via **internal vs external URLs**
- Troubleshooting **auth failures** or **connection refused** errors

For background worker setup and queue framework patterns, see **render-background-workers**. For Blueprint authoring, see **render-blueprints**.

## Key Concepts

### Valkey 8 (not Redis)

New instances run **Valkey 8**, an open-source Redis fork. It is a drop-in replacement for Redis—existing Redis client libraries work without changes. Legacy instances (created before Feb 2025) run Redis 6.

### Connection URLs

Every instance has two URLs:

| URL type | When to use | Auth required |
|----------|-------------|---------------|
| **Internal** (`redis://red-xxx:6379`) | From Render services in the same region | No (by default) |
| **External** (`rediss://red-xxx:6379`) | From outside Render (local dev, CI) | Always |

**Always prefer the internal URL** for production services—lower latency, no TLS overhead, communicates over the private network.

External connections are **disabled by default**. Enable them by adding IP ranges to the access control list in the Dashboard.

### Internal authentication

By default, internal connections are unauthenticated. You can **require auth for internal connections** in the Dashboard for compliance or extra security. This changes the internal URL to include credentials:

```
redis://default:PASSWORD@red-xxx:6379
```

**Warning:** Enabling internal auth breaks existing unauthenticated connections. Migrate clients to the authenticated URL first.

## Maxmemory Policy

**Critical decision.** Choose based on your use case:

| Use case | Policy | Why |
|----------|--------|-----|
| **Cache** (can lose data) | `allkeys-lru` | Evicts least-recently-used keys to free space |
| **Job queue** (cannot lose data) | `noeviction` | Returns error on writes when full; never drops keys |
| **Session store** | `allkeys-lru` or `volatile-lru` | Sessions can be regenerated; LRU is safe |

All available policies:

| Policy | Behavior | Memory fills up? |
|--------|----------|-----------------|
| `allkeys-lru` | Evict any key by LRU | No |
| `noeviction` | Error on writes when full | Yes |
| `volatile-lru` | Evict keys with TTL by LRU | Yes |
| `volatile-lfu` | Evict keys with TTL by LFU | Yes |
| `allkeys-lfu` | Evict any key by LFU | No |
| `volatile-random` | Evict random keys with TTL | Yes |
| `allkeys-random` | Evict any random key | No |
| `volatile-ttl` | Evict keys nearest to expiry | Yes |

## Blueprint Configuration

```yaml
services:
  - type: keyvalue
    name: cache
    plan: starter
    region: oregon
    maxmemoryPolicy: allkeys-lru
    ipAllowList: []
```

### `ipAllowList` is required

Blueprints **must** include `ipAllowList` on Key Value services. Common patterns:

| Value | Meaning |
|-------|---------|
| `[]` | No external access (internal only—**recommended for most apps**) |
| `[{source: "0.0.0.0/0", description: "everywhere"}]` | Open external access (use sparingly) |
| `[{source: "203.0.113.0/24", description: "office"}]` | Specific IP ranges |

### Wiring to services

Use `fromService` with `type: keyvalue` and `property: connectionString`:

```yaml
envVars:
  - key: REDIS_URL
    fromService:
      name: cache
      type: keyvalue
      property: connectionString
```

Available `fromService` properties for Key Value:

| Property | Value |
|----------|-------|
| `connectionString` | Full internal URL (`redis://red-xxx:6379`) |
| `host` | Hostname only |
| `port` | Port only (typically `6379`) |

## Data Persistence

- **Paid instances:** Disk-backed, `appendfsync everysec`. You may lose up to 1 second of writes on interruption.
- **Free instances:** No disk persistence. Data is lost on restart or upgrade.
- **Upgrading from Free:** All data is lost during the upgrade because Free instances have no disk.

## Instance Types and Upgrades

- Instance type determines **RAM** and **connection limit**
- You can **upgrade** to a larger type (brief downtime, ~1-2 minutes)
- You **cannot downgrade** to a smaller type
- For instances larger than 10 GB RAM, contact Render support

## Connection Examples

See `references/connection-examples.md` for client code in Node.js (ioredis, node-redis), Python (redis-py), Ruby (redis-rb, Sidekiq), and Go.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Missing `ipAllowList` in Blueprint | Add `ipAllowList: []` for internal-only access |
| Using `allkeys-lru` for job queues | Switch to `noeviction`—LRU eviction drops queued jobs |
| Connecting with external URL from a Render service | Use the internal URL for lower latency and no auth requirement |
| Forgetting `type: keyvalue` in `fromService` | `type` is required; without it the wiring fails |
| Using deprecated `redis` type alias | Prefer `keyvalue` in new Blueprints (`redis` still works but is deprecated) |

## References

| Document | Contents |
|----------|----------|
| `references/connection-examples.md` | Client code for Node.js, Python, Ruby, Go |
| `references/troubleshooting.md` | Auth errors, connection refused, memory full, migration from Redis 6 |

## Related Skills

- **render-background-workers** — Queue consumer setup with Celery, Sidekiq, BullMQ
- **render-blueprints** — Full `render.yaml` schema, `fromService` patterns
- **render-networking** — Private network, internal URLs
- **render-env-vars** — Wiring `REDIS_URL` and other connection vars
