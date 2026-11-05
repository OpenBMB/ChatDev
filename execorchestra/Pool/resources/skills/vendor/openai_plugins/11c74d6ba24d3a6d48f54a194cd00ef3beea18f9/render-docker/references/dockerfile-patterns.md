# Dockerfile patterns for Render

These templates assume **linux/amd64**, **BuildKit**, and that the app listens on **`0.0.0.0:$PORT`** (Render injects `PORT`). Use **multi-stage** builds, **minimal** final images, and a **non-root** user where practical. Prefer **`exec`** in the entrypoint chain so PID 1 receives **SIGTERM** for graceful shutdown.

---

## Node.js (multi-stage)

```dockerfile
# syntax=docker/dockerfile:1
ARG NODE_VERSION=20
FROM node:${NODE_VERSION}-bookworm-slim AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:${NODE_VERSION}-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN addgroup -g 1001 -S nodejs && adduser -S nodejs -u 1001 -G nodejs
COPY --from=builder --chown=nodejs:nodejs /app/dist ./dist
COPY --from=builder --chown=nodejs:nodejs /app/node_modules ./node_modules
COPY --from=builder --chown=nodejs:nodejs /app/package.json ./
ARG PORT=10000
ENV PORT=$PORT
EXPOSE $PORT
USER nodejs
CMD ["node", "dist/server.js"]
```

Adjust `build` output paths and start file for your framework. For graceful shutdown, avoid wrapping Node in a shell unless you end with `exec node ...`.

---

## Python (multi-stage)

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.12-bookworm AS builder
WORKDIR /app
ENV PIP_NO_CACHE_DIR=1
COPY requirements.txt .
RUN pip wheel --no-deps -w /wheels -r requirements.txt

FROM python:3.12-slim-bookworm AS runner
WORKDIR /app
RUN useradd -r -u 1001 appuser
COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels
COPY . .
RUN chown -R appuser:appuser /app
USER appuser
ARG PORT=10000
ENV PORT=$PORT
EXPOSE $PORT
CMD ["sh", "-c", "exec gunicorn -b 0.0.0.0:${PORT} myapp.wsgi:application"]
```

Swap Gunicorn/uvicorn and module paths for ASGI or Flask. Use **`exec`** in `CMD` so the worker is PID 1.

---

## Go (multi-stage)

```dockerfile
# syntax=docker/dockerfile:1
FROM golang:1.22-bookworm AS builder
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o /out/server .

FROM alpine:3.19 AS runner
RUN adduser -D -u 1001 appuser
WORKDIR /app
COPY --from=builder /out/server .
USER appuser
ARG PORT=10000
ENV PORT=$PORT
EXPOSE $PORT
ENTRYPOINT ["/app/server"]
```

`scratch` is an option if you do not need CA certs or shell; add certs and `USER 65534` patterns as needed.

---

## Ruby (multi-stage)

```dockerfile
# syntax=docker/dockerfile:1
FROM ruby:3.3-bookworm AS builder
WORKDIR /app
RUN apt-get update -y && apt-get install -y --no-install-recommends build-essential \
  && rm -rf /var/lib/apt/lists/*
COPY Gemfile Gemfile.lock ./
RUN bundle config set --local deployment true \
  && bundle config set --local without 'development test' \
  && bundle install --jobs 4 --retry 3

FROM ruby:3.3-slim-bookworm AS runner
WORKDIR /app
RUN apt-get update -y && apt-get install -y --no-install-recommends libpq5 \
  && rm -rf /var/lib/apt/lists/* \
  && useradd -r -u 1001 appuser
COPY --from=builder /usr/local/bundle /usr/local/bundle
COPY . .
RUN chown -R appuser:appuser /app
USER appuser
ARG PORT=10000
ENV PORT=$PORT RAILS_ENV=production
EXPOSE $PORT
CMD ["sh", "-c", "exec bundle exec puma -b tcp://0.0.0.0:${PORT}"]
```

Add native packages your gems require in the **runner** stage only.

---

## Rust (multi-stage)

```dockerfile
# syntax=docker/dockerfile:1
FROM rust:1-bookworm AS builder
WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY src ./src
RUN cargo build --release

FROM debian:bookworm-slim AS runner
RUN useradd -r -u 1001 appuser
WORKDIR /app
RUN apt-get update -y && apt-get install -y --no-install-recommends ca-certificates \
  && rm -rf /var/lib/apt/lists/*
COPY --from=builder /src/target/release/myapp /app/myapp
USER appuser
ARG PORT=10000
ENV PORT=$PORT
EXPOSE $PORT
ENTRYPOINT ["/app/myapp"]
```

For static binaries with no TLS needs, **`scratch`** plus copied CA bundle is possible; **debian-slim** is simpler when linking OpenSSL or libc.

---

## Static site (build frontend, serve with Caddy or nginx)

**Caddy** (simple config, automatic HTTPS is not used on Render the same way; you still bind `$PORT`):

```dockerfile
# syntax=docker/dockerfile:1
FROM node:20-bookworm-slim AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM caddy:2-alpine AS runner
RUN adduser -D -u 1001 caddy
COPY --from=builder /app/dist /srv
ARG PORT=10000
ENV PORT=$PORT
EXPOSE $PORT
COPY <<'CADDYFILE' /etc/caddy/Caddyfile
:{$PORT}
root * /srv
file_server
CADDYFILE
USER caddy
CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
```

**nginx** variant: copy `dist` to `/usr/share/nginx/html`, templated `nginx.conf` with `listen $PORT` via `envsubst` at container start, or a fixed `listen 10000` matching `PORT`. Keep the final stage minimal and run **nginx** as non-root where possible (official image docs vary by tag).

---

## Cross-cutting practices

- **Signals:** use `exec` in shell wrappers so the application process is PID 1, or a minimal init only if you understand the tradeoffs.
- **Non-root:** set `USER` after `COPY` and `chown`.
- **Layers:** combine `RUN` steps that share the same cache epoch when it does not hurt readability; split when it improves cache hits for dependencies.
- **Secrets:** never `ARG` for tokens; use runtime env or BuildKit `--mount=type=secret` for build-time only.
