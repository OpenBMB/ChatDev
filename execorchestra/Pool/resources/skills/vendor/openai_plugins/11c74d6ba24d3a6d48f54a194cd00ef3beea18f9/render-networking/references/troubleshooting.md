# Private network troubleshooting

Common issues when private connectivity fails or behaves unexpectedly on Render.

## DNS resolution failures

- Confirm both services are in the **same region** and **same workspace**. Private DNS is scoped to that combination.
- Verify the **target service is running** (deploy succeeded, process up). Stopped or failed deploys will not resolve usefully for callers.
- Use the **system resolver** (see below); do not rely on ad-hoc HTTP “DNS” APIs for internal names.

## Port conflicts and limits

- **Reserved ports:** **10000**, **18012**, **18013**, **19099** — do not use these for your application’s primary listener.
- **75-port maximum** per service; trim listeners or consolidate if you hit the cap.
- **Multi-port Web Services:** Only the **`PORT`** port receives **public** HTTP; other open ports are **private-only**. Callers using the wrong port or expecting public routing on an extra port will fail or time out.

## Cross-region

Services in **different regions** **cannot** communicate over Render’s private network. Use public endpoints, data replication, or redesign placement so peers share a region.

## Cross-workspace

Services in **different workspaces** **cannot** communicate privately, even if regions match. Merge into one workspace or use an allowed public/integration path.

## Protocol mismatches

- Some HTTP clients require an explicit **`http://`** or **`https://`** prefix for internal URLs; a bare hostname may not construct a valid request URL.
- Mismatching **TLS** expectations (HTTPS client to HTTP server or vice versa) produces connection errors that look like “network” failures.

## Free-tier limitations

**Free Web Services** can **send** private traffic but **cannot receive** inbound private connections. If a Private Service or another Web Service cannot reach a free-tier web target privately, upgrade the target or expose traffic via a different topology (e.g., public API with auth).

## Workers, crons, and workflows “unreachable”

**Background Workers**, **Cron Jobs**, and **Workflow Runs** have **no internal hostname**. They **cannot** accept inbound private connections. Only **outbound** calls from them are valid; do not point other services at a “worker internal URL.”

## DNS resolver

- Use the **system DNS** configured in the runtime (e.g., behavior consistent with **`/etc/resolv.conf`** in Linux containers).
- Avoid replacing resolution with custom HTTP-based lookups for internal Render names; that bypasses the platform’s private DNS chain.

## Environment isolation (Professional+)

If private traffic **suddenly fails** between services that used to work, check whether **per-environment isolation** was enabled or tightened. Isolation can **block cross-environment** private traffic even when region and workspace match at the workspace level.

## Static sites

**Static Sites are not on the private network.** They cannot call or be called via internal hostnames. Use a Web Service or edge-appropriate public API for integration.
