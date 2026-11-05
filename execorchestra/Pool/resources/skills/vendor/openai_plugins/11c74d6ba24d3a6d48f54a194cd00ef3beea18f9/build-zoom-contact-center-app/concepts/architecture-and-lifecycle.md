# Contact Center Architecture and Lifecycle

This document defines a stable architecture pattern that works across Contact Center app, web, and mobile integrations.

## Architecture Layers

1. Integration Surface
- Zoom Contact Center App (Zoom client embedded webview).
- Web SDK/Campaign SDK on external sites.
- Android/iOS native SDK.

2. Engagement State Layer
- Current `engagementId`.
- Engagement status (`start`, `hold`, `resume`, `end`).
- Engagement-scoped draft data.

3. Channel Service Layer
- Chat.
- Video.
- ZVA.
- Scheduled Callback.

4. Persistence Layer
- Transient per-engagement state cache (frontend local storage or backend session store).
- Optional backend persistence for long-running workflows and compliance logging.

## Canonical Lifecycle

1. Initialize context.
2. Determine active engagement context.
3. Build/init channel service/client.
4. Register callbacks before launching UI.
5. Start channel view.
6. Process status/context events.
7. End and cleanup.

## Context-Switching Contract

- Treat `engagementId` as the primary state key.
- Never assume a single engagement in memory for messaging channels.
- Restore state on each engagement context change.
- Clear or archive engagement state only when end-state logic is complete.

## Event-Driven Contract

- Do not poll as a primary strategy.
- Subscribe early and keep handlers idempotent.
- Handle out-of-order or repeated events safely.

## Campaign Mode Pattern

1. Fetch campaigns with campaign API key.
2. Pick channel from `translatedCampaignChannels`.
3. Create channel item with `useCampaignMode=true`.
4. Launch service UI.
5. Release conflicting channel services when switching channels.

## Security and Identity

- Use explicit user/session identity refresh paths (`authorize`, `getAppContext`) for Contact Center app scenarios.
- For PWA flows, do not depend on `x-zoom-app-context` header.
- Keep OAuth and app context decryption on backend where possible.
