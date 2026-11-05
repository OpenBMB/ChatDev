---
name: netlify-edge-functions
description: Guide for writing Netlify Edge Functions. Use when building middleware, geolocation-based logic, request/response manipulation, authentication checks, A/B testing, or any low-latency edge compute. Covers Deno runtime, context.next() middleware pattern, geolocation, and when to choose edge vs serverless.
---

# Netlify Edge Functions

Edge functions run on Netlify's globally distributed edge network (Deno runtime), providing low-latency responses close to users.

## Syntax

```typescript
import type { Config, Context } from "@netlify/edge-functions";

export default async (req: Request, context: Context) => {
  return new Response("Hello from the edge!");
};

export const config: Config = {
  path: "/hello",
};
```

Place files in `netlify/edge-functions/`. Uses `.ts`, `.js`, `.tsx`, or `.jsx` extensions.

## Config Object

```typescript
export const config: Config = {
  path: "/api/*",                    // URLPattern path(s)
  excludedPath: "/api/public/*",     // Exclusions
  method: ["GET", "POST"],           // HTTP methods
  onError: "bypass",                 // "fail" (default), "bypass", or "/error-page"
  cache: "manual",                   // Enable response caching
};
```

## Middleware Pattern

Use `context.next()` to invoke the next handler in the chain and optionally modify the response:

```typescript
export default async (req: Request, context: Context) => {
  // Before: modify request or short-circuit
  if (!isAuthenticated(req)) {
    return new Response("Unauthorized", { status: 401 });
  }

  // Continue to origin/next function
  const response = await context.next();

  // After: modify response
  response.headers.set("x-custom-header", "value");
  return response;
};
```

Return `undefined` to pass through without modification:

```typescript
export default async (req: Request, context: Context) => {
  if (!shouldHandle(req)) return; // continues to next handler
  return new Response("Handled");
};
```

## Geolocation and IP

```typescript
export default async (req: Request, context: Context) => {
  const { city, country, subdivision, timezone } = context.geo;
  const ip = context.ip;

  if (country?.code === "DE") {
    return Response.redirect(new URL("/de", req.url));
  }
};
```

Local dev with mocked geo: `netlify dev --geo=mock --country=US`

## Environment Variables

Use `Netlify.env` (not `process.env` or `Deno.env`):

```typescript
const secret = Netlify.env.get("API_SECRET");
```

## Module Support

- **Node.js builtins**: `import { randomBytes } from "node:crypto";`
- **npm packages**: Install via npm and import by name
- **Deno modules**: URL imports (e.g., `import X from "https://esm.sh/package"`)

For URL imports, use an import map:

```json
// import_map.json
{ "imports": { "html-rewriter": "https://ghuc.cc/worker-tools/html-rewriter/index.ts" } }
```

```toml
# netlify.toml
[functions]
  deno_import_map = "./import_map.json"
```

## When to Use Edge vs Serverless

| Use Edge Functions for | Use Serverless Functions for |
|---|---|
| Low-latency responses | Long-running operations (up to 15 min) |
| Request/response manipulation | Complex Node.js dependencies |
| Geolocation-based logic | Database-heavy operations |
| Auth checks and redirects | Background/scheduled tasks |
| A/B testing, personalization | Tasks needing > 512 MB memory |

## Limits

| Resource | Limit |
|---|---|
| CPU time | 50 ms per request |
| Memory | 512 MB per deployed set |
| Response header timeout | 40 seconds |
| Code size | 20 MB compressed |
