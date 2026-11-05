# Pipelines API Reference

## Pipeline Binding Interface

```typescript
// From @cloudflare/workers-types
interface Pipeline {
  send(data: object | object[]): Promise<void>;
}

interface Env {
  STREAM: Pipeline;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    // send() returns Promise<void> - no result data
    await env.STREAM.send([event]);
    return new Response('OK');
  }
} satisfies ExportedHandler<Env>;
```

**Key points:**
- `send()` accepts single object or array
- Always returns `Promise<void>` (no confirmation data)
- Throws on network/validation errors (wrap in try/catch)
- Use `ctx.waitUntil()` for fire-and-forget pattern

## Writing Events

### Single Event

```typescript
await env.STREAM.send([{
  user_id: "12345",
  event_type: "purchase",
  product_id: "widget-001",
  amount: 29.99
}]);
```

### Batch Events

```typescript
const events = [
  { user_id: "user1", event_type: "view" },
  { user_id: "user2", event_type: "purchase", amount: 50 }
];
await env.STREAM.send(events);
```

**Limits:**
- Max 1 MB per request
- 5 MB/s per stream

### Fire-and-Forget Pattern

```typescript
export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const event = { /* ... */ };

    // Don't block response on send
    ctx.waitUntil(env.STREAM.send([event]));

    return new Response('OK');
  }
};
```

### Error Handling

```typescript
try {
  await env.STREAM.send([event]);
} catch (error) {
  console.error('Pipeline send failed:', error);
  // Log to another system, retry, or return error response
  return new Response('Failed to track event', { status: 500 });
}
```

## HTTP Ingest API

### Endpoint Format

```
https://{stream-id}.ingest.cloudflare.com
```

Get `{stream-id}` from: `npx wrangler pipelines streams list`

### Request Format

**CRITICAL:** Must send array, not single object

```bash
# ✅ Correct
curl -X POST https://{stream-id}.ingest.cloudflare.com \
  -H "Content-Type: application/json" \
  -d '[{"user_id": "123", "event_type": "purchase"}]'

# ❌ Wrong - will fail
curl -X POST https://{stream-id}.ingest.cloudflare.com \
  -H "Content-Type: application/json" \
  -d '{"user_id": "123", "event_type": "purchase"}'
```

### Authentication

```bash
curl -X POST https://{stream-id}.ingest.cloudflare.com \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -d '[{"event": "data"}]'
```

**Required permission:** Workers Pipeline Send

Create token: Dashboard → Workers → API tokens → Create with Pipeline Send permission

### Response Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Accepted | Success |
| 400 | Invalid format | Check JSON array, schema match |
| 401 | Auth failed | Verify token valid |
| 413 | Payload too large | Split into smaller batches (<1 MB) |
| 429 | Rate limited | Back off, retry with delay |
| 5xx | Server error | Retry with exponential backoff |

## SQL Functions Quick Reference

Available in `INSERT INTO sink SELECT ... FROM stream` transformations:

| Function | Example | Use Case |
|----------|---------|----------|
| `UPPER(s)` | `UPPER(event_type)` | Normalize strings |
| `LOWER(s)` | `LOWER(email)` | Case-insensitive matching |
| `CONCAT(...)` | `CONCAT(user_id, '_', product_id)` | Generate composite keys |
| `CASE WHEN ... THEN ... END` | `CASE WHEN amount > 100 THEN 'high' ELSE 'low' END` | Conditional enrichment |
| `CAST(x AS type)` | `CAST(timestamp AS string)` | Type conversion |
| `COALESCE(x, y)` | `COALESCE(amount, 0.0)` | Default values |
| Math operators | `amount * 1.1`, `price / quantity` | Calculations |
| Comparison | `amount > 100`, `status IN ('active', 'pending')` | Filtering |

**String types for CAST:** `string`, `int32`, `int64`, `float32`, `float64`, `bool`, `timestamp`

Full reference: [Pipelines SQL Reference](https://developers.cloudflare.com/pipelines/sql-reference/)

## SQL Transform Examples

### Filter Events

```sql
INSERT INTO my_sink
SELECT * FROM my_stream
WHERE event_type = 'purchase' AND amount > 100
```

### Select Specific Fields

```sql
INSERT INTO my_sink
SELECT user_id, event_type, timestamp, amount
FROM my_stream
```

### Transform and Enrich

```sql
INSERT INTO my_sink
SELECT
  user_id,
  UPPER(event_type) as event_type,
  timestamp,
  amount * 1.1 as amount_with_tax,
  CONCAT(user_id, '_', product_id) as unique_key,
  CASE
    WHEN amount > 1000 THEN 'high_value'
    WHEN amount > 100 THEN 'medium_value'
    ELSE 'low_value'
  END as customer_tier
FROM my_stream
WHERE event_type IN ('purchase', 'refund')
```

## Querying Results (R2 Data Catalog)

```bash
export WRANGLER_R2_SQL_AUTH_TOKEN=YOUR_CATALOG_TOKEN

npx wrangler r2 sql query "warehouse_name" "
SELECT
  event_type,
  COUNT(*) as event_count,
  SUM(amount) as total_revenue
FROM default.my_table
WHERE event_type = 'purchase'
  AND timestamp >= '2025-01-01'
GROUP BY event_type
ORDER BY total_revenue DESC
LIMIT 100"
```

**Note:** Iceberg tables support standard SQL queries with GROUP BY, JOINs, WHERE, ORDER BY, etc.
