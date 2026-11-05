# Configuration

How to enable R2 Data Catalog and configure authentication.

## Prerequisites

- Cloudflare account with [R2 subscription](https://developers.cloudflare.com/r2/pricing/)
- R2 bucket created
- Access to Cloudflare dashboard or Wrangler CLI

## Enable Catalog on Bucket

Choose one method:

### Via Wrangler (Recommended)

```bash
npx wrangler r2 bucket catalog enable <BUCKET_NAME>
```

**Output:**
```
✅ Data Catalog enabled for bucket 'my-bucket'
   Catalog URI: https://<account-id>.r2.cloudflarestorage.com/iceberg/my-bucket
   Warehouse: my-bucket
```

### Via Dashboard

1. Navigate to **R2** → Select your bucket → **Settings** tab
2. Scroll to "R2 Data Catalog" section → Click **Enable**
3. Note the **Catalog URI** and **Warehouse name** shown

**Result:**
- Catalog URI: `https://<account-id>.r2.cloudflarestorage.com/iceberg/<bucket-name>`
- Warehouse: `<bucket-name>` (same as bucket name)

### Via API (Programmatic)

```bash
curl -X POST \
  "https://api.cloudflare.com/client/v4/accounts/<account-id>/r2/buckets/<bucket>/catalog" \
  -H "Authorization: Bearer <api-token>" \
  -H "Content-Type: application/json"
```

**Response:**
```json
{
  "result": {
    "catalog_uri": "https://<account-id>.r2.cloudflarestorage.com/iceberg/<bucket>",
    "warehouse": "<bucket>"
  },
  "success": true
}
```

## Check Catalog Status

```bash
npx wrangler r2 bucket catalog status <BUCKET_NAME>
```

**Output:**
```
Catalog Status: enabled
Catalog URI: https://<account-id>.r2.cloudflarestorage.com/iceberg/my-bucket
Warehouse: my-bucket
```

## Disable Catalog (If Needed)

```bash
npx wrangler r2 bucket catalog disable <BUCKET_NAME>
```

⚠️ **Warning:** Disabling does NOT delete tables/data. Files remain in bucket. Metadata becomes inaccessible until re-enabled.

## API Token Creation

R2 Data Catalog requires API token with **both** R2 Storage + R2 Data Catalog permissions.

### Dashboard Method (Recommended)

1. Go to **R2** → **Manage R2 API Tokens** → **Create API Token**
2. Select permission level:
   - **Admin Read & Write** - Full catalog + storage access (read/write)
   - **Admin Read only** - Read-only access (for query engines)
3. Copy token value immediately (shown only once)

**Permission groups included:**
- `Workers R2 Data Catalog Write` (or Read)
- `Workers R2 Storage Bucket Item Write` (or Read)

### API Method (Programmatic)

Use Cloudflare API to create tokens programmatically. Required permissions:
- `Workers R2 Data Catalog Write` (or Read)
- `Workers R2 Storage Bucket Item Write` (or Read)

## Client Configuration

### PyIceberg

```python
from pyiceberg.catalog.rest import RestCatalog

catalog = RestCatalog(
    name="my_catalog",
    warehouse="<bucket-name>",           # Same as bucket name
    uri="<catalog-uri>",                 # From enable command
    token="<api-token>",                 # From token creation
)
```

**Full example with credentials:**
```python
import os
from pyiceberg.catalog.rest import RestCatalog

# Store credentials in environment variables
WAREHOUSE = os.getenv("R2_WAREHOUSE")      # e.g., "my-bucket"
CATALOG_URI = os.getenv("R2_CATALOG_URI")  # e.g., "https://abc123.r2.cloudflarestorage.com/iceberg/my-bucket"
TOKEN = os.getenv("R2_TOKEN")              # API token

catalog = RestCatalog(
    name="r2_catalog",
    warehouse=WAREHOUSE,
    uri=CATALOG_URI,
    token=TOKEN,
)

# Test connection
print(catalog.list_namespaces())
```

### Spark / Trino / DuckDB

See [patterns.md](patterns.md) for integration examples with other query engines.

## Connection String Format

For quick reference:

```
Catalog URI:  https://<account-id>.r2.cloudflarestorage.com/iceberg/<bucket>
Warehouse:    <bucket-name>
Token:        <r2-api-token>
```

**Where to find values:**

| Value | Source |
|-------|--------|
| `<account-id>` | Dashboard URL or `wrangler whoami` |
| `<bucket>` | R2 bucket name |
| Catalog URI | Output from `wrangler r2 bucket catalog enable` |
| Token | R2 API Token creation page |

## Security Best Practices

1. **Store tokens securely** - Use environment variables or secret managers, never hardcode
2. **Use least privilege** - Read-only tokens for query engines, write tokens only where needed
3. **Rotate tokens regularly** - Create new tokens, test, then revoke old ones
4. **One token per application** - Easier to track and revoke if compromised
5. **Monitor token usage** - Check R2 analytics for unexpected patterns
6. **Bucket-scoped tokens** - Create tokens per bucket, not account-wide

## Environment Variables Pattern

```bash
# .env (never commit)
R2_CATALOG_URI=https://<account-id>.r2.cloudflarestorage.com/iceberg/<bucket>
R2_WAREHOUSE=<bucket-name>
R2_TOKEN=<api-token>
```

```python
import os
from pyiceberg.catalog.rest import RestCatalog

catalog = RestCatalog(
    name="r2",
    uri=os.getenv("R2_CATALOG_URI"),
    warehouse=os.getenv("R2_WAREHOUSE"),
    token=os.getenv("R2_TOKEN"),
)
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| 404 "catalog not found" | Run `wrangler r2 bucket catalog enable <bucket>` |
| 401 "unauthorized" | Check token has both Catalog + Storage permissions |
| 403 on data files | Token needs both permission groups |

See [gotchas.md](gotchas.md) for detailed troubleshooting.
