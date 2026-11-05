---
name: render-docker
description: >-
  Builds and deploys Docker containers on Render—Dockerfiles, multi-stage
  builds, Blueprint Docker fields, private registries, layer caching, and
  platform constraints. Use when the user mentions Docker,
  Dockerfile, container images, multi-stage builds, container registry,
  GHCR, ECR, BuildKit, dockerContext, runtime docker or image, or
  optimizing Docker builds on Render.
license: MIT
compatibility: >-
  Any Render compute service (web, private, worker, cron) with runtime: docker
  or runtime: image.
metadata:
  author: Render
  version: "1.0.0"
  category: deployment
---

# Render Docker Deployments

Render uses **BuildKit** for Docker builds. All compute service types that support custom runtimes can use **`runtime: docker`** (build from a Dockerfile in the repo) or **`runtime: image`** (pull a prebuilt image; no Dockerfile build on Render). Deeper patterns and copy-paste templates live under `references/`.

## When to Use

- Authoring or debugging a **Dockerfile** for a Render service
- Choosing **`runtime: docker`** vs **`runtime: image`** in a Blueprint
- Wiring **private base images** or **prebuilt images** with registry credentials
- **Multi-stage builds**, **build args**, **secrets**, and **layer caching**
- **Performance** and **security** hardening of container images on Render

For full Blueprint authoring, see **render-blueprints**. For end-to-end deploy flows, see **render-deploy**.

## Render Docker Builds

- **BuildKit** is used for Docker builds on Render.
- **`runtime: docker`**: Render builds an image from your repo using `dockerfilePath`, `dockerContext`, and optional `dockerCommand` (overrides image `CMD`).
- **`runtime: image`**: Render pulls **`image.url`**; no repo-based image build. Pair with **`registryCredential`** when the registry is private.

## Blueprint Configuration

| Field | Role |
|-------|------|
| `dockerfilePath` | Path to the Dockerfile (default `./Dockerfile`) |
| `dockerContext` | Build context directory (what is sent to the daemon) |
| `dockerCommand` | Overrides the container `CMD` after the image is built |
| `image.url` | Image reference for `runtime: image` (registry/repo:tag or digest) |
| `registryCredential` | Auth for private pulls; often `fromRegistryCreds` → Dashboard-stored credential |

Example sketch (values illustrative):

```yaml
services:
  - type: web
    name: api
    runtime: docker
    region: oregon
    plan: starter
    dockerfilePath: ./Dockerfile
    dockerContext: .
    dockerCommand: node server.js
    envVars:
      - key: PORT
        value: 10000
```

For `runtime: image`, set `image.url` and, if needed, `registryCredential` per **Registry Configuration** below.

## Multi-Stage Builds

**Recommended for production.** Use a **builder** stage for compilation and dependency installation, and a minimal **runner** stage that only copies artifacts and runtime files. Benefits:

- Smaller images and faster pulls
- Fewer tools and secrets in the final image (smaller attack surface)
- Clear separation between build-time and run-time dependencies

See `references/dockerfile-patterns.md` for language-specific templates.

## Build Args vs Secrets

**Critical:** **Never pass secrets via `ARG`.** Build arguments are stored in image **layers** and can be recovered from the image history or intermediate layers.

- Prefer **runtime environment variables** (Render **env vars** / secret files) for application secrets.
- For **build-time** secrets (e.g. private package feeds), use **Docker BuildKit secret mounts** (`RUN --mount=type=secret,...`) rather than `ARG`.

Treat anything sensitive as **runtime** or **BuildKit secret mount**, not as a build arg.

## Registry Configuration

Private **base images** (for `runtime: docker`) or **prebuilt images** (`runtime: image`) need authentication:

- Store credentials in the Render Dashboard under **Registry Credentials**.
- In Blueprint, reference them with **`registryCredential.fromRegistryCreds.name`** (match the Dashboard name).

Supports common registries (Docker Hub, GHCR, ECR, Google Artifact Registry, and others). Step-by-step per provider: `references/registry-setup.md`.

**Prebuilt image services** do **not** auto-deploy when the tag moves in the registry; trigger a **manual redeploy** or use a **deploy hook** when you publish a new image.

## Layer Caching

- Render **caches Docker layers** between builds; **order Dockerfile instructions** so that frequently unchanged layers stay early (see `references/optimization-guide.md`).
- **Tags and caching:** mutable tags like **`latest`** can resolve to **stale cached** images. Prefer **immutable** references: **digest** (`repo/image@sha256:...`) or **version pins** (`v1.2.3`).

## Platform Specifics

- Render builds **linux/amd64**. Avoid assumptions about other architectures in production images.
- **Port binding** matches native services: bind HTTP to **`0.0.0.0:$PORT`** (Render sets `PORT`).
- **Health checks** behave like non-Docker web services (`healthCheckPath`, etc.).
- **Secret files** from Render appear under **`/etc/secrets/`** — do not rely on repo-root secret paths inside the container unless you copy or mount them explicitly in the image.

## `.dockerignore` and Start Commands

- Always maintain a **`.dockerignore`** that excludes **`node_modules`**, **`.git`**, **`.env`**, build artifacts, logs, and OS junk. This shrinks context upload time and avoids leaking local files into layers. Lists and rationale: `references/optimization-guide.md`.
- **Custom start command:** if you need multiple shell steps, use a single shell form, e.g. **`/bin/sh -c 'set -e; ./migrate && exec node server.js'`** (prefer **`exec`** so your app receives signals for graceful shutdown).

## References

| Document | Contents |
|----------|----------|
| `references/dockerfile-patterns.md` | Multi-stage templates (Node, Python, Go, Ruby, Rust, static sites) |
| `references/registry-setup.md` | Docker Hub, GHCR, ECR, Artifact Registry + Blueprint wiring |
| `references/optimization-guide.md` | Layer order, `.dockerignore`, BuildKit cache mounts, debugging |

## Related Skills

- **render-deploy** — Deploy flows, Blueprint vs Dashboard, operational steps
- **render-blueprints** — Full `render.yaml` schema, wiring, and validation
- **render-web-services** — Web service behavior, health checks, and HTTP edge cases
