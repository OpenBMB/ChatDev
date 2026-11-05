# DNS Configuration for Render Custom Domains

## Record Types by Domain Type

### Subdomain (e.g. `app.example.com`, `api.example.com`)

| Provider | Record type | Name | Value |
|----------|-------------|------|-------|
| Any | CNAME | `app` | `<service>.onrender.com` |

Subdomains always use CNAME records.

### Apex domain (e.g. `example.com`)

Apex domains technically cannot have CNAME records per DNS standards. Options:

| Provider | Record type | Name | Value | Notes |
|----------|-------------|------|-------|-------|
| **Cloudflare** | CNAME (flattened) | `@` | `<service>.onrender.com` | Cloudflare auto-flattens at the zone apex |
| **Namecheap** | ALIAS | `@` | `<service>.onrender.com` | Namecheap supports ALIAS records |
| **Other** | A | `@` | Render-provided IP | Check Dashboard for the IP address |

**Preferred approach:** Use a DNS provider that supports CNAME flattening or ALIAS records (Cloudflare, Namecheap, DNSimple, NS1). This avoids hardcoding an IP that could change.

### www + apex pattern

When you add `www.example.com`, Render automatically adds `example.com` with a redirect to `www`. When you add `example.com`, Render adds `www.example.com` with a redirect to the root.

Set up DNS for both:

```
example.com     → CNAME (flattened) or A → <service>.onrender.com or IP
www.example.com → CNAME                  → <service>.onrender.com
```

## Provider-Specific Guides

### Cloudflare

1. Go to DNS settings for your domain
2. Add a CNAME record:
   - Name: `@` (for apex) or subdomain
   - Target: `<service>.onrender.com`
   - Proxy status: **DNS only** (gray cloud) recommended during initial setup
3. After verification succeeds, you can enable the orange cloud (proxy) if desired

**Cloudflare proxy (orange cloud) considerations:**
- Adds Cloudflare's CDN and WAF in front of Render
- May cache responses (configure cache rules)
- SSL mode should be **Full (strict)** since Render provides valid TLS

### Namecheap

1. Go to Advanced DNS for your domain
2. Add a CNAME record:
   - Host: `@` (for apex, uses ALIAS) or subdomain
   - Value: `<service>.onrender.com`
   - TTL: Automatic

### Other providers

1. For subdomains: Add a CNAME record pointing to `<service>.onrender.com`
2. For apex domains: Check if your provider supports ALIAS/ANAME records. If not, use an A record with the IP from the Render Dashboard.

## TTL Recommendations

| Scenario | Recommended TTL |
|----------|-----------------|
| Initial setup / migration | 300 (5 minutes) — enables fast iteration |
| After verified and stable | 3600 (1 hour) or higher |
| During DNS provider migration | 60-300 — minimize stale cache risk |

## IPv6 (AAAA Records)

**Remove all AAAA records** for domains you point to Render. Render uses IPv4 only. Stale AAAA records cause some clients to attempt IPv6 connections that fail.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Verification fails | DNS not propagated | Wait 2-5 min, flush caches, retry |
| 502 after verification | Routing rules updating | Wait 2-5 min |
| Certificate not issued | CAA records blocking | Add `letsencrypt.org` and `pki.goog` CAA entries |
| ERR_SSL_VERSION_OR_CIPHER_MISMATCH | AAAA record present | Remove all AAAA records |
| Redirect loop | Cloudflare SSL mode not "Full (strict)" | Set SSL to Full (strict) in Cloudflare |
