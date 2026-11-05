# Android Service Patterns

## Chat Pattern

```kotlin
val service = ZoomCCInterface.getZoomCCChatService()
service.init(
    ZoomCCItem(
        entryId = chatEntryId,
        sdkType = ZoomCCIInterfaceType.CHAT,
        serverType = CCServerType.CCServerWWW
    )
)
service.addListener(object : ZoomCCChatListener {
    override fun unreadMsgCountChanged(count: Int) {}
    override fun onClientEvent(event: ClientEvent) {}
    override fun onEngagementEnd(engagementId: String) {}
    override fun onEngagementStart(engagementId: String) {}
    override fun onLoginStatus(status: IMStatus?) {}
    override fun onError(error: Int, detail: Long, description: String) {}
})
service.login()
service.fetchUI()
```

## Video Pattern

```kotlin
val service = ZoomCCInterface.getZoomCCVideoService()
service.init(
    ZoomCCItem(
        entryId = videoEntryId,
        sdkType = ZoomCCIInterfaceType.VIDEO,
        serverType = CCServerType.CCServerWWW
    )
)
service.setVideoPreviewOption(VideoPreviewOption.ZmCCVideoPreviewOptionDefault)
service.setAutoJoinWhenVideoCreated(false)
service.setUseBackwardFacingCameraByDefault(false)
service.addListener(object : ZoomCCVideoListener {})
service.fetchUI()
```

## Scheduled Callback Pattern

```kotlin
val service = ZoomCCInterface.getZoomCCScheduledCallbackService()
service.init(
    ZoomCCItem(
        apiKey = callbackApiKey,
        sdkType = ZoomCCIInterfaceType.SCHEDULED_CALLBACK,
        serverType = CCServerType.CCServerWWW
    )
)
service.fetchUI()
```

## Cleanup Pattern

```kotlin
override fun onDestroy() {
    ZoomCCInterface.releaseZoomCCService(chatEntryId)
    ZoomCCInterface.releaseZoomCCService(videoEntryId)
    ZoomCCInterface.releaseZoomCCService(callbackApiKey)
    super.onDestroy()
}
```
