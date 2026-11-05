# Lifecycle Workflow

Recommended runtime flow:

1. App bootstraps and wraps tree with `ZoomSDKProvider`.
2. `initSDK` runs once with `jwtToken`, `domain`, logging options.
3. App checks `isInitialized()` before meeting actions.
4. User chooses:
   - `joinMeeting` (participant)
   - `startMeeting` (host, with ZAK)
5. Native Meeting SDK UI/session runs.
6. Call `cleanup()` on app shutdown/logout.

```text
React UI -> ZoomSDKProvider -> JS Wrapper (ZoomSDK.ts)
       -> Native Bridge (RNZoomSDK)
       -> iOS MobileRTC / Android ZoomSDK
```

If initialization/auth fails, stop and rotate token before retrying.
