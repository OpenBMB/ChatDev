# Static Site Framework Configurations

Build commands and publish paths for common static site generators and frontend frameworks.

## Framework Reference

### React (Create React App)

```yaml
buildCommand: npm ci && npm run build
staticPublishPath: build
```

### React / Vue / Svelte (Vite)

```yaml
buildCommand: npm ci && npm run build
staticPublishPath: dist
```

### Next.js (static export)

Requires `output: 'export'` in `next.config.js`:

```yaml
buildCommand: npm ci && next build
staticPublishPath: out
```

If you need SSR (`next start`), use a **Web Service** instead.

### Nuxt (static generate)

```yaml
buildCommand: npm ci && nuxt generate
staticPublishPath: .output/public
```

For SSR (`nuxt build` + server), use a **Web Service**.

### SvelteKit (static adapter)

Requires `@sveltejs/adapter-static` in `svelte.config.js`:

```yaml
buildCommand: npm ci && npm run build
staticPublishPath: build
```

### Astro

Default static output:

```yaml
buildCommand: npm ci && astro build
staticPublishPath: dist
```

For SSR mode, use a **Web Service**.

### Hugo

```yaml
buildCommand: hugo --minify
staticPublishPath: public
```

Set `HUGO_VERSION` env var if you need a specific version.

### Gatsby

```yaml
buildCommand: npm ci && gatsby build
staticPublishPath: public
```

### Docusaurus

```yaml
buildCommand: npm ci && npm run build
staticPublishPath: build
```

### Jekyll

```yaml
buildCommand: bundle exec jekyll build
staticPublishPath: _site
```

### Eleventy (11ty)

```yaml
buildCommand: npm ci && npx @11ty/eleventy
staticPublishPath: _site
```

### Angular

```yaml
buildCommand: npm ci && ng build --configuration production
staticPublishPath: dist/<project-name>/browser
```

Angular 17+ uses `browser` subfolder. Older versions use `dist/<project-name>`.

## Environment Variables

Common build-time env vars:

| Variable | Purpose |
|----------|---------|
| `NODE_VERSION` | Pin Node.js version (e.g. `20`) |
| `HUGO_VERSION` | Pin Hugo version |
| `PYTHON_VERSION` | Pin Python version (Jekyll, Pelican) |
| `SKIP_INSTALL_DEPS` | Set to `true` to skip auto dependency install |
| `NODE_ENV` | Defaults to `production` on Render |

## SPA Routing

All SPAs need a rewrite rule to serve `index.html` for all paths. Add this to every SPA Blueprint:

```yaml
routes:
  - type: rewrite
    source: /*
    destination: /index.html
```

Without this, refreshing or deep-linking to any route returns 404.
