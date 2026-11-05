# R2 SQL Gotchas

Limitations, troubleshooting, and common pitfalls for R2 SQL.

## Critical Limitations

### No Workers Binding

**Cannot call R2 SQL from Workers/Pages code** - no binding exists.

```typescript
// ❌ This doesn't exist
export default {
  async fetch(request, env) {
    const result = await env.R2_SQL.query("SELECT * FROM table");  // Not possible
    return Response.json(result);
  }
};
```

**Solutions:**
- HTTP API from external systems (not Workers)
- PyIceberg/Spark via r2-data-catalog REST API
- For Workers, use D1 or external databases

### ORDER BY Limitations

Can only order by:
1. **Partition key columns** - Always supported
2. **Aggregation functions** - Supported via shuffle strategy

**Cannot order by** regular non-partition columns.

```sql
-- ✅ Valid: ORDER BY partition key
SELECT * FROM logs.requests ORDER BY timestamp DESC LIMIT 100;

-- ✅ Valid: ORDER BY aggregation
SELECT region, SUM(amount) FROM sales.transactions
GROUP BY region ORDER BY SUM(amount) DESC;

-- ❌ Invalid: ORDER BY non-partition column
SELECT * FROM logs.requests ORDER BY user_id;

-- ❌ Invalid: ORDER BY alias (must repeat function)
SELECT region, SUM(amount) as total FROM sales.transactions
GROUP BY region ORDER BY total;  -- Use ORDER BY SUM(amount)
```

Check partition spec: `DESCRIBE namespace.table_name`

## SQL Feature Limitations

| Feature | Supported | Notes |
|---------|-----------|-------|
| SELECT, WHERE, GROUP BY, HAVING | ✅ | Standard support |
| COUNT, SUM, AVG, MIN, MAX | ✅ | Standard aggregations |
| ORDER BY partition/aggregation | ✅ | See above |
| LIMIT | ✅ | Max 10,000 |
| Column aliases | ❌ | No AS alias |
| Expressions in SELECT | ❌ | No col1 + col2 |
| ORDER BY non-partition | ❌ | Fails at runtime |
| JOINs, subqueries, CTEs | ❌ | Denormalize at write time |
| Window functions, UNION | ❌ | Use external engines |
| INSERT/UPDATE/DELETE | ❌ | Use PyIceberg/Pipelines |
| Nested columns, arrays, JSON | ❌ | Flatten at write time |

**Workarounds:**
- No JOINs: Denormalize data or use Spark/PyIceberg
- No subqueries: Split into multiple queries
- No aliases: Accept generated names, transform in app

## Common Errors

### "Column not found"
**Cause:** Typo, column doesn't exist, or case mismatch
**Solution:** `DESCRIBE namespace.table_name` to check schema

### "Type mismatch"
```sql
-- ❌ Wrong types
WHERE status = '200'              -- string instead of integer
WHERE timestamp > '2025-01-01'    -- missing time/timezone

-- ✅ Correct types
WHERE status = 200
WHERE timestamp > '2025-01-01T00:00:00Z'
```

### "ORDER BY column not in partition key"
**Cause:** Ordering by non-partition column
**Solution:** Use partition key, aggregation, or remove ORDER BY. Check: `DESCRIBE table`

### "Token authentication failed"
```bash
# Check/set token
echo $WRANGLER_R2_SQL_AUTH_TOKEN
export WRANGLER_R2_SQL_AUTH_TOKEN=<your-token>

# Or .env file
echo "WRANGLER_R2_SQL_AUTH_TOKEN=<your-token>" > .env
```

### "Table not found"
```sql
-- Verify catalog and tables
SHOW DATABASES;
SHOW TABLES IN namespace_name;
```

Enable catalog: `npx wrangler r2 bucket catalog enable <bucket>`

### "LIMIT exceeds maximum"
Max LIMIT is 10,000. For pagination, use WHERE filters with partition keys.

### "No data returned" (unexpected)
**Debug steps:**
1. `SELECT COUNT(*) FROM table` - verify data exists
2. Remove WHERE filters incrementally
3. `SELECT * FROM table LIMIT 10` - inspect actual data/types

## Performance Issues

### Slow Queries

**Causes:** Too many partitions, large LIMIT, no filters, small files

```sql
-- ❌ Slow: No filters
SELECT * FROM logs.requests LIMIT 10000;

-- ✅ Fast: Filter on partition key
SELECT * FROM logs.requests
WHERE timestamp >= '2025-01-15T00:00:00Z' AND timestamp < '2025-01-16T00:00:00Z'
LIMIT 1000;

-- ✅ Faster: Multiple filters
SELECT * FROM logs.requests
WHERE timestamp >= '2025-01-15T00:00:00Z' AND status = 404 AND method = 'GET'
LIMIT 1000;
```

**File optimization:**
- Target Parquet size: 100-500MB compressed
- Pipelines roll interval: 300+ sec (prod), 10 sec (dev)
- Run compaction to merge small files

### Query Timeout

**Solution:** Add restrictive WHERE filters, reduce time range, query smaller intervals

```sql
-- ❌ Times out: Year-long aggregation
SELECT status, COUNT(*) FROM logs.requests
WHERE timestamp >= '2024-01-01T00:00:00Z' GROUP BY status;

-- ✅ Faster: Month-long aggregation
SELECT status, COUNT(*) FROM logs.requests
WHERE timestamp >= '2025-01-01T00:00:00Z' AND timestamp < '2025-02-01T00:00:00Z'
GROUP BY status;
```

## Best Practices

### Partitioning
- **Time-series:** Partition by day/hour on timestamp
- **Avoid:** High-cardinality keys (user_id), >10,000 partitions

```python
from pyiceberg.partitioning import PartitionSpec, PartitionField
from pyiceberg.transforms import DayTransform

PartitionSpec(PartitionField(source_id=1, field_id=1000, transform=DayTransform(), name="day"))
```

### Query Writing
- **Always use LIMIT** for early termination
- **Filter on partition keys first** for pruning
- **Combine filters with AND** for more pruning

```sql
-- Good
WHERE timestamp >= '2025-01-15T00:00:00Z' AND status = 404 AND method = 'GET' LIMIT 100
```

### Type Safety
- Quote strings: `'GET'` not `GET`
- RFC3339 timestamps: `'2025-01-01T00:00:00Z'` not `'2025-01-01'`
- ISO dates: `'2025-01-15'` not `'01/15/2025'`

### Data Organization
- **Pipelines:** Dev `roll_file_time: 10`, Prod `roll_file_time: 300+`
- **Compression:** Use `zstd`
- **Maintenance:** Compaction for small files, expire old snapshots

## Debugging Checklist

1. `npx wrangler r2 bucket catalog enable <bucket>` - Verify catalog
2. `echo $WRANGLER_R2_SQL_AUTH_TOKEN` - Check token
3. `SHOW DATABASES` - List namespaces
4. `SHOW TABLES IN namespace` - List tables
5. `DESCRIBE namespace.table` - Check schema
6. `SELECT COUNT(*) FROM namespace.table` - Verify data
7. `SELECT * FROM namespace.table LIMIT 10` - Test simple query
8. Add filters incrementally

## See Also

- [api.md](api.md) - SQL syntax
- [patterns.md](patterns.md) - Query optimization
- [configuration.md](configuration.md) - Setup
- [Cloudflare R2 SQL Docs](https://developers.cloudflare.com/r2-sql/)
