# Web Reference Map

Primary docs:
- https://developers.zoom.us/docs/contact-center/web/get-started/
- https://developers.zoom.us/docs/contact-center/web/chat/
- https://developers.zoom.us/docs/contact-center/web/video/
- https://developers.zoom.us/docs/contact-center/web/campaigns/
- https://developers.zoom.us/docs/contact-center/web/sdk-reference/
- https://developers.zoom.us/docs/contact-center/smart-embed/

## Engagement APIs/Events (Contact Center App)

- `getEngagementContext`
- `getEngagementStatus`
- `onEngagementContextChange`
- `onEngagementStatusChange`
- `onEngagementVariableValueChange`

## Campaign SDK Events

- `open`
- `close`
- `show`
- `hide`
- `engagement_started`
- `engagement_ended`

## Campaign SDK Methods

- `open()`
- `close()`
- `show()`
- `hide()`
- `endChat()`
- `waitForInit()`
- `waitForReady()`
- `updateUserContext()`

## Video Client Events

- `video-start`
- `video-end`
- `notification-join-call`
- `video-click-end`
- `video-force-end`
- `task-created`

## Smart Embed Event Surface

- init/config events (`zcc-init-config-request`, `zcc-init-config-response`)
- engagement and channel events
- contact search request/response patterns
- resize and interaction events
