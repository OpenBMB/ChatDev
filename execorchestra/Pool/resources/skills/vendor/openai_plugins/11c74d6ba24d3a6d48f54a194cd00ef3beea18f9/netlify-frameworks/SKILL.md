---
name: netlify-frameworks
description: Guide for deploying web frameworks on Netlify. Use when setting up a framework project (Vite/React, Astro, TanStack Start, Next.js, Nuxt, SvelteKit, Remix) for Netlify deployment, configuring adapters or plugins, or troubleshooting framework-specific Netlify integration. Covers what Netlify needs from each framework and how adapters handle server-side rendering.
---

# Frameworks on Netlify

Netlify supports any framework that produces static output. For frameworks with server-side capabilities (SSR, API routes, middleware), an adapter or plugin translates the framework's server-side code into Netlify Functions and Edge Functions automatically.

## How It Works

During build, the framework adapter writes files to `.netlify/v1/` — functions, edge functions, redirects, and configuration. Netlify reads these to deploy the site. You do not need to write Netlify Functions manually when using a framework adapter for server-side features.

## Detecting Your Framework

Check these files to determine the framework:

| File | Framework |
|---|---|
| `astro.config.*` | Astro |
| `next.config.*` | Next.js |
| `nuxt.config.*` | Nuxt |
| `vite.config.*` + `react-router` | Vite + React (SPA or Remix) |
| `app.config.*` + `@tanstack/react-start` | TanStack Start |
| `svelte.config.*` | SvelteKit |

## Framework Reference Guides

Each framework has specific adapter/plugin requirements and local dev patterns:

- **Vite + React (SPA or with server routes)**: See [references/vite.md](references/vite.md)
- **Astro**: See [references/astro.md](references/astro.md)
- **TanStack Start**: See [references/tanstack.md](references/tanstack.md)
- **Next.js**: See [references/nextjs.md](references/nextjs.md)

## General Patterns

### Client-Side Routing (SPA)

For single-page apps with client-side routing, add a catch-all redirect:

```toml
# netlify.toml
[[redirects]]
from = "/*"
to = "/index.html"
status = 200
```

### Custom 404 Pages

- **Static sites**: Create a `404.html` in your publish directory. Netlify serves it automatically for unmatched routes.
- **SSR frameworks**: Handle 404s in the framework's routing (the adapter maps this to Netlify's function routing).

### Environment Variables in Frameworks

Each framework exposes environment variables to client-side code differently:

| Framework | Client prefix | Access pattern |
|---|---|---|
| Vite / React | `VITE_` | `import.meta.env.VITE_VAR` |
| Astro | `PUBLIC_` | `import.meta.env.PUBLIC_VAR` |
| Next.js | `NEXT_PUBLIC_` | `process.env.NEXT_PUBLIC_VAR` |
| Nuxt | `NUXT_PUBLIC_` | `useRuntimeConfig().public.var` |

Server-side code in all frameworks can access variables via `process.env.VAR` or `Netlify.env.get("VAR")`.

## Bundled References (Load As Needed)

- [Vite + React guide](references/vite.md)
- [Astro guide](references/astro.md)
- [TanStack Start guide](references/tanstack.md)
- [Next.js guide](references/nextjs.md)
