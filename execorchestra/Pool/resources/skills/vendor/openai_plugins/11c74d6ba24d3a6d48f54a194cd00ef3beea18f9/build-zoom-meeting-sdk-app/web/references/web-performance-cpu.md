---
title: "Web: Performance and CPU (Meeting SDK)"
---

# Web: Performance and CPU (Meeting SDK)

Common “meeting web” questions boil down to resource usage and rendering constraints.

## Clarify the Integration

- Client View vs Component View
- Expected participant count and whether gallery view is required
- Target devices (low-end laptops, thin clients, mobile browsers)

## General Levers

- Prefer realistic expectations: browsers + multi-video rendering are CPU-heavy.
- Avoid extra DOM/layout work around the meeting container.
- Ensure SharedArrayBuffer / cross-origin isolation is configured when required (see `sharedarraybuffer-gallery-view.md`).

## Practical Checks

- Confirm the meeting container is not constantly re-rendering (React state loops around the Zoom root).
- Check for global CSS resets that impact layout and cause expensive reflows.
- On constrained machines, reduce unnecessary UI overlays and avoid heavy background effects.
