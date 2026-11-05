---
title: "Forum-Derived Top Questions (Meeting SDK)"
---

# Forum-Derived Top Questions (Meeting SDK)

Use this as a high-signal checklist of what developers repeatedly ask about the **Zoom Meeting SDK** (Web, Mobile, Desktop, Linux).

## Fast Routing Questions (Ask First)

- Platform: **Web** vs **Android/iOS** vs **Windows/macOS** vs **Linux headless**
- Web integration: **Client View (CDN + `ZoomMtg`)** vs **Component View (npm + `ZoomMtgEmbedded`)**
- Join type: **join** as participant vs **start** as host
- Auth inputs you have: `sdkKey`, `sdkSecret` (server only), `meetingNumber`, `role`, `zak` (if starting as host), `passcode`
- Exact error: full error code/message + SDK version

## Signatures (Most Common Root Cause)

- **Generate signature server-side only** (never expose SDK Secret in browser/mobile client code).
- Use the right payload fields:
  - `sdkKey`, `mn` (meeting number), `role`, `iat`, `exp`, `tokenExp`
- Typical mistakes:
  - Wrong meeting number format (non-digits; strip formatting)
  - `exp` too long/short, or client/server clock skew
  - Mixing Meeting SDK signature with REST API OAuth/JWT app-type tokens (different things)

## Web SDK: Client View vs Component View Confusion

- **Client View (CDN)** uses `ZoomMtg.*` callback style.
- **Component View (npm)** uses `ZoomMtgEmbedded.createClient()` with promise-based APIs.
- When a question is about “hide UI”, “toolbar”, “meeting info”, first confirm which view they are using:
  - Some UI changes are only possible in **one** of the views, or not supported at all.

## “Hide Meeting Password / Invite URL / Meeting Info”

Common ask: “How do I hide passcode / meeting info / invite URL in Meeting SDK?”

What to cover in answers:
- What’s supported by the SDK (official flags/APIs) vs what is not.
- If the goal is “don’t leak passcode”, the most reliable approach is usually:
  - Use meeting settings that reduce exposure (and avoid displaying it in your own UI)
  - Don’t log it client-side
  - Don’t render invite UI if you control that surface (Component View)

## Join Failures and Timeouts (Web)

Common asks:
- “Join meeting failed”
- “Joining meeting timeout”
- “Browser doesn’t support gallery view”

Checklist:
- Confirm `crossOriginIsolated` / SharedArrayBuffer requirements (if using features that need it)
- Confirm HTTPS + correct COOP/COEP headers (when required)
- Confirm ad blockers / CSP / corporate proxies aren’t blocking Zoom assets
- Confirm correct `passWord` casing (Web Client View uses `passWord`)

## Captions / Transcript UI

Common asks:
- Enabling captions
- Hiding captions but transcript still shows

Answer pattern:
- Separate “what the host/account policy controls” from “what SDK UI controls”
- Call out constraints: some transcript/caption behaviors are server-side policy and not fully suppressible from SDK UI alone

## Waiting Room and Admission Flow

Common asks:
- Enabling/disabling waiting room
- Notifications and UI behavior

Answer pattern:
- Distinguish Meeting settings (host/account) vs SDK client behavior
- If the goal is “auto-admit” or “control admission”, you likely need the host controls (and sometimes REST API) rather than just SDK UI changes

## Raw Data / Raw Recording

Common asks:
- Start raw recording fails (permissions)
- Raw data availability varies by platform

Answer pattern:
- Always ask platform + SDK variant and whether they’re using supported raw-data APIs for that platform
- If it’s permission-related:
  - confirm required entitlements/features
  - confirm app permissions / OS permissions

## Performance: “Save CPU”, Gallery View, Low-End Devices

Common asks:
- Gallery view availability
- High CPU usage

Checklist:
- Reduce subscribed video streams / lower quality where supported
- Ensure you’re not rendering unnecessary DOM/video elements (Component View)
- Confirm the device/browser constraints (some behavior is expected)
