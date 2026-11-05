# Docker build optimization on Render

Render uses **BuildKit** and **caches Docker layers** between builds. Small context uploads and stable early layers make builds faster and more predictable.

## Layer ordering (maximize cache hits)

1. Copy **dependency manifests** first (`package.json`, `package-lock.json`, `requirements.txt`, `go.mod`, `Gemfile`, etc.).
2. **Install dependencies** in a dedicated `RUN` (or use cache mounts — see below).
3. **Copy application source** last.

When application code changes, dependency layers should **not** rebuild. When only dependencies change, source layers may rebuild — that is usually cheaper than reinstalling everything every time.

## `.dockerignore`

Exclude anything not required for the build or runtime image. Typical entries:

```
node_modules
.git
.env
.env.*
__pycache__
*.pyc
.next
dist
build
*.log
.DS_Store
coverage
.vscode
.idea
```

**Too aggressive** `.dockerignore` rules are a common cause of **“file not found”** errors in `COPY` — if the build fails after tightening ignore rules, verify every `COPY` path is still in the context.

## Multi-stage benefits

- **Smaller final image** — no compilers, headers, or devDependencies in production.
- **Faster deploys** — less to pull and extract on each instance.
- **Security** — fewer packages and tools in the attack surface.

## BuildKit on Render

You can use:

- **Cache mounts:** `RUN --mount=type=cache,target=/root/.npm ...` or pip/npm/yarn caches to speed installs.
- **Secret mounts:** `RUN --mount=type=secret,id=npmrc ...` for private registry auth at build time **without** baking secrets into layers.

Enable features with the syntax directive when needed:

```dockerfile
# syntax=docker/dockerfile:1
```

## Image size tips

- Prefer **`-alpine`**, **`-slim`**, or **distroless** bases when compatible with your stack.
- After `apt-get install`, remove lists: `rm -rf /var/lib/apt/lists/*`.
- **Combine** related `RUN` instructions to reduce layer count when it does not hurt caching.
- Strip debug symbols in compiled languages (`-ldflags="-s -w"` for Go, release builds for Rust).

## Build caching on Render

- Layers are reused when **instructions and inputs** match previous builds.
- **Ordering matters:** put the slowest, most stable steps **early**.
- Busting cache intentionally: pass a **build arg** that changes when you want a full rebuild (use only for non-secret values).

## Debugging failed builds

1. Read **Render build logs** end-to-end; BuildKit output often names the failing step.
2. **Missing files:** verify paths relative to **`dockerContext`** and that `.dockerignore` is not excluding them.
3. **Wrong platform:** ensure artifacts target **linux/amd64** (emulation in local Docker can hide issues).
4. **Missing system libraries:** add packages in the correct stage (builder vs runner) for compile-time vs run-time.
5. **Out-of-memory:** large parallel compilations may need slimmer parallelism or a larger local/staging iteration loop before pushing.

## Mutable tags vs digests

Even with good Dockerfile caching, **deployed** images that use tags like **`latest`** can appear “stuck” if a registry or platform layer caches by tag. Prefer **version tags** or **SHA256 digests** for anything you need to be reproducible.
