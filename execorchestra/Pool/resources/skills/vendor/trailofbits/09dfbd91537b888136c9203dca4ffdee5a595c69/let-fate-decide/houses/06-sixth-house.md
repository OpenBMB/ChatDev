# Sixth House

**Domain**: Practice, service, quality, routine, and maintenance

## Core Meaning
The Sixth House describes the work of making systems reliable. It points to
tests, cleanup, repeatable process, health checks, observability, and the small
habits that compound into quality.

## Building New Projects
Use this house to define the development loop: tests, linting, CI, local setup,
error handling, deploy hygiene, and the maintenance burden the team is willing
to carry.

## Vulnerability Discovery
Use this house to inspect routine paths: retries, cleanup, cron jobs, queues,
rate limits, background workers, monitoring gaps, and ordinary code that rarely
gets dramatic attention.

## Correctness Verification
Use this house to focus on regression tests, invariants in common workflows,
fuzz harness stability, determinism, resource cleanup, and operational
repeatability.

## Technical Workflow Lenses
- Audit pipeline: convert discoveries into repeatable checks, regression tests,
  coverage targets, and maintenance tasks.
- Evidence mode: use CI results, sanitizer output, fuzz coverage, mutation
  scores, invariants, logs, and observability data.
- Human context: reduce recurring toil with documented workflows, ownership,
  and boring automation.

## Technical Prompt
What ordinary practice would prevent this system from drifting into failure?
