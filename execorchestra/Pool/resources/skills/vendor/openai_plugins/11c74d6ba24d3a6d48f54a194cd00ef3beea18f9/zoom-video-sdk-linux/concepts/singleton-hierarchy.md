# Singleton Hierarchy - Complete SDK Navigation Map

## 5-Level SDK Navigation

The Zoom Video SDK for Linux follows a hierarchical singleton pattern. Understanding this hierarchy is the key to navigating the entire SDK.

```
Level 1: SDK Singleton
    └─ IZoomVideoSDK (CreateZoomVideoSDKObj)
        │
        ├─ Level 2: Session Info
        │   └─ IZoomVideoSDKSession (via getSessionInfo)
        │       └─ Level 3: Users
        │           └─ IZoomVideoSDKUser[] (via getMyself, getAllUsers, getRemoteUsers)
        │               └─ Level 4: User Pipes
        │                   ├─ IZoomVideoSDKRawDataPipe (via GetVideoPipe)
        │                   └─ IZoomVideoSDKRawDataPipe (via GetSharePipe)
        │
        └─ Level 2: Feature Helpers
            ├─ IZoomVideoSDKAudioHelper (getAudioHelper)
            ├─ IZoomVideoSDKVideoHelper (getVideoHelper)
            ├─ IZoomVideoSDKShareHelper (getShareHelper)
            ├─ IZoomVideoSDKChatHelper (getChatHelper)
            ├─ IZoomVideoSDKRecordingHelper (getRecordingHelper)
            ├─ IZoomVideoSDKLiveStreamHelper (getLiveStreamHelper)
            ├─ IZoomVideoSDKLiveTranscriptionHelper (getLiveTranscriptionHelper)
            ├─ IZoomVideoSDKCmdChannel (getCmdChannel)
            ├─ IZoomVideoSDKPhoneHelper (getPhoneHelper)
            ├─ IZoomVideoSDKCRCHelper (getCRCHelper)
            ├─ IZoomVideoSDKWhiteboardHelper (getWhiteboardHelper)
            ├─ IZoomVideoSDKSubSessionHelper (getSubSessionHelper)
            └─ Settings Helpers
                ├─ IZoomVideoSDKAudioSettingHelper (getAudioSettingHelper)
                ├─ IZoomVideoSDKVideoSettingHelper (getVideoSettingHelper)
                └─ IZoomVideoSDKShareSettingHelper (getShareSettingHelper)
```

---

## Level 1: SDK Singleton

**Entry Point**: This is where everything starts.

```cpp
// Create SDK object
IZoomVideoSDK* video_sdk_obj = CreateZoomVideoSDKObj();

// Initialize
ZoomVideoSDKInitParams init_params;
init_params.domain = "https://zoom.us";
init_params.enableLog = true;
init_params.logFilePrefix = "bot";
init_params.videoRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;
init_params.shareRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;
init_params.audioRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;

video_sdk_obj->initialize(init_params);

// Join session
ZoomVideoSDKSessionContext ctx;
ctx.sessionName = "my-session";
ctx.userName = "Bot";
ctx.token = "jwt-token";

IZoomVideoSDKSession* session = video_sdk_obj->joinSession(ctx);

// Cleanup
video_sdk_obj->leaveSession(false);
video_sdk_obj->cleanup();
DestroyZoomVideoSDKObj();
```

**Key Methods**:
- `initialize()` - Must be called before any other SDK operations
- `joinSession()` - Join or create a session
- `leaveSession(bool endSession)` - Leave session (host can end for all)
- `cleanup()` - Release SDK resources
- `addListener()` / `removeListener()` - Register event callbacks
- `isInSession()` - Check if currently in a session
- `getSessionInfo()` - Access Level 2: Session
- `get*Helper()` - Access Level 2: Feature Helpers

---

## Level 2A: Session Info

**Purpose**: Access session-level information and users.

```cpp
IZoomVideoSDKSession* session = video_sdk_obj->getSessionInfo();
```

**Key Methods**:
```cpp
// Current user
IZoomVideoSDKUser* myself = session->getMyself();

// All users (including self)
IVideoSDKVector<IZoomVideoSDKUser*>* all = session->getAllUsers();

// Remote users only (excluding self)
IVideoSDKVector<IZoomVideoSDKUser*>* remote = session->getRemoteUsers();

// Session info
const char* sessionName = session->getSessionName();
const char* sessionID = session->getSessionID();
const char* sessionPassword = session->getSessionPassword();
const char* sessionHost = session->getSessionHost();
```

---

## Level 2B: Feature Helpers

Feature helpers control YOUR streams and actions. They do NOT control other users' streams.

### Audio Helper

**Purpose**: Control YOUR audio (mic, speaker, mute).

```cpp
IZoomVideoSDKAudioHelper* audio = video_sdk_obj->getAudioHelper();

// Start/stop your audio
audio->startAudio();
audio->stopAudio();

// Mute/unmute yourself
audio->muteAudio(true);
audio->unmuteAudio();

// Subscribe to raw audio callbacks
audio->subscribe();
audio->unSubscribe();

// Device management
IVideoSDKVector<IZoomVideoSDKMicDevice*>* mics = audio->getMicList();
IVideoSDKVector<IZoomVideoSDKSpeakerDevice*>* speakers = audio->getSpeakerList();
audio->selectMic(deviceID);
audio->selectSpeaker(deviceID);
```

**Key Insight**: To receive others' audio, subscribe via `subscribe()` and implement audio callbacks in `IZoomVideoSDKDelegate`.

### Video Helper

**Purpose**: Control YOUR video (camera).

```cpp
IZoomVideoSDKVideoHelper* video = video_sdk_obj->getVideoHelper();

// Start/stop your video
video->startVideo();
video->stopVideo();

// Camera management
IVideoSDKVector<IZoomVideoSDKCameraDevice*>* cameras = video->getCameraList();
video->selectCamera(deviceID);

// Video settings
video->rotateMyVideo(90);  // 0, 90, 180, 270
```

**Key Insight**: To receive others' video, subscribe to their `GetVideoPipe()`.

### Share Helper

**Purpose**: Control YOUR screen share.

```cpp
IZoomVideoSDKShareHelper* share = video_sdk_obj->getShareHelper();

// Start/stop screen share
share->startShare();
share->stopShare();

// Custom share source
IZoomVideoSDKShareSource* source = new MyShareSource();
share->startSharingExternalSource(source);

// Share status
bool isSharing = share->isSharingOut();
bool canShare = share->isSharingOut() == false;
```

**Key Insight**: To receive others' share, subscribe to their `GetSharePipe()`.

### Chat Helper

**Purpose**: Send/receive chat messages.

```cpp
IZoomVideoSDKChatHelper* chat = video_sdk_obj->getChatHelper();

// Send messages
chat->sendChatToAll("Hello everyone!");
chat->sendChatToUser(user, "Private message");

// Delete messages (host only)
chat->deleteChatMessage(messageID);

// Check privileges
ZoomVideoSDKChatPrivilegeType priv = chat->getChatPrivilege();
```

**Receive**: Implement `onChatNewMessageNotify()` in delegate.

### Recording Helper

**Purpose**: Cloud recording control.

```cpp
IZoomVideoSDKRecordingHelper* rec = video_sdk_obj->getRecordingHelper();

// Check permissions
ZoomVideoSDKErrors canRecord = rec->canStartRecording();

if (canRecord == ZoomVideoSDKErrors_Success) {
    // Start recording
    rec->startCloudRecording();
}

// Stop recording
rec->stopCloudRecording();

// Pause/resume
rec->pauseCloudRecording();
rec->resumeCloudRecording();

// Check status
bool isRecording = rec->isCloudRecording();
```

**Receive status**: Implement `onCloudRecordingStatus()` in delegate.

### Live Stream Helper

**Purpose**: RTMP live streaming.

```cpp
IZoomVideoSDKLiveStreamHelper* stream = video_sdk_obj->getLiveStreamHelper();

// Check permissions
ZoomVideoSDKErrors canStream = stream->canStartLiveStream();

if (canStream == ZoomVideoSDKErrors_Success) {
    // Start live stream
    stream->startLiveStream("rtmp://...", "stream-key", "broadcast-url");
}

// Stop stream
stream->stopLiveStream();

// Check status
bool isStreaming = stream->isInLiveStreamingMode();
```

**Receive status**: Implement `onLiveStreamStatusChanged()` in delegate.

### Live Transcription Helper

**Purpose**: Real-time speech-to-text.

```cpp
IZoomVideoSDKLiveTranscriptionHelper* trans = video_sdk_obj->getLiveTranscriptionHelper();

// Check permissions
bool canStart = trans->canStartLiveTranscription();

if (canStart) {
    // Start transcription
    trans->startLiveTranscription();
}

// Stop transcription
trans->stopLiveTranscription();

// Set language
IVideoSDKVector<ILiveTranscriptionLanguage*>* langs = trans->getAvailableSpokenLanguages();
trans->setSpokenLanguage(langs->GetItem(0)->getLTTLanguageID());
```

**Receive messages**: Implement `onLiveTranscriptionMsgInfoReceived()` in delegate.

### Command Channel

**Purpose**: Custom command messaging between participants.

```cpp
IZoomVideoSDKCmdChannel* cmd = video_sdk_obj->getCmdChannel();

// Send command to user
cmd->sendCommand(user, "custom-command-data");
```

**Receive**: Implement `onCommandReceived()` in delegate.

### Phone Helper

**Purpose**: PSTN dial-out.

```cpp
IZoomVideoSDKPhoneHelper* phone = video_sdk_obj->getPhoneHelper();

// Get supported countries
IVideoSDKVector<IZoomVideoSDKPhoneSupportCountryInfo*>* countries = phone->getSupportCountryInfo();

// Invite by phone
phone->inviteByPhone(countryCode, phoneNumber, displayName);

// Cancel invitation
phone->cancelInviteByPhone(success_callback, fail_callback);
```

### Settings Helpers

**Purpose**: Configure audio/video/share settings.

```cpp
// Audio settings
IZoomVideoSDKAudioSettingHelper* audioSettings = video_sdk_obj->getAudioSettingHelper();
audioSettings->setMicVolume(volume);
audioSettings->setSpeakerVolume(volume);

// Video settings
IZoomVideoSDKVideoSettingHelper* videoSettings = video_sdk_obj->getVideoSettingHelper();
videoSettings->setOriginalSizeMode(true);

// Share settings
IZoomVideoSDKShareSettingHelper* shareSettings = video_sdk_obj->getShareSettingHelper();
```

---

## Level 3: Users

**Purpose**: Access individual user objects.

```cpp
// Get current user
IZoomVideoSDKUser* myself = video_sdk_obj->getSessionInfo()->getMyself();

// Get all users
IVideoSDKVector<IZoomVideoSDKUser*>* users = video_sdk_obj->getSessionInfo()->getAllUsers();

// Iterate users
for (int i = 0; i < users->GetCount(); i++) {
    IZoomVideoSDKUser* user = users->GetItem(i);

    const char* name = user->getUserName();
    bool isHost = user->isHost();
    bool isManager = user->isManager();
}
```

**User Methods**:
```cpp
// User info
const char* getUserName();
const char* getUserGuid();
bool isHost();
bool isManager();

// Video status
IZoomVideoSDKRawDataPipe* GetVideoPipe();  // Level 4

// Audio status
IZoomVideoSDKAudioStatus* getAudioStatus();

// Share status
IZoomVideoSDKRawDataPipe* GetSharePipe();  // Level 4
```

---

## Level 4: User Pipes

**Purpose**: Subscribe to raw video/share data from specific users.

### Video Pipe

```cpp
IZoomVideoSDKUser* user = /* get from session */;
IZoomVideoSDKRawDataPipe* videoPipe = user->GetVideoPipe();

// Subscribe to user's video
class VideoDelegate : public IZoomVideoSDKRawDataPipeDelegate {
    void onRawDataFrameReceived(YUVRawDataI420* data) override {
        // Process YUV420 frame
    }

    void onRawDataStatusChanged(RawDataStatus status) override {
        // Video on/off
    }
};

videoPipe->subscribe(ZoomVideoSDKResolution_720P, new VideoDelegate());

// Unsubscribe
videoPipe->unSubscribe();
```

### Share Pipe

```cpp
IZoomVideoSDKUser* user = /* get from session */;
IZoomVideoSDKRawDataPipe* sharePipe = user->GetSharePipe();

// Subscribe to user's share (same pattern as video)
sharePipe->subscribe(ZoomVideoSDKResolution_1080P, new ShareDelegate());
```

---

## Navigation Patterns

### Pattern: Feature → Helper

**"I want to do X"** → Find the helper that controls X.

| Want to... | Navigate to... |
|-----------|---------------|
| Start my audio | `getAudioHelper()->startAudio()` |
| Start my video | `getVideoHelper()->startVideo()` |
| Share my screen | `getShareHelper()->startShare()` |
| Send chat | `getChatHelper()->sendChatToAll()` |
| Start recording | `getRecordingHelper()->startCloudRecording()` |
| Start live stream | `getLiveStreamHelper()->startLiveStream()` |
| Start transcription | `getLiveTranscriptionHelper()->startLiveTranscription()` |

### Pattern: Receive Data → Pipes

**"I want to receive X from others"** → Subscribe to user pipes or implement delegate callbacks.

| Want to receive... | Navigate to... |
|-------------------|---------------|
| Others' video (raw) | `user->GetVideoPipe()->subscribe()` |
| Others' share (raw) | `user->GetSharePipe()->subscribe()` |
| Mixed audio (raw) | `getAudioHelper()->subscribe()` + `onMixedAudioRawDataReceived()` |
| Per-user audio (raw) | `getAudioHelper()->subscribe()` + `onOneWayAudioRawDataReceived()` |
| Chat messages | Implement `onChatNewMessageNotify()` |
| Commands | Implement `onCommandReceived()` |

### Pattern: Virtual Devices → Session Context

**"I want to inject custom data"** → Set virtual devices in session context BEFORE joining.

| Want to inject... | Navigate to... |
|------------------|---------------|
| Custom audio (mic) | `session_context.virtualAudioMic = new MyMic()` |
| Custom video | `session_context.externalVideoSource = new MyVideo()` |
| Virtual speaker (headless) | `session_context.virtualAudioSpeaker = new MySpeaker()` |
| Custom share | `getShareHelper()->startSharingExternalSource(source)` |

---

## Quick Reference

### Get SDK Object
```cpp
IZoomVideoSDK* sdk = CreateZoomVideoSDKObj();
```

### Get Session
```cpp
IZoomVideoSDKSession* session = sdk->getSessionInfo();
```

### Get Users
```cpp
IZoomVideoSDKUser* myself = session->getMyself();
IVideoSDKVector<IZoomVideoSDKUser*>* all = session->getAllUsers();
IVideoSDKVector<IZoomVideoSDKUser*>* remote = session->getRemoteUsers();
```

### Get Helpers
```cpp
IZoomVideoSDKAudioHelper* audio = sdk->getAudioHelper();
IZoomVideoSDKVideoHelper* video = sdk->getVideoHelper();
IZoomVideoSDKShareHelper* share = sdk->getShareHelper();
IZoomVideoSDKChatHelper* chat = sdk->getChatHelper();
IZoomVideoSDKRecordingHelper* rec = sdk->getRecordingHelper();
IZoomVideoSDKLiveStreamHelper* stream = sdk->getLiveStreamHelper();
IZoomVideoSDKLiveTranscriptionHelper* trans = sdk->getLiveTranscriptionHelper();
IZoomVideoSDKCmdChannel* cmd = sdk->getCmdChannel();
```

### Get Pipes
```cpp
IZoomVideoSDKRawDataPipe* videoPipe = user->GetVideoPipe();
IZoomVideoSDKRawDataPipe* sharePipe = user->GetSharePipe();
```

---

## Complete Navigation Example

```cpp
// Level 1: SDK Singleton
IZoomVideoSDK* sdk = CreateZoomVideoSDKObj();
sdk->initialize(init_params);
sdk->joinSession(session_context);

// Level 2A: Session Info
IZoomVideoSDKSession* session = sdk->getSessionInfo();

// Level 3: Users
IZoomVideoSDKUser* myself = session->getMyself();
IVideoSDKVector<IZoomVideoSDKUser*>* remote = session->getRemoteUsers();

// Level 4: Subscribe to remote user's video
IZoomVideoSDKUser* remoteUser = remote->GetItem(0);
IZoomVideoSDKRawDataPipe* videoPipe = remoteUser->GetVideoPipe();
videoPipe->subscribe(ZoomVideoSDKResolution_720P, videoDelegate);

// Level 2B: Control my audio
IZoomVideoSDKAudioHelper* audio = sdk->getAudioHelper();
audio->startAudio();
audio->subscribe();  // For raw audio callbacks

// Level 2B: Control my video
IZoomVideoSDKVideoHelper* video = sdk->getVideoHelper();
video->startVideo();

// Level 2B: Send chat
IZoomVideoSDKChatHelper* chat = sdk->getChatHelper();
chat->sendChatToAll("Hello!");

// Level 2B: Start recording
IZoomVideoSDKRecordingHelper* rec = sdk->getRecordingHelper();
if (rec->canStartRecording() == ZoomVideoSDKErrors_Success) {
    rec->startCloudRecording();
}
```

---

## See Also

- **[SDK Architecture Pattern](sdk-architecture-pattern.md)** - Universal 3-step pattern
- **[API Reference](../references/linux-reference.md)** - Complete API documentation
- **[Session Join Pattern](../examples/session-join-pattern.md)** - Working session join code
