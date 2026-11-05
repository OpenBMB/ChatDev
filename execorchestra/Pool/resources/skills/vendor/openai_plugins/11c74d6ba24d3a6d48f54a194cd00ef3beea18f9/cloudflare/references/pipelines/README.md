# Cloudflare Pipelines

ETL streaming platform for ingesting, transforming, and loading data into R2 with SQL transformations.

## Overview

Pipelines provides:
- **Streams**: Durable event buffers (HTTP/Workers ingestion)
- **Pipelines**: SQL-based transformations
- **Sinks**: R2 destinations (Iceberg tables or Parquet/JSON files)

**Status**: Open beta (Workers Paid plan)
**Pricing**: No charge beyond standard R2 storage/operations

## Architecture

```
Data Sources → Streams → Pipelines (SQL) → Sinks → R2
                 ↑          ↓                ↓
            HTTP/Workers  Transform     Iceberg/Parquet
```

| Component | Purpose | Key Feature |
|-----------|---------|-------------|
| Streams | Event ingestion | Structured (validated) or unstructured |
| Pipelines | Transform with SQL | Immutable after creation |
| Sinks | Write to R2 | Exactly-once delivery |

## Quick Start

```bash
# Interactive setup (recommended)
npx wrangler pipelines setup
```

**Minimal Worker example:**
```typescript
interface Env {
  STREAM: Pipeline;
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const event = { user_id: "123", event_type: "purchase", amount: 29.99 };

    // Fire-and-forget pattern
    ctx.waitUntil(env.STREAM.send([event]));

    return new Response('OK');
  }
} satisfies ExportedHandler<Env>;
```

## Which Sink Type?

```
Need SQL queries on data?
  → R2 Data Catalog (Iceberg)
    ✅ ACID transactions, time-travel, schema evolution
    ❌ More setup complexity (namespace, table, catalog token)

Just file storage/archival?
  → R2 Storage (Parquet)
    ✅ Simple, direct file access
    ❌ No built-in SQL queries

Using external tools (Spark/Athena)?
  → R2 Storage (Parquet with partitioning)
    ✅ Standard format, partition pruning for performance
    ❌ Must manage schema compatibility yourself
```

## Common Use Cases

- **Analytics pipelines**: Clickstream, telemetry, server logs
- **Data warehousing**: ETL into queryable Iceberg tables
- **Event processing**: Mobile/IoT with enrichment
- **Ecommerce analytics**: User events, purchases, views

## Reading Order

**New to Pipelines?** Start here:
1. [configuration.md](./configuration.md) - Setup streams, sinks, pipelines
2. [api.md](./api.md) - Send events, TypeScript types, SQL functions
3. [patterns.md](./patterns.md) - Best practices, integrations, complete example
4. [gotchas.md](./gotchas.md) - Critical warnings, troubleshooting

**Task-based routing:**
- Setup pipeline → [configuration.md](./configuration.md)
- Send/query data → [api.md](./api.md)
- Implement pattern → [patterns.md](./patterns.md)
- Debug issue → [gotchas.md](./gotchas.md)

## In This Reference

- [configuration.md](./configuration.md) - wrangler.jsonc bindings, schema definition, sink options, CLI commands
- [api.md](./api.md) - Pipeline binding interface, send() method, HTTP ingest, SQL function reference
- [patterns.md](./patterns.md) - Fire-and-forget, schema validation with Zod, integrations, performance tuning
- [gotchas.md](./gotchas.md) - Silent validation failures, immutable pipelines, latency expectations, limits

## See Also

- [r2](../r2/) - R2 storage backend for sinks
- [queues](../queues/) - Compare with Queues for async processing
- [workers](../workers/) - Worker runtime for event ingestion
