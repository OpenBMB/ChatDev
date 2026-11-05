# Autoscaling configuration guide

Autoscaling on Render applies to **Web Services**, **Private Services**, and **Background Workers** on **Professional+** workspaces. It adjusts instance count between **min** and **max** based on **CPU** and/or **memory** utilization targets.

## Enabling autoscaling

- **Dashboard:** open the service → **Scaling** → **Autoscaling**, then set min/max and targets.
- **Blueprint:** add a top-level **`scaling`** object on the service (see example below).

At least **one** of **CPU** or **memory** targeting must be enabled. If both are disabled, autoscaling is off.

## Choosing targets

- **CPU target** — Best for **compute-bound** services. A common starting point is **~70%**; raise or lower after observing real traffic and latency.
- **Memory target** — Best for **memory-bound** services. A common starting point is **~80%**; adjust if you see OOM risk or wasted RAM.
- **Both CPU and memory** — **Recommended** for many production services. Render computes scale for each metric and applies the **larger** instance count (more aggressive scale-out).

## Min and max instances

- **minInstances** — Baseline capacity. Use **at least 1**; use **2+** when you want capacity during scale events or rolling behavior (subject to plan and service type).
- **maxInstances** — **Cost ceiling** and upper bound. The platform still enforces an **absolute maximum of 100** instances per service.

## Monitoring

- Watch **scaling events** and instance count in the **Dashboard**.
- Correlate with **CPU/memory** charts (and logs) to see if targets are too loose (high cost) or too tight (latency, errors).

## Blueprint example

```yaml
scaling:
  minInstances: 2
  maxInstances: 10
  targetCPUPercent: 70
  targetMemoryPercent: 80
```

Omit a target field or disable that metric in the Dashboard if you only want one signal (e.g. memory-only for a cache-heavy worker).

## Common mistakes

| Mistake | Effect |
|---------|--------|
| **CPU and memory targets too low** | **Over-provisioning**, higher cost than necessary |
| **Targets too high** | **Under-provisioning**, slow responses or instability |
| **No practical max** (max too high vs traffic) | Risk of **many instances** during attacks or bugs—**100** is still the hard cap |
| **Autoscaling + persistent disk** | **Not allowed**—disk-attached services stay **single-instance** |
| **`numInstances` alongside `scaling`** | **Autoscaling wins**; manual count does not override the policy |

## Preview environments

- **Autoscaling is disabled** in preview environments.
- Preview instances typically follow **`minInstances`** (or equivalent preview defaults) rather than dynamic scaling—do not assume preview behavior matches production autoscaling.
