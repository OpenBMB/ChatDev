---
name: render-postgres
description: >-
  Sets up and optimizes Managed PostgreSQL on Render—connection strings
  (internal vs external), creation constraints, storage autoscaling, connection
  limits, high availability, read replicas, backups, and MCP inspection. Use
  when the user
  mentions Postgres, PostgreSQL, Render database, connection string, DATABASE_URL,
  backups, snapshots, replicas, HA, disk storage, connection pooling, or
  troubleshooting DB connectivity.
license: MIT
compatibility: Render Managed Postgres (any plan)
metadata:
  author: Render
  version: "1.0.0"
  category: data
---

# Render Managed PostgreSQL

This skill covers **Managed Postgres on Render**: how to connect, what cannot change after creation, storage behavior, limits, HA, replicas, and safe deletion. Deep dives live under `references/`.

## When to Use

Apply this skill when the user:

- Configures **Postgres** for an app on Render (URLs, TLS, pooling)
- Creates or changes a **database**, **plan**, **disk**, or **replicas**
- Asks about **backups**, **PITR**, **exports**, or **deleting** a database
- Hits **connection limits**, **SSL errors**, or **latency** between services and DB
- Authors **Blueprint** `databases` / `readReplicas` or wires `fromDatabase`

For deploy flows and Blueprint basics, see **render-deploy** and **render-blueprints**. For private networking between services, see **render-networking**. For env var patterns, see **render-env-vars**.

## Connection Patterns

Render exposes **two connection URLs** for the same logical database:

| URL | Use when | TLS |
|-----|----------|-----|
| **Internal** | App or service on Render in the **same region and workspace** | Not required (private network) |
| **External** | Local development, CI, or tools outside Render | **Required** (TLS 1.2+) |

**Always prefer the internal URL for Render-hosted apps** so traffic stays on Render’s network and avoids extra latency and public egress patterns.

- **IP allow list** applies to **external** access only. Same-region Render services use the **internal** URL regardless of the allow list.
- **External** clients must use TLS; misconfigured clients often show SSL handshake or `sslmode` errors.

URL formats, Dashboard locations, Blueprint `fromDatabase`, pooling, and common mistakes: `references/connection-guide.md`.

## Creation and Setup

- **Instance display name**: Can be changed later (where the Dashboard allows renaming the resource).
- **Immutable after creation**: `databaseName`, database **user**, **region**, **PostgreSQL major version**. Plan these before create; changing them requires a new database and migration.
- **Storage size**: **1 GB** or **multiples of 5 GB** when provisioning.

Wire apps with Blueprint `fromDatabase` using `property: connectionString` (or `host`, `port`, `user`, `password`, `database` individually). See **render-blueprints**.

### Multiple logical databases

You can run `CREATE DATABASE new_db;` in `psql` on the same instance. **Host, port, and credentials stay the same**; only the **database name in the URL path** changes (e.g. `.../myapp` vs `.../new_db`).

## Storage Management

- **Autoscaling**: When disk use reaches roughly **~90%**, Render can grow storage by about **~50%**, rounded up to the **next 5 GB multiple**, up to **16 TB** max.
- **Cannot shrink** disk after an increase.
- **Cooldown**: After a storage increase, you **cannot increase again for 12 hours**.
- **Over limit / unhealthy**: If disk is over the configured limit, the database can become **unhealthy**; Render may **suspend** it until resolved.

Monitor disk and plan exports or cleanup before you hit hard limits. Backup and restore options: `references/backup-and-recovery.md`.

## Connection Limits

Maximum connections depend on **instance RAM** (current-generation plans):

| RAM | Max connections (typical) |
|-----|---------------------------|
| Under 8 GB | 100 |
| 8 GB | 200 |
| 16 GB | 300 |
| 32 GB and above | 500 |

**Legacy** database plans may have **lower** limits; confirm in the Dashboard or API for the specific plan.

Render does **not** provide a built-in pooler; use **application-side pooling** (framework pools, PgBouncer, pgpool, etc.). Limits are **hard**—exhausting them causes connection errors. More detail: `references/connection-guide.md` and `references/performance-tuning.md`.

## High Availability

**High availability (HA)** is available when:

- Workspace is **Professional** or higher, **and**
- Database plan is **Pro** or higher, **and**
- **PostgreSQL 13+**

**Instance type changes** cause **brief downtime**. With HA, downtime is typically **less** than **without HA** (often on the order of **minutes** without HA—exact duration depends on plan and operation).

**One-way migration off legacy types**: After moving to current-generation instance types, you **cannot** move back to **legacy** instance types.

## Read Replicas

- Up to **5 read replicas** per database.
- In Blueprints, declare replicas under **`readReplicas`** as a **list of names**.
- **CAUTION — declarative sync**:
  - An **empty** `readReplicas` list can **destroy all** existing replicas.
  - **Name mismatches** between the Blueprint and live replicas can **create** new replicas and **remove** replicas whose names are no longer listed.

Always treat `readReplicas` as **authoritative** desired state, not additive-only.

## Useful MCP Commands

Use the Render MCP tools (names may vary slightly by integration; align with your server’s tool list):

| Goal | Tool / pattern |
|------|----------------|
| List databases | `list_postgres_instances` |
| Instance details | `get_postgres` with `postgresId` |
| Read-only SQL | `query_render_postgres` with `postgresId` and `sql` |
| Connection load | `get_metrics` with `resourceId` (Postgres ID) and `metricTypes: ["active_connections"]` |

`query_render_postgres` runs in a **read-only** transaction and opens a **new connection per query**—do not use it as a substitute for app pooling.

Shorthand (same tools): `list_postgres_instances()`, `get_postgres(postgresId)`, `query_render_postgres(postgresId, sql)`, `get_metrics(resourceId, metricTypes: ["active_connections"])`.

## Deleting and Data Safety

- **Backups and snapshots are not retained** after you **delete** the database. **Export first** (`pg_dump`, Dashboard restore workflow from existing backups, etc.).
- Before destructive actions, confirm retention and recovery paths in `references/backup-and-recovery.md`.

## References

| Document | Contents |
|----------|----------|
| `references/connection-guide.md` | Internal vs external URLs, SSL, allow list, Blueprint wiring, pooling, multi-database URLs, troubleshooting |
| `references/backup-and-recovery.md` | Snapshots, PITR, `pg_dump` / `pg_restore`, restore flows, deletion, cross-region |
| `references/performance-tuning.md` | `pg_stat_statements`, indexes, bloat, `EXPLAIN ANALYZE`, metrics, scaling |

## Related Skills

- **render-deploy** — End-to-end deploy, services, and MCP/Dashboard flows
- **render-blueprints** — `databases`, `fromDatabase`, `readReplicas`, immutable fields
- **render-networking** — Private services, regions, and how traffic routes between resources
- **render-env-vars** — Storing `DATABASE_URL` and secret wiring patterns
