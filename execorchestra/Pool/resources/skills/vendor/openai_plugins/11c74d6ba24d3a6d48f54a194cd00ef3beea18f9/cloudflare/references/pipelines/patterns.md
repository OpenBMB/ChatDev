# Pipelines Patterns

## Fire-and-Forget

```typescript
export default {
  async fetch(request, env, ctx) {
    const event = { user_id: '...', event_type: 'page_view', timestamp: new Date().toISOString() };
    ctx.waitUntil(env.STREAM.send([event])); // Don't block response
    return new Response('OK');
  }
};
```

## Schema Validation with Zod

```typescript
import { z } from 'zod';

const EventSchema = z.object({
  user_id: z.string(),
  event_type: z.enum(['purchase', 'view']),
  amount: z.number().positive().optional()
});

const validated = EventSchema.parse(rawEvent); // Throws on invalid
await env.STREAM.send([validated]);
```

**Why:** Structured streams drop invalid events silently. Client validation gives immediate feedback.

## SQL Transform Patterns

```sql
-- Filter early (reduce storage)
INSERT INTO my_sink
SELECT user_id, event_type, amount
FROM my_stream
WHERE event_type = 'purchase' AND amount > 10

-- Select only needed fields
INSERT INTO my_sink
SELECT user_id, event_type, timestamp FROM my_stream

-- Enrich with CASE
INSERT INTO my_sink
SELECT user_id, amount,
  CASE WHEN amount > 1000 THEN 'vip' ELSE 'standard' END as tier
FROM my_stream
```

## Pipelines + Queues Fan-out

```typescript
await Promise.all([
  env.ANALYTICS_STREAM.send([event]),  // Long-term storage
  env.PROCESS_QUEUE.send(event)        // Immediate processing
]);
```

| Need | Use |
|------|-----|
| Long-term storage, SQL queries | Pipelines |
| Immediate processing, retries | Queues |
| Both | Fan-out pattern |

## Performance Tuning

| Goal | Config |
|------|--------|
| Low latency | `--roll-interval 10` |
| Query performance | `--roll-interval 300 --roll-size 100` |
| Cost optimal | `--compression zstd --roll-interval 300` |

## Schema Evolution

Pipelines are immutable. Use versioning:

```bash
# Create v2 stream/sink/pipeline
npx wrangler pipelines streams create events-v2 --schema-file v2.json

# Dual-write during transition
await Promise.all([env.EVENTS_V1.send([event]), env.EVENTS_V2.send([event])]);

# Query across versions with UNION ALL
```
