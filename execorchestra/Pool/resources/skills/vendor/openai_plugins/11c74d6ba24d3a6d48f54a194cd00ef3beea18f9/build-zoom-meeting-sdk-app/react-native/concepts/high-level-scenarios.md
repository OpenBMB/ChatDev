# High-Level Scenarios

## 1. Mobile attendee app (customer-facing)

- User opens iOS/Android app and joins meetings from in-app schedule.
- Backend provides short-lived Meeting SDK JWT.
- App calls `joinMeeting` with meeting number and passcode when required.

## 2. Mobile host operations app

- Authenticated operator starts scheduled sessions from mobile.
- Backend retrieves host ZAK via Zoom APIs.
- App uses `startMeeting` with `zoomAccessToken`.

## 3. Kiosk-style controlled join flow

- App runs in constrained device mode.
- Meeting controls are reduced via meeting flags/settings.
- App enforces deterministic init -> join -> cleanup sequence on each session.

## 4. Support/field workforce app

- Agents join support calls and optionally use share/chat controls.
- Per-platform settings are tuned independently (Android/iOS parity is not guaranteed).
- Runtime fallback handling is added for unsupported feature flags.
