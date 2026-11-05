# Astro on Netlify

## Setup

Install the Netlify adapter:

```bash
npx astro add netlify
```

This installs `@astrojs/netlify` and updates `astro.config.*` automatically.

### Manual Setup

```bash
npm install @astrojs/netlify
```

```typescript
// astro.config.mjs
import { defineConfig } from "astro/config";
import netlify from "@astrojs/netlify";

export default defineConfig({
  output: "server",  // or "hybrid" for mixed static/SSR
  adapter: netlify(),
});
```

## Output Modes

| Mode | Behavior |
|---|---|
| `"static"` | Fully pre-rendered at build time (no adapter needed) |
| `"server"` | All pages rendered on request (SSR) |
| `"hybrid"` | Static by default, opt-in to SSR per page with `export const prerender = false` |

## What the Adapter Does

- Converts Astro server routes into Netlify Functions
- Handles SSR, API routes, and middleware
- Maps Astro's routing to Netlify's function routing
- You do **not** write raw Netlify Functions for Astro's server routes

## API Routes

Astro API routes (in `src/pages/api/`) are handled by the adapter:

```typescript
// src/pages/api/items.ts
import type { APIRoute } from "astro";

export const GET: APIRoute = async () => {
  return new Response(JSON.stringify({ items: [] }), {
    headers: { "Content-Type": "application/json" },
  });
};

export const POST: APIRoute = async ({ request }) => {
  const data = await request.json();
  return new Response(JSON.stringify({ created: data }), { status: 201 });
};
```

## Forms (HTML Pattern)

Astro renders HTML server-side, so Netlify can detect forms directly:

```astro
---
// src/pages/contact.astro
---
<form name="contact" method="POST" data-netlify="true">
  <label>Name: <input type="text" name="name" /></label>
  <label>Email: <input type="email" name="email" /></label>
  <label>Message: <textarea name="message"></textarea></label>
  <button type="submit">Send</button>
</form>
```

For form submissions that should redirect back with feedback, handle the POST in an API route and redirect:

```typescript
// src/pages/api/contact.ts
export const POST: APIRoute = async ({ request, redirect }) => {
  const formData = await request.formData();
  // Process form...
  return redirect("/contact?success=true");
};
```

## Custom 404

Create `src/pages/404.astro`. Astro handles this automatically.

## Local Development

**Option A: Astro dev server** (simpler, but no Netlify primitives):

```bash
npm run dev    # astro dev
```

**Option B: netlify dev** (full Netlify environment including functions, env vars):

```bash
netlify dev
```

The Astro adapter's local dev experience with `netlify dev` varies — for Blobs and DB access, `netlify dev` is recommended. If using `@netlify/vite-plugin` alongside Astro, local platform primitives may also be available via the standard dev server, but this integration is less mature than with pure Vite projects.

## Build and Deploy

```toml
# netlify.toml
[build]
command = "astro build"
publish = "dist"
```

The adapter configures the publish directory and function routing automatically.
