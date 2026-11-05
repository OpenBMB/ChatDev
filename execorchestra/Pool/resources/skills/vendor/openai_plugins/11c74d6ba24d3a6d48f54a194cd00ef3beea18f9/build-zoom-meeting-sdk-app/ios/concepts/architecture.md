# iOS Architecture

## Layer Model

- UIKit/SwiftUI app layer.
- Meeting orchestration layer (state machine + delegate fan-out).
- SDK adapter layer (MobileRTC service wrappers).
- Backend signature/token service.

## Reference Flow

```text
iOS UI -> Meeting Coordinator -> Backend Sign Service -> Meeting SDK
   ^            |                        |                  |
   |            v                        v                  v
User intents  Local state store     Role/token policy   SDK delegates/events
```

## Why this split

- Keeps security-critical logic server-side.
- Stabilizes delegate/event ordering.
- Makes upgrade drift easier to isolate.
