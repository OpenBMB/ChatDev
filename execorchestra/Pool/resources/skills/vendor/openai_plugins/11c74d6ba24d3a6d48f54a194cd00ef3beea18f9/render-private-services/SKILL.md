---
name: render-private-services
description: >-
  Configures Render private services—internal-only apps that accept traffic
  exclusively from other Render services over the private network. Use when
  the user needs an internal API, microservice, gRPC server, sidecar, or any
  service that should not be publicly accessible. Also use when choosing
  between a private service and a background worker.
  Trigger terms: private service, pserv, internal service, internal API,
  microservice, gRPC, not public, private network service.
license: MIT
compatibility: Render private services (paid plans)
metadata:
  author: Render
  version: "1.0.0"
  category: compute
---

# Render Private Services

Private services are identical to web services except they have **no public URL**. They are reachable only by other Render services on the same **private network** (same region + workspace). Use them for internal APIs, microservices, gRPC servers, sidecar processes, and anything that should never face the internet.

## When to Use

- Building an **internal API** or **microservice** behind a public gateway
- Running a **gRPC**, **TCP**, or other non-HTTP server that only your services call
- Deploying infrastructure components (**Elasticsearch**, **ClickHouse**, **RabbitMQ**)
- Choosing between a **private service** and a **background worker**

For public-facing HTTP services, use **render-web-services**. For services that don't receive any traffic, use **render-background-workers**.

## Private Service vs Background Worker

| Criterion | Private Service | Background Worker |
|-----------|----------------|-------------------|
| Binds to a port | **Yes** (required) | No |
| Receives private network traffic | **Yes** | No |
| Sends outbound traffic | Yes | Yes |
| Has internal hostname | **Yes** | No |
| Use case | Internal APIs, gRPC, TCP servers | Queue consumers, async processors |

**Rule of thumb:** If the process **listens on a port** and other services call it, it's a private service. If it **pulls work from a queue** and never receives requests, it's a background worker.

## How Private Services Work

- No `onrender.com` subdomain—not reachable from the internet
- Reachable at `<service-name>:<port>` on the private network by services in the same region and workspace
- Can listen on **any port** (except restricted system ports)—not limited to HTTP or port 10000
- Supports **any protocol**: HTTP, gRPC, TCP, WebSocket, custom binary protocols
- Same build/deploy lifecycle as web services (build command, start command, pre-deploy, health checks via the private network)
- Supports persistent disks, scaling, Docker runtime—same capabilities as web services

## Connecting to a Private Service

Other services reference a private service via its **internal hostname and port**:

```
http://<service-name>:<port>
```

In Blueprints, wire the address using `fromService`:

```yaml
- key: INTERNAL_API_URL
  fromService:
    name: my-api
    type: pserv
    property: hostport
```

Available `fromService` properties for `pserv`:

| Property | Value |
|----------|-------|
| `host` | Internal hostname (e.g. `my-api`) |
| `port` | Port the service listens on |
| `hostport` | `host:port` combined (e.g. `my-api:10000`) |

You can also reference a specific env var from the private service using `envVarKey` instead of `property`.

## Port Binding

Private services **must bind to at least one port**. If your process does not need to receive traffic, create a background worker instead.

- Bind to `0.0.0.0` (not `127.0.0.1` or `localhost`)
- The `PORT` env var defaults to `10000`, but you can listen on any non-restricted port
- For non-HTTP protocols (gRPC, TCP), configure your server on the desired port and tell consumers the `hostport`

## Blueprint Configuration

```yaml
services:
  - type: pserv
    name: internal-api
    runtime: node
    region: oregon
    plan: starter
    buildCommand: npm ci && npm run build
    startCommand: npm start
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: db
          property: connectionString
```

### Microservices pattern (gateway + internal services)

```yaml
services:
  - type: web
    name: gateway
    runtime: node
    plan: starter
    region: oregon
    buildCommand: npm ci && npm run build
    startCommand: npm start
    envVars:
      - key: USER_SERVICE_URL
        fromService:
          name: user-service
          type: pserv
          property: hostport
      - key: BILLING_SERVICE_URL
        fromService:
          name: billing-service
          type: pserv
          property: hostport

  - type: pserv
    name: user-service
    runtime: node
    plan: starter
    region: oregon
    buildCommand: npm ci
    startCommand: node server.js
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: db
          property: connectionString

  - type: pserv
    name: billing-service
    runtime: python
    plan: starter
    region: oregon
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn billing:app
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: db
          property: connectionString
```

## References

| Document | Contents |
|----------|----------|
| `references/patterns.md` | Microservice topology, gRPC setup, sidecar patterns, health checks for private services |

## Related Skills

- **render-web-services** — Public HTTP services
- **render-networking** — Private network, DNS, service discovery
- **render-background-workers** — Services that don't receive traffic
- **render-blueprints** — Full `render.yaml` schema, `fromService` wiring
- **render-scaling** — Instance types and autoscaling for private services
