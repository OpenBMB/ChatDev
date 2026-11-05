# Gotchas & Troubleshooting

Common problems → causes → solutions.

## Permission Errors

### 401 Unauthorized

**Error:** `"401 Unauthorized"`
**Cause:** Token missing R2 Data Catalog permissions.
**Solution:** Use "Admin Read & Write" token (includes catalog + storage permissions). Test with `catalog.list_namespaces()`.

### 403 Forbidden

**Error:** `"403 Forbidden"` on data files
**Cause:** Token lacks storage permissions.
**Solution:** Token needs both R2 Data Catalog + R2 Storage Bucket Item permissions.

### Token Rotation Issues

**Error:** New token fails after rotation.
**Solution:** Create new token → test in staging → update prod → monitor 24h → revoke old.

## Catalog URI Issues

### 404 Not Found

**Error:** `"404 Catalog not found"`
**Cause:** Catalog not enabled or wrong URI.
**Solution:** Run `wrangler r2 bucket catalog enable <bucket>`. URI must be HTTPS with `/iceberg/` and case-sensitive bucket name.

### Wrong Warehouse

**Error:** Cannot create/load tables.
**Cause:** Warehouse ≠ bucket name.
**Solution:** Set `warehouse="bucket-name"` to match bucket exactly.

## Table and Schema Issues

### Table/Namespace Already Exists

**Error:** `"TableAlreadyExistsError"`
**Solution:** Use try/except to load existing or check first.

### Namespace Not Found

**Error:** Cannot create table.
**Solution:** Create namespace first: `catalog.create_namespace("ns")`

### Schema Evolution Errors

**Error:** `"422 Validation"` on schema update.
**Cause:** Incompatible change (required field, type shrink).
**Solution:** Only add nullable columns, compatible type widening (int→long, float→double).

## Data and Query Issues

### Empty Scan Results

**Error:** Scan returns no data.
**Cause:** Incorrect filter or partition column.
**Solution:** Test without filter first: `table.scan().to_pandas()`. Verify partition column names.

### Slow Queries

**Error:** Performance degrades over time.
**Cause:** Too many small files.
**Solution:** Check file count, compact if >1000 or avg <10MB. See [api.md](api.md#compaction).

### Type Mismatch

**Error:** `"Cannot cast"` on append.
**Cause:** PyArrow types don't match Iceberg schema.
**Solution:** Cast to int64 (Iceberg default), not int32. Check `table.schema()`.

## Compaction Issues

### Compaction Issues

**Problem:** File count unchanged or compaction takes hours.
**Cause:** Target size too large, or table too big for PyIceberg.
**Solution:** Only compact if avg <50MB. For >1TB tables, use Spark. Run during low-traffic periods.

## Maintenance Issues

### Snapshot/Orphan Issues

**Problem:** Expiration fails or orphan cleanup deletes active data.
**Cause:** Too aggressive retention or wrong order.
**Solution:** Always expire snapshots first with `retain_last=10`, then cleanup orphans with 3+ day threshold.

## Concurrency Issues

### Concurrent Write Conflicts

**Problem:** `CommitFailedException` with multiple writers.
**Cause:** Optimistic locking - simultaneous commits.
**Solution:** Add retry with exponential backoff (see [patterns.md](patterns.md#pattern-6-concurrent-writes-with-retry)).

### Stale Metadata

**Problem:** Old schema/data after external update.
**Cause:** Cached metadata.
**Solution:** Reload table: `table = catalog.load_table(("ns", "table"))`

## Performance Optimization

### Performance Tips

**Scans:** Use `row_filter` and `selected_fields` to reduce data scanned.
**Partitions:** 100-1000 optimal. Avoid high cardinality (millions) or low (<10).
**Files:** Keep 100-500MB avg. Compact if <10MB or >10k files.

## Limits

| Resource | Recommended | Impact if Exceeded |
|----------|-------------|-------------------|
| Tables/namespace | <10k | Slow list ops |
| Files/table | <100k | Slow query planning |
| Partitions/table | 100-1k | Metadata overhead |
| Snapshots/table | Expire >7d | Metadata bloat |

## Common Error Messages Reference

| Error Message | Likely Cause | Fix |
|---------------|--------------|-----|
| `401 Unauthorized` | Missing/invalid token | Check token has catalog+storage permissions |
| `403 Forbidden` | Token lacks storage permissions | Add R2 Storage Bucket Item permission |
| `404 Not Found` | Catalog not enabled or wrong URI | Run `wrangler r2 bucket catalog enable` |
| `409 Conflict` | Table/namespace already exists | Use try/except or load existing |
| `422 Unprocessable Entity` | Schema validation failed | Check type compatibility, required fields |
| `CommitFailedException` | Concurrent write conflict | Add retry logic with backoff |
| `NamespaceAlreadyExistsError` | Namespace exists | Use try/except or load existing |
| `NoSuchTableError` | Table doesn't exist | Check namespace+table name, create first |
| `TypeError: Cannot cast` | PyArrow type mismatch | Cast data to match Iceberg schema |

## Debugging Checklist

When things go wrong, check in order:

1. ✅ **Catalog enabled:** `npx wrangler r2 bucket catalog status <bucket>`
2. ✅ **Token permissions:** Both R2 Data Catalog + R2 Storage in dashboard
3. ✅ **Connection test:** `catalog.list_namespaces()` succeeds
4. ✅ **URI format:** HTTPS, includes `/iceberg/`, correct bucket name
5. ✅ **Warehouse name:** Matches bucket name exactly
6. ✅ **Namespace exists:** Create before `create_table()`
7. ✅ **Enable debug logging:** `logging.basicConfig(level=logging.DEBUG)`
8. ✅ **PyIceberg version:** `pip install --upgrade pyiceberg` (≥0.5.0)
9. ✅ **File health:** Compact if >1000 files or avg <10MB
10. ✅ **Snapshot count:** Expire if >100 snapshots

## Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
# Now operations show HTTP requests/responses
```

## Resources

- [Cloudflare Community](https://community.cloudflare.com/c/developers/workers/40)
- [Cloudflare Discord](https://discord.cloudflare.com) - #r2 channel
- [PyIceberg GitHub](https://github.com/apache/iceberg-python/issues)
- [Apache Iceberg Slack](https://iceberg.apache.org/community/)

## Next Steps

- [patterns.md](patterns.md) - Working examples
- [api.md](api.md) - API reference
