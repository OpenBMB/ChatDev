# Web Common Issues

## `window.zoomCampaignSdk` Is Undefined

- Confirm script URL is reachable and not blocked.
- Confirm initialization completed before method calls.

## CSP Blocks SDK

- Add CSP directives for script/connect/media/font/image paths required by Zoom SDK.
- Re-test with browser console open for wasm or websocket policy errors.

## Campaign Not Triggering

- Validate campaign targeting rules and page conditions.
- Inspect network calls and config/style responses.

## Third-Party Link Behavior

- Avoid fragile `defer` script behavior when startup triggers external links.
- Prefer explicit handling for `target="_blank"` and `window.open` flows.
