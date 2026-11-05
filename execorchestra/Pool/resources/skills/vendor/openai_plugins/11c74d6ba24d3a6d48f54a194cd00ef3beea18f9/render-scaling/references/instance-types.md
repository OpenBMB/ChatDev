# Instance types on Render

Approximate **plan** specs for Web Services, Private Services, and Background Workers. **Prices change**—verify at [Render pricing](https://render.com/pricing).

## Plan and spec table

| Plan | CPU | RAM | Monthly Base |
|------|-----|-----|--------------|
| free | Shared | 512 MB | $0 |
| starter | Shared | 512 MB | $7 |
| starter_plus | 1 | 1 GB | $13 |
| standard | 1 | 2 GB | $25 |
| standard_plus | 2 | 4 GB | $50 |
| pro | 4 | 8 GB | $95 |
| pro_plus | 8 | 16 GB | $175 |
| pro_max | 16 | 32 GB | $350 |
| pro_ultra | 32 | 64 GB | $700 |

> **Note:** Monthly figures are **approximate** and may not match your invoice (usage, proration, and promotions differ). Always use [render.com/pricing](https://render.com/pricing) for authoritative rates.

## Flexible vs non-flexible plans

Some plans are **flexible** (usable in mixed configurations such as **preview environments** alongside other instance types where the platform allows it); others are **non-flexible**. Exact flexible-plan rules depend on workspace and product updates—confirm in the Dashboard or docs when mixing preview and production instance types.

## When to scale up vs out

- **Scale up** (larger **plan**): **Memory-intensive** apps, **single-process** or **single-threaded** architectures, workloads that need **more CPU per request** or **larger heap** without sharding.
- **Scale out** (more **instances**): **Stateless** request handlers, **high concurrency**, **even load distribution** across identical processes.
- **Both**: Start with a **right-sized plan**, then add **horizontal** scaling as traffic grows. Avoid tiny instances multiplied many times if each process needs substantial RAM.

## Free tier limitations

- **Single instance** for the service.
- Web services **spin down after inactivity** (cold starts on the next request).
- **Limited** CPU and memory vs paid plans—treat free-tier behavior as distinct when advising on performance and scaling.
