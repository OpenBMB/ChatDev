# Contact Center 5-Minute Preflight Runbook

Use this before deep debugging. It catches the most common Zoom Contact Center integration failures quickly.

## Skill Doc Standard Note

- Skill entrypoint is `SKILL.md`.
- This runbook is an operational convention (recommended), not a required skill file.
- `SKILL.md` is a navigation convention for larger skill docs.

## 1) Confirm Integration Path

- Contact Center app inside Zoom client: use Zoom Apps SDK APIs/events (`getEngagementContext`, `onEngagementStatusChange`, etc.).
- Website embed: use Contact Center web SDK/campaign script path.
- Native mobile app: use Android/iOS Contact Center SDK binaries and service lifecycle.

Wrong path is the top source of confusion.

## 2) Confirm Required Credentials

- `entryId` for chat/video/ZVA channels.
- `apiKey` for scheduled callback and campaign/web-tag scenarios.
- If building a Contact Center app in Zoom client, validate app credentials and OAuth setup in Marketplace.

## 3) Confirm Lifecycle Order

Common native/mobile order:
1. Initialize SDK context early.
2. Get service instance.
3. Initialize service with `ZoomCCItem`.
4. Register listener/delegate.
5. `login()` where required (typically chat/ZVA).
6. `fetchUI()` to present the channel view.

Web app path:
1. `zoomSdk.config(...)`
2. `getEngagementContext()` and `getEngagementStatus()`
3. subscribe to `onEngagementContextChange` and `onEngagementStatusChange`
4. persist state keyed by `engagementId`

## 4) Confirm Context Switching Behavior

- A single app instance can receive multiple engagement contexts.
- Persist draft/workflow state by `engagementId`.
- Do not assume only one active engagement for chat/SMS/email workflows.

## 5) Confirm Cleanup Semantics

- End action (`endChat`, `endVideo`, `endScheduledCallback`) is not the same as service release.
- Apply platform-specific cleanup (`logout`/`logoff`, release/uninitialize APIs).
- On iOS, forward app lifecycle callbacks (`appDidBecomeActive`, `appWillTerminate`, etc.) to `ZoomCCInterface`.

## 6) Version + Drift Checks

- Zoom enforces minimum SDK versions quarterly (first weekend of February, May, August, November).
- Re-check docs and changelog before release; naming and signatures can drift.
- Watch deprecations:
  - iOS `onService:error:detail:` is deprecated in favor of `onService:error:detail:description:`.

## 7) Quick Probes

- App context/status APIs return valid values.
- Engagement events fire when agent switches engagements.
- Chat/video/scheduled callback can be started and ended once each without stale state.
- No CSP or domain allow-list blocks for web integrations.

## 8) Fast Decision Tree

- No engagement data in Contact Center app -> missing SDK `config` capabilities or wrong runtime context.
- Channel UI does not open -> invalid `entryId`/`apiKey`, missing init, or wrong service/channel mapping.
- Events not firing on switch/end -> listeners not attached early enough or removed incorrectly.
- Rejoin fails on mobile -> deep-link/scheme configuration mismatch.
