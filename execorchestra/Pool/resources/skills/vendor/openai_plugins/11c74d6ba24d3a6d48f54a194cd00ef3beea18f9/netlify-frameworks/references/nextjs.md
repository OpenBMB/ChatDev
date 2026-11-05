# Next.js on Netlify

## Setup

Next.js on Netlify uses the `@netlify/next` runtime, which is installed automatically. No manual adapter installation is required — Netlify detects Next.js and configures the build automatically.

```toml
# netlify.toml
[build]
command = "next build"
publish = ".next"
```

## What the Runtime Does

- Converts Next.js server-side features (SSR, API routes, middleware, ISR) into Netlify Functions and Edge Functions
- Handles image optimization via Netlify Image CDN
- Maps Next.js routing to Netlify's infrastructure
- Supports App Router and Pages Router

## Key Configuration

### next.config.js

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "example.com" },
    ],
  },
};

module.exports = nextConfig;
```

Remote image patterns in `next.config.js` are automatically mapped to Netlify Image CDN's `remote_images` configuration.

## API Routes

Next.js API routes work automatically — they are deployed as Netlify Functions:

```typescript
// app/api/items/route.ts (App Router)
export async function GET() {
  return Response.json({ items: [] });
}

export async function POST(request: Request) {
  const data = await request.json();
  return Response.json({ created: data }, { status: 201 });
}
```

## Middleware

Next.js middleware is deployed as a Netlify Edge Function:

```typescript
// middleware.ts
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  // Runs at the edge on Netlify
  return NextResponse.next();
}
```

## ISR (Incremental Static Regeneration)

ISR works on Netlify. Pages with `revalidate` are cached and revalidated using Netlify's CDN cache with `stale-while-revalidate`. On-demand revalidation via `revalidatePath` and `revalidateTag` triggers Netlify cache purge.

## Local Development

```bash
npm run dev    # next dev — standard Next.js dev server
```

For Netlify-specific features (environment variables, edge middleware testing), use:

```bash
netlify dev
```

## Known Patterns

- **Static export** (`output: "export"`): Works without the runtime — produces a fully static site
- **Standalone mode** is not required; the Netlify runtime handles deployment automatically
- Environment variables use the `NEXT_PUBLIC_` prefix for client-side access
