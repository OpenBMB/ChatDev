# Web Service deploy lifecycle on Render

This document expands on **build → pre-deploy → new instances → health check → traffic switch → drain** for Web Services.

## Build phase

- Render **clones** the repository at the configured **branch/commit**.
- Runs **`buildCommand`** (or the default for the environment).
- Output is a **build artifact** or image used for the **runtime** container.

The **persistent disk** (if any) is **not** available during build—do not assume mounted paths from disks exist in the build environment.

## Pre-deploy command

- Optional **`preDeployCommand`** runs in the **new** image **before** production traffic moves to new instances.
- Typical use: **database migrations**, one-off schema updates, or validation that must pass before serving traffic.
- If the command **exits non-zero** (fails), the **deploy is canceled**; the previous live revision remains serving (subject to product behavior at the time).

## Zero-downtime deploy (when enabled)

For services **without** attached persistent disks (and subject to plan/type rules):

1. **New instances** start from the new build.
2. **Health checks** must pass for the new revision.
3. **Traffic switches** to healthy new instances.
4. **Old instances drain** in-flight requests, then shut down.

With a **persistent disk**, zero-downtime deploys are **disabled**; expect a different rollout (single instance, swap behavior per platform docs).

## Graceful shutdown and `maxShutdownDelaySeconds`

- **`maxShutdownDelaySeconds`** controls how long **old instances** may continue handling requests during drain before shutdown (allowed range **1–300**, **default 30**).
- Tune upward if requests are **long-lived** (large uploads, slow streaming) so clients see fewer hard cuts; tune downward if you need faster replacement (understand tradeoffs).

## Rollback

- From the **Dashboard**, you can **revert** to a **previous successful deploy** when something misbehaves after a release.
- Prefer rollbacks for bad config or failed migrations only after understanding **data** compatibility (migrations may be one-way).

## Auto-deploy triggers

Blueprint / service settings use **`autoDeployTrigger`** (or Dashboard equivalents):

| Value | Behavior |
|--------|----------|
| **`commit`** | Deploy on every push to the **connected branch** |
| **`checksPass`** | Deploy only when required **Git provider checks** pass |
| **`off`** | **Manual** deploys only |

Pair with branch protection and CI so **`checksPass`** matches your org’s quality gates.

## Build filters

- Configure **path filters** so builds run only when certain paths change (reduces noise and build minutes).
- Exact YAML keys depend on your Blueprint version; align with current Render Blueprint docs when generating `render.yaml`.

## Manual deploy

- Trigger from the **Dashboard** (Manual Deploy).
- CLI: **`render deploys create`** (with correct service context and authentication)—useful in scripts and non-Git triggers.

## Deploy hooks

- **Webhook URLs** can **trigger deploys** when called (e.g. from external CI or release systems).
- Secure hooks (secrets, allowlists) and avoid exposing them in public repos.

## PR previews

- Controlled via Blueprint **`previews.generation`** and related settings; previews spin up **ephemeral** service instances for pull requests when enabled and connected to the repo.

## Mental model

```text
push / hook / manual
       ↓
    BUILD (no disk mount)
       ↓
 PRE-DEPLOY (new image; optional)
       ↓
 NEW INSTANCES + HEALTH CHECKS
       ↓
 TRAFFIC SWITCH (if healthy)
       ↓
 OLD INSTANCES DRAIN (maxShutdownDelaySeconds)
```

Use **`healthCheckPath`** and **`PORT`** correctness as the first line of defense when deploys “succeed” in the UI but never take traffic.
