---
name: render-domains
description: >-
  Configures custom domains and TLS certificates on Render—DNS setup, CNAME
  records, apex domains, wildcard domains, and certificate troubleshooting.
  Use when the user needs to add a custom domain, configure DNS, set up
  HTTPS/TLS, troubleshoot certificate issuance, disable the onrender.com
  subdomain, or add a wildcard domain.
  Trigger terms: custom domain, DNS, CNAME, TLS, SSL, HTTPS, certificate,
  apex domain, wildcard domain, onrender.com, domain verification.
license: MIT
compatibility: Render web services and static sites
metadata:
  author: Render
  version: "1.0.0"
  category: networking
---

# Render Custom Domains

Render automatically provisions and renews TLS certificates (via Let's Encrypt and Google Trust Services) for all custom domains. All HTTP traffic is redirected to HTTPS. Custom domains work on **web services** and **static sites** only.

## When to Use

- Adding a **custom domain** to a web service or static site
- Configuring **DNS records** (CNAME, A, or ALIAS) with a provider
- Setting up a **wildcard domain** (`*.example.com`)
- Troubleshooting **certificate issuance** or **domain verification** failures
- Choosing between **apex** (`example.com`) and **www** (`www.example.com`)
- **Disabling the `onrender.com` subdomain** after adding a custom domain

## Domain Limits

| Workspace tier | Custom domain limit |
|---------------|---------------------|
| Hobby | 2 custom domains (across all services) |
| Professional+ | Unlimited |

## Setup Steps

### 1. Add domain in Dashboard

1. Go to your service's **Settings > Custom Domains**
2. Click **+ Add Custom Domain**
3. Enter your domain (e.g. `app.example.com`)
4. Click **Save**

Adding a `www` subdomain automatically adds the root domain (and vice versa) with a redirect between them.

### 2. Configure DNS

Add a DNS record with your provider pointing to your Render service:

| Domain type | Record type | Name | Value |
|-------------|-------------|------|-------|
| **Subdomain** (`app.example.com`) | CNAME | `app` | `<service>.onrender.com` |
| **Apex** (`example.com`) on Cloudflare | CNAME (flattened) | `@` | `<service>.onrender.com` |
| **Apex** on other providers | A | `@` | Use Render-provided IP (see Dashboard) |

**Important:** Remove any `AAAA` (IPv6) records for your domain. Render uses IPv4, and stale `AAAA` records cause unexpected behavior.

Provider-specific guides:
- [Cloudflare](https://render.com/docs/configure-cloudflare-dns)
- [Namecheap](https://render.com/docs/configure-namecheap-dns)
- [Other providers](https://render.com/docs/configure-other-dns)

### 3. Verify domain

Click **Verify** in the Dashboard. If verification fails, DNS may not have propagated yet—wait a few minutes and retry.

Speed up verification by flushing DNS caches:
- [Google Public DNS](https://developers.google.com/speed/public-dns/cache)
- [Cloudflare DNS](https://1.1.1.1/purge-cache/)
- [OpenDNS](https://cachecheck.opendns.com/)

After verification, Render issues a TLS certificate automatically.

## Wildcard Domains

Wildcard domains (`*.example.com`) route all matching subdomains to one service.

Requires **three CNAME records**:

| Name | Value | Purpose |
|------|-------|---------|
| `*` | `<service>.onrender.com` | Routes traffic |
| `_acme-challenge` | `<service-id>.verify.renderdns.com` | Let's Encrypt validation |
| `_cf-custom-hostname` | `<service-id>.hostname.renderdns.com` | Cloudflare DDoS validation |

**Cloudflare users:** If you add `*.example.com` without adding the root domain to Render, disable proxying (gray cloud) for the root domain to avoid routing conflicts.

## CAA Records

If your domain has `CAA` records, add entries for Render's certificate authorities:

```
example.com IN CAA 0 issue "letsencrypt.org"
example.com IN CAA 0 issuewild "letsencrypt.org"
example.com IN CAA 0 issue "pki.goog; cansignhttpexchanges=yes"
example.com IN CAA 0 issuewild "pki.goog; cansignhttpexchanges=yes"
```

Without these, TLS certificate issuance fails silently.

## Disabling the `onrender.com` Subdomain

After adding at least one custom domain, you can disable the default `onrender.com` subdomain:

1. Settings > Custom Domains > **Render Subdomain** > toggle to **Disabled**
2. All requests to the `onrender.com` URL receive a 404
3. Can be re-enabled at any time

## Blueprint Configuration

Custom domains are specified in the `domains` field:

```yaml
services:
  - type: web
    name: api
    runtime: node
    plan: starter
    domains:
      - app.example.com
      - www.example.com
```

Blueprint `domains` only **declare** the domain association. You still need to configure DNS with your provider manually.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| AAAA records present | Remove all IPv6 AAAA records for the domain |
| CAA records blocking issuance | Add `letsencrypt.org` and `pki.goog` entries |
| Verifying too quickly | Wait 2-5 minutes for DNS propagation, then flush caches |
| Cloudflare proxy + wildcard without root domain | Disable proxying (gray cloud) for the root domain |
| Trying to add domain to a private service | Custom domains only work on web services and static sites |
| 502 after verification | Routing rules are updating — wait a few minutes |

## References

| Document | Contents |
|----------|----------|
| `references/dns-configuration.md` | Provider-specific DNS setup, apex domain options, TTL recommendations |

## Related Skills

- **render-web-services** — Web service configuration, TLS, port binding
- **render-static-sites** — Static site domains, CDN, headers
- **render-blueprints** — `domains` field in `render.yaml`
