# Key Value Troubleshooting

## AUTH failed: Client IP address is not in the allowlist

**Cause:** Connecting from an IP not in the instance's access control list via the external URL.

**Fix:**
1. In Dashboard, go to your Key Value instance > Networking
2. Add your IP address (CIDR notation, e.g. `203.0.113.5/32`)
3. Retry the connection

This only applies to external connections. Internal connections from Render services in the same region are not affected by the IP allowlist.

## Connection refused (internal URL)

**Cause:** Service and Key Value instance are in different regions, or the Key Value instance is not yet available.

**Fix:**
- Verify both resources are in the **same region** (e.g. both in `oregon`)
- Check the instance status in Dashboard — it should show "Available"
- Ensure you're using the **internal** URL (starts with `redis://`), not the external URL

## WRONGPASS / invalid username-password pair

**Cause:** Internal authentication is enabled but client is using the unauthenticated URL.

**Fix:** Update the connection URL to include credentials:

```
redis://default:PASSWORD@red-xxx:6379
```

Get the authenticated URL from Dashboard > Connect menu.

## OOM command not allowed (maxmemory reached)

**Cause:** Instance memory is full and `maxmemoryPolicy` is `noeviction`.

**Fix options:**
- **Upgrade** to a larger instance type (Dashboard > Key Value Instance > Update)
- **Add TTLs** to keys that don't need to persist forever
- **Switch policy** to `allkeys-lru` if data loss is acceptable (cache use case)
- **Review data patterns** — are you storing more than intended?

## Data lost after upgrade from Free

**Expected behavior.** Free instances have no disk persistence. Upgrading from Free to a paid plan wipes all data because the instance is recreated with disk backing.

**Prevention:** Export critical data before upgrading, or use a paid instance from the start for production workloads.

## Data lost after restart (Free tier)

**Expected behavior.** Free Key Value instances do not persist data to disk. Data is in-memory only and lost on restart, redeploy, or platform maintenance.

**Fix:** Upgrade to a paid plan for `appendfsync everysec` persistence.

## Legacy Redis 6 instances

Instances created before February 2025 run Redis 6. They continue to operate but do not receive version updates. New instances run Valkey 8.

No action is required unless you need Valkey 8-specific features. Migration to a new instance requires creating a new Key Value and updating connection strings.

## Cannot downgrade instance type

Instance type changes are **upgrade-only**. You cannot move to a smaller instance. If you need less capacity, create a new smaller instance and migrate your data.
