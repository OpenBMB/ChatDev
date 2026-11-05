# Video SDK Linux 5-Minute Preflight Runbook

Use this before deep debugging.

## Skill Doc Standard Note

- Skill entrypoint is `SKILL.md`.
- This runbook is an operational convention (recommended), not a required skill file.
- SDK/API names can drift by version; validate current names against docs/raw-docs before release.

## 1) Confirm Integration Surface

- Confirm this is a Video SDK custom session flow for Linux (not Meeting SDK).
- Verify UI/state are driven by session events, not meeting semantics.
- Wrapper platforms require JS/native bridge synchronization checks.

## 2) Confirm Required Credentials

- Video SDK app credentials (SDK Key/Secret) stored server-side.
- Backend-generated session JWT token.
- Session fields (`sessionName`, `userName`, role type) resolved before join.

## 3) Confirm Lifecycle Order

1. Initialize SDK client/context and register event listeners.
2. Generate/fetch session token from backend.
3. Join session and establish media streams.
4. Handle participant/media/control events during active session.

## 4) Confirm Event/State Handling

- Keep participant state keyed by user/session IDs.
- Reconcile subscribe/unsubscribe transitions for video/audio/share streams.
- Treat reconnect and device-change events as first-class state transitions.

## 5) Confirm Cleanup + Upgrade Posture

- Leave/end session and release helper/client resources.
- Remove listeners to avoid duplicate callbacks on rejoin.
- Re-check SDK version compatibility before deployment updates.

## 6) Quick Probes

- Token issuance and join flow succeed once end-to-end.
- Audio/video publish-subscribe operations complete with expected callbacks.
- Leave/rejoin works without leaked listener or stream state.

## 7) Fast Decision Tree

- Join fails immediately -> invalid/expired token or session field mismatch.
- Media state stuck -> listener binding/order issue or permission/device problem.
- Inconsistent behavior after update -> wrapper/native SDK version mismatch.

## 8) Source Checkpoints

### Official docs

- https://developers.zoom.us/docs/video-sdk/linux/
- https://marketplacefront.zoom.us/sdk/custom/linux/

### Raw docs in repo

- `raw-docs/developers.zoom.us/docs/video-sdk/linux/`
- `raw-docs/marketplacefront.zoom.us/sdk/video-sdk/linux/`
