# SDK Architecture Pattern

Electron wrapper follows a service + controller + event callback model.

## Core layers

- `zoom_sdk` bootstrap/auth wrappers.
- Meeting service facade.
- Feature controllers (audio, video, participants, recording, share, chat, etc.).
- Settings service/controllers.
- Optional modules (raw data, webinar, AI companion, whiteboard, QA/polling).

## Universal pattern

1. Get service/controller.
2. Register event callback(s).
3. Invoke async action.
4. Handle callback result/error codes.

## Implementation guidance

- Centralize callback routing in one internal event bus.
- Use typed wrapper methods per module to reduce invocation mistakes.
- Log SDK return codes consistently for diagnostics.
