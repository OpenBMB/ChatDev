# Cloudflare R2 SQL Skill Reference

Expert guidance for Cloudflare R2 SQL - serverless distributed query engine for Apache Iceberg tables.

## Reading Order

**New to R2 SQL?** Start here:
1. Read "What is R2 SQL?" and "When to Use" below
2. [configuration.md](configuration.md) - Enable catalog, create tokens
3. [patterns.md](patterns.md) - Wrangler CLI and integration examples
4. [api.md](api.md) - SQL syntax and query reference
5. [gotchas.md](gotchas.md) - Limitations and troubleshooting

**Quick reference?** Jump to:
- [Run a query via Wrangler](patterns.md#wrangler-cli-query)
- [SQL syntax reference](api.md#sql-syntax)
- [ORDER BY limitations](gotchas.md#order-by-limitations)

## What is R2 SQL?

R2 SQL is Cloudflare's **serverless distributed analytics query engine** for querying Apache Iceberg tables in R2 Data Catalog. Features:

- **Serverless** - No clusters to manage, no infrastructure
- **Distributed** - Leverages Cloudflare's global network for parallel execution
- **SQL interface** - Familiar SQL syntax for analytics queries
- **Zero egress fees** - Query from any cloud/region without data transfer costs
- **Open beta** - Free during beta (standard R2 storage costs apply)

### What is Apache Iceberg?

Open table format for large-scale analytics datasets in object storage:
- **ACID transactions** - Safe concurrent reads/writes
- **Metadata optimization** - Fast queries without full table scans
- **Schema evolution** - Add/rename/drop columns without rewrites
- **Partitioning** - Organize data for efficient pruning

## When to Use

**Use R2 SQL for:**
- **Log analytics** - Query application/system logs with WHERE filters and aggregations
- **BI dashboards** - Generate reports from large analytical datasets
- **Fraud detection** - Analyze transaction patterns with GROUP BY/HAVING
- **Multi-cloud analytics** - Query data from any cloud without egress fees
- **Ad-hoc exploration** - Run SQL queries on Iceberg tables via Wrangler CLI

**Don't use R2 SQL for:**
- **Workers/Pages runtime** - R2 SQL has no Workers binding, use HTTP API from external systems
- **Real-time queries (<100ms)** - Optimized for analytical batch queries, not OLTP
- **Complex joins/CTEs** - Limited SQL feature set (no JOINs, subqueries, CTEs currently)
- **Small datasets (<1GB)** - Setup overhead not justified

## Decision Tree: Need to Query R2 Data?

```
Do you need to query structured data in R2?
├─ YES, data is in Iceberg tables
│  ├─ Need SQL interface? → Use R2 SQL (this reference)
│  ├─ Need Python API? → See r2-data-catalog reference (PyIceberg)
│  └─ Need other engine? → See r2-data-catalog reference (Spark, Trino, etc.)
│
├─ YES, but not in Iceberg format
│  ├─ Streaming data? → Use Pipelines to write to Data Catalog, then R2 SQL
│  └─ Static files? → Use PyIceberg to create Iceberg tables, then R2 SQL
│
└─ NO, just need object storage → Use R2 reference (not R2 SQL)
```

## Architecture Overview

**Query Planner:**
- Top-down metadata investigation with multi-layer pruning
- Partition-level, column-level, and row-group pruning
- Streaming pipeline - execution starts before planning completes
- Early termination with LIMIT - stops when result complete

**Query Execution:**
- Coordinator distributes work to workers across Cloudflare network
- Workers run Apache DataFusion for parallel query execution
- Parquet column pruning - reads only required columns
- Ranged reads from R2 for efficiency

**Aggregation Strategies:**
- Scatter-gather - simple aggregations (SUM, COUNT, AVG)
- Shuffling - ORDER BY/HAVING on aggregates via hash partitioning

## Quick Start

```bash
# 1. Enable R2 Data Catalog on bucket
npx wrangler r2 bucket catalog enable my-bucket

# 2. Create API token (Admin Read & Write)
# Dashboard: R2 → Manage API tokens → Create API token

# 3. Set environment variable
export WRANGLER_R2_SQL_AUTH_TOKEN=<your-token>

# 4. Run query
npx wrangler r2 sql query "my-bucket" "SELECT * FROM default.my_table LIMIT 10"
```

## Important Limitations

**CRITICAL: No Workers Binding**
- R2 SQL cannot be called directly from Workers/Pages code
- For programmatic access, use HTTP API from external systems
- Or query via PyIceberg, Spark, etc. (see r2-data-catalog reference)

**SQL Feature Set:**
- No JOINs, CTEs, subqueries, window functions
- ORDER BY supports aggregation columns (not just partition keys)
- LIMIT max 10,000 (default 500)
- See [gotchas.md](gotchas.md) for complete limitations

## In This Reference

- **[configuration.md](configuration.md)** - Enable catalog, create API tokens
- **[api.md](api.md)** - SQL syntax, functions, operators, data types
- **[patterns.md](patterns.md)** - Wrangler CLI, HTTP API, Pipelines, PyIceberg
- **[gotchas.md](gotchas.md)** - Limitations, troubleshooting, performance tips

## See Also

- [r2-data-catalog](../r2-data-catalog/) - PyIceberg, REST API, external engines
- [pipelines](../pipelines/) - Streaming ingestion to Iceberg tables
- [r2](../r2/) - R2 object storage fundamentals
- [Cloudflare R2 SQL Docs](https://developers.cloudflare.com/r2-sql/)
- [R2 SQL Deep Dive Blog](https://blog.cloudflare.com/r2-sql-deep-dive/)
