---
name: render-env-vars
description: >-
  Configures environment variables, secrets, and env groups on Render. Use when
  the user needs to set env vars, wire secrets between services, create env
  groups, use generateValue, set sync: false, or troubleshoot missing or
  incorrect environment variable values in Blueprints or the Dashboard.
license: MIT
compatibility: Render Dashboard, CLI, or MCP tools
metadata:
  author: Render
  version: "1.0.0"
  category: configuration
---

# Environment Variables on Render

Render exposes configuration to services as **environment variables**. Values are always **strings** at the platform layer—applications must parse numbers, booleans, and structured data explicitly.

There are **three** primary ways to set variables:

1. **Render Dashboard** — per-service UI, bulk import from `.env`, save/redeploy options
2. **Blueprint** — `envVars` (and related keys) in `render.yaml`
3. **MCP / API** — e.g. `update_environment_variables` on a service

Deep wiring patterns, full platform variable tables, and language-specific notes live under `references/`.

## When to Use This Skill

Use this skill when users want to:

- Add, change, or remove environment variables or secrets
- Understand Dashboard vs Blueprint vs API/MCP flows
- Use **environment groups** for shared configuration
- Wire `fromDatabase`, `fromService`, `fromGroup`, `sync: false`, or `generateValue` in Blueprints
- Debug missing vars, secret files, precedence, or platform-injected names

For full Blueprint authoring, pair with **render-blueprints**. For first-time deploys, **render-deploy**. For web service behavior and ports, **render-web-services**.

## Setting Variables

### Dashboard

- Add variables **individually** (name + value) or **in bulk** by pasting/uploading a `.env`-style file.
- **Save options** typically include:
  - **Save and rebuild & deploy** — picks up build-time changes
  - **Deploy only** — runtime change without a full rebuild (when applicable)
  - **Save only** — persist without triggering a deploy

Use Dashboard edits when iterating quickly or when the repo should not carry certain values.

### Blueprint (`render.yaml`)

Declare `envVars` on each service. Values can be literals, generated secrets, sync-disabled prompts, or references to databases, other services, or env groups. See **Blueprint Wiring** below and `references/wiring-reference.md` for exhaustive patterns and YAML.

### MCP / API

Automation tools can set variables on existing services (e.g. `update_environment_variables`). Useful for CI, rotation, or keeping Dashboard state in sync with external secret stores—without committing secrets to Git.

## Secret Management

- **`sync: false`** — Render prompts in the Dashboard for the value **only on initial Blueprint setup** when the resource is first created. On **Blueprint updates**, `sync: false` is **ignored** (values are not re-prompted from the file alone). These vars are **excluded from preview environments** and are **invalid inside environment groups**.
- **`generateValue: true`** — Render generates a **base64-encoded 256-bit** random value at provision time. Use for passwords, signing keys, or tokens that do not need human-chosen values.
- **Never commit real secrets** in `render.yaml` as plain `value:` entries. Prefer Dashboard, secret manager integration, `generateValue`, or `sync: false` with Dashboard entry.

### Secret files

- Store sensitive file content as **secret files** (not inline env strings). They appear as **plaintext files** under **`/etc/secrets/<filename>`**.
- **Combined limit**: **1 MB** total secret file payload per service or per linked env group (as applicable to your setup).
- **Docker**: secret files are available under **`/etc/secrets/`** on the running instance.

## Environment Groups

**Environment groups** are named collections of variables linked to **multiple services**.

- **Precedence**: **Service-level** variables **override** variables from linked groups with the same name.
- **Multiple groups** on one service: the group that was **most recently created** wins for overlapping keys. This ordering is **not documented as stable**—avoid relying on it; use distinct names or consolidate groups.
- Groups can be **scoped to a project environment** so staging and production differ without duplicating every service definition.

## Blueprint Wiring (Summary)

Full syntax, examples, and edge cases: `references/wiring-reference.md`. Authoritative Blueprint docs: **render-blueprints** skill.

| Mechanism | Role |
|-----------|------|
| `value` | Hardcoded string (non-secret config only) |
| `generateValue: true` | Platform-generated secret |
| `sync: false` | Dashboard prompt on **initial** create only |
| `fromDatabase` | Inject DB fields (`connectionString`, `host`, `port`, `user`, `password`, `database`) |
| `fromService` | Key Value: `type: keyvalue` + properties; private/web: `host`, `hostport`, or `envVarKey` |
| `fromGroup` | Link all vars from a named group |

## Platform-Injected Variables

Render sets **read-only** variables your app can read at runtime (and some at build). A concise list:

| Variable | Typical meaning |
|----------|-----------------|
| `RENDER` | `"true"` when running on Render |
| `RENDER_SERVICE_TYPE` | Service kind (e.g. web, worker) |
| `RENDER_SERVICE_ID` | Service identifier |
| `RENDER_SERVICE_NAME` | Human-readable service name |
| `RENDER_INSTANCE_ID` | Current instance |
| `RENDER_EXTERNAL_URL` | Public URL (when applicable) |
| `RENDER_EXTERNAL_HOSTNAME` | Public hostname |
| `RENDER_DISCOVERY_SERVICE` | Service discovery hostname (private network) |
| `RENDER_GIT_COMMIT` | Deployed commit SHA |
| `RENDER_GIT_BRANCH` | Branch for this deploy |
| `PORT` | HTTP port to bind (**default `10000`**) |
| `IS_PULL_REQUEST` | Preview deploy indicator |
| `RENDER_CPU_COUNT` | vCPU count for the instance |
| `RENDER_WEB_CONCURRENCY` | Suggested worker/process count hint |

Build vs runtime availability, language version env vars, and **WEB_CONCURRENCY** defaults: `references/platform-variables.md`.

## Runtime-Specific Defaults

Render and buildpacks may set defaults (verify in your service’s **Environment** tab):

| Runtime | Notable defaults |
|---------|------------------|
| **Node.js** | `NODE_ENV=production` |
| **Python** | `PYTHON_VERSION` (pinned by build); Gunicorn-oriented images often set `GUNICORN_CMD_ARGS` to bind **`0.0.0.0:10000`** |
| **Ruby** | `RAILS_ENV=production`, `RAILS_LOG_TO_STDOUT=true` |
| **Go** | `GO111MODULE=on` (legacy modules flag; still seen on older stacks) |
| **Rust** | `ROCKET_PORT=10000` (Rocket convention) |

Always bind HTTP servers to **`0.0.0.0`** and **`PORT`** (or the stack’s documented port env) unless using a static site or custom Docker entrypoint.

## Common Issues

1. **Everything is a string** — `DEBUG=false` is truthy in many parsers; use explicit comparison or typed config loaders.
2. **`WEB_CONCURRENCY`** — Default behavior changed for services **created after December 8, 2025**. Compare with older services when debugging worker counts; see `references/platform-variables.md`.
3. **Undocumented `RENDER_*` variables** — Names and semantics may change; do not depend on undocumented injection for critical logic.
4. **Blueprint vs Dashboard drift** — Editing only `render.yaml` does not retroactively apply `sync: false` prompts on update; merge strategy for env keys is easy to misunderstand—test in a scratch service.
5. **Secret file paths** — Code must read **`/etc/secrets/<filename>`**; wrong paths or missing mounts usually show as file-not-found at runtime.

## References

- `references/wiring-reference.md` — Complete Blueprint `envVar` wiring, YAML examples, precedence, edge cases
- `references/platform-variables.md` — Injected variables (build vs runtime), language versions, concurrency, reading vars from code

## Related Skills

- **render-blueprints** — Full Blueprint authoring, validation, multi-service layouts
- **render-deploy** — First deploy, repo requirements, MCP vs YAML
- **render-web-services** — Ports, health checks, scaling behavior tied to env-driven servers
