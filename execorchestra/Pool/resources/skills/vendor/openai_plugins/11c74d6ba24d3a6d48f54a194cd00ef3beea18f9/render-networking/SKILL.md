---
name: render-networking
description: >-
  Connects Render services over the private network—internal DNS, service
  discovery, and cross-service communication. Use when the user needs to wire
  services together, resolve internal hostnames, troubleshoot connectivity
  between services, configure environment isolation, or understand which
  services can reach each other.
license: MIT
compatibility: Render services in the same region and workspace
metadata:
  author: Render
  version: "1.0.0"
  category: networking
---

# Render private networking

Render’s **private network** lets services talk to each other without exposing traffic on the public internet. Use this skill when users need internal connectivity, discovery across scaled instances, or correct URL/port behavior for Blueprints and the Dashboard.

## When to Use This Skill

- Designing or debugging **service-to-service** traffic on Render
- Questions about **internal hostnames**, **internal URLs**, or **Connect > Internal** in the Dashboard
- **Service discovery** across multiple instances (custom load balancing, mesh-style setups)
- **Port limits**, reserved ports, or **multi-port** web services (public vs private)
- **Free-tier** web services and **who can send vs receive** private traffic
- **Environment isolation** (Professional+) or **AWS PrivateLink** for private egress/ingress patterns

For step-by-step architecture examples and Blueprint patterns, see `references/communication-patterns.md`. For failure modes and fixes, see `references/troubleshooting.md`.

## Private Network Basics

Private connectivity is available only when **all** of the following hold:

- Services are in the **same region**
- Services are in the **same workspace**

If either differs, private DNS and internal routing will not connect those services.

### Who can communicate

| Resource | Private inbound | Private outbound | Internal hostname |
|----------|-----------------|------------------|-------------------|
| **Web Service** | Yes (paid tiers; see Free tier below) | Yes | Yes |
| **Private Service** | Yes | Yes | Yes |
| **Background Worker** | No | Yes | No |
| **Cron Job** | No | Yes | No |
| **Workflow Run** | No | Yes | No |
| **Static Site** | — | — | **Not on private network** |
| **Managed Postgres** | Via internal URL (from allowed clients) | N/A (datastore) | Via internal URL |
| **Key Value** | Via internal URL (from allowed clients) | N/A (datastore) | Via internal URL |

**Free-tier Web Services:** They may **send** private traffic to other services, but they **cannot receive** inbound private traffic. Plan upgrades or topology changes apply if a free web service must accept private connections.

Workers, crons, and workflow runs initiate outbound connections (e.g., to internal URLs or private service hostnames) but are **not** reachable by internal hostname for inbound calls.

## Internal Addresses

- Open the service in the Render Dashboard → **Connect** → **Internal** tab for the canonical internal hostname, URL, and connection details.
- Clients often need an **explicit scheme** in code or config, e.g. `http://service-name:port` or `https://...` when TLS applies—do not assume a bare hostname alone is enough for every HTTP client.
- **URL shape:** `http://[internal-hostname]:[port]/path` (adjust scheme/port per service).

## Service Discovery

For services with **multiple instances**, Render exposes a **discovery DNS** name that resolves to **all instance IPs** for that service. The pattern is **`[hostname]-discovery`** (see Dashboard docs for the exact hostname shown for your service).

- **`RENDER_DISCOVERY_SERVICE`** is set in environments where discovery applies; use it with the discovery hostname pattern for scripts and app code that need instance lists.
- **Use case:** Custom load balancing, health aggregation, or any logic that must fan out or pick among instances explicitly instead of a single internal hostname.

See `references/communication-patterns.md` for discovery-oriented patterns.

## Port Rules

- **Maximum 75 open ports** per service.
- **Reserved ports** (do not bind your app to these for normal use): **10000** (public HTTP proxy path), **18012**, **18013**, **19099**.
- **Multi-port Web Services:** Only **one** port receives **public** HTTP traffic; that port must align with the **`PORT`** environment variable. **Additional** ports are for **private network** access only.

When something fails to connect, verify the target is listening on the expected port and that the port is not reserved or blocked by misconfiguration.

## Environment Isolation

On **Professional and higher** workspaces, you can configure **per-environment** rules so private traffic does **not** cross certain environment boundaries. If private calls work in one environment but not another, check workspace **environment isolation** settings before assuming DNS or app bugs.

## AWS PrivateLink

**Professional+** workspaces can use **AWS PrivateLink** to extend private connectivity to or from external AWS VPCs and approved endpoints. This is separate from default service-to-service private DNS; use it when the architecture requires **private** access to Render or from Render to specific AWS resources without the public internet.

## Common Patterns

Short summaries; full diagrams and Blueprint notes live in `references/communication-patterns.md`.

1. **Web gateway + private backends** — Public Web Service terminates HTTP; internal calls use private hostnames and ports to Private Services or internal URLs.
2. **Worker to database** — Background Worker (no internal hostname) connects **outbound** to Postgres or Key Value **internal URLs**.
3. **Microservices** — Private Services (and eligible Web Services) call each other by **internal hostname:port** on the private network.

## References

| Document | Purpose |
|----------|---------|
| `references/communication-patterns.md` | Gateway, worker→DB, mesh, URL construction, Blueprint `fromService`, discovery load balancing, private health checks |
| `references/troubleshooting.md` | DNS, ports, region/workspace, free tier, protocol, resolver, environment isolation |

## Related Skills

- **render-web-services** — Public web services, `PORT`, and HTTP behavior
- **render-private-services** (planned) — Private Service–specific setup and scaling
- **render-blueprints** — `render.yaml`, `fromService`, and multi-service wiring
