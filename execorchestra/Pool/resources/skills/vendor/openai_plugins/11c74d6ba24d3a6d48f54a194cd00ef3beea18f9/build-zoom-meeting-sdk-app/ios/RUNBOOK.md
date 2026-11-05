# Meeting SDK iOS 5-Minute Preflight Runbook

Use this before deep debugging.

## Skill Doc Standard Note

- Skill entrypoint is `SKILL.md`.
- This runbook is an operational convention (recommended), not a required skill file.
- SDK/API names can drift by version; validate current names against docs/raw-docs before release.

## 1) Confirm Integration Surface

- Confirm this is a Meeting SDK embed path for iOS (not REST `join_url` only).
- Choose default/full UI first, then move to custom UI after stable join/start.
- Wrapper platforms (Web/React Native/Electron) require extra runtime and bridge checks.

## 2) Confirm Required Credentials

- Meeting SDK app credentials (Client ID/Secret).
- Backend-generated Meeting SDK signature/JWT.
- Meeting identifiers (`meetingNumber`, password) and ZAK for host start flows when needed.

## 3) Confirm Lifecycle Order

1. Initialize SDK and register event handlers.
2. Authenticate SDK session/token.
3. Join or start meeting/webinar with role-appropriate credentials.
4. Handle in-meeting events and network/media state updates.

## 4) Confirm Event/State Handling

- Correlate meeting/session state changes with participant identity and role.
- Handle reconnect/waiting-room transitions explicitly.
- Keep callback/promise/event handlers idempotent to avoid duplicate actions.

## 5) Confirm Cleanup + Upgrade Posture

- Leave meeting and release SDK resources cleanly.
- Remove listeners/subscriptions during component/app teardown.
- Re-check quarterly version enforcement windows before release updates.

## 6) Quick Probes

- Init/auth succeeds before join/start attempt.
- Join/start flow completes once on target platform without stale state.
- Core media controls (audio/video/share) respond to expected events.

## 7) Fast Decision Tree

- 401/signature errors -> backend signature claims/time skew/app credentials mismatch.
- UI loads but cannot join -> wrong role/ZAK/password field or invalid meeting data.
- Random event behavior -> listeners attached multiple times or detached too early.

## 8) Source Checkpoints

### Official docs

- https://developers.zoom.us/docs/meeting-sdk/ios/
- https://marketplacefront.zoom.us/sdk/meeting/ios/annotated.html

### Raw docs in repo

- `raw-docs/developers.zoom.us/docs/meeting-sdk/ios/`
- `raw-docs/marketplacefront.zoom.us/sdk/meeting-sdk/ios/`
