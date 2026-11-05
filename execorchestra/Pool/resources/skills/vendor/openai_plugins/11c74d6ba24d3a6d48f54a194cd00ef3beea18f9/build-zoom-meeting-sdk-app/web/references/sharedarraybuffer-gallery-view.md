---
title: "Web: SharedArrayBuffer and Gallery View"
---

# Web: SharedArrayBuffer and Gallery View

Many Meeting SDK Web issues that mention gallery view or performance are caused by missing cross-origin isolation.

## What to Ask

- Are they using **Client View** (CDN) or **Component View** (npm)?
- Is the app served over **HTTPS**?
- Does the browser report `crossOriginIsolated === true`?

## Symptoms

- “SharedArrayBuffer is not defined”
- “Your browser doesn’t support gallery view”
- performance degradation on certain machines/browsers

## What to Do

1. Serve the app with the required COOP/COEP headers so `crossOriginIsolated` can become true.
2. Avoid embedding the app in contexts that break isolation (some iframes/proxies).
3. If the environment cannot be isolated (enterprise proxy, incompatible embeds), treat gallery view / HD features as best-effort and fall back gracefully.

## Debug Checklist

- In DevTools console:
  - `window.crossOriginIsolated` should be `true` for SAB-dependent features.
- Verify required headers are present on **all** relevant responses (HTML + JS + WASM).
