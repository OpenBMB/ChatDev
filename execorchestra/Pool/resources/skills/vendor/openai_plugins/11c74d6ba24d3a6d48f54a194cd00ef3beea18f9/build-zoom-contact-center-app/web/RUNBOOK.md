# Contact Center Web 5-Minute Preflight Runbook

Use this before deep debugging.

## Skill Doc Standard Note

- Skill entrypoint is `SKILL.md`.
- This runbook is an operational convention (recommended), not a required skill file.
- SDK/API names can drift by version; validate current names against docs/raw-docs before release.

## 1) Confirm Integration Surface

- Confirm channel target and integration mode for Web.
- Contact Center app path and web embed path have different lifecycle rules.
- For mobile SDKs, verify native service lifecycle and listener registration order.

## 2) Confirm Required Credentials

- `entryId` for chat/video/ZVA entry points.
- `apiKey` for scheduled callback and campaign/tag use cases.
- If in-client app behavior is needed, verify Zoom App credentials and required scopes.

## 3) Confirm Lifecycle Order

1. Initialize SDK context early.
2. Get channel service and register listeners/delegates before actions.
3. Authenticate/login where required.
4. Start/fetch channel UI and handle engagement status transitions.

## 4) Confirm Event/State Handling

- Track state by `engagementId`; do not assume single engagement forever.
- Handle context-switch events without losing draft/chat workflow state.
- Keep service/channel state isolated per active engagement.

## 5) Confirm Cleanup + Upgrade Posture

- End channel session and release service resources cleanly.
- Forward app lifecycle callbacks for iOS integrations.
- Re-check release notes for renamed/deprecated methods before upgrades.

## 6) Quick Probes

- Engagement context/status APIs return valid values.
- Start/end flow works once end-to-end for target channel.
- Listener callbacks fire on switch/end events without stale state.

## 7) Fast Decision Tree

- UI does not open -> invalid `entryId`/`apiKey` or missing init/listener sequence.
- Events missing -> listener registered too late or detached unexpectedly.
- Rejoin/resume fails -> lifecycle callbacks or deep-link/scheme config mismatch.

## 8) Source Checkpoints

### Official docs

- https://developers.zoom.us/docs/contact-center/web/
- https://developers.zoom.us/docs/contact-center/web/sdk-reference/

### Raw docs in repo

- `raw-docs/developers.zoom.us/docs/contact-center/web/`
