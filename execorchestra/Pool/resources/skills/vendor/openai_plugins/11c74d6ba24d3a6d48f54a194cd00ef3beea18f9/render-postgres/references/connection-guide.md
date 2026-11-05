# Database connection guide (Render Managed Postgres)

## URL formats

- **Internal** (same region and workspace on Render; private network):

  `postgres://user:password@hostname/dbname`

  No SSL/TLS required for typical internal client settings.

- **External** (local dev, external tools, CI outside Render):

  `postgres://user:password@hostname/dbname?sslmode=require`

  TLS **1.2+** is required for external endpoints; see [Render database documentation](https://render.com/docs/databases) for current TLS and networking requirements.

## Finding URLs in the Dashboard

1. Open your Render Dashboard.
2. Select the **database** instance.
3. Open the **Connect** tab.
4. Copy **Internal** or **External** connection strings as appropriate.

## Blueprint wiring

In `render.yaml`, expose credentials to services with `fromDatabase`:

- **`property: connectionString`** — single URL (ensure the app uses internal vs external appropriately at runtime if you override per environment), or
- Individual properties: **`host`**, **`port`**, **`user`**, **`password`**, **`database`**

See the **render-blueprints** skill for full examples and immutable field rules.

## Connection pooling

Render **does not** provide a managed connection pooler in front of Managed Postgres. You must use:

- **Framework connection pools** (e.g. Rails, Django, Node pg pool), or
- **External poolers** you operate (PgBouncer, pgpool, etc.)

Instance **connection limits are enforced**; pooling is how you stay under them under concurrent load.

## Multiple logical databases

1. Connect with `psql` or your admin tool using the primary database credentials.
2. Run `CREATE DATABASE new_db;`
3. Point applications at the **same host and port** and **same user/password**, changing only the **path** (database name) in the URL:

   `postgres://user:password@hostname/new_db`

## SSL/TLS summary

| Path | TLS |
|------|-----|
| Internal (Render private network) | Not required |
| External | TLS 1.2+ required; use `sslmode=require` (or stricter) in clients |

## Common connection issues

| Symptom | Likely cause | Mitigation |
|---------|----------------|------------|
| Higher latency than expected | App on Render using **external** URL | Switch to **internal** URL for that service |
| SSL / certificate errors | External URL without TLS or wrong `sslmode` | Use `?sslmode=require` and a TLS-capable client |
| “Too many connections” / pool exhausted | Hitting **max_connections** | Reduce pool size per instance, add pooling, scale RAM/plan, or add **read replicas** for read-heavy load |
| Wrong database after `CREATE DATABASE` | URL still points at old DB name | Update connection string path to the new database name |
