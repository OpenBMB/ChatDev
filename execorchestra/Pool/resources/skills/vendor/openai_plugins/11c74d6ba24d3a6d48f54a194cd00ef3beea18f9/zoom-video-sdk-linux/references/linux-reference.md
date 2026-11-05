# Zoom Video SDK Linux - API Reference

**Source**: https://marketplacefront.zoom.us/sdk/custom/linux/

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
| `AudioRawData` | Audio raw data handler (PCM) |
| `YUVRawDataI420` | YUV raw data handler (I420 format) |
| `YUVProcessDataI420` | YUV processing data |
| `IZoomVideoSDKRawDataPipe` | Video/share raw data pipe |
| `IZoomVideoSDKRawDataPipeDelegate` | Video/share raw data sink |
| `IYUVRawDataI420Converter` | I420 YUV converter |

### Virtual Devices

| Class | Description |
|-------|-------------|
| `IZoomVideoSDKVirtualAudioMic` | Virtual audio microphone for injection |
| `IZoomVideoSDKVirtualAudioSpeaker` | Virtual audio speaker for headless |
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
| `IZoomVideoSDKIncomingLiveStreamHelper` | Incoming live stream |
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
    const zchar_t* domain;              // Required: "https://zoom.us"
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

// Alias
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

---

## IZoomVideoSDKDelegate (Callbacks)

```cpp
class IZoomVideoSDKDelegate {
public:
    // Session
    virtual void onSessionJoin() = 0;
    virtual void onSessionLeave() = 0;
    virtual void onError(ZoomVideoSDKErrors errorCode, int detailErrorCode) = 0;
    virtual void onSessionNeedPassword(IZoomVideoSDKPasswordHandler* handler) = 0;
    virtual void onSessionPasswordWrong(IZoomVideoSDKPasswordHandler* handler) = 0;

    // Users
    virtual void onUserJoin(IZoomVideoSDKUserHelper* pUserHelper,
                           IVideoSDKVector<IZoomVideoSDKUser*>* userList) = 0;
    virtual void onUserLeave(IZoomVideoSDKUserHelper* pUserHelper,
                            IVideoSDKVector<IZoomVideoSDKUser*>* userList) = 0;
    virtual void onUserHostChanged(IZoomVideoSDKUserHelper* pUserHelper,
                                  IZoomVideoSDKUser* pUser) = 0;
    virtual void onUserManagerChanged(IZoomVideoSDKUser* pUser) = 0;
    virtual void onUserNameChanged(IZoomVideoSDKUser* pUser) = 0;

    // Video
    virtual void onUserVideoStatusChanged(IZoomVideoSDKVideoHelper* pVideoHelper,
                                         IVideoSDKVector<IZoomVideoSDKUser*>* userList) = 0;

    // Audio
    virtual void onUserAudioStatusChanged(IZoomVideoSDKAudioHelper* pAudioHelper,
                                         IVideoSDKVector<IZoomVideoSDKUser*>* userList) = 0;
    virtual void onUserActiveAudioChanged(IZoomVideoSDKAudioHelper* pAudioHelper,
                                         IVideoSDKVector<IZoomVideoSDKUser*>* list) = 0;

    // Raw Audio
    virtual void onMixedAudioRawDataReceived(AudioRawData* data_) = 0;
    virtual void onOneWayAudioRawDataReceived(AudioRawData* data_,
                                             IZoomVideoSDKUser* pUser) = 0;
    virtual void onSharedAudioRawDataReceived(AudioRawData* data_) = 0;

    // Virtual Speaker
    virtual void onVirtualSpeakerMixedAudioReceived(AudioRawData* data_) = 0;
    virtual void onVirtualSpeakerOneWayAudioReceived(AudioRawData* data_,
                                                    IZoomVideoSDKUser* pUser) = 0;
    virtual void onVirtualSpeakerSharedAudioReceived(AudioRawData* data_) = 0;

    // Share
    virtual void onUserShareStatusChanged(IZoomVideoSDKShareHelper* pShareHelper,
                                         IZoomVideoSDKUser* pUser,
                                         IZoomVideoSDKShareAction* pShareAction) = 0;

    // Chat
    virtual void onChatNewMessageNotify(IZoomVideoSDKChatHelper* pChatHelper,
                                       IZoomVideoSDKChatMessage* messageItem) = 0;
    virtual void onChatMsgDeleteNotification(IZoomVideoSDKChatHelper* pChatHelper,
                                            const zchar_t* msgID,
                                            ZoomVideoSDKChatMessageDeleteType deleteBy) = 0;
    virtual void onChatPrivilegeChanged(IZoomVideoSDKChatHelper* pChatHelper,
                                       ZoomVideoSDKChatPrivilegeType privilege) = 0;

    // Commands
    virtual void onCommandReceived(IZoomVideoSDKUser* sender, const zchar_t* strCmd) = 0;
    virtual void onCommandChannelConnectResult(bool isSuccess) = 0;

    // Recording
    virtual void onCloudRecordingStatus(RecordingStatus status,
                                       IZoomVideoSDKRecordingConsentHandler* pHandler) = 0;
    virtual void onUserRecordingConsent(IZoomVideoSDKUser* pUser) = 0;
    virtual void onHostAskUnmute() = 0;

    // Live Stream
    virtual void onLiveStreamStatusChanged(IZoomVideoSDKLiveStreamHelper* pLiveStreamHelper,
                                          ZoomVideoSDKLiveStreamStatus status) = 0;

    // Live Transcription
    virtual void onLiveTranscriptionStatus(ZoomVideoSDKLiveTranscriptionStatus status) = 0;
    virtual void onLiveTranscriptionMsgReceived(const zchar_t* ltMsg,
                                               IZoomVideoSDKUser* pUser,
                                               ZoomVideoSDKLiveTranscriptionOperationType type) = 0;
    virtual void onLiveTranscriptionMsgInfoReceived(ILiveTranscriptionMessageInfo* messageInfo) = 0;
    virtual void onLiveTranscriptionMsgError(ILiveTranscriptionLanguage* spokenLanguage,
                                            ILiveTranscriptionLanguage* transcriptLanguage) = 0;
    virtual void onOriginalLanguageMsgReceived(ILiveTranscriptionMessageInfo* messageInfo) = 0;

    // Phone
    virtual void onInviteByPhoneStatus(PhoneStatus status, PhoneFailedReason reason) = 0;
    virtual void onCalloutJoinSuccess(IZoomVideoSDKUser* pUser, const zchar_t* phoneNumber) = 0;

    // Camera Control
    virtual void onCameraControlRequestResult(IZoomVideoSDKUser* pUser, bool isApproved) = 0;
    virtual void onCameraControlRequestReceived(IZoomVideoSDKUser* pUser,
                                               ZoomVideoSDKCameraControlRequestType requestType,
                                               IZoomVideoSDKCameraControlRequestHandler* handler) = 0;

    // Multi-Camera
    virtual void onMultiCameraStreamStatusChanged(ZoomVideoSDKMultiCameraStreamStatus status,
                                                 IZoomVideoSDKUser* pUser,
                                                 IZoomVideoSDKRawDataPipe* pVideoPipe) = 0;

    // Devices
    virtual void onMicSpeakerVolumeChanged(unsigned int micVolume,
                                          unsigned int speakerVolume) = 0;
    virtual void onAudioDeviceStatusChanged(ZoomVideoSDKAudioDeviceType type,
                                           ZoomVideoSDKAudioDeviceStatus status) = 0;
    virtual void onTestMicStatusChanged(ZoomVideoSDK_TESTMIC_STATUS status) = 0;
    virtual void onSelectedAudioDeviceChanged() = 0;
    virtual void onCameraListChanged() = 0;

    // Network
    virtual void onUserVideoNetworkStatusChanged(ZoomVideoSDKNetworkStatus status,
                                                IZoomVideoSDKUser* pUser) = 0;
    virtual void onProxyDetectComplete() = 0;
    virtual void onProxySettingNotification(IZoomVideoSDKProxySettingHandler* handler) = 0;
    virtual void onSSLCertVerifiedFailNotification(IZoomVideoSDKSSLCertificateInfo* info) = 0;

    // CRC
    virtual void onCallCRCDeviceStatusChanged(ZoomVideoSDKCRCCallStatus status) = 0;

    // Canvas
    virtual void onVideoCanvasSubscribeFail(ZoomVideoSDKSubscribeFailReason fail_reason,
                                           IZoomVideoSDKUser* pUser, void* handle) = 0;
    virtual void onShareCanvasSubscribeFail(ZoomVideoSDKSubscribeFailReason fail_reason,
                                           IZoomVideoSDKUser* pUser, void* handle) = 0;

    // Annotations
    virtual void onAnnotationHelperCleanUp(IZoomVideoSDKAnnotationHelper* helper) = 0;
    virtual void onAnnotationPrivilegeChange(IZoomVideoSDKUser* pUser, bool enable) = 0;
    virtual void onAnnotationHelperActived(void* handle) = 0;

    // Video Alpha Channel
    virtual void onVideoAlphaChannelStatusChanged(bool isAlphaModeOn) = 0;

    // File Transfer
    virtual void onSendFileStatus(IZoomVideoSDKSendFile* file,
                                 const FileTransferStatus& status) = 0;
    virtual void onReceiveFileStatus(IZoomVideoSDKReceiveFile* file,
                                    const FileTransferStatus& status) = 0;
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

---

## Essential Headers

```cpp
#include "zoom_video_sdk_api.h"              // CreateZoomVideoSDKObj, DestroyZoomVideoSDKObj
#include "zoom_video_sdk_interface.h"        // IZoomVideoSDK
#include "zoom_video_sdk_delegate_interface.h" // IZoomVideoSDKDelegate
#include "zoom_video_sdk_def.h"              // Structures, enums
#include "zoom_video_sdk_platform.h"         // Platform definitions
#include "zoom_sdk_raw_data_def.h"           // Raw data types

// Helpers
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
```

---

## Additional Resources

- **Official Docs**: https://developers.zoom.us/docs/video-sdk/linux/
- **API Reference**: https://marketplacefront.zoom.us/sdk/custom/linux/
- **Sample Code**: https://github.com/zoom/videosdk-linux-raw-recording-sample
- **Dev Forum**: https://devforum.zoom.us
