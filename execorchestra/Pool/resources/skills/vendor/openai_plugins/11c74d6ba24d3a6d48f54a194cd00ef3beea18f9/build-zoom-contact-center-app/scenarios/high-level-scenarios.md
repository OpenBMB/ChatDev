# High-Level Scenarios

## 1. Agent Notes App in Contact Center

Goal:
- Agent writes notes that follow engagement context switching.

Flow:
1. `config` Zoom Apps SDK with engagement capabilities.
2. Load `getEngagementContext` + `getEngagementStatus`.
3. Store notes by `engagementId`.
4. On `onEngagementContextChange`, swap UI state to selected engagement.
5. On `onEngagementStatusChange` `end`, finalize or clear engagement draft.

## 2. Web Chat Campaign Launch

Goal:
- Product team controls targeting in admin without code redeploy.

Flow:
1. Add campaign web tag script.
2. Wait for `zoomCampaignSdk:ready`.
3. Programmatically `open/show/hide/close` as needed.
4. Listen for engagement events for analytics and CRM writes.

## 3. Mobile Chat and Video with Native SDK

Goal:
- Customer mobile app can launch chat/video and recover from interruptions.

Flow:
1. Initialize SDK context in app startup.
2. Build `ZoomCCItem` for channel.
3. Initialize service, attach delegates/listeners, and launch UI.
4. Handle disconnect/rejoin links for video.
5. End flow and release service resources.

## 4. Campaign-Mode Channel Router

Goal:
- Runtime selection of chat/video/ZVA/scheduled callback per campaign.

Flow:
1. Fetch campaigns by API key.
2. Inspect campaign channels.
3. Build channel-specific item with campaign mode.
4. Release previous conflicting service before opening new channel.

## 5. Smart Embed CRM Integration

Goal:
- Embed Contact Center softphone in CRM with screen-pop and contact lookup.

Flow:
1. Load Smart Embed iframe.
2. Handle postMessage events (`zcc-init-config-request`, search, resize, engagement events).
3. Return contact search results and route screen-pop in CRM.
4. Keep feature flags aligned with Smart Embed version path.
