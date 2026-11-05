---
name: render-web-services
description: >-
  Configures Render web services—port binding, TLS, health checks, custom
  domains, auto-deploy, PR previews, persistent disks, and deploy lifecycle.
  Use when the user needs to set up a web service, fix health check failures,
  add a custom domain, configure zero-downtime deploys, or troubleshoot port
  binding issues.
license: MIT
compatibility: Render web services (native runtimes or Docker)
metadata:
  author: Render
  version: "1.0.0"
  category: compute
---

# Render Web Services

This skill covers **Web Service** behavior on Render: how traffic reaches your process, how deploys go live, and how optional features (domains, disks, auto-deploy) interact. Use it alongside Blueprint and networking skills when wiring `render.yaml` or Dashboard settings.

## When to Use

- Configuring or debugging **port binding**, **PORT**, or **multi-port** web services
- **TLS/HTTPS** expectations at the edge vs inside the container
- **Health checks** blocking or rolling back deploys
- **Custom domains**, DNS, and certificate provisioning
- **Auto-deploy**, **CI-gated deploys**, and **PR preview** generation
- **Persistent disks** and their impact on scaling and zero-downtime
- **Deploy lifecycle**: build, pre-deploy, swap, drain, **rollback**, shutdown delay

Deeper patterns live under `references/` (health checks, domains, deploy phases).

## Port Binding

- Listen on **`0.0.0.0`** (all interfaces). Binding only to **`localhost`** or **`127.0.0.1`** prevents Render’s proxy from reaching your app.
- Use the **`PORT`** environment variable for the HTTP listen port. Render sets it for you; the **default is often `10000`** and you can change the configured value in the service **Settings** in the Dashboard.
- **Reserved ports** (do **not** bind your application to these for normal traffic): **`18012`**, **`18013`**, **`19099`**.

### Multi-port Web Services

- Only **one** port receives **public** HTTP traffic: the port aligned with **`PORT`**.
- **Additional** open ports are reachable on Render’s **private network** only (not from the public internet through the same public URL pattern).

## TLS and HTTPS

- **TLS terminates at Render’s edge.** The edge speaks HTTPS to clients; your process typically receives **plain HTTP** on `PORT`.
- **HTTPS redirect** for clients is handled by the platform; users hitting HTTP are redirected appropriately at the edge.
- **Do not terminate TLS inside the app** for the primary public listener unless you have a rare, explicit need—standard Web Services assume HTTP behind the proxy.

## Health Checks

- Configure a path via **`healthCheckPath`** in a Blueprint or the **Health Check Path** field in the Dashboard.
- Render issues **HTTP GET** requests to that path. Responses must be **`2xx` or `3xx`** for success.
- **Failed health checks** prevent a new deploy from **going live** (the deploy does not succeed in taking production traffic as expected).
- Render probes on a **repeat interval** with a per-request **timeout**; both are **configurable** in service settings (see Dashboard). Failed checks during rollout prevent the new revision from receiving traffic.
- Check frequency, timeouts, and tuning guidance in `references/health-check-patterns.md`.

## Custom Domains

- Point DNS with a **CNAME** to **`[service-name].onrender.com`** (use your service’s hostname from the Dashboard).
- Render **automatically provisions and renews** TLS certificates for verified domains.
- **Apex** (root) domains need provider-specific **CNAME-like** or flattened records where plain CNAME at `@` is unsupported.
- **Wildcard** domains (e.g. `*.example.com`) are supported when configured and verified.
- Multiple custom domains per service are supported; Blueprints can list them under the **`domains`** field.

See `references/custom-domains.md` for Dashboard steps, verification, and troubleshooting.

## Auto-Deploy and PR Previews

- **`autoDeployTrigger`** (Blueprint) / auto-deploy settings control when production deploys run:
  - **`commit`** — deploy on every push to the tracked branch
  - **`checksPass`** — deploy only when required **Git checks** pass
  - **`off`** — **manual** deploys only (Dashboard, CLI, hooks)
- **PR previews** are configured under Blueprint **`previews.generation`** (and related preview settings); generation behavior depends on repo integration and plan.

## Persistent Disks

- Attach disks via the **`disk`** field in a Blueprint (or equivalent Dashboard storage settings).
- A service with an attached persistent disk is **single-instance** only: **horizontal scaling** is not available in that configuration.
- **Zero-downtime deploys are disabled** when a persistent disk is attached—deploys follow a different rollout pattern.
- **Disk size increases** are allowed; **decreases** are not.
- The disk is **not mounted during the build phase**—only at **runtime** in the running service.

## Deploy Lifecycle

Typical flow:

1. **Build** — clone repo, run **`buildCommand`**, produce the runnable artifact/image.
2. **Pre-deploy command** (optional) — runs in the **new** image **before** traffic switches; use for **migrations**. If it **fails**, the deploy is **canceled**.
3. **Deploy** — new instances start; health checks must pass before traffic moves.
4. **Zero-downtime swap** (when applicable) — traffic shifts to new instances; **old instances drain** in-flight work.

- **`maxShutdownDelaySeconds`** (range **1–300**, **default 30**) bounds how long old instances may continue handling requests during drain before shutdown.
- **Rollbacks** — revert to a **previous successful deploy** from the Dashboard.

Full sequence, hooks, filters, and CLI notes: `references/deploy-lifecycle.md`.

## Free Tier Notes

Free Web Services have **separate limits**: e.g. **no custom domains** on the free instance type, and services **spin down after inactivity** (cold starts on next request). Treat free-tier behavior as distinct from paid Web Service defaults when advising on domains, uptime, and scaling.

## References

| Topic | File |
|--------|------|
| Health check design, timeouts, pitfalls | `references/health-check-patterns.md` |
| Domains, DNS, TLS verification | `references/custom-domains.md` |
| Build, pre-deploy, drain, rollbacks, triggers | `references/deploy-lifecycle.md` |

## Related Skills

- **render-deploy** — Blueprints, first-time deploy, `render.yaml` structure
- **render-docker** — Docker-based Web Services and image/runtime details
- **render-networking** — Private network, internal URLs, multi-port private listeners
- **render-scaling** — Instance counts, plans, and scaling constraints (including disk interactions)
