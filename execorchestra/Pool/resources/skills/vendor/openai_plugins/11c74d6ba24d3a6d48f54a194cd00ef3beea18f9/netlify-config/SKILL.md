---
name: netlify-config
description: Reference for netlify.toml configuration. Use when configuring build settings, redirects, rewrites, headers, deploy contexts, environment variables, or any site-level configuration. Covers the complete netlify.toml syntax including redirects with splats/conditions, headers, deploy contexts, functions config, and edge functions config.
---

# Netlify Configuration (netlify.toml)

Place `netlify.toml` at the repository root (or at the base directory for monorepos).

## Build Settings

```toml
[build]
  base = "project/"          # Base directory (default: root)
  command = "npm run build"  # Build command
  publish = "dist/"          # Output directory
```

## Redirects

```toml
# Basic redirect
[[redirects]]
from = "/old"
to = "/new"
status = 301              # 301 (default), 302, 200 (rewrite), 404

# SPA catch-all
[[redirects]]
from = "/*"
to = "/index.html"
status = 200

# Splat (wildcard)
[[redirects]]
from = "/blog/*"
to = "/news/:splat"

# Path parameters
[[redirects]]
from = "/users/:id"
to = "/api/users/:id"
status = 200

# Force (override existing files)
[[redirects]]
from = "/app/*"
to = "/index.html"
status = 200
force = true

# Proxy to external service
[[redirects]]
from = "/api/*"
to = "https://api.example.com/:splat"
status = 200
[redirects.headers]
  X-Custom = "value"

# Country/language conditions
[[redirects]]
from = "/*"
to = "/fr/:splat"
status = 200
conditions = { Country = ["FR"], Language = ["fr"] }
```

**Rule order matters** — Netlify processes the first matching rule. Place specific rules before general ones.

## Headers

```toml
[[headers]]
for = "/*"
[headers.values]
  X-Frame-Options = "DENY"
  X-Content-Type-Options = "nosniff"

[[headers]]
for = "/assets/*"
[headers.values]
  Cache-Control = "public, max-age=31536000, immutable"
```

Headers apply only to files served from Netlify's CDN (not to function or edge function responses — set those in code).

## Deploy Contexts

Override settings per deploy context:

```toml
[context.production]
command = "npm run build"
environment = { NODE_ENV = "production" }

[context.deploy-preview]
command = "npm run build:preview"

[context.branch-deploy]
command = "npm run build:staging"

[context.dev]
environment = { NODE_ENV = "development" }

# Specific branch
[context."staging"]
command = "npm run build:staging"
```

## Environment Variables

```toml
[build.environment]
NODE_VERSION = "20"

[context.production.environment]
API_URL = "https://api.prod.com"

[context.deploy-preview.environment]
API_URL = "https://api.staging.com"
```

**Do not put secrets in netlify.toml** (it's committed to source control). Use the Netlify UI or CLI for sensitive values. See the **netlify-cli-and-deploy** skill for CLI environment variable management.

## Functions Configuration

```toml
[functions]
directory = "netlify/functions"   # Default
node_bundler = "esbuild"

# Scheduled function
[functions."cleanup"]
schedule = "@daily"
```

## Edge Functions Configuration

```toml
[[edge_functions]]
path = "/admin"
function = "auth"

# Import map for Deno URL imports
[functions]
deno_import_map = "./import_map.json"
```

## Dev Server

```toml
[dev]
command = "npm start"       # Dev server command
port = 8888                 # Netlify Dev port
targetPort = 3000           # Your app's dev server port
framework = "#auto"         # "#auto", "#static", "#custom"
```

## Plugins

```toml
[[plugins]]
package = "@netlify/plugin-lighthouse"
[plugins.inputs]
  audits = ["performance", "accessibility"]
```

## Image CDN

```toml
[images]
remote_images = ["https://example\\.com/.*"]
```

See the **netlify-image-cdn** skill for full Image CDN usage.
