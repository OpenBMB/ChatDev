# Cloudflare R2 Data Catalog Skill Reference

Expert guidance for Cloudflare R2 Data Catalog - Apache Iceberg catalog built into R2 buckets.

## Reading Order

**New to R2 Data Catalog?** Start here:
1. Read "What is R2 Data Catalog?" and "When to Use" below
2. [configuration.md](configuration.md) - Enable catalog, create tokens
3. [patterns.md](patterns.md) - PyIceberg setup and common patterns
4. [api.md](api.md) - REST API reference as needed
5. [gotchas.md](gotchas.md) - Troubleshooting when issues arise

**Quick reference?** Jump to:
- [Enable catalog on bucket](configuration.md#enable-catalog-on-bucket)
- [PyIceberg connection pattern](patterns.md#pyiceberg-connection-pattern)
- [Permission errors](gotchas.md#permission-errors)

## What is R2 Data Catalog?

R2 Data Catalog is a **managed Apache Iceberg REST catalog** built directly into R2 buckets. It provides:

- **Apache Iceberg tables** - ACID transactions, schema evolution, time-travel queries
- **Zero-egress costs** - Query from any cloud/region without data transfer fees
- **Standard REST API** - Works with Spark, PyIceberg, Snowflake, Trino, DuckDB
- **No infrastructure** - Fully managed, no catalog servers to run
- **Public beta** - Available to all R2 subscribers, no extra cost beyond R2 storage

### What is Apache Iceberg?

Open table format for analytics datasets in object storage. Features:
- **ACID transactions** - Safe concurrent reads/writes
- **Metadata optimization** - Fast queries without full scans
- **Schema evolution** - Add/rename/delete columns without rewrites
- **Time-travel** - Query historical snapshots
- **Partitioning** - Organize data for efficient queries

## When to Use

**Use R2 Data Catalog for:**
- **Log analytics** - Store and query application/system logs
- **Data lakes/warehouses** - Analytical datasets queried by multiple engines
- **BI pipelines** - Aggregate data for dashboards and reports
- **Multi-cloud analytics** - Share data across clouds without egress fees
- **Time-series data** - Event streams, metrics, sensor data

**Don't use for:**
- **Transactional workloads** - Use D1 or external database instead
- **Sub-second latency** - Iceberg optimized for batch/analytical queries
- **Small datasets (<1GB)** - Setup overhead not worth it
- **Unstructured data** - Store files directly in R2, not as Iceberg tables

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Query Engines                                  │
│  (PyIceberg, Spark, Trino, Snowflake, DuckDB)  │
└────────────────┬────────────────────────────────┘
                 │
                 │ REST API (OAuth2 token)
                 ▼
┌─────────────────────────────────────────────────┐
│  R2 Data Catalog (Managed Iceberg REST Catalog)│
│  • Namespace/table metadata                     │
│  • Transaction coordination                     │
│  • Snapshot management                          │
└────────────────┬────────────────────────────────┘
                 │
                 │ Vended credentials
                 ▼
┌─────────────────────────────────────────────────┐
│  R2 Bucket Storage                              │
│  • Parquet data files                           │
│  • Metadata files                               │
│  • Manifest files                               │
└─────────────────────────────────────────────────┘
```

**Key concepts:**
- **Catalog URI** - REST endpoint for catalog operations (e.g., `https://<account-id>.r2.cloudflarestorage.com/iceberg/<bucket>`)
- **Warehouse** - Logical grouping of tables (typically same as bucket name)
- **Namespace** - Schema/database containing tables (e.g., `logs`, `analytics`)
- **Table** - Iceberg table with schema, data files, snapshots
- **Vended credentials** - Temporary S3 credentials catalog provides for data access

## Limits

| Resource | Limit | Notes |
|----------|-------|-------|
| Namespaces per catalog | No hard limit | Organize tables logically |
| Tables per namespace | <10,000 recommended | Performance degrades beyond this |
| Files per table | <100,000 recommended | Run compaction regularly |
| Snapshots per table | Configurable retention | Expire >7 days old |
| Partitions per table | 100-1,000 optimal | Too many = slow metadata ops |
| Table size | Same as R2 bucket | 10GB-10TB+ common |
| API rate limits | Standard R2 API limits | Shared with R2 storage operations |
| Target file size | 128-512 MB | After compaction |

## Current Status

**Public Beta** (as of Jan 2026)
- Available to all R2 subscribers
- No extra cost beyond standard R2 storage/operations
- Production-ready, but breaking changes possible
- Supports: namespaces, tables, snapshots, compaction, time-travel, table maintenance

## Decision Tree: Is R2 Data Catalog Right For You?

```
Start → Need analytics on object storage data?
         │
         ├─ No → Use R2 directly for object storage
         │
         └─ Yes → Dataset >1GB with structured schema?
                  │
                  ├─ No → Too small, use R2 + ad-hoc queries
                  │
                  └─ Yes → Need ACID transactions or schema evolution?
                           │
                           ├─ No → Consider simpler solutions (Parquet on R2)
                           │
                           └─ Yes → Need multi-cloud/multi-tool access?
                                    │
                                    ├─ No → D1 or external DB may be simpler
                                    │
                                    └─ Yes → ✅ Use R2 Data Catalog
```

**Quick check:** If you answer "yes" to all:
- Dataset >1GB and growing
- Structured/tabular data (logs, events, metrics)
- Multiple query tools or cloud environments
- Need versioning, schema changes, or concurrent access

→ R2 Data Catalog is a good fit.

## In This Reference

- **[configuration.md](configuration.md)** - Enable catalog, create API tokens, connect clients
- **[api.md](api.md)** - REST endpoints, operations, maintenance
- **[patterns.md](patterns.md)** - PyIceberg examples, common use cases
- **[gotchas.md](gotchas.md)** - Troubleshooting, best practices, limitations

## See Also

- [Cloudflare R2 Data Catalog Docs](https://developers.cloudflare.com/r2/data-catalog/)
- [Apache Iceberg Docs](https://iceberg.apache.org/)
- [PyIceberg Docs](https://py.iceberg.apache.org/)
