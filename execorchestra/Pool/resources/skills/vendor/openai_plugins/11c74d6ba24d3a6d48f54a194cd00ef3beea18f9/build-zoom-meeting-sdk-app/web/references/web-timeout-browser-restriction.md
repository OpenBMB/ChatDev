---
title: "Web: Joining Meeting Timeout / Browser Restriction"
---

# Web: Joining Meeting Timeout / Browser Restriction

Forum threads often report errors like:

- “Joining meeting timeout”
- “Your network connection has timed out”
- “Your organization has disabled access to Zoom from the browser”

## What to Ask (Quick)

- Browser + OS
- Are they behind a corporate proxy/VPN/firewall?
- Does the issue reproduce on a clean network (mobile hotspot)?
- Are any ad blockers/privacy tools enabled?
- Client View (CDN `ZoomMtg`) vs Component View (npm `ZoomMtgEmbedded`)

## Common Root Causes

- Network blocks: WebSocket / media / Zoom domains blocked by org policy
- CSP/proxy rewriting that breaks SDK resources
- Mixed content / non-HTTPS in dev environments

## Practical Debug Steps

1. Try from a different network (hotspot) to isolate policy blocks quickly.
2. Disable ad blockers/privacy extensions for the site.
3. Verify the page and SDK assets load without 4xx/5xx in DevTools Network tab.
4. If in enterprise environment: ask for the organization’s allowlist policy for Zoom web traffic.
