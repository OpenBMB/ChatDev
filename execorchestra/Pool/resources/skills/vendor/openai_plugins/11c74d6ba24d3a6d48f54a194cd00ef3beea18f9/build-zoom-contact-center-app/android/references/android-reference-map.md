# Android Reference Map

Primary reference:
- https://marketplacefront.zoom.us/sdk/contact/android/index.html

## Core Types

- `ZoomCCInterface`
- `ZoomCCItem`
- `ZoomCCContext`
- `ZoomCCService`
- `ZoomCCChatService`
- `ZoomCCVideoService`
- `ZoomCCScheduledCallbackService`

## Listener Types

- `ZoomCCServiceListener`
- `ZoomCCChatListener`
- `ZoomCCVideoListener`

## Enums

- `ZoomCCIInterfaceType`
- `ClientEvent`
- `IMStatus`
- `CCServerType`
- `VideoPreviewOption`

## Common Methods

- SDK init/context:
- `ZoomCCInterface.init(...)`
- `ZoomCCInterface.setContext(...)`
- service factory:
- `getZoomCCChatService()`
- `getZoomCCVideoService()`
- `getZoomCCZVAService()`
- `getZoomCCScheduledCallbackService()`
- service lifecycle:
- `init(item)`, `login()`, `logoff()`, `fetchUI()`
- engagement control:
- `endChat()`, `endVideo()`
- release:
- `releaseZoomCCService(key)`

## Deprecation Notes

- Review `deprecated.html` in each SDK version package.
- Keep runtime guards for enum/value additions and optional callbacks.
