# Lifecycle and Events (Web)

## Lifecycle

1. Inject script with API key and env.
2. Wait for `zoomCampaignSdk:ready` or `waitForReady()`.
3. Register event listeners.
4. Execute control calls (`open`, `close`, `show`, `hide`, `endChat`).
5. Optionally refresh user variables via `updateUserContext()`.
6. Remove listeners during page teardown.

## Event Surface

- `open`
- `close`
- `show`
- `hide`
- `engagement_started`
- `engagement_ended`

## Method Surface

- `close()`
- `endChat()`
- `hide()`
- `show()`
- `ChangeCampaign(id, channel?)`
- `updateUserContext()`
- `waitForInit()`
- `waitForReady()`
