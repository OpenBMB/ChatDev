# Static Site Routing and Headers

## Redirect and Rewrite Rules

Configure in Dashboard (Settings > Redirects/Rewrites) or via Blueprint `routes` field.

### Rule types

| Type | Behavior | Status code |
|------|----------|-------------|
| `redirect` | Client-side redirect (browser URL changes) | 301 (permanent) or 302 (temporary) |
| `rewrite` | Server-side rewrite (browser URL stays the same) | Transparent |

### SPA catch-all (most common)

Every SPA needs this rule to handle client-side routing:

```yaml
routes:
  - type: rewrite
    source: /*
    destination: /index.html
```

Without this, direct navigation to `/dashboard` or `/about` returns 404 from the CDN.

### Ordering

Rules are evaluated **top to bottom**. Place specific rules above catch-all rules:

```yaml
routes:
  # Specific redirects first
  - type: redirect
    source: /old-blog/*
    destination: /blog/*
  - type: redirect
    source: /docs
    destination: https://docs.example.com
  # SPA catch-all last
  - type: rewrite
    source: /*
    destination: /index.html
```

### Path patterns

| Pattern | Matches |
|---------|---------|
| `/exact` | Only `/exact` |
| `/path/*` | `/path/` and everything under it |
| `/*` | Everything (catch-all) |

## Custom Response Headers

Configure in Dashboard (Settings > Headers) or via Blueprint `headers` field.

### Security headers

```yaml
headers:
  - path: /*
    name: X-Frame-Options
    value: DENY
  - path: /*
    name: X-Content-Type-Options
    value: nosniff
  - path: /*
    name: Referrer-Policy
    value: strict-origin-when-cross-origin
  - path: /*
    name: Permissions-Policy
    value: camera=(), microphone=(), geolocation=()
```

### Cache headers for static assets

```yaml
headers:
  - path: /assets/*
    name: Cache-Control
    value: public, max-age=31536000, immutable
  - path: /index.html
    name: Cache-Control
    value: no-cache
```

Vite, Webpack, and other bundlers add content hashes to asset filenames, making `immutable` safe. The entry point (`index.html`) should always be revalidated.

### CORS headers

```yaml
headers:
  - path: /api/*
    name: Access-Control-Allow-Origin
    value: https://app.example.com
  - path: /api/*
    name: Access-Control-Allow-Methods
    value: GET, POST, OPTIONS
```

## Automatic behaviors

- **HTTP → HTTPS** redirect is automatic (no configuration needed)
- **Brotli compression** is applied automatically
- **Cache invalidation** happens immediately on every deploy
