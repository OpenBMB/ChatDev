# Render-injected and runtime environment variables

Render injects **platform variables** into builds and/or running services. Treat undocumented names as **unstable**. Always read **`PORT`** for HTTP listeners on native/web services unless your stack documents otherwise.

## Build-time vs runtime

Availability can vary by **service type**, **language**, and **Docker vs native**. When in doubt, print `env` in a one-off shell (Dashboard **Shell**) or log at process start. The table below uses:

- **Build** — available during `buildCommand` / image build steps Render controls
- **Runtime** — available to `startCommand` / container CMD

| Variable | Build | Runtime | Notes |
|----------|:-----:|:-------:|-------|
| `RENDER` | Often | Yes | `"true"` on Render |
| `RENDER_SERVICE_TYPE` | Often | Yes | e.g. `web`, `worker`, `static` |
| `RENDER_SERVICE_ID` | Often | Yes | Stable service UUID |
| `RENDER_SERVICE_NAME` | Often | Yes | Configured service name |
| `RENDER_INSTANCE_ID` | No | Yes | Per-running-instance id |
| `RENDER_EXTERNAL_URL` | Varies | Yes | Public URL when service has one |
| `RENDER_EXTERNAL_HOSTNAME` | Varies | Yes | Public hostname |
| `RENDER_DISCOVERY_SERVICE` | Varies | Yes | Private service discovery hostname |
| `RENDER_GIT_COMMIT` | Yes | Yes | SHA of deployed revision |
| `RENDER_GIT_BRANCH` | Yes | Yes | Branch for this deploy |
| `PORT` | Sometimes | Yes | **Default `10000`**; must bind `0.0.0.0` for inbound HTTP |
| `IS_PULL_REQUEST` | Varies | Yes | Set for preview deploys from PRs |
| `RENDER_CPU_COUNT` | Rare | Yes | vCPUs allocated to the instance |
| `RENDER_WEB_CONCURRENCY` | Rare | Yes | Hint for process/worker count (see below) |
| `NODE_VERSION` | Yes | If set | Native Node builds |
| `PYTHON_VERSION` | Yes | If set | Native Python builds |
| `RUBY_VERSION` | Yes | If set | Native Ruby builds |
| `GO_VERSION` | Yes | If set | Native Go builds |
| `RUST_VERSION` | Yes | If set | Native Rust builds |
| `ELIXIR_VERSION` | Yes | If set | Native Elixir builds |
| `ERLANG_VERSION` | Yes | If set | Often paired with Elixir |

Dockerfile-based services only see variables you set or that the platform injects at the relevant phase; **language version** env vars apply primarily to **Render native** build pipelines.

## `WEB_CONCURRENCY` and `RENDER_WEB_CONCURRENCY`

- Many stacks read **`WEB_CONCURRENCY`** (Gunicorn, Unicorn, Puma integrations, etc.) to choose worker count.
- Render also exposes **`RENDER_WEB_CONCURRENCY`** as a **suggested** concurrency aligned with instance size. Some buildpacks or docs map between them; confirm in your service’s **Environment** tab.
- **Services created after December 8, 2025** use updated **default `WEB_CONCURRENCY`** behavior compared to older services. When debugging “too many/few workers,” compare **service creation date**, explicit **`WEB_CONCURRENCY`** overrides, and **`RENDER_CPU_COUNT`**.

## `RENDER_CPU_COUNT`

- Integer string (e.g. `"2"`) reflecting **allocated vCPUs** for the current instance type.
- Use for auto-tuning worker pools **in addition to** memory limits, not as a substitute for load testing.

## Per-language defaults (implications)

| Language / stack | Common injected or buildpack defaults | Implication |
|------------------|--------------------------------------|-------------|
| **Node.js** | `NODE_ENV=production` | DevDependencies may be omitted; assert logging and error handlers match prod |
| **Python** | `PYTHON_VERSION`, `GUNICORN_CMD_ARGS` → bind `0.0.0.0:10000` | Must match `PORT`; custom ASGI/WSGI commands should also bind `0.0.0.0:$PORT` |
| **Ruby** | `RAILS_ENV=production`, `RAILS_LOG_TO_STDOUT=true` | Logs go to stdout; ensure 12-factor logging |
| **Go** | `GO111MODULE=on` (legacy) | Modern Go may not need it; Dockerfile users set their own |
| **Rust / Rocket** | `ROCKET_PORT=10000` | Align with `PORT` or override consistently |
| **Elixir** | `ELIXIR_VERSION`, `ERLANG_VERSION`, `PORT` | Release must read `PORT` for Phoenix if not using defaults |

## Language version variables

These pin or document the toolchain Render uses for **native** builds:

| Variable | Purpose |
|----------|---------|
| `NODE_VERSION` | Node.js major/minor selection |
| `PYTHON_VERSION` | Python 3.x selection |
| `RUBY_VERSION` | Ruby version |
| `GO_VERSION` | Go toolchain |
| `RUST_VERSION` | Rust toolchain |
| `ELIXIR_VERSION` | Elixir |
| `ERLANG_VERSION` | OTP / Erlang |

Docker builds should encode versions in the **image** or **build args** instead of relying on these.

## Reading environment variables from application code

| Language | API |
|----------|-----|
| **JavaScript / Node.js** | `process.env.MY_VAR` |
| **Python** | `os.environ["MY_VAR"]` or `os.getenv("MY_VAR")` |
| **Ruby** | `ENV["MY_VAR"]` |
| **Go** | `os.Getenv("MY_VAR")` |
| **Elixir** | `System.get_env("MY_VAR")` |

Remember: all values arrive as **strings**. Parse integers with explicit error handling; treat `"false"` and `""` carefully in boolean logic.
