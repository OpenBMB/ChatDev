# macOS Architecture

## Layer Model

- App shell (AppKit/Swift UI integration layer).
- Meeting coordinator (join/start state machine).
- SDK service/controller layer (ZoomSDK class + service delegates).
- Backend signing/token service.

## Reference Flow

```text
macOS App -> Meeting Coordinator -> Backend Signature Service -> Meeting SDK
   ^               |                         |                    |
   |               v                         v                    v
User actions   State + retry policy      Role/token policy   Service delegates
```

## Why this split

- Isolates security logic from desktop client.
- Makes controller/delegate ordering explicit.
- Reduces upgrade regression blast radius.
