# Architecture and Lifecycle

## Architecture

```text
Web or Mobile Host App
  -> Zoom Campaign SDK (zcc-sdk.js)
  -> Campaign or Entry routing
  -> Bot conversation state
  -> Optional native bridge (Android/iOS)
  -> Optional backend automation (OAuth + REST KB APIs)
```

## Lifecycle

1. Provision bot flow and campaign/entry configuration.
2. Embed SDK snippet and provide runtime config (`apikey`, `env`, user context).
3. Wait for readiness, then register event callbacks.
4. Start or show engagement (`open`, `show`).
5. React to events (`open`, `close`, `engagement_started`, `engagement_ended`).
6. For mobile wrappers, forward bridge events (`support_handoff`, exit, URL commands).
7. End session (`endChat`) and detach handlers.

## Version Drift Notes

- Documentation now uses "Virtual Agent" naming.
- Official sample repositories still contain older naming (`virtual-assistant`, `liveSDK`) that can mislead search and code mapping.
