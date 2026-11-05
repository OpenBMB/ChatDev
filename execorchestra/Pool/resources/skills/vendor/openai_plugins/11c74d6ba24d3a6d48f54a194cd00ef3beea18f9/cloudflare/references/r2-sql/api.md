# R2 SQL API Reference

SQL syntax, functions, operators, and data types for R2 SQL queries.

## SQL Syntax

```sql
SELECT column_list | aggregation_function
FROM [namespace.]table_name
WHERE conditions
[GROUP BY column_list]
[HAVING conditions]
[ORDER BY column | aggregation_function [DESC | ASC]]
[LIMIT number]
```

## Schema Discovery

```sql
SHOW DATABASES;           -- List namespaces
SHOW NAMESPACES;          -- Alias for SHOW DATABASES
SHOW SCHEMAS;             -- Alias for SHOW DATABASES
SHOW TABLES IN namespace; -- List tables in namespace
DESCRIBE namespace.table; -- Show table schema, partition keys
```

## SELECT Clause

```sql
-- All columns
SELECT * FROM logs.http_requests;

-- Specific columns
SELECT user_id, timestamp, status FROM logs.http_requests;
```

**Limitations:** No column aliases, expressions, or nested column access

## WHERE Clause

### Operators

| Operator | Example |
|----------|---------|
| `=`, `!=`, `<`, `<=`, `>`, `>=` | `status = 200` |
| `LIKE` | `user_agent LIKE '%Chrome%'` |
| `BETWEEN` | `timestamp BETWEEN '2025-01-01T00:00:00Z' AND '2025-01-31T23:59:59Z'` |
| `IS NULL`, `IS NOT NULL` | `email IS NOT NULL` |
| `AND`, `OR` | `status = 200 AND method = 'GET'` |

Use parentheses for precedence: `(status = 404 OR status = 500) AND method = 'POST'`

## Aggregation Functions

| Function | Description |
|----------|-------------|
| `COUNT(*)` | Count all rows |
| `COUNT(column)` | Count non-null values |
| `COUNT(DISTINCT column)` | Count unique values |
| `SUM(column)`, `AVG(column)` | Numeric aggregations |
| `MIN(column)`, `MAX(column)` | Min/max values |

```sql
-- Multiple aggregations with GROUP BY
SELECT region, COUNT(*), SUM(amount), AVG(amount)
FROM sales.transactions
WHERE sale_date >= '2024-01-01'
GROUP BY region;
```

## HAVING Clause

Filter aggregated results (after GROUP BY):

```sql
SELECT category, SUM(amount)
FROM sales.transactions
GROUP BY category
HAVING SUM(amount) > 10000;
```

## ORDER BY Clause

Sort results by:
- **Partition key columns** - Always supported
- **Aggregation functions** - Supported via shuffle strategy

```sql
-- Order by partition key
SELECT * FROM logs.requests ORDER BY timestamp DESC LIMIT 100;

-- Order by aggregation (repeat function, aliases not supported)
SELECT region, SUM(amount)
FROM sales.transactions
GROUP BY region
ORDER BY SUM(amount) DESC;
```

**Limitations:** Cannot order by non-partition columns. See [gotchas.md](gotchas.md#order-by-limitations)

## LIMIT Clause

```sql
SELECT * FROM logs.requests LIMIT 100;
```

| Setting | Value |
|---------|-------|
| Min | 1 |
| Max | 10,000 |
| Default | 500 |

**Always use LIMIT** to enable early termination optimization.

## Data Types

| Type | SQL Literal | Example |
|------|-------------|---------|
| `integer` | Unquoted number | `42`, `-10` |
| `float` | Decimal number | `3.14`, `-0.5` |
| `string` | Single quotes | `'hello'`, `'GET'` |
| `boolean` | Keyword | `true`, `false` |
| `timestamp` | RFC3339 string | `'2025-01-01T00:00:00Z'` |
| `date` | ISO 8601 date | `'2025-01-01'` |

### Type Safety

- Quote strings with single quotes: `'value'`
- Timestamps must be RFC3339: `'2025-01-01T00:00:00Z'` (include timezone)
- Dates must be ISO 8601: `'2025-01-01'` (YYYY-MM-DD)
- No implicit conversions

```sql
-- ✅ Correct
WHERE status = 200 AND method = 'GET' AND timestamp > '2025-01-01T00:00:00Z'

-- ❌ Wrong
WHERE status = '200'              -- string instead of integer
WHERE timestamp > '2025-01-01'    -- missing time/timezone
WHERE method = GET                -- unquoted string
```

## Query Result Format

JSON array of objects:

```json
[
  {"user_id": "user_123", "timestamp": "2025-01-15T10:30:00Z", "status": 200},
  {"user_id": "user_456", "timestamp": "2025-01-15T10:31:00Z", "status": 404}
]
```

## See Also

- [patterns.md](patterns.md) - Query examples and use cases
- [gotchas.md](gotchas.md) - SQL limitations and error handling
- [configuration.md](configuration.md) - Setup and authentication
