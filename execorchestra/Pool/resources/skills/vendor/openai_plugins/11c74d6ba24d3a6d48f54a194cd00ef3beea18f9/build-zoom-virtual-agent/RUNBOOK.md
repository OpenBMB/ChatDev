# Virtual Agent 5-Minute Runbook

## 1. Credentials and Product Access

- Confirm Virtual Agent license is active.
- Confirm campaign or entry ID exists and is published.
- Confirm API key and environment (`us01` or `eu01`) are correct.

## 2. Browser or WebView Readiness

- Verify CSP allows Zoom SDK script, websocket, media, and wasm execution.
- Verify no blocker/proxy is stripping `zcc-sdk.js`.
- For WebView, verify JavaScript is enabled.

## 3. Lifecycle Order

- Load SDK script.
- Wait for `zoomCampaignSdk:ready` or `waitForReady()`.
- Register event handlers.
- Call `open()` / `show()` only after readiness.

## 4. Native Bridge (Android/iOS)

- Inject `window.zoomCampaignSdk.native` on readiness.
- Wire `exitHandler`, `commonHandler`, and `support_handoff` callbacks.
- Verify URL policy (`target="_blank"`, `window.open`) is implemented.

## 5. Drift Check

- Validate docs naming (`Virtual Agent`) vs sample naming (`Virtual Assistant` / `LiveSDK`).
- Treat `openURL` command path as legacy/deprecated and prefer DOM links or `window.open`.
