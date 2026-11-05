# API Reference

R2 Data Catalog exposes standard [Apache Iceberg REST Catalog API](https://github.com/apache/iceberg/blob/main/open-api/rest-catalog-open-api.yaml).

## Quick Reference

**Most common operations:**

| Task | PyIceberg Code |
|------|----------------|
| Connect | `RestCatalog(name="r2", warehouse=bucket, uri=uri, token=token)` |
| List namespaces | `catalog.list_namespaces()` |
| Create namespace | `catalog.create_namespace("logs")` |
| Create table | `catalog.create_table(("ns", "table"), schema=schema)` |
| Load table | `catalog.load_table(("ns", "table"))` |
| Append data | `table.append(pyarrow_table)` |
| Query data | `table.scan().to_pandas()` |
| Compact files | `table.rewrite_data_files(target_file_size_bytes=128*1024*1024)` |
| Expire snapshots | `table.expire_snapshots(older_than=timestamp_ms, retain_last=10)` |

## REST Endpoints

Base: `https://<account-id>.r2.cloudflarestorage.com/iceberg/<bucket-name>`

| Operation | Method | Path |
|-----------|--------|------|
| Catalog config | GET | `/v1/config` |
| List namespaces | GET | `/v1/namespaces` |
| Create namespace | POST | `/v1/namespaces` |
| Delete namespace | DELETE | `/v1/namespaces/{ns}` |
| List tables | GET | `/v1/namespaces/{ns}/tables` |
| Create table | POST | `/v1/namespaces/{ns}/tables` |
| Load table | GET | `/v1/namespaces/{ns}/tables/{table}` |
| Update table | POST | `/v1/namespaces/{ns}/tables/{table}` |
| Delete table | DELETE | `/v1/namespaces/{ns}/tables/{table}` |
| Rename table | POST | `/v1/tables/rename` |

**Authentication:** Bearer token in header: `Authorization: Bearer <token>`

## PyIceberg Client API

Most users use PyIceberg, not raw REST.

### Connection

```python
from pyiceberg.catalog.rest import RestCatalog

catalog = RestCatalog(
    name="my_catalog",
    warehouse="<bucket-name>",
    uri="<catalog-uri>",
    token="<api-token>",
)
```

### Namespace Operations

```python
from pyiceberg.exceptions import NamespaceAlreadyExistsError

namespaces = catalog.list_namespaces()  # [('default',), ('logs',)]
catalog.create_namespace("logs", properties={"owner": "team"})
catalog.drop_namespace("logs")  # Must be empty
```

### Table Operations

```python
from pyiceberg.schema import Schema
from pyiceberg.types import NestedField, StringType, IntegerType

schema = Schema(
    NestedField(1, "id", IntegerType(), required=True),
    NestedField(2, "name", StringType(), required=False),
)
table = catalog.create_table(("logs", "app_logs"), schema=schema)
tables = catalog.list_tables("logs")
table = catalog.load_table(("logs", "app_logs"))
catalog.rename_table(("logs", "old"), ("logs", "new"))
```

### Data Operations

```python
import pyarrow as pa

data = pa.table({"id": [1, 2], "name": ["Alice", "Bob"]})
table.append(data)
table.overwrite(data)

# Read with filters
scan = table.scan(row_filter="id > 100", selected_fields=["id", "name"])
df = scan.to_pandas()
```

### Schema Evolution

```python
from pyiceberg.types import IntegerType, LongType

with table.update_schema() as update:
    update.add_column("user_id", IntegerType(), doc="User ID")
    update.rename_column("msg", "message")
    update.delete_column("old_field")
    update.update_column("id", field_type=LongType())  # int→long only
```

### Time-Travel

```python
from datetime import datetime, timedelta

# Query specific snapshot or timestamp
scan = table.scan(snapshot_id=table.snapshots()[-2].snapshot_id)
yesterday_ms = int((datetime.now() - timedelta(days=1)).timestamp() * 1000)
scan = table.scan(as_of_timestamp=yesterday_ms)
```

### Partitioning

```python
from pyiceberg.partitioning import PartitionSpec, PartitionField
from pyiceberg.transforms import DayTransform
from pyiceberg.types import TimestampType

partition_spec = PartitionSpec(
    PartitionField(source_id=1, field_id=1000, transform=DayTransform(), name="day")
)
table = catalog.create_table(("events", "actions"), schema=schema, partition_spec=partition_spec)
scan = table.scan(row_filter="day = '2026-01-27'")  # Prunes partitions
```

## Table Maintenance

### Compaction

```python
files = table.scan().plan_files()
avg_mb = sum(f.file_size_in_bytes for f in files) / len(files) / (1024**2)
print(f"Files: {len(files)}, Avg: {avg_mb:.1f} MB")

table.rewrite_data_files(target_file_size_bytes=128 * 1024 * 1024)
```

**When:** Avg <10MB or >1000 files. **Frequency:** High-write daily, medium weekly.

### Snapshot Expiration

```python
from datetime import datetime, timedelta

seven_days_ms = int((datetime.now() - timedelta(days=7)).timestamp() * 1000)
table.expire_snapshots(older_than=seven_days_ms, retain_last=10)
```

**Retention:** Production 7-30d, dev 1-7d, audit 90+d.

### Orphan Cleanup

```python
three_days_ms = int((datetime.now() - timedelta(days=3)).timestamp() * 1000)
table.delete_orphan_files(older_than=three_days_ms)
```

⚠️ Always expire snapshots first, use 3+ day threshold, run during low traffic.

### Full Maintenance

```python
# Compact → Expire → Cleanup (in order)
if len(table.scan().plan_files()) > 1000:
    table.rewrite_data_files(target_file_size_bytes=128 * 1024 * 1024)
seven_days_ms = int((datetime.now() - timedelta(days=7)).timestamp() * 1000)
table.expire_snapshots(older_than=seven_days_ms, retain_last=10)
three_days_ms = int((datetime.now() - timedelta(days=3)).timestamp() * 1000)
table.delete_orphan_files(older_than=three_days_ms)
```

## Metadata Inspection

```python
table = catalog.load_table(("logs", "app_logs"))
print(table.schema())
print(table.current_snapshot())
print(table.properties)
print(f"Files: {len(table.scan().plan_files())}")
```

## Error Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| 401 | Unauthorized | Invalid/missing token |
| 404 | Not Found | Catalog not enabled, namespace/table missing |
| 409 | Conflict | Already exists, concurrent update |
| 422 | Validation | Invalid schema, incompatible type |

See [gotchas.md](gotchas.md) for detailed troubleshooting.
