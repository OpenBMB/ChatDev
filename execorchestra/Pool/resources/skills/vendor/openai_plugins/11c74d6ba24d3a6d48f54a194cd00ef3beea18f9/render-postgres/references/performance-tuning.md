# Postgres performance on Render

## Slow query detection (`pg_stat_statements`)

Enable the **`pg_stat_statements`** extension (if not already enabled) to aggregate query statistics.

Example top slow queries by mean time:

```sql
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

Reset or interpret stats after schema or workload changes; averages can be skewed by few large calls.

## Indexes and sequential scans

- Use **`EXPLAIN ANALYZE`** on hot queries to see **sequential scans** and row estimates.
- Add **indexes** for columns used heavily in **`WHERE`**, **`JOIN`**, and **`ORDER BY`**, balancing write amplification.

## Connection monitoring

**Metrics API / MCP:**

- `get_metrics` with `resourceId` set to the **Postgres instance ID** and `metricTypes: ["active_connections"]` for time-series connection counts.

**Live SQL:**

```sql
SELECT state, count(*)
FROM pg_stat_activity
GROUP BY state;
```

Correlate spikes with deploys, pool sizes, and background jobs.

## Table bloat

Monitor dead tuples:

```sql
-- Simplified bloat signal: high n_dead_tup relative to live rows
SELECT relname, n_live_tup, n_dead_tup
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC
LIMIT 20;
```

Run **`VACUUM ANALYZE`** (or rely on autovacuum tuning) on heavily updated tables; investigate long transactions that block cleanup.

## Query and application patterns

- Prefer **`EXPLAIN ANALYZE`** in staging with production-like data sizes.
- Eliminate **N+1** query patterns at the app layer.
- Use **connection pooling**; keep per-process pool sizes aligned with **max connections** (see main skill).

## Scaling strategies

| Need | Direction |
|------|-----------|
| More CPU/RAM/connections | **Vertical**: larger database **plan** / instance type |
| Read-heavy workload | **Read replicas** (up to 5); route read-only traffic explicitly |
| Disk pressure | Autoscaling grows at ~**90%** (see main skill); **cannot shrink**—archive or migrate data |

## Storage monitoring

Use **`get_metrics`** for disk-related metrics where exposed for your resource type, and Dashboard graphs for trend analysis. Plan cleanup **before** autoscaling steps you cannot immediately reverse (cooldown and no shrink).
