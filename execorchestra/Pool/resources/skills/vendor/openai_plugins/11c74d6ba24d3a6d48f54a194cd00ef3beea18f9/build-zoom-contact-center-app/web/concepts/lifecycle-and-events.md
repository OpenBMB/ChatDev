# Web Lifecycle and Event Model

## Contact Center App Runtime (Zoom Client)

1. Configure SDK capabilities.
2. Read running context.
3. Read engagement context/status.
4. Subscribe to:
- `onEngagementContextChange`
- `onEngagementStatusChange`
- optional variable change events
5. Maintain engagement-scoped state.

## Web Campaign SDK Runtime

1. Load script with API key.
2. Wait for `zoomCampaignSdk:ready`.
3. Call methods:
- `open`
- `close`
- `show`
- `hide`
- `endChat`
4. Subscribe/unsubscribe to SDK events.

## Video Client Runtime

1. Create client.
2. Initialize with entry identifier and optional metadata.
3. Start video.
4. Handle `video-start` and `video-end` events.

## Smart Embed Runtime

1. Load Smart Embed iframe.
2. Listen for `message` events from iframe.
3. Respond to init/search/control requests.
4. Map engagement and contact data to CRM/app entities.

## State Strategy

- Key all session data by `engagementId`.
- Keep event handlers re-entrant and idempotent.
- Treat `end` status as cleanup boundary.
