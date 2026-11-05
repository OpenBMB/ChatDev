# iOS Reference Map

Primary references:
- https://marketplacefront.zoom.us/sdk/contact/ios/index.html
- SDK headers packaged in iOS SDK zip (`ZoomCCInterface.h`)

## Core Types

- `ZoomCCInterface`
- `ZoomCCContext`
- `ZoomCCItem`
- `ZoomCCCampaignInfo`

## Service Protocols

- `ZoomCCService`
- `ZoomCCChatService`
- `ZoomCCVideoService`
- `ZoomCCScheduledCallbackService`

## Delegate Protocols

- `ZoomCCServiceDelegate`
- `ZoomCCChatServiceDelegate`
- `ZoomCCAppLifecyleDelegate`

## Key Methods

- Interface:
- `sharedInstance`
- `chatService`
- `zvaService`
- `videoService`
- `scheduledCallbackService`
- `getCampaigns`
- Service lifecycle:
- `initializeWithItem`
- `login`
- `logout`
- `fetchUI`
- Video:
- `handleRejoinVideoOpenURL:item:videoDelegate:complete:`

## Deprecation Note

- `onService:error:detail:` is deprecated.
- Use `onService:error:detail:description:`.
