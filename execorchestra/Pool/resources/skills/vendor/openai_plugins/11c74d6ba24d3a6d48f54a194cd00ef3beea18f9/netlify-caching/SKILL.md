---
name: netlify-caching
description: Guide for controlling caching on Netlify's CDN. Use when configuring cache headers, setting up stale-while-revalidate, implementing on-demand cache purge, or understanding Netlify's CDN caching behavior. Covers Cache-Control, Netlify-CDN-Cache-Control, cache tags, durable cache, and framework-specific caching patterns.
---

# Caching on Netlify

## Default Behavior

**Static assets** are cached automatically:
- CDN: cached for 1 year, invalidated on every deploy
- Browser: always revalidates (`max-age=0, must-revalidate`)
- No configuration needed

**Dynamic responses** (functions, edge functions, proxied) are **not cached by default**. Add cache headers explicitly.

## Cache-Control Headers

Three headers control caching, from most to least specific:

| Header | Who sees it | Use case |
|---|---|---|
| `Netlify-CDN-Cache-Control` | Netlify CDN only (stripped before browser) | CDN-only caching |
| `CDN-Cache-Control` | All CDN caches (stripped before browser) | Multi-CDN setups |
| `Cache-Control` | Browser and all caches | General caching |

### Common Patterns

```typescript
// Cache at CDN for 1 hour, browser always revalidates
return new Response(body, {
  headers: {
    "Netlify-CDN-Cache-Control": "public, s-maxage=3600, must-revalidate",
    "Cache-Control": "public, max-age=0, must-revalidate",
  },
});

// Stale-while-revalidate (serve stale for 2 min while refreshing)
return new Response(body, {
  headers: {
    "Netlify-CDN-Cache-Control": "public, max-age=60, stale-while-revalidate=120",
  },
});

// Durable cache (shared across edge nodes, serverless functions only)
return new Response(body, {
  headers: {
    "Netlify-CDN-Cache-Control": "public, durable, max-age=60, stale-while-revalidate=120",
  },
});
```

### Immutable Assets

For fingerprinted files (hash in filename):

```toml
# netlify.toml
[[headers]]
for = "/assets/*"
[headers.values]
Cache-Control = "public, max-age=31536000, immutable"
```

## Cache Tags and On-Demand Purge

Tag responses for selective cache invalidation:

```typescript
return new Response(body, {
  headers: {
    "Netlify-Cache-ID": "product,listing",
    "Netlify-CDN-Cache-Control": "public, s-maxage=86400",
  },
});
```

Purge by tag:

```typescript
import { purgeCache } from "@netlify/functions";

export default async () => {
  await purgeCache({ tags: ["product"] });
  return new Response("Purged", { status: 202 });
};
```

Purge entire site:

```typescript
await purgeCache();
```

Responses with `Netlify-Cache-ID` are **excluded from automatic deploy-based invalidation** — they must be purged explicitly.

## Cache Key Variation

Customize what creates separate cache entries:

```typescript
return new Response(body, {
  headers: {
    "Netlify-Vary": "cookie=ab_test|is_logged_in",
    // Other options: query=param1|param2, header=X-Custom, country=us|de, language=en|fr
  },
});
```

## Framework-Specific Caching

### Next.js
ISR uses Netlify's durable cache automatically (runtime 5.5.0+). `revalidatePath` and `revalidateTag` trigger cache purge.

### Astro / Remix
Full control over cache headers in server routes. Set `Netlify-CDN-Cache-Control` in responses for CDN caching.

### Nuxt
Default Nitro preset handles caching. ISR-style patterns use `routeRules` with `swr` or `isr` options.

### Vite SPA
Static assets are cached by default. API responses from Netlify Functions need explicit cache headers.

## Debugging

Check the `Cache-Status` response header:
- `HIT` — served from cache
- `MISS` — generated fresh
- `REVALIDATED` — stale content was revalidated

## Constraints

- Basic auth disables caching for the entire site
- Durable cache is serverless functions only (not edge functions)
- Same URL must return identical `Netlify-Vary` headers across responses
- Deploy invalidation is scoped to deploy context (production vs preview)
