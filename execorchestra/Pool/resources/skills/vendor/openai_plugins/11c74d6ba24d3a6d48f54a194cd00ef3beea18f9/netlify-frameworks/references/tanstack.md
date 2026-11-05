# TanStack Start on Netlify

## Setup

TanStack Start uses the Netlify Vite plugin for deployment.

```bash
npm install @netlify/vite-plugin
```

```typescript
// app.config.ts
import { defineConfig } from "@tanstack/react-start/config";
import netlify from "@netlify/vite-plugin";

export default defineConfig({
  vite: {
    plugins: [netlify()],
  },
});
```

## What the Plugin Does

- Handles SSR output for Netlify Functions
- Enables Netlify platform primitives (Blobs, DB, env vars) in local dev
- Maps TanStack Start's file-based routing to Netlify's infrastructure

## Server Functions

TanStack Start uses `createServerFn` for server-side logic. These are automatically handled by the Netlify Vite plugin — no raw Netlify Functions needed:

```typescript
import { createServerFn } from "@tanstack/react-start";

const getItems = createServerFn({ method: "GET" }).handler(async () => {
  // Server-side code — runs as Netlify Function in production
  const items = await db.select().from(itemsTable);
  return items;
});
```

## Local Development

```bash
npm run dev    # Uses Vite plugin — Netlify primitives available
```

The Vite plugin provides Functions, Blobs, DB, and environment variables during local dev without needing `netlify dev`.

## Build and Deploy

```toml
# netlify.toml
[build]
command = "npm run build"
publish = ".output/public"
```

The Vite plugin configures the output structure for Netlify automatically.
