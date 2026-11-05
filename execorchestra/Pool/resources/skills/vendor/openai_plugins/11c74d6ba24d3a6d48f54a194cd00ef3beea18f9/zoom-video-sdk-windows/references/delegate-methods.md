# Delegate Methods Reference

Complete list of all `IZoomVideoSDKDelegate` callback methods. **All 80+ methods must be implemented**, even if empty.

> **Note**: The callback count has grown significantly in SDK v2.4.x with additions for subsessions (breakout rooms), broadcast streaming, whiteboard, RTMS, and enhanced annotation support.

---

## Quick Template

Copy this template and add your implementation:

```cpp
class MyDelegate : public IZoomVideoSDKDelegate {
public:
    // ═══════════════════════════════════════════════════════════════════════
    // SESSION LIFECYCLE
    // ═══════════════════════════════════════════════════════════════════════

    void onSessionJoin() override {
        // Called when successfully joined session
    }

    void onSessionLeave() override {
        // Called when left session (no reason)
    }

    void onSessionLeave(ZoomVideoSDKSessionLeaveReason reason) override {
        // Called when left session (with reason)
    }

    void onError(ZoomVideoSDKErrors errorCode, int detailErrorCode) override {
        // Called on SDK errors
    }

    void onSessionNeedPassword(IZoomVideoSDKPasswordHandler* handler) override {
        // Called when session requires password
    }

    void onSessionPasswordWrong(IZoomVideoSDKPasswordHandler* handler) override {
        // Called when password is incorrect
    }

    // ═══════════════════════════════════════════════════════════════════════
    // USER EVENTS
    // ═══════════════════════════════════════════════════════════════════════

    void onUserJoin(IZoomVideoSDKUserHelper* helper,
                    IVideoSDKVector<IZoomVideoSDKUser*>* userList) override {
        // Called when users join session
    }

    void onUserLeave(IZoomVideoSDKUserHelper* helper,
                     IVideoSDKVector<IZoomVideoSDKUser*>* userList) override {
        // Called when users leave session
    }

    void onUserHostChanged(IZoomVideoSDKUserHelper* helper,
                           IZoomVideoSDKUser* user) override {
        // Called when host changes
    }

    void onUserManagerChanged(IZoomVideoSDKUser* user) override {
        // Called when manager status changes
    }

    void onUserNameChanged(IZoomVideoSDKUser* user) override {
        // Called when user name changes
    }

    // ═══════════════════════════════════════════════════════════════════════
    // VIDEO EVENTS
    // ═══════════════════════════════════════════════════════════════════════

    void onUserVideoStatusChanged(IZoomVideoSDKVideoHelper* helper,
                                  IVideoSDKVector<IZoomVideoSDKUser*>* userList) override {
        // IMPORTANT: Subscribe to video here, not in onUserJoin
    }

    void onSpotlightVideoChanged(IZoomVideoSDKVideoHelper* helper,
                                 IVideoSDKVector<IZoomVideoSDKUser*>* userList) override {
        // Called when spotlight changes
    }

    void onVideoCanvasSubscribeFail(ZoomVideoSDKSubscribeFailReason reason,
                                    IZoomVideoSDKUser* user, void* handle) override {
        // Called when video subscription fails
    }

    void onVideoAlphaChannelStatusChanged(bool isAlphaModeOn) override {
        // Called when alpha channel mode changes
    }

    // ═══════════════════════════════════════════════════════════════════════
    // AUDIO EVENTS
    // ═══════════════════════════════════════════════════════════════════════

    void onUserAudioStatusChanged(IZoomVideoSDKAudioHelper* helper,
                                  IVideoSDKVector<IZoomVideoSDKUser*>* userList) override {
        // Called when audio status changes (mute/unmute)
    }

    void onUserActiveAudioChanged(IZoomVideoSDKAudioHelper* helper,
                                  IVideoSDKVector<IZoomVideoSDKUser*>* userList) override {
        // Called when active speaker changes
    }

    void onHostAskUnmute() override {
        // Called when host requests you to unmute
    }

    // ═══════════════════════════════════════════════════════════════════════
    // RAW AUDIO EVENTS
    // ═══════════════════════════════════════════════════════════════════════

    void onMixedAudioRawDataReceived(AudioRawData* data) override {
        // Called with mixed audio from all participants
    }

    void onOneWayAudioRawDataReceived(AudioRawData* data,
                                      IZoomVideoSDKUser* user) override {
        // Called with audio from specific user
    }

    void onSharedAudioRawDataReceived(AudioRawData* data) override {
        // Called with shared audio
    }

    // ═══════════════════════════════════════════════════════════════════════
    // SHARE EVENTS
    // ═══════════════════════════════════════════════════════════════════════

    void onUserShareStatusChanged(IZoomVideoSDKShareHelper* helper,
                                  IZoomVideoSDKUser* user,
                                  IZoomVideoSDKShareAction* shareAction) override {
        // Called when share status changes - use shareAction to subscribe
    }

    void onShareContentChanged(IZoomVideoSDKShareHelper* helper,
                               IZoomVideoSDKUser* user,
                               IZoomVideoSDKShareAction* shareAction) override {
        // Called when share content type changes
    }

    void onFailedToStartShare(IZoomVideoSDKShareHelper* helper,
                              IZoomVideoSDKUser* user) override {
        // Called when share fails to start
    }

    void onShareContentSizeChanged(IZoomVideoSDKShareHelper* helper,
                                   IZoomVideoSDKUser* user,
                                   IZoomVideoSDKShareAction* shareAction) override {
        // Called when share size changes
    }

    void onShareCanvasSubscribeFail(IZoomVideoSDKUser* user, void* handle,
                                    IZoomVideoSDKShareAction* shareAction) override {
        // Called when share subscription fails
    }

    // ═══════════════════════════════════════════════════════════════════════
    // CHAT EVENTS
    // ═══════════════════════════════════════════════════════════════════════

    void onChatNewMessageNotify(IZoomVideoSDKChatHelper* helper,
                                IZoomVideoSDKChatMessage* messageItem) override {
        // Called when new chat message received
    }

    void onChatMsgDeleteNotification(IZoomVideoSDKChatHelper* helper,
                                     const zchar_t* msgID,
                                     ZoomVideoSDKChatMessageDeleteType deleteBy) override {
        // Called when chat message deleted
    }

    void onChatPrivilegeChanged(IZoomVideoSDKChatHelper* helper,
                                ZoomVideoSDKChatPrivilegeType privilege) override {
        // Called when chat privilege changes
    }

    // ═══════════════════════════════════════════════════════════════════════
    // COMMAND CHANNEL EVENTS
    // ═══════════════════════════════════════════════════════════════════════

    void onCommandReceived(IZoomVideoSDKUser* sender, const zchar_t* strCmd) override {
        // Called when command received
    }

    void onCommandChannelConnectResult(bool isSuccess) override {
        // Called when command channel connection result
    }

    // ═══════════════════════════════════════════════════════════════════════
    // RECORDING EVENTS
    // ═══════════════════════════════════════════════════════════════════════

    void onCloudRecordingStatus(RecordingStatus status,
                                IZoomVideoSDKRecordingConsentHandler* handler) override {
        // Called when cloud recording status changes
    }

    void onUserRecordingConsent(IZoomVideoSDKUser* user) override {
        // Called when user gives recording consent
    }

    // ═══════════════════════════════════════════════════════════════════════
    // LIVE STREAM EVENTS
    // ═══════════════════════════════════════════════════════════════════════

    void onLiveStreamStatusChanged(IZoomVideoSDKLiveStreamHelper* helper,
                                   ZoomVideoSDKLiveStreamStatus status) override {
        // Called when live stream status changes
    }

    // ═══════════════════════════════════════════════════════════════════════
    // LIVE TRANSCRIPTION EVENTS
    // ═══════════════════════════════════════════════════════════════════════

    void onLiveTranscriptionStatus(ZoomVideoSDKLiveTranscriptionStatus status) override {
        // Called when transcription status changes
    }

    void onLiveTranscriptionMsgInfoReceived(ILiveTranscriptionMessageInfo* info) override {
        // Called when transcription message received
    }

    void onOriginalLanguageMsgReceived(ILiveTranscriptionMessageInfo* info) override {
        // Called when original language message received
    }

    void onLiveTranscriptionMsgError(ILiveTranscriptionLanguage* spokenLanguage,
                                     ILiveTranscriptionLanguage* transcriptLanguage) override {
        // Called on transcription error
    }

    // ═══════════════════════════════════════════════════════════════════════
    // PHONE EVENTS
    // ═══════════════════════════════════════════════════════════════════════

    void onInviteByPhoneStatus(PhoneStatus status, PhoneFailedReason reason) override {
        // Called when phone invite status changes
    }

    void onCalloutJoinSuccess(IZoomVideoSDKUser* user, const zchar_t* phoneNumber) override {
        // Called when callout user joins
    }

    // ═══════════════════════════════════════════════════════════════════════
    // CAMERA CONTROL EVENTS
    // ═══════════════════════════════════════════════════════════════════════

    void onCameraControlRequestResult(IZoomVideoSDKUser* user, bool isApproved) override {
        // Called when camera control request result
    }

    void onCameraControlRequestReceived(IZoomVideoSDKUser* user,
                                        ZoomVideoSDKCameraControlRequestType requestType,
                                        IZoomVideoSDKCameraControlRequestHandler* handler) override {
        // Called when camera control request received
    }

    // ═══════════════════════════════════════════════════════════════════════
    // REMOTE CONTROL EVENTS
    // ═══════════════════════════════════════════════════════════════════════

    void onRemoteControlStatus(IZoomVideoSDKUser* user,
                               IZoomVideoSDKShareAction* shareAction,
                               ZoomVideoSDKRemoteControlStatus status) override {
        // Called when remote control status changes
    }

    void onRemoteControlRequestReceived(IZoomVideoSDKUser* user,
                                        IZoomVideoSDKShareAction* shareAction,
                                        IZoomVideoSDKRemoteControlRequestHandler* handler) override {
        // Called when remote control request received
    }

    void onRemoteControlServiceInstallResult(bool bSuccess) override {
        // Called when remote control service install result
    }

    // ═══════════════════════════════════════════════════════════════════════
    // MULTI-CAMERA EVENTS
    // ═══════════════════════════════════════════════════════════════════════

    void onMultiCameraStreamStatusChanged(ZoomVideoSDKMultiCameraStreamStatus status,
                                          IZoomVideoSDKUser* user,
                                          IZoomVideoSDKRawDataPipe* pipe) override {
        // Called when multi-camera stream status changes
    }

    // ═══════════════════════════════════════════════════════════════════════
    // DEVICE EVENTS
    // ═══════════════════════════════════════════════════════════════════════

    void onMicSpeakerVolumeChanged(unsigned int micVolume,
                                   unsigned int speakerVolume) override {
        // Called when mic/speaker volume changes
    }

    void onAudioDeviceStatusChanged(ZoomVideoSDKAudioDeviceType type,
                                    ZoomVideoSDKAudioDeviceStatus status) override {
        // Called when audio device status changes
    }

    void onTestMicStatusChanged(ZoomVideoSDK_TESTMIC_STATUS status) override {
        // Called when test mic status changes
    }

    void onSelectedAudioDeviceChanged() override {
        // Called when selected audio device changes
    }

    void onCameraListChanged() override {
        // Called when camera list changes
    }

    // ═══════════════════════════════════════════════════════════════════════
    // NETWORK EVENTS
    // ═══════════════════════════════════════════════════════════════════════

    void onUserVideoNetworkStatusChanged(ZoomVideoSDKNetworkStatus status,
                                         IZoomVideoSDKUser* user) override {
        // Called when video network status changes
    }

    void onProxyDetectComplete() override {
        // Called when proxy detection completes
    }

    void onProxySettingNotification(IZoomVideoSDKProxySettingHandler* handler) override {
        // Called when proxy settings notification
    }

    void onSSLCertVerifiedFailNotification(IZoomVideoSDKSSLCertificateInfo* info) override {
        // Called when SSL cert verification fails
    }

    // ═══════════════════════════════════════════════════════════════════════
    // CRC EVENTS
    // ═══════════════════════════════════════════════════════════════════════

    void onCallCRCDeviceStatusChanged(ZoomVideoSDKCRCCallStatus status) override {
        // Called when CRC device status changes
    }

    // ═══════════════════════════════════════════════════════════════════════
    // ANNOTATION EVENTS
    // ═══════════════════════════════════════════════════════════════════════

    void onAnnotationHelperCleanUp(IZoomVideoSDKAnnotationHelper* helper) override {
        // Called when annotation helper cleanup
    }

    void onAnnotationPrivilegeChange(IZoomVideoSDKUser* user,
                                     IZoomVideoSDKShareAction* shareAction) override {
        // Called when annotation privilege changes
    }

    void onAnnotationHelperActived(void* handle) override {
        // Called when annotation helper activated
    }

    // ═══════════════════════════════════════════════════════════════════════
    // FILE TRANSFER EVENTS
    // ═══════════════════════════════════════════════════════════════════════

    void onSendFileStatus(IZoomVideoSDKSendFile* file,
                          const FileTransferStatus& status) override {
        // Called when send file status changes
    }

    void onReceiveFileStatus(IZoomVideoSDKReceiveFile* file,
                             const FileTransferStatus& status) override {
        // Called when receive file status changes
    }

    // ═══════════════════════════════════════════════════════════════════════
    // INCOMING LIVE STREAM EVENTS
    // ═══════════════════════════════════════════════════════════════════════

    void onBindIncomingLiveStreamResponse(bool bSuccess, const zchar_t* strStreamKeyID) override {
        // Called when bind incoming live stream response
    }

    void onUnbindIncomingLiveStreamResponse(bool bSuccess, const zchar_t* strStreamKeyID) override {
        // Called when unbind incoming live stream response
    }

    void onIncomingLiveStreamStatusResponse(bool bSuccess,
                                            IVideoSDKVector<IncomingLiveStreamStatus>* list) override {
        // Called when incoming live stream status response
    }

    void onStartIncomingLiveStreamResponse(bool bSuccess, const zchar_t* strStreamKeyID) override {
        // Called when start incoming live stream response
    }

    void onStopIncomingLiveStreamResponse(bool bSuccess, const zchar_t* strStreamKeyID) override {
        // Called when stop incoming live stream response
    }

    // ═══════════════════════════════════════════════════════════════════════
    // SHARE SETTING & CONTENT EVENTS
    // ═══════════════════════════════════════════════════════════════════════

    void onShareSettingChanged(ZoomVideoSDKShareSetting setting) override {
        // Called when share settings change
    }

    void onUnsharingWindowsChanged(IVideoSDKVector<void*>* windowsList,
                                   IZoomVideoSDKShareHelper* pShareHelper,
                                   IZoomVideoSDKUser* pUser,
                                   IZoomVideoSDKShareAction* pShareAction) override {
        // Called when list of unsharing windows changes (macOS only)
    }

    void onSharingActiveMonitorChanged(IVideoSDKVector<void*>* monitorIDs,
                                       IZoomVideoSDKShareHelper* pShareHelper,
                                       IZoomVideoSDKUser* pUser,
                                       IZoomVideoSDKShareAction* pShareAction) override {
        // Called when active monitors displaying share changes
    }

    // ═══════════════════════════════════════════════════════════════════════
    // AUDIO LEVEL & NETWORK EVENTS (NEW)
    // ═══════════════════════════════════════════════════════════════════════

    void onAudioLevelChanged(unsigned int level, bool bAudioSharing,
                            IZoomVideoSDKUser* pUser) override {
        // Called when audio level changes (range 0-9)
    }

    void onUserNetworkStatusChanged(ZoomVideoSDKDataType type,
                                    ZoomVideoSDKNetworkStatus level,
                                    IZoomVideoSDKUser* pUser) override {
        // Called when network status changes for specific data type
    }

    void onUserOverallNetworkStatusChanged(ZoomVideoSDKNetworkStatus level,
                                           IZoomVideoSDKUser* pUser) override {
        // Called when overall network status changes
    }

    void onShareNetworkStatusChanged(ZoomVideoSDKNetworkStatus shareNetworkStatus,
                                     bool isSendingShare) override {
        // Called when share network status changes (deprecated)
    }

    // ═══════════════════════════════════════════════════════════════════════
    // LIVE TRANSCRIPTION EVENTS (ADDITIONAL)
    // ═══════════════════════════════════════════════════════════════════════

    void onSpokenLanguageChanged(ILiveTranscriptionLanguage* spokenLanguage) override {
        // Called when spoken language changes
    }

    // ═══════════════════════════════════════════════════════════════════════
    // ANNOTATION EVENTS (ADDITIONAL)
    // ═══════════════════════════════════════════════════════════════════════

    void onAnnotationToolTypeChanged(IZoomVideoSDKAnnotationHelper* helper,
                                     void* handle,
                                     ZoomVideoSDKAnnotationToolType toolType) override {
        // Called when annotation tool type changes
    }

    // ═══════════════════════════════════════════════════════════════════════
    // WHITEBOARD EVENTS
    // ═══════════════════════════════════════════════════════════════════════

    void onUserWhiteboardShareStatusChanged(IZoomVideoSDKUser* user,
                                            IZoomVideoSDKWhiteboardHelper* helper) override {
        // Called when whiteboard share status changes
    }

    void onWhiteboardExported(ZoomVideoSDKExportFormat format,
                              unsigned char* data, long length) override {
        // Called when whiteboard export completes
    }

    // ═══════════════════════════════════════════════════════════════════════
    // SUBSESSION (BREAKOUT ROOM) EVENTS
    // ═══════════════════════════════════════════════════════════════════════

    void onSubSessionStatusChanged(ZoomVideoSDKSubSessionStatus status,
                                   IVideoSDKVector<ISubSessionKit*>* pSubSessionKitList) override {
        // Called when subsession status changes
    }

    void onSubSessionManagerHandle(IZoomVideoSDKSubSessionManager* pManager) override {
        // Called when user gains subsession manager privilege
    }

    void onSubSessionParticipantHandle(IZoomVideoSDKSubSessionParticipant* pParticipant) override {
        // Called when user gains/loses subsession participant privileges
    }

    void onSubSessionUsersUpdate(ISubSessionKit* pSubSessionKit) override {
        // Called when subsession users are updated
    }

    void onBroadcastMessageFromMainSession(const zchar_t* sMessage,
                                           const zchar_t* sUserName) override {
        // Called when receiving broadcast message from main session
    }

    void onSubSessionUserHelpRequest(ISubSessionUserHelpRequestHandler* pHandler) override {
        // Called when receiving help request from subsession
    }

    void onSubSessionUserHelpRequestResult(ZoomVideoSDKUserHelpRequestResult eResult) override {
        // Called with help request result
    }

    // ═══════════════════════════════════════════════════════════════════════
    // BROADCAST STREAMING EVENTS
    // ═══════════════════════════════════════════════════════════════════════

    void onStartBroadcastResponse(bool bSuccess, const zchar_t* channelID) override {
        // Called when start broadcast response received
    }

    void onStopBroadcastResponse(bool bSuccess) override {
        // Called when stop broadcast response received
    }

    void onGetBroadcastControlStatus(bool bSuccess,
                                     ZoomVideoSDKBroadcastControlStatus status) override {
        // Called when get broadcast status response received
    }

    void onStreamingJoinStatusChanged(ZoomVideoSDKStreamingJoinStatus status) override {
        // Called when viewer's join status changes
    }

    // ═══════════════════════════════════════════════════════════════════════
    // RTMS (REAL-TIME MEDIA STREAMS) EVENTS
    // ═══════════════════════════════════════════════════════════════════════

    void onRealTimeMediaStreamsStatus(RealTimeMediaStreamsStatus status) override {
        // Called when RTMS status changes
    }

    void onRealTimeMediaStreamsFail(RealTimeMediaStreamsFailReason failReason) override {
        // Called when RTMS fails
    }

    // ═══════════════════════════════════════════════════════════════════════
    // CANVAS SNAPSHOT EVENTS
    // ═══════════════════════════════════════════════════════════════════════

    void onCanvasSnapshotTaken(IZoomVideoSDKUser* pUser, bool isShare) override {
        // Called when canvas snapshot is taken successfully
    }

    void onCanvasSnapshotIncompatible(IZoomVideoSDKUser* pUser) override {
        // Called when snapshot cannot be taken due to compatibility
    }
};
```

---

## Most Important Callbacks

| Callback | When to Use |
|----------|-------------|
| `onSessionJoin` | Start audio/video, subscribe to self |
| `onSessionLeave` | Cleanup resources |
| `onError` | Handle errors |
| `onUserJoin` | Track new users (but don't subscribe video here!) |
| `onUserLeave` | Cleanup user resources |
| `onUserVideoStatusChanged` | **Subscribe to video here** |
| `onUserAudioStatusChanged` | Track mute/unmute |
| `onChatNewMessageNotify` | Handle chat messages |
| `onUserShareStatusChanged` | Subscribe to screen share |
| `onVideoCanvasSubscribeFail` | Handle subscription failures |

---

## Related Documentation

- [SDK Architecture Pattern](../concepts/sdk-architecture-pattern.md) - Event-driven design
- [Video Rendering](../examples/video-rendering.md) - Using video callbacks
- [Build Errors](../troubleshooting/build-errors.md) - Abstract class errors
- [API Reference](windows-reference.md) - Full method signatures

---

**TL;DR**: Copy the template above and implement all methods. Focus on session, user, video, and audio events for basic functionality.
