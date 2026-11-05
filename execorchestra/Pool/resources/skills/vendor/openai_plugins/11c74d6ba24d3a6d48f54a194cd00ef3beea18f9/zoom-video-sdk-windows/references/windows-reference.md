# Zoom Video SDK Windows - API Reference

**Source**: https://marketplacefront.zoom.us/sdk/custom/windows/

---

## API Hierarchy (5 Levels Deep)

Understanding the SDK requires navigating from the singleton entry point through 5 levels of objects. Start from `IZoomVideoSDK` and follow return types.

### Level 1: Entry Point (Singleton)

```
CreateZoomVideoSDKObj() → IZoomVideoSDK*
```

| Method | Returns | Purpose |
|--------|---------|---------|
| `initialize(params)` | `ZoomVideoSDKErrors` | Initialize SDK (call once) |
| `joinSession(context)` | `IZoomVideoSDKSession*` | Join and get session object |
| `leaveSession(end)` | `ZoomVideoSDKErrors` | Leave or end session |
| `addListener(delegate)` | `void` | Register event callbacks |
| `getSessionInfo()` | `IZoomVideoSDKSession*` | Get current session |
| `getVideoHelper()` | `IZoomVideoSDKVideoHelper*` | Camera/video control |
| `getAudioHelper()` | `IZoomVideoSDKAudioHelper*` | Mic/speaker control |
| `getShareHelper()` | `IZoomVideoSDKShareHelper*` | Screen sharing |
| `getChatHelper()` | `IZoomVideoSDKChatHelper*` | Chat messaging |
| `getUserHelper()` | `IZoomVideoSDKUserHelper*` | User management |
| `getRecordingHelper()` | `IZoomVideoSDKRecordingHelper*` | Cloud recording |
| `getCmdChannel()` | `IZoomVideoSDKCmdChannel*` | Custom signaling |

### Level 2: Core Helpers & Session

#### IZoomVideoSDKSession
```cpp
IZoomVideoSDKSession* session = sdk->getSessionInfo();
```

| Method | Returns | Purpose |
|--------|---------|---------|
| `getMyself()` | `IZoomVideoSDKUser*` | Current user object |
| `getRemoteUsers()` | `IVideoSDKVector<IZoomVideoSDKUser*>*` | All remote users |
| `getSessionName()` | `const zchar_t*` | Session name |
| `getSessionID()` | `const zchar_t*` | Unique session ID |
| `getSessionPassword()` | `const zchar_t*` | Session password |
| `getSessionHost()` | `IZoomVideoSDKUser*` | Host user |

#### IZoomVideoSDKVideoHelper
Controls YOUR camera. Does NOT control remote users' video.

| Method | Returns | Purpose |
|--------|---------|---------|
| `startVideo()` | `ZoomVideoSDKErrors` | Turn on your camera |
| `stopVideo()` | `ZoomVideoSDKErrors` | Turn off your camera |
| `rotateMyVideo(rotation)` | `bool` | Rotate camera output |
| `switchCamera(deviceId)` | `bool` | Change camera device |
| `getCameraList()` | `IVideoSDKVector<IZoomVideoSDKCameraDevice*>*` | Available cameras |
| `getNumberOfCameras()` | `uint32_t` | Camera count |
| `startVideoCanvasPreview(hwnd, aspect, resolution)` | `ZoomVideoSDKErrors` | Preview your video |
| `stopVideoCanvasPreview(hwnd)` | `ZoomVideoSDKErrors` | Stop preview |

#### IZoomVideoSDKAudioHelper
| Method | Returns | Purpose |
|--------|---------|---------|
| `startAudio()` | `ZoomVideoSDKErrors` | Connect to audio |
| `stopAudio()` | `ZoomVideoSDKErrors` | Disconnect audio |
| `muteAudio(user)` | `ZoomVideoSDKErrors` | Mute a user |
| `unmuteAudio(user)` | `ZoomVideoSDKErrors` | Unmute a user |
| `getMicList()` | `IVideoSDKVector<IZoomVideoSDKMicDevice*>*` | Available mics |
| `getSpeakerList()` | `IVideoSDKVector<IZoomVideoSDKSpeakerDevice*>*` | Available speakers |
| `selectMic(deviceId, name)` | `ZoomVideoSDKErrors` | Select mic |
| `selectSpeaker(deviceId, name)` | `ZoomVideoSDKErrors` | Select speaker |

#### IZoomVideoSDKShareHelper
| Method | Returns | Purpose |
|--------|---------|---------|
| `startShareScreen(monitorId)` | `ZoomVideoSDKErrors` | Share a monitor |
| `startShareWindow(hwnd)` | `ZoomVideoSDKErrors` | Share a window |
| `stopShare()` | `ZoomVideoSDKErrors` | Stop sharing |
| `isShareLocked()` | `bool` | Check if locked |
| `lockShare(lock)` | `ZoomVideoSDKErrors` | Lock sharing |
| `isOtherSharing()` | `bool` | Someone else sharing? |

### Level 3: User & Rendering Objects

#### IZoomVideoSDKUser
Represents a participant. Get from `session->getMyself()` or callbacks.

| Method | Returns | Purpose |
|--------|---------|---------|
| `getUserID()` | `const zchar_t*` | Unique user ID |
| `getUserName()` | `const zchar_t*` | Display name |
| `isHost()` | `bool` | Is session host? |
| `isManager()` | `bool` | Is manager? |
| `GetVideoCanvas()` | `IZoomVideoSDKCanvas*` | **SDK-rendered video** |
| `GetVideoPipe()` | `IZoomVideoSDKRawDataPipe*` | **Raw YUV frames** |
| `GetShareCanvas()` | `IZoomVideoSDKCanvas*` | SDK-rendered share |
| `GetSharePipe()` | `IZoomVideoSDKRawDataPipe*` | Raw share frames |
| `getVideoStatus()` | `ZoomVideoSDKVideoStatus` | Video on/off state |
| `getAudioStatus()` | `ZoomVideoSDKAudioStatus` | Audio mute state |

#### IZoomVideoSDKCanvas (SDK Rendering)
Let the SDK render video directly to your HWND. **Recommended for most apps.**

| Method | Returns | Purpose |
|--------|---------|---------|
| `subscribeWithView(hwnd, aspect, resolution)` | `ZoomVideoSDKErrors` | Start rendering to HWND |
| `unSubscribeWithView(hwnd)` | `ZoomVideoSDKErrors` | Stop rendering |
| `setAspectMode(aspect)` | `ZoomVideoSDKErrors` | Change aspect ratio |
| `setResolution(resolution)` | `ZoomVideoSDKErrors` | Change resolution |

#### IZoomVideoSDKRawDataPipe (Raw YUV Access)
Get raw YUV420 frames for custom processing.

| Method | Returns | Purpose |
|--------|---------|---------|
| `subscribe(resolution, delegate)` | `ZoomVideoSDKErrors` | Start receiving frames |
| `unSubscribe(delegate)` | `ZoomVideoSDKErrors` | Stop receiving |
| `getVideoStatus()` | `ZoomVideoSDKVideoStatus` | Check if video is on |

#### IZoomVideoSDKShareAction
Received in `onUserShareStatusChanged` callback. Controls remote share subscription.

| Method | Returns | Purpose |
|--------|---------|---------|
| `subscribe()` | `ZoomVideoSDKErrors` | Subscribe to share |
| `unSubscribe()` | `ZoomVideoSDKErrors` | Unsubscribe |
| `subscribeWithView(hwnd, aspect)` | `ZoomVideoSDKErrors` | Render share to HWND |
| `unSubscribeWithView(hwnd)` | `ZoomVideoSDKErrors` | Stop rendering |
| `getShareCanvas()` | `IZoomVideoSDKCanvas*` | Get share canvas |
| `getSharePipe()` | `IZoomVideoSDKRawDataPipe*` | Get raw share pipe |
| `getShareType()` | `ZoomVideoSDKShareType` | Screen/window/etc |

### Level 4: Devices, Chat & Callbacks

#### IZoomVideoSDKCameraDevice
| Method | Returns |
|--------|---------|
| `getDeviceId()` | `const zchar_t*` |
| `getDeviceName()` | `const zchar_t*` |
| `isSelectedDevice()` | `bool` |

#### IZoomVideoSDKMicDevice / IZoomVideoSDKSpeakerDevice
| Method | Returns |
|--------|---------|
| `getDeviceId()` | `const zchar_t*` |
| `getDeviceName()` | `const zchar_t*` |
| `isSelectedDevice()` | `bool` |

#### IZoomVideoSDKChatHelper
| Method | Returns | Purpose |
|--------|---------|---------|
| `sendChatToAll(message)` | `ZoomVideoSDKErrors` | Broadcast message |
| `sendChatToUser(user, message)` | `ZoomVideoSDKErrors` | Private message |
| `canChatMessageBeDeleted(msgId)` | `bool` | Check delete permission |
| `deleteChatMessage(msgId)` | `ZoomVideoSDKErrors` | Delete a message |

#### IZoomVideoSDKChatMessage
Received in `onChatNewMessageNotify` callback.

| Method | Returns |
|--------|---------|
| `getMessageID()` | `const zchar_t*` |
| `getSendUser()` | `IZoomVideoSDKUser*` |
| `getReceiverUser()` | `IZoomVideoSDKUser*` |
| `getContent()` | `const zchar_t*` |
| `getTimeStamp()` | `time_t` |
| `isChatToAll()` | `bool` |
| `isSelfSend()` | `bool` |

#### IZoomVideoSDKRawDataPipeDelegate
Implement this to receive raw YUV frames.

```cpp
class MyVideoRenderer : public IZoomVideoSDKRawDataPipeDelegate {
    void onRawDataFrameReceived(YUVRawDataI420* data) override {
        // Process frame
    }
    void onRawDataStatusChanged(RawDataStatus status) override {
        // Handle on/off
    }
};
```

### Level 5: Raw Data & Utilities

#### YUVRawDataI420
Video frame in YUV420 format (I420).

| Method | Returns | Purpose |
|--------|---------|---------|
| `GetYBuffer()` | `char*` | Y plane (luminance) |
| `GetUBuffer()` | `char*` | U plane (chrominance) |
| `GetVBuffer()` | `char*` | V plane (chrominance) |
| `GetStreamWidth()` | `unsigned int` | Frame width |
| `GetStreamHeight()` | `unsigned int` | Frame height |
| `GetRotation()` | `unsigned int` | 0, 90, 180, 270 |
| `GetTimeStamp()` | `unsigned long long` | Frame timestamp |
| `CanAddRef()` / `AddRef()` / `Release()` | - | Reference counting |

#### AudioRawData
PCM audio samples (16-bit signed).

| Method | Returns | Purpose |
|--------|---------|---------|
| `GetBuffer()` | `char*` | PCM sample buffer |
| `GetBufferLen()` | `unsigned int` | Buffer size (bytes) |
| `GetSampleRate()` | `unsigned int` | Sample rate (Hz) |
| `GetChannelNum()` | `unsigned int` | 1=mono, 2=stereo |

#### IZoomVideoSDKUserHelper
Admin actions on users.

| Method | Returns | Purpose |
|--------|---------|---------|
| `removeUser(user)` | `bool` | Kick user from session |
| `makeHost(user)` | `bool` | Transfer host role |
| `makeManager(user)` | `bool` | Promote to manager |
| `revokeManager(user)` | `bool` | Demote manager |
| `changeName(user, name)` | `bool` | Rename user |

#### IZoomVideoSDKCmdChannel
Custom signaling (max 60 messages/second).

| Method | Returns | Purpose |
|--------|---------|---------|
| `sendCommand(user, command)` | `ZoomVideoSDKErrors` | Send to one user |
| `sendCommandToAll(command)` | `ZoomVideoSDKErrors` | Broadcast to all |

#### IVirtualBackgroundItem
| Method | Returns |
|--------|---------|
| `getImageFilePath()` | `const zchar_t*` |
| `getImageName()` | `const zchar_t*` |
| `getType()` | `ZoomVideoSDKVirtualBackgroundDataType` |
| `isSelected()` | `bool` |

---

## Critical Timing Rules

### ⚠️ CRITICAL: Subscribe in onUserVideoStatusChanged, NOT onUserJoin

**WRONG** (causes Error 2 - Internal_Error):
```cpp
void onUserJoin(IZoomVideoSDKUserHelper* helper, IVideoSDKVector<IZoomVideoSDKUser*>* userList) {
    for (int i = 0; i < userList->GetCount(); i++) {
        IZoomVideoSDKUser* user = userList->GetItem(i);
        // ERROR: Video may not be ready yet!
        user->GetVideoCanvas()->subscribeWithView(hwnd, aspect, resolution);
    }
}
```

**CORRECT**:
```cpp
void onUserVideoStatusChanged(IZoomVideoSDKVideoHelper* helper,
                               IVideoSDKVector<IZoomVideoSDKUser*>* userList) {
    IZoomVideoSDKUser* myself = sdk->getSessionInfo()->getMyself();

    for (int i = 0; i < userList->GetCount(); i++) {
        IZoomVideoSDKUser* user = userList->GetItem(i);
        if (user == myself) continue;  // Skip self

        // Check if video is actually on
        IZoomVideoSDKRawDataPipe* pipe = user->GetVideoPipe();
        if (pipe) {
            ZoomVideoSDKVideoStatus status = pipe->getVideoStatus();
            if (status.isOn) {
                // NOW it's safe to subscribe
                IZoomVideoSDKCanvas* canvas = user->GetVideoCanvas();
                canvas->subscribeWithView(hwnd, aspect, resolution);
            }
        }
    }
}
```

### Video Status Structure

```cpp
struct ZoomVideoSDKVideoStatus {
    bool isOn;      // true = video is transmitting
    bool hasSource; // true = camera is available
};
```

- `isOn == true` → Safe to subscribe
- `isOn == false` → Unsubscribe or skip
- `hasSource == false` → User has no camera

### Subscribe Fail Reasons (onVideoCanvasSubscribeFail)

```cpp
enum ZoomVideoSDKSubscribeFailReason {
    ZoomVideoSDKSubscribeFailReason_None = 0,
    ZoomVideoSDKSubscribeFailReason_HasSubscribe1080POr720P = 1,
    ZoomVideoSDKSubscribeFailReason_HasSubscribeTwo720P = 2,
    ZoomVideoSDKSubscribeFailReason_HasSubscribeExceededLimit = 3,
    ZoomVideoSDKSubscribeFailReason_HasSubscribeTwoShare = 4,
    ZoomVideoSDKSubscribeFailReason_HasSubscribeVideo1080POr720PAndOneShare = 5,
    ZoomVideoSDKSubscribeFailReason_TooFrequentCall = 6
};
```

**Handling TooFrequentCall**: Add `Sleep(200)` between subscribe calls.

### SDK Error Codes Quick Reference

| Code | Name | Common Cause |
|------|------|--------------|
| 0 | Success | - |
| 1 | Wrong_Usage | Calling method in wrong state |
| 2 | Internal_Error | Video not ready, subscribe too early |
| 7 | Invalid_Parameter | NULL pointer, bad HWND |
| 8 | Call_Too_Frequently | Need Sleep() between calls |

---

## Two Rendering Approaches

| Approach | Interface | When to Use |
|----------|-----------|-------------|
| **Canvas API** | `IZoomVideoSDKCanvas::subscribeWithView(HWND)` | Standard apps, best quality |
| **Raw Data Pipe** | `IZoomVideoSDKRawDataPipe::subscribe(delegate)` | Custom processing, effects, recording |

### Canvas API (Recommended)
```cpp
// SDK renders directly to your window - no YUV conversion needed
IZoomVideoSDKCanvas* canvas = user->GetVideoCanvas();
canvas->subscribeWithView(hwnd, ZoomVideoSDKVideoAspect_PanAndScan, ZoomVideoSDKResolution_Auto);
```

### Raw Data Pipe (Advanced)
```cpp
// You receive YUV420 frames and must render them yourself
class MyRenderer : public IZoomVideoSDKRawDataPipeDelegate {
    void onRawDataFrameReceived(YUVRawDataI420* data) override {
        // Convert YUV to RGB, then render with GDI/DirectX/OpenGL
    }
};

IZoomVideoSDKRawDataPipe* pipe = user->GetVideoPipe();
pipe->subscribe(ZoomVideoSDKResolution_720P, myRenderer);
```

---

## Complete Class List

### Core SDK

| Class | Description |
|-------|-------------|
| `IZoomVideoSDK` | Main singleton object - session creation, callbacks, features |
| `IZoomVideoSDKSession` | Session information interface |
| `IZoomVideoSDKDelegate` | Event callbacks for session events |
| `IZoomVideoSDKUser` | User object interface |
| `IZoomVideoSDKUserHelper` | User management helper |

### Raw Data Interfaces

| Class | Description |
|-------|-------------|
| `AudioRawData` | Audio raw data handler (PCM 16-bit) |
| `YUVRawDataI420` | YUV raw data handler (I420 format) |
| `YUVProcessDataI420` | YUV processing data |
| `IZoomVideoSDKRawDataPipe` | Video/share raw data pipe |
| `IZoomVideoSDKRawDataPipeDelegate` | Video/share raw data sink |
| `IYUVRawDataI420Converter` | I420 YUV converter |

### Virtual Devices

| Class | Description |
|-------|-------------|
| `IZoomVideoSDKVirtualAudioMic` | Virtual audio microphone for injection |
| `IZoomVideoSDKVirtualAudioSpeaker` | Virtual audio speaker |
| `IZoomVideoSDKVideoSource` | Video source for injection |
| `IZoomVideoSDKVideoSourcePreProcessor` | Video preprocessing |
| `IZoomVideoSDKShareSource` | Share source for injection |
| `IZoomVideoSDKSharePreprocessor` | Share preprocessing |

### Senders

| Class | Description |
|-------|-------------|
| `IZoomVideoSDKAudioSender` | Audio raw data sender |
| `IZoomVideoSDKVideoSender` | Video raw data sender |
| `IZoomVideoSDKShareSender` | Share raw data sender |
| `IZoomVideoSDKShareAudioSender` | Share audio sender |
| `IZoomVideoSDKShareAudioSource` | Share audio source |

### Helpers

| Class | Description |
|-------|-------------|
| `IZoomVideoSDKAudioHelper` | Audio controls |
| `IZoomVideoSDKVideoHelper` | Video/camera controls |
| `IZoomVideoSDKShareHelper` | Screen sharing |
| `IZoomVideoSDKChatHelper` | Chat messaging |
| `IZoomVideoSDKRecordingHelper` | Cloud recording |
| `IZoomVideoSDKLiveStreamHelper` | RTMP live streaming |
| `IZoomVideoSDKLiveTranscriptionHelper` | Live transcription |
| `IZoomVideoSDKPhoneHelper` | Phone dial-out |
| `IZoomVideoSDKCmdChannel` | Command channel |
| `IZoomVideoSDKCRCHelper` | CRC helper |
| `IZoomVideoSDKWhiteboardHelper` | Whiteboard |
| `IZoomVideoSDKAnnotationHelper` | Annotations |
| `IZoomVideoSDKNetworkConnectionHelper` | Network connection |
| `IZoomVideoSDKSubSessionHelper` | Subsession helper |
| `IZoomVideoSDKSubSessionManager` | Subsession manager |
| `IZoomVideoSDKRTMSHelper` | Real-time media streams |
| `IZoomVideoSDKIncomingLiveStreamHelper` | Incoming live stream |

### Settings Helpers

| Class | Description |
|-------|-------------|
| `IZoomVideoSDKAudioSettingHelper` | Audio settings |
| `IZoomVideoSDKVideoSettingHelper` | Video settings |
| `IZoomVideoSDKShareSettingHelper` | Share settings |
| `IZoomVideoSDKTestAudioDeviceHelper` | Audio device testing |

### Devices

| Class | Description |
|-------|-------------|
| `IZoomVideoSDKCameraDevice` | Camera device |
| `IZoomVideoSDKMicDevice` | Microphone device |
| `IZoomVideoSDKSpeakerDevice` | Speaker device |
| `IVirtualBackgroundItem` | Virtual background item |

### Streaming

| Class | Description |
|-------|-------------|
| `IZoomVideoSDKBroadcastStreamingController` | Broadcast controller |
| `IZoomVideoSDKBroadcastStreamingViewer` | Broadcast viewer |
| `IZoomVideoSDKBroadcastStreamingAudioCallback` | Broadcast audio callback |
| `IZoomVideoSDKBroadcastStreamingVideoCallback` | Broadcast video callback |

### Session & Messages

| Class | Description |
|-------|-------------|
| `IZoomVideoSDKChatMessage` | Chat message |
| `ILiveTranscriptionLanguage` | Transcription language |
| `ILiveTranscriptionMessageInfo` | Transcription message |
| `IZoomVideoSDKSessionDialInNumberInfo` | Dial-in info |
| `IZoomVideoSDKPhoneSupportCountryInfo` | Phone country info |

### Subsessions

| Class | Description |
|-------|-------------|
| `ISubSessionKit` | Subsession kit |
| `ISubSessionUser` | Subsession user |
| `ISubSessionUserHelpRequestHandler` | Help request handler |
| `IZoomVideoSDKSubSessionParticipant` | Subsession participant |

### File Transfer

| Class | Description |
|-------|-------------|
| `IZoomVideoSDKFileTransferBaseInfo` | File transfer base info |
| `IZoomVideoSDKSendFile` | Send file interface |
| `IZoomVideoSDKReceiveFile` | Receive file interface |

### Handlers

| Class | Description |
|-------|-------------|
| `IZoomVideoSDKPasswordHandler` | Password handler |
| `IZoomVideoSDKRecordingConsentHandler` | Recording consent |
| `IZoomVideoSDKCameraControlRequestHandler` | Camera control requests |
| `IZoomVideoSDKRemoteCameraControlHelper` | Remote camera control |
| `IZoomVideoSDKProxySettingHandler` | Proxy settings |
| `IZoomVideoSDKSSLCertificateInfo` | SSL certificate info |

### Canvas & Actions

| Class | Description |
|-------|-------------|
| `IZoomVideoSDKCanvas` | Video/share canvas |
| `IZoomVideoSDKShareAction` | Share action |
| `IMonitorListBuilder` | Monitor list builder |

### Utilities

| Class | Description |
|-------|-------------|
| `IVideoSDKVector` | SDK vector collection |

---

## Structures

### Initialization

```cpp
struct ZoomVideoSDKInitParams {
    const zchar_t* domain;              // Required: L"https://zoom.us"
    bool enableLog;                      // Enable logging
    const zchar_t* logFilePrefix;        // Log file prefix
    ZoomVideoSDKRawDataMemoryMode videoRawDataMemoryMode;
    ZoomVideoSDKRawDataMemoryMode shareRawDataMemoryMode;
    ZoomVideoSDKRawDataMemoryMode audioRawDataMemoryMode;
    bool enableIndirectRawdata;          // Indirect raw data access
    ZoomVideoSDKExtendParams* extendParams; // Extended parameters
};

struct ZoomVideoSDKExtendParams {
    const zchar_t* speakerTestFilePath;
    // Additional extended parameters
};
```

### Session Context

```cpp
struct ZoomVideoSDKSessionContext {
    const zchar_t* sessionName;          // Required
    const zchar_t* sessionPassword;      // Optional
    const zchar_t* userName;             // Required
    const zchar_t* token;                // Required: JWT token
    unsigned int sessionIdleTimeoutMins; // 0 = never timeout, default 40
    bool autoLoadMutliStream;            // Auto-load multiple streams

    ZoomVideoSDKVideoOption videoOption;
    ZoomVideoSDKAudioOption audioOption;

    IZoomVideoSDKVideoSource* externalVideoSource;
    IZoomVideoSDKVirtualAudioMic* virtualAudioMic;
    IZoomVideoSDKVirtualAudioSpeaker* virtualAudioSpeaker;
    IZoomVideoSDKVideoSourcePreProcessor* preProcessor;
};

struct ZoomVideoSDKVideoOption {
    bool localVideoOn;                   // Start with video on
};

struct ZoomVideoSDKAudioOption {
    bool connect;                        // Connect to audio
    bool mute;                           // Start muted
};
```

### Statistics

```cpp
struct ZoomVideoSDKSessionAudioStatisticInfo {
    int frequency;
    int latency;
    int Jitter;
    float packetLossAvg;
    float packetLossMax;
};

struct ZoomVideoSDKSessionASVStatisticInfo {
    int frame_width;
    int frame_height;
    int fps;
    int latency;
    int Jitter;
    float packetLossAvg;
    float packetLossMax;
};

// Aliases
typedef ZoomVideoSDKSessionASVStatisticInfo _SessionASVStatisticInfo;
typedef ZoomVideoSDKSessionAudioStatisticInfo _SessionAudioStatisticInfo;

struct ZoomVideoSDKVideoStatisticInfo {
    int width;
    int height;
    int fps;
    int bps;
};

struct ZoomVideoSDKShareStatisticInfo {
    int width;
    int height;
    int fps;
    int bps;
};
```

### Video/Audio Status

```cpp
struct ZoomVideoSDKVideoStatus {
    bool isOn;
    bool hasSource;
};

struct ZoomVideoSDKAudioStatus {
    bool isMuted;
    bool isAudioConnected;
    ZoomVideoSDKAudioType audioType;
};

struct VideoSourceCapability {
    unsigned int width;
    unsigned int height;
    unsigned int frame;  // FPS
};
```

### Live Streaming

```cpp
struct ZoomVideoSDKLiveStreamParams {
    const zchar_t* streamUrl;           // RTMP URL
    const zchar_t* streamKey;           // Stream key
    const zchar_t* broadcastUrl;        // Broadcast URL
};

struct ZoomVideoSDKLiveStreamSetting {
    // Live stream settings
};

struct IncomingLiveStreamStatus {
    // Incoming stream status
};
```

### Share

```cpp
struct ZoomVideoSDKShareOption {
    bool isWithDeviceAudio;
    bool isOptimizeForSharedVideo;
};

struct ZoomVideoSDKShareCursorData {
    int x;
    int y;
    // Cursor information
};

struct ZoomVideoSDKSharePreprocessParam {
    // Preprocessing parameters
};
```

### File Transfer

```cpp
struct FileTransferProgress {
    unsigned long long transferredSize;
    unsigned long long totalSize;
    float percentage;
};

struct ZoomVideoSDKFileStatus {
    // File transfer status
};
```

### Misc

```cpp
struct ZoomVideoSDKViewSize {
    int width;
    int height;
};

struct tagVideoPreferenceSetting {
    // Video preference settings
};

struct tagProxySettings {
    // Proxy configuration
};

struct InvitePhoneUserInfo {
    const zchar_t* countryCode;
    const zchar_t* phoneNumber;
    const zchar_t* displayName;
};

struct ZoomVideoSDKSteamingJoinContext {
    // Streaming join context
};
```

---

## IZoomVideoSDK (Main Interface)

```cpp
class IZoomVideoSDK {
public:
    // Lifecycle
    virtual ZoomVideoSDKErrors initialize(ZoomVideoSDKInitParams& params) = 0;
    virtual ZoomVideoSDKErrors cleanup() = 0;

    // Session management
    virtual IZoomVideoSDKSession* joinSession(ZoomVideoSDKSessionContext& params) = 0;
    virtual ZoomVideoSDKErrors leaveSession(bool end) = 0;
    virtual IZoomVideoSDKSession* getSessionInfo() = 0;
    virtual bool isInSession() = 0;

    // Listeners
    virtual void addListener(IZoomVideoSDKDelegate* listener) = 0;
    virtual void removeListener(IZoomVideoSDKDelegate* listener) = 0;

    // Helpers
    virtual IZoomVideoSDKAudioHelper* getAudioHelper() = 0;
    virtual IZoomVideoSDKVideoHelper* getVideoHelper() = 0;
    virtual IZoomVideoSDKUserHelper* getUserHelper() = 0;
    virtual IZoomVideoSDKShareHelper* getShareHelper() = 0;
    virtual IZoomVideoSDKRecordingHelper* getRecordingHelper() = 0;
    virtual IZoomVideoSDKLiveStreamHelper* getLiveStreamHelper() = 0;
    virtual IZoomVideoSDKChatHelper* getChatHelper() = 0;
    virtual IZoomVideoSDKCmdChannel* getCmdChannel() = 0;
    virtual IZoomVideoSDKPhoneHelper* getPhoneHelper() = 0;
    virtual IZoomVideoSDKLiveTranscriptionHelper* getLiveTranscriptionHelper() = 0;
    virtual IZoomVideoSDKCRCHelper* getCRCHelper() = 0;
    virtual IZoomVideoSDKWhiteboardHelper* getWhiteboardHelper() = 0;
    virtual IZoomVideoSDKSubSessionHelper* getSubSessionHelper() = 0;
    virtual IZoomVideoSDKRTMSHelper* getRealTimeMediaStreamsHelper() = 0;
    virtual IZoomVideoSDKIncomingLiveStreamHelper* getIncomingLiveStreamHelper() = 0;

    // Settings
    virtual IZoomVideoSDKAudioSettingHelper* getAudioSettingHelper() = 0;
    virtual IZoomVideoSDKVideoSettingHelper* getVideoSettingHelper() = 0;
    virtual IZoomVideoSDKShareSettingHelper* getShareSettingHelper() = 0;
    virtual IZoomVideoSDKTestAudioDeviceHelper* GetAudioDeviceTestHelper() = 0;
    virtual IZoomVideoSDKNetworkConnectionHelper* getNetworkConnectionHelper() = 0;

    // Utilities
    virtual const zchar_t* getSDKVersion() = 0;
    virtual const zchar_t* exportLog() = 0;
    virtual ZoomVideoSDKErrors cleanAllExportedLogs() = 0;
};
```

### Factory Functions

```cpp
// Create SDK object
IZoomVideoSDK* CreateZoomVideoSDKObj();

// Destroy SDK object
void DestroyZoomVideoSDKObj();
```

---

## IZoomVideoSDKDelegate (Callbacks)

```cpp
class IZoomVideoSDKDelegate {
public:
    // Session callbacks
    virtual void onSessionJoin() = 0;
    virtual void onSessionLeave() = 0;
    virtual void onSessionLeave(ZoomVideoSDKSessionLeaveReason eReason) = 0;
    virtual void onError(ZoomVideoSDKErrors errorCode, int detailErrorCode) = 0;
    virtual void onSessionNeedPassword(IZoomVideoSDKPasswordHandler* handler) = 0;
    virtual void onSessionPasswordWrong(IZoomVideoSDKPasswordHandler* handler) = 0;

    // User callbacks
    virtual void onUserJoin(IZoomVideoSDKUserHelper* pUserHelper,
                           IVideoSDKVector<IZoomVideoSDKUser*>* userList) = 0;
    virtual void onUserLeave(IZoomVideoSDKUserHelper* pUserHelper,
                            IVideoSDKVector<IZoomVideoSDKUser*>* userList) = 0;
    virtual void onUserHostChanged(IZoomVideoSDKUserHelper* pUserHelper,
                                  IZoomVideoSDKUser* pUser) = 0;
    virtual void onUserManagerChanged(IZoomVideoSDKUser* pUser) = 0;
    virtual void onUserNameChanged(IZoomVideoSDKUser* pUser) = 0;

    // Video callbacks
    virtual void onUserVideoStatusChanged(IZoomVideoSDKVideoHelper* pVideoHelper,
                                         IVideoSDKVector<IZoomVideoSDKUser*>* userList) = 0;
    virtual void onSpotlightVideoChanged(IZoomVideoSDKVideoHelper* pVideoHelper,
                                        IVideoSDKVector<IZoomVideoSDKUser*>* userList) = 0;

    // Audio callbacks
    virtual void onUserAudioStatusChanged(IZoomVideoSDKAudioHelper* pAudioHelper,
                                         IVideoSDKVector<IZoomVideoSDKUser*>* userList) = 0;
    virtual void onUserActiveAudioChanged(IZoomVideoSDKAudioHelper* pAudioHelper,
                                         IVideoSDKVector<IZoomVideoSDKUser*>* list) = 0;

    // Raw audio callbacks
    virtual void onMixedAudioRawDataReceived(AudioRawData* data_) = 0;
    virtual void onOneWayAudioRawDataReceived(AudioRawData* data_,
                                             IZoomVideoSDKUser* pUser) = 0;
    virtual void onSharedAudioRawDataReceived(AudioRawData* data_) = 0;

    // Share callbacks
    virtual void onUserShareStatusChanged(IZoomVideoSDKShareHelper* pShareHelper,
                                         IZoomVideoSDKUser* pUser,
                                         IZoomVideoSDKShareAction* pShareAction) = 0;
    virtual void onShareContentChanged(IZoomVideoSDKShareHelper* pShareHelper,
                                      IZoomVideoSDKUser* pUser,
                                      IZoomVideoSDKShareAction* pShareAction) = 0;
    virtual void onFailedToStartShare(IZoomVideoSDKShareHelper* pShareHelper,
                                     IZoomVideoSDKUser* pUser) = 0;
    virtual void onShareContentSizeChanged(IZoomVideoSDKShareHelper* pShareHelper,
                                          IZoomVideoSDKUser* pUser,
                                          IZoomVideoSDKShareAction* pShareAction) = 0;

    // Chat callbacks
    virtual void onChatNewMessageNotify(IZoomVideoSDKChatHelper* pChatHelper,
                                       IZoomVideoSDKChatMessage* messageItem) = 0;
    virtual void onChatMsgDeleteNotification(IZoomVideoSDKChatHelper* pChatHelper,
                                            const zchar_t* msgID,
                                            ZoomVideoSDKChatMessageDeleteType deleteBy) = 0;
    virtual void onChatPrivilegeChanged(IZoomVideoSDKChatHelper* pChatHelper,
                                       ZoomVideoSDKChatPrivilegeType privilege) = 0;

    // Command channel callbacks
    virtual void onCommandReceived(IZoomVideoSDKUser* sender, const zchar_t* strCmd) = 0;
    virtual void onCommandChannelConnectResult(bool isSuccess) = 0;

    // Recording callbacks
    virtual void onCloudRecordingStatus(RecordingStatus status,
                                       IZoomVideoSDKRecordingConsentHandler* pHandler) = 0;
    virtual void onUserRecordingConsent(IZoomVideoSDKUser* pUser) = 0;
    virtual void onHostAskUnmute() = 0;

    // Live stream callbacks
    virtual void onLiveStreamStatusChanged(IZoomVideoSDKLiveStreamHelper* pLiveStreamHelper,
                                          ZoomVideoSDKLiveStreamStatus status) = 0;

    // Live transcription callbacks
    virtual void onLiveTranscriptionStatus(ZoomVideoSDKLiveTranscriptionStatus status) = 0;
    virtual void onOriginalLanguageMsgReceived(ILiveTranscriptionMessageInfo* messageInfo) = 0;
    virtual void onLiveTranscriptionMsgInfoReceived(ILiveTranscriptionMessageInfo* messageInfo) = 0;
    virtual void onLiveTranscriptionMsgError(ILiveTranscriptionLanguage* spokenLanguage,
                                            ILiveTranscriptionLanguage* transcriptLanguage) = 0;

    // Phone callbacks
    virtual void onInviteByPhoneStatus(PhoneStatus status, PhoneFailedReason reason) = 0;
    virtual void onCalloutJoinSuccess(IZoomVideoSDKUser* pUser, const zchar_t* phoneNumber) = 0;

    // Camera control callbacks
    virtual void onCameraControlRequestResult(IZoomVideoSDKUser* pUser, bool isApproved) = 0;
    virtual void onCameraControlRequestReceived(IZoomVideoSDKUser* pUser,
                                               ZoomVideoSDKCameraControlRequestType requestType,
                                               IZoomVideoSDKCameraControlRequestHandler* handler) = 0;

    // Remote control callbacks
    virtual void onRemoteControlStatus(IZoomVideoSDKUser* pUser,
                                      IZoomVideoSDKShareAction* pShareAction,
                                      ZoomVideoSDKRemoteControlStatus status) = 0;
    virtual void onRemoteControlRequestReceived(IZoomVideoSDKUser* pUser,
                                               IZoomVideoSDKShareAction* pShareAction,
                                               IZoomVideoSDKRemoteControlRequestHandler* handler) = 0;
    virtual void onRemoteControlServiceInstallResult(bool bSuccess) = 0;

    // Multi-camera callbacks
    virtual void onMultiCameraStreamStatusChanged(ZoomVideoSDKMultiCameraStreamStatus status,
                                                 IZoomVideoSDKUser* pUser,
                                                 IZoomVideoSDKRawDataPipe* pVideoPipe) = 0;

    // Device callbacks
    virtual void onMicSpeakerVolumeChanged(unsigned int micVolume,
                                          unsigned int speakerVolume) = 0;
    virtual void onAudioDeviceStatusChanged(ZoomVideoSDKAudioDeviceType type,
                                           ZoomVideoSDKAudioDeviceStatus status) = 0;
    virtual void onTestMicStatusChanged(ZoomVideoSDK_TESTMIC_STATUS status) = 0;
    virtual void onSelectedAudioDeviceChanged() = 0;
    virtual void onCameraListChanged() = 0;

    // Network callbacks
    virtual void onUserVideoNetworkStatusChanged(ZoomVideoSDKNetworkStatus status,
                                                IZoomVideoSDKUser* pUser) = 0;
    virtual void onProxyDetectComplete() = 0;
    virtual void onProxySettingNotification(IZoomVideoSDKProxySettingHandler* handler) = 0;
    virtual void onSSLCertVerifiedFailNotification(IZoomVideoSDKSSLCertificateInfo* info) = 0;

    // CRC callbacks
    virtual void onCallCRCDeviceStatusChanged(ZoomVideoSDKCRCCallStatus status) = 0;

    // Canvas callbacks
    virtual void onVideoCanvasSubscribeFail(ZoomVideoSDKSubscribeFailReason fail_reason,
                                           IZoomVideoSDKUser* pUser, void* handle) = 0;
    virtual void onShareCanvasSubscribeFail(IZoomVideoSDKUser* pUser, void* handle,
                                           IZoomVideoSDKShareAction* pShareAction) = 0;

    // Annotation callbacks
    virtual void onAnnotationHelperCleanUp(IZoomVideoSDKAnnotationHelper* helper) = 0;
    virtual void onAnnotationPrivilegeChange(IZoomVideoSDKUser* pUser,
                                            IZoomVideoSDKShareAction* pShareAction) = 0;
    virtual void onAnnotationHelperActived(void* handle) = 0;

    // File transfer callbacks
    virtual void onSendFileStatus(IZoomVideoSDKSendFile* file,
                                 const FileTransferStatus& status) = 0;
    virtual void onReceiveFileStatus(IZoomVideoSDKReceiveFile* file,
                                    const FileTransferStatus& status) = 0;

    // Misc callbacks
    virtual void onVideoAlphaChannelStatusChanged(bool isAlphaModeOn) = 0;

    // Incoming live stream callbacks
    virtual void onBindIncomingLiveStreamResponse(bool bSuccess, const zchar_t* strStreamKeyID) = 0;
    virtual void onUnbindIncomingLiveStreamResponse(bool bSuccess, const zchar_t* strStreamKeyID) = 0;
    virtual void onIncomingLiveStreamStatusResponse(bool bSuccess,
                                                    IVideoSDKVector<IncomingLiveStreamStatus>* list) = 0;
    virtual void onStartIncomingLiveStreamResponse(bool bSuccess, const zchar_t* strStreamKeyID) = 0;
    virtual void onStopIncomingLiveStreamResponse(bool bSuccess, const zchar_t* strStreamKeyID) = 0;
};
```

---

## Raw Data Interfaces

### AudioRawData

```cpp
class AudioRawData {
public:
    virtual char* GetBuffer() = 0;           // PCM 16-bit buffer
    virtual unsigned int GetBufferLen() = 0; // Buffer length in bytes
    virtual unsigned int GetSampleRate() = 0;// Sample rate (Hz)
    virtual unsigned int GetChannelNum() = 0;// Channels (1=mono, 2=stereo)
    virtual unsigned long long GetTimeStamp() = 0;
};
```

### YUVRawDataI420

```cpp
class YUVRawDataI420 {
public:
    virtual char* GetYBuffer() = 0;
    virtual char* GetUBuffer() = 0;
    virtual char* GetVBuffer() = 0;
    virtual char* GetAlphaBuffer() = 0;      // Optional alpha channel
    virtual char* GetBuffer() = 0;           // Full YUV buffer
    virtual unsigned int GetBufferLen() = 0;
    virtual unsigned int GetStreamWidth() = 0;
    virtual unsigned int GetStreamHeight() = 0;
    virtual unsigned int GetRotation() = 0;  // 0, 90, 180, 270
    virtual unsigned long long GetSourceID() = 0;
    virtual unsigned long long GetTimeStamp() = 0;
    virtual bool IsLimitedI420() = 0;

    // Reference counting
    virtual bool CanAddRef() = 0;
    virtual bool AddRef() = 0;
    virtual int Release() = 0;
};
```

### IZoomVideoSDKRawDataPipeDelegate

```cpp
class IZoomVideoSDKRawDataPipeDelegate {
public:
    virtual void onRawDataFrameReceived(YUVRawDataI420* data) = 0;
    virtual void onRawDataStatusChanged(RawDataStatus status) = 0;
};

enum RawDataStatus {
    RawData_On,
    RawData_Off
};
```

---

## Virtual Device Interfaces

### IZoomVideoSDKVirtualAudioMic

```cpp
class IZoomVideoSDKVirtualAudioMic {
public:
    virtual void onMicInitialize(IZoomVideoSDKAudioSender* sender) = 0;
    virtual void onMicStartSend() = 0;
    virtual void onMicStopSend() = 0;
    virtual void onMicUninitialized() = 0;
};

class IZoomVideoSDKAudioSender {
public:
    virtual ZoomVideoSDKErrors Send(char* data,
                                   unsigned int dataLength,
                                   int sampleRate) = 0;
};
```

### IZoomVideoSDKVirtualAudioSpeaker

```cpp
class IZoomVideoSDKVirtualAudioSpeaker {
public:
    virtual void onVirtualSpeakerMixedAudioReceived(AudioRawData* data_) = 0;
    virtual void onVirtualSpeakerOneWayAudioReceived(AudioRawData* data_,
                                                    IZoomVideoSDKUser* pUser) = 0;
    virtual void onVirtualSpeakerSharedAudioReceived(AudioRawData* data_) = 0;
};
```

### IZoomVideoSDKVideoSource

```cpp
class IZoomVideoSDKVideoSource {
public:
    virtual void onInitialize(IZoomVideoSDKVideoSender* sender,
                             IVideoSDKVector<VideoSourceCapability>* supportCapList,
                             VideoSourceCapability& suggestCap) = 0;
    virtual void onPropertyChange(IVideoSDKVector<VideoSourceCapability>* supportCapList,
                                 VideoSourceCapability suggestCap) = 0;
    virtual void onStartSend() = 0;
    virtual void onStopSend() = 0;
    virtual void onUninitialized() = 0;
};

class IZoomVideoSDKVideoSender {
public:
    virtual ZoomVideoSDKErrors sendVideoFrame(char* frameBuffer,
                                             int width, int height,
                                             int frameLength,
                                             int rotation) = 0;
    // Alternative with Y, U, V planes
    virtual ZoomVideoSDKErrors sendVideoFrame(char* yBuffer, char* uBuffer, char* vBuffer,
                                             int width, int height,
                                             int frameLength,
                                             int rotation) = 0;
};
```

### IZoomVideoSDKShareSource

```cpp
class IZoomVideoSDKShareSource {
public:
    virtual void onShareSendStarted(IZoomVideoSDKShareSender* pSender) = 0;
    virtual void onShareSendStopped() = 0;
};

class IZoomVideoSDKShareSender {
public:
    virtual ZoomVideoSDKErrors sendShareFrame(char* frameBuffer,
                                             int width, int height,
                                             int frameLength) = 0;
    virtual ZoomVideoSDKErrors sendShareFrame(char* yBuffer, char* uBuffer, char* vBuffer,
                                             int width, int height,
                                             int frameLength,
                                             int rotation) = 0;
};
```

---

## Enumerations

### ZoomVideoSDKErrors

```cpp
enum ZoomVideoSDKErrors {
    ZoomVideoSDKErrors_Success = 0,
    ZoomVideoSDKErrors_Wrong_Usage = 1,
    ZoomVideoSDKErrors_Internal_Error = 2,
    ZoomVideoSDKErrors_Uninitialize = 3,
    ZoomVideoSDKErrors_Memory_Error = 4,
    ZoomVideoSDKErrors_Load_Module_Error = 5,
    ZoomVideoSDKErrors_UnLoad_Module_Error = 6,
    ZoomVideoSDKErrors_Invalid_Parameter = 7,
    ZoomVideoSDKErrors_Call_Too_Frequently = 8,
    ZoomVideoSDKErrors_No_Impl = 9,
    ZoomVideoSDKErrors_Dont_Support_Feature = 10,
    ZoomVideoSDKErrors_Unknown = 100,

    // Auth errors (1000+)
    ZoomVideoSDKErrors_Auth_Error = 1001,
    ZoomVideoSDKErrors_Auth_Empty_Key_or_Secret = 1002,
    ZoomVideoSDKErrors_Auth_Wrong_Key_or_Secret = 1003,
    ZoomVideoSDKErrors_Auth_DoesNot_Support_SDK = 1004,
    ZoomVideoSDKErrors_Auth_Disable_SDK = 1005,

    // Session errors (3000+)
    ZoomVideoSDKErrors_Session_Join_Failed = 3001,
    ZoomVideoSDKErrors_Session_No_Rights = 3002,
    ZoomVideoSDKErrors_Session_Already_In_Progress = 3003,
    ZoomVideoSDKErrors_Session_Dont_Support_SessionType = 3004,
    ZoomVideoSDKErrors_Session_Reconnecting = 3005,
    ZoomVideoSDKErrors_Session_Disconnecting = 3006,
    ZoomVideoSDKErrors_Session_Not_Started = 3007,
    ZoomVideoSDKErrors_Session_Need_Password = 3008,
    ZoomVideoSDKErrors_Session_Password_Wrong = 3009,
    ZoomVideoSDKErrors_Session_Remote_DB_Error = 3010,
    ZoomVideoSDKErrors_Session_Invalid_Param = 3011,

    // Audio/Video errors
    ZoomVideoSDKErrors_Session_Audio_Error = 4001,
    ZoomVideoSDKErrors_Session_Audio_No_Microphone = 4002,
    ZoomVideoSDKErrors_Session_Video_Error = 5001,
    ZoomVideoSDKErrors_Session_Video_Device_Error = 5002,

    // Share errors
    ZoomVideoSDKErrors_Session_Share_Error = 6001,
    ZoomVideoSDKErrors_Session_Share_Module_Not_Ready = 6002,
    ZoomVideoSDKErrors_Session_Share_You_Are_Not_Sharing = 6003,
    ZoomVideoSDKErrors_Session_Share_Type_Is_Not_Support = 6004,
    ZoomVideoSDKErrors_Session_Share_Internal_Error = 6005,

    ZoomVideoSDKErrors_Dont_Support_Multi_Stream_Video_User = 7001,
};
```

### Resolution Options

```cpp
enum ZoomVideoSDKResolution {
    ZoomVideoSDKResolution_90P,
    ZoomVideoSDKResolution_180P,
    ZoomVideoSDKResolution_360P,
    ZoomVideoSDKResolution_720P,
    ZoomVideoSDKResolution_1080P
};
```

### Recording Status

```cpp
enum RecordingStatus {
    Recording_Start,
    Recording_Stop,
    Recording_Pause,
    Recording_Connecting,
    Recording_DiskFull
};
```

### Memory Mode

```cpp
enum ZoomVideoSDKRawDataMemoryMode {
    ZoomVideoSDKRawDataMemoryModeStack,
    ZoomVideoSDKRawDataMemoryModeHeap
};
```

### Session Leave Reason

```cpp
enum ZoomVideoSDKSessionLeaveReason {
    ZoomVideoSDKSessionLeaveReason_EndByHost,
    ZoomVideoSDKSessionLeaveReason_HostEndForAll,
    ZoomVideoSDKSessionLeaveReason_KickedByHost,
    ZoomVideoSDKSessionLeaveReason_Timeout,
    ZoomVideoSDKSessionLeaveReason_SessionIdleTimeout,
    ZoomVideoSDKSessionLeaveReason_Default
};
```

### Live Transcription Status

```cpp
enum ZoomVideoSDKLiveTranscriptionStatus {
    ZoomVideoSDKLiveTranscription_Status_Stop,
    ZoomVideoSDKLiveTranscription_Status_Start
};
```

### Network Status

```cpp
enum ZoomVideoSDKNetworkStatus {
    ZoomVideoSDKNetworkStatus_Good,
    ZoomVideoSDKNetworkStatus_Normal,
    ZoomVideoSDKNetworkStatus_Poor,
    ZoomVideoSDKNetworkStatus_Bad,
    ZoomVideoSDKNetworkStatus_Connecting
};
```

---

## Essential Headers

```cpp
// Core headers
#include "zoom_video_sdk_api.h"              // CreateZoomVideoSDKObj, DestroyZoomVideoSDKObj
#include "zoom_video_sdk_interface.h"        // IZoomVideoSDK
#include "zoom_video_sdk_delegate_interface.h" // IZoomVideoSDKDelegate
#include "zoom_video_sdk_def.h"              // Structures, enums
#include "zoom_video_sdk_platform.h"         // Platform definitions
#include "zoom_sdk_raw_data_def.h"           // Raw data types

// Helper headers
#include "helpers/zoom_video_sdk_user_helper_interface.h"
#include "helpers/zoom_video_sdk_audio_helper_interface.h"
#include "helpers/zoom_video_sdk_video_helper_interface.h"
#include "helpers/zoom_video_sdk_share_helper_interface.h"
#include "helpers/zoom_video_sdk_chat_helper_interface.h"
#include "helpers/zoom_video_sdk_recording_helper_interface.h"
#include "helpers/zoom_video_sdk_livestream_helper_interface.h"
#include "helpers/zoom_video_sdk_livetranscription_helper_interface.h"
#include "helpers/zoom_video_sdk_cmd_channel_interface.h"
#include "helpers/zoom_video_sdk_phone_helper_interface.h"
#include "helpers/zoom_video_sdk_audio_send_rawdata_interface.h"
#include "helpers/zoom_video_sdk_video_source_helper_interface.h"

// Message interfaces
#include "zoom_video_sdk_chat_message_interface.h"
#include "zoom_video_sdk_session_info_interface.h"

// Namespace
using namespace ZOOM_VIDEO_SDK_NAMESPACE;
// Or use macro
USING_ZOOM_VIDEO_SDK_NAMESPACE
```

---

## Additional Resources

- **Official Docs**: https://developers.zoom.us/docs/video-sdk/windows/
- **API Reference**: https://marketplacefront.zoom.us/sdk/custom/windows/
- **Sample Code**: https://github.com/zoom/videosdk-windows-rawdata-sample
- **Dev Forum**: https://devforum.zoom.us
- **C# .NET Sample**: https://github.com/zoom/videosdk-windows-dotnet-quickstart
